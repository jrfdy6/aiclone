from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = WORKSPACE_ROOT / "memory" / "runtime" / "pm_review_hygiene_audit.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries


def _summarize(entries: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "runs": len(entries),
        "processed_count": sum(int(entry.get("processed_count") or 0) for entry in entries),
        "advanced_count": sum(int(entry.get("advanced_count") or 0) for entry in entries),
        "returned_count": sum(int(entry.get("returned_count") or 0) for entry in entries),
        "escalated_count": sum(int(entry.get("escalated_count") or 0) for entry in entries),
        "closed_count": sum(int(entry.get("closed_count") or 0) for entry in entries),
        "continued_count": sum(int(entry.get("continued_count") or 0) for entry in entries),
    }


def record_review_hygiene_audit(result: dict[str, Any]) -> dict[str, Any] | None:
    processed = result.get("processed") or []
    if not isinstance(processed, list) or not processed:
        return None
    entry = {
        "run_id": str(uuid4()),
        "processed_at": _now_iso(),
        "processed_count": int(result.get("processed_count") or 0),
        "advanced_count": int(result.get("advanced_count") or 0),
        "returned_count": int(result.get("returned_count") or 0),
        "escalated_count": int(result.get("escalated_count") or 0),
        "closed_count": int(result.get("closed_count") or 0),
        "continued_count": int(result.get("continued_count") or 0),
        "processed": processed[:25],
    }
    _append_jsonl(AUDIT_PATH, entry)
    return entry


def list_review_hygiene_audit(*, limit: int = 12, hours: int = 24) -> dict[str, Any]:
    entries = _read_jsonl(AUDIT_PATH)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, hours))
    recent_window: list[dict[str, Any]] = []
    for entry in entries:
        timestamp = _parse_timestamp(entry.get("processed_at"))
        if timestamp is not None and timestamp >= cutoff:
            recent_window.append(entry)

    latest_first = list(reversed(entries[-max(0, limit) :])) if limit > 0 else []
    return {
        "path": str(AUDIT_PATH),
        "window_hours": max(1, hours),
        "summary": _summarize(recent_window),
        "entries": latest_first,
    }
