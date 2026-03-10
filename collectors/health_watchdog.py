"""5-minute Railway health watchdog."""
import os
from datetime import datetime

import requests

API_BASE = os.getenv("GOAT_API_BASE", "https://aiclone-production-32dc.up.railway.app")
HEALTH_PATH = "/health"
LOG_PATH = "/api/system/logs?limit=5"


def utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def fetch(path: str):
    resp = requests.get(f"{API_BASE}{path}", timeout=8)
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        return resp.json()
    return resp.text


def check_health() -> dict:
    try:
        payload = fetch(HEALTH_PATH)
        status = payload.get("status") if isinstance(payload, dict) else "unknown"
        ok = status in {"ok", "healthy"}
        return {
            "ok": ok,
            "raw": payload,
            "checked_at": utc_timestamp(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "checked_at": utc_timestamp(),
        }


def build_alert(status: dict) -> str:
    if status.get("ok"):
        return f"✅ Railway health good @ {status['checked_at']}"
    latest_logs = []
    try:
        raw = fetch(LOG_PATH)
        if isinstance(raw, dict):
            latest_logs = raw.get("logs", [])
        elif isinstance(raw, list):
            latest_logs = raw
    except Exception:
        pass
    lines = ["🚨 Railway health check FAILED", f"Checked: {status['checked_at']}"]
    if status.get("error"):
        lines.append(f"Error: {status['error']}")
    else:
        lines.append(f"Payload: {status.get('raw')}")
    if latest_logs:
        lines.append("\nRecent logs:")
        for entry in latest_logs:
            lines.append(f"- `{entry.get('timestamp','?')}` {entry.get('message','')}")
    return "\n".join(lines)


if __name__ == "__main__":
    state = check_health()
    print(build_alert(state))
