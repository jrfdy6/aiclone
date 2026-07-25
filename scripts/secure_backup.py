#!/usr/bin/env python3
"""Secure, bounded backups for the Codex-native AI Clone runtime."""

from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from runtime_paths import PROJECT_ROOT, RUNTIME_ROOT, SECRETS_ROOT, STATE_ROOT


BACKUP_ROOT = RUNTIME_ROOT / "backups"
PROJECT_BACKUP_ROOT = BACKUP_ROOT / "project"
CONFIG_BACKUP_ROOT = BACKUP_ROOT / "config"
STATE_BACKUP_ROOT = BACKUP_ROOT / "state"
STATE_ARCHIVE_PREFIX = "AI-Clone-State"
STATE_MANIFEST_NAME = ".ai-clone-state-backup-manifest.json"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".railway-stage",
    "__pycache__",
    "node_modules",
    "backups",
    "logs",
    "media",
    "tmp",
    "venv",
    ".venv",
    ".venv-main-safe",
    "myenv312",
    "secrets",
    "keys",
}
SECRET_NAME_MARKERS = (
    ".env",
    "credential",
    "oauth_token",
    "service-account",
    "service_account",
    "private-key",
    "private_key",
)
SECRET_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}
SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_secret_name(path: Path) -> bool:
    lowered = path.name.lower()
    return (
        lowered.startswith(".env")
        or any(marker in lowered for marker in SECRET_NAME_MARKERS)
        or path.suffix.lower() in SECRET_SUFFIXES
    )


def _excluded(relative: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES or part.startswith(".venv") for part in relative.parts) or _is_secret_name(relative)


