from __future__ import annotations

import csv
from pathlib import Path

from src.synthetic_data.generator import generate_all


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_generation_is_reproducible(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    config = root / "config" / "generator.yaml"
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_all(config, first)
    generate_all(config, second)
    assert (first / "raw" / "subscriptions.csv").read_bytes() == (second / "raw" / "subscriptions.csv").read_bytes()
    assert (first / "raw" / "support_tickets.csv").read_bytes() == (second / "raw" / "support_tickets.csv").read_bytes()


def test_generator_creates_expected_files(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    generate_all(root / "config" / "generator.yaml", tmp_path)
    expected = {
        "accounts.csv",
        "subscriptions.csv",
        "monthly_metrics.csv",
        "subscription_events.csv",
        "support_tickets.csv",
        "refunds.csv",
        "live_activity.csv",
        "manifest.json",
    }
    assert expected.issubset({path.name for path in (tmp_path / "raw").iterdir()})


def test_raw_data_contains_deliberate_duplicates(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    generate_all(root / "config" / "generator.yaml", tmp_path)
    rows = _read(tmp_path / "raw" / "support_tickets.csv")
    ids = [row["ticket_id"] for row in rows]
    assert len(ids) > len(set(ids))
