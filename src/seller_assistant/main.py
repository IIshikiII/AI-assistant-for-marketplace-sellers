"""Точка входа: uvicorn seller_assistant.main:app"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from seller_assistant.api import health, pages
from seller_assistant.config import get_settings
from seller_assistant.db import SessionLocal
from seller_assistant.services import shop
from seller_assistant.web.templating import WEB_DIR

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Пустая база — загружаем демо-магазин, чтобы прототип сразу было что показать.
    try:
        with SessionLocal() as session:
            shop.ensure_demo(session)
    except Exception:
        log.exception("Не удалось подготовить демо-данные")
    yield


app = FastAPI(
    title="marketPilot AI",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(pages.router)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
