"""Клиент DeepSeek. API совместим с OpenAI, поэтому используем SDK openai с другим base_url.

Весь остальной код ходит в LLM только через этот модуль — так модель легко подменить
в тестах и при необходимости сменить провайдера.
"""

import json
from functools import lru_cache

from openai import OpenAI

from seller_assistant.config import get_settings


class LLMNotConfiguredError(RuntimeError):
    pass


@lru_cache
def get_client() -> OpenAI:
    settings = get_settings()
    if settings.deepseek_api_key is None:
        raise LLMNotConfiguredError("DEEPSEEK_API_KEY не задан в .env")
    return OpenAI(
        api_key=settings.deepseek_api_key.get_secret_value(),
        base_url=settings.deepseek_base_url,
        timeout=settings.llm_timeout_seconds,
    )


def complete(system: str, user: str, *, temperature: float = 0.3) -> str:
    """Один запрос к модели: системная инструкция + сообщение пользователя → текст ответа."""
    response = get_client().chat.completions.create(
        model=get_settings().deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def complete_json(system: str, user: str, *, temperature: float = 0.2) -> dict:
    """Запрос с ответом строго в JSON (response_format json_object). В system опишите схему."""
    response = get_client().chat.completions.create(
        model=get_settings().deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content or "{}")
