import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SEND_EMAIL = os.getenv("SEND_EMAIL", "false").lower() in ("true", "1", "yes")
MAIL_MAILER = os.getenv("MAIL_MAILER", "outlook").lower()
FROM_EMAIL = os.getenv("FROM_EMAIL", "")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "CreditInfo Tanzania CRM").strip('"')
SHARED_MAILBOX = os.getenv("SHARED_MAILBOX", FROM_EMAIL)
MAILBOX_PASSWORD = os.getenv("MAILBOX_PASSWORD", "")
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID", "")
OUTLOOK_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET", "")
TENANT_ID = os.getenv("TENANT_ID", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

DEFAULT_CC_RECIPIENTS = [
    "Pecy.Mwageni@creditinfo.co.tz",
    "dadila.seddy@creditinfo.co.tz",
    "joseph.mbuya@creditinfo.co.tz",
    "charles.mtauli@creditinfo.co.tz",
]

DATA_DIR = BASE_DIR / "data"
SUBSCRIBER_EMAILS_FILE = DATA_DIR / "subscriber_emails.json"
CC_RECIPIENTS_FILE = DATA_DIR / "cc_recipients.json"
DEACTIVATION_FORM_PATH = DATA_DIR / "User De-activation Request-2018 3.pdf"
DEACTIVATION_FORM_FILENAME = "User De-activation Request Form.pdf"

AUTH_STATE_FILE = DATA_DIR / "auth_state.json"
ACTIVITY_LOG_FILE = DATA_DIR / "activity_log.json"
SEND_HISTORY_FILE = DATA_DIR / "subscriber_send_history.json"
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))


def email_configured() -> bool:
    if not SEND_EMAIL:
        return False
    if MAIL_MAILER == "outlook":
        return bool(OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET and TENANT_ID and (SHARED_MAILBOX or FROM_EMAIL))
    return bool(SMTP_HOST and SHARED_MAILBOX and MAILBOX_PASSWORD)
