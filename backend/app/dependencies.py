"""FastAPI dependencies for authentication/authorization, used via `Depends(...)` either on
individual routes or at the router level (see app/main.py's `include_router` calls)."""

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole
from app.services.auth_service import decode_access_token

# Name of the httpOnly cookie holding the JWT session token, set by routers/auth.py on
# login/register and cleared on logout.
SESSION_COOKIE_NAME = "session_token"


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the logged-in User from the session cookie, or raise 401.

    The JWT only carries the user's id (see auth_service.create_access_token) - the role and
    every other field is re-read from the DB on every request, so a role change (e.g. an admin
    promotion/demotion) takes effect immediately without waiting for the token to expire.
    """
    if session_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = decode_access_token(session_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        # Token decoded fine but the account no longer exists (e.g. deleted) - treat the same
        # as "not authenticated" rather than a 500.
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Like get_current_user, but additionally requires the ADMIN role (403 otherwise). Used to
    gate Settings/tracking-source management (Section 3.9) and user-role management."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
