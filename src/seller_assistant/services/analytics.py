"""Аналитика и правила рекомендаций. Чистые функции, без БД и без LLM.

Все цифры в рекомендациях считает этот модуль — детерминированно и проверяемо.
LLM потом только объясняет их человеческим языком (services/ai.py) и не придумывает чисел.
"""

import math
from dataclasses import dataclass, field

from seller_assistant.models import Product

# Допущения экономики. Выводятся в интерфейсе, чтобы было видно, на чём основан расчёт.
COMMISSION = {"WB": 0.20, "Ozon": 0.18}  # комиссия маркетплейса от цены
LOGISTICS_PER_UNIT = 70.0  # логистика и хранение на одну продажу, ₽
HOLDING_COST_MONTH = 0.05  # стоимость заморозки денег в остатках: хранение + капитал, в месяц
TARGET_DRR = 0.15  # целевая доля рекламных расходов
SAFETY_DAYS = 7  # страховой запас поверх срока поставки
REORDER_HORIZON = 30  # закупаем на срок поставки + 30 дней продаж
OVERSTOCK_DAYS = 120  # запас больше чем на 4 месяца — избыточный

ASSUMPTIONS = {
    "Комиссия WB": "20% от цены",
    "Комиссия Ozon": "18% от цены",
    "Логистика и хранение": f"{LOGISTICS_PER_UNIT:.0f} ₽ на продажу",
    "Стоимость заморозки остатков": f"{HOLDING_COST_MONTH:.0%} в месяц",
    "Целевой ДРР": f"{TARGET_DRR:.0%}",
    "Страховой запас": f"{SAFETY_DAYS} дней",
    "Горизонт эффекта": "30 дней",
}


@dataclass
class Stats:
    """Сводные показатели по одному товару на последний день данных."""

    product: Product
    price: float
    unit_margin: float
    units_7: int
    units_prev7: int
    revenue_7: float
    revenue_prev7: float
    revenue_30: float
    forecast_daily: float  # прогноз продаж в день: среднее за 14 дней без дней out-of-stock
    stock: int
    cover_days: float  # на сколько дней хватит остатка
    oos_days_7: int
    price_14_ago: float
    ad_spend_14: float
    ad_revenue_14: float
    ad_orders_14: int
    ad_spend_7: float
    ad_spend_prev7: float
    rating_30: float | None
    rating_before: float | None
    reviews_30: int
    negative_share_30: float
    history: list[dict] = field(default_factory=list)

    @property
    def drr_14(self) -> float | None:
        return self.ad_spend_14 / self.ad_revenue_14 if self.ad_revenue_14 else None

    @property
    def sales_change(self) -> float | None:
        return (self.units_7 - self.units_prev7) / self.units_prev7 if self.units_prev7 else None

    @property
    def price_change(self) -> float:
        return (self.price - self.price_14_ago) / self.price_14_ago if self.price_14_ago else 0.0

    @property
    def margin_ratio(self) -> float:
        return self.unit_margin / self.price if self.price else 0.0


def unit_margin(product: Product, price: float) -> float:
    commission = COMMISSION.get(product.marketplace, 0.2)
    return price * (1 - commission) - float(product.cost_price) - LOGISTICS_PER_UNIT


