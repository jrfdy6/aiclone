from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codex_subprocess_env import codex_worker_security_args, minimal_codex_env


def test_minimal_codex_env_drops_project_credentials() -> None:
    result = minimal_codex_env(
        {
            "HOME": "/tmp/home",
            "PATH": "/usr/bin",
            "OPENAI_API_KEY": "secret",
            "CONTROL_PLANE_SERVICE_TOKEN": "secret",
            "GMAIL_REFRESH_TOKEN": "secret",
        }
    )
    assert result == {"HOME": "/tmp/home", "PATH": "/usr/bin"}


def test_worker_security_args_use_named_permission_profiles() -> None:
    readonly = codex_worker_security_args(allow_workspace_writes=False)
    writable = codex_worker_security_args(allow_workspace_writes=True)

    assert "--sandbox" not in readonly
    assert "--sandbox" not in writable
    assert "--ephemeral" in readonly
    assert "--strict-config" in readonly
    assert "--ignore-user-config" in readonly
    assert any(item.startswith("permissions.codex-native-readonly-worker=") for item in readonly)
    assert any(item.startswith("permissions.codex-native-workspace-worker=") for item in writable)
    assert any('"."="read"' in item for item in readonly)
    assert any('"."="write"' in item for item in writable)
    assert any('"~/.codex"="deny"' in item for item in readonly)
    assert any('"**/.env*"="deny"' in item for item in readonly)
    assert any("network={enabled=false}" in item for item in readonly)
    assert 'default_permissions="codex-native-readonly-worker"' in readonly
    assert 'default_permissions="codex-native-workspace-worker"' in writable
    assert 'approval_policy="never"' in readonly
    assert 'web_search="disabled"' in readonly
