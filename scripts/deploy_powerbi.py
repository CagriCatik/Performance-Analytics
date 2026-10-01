from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "PerformanceAnalytics"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build, deploy and refresh the Performance Analytics Power BI project.")
    parser.add_argument("--workspace-id", default=os.getenv("FABRIC_WORKSPACE_ID"))
    parser.add_argument("--environment", default=os.getenv("DEPLOY_ENVIRONMENT", "prod"))
    parser.add_argument("--source-root", default=os.getenv("POWERBI_DATA_ROOT_URL"))
    parser.add_argument("--skip-data-upload", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true")
    return parser.parse_args()


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def get_credential():
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise SystemExit("Install requirements-deploy.txt before deployment.") from exc
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def fabric_headers(credential, scope: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {credential.get_token(scope).token}", "Content-Type": "application/json"}


def semantic_model_id(workspace_id: str, credential) -> str:
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items?type=SemanticModel"
    response = requests.get(url, headers=fabric_headers(credential, "https://api.fabric.microsoft.com/.default"), timeout=60)
    response.raise_for_status()
    matches = [item for item in response.json().get("value", []) if item.get("displayName") == MODEL_NAME]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {MODEL_NAME} semantic model, found {len(matches)}")
    return matches[0]["id"]


def refresh_and_wait(workspace_id: str, dataset_id: str, credential) -> None:
    headers = fabric_headers(credential, "https://analysis.windows.net/powerbi/api/.default")
    base = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
    # Service-principal refresh calls don't support notifyOption.
    response = requests.post(base, headers=headers, timeout=60)
    response.raise_for_status()
    print(f"Refresh submitted for semantic model {dataset_id}")

    deadline = time.monotonic() + 3600
    while time.monotonic() < deadline:
        status_response = requests.get(f"{base}?$top=1", headers=headers, timeout=60)
        status_response.raise_for_status()
        refreshes = status_response.json().get("value", [])
        if refreshes:
            status = refreshes[0].get("status")
            print(f"Refresh status: {status}")
            if status == "Completed":
                return
            if status in {"Failed", "Disabled", "Cancelled"}:
                raise RuntimeError(f"Semantic-model refresh ended with status {status}: {refreshes[0]}")
        time.sleep(15)
    raise TimeoutError("Semantic-model refresh did not finish within one hour")


def main() -> None:
    args = parse_args()
    if not args.workspace_id:
        raise SystemExit("Set FABRIC_WORKSPACE_ID or pass --workspace-id.")
    if not args.source_root:
        raise SystemExit("Set POWERBI_DATA_ROOT_URL or pass --source-root (Azure Blob container URL).")

    run([sys.executable, "-m", "src.synthetic_data.generator", "--config", "config/generator.yaml"])
    run([sys.executable, "-m", "pytest", "-q"])
    if not args.skip_data_upload:
        run([sys.executable, "scripts/publish_data.py"])
    run([sys.executable, "scripts/build_powerbi_project.py", "--source-kind", "azure-blob", "--source-root", args.source_root])

    try:
        from fabric_cicd import FabricWorkspace, publish_all_items
    except ImportError as exc:
        raise SystemExit("Install requirements-deploy.txt before deployment.") from exc

    credential = get_credential()
    workspace = FabricWorkspace(
        workspace_id=args.workspace_id,
        environment=args.environment,
        repository_directory=str(ROOT / "powerbi"),
        item_type_in_scope=["SemanticModel", "Report"],
        token_credential=credential,
    )
    publish_all_items(workspace)
    print(f"Deployed {MODEL_NAME} semantic model and report")

    if not args.skip_refresh:
        refresh_and_wait(args.workspace_id, semantic_model_id(args.workspace_id, credential), credential)


if __name__ == "__main__":
    main()
