#!/usr/bin/env python3
"""Jean-Claude execution dispatcher.

Consumes one queued PM card owned by Jean-Claude, writes an SOP/work-order into
the correct workspace lane, updates the same PM card, and appends Chronicle so
the executive standup can react to the result later.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
CODEX_HANDOFF_PATH = MEMORY_ROOT / "codex_session_handoff.jsonl"
REGISTRY_PATH = MEMORY_ROOT / "workspace_registry.json"
RUNNER_ID = "jean-claude-execution"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
PACK_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md", "CHARTER.md")
EXECUTIVE_REGISTRY_FALLBACK = {
    "workspace_key": "shared_ops",
    "display_name": "Executive",
    "workspace_agent": "Jean-Claude",
    "target_agent": "Jean-Claude",
    "notes": "Executive lane for cross-workspace hygiene and accountability sweeps.",
}

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs


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


def _optional_backend_imports(mode: str) -> dict[str, Any]:
    if mode != "service":
        return {"mode": "api"}
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {}
    try:
        from app.models import PMCardUpdate  # type: ignore
        from app.services.pm_card_service import get_card, list_execution_queue, update_card  # type: ignore

        loaded["PMCardUpdate"] = PMCardUpdate
        loaded["get_card"] = get_card
        loaded["list_execution_queue"] = list_execution_queue
        loaded["update_card"] = update_card
        loaded["mode"] = "service"
    except Exception as exc:  # pragma: no cover
        loaded["mode"] = "api"
        loaded["error"] = str(exc)
    return loaded


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    items = payload.get("workspaces") or []
    registry: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and item.get("workspace_key"):
            registry[str(item["workspace_key"])] = item
    return registry


def _registry_item(workspace_key: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = dict(registry.get(workspace_key) or {})
    if workspace_key == "shared_ops":
        for key, value in EXECUTIVE_REGISTRY_FALLBACK.items():
            item.setdefault(key, value)
    return item


def _load_pack(base: Path) -> dict[str, Any]:
    pack: dict[str, Any] = {"base_path": str(base), "files": {}}
    for name in PACK_FILES:
        path = base / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        pack["files"][name] = {
            "path": str(path),
            "content": text,
        }
    return pack


def _load_queue(imports: dict[str, Any], api_url: str, limit: int) -> tuple[str, list[dict[str, Any]]]:
    if imports.get("mode") == "service":
        entries = [
            entry.model_dump(mode="json")
            for entry in imports["list_execution_queue"](
                limit=limit,
                manager_agent="Jean-Claude",
                execution_state="queued",
            )
        ]
        return "service", entries
    entries = _fetch_json(
        f"{api_url}/api/pm/execution-queue?manager_agent=Jean-Claude&execution_state=queued&limit={limit}"
    )
    return "api", entries if isinstance(entries, list) else []


def _load_card(imports: dict[str, Any], api_url: str, card_id: str) -> dict[str, Any]:
    if imports.get("mode") == "service":
        card = imports["get_card"](card_id)
        if card is None:
            raise SystemExit(f"PM card not found: {card_id}")
        return card.model_dump(mode="json")
    payload = _fetch_json(f"{api_url}/api/pm/cards?limit=200")
    if not isinstance(payload, list):
        raise SystemExit("PM card list response was not a list.")
    for card in payload:
        if str(card.get("id")) == card_id:
            return card
    raise SystemExit(f"PM card not found: {card_id}")


def _select_next_entry(entries: list[dict[str, Any]], *, card_id: str | None = None) -> dict[str, Any] | None:
    filtered: list[dict[str, Any]] = []
    for item in entries:
        if card_id and str(item.get("card_id") or "") != card_id:
            continue
        execution_mode = str(item.get("execution_mode") or "direct").lower()
        assigned_runner = str(item.get("assigned_runner") or "").strip().lower()
        if execution_mode == "delegated" and assigned_runner and assigned_runner not in {"codex", "jean-claude"}:
            continue
        filtered.append(item)
    if not filtered:
        return None
    return sorted(
        filtered,
        key=lambda item: _parse_datetime(item.get("queued_at"))
        or _parse_datetime(item.get("last_transition_at"))
        or datetime.max.replace(tzinfo=timezone.utc),
    )[0]


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
    return "-".join(part for part in lowered.split("-") if part) or "workspace-agent"


def _workspace_label(workspace_key: str, display_name: str | None) -> str:
    normalized_display = (display_name or workspace_key).strip()
    normalized_key = workspace_key.strip()
    if normalized_display.lower() == normalized_key.lower():
        return f"`{normalized_key}`"
    return f"{normalized_display} (`{normalized_key}`)"


def _workspace_root(workspace_key: str, registry: dict[str, dict[str, Any]]) -> Path:
    if workspace_key == "shared_ops":
        base = WORKSPACE_ROOT / "workspaces" / "shared-ops"
    else:
        item = registry.get(workspace_key) or {}
        configured = item.get("filesystem_path")
        if isinstance(configured, str) and configured.strip():
            base = Path(configured)
        else:
            base = WORKSPACE_ROOT / "workspaces" / workspace_key
    for subdir in ("dispatch", "briefings", "docs"):
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base


def _build_bundle(args: argparse.Namespace, run_id: str, selected_entry: dict[str, Any], card: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    workspace_key = str(selected_entry.get("workspace_key") or "shared_ops")
    workspace_root = _workspace_root(workspace_key, registry)
    workspace_pack = _load_pack(workspace_root)
    registry_item = _registry_item(workspace_key, registry)
    return {
        "schema_version": "runner_input/v1",
        "run_id": run_id,
        "runner_id": RUNNER_ID,
        "owner_agent": "jean-claude",
        "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
        "workspace_scope": [workspace_key],
        "primary_workspace_key": workspace_key,
        "goal": args.goal,
        "run_mode": "manual",
        "time_budget_minutes": args.time_budget_minutes,
        "model": args.model,
        "dry_run": args.dry_run,
        "workspace_root": str(workspace_root),
        "queue_entry": selected_entry,
        "pm_card": card,
        "registry_item": registry_item,
        "workspace_display_name": str(registry_item.get("display_name") or workspace_key),
        "agent_pack": _load_pack(WORKSPACE_ROOT / "agents" / "jean-claude"),
        "workspace_pack": workspace_pack,
        "base_pack": _load_pack(WORKSPACE_ROOT),
    }


def _build_sop(bundle: dict[str, Any]) -> dict[str, Any]:
    queue_entry = bundle["queue_entry"]
    card = bundle["pm_card"]
    workspace_key = bundle["primary_workspace_key"]
    registry_item = bundle.get("registry_item") or {}
    display_name = str(registry_item.get("display_name") or workspace_key)
    workspace_label = _workspace_label(workspace_key, display_name)
    direct = str(queue_entry.get("execution_mode") or "direct") == "direct"
    target_agent = str(queue_entry.get("target_agent") or "Jean-Claude")
    canonical_target = str(registry_item.get("target_agent") or "").strip()
    if canonical_target:
        target_agent = canonical_target
    reason = str(queue_entry.get("reason") or ((card.get("payload") or {}).get("reason")) or "Advance the PM card.")

    workspace_agent = queue_entry.get("workspace_agent")
    canonical_workspace_agent = str(registry_item.get("workspace_agent") or "").strip()
    if canonical_workspace_agent:
        workspace_agent = canonical_workspace_agent

    if direct:
        objective = (
            f"Jean-Claude should execute this directly inside {workspace_label} while preserving PM truth and writing bounded results back."
        )
    else:
        objective = f"Jean-Claude should brief {target_agent} and keep the work contained inside {workspace_label}."

    steps = [
        "Stay inside the originating workspace lane.",
        "Use the PM card as the source of truth throughout execution.",
        "Write results back through the execution-result writer so Chronicle, LEARNINGS, persistent_state, and PM state all update together.",
    ]
    if direct:
        steps.insert(0, "Jean-Claude owns direct execution on this card.")
    else:
        steps.insert(0, f"{target_agent} owns the lane execution once this SOP is handed off.")

    return {
        "schema_version": "workspace_sop/v1",
        "manager_agent": "Jean-Claude",
        "workspace_key": workspace_key,
        "execution_mode": queue_entry.get("execution_mode") or "direct",
        "workspace_agent": workspace_agent,
        "target_agent": target_agent,
        "card_id": queue_entry.get("card_id"),
        "title": queue_entry.get("title"),
        "objective": objective,
        "reason": reason,
        "read_order": [
            "Read Jean-Claude local pack first.",
            "Read workspace local pack second.",
            "Read the PM card and linked standup before changing scope or priorities.",
        ],
        "identity_sources": {
            "manager_pack": bundle.get("agent_pack"),
            "workspace_pack": bundle.get("workspace_pack"),
        },
        "steps": steps,
        "linked_standup_id": card.get("link_id"),
        "pm_source": card.get("source"),
        "write_back_contract": {
            "pm_card_id": queue_entry.get("card_id"),
            "use_writer": str(WORKSPACE_ROOT / "scripts" / "runners" / "write_execution_result.py"),
            "next_state_on_result": "review",
        },
    }


def _update_card(
    imports: dict[str, Any],
    api_url: str,
    card: dict[str, Any],
    run_id: str,
    sop_path: Path,
    briefing_path: Path,
    *,
    execution_packet_path: Path | None,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run:
        return None
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    now = _now()
    history = list(execution.get("history") or [])
    target_agent = str(execution.get("target_agent") or "Jean-Claude")
    execution_mode = str(execution.get("execution_mode") or "direct")
    event_name = "sop_opened" if execution_mode == "direct" else "delegated"
    next_state = "running" if execution_mode == "direct" else "queued"
    next_status = "in_progress" if execution_mode == "direct" else "queued"
    history.append(
        {
            "event": event_name,
            "state": next_state,
            "runner_id": RUNNER_ID,
            "run_id": run_id,
            "requested_by": "Jean-Claude",
            "target_agent": target_agent,
            "at": now.isoformat(),
        }
    )
    execution.update(
        {
            "state": next_state,
            "manager_agent": execution.get("manager_agent") or "Jean-Claude",
            "manager_attention_required": False,
            "target_agent": target_agent,
            "assigned_runner": _slug(target_agent) if execution_mode == "delegated" else "jean-claude",
            "active_run_id": run_id,
            "sop_path": str(sop_path),
            "briefing_path": str(briefing_path),
            "last_transition_at": now.isoformat(),
            "history": history[-12:],
        }
    )
    if execution_packet_path is not None:
        execution["execution_packet_path"] = str(execution_packet_path)
        execution["executor_status"] = "queued"
        execution["executor_worker_id"] = None
        execution["executor_started_at"] = None
        execution["executor_last_error"] = None
    else:
        execution["execution_packet_path"] = None
        execution["executor_status"] = None
        execution["executor_worker_id"] = None
        execution["executor_started_at"] = None
        execution["executor_last_error"] = None
    payload["execution"] = execution

    if imports.get("mode") == "service":
        updated = imports["update_card"](
            str(card["id"]),
            imports["PMCardUpdate"](
                status=next_status,
                payload=payload,
            ),
        )
        return updated.model_dump(mode="json") if updated else None

    return _fetch_json(
        f"{api_url}/api/pm/cards/{card['id']}",
        method="PATCH",
        payload={"status": next_status, "payload": payload},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goal",
        default="Open one queued PM card into a Jean-Claude SOP and route it to the correct execution lane.",
    )
    parser.add_argument("--model", default="openai/gpt-5.3-codex")
    parser.add_argument("--time-budget-minutes", type=int, default=25)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--mode", choices=["api", "service"], default="api")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--card-id")
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
    queue_mode, queue_entries = _load_queue(imports, args.api_url.rstrip("/"), args.limit)
    selected_entry = _select_next_entry(queue_entries, card_id=args.card_id)
    if selected_entry is None:
        summary = (
            f"Jean-Claude found no queued PM card matching {args.card_id}."
            if args.card_id
            else "Jean-Claude found no queued PM cards to dispatch."
        )
        finished_at = _now()
        ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": RUNNER_ID,
            "owner_agent": "jean-claude",
            "scope": "shared_ops",
            "primary_workspace_key": None,
            "workspace_scope": [],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": "noop",
            "model": args.model,
            "goal": args.goal,
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
                        run_id=f"jean_claude_execution_dispatch::{run_id}",
                        automation_id="jean_claude_execution_dispatch",
                        automation_name="Jean-Claude Execution Dispatch",
                        status="ok",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=ledger_entry["duration_ms"],
                        owner_agent="Jean-Claude",
                        scope="shared_ops",
                        action_required=False,
                        metadata={
                            "summary": summary,
                            "result": "noop",
                            "queue_mode": queue_mode,
                        },
                    )
                ],
            )
        print(summary)
        return 0

    card = _load_card(imports, args.api_url.rstrip("/"), str(selected_entry["card_id"]))
    registry = _read_registry()
    bundle = _build_bundle(args, run_id, selected_entry, card, registry)
    sop = _build_sop(bundle)
    workspace_root = Path(bundle["workspace_root"])
    sop_path = workspace_root / "dispatch" / f"{stamp}_sop.json"
    briefing_path = workspace_root / "briefings" / f"{stamp}_briefing.md"
    work_order_path: Path | None = None

    _write_json(input_path, bundle)
    _write_json(sop_path, sop)
    display_name = bundle.get("workspace_display_name") or bundle["primary_workspace_key"]
    workspace_key = bundle["primary_workspace_key"]
    if str(display_name).strip().lower() == workspace_key.lower():
        workspace_line = f"- Workspace: `{workspace_key}`"
    else:
        workspace_line = f"- Workspace: {display_name} (`{workspace_key}`)"
    briefing_lines = [
        f"# Jean-Claude SOP Brief - {sop['title']}",
        "",
        workspace_line,
        f"- Mode: `{sop['execution_mode']}`",
        f"- Manager: `Jean-Claude`",
        f"- Target: `{sop['target_agent']}`",
        "",
        "## Objective",
        sop["objective"],
        "",
        "## Steps",
    ]
    briefing_lines.extend(f"- {item}" for item in sop["steps"])
    briefing_path.write_text("\n".join(briefing_lines).rstrip() + "\n", encoding="utf-8")

    if sop["execution_mode"] == "direct":
        card_payload = dict(card.get("payload") or {})
        repo_path = str(card_payload.get("repo_path") or WORKSPACE_ROOT)
        work_order_path = workspace_root / "dispatch" / f"{stamp}_jean_claude_work_order.json"
        direct_work_order = {
            "schema_version": "codex_execution_work_order/v1",
            "run_id": run_id,
            "workspace_key": bundle["primary_workspace_key"],
            "workspace_root": str(workspace_root),
            "repo_path": repo_path,
            "front_door_agent": card_payload.get("front_door_agent") or card.get("owner") or "Neo",
            "manager_agent": "Jean-Claude",
            "owner_agent": "Jean-Claude",
            "target_agent": "Jean-Claude",
            "card_id": selected_entry["card_id"],
            "pm_card_id": selected_entry["card_id"],
            "title": selected_entry["title"],
            "objective": sop["objective"],
            "reason": sop["reason"],
            "instructions": list(sop["steps"]),
            "sop_path": str(sop_path),
            "briefing_path": str(briefing_path),
            "read_order": list(sop["read_order"]),
            "identity_sources": dict(sop["identity_sources"]),
            "write_back_contract": {
                "pm_card_id": selected_entry["card_id"],
                "preferred_runner_id": "jean-claude",
                "preferred_author_agent": "Jean-Claude",
                "use_writer": str(WORKSPACE_ROOT / "scripts" / "runners" / "write_execution_result.py"),
                "next_state_on_result": "review",
            },
        }
        _write_json(work_order_path, direct_work_order)

    chronicle_entry = {
        "schema_version": "codex_chronicle/v1",
        "entry_id": str(uuid.uuid4()),
        "created_at": _iso(_now()),
        "source": "jean-claude-dispatch",
        "author_agent": "jean-claude",
        "workspace_key": bundle["primary_workspace_key"],
        "scope": bundle["scope"],
        "trigger": "sop_dispatch",
        "importance": "high",
        "summary": f"Jean-Claude opened an SOP for `{sop['title']}` and routed it toward {sop['target_agent']}.",
        "signal_types": ["pm", "execution", "delegation", "sop"],
        "decisions": [f"Use `{sop['execution_mode']}` execution for this PM card."],
        "blockers": [],
        "project_updates": [f"SOP written to {sop_path}"],
        "learning_updates": [
            "Workspace execution should stay inside the workspace lane while Jean-Claude carries summaries back to executive leadership."
        ],
        "identity_signals": [],
        "mindset_signals": [
            "Jean-Claude should own delegation and SOP quality rather than turning Neo into the direct executor.",
        ],
        "phrase_signals": [],
        "outcomes": [f"Briefing written to {briefing_path}"],
        "follow_ups": [
            "Workspace execution should report back through PM and result write-back before the next executive standup."
        ],
        "memory_promotions": [],
        "pm_candidates": [],
        "artifacts": [str(sop_path), str(briefing_path), *([str(work_order_path)] if work_order_path is not None else [])],
        "tags": ["jean-claude", "sop", bundle["primary_workspace_key"]],
    }

    if not args.dry_run:
        _append_jsonl(CODEX_HANDOFF_PATH, chronicle_entry)
    updated_card = _update_card(
        imports,
        args.api_url.rstrip("/"),
        card,
        run_id,
        sop_path,
        briefing_path,
        execution_packet_path=work_order_path,
        dry_run=args.dry_run,
    )

    finished_at = _now()
    ledger_entry = {
        "schema_version": "runner_ledger/v1",
        "run_id": run_id,
        "runner_id": RUNNER_ID,
        "owner_agent": "jean-claude",
        "scope": bundle["scope"],
        "primary_workspace_key": bundle["primary_workspace_key"],
        "workspace_scope": bundle["workspace_scope"],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "status": "ok",
        "model": args.model,
        "goal": args.goal,
        "summary": chronicle_entry["summary"],
        "artifacts_written": [
            {"kind": "file", "path": str(input_path), "workspace_key": bundle["primary_workspace_key"], "label": "runner input"},
            {"kind": "file", "path": str(sop_path), "workspace_key": bundle["primary_workspace_key"], "label": "workspace SOP"},
            {"kind": "memo", "path": str(briefing_path), "workspace_key": bundle["primary_workspace_key"], "label": "workspace briefing"},
            *(
                [
                    {
                        "kind": "file",
                        "path": str(work_order_path),
                        "workspace_key": bundle["primary_workspace_key"],
                        "label": "direct execution work order",
                    }
                ]
                if work_order_path is not None
                else []
            ),
            {
                "kind": "file",
                "path": str(CODEX_HANDOFF_PATH),
                "workspace_key": bundle["primary_workspace_key"],
                "label": "chronicle append" if not args.dry_run else "chronicle append (skipped in dry run)",
            },
        ],
        "memory_promotions": [],
        "pm_updates": [
            {
                "action": "move_status",
                "pm_card_id": selected_entry["card_id"],
                "workspace_key": bundle["primary_workspace_key"],
                "scope": bundle["scope"],
                "owner_agent": "jean-claude",
                "title": selected_entry["title"],
                "status": "in_progress",
                "reason": "Jean-Claude opened the workspace SOP and routed execution into the correct lane.",
                "payload": {
                    "execution_state": "running" if sop["execution_mode"] == "direct" else "queued",
                    "target_agent": sop["target_agent"],
                    "execution_mode": sop["execution_mode"],
                    "execution_packet_path": str(work_order_path) if work_order_path is not None else None,
                },
            }
        ],
        "blockers": [],
        "dependencies": [],
        "recommended_next_actions": [
            "Have the direct executor or workspace agent complete the bounded work.",
            "Write the result back through write_execution_result.py before the next executive standup.",
        ],
        "escalations": [],
        "error": None,
        "metadata": {
            "queue_mode": queue_mode,
            "selected_card_id": selected_entry["card_id"],
            "api_url": args.api_url,
            "dry_run": args.dry_run,
            "updated_card_id": updated_card.get("id") if isinstance(updated_card, dict) else None,
        },
    }
    _append_jsonl(ledger_path, ledger_entry)
    if not args.dry_run:
        mirror_runs(
            args.api_url,
            [
                build_run_payload(
                    run_id=f"jean_claude_execution_dispatch::{run_id}",
                    automation_id="jean_claude_execution_dispatch",
                    automation_name="Jean-Claude Execution Dispatch",
                    status="ok",
                    run_at=started_at,
                    finished_at=finished_at,
                    duration_ms=ledger_entry["duration_ms"],
                    owner_agent="Jean-Claude",
                    scope=bundle["scope"],
                    workspace_key=bundle["primary_workspace_key"],
                    action_required=False,
                    metadata={
                        "summary": chronicle_entry["summary"],
                        "result": "dispatched",
                        "selected_card_id": selected_entry["card_id"],
                        "updated_card_id": updated_card.get("id") if isinstance(updated_card, dict) else None,
                        "execution_mode": sop["execution_mode"],
                        "target_agent": sop["target_agent"],
                    },
                )
            ],
        )

    print(chronicle_entry["summary"])
    print(f"Runner input: {input_path}")
    print(f"SOP: {sop_path}")
    print(f"Briefing: {briefing_path}")
    if work_order_path is not None:
        print(f"Work order: {work_order_path}")
    print(f"Ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach PM API at {DEFAULT_API_URL}: {exc}") from exc