def compute_stats(product: Product) -> Stats:
    sales = sorted(product.sales, key=lambda s: s.day)
    last = sales[-1]
    last7, prev7, last14, last30 = sales[-7:], sales[-14:-7], sales[-14:], sales[-30:]

    in_stock = [s for s in last14 if s.stock_end > 0 or s.units > 0]
    forecast = sum(s.units for s in in_stock) / len(in_stock) if in_stock else 0.0
    if forecast == 0:  # товар закончился две недели назад — берём спрос до этого
        before = [s for s in sales[:-14] if s.units > 0]
        forecast = sum(s.units for s in before[-14:]) / max(1, len(before[-14:]))

    ads = [d for c in product.campaigns for d in c.days]
    last_day = last.day
    ads14 = [d for d in ads if (last_day - d.day).days < 14]
    ads7 = [d for d in ads14 if (last_day - d.day).days < 7]
    ads_prev7 = [d for d in ads14 if (last_day - d.day).days >= 7]

    reviews = list(product.reviews)
    r30 = [r for r in reviews if (last_day - r.day).days < 30]
    rbefore = [r for r in reviews if (last_day - r.day).days >= 30]

    price = float(last.price)
    return Stats(
        product=product,
        price=price,
        unit_margin=unit_margin(product, price),
        units_7=sum(s.units for s in last7),
        units_prev7=sum(s.units for s in prev7),
        revenue_7=sum(s.units * float(s.price) for s in last7),
        revenue_prev7=sum(s.units * float(s.price) for s in prev7),
        revenue_30=sum(s.units * float(s.price) for s in last30),
        forecast_daily=forecast,
        stock=last.stock_end,
        cover_days=last.stock_end / forecast if forecast else math.inf,
        oos_days_7=sum(1 for s in last7 if s.stock_end == 0),
        price_14_ago=float(sales[-14].price),
        ad_spend_14=sum(float(d.spend) for d in ads14),
        ad_revenue_14=sum(float(d.revenue) for d in ads14),
        ad_orders_14=sum(d.orders for d in ads14),
        ad_spend_7=sum(float(d.spend) for d in ads7),
        ad_spend_prev7=sum(float(d.spend) for d in ads_prev7),
        rating_30=sum(r.rating for r in r30) / len(r30) if r30 else None,
        rating_before=sum(r.rating for r in rbefore) / len(rbefore) if rbefore else None,
        reviews_30=len(r30),
        negative_share_30=sum(1 for r in r30 if r.rating <= 2) / len(r30) if r30 else 0.0,
        history=[
            {
                "day": s.day.isoformat(),
                "units": s.units,
                "stock": s.stock_end,
                "price": float(s.price),
            }
            for s in sales
        ],
    )


def diagnose_drop(st: Stats) -> list[str]:
    """Root cause: какие факторы объясняют просадку продаж. Пустой список — причина не найдена."""
    causes = []
    if st.oos_days_7 >= 2 or st.cover_days < 3:
        causes.append(f"нет товара на складе ({st.oos_days_7} дн. из 7 без остатка)")
    if st.price_change > 0.08:
        causes.append(f"цена выросла на {st.price_change:.0%} за 2 недели")
    if st.ad_spend_prev7 > 0 and st.ad_spend_7 < st.ad_spend_prev7 * 0.5:
        causes.append(
            f"рекламный бюджет упал с {st.ad_spend_prev7:,.0f} до {st.ad_spend_7:,.0f} ₽/нед"
        )
    if st.reviews_30 >= 5 and st.negative_share_30 >= 0.3:
        causes.append(f"доля негативных отзывов {st.negative_share_30:.0%} за 30 дней")
    return causes


@dataclass
class Rec:
    product: Product | None
    kind: str
    area: str
    severity: int
    title: str
    cause: str
    action: str
    effect_rub: float
    effect_note: str
    metrics: dict


def _rub(x: float) -> str:
    return f"{x:,.0f} ₽".replace(",", " ")


def build_recommendations(products: list[Product]) -> list[Rec]:
    recs: list[Rec] = []
    for product in products:
        st = compute_stats(product)
        recs.extend(_stock_rules(st))
        recs.extend(_ads_rules(st))
        recs.extend(_card_rules(st))
        recs.extend(_price_and_drop_rules(st))
    recs.sort(key=lambda r: (-r.severity, -r.effect_rub))
    return recs


def _base_metrics(st: Stats) -> dict:
    return {
        "Цена": _rub(st.price),
        "Маржа с единицы": _rub(st.unit_margin),
        "Продажи 7 дн / пред. 7 дн": f"{st.units_7} / {st.units_prev7} шт",
        "Прогноз спроса": f"{st.forecast_daily:.1f} шт/день",
        "Остаток": f"{st.stock} шт",
        "Хватит на": "∞" if math.isinf(st.cover_days) else f"{st.cover_days:.0f} дн",
        "Срок поставки": f"{st.product.lead_time_days} дн",
    }


