"""Workspace backup automation script.

Creates an include-only archive of the OpenClaw workspace, optionally encrypts it,
copies it into a Git repo, and logs the run back to the FastAPI backend so Ops/Brain
can surface the telemetry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Iterable, List, Optional

import requests

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "deliverables" / "backups"
DEFAULT_INCLUDE = [
    "downloads/aiclone",
    "knowledge",
    "notes",
    "memory",
    "collectors",
    "deliverables",
]
DEFAULT_EXCLUDE = [
    "downloads/aiclone/.git",
    "downloads/aiclone/frontend/.next",
    "downloads/aiclone/node_modules",
    "downloads/aiclone/.venv",
    "downloads/aiclone/__pycache__",
    "downloads/aiclone/backend/.pytest_cache",
    "downloads/aiclone/backend/.mypy_cache",
    "downloads/aiclone/frontend/node_modules",
    "secrets",
    "tmp",
]


def _normalize_paths(paths: Iterable[str]) -> List[Path]:
    return [Path(p.strip("/")) for p in paths if p]


def should_exclude(rel_path: Path, excludes: List[Path]) -> bool:
    rel_posix = rel_path.as_posix()
    for pattern in excludes:
        pat = pattern.as_posix()
        if rel_posix == pat or rel_posix.startswith(pat + "/"):
            return True
    return False


def create_archive(include_paths: List[Path], exclude_paths: List[Path], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    archive_path = output_dir / f"workspace-backup-{timestamp}.tar.gz"

    def tar_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        rel = Path(tarinfo.name)
        return None if should_exclude(rel, exclude_paths) else tarinfo

    with tarfile.open(archive_path, "w:gz") as tar:
        for rel_path in include_paths:
            abs_path = WORKSPACE_ROOT / rel_path
            if not abs_path.exists():
                continue
            tar.add(abs_path, arcname=rel_path.as_posix(), filter=tar_filter)
    return archive_path


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def encrypt_archive(archive_path: Path, passphrase: Optional[str]) -> Path:
    if not passphrase:
        return archive_path
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl is required for encryption but was not found on PATH")
    encrypted_path = archive_path.with_suffix(archive_path.suffix + ".enc")
    cmd = [
        openssl,
        "enc",
        "-aes-256-cbc",
        "-salt",
        "-in",
        str(archive_path),
        "-out",
        str(encrypted_path),
        "-pass",
        f"pass:{passphrase}",
    ]
    subprocess.run(cmd, check=True)
    return encrypted_path


def copy_to_repo(archive_path: Path, repo_path: Path) -> Path:
    repo_path.mkdir(parents=True, exist_ok=True)
    destination = repo_path / archive_path.name
    shutil.copy2(archive_path, destination)
    return destination


def git_commit_and_push(repo_path: Path, file_path: Path, message: str, branch: str = "main") -> None:
    subprocess.run(["git", "-C", str(repo_path), "add", file_path.name], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", message], check=True)
    subprocess.run(["git", "-C", str(repo_path), "push", "origin", branch], check=True)


def post_log(api_url: str, token: Optional[str], payload: dict) -> None:
    if not api_url:
        return
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        requests.post(api_url.rstrip("/") + "/api/system/logs", headers=headers, json=payload, timeout=10)
    except Exception as exc:
        print(f"Failed to post log: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup the OpenClaw workspace.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Directory to store archives")
    parser.add_argument("--include", nargs="*", default=DEFAULT_INCLUDE, help="Relative paths to include")
    parser.add_argument("--exclude", nargs="*", default=DEFAULT_EXCLUDE, help="Relative paths to exclude")
    parser.add_argument("--encrypt", action="store_true", help="Encrypt archive with openssl")
    parser.add_argument("--passphrase", default=os.getenv("BACKUP_PASSPHRASE"), help="Encryption passphrase")
    parser.add_argument("--repo", default=os.getenv("BACKUP_REPO"), help="Path to Git repo for backups")
    parser.add_argument("--branch", default=os.getenv("BACKUP_REPO_BRANCH", "main"))
    parser.add_argument("--api-url", default=os.getenv("BACKUP_API_URL"), help="Backend base URL for logging")
    parser.add_argument("--api-token", default=os.getenv("BACKUP_API_TOKEN"), help="Bearer token for logging")
    args = parser.parse_args()

    include_paths = _normalize_paths(args.include)
    exclude_paths = _normalize_paths(args.exclude)
    output_dir = Path(args.output)

    archive = create_archive(include_paths, exclude_paths, output_dir)
    checksum = sha256sum(archive)

    if args.encrypt:
        archive = encrypt_archive(archive, args.passphrase)

    repo_file = None
    if args.repo:
        repo_file = copy_to_repo(archive, Path(args.repo))
        message = f"Backup: {archive.name}"
        try:
            git_commit_and_push(Path(args.repo), repo_file, message, branch=args.branch)
        except subprocess.CalledProcessError as exc:
            print(f"Git push failed: {exc}")

    log_payload = {
        "id": str(uuid.uuid4()),
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "level": "INFO",
        "component": "automation.backup",
        "message": "Workspace backup completed",
        "context": {
            "archive": archive.name,
            "size_bytes": archive.stat().st_size,
            "sha256": checksum,
            "repo_file": repo_file.name if repo_file else None,
        },
    }
    post_log(args.api_url, args.api_token, log_payload)
    print(json.dumps(log_payload, indent=2))


if __name__ == "__main__":
    main()
