# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import pytest
from unittest.mock import MagicMock, patch
from iatoolkit.services.load_documents_service import LoadDocumentsService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.models import Company, IngestionSource, IngestionStatus
from iatoolkit.common.exceptions import IAToolkitException

class TestLoadDocumentsService:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up mocks for all dependencies and instantiate the service."""
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_file_connector_factory = MagicMock(spec=FileConnectorFactory)
        self.mock_kb_service = MagicMock(spec=KnowledgeBaseService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)

        self.service = LoadDocumentsService(
            config_service=self.mock_config_service,
            file_connector_factory=self.mock_file_connector_factory,
            knowledge_base_service=self.mock_kb_service,
            document_repo=self.mock_document_repo
        )
        self.company = Company(id=1, short_name='acme')

    def test_sync_sources_from_yaml_creates_records(self):
        # Arrange
        mock_yaml = {
            'document_sources': {
                'contracts': {'path': 'contracts/', 'collection': 'Legal'}
            },
            'connectors': {'development': {'type': 'local', 'path': '/tmp'}}
        }
        self.mock_config_service.get_configuration.return_value = mock_yaml

        # Mock finding NO existing source
        self.mock_document_repo.get_ingestion_source_by_name.return_value = None

        # Act
        with patch.dict('os.environ', {'FLASK_ENV': 'dev'}):
            self.service.sync_sources_from_yaml(self.company)

        # Assert
        # Check that Repo create/update was called
        self.mock_document_repo.create_or_update_ingestion_source.assert_called_once()
        saved_source = self.mock_document_repo.create_or_update_ingestion_source.call_args[0][0]

        assert isinstance(saved_source, IngestionSource)
        assert saved_source.name == 'contracts'
        assert saved_source.configuration['path'] == 'contracts/'
        assert saved_source.company_id == 1

    def test_trigger_ingestion_success(self):
        # Arrange
        mock_source = IngestionSource(
            id=10,
            name="test_source",
            company=self.company,
            configuration={'type': 'local', 'path': 'data/'},
            status=IngestionStatus.ACTIVE
        )

        mock_connector = MagicMock()
        self.mock_file_connector_factory.create.return_value = mock_connector

        # Mock FileProcessor
        with patch('iatoolkit.services.load_documents_service.FileProcessor') as MockProcessor:
            mock_processor_instance = MockProcessor.return_value
            mock_processor_instance.processed_files = 5

            # Act
            processed = self.service.trigger_ingestion(mock_source)

            # Assert
            # 1. Check connector creation
            self.mock_file_connector_factory.create.assert_called_with(mock_source.configuration)

            # 2. Check processor run
            mock_processor_instance.process_files.assert_called_once()

            # 3. Check status update via Repo
            # Expected calls: 1 for RUNNING, 1 for ACTIVE (success)
            assert self.mock_document_repo.create_or_update_ingestion_source.call_count == 2

            assert processed == 5
            assert mock_source.status == IngestionStatus.ACTIVE

    def test_trigger_ingestion_handles_error(self):
        # Arrange
        mock_source = IngestionSource(name="error_source", company=self.company, configuration={})
        self.mock_file_connector_factory.create.side_effect = Exception("Fail")

        # Act & Assert
        with pytest.raises(Exception):
            self.service.trigger_ingestion(mock_source)

        # Check error status saved via Repo
        assert mock_source.status == IngestionStatus.ERROR
        assert "Fail" in mock_source.last_error
        assert self.mock_document_repo.create_or_update_ingestion_source.call_count >= 1

    def test_load_sources_orchestration(self):
        """Test load_sources orchestrates sync and retrieval via Repo."""
        # Arrange
        self.mock_config_service.get_configuration.return_value = {}

        # Mock Repo returning 1 active source
        mock_source = IngestionSource(name="manuals")
        self.mock_document_repo.get_active_ingestion_sources.return_value = [mock_source]

        # Internal mocks
        with patch.object(self.service, 'trigger_ingestion', return_value=10) as mock_trigger:
            with patch.object(self.service, 'sync_sources_from_yaml') as mock_sync:

                # Act
                total = self.service.load_sources(self.company, sources_to_load=["manuals"])

                # Assert
                mock_sync.assert_called_once_with(self.company)
                self.mock_document_repo.get_active_ingestion_sources.assert_called_with(1, ["manuals"])
                mock_trigger.assert_called_once_with(mock_source, None)
                assert total == 10

    def test_callback_delegates_correctly(self):
        # Arrange
        filename = "doc.pdf"
        content = b"data"
        context = {'collection': 'HR', 'metadata': {'tag': 'confidential'}}

        # Act
        self.service._file_processing_callback(self.company, filename, content, context)

        # Assert
        self.mock_kb_service.ingest_document_sync.assert_called_once_with(
            company=self.company,
            filename=filename,
            content=content,
            collection='HR',
            metadata={'tag': 'confidential'}
        )