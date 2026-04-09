#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from thin_trigger_client import DEFAULT_API_URL, ThinTriggerError, request_json


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from enqueue_pm_execution_card import build_card_request  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the PM -> Jean-Claude -> Codex -> PM write-back path.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--title", default="Smoke: verify PM execution loop")
    parser.add_argument("--reason", default="Smoke test the direct Jean-Claude -> Codex execution path.")
    parser.add_argument("--instruction", action="append", default=["Keep the change bounded and traceable."])
    parser.add_argument("--acceptance-criterion", action="append", default=["The PM card returns a result payload."])
    parser.add_argument("--artifact", action="append", default=["smoke result"])
    parser.add_argument("--card-id", default="")
    parser.add_argument("--worker-id", default="smoke-codex")
    parser.add_argument("--live", action="store_true", help="Actually create a PM card and run the local runners.")
    return parser.parse_args()


def build_smoke_card_payload(args: argparse.Namespace) -> dict[str, Any]:
    return build_card_request(
        SimpleNamespace(
            title=args.title,
            workspace_key=args.workspace_key,
            owner="Neo",
            status="todo",
            source="openclaw:smoke-test",
            source_agent="Neo",
            requested_by="Neo",
            manager_agent="Jean-Claude",
            target_agent="Jean-Claude",
            workspace_agent=None,
            execution_mode="direct",
            execution_state="queued",
            lane="codex",
            assigned_runner="codex",
            reason=args.reason,
            instruction=args.instruction,
            acceptance_criterion=args.acceptance_criterion,
            artifact=args.artifact,
            repo_path=str(ROOT),
            branch="",
            sop_path="",
            briefing_path="",
        )
    )


def _runner_command(script_name: str, *, workspace_key: str, card_id: str, api_url: str, worker_id: str | None = None) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "runners" / script_name),
        "--workspace-key",
        workspace_key,
        "--card-id",
        card_id,
        "--api-url",
        api_url,
    ]
    if worker_id:
        command.extend(["--worker-id", worker_id])
    return command


def _load_card_snapshot(api_url: str, card_id: str) -> dict[str, Any]:
    cards = request_json(api_url, "/api/pm/cards?limit=400")
    if not isinstance(cards, list):
        raise ThinTriggerError("PM card list response was not a list.", detail=cards)
    for card in cards:
        if isinstance(card, dict) and str(card.get("id") or "") == card_id:
            return card
    raise ThinTriggerError(f"PM card {card_id} was not found after smoke execution.")


def run_live_smoke(args: argparse.Namespace) -> dict[str, Any]:
    created_card_id = str(args.card_id or "").strip()
    created_payload: dict[str, Any] | None = None
    if not created_card_id:
        created_payload = request_json(args.api_url, "/api/pm/cards", method="POST", payload=build_smoke_card_payload(args))
        if not isinstance(created_payload, dict):
            raise ThinTriggerError("Smoke PM create did not return an object.", detail=created_payload)
        created_card_id = str(created_payload.get("id") or "")
        if not created_card_id:
            raise ThinTriggerError("Smoke PM create did not return a card id.", detail=created_payload)

    jean_command = _runner_command(
        "run_jean_claude_execution.py",
        workspace_key=args.workspace_key,
        card_id=created_card_id,
        api_url=args.api_url,
    )
    codex_command = _runner_command(
        "run_codex_workspace_execution.py",
        workspace_key=args.workspace_key,
        card_id=created_card_id,
        api_url=args.api_url,
        worker_id=args.worker_id,
    )

    jean_result = subprocess.run(jean_command, text=True, capture_output=True, check=False)
    if jean_result.returncode != 0:
        raise RuntimeError((jean_result.stderr or jean_result.stdout or "Jean-Claude dispatch failed").strip())

    codex_result = subprocess.run(codex_command, text=True, capture_output=True, check=False)
    if codex_result.returncode != 0:
        raise RuntimeError((codex_result.stderr or codex_result.stdout or "Codex execution failed").strip())

    card_snapshot = _load_card_snapshot(args.api_url, created_card_id)
    payload = dict(card_snapshot.get("payload") or {})
    latest_result = dict(payload.get("latest_execution_result") or {})
    execution = dict(payload.get("execution") or {})

    return {
        "success": True,
        "mode": "live",
        "card_id": created_card_id,
        "created_card": created_payload,
        "card_status": card_snapshot.get("status"),
        "execution_state": execution.get("state"),
        "executor_status": execution.get("executor_status"),
        "latest_result_status": latest_result.get("status"),
        "latest_result_summary": latest_result.get("summary"),
        "jean_claude_stdout": jean_result.stdout.strip(),
        "codex_stdout": codex_result.stdout.strip(),
    }


def main() -> int:
    args = parse_args()
    if not args.live:
        payload = build_smoke_card_payload(args)
        card_id = str(args.card_id or "<existing-card-id>")
        result = {
            "success": True,
            "mode": "plan",
            "payload": payload,
            "commands": [
                _runner_command("run_jean_claude_execution.py", workspace_key=args.workspace_key, card_id=card_id, api_url=args.api_url),
                _runner_command(
                    "run_codex_workspace_execution.py",
                    workspace_key=args.workspace_key,
                    card_id=card_id,
                    api_url=args.api_url,
                    worker_id=args.worker_id,
                ),
            ],
        }
        print(json.dumps(result, indent=2))
        return 0

    try:
        print(json.dumps(run_live_smoke(args), indent=2))
        return 0
    except (RuntimeError, ThinTriggerError) as exc:
        print(json.dumps({"success": False, "mode": "live", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
