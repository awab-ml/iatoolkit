# tests/services/test_configuration_service.py

import pytest
from unittest.mock import Mock, patch, call
from pathlib import Path

from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.common.util import Utility
from iatoolkit import BaseCompany  # Usado para type hinting en el mock
from iatoolkit.repositories.models import Company as CompanyModel, PromptCategory

# --- Mock Data ---
# Simula el contenido de company.yaml
MOCK_MAIN_CONFIG = {
    'id': 'acme',
    'name': 'ACME Corp',
    'parameters': {'cors_origin': ['https://acme.com']},
    'tools': [{'function_name': 'get_stock', 'description': 'Gets stock price', 'params': {}}],
    'prompt_categories': ['General'],
    'prompts': [{'category': 'General', 'name': 'sales_report', 'description': 'Sales report', 'order': 1}],
    'help_files': {'onboarding_cards': 'onboarding.yaml'}
}

# Simula el contenido de onboarding.yaml
MOCK_ONBOARDING_CONFIG = [
    {'icon': 'fas fa-rocket', 'title': 'Welcome!'}
]


class TestConfigurationService:
    """
    Unit tests for the ConfigurationService.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """
        Pytest fixture that runs before each test to create mocks for all dependencies
        and instantiate the ConfigurationService.
        """
        self.mock_utility = Mock(spec=Utility)

        # Mock para la instancia de la clase de compañía (ej. SampleCompany)
        self.mock_company_instance = Mock(spec=BaseCompany)
        # Mock para el objeto ORM que devuelven los métodos de creación
        self.mock_company_orm_object = Mock(spec=CompanyModel)
        self.mock_company_instance._create_company.return_value = self.mock_company_orm_object
        self.mock_company_instance._create_prompt_category.return_value = Mock(spec=PromptCategory)

        self.service = ConfigurationService(utility=self.mock_utility)
        self.COMPANY_NAME = 'acme'

    @patch('pathlib.Path.exists')
    def test_load_configuration_happy_path(self, mock_exists):
        """
        GIVEN a valid configuration with main and help files
        WHEN load_configuration is called
        THEN it should call all registration methods on the company instance with the correct data.
        """
        # Arrange
        mock_exists.return_value = True

        def yaml_side_effect(path):
            if "company.yaml" in str(path):
                return MOCK_MAIN_CONFIG
            if "onboarding.yaml" in str(path):
                return MOCK_ONBOARDING_CONFIG
            return {}

        self.mock_utility.load_schema_from_yaml.side_effect = yaml_side_effect

        # Act
        self.service.load_configuration(self.COMPANY_NAME, self.mock_company_instance)

        # Assert
        # 1. Verify core details were registered
        self.mock_company_instance._create_company.assert_called_once_with(
            short_name='acme',
            name='ACME Corp',
            parameters={'cors_origin': ['https://acme.com']}
        )

        # 2. Verify tools were registered
        self.mock_company_instance._create_function.assert_called_once_with(
            function_name='get_stock',
            description='Gets stock price',
            params={}
        )

        # 3. Verify prompts were registered
        self.mock_company_instance._create_prompt_category.assert_called_once_with(name='General', order=1)
        self.mock_company_instance._create_prompt.assert_called_once()

        # 4. Verify final attributes were set on the instance
        assert self.mock_company_instance.company_short_name == self.COMPANY_NAME
        assert self.mock_company_instance.company == self.mock_company_orm_object

    @patch('pathlib.Path.exists', return_value=True)
    def test_get_configuration_uses_cache_on_second_call(self, mock_path_exists):
        """
        GIVEN a configuration that needs to be loaded from files,
        WHEN get_configuration is called multiple times for the same company,
        THEN the file-reading logic should only be executed on the first call.
        """

        # Arrange
        # Configura el mock para que devuelva el contenido correcto para cada archivo.
        def yaml_side_effect(path):
            if "company.yaml" in str(path):
                return MOCK_MAIN_CONFIG
            if "onboarding.yaml" in str(path):
                return MOCK_ONBOARDING_CONFIG
            return {}

        self.mock_utility.load_schema_from_yaml.side_effect = yaml_side_effect

        # --- First Call ---
        # Act
        result1 = self.service.get_configuration(self.COMPANY_NAME, 'name')

        # Assert
        assert result1 == 'ACME Corp'
        # Verificamos que se leyeron los dos archivos (el principal y el de ayuda).
        assert self.mock_utility.load_schema_from_yaml.call_count == 2
        expected_calls = [
            call(Path(f'companies/{self.COMPANY_NAME}/config/company.yaml')),
            call(Path(f'companies/{self.COMPANY_NAME}/config/onboarding.yaml'))
        ]
        self.mock_utility.load_schema_from_yaml.assert_has_calls(expected_calls, any_order=True)

        # --- Second Call ---
        # Act: pedimos otra pieza de la configuración
        result2 = self.service.get_configuration(self.COMPANY_NAME, 'id')

        # Assert
        assert result2 == 'acme'
        # La aserción CRUCIAL: El contador de llamadas NO debe haber aumentado,
        # lo que prueba que los datos se sirvieron desde la caché.
        assert self.mock_utility.load_schema_from_yaml.call_count == 2

    @patch('pathlib.Path.exists', return_value=False)
    def test_load_configuration_raises_file_not_found(self, mock_exists):
        """
        GIVEN the main company.yaml file does not exist
        WHEN load_configuration is called
        THEN it should raise a FileNotFoundError.
        """
        with pytest.raises(FileNotFoundError):
            self.service.load_configuration(self.COMPANY_NAME, self.mock_company_instance)

    @patch('pathlib.Path.exists')
    def test_load_configuration_handles_missing_help_file(self, mock_exists):
        """
        GIVEN the main company.yaml exists but a referenced help file does not
        WHEN _load_and_merge_configs is called
        THEN it should complete successfully, setting the missing content to None.
        """
        # Arrange: Configure the side_effect to return values sequentially.
        # The first call to .exists() is for company.yaml -> True
        # The second call to .exists() is for onboarding.yaml -> False
        mock_exists.side_effect = [True, False]

        # Arrange: The utility will only be called for the file that exists.
        self.mock_utility.load_schema_from_yaml.return_value = MOCK_MAIN_CONFIG

        # Act
        # Usamos el método privado para probar la lógica de merge directamente
        merged_config = self.service._load_and_merge_configs(self.COMPANY_NAME)

        # Assert
        # 1. Check that the key for the missing file exists and is None.
        assert 'onboarding_cards' in merged_config
        assert merged_config['onboarding_cards'] is None

        # 2. Check that other keys from the main config are still present.
        assert merged_config['id'] == 'acme'

        # 3. Check that load_schema_from_yaml was only called once (for company.yaml).
        self.mock_utility.load_schema_from_yaml.assert_called_once()

        # 4. Check that .exists() was called twice as expected.
        assert mock_exists.call_count == 2

    @patch('pathlib.Path.exists', return_value=True)
    def test_load_configuration_handles_empty_sections(self, mock_exists):
        """
        GIVEN a config file is missing optional sections like 'tools' or 'prompts'
        WHEN load_configuration is called
        THEN it should run without error and not call registration methods for those sections.
        """
        # Arrange
        minimal_config = {
            'id': 'minimal_co',
            'name': 'Minimal Co',
            'help_files': {}  # No help files
            # No 'tools', 'prompts', etc.
        }
        self.mock_utility.load_schema_from_yaml.return_value = minimal_config

        # Act
        self.service.load_configuration('minimal_co', self.mock_company_instance)

        # Assert
        # Verify the core details were still registered
        self.mock_company_instance._create_company.assert_called_once_with(
            short_name='minimal_co', name='Minimal Co', parameters={}
        )
        # Verify that methods for missing sections were NOT called
        self.mock_company_instance._create_function.assert_not_called()
        self.mock_company_instance._create_prompt.assert_not_called()