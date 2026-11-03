from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import structlog

log = structlog.get_logger()


class EmailChannel:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str,
        start_tls: bool = True,
    ):
        self.start_tls = start_tls
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name

    async def send(
        self, to_email: str, subject: str, body: str, html_body: str = None, attachment: tuple[str, str] = None
    ) -> bool:
        """[attachment] is a CSV's (file name, text)."""
        try:
            text = MIMEMultipart("alternative")
            text.attach(MIMEText(body, "plain"))
            if html_body:
                text.attach(MIMEText(html_body, "html"))
            if attachment:
                msg = MIMEMultipart("mixed")
                msg.attach(text)
                part = MIMEApplication(attachment[1].encode("utf-8"), _subtype="csv")
                part.add_header("Content-Disposition", "attachment", filename=attachment[0])
                msg.attach(part)
            else:
                msg = text
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username or None,
                password=self.password or None,
                start_tls=self.start_tls,
            )
            log.info("email_sent", subject=subject)
            return True
        except Exception as e:
            log.error("email_send_failed", error=str(e))
            return False
