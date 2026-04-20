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


def _workspace_root_candidates(workspace_key: str, root_slug: str) -> list[Path]:
    current = Path(__file__).resolve()
    candidates = [workspace_root_path(workspace_key)]
    bases = [*current.parents, Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/app/backend")]
    for base in bases:
        if not root_slug:
            continue
        candidates.append(base / "workspaces" / root_slug)
        candidates.append(base / "backend" / "workspaces" / root_slug)

    ordered: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.as_posix()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def _resolve_workspace_root(workspace_key: str, root_slug: str) -> Path:
    for candidate in _workspace_root_candidates(workspace_key, root_slug):
        if candidate.exists():
            return candidate
    return workspace_root_path(workspace_key)


def _repo_root_for_workspace_root(root: Path) -> Path:
    if root.parent.name == "workspaces":
        return root.parent.parent
    return root.parents[1] if len(root.parents) > 1 else root


def _is_workspace_root_missing_blocker(value: Any) -> bool:
    text = _clean_text(value).lower()
    return bool(text and "has no local artifact root yet" in text)


def _is_non_actionable_status_surface(value: Any) -> bool:
    text = _clean_text(value).lower()
    if not text:
        return True
    if "why does it say needs brain" in text:
        return True
    if "no active blockers reported" in text:
        return True
    if "recent standups" in text and "0 blockers" in text and "no open pm cards" in text:
        return True
    if "open pm lane" in text and "no open pm cards" in text and "0 blockers" in text:
        return True
    if text.startswith("fallback watchdog found") and "last execution result" in text:
        return True
    if text.startswith("active blockers ") and ("automation drift remains" in text or "fallback watchdog" in text):
        return True
    return False


def _filter_resolved_workspace_root_blockers(blockers: list[Any], *, root_exists: bool) -> list[str]:
    cleaned = [_clean_text(item) for item in blockers if _clean_text(item) and not _is_non_actionable_status_surface(item)]
    if not root_exists:
        return cleaned[:4]
    return [item for item in cleaned if not _is_workspace_root_missing_blocker(item)][:4]


def _is_owner_review_pm_card(card: Any) -> bool:
    payload = getattr(card, "payload", {}) or {}
    if not isinstance(payload, dict):
        payload = {}
    owner_review = payload.get("owner_review") if isinstance(payload, dict) else {}
    if str(getattr(card, "source", "") or "").strip() == "openclaw:workspace-owner-review":
        return True
    if str(getattr(card, "link_type", "") or "").strip() == "owner_review":
        return True
    if isinstance(owner_review, dict) and str(owner_review.get("sync_state") or "").strip() == "pending_owner_review":
        return True
    if str(payload.get("trigger_origin") or "").strip() == "owner_review":
        return True
    return str(getattr(card, "title", "") or "").strip().lower().startswith("owner review -")


def _pm_attention_kind(card: Any) -> str | None:
    status = _clean_text(getattr(card, "status", "")).lower() or "todo"
    if status not in ATTENTION_PM_STATUSES:
        return None
    if _is_owner_review_pm_card(card):
        return "owner_review"
    if status == "blocked":
        return "blocked"
    if status == "failed":
        return "failed"
    return "review"


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
        payload_workspace_key = canonicalize_workspace_key(
            payload.get("workspace_key") or payload.get("workspace") or workspace_key,
            default=workspace_key,
        )
        attention_kind = _pm_attention_kind(card)
        compacted.append(
            {
                "id": card_id,
                "title": getattr(card, "title", ""),
                "status": status,
                "owner": getattr(card, "owner", None),
                "source": getattr(card, "source", None),
                "link_type": getattr(card, "link_type", None),
                "attention_kind": attention_kind,
                "workspace_key": payload_workspace_key,
                "updated_at": getattr(card, "updated_at", None).isoformat() if getattr(card, "updated_at", None) else None,
            }
        )
    return compacted[:limit]


def _safe_standups(workspace_key: str, *, limit: int, root_exists: bool = False) -> list[dict[str, Any]]:
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
        blockers = _filter_resolved_workspace_root_blockers(
            list(getattr(standup, "blockers", []) or []),
            root_exists=root_exists,
        )
        compacted.append(
            {
                "id": standup_id,
                "status": getattr(standup, "status", None),
                "workspace_key": canonicalize_workspace_key(getattr(standup, "workspace_key", workspace_key), default=workspace_key),
                "standup_kind": payload.get("standup_kind"),
                "summary": payload.get("summary"),
                "blockers": blockers,
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


def _active_standup_blockers(latest_standups: list[dict[str, Any]]) -> list[str]:
    if not latest_standups:
        return []
    return [_clean_text(blocker) for blocker in (latest_standups[0].get("blockers") or []) if _clean_text(blocker)]


def _attention_summary(*, attention_cards: list[dict[str, Any]], active_blockers: list[str]) -> dict[str, Any]:
    owner_review_cards = [card for card in attention_cards if card.get("attention_kind") == "owner_review"]
    blocked_cards = [card for card in attention_cards if card.get("attention_kind") == "blocked"]
    failed_cards = [card for card in attention_cards if card.get("attention_kind") == "failed"]
    review_cards = [card for card in attention_cards if card.get("attention_kind") == "review"]

    if active_blockers:
        status = "blocked"
        label = "Needs Brain"
    elif failed_cards:
        status = "failed_work"
        label = "Failed Work"
    elif blocked_cards:
        status = "blocked"
        label = "Blocked"
    elif review_cards:
        status = "pm_review"
        label = "PM Review"
    elif owner_review_cards:
        status = "owner_review"
        label = "Owner Review"
    else:
        status = "clear"
        label = "No blocker"

    reasons: list[str] = []
    if active_blockers:
        reasons.extend(active_blockers[:3])
    if owner_review_cards:
        reasons.append(f"{len(owner_review_cards)} owner-review PM card(s) need a decision.")
    if review_cards:
        reasons.append(f"{len(review_cards)} PM review card(s) need routing.")
    if blocked_cards:
        reasons.append(f"{len(blocked_cards)} PM card(s) are blocked.")
    if failed_cards:
        reasons.append(f"{len(failed_cards)} PM card(s) failed.")

    return {
        "status": status,
        "label": label,
        "reasons": reasons[:5],
        "owner_review_pm_cards": len(owner_review_cards),
        "review_pm_cards": len(review_cards),
        "blocked_pm_cards": len(blocked_cards),
        "failed_pm_cards": len(failed_cards),
    }


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
    root = _resolve_workspace_root(workspace_key, root_slug)
    repo_root = _repo_root_for_workspace_root(root)
    latest_briefing = _latest_file(root / "briefings", "*.md")
    latest_dispatch = _latest_file(root / "dispatch", "*.json")
    latest_analytics = _latest_file(root / "analytics", "*.md")
    latest_execution_log = root / "memory" / "execution_log.md"
    active_cards = [
        card for card in _safe_pm_cards(workspace_key, limit=pm_limit) if str(card.get("status") or "").lower() in ACTIVE_PM_STATUSES
    ]
    latest_standups = _safe_standups(workspace_key, limit=standup_limit, root_exists=root.exists())
    active_blockers = _active_standup_blockers(latest_standups)
    blocker_count = len(active_blockers)
    attention_cards = [card for card in active_cards if str(card.get("status") or "").lower() in ATTENTION_PM_STATUSES]
    attention_summary = _attention_summary(attention_cards=attention_cards, active_blockers=active_blockers)
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
            "owner_review_pm_cards": int(attention_summary.get("owner_review_pm_cards") or 0),
            "latest_standups": len(latest_standups),
            "standup_blockers": blocker_count,
        },
        "active_blockers": active_blockers,
        "attention": attention_summary,
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
