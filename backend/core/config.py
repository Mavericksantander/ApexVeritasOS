from pathlib import Path

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///avos.db"
    AVOS_RATE_LIMIT: int = 120
    AVOS_RATE_WINDOW: int = 60
    SECRET_KEY: str = "change-me-now"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["*"]
    REGISTRY_ISSUER_KEYS: str = ""

    model_config = ConfigDict(env_file=Path(".env"), env_file_encoding="utf-8")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "t", "yes", "on"}:
                return True
            if lowered in {"0", "false", "f", "no", "off"}:
                return False
            # Treat unknown text (e.g., release or production) as False
            return False
        return value


settings = Settings()
