# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask import request, jsonify
from flask.views import MethodView
from injector import inject
from iatoolkit.services.auth_service import AuthService
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.services.load_documents_service import LoadDocumentsService
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.repositories.models import IngestionSource, IngestionSourceType, IngestionStatus
import logging

class IngestionApiView(MethodView):
    """
    API for managing and triggering document ingestion sources.
    """

    @inject
    def __init__(self,
                 auth_service: AuthService,
                 document_repo: DocumentRepo,
                 profile_repo: ProfileRepo,
                 load_documents_service: LoadDocumentsService):
        self.auth_service = auth_service
        self.document_repo = document_repo
        self.profile_repo = profile_repo
        self.load_documents_service = load_documents_service

    def get(self, company_short_name: str):
        """
        GET /api/{company}/ingestion-sources
        Lists all configured ingestion sources for the company.
        """
        auth_result = self.auth_service.verify(roles=['admin'])
        if not auth_result.get("success"):
            return jsonify(auth_result), auth_result.get("status_code", 401)

        company = self.profile_repo.get_company_by_short_name(company_short_name)
        if not company:
            return jsonify({"error": "Company not found"}), 404

        sources = self.document_repo.session.query(IngestionSource).filter_by(company_id=company.id).all()

        response_data = []
        for src in sources:
            source_dict = src.to_dict()
            # Enriquecer con nombre de colección si existe
            if src.collection_type:
                source_dict['collection_name'] = src.collection_type.name
            response_data.append(source_dict)

        return jsonify(response_data), 200

    def post(self, company_short_name: str, source_id: int = None, action: str = None):
        """
        POST /api/{company}/ingestion-sources (Create)
        POST /api/{company}/ingestion-sources/{id}/run (Trigger)
        """
        auth_result = self.auth_service.verify(roles=['admin'])
        if not auth_result.get("success"):
            return jsonify(auth_result), auth_result.get("status_code", 401)

        company = self.profile_repo.get_company_by_short_name(company_short_name)
        if not company:
            return jsonify({"error": "Company not found"}), 404

        # Case 1: Trigger Run
        if source_id and action == 'run':
            return self._trigger_run(company, source_id)

        # Case 2: Create New Source
        if not source_id and not action:
            return self._create_source(company)

        return jsonify({"error": "Invalid endpoint usage"}), 400

    def _trigger_run(self, company, source_id):
        source = self.document_repo.session.query(IngestionSource).filter_by(id=source_id, company_id=company.id).first()
        if not source:
            return jsonify({"error": "Source not found"}), 404

        if source.status == IngestionStatus.RUNNING:
            return jsonify({"error": "Ingestion already running"}), 409

        try:
            # Trigger sync execution (could be async in future)
            processed_count = self.load_documents_service.trigger_ingestion(source)
            return jsonify({
                "message": "Ingestion completed successfully",
                "processed_files": processed_count
            }), 200
        except Exception as e:
            logging.error(f"Ingestion trigger failed: {e}")
            return jsonify({"error": str(e)}), 500

    def _create_source(self, company):
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required_fields = ['name', 'source_type', 'configuration']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        try:
            # Validate Source Type
            source_type = IngestionSourceType(data['source_type']) # Will raise ValueError if invalid

            new_source = IngestionSource(
                company_id=company.id,
                name=data['name'],
                source_type=source_type,
                configuration=data['configuration'],
                schedule_cron=data.get('schedule_cron'),
                status=IngestionStatus.ACTIVE
            )

            # Optional: Link Collection
            if 'collection_type_id' in data:
                new_source.collection_type_id = data['collection_type_id']

            self.document_repo.create_or_update_ingestion_source(new_source)

            return jsonify(new_source.to_dict()), 201

        except ValueError as e:
            return jsonify({"error": f"Invalid source type or value: {str(e)}"}), 400
        except Exception as e:
            logging.error(f"Failed to create source: {e}")
            return jsonify({"error": "Internal server error"}), 500