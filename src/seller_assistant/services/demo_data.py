"""Детерминированный демо-магазин: 60 дней продаж, остатков, рекламы и отзывов.

Реальных ключей API маркетплейсов в прототипе нет, поэтому данные синтетические,
но в них заложены типовые проблемы продавца — их и должна найти система:
дефицит, out-of-stock, неликвид, убыточная реклама, недогруженная реклама,
волна негативных отзывов, просадка после повышения цены и после отключения рекламы.
"""

import math
import random
from dataclasses import dataclass
from datetime import date, timedelta

from seller_assistant.models import AdCampaign, AdDaily, DailySale, Product, Review

DAYS = 60
SEED = 42


@dataclass(frozen=True)
class Spec:
    sku: str
    name: str
    category: str
    marketplace: str
    cost: float
    price: float
    daily: float  # средние продажи в день
    lead: int  # срок поставки, дней
    scenario: str = "normal"
    ad_drr: float = 0.12  # доля рекламных расходов от рекламной выручки


SPECS: list[Spec] = [
    Spec("WB-1001", "Термокружка 450 мл, нержавейка", "Посуда", "WB", 310, 990, 14, 21, "restock"),
    Spec("WB-1002", "Органайзер для косметики, 3 яруса", "Дом", "WB", 420, 1490, 9, 18, "stockout"),
    Spec("WB-1003", "Коврик для йоги 6 мм, TPE", "Спорт", "WB", 680, 2190, 6, 25, "ads_bad", 0.48),
    Spec(
        "WB-1004",
        "Лампа настольная LED с беспроводной зарядкой",
        "Электроника",
        "WB",
        1350,
        3790,
        4,
        30,
        "reviews_bad",
    ),
    Spec("WB-1005", "Набор контейнеров для еды, 5 шт", "Посуда", "WB", 290, 890, 18, 14),
    Spec("WB-1006", "Плед флисовый 150×200", "Текстиль", "WB", 520, 1690, 2, 21, "overstock"),
    Spec(
        "WB-1007",
        "Бутылка для воды 750 мл с таймером",
        "Спорт",
        "WB",
        180,
        690,
        22,
        14,
        "ads_good",
        0.05,
    ),
    Spec(
        "WB-1008",
        "Подушка ортопедическая с эффектом памяти",
        "Текстиль",
        "WB",
        890,
        2890,
        7,
        28,
        "price_up",
    ),
    Spec("WB-1009", "Массажёр для шеи электрический", "Электроника", "WB", 1100, 3290, 5, 30),
    Spec("WB-1010", "Сушилка для белья напольная", "Дом", "WB", 760, 2290, 3, 21, "overstock"),
    Spec(
        "WB-1011",
        "Зонт автоматический, ветрозащитный",
        "Аксессуары",
        "WB",
        450,
        1390,
        11,
        18,
        "ads_off",
    ),
    Spec("WB-1012", "Кофемолка ручная, керамические жернова", "Посуда", "WB", 640, 1990, 5, 25),
    Spec("OZ-2001", "Термокружка 450 мл, нержавейка", "Посуда", "Ozon", 310, 1020, 8, 21),
    Spec("OZ-2002", "Органайзер для косметики, 3 яруса", "Дом", "Ozon", 420, 1520, 5, 18),
    Spec(
        "OZ-2003",
        "Робот-пылесос, сухая уборка",
        "Электроника",
        "Ozon",
        5200,
        12990,
        2,
        35,
        "restock",
    ),
    Spec(
        "OZ-2004", "Набор ножей, 6 предметов", "Посуда", "Ozon", 980, 2990, 4, 25, "ads_bad", 0.39
    ),
    Spec("OZ-2005", "Гантели разборные 2×10 кг", "Спорт", "Ozon", 2100, 5490, 2, 30),
    Spec(
        "OZ-2006",
        "Увлажнитель воздуха ультразвуковой",
        "Электроника",
        "Ozon",
        1450,
        3990,
        6,
        30,
        "reviews_bad",
    ),
    Spec("OZ-2007", "Полотенца махровые, набор 3 шт", "Текстиль", "Ozon", 610, 1790, 7, 21),
    Spec(
        "OZ-2008",
        "Скакалка скоростная с подшипниками",
        "Спорт",
        "Ozon",
        140,
        590,
        15,
        14,
        "ads_good",
        0.06,
    ),
    Spec("OZ-2009", "Лампа-ночник детская", "Электроника", "Ozon", 390, 1290, 1, 25, "overstock"),
    Spec("OZ-2010", "Форма для запекания, стекло", "Посуда", "Ozon", 330, 990, 6, 18),
]

POSITIVE = [
    "Всё отлично, соответствует описанию.",
    "Хорошее качество за свои деньги, рекомендую.",
    "Доставили быстро, упаковка целая.",
    "Пользуюсь неделю, полёт нормальный.",
    "Брала в подарок, очень довольны.",
    "Качество приятно удивило.",
    "Как на фото, всё работает.",
]
NEUTRAL = [
    "В целом нормально, но цена могла бы быть ниже.",
    "Неплохо, но доставка заняла много времени.",
    "Средне. Ожидала чуть лучше по качеству.",
]
GENERIC_NEGATIVE = [
    "Пришло с царапиной, неприятно.",
    "Не понравилось, оформила возврат.",
]
# Повторяющиеся жалобы — их должен найти разбор отзывов.
DEFECTS: dict[str, list[str]] = {
    "WB-1004": [
        "Беспроводная зарядка не работает с моим телефоном, хотя в описании заявлена.",
        "Зарядка греется и отключается через 10 минут.",
        "Телефон заряжается только если положить идеально ровно, неудобно.",
        "Лампа мерцает на минимальной яркости, глаза устают.",
        "В описании про совместимость ничего толком нет, зарядка не подошла.",
        "Свет холодный, хотя на фото тёплый. Зарядка слабая.",
    ],
    "OZ-2006": [
        "Протекает снизу через неделю использования.",
        "Под увлажнителем лужа, вода течёт из бака.",
        "Очень шумный, спать невозможно, хотя написано «тихий».",
        "Бак треснул по шву, вода на полу.",
        "Шумит как вентилятор, ночной режим не спасает.",
        "Протёк, испортил тумбочку. Верните деньги.",
    ],
}

