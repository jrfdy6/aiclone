#!/usr/bin/env python3
"""Build and verify the integrated owner story in an isolated synthetic state root.

This harness deliberately simulates owner approval and publication *only* inside a
marked acceptance database.  It never opens, copies, or mutates the canonical owner
database and it never performs an external network or social-platform action.  The resulting
bounded projections can be served through the normal backend and frontend routes for
browser acceptance without turning fixture events into owner history.

The optional ``codex-remote-safe`` mode calls the saved-login Codex CLI only through
the production closed public-safe packet contract.  Its source and voice fixtures are
explicitly synthetic/public, it cannot read the canonical owner database, and it never
performs a social-platform action.  The model request itself is an external operation.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Awaitable, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, BACKEND, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from app.services.canonical_decision_service import CanonicalDecisionService  # noqa: E402
from app.services.content_learning_service import ContentLearningService  # noqa: E402
from app.services.content_lifecycle_service import (  # noqa: E402
    ContentLifecycleService,
    PrivateContentArtifactStore,
)
from app.services.content_owner_action_service import ContentOwnerActionService  # noqa: E402
from app.services.content_portfolio_selection_service import ContentPortfolioSelectionService  # noqa: E402
from app.services.integrated_content_projection_service import (  # noqa: E402
    build_integrated_content_projection,
)
from app.services.integrated_memory_readiness_service import (  # noqa: E402
    IntegratedMemoryReadinessService,
    RECALL_PROBE_QUERIES,
)
from app.services.integrated_system_store import (  # noqa: E402
    SCHEMA_VERSION,
    IntegratedSystemStore,
    default_database_path,
)
from app.services.integrated_variant_generation_service import (  # noqa: E402
    generate_integrated_variant,
)
from app.services.ops_standup_projection_service import (  # noqa: E402
    build_ops_standup_projection,
)
from app.services.open_brain_db import close_pool  # noqa: E402
from app.services.persona_learning_service import PersonaLearningService  # noqa: E402
from app.services.portfolio_cycle_service import (  # noqa: E402
    PortfolioCycleService,
    active_portfolio_workspaces,
)
from app.services.portfolio_selected_drafting_service import PortfolioSelectedDraftingService  # noqa: E402
from app.services.source_evidence_interpretation_service import (  # noqa: E402
    InterpretationLensService,
    InterpretationSynthesisRouter,
    SourceEvidenceService,
)
from app.services.source_intake_contract_service import (  # noqa: E402
    NormalizedDiscovery,
    SourceIntakeContractService,
)
from app.services.source_processing_service import SourceProcessingService  # noqa: E402
from app.services.workspace_registry_service import workspace_registry_entries  # noqa: E402
from codex_memory_index import search_index, sync_index  # noqa: E402
from verify_integrated_production_projection import (  # noqa: E402
    verify as verify_production_projection_story,
)


HARNESS_SCHEMA = "integrated_owner_acceptance_harness/v1"
RECEIPT_SCHEMA = "integrated_owner_acceptance_receipt/v1"
NAMESPACE = "synthetic_integrated_owner_acceptance_v1"
PREFIX = "acceptance:v1"
MARKER_NAME = ".ai-clone-integrated-acceptance.json"
MARKER_TEXT = "SYNTHETIC ACCEPTANCE CANARY — NOT OWNER HISTORY"
SOURCE_URL = "https://youtube.com/watch?v=AICloneSyntheticCanaryV1"
PUBLICATION_URL = (
    "https://www.linkedin.com/posts/"
    "ai-clone-synthetic-acceptance-canary-not-a-publication-v1"
)
SOURCE_NAME = "Synthetic Field Systems Review"
SOURCE_TITLE = f"[{MARKER_TEXT}] Visible Decision Gates"
THESIS = (
    f"[{MARKER_TEXT}] Visible decision gates make authorized action clear "
    "and reduce ambiguous handoffs."
)
SOURCE_BODY = (
    "Synthetic Field Systems Review reports that visible decision gates reduce "
    "ambiguous handoffs and make the next authorized action clear. The acceptance "
    "fixture also says explicit ownership and evidence links help teams act without "
    "guessing. This text is synthetic and does not describe the owner's experience."
)


def verify_projection_story(
    content: dict[str, Any],
    ops: dict[str, Any],
) -> dict[str, Any]:
    """Verify fixture data while reporting controller readiness separately."""

    return verify_production_projection_story(
        content,
        ops,
        require_action_readiness=False,
    )


BASE_BODY = (
    f"[{MARKER_TEXT}]\n\n"
    "Synthetic Field Systems Review reports that visible decision gates reduce "
    "ambiguous handoffs and make the next authorized action clear. Explicit ownership "
    "and evidence links help teams act without guessing.\n\n"
    "This acceptance-only copy applies that external evidence as a systems principle. "
    "It is not a claim about the owner's lived experience. "
    f"Source: {SOURCE_URL}"
)


CanonicalGenerator = Callable[[dict[str, Any]], Awaitable[Any]]
VariantGenerator = Callable[[dict[str, Any]], Awaitable[Any]]


class AcceptanceHarnessError(RuntimeError):
    """Raised when isolation or integrated acceptance verification fails."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(dict(value), indent=2, sort_keys=True) + "\n")


def _marker_payload() -> dict[str, Any]:
    return {
        "schema_version": HARNESS_SCHEMA,
        "namespace": NAMESPACE,
        "authority": "isolated_synthetic_acceptance_only",
        "canonical_owner_fact_claims": False,
        "external_side_effects_allowed": False,
    }


