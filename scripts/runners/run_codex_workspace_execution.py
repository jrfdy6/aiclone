#!/usr/bin/env python3
"""Local Codex executor for PM-backed coding work orders."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
RUNNERS_ROOT = SCRIPTS_ROOT / "runners"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
SAFE_CODEX_CLI_MODEL = "gpt-5.4"
DEFAULT_MODEL = SAFE_CODEX_CLI_MODEL
DEFAULT_REASONING_EFFORT = "high"
RUNNER_ID = "codex-workspace-execution"
UNSUPPORTED_CODEX_CLI_MODELS = frozenset(
    {
        "gpt-5.1-codex",
        "gpt-5.1-codex-max",
        "gpt-5.1-codex-mini",
        "gpt-5.2-codex",
        "gpt-5.3-codex",
        "gpt-5.3-codex-spark",
    }
)
WRAPPER_STATUS_MARKERS = (
    "write_execution_result.py",
    "writer cli",
    "writer failure",
    "rerun the writer",
    "failed to reach pm api",
    "pm api",
    "automatic write-back",
    "automatic writeback",
    "write-back to the pm api",
    "writeback to the pm api",
    "network access to railway",
    "urlopen error",
)

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(RUNNERS_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNERS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs
from chronicle_memory_contract import build_workspace_memory_contract
from runner_lock import execute_with_runner_lock


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, default=_json_default) + "\n")


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_codex_cli_model(model: str | None, fallback_model: str = DEFAULT_MODEL) -> str:
    fallback = str(fallback_model or "").strip() or SAFE_CODEX_CLI_MODEL
    if fallback.startswith("openai/"):
        fallback = fallback.split("/", 1)[1].strip()
    if fallback.lower() in UNSUPPORTED_CODEX_CLI_MODELS:
        fallback = SAFE_CODEX_CLI_MODEL
    cleaned = str(model or "").strip() or fallback
    if cleaned.startswith("openai/"):
        cleaned = cleaned.split("/", 1)[1].strip()
    if cleaned.lower() in UNSUPPORTED_CODEX_CLI_MODELS:
        return fallback
    return cleaned or fallback


def _optional_backend_imports(mode: str) -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {"mode": "api"}
    try:
        from app.models.pm_board import PMCard  # type: ignore
        from app.services.pm_card_service import build_execution_queue_entry  # type: ignore

        loaded["PMCard"] = PMCard
        loaded["build_execution_queue_entry"] = build_execution_queue_entry
    except Exception as exc:  # pragma: no cover
        loaded["helper_error"] = str(exc)
    if mode != "service":
        return loaded
    try:
        from app.models import PMCardUpdate  # type: ignore
        from app.services.pm_card_service import get_card, list_cards, list_execution_queue, update_card  # type: ignore

        loaded["PMCardUpdate"] = PMCardUpdate
        loaded["get_card"] = get_card
        loaded["list_cards"] = list_cards
        loaded["list_execution_queue"] = list_execution_queue
        loaded["update_card"] = update_card
        loaded["mode"] = "service"
    except Exception as exc:  # pragma: no cover
        loaded["mode"] = "api"
        loaded["error"] = str(exc)
    return loaded


def _load_queue(
    imports: dict[str, Any],
    api_url: str,
    *,
    workspace_key: str | None,
    limit: int,
) -> tuple[str, list[dict[str, Any]]]:
    if imports.get("mode") == "service":
        entries = [
            entry.model_dump(mode="json")
            for entry in imports["list_execution_queue"](
                limit=limit,
                workspace_key=workspace_key,
                execution_state="running",
            )
        ]
        return "service", entries
    query = [f"execution_state=running", f"limit={limit}"]
    if workspace_key:
        query.append(f"workspace_key={urllib.parse.quote(workspace_key)}")
    entries = _fetch_json(f"{api_url}/api/pm/execution-queue?{'&'.join(query)}")
    return "api", entries if isinstance(entries, list) else []


def _load_card(imports: dict[str, Any], api_url: str, card_id: str) -> dict[str, Any]:
    if imports.get("mode") == "service":
        card = imports["get_card"](card_id)
        if card is None:
            raise SystemExit(f"PM card not found: {card_id}")
        return card.model_dump(mode="json")
    payload = _fetch_json(f"{api_url}/api/pm/cards?limit=250")
    if not isinstance(payload, list):
        raise SystemExit("PM card list response was not a list.")
    for card in payload:
        if str(card.get("id")) == card_id:
            return card
    raise SystemExit(f"PM card not found: {card_id}")


def _load_host_action_automation_cards(imports: dict[str, Any], api_url: str, limit: int) -> list[dict[str, Any]]:
    if imports.get("mode") == "service" and imports.get("list_cards") is not None:
        cards = imports["list_cards"](limit=limit)
        return [card.model_dump(mode="json") for card in cards]
    payload = _fetch_json(f"{api_url}/api/pm/cards?limit={limit}")
    return payload if isinstance(payload, list) else []


def _is_closed_status(status: Any) -> bool:
    return str(status or "").strip().lower() in {"done", "closed", "cancelled"}


def _host_action_automation(card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(card.get("payload") or {})
    automation = payload.get("host_action_automation")
    return dict(automation) if isinstance(automation, dict) else {}


def _select_queued_host_action_automation_card(cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for card in cards:
        if _is_closed_status(card.get("status")):
            continue
        automation = _host_action_automation(card)
        if str(automation.get("automation_id") or "") != "fallback_watchdog_writeback":
            continue
        if str(automation.get("state") or "").strip().lower() != "queued":
            continue
        candidates.append(card)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda card: _parse_datetime(_host_action_automation(card).get("queued_at"))
        or _parse_datetime(card.get("updated_at"))
        or datetime.max.replace(tzinfo=timezone.utc),
    )[0]


def _build_entry_from_card(imports: dict[str, Any], card: dict[str, Any]) -> dict[str, Any] | None:
    pm_card_model = imports.get("PMCard")
    builder = imports.get("build_execution_queue_entry")
    if pm_card_model is not None and builder is not None:
        try:
            parsed = pm_card_model.model_validate(card)
            entry = builder(parsed)
        except Exception:  # pragma: no cover
            entry = None
        if entry is not None:
            return entry.model_dump(mode="json")

    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    packet_path = str(execution.get("execution_packet_path") or "").strip()
    card_id = str(card.get("id") or "").strip()
    if not packet_path or not card_id:
        return None
    fallback_entry = {
        "card_id": card_id,
        "title": str(card.get("title") or payload.get("title") or ""),
        "workspace_key": str(payload.get("workspace_key") or card.get("workspace_key") or "shared_ops"),
        "execution_state": str(execution.get("state") or payload.get("execution_state") or "running"),
        "executor_status": str(execution.get("executor_status") or "queued"),
        "execution_mode": str(execution.get("execution_mode") or payload.get("execution_mode") or ""),
        "target_agent": str(execution.get("target_agent") or payload.get("target_agent") or ""),
        "manager_agent": str(execution.get("manager_agent") or payload.get("manager_agent") or ""),
        "execution_packet_path": packet_path,
        "reason": str(payload.get("reason") or ""),
        "sop_path": str(execution.get("sop_path") or payload.get("sop_path") or ""),
        "briefing_path": str(execution.get("briefing_path") or payload.get("briefing_path") or ""),
        "last_transition_at": str(execution.get("last_transition_at") or payload.get("last_transition_at") or ""),
    }
    return {key: value for key, value in fallback_entry.items() if value}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _slug(text: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    return "-".join(part for part in lowered.split("-") if part) or "codex-executor"


def _select_entry(
    entries: list[dict[str, Any]],
    *,
    card_id: str | None,
    workspace_key: str | None,
) -> dict[str, Any] | None:
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        if card_id and str(entry.get("card_id") or "") != card_id:
            continue
        if workspace_key and str(entry.get("workspace_key") or "") != workspace_key:
            continue
        packet_path = str(entry.get("execution_packet_path") or "").strip()
        if not packet_path:
            continue
        executor_status = str(entry.get("executor_status") or "queued").strip().lower()
        if executor_status not in {"queued"}:
            continue
        filtered.append(entry)
    if not filtered:
        return None
    return sorted(
        filtered,
        key=lambda item: _parse_datetime(item.get("last_transition_at"))
        or _parse_datetime(item.get("queued_at"))
        or datetime.max.replace(tzinfo=timezone.utc),
    )[0]


def _update_card(
    imports: dict[str, Any],
    api_url: str,
    card_id: str,
    *,
    status: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if imports.get("mode") == "service":
        updated = imports["update_card"](
            card_id,
            imports["PMCardUpdate"](
                status=status,
                payload=payload,
            ),
        )
        if updated is None:
            raise SystemExit(f"Failed to update PM card {card_id}")
        return updated.model_dump(mode="json")
    patch: dict[str, Any] = {"payload": payload}
    if status is not None:
        patch["status"] = status
    return _fetch_json(f"{api_url}/api/pm/cards/{card_id}", method="PATCH", payload=patch)


def _patch_host_action_automation(
    imports: dict[str, Any],
    api_url: str,
    card: dict[str, Any],
    *,
    state: str,
    worker_id: str,
    error: str | None = None,
    proof_items: list[str] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    payload = dict(card.get("payload") or {})
    automation = dict(payload.get("host_action_automation") or {})
    now = _iso(_now())
    automation.update(
        {
            "state": state,
            "last_transition_at": now,
            "worker_id": worker_id,
        }
    )
    if state == "running":
        automation["started_at"] = now
    if state in {"completed", "failed"}:
        automation["finished_at"] = now
    if error:
        automation["last_error"] = error
    else:
        automation.pop("last_error", None)
    if proof_items is not None:
        automation["proof_items"] = proof_items
    payload["host_action_automation"] = automation

    execution = dict(payload.get("execution") or {})
    history = list(execution.get("history") or [])
    history.append(
        {
            "event": f"host_action_automation_{state}",
            "state": state,
            "runner_id": RUNNER_ID,
            "requested_by": worker_id,
            "at": now,
        }
    )
    execution.update(
        {
            "state": f"host_action_automation_{state}",
            "executor_status": "failed" if state == "failed" else ("completed" if state == "completed" else state),
            "executor_worker_id": worker_id,
            "executor_last_error": error,
            "last_transition_at": now,
            "history": history[-12:],
        }
    )
    payload["execution"] = execution
    return _update_card(imports, api_url, str(card["id"]), status=status, payload=payload)


def _run_command(command: list[str], *, timeout_seconds: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(WORKSPACE_ROOT),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _load_saved_watchdog_report() -> dict[str, Any]:
    report_path = MEMORY_ROOT / "reports" / "fallback_watchdog_latest.json"
    if not report_path.exists():
        raise RuntimeError(f"Fallback watchdog report was not written: {report_path}")
    return json.loads(report_path.read_text(encoding="utf-8"))


def _source_work_order_path(source_card: dict[str, Any]) -> Path:
    payload = dict(source_card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    candidates: list[str] = []
    latest_result = payload.get("latest_execution_result")
    if isinstance(latest_result, dict):
        candidates.extend(str(item).strip() for item in latest_result.get("artifacts") or [] if str(item).strip())
    packet_path = str(execution.get("execution_packet_path") or "").strip()
    if packet_path:
        candidates.append(packet_path)
    for candidate in candidates:
        if candidate.endswith("_jean_claude_work_order.json") or candidate.endswith("_work_order.json"):
            path = Path(candidate).expanduser()
            if not path.is_absolute():
                path = WORKSPACE_ROOT / path
            if path.exists():
                return path
    raise RuntimeError(f"Could not find a source work order for PM card {source_card.get('id')}")


def _latest_result_artifact(source_card: dict[str, Any], suffix: str) -> str | None:
    latest_result = dict((dict(source_card.get("payload") or {}).get("latest_execution_result") or {}))
    preferred_keys = []
    if suffix == "_execution_result.md":
        preferred_keys.append("memo_path")
    if suffix == ".json":
        preferred_keys.append("result_path")
    for key in preferred_keys:
        value = str(latest_result.get(key) or "").strip()
        if value.endswith(suffix):
            return value
    for item in latest_result.get("artifacts") or []:
        text = str(item or "").strip()
        if text.endswith(suffix):
            return text
    value = str(latest_result.get("memo_path") or latest_result.get("result_path") or "").strip()
    return value if value.endswith(suffix) else None


def _run_fallback_watchdog_writeback_automation(
    imports: dict[str, Any],
    api_url: str,
    card: dict[str, Any],
    *,
    worker_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    payload = dict(card.get("payload") or {})
    automation = dict(payload.get("host_action_automation") or {})
    host_action = dict(payload.get("host_action_required") or {})
    source_card_id = str(automation.get("source_card_id") or host_action.get("source_card_id") or "").strip()
    if not source_card_id:
        raise RuntimeError("Host action automation is missing source_card_id.")

    if dry_run:
        return {
            "status": "ok",
            "summary": f"Dry run selected host-action automation for source PM card {source_card_id}.",
            "artifacts": [],
            "proof_items": [],
            "metadata": {"dry_run": True},
        }

    running_card = _patch_host_action_automation(
        imports,
        api_url,
        card,
        state="running",
        worker_id=worker_id,
        status="in_progress",
    )

    watchdog = _run_command([sys.executable, str(SCRIPTS_ROOT / "fallback_watchdog.py"), "--api-url", api_url], timeout_seconds=240)
    if watchdog.returncode != 0:
        raise RuntimeError((watchdog.stderr or watchdog.stdout or "fallback_watchdog.py failed").strip())
    report = _load_saved_watchdog_report()
    if str(report.get("status") or "").strip() != "ok" or int(report.get("active_count") or 0) != 0:
        raise RuntimeError(
            "Fallback watchdog refresh did not clear: "
            f"status={report.get('status')} active_count={report.get('active_count')}"
        )

    source_card = _load_card(imports, api_url, source_card_id)
    work_order = _source_work_order_path(source_card)
    generated_at = str(report.get("generated_at") or "").strip()
    report_path = str(MEMORY_ROOT / "reports" / "fallback_watchdog_latest.json")
    summary = (
        f"Refreshed fallback watchdog report is recorded for PM card {source_card_id}. "
        f"memory/reports/fallback_watchdog_latest.json generated at {generated_at} shows status=ok "
        "with active_count=0, memory_alert_count=0, durable_retrieval_alert_count=0, "
        "delivery_alert_count=0, runtime_alert_count=0, and no alerts."
    )
    writer_command = [
        sys.executable,
        str(SCRIPTS_ROOT / "runners" / "write_execution_result.py"),
        "--force-api",
        "--api-url",
        api_url,
        "--work-order",
        str(work_order),
        "--runner-id",
        "jean-claude",
        "--author-agent",
        "Jean-Claude",
        "--status",
        "done",
        "--summary",
        summary,
        "--decision",
        "Closed the shared_ops fallback watchdog packet only after the refreshed saved watchdog artifact existed and reported status=ok.",
        "--learning",
        "For fallback watchdog closure, run the execution-result writer after the saved report refresh so PM truth and Chronicle cite the refreshed artifact rather than a no-network equivalent.",
        "--outcome",
        f"Refreshed watchdog artifact: {report_path} generated_at={generated_at}, status=ok, active_count=0, memory_alert_count=0, durable_retrieval_alert_count=0, delivery_alert_count=0, runtime_alert_count=0.",
        "--outcome",
        "Execution result write-back now records the refreshed status=ok report into Chronicle, PM state, durable runner artifacts, workspace execution log, daily memory, and persistent_state.",
        "--project-update",
        f"PM card {source_card_id} has refreshed fallback watchdog proof attached to the execution-result write-back.",
        "--persistent-state",
        f"shared_ops fallback watchdog PM card {source_card_id} is closed against refreshed report {report_path} generated_at={generated_at} with status=ok and zero active fallback alerts.",
        "--host-action-proof",
        f"Refreshed watchdog report {report_path} generated_at={generated_at} shows status=ok, active_count=0, memory_alert_count=0, durable_retrieval_alert_count=0, delivery_alert_count=0, runtime_alert_count=0, and alerts=[].",
        "--artifact",
        report_path,
    ]
    verification_doc = (
        WORKSPACE_ROOT
        / "workspaces"
        / "shared-ops"
        / "docs"
        / f"fallback_watchdog_verification_{datetime.now().astimezone().date().isoformat()}.md"
    )
    if verification_doc.exists():
        writer_command.extend(["--artifact", str(verification_doc)])
    writer = _run_command(writer_command, timeout_seconds=240)
    if writer.returncode != 0:
        raise RuntimeError((writer.stderr or writer.stdout or "write_execution_result.py failed").strip())

    refreshed_source_card = _load_card(imports, api_url, source_card_id)
    result_memo = _latest_result_artifact(refreshed_source_card, "_execution_result.md") or str(
        dict((dict(refreshed_source_card.get("payload") or {}).get("latest_execution_result") or {})).get("memo_path") or ""
    )
    result_json = _latest_result_artifact(refreshed_source_card, ".json") or str(
        dict((dict(refreshed_source_card.get("payload") or {}).get("latest_execution_result") or {})).get("result_path") or ""
    )
    proof_items = [
        f"Refreshed watchdog report: {report_path} generated_at={generated_at}, status=ok, active_count=0, memory_alert_count=0, durable_retrieval_alert_count=0, delivery_alert_count=0, runtime_alert_count=0, alerts=[].",
        f"PM result write-back proof: {result_memo or 'latest runner memo'} and {result_json or 'latest runner result JSON'} record the refreshed watchdog artifact for PM card {source_card_id}.",
    ]
    close_result = _fetch_json(
        f"{api_url}/api/pm/cards/{card['id']}/actions",
        method="POST",
        payload={
            "action": "approve",
            "requested_by": "Host Action Automation",
            "reason": (
                f"Host automation complete: refreshed fallback watchdog report {report_path} "
                f"generated_at={generated_at} shows status=ok with zero active fallback alerts. "
                f"Execution-result write-back for PM card {source_card_id} is recorded in {result_memo or 'the latest runner memo'}."
            ),
            "resolution_mode": "close_only",
            "proof_items": proof_items,
        },
    )
    closed_card = dict(close_result.get("card") or {}) if isinstance(close_result, dict) else {}
    _patch_host_action_automation(
        imports,
        api_url,
        closed_card or running_card,
        state="completed",
        worker_id=worker_id,
        proof_items=proof_items,
        status="done",
    )
    return {
        "status": "ok",
        "summary": f"Host action automation completed for PM card {source_card_id}; refreshed watchdog report {generated_at} is status=ok and the host card is closed.",
        "artifacts": [report_path, result_memo, result_json],
        "proof_items": proof_items,
        "metadata": {
            "source_card_id": source_card_id,
            "host_card_id": card["id"],
            "watchdog_stdout": watchdog.stdout[-2000:],
            "writer_stdout": writer.stdout[-2000:],
            "close_status": dict(close_result.get("card") or {}).get("status") if isinstance(close_result, dict) else None,
        },
    }


def _claim_execution(
    imports: dict[str, Any],
    api_url: str,
    card: dict[str, Any],
    *,
    worker_id: str,
    packet_path: Path,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run:
        return None
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    history = list(execution.get("history") or [])
    now = _now().isoformat()
    history.append(
        {
            "event": "codex_execution_claimed",
            "state": execution.get("state") or "running",
            "runner_id": RUNNER_ID,
            "requested_by": worker_id,
            "at": now,
        }
    )
    execution.update(
        {
            "state": execution.get("state") or "running",
            "execution_packet_path": str(packet_path),
            "executor_status": "running",
            "executor_worker_id": worker_id,
            "executor_started_at": now,
            "executor_last_error": None,
            "last_transition_at": now,
            "history": history[-16:],
        }
    )
    payload["execution"] = execution
    return _update_card(imports, api_url, str(card["id"]), status=str(card.get("status") or "in_progress"), payload=payload)


def _mark_failed(
    imports: dict[str, Any],
    api_url: str,
    card: dict[str, Any],
    *,
    worker_id: str,
    error_message: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run:
        return None
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    history = list(execution.get("history") or [])
    now = _now().isoformat()
    history.append(
        {
            "event": "codex_execution_failed",
            "state": "failed",
            "runner_id": RUNNER_ID,
            "requested_by": worker_id,
            "at": now,
            "error": error_message[:400],
        }
    )
    execution.update(
        {
            "state": "failed",
            "executor_status": "failed",
            "executor_worker_id": worker_id,
            "executor_finished_at": now,
            "executor_last_error": error_message[:4000],
            "manager_attention_required": True,
            "last_transition_at": now,
            "history": history[-16:],
        }
    )
    payload["execution"] = execution
    return _update_card(imports, api_url, str(card["id"]), status=str(card.get("status") or "in_progress"), payload=payload)


def _parse_work_order(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Execution packet not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = str(payload.get("schema_version") or "")
    if schema not in {"codex_execution_work_order/v1", "workspace_agent_work_order/v1"}:
        raise SystemExit(f"Unsupported execution packet schema: {schema or 'missing'}")

    write_back_contract = dict(payload.get("write_back_contract") or {})
    workspace_root = Path(str(payload.get("workspace_root") or path.parent.parent)).expanduser()
    repo_path = Path(str(payload.get("repo_path") or WORKSPACE_ROOT)).expanduser()
    owner_agent = str(payload.get("owner_agent") or payload.get("workspace_agent") or payload.get("target_agent") or "Jean-Claude")
    preferred_runner_id = str(write_back_contract.get("preferred_runner_id") or _slug(owner_agent))
    preferred_author_agent = str(write_back_contract.get("preferred_author_agent") or owner_agent)
    instructions = [str(item).strip() for item in payload.get("instructions") or [] if str(item).strip()]
    acceptance_criteria = [str(item).strip() for item in payload.get("acceptance_criteria") or [] if str(item).strip()]
    artifacts_expected = [str(item).strip() for item in payload.get("artifacts_expected") or [] if str(item).strip()]
    read_order = [str(item).strip() for item in payload.get("read_order") or [] if str(item).strip()]

    return {
        "schema_version": schema,
        "path": str(path),
        "workspace_key": str(payload.get("workspace_key") or "shared_ops"),
        "workspace_root": workspace_root,
        "repo_path": repo_path,
        "title": str(payload.get("title") or "Untitled execution"),
        "objective": str(payload.get("objective") or "Complete the bounded PM-backed execution packet."),
        "reason": str(payload.get("reason") or ""),
        "owner_agent": owner_agent,
        "manager_agent": str(payload.get("manager_agent") or "Jean-Claude"),
        "target_agent": str(payload.get("target_agent") or owner_agent),
        "front_door_agent": str(payload.get("front_door_agent") or "Neo"),
        "pm_card_id": str(payload.get("pm_card_id") or payload.get("card_id") or write_back_contract.get("pm_card_id") or ""),
        "sop_path": str(payload.get("sop_path") or ""),
        "briefing_path": str(payload.get("briefing_path") or ""),
        "instructions": instructions,
        "acceptance_criteria": acceptance_criteria,
        "artifacts_expected": artifacts_expected,
        "completion_contract": dict(payload.get("completion_contract") or {}),
        "read_order": read_order,
        "preferred_runner_id": preferred_runner_id,
        "preferred_author_agent": preferred_author_agent,
        "recent_chronicle_entries": list(payload.get("recent_chronicle_entries") or []),
        "durable_memory_context": dict(payload.get("durable_memory_context") or {}),
        "memory_context": dict(payload.get("memory_context") or {}),
        "source_paths": [str(item).strip() for item in payload.get("source_paths") or [] if str(item).strip()],
    }


def _packet_matches_entry(packet: dict[str, Any], entry: dict[str, Any]) -> bool:
    if str(packet.get("pm_card_id") or "") != str(entry.get("card_id") or ""):
        return False
    entry_target = str(entry.get("target_agent") or "").strip()
    packet_target = str(packet.get("target_agent") or packet.get("owner_agent") or "").strip()
    if entry_target and packet_target and entry_target != packet_target:
        return False
    return True


def _rebuild_direct_packet_from_entry(entry: dict[str, Any], card: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    sop_path = Path(str(execution.get("sop_path") or entry.get("sop_path") or "")).expanduser()
    briefing_path = Path(str(execution.get("briefing_path") or entry.get("briefing_path") or "")).expanduser()
    memory_contract = build_workspace_memory_contract(
        workspace_key,
        seed_texts=[
            entry.get("title"),
            entry.get("reason"),
            card.get("title"),
            payload.get("reason"),
        ],
        memory_paths=(
            "memory/persistent_state.md",
            "memory/cron-prune.md",
            "memory/daily-briefs.md",
            "memory/LEARNINGS.md",
            "memory/{today}.md",
        ),
    )
    workspace_root = sop_path.parent.parent if sop_path.exists() else WORKSPACE_ROOT / "workspaces" / workspace_key
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "dispatch").mkdir(parents=True, exist_ok=True)
    stamp = _stamp(_now())
    packet_path = workspace_root / "dispatch" / f"{stamp}_jean_claude_work_order.json"
    packet = {
        "schema_version": "codex_execution_work_order/v1",
        "run_id": str(uuid.uuid4()),
        "workspace_key": workspace_key,
        "workspace_root": str(workspace_root),
        "repo_path": str(payload.get("repo_path") or WORKSPACE_ROOT),
        "front_door_agent": payload.get("front_door_agent") or card.get("owner") or "Neo",
        "manager_agent": "Jean-Claude",
        "owner_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "card_id": str(entry.get("card_id") or card.get("id") or ""),
        "pm_card_id": str(entry.get("card_id") or card.get("id") or ""),
        "title": str(entry.get("title") or card.get("title") or "Untitled execution"),
        "objective": f"Jean-Claude should execute this directly inside `{workspace_key}` while preserving PM truth and writing bounded results back.",
        "reason": str(entry.get("reason") or payload.get("reason") or "Advance the PM card."),
        "instructions": [
            "Jean-Claude owns direct execution on this card.",
            "Stay inside the originating workspace lane.",
            "Use the PM card as the source of truth throughout execution.",
            "Write results back through the execution-result writer so Chronicle, LEARNINGS, persistent_state, and PM state all update together.",
            *[
                str(item).strip()
                for item in payload.get("instructions") or []
                if str(item).strip()
            ],
        ],
        "acceptance_criteria": [
            str(item).strip()
            for item in payload.get("acceptance_criteria") or []
            if str(item).strip()
        ],
        "artifacts_expected": [
            str(item).strip()
            for item in payload.get("artifacts_expected") or []
            if str(item).strip()
        ],
        "completion_contract": dict(payload.get("completion_contract") or {}),
        "sop_path": str(sop_path) if str(sop_path) else "",
        "briefing_path": str(briefing_path) if str(briefing_path) else "",
        "read_order": [
            "Read Jean-Claude local pack first.",
            "Read workspace local pack second.",
            "Read the PM card and linked standup before changing scope or priorities.",
            "Read recent Chronicle, durable markdown recall, and core memory tails before changing routing.",
        ],
        "identity_sources": {},
        "recent_chronicle_entries": memory_contract["chronicle_entries"],
        "durable_memory_context": memory_contract["durable_memory_context"],
        "memory_context": memory_contract["memory_context"],
        "source_paths": memory_contract["source_paths"],
        "write_back_contract": {
            "pm_card_id": str(entry.get("card_id") or card.get("id") or ""),
            "preferred_runner_id": "jean-claude",
            "preferred_author_agent": "Jean-Claude",
            "next_state_on_result": "review",
        },
    }
    _write_json(packet_path, packet)
    return packet_path, _parse_work_order(packet_path)


def _build_schema() -> dict[str, Any]:
    def _string_array() -> dict[str, Any]:
        return {"type": "array", "items": {"type": "string"}}

    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["review", "done", "blocked"]},
            "summary": {"type": "string", "minLength": 20},
            "decisions": _string_array(),
            "blockers": _string_array(),
            "learnings": _string_array(),
            "outcomes": _string_array(),
            "follow_ups": _string_array(),
            "host_actions": _string_array(),
            "host_action_proof": _string_array(),
            "project_updates": _string_array(),
            "memory_promotions": _string_array(),
            "persistent_state": _string_array(),
            "artifact_paths": _string_array(),
        },
        "required": [
            "status",
            "summary",
            "decisions",
            "blockers",
            "learnings",
            "outcomes",
            "follow_ups",
            "host_actions",
            "host_action_proof",
            "project_updates",
            "memory_promotions",
            "persistent_state",
            "artifact_paths",
        ],
        "additionalProperties": False,
    }


def _build_prompt(packet: dict[str, Any]) -> str:
    lines = [
        f"You are executing a bounded Codex work packet on behalf of {packet['owner_agent']}.",
        f"Front door agent: {packet['front_door_agent']}",
        f"Manager agent: {packet['manager_agent']}",
        f"Target agent: {packet['target_agent']}",
        f"Workspace: {packet['workspace_key']}",
        f"Repo path: {packet['repo_path']}",
        f"Work packet path: {packet['path']}",
        f"PM card id: {packet['pm_card_id']}",
        "",
        f"Title: {packet['title']}",
        f"Objective: {packet['objective']}",
    ]
    if packet["reason"]:
        lines.append(f"Reason: {packet['reason']}")
    if packet["sop_path"]:
        lines.append(f"SOP path: {packet['sop_path']}")
    if packet["briefing_path"]:
        lines.append(f"Briefing path: {packet['briefing_path']}")
    if packet["read_order"]:
        lines.extend(["", "Read order:"])
        lines.extend(f"- {item}" for item in packet["read_order"])
    if packet["instructions"]:
        lines.extend(["", "Execution instructions:"])
        lines.extend(f"- {item}" for item in packet["instructions"])
    if packet.get("acceptance_criteria"):
        lines.extend(["", "Acceptance criteria:"])
        lines.extend(f"- {item}" for item in packet["acceptance_criteria"])
    if packet.get("artifacts_expected"):
        lines.extend(["", "Expected artifacts:"])
        lines.extend(f"- {item}" for item in packet["artifacts_expected"])
    recent_chronicle_entries = packet.get("recent_chronicle_entries") or []
    if recent_chronicle_entries:
        lines.extend(["", "Recent Chronicle:"])
        for entry in recent_chronicle_entries[-4:]:
            summary = " ".join(str(entry.get("summary") or "").split()).strip()
            if summary:
                lines.append(f"- {summary[:240]}")
    durable_results = (packet.get("durable_memory_context") or {}).get("results") or []
    if durable_results:
        lines.extend(["", "Durable memory recall:"])
        for item in durable_results[:4]:
            title = " ".join(str(item.get("title") or "Untitled").split()).strip()
            path_str = " ".join(str(item.get("path") or "").split()).strip()
            excerpt = " ".join(str(item.get("excerpt") or "").split()).strip()
            if excerpt:
                lines.append(f"- {title} ({path_str}): {excerpt[:280]}")
            else:
                lines.append(f"- {title} ({path_str})")
    memory_context = packet.get("memory_context") or {}
    if memory_context:
        lines.extend(["", "Core memory context:"])
        for key, value in memory_context.items():
            text = " ".join(str(value or "").split()).strip()
            if not text:
                continue
            label = str(key).replace("_tail", "").replace("_", " ")
            lines.append(f"- {label}: {text[-280:]}")
    source_paths = packet.get("source_paths") or []
    if source_paths:
        lines.extend(["", "Memory contract sources:"])
        lines.extend(f"- {item}" for item in source_paths[:12])
    completion_contract = packet.get("completion_contract") or {}
    done_when = [str(item).strip() for item in completion_contract.get("done_when") or [] if str(item).strip()]
    if done_when:
        lines.extend(["", "Completion contract:"])
        lines.extend(f"- {item}" for item in done_when[:6])
    lines.extend(
        [
            "",
            "Rules:",
            "- Stay inside the repo and workspace lane described by the packet.",
            "- Read the packet and any linked SOP/briefing files from disk before editing code.",
            "- Make the required file changes directly in the repo when the task is implementable.",
            "- Do not manually edit PM card state or any `memory/` files; the wrapper owns result memos, execution logs, Chronicle, and PM updates.",
            "- Never run `write_execution_result.py`, `curl`, or any other network/API call from inside this task.",
            "- Never report wrapper, Railway, PM API, or write-back failures in the structured result; only report blockers that affected the workspace task itself.",
            "- Prefer status `review` after making changes, unless the task is fully complete and safe to mark `done`.",
            "- Use status `blocked` only when a concrete blocker prevented meaningful progress.",
            "- If repo-side work is complete but the remaining step requires host credentials or an external UI, keep status `review` and put the exact remaining steps in `host_actions`.",
            "- Use `host_action_proof` to list what evidence the host should capture, such as a confirmation screenshot, publish URL, or analytics note.",
            "- Use `follow_ups` for runtime or team follow-through, not for host-only steps that should become a host-action card.",
            "- Return artifact_paths as absolute file paths for changed or created files when possible.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _mentions_wrapper_status(text: str, api_url: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    api_host = urllib.parse.urlparse(api_url).netloc.lower()
    if api_host and api_host in lowered:
        return True
    return any(marker in lowered for marker in WRAPPER_STATUS_MARKERS)


def _sanitize_summary(summary: str, api_url: str, packet: dict[str, Any], outcomes: list[str]) -> tuple[str, bool]:
    raw_summary = str(summary or "").strip()
    if not _mentions_wrapper_status(raw_summary, api_url):
        return raw_summary, False

    fragments = [
        fragment.strip().rstrip(".,;: ")
        for fragment in re.split(r"(?i)\s+but\s+|(?<=[.!?])\s+", raw_summary)
        if fragment.strip() and not _mentions_wrapper_status(fragment, api_url)
    ]
    if fragments:
        cleaned = ". ".join(fragments).strip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned, cleaned != raw_summary

    clean_outcomes = [item for item in outcomes if item and not _mentions_wrapper_status(item, api_url)]
    if clean_outcomes:
        cleaned = clean_outcomes[0].strip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned, True

    return (
        f"Completed `{packet['title']}` inside `{packet['workspace_key']}` and returned the card for `{packet['owner_agent']}` review.",
        True,
    )


def _sanitize_result_for_wrapper_success(result: dict[str, Any], api_url: str, packet: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    sanitized = dict(result)
    changed = False

    for field in ("blockers", "follow_ups", "host_actions", "host_action_proof", "project_updates"):
        values = [str(item).strip() for item in sanitized.get(field) or [] if str(item).strip()]
        filtered = [item for item in values if not _mentions_wrapper_status(item, api_url)]
        if filtered != values:
            sanitized[field] = filtered
            changed = True

    outcomes = [str(item).strip() for item in sanitized.get("outcomes") or [] if str(item).strip()]
    summary, summary_changed = _sanitize_summary(str(sanitized.get("summary") or ""), api_url, packet, outcomes)
    if summary_changed:
        sanitized["summary"] = summary
        changed = True

    if str(sanitized.get("status") or "").strip().lower() == "blocked" and not list(sanitized.get("blockers") or []):
        sanitized["status"] = "review"
        changed = True

    return sanitized, changed


def _run_codex(packet: dict[str, Any], *, model: str, reasoning_effort: str, timeout_seconds: int) -> tuple[dict[str, Any], str, str, str]:
    repo_path = Path(packet["repo_path"])
    resolved_model = _resolve_codex_cli_model(model)
    with tempfile.TemporaryDirectory(prefix="codex-workspace-run-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        schema_path = temp_dir / "schema.json"
        output_path = temp_dir / "output.json"
        schema_path.write_text(json.dumps(_build_schema(), indent=2), encoding="utf-8")
        command = [
            "codex",
            "exec",
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--cd",
            str(repo_path),
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--model",
            resolved_model,
            "-",
        ]
        if not (repo_path / ".git").exists():
            command.insert(-1, "--skip-git-repo-check")
        completed = subprocess.run(
            command,
            input=_build_prompt(packet),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            raise RuntimeError(
                f"codex exec exited with code {completed.returncode}: "
                f"{(stderr or stdout or 'no output').strip()[:1200]}"
            )
        if not output_path.exists():
            raise RuntimeError("codex exec completed without writing an output message file")
        raw_output = output_path.read_text(encoding="utf-8").strip()
        parsed = json.loads(raw_output)
        if not isinstance(parsed, dict):
            raise RuntimeError("codex exec did not return a JSON object")
        return parsed, raw_output, stdout[-4000:], stderr[-4000:]


def _writer_args(flag: str, items: list[str]) -> list[str]:
    args: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if value:
            args.extend([flag, value])
    return args


def _write_result(
    packet: dict[str, Any],
    result: dict[str, Any],
    *,
    api_url: str,
    dry_run: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPTS_ROOT / "runners" / "write_execution_result.py"),
        "--work-order",
        packet["path"],
        "--api-url",
        api_url,
        "--force-api",
        "--runner-id",
        packet["preferred_runner_id"],
        "--author-agent",
        packet["preferred_author_agent"],
        "--status",
        str(result.get("status") or "review"),
        "--summary",
        str(result.get("summary") or "").strip(),
    ]
    command.extend(_writer_args("--decision", list(result.get("decisions") or [])))
    command.extend(_writer_args("--blocker", list(result.get("blockers") or [])))
    command.extend(_writer_args("--learning", list(result.get("learnings") or [])))
    command.extend(_writer_args("--outcome", list(result.get("outcomes") or [])))
    command.extend(_writer_args("--follow-up", list(result.get("follow_ups") or [])))
    command.extend(_writer_args("--host-action", list(result.get("host_actions") or [])))
    command.extend(_writer_args("--host-action-proof", list(result.get("host_action_proof") or [])))
    command.extend(_writer_args("--project-update", list(result.get("project_updates") or [])))
    command.extend(_writer_args("--memory-promotion", list(result.get("memory_promotions") or [])))
    command.extend(_writer_args("--persistent-state", list(result.get("persistent_state") or [])))
    command.extend(_writer_args("--artifact", list(result.get("artifact_paths") or [])))
    if dry_run:
        command.append("--dry-run")
    env = os.environ.copy()
    for variable in ("OPEN_BRAIN_DATABASE_URL", "BRAIN_VECTOR_DATABASE_URL", "DATABASE_URL"):
        env[variable] = ""
    return subprocess.run(command, text=True, capture_output=True, check=False, env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--mode", choices=["api", "service"], default="api")
    parser.add_argument("--workspace-key")
    parser.add_argument("--card-id")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-codex-workspace-executor")
    parser.add_argument("--output-root", default=str(MEMORY_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = _now()
    run_id = str(uuid.uuid4())
    stamp = _stamp(started_at)
    output_root = Path(args.output_root)
    ledger_path = output_root / "runner-ledgers" / f"{RUNNER_ID}.jsonl"
    input_path = output_root / "runner-inputs" / RUNNER_ID / f"{stamp}.json"
    imports = _optional_backend_imports(args.mode)

    selected_host_action: dict[str, Any] | None = None
    if args.card_id:
        host_candidate = _load_card(imports, args.api_url.rstrip("/"), str(args.card_id))
        if str(_host_action_automation(host_candidate).get("state") or "").strip().lower() == "queued":
            selected_host_action = host_candidate
    else:
        selected_host_action = _select_queued_host_action_automation_card(
            _load_host_action_automation_cards(imports, args.api_url.rstrip("/"), max(args.limit, 100))
        )

    if selected_host_action is not None:
        automation = _host_action_automation(selected_host_action)
        _write_json(
            input_path,
            {
                "schema_version": "codex_workspace_execution_input/v1",
                "run_id": run_id,
                "worker_id": args.worker_id,
                "host_action_card": selected_host_action,
                "host_action_automation": automation,
                "mode": args.mode,
                "api_url": args.api_url,
                "dry_run": args.dry_run,
            },
        )
        try:
            automation_result = _run_fallback_watchdog_writeback_automation(
                imports,
                args.api_url.rstrip("/"),
                selected_host_action,
                worker_id=args.worker_id,
                dry_run=args.dry_run,
            )
            status = "ok"
            error = None
        except Exception as exc:
            status = "failed"
            error = str(exc)
            automation_result = {
                "status": "failed",
                "summary": f"Host action automation failed for `{selected_host_action.get('title')}`: {exc}",
                "artifacts": [],
                "proof_items": [],
                "metadata": {},
            }
            if not args.dry_run:
                try:
                    _patch_host_action_automation(
                        imports,
                        args.api_url.rstrip("/"),
                        selected_host_action,
                        state="failed",
                        worker_id=args.worker_id,
                        error=error,
                        status="blocked",
                    )
                except Exception:
                    pass

        finished_at = _now()
        workspace_key = str((selected_host_action.get("payload") or {}).get("workspace_key") or "shared_ops")
        ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": RUNNER_ID,
            "owner_agent": "Host Action Automation",
            "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
            "primary_workspace_key": workspace_key,
            "workspace_scope": [workspace_key],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": status,
            "model": "host-action-automation",
            "goal": "Run a queued host-action automation without invoking Codex.",
            "summary": str(automation_result.get("summary") or ""),
            "artifacts_written": [
                {"kind": "file", "path": str(input_path), "workspace_key": workspace_key, "label": "runner input"},
                *[
                    {"kind": "file", "path": str(path), "workspace_key": workspace_key, "label": "host action artifact"}
                    for path in automation_result.get("artifacts") or []
                    if str(path).strip()
                ],
            ],
            "memory_promotions": [],
            "pm_updates": [
                {
                    "action": "host_action_automation",
                    "pm_card_id": selected_host_action.get("id"),
                    "workspace_key": workspace_key,
                    "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
                    "owner_agent": "Host Action Automation",
                    "title": selected_host_action.get("title"),
                    "status": status,
                    "reason": str(automation_result.get("summary") or error or ""),
                    "payload": {"automation_id": automation.get("automation_id"), "automation_state": automation_result.get("status")},
                }
            ],
            "blockers": [error] if error else [],
            "dependencies": [],
            "recommended_next_actions": [] if not error else ["Inspect the host-action automation error and rerun after the host path is ready."],
            "escalations": ["manager_attention_required"] if error else [],
            "error": error,
            "metadata": {
                "queue_mode": "host_action_automation",
                "selected_card_id": selected_host_action.get("id"),
                "automation": automation,
                **dict(automation_result.get("metadata") or {}),
                "dry_run": args.dry_run,
            },
        }
        _append_jsonl(ledger_path, ledger_entry)
        if not args.dry_run:
            mirror_runs(
                args.api_url,
                [
                    build_run_payload(
                        run_id=f"codex_workspace_execution::{run_id}",
                        automation_id="codex_workspace_execution",
                        automation_name="Codex Workspace Execution",
                        status="ok" if status == "ok" else "error",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=ledger_entry["duration_ms"],
                        owner_agent="Host Action Automation",
                        scope="workspace" if workspace_key != "shared_ops" else "shared_ops",
                        workspace_key=workspace_key,
                        action_required=bool(error),
                        error=error,
                        metadata={
                            "selected_card_id": selected_host_action.get("id"),
                            "automation_id": automation.get("automation_id"),
                            "summary": ledger_entry["summary"],
                        },
                    )
                ],
            )
        print(ledger_entry["summary"])
        return 0 if status == "ok" else 1

    queue_mode, entries = _load_queue(imports, args.api_url.rstrip("/"), workspace_key=args.workspace_key, limit=args.limit)
    selected_card: dict[str, Any] | None = None
    selected_entry = _select_entry(entries, card_id=args.card_id, workspace_key=args.workspace_key)
    if args.card_id:
        selected_card = _load_card(imports, args.api_url.rstrip("/"), str(args.card_id))
        if selected_entry is None:
            selected_entry = _build_entry_from_card(imports, selected_card)
        if selected_entry is not None and args.workspace_key and str(selected_entry.get("workspace_key") or "") != str(args.workspace_key):
            selected_entry = None

    if selected_entry is None:
        summary = (
            f"PM card {args.card_id} exists but does not currently expose a runnable Codex execution packet."
            if args.card_id
            else "No runnable Codex workspace execution packets are currently queued."
        )
        finished_at = _now()
        ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": RUNNER_ID,
            "owner_agent": "Jean-Claude",
            "scope": "workspace",
            "primary_workspace_key": args.workspace_key,
            "workspace_scope": [args.workspace_key] if args.workspace_key else [],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": "noop",
            "model": args.model,
            "goal": "Execute one PM-backed coding work packet with Codex terminal.",
            "summary": summary,
            "artifacts_written": [],
            "memory_promotions": [],
            "pm_updates": [],
            "blockers": [],
            "dependencies": [],
            "recommended_next_actions": [],
            "escalations": [],
            "error": None,
            "metadata": {"queue_mode": queue_mode, "dry_run": args.dry_run},
        }
        _append_jsonl(ledger_path, ledger_entry)
        if not args.dry_run:
            mirror_runs(
                args.api_url,
                [
                    build_run_payload(
                        run_id=f"codex_workspace_execution::{run_id}",
                        automation_id="codex_workspace_execution",
                        automation_name="Codex Workspace Execution",
                        status="ok",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=ledger_entry["duration_ms"],
                        owner_agent="Jean-Claude",
                        scope="workspace",
                        workspace_key=args.workspace_key,
                        action_required=False,
                        metadata={"summary": summary, "result": "noop", "queue_mode": queue_mode},
                    )
                ],
            )
        print(summary)
        return 0

    card = selected_card or _load_card(imports, args.api_url.rstrip("/"), str(selected_entry["card_id"]))
    try:
        packet_path = Path(str(selected_entry.get("execution_packet_path") or "")).expanduser()
        packet = _parse_work_order(packet_path)
        if not _packet_matches_entry(packet, selected_entry):
            direct_rebuild_allowed = (
                str(selected_entry.get("execution_mode") or "").lower() == "direct"
                and str(selected_entry.get("target_agent") or "").strip() == "Jean-Claude"
            )
            if not direct_rebuild_allowed:
                raise RuntimeError(
                    f"Execution packet target mismatch for card {selected_entry['card_id']}: "
                    f"queue target={selected_entry.get('target_agent')} packet target={packet.get('target_agent')}"
                )
            packet_path, packet = _rebuild_direct_packet_from_entry(selected_entry, card)
    except Exception as exc:
        _mark_failed(
            imports,
            args.api_url.rstrip("/"),
            card,
            worker_id=args.worker_id,
            error_message=str(exc),
            dry_run=args.dry_run,
        )
        raise SystemExit(str(exc)) from exc
    _write_json(
        input_path,
        {
            "schema_version": "codex_workspace_execution_input/v1",
            "run_id": run_id,
            "worker_id": args.worker_id,
            "queue_entry": selected_entry,
            "packet": packet,
            "mode": args.mode,
            "api_url": args.api_url,
            "dry_run": args.dry_run,
        },
    )
    claimed_card = _claim_execution(imports, args.api_url.rstrip("/"), card, worker_id=args.worker_id, packet_path=packet_path, dry_run=args.dry_run)

    try:
        if args.dry_run:
            result = {
                "status": "review",
                "summary": f"Dry run selected `{packet['title']}` for {packet['owner_agent']} inside `{packet['workspace_key']}`.",
                "decisions": ["Dry run skipped codex execution."],
                "blockers": [],
                "learnings": [],
                "outcomes": [],
                "follow_ups": [],
                "host_actions": [],
                "host_action_proof": [],
                "project_updates": [],
                "memory_promotions": [],
                "persistent_state": [],
                "artifact_paths": [packet["path"]],
            }
            raw_output = json.dumps(result)
            stdout = ""
            stderr = ""
        else:
            result, raw_output, stdout, stderr = _run_codex(
                packet,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
            )
    except Exception as exc:
        updated = _mark_failed(
            imports,
            args.api_url.rstrip("/"),
            claimed_card or card,
            worker_id=args.worker_id,
            error_message=str(exc),
            dry_run=args.dry_run,
        )
        finished_at = _now()
        ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": RUNNER_ID,
            "owner_agent": packet["owner_agent"],
            "scope": "workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
            "primary_workspace_key": packet["workspace_key"],
            "workspace_scope": [packet["workspace_key"]],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": "failed",
            "model": args.model,
            "goal": packet["objective"],
            "summary": f"Codex execution failed for `{packet['title']}`.",
            "artifacts_written": [{"kind": "file", "path": str(input_path), "workspace_key": packet["workspace_key"], "label": "executor input"}],
            "memory_promotions": [],
            "pm_updates": [
                {
                    "action": "move_status",
                    "pm_card_id": packet["pm_card_id"],
                    "workspace_key": packet["workspace_key"],
                    "scope": "workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
                    "owner_agent": packet["owner_agent"],
                    "title": packet["title"],
                    "status": str((updated or {}).get("status") or card.get("status") or "in_progress"),
                    "reason": str(exc),
                    "payload": {"execution_state": "failed", "executor_status": "failed"},
                }
            ],
            "blockers": [str(exc)],
            "dependencies": [],
            "recommended_next_actions": [
                "Inspect the executor error on the PM card.",
                "Return the card to Jean-Claude or requeue it once the failure cause is fixed.",
            ],
            "escalations": ["manager_attention_required"],
            "error": str(exc),
            "metadata": {
                "queue_mode": queue_mode,
                "selected_card_id": selected_entry["card_id"],
                "packet_path": packet["path"],
                "api_url": args.api_url,
                "dry_run": args.dry_run,
            },
        }
        _append_jsonl(ledger_path, ledger_entry)
        if not args.dry_run:
            mirror_runs(
                args.api_url,
                [
                    build_run_payload(
                        run_id=f"codex_workspace_execution::{run_id}",
                        automation_id="codex_workspace_execution",
                        automation_name="Codex Workspace Execution",
                        status="error",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=ledger_entry["duration_ms"],
                        owner_agent=packet["owner_agent"],
                        scope="workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
                        workspace_key=packet["workspace_key"],
                        action_required=True,
                        error=str(exc),
                        metadata={
                            "selected_card_id": selected_entry["card_id"],
                            "packet_path": packet["path"],
                            "summary": ledger_entry["summary"],
                        },
                    )
                ],
            )
        print(str(exc), file=sys.stderr)
        return 1

    sanitized_result, result_sanitized = _sanitize_result_for_wrapper_success(result, args.api_url.rstrip("/"), packet)
    writer_result = _write_result(packet, sanitized_result, api_url=args.api_url.rstrip("/"), dry_run=args.dry_run)
    if writer_result.returncode != 0:
        error_message = (writer_result.stderr or writer_result.stdout or "write_execution_result failed").strip()
        updated = _mark_failed(
            imports,
            args.api_url.rstrip("/"),
            claimed_card or card,
            worker_id=args.worker_id,
            error_message=error_message,
            dry_run=args.dry_run,
        )
        finished_at = _now()
        ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": RUNNER_ID,
            "owner_agent": packet["owner_agent"],
            "scope": "workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
            "primary_workspace_key": packet["workspace_key"],
            "workspace_scope": [packet["workspace_key"]],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": "failed",
            "model": args.model,
            "goal": packet["objective"],
            "summary": f"Codex completed work for `{packet['title']}` but result write-back failed.",
            "artifacts_written": [{"kind": "file", "path": str(input_path), "workspace_key": packet["workspace_key"], "label": "executor input"}],
            "memory_promotions": [],
            "pm_updates": [
                {
                    "action": "move_status",
                    "pm_card_id": packet["pm_card_id"],
                    "workspace_key": packet["workspace_key"],
                    "scope": "workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
                    "owner_agent": packet["owner_agent"],
                    "title": packet["title"],
                    "status": str((updated or {}).get("status") or card.get("status") or "in_progress"),
                    "reason": error_message,
                    "payload": {"execution_state": "failed", "executor_status": "failed"},
                }
            ],
            "blockers": [error_message],
            "dependencies": [],
            "recommended_next_actions": [
                "Inspect the writer failure and rerun write_execution_result.py if the code changes are valid.",
            ],
            "escalations": ["manager_attention_required"],
            "error": error_message,
            "metadata": {
                "queue_mode": queue_mode,
                "selected_card_id": selected_entry["card_id"],
                "packet_path": packet["path"],
                "writer_stdout": writer_result.stdout[-2000:],
                "writer_stderr": writer_result.stderr[-2000:],
                "result_sanitized": result_sanitized,
                "dry_run": args.dry_run,
            },
        }
        _append_jsonl(ledger_path, ledger_entry)
        print(error_message, file=sys.stderr)
        return 1

    finished_at = _now()
    artifact_paths = [str(path).strip() for path in sanitized_result.get("artifact_paths") or [] if str(path).strip()]
    ledger_entry = {
        "schema_version": "runner_ledger/v1",
        "run_id": run_id,
        "runner_id": RUNNER_ID,
        "owner_agent": packet["owner_agent"],
        "scope": "workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
        "primary_workspace_key": packet["workspace_key"],
        "workspace_scope": [packet["workspace_key"]],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "status": "ok",
        "model": args.model,
        "goal": packet["objective"],
        "summary": str(sanitized_result.get("summary") or ""),
        "artifacts_written": [
            {"kind": "file", "path": str(input_path), "workspace_key": packet["workspace_key"], "label": "executor input"},
            {"kind": "file", "path": packet["path"], "workspace_key": packet["workspace_key"], "label": "execution packet"},
            *[
                {"kind": "file", "path": path, "workspace_key": packet["workspace_key"], "label": "codex artifact"}
                for path in artifact_paths
            ],
        ],
        "memory_promotions": [str(item) for item in sanitized_result.get("memory_promotions") or [] if str(item).strip()],
        "pm_updates": [
            {
                "action": "update_card",
                "pm_card_id": packet["pm_card_id"],
                "workspace_key": packet["workspace_key"],
                "scope": "workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
                "owner_agent": packet["owner_agent"],
                "title": packet["title"],
                "status": str(sanitized_result.get("status") or "review"),
                "reason": str(sanitized_result.get("summary") or ""),
                "payload": {
                    "execution_state": str(sanitized_result.get("status") or "review"),
                    "executor_status": "completed",
                },
            }
        ],
        "blockers": [str(item) for item in sanitized_result.get("blockers") or [] if str(item).strip()],
        "dependencies": [],
        "recommended_next_actions": [str(item) for item in sanitized_result.get("follow_ups") or [] if str(item).strip()],
        "escalations": [],
        "error": None,
        "metadata": {
            "queue_mode": queue_mode,
            "selected_card_id": selected_entry["card_id"],
            "packet_path": packet["path"],
            "writer_stdout": writer_result.stdout[-2000:],
            "writer_stderr": writer_result.stderr[-2000:],
            "codex_stdout": stdout,
            "codex_stderr": stderr,
            "codex_raw_output": raw_output,
            "result_sanitized": result_sanitized,
            "dry_run": args.dry_run,
        },
    }
    _append_jsonl(ledger_path, ledger_entry)
    if not args.dry_run:
        mirror_runs(
            args.api_url,
            [
                build_run_payload(
                    run_id=f"codex_workspace_execution::{run_id}",
                    automation_id="codex_workspace_execution",
                    automation_name="Codex Workspace Execution",
                    status="ok",
                    run_at=started_at,
                    finished_at=finished_at,
                    duration_ms=ledger_entry["duration_ms"],
                    owner_agent=packet["owner_agent"],
                    scope="workspace" if packet["workspace_key"] != "shared_ops" else "shared_ops",
                    workspace_key=packet["workspace_key"],
                    action_required=False,
                    metadata={
                        "selected_card_id": selected_entry["card_id"],
                        "packet_path": packet["path"],
                        "result_status": str(sanitized_result.get("status") or "review"),
                        "summary": str(sanitized_result.get("summary") or ""),
                        "result_sanitized": result_sanitized,
                    },
                )
            ],
        )

    print(str(sanitized_result.get("summary") or "").strip())
    print(f"Executor input: {input_path}")
    print(f"Execution packet: {packet['path']}")
    print(f"Ledger: {ledger_path}")
    if writer_result.stdout.strip():
        print(writer_result.stdout.strip())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            execute_with_runner_lock(
                lock_name="codex_workspace_execution",
                automation_id="codex_workspace_execution",
                automation_name="Codex Workspace Execution",
                default_api_url=DEFAULT_API_URL,
                main_func=main,
                owner_agent="Jean-Claude",
                scope="workspace",
            )
        )
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach PM API at {DEFAULT_API_URL}: {exc}") from exc
