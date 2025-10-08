# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask.views import MethodView
from flask import request, jsonify
from iatoolkit.services.tasks_service import TaskService
from iatoolkit.repositories.profile_repo import ProfileRepo
from injector import inject
from datetime import datetime
import logging
from typing import Optional


class TaskView(MethodView):
    @inject
    def __init__(self, task_service: TaskService, profile_repo: ProfileRepo):
        self.task_service = task_service
        self.profile_repo = profile_repo

    def _authenticate_requesting_company_via_api_key(self) -> tuple[
        Optional[int], Optional[str], Optional[tuple[dict, int]]]:
        """
        Autentica a la compañía  usando su API Key.
        Retorna (company_id, company_short_name, None) en éxito.
        Retorna (None, None, (error_json, status_code)) en fallo.
        """
        api_key_header = request.headers.get('Authorization')
        if not api_key_header or not api_key_header.startswith('Bearer '):
            return None, None, ({"error": "API Key faltante o mal formada en el header Authorization"}, 401)

        api_key_value = api_key_header.split('Bearer ')[1]
        try:
            api_key_entry = self.profile_repo.get_active_api_key_entry(api_key_value)
            if not api_key_entry:
                return None, None, ({"error": "API Key inválida o inactiva"}, 401)

            # api_key_entry.company ya está cargado por joinedload en get_active_api_key_entry
            if not api_key_entry.company:  # Sanity check
                logging.error(
                    f"ChatTokenRequest: API Key {api_key_value[:5]}... no tiene compañía asociada a pesar de ser válida.")
                return None, None, ({"error": "Error interno del servidor al verificar API Key"}, 500)

            return api_key_entry.company_id, api_key_entry.company.short_name, None

        except Exception as e:
            logging.exception(f"ChatTokenRequest: Error interno durante validación de API Key: {e}")
            return None, None, ({"error": "Error interno del servidor al validar API Key"}, 500)


    def post(self):
        try:
            # only requests with valid api-key are allowed
            auth_company_id, auth_company_short_name, error = self._authenticate_requesting_company_via_api_key()
            if error:
                return jsonify(error[0]), error[1]

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
