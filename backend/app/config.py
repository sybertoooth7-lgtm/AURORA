"""
AURORA Configuration Management
Handles environment variables and application settings
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


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

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_REQUESTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # Satellite Data — Copernicus Data Space Ecosystem (Sentinel Hub)
    # Free OAuth client credentials from https://shapps.dataspace.copernicus.eu/dashboard/
    # (User Settings -> OAuth clients). Leave unset to fall back to the
    # deterministic demo provider used for local dev and tests.
    SENTINEL_CLIENT_ID: Optional[str] = None
    SENTINEL_CLIENT_SECRET: Optional[str] = None
    SENTINEL_TOKEN_URL: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    SENTINEL_STATS_URL: str = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
    SENTINEL_LOOKBACK_DAYS: int = 30

    # Job queue (RQ) -- analysis runs execute in a separate worker process
    # (see worker.py) instead of FastAPI BackgroundTasks, so they survive an
    # API restart and don't share the API process's memory/CPU.
    REDIS_URL: str = "redis://localhost:6379/0"
    ANALYSIS_JOB_TIMEOUT_SECONDS: int = 180

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000"

    JWT_ISSUER: str = "aurora-api"
    JWT_AUDIENCE: str = "aurora-client"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Reject the development secret when running in production."""
        if (self.ENVIRONMENT.lower() == "production" or not self.DEBUG) and (
            len(self.SECRET_KEY) < 32
            or self.SECRET_KEY in {
                "your-secret-key-change-in-production",
                "change-me-to-a-long-random-value",
            }
        ):
            raise ValueError(
                "SECRET_KEY must be at least 32 characters and unique in production"
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
