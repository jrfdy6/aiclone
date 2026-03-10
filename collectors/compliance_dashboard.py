"""Builds the compliance dashboard payload by pulling metrics/logs from the live API."""
import os
from datetime import datetime
from typing import List

import requests

API_BASE = os.getenv("GOAT_API_BASE", "https://aiclone-production-32dc.up.railway.app")
ANALYTICS_PATH = "/api/analytics/compliance"
LOGS_PATH = "/api/system/logs?limit=20"


def fetch_json(path: str):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def format_dashboard(metrics: dict, logs: List[dict]) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"**Ops Compliance — {now}**"]
    lines.append(
        "- Approvals (24h): {approvals}\n- Prospects w/ email: {prospects}".format(
            approvals=metrics.get("approvals_last_24h", "n/a"),
            prospects=metrics.get("prospects_with_email", "n/a"),
        )
    )
    if logs:
        lines.append("\n**Recent System Events**")
        for entry in logs[:10]:
            ts = entry.get("timestamp", "?")
            msg = entry.get("message", "")
            lines.append(f"- `{ts}` {msg}")
    return "\n".join(lines)


def build_payload():
    metrics = fetch_json(ANALYTICS_PATH)
    raw_logs = fetch_json(LOGS_PATH)
    if isinstance(raw_logs, dict):
        logs = raw_logs.get("logs", [])
    elif isinstance(raw_logs, list):
        logs = raw_logs
    else:
        logs = []
    return format_dashboard(metrics, logs)


if __name__ == "__main__":
    print(build_payload())
