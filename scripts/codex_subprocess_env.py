"""Minimal environment for Codex CLI child processes.

Codex authenticates from its saved ChatGPT login. Service credentials used by
Railway, Gmail, or other project integrations must never be inherited by a
prompt-driven subprocess.
"""
from __future__ import annotations

import os


SAFE_ENV_NAMES = {
    "ALL_PROXY",
    "CODEX_HOME",
    "HOME",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "NODE_EXTRA_CA_CERTS",
    "NO_PROXY",
    "PATH",
    "SHELL",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TERM",
    "TMPDIR",
    "USER",
}

READONLY_WORKER_PERMISSION_PROFILE = "codex-native-readonly-worker"
WORKSPACE_WORKER_PERMISSION_PROFILE = "codex-native-workspace-worker"


def codex_worker_security_args(*, allow_workspace_writes: bool) -> list[str]:
    """Return fail-closed CLI settings for an unattended Codex child.

    The profile definitions live in the repository's ``.codex/config.toml``.
    Do not add ``--sandbox`` here: legacy sandbox flags override named
    permission profiles and would restore broad filesystem reads.
    """

    profile = (
        WORKSPACE_WORKER_PERMISSION_PROFILE
        if allow_workspace_writes
        else READONLY_WORKER_PERMISSION_PROFILE
    )
    workspace_access = "write" if allow_workspace_writes else "read"
    profile_definition = (
        "{description=\"Bounded unattended Codex worker\","
        "filesystem={"
        "\":minimal\"=\"read\","
        "\":tmpdir\"=\"write\","
        "\":slash_tmp\"=\"write\","
        "\"~/.codex\"=\"deny\","
        "\"~/.openclaw\"=\"deny\","
        "\"~/.ssh\"=\"deny\","
        "\"~/Library/Keychains\"=\"deny\","
        "\"~/Library/Mail\"=\"deny\","
        "\":workspace_roots\"={"
        f"\".\"=\"{workspace_access}\","
        "\".git\"=\"read\","
        "\".codex\"=\"read\","
        "\"**/.env*\"=\"deny\","
        "\"**/secrets\"=\"deny\","
        "\"**/secrets/**\"=\"deny\","
        "\"**/*credential*\"=\"deny\""
        "}},network={enabled=false}}"
    )
    return [
        "--strict-config",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "-c",
        f"permissions.{profile}={profile_definition}",
        "-c",
        f'default_permissions="{profile}"',
        "-c",
        'approval_policy="never"',
        "-c",
        'web_search="disabled"',
    ]


def minimal_codex_env(source: dict[str, str] | None = None) -> dict[str, str]:
    values = source or dict(os.environ)
    return {name: value for name, value in values.items() if name in SAFE_ENV_NAMES and value}
