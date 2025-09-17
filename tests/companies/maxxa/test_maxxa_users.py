from companies.maxxa.maxxa_users import MaxxaUsers
from unittest.mock import Mock, patch
import pytest
import os
import json

class TestMaxxaContact():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()
        self.mock_util = Mock()
        self.mock_maxxa_util = Mock()

        self.patcher = patch.dict(os.environ, {'USERS_APP_API_URL': 'https://api.test.com'})
        self.patcher.start()

        #instance of certificate
        self.maxxa_users = MaxxaUsers(
            call_service=self.mock_call_service,
            util=self.mock_util,
            maxxa_util=self.mock_maxxa_util
        )

    def teardown_method(self):
        self.patcher.stop()

    def test_get_users_success(self):
        mock_response = [{'name': 'msoto', 'context': 'MASAVAL', 'users': [{'role': 'Leader', 'name': 'juana'}]}]
        self.mock_call_service.get.return_value = (mock_response, 200)
        result = self.maxxa_users.get_users()

        assert 'lider' in result

        self.mock_call_service.get.assert_called_once()

    def test_get_users_missing_url(self):
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception) as e:
                self.maxxa_users.get_users()
            assert str(e.value) == 'missing users_url'

    def test_get_users_service_error(self):
        self.mock_call_service.get.return_value = (None, 500)
        with pytest.raises(Exception) as e:
            self.maxxa_users.get_users()
        assert str(e.value) == 'error calling users service: 500'