"""ORM-модели. Каждую новую модель импортируйте здесь, иначе Alembic её не увидит."""

from seller_assistant.models.catalog import AdCampaign, AdDaily, DailySale, Product, Review
from seller_assistant.models.decisions import DecisionLog, Recommendation

__all__ = [
    "AdCampaign",
    "AdDaily",
    "DailySale",
    "DecisionLog",
    "Product",
    "Recommendation",
    "Review",
]
