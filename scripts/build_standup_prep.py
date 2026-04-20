#!/usr/bin/env python3
"""Build standup prep from Chronicle, memory, automation state, and PM context."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain_automation_context import (
    build_brain_automation_context,
    portfolio_attention_lines,
    source_intelligence_lines,
    workspace_brain_signal_lines,
)
from durable_memory_context import build_durable_memory_context
from runtime_bootstrap import maybe_reexec_with_workspace_venv


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path
from app.services.instagram_public_feedback_service import load_workspace_feedback_snapshot

MEMORY_ROOT = WORKSPACE_ROOT / "memory"
CODEX_CHRONICLE_PATH = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/codex_session_handoff.jsonl")
JOBS_JSON = Path("/Users/neo/.openclaw/cron/jobs.json")
REGISTRY_PATH = MEMORY_ROOT / "workspace_registry.json"
INFERRED_BRIEF_PATH = WORKSPACE_ROOT / "docs" / "inferred_workspace_operating_brief_2026-03-31.md"
DEFAULT_API_URL = os.environ.get("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _tail_text(path: Path, *, max_chars: int = 1800) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return text[-max_chars:]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_api_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_jsonl_tail(path: Path, *, max_items: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    items: list[dict[str, Any]] = []
    for line in lines[-max_items:]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _latest_report(pattern: str) -> Path | None:
    matches = sorted((MEMORY_ROOT / "reports").glob(pattern))
    return matches[-1] if matches else None


def _pm_api_source_ref(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/api/pm/cards?limit=100"


def _load_fallback_watchdog_report() -> dict[str, Any]:
    path = MEMORY_ROOT / "reports" / "fallback_watchdog_latest.json"
    if not path.exists():
        return {"available": False, "active": False, "report_path": str(path), "source_paths": []}
    try:
        payload = _read_json(path)
    except Exception as exc:
        return {
            "available": False,
            "active": False,
            "report_path": str(path),
            "source_paths": [str(path)],
            "error": str(exc),
        }
    if not isinstance(payload, dict):
        return {
            "available": False,
            "active": False,
            "report_path": str(path),
            "source_paths": [str(path)],
            "error": "fallback watchdog payload is not a JSON object",
        }
    report = dict(payload)
    report["available"] = True
    report["report_path"] = str(path)
    report["source_paths"] = list(
        dict.fromkeys(
            [
                str(path),
                *[str(item).strip() for item in (report.get("source_paths") or []) if str(item).strip()],
            ]
        )
    )
    return report


def _read_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    payload = _read_json(REGISTRY_PATH)
    items = payload.get("workspaces") or []
    registry: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and item.get("workspace_key"):
            registry[str(item["workspace_key"])] = item
    return registry


def _workspace_key_candidates(workspace_key: str) -> list[str]:
    normalized = str(workspace_key or "").strip()
    if not normalized:
        return []
    lowered = normalized.lower()
    variants = {
        normalized,
        lowered,
        lowered.replace("_", "-"),
        lowered.replace("-", " "),
        lowered.replace("_", " "),
    }
    if lowered in {"linkedin-os", "linkedin os", "linkedin", "linkedin-content-os", "linkedin content os"}:
        variants.update({"feezie-os", "feezie os", "feezie", "linkedin-content-os", "linkedin content os"})
    return [variant for variant in variants if variant]


def _is_feezie_workspace_key(workspace_key: str) -> bool:
    return bool(
        set(_workspace_key_candidates(workspace_key))
        & {"feezie-os", "feezie os", "feezie", "linkedin-os", "linkedin os", "linkedin-content-os", "linkedin content os"}
    )


def _canonical_workspace_key(workspace_key: str, registry: dict[str, dict[str, Any]]) -> str:
    candidates = set(_workspace_key_candidates(workspace_key))
    for key, item in registry.items():
        item_candidates = set(_workspace_key_candidates(key))
        for field in ("workspace_root", "display_name", "legacy_name", "future_name"):
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                item_candidates.update(_workspace_key_candidates(value))
        if candidates & item_candidates:
            return key
    return workspace_key


def _workspace_root(workspace_key: str, registry: dict[str, dict[str, Any]]) -> Path | None:
    workspace_key = _canonical_workspace_key(workspace_key, registry)
    if workspace_key == "shared_ops":
        return WORKSPACE_ROOT / "workspaces" / "shared-ops"
    item = registry.get(workspace_key) or {}
    configured = item.get("filesystem_path")
    if isinstance(configured, str) and configured.strip():
        return Path(configured)
    if _is_feezie_workspace_key(workspace_key):
        return WORKSPACE_ROOT / "workspaces" / "linkedin-content-os"
    return None


def _is_workspace_root_missing_blocker(value: Any) -> bool:
    text = " ".join(str(value or "").replace("\xa0", " ").split()).strip().lower()
    return bool(text and "has no local artifact root yet" in text)


def _is_non_actionable_status_surface(value: Any) -> bool:
    text = " ".join(str(value or "").replace("\xa0", " ").split()).strip().lower()
    if not text:
        return True
    if "no active blockers reported" in text:
        return True
    if "recent standups" in text and "0 blockers" in text and "no open pm cards" in text:
        return True
    if "open pm lane" in text and "no open pm cards" in text and "0 blockers" in text:
        return True
    return False


def _filter_resolved_workspace_root_blockers(
    blockers: list[str],
    *,
    workspace_key: str,
    registry: dict[str, dict[str, Any]],
    workspace_context: dict[str, Any],
) -> list[str]:
    if not blockers:
        return []
    root = _workspace_root(workspace_key, registry)
    root_exists = bool(workspace_context.get("available")) or bool(root and root.exists())
    if not root_exists:
        return blockers
    return [item for item in blockers if not _is_workspace_root_missing_blocker(item)]


def _latest_file(directory: Path, suffix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.glob(f"*{suffix}"))
    if not matches:
        return None
    non_readme = [path for path in matches if path.stem.lower() != "readme"]
    return non_readme[-1] if non_readme else matches[-1]


def _workspace_context(workspace_key: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = _workspace_root(workspace_key, registry)
    if root is None or not root.exists():
        return {"available": False, "workspace_root": None, "source_paths": []}
    latest_sop = _latest_file(root / "dispatch", ".json")
    latest_briefing = _latest_file(root / "briefings", ".md")
    latest_analytics = _latest_file(root / "analytics", ".md")
    execution_log = root / "memory" / "execution_log.md"
    audience_feedback = load_workspace_feedback_snapshot(root)
    source_paths = [
        str(path)
        for path in (latest_sop, latest_briefing, latest_analytics, execution_log if execution_log.exists() else None)
        if path
    ]
    for key in ("json_path", "markdown_path"):
        value = audience_feedback.get(key)
        if isinstance(value, str) and value.strip():
            source_paths.append(value.strip())
    return {
        "available": True,
        "workspace_root": str(root),
        "latest_sop_path": str(latest_sop) if latest_sop else None,
        "latest_briefing_path": str(latest_briefing) if latest_briefing else None,
        "latest_analytics_path": str(latest_analytics) if latest_analytics else None,
        "execution_log_path": str(execution_log) if execution_log.exists() else None,
        "latest_sop_tail": _tail_text(latest_sop, max_chars=1200) if latest_sop else "",
        "latest_briefing_tail": _tail_text(latest_briefing, max_chars=1200) if latest_briefing else "",
        "latest_analytics_tail": _tail_text(latest_analytics, max_chars=1200) if latest_analytics else "",
        "execution_log_tail": _tail_text(execution_log, max_chars=1200) if execution_log.exists() else "",
        "audience_feedback_available": bool(audience_feedback),
        "audience_feedback_path": str(audience_feedback.get("json_path") or "").strip() or None,
        "audience_feedback_markdown_path": str(audience_feedback.get("markdown_path") or "").strip() or None,
        "audience_feedback": audience_feedback,
        "source_paths": source_paths,
    }


def _workspace_display_name(workspace_key: str, registry: dict[str, dict[str, Any]]) -> str:
    workspace_key = _canonical_workspace_key(workspace_key, registry)
    if workspace_key == "shared_ops":
        return "Executive"
    item = registry.get(workspace_key) or {}
    value = item.get("display_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return workspace_key


def _workspace_label(workspace_key: str, display_name: str | None) -> str:
    normalized_display = (display_name or workspace_key).strip()
    normalized_key = workspace_key.strip()
    if not normalized_key:
        return "`shared_ops`"
    if not normalized_display or normalized_display.lower() == normalized_key.lower():
        return f"`{normalized_key}`"
    return f"{normalized_display} (`{normalized_key}`)"


def _extract_markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    normalized_heading = heading.strip().lower()
    collected: list[str] = []
    capture = False
    base_level = None
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip().lower()
            if title == normalized_heading:
                capture = True
                base_level = level
                collected = [raw_line]
                continue
            if capture and base_level is not None and level <= base_level:
                break
        if capture:
            collected.append(raw_line)
    return "\n".join(collected).strip()


def _compact_markdown_section(markdown: str, *, max_lines: int = 10) -> str:
    if not markdown.strip():
        return ""
    lines = [line.rstrip() for line in markdown.splitlines()]
    compacted = [line for line in lines if line.strip()]
    return "\n".join(compacted[:max_lines]).strip()


def _workspace_scope_matches(workspace_key: str, candidate_workspace: str, *, include_shared_ops: bool = False) -> bool:
    if workspace_key == "shared_ops":
        return True
    allowed = {workspace_key}
    if include_shared_ops:
        allowed.add("shared_ops")
    return candidate_workspace in allowed


def _load_pack_excerpt(base: Path | None, filename: str, *, max_lines: int = 12) -> tuple[Path | None, str]:
    if base is None:
        return None, ""
    path = base / filename
    if not path.exists():
        return None, ""
    return path, _compact_markdown_section(_read_text(path), max_lines=max_lines)


def _pack_signal_lines(markdown: str, *, limit: int = 8) -> list[str]:
    signals: list[str] = []
    seen: set[str] = set()
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        elif stripped.startswith("* "):
            stripped = stripped[2:].strip()
        lowered = stripped.lower()
        if lowered.startswith(("name:", "role:", "temperament:", "values:", "judgment style:", "tone:")):
            continue
        if lowered == "known owner preferences for this lane:":
            continue
        key = lowered.rstrip(".")
        if key in seen:
            continue
        seen.add(key)
        signals.append(stripped.rstrip())
        if len(signals) >= limit:
            break
    return signals


def _first_signal_line(signals: list[str], keywords: tuple[str, ...]) -> str:
    for signal in signals:
        lowered = signal.lower()
        if any(keyword in lowered for keyword in keywords):
            return signal.rstrip(".")
    return ""


def _load_strategy_context(workspace_key: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    display_name = _workspace_display_name(workspace_key, registry)
    charter_path: Path | None = None
    workspace_root = _workspace_root(workspace_key, registry)
    if workspace_root is not None:
        candidate = workspace_root / "CHARTER.md"
        if candidate.exists():
            charter_path = candidate
    charter_excerpt = _compact_markdown_section(_read_text(charter_path), max_lines=18) if charter_path else ""
    identity_path, identity_excerpt = _load_pack_excerpt(workspace_root, "IDENTITY.md", max_lines=12)
    soul_path, soul_excerpt = _load_pack_excerpt(workspace_root, "SOUL.md", max_lines=14)
    user_path, user_excerpt = _load_pack_excerpt(workspace_root, "USER.md", max_lines=14)
    pack_signals = []
    for excerpt in (user_excerpt, soul_excerpt, identity_excerpt):
        for signal in _pack_signal_lines(excerpt):
            if signal not in pack_signals:
                pack_signals.append(signal)
    lane_boundary = _first_signal_line(
        pack_signals,
        ("inside `", "inside ", "is not:", "contained", "containment", "lane", "workspace"),
    )
    trust_constraint = _first_signal_line(
        pack_signals,
        ("trust", "families", "students", "partners", "frontline", "school"),
    )
    execution_posture = _first_signal_line(
        pack_signals,
        ("artifact", "report back", "clear", "discipline", "execute", "escalate", "blocker", "status"),
    )

    inferred_heading = {
        "feezie-os": "FEEZIE OS",
        "linkedin-os": "FEEZIE OS",
        "fusion-os": "Fusion OS",
        "easyoutfitapp": "Easy Outfit App",
        "ai-swag-store": "AI Swag Store",
        "agc": "AGC",
        "shared_ops": "Executive Interpretation Rule",
    }.get(workspace_key, display_name)
    inferred_excerpt = ""
    if INFERRED_BRIEF_PATH.exists():
        inferred_text = _read_text(INFERRED_BRIEF_PATH)
        inferred_excerpt = _compact_markdown_section(_extract_markdown_section(inferred_text, inferred_heading), max_lines=18)

    default_routing = "Strong signal should usually go to canonical memory plus standup before PM."
    if _is_feezie_workspace_key(workspace_key):
        default_routing = "FEEZIE signal should usually go to canonical memory plus executive standup first, then persona canon or PM when justified."
    return {
        "workspace_key": workspace_key,
        "display_name": display_name,
        "charter_path": str(charter_path) if charter_path else None,
        "charter_excerpt": charter_excerpt,
        "identity_path": str(identity_path) if identity_path else None,
        "identity_excerpt": identity_excerpt,
        "soul_path": str(soul_path) if soul_path else None,
        "soul_excerpt": soul_excerpt,
        "user_path": str(user_path) if user_path else None,
        "user_excerpt": user_excerpt,
        "pack_signal_lines": pack_signals[:6],
        "lane_boundary": lane_boundary,
        "trust_constraint": trust_constraint,
        "execution_posture": execution_posture,
        "inferred_brief_path": str(INFERRED_BRIEF_PATH) if INFERRED_BRIEF_PATH.exists() else None,
        "inferred_excerpt": inferred_excerpt,
        "default_routing": default_routing,
    }


def _parse_delivery_hygiene_metrics() -> dict[str, Any]:
    report = _latest_report("openclaw_cron_delivery_hygiene_*.md")
    if report is None:
        return {}
    text = report.read_text(encoding="utf-8", errors="ignore")
    metrics: dict[str, Any] = {"source": str(report)}
    for key in ("mismatch_count", "action_required_count"):
        marker = f"{key} = "
        idx = text.find(marker)
        if idx == -1:
            continue
        value = text[idx + len(marker) :].splitlines()[0].strip()
        if value.isdigit():
            metrics[key] = int(value)
    return metrics


def _optional_backend_imports() -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {}
    try:
        from app.services.pm_card_service import list_cards  # type: ignore

        loaded["list_cards"] = list_cards
    except Exception as exc:
        loaded["pm_error"] = str(exc)
    try:
        from app.services.workspace_runtime_contract_service import default_standup_kind_for_workspace  # type: ignore

        loaded["default_standup_kind_for_workspace"] = default_standup_kind_for_workspace
    except Exception as exc:
        loaded["runtime_contract_error"] = str(exc)
    try:
        from app.models import StandupCreate  # type: ignore
        from app.services.standup_service import create_standup  # type: ignore

        loaded["StandupCreate"] = StandupCreate
        loaded["create_standup"] = create_standup
    except Exception as exc:
        loaded["standup_error"] = str(exc)
    try:
        from app.services.automation_mismatch_service import build_mismatch_report  # type: ignore

        loaded["build_mismatch_report"] = build_mismatch_report
    except Exception as exc:
        loaded["automation_error"] = str(exc)
    return loaded


def _workspace_key_from_card(card: dict[str, Any]) -> str:
    payload = card.get("payload") or {}
    for key in ("workspace_key", "workspace", "belongs_to_workspace"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "shared_ops"


def _normalize_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"ready", "todo", "to_do", "pending"}:
        return "ready"
    if normalized in {"queued", "queue"}:
        return "queued"
    if normalized in {"running", "in_progress", "in-progress", "active"}:
        return "in_progress"
    if normalized in {"review", "in_review"}:
        return "review"
    if normalized in {"blocked", "stalled", "failed"}:
        return "blocked"
    if normalized in {"done", "complete", "completed"}:
        return "done"
    return normalized or "ready"


def _dedupe_strings(values: list[str], *, limit: int = 10) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = " ".join(str(item).split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def _build_pm_snapshot(pm_context: dict[str, Any], workspace_key: str, workspace_label: str) -> dict[str, Any]:
    if not pm_context.get("available"):
        return {
            "available": False,
            "workspace_key": workspace_key,
            "card_count": 0,
            "open_count": 0,
            "status_counts": {},
            "cards": [],
            "lines": [
                f"PM board is not reachable for {workspace_label}.",
                "Treat this standup as recommendation-only until live PM state is available.",
            ],
        }

    cards = []
    status_counts: Counter[str] = Counter()
    for item in pm_context.get("cards") or []:
        if not isinstance(item, dict):
            continue
        normalized_status = _normalize_status(str(item.get("status") or "ready"))
        status_counts[normalized_status] += 1
        cards.append(
            {
                "id": item.get("id"),
                "title": str(item.get("title") or "Untitled").strip(),
                "owner": item.get("owner"),
                "status": normalized_status,
                "workspace_key": item.get("workspace_key") or workspace_key,
                "updated_at": item.get("updated_at"),
            }
        )

    open_count = sum(count for key, count in status_counts.items() if key != "done")
    lines = [f"{open_count} open PM card(s) across {workspace_label}."]
    if status_counts:
        fragments = []
        for key in ("blocked", "review", "in_progress", "queued", "ready", "done"):
            if status_counts.get(key):
                fragments.append(f"{key}={status_counts[key]}")
        if fragments:
            lines.append("Status mix: " + ", ".join(fragments) + ".")
    focus_cards = cards[:5]
    if focus_cards:
        focus_titles = ", ".join(f"{card['title']} ({card['status']})" for card in focus_cards)
        lines.append(f"Top board focus: {focus_titles}.")

    return {
        "available": True,
        "workspace_key": workspace_key,
        "card_count": len(cards),
        "open_count": open_count,
        "status_counts": dict(status_counts),
        "cards": cards[:12],
        "lines": lines,
    }


def _build_artifact_deltas(
    chronicle_entries: list[dict[str, Any]],
    automation_context: dict[str, Any],
    workspace_context: dict[str, Any],
    memory_context: dict[str, Any],
) -> list[str]:
    deltas: list[str] = []
    if chronicle_entries:
        latest = chronicle_entries[-1]
        summary = _standup_chronicle_summary(latest)
        if summary:
            deltas.append(f"Chronicle: {summary}")
        for item in latest.get("decisions") or []:
            normalized_item = _normalize_standup_signal_text(item)
            if normalized_item:
                deltas.append(f"Chronicle decision: {normalized_item}")
    mismatch_count = int(
        automation_context.get("mismatch_count")
        or (automation_context.get("fallback") or {}).get("mismatch_count")
        or 0
    )
    action_required = int(
        automation_context.get("action_required_count")
        or (automation_context.get("fallback") or {}).get("action_required_count")
        or 0
    )
    if mismatch_count or action_required:
        deltas.append(
            f"Automation: mismatch_count={mismatch_count}, action_required_count={action_required}."
        )
    if workspace_context.get("latest_briefing_path"):
        deltas.append(f"Workspace briefing ready: {workspace_context['latest_briefing_path']}")
    if workspace_context.get("latest_analytics_path"):
        deltas.append(f"Workspace analytics note ready: {workspace_context['latest_analytics_path']}")
    if workspace_context.get("latest_sop_path"):
        deltas.append(f"Latest SOP: {workspace_context['latest_sop_path']}")
    audience_feedback = dict(workspace_context.get("audience_feedback") or {})
    if audience_feedback:
        profile = dict(audience_feedback.get("profile") or {})
        recent_summary = dict(audience_feedback.get("recent_summary") or {})
        fragments: list[str] = []
        followers = profile.get("followers")
        sample_size = recent_summary.get("sample_size")
        avg_visible_engagement = recent_summary.get("average_visible_engagement")
        if isinstance(followers, (int, float)):
            fragments.append(f"followers={int(followers)}")
        if isinstance(sample_size, (int, float)) and sample_size:
            fragments.append(f"recent_sample={int(sample_size)}")
        if isinstance(avg_visible_engagement, (int, float)):
            fragments.append(f"avg_visible_engagement={avg_visible_engagement}")
        top_post = dict(recent_summary.get("top_post") or {})
        if top_post.get("shortcode") and isinstance(top_post.get("visible_engagement"), (int, float)):
            fragments.append(f"top_post={top_post['shortcode']}({int(top_post['visible_engagement'])})")
        if fragments:
            deltas.append("Audience feedback: " + ", ".join(fragments) + ".")
        feedback_path = str(workspace_context.get("audience_feedback_path") or "").strip()
        if feedback_path:
            deltas.append(f"Audience feedback snapshot: {feedback_path}")
    if memory_context.get("daily_briefs_tail"):
        deltas.append("Daily brief is populated and ready for standup review.")
    if memory_context.get("cron_prune_tail"):
        deltas.append("Pruning cycle history is available for memory continuity checks.")
    return _dedupe_strings(deltas, limit=8)


def _build_audience_response(workspace_context: dict[str, Any]) -> list[str]:
    audience_feedback = dict(workspace_context.get("audience_feedback") or {})
    if not audience_feedback:
        return []
    lines: list[str] = []
    feedback_path = str(workspace_context.get("audience_feedback_path") or "").strip()
    if feedback_path:
        lines.append(f"Public audience-feedback snapshot is ready: {feedback_path}")
    profile = dict(audience_feedback.get("profile") or {})
    recent_summary = dict(audience_feedback.get("recent_summary") or {})
    fragments: list[str] = []
    followers = profile.get("followers")
    sample_size = recent_summary.get("sample_size")
    avg_likes = recent_summary.get("average_visible_likes")
    avg_comments = recent_summary.get("average_visible_comments")
    avg_engagement = recent_summary.get("average_visible_engagement")
    if isinstance(followers, (int, float)):
        fragments.append(f"followers={int(followers)}")
    if isinstance(sample_size, (int, float)) and sample_size:
        fragments.append(f"recent_sample={int(sample_size)}")
    if isinstance(avg_likes, (int, float)):
        fragments.append(f"avg_visible_likes={avg_likes}")
    if isinstance(avg_comments, (int, float)):
        fragments.append(f"avg_visible_comments={avg_comments}")
    if isinstance(avg_engagement, (int, float)):
        fragments.append(f"avg_visible_engagement={avg_engagement}")
    if fragments:
        lines.append("Instagram public response: " + ", ".join(fragments) + ".")
    top_post = dict(recent_summary.get("top_post") or {})
    if top_post.get("shortcode") and top_post.get("url"):
        lines.append(
            f"Top visible-response post: `{top_post['shortcode']}` at {top_post['url']} with visible engagement {top_post.get('visible_engagement') or 0}."
        )
    limitations = [str(item).strip() for item in (audience_feedback.get("limitations") or []) if str(item).strip()]
    if limitations:
        lines.append(limitations[0])
    return _dedupe_strings(lines, limit=4)


def _build_signals_captured(workspace_key: str, chronicle_entries: list[dict[str, Any]], workspace_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if chronicle_entries:
        summary = _standup_chronicle_summary(chronicle_entries[-1])
        if summary:
            lines.append(summary)
    audience_feedback = dict(workspace_context.get("audience_feedback") or {})
    for item in audience_feedback.get("signal_lines") or []:
        normalized = str(item).strip()
        if normalized:
            lines.append(normalized)
    recent_summary = dict(audience_feedback.get("recent_summary") or {})
    posts_last_30d = recent_summary.get("posts_last_30d")
    if isinstance(posts_last_30d, (int, float)):
        lines.append(f"Public Instagram sample shows {int(posts_last_30d)} post(s) inside the last 30 days.")
    return _dedupe_strings(lines, limit=5)


def _build_content_produced(workspace_context: dict[str, Any]) -> list[str]:
    audience_feedback = dict(workspace_context.get("audience_feedback") or {})
    recent_posts = list(audience_feedback.get("recent_posts") or [])
    if not recent_posts:
        return []
    lines: list[str] = []
    for post in recent_posts[:4]:
        shortcode = str(post.get("shortcode") or "unknown").strip()
        taken_at = str(post.get("taken_at") or "unknown").strip()
        pillar = str(post.get("content_pillar") or "Unknown pillar").strip()
        audience = str(post.get("audience") or "unknown audience").strip()
        visible_engagement = int(post.get("visible_engagement") or 0)
        caption = str(post.get("caption_excerpt") or "No caption excerpt.").strip()
        lines.append(
            f"`{shortcode}` | {taken_at} | {pillar} for {audience} | visible engagement={visible_engagement} | {caption}"
        )
    return _dedupe_strings(lines, limit=4)


def _build_generic_work_produced(workspace_context: dict[str, Any], pm_snapshot: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if workspace_context.get("latest_sop_path"):
        lines.append(f"Latest SOP is staged at `{workspace_context['latest_sop_path']}`.")
    if workspace_context.get("latest_briefing_path"):
        lines.append(f"Latest workspace briefing is ready at `{workspace_context['latest_briefing_path']}`.")
    if workspace_context.get("latest_analytics_path"):
        lines.append(f"Latest analytics note is ready at `{workspace_context['latest_analytics_path']}`.")
    if workspace_context.get("execution_log_path"):
        lines.append(f"Execution log is available at `{workspace_context['execution_log_path']}` for ship-state review.")
    for card in pm_snapshot.get("cards") or []:
        status = str(card.get("status") or "").strip()
        title = str(card.get("title") or "").strip()
        if title and status in {"in_progress", "review", "done"}:
            lines.append(f"PM board reflects `{title}` in `{status}` status.")
        if len(lines) >= 4:
            break
    return _dedupe_strings(lines, limit=4)


def _build_opportunities_created(workspace_context: dict[str, Any]) -> list[str]:
    audience_feedback = dict(workspace_context.get("audience_feedback") or {})
    opportunities = [str(item).strip() for item in (audience_feedback.get("opportunity_signals") or []) if str(item).strip()]
    return _dedupe_strings(opportunities, limit=5)


def _build_generic_traction(workspace_context: dict[str, Any], pm_snapshot: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if workspace_context.get("audience_feedback_path"):
        lines.append(f"Feedback snapshot is available at `{workspace_context['audience_feedback_path']}`.")
    if workspace_context.get("latest_analytics_path"):
        lines.append(f"Latest traction note is ready at `{workspace_context['latest_analytics_path']}`.")
    if pm_snapshot.get("available"):
        open_count = int(pm_snapshot.get("open_count") or 0)
        lines.append(f"PM board is reachable with {open_count} open card(s); live traction still needs explicit measurement artifacts.")
    elif workspace_context.get("latest_briefing_path") or workspace_context.get("execution_log_path"):
        lines.append("Local execution artifacts exist, but no explicit traction snapshot has been captured yet.")
    return _dedupe_strings(lines, limit=4)


def _build_generic_opportunities(workspace_context: dict[str, Any], pm_snapshot: dict[str, Any], needs: list[str]) -> list[str]:
    lines: list[str] = []
    for card in pm_snapshot.get("cards") or []:
        status = str(card.get("status") or "").strip()
        title = str(card.get("title") or "").strip()
        if title and status in {"review", "queued", "ready", "in_progress"}:
            lines.append(f"`{title}` is the next visible opportunity to qualify or advance.")
        if len(lines) >= 3:
            break
    for item in needs[:2]:
        normalized = str(item).strip()
        if normalized:
            lines.append(normalized)
    if workspace_context.get("latest_briefing_path") and not lines:
        lines.append("The latest workspace briefing should be reviewed for the next concrete opportunity.")
    return _dedupe_strings(lines, limit=5)


def _build_next_focus_section(
    workspace_context: dict[str, Any],
    pm_snapshot: dict[str, Any],
    needs: list[str],
) -> list[str]:
    lines: list[str] = []
    audience_feedback = dict(workspace_context.get("audience_feedback") or {})
    for item in audience_feedback.get("recommended_next_focus") or []:
        normalized = str(item).strip()
        if normalized:
            lines.append(normalized)
    for card in pm_snapshot.get("cards") or []:
        if str(card.get("status") or "") == "review":
            title = str(card.get("title") or "").strip()
            if title:
                lines.append(f"Resolve whether `{title}` closes or reopens before new narrative work expands.")
            break
    for item in needs[:1]:
        normalized = str(item).strip()
        if normalized:
            lines.append(normalized)
    return _dedupe_strings(lines, limit=5)


def _build_standup_sections(
    workspace_key: str,
    chronicle_entries: list[dict[str, Any]],
    workspace_context: dict[str, Any],
    pm_snapshot: dict[str, Any],
    audience_response: list[str],
    needs: list[str],
) -> dict[str, list[str]]:
    if workspace_key == "shared_ops":
        return {}

    signal_lines = _build_signals_captured(workspace_key, chronicle_entries, workspace_context)
    if not signal_lines and workspace_context.get("latest_briefing_path"):
        signal_lines = [f"Latest workspace briefing is available at `{workspace_context['latest_briefing_path']}`."]

    work_lines = _build_content_produced(workspace_context)
    if not work_lines:
        work_lines = _build_generic_work_produced(workspace_context, pm_snapshot)

    traction_lines = audience_response or _build_generic_traction(workspace_context, pm_snapshot)
    opportunity_lines = _build_opportunities_created(workspace_context)
    if not opportunity_lines:
        opportunity_lines = _build_generic_opportunities(workspace_context, pm_snapshot, needs)

    sections = {
        "signals_captured": signal_lines,
        "content_produced": work_lines,
        "audience_response": traction_lines,
        "opportunities_created": opportunity_lines,
        "next_focus": _build_next_focus_section(workspace_context, pm_snapshot, needs),
    }
    return {key: value for key, value in sections.items() if value}


def _build_agenda(
    pm_snapshot: dict[str, Any],
    pm_updates: list[dict[str, Any]],
    blockers: list[str],
    workspace_key: str,
    strategy_context: dict[str, Any],
    standup_kind: str,
) -> list[str]:
    agenda: list[str] = []
    display_name = str(strategy_context.get("display_name") or workspace_key)
    if _is_feezie_workspace_key(workspace_key):
        agenda.append(
            "Check whether the next public move strengthens Feeze's brand, career narrative, and trust before optimizing for content output."
        )
    elif workspace_key != "shared_ops":
        agenda.append(f"Pressure-test the next move against `{display_name}` mission, constraints, and lane boundaries.")
    elif standup_kind in {"executive_ops", "weekly_review"}:
        agenda.append("Start from PM truth, then test whether current motion still matches the inferred workspace operating brief.")

    if pm_snapshot.get("available"):
        cards = pm_snapshot.get("cards") or []
        blocked = [card for card in cards if card.get("status") == "blocked"]
        review = [card for card in cards if card.get("status") == "review"]
        active = [card for card in cards if card.get("status") in {"in_progress", "queued", "ready"}]

        for card in blocked[:2]:
            agenda.append(f"Unblock `{card['title']}` before new work enters the lane.")
        for card in review[:2]:
            agenda.append(f"Decide whether `{card['title']}` closes or returns to execution.")
        for card in active[:2]:
            agenda.append(f"Confirm the next move for `{card['title']}` on the PM board.")

    for item in pm_updates[:2]:
        title = str(item.get("title") or "").strip()
        if title:
            agenda.append(f"Decide whether to create or queue `{title}`.")

    if blockers:
        agenda.append(f"Resolve the top blocker: {blockers[0]}")

    if not agenda:
        label = display_name if workspace_key != "shared_ops" else "shared ops"
        agenda.append(f"Nothing to report from the PM board for {label}. Keep the lane ready for the next real signal.")
    return _dedupe_strings(agenda, limit=6)


def _load_pm_context_from_api(workspace_key: str, api_url: str) -> dict[str, Any]:
    url = _pm_api_source_ref(api_url)
    payload = _fetch_api_json(url)
    rows = payload if isinstance(payload, list) else payload.get("cards") or []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_workspace = _workspace_key_from_card(row)
        if not _workspace_scope_matches(workspace_key, row_workspace):
            continue
        filtered.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "owner": row.get("owner"),
                "status": row.get("status"),
                "workspace_key": row_workspace,
                "updated_at": row.get("updated_at"),
            }
        )
    return {
        "available": True,
        "cards": filtered[:25],
        "card_count": len(filtered),
        "source": "pm_api",
        "source_ref": url,
        "primary_source": "pm_api",
        "fallback_active": False,
    }


def _load_pm_context(imports: dict[str, Any], workspace_key: str, api_url: str) -> dict[str, Any]:
    api_error: str | None = None
    try:
        return _load_pm_context_from_api(workspace_key, api_url)
    except Exception as exc:
        api_error = str(exc)

    list_cards = imports.get("list_cards")
    if list_cards is None:
        return {
            "available": False,
            "error": f"{api_error}; local fallback failed: {imports.get('pm_error', 'pm unavailable')}",
            "cards": [],
            "card_count": 0,
            "source": "pm_unavailable",
            "source_ref": _pm_api_source_ref(api_url),
            "primary_source": "pm_api",
            "fallback_active": True,
            "fallback_reason": "pm_api_error",
            "primary_error": api_error,
        }
    try:
        rows = [item.model_dump(mode="json") for item in list_cards(limit=100)]
    except Exception as exc:
        return {
            "available": False,
            "error": f"{api_error}; local fallback failed: {exc}",
            "cards": [],
            "card_count": 0,
            "source": "pm_unavailable",
            "source_ref": _pm_api_source_ref(api_url),
            "primary_source": "pm_api",
            "fallback_active": True,
            "fallback_reason": "pm_api_error",
            "primary_error": api_error,
            "fallback_error": str(exc),
        }

    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_workspace = _workspace_key_from_card(row)
        if not _workspace_scope_matches(workspace_key, row_workspace):
            continue
        filtered.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "owner": row.get("owner"),
                "status": row.get("status"),
                "workspace_key": row_workspace,
                "updated_at": row.get("updated_at"),
            }
        )
    return {
        "available": True,
        "cards": filtered[:25],
        "card_count": len(filtered),
        "source": "pm_backend_service",
        "source_ref": "app.services.pm_card_service.list_cards",
        "primary_source": "pm_api",
        "fallback_active": True,
        "fallback_reason": "pm_api_error",
        "primary_error": api_error,
    }


def _load_automation_context(imports: dict[str, Any]) -> dict[str, Any]:
    build_mismatch_report = imports.get("build_mismatch_report")
    if build_mismatch_report is not None:
        try:
            payload = build_mismatch_report().model_dump(mode="json")
            payload["available"] = True
            payload["source"] = "automation_mismatch_service"
            payload["source_ref"] = "app.services.automation_mismatch_service.build_mismatch_report"
            payload["primary_source"] = "automation_mismatch_service"
            payload["fallback_active"] = False
            return payload
        except Exception as exc:
            fallback = _parse_delivery_hygiene_metrics()
            return {
                "available": False,
                "error": str(exc),
                "fallback": fallback,
                "source": "delivery_hygiene_metrics" if fallback else "automation_unavailable",
                "source_ref": fallback.get("source") if isinstance(fallback, dict) else None,
                "primary_source": "automation_mismatch_service",
                "fallback_active": True,
                "fallback_reason": "automation_mismatch_service_error",
                "primary_error": str(exc),
            }
    jobs: list[dict[str, Any]] = []
    if JOBS_JSON.exists():
        try:
            payload = _read_json(JOBS_JSON)
            jobs = [item for item in payload.get("jobs") or [] if isinstance(item, dict)]
        except Exception:
            jobs = []
    fallback = _parse_delivery_hygiene_metrics()
    return {
        "available": False,
        "error": imports.get("automation_error", "automation unavailable"),
        "job_count": len(jobs),
        "job_names": [str(item.get("name") or "Unnamed") for item in jobs[:20]],
        "fallback": fallback,
        "source": "delivery_hygiene_metrics" if fallback else "automation_unavailable",
        "source_ref": fallback.get("source") if isinstance(fallback, dict) else None,
        "primary_source": "automation_mismatch_service",
        "fallback_active": True,
        "fallback_reason": "automation_mismatch_service_unavailable",
        "primary_error": imports.get("automation_error", "automation unavailable"),
    }


def _filter_chronicle_entries(workspace_key: str, max_items: int) -> list[dict[str, Any]]:
    entries = _read_jsonl_tail(CODEX_CHRONICLE_PATH, max_items=max_items)
    filtered: list[dict[str, Any]] = []
    for item in entries:
        entry_workspace = str(item.get("workspace_key") or "shared_ops")
        if not _workspace_scope_matches(workspace_key, entry_workspace):
            continue
        filtered.append(item)
    return filtered


def _normalize_memory_content(content: str) -> str:
    lowered = content.lower()
    if lowered.startswith("--- ## context") or "current fusion-os workspace is internally inconsistent" in lowered:
        return "Fusion OS needed a coherent content-and-signal operating model before weekly automation could be trusted."
    if "voice system" in lowered and "fusion academy dc" in lowered and "observation" in lowered and "guidance" in lowered:
        return (
            "Fusion content should use institutional voice, represent Fusion Academy DC, avoid first-person singular, "
            "and follow Observation -> Clarification -> Guidance."
        )
    if lowered.startswith("excellent please let me know what you need to implement"):
        return "Implement the approved Fusion operating model and audience-feedback loop."
    if "ai clone" in lowered and "workspace" in lowered and ("stand up" in lowered or "standup" in lowered):
        return "Jean-Claude should use whole-system AI Clone context to inform each workspace while only routing workspace-relevant signal into standups."
    if "jean claude" in lowered and ("multiple wrkspaces" in lowered or "multiple workspaces" in lowered):
        return "Jean-Claude needs a routing contract for using whole-system context across multiple workspaces."
    if lowered.startswith("i think a great place to start") and "jean claude" in lowered:
        return "Start with Jean-Claude's cross-workspace routing contract."
    if lowered.startswith("so he will need") and "workspace" in lowered:
        return "Jean-Claude should filter whole-system context down to the signals that matter for each workspace."
    if "kodex" in lowered or "codex" in lowered:
        if "open claw" in lowered or "openclaw" in lowered:
            return "Codex conversations need periodic Chronicle writes so OpenClaw stays aligned with current work."
        return "Codex work should be preserved as high-signal Chronicle chunks before context loss."
    if "heartbeat" in lowered and "discord" in lowered:
        return "Heartbeat outputs need to be diagnostically useful, not just generic summaries."
    if "heartbeat" in lowered:
        return "Heartbeat should wake the system and produce actionable state, not just silent status."
    if "tell the story" in lowered or "perfect memory" in lowered or "second brain" in lowered:
        return "The AI clone should preserve project, learning, voice, and identity signal as second-brain memory."
    if "persona" in lowered or "how i talk" in lowered or "phrase" in lowered:
        return "Chronicle should preserve persona, phrasing, and project-development signal from Codex work."
    return content.strip()


def _normalize_standup_signal_text(content: Any) -> str:
    normalized = _normalize_memory_content(" ".join(str(content or "").split()).strip())
    if _is_non_actionable_status_surface(normalized):
        return ""
    lowered = normalized.lower()
    if lowered.startswith("love it") and "plan" in lowered and "execute" in lowered:
        return "Recent Codex discussion tightened the execution plan."
    if lowered in {"yes please do that.", "yes please do that", "please execute on both.", "please execute on both"}:
        return "Recent Codex discussion confirmed the next execution step."
    return normalized


def _standup_chronicle_summary(entry: dict[str, Any]) -> str:
    source = str(entry.get("source") or "").strip().lower()
    if source == "codex-history":
        candidates = [
            _normalize_standup_signal_text(item) for item in (entry.get("decisions") or [])[:1]
        ]
        candidates.extend(_normalize_standup_signal_text(item) for item in (entry.get("follow_ups") or [])[:1])
        candidates.extend(_normalize_standup_signal_text(item) for item in (entry.get("project_updates") or [])[:1])
        for candidate in candidates:
            if candidate:
                return f"Recent Codex discussion for `{entry.get('workspace_key') or 'shared_ops'}`: {candidate}"
        return f"Recent Codex discussion updated Chronicle context for `{entry.get('workspace_key') or 'shared_ops'}`."
    return _normalize_standup_signal_text(entry.get("summary") or "")


def _normalize_pm_title(candidate: str) -> str:
    lowered = candidate.lower()
    if lowered.startswith("jean-claude should ") or "promotion boundary" in lowered or "narrowed sop" in lowered:
        return "Tighten Chronicle-to-PM promotion criteria for autonomous execution"
    if "openclaw" in lowered and "codex" in lowered:
        return "Align OpenClaw and Codex workflow sync"
    if "heartbeat" in lowered and "discord" in lowered:
        return "Make heartbeat and Discord summaries diagnostically useful"
    if "heartbeat" in lowered:
        return "Verify heartbeat wake, logging, and summary quality"
    if "pm board" in lowered or "stand-up" in lowered or "standup" in lowered:
        return "Wire Chronicle into standup and PM flow"
    if "memory" in lowered or "persistent" in lowered:
        return "Promote Codex Chronicle into durable memory"
    if "workspace standup" in lowered and "fusion" in lowered:
        return "Create the first recurring Fusion OS workspace standup"
    if "fusion" in lowered and "execution lane" in lowered:
        return "Turn Fusion OS delegated proof into a recurring workspace execution lane"
    return candidate.strip()[:120]


def _is_actionable_pm_title(title: str) -> bool:
    normalized = " ".join(title.split()).strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    disallowed_prefixes = (
        "jean-claude should ",
        "neo should ",
        "yoda should ",
        "workspace execution should ",
        "complete ",
        "keep ",
        "decide whether ",
        "review ",
    )
    if lowered.startswith(disallowed_prefixes):
        return False
    if lowered.startswith("nothing to report"):
        return False

    allowed_prefixes = (
        "align ",
        "backfill ",
        "build ",
        "clarify ",
        "create ",
        "define ",
        "document ",
        "make ",
        "promote ",
        "refine ",
        "run ",
        "standardize ",
        "tighten ",
        "turn ",
        "verify ",
        "wire ",
    )
    return lowered.startswith(allowed_prefixes)


def _pm_candidate_gate(
    candidate: str,
    normalized_title: str,
    pm_snapshot: dict[str, Any],
) -> tuple[bool, str]:
    raw = " ".join(str(candidate).split()).strip()
    title = " ".join(normalized_title.split()).strip()
    if not raw or not title:
        return False, "empty"

    existing_titles = {
        str(card.get("title") or "").strip().lower()
        for card in (pm_snapshot.get("cards") or [])
        if isinstance(card, dict) and str(card.get("title") or "").strip()
    }
    if title.lower() in existing_titles:
        return False, "duplicate_active_card"

    lowered_raw = raw.lower()
    advisory_prefixes = (
        "workspace execution should ",
        "jean-claude should ",
        "neo should ",
        "yoda should ",
        "keep ",
        "complete ",
        "review ",
        "decide whether ",
        "nothing to report",
    )
    if lowered_raw.startswith(advisory_prefixes):
        return False, "advisory_statement"

    if not _is_actionable_pm_title(title):
        return False, "not_action_shaped"

    return True, "promote_to_pm"


def _build_promotions(entries: list[dict[str, Any]], workspace_key: str) -> list[dict[str, Any]]:
    promotions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in entries:
        for content in item.get("memory_promotions") or []:
            normalized = _normalize_memory_content(content)
            key = ("persistent_state", normalized.strip().lower())
            if not normalized or key in seen:
                continue
            seen.add(key)
            promotions.append(
                {
                    "target": "persistent_state",
                    "workspace_key": workspace_key,
                    "reason": "Chronicle signal marked for durable memory.",
                    "content": normalized,
                }
            )
        for content in item.get("learning_updates") or []:
            normalized = _normalize_memory_content(content)
            key = ("learnings", normalized.strip().lower())
            if not normalized or key in seen:
                continue
            seen.add(key)
            promotions.append(
                {
                    "target": "learnings",
                    "workspace_key": workspace_key,
                    "reason": "Implementation learning should survive beyond the current session.",
                    "content": normalized,
                }
            )
    return promotions[:10]


def _build_pm_updates(
    entries: list[dict[str, Any]],
    workspace_key: str,
    owner_agent: str,
    pm_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not pm_snapshot.get("available"):
        return updates

    if workspace_key == "shared_ops":
        candidate_entries = entries
    else:
        candidate_entries = [
            item for item in entries if str(item.get("workspace_key") or "shared_ops") == workspace_key
        ]
        if not candidate_entries:
            return updates
    for item in candidate_entries:
        for candidate in item.get("pm_candidates") or []:
            title = _normalize_pm_title(candidate)
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            should_promote, _ = _pm_candidate_gate(candidate, title, pm_snapshot)
            if not should_promote:
                continue
            seen.add(key)
            updates.append(
                {
                    "action": "recommend_only",
                    "pm_card_id": None,
                    "workspace_key": workspace_key,
                    "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
                    "owner_agent": owner_agent,
                    "title": title[:120],
                    "status": "todo",
                    "reason": "Derived from recent Codex Chronicle signal during standup prep.",
                    "payload": {
                        "priority": "medium",
                        "source": "standup_prep",
                        "source_agent": owner_agent,
                    },
                }
            )
    return updates[:10]


def _strategy_lines(strategy_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    charter_excerpt = str(strategy_context.get("charter_excerpt") or "").strip()
    identity_excerpt = str(strategy_context.get("identity_excerpt") or "").strip()
    soul_excerpt = str(strategy_context.get("soul_excerpt") or "").strip()
    user_excerpt = str(strategy_context.get("user_excerpt") or "").strip()
    inferred_excerpt = str(strategy_context.get("inferred_excerpt") or "").strip()
    if charter_excerpt or identity_excerpt or soul_excerpt or user_excerpt:
        lines.append(f"Charter and workspace pack loaded for `{strategy_context.get('display_name')}`.")
    lane_boundary = str(strategy_context.get("lane_boundary") or "").strip()
    if lane_boundary:
        lines.append(f"Workspace boundary: {lane_boundary}.")
    trust_constraint = str(strategy_context.get("trust_constraint") or "").strip()
    if trust_constraint:
        lines.append(f"Trust constraint: {trust_constraint}.")
    execution_posture = str(strategy_context.get("execution_posture") or "").strip()
    if execution_posture:
        lines.append(f"Execution posture: {execution_posture}.")
    if inferred_excerpt:
        lines.append("Inferred operating brief is available and should shape interpretation.")
    routing = str(strategy_context.get("default_routing") or "").strip()
    if routing:
        lines.append(routing)
    return lines


def _build_markdown(prep: dict[str, Any]) -> str:
    lines = [
        f"# Standup Prep — {prep['standup_kind']} — {prep['workspace_key']}",
        "",
        f"- Generated: `{prep['generated_at']}`",
        f"- Owner Agent: `{prep['owner_agent']}`",
        "",
        "## Summary",
        prep["summary"],
        "",
        "## PM Snapshot",
    ]
    pm_snapshot_lines = list((prep.get("pm_snapshot") or {}).get("lines") or [])
    if not pm_snapshot_lines:
        lines.append("- No PM snapshot available.")
    else:
        for item in pm_snapshot_lines:
            lines.append(f"- {item}")
    lines.extend(["", "## Agenda"])
    agenda = prep.get("agenda") or ["Nothing to report."]
    for item in agenda:
        lines.append(f"- {item}")
    lines.extend(["", "## Artifact Deltas"])
    artifact_deltas = prep.get("artifact_deltas") or ["No artifact deltas captured yet."]
    for item in artifact_deltas:
        lines.append(f"- {item}")
    lines.extend(["", "## Brain Context"])
    brain_context_lines = prep.get("brain_context_lines") or ["No active Brain Signal or portfolio blocker is attached to this prep."]
    for item in brain_context_lines:
        lines.append(f"- {item}")
    lines.extend(["", "## Blockers"])
    blockers = prep.get("blockers") or ["None."]
    for item in blockers:
        lines.append(f"- {item}")
    lines.extend(["", "## Commitments"])
    commitments = prep.get("commitments") or ["None."]
    for item in commitments:
        lines.append(f"- {item}")
    lines.extend(["", "## Needs"])
    needs = prep.get("needs") or ["None."]
    for item in needs:
        lines.append(f"- {item}")
    standup_sections = dict(prep.get("standup_sections") or {})
    if standup_sections:
        for title, key in (
            ("Signal", "signals_captured"),
            ("Work Produced", "content_produced"),
            ("Traction", "audience_response"),
            ("Opportunities", "opportunities_created"),
            ("Next Focus", "next_focus"),
        ):
            lines.extend(["", f"## {title}"])
            section_items = standup_sections.get(key) or ["None."]
            for item in section_items:
                lines.append(f"- {item}")
    else:
        lines.extend(["", "## Traction"])
        audience_response = prep.get("audience_response") or ["None."]
        for item in audience_response:
            lines.append(f"- {item}")
    lines.extend(["", "## Memory Promotions"])
    promotions = prep.get("memory_promotions") or []
    if not promotions:
        lines.append("- None.")
    else:
        for item in promotions:
            lines.append(f"- `{item['target']}`: {item['content']}")
    lines.extend(["", "## PM Recommendations"])
    pm_updates = prep.get("pm_updates") or []
    if not pm_updates:
        lines.append("- None.")
    else:
        for item in pm_updates:
            lines.append(f"- `{item['workspace_key']}`: {item['title']}")
    lines.extend(["", "## Strategy Context"])
    for item in prep.get("strategy_context_lines") or ["No strategy context loaded."]:
        lines.append(f"- {item}")
    lines.extend(["", "## Chronicle Highlights"])
    entries = prep.get("chronicle_entries") or []
    if not entries:
        lines.append("- None.")
    else:
        for item in entries:
            lines.append(f"- {_standup_chronicle_summary(item)}")
    lines.extend(["", "## Durable Memory Recall"])
    durable_memory = (prep.get("durable_memory_context") or {}).get("results") or []
    if not durable_memory:
        lines.append("- None.")
    else:
        for item in durable_memory:
            title = str(item.get("title") or "Untitled").strip()
            excerpt = str(item.get("excerpt") or "").strip()
            path_str = str(item.get("path") or "").strip()
            if excerpt:
                lines.append(f"- `{title}` ({path_str}): {excerpt}")
            else:
                lines.append(f"- `{title}` ({path_str})")
    lines.extend(["", "## Source Paths"])
    for item in prep.get("source_paths") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def _durable_memory_hints(
    workspace_key: str,
    workspace_display_name: str,
    chronicle_entries: list[dict[str, Any]],
) -> list[str]:
    hints: list[str] = [workspace_key, workspace_display_name]
    for entry in chronicle_entries:
        for field in (
            entry.get("summary"),
            *(entry.get("decisions") or [])[:1],
            *(entry.get("memory_promotions") or [])[:1],
            *(entry.get("learning_updates") or [])[:1],
            *(entry.get("pm_candidates") or [])[:1],
        ):
            if isinstance(field, str) and field.strip():
                hints.append(field)
    return hints


def main() -> int:
    maybe_reexec_with_workspace_venv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standup-kind", default="auto")
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--owner-agent", default="jean-claude")
    parser.add_argument("--chronicle-limit", type=int, default=8)
    parser.add_argument("--output-root", default=str(MEMORY_ROOT / "standup-prep"))
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--create-standup-entry", action="store_true")
    args = parser.parse_args()

    imports = _optional_backend_imports()
    resolved_standup_kind = (
        imports["default_standup_kind_for_workspace"](args.workspace_key)
        if args.standup_kind == "auto" and imports.get("default_standup_kind_for_workspace")
        else args.standup_kind
    )
    generated_at = _now()
    stamp = _stamp(generated_at)
    output_root = Path(args.output_root)
    json_path = output_root / resolved_standup_kind / f"{stamp}.json"
    md_path = output_root / resolved_standup_kind / f"{stamp}.md"

    registry = _read_registry()
    strategy_context = _load_strategy_context(args.workspace_key, registry)
    chronicle_entries = _filter_chronicle_entries(args.workspace_key, args.chronicle_limit)
    pm_context = _load_pm_context(imports, args.workspace_key, args.api_url)
    workspace_display_name = str(strategy_context.get("display_name") or args.workspace_key)
    workspace_label = _workspace_label(args.workspace_key, workspace_display_name)
    pm_snapshot = _build_pm_snapshot(pm_context, args.workspace_key, workspace_label)
    automation_context = _load_automation_context(imports)
    workspace_context = _workspace_context(args.workspace_key, registry)
    durable_memory_context = build_durable_memory_context(
        args.workspace_key,
        _durable_memory_hints(args.workspace_key, workspace_display_name, chronicle_entries),
    )
    fallback_watchdog = _load_fallback_watchdog_report()
    brain_context = build_brain_automation_context(signal_limit=5)
    brain_context_lines = [
        *portfolio_attention_lines(brain_context, limit=2),
        *workspace_brain_signal_lines(brain_context, args.workspace_key, limit=3),
        *source_intelligence_lines(brain_context, limit=1),
    ]
    memory_context = {
        "persistent_state_tail": _tail_text(resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/persistent_state.md")),
        "cron_prune_tail": _tail_text(resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/cron-prune.md")),
        "daily_briefs_tail": _tail_text(resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/daily-briefs.md")),
        "today_log_tail": _tail_text(
            resolve_snapshot_fallback_path(WORKSPACE_ROOT, f"memory/{datetime.now().astimezone():%Y-%m-%d}.md")
        ),
    }
    if workspace_context.get("available"):
        memory_context["workspace_briefing_tail"] = workspace_context.get("latest_briefing_tail", "")
        memory_context["workspace_execution_log_tail"] = workspace_context.get("execution_log_tail", "")

    blockers: list[str] = []
    commitments: list[str] = []
    needs: list[str] = []
    audience_response = _build_audience_response(workspace_context)
    pm_context_fallback_active = bool(pm_context.get("fallback_active"))
    pm_context_source = str(pm_context.get("source") or "").strip()
    pm_context_fallback_reason = str(pm_context.get("fallback_reason") or "").strip()
    automation_fallback_active = bool(automation_context.get("fallback_active"))
    automation_context_source = str(automation_context.get("source") or "").strip()
    automation_fallback_reason = str(automation_context.get("fallback_reason") or "").strip()
    if pm_context_fallback_active:
        blockers.append(
            "PM context used a fallback source"
            + (f" (`{pm_context_source}`)" if pm_context_source else "")
            + (
                f" because `{pm_context_fallback_reason}`."
                if pm_context_fallback_reason
                else "."
            )
        )
    if automation_fallback_active:
        blockers.append(
            "Automation context used a fallback source"
            + (f" (`{automation_context_source}`)" if automation_context_source else "")
            + (
                f" because `{automation_fallback_reason}`."
                if automation_fallback_reason
                else "."
            )
        )
    fallback_watchdog_active = bool(fallback_watchdog.get("active"))
    fallback_watchdog_count = int(fallback_watchdog.get("active_count") or 0)
    fallback_watchdog_headline = str(fallback_watchdog.get("headline") or "").strip()
    fallback_followup = dict(fallback_watchdog.get("followup_card") or {})
    if fallback_watchdog_active:
        blockers.append(
            fallback_watchdog_headline
            or f"Fallback watchdog reports {fallback_watchdog_count} active degraded source contract(s)."
        )
        followup_title = str(fallback_followup.get("title") or "").strip()
        if followup_title:
            needs.append(
                f"Review `{followup_title}` on the PM board and repair the degraded source contract before trusting downstream automation."
            )
        elif fallback_watchdog.get("report_path"):
            needs.append(
                f"Review `{fallback_watchdog['report_path']}` and repair the degraded source contract before trusting downstream automation."
            )
    if chronicle_entries:
        for entry in chronicle_entries:
            for item in entry.get("blockers") or []:
                normalized_blocker = _normalize_standup_signal_text(item)
                if normalized_blocker:
                    blockers.append(normalized_blocker)
        for entry in chronicle_entries:
            for item in entry.get("follow_ups") or []:
                normalized_follow_up = _normalize_standup_signal_text(item)
                if normalized_follow_up:
                    needs.append(normalized_follow_up)
    mismatch_count = int(
        automation_context.get("mismatch_count")
        or (automation_context.get("fallback") or {}).get("mismatch_count")
        or 0
    )
    action_required = int(
        automation_context.get("action_required_count")
        or (automation_context.get("fallback") or {}).get("action_required_count")
        or 0
    )
    if mismatch_count or action_required:
        blockers.append(
            f"Automation drift remains: mismatch_count={mismatch_count}, action_required_count={action_required}."
        )
    for card in pm_snapshot.get("cards") or []:
        status = str(card.get("status") or "ready")
        title = str(card.get("title") or "Untitled").strip()
        if status == "blocked":
            blockers.append(f"PM board marks `{title}` as blocked.")
        elif status == "review":
            commitments.append(f"Review `{title}` and decide whether it closes or returns to execution.")
        elif status == "in_progress":
            commitments.append(f"Keep `{title}` moving and bring the result back to the next standup.")
        elif status == "queued":
            commitments.append(f"Jean-Claude should open the SOP for `{title}` and move it into execution.")
        elif status == "ready":
            commitments.append(f"Decide whether `{title}` is the next board item to queue.")
    if not pm_context.get("available"):
        needs.append("PM board is not reachable from the current runtime; treat PM updates as recommendations only.")
    if args.workspace_key != "shared_ops" and not workspace_context.get("available"):
        blockers.append(f"{workspace_label} has no local artifact root yet.")
    if workspace_context.get("latest_briefing_path") and args.workspace_key != "shared_ops":
        commitments.append("Bring the latest workspace briefing into the next standup and decide the next move from it.")
    if workspace_context.get("execution_log_path"):
        commitments.append("Use the workspace execution log to confirm what actually shipped before adding new work.")
    if audience_response:
        commitments.append("Review the latest public audience-feedback snapshot before changing narrative direction.")

    memory_promotions = _build_promotions(chronicle_entries, args.workspace_key)
    pm_updates_blocked_reason: str | None = None
    if pm_snapshot.get("available"):
        pm_updates = _build_pm_updates(chronicle_entries, args.workspace_key, args.owner_agent, pm_snapshot)
    else:
        pm_updates = []
        pm_updates_blocked_reason = "pm_snapshot_unavailable"
    if resolved_standup_kind == "saturday_vision":
        pm_updates = []
        needs.append("Keep Saturday Vision Sync strategy-only unless a conclusion clearly deserves PM promotion.")
    else:
        for item in pm_updates[:3]:
            title = str(item.get("title") or "").strip()
            if title:
                needs.append(f"Decide whether to create or queue `{title}` from current Chronicle signal.")
    artifact_deltas = _build_artifact_deltas(chronicle_entries, automation_context, workspace_context, memory_context)
    for item in reversed(brain_context_lines[:5]):
        artifact_deltas.insert(0, f"Brain context: {item}")
    if pm_context_fallback_active:
        artifact_deltas.insert(
            0,
            "PM context fallback: "
            + (
                f"using `{pm_context_source}` because `{pm_context_fallback_reason}`."
                if pm_context_source and pm_context_fallback_reason
                else "the primary PM backend contract was unavailable."
            ),
        )
    if automation_fallback_active:
        artifact_deltas.insert(
            0,
            "Automation context fallback: "
            + (
                f"using `{automation_context_source}` because `{automation_fallback_reason}`."
                if automation_context_source and automation_fallback_reason
                else "the primary automation mismatch contract was unavailable."
            ),
        )
    if fallback_watchdog_active:
        artifact_deltas.insert(
            0,
            "Fallback watchdog: "
            + (
                fallback_watchdog_headline
                or f"{fallback_watchdog_count} degraded source contract(s) are active."
            ),
        )
        report_path = str(fallback_watchdog.get("report_path") or "").strip()
        if report_path:
            artifact_deltas.insert(1, f"Fallback watchdog report: {report_path}")
    strategy_context_lines = _strategy_lines(strategy_context)
    blockers = _filter_resolved_workspace_root_blockers(
        blockers,
        workspace_key=args.workspace_key,
        registry=registry,
        workspace_context=workspace_context,
    )
    agenda = _build_agenda(pm_snapshot, pm_updates, blockers, args.workspace_key, strategy_context, resolved_standup_kind)

    blockers = _dedupe_strings(blockers, limit=8)
    commitments = _dedupe_strings(commitments, limit=8)
    needs = _dedupe_strings(needs, limit=8)
    standup_sections = _build_standup_sections(
        args.workspace_key,
        chronicle_entries,
        workspace_context,
        pm_snapshot,
        audience_response,
        needs,
    )

    summary_parts = []
    if pm_snapshot.get("available"):
        summary_parts.append(
            f"PM board shows {pm_snapshot.get('open_count', 0)} open scoped card(s) and sets the meeting agenda first."
        )
    else:
        summary_parts.append("PM board is unavailable from this runtime, so the meeting stays recommendation-only.")
    if chronicle_entries:
        summary_parts.append(f"Chronicle contributes {len(chronicle_entries)} recent high-signal chunk(s).")
    if durable_memory_context.get("available"):
        summary_parts.append(
            f"Durable memory retrieval surfaced {durable_memory_context.get('result_count', 0)} older markdown artifact(s)."
        )
    if pm_context_fallback_active:
        summary_parts.append(
            "PM context is currently running on a fallback source"
            + (f" (`{pm_context_source}`)." if pm_context_source else ".")
        )
    if automation_fallback_active:
        summary_parts.append(
            "Automation context is currently running on a fallback source"
            + (f" (`{automation_context_source}`)." if automation_context_source else ".")
        )
    if fallback_watchdog_active:
        summary_parts.append(
            fallback_watchdog_headline
            or f"Fallback watchdog reports {fallback_watchdog_count} active degraded source contract(s)."
        )
    if brain_context_lines:
        summary_parts.append("Brain context contributes portfolio snapshot, signal review, and source intelligence state.")
    if mismatch_count == 0 and action_required == 0:
        summary_parts.append("Automation layer is currently clean.")
    if args.workspace_key != "shared_ops":
        if workspace_context.get("latest_briefing_path"):
            summary_parts.append(f"{workspace_label} artifacts are available to support board decisions.")
        else:
            summary_parts.append(f"{workspace_label} artifact lane is still sparse and needs its first recurring meeting cadence.")
        if audience_response:
            summary_parts.append("Public audience response is available to pressure-test narrative quality before the next content move.")
    if strategy_context_lines:
        summary_parts.append(strategy_context_lines[0])

    for item in pm_updates:
        payload = dict(item.get("payload") or {})
        payload.update(
            {
                "strategy_context": {
                    "display_name": strategy_context.get("display_name"),
                    "default_routing": strategy_context.get("default_routing"),
                    "charter_path": strategy_context.get("charter_path"),
                    "identity_path": strategy_context.get("identity_path"),
                    "soul_path": strategy_context.get("soul_path"),
                    "user_path": strategy_context.get("user_path"),
                    "lane_boundary": strategy_context.get("lane_boundary"),
                    "trust_constraint": strategy_context.get("trust_constraint"),
                    "execution_posture": strategy_context.get("execution_posture"),
                    "inferred_brief_path": strategy_context.get("inferred_brief_path"),
                }
            }
        )
        item["payload"] = payload

    prep = {
        "schema_version": "standup_prep/v2",
        "prep_id": str(uuid.uuid4()),
        "generated_at": _iso(generated_at),
        "standup_kind": resolved_standup_kind,
        "workspace_key": args.workspace_key,
        "owner_agent": args.owner_agent,
        "summary": " ".join(summary_parts) or "Standup prep generated.",
        "agenda": agenda,
        "artifact_deltas": artifact_deltas,
        "blockers": blockers,
        "commitments": commitments,
        "needs": needs,
        "audience_response": audience_response,
        "standup_sections": standup_sections,
        "chronicle_entries": chronicle_entries,
        "durable_memory_context": durable_memory_context,
        "fallback_watchdog": fallback_watchdog,
        "brain_context": brain_context,
        "brain_context_lines": brain_context_lines,
        "memory_context": memory_context,
        "workspace_context": workspace_context,
        "strategy_context": strategy_context,
        "strategy_context_lines": strategy_context_lines,
        "pm_context": pm_context,
        "pm_snapshot": pm_snapshot,
        "automation_context": automation_context,
        "memory_promotions": memory_promotions,
        "pm_updates": pm_updates,
        "pm_updates_blocked_reason": pm_updates_blocked_reason,
        "standup_payload": {
            "owner": args.owner_agent,
            "status": "prepared",
            "blockers": blockers,
            "commitments": commitments,
            "needs": needs,
            "source": "codex-chronicle-standup-prep",
            "conversation_path": str(md_path),
            "workspace_key": args.workspace_key,
            "payload": {
                "standup_kind": resolved_standup_kind,
                "summary": " ".join(summary_parts) or "Standup prep generated.",
                "prep_json_path": str(json_path),
                "chronicle_path": str(CODEX_CHRONICLE_PATH),
                "durable_memory_context": durable_memory_context,
                "fallback_watchdog": fallback_watchdog,
                "brain_context": brain_context,
                "agenda": agenda,
                "artifact_deltas": artifact_deltas,
                "audience_response": audience_response,
                "standup_sections": standup_sections,
                "pm_snapshot": pm_snapshot,
                "strategy_context": strategy_context,
            },
        },
        "source_paths": list(
            dict.fromkeys(
                [
                    str(CODEX_CHRONICLE_PATH),
                    str(resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/persistent_state.md")),
                    str(resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/cron-prune.md")),
                    str(resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/daily-briefs.md")),
                    *([str(INFERRED_BRIEF_PATH)] if INFERRED_BRIEF_PATH.exists() else []),
                    *([strategy_context["charter_path"]] if strategy_context.get("charter_path") else []),
                    *([strategy_context["identity_path"]] if strategy_context.get("identity_path") else []),
                    *([strategy_context["soul_path"]] if strategy_context.get("soul_path") else []),
                    *([strategy_context["user_path"]] if strategy_context.get("user_path") else []),
                    *([pm_context["source_ref"]] if pm_context.get("source_ref") else []),
                    *([automation_context["source_ref"]] if automation_context.get("source_ref") else []),
                    *(fallback_watchdog.get("source_paths") or []),
                    *(brain_context.get("source_paths") or []),
                    *durable_memory_context.get("source_paths", []),
                    *workspace_context.get("source_paths", []),
                ]
            )
        ),
    }

    if args.create_standup_entry and imports.get("create_standup") and imports.get("StandupCreate"):
        try:
            standup_payload = imports["StandupCreate"](**prep["standup_payload"])
            entry = imports["create_standup"](standup_payload)
            prep["created_standup"] = entry.model_dump(mode="json")
        except Exception as exc:
            prep["created_standup_error"] = str(exc)

    _write_json(json_path, prep)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_build_markdown(prep), encoding="utf-8")
    print(prep["summary"])
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
