#!/usr/bin/env python3
"""Secure, bounded backups for the Codex-native AI Clone runtime."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from runtime_paths import PROJECT_ROOT, RUNTIME_ROOT, SECRETS_ROOT, ensure_runtime_dirs


BACKUP_ROOT = RUNTIME_ROOT / "backups"
PROJECT_BACKUP_ROOT = BACKUP_ROOT / "project"
CONFIG_BACKUP_ROOT = BACKUP_ROOT / "config"

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
    ensure_runtime_dirs()
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
