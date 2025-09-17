# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from repositories.vs_repo import VSRepo
from repositories.document_repo import DocumentRepo
from injector import inject


class SearchService:
    @inject
    def __init__(self,
                 doc_repo: DocumentRepo,
                 vs_repo: VSRepo):
        super().__init__()
        self.vs_repo = vs_repo
        self.doc_repo = doc_repo

    def search(self, company_id:  int, query: str, metadata_filter: dict = None) -> str:
        document_list = self.vs_repo.query(company_id=company_id,
                                           query_text=query,
                                           metadata_filter=metadata_filter)

        search_context = ''
        for doc in document_list:
            search_context += f'documento "{doc.filename}"'
            if doc.meta and 'document_type' in doc.meta:
                search_context += f' tipo: {doc.meta.get('document_type', '')}'
            search_context += f': {doc.content}\n'

        return search_context
