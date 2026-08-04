"""Application configuration, loaded from environment variables / `.env`.

Uses pydantic-settings so every value below can be overridden by an environment variable of the
same name (case-insensitive) without changing this file - e.g. `ARRIVED_RETENTION_DAYS=0` at
process startup temporarily overrides `arrived_retention_days` for a single run.
"""

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

    # Dev-only default so the app runs out of the box - override in .env for anything beyond
    # local use, since anyone with this value can forge session cookies.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    # How long a login session stays valid before the user has to log in again.
    jwt_expire_days: int = 7
    # Whether the session cookie is marked `Secure` (HTTPS-only). Off for local http dev.
    cookie_secure: bool = False


# Single shared instance, imported wherever config is needed (e.g. `from app.config import
# settings`) instead of constructing `Settings()` repeatedly.
settings = Settings()
