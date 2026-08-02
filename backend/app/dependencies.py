from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole
from app.services.auth_service import decode_access_token

SESSION_COOKIE_NAME = "session_token"


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if session_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = decode_access_token(session_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
