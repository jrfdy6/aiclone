#!/usr/bin/env python3
"""Refresh Fusion public feedback, build standup prep, and record local-first run truth."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from automation_run_mirror import append_local_runs, build_run_payload, mirror_runs
from runtime_paths import PROJECT_ROOT


AUTOMATION_ID = "fusion_feedback_refresh"
AUTOMATION_NAME = "Fusion Feedback Refresh"
DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")
FUSION_WORKSPACE_KEY = "fusion-os"
FUSION_OWNER_AGENT = "jean-claude"
FUSION_WORKSPACE_ROOT = PROJECT_ROOT / "workspaces" / FUSION_WORKSPACE_KEY
MODEL_TOKEN_ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "COHERE_API_KEY",
    "DEEPSEEK_API_KEY",
    "FIREWORKS_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "PERPLEXITY_API_KEY",
    "TOGETHER_API_KEY",
    "XAI_API_KEY",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Keep control-plane auth while excluding model-provider credentials."""

    env = dict(source if source is not None else os.environ)
    for key in MODEL_TOKEN_ENV_KEYS:
        env.pop(key, None)
    return env


def _run_stage(command: list[str], *, timeout: int, env: dict[str, str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "error": "stage timed out"}
    except OSError as exc:
        return {"ok": False, "returncode": None, "error": f"stage could not start ({type(exc).__name__})"}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "error": None if completed.returncode == 0 else f"stage exited with code {completed.returncode}",
    }


def _refresh_summary(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    allowed = {
        "workspace_key",
        "username",
        "followers",
        "average_visible_engagement",
        "sample_size",
        "json_path",
        "markdown_path",
    }
    return {key: payload[key] for key in allowed if key in payload}


def _standup_paths(stdout: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    for line in stdout.splitlines():
        label, separator, value = line.partition(":")
        if not separator or not value.strip():
            continue
        normalized = label.strip().lower()
        if normalized == "json":
            paths["json_path"] = value.strip()
        elif normalized == "markdown":
            paths["markdown_path"] = value.strip()
    return paths


def run(
    *,
    api_url: str = DEFAULT_API_URL,
    workspace_key: str = FUSION_WORKSPACE_KEY,
    owner_agent: str = FUSION_OWNER_AGENT,
    username: str = "fusionacademydc",
    sample_size: int = 12,
    remote_mirror: bool = True,
) -> tuple[dict[str, Any], bool]:
    if workspace_key != FUSION_WORKSPACE_KEY:
        raise ValueError(f"workspace_key must be {FUSION_WORKSPACE_KEY}")
    if owner_agent != FUSION_OWNER_AGENT:
        raise ValueError(f"owner_agent must be {FUSION_OWNER_AGENT}")

    started = _utcnow()
    started_clock = time.monotonic()
    child_env = _child_environment()
    refresh = _run_stage(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "refresh_fusion_instagram_feedback.py"),
            "--workspace-key",
            workspace_key,
            "--workspace-root",
            str(FUSION_WORKSPACE_ROOT),
            "--username",
            username,
            "--sample-size",
            str(max(sample_size, 1)),
        ],
        timeout=180,
        env=child_env,
    )
    standup = _run_stage(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "build_standup_prep.py"),
            "--workspace-key",
            workspace_key,
            "--owner-agent",
            owner_agent,
        ],
        timeout=300,
        env=child_env,
    )

    finished = _utcnow()
    ok = bool(refresh.get("ok") and standup.get("ok"))
    stage_errors = [
        f"{name}: {result['error']}"
        for name, result in (("feedback_refresh", refresh), ("standup_prep", standup))
        if result.get("error")
    ]
    run_payload = build_run_payload(
        run_id=f"fusion-feedback-refresh::{uuid.uuid4()}",
        automation_id=AUTOMATION_ID,
        automation_name=AUTOMATION_NAME,
        status="success" if ok else "error",
        source="codex_launchd_registry",
        runtime="launchd",
        run_at=started,
        finished_at=finished,
        duration_ms=round((time.monotonic() - started_clock) * 1000),
        error="; ".join(stage_errors)[:1200] or None,
        owner_agent=owner_agent,
        scope="workspace",
        workspace_key=workspace_key,
        action_required=not ok,
        metadata={
            "local_first": True,
            "model_api_tokens_used": False,
            "feedback_refresh": {
                "ok": bool(refresh.get("ok")),
                "returncode": refresh.get("returncode"),
                **_refresh_summary(str(refresh.get("stdout") or "")),
            },
            "standup_prep": {
                "ok": bool(standup.get("ok")),
                "returncode": standup.get("returncode"),
                **_standup_paths(str(standup.get("stdout") or "")),
            },
        },
    )

    try:
        if remote_mirror:
            mirrored = mirror_runs(api_url, [run_payload])
            remote_status = "ok" if mirrored else "deferred"
        else:
            append_local_runs([run_payload])
            remote_status = "disabled"
    except OSError as exc:
        return (
            {
                "schema_version": "fusion_feedback_refresh_run/v1",
                "status": "error",
                "remote_mirror": "not_attempted",
                "ledger_error": f"local run ledger write failed ({type(exc).__name__})",
            },
            False,
        )

    report: dict[str, Any] = {
        "schema_version": "fusion_feedback_refresh_run/v1",
        "status": "success" if ok else "error",
        "remote_mirror": remote_status,
        "workspace_key": workspace_key,
        "owner_agent": owner_agent,
        "feedback_refresh": run_payload["metadata"]["feedback_refresh"],
        "standup_prep": run_payload["metadata"]["standup_prep"],
    }
    if stage_errors:
        report["error"] = "; ".join(stage_errors)
    return report, ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--workspace-key", choices=[FUSION_WORKSPACE_KEY], default=FUSION_WORKSPACE_KEY)
    parser.add_argument("--owner-agent", choices=[FUSION_OWNER_AGENT], default=FUSION_OWNER_AGENT)
    parser.add_argument("--username", default="fusionacademydc")
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--no-remote-mirror", action="store_true")
    args = parser.parse_args()
    report, ok = run(
        api_url=args.api_url,
        workspace_key=args.workspace_key,
        owner_agent=args.owner_agent,
        username=args.username,
        sample_size=args.sample_size,
        remote_mirror=not args.no_remote_mirror,
    )
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
