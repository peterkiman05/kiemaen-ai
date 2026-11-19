import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Kiemaen AI Command Center"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./kiemaen_v2.db")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "kiemaen2026")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")

    class Config:
        env_file = ".env"

settings = Settings()
