#!/usr/bin/env python3
"""Detect hidden fallback usage and route it into reports, standups, and PM follow-up."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from runtime_bootstrap import maybe_reexec_with_workspace_venv


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
REPORT_ROOT = WORKSPACE_ROOT / "memory" / "reports"
REGISTRY_PATH = WORKSPACE_ROOT / "memory" / "workspace_registry.json"

FOLLOWUP_TITLE = "Executive resolve fallback usage in memory and retrieval lanes"
FOLLOWUP_SOURCE = "fallback_watchdog:executive_followup"
FOLLOWUP_REASON = "Fallback watchdog detected degraded read or retrieval paths that need repair."

MONITORED_MEMORY_PATHS: tuple[str, ...] = (
    "memory/persistent_state.md",
    "memory/LEARNINGS.md",
    "memory/codex_session_handoff.jsonl",
    "memory/cron-prune.md",
    "memory/daily-briefs.md",
    "memory/dream_cycle_log.md",
    "memory/{today}.md",
)

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_memory_read_target
from app.services.pm_execution_contract_service import build_execution_contract
from build_standup_prep import _load_automation_context, _load_pm_context, _optional_backend_imports
from durable_memory_context import build_durable_memory_context
from progress_pulse_gate import build_report as build_progress_pulse_gate_report


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today_relative_path(relative_path: str) -> str:
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    return relative_path.replace("{today}", today)


def _dedupe_strings(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = " ".join(str(item or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _is_closed_status(status: object) -> bool:
    return str(status or "").strip().lower() in {"done", "closed", "cancelled"}


def _load_cards(api_url: str, fetch_json: Callable[..., Any]) -> list[dict[str, Any]]:
    payload = fetch_json(f"{api_url.rstrip('/')}/api/pm/cards?limit=400")
    return [item for item in payload if isinstance(item, dict)]


def _find_open_followup(cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    for card in cards:
        if card.get("title") != FOLLOWUP_TITLE:
            continue
        if card.get("source") != FOLLOWUP_SOURCE:
            continue
        if _is_closed_status(card.get("status")):
            continue
        return card
    return None


def _load_workspace_keys() -> list[str]:
    workspace_keys = ["shared_ops"]
    if REGISTRY_PATH.exists():
        try:
            payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        for item in payload.get("workspaces") or []:
            if not isinstance(item, dict):
                continue
            workspace_key = str(item.get("workspace_key") or "").strip()
            if workspace_key and workspace_key not in workspace_keys:
                workspace_keys.append(workspace_key)
    return workspace_keys


def _memory_alerts() -> tuple[list[dict[str, Any]], list[str]]:
    alerts: list[dict[str, Any]] = []
    source_paths: list[str] = []
    for relative_path in MONITORED_MEMORY_PATHS:
        resolved_relative = _today_relative_path(relative_path)
        resolution = resolve_memory_read_target(WORKSPACE_ROOT, resolved_relative)
        resolved_path = Path(resolution["resolved_path"])
        source_paths.append(str(resolved_path))
        if resolution.get("fallback_active"):
            resolved_mode = str(resolution.get("resolved_mode") or "missing")
            expected_mode = str(resolution.get("expected_mode") or "live")
            severity = "critical" if resolved_mode in {"snapshot", "missing"} else "warning"
            alerts.append(
                {
                    "id": f"core_memory::{resolved_relative}",
                    "kind": "core_memory_resolution",
                    "severity": severity,
                    "workspace_key": "shared_ops",
                    "relative_path": resolved_relative,
                    "expected_mode": expected_mode,
                    "resolved_mode": resolved_mode,
                    "expected_path": str(resolution.get("expected_path") or ""),
                    "resolved_path": str(resolved_path),
                    "snapshot_id": resolution.get("snapshot_id"),
                    "summary": (
                        f"`{resolved_relative}` expected `{expected_mode}` but resolved `{resolved_mode}` at `{resolved_path}`."
                    ),
                }
            )
            continue
        if resolution.get("runtime_out_of_sync"):
            live_path = str(resolution.get("live_path") or "")
            runtime_path = str(resolution.get("runtime_path") or "")
            delta_hours = resolution.get("live_newer_by_hours")
            detail = f"live mirror is {delta_hours}h newer" if isinstance(delta_hours, (int, float)) else "live mirror is newer"
            alerts.append(
                {
                    "id": f"core_memory_sync::{resolved_relative}",
                    "kind": "core_memory_sync_drift",
                    "severity": "warning",
                    "workspace_key": "shared_ops",
                    "relative_path": resolved_relative,
                    "expected_mode": str(resolution.get("expected_mode") or "runtime"),
                    "resolved_mode": str(resolution.get("resolved_mode") or "runtime"),
                    "runtime_path": runtime_path,
                    "live_path": live_path,
                    "summary": (
                        f"`{resolved_relative}` runtime lane is out of sync: `{live_path}` changed after `{runtime_path}` ({detail})."
                    ),
                }
            )
    return alerts, source_paths


def _durable_checks(workspace_keys: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    source_paths: list[str] = []
    for workspace_key in workspace_keys:
        context = build_durable_memory_context(workspace_key, (), max_results=2)
        warnings = [str(item).strip() for item in (context.get("warnings") or []) if str(item).strip()]
        retrieval_mode = str(context.get("retrieval_mode") or "empty")
        filesystem_result_count = int(context.get("filesystem_result_count") or 0)
        qmd_result_count = int(context.get("qmd_result_count") or 0)
        check = {
            "workspace_key": workspace_key,
            "retrieval_mode": retrieval_mode,
            "fallback_active": bool(context.get("fallback_active")),
            "filesystem_result_count": filesystem_result_count,
            "qmd_result_count": qmd_result_count,
            "warnings": warnings,
            "source_paths": list(context.get("source_paths") or [])[:4],
        }
        checks.append(check)
        source_paths.extend(check["source_paths"])
        if not check["fallback_active"]:
            continue
        severity = "critical" if warnings and qmd_result_count == 0 else "warning"
        detail_bits: list[str] = []
        if filesystem_result_count:
            detail_bits.append(f"filesystem_results={filesystem_result_count}")
        if warnings:
            detail_bits.append(f"warnings={len(warnings)}")
        alerts.append(
            {
                "id": f"durable_memory::{workspace_key}",
                "kind": "durable_memory_retrieval",
                "severity": severity,
                "workspace_key": workspace_key,
                "retrieval_mode": retrieval_mode,
                "filesystem_result_count": filesystem_result_count,
                "qmd_result_count": qmd_result_count,
                "warnings": warnings[:3],
                "source_paths": check["source_paths"],
                "summary": (
                    f"`{workspace_key}` durable retrieval is in `{retrieval_mode}` mode"
                    + (f" ({', '.join(detail_bits)})." if detail_bits else ".")
                ),
            }
        )
    return checks, alerts, source_paths


def _progress_pulse_alerts() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report = build_progress_pulse_gate_report()
    alerts: list[dict[str, Any]] = []
    if report.get("delivery_fallback_active"):
        alerts.append(
            {
                "id": "progress_pulse::delivery",
                "kind": "progress_pulse_delivery",
                "severity": "warning",
                "workspace_key": "shared_ops",
                "new_handoff_count": int(report.get("new_handoff_count") or 0),
                "material_handoff_count": int(report.get("material_handoff_count") or 0),
                "latest_handoff_summary": report.get("latest_handoff_summary"),
                "summary": (
                    "Progress Pulse would deliver from `persistent_state.md` drift without a material Chronicle handoff."
                ),
            }
        )
    return alerts, report


def _runtime_context_alerts(api_url: str) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    imports = _optional_backend_imports()
    pm_context = _load_pm_context(imports, "shared_ops", api_url)
    automation_context = _load_automation_context(imports)
    alerts: list[dict[str, Any]] = []
    source_refs: list[str] = []

    pm_source_ref = str(pm_context.get("source_ref") or "").strip()
    if pm_source_ref:
        source_refs.append(pm_source_ref)
    if pm_context.get("fallback_active"):
        pm_available = bool(pm_context.get("available"))
        pm_source = str(pm_context.get("source") or "pm_unavailable")
        pm_reason = str(pm_context.get("fallback_reason") or "pm_backend_service_unavailable")
        severity = "warning" if pm_available else "critical"
        alerts.append(
            {
                "id": "runtime_context::pm",
                "kind": "pm_context_loader",
                "severity": severity,
                "workspace_key": "shared_ops",
                "source": pm_source,
                "source_ref": pm_source_ref or None,
                "fallback_reason": pm_reason,
                "primary_error": pm_context.get("primary_error"),
                "available": pm_available,
                "summary": (
                    f"PM context loader is using `{pm_source}` because `{pm_reason}`."
                    if pm_available
                    else f"PM context loader is unavailable after fallback because `{pm_reason}`."
                ),
            }
        )

    automation_source_ref = str(automation_context.get("source_ref") or "").strip()
    if automation_source_ref:
        source_refs.append(automation_source_ref)
    if automation_context.get("fallback_active"):
        automation_source = str(automation_context.get("source") or "automation_unavailable")
        automation_reason = str(automation_context.get("fallback_reason") or "automation_mismatch_service_unavailable")
        has_secondary_source = automation_source not in {"", "automation_unavailable"}
        severity = "warning" if has_secondary_source else "critical"
        alerts.append(
            {
                "id": "runtime_context::automation",
                "kind": "automation_context_loader",
                "severity": severity,
                "workspace_key": "shared_ops",
                "source": automation_source,
                "source_ref": automation_source_ref or None,
                "fallback_reason": automation_reason,
                "primary_error": automation_context.get("primary_error"),
                "available": has_secondary_source,
                "summary": (
                    f"Automation context loader is using `{automation_source}` because `{automation_reason}`."
                    if has_secondary_source
                    else f"Automation context loader is unavailable after fallback because `{automation_reason}`."
                ),
            }
        )

    return alerts, {"pm_context": pm_context, "automation_context": automation_context}, source_refs


def _fingerprint(alerts: list[dict[str, Any]]) -> str:
    normalized = json.dumps(
        [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "severity": item.get("severity"),
                "workspace_key": item.get("workspace_key"),
                "summary": item.get("summary"),
            }
            for item in alerts
        ],
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _headline(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "No monitored fallback conditions are active."
    return f"Fallback watchdog found {len(alerts)} active fallback condition(s) across memory, retrieval, or delivery lanes."


def _upsert_followup(
    api_url: str,
    cards: list[dict[str, Any]],
    report: dict[str, Any],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any]:
    contract = build_execution_contract(
        title=FOLLOWUP_TITLE,
        workspace_key="shared_ops",
        source="fallback_watchdog",
        reason=FOLLOWUP_REASON,
        instructions=[
            "Inspect the fallback watchdog report and identify why each lane left its expected source contract.",
            "Repair the root cause so canonical memory reads return to runtime/live expectations and durable retrieval returns to indexed QMD-first operation.",
            "Write back a bounded PM result that records the fix and the verification step that proves the fallback cleared.",
        ],
        acceptance_criteria=[
            "Every active fallback alert is either cleared or left with an explicit blocker plus owner.",
            "The report no longer shows silent source degradation for the repaired lane.",
        ],
        artifacts_expected=[
            "fallback watchdog verification note",
            "updated PM result or blocker explanation",
        ],
    )
    execution = {
        "lane": "codex",
        "state": "queued",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "execution_mode": "direct",
        "requested_by": "Fallback Watchdog",
        "assigned_runner": "codex",
        "reason": FOLLOWUP_REASON,
        "queued_at": now.isoformat(),
        "last_transition_at": now.isoformat(),
        "source": "fallback_watchdog",
    }
    payload = {
        "workspace_key": "shared_ops",
        "scope": "shared_ops",
        "source_agent": "fallback_watchdog",
        "created_from_fallback_watchdog": True,
        "latest_report_generated_at": report.get("generated_at"),
        "active_alert_count": report.get("active_count"),
        "active_alert_fingerprint": report.get("fingerprint"),
        "alert_summary": report.get("headline"),
        "alerts": report.get("alerts") or [],
        "source_paths": report.get("source_paths") or [],
        "monitored_workspace_keys": report.get("monitored_workspace_keys") or [],
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "execution": execution,
    }

    existing = _find_open_followup(cards)
    if existing is not None:
        existing_payload = dict(existing.get("payload") or {})
        existing_execution = dict(existing_payload.get("execution") or {})
        existing_state = str(existing_execution.get("state") or "").strip().lower()
        if existing_state in {"ready", "queued", "running", "review"}:
            execution.update(
                {
                    "state": existing_execution.get("state"),
                    "queued_at": existing_execution.get("queued_at") or execution.get("queued_at"),
                    "last_transition_at": existing_execution.get("last_transition_at") or execution.get("last_transition_at"),
                    "assigned_runner": existing_execution.get("assigned_runner") or execution.get("assigned_runner"),
                    "executor_status": existing_execution.get("executor_status"),
                    "executor_worker_id": existing_execution.get("executor_worker_id"),
                    "manager_attention_required": existing_execution.get("manager_attention_required"),
                }
            )
        payload["execution"] = execution
        updated = fetch_json(
            f"{api_url.rstrip('/')}/api/pm/cards/{existing['id']}",
            method="PATCH",
            payload={
                "owner": "Jean-Claude",
                "payload": {**existing_payload, **payload},
            },
        )
        return {
            "action": "updated",
            "card_id": updated.get("id") if isinstance(updated, dict) else existing.get("id"),
            "status": updated.get("status") if isinstance(updated, dict) else existing.get("status"),
            "title": FOLLOWUP_TITLE,
        }

    created = fetch_json(
        f"{api_url.rstrip('/')}/api/pm/cards",
        method="POST",
        payload={
            "title": FOLLOWUP_TITLE,
            "owner": "Jean-Claude",
            "status": "todo",
            "source": FOLLOWUP_SOURCE,
            "payload": payload,
        },
    )
    return {
        "action": "created",
        "card_id": created.get("id") if isinstance(created, dict) else None,
        "status": created.get("status") if isinstance(created, dict) else "todo",
        "title": FOLLOWUP_TITLE,
    }


def _resolve_followup(
    api_url: str,
    cards: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any] | None:
    existing = _find_open_followup(cards)
    if existing is None:
        return None
    payload = dict(existing.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    history = list(execution.get("history") or [])
    history.append(
        {
            "event": "fallback_watchdog_resolved",
            "state": "done",
            "requested_by": "Fallback Watchdog",
            "target_agent": "Jean-Claude",
            "at": now.isoformat(),
        }
    )
    execution.update(
        {
            "state": "done",
            "manager_attention_required": False,
            "target_agent": "Jean-Claude",
            "assigned_runner": "codex",
            "reason": "Fallback watchdog no longer sees active degraded source contracts.",
            "last_transition_at": now.isoformat(),
            "history": history[-12:],
        }
    )
    payload["execution"] = execution
    payload["resolved_at"] = now.isoformat()
    payload["resolution_reason"] = "No monitored fallback alerts remained active."
    updated = fetch_json(
        f"{api_url.rstrip('/')}/api/pm/cards/{existing['id']}",
        method="PATCH",
        payload={
            "status": "done",
            "payload": payload,
        },
    )
    return {
        "action": "closed",
        "card_id": updated.get("id") if isinstance(updated, dict) else existing.get("id"),
        "status": updated.get("status") if isinstance(updated, dict) else "done",
        "title": FOLLOWUP_TITLE,
    }


def build_report(
    api_url: str,
    sync_live: bool,
    *,
    fetch_json: Callable[..., Any] = _fetch_json,
) -> dict[str, Any]:
    now = _now()
    workspace_keys = _load_workspace_keys()
    memory_alerts, memory_source_paths = _memory_alerts()
    durable_checks, durable_alerts, durable_source_paths = _durable_checks(workspace_keys)
    progress_pulse_alerts, progress_pulse_report = _progress_pulse_alerts()
    runtime_alerts, runtime_checks, runtime_source_refs = _runtime_context_alerts(api_url)
    alerts = [*memory_alerts, *durable_alerts, *progress_pulse_alerts, *runtime_alerts]
    source_paths = _dedupe_strings(memory_source_paths + durable_source_paths + runtime_source_refs)

    report = {
        "generated_at": _iso(now),
        "source": "fallback_watchdog",
        "status": "action_required" if alerts else "ok",
        "headline": _headline(alerts),
        "active": bool(alerts),
        "active_count": len(alerts),
        "memory_alert_count": len(memory_alerts),
        "durable_retrieval_alert_count": len(durable_alerts),
        "delivery_alert_count": len(progress_pulse_alerts),
        "runtime_alert_count": len(runtime_alerts),
        "fingerprint": _fingerprint(alerts),
        "monitored_workspace_keys": workspace_keys,
        "alerts": alerts,
        "durable_checks": durable_checks,
        "progress_pulse": progress_pulse_report,
        "runtime_checks": runtime_checks,
        "source_paths": source_paths,
        "followup_recommended": bool(alerts),
        "followup_card": None,
    }

    if sync_live:
        cards = _load_cards(api_url, fetch_json)
        if alerts:
            report["followup_card"] = _upsert_followup(
                api_url,
                cards,
                report,
                now=now,
                fetch_json=fetch_json,
            )
        else:
            report["followup_card"] = _resolve_followup(
                api_url,
                cards,
                now=now,
                fetch_json=fetch_json,
            )

    return report


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Fallback Watchdog Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Active alerts: `{report['active_count']}`",
        f"- Memory alerts: `{report['memory_alert_count']}`",
        f"- Durable retrieval alerts: `{report['durable_retrieval_alert_count']}`",
        f"- Delivery alerts: `{report['delivery_alert_count']}`",
        f"- Runtime loader alerts: `{report['runtime_alert_count']}`",
        "",
        f"{report['headline']}",
        "",
        "## Active alerts",
    ]
    alerts = report.get("alerts") or []
    if not alerts:
        lines.append("- None.")
    else:
        for item in alerts:
            lines.append(f"- `{item['severity']}` `{item['kind']}` — {item['summary']}")
    lines.extend(["", "## Durable checks"])
    for item in report.get("durable_checks") or []:
        lines.append(
            f"- `{item['workspace_key']}` -> `{item['retrieval_mode']}` "
            f"(qmd={item['qmd_result_count']}, filesystem={item['filesystem_result_count']})"
        )
        for warning in item.get("warnings") or []:
            lines.append(f"  - Warning: {warning}")
    lines.extend(["", "## Runtime checks"])
    runtime_checks = report.get("runtime_checks") or {}
    pm_context = runtime_checks.get("pm_context") or {}
    automation_context = runtime_checks.get("automation_context") or {}
    if pm_context:
        lines.append(
            f"- PM context -> `{pm_context.get('source', 'unknown')}` "
            f"(fallback_active={bool(pm_context.get('fallback_active'))})"
        )
    if automation_context:
        lines.append(
            f"- Automation context -> `{automation_context.get('source', 'unknown')}` "
            f"(fallback_active={bool(automation_context.get('fallback_active'))})"
        )
    lines.extend(["", "## PM follow-up"])
    followup = report.get("followup_card")
    if not isinstance(followup, dict):
        lines.append("- None.")
    else:
        lines.append(
            f"- `{followup.get('title', FOLLOWUP_TITLE)}` -> `{followup.get('action', 'tracked')}` "
            f"(`{followup.get('status', 'unknown')}`)"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    maybe_reexec_with_workspace_venv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default=str(REPORT_ROOT / "fallback_watchdog_latest.json"))
    parser.add_argument("--output-md", default=str(REPORT_ROOT / "fallback_watchdog_latest.md"))
    args = parser.parse_args()

    report = build_report(args.api_url, sync_live=not args.dry_run)
    _write_json(Path(args.output_json).expanduser(), report)
    _write_markdown(Path(args.output_md).expanduser(), _markdown_report(report))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
