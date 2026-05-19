from typing import Any, Dict, Optional

from activity_log_store import append_activity_log
from auth_store import (
    add_pending_login_request,
    clear_session,
    create_session,
    generate_otp_code,
    get_active_session,
    get_login_request,
    normalize_email,
    resolve_login_request,
    store_otp,
    verify_otp_code,
)
from config import MAIL_FROM_NAME, SEND_EMAIL
from email_service import EmailServiceError, send_simple_email


def request_otp(email: str) -> Dict[str, Any]:
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("A valid email address is required.")

    code = generate_otp_code()
    store_otp(normalized, code)

    subject = "Your login code — Excel Data Manager"
    body = (
        f"<p>Hello,</p>"
        f"<p>Your one-time login code is:</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>This code expires in 10 minutes. If you did not request this, you can ignore this email.</p>"
        f"<p>Regards,<br>{MAIL_FROM_NAME}</p>"
    )

    otp_sent = False
    dev_code: Optional[str] = None
    if SEND_EMAIL:
        try:
            send_simple_email(normalized, subject, body)
            otp_sent = True
        except EmailServiceError:
            dev_code = code
    else:
        dev_code = code
        print(f"[DEV] OTP for {normalized}: {code}")

    return {
        "message": "OTP sent to your email." if otp_sent else "OTP generated (check server console if email is disabled).",
        "email": normalized,
        "otp_sent": otp_sent,
        "dev_code": dev_code,
    }


def verify_otp_and_login(email: str, code: str) -> Dict[str, Any]:
    normalized = normalize_email(email)
    if not verify_otp_code(normalized, code):
        raise ValueError("Invalid or expired OTP code.")

    active = get_active_session()
    if active and active.get("email") != normalized:
        request = add_pending_login_request(normalized)
        append_activity_log(
            normalized,
            "login_requested",
            {"active_user": active.get("email"), "request_id": request["id"]},
        )
        return {
            "status": "pending_approval",
            "message": f"Another user ({active.get('email')}) is currently logged in. Waiting for approval.",
            "request_id": request["id"],
            "active_user": active.get("email"),
        }

    session = create_session(normalized)
    append_activity_log(normalized, "login", {})
    return {
        "status": "authenticated",
        "token": session["token"],
        "email": session["email"],
    }


def approve_login_request(request_id: str, approver_email: str) -> Dict[str, Any]:
    request = get_login_request(request_id)
    if not request or request.get("status") != "pending":
        raise ValueError("Login request not found or already resolved.")

    active = get_active_session()
    if not active or active.get("email") != approver_email:
        raise ValueError("Only the currently logged-in user can approve login requests.")

    resolved = resolve_login_request(request_id, approved=True)
    previous_email = active.get("email")
    clear_session()
    session = create_session(resolved["email"])

    append_activity_log(approver_email, "login_approved", {"for_email": resolved["email"]})
    append_activity_log(resolved["email"], "login", {"approved_by": approver_email})
    append_activity_log(previous_email, "session_ended", {"reason": "approved_new_login"})

    return {
        "status": "approved",
        "token": session["token"],
        "email": session["email"],
        "for_email": resolved["email"],
    }


def deny_login_request(request_id: str, denier_email: str) -> Dict[str, Any]:
    request = get_login_request(request_id)
    if not request or request.get("status") != "pending":
        raise ValueError("Login request not found or already resolved.")

    active = get_active_session()
    if not active or active.get("email") != denier_email:
        raise ValueError("Only the currently logged-in user can deny login requests.")

    resolved = resolve_login_request(request_id, approved=False)
    append_activity_log(denier_email, "login_denied", {"for_email": resolved["email"]})

    return {"status": "denied", "for_email": resolved["email"]}


def logout_user(email: str) -> None:
    active = get_active_session()
    if active and active.get("email") == email:
        clear_session()
        append_activity_log(email, "logout", {})
