from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./serviceAccountKey.json"
    FIREBASE_PROJECT_ID: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    SMS_DEMO_TO_NUMBER: str = ""
    SMS_MODE: str = "mock"
    LOG_LEVEL: str = "INFO"
    BACKEND_PORT: int = 8000
    PIPELINE_AUTO_RUN: bool = False
    PRICE_REFRESH_INTERVAL: int = 3600
    NEWS_REFRESH_INTERVAL: int = 1800

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()