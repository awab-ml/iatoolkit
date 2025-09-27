# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from iatoolkit import Company, Function
from iatoolkit import ProfileRepo
from iatoolkit import LLMQueryRepo
from iatoolkit import DatabaseManager
from iatoolkit import SqlService
from iatoolkit import BaseCompany
from injector import inject
from companies.sample_company.configuration import FUNCTION_LIST
from companies.sample_company.sample_company_database import SampleCompanyDatabase
import os


class SampleCompany(BaseCompany):
    @inject
    def __init__(self,
            profile_repo: ProfileRepo,
            llm_query_repo: LLMQueryRepo,
            sql_service: SqlService):
        super().__init__(profile_repo, llm_query_repo)
        self.sql_service = sql_service
        self.company = self.profile_repo.get_company_by_short_name('sample_company')
        self.sample_db_manager = None
        self.sample_database = None

        # connect to Internal database
        sample_db_uri = os.getenv('SAMPLE_DATABASE_URI')
        if not sample_db_uri:
            # if not exists use the same iatoolkit database
            sample_db_uri = os.getenv('DATABASE_URI')

        if sample_db_uri:
            self.sample_db_manager = DatabaseManager(sample_db_uri, register_pgvector=False)
            self.sample_database = SampleCompanyDatabase(self.sample_db_manager)

    def register_company(self):
        # Initialize the company in the database if not exists
        c = Company(name='Sample Company',
                    short_name='sample_company',
                    allow_jwt=True,
                    parameters={})
        c = self.profile_repo.create_company(c)

        # create or update the function list
        for function in FUNCTION_LIST:
            self.llm_query_repo.create_or_update_function(
                Function(
                    company_id=c.id,
                    name=function['function_name'],
                    description=function['description'],
                    parameters=function['params']
                )
            )

    # Return a global context used by this company: business description, schemas, database models
    def get_company_context(self, **kwargs) -> str:
        company_context = ''
        if self.sample_db_manager:
            company_context += self.get_schema_definitions(self.sample_db_manager)

        return company_context

    def start_execution(self) -> dict:
        return {}

    def get_metadata_from_filename(self, filename: str) -> dict:
        return {}

    def handle_request(self, action: str, **kwargs) -> str:
        if action == "sql_query":
            sql_query = kwargs.get('query')
            return self.sql_service.exec_sql(self.sample_db_manager, sql_query)
        else:
            return self.unsupported_operation(action)

    def get_user_info(self, user_identifier: str) -> dict:
        user_data = {
            "id": user_identifier,
            "user_email": 'sample@sample_company.com',
            "user_fullname": 'Sample User',
            "super_user": False,
            "company_id": self.company.id,
            "company_name": self.company.name,
            "company_short_name": self.company.short_name,
            "is_local": False,
            "extras": {}
        }
        return user_data

    def get_schema_definitions(self, db_manager: DatabaseManager) -> str:
        """
        Genera las definiciones de esquema para todas las tablas del modelo.
        """
        model_tables = [
            {'table_name': 'sample_customers', 'schema_name': 'customer'},
            {'table_name': 'sample_products', 'schema_name': 'product'},
            {'table_name': 'sample_orders', 'schema_name': 'order'},
            {'table_name': 'sample_order_items', 'schema_name': 'order_item'},
        ]

        db_context = ''
        for table in model_tables:
            try:
                table_definition = db_manager.get_table_schema(
                    table_name=table['table_name'],
                    schema_name=table['schema_name'],
                    exclude_columns=[]
                )
                db_context += table_definition
            except RuntimeError as e:
                print(f"Advertencia al generar esquema para {table['table_name']}: {e}")

        return db_context
