#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = os.getenv("AI_CLONE_API_BASE_URL", "http://127.0.0.1:8000/api/content-generation")
DEFAULT_WORKSPACE_ROOT = os.getenv("LOCAL_CODEX_BRIDGE_WORKSPACE_ROOT", "/Users/neo/.openclaw/workspace")
DEFAULT_MODEL = os.getenv("LOCAL_CODEX_BRIDGE_MODEL", "gpt-5.1-codex")
DEFAULT_REASONING_EFFORT = os.getenv("LOCAL_CODEX_BRIDGE_REASONING_EFFORT", "high")
DEFAULT_POLL_SECONDS = float(os.getenv("LOCAL_CODEX_BRIDGE_POLL_SECONDS", "4"))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("LOCAL_CODEX_BRIDGE_TIMEOUT_SECONDS", "420"))


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Local-Codex-Token"] = token
    return headers


def _request_json(method: str, url: str, *, token: str | None = None, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=_headers(token), method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    if not raw.strip():
        return None
    return json.loads(raw)


def _claim_next_job(*, api_base: str, token: str | None, worker_id: str, workspace_slug: str) -> dict[str, Any] | None:
    payload = _request_json(
        "POST",
        f"{api_base.rstrip('/')}/codex-jobs/claim-next",
        token=token,
        payload={"worker_id": worker_id, "workspace_slug": workspace_slug},
    )
    if not isinstance(payload, dict) or not payload.get("job_available"):
        return None
    return payload


def _complete_job(
    *,
    api_base: str,
    token: str | None,
    job_id: str,
    worker_id: str,
    options: list[str],
    model: str,
    raw_output: str,
    command_stdout: str,
    command_stderr: str,
) -> None:
    _request_json(
        "POST",
        f"{api_base.rstrip('/')}/codex-jobs/{job_id}/complete",
        token=token,
        payload={
            "worker_id": worker_id,
            "options": options,
            "model": model,
            "raw_output": raw_output,
            "command_stdout": command_stdout,
            "command_stderr": command_stderr,
        },
    )


def _fail_job(*, api_base: str, token: str | None, job_id: str, worker_id: str, error_message: str) -> None:
    _request_json(
        "POST",
        f"{api_base.rstrip('/')}/codex-jobs/{job_id}/fail",
        token=token,
        payload={"worker_id": worker_id, "error_message": error_message[:2000]},
    )


def _build_schema(expected_option_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "options": {
                "type": "array",
                "minItems": expected_option_count,
                "maxItems": expected_option_count,
                "items": {"type": "string", "minLength": 20},
            }
        },
        "required": ["options"],
        "additionalProperties": False,
    }


def _run_codex_job(
    *,
    workspace_root: Path,
    model: str,
    reasoning_effort: str,
    prompt: str,
    expected_option_count: int,
    timeout_seconds: int,
) -> tuple[list[str], str, str, str]:
    with tempfile.TemporaryDirectory(prefix="local-codex-job-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        schema_path = temp_dir / "schema.json"
        output_path = temp_dir / "output.json"
        schema_path.write_text(json.dumps(_build_schema(expected_option_count), indent=2), encoding="utf-8")

        command = [
            "codex",
            "exec",
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--cd",
            str(workspace_root),
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--model",
            model,
            "-",
        ]
        if not (workspace_root / ".git").exists():
            command.insert(-1, "--skip-git-repo-check")

        completed = subprocess.run(
            command,
            input=prompt,
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
                f"{(stderr or stdout or 'no output').strip()[:800]}"
            )
        if not output_path.exists():
            raise RuntimeError("codex exec completed without writing an output message file")
        raw_output = output_path.read_text(encoding="utf-8").strip()
        parsed = json.loads(raw_output)
        if not isinstance(parsed, dict):
            raise RuntimeError("codex exec did not return a JSON object")
        raw_options = parsed.get("options")
        if not isinstance(raw_options, list):
            raise RuntimeError("codex exec response did not include an options array")
        options = [str(item).strip() for item in raw_options if str(item).strip()]
        if len(options) != expected_option_count:
            raise RuntimeError(f"codex exec returned {len(options)} options; expected {expected_option_count}")
        return options, raw_output, stdout[-4000:], stderr[-4000:]


def run_once(
    *,
    api_base: str,
    token: str | None,
    worker_id: str,
    workspace_slug: str,
    workspace_root: Path,
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
) -> bool:
    job = _claim_next_job(api_base=api_base, token=token, worker_id=worker_id, workspace_slug=workspace_slug)
    if not job:
        return False

    job_id = str(job.get("job_id") or "")
    context_packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    prompt = str(context_packet.get("prompt") or "").strip()
    expected_option_count = int(context_packet.get("expected_option_count") or 3)
    requested_model = str(context_packet.get("requested_model") or model or DEFAULT_MODEL).strip() or DEFAULT_MODEL

    if not prompt:
        _fail_job(
            api_base=api_base,
            token=token,
            job_id=job_id,
            worker_id=worker_id,
            error_message="Claimed Codex job did not include a prompt packet.",
        )
        return True

    try:
        options, raw_output, stdout, stderr = _run_codex_job(
            workspace_root=workspace_root,
            model=requested_model,
            reasoning_effort=reasoning_effort,
            prompt=prompt,
            expected_option_count=expected_option_count,
            timeout_seconds=timeout_seconds,
        )
        _complete_job(
            api_base=api_base,
            token=token,
            job_id=job_id,
            worker_id=worker_id,
            options=options,
            model=requested_model,
            raw_output=raw_output,
            command_stdout=stdout,
            command_stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        _fail_job(
            api_base=api_base,
            token=token,
            job_id=job_id,
            worker_id=worker_id,
            error_message=f"codex exec timed out after {timeout_seconds} seconds.",
        )
    except Exception as exc:
        _fail_job(
            api_base=api_base,
            token=token,
            job_id=job_id,
            worker_id=worker_id,
            error_message=str(exc),
        )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claim local Codex content-generation jobs and execute them with codex exec.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--workspace-slug", default="linkedin-content-os")
    parser.add_argument("--workspace-root", default=DEFAULT_WORKSPACE_ROOT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-codex-bridge")
    parser.add_argument("--token", default=os.getenv("LOCAL_CODEX_BRIDGE_TOKEN") or os.getenv("CRON_ACCESS_TOKEN"))
    parser.add_argument("--once", action="store_true", help="Claim at most one job, then exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).expanduser()
    if not workspace_root.exists():
        print(f"Workspace root does not exist: {workspace_root}", file=sys.stderr)
        return 1

    while True:
        try:
            claimed = run_once(
                api_base=args.api_base,
                token=args.token,
                worker_id=args.worker_id,
                workspace_slug=args.workspace_slug,
                workspace_root=workspace_root,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
            )
        except urllib.error.HTTPError as exc:
            print(f"Bridge HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
            if args.once:
                return 1
            time.sleep(args.poll_seconds)
            continue
        except urllib.error.URLError as exc:
            print(f"Bridge URL error: {exc}", file=sys.stderr)
            if args.once:
                return 1
            time.sleep(args.poll_seconds)
            continue

        if args.once:
            return 0
        if not claimed:
            time.sleep(args.poll_seconds)
            continue


if __name__ == "__main__":
    raise SystemExit(main())
