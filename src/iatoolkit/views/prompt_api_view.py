# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask import jsonify, request
from flask.views import MethodView
from iatoolkit.services.prompt_service import PromptService
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.repositories.llm_query_repo import LLMQueryRepo
from iatoolkit.services.auth_service import AuthService
from injector import inject
import logging


class PromptApiView(MethodView):
    @inject
    def __init__(self,
                 auth_service: AuthService,
                 prompt_service: PromptService,
                 profile_service: ProfileService,
                 llm_query_repo: LLMQueryRepo):
        self.auth_service = auth_service
        self.prompt_service = prompt_service
        self.profile_service = profile_service
        self.llm_query_repo = llm_query_repo

    def get(self, company_short_name, prompt_name=None):
        """
        GET /: Lista el árbol de prompts (Categorías > Prompts).
        GET /<name>: Devuelve detalle completo: metadata + contenido texto.
        """
        try:
            # get access credentials
            auth_result = self.auth_service.verify(anonymous=True)
            if not auth_result.get("success"):
                return jsonify(auth_result), auth_result.get('status_code')

            if prompt_name:
                company = self.profile_service.get_company_by_short_name(company_short_name)

                # get the prompt object from database
                prompt_obj = self.llm_query_repo.get_prompt_by_name(company, prompt_name)

                # get the prompt content
                content = self.prompt_service.get_prompt_content(company, prompt_name)

                return jsonify({
                    "meta": prompt_obj.to_dict(),
                    "content": content
                })
            else:
                # return all the prompts
                return jsonify(self.prompt_service.get_user_prompts(company_short_name))

        except Exception as e:
            logging.exception(
                f"unexpected error getting company prompts: {e}")
            return jsonify({"error_message": str(e)}), 500

    def put(self, company_short_name, prompt_name):
        """
        Actualiza el prompt (texto y configuración).
        Payload: { "content": "...", "description": "...", "custom_fields": [...] }
        """
        auth_result = self.auth_service.verify()
        if not auth_result.get("success"):
            return jsonify(auth_result), 401

        data = request.get_json()
        self.prompt_service.save_prompt(company_short_name, prompt_name, data)
        return jsonify({"status": "success"})
