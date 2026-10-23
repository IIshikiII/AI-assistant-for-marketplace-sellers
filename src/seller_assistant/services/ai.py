"""Сценарии с LLM: объяснение рекомендации, разбор отзывов, копилот по данным магазина.

Принцип: LLM получает уже посчитанные цифры и тексты и только интерпретирует их.
Ей явно запрещено придумывать числа — это проверяемо по блоку «Данные» в каждом ответе.
"""

import math

from seller_assistant.llm import client as llm
from seller_assistant.models import Product, Recommendation
from seller_assistant.services import analytics

STYLE = (
    "Ты — marketPilot AI, аналитик-помощник продавца на маркетплейсах Wildberries и Ozon. "
    "Пиши по-русски, коротко и по делу, деловым языком. Используй только цифры из "
    "переданных данных, ничего не выдумывай. Если данных не хватает для вывода — так и скажи. "
    "Форматирование — Markdown: короткие абзацы и маркированные списки, без таблиц."
)


def explain_recommendation(rec: Recommendation) -> str:
    metrics = "\n".join(f"- {k}: {v}" for k, v in rec.metrics.items())
    user = (
        f"Рекомендация системы: {rec.title}\n"
        f"Причина (рассчитано правилами): {rec.cause}\n"
        f"Предлагаемое действие: {rec.action}\n"
        f"Ожидаемый эффект за 30 дней: {rec.effect_rub:,.0f} ₽. {rec.effect_note}\n"
        f"Данные:\n{metrics}\n\n"
        "Объясни владельцу бизнеса в 3 блоках: **Что происходит**, **Почему это важно** "
        "(в деньгах), **Что сделать сегодня** (2–4 конкретных шага). Отдельной строкой — "
        "**Риски**: когда рекомендация может не сработать. Не более 160 слов."
    )
    return llm.complete(STYLE, user)


REVIEW_SCHEMA = """Верни JSON строго такого вида:
{
  "summary": "1–2 предложения: главное, что говорят покупатели",
  "themes": [
    {"theme": "короткое название проблемы или плюса", "sentiment": "negative|positive",
     "count": число отзывов, "quote": "типичная цитата из отзывов"}
  ],
  "card_fixes": ["конкретная правка описания, фото или характеристик карточки"],
  "product_fixes": ["что передать поставщику или изменить в товаре"],
  "reply_template": "вежливый шаблон ответа на типовой негативный отзыв, 2–3 предложения"
}
Темы отсортируй по количеству, не больше 6. Считай count по переданным отзывам."""


def analyze_reviews(product: Product, limit: int = 60) -> dict:
    reviews = sorted(product.reviews, key=lambda r: r.day, reverse=True)[:limit]
    lines = "\n".join(f"- [{r.day:%d.%m}] {r.rating}★ {r.text}" for r in reviews)
    user = (
        f"Товар: {product.name}, маркетплейс {product.marketplace}, "
        f"категория {product.category}.\nОтзывы покупателей ({len(reviews)} шт, новые сверху):\n"
        f"{lines}"
    )
    return llm.complete_json(STYLE + "\n\n" + REVIEW_SCHEMA, user)


def _shop_context(kpis: dict, stats: list[analytics.Stats], recs: list[Recommendation]) -> str:
    head = (
        f"Выручка за 7 дней: {kpis['revenue_7']:,.0f} ₽ ({kpis['revenue_change']:+.0%} к пред. "
        f"неделе). Маржа после рекламы за 7 дней: {kpis['margin_7']:,.0f} ₽. "
        f"Реклама за 7 дней: {kpis['ad_spend_7']:,.0f} ₽, ДРР 14 дн {kpis['drr_14']:.0%}. "
        f"SKU: {kpis['skus']}, в риске дефицита: {kpis['at_risk']}, без остатка: "
        f"{kpis['out_of_stock']}. Заморожено в излишках: {kpis['frozen']:,.0f} ₽. "
        f"Средний рейтинг за 30 дней: {kpis['rating']:.2f}."
    )
    rows = []
    for s in stats:
        cover = "∞" if math.isinf(s.cover_days) else f"{s.cover_days:.0f}"
        drr = f"{s.drr_14:.0%}" if s.drr_14 is not None else "нет рекламы"
        rows.append(
            f"- {s.product.sku} {s.product.name} ({s.product.marketplace}): цена {s.price:.0f}, "
            f"маржа/шт {s.unit_margin:.0f}, продажи 7д {s.units_7} (пред. {s.units_prev7}), "
            f"остаток {s.stock} шт на {cover} дн, поставка {s.product.lead_time_days} дн, "
            f"ДРР {drr}, рейтинг 30д {s.rating_30 or 0:.1f}, негатив {s.negative_share_30:.0%}"
        )
    rec_lines = [
        f"- [{'!' * r.severity}] {r.title}. Действие: {r.action} Эффект: {r.effect_rub:,.0f} ₽"
        for r in recs[:12]
    ]
    return (
        f"СВОДКА МАГАЗИНА\n{head}\n\nТОВАРЫ\n"
        + "\n".join(rows)
        + "\n\nОТКРЫТЫЕ РЕКОМЕНДАЦИИ СИСТЕМЫ (по приоритету)\n"
        + "\n".join(rec_lines)
    )


def weekly_digest(kpis: dict, stats: list[analytics.Stats], recs: list[Recommendation]) -> str:
    user = (
        _shop_context(kpis, stats, recs)
        + "\n\nСоставь сводку недели для собственника: 1) общая оценка состояния магазина в 2 "
        "предложениях; 2) **Топ-5 действий на эту неделю** с эффектом в рублях, по убыванию "
        "важности; 3) **Что идёт хорошо** — 1–2 пункта. Не более 220 слов."
    )
    return llm.complete(STYLE, user)


def ask_copilot(
    question: str, kpis: dict, stats: list[analytics.Stats], recs: list[Recommendation]
) -> str:
    user = (
        _shop_context(kpis, stats, recs) + f"\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}\n\n"
        "Ответь на вопрос, опираясь только на эти данные. Ссылайся на конкретные SKU и цифры. "
        "Если вопрос не про магазин — вежливо верни разговор к данным магазина."
    )
    return llm.complete(STYLE, user)
