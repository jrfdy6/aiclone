from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNERS = ROOT / "scripts" / "runners"
if str(RUNNERS) not in sys.path:
    sys.path.insert(0, str(RUNNERS))

from runner_security import (
    require_execution_packet,
    require_repo_path,
    resolve_execution_workspace_root,
    resolve_workspace_root,
    validate_workspace_key,
)


def test_workspace_keys_reject_traversal() -> None:
    with pytest.raises(ValueError):
        validate_workspace_key("../../tmp")


def test_repo_path_rejects_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    with pytest.raises(ValueError):
        require_repo_path(outside, project)


def test_workspace_root_rejects_configured_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "workspaces").mkdir(parents=True)
    with pytest.raises(ValueError):
        resolve_workspace_root(project, "shared_ops", str(tmp_path / "outside"))


def test_execution_packet_requires_dispatch_json(tmp_path: Path) -> None:
    project = tmp_path / "project"
    packet = project / "workspaces" / "demo" / "dispatch" / "work.json"
    packet.parent.mkdir(parents=True)
    packet.write_text("{}")
    assert require_execution_packet(packet, project) == packet.resolve()


def test_execution_packet_accepts_private_workspace_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    state = tmp_path / "private-state"
    packet = state / "workspaces" / "future-workspace" / "dispatch" / "work.json"
    packet.parent.mkdir(parents=True)
    packet.write_text("{}")

    assert require_execution_packet(packet, project, state_root=state) == packet.resolve()
    assert resolve_execution_workspace_root(
        project,
        state,
        "future-workspace",
        str(packet.parent.parent),
    ) == packet.parent.parent.resolve()


def test_execution_workspace_root_rejects_escape_from_project_and_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_execution_workspace_root(
            tmp_path / "project",
            tmp_path / "private-state",
            "future-workspace",
            str(tmp_path / "outside"),
        )
