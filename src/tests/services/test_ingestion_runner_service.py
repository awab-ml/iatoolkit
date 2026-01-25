# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import pytest
from unittest.mock import MagicMock, patch

from iatoolkit.services.ingestion_runner_service import IngestionRunnerService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.repositories.models import Company, IngestionSource, IngestionStatus
from iatoolkit.common.exceptions import IAToolkitException


class TestIngestionRunnerService:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.mock_file_connector_factory = MagicMock(spec=FileConnectorFactory)
        self.mock_kb_service = MagicMock(spec=KnowledgeBaseService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)
        self.mock_config_service = MagicMock(spec=ConfigurationService)

        self.service = IngestionRunnerService(
            file_connector_factory=self.mock_file_connector_factory,
            knowledge_base_service=self.mock_kb_service,
            document_repo=self.mock_document_repo,
            config_service=self.mock_config_service,
        )
        self.company = Company(id=1, short_name="acme")

    def test_run_ingestion_not_found(self):
        self.mock_document_repo.get_ingestion_source_by_id.return_value = None

        with pytest.raises(IAToolkitException) as exc:
            self.service.run_ingestion(self.company, 99, user_identifier="u1")

        assert exc.value.error_type == IAToolkitException.ErrorType.DOCUMENT_NOT_FOUND
        self.mock_document_repo.create_ingestion_run.assert_not_called()

    def test_run_ingestion_already_running(self):
        source = IngestionSource(id=1, company_id=1, status=IngestionStatus.RUNNING, connector_name="c1")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        with pytest.raises(IAToolkitException) as exc:
            self.service.run_ingestion(self.company, 1, user_identifier="u1")

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_STATE
        self.mock_document_repo.create_ingestion_run.assert_not_called()

    @patch("iatoolkit.services.ingestion_runner_service.FileProcessor")
    def test_run_ingestion_success_creates_and_updates_run(self, MockProcessor):
        # Arrange
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="iatoolkit_storage",
            configuration={"root": "p", "metadata": {"x": 1}},
        )
        source.company = self.company
        source.collection_type = None

        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        self.mock_config_service.get_configuration.return_value = {
            "iatoolkit_storage": {"type": "local", "path": "/tmp"}
        }

        MockProcessor.return_value.processed_files = 3
        self.mock_file_connector_factory.create.return_value = MagicMock()

        created_run_snapshot = {}

        def capture_run_at_create(run_obj):
            created_run_snapshot["company_id"] = run_obj.company_id
            created_run_snapshot["source_id"] = run_obj.source_id
            created_run_snapshot["triggered_by"] = run_obj.triggered_by
            created_run_snapshot["status"] = run_obj.status
            return run_obj

        self.mock_document_repo.create_ingestion_run.side_effect = capture_run_at_create

        # Act
        count = self.service.run_ingestion(self.company, 1, user_identifier="u1")

        # Assert
        assert count == 3

        self.mock_document_repo.create_ingestion_run.assert_called_once()
        self.mock_document_repo.update_ingestion_run.assert_called_once()

        assert created_run_snapshot["company_id"] == 1
        assert created_run_snapshot["source_id"] == 1
        assert created_run_snapshot["triggered_by"] == "u1"
        assert created_run_snapshot["status"] == IngestionStatus.RUNNING

        updated_run = self.mock_document_repo.update_ingestion_run.call_args[0][0]
        assert updated_run.status == IngestionStatus.ACTIVE
        assert updated_run.processed_files == 3
        assert updated_run.finished_at is not None

        called_config = self.mock_file_connector_factory.create.call_args[0][0]
        assert called_config["type"] == "local"
        assert called_config["path"] == "p"

    @patch("iatoolkit.services.ingestion_runner_service.FileProcessor")
    def test_run_ingestion_failure_updates_run_as_error(self, MockProcessor):
        # Arrange
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="iatoolkit_storage",
            configuration={"root": "p"},
        )
        source.company = self.company
        source.collection_type = None

        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        self.mock_config_service.get_configuration.return_value = {
            "iatoolkit_storage": {"type": "local", "path": "/tmp"}
        }

        MockProcessor.return_value.process_files.side_effect = Exception("boom")
        MockProcessor.return_value.processed_files = 0
        self.mock_file_connector_factory.create.return_value = MagicMock()

        with pytest.raises(Exception) as exc:
            self.service.run_ingestion(self.company, 1, user_identifier="u1")

        assert "boom" in str(exc.value)

        self.mock_document_repo.create_ingestion_run.assert_called_once()
        self.mock_document_repo.update_ingestion_run.assert_called_once()

        updated_run = self.mock_document_repo.update_ingestion_run.call_args[0][0]
        assert updated_run.status == IngestionStatus.ERROR
        assert updated_run.error_message is not None
        assert updated_run.finished_at is not None

    @patch("iatoolkit.services.ingestion_runner_service.FileProcessor")
    def test_trigger_ingestion_logic_sets_source_status_and_persists(self, MockProcessor):
        # Arrange
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="iatoolkit_storage",
            configuration={"root": "p", "metadata": {"a": 1}},
        )
        source.company = self.company
        source.collection_type = None

        self.mock_config_service.get_configuration.return_value = {
            "iatoolkit_storage": {"type": "local", "path": "/tmp"}
        }

        self.mock_file_connector_factory.create.return_value = MagicMock()
        MockProcessor.return_value.processed_files = 2

        processed = self.service._trigger_ingestion_logic(source, filters={"ext": "pdf"})

        assert processed == 2
        assert self.mock_document_repo.create_or_update_ingestion_source.call_count >= 2
        self.mock_file_connector_factory.create.assert_called_once()

    def test_trigger_ingestion_missing_connector_name_raises(self):
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name=None,
            configuration={"root": "p"},
        )
        source.company = self.company
        source.collection_type = None

        with pytest.raises(IAToolkitException) as exc:
            self.service._trigger_ingestion_logic(source)

        assert exc.value.error_type == IAToolkitException.ErrorType.CONFIG_ERROR

    def test_trigger_ingestion_missing_root_raises(self):
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="iatoolkit_storage",
            configuration={},
        )
        source.company = self.company
        source.collection_type = None

        with pytest.raises(IAToolkitException) as exc:
            self.service._trigger_ingestion_logic(source)

        assert exc.value.error_type == IAToolkitException.ErrorType.CONFIG_ERROR

    def test_trigger_ingestion_missing_connector_alias_raises(self):
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="missing",
            configuration={"root": "p"},
        )
        source.company = self.company
        source.collection_type = None

        self.mock_config_service.get_configuration.return_value = {
            "iatoolkit_storage": {"type": "local", "path": "/tmp"}
        }

        with pytest.raises(IAToolkitException) as exc:
            self.service._trigger_ingestion_logic(source)

        assert exc.value.error_type == IAToolkitException.ErrorType.CONFIG_ERROR

    @patch("iatoolkit.services.ingestion_runner_service.FileProcessor")
    def test_run_ingestion_failure_sets_source_status_error(self, MockProcessor):
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="iatoolkit_storage",
            configuration={"root": "p"},
        )
        source.company = self.company
        source.collection_type = None

        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        self.mock_config_service.get_configuration.return_value = {
            "iatoolkit_storage": {"type": "local", "path": "/tmp"}
        }

        MockProcessor.return_value.process_files.side_effect = Exception("boom")
        MockProcessor.return_value.processed_files = 0
        self.mock_file_connector_factory.create.return_value = MagicMock()

        with pytest.raises(Exception):
            self.service.run_ingestion(self.company, 1, user_identifier="u1")

        last_saved_source = self.mock_document_repo.create_or_update_ingestion_source.call_args_list[-1][0][0]
        assert last_saved_source.status == IngestionStatus.ERROR
        assert last_saved_source.last_error is not None