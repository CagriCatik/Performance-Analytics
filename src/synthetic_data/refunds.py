from __future__ import annotations

import random
from datetime import datetime, timedelta

from .common import random_datetime


def generate_refunds(
    rng: random.Random,
    count: int,
    tickets: list[dict],
    domain_cfg: dict | None = None,
) -> list[dict]:
    cfg = (domain_cfg or {}).get("refunds", {})
    reasons = cfg.get("reasons", ["Service Outage", "Billing Error", "Cancellation Refund", "Duplicate Charge", "Dissatisfaction"])
    reason_weights = cfg.get("reason_weights", [0.20, 0.25, 0.30, 0.15, 0.10])
    approval_prob = float(cfg.get("approval_probability", 0.88))

    billing_tickets = [t for t in tickets if t.get("category") == "Billing"]
    pool = billing_tickets if billing_tickets else tickets

    rows = []
    for index in range(1, count + 1):
        ticket = rng.choice(pool)
        opened_dt = datetime.fromisoformat(ticket["opened_at"])
        claim_dt = opened_dt + timedelta(days=rng.randint(1, 14))
        reason = rng.choices(reasons, weights=reason_weights, k=1)[0]
        approved = rng.random() < approval_prob

        amount_base = rng.uniform(20.0, 500.0)
        if ticket.get("severity") == "Critical":
            amount_base *= rng.uniform(2.0, 4.0)
        elif ticket.get("severity") == "High":
            amount_base *= rng.uniform(1.3, 2.0)
        amount = round(amount_base, 2)

        rows.append({
            "refund_id": f"REF{index:06d}",
            "ticket_id": ticket["ticket_id"],
            "subscription_id": ticket["subscription_id"],
            "account_id": ticket["account_id"],
            "claim_date": claim_dt.date().isoformat(),
            "reason": reason,
            "amount_eur": amount if approved else 0.0,
            "approved": approved,
            "plan_name": ticket.get("plan_name", ""),
            "country": ticket.get("country", ""),
            "region": ticket.get("region", ""),
        })
    return rows
