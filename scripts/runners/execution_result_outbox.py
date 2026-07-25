#!/usr/bin/env python3
"""Private, signed reconciliation outbox for PM execution-result commits."""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
for import_root in (SCRIPTS_ROOT, BACKEND_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.models import PMExecutionResultCommitRequest, PMExecutionResultCommitResult
from app.services.execution_artifact_reference_service import (
    contains_private_filesystem_reference,
    encode_local_execution_artifact_reference,
    validate_remote_execution_artifact_reference,
)
from runtime_http import (
    ControlPlaneURLSecurityError,
    control_plane_headers,
    open_control_plane_request,
    runtime_secret_value,
    validate_control_plane_url,
)
from runtime_paths import PROJECT_ROOT, STATE_ROOT


OUTBOX_SCHEMA = "pm_execution_result_outbox/v1"
OUTBOX_SECRET_NAME = "CONTROL_PLANE_JOB_SIGNING_SECRET"
OUTBOX_HMAC_DOMAIN = b"ai-clone/pm-execution-result-outbox/v1"
OUTBOX_AUTH_FIELD = "authorization"
OUTBOX_PENDING_EXIT = 75
MAX_OUTBOX_BYTES = 1024 * 1024
MAX_PENDING_ENTRIES = 500
_REMOTE_TEXT_FIELDS = (
    "title",
    "summary",
)
_REMOTE_TEXT_LIST_FIELDS = (
    "decisions",
    "blockers",
    "learnings",
    "outcomes",
    "follow_ups",
    "host_actions",
    "host_action_proof",
    "project_updates",
    "memory_promotions",
    "persistent_state_updates",
)
_PRIVATE_PATH_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:"
    r"~(?:[A-Za-z0-9._-]+)?[\\/][^\s`'\"<>]+"
    r"|(?:"
    r"/Users/|/home/|/private/|/tmp/|/var/|/Volumes/|/opt/|/etc/|/usr/|"
    r"/Library/|/Applications/|/workspace/|/root/|/mnt/"
    r")[^\s`'\"<>]+"
    r"|[A-Za-z]:[\\/][^\s`'\"<>]+"
    r")"
)


class ExecutionResultOutboxError(RuntimeError):
    pass


class ExecutionResultOutboxSecurityError(ExecutionResultOutboxError):
    pass


class ExecutionResultOutboxUnavailable(ExecutionResultOutboxError):
    pass


class ExecutionResultOutboxConflict(ExecutionResultOutboxError):
    pass


class ExecutionResultOutboxEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_execution_result_outbox/v1"] = OUTBOX_SCHEMA
    state: Literal["prepared", "materialized", "committed"]
    operation: PMExecutionResultCommitRequest
    prepared_at: datetime
    materialized_at: datetime | None = None
    committed_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0, le=100_000)
    last_attempt_at: datetime | None = None
    last_error: str | None = Field(default=None, max_length=500)
    disposition: Literal["committed", "already_committed"] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _outbox_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    configured = str(os.getenv("AI_CLONE_EXECUTION_RESULT_OUTBOX_ROOT") or "").strip()
    if not configured:
        return STATE_ROOT / "outbox" / "execution-results"
    configured_root = Path(configured).expanduser().resolve()
    private_state_root = STATE_ROOT.expanduser().resolve()
    if configured_root != private_state_root and private_state_root not in configured_root.parents:
        raise ExecutionResultOutboxSecurityError("Configured execution-result outbox must remain under AI_CLONE_STATE_ROOT.")
    return configured_root


def _pending_dir(root: Path) -> Path:
    return root / "pending"


def _archive_dir(root: Path) -> Path:
    return root / "archive"


