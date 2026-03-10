# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

# database_manager.py
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import make_url
from iatoolkit.repositories.models import Base, ORM_SCHEMA
from injector import inject
from pgvector.psycopg2 import register_vector
from iatoolkit.common.interfaces.database_provider import DatabaseProvider
import logging


class DatabaseManager(DatabaseProvider):
    _POSTGRES_BOOTSTRAP_PATCHES = (
        (
            "phase2_collection_parser_provider",
            "ALTER TABLE {schema}.iat_collection_types ADD COLUMN IF NOT EXISTS parser_provider VARCHAR",
        ),
        (
            "phase2_remove_document_content",
            "ALTER TABLE {schema}.iat_documents DROP COLUMN IF EXISTS content",
        ),
        (
            "phase3_http_tool_execution_config",
            "ALTER TABLE {schema}.iat_tools ADD COLUMN IF NOT EXISTS execution_config JSONB",
        ),
        (
            "phase4_company_is_active",
            "ALTER TABLE {schema}.iat_companies ADD COLUMN IF NOT EXISTS is_active BOOLEAN",
        ),
        (
            "phase4_company_runtime_mode",
            "ALTER TABLE {schema}.iat_companies ADD COLUMN IF NOT EXISTS runtime_mode VARCHAR(32)",
        ),
        (
            "phase4_company_runtime_backfill",
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = '{schema}'
                      AND table_name = 'iat_company_deployments'
                ) THEN
                    UPDATE {schema}.iat_companies c
                    SET
                        is_active = COALESCE(d.is_active, c.is_active),
                        runtime_mode = COALESCE(NULLIF(LOWER(TRIM(CAST(d.runtime_mode AS TEXT))), ''), c.runtime_mode)
                    FROM {schema}.iat_company_deployments d
                    WHERE d.company_id = c.id;
                END IF;
            END$$
            """,
        ),
        (
            "phase4_company_is_active_defaults",
            "UPDATE {schema}.iat_companies SET is_active = COALESCE(is_active, TRUE)",
        ),
        (
            "phase4_company_runtime_mode_defaults",
            "UPDATE {schema}.iat_companies SET runtime_mode = COALESCE(NULLIF(LOWER(TRIM(runtime_mode)), ''), 'static')",
        ),
        (
            "phase4_company_is_active_not_null",
            "ALTER TABLE {schema}.iat_companies ALTER COLUMN is_active SET NOT NULL",
        ),
        (
            "phase4_company_is_active_default",
            "ALTER TABLE {schema}.iat_companies ALTER COLUMN is_active SET DEFAULT TRUE",
        ),
        (
            "phase4_company_runtime_mode_not_null",
            "ALTER TABLE {schema}.iat_companies ALTER COLUMN runtime_mode SET NOT NULL",
        ),
        (
            "phase4_company_runtime_mode_default",
            "ALTER TABLE {schema}.iat_companies ALTER COLUMN runtime_mode SET DEFAULT 'static'",
        ),
        (
            "phase4_company_is_active_index",
            "CREATE INDEX IF NOT EXISTS idx_iat_companies_is_active ON {schema}.iat_companies(is_active)",
        ),
        (
            "phase4_company_runtime_mode_index",
            "CREATE INDEX IF NOT EXISTS idx_iat_companies_runtime_mode ON {schema}.iat_companies(runtime_mode)",
        ),
        (
            "phase4_drop_company_class_ref",
            "ALTER TABLE {schema}.iat_companies DROP COLUMN IF EXISTS company_class_ref",
        ),
        (
            "phase5_prompt_output_schema",
            "ALTER TABLE {schema}.iat_prompt ADD COLUMN IF NOT EXISTS output_schema JSONB",
        ),
        (
            "phase5_prompt_output_schema_yaml",
            "ALTER TABLE {schema}.iat_prompt ADD COLUMN IF NOT EXISTS output_schema_yaml TEXT",
        ),
        (
            "phase5_prompt_output_schema_mode",
            "ALTER TABLE {schema}.iat_prompt ADD COLUMN IF NOT EXISTS output_schema_mode VARCHAR(32) NOT NULL DEFAULT 'best_effort'",
        ),
        (
            "phase5_prompt_output_response_mode",
            "ALTER TABLE {schema}.iat_prompt ADD COLUMN IF NOT EXISTS output_response_mode VARCHAR(32) NOT NULL DEFAULT 'chat_compatible'",
        ),
        (
            "phase6_prompt_attachment_mode",
            "ALTER TABLE {schema}.iat_prompt ADD COLUMN IF NOT EXISTS attachment_mode VARCHAR(32) NOT NULL DEFAULT 'extracted_only'",
        ),
        (
            "phase6_prompt_attachment_fallback",
            "ALTER TABLE {schema}.iat_prompt ADD COLUMN IF NOT EXISTS attachment_fallback VARCHAR(32) NOT NULL DEFAULT 'extract'",
        ),
        (
            "phase7_sql_sources_table",
            """
            CREATE TABLE IF NOT EXISTS {schema}.iat_sql_sources (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES {schema}.iat_companies(id) ON DELETE CASCADE,
                database VARCHAR(255) NOT NULL,
                connection_type VARCHAR(32) NOT NULL DEFAULT 'direct',
                connection_string_env VARCHAR(255),
                schema VARCHAR(255) NOT NULL DEFAULT 'public',
                description TEXT,
                bridge_id VARCHAR(255),
                source VARCHAR(16) NOT NULL DEFAULT 'YAML',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                CONSTRAINT uix_company_sql_source_database UNIQUE (company_id, database)
            )
            """,
        ),
        (
            "phase7_sql_sources_company_index",
            "CREATE INDEX IF NOT EXISTS idx_iat_sql_sources_company ON {schema}.iat_sql_sources(company_id)",
        ),
        (
            "phase7_sql_sources_active_index",
            "CREATE INDEX IF NOT EXISTS idx_iat_sql_sources_active ON {schema}.iat_sql_sources(is_active)",
        ),
        (
            "phase7_sql_sources_source_index",
            "CREATE INDEX IF NOT EXISTS idx_iat_sql_sources_source ON {schema}.iat_sql_sources(source)",
        ),
    )

    @inject
    def __init__(self,
                 database_url: str,
                 schema: str = 'public',
                 register_pgvector: bool = True):
        """
        Inicializa el gestor de la base de datos.
        :param database_url: URL de la base de datos.
        :param schema: Esquema por defecto para la conexión (search_path).
        :param echo: Si True, habilita logs de SQL.
        """

        self.schema = schema

        # FIX HEROKU: replace postgres:// by postgresql:// for compatibility with SQLAlchemy 1.4+
        if database_url and database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        self.url = make_url(database_url)

        if database_url.startswith('sqlite'):
            raw_engine = create_engine(database_url, echo=False)
        else:
            raw_engine = create_engine(
                database_url,
                echo=False,
                pool_size=10,  # per worker
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
                pool_use_lifo=True,
                connect_args={
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                    "connect_timeout": 10,
                },
                future=True,
            )
        translated_schema = None if self.url.get_backend_name() == 'sqlite' else self.schema
        self._engine = raw_engine.execution_options(
            schema_translate_map={ORM_SCHEMA: translated_schema}
        )
        self.SessionFactory = sessionmaker(bind=self._engine,
                                           autoflush=False,
                                           autocommit=False,
                                           expire_on_commit=False)
        self.scoped_session = scoped_session(self.SessionFactory)

        # Register pgvector for each new connection
        backend = self.url.get_backend_name()
        if backend == 'postgresql' or backend == 'postgres':
            if register_pgvector:
                event.listen(raw_engine, 'connect', self.on_connect)

            # if there is a schema, configure the search_path for each connection
            if self.schema:
                event.listen(raw_engine, 'checkout', self.set_search_path)

    def set_search_path(self, dbapi_connection, connection_record, connection_proxy):
        # Configure the search_path for this connection
        cursor = dbapi_connection.cursor()

        # The defined schema is first, and then public by default
        try:
            cursor.execute(f"SET search_path TO {self.schema}, public")
            cursor.close()

            # commit for persist the change in the session
            dbapi_connection.commit()
        except Exception:
            # if failed, rollback to avoid invalidating the connection
            dbapi_connection.rollback()

    @staticmethod
    def on_connect(dbapi_connection, connection_record):
        """
        Esta función se ejecuta cada vez que se establece una conexión.
        dbapi_connection es la conexión psycopg2 real.
        """
        register_vector(dbapi_connection)

    def get_session(self):
        # Return the scoped_session proxy itself so each operation resolves
        # against the current request/thread-bound Session.
        return self.scoped_session

    def get_connection(self):
        return self._engine.connect()

    def create_all(self):
        # if there is a schema defined, make sure it exists before creating tables
        backend = self.url.get_backend_name()
        if self.schema and (backend == 'postgresql' or backend == 'postgres'):
            with self._engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))

        Base.metadata.create_all(self._engine)
        applied_patches = self._apply_bootstrap_patches()
        if applied_patches:
            logging.info(
                "Ensured PostgreSQL bootstrap schema compatibility (%s statements).",
                len(applied_patches),
            )

    def _apply_bootstrap_patches(self) -> list[str]:
        backend = self.url.get_backend_name()
        if backend not in ('postgresql', 'postgres'):
            return []

        applied = []
        with self._engine.begin() as conn:
            if self.schema:
                conn.execute(text(f"SET search_path TO {self.schema}, public"))

            for patch_name, statement in self._POSTGRES_BOOTSTRAP_PATCHES:
                conn.execute(text(statement.format(schema=self.schema)))
                applied.append(patch_name)

        return applied

    def drop_all(self):
        Base.metadata.drop_all(self._engine)

    def remove_session(self):
        self.scoped_session.remove()

    # -- execution methods ----

    def execute_query(self, query: str, commit: bool = False) -> list[dict] | dict:
        """
        Implementation for Direct SQLAlchemy connection.
        """
        session = self.get_session()
        if self.schema:
            session.execute(text(f"SET search_path TO {self.schema}"))

        result = session.execute(text(query))
        if commit:
            session.commit()

        if result.returns_rows:
            # Convert SQLAlchemy rows to list of dicts immediately
            cols = result.keys()
            return [dict(zip(cols, row)) for row in result.fetchall()]

        return {'rowcount': result.rowcount}

    def commit(self):
        self.get_session().commit()

    def rollback(self):
        self.get_session().rollback()

    # -- schema methods ----
    def get_database_structure(self) -> dict:
        inspector = inspect(self._engine)
        structure = {}
        for table in inspector.get_table_names(schema=self.schema):
            columns_data = []

            # get columns
            try:
                columns = inspector.get_columns(table, schema=self.schema)
                # Obtener PKs para marcarlas
                pks = inspector.get_pk_constraint(table, schema=self.schema).get('constrained_columns', [])

                for col in columns:
                    columns_data.append({
                        "name": col['name'],
                        "type": str(col['type']),
                        "nullable": col.get('nullable', True),
                        "pk": col['name'] in pks
                    })
            except Exception as e:
                logging.warning(f"Could not inspect columns for table {table}: {e}")

            structure[table] = {
                "columns": columns_data
            }

        return structure
