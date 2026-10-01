from __future__ import annotations

import argparse
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish generated CSV/JSON data to Azure Blob Storage.")
    parser.add_argument("--account-url", default=os.getenv("POWERBI_BLOB_ACCOUNT_URL"))
    parser.add_argument("--container", default=os.getenv("POWERBI_BLOB_CONTAINER"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.account_url or not args.container:
        raise SystemExit("Set POWERBI_BLOB_ACCOUNT_URL and POWERBI_BLOB_CONTAINER.")

    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise SystemExit("Install requirements-deploy.txt before publishing data.") from exc

    service = BlobServiceClient(args.account_url, credential=DefaultAzureCredential())
    container = service.get_container_client(args.container)
    for folder in ("raw", "reference"):
        for path in sorted((ROOT / "data" / folder).glob("*")):
            if path.suffix.lower() not in {".csv", ".json"}:
                continue
            blob_name = f"{folder}/{path.name}"
            with path.open("rb") as source:
                container.upload_blob(blob_name, source, overwrite=True)
            print(f"Uploaded {blob_name}")


if __name__ == "__main__":
    main()