CAMPAIGN_KIND = ["Поиск", "Каталог", "Карточка товара"]


def _units(rng: random.Random, mean: float) -> int:
    """Продажи за день: шум вокруг среднего, без отрицательных значений."""
    if mean <= 0:
        return 0
    value = rng.gauss(mean, max(1.0, math.sqrt(mean)))
    return max(0, round(value))


def _weekday_factor(day: date) -> float:
    return 1.15 if day.weekday() in (5, 6) else 0.95


def build_demo_shop(today: date | None = None) -> list[Product]:
    """Собирает несохранённые ORM-объекты. Последний день данных — вчера."""
    rng = random.Random(SEED)
    end = (today or date.today()) - timedelta(days=1)
    start = end - timedelta(days=DAYS - 1)
    products: list[Product] = []

    for spec in SPECS:
        product = Product(
            sku=spec.sku,
            name=spec.name,
            category=spec.category,
            marketplace=spec.marketplace,
            cost_price=spec.cost,
            lead_time_days=spec.lead,
        )
        _fill_sales(product, spec, rng, start)
        _fill_ads(product, spec, rng)
        _fill_reviews(product, spec, rng, start)
        products.append(product)
    return products


def _fill_sales(product: Product, spec: Spec, rng: random.Random, start: date) -> None:
    daily = spec.daily
    # Стартовый запас и логика пополнения зависят от сценария.
    if spec.scenario == "overstock":
        stock = int(daily * 220)
    elif spec.scenario == "restock":
        stock = int(daily * (DAYS + 7))  # к концу периода останется ~неделя продаж
    elif spec.scenario == "stockout":
        stock = int(daily * (DAYS - 6))  # закончится за ~5 дней до конца
    else:
        stock = int(daily * 45)

    replenish = spec.scenario in (
        "normal",
        "ads_bad",
        "ads_good",
        "reviews_bad",
        "price_up",
        "ads_off",
    )
    for i in range(DAYS):
        day = start + timedelta(days=i)
        price = spec.price
        demand = daily * _weekday_factor(day)
        days_left = DAYS - i

        if spec.scenario == "price_up" and days_left <= 10:
            price = round(spec.price * 1.19, -1)
            demand *= 0.55
        if spec.scenario == "ads_off" and days_left <= 9:
            demand *= 0.5
        if spec.scenario == "reviews_bad" and days_left <= 18:
            demand *= 0.75

        units = min(stock, _units(rng, demand))
        stock -= units
        # Плановая поставка, когда запас падает ниже двух сроков поставки.
        if replenish and stock < daily * (spec.lead + 14):
            stock += int(daily * 45)
        product.sales.append(DailySale(day=day, units=units, price=price, stock_end=stock))


def _fill_ads(product: Product, spec: Spec, rng: random.Random) -> None:
    if spec.scenario == "overstock":
        return  # по неликвиду реклама не ведётся — тоже повод для рекомендации
    campaign = AdCampaign(
        name=f"{spec.name[:28]} — {rng.choice(CAMPAIGN_KIND)}", kind=rng.choice(CAMPAIGN_KIND)
    )
    for sale in product.sales:
        days_left = (product.sales[-1].day - sale.day).days + 1
        if spec.scenario == "ads_off" and days_left <= 9:
            continue  # кампания остановлена — бюджет закончился
        ad_orders = max(0, round(sale.units * rng.uniform(0.25, 0.4)))
        ad_revenue = ad_orders * float(sale.price)
        drr = spec.ad_drr * rng.uniform(0.85, 1.15)
        spend = round(ad_revenue * drr if ad_revenue else spec.price * spec.ad_drr * 0.5, 2)
        clicks = max(ad_orders, round(spend / rng.uniform(9, 16)))
        campaign.days.append(
            AdDaily(day=sale.day, spend=spend, clicks=clicks, orders=ad_orders, revenue=ad_revenue)
        )
    product.campaigns.append(campaign)


def _fill_reviews(product: Product, spec: Spec, rng: random.Random, start: date) -> None:
    for i in range(DAYS):
        day = start + timedelta(days=i)
        days_left = DAYS - i
        if spec.scenario == "reviews_bad" and days_left <= 20:
            if rng.random() < 0.6:
                if rng.random() < 0.7:
                    text, rating = rng.choice(DEFECTS[spec.sku]), rng.choice([1, 1, 2, 2, 3])
                else:
                    text, rating = rng.choice(POSITIVE), rng.choice([4, 5])
                product.reviews.append(Review(day=day, rating=rating, text=text))
            continue
        if rng.random() < min(0.6, spec.daily / 18):
            roll = rng.random()
            if roll < 0.75:
                text, rating = rng.choice(POSITIVE), rng.choice([5, 5, 5, 4])
            elif roll < 0.93:
                text, rating = rng.choice(NEUTRAL), rng.choice([3, 4])
            else:
                text, rating = rng.choice(GENERIC_NEGATIVE), rng.choice([1, 2])
            product.reviews.append(Review(day=day, rating=rating, text=text))
