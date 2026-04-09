#!/usr/bin/env python3
"""Write execution results back into PM state, Chronicle, and durable memory."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
CODEX_HANDOFF_PATH = MEMORY_ROOT / "codex_session_handoff.jsonl"
SCRIPT_DIR = WORKSPACE_ROOT / "scripts"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_list(values: list[str] | None, file_path: str | None) -> list[str]:
    items = [value.strip() for value in (values or []) if value and value.strip()]
    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")
        items.extend(line.strip() for line in text.splitlines() if line.strip())
    return items


def _read_summary(args: argparse.Namespace) -> str:
    if args.summary is not None:
        return args.summary.strip()
    if args.summary_file is not None:
        return Path(args.summary_file).read_text(encoding="utf-8").strip()
    return sys.stdin.read().strip()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _append_markdown(path: Path, heading: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "append_markdown_block.py"),
        str(path),
        "--heading",
        heading,
        "--body",
        body,
    ]
    subprocess.run(cmd, check=True)


def _parse_work_order_context(work_order: dict[str, Any], work_order_path: Path) -> dict[str, Any]:
    brief = work_order.get("execution_brief")
    if isinstance(brief, dict):
        card_id = str(brief.get("card_id") or "")
        workspace_key = str(brief.get("workspace_key") or "shared_ops")
        title = str(brief.get("title") or "Untitled execution")
        workspace_root = None
    else:
        card_id = str(work_order.get("pm_card_id") or work_order.get("card_id") or "")
        workspace_key = str(work_order.get("workspace_key") or "shared_ops")
        title = str(work_order.get("title") or "Untitled execution")
        workspace_root = work_order_path.parent.parent if work_order_path.parent.name == "dispatch" else None
    if not card_id:
        raise SystemExit("Work order is missing a PM card id.")
    return {
        "card_id": card_id,
        "workspace_key": workspace_key,
        "title": title,
        "workspace_root": workspace_root,
        "preferred_target_agent": work_order.get("workspace_agent") or work_order.get("owner_agent"),
    }


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _optional_backend_imports() -> dict[str, Any]:
    if not any(os.getenv(name) for name in ("OPEN_BRAIN_DATABASE_URL", "BRAIN_VECTOR_DATABASE_URL", "DATABASE_URL")):
        return {"mode": "api"}
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {}
    try:
        from app.models import PMCardUpdate  # type: ignore
        from app.services.pm_card_service import get_card, update_card  # type: ignore

        loaded["PMCardUpdate"] = PMCardUpdate
        loaded["get_card"] = get_card
        loaded["update_card"] = update_card
        loaded["mode"] = "service"
    except Exception as exc:  # pragma: no cover - runtime dependent
        loaded["mode"] = "api"
        loaded["error"] = str(exc)
    return loaded


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


def _update_card(imports: dict[str, Any], api_url: str, card_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if imports.get("mode") == "service":
        updated = imports["update_card"](
            card_id,
            imports["PMCardUpdate"](
                status=payload["status"],
                payload=payload["payload"],
            ),
        )
        if updated is None:
            raise SystemExit(f"Failed to update PM card {card_id}")
        return updated.model_dump(mode="json")
    return _fetch_json(f"{api_url}/api/pm/cards/{card_id}", method="PATCH", payload=payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-order", required=True, help="Path to a runner or workspace-agent work order JSON.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--force-api", action="store_true", help="Skip backend service imports and write back through the API only.")
    parser.add_argument("--runner-id", default="neo")
    parser.add_argument("--author-agent", default="neo")
    parser.add_argument("--status", default="review", choices=["review", "done", "blocked"])
    parser.add_argument("--summary", help="Short summary of what the execution produced.")
    parser.add_argument("--summary-file")
    parser.add_argument("--blocker", action="append", dest="blockers")
    parser.add_argument("--blocker-file")
    parser.add_argument("--decision", action="append", dest="decisions")
    parser.add_argument("--decision-file")
    parser.add_argument("--learning", action="append", dest="learnings")
    parser.add_argument("--learning-file")
    parser.add_argument("--outcome", action="append", dest="outcomes")
    parser.add_argument("--outcome-file")
    parser.add_argument("--follow-up", action="append", dest="follow_ups")
    parser.add_argument("--follow-up-file")
    parser.add_argument("--project-update", action="append", dest="project_updates")
    parser.add_argument("--project-update-file")
    parser.add_argument("--memory-promotion", action="append", dest="memory_promotions")
    parser.add_argument("--memory-promotion-file")
    parser.add_argument("--persistent-state", action="append", dest="persistent_state")
    parser.add_argument("--persistent-state-file")
    parser.add_argument("--artifact", action="append", dest="artifacts")
    parser.add_argument("--artifact-file")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = _read_summary(args)
    if not summary:
        raise SystemExit("A non-empty summary is required.")

    work_order_path = Path(args.work_order).expanduser()
    if not work_order_path.exists():
        raise SystemExit(f"Work order not found: {work_order_path}")
    work_order = json.loads(work_order_path.read_text(encoding="utf-8"))
    context = _parse_work_order_context(work_order, work_order_path)
    card_id = str(context["card_id"])
    workspace_key = str(context["workspace_key"])
    title = str(context["title"])
    workspace_root = context.get("workspace_root")
    preferred_target_agent = context.get("preferred_target_agent")
    now = _now()
    stamp = _stamp(now)
    result_id = str(uuid.uuid4())

    imports = {"mode": "api"} if args.force_api else _optional_backend_imports()
    pm_api_available = True
    try:
        card = _load_card(imports, args.api_url.rstrip("/"), card_id)
    except urllib.error.URLError as exc:
        pm_api_available = False
        card = {"payload": {}}
        print(f"[write_execution_result] Warning: PM API unreachable at {args.api_url.rstrip('/')}: {exc}. Continuing in offline mode.")

    decisions = _read_list(args.decisions, args.decision_file)
    blockers = _read_list(args.blockers, args.blocker_file)
    learnings = _read_list(args.learnings, args.learning_file)
    outcomes = _read_list(args.outcomes, args.outcome_file)
    follow_ups = _read_list(args.follow_ups, args.follow_up_file)
    project_updates = _read_list(args.project_updates, args.project_update_file)
    memory_promotions = _read_list(args.memory_promotions, args.memory_promotion_file)
    persistent_state = _read_list(args.persistent_state, args.persistent_state_file)
    artifacts = _read_list(args.artifacts, args.artifact_file)

    result_payload = {
        "schema_version": "execution_result/v1",
        "result_id": result_id,
        "runner_id": args.runner_id,
        "author_agent": args.author_agent,
        "created_at": _iso(now),
        "workspace_key": workspace_key,
        "card_id": card_id,
        "title": title,
        "status": args.status,
        "summary": summary,
        "blockers": blockers,
        "decisions": decisions,
        "learnings": learnings,
        "outcomes": outcomes,
        "follow_ups": follow_ups,
        "project_updates": project_updates,
        "memory_promotions": memory_promotions,
        "persistent_state_updates": persistent_state,
        "artifacts": [str(work_order_path), *artifacts],
    }

    result_path = MEMORY_ROOT / "runner-results" / args.runner_id / f"{stamp}.json"
    memo_path = MEMORY_ROOT / "runner-memos" / args.runner_id / f"{stamp}_execution_result.md"
    daily_path = MEMORY_ROOT / f"{datetime.now().astimezone().date().isoformat()}.md"
    workspace_memory_path = (
        workspace_root.resolve() / "memory" / "execution_log.md"
        if isinstance(workspace_root, Path)
        else None
    )

    _write_json(result_path, result_payload)

    memo_lines = [
        f"# Execution Result - {title}",
        "",
        f"- Card: `{card_id}`",
        f"- Workspace: `{workspace_key}`",
        f"- Status: `{args.status}`",
        "",
        "## Summary",
        summary,
        "",
        "## Blockers",
    ]
    for item in blockers or ["None."]:
        memo_lines.append(f"- {item}")
    memo_lines.extend([
        "",
        "## Decisions",
    ])
    for item in decisions or ["None."]:
        memo_lines.append(f"- {item}")
    memo_lines.extend(["", "## Learnings"])
    for item in learnings or ["None."]:
        memo_lines.append(f"- {item}")
    memo_lines.extend(["", "## Outcomes"])
    for item in outcomes or ["None."]:
        memo_lines.append(f"- {item}")
    memo_lines.extend(["", "## Follow-ups"])
    for item in follow_ups or ["None."]:
        memo_lines.append(f"- {item}")
    memo_path.parent.mkdir(parents=True, exist_ok=True)
    memo_path.write_text("\n".join(memo_lines).rstrip() + "\n", encoding="utf-8")

    chronicle_entry = {
        "schema_version": "codex_chronicle/v1",
        "entry_id": str(uuid.uuid4()),
        "created_at": _iso(now),
        "source": f"{args.runner_id}-execution-result",
        "author_agent": args.author_agent,
        "workspace_key": workspace_key,
        "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
        "trigger": "execution_result",
        "importance": "high",
        "summary": summary,
        "signal_types": ["execution", "learning", "outcome", "pm"],
        "decisions": decisions,
        "blockers": blockers,
        "project_updates": project_updates or [f"Execution result recorded for `{title}`."],
        "learning_updates": learnings,
        "identity_signals": [],
        "mindset_signals": [
            "Execution results should feed the same memory loop that standups and OpenClaw already trust.",
        ],
        "phrase_signals": [],
        "outcomes": outcomes or [f"Execution result file written to {result_path}"],
        "follow_ups": follow_ups,
        "memory_promotions": memory_promotions + persistent_state,
        "pm_candidates": follow_ups,
        "artifacts": [str(result_path), str(memo_path), str(work_order_path), *artifacts],
        "tags": [args.runner_id, "execution-result", workspace_key],
    }

    daily_lines = [
        f"- Card: `{card_id}`",
        f"- Workspace: `{workspace_key}`",
        f"- Result: {summary}",
    ]
    if outcomes:
        daily_lines.append("")
        daily_lines.append("### Outcomes")
        daily_lines.extend(f"- {item}" for item in outcomes)
    if blockers:
        daily_lines.append("")
        daily_lines.append("### Blockers")
        daily_lines.extend(f"- {item}" for item in blockers)
    if follow_ups:
        daily_lines.append("")
        daily_lines.append("### Follow-ups")
        daily_lines.extend(f"- {item}" for item in follow_ups)

    if not args.dry_run:
        _append_jsonl(CODEX_HANDOFF_PATH, chronicle_entry)
        _append_markdown(
            daily_path,
            f"## {args.runner_id.capitalize()} Execution Result — {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}",
            "\n".join(daily_lines),
        )
        if workspace_memory_path is not None:
            _append_markdown(
                workspace_memory_path,
                f"## {args.author_agent} Workspace Result — {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}",
                "\n".join(daily_lines),
            )
        if learnings:
            _append_markdown(
                MEMORY_ROOT / "LEARNINGS.md",
                f"## {args.runner_id.capitalize()} Execution Learnings — {datetime.now().astimezone():%Y-%m-%d}",
                "\n".join(f"- {item}" for item in learnings),
            )
        if memory_promotions or persistent_state:
            _append_markdown(
                MEMORY_ROOT / "persistent_state.md",
                f"## {args.runner_id.capitalize()} Execution State — {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}",
                "\n".join(f"- {item}" for item in [*memory_promotions, *persistent_state]),
            )

    execution = dict((card.get("payload") or {}).get("execution") or {})
    history = list(execution.get("history") or [])
    next_execution_state = args.status
    next_pm_status = "done" if args.status == "done" else ("blocked" if args.status == "blocked" else "review")
    next_target_agent = execution.get("target_agent") or preferred_target_agent or args.author_agent
    next_assigned_runner = args.runner_id
    if args.status == "blocked":
        next_execution_state = "queued"
        next_target_agent = "Jean-Claude"
        next_assigned_runner = "jean-claude"
    history.append(
        {
            "event": "blocked_return" if args.status == "blocked" else "result",
            "state": next_execution_state,
            "runner_id": args.runner_id,
            "requested_by": args.author_agent,
            "at": now.isoformat(),
            "result_id": result_id,
        }
    )
    execution.update(
        {
            "state": next_execution_state,
            "target_agent": next_target_agent,
            "assigned_runner": next_assigned_runner,
            "manager_agent": execution.get("manager_agent") or "Jean-Claude",
            "manager_attention_required": args.status == "blocked",
            "workspace_agent": execution.get("workspace_agent") or preferred_target_agent,
            "execution_mode": "direct" if args.status == "blocked" else execution.get("execution_mode"),
            "executor_status": "completed",
            "executor_finished_at": now.isoformat(),
            "executor_last_error": None,
            "returned_from_agent": args.author_agent if args.status == "blocked" else execution.get("returned_from_agent"),
            "queued_at": now.isoformat() if args.status == "blocked" else execution.get("queued_at"),
            "last_transition_at": now.isoformat(),
            "result_id": result_id,
            "result_path": str(result_path),
            "workspace_result_path": str(workspace_memory_path) if workspace_memory_path is not None else None,
            "history": history[-12:],
        }
    )
    payload = dict(card.get("payload") or {})
    payload["execution"] = execution
    payload["latest_execution_result"] = {
        "result_id": result_id,
        "summary": summary,
        "status": args.status,
        "result_path": str(result_path),
        "memo_path": str(memo_path),
        "blockers": blockers,
        "follow_ups": follow_ups,
        "learnings": learnings,
        "outcomes": outcomes,
        "artifacts": [str(result_path), str(memo_path), str(work_order_path), *artifacts],
    }

    if not args.dry_run and pm_api_available:
        updated = _update_card(
            imports,
            args.api_url.rstrip("/"),
            card_id,
            {
                "status": next_pm_status,
                "payload": payload,
            },
        )
    else:
        updated = {"id": card_id, "status": next_pm_status, "payload": payload}
        if not pm_api_available:
            print(f"[write_execution_result] Offline mode: skipped updating PM API, wrote local artifacts only.")

    print(f"Execution result written for {title}")
    print(f"Result JSON: {result_path}")
    print(f"Result memo: {memo_path}")
    print(f"Updated PM card: {updated.get('id')} -> {updated.get('status')}")
    if args.dry_run:
        print("Dry run: Chronicle and durable memory writes were skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
