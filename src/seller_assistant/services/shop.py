"""Работа с данными магазина в БД: загрузка, демо-данные, пересчёт рекомендаций, решения."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from seller_assistant.models import (
    AdCampaign,
    DecisionLog,
    Product,
    Recommendation,
)
from seller_assistant.services import analytics
from seller_assistant.services.demo_data import build_demo_shop


def load_products(session: Session) -> list[Product]:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.sales),
            selectinload(Product.reviews),
            selectinload(Product.campaigns).selectinload(AdCampaign.days),
        )
        .order_by(Product.sku)
    )
    return list(session.scalars(stmt))


def has_data(session: Session) -> bool:
    return bool(session.scalar(select(func.count(Product.id))))


def reset_demo(session: Session) -> None:
    """Полностью пересоздаёт демо-магазин. Журнал решений тоже очищается."""
    session.execute(delete(DecisionLog))
    session.execute(delete(Recommendation))
    session.execute(delete(Product))
    session.add_all(build_demo_shop())
    session.commit()
    refresh_recommendations(session)


def ensure_demo(session: Session) -> None:
    if not has_data(session):
        reset_demo(session)


def refresh_recommendations(session: Session) -> int:
    """Пересчитывает рекомендации. Те, по которым уже принято решение, не трогаем."""
    decided = {
        (r.product_id, r.kind)
        for r in session.scalars(select(Recommendation).where(Recommendation.status != "new"))
    }
    session.execute(delete(Recommendation).where(Recommendation.status == "new"))
    count = 0
    for rec in analytics.build_recommendations(load_products(session)):
        product_id = rec.product.id if rec.product else None
        if (product_id, rec.kind) in decided:
            continue
        session.add(
            Recommendation(
                product_id=product_id,
                kind=rec.kind,
                area=rec.area,
                severity=rec.severity,
                title=rec.title,
                cause=rec.cause,
                action=rec.action,
                effect_rub=round(rec.effect_rub, 2),
                effect_note=rec.effect_note,
                metrics=rec.metrics,
                status="new",
            )
        )
        count += 1
    session.commit()
    return count


def list_recommendations(
    session: Session, *, status: str | None = "new", area: str | None = None
) -> list[Recommendation]:
    stmt = select(Recommendation).options(selectinload(Recommendation.product))
    if status:
        stmt = stmt.where(Recommendation.status == status)
    if area:
        stmt = stmt.where(Recommendation.area == area)
    stmt = stmt.order_by(Recommendation.severity.desc(), Recommendation.effect_rub.desc())
    return list(session.scalars(stmt))


def decide(session: Session, rec: Recommendation, decision: str, comment: str) -> DecisionLog:
    if decision not in ("accepted", "rejected"):
        raise ValueError(decision)
    rec.status = decision
    log = DecisionLog(
        recommendation_id=rec.id,
        decision=decision,
        comment=comment.strip(),
        snapshot_title=rec.title,
        snapshot_effect_rub=rec.effect_rub,
    )
    session.add(log)
    session.commit()
    return log


def journal(session: Session) -> list[DecisionLog]:
    return list(session.scalars(select(DecisionLog).order_by(DecisionLog.created_at.desc())))


def overview(session: Session) -> tuple[dict, list[analytics.Stats]]:
    stats = [analytics.compute_stats(p) for p in load_products(session)]
    return analytics.kpis(stats), stats
