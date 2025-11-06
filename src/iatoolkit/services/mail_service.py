# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.infra.mail_app import MailApp
from iatoolkit.services.i18n_service import I18nService
from injector import inject
from pathlib import Path
from iatoolkit.common.exceptions import IAToolkitException
import base64

TEMP_DIR = Path("static/temp")

class MailService:
    @inject
    def __init__(self,
                 mail_app: MailApp,
                 i18n_service: I18nService):
        self.mail_app = mail_app
        self.i18n_service = i18n_service


    def _read_token_bytes(self, token: str) -> bytes:
        # Defensa simple contra path traversal
        if not token or "/" in token or "\\" in token or token.startswith("."):
            raise IAToolkitException(IAToolkitException.ErrorType.MAIL_ERROR,
                               "attachment_token invalid")
        path = TEMP_DIR / token
        if not path.is_file():
            raise IAToolkitException(IAToolkitException.ErrorType.MAIL_ERROR,
                               f"attach file not found: {token}")
        return path.read_bytes()

    def send_mail(self, **kwargs):
        from_email = kwargs.get('from_email', 'iatoolkit@iatoolkit.com')
        recipient = kwargs.get('recipient')
        subject = kwargs.get('subject')
        body = kwargs.get('body')
        attachments = kwargs.get('attachments')

        # Normalizar a payload de MailApp (name + base64 content)
        norm_attachments = []
        for a in attachments or []:
            if a.get("attachment_token"):
                raw = self._read_token_bytes(a["attachment_token"])
                norm_attachments.append({
                    "filename": a["filename"],
                    "content": base64.b64encode(raw).decode("utf-8"),
                })
            else:
                # asumo que ya viene un base64
                norm_attachments.append({
                    "filename": a["filename"],
                    "content": a["content"]
                })

        self.sender = {"email": from_email, "name": "IAToolkit"}

        response = self.mail_app.send_email(
            sender=self.sender,
            to=recipient,
            subject=subject,
            body=body,
            attachments=norm_attachments)

        return self.i18n_service.t('services.mail_sent')
