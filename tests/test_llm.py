"""Тесты не ходят в настоящий DeepSeek: клиент подменяется заглушкой."""

from types import SimpleNamespace

import pytest

from seller_assistant.llm import client as llm


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content="ответ модели")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_complete_sends_system_and_user(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FakeCompletions()
    fake = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    assert llm.complete("ты ассистент", "привет") == "ответ модели"
    roles = [m["role"] for m in completions.calls[0]["messages"]]
    assert roles == ["system", "user"]
