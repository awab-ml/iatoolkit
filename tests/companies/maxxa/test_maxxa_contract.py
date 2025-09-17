from companies.maxxa.maxxa_contract import MaxxaContract
from infra.call_service import CallServiceClient
from util import Utility
from companies.maxxa.maxxa_util import UtilityMaxxa
from unittest.mock import Mock, patch
import json
import os


class TestMaxxaContract:

    def setup_method(self):
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock()
        self.maxxa_contract = MaxxaContract(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util
        )

    # Tests para map_json_fields
    def test_map_json_fields_empty_response(self):
        """Test cuando la respuesta está vacía"""
        result = self.maxxa_contract.map_json_fields({})
        assert result == []

    def test_map_json_fields_none_response(self):
        """Test cuando la respuesta es None"""
        result = self.maxxa_contract.map_json_fields(None)
        assert result == []

    def test_map_json_fields_single_task(self):
        """Test mapeo de una sola tarea"""
        # Arrange
        mock_response = [{
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [{
                'item': 'CONFECCIÓN CONTRATO',
                'param_value': '{"numero": "G123", "num_multiproducto": "C456"}'
            }],
            'representatives': '[{"type": "admin", "rut": "12345678-9", "nombre": "Juan Pérez", "correo": "juan@test.com"}]'
        }]

        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act
        result = self.maxxa_contract.map_json_fields(mock_response)

        # Assert
        assert len(result) == 1
        task_data = result[0]
        assert task_data['contract_date'] == '02-07-2025'
        assert task_data['guarantee_contract'] == 'G123'
        assert task_data['credit_contract'] == 'C456'
        assert len(task_data['signatories']) == 1
        assert task_data['signatories'][0]['type'] == 'admin'
        assert task_data['signatories'][0]['rut'] == '12345678-9'
        assert task_data['signatories'][0]['name'] == 'Juan Pérez'
        assert task_data['signatories'][0]['email'] == 'juan@test.com'

    def test_map_json_fields_multiple_tasks(self):
        """Test mapeo de múltiples tareas"""
        # Arrange
        mock_response = [
            {
                'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
                'checklist': [{
                    'item': 'CONFECCIÓN CONTRATO',
                    'param_value': '{"numero": "G123", "num_multiproducto": "C456"}'
                }],
                'representatives': '[]'
            },
            {
                'end_date': 'Thu, 03 Jul 2025 10:30:00 -0000',
                'checklist': [{
                    'item': 'CONFECCIÓN CONTRATO',
                    'param_value': '{"numero": "G789", "num_multiproducto": "C012"}'
                }],
                'representatives': '[]'
            }
        ]

        self.mock_maxxa_util.transform_date.side_effect = ['02-07-2025', '03-07-2025']

        # Act
        result = self.maxxa_contract.map_json_fields(mock_response)

        # Assert
        assert len(result) == 2
        assert result[0]['contract_date'] == '02-07-2025'
        assert result[1]['contract_date'] == '03-07-2025'

    def test_map_json_fields_no_contract_formation(self):
        """Test cuando no hay item de CONFECCIÓN CONTRATO en el checklist"""
        # Arrange
        mock_response = [{
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [{
                'item': 'OTRO_ITEM',
                'param_value': '{}'
            }],
            'representatives': '[]'
        }]

        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act
        result = self.maxxa_contract.map_json_fields(mock_response)

        # Assert
        assert len(result) == 1
        task_data = result[0]
        assert task_data['contract_date'] == '02-07-2025'
        assert task_data['guarantee_contract'] == ''
        assert task_data['credit_contract'] == ''
        assert task_data['signatories'] == []

    def test_map_json_fields_invalid_json_representatives(self):
        """Test cuando el JSON de representantes es inválido"""
        # Arrange
        mock_response = [{
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [],
            'representatives': 'invalid json'
        }]

        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act & Assert
        try:
            result = self.maxxa_contract.map_json_fields(mock_response)
            assert False, "Debería haber lanzado una excepción"
        except json.JSONDecodeError:
            pass  # Esperado

    def test_map_json_fields_invalid_json_param_value(self):
        """Test cuando el JSON de param_value es inválido"""
        # Arrange
        mock_response = [{
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [{
                'item': 'CONFECCIÓN CONTRATO',
                'param_value': 'invalid json'
            }],
            'representatives': '[]'
        }]

        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act & Assert
        try:
            result = self.maxxa_contract.map_json_fields(mock_response)
            assert False, "Debería haber lanzado una excepción"
        except json.JSONDecodeError:
            pass  # Esperado

    # Tests para _process_single_task
    def test_process_single_task_complete_data(self):
        """Test procesamiento de tarea con datos completos"""
        # Arrange
        task = {
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [{
                'item': 'CONFECCIÓN CONTRATO',
                'param_value': '{"numero": "G123", "num_multiproducto": "C456"}'
            }],
            'representatives': '[{"type": "admin", "rut": "12345678-9", "nombre": "Juan Pérez", "correo": "juan@test.com"}]'
        }

        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act
        result = self.maxxa_contract._process_single_task(task)

        # Assert
        assert result['contract_date'] == '02-07-2025'
        assert result['guarantee_contract'] == 'G123'
        assert result['credit_contract'] == 'C456'
        assert len(result['signatories']) == 1
        assert result['signatories'][0]['type'] == 'admin'

    def test_process_single_task_missing_fields(self):
        """Test procesamiento de tarea con campos faltantes"""
        # Arrange
        task = {
            'end_date': '',
            'checklist': [],
            'representatives': '[]'
        }

        self.mock_maxxa_util.transform_date.return_value = ''

        # Act
        result = self.maxxa_contract._process_single_task(task)

        # Assert
        assert result['contract_date'] == ''
        assert result['guarantee_contract'] == ''
        assert result['credit_contract'] == ''
        assert result['signatories'] == []

    def test_process_single_task_multiple_representatives(self):
        """Test procesamiento con múltiples representantes"""
        # Arrange
        task = {
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [],
            'representatives': '''[
                {"type": "admin", "rut": "12345678-9", "nombre": "Juan Pérez", "correo": "juan@test.com"},
                {"type": "user", "rut": "98765432-1", "nombre": "María García", "correo": "maria@test.com"}
            ]'''
        }

        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act
        result = self.maxxa_contract._process_single_task(task)

        # Assert
        assert len(result['signatories']) == 2
        assert result['signatories'][0]['type'] == 'admin'
        assert result['signatories'][0]['name'] == 'Juan Pérez'
        assert result['signatories'][1]['type'] == 'user'
        assert result['signatories'][1]['name'] == 'María García'

    # Tests para get_client_contract_info
    @patch('os.getenv')
    def test_get_client_contract_info_success(self, mock_getenv):
        """Test obtención exitosa de información de contratos"""
        # Arrange
        mock_getenv.return_value = 'http://portal-backend.com'
        self.mock_util.validate_rut.return_value = True

        mock_response_data = [{
            'end_date': 'Wed, 02 Jul 2025 22:01:10 -0000',
            'checklist': [{
                'item': 'CONFECCIÓN CONTRATO',
                'param_value': '{"numero": "G123", "num_multiproducto": "C456"}'
            }],
            'representatives': '[]'
        }]

        self.mock_call_service.post.return_value = (mock_response_data, 200)
        self.mock_maxxa_util.transform_date.return_value = '02-07-2025'

        # Act
        result = self.maxxa_contract.get_client_contract_info('12345678-9')

        # Assert
        assert len(result) == 1
        assert result[0]['contract_date'] == '02-07-2025'
        self.mock_call_service.post.assert_called_once()

    @patch('os.getenv')
    def test_get_client_contract_info_invalid_rut(self, mock_getenv):
        """Test con RUT inválido"""
        # Arrange
        mock_getenv.return_value = 'http://portal-backend.com'
        self.mock_util.validate_rut.return_value = False

        # Act
        result = self.maxxa_contract.get_client_contract_info('invalid-rut')

        # Assert
        assert result == 'El rut "invalid-rut" no es válido'
        self.mock_call_service.post.assert_not_called()

    @patch('os.getenv')
    def test_get_client_contract_info_missing_portal_url(self, mock_getenv):
        """Test cuando falta la URL del portal backend"""
        # Arrange
        mock_getenv.return_value = None

        # Act & Assert
        try:
            self.maxxa_contract.get_client_contract_info('12345678-9')
            assert False, "Debería haber lanzado una excepción"
        except Exception as e:
            assert str(e) == 'missing portal_backend_url'

    @patch('os.getenv')
    def test_get_client_contract_info_404_response(self, mock_getenv):
        """Test cuando el servicio retorna 404"""
        # Arrange
        mock_getenv.return_value = 'http://portal-backend.com'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.post.return_value = ({}, 404)

        # Act
        result = self.maxxa_contract.get_client_contract_info('12345678-9')

        # Assert
        assert result == 'No existe información de contratos para el cliente con rut 12345678-9'

    @patch('os.getenv')
    def test_get_client_contract_info_service_error(self, mock_getenv):
        """Test cuando el servicio retorna error"""
        # Arrange
        mock_getenv.return_value = 'http://portal-backend.com'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.post.return_value = ({}, 500)

        # Act
        result = self.maxxa_contract.get_client_contract_info('12345678-9')

        # Assert
        assert result == 'No se pudo comunicar con portal-backend, intentalo de nuevo'

    @patch('os.getenv')
    def test_get_client_contract_info_correct_payload(self, mock_getenv):
        """Test que el payload enviado al servicio sea correcto"""
        # Arrange
        mock_getenv.return_value = 'http://portal-backend.com'
        self.mock_util.validate_rut.return_value = True
        self.mock_call_service.post.return_value = ([], 200)

        expected_url = 'http://portal-backend.com/tasks-control/search'
        expected_data = {
            'rut_or_name': '12345678-9',
            'status': 'APROBADA',
            'operation_type': ['CONTRATO']
        }

        # Act
        self.maxxa_contract.get_client_contract_info('12345678-9')

        # Assert
        self.mock_call_service.post.assert_called_once_with(
            endpoint=expected_url,
            json_dict=expected_data
        )
