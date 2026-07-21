from __future__ import annotations

import os
import plistlib
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "run_local_codex_bridge.sh"
PLIST = ROOT / "automations" / "launchd" / "com.neo.feezie_codex_bridge.plist"


def test_launch_agent_invokes_private_runtime_python_without_shell_hop() -> None:
    with PLIST.open("rb") as handle:
        payload = plistlib.load(handle)

    arguments = payload["ProgramArguments"]
    assert arguments[:2] == [
        "/Users/neo/.codex/ai-clone/venv/bin/python",
        "/Users/neo/Documents/Codex/AI-Clone/scripts/local_codex_bridge.py",
    ]
    assert "/bin/bash" not in arguments
    assert "WorkingDirectory" not in payload


def test_bridge_wrapper_passes_only_allowlisted_environment(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/bin/bash\n/usr/bin/env | /usr/bin/cut -d= -f1 | /usr/bin/sort\n",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    secret_file = tmp_path / "control_plane.env"
    secret_file.write_text(
        "LOCAL_CODEX_BRIDGE_TOKEN=bridge-worker-only\n"
        "CONTROL_PLANE_SERVICE_TOKEN=must-not-pass\n"
        "CONTROL_PLANE_LOGIN_PASSWORD=must-not-pass\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.update(
        {
            "HOME": str(fake_home),
            "LOCAL_CODEX_BRIDGE_PYTHON": str(fake_python),
            "LOCAL_CODEX_BRIDGE_ENV_FILE": str(secret_file),
            "AI_CLONE_ROOT": str(ROOT),
            "OPENAI_API_KEY": "must-not-pass",
            "PERPLEXITY_API_KEY": "must-not-pass",
            "CRON_ACCESS_TOKEN": "must-not-pass",
            "CONTROL_PLANE_SERVICE_TOKEN": "must-not-pass",
            "CONTROL_PLANE_LOGIN_PASSWORD": "must-not-pass",
            "CONTROL_PLANE_JOB_SIGNING_SECRET": "must-not-pass",
        }
    )

    completed = subprocess.run(
        ["/bin/bash", str(WRAPPER)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    names = set(completed.stdout.splitlines())
    assert "LOCAL_CODEX_BRIDGE_TOKEN" in names
    assert "AI_CLONE_API_BASE_URL" in names
    assert "HOME" in names
    assert "PATH" in names
    assert "OPENAI_API_KEY" not in names
    assert "PERPLEXITY_API_KEY" not in names
    assert "CRON_ACCESS_TOKEN" not in names
    assert "CONTROL_PLANE_SERVICE_TOKEN" not in names
    assert "CONTROL_PLANE_LOGIN_PASSWORD" not in names
    assert "CONTROL_PLANE_JOB_SIGNING_SECRET" not in names
