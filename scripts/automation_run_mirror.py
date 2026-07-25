#!/usr/bin/env python3
"""Helpers for mirroring local automation runs into backend automation history."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_paths import AUTOMATION_RUNS_ROOT
from runtime_http import control_plane_headers


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_run_payload(
    *,
    run_id: str,
    automation_id: str,
    automation_name: str,
    status: str,
    source: str = "local_launchd_registry",
    runtime: str = "launchd",
    delivered: bool | None = None,
    delivery_channel: str | None = None,
    delivery_target: str | None = None,
    run_at: datetime | str | None = None,
    finished_at: datetime | str | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
    owner_agent: str | None = None,
    session_target: str | None = None,
    scope: str = "shared_ops",
    workspace_key: str | None = None,
    action_required: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "automation_id": automation_id,
        "automation_name": automation_name,
        "source": source,
        "runtime": runtime,
        "status": status,
        "delivered": delivered,
        "delivery_channel": delivery_channel,
        "delivery_target": delivery_target,
        "run_at": _iso(run_at),
        "finished_at": _iso(finished_at),
        "duration_ms": duration_ms,
        "error": error,
        "owner_agent": owner_agent,
        "session_target": session_target,
        "scope": scope,
        "workspace_key": workspace_key,
        "action_required": action_required,
        "metadata": metadata or {},
    }


def append_local_runs(runs: list[dict[str, Any]], path: Path | None = None) -> Path:
    """Persist run truth locally before attempting any network mirror."""

    target = path or (AUTOMATION_RUNS_ROOT / "all.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with target.open("a", encoding="utf-8") as handle:
        for run in runs:
            payload = dict(run)
            metadata = dict(payload.get("metadata") or {})
            metadata.setdefault("locally_recorded_at", recorded_at)
            payload["metadata"] = metadata
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def read_local_runs(path: Path | None = None) -> list[dict[str, Any]]:
    """Read valid local run-ledger rows without consulting Railway."""

    target = path or (AUTOMATION_RUNS_ROOT / "all.jsonl")
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def latest_successful_run_ms(automation_id: str, path: Path | None = None) -> int | None:
    """Return the latest successful local run timestamp in Unix milliseconds."""

    latest: int | None = None
    for row in read_local_runs(path):
        if str(row.get("automation_id") or "") != automation_id:
            continue
        if str(row.get("status") or "").lower() not in {"ok", "success", "completed"}:
            continue
        raw_timestamp = row.get("finished_at") or row.get("run_at")
        if not isinstance(raw_timestamp, str):
            continue
        try:
            timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp_ms = int(timestamp.timestamp() * 1000)
        latest = timestamp_ms if latest is None else max(latest, timestamp_ms)
    return latest


def mirror_runs(api_url: str, runs: list[dict[str, Any]]) -> bool:
    if not runs:
        return True
    append_local_runs(runs)
    payload = json.dumps({"runs": runs}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/automations/runs/mirror",
        data=payload,
        method="POST",
        headers=control_plane_headers({"Accept": "application/json", "Content-Type": "application/json"}),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
        result = json.loads(raw) if raw.strip() else {}
        return bool(
            isinstance(result, dict)
            and result.get("success") is True
            and int(result.get("count") or 0) >= len(runs)
        )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False
