# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from unittest.mock import MagicMock
from flask import Flask
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.views.tasks_review_api_view import TaskReviewApiView
from iatoolkit.services.tasks_service import TaskService, TaskStatus
from iatoolkit.services.auth_service import AuthService

# --- Constantes para los Tests ---
MOCK_COMPANY_SHORT_NAME = "test-company"
MOCK_USER_IDENTIFIER = "user-123"

class TestTaskReviewView:

    def setup_method(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.url = '/tasks/review/1'

        self.mock_auth = MagicMock(spec=AuthService)
        self.mock_task_service = MagicMock(spec=TaskService)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)

        # Instanciamos la vista con el mock del servicio
        self.task_review_view = TaskReviewApiView.as_view("tasks-review",
                                                       auth_service=self.mock_auth,
                                                       task_service=self.mock_task_service,
                                                       profile_repo=self.mock_profile_repo)
        self.app.add_url_rule('/tasks/review/<int:task_id>', view_func=self.task_review_view, methods=["POST"])

        self.mock_auth.verify.return_value = {"success": True, 'user_identifier': MOCK_USER_IDENTIFIER}
        self.payload = {
            "review_user": "test_username",
            "approved": True,
            "comment": "this is a comment",
        }

    @pytest.mark.parametrize("missing_field", ["review_user", "approved"])
    def test_post_when_missing_required_fields(self, missing_field):
        payload = {
            "review_user": "test_username",
            "approved": True,
            "comment": "this is a comment",
        }
        payload.pop(missing_field)
        response = self.client.post(self.url, json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": f"El campo {missing_field} es requerido"
        }

        self.mock_task_service.create_task.assert_not_called()

    def test_post_when_internal_exception_error(self):
        self.mock_task_service.review_task.side_effect = Exception("Internal Error")
        response = self.client.post(self.url, json=self.payload)

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

        response = self.client.post(self.url, json=self.payload)

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

    def test_post_when_no_auth(self):
        self.mock_auth.verify.return_value = {"success": False, 'status_code': 401}

        response = self.client.post(self.url, json=self.payload)
        assert response.status_code == 401

