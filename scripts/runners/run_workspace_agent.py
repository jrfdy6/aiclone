#!/usr/bin/env python3
"""Workspace-agent handoff runner.

Consumes one delegated PM card already opened by Jean-Claude, writes a bounded
workspace-agent work order inside that workspace, appends Chronicle, and keeps
the same PM card as the source of truth while the workspace lane executes.
"""
from __future__ import annotations

import argparse
import json
import sys
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
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
REGISTRY_PATH = MEMORY_ROOT / "workspace_registry.json"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
PACK_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md", "CHARTER.md")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from app.services.core_memory_snapshot_service import resolve_live_memory_write_path
from automation_run_mirror import build_run_payload, mirror_runs
from chronicle_memory_contract import build_workspace_memory_contract
from runner_lock import execute_with_runner_lock

CODEX_HANDOFF_PATH = resolve_live_memory_write_path(WORKSPACE_ROOT, "memory/codex_session_handoff.jsonl")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(text: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    return "-".join(part for part in lowered.split("-") if part) or "workspace-agent"


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


def _workspace_root(workspace_key: str, registry: dict[str, dict[str, Any]]) -> Path:
    item = registry.get(workspace_key) or {}
    configured = item.get("filesystem_path")
    if isinstance(configured, str) and configured.strip():
        base = Path(configured)
    else:
        base = WORKSPACE_ROOT / "workspaces" / workspace_key
    for subdir in ("dispatch", "briefings", "docs", "memory", "agent-ledgers"):
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base


def _latest_file(directory: Path, suffix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.glob(f"*{suffix}"))
    return matches[-1] if matches else None


def _merge_unique_strings(values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _build_workspace_execution_contract(
    *,
    workspace_key: str,
    manager_briefing_path: str | None,
    latest_workspace_briefing_path: str | None,
    execution_log_path: str | None,
    task_instructions: list[str],
    acceptance_criteria: list[str],
    completion_contract: dict[str, Any],
) -> dict[str, Any]:
    instructions = [
        f"Execute only inside `{workspace_key}`.",
        "Use the shared PM card as the source of truth.",
        "Treat broader AI Clone context as advisory unless Jean-Claude tied it directly to this workspace card.",
        "Use recent Chronicle plus durable markdown recall before deciding whether to start, unblock, or escalate.",
        "State the lane or trust constraint from the workspace pack that governed your decision.",
        "Name the exact next artifact changed or the blocker preventing it.",
        "Leave PM and Chronicle write-back to the wrapper-owned result path; focus on bounded workspace artifacts and status content.",
    ]
    if manager_briefing_path:
        instructions.append(f"Cite the current Jean-Claude briefing at `{manager_briefing_path}` when reporting status.")
    else:
        instructions.append("If the Jean-Claude briefing is missing, say that directly instead of inventing context.")
    if latest_workspace_briefing_path:
        instructions.append(f"Ground the handoff against the latest workspace briefing at `{latest_workspace_briefing_path}` before proposing new work.")
    if execution_log_path:
        instructions.append(f"Cite the latest workspace execution log at `{execution_log_path}` before proposing new scope.")
    else:
        instructions.append("If no workspace execution log exists yet, say that directly instead of inventing prior execution.")
    instructions.extend(task_instructions)

    base_acceptance = [
        "Status cites the current Jean-Claude briefing or explicitly states that it was missing.",
        "Status cites the latest workspace execution log or explicitly states that it was unavailable.",
        "Status states the lane or trust constraint that governed the recommendation.",
        "Status explains why any imported broader-system context matters to this workspace now.",
        "Status names the exact next artifact updated or the blocker preventing it.",
    ]
    merged_acceptance = _merge_unique_strings(base_acceptance + acceptance_criteria)

    completion_contract_payload = dict(completion_contract or {})
    result_requirements = dict(completion_contract_payload.get("result_requirements") or {})
    result_requirements.setdefault("require_briefing_citation", True)
    result_requirements.setdefault("require_execution_log_citation", True)
    result_requirements.setdefault("require_lane_constraint", True)
    result_requirements.setdefault("require_relevance_explanation_for_global_context", True)
    result_requirements.setdefault("require_exact_next_artifact_or_blocker", True)
    completion_contract_payload["result_requirements"] = result_requirements
    if not completion_contract_payload.get("done_when"):
        completion_contract_payload["done_when"] = merged_acceptance[:6]

    return {
        "instructions": _merge_unique_strings(instructions)[:10],
        "acceptance_criteria": merged_acceptance[:8],
        "completion_contract": completion_contract_payload,
        "local_artifact_context": {
            "manager_briefing_path": manager_briefing_path,
            "latest_workspace_briefing_path": latest_workspace_briefing_path,
            "execution_log_path": execution_log_path,
        },
    }


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


def _load_queue(imports: dict[str, Any], api_url: str, *, workspace_key: str | None, target_agent: str | None, limit: int) -> tuple[str, list[dict[str, Any]]]:
    if imports.get("mode") == "service":
        entries = [
            entry.model_dump(mode="json")
            for entry in imports["list_execution_queue"](
                limit=limit,
                target_agent=target_agent,
                workspace_key=workspace_key,
            )
        ]
        return "service", entries
    query = [f"limit={limit}"]
    if workspace_key:
        query.append(f"workspace_key={workspace_key}")
    if target_agent:
        query.append(f"target_agent={urllib.parse.quote(target_agent)}")
    url = f"{api_url}/api/pm/execution-queue?{'&'.join(query)}"
    entries = _fetch_json(url)
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


def _select_entry(
    entries: list[dict[str, Any]],
    *,
    workspace_key: str | None,
    target_agent: str | None,
    card_id: str | None,
) -> dict[str, Any] | None:
    filtered = []
    for entry in entries:
        if card_id and str(entry.get("card_id") or "") != card_id:
            continue
        if str(entry.get("execution_mode") or "") != "delegated":
            continue
        if str(entry.get("execution_state") or "").lower() not in {"queued", "running"}:
            continue
        if workspace_key and str(entry.get("workspace_key") or "") != workspace_key:
            continue
        if target_agent and str(entry.get("target_agent") or "") != target_agent:
            continue
        filtered.append(entry)
    if not filtered:
        return None
    return sorted(
        filtered,
        key=lambda item: (
            0 if str(item.get("execution_state") or "").lower() == "queued" else 1,
            _parse_datetime(item.get("last_transition_at"))
            or _parse_datetime(item.get("queued_at"))
            or datetime.max.replace(tzinfo=timezone.utc),
        ),
    )[0]


def _update_card(
    imports: dict[str, Any],
    api_url: str,
    card: dict[str, Any],
    *,
    run_id: str,
    work_order_path: Path,
    briefing_path: Path,
    target_agent: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run:
        return None
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    now = _now()
    history = list(execution.get("history") or [])
    history.append(
        {
            "event": "workspace_pickup",
            "state": "running",
            "runner_id": _slug(target_agent),
            "run_id": run_id,
            "requested_by": "Jean-Claude",
            "target_agent": target_agent,
            "at": now.isoformat(),
        }
    )
    execution.update(
        {
            "state": "running",
            "assigned_runner": _slug(target_agent),
            "workspace_agent_run_id": run_id,
            "execution_packet_path": str(work_order_path),
            "executor_status": "queued",
            "executor_worker_id": None,
            "executor_started_at": None,
            "executor_last_error": None,
            "workspace_agent_packet_path": str(work_order_path),
            "workspace_agent_briefing_path": str(briefing_path),
            "workspace_agent_last_report_at": now.isoformat(),
            "last_transition_at": now.isoformat(),
            "history": history[-16:],
        }
    )
    payload["execution"] = execution
    if imports.get("mode") == "service":
        updated = imports["update_card"](
            str(card["id"]),
            imports["PMCardUpdate"](
                status="in_progress",
                payload=payload,
            ),
        )
        return updated.model_dump(mode="json") if updated else None
    return _fetch_json(
        f"{api_url}/api/pm/cards/{card['id']}",
        method="PATCH",
        payload={"status": "in_progress", "payload": payload},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-key")
    parser.add_argument("--agent-name")
    parser.add_argument("--card-id")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--mode", choices=["api", "service"], default="api")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output-root", default=str(MEMORY_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = _now()
    run_id = str(uuid.uuid4())
    stamp = _stamp(started_at)
    imports = _optional_backend_imports(args.mode)
    registry = _read_registry()
    output_root = Path(args.output_root)
    ledger_path = output_root / "runner-ledgers" / "workspace-agents.jsonl"

    workspace_key = args.workspace_key
    target_agent = args.agent_name
    if workspace_key and not target_agent:
        target_agent = str((registry.get(workspace_key) or {}).get("workspace_agent") or "")
    if target_agent is not None and not target_agent.strip():
        target_agent = None

    queue_mode, entries = _load_queue(
        imports,
        args.api_url.rstrip("/"),
        workspace_key=workspace_key,
        target_agent=target_agent,
        limit=args.limit,
    )
    selected_entry = _select_entry(
        entries,
        workspace_key=workspace_key,
        target_agent=target_agent,
        card_id=args.card_id,
    )

    if selected_entry is None:
        summary = (
            f"No delegated workspace-agent execution lane matched {args.card_id}."
            if args.card_id
            else "No delegated workspace-agent execution lanes are currently queued or running."
        )
        finished_at = _now()
        _append_jsonl(
            ledger_path,
            {
                "schema_version": "runner_ledger/v1",
                "run_id": run_id,
                "runner_id": "workspace-agent",
                "owner_agent": target_agent or "workspace-agent",
                "scope": "workspace",
                "primary_workspace_key": workspace_key,
                "workspace_scope": [workspace_key] if workspace_key else [],
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
                "status": "noop",
                "summary": summary,
                "artifacts_written": [],
                "memory_promotions": [],
                "pm_updates": [],
                "blockers": [],
                "dependencies": [],
                "recommended_next_actions": [],
                "escalations": [],
                "error": None,
                "metadata": {"queue_mode": queue_mode, "workspace_key": workspace_key, "target_agent": target_agent, "dry_run": args.dry_run},
            },
        )
        if not args.dry_run:
            mirror_runs(
                args.api_url,
                [
                    build_run_payload(
                        run_id=f"workspace_agent_dispatch::{run_id}",
                        automation_id="workspace_agent_dispatch",
                        automation_name="Workspace Agent Dispatch",
                        status="ok",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                        owner_agent=target_agent,
                        scope="workspace",
                        workspace_key=workspace_key,
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

    workspace_key = str(selected_entry.get("workspace_key") or workspace_key or "shared_ops")
    target_agent = str(selected_entry.get("target_agent") or target_agent or "Workspace Agent")
    card = _load_card(imports, args.api_url.rstrip("/"), str(selected_entry["card_id"]))
    workspace_root = _workspace_root(workspace_key, registry)
    card_payload = dict(card.get("payload") or {})
    execution = dict(card_payload.get("execution") or {})
    sop_path = Path(str(execution.get("sop_path") or ""))
    briefing_source = execution.get("briefing_path")
    memory_contract = build_workspace_memory_contract(
        workspace_key,
        seed_texts=[
            selected_entry.get("title"),
            selected_entry.get("reason"),
            card.get("title"),
            card_payload.get("reason"),
            target_agent,
        ],
        memory_paths=(
            "memory/persistent_state.md",
            "memory/cron-prune.md",
            "memory/daily-briefs.md",
            "memory/{today}.md",
        ),
        include_shared_ops=False,
    )
    input_path = output_root / "runner-inputs" / _slug(target_agent) / f"{stamp}.json"
    work_order_path = workspace_root / "dispatch" / f"{stamp}_{_slug(target_agent)}_work_order.json"
    briefing_path = workspace_root / "briefings" / f"{stamp}_{_slug(target_agent)}_status.md"
    local_ledger_path = workspace_root / "agent-ledgers" / f"{_slug(target_agent)}.jsonl"
    latest_workspace_briefing = _latest_file(workspace_root / "briefings", ".md")
    execution_log_path = workspace_root / "memory" / "execution_log.md"

    bundle = {
        "schema_version": "workspace_agent_input/v1",
        "run_id": run_id,
        "runner_id": _slug(target_agent),
        "owner_agent": target_agent,
        "workspace_key": workspace_key,
        "workspace_root": str(workspace_root),
        "pm_card": card,
        "queue_entry": selected_entry,
        "sop_path": str(sop_path) if sop_path else None,
        "manager_agent": "Jean-Claude",
        "briefing_source_path": str(briefing_source) if briefing_source else None,
        "manager_pack": _load_pack(WORKSPACE_ROOT / "agents" / "jean-claude"),
        "workspace_pack": _load_pack(workspace_root),
        "base_pack": _load_pack(WORKSPACE_ROOT),
        "recent_chronicle_entries": memory_contract["chronicle_entries"],
        "durable_memory_context": memory_contract["durable_memory_context"],
        "memory_context": memory_contract["memory_context"],
        "source_paths": memory_contract["source_paths"],
    }
    card_payload = dict(card.get("payload") or {})
    task_instructions = [
        str(item).strip()
        for item in card_payload.get("instructions") or []
        if str(item).strip()
    ]
    acceptance_criteria = [
        str(item).strip()
        for item in card_payload.get("acceptance_criteria") or []
        if str(item).strip()
    ]
    artifacts_expected = [
        str(item).strip()
        for item in card_payload.get("artifacts_expected") or []
        if str(item).strip()
    ]
    artifact_context = _build_workspace_execution_contract(
        workspace_key=workspace_key,
        manager_briefing_path=str(briefing_source) if briefing_source else None,
        latest_workspace_briefing_path=str(latest_workspace_briefing) if latest_workspace_briefing else None,
        execution_log_path=str(execution_log_path) if execution_log_path.exists() else None,
        task_instructions=task_instructions,
        acceptance_criteria=acceptance_criteria,
        completion_contract=dict(card_payload.get("completion_contract") or {}),
    )
    work_order = {
        "schema_version": "workspace_agent_work_order/v1",
        "run_id": run_id,
        "workspace_key": workspace_key,
        "workspace_root": str(workspace_root),
        "repo_path": str(card_payload.get("repo_path") or WORKSPACE_ROOT),
        "front_door_agent": card_payload.get("front_door_agent") or card.get("owner") or "Neo",
        "manager_agent": "Jean-Claude",
        "workspace_agent": target_agent,
        "owner_agent": target_agent,
        "target_agent": target_agent,
        "card_id": selected_entry["card_id"],
        "title": selected_entry["title"],
        "objective": f"{target_agent} should execute this work only inside `{workspace_key}` and report back to Jean-Claude with a bounded status briefing.",
        "sop_path": str(sop_path) if sop_path else None,
        "briefing_path": str(briefing_path),
        "pm_card_id": selected_entry["card_id"],
        "reason": selected_entry.get("reason"),
        "instructions": artifact_context["instructions"],
        "acceptance_criteria": artifact_context["acceptance_criteria"],
        "artifacts_expected": artifacts_expected,
        "completion_contract": artifact_context["completion_contract"],
        "read_order": [
            "Read the local workspace pack first.",
            "Read Jean-Claude's SOP and briefing second.",
            "Read the PM card before executing or declaring completion.",
            "Read recent Chronicle entries, durable memory recall, and core memory tails before changing scope.",
        ],
        "identity_sources": {
            "workspace_pack": bundle["workspace_pack"],
            "manager_pack": bundle["manager_pack"],
        },
        "write_back_contract": {
            "pm_card_id": selected_entry["card_id"],
            "preferred_runner_id": _slug(target_agent),
            "preferred_author_agent": target_agent,
            "next_state_on_result": "review",
        },
        "context_policy": {
            "manager_scope": "Jean-Claude may use whole-system AI Clone context before delegation.",
            "workspace_scope": f"{target_agent} executes only inside `{workspace_key}`.",
            "relevance_rule": "If wider-system context matters here, say why it matters to this workspace now.",
        },
        "local_artifact_context": artifact_context["local_artifact_context"],
        "recent_chronicle_entries": memory_contract["chronicle_entries"],
        "durable_memory_context": memory_contract["durable_memory_context"],
        "memory_context": memory_contract["memory_context"],
        "source_paths": memory_contract["source_paths"],
    }

    _write_json(input_path, bundle)
    _write_json(work_order_path, work_order)

    briefing_lines = [
        f"# {target_agent} Intake Brief",
        "",
        f"- Workspace: `{workspace_key}`",
        f"- Manager: `Jean-Claude`",
        f"- PM card: `{selected_entry['card_id']}`",
        f"- Title: {selected_entry['title']}",
        "",
        "## Expectation",
        f"{target_agent} owns execution inside this workspace only and should report back through the shared PM card when the work is done or blocked.",
        "",
        "## Inputs",
        f"- Workspace pack: `{workspace_root / 'AGENTS.md'}`",
        f"- Workspace identity: `{workspace_root / 'IDENTITY.md'}`",
        f"- Workspace soul: `{workspace_root / 'SOUL.md'}`",
        f"- SOP: `{sop_path}`" if sop_path else "- SOP: `missing`",
        f"- Jean-Claude briefing: `{briefing_source}`" if briefing_source else "- Jean-Claude briefing: `missing`",
        f"- Latest workspace briefing: `{latest_workspace_briefing}`" if latest_workspace_briefing else "- Latest workspace briefing: `missing`",
        f"- Workspace execution log: `{execution_log_path}`" if execution_log_path.exists() else "- Workspace execution log: `missing`",
        f"- Recent Chronicle source: `{CODEX_HANDOFF_PATH}`",
        "",
        "## Recent Chronicle",
    ]
    chronicle_entries = memory_contract["chronicle_entries"]
    if not chronicle_entries:
        briefing_lines.append("- None in the latest Chronicle window.")
    else:
        for entry in chronicle_entries[-3:]:
            summary = str(entry.get("summary") or "Untitled Chronicle entry").strip()
            briefing_lines.append(f"- {summary}")
    briefing_lines.extend(
        [
            "",
            "## Durable Memory Recall",
        ]
    )
    durable_results = (memory_contract["durable_memory_context"].get("results") or [])[:3]
    if not durable_results:
        briefing_lines.append("- None surfaced for this lane.")
    else:
        for item in durable_results:
            title = str(item.get("title") or "Untitled").strip()
            path_str = str(item.get("path") or "").strip()
            excerpt = str(item.get("excerpt") or "").strip()
            if excerpt:
                briefing_lines.append(f"- `{title}` ({path_str}): {excerpt}")
            else:
                briefing_lines.append(f"- `{title}` ({path_str})")
    briefing_lines.extend(
        [
            "",
            "## Core Memory Context",
        ]
    )
    for key, value in (memory_contract["memory_context"] or {}).items():
        if not value:
            continue
        label = key.replace("_tail", "").replace("_", " ")
        briefing_lines.append(f"- {label}: {value[-280:]}")
    briefing_lines.extend(
        [
            "",
        "## Next",
        f"- Execute inside `{workspace_key}`.",
        "- Keep the PM card as the source of truth.",
        "- Cite the latest briefing and execution log in the result, or say clearly when one is missing.",
        "- If broader-system context matters, explain why it matters to this workspace now.",
        "- Write the result back with the execution-result writer before the next executive standup.",
    ])
    briefing_path.write_text("\n".join(briefing_lines).rstrip() + "\n", encoding="utf-8")

    chronicle_entry = {
        "schema_version": "codex_chronicle/v1",
        "entry_id": str(uuid.uuid4()),
        "created_at": _iso(_now()),
        "source": "workspace-agent-handoff",
        "author_agent": target_agent,
        "workspace_key": workspace_key,
        "scope": "workspace",
        "trigger": "workspace_pickup",
        "importance": "high",
        "summary": f"{target_agent} accepted Jean-Claude's SOP for `{selected_entry['title']}` inside `{workspace_key}`.",
        "signal_types": ["pm", "workspace_execution", "delegation"],
        "decisions": [f"Keep execution inside `{workspace_key}` and return status through the same PM card."],
        "blockers": [],
        "project_updates": [f"Workspace-agent work order written to {work_order_path}"],
        "learning_updates": [
            "Delegated workspace execution should stay local while only briefings and PM truth move back to executive leadership."
        ],
        "identity_signals": [],
        "mindset_signals": [],
        "phrase_signals": [],
        "outcomes": [f"Workspace-agent briefing written to {briefing_path}"],
        "follow_ups": ["Complete or unblock the SOP and write the result back through the shared execution writer."],
        "memory_promotions": [],
        "pm_candidates": [],
        "artifacts": [str(work_order_path), str(briefing_path)],
        "tags": ["workspace-agent", target_agent, workspace_key],
    }

    if not args.dry_run:
        _append_jsonl(CODEX_HANDOFF_PATH, chronicle_entry)
    _append_jsonl(local_ledger_path, chronicle_entry)
    updated_card = _update_card(
        imports,
        args.api_url.rstrip("/"),
        card,
        run_id=run_id,
        work_order_path=work_order_path,
        briefing_path=briefing_path,
        target_agent=target_agent,
        dry_run=args.dry_run,
    )

    finished_at = _now()
    ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": "workspace-agent",
            "owner_agent": target_agent,
            "scope": "workspace",
            "primary_workspace_key": workspace_key,
            "workspace_scope": [workspace_key],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": "ok",
            "summary": chronicle_entry["summary"],
            "artifacts_written": [
                {"kind": "file", "path": str(input_path), "workspace_key": workspace_key, "label": "workspace-agent input"},
                {"kind": "file", "path": str(work_order_path), "workspace_key": workspace_key, "label": "workspace-agent work order"},
                {"kind": "memo", "path": str(briefing_path), "workspace_key": workspace_key, "label": "workspace-agent briefing"},
            ],
            "memory_promotions": [],
            "pm_updates": [
                {
                    "action": "running_handoff",
                    "pm_card_id": selected_entry["card_id"],
                    "workspace_key": workspace_key,
                    "owner_agent": target_agent,
                    "status": "in_progress",
                    "reason": "Workspace agent accepted the delegated lane and is now executing inside the workspace.",
                    "payload": {
                        "execution_state": "running",
                        "workspace_agent": target_agent,
                        "workspace_agent_packet_path": str(work_order_path),
                    },
                }
            ],
            "blockers": [],
            "dependencies": [],
            "recommended_next_actions": [
                "Execute the workspace SOP inside the lane.",
                "Write the result back through write_execution_result.py when done or blocked.",
            ],
            "escalations": [],
            "error": None,
            "metadata": {
                "queue_mode": queue_mode,
                "selected_card_id": selected_entry["card_id"],
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
                    run_id=f"workspace_agent_dispatch::{run_id}",
                    automation_id="workspace_agent_dispatch",
                    automation_name="Workspace Agent Dispatch",
                    status="ok",
                    run_at=started_at,
                    finished_at=finished_at,
                    duration_ms=ledger_entry["duration_ms"],
                    owner_agent=target_agent,
                    scope="workspace",
                    workspace_key=workspace_key,
                    action_required=False,
                    metadata={
                        "summary": chronicle_entry["summary"],
                        "result": "workspace_pickup",
                        "selected_card_id": selected_entry["card_id"],
                        "updated_card_id": updated_card.get("id") if isinstance(updated_card, dict) else None,
                    },
                )
            ],
        )

    print(chronicle_entry["summary"])
    print(f"Workspace-agent input: {input_path}")
    print(f"Work order: {work_order_path}")
    print(f"Briefing: {briefing_path}")
    print(f"Ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            execute_with_runner_lock(
                lock_name="workspace_agent_dispatch",
                automation_id="workspace_agent_dispatch",
                automation_name="Workspace Agent Dispatch",
                default_api_url=DEFAULT_API_URL,
                main_func=main,
                scope="workspace",
            )
        )
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach PM API at {DEFAULT_API_URL}: {exc}") from exc