def _stock_rules(st: Stats) -> list[Rec]:
    p, lead = st.product, st.product.lead_time_days
    order_qty = math.ceil(st.forecast_daily * (lead + REORDER_HORIZON) - st.stock)
    daily_margin = st.forecast_daily * max(st.unit_margin, 0)

    if st.stock == 0:
        return [
            Rec(
                p,
                "stockout",
                "Остатки",
                3,
                f"Товар закончился: {p.name} ({p.marketplace})",
                f"Остаток 0 шт, {st.oos_days_7} из последних 7 дней без продаж из-за отсутствия "
                f"товара. Спрос до обнуления — {st.forecast_daily:.1f} шт/день.",
                f"Срочно заказать {order_qty} шт у поставщика (срок поставки {lead} дн.) и "
                "проверить, можно ли ускорить отгрузку или перебросить товар с другого склада.",
                daily_margin * 30,
                f"Каждый день без товара теряется ≈{_rub(daily_margin)} маржи; "
                "к тому же карточка теряет позиции в выдаче.",
                _base_metrics(st) | {"Рекомендуемый заказ": f"{order_qty} шт"},
            )
        ]

    if st.cover_days < lead + SAFETY_DAYS:
        gap_days = max(1.0, lead - st.cover_days)
        severity = 3 if st.cover_days < lead else 2
        return [
            Rec(
                p,
                "restock",
                "Остатки",
                severity,
                f"Риск дефицита через {st.cover_days:.0f} дн: {p.name} ({p.marketplace})",
                f"Остатка {st.stock} шт хватит на {st.cover_days:.0f} дн при спросе "
                f"{st.forecast_daily:.1f} шт/день, а поставка идёт {lead} дн.",
                f"Разместить заказ на {order_qty} шт сегодня (покрытие на срок поставки + "
                f"{REORDER_HORIZON} дней).",
                min(gap_days, 30) * daily_margin,
                f"Без заказа товара не будет ≈{gap_days:.0f} дн — потеря ≈{_rub(daily_margin)} "
                "маржи в день.",
                _base_metrics(st) | {"Рекомендуемый заказ": f"{order_qty} шт"},
            )
        ]

    if st.cover_days > OVERSTOCK_DAYS:
        excess = st.stock - st.forecast_daily * 60
        frozen = excess * float(p.cost_price)
        if frozen > 30_000:
            return [
                Rec(
                    p,
                    "overstock",
                    "Остатки",
                    2,
                    f"Неликвид: запаса на {st.cover_days:.0f} дн — {p.name} ({p.marketplace})",
                    f"На складе {st.stock} шт при продажах {st.forecast_daily:.1f} шт/день. "
                    f"Сверх двухмесячной потребности заморожено ≈{_rub(frozen)} по себестоимости. "
                    "Рекламы по товару нет.",
                    "Не заказывать товар до снижения запаса. Запустить акцию со скидкой 10–15% и "
                    "небольшую рекламную кампанию; при отсутствии эффекта за 2 недели — "
                    "распродажа или вывоз со склада маркетплейса.",
                    frozen * HOLDING_COST_MONTH,
                    f"Высвобождение ≈{_rub(frozen)} оборотных денег; содержание излишка стоит "
                    f"≈{_rub(frozen * HOLDING_COST_MONTH)} в месяц.",
                    _base_metrics(st) | {"Заморожено в излишке": _rub(frozen)},
                )
            ]
    return []


