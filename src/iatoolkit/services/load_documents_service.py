# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

from iatoolkit.repositories.models import Company, IngestionSource, IngestionStatus, IngestionSourceType
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.services.file_processor_service import FileProcessorConfig, FileProcessor
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.common.exceptions import IAToolkitException
import logging
from datetime import datetime
from injector import inject, singleton
import os


@singleton
class LoadDocumentsService:
    """
    Orchestrates the discovery and loading of documents.
    Now operates based on IngestionSource database records accessed via DocumentRepo.
    """
    @inject
    def __init__(self,
                 config_service: ConfigurationService,
                 file_connector_factory: FileConnectorFactory,
                 knowledge_base_service: KnowledgeBaseService,
                 document_repo: DocumentRepo  # New dependency
                 ):
        self.config_service = config_service
        self.file_connector_factory = file_connector_factory
        self.knowledge_base_service = knowledge_base_service
        self.document_repo = document_repo

        logging.getLogger().setLevel(logging.ERROR)

    def load_sources(self,
                     company: Company,
                     sources_to_load: list[str] = None,
                     filters: dict = None) -> int:
        """
        Legacy/CLI Entrypoint.
        1. Syncs sources from YAML to DB to ensure consistency.
        2. Triggers ingestion for the requested sources (by name).
        """
        if not sources_to_load:
            raise IAToolkitException(IAToolkitException.ErrorType.PARAM_NOT_FILLED,
                                     f"Missing sources to load for company '{company.short_name}'.")

        # 1. Sync DB with YAML configuration
        self.sync_sources_from_yaml(company)

        # 2. Retrieve sources from DB using Repo
        sources = self.document_repo.get_active_ingestion_sources(company.id, sources_to_load)

        if not sources:
            logging.warning(f"No active ingestion sources found matching: {sources_to_load}")
            return 0

        total_processed = 0
        for source in sources:
            try:
                total_processed += self.trigger_ingestion(source, filters)
            except Exception as e:
                logging.error(f"Error executing source {source.name}: {e}")

        return total_processed

    def sync_sources_from_yaml(self, company: Company):
        """
        Reads the company.yaml 'document_sources' and creates/updates IngestionSource records.
        This allows managing sources via YAML until the UI is fully ready.
        """
        kb_config = self.config_service.get_configuration(company.short_name, 'knowledge_base')
        if not kb_config:
            return

        yaml_sources = kb_config.get('document_sources', {})
        base_connector = self._get_base_connector_config(kb_config)

        for name, config in yaml_sources.items():
            # Determine type based on base connector or specific config override
            source_type = IngestionSourceType.LOCAL if base_connector.get('type') == 'local' else IngestionSourceType.S3

            # Build Configuration JSON for the Connector Factory
            full_config = base_connector.copy()
            full_config.update({
                'path': config.get('path'),
                'folder': config.get('folder'),
                'metadata': config.get('metadata', {}),
                'collection': config.get('collection') # Store collection name in config for now
            })

            # Check if exists using Repo
            source_record = self.document_repo.get_ingestion_source_by_name(company.id, name)

            if not source_record:
                source_record = IngestionSource(
                    company_id=company.id,
                    name=name,
                    source_type=source_type,
                    status=IngestionStatus.ACTIVE
                )

            # Update config (whether new or existing)
            source_record.configuration = full_config

            # Save using Repo
            self.document_repo.create_or_update_ingestion_source(source_record)

    def trigger_ingestion(self, source: IngestionSource, filters: dict = None) -> int:
        """
        Executes the ingestion for a specific DB Source.
        This is the method the API and Scheduler will call.
        """
        # 1. Update Status
        source.status = IngestionStatus.RUNNING
        source.last_error = None
        self.document_repo.create_or_update_ingestion_source(source)

        processed_count = 0
        try:
            logging.info(f"🚀 Starting ingestion for source '{source.name}' ({source.id})")

            # 2. Prepare Context
            connector_config = source.configuration
            metadata = connector_config.get('metadata', {})

            # Resolve Collection Name (Prefer relation, fallback to config dict)
            collection_name = source.collection_type.name if source.collection_type else connector_config.get('collection')

            context = {
                'company': source.company,
                'collection': collection_name,
                'metadata': metadata
            }

            processor_config = FileProcessorConfig(
                callback=self._file_processing_callback,
                context=context,
                filters=filters or {"filename_contains": ".pdf"},
                continue_on_error=True,
                echo=True
            )

            # 3. Factory & Process
            connector = self.file_connector_factory.create(connector_config)
            processor = FileProcessor(connector, processor_config)
            processor.process_files()

            processed_count = processor.processed_files

            # 4. Success Update
            source.last_run_at = datetime.now()
            source.status = IngestionStatus.ACTIVE
            logging.info(f"✅ Finished source '{source.name}'. Processed: {processed_count}")

        except Exception as e:
            logging.exception(f"❌ Ingestion failed for source {source.name}")
            source.status = IngestionStatus.ERROR
            source.last_error = str(e)
            raise e
        finally:
            self.document_repo.create_or_update_ingestion_source(source)

        return processed_count

    def _get_base_connector_config(self, knowledge_base_config: dict) -> dict:
        """Determines and returns the appropriate base connector configuration (dev vs prod)."""
        connectors = knowledge_base_config.get('connectors', {})
        env = os.getenv('FLASK_ENV', 'dev')

        if env == 'dev':
            return connectors.get('development', {'type': 'local'})
        else:
            prod_config = connectors.get('production')
            if not prod_config:
                return {}
            return prod_config

    def _file_processing_callback(self, company: Company, filename: str, content: bytes, context: dict = None):
        """
        Callback method to process a single file.
        Delegates the actual ingestion (storage, vectorization) to KnowledgeBaseService.
        """
        if not company:
            raise IAToolkitException(IAToolkitException.ErrorType.MISSING_PARAMETER, "Missing company object in callback.")

        try:
            predefined_metadata = context.get('metadata', {}) if context else {}

            new_document = self.knowledge_base_service.ingest_document_sync(
                company=company,
                filename=filename,
                content=content,
                collection=context.get('collection'),
                metadata=predefined_metadata
            )

            return new_document

        except Exception as e:
            logging.exception(f"Error processing file '{filename}': {e}")
            raise IAToolkitException(IAToolkitException.ErrorType.LOAD_DOCUMENT_ERROR,
                                     f"Error while processing file: {filename}")