# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
import os


class TestApp:

    def setup_method(self):
        """Configurar los mocks necesarios"""
        # Verificar que la variable está disponible antes de continuar
        assert os.environ.get('DATABASE_URI') == 'sqlite:///:memory:', \
            "DATABASE_URI no está configurado correctamente"

        # Configurar los mocks
        self.patches = [
            patch('app.load_dotenv', return_value=True),  # Prevenir que load_dotenv sobreescriba las variables
            patch('app.redis.Redis', return_value=MagicMock()),
            patch('app.DatabaseManager', autospec=True),
            patch('app.register_routes'),
            patch('app.FlaskInjector'),
            patch('app.Bcrypt')
        ]

        # Iniciar todos los patches
        self.mocks = [p.start() for p in self.patches]

        # Importar e inicializar la app después de los patches
        from app import create_app
        self.app = create_app()

    def teardown_method(self):
        patch.stopall()

    def test_database_manager_initialization(self):
        """Verificar que DatabaseManager se inicializa con el URI correcto"""
        db_manager_mock = self.mocks[2]  # El índice corresponde al orden en self.patches
        db_manager_mock.assert_called_once_with('sqlite:///:memory:')

        # Verificar que se llamó create_all()
        db_instance = db_manager_mock.return_value
        db_instance.create_all.assert_called_once()

    def test_app_creation(self):
        """Verificar la creación básica de la aplicación"""
        assert isinstance(self.app, Flask)

    def test_app_configuration(self):
        """Verificar la configuración de la aplicación"""
        assert self.app.config['SESSION_TYPE'] == 'redis'
        assert self.app.config['SESSION_PERMANENT'] is False
        assert self.app.config['SESSION_USE_SIGNER'] is True

    def test_redis_initialization(self):
        """Verificar la inicialización de Redis"""
        redis_mock = self.mocks[1]  # El índice corresponde al orden en self.patches
        redis_mock.assert_called_once()

    def test_routes_registration(self):
        """Verificar el registro de rutas"""
        routes_mock = self.mocks[3]  # El índice corresponde al orden en self.patches
        routes_mock.assert_called_once_with(self.app)

    def test_flask_injector_initialization(self):
        """Verificar la inicialización de Flask-Injector"""
        injector_mock = self.mocks[4]  # El índice corresponde al orden en self.patches
        injector_mock.assert_called_once()
