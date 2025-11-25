# src/tests/views/test_index_view.py

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch

from iatoolkit.views.index_view import IndexView
from iatoolkit.common.util import Utility


class TestIndexView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.testing = True
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y los mocks antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.utility = MagicMock(spec=Utility)

        # Registrar la vista index (landing genérica, sin company)
        view = IndexView.as_view("index", util=self.utility)
        self.app.add_url_rule("/", view_func=view, methods=["GET"])

    @pytest.mark.parametrize("resolved_template", ["index_es.html", "index_en.html"])
    @patch('iatoolkit.views.index_view.render_template')
    def test_index_view_renders_language_template(self, mock_render_template, resolved_template):
        """Valida que la vista resuelve y renderiza el template correcto según el idioma."""
        self.utility.get_template_by_language.return_value = resolved_template
        mock_render_template.return_value = f"rendered:{resolved_template}"

        resp = self.client.get("/")

        assert resp.status_code == 200
        self.utility.get_template_by_language.assert_called_once_with("index")
        mock_render_template.assert_called_once_with(resolved_template)