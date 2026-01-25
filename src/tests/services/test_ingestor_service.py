# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import pytest
from unittest.mock import MagicMock, patch

from iatoolkit.services.ingestor_service import IngestorService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.models import Company, IngestionSource
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.services.ingestion_source_service import IngestionSourceService
from iatoolkit.services.ingestion_runner_service import IngestionRunnerService


class TestIngestorService:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_file_connector_factory = MagicMock(spec=FileConnectorFactory)
        self.mock_kb_service = MagicMock(spec=KnowledgeBaseService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)

        self.mock_ingestion_source_service = MagicMock(spec=IngestionSourceService)
        self.mock_ingestion_runner_service = MagicMock(spec=IngestionRunnerService)

        self.service = IngestorService(
            config_service=self.mock_config_service,
            file_connector_factory=self.mock_file_connector_factory,
            knowledge_base_service=self.mock_kb_service,
            document_repo=self.mock_document_repo,
            ingestion_source_service=self.mock_ingestion_source_service,
            ingestion_runner_service=self.mock_ingestion_runner_service
        )
        self.company = Company(id=1, short_name='acme')

    def test_create_source_delegates_to_ingestion_source_service(self):
        payload = {"name": "S1", "source_type": "s3", "configuration": {}, "collection_name": "C1"}
        expected = IngestionSource(id=1, name="S1")
        self.mock_ingestion_source_service.create_source.return_value = expected

        result = self.service.create_source(self.company, payload)

        assert result == expected
        self.mock_ingestion_source_service.create_source.assert_called_once_with(self.company, payload)

    def test_run_ingestion_delegates_to_ingestion_runner_service(self):
        self.mock_ingestion_runner_service.run_ingestion.return_value = 3

        count = self.service.run_ingestion(self.company, 10, user_identifier="u1")

        assert count == 3
        self.mock_ingestion_runner_service.run_ingestion.assert_called_once_with(
            self.company, 10, user_identifier="u1"
        )

    def test_run_ingestion_propagates_exceptions(self):
        self.mock_ingestion_runner_service.run_ingestion.side_effect = IAToolkitException(
            IAToolkitException.ErrorType.INVALID_STATE, "Already running"
        )

        with pytest.raises(IAToolkitException) as exc:
            self.service.run_ingestion(self.company, 10)

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_STATE

    def test_update_source_delegates(self):
        expected = IngestionSource(id=1, name="New")
        self.mock_ingestion_source_service.update_source.return_value = expected

        result = self.service.update_source(self.company, 1, {"name": "New"})

        assert result == expected
        self.mock_ingestion_source_service.update_source.assert_called_once_with(self.company, 1, {"name": "New"})

    def test_delete_source_delegates(self):
        self.service.delete_source(self.company, 1)
        self.mock_ingestion_source_service.delete_source.assert_called_once_with(self.company, 1)

    def test_load_sources_uses_runner_trigger_logic(self):
        # Arrange
        with patch('iatoolkit.services.ingestor_service.current_iatoolkit') as mock_current:
            mock_current.return_value.is_community = True

            self.service.sync_sources_from_yaml = MagicMock()

            src1 = IngestionSource(id=1, name="src1")
            src2 = IngestionSource(id=2, name="src2")
            self.mock_document_repo.get_active_ingestion_sources.return_value = [src1, src2]

            self.mock_ingestion_runner_service._trigger_ingestion_logic.side_effect = [2, 3]

            # Act
            total = self.service.load_sources(self.company, sources_to_load=["src1", "src2"], filters={"ext": "pdf"})

            # Assert
            assert total == 5
            self.service.sync_sources_from_yaml.assert_called_once_with(self.company)
            self.mock_document_repo.get_active_ingestion_sources.assert_called_once_with(self.company.id, ["src1", "src2"])
            assert self.mock_ingestion_runner_service._trigger_ingestion_logic.call_count == 2
            self.mock_ingestion_runner_service._trigger_ingestion_logic.assert_any_call(src1, filters={"ext": "pdf"})
            self.mock_ingestion_runner_service._trigger_ingestion_logic.assert_any_call(src2, filters={"ext": "pdf"})

    def test_load_sources_missing_sources_to_load_raises(self):
        with patch('iatoolkit.services.ingestor_service.current_iatoolkit') as mock_current:
            mock_current.return_value.is_community = True

            with pytest.raises(IAToolkitException) as exc:
                self.service.load_sources(self.company, sources_to_load=None)

            assert exc.value.error_type == IAToolkitException.ErrorType.PARAM_NOT_FILLED