def _assert_isolated_root(
    output_root: Path,
    *,
    canonical_database_path: Path | None,
) -> Path:
    expanded = output_root.expanduser()
    if expanded.exists() and expanded.is_symlink():
        raise AcceptanceHarnessError("acceptance root cannot be a symlink")
    resolved = expanded.resolve()
    if not any(token in str(resolved).lower() for token in ("acceptance", "canary")):
        raise AcceptanceHarnessError("acceptance root must be visibly named acceptance or canary")
    database = resolved / "state" / "system" / "ai-clone.sqlite3"
    protected = {
        (Path.home() / ".codex" / "ai-clone" / "state" / "system" / "ai-clone.sqlite3").resolve(),
    }
    if canonical_database_path is not None:
        protected.add(Path(canonical_database_path).expanduser().resolve())
    else:
        # Callers that need to point AI_CLONE_STATE_ROOT at the acceptance root
        # (for example model generation or browser serving) must capture
        # and pass the original canonical path before changing that environment.
        protected.add(default_database_path().expanduser().resolve())
    if database.resolve() in protected or resolved in {item.parent for item in protected}:
        raise AcceptanceHarnessError("acceptance target resolves to canonical owner state")

    marker = resolved / MARKER_NAME
    if resolved.exists():
        entries = list(resolved.iterdir())
        if entries and not marker.is_file():
            raise AcceptanceHarnessError("existing acceptance root lacks the exact isolation marker")
        if marker.is_file():
            try:
                existing = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise AcceptanceHarnessError("acceptance isolation marker is invalid") from exc
            if existing != _marker_payload():
                raise AcceptanceHarnessError("acceptance isolation marker does not match this harness")
        if any(path.is_symlink() for path in resolved.rglob("*")):
            raise AcceptanceHarnessError("acceptance root cannot contain symlinks")
    resolved.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        _write_json(marker, _marker_payload())
    return resolved


async def _deterministic_canonical_generator(request: dict[str, Any]) -> list[str]:
    context = request.get("context") if isinstance(request.get("context"), dict) else {}
    if (
        request.get("topic") != THESIS
        or request.get("content_type") != "canonical_post"
        or context.get("source_url") != SOURCE_URL
        or context.get("source_author") != SOURCE_NAME
        or context.get("draft_authority") != "portfolio_selected"
    ):
        raise AcceptanceHarnessError("deterministic generator received the wrong canonical context")
    return [BASE_BODY]


async def _deterministic_variant_generator(request: dict[str, Any]) -> list[str]:
    context = request.get("context") if isinstance(request.get("context"), dict) else {}
    base = str(context.get("base_post") or "").strip()
    platform = str(request.get("platform") or "").strip().lower()
    if platform not in {"linkedin", "instagram"} or MARKER_TEXT not in base:
        raise AcceptanceHarnessError("variant generator received an unmarked or unsupported request")
    lead = (
        "LinkedIn acceptance adaptation: the next authorized action should be visible."
        if platform == "linkedin"
        else "Instagram acceptance adaptation: can your team see the next authorized action?"
    )
    # Keeping the exact parent copy beneath a platform lead proves that thesis,
    # evidence, attribution, and safety bytes cannot silently disappear.
    return [f"[{MARKER_TEXT}]\n\n{lead}\n\n{base}"]


def _revision_row(store: IntegratedSystemStore, idempotency_key: str) -> dict[str, Any] | None:
    with store.connection() as connection:
        row = connection.execute(
            """SELECT r.*,a.content_sha256 FROM content_revisions r
            JOIN artifacts a ON a.artifact_id=r.body_artifact_id
            WHERE r.idempotency_key=?""",
            (idempotency_key,),
        ).fetchone()
    return dict(row) if row else None


