#!/usr/bin/env python3
"""Run bounded maintenance analysis through Codex using saved ChatGPT login.

Codex receives read-only access to the project. This runner validates structured
output and writes only to fixed, ignored memory targets before mirroring run
metadata to Railway.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import (
    build_run_payload,
    latest_successful_run_ms,
    mirror_runs,
)
from codex_subprocess_env import codex_worker_security_args, minimal_codex_env
from runner_lock import RunnerLock, RunnerLockUnavailable
from runtime_paths import AUTOMATION_RUNS_ROOT, PROJECT_ROOT


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")
RUN_LOG = AUTOMATION_RUNS_ROOT / "all.jsonl"


@dataclass(frozen=True)
class JobSpec:
    automation_id: str
    name: str
    title: str
    prompt: str
    target: str
    section_prefix: str


JOBS: dict[str, JobSpec] = {
    "nightly-self-improvement": JobSpec(
        automation_id="codex_nightly_self_improvement",
        name="Codex Nightly Self-Improvement",
        title="Nightly Self-Improvement",
        prompt=(
            "Review the current AI Clone operating system for evidence-backed wins, frictions, "
            "repeated failures, and one or two low-risk improvements. Focus on the local run ledger, "
            "PM state, Chronicle handoffs, current reports, and source-of-truth instructions. Do not "
            "suggest changing permissions, sending messages, deploying, or deleting data."
        ),
        target="memory/self-improvement.md",
        section_prefix="Nightly Self-Improvement",
    ),
    "daily-memory-flush": JobSpec(
        automation_id="codex_daily_memory_flush",
        name="Codex Daily Memory Flush",
        title="Daily Memory Flush",
        prompt=(
            "Synthesize the last day of material decisions, blockers, project movement, completed work, "
            "and follow-ups into durable memory. Prefer concrete evidence from Chronicle handoffs, PM "
            "artifacts, execution logs, and automation runs. Exclude acknowledgements, secrets, raw email "
            "content, and generic status boilerplate."
        ),
        target="memory/{date}.md",
        section_prefix="Daily Memory Flush",
    ),
    "rolling-docs": JobSpec(
        automation_id="codex_rolling_docs",
        name="Codex Rolling Docs",
        title="Rolling Docs Refresh",
        prompt=(
            "Review the source-of-truth documents, recent Chronicle handoffs, PM state, and recent code "
            "changes. Identify documentation that is stale or inconsistent with the Codex-native "
            "Railway-to-launchd architecture. Produce a bounded documentation refresh report; do not edit "
            "files and do not include legacy migration notes unless they still affect active behavior."
        ),
        target="memory/doc-updates.md",
        section_prefix="Rolling Docs Refresh",
    ),
}


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
        "actions": {"type": "array", "items": {"type": "string"}},
        "durable_memory": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "findings", "actions", "durable_memory", "evidence"],
    "additionalProperties": False,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_target(relative: str, now: datetime) -> Path:
    rendered = relative.format(date=now.astimezone().date().isoformat())
    target = (PROJECT_ROOT / rendered).resolve()
    target.relative_to(PROJECT_ROOT.resolve())
    return target


def _prompt(spec: JobSpec, now: datetime) -> str:
    return "\n".join(
        [
            "You are a scheduled maintenance analyst for the AI Clone project.",
            "The active architecture is Codex + authenticated Railway + local launchd. OpenClaw, QMD, and Discord are retired.",
            "Work read-only. Never expose credentials, token values, OAuth data, private email contents, or personal data.",
            "Use only evidence available in this repository. Do not browse or invoke external services.",
            f"Current UTC time: {now.isoformat().replace('+00:00', 'Z')}",
            "",
            spec.prompt,
            "",
            "Return concise JSON matching the provided schema. Evidence entries must be repository-relative paths, optionally with a short description.",
        ]
    )


def _validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Codex maintenance output must be a JSON object.")
    allowed = set(OUTPUT_SCHEMA["properties"])
    if set(payload) != allowed:
        raise ValueError("Codex maintenance output has missing or unexpected fields.")
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise ValueError("Codex maintenance output summary is empty.")
    validated: dict[str, Any] = {"summary": summary[:1200]}
    for key in ("findings", "actions", "durable_memory", "evidence"):
        value = payload.get(key)
        if not isinstance(value, list):
            raise ValueError(f"Codex maintenance output {key} must be an array.")
        validated[key] = [str(item).strip()[:800] for item in value if str(item).strip()][:12]
    return validated


def run_codex(spec: JobSpec, *, now: datetime, timeout_seconds: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ai-clone-maintenance-") as temp_dir:
        temp_root = Path(temp_dir)
        schema_path = temp_root / "schema.json"
        output_path = temp_root / "output.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA, indent=2), encoding="utf-8")
        command = [
            "codex",
            "exec",
            *codex_worker_security_args(allow_workspace_writes=False),
            "-c",
            'model_reasoning_effort="high"',
            "--cd",
            str(PROJECT_ROOT),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        completed = subprocess.run(
            command,
            input=_prompt(spec, now),
            text=True,
            capture_output=True,
            check=False,
            timeout=max(60, timeout_seconds),
            env=minimal_codex_env(),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no output").strip()[-800:]
            raise RuntimeError(f"codex exec failed with exit {completed.returncode}: {detail}")
        if not output_path.exists():
            raise RuntimeError("codex exec completed without a structured output file.")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("codex exec returned invalid JSON.") from exc
        return _validate_payload(payload)


def _markdown(spec: JobSpec, payload: dict[str, Any], now: datetime) -> str:
    lines = [
        f"## {spec.section_prefix} — {now.astimezone().date().isoformat()}",
        "",
        f"_Generated by a read-only Codex launchd runner at {now.isoformat().replace('+00:00', 'Z')}._",
        "",
        "### Summary",
        payload["summary"],
    ]
    for heading, key in (
        ("Findings", "findings"),
        ("Actions", "actions"),
        ("Durable Memory", "durable_memory"),
        ("Evidence", "evidence"),
    ):
        lines.extend(["", f"### {heading}"])
        items = payload.get(key) or []
        lines.extend(f"- {item}" for item in items) if items else lines.append("- None.")
    return "\n".join(lines).rstrip() + "\n"


def _upsert_daily_section(path: Path, heading: str, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            continue
        if start is not None and line.startswith("## "):
            end = index
            break
    block_lines = block.rstrip().splitlines()
    if start is None:
        updated = existing.rstrip()
        updated = f"{updated}\n\n{block.rstrip()}\n" if updated else block
    else:
        updated_lines = [*lines[:start], *block_lines, *lines[end:]]
        updated = "\n".join(updated_lines).rstrip() + "\n"
    path.write_text(updated, encoding="utf-8")


def write_result(spec: JobSpec, payload: dict[str, Any], *, now: datetime) -> list[str]:
    target = _safe_target(spec.target, now)
    block = _markdown(spec, payload, now)
    heading = block.splitlines()[0]
    _upsert_daily_section(target, heading, block)

    latest = _safe_target(f"memory/reports/{spec.automation_id}_latest.md", now)
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(f"# {spec.title}\n\n{block}", encoding="utf-8")
    project_root = PROJECT_ROOT.resolve()
    return [target.relative_to(project_root).as_posix(), latest.relative_to(project_root).as_posix()]


def _record(
    spec: JobSpec,
    *,
    status: str,
    started: datetime,
    finished: datetime,
    duration_ms: int,
    api_url: str,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    run = build_run_payload(
        run_id=f"{spec.automation_id}::{uuid.uuid4()}",
        automation_id=spec.automation_id,
        automation_name=spec.name,
        status=status,
        source="codex_launchd_registry",
        runtime="codex_exec",
        run_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        error=error,
        session_target="local_launchd",
        scope="shared_ops",
        action_required=status == "error",
        metadata={"local_first": True, "sandbox": "read-only", **(metadata or {})},
    )
    return mirror_runs(api_url, [run])


def execute_job(
    job_key: str,
    *,
    api_url: str = DEFAULT_API_URL,
    timeout_seconds: int = 1200,
    minimum_success_age_hours: float = 0,
) -> tuple[dict[str, Any], bool]:
    spec = JOBS[job_key]
    started = _utcnow()
    clock = time.monotonic()
    last_success_ms = latest_successful_run_ms(spec.automation_id, RUN_LOG)
    if last_success_ms is not None and minimum_success_age_hours > 0:
        age_hours = (started.timestamp() * 1000 - last_success_ms) / 3_600_000
        if age_hours < minimum_success_age_hours:
            finished = _utcnow()
            mirrored = _record(
                spec,
                status="skipped",
                started=started,
                finished=finished,
                duration_ms=round((time.monotonic() - clock) * 1000),
                api_url=api_url,
                metadata={"reason": "minimum_success_age_gate", "success_age_hours": round(age_hours, 2)},
            )
            return {"status": "skipped", "remote_mirror": "ok" if mirrored else "deferred"}, True

    try:
        with RunnerLock(spec.automation_id):
            payload = run_codex(spec, now=started, timeout_seconds=timeout_seconds)
            outputs = write_result(spec, payload, now=started)
    except RunnerLockUnavailable as exc:
        finished = _utcnow()
        mirrored = _record(
            spec,
            status="skipped",
            started=started,
            finished=finished,
            duration_ms=round((time.monotonic() - clock) * 1000),
            api_url=api_url,
            metadata={"reason": "single_flight_lock", "detail": str(exc)},
        )
        return {"status": "skipped", "remote_mirror": "ok" if mirrored else "deferred"}, True
    except Exception as exc:
        finished = _utcnow()
        error = str(exc)[:1200]
        mirrored = _record(
            spec,
            status="error",
            started=started,
            finished=finished,
            duration_ms=round((time.monotonic() - clock) * 1000),
            api_url=api_url,
            error=error,
            metadata={"error_type": type(exc).__name__},
        )
        return {"status": "error", "error": error, "remote_mirror": "ok" if mirrored else "deferred"}, False

    finished = _utcnow()
    mirrored = _record(
        spec,
        status="success",
        started=started,
        finished=finished,
        duration_ms=round((time.monotonic() - clock) * 1000),
        api_url=api_url,
        metadata={"outputs": outputs, "summary": payload["summary"][:300]},
    )
    return {
        "status": "success",
        "outputs": outputs,
        "remote_mirror": "ok" if mirrored else "deferred",
    }, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, choices=sorted(JOBS))
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--minimum-success-age-hours", type=float, default=0)
    args = parser.parse_args()
    result, ok = execute_job(
        args.job,
        api_url=args.api_url,
        timeout_seconds=args.timeout_seconds,
        minimum_success_age_hours=args.minimum_success_age_hours,
    )
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
