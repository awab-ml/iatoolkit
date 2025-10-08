# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from unittest.mock import MagicMock
from iatoolkit.services.search_service import SearchService
from iatoolkit.repositories.models import Document


class TestSearchService:
    def setup_method(self):
        # Mock de dependencias
        self.doc_repo = MagicMock()
        self.vs_repo = MagicMock()

        self.service = SearchService(
            doc_repo=self.doc_repo,
            vs_repo=self.vs_repo
        )


    def test_search_documents_no_results(self):
        self.vs_repo.query.return_value = []

        result = self.service.search(company_id=1, query="consulta_inexistente")
        assert result == ''


    def test_search_documents_success(self):
        # Mock de chunks devueltos por el vector store
        document = Document(id=1, company_id=1, filename='doc1.pdf', content="Contenido del documento")
        self.vs_repo.query.return_value = [document]


        # Llamar a search y verificar resultado
        result = self.service.search(company_id=1, query="consulta")

        assert result == 'documento "doc1.pdf": Contenido del documento\n'