def _event_exists(store: IntegratedSystemStore, idempotency_key: str) -> bool:
    with store.connection() as connection:
        return bool(
            connection.execute(
                "SELECT 1 FROM learning_events WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        )


def _complete_scenario_exists(store: IntegratedSystemStore) -> bool:
    try:
        with store.connection() as connection:
            required = (
                connection.execute(
                    "SELECT 1 FROM content_revisions WHERE idempotency_key=?",
                    (f"content-edit:{PREFIX}:manual-edit",),
                ).fetchone(),
                connection.execute(
                    "SELECT 1 FROM learning_events WHERE idempotency_key=?",
                    (f"content-owner-action:{PREFIX}:publication",),
                ).fetchone(),
                connection.execute(
                    "SELECT 1 FROM readiness_receipts WHERE idempotency_key=? AND status='ready'",
                    (f"memory-readiness:{PREFIX}:memory",),
                ).fetchone(),
                connection.execute(
                    "SELECT 1 FROM ops_conclusions WHERE portfolio_cycle_id=? AND status='complete'",
                    (f"{PREFIX}:portfolio",),
                ).fetchone(),
                connection.execute(
                    "SELECT 1 FROM decision_records WHERE idempotency_key=? AND status='resolved'",
                    (f"{PREFIX}:decision",),
                ).fetchone(),
            )
        return all(required)
    except sqlite3.Error:
        return False


def _write_retrieval_projection(
    *,
    store: IntegratedSystemStore,
    state_root: Path,
    project_root: Path,
    index_path: Path,
) -> dict[str, Any]:
    with store.connection() as connection:
        rows = connection.execute(
            """SELECT memory_entry_id,memory_lane,subject_type,subject_id,fact_json
            FROM structured_memory_entries ORDER BY memory_entry_id"""
        ).fetchall()
    facts = [
        {
            "memory_entry_id": row["memory_entry_id"],
            "memory_lane": row["memory_lane"],
            "subject_type": row["subject_type"],
            "subject_id": row["subject_id"],
            "fact_sha256": _sha256_bytes(str(row["fact_json"]).encode("utf-8")),
        }
        for row in rows
    ]
    memory_projection = state_root / "memory" / "integrated-owner-acceptance.md"
    lines = [
        f"# {MARKER_TEXT}",
        "",
        "This file is an isolated retrieval projection and not canonical owner memory.",
        "",
        *[f"- Recall probe: {query}" for query in RECALL_PROBE_QUERIES],
        "",
        f"- Content thesis: {THESIS}",
        f"- Structured memory entries: {len(facts)}",
        f"- Entry receipt digest: {_sha256_json(facts)}",
    ]
    _atomic_write_text(memory_projection, "\n".join(lines) + "\n")
    _atomic_write_text(
        project_root / "SOURCE_OF_TRUTH.md",
        f"# {MARKER_TEXT}\n\nSynthetic acceptance retrieval root only.\n",
    )
    return sync_index(
        project_root=project_root,
        state_root=state_root,
        index_path=index_path,
    )


def _build_scenario(
    *,
    store: IntegratedSystemStore,
    artifacts: PrivateContentArtifactStore,
    state_root: Path,
    retrieval_project_root: Path,
    retrieval_index_path: Path,
    canonical_generator: CanonicalGenerator,
    variant_generator: VariantGenerator,
    require_generation_receipt: bool,
) -> None:
    intake = SourceIntakeContractService(store)
    processing = SourceProcessingService(store, artifacts)
    lifecycle = ContentLifecycleService(store, artifacts)
    playlist = intake.register(
        NormalizedDiscovery(
            origin="youtube_playlist",
            source_kind="video",
            discovery_route=f"{NAMESPACE}:designated_owner_playlist_simulation",
            idempotency_key=f"{PREFIX}:playlist-discovery",
            canonical_url=SOURCE_URL,
            external_ref=SOURCE_URL,
            author_or_publisher=SOURCE_NAME,
            title=SOURCE_TITLE,
            rights_state="permitted",
            metadata={
                "acceptance_namespace": NAMESPACE,
                "synthetic": True,
                "sharing": {
                    "schema_version": "integrated_source_remote_sharing/v1",
                    "classification": "public",
                    "content_shareable": True,
                    "basis": "isolated_synthetic_fixture",
                },
            },
        )
    )
    watchlist = intake.register(
        NormalizedDiscovery(
            origin="youtube_watchlist",
            source_kind="video",
            discovery_route=f"{NAMESPACE}:watchlists_yaml_simulation",
            idempotency_key=f"{PREFIX}:watchlist-discovery",
            canonical_url=SOURCE_URL,
            external_ref=SOURCE_URL,
            author_or_publisher=SOURCE_NAME,
            title=SOURCE_TITLE,
            rights_state="permitted",
            metadata={
                "acceptance_namespace": NAMESPACE,
                "synthetic": True,
                "sharing": {
                    "schema_version": "integrated_source_remote_sharing/v1",
                    "classification": "public",
                    "content_shareable": True,
                    "basis": "isolated_synthetic_fixture",
                },
            },
        )
    )
    if playlist["source"]["source_id"] != watchlist["source"]["source_id"]:
        raise AcceptanceHarnessError("duplicate routes did not resolve to one canonical source")
    source_id = str(playlist["source"]["source_id"])
    processing.qualify(
        discovery_id=str(playlist["discovery"]["discovery_id"]),
        relevance_state="qualified",
        admissibility_state="admissible",
        reason="isolated_synthetic_acceptance",
    )
    capture = processing.attach_captured_text(
        source_id=source_id,
        text=SOURCE_BODY,
        capture_kind="transcript",
        metadata={"acceptance_namespace": NAMESPACE, "synthetic": True},
    )
    reused = processing.attach_captured_text(
        source_id=source_id,
        text=SOURCE_BODY,
        capture_kind="transcript",
        metadata={"acceptance_namespace": NAMESPACE, "synthetic": True},
    )
    if not reused["reused"] or reused["artifact"]["artifact_id"] != capture["artifact"]["artifact_id"]:
        raise AcceptanceHarnessError("duplicate discovery did not reuse the captured transcript")

    evidence = SourceEvidenceService(store).record(
        source_id=source_id,
        extractor_name="authoritative_evidence",
        extractor_version="1.0.0",
        artifact_id=str(capture["artifact"]["artifact_id"]),
        evidence_refs=[
            {
                "kind": "transcript_span",
                "start": 0,
                "end": len(SOURCE_BODY),
                "source_url": SOURCE_URL,
            }
        ],
        confidence=1.0,
        idempotency_key=f"{PREFIX}:evidence",
    )
    lens_service = InterpretationLensService(store)
    worldview = lens_service.record_reading(
        evidence_id=str(evidence["evidence_id"]),
        lens_name="worldview_alignment",
        lens_version="1.0.0",
        reading={
            "canonical_belief_ref": "belief:humane-clarity",
            "assessment": "synthetic fixture aligns with a governed belief",
        },
        confidence=0.98,
        idempotency_key=f"{PREFIX}:worldview-lens",
        provenance_kind="synthesized_lens",
    )
    audience = lens_service.record_reading(
        evidence_id=str(evidence["evidence_id"]),
        lens_name="audience_relevance",
        lens_version="1.0.0",
        reading={"audience": "education and technology operators", "relevance": "high"},
        confidence=0.91,
        idempotency_key=f"{PREFIX}:audience-lens",
        provenance_kind="deterministic_policy",
    )
    routed = InterpretationSynthesisRouter(store, lifecycle).create_opportunity(
        evidence_id=str(evidence["evidence_id"]),
        interpretation_ids=[
            str(worldview["interpretation_id"]),
            str(audience["interpretation_id"]),
        ],
        thesis=THESIS,
        canonical_belief_refs=["belief:humane-clarity"],
        truth_state="pass",
        safety_state="pass",
        attribution_state="required",
        idempotency_key=f"{PREFIX}:synthesis",
        canonical_pillar="leadership_operator",
        intent="value",
        portfolio_score=1.0,
    )
    if routed["opportunity"]["status"] != "qualified":
        raise AcceptanceHarnessError("synthesis did not create a qualified opportunity")

    def pre_draft_retrieval_refresh() -> dict[str, Any]:
        return _write_retrieval_projection(
            store=store,
            state_root=state_root,
            project_root=retrieval_project_root,
            index_path=retrieval_index_path,
        )

    def pre_draft_recall_search(query: str) -> list[dict[str, Any]]:
        return search_index(
            query,
            project_root=retrieval_project_root,
            state_root=state_root,
            index_path=retrieval_index_path,
            sync_if_missing=False,
        )

    pre_draft_observed_at = datetime.now(timezone.utc)
    pre_draft_readiness = IntegratedMemoryReadinessService(store).run_readiness(
        cycle_id=f"{PREFIX}:portfolio",
        retrieval_refresh=pre_draft_retrieval_refresh,
        recall_search=pre_draft_recall_search,
        now=pre_draft_observed_at,
    )
    if pre_draft_readiness["status"] != "ready":
        raise AcceptanceHarnessError(
            "pre-draft memory readiness did not pass before portfolio selection"
        )
    portfolio = PortfolioCycleService(store)
    registry_entries = workspace_registry_entries()
    expected_workspaces = active_portfolio_workspaces(registry_entries)
    goals_by_workspace = {
        str(entry["key"]): dict(entry["goal_contract"])
        for entry in registry_entries
        if str(entry.get("key") or "") in expected_workspaces
    }
    portfolio.start_cycle(
        portfolio_cycle_id=f"{PREFIX}:portfolio",
        cycle_date=pre_draft_observed_at.date(),
        expected_workspaces=expected_workspaces,
        readiness_id=str(pre_draft_readiness["readiness_id"]),
        morning_brief_ref=f"{NAMESPACE}:synthetic-morning-brief",
        observed_at=pre_draft_observed_at,
    )
    selection = ContentPortfolioSelectionService(store).select(
        portfolio_cycle_id=f"{PREFIX}:portfolio",
        opportunity_ids=[str(routed["opportunity"]["opportunity_id"])],
        development_slots=2,
    )
    if selection["selected_opportunity_ids"] != [
        str(routed["opportunity"]["opportunity_id"])
    ]:
        raise AcceptanceHarnessError("qualified opportunity was not selected for drafting")

    base_key = f"portfolio-selected-base:{routed['opportunity']['opportunity_id']}"
    base = _revision_row(store, base_key)
    if base is None:
        generated = asyncio.run(
            PortfolioSelectedDraftingService(
                lifecycle,
                require_generation_receipt=require_generation_receipt,
            ).draft_one(
                opportunity_id=str(routed["opportunity"]["opportunity_id"]),
                portfolio_cycle_id=f"{PREFIX}:portfolio",
                controls={
                    "audience_emphasis": "leadership",
                    "tone": "conversational",
                },
                generator=canonical_generator,
            )
        )
        post_id = str(generated["post"]["post_id"])
        base_revision_id = str(generated["revisions"][0]["revision_id"])
    else:
        post_id = str(base["post_id"])
        base_revision_id = str(base["revision_id"])

    variant_specs = (
        (
            "linkedin",
            {"hook": "direct", "length": "medium", "audience_emphasis": "leadership"},
        ),
        ("instagram", {"hook": "question", "length": "short"}),
    )
    variant_rows: dict[str, dict[str, Any]] = {}
    for platform, controls in variant_specs:
        variant_key = f"{PREFIX}:{platform}-variant"
        row = _revision_row(store, variant_key)
        if row is None:
            asyncio.run(
                generate_integrated_variant(
                    lifecycle=lifecycle,
                    post_id=post_id,
                    parent_revision_id=base_revision_id,
                    platform=platform,
                    controls=controls,
                    idempotency_key=variant_key,
                    generator=variant_generator,
                )
            )
            row = _revision_row(store, variant_key)
        if row is None:
            raise AcceptanceHarnessError(f"{platform} variant was not persisted")
        variant_rows[platform] = row

    owner_actions = ContentOwnerActionService(lifecycle)
    selected = variant_rows["instagram"]
    if not _event_exists(store, f"content-owner-action:{PREFIX}:variant-selected"):
        owner_actions.record_learning_action(
            post_id=post_id,
            revision_id=str(selected["revision_id"]),
            event_kind="variant_selected",
            revision_sha256=str(selected["content_sha256"]),
            owner_confirmed=True,
            event_at=None,
            integrity_confirmation=None,
            platform=None,
            public_url=None,
            idempotency_key=f"{PREFIX}:variant-selected",
        )

    edit_key = f"content-edit:{PREFIX}:manual-edit"
    edited = _revision_row(store, edit_key)
    if edited is None:
        # The artifact store accepts logical refs, not artifact IDs. Resolve the
        # exact selected bytes before creating the immutable child.
        with store.connection() as connection:
            artifact = connection.execute(
                "SELECT logical_ref FROM artifacts WHERE artifact_id=?",
                (selected["body_artifact_id"],),
            ).fetchone()
        if not artifact:
            raise AcceptanceHarnessError("selected variant artifact is missing")
        selected_body = artifacts.read_text(str(artifact["logical_ref"]))
        edited_result = owner_actions.record_manual_edit(
            post_id=post_id,
            parent_revision_id=str(selected["revision_id"]),
            body=(
                f"{selected_body}\n\n"
                "Synthetic acceptance edit: platform adaptation only; no owner fact was asserted."
            ),
            edit_classification="platform",
            idempotency_key=f"{PREFIX}:manual-edit",
        )
        edited = _revision_row(store, edit_key)
        if edited is None or edited_result["revision_id"] != edited["revision_id"]:
            raise AcceptanceHarnessError("immutable classified edit was not persisted")

    approved_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    published_at = approved_at + timedelta(minutes=1)
    if not _event_exists(store, f"content-owner-action:{PREFIX}:owner-approval"):
        owner_actions.record_learning_action(
            post_id=post_id,
            revision_id=str(edited["revision_id"]),
            event_kind="owner_approved",
            revision_sha256=str(edited["content_sha256"]),
            owner_confirmed=True,
            event_at=approved_at.isoformat(),
            integrity_confirmation={
                "truth": True,
                "safety": True,
                "privacy": True,
                "attribution": True,
            },
            platform=None,
            public_url=None,
            idempotency_key=f"{PREFIX}:owner-approval",
        )
    if not _event_exists(store, f"content-owner-action:{PREFIX}:publication"):
        owner_actions.record_learning_action(
            post_id=post_id,
            revision_id=str(edited["revision_id"]),
            event_kind="publication_confirmed",
            revision_sha256=str(edited["content_sha256"]),
            owner_confirmed=True,
            event_at=published_at.isoformat(),
            integrity_confirmation=None,
            platform="linkedin",
            public_url=PUBLICATION_URL,
            idempotency_key=f"{PREFIX}:publication",
        )
    if not _event_exists(store, f"{PREFIX}:conversation"):
        ContentLearningService(store).record(
            post_id=post_id,
            revision_id=str(edited["revision_id"]),
            event_kind="meaningful_conversation_confirmed",
            payload={
                "interaction_ref": f"{NAMESPACE}:synthetic-conversation",
                "confirmed_by_owner": True,
                "synthetic_acceptance": True,
            },
            idempotency_key=f"{PREFIX}:conversation",
        )

    persona = PersonaLearningService(store)
    candidate = persona.create_candidate(
        candidate_kind="reversible_pattern",
        claim={
            "pattern": "make the next authorized action visible",
            "acceptance_namespace": NAMESPACE,
            "synthetic": True,
        },
        idempotency_key=f"{PREFIX}:persona-candidate",
    )
    persona_result = persona.attach_evidence(
        candidate_id=str(candidate["persona_candidate_id"]),
        context_key=f"{NAMESPACE}:context-1",
        post_id=post_id,
        revision_id=str(edited["revision_id"]),
        source_id=source_id,
    )
    if persona_result["automatic_promotion_eligible"] is not False:
        raise AcceptanceHarnessError("single synthetic pattern unexpectedly became promotable")

    decisions = CanonicalDecisionService(store)
    decision = decisions.create(
        decision_type="owner_call",
        title=f"[{MARKER_TEXT}] Select the exact acceptance revision",
        payload={
            "route": "ops",
            "interaction_mode": "simple",
            "acceptance_namespace": NAMESPACE,
            "synthetic": True,
        },
        idempotency_key=f"{PREFIX}:decision",
    )
    decisions.link_surface(
        decision_id=str(decision["decision_id"]),
        surface="content",
        external_ref=post_id,
    )
    decisions.link_surface(
        decision_id=str(decision["decision_id"]),
        surface="ops",
        external_ref=f"{PREFIX}:portfolio",
    )
    if decision["status"] == "open":
        decision = decisions.transition(
            decision_id=str(decision["decision_id"]),
            expected_version=int(decision["state_version"]),
            new_status="resolved",
            resolution={
                "choice": str(edited["revision_id"]),
                "synthetic_acceptance": True,
            },
        )
    if decision["status"] != "resolved":
        raise AcceptanceHarnessError("acceptance decision did not reach one canonical resolution")

    memory = IntegratedMemoryReadinessService(store)

    def retrieval_refresh() -> dict[str, Any]:
        return _write_retrieval_projection(
            store=store,
            state_root=state_root,
            project_root=retrieval_project_root,
            index_path=retrieval_index_path,
        )

    def recall_search(query: str) -> list[dict[str, Any]]:
        return search_index(
            query,
            project_root=retrieval_project_root,
            state_root=state_root,
            index_path=retrieval_index_path,
            sync_if_missing=False,
        )

    readiness = memory.run_readiness(
        cycle_id=f"{PREFIX}:memory",
        retrieval_refresh=retrieval_refresh,
        recall_search=recall_search,
        now=datetime.now(timezone.utc),
    )
    if readiness["status"] != "ready":
        raise AcceptanceHarnessError("real isolated retrieval refresh and recall probes are not ready")

    portfolio.record_workspace_conclusion(
        portfolio_cycle_id=f"{PREFIX}:portfolio",
        workspace_key="feezie-os",
        conclusion_kind="conclusion",
        provenance_kind="deterministic_policy",
        payload={
            "summary": f"{MARKER_TEXT}: source, content, learning, and memory lineage verified.",
            "goal": goals_by_workspace["feezie-os"],
            "changes_since_prior": [
                {
                    "type": "synthetic_acceptance_completed",
                    "summary": "The isolated source-to-outcome story completed without external mutation.",
                }
            ],
            "system_decisions": [
                {
                    "decision": "acknowledge_verified_synthetic_outcome",
                    "summary": "Treat the isolated completion receipt as proof of mechanics only.",
                }
            ],
            "actions_taken": [
                {
                    "summary": "Executed the isolated bounded content lifecycle fixture.",
                    "result_id": f"{PREFIX}:synthetic-result",
                    "result_status": "done",
                }
            ],
            "completed_work": [{"summary": "Synthetic acceptance story reconstructed"}],
            "decisions": [{"decision_id": decision["decision_id"], "route": "ops"}],
            "evidence_links": [{"url": SOURCE_URL, "label": "Synthetic source fixture"}],
            "next_cycle_inputs": [
                {
                    "type": "synthetic_outcome_receipt",
                    "summary": "Retain the isolated result as mechanical proof, never owner history.",
                }
            ],
        },
        idempotency_key=f"{PREFIX}:workspace-conclusion",
    )
    for workspace_key in expected_workspaces:
        if workspace_key == "feezie-os":
            continue
        goal = goals_by_workspace[workspace_key]
        portfolio.record_workspace_conclusion(
            portfolio_cycle_id=f"{PREFIX}:portfolio",
            workspace_key=workspace_key,
            conclusion_kind="healthy_no_change",
            provenance_kind="deterministic_policy",
            payload={
                "summary": (
                    f"{MARKER_TEXT}: {workspace_key} goal evaluated; this content-only "
                    "fixture contains no eligible workspace-specific action."
                ),
                "goal": goal,
                "system_decisions": [
                    {
                        "decision": "record_goal_scoped_no_action",
                        "summary": "Do not turn unrelated synthetic content evidence into workspace work.",
                    }
                ],
                "no_action": [
                    {
                        "selected": True,
                        "reason": "The isolated fixture supplied no eligible evidence for this workspace goal.",
                        "future_trigger": str(goal["no_action_trigger"]),
                    }
                ],
                "next_cycle_inputs": [
                    {
                        "type": "no_action_trigger",
                        "reason": "Await evidence scoped to this canonical workspace goal.",
                        "future_trigger": str(goal["no_action_trigger"]),
                    }
                ],
            },
            idempotency_key=f"{PREFIX}:workspace-conclusion:{workspace_key}",
        )
    ops = portfolio.conclude_ops(
        portfolio_cycle_id=f"{PREFIX}:portfolio",
        system_health={
            "memory": "ready",
            "content": "ready",
        },
        ops_decisions=[
            {
                "decision_id": decision["decision_id"],
                "summary": "One synthetic decision record is shared by Content and Ops.",
            }
        ],
        recommended_next_actions=[
            "Use the browser contract to inspect this isolated fixture through /workspace."
        ],
    )
    if ops["status"] != "complete":
        raise AcceptanceHarnessError("acceptance Ops conclusion did not complete")


def _database_receipt(store: IntegratedSystemStore) -> dict[str, Any]:
    with store.connection() as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        schema_versions = [
            int(row[0])
            for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]
        table_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "sources",
                "discovery_events",
                "evidence_records",
                "interpretations",
                "content_opportunities",
                "content_generation_jobs",
                "canonical_posts",
                "content_revisions",
                "learning_events",
                "persona_candidates",
                "decision_records",
                "structured_memory_entries",
                "readiness_receipts",
                "workspace_conclusions",
                "ops_conclusions",
            )
        }
        identifiers = {
            "source_id": connection.execute(
                "SELECT source_id FROM discovery_events WHERE idempotency_key=?",
                (f"{PREFIX}:playlist-discovery",),
            ).fetchone()[0],
            "evidence_id": connection.execute(
                "SELECT evidence_id FROM evidence_records WHERE idempotency_key=?",
                (f"{PREFIX}:evidence",),
            ).fetchone()[0],
            "interpretation_ids": [
                row[0]
                for row in connection.execute(
                    """SELECT interpretation_id FROM interpretations
                    WHERE idempotency_key IN (?,?) ORDER BY interpretation_id""",
                    (f"{PREFIX}:worldview-lens", f"{PREFIX}:audience-lens"),
                )
            ],
            "opportunity_id": connection.execute(
                "SELECT opportunity_id FROM content_opportunities WHERE thesis=?",
                (THESIS,),
            ).fetchone()[0],
            "post_id": connection.execute(
                "SELECT post_id FROM content_generation_jobs WHERE opportunity_id=(SELECT opportunity_id FROM content_opportunities WHERE thesis=?)",
                (THESIS,),
            ).fetchone()[0],
            "base_revision_id": connection.execute(
                "SELECT revision_id FROM content_generation_jobs WHERE opportunity_id=(SELECT opportunity_id FROM content_opportunities WHERE thesis=?)",
                (THESIS,),
            ).fetchone()[0],
            "generation_job_id": connection.execute(
                "SELECT generation_job_id FROM content_generation_jobs WHERE opportunity_id=(SELECT opportunity_id FROM content_opportunities WHERE thesis=?)",
                (THESIS,),
            ).fetchone()[0],
            "linkedin_revision_id": connection.execute(
                "SELECT revision_id FROM content_revisions WHERE idempotency_key=?",
                (f"{PREFIX}:linkedin-variant",),
            ).fetchone()[0],
            "instagram_revision_id": connection.execute(
                "SELECT revision_id FROM content_revisions WHERE idempotency_key=?",
                (f"{PREFIX}:instagram-variant",),
            ).fetchone()[0],
            "selected_revision_id": connection.execute(
                "SELECT revision_id FROM content_revisions WHERE idempotency_key=?",
                (f"content-edit:{PREFIX}:manual-edit",),
            ).fetchone()[0],
            "decision_id": connection.execute(
                "SELECT decision_id FROM decision_records WHERE idempotency_key=?",
                (f"{PREFIX}:decision",),
            ).fetchone()[0],
            "persona_candidate_id": connection.execute(
                "SELECT persona_candidate_id FROM persona_candidates WHERE idempotency_key=?",
                (f"{PREFIX}:persona-candidate",),
            ).fetchone()[0],
            "readiness_id": connection.execute(
                "SELECT readiness_id FROM readiness_receipts WHERE idempotency_key=?",
                (f"memory-readiness:{PREFIX}:memory",),
            ).fetchone()[0],
            "portfolio_cycle_id": f"{PREFIX}:portfolio",
            "ops_conclusion_id": connection.execute(
                "SELECT ops_conclusion_id FROM ops_conclusions WHERE portfolio_cycle_id=?",
                (f"{PREFIX}:portfolio",),
            ).fetchone()[0],
        }
        publication = json.loads(
            connection.execute(
                "SELECT payload_json FROM learning_events WHERE idempotency_key=?",
                (f"content-owner-action:{PREFIX}:publication",),
            ).fetchone()[0]
        )
        opportunity_metadata = json.loads(
            connection.execute(
                "SELECT metadata_json FROM content_opportunities WHERE thesis=?",
                (THESIS,),
            ).fetchone()[0]
        )
    if integrity != "ok" or foreign_key_errors:
        raise AcceptanceHarnessError("isolated acceptance database integrity failed")
    return {
        "schema_version": SCHEMA_VERSION,
        "applied_migrations": schema_versions,
        "integrity_check": integrity,
        "foreign_key_error_count": foreign_key_errors,
        "relative_path": "state/system/ai-clone.sqlite3",
        "table_counts": table_counts,
        "identifiers": identifiers,
        "lineage_sha256": _sha256_json(identifiers),
        "synthetic_publication": {
            "platform": publication.get("platform"),
            "public_url": publication.get("public_url"),
            "fixture_only": True,
            "network_verification_performed": False,
        },
        "generation_receipt": opportunity_metadata.get("generation_receipt"),
    }


