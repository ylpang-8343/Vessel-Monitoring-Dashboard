"""Registration, login, logout, "who am I", and "Sign in with Microsoft" endpoints. Unlike every
other router in the app, these must stay reachable *without* being logged in already (see
app/main.py, where this router is the one NOT wrapped in `Depends(get_current_user)`)."""

import secrets
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import SESSION_COOKIE_NAME, get_current_user
from app.models import AuthProvider, User, UserRole
from app.schemas import MicrosoftStatusOut, UserLogin, UserOut, UserRegister
from app.services import microsoft_auth_service
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_MAX_AGE_SECONDS = settings.jwt_expire_days * 24 * 60 * 60
# Short-lived - only needs to survive the round trip to Microsoft and back, not a whole session.
OAUTH_STATE_COOKIE_NAME = "ms_oauth_state"
OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60


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
        samesite="none",
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
    "no such email", "wrong password", and "this account has no password because it was created
    via Microsoft sign-in" - so a login form can't be used to enumerate which emails are
    registered or how they authenticate."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or user.password_hash is None or not verify_password(payload.password, user.password_hash):
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


@router.get("/microsoft/status", response_model=MicrosoftStatusOut)
def microsoft_status():
    """Whether "Sign in with Microsoft" is actually usable on this deployment - the frontend
    calls this to decide whether to show the button at all, rather than showing one that would
    just fail. Public (no login required), matching register/login."""
    return MicrosoftStatusOut(configured=microsoft_auth_service.is_configured())


@router.get("/microsoft/login")
def microsoft_login():
    """Start the Microsoft sign-in flow: redirect the browser to Microsoft's own login page,
    with a fresh CSRF `state` token stashed in a short-lived cookie for the callback to verify.
    A full-page redirect (not a fetch call) - OAuth's authorize step has to happen in the
    top-level browser navigation, not from JS."""
    if not microsoft_auth_service.is_configured():
        raise HTTPException(status_code=503, detail="Microsoft sign-in is not configured")

    state = secrets.token_urlsafe(24)
    response = RedirectResponse(microsoft_auth_service.build_authorize_url(state), status_code=307)
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=state,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/microsoft/callback")
def microsoft_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    ms_oauth_state: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """Microsoft redirects the browser back here after the user signs in (or cancels). Exchanges
    the authorization code for an access token, fetches the user's profile from Graph, then
    finds-or-creates a matching User and logs them in - always ending in a redirect back to the
    frontend (to `/` on success, to `/login?error=...` on any failure) since this endpoint is
    itself only ever reached via a full-page browser navigation, never called from JS."""

    def fail(message: str) -> RedirectResponse:
        resp = RedirectResponse(f"{settings.frontend_base_url}/login?error={quote(message)}", status_code=307)
        resp.delete_cookie(key=OAUTH_STATE_COOKIE_NAME)
        return resp

    if error:
        return fail("Microsoft sign-in was cancelled or did not complete")
    # The state cookie is set by /microsoft/login immediately before Microsoft ever sees the
    # request, so a mismatch (or missing cookie) means this callback wasn't reached via that
    # flow - reject it rather than trusting the query string alone (CSRF protection).
    if not code or not state or not ms_oauth_state or state != ms_oauth_state:
        return fail("Invalid Microsoft sign-in response - please try again")

    try:
        access_token = microsoft_auth_service.exchange_code_for_token(code)
        profile = microsoft_auth_service.fetch_profile(access_token)
    except httpx.HTTPError:
        return fail("Could not complete Microsoft sign-in - please try again")

    email = profile.get("mail") or profile.get("userPrincipalName")
    if not email:
        return fail("Your Microsoft account has no email address on file")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        # Brand-new account, same as email/password registration: always role=USER, never
        # admin - "Sign in with Microsoft" is not a second path to self-promotion.
        user = User(
            email=email,
            password_hash=None,
            role=UserRole.USER,
            auth_provider=AuthProvider.MICROSOFT,
            microsoft_id=profile.get("id"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.microsoft_id:
        # An existing account (registered with a password, or promoted to admin) whose email
        # matches - link Microsoft sign-in to it instead of creating a second, duplicate
        # account. Their existing role is untouched either way.
        user.microsoft_id = profile.get("id")
        db.commit()

    resp = RedirectResponse(settings.frontend_base_url, status_code=307)
    _set_session_cookie(resp, user.id)
    resp.delete_cookie(key=OAUTH_STATE_COOKIE_NAME)
    return resp
