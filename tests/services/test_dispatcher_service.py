# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock
from services.dispatcher_service import Dispatcher
from exceptions import AppException
from repositories.llm_query_repo import LLMQueryRepo
from services.excel_service import ExcelService
from services.mail_service import MailService
from util import Utility


class TestDispatcher:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura los mocks para las empresas y el Dispatcher."""
        # Mocks para las clases de las empresas
        self.mock_maxxa = MagicMock()
        self.mock_prompt_manager = MagicMock()
        self.mock_llm_query_repo = MagicMock(spec=LLMQueryRepo)
        self.excel_service = MagicMock(spec=ExcelService)
        self.mail_service = MagicMock(spec=MailService)
        self.util = MagicMock(spec=Utility)

        # Dispatcher inicializado con los mocks
        self.dispatcher = Dispatcher(
            prompt_service=self.mock_prompt_manager,
            llmquery_repo=self.mock_llm_query_repo,
            util=self.util,
            excel_service=self.excel_service,
            mail_service=self.mail_service,
            maxxa=self.mock_maxxa
        )

        # Mock de respuestas genéricas de cada empresa
        self.mock_maxxa.handle_request.return_value = {"result": "maxxa_response"}

    def test_init_db_calls_init_db_on_each_company(self):
        self.dispatcher.init_db()
        self.mock_maxxa.init_db.assert_called_once()

    def test_dispatch_maxxa(self):
        result = self.dispatcher.dispatch("maxxa", "finantial_data", key='a value')

        self.mock_maxxa.handle_request.assert_called_once_with("finantial_data", key='a value')
        assert result == {"result": "maxxa_response"}

    def test_dispatch_invalid_company(self):
        with pytest.raises(AppException) as excinfo:
            self.dispatcher.dispatch("invalid_company", "some_tag")

        # Validar que se lanza la excepción correcta
        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Empresa no configurada: invalid_company" in str(excinfo.value)

    def test_dispatch_method_exception(self):
        """Valida que el dispatcher maneje excepciones lanzadas por las empresas."""
        # Configurar un mock para arrojar excepción
        self.mock_maxxa.handle_request.side_effect = Exception("Method error")

        with pytest.raises(AppException) as excinfo:
            self.dispatcher.dispatch("maxxa", "finantial_data")

        # Validar que se captura y transforma la excepción
        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Error en function call 'finantial_data': Method error" in str(excinfo.value)

    def test_get_company_context(self):
        self.mock_maxxa.get_company_context.return_value = "Company Context Maxxa"

        # Probar cada contexto
        params = {"param1": "value1"}
        assert self.dispatcher.get_company_context("maxxa", **params) == "Company Context Maxxa"

        self.mock_maxxa.get_company_context.assert_called_once_with(**params)


    def test_start_execution_when_ok(self):
        # Configurar los mocks para cada compañía
        self.mock_maxxa.start_execution.return_value = True

        assert self.dispatcher.start_execution() == True
        self.mock_maxxa.start_execution.assert_called_once()


    def test_start_execution_when_exception(self):
        self.mock_maxxa.start_execution.side_effect = Exception('an error')
        with pytest.raises(Exception):
            self.dispatcher.start_execution()