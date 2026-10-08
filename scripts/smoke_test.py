"""Post-deployment smoke test for the FastAPI app (real Azure ML + Foundry).

Usage: python scripts/smoke_test.py https://<app>.azurewebsites.net [--wait 600]
Exits non-zero on the first failed check. No credentials are used or printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

INCIDENT = {
    "incident_id": "INC-SMOKE-001",
    "title": "Orders availability incident",
    "description": "Elevated latency and intermittent request failures.",
    "service": "orders",
    "region": "westus",
    "incident_type": "availability",
    "customer_impact": "broad",
    "detected_by": "on_call",
    "duration_minutes": 299,
    "affected_users": 396,
    "error_rate": 0.1735,
    "latency_ms": 310,
    "has_data_loss": False,
    "is_security_related": False,
}


def call(url: str, payload: dict | None = None, timeout: int = 120) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode(errors="replace")[:500]}
    except Exception as exc:  # network / timeout while the app is warming up
        return 0, {"error": str(exc)}


def fail(message: str) -> None:
    print(f"FAILED: {message}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--wait", type=int, default=600, help="seconds to wait for /health")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    deadline = time.monotonic() + args.wait
    while True:
        status, body = call(f"{base}/health", timeout=20)
        if status == 200:
            print(f"/health 200 {body}")
            break
        if time.monotonic() > deadline:
            fail(f"/health did not return 200 within {args.wait}s (last: {status} {body})")
        print(f"/health not ready ({status}); retrying in 15s")
        time.sleep(15)

    status, pred = call(f"{base}/predict", INCIDENT)
    if status != 200 or pred.get("model_backend") != "azureml" or not pred.get("trace_id"):
        fail(f"/predict {status} {pred}")
    print(f"/predict 200 severity={pred['severity']} backend={pred['model_backend']} trace_id={pred['trace_id']}")

    status, ana = call(f"{base}/analyze", {"incident": INCIDENT, "include_explanation": True})
    if status != 200 or not ana.get("trace_id") or not ana.get("analysis"):
        fail(f"/analyze {status} {ana}")
    print(f"/analyze 200 trace_id={ana['trace_id']}")

    status, metrics = call(f"{base}/metrics", timeout=20)
    ops = metrics.get("operations", {})
    if status != 200 or "azureml.predict" not in ops or "foundry.analyze" not in ops:
        fail(f"/metrics {status} {metrics}")
    print(f"/metrics 200 operations={list(ops)}")
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
