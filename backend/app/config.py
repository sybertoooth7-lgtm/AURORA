"""
AURORA Configuration Management
Handles environment variables and application settings
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application configuration from environment variables"""

    # Database
    # NOTE: must include the +psycopg driver suffix — requirements.txt installs
    # psycopg (v3), and a bare "postgresql://" URL makes SQLAlchemy default to
    # the psycopg2 dialect, which is not installed and will fail at startup.
    DATABASE_URL: str = "postgresql+psycopg://localhost/aurora_db"
    SQLALCHEMY_ECHO: bool = False

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    API_WORKERS: int = 4

    # Platform version (single source of truth for /, /health and the API
    # metadata -- bump it here, never in three places).
    APP_VERSION: str = "0.2.0"

    # Security
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Auth-specific hardening. /auth/token and /auth/register get their own
    # (much stricter) rate limit than general API traffic, and repeated
    # failed logins lock the *account* out for a while regardless of which
    # IP the attempts came from -- a purely per-IP limit doesn't stop
    # someone spraying guesses at one account from many source addresses.
    AUTH_RATE_LIMIT_REQUESTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_SECONDS: int = 900  # 15 minutes

    # Satellite Data — Copernicus Data Space Ecosystem (Sentinel Hub)
    # Free OAuth client credentials from https://shapps.dataspace.copernicus.eu/dashboard/
    # (User Settings -> OAuth clients). Leave unset to fall back to the
    # deterministic demo provider used for local dev and tests.
    SENTINEL_CLIENT_ID: str | None = None
    SENTINEL_CLIENT_SECRET: str | None = None
    SENTINEL_TOKEN_URL: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    SENTINEL_STATS_URL: str = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
    SENTINEL_LOOKBACK_DAYS: int = 30

    # Job queue (RQ) -- analysis runs execute in a separate worker process
    # (see worker.py) instead of FastAPI BackgroundTasks, so they survive an
    # API restart and don't share the API process's memory/CPU. Also used
    # for the login-lockout counters and the logout token blocklist below.
    REDIS_URL: str = "redis://localhost:6379/0"
    ANALYSIS_JOB_TIMEOUT_SECONDS: int = 180

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # text | json
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # AI pipelines
    # Number of historical observations fetched for history-aware pipelines
    # (anomaly detection, land change). Wider = more robust baselines but
    # more provider data per run.
    AI_HISTORY_LIMIT: int = 8
    # Synchronous inference (POST /ai/infer) refuses to wait longer than this
    # for a provider response -- above this the client should use the queued
    # /analysis/ flow instead.
    AI_INFER_SYNC_TIMEOUT_SECONDS: int = 30

    # Parametric agriculture insurance (AURORA-2 Earth revenue).
    INSURANCE_DEFAULT_TRIGGER_THRESHOLD: float = 0.4
    INSURANCE_MAX_SUM_INSURED_USD: float = 50_000_000.0
    # Sentinel Hub OAuth setup page for the onboarding "connect live data"
    # checklist item (label/URL are the constants used across the product).
    ONBOARDING_SENTINEL_SETUP_URL: str = "https://shapps.dataspace.copernicus.eu/dashboard/"

    # Robotics field-inspection flights (AURORA-2 Earth revenue). The MVP
    # flight telemetry store is in-memory per process (see app.robotics.flight)
    # -- this bounds how many frames each flight keeps before eviction.
    ROBOTICS_FLIGHT_RETENTION_FRAMES: int = 1000

    class Config:
        env_file = ".env"
        case_sensitive = True

    @model_validator(mode="after")
    def _reject_insecure_secret_in_production(self) -> "Settings":
        """Fail fast rather than silently forge-able: if this ever runs
        with ENVIRONMENT != development and nobody set a real SECRET_KEY,
        every JWT this process issues (or accepts) is trivially forgeable
        by anyone who has read this file -- which is public, on GitHub."""
        if self.ENVIRONMENT != "development":
            if self.SECRET_KEY == DEFAULT_SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY is still the placeholder default. Set a real, "
                    "random SECRET_KEY (e.g. `python -c \"import secrets; "
                    "print(secrets.token_urlsafe(48))\"`) before running with "
                    f"ENVIRONMENT={self.ENVIRONMENT!r}."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY is too short to be a secure signing key "
                    "(need at least 32 characters) for a non-development "
                    f"ENVIRONMENT={self.ENVIRONMENT!r}."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
