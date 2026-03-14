# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit Enterprise
#
# IAToolkit Enterprise is commercial, proprietary software.
# Unauthorized copying, modification, distribution, or use of this software,
# via any medium, is strictly prohibited unless explicitly permitted by the
# Enterprise License Agreement provided to the customer.
#
# This file is part of the IAToolkit Enterprise Edition and may not be
# redistributed as open-source. For licensing information, refer to:
# ENTERPRISE_LICENSE

from injector import inject
from iat_enterprise.repositories.models import Task, TaskType, TaskStatus
from iat_enterprise.infra.task_queue import TaskQueue
from iatoolkit.services.query_service import QueryService
from iatoolkit.services.storage_service import StorageService
from iatoolkit.services.knowledge_base_service import KnowledgeBaseService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.parsers.parsing_service import ParsingService
from iat_enterprise.repositories.tasks_repo import TaskRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.infra.call_service import CallServiceClient
from iatoolkit.common.util import Utility
from iatoolkit.common.exceptions import IAToolkitException
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
import base64
import os


class TaskService:
    @inject
    def __init__(self,
                 task_queue: TaskQueue,
                 task_repo: TaskRepo,
                 query_service: QueryService,
                 knowledge_base_service: KnowledgeBaseService,
                 profile_repo: ProfileRepo,
                 call_service: CallServiceClient,
                 config_service: ConfigurationService,
                 storage_service: StorageService,
                 parsing_service: ParsingService,
                 util: Utility):
        self.task_queue = task_queue
        self.task_repo = task_repo
        self.query_service = query_service
        self.storage_service = storage_service
        self.knowledge_base_service = knowledge_base_service
        self.profile_repo = profile_repo
        self.call_service = call_service
        self.config_service = config_service
        self.parsing_service = parsing_service
        self.util = util

    def _resolve_queue_for_task_type(self, task_type: TaskType) -> str:
        default_queue = (os.getenv("RQ_DEFAULT_QUEUE", "default") or "default").strip()
        ingestion_queue = (os.getenv("RQ_INGESTION_QUEUE", "ingestion") or "ingestion").strip()

        if task_type == TaskType.KNOWLEDGE_INGESTION:
            return ingestion_queue
        return default_queue

    def create_task(self,
                    company_short_name: str,
                    user_identifier: str,
                    client_data: dict,
                    task_type: TaskType = TaskType.PROMPT_EXECUTION,
                    prompt_name: str = None,
                    external_reference_id: str = None,
                    callback_url: str = None,
                    execute_at: datetime = None,
                    files: list = []
                    ) -> Task:

        if external_reference_id is not None:
            external_reference_id = str(external_reference_id)

        # type validation
        if task_type == TaskType.PROMPT_EXECUTION and not prompt_name:
             raise IAToolkitException(IAToolkitException.ErrorType.MISSING_PARAMETER,
                        "prompt_name is required for PROMPT_EXECUTION")

        # validate company
        company = self.profile_repo.get_company_by_short_name(company_short_name)
        if not company:
            raise IAToolkitException(IAToolkitException.ErrorType.INVALID_NAME,
                               f'No existe la empresa: {company_short_name}')

        # identify who is asking for this execution
        if not user_identifier:
            user_identifier = 'anonymous'

        # 1. Load Task Configuration (if available) ---
        task_config = {}
        if prompt_name:
            task_config = self._get_task_config(company_short_name, prompt_name)

        # 2. Validate Input Contracts ---
        if task_config:
            required_inputs = task_config.get('required_inputs', [])
            missing_inputs = [key for key in required_inputs if key not in client_data]
            if missing_inputs:
                raise IAToolkitException(
                    IAToolkitException.ErrorType.MISSING_PARAMETER,
                    f"Faltan datos requeridos para la tarea '{prompt_name}': {', '.join(missing_inputs)}"
                )

        # --- IDEMPOTENCY CHECK ---
        # if we have an external reference ID, check if it already exists to avoid duplicates
        # in case of retries or double submits.
        if external_reference_id:
            existing_task = self.task_repo.get_task_by_external_id(company_short_name, external_reference_id)
            if existing_task:
                logging.info(f"Task duplicada prevenida. Retornando existente: {existing_task.id}")
                return existing_task

        # process the task files (Upload to S3/Storage)
        task_files = self.get_task_files(company_short_name, files)

        # create Task object
        new_task = Task(
            company_short_name=company_short_name,
            user_identifier=user_identifier,
            type=task_type,
            status=TaskStatus.pending,
            prompt_name=prompt_name,
            external_reference_id=external_reference_id,
            client_data=client_data,
            callback_url=callback_url,
            files=task_files
        )
        new_task = self.task_repo.create_task(new_task)

        # Apply Execution Policy (Timeout) ---
        job_timeout = '10m'
        if task_config and 'execution' in task_config:
            timeout_seconds = task_config['execution'].get('timeout_seconds')
            if timeout_seconds:
                job_timeout = f"{timeout_seconds}s"

        queue_name = self._resolve_queue_for_task_type(task_type)

        # Enqueue asynchronous job passing only the ID
        # Lazy Import for avoiding circular imports
        from iat_enterprise.infra.jobs import run_task_job
        self.task_queue.enqueue(
            run_task_job,
            new_task.id,
            queue_name=queue_name,
            job_timeout=job_timeout,
            description=f'{new_task.description} ID: {new_task.id}'
        )

        return new_task

    def execute_task(self, task: Task):
        # in this case do nothing
        if task.status != TaskStatus.pending:
            return task

        response = {}
        try:
            # --- DISPATCHER ---
            if task.type == TaskType.PROMPT_EXECUTION:
                response = self._execute_prompt_task(task)
            elif task.type == TaskType.KNOWLEDGE_INGESTION:
                response = self._execute_ingestion_task(task)
            else:
                raise IAToolkitException(IAToolkitException.ErrorType.INVALID_NAME,
                            f"Task type is not supported: {task.type}")

            # exit
            task.status = TaskStatus.executed

        except IAToolkitException as ie:
            task.error_msg = ie.message
            task.status = TaskStatus.failed
            raise ie

        except Exception as e:
            task.status = TaskStatus.failed
            task.error_msg = str(e)
            error_message = response.get('error') or response.get('error_message') or str(e)
            raise IAToolkitException(IAToolkitException.ErrorType.TASK_EXECUTION_ERROR,
                                     error_message)

        finally:
            self._cleanup_temporary_task_files(task)
            self.task_repo.update_task(task)

            # Callbacks
            if task.callback_url:
                self.notify_callback(task, response)

        return task

    def _execute_prompt_task(self, task: Task):
        # Apply Model Override Policy ---
        # Default to None (let QueryService use company default)
        model_override = None

        task_config = self._get_task_config(task.company_short_name, task.prompt_name)
        if task_config and 'llm_model' in task_config:
            model_override = task_config['llm_model']
        elif 'model' in task.client_data:
            model_override = task.client_data['model']

        company = self.profile_repo.get_company_by_short_name(task.company_short_name)

        # Hydrate files content from Storage if needed by LLM
        # (Assuming query_service needs the actual content bytes/base64)
        hydrated_files = self._hydrate_files_content(task.company_short_name, task.files)
        llm_files = self._prepare_prompt_files_for_llm(task, hydrated_files, company=company)

        # call the IA
        response = self.query_service.llm_query(
            company_short_name=task.company_short_name,
            user_identifier=task.user_identifier,
            task_id=task.id,
            model=model_override,
            prompt_name=task.prompt_name,
            client_data=task.client_data,
            ignore_history=True,
            files=llm_files,
        )
        if 'error' in response:
            task.status = TaskStatus.failed
            raise IAToolkitException(IAToolkitException.ErrorType.LLM_ERROR,
                                     response.get('error_message'))

        # update the Task with the response from llm_query
        task.llm_query_id = response.get('query_id', 0)

        # validate response
        if not response.get('valid_response'):
            task.status = TaskStatus.failed
            raise IAToolkitException(IAToolkitException.ErrorType.LLM_ERROR,
                            "Invalid response in TaskService._execute_prompt_task")

        return response

    def _execute_ingestion_task(self, task: Task):
        """
        Procesa la ingestión de documentos en la Knowledge Base.
        Decodifica archivos Base64 y delega al KnowledgeBaseService.
        """
        company = self.profile_repo.get_company_by_short_name(task.company_short_name)
        if not company:
            raise IAToolkitException(IAToolkitException.ErrorType.INVALID_NAME,
                                     f"Company '{task.company_short_name}' not found.")

        ingestion_results = []
        errors = []

        # 2. iterate over files
        # task.files is a list of dicts: [{'filename': '...', 'content': 'base64...', 'type': '...'}]
        if not task.files:
            raise IAToolkitException(IAToolkitException.ErrorType.MISSING_PARAMETER,
                                     "No files provided for ingestion task.")

        for file_info in task.files:
            filename = file_info.get('filename')
            storage_key = file_info.get('storage_key')

            try:
                # Retrieve content from StorageService (Returns Base64 encoded in bytes)
                raw_content = self.storage_service.get_document_content(task.company_short_name, storage_key)
                file_bytes = None

                # 2. detect if it's Base64 or Binary
                try:
                    content_str = raw_content.decode('utf-8').strip()

                    # Si decodifica, verificamos si parece Base64 (data URI o caracteres b64 válidos)
                    if ',' in content_str and content_str.startswith('data:'):
                        # Es un Data URI (ej: "data:application/pdf;base64,JVBERi...")
                        _, b64_data = content_str.split(',', 1)
                        file_bytes = base64.b64decode(b64_data)
                    else:
                        # Intentamos decodificar como Base64 puro
                        try:
                            # Validación rápida: length % 4 == 0 y solo caracteres válidos
                            # O simplemente intentar decodificar.
                            decoded = base64.b64decode(content_str, validate=True)
                            file_bytes = decoded
                        except Exception:
                            # Si falla la decodificación B64, asumimos que era texto plano o binario que coincidió con UTF-8
                            # Para ingestión de documentos, preferimos usar los bytes originales si no es B64
                            file_bytes = raw_content

                except UnicodeDecodeError:
                    # Si falla el decode('utf-8'), es definitivamente binario (ej. PDF puro)
                    logging.debug(f"File {filename} is binary, using raw bytes.")
                    file_bytes = raw_content

                # send to KnowledgeBaseService
                # Pass client metadata if exists, adding the task_id
                meta = task.client_data.copy()
                meta.update({'source_task_id': task.id})

                doc = self.knowledge_base_service.ingest_document_sync(
                    company=company,
                    filename=filename,
                    user_identifier=task.user_identifier,
                    content=file_bytes,
                    metadata=meta,
                    collection=task.client_data.get('collection', None)
                )

                ingestion_results.append({
                        'filename': filename,
                        'status': 'success',
                        'doc_id': doc.id
                    })

                logging.debug(f"Ingested file '{filename}' for task {task.id}")

            except Exception as e:
                error_msg = str(e)
                logging.exception(f"Error ingesting '{filename}': {error_msg}")
                errors.append({'filename': filename, 'error': error_msg})
                # we don't want to stop ingestion if one file fails'

        # 3. return value
        result = {
            'ingested_count': len(ingestion_results),
            'failed_count': len(errors),
            'details': ingestion_results,
            'errors': errors
        }

        # Si todo falló, marcamos la tarea como fallida lanzando excepción
        if not ingestion_results and errors:
            raise IAToolkitException(IAToolkitException.ErrorType.TASK_EXECUTION_ERROR,
                                     f"All files failed to ingest: {errors}")

        return result

    def _cleanup_temporary_task_files(self, task: Task) -> None:
        files_metadata = task.files or []
        if not isinstance(files_metadata, list):
            return

        deleted_keys = set()
        for file_info in files_metadata:
            if not isinstance(file_info, dict):
                continue

            storage_key = file_info.get('storage_key')
            if not storage_key or storage_key in deleted_keys:
                continue

            deleted_keys.add(storage_key)
            filename = file_info.get('filename', 'unknown')
            try:
                self.storage_service.delete_file(task.company_short_name, storage_key)
            except Exception as cleanup_error:
                logging.warning(
                    "Cleanup warning for task %s file '%s' (storage_key=%s): %s",
                    task.id,
                    filename,
                    storage_key,
                    cleanup_error
                )

    def _get_task_config(self, company_short_name: str, prompt_name: str) -> dict:
        """Helper to retrieve task-specific configuration from company.yaml"""
        tasks_config = self.config_service.get_configuration(company_short_name, 'tasks')
        if tasks_config and prompt_name in tasks_config:
            return tasks_config[prompt_name]
        return {}

    def notify_callback(self, task: Task, response: dict):
        response_data = {
            'task_id': task.id,
            'external_reference_id': task.external_reference_id,
            'status': task.status.name,
        }

        if task.status == TaskStatus.failed:
            response_data['error_message'] = task.error_msg

        if task.type == TaskType.KNOWLEDGE_INGESTION:
            response_data.update({
                'ingested_count': response.get('ingested_count', 0),
                'failed_count': response.get('failed_count', 0),
                'details': response.get('details', []),
                'errors': response.get('errors', [])
            })
        else:
            response_data.update({
                'prompt_name': task.prompt_name,
                'model': response.get('stats', {}).get('model', ''),
                'answer': response.get('answer', ''),
                'additional_data': response.get('aditional_data', {}),
            })

        try:
            response, status_code = self.call_service.post(task.callback_url, response_data)
        except Exception as e:
            logging.exception(f"Error in callback notification {task.callback_url}: {str(e)}")
            raise IAToolkitException(
                IAToolkitException.ErrorType.REQUEST_ERROR,
                f"Error in callback notification {task.callback_url}: {str(e)}"
            )

    def get_task_files(self, company_short_name, uploaded_files):
        files_info = []

        for file_obj in uploaded_files:
            filename = 'unknown'
            content = b''
            content_type = 'application/octet-stream'

            # case 1: Es un diccionario (Viene del JSON Base64 del RAG)
            if isinstance(file_obj, dict):
                filename = secure_filename(file_obj.get('filename', 'unknown'))
                content_type = file_obj.get('type', 'application/octet-stream')
                content_str = file_obj.get('content', '')

                # Guardamos tal cual viene (con header data: si lo trae) para no romper el Prompt Execution
                # Solo aseguramos que sea bytes para el storage
                if isinstance(content_str, str):
                    content = content_str.encode('utf-8')
                else:
                    content = content_str   # Asumimos bytes si no es string

            # CASO 2: Es un FileStorage (Viene de un form-data estándar)
            elif hasattr(file_obj, 'filename'):
                filename = secure_filename(file_obj.filename)
                content_type = file_obj.content_type
                try:
                    raw_bytes = file_obj.read()
                    # CONVERTIR A BASE64: Para unificar formato y ser consistentes con el storage temporal
                    content = base64.b64encode(raw_bytes)
                except Exception as e:
                    raise IAToolkitException(
                        IAToolkitException.ErrorType.FILE_IO_ERROR,
                        f"Error al leer archivo {filename}: {str(e)}"
                    )

            # Subir a StorageService
            if content:
                try:
                    storage_key = self.storage_service.upload_document(
                        company_short_name=company_short_name,
                        file_content=content,
                        filename=filename,
                        mime_type=content_type
                    )

                    files_info.append({
                        'filename': filename,
                        'storage_key': storage_key,  # save the reference
                        'type': content_type
                    })
                except Exception as e:
                    logging.error(f"Failed to upload file {filename} to storage: {e}")
                    raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                                             f"Error uploading file {filename}")

        return files_info

    def _hydrate_files_content(self, company_short_name: str, files_metadata: list) -> list:
        """
        Helper to download file content from storage and re-construct the structure
        expected by query_service (with 'content' field).
        """
        if not files_metadata:
            return []

        hydrated = []
        for f in files_metadata:
            new_f = f.copy()
            if 'storage_key' in f:
                try:
                    content_bytes = self.storage_service.get_document_content(company_short_name, f['storage_key'])
                    new_f['content'] = content_bytes.decode('utf-8')
                except Exception as e:
                    logging.error(f"Error hydrating file {f.get('filename')}: {e}")
                    # Skip this file or let it fail later? Let's keep metadata but empty content
                    new_f['content'] = ''
            hydrated.append(new_f)
        return hydrated

    def _prepare_prompt_files_for_llm(self, task: Task, hydrated_files: list, company=None) -> list:
        """
        Converts document attachments into plain text before prompt execution.
        If conversion fails, keeps the original payload to preserve current behavior.
        """
        if not hydrated_files:
            return []

        # Respect prompt attachment contract: when native delivery is enabled, preserve original files.
        attachment_mode = "extracted_only"
        try:
            if company and task.prompt_name:
                contract = self.query_service.context_builder.get_prompt_output_contract(company, task.prompt_name) or {}
                attachment_mode = str(contract.get("attachment_mode") or "extracted_only").strip().lower()
        except Exception as e:
            logging.debug(
                "Could not resolve attachment_mode for task %s prompt '%s': %s",
                task.id,
                task.prompt_name,
                e,
            )

        if attachment_mode in {"native_only", "native_plus_extracted", "auto"}:
            return hydrated_files

        prepared_files = []
        for file_info in hydrated_files:
            prepared_file = file_info.copy()
            filename = (prepared_file.get('filename') or '').strip()
            content = prepared_file.get('content')

            if not filename or not content:
                prepared_files.append(prepared_file)
                continue

            if self._is_image_file(filename) or not self._is_docling_candidate(filename):
                prepared_files.append(prepared_file)
                continue

            try:
                raw_bytes = self._decode_attachment_payload(content)
                parse_result = self.parsing_service.parse_document(
                    company_short_name=task.company_short_name,
                    filename=filename,
                    content=raw_bytes,
                    metadata={"source": "prompt_task_attachment", "task_id": task.id},
                )

                extracted_text = self._compose_text_from_parse_result(parse_result)
                if not extracted_text.strip():
                    logging.warning(
                        "Parser returned empty content for attachment '%s' in task %s. Using original payload.",
                        filename,
                        task.id,
                    )
                    prepared_files.append(prepared_file)
                    continue

                base_name, _ = os.path.splitext(filename)
                prepared_file['filename'] = f"{base_name}.txt"
                prepared_file['type'] = 'text/plain'
                prepared_file['content'] = base64.b64encode(extracted_text.encode('utf-8')).decode('utf-8')

                mem_info = ""
                try:
                    import psutil
                    mem_mb = psutil.virtual_memory().available / (1024 * 1024)
                    mem_info = f" [Memoria disponible: {mem_mb:.2f} MB]"
                except ImportError:
                    pass

                logging.info(
                    "Attachment '%s' converted to text using provider '%s' for prompt task %s (%s bytes).%s",
                    filename,
                    getattr(parse_result, 'provider', 'unknown'),
                    task.id,
                    len(extracted_text),
                    mem_info
                )
            except Exception as e:
                logging.warning(
                    "Could not convert attachment '%s' to text for task %s. Using original payload. Error: %s",
                    filename,
                    task.id,
                    e,
                )

            prepared_files.append(prepared_file)

        return prepared_files

    def _compose_text_from_parse_result(self, parse_result) -> str:
        text_parts = []

        for text_unit in getattr(parse_result, 'texts', []) or []:
            text_value = (getattr(text_unit, 'text', '') or '').strip()
            if text_value:
                text_parts.append(text_value)

        for index, table_unit in enumerate(getattr(parse_result, 'tables', []) or [], start=1):
            table_text = (getattr(table_unit, 'text', '') or '').strip()
            if table_text:
                text_parts.append(f"[TABLE {index}]\n{table_text}")

        return "\n\n".join(text_parts)

    def _decode_attachment_payload(self, payload) -> bytes:
        if payload is None:
            return b""

        if isinstance(payload, bytes):
            try:
                payload = payload.decode('utf-8')
            except UnicodeDecodeError:
                return payload

        if not isinstance(payload, str):
            return b""

        payload = payload.strip()
        if not payload:
            return b""

        if payload.startswith('data:') and ',' in payload:
            payload = payload.split(',', 1)[1]

        try:
            return base64.b64decode(payload, validate=True)
        except Exception:
            return payload.encode('utf-8')

    def _is_docling_candidate(self, filename: str) -> bool:
        return filename.lower().endswith(('.pdf', '.docx', '.pptx', '.xlsx', '.html', '.htm'))

    def _is_image_file(self, filename: str) -> bool:
        return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))

    def review_task(self, task_id: int, review_user: str, approved: bool, comment: str):
        # get the task
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise IAToolkitException(IAToolkitException.ErrorType.TASK_NOT_FOUND,
                        f'No existe la tarea: {task_id}')

        if task.status != TaskStatus.executed:
            raise IAToolkitException(IAToolkitException.ErrorType.INVALID_STATE,
                        f'La tarea debe estar en estado ejecutada: {task_id}')

        # update the task
        task.approved = approved
        task.status = TaskStatus.approved if approved else TaskStatus.rejected
        task.review_user = review_user
        task.comment = comment
        task.review_date = datetime.now()
        self.task_repo.update_task(task)
        return task


    def list_tasks(self, company_short_name: str,
                   task_type: TaskType = None,
                   status_list: list[TaskStatus] = None,
                   start_date: datetime = None,
                   end_date: datetime = None,
                   prompt_name: str = None) -> list[Task]:
        """
        """
        return self.task_repo.list_tasks(
            company_short_name=company_short_name,
            task_type=task_type,
            status_list=status_list,
            start_date=start_date,
            end_date=end_date,
            prompt_name=prompt_name
        )

    def get_task(self, task_id: int) -> Task:
        return self.task_repo.get_task_by_id(task_id)

    def get_task_execution_result(self, task: Task) -> dict:
        if not task or task.type != TaskType.PROMPT_EXECUTION:
            return {}

        if not task.llm_query_id:
            return {}

        llm_query = self.task_repo.get_llm_query_by_id(task.llm_query_id)
        if not llm_query:
            return {}

        raw_response = llm_query.response if isinstance(llm_query.response, dict) else {}
        structured_output = raw_response.get("structured_output")
        if structured_output is None:
            structured_output = raw_response.get("additional_data")
        if structured_output is None:
            structured_output = raw_response.get("aditional_data")
        return {
            "query_id": llm_query.id,
            "answer": llm_query.output,
            "stats": llm_query.stats or {},
            "valid_response": bool(llm_query.valid_response),
            "structured_output": structured_output,
        }