def _ads_rules(st: Stats) -> list[Rec]:
    p, drr = st.product, st.drr_14
    if drr is None or st.ad_spend_14 < 1000:
        return []
    ad_profit_14 = st.ad_orders_14 * st.unit_margin - st.ad_spend_14
    metrics = _base_metrics(st) | {
        "Расход на рекламу 14 дн": _rub(st.ad_spend_14),
        "Выручка с рекламы 14 дн": _rub(st.ad_revenue_14),
        "ДРР": f"{drr:.0%}",
        "Прибыль с рекламы 14 дн": _rub(ad_profit_14),
    }
    if drr > TARGET_DRR * 2:
        loss_30 = max(0.0, -ad_profit_14) / 14 * 30
        saving_30 = st.ad_spend_14 / 14 * 30 * 0.4
        return [
            Rec(
                p,
                "ads_cut",
                "Реклама",
                3 if ad_profit_14 < 0 else 2,
                f"Реклама в минус: ДРР {drr:.0%} — {p.name} ({p.marketplace})",
                f"За 14 дней потрачено {_rub(st.ad_spend_14)}, реклама принесла "
                f"{_rub(st.ad_revenue_14)} выручки ({st.ad_orders_14} заказов). "
                f"ДРР {drr:.0%} при целевом {TARGET_DRR:.0%}; с учётом маржи "
                f"{_rub(st.unit_margin)}/шт кампания "
                f"{'убыточна' if ad_profit_14 < 0 else 'малоприбыльна'}.",
                "Снизить ставки на 40%, отключить фразы с нулевыми заказами, оставить только "
                "поисковые запросы с конверсией. Через 7 дней сравнить ДРР.",
                max(loss_30, saving_30 * 0.5),
                f"Сокращение неэффективных расходов ≈{_rub(saving_30)} за 30 дней.",
                metrics,
            )
        ]
    if drr < TARGET_DRR / 2 and st.cover_days > st.product.lead_time_days + SAFETY_DAYS:
        extra_profit_30 = ad_profit_14 / 14 * 30 * 0.5
        return [
            Rec(
                p,
                "ads_scale",
                "Реклама",
                1,
                f"Реклама недогружена: ДРР {drr:.0%} — {p.name} ({p.marketplace})",
                f"Кампания окупается с запасом: ДРР {drr:.0%}, прибыль с рекламы "
                f"{_rub(ad_profit_14)} за 14 дней. Остатка хватит на {st.cover_days:.0f} дн.",
                "Увеличить дневной бюджет на 50% и поднять ставки в топовых запросах; следить, "
                "чтобы ДРР не превысил 12% и хватило остатков.",
                max(0.0, extra_profit_30),
                "Дополнительная маржа при сохранении текущей эффективности.",
                metrics,
            )
        ]
    return []


def _card_rules(st: Stats) -> list[Rec]:
    p = st.product
    if st.reviews_30 < 8 or st.negative_share_30 < 0.3:
        return []
    lost = st.revenue_30 * 0.15 * st.margin_ratio
    rating_note = (
        f"Средняя оценка упала с {st.rating_before:.1f} до {st.rating_30:.1f}."
        if st.rating_before and st.rating_30
        else ""
    )
    return [
        Rec(
            p,
            "reviews",
            "Карточка",
            3 if st.negative_share_30 >= 0.45 else 2,
            f"Волна негативных отзывов ({st.negative_share_30:.0%}) — {p.name} ({p.marketplace})",
            f"За 30 дней {st.reviews_30} отзывов, из них {st.negative_share_30:.0%} с оценкой 1–2. "
            f"{rating_note} Похоже на повторяющуюся проблему товара или описания.",
            "Разобрать отзывы (кнопка «Разбор отзывов ИИ» в карточке товара), исправить описание "
            "и фото под реальные свойства, ответить покупателям, передать претензии поставщику.",
            lost,
            "Падение рейтинга снижает конверсию карточки; оценка потерь — 15% маржи за 30 дней.",
            _base_metrics(st)
            | {
                "Отзывов за 30 дн": str(st.reviews_30),
                "Негативных": f"{st.negative_share_30:.0%}",
                "Рейтинг 30 дн / раньше": f"{st.rating_30 or 0:.1f} / {st.rating_before or 0:.1f}",
            },
        )
    ]


