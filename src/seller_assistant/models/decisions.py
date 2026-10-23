"""Рекомендации системы и решения пользователя по ним (human-in-the-loop)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from seller_assistant.db import Base
from seller_assistant.models.catalog import Product


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # restock | stockout | overstock | ads_cut | …
    area: Mapped[str] = mapped_column(String(32))  # Остатки | Реклама | Карточка | Цена
    severity: Mapped[int] = mapped_column(Integer)  # 3 — критично, 2 — важно, 1 — к сведению
    title: Mapped[str] = mapped_column(String(255))
    cause: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    effect_rub: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False)
    )  # ожидаемый эффект за 30 дней
    effect_note: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSON)  # цифры, на которых основан вывод
    status: Mapped[str] = mapped_column(String(16), default="new")  # new|accepted|rejected
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product | None] = relationship()
    decisions: Mapped[list["DecisionLog"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class DecisionLog(Base):
    """Журнал управленческих решений: что система предложила и что решил человек."""

    __tablename__ = "decision_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(16))  # accepted | rejected
    comment: Mapped[str] = mapped_column(Text, default="")
    snapshot_title: Mapped[str] = mapped_column(String(255))
    snapshot_effect_rub: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recommendation: Mapped[Recommendation | None] = relationship(back_populates="decisions")
