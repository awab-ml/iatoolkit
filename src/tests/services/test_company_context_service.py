
# tests/services/test_company_context_service.py

import pytest
from unittest.mock import MagicMock, call
from iatoolkit.services.company_context_service import CompanyContextService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.common.interfaces.asset_storage import AssetRepository, AssetType
from iatoolkit.services.sql_service import SqlService
from iatoolkit.repositories.database_manager import DatabaseManager
from iatoolkit.common.util import Utility
from iatoolkit.common.exceptions import IAToolkitException

# --- Mock Data for different test scenarios ---

# Simulates include_all_tables: true
MOCK_CONFIG_INCLUDE_ALL = {
    'sql': [{
        'database': 'main_db',
        'include_all_tables': True
    }]
}

# Simulates an explicit list of tables
MOCK_CONFIG_EXPLICIT_LIST = {
    'sql': [{
        'database': 'main_db',
        'tables': {
            'products': {},
            'customers': {}
        }
    }]
}

# Simulates include_all_tables with exclusions and overrides
MOCK_CONFIG_COMPLEX = {
    'sql': [{
        'database': 'main_db',
        'include_all_tables': True,
        'exclude_tables': ['logs'],
        'exclude_columns': ['id', 'created_at'],  # Global exclude
        'tables': {
            'users': {
                'exclude_columns': ['password_hash']  # Local override
            },
            'user_profiles': {
                'schema_name': 'profiles'  # Schema override
            }
        }
    }]
}


