from __future__ import annotations

import random
from datetime import date
from dateutil.relativedelta import relativedelta


def generate_monthly_metrics(
    rng: random.Random,
    subscriptions: list[dict],
    risk_factors: dict[str, float],
    start_date: date,
    end_date: date,
    domain_cfg: dict | None = None,
) -> list[dict]:
    cfg = (domain_cfg or {}).get("monthly_metrics", {})
    active_users_mean = float(cfg.get("active_users_mean", 0.65))
    active_users_std = float(cfg.get("active_users_std", 0.18))
    api_calls_base = float(cfg.get("api_calls_base", 12000.0))
    api_calls_std = float(cfg.get("api_calls_std", 5000.0))
    storage_gb_base = float(cfg.get("storage_gb_base", 4.5))
    storage_gb_std = float(cfg.get("storage_gb_std", 2.0))
    feature_adoption_mean = float(cfg.get("feature_adoption_mean", 0.58))
    feature_adoption_std = float(cfg.get("feature_adoption_std", 0.20))
    nps_mean = float(cfg.get("nps_mean", 32.0))
    nps_std = float(cfg.get("nps_std", 18.0))

    sub_map = {s["subscription_id"]: s for s in subscriptions}

    rows = []
    current = date(start_date.year, start_date.month, 1)
    while current <= end_date:
        month_end = current + relativedelta(months=1) - relativedelta(days=1)
        for sub in subscriptions:
            sub_start = date.fromisoformat(sub["start_date"])
            sub_end_raw = sub["end_date"]
            sub_end = date.fromisoformat(sub_end_raw) if sub_end_raw else None

            if sub_start > month_end:
                continue
            if sub_end and sub_end < current:
                continue

            risk = risk_factors.get(sub["subscription_id"], 0.20)
            max_users = int(sub["max_users"])
            active_ratio = max(0.05, min(1.0, rng.gauss(active_users_mean - risk * 0.3, active_users_std)))
            active_users = max(1, round(max_users * active_ratio))
            licensed_users = max(active_users, round(max_users * rng.uniform(0.5, 1.0)))

            api_calls = max(0, round(rng.gauss(api_calls_base * (1 - risk * 0.4), api_calls_std)))
            storage_gb = max(0.1, round(rng.gauss(storage_gb_base, storage_gb_std), 2))
            feature_adoption = max(0.0, min(1.0, rng.gauss(feature_adoption_mean - risk * 0.2, feature_adoption_std)))
            nps_score = round(max(-100, min(100, rng.gauss(nps_mean - risk * 30, nps_std))))

            mrr = float(sub["mrr_eur"])
            revenue_at_risk = round(mrr * risk * rng.uniform(0.5, 1.2), 2)

            rows.append({
                "month_date": current.isoformat(),
                "subscription_id": sub["subscription_id"],
                "account_id": sub["account_id"],
                "plan_name": sub["plan_name"],
                "mrr_eur": round(mrr, 2),
                "active_users": active_users,
                "licensed_users": licensed_users,
                "active_user_ratio": round(active_ratio, 4),
                "api_calls": api_calls,
                "storage_gb": storage_gb,
                "feature_adoption_pct": round(feature_adoption, 4),
                "nps_score": nps_score,
                "revenue_at_risk_eur": revenue_at_risk,
            })
        current += relativedelta(months=1)
    return rows
