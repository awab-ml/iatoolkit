# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from unittest.mock import MagicMock
from flask import Flask
from iatoolkit.views.tasks_api_view import TaskApiView
from iatoolkit.services.tasks_service import TaskService
from iatoolkit.services.auth_service import AuthService
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.models import Company, ApiKey
from datetime import datetime


class TestTaskView:

    def setup_method(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.url = '/api/tasks'

        # Mock del TaskService
        self.mock_auth = MagicMock(spec=AuthService)
        self.mock_task_service = MagicMock(spec=TaskService)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)


        # Instanciamos la vista con el mock del servicio
        self.task_view = TaskApiView.as_view("tasks",
                                          auth_service=self.mock_auth,
                                          task_service=self.mock_task_service,
                                          profile_repo=self.mock_profile_repo)
        self.app.add_url_rule(self.url, view_func=self.task_view, methods=["POST"])

        self.mock_auth.verify.return_value = {"success": True, 'user_identifier': 'an_user'}
        self.payload = {
            "company": "test_company",
            "task_type": "test_type",
            "client_data": {"key": "value"}
        }


    @pytest.mark.parametrize("missing_field", ["company", "task_type", "client_data"])
    def test_post_when_missing_required_fields(self, missing_field):
        payload = {
            "company": "test_company",
            "task_type": "test_type",
            "client_data": {"key": "value"},
        }
        payload.pop(missing_field)

        response = self.client.post(self.url,json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": f"El campo {missing_field} es requerido"
        }

        self.mock_task_service.create_task.assert_not_called()

    def test_post_when_invalid_execute_at_format(self):

        self.payload['execute_at'] = "fecha-invalida"

        response = self.client.post(self.url,json=self.payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": "El formato de execute_at debe ser YYYY-MM-DD HH:MM:SS"
        }

        self.mock_task_service.create_task.assert_not_called()

    def test_post_when_internal_exception_error(self):
        self.mock_task_service.create_task.side_effect = Exception("Internal Error")

        response = self.client.post(self.url, json=self.payload)

        assert response.status_code == 500
        assert response.get_json() == {
            "error": "Internal Error"
        }

        self.mock_task_service.create_task.assert_called_once()

    def test_post_when_successful_creation(self):
        mocked_task = MagicMock()
        mocked_task.id = 123
        mocked_task.status.name = "CREATED"
        self.mock_task_service.create_task.return_value = mocked_task

        payload = {
            "company": "test_company",
            "company_task_id": 100,
            "task_type": "test_type",
            "client_data": {"key": "value"},
            "execute_at": "2024-04-17 10:00:00"
        }

        response = self.client.post(self.url, json=payload)

        assert response.status_code == 201
        assert response.get_json() == {
            "task_id": 123,
            "status": "CREATED"
        }

        execute_datetime = datetime.fromisoformat(payload["execute_at"])

        self.mock_task_service.create_task.assert_called_once_with(
            company_short_name="test_company",
            task_type_name="test_type",
            client_data={"key": "value"},
            company_task_id=100,
            execute_at=execute_datetime,
            files=[]
        )


    def test_post_when_no_auth(self):
        self.mock_auth.verify.return_value = {"success": False, 'status_code': 401}

        response = self.client.post(self.url, json=self.payload)
        assert response.status_code == 401
