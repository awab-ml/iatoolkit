# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit Enterprise

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from iat_enterprise.services.tasks_service import TaskService
from iat_enterprise.infra.jobs import run_task_job
from iatoolkit.infra.call_service import CallServiceClient
from iatoolkit.services.storage_service import StorageService
from iat_enterprise.repositories.models import Task, TaskStatus, TaskType
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.services.parsers.parsing_service import ParsingService
from iatoolkit.common.util import Utility
from iatoolkit.common.exceptions import IAToolkitException
from datetime import datetime, timedelta
from iat_enterprise.infra.task_queue import TaskQueue
import base64


class TestTaskService:

    def setup_method(self):
        self.mock_task_repo = MagicMock()
        self.mock_query_service = MagicMock()
        self.mock_query_service.context_builder = MagicMock()
        self.mock_query_service.context_builder.get_prompt_output_contract.return_value = {
            "attachment_mode": "extracted_only"
        }
        self.mock_profile_repo = MagicMock()
        self.mock_call_service = MagicMock(spec=CallServiceClient)
        self.mock_task_queue = MagicMock(spec=TaskQueue)
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_knowledge_base_service = MagicMock(spec=KnowledgeBaseService)
        self.mock_storage_service = MagicMock(spec=StorageService)  # Nuevo Mock
        self.mock_parsing_service = MagicMock(spec=ParsingService)
        self.util = MagicMock(spec=Utility)

        self.task_service = TaskService(
            task_queue=self.mock_task_queue,
            task_repo=self.mock_task_repo,
            query_service=self.mock_query_service,
            knowledge_base_service=self.mock_knowledge_base_service, # Inyección
            profile_repo=self.mock_profile_repo,
            call_service=self.mock_call_service,
            config_service=self.mock_config_service,
            storage_service=self.mock_storage_service,
            parsing_service=self.mock_parsing_service,
            util=self.util
        )

        # Updated mock task
        self.task_mock = Task(
            id=99,
            company_short_name="test_company",
            prompt_name="prompt.tpl",
            external_reference_id='workflow_1',
            client_data={"key": "value"},
            execute_at=datetime.now(),
            status=TaskStatus.pending,
            type=TaskType.PROMPT_EXECUTION,
            files=[]
        )

        # Default behavior: no config found for tasks
        self.mock_config_service.get_configuration.return_value = {}

    def test_create_task_when_company_not_found(self):
        self.mock_profile_repo.get_company_by_short_name.return_value = None

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.create_task(
                company_short_name="non_existent_company",
                user_identifier='an_user',
                client_data={},
                prompt_name="test_prompt"
            )

        assert excinfo.value.error_type == IAToolkitException.ErrorType.INVALID_NAME
        assert "No existe la empresa" in str(excinfo.value)

    def test_create_task_when_ok(self):
        self.mock_task_repo.create_task.return_value = self.task_mock

        result_task = self.task_service.create_task(
            company_short_name="test_company",
            user_identifier='an_user',
            client_data={"key": "value"},
            prompt_name="test_prompt"
        )

        assert result_task.status == TaskStatus.pending
        self.mock_task_queue.enqueue.assert_called_once()
        self.mock_query_service.llm_query.assert_not_called()

    def test_create_task_validates_required_inputs(self):
        self.mock_config_service.get_configuration.return_value = {
            "test_prompt": {
                "required_inputs": ["mandatory_field"]
            }
        }
        self.mock_profile_repo.get_company_by_short_name.return_value = MagicMock()

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.create_task(
                company_short_name="test_company",
                user_identifier='an_user',
                client_data={"other_field": "value"},
                prompt_name="test_prompt"
            )

        assert excinfo.value.error_type == IAToolkitException.ErrorType.MISSING_PARAMETER

    def test_create_task_applies_execution_policy_timeout(self):
        self.mock_config_service.get_configuration.return_value = {
            "test_prompt": {
                "execution": {"timeout_seconds": 300}
            }
        }
        self.mock_task_repo.create_task.return_value = self.task_mock

        self.task_service.create_task(
            company_short_name="test_company",
            user_identifier='an_user',
            client_data={},
            prompt_name="test_prompt"
        )

        self.mock_task_queue.enqueue.assert_called_with(
            run_task_job,
            self.task_mock.id,
            queue_name="default",
            job_timeout="300s",
            description='Prompt Execution: prompt.tpl ID: 99',
        )

    def test_review_task_when_task_not_found(self):
        self.mock_task_repo.get_task_by_id.return_value = None

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.review_task(task_id=99,
                                          review_user='pgonzalez',
                                          approved=True,
                                          comment='Validación aprobada')

        assert excinfo.value.error_type.name == "TASK_NOT_FOUND"

    def test_review_task_when_invalid_status(self):
        self.mock_task_repo.get_task_by_id.return_value = self.task_mock

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.review_task(task_id=99,
                                          review_user='pgonzalez',
                                          approved=True,
                                          comment='Validación aprobada')

        assert excinfo.value.error_type.name == "INVALID_STATE"

    def test_execute_task_when_llm_error(self):
        self.task_mock.files = [{
            "filename": "evidence.png",
            "storage_key": "companies/test/docs/evidence.png",
            "type": "image/png",
        }]
        self.mock_storage_service.get_document_content.return_value = base64.b64encode(b"image-bytes")
        llm_response = {
            "query_id": 456,
            "valid_response": False,
            "error": "IA error"}
        self.mock_query_service.llm_query.return_value = llm_response

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.execute_task(self.task_mock)

        assert excinfo.value.error_type == IAToolkitException.ErrorType.LLM_ERROR
        assert self.task_mock.status == TaskStatus.failed
        self.mock_storage_service.delete_file.assert_called_once_with(
            "test_company",
            "companies/test/docs/evidence.png"
        )

    def test_execute_task_when_llm_response_valid(self):
        llm_response = {"query_id": 123, "valid_response": True}
        self.mock_query_service.llm_query.return_value = llm_response
        result_task = self.task_service.execute_task(self.task_mock)

        assert result_task.llm_query_id == 123
        assert result_task.status == TaskStatus.executed
        self.mock_task_repo.update_task.assert_called_once_with(result_task)

    def test_execute_task_prompt_converts_document_attachments_to_text(self):
        self.task_mock.files = [{
            "filename": "manual.pdf",
            "storage_key": "companies/test/docs/manual.pdf",
            "type": "application/pdf",
        }]
        self.mock_storage_service.get_document_content.return_value = base64.b64encode(b"%PDF-test")
        self.mock_parsing_service.parse_document.return_value = SimpleNamespace(
            provider="docling",
            texts=[SimpleNamespace(text="Resumen del documento")],
            tables=[SimpleNamespace(text="| col |\n| --- |\n| 1 |")],
        )

        self.mock_query_service.llm_query.return_value = {"query_id": 1001, "valid_response": True}

        self.task_service.execute_task(self.task_mock)

        self.mock_parsing_service.parse_document.assert_called_once()
        llm_kwargs = self.mock_query_service.llm_query.call_args.kwargs
        sent_file = llm_kwargs["files"][0]
        assert sent_file["filename"] == "manual.txt"
        decoded_text = base64.b64decode(sent_file["content"]).decode("utf-8")
        assert "Resumen del documento" in decoded_text
        assert "[TABLE 1]" in decoded_text
        self.mock_storage_service.delete_file.assert_called_once_with(
            "test_company",
            "companies/test/docs/manual.pdf"
        )

    def test_execute_task_prompt_uses_original_attachment_when_conversion_fails(self):
        self.task_mock.files = [{
            "filename": "manual.pdf",
            "storage_key": "companies/test/docs/manual.pdf",
            "type": "application/pdf",
        }]
        original_b64 = base64.b64encode(b"%PDF-test").decode("utf-8")
        self.mock_storage_service.get_document_content.return_value = original_b64.encode("utf-8")
        self.mock_parsing_service.parse_document.side_effect = RuntimeError("docling failed")

        self.mock_query_service.llm_query.return_value = {"query_id": 1002, "valid_response": True}

        self.task_service.execute_task(self.task_mock)

        llm_kwargs = self.mock_query_service.llm_query.call_args.kwargs
        sent_file = llm_kwargs["files"][0]
        assert sent_file["filename"] == "manual.pdf"
        assert sent_file["content"] == original_b64

    def test_execute_task_prompt_preserves_native_attachment_when_mode_is_native_only(self):
        self.task_mock.files = [{
            "filename": "manual.pdf",
            "storage_key": "companies/test/docs/manual.pdf",
            "type": "application/pdf",
        }]
        original_b64 = base64.b64encode(b"%PDF-test-native").decode("utf-8")
        self.mock_storage_service.get_document_content.return_value = original_b64.encode("utf-8")
        self.mock_query_service.context_builder.get_prompt_output_contract.return_value = {
            "attachment_mode": "native_only"
        }
        self.mock_query_service.llm_query.return_value = {"query_id": 1003, "valid_response": True}

        self.task_service.execute_task(self.task_mock)

        self.mock_parsing_service.parse_document.assert_not_called()
        llm_kwargs = self.mock_query_service.llm_query.call_args.kwargs
        sent_file = llm_kwargs["files"][0]
        assert sent_file["filename"] == "manual.pdf"
        assert sent_file["content"] == original_b64

    def test_execute_task_with_callback_when_llm_returns_error(self):
        # Setup task with callback
        self.task_mock.callback_url = "http://my-callback.com"
        error_msg = "Model overloaded"

        # Mock LLM returning error
        llm_response = {
            "error": True,
            "error_message": error_msg
        }
        self.mock_query_service.llm_query.return_value = llm_response
        self.mock_call_service.post.return_value = ({}, 200)

        # Expect exception
        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.execute_task(self.task_mock)

        # Verify exception type
        assert excinfo.value.error_type == IAToolkitException.ErrorType.LLM_ERROR

        # Verify task status and error message were updated
        assert self.task_mock.status == TaskStatus.failed
        assert self.task_mock.error_msg == error_msg

        # Verify persistence (DB update)
        self.mock_task_repo.update_task.assert_called_once_with(self.task_mock)

        # Verify callback was called with correct data
        self.mock_call_service.post.assert_called_once()
        args, _ = self.mock_call_service.post.call_args
        url, payload = args

        assert url == "http://my-callback.com"
        assert payload['status'] == 'failed'
        assert payload['error_message'] == error_msg
        assert payload['task_id'] == self.task_mock.id

    def test_execute_task_when_exception_in_callback(self):
        llm_response = {
            "query_id": 123,
            "valid_response": True,
            "answer": 'an llm answer',
            "additional_data": {}
        }
        self.mock_query_service.llm_query.return_value = llm_response
        self.task_mock.callback_url = "http://test.com"
        self.mock_call_service.post.side_effect =Exception("timeout")
        with pytest.raises(IAToolkitException) as excinfo:
            result_task = self.task_service.execute_task(self.task_mock)

        assert excinfo.value.error_type == IAToolkitException.ErrorType.REQUEST_ERROR


    def test_execute_task_when_callback_ok(self):
        llm_response = {
            "query_id": 123,
            "valid_response": True,
            "answer": 'an llm answer',
            "additional_data": {}
        }
        self.mock_query_service.llm_query.return_value = llm_response
        self.task_mock.callback_url = "http://test.com"
        self.task_mock.client_data = {"key": "value"}
        self.mock_call_service.post.return_value = {'status': 'ok'}, 200
        result_task = self.task_service.execute_task(self.task_mock)

        assert result_task.llm_query_id == 123
        assert result_task.status == TaskStatus.executed
        self.mock_call_service.post.assert_called_once()

    def test_get_task_execution_result_for_prompt_task(self):
        llm_query = SimpleNamespace(
            id=123,
            output="Prompt answer",
            stats={"total_tokens": 456},
            valid_response=True,
            response={
                "structured_output": {"summary": "ok"},
                "schema_valid": True,
                "schema_errors": [],
                "schema_applied": True,
            },
        )
        self.mock_task_repo.get_llm_query_by_id.return_value = llm_query
        self.task_mock.llm_query_id = 123
        self.task_mock.type = TaskType.PROMPT_EXECUTION

        result = self.task_service.get_task_execution_result(self.task_mock)

        assert result["query_id"] == 123
        assert result["answer"] == "Prompt answer"
        assert result["stats"]["total_tokens"] == 456
        assert result["valid_response"] is True
        assert result["structured_output"] == {"summary": "ok"}

    def test_get_task_execution_result_fallbacks_to_additional_data_when_structured_output_missing(self):
        llm_query = SimpleNamespace(
            id=124,
            output="Prompt answer",
            stats={"total_tokens": 50},
            valid_response=True,
            response={
                "format": "json_string",
                "additional_data": {"employees": [{"id": 1}]},
            },
        )
        self.mock_task_repo.get_llm_query_by_id.return_value = llm_query
        self.task_mock.llm_query_id = 124
        self.task_mock.type = TaskType.PROMPT_EXECUTION

        result = self.task_service.get_task_execution_result(self.task_mock)

        assert result["query_id"] == 124
        assert result["structured_output"] == {"employees": [{"id": 1}]}


    # --- Tests para Ingestión RAG ---
    def test_execute_task_ingestion_success(self):
        """Test happy path for KNOWLEDGE_INGESTION task w/ Storage Cleanup"""
        # Configurar tarea de ingestión simulando que ya tiene la key de storage
        # (ya no usamos 'content' en base64 aquí, sino referencia)
        files_metadata = [{
            'filename': 'doc.pdf',
            'storage_key': 'companies/abc/docs/123.pdf',
            'type': 'application/pdf'
        }]

        ingest_task = Task(
            id=100,
            company_short_name="test_company",
            type=TaskType.KNOWLEDGE_INGESTION,
            status=TaskStatus.pending,
            files=files_metadata,
            client_data={},
            execute_at=None
        )

        # Mocks
        self.mock_profile_repo.get_company_by_short_name.return_value = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = 1
        self.mock_knowledge_base_service.ingest_document_sync.return_value = mock_doc

        # Mock del Storage: devuelve el contenido EN BASE64 (simulando lo que guardó get_task_files)
        # "dummy pdf content" en base64 es b'ZHVtbXkgcGRmIGNvbnRlbnQ='
        base64_content = base64.b64encode(b"dummy pdf content")
        self.mock_storage_service.get_document_content.return_value = base64_content

        # Execute
        self.task_service.execute_task(ingest_task)

        # Assert 1: Se descargó el contenido del storage
        self.mock_storage_service.get_document_content.assert_called_with("test_company", 'companies/abc/docs/123.pdf')

        # Assert 2: Se llamó al servicio de ingestión
        # El servicio decodifica el base64, así que ingestión recibe los bytes originales
        self.mock_knowledge_base_service.ingest_document_sync.assert_called_once()
        args, kwargs = self.mock_knowledge_base_service.ingest_document_sync.call_args
        assert kwargs['content'] == b"dummy pdf content"

        # Assert 3: IMPORTANTE - Se eliminó el archivo del storage tras el éxito
        self.mock_storage_service.delete_file.assert_called_once_with("test_company", 'companies/abc/docs/123.pdf')

        # Assert 4: Estado final
        assert ingest_task.status == TaskStatus.executed

    def test_execute_task_ingestion_fails_if_company_missing(self):
        ingest_task = Task(
            id=101,
            company_short_name="missing_company",
            type=TaskType.KNOWLEDGE_INGESTION,
            status=TaskStatus.pending,
            files=[]
        )
        self.mock_profile_repo.get_company_by_short_name.return_value = None

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.execute_task(ingest_task)

        assert excinfo.value.error_type == IAToolkitException.ErrorType.INVALID_NAME
        assert ingest_task.status == TaskStatus.failed

    def test_execute_task_ingestion_cleans_up_temp_file_when_processing_fails(self):
        ingest_task = Task(
            id=102,
            company_short_name="test_company",
            type=TaskType.KNOWLEDGE_INGESTION,
            status=TaskStatus.pending,
            files=[{
                'filename': 'broken.pdf',
                'storage_key': 'companies/abc/docs/broken.pdf',
                'type': 'application/pdf'
            }],
            client_data={},
            execute_at=None
        )
        self.mock_profile_repo.get_company_by_short_name.return_value = MagicMock()
        self.mock_storage_service.get_document_content.return_value = base64.b64encode(b"broken content")
        self.mock_knowledge_base_service.ingest_document_sync.side_effect = RuntimeError("parse error")

        with pytest.raises(IAToolkitException) as excinfo:
            self.task_service.execute_task(ingest_task)

        assert excinfo.value.error_type == IAToolkitException.ErrorType.TASK_EXECUTION_ERROR
        self.mock_storage_service.delete_file.assert_called_once_with(
            "test_company",
            "companies/abc/docs/broken.pdf"
        )


    def test_notify_callback_ingestion_with_errors(self):
        """
        Verifica que si la tarea es de Ingestión, el callback incluya
        los detalles de error y conteos específicos, y no los campos de prompt.
        """
        # 1. Configurar Tarea de Ingestión
        ingest_task = Task(
            id=200,
            company_short_name="test_company",
            type=TaskType.KNOWLEDGE_INGESTION,
            status=TaskStatus.executed,
            callback_url="http://callback-test.com",
            external_reference_id="ref_123",
            files=[],
            client_data={}
        )

        # 2. Simular respuesta con éxito parcial (1 OK, 1 Error)
        ingestion_response = {
            'ingested_count': 1,
            'failed_count': 1,
            'details': [{'filename': 'good.pdf', 'status': 'success'}],
            'errors': [{'filename': 'bad.pdf', 'error': 'Corrupted file'}]
        }

        self.mock_call_service.post.return_value = ({}, 200)

        # 3. Ejecutar
        self.task_service.notify_callback(ingest_task, ingestion_response)

        # 4. Validar llamada al servicio externo
        self.mock_call_service.post.assert_called_once()
        args, _ = self.mock_call_service.post.call_args
        url, payload = args

        assert url == "http://callback-test.com"
        assert payload['task_id'] == 200
        # Campos específicos de ingestión
        assert payload['ingested_count'] == 1
        assert payload['failed_count'] == 1
        assert len(payload['errors']) == 1
        assert payload['errors'][0]['filename'] == 'bad.pdf'

        # Asegurar que NO se envían campos de prompt
        assert 'answer' not in payload

    @patch("iat_enterprise.services.tasks_service.secure_filename", return_value="secure_file.txt")
    def test_get_task_files_when_save_exception(self, mock_secure_filename):
        uploaded_file_mock = MagicMock()
        # Mocking Werkzeug file object behavior
        uploaded_file_mock.filename = "file.txt"
        uploaded_file_mock.read.side_effect = Exception("Error Guardando")

        with pytest.raises(IAToolkitException) as excinfo:
            # FIX: Añadimos "test_company" como primer argumento
            self.task_service.get_task_files("test_company", [uploaded_file_mock])

        assert excinfo.value.error_type == IAToolkitException.ErrorType.FILE_IO_ERROR

        @patch("iat_enterprise.services.tasks_service.secure_filename", return_value="secure_file.txt")
        def test_get_task_files_when_success(self, mock_secure_filename):
            """Test que verifica la subida al Storage Service"""
            uploaded_file_mock = MagicMock()
            uploaded_file_mock.filename = "file.txt"
            uploaded_file_mock.content_type = "text/plain"
            uploaded_file_mock.read.return_value = b"content bytes"

            # Mock del resultado de upload
            self.mock_storage_service.upload_document.return_value = "s3://bucket/key.txt"

            # Ejecutar pasando company_short_name (ahora requerido)
            files_info = self.task_service.get_task_files("test_company", [uploaded_file_mock])

            # Asserts
            assert len(files_info) == 1
            assert files_info[0]['filename'] == "secure_file.txt"
            assert files_info[0]['storage_key'] == "s3://bucket/key.txt"

            # Verificar que NO devolvemos el contenido en el dict (para no llenar la DB)
            assert 'content' not in files_info[0]

            # Verificar llamada al storage
            # IMPORTANTE: Ahora validamos que se suba el contenido en BASE64
            expected_content = base64.b64encode(b"content bytes")

            self.mock_storage_service.upload_document.assert_called_once_with(
                company_short_name="test_company",
                file_content=expected_content,
                filename="secure_file.txt",
                mime_type="text/plain"
            )
