"""App configuration loaded from .env."""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    siapkerja_username: str = ""
    siapkerja_password: str = ""
    hari_libur: str = "Sabtu,Minggu"
    libur_nasional: bool = True
    reminder_times: str = "16:00,21:00"
    latitude: str = "-6.370891"
    longitude: str = "107.272352"
    location: str = "Karawang"
    activity_log: str = ""
    lesson_learned: str = ""
    obstacles: str = ""

    # Twilio WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "+14155238886"
    whatsapp_to: str = ""

    api_base: str = "https://monev-api.maganghub.kemnaker.go.id/api/v1"
    auth_base: str = "https://account.kemnaker.go.id"

    model_config = {
        "env_file": Path(__file__).parent.parent / ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
