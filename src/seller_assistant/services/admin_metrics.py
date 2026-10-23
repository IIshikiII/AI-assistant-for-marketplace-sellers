"""Метрики продукта для роли «админ»: ценность, качество рекомендаций, LLM, данные.

Целевые значения взяты из отчёта команды (НФТ) и docs/economics.md.
"""

import statistics
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from seller_assistant.config import get_settings
from seller_assistant.models import DailySale, DecisionLog, LlmCall, Product, Recommendation
from seller_assistant.services.analytics import build_recommendations
from seller_assistant.services.demo_data import SPECS, build_demo_shop

# Целевые значения
LLM_P50_TARGET_S = 15  # НФТ: медианное время ответа LLM ≤ 15 с
LLM_P95_TARGET_S = 30  # НФТ: 95-й перцентиль ≤ 30 с
DQ_TARGET = 0.97  # НФТ: полнота данных ≥ 97%
DUPLICATES_TARGET = 0.01  # НФТ: дубликатов ≤ 1%
ACCEPTANCE_TARGET = 0.5  # порог пилота: принято ≥ 50% рекомендаций
PRECISION_TARGET = 0.85
RECALL_TARGET = 0.9

# Разметка эталонного набора: какой сценарий демо-магазина какую рекомендацию должен дать.
EXPECTED_KIND = {
    "stockout": {"stockout"},
    "restock": {"restock"},
    "overstock": {"overstock"},
    "ads_bad": {"ads_cut"},
    "ads_good": {"ads_scale"},
    "reviews_bad": {"reviews"},
    "price_up": {"price"},
    "ads_off": {"ads_off"},
    "normal": set(),
}
KIND_LABEL = {
    "stockout": "Нет остатка",
    "restock": "Риск дефицита",
    "overstock": "Неликвид",
    "ads_cut": "Убыточная реклама",
    "ads_scale": "Масштабировать рекламу",
    "reviews": "Негатив в отзывах",
    "price": "Просадка после цены",
    "ads_off": "Реклама остановлена",
    "drop": "Просадка без причины",
}
LLM_KIND_LABEL = {
    "explain": "Объяснение рекомендации",
    "reviews": "Разбор отзывов",
    "digest": "Сводка недели",
    "copilot": "Копилот",
    "other": "Прочее",
}


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


def evaluation() -> dict:
    """Регрессионная проверка правил на размеченном демо-наборе: precision / recall / F1."""
    started = time.perf_counter()
    products = build_demo_shop(date(2026, 10, 24))
    found = {(r.product.sku, r.kind) for r in build_recommendations(products)}
    expected = {(spec.sku, kind) for spec in SPECS for kind in EXPECTED_KIND[spec.scenario]}
    tp, fp, fn = found & expected, found - expected, expected - found
    precision = len(tp) / len(found) if found else 1.0
    recall = len(tp) / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    names = {s.sku: s.name for s in SPECS}
    errors = [
        {
            "type": "Лишняя рекомендация (FP)",
            "sku": sku,
            "name": names[sku],
            "kind": KIND_LABEL.get(kind, kind),
        }
        for sku, kind in sorted(fp)
    ] + [
        {"type": "Пропуск (FN)", "sku": sku, "name": names[sku], "kind": KIND_LABEL.get(kind, kind)}
        for sku, kind in sorted(fn)
    ]
    healthy = [s.sku for s in SPECS if s.scenario == "normal"]
    false_alarm_healthy = sorted({sku for sku, _ in fp if sku in healthy})
    return {
        "cases": len(SPECS),
        "expected": len(expected),
        "found": len(found),
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "errors": errors,
        "healthy": len(healthy),
        "healthy_false_alarms": false_alarm_healthy,
        "runtime_ms": int((time.perf_counter() - started) * 1000),
    }


def value_metrics(session: Session) -> dict:
    recs = list(session.scalars(select(Recommendation)))
    decisions = list(
        session.scalars(select(DecisionLog).options(selectinload(DecisionLog.recommendation)))
    )
    accepted = [d for d in decisions if d.decision == "accepted"]
    ttd_hours = [
        (d.created_at - d.recommendation.created_at).total_seconds() / 3600
        for d in decisions
        if d.recommendation is not None
    ]
    by_area: dict[str, dict] = {}
    for r in recs:
        row = by_area.setdefault(r.area, {"total": 0, "accepted": 0, "rejected": 0, "open": 0})
        row["total"] += 1
        row[{"new": "open"}.get(r.status, r.status)] += 1
    critical_open = sum(1 for r in recs if r.status == "new" and r.severity == 3)
    explained = sum(1 for r in recs if r.ai_explanation)
    return {
        "recs_total": len(recs),
        "recs_open": sum(1 for r in recs if r.status == "new"),
        "critical_open": critical_open,
        "explained": explained,
        "decided": len(decisions),
        "accepted": len(accepted),
        "acceptance_rate": len(accepted) / len(decisions) if decisions else None,
        "accepted_effect": sum(d.snapshot_effect_rub for d in accepted),
        "open_effect": sum(r.effect_rub for r in recs if r.status == "new"),
        "ttd_median_h": statistics.median(ttd_hours) if ttd_hours else None,
        "by_area": by_area,
        "funnel": [
            ("Сформировано рекомендаций", len(recs)),
            ("Открыто объяснение ИИ", explained),
            ("Принято решение", len(decisions)),
            ("Принято к исполнению", len(accepted)),
        ],
    }


