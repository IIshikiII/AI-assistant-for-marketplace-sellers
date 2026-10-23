from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from seller_assistant.db import get_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Процесс жив. Не трогает внешние зависимости."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(session: Session = Depends(get_session)) -> dict[str, str]:
    """Приложение готово принимать запросы: база доступна. Деплой ждёт именно его."""
    session.execute(text("SELECT 1"))
    return {"status": "ready"}
