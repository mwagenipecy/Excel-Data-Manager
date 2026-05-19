from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth_store import validate_token

security = HTTPBearer(auto_error=False)


def get_current_user_email(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    email = validate_token(credentials.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")
    return email


def get_optional_user_email(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    if not credentials or not credentials.credentials:
        return None
    return validate_token(credentials.credentials)
