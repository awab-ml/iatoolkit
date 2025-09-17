# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import Mock, patch
from companies.mastercard.mastercard import Mastercard
from services.sql_service import SqlService

class TestMastercard:
    def setup_method(self):
        """Configura el ambiente de prueba antes de cada test"""
        self.mock_profile_repo = Mock()
        self.mock_llm_query_repo = Mock()
        self.mock_db_manager = Mock()
        self.mock_util = Mock()
        self.mock_task_repo = Mock()
        self.mock_sql_service = Mock()
        self.mock_session = Mock()

        # Patch para Transaction
        self.transaction_patcher = patch('companies.mastercard.mastercard.Transaction')
        self.mock_transaction = self.transaction_patcher.start()

        # Configurar el mock del session
        self.mock_db_manager.get_session.return_value = self.mock_session

        self.mastercard = Mastercard(
            profile_repo=self.mock_profile_repo,
            llm_query_repo=self.mock_llm_query_repo,
            task_repo=self.mock_task_repo,
            db_manager=self.mock_db_manager,
            sql_service=self.mock_sql_service,
            util=self.mock_util
        )

    def teardown_method(self):
        """Limpia los mocks después de cada test"""
        self.transaction_patcher.stop()

    @patch('companies.mastercard.mastercard.Company')
    @patch('companies.mastercard.mastercard.Function')
    def test_init_db(self, mock_function_class, mock_company_class):
        # Configurar mock de Company
        mock_company_instance = Mock()
        mock_company_instance.id = 1
        mock_company_class.return_value = mock_company_instance

        # Configurar el comportamiento del profile_repo
        self.mock_profile_repo.create_company.return_value = mock_company_instance

        # Configurar mock de Intent
        mock_function_instance = Mock()
        mock_function_class.return_value = mock_function_instance

        # Ejecutar método
        self.mastercard.init_db()

        # Verificar la creación de la compañía
        mock_company_class.assert_called_once_with(
            name='Mastercard',
            short_name='mastercard',
            logo_file='logo_tarjeta.png',
            parameters={}
        )
        self.mock_profile_repo.create_company.assert_called_once_with(mock_company_instance)
        self.mock_llm_query_repo.create_or_update_function.assert_called()

    def test_get_company_context(self):
        """Test para obtener el contexto de la empresa"""
        # Configurar mocks
        self.mock_db_manager.get_table_schema.return_value = "CREATE TABLE schema..."
        self.mock_util.render_prompt_from_template.return_value = "rendered template"

        # Ejecutar método
        result = self.mastercard.get_company_context()

        # Verificaciones
        self.mock_db_manager.get_table_schema.assert_called_once_with('transactions')
        assert 'transactions' in result

    def test_handle_request_unsupported(self):
        """Test para operación no soportada"""
        with pytest.raises(Exception) as excinfo:
            self.mastercard.handle_request('unsupported_operation')
        assert str(excinfo.value) == "La operación 'unsupported_operation' no está soportada por esta empresa."

    def test_transaction_model(self):
        """Test para el modelo Transaction"""
        #