"""Jinja2-шаблоны и фильтры форматирования."""

import math
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")

_md = MarkdownIt("commonmark", {"html": False, "breaks": True})


def rub(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f} ₽".replace(",", " ")


def pct(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:+.0%}" if signed else f"{value:.0%}"


def days(value: float) -> str:
    return "∞" if math.isinf(value) else f"{value:.0f}"


def markdown(text: str | None) -> Markup:
    return Markup(_md.render(text or ""))


templates.env.filters.update(rub=rub, pct=pct, days=days, markdown=markdown)
templates.env.globals["SEVERITY"] = {
    3: ("Критично", "badge-error"),
    2: ("Важно", "badge-warning"),
    1: ("Возможность", "badge-info"),
}
templates.env.globals["AREAS"] = ["Остатки", "Реклама", "Карточка", "Цена", "Продажи"]
