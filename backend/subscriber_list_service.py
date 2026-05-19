import io
from typing import Dict, List, Optional, Tuple

import pandas as pd

from excel_utils import create_excel_buffer
from package_service import list_subscribers_with_stats
from subscriber_store import load_subscriber_emails, merge_subscriber_emails_from_upload

SUBSCRIBER_COLUMN_ALIASES = [
    'subscriber name', 'subscriber_name', 'subscriber', 'name', 'organisation', 'organization'
]
EMAIL_COLUMN_ALIASES = [
    'email', 'recipient email', 'recipient_email', 'e-mail', 'mail'
]


def _normalize_column(name: str) -> str:
    return str(name).strip().lower().replace('_', ' ')


def _find_column(columns: List[str], aliases: List[str]) -> Optional[str]:
    normalized = {_normalize_column(c): c for c in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def build_subscriber_list_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    subscribers = list_subscribers_with_stats(df)
    saved_emails = load_subscriber_emails()
    rows = []
    for sub in subscribers:
        rows.append({
            'Subscriber Name': sub['name'],
            'Record Count': sub['record_count'],
            'Email': saved_emails.get(sub['name'], ''),
        })
    return pd.DataFrame(rows)


def create_subscriber_list_excel(df: pd.DataFrame) -> bytes:
    list_df = build_subscriber_list_dataframe(df)
    return create_excel_buffer(list_df, 'Subscriber_Emails')


def parse_subscriber_email_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes))
    return pd.read_excel(io.BytesIO(file_bytes))


def import_subscriber_emails_from_dataframe(
    upload_df: pd.DataFrame,
    valid_subscriber_names: List[str],
) -> Tuple[Dict[str, str], dict]:
    upload_df = upload_df.copy()
    upload_df.columns = [str(c).strip() for c in upload_df.columns]

    subscriber_col = _find_column(upload_df.columns.tolist(), SUBSCRIBER_COLUMN_ALIASES)
    email_col = _find_column(upload_df.columns.tolist(), EMAIL_COLUMN_ALIASES)

    if not subscriber_col:
        raise ValueError(
            "Could not find subscriber column. Expected one of: Subscriber Name, subscriber_name, Subscriber"
        )
    if not email_col:
        raise ValueError(
            "Could not find email column. Expected one of: Email, recipient_email, Recipient Email"
        )

    valid_set = {name.strip(): name for name in valid_subscriber_names}
    valid_lower = {name.strip().lower(): name for name in valid_subscriber_names}

    updates = []
    report = {
        'not_found': [],
        'skipped_empty': 0,
        'invalid_email': [],
    }

    for _, row in upload_df.iterrows():
        raw_name = row.get(subscriber_col)
        if pd.isna(raw_name) or not str(raw_name).strip():
            continue

        name_key = str(raw_name).strip()
        matched_name = valid_set.get(name_key) or valid_lower.get(name_key.lower())

        if not matched_name:
            if name_key not in report['not_found']:
                report['not_found'].append(name_key)
            continue

        raw_email = row.get(email_col)
        if pd.isna(raw_email) or not str(raw_email).strip():
            report['skipped_empty'] += 1
            continue

        email = str(raw_email).strip()
        if '@' not in email:
            report['invalid_email'].append({'subscriber': matched_name, 'email': email})
            continue

        updates.append({'subscriber_name': matched_name, 'email': email})

    if updates:
        saved, merge_report = merge_subscriber_emails_from_upload(updates, valid_subscriber_names)
        report.update(merge_report)
    else:
        from subscriber_store import sync_emails_to_active_subscribers
        saved, removed = sync_emails_to_active_subscribers(valid_subscriber_names)
        report['added'] = []
        report['updated'] = []
        report['removed_not_in_data'] = removed
        report['saved_count'] = len(saved)

    return saved, report
