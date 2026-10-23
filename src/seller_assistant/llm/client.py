"""Клиент DeepSeek. API совместим с OpenAI, поэтому используем SDK openai с другим base_url.

Весь остальной код ходит в LLM только через этот модуль — так модель легко подменить
в тестах и при необходимости сменить провайдера.

Каждый вызов замеряется (время, токены, успех) и передаётся наблюдателям из `observers`.
Приложение подключает запись в БД при старте (services/telemetry.py), тесты — нет.
"""

import contextlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from seller_assistant.config import get_settings


class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass
class CallInfo:
    kind: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    ok: bool
    error: str | None = None


observers: list[Callable[[CallInfo], None]] = []


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


def _notify(info: CallInfo) -> None:
    for observer in observers:
        # Телеметрия не должна ломать ответ пользователю.
        with contextlib.suppress(Exception):
            observer(info)


def _chat(kind: str, system: str, user: str, **params) -> str:
    model = get_settings().deepseek_model
    started = time.perf_counter()
    try:
        response = get_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **params,
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        _notify(CallInfo(kind, model, elapsed, 0, 0, ok=False, error=str(exc)[:500]))
        raise
    elapsed = int((time.perf_counter() - started) * 1000)
    usage = getattr(response, "usage", None)
    _notify(
        CallInfo(
            kind,
            model,
            elapsed,
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
            ok=True,
        )
    )
    return response.choices[0].message.content or ""


def complete(system: str, user: str, *, kind: str = "other", temperature: float = 0.3) -> str:
    """Один запрос к модели: системная инструкция + сообщение пользователя → текст ответа."""
    return _chat(kind, system, user, temperature=temperature)


def complete_json(system: str, user: str, *, kind: str = "other", temperature: float = 0.2) -> dict:
    """Запрос с ответом строго в JSON (response_format json_object). В system опишите схему."""
    text = _chat(
        kind, system, user, temperature=temperature, response_format={"type": "json_object"}
    )
    return json.loads(text or "{}")
