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


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
CODEX_CHRONICLE_PATH = MEMORY_ROOT / "codex_session_handoff.jsonl"
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


def _workspace_root(workspace_key: str, registry: dict[str, dict[str, Any]]) -> Path | None:
    if workspace_key == "shared_ops":
        return WORKSPACE_ROOT / "workspaces" / "shared-ops"
    item = registry.get(workspace_key) or {}
    configured = item.get("filesystem_path")
    if isinstance(configured, str) and configured.strip():
        return Path(configured)
    return None


def _latest_file(directory: Path, suffix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.glob(f"*{suffix}"))
    return matches[-1] if matches else None


def _workspace_context(workspace_key: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = _workspace_root(workspace_key, registry)
    if root is None or not root.exists():
        return {"available": False, "workspace_root": None, "source_paths": []}
    latest_sop = _latest_file(root / "dispatch", ".json")
    latest_briefing = _latest_file(root / "briefings", ".md")
    execution_log = root / "memory" / "execution_log.md"
    source_paths = [str(path) for path in (latest_sop, latest_briefing, execution_log if execution_log.exists() else None) if path]
    return {
        "available": True,
        "workspace_root": str(root),
        "latest_sop_path": str(latest_sop) if latest_sop else None,
        "latest_briefing_path": str(latest_briefing) if latest_briefing else None,
        "execution_log_path": str(execution_log) if execution_log.exists() else None,
        "latest_sop_tail": _tail_text(latest_sop, max_chars=1200) if latest_sop else "",
        "latest_briefing_tail": _tail_text(latest_briefing, max_chars=1200) if latest_briefing else "",
        "execution_log_tail": _tail_text(execution_log, max_chars=1200) if execution_log.exists() else "",
        "source_paths": source_paths,
    }


def _workspace_display_name(workspace_key: str, registry: dict[str, dict[str, Any]]) -> str:
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


def _load_strategy_context(workspace_key: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    display_name = _workspace_display_name(workspace_key, registry)
    charter_path: Path | None = None
    workspace_root = _workspace_root(workspace_key, registry)
    if workspace_root is not None:
        candidate = workspace_root / "CHARTER.md"
        if candidate.exists():
            charter_path = candidate
    charter_excerpt = _compact_markdown_section(_read_text(charter_path), max_lines=18) if charter_path else ""

    inferred_heading = {
        "linkedin-os": "FEEZIE OS",
        "fusion-os": "Fusion OS",
        "easyoutfitapp": "EasyOutfitApp",
        "ai-swag-store": "AI Swag Store",
        "agc": "AGC",
        "shared_ops": "Executive Interpretation Rule",
    }.get(workspace_key, display_name)
    inferred_excerpt = ""
    if INFERRED_BRIEF_PATH.exists():
        inferred_text = _read_text(INFERRED_BRIEF_PATH)
        inferred_excerpt = _compact_markdown_section(_extract_markdown_section(inferred_text, inferred_heading), max_lines=18)

    default_routing = "Strong signal should usually go to canonical memory plus standup before PM."
    if workspace_key == "linkedin-os":
        default_routing = "FEEZIE signal should usually go to canonical memory plus executive standup first, then persona canon or PM when justified."
    return {
        "workspace_key": workspace_key,
        "display_name": display_name,
        "charter_path": str(charter_path) if charter_path else None,
        "charter_excerpt": charter_excerpt,
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
        summary = str(latest.get("summary") or "").strip()
        if summary:
            deltas.append(f"Chronicle: {summary}")
        for item in latest.get("decisions") or []:
            deltas.append(f"Chronicle decision: {item}")
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
    if workspace_context.get("latest_sop_path"):
        deltas.append(f"Latest SOP: {workspace_context['latest_sop_path']}")
    if memory_context.get("daily_briefs_tail"):
        deltas.append("Daily brief is populated and ready for standup review.")
    if memory_context.get("cron_prune_tail"):
        deltas.append("Pruning cycle history is available for memory continuity checks.")
    return _dedupe_strings(deltas, limit=8)


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
    if workspace_key == "linkedin-os":
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
    url = f"{api_url.rstrip('/')}/api/pm/cards?limit=100"
    payload = _fetch_api_json(url)
    rows = payload if isinstance(payload, list) else payload.get("cards") or []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_workspace = _workspace_key_from_card(row)
        if workspace_key != "shared_ops" and row_workspace not in {workspace_key, "shared_ops"}:
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
    return {"available": True, "cards": filtered[:25], "card_count": len(filtered), "source": "pm_api"}


def _load_pm_context(imports: dict[str, Any], workspace_key: str, api_url: str) -> dict[str, Any]:
    list_cards = imports.get("list_cards")
    if list_cards is None:
        try:
            return _load_pm_context_from_api(workspace_key, api_url)
        except Exception as exc:
            return {
                "available": False,
                "error": f"{imports.get('pm_error', 'pm unavailable')}; api fallback failed: {exc}",
                "cards": [],
                "card_count": 0,
            }
    try:
        rows = [item.model_dump(mode="json") for item in list_cards(limit=100)]
    except Exception as exc:
        try:
            return _load_pm_context_from_api(workspace_key, api_url)
        except Exception as api_exc:
            return {"available": False, "error": f"{exc}; api fallback failed: {api_exc}", "cards": [], "card_count": 0}

    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_workspace = _workspace_key_from_card(row)
        if workspace_key != "shared_ops" and row_workspace not in {workspace_key, "shared_ops"}:
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
    return {"available": True, "cards": filtered[:25], "card_count": len(filtered)}


def _load_automation_context(imports: dict[str, Any]) -> dict[str, Any]:
    build_mismatch_report = imports.get("build_mismatch_report")
    if build_mismatch_report is not None:
        try:
            payload = build_mismatch_report().model_dump(mode="json")
            payload["available"] = True
            return payload
        except Exception as exc:
            return {"available": False, "error": str(exc), "fallback": _parse_delivery_hygiene_metrics()}
    jobs: list[dict[str, Any]] = []
    if JOBS_JSON.exists():
        try:
            payload = _read_json(JOBS_JSON)
            jobs = [item for item in payload.get("jobs") or [] if isinstance(item, dict)]
        except Exception:
            jobs = []
    return {
        "available": False,
        "error": imports.get("automation_error", "automation unavailable"),
        "job_count": len(jobs),
        "job_names": [str(item.get("name") or "Unnamed") for item in jobs[:20]],
        "fallback": _parse_delivery_hygiene_metrics(),
    }


def _filter_chronicle_entries(workspace_key: str, max_items: int) -> list[dict[str, Any]]:
    entries = _read_jsonl_tail(CODEX_CHRONICLE_PATH, max_items=max_items)
    filtered: list[dict[str, Any]] = []
    for item in entries:
        entry_workspace = str(item.get("workspace_key") or "shared_ops")
        if workspace_key != "shared_ops" and entry_workspace not in {workspace_key, "shared_ops"}:
            continue
        filtered.append(item)
    return filtered


def _normalize_memory_content(content: str) -> str:
    lowered = content.lower()
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
    inferred_excerpt = str(strategy_context.get("inferred_excerpt") or "").strip()
    if charter_excerpt:
        lines.append(f"Charter loaded for `{strategy_context.get('display_name')}`.")
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
            lines.append(f"- {item.get('summary')}")
    lines.extend(["", "## Source Paths"])
    for item in prep.get("source_paths") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
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
    memory_context = {
        "persistent_state_tail": _tail_text(MEMORY_ROOT / "persistent_state.md"),
        "cron_prune_tail": _tail_text(MEMORY_ROOT / "cron-prune.md"),
        "daily_briefs_tail": _tail_text(MEMORY_ROOT / "daily-briefs.md"),
        "today_log_tail": _tail_text(MEMORY_ROOT / f"{datetime.now().astimezone():%Y-%m-%d}.md"),
    }
    if workspace_context.get("available"):
        memory_context["workspace_briefing_tail"] = workspace_context.get("latest_briefing_tail", "")
        memory_context["workspace_execution_log_tail"] = workspace_context.get("execution_log_tail", "")

    blockers: list[str] = []
    commitments: list[str] = []
    needs: list[str] = []
    if chronicle_entries:
        blockers.extend(item for entry in chronicle_entries for item in (entry.get("blockers") or []))
        needs.extend(item for entry in chronicle_entries for item in (entry.get("follow_ups") or []))
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
    strategy_context_lines = _strategy_lines(strategy_context)
    agenda = _build_agenda(pm_snapshot, pm_updates, blockers, args.workspace_key, strategy_context, resolved_standup_kind)

    blockers = _dedupe_strings(blockers, limit=8)
    commitments = _dedupe_strings(commitments, limit=8)
    needs = _dedupe_strings(needs, limit=8)

    summary_parts = []
    if pm_snapshot.get("available"):
        summary_parts.append(
            f"PM board shows {pm_snapshot.get('open_count', 0)} open scoped card(s) and sets the meeting agenda first."
        )
    else:
        summary_parts.append("PM board is unavailable from this runtime, so the meeting stays recommendation-only.")
    if chronicle_entries:
        summary_parts.append(f"Chronicle contributes {len(chronicle_entries)} recent high-signal chunk(s).")
    if mismatch_count == 0 and action_required == 0:
        summary_parts.append("Automation layer is currently clean.")
    if args.workspace_key != "shared_ops":
        if workspace_context.get("latest_briefing_path"):
            summary_parts.append(f"{workspace_label} artifacts are available to support board decisions.")
        else:
            summary_parts.append(f"{workspace_label} artifact lane is still sparse and needs its first recurring meeting cadence.")
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
        "chronicle_entries": chronicle_entries,
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
                "prep_json_path": str(json_path),
                "chronicle_path": str(CODEX_CHRONICLE_PATH),
                "agenda": agenda,
                "artifact_deltas": artifact_deltas,
                "pm_snapshot": pm_snapshot,
                "strategy_context": strategy_context,
            },
        },
        "source_paths": [
            str(CODEX_CHRONICLE_PATH),
            str(MEMORY_ROOT / "persistent_state.md"),
            str(MEMORY_ROOT / "cron-prune.md"),
            str(MEMORY_ROOT / "daily-briefs.md"),
            *( [str(INFERRED_BRIEF_PATH)] if INFERRED_BRIEF_PATH.exists() else [] ),
            *([strategy_context["charter_path"]] if strategy_context.get("charter_path") else []),
            *workspace_context.get("source_paths", []),
        ],
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
