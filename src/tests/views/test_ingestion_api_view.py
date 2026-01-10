# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import pytest
import json
from unittest.mock import MagicMock
from flask import Flask
from iatoolkit.views.ingestion_api_view import IngestionApiView
from iatoolkit.services.auth_service import AuthService
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.services.ingestor_service import IngestorService
from iatoolkit.repositories.models import Company, IngestionSource, IngestionSourceType
from iatoolkit.common.exceptions import IAToolkitException

class TestIngestionApiView:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.app = Flask(__name__)

        self.mock_auth_service = MagicMock(spec=AuthService)
        self.mock_document_repo = MagicMock(spec=DocumentRepo)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)
        self.mock_ingestor_service = MagicMock(spec=IngestorService)
        self.mock_session = MagicMock()
        self.mock_document_repo.session = self.mock_session

        self.view = IngestionApiView.as_view(
            'ingestion_api',
            auth_service=self.mock_auth_service,
            document_repo=self.mock_document_repo,
            profile_repo=self.mock_profile_repo,
            ingestor_service=self.mock_ingestor_service
        )

        self.app.add_url_rule('/<company_short_name>/api/ingestion-sources',
                              view_func=self.view, methods=['GET', 'POST'])
        self.app.add_url_rule('/<company_short_name>/api/ingestion-sources/<int:source_id>/<action>',
                              view_func=self.view, methods=['POST'])

        self.client = self.app.test_client()
        self.company = Company(id=1, short_name="test_co")
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company
        self.mock_auth_service.verify.return_value = {"success": True}

    def test_post_trigger_run_delegates_to_service(self):
        # Arrange
        self.mock_ingestor_service.run_ingestion.return_value = 10

        # Act
        response = self.client.post(f'/{self.company.short_name}/api/ingestion-sources/1/run')

        # Assert
        assert response.status_code == 200
        assert response.get_json()['processed_files'] == 10
        self.mock_ingestor_service.run_ingestion.assert_called_once_with(self.company, 1)

    def test_post_trigger_run_handles_conflict(self):
        # Arrange
        self.mock_ingestor_service.run_ingestion.side_effect = IAToolkitException(
            IAToolkitException.ErrorType.INVALID_STATE, "Already running"
        )

        # Act
        response = self.client.post(f'/{self.company.short_name}/api/ingestion-sources/1/run')

        # Assert
        assert response.status_code == 409
        assert "Already running" in response.get_json()['error']

    def test_post_create_source_delegates_to_service(self):
        # Arrange
        payload = {"name": "S1", "source_type": "s3", "configuration": {}}
        mock_created = IngestionSource(id=1, name="S1", source_type=IngestionSourceType.S3)
        self.mock_ingestor_service.create_source.return_value = mock_created

        # Act
        response = self.client.post(
            f'/{self.company.short_name}/api/ingestion-sources',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 201
        self.mock_ingestor_service.create_source.assert_called_once_with(self.company, payload)

    def test_post_create_source_invalid_params(self):
        # Arrange
        self.mock_ingestor_service.create_source.side_effect = IAToolkitException(
            IAToolkitException.ErrorType.MISSING_PARAMETER, "Missing field"
        )

        # Act
        response = self.client.post(
            f'/{self.company.short_name}/api/ingestion-sources',
            data=json.dumps({}),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 400