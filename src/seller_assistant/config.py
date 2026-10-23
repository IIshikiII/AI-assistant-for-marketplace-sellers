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
    # Цены DeepSeek для расчёта стоимости вызовов (USD за 1 млн токенов) и курс.
    # Это допущения: сверяйте с https://api-docs.deepseek.com/quick_start/pricing
    deepseek_price_input_usd: float = 0.28
    deepseek_price_output_usd: float = 0.42
    usd_rub: float = 95.0
    llm_budget_rub_month: float = 1500.0  # бюджет на LLM на одного клиента (docs/economics.md)


@lru_cache
def get_settings() -> Settings:
    return Settings()
