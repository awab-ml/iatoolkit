from companies.maxxa.maxxa_util import UtilityMaxxa
from infra.call_service import CallServiceClient
from unittest.mock import Mock, patch


class TestMaxxaUtil():

    def setup_method(self):
        self.mock_call_service = Mock()
        self.maxxa_util = UtilityMaxxa(self.mock_call_service)

    def test_transform_currency_dollar(self):
        result = self.maxxa_util.transform_currency("$")
        assert result == "CLP"

    def test_transform_currency_euro(self):
        result = self.maxxa_util.transform_currency("€")
        assert result == "EUR"

    def test_transform_currency_unknown(self):
        result = self.maxxa_util.transform_currency("USD")
        assert result == "USD"

    def test_transform_currency_empty_string(self):
        result = self.maxxa_util.transform_currency("")
        assert result == ""

    def test_transform_currency_none(self):
        result = self.maxxa_util.transform_currency(None)
        assert result == ""

    def test_transform_currency_whitespace(self):
        result = self.maxxa_util.transform_currency("   ")
        assert result == "   "

    def test_transform_date_already_formatted(self):
        result = self.maxxa_util.transform_date("15-03-2024")
        assert result == "15-03-2024"

    def test_transform_date_iso_format(self):
        result = self.maxxa_util.transform_date("2024-03-15")
        assert result == "15-03-2024"

    def test_transform_date_iso_datetime(self):
        result = self.maxxa_util.transform_date("2024-03-15T10:30:00")
        assert result == "15-03-2024"

    def test_transform_date_us_format(self):
        result = self.maxxa_util.transform_date("03/15/2024")
        assert result == "15-03-2024"

    def test_transform_date_text_format(self):
        result = self.maxxa_util.transform_date("March 15, 2024")
        assert result == "15-03-2024"

    def test_transform_date_empty_string(self):
        result = self.maxxa_util.transform_date("")
        assert result == ""

    def test_transform_date_none(self):
        result = self.maxxa_util.transform_date(None)
        assert result == ""

    def test_transform_date_invalid_format(self):
        result = self.maxxa_util.transform_date("invalid-date")
        assert result == ""

    def test_transform_date_whitespace(self):
        result = self.maxxa_util.transform_date("   ")
        assert result == ""

    def test_join_rut_dv_valid(self):
        result = self.maxxa_util.join_rut_dv("12345678", "9")
        assert result == "12345678-9"

    def test_join_rut_dv_with_spaces(self):
        result = self.maxxa_util.join_rut_dv(" 12345678 ", " 9 ")
        assert result == " 12345678 - 9 "

    def test_join_rut_dv_empty_rut(self):
        result = self.maxxa_util.join_rut_dv("", "9")
        assert result == ""

    def test_join_rut_dv_empty_dv(self):
        result = self.maxxa_util.join_rut_dv("12345678", "")
        assert result == ""

    def test_join_rut_dv_none_rut(self):
        result = self.maxxa_util.join_rut_dv(None, "9")
        assert result == ""

    def test_join_rut_dv_none_dv(self):
        result = self.maxxa_util.join_rut_dv("12345678", None)
        assert result == ""

    def test_join_rut_dv_both_none(self):
        result = self.maxxa_util.join_rut_dv(None, None)
        assert result == ""

    def test_join_rut_dv_both_empty(self):
        result = self.maxxa_util.join_rut_dv("", "")
        assert result == ""

    def test_get_customers_names_response_valid(self):
        customers = [
            {'client_name': 'Empresa 1', 'rut': '12345678-9'},
            {'client_name': 'Empresa 2', 'rut': '98765432-1'}
        ]
        result = self.maxxa_util.get_customers_names_response(customers)
        expected = "1. Empresa 1 (12345678-9) \n2. Empresa 2 (98765432-1) "
        assert result == expected

    def test_get_customers_names_response_single_customer(self):
        customers = [
            {'client_name': 'Empresa 1', 'rut': '12345678-9'}
        ]
        result = self.maxxa_util.get_customers_names_response(customers)
        expected = "1. Empresa 1 (12345678-9) "
        assert result == expected

    def test_get_customers_names_response_empty_list(self):
        customers = []
        result = self.maxxa_util.get_customers_names_response(customers)
        assert result == ""

    def test_get_customers_names_response_none(self):
        customers = None
        result = self.maxxa_util.get_customers_names_response(customers)
        assert result == ""

    def test_get_customers_names_response_missing_fields(self):
        customers = [
            {'client_name': 'Empresa 1'},  # sin rut
            {'rut': '98765432-1'}  # sin nombre
        ]
        result = self.maxxa_util.get_customers_names_response(customers)
        expected = "1. Empresa 1 () \n2.  (98765432-1) "
        assert result == expected

    def test_get_customers_names_response_empty_fields(self):
        customers = [
            {'client_name': '', 'rut': ''},
            {'client_name': 'Empresa 2', 'rut': '98765432-1'}
        ]
        result = self.maxxa_util.get_customers_names_response(customers)
        expected = "1.  () \n2. Empresa 2 (98765432-1) "
        assert result == expected

    def test_get_customers_names_response_many_customers(self):
        customers = [
            {'client_name': f'Empresa {i}', 'rut': f'1234567{i}-{i}'} 
            for i in range(1, 6)
        ]
        result = self.maxxa_util.get_customers_names_response(customers)

        assert "1. Empresa 1 (12345671-1) " in result
        assert "2. Empresa 2 (12345672-2) " in result
        assert "3. Empresa 3 (12345673-3) " in result
        assert "4. Empresa 4 (12345674-4) " in result
        assert "5. Empresa 5 (12345675-5) " in result
        assert result.count('\n') == 4

    @patch('os.getenv')
    def test_exec_sp_success(self, mock_getenv):
        # Arrange
        mock_getenv.return_value = 'http://fake-middleware.com'
        expected_response_data = [{'col1': 'value1', 'col2': 123}]
        self.mock_call_service.post.return_value = (expected_response_data, 200)

        # Act
        result = self.maxxa_util.exec_sp('TEST_DB', 'TEST_SP', False, [])

        # Assert
        assert result == expected_response_data
        self.mock_call_service.post.assert_called_once()

    @patch('os.getenv')
    def test_exec_sp_service_error(self, mock_getenv):
        # Arrange
        mock_getenv.return_value = 'http://fake-middleware.com'
        self.mock_call_service.post.return_value = ({'error': 'server down'}, 500)
        expected_error_message = 'no pude comunicarme con la base de certificados de Maxxa, intentalo de nuevo'

        # Act
        result = self.maxxa_util.exec_sp('TEST_DB', 'TEST_SP', False, [])

        # Assert
        assert result == expected_error_message

    @patch('os.getenv')
    def test_exec_sp_missing_middleware_url(self, mock_getenv):
        # Arrange
        mock_getenv.return_value = None

        # Act & Assert
        try:
            self.maxxa_util.exec_sp('TEST_DB', 'TEST_SP', False, [])
            assert False, "Exception was not raised"
        except Exception as e:
            assert str(e) == 'missing middleware url'

    @patch('os.getenv')
    def test_exec_sp_payload_construction(self, mock_getenv):
        # Arrange
        mock_getenv.return_value = 'http://fake-middleware.com'
        self.mock_call_service.post.return_value = ({}, 200)

        db_name = 'MyDatabase'
        sp_name = 'MyProcedure'
        is_non_query = True
        params = [{'name': 'Param1', 'type': 'String', 'value': 'Value1'}]

        expected_endpoint = 'http://fake-middleware.com/v1/procedures/exec_sp'
        expected_payload = {
            'databaseName': db_name,
            'procedureName': sp_name,
            'isNonQuery': is_non_query,
            'parameters': params
        }

        # Act
        self.maxxa_util.exec_sp(db_name, sp_name, is_non_query, params)

        # Assert
        self.mock_call_service.post.assert_called_once_with(
            endpoint=expected_endpoint,
            json_dict=expected_payload
        )
