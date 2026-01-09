# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
import json
from unittest.mock import MagicMock
from flask import Flask
from iatoolkit.views.ingestion_api_view import IngestionApiView
from iatoolkit.services.auth_service import AuthService
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.services.load_documents_service import LoadDocumentsService
from iatoolkit.repositories.models import Company, IngestionSource, IngestionStatus, IngestionSourceType

class TestIngestionApiView:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.app = Flask(__name__)

        # Mocks
        self.mock_auth_service = MagicMock(spec=AuthService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)
        self.mock_load_documents_service = MagicMock(spec=LoadDocumentsService)

        # Mock Session for DocumentRepo
        self.mock_session = MagicMock()
        self.mock_document_repo.session = self.mock_session

        # Instantiate View
        self.view = IngestionApiView.as_view(
            'ingestion_api',
            auth_service=self.mock_auth_service,
            document_repo=self.mock_document_repo,
            profile_repo=self.mock_profile_repo,
            load_documents_service=self.mock_load_documents_service
        )

        # Register Routes
        self.app.add_url_rule('/<company_short_name>/api/ingestion-sources',
                              view_func=self.view, methods=['GET', 'POST'])
        self.app.add_url_rule('/<company_short_name>/api/ingestion-sources/<int:source_id>/<action>',
                              view_func=self.view, methods=['POST'])

        self.client = self.app.test_client()
        self.company_short_name = "test_co"
        self.mock_company = Company(id=1, short_name=self.company_short_name)

        # Default Auth Success
        self.mock_auth_service.verify.return_value = {"success": True}

    def test_get_sources_success(self):
        # Arrange
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company

        source1 = IngestionSource(id=1, name="S1", source_type=IngestionSourceType.LOCAL, company_id=1)
        source2 = IngestionSource(id=2, name="S2", source_type=IngestionSourceType.S3, company_id=1)

        self.mock_session.query.return_value.filter_by.return_value.all.return_value = [source1, source2]

        # Act
        response = self.client.get(f'/{self.company_short_name}/api/ingestion-sources')

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
        assert data[0]['name'] == "S1"
        assert data[1]['source_type'] == "s3"

    def test_get_sources_unauthorized(self):
        # Arrange
        self.mock_auth_service.verify.return_value = {"success": False, "status_code": 401}

        # Act
        response = self.client.get(f'/{self.company_short_name}/api/ingestion-sources')

        # Assert
        assert response.status_code == 401

    def test_trigger_run_success(self):
        # Arrange
        source_id = 10
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company

        mock_source = IngestionSource(id=source_id, company_id=1, status=IngestionStatus.ACTIVE)
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = mock_source

        self.mock_load_documents_service.trigger_ingestion.return_value = 5 # 5 files processed

        # Act
        response = self.client.post(f'/{self.company_short_name}/api/ingestion-sources/{source_id}/run')

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data['processed_files'] == 5
        self.mock_load_documents_service.trigger_ingestion.assert_called_once_with(mock_source)

    def test_trigger_run_already_running(self):
        # Arrange
        source_id = 10
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company

        mock_source = IngestionSource(id=source_id, company_id=1, status=IngestionStatus.RUNNING)
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = mock_source

        # Act
        response = self.client.post(f'/{self.company_short_name}/api/ingestion-sources/{source_id}/run')

        # Assert
        assert response.status_code == 409
        self.mock_load_documents_service.trigger_ingestion.assert_not_called()

    def test_create_source_success(self):
        # Arrange
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company

        payload = {
            "name": "New Source",
            "source_type": "s3",
            "configuration": {"bucket": "b1"},
            "schedule_cron": "0 0 * * *"
        }

        # Act
        response = self.client.post(
            f'/{self.company_short_name}/api/ingestion-sources',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 201
        self.mock_document_repo.create_or_update_ingestion_source.assert_called_once()

        saved_source = self.mock_document_repo.create_or_update_ingestion_source.call_args[0][0]
        assert saved_source.name == "New Source"
        assert saved_source.source_type == IngestionSourceType.S3
        assert saved_source.company_id == 1

    def test_create_source_invalid_type(self):
        # Arrange
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company

        payload = {
            "name": "Bad Source",
            "source_type": "ftp", # Invalid
            "configuration": {}
        }

        # Act
        response = self.client.post(
            f'/{self.company_short_name}/api/ingestion-sources',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 400
        assert "Invalid source type" in response.get_json()['error']