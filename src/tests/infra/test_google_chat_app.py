# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from unittest.mock import Mock, patch
from iatoolkit.infra.google_chat_app import GoogleChatApp


class TestGoogleChatApp:
    @pytest.fixture
    def mock_call_service(self):
        return Mock()

    @pytest.fixture
    def google_chat_service(self, mock_call_service):
        return GoogleChatApp(mock_call_service)

    def test_send_message_success(self, google_chat_service, mock_call_service):
        # Configurar el mock
        mock_call_service.post.return_value = ({"status": "sent"}, 200)

        message_data = {
            "type": "MESSAGE_TRIGGER",
            "space": {
                "name": "spaces/AAQAupQldd4"
            },
            "message": {
                "text": "Test message"
            }
        }

        with patch.dict('os.environ', {'GOOGLE_CHAT_BOT_URL': 'https://test-bot.com'}):
            result = google_chat_service.send_message(message_data=message_data)

        assert result['success'] is True
        assert result['message'] == "Mensaje enviado correctamente"
        mock_call_service.post.assert_called_once_with('https://test-bot.com', message_data)

    def test_send_message_missing_env_var(self, google_chat_service):
        message_data = {
            "type": "MESSAGE_TRIGGER",
            "space": {"name": "spaces/test"},
            "message": {"text": "Test"}
        }

        with patch.dict('os.environ', {}, clear=True):
            result = google_chat_service.send_message(message_data=message_data)

        assert result['success'] is False
        assert "GOOGLE_CHAT_BOT_URL no está configurada" in result['message']

    def test_send_message_api_error(self, google_chat_service, mock_call_service):
        # Configurar el mock para simular error
        mock_call_service.post.return_value = ({"error": "API Error"}, 500)

        message_data = {
            "type": "MESSAGE_TRIGGER",
            "space": {"name": "spaces/test"},
            "message": {"text": "Test"}
        }

        with patch.dict('os.environ', {'GOOGLE_CHAT_BOT_URL': 'https://test-bot.com'}):
            result = google_chat_service.send_message(message_data=message_data)

        assert result['success'] is False
        assert "Error al enviar mensaje" in result['message']
