from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_config(config_path: Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    config["_project_root"] = str(config_path.resolve().parent.parent)
    return config
