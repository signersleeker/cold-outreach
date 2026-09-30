from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def sqlalchemy_url(database_url: str) -> str:
    """Normalize postgres:// DSNs for SQLAlchemy + psycopg3."""
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8000
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origin: str = "http://localhost:5173"
    serve_frontend: bool = False

    database_url: str

    secret_key: str = ""
    outreach_app_password: str = ""
    session_cookie_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 24 * 7

    google_client_id: str = ""
    google_client_secret: str = ""

    zerobounce_api_key: str = ""

    daily_cap: int = 20

    def sqlalchemy_database_url(self) -> str:
        return sqlalchemy_url(self.database_url)

    def base_url(self) -> str:
        return self.app_base_url.rstrip("/")

    def resolved_frontend_url(self) -> str:
        return (self.frontend_url or self.cors_origin or "http://localhost:5173").rstrip("/")

    def google_redirect_url(self) -> str:
        """Derived, never a separate env var.

        A standalone GOOGLE_REDIRECT_URI would silently drift out of sync with
        APP_BASE_URL, and the only symptom is an opaque redirect_uri_mismatch
        from Google. Deriving it makes that failure impossible.
        """
        return f"{self.base_url()}/auth/google/callback"

    def unsub_url(self, token: str) -> str:
        return f"{self.base_url()}/u/{token}"

    def oauth_configured(self) -> bool:
        return bool(self.google_client_id.strip() and self.google_client_secret.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
