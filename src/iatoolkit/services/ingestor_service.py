# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit import current_iatoolkit
from iatoolkit.repositories.models import Company, IngestionSource
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.services.ingestion_source_service import IngestionSourceService
from iatoolkit.services.ingestion_runner_service import IngestionRunnerService
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.common.exceptions import IAToolkitException
import logging
from injector import inject, singleton



@singleton
class IngestorService:
    """
    Backwards-compatible facade.
    Keeps old name used across the app/tests, but delegates responsibilities to:
    - IngestionSourceService (CRUD)
    - IngestionRunnerService (execution + runs)
    """
    @inject
    def __init__(self,
                 config_service: ConfigurationService,
                 file_connector_factory: FileConnectorFactory,
                 knowledge_base_service: KnowledgeBaseService,
                 document_repo: DocumentRepo,
                 ingestion_source_service: IngestionSourceService,
                 ingestion_runner_service: IngestionRunnerService
                 ):
        self.config_service = config_service
        self.file_connector_factory = file_connector_factory
        self.knowledge_base_service = knowledge_base_service
        self.document_repo = document_repo

        self.ingestion_source_service = ingestion_source_service
        self.ingestion_runner_service = ingestion_runner_service

        logging.getLogger().setLevel(logging.ERROR)

    def run_ingestion(self, company: Company, source_id: int, user_identifier: str | None = None) -> int:
        return self.ingestion_runner_service.run_ingestion(company, source_id, user_identifier=user_identifier)

    def create_source(self, company: Company, data: dict) -> IngestionSource:
        return self.ingestion_source_service.create_source(company, data)

    def update_source(self, company: Company, source_id: int, data: dict) -> IngestionSource:
        return self.ingestion_source_service.update_source(company, source_id, data)

    def delete_source(self, company: Company, source_id: int) -> None:
        return self.ingestion_source_service.delete_source(company, source_id)

    # --- CLI Legacy Support ---

    def load_sources(self,
                     company: Company,
                     sources_to_load: list[str] = None,
                     filters: dict = None) -> int:
        """
        Legacy Entrypoint for CLI.
        1. Syncs sources from YAML to DB.
        2. Triggers ingestion for the requested sources (by name).
        """
        if not current_iatoolkit().is_community:
            return

        if not sources_to_load:
            raise IAToolkitException(IAToolkitException.ErrorType.PARAM_NOT_FILLED,
                                     f"Missing sources to load for company '{company.short_name}'.")

        self.sync_sources_from_yaml(company)

        sources = self.document_repo.get_active_ingestion_sources(company.id, sources_to_load)
        if not sources:
            logging.warning(f"No active ingestion sources found matching: {sources_to_load}")
            return 0

        total_processed = 0
        for source in sources:
            total_processed += self.ingestion_runner_service._trigger_ingestion_logic(source, filters=filters or {})

        return total_processed

    def _get_base_connector_config(self, knowledge_base_config: dict) -> dict:
        connectors = knowledge_base_config.get('connectors', {})
        import os
        env = os.getenv('FLASK_ENV', 'dev')
        if env == 'dev':
            return connectors.get('development', {'type': 'local'})
        else:
            return connectors.get('production', {})

    def sync_sources_from_yaml(self, company: Company):
        kb_config = self.config_service.get_configuration(company.short_name, 'knowledge_base')
        if not kb_config:
            return

        yaml_sources = kb_config.get('document_sources', {})
        base_connector = self._get_base_connector_config(kb_config)

        from iatoolkit.repositories.models import IngestionSourceType, IngestionStatus

        for name, config in yaml_sources.items():
            source_type = IngestionSourceType.LOCAL if base_connector.get('type') == 'local' else IngestionSourceType.S3

            full_config = base_connector.copy()
            full_config.update({
                'path': config.get('path'),
                'folder': config.get('folder'),
                'metadata': config.get('metadata', {}),
                'collection': config.get('collection')
            })

            source_record = self.document_repo.get_ingestion_source_by_name(company.id, name)

            if not source_record:
                source_record = IngestionSource(
                    company_id=company.id,
                    name=name,
                    source_type=source_type,
                    status=IngestionStatus.ACTIVE
                )

            source_record.configuration = full_config
            self.document_repo.create_or_update_ingestion_source(source_record)