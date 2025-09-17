from companies.maxxa.maxxa_email import MaxxaEmail
from unittest.mock import Mock, patch
import pytest
import os


class TestMaxxaEmail():

    def setup_method(self):
        #dependencies
        self.mock_call_service = Mock()

        self.patcher = patch.dict(os.environ, {'MAIL_APP_URL': 'https://mail-app.test.com'})
        self.patcher.start()

        #instance of certificate
        self.maxxa_email = MaxxaEmail(
            call_service=self.mock_call_service,
        )

    def teardown_method(self):
        self.patcher.stop()

    def test_get_client_contact_info_success(self):
        subject = 'Test Subject'
        body = 'Test Body'
        to = 'test@example.com'
        base64_data = 'example-base64-data'
        filename = 'example-filename'
        content_type = 'application/pdf'
        attachments = [{'content': base64_data, 'filename': filename, 'content_type': content_type}]

        mock_response = {
            'message': 'Email sent successfully'
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        result = self.maxxa_email.send_email(
            subject=subject,
            body=body,
            to_email=to,
            attachments=attachments
        )

        assert result == 'El correo se ha enviado correctamente'
        self.mock_call_service.post.assert_called_once()

    def test_send_email_when_not_valid_email(self):
        subject = 'Test Subject'
        body = 'Test Body'
        to = 'example.com'
        base64_data = 'example-base64-data'
        filename = 'example-filename'
        content_type = 'application/pdf'
        attachments = [{'content': base64_data, 'filename': filename, 'content_type': content_type}]

        result = self.maxxa_email.send_email(
            subject=subject,
            body=body,
            to_email=to,
            attachments=attachments
        )

        assert result == 'El email de destino es incorrecto (INVALID_EMAIL)'
        self.mock_call_service.post.assert_not_called()

    def test_send_email_multiple_attachments(self):
        subject = 'Test Subject'
        body = 'Test Body'
        to = 'test@example.com'
        base64_data = 'example-base64-data'
        filename = 'example-filename'
        content_type = 'application/pdf'
        attachments = [
            {'content': base64_data, 'filename': filename, 'content_type': content_type},
            {'content': base64_data, 'filename': filename, 'content_type': content_type},
            {'content': base64_data, 'filename': filename, 'content_type': content_type},
        ]

        mock_response = {
            'message': 'Email sent successfully'
        }
        self.mock_call_service.post.return_value = (mock_response, 200)
        result = self.maxxa_email.send_email(
            subject=subject,
            body=body,
            to_email=to,
            attachments=attachments
        )

        assert result == 'El correo se ha enviado correctamente'
        self.mock_call_service.post.assert_called_once()


    def test_send_email_service_error(self):
        subject = 'Test Subject'
        body = 'Test Body'
        to = 'test@example.com'
        base64_data = 'example-base64-data'
        filename = 'example-filename'
        content_type = 'application/pdf'
        attachments = [{'content': base64_data, 'filename': filename, 'content_type': content_type}]

        mock_response = {
            'error_type': 'service_error',
            'message': 'no pude comunicarme con el libro de contactos, intentalo de nuevo'
        }
        self.mock_call_service.post.return_value = (mock_response, 500)
        result = self.maxxa_email.send_email(
            subject=subject,
            body=body,
            to_email=to,
            attachments=attachments
        )

        assert result == 'Ha ocurrido un error al intentar enviar el correo, service_error, no pude comunicarme con el libro de contactos, intentalo de nuevo'
        self.mock_call_service.post.assert_called_once()
