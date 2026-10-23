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


def test_observer_gets_latency_and_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    class Completions:
        def create(self, **kwargs):
            usage = SimpleNamespace(prompt_tokens=120, completion_tokens=30)
            message = SimpleNamespace(content="ok")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)

    fake = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    seen: list[llm.CallInfo] = []
    monkeypatch.setattr(llm, "observers", [seen.append])

    llm.complete("s", "u", kind="explain")
    assert seen[0].kind == "explain"
    assert (seen[0].prompt_tokens, seen[0].completion_tokens, seen[0].ok) == (120, 30, True)


def test_observer_sees_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        def create(self, **kwargs):
            raise TimeoutError("timeout")

    fake = SimpleNamespace(chat=SimpleNamespace(completions=Broken()))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    seen: list[llm.CallInfo] = []
    monkeypatch.setattr(llm, "observers", [seen.append])

    with pytest.raises(TimeoutError):
        llm.complete("s", "u", kind="copilot")
    assert seen[0].ok is False
    assert "timeout" in (seen[0].error or "")
