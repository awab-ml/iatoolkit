# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit

import pytest
from unittest.mock import MagicMock, patch
from injector import Injector
from iatoolkit.base_company import BaseCompany
from iatoolkit.company_registry import get_company_registry, register_company
from services.dispatcher_service import Dispatcher
from common.exceptions import IAToolkitException
from repositories.llm_query_repo import LLMQueryRepo
from services.excel_service import ExcelService
from services.mail_service import MailService
from common.util import Utility


# Una clase de empresa Mock para usar en los tests
class MockMaxxa(BaseCompany):
    def init_db(self): pass

    def get_company_context(self, **kwargs) -> str: return "Company Context Maxxa"

    def handle_request(self, tag: str, params: dict) -> dict: return {"result": "maxxa_response"}

    def start_execution(self): pass

    def get_metadata_from_filename(self, filename: str) -> dict: return {}


class TestDispatcher:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura los mocks, el registro y el Dispatcher."""
        # Limpiar el registro antes de cada test para evitar interferencias
        registry = get_company_registry()
        registry.clear()

        # Mocks para los servicios inyectados en el Dispatcher
        self.mock_prompt_manager = MagicMock()
        self.mock_llm_query_repo = MagicMock(spec=LLMQueryRepo)
        self.excel_service = MagicMock(spec=ExcelService)
        self.mail_service = MagicMock(spec=MailService)
        self.util = MagicMock(spec=Utility)

        # Crear un mock para nuestra clase de empresa
        self.mock_maxxa_instance = MockMaxxa(
            profile_repo=MagicMock(),
            llm_query_repo=self.mock_llm_query_repo
        )
        # Mockear los métodos que vamos a llamar
        self.mock_maxxa_instance.init_db = MagicMock()
        self.mock_maxxa_instance.handle_request = MagicMock(return_value={"result": "maxxa_response"})
        self.mock_maxxa_instance.get_company_context = MagicMock(return_value="Company Context Maxxa")
        self.mock_maxxa_instance.start_execution = MagicMock(return_value=True)

        # REGISTRAR la clase en el registry
        register_company("maxxa", MockMaxxa)

        # Dispatcher inicializado con los mocks
        self.dispatcher = Dispatcher(
            prompt_service=self.mock_prompt_manager,
            llmquery_repo=self.mock_llm_query_repo,
            util=self.util,
            excel_service=self.excel_service,
            mail_service=self.mail_service
        )

        # Simular la inyección y la instanciación de empresas
        mock_injector = Injector()
        # Le decimos al injector que cuando pida MockMaxxa, devuelva nuestra instancia mockeada
        mock_injector.binder.bind(MockMaxxa, to=self.mock_maxxa_instance)
        self.dispatcher.set_injector(mock_injector)

        # Ahora self.dispatcher.company_classes contiene {'maxxa': self.mock_maxxa_instance}

    def test_init_db_calls_init_db_on_each_company(self):
        """Test que init_db llama a init_db de cada empresa registrada."""
        self.dispatcher.init_db()
        self.mock_maxxa_instance.init_db.assert_called_once()

    def test_dispatch_maxxa(self):
        """Test que dispatch funciona correctamente para una empresa válida."""
        result = self.dispatcher.dispatch("maxxa", "financial_data", key='a value')

        self.mock_maxxa_instance.handle_request.assert_called_once_with("financial_data", key='a value')
        assert result == {"result": "maxxa_response"}

    def test_dispatch_invalid_company(self):
        """Test que dispatch lanza excepción para empresa no configurada."""
        with pytest.raises(IAToolkitException) as excinfo:
            self.dispatcher.dispatch("invalid_company", "some_tag")

        assert "Empresa 'invalid_company' no configurada" in str(excinfo.value)

    def test_dispatch_method_exception(self):
        """Valida que el dispatcher maneje excepciones lanzadas por las empresas."""
        self.mock_maxxa_instance.handle_request.side_effect = Exception("Method error")

        with pytest.raises(IAToolkitException) as excinfo:
            self.dispatcher.dispatch("maxxa", "financial_data")

        assert "Error en function call 'financial_data'" in str(excinfo.value)
        assert "Method error" in str(excinfo.value)

    def test_dispatch_system_function(self):
        """Test que dispatch maneja correctamente las funciones del sistema."""
        self.excel_service.excel_generator.return_value = {"file": "test.xlsx"}

        result = self.dispatcher.dispatch("maxxa", "iat_generate_excel", filename="test.xlsx")

        self.excel_service.excel_generator.assert_called_once_with(filename="test.xlsx")
        self.mock_maxxa_instance.handle_request.assert_not_called()
        assert result == {"file": "test.xlsx"}

    def test_get_company_context(self):
        """Test que get_company_context funciona correctamente."""
        # Simular que no hay archivos de contexto para simplificar
        self.util.get_files_by_extension.return_value = []

        params = {"param1": "value1"}
        result = self.dispatcher.get_company_context("maxxa", **params)

        self.mock_maxxa_instance.get_company_context.assert_called_once_with(**params)
        assert "Company Context Maxxa" in result

    def test_start_execution_when_ok(self):
        """Test que start_execution funciona correctamente."""
        result = self.dispatcher.start_execution()

        assert result is True
        self.mock_maxxa_instance.start_execution.assert_called_once()

    def test_dispatcher_with_no_companies_registered(self):
        """Test que el dispatcher funciona si no se registra ninguna empresa."""
        # Limpiar el registro
        get_company_registry().clear()

        # Crear un nuevo dispatcher sin empresas
        dispatcher = Dispatcher(
            prompt_service=self.mock_prompt_manager,
            llmquery_repo=self.mock_llm_query_repo,
            util=self.util,
            excel_service=self.excel_service,
            mail_service=self.mail_service
        )
        dispatcher.set_injector(Injector())  # Un injector vacío

        # Verificar que no hay empresas registradas
        assert len(dispatcher.company_classes) == 0

        # Verificar que dispatch falla para cualquier empresa
        with pytest.raises(IAToolkitException) as excinfo:
            dispatcher.dispatch("any_company", "some_action")
        assert "Empresa 'any_company' no configurada" in str(excinfo.value)