# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import pytest
from unittest.mock import MagicMock

from iatoolkit.services.ingestion_source_service import IngestionSourceService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.models import Company, IngestionSource, IngestionStatus
from iatoolkit.common.exceptions import IAToolkitException


class TestIngestionSourceService:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)

        self.service = IngestionSourceService(
            config_service=self.mock_config_service,
            document_repo=self.mock_document_repo
        )
        self.company = Company(id=1, short_name="acme")

    def test_get_source_not_found(self):
        self.mock_document_repo.get_ingestion_source_by_id.return_value = None

        with pytest.raises(IAToolkitException) as exc:
            self.service.get_source(self.company, 99)

        assert exc.value.error_type == IAToolkitException.ErrorType.DOCUMENT_NOT_FOUND

    def test_update_source_rejects_running(self):
        source = IngestionSource(id=1, company_id=1, status=IngestionStatus.RUNNING, connector_name="iatoolkit_storage")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        with pytest.raises(IAToolkitException) as exc:
            self.service.update_source(self.company, 1, {"name": "X"})

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_STATE

    def test_update_source_invalid_status(self):
        source = IngestionSource(id=1, company_id=1, status=IngestionStatus.ACTIVE, connector_name="iatoolkit_storage")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        with pytest.raises(IAToolkitException) as exc:
            self.service.update_source(self.company, 1, {"status": "nope"})

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_PARAMETER

    def test_update_source_invalid_collection_name(self):
        source = IngestionSource(id=1, company_id=1, status=IngestionStatus.ACTIVE, connector_name="iatoolkit_storage")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source
        self.mock_document_repo.get_collection_type_by_name.return_value = None

        with pytest.raises(IAToolkitException) as exc:
            self.service.update_source(self.company, 1, {"collection_name": "missing"})

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_PARAMETER

    def test_update_source_configuration_must_be_object(self):
        source = IngestionSource(id=1, company_id=1, status=IngestionStatus.ACTIVE, connector_name="iatoolkit_storage")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        with pytest.raises(IAToolkitException) as exc:
            self.service.update_source(self.company, 1, {"configuration": "bad"})

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_PARAMETER

    def test_delete_source_rejects_running(self):
        source = IngestionSource(id=1, company_id=1, status=IngestionStatus.RUNNING, connector_name="iatoolkit_storage")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        with pytest.raises(IAToolkitException) as exc:
            self.service.delete_source(self.company, 1)

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_STATE

    def test_create_source_success(self):
        # Arrange
        data = {
            "name": "S1",
            "collection_name": "C1",
            "connector_name": "iatoolkit_storage",
            "configuration": {"root": "p1/folder1", "metadata": {"a": 1}},
        }

        collection_type = MagicMock()
        collection_type.id = 7
        self.mock_document_repo.get_collection_type_by_name.return_value = collection_type

        expected_source = IngestionSource(id=123, name="S1", connector_name="iatoolkit_storage")
        self.mock_document_repo.create_or_update_ingestion_source.return_value = expected_source

        # Act
        result = self.service.create_source(self.company, data)

        # Assert
        assert result == expected_source
        self.mock_document_repo.create_or_update_ingestion_source.assert_called_once()
        created = self.mock_document_repo.create_or_update_ingestion_source.call_args[0][0]

        assert created.company_id == self.company.id
        assert created.collection_type_id == 7
        assert created.name == "S1"
        assert created.connector_name == "iatoolkit_storage"
        assert created.configuration["root"] == "p1/folder1"
        assert created.configuration["collection"] == "C1"
        assert created.configuration["metadata"] == {"a": 1}

    def test_create_source_missing_required_fields(self):
        with pytest.raises(IAToolkitException) as exc:
            self.service.create_source(self.company, {"name": "S1"})

        assert exc.value.error_type == IAToolkitException.ErrorType.MISSING_PARAMETER

    def test_create_source_configuration_must_be_object(self):
        data = {
            "name": "S1",
            "collection_name": "C1",
            "connector_name": "iatoolkit_storage",
            "configuration": "bad"
        }
        self.mock_document_repo.get_collection_type_by_name.return_value = MagicMock(id=7)

        with pytest.raises(IAToolkitException) as exc:
            self.service.create_source(self.company, data)

        assert exc.value.error_type == IAToolkitException.ErrorType.INVALID_PARAMETER

    def test_list_sources_happy_path(self):
        sources = [
            IngestionSource(id=1, company_id=1, name="S1", connector_name="c1"),
            IngestionSource(id=2, company_id=1, name="S2", connector_name="c2"),
        ]

        self.mock_document_repo.list_ingestion_sources.return_value = sources

        result = self.service.list_sources(self.company)

        assert result == sources
        self.mock_document_repo.list_ingestion_sources.assert_called_once_with(self.company.id)

    def test_get_source_happy_path(self):
        src = IngestionSource(id=10, company_id=1, name="S1", connector_name="c1")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = src

        result = self.service.get_source(self.company, 10)

        assert result == src
        self.mock_document_repo.get_ingestion_source_by_id.assert_called_once_with(self.company.id, 10)

    def test_delete_source_happy_path(self):
        src = IngestionSource(id=10, company_id=1, status=IngestionStatus.ACTIVE, connector_name="c1")
        self.mock_document_repo.get_ingestion_source_by_id.return_value = src

        self.service.delete_source(self.company, 10)

        self.mock_document_repo.delete_ingestion_source.assert_called_once_with(src)

    def test_update_source_updates_collection_name_also_updates_configuration_collection(self):
        source = IngestionSource(
            id=1,
            company_id=1,
            status=IngestionStatus.ACTIVE,
            connector_name="iatoolkit_storage",
            configuration={"root": "p", "collection": "Old"},
        )
        self.mock_document_repo.get_ingestion_source_by_id.return_value = source

        collection_type = MagicMock()
        collection_type.id = 99
        self.mock_document_repo.get_collection_type_by_name.return_value = collection_type

        def return_same_source(src: IngestionSource) -> IngestionSource:
            return src

        self.mock_document_repo.create_or_update_ingestion_source.side_effect = return_same_source

        updated = self.service.update_source(self.company, 1, {"collection_name": "New"})

        assert updated.configuration["collection"] == "New"
        assert updated.collection_type_id == 99