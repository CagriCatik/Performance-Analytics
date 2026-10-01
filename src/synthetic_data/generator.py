from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
from datetime import date, datetime, time
from pathlib import Path

from .accounts import generate_accounts
from .common import write_csv
from .config import load_config, load_yaml
from .data_quality import inject_quality_issues
from .live_activity import LiveActivityTracker
from .monthly_metrics import generate_monthly_metrics
from .refunds import generate_refunds
from .reference import build_plans_catalog, build_regions
from .subscription_events import generate_subscription_events
from .subscriptions import generate_subscriptions
from .support_tickets import generate_support_tickets
from .validation import validate_dataset

LOGGER = logging.getLogger("synthetic_data")


def _configure_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_dir / "generator.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _dataset_hash(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def generate_all(config_path: Path, output_root: Path | None = None) -> dict[str, list[dict]]:
    config = load_config(config_path)
    project_root = Path(config["_project_root"])
    seed = int(config["seed"])
    rng = random.Random(seed)

    regions_cfg = load_yaml(project_root / "config" / "regions.yaml")
    plans_cfg = load_yaml(project_root / "config" / "plans.yaml")

    raw_dir = _resolve_project_path(project_root, config["output"]["raw_dir"])
    reference_dir = _resolve_project_path(project_root, config["output"]["reference_dir"])
    log_dir = _resolve_project_path(project_root, config["output"]["log_dir"])
    if output_root is not None:
        raw_dir = output_root / "raw"
        reference_dir = output_root / "reference"
        log_dir = output_root / "logs"
    _configure_logging(log_dir)

    start_date = date.fromisoformat(config["time_range"]["start"])
    end_date = date.fromisoformat(config["time_range"]["end"])
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max.replace(microsecond=0))
    sizes = config["dataset"]
    anomalies = config["anomalies"]
    domain_cfg = config.get("domain_rules", {})

    LOGGER.info("Generating SaaS analytics dataset with seed=%s", seed)
    anomaly_enabled = bool(anomalies.get("enabled", True))
    churned_ratio = float(anomalies["churned_account_ratio"]) if anomaly_enabled else 0.05

    accounts = generate_accounts(rng, int(sizes["accounts"]), regions_cfg, domain_cfg=domain_cfg)
    subscriptions, risk_factors = generate_subscriptions(
        rng, int(sizes["subscriptions"]), accounts, plans_cfg, churned_ratio, domain_cfg=domain_cfg,
    )
    metrics = generate_monthly_metrics(rng, subscriptions, risk_factors, start_date, end_date, domain_cfg=domain_cfg)
    events = generate_subscription_events(
        rng, int(sizes["subscription_events"]), subscriptions, risk_factors, start_dt, end_dt, domain_cfg=domain_cfg,
    )
    tickets = generate_support_tickets(
        rng, int(sizes["support_tickets"]), subscriptions, risk_factors, start_dt, end_dt, domain_cfg=domain_cfg,
    )
    refunds = generate_refunds(rng, int(sizes["refunds"]), tickets, domain_cfg=domain_cfg)

    clean_dataset = {
        "accounts": accounts,
        "subscriptions": subscriptions,
        "monthly_metrics": metrics,
        "subscription_events": events,
        "support_tickets": tickets,
        "refunds": refunds,
    }
    validate_dataset(clean_dataset)
    LOGGER.info("Clean dataset passed referential-integrity validation")

    quality = config["data_quality"]
    raw_dataset: dict[str, list[dict]] = {}
    for name, rows in clean_dataset.items():
        if quality.get("enabled", True):
            raw_dataset[name] = inject_quality_issues(
                rng, rows,
                float(quality["inconsistent_text_ratio"]),
                float(quality["missing_optional_ratio"]),
                float(quality["duplicate_ratio"]),
                domain_cfg=domain_cfg,
            )
        else:
            raw_dataset[name] = rows
        write_csv(raw_dir / f"{name}.csv", raw_dataset[name])
        LOGGER.info("Wrote %-28s rows=%-7s hash=%s", name, len(raw_dataset[name]), _dataset_hash(raw_dataset[name]))

    tracker = LiveActivityTracker(subscriptions, live_cfg=config.get("live_feed", {}), seed=seed)
    live_rows = tracker.get_activity()
    write_csv(raw_dir / "live_activity.csv", live_rows)
    LOGGER.info("Wrote live_activity.csv rows=%s", len(live_rows))

    reference_dataset = {
        "plans_catalog": build_plans_catalog(plans_cfg),
        "regions": build_regions(regions_cfg),
    }
    for name, rows in reference_dataset.items():
        write_csv(reference_dir / f"{name}.csv", rows)
        LOGGER.info("Wrote reference %-14s rows=%s", name, len(rows))

    manifest = {
        "seed": seed,
        "time_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "raw_row_counts": {name: len(rows) for name, rows in raw_dataset.items()},
        "reference_row_counts": {name: len(rows) for name, rows in reference_dataset.items()},
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOGGER.info("Generation complete")
    return raw_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic SaaS analytics data")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/generator.yaml"),
        help="Path to generator YAML configuration",
    )
    args = parser.parse_args()
    generate_all(args.config)


if __name__ == "__main__":
    main()
