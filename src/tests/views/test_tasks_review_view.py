# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from unittest.mock import MagicMock
from flask import Flask
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.views.tasks_review_view import TaskReviewView
from iatoolkit.services.tasks_service import TaskService, TaskStatus
from iatoolkit.repositories.models import Company, ApiKey



class TestTaskReviewView:

    def setup_method(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()

        self.mock_task_service = MagicMock(spec=TaskService)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)

        # Instanciamos la vista con el mock del servicio
        self.task_review_view = TaskReviewView.as_view("tasks-review",
                                                       task_service=self.mock_task_service,
                                                       profile_repo=self.mock_profile_repo)
        self.app.add_url_rule('/tasks/review/<int:task_id>', view_func=self.task_review_view, methods=["POST"])

        # API Key exitosa
        self.api_key = ApiKey(key="test_key", company_id=100)
        self.api_key.company = Company(id=100, name="Test Company", short_name="test_company")
        self.mock_profile_repo.get_active_api_key_entry.return_value = self.api_key
        self.valid_header = {"Authorization": f"Bearer {self.api_key.key}"}

    @pytest.mark.parametrize("missing_field", ["review_user", "approved"])
    def test_post_when_missing_required_fields(self, missing_field):
        payload = {
            "review_user": "test_username",
            "approved": True,
            "comment": "this is a comment",
        }
        payload.pop(missing_field)

        response = self.client.post('/tasks/review/1',
                                    headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": f"El campo {missing_field} es requerido"
        }

        self.mock_task_service.create_task.assert_not_called()

    def test_post_when_internal_exception_error(self):
        self.mock_task_service.review_task.side_effect = Exception("Internal Error")

        payload = {
            "review_user": "test_username",
            "approved": True,
            "comment": "this is a comment",
        }

        response = self.client.post('/tasks/review/1',
                                    headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 500
        assert response.get_json() == {
            "error": "Internal Error"
        }

        self.mock_task_service.review_task.assert_called_once()

    def test_post_when_successful_creation(self):
        mocked_task = MagicMock()
        mocked_task.id = 123
        mocked_task.status = TaskStatus.aprobada
        self.mock_task_service.review_task.return_value = mocked_task

        payload = {
            "review_user": "test_username",
            "approved": True,
            "comment": "this is a comment",
        }

        response = self.client.post('/tasks/review/1',
                                    headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 200
        assert response.get_json() == {
            "task_id": 123,
            "status": "aprobada"
        }

        self.mock_task_service.review_task.assert_called_once_with(
            task_id=1,
            review_user="test_username",
            approved=True,
            comment="this is a comment"
        )
