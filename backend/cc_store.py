import json
import re
from typing import List

from config import DATA_DIR, DEFAULT_CC_RECIPIENTS

CC_RECIPIENTS_FILE = DATA_DIR / "cc_recipients.json"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email.strip()))


def load_cc_recipients() -> List[str]:
    _ensure_data_dir()
    if not CC_RECIPIENTS_FILE.exists():
        return _save_cc_recipients(list(DEFAULT_CC_RECIPIENTS))

    try:
        with open(CC_RECIPIENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            cleaned = []
            seen = set()
            for item in data:
                email = str(item).strip()
                if email and _validate_email(email):
                    key = _normalize_email(email)
                    if key not in seen:
                        seen.add(key)
                        cleaned.append(email)
            if cleaned:
                return cleaned
    except (json.JSONDecodeError, OSError):
        pass

    return _save_cc_recipients(list(DEFAULT_CC_RECIPIENTS))


def _save_cc_recipients(recipients: List[str]) -> List[str]:
    _ensure_data_dir()
    cleaned = []
    seen = set()
    for email in recipients:
        email = str(email).strip()
        if not email or not _validate_email(email):
            continue
        key = _normalize_email(email)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(email)

    with open(CC_RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    return cleaned


def add_cc_recipient(email: str) -> List[str]:
    if not _validate_email(email):
        raise ValueError(f"Invalid email address: {email}")
    recipients = load_cc_recipients()
    key = _normalize_email(email)
    if any(_normalize_email(r) == key for r in recipients):
        return recipients
    recipients.append(email.strip())
    return _save_cc_recipients(recipients)


def remove_cc_recipient(email: str) -> List[str]:
    key = _normalize_email(email)
    recipients = [r for r in load_cc_recipients() if _normalize_email(r) != key]
    return _save_cc_recipients(recipients)


def set_cc_recipients(recipients: List[str]) -> List[str]:
    return _save_cc_recipients(recipients)
