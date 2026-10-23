"""Запись вызовов LLM в БД. Подключается в main.py как наблюдатель llm.client."""

import logging

from seller_assistant.config import get_settings
from seller_assistant.db import SessionLocal
from seller_assistant.llm.client import CallInfo
from seller_assistant.models import LlmCall

log = logging.getLogger(__name__)


def call_cost_rub(prompt_tokens: int, completion_tokens: int) -> float:
    s = get_settings()
    usd = (
        prompt_tokens * s.deepseek_price_input_usd + completion_tokens * s.deepseek_price_output_usd
    ) / 1_000_000
    return usd * s.usd_rub


def record_llm_call(info: CallInfo) -> None:
    try:
        with SessionLocal() as session:
            session.add(
                LlmCall(
                    kind=info.kind,
                    model=info.model,
                    latency_ms=info.latency_ms,
                    prompt_tokens=info.prompt_tokens,
                    completion_tokens=info.completion_tokens,
                    cost_rub=call_cost_rub(info.prompt_tokens, info.completion_tokens),
                    ok=info.ok,
                    error=info.error,
                )
            )
            session.commit()
    except Exception:
        log.exception("Не удалось записать телеметрию LLM")
