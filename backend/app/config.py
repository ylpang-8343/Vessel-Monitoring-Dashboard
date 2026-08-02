from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://vessel:vessel@localhost:5432/vessel_monitoring"
    anthropic_api_key: str | None = None

    tracking_poll_interval_seconds: int = 300
    arrived_retention_days: int = 10

    cors_origins: list[str] = ["http://localhost:3000"]

    # Dev-only default so the app runs out of the box - override in .env for anything beyond
    # local use, since anyone with this value can forge session cookies.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_expire_days: int = 7
    cookie_secure: bool = False


settings = Settings()
