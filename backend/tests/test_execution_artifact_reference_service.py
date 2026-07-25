from pathlib import Path

import pytest

from app.services.execution_artifact_reference_service import (
    encode_local_execution_artifact_reference,
    resolve_local_execution_artifact_reference,
    validate_remote_execution_artifact_reference,
)


@pytest.mark.parametrize(
    "value",
    [
        "/Users/neo/.codex/ai-clone/state/memory/result.json",
        "/private/tmp/result.json",
        "~/result.json",
        "~neo/result.json",
        "C:\\Users\\neo\\result.json",
        "\\\\server\\share\\result.json",
        "memory/.codex/result.json",
        "memory/%2e%2e/secrets/result.json",
        "file:///Users/neo/result.json",
    ],
)
def test_remote_reference_rejects_host_private_or_traversing_paths(value: str) -> None:
    with pytest.raises(ValueError):
        validate_remote_execution_artifact_reference(value)


@pytest.mark.parametrize(
    "value",
    [
        "state://memory/runner-results/result.json",
        "repo://dispatch/work-order.json",
        "workspace://feezie-os/memory/execution_log.md",
        "memory/legacy-result.json",
        "local-artifact://sha256/20dcb8f9b3ea8a4f675e5c7b2d8d9f410da8b8c7d51f53099ecba01383d32bdf",
    ],
)
def test_remote_reference_accepts_safe_logical_and_legacy_relative_paths(value: str) -> None:
    assert validate_remote_execution_artifact_reference(value) == value


def test_encoder_projects_known_roots_without_exposing_the_host(tmp_path: Path) -> None:
    state_root = tmp_path / "private-state"
    project_root = tmp_path / "project"
    state_path = state_root / "memory" / "runner-results" / "result.json"
    repo_path = project_root / "dispatch" / "work-order.json"

    assert (
        encode_local_execution_artifact_reference(
            str(state_path),
            state_root=state_root,
            project_root=project_root,
        )
        == "state://memory/runner-results/result.json"
    )
    assert (
        encode_local_execution_artifact_reference(
            str(repo_path),
            state_root=state_root,
            project_root=project_root,
        )
        == "repo://dispatch/work-order.json"
    )


def test_encoder_uses_opaque_reference_for_an_external_local_artifact(tmp_path: Path) -> None:
    external_path = tmp_path / "external" / "private-name.txt"
    reference = encode_local_execution_artifact_reference(
        str(external_path),
        state_root=tmp_path / "state",
        project_root=tmp_path / "project",
    )

    assert reference.startswith("local-artifact://sha256/")
    assert "private-name" not in reference
    assert str(tmp_path) not in reference


def test_local_resolver_maps_state_and_repo_references_back_to_authorized_roots(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    project_root = tmp_path / "project"

    assert resolve_local_execution_artifact_reference(
        "state://memory/runner-results/result.json",
        state_root=state_root,
        project_root=project_root,
    ) == state_root / "memory" / "runner-results" / "result.json"
    assert resolve_local_execution_artifact_reference(
        "repo://dispatch/work-order.json",
        state_root=state_root,
        project_root=project_root,
    ) == project_root / "dispatch" / "work-order.json"


def test_local_resolver_rejects_symlink_escape_from_authorized_root(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    outside = tmp_path / "outside"
    state_root.mkdir()
    outside.mkdir()
    (state_root / "memory").symlink_to(outside, target_is_directory=True)

    assert (
        resolve_local_execution_artifact_reference(
            "state://memory/private-result.json",
            state_root=state_root,
            project_root=tmp_path / "project",
        )
        is None
    )