def _chmod_private(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError as exc:
        raise ExecutionResultOutboxSecurityError(f"Could not secure execution-result outbox path: {path}") from exc


def _ensure_private_layout(root: Path) -> None:
    for path in (root, _pending_dir(root), _archive_dir(root)):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISDIR(path_stat.st_mode):
            raise ExecutionResultOutboxSecurityError("Execution-result outbox directories must not be symlinks.")
        _chmod_private(path, 0o700)


def _assert_private_regular_file(path: Path) -> None:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise ExecutionResultOutboxSecurityError(f"Could not inspect execution-result outbox entry: {path}") from exc
    if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry must be a regular file.")
    if stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry permissions are not private.")
    if file_stat.st_size > MAX_OUTBOX_BYTES:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry exceeds its size limit.")


def _secret() -> bytes:
    value = runtime_secret_value(OUTBOX_SECRET_NAME, filenames=("control_plane.env",))
    if not value:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox signing is not configured.")
    return hmac.new(value.encode("utf-8"), OUTBOX_HMAC_DOMAIN, hashlib.sha256).digest()


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    unsigned = dict(payload)
    unsigned.pop(OUTBOX_AUTH_FIELD, None)
    return json.dumps(unsigned, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _signed_payload(entry: ExecutionResultOutboxEntry) -> dict[str, Any]:
    payload = entry.model_dump(mode="json")
    signature = hmac.new(_secret(), _canonical_bytes(payload), hashlib.sha256).hexdigest()
    payload[OUTBOX_AUTH_FIELD] = {
        "version": 1,
        "algorithm": "hmac-sha256",
        "signature": signature,
    }
    return payload


def _validated_entry_payload(payload: Any) -> ExecutionResultOutboxEntry:
    if not isinstance(payload, dict):
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry is not an object.")
    authorization = payload.get(OUTBOX_AUTH_FIELD)
    if not isinstance(authorization, dict):
        raise ExecutionResultOutboxSecurityError("Execution-result outbox authorization is missing.")
    if authorization.get("version") != 1 or authorization.get("algorithm") != "hmac-sha256":
        raise ExecutionResultOutboxSecurityError("Execution-result outbox authorization is invalid.")
    supplied = str(authorization.get("signature") or "")
    expected = hmac.new(_secret(), _canonical_bytes(payload), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ExecutionResultOutboxSecurityError("Execution-result outbox signature is invalid.")
    unsigned = dict(payload)
    unsigned.pop(OUTBOX_AUTH_FIELD, None)
    try:
        return ExecutionResultOutboxEntry.model_validate(unsigned)
    except Exception as exc:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox schema is invalid.") from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_OUTBOX_BYTES:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry exceeds its size limit.")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _chmod_private(path.parent, 0o700)
    fd, temp_raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        _chmod_private(path, 0o600)
        _fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


@contextmanager
def _locked(root: Path):
    _ensure_private_layout(root)
    lock_path = root / ".lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox lock could not be opened safely.") from exc
    try:
        lock_stat = os.fstat(fd)
        if not stat.S_ISREG(lock_stat.st_mode):
            raise ExecutionResultOutboxSecurityError("Execution-result outbox lock must be a regular file.")
        os.fchmod(fd, 0o600)
        handle = os.fdopen(fd, "a+", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _entry_path(root: Path, result_id: str) -> Path:
    return _pending_dir(root) / f"{result_id}.json"


def _load_unlocked(path: Path) -> ExecutionResultOutboxEntry:
    _assert_private_regular_file(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry could not be read.") from exc
    return _validated_entry_payload(payload)


def prepare_outbox_entry(
    operation: PMExecutionResultCommitRequest | dict[str, Any],
    *,
    root: Path | None = None,
) -> Path:
    validated = (
        operation
        if isinstance(operation, PMExecutionResultCommitRequest)
        else PMExecutionResultCommitRequest.model_validate(operation)
    )
    active_root = _outbox_root(root)
    path = _entry_path(active_root, str(validated.result_id))
    with _locked(active_root):
        if path.exists():
            existing = _load_unlocked(path)
            if existing.operation.model_dump(mode="json") != validated.model_dump(mode="json"):
                raise ExecutionResultOutboxConflict("Result id already has a different pending operation.")
            return path
        entry = ExecutionResultOutboxEntry(
            state="prepared",
            operation=validated,
            prepared_at=_now(),
        )
        _atomic_write(path, _signed_payload(entry))
    return path


def load_outbox_entry(path: Path, *, root: Path | None = None) -> ExecutionResultOutboxEntry:
    active_root = _outbox_root(root)
    resolved = Path(path).expanduser().resolve()
    if resolved.parent != _pending_dir(active_root).resolve():
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry is outside the pending directory.")
    with _locked(active_root):
        return _load_unlocked(resolved)


def mark_outbox_materialized(path: Path, *, root: Path | None = None) -> ExecutionResultOutboxEntry:
    active_root = _outbox_root(root)
    resolved = Path(path).expanduser().resolve()
    if resolved.parent != _pending_dir(active_root).resolve():
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry is outside the pending directory.")
    with _locked(active_root):
        entry = _load_unlocked(resolved)
        if entry.state == "committed":
            raise ExecutionResultOutboxConflict("Committed execution-result outbox entry cannot be materialized again.")
        if entry.state == "materialized":
            return entry
        entry = entry.model_copy(
            update={
                "state": "materialized",
                "materialized_at": _now(),
                "last_error": None,
            }
        )
        _atomic_write(resolved, _signed_payload(entry))
        return entry


def list_pending_outbox_entries(*, root: Path | None = None) -> list[Path]:
    active_root = _outbox_root(root)
    try:
        root_stat = active_root.lstat()
    except FileNotFoundError:
        # A brand-new or genuinely idle worker has no reconciliation state.
        # Do not create private runtime directories merely to prove an empty
        # outbox on every scheduled poll.
        return []
    except OSError as exc:
        raise ExecutionResultOutboxSecurityError("Execution-result outbox root could not be inspected.") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise ExecutionResultOutboxSecurityError("Execution-result outbox root must be a private directory.")
    with _locked(active_root):
        paths = sorted(_pending_dir(active_root).glob("*.json"), key=lambda item: item.stat().st_mtime)
        if len(paths) > MAX_PENDING_ENTRIES:
            raise ExecutionResultOutboxConflict("Execution-result outbox exceeds its bounded pending-entry limit.")
        for path in paths:
            _assert_private_regular_file(path)
        return paths


def _validated_api_base(api_url: str) -> str:
    try:
        normalized = validate_control_plane_url(api_url)
    except ControlPlaneURLSecurityError as exc:
        raise ExecutionResultOutboxSecurityError(str(exc)) from exc
    parsed = urllib.parse.urlparse(normalized)
    if parsed.query or parsed.fragment:
        raise ExecutionResultOutboxSecurityError("Execution-result reconciliation API URL must not contain a query or fragment.")
    if parsed.path not in {"", "/"}:
        raise ExecutionResultOutboxSecurityError("Execution-result reconciliation API URL must not contain a path.")
    return normalized.rstrip("/")


def _scrub_remote_text(value: str, replacements: dict[str, str]) -> str:
    scrubbed = str(value)
    for local_path, logical_reference in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if local_path:
            scrubbed = scrubbed.replace(local_path, logical_reference)
    scrubbed = _PRIVATE_PATH_TOKEN_RE.sub(
        lambda match: encode_local_execution_artifact_reference(
            match.group(0),
            state_root=STATE_ROOT,
            project_root=PROJECT_ROOT,
        ),
        scrubbed,
    )
    if contains_private_filesystem_reference(scrubbed):
        raise ExecutionResultOutboxSecurityError(
            "Execution-result text contains a private filesystem path that cannot be sent to the control plane."
        )
    return scrubbed


def _remote_operation(operation: PMExecutionResultCommitRequest) -> PMExecutionResultCommitRequest:
    """Build the logical-only operation sent to the remote control plane.

    The signed local outbox intentionally retains physical paths so a crashed
    worker can replay materialization. This derived request is the only form
    allowed to cross the network boundary.
    """

    local_references = [
        *operation.artifacts,
        operation.result_path,
        operation.memo_path,
        operation.work_order_path,
        *([operation.workspace_result_path] if operation.workspace_result_path else []),
    ]
    replacements = {
        raw: encode_local_execution_artifact_reference(
            raw,
            state_root=STATE_ROOT,
            project_root=PROJECT_ROOT,
        )
        for raw in dict.fromkeys(local_references)
    }
    update: dict[str, Any] = {
        "artifacts": [replacements[item] for item in operation.artifacts],
        "result_path": replacements[operation.result_path],
        "memo_path": replacements[operation.memo_path],
        "work_order_path": replacements[operation.work_order_path],
        "workspace_result_path": (
            replacements[operation.workspace_result_path] if operation.workspace_result_path else None
        ),
    }
    for field_name in _REMOTE_TEXT_FIELDS:
        update[field_name] = _scrub_remote_text(str(getattr(operation, field_name)), replacements)
    for field_name in _REMOTE_TEXT_LIST_FIELDS:
        update[field_name] = [
            _scrub_remote_text(str(item), replacements)
            for item in getattr(operation, field_name)
        ]

    remote = PMExecutionResultCommitRequest.model_validate(
        {
            **operation.model_dump(mode="python"),
            **update,
        }
    )
    for field_name in ("result_path", "memo_path", "work_order_path"):
        validate_remote_execution_artifact_reference(str(getattr(remote, field_name)))
    if remote.workspace_result_path:
        validate_remote_execution_artifact_reference(remote.workspace_result_path)
    for artifact in remote.artifacts:
        validate_remote_execution_artifact_reference(artifact, allow_web_url=True)
    serialized = remote.model_dump_json()
    if contains_private_filesystem_reference(serialized):
        raise ExecutionResultOutboxSecurityError(
            "Execution-result request still contains a private filesystem path after logical-reference projection."
        )
    return remote


def _commit_request(operation: PMExecutionResultCommitRequest, *, api_url: str) -> PMExecutionResultCommitResult:
    api_base = _validated_api_base(api_url)
    remote_operation = _remote_operation(operation)
    url = f"{api_base}/api/pm/cards/{operation.card_id}/execution-result"
    request = urllib.request.Request(
        url,
        data=remote_operation.model_dump_json().encode("utf-8"),
        headers=control_plane_headers({"Accept": "application/json", "Content-Type": "application/json"}),
        method="POST",
    )
    try:
        with open_control_plane_request(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 409, 422}:
            raise ExecutionResultOutboxConflict(f"Execution-result commit was rejected with HTTP {exc.code}.") from exc
        raise ExecutionResultOutboxUnavailable(f"Execution-result commit failed with HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ExecutionResultOutboxUnavailable("Execution-result commit endpoint is unavailable.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutionResultOutboxUnavailable("Execution-result commit returned an invalid response.") from exc
    try:
        return PMExecutionResultCommitResult.model_validate(payload)
    except Exception as exc:
        raise ExecutionResultOutboxUnavailable("Execution-result commit response failed validation.") from exc


def _save_failure_unlocked(path: Path, entry: ExecutionResultOutboxEntry, error: Exception) -> None:
    updated = entry.model_copy(
        update={
            "attempt_count": min(entry.attempt_count + 1, 100_000),
            "last_attempt_at": _now(),
            "last_error": " ".join(str(error).split())[:500],
        }
    )
    _atomic_write(path, _signed_payload(updated))


def _archive_unlocked(
    path: Path,
    entry: ExecutionResultOutboxEntry,
    disposition: Literal["committed", "already_committed"],
    *,
    root: Path,
) -> Path:
    archive_path = _archive_dir(root) / path.name
    if archive_path.exists():
        archived = _load_unlocked(archive_path)
        if archived.operation.model_dump(mode="json") != entry.operation.model_dump(mode="json"):
            raise ExecutionResultOutboxConflict("Archived result id conflicts with the pending operation.")
        path.unlink()
        _fsync_directory(path.parent)
        return archive_path

    committed = entry.model_copy(
        update={
            "state": "committed",
            "committed_at": _now(),
            "attempt_count": min(entry.attempt_count + 1, 100_000),
            "last_attempt_at": _now(),
            "last_error": None,
            "disposition": disposition,
        }
    )
    # Write the committed archive before removing the materialized pending
    # entry. A crash between those operations leaves a replayable pending
    # request plus a valid archive, never an unreplayable "committed" pending
    # state.
    _atomic_write(archive_path, _signed_payload(committed))
    path.unlink()
    _fsync_directory(path.parent)
    return archive_path


def reconcile_outbox_entry(
    path: Path,
    *,
    api_url: str,
    root: Path | None = None,
) -> PMExecutionResultCommitResult:
    active_root = _outbox_root(root)
    resolved = Path(path).expanduser().resolve()
    if resolved.parent != _pending_dir(active_root).resolve():
        raise ExecutionResultOutboxSecurityError("Execution-result outbox entry is outside the pending directory.")
    with _locked(active_root):
        entry = _load_unlocked(resolved)
        if entry.state != "materialized":
            raise ExecutionResultOutboxConflict("Execution-result outbox entry is not locally materialized.")
        try:
            response = _commit_request(entry.operation, api_url=api_url)
        except (ExecutionResultOutboxUnavailable, ExecutionResultOutboxConflict) as exc:
            _save_failure_unlocked(resolved, entry, exc)
            raise
        _archive_unlocked(resolved, entry, response.disposition, root=active_root)
        return response


def flush_pending_outbox(
    *,
    api_url: str,
    materialize: Callable[[PMExecutionResultCommitRequest], None] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Replay prepared entries, then reconcile every materialized operation."""

    # Validate configuration before the absent-root idle fast path. Otherwise
    # a worker could claim and execute its first card, then discover that it
    # cannot sign a prepared result operation for replay.
    _secret()
    _validated_api_base(api_url)
    active_root = _outbox_root(root)
    report: dict[str, Any] = {"processed": 0, "committed": 0, "pending": 0, "conflicts": 0, "errors": []}
    for path in list_pending_outbox_entries(root=active_root):
        report["processed"] += 1
        try:
            entry = load_outbox_entry(path, root=active_root)
            if entry.state == "prepared":
                if materialize is None:
                    report["pending"] += 1
                    continue
                materialize(entry.operation)
                mark_outbox_materialized(path, root=active_root)
            reconcile_outbox_entry(path, api_url=api_url, root=active_root)
            report["committed"] += 1
        except ExecutionResultOutboxConflict as exc:
            report["conflicts"] += 1
            report["errors"].append({"result_id": path.stem, "kind": "conflict", "message": str(exc)[:300]})
        except (ExecutionResultOutboxUnavailable, ExecutionResultOutboxSecurityError) as exc:
            report["pending"] += 1
            report["errors"].append({"result_id": path.stem, "kind": "unavailable", "message": str(exc)[:300]})
        except Exception as exc:
            report["pending"] += 1
            report["errors"].append(
                {"result_id": path.stem, "kind": "materialization", "message": " ".join(str(exc).split())[:300]}
            )
    return report
