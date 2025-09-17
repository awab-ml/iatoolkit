# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import Mock, patch
from companies.mayo.mayo import Mayo
import json

class TestMayo:

    def setup_method(self):
        self.mock_profile_repo = Mock()
        self.mock_llm_query_repo = Mock()
        self.mock_document_service = Mock()
        self.mock_util = Mock()
        self.mock_file_connector_factory = Mock()

        self.mayo = Mayo(
            profile_repo=self.mock_profile_repo,
            llm_query_repo=self.mock_llm_query_repo,
            document_service=self.mock_document_service,
            util=self.mock_util,
            file_connector_factory=self.mock_file_connector_factory
        )

    @patch('companies.mayo.mayo.Company')
    @patch('companies.mayo.mayo.Function')
    @patch('os.getenv')
    def test_init_db(self, mock_getenv, mock_function, mock_company):
        mock_company_instance = mock_company.return_value
        mock_function_instance = mock_function.return_value
        mock_company_instance.id = 1
        mock_function_instance.id = 2

        mock_getenv.return_value = None  # Simula un entorno no-dev
        self.mock_profile_repo.create_company.return_value = mock_company_instance
        self.mock_llm_query_repo.create_or_update_function.return_value = mock_function_instance

        self.mayo.init_db()

        self.mock_profile_repo.create_company.assert_called_once_with(mock_company_instance)
        self.mock_llm_query_repo.create_or_update_function.assert_called_once_with(mock_function(company_id=1,
                                                                                               name='Salud',
                                                                                               description='temas de salud, informes de laboratorios clinicos, examenes de imagenes'))

    def test_handle_request_clinical_data(self):
        connector = {'type': 's3'}
        mock_response = {'context': 'mocked_context', 'prompt': 'mocked_prompt'}
        self.mayo.clinical_data = Mock(return_value=mock_response)

        result = self.mayo.handle_request(action="clinical_data",
                                          connector=connector)

        self.mayo.clinical_data.assert_called_once()
        assert result == mock_response

    def test_handle_request_unsupported_operation(self):
        with pytest.raises(Exception, match="La operación 'unsupported_tag' no está soportada por esta empresa."):
            self.mayo.handle_request(action="unsupported_tag", params={})

    @patch('companies.mayo.mayo.FileProcessorConfig')
    @patch('companies.mayo.mayo.FileProcessor')
    def test_clinical_data(self, mock_file_processor, mock_file_processor_config):
        connector_mock = Mock()
        self.mock_file_connector_factory.create.return_value = connector_mock

        processor_mock = mock_file_processor.return_value
        self.mock_document_service.read_pdf.return_value = "mocked_text"

        self.mayo.concatenated_content = [
            {"filename": "file1.pdf", "content": "content1"},
            {"filename": "file2.pdf", "content": "content2"}
        ]

        result = self.mayo.clinical_data(rut='278637-2')
        context = json.loads(result)
        assert len(context) == 2
        assert context[0]['resultado de examen'] == 'content1'


    @patch('companies.mayo.mayo.FileProcessorConfig')
    @patch('companies.mayo.mayo.FileProcessor')
    def test_clinical_data_no_rut(self,mock_file_processor, mock_file_processor_config):

        result = self.mayo.clinical_data()
        assert result == 'missing rut'

    def test_process_file_content(self):
        self.mock_document_service.read_pdf.return_value = "mocked_text"
        self.mayo.concatenated_content = []

        self.mayo.process_file_content("file.pdf", b"mocked_content", {})

        self.mock_document_service.read_pdf.assert_called_once_with(b"mocked_content")
        assert self.mayo.concatenated_content == [{'filename': "file.pdf", 'content': "mocked_text"}]

