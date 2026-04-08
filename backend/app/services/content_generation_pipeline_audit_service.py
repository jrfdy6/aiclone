from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.content_generation_context_service import (
    _content_reservoir_snapshot_summary,
    _item_metadata,
    _load_content_reservoir_payload,
    _load_source_assets_payload,
    _runtime_content_reservoir_snapshot_summary,
    _runtime_source_assets_snapshot_summary,
    _source_assets_snapshot_summary,
    build_content_generation_context,
)
from app.services.persona_bundle_context_service import load_bundle_persona_chunks


SOURCE_MODES = ("persona_only", "selected_source", "recent_signals")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown").strip() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _bundle_summary() -> dict[str, Any]:
    chunks = load_bundle_persona_chunks()
    return {
        "total": len(chunks),
        "by_memory_role": _count_values([str((_item_metadata(item).get("memory_role") or "unknown")) for item in chunks]),
        "by_bundle_path": _count_values([str((_item_metadata(item).get("bundle_path") or "unknown")) for item in chunks]) if chunks else {},
        "by_domain_tag": _count_values(
            [str(tag) for item in chunks for tag in ((_item_metadata(item).get("domain_tags") or []))]
        ),
    }


def _mode_summary(
    *,
    user_id: str,
    topic: str,
    context: str,
    content_type: str,
    category: str,
    tone: str,
    audience: str,
    source_mode: str,
    allow_snapshot_rebuild: bool,
) -> dict[str, Any]:
    content_context = build_content_generation_context(
        user_id=user_id,
        topic=topic,
        context=context,
        content_type=content_type,
        category=category,
        tone=tone,
        audience=audience,
        source_mode=source_mode,
        include_audit=True,
        allow_snapshot_rebuild=allow_snapshot_rebuild,
    )
    audit = content_context.audit if isinstance(content_context.audit, dict) else {}
    retrieval = audit.get("retrieval") if isinstance(audit.get("retrieval"), dict) else {}
    curated = retrieval.get("curated_persona_chunks") if isinstance(retrieval.get("curated_persona_chunks"), dict) else {}
    reservoir = (
        retrieval.get("content_reservoir_candidates")
        if isinstance(retrieval.get("content_reservoir_candidates"), dict)
        else {}
    )
    examples = retrieval.get("example_chunks") if isinstance(retrieval.get("example_chunks"), dict) else {}
    curated_source_lane_counts = curated.get("counts_by_source_lane") if isinstance(curated.get("counts_by_source_lane"), dict) else {}
    reservoir_memory_role_counts = (
        reservoir.get("counts_by_memory_role") if isinstance(reservoir.get("counts_by_memory_role"), dict) else {}
    )
    return {
        "grounding_mode": content_context.grounding_mode,
        "grounding_reason": content_context.grounding_reason,
        "framing_modes": content_context.framing_modes,
        "primary_claims": content_context.primary_claims,
        "proof_packets": content_context.proof_packets,
        "story_beats": content_context.story_beats,
        "persona_context_summary": content_context.persona_context_summary,
        "curated_persona_chunk_count": len(content_context.persona_chunks),
        "content_reservoir_chunk_count": len(content_context.content_reservoir_chunks),
        "retrieval_support_count": int(curated_source_lane_counts.get("retrieval_support") or 0),
        "canonical_bundle_count": int(curated_source_lane_counts.get("canonical_bundle") or 0),
        "legacy_support_count": int(curated_source_lane_counts.get("legacy_support") or 0),
        "reservoir_candidate_count": int(reservoir.get("count") or 0),
        "reservoir_candidate_memory_roles": reservoir_memory_role_counts,
        "example_count": int(examples.get("count") or 0),
        "audit": audit,
    }


def _issue(severity: str, phase: str, summary: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "severity": severity,
        "phase": phase,
        "summary": summary,
        "details": details,
    }


