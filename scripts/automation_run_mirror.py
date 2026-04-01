#!/usr/bin/env python3
"""Helpers for mirroring local automation runs into backend automation history."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


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


def mirror_runs(api_url: str, runs: list[dict[str, Any]]) -> bool:
    if not runs:
        return True
    payload = json.dumps({"runs": runs}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/automations/runs/mirror",
        data=payload,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
