$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m src.synthetic_data.generator --config config/generator.yaml
python -m pytest -q
python scripts/build_powerbi_project.py

if ($env:FABRIC_WORKSPACE_ID) {
    python scripts/deploy_powerbi.py --workspace-id $env:FABRIC_WORKSPACE_ID
} else {
    Write-Host "Local PBIP generated. Set FABRIC_WORKSPACE_ID and cloud-source variables to deploy automatically."
}
