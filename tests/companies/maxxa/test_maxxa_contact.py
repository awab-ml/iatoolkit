from companies.maxxa.maxxa_contact import MaxxaContact
from unittest.mock import Mock, patch
import pytest
import os


class TestMaxxaContact():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock()

        self.patcher = patch.dict(os.environ, {'CONTACT_BOOK_API_URL': 'https://api.test.com'})
        self.patcher.start()

        #instance of certificate
        self.maxxa_contact = MaxxaContact(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util
        )

    def teardown_method(self):
        self.patcher.stop()

    def test_get_client_contact_info_success(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        mock_response = {
            'main_contact': {
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'phone': '1234567890'
            },
            'guarantee_contact': {
                'name': 'Jane Smith',
                'email': 'jane.smith@example.com',
                'phone': '0987654321'
            }
        }
        self.mock_call_service.get.return_value = (mock_response, 200)
        result = self.maxxa_contact.get_client_contact_info(rut=rut)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]['name'] == 'John Doe'
        assert result[0]['is_main_contact'] == True
        assert result[1]['name'] == 'Jane Smith'
        assert result[1]['is_main_contact'] == False
        self.mock_call_service.get.assert_called_once()
        self.mock_util.validate_rut.assert_called_once_with(rut)

    def test_get_client_contact_info_when_not_valid_rut(self):
        rut = 'invalid-rut'
        self.mock_util.validate_rut.return_value = False
        result = self.maxxa_contact.get_client_contact_info(rut=rut)
        assert result == f'El rut "{rut}" no es válido'

    def test_get_client_contact_info_missing_contact_url(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception) as e:
                self.maxxa_contact.get_client_contact_info(rut=rut)
            assert str(e.value) == 'missing contact_book_api_url'

    def test_get_client_contact_info_not_found(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (None, 404)
        result = self.maxxa_contact.get_client_contact_info(rut=rut)
        assert result == f'No existe información de contactor para el cliente con rut {rut}'

    def test_get_client_contact_info_service_error(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (None, 500)
        result = self.maxxa_contact.get_client_contact_info(rut=rut)
        assert result == 'no pude comunicarme con el libro de contactos, intentalo de nuevo'

    def test_map_json_fields_with_all_contacts(self):
        contact = {
            'main_contact': {
                'name': 'Main Contact',
                'email': 'main@example.com',
                'phone': '1234567890'
            },
            'guarantee_contact': {
                'name': 'Guarantee Contact',
                'email': 'guarantee@example.com',
                'phone': '0987654321'
            },
            'credit_lines_contact': {
                'name': 'Credit Contact',
                'email': 'credit@example.com',
                'phone': '1122334455'
            },
            'portal_contact': {
                'name': 'Portal Contact',
                'email': 'portal@example.com',
                'phone': '5566778899'
            }
        }

        result = self.maxxa_contact.map_json_fields(contact)

        assert len(result) == 4
        assert result[0]['name'] == 'Main Contact'
        assert result[0]['is_main_contact'] == True
        assert result[1]['name'] == 'Guarantee Contact'
        assert result[1]['is_main_contact'] == False
        assert result[2]['name'] == 'Credit Contact'
        assert result[2]['is_main_contact'] == False
        assert result[3]['name'] == 'Portal Contact'
        assert result[3]['is_main_contact'] == False

    def test_map_json_fields_with_duplicate_phones(self):
        contact = {
            'main_contact': {
                'name': 'Main Contact',
                'email': 'main@example.com',
                'phone': '1234567890'
            },
            'guarantee_contact': {
                'name': 'Guarantee Contact',
                'email': 'guarantee@example.com',
                'phone': '1234567890'
            }
        }

        result = self.maxxa_contact.map_json_fields(contact)

        assert len(result) == 1
        assert result[0]['name'] == 'Main Contact'
        assert result[0]['phone'] == '1234567890'

    def test_map_json_fields_with_datos_empresa_sii(self):
        contact = {
            'main_contact': {
                'name': 'Datos Empresa SII-*-',
                'email': 'sii@example.com',
                'phone': '1234567890'
            },
            'guarantee_contact': {
                'name': 'Valid Contact',
                'email': 'valid@example.com',
                'phone': '0987654321'
            }
        }

        result = self.maxxa_contact.map_json_fields(contact)

        assert len(result) == 1
        assert result[0]['name'] == 'Valid Contact'
        assert 'Datos Empresa SII-*-' not in [r['name'] for r in result]

    def test_map_json_fields_with_empty_contact(self):
        contact = {}
        result = self.maxxa_contact.map_json_fields(contact)
        assert result == []

    def test_map_json_fields_with_none_contact(self):
        contact = None
        result = self.maxxa_contact.map_json_fields(contact)
        assert result == []

    def test_add_contact_if_valid_with_valid_contact(self):
        contact_data = {
            'name': 'Test Contact',
            'email': 'test@example.com',
            'phone': '1234567890'
        }
        response = []
        phone_numbers_seen = set()

        self.maxxa_contact.add_contact_if_valid(contact_data, response, phone_numbers_seen, True)

        assert len(response) == 1
        assert response[0]['name'] == 'Test Contact'
        assert response[0]['is_main_contact'] == True
        assert '1234567890' in phone_numbers_seen

    def test_add_contact_if_valid_with_datos_empresa_sii(self):
        contact_data = {
            'name': 'Datos Empresa SII-*-',
            'email': 'sii@example.com',
            'phone': '1234567890'
        }
        response = []
        phone_numbers_seen = set()

        self.maxxa_contact.add_contact_if_valid(contact_data, response, phone_numbers_seen, True)

        assert len(response) == 0
        assert len(phone_numbers_seen) == 0

    def test_add_contact_if_valid_with_duplicate_phone(self):
        contact_data = {
            'name': 'Test Contact',
            'email': 'test@example.com',
            'phone': '1234567890'
        }
        response = []
        phone_numbers_seen = {'1234567890'}

        self.maxxa_contact.add_contact_if_valid(contact_data, response, phone_numbers_seen, True)

        assert len(response) == 0