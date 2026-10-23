"""Подключение к PostgreSQL.

Модели наследуются от Base, схема меняется только миграциями Alembic.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from seller_assistant.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос."""
    with SessionLocal() as session:
        yield session
