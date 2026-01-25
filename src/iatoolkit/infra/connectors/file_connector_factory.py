# ... existing code ...
import os
from typing import Dict
from iatoolkit.infra.connectors.file_connector import FileConnector
from iatoolkit.infra.connectors.local_file_connector import LocalFileConnector
from iatoolkit.infra.connectors.s3_connector import S3Connector
from iatoolkit.infra.connectors.google_cloud_storage_connector import GoogleCloudStorageConnector
from iatoolkit.infra.connectors.google_drive_connector import GoogleDriveConnector

class FileConnectorFactory:
    @staticmethod
    def create(config: Dict) -> FileConnector:
        """
        Crea un conector basado en un diccionario de configuración.
        Permite pasar credenciales explícitas en 'auth' o 'service_account_path',
        o dejar que el conector use sus defaults.
        """
        connector_type = config.get('type')

        if connector_type == 'local':
            return LocalFileConnector(config['path'])

        elif connector_type == 's3':
            # Resolve credentials in a single place for the whole toolkit.
            auth = config.get('auth', {})
            if not auth:
                auth_env = config.get('auth_env') or {}
                a_env = auth_env.get('aws_access_key_id_env')
                s_env = auth_env.get('aws_secret_access_key_env')
                r_env = auth_env.get('aws_region_env')

                access_key = os.getenv(a_env) if a_env else None
                secret_key = os.getenv(s_env) if s_env else None
                region = os.getenv(r_env) if r_env else None

                if access_key and secret_key:
                    auth = {
                        'aws_access_key_id': access_key,
                        'aws_secret_access_key': secret_key,
                        'region_name': region or os.getenv('AWS_REGION', 'us-east-1')
                    }
                else:
                    # Fall back to the standard AWS_* env vars (or empty to enable default chain).
                    auth = {
                        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                        'region_name': os.getenv('AWS_REGION', 'us-east-1')
                    }

            return S3Connector(
                bucket=config['bucket'],
                prefix=config.get('prefix', ''),
                folder=config.get('folder', ''),
                auth=auth
            )

        elif connector_type == 'gdrive':
            return GoogleDriveConnector(
                folder_id=config['folder_id'],
                service_account_path=config.get('service_account', 'service_account.json')
            )

        elif connector_type in ['gcs', 'google_cloud_storage']:
            return GoogleCloudStorageConnector(
                bucket_name=config['bucket'],
                service_account_path=config.get('service_account_path', 'service_account.json')
            )

        else:
            raise ValueError(f"Unknown connector type: {connector_type}")
