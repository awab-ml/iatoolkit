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
from datetime import datetime
import logging
from typing import Optional


class TaskApiView(MethodView):
    @inject
    def __init__(self,
                 auth_service: AuthService,
                 task_service: TaskService,
                 profile_repo: ProfileRepo):
        self.auth_service = auth_service
        self.task_service = task_service
        self.profile_repo = profile_repo

    def post(self):
        try:
            auth_result = self.auth_service.verify(anonymous=True)
            if not auth_result.get("success"):
                return jsonify(auth_result), auth_result.get("status_code")

            req_data = request.get_json()
            files = request.files.getlist('files')

            required_fields = ['company', 'task_type', 'client_data']
            for field in required_fields:
                if field not in req_data:
                    return jsonify({"error": f"El campo {field} es requerido"}), 400

            company_short_name = req_data.get('company', '')
            task_type = req_data.get('task_type', '')
            client_data = req_data.get('client_data', {})
            company_task_id = req_data.get('company_task_id', 0)
            execute_at = req_data.get('execute_at', None)

            # validate date format is parameter is present
            if execute_at:
                try:
                    # date in iso format
                    execute_at = datetime.fromisoformat(execute_at)
                except ValueError:
                    return jsonify({
                        "error": "El formato de execute_at debe ser YYYY-MM-DD HH:MM:SS"
                    }), 400

            new_task = self.task_service.create_task(
                company_short_name=company_short_name,
                task_type_name=task_type,
                client_data=client_data,
                company_task_id=company_task_id,
                execute_at=execute_at,
                files=files)

            return jsonify({
                "task_id": new_task.id,
                "status": new_task.status.name
            }), 201

        except Exception as e:
            logging.exception("Error al crear la tarea: %s", str(e))
            return jsonify({"error": str(e)}), 500
