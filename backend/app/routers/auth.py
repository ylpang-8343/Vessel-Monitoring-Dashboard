"""Registration, login, logout, and "who am I" endpoints. Unlike every other router in the app,
these must stay reachable *without* being logged in already (see app/main.py, where this router
is the one NOT wrapped in `Depends(get_current_user)`)."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import SESSION_COOKIE_NAME, get_current_user
from app.models import User, UserRole
from app.schemas import UserLogin, UserOut, UserRegister
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_MAX_AGE_SECONDS = settings.jwt_expire_days * 24 * 60 * 60


def _set_session_cookie(response: Response, user_id: int) -> None:
    """Issue a fresh session token and attach it as an httpOnly cookie (so frontend JS can't
    read it, only send it automatically) on the given response. `samesite="lax"` plus an
    explicit CORS origin (see app/main.py) is what makes this work across the :3000/:8000 port
    split in local dev without needing a third-party-cookie exception."""
    token = create_access_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, response: Response, db: Session = Depends(get_db)):
    """Create a new account and log the caller straight in. `payload` has already been
    validated for password complexity and confirm-match by UserRegister's validators before
    this function ever runs."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # Registration never grants admin - the first admin is created via the `promote-admin`
    # terminal command (app/cli.py), and every admin after that via the Users tab. This keeps
    # there from ever being a self-promotion path reachable from the web app.
    user = User(email=payload.email, password_hash=hash_password(payload.password), role=UserRole.USER)
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Verify credentials and issue a session cookie. Deliberately returns the same 401 for
    both "no such email" and "wrong password" so a login form can't be used to enumerate which
    emails are registered."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response):
    """Clear the session cookie. Stateless on the server side - the JWT itself isn't tracked or
    revoked anywhere, it just stops being sent by the browser after this."""
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Return the currently logged-in user. Used by the frontend's AuthProvider on every page
    load to figure out who's logged in (if anyone) and what role they have."""
    return user
