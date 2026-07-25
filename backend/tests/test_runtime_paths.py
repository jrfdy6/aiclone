from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_paths import (  # noqa: E402
    memory_read_candidates,
    memory_state_path,
    resolve_memory_read_path,
    resolve_state_or_project_path,
    resolve_workspace_read_path,
    seed_memory_state_file,
    seed_workspace_state_file,
    workspace_state_path,
    workspace_state_root,
)


def test_memory_state_writes_are_outside_project_and_accept_logical_memory_prefix(tmp_path: Path) -> None:
    state_root = tmp_path / "private-state"

    direct = memory_state_path("LEARNINGS.md", state_root=state_root)
    logical = memory_state_path("memory/LEARNINGS.md", state_root=state_root)

    assert direct == state_root / "memory" / "LEARNINGS.md"
    assert logical == direct


def test_memory_reads_prefer_private_state_then_legacy_runtime_then_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    candidates = memory_read_candidates(
        "memory/persistent_state.md",
        project_root=project_root,
        state_root=state_root,
    )
    assert candidates == (
        state_root / "memory" / "persistent_state.md",
        project_root / "memory" / "runtime" / "persistent_state.md",
        project_root / "memory" / "persistent_state.md",
    )

    project_path = candidates[-1]
    project_path.parent.mkdir(parents=True)
    project_path.write_text("legacy project\n", encoding="utf-8")
    assert (
        resolve_memory_read_path(
            "persistent_state.md",
            project_root=project_root,
            state_root=state_root,
        )
        == project_path
    )

    runtime_path = candidates[1]
    runtime_path.parent.mkdir(parents=True)
    runtime_path.write_text("legacy runtime\n", encoding="utf-8")
    assert (
        resolve_memory_read_path(
            "persistent_state.md",
            project_root=project_root,
            state_root=state_root,
        )
        == runtime_path
    )

    private_path = candidates[0]
    private_path.parent.mkdir(parents=True)
    private_path.write_text("private state\n", encoding="utf-8")
    assert (
        resolve_memory_read_path(
            "persistent_state.md",
            project_root=project_root,
            state_root=state_root,
        )
        == private_path
    )


def test_workspace_state_is_generic_and_reads_fall_back_to_configured_source(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    source_root = project_root / "workspaces" / "future-capability"
    legacy = source_root / "memory" / "execution_log.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy workspace output\n", encoding="utf-8")

    assert workspace_state_root("future-capability", state_root=state_root) == (
        state_root / "workspaces" / "future-capability"
    )
    assert workspace_state_path(
        "future-capability",
        "memory/execution_log.md",
        state_root=state_root,
    ) == state_root / "workspaces" / "future-capability" / "memory" / "execution_log.md"
    assert (
        resolve_workspace_read_path(
            "future-capability",
            "memory/execution_log.md",
            source_root=source_root,
            project_root=project_root,
            state_root=state_root,
        )
        == legacy
    )

    private = workspace_state_path(
        "future-capability",
        "memory/execution_log.md",
        state_root=state_root,
    )
    private.parent.mkdir(parents=True)
    private.write_text("private workspace output\n", encoding="utf-8")
    assert (
        resolve_workspace_read_path(
            "future-capability",
            "memory/execution_log.md",
            source_root=source_root,
            project_root=project_root,
            state_root=state_root,
        )
        == private
    )


def test_config_reader_uses_project_fallback_without_copying_it(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    project_config = project_root / "config" / "workspace_registry.json"
    project_config.parent.mkdir(parents=True)
    project_config.write_text("{}\n", encoding="utf-8")

    resolved = resolve_state_or_project_path(
        "config/workspace_registry.json",
        "config/workspace_registry.json",
        project_root=project_root,
        state_root=state_root,
    )

    assert resolved == project_config
    assert not (state_root / "config" / "workspace_registry.json").exists()


def test_append_seed_copies_legacy_memory_without_modifying_source(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    legacy = project_root / "memory" / "runtime" / "codex_session_handoff.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"entry_id":"legacy"}\n', encoding="utf-8")

    target = seed_memory_state_file(
        "codex_session_handoff.jsonl",
        project_root=project_root,
        state_root=state_root,
    )
    target.write_text(target.read_text(encoding="utf-8") + '{"entry_id":"new"}\n', encoding="utf-8")

    assert target.read_text(encoding="utf-8").splitlines() == [
        '{"entry_id":"legacy"}',
        '{"entry_id":"new"}',
    ]
    assert legacy.read_text(encoding="utf-8") == '{"entry_id":"legacy"}\n'


def test_append_seed_copies_legacy_workspace_file_without_moving_it(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    source_root = project_root / "workspaces" / "legacy-name"
    legacy = source_root / "memory" / "execution_log.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# Existing execution history\n", encoding="utf-8")

    target = seed_workspace_state_file(
        "future-workspace",
        "memory/execution_log.md",
        source_root=source_root,
        project_root=project_root,
        state_root=state_root,
    )

    assert target == state_root / "workspaces" / "future-workspace" / "memory" / "execution_log.md"
    assert target.read_text(encoding="utf-8") == "# Existing execution history\n"
    assert legacy.exists()


def test_concurrent_memory_seed_publishes_one_complete_copy(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    legacy = project_root / "memory" / "codex_session_handoff.jsonl"
    legacy.parent.mkdir(parents=True)
    expected = "".join(f'{{"entry_id":"legacy-{index}"}}\n' for index in range(1_000))
    legacy.write_text(expected, encoding="utf-8")

    def seed() -> Path:
        return seed_memory_state_file(
            "codex_session_handoff.jsonl",
            project_root=project_root,
            state_root=state_root,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        targets = list(executor.map(lambda _index: seed(), range(32)))

    assert len(set(targets)) == 1
    assert targets[0].read_text(encoding="utf-8") == expected
    assert not list(targets[0].parent.glob(f".{targets[0].name}.*.seed"))


def test_memory_seed_rejects_symlink_target_escape(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "private-state"
    outside = tmp_path / "outside.md"
    outside.write_text("preserve\n", encoding="utf-8")
    target = state_root / "memory" / "LEARNINGS.md"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)

    with pytest.raises(ValueError, match="must not traverse a symlink"):
        seed_memory_state_file(
            "LEARNINGS.md",
            project_root=project_root,
            state_root=state_root,
        )

    assert outside.read_text(encoding="utf-8") == "preserve\n"


def test_workspace_state_rejects_symlink_parent_escape(tmp_path: Path) -> None:
    state_root = tmp_path / "private-state"
    outside = tmp_path / "outside"
    outside.mkdir()
    state_root.mkdir()
    (state_root / "workspaces").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="must not traverse a symlink"):
        workspace_state_path(
            "future-workspace",
            "memory/execution_log.md",
            state_root=state_root,
        )

    assert not list(outside.iterdir())


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda root: memory_state_path("../escape", state_root=root),
            "parent traversal",
        ),
        (
            lambda root: workspace_state_path("../../escape", "report.json", state_root=root),
            "Invalid workspace key",
        ),
        (
            lambda root: workspace_state_path("future", "../report.json", state_root=root),
            "parent traversal",
        ),
    ],
)
def test_state_helpers_reject_traversal(call, message: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=message):
        call(tmp_path)
