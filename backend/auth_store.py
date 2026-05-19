import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import AUTH_STATE_FILE, DATA_DIR, OTP_EXPIRE_MINUTES


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_state() -> Dict[str, Any]:
    return {
        "active_session": None,
        "pending_requests": [],
        "otps": {},
    }


def load_auth_state() -> Dict[str, Any]:
    _ensure_data_dir()
    if not AUTH_STATE_FILE.exists():
        return _default_state()
    try:
        with open(AUTH_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_state()
        data.setdefault("active_session", None)
        data.setdefault("pending_requests", [])
        data.setdefault("otps", {})
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def save_auth_state(state: Dict[str, Any]) -> None:
    _ensure_data_dir()
    with open(AUTH_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def store_otp(email: str, code: str) -> None:
    state = load_auth_state()
    expires_at = (_now() + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat()
    state["otps"][normalize_email(email)] = {
        "code": code,
        "expires_at": expires_at,
    }
    save_auth_state(state)


def verify_otp_code(email: str, code: str) -> bool:
    state = load_auth_state()
    entry = state["otps"].get(normalize_email(email))
    if not entry:
        return False
    if entry.get("code") != code.strip():
        return False
    try:
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False
    if _now() > expires_at:
        return False
    del state["otps"][normalize_email(email)]
    save_auth_state(state)
    return True


def get_active_session() -> Optional[Dict[str, Any]]:
    return load_auth_state().get("active_session")


def create_session(email: str) -> Dict[str, Any]:
    state = load_auth_state()
    session = {
        "email": normalize_email(email),
        "token": secrets.token_urlsafe(32),
        "created_at": _now().isoformat(),
    }
    state["active_session"] = session
    state["pending_requests"] = []
    save_auth_state(state)
    return session


def clear_session() -> None:
    state = load_auth_state()
    state["active_session"] = None
    save_auth_state(state)


def validate_token(token: str) -> Optional[str]:
    session = get_active_session()
    if not session:
        return None
    if session.get("token") == token:
        return session.get("email")
    return None


def add_pending_login_request(email: str) -> Dict[str, Any]:
    state = load_auth_state()
    normalized = normalize_email(email)
    for req in state["pending_requests"]:
        if req.get("email") == normalized and req.get("status") == "pending":
            return req
    request = {
        "id": str(uuid.uuid4()),
        "email": normalized,
        "requested_at": _now().isoformat(),
        "status": "pending",
    }
    state["pending_requests"].append(request)
    save_auth_state(state)
    return request


def get_pending_requests() -> List[Dict[str, Any]]:
    state = load_auth_state()
    return [r for r in state.get("pending_requests", []) if r.get("status") == "pending"]


def get_login_request(request_id: str) -> Optional[Dict[str, Any]]:
    state = load_auth_state()
    for req in state.get("pending_requests", []):
        if req.get("id") == request_id:
            return req
    return None


def resolve_login_request(request_id: str, approved: bool) -> Optional[Dict[str, Any]]:
    state = load_auth_state()
    target = None
    for req in state.get("pending_requests", []):
        if req.get("id") == request_id:
            target = req
            break
    if not target:
        return None
    target["status"] = "approved" if approved else "denied"
    target["resolved_at"] = _now().isoformat()
    save_auth_state(state)
    return target


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"
