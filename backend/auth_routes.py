from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from activity_log_store import load_activity_logs
from auth_deps import get_current_user_email
from auth_service import (
    approve_login_request,
    deny_login_request,
    logout_user,
    request_otp,
    verify_otp_and_login,
)
from auth_store import get_active_session, get_login_request, get_pending_requests

router = APIRouter(prefix="/auth", tags=["auth"])


class RequestOtpBody(BaseModel):
    email: EmailStr


class VerifyOtpBody(BaseModel):
    email: EmailStr
    code: str


class ApproveDenyBody(BaseModel):
    request_id: str


@router.post("/request-otp")
async def api_request_otp(body: RequestOtpBody):
    try:
        return request_otp(str(body.email))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-otp")
async def api_verify_otp(body: VerifyOtpBody):
    try:
        return verify_otp_and_login(str(body.email), body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def api_me(user_email: str = Depends(get_current_user_email)):
    active = get_active_session()
    return {
        "email": user_email,
        "active_session": active is not None,
        "pending_requests": get_pending_requests(),
    }


@router.post("/logout")
async def api_logout(user_email: str = Depends(get_current_user_email)):
    logout_user(user_email)
    return {"message": "Logged out successfully."}


@router.get("/pending-requests")
async def api_pending_requests(user_email: str = Depends(get_current_user_email)):
    active = get_active_session()
    if not active or active.get("email") != user_email:
        raise HTTPException(status_code=403, detail="Not the active session owner.")
    return {"pending_requests": get_pending_requests()}


@router.post("/approve-login")
async def api_approve_login(
    body: ApproveDenyBody,
    user_email: str = Depends(get_current_user_email),
):
    try:
        return approve_login_request(body.request_id, user_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deny-login")
async def api_deny_login(
    body: ApproveDenyBody,
    user_email: str = Depends(get_current_user_email),
):
    try:
        return deny_login_request(body.request_id, user_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/login-request-status")
async def api_login_request_status(request_id: str = Query(...)):
    request = get_login_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Login request not found.")
    result = {"request_id": request_id, "status": request.get("status", "pending")}
    if request.get("status") == "approved":
        active = get_active_session()
        if active and active.get("email") == request.get("email"):
            result["token"] = active.get("token")
            result["email"] = active.get("email")
    return result


@router.get("/activity-log")
async def api_activity_log(
    limit: int = Query(100, ge=1, le=500),
    user_email: str = Depends(get_current_user_email),
):
    logs = load_activity_logs(limit=limit)
    return {"logs": logs, "viewer": user_email}
