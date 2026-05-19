import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import DATA_DIR, SEND_HISTORY_FILE


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_sent_date(sent_at: str) -> str:
    try:
        dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, AttributeError):
        return sent_at[:10] if sent_at and len(sent_at) >= 10 else "unknown"


def _parse_sent_month(sent_at: str) -> str:
    d = _parse_sent_date(sent_at)
    return d[:7] if len(d) >= 7 else "unknown"


def _month_label(month_key: str) -> str:
    try:
        year, mon = month_key.split("-")
        return datetime(int(year), int(mon), 1).strftime("%B %Y")
    except (ValueError, TypeError):
        return month_key


def _filter_sends(
    sends: List[Dict[str, Any]],
    date: Optional[str] = None,
    month: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    result = []
    for entry in sends:
        d = _parse_sent_date(entry.get("sent_at", ""))
        if d == "unknown":
            continue
        if date and d != date:
            continue
        if month and _parse_sent_month(entry.get("sent_at", "")) != month:
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        result.append(entry)
    return result


def _migrate_legacy_history(data: Any) -> List[Dict[str, Any]]:
    """Convert old month-keyed format to flat send list."""
    if isinstance(data, dict) and "sends" in data:
        sends = data["sends"]
        return sends if isinstance(sends, list) else []

    if not isinstance(data, dict):
        return []

    sends: List[Dict[str, Any]] = []
    for _month, subs in data.items():
        if not isinstance(subs, dict):
            continue
        for name, info in subs.items():
            if not isinstance(info, dict):
                continue
            sends.append({
                "subscriber_name": name,
                "sent_at": info.get("sent_at") or _now_iso(),
                "sent_by": info.get("sent_by", ""),
                "recipient_email": info.get("recipient_email", ""),
            })
    return sends


def load_sends() -> List[Dict[str, Any]]:
    _ensure_data_dir()
    if not SEND_HISTORY_FILE.exists():
        return []
    try:
        with open(SEND_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        sends = _migrate_legacy_history(data)
        return sorted(sends, key=lambda s: s.get("sent_at") or "", reverse=True)
    except (json.JSONDecodeError, OSError):
        return []


def save_sends(sends: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(SEND_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"sends": sends}, f, indent=2, ensure_ascii=False)


def record_subscriber_send(
    subscriber_name: str,
    sent_by: str,
    recipient_email: str = "",
) -> Dict[str, Any]:
    if not subscriber_name:
        return {}
    sends = load_sends()
    entry = {
        "subscriber_name": subscriber_name,
        "sent_at": _now_iso(),
        "sent_by": sent_by.strip().lower(),
        "recipient_email": recipient_email.strip(),
    }
    sends.insert(0, entry)
    save_sends(sends)
    return entry


def get_last_send_for_subscriber(subscriber_name: str) -> Optional[Dict[str, Any]]:
    for entry in load_sends():
        if entry.get("subscriber_name") == subscriber_name:
            return entry
    return None


def build_report_grouped_by_date(
    date_filter: Optional[str] = None,
    month_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    all_sends = load_sends()
    sends = _filter_sends(
        all_sends,
        date=date_filter,
        month=month_filter,
        date_from=date_from,
        date_to=date_to,
    )

    groups_map: Dict[str, List[Dict[str, Any]]] = {}
    for entry in sends:
        date_key = _parse_sent_date(entry.get("sent_at", ""))
        groups_map.setdefault(date_key, []).append({
            "subscriber_name": entry.get("subscriber_name"),
            "recipient_email": entry.get("recipient_email", ""),
            "sent_at": entry.get("sent_at"),
            "sent_by": entry.get("sent_by"),
            "date": date_key,
        })

    groups = []
    for date_key in sorted(groups_map.keys(), reverse=True):
        try:
            dt = datetime.strptime(date_key, "%Y-%m-%d")
            date_label = dt.strftime("%d %B %Y")
        except ValueError:
            date_label = date_key
        records = sorted(groups_map[date_key], key=lambda r: r.get("sent_at") or "", reverse=True)
        groups.append({
            "date": date_key,
            "date_label": date_label,
            "sent_count": len(records),
            "records": records,
        })

    date_options = []
    seen_dates = set()
    for s in all_sends:
        dk = _parse_sent_date(s.get("sent_at", ""))
        if dk == "unknown" or dk in seen_dates:
            continue
        seen_dates.add(dk)
    for dk in sorted(seen_dates, reverse=True):
        try:
            dt = datetime.strptime(dk, "%Y-%m-%d")
            label = dt.strftime("%d %B %Y")
        except ValueError:
            label = dk
        count = sum(1 for s in all_sends if _parse_sent_date(s.get("sent_at", "")) == dk)
        date_options.append({"value": dk, "label": label, "sent_count": count})

    month_counts: Dict[str, int] = {}
    for s in all_sends:
        mk = _parse_sent_month(s.get("sent_at", ""))
        if mk != "unknown":
            month_counts[mk] = month_counts.get(mk, 0) + 1
    month_options = [
        {"value": mk, "label": _month_label(mk), "sent_count": month_counts[mk]}
        for mk in sorted(month_counts.keys(), reverse=True)
    ]

    filter_label_parts = []
    if month_filter:
        filter_label_parts.append(_month_label(month_filter))
    elif date_from or date_to:
        if date_from and date_to:
            filter_label_parts.append(f"{date_from} to {date_to}")
        elif date_from:
            filter_label_parts.append(f"from {date_from}")
        else:
            filter_label_parts.append(f"until {date_to}")
    elif date_filter:
        try:
            filter_label_parts.append(datetime.strptime(date_filter, "%Y-%m-%d").strftime("%d %B %Y"))
        except ValueError:
            filter_label_parts.append(date_filter)

    return {
        "date": date_filter,
        "month": month_filter,
        "date_from": date_from,
        "date_to": date_to,
        "filter_label": ", ".join(filter_label_parts) if filter_label_parts else None,
        "total_sent": len(sends),
        "dates": date_options,
        "months": month_options,
        "groups": groups,
    }
