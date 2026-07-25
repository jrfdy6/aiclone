from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import durable_memory_context  # noqa: E402


def test_private_index_match_is_present_but_content_is_withheld_from_remote_context(
    tmp_path: Path,
) -> None:
    private_path = tmp_path / "private-state" / "memory" / "operator_notes.md"
    indexed = [
        {
            "path": "memory/operator_notes.md",
            "title": "Sensitive private operator plan",
            "score": -1.25,
            "excerpt": "Never include this private sentence in a remote prompt.",
            "source": "codex_memory_index",
            "storage_scope": "private_state_memory",
            "private_state": True,
        }
    ]

    with (
        mock.patch.object(durable_memory_context, "search_index", return_value=indexed),
        mock.patch.object(
            durable_memory_context,
            "_unique_queries",
            return_value=["operator plan"],
        ),
        mock.patch.object(
            durable_memory_context,
            "PRIVATE_MEMORY_ROOT",
            private_path.parent,
        ),
    ):
        context = durable_memory_context.build_durable_memory_context(
            "future-capability",
            ["operator plan"],
        )

    assert context["available"] is True
    assert context["private_state_result_count"] == 1
    assert context["private_content_withheld"] is True
    assert context["source_paths"] == []
    assert context["results"][0]["path"] == "memory/operator_notes.md"
    assert context["results"][0]["title"] == "operator notes"
    assert context["results"][0]["excerpt"] == ""
    assert context["results"][0]["remote_content_policy"] == "metadata_only"
    assert "Never include" not in str(context)


def test_filesystem_fallback_prefers_private_future_workspace_over_project_legacy(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    state = tmp_path / "private-state"
    private_note = (
        state
        / "workspaces"
        / "future-capability"
        / "memory"
        / "decision.md"
    )
    private_note.parent.mkdir(parents=True)
    private_note.write_text(
        "# Private Current Decision\nThe cobalt decision is current.\n",
        encoding="utf-8",
    )
    legacy_note = (
        project
        / "workspaces"
        / "future-capability"
        / "research"
        / "decision.md"
    )
    legacy_note.parent.mkdir(parents=True)
    legacy_note.write_text(
        "# Legacy Decision\nThe cobalt decision is stale.\n",
        encoding="utf-8",
    )

    with (
        mock.patch.object(
            durable_memory_context,
            "search_index",
            side_effect=RuntimeError("index unavailable"),
        ),
        mock.patch.object(
            durable_memory_context,
            "_unique_queries",
            return_value=["cobalt decision"],
        ),
        mock.patch.object(durable_memory_context, "WORKSPACE_ROOT", project),
        mock.patch.object(durable_memory_context, "MEMORY_ROOT", project / "memory"),
        mock.patch.object(durable_memory_context, "KNOWLEDGE_ROOT", project / "knowledge"),
        mock.patch.object(durable_memory_context, "WORKSPACES_ROOT", project / "workspaces"),
        mock.patch.object(durable_memory_context, "PRIVATE_MEMORY_ROOT", state / "memory"),
        mock.patch.object(
            durable_memory_context,
            "PRIVATE_WORKSPACES_ROOT",
            state / "workspaces",
        ),
    ):
        context = durable_memory_context.build_durable_memory_context(
            "future-capability",
            ["cobalt decision"],
        )

    assert context["retrieval_mode"] == "codex_index_warning+filesystem_fallback"
    assert context["private_state_result_count"] == 1
    assert context["results"][0]["path"] == (
        "workspaces/future-capability/memory/decision.md"
    )
    assert context["results"][0]["excerpt"] == ""
    assert context["source_paths"] == [str(legacy_note)]


def test_filesystem_fallback_shadows_runtime_legacy_at_same_logical_memory_path(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    state = tmp_path / "private-state"
    private_note = state / "memory" / "decision.md"
    private_note.parent.mkdir(parents=True)
    private_note.write_text(
        "# Current Decision\nThe heliotrope policy is current.\n",
        encoding="utf-8",
    )
    runtime_legacy = project / "memory" / "runtime" / "decision.md"
    runtime_legacy.parent.mkdir(parents=True)
    runtime_legacy.write_text(
        "# Runtime Legacy\nThe heliotrope policy is stale here.\n",
        encoding="utf-8",
    )

    with (
        mock.patch.object(
            durable_memory_context,
            "search_index",
            side_effect=RuntimeError("index unavailable"),
        ),
        mock.patch.object(
            durable_memory_context,
            "_unique_queries",
            return_value=["heliotrope policy"],
        ),
        mock.patch.object(durable_memory_context, "WORKSPACE_ROOT", project),
        mock.patch.object(durable_memory_context, "MEMORY_ROOT", project / "memory"),
        mock.patch.object(durable_memory_context, "KNOWLEDGE_ROOT", project / "knowledge"),
        mock.patch.object(durable_memory_context, "WORKSPACES_ROOT", project / "workspaces"),
        mock.patch.object(durable_memory_context, "PRIVATE_MEMORY_ROOT", state / "memory"),
        mock.patch.object(
            durable_memory_context,
            "PRIVATE_WORKSPACES_ROOT",
            state / "workspaces",
        ),
    ):
        context = durable_memory_context.build_durable_memory_context(
            "future-capability",
            ["heliotrope policy"],
        )

    assert [item["path"] for item in context["results"]] == ["memory/decision.md"]
    assert context["results"][0]["storage_scope"] == "private_state_memory"
    assert context["results"][0]["excerpt"] == ""
    assert context["source_paths"] == []
