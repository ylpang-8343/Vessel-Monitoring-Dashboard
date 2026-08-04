"""Password hashing and session-token (JWT) helpers used by routers/auth.py and
app/dependencies.py."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """One-way hash for storing a password (bcrypt generates and embeds its own salt)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a login attempt's plaintext password against the stored hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    """Issue a signed session token for a user, valid for `settings.jwt_expire_days`.

    Intentionally carries only the user id ("sub") - not the role or any other field - so that
    a role change made while a session is active takes effect on the very next request instead
    of waiting for the old token to expire (see app/dependencies.py's get_current_user, which
    re-reads the user from the DB on every call).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Verify a session token's signature/expiry and return the user id it encodes, or None if
    the token is missing, expired, tampered with, or otherwise invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None
