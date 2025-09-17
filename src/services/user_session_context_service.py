# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from infra.redis_session_manager import RedisSessionManager
from typing import List, Dict, Optional
import json


class UserSessionContextService:
    """
    Gestiona el contexto de la sesión del usuario, incluyendo el historial
    de conversación con el LLM y datos de la sesión del usuario.

    Usa RedisSessionManager para persistencia directa en Redis.
    """

    def _get_llm_history_key(self, company_short_name: str, user_identifier: str) -> str:
        user_identifier = (user_identifier or "").strip()
        if not user_identifier:
            return None
        return f"llm_history:{company_short_name}/{user_identifier}"

    def _get_user_data_key(self, company_short_name: str, user_identifier: str) -> str:
        user_identifier = (user_identifier or "").strip()
        if not user_identifier:
            return None
        return f"user_data:{company_short_name}/{user_identifier}"

    def clear_all_context(self, company_short_name: str, user_identifier: str):
        """Limpia todo el contexto de sesión para un usuario."""
        self.clear_llm_history(company_short_name, user_identifier)
        self.clear_user_session_data(company_short_name, user_identifier)

    def clear_llm_history(self, company_short_name: str, user_identifier: str):
        history_key = self._get_llm_history_key(company_short_name, user_identifier)
        if history_key:
            RedisSessionManager.remove(history_key)

    def get_last_response_id(self, company_short_name: str, user_identifier: str) -> str:
        history_key = self._get_llm_history_key(company_short_name, user_identifier)
        if not history_key:
            return None

        return RedisSessionManager.get(history_key, '')

    def save_last_response_id(self, company_short_name: str, user_identifier: str, response_id: str):
        user_identifier = (user_identifier or "").strip()
        history_key = self._get_llm_history_key(company_short_name, user_identifier)
        if not history_key or not user_identifier:
            return

        RedisSessionManager.set(history_key, response_id)

    def save_context_history(self, company_short_name: str, user_identifier: str, context_history: List[Dict]):
        history_key = f"chat_history:{company_short_name}/{user_identifier}"
        if not history_key:
            return
        RedisSessionManager.set(history_key, json.dumps(context_history))

    def get_context_history(self, company_short_name: str, user_identifier: str) -> Optional[List[Dict]]:
        history_key = f"chat_history:{company_short_name}/{user_identifier}"
        return RedisSessionManager.get_json(history_key, {})

    def save_user_session_data(self, company_short_name: str, user_identifier: str, data: dict):
        """Guarda un diccionario de datos en la sesión del usuario."""
        user_identifier = (user_identifier or "").strip()
        data_key = self._get_user_data_key(company_short_name, user_identifier)
        if data_key:
            RedisSessionManager.set_json(data_key, data)

    def get_user_session_data(self, company_short_name: str, user_identifier: str) -> dict:
        """Recupera el diccionario de datos de la sesión del usuario."""
        data_key = self._get_user_data_key(company_short_name, user_identifier)
        if not data_key:
            return {}

        return RedisSessionManager.get_json(data_key, {})

    def clear_user_session_data(self, company_short_name: str, user_identifier: str):
        """Limpia los datos de la sesión del usuario."""
        data_key = self._get_user_data_key(company_short_name, user_identifier)
        if data_key:
            RedisSessionManager.remove(data_key)