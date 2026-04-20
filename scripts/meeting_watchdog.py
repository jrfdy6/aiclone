#!/usr/bin/env python3
"""Audit whether important standup lanes are producing fresh, non-trivial transcripts."""
from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
REPORT_ROOT = WORKSPACE_ROOT / "memory" / "reports"


@dataclass(frozen=True)
class RoomSpec:
    key: str
    label: str
    workspace_key: str
    max_age_hours: int
    expected: bool = True


ROOM_SPECS: tuple[RoomSpec, ...] = (
    RoomSpec("executive_ops", "Executive Standup", "shared_ops", 36),
    RoomSpec("operations", "Operations Standup", "shared_ops", 36),
    RoomSpec("weekly_review", "Weekly Review", "shared_ops", 8 * 24),
    RoomSpec("saturday_vision", "Saturday Vision Sync", "shared_ops", 8 * 24),
    RoomSpec("workspace_sync", "FEEZIE OS Standup", "feezie-os", 36),
    RoomSpec("workspace_sync", "Fusion Standup", "fusion-os", 72),
    RoomSpec("workspace_sync", "Easy Outfit App Standup", "easyoutfitapp", 72),
    RoomSpec("workspace_sync", "AI Swag Store Standup", "ai-swag-store", 72),
    RoomSpec("workspace_sync", "AGC Standup", "agc", 72),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _standup_kind(entry: dict[str, Any]) -> str:
    payload = entry.get("payload") or {}
    value = payload.get("standup_kind")
    if isinstance(value, str) and value.strip():
        return value.strip()
    workspace_key = entry.get("workspace_key")
    return workspace_key.strip() if isinstance(workspace_key, str) and workspace_key.strip() else "shared_ops"


def _discussion_rounds(entry: dict[str, Any]) -> list[dict[str, Any]]:
    payload = entry.get("payload") or {}
    rounds = payload.get("discussion")
    if isinstance(rounds, list):
        return [item for item in rounds if isinstance(item, dict)]
    return []


def _summary_text(entry: dict[str, Any]) -> str:
    payload = entry.get("payload") or {}
    summary = payload.get("summary")
    return str(summary).strip() if isinstance(summary, str) else ""


def _is_standup_prep(entry: dict[str, Any]) -> bool:
    payload = entry.get("payload") or {}
    source = str(entry.get("source") or "").strip()
    return source == "codex-chronicle-standup-prep" or bool((payload or {}).get("prep_json_path"))


def _prep_is_nontrivial(entry: dict[str, Any]) -> bool:
    payload = entry.get("payload") or {}
    agenda = payload.get("agenda")
    return bool(_summary_text(entry)) and isinstance(agenda, list) and len(agenda) > 0


def _match_entry(entry: dict[str, Any], spec: RoomSpec) -> bool:
    return _standup_kind(entry) == spec.key and str(entry.get("workspace_key") or "shared_ops") == spec.workspace_key


def _status_for(spec: RoomSpec, entry: dict[str, Any] | None, now: datetime) -> tuple[str, str]:
    if entry is None:
        if spec.expected:
            return "missing", "No transcript found for this required meeting lane."
        return "planned", "This lane is not required yet."
    created_at = _parse_datetime(entry.get("created_at"))
    rounds = len(_discussion_rounds(entry))
    summary = _summary_text(entry)
    is_prep = _is_standup_prep(entry)
    if is_prep:
        if not _prep_is_nontrivial(entry):
            return "thin", "Standup prep exists but does not include a non-trivial summary and agenda."
    elif rounds < 3 or not summary:
        return "thin", "Transcript exists but does not yet satisfy the three-round, non-trivial standard."
    if created_at is None:
        return "warning", "Transcript exists but timestamp data is incomplete."
    age = now - created_at
    if age > timedelta(hours=spec.max_age_hours):
        return "stale", f"Latest transcript is older than the {spec.max_age_hours}h freshness window."
    if is_prep:
        return "ok", "Standup prep is fresh enough and includes a non-trivial summary and agenda."
    return "ok", "Transcript is fresh enough and includes a real discussion."


def build_report(api_url: str, limit: int) -> dict[str, Any]:
    now = _now()
    standups = _fetch_json(f"{api_url.rstrip('/')}/api/standups/?limit={limit}")
    rows = standups if isinstance(standups, list) else []
    room_statuses: list[dict[str, Any]] = []
    missing = 0
    stale = 0
    thin = 0

    for spec in ROOM_SPECS:
        latest = next((entry for entry in rows if isinstance(entry, dict) and _match_entry(entry, spec)), None)
        status, reason = _status_for(spec, latest, now)
        if status == "missing":
            missing += 1
        elif status == "stale":
            stale += 1
        elif status == "thin":
            thin += 1
        room_statuses.append(
            {
                "key": spec.key,
                "label": spec.label,
                "workspace_key": spec.workspace_key,
                "expected": spec.expected,
                "status": status,
                "reason": reason,
                "max_age_hours": spec.max_age_hours,
                "latest_standup_id": latest.get("id") if isinstance(latest, dict) else None,
                "latest_created_at": latest.get("created_at") if isinstance(latest, dict) else None,
                "round_count": len(_discussion_rounds(latest)) if isinstance(latest, dict) else 0,
                "summary": _summary_text(latest) if isinstance(latest, dict) else "",
                "retrigger_recommended": status in {"missing", "stale", "thin"} and spec.expected,
            }
        )

    return {
        "generated_at": _iso(now),
        "source": "meeting_watchdog",
        "required_room_count": len([spec for spec in ROOM_SPECS if spec.expected]),
        "missing_count": missing,
        "stale_count": stale,
        "thin_count": thin,
        "room_statuses": room_statuses,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Meeting Watchdog Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Missing: `{report['missing_count']}`",
        f"- Stale: `{report['stale_count']}`",
        f"- Thin: `{report['thin_count']}`",
        "",
        "## Rooms",
    ]
    for room in report.get("room_statuses") or []:
        lines.append(f"- `{room['label']}` — `{room['status']}`")
        lines.append(f"  - Reason: {room['reason']}")
        if room.get("latest_created_at"):
            lines.append(f"  - Latest: `{room['latest_created_at']}`")
        if room.get("round_count"):
            lines.append(f"  - Rounds: `{room['round_count']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument(
        "--output-json",
        default=str(REPORT_ROOT / "meeting_watchdog_latest.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(REPORT_ROOT / "meeting_watchdog_latest.md"),
    )
    args = parser.parse_args()

    report = build_report(args.api_url, args.limit)
    _write_json(Path(args.output_json).expanduser(), report)
    _write_markdown(Path(args.output_md).expanduser(), _markdown_report(report))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
