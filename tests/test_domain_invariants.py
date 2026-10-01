from __future__ import annotations

import random
from datetime import date, datetime
from pathlib import Path

from src.synthetic_data.accounts import generate_accounts
from src.synthetic_data.config import load_yaml
from src.synthetic_data.monthly_metrics import generate_monthly_metrics
from src.synthetic_data.refunds import generate_refunds
from src.synthetic_data.subscription_events import generate_subscription_events
from src.synthetic_data.subscriptions import generate_subscriptions
from src.synthetic_data.support_tickets import generate_support_tickets
from src.synthetic_data.validation import validate_dataset


def _clean_dataset(seed: int = 42) -> tuple[dict[str, list[dict]], dict[str, float]]:
    root = Path(__file__).resolve().parents[1]
    rng = random.Random(seed)
    regions = load_yaml(root / "config" / "regions.yaml")
    plans = load_yaml(root / "config" / "plans.yaml")
    accounts = generate_accounts(rng, 20, regions)
    subscriptions, risk = generate_subscriptions(rng, 60, accounts, plans, 0.15)
    metrics = generate_monthly_metrics(rng, subscriptions, risk, date(2025, 1, 1), date(2025, 3, 31))
    events = generate_subscription_events(rng, 200, subscriptions, risk, datetime(2025, 1, 1), datetime(2025, 3, 31, 23, 59, 59))
    tickets = generate_support_tickets(rng, 300, subscriptions, risk, datetime(2025, 1, 1), datetime(2025, 3, 31, 23, 59, 59))
    refunds = generate_refunds(rng, 50, tickets)
    return {
        "accounts": accounts,
        "subscriptions": subscriptions,
        "monthly_metrics": metrics,
        "subscription_events": events,
        "support_tickets": tickets,
        "refunds": refunds,
    }, risk


def test_clean_dataset_preserves_referential_integrity() -> None:
    dataset, _ = _clean_dataset()
    validate_dataset(dataset)


def test_higher_risk_subscriptions_receive_more_tickets() -> None:
    dataset, risk = _clean_dataset()
    counts = {sub_id: 0 for sub_id in risk}
    for ticket in dataset["support_tickets"]:
        if ticket["subscription_id"] in counts:
            counts[ticket["subscription_id"]] += 1
    ordered = sorted(risk, key=risk.get)
    low = ordered[: max(5, len(ordered) // 5)]
    high = ordered[-max(5, len(ordered) // 5):]
    low_avg = sum(counts[s] for s in low) / len(low)
    high_avg = sum(counts[s] for s in high) / len(high)
    assert high_avg > low_avg


def test_higher_risk_subscriptions_have_lower_feature_adoption() -> None:
    dataset, risk = _clean_dataset()
    adoption: dict[str, list[float]] = {sub_id: [] for sub_id in risk}
    for row in dataset["monthly_metrics"]:
        if row["subscription_id"] in adoption:
            adoption[row["subscription_id"]].append(float(row["feature_adoption_pct"]))
    ordered = sorted(risk, key=risk.get)
    low = [s for s in ordered[: max(5, len(ordered) // 5)] if adoption[s]]
    high = [s for s in ordered[-max(5, len(ordered) // 5):] if adoption[s]]
    if not low or not high:
        return
    low_avg = sum(sum(adoption[s]) / len(adoption[s]) for s in low) / len(low)
    high_avg = sum(sum(adoption[s]) / len(adoption[s]) for s in high) / len(high)
    assert high_avg < low_avg
