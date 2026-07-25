from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services import pm_card_service, standup_service
from app.services.brain_response_privacy_service import sanitize_brain_payload, sanitize_brain_text
from app.services.pm_truth_service import classify_pm_card
from app.services.standup_truth_service import classify_standup
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
PRIVATE_STATE_ROOT = Path(
    os.getenv("AI_CLONE_STATE_ROOT") or (Path.home() / ".codex" / "ai-clone" / "state")
).expanduser()
_WORKSPACE_STATE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


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
            return sanitize_brain_text(cleaned[:limit])
    return ""


def _tail_text(path: Path, *, max_chars: int = 1000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return sanitize_brain_text(path.read_text(encoding="utf-8", errors="ignore").strip()[-max_chars:])


def _latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    matches = sorted(path for path in directory.glob(pattern) if path.is_file())
    if not matches:
        return None
    non_readme = [path for path in matches if path.stem.lower() != "readme"]
    return non_readme[-1] if non_readme else matches[-1]


def _private_workspace_state_root(workspace_key: str) -> Path | None:
    """Resolve generated workspace state without trusting a key as a path."""

    key = str(workspace_key or "").strip().lower()
    if not _WORKSPACE_STATE_KEY_PATTERN.fullmatch(key):
        return None
    return PRIVATE_STATE_ROOT / "workspaces" / key


def _workspace_activity_roots(workspace_key: str, legacy_root: Path) -> tuple[tuple[Path, str], ...]:
    """Return state-first activity roots while retaining the project fallback."""

    state_root = _private_workspace_state_root(workspace_key)
    candidates: list[tuple[Path, str]] = []
    if state_root is not None:
        candidates.append((state_root, "private_state"))
    candidates.append((legacy_root, "legacy_project"))
    return tuple(candidates)


def _latest_workspace_activity(
    workspace_key: str,
    legacy_root: Path,
    relative_directory: str,
    pattern: str,
) -> tuple[Path | None, Path, str]:
    for activity_root, source in _workspace_activity_roots(workspace_key, legacy_root):
        path = _latest_file(activity_root / relative_directory, pattern)
        if path is not None:
            return path, activity_root, source
    return None, legacy_root, "legacy_project"


def _workspace_activity_file(
    workspace_key: str,
    legacy_root: Path,
    relative_path: str,
) -> tuple[Path, Path, str]:
    for activity_root, source in _workspace_activity_roots(workspace_key, legacy_root):
        path = activity_root / relative_path
        if path.exists() and path.is_file():
            return path, activity_root, source
    return legacy_root / relative_path, legacy_root, "legacy_project"


def _activity_payload(
    path: Path | None,
    display_root: Path,
    source: str,
    *,
    include_tail: bool = False,
) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = _path_payload(path, display_root, include_tail=include_tail)
    if payload is not None:
        payload["source"] = source
    return payload


def _activity_display_root(source: str, repo_root: Path) -> Path:
    return PRIVATE_STATE_ROOT if source == "private_state" else repo_root


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
    if "automation drift remains" in text:
        action_required = re.search(r"action_required_count\s*=\s*(\d+)", text)
        if action_required and int(action_required.group(1)) == 0:
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
    if str(getattr(card, "source", "") or "").strip() in {
        "codex_native:workspace-owner-review",
        "openclaw:workspace-owner-review",
    }:
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
    try:
        cards = list(pm_card_service.list_cards(workspace_key=workspace_key, limit=limit))
    except Exception:
        cards = []
    compacted: list[dict[str, Any]] = []
    for card in cards:
        card_id = str(getattr(card, "id", "") or "")
        if not card_id or card_id in seen:
            continue
        seen.add(card_id)
        try:
            presentation_card = pm_card_service.decorate_card_for_client(card) or card
        except Exception:
            presentation_card = card
        status = _clean_text(getattr(presentation_card, "status", "")).lower() or "todo"
        payload = getattr(presentation_card, "payload", {}) or {}
        payload_workspace_key = canonicalize_workspace_key(
            payload.get("workspace_key") or payload.get("workspace") or workspace_key,
            default=workspace_key,
        )
        truth = classify_pm_card(presentation_card)
        attention_kind = str(truth.get("attention_class") or "informational")
        compacted.append(
            {
                "id": card_id,
                "title": getattr(presentation_card, "title", ""),
                "status": status,
                "owner": getattr(presentation_card, "owner", None),
                "source": getattr(presentation_card, "source", None),
                "link_type": getattr(presentation_card, "link_type", None),
                "attention_kind": attention_kind,
                "workspace_key": payload_workspace_key,
                "updated_at": getattr(presentation_card, "updated_at", None).isoformat()
                if getattr(presentation_card, "updated_at", None)
                else None,
                "truth": truth,
            }
        )
    return compacted[:limit]


def _safe_standups(workspace_key: str, *, limit: int, root_exists: bool = False) -> list[dict[str, Any]]:
    rows: list[Any] = []
    seen: set[str] = set()
    try:
        rows = list(standup_service.list_standups(workspace_key=workspace_key, limit=limit))
    except Exception:
        rows = []
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
        truth = classify_standup(
            SimpleNamespace(
                workspace_key=getattr(standup, "workspace_key", workspace_key),
                created_at=getattr(standup, "created_at", None) or datetime.now(timezone.utc),
                payload=payload,
                commitments=list(getattr(standup, "commitments", []) or []),
                blockers=blockers,
                needs=list(getattr(standup, "needs", []) or []),
            )
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
                "truth": truth,
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
    if str((latest_standups[0].get("truth") or {}).get("freshness") or "") != "current":
        return []
    return [_clean_text(blocker) for blocker in (latest_standups[0].get("blockers") or []) if _clean_text(blocker)]


def _is_historical_failed_recovery(card: dict[str, Any]) -> bool:
    truth = card.get("truth") or {}
    return (
        str(truth.get("execution_class") or "") == "failed"
        and str(truth.get("freshness") or "") in {"stale", "historical"}
    )


def _attention_summary(
    *,
    operator_cards: list[dict[str, Any]],
    system_issue_cards: list[dict[str, Any]],
    active_blockers: list[str],
) -> dict[str, Any]:
    owner_cards = [card for card in operator_cards if card.get("attention_kind") == "needs_owner"]
    host_cards = [card for card in operator_cards if card.get("attention_kind") == "needs_host"]
    failed_cards = [
        card
        for card in system_issue_cards
        if (card.get("truth") or {}).get("execution_class") == "failed"
        and not _is_historical_failed_recovery(card)
    ]
    historical_failed_cards = [card for card in system_issue_cards if _is_historical_failed_recovery(card)]
    mismatch_cards = [card for card in system_issue_cards if bool((card.get("truth") or {}).get("state_mismatch"))]

    if owner_cards:
        status = "needs_owner"
        label = "Needs your decision"
    elif host_cards:
        status = "needs_host"
        label = "Needs your action"
    elif failed_cards or mismatch_cards or active_blockers:
        status = "system_issue"
        label = "System attention"
    else:
        status = "clear"
        label = "Healthy"

    reasons: list[str] = []
    if owner_cards:
        reasons.append(f"{len(owner_cards)} card(s) require your judgment.")
    if host_cards:
        reasons.append(f"{len(host_cards)} card(s) require an action only you can complete.")
    if failed_cards:
        reasons.append(f"{len(failed_cards)} autonomous execution(s) failed and should return to the system lane.")
    if mismatch_cards:
        reasons.append(f"{len(mismatch_cards)} card(s) disagree with their execution state.")
    if active_blockers:
        reasons.extend(active_blockers[:3])

    return {
        "status": status,
        "label": label,
        "reasons": reasons[:5],
        "needs_owner_pm_cards": len(owner_cards),
        "needs_host_pm_cards": len(host_cards),
        "failed_pm_cards": len(failed_cards),
        "historical_failed_pm_cards": len(historical_failed_cards),
        "state_mismatch_pm_cards": len(mismatch_cards),
        "needs_operator": bool(owner_cards or host_cards),
        "has_system_issue": bool(failed_cards or mismatch_cards or active_blockers),
    }


def _readiness_summary(
    *,
    latest_standups: list[dict[str, Any]],
    system_issue_cards: list[dict[str, Any]],
    active_blockers: list[str],
) -> dict[str, Any]:
    latest_truth = (latest_standups[0].get("truth") or {}) if latest_standups else {}
    failed_count = sum(
        1
        for card in system_issue_cards
        if str((card.get("truth") or {}).get("execution_class") or "") == "failed"
        and not _is_historical_failed_recovery(card)
    )
    historical_failed_count = sum(1 for card in system_issue_cards if _is_historical_failed_recovery(card))
    mismatch_count = sum(1 for card in system_issue_cards if bool((card.get("truth") or {}).get("state_mismatch")))
    legacy_instruction_count = sum(
        1 for card in system_issue_cards if bool((card.get("truth") or {}).get("legacy_instruction"))
    )
    expired_count = sum(
        1 for card in system_issue_cards if str((card.get("truth") or {}).get("freshness") or "") == "expired"
    )
    reasons: list[str] = []

    if failed_count:
        reasons.append(f"{failed_count} failed autonomous execution(s).")
    if mismatch_count:
        reasons.append(f"{mismatch_count} PM/execution state mismatch(es).")
    if expired_count:
        reasons.append(f"{expired_count} expired PM instruction(s) remain active.")
    if legacy_instruction_count:
        reasons.append(f"{legacy_instruction_count} active card(s) still reference a retired local path.")
    if historical_failed_count:
        reasons.append(f"{historical_failed_count} historical failed execution record(s) remain visible in recovery.")
    if active_blockers:
        reasons.extend(active_blockers[:2])
    if not latest_standups:
        reasons.append("No standup has been recorded for this workspace.")
    elif latest_truth.get("freshness") == "stale":
        reasons.append("The latest standup is outside its freshness window.")
    if latest_truth.get("quality") in {"ceremonial", "empty", "unrouted_blocker"}:
        reasons.append(str(latest_truth.get("quality_reason") or "The latest standup did not produce a decision handoff."))

    if failed_count or mismatch_count or active_blockers:
        state = "degraded"
        label = "Needs system attention"
    elif reasons:
        state = "watch"
        label = "Check soon"
    else:
        state = "healthy"
        label = "Healthy"

    return {
        "state": state,
        "label": label,
        "reasons": reasons[:5],
        "failed_executions": failed_count,
        "historical_failed_executions": historical_failed_count,
        "state_mismatches": mismatch_count,
        "expired_instructions": expired_count,
        "legacy_instructions": legacy_instruction_count,
        "latest_standup_freshness": latest_truth.get("freshness"),
        "latest_standup_quality": latest_truth.get("quality"),
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
    latest_briefing, briefing_root, briefing_source = _latest_workspace_activity(
        workspace_key,
        root,
        "briefings",
        "*.md",
    )
    latest_dispatch, dispatch_root, dispatch_source = _latest_workspace_activity(
        workspace_key,
        root,
        "dispatch",
        "*.json",
    )
    latest_analytics, analytics_root, analytics_source = _latest_workspace_activity(
        workspace_key,
        root,
        "analytics",
        "*.md",
    )
    latest_execution_log, execution_log_root, execution_log_source = _workspace_activity_file(
        workspace_key,
        root,
        "memory/execution_log.md",
    )
    active_cards = [
        card for card in _safe_pm_cards(workspace_key, limit=pm_limit) if str(card.get("status") or "").lower() in ACTIVE_PM_STATUSES
    ]
    latest_standups = _safe_standups(workspace_key, limit=standup_limit, root_exists=root.exists())
    active_blockers = _active_standup_blockers(latest_standups)
    blocker_count = len(active_blockers)
    operator_cards = [
        card for card in active_cards if str(card.get("attention_kind") or "") in {"needs_owner", "needs_host"}
    ]
    system_issue_cards = [
        card
        for card in active_cards
        if str((card.get("truth") or {}).get("execution_class") or "") in {"failed", "blocked"}
        or bool((card.get("truth") or {}).get("state_mismatch"))
        or bool((card.get("truth") or {}).get("legacy_instruction"))
        or str((card.get("truth") or {}).get("freshness") or "") == "expired"
    ]
    historical_recovery_cards = [card for card in system_issue_cards if _is_historical_failed_recovery(card)]
    attention_summary = _attention_summary(
        operator_cards=operator_cards,
        system_issue_cards=system_issue_cards,
        active_blockers=active_blockers,
    )
    readiness_summary = _readiness_summary(
        latest_standups=latest_standups,
        system_issue_cards=system_issue_cards,
        active_blockers=active_blockers,
    )
    source_paths = [
        value
        for value in [
            _relative_path(latest_briefing, _activity_display_root(briefing_source, repo_root))
            if latest_briefing
            else None,
            _relative_path(latest_dispatch, _activity_display_root(dispatch_source, repo_root))
            if latest_dispatch
            else None,
            _relative_path(latest_analytics, _activity_display_root(analytics_source, repo_root))
            if latest_analytics
            else None,
            _relative_path(latest_execution_log, _activity_display_root(execution_log_source, repo_root))
            if latest_execution_log.exists()
            else None,
        ]
        if value
    ]

    return {
        "workspace_key": workspace_key,
        "display_name": entry.get("portfolio_label") or entry.get("display_name") or workspace_key,
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
        "capability_keys": entry.get("capability_keys") or [],
        "capabilities": entry.get("capabilities") or [],
        "pack_status": _pack_status(root, repo_root),
        "local_contracts": _local_contracts(root, repo_root),
        "latest_briefing": _activity_payload(
            latest_briefing,
            _activity_display_root(briefing_source, repo_root),
            briefing_source,
            include_tail=True,
        ),
        "latest_dispatch": _activity_payload(
            latest_dispatch,
            _activity_display_root(dispatch_source, repo_root),
            dispatch_source,
        ),
        "latest_analytics": _activity_payload(
            latest_analytics,
            _activity_display_root(analytics_source, repo_root),
            analytics_source,
            include_tail=True,
        ),
        "execution_log": _activity_payload(
            latest_execution_log if latest_execution_log.exists() else None,
            _activity_display_root(execution_log_source, repo_root),
            execution_log_source,
            include_tail=True,
        ),
        "active_pm_cards": active_cards[:pm_limit],
        "latest_standups": latest_standups[:standup_limit],
        "persisted_snapshot_types": _safe_snapshot_types(workspace_key, root_slug),
        "counts": {
            "pack_files_present": sum(1 for item in _pack_status(root, repo_root) if item.get("exists")),
            "local_contracts": len(_local_contracts(root, repo_root)),
            "active_pm_cards": len(active_cards),
            "attention_pm_cards": len(operator_cards),
            "needs_owner_pm_cards": int(attention_summary.get("needs_owner_pm_cards") or 0),
            "needs_host_pm_cards": int(attention_summary.get("needs_host_pm_cards") or 0),
            "system_issue_pm_cards": len(system_issue_cards),
            "historical_recovery_pm_cards": len(historical_recovery_cards),
            "latest_standups": len(latest_standups),
            "standup_blockers": blocker_count,
        },
        "active_blockers": active_blockers,
        "attention": attention_summary,
        "readiness": readiness_summary,
        "needs_operator_attention": bool(attention_summary.get("needs_operator")),
        "has_system_issue": bool(attention_summary.get("has_system_issue")),
        "needs_brain_attention": bool(attention_summary.get("needs_operator") or attention_summary.get("has_system_issue")),
        "source_paths": source_paths,
    }


def build_portfolio_workspace_snapshot(*, pm_limit: int = 8, standup_limit: int = 5) -> dict[str, Any]:
    workspaces = [
        _build_workspace_summary(entry, pm_limit=pm_limit, standup_limit=standup_limit)
        for entry in workspace_registry_entries()
    ]
    visible_workspaces = [workspace for workspace in workspaces if workspace.get("portfolio_visible") or workspace.get("kind") == "executive"]
    response_payload = {
        "generated_at": _now_iso(),
        "schema_version": "portfolio_workspace_snapshot/v1",
        "source": "portfolio_workspace_snapshot_service",
        "workspaces": sorted(visible_workspaces, key=lambda item: (int(item.get("priority_order") or 999), str(item.get("workspace_key") or ""))),
        "counts": {
            "workspaces": len(visible_workspaces),
            "needs_brain_attention": sum(1 for workspace in visible_workspaces if workspace.get("needs_brain_attention")),
            "needs_operator_attention": sum(1 for workspace in visible_workspaces if workspace.get("needs_operator_attention")),
            "system_issues": sum(1 for workspace in visible_workspaces if workspace.get("has_system_issue")),
            "active_pm_cards": sum(int((workspace.get("counts") or {}).get("active_pm_cards") or 0) for workspace in visible_workspaces),
            "standup_blockers": sum(int((workspace.get("counts") or {}).get("standup_blockers") or 0) for workspace in visible_workspaces),
        },
    }
    return sanitize_brain_payload(response_payload)
