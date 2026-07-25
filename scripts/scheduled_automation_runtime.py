#!/usr/bin/env python3
"""Local-first runtime helpers for deterministic scheduled automations.

The task result is appended to the private local run ledger before any network
request is attempted.  Railway mirroring is backed by a persistent retry queue
so a transient outage cannot erase run truth or turn a healthy local task into
a failed task.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from automation_run_mirror import append_local_runs, build_run_payload
from codex_subprocess_env import minimal_codex_env
from runtime_http import control_plane_headers, control_plane_token
from runtime_paths import (
    AUTOMATION_RUNS_ROOT,
    LOG_ROOT,
    PROJECT_ROOT,
    RUNTIME_ROOT,
    STATE_ROOT,
    ensure_runtime_dirs,
)


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")
DEFAULT_PENDING_PATH = AUTOMATION_RUNS_ROOT / "pending_railway_mirror.jsonl"
DEFAULT_LEDGER_PATH = AUTOMATION_RUNS_ROOT / "all.jsonl"
DEFAULT_MIRROR_TIMEOUT_SECONDS = 15
DEFAULT_MIRROR_ATTEMPTS = 3
MAX_PENDING_BATCH = 100


class ScheduledTaskError(RuntimeError):
    """Raised when a deterministic scheduled task cannot finish safely."""


@dataclass(frozen=True)
class TaskOutcome:
    ok: bool
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
    action_required: bool = False
    error: str | None = None


@dataclass(frozen=True)
class CommandOutput:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class MirrorOutcome:
    status: str
    attempted: int
    mirrored: int
    pending: int
    error: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _bounded_text(value: Any, *, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _safe_subprocess_error(stderr: str) -> str:
    """Return one bounded, credential-redacted diagnostic line for operators."""

    lines = [line.strip() for line in str(stderr or "").splitlines() if line.strip()]
    if not lines:
        return ""
    detail = lines[-1]
    detail = re.sub(
        r"(?i)\\b(authorization|bearer|token|secret|password|api[_-]?key)\\b\\s*[:=]\\s*\\S+",
        r"\1=<redacted>",
        detail,
    )
    return _bounded_text(detail, limit=220)


def _safe_project_script(relative_name: str) -> Path:
    scripts_root = (PROJECT_ROOT / "scripts").resolve()
    candidate = (scripts_root / relative_name).resolve()
    try:
        candidate.relative_to(scripts_root)
    except ValueError as exc:
        raise ScheduledTaskError("Scheduled script escaped the project scripts directory.") from exc
    if candidate.suffix != ".py" or not candidate.is_file():
        raise ScheduledTaskError(f"Scheduled script is unavailable: {relative_name}")
    return candidate


def scheduled_subprocess_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return a narrow environment without model-provider credentials."""

    values = source or dict(os.environ)
    env = minimal_codex_env(values)
    service_token = control_plane_token()
    explicit = {
        "AI_CLONE_ROOT": str(PROJECT_ROOT),
        "AI_CLONE_RUNTIME_ROOT": str(RUNTIME_ROOT),
        "AI_CLONE_STATE_ROOT": str(STATE_ROOT),
        # Backend imports must not bulk-load the full integration environment.
        # Remote builders receive only the bearer credential they require.
        "AI_CLONE_SECRETS_ROOT": str(RUNTIME_ROOT / "scheduled-no-secret-files"),
        "AI_CLONE_LOG_ROOT": str(LOG_ROOT),
        "AICLONE_API_URL": str(values.get("AICLONE_API_URL") or DEFAULT_API_URL),
    }
    if service_token:
        explicit["CONTROL_PLANE_SERVICE_TOKEN"] = service_token
    env.update(explicit)
    return env


