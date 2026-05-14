import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Central place for environment-based settings."""

    APP_ENV = os.getenv("APP_ENV", "development")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smokesignal.db")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MARKET_DATA_API_KEY = os.getenv("MARKET_DATA_API_KEY", "")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
    SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"
    HOURLY_UPDATES_ENABLED = os.getenv("HOURLY_UPDATES_ENABLED", "false").lower() == "true"


settings = Settings()


def get_sqlite_path() -> str:
    """Convert sqlite:/// URLs into a filesystem path sqlite3 can use."""
    database_url = settings.DATABASE_URL
    if not database_url.startswith("sqlite:///"):
        raise ValueError("This MVP currently supports only sqlite:/// DATABASE_URL values.")

    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[1]
        path = project_root / path
    return str(path)
