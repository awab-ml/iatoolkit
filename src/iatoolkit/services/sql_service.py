# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.database_manager import DatabaseManager
from iatoolkit.common.util import Utility
from iatoolkit.services.i18n_service import I18nService
from iatoolkit.common.exceptions import IAToolkitException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from injector import inject, singleton
import json
import logging


@singleton
class SqlService:
    """
    Manages database connections and executes SQL statements.
    It maintains a cache of named DatabaseManager instances to avoid reconnecting.
    """

    @inject
    def __init__(self,
                 util: Utility,
                 i18n_service: I18nService):
        self.util = util
        self.i18n_service = i18n_service

        # Cache for database connections
        self._db_connections: dict[str, DatabaseManager] = {}

    def register_database(self, db_uri: str, db_name: str, schema: str | None = None):
        """
        Creates and caches a DatabaseManager instance for a given database name and URI.
        If a database with the same name is already registered, it does nothing.
        """
        if db_name in self._db_connections:
            return

        logging.info(f"Registering and creating connection for database: '{db_name}' (schema: {schema})")

        # create the database connection and save it on the cache
        db_manager = DatabaseManager(db_uri, schema=schema, register_pgvector=False)
        self._db_connections[db_name] = db_manager

    def get_database_manager(self, db_name: str) -> DatabaseManager:
        """
        Retrieves a registered DatabaseManager instance from the cache.
        """
        try:
            return self._db_connections[db_name]
        except KeyError:
            logging.error(f"Attempted to access unregistered database: '{db_name}'")
            raise IAToolkitException(
                IAToolkitException.ErrorType.DATABASE_ERROR,
                f"Database '{db_name}' is not registered with the SqlService."
            )

    def exec_sql(self, company_short_name: str,
                 database: str,
                 query: str,
                 format: str = 'json',
                 commit: bool = False):
        """
        Executes a raw SQL statement against a registered database.

        Args:
            company_short_name: The company identifier (for logging/context).
            database: The logical name of the database to query.
            query: The SQL statement to execute.
            format: The output format ('json' or 'dict'). Only relevant for SELECT queries.
            commit: Whether to commit the transaction immediately after execution.
                    Use True for INSERT/UPDATE/DELETE statements.

        Returns:
            - A JSON string or list of dicts for SELECT queries.
            - A dictionary {'rowcount': N} for non-returning statements (INSERT/UPDATE) if not using RETURNING.
        """
        try:
            # 1. Get the database manager from the cache
            db_manager = self.get_database_manager(database)
            session = db_manager.get_session()

            # 2. Execute the SQL statement
            result = session.execute(text(query))

            # 3. Handle Commit
            if commit:
                session.commit()

            # 4. Process Results
            # Check if the query returns rows (e.g., SELECT or INSERT ... RETURNING)
            if result.returns_rows:
                cols = result.keys()
                rows_context = [dict(zip(cols, row)) for row in result.fetchall()]

                if format == 'dict':
                    return rows_context

                # serialize the result
                return json.dumps(rows_context, default=self.util.serialize)

            # For statements that don't return rows (standard UPDATE/DELETE)
            return {'rowcount': result.rowcount}

        except IAToolkitException:
            # Re-raise exceptions from get_database_manager to preserve the specific error
            raise
        except Exception as e:
            # Attempt to rollback if a session was active
            db_manager = self._db_connections.get(database)
            if db_manager:
                db_manager.get_session().rollback()

            error_message = str(e)
            if 'timed out' in str(e):
                error_message = self.i18n_service.t('errors.timeout')

            logging.error(f"Error executing SQL statement: {error_message}")
            raise IAToolkitException(IAToolkitException.ErrorType.DATABASE_ERROR,
                                     error_message) from e

    def commit(self, database: str):
        """
        Commits the current transaction for a registered database.
        Useful when multiple exec_sql calls are part of a single transaction.
        """

        # Get the database manager from the cache
        db_manager = self.get_database_manager(database)
        try:
            db_manager.get_session().commit()
        except SQLAlchemyError as db_error:
            db_manager.get_session().rollback()
            logging.error(f"Error de base de datos: {str(db_error)}")
            raise db_error
        except Exception as e:
            logging.error(f"error while commiting sql: '{str(e)}'")
            raise IAToolkitException(
                IAToolkitException.ErrorType.DATABASE_ERROR, str(e)
            )