from __future__ import annotations

import json
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from secure_backup import (
    create_config_backup,
    create_project_snapshot,
    create_state_snapshot,
    verify_state_snapshot,
)
import run_secure_project_snapshot as project_snapshot_runner


def test_project_snapshot_excludes_secrets_dependencies_and_symlinks() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        project = root / "project"
        output = root / "runtime" / "backups"
        (project / "docs").mkdir(parents=True)
        (project / "docs" / "guide.md").write_text("safe", encoding="utf-8")
        (project / ".env").write_text("TOKEN=secret", encoding="utf-8")
        (project / "backend").mkdir()
        (project / "backend" / "private.key").write_text("secret", encoding="utf-8")
        (project / "node_modules" / "pkg").mkdir(parents=True)
        (project / "node_modules" / "pkg" / "index.js").write_text("large", encoding="utf-8")
        outside = root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (project / "docs" / "outside-link").symlink_to(outside)

        result = create_project_snapshot(
            project_root=project,
            output_root=output,
            now=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
        )
        archive = Path(result["path"])
        with tarfile.open(archive, "r:gz") as handle:
            names = set(handle.getnames())

        assert "AI-Clone/docs/guide.md" in names
        assert not any(".env" in name for name in names)
        assert not any("node_modules" in name for name in names)
        assert not any("private.key" in name for name in names)
        assert not any("outside-link" in name for name in names)
        assert archive.stat().st_mode & 0o777 == 0o600


def test_config_backup_without_passphrase_writes_manifest_only() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        secrets = root / "secrets"
        output = root / "runtime" / "config"
        secrets.mkdir()
        secret = secrets / "control.env"
        secret.write_text("TOKEN=not-printed", encoding="utf-8")
        secret.chmod(0o600)

        result = create_config_backup(
            secrets_root=secrets,
            output_root=output,
            passphrase=None,
            now=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
        )
        manifest = Path(result["manifest_path"])
        content = manifest.read_text(encoding="utf-8")

        assert result["encrypted"] is False
        assert result["file_count"] == 1
        assert "TOKEN=not-printed" not in content
        assert "control.env" in content
        assert manifest.stat().st_mode & 0o777 == 0o600


def test_state_snapshot_is_private_self_verifying_and_excludes_secret_names() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        state = root / "state"
        output = root / "backups"
        (state / "memory").mkdir(parents=True)
        (state / "memory" / "history.jsonl").write_text('{"id":"one"}\n', encoding="utf-8")
        (state / "memory" / "empty.jsonl").write_text("", encoding="utf-8")
        (state / "persona").mkdir()
        (state / "persona" / "voice.jsonl").write_text('{"id":"voice"}\n', encoding="utf-8")
        (state / ".env").write_text("TOKEN=never-archive", encoding="utf-8")
        (state / "secrets").mkdir()
        (state / "secrets" / "token.txt").write_text("never-archive", encoding="utf-8")
        (state / "automations").mkdir()
        (state / "automations" / "active.jsonl.lock").write_text("ephemeral", encoding="utf-8")
        outside = root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (state / "memory" / "outside-link").symlink_to(outside)

        result = create_state_snapshot(
            state_root=state,
            output_root=output,
            now=datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc),
        )
        archive = Path(result["path"])
        verification = verify_state_snapshot(archive)
        with tarfile.open(archive, "r:gz") as handle:
            names = set(handle.getnames())

        assert result["verified"] is True
        assert verification["verified"] is True
        assert verification["file_count"] == 3
        assert "AI-Clone-State/memory/history.jsonl" in names
        assert "AI-Clone-State/memory/empty.jsonl" in names
        assert "AI-Clone-State/persona/voice.jsonl" in names
        assert not any(".env" in name for name in names)
        assert not any("/secrets/" in name for name in names)
        assert not any(name.endswith(".lock") for name in names)
        assert not any("outside-link" in name for name in names)
        assert archive.stat().st_mode & 0o777 == 0o600


def test_state_snapshot_uses_online_sqlite_backup_and_omits_wal_sidecars() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        state = root / "state"
        output = root / "backups"
        database = state / "memory" / "durable.sqlite3"
        database.parent.mkdir(parents=True)
        connection = sqlite3.connect(database)
        try:
            assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            connection.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO memories(value) VALUES (?)", ("first",))
            connection.commit()
            connection.execute("INSERT INTO memories(value) VALUES (?)", ("uncheckpointed",))
            connection.commit()
            assert database.with_name(f"{database.name}-wal").exists()

            result = create_state_snapshot(
                state_root=state,
                output_root=output,
                now=datetime(2026, 7, 25, 12, 30, tzinfo=timezone.utc),
            )
        finally:
            connection.close()

        archive = Path(result["path"])
        with tarfile.open(archive, "r:gz") as handle:
            names = set(handle.getnames())
            manifest_source = handle.extractfile(".ai-clone-state-backup-manifest.json")
            database_source = handle.extractfile("AI-Clone-State/memory/durable.sqlite3")
            assert manifest_source is not None
            assert database_source is not None
            manifest = json.loads(manifest_source.read().decode("utf-8"))
            restored = root / "restored.sqlite3"
            restored.write_bytes(database_source.read())

        assert "AI-Clone-State/memory/durable.sqlite3" in names
        assert not any(name.endswith(("-wal", "-shm", "-journal")) for name in names)
        database_record = next(
            item for item in manifest["files"] if item["path"] == "memory/durable.sqlite3"
        )
        assert database_record["kind"] == "sqlite_online_backup"
        assert result["skipped"]["sqlite_sidecars"] >= 1
        restored_connection = sqlite3.connect(restored)
        try:
            assert restored_connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert restored_connection.execute(
                "SELECT value FROM memories ORDER BY id"
            ).fetchall() == [("first",), ("uncheckpointed",)]
        finally:
            restored_connection.close()


def test_daily_project_snapshot_also_creates_verified_state_snapshot() -> None:
    project_result = {
        "path": "/private/project.tar.gz",
        "name": "project.tar.gz",
        "file_count": 10,
        "source_bytes": 100,
        "archive_bytes": 80,
        "sha256": "project-hash",
        "retention_removed": [],
    }
    state_result = {
        "path": "/private/state.tar.gz",
        "name": "state.tar.gz",
        "file_count": 4,
        "source_bytes": 40,
        "archive_bytes": 30,
        "sha256": "state-hash",
        "verified": True,
        "skipped": {"lock_files": 1},
    }
    with (
        patch.object(project_snapshot_runner, "create_project_snapshot", return_value=project_result),
        patch.object(project_snapshot_runner, "create_state_snapshot", return_value=state_result),
        patch.object(project_snapshot_runner, "mirror_runs", return_value=True) as mirror_runs,
    ):
        result, ok = project_snapshot_runner.run(api_url="http://example.test")

    assert ok is True
    assert result["state_snapshot"]["verified"] is True
    assert result["state_snapshot"]["sha256"] == "state-hash"
    mirrored_payload = mirror_runs.call_args.args[1][0]
    mirrored_state = mirrored_payload["metadata"]["state_snapshot"]
    assert "path" not in mirrored_state
    assert mirrored_state["verified"] is True
