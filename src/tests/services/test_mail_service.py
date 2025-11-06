# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from unittest.mock import MagicMock
from iatoolkit.services.mail_service import MailService
from iatoolkit.services.i18n_service import I18nService

class TestMailService:

    def setup_method(self):
        self.mock_mail_app = MagicMock()
        self.mock_i18n_service = MagicMock(spec=I18nService)

        self.mock_i18n_service.t.side_effect = lambda key, **kwargs: f"translated:{key}"

        # Instancia de MailService con la dependencia inyectada como mock
        self.mail_service = MailService(mail_app=self.mock_mail_app, i18n_service=self.mock_i18n_service)

        # Datos por defecto para enviar email
        self.recipient = 'destinatario@test.com'
        self.subject = 'Prueba'
        self.body = 'Contenido del mensaje'


    def test_send_mail_when_success(self):
        result = self.mail_service.send_mail(
            recipient=self.recipient,
            subject=self.subject,
            body=self.body,
            attachments=[]
        )

        # Comprobamos si mail_app.send_email fue invocado correctamente
        self.mock_mail_app.send_email.assert_called_once_with(
            sender={'email': 'iatoolkit@iatoolkit.com', 'name': 'IAToolkit'},
            to=self.recipient,
            subject=self.subject,
            body=self.body,
            attachments=[]        )
        assert result == 'translated:services.mail_sent'

    def test_send_mail_when_no_recipient(self):
        # Probamos el comportamiento cuando falta el receptor del mensaje
        result = self.mail_service.send_mail(
            subject=self.subject,
            body=self.body
        )

        '''
        self.mock_mail_app.send_email.assert_called_once_with(
            sender={'email': 'iatoolkit@iatoolkit.com', 'name': 'IAToolkit'},
            to=None,
            subject=self.subject,
            body=self.body,
            attach=None,
            attachments=None
        )
        assert result == 'mail enviado'
        '''

    def test_send_mail_partial_args(self):
        # Comprobamos cuando faltan parcialmente argumentos como subject y body
        result = self.mail_service.send_mail(recipient=self.recipient)

        self.mock_mail_app.send_email.assert_called_once_with(
            sender={'email': 'iatoolkit@iatoolkit.com', 'name': 'IAToolkit'},
            to=self.recipient,
            subject=None,
            body=None,
            attachments=[] )
        assert result == 'translated:services.mail_sent'
