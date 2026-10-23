"""Точка входа: uvicorn seller_assistant.main:app"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from seller_assistant.api import health
from seller_assistant.config import get_settings

WEB_DIR = Path(__file__).parent / "web"

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Ассистент продавца",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(health.router)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

templates = Jinja2Templates(directory=WEB_DIR / "templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
