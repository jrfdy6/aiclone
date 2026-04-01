#!/usr/bin/env python3
"""Jean-Claude MVP runner.

Builds a cross-workspace operating review from local files and optional backend
services, then writes:
- runner input bundle
- structured recommendations
- markdown memo
- JSONL ledger entry

This MVP is intentionally file-first. It degrades cleanly when DB-backed
backend services are unavailable in the current Python environment.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
OPENCLAW_ROOT = Path("/Users/neo/.openclaw")
JOBS_JSON = OPENCLAW_ROOT / "cron" / "jobs.json"
REGISTRY_PATH = MEMORY_ROOT / "workspace_registry.json"
CODEX_HANDOFF_PATH = MEMORY_ROOT / "codex_session_handoff.jsonl"

RUNNER_ID = "jean-claude"
DEFAULT_WORKSPACE_SCOPE = [
    "linkedin-os",
    "fusion-os",
    "easyoutfitapp",
    "ai-swag-store",
    "agc",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    return str(value)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=_json_default) + "\n")


def _read_jsonl_tail(path: Path, *, max_items: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines: deque[str] = deque(maxlen=max_items)
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                lines.append(line)

    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _tail_text(path: Path, *, max_chars: int = 2400) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return text[-max_chars:]


def _latest_report(pattern: str) -> Path | None:
    matches = sorted((MEMORY_ROOT / "reports").glob(pattern))
    return matches[-1] if matches else None


def _parse_delivery_hygiene_metrics() -> dict[str, Any]:
    report = _latest_report("openclaw_cron_delivery_hygiene_*.md")
    if report is None:
        return {}
    text = report.read_text(encoding="utf-8", errors="ignore")
    metrics: dict[str, Any] = {"source": str(report)}
    for key in ("mismatch_count", "action_required_count"):
        match = re.search(rf"{key}\s*=\s*(\d+)", text)
        if match:
            metrics[key] = int(match.group(1))
    return metrics


def _load_registry() -> list[dict[str, Any]]:
    if REGISTRY_PATH.exists():
        payload = _read_json(REGISTRY_PATH)
        workspaces = payload.get("workspaces")
        if isinstance(workspaces, list):
            return [item for item in workspaces if isinstance(item, dict)]
    return [
        {
            "workspace_key": key,
            "display_name": key,
            "filesystem_path": None,
            "status": "planned",
            "notes": "Workspace registry fallback entry.",
        }
        for key in DEFAULT_WORKSPACE_SCOPE
    ]


def _workspace_key_from_card(card: dict[str, Any]) -> str:
    payload = card.get("payload") or {}
    for key in ("workspace_key", "workspace", "belongs_to_workspace"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "shared_ops"


def _optional_backend_imports() -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {}
    try:
        from app.services.pm_card_service import list_cards  # type: ignore

        loaded["list_cards"] = list_cards
    except Exception as exc:  # pragma: no cover - environment dependent
        loaded["pm_error"] = str(exc)
    try:
        from app.services.workspace_snapshot_store import list_snapshot_payloads  # type: ignore

        loaded["list_snapshot_payloads"] = list_snapshot_payloads
    except Exception as exc:  # pragma: no cover - environment dependent
        loaded["snapshot_error"] = str(exc)
    try:
        from app.services.automation_mismatch_service import build_mismatch_report  # type: ignore

        loaded["build_mismatch_report"] = build_mismatch_report
    except Exception as exc:  # pragma: no cover - environment dependent
        loaded["automation_error"] = str(exc)
    return loaded


def _load_pm_context(imports: dict[str, Any], workspace_scope: list[str]) -> dict[str, Any]:
    list_cards = imports.get("list_cards")
    if list_cards is None:
        return {
            "available": False,
            "error": imports.get("pm_error", "pm_card_service unavailable"),
            "card_count": 0,
            "cards": [],
            "by_status": {},
            "by_workspace": {},
        }
    try:
        cards = [card.model_dump(mode="json") for card in list_cards(limit=100)]
    except Exception as exc:  # pragma: no cover - runtime dependent
        return {
            "available": False,
            "error": str(exc),
            "card_count": 0,
            "cards": [],
            "by_status": {},
            "by_workspace": {},
        }

    by_status = Counter()
    by_workspace = Counter()
    normalized_cards: list[dict[str, Any]] = []
    allowed = set(workspace_scope) | {"shared_ops"}
    for card in cards:
        status = str(card.get("status") or "todo")
        workspace_key = _workspace_key_from_card(card)
        if workspace_key not in allowed:
            workspace_key = "shared_ops"
        by_status[status] += 1
        by_workspace[workspace_key] += 1
        normalized_cards.append(
            {
                "id": card.get("id"),
                "title": card.get("title"),
                "owner": card.get("owner"),
                "status": status,
                "workspace_key": workspace_key,
                "updated_at": card.get("updated_at"),
            }
        )

    return {
        "available": True,
        "card_count": len(normalized_cards),
        "cards": normalized_cards[:25],
        "by_status": dict(by_status),
        "by_workspace": dict(by_workspace),
    }


def _load_automation_context(imports: dict[str, Any]) -> dict[str, Any]:
    build_mismatch_report = imports.get("build_mismatch_report")
    if build_mismatch_report is not None:
        try:
            report = build_mismatch_report().model_dump(mode="json")
            report["available"] = True
            return report
        except Exception as exc:  # pragma: no cover - runtime dependent
            return {
                "available": False,
                "error": str(exc),
                "fallback": _parse_delivery_hygiene_metrics(),
            }

    jobs: list[dict[str, Any]] = []
    if JOBS_JSON.exists():
        try:
            payload = _read_json(JOBS_JSON)
            jobs = payload.get("jobs") or []
        except Exception:
            jobs = []
    return {
        "available": False,
        "error": imports.get("automation_error", "automation mismatch service unavailable"),
        "job_count": len(jobs),
        "job_names": [str(job.get("name") or "Unnamed") for job in jobs[:20] if isinstance(job, dict)],
        "fallback": _parse_delivery_hygiene_metrics(),
    }


def _scan_workspace(path_value: Any, entry: dict[str, Any], imports: dict[str, Any]) -> dict[str, Any]:
    path = Path(path_value) if isinstance(path_value, str) and path_value else None
    result: dict[str, Any] = {
        "workspace_key": entry.get("workspace_key"),
        "display_name": entry.get("display_name"),
        "future_name": entry.get("future_name"),
        "status": entry.get("status") or "planned",
        "filesystem_path": str(path) if path else None,
        "path_exists": bool(path and path.exists()),
        "notes": entry.get("notes"),
    }
    if not path or not path.exists():
        result["state"] = "not_instantiated"
        return result

    readme = path / "README.md"
    backlog = path / "backlog.md"
    docs_dir = path / "docs"
    analytics_dir = path / "analytics"
    result.update(
        {
            "state": "available",
            "has_readme": readme.exists(),
            "has_backlog": backlog.exists(),
            "docs_count": len(list(docs_dir.glob("*.md"))) if docs_dir.exists() else 0,
            "analytics_count": len(list(analytics_dir.glob("*"))) if analytics_dir.exists() else 0,
            "readme_excerpt": _tail_text(readme, max_chars=600),
            "backlog_excerpt": _tail_text(backlog, max_chars=600),
        }
    )

    list_snapshot_payloads = imports.get("list_snapshot_payloads")
    if list_snapshot_payloads is not None:
        try:
            payloads = list_snapshot_payloads(entry["workspace_key"])
            result["snapshot_types"] = sorted(payloads.keys())
        except Exception as exc:  # pragma: no cover
            result["snapshot_error"] = str(exc)
    return result


def _load_workspace_context(imports: dict[str, Any], workspace_scope: list[str]) -> dict[str, Any]:
    registry = [item for item in _load_registry() if item.get("workspace_key") in workspace_scope]
    scanned = [_scan_workspace(item.get("filesystem_path"), item, imports) for item in registry]
    by_state = Counter(str(item.get("state") or item.get("status") or "unknown") for item in scanned)
    return {
        "registry": registry,
        "workspaces": scanned,
        "by_state": dict(by_state),
    }


def _load_codex_handoff_context() -> dict[str, Any]:
    entries = _read_jsonl_tail(CODEX_HANDOFF_PATH, max_items=8)
    recent_entries: list[dict[str, Any]] = []
    for item in entries:
        recent_entries.append(
            {
                "created_at": item.get("created_at"),
                "source": item.get("source"),
                "author_agent": item.get("author_agent"),
                "workspace_key": item.get("workspace_key"),
                "scope": item.get("scope"),
                "summary": item.get("summary"),
                "decisions": item.get("decisions") or [],
                "blockers": item.get("blockers") or [],
                "follow_ups": item.get("follow_ups") or [],
                "importance": item.get("importance"),
                "tags": item.get("tags") or [],
                "signal_types": item.get("signal_types") or [],
                "project_updates": item.get("project_updates") or [],
                "learning_updates": item.get("learning_updates") or [],
                "identity_signals": item.get("identity_signals") or [],
                "mindset_signals": item.get("mindset_signals") or [],
                "memory_promotions": item.get("memory_promotions") or [],
                "pm_candidates": item.get("pm_candidates") or [],
            }
        )
    return {
        "available": bool(recent_entries),
        "path": str(CODEX_HANDOFF_PATH),
        "recent_entries": recent_entries,
    }


def _load_previous_run(ledger_path: Path) -> dict[str, Any] | None:
    if not ledger_path.exists():
        return None
    last_line = ""
    with ledger_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        return None
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _build_input_bundle(args: argparse.Namespace, imports: dict[str, Any], ledger_path: Path, run_id: str) -> dict[str, Any]:
    workspace_scope = args.workspace or DEFAULT_WORKSPACE_SCOPE
    pm_context = _load_pm_context(imports, workspace_scope)
    automation_context = _load_automation_context(imports)
    workspace_context = _load_workspace_context(imports, workspace_scope)
    codex_handoff_context = _load_codex_handoff_context()
    previous_run = _load_previous_run(ledger_path)
    return {
        "schema_version": "runner_input/v1",
        "run_id": run_id,
        "runner_id": RUNNER_ID,
        "owner_agent": RUNNER_ID,
        "scope": "shared_ops",
        "workspace_scope": workspace_scope,
        "primary_workspace_key": None,
        "goal": args.goal,
        "run_mode": "scheduled",
        "time_budget_minutes": args.time_budget_minutes,
        "model": args.model,
        "dry_run": True,
        "allowed_paths": [str(WORKSPACE_ROOT)],
        "allowed_command_prefixes": ["git status", "rg", "sed", "cat"],
        "pm_context": pm_context,
        "automation_context": automation_context,
        "codex_handoff_context": codex_handoff_context,
        "codex_chronicle_context": codex_handoff_context,
        "workspace_context": workspace_context,
        "previous_run_context": previous_run or {},
        "role_payload": {
            "portfolio_health": "unknown",
            "workspaces_reviewed": workspace_scope,
        },
    }


def _priority_workspace(bundle: dict[str, Any]) -> str | None:
    pm_by_workspace = (bundle.get("pm_context") or {}).get("by_workspace") or {}
    workspaces = (bundle.get("workspace_context") or {}).get("workspaces") or []
    scores: list[tuple[int, str]] = []
    for item in workspaces:
        key = str(item.get("workspace_key") or "")
        score = 0
        if item.get("state") == "available":
            score += 10
        if item.get("status") == "active":
            score += 5
        score += int(pm_by_workspace.get(key, 0))
        if item.get("workspace_key") == "linkedin-os":
            score += 2
        scores.append((score, key))
    scores = [item for item in scores if item[1]]
    if not scores:
        return None
    scores.sort(reverse=True)
    return scores[0][1]


def _build_recommendations(bundle: dict[str, Any]) -> dict[str, Any]:
    workspace_items = (bundle.get("workspace_context") or {}).get("workspaces") or []
    automation_context = bundle.get("automation_context") or {}
    codex_handoff_context = bundle.get("codex_handoff_context") or {}
    pm_context = bundle.get("pm_context") or {}
    workspaces_touched = [str(item.get("workspace_key")) for item in workspace_items if item.get("workspace_key")]

    blockers: list[str] = []
    dependencies: list[str] = []
    next_actions: list[str] = []
    escalations: list[dict[str, Any]] = []
    artifacts_written: list[dict[str, Any]] = []
    pm_updates: list[dict[str, Any]] = []
    memory_promotions: list[dict[str, Any]] = []

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
            f"Maintenance layer still has mismatch_count={mismatch_count}, action_required_count={action_required}."
        )
        pm_updates.append(
            {
                "action": "recommend_only",
                "pm_card_id": None,
                "workspace_key": "shared_ops",
                "scope": "shared_ops",
                "owner_agent": RUNNER_ID,
                "title": "Review OpenClaw maintenance mismatches before scaling local runners",
                "status": "todo",
                "reason": "Jean-Claude runner detected unresolved automation health drift.",
                "payload": {"priority": "high", "source_runner": RUNNER_ID},
            }
        )

    if not pm_context.get("available"):
        dependencies.append("PM board service is not available in the current runner environment.")
        next_actions.append("Wire Jean-Claude runner into a DB-enabled PM path or expose a stable PM API for local runner use.")

    if not codex_handoff_context.get("available"):
        dependencies.append("No Codex handoff entries were observed in canonical memory.")
        next_actions.append(
            "Start writing major Codex decisions, blockers, and follow-ups into memory/codex_session_handoff.jsonl so OpenClaw brain jobs read current truth."
        )
    else:
        for entry in codex_handoff_context.get("recent_entries") or []:
            for content in entry.get("memory_promotions") or []:
                memory_promotions.append(
                    {
                        "target": "persistent_state",
                        "workspace_key": str(entry.get("workspace_key") or "shared_ops"),
                        "reason": "Recent Chronicle entry marked this signal as durable.",
                        "content": content,
                    }
                )

    highest_priority_workspace = _priority_workspace(bundle)
    for item in workspace_items:
        key = str(item.get("workspace_key") or "")
        if item.get("state") == "not_instantiated":
            next_actions.append(f"Bootstrap a filesystem root and baseline docs for `{key}` before assigning a dedicated subagent.")
            pm_updates.append(
                {
                    "action": "recommend_only",
                    "pm_card_id": None,
                    "workspace_key": key,
                    "scope": "workspace",
                    "owner_agent": RUNNER_ID,
                    "title": f"Bootstrap {key} workspace root",
                    "status": "todo",
                    "reason": "Workspace is planned but not materially instantiated on disk.",
                    "payload": {"priority": "medium", "source_runner": RUNNER_ID},
                }
            )
        elif key == "linkedin-os":
            next_actions.append("Keep FEEZIE OS operational through the current LinkedIn lane while expanding the broader public system carefully.")
        if key == highest_priority_workspace:
            next_actions.append(f"Treat `{key}` as the current highest-priority workspace until clearer PM signals exist.")

    summary_parts = []
    if highest_priority_workspace:
        summary_parts.append(f"Highest-priority workspace right now is `{highest_priority_workspace}`.")
    if mismatch_count == 0 and action_required == 0:
        summary_parts.append("OpenClaw maintenance layer is currently clean.")
    if any(item.get("state") == "not_instantiated" for item in workspace_items):
        planned = [item["workspace_key"] for item in workspace_items if item.get("state") == "not_instantiated"]
        summary_parts.append(f"Several workspaces are still planned-only on disk: {', '.join(planned)}.")
    if not summary_parts:
        summary_parts.append("Jean-Claude completed a portfolio review with no critical issues detected.")

    role_payload = {
        "portfolio_health": "stable" if mismatch_count == 0 else "needs_attention",
        "workspaces_reviewed": workspaces_touched,
        "highest_priority_workspace": highest_priority_workspace,
        "operating_recommendations": next_actions[:5],
    }

    if any(item.get("state") == "not_instantiated" for item in workspace_items):
        escalations.append(
            {
                "target_agent": "neo",
                "kind": "workspace_bootstrap",
                "workspace_key": "shared_ops",
                "reason": "Not all planned workspaces have been materially instantiated.",
                "recommended_action": "Decide which workspace roots should be created first before handing work to dedicated subagents.",
                "severity": "medium",
            }
        )
    if highest_priority_workspace == "linkedin-os":
        escalations.append(
            {
                "target_agent": "yoda",
                "kind": "strategy_review",
                "workspace_key": "linkedin-os",
                "reason": "FEEZIE OS remains the strongest active workspace and is currently expressed through the linkedin-os lane.",
                "recommended_action": "Review whether current workspace effort is aligned with the FEEZIE OS trajectory.",
                "severity": "medium",
            }
        )

    return {
        "schema_version": "runner_output/v1",
        "run_id": bundle["run_id"],
        "runner_id": RUNNER_ID,
        "owner_agent": RUNNER_ID,
        "status": "ok",
        "scope": "shared_ops",
        "workspaces_touched": workspaces_touched,
        "summary": " ".join(summary_parts),
        "artifacts_written": artifacts_written,
        "memory_promotions": memory_promotions[:8],
        "pm_updates": pm_updates,
        "blockers": blockers,
        "dependencies": dependencies,
        "recommended_next_actions": next_actions[:8],
        "escalations": escalations,
        "role_payload": role_payload,
    }


def _write_markdown_memo(path: Path, bundle: dict[str, Any], output: dict[str, Any]) -> None:
    lines = [
        f"# Jean-Claude Ops Review - {_iso(_now())}",
        "",
        "## Summary",
        output["summary"],
        "",
        "## Workspaces Touched",
    ]
    for workspace_key in output.get("workspaces_touched") or []:
        lines.append(f"- `{workspace_key}`")
    lines.extend(["", "## Recommended Next Actions"])
    for item in output.get("recommended_next_actions") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Blockers"])
    blockers = output.get("blockers") or ["None."]
    for item in blockers:
        lines.append(f"- {item}")
    lines.extend(["", "## Dependencies"])
    deps = output.get("dependencies") or ["None."]
    for item in deps:
        lines.append(f"- {item}")
    lines.extend(["", "## Escalations"])
    escalations = output.get("escalations") or []
    if not escalations:
        lines.append("- None.")
    else:
        for escalation in escalations:
            lines.append(
                f"- `{escalation.get('target_agent')}`: {escalation.get('recommended_action')} ({escalation.get('reason')})"
            )
    lines.extend(
        [
            "",
            "## PM Context",
            f"- available: `{bundle.get('pm_context', {}).get('available')}`",
            f"- card_count: `{bundle.get('pm_context', {}).get('card_count')}`",
            "",
            "## Automation Context",
            f"- mismatch_count: `{bundle.get('automation_context', {}).get('mismatch_count', (bundle.get('automation_context', {}).get('fallback') or {}).get('mismatch_count', 'unknown'))}`",
            f"- action_required_count: `{bundle.get('automation_context', {}).get('action_required_count', (bundle.get('automation_context', {}).get('fallback') or {}).get('action_required_count', 'unknown'))}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goal",
        default="Review all active workspaces, identify the highest-leverage next actions, and emit structured PM recommendations.",
        help="Goal statement for this Jean-Claude run.",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        help="Workspace key to include. Repeat to include multiple. Defaults to the full portfolio scope.",
    )
    parser.add_argument(
        "--model",
        default="openai/gpt-5.3-codex",
        help="Target Codex-family model label for the runner contract.",
    )
    parser.add_argument("--time-budget-minutes", type=int, default=30)
    parser.add_argument(
        "--output-root",
        default=str(MEMORY_ROOT),
        help="Root folder for runner ledgers/memos/inputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = _now()
    run_id = str(uuid.uuid4())
    stamp = _stamp(started_at)

    output_root = Path(args.output_root)
    ledger_path = output_root / "runner-ledgers" / f"{RUNNER_ID}.jsonl"
    input_path = output_root / "runner-inputs" / RUNNER_ID / f"{stamp}.json"
    recommendation_path = output_root / "runner-recommendations" / RUNNER_ID / f"{stamp}.json"
    memo_path = output_root / "runner-memos" / RUNNER_ID / f"{stamp}_ops_review.md"

    imports = _optional_backend_imports()
    bundle = _build_input_bundle(args, imports, ledger_path, run_id)
    output = _build_recommendations(bundle)

    _write_json(input_path, bundle)
    _write_json(recommendation_path, output)
    _write_markdown_memo(memo_path, bundle, output)

    finished_at = _now()
    ledger_entry = {
        "schema_version": "runner_ledger/v1",
        "run_id": run_id,
        "runner_id": RUNNER_ID,
        "owner_agent": RUNNER_ID,
        "scope": "shared_ops",
        "primary_workspace_key": None,
        "workspace_scope": bundle["workspace_scope"],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "status": output["status"],
        "model": args.model,
        "goal": args.goal,
        "summary": output["summary"],
        "artifacts_written": [
            {"kind": "file", "path": str(input_path), "workspace_key": "shared_ops", "label": "runner input"},
            {"kind": "file", "path": str(recommendation_path), "workspace_key": "shared_ops", "label": "runner output"},
            {"kind": "memo", "path": str(memo_path), "workspace_key": "shared_ops", "label": "ops review memo"},
        ],
        "memory_promotions": output.get("memory_promotions") or [],
        "pm_updates": output["pm_updates"],
        "blockers": output["blockers"],
        "dependencies": output["dependencies"],
        "recommended_next_actions": output["recommended_next_actions"],
        "escalations": output["escalations"],
        "error": None,
        "metadata": {
            "pm_available": bundle["pm_context"].get("available"),
            "automation_available": bundle["automation_context"].get("available"),
            "workspace_registry": str(REGISTRY_PATH),
        },
    }
    _append_jsonl(ledger_path, ledger_entry)

    print(output["summary"])
    print(f"Input bundle: {input_path}")
    print(f"Recommendations: {recommendation_path}")
    print(f"Memo: {memo_path}")
    print(f"Ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
