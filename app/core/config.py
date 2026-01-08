"""Application configuration from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://keyraa:keyraa@localhost:5432/keyraa"
    DATABASE_URL_SYNC: str = "postgresql://keyraa:keyraa@localhost:5432/keyraa"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Amadeus API
    AMADEUS_CLIENT_ID: str = ""
    AMADEUS_CLIENT_SECRET: str = ""
    AMADEUS_BASE_URL: str = "https://test.api.amadeus.com"

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "bookings@keyraa.local"

    # Application
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    USE_MOCK_AMADEUS: bool = True

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"



@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
