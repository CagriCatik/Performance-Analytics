from __future__ import annotations

import random
from datetime import datetime

from .common import random_datetime


def generate_subscription_events(
    rng: random.Random,
    count: int,
    subscriptions: list[dict],
    risk_factors: dict[str, float],
    start_dt: datetime,
    end_dt: datetime,
    domain_cfg: dict | None = None,
) -> list[dict]:
    cfg = (domain_cfg or {}).get("subscription_events", {})
    event_types = cfg.get("event_types", ["Upgrade", "Downgrade", "Renewal", "Churn", "Reactivation"])
    event_weights = cfg.get("event_weights", [0.22, 0.10, 0.45, 0.16, 0.07])

    plan_order = ["Starter", "Pro", "Business", "Enterprise"]

    rows = []
    for index in range(1, count + 1):
        sub = rng.choice(subscriptions)
        risk = risk_factors.get(sub["subscription_id"], 0.20)

        adjusted_weights = list(event_weights)
        if risk > 0.5:
            churn_idx = event_types.index("Churn") if "Churn" in event_types else -1
            downgrade_idx = event_types.index("Downgrade") if "Downgrade" in event_types else -1
            if churn_idx >= 0:
                adjusted_weights[churn_idx] *= (1 + risk * 2)
            if downgrade_idx >= 0:
                adjusted_weights[downgrade_idx] *= (1 + risk)

        event_type = rng.choices(event_types, weights=adjusted_weights, k=1)[0]
        event_dt = random_datetime(rng, start_dt, end_dt)
        current_plan = sub["plan_name"]
        current_idx = plan_order.index(current_plan) if current_plan in plan_order else 1

        if event_type == "Upgrade":
            new_plan = plan_order[min(current_idx + 1, len(plan_order) - 1)]
        elif event_type == "Downgrade":
            new_plan = plan_order[max(current_idx - 1, 0)]
        else:
            new_plan = current_plan

        rows.append({
            "event_id": f"EVT{index:07d}",
            "subscription_id": sub["subscription_id"],
            "account_id": sub["account_id"],
            "event_type": event_type,
            "event_date": event_dt.date().isoformat(),
            "event_timestamp": event_dt.isoformat(timespec="seconds"),
            "from_plan": current_plan,
            "to_plan": new_plan,
            "mrr_change_eur": round(
                rng.gauss(0, 50) if event_type in ("Renewal",) else
                rng.uniform(20, 150) if event_type == "Upgrade" else
                rng.uniform(-120, -10) if event_type in ("Downgrade", "Churn") else
                rng.uniform(-30, 30),
                2,
            ),
            "region": sub["region"],
            "country": sub["country"],
        })
    return rows