def _artifact_receipt(store: IntegratedSystemStore, artifact_root: Path) -> dict[str, Any]:
    with store.connection() as connection:
        rows = connection.execute(
            "SELECT artifact_id,content_sha256,logical_ref,byte_size FROM artifacts ORDER BY artifact_id"
        ).fetchall()
    inventory: list[dict[str, Any]] = []
    for row in rows:
        target = (artifact_root / row["logical_ref"]).resolve()
        if artifact_root.resolve() not in target.parents or not target.is_file() or target.is_symlink():
            raise AcceptanceHarnessError("acceptance artifact escaped or is missing from the isolated root")
        actual = target.read_bytes()
        if _sha256_bytes(actual) != row["content_sha256"] or len(actual) != row["byte_size"]:
            raise AcceptanceHarnessError("acceptance artifact bytes do not match canonical SQL")
        inventory.append(
            {
                "artifact_id": row["artifact_id"],
                "content_sha256": row["content_sha256"],
                "byte_size": row["byte_size"],
            }
        )
    return {
        "relative_root": "state/system/artifacts",
        "artifact_count": len(inventory),
        "inventory_sha256": _sha256_json(inventory),
    }


def _browser_contract() -> dict[str, Any]:
    return {
        "status": "ready_for_browser_verification",
        "production_browser_verified": False,
        "route": "/workspace",
        "read_only_api_paths": [
            "/api/workspace/integrated-content",
            "/api/workspace/ops-standup",
        ],
        "required_selectors": [
            "#integrated-content-portfolio",
            "#ops-standup-summary",
            "#owner-decision-surface",
        ],
        "required_visible_text": [
            "Sources → Opportunities → Posts",
            "Ops Standup Summary and Conclusion",
            "Owner Decisions",
            MARKER_TEXT,
            "LinkedIn variant",
            "Instagram variant",
            "Complete source-to-decision lineage",
            "Canonical draft ready for owner review. Nothing was published.",
        ],
        "revision_toggle_contract": {
            "aria_label_prefix": "Select revision for",
            "required_option_kinds": ["base", "linkedin", "instagram", "edit"],
        },
        "launch_environment": {
            "AI_CLONE_STATE_ROOT": "<acceptance-root>/state",
            "AI_CLONE_LOCAL_CANONICAL_PROJECTION": "true",
            "BACKEND_API_URL": "http://127.0.0.1:<backend-port>",
        },
        "required_secret_names_not_stored_in_receipt": [
            "CONTROL_PLANE_SERVICE_TOKEN",
            "CONTROL_PLANE_PASSWORD",
            "CONTROL_PLANE_SESSION_SECRET",
        ],
    }


