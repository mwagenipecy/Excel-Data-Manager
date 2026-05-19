import json
from typing import Dict, List, Optional, Tuple

from config import DATA_DIR, SUBSCRIBER_EMAILS_FILE


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_subscriber_emails() -> Dict[str, str]:
    _ensure_data_dir()
    if not SUBSCRIBER_EMAILS_FILE.exists():
        return {}
    try:
        with open(SUBSCRIBER_EMAILS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v).strip() for k, v in data.items() if v}
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_subscriber_emails(mappings: Dict[str, str]) -> Dict[str, str]:
    _ensure_data_dir()
    cleaned = {str(k): str(v).strip() for k, v in mappings.items() if k and v and str(v).strip()}
    with open(SUBSCRIBER_EMAILS_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    return cleaned


def sync_emails_to_active_subscribers(valid_subscriber_names: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """Remove saved emails for subscribers that no longer exist in current active data."""
    valid_set = set(valid_subscriber_names)
    mappings = load_subscriber_emails()
    removed = [name for name in list(mappings.keys()) if name not in valid_set]
    for name in removed:
        del mappings[name]
    return save_subscriber_emails(mappings), removed


def update_subscriber_email(subscriber_name: str, email: str) -> Dict[str, str]:
    mappings = load_subscriber_emails()
    if email.strip():
        mappings[subscriber_name] = email.strip()
    elif subscriber_name in mappings:
        del mappings[subscriber_name]
    return save_subscriber_emails(mappings)


def bulk_update_subscriber_emails(
    updates: List[dict],
    valid_subscriber_names: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Merge email updates from UI. Optionally prune subscribers not in active data."""
    mappings = load_subscriber_emails()
    valid_set = set(valid_subscriber_names) if valid_subscriber_names is not None else None

    for item in updates:
        name = item.get("subscriber_name", "").strip()
        email = item.get("email", "").strip()
        if not name:
            continue
        if valid_set is not None and name not in valid_set:
            continue
        if email:
            mappings[name] = email
        elif name in mappings:
            del mappings[name]

    if valid_set is not None:
        for name in list(mappings.keys()):
            if name not in valid_set:
                del mappings[name]

    return save_subscriber_emails(mappings)


def merge_subscriber_emails_from_upload(
    updates: List[dict],
    valid_subscriber_names: List[str],
) -> Tuple[Dict[str, str], dict]:
    """
    Merge uploaded emails into existing saved list (does not wipe unrelated entries first).
    Then sync: remove subscribers not in current active data; add/update from upload file.
    """
    valid_set = set(valid_subscriber_names)
    mappings = load_subscriber_emails()

    removed_not_in_data = [name for name in list(mappings.keys()) if name not in valid_set]
    for name in removed_not_in_data:
        del mappings[name]

    added = []
    updated = []
    for item in updates:
        name = item.get("subscriber_name", "").strip()
        email = item.get("email", "").strip()
        if not name or not email or name not in valid_set:
            continue
        if name in mappings:
            if name not in updated:
                updated.append(name)
        else:
            added.append(name)
        mappings[name] = email

    saved = save_subscriber_emails(mappings)
    return saved, {
        "added": added,
        "updated": updated,
        "removed_not_in_data": removed_not_in_data,
        "saved_count": len(saved),
    }


def get_email_for_subscriber(subscriber_name: str) -> Optional[str]:
    return load_subscriber_emails().get(subscriber_name)
