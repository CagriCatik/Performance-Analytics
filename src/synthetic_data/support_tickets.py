from __future__ import annotations

import random
from datetime import datetime, timedelta

from .common import random_datetime


def generate_support_tickets(
    rng: random.Random,
    count: int,
    subscriptions: list[dict],
    risk_factors: dict[str, float],
    start_dt: datetime,
    end_dt: datetime,
    domain_cfg: dict | None = None,
) -> list[dict]:
    cfg = (domain_cfg or {}).get("support_tickets", {})
    categories = cfg.get("categories", ["Billing", "Technical", "Onboarding", "Feature Request", "Security", "Integration"])
    severities = cfg.get("severities", ["Low", "Medium", "High", "Critical"])
    sev_weights = cfg.get("severity_weights", [0.40, 0.35, 0.18, 0.07])
    sev_factors = cfg.get("severity_factors", {"Low": 0.7, "Medium": 1.0, "High": 1.8, "Critical": 3.2})
    resolution_mean = float(cfg.get("resolution_mean_hours", 14.0))
    resolution_std = float(cfg.get("resolution_std_hours", 10.0))
    fcr_rate = float(cfg.get("first_contact_resolution_rate", 0.72))

    sub_weights = [max(0.1, risk_factors.get(s["subscription_id"], 0.20)) for s in subscriptions]
    rows = []
    for index in range(1, count + 1):
        sub = rng.choices(subscriptions, weights=sub_weights, k=1)[0]
        risk = risk_factors.get(sub["subscription_id"], 0.20)

        adjusted_weights = list(sev_weights)
        high_idx = severities.index("High") if "High" in severities else -1
        crit_idx = severities.index("Critical") if "Critical" in severities else -1
        if risk > 0.4:
            if high_idx >= 0:
                adjusted_weights[high_idx] *= (1 + risk)
            if crit_idx >= 0:
                adjusted_weights[crit_idx] *= (1 + risk * 2)

        severity = rng.choices(severities, weights=adjusted_weights, k=1)[0]
        factor = float(sev_factors.get(severity, 1.0))
        opened_at = random_datetime(rng, start_dt, end_dt)
        resolution_hours = max(0.5, rng.gauss(resolution_mean * factor, resolution_std))
        is_resolved = rng.random() < (0.85 if sub["status"] != "Churned" else 0.60)
        closed_at = (opened_at + timedelta(hours=resolution_hours)) if is_resolved else None
        if closed_at and closed_at > end_dt:
            closed_at = None
            is_resolved = False

        fcr = rng.random() < (fcr_rate * (1 - risk * 0.3))

        rows.append({
            "ticket_id": f"TKT{index:07d}",
            "subscription_id": sub["subscription_id"],
            "account_id": sub["account_id"],
            "opened_at": opened_at.isoformat(timespec="seconds"),
            "closed_at": closed_at.isoformat(timespec="seconds") if closed_at else "",
            "category": rng.choice(categories),
            "severity": severity,
            "status": "Closed" if is_resolved else "Open",
            "resolution_hours": round(resolution_hours, 2) if is_resolved else None,
            "first_contact_resolution": is_resolved and fcr,
            "escalated": not fcr and rng.random() < (0.15 * factor),
            "opened_date": opened_at.date().isoformat(),
            "country": sub["country"],
            "region": sub["region"],
            "plan_name": sub["plan_name"],
        })
    return rows
