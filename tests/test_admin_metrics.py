from seller_assistant.services.admin_metrics import PRECISION_TARGET, RECALL_TARGET, evaluation
from seller_assistant.services.telemetry import call_cost_rub


def test_evaluation_meets_targets() -> None:
    e = evaluation()
    assert e["precision"] >= PRECISION_TARGET
    assert e["recall"] >= RECALL_TARGET
    assert not e["healthy_false_alarms"]


def test_llm_cost_is_positive_and_small() -> None:
    cost = call_cost_rub(1000, 500)
    assert 0 < cost < 1
