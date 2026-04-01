#!/usr/bin/env python3
"""Neo queue runner.

Consumes one queued PM card from the Codex execution queue, writes a bounded
execution packet for the next worker, appends a Chronicle event, and moves the
same PM card into a running state.

This runner does not pretend the underlying work is complete. Its job is to
turn queued board work into an explicit execution packet and preserve the same
PM card as the source of truth.
"""
from __future__ import annotations

import argparse
import json
import os
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
RUNNER_ID = "neo"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
PACK_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md", "CHARTER.md")


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
        handle.write(json.dumps(payload, default=_json_default) + "\n")


def _read_jsonl_tail(path: Path, *, max_items: int = 6) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                items.append(payload)
    return items[-max_items:]


def _tail_text(path: Path, *, max_chars: int = 1200) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return text[-max_chars:]


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


def _optional_backend_imports() -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {}
    try:
        from app.models import PMCardUpdate  # type: ignore
        from app.services.pm_card_service import list_cards, list_execution_queue, update_card  # type: ignore

        loaded["PMCardUpdate"] = PMCardUpdate
        loaded["list_cards"] = list_cards
        loaded["list_execution_queue"] = list_execution_queue
        loaded["update_card"] = update_card
        loaded["mode"] = "service"
    except Exception as exc:  # pragma: no cover - environment dependent
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


def _load_queue(imports: dict[str, Any], api_url: str, limit: int) -> tuple[str, list[dict[str, Any]]]:
    if imports.get("mode") == "service":
        entries = [entry.model_dump(mode="json") for entry in imports["list_execution_queue"](limit=limit, target_agent="Neo", execution_state="queued")]
        return "service", entries
    entries = _fetch_json(f"{api_url}/api/pm/execution-queue?target_agent=Neo&execution_state=queued&limit={limit}")
    return "api", entries if isinstance(entries, list) else []


def _load_cards(imports: dict[str, Any], api_url: str, limit: int) -> list[dict[str, Any]]:
    if imports.get("mode") == "service":
        return [card.model_dump(mode="json") for card in imports["list_cards"](limit=limit)]
    payload = _fetch_json(f"{api_url}/api/pm/cards?limit={limit}")
    return payload if isinstance(payload, list) else []


def _select_next_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    return sorted(entries, key=lambda item: _parse_datetime(item.get("queued_at")) or _parse_datetime(item.get("last_transition_at")) or datetime.max.replace(tzinfo=timezone.utc))[0]


def _build_input_bundle(
    *,
    run_id: str,
    args: argparse.Namespace,
    selected_entry: dict[str, Any],
    selected_card: dict[str, Any],
    queue_snapshot: list[dict[str, Any]],
) -> dict[str, Any]:
    workspace_key = str(selected_entry.get("workspace_key") or "shared_ops")
    chronicle_tail = _read_jsonl_tail(CODEX_HANDOFF_PATH, max_items=6)
    return {
        "schema_version": "runner_input/v1",
        "run_id": run_id,
        "runner_id": RUNNER_ID,
        "owner_agent": RUNNER_ID,
        "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
        "workspace_scope": [workspace_key],
        "primary_workspace_key": workspace_key,
        "goal": args.goal or f"Advance queued PM card: {selected_entry.get('title')}",
        "run_mode": "manual",
        "time_budget_minutes": args.time_budget_minutes,
        "model": args.model,
        "dry_run": args.dry_run,
        "allowed_paths": [str(WORKSPACE_ROOT)],
        "allowed_command_prefixes": ["rg", "sed", "cat", "git status"],
        "pm_context": {
            "selected_card": selected_card,
            "queue_depth": len(queue_snapshot),
            "queue_snapshot": queue_snapshot[:10],
        },
        "codex_handoff_context": {"recent_entries": chronicle_tail, "path": str(CODEX_HANDOFF_PATH)},
        "codex_chronicle_context": {"recent_entries": chronicle_tail, "path": str(CODEX_HANDOFF_PATH)},
        "automation_context": {
            "source": "pm_execution_queue",
            "queue_entry": selected_entry,
        },
        "previous_run_context": {},
        "agent_pack": _load_pack(WORKSPACE_ROOT / "agents" / "neo"),
        "base_pack": _load_pack(WORKSPACE_ROOT),
        "role_payload": {
            "selected_card_id": selected_entry.get("card_id"),
            "selected_title": selected_entry.get("title"),
            "target_agent": selected_entry.get("target_agent") or "Neo",
            "dispatch_mode": "queue_consumer",
            "linked_standup_id": selected_card.get("link_id"),
        },
    }


