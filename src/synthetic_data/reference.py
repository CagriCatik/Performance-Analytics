from __future__ import annotations


def build_plans_catalog(plans_cfg: dict) -> list[dict]:
    return [
        {
            "plan_name": p["name"],
            "tier": p["tier"],
            "monthly_price_eur": p["monthly_price_eur"],
            "annual_price_eur": p["annual_price_eur"],
            "max_users": p["max_users"],
            "churn_base": p["churn_base"],
        }
        for p in plans_cfg["plans"]
    ]


def build_regions(regions_cfg: dict) -> list[dict]:
    rows = []
    for region in regions_cfg["regions"]:
        for city in region["cities"]:
            rows.append({
                "region": region["name"],
                "country": city["country"],
                "city": city["name"],
                "latitude": city["latitude"],
                "longitude": city["longitude"],
            })
    return rows
