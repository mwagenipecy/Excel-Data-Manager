from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from cc_store import add_cc_recipient, load_cc_recipients, remove_cc_recipient, set_cc_recipients
from config import SEND_EMAIL, FROM_EMAIL, MAIL_FROM_NAME, MAIL_MAILER, email_configured
from email_service import EmailServiceError, get_cc_recipients, send_subscriber_email
from package_service import (
    create_subscriber_zip_bytes,
    list_subscribers_with_stats,
)
from subscriber_list_service import (
    create_subscriber_list_excel,
    import_subscriber_emails_from_dataframe,
    parse_subscriber_email_file,
)
from activity_log_store import append_activity_log
from auth_deps import get_current_user_email
from send_history_store import build_report_grouped_by_date, get_last_send_for_subscriber, record_subscriber_send
from subscriber_store import bulk_update_subscriber_emails, load_subscriber_emails, sync_emails_to_active_subscribers

router = APIRouter(prefix="/email", tags=["email"])

_current_data_getter = None


def init_email_routes(get_data_fn):
    global _current_data_getter
    _current_data_getter = get_data_fn


def _require_data():
    df = _current_data_getter() if _current_data_getter else None
    if df is None:
        raise HTTPException(status_code=404, detail="No data available. Please upload an Excel file first.")
    return df


class SubscriberEmailItem(BaseModel):
    subscriber_name: str
    email: str = ""


class BulkSubscriberEmailsRequest(BaseModel):
    mappings: List[SubscriberEmailItem]


class SendEmailsRequest(BaseModel):
    subscriber_names: Optional[List[str]] = None
    subject: Optional[str] = None
    message: Optional[str] = None


class CcRecipientRequest(BaseModel):
    email: str


class CcRecipientsRequest(BaseModel):
    recipients: List[str]


@router.get("/status")
async def email_status():
    return {
        "send_email_enabled": SEND_EMAIL,
        "configured": email_configured(),
        "mailer": MAIL_MAILER,
        "from_email": FROM_EMAIL,
        "from_name": MAIL_FROM_NAME,
        "cc_recipients": get_cc_recipients(),
    }


