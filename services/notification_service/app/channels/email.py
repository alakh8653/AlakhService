import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import structlog

log = structlog.get_logger()

class EmailChannel:
    def __init__(self, host: str, port: int, username: str, password: str, from_email: str, from_name: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name

    async def send(self, to_email: str, subject: str, body: str, html_body: str = None) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg.attach(MIMEText(body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=True,
            )
            log.info("email_sent", to=to_email, subject=subject)
            return True
        except Exception as e:
            log.error("email_send_failed", error=str(e), to=to_email)
            return False
