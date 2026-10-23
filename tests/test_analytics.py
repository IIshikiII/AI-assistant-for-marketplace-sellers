"""Правила рекомендаций на демо-магазине: каждая заложенная проблема должна находиться.

Это и есть набор проверок (evaluation) детерминированной части: известные случаи
с ожидаемым результатом. Без БД — ORM-объекты не сохраняются.
"""

from datetime import date

import pytest

from seller_assistant.services.analytics import (
    build_recommendations,
    compute_stats,
    diagnose_drop,
    kpis,
)
from seller_assistant.services.demo_data import build_demo_shop

TODAY = date(2026, 10, 24)


@pytest.fixture(scope="module")
def shop():
    return {p.sku: p for p in build_demo_shop(TODAY)}


@pytest.fixture(scope="module")
def recs(shop):
    return {(r.product.sku, r.kind) for r in build_recommendations(list(shop.values()))}


@pytest.mark.parametrize(
    ("sku", "kind"),
    [
        ("WB-1002", "stockout"),  # товар закончился
        ("WB-1001", "restock"),  # закончится раньше, чем придёт поставка
        ("OZ-2003", "restock"),
        ("WB-1006", "overstock"),  # запас на полгода
        ("WB-1010", "overstock"),
        ("WB-1003", "ads_cut"),  # ДРР ~50%
        ("OZ-2004", "ads_cut"),
        ("WB-1007", "ads_scale"),  # реклама окупается с запасом
        ("WB-1004", "reviews"),  # повторяющийся дефект в отзывах
        ("OZ-2006", "reviews"),
        ("WB-1008", "price"),  # просадка после повышения цены
        ("WB-1011", "ads_off"),  # просадка после остановки рекламы
    ],
)
def test_known_problem_is_found(recs, sku, kind) -> None:
    assert (sku, kind) in recs


@pytest.mark.parametrize("sku", ["WB-1005", "WB-1009", "OZ-2001", "OZ-2010"])
def test_healthy_products_have_no_recommendations(recs, sku) -> None:
    assert not [k for s, k in recs if s == sku]


def test_root_cause_points_to_price(shop) -> None:
    causes = diagnose_drop(compute_stats(shop["WB-1008"]))
    assert any("цена" in c for c in causes)


def test_recommendations_sorted_by_severity_then_effect(shop) -> None:
    items = build_recommendations(list(shop.values()))
    keys = [(-r.severity, -r.effect_rub) for r in items]
    assert keys == sorted(keys)
    assert all(r.effect_rub >= 0 for r in items)


def test_kpis(shop) -> None:
    k = kpis([compute_stats(p) for p in shop.values()])
    assert k["skus"] == len(shop)
    assert k["out_of_stock"] >= 1
    assert k["revenue_7"] > 0
