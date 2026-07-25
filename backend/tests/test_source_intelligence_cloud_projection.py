from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import source_intelligence_cloud_projection as projection  # noqa: E402


def test_cloud_projection_withholds_unclassified_sources_and_all_local_paths() -> None:
    payload = {
        "schema_version": "source_intelligence_index/v1",
        "generated_at": "2026-07-25T12:00:00Z",
        "roots": {
            "private": "/Users/neo/.codex/ai-clone/state/memory/source-intelligence",
        },
        "counts": {
            "total": 3,
            "raw": 1,
            "digested": 0,
            "reviewed": 0,
            "routed": 2,
            "promoted": 0,
            "ignored": 0,
        },
        "sources": [
            {
                "source_id": "private-signal",
                "title": "Private source",
                "summary": "Private insight that must remain on the operator machine.",
                "status": "routed",
                "raw_path": "/Users/neo/private/source.md",
                "route_decision": {
                    "path": "/Users/neo/private/routing.json",
                    "route_affordances": {"post_seed": True},
                },
            },
            {
                "source_id": "shared-signal",
                "source_kind": "transcript_library",
                "source_channel": "youtube",
                "title": "Shareable title",
                "summary": "A deliberately shared, normalized summary.",
                "source_url": "https://www.youtube.com/watch?v=abc&token=do-not-stage#private",
                "status": "routed",
                "raw_path": "/Users/neo/private/raw.md",
                "digest_path": "/Users/neo/private/digest.md",
                "route_decision": {
                    "path": "/Users/neo/private/route.json",
                    "workspace_key": "feezie-os",
                    "priority_lane": "private",
                    "route_affordances": {
                        "post_seed": True,
                        "brain_review": True,
                        "private_note": "do not stage",
                    },
                },
                "sharing": {
                    "classification": "cloud",
                    "content_shareable": True,
                    "reviewer_notes": "/Users/neo/private/review.md",
                },
            },
            {
                "source_id": "/Users/neo/private/source-id",
                "title": "Legacy packet at knowledge/private/draft.md",
                "summary": "Local draft path=/Users/neo/private/draft.md",
                "metadata_path": "knowledge/ingestions/example/shared_source_packet.json",
                "normalized_path": "/Users/neo/private/normalized.md",
                "status": "raw",
            },
        ],
    }

    result = projection.build_cloud_safe_projection(payload)
    serialized = json.dumps(result, sort_keys=True)

    assert result["schema_version"] == "source_intelligence_index/v1"
    assert result["counts"]["total"] == 3
    assert result["cloud_projection"] == {
        "schema_version": "source_intelligence_cloud_projection/v1",
        "policy": "explicit_shareability_only",
        "aggregate_source_count": 3,
        "shared_source_count": 2,
        "withheld_source_count": 1,
        "paths_included": False,
    }
    assert len(result["sources"]) == 2
    assert "private-signal" not in {item["source_id"] for item in result["sources"]}
    shared = next(item for item in result["sources"] if item["source_id"] == "shared-signal")
    assert shared["summary"] == "A deliberately shared, normalized summary."
    assert shared["source_url"] == "https://www.youtube.com/watch?v=abc"
    assert shared["route_decision"] == {
        "workspace_key": "feezie-os",
        "route_affordances": {
            "post_seed": True,
            "brain_review": True,
        },
    }
    legacy = next(item for item in result["sources"] if item["source_id"] != "shared-signal")
    assert legacy["source_id"].startswith("source-")
    assert "title" not in legacy
    assert "summary" not in legacy
    assert "roots" not in result
    assert "raw_path" not in serialized
    assert "digest_path" not in serialized
    assert "metadata_path" not in serialized
    assert "/Users/neo" not in serialized
    assert "Private insight" not in serialized
    assert "do-not-stage" not in serialized


@pytest.mark.parametrize(
    "sharing",
    [
        None,
        {},
        {"classification": "private"},
        {"classification": "shared", "content_shareable": False},
        {"classification": "shared", "content_shareable": "true"},
    ],
)
def test_cloud_projection_requires_unambiguous_shareability(sharing: dict[str, object] | None) -> None:
    source = {
        "source_id": "fixture",
        "title": "Not explicitly shared",
        "summary": "Keep this private.",
        "status": "routed",
    }
    if sharing is not None:
        source["sharing"] = sharing

    result = projection.build_cloud_safe_projection({"sources": [source]})

    assert result["sources"] == []
    assert result["cloud_projection"]["withheld_source_count"] == 1


def test_project_file_writes_only_projection_and_rejects_symlink_target(tmp_path: Path) -> None:
    source_path = tmp_path / "private-index.json"
    output_path = tmp_path / "stage" / "index.json"
    source_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "fixture",
                        "title": "Fixture",
                        "summary": "Safe shared summary.",
                        "status": "reviewed",
                        "digest_path": "knowledge/fixture.shared_source_packet.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = projection.project_source_intelligence_file(source_path, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    assert not list(output_path.parent.glob(".index.json.*.tmp"))

    symlink_target = tmp_path / "outside.json"
    symlink_target.write_text("do not replace\n", encoding="utf-8")
    symlink_output = tmp_path / "symlink-index.json"
    symlink_output.symlink_to(symlink_target)
    with pytest.raises(RuntimeError, match="must not be a symlink"):
        projection.project_source_intelligence_file(source_path, symlink_output)
    assert symlink_target.read_text(encoding="utf-8") == "do not replace\n"
