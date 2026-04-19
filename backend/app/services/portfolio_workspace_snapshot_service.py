from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import pm_card_service, standup_service
from app.services.workspace_registry_service import (
    canonicalize_workspace_key,
    workspace_registry_entries,
    workspace_root_path,
    workspace_root_slug,
)
from app.services.workspace_snapshot_store import list_snapshot_payloads


PACK_FILES = ("CHARTER.md", "IDENTITY.md", "SOUL.md", "USER.md", "AGENTS.md")
LOCAL_CONTRACT_FILES = (
    "docs/operating_model.md",
    "docs/standup_contract.md",
    "docs/weekly_workflow.md",
)
ACTIVE_PM_STATUSES = {"todo", "queued", "running", "in_progress", "review", "blocked", "failed"}
ATTENTION_PM_STATUSES = {"review", "blocked", "failed"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _first_meaningful_line(path: Path, *, limit: int = 220) -> str:
    if not path.exists() or not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("#"):
            if cleaned.startswith("-"):
                cleaned = cleaned[1:].strip()
            return cleaned[:limit]
    return ""


def _tail_text(path: Path, *, max_chars: int = 1000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()[-max_chars:]


def _latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    matches = sorted(path for path in directory.glob(pattern) if path.is_file())
    if not matches:
        return None
    non_readme = [path for path in matches if path.stem.lower() != "readme"]
    return non_readme[-1] if non_readme else matches[-1]


def _path_payload(path: Path, root: Path, *, include_tail: bool = False) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    payload: dict[str, Any] = {
        "path": _relative_path(path, root),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "snippet": _first_meaningful_line(path),
    }
    if include_tail:
        payload["tail"] = _tail_text(path)
    return payload


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _workspace_snapshot_keys(workspace_key: str, root_slug: str) -> list[str]:
    keys = [workspace_key, root_slug]
    if workspace_key == "feezie-os":
        keys.extend(["linkedin-os", "linkedin-content-os"])
    return list(dict.fromkeys(key for key in keys if key))


def _safe_pm_cards(workspace_key: str, *, limit: int) -> list[dict[str, Any]]:
    cards: list[Any] = []
    seen: set[str] = set()
    for key in _workspace_snapshot_keys(workspace_key, workspace_root_slug(workspace_key)):
        try:
            cards.extend(pm_card_service.list_cards(workspace_key=key, limit=limit))
        except Exception:
            continue
    compacted: list[dict[str, Any]] = []
    for card in cards:
        card_id = str(getattr(card, "id", "") or "")
        if not card_id or card_id in seen:
            continue
        seen.add(card_id)
        status = _clean_text(getattr(card, "status", "")).lower() or "todo"
        payload = getattr(card, "payload", {}) or {}
        compacted.append(
            {
                "id": card_id,
                "title": getattr(card, "title", ""),
                "status": status,
                "owner": getattr(card, "owner", None),
                "source": getattr(card, "source", None),
                "workspace_key": payload.get("workspace_key") or payload.get("workspace") or workspace_key,
                "updated_at": getattr(card, "updated_at", None).isoformat() if getattr(card, "updated_at", None) else None,
            }
        )
    return compacted[:limit]


def _safe_standups(workspace_key: str, *, limit: int) -> list[dict[str, Any]]:
    rows: list[Any] = []
    seen: set[str] = set()
    for key in _workspace_snapshot_keys(workspace_key, workspace_root_slug(workspace_key)):
        try:
            rows.extend(standup_service.list_standups(workspace_key=key, limit=limit))
        except Exception:
            continue
    compacted: list[dict[str, Any]] = []
    for standup in rows:
        standup_id = str(getattr(standup, "id", "") or "")
        if not standup_id or standup_id in seen:
            continue
        seen.add(standup_id)
        payload = getattr(standup, "payload", {}) or {}
        compacted.append(
            {
                "id": standup_id,
                "status": getattr(standup, "status", None),
                "workspace_key": getattr(standup, "workspace_key", workspace_key),
                "standup_kind": payload.get("standup_kind"),
                "summary": payload.get("summary"),
                "blockers": list(getattr(standup, "blockers", []) or [])[:4],
                "needs": list(getattr(standup, "needs", []) or [])[:4],
                "created_at": getattr(standup, "created_at", None).isoformat() if getattr(standup, "created_at", None) else None,
            }
        )
    return compacted[:limit]


def _safe_snapshot_types(workspace_key: str, root_slug: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key in _workspace_snapshot_keys(workspace_key, root_slug):
        try:
            payloads = list_snapshot_payloads(key)
        except Exception:
            payloads = {}
        if payloads:
            result[key] = sorted(payloads)
    return result


def _pack_status(root: Path, repo_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for filename in PACK_FILES:
        path = root / filename
        items.append(
            {
                "name": filename,
                "exists": path.exists(),
                "path": _relative_path(path, repo_root),
                "snippet": _first_meaningful_line(path),
            }
        )
    return items


def _local_contracts(root: Path, repo_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for relative in LOCAL_CONTRACT_FILES:
        path = root / relative
        payload = _path_payload(path, repo_root)
        if payload:
            payload["name"] = Path(relative).name
            items.append(payload)
    return items


def _build_workspace_summary(entry: dict[str, Any], *, pm_limit: int, standup_limit: int) -> dict[str, Any]:
    workspace_key = canonicalize_workspace_key(str(entry.get("key") or ""), default="shared_ops")
    root_slug = str(entry.get("workspace_root") or workspace_root_slug(workspace_key))
    root = workspace_root_path(workspace_key)
    repo_root = root.parents[1] if len(root.parents) > 1 else root
    latest_briefing = _latest_file(root / "briefings", "*.md")
    latest_dispatch = _latest_file(root / "dispatch", "*.json")
    latest_analytics = _latest_file(root / "analytics", "*.md")
    latest_execution_log = root / "memory" / "execution_log.md"
    active_cards = [
        card for card in _safe_pm_cards(workspace_key, limit=pm_limit) if str(card.get("status") or "").lower() in ACTIVE_PM_STATUSES
    ]
    latest_standups = _safe_standups(workspace_key, limit=standup_limit)
    blocker_count = sum(len(row.get("blockers") or []) for row in latest_standups)
    attention_cards = [card for card in active_cards if str(card.get("status") or "").lower() in ATTENTION_PM_STATUSES]
    source_paths = [
        value
        for value in [
            _relative_path(latest_briefing, repo_root) if latest_briefing else None,
            _relative_path(latest_dispatch, repo_root) if latest_dispatch else None,
            _relative_path(latest_analytics, repo_root) if latest_analytics else None,
            _relative_path(latest_execution_log, repo_root) if latest_execution_log.exists() else None,
        ]
        if value
    ]

    return {
        "workspace_key": workspace_key,
        "display_name": entry.get("display_name") or workspace_key,
        "short_label": entry.get("short_label") or entry.get("display_name") or workspace_key,
        "kind": entry.get("kind") or "workspace",
        "status": entry.get("status") or "planned",
        "portfolio_visible": bool(entry.get("portfolio_visible")),
        "priority_order": int(entry.get("priority_order") or 999),
        "workspace_root": _relative_path(root, repo_root),
        "description": entry.get("description") or "",
        "manager_agent": entry.get("manager_agent"),
        "target_agent": entry.get("target_agent"),
        "workspace_agent": entry.get("workspace_agent"),
        "execution_mode": entry.get("execution_mode"),
        "default_standup_kind": entry.get("default_standup_kind"),
        "workspace_sync_participants": entry.get("workspace_sync_participants") or [],
        "pack_status": _pack_status(root, repo_root),
        "local_contracts": _local_contracts(root, repo_root),
        "latest_briefing": _path_payload(latest_briefing, repo_root, include_tail=True) if latest_briefing else None,
        "latest_dispatch": _path_payload(latest_dispatch, repo_root) if latest_dispatch else None,
        "latest_analytics": _path_payload(latest_analytics, repo_root, include_tail=True) if latest_analytics else None,
        "execution_log": _path_payload(latest_execution_log, repo_root, include_tail=True) if latest_execution_log.exists() else None,
        "active_pm_cards": active_cards[:pm_limit],
        "latest_standups": latest_standups[:standup_limit],
        "persisted_snapshot_types": _safe_snapshot_types(workspace_key, root_slug),
        "counts": {
            "pack_files_present": sum(1 for item in _pack_status(root, repo_root) if item.get("exists")),
            "local_contracts": len(_local_contracts(root, repo_root)),
            "active_pm_cards": len(active_cards),
            "attention_pm_cards": len(attention_cards),
            "latest_standups": len(latest_standups),
            "standup_blockers": blocker_count,
        },
        "needs_brain_attention": bool(attention_cards or blocker_count),
        "source_paths": source_paths,
    }


def build_portfolio_workspace_snapshot(*, pm_limit: int = 8, standup_limit: int = 5) -> dict[str, Any]:
    workspaces = [
        _build_workspace_summary(entry, pm_limit=pm_limit, standup_limit=standup_limit)
        for entry in workspace_registry_entries()
    ]
    visible_workspaces = [workspace for workspace in workspaces if workspace.get("portfolio_visible") or workspace.get("kind") == "executive"]
    return {
        "generated_at": _now_iso(),
        "schema_version": "portfolio_workspace_snapshot/v1",
        "source": "portfolio_workspace_snapshot_service",
        "workspaces": sorted(visible_workspaces, key=lambda item: (int(item.get("priority_order") or 999), str(item.get("workspace_key") or ""))),
        "counts": {
            "workspaces": len(visible_workspaces),
            "needs_brain_attention": sum(1 for workspace in visible_workspaces if workspace.get("needs_brain_attention")),
            "active_pm_cards": sum(int((workspace.get("counts") or {}).get("active_pm_cards") or 0) for workspace in visible_workspaces),
            "standup_blockers": sum(int((workspace.get("counts") or {}).get("standup_blockers") or 0) for workspace in visible_workspaces),
        },
    }
