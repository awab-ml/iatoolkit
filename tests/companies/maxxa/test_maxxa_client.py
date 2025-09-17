from companies.maxxa.maxxa_client import MaxxaClient
from unittest.mock import Mock, patch
import pytest
import os
import json


class TestMaxxaClient():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock()
        self.mock_maxxa_public_market = Mock()
        self.mock_maxxa_contact = Mock()
        self.mock_maxxa_contract = Mock()
        self.mock_maxxa_collection = Mock()

        self.patcher = patch.dict(os.environ, {'BCU_API_URL': 'https://api.test.com'})
        self.patcher.start()

        #instance of client
        self.maxxa_client = MaxxaClient(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util,
            maxxa_public_market=self.mock_maxxa_public_market,
            maxxa_contact=self.mock_maxxa_contact,
            maxxa_contract=self.mock_maxxa_contract,
            maxxa_collection=self.mock_maxxa_collection
        )

        self.mock_maxxa_public_market.get_tenders_by_rut.return_value = '[]'
        self.mock_maxxa_contact.get_client_contact_info.return_value = '[]'
        self.mock_maxxa_contract.get_client_contract_info.return_value = '[]'
        self.mock_maxxa_collection.get_client_collections.return_value = '[]'

    def teardown_method(self):
        self.patcher.stop()


    def test_get_client_success(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 1,
            'customers': [{
                'rut': '12345678-9',
                'client_name': 'Empresa Test',
                'p_guarantee': True,
                'p_credit': True,
                'p_erpyme': False,
                'p_portal': True,
                'blocked': False,
                'jsonb_guarantee': {"vigentes": 5, "cobradas": 2, "terminadas": 1, "linea_publica": "1000000", "linea_publica_disponible": "500000", "login_ejecutivo": "ejecutivo1", "login_lider": "lider1", "created": "2024-01-01"},
                'jsonb_credit': {"product_type": "Credito", "line_type": "Revolvente", "guarantee_type": "Fianza", "original_amount": "2000000", "interest_rate": "12.5", "term_in_months": "24", "financier_name": "Banco Test", "line_status": "Activa", "line_available": "1000000", "current_debt": "1500000", "morosity_status": "Al dia", "paid_installments": "12", "overdue_installments": "0", "created": "2024-01-01", "channel": "Directo", "executive": "ejecutivo2", "group": "grupo1"},
                'jsonb_erpyme': {},
                'jsonb_risk_evaluation': {"sii_segment": "Mediana", "economic_activity": "Comercio", "annual_sales": "50000000", "risk_classification": "A"},
                'jsonb_collection': {"status": "Activo"},
                'jsonb_portal': {"portal_registration": True, "portal_active_users": 3, "sii_password_validated": True},
            }]
        }

        self.mock_call_service.post.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'



        result = self.maxxa_client.get_client(rut_or_name=rut)

        assert 'rut' in result
        assert '12345678-9' in result
        assert 'Empresa Test' in result
        assert 'Mediana' in result
        assert 'Comercio' in result

        self.mock_call_service.post.assert_called_once()
        self.mock_maxxa_public_market.get_tenders_by_rut.assert_called_once_with(rut)
        self.mock_maxxa_contact.get_client_contact_info.assert_called_once_with(rut)

    def test_get_client_missing_rut_or_name(self):
        with pytest.raises(Exception) as e:
            self.maxxa_client.get_client()
        assert str(e.value) == 'missing rut or name'

    def test_get_client_empty_rut_or_name(self):
        with pytest.raises(Exception) as e:
            self.maxxa_client.get_client(rut_or_name='')
        assert str(e.value) == 'missing rut or name'

    def test_get_client_missing_bcu_url(self):
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception) as e:
                self.maxxa_client.get_client(rut_or_name='12345678-9')
            assert str(e.value) == 'missing bcu_url'

    def test_get_client_not_found(self):
        rut = '12345678-9'
        self.mock_call_service.post.return_value = (None, 404)
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == f'El cliente {rut} no figura como cliente de Maxxa'

    def test_get_client_service_error(self):
        rut = '12345678-9'
        self.mock_call_service.post.return_value = (None, 500)
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == 'no pude comunicarme con la base de datos de Maxxa, intentalo de nuevo'

    def test_get_client_too_many_customers(self):
        rut = '12345678-9'
        mock_response = {'total_customers': 15}
        self.mock_call_service.post.return_value = (mock_response, 200)
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == 'Se encontraron múltiples clientes con ese nombre o rut. Debe especificar mejor el nombre o rut del cliente'

    def test_get_client_multiple_customers(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 3,
            'customers': [
                {'client_name': 'Empresa 1'},
                {'client_name': 'Empresa 2'},
                {'client_name': 'Empresa 3'}
            ]
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        self.mock_maxxa_util.get_customers_names_response.return_value = 'Empresa 1, Empresa 2, Empresa 3'
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == f'Se encontraron múltiples clientes con ese nombre o rut. Por favor, especifique cuál de los siguientes clientes desea consultar: Empresa 1, Empresa 2, Empresa 3'
        self.mock_maxxa_util.get_customers_names_response.assert_called_once_with(mock_response['customers'])

    def test_get_client_zero_customers(self):
        rut = '12345678-9'
        mock_response = {'total_customers': 0}
        self.mock_call_service.post.return_value = (mock_response, 200)
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == f'No se encontró el cliente {rut}'

    def test_get_client_empty_customers_list(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 0,
            'customers': []
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == f'No se encontró el cliente {rut}'

    def test_get_client_with_invalid_json_data(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 1,
            'customers': [{
                'rut': '12345678-9',
                'client_name': 'Empresa Test',
                'p_guarantee': True,
                'p_credit': True,
                'p_erpyme': False,
                'p_portal': True,
                'blocked': False,
                'data_guarantee': '{"vigentes": 5}',
                'data_credit': '{"product_type": "Credito"}',
                'data_erpyme': '{}',
                'data_scoring': '{"sii_segment": "Mediana"}',
                'data_collection': '{"status": "Activo"}',
                'data_portal': '{"portal_registration": true}',
                'service_or_support_request_history': 'Historial'
            }]
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'

        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert 'rut' in result
        assert '12345678-9' in result

    def test_get_client_with_none_data_fields(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 1,
            'customers': [{
                'rut': '12345678-9',
                'client_name': 'Empresa Test',
                'p_guarantee': False,
                'p_credit': False,
                'p_erpyme': False,
                'p_portal': False,
                'blocked': False,
            }]
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'

        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert 'rut' in result
        assert '12345678-9' in result
        assert 'p_guarantee' in result
        assert 'p_credit' in result

    def test_get_client_with_portal(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 1,
            'customers': [{
                'rut': '12345678-9',
                'client_name': 'Empresa Test',
                'p_guarantee': False,
                'p_credit': False,
                'p_erpyme': False,
                'p_portal': True,
                'blocked': False,
                'jsonb_risk_evaluation': '{"sii_segment": "Mediana"}',
                'jsonb_portal': {"portal_registration": True,
                                 "portal_active_users": 2,
                                 "sii_password_validated": True},
            }]
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'

        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert '"jsonb_portal":' in result
        result_dict = json.loads(result)
        assert result_dict['jsonb_portal']['portal_registration'] == True
        assert result_dict['jsonb_portal']['portal_active_users'] == 2
        assert result_dict['jsonb_portal']['sii_password_validated'] == True

    def test_get_client_with_none_response(self):
        rut = '12345678-9'
        mock_response = {
            'total_customers': 1,
            'customers': [None]
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        result = self.maxxa_client.get_client(rut_or_name=rut)
        assert result == f'No se encontró el cliente {rut}'