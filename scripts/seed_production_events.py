"""Bootstrap Blob Storage with synthetic incidents for a demo environment."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/synthetic_incidents.csv"))
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--container", default="production")
    parser.add_argument("--prefix", default="events")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    rows = list(csv.DictReader(args.source.open("r", newline="", encoding="utf-8")))
    if not rows:
        raise SystemExit("Source dataset is empty.")

    client = BlobServiceClient(
        account_url=f"https://{args.account_name}.blob.core.windows.net",
        credential=DefaultAzureCredential(exclude_interactive_browser_credential=False),
    )
    container = client.get_container_client(args.container)

    base_time = datetime.now(timezone.utc) - timedelta(minutes=len(rows))
    for index, row in enumerate(rows):
        observed_at = base_time + timedelta(minutes=index)
        payload = {
            **row,
            "recorded_at": observed_at.isoformat(),
            "predicted_severity": row["severity"],
            "observed_severity": row["severity"],
            "model_backend": "seed",
            "model_version": "1",
            "trace_id": None,
        }
        blob_name = (
            f"{args.prefix.strip('/')}/{observed_at:%Y/%m/%d}/"
            f"seed-{row['incident_id']}.json"
        )
        container.upload_blob(
            name=blob_name,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            overwrite=args.overwrite,
            content_type="application/json",
        )

    print(f"Seeded {len(rows)} production event blobs into {args.account_name}/{args.container}.")


if __name__ == "__main__":
    main()
