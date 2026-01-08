# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import base64
import uuid
import logging
import mimetypes
import os
from injector import inject
from typing import Dict
from iatoolkit.infra.connectors.s3_connector import S3Connector
from iatoolkit.common.exceptions import IAToolkitException


class StorageService:
    """
    High level service for managing assets storage (images generated, attachments, etc).
    Provides abstraction for file decoding and naming.
    """

    @inject
    def __init__(self):
        self.connector = self._init_connector()

    def _init_connector(self) -> S3Connector:
        # We configure S3 directly using environment variables
        bucket = os.getenv("S3_BUCKET_NAME", "iatoolkit-assets")

        auth = {
            'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'region_name': os.getenv('AWS_REGION', 'us-east-1')
        }

        return S3Connector(
            bucket=bucket,
            prefix="",   # Empty prefix to allow full control over keys
            folder="",
            auth=auth
        )

    def store_generated_image(self, company_short_name: str, base64_data: str, mime_type: str) -> Dict[str, str]:
        """
        Guarda una imagen generada por LLM (Base64) en el storage.

        Returns:
            Dict con:
            - 'storage_key': La ruta interna (para guardar en BD)
            - 'url': La URL firmada (para devolver al frontend inmediatamente)
        """
        try:
            # 1. Decode Base64
            # Sometimes the string comes with header 'data:image/png;base64,...', clean it
            if "base64," in base64_data:
                base64_data = base64_data.split("base64,")[1]

            image_bytes = base64.b64decode(base64_data)

            # 2. Generate unique name
            ext = mimetypes.guess_extension(mime_type) or ".png"
            filename = f"{uuid.uuid4()}{ext}"

            # 3. Define folder structure: companies/{company}/generated/{filename}
            storage_key = f"companies/{company_short_name}/generated_images/{filename}"

            # 4. Upload
            self.connector.upload_file(
                file_path=storage_key,
                content=image_bytes,
                content_type=mime_type
            )

            logging.info(f"Generated image saved at: {storage_key}")

            # 5. Generate temporary URL
            url = self.connector.generate_presigned_url(storage_key)

            return {
                "storage_key": storage_key,
                "url": url
            }

        except Exception as e:
            error_msg = f"Error saving image to Storage: {str(e)}"
            logging.error(error_msg)
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR, error_msg)

    def get_public_url(self, storage_key: str) -> str:
        """Gets a fresh signed URL for an existing resource."""
        return self.connector.generate_presigned_url(storage_key)