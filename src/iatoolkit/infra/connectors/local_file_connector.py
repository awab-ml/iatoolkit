# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import os
from iatoolkit.infra.connectors.file_connector import FileConnector
from typing import List
from iatoolkit.common.exceptions import IAToolkitException


class LocalFileConnector(FileConnector):
    def __init__(self, directory: str):
        local_root = os.getenv("ROOT_DIR_LOCAL_FILES", '')
        self.directory = os.path.join(local_root, directory)

    def list_files(self) -> List[dict]:
        """
        Estándar: Lista todos los archivos como diccionarios con claves 'path', 'name' y 'metadata'.
        """
        try:
            files = [
                os.path.join(self.directory, f)
                for f in os.listdir(self.directory)
                if os.path.isfile(os.path.join(self.directory, f))
            ]

            return [
                {
                    "path": file,  # Ruta completa al archivo local
                    "name": os.path.basename(file),  # Nombre del archivo
                    "metadata": {"size": os.path.getsize(file), "last_modified": os.path.getmtime(file)}
                }
                for file in files
            ]
        except Exception as e:
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                               f"Error procesando el directorio {self.directory}: {e}")

    def get_file_content(self, file_path: str) -> bytes:
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                               f"Error leyendo el archivo {file_path}: {e}")
