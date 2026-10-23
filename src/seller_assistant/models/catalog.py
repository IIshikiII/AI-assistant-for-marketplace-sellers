"""Данные магазина: товары, продажи и остатки по дням, реклама, отзывы."""

from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from seller_assistant.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(128))
    marketplace: Mapped[str] = mapped_column(String(32))  # WB | Ozon
    cost_price: Mapped[float] = mapped_column(
        Numeric(12, 2, asdecimal=False)
    )  # себестоимость за штуку
    lead_time_days: Mapped[int] = mapped_column(Integer)  # срок поставки от поставщика
    # Кеш разбора отзывов от LLM, чтобы не платить за повторный запрос.
    review_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    sales: Mapped[list["DailySale"]] = relationship(
        back_populates="product", order_by="DailySale.day", cascade="all, delete-orphan"
    )
    campaigns: Mapped[list["AdCampaign"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="product", order_by="Review.day.desc()", cascade="all, delete-orphan"
    )


class DailySale(Base):
    """Продажи, цена и остаток на конец дня по одному товару."""

    __tablename__ = "daily_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date, index=True)
    units: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False))
    stock_end: Mapped[int] = mapped_column(Integer)

    product: Mapped[Product] = relationship(back_populates="sales")


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(64))  # поиск | каталог | карточка

    product: Mapped[Product] = relationship(back_populates="campaigns")
    days: Mapped[list["AdDaily"]] = relationship(
        back_populates="campaign", order_by="AdDaily.day", cascade="all, delete-orphan"
    )


class AdDaily(Base):
    __tablename__ = "ad_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("ad_campaigns.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date, index=True)
    spend: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False))
    clicks: Mapped[int] = mapped_column(Integer)
    orders: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False))

    campaign: Mapped[AdCampaign] = relationship(back_populates="days")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="reviews")
