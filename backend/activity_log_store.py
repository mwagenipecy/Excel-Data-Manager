import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import ACTIVITY_LOG_FILE, DATA_DIR


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_activity_logs(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    _ensure_data_dir()
    if not ACTIVITY_LOG_FILE.exists():
        return []
    try:
        with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
        if not isinstance(logs, list):
            return []
        logs = list(reversed(logs))
        if limit is not None:
            logs = logs[:limit]
        return logs
    except (json.JSONDecodeError, OSError):
        return []


def append_activity_log(
    email: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ensure_data_dir()
    entry = {
        "timestamp": _now_iso(),
        "email": email.strip().lower(),
        "action": action,
        "details": details or {},
    }
    logs: List[Dict[str, Any]] = []
    if ACTIVITY_LOG_FILE.exists():
        try:
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                logs = existing
        except (json.JSONDecodeError, OSError):
            logs = []
    logs.append(entry)
    with open(ACTIVITY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    return entry