def _build_receipt(
    *,
    output_root: Path,
    store: IntegratedSystemStore,
    artifact_root: Path,
    generator_mode: str,
    replayed: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    content = build_integrated_content_projection(store=store, artifact_root=artifact_root)
    ops = build_ops_standup_projection(store=store)
    projection_verification = verify_projection_story(content, ops)
    database = _database_receipt(store)
    artifacts = _artifact_receipt(store, artifact_root)
    generation = database.pop("generation_receipt")
    if generator_mode == "codex-remote-safe":
        trace = generation.get("provider_trace") if isinstance(generation, dict) else None
        if (
            not isinstance(trace, list)
            or len(trace) != 1
            or {str(item.get("provider") or "") for item in trace if isinstance(item, dict)}
            != {"codex_cli_saved_login"}
            or generation.get("provider_fallback_used") is not False
            or generation.get("llm_request_count") != 1
            or generation.get("primary_provider") != "codex_cli_saved_login"
            or generation.get("execution_boundary") != "saved_login_codex_remote_safe/v1"
            or generation.get("draft_authority") != "portfolio_selected"
            or not isinstance(generation.get("remote_packet"), dict)
            or generation["remote_packet"].get("classification") != "public_cloud_safe"
        ):
            raise AcceptanceHarnessError(
                "codex-remote-safe acceptance lacks one exact public-safe saved-login receipt"
            )
    elif generation is not None:
        raise AcceptanceHarnessError(
            "deterministic acceptance cannot reuse model-generated isolated state"
        )
    with store.connection() as connection:
        readiness = json.loads(
            connection.execute(
                "SELECT recall_probe_json FROM readiness_receipts WHERE idempotency_key=?",
                (f"memory-readiness:{PREFIX}:memory",),
            ).fetchone()[0]
        )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "passing",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "schema_version": HARNESS_SCHEMA,
            "namespace": NAMESPACE,
            "marker": MARKER_TEXT,
            "scenario_sha256": _sha256_json(
                {
                    "namespace": NAMESPACE,
                    "source_url": SOURCE_URL,
                    "source_body": SOURCE_BODY,
                    "thesis": THESIS,
                    "base_body": BASE_BODY if generator_mode == "deterministic" else None,
                }
            ),
            "replayed_existing_isolated_state": replayed,
        },
        "scope": {
            "authority": "isolated_synthetic_acceptance_sql",
            "canonical_owner_state_mutated": False,
            "canonical_owner_fact_claims": False,
            "synthetic_owner_actions": True,
            "synthetic_publication_event": True,
            "external_network_requests": generator_mode == "codex-remote-safe",
            "external_social_actions": False,
            "production_release_evidence": False,
        },
        "generator": {
            "mode": generator_mode,
            "synthetic_fixture_inputs": True,
            "real_provider_exercised": generator_mode == "codex-remote-safe",
            "receipt": generation if generator_mode == "codex-remote-safe" else None,
        },
        "database": database,
        "artifacts": artifacts,
        "memory": {
            "status": readiness.get("status"),
            "consolidation": readiness.get("consolidation"),
            "retrieval_refresh": readiness.get("retrieval_refresh"),
            "recall_probes": readiness.get("recall_probes"),
            "retrieval_readiness": readiness.get("retrieval_readiness"),
            "index_relative_path": "state/retrieval/acceptance-memory.sqlite3",
        },
        "projections": {
            "verification": projection_verification,
            "content": {
                "relative_path": "evidence/integrated-content.json",
                "sha256": _sha256_json(content),
                "byte_size": len(_canonical_json(content).encode("utf-8")),
                "state": content["state"],
                "counts": content["counts"],
            },
            "ops": {
                "relative_path": "evidence/ops-standup.json",
                "sha256": _sha256_json(ops),
                "byte_size": len(_canonical_json(ops).encode("utf-8")),
                "state": ops["state"],
                "status": ops["status"],
                "portfolio_cycle_id": ops["portfolio_cycle_id"],
                "active_project_recursion_count": len(ops["workspace_recursion"]),
                "shared_ops_reconciliation_evidence": projection_verification[
                    "shared_ops_reconciliation_evidence"
                ],
            },
        },
        "browser_acceptance": _browser_contract(),
        "limitations": [
            "The designated playlist discovery is simulated through the real normalized "
            "intake contract; no platform poll occurred.",
            "The qualified opportunity is selected by the real portfolio policy and drafted "
            "through the leased portfolio-selected canonical drafting job.",
            "Owner approval, publication, and conversation events are synthetic fixture "
            "actions confined to this marked database.",
            (
                "The canonical draft uses an injected deterministic generator."
                if generator_mode == "deterministic"
                else "The canonical draft and linked variants used the one-call saved-login "
                "Codex remote-safe generator with explicitly synthetic/public fixture inputs."
            ),
            "The receipt prepares the actual owner surfaces for browser inspection but does "
            "not claim an authenticated browser session or production deployment.",
        ],
    }
    # Ensure the durable receipt itself never leaks a local path or credential.
    rendered = _canonical_json(receipt)
    forbidden = ("/Users/", "/home/", "file://", "BEGIN PRIVATE KEY", "CONTROL_PLANE_SERVICE_TOKEN=")
    if any(token in rendered for token in forbidden):
        raise AcceptanceHarnessError("acceptance receipt contains private implementation material")
    _write_json(output_root / "evidence" / "integrated-content.json", content)
    _write_json(output_root / "evidence" / "ops-standup.json", ops)
    _write_json(output_root / "evidence" / "acceptance-receipt.json", receipt)
    return receipt, content, ops


