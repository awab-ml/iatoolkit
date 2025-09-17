from companies.maxxa.maxxa_public_market import MaxxaPublicMarket
from unittest.mock import Mock, patch
import pytest
import os


class TestMaxxaPublicMarket():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock()

        self.patcher = patch.dict(os.environ, {'PUBLIC_MARKET_API_URL': 'https://api.test.com'})
        self.patcher.start()

        #instance of public market
        self.maxxa_public_market = MaxxaPublicMarket(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util
        )

    def teardown_method(self):
        self.patcher.stop()

    def test_tenders_by_rut_success(self):
        rut = '12345678-9'
        mock_response = {
            'rut': '12345678-9',
            'client_name': 'Empresa Test',
            'tenders': [
                {
                    'external_id': 'LIC-001',
                    'buyer': 'Comprador Test',
                    'tender_status': 'Activa',
                    'publish_date': '2024-01-01',
                    'closing_date': '2024-02-01',
                    'adjudication_date': '2024-02-15',
                    'external_link': 'https://example.com',
                    'seriousness_guarantees': '1000000',
                    'faithful_guarantees': '500000',
                    'amount': '5000000',
                    'offer_status': 'Presentada',
                    'won': True
                }
            ]
        }

        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'
        self.mock_maxxa_util.transform_currency.return_value = 'Pesos'

        result = self.maxxa_public_market.client_tenders(rut=rut)

        assert 'rut' in result
        assert '12345678-9' in result
        assert 'LIC-001' in result
        assert 'Empresa Test' in result

        self.mock_util.validate_rut.assert_called_once_with(rut)
        self.mock_call_service.get.assert_called_once()

    def test_tenders_by_rut_missing_rut(self):
        with pytest.raises(Exception) as e:
            self.maxxa_public_market.client_tenders()
        assert str(e.value) == 'missing rut'

    def test_tenders_by_rut_empty_rut(self):
        with pytest.raises(Exception) as e:
            self.maxxa_public_market.client_tenders(rut='')
        assert str(e.value) == 'missing rut'

    def test_get_tenders_by_rut_invalid_rut(self):
        rut = 'invalid-rut'
        self.mock_util.validate_rut.return_value = False
        result = self.maxxa_public_market.get_tenders_by_rut(rut)
        assert result == f'El RUT "{rut}" no corresponde a un rut valido'

    def test_get_tenders_by_rut_missing_url(self):
        rut = '12345678-9'
        self.mock_util.validate_rut.return_value = True
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception) as e:
                self.maxxa_public_market.get_tenders_by_rut(rut)
            assert str(e.value) == 'missing public_market_url'

    def test_get_tenders_by_rut_not_found(self):
        rut = '12345678-9'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (None, 404)
        result = self.maxxa_public_market.get_tenders_by_rut(rut)
        assert result == f'no existen licitaciones en chilecompra que registren participacion del rut {rut}'

    def test_get_tenders_by_rut_service_error(self):
        rut = '12345678-9'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (None, 500)
        result = self.maxxa_public_market.get_tenders_by_rut(rut)
        assert result == 'no pude comunicarme con mercado publico, intentalo de nuevo'

    def test_get_tenders_by_rut_not_list(self):
        rut = '12345678-9'
        mock_response = {'tenders': 'not_a_list'}
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (mock_response, 200)
        result = self.maxxa_public_market.get_tenders_by_rut(rut)
        assert result == f'no existen licitaciones en chilecompra que registren participacion del rut {rut}'

    def test_get_tenders_by_rut_empty_list(self):
        rut = '12345678-9'
        mock_response = {
            'rut': '12345678-9',
            'client_name': 'Empresa Test',
            'tenders': []
        }
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.get.return_value = (mock_response, 200)
        result = self.maxxa_public_market.get_tenders_by_rut(rut)
        assert isinstance(result, dict)
        assert result['rut'] == '12345678-9'
        assert result['company_name'] == 'Empresa Test'
        assert result['tenders'] == []

    def test_get_tender_by_id_success(self):
        tender_id = 'LIC-001'
        mock_response = {
            'external_id': 'LIC-001',
            'buyer': {
                'rut': '98765432-1',
                'public_organization': {
                    'name': 'Organización Compradora'
                }
            },
            'tender_info': {
                'description': 'Descripción de la licitación'
            },
            'publish_datetime': '2024-01-01T10:00:00',
            'closing_datetime': '2024-02-01T18:00:00',
            'adjudication_datetime': '2024-02-15T12:00:00'
        }
        self.mock_call_service.get.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'
        result = self.maxxa_public_market.get_tender_by_id(tender_id)
        assert 'id_licitacion' in result
        assert 'LIC-001' in result
        assert 'buyer_rut' in result
        assert '98765432-1' in result
        assert 'buyer_name' in result
        assert 'Organización Compradora' in result
        self.mock_call_service.get.assert_called_once()

    def test_get_tender_by_id_missing_url(self):
        tender_id = 'LIC-001'
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception) as e:
                self.maxxa_public_market.get_tender_by_id(tender_id)
            assert str(e.value) == 'missing public_market_url'

    def test_get_tender_by_id_not_found(self):
        tender_id = 'LIC-999'
        self.mock_call_service.get.return_value = (None, 404)
        result = self.maxxa_public_market.get_tender_by_id(tender_id)
        assert result == f'no existe en chilecompra la licitación {tender_id}'

    def test_get_tender_by_id_service_error(self):
        tender_id = 'LIC-001'
        self.mock_call_service.get.return_value = (None, 500)
        result = self.maxxa_public_market.get_tender_by_id(tender_id)
        assert result == 'no pude comunicarme con mercado publico, intentalo de nuevo'

    def test_get_tender_by_id_with_none_fields(self):
        tender_id = 'LIC-001'
        mock_response = {
            'external_id': 'LIC-001',
            'buyer': {},
            'tender_info': {},
            'publish_datetime': None,
            'closing_datetime': None,
            'adjudication_datetime': None
        }

        self.mock_call_service.get.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'

        result = self.maxxa_public_market.get_tender_by_id(tender_id)

        assert 'id_licitacion' in result
        assert 'LIC-001' in result
        assert 'buyer_rut' in result
        assert 'buyer_name' in result
        assert 'description' in result

        self.mock_call_service.get.assert_called_once()

    def test_get_tender_by_id_with_empty_buyer(self):
        tender_id = 'LIC-001'
        mock_response = {
            'external_id': 'LIC-001',
            'buyer': {},
            'tender_info': {},
            'publish_datetime': '2024-01-01T10:00:00',
            'closing_datetime': '2024-02-01T18:00:00',
            'adjudication_datetime': '2024-02-15T12:00:00'
        }

        self.mock_call_service.get.return_value = (mock_response, 200)
        self.mock_maxxa_util.transform_date.return_value = '01/01/2024'

        result = self.maxxa_public_market.get_tender_by_id(tender_id)

        assert 'id_licitacion' in result
        assert 'LIC-001' in result
        assert 'buyer_rut' in result
        assert 'buyer_name' in result
        assert 'description' in result

        self.mock_call_service.get.assert_called_once()
