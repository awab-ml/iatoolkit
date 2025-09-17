from companies.maxxa.maxxa_certificate import MaxxaCertificate
from unittest.mock import Mock, patch
from companies.maxxa.maxxa_util import UtilityMaxxa
import pytest
import os
import json


class TestMaxxaCertificate():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock(spec=UtilityMaxxa)


        #instance of certificate
        self.maxxa_certificate = MaxxaCertificate(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util
        )

        self.certificate = {
            'certificate_id': '1234567890',
            'certificate_type': 'Fianza',
            'provider_rut': '12345678',
            'provider_rut_dv': '9',
            'provider_name': 'Empresa Test',
            'guarantee_issue_date': '2024-01-01',
            'guarantee_due_date': '2024-12-31',
            'insured_amount_in_original_currency': '1000000',
            'original_currency': 'CLP',
        }


    def test_get_certificate_success(self):
        self.mock_maxxa_util.exec_sp.return_value = [self.certificate]
        result = self.maxxa_certificate.get_certificate_by_id(certificate_id="1234567890")
        cert_data = json.loads(result)
        assert cert_data.get('certificate_id') == "1234567890"


    def test_get_certificate_when_empty_certificate_id(self):
        with pytest.raises(Exception) as e:
            self.maxxa_certificate.get_certificate_by_id(certificate_id='')
        assert str(e.value) == 'missing certificate_id'


    def test_get_certificate_when_not_found(self):
        self.mock_maxxa_util.exec_sp.return_value = []
        result = self.maxxa_certificate.get_certificate_by_id(certificate_id='1234567890')
        assert result == 'no existe el certificado'

    def test_get_certificate_when_not_ok(self):
        self.mock_maxxa_util.exec_sp.return_value = 'an error'
        result = self.maxxa_certificate.get_certificate_by_id(certificate_id='1234567890')
        assert result ==  'an error'

    def test_get_by_rut_success(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = True

        self.mock_maxxa_util.join_rut_dv.return_value = '12345678-9'
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'
        self.mock_maxxa_util.transform_currency.return_value = 'Pesos'
        self.mock_maxxa_util.exec_sp.return_value = [self.certificate, self.certificate]

        result = self.maxxa_certificate.get_certificate_by_rut(rut=rut)
        json_result = json.loads(result)

        assert len(json_result) == 2
        self.mock_util.validate_rut.assert_called_once_with(rut)

    def test_get_by_rut_when_not_valid_rut(self):
        rut = '1234567890'
        self.mock_util.validate_rut.return_value = False
        result = self.maxxa_certificate.get_certificate_by_rut(rut=rut)
        assert result == f'El RUT "{rut}" no corresponde a un rut valido para obtener certificados de fianza'

    def test_get_by_rut_when_not_rut(self):
        with pytest.raises(Exception) as e:
            self.maxxa_certificate.get_certificate_by_rut(rut='')
        assert str(e.value) == 'missing rut'

    def test_get_by_rut_when_not_ok(self):
        self.mock_maxxa_util.exec_sp.return_value = []
        result = self.maxxa_certificate.get_certificate_by_rut(rut='1234567890')
        assert 'no existen certificados' in result

    def test_get_by_rut_when_error(self):
        self.mock_maxxa_util.exec_sp.return_value = 'an error'
        result = self.maxxa_certificate.get_certificate_by_rut(rut='1234567890')
        assert 'error' in result