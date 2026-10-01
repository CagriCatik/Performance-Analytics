from __future__ import annotations

import random

from src.synthetic_data.data_quality import inject_quality_issues


def test_quality_injection_does_not_modify_input() -> None:
    source = [{"id": "1", "country": "Germany", "base_location": "Stuttgart"} for _ in range(20)]
    original = [row.copy() for row in source]
    dirty = inject_quality_issues(random.Random(1), source, 0.2, 0.2, 0.2)
    assert source == original
    assert len(dirty) > len(source)
