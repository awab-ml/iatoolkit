# tests/services/test_tool_service.py

import pytest
from unittest.mock import MagicMock, patch
from iatoolkit.services.tool_service import ToolService
from iatoolkit.repositories.llm_query_repo import LLMQueryRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.models import Company, Tool
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.services.sql_service import SqlService
from iatoolkit.services.excel_service import ExcelService
from iatoolkit.services.mail_service import MailService
from iatoolkit.services.visual_kb_service import VisualKnowledgeBaseService
from iatoolkit.services.visual_tool_service import VisualToolService

class TestToolService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_llm_query_repo = MagicMock(spec=LLMQueryRepo)
        self.mock_sql_service = MagicMock(spec=SqlService)
        self.mock_excel_service = MagicMock(spec=ExcelService)
        self.mock_mail_service = MagicMock(spec=MailService)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)
        self.mock_visual_kb_service = MagicMock(spec=VisualKnowledgeBaseService)
        self.mock_visual_tool_service = MagicMock(spec=VisualToolService)

        self.service = ToolService(
            llm_query_repo=self.mock_llm_query_repo,
            profile_repo=self.mock_profile_repo,
            sql_service=self.mock_sql_service,
            excel_service=self.mock_excel_service,
            mail_service=self.mock_mail_service,
            visual_kb_service=self.mock_visual_kb_service,
            visual_tool_service=self.mock_visual_tool_service
        )

        # Mock del modelo de base de datos (Company Model)
        self.mock_company = MagicMock(spec=Company)
        self.mock_company.id = 1

        # Mock de la instancia de negocio (Company Instance) que tiene .company
        self.company_short_name = 'my_company'
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company


    def test_register_system_tools_success(self):
        """
        GIVEN a call to register_system_tools
        WHEN executed
        THEN it should delete old system tools, create new ones with TYPE_SYSTEM, and commit.
        """
        # Mock the system definitions imported in service
        with patch('iatoolkit.services.tool_service.SYSTEM_TOOLS_DEFINITIONS', [{'function_name': 'sys_1', 'description': 'd', 'parameters': {}}]):
            # Act
            self.service.register_system_tools()

            # Assert
            self.mock_llm_query_repo.delete_system_tools.assert_called_once()
            self.mock_llm_query_repo.create_or_update_tool.assert_called_once()

            # Check args
            created_tool = self.mock_llm_query_repo.create_or_update_tool.call_args[0][0]
            assert created_tool.tool_type == Tool.TYPE_SYSTEM
            assert created_tool.source == Tool.SOURCE_SYSTEM

            self.mock_llm_query_repo.commit.assert_called_once()

    def test_register_system_tools_rollback_on_exception(self):
        """
        GIVEN an exception during registration
        WHEN register_system_tools is executed
        THEN it should rollback and raise IAToolkitException.
        """
        # Arrange
        self.mock_llm_query_repo.delete_system_tools.side_effect = Exception("DB Error")

        # Act & Assert
        with pytest.raises(IAToolkitException) as excinfo:
            self.service.register_system_tools()

        assert excinfo.value.error_type == IAToolkitException.ErrorType.DATABASE_ERROR
        self.mock_llm_query_repo.rollback.assert_called_once()

    def test_sync_company_tools_logic(self):
        """
        GIVEN a company config with tools
        WHEN sync_company_tools is executed
        THEN it should create YAML tools as NATIVE/YAML, delete only removed YAML tools, and ignore USER tools.
        """
        # Arrange
        # DB State:
        # 1. 'yaml_keep': From YAML, still in config (Keep & Update)
        # 2. 'yaml_remove': From YAML, removed from config (Delete)
        # 3. 'user_defined': From GUI (Ignore/Keep)

        tool_yaml_keep = MagicMock(spec=Tool)
        tool_yaml_keep.name = 'yaml_keep'
        tool_yaml_keep.source = Tool.SOURCE_YAML

        tool_yaml_remove = MagicMock(spec=Tool)
        tool_yaml_remove.name = 'yaml_remove'
        tool_yaml_remove.source = Tool.SOURCE_YAML

        tool_user = MagicMock(spec=Tool)
        tool_user.name = 'user_defined'
        tool_user.source = Tool.SOURCE_USER

        self.mock_llm_query_repo.get_company_tools.return_value = [tool_yaml_keep, tool_yaml_remove, tool_user]

        # Config defines: 'yaml_keep' (updated) and 'new_yaml' (created)
        tools_config = [
            {'function_name': 'yaml_keep', 'description': 'Updated', 'params': {}},
            {'function_name': 'new_yaml', 'description': 'New', 'params': {}}
        ]

        # Act
        self.service.sync_company_tools(self.company_short_name, tools_config)

        # Assert

        # 1. Upsert Calls
        assert self.mock_llm_query_repo.create_or_update_tool.call_count == 2
        calls = self.mock_llm_query_repo.create_or_update_tool.call_args_list

        # Check 'yaml_keep' update
        tool_keep = calls[0][0][0]
        assert tool_keep.name == 'yaml_keep'
        assert tool_keep.source == Tool.SOURCE_YAML
        assert tool_keep.tool_type == Tool.TYPE_NATIVE

        # Check 'new_yaml' creation
        tool_new = calls[1][0][0]
        assert tool_new.name == 'new_yaml'
        assert tool_new.source == Tool.SOURCE_YAML
        assert tool_new.tool_type == Tool.TYPE_NATIVE

        # 2. Delete Calls
        # Should only delete 'yaml_remove' because source=YAML and not in config
        self.mock_llm_query_repo.delete_tool.assert_called_once_with(tool_yaml_remove)

        # 'user_defined' should NOT be deleted even though it's not in config
        # Verified implicitly by delete_tool called once.

        self.mock_llm_query_repo.commit.assert_called_once()

    def test_sync_company_tools_rollback_on_exception(self):
        """
        GIVEN an exception during sync
        WHEN sync_company_tools is executed
        THEN it should rollback and raise exception.
        """
        self.mock_llm_query_repo.get_company_tools.side_effect = Exception("Sync Error")

        with pytest.raises(IAToolkitException) as excinfo:
            self.service.sync_company_tools(self.company_short_name, [])

        assert excinfo.value.error_type == IAToolkitException.ErrorType.DATABASE_ERROR
        self.mock_llm_query_repo.rollback.assert_called_once()

    def test_get_tools_for_llm_format(self):
        """
        GIVEN a company with tools
        WHEN get_tools_for_llm is called
        THEN it should return a list of tools formatted for OpenAI.
        """
        # Arrange
        tool1 = MagicMock(spec=Tool)
        tool1.name = 'tool1'
        tool1.description = 'desc1'
        tool1.parameters = {'prop': 1}

        self.mock_llm_query_repo.get_company_tools.return_value = [tool1]

        # Act
        result = self.service.get_tools_for_llm(self.mock_company)

        # Assert
        assert len(result) == 1
        assert result[0]['type'] == 'function'
        assert result[0]['name'] == 'tool1'
        assert result[0]['strict'] is True

    # --- CRUD Tests ---

    def test_create_tool_api(self):
        """Test creating a tool via API logic."""
        # Arrange
        tool_data = {
            "name": "api_tool",
            "description": "desc",
            "tool_type": Tool.TYPE_INFERENCE,
            "execution_config": {"url": "http"}
        }
        # Mock no duplication
        self.mock_llm_query_repo.get_tool_definition.return_value = None

        mock_created = MagicMock(spec=Tool)
        mock_created.to_dict.return_value = tool_data
        self.mock_llm_query_repo.add_tool.return_value = mock_created

        # Act
        result = self.service.create_tool(self.company_short_name, tool_data)

        # Assert
        assert result['name'] == 'api_tool'
        self.mock_llm_query_repo.add_tool.assert_called_once()
        args = self.mock_llm_query_repo.add_tool.call_args[0][0]
        assert args.source == Tool.SOURCE_USER
        assert args.tool_type == Tool.TYPE_INFERENCE

    def test_create_tool_duplicate_error(self):
        """Test creating a duplicate tool throws exception."""
        self.mock_llm_query_repo.get_tool_definition.return_value = MagicMock() # Exists

        with pytest.raises(IAToolkitException) as exc:
            self.service.create_tool(self.company_short_name, {"name": "dup", "description": "d"})

        assert exc.value.error_type == IAToolkitException.ErrorType.DUPLICATE_ENTRY

    def test_update_tool_success(self):
        """Test updating a tool."""
        existing_tool = MagicMock(spec=Tool)
        existing_tool.tool_type = Tool.TYPE_NATIVE
        existing_tool.to_dict.return_value = {}
        self.mock_llm_query_repo.get_tool_by_id.return_value = existing_tool

        update_data = {"description": "new desc"}
        self.service.update_tool(self.company_short_name, 1, update_data)

        assert existing_tool.description == "new desc"
        self.mock_llm_query_repo.commit.assert_called_once()

    def test_update_tool_system_tool_fails(self):
        """Test that system tools cannot be updated."""
        existing_tool = MagicMock(spec=Tool)
        existing_tool.tool_type = Tool.TYPE_SYSTEM # System!
        self.mock_llm_query_repo.get_tool_by_id.return_value = existing_tool

        with pytest.raises(IAToolkitException) as exc:
            self.service.update_tool(self.company_short_name, 1, {})

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_OPERATION

    def test_delete_tool_system_tool_fails(self):
        """Test that system tools cannot be deleted via API."""
        existing_tool = MagicMock(spec=Tool)
        existing_tool.tool_type = Tool.TYPE_SYSTEM
        self.mock_llm_query_repo.get_tool_by_id.return_value = existing_tool

        with pytest.raises(IAToolkitException) as exc:
            self.service.delete_tool(self.company_short_name, 1)

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_OPERATION
    def test_get_tools_for_llm_format(self):
        """
        GIVEN a company with tools
        WHEN get_tools_for_llm is called
        THEN it should return a list of tools formatted for OpenAI (type, function, strict).
        """
        # Arrange
        tool1 = MagicMock(spec=Tool)
        tool1.name = 'tool1'
        tool1.description = 'desc1'
        tool1.parameters = {'prop': 1}

        self.mock_llm_query_repo.get_company_tools.return_value = [tool1]

        # Act
        result = self.service.get_tools_for_llm(self.mock_company)

        # Assert
        assert len(result) == 1
        assert result[0]['type'] == 'function'
        assert result[0]['name'] == 'tool1'
        assert result[0]['description'] == 'desc1'
        assert result[0]['parameters']['prop'] == 1
        assert result[0]['parameters']['additionalProperties'] is False
        assert result[0]['strict'] is True

