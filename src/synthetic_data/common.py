from __future__ import annotations

import csv
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


def weighted_choice(rng: random.Random, items: Sequence[T], weights: Sequence[float]) -> T:
    return rng.choices(list(items), weights=list(weights), k=1)[0]


def random_date(rng: random.Random, start: date, end: date) -> date:
    if end < start:
        raise ValueError("end must be >= start")
    return start + timedelta(days=rng.randint(0, (end - start).days))


def random_datetime(rng: random.Random, start: datetime, end: datetime) -> datetime:
    if end < start:
        raise ValueError("end must be >= start")
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, max(seconds, 0)))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