def _project_files(project_root: Path) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(project_root, followlinks=False):
        current = Path(directory)
        try:
            current_rel = current.relative_to(project_root)
        except ValueError:
            continue
        dirnames[:] = [
            name
            for name in dirnames
            if not _excluded(current_rel / name) and not (current / name).is_symlink()
        ]
        for filename in filenames:
            path = current / filename
            relative = current_rel / filename
            if _excluded(relative) or path.is_symlink() or not path.is_file():
                continue
            yield path


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _retain(directory: Path, pattern: str, keep: int) -> list[str]:
    directory_resolved = directory.resolve()
    candidates = sorted(
        (path for path in directory.glob(pattern) if path.is_file() and path.parent.resolve() == directory_resolved),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    removed: list[str] = []
    for path in candidates[max(1, keep) :]:
        path.unlink()
        removed.append(path.name)
    return removed


def create_project_snapshot(
    *,
    project_root: Path = PROJECT_ROOT,
    output_root: Path = PROJECT_BACKUP_ROOT,
    keep: int = 7,
    now: datetime | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {project_root}")
    current = now or _utcnow()
    _private_directory(output_root)
    final_path = output_root / f"ai-clone-project-{_stamp(current)}.tar.gz"
    partial_path = output_root / f".{final_path.name}.partial"
    file_count = 0
    source_bytes = 0
    try:
        with tarfile.open(partial_path, "w:gz", dereference=False) as archive:
            for path in _project_files(project_root):
                relative = path.relative_to(project_root)
                archive.add(path, arcname=(Path("AI-Clone") / relative).as_posix(), recursive=False)
                file_count += 1
                source_bytes += path.stat().st_size
        partial_path.chmod(0o600)
        partial_path.replace(final_path)
    finally:
        if partial_path.exists():
            partial_path.unlink()
    final_path.chmod(0o600)
    removed = _retain(output_root, "ai-clone-project-*.tar.gz", keep)
    return {
        "path": str(final_path),
        "name": final_path.name,
        "file_count": file_count,
        "source_bytes": source_bytes,
        "archive_bytes": final_path.stat().st_size,
        "sha256": _sha256(final_path),
        "retention_removed": removed,
    }


def _state_files(state_root: Path) -> tuple[list[Path], dict[str, int]]:
    files: list[Path] = []
    skipped = {
        "symlinks": 0,
        "secret_names": 0,
        "lock_files": 0,
        "sqlite_sidecars": 0,
        "non_files": 0,
    }
    if not state_root.exists():
        return files, skipped
    for path in sorted(state_root.rglob("*")):
        if path.is_symlink():
            skipped["symlinks"] += 1
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            skipped["non_files"] += 1
            continue
        relative = path.relative_to(state_root)
        if any(part.lower() in {"secrets", "keys", "credentials"} for part in relative.parts[:-1]):
            skipped["secret_names"] += 1
            continue
        if path.name.endswith(".lock"):
            skipped["lock_files"] += 1
            continue
        if path.name.endswith(("-wal", "-shm", "-journal")):
            skipped["sqlite_sidecars"] += 1
            continue
        if _is_secret_name(relative):
            skipped["secret_names"] += 1
            continue
        files.append(path)
    return files, skipped


def _is_sqlite_database(path: Path) -> bool:
    return path.suffix.lower() in SQLITE_SUFFIXES


def _sqlite_integrity_check(path: Path) -> None:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if not row or str(row[0]).lower() != "ok":
        raise ValueError(f"SQLite integrity check failed for snapshot member: {path.name}")


def _sqlite_online_backup(source: Path, destination: Path) -> None:
    """Create one transactionally consistent SQLite copy without source WAL files."""

    source_connection = sqlite3.connect(
        f"{source.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=10,
    )
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()
    destination.chmod(0o600)
    _sqlite_integrity_check(destination)


def create_state_snapshot(
    *,
    state_root: Path = STATE_ROOT,
    output_root: Path = STATE_BACKUP_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a local, owner-only, self-verifying snapshot of private state.

    State snapshots are intentionally separate from the project archive and do
    not include the secrets root. No retention deletion is automatic.
    """

    state_root = state_root.expanduser().resolve()
    if not state_root.is_dir():
        raise FileNotFoundError(f"State root does not exist: {state_root}")
    current = now or _utcnow()
    _private_directory(output_root)
    final_path = output_root / f"ai-clone-state-{_stamp(current)}.tar.gz"
    partial_path = output_root / f".{final_path.name}.partial"
    source_files, skipped = _state_files(state_root)
    manifest_files: list[dict[str, Any]] = []
    source_bytes = 0
    try:
        with tempfile.TemporaryDirectory(prefix="ai-clone-state-sqlite-") as sqlite_temp_dir:
            sqlite_snapshots: dict[Path, Path] = {}
            for index, path in enumerate(source_files):
                if not _is_sqlite_database(path):
                    continue
                snapshot_path = Path(sqlite_temp_dir) / f"database-{index}.sqlite3"
                _sqlite_online_backup(path, snapshot_path)
                sqlite_snapshots[path] = snapshot_path

            with tarfile.open(partial_path, "w:gz", dereference=False) as archive:
                for path in source_files:
                    if path.is_symlink() or not path.is_file():
                        raise RuntimeError(f"State file changed during snapshot: {path}")
                    relative = path.relative_to(state_root).as_posix()
                    captured_path = sqlite_snapshots.get(path, path)
                    metadata = captured_path.stat()
                    digest = hashlib.sha256()
                    size = 0
                    with captured_path.open("rb") as source, tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as captured:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                            captured.write(chunk)
                            size += len(chunk)
                        captured.seek(0)
                        member = tarfile.TarInfo((Path(STATE_ARCHIVE_PREFIX) / relative).as_posix())
                        member.size = size
                        member.mode = 0o600
                        member.mtime = int(metadata.st_mtime)
                        archive.addfile(member, captured)
                    source_bytes += size
                    manifest_record = {
                        "path": relative,
                        "size_bytes": size,
                        "sha256": digest.hexdigest(),
                    }
                    if path in sqlite_snapshots:
                        manifest_record["kind"] = "sqlite_online_backup"
                    manifest_files.append(manifest_record)
                manifest = {
                    "schema_version": "ai_clone_state_backup/v1",
                    "created_at": current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "file_count": len(manifest_files),
                    "source_bytes": source_bytes,
                    "files": manifest_files,
                    "skipped": skipped,
                }
                manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
                manifest_info = tarfile.TarInfo(STATE_MANIFEST_NAME)
                manifest_info.size = len(manifest_bytes)
                manifest_info.mode = 0o600
                manifest_info.mtime = int(current.timestamp())
                archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
        partial_path.chmod(0o600)
        partial_path.replace(final_path)
    finally:
        if partial_path.exists():
            partial_path.unlink()
    final_path.chmod(0o600)
    try:
        verification = verify_state_snapshot(final_path)
    except Exception:
        final_path.unlink(missing_ok=True)
        raise
    return {
        "path": str(final_path),
        "name": final_path.name,
        "file_count": len(manifest_files),
        "source_bytes": source_bytes,
        "archive_bytes": final_path.stat().st_size,
        "sha256": _sha256(final_path),
        "skipped": skipped,
        "verified": verification["verified"],
    }


def verify_state_snapshot(archive_path: Path) -> dict[str, Any]:
    """Verify archive containment plus every manifest size and SHA-256."""

    archive_path = archive_path.expanduser().resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        manifest_member = next((member for member in members if member.name == STATE_MANIFEST_NAME), None)
        if manifest_member is None or not manifest_member.isfile():
            raise ValueError("State snapshot manifest is missing.")
        manifest_handle = archive.extractfile(manifest_member)
        if manifest_handle is None:
            raise ValueError("State snapshot manifest cannot be read.")
        manifest = json.loads(manifest_handle.read().decode("utf-8"))
        if manifest.get("schema_version") != "ai_clone_state_backup/v1":
            raise ValueError("State snapshot manifest version is unsupported.")
        expected = {
            str(item.get("path") or ""): item
            for item in (manifest.get("files") or [])
            if isinstance(item, dict) and str(item.get("path") or "")
        }
        actual_members: dict[str, tarfile.TarInfo] = {}
        prefix = f"{STATE_ARCHIVE_PREFIX}/"
        for member in members:
            if member.name == STATE_MANIFEST_NAME:
                continue
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError(f"Unsafe or unexpected state snapshot member: {member.name}")
            relative = member.name[len(prefix) :]
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not relative:
                raise ValueError(f"Unsafe state snapshot path: {member.name}")
            actual_members[relative] = member
        if set(actual_members) != set(expected):
            raise ValueError("State snapshot file list does not match its manifest.")
        verified_bytes = 0
        for relative, member in actual_members.items():
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"State snapshot member cannot be read: {relative}")
            digest = hashlib.sha256()
            size = 0
            record = expected[relative]
            sqlite_temp_path: Path | None = None
            sqlite_temp_handle = None
            if record.get("kind") == "sqlite_online_backup":
                sqlite_temp_handle = tempfile.NamedTemporaryFile(
                    prefix="ai-clone-state-verify-",
                    suffix=".sqlite3",
                    delete=False,
                )
                sqlite_temp_path = Path(sqlite_temp_handle.name)
            try:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
                    if sqlite_temp_handle is not None:
                        sqlite_temp_handle.write(chunk)
                if sqlite_temp_handle is not None:
                    sqlite_temp_handle.flush()
                    os.fsync(sqlite_temp_handle.fileno())
                    sqlite_temp_handle.close()
                    sqlite_temp_handle = None
                    _sqlite_integrity_check(sqlite_temp_path)
            finally:
                if sqlite_temp_handle is not None:
                    sqlite_temp_handle.close()
                if sqlite_temp_path is not None:
                    sqlite_temp_path.unlink(missing_ok=True)
            expected_size = record.get("size_bytes")
            if (
                not isinstance(expected_size, int)
                or size != expected_size
                or digest.hexdigest() != record.get("sha256")
            ):
                raise ValueError(f"State snapshot verification failed: {relative}")
            verified_bytes += size
    return {
        "verified": True,
        "path": str(archive_path),
        "file_count": len(actual_members),
        "source_bytes": verified_bytes,
    }


def _secret_manifest(secrets_root: Path, now: datetime) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if secrets_root.exists():
        for path in sorted(secrets_root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            metadata = path.stat()
            files.append(
                {
                    "path": path.relative_to(secrets_root).as_posix(),
                    "size_bytes": metadata.st_size,
                    "mode": stat.filemode(metadata.st_mode),
                    "modified_at": datetime.fromtimestamp(metadata.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                    "sha256": _sha256(path),
                }
            )
    return {
        "schema_version": "ai_clone_config_manifest/v1",
        "created_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "secrets_root": str(secrets_root),
        "file_count": len(files),
        "files": files,
    }


def _encrypted_secret_archive(secrets_root: Path, output_path: Path, passphrase: str) -> None:
    if not passphrase:
        raise ValueError("A non-empty passphrase is required for secret-content backup.")
    if not secrets_root.is_dir():
        raise FileNotFoundError(f"Secrets root does not exist: {secrets_root}")
    with tempfile.TemporaryDirectory(prefix="ai-clone-config-backup-") as temp_dir:
        plain_archive = Path(temp_dir) / "config.tar.gz"
        with tarfile.open(plain_archive, "w:gz", dereference=False) as archive:
            for path in sorted(secrets_root.rglob("*")):
                if path.is_symlink() or not path.is_file():
                    continue
                archive.add(path, arcname=(Path("secrets") / path.relative_to(secrets_root)).as_posix(), recursive=False)
        completed = subprocess.run(
            [
                "openssl",
                "enc",
                "-aes-256-cbc",
                "-pbkdf2",
                "-salt",
                "-in",
                str(plain_archive),
                "-out",
                str(output_path),
                "-pass",
                "stdin",
            ],
            input=passphrase + "\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"openssl encryption failed: {(completed.stderr or 'unknown error').strip()[-400:]}")


def create_config_backup(
    *,
    secrets_root: Path = SECRETS_ROOT,
    output_root: Path = CONFIG_BACKUP_ROOT,
    passphrase: str | None = None,
    keep: int = 8,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _utcnow()
    _private_directory(output_root)
    stamp = _stamp(current)
    manifest = _secret_manifest(secrets_root, current)
    manifest_path = output_root / f"ai-clone-config-manifest-{stamp}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)

    encrypted_path: Path | None = None
    if passphrase:
        encrypted_path = output_root / f"ai-clone-config-{stamp}.tar.gz.enc"
        _encrypted_secret_archive(secrets_root, encrypted_path, passphrase)
        encrypted_path.chmod(0o600)

    removed = [
        *_retain(output_root, "ai-clone-config-manifest-*.json", keep),
        *_retain(output_root, "ai-clone-config-*.tar.gz.enc", keep),
    ]
    return {
        "manifest_path": str(manifest_path),
        "manifest_name": manifest_path.name,
        "file_count": manifest["file_count"],
        "encrypted_archive_path": str(encrypted_path) if encrypted_path else None,
        "encrypted": encrypted_path is not None,
        "retention_removed": removed,
    }
