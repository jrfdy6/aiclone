import os
from datetime import datetime

import requests

API_BASE = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")


def fetch_json(path: str):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def format_dashboard(metrics: dict, logs: list[dict]) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    parts = [f"**Compliance Dashboard — {now}**"]
    parts.append(
        "- Approvals (24h): {approvals_last_24h}\n- Prospects w/ email: {prospects_with_email}".format(
            **metrics
        )
    )
    if logs:
        parts.append("**Recent Events**")
        for log in logs[:5]:
            ts = log.get("timestamp")
            component = log.get("component")
            message = log.get("message")
            parts.append(f"• `{component}` — {message} ({ts})")
    else:
        parts.append("No recent system log entries.")
    return "\n".join(parts)


def main():
    metrics = fetch_json("/api/analytics/compliance")
    logs = fetch_json("/api/system/logs?limit=20")
    dashboard = format_dashboard(metrics, logs)
    print(dashboard)


if __name__ == "__main__":
    main()
