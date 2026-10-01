from __future__ import annotations

import copy
import random

COUNTRY_VARIANTS = {
    "Germany": ["Germany", "GERMANY", "DE", "Deutschland", " Germany "],
    "France": ["France", "FRANCE", "FR", " France "],
    "Spain": ["Spain", "SPAIN", "ES", " Spain "],
    "Italy": ["Italy", "ITALY", "IT", " Italy "],
    "Austria": ["Austria", "AT", " Austria "],
    "Switzerland": ["Switzerland", "CH", " Switzerland "],
    "Belgium": ["Belgium", "BE", " Belgium "],
    "Netherlands": ["Netherlands", "NL", " Netherlands "],
}


def inject_quality_issues(
    rng: random.Random,
    rows: list[dict],
    inconsistent_text_ratio: float,
    missing_optional_ratio: float,
    duplicate_ratio: float,
    domain_cfg: dict | None = None,
) -> list[dict]:
    dirty = copy.deepcopy(rows)
    if not dirty:
        return dirty

    cfg = (domain_cfg or {}).get("data_quality", {})
    country_variants = cfg.get("country_variants", COUNTRY_VARIANTS)
    optional_fields = cfg.get("optional_fields", ["closed_at", "completed_at", "base_location"])

    country_rows = [row for row in dirty if "country" in row and row.get("country") in country_variants]
    for row in rng.sample(country_rows, min(len(country_rows), round(len(dirty) * inconsistent_text_ratio))):
        row["country"] = rng.choice(country_variants[row["country"]])

    candidates = [(row, field) for row in dirty for field in optional_fields if field in row and row.get(field) not in {"", None}]
    for row, field in rng.sample(candidates, min(len(candidates), round(len(dirty) * missing_optional_ratio))):
        row[field] = ""

    duplicate_count = min(len(dirty), round(len(dirty) * duplicate_ratio))
    if duplicate_count > 0:
        dirty.extend(copy.deepcopy(rng.sample(dirty, duplicate_count)))
        rng.shuffle(dirty)
    return dirty

