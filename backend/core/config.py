from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///avos.db"
    AVOS_RATE_LIMIT: int = 120
    AVOS_RATE_WINDOW: int = 60
    SECRET_KEY: str = "change-me-now"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = Path(".env")
        env_file_encoding = "utf-8"


settings = Settings()
