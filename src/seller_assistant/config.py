"""Настройки приложения. Читаются из переменных окружения и файла .env."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"  # local | production
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/app"

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
