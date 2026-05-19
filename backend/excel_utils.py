import io
from datetime import datetime
from typing import Optional

import pandas as pd

EXCLUDED_COLUMNS = [
    'Is Open', 'Position', 'Expiry Date', 'Needs To Change Password',
    'Branch Name', 'Close Reason', 'User ID', 'Use Admin Log'
]


def create_excel_buffer(df, sheet_name='Data'):
    df_clean = df.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            df_clean[col] = df_clean[col].astype(str).replace(['nan', 'None', 'NaN'], '')
        df_clean[col] = df_clean[col].fillna('')

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_clean.to_excel(writer, sheet_name=sheet_name, index=False, na_rep='')

    excel_content = excel_buffer.getvalue()
    if len(excel_content) == 0:
        raise ValueError("Generated Excel file is empty")
    return excel_content


def filter_dataframe_for_download_all(df):
    if 'Is Open' not in df.columns:
        return df.copy()
    return df[df['Is Open'].astype(str).str.lower().isin(['yes', 'true', '1', 'active'])].copy()


def prepare_dataframe_for_excel(df):
    df_copy = df.copy()
    columns_to_remove = [col for col in EXCLUDED_COLUMNS if col in df_copy.columns]
    if columns_to_remove:
        df_copy = df_copy.drop(columns=columns_to_remove)
    return df_copy


def create_safe_filename(name, fallback_prefix="File"):
    if not name or str(name).strip() == '':
        return f"{fallback_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    safe_name = "".join(c for c in str(name) if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_name:
        safe_name = f"{fallback_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    return safe_name


def get_active_subscribers_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    filtered_df = filter_dataframe_for_download_all(df)
    if len(filtered_df) == 0:
        raise ValueError("No active users found")
    if 'Subscriber Name' not in filtered_df.columns:
        raise ValueError("'Subscriber Name' column not found in data")
    return filtered_df
