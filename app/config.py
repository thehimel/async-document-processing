import os
import signal
import sys
from urllib.parse import urlparse

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


def _session_domain_from_frontend_url(frontend_url: str | None) -> str | None:
    """Derive session cookie domain from frontend URL. None for localhost."""
    if not frontend_url:
        return None
    host = urlparse(frontend_url).hostname
    if not host or host in ("localhost", "127.0.0.1"):
        return None
    return f".{host}"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_db: str = "core"
    postgres_ssl_require: bool = False  # Set true for Neon and other cloud Postgres
    postgres_db_test: str | None = None  # If unset, uses {postgres_db}_test
    sql_echo: bool = False

    # Google OAuth — create credentials at console.cloud.google.com
    google_client_id: str
    google_client_secret: str

    # JWT: generate secret with `openssl rand -hex 32`
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 1 day

    # Session middleware secret (used by Authlib to sign the OAuth state cookie)
    # Generate with: openssl rand -hex 32
    session_secret_key: str

    # CORS: "*" allows all origins (dev only); use comma-separated list for production.
    cors_origins: str = "*"

    # Frontend base URL for OAuth callback. Required when API is proxied (e.g. via Next.js rewrites).
    # Callback must match Google's authorized redirect URIs (frontend domain, not API domain).
    # Session cookie domain is derived from this.
    # Dev: http://localhost:3000  Prod: https://example.com or https://www.example.com
    frontend_url: str | None = None

    # When False, rate limiting is disabled (e.g. for tests).
    rate_limit_enabled: bool = True


try:
    settings = Settings()
except ValidationError as e:
    missing = [str(err["loc"][0]).upper() for err in e.errors() if err["type"] == "missing"]
    print(f"Missing: {', '.join(missing)}. Set in .env. See .env.example.", file=sys.stderr)
    try:
        os.kill(os.getppid(), signal.SIGTERM)
    except OSError:
        pass
    sys.exit(1)