def _build_execution_packet(bundle: dict[str, Any]) -> dict[str, Any]:
    selected_card = (bundle.get("pm_context") or {}).get("selected_card") or {}
    selected_entry = (bundle.get("automation_context") or {}).get("queue_entry") or {}
    workspace_key = str(selected_entry.get("workspace_key") or "shared_ops")
    reason = str(selected_entry.get("reason") or selected_card.get("payload", {}).get("reason") or "Advance the queued PM card.")
    follow_ups = [
        "Use this packet as the bounded brief for the next Codex worker.",
        "Write execution results back to the same PM card before closing the loop.",
        "Append a Chronicle event that captures what changed, what was learned, and what is next.",
    ]
    return {
        "schema_version": "runner_output/v1",
        "run_id": bundle["run_id"],
        "runner_id": RUNNER_ID,
        "owner_agent": RUNNER_ID,
        "status": "ok",
        "scope": bundle["scope"],
        "workspaces_touched": bundle["workspace_scope"],
        "summary": f"Neo picked up `{selected_entry.get('title')}` from the PM queue and opened a Codex execution packet.",
        "artifacts_written": [],
        "codex_handoff_write": None,
        "memory_promotions": [],
        "pm_updates": [
            {
                "action": "move_status",
                "pm_card_id": selected_entry.get("card_id"),
                "workspace_key": workspace_key,
                "scope": bundle["scope"],
                "owner_agent": RUNNER_ID,
                "title": selected_entry.get("title"),
                "status": "in_progress",
                "reason": "Neo runner picked up the queued PM card and opened a bounded execution packet.",
                "payload": {
                    "execution_state": "running",
                    "target_agent": selected_entry.get("target_agent") or "Neo",
                },
            }
        ],
        "blockers": [],
        "dependencies": [],
        "recommended_next_actions": follow_ups,
        "escalations": [],
        "role_payload": {
            "selected_card_id": selected_entry.get("card_id"),
            "linked_standup_id": selected_card.get("link_id"),
            "workspace_key": workspace_key,
            "execution_reason": reason,
            "subagent_ready": True,
        },
        "execution_brief": {
            "card_id": selected_entry.get("card_id"),
            "title": selected_entry.get("title"),
            "workspace_key": workspace_key,
            "objective": reason,
            "linked_standup_id": selected_card.get("link_id"),
            "source": selected_card.get("source"),
            "guardrails": [
                "Stay inside the PM card scope.",
                "Do not close the card without writing results back.",
                "Prefer bounded workspace changes over broad system changes.",
            ],
            "write_back_contract": {
                "pm_card_id": selected_entry.get("card_id"),
                "next_execution_state": "review",
                "chronicle_write_required": True,
            },
        },
    }


