# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from unittest.mock import MagicMock
from iatoolkit.repositories.models import Document, Company, IngestionSource
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.common.exceptions import IAToolkitException
import base64
from typing import List, Optional


class TestDocumentRepo:
    def setup_method(self):
        # Mock the DatabaseManager
        self.mock_db_manager = MagicMock()
        self.session = self.mock_db_manager.get_session()

        # Initialize DocumentRepo with the mocked DatabaseManager
        self.repo = DocumentRepo(self.mock_db_manager)
        self.mock_document = Document(company_id=1,
                                 filename='test.txt',
                                 content='123',
                                 storage_key='iatoolkit/document-key',
                                 meta={'repertorio_id': 10})
        self.mock_company = Company(name='company')


    def test_insert_when_ok(self):
        self.repo.insert(self.mock_document)

        # Assert
        self.session.add.assert_called()
        self.session.commit.assert_called()

    def test_get_missing_company(self):
        # Act & Assert
        with pytest.raises(IAToolkitException) as exc_info:
            self.repo.get(None, filename="test_file.txt")

        assert exc_info.value.error_type == IAToolkitException.ErrorType.PARAM_NOT_FILLED

    def test_get_document_by_filename(self):
        self.session.query.return_value.filter_by.return_value.first.return_value = self.mock_document

        # Act
        result = self.repo.get(self.mock_company, filename="test_file.txt")

        # Assert
        assert result == self.mock_document
        self.session.query.assert_called()

    def test_get_by_id_when_id_is_none(self):
        result = self.repo.get_by_id(0)

        assert result is None
        self.session.query.assert_not_called()

    def test_get_by_id_when_document_not_found(self):
        self.session.query.return_value.filter_by.return_value.first.return_value = None

        result = self.repo.get_by_id(999)

        assert result is None
        self.session.query.assert_called()

    def test_get_by_id_when_document_exists(self):
        self.session.query.return_value.filter_by.return_value.first.return_value = self.mock_document

        result = self.repo.get_by_id(1)

        assert result == self.mock_document
        self.session.query.assert_called()

    # --- New Ingestion Source Tests ---

    def test_get_ingestion_source_by_name(self):
        # Arrange
        mock_source = IngestionSource(id=10, name="src1", company_id=1)
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_source

        # Act
        result = self.repo.get_ingestion_source_by_name(1, "src1")

        # Assert
        assert result == mock_source
        self.session.query.assert_called_with(IngestionSource)

    def test_create_or_update_ingestion_source_create(self):
        # Arrange
        new_source = IngestionSource(name="new_src", company_id=1)
        # Act
        self.repo.create_or_update_ingestion_source(new_source)
        # Assert
        self.session.add.assert_called_with(new_source)
        self.session.commit.assert_called()

    def test_create_or_update_ingestion_source_update(self):
        # Arrange
        existing_source = IngestionSource(id=5, name="updated_src")
        # Act
        self.repo.create_or_update_ingestion_source(existing_source)
        # Assert
        self.session.merge.assert_called_with(existing_source)
        self.session.commit.assert_called()

    def test_get_active_ingestion_sources(self):
        # Arrange
        mock_list = [IngestionSource(name="src1"), IngestionSource(name="src2")]

        # Mock chained query: query().filter().all()
        mock_query = self.session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_list

        # Act
        result = self.repo.get_active_ingestion_sources(1, ["src1", "src2"])

        # Assert
        assert len(result) == 2
        # Verify filter call
        # Hard to assert complex filter arguments on mocks, but we check query flow
        mock_query.filter.assert_called()
        mock_query.all.assert_called()


