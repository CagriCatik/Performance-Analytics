from __future__ import annotations

import random

NAMES_BY_CITY: dict[str, list[str]] = {
    "Stuttgart": [
        "Nexura GmbH", "Praevio Solutions GmbH", "Kodevo Software AG", "Valensy Digital GmbH",
        "Trellix Systems Stuttgart", "Bluenode Technologies", "Lumara Enterprise GmbH",
        "Coriva Analytics", "Fenesta Cloud GmbH", "Zetora Software", "Vertevo Solutions",
        "Qentara AG Stuttgart", "Brixio Digital GmbH", "Celynx Platforms",
    ],
    "Munich": [
        "Navixio GmbH", "Proliant Software AG", "Crystalvex Munich", "Datalume GmbH",
        "Axero Platforms", "Skybridge Software GmbH", "Tenzar Analytics AG",
        "Celaris Cloud GmbH", "Quantex Digital", "Noveris Systems GmbH",
        "Florix Technologies", "Brevona Solutions AG", "Meridax Software", "Vortela GmbH",
    ],
    "Vienna": [
        "Kapiva Solutions GmbH", "Zentrix Digital AG", "Lumevo Software", "Corevex Austria",
        "Flexara Cloud GmbH", "Naltrix Systems AG", "Quantova Digital Vienna",
        "Stratum Analytics GmbH", "Arclytics Solutions", "Ventura Software AG",
        "Blendora Platforms GmbH", "Nexum Digital Austria", "Praxis Cloud AG",
    ],
    "Zurich": [
        "Nexora Switzerland AG", "Prolytic Software AG", "Celeron Cloud Zurich",
        "Datavex Switzerland", "Axion Platforms AG", "Skyra Digital GmbH",
        "Quantara Analytics AG", "Solevo Cloud AG", "Novaris Systems",
        "Fluvio Technologies AG", "Brenova Solutions", "Meridian Software AG",
    ],
    "Paris": [
        "Nexalis Solutions SA", "Prolvex Digital SA", "Crystalara Paris", "Datanome SAS",
        "Axelera Platforms", "Skylink Software SA", "Tenvex Analytics",
        "Celaris Cloud SA", "Quantrix Digital", "Noveris Systems SA",
        "Flomax Technologies", "Brevoria Solutions SA", "Meridax Digital Paris",
    ],
    "Brussels": [
        "Capivex Solutions NV", "Zentira Digital SA", "Lumevo Software NV", "Corevex Belgium",
        "Flexora Cloud NV", "Naltrex Systems SA", "Quantova Digital Brussels",
        "Stratus Analytics NV", "Arclex Solutions", "Ventura Software SA",
        "Blendix Platforms NV", "Nexum Digital Belgium", "Praxis Cloud NV",
    ],
    "Amsterdam": [
        "Nexora Netherlands BV", "Prolytic Software BV", "Celaris Cloud Amsterdam",
        "Datavex Netherlands", "Axion Platforms BV", "Skyra Digital NL",
        "Quantara Analytics BV", "Solevo Cloud BV", "Novaris Systems NL",
        "Fluvio Tech BV", "Brenova Solutions NL", "Meridian Software BV",
    ],
    "Madrid": [
        "Nexalis Solutions SL", "Prolux Digital SL", "Crystalara Madrid", "Datanome SL",
        "Axelera Platforms SL", "Skylink Software SL", "Tenvex Analytics SL",
        "Celaris Cloud SL", "Quantrix Digital SL", "Noveris Systems SL",
        "Flomax Technologies SL", "Brevoria Solutions SL", "Meridax Digital SL",
    ],
    "Barcelona": [
        "Capivex Solutions BCN", "Zentira Digital SL", "Lumevo Software BCN", "Corevex Cataluña",
        "Flexora Cloud SL", "Naltrex Systems BCN", "Quantova Digital Barcelona",
        "Stratus Analytics SL", "Arclex Solutions BCN", "Ventura Software SL",
    ],
    "Milan": [
        "Nexora Solutions SpA", "Prolytic Software SpA", "Celaris Cloud Milan",
        "Datavex Italia", "Axion Platforms SpA", "Skyra Digital IT",
        "Quantara Analytics SpA", "Solevo Cloud SpA", "Novaris Systems IT",
        "Fluvio Tech SpA", "Brenova Solutions IT", "Meridian Software SpA",
    ],
    "Rome": [
        "Capivex Solutions Roma", "Zentira Digital SpA", "Lumevo Software Roma", "Corevex Roma",
        "Flexora Cloud IT", "Naltrex Systems Roma", "Quantova Digital Roma",
        "Stratus Analytics Roma", "Arclex Solutions SpA", "Ventura Software Roma",
    ],
}


def _generate_account_name(city_name: str, rng: random.Random, used_names: set[str], index: int) -> str:
    pool = NAMES_BY_CITY.get(city_name, [])
    available = [n for n in pool if n not in used_names]
    if available:
        chosen = rng.choice(available)
        used_names.add(chosen)
        return chosen
    fallback = f"{city_name} Digital Solutions {index:02d}"
    counter = 1
    while fallback in used_names:
        fallback = f"{city_name} Software Inc {index:02d}-{counter}"
        counter += 1
    used_names.add(fallback)
    return fallback


def generate_accounts(
    rng: random.Random,
    count: int,
    regions_cfg: dict,
    domain_cfg: dict | None = None,
) -> list[dict]:
    cities = []
    for region in regions_cfg["regions"]:
        for city in region["cities"]:
            cities.append((region["name"], city))

    cfg = (domain_cfg or {}).get("accounts", {})
    jitter = float(cfg.get("coordinate_jitter", 0.10))
    segments = cfg.get("segments", ["SMB", "Mid-Market", "Enterprise"])
    segment_weights = cfg.get("segment_weights", [0.55, 0.30, 0.15])
    industries_cfg = cfg.get("industries", [{"name": "Technology", "weight": 1.0}])
    industry_names = [i["name"] for i in industries_cfg]
    industry_weights = [i["weight"] for i in industries_cfg]

    used_names: set[str] = set()
    rows = []
    for index in range(1, count + 1):
        region, city = rng.choice(cities)
        rows.append({
            "account_id": f"ACC{index:05d}",
            "account_name": _generate_account_name(city["name"], rng, used_names, index),
            "country": city["country"],
            "region": region,
            "city": city["name"],
            "latitude": round(float(city["latitude"]) + rng.uniform(-jitter, jitter), 6),
            "longitude": round(float(city["longitude"]) + rng.uniform(-jitter, jitter), 6),
            "segment": rng.choices(segments, weights=segment_weights, k=1)[0],
            "industry": rng.choices(industry_names, weights=industry_weights, k=1)[0],
        })
    return rows
