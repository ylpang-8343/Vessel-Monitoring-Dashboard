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
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
