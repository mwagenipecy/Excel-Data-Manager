import base64
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional, Tuple

import httpx
import msal

from cc_store import load_cc_recipients
from config import (
    DEACTIVATION_FORM_FILENAME,
    DEACTIVATION_FORM_PATH,
    FROM_EMAIL,
    MAIL_FROM_NAME,
    MAIL_MAILER,
    MAILBOX_PASSWORD,
    OUTLOOK_CLIENT_ID,
    OUTLOOK_CLIENT_SECRET,
    SEND_EMAIL,
    SHARED_MAILBOX,
    SMTP_HOST,
    SMTP_PORT,
    TENANT_ID,
    email_configured,
)

# (bytes, filename, content_type)
Attachment = Tuple[bytes, str, str]


class EmailServiceError(Exception):
    pass


def get_cc_recipients() -> List[str]:
    return load_cc_recipients()


def _sender_address() -> str:
    return SHARED_MAILBOX or FROM_EMAIL


def load_deactivation_form_attachment() -> Attachment:
    path = Path(DEACTIVATION_FORM_PATH)
    if not path.is_file():
        raise EmailServiceError(
            f"Deactivation form not found at {path}. "
            "Place the PDF in backend/data/."
        )
    return path.read_bytes(), DEACTIVATION_FORM_FILENAME, "application/pdf"


def build_subscriber_email_body(subscriber_name: str, custom_message: Optional[str] = None) -> str:
    deactivation_section = (
        "<p><strong>User deactivation:</strong> "
        "If you need to deactivate any user, please complete the attached "
        "<em>User De-activation Request Form</em> and return it to CreditInfo Tanzania.</p>"
    )

    if custom_message:
        return (
            f"{custom_message}"
            f"<p>Please find attached:</p>"
            f"<ul>"
            f"<li><strong>{subscriber_name}</strong> — CRM user data export (ZIP)</li>"
            f"<li>User De-activation Request Form (PDF)</li>"
            f"</ul>"
            f"{deactivation_section}"
            f"<p>Regards,<br>{MAIL_FROM_NAME}</p>"
        )

    return (
        f"<p>Dear Partner,</p>"
        f"<p>Please find attached the CRM user data export for "
        f"<strong>{subscriber_name}</strong>. This ZIP file contains active user "
        f"records for your organization.</p>"
        f"<p>Also attached is the <strong>User De-activation Request Form</strong> (PDF).</p>"
        f"{deactivation_section}"
        f"<p>Should you have any questions, please contact CreditInfo Tanzania.</p>"
        f"<p>Regards,<br>{MAIL_FROM_NAME}</p>"
    )


def _graph_access_token() -> str:
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        OUTLOOK_CLIENT_ID,
        authority=authority,
        client_credential=OUTLOOK_CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        error = result.get("error_description") or result.get("error") or "Unknown authentication error"
        raise EmailServiceError(f"Failed to acquire Graph token: {error}")
    return result["access_token"]


def _graph_attachment_payload(attachment: Attachment) -> dict:
    data, filename, content_type = attachment
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": filename,
        "contentType": content_type,
        "contentBytes": base64.b64encode(data).decode("utf-8"),
    }


def _send_via_graph(
    to_email: str,
    subject: str,
    html_body: str,
    attachments: List[Attachment],
    cc_recipients: List[str],
) -> None:
    token = _graph_access_token()
    sender = _sender_address()

    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "from": {
                "emailAddress": {
                    "address": sender,
                    "name": MAIL_FROM_NAME,
                }
            },
            "toRecipients": [{"emailAddress": {"address": to_email}}],
            "ccRecipients": [{"emailAddress": {"address": addr}} for addr in cc_recipients],
            "attachments": [_graph_attachment_payload(a) for a in attachments],
        },
        "saveToSentItems": True,
    }

    url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=message)
        if response.status_code >= 400:
            raise EmailServiceError(f"Graph API error ({response.status_code}): {response.text}")


def _send_via_smtp(
    to_email: str,
    subject: str,
    html_body: str,
    attachments: List[Attachment],
    cc_recipients: List[str],
) -> None:
    sender = _sender_address()
    msg = MIMEMultipart()
    msg["From"] = f"{MAIL_FROM_NAME} <{sender}>"
    msg["To"] = to_email
    msg["Cc"] = ", ".join(cc_recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    for data, filename, content_type in attachments:
        subtype = content_type.split("/")[-1] if "/" in content_type else "octet-stream"
        part = MIMEApplication(data, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    recipients = [to_email] + cc_recipients
    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(sender, MAILBOX_PASSWORD)
        server.sendmail(sender, recipients, msg.as_string())


def send_subscriber_email(
    to_email: str,
    subscriber_name: str,
    attachment_bytes: bytes,
    attachment_filename: str,
    subject: Optional[str] = None,
    message: Optional[str] = None,
    cc_recipients: Optional[List[str]] = None,
) -> dict:
    if not SEND_EMAIL:
        raise EmailServiceError("Email sending is disabled. Set SEND_EMAIL=true in .env")
    if not email_configured():
        raise EmailServiceError("Email is not fully configured. Check .env settings.")

    cc_list = cc_recipients if cc_recipients is not None else get_cc_recipients()
    email_subject = subject or f"CRM User Data & Deactivation Form - {subscriber_name}"
    email_body = build_subscriber_email_body(subscriber_name, message)

    attachments: List[Attachment] = [
        (attachment_bytes, attachment_filename, "application/zip"),
        load_deactivation_form_attachment(),
    ]

    if MAIL_MAILER == "outlook" and OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET and TENANT_ID:
        _send_via_graph(to_email, email_subject, email_body, attachments, cc_list)
        method = "microsoft_graph"
    else:
        _send_via_smtp(to_email, email_subject, email_body, attachments, cc_list)
        method = "smtp"

    return {
        "to": to_email,
        "cc": cc_list,
        "subject": email_subject,
        "attachments": [attachment_filename, DEACTIVATION_FORM_FILENAME],
        "method": method,
    }


def send_simple_email(to_email: str, subject: str, html_body: str) -> dict:
    """Send a plain HTML email (no attachments) — used for OTP codes."""
    if not SEND_EMAIL:
        raise EmailServiceError("Email sending is disabled. Set SEND_EMAIL=true in .env")
    if not email_configured():
        raise EmailServiceError("Email is not fully configured. Check .env settings.")

    if MAIL_MAILER == "outlook" and OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET and TENANT_ID:
        _send_via_graph(to_email, subject, html_body, [], [])
        method = "microsoft_graph"
    else:
        _send_via_smtp(to_email, subject, html_body, [], [])
        method = "smtp"

    return {"to": to_email, "subject": subject, "method": method}