def llm_metrics(session: Session) -> dict:
    s = get_settings()
    calls = list(session.scalars(select(LlmCall).order_by(LlmCall.created_at)))
    ok = [c for c in calls if c.ok]
    lat = [c.latency_ms / 1000 for c in ok]
    cost = sum(c.cost_rub for c in calls)
    now = datetime.now(UTC)
    last_30d = [c for c in calls if c.created_at >= now - timedelta(days=30)]
    first = calls[0].created_at if calls else now
    span_days = max(1.0, (now - first).total_seconds() / 86400)
    month_projection = sum(c.cost_rub for c in last_30d) / min(30.0, span_days) * 30

    kinds = []
    for kind, n in Counter(c.kind for c in calls).most_common():
        kc = [c for c in calls if c.kind == kind]
        kok = [c.latency_ms / 1000 for c in kc if c.ok]
        kinds.append(
            {
                "kind": LLM_KIND_LABEL.get(kind, kind),
                "calls": n,
                "errors": sum(1 for c in kc if not c.ok),
                "p50": _percentile(kok, 0.5),
                "p95": _percentile(kok, 0.95),
                "tokens": sum(c.prompt_tokens + c.completion_tokens for c in kc),
                "cost": sum(c.cost_rub for c in kc),
            }
        )
    return {
        "calls": len(calls),
        "errors": len(calls) - len(ok),
        "error_rate": (len(calls) - len(ok)) / len(calls) if calls else None,
        "p50": _percentile(lat, 0.5),
        "p95": _percentile(lat, 0.95),
        "prompt_tokens": sum(c.prompt_tokens for c in calls),
        "completion_tokens": sum(c.completion_tokens for c in calls),
        "cost": cost,
        "cost_per_call": cost / len(calls) if calls else None,
        "month_projection": month_projection,
        "budget": s.llm_budget_rub_month,
        "model": s.deepseek_model,
        "prices": (s.deepseek_price_input_usd, s.deepseek_price_output_usd, s.usd_rub),
        "kinds": kinds,
        "recent_errors": [c for c in reversed(calls) if not c.ok][:5],
        "series": [
            {
                "t": c.created_at.isoformat(),
                "s": round(c.latency_ms / 1000, 2),
                "ok": c.ok,
                "kind": LLM_KIND_LABEL.get(c.kind, c.kind),
            }
            for c in calls[-150:]
        ],
    }


def data_metrics(session: Session) -> dict:
    products = list(session.scalars(select(Product)))
    sales = list(session.scalars(select(DailySale)))
    if not products or not sales:
        return {"empty": True}
    first, last = min(s.day for s in sales), max(s.day for s in sales)
    days = (last - first).days + 1
    expected_rows = len(products) * days
    pairs = Counter((s.product_id, s.day) for s in sales)
    duplicates = sum(n - 1 for n in pairs.values() if n > 1)
    invalid = sum(
        1 for s in sales if s.units < 0 or s.stock_end < 0 or s.price is None or s.price <= 0
    )
    valid_rows = len(pairs) - invalid
    product_fields_ok = sum(
        1 for p in products if p.cost_price and p.cost_price > 0 and p.lead_time_days
    )
    with_reviews = session.scalar(
        select(func.count(func.distinct(Product.id))).where(Product.reviews.any())
    )
    with_ads = session.scalar(
        select(func.count(func.distinct(Product.id))).where(Product.campaigns.any())
    )
    lag_days = (date.today() - last).days
    return {
        "empty": False,
        "skus": len(products),
        "days": days,
        "period": (first, last),
        "rows": len(sales),
        "expected_rows": expected_rows,
        "completeness": valid_rows / expected_rows if expected_rows else 0.0,
        "duplicates": duplicates,
        "duplicate_rate": duplicates / len(sales) if sales else 0.0,
        "invalid": invalid,
        "product_fields": product_fields_ok / len(products),
        "with_reviews": with_reviews or 0,
        "with_ads": with_ads or 0,
        "lag_days": lag_days,
        "sources": [
            ("Демо-магазин (продажи, остатки, цены)", "подключён"),
            ("Реклама", "подключён"),
            ("Отзывы", "подключён"),
            ("API Wildberries", "не подключён"),
            ("API Ozon", "не подключён"),
            ("Загрузка Excel", "не подключён"),
        ],
    }


def collect(session: Session) -> dict:
    return {
        "value": value_metrics(session),
        "eval": evaluation(),
        "llm": llm_metrics(session),
        "data": data_metrics(session),
        "targets": {
            "p50": LLM_P50_TARGET_S,
            "p95": LLM_P95_TARGET_S,
            "dq": DQ_TARGET,
            "dup": DUPLICATES_TARGET,
            "acceptance": ACCEPTANCE_TARGET,
            "precision": PRECISION_TARGET,
            "recall": RECALL_TARGET,
        },
    }
