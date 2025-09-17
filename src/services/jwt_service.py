# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import jwt
import time
import logging
from injector import singleton, inject
from typing import Optional, Dict, Any
from flask import Flask


@singleton
class JWTService:
    @inject
    def __init__(self,  app: Flask):
        # Acceder a la configuración directamente desde app.config
        try:
            self.secret_key = app.config['JWT_SECRET_KEY']
            self.algorithm = app.config['JWT_ALGORITHM']
        except KeyError as e:
            logging.error(f"Configuración JWT faltante en app.config: {e}. JWTService no funcionará correctamente.")
            raise RuntimeError(f"Configuración JWT esencial faltante: {e}")

    def generate_chat_jwt(self,
                          company_id: int,
                          company_short_name: str,
                          external_user_id: str,
                          expires_delta_seconds: int) -> Optional[str]:
        # generate a JWT for a chat session
        try:
            payload = {
                'company_id': company_id,
                'company_short_name': company_short_name,
                'external_user_id': external_user_id,
                'exp': time.time() + expires_delta_seconds,
                'iat': time.time(),
                'type': 'chat_session'  # Identificador del tipo de token
            }
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            return token
        except Exception as e:
            logging.error(f"Error al generar JWT para company {company_id}, user {external_user_id}: {e}")
            return None

    def validate_chat_jwt(self, token: str, expected_company_short_name: str) -> Optional[Dict[str, Any]]:
        """
        Valida un JWT de sesión de chat.
        Retorna el payload decodificado si es válido y coincide con la empresa, o None.
        """
        if not token:
            return None
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Validaciones adicionales
            if payload.get('type') != 'chat_session':
                logging.warning(f"Validación JWT fallida: tipo incorrecto '{payload.get('type')}'")
                return None

            if payload.get('company_short_name') != expected_company_short_name:
                logging.warning(
                    f"Validación JWT fallida: company_short_name no coincide. "
                    f"Esperado: {expected_company_short_name}, Obtenido: {payload.get('company_short_name')}"
                )
                return None

            # external_user_id debe estar presente
            if 'external_user_id' not in payload or not payload['external_user_id']:
                logging.warning(f"Validación JWT fallida: external_user_id ausente o vacío.")
                return None

            # company_id debe estar presente
            if 'company_id' not in payload or not isinstance(payload['company_id'], int):
                logging.warning(f"Validación JWT fallida: company_id ausente o tipo incorrecto.")
                return None

            logging.debug(
                f"JWT validado exitosamente para company: {payload.get('company_short_name')}, user: {payload.get('external_user_id')}")
            return payload

        except jwt.ExpiredSignatureError:
            logging.info(f"Validación JWT fallida: token expirado para {expected_company_short_name}")
            return None
        except jwt.InvalidTokenError as e:
            logging.warning(f"Validación JWT fallida: token inválido para {expected_company_short_name}. Error: {e}")
            return None
        except Exception as e:
            logging.error(f"Error inesperado durante validación de JWT para {expected_company_short_name}: {e}")
            return None
