#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python -m src.synthetic_data.generator --config config/generator.yaml
python -m pytest -q
