# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask.views import MethodView
from flask import request, jsonify
from iatoolkit.services.tasks_service import TaskService
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.services.auth_service import AuthService
from injector import inject
import logging
from typing import Optional


class TaskReviewApiView(MethodView):
    @inject
    def __init__(self,
                 auth_service: AuthService,
                 task_service: TaskService,
                 profile_repo: ProfileRepo):
        self.auth_service = auth_service
        self.task_service = task_service
        self.profile_repo = profile_repo

    def post(self, task_id: int):
        auth_result = self.auth_service.verify(anonymous=True)
        if not auth_result.get("success"):
            return jsonify(auth_result), auth_result.get("status_code")

        try:
            req_data = request.get_json()
            required_fields = ['review_user', 'approved']
            for field in required_fields:
                if field not in req_data:
                    return jsonify({"error": f"El campo {field} es requerido"}), 400

            review_user = req_data.get('review_user', '')
            approved = req_data.get('approved', False)
            comment = req_data.get('comment', '')

            new_task = self.task_service.review_task(
                task_id=task_id,
                review_user=review_user,
                approved=approved,
                comment=comment)

            return jsonify({
                "task_id": new_task.id,
                "status": new_task.status.name
            }), 200

        except Exception as e:
            logging.exception("Error al revisar la tarea: %s", str(e))
            return jsonify({"error": str(e)}), 500
