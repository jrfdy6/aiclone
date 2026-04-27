from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

try:
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    dict_row = None  # type: ignore
    Jsonb = None  # type: ignore

try:
    from app.services.open_brain_db import get_pool
except Exception:  # pragma: no cover
    get_pool = None  # type: ignore

_LOCK = Lock()
_NONTERMINAL_STATUSES = {"pending", "claimed", "running"}
_TERMINAL_STATUSES = {"completed", "failed", "canceled"}
_JOB_SELECT_COLUMNS = (
    "id, workspace_slug, requested_by, job_kind, status, request_payload, context_packet, "
    "claimed_by, claimed_at, started_at, completed_at, failed_at, canceled_at, error_message, "
    "result_payload, artifacts, idempotency_key, created_at, updated_at"
)


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


def _maybe_pool():
    if get_pool is None or dict_row is None or Jsonb is None:
        return None
    try:
        return get_pool()
    except Exception:
        return None


def _ensure_store_dir() -> None:
    _store_dir().mkdir(parents=True, exist_ok=True)


def _ensure_artifact_dir(job_id: str) -> None:
    _artifact_dir(job_id).mkdir(parents=True, exist_ok=True)


def _load_jobs() -> list[dict[str, Any]]:
    pool = _maybe_pool()
    if pool is not None:
        return _load_jobs_from_db(pool)
    path = _store_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _write_jobs(jobs: list[dict[str, Any]]) -> None:
    pool = _maybe_pool()
    if pool is not None:
        _upsert_jobs_to_db(pool, jobs)
        return
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


def _coerce_db_timestamp(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _serialize_job_row(row: dict[str, Any]) -> dict[str, Any]:
    serialized = {key: _coerce_db_timestamp(value) for key, value in row.items()}
    request_payload = serialized.get("request_payload")
    serialized["request_payload"] = request_payload if isinstance(request_payload, dict) else {}
    context_packet = serialized.get("context_packet")
    serialized["context_packet"] = context_packet if isinstance(context_packet, dict) else {}
    result_payload = serialized.get("result_payload")
    serialized["result_payload"] = result_payload if isinstance(result_payload, dict) else None
    artifacts = serialized.get("artifacts")
    serialized["artifacts"] = [dict(item) for item in artifacts if isinstance(item, dict)] if isinstance(artifacts, list) else []
    serialized["status"] = _normalize_status(serialized.get("status"))
    return serialized


def _job_db_params(job: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(job.get("id") or ""),
        _normalize_workspace_slug(job.get("workspace_slug")),
        str(job.get("requested_by") or ""),
        str(job.get("job_kind") or "content_generation"),
        _normalize_status(job.get("status")),
        Jsonb(job.get("request_payload") if isinstance(job.get("request_payload"), dict) else {}),
        Jsonb(job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}),
        str(job.get("claimed_by") or "") or None,
        _optional_datetime(job.get("claimed_at")),
        _optional_datetime(job.get("started_at")),
        _optional_datetime(job.get("completed_at")),
        _optional_datetime(job.get("failed_at")),
        _optional_datetime(job.get("canceled_at")),
        str(job.get("error_message") or "") or None,
        Jsonb(job.get("result_payload")) if isinstance(job.get("result_payload"), dict) else None,
        Jsonb([dict(item) for item in job.get("artifacts") if isinstance(item, dict)] if isinstance(job.get("artifacts"), list) else []),
        str(job.get("idempotency_key") or ""),
        _optional_datetime(job.get("created_at")),
        _optional_datetime(job.get("updated_at")),
    )


def _load_jobs_from_db(pool) -> list[dict[str, Any]]:
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_JOB_SELECT_COLUMNS}
                FROM local_codex_jobs
                ORDER BY created_at ASC
                """
            )
            rows = cur.fetchall() or []
    return [_serialize_job_row(row) for row in rows]


def _upsert_jobs_to_db(pool, jobs: list[dict[str, Any]]) -> None:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for job in jobs:
                cur.execute(
                    """
                    INSERT INTO local_codex_jobs (
                        id, workspace_slug, requested_by, job_kind, status, request_payload, context_packet,
                        claimed_by, claimed_at, started_at, completed_at, failed_at, canceled_at, error_message,
                        result_payload, artifacts, idempotency_key, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET workspace_slug = EXCLUDED.workspace_slug,
                        requested_by = EXCLUDED.requested_by,
                        job_kind = EXCLUDED.job_kind,
                        status = EXCLUDED.status,
                        request_payload = EXCLUDED.request_payload,
                        context_packet = EXCLUDED.context_packet,
                        claimed_by = EXCLUDED.claimed_by,
                        claimed_at = EXCLUDED.claimed_at,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        failed_at = EXCLUDED.failed_at,
                        canceled_at = EXCLUDED.canceled_at,
                        error_message = EXCLUDED.error_message,
                        result_payload = EXCLUDED.result_payload,
                        artifacts = EXCLUDED.artifacts,
                        idempotency_key = EXCLUDED.idempotency_key,
                        created_at = COALESCE(local_codex_jobs.created_at, EXCLUDED.created_at, NOW()),
                        updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                    """,
                    _job_db_params(job),
                )
        conn.commit()


def _write_artifact_content_to_db(pool, *, artifact: dict[str, Any], content: str) -> None:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO local_codex_job_artifacts (
                    artifact_id, job_id, kind, label, filename, mime_type, size_bytes, relative_path, content, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (artifact_id) DO UPDATE
                SET job_id = EXCLUDED.job_id,
                    kind = EXCLUDED.kind,
                    label = EXCLUDED.label,
                    filename = EXCLUDED.filename,
                    mime_type = EXCLUDED.mime_type,
                    size_bytes = EXCLUDED.size_bytes,
                    relative_path = EXCLUDED.relative_path,
                    content = EXCLUDED.content,
                    updated_at = NOW()
                """,
                (
                    str(artifact.get("artifact_id") or ""),
                    str(artifact.get("job_id") or ""),
                    str(artifact.get("kind") or "artifact"),
                    str(artifact.get("label") or ""),
                    str(artifact.get("filename") or ""),
                    str(artifact.get("mime_type") or "text/plain"),
                    int(artifact.get("size_bytes") or 0),
                    str(artifact.get("relative_path") or "") or None,
                    content,
                    _optional_datetime(artifact.get("created_at")),
                ),
            )
        conn.commit()


def _read_artifact_content_from_db(pool, *, job_id: str, artifact_id: str) -> str | None:
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT content
                FROM local_codex_job_artifacts
                WHERE artifact_id = %s AND job_id = %s
                """,
                (artifact_id, job_id),
            )
            row = cur.fetchone() or {}
    content = row.get("content")
    return str(content) if content is not None else None


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


def list_codex_jobs(*, workspace_slug: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        jobs = [
            dict(job)
            for job in _load_jobs()
            if _job_matches_workspace(job, workspace_slug)
        ]
    jobs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    if isinstance(limit, int) and limit > 0:
        return jobs[:limit]
    return jobs


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
    artifact = {
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
    pool = _maybe_pool()
    if pool is not None:
        _write_artifact_content_to_db(pool, artifact=artifact, content=content)
    return artifact


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
    pool = _maybe_pool()
    if pool is not None:
        content = _read_artifact_content_from_db(pool, job_id=job_id, artifact_id=artifact_id)
        if content is not None:
            return content
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
