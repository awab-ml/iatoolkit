# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import logging
from typing import List
from iatoolkit.common.exceptions import IAToolkitException
from flask import request
from injector import inject
import os
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, date
from decimal import Decimal
import yaml
from cryptography.fernet import Fernet
import base64



class Utility:
    @inject
    def __init__(self):
        self.encryption_key = os.getenv('FERNET_KEY')

    def render_prompt_from_template(self,
                                    template_pathname: str,
                                    client_data: dict = {},
                                    **kwargs) -> str:

        try:
            # Normalizar la ruta para que funcione en cualquier SO
            template_pathname = os.path.abspath(template_pathname)
            template_dir = os.path.dirname(template_pathname)
            template_file = os.path.basename(template_pathname)

            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template(template_file)

            # add all the keys in client_data to kwargs
            kwargs.update(client_data)

            # render my dynamic prompt
            prompt = template.render(**kwargs)
            return prompt
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.TEMPLATE_ERROR,
                               f'No se pudo renderizar el template: {template_pathname}, error: {str(e)}') from e

    def render_prompt_from_string(self,
                                  template_string: str,
                                  searchpath: str | list[str] = None,
                                  client_data: dict = {},
                                  **kwargs) -> str:
        """
        Renderiza un prompt a partir de un string de plantilla Jinja2.

        :param template_string: El string que contiene la plantilla Jinja2.
        :param searchpath: Una ruta o lista de rutas a directorios para buscar plantillas incluidas (con {% include %}).
        :param query: El query principal a pasar a la plantilla.
        :param client_data: Un diccionario con datos adicionales para la plantilla.
        :param kwargs: Argumentos adicionales para la plantilla.
        :return: El prompt renderizado como un string.
        """
        try:
            # Si se proporciona un searchpath, se usa un FileSystemLoader para permitir includes.
            if searchpath:
                loader = FileSystemLoader(searchpath)
            else:
                loader = None  # Sin loader, no se pueden incluir plantillas desde archivos.

            env = Environment(loader=loader)
            template = env.from_string(template_string)

            kwargs.update(client_data)

            prompt = template.render(**kwargs)
            return prompt
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.TEMPLATE_ERROR,
                               f'No se pudo renderizar el template desde el string, error: {str(e)}') from e


    def get_company_template(self, company_short_name: str, template_name: str) -> str:
        # 1. get the path to the company specific template
        template_path = os.path.join(os.getcwd(), f'companies/{company_short_name}/templates/{template_name}')
        if not os.path.exists(template_path):
            return None

        # 2. read the file
        try:
            with open(template_path, 'r') as f:
                template_string = f.read()

            return template_string
        except Exception as e:
            logging.exception(e)
            return None

    def get_template_by_language(self, template_name: str, default_langueage: str = 'en') -> str:
        # english is default
        lang = request.args.get("lang", default_langueage)
        return f'{template_name}_{lang}.html'

    def serialize(self, obj):
        if isinstance(obj, datetime) or isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        else:
            raise TypeError(f"Type {type(obj)} not serializable")

    def encrypt_key(self, key: str) -> str:
        if not self.encryption_key:
            raise IAToolkitException(IAToolkitException.ErrorType.CRYPT_ERROR,
                               'No se pudo obtener variable de ambiente para encriptar')

        if not key:
            raise IAToolkitException(IAToolkitException.ErrorType.CRYPT_ERROR,
                               'falta la clave a encriptar')
        try:
            cipher_suite = Fernet(self.encryption_key.encode('utf-8'))

            encrypted_key = cipher_suite.encrypt(key.encode('utf-8'))
            encrypted_key_str = base64.urlsafe_b64encode(encrypted_key).decode('utf-8')

            return encrypted_key_str
        except Exception as e:
            raise IAToolkitException(IAToolkitException.ErrorType.CRYPT_ERROR,
                               f'No se pudo encriptar la clave: {str(e)}') from e

    def decrypt_key(self, encrypted_key: str) -> str:
        if not self.encryption_key:
            raise IAToolkitException(IAToolkitException.ErrorType.CRYPT_ERROR,
                               'No se pudo obtener variable de ambiente para desencriptar')
        if not encrypted_key:
            raise IAToolkitException(IAToolkitException.ErrorType.CRYPT_ERROR,
                               'falta la clave a encriptar')

        try:
            # transform to bytes first
            encrypted_data_from_storage_bytes = base64.urlsafe_b64decode(encrypted_key.encode('utf-8'))

            cipher_suite = Fernet(self.encryption_key.encode('utf-8'))
            decrypted_key_bytes = cipher_suite.decrypt(encrypted_data_from_storage_bytes)
            return decrypted_key_bytes.decode('utf-8')
        except Exception as e:
            raise IAToolkitException(IAToolkitException.ErrorType.CRYPT_ERROR,
                               f'No se pudo desencriptar la clave: {str(e)}') from e

    def load_schema_from_yaml(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            schema = yaml.safe_load(f)
        return schema

    def validate_schema_structure(self, schema: dict) -> list[str]:
        """
        Valida que el diccionario cumpla con el formato oficial:
        { table_name: { columns: { col_name: { type: ..., properties: ... } } } }
        """
        errors = []
        if not schema or not isinstance(schema, dict):
            return ["El esquema está vacío o no es válido."]

        if len(schema) != 1:
            return ["El esquema debe tener exactamente una clave raíz (el nombre de la tabla)."]

        root_key = list(schema.keys())[0]
        root_data = schema[root_key]

        if not isinstance(root_data, dict):
            return [f"El contenido de '{root_key}' debe ser un diccionario."]

            # Validar sección 'columns'
        columns = table_content.get('columns')
        if not columns:
            if not table_content.get('properties') and not table_content.get('fields'):
                errors.append(f"Falta la sección 'columns' dentro de la tabla '{table_name}'.")

        # CAMBIO: Permitir listas pero reportar como advertencia no bloqueante si quisieras,
        # o simplemente rechazarlo si quieres ser estricto.
        # Dado que admin_schema_view ya lo convierte, aquí podríamos ser estrictos para
        # indicar que el ARCHIVO físico está mal, aunque el sistema lo tolere.
        elif isinstance(columns, list):
            # Retornamos esto como un error de formato, pero el View sabrá manejarlo.
            return [f"⚠️ Legacy Format: 'columns' es una lista en '{table_name}'. Se convertirá automáticamente."]

        elif not isinstance(columns, dict):
            errors.append(f"La sección 'columns' de '{table_name}' debe ser un diccionario.")

        return errors

    def generate_schema_table(self, schema: dict) -> str:
        """
        Genera documentación Markdown estandarizada soportando 'columns'.
        """
        if not schema or not isinstance(schema, dict):
            return ""

        # Detección de raíz
        keys = list(schema.keys())
        if not keys: return ""

        root_name = keys[0]
        root_data = schema[root_name]

        # Descripción de la tabla
        root_description = root_data.get('description', '')

        # Extracción inteligente de columnas/propiedades
        # Prioridad: columns > properties > fields
        properties = root_data.get('columns', root_data.get('properties', root_data.get('fields', {})))

        output = [f"### Objeto: `{root_name}`"]

        if root_description:
            # Limpiar saltos de línea para visualización limpia
            clean_desc = root_description.replace('\n', ' ').strip()
            output.append(f"\n{clean_desc}")

        if properties:
            output.append("\n**Estructura de Datos:**")
            # Usamos indent_level 0 para las columnas principales
            output.append(self._format_json_schema(properties, 0))
        else:
            output.append("\n_Sin definición de estructura._")

        return "\n".join(output)

    def _format_json_schema(self, properties: dict, indent_level: int) -> str:
        output = []
        indent_str = '  ' * indent_level

        if not isinstance(properties, dict):
            return ""

        for name, details in properties.items():
            if not isinstance(details, dict): continue

            description = details.get('description', '')
            data_type = details.get('type', 'any')

            # NORMALIZACIÓN VISUAL: jsonb -> object
            if data_type and data_type.lower() == 'jsonb':
                data_type = 'object'

            line = f"{indent_str}- **`{name}`**"
            if data_type:
                line += f" ({data_type})"
            if description:
                clean_desc = description.replace('\n', ' ').strip()
                line += f": {clean_desc}"

            output.append(line)

            # Recursividad: buscar hijos en 'properties', 'fields' o 'columns'
            children = details.get('properties', details.get('fields'))

            # Caso Array (items -> properties)
            if not children and details.get('items'):
                items = details['items']
                if isinstance(items, dict):
                    if items.get('description'):
                        output.append(f"{indent_str}  _Items: {items['description']}_")
                    children = items.get('properties', items.get('fields'))

            if children:
                output.append(self._format_json_schema(children, indent_level + 1))

        return "\n".join(output)

    def load_yaml_from_string(self, yaml_content: str) -> dict:
        """
        Parses a YAML string into a dictionary securely.
        """
        try:
            if not yaml_content:
                return {}

            # Normalizar tabulaciones que rompen YAML
            yaml_content = yaml_content.replace('\t', '  ')

            loaded = yaml.safe_load(yaml_content)
            # Asegurar que siempre retornamos un dict, incluso si el YAML es una lista o escalar
            return loaded if isinstance(loaded, dict) else {}
        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML string: {e}")
            return {}

    def dump_yaml_to_string(self, config: dict) -> str:
        """
        Dumps a dictionary into a YAML formatted string.
        It uses default flow style False to ensure block format (readable YAML).
        """
        try:
            # default_flow_style=False ensures lists and dicts are expanded (not inline like JSON)
            # allow_unicode=True ensures characters like accents are preserved
            return yaml.safe_dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except yaml.YAMLError as e:
            logging.error(f"Error dumping YAML to string: {e}")
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                                     f"Failed to generate YAML: {e}")

    def generate_context_for_schema(self, entity_name: str, schema_file: str = None, schema: dict = {}) -> str:
        if not schema_file and not schema:
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                               f'No se pudo obtener schema de la entidad: {entity_name}')

        try:
            if schema_file:
                schema = self.load_schema_from_yaml(schema_file)
            table_schema = self.generate_schema_table(schema)
            return table_schema
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                               f'No se pudo leer el schema de la entidad: {entity_name}') from e


    def generate_schema_table(self, schema: dict) -> str:
        """
        Genera documentación Markdown estandarizada soportando 'columns' como lista o dict.
        """
        if not schema or not isinstance(schema, dict):
            return ""

        # Detección de raíz (Wrapper) vs Estructura Plana
        keys = list(schema.keys())
        if not keys: return ""

        # Heurística: Si hay múltiples claves y no parecen metadatos de JSON Schema (type, properties),
        # asumimos que es una definición plana de campos (ej: {"field1":..., "field2":...})
        if len(keys) > 1 and 'type' not in keys and 'properties' not in keys:
            return self._format_json_schema(schema, 0)

        root_name = keys[0]
        root_data = schema[root_name]

        # Si el root_data no es dict, quizás el schema es plano (ej: lista de columnas directa)
        # Pero asumimos el formato estándar: { table: { ... } }
        if not isinstance(root_data, dict):
            # Fallback para estructuras extrañas o planas
            return self._format_json_schema(schema, 0)

        # Heurística 2: Si es una sola clave pero el contenido parece un campo simple (tiene type y no estructura de hijos)
        # ej: {"field1": {"type": "string"}} -> debe renderizarse como campo, no como tabla.
        has_structure = any(k in root_data for k in ['columns', 'properties', 'fields'])
        if 'type' in root_data and not has_structure:
            return self._format_json_schema(schema, 0)

        description = root_data.get('description', '')

        # Extracción inteligente: columns > properties > fields
        props_source = root_data.get('columns', root_data.get('properties', root_data.get('fields')))

        output = [f"### Objeto: `{root_name}`"]

        if description:
            output.append(f"\n{description.strip()}")

        if props_source:
            output.append("\n**Estructura de Datos:**")
            output.append(self._format_json_schema(props_source, 0))
        else:
            output.append("\n_Sin definición de estructura._")

        return "\n".join(output)

    def _format_json_schema(self, properties: dict | list, indent_level: int) -> str:
        output = []
        indent_str = '  ' * indent_level

        if not properties:
            return ""

        # Normalizar entrada: Lista vs Dict
        items_iterable = []

        if isinstance(properties, dict):
            items_iterable = properties.items()
        elif isinstance(properties, list):
            # Adaptar lista [{'name': 'x', ...}] a tuplas ('x', {...})
            for item in properties:
                if isinstance(item, dict):
                    name = item.get('name', 'unknown')
                    items_iterable.append((name, item))

        for name, details in items_iterable:
            if not isinstance(details, dict): continue

            description = details.get('description', '')
            data_type = details.get('type', 'any')

            # Normalización visual
            if data_type and str(data_type).lower() == 'jsonb':
                data_type = 'object'

            line = f"{indent_str}- **`{name}`**"
            if data_type:
                line += f" ({data_type})"
            if description:
                clean_desc = description.replace('\n', ' ').strip()
                line += f": {clean_desc}"

            output.append(line)

            # Recursividad: buscar hijos
            children = details.get('properties', details.get('fields', details.get('columns')))

            # Caso Array
            if not children and details.get('items'):
                items = details['items']
                if isinstance(items, dict):
                    if items.get('description'):
                        output.append(f"{indent_str}  _Items: {items['description']}_")
                    children = items.get('properties', items.get('fields'))

            if children:
                output.append(self._format_json_schema(children, indent_level + 1))

        return "\n".join(output)

    def load_markdown_context(self, filepath: str) -> str:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    @classmethod
    def _get_verifier(self, rut: int):
        value = 11 - sum([int(a) * int(b) for a, b in zip(str(rut).zfill(8), '32765432')]) % 11
        return {10: 'K', 11: '0'}.get(value, str(value))

    def validate_rut(self, rut_str):
        if not rut_str or not isinstance(rut_str, str):
            return False

        rut_str = rut_str.strip().replace('.', '').upper()
        parts = rut_str.split('-')
        if not len(parts) == 2:
            return False

        try:
            rut = int(parts[0])
        except ValueError:
            return False

        if rut < 1000000:
            return False

        if not len(parts[1]) == 1:
            return False

        digit = parts[1].upper()
        return digit == self._get_verifier(rut)

    def get_files_by_extension(self, directory: str, extension: str, return_extension: bool = False) -> List[str]:
        try:
            # Normalizar la extensión (agregar punto si no lo tiene)
            if not extension.startswith('.'):
                extension = '.' + extension

            # Verificar que el directorio existe
            if not os.path.exists(directory):
                raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                                   f'El directorio no existe: {directory}')

            if not os.path.isdir(directory):
                raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                                   f'La ruta no es un directorio: {directory}')

            # Buscar archivos con la extensión especificada
            files = []
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path) and filename.endswith(extension):
                    if return_extension:
                        files.append(filename)
                    else:
                        name_without_extension = os.path.splitext(filename)[0]
                        files.append(name_without_extension)

            return sorted(files)  # Retornar lista ordenada alfabéticamente

        except IAToolkitException:
            raise
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.FILE_IO_ERROR,
                               f'Error al buscar archivos en el directorio {directory}: {str(e)}') from e
