# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import pytest
from unittest.mock import MagicMock, patch
from iatoolkit.services.ingestor_service import IngestorService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.models import Company, IngestionSource, IngestionStatus, IngestionSourceType
from iatoolkit.common.exceptions import IAToolkitException

class TestIngestorService:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_file_connector_factory = MagicMock(spec=FileConnectorFactory)
        self.mock_kb_service = MagicMock(spec=KnowledgeBaseService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)
        self.mock_session = MagicMock()
        self.mock_document_repo.session = self.mock_session

        self.service = IngestorService(
            config_service=self.mock_config_service,
            file_connector_factory=self.mock_file_connector_factory,
            knowledge_base_service=self.mock_kb_service,
            document_repo=self.mock_document_repo
        )
        self.company = Company(id=1, short_name='acme')

    # --- Tests for create_source ---

    def test_create_source_success(self):
        # Arrange
        data = {
            'name': 'Test Bucket',
            'collection_name': 'Test Collection',
            'source_type': 's3',
            'configuration': {'bucket': 'b1'}
        }
        expected_source = IngestionSource(id=1, name='Test Bucket')
        self.mock_document_repo.create_or_update_ingestion_source.return_value = expected_source
        self.mock_config_service.get_configuration.return_value = {
            'provider': 's3'
        }
        # Act
        result = self.service.create_source(self.company, data)

        # Assert
        self.mock_document_repo.create_or_update_ingestion_source.assert_called_once()
        arg_source = self.mock_document_repo.create_or_update_ingestion_source.call_args[0][0]
        assert arg_source.name == 'Test Bucket'
        assert arg_source.source_type == IngestionSourceType.S3
        assert result == expected_source

    def test_create_source_missing_params(self):
        with pytest.raises(IAToolkitException) as exc:
            self.service.create_source(self.company, {'name': 'Missing Type'})
        assert exc.value.error_type == IAToolkitException.ErrorType.MISSING_PARAMETER

    def test_create_source_invalid_type(self):
        data = {'name': 'X', 'source_type': 'ftp',
                'collection_name': 'Test Collection','configuration': {}}
        with pytest.raises(IAToolkitException) as exc:
            self.service.create_source(self.company, data)
        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_PARAMETER

    def test_create_source_invalid_collection_name(self):
        data = {'name': 'X', 'source_type': 's3',
                'collection_name': 'Test Collection','configuration': {}}
        self.mock_document_repo.get_collection_type_by_name.return_value = None
        with pytest.raises(IAToolkitException) as exc:
            self.service.create_source(self.company, data)
        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_PARAMETER

    # --- Tests for run_ingestion ---

    def test_run_ingestion_success(self):
        # Arrange
        mock_source = IngestionSource(id=10, status=IngestionStatus.ACTIVE, company_id=1, configuration={'type':'local'})
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = mock_source

        # Mock internal trigger logic via mocking connector factory (since internal logic uses it)
        mock_connector = MagicMock()
        self.mock_file_connector_factory.create.return_value = mock_connector

        with patch('iatoolkit.services.ingestor_service.FileProcessor') as MockProcessor:
            MockProcessor.return_value.processed_files = 3

            # Act
            count = self.service.run_ingestion(self.company, 10)

            # Assert
            assert count == 3
            self.mock_file_connector_factory.create.assert_called()

    def test_run_ingestion_not_found(self):
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = None
        with pytest.raises(IAToolkitException) as exc:
            self.service.run_ingestion(self.company, 99)
        assert exc.value.error_type == IAToolkitException.ErrorType.DOCUMENT_NOT_FOUND

    def test_run_ingestion_already_running(self):
        mock_source = IngestionSource(id=10, status=IngestionStatus.RUNNING, company_id=1)
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = mock_source

        with pytest.raises(IAToolkitException) as exc:
            self.service.run_ingestion(self.company, 10)
        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_STATE

    # --- Tests for Legacy/Sync Logic (Reused from previous) ---

    def test_sync_sources_from_yaml(self):
        # Arrange
        mock_yaml = {
            'document_sources': {'src1': {'path': 'p1'}},
            'connectors': {'development': {'type': 'local'}}
        }
        self.mock_config_service.get_configuration.return_value = mock_yaml
        self.mock_document_repo.get_ingestion_source_by_name.return_value = None # Create new

        # Act
        with patch.dict('os.environ', {'FLASK_ENV': 'dev'}):
            self.service.sync_sources_from_yaml(self.company)

        # Assert
        self.mock_document_repo.create_or_update_ingestion_source.assert_called_once()