def build_isolated_acceptance(
    output_root: Path,
    *,
    generator_mode: str = "deterministic",
    canonical_generator: CanonicalGenerator | None = None,
    variant_generator: VariantGenerator | None = None,
    canonical_database_path: Path | None = None,
) -> dict[str, Any]:
    """Build the acceptance story and return its path-free durable receipt."""

    if generator_mode not in {"deterministic", "codex-remote-safe"}:
        raise AcceptanceHarnessError("unsupported acceptance generator mode")
    root = _assert_isolated_root(
        output_root,
        canonical_database_path=canonical_database_path,
    )
    state_root = root / "state"
    database_path = state_root / "system" / "ai-clone.sqlite3"
    artifact_root = database_path.parent / "artifacts"
    retrieval_project_root = root / "retrieval-project"
    retrieval_index_path = state_root / "retrieval" / "acceptance-memory.sqlite3"
    store = IntegratedSystemStore(database_path)
    artifacts = PrivateContentArtifactStore(artifact_root)
    store.migrate()
    if generator_mode == "codex-remote-safe" and (
        canonical_generator is None or variant_generator is None
    ):
        configured_canonical, configured_variant = _configure_codex_remote_safe(root)
        canonical_generator = canonical_generator or configured_canonical
        variant_generator = variant_generator or configured_variant
    replayed = _complete_scenario_exists(store)
    if not replayed:
        _build_scenario(
            store=store,
            artifacts=artifacts,
            state_root=state_root,
            retrieval_project_root=retrieval_project_root,
            retrieval_index_path=retrieval_index_path,
            canonical_generator=canonical_generator or _deterministic_canonical_generator,
            variant_generator=variant_generator or _deterministic_variant_generator,
            require_generation_receipt=generator_mode == "codex-remote-safe",
        )
    receipt, _, _ = _build_receipt(
        output_root=root,
        store=store,
        artifact_root=artifact_root,
        generator_mode=generator_mode,
        replayed=replayed,
    )
    return receipt


