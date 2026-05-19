import io
import zipfile
from typing import Dict, List, Tuple

import pandas as pd

from excel_utils import (
    create_excel_buffer,
    create_safe_filename,
    get_active_subscribers_dataframe,
    prepare_dataframe_for_excel,
)


def list_subscribers_with_stats(df: pd.DataFrame) -> List[dict]:
    filtered_df = get_active_subscribers_dataframe(df)
    if len(filtered_df) == 0:
        return []
    subscriber_stats = filtered_df.groupby('Subscriber Name').size().reset_index(name='record_count')
    subscriber_stats = subscriber_stats.sort_values('Subscriber Name')

    subscribers = []
    for _, row in subscriber_stats.iterrows():
        name = row['Subscriber Name']
        subscribers.append({
            "name": name,
            "record_count": int(row['record_count']),
            "safe_filename": create_safe_filename(name, "Subscriber"),
        })
    return subscribers


def create_subscriber_excel_bytes(df: pd.DataFrame, subscriber_name: str) -> Tuple[bytes, str]:
    filtered_df = get_active_subscribers_dataframe(df)
    subscriber_df = filtered_df[filtered_df['Subscriber Name'] == subscriber_name].copy()
    if len(subscriber_df) == 0:
        raise ValueError(f"No active records found for subscriber: {subscriber_name}")

    prepared_df = prepare_dataframe_for_excel(subscriber_df)
    excel_content = create_excel_buffer(prepared_df, 'Data')
    safe_name = create_safe_filename(subscriber_name, "Subscriber")
    filename = f"{safe_name}_data.xlsx"
    return excel_content, filename


def create_subscriber_zip_bytes(df: pd.DataFrame, subscriber_name: str) -> Tuple[bytes, str]:
    excel_content, excel_filename = create_subscriber_excel_bytes(df, subscriber_name)
    safe_name = create_safe_filename(subscriber_name, "Subscriber")
    zip_filename = f"{safe_name}_data.zip"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        zip_file.writestr(excel_filename, excel_content)

    return zip_buffer.getvalue(), zip_filename


def create_all_subscriber_packages(df: pd.DataFrame) -> Dict[str, Tuple[bytes, str]]:
    packages = {}
    for subscriber in list_subscribers_with_stats(df):
        name = subscriber["name"]
        zip_bytes, zip_name = create_subscriber_zip_bytes(df, name)
        packages[name] = (zip_bytes, zip_name)
    return packages
