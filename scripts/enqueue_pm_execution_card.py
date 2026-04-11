#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from thin_trigger_client import DEFAULT_API_URL, ThinTriggerError, request_json


ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workspace_runtime_contract_service import execution_defaults_for_workspace  # noqa: E402
from app.services.pm_execution_contract_service import build_execution_contract  # noqa: E402
from app.services.trigger_identity_service import build_pm_trigger_key  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enqueue a PM execution card through the backend contract.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--title", required=True)
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--owner", default=None)
    parser.add_argument("--status", default="todo")
    parser.add_argument("--source", default="openclaw:thin-trigger")
    parser.add_argument("--source-agent", default="Neo")
    parser.add_argument("--requested-by", default="Neo")
    parser.add_argument("--manager-agent", default=None)
    parser.add_argument("--target-agent", default=None)
    parser.add_argument("--workspace-agent", default=None)
    parser.add_argument("--execution-mode", default=None)
    parser.add_argument("--execution-state", default="queued")
    parser.add_argument("--lane", default="codex")
    parser.add_argument("--assigned-runner", default="codex")
    parser.add_argument("--reason", default="")
    parser.add_argument("--instruction", action="append", default=[])
    parser.add_argument("--acceptance-criterion", action="append", default=[])
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--repo-path", default=str(ROOT))
    parser.add_argument("--branch", default="")
    parser.add_argument("--sop-path", default="")
    parser.add_argument("--briefing-path", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_card_request(args: argparse.Namespace | SimpleNamespace, *, now_iso: str | None = None) -> dict[str, Any]:
    defaults = execution_defaults_for_workspace(str(args.workspace_key))
    timestamp = now_iso or _now_iso()
    workspace_key = str(args.workspace_key or "shared_ops")
    explicit_manager_agent = str(args.manager_agent or "").strip()
    explicit_target_agent = str(args.target_agent or "").strip()
    use_neo_front_door = str(args.source_agent or "").strip() == "Neo" and not explicit_manager_agent and not explicit_target_agent
    downstream_manager_agent = str(defaults["manager_agent"] or "Jean-Claude")
    downstream_target_agent = str(defaults["target_agent"] or downstream_manager_agent)
    manager_agent = explicit_manager_agent or downstream_manager_agent
    target_agent = explicit_target_agent or downstream_target_agent
    workspace_agent = args.workspace_agent
    if workspace_agent is None:
        workspace_agent = defaults.get("workspace_agent")
    execution_mode = str(args.execution_mode or defaults["execution_mode"] or "direct")
    normalized_reason = str(args.reason or "").strip() or f"OpenClaw queued `{args.title}` through the thin backend contract."
    execution_payload: dict[str, Any] = {
        "lane": str(args.lane),
        "state": str(args.execution_state),
        "manager_agent": manager_agent,
        "target_agent": target_agent,
        "execution_mode": execution_mode,
        "requested_by": str(args.requested_by),
        "assigned_runner": str(args.assigned_runner),
        "reason": normalized_reason,
        "last_transition_at": timestamp,
        "source": str(args.source),
    }
    if str(args.execution_state).lower() == "queued":
        execution_payload["queued_at"] = timestamp
    if workspace_agent:
        execution_payload["workspace_agent"] = str(workspace_agent)
    if str(args.sop_path or "").strip():
        execution_payload["sop_path"] = str(args.sop_path).strip()
    if str(args.briefing_path or "").strip():
        execution_payload["briefing_path"] = str(args.briefing_path).strip()

    contract = build_execution_contract(
        title=str(args.title),
        workspace_key=workspace_key,
        source="openclaw_thin_trigger",
        reason=normalized_reason,
        instructions=[str(item).strip() for item in args.instruction if str(item).strip()],
        acceptance_criteria=[str(item).strip() for item in args.acceptance_criterion if str(item).strip()],
        artifacts_expected=[str(item).strip() for item in args.artifact if str(item).strip()],
    )

    payload: dict[str, Any] = {
        "workspace_key": workspace_key,
        "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
        "source_agent": str(args.source_agent),
        "requested_by": str(args.requested_by),
        "reason": normalized_reason,
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "repo_path": str(args.repo_path),
        "branch": str(args.branch or "").strip() or None,
        "execution": execution_payload,
        "trigger_origin": "openclaw_thin_trigger",
        "triggered_at": timestamp,
    }
    if use_neo_front_door:
        payload["front_door_agent"] = "Neo"
        payload["downstream_route"] = {
            "manager_agent": downstream_manager_agent,
            "target_agent": downstream_target_agent,
            "workspace_agent": str(workspace_agent) if workspace_agent else None,
            "execution_mode": execution_mode,
        }
    payload["trigger_key"] = build_pm_trigger_key(
        title=str(args.title),
        workspace_key=workspace_key,
        source=str(args.source),
        payload=payload,
    )

    return {
        "title": str(args.title),
        "owner": str(args.owner or ("Neo" if use_neo_front_door else manager_agent)),
        "status": str(args.status),
        "source": str(args.source),
        "payload": payload,
    }


def main() -> int:
    args = parse_args()
    card_request = build_card_request(args)
    if args.dry_run:
        print(json.dumps({"success": True, "dry_run": True, "api_url": args.api_url, "payload": card_request}, indent=2))
        return 0
    try:
        created = request_json(args.api_url, "/api/pm/cards", method="POST", payload=card_request)
        if not isinstance(created, dict):
            raise ThinTriggerError("PM trigger returned a non-object response.")
        print(json.dumps({"success": True, "card": created}, indent=2))
        return 0
    except ThinTriggerError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