@router.get("/subscribers")
async def get_email_subscribers():
    df = _require_data()
    try:
        subscribers = list_subscribers_with_stats(df)
        saved_emails = load_subscriber_emails()
        for sub in subscribers:
            sub["email"] = saved_emails.get(sub["name"], "")
            sub["has_email"] = bool(sub["email"])
            last_send = get_last_send_for_subscriber(sub["name"])
            sub["last_sent_at"] = last_send.get("sent_at") if last_send else None
            sub["last_sent_by"] = last_send.get("sent_by") if last_send else None
            sub["ever_sent"] = last_send is not None
        return {
            "total_subscribers": len(subscribers),
            "subscribers_with_email": sum(1 for s in subscribers if s["has_email"]),
            "subscribers_ever_sent": sum(1 for s in subscribers if s["ever_sent"]),
            "cc_recipients": get_cc_recipients(),
            "subscribers": subscribers,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sent-report")
async def get_sent_report(
    date: Optional[str] = Query(None, description="YYYY-MM-DD single day filter"),
    month: Optional[str] = Query(None, description="YYYY-MM monthly filter"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD range start"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD range end"),
    user_email: str = Depends(get_current_user_email),
):
    if month and len(month) != 7:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM format")
    for label, val in [("date_from", date_from), ("date_to", date_to), ("date", date)]:
        if val and len(val) != 10:
            raise HTTPException(status_code=400, detail=f"{label} must be YYYY-MM-DD format")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be on or before date_to")

    report = build_report_grouped_by_date(
        date_filter=date,
        month_filter=month,
        date_from=date_from,
        date_to=date_to,
    )
    df = _current_data_getter() if _current_data_getter else None
    if df is not None:
        try:
            all_subs = {s["name"]: s["record_count"] for s in list_subscribers_with_stats(df)}
            for group in report["groups"]:
                for rec in group["records"]:
                    rec["user_count"] = all_subs.get(rec["subscriber_name"])
        except ValueError:
            pass
    return report


@router.get("/cc-recipients")
async def get_cc_recipients_list():
    return {"cc_recipients": load_cc_recipients()}


@router.put("/cc-recipients")
async def update_cc_recipients(request: CcRecipientsRequest):
    try:
        saved = set_cc_recipients(request.recipients)
        return {"message": "CC recipients updated", "cc_recipients": saved}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cc-recipients")
async def add_cc_recipient_endpoint(request: CcRecipientRequest):
    try:
        saved = add_cc_recipient(request.email)
        return {"message": "CC recipient added", "cc_recipients": saved}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/cc-recipients")
async def remove_cc_recipient_endpoint(email: str):
    saved = remove_cc_recipient(email)
    return {"message": "CC recipient removed", "cc_recipients": saved}


@router.get("/download-subscriber-list")
async def download_subscriber_list():
    df = _require_data()
    try:
        excel_content = create_subscriber_list_excel(df)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"subscriber_email_list_{timestamp}.xlsx"
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating subscriber list: {str(e)}")


@router.post("/upload-subscriber-emails")
async def upload_subscriber_emails(file: UploadFile = File(...)):
    df = _require_data()

    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="File must be Excel (.xlsx, .xls) or CSV (.csv)")

    try:
        contents = await file.read()
        upload_df = parse_subscriber_email_file(contents, file.filename)
        subscribers = list_subscribers_with_stats(df)
        valid_names = [s['name'] for s in subscribers]
        saved, report = import_subscriber_emails_from_dataframe(upload_df, valid_names)

        return {
            "message": "Subscriber emails merged successfully",
            "saved_count": len(saved),
            "added_subscribers": len(report.get("added", [])),
            "updated_subscribers": len(report.get("updated", [])),
            "removed_subscribers": len(report.get("removed_not_in_data", [])),
            "report": report,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.put("/subscriber-emails")
async def save_subscriber_emails(request: BulkSubscriberEmailsRequest):
    df = _require_data()
    try:
        subscribers = list_subscribers_with_stats(df)
        valid_names = [s["name"] for s in subscribers]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    updates = [item.model_dump() for item in request.mappings]
    saved = bulk_update_subscriber_emails(updates, valid_subscriber_names=valid_names)
    return {
        "message": "Subscriber emails saved successfully (merged, synced to active subscribers)",
        "saved_count": len(saved),
        "mappings": saved,
    }


@router.get("/download-subscriber-zip/{subscriber_name}")
async def download_subscriber_zip(subscriber_name: str):
    df = _require_data()
    try:
        zip_bytes, zip_filename = create_subscriber_zip_bytes(df, subscriber_name)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating ZIP: {str(e)}")


@router.post("/send")
async def send_emails_to_subscribers(
    request: SendEmailsRequest = SendEmailsRequest(),
    user_email: str = Depends(get_current_user_email),
):
    df = _require_data()

    if not SEND_EMAIL:
        raise HTTPException(status_code=400, detail="Email sending is disabled. Set SEND_EMAIL=true in .env")
    if not email_configured():
        raise HTTPException(status_code=400, detail="Email is not configured. Check backend .env file.")

    try:
        subscribers = list_subscribers_with_stats(df)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    saved_emails = load_subscriber_emails()
    target_names = request.subscriber_names
    if target_names:
        subscribers = [s for s in subscribers if s["name"] in target_names]

    default_subject = "CRM User Data & Deactivation Form"

    results = []
    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for sub in subscribers:
        name = sub["name"]
        to_email = saved_emails.get(name, "").strip()

        if not to_email:
            skipped_count += 1
            results.append({
                "subscriber_name": name,
                "status": "skipped",
                "reason": "No email address configured",
            })
            continue

        try:
            zip_bytes, zip_filename = create_subscriber_zip_bytes(df, name)
            email_subject = request.subject or default_subject
            send_result = send_subscriber_email(
                to_email=to_email,
                subscriber_name=name,
                attachment_bytes=zip_bytes,
                attachment_filename=zip_filename,
                subject=email_subject,
                message=request.message,
            )
            record_subscriber_send(name, user_email, recipient_email=to_email)
            sent_count += 1
            results.append({
                "subscriber_name": name,
                "status": "sent",
                "to": to_email,
                "cc": send_result["cc"],
                "attachments": send_result.get("attachments", [zip_filename]),
                "method": send_result["method"],
            })
        except EmailServiceError as e:
            failed_count += 1
            results.append({
                "subscriber_name": name,
                "status": "failed",
                "to": to_email,
                "error": str(e),
            })
        except Exception as e:
            failed_count += 1
            results.append({
                "subscriber_name": name,
                "status": "failed",
                "to": to_email,
                "error": str(e),
            })

    if sent_count == 0 and failed_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No emails sent. Assign email addresses to subscribers before sending.",
        )

    append_activity_log(
        user_email,
        "send_email",
        {
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "subscribers": [r.get("subscriber_name") for r in results if r.get("status") == "sent"],
        },
    )

    return {
        "message": f"Processed {len(results)} subscribers",
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "cc_recipients": get_cc_recipients(),
        "results": results,
    }
