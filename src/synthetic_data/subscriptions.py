from __future__ import annotations

import random
from datetime import date, timedelta


def generate_subscriptions(
    rng: random.Random,
    count: int,
    accounts: list[dict],
    plans_cfg: dict,
    churned_ratio: float = 0.12,
    domain_cfg: dict | None = None,
) -> tuple[list[dict], dict[str, float]]:
    plans = plans_cfg["plans"]
    plan_names = [p["name"] for p in plans]
    plan_weights = [p["weight"] for p in plans]
    plan_map = {p["name"]: p for p in plans}

    cfg = (domain_cfg or {}).get("subscriptions", {})
    billing_cycles = cfg.get("billing_cycles", ["Monthly", "Annual"])
    billing_weights = cfg.get("billing_cycle_weights", [0.45, 0.55])

    start_pool = date(2023, 1, 1)
    end_pool = date(2025, 6, 30)
    total_days = (end_pool - start_pool).days

    critical_count = max(1, int(count * churned_ratio))
    critical_ids: set[int] = set(rng.sample(range(1, count + 1), min(critical_count, count)))

    risk_factors: dict[str, float] = {}
    rows = []
    for index in range(1, count + 1):
        account = rng.choice(accounts)
        plan_name = rng.choices(plan_names, weights=plan_weights, k=1)[0]
        plan = plan_map[plan_name]
        billing_cycle = rng.choices(billing_cycles, weights=billing_weights, k=1)[0]

        start_date = start_pool + timedelta(days=rng.randint(0, total_days))
        age_months = max(1, (date(2025, 12, 31) - start_date).days // 30)

        is_churned = index in critical_ids
        if is_churned:
            # Churned subscriptions ended sometime in 2025
            end_date = start_date + timedelta(days=rng.randint(30, min(age_months * 30, 600)))
            if end_date > date(2025, 12, 31):
                end_date = date(2025, 12, 31)
            status = "Churned"
            risk = rng.uniform(0.55, 0.90)
        else:
            end_date = None
            status = rng.choices(["Active", "Trial", "Suspended"], weights=[0.90, 0.07, 0.03], k=1)[0]
            risk = rng.uniform(0.05, 0.45)

        price = plan["annual_price_eur"] if billing_cycle == "Annual" else plan["monthly_price_eur"] * 12
        risk_factors[f"SUB{index:06d}"] = risk

        rows.append({
            "subscription_id": f"SUB{index:06d}",
            "account_id": account["account_id"],
            "plan_name": plan_name,
            "plan_tier": plan["tier"],
            "billing_cycle": billing_cycle,
            "annual_value_eur": round(price, 2),
            "mrr_eur": round(price / 12, 2),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat() if end_date else "",
            "status": status,
            "age_months": age_months,
            "max_users": plan["max_users"],
            "country": account["country"],
            "region": account["region"],
        })
    return rows, risk_factors
