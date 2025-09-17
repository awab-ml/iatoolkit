# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import Mock, patch
from companies.rieutord.rieutord import Rieutord


class TestRieutord:

    def setup_method(self):
        self.mock_profile_repo = Mock()
        self.mock_llm_query_repo = Mock()
        self.mock_doc_type_repo = Mock()
        self.mock_search_service = Mock()
        self.mock_task_repo = Mock()
        self.mock_util = Mock()

        self.rieutord = Rieutord(
            profile_repo=self.mock_profile_repo,
            llm_query_repo=self.mock_llm_query_repo,
            doc_type_repo=self.mock_doc_type_repo,
            search_service=self.mock_search_service,
            task_repo=self.mock_task_repo,
            util=self.mock_util
        )

    @patch('companies.rieutord.rieutord.Company')
    def test_init_db(self, mock_company):
        mock_company_instance = mock_company.return_value
        mock_company_instance.id = 1

        self.mock_profile_repo.create_company.return_value = mock_company_instance

        self.rieutord.init_db()

        self.mock_profile_repo.create_company.assert_called_once_with(mock_company_instance)


    def test_handle_request_unsupported_operation(self):
        with pytest.raises(Exception, match="La operación 'unsupported_tag' no está soportada por esta empresa."):
            self.rieutord.unsupported_operation("unsupported_tag")

    def test_classify_documents_with_files(self):
        document_types = [
            Mock(name='doc1', description='desc1'),
            Mock(name='doc2', description='desc2')
        ]
        self.mock_doc_type_repo.get_all_document_types.return_value = document_types
        self.mock_util.render_prompt_from_template.return_value = 'generated_prompt'

        result = self.rieutord.classify_documents(question='What type is this document?', files=3)

        self.mock_doc_type_repo.get_all_document_types.assert_called_once()
        self.mock_util.render_prompt_from_template.assert_called_once()
        assert result == 'generated_prompt'

    def test_search_documents(self):
        self.mock_search_service.search.return_value = 'search context'

        result = self.rieutord.handle_request(action='search', query='Find document')

        self.mock_search_service.search.assert_called_once()
        assert result == 'search context'
