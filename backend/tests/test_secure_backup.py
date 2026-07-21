from __future__ import annotations

import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from secure_backup import create_config_backup, create_project_snapshot


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