def _price_and_drop_rules(st: Stats) -> list[Rec]:
    p, change = st.product, st.sales_change
    if change is None or change > -0.25 or st.stock == 0 or st.units_prev7 < 10:
        return []  # без просадки или дефицит уже разобран правилом остатков
    causes = diagnose_drop(st)
    lost_units_30 = (st.units_prev7 - st.units_7) / 7 * 30
    old_margin = unit_margin(p, st.price_14_ago)
    metrics = _base_metrics(st) | {
        "Изменение продаж": f"{change:.0%}",
        "Цена 14 дн назад": _rub(st.price_14_ago),
        "Реклама 7 дн / пред. 7 дн": f"{_rub(st.ad_spend_7)} / {_rub(st.ad_spend_prev7)}",
    }

    if st.price_change > 0.08:
        other = ", ".join(c for c in causes if "цена" not in c)
        margin_now = st.units_7 / 7 * 30 * st.unit_margin
        margin_before = st.units_prev7 / 7 * 30 * old_margin
        return [
            Rec(
                p,
                "price",
                "Цена",
                3 if margin_before > margin_now else 2,
                f"Продажи −{-change:.0%} после повышения цены — {p.name} ({p.marketplace})",
                f"Цену подняли с {_rub(st.price_14_ago)} до {_rub(st.price)} "
                f"(+{st.price_change:.0%}), продажи упали с {st.units_prev7} до {st.units_7} "
                f"шт/нед. Другие факторы: {other or 'не выявлены'}.",
                f"Вернуть цену к {_rub(st.price_14_ago)} или протестировать промежуточную "
                f"{_rub((st.price + st.price_14_ago) / 2)} на 7 дней.",
                max(0.0, margin_before - margin_now),
                f"Маржа за 30 дней: сейчас ≈{_rub(margin_now)}, при прежней цене ≈"
                f"{_rub(margin_before)}.",
                metrics,
            )
        ]

    if any("рекламный бюджет" in c for c in causes):
        return [
            Rec(
                p,
                "ads_off",
                "Реклама",
                3,
                f"Продажи −{-change:.0%}: остановилась реклама — {p.name} ({p.marketplace})",
                f"Продажи упали с {st.units_prev7} до {st.units_7} шт/нед. Найденная причина: "
                f"{'; '.join(causes)}. Остатки и цена в норме.",
                "Проверить баланс рекламного кабинета и статус кампании, возобновить показы "
                "с прежним бюджетом.",
                lost_units_30 * st.unit_margin,
                f"Возврат ≈{lost_units_30:.0f} шт продаж за 30 дней.",
                metrics,
            )
        ]

    if not causes:
        return [
            Rec(
                p,
                "drop",
                "Продажи",
                2,
                f"Продажи −{-change:.0%} без очевидной причины — {p.name} ({p.marketplace})",
                "Остатки, цена, реклама и отзывы не изменились. Возможные причины — "
                "конкуренты, сезонность или позиции в поиске.",
                "Проверить цены конкурентов и позиции карточки по ключевым запросам.",
                lost_units_30 * max(st.unit_margin, 0),
                "Оценка потерь при сохранении тренда.",
                metrics,
            )
        ]
    return []


def kpis(stats: list[Stats]) -> dict:
    rev7 = sum(s.revenue_7 for s in stats)
    rev_prev = sum(s.revenue_prev7 for s in stats)
    margin7 = sum(s.units_7 * s.unit_margin for s in stats) - sum(s.ad_spend_7 for s in stats)
    ad7 = sum(s.ad_spend_7 for s in stats)
    ad_rev14 = sum(s.ad_revenue_14 for s in stats)
    ad14 = sum(s.ad_spend_14 for s in stats)
    at_risk = [s for s in stats if s.stock == 0 or s.cover_days < s.product.lead_time_days]
    frozen = sum(
        max(0.0, s.stock - s.forecast_daily * 60) * float(s.product.cost_price)
        for s in stats
        if s.cover_days > OVERSTOCK_DAYS
    )
    ratings = [s.rating_30 for s in stats if s.rating_30]
    return {
        "revenue_7": rev7,
        "revenue_change": (rev7 - rev_prev) / rev_prev if rev_prev else 0.0,
        "margin_7": margin7,
        "ad_spend_7": ad7,
        "drr_14": ad14 / ad_rev14 if ad_rev14 else 0.0,
        "skus": len(stats),
        "at_risk": len(at_risk),
        "out_of_stock": sum(1 for s in stats if s.stock == 0),
        "frozen": frozen,
        "rating": sum(ratings) / len(ratings) if ratings else 0.0,
    }