class TestCompanyContextService:
    """
    Unit tests for the CompanyContextService, updated for the new data_sources schema
    and the DatabaseProvider interface.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up mocks for all dependencies and instantiate the service."""
        self.mock_sql_service = MagicMock(spec=SqlService)
        self.mock_utility = MagicMock(spec=Utility)
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_asset_repo = MagicMock(spec=AssetRepository)  # <--- Mock Repo

        # NOTE: DatabaseProvider mock is no longer needed for these tests as we mock sql_service.get_database_structure directly

        self.context_service = CompanyContextService(
            sql_service=self.mock_sql_service,
            utility=self.mock_utility,
            config_service=self.mock_config_service,
            asset_repo=self.mock_asset_repo
        )
        self.COMPANY_NAME = 'acme'

    # --- Tests for New SQL Context Logic ---
        def test_sql_context_with_include_all_tables(self):
            """
            GIVEN config has 'include_all_tables: true'
            WHEN _get_sql_schema_context is called
            THEN it should process all tables returned by the db structure.
            """
            # Arrange
            self.mock_config_service.get_configuration.return_value = MOCK_CONFIG_INCLUDE_ALL

            # Mock the structure returned by SQL service
            mock_structure = {
                'users': {'columns': [{'name': 'id', 'type': 'INTEGER'}, {'name': 'name', 'type': 'VARCHAR'}]},
                'products': {'columns': [{'name': 'sku', 'type': 'VARCHAR'}, {'name': 'price', 'type': 'DECIMAL'}]}
            }
            self.mock_sql_service.get_database_structure.return_value = mock_structure

            # Act
            result = self.context_service._get_sql_schema_context(self.COMPANY_NAME)

            # Assert
            self.mock_sql_service.get_database_structure.assert_called_once_with(self.COMPANY_NAME, 'main_db')

            # Verify content presence (simple check as exact string matching is brittle)
            assert "'table': 'users'" in result
            assert "'table': 'products'" in result
            assert "sku" in result
            assert "price" in result

        def test_sql_context_with_explicit_table_map(self):
            """
            GIVEN config has an explicit map of tables
            WHEN _get_sql_schema_context is called
            THEN it should only process tables listed in the map.
            """
            # Arrange
            self.mock_config_service.get_configuration.return_value = MOCK_CONFIG_EXPLICIT_LIST

            # DB has more tables than config asks for
            mock_structure = {
                'products': {'columns': [{'name': 'sku', 'type': 'VARCHAR'}]},
                'customers': {'columns': [{'name': 'id', 'type': 'INTEGER'}]},
                'orders': {'columns': [{'name': 'id', 'type': 'INTEGER'}]}  # Should be ignored
            }
            self.mock_sql_service.get_database_structure.return_value = mock_structure

            # Act
            result = self.context_service._get_sql_schema_context(self.COMPANY_NAME)

            # Assert
            assert "'table': 'products'" in result
            assert "'table': 'customers'" in result
            assert "'table': 'orders'" not in result

        def test_sql_context_with_complex_overrides(self):
            """
            GIVEN a complex config with include_all, exclusions, and overrides
            WHEN _get_sql_schema_context is called
            THEN it should apply all rules correctly.
            """
            # Arrange
            self.mock_config_service.get_configuration.return_value = MOCK_CONFIG_COMPLEX

            mock_structure = {
                'users': {'columns': [
                    {'name': 'id', 'type': 'INT'},
                    {'name': 'name', 'type': 'VARCHAR'},
                    {'name': 'password_hash', 'type': 'VARCHAR'}  # Should be excluded locally
                ]},
                'user_profiles': {'columns': [
                    {'name': 'id', 'type': 'INT'},  # Excluded globally
                    {'name': 'created_at', 'type': 'DATE'},  # Excluded globally
                    {'name': 'bio', 'type': 'TEXT'}
                ]},
                'logs': {'columns': [{'name': 'msg', 'type': 'TEXT'}]}  # Excluded via exclude_tables
            }
            self.mock_sql_service.get_database_structure.return_value = mock_structure

            # Act
            result = self.context_service._get_sql_schema_context(self.COMPANY_NAME)

            # Assert
            # 1. 'logs' excluded
            assert "'table': 'logs'" not in result

            # 2. 'users': password_hash excluded, name included
            assert "password_hash" not in result
            assert "name" in result

            # 3. 'user_profiles': id, created_at excluded, bio included
            assert "created_at" not in result
            assert "bio" in result

            # 4. Check schema override for user_profiles
            # The code generates: f"The meaning of each field in this table is detailed in the **`{schema_object_name}`** object."
            # MOCK_CONFIG_COMPLEX sets schema_name: 'profiles' for 'user_profiles'
            assert "**`profiles`** object" in result

        def test_build_context_with_only_static_files(self):
            """
            GIVEN only static markdown files provide context in the repo
            WHEN get_company_context is called
            THEN it should return only the markdown context.
            """
            # Arrange
            # 1. Mock Markdown files
            self.mock_asset_repo.list_files.side_effect = lambda company, asset_type, extension: \
                ['info.md'] if asset_type == AssetType.CONTEXT else []

            self.mock_asset_repo.read_text.return_value = "STATIC_INFO"

            # 2. No SQL config
            self.mock_config_service.get_configuration.return_value = None

            # Act
            full_context = self.context_service.get_company_context(self.COMPANY_NAME)

            # Assert
            assert "STATIC_INFO" in full_context

            # Verify repository calls
            self.mock_asset_repo.list_files.assert_any_call(self.COMPANY_NAME, AssetType.CONTEXT, extension='.md')
            self.mock_asset_repo.read_text.assert_any_call(self.COMPANY_NAME, AssetType.CONTEXT, 'info.md')

            # Verify SQL service was NOT called
            self.mock_sql_service.get_database_structure.assert_not_called()

    def test_build_context_with_yaml_schemas(self):
        """
        GIVEN yaml schema files in the repo
        WHEN get_company_context is called
        THEN it should parse them and include them in context.
        """

        # Arrange
        # 1. Mock YAML files
        def list_files_side_effect(company, asset_type, extension):
            if asset_type == AssetType.SCHEMA: return ['orders.yaml']
            return []

        self.mock_asset_repo.list_files.side_effect = list_files_side_effect

        # 2. Mock Content and Parsing
        self.mock_asset_repo.read_text.return_value = "yaml_content"
        self.mock_utility.load_yaml_from_string.return_value = {"orders": {"description": "Order table"}}
        self.mock_utility.generate_schema_table.return_value = "Parsed Order Schema"

        # 3. No SQL config
        self.mock_config_service.get_configuration.return_value = None

        # Act
        full_context = self.context_service.get_company_context(self.COMPANY_NAME)

        # Assert
        assert "Parsed Order Schema" in full_context

        # Verify flow
        self.mock_asset_repo.read_text.assert_called_with(self.COMPANY_NAME, AssetType.SCHEMA, 'orders.yaml')
        self.mock_utility.load_yaml_from_string.assert_called_with("yaml_content")
        self.mock_utility.generate_schema_table.assert_called_with({"orders": {"description": "Order table"}})

    def test_gracefully_handles_repo_exceptions(self):
        """
        GIVEN the repository raises an exception when listing/reading
        WHEN get_company_context is called
        THEN it should log warnings but continue (return empty strings for those parts).
        """
        # Arrange
        self.mock_asset_repo.list_files.side_effect = Exception("Repo Down")
        self.mock_config_service.get_configuration.return_value = None

        # Act
        full_context = self.context_service.get_company_context(self.COMPANY_NAME)

        # Assert
        assert full_context == ""  # Should result in empty string, not crash

    def test_gracefully_handles_db_manager_exception(self):
        """
        GIVEN retrieving a database structure throws an exception
        WHEN get_company_context is called
        THEN it should log a warning and return context from other sources.
        """
        # Arrange
        self.mock_utility.get_files_by_extension.return_value = []  # No static context
        self.mock_config_service.get_configuration.return_value = {'sql': [{'database': 'down_db'}]}

        # Configure the exception on get_database_structure
        self.mock_sql_service.get_database_structure.side_effect = IAToolkitException(
            IAToolkitException.ErrorType.DATABASE_ERROR, "DB is down"
        )

        # Act
        full_context = self.context_service.get_company_context(self.COMPANY_NAME)

        # Assert
        assert full_context == ""
        self.mock_sql_service.get_database_structure.assert_called_once_with(self.COMPANY_NAME, 'down_db')