def run_project_python(
    script_name: str,
    arguments: Iterable[str] = (),
    *,
    timeout_seconds: int,
    allowed_exit_codes: set[int] | None = None,
) -> CommandOutput:
    """Run one allowlisted project Python script with a hard timeout."""

    if timeout_seconds < 1 or timeout_seconds > 900:
        raise ScheduledTaskError("Scheduled task timeout must be between 1 and 900 seconds.")
    script_path = _safe_project_script(script_name)
    accepted = allowed_exit_codes or {0}
    try:
        completed = subprocess.run(
            [sys.executable, str(script_path), *[str(item) for item in arguments]],
            cwd=str(PROJECT_ROOT),
            env=scheduled_subprocess_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScheduledTaskError(f"{script_name} exceeded its {timeout_seconds}-second timeout.") from exc
    if completed.returncode not in accepted:
        detail = _safe_subprocess_error(completed.stderr)
        suffix = f" {detail}" if detail else ""
        raise ScheduledTaskError(
            f"{script_name} exited with status {completed.returncode}.{suffix}"
        )
    return CommandOutput(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_json_output(output: str) -> dict[str, Any]:
    """Parse one JSON object, tolerating harmless leading diagnostic lines."""

    stripped = output.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ScheduledTaskError("Scheduled builder did not emit a JSON object.")
        try:
            payload = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ScheduledTaskError("Scheduled builder emitted invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise ScheduledTaskError("Scheduled builder JSON must be an object.")
    return payload


def atomic_write_text(path: Path, content: str, *, mode: int = 0o600) -> None:
    """Atomically write a bounded runtime or project artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(mode)
        os.replace(temp_path, path)
        path.chmod(mode)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and str(payload.get("id") or "").strip():
            rows.append(payload)
    return rows


@contextmanager
def _pending_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+", encoding="utf-8") as handle:
        lock_path.chmod(0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    atomic_write_text(path, content, mode=0o600)


def enqueue_pending_run(payload: dict[str, Any], *, pending_path: Path = DEFAULT_PENDING_PATH) -> int:
    """Durably queue a run for an authenticated Railway retry."""

    run_id = str(payload.get("id") or "").strip()
    if not run_id:
        raise ScheduledTaskError("Cannot queue a run without an id.")
    with _pending_lock(pending_path):
        rows = _read_jsonl(pending_path)
        by_id = {str(row["id"]): row for row in rows}
        by_id[run_id] = payload
        ordered = [by_id[key] for key in sorted(by_id)]
        _write_jsonl(pending_path, ordered)
        return len(ordered)


def _validated_api_url(api_url: str) -> str:
    parsed = urllib.parse.urlparse(api_url.strip())
    local_host = parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.scheme not in ({"http", "https"} if local_host else {"https"}):
        raise ScheduledTaskError("Railway mirror URL must use HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ScheduledTaskError("Railway mirror URL is invalid.")
    return api_url.rstrip("/")


def _post_runs(api_url: str, runs: list[dict[str, Any]], *, timeout_seconds: int) -> None:
    endpoint = f"{_validated_api_url(api_url)}/api/automations/runs/mirror"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"runs": runs}).encode("utf-8"),
        method="POST",
        headers=control_plane_headers({"Accept": "application/json", "Content-Type": "application/json"}),
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response.read(4096)


def flush_pending_runs(
    api_url: str,
    *,
    pending_path: Path = DEFAULT_PENDING_PATH,
    attempts: int = DEFAULT_MIRROR_ATTEMPTS,
    timeout_seconds: int = DEFAULT_MIRROR_TIMEOUT_SECONDS,
) -> MirrorOutcome:
    """Retry the oldest pending run batch and remove only confirmed rows."""

    with _pending_lock(pending_path):
        queued = _read_jsonl(pending_path)
    batch = queued[:MAX_PENDING_BATCH]
    if not batch:
        return MirrorOutcome(status="ok", attempted=0, mirrored=0, pending=0)
    if attempts < 1:
        return MirrorOutcome(status="deferred", attempted=0, mirrored=0, pending=len(queued))
    if timeout_seconds < 1 or timeout_seconds > 60:
        raise ScheduledTaskError("Railway mirror timeout must be between 1 and 60 seconds.")
    if not control_plane_token():
        return MirrorOutcome(
            status="deferred",
            attempted=0,
            mirrored=0,
            pending=len(queued),
            error="Control-plane service token is unavailable.",
        )

    last_error: str | None = None
    made_attempts = 0
    for attempt in range(attempts):
        made_attempts += 1
        try:
            _post_runs(api_url, batch, timeout_seconds=timeout_seconds)
            mirrored_ids = {str(row["id"]) for row in batch}
            with _pending_lock(pending_path):
                latest = _read_jsonl(pending_path)
                remaining = [row for row in latest if str(row.get("id")) not in mirrored_ids]
                _write_jsonl(pending_path, remaining)
            return MirrorOutcome(
                status="ok",
                attempted=made_attempts,
                mirrored=len(batch),
                pending=len(remaining),
            )
        except (ScheduledTaskError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = _bounded_text(exc, limit=240)
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 2))

    with _pending_lock(pending_path):
        pending_count = len(_read_jsonl(pending_path))
    return MirrorOutcome(
        status="deferred",
        attempted=made_attempts,
        mirrored=0,
        pending=pending_count,
        error=last_error or "Railway mirror failed.",
    )


def run_scheduled_task(
    *,
    automation_id: str,
    automation_name: str,
    task: Callable[[], TaskOutcome],
    api_url: str = DEFAULT_API_URL,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    pending_path: Path = DEFAULT_PENDING_PATH,
    mirror_attempts: int = DEFAULT_MIRROR_ATTEMPTS,
) -> tuple[dict[str, Any], bool]:
    """Execute a deterministic task, persist locally, then mirror retryably."""

    if ledger_path == DEFAULT_LEDGER_PATH and pending_path == DEFAULT_PENDING_PATH:
        ensure_runtime_dirs()
    started = utc_now()
    started_clock = time.monotonic()
    try:
        outcome = task()
    except Exception as exc:
        outcome = TaskOutcome(
            ok=False,
            summary=f"{automation_name} failed.",
            error=_bounded_text(exc, limit=300),
            action_required=True,
        )
    finished = utc_now()
    status = "success" if outcome.ok else "failed"
    run_id = f"{automation_id}-{started.strftime('%Y%m%dT%H%M%S%fZ')}"
    metadata = {
        **dict(outcome.metadata),
        "summary": _bounded_text(outcome.summary, limit=400),
        "local_first": True,
        "railway_mirror_retryable": True,
    }
    payload = build_run_payload(
        run_id=run_id,
        automation_id=automation_id,
        automation_name=automation_name,
        status=status,
        source="codex_launchd_registry",
        runtime="launchd",
        run_at=started,
        finished_at=finished,
        duration_ms=round((time.monotonic() - started_clock) * 1000),
        error=outcome.error,
        owner_agent="Neo",
        scope="shared_ops",
        action_required=outcome.action_required or not outcome.ok,
        metadata=metadata,
    )

    # This ordering is the contract: local truth exists before queue/network.
    append_local_runs([payload], ledger_path)
    try:
        ledger_path.chmod(0o600)
    except OSError:
        pass
    queued_count = enqueue_pending_run(payload, pending_path=pending_path)
    mirror = flush_pending_runs(
        api_url,
        pending_path=pending_path,
        attempts=mirror_attempts,
    )
    result = {
        "schema_version": "codex_scheduled_task_run/v1",
        "automation_id": automation_id,
        "run_id": run_id,
        "status": status,
        "summary": outcome.summary,
        "local_ledger": str(ledger_path),
        "railway_mirror": {
            "status": mirror.status,
            "attempted": mirror.attempted,
            "mirrored": mirror.mirrored,
            "pending_before_attempt": queued_count,
            "pending": mirror.pending,
            "error": mirror.error,
        },
        "metadata": dict(outcome.metadata),
    }
    return result, outcome.ok
