from companies.maxxa.maxxa_collection import MaxxaCollection
from companies.maxxa.maxxa_contact import MaxxaContact
from unittest.mock import Mock, patch
import pytest
import os
import json


class TestMaxxaCollection():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock()

        self.patcher = patch.dict(os.environ, {'PORTAL_BACKEND_URL': 'https://api.test.com'})
        self.patcher.start()

        #instance of certificate
        self.maxxa_collection = MaxxaCollection(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util
        )

    def teardown_method(self):
        self.patcher.stop()

    def test_get_client_collection_success(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        self.mock_maxxa_util.transform_date.return_value = '01-07-2024'
        mock_response = [{
                'status': "IN_PROCESS",
                'letter_date': "Fri, 06 Jun 2025 00:00:00 -0000",
                'warranty': {
                    "certificate_id": "AE001226",
                }
            }
            ]
        self.mock_call_service.get.return_value = (mock_response, 200)
        result = self.maxxa_collection.get_client_collections(rut=rut)

        assert isinstance(result, str)
        cert_list = json.loads(result)
        assert cert_list[0]['certificate_id'] == 'AE001226'

        self.mock_call_service.get.assert_called_once()
        self.mock_util.validate_rut.assert_called_once_with(rut)

    def test_get_client_contact_info_when_not_valid_rut(self):
        rut = 'invalid-rut'
        self.mock_util.validate_rut.return_value = False
        result = self.maxxa_collection.get_client_collections(rut=rut)
        assert r'no es válido' in result

    def test_get_client_contact_info_missing_url(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception) as e:
                self.maxxa_collection.get_client_collections(rut=rut)
            assert str(e.value) == 'missing portal_backend_url'

    def test_get_client_contact_info_not_found(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (None, 404)
        result = self.maxxa_collection.get_client_collections(rut=rut)
        assert result == f'No existe información de cobranza pre-judicial para el cliente con rut {rut}'

    def test_get_client_contact_info_service_error(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (None, 500)
        result = self.maxxa_collection.get_client_collections(rut=rut)
        assert result == 'No se pudo comunicar con cobranza pre-judicial, intentalo de nuevo'
