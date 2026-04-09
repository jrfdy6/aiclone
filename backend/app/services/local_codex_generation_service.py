from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


_LOCK = Lock()
_NONTERMINAL_STATUSES = {"pending", "claimed", "running"}
_TERMINAL_STATUSES = {"completed", "failed", "canceled"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_dir() -> Path:
    explicit = (os.getenv("LOCAL_CODEX_JOB_STORE_DIR") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path(tempfile.gettempdir()) / "aiclone-local-codex-jobs"


def _store_path() -> Path:
    return _store_dir() / "jobs.json"


def _artifact_root() -> Path:
    return _store_dir() / "artifacts"


def _artifact_dir(job_id: str) -> Path:
    return _artifact_root() / job_id


def _ensure_store_dir() -> None:
    _store_dir().mkdir(parents=True, exist_ok=True)


def _ensure_artifact_dir(job_id: str) -> None:
    _artifact_dir(job_id).mkdir(parents=True, exist_ok=True)


def _load_jobs() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _write_jobs(jobs: list[dict[str, Any]]) -> None:
    _ensure_store_dir()
    path = _store_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp_path.replace(path)


def _normalize_workspace_slug(value: str | None) -> str:
    slug = " ".join((value or "").split()).strip().lower()
    return slug or "linkedin-content-os"


def _normalize_status(value: str | None) -> str:
    status = " ".join((value or "").split()).strip().lower()
    if status in _NONTERMINAL_STATUSES or status in _TERMINAL_STATUSES:
        return status
    return "pending"


def _job_matches_workspace(job: dict[str, Any], workspace_slug: str | None) -> bool:
    if not workspace_slug:
        return True
    return _normalize_workspace_slug(job.get("workspace_slug")) == _normalize_workspace_slug(workspace_slug)


def _find_job(jobs: list[dict[str, Any]], job_id: str) -> dict[str, Any] | None:
    for job in jobs:
        if str(job.get("id") or "") == job_id:
            return job
    return None


def _touch(job: dict[str, Any], *, status: str | None = None) -> None:
    if status:
        job["status"] = _normalize_status(status)
    job["updated_at"] = _utcnow_iso()


def _normalize_artifact_name(value: str, *, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in (value or "").strip())
    cleaned = cleaned.strip("-._")
    return cleaned or fallback


def create_codex_job(
    *,
    workspace_slug: str,
    requested_by: str,
    request_payload: dict[str, Any],
    context_packet: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    normalized_workspace = _normalize_workspace_slug(workspace_slug)
    now = _utcnow_iso()
    with _LOCK:
        jobs = _load_jobs()
        for job in jobs:
            if (
                str(job.get("idempotency_key") or "") == idempotency_key
                and _normalize_status(job.get("status")) in _NONTERMINAL_STATUSES
            ):
                return dict(job)
        for job in jobs:
            if (
                _normalize_workspace_slug(job.get("workspace_slug")) == normalized_workspace
                and _normalize_status(job.get("status")) in _NONTERMINAL_STATUSES
            ):
                raise ValueError(f"A local Codex job is already active for {normalized_workspace}.")

        job = {
            "id": str(uuid4()),
            "workspace_slug": normalized_workspace,
            "requested_by": requested_by,
            "job_kind": "content_generation",
            "status": "pending",
            "request_payload": request_payload,
            "context_packet": context_packet,
            "claimed_by": None,
            "claimed_at": None,
            "started_at": None,
            "completed_at": None,
            "failed_at": None,
            "canceled_at": None,
            "error_message": None,
            "result_payload": None,
            "artifacts": [],
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
        }
        jobs.append(job)
        _write_jobs(jobs)
        return dict(job)


def get_codex_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        jobs = _load_jobs()
        job = _find_job(jobs, job_id)
        return dict(job) if job else None


def claim_next_codex_job(*, worker_id: str, workspace_slug: str | None = None) -> dict[str, Any] | None:
    with _LOCK:
        jobs = _load_jobs()
        pending_jobs = [
            job
            for job in jobs
            if _normalize_status(job.get("status")) == "pending" and _job_matches_workspace(job, workspace_slug)
        ]
        if not pending_jobs:
            return None
        pending_jobs.sort(key=lambda item: str(item.get("created_at") or ""))
        selected = pending_jobs[0]
        selected["claimed_by"] = worker_id
        selected["claimed_at"] = _utcnow_iso()
        selected["started_at"] = selected.get("started_at") or selected["claimed_at"]
        selected["error_message"] = None
        _touch(selected, status="running")
        _write_jobs(jobs)
        return dict(selected)


def complete_codex_job(
    *,
    job_id: str,
    worker_id: str,
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    with _LOCK:
        jobs = _load_jobs()
        job = _find_job(jobs, job_id)
        if not job:
            raise ValueError("Codex job not found.")
        status = _normalize_status(job.get("status"))
        if status in _TERMINAL_STATUSES:
            return dict(job)
        job["claimed_by"] = worker_id
        job["completed_at"] = _utcnow_iso()
        job["error_message"] = None
        job["result_payload"] = result_payload
        _touch(job, status="completed")
        _write_jobs(jobs)
        return dict(job)


def fail_codex_job(
    *,
    job_id: str,
    worker_id: str,
    error_message: str,
) -> dict[str, Any]:
    with _LOCK:
        jobs = _load_jobs()
        job = _find_job(jobs, job_id)
        if not job:
            raise ValueError("Codex job not found.")
        status = _normalize_status(job.get("status"))
        if status in _TERMINAL_STATUSES:
            return dict(job)
        job["claimed_by"] = worker_id
        job["failed_at"] = _utcnow_iso()
        job["error_message"] = error_message
        _touch(job, status="failed")
        _write_jobs(jobs)
        return dict(job)


def cancel_codex_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        jobs = _load_jobs()
        job = _find_job(jobs, job_id)
        if not job:
            raise ValueError("Codex job not found.")
        status = _normalize_status(job.get("status"))
        if status in _TERMINAL_STATUSES:
            return dict(job)
        job["canceled_at"] = _utcnow_iso()
        job["error_message"] = "Canceled by user."
        _touch(job, status="canceled")
        _write_jobs(jobs)
        return dict(job)


def write_job_artifact(
    *,
    job_id: str,
    kind: str,
    label: str,
    content: str,
    filename: str,
    mime_type: str = "text/plain",
) -> dict[str, Any]:
    _ensure_store_dir()
    _ensure_artifact_dir(job_id)
    artifact_id = str(uuid4())
    normalized_filename = _normalize_artifact_name(filename, fallback=f"{artifact_id}.txt")
    path = _artifact_dir(job_id) / normalized_filename
    encoded = content.encode("utf-8")
    path.write_bytes(encoded)
    return {
        "artifact_id": artifact_id,
        "job_id": job_id,
        "kind": " ".join((kind or "").split()).strip() or "artifact",
        "label": " ".join((label or "").split()).strip() or normalized_filename,
        "filename": normalized_filename,
        "mime_type": " ".join((mime_type or "").split()).strip() or "text/plain",
        "relative_path": str(path.relative_to(_store_dir())),
        "size_bytes": len(encoded),
        "created_at": _utcnow_iso(),
    }


def append_job_artifacts(*, job_id: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    with _LOCK:
        jobs = _load_jobs()
        job = _find_job(jobs, job_id)
        if not job:
            raise ValueError("Codex job not found.")
        stored = job.get("artifacts")
        job["artifacts"] = [item for item in stored if isinstance(item, dict)] if isinstance(stored, list) else []
        for artifact in artifacts:
            if isinstance(artifact, dict):
                job["artifacts"].append(dict(artifact))
        _touch(job)
        _write_jobs(jobs)
        return dict(job)


def list_job_artifacts(job_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        jobs = _load_jobs()
        job = _find_job(jobs, job_id)
        if not job:
            raise ValueError("Codex job not found.")
        stored = job.get("artifacts")
        return [dict(item) for item in stored if isinstance(item, dict)] if isinstance(stored, list) else []


def read_job_artifact_content(*, job_id: str, artifact_id: str) -> str | None:
    artifacts = list_job_artifacts(job_id)
    match = next((item for item in artifacts if str(item.get("artifact_id") or "") == artifact_id), None)
    if not match:
        raise ValueError("Codex job artifact not found.")
    relative_path = str(match.get("relative_path") or "").strip()
    if not relative_path:
        return None
    path = _store_dir() / relative_path
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None
