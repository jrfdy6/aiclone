from __future__ import annotations

from datetime import datetime, timezone

from app.models.standups import StandupEntry
from app.services import standup_service


def test_public_standup_copy_hides_retired_runtime_and_preserves_artifact_context() -> None:
    leaked_path = "/Users/neo/.openclaw/workspace/workspaces/agc/docs/plan.md"
    entry = StandupEntry(
        id="standup-privacy-1",
        owner="Jean-Claude",
        workspace_key="agc",
        status="completed",
        blockers=[f"Review {leaked_path} before the next run."],
        commitments=[],
        needs=[],
        source="codex-chronicle-standup-prep",
        conversation_path=leaked_path,
        payload={
            "summary": f"Ground the next move in {leaked_path}.",
            "source_paths": [leaked_path],
            "private": "CONTROL_PLANE_SERVICE_TOKEN=do-not-return",
        },
        created_at=datetime.now(timezone.utc),
    )

    public = standup_service.public_standup_entry(entry)
    serialized = public.model_dump_json()

    assert "/Users/" not in serialized
    assert ".openclaw" not in serialized.lower()
    assert "do-not-return" not in serialized
    assert "workspaces/agc/docs/plan.md" in serialized
    assert public.conversation_path == "workspaces/agc/docs/plan.md"

    # The presentation boundary must never rewrite the historical source row.
    assert entry.conversation_path == leaked_path
    assert entry.payload["source_paths"] == [leaked_path]


def test_public_standup_list_returns_distinct_safe_models() -> None:
    entry = StandupEntry(
        id="standup-privacy-2",
        owner="Jean-Claude",
        workspace_key="shared_ops",
        status="completed",
        blockers=[],
        commitments=[],
        needs=[],
        source="standup_prep",
        conversation_path="/Users/neo/Documents/Codex/AI-Clone/memory/standup-prep/latest.md",
        payload={
            "summary": "Prepared from /Users/neo/.codex/ai-clone/state/private.json.",
            "prep_json_path": "/Users/neo/Documents/Codex/AI-Clone/memory/standup-prep/latest.json",
        },
        created_at=datetime.now(timezone.utc),
    )

    public = standup_service.public_standup_entries([entry])

    assert public[0] is not entry
    assert public[0].conversation_path == "memory/standup-prep/latest.md"
    assert public[0].payload["prep_json_path"] == "memory/standup-prep/latest.json"
    assert "[local-runtime]" in str(public[0].payload["summary"])
