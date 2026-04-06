#!/usr/bin/env python3
"""Compatibility helpers for the legacy memory workspace registry.

The canonical workspace truth now lives in
`backend/app/services/workspace_registry_service.py`, but a few runner and prep
scripts still consume `memory/workspace_registry.json`.

This module keeps the old file shape available while ensuring it is derived from
the canonical registry instead of drifting independently.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
LEGACY_REGISTRY_PATH = MEMORY_ROOT / "workspace_registry.json"
_SOURCE_PATH = "backend/app/services/workspace_registry_service.py"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_backend_path() -> None:
    backend = str(BACKEND_ROOT)
    if backend not in sys.path:
        sys.path.insert(0, backend)


def _canonical_registry_payload(*, include_executive: bool) -> dict[str, Any]:
    _ensure_backend_path()
    from app.services.workspace_registry_service import workspace_registry_payload  # type: ignore

    payload = workspace_registry_payload(include_executive=include_executive)
    if not isinstance(payload, dict):
        raise RuntimeError("Canonical workspace registry payload was not a dictionary.")
    return payload


def _canonical_root_path(workspace_key: str) -> str:
    _ensure_backend_path()
    from app.services.workspace_registry_service import workspace_root_path  # type: ignore

    return str(workspace_root_path(workspace_key, repo_root=WORKSPACE_ROOT))


def _legacy_entry_from_canonical(entry: dict[str, Any]) -> dict[str, Any]:
    key = str(entry.get("key") or "").strip()
    if not key:
        raise RuntimeError("Workspace registry entry is missing a key.")

    display_name = str(entry.get("display_name") or key)
    description = str(entry.get("description") or "").strip()
    operator_name = entry.get("operator_name")
    workspace_agent = entry.get("workspace_agent")

    legacy: dict[str, Any] = {
        "workspace_key": key,
        "display_name": display_name,
        "filesystem_path": _canonical_root_path(key),
        "status": str(entry.get("status") or "planned"),
        "manager_agent": str(entry.get("manager_agent") or "Jean-Claude"),
        "workspace_agent": str(workspace_agent) if isinstance(workspace_agent, str) else None,
        "execution_mode": str(entry.get("execution_mode") or "delegated"),
        "notes": description,
        "kind": str(entry.get("kind") or "workspace"),
        "workspace_root": str(entry.get("workspace_root") or key),
        "operator_name": str(operator_name) if isinstance(operator_name, str) else None,
        "target_agent": str(entry.get("target_agent") or ""),
        "brief_heading": str(entry.get("brief_heading") or display_name),
        "priority_order": int(entry.get("priority_order") or 0),
        "route": entry.get("route"),
        "portfolio_visible": bool(entry.get("portfolio_visible")),
    }
    if key == "feezie-os":
        legacy["legacy_name"] = "LinkedIn OS"
        legacy["future_name"] = "FEEZIE OS"
    return legacy


def build_legacy_workspace_registry_payload(*, include_executive: bool = False) -> dict[str, Any]:
    canonical = _canonical_registry_payload(include_executive=include_executive)
    workspaces = canonical.get("workspaces") or []
    if not isinstance(workspaces, list):
        raise RuntimeError("Canonical workspace registry did not contain a workspace list.")
    return {
        "version": 2,
        "generated_at": str(canonical.get("generated_at") or _now_iso()),
        "source": _SOURCE_PATH,
        "include_executive": include_executive,
        "workspaces": [
            _legacy_entry_from_canonical(entry)
            for entry in workspaces
            if isinstance(entry, dict)
        ],
    }


def write_legacy_workspace_registry(
    path: Path = LEGACY_REGISTRY_PATH,
    *,
    include_executive: bool = False,
) -> dict[str, Any]:
    payload = build_legacy_workspace_registry_payload(include_executive=include_executive)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_legacy_workspace_registry_payload(
    path: Path = LEGACY_REGISTRY_PATH,
    *,
    include_executive: bool = False,
    ensure_synced: bool = True,
) -> dict[str, Any]:
    if ensure_synced:
        try:
            return write_legacy_workspace_registry(path, include_executive=include_executive)
        except Exception:
            pass

    if not path.exists():
        return {"version": 2, "generated_at": _now_iso(), "source": _SOURCE_PATH, "workspaces": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {"version": 2, "generated_at": _now_iso(), "source": _SOURCE_PATH, "workspaces": []}


def load_legacy_workspace_registry_map(
    path: Path = LEGACY_REGISTRY_PATH,
    *,
    include_executive: bool = False,
    ensure_synced: bool = True,
) -> dict[str, dict[str, Any]]:
    payload = load_legacy_workspace_registry_payload(
        path,
        include_executive=include_executive,
        ensure_synced=ensure_synced,
    )
    items = payload.get("workspaces") or []
    registry: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        return registry
    for item in items:
        if isinstance(item, dict) and item.get("workspace_key"):
            registry[str(item["workspace_key"])] = dict(item)
    return registry


if __name__ == "__main__":
    write_legacy_workspace_registry()
