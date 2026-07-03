from pathlib import Path
from typing import Optional
import os

from pydantic import model_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(str(ROOT_DIR / ".env"))


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "file:./prisma/dev.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_RETRIES: int = 2

    SENDGRID_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "noreply@healthcare.app"
    EMAIL_BACKEND: str = "console"

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    CALENDAR_TIMEZONE: str = "Asia/Kolkata"

    REDIS_URL: str = "redis://localhost:6379/0"

    BACKGROUND_INTERVAL_MINUTES: int = 5
    MEDICATION_REMINDER_HOUR: int = 9
    CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.APP_ENV.lower() == "production":
            if self.SECRET_KEY == "change-me-in-production":
                raise ValueError("SECRET_KEY must be set in production")
            if "*" in self.allowed_cors_origins:
                raise ValueError("CORS_ORIGINS cannot include '*' in production")
        return self

    class Config:
        env_file = str(ROOT_DIR / ".env")
        extra = "allow"


settings = Settings()