def _configure_codex_remote_safe(
    output_root: Path,
) -> tuple[CanonicalGenerator, VariantGenerator]:
    """Create a labeled synthetic/public voice fixture for isolated model acceptance."""

    voice_corpus = output_root / "fixtures" / "synthetic-public-voice-corpus.jsonl"
    entries = [
        {
            "id": "synthetic-public-voice-1",
            "kind": "positive",
            "provenance": "human_edited",
            "approval_status": "approved",
            "privacy": "public",
            "channel": "linkedin",
            "post_type": "direct_commentary",
            "text": (
                f"[{MARKER_TEXT}] Clear decisions make the next useful action visible. "
                "If people still have to guess, the handoff is not finished."
            ),
        },
        {
            "id": "synthetic-public-voice-2",
            "kind": "positive",
            "provenance": "human_edited",
            "approval_status": "approved",
            "privacy": "public",
            "channel": "linkedin",
            "post_type": "short_commentary",
            "text": (
                f"[{MARKER_TEXT}] I keep returning to one question: can the team see the "
                "boundary, the owner, and the next move? Clarity lets good people act."
            ),
        },
    ]
    _atomic_write_text(
        voice_corpus,
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries),
    )
    from app.services.integrated_production_generator_service import (  # noqa: PLC0415
        generate_production_owner_post,
        generate_production_variant,
    )

    async def generate_with_fixture_voice(
        generation: Mapping[str, Any],
    ) -> Any:
        return await generate_production_owner_post(
            generation,
            voice_corpus_path=voice_corpus,
        )

    async def generate_variant_with_fixture_voice(
        generation: Mapping[str, Any],
    ) -> Any:
        return await generate_production_variant(
            generation,
            voice_corpus_path=voice_corpus,
        )

    generate_with_fixture_voice.__name__ = generate_production_owner_post.__name__
    generate_variant_with_fixture_voice.__name__ = generate_production_variant.__name__
    return generate_with_fixture_voice, generate_variant_with_fixture_voice


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Isolated acceptance/canary root. Defaults to a new private temporary root.",
    )
    parser.add_argument(
        "--generator",
        choices=("deterministic", "codex-remote-safe"),
        default="deterministic",
        help=(
            "Use replay-safe deterministic copy or the one-call saved-login Codex "
            "generator with closed synthetic/public inputs."
        ),
    )
    return parser.parse_args()


def _run() -> int:
    args = parse_args()
    canonical_path = default_database_path().expanduser().resolve()
    output_root = (
        args.output_root.expanduser().resolve()
        if args.output_root
        else Path(tempfile.mkdtemp(prefix="ai-clone-integrated-acceptance-"))
    )
    receipt = build_isolated_acceptance(
        output_root,
        generator_mode=args.generator,
        canonical_database_path=canonical_path,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "schema_version": receipt["schema_version"],
                "output_root": str(output_root),
                "receipt": str(output_root / "evidence" / "acceptance-receipt.json"),
                "lineage_sha256": receipt["database"]["lineage_sha256"],
                "browser_status": receipt["browser_acceptance"]["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    try:
        return _run()
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
