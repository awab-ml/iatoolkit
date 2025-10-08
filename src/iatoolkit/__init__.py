"""
IAToolkit Package
"""

# Expose main classes and functions at the top level of the package

# Assuming 'toolkit.py' contains the IAToolkit class
from .iatoolkit import IAToolkit, create_app
from .iatoolkit import current_iatoolkit

# Assuming 'app_factory.py' contains create_app and register_company
from .company_registry import register_company

# Assuming 'base_company.py' contains BaseCompany
from .base_company import BaseCompany

# --- Services ---
# Assuming they are in a 'services' sub-package
from iatoolkit.services.sql_service import SqlService
from iatoolkit.services.excel_service import ExcelService
from iatoolkit.services.dispatcher_service import Dispatcher
from iatoolkit.services.document_service import DocumentService
from iatoolkit.services.search_service import SearchService
from iatoolkit.services.load_documents_service import LoadDocumentsService
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.llm_query_repo import LLMQueryRepo

from iatoolkit.services.query_service import QueryService
from iatoolkit.services.prompt_manager_service import PromptService
from iatoolkit.repositories.database_manager import DatabaseManager

from iatoolkit.infra.call_service import CallServiceClient
from iatoolkit.common.util import Utility


from iatoolkit.repositories.models import Base, Company, Function, TaskType, Prompt, PromptCategory


__all__ = [
    'IAToolkit',
    'create_app',
    'current_iatoolkit',
    'register_company',
    'BaseCompany',
    'SqlService',
    'ExcelService',
    'Dispatcher',
    'DocumentService',
    'SearchService',
    'QueryService',
    'LoadDocumentsService',
    'ProfileRepo',
    'LLMQueryRepo',
    'PromptService',
    'DatabaseManager',
    'CallServiceClient',
    'Utility',
    'Company',
    'Function',
    'TaskType',
    'Base',
    'Prompt',
    'PromptCategory'
]
