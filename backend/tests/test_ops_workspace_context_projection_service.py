from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ops_workspace_context_projection_service as context_service
from app.services.ops_workspace_context_projection_service import (
    OpsWorkspaceContextProjectionError,
    build_ops_workspace_context_projection,
    ops_workspace_context_projection_semantic_sha256,
    unavailable_ops_workspace_context_projection,
    validate_ops_workspace_context_projection,
)


WORKSPACES = (
    ("feezie-os", "FEEZIE OS"),
    ("fusion-os", "Fusion OS"),
    ("easyoutfitapp", "Easy Outfit App"),
    ("ai-swag-store", "AI Swag Store"),
    ("agc", "AGC"),
    ("work-life-tools", "Work Life Tools"),
)
OBSERVED_AT = "2026-08-20T06:15:00Z"
CYCLE_ID = "daily-2026-08-20"


def _entries() -> tuple[dict, ...]:
    return tuple(
        {
            "key": key,
            "kind": "workspace",
            "portfolio_visible": True,
            "status": "live",
            "portfolio_label": label,
        }
        for key, label in WORKSPACES
    )


@pytest.fixture
def context_projection(tmp_path: Path, monkeypatch) -> dict:
    state_root = tmp_path / "state"
    prep_root = state_root / "memory" / "standup-prep" / "workspace_sync"
    report_path = state_root / "memory" / "reports" / "portfolio_standup_prep_latest.json"
    prep_root.mkdir(parents=True)
    report_path.parent.mkdir(parents=True)
    source_mtime = datetime(2026, 8, 20, 6, 14, tzinfo=timezone.utc).timestamp()
    results = []

    for key, label in WORKSPACES:
        artifact_path = state_root / "workspaces" / key / "analytics" / "recognizable.md"
        artifact_path.parent.mkdir(parents=True)
        artifact_path.write_text(
            "\n".join(
                (
                    f"# {label} Recognizable Experiment",
                    "",
                    "## Exact Next Move",
                    (
                        "Use the owner-observed signal in this workspace to advance one "
                        "bounded next step; contact owner@example.com only outside this test."
                    ),
                    "Do not expose /private/tmp/owner-private-source.md or "
                    "https://private.example.test/record in the projection.",
                )
            ),
            encoding="utf-8",
        )
        os.utime(artifact_path, (source_mtime, source_mtime))
        prep_path = prep_root / f"{key}.json"
        prep_path.write_text(
            json.dumps(
                {
                    "schema_version": "standup_prep/v2",
                    "workspace_key": key,
                    "cycle_id": CYCLE_ID,
                    "observed_at": OBSERVED_AT,
                    "pm_snapshot": {
                        "cards": [
                            {
                                "title": f"Advance the current {label} experiment",
                                "status": "todo",
                            }
                        ]
                    },
                    "workspace_context": {
                        "available": True,
                        "latest_analytics_path": str(artifact_path),
                    },
                }
            ),
            encoding="utf-8",
        )
        results.append({"workspace_key": key, "prep_json_path": str(prep_path)})

    report_path.write_text(
        json.dumps(
            {
                "schema_version": "portfolio_standup_prep/v1",
                "cycle_id": CYCLE_ID,
                "observed_at": OBSERVED_AT,
                "results": results,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(context_service, "_active_project_entries", _entries)
    return build_ops_workspace_context_projection(
        state_root=state_root,
        report_path=report_path,
    )


def test_projection_proves_recognizable_sources_for_exact_active_portfolio(
    context_projection: dict,
) -> None:
    projection = context_projection

    assert projection["schema_version"] == "ops_workspace_context_projection/v1"
    assert projection["state"] == "ready"
    assert projection["cycle_id"] == CYCLE_ID
    assert projection["clock"]["authority"] == "ai_clone_utc"
    assert [item["workspace_key"] for item in projection["workspaces"]] == [
        key for key, _ in WORKSPACES
    ]
    agc = next(item for item in projection["workspaces"] if item["workspace_key"] == "agc")
    assert agc["state"] == "consumed"
    assert agc["current_focus"]["title"] == "Advance the current AGC experiment"
    assert agc["artifacts"][0]["title"] == "AGC Recognizable Experiment"
    assert agc["artifacts"][0]["reference"] == "workspace://agc/analytics/recognizable.md"
    assert agc["artifacts"][0]["consumption_role"] == "reference_only"
    assert agc["artifacts"][0]["source_state"] == "verified_preexisting"


def test_projection_removes_private_material_without_hiding_the_source_title(
    context_projection: dict,
) -> None:
    serialized = json.dumps(context_projection)

    assert "AGC Recognizable Experiment" in serialized
    assert "owner@example.com" not in serialized
    assert "/private/tmp/owner-private-source.md" not in serialized
    assert "private.example.test" not in serialized
    assert "a private contact" in serialized
    assert "an external reference" in serialized


def test_execution_log_uses_latest_result_and_skips_unfilled_template_copy(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    artifact_path = state_root / "workspaces" / "agc" / "memory" / "execution_log.md"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        "\n".join(
            (
                "## Jean-Claude Workspace Result — 2026-08-18 08:00 UTC",
                "",
                "- Result: Prepared an older generic packet.",
                "",
                "### Outcomes",
                "- Earlier material that should not lead the owner view.",
                "",
                "## Jean-Claude Workspace Result — 2026-08-20 06:00 UTC",
                "",
                "- Result: Prepared the current AGC partner-path experiment for review.",
                "",
                "### Outcomes",
                "- Bound the current capability brief to the governed workspace lane.",
                "- Scheduled timestamp: __________________",
                "",
                "### Follow-ups",
                "- Review the bounded qualification signal before advancing the lane.",
            )
        ),
        encoding="utf-8",
    )
    source_mtime = datetime(2026, 8, 20, 6, 10, tzinfo=timezone.utc).timestamp()
    os.utime(artifact_path, (source_mtime, source_mtime))

    artifact = context_service._artifact_projection(
        kind="execution_log",
        raw_path=artifact_path,
        workspace_key="agc",
        state_root=state_root,
        observed_at=datetime.fromisoformat(OBSERVED_AT.replace("Z", "+00:00")),
    )

    assert artifact is not None
    assert artifact["title"] == (
        "Prepared the current AGC partner-path experiment for review."
    )
    assert "Bound the current capability brief" in artifact["summary"]
    assert "Review the bounded qualification signal" in artifact["summary"]
    assert "Earlier material" not in artifact["summary"]
    assert "___" not in artifact["summary"]


def test_analytics_prefers_the_owner_decision_surface_over_repo_completion_copy(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    artifact_path = state_root / "workspaces" / "agc" / "analytics" / "baseline.md"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        "\n".join(
            (
                "# AGC Qualification Baseline",
                "",
                "## Bounded Opportunity",
                "Capture the current qualification signal before advancing the lane.",
                "",
                "## Completion Path",
                "Repo-side scope is complete once this file exists.",
            )
        ),
        encoding="utf-8",
    )
    source_mtime = datetime(2026, 8, 20, 6, 10, tzinfo=timezone.utc).timestamp()
    os.utime(artifact_path, (source_mtime, source_mtime))

    artifact = context_service._artifact_projection(
        kind="analytics",
        raw_path=artifact_path,
        workspace_key="agc",
        state_root=state_root,
        observed_at=datetime.fromisoformat(OBSERVED_AT.replace("Z", "+00:00")),
    )

    assert artifact is not None
    assert artifact["summary"] == (
        "Capture the current qualification signal before advancing the lane."
    )


def test_projection_rejects_partial_or_tampered_portfolio(
    context_projection: dict,
) -> None:
    partial = copy.deepcopy(context_projection)
    partial["workspaces"] = partial["workspaces"][:-1]
    with pytest.raises(OpsWorkspaceContextProjectionError, match="exact active"):
        validate_ops_workspace_context_projection(partial)

    tampered = copy.deepcopy(context_projection)
    tampered["workspaces"][0]["artifacts"][0]["reference"] = (
        "workspace://agc/analytics/wrong-workspace.md"
    )
    with pytest.raises(OpsWorkspaceContextProjectionError, match="artifact"):
        validate_ops_workspace_context_projection(tampered)

    false_consumption = copy.deepcopy(context_projection)
    false_consumption["workspaces"][0]["artifacts"][0]["source_state"] = (
        "changed_since_cycle"
    )
    with pytest.raises(OpsWorkspaceContextProjectionError, match="changed workspace source"):
        validate_ops_workspace_context_projection(false_consumption)

    missing_reason = copy.deepcopy(context_projection)
    missing_reason["state"] = "degraded"
    missing_reason["reason_codes"] = ["workspace_context_projection_incomplete"]
    missing_reason["workspaces"][0]["state"] = "partial"
    missing_reason["workspaces"][0]["artifacts"] = []
    with pytest.raises(OpsWorkspaceContextProjectionError, match="requires a reason"):
        validate_ops_workspace_context_projection(missing_reason)


def test_unavailable_projection_claims_no_consumed_context() -> None:
    projection = unavailable_ops_workspace_context_projection(
        "workspace_context_projection_not_synced"
    )

    assert validate_ops_workspace_context_projection(projection) == projection
    assert projection["state"] == "unavailable"
    assert projection["observed_at"] is None
    assert projection["cycle_id"] is None
    assert projection["workspaces"] == []


def test_workspace_route_reads_context_projection_without_caching(
    monkeypatch,
    context_projection: dict,
) -> None:
    monkeypatch.setattr(
        "app.routes.workspace.get_snapshot_payload",
        lambda workspace, snapshot_type: context_projection
        if snapshot_type == "ops_workspace_cycle_context"
        else None,
    )

    response = TestClient(app).get("/api/workspace/ops-workspace-context")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json() == context_projection


def test_context_sync_receipt_binds_cycle_and_semantics(
    monkeypatch,
    context_projection: dict,
) -> None:
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda workspace, kind, payload, **kwargs: (
            {"payload": payload, "updated_at": payload["generated_at"]},
            True,
        ),
    )

    response = TestClient(app).post(
        "/api/brain/ops-workspace-context/sync",
        json={
            "schema_version": "ops_workspace_context_projection_sync/v1",
            "generated_at": context_projection["generated_at"],
            "projection": context_projection,
        },
    )

    assert response.status_code == 200
    receipt = response.json()
    assert receipt["disposition"] == "stored"
    assert receipt["cycle_id"] == CYCLE_ID
    assert receipt["observed_at"] == OBSERVED_AT
    assert receipt["semantic_payload_sha256"] == (
        ops_workspace_context_projection_semantic_sha256(context_projection)
    )


def test_context_sync_is_idempotent_for_same_governed_cycle(
    monkeypatch,
    context_projection: dict,
) -> None:
    stored_projection = copy.deepcopy(context_projection)
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda workspace, kind, payload, **kwargs: (
            {
                "payload": stored_projection,
                "updated_at": stored_projection["generated_at"],
            },
            False,
        ),
    )

    response = TestClient(app).post(
        "/api/brain/ops-workspace-context/sync",
        json={
            "schema_version": "ops_workspace_context_projection_sync/v1",
            "generated_at": context_projection["generated_at"],
            "projection": context_projection,
        },
    )

    assert response.status_code == 200
    assert response.json()["stored"] is False
    assert response.json()["disposition"] == "idempotent_same_cycle"
