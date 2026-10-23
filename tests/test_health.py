from fastapi.testclient import TestClient

from seller_assistant.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Ассистент продавца" in response.text
