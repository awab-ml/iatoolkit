import pytest
from flask import Flask
from unittest.mock import MagicMock

from iatoolkit.views.load_company_configuration_api_view import LoadCompanyConfigurationApiView
from iatoolkit.services.auth_service import AuthService
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.configuration_service import ConfigurationService


MOCK_COMPANY_SHORT_NAME = "sample_company"


class TestLoadCompanyConfigurationApiView:
    """
    Tests para LoadCompanyConfigurationApiView, siguiendo el estilo de TestInitContextApiView.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up de un entorno Flask y mocks antes de cada test."""
        self.app = Flask(__name__)
        self.app.testing = True
        self.client = self.app.test_client()

        # Mocks para los servicios inyectados
        self.mock_auth_service = MagicMock(spec=AuthService)
        self.mock_profile_service = MagicMock(spec=ProfileService)
        self.mock_config_service = MagicMock(spec=ConfigurationService)

        # Vista registrada con dependencias mockeadas
        view_func = LoadCompanyConfigurationApiView.as_view(
            "load_company_config_api",
            configuration_service=self.mock_config_service,
            profile_service=self.mock_profile_service,
            auth_service=self.mock_auth_service,
        )
        self.app.add_url_rule(
            "/api/<company_short_name>/config",
            view_func=view_func,
            methods=["GET"],
        )

        # Valor por defecto: autenticación OK
        self.mock_auth_service.verify.return_value = {
            "success": True,
            "company_short_name": MOCK_COMPANY_SHORT_NAME,
            "user_identifier": "user@test.com",
        }

    def test_get_fails_if_auth_fails(self):
        """Debe devolver status_code de auth (401) si falla la autenticación."""
        self.mock_auth_service.verify.return_value = {
            "success": False,
            "error_message": "Invalid API Key",
            "status_code": 401,
        }

        resp = self.client.get(f"/api/{MOCK_COMPANY_SHORT_NAME}/config")

        assert resp.status_code == 401
        data = resp.get_json()
        assert data["success"] is False
        assert data["error_message"] == "Invalid API Key"
        self.mock_profile_service.get_company_by_short_name.assert_not_called()
        self.mock_config_service.load_configuration.assert_not_called()

    def test_get_company_not_found_returns_404(self):
        """Debe devolver 404 si la compañía no existe."""
        self.mock_profile_service.get_company_by_short_name.return_value = None

        resp = self.client.get(f"/api/{MOCK_COMPANY_SHORT_NAME}/config")

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "company not found."
        self.mock_config_service.load_configuration.assert_not_called()

    def test_get_success_without_errors(self):
        """Cuando load_configuration no devuelve errores, debe responder 200."""
        # Arrange
        mock_company = MagicMock()
        self.mock_profile_service.get_company_by_short_name.return_value = mock_company

        config = {"id": MOCK_COMPANY_SHORT_NAME, "name": "Sample Company", "company": mock_company}
        errors = []
        self.mock_config_service.load_configuration.return_value = (config, errors)

        # Act
        resp = self.client.get(f"/api/{MOCK_COMPANY_SHORT_NAME}/config")

        # Assert
        assert resp.status_code == 200
        data = resp.get_json()
        assert "config" in data
        assert data["config"]["id"] == MOCK_COMPANY_SHORT_NAME
        # la vista elimina la clave 'company' del config
        assert "company" not in data["config"]
        assert data["errors"] == [[]]
        self.mock_config_service.load_configuration.assert_called_once_with(MOCK_COMPANY_SHORT_NAME)

    def test_get_with_errors_returns_400(self):
        """Cuando load_configuration devuelve errores, debe responder 400."""
        mock_company = MagicMock()
        self.mock_profile_service.get_company_by_short_name.return_value = mock_company

        config = {"id": MOCK_COMPANY_SHORT_NAME, "name": "Sample Company"}
        errors = ["validation error 1", "validation error 2"]
        self.mock_config_service.load_configuration.return_value = (config, errors)

        resp = self.client.get(f"/api/{MOCK_COMPANY_SHORT_NAME}/config")

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["config"]["id"] == MOCK_COMPANY_SHORT_NAME
        assert data["errors"] == [errors]
        self.mock_config_service.load_configuration.assert_called_once_with(MOCK_COMPANY_SHORT_NAME)

    def test_get_when_exception(self):
        """Si ocurre una excepción inesperada, debe devolver 500 y status 'error'."""
        mock_company = MagicMock()
        self.mock_profile_service.get_company_by_short_name.return_value = mock_company

        self.mock_config_service.load_configuration.side_effect = Exception("boom")

        resp = self.client.get(f"/api/{MOCK_COMPANY_SHORT_NAME}/config")

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["status"] == "error"