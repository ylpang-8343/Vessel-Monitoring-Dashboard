"""Application configuration, loaded from environment variables / `.env`.

Uses pydantic-settings so every value below can be overridden by an environment variable of the
same name (case-insensitive) without changing this file - e.g. `ARRIVED_RETENTION_DAYS=0` at
process startup temporarily overrides `arrived_retention_days` for a single run.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads `.env` in the working directory (backend/) and ignores any env vars that don't map
    # to a field below, instead of erroring on unknown keys.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLAlchemy connection string for Postgres (see docker-compose.yml for the default
    # user/password/db this points at).
    database_url: str = "postgresql+psycopg://vessel:vessel@localhost:5432/vessel_monitoring"
    # Used by services/pdf_extraction.py; PDF bulk-upload extraction is disabled (returns a
    # clear "unavailable" error) when this is unset.
    anthropic_api_key: str | None = None

    # How often the background tracking worker polls for new vessel status (Section 3.3).
    tracking_poll_interval_seconds: int = 300
    # How many days a vessel stays visible after "Arrived at Destination" before being
    # auto-archived (Section 3.7).
    arrived_retention_days: int = 10

    # Allowed origins for CORS - must be an explicit list (not "*") since cookies are sent
    # cross-origin between the frontend (:3000) and this API (:8000).
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Phase 6 (Section 7) ---
    # How late an arrival (or an overdue in-transit vessel) has to be before it counts as
    # "delayed". A small grace window keeps a few minutes' drift from flagging every vessel.
    delay_threshold_minutes: int = 60
    # How long a vessel may sit "At Port" before that counts as an unusually long port stay.
    long_port_stay_hours: int = 72
    # Model used for the AI voyage summary (services/ai_service.py). Overridable so a
    # deployment can trade cost against quality without a code change.
    ai_summary_model: str = "claude-opus-5"

    # Dev-only default so the app runs out of the box - override in .env for anything beyond
    # local use, since anyone with this value can forge session cookies.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    # How long a login session stays valid before the user has to log in again.
    jwt_expire_days: int = 7
    # Whether the session cookie is marked `Secure` (HTTPS-only). Off for local http dev.
    cookie_secure: bool = False
    # SameSite policy for the session cookie.
    #
    # "lax" is correct whenever the frontend and backend share a site - including local dev,
    # where :3000 -> :8000 counts as same-site (SameSite ignores the port). Use "none" only when
    # they're on genuinely different domains, as in a split deployment.
    #
    # ⚠️ Browsers reject a `SameSite=None` cookie that isn't also `Secure`, silently - the
    # response looks fine and the cookie is simply never stored, so every request afterwards
    # reads as logged-out. So "none" REQUIRES cookie_secure=true (and therefore HTTPS). Setting
    # one without the other is the single easiest way to make login mysteriously stop working;
    # app/main.py logs a loud warning at startup if this pair is inconsistent.
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # "Sign in with Microsoft" (services/microsoft_auth_service.py, routers/auth.py). Unset by
    # default - the button is hidden/disabled on the frontend until both are configured, the
    # same "unavailable rather than broken" posture as PDF extraction without an API key.
    # Register an app at https://portal.azure.com (Entra ID -> App registrations) to get these.
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    # "common" accepts both personal Microsoft accounts and any work/school (Entra ID) account;
    # set to a specific tenant id to restrict sign-in to one organisation.
    microsoft_tenant_id: str = "common"
    # Must exactly match a Redirect URI configured on the Azure app registration.
    microsoft_redirect_uri: str = "http://localhost:8000/api/auth/microsoft/callback"
    # Overridable so a verification pass can point the OAuth flow at a local fake identity
    # provider instead of the real login.microsoftonline.com / graph.microsoft.com - lets the
    # whole authorize -> token -> profile round trip be exercised against real HTTP calls
    # without needing a live Azure app during testing.
    microsoft_authority_base_url: str = "https://login.microsoftonline.com"
    microsoft_graph_base_url: str = "https://graph.microsoft.com"
    # Where to send the browser after a Microsoft sign-in completes (success or failure) -
    # the frontend's own origin, not this API's.
    frontend_base_url: str = "http://localhost:3000"


# Single shared instance, imported wherever config is needed (e.g. `from app.config import
# settings`) instead of constructing `Settings()` repeatedly.
settings = Settings()