def _build_issues(
    *,
    source_assets_snapshot: dict[str, Any],
    runtime_source_assets: dict[str, Any],
    content_reservoir_snapshot: dict[str, Any],
    runtime_content_reservoir: dict[str, Any],
    mode_summaries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    persisted_source_assets = int(source_assets_snapshot.get("item_count") or 0)
    runtime_source_assets_count = int(runtime_source_assets.get("item_count") or 0)
    persisted_reservoir = int(content_reservoir_snapshot.get("item_count") or 0)
    runtime_reservoir = int(runtime_content_reservoir.get("item_count") or 0)

    if runtime_source_assets_count > persisted_source_assets:
        issues.append(
            _issue(
                "high",
                "source_assets",
                "Persisted source assets are lagging runtime inputs.",
                {
                    "persisted_count": persisted_source_assets,
                    "runtime_count": runtime_source_assets_count,
                    "persisted_generated_at": source_assets_snapshot.get("generated_at"),
                    "runtime_generated_at": runtime_source_assets.get("generated_at"),
                },
            )
        )

    if runtime_reservoir > persisted_reservoir:
        issues.append(
            _issue(
                "high",
                "content_reservoir",
                "Persisted content reservoir is lagging runtime inputs.",
                {
                    "persisted_count": persisted_reservoir,
                    "runtime_count": runtime_reservoir,
                    "persisted_generated_at": content_reservoir_snapshot.get("generated_at"),
                    "runtime_generated_at": runtime_content_reservoir.get("generated_at"),
                },
            )
        )

    persona_only_claims = mode_summaries["persona_only"]["primary_claims"]
    for mode in ("selected_source", "recent_signals"):
        summary = mode_summaries[mode]
        if summary["reservoir_candidate_count"] > 0 and summary["retrieval_support_count"] == 0:
            issues.append(
                _issue(
                    "high",
                    "context_assembly",
                    f"{mode} retrieved source-backed support, but none of it reached the curated prompt context.",
                    {
                        "mode": mode,
                        "reservoir_candidate_count": summary["reservoir_candidate_count"],
                        "retrieval_support_count": summary["retrieval_support_count"],
                        "reservoir_candidate_memory_roles": summary["reservoir_candidate_memory_roles"],
                    },
                )
            )
        if summary["primary_claims"] == persona_only_claims:
            issues.append(
                _issue(
                    "medium",
                    "source_mode_effect",
                    f"{mode} is landing on the same primary claims as persona_only.",
                    {
                        "mode": mode,
                        "claims": summary["primary_claims"],
                    },
                )
            )
        ambient_count = int((summary["reservoir_candidate_memory_roles"] or {}).get("ambient") or 0)
        proof_count = int((summary["reservoir_candidate_memory_roles"] or {}).get("proof") or 0)
        if ambient_count >= proof_count and summary["reservoir_candidate_count"] > 0:
            issues.append(
                _issue(
                    "medium",
                    "reservoir_quality",
                    f"{mode} reservoir support is skewing too ambient relative to proof.",
                    {
                        "mode": mode,
                        "ambient_count": ambient_count,
                        "proof_count": proof_count,
                    },
                )
            )

    return issues


def build_content_generation_pipeline_audit(
    *,
    user_id: str,
    topic: str,
    context: str,
    content_type: str,
    category: str,
    tone: str,
    audience: str,
    allow_snapshot_rebuild: bool = True,
) -> dict[str, Any]:
    # Warm the snapshot-backed inputs through the same refresh path content generation uses
    # so the persisted-vs-runtime comparison reflects the current production read model.
    _load_source_assets_payload(allow_runtime_rebuild=True)
    _load_content_reservoir_payload(allow_runtime_rebuild=True)

    source_assets_snapshot = _source_assets_snapshot_summary()
    runtime_source_assets = _runtime_source_assets_snapshot_summary()
    content_reservoir_snapshot = _content_reservoir_snapshot_summary()
    runtime_content_reservoir = _runtime_content_reservoir_snapshot_summary()

    mode_summaries = {
        mode: _mode_summary(
            user_id=user_id,
            topic=topic,
            context=context,
            content_type=content_type,
            category=category,
            tone=tone,
            audience=audience,
            source_mode=mode,
            allow_snapshot_rebuild=allow_snapshot_rebuild,
        )
        for mode in SOURCE_MODES
    }

    issues = _build_issues(
        source_assets_snapshot=source_assets_snapshot,
        runtime_source_assets=runtime_source_assets,
        content_reservoir_snapshot=content_reservoir_snapshot,
        runtime_content_reservoir=runtime_content_reservoir,
        mode_summaries=mode_summaries,
    )

    return {
        "generated_at": _now_iso(),
        "request": {
            "user_id": user_id,
            "topic": topic,
            "context": context,
            "content_type": content_type,
            "category": category,
            "tone": tone,
            "audience": audience,
            "allow_snapshot_rebuild": allow_snapshot_rebuild,
        },
        "phases": {
            "persona_bundle": _bundle_summary(),
            "source_assets": {
                "persisted": source_assets_snapshot,
                "runtime": runtime_source_assets,
            },
            "content_reservoir": {
                "persisted": content_reservoir_snapshot,
                "runtime": runtime_content_reservoir,
            },
            "source_modes": mode_summaries,
        },
        "issues": issues,
    }
