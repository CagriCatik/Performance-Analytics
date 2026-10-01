$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m src.synthetic_data.generator --config config/generator.yaml
python -m pytest -q