def _write_markdown_memo(path: Path, bundle: dict[str, Any], output: dict[str, Any]) -> None:
    selected_card = (bundle.get("pm_context") or {}).get("selected_card") or {}
    brief = output.get("execution_brief") or {}
    lines = [
        f"# Neo Execution Pickup - {_iso(_now())}",
        "",
        "## PM Card",
        f"- title: {selected_card.get('title') or 'Unknown'}",
        f"- id: `{selected_card.get('id') or 'unknown'}`",
        f"- workspace: `{brief.get('workspace_key') or 'shared_ops'}`",
        "",
        "## Objective",
        str(brief.get("objective") or "Advance the queued PM card."),
        "",
        "## Guardrails",
    ]
    for item in brief.get("guardrails") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Actions"])
    for item in output.get("recommended_next_actions") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Related Chronicle Signal"])
    chronicle_tail = _read_jsonl_tail(CODEX_HANDOFF_PATH, max_items=1)
    if chronicle_tail:
        lines.append(f"- {chronicle_tail[-1].get('summary')}")
    else:
        lines.append("- No recent Chronicle entry available.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _chronicle_entry(*, output: dict[str, Any], memo_path: Path, work_order_path: Path) -> dict[str, Any]:
    brief = output.get("execution_brief") or {}
    return {
        "schema_version": "codex_chronicle/v1",
        "entry_id": str(uuid.uuid4()),
        "created_at": _iso(_now()),
        "source": "neo-runner",
        "author_agent": "neo",
        "workspace_key": brief.get("workspace_key") or "shared_ops",
        "scope": output.get("scope") or "shared_ops",
        "trigger": "pm_queue_pickup",
        "importance": "high",
        "summary": output["summary"],
        "signal_types": ["execution", "pm", "queue", "codex"],
        "decisions": [
            f"Neo opened a bounded execution packet for `{brief.get('title')}`.",
        ],
        "blockers": [],
        "project_updates": [
            f"Execution packet written to {work_order_path}",
        ],
        "learning_updates": [
            "Keep PM board truth and Codex execution artifacts tied to the same card.",
        ],
        "identity_signals": [],
        "mindset_signals": [
            "Execution should move through bounded packets instead of loose task drift.",
        ],
        "phrase_signals": [],
        "outcomes": [
            f"Queue pickup memo written to {memo_path}",
        ],
        "follow_ups": output.get("recommended_next_actions") or [],
        "memory_promotions": [],
        "pm_candidates": [],
        "artifacts": [str(memo_path), str(work_order_path)],
        "tags": ["neo", "execution", "pm-board", "codex-runner"],
    }


def _update_card_state(imports: dict[str, Any], api_url: str, selected_card: dict[str, Any], run_id: str, work_order_path: Path, *, dry_run: bool) -> dict[str, Any] | None:
    if dry_run:
        return None
    payload = dict(selected_card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    now = _now()
    history = list(execution.get("history") or [])
    history.append(
        {
            "event": "pickup",
            "state": "running",
            "requested_by": "Neo",
            "target_agent": "Neo",
            "runner_id": RUNNER_ID,
            "run_id": run_id,
            "at": now.isoformat(),
        }
    )
    execution.update(
        {
            "lane": execution.get("lane") or "codex",
            "state": "running",
            "target_agent": execution.get("target_agent") or "Neo",
            "requested_by": "Neo",
            "assigned_runner": RUNNER_ID,
            "active_run_id": run_id,
            "execution_packet_path": str(work_order_path),
            "last_transition_at": now.isoformat(),
            "history": history[-12:],
        }
    )
    payload["execution"] = execution
    payload["last_execution_packet_path"] = str(work_order_path)

    if imports.get("mode") == "service":
        updated = imports["update_card"](
            str(selected_card["id"]),
            imports["PMCardUpdate"](
                status="in_progress",
                payload=payload,
            ),
        )
        return updated.model_dump(mode="json") if updated else None

    return _fetch_json(
        f"{api_url}/api/pm/cards/{selected_card['id']}",
        method="PATCH",
        payload={"status": "in_progress", "payload": payload},
    )


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goal",
        default="Advance one queued PM card into a bounded Codex execution packet.",
        help="Goal statement for this Neo run.",
    )
    parser.add_argument("--model", default="openai/gpt-5.3-codex", help="Target Codex-family model label.")
    parser.add_argument("--time-budget-minutes", type=int, default=25)
    parser.add_argument("--output-root", default=str(MEMORY_ROOT))
    parser.add_argument("--api-url", default=os.getenv("AICLONE_API_URL", DEFAULT_API_URL))
    parser.add_argument("--limit", type=int, default=25)
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
    work_order_path = output_root / "runner-work-orders" / RUNNER_ID / f"{stamp}.json"
    memo_path = output_root / "runner-memos" / RUNNER_ID / f"{stamp}_queue_pickup.md"

    imports = _optional_backend_imports()
    try:
        queue_mode, queue_entries = _load_queue(imports, args.api_url.rstrip("/"), args.limit)
        selected_entry = _select_next_entry(queue_entries)
        if selected_entry is None:
            summary = "Neo found no queued PM cards to pick up."
            finished_at = _now()
            ledger_entry = {
                "schema_version": "runner_ledger/v1",
                "run_id": run_id,
                "runner_id": RUNNER_ID,
                "owner_agent": RUNNER_ID,
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
            print(summary)
            return 0

        cards = _load_cards(imports, args.api_url.rstrip("/"), 100)
        selected_card = next((card for card in cards if str(card.get("id")) == str(selected_entry.get("card_id"))), None)
        if selected_card is None:
            raise SystemExit(f"Queued card {selected_entry.get('card_id')} was not found in the PM card list.")

        bundle = _build_input_bundle(
            run_id=run_id,
            args=args,
            selected_entry=selected_entry,
            selected_card=selected_card,
            queue_snapshot=queue_entries,
        )
        output = _build_execution_packet(bundle)

        _write_json(input_path, bundle)
        _write_json(work_order_path, output)
        _write_markdown_memo(memo_path, bundle, output)

        chronicle_entry = _chronicle_entry(output=output, memo_path=memo_path, work_order_path=work_order_path)
        if not args.dry_run:
            _append_jsonl(CODEX_HANDOFF_PATH, chronicle_entry)

        updated_card = _update_card_state(imports, args.api_url.rstrip("/"), selected_card, run_id, work_order_path, dry_run=args.dry_run)

        finished_at = _now()
        ledger_entry = {
            "schema_version": "runner_ledger/v1",
            "run_id": run_id,
            "runner_id": RUNNER_ID,
            "owner_agent": RUNNER_ID,
            "scope": bundle["scope"],
            "primary_workspace_key": bundle["primary_workspace_key"],
            "workspace_scope": bundle["workspace_scope"],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "status": output["status"],
            "model": args.model,
            "goal": args.goal,
            "summary": output["summary"],
            "artifacts_written": [
                {"kind": "file", "path": str(input_path), "workspace_key": bundle["primary_workspace_key"], "label": "runner input"},
                {"kind": "file", "path": str(work_order_path), "workspace_key": bundle["primary_workspace_key"], "label": "execution packet"},
                {"kind": "memo", "path": str(memo_path), "workspace_key": bundle["primary_workspace_key"], "label": "queue pickup memo"},
                {
                    "kind": "file",
                    "path": str(CODEX_HANDOFF_PATH),
                    "workspace_key": bundle["primary_workspace_key"],
                    "label": "chronicle append" if not args.dry_run else "chronicle append (skipped in dry run)",
                },
            ],
            "memory_promotions": output["memory_promotions"],
            "pm_updates": output["pm_updates"],
            "blockers": output["blockers"],
            "dependencies": output["dependencies"],
            "recommended_next_actions": output["recommended_next_actions"],
            "escalations": output["escalations"],
            "error": None,
            "metadata": {
                "queue_mode": queue_mode,
                "selected_card_id": selected_entry.get("card_id"),
                "api_url": args.api_url,
                "dry_run": args.dry_run,
                "updated_card_id": updated_card.get("id") if isinstance(updated_card, dict) else None,
            },
        }
        _append_jsonl(ledger_path, ledger_entry)

        print(output["summary"])
        print(f"Runner input: {input_path}")
        print(f"Execution packet: {work_order_path}")
        print(f"Memo: {memo_path}")
        print(f"Ledger: {ledger_path}")
        return 0
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach PM API at {args.api_url}: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
