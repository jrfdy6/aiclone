from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Sequence

from app.services.content_lifecycle_service import (
    ContentLifecycleService,
    PrivateContentArtifactStore,
)
from app.services.content_portfolio_selection_service import ContentPortfolioSelectionService
from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json
from app.services.source_evidence_interpretation_service import (
    INTERPRETATION_PROVENANCE_KINDS,
    InterpretationLensService,
    InterpretationSynthesisRouter,
    SourceEvidenceService,
)


_SAFE_ERROR_RE = re.compile(r"[^a-z0-9_.:-]+")
_LENS_FORBIDDEN_MUTATION_TABLES = (
    "content_opportunities",
    "opportunity_sources",
    "portfolio_selections",
    "canonical_posts",
    "content_revisions",
    "persona_candidates",
    "persona_candidate_evidence",
    "persona_promotions",
    "structured_memory_entries",
    "workspace_conclusions",
    "ops_conclusions",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


@dataclass(frozen=True)
class SourceAnalysisContext:
    source: Mapping[str, Any]
    artifact: Mapping[str, Any]
    body: str
    evidence: Mapping[str, Any] | None = None
    interpretations: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class InterpretationLensDefinition:
    name: str
    version: str
    provenance_kind: str
    evaluate: Callable[
        [SourceAnalysisContext],
        Mapping[str, Any] | Awaitable[Mapping[str, Any]],
    ]

    def validate(self) -> InterpretationLensDefinition:
        if not _clean(self.name) or not _clean(self.version):
            raise ValueError("interpretation lens name and version are required")
        if self.provenance_kind not in INTERPRETATION_PROVENANCE_KINDS:
            raise ValueError("invalid interpretation lens provenance kind")
        return self


EvidenceExtractor = Callable[
    [SourceAnalysisContext], Mapping[str, Any] | Awaitable[Mapping[str, Any]]
]
SynthesisExecutor = Callable[
    [SourceAnalysisContext], Mapping[str, Any] | Awaitable[Mapping[str, Any]]
]


def whole_document_evidence_extractor(context: SourceAnalysisContext) -> dict[str, Any]:
    """Bind the full captured bytes without making an interpretive claim."""

    return {
        "extractor_name": "content_addressed_document_binding",
        "extractor_version": "1.0.0",
        "confidence": 1.0,
        "evidence_refs": [
            {
                "kind": "captured_document",
                "start": 0,
                "end": len(context.body),
            }
        ],
    }


def _bounded_opening_claim(body: str, *, limit: int = 280) -> str:
    compact = " ".join(body.split()).strip()
    if not compact:
        raise ValueError("captured source body is empty")
    sentence = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)[0]
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 1].rstrip(" ,;:-") + "…"


def _deterministic_pillar(body: str) -> tuple[str, list[str]]:
    lowered = body.lower()
    vocabularies = {
        "ai_native": {
            "ai",
            "agent",
            "automation",
            "model",
            "product",
            "prompt",
            "software",
            "technology",
            "workflow",
        },
        "leadership_operator": {
            "adoption",
            "change",
            "decision",
            "leadership",
            "manager",
            "operation",
            "system",
            "team",
        },
        "trust_systems": {
            "admissions",
            "community",
            "education",
            "family",
            "learning",
            "school",
            "student",
            "trust",
        },
    }
    scores = {
        pillar: sorted(term for term in terms if re.search(rf"\b{re.escape(term)}\w*\b", lowered))
        for pillar, terms in vocabularies.items()
    }
    winner = max(
        scores,
        key=lambda pillar: (
            len(scores[pillar]),
            pillar == "leadership_operator",
            pillar,
        ),
    )
    return winner, scores[winner]


def deterministic_exploratory_lenses() -> list[InterpretationLensDefinition]:
    """Low-cost lenses that classify evidence without adopting identity claims."""

    def claim_structure(context: SourceAnalysisContext) -> dict[str, Any]:
        return {
            "reading": {
                "claim_excerpt": _bounded_opening_claim(context.body),
                "reading_kind": "exact_source_opening",
            },
            "confidence": 1.0,
        }

    def audience_relevance(context: SourceAnalysisContext) -> dict[str, Any]:
        pillar, matched_terms = _deterministic_pillar(context.body)
        return {
            "reading": {
                "canonical_pillar": pillar,
                "matched_terms": matched_terms,
                "reading_kind": "keyword_policy",
            },
            "confidence": min(0.85, 0.55 + 0.05 * len(matched_terms)),
        }

    def truth_attribution(context: SourceAnalysisContext) -> dict[str, Any]:
        external = context.source["rights_state"] != "owner_controlled"
        return {
            "reading": {
                "attribution_state": "required" if external else "pass",
                "owner_identity_adoption": False,
                "reading_kind": "rights_policy",
            },
            "confidence": 1.0,
        }

    return [
        InterpretationLensDefinition(
            name="source_claim_structure",
            version="1.0.0",
            provenance_kind="deterministic_policy",
            evaluate=claim_structure,
        ),
        InterpretationLensDefinition(
            name="audience_relevance",
            version="1.0.0",
            provenance_kind="deterministic_policy",
            evaluate=audience_relevance,
        ),
        InterpretationLensDefinition(
            name="truth_attribution_risk",
            version="1.0.0",
            provenance_kind="deterministic_policy",
            evaluate=truth_attribution,
        ),
    ]


def deterministic_exploratory_synthesizer(context: SourceAnalysisContext) -> dict[str, Any]:
    readings = {item["lens_name"]: item["reading"] for item in context.interpretations}
    claim = _clean(readings.get("source_claim_structure", {}).get("claim_excerpt"))
    pillar = _clean(readings.get("audience_relevance", {}).get("canonical_pillar"))
    attribution = _clean(
        readings.get("truth_attribution_risk", {}).get("attribution_state")
    )
    if not claim or not pillar or attribution not in {"pass", "required"}:
        raise ValueError("deterministic synthesis is missing required lens readings")
    source_label = _clean(
        context.source.get("author_or_publisher")
        or context.source.get("title")
        or "the original source"
    )
    return {
        "thesis": f'Explore {source_label}\u2019s claim, “{claim}”, without treating it as owner experience or settled belief.',
        "canonical_belief_refs": [],
        "truth_state": "pass",
        "safety_state": "owner_review_required",
        "attribution_state": attribution,
        "exploratory_conflict": True,
        "canonical_pillar": pillar,
        "intent": "value",
        "portfolio_score": 0.6,
    }


class SourceContentIntelligenceService:
    """Resumable evidence -> lenses -> synthesis boundary for qualified sources.

    The executor callbacks receive only immutable snapshots. Evidence bytes stay in
    the private artifact store, lenses can only return readings, and only the
    synthesis router receives authority to create a ContentOpportunity.
    """

    def __init__(
        self,
        store: IntegratedSystemStore,
        artifact_store: PrivateContentArtifactStore,
    ) -> None:
        self.store = store
        self.artifact_store = artifact_store
        self.lifecycle = ContentLifecycleService(store, artifact_store)
        self.evidence = SourceEvidenceService(store)
        self.lenses = InterpretationLensService(store)
        self.router = InterpretationSynthesisRouter(store, self.lifecycle)
        self.portfolio = ContentPortfolioSelectionService(store)
        self.store.migrate()

    async def process_source(
        self,
        *,
        source_id: str,
        idempotency_key: str,
        lens_definitions: Sequence[InterpretationLensDefinition],
        synthesizer: SynthesisExecutor,
        evidence_extractor: EvidenceExtractor = whole_document_evidence_extractor,
    ) -> dict[str, Any]:
        source_id = _clean(source_id)
        idempotency_key = _clean(idempotency_key)
        if not source_id or not idempotency_key:
            raise ValueError("source intelligence source and idempotency key are required")
        definitions = [definition.validate() for definition in lens_definitions]
        lens_identities = [(definition.name, definition.version) for definition in definitions]
        if len(definitions) < 2 or len(set(lens_identities)) != len(lens_identities):
            raise ValueError("source intelligence requires at least two distinct versioned lenses")

        stage = "source_preflight"
        try:
            source, artifact, body = self._load_qualified_source(source_id)
            source_context = {
                key: source[key]
                for key in (
                    "source_id",
                    "source_kind",
                    "canonical_url",
                    "author_or_publisher",
                    "title",
                    "rights_state",
                    "admissibility_state",
                    "content_sha256",
                    "captured_at",
                )
            }
            artifact_context = {
                key: artifact[key]
                for key in (
                    "artifact_id",
                    "content_sha256",
                    "artifact_kind",
                    "media_type",
                    "byte_size",
                )
            }
            base_context = SourceAnalysisContext(
                source=source_context,
                artifact=artifact_context,
                body=body,
            )

            stage = "authoritative_evidence"
            extraction = dict(await _resolve(evidence_extractor(base_context)))
            normalized_refs = self._normalize_evidence_refs(
                body=body,
                artifact=artifact,
                evidence_refs=extraction.get("evidence_refs"),
            )
            evidence = self.evidence.record(
                source_id=source_id,
                extractor_name=_clean(extraction.get("extractor_name")),
                extractor_version=_clean(extraction.get("extractor_version")),
                artifact_id=artifact["artifact_id"],
                evidence_refs=normalized_refs,
                confidence=self._confidence(extraction.get("confidence")),
                idempotency_key=f"{idempotency_key}:evidence",
            )

            stage = "interpretation_lenses"
            interpretation_context = SourceAnalysisContext(
                source=source_context,
                artifact=artifact_context,
                body=body,
                evidence=evidence,
            )
            interpretations: list[dict[str, Any]] = []
            downstream_fingerprint = self._lens_forbidden_mutation_fingerprint()
            for definition in definitions:
                output = dict(await _resolve(definition.evaluate(interpretation_context)))
                if self._lens_forbidden_mutation_fingerprint() != downstream_fingerprint:
                    raise RuntimeError(
                        f"interpretation lens {definition.name} mutated a forbidden downstream table"
                    )
                reading = output.get("reading")
                if not isinstance(reading, Mapping) or not reading:
                    raise ValueError(f"interpretation lens {definition.name} returned no reading")
                interpretations.append(
                    self.lenses.record_reading(
                        evidence_id=evidence["evidence_id"],
                        lens_name=definition.name,
                        lens_version=definition.version,
                        reading=dict(reading),
                        confidence=self._confidence(output.get("confidence")),
                        idempotency_key=(
                            f"{idempotency_key}:lens:{definition.name}:{definition.version}"
                        ),
                        provenance_kind=definition.provenance_kind,
                    )
                )

            stage = "synthesis_router"
            synthesis_context = SourceAnalysisContext(
                source=source_context,
                artifact=artifact_context,
                body=body,
                evidence=evidence,
                interpretations=tuple(interpretations),
            )
            synthesis = dict(await _resolve(synthesizer(synthesis_context)))
            result = self.router.create_opportunity(
                evidence_id=evidence["evidence_id"],
                interpretation_ids=[item["interpretation_id"] for item in interpretations],
                thesis=_clean(synthesis.get("thesis")),
                canonical_belief_refs=[
                    _clean(value) for value in synthesis.get("canonical_belief_refs", [])
                ],
                truth_state=_clean(synthesis.get("truth_state")),
                safety_state=_clean(synthesis.get("safety_state")),
                attribution_state=_clean(synthesis.get("attribution_state")),
                owner_requested=bool(synthesis.get("owner_requested")),
                exploratory_conflict=bool(synthesis.get("exploratory_conflict")),
                canonical_pillar=(
                    _clean(synthesis.get("canonical_pillar"))
                    if synthesis.get("canonical_pillar") is not None
                    else None
                ),
                intent=(
                    _clean(synthesis.get("intent"))
                    if synthesis.get("intent") is not None
                    else None
                ),
                portfolio_score=synthesis.get("portfolio_score"),
                idempotency_key=f"{idempotency_key}:opportunity",
            )
            opportunity = result["opportunity"]
            self.store.append_event(
                event_type="source_intelligence.completed",
                aggregate_type="source",
                aggregate_id=source_id,
                actor_type="source_intelligence_orchestrator",
                payload={
                    "evidence_id": evidence["evidence_id"],
                    "interpretation_ids": [
                        item["interpretation_id"] for item in interpretations
                    ],
                    "opportunity_id": opportunity["opportunity_id"],
                    "owner_requested": bool(opportunity["owner_requested"]),
                },
                provenance={
                    "pipeline_version": "source_content_intelligence/v1",
                    "source_artifact_sha256": artifact["content_sha256"],
                },
                artifact_refs=[artifact["artifact_id"]],
                idempotency_key=f"source-intelligence-complete:{idempotency_key}",
            )
            return {
                "schema_version": "source_content_intelligence_run/v1",
                "status": "complete",
                "source_id": source_id,
                "artifact": {
                    "artifact_id": artifact["artifact_id"],
                    "content_sha256": artifact["content_sha256"],
                },
                "evidence": evidence,
                "interpretations": interpretations,
                "opportunity": opportunity,
                "selection": result.get("selection"),
            }
        except Exception as exc:
            error_code = _SAFE_ERROR_RE.sub(
                "_", f"{type(exc).__name__}:{stage}".lower()
            ).strip("_")[:120]
            self.store.append_event(
                event_type="source_intelligence.failed",
                aggregate_type="source",
                aggregate_id=source_id,
                actor_type="source_intelligence_orchestrator",
                payload={"error_code": error_code, "failed_component": stage},
                provenance={"pipeline_version": "source_content_intelligence/v1"},
                idempotency_key=(
                    f"source-intelligence-failed:{idempotency_key}:"
                    f"{hashlib.sha256(error_code.encode('utf-8')).hexdigest()[:16]}"
                ),
            )
            raise

    async def process_source_deterministically(
        self,
        *,
        source_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.process_source(
            source_id=source_id,
            idempotency_key=idempotency_key,
            lens_definitions=deterministic_exploratory_lenses(),
            synthesizer=deterministic_exploratory_synthesizer,
        )

    async def process_pending_deterministically(
        self,
        *,
        batch_id: str,
        limit: int = 25,
    ) -> dict[str, Any]:
        batch_id = _clean(batch_id)
        if not batch_id:
            raise ValueError("source intelligence batch id is required")
        if not 1 <= limit <= 100:
            raise ValueError("source intelligence batch limit must be between one and one hundred")
        event_key = f"source-intelligence-batch:{batch_id}"
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM system_events WHERE idempotency_key=?", (event_key,)
            ).fetchone()
            if existing:
                payload = json.loads(existing["payload_json"])
                return {
                    "schema_version": "source_content_intelligence_batch/v1",
                    **payload,
                    "event_id": existing["event_id"],
                    "replayed": True,
                }
            rows = connection.execute(
                """SELECT s.source_id,s.raw_artifact_id,s.transcript_artifact_id,
                    COALESCE(t.content_sha256,r.content_sha256) AS selected_artifact_sha256
                FROM sources s
                LEFT JOIN artifacts t ON t.artifact_id=s.transcript_artifact_id
                LEFT JOIN artifacts r ON r.artifact_id=s.raw_artifact_id
                WHERE s.admissibility_state='admissible'
                  AND s.merged_into_source_id IS NULL
                  AND s.rights_state IN ('permitted','owner_controlled')
                  AND COALESCE(s.transcript_artifact_id,s.raw_artifact_id) IS NOT NULL
                  AND EXISTS(
                      SELECT 1 FROM discovery_events d
                      WHERE d.source_id=s.source_id AND d.relevance_state='qualified'
                  )
                  AND NOT EXISTS(
                      SELECT 1 FROM opportunity_sources os WHERE os.source_id=s.source_id
                  )
                ORDER BY s.captured_at,s.source_id LIMIT ?""",
                (limit,),
            ).fetchall()
        completed: list[dict[str, str]] = []
        failures: list[dict[str, str]] = []
        for row in rows:
            source_id = row["source_id"]
            run_key = (
                f"deterministic-v1:{source_id}:{row['selected_artifact_sha256']}"
            )
            try:
                result = await self.process_source_deterministically(
                    source_id=source_id,
                    idempotency_key=run_key,
                )
                completed.append(
                    {
                        "source_id": source_id,
                        "opportunity_id": result["opportunity"]["opportunity_id"],
                    }
                )
            except Exception as exc:
                failures.append(
                    {
                        "source_id": source_id,
                        "error_code": _SAFE_ERROR_RE.sub(
                            "_", type(exc).__name__.lower()
                        ).strip("_")[:80],
                    }
                )
        status = "degraded" if failures else "complete"
        disposition = "healthy_no_change" if not rows else "processed"
        payload = {
            "batch_id": batch_id,
            "status": status,
            "disposition": disposition,
            "candidate_count": len(rows),
            "completed": completed,
            "failures": failures,
        }
        event = self.store.append_event(
            event_type=(
                "source_intelligence.batch_degraded"
                if failures
                else "source_intelligence.batch_no_change"
                if not rows
                else "source_intelligence.batch_completed"
            ),
            aggregate_type="source_intelligence_batch",
            aggregate_id=batch_id,
            actor_type="source_intelligence_orchestrator",
            payload=payload,
            provenance={"pipeline_version": "source_content_intelligence/v1"},
            idempotency_key=event_key,
        )
        return {
            "schema_version": "source_content_intelligence_batch/v1",
            **payload,
            "event_id": event["event_id"],
            "replayed": False,
        }

    def select_portfolio(
        self,
        *,
        portfolio_cycle_id: str,
        development_slots: int = 3,
        history_window: int = 22,
    ) -> dict[str, Any]:
        existing = self.portfolio.selection_for_cycle(portfolio_cycle_id)
        if existing is not None:
            return existing
        with self.store.connection() as connection:
            candidates = [
                row["opportunity_id"]
                for row in connection.execute(
                    """SELECT opportunity_id FROM content_opportunities
                    WHERE status IN ('qualified','backlog','selected','drafting')
                      AND owner_requested=0
                      AND truth_state='pass'
                      AND safety_state IN ('pass','owner_review_required')
                      AND attribution_state IN ('pass','required')
                    ORDER BY created_at,opportunity_id"""
                )
            ]
        if candidates:
            return self.portfolio.select(
                portfolio_cycle_id=portfolio_cycle_id,
                opportunity_ids=candidates,
                development_slots=development_slots,
                history_window=history_window,
            )
        event = self.store.append_event(
            event_type="content_portfolio.no_change",
            aggregate_type="portfolio_cycle",
            aggregate_id=portfolio_cycle_id,
            actor_type="portfolio_policy",
            payload={"candidate_count": 0, "disposition": "healthy_no_change"},
            provenance={"policy_version": "rolling_40_40_20_and_9_1_1/v1"},
            idempotency_key=f"content-portfolio-no-change:{portfolio_cycle_id}",
        )
        return {
            "schema_version": "content_portfolio_selection/v1",
            "portfolio_cycle_id": portfolio_cycle_id,
            "selected_opportunity_ids": [],
            "selections": [],
            "warnings": [],
            "disposition": "healthy_no_change",
            "event_id": event["event_id"],
        }

    def _load_qualified_source(
        self, source_id: str
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        with self.store.connection() as connection:
            source_row = connection.execute(
                "SELECT * FROM sources WHERE source_id=?", (source_id,)
            ).fetchone()
            if not source_row:
                raise ValueError("unknown source")
            source = dict(source_row)
            if source["merged_into_source_id"]:
                raise ValueError("source alias must be resolved to its canonical source")
            qualified = connection.execute(
                """SELECT EXISTS(
                    SELECT 1 FROM discovery_events
                    WHERE source_id=? AND relevance_state='qualified'
                )""",
                (source_id,),
            ).fetchone()[0]
            if (
                not qualified
                or source["admissibility_state"] != "admissible"
                or source["rights_state"] not in {"permitted", "owner_controlled"}
            ):
                raise ValueError("source has not passed relevance, admissibility, and rights gates")
            artifact_id = source["transcript_artifact_id"] or source["raw_artifact_id"]
            if not artifact_id:
                raise ValueError("qualified source has no captured artifact")
            artifact_row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
            ).fetchone()
            if not artifact_row:
                raise ValueError("captured source artifact is missing from the catalog")
            artifact = dict(artifact_row)
        body = self.artifact_store.read_text(artifact["logical_ref"])
        if _sha256_text(body) != artifact["content_sha256"]:
            raise ValueError("captured source artifact hash mismatch")
        return source, artifact, body

    def _lens_forbidden_mutation_fingerprint(self) -> str:
        snapshot: dict[str, list[dict[str, Any]]] = {}
        with self.store.connection() as connection:
            available = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            for table in _LENS_FORBIDDEN_MUTATION_TABLES:
                if table in available:
                    snapshot[table] = [
                        dict(row)
                        for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
                    ]
        return hashlib.sha256(_canonical_json(snapshot).encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_evidence_refs(
        *,
        body: str,
        artifact: Mapping[str, Any],
        evidence_refs: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise ValueError("authoritative extractor returned no source-bound references")
        normalized: list[dict[str, Any]] = []
        for raw_ref in evidence_refs:
            if not isinstance(raw_ref, Mapping):
                raise ValueError("evidence reference must be an object")
            ref = dict(raw_ref)
            kind = _clean(ref.get("kind"))
            if not kind:
                raise ValueError("evidence reference kind is required")
            ref["kind"] = kind
            has_start = "start" in ref
            has_end = "end" in ref
            if has_start != has_end:
                raise ValueError("evidence spans require both start and end")
            if has_start:
                start = ref["start"]
                end = ref["end"]
                if (
                    isinstance(start, bool)
                    or isinstance(end, bool)
                    or not isinstance(start, int)
                    or not isinstance(end, int)
                    or start < 0
                    or end <= start
                    or end > len(body)
                ):
                    raise ValueError("evidence span is outside the captured source")
                exact_text = body[start:end]
                supplied_excerpt = ref.pop("excerpt", None)
                if supplied_excerpt is not None and str(supplied_excerpt) != exact_text:
                    raise ValueError("evidence excerpt does not match the captured source span")
                ref["quote_sha256"] = _sha256_text(exact_text)
            ref["artifact_id"] = artifact["artifact_id"]
            ref["artifact_sha256"] = artifact["content_sha256"]
            normalized.append(ref)
        encoded = _canonical_json(normalized).encode("utf-8")
        if len(encoded) > 128 * 1024:
            raise ValueError("evidence reference packet exceeds the structured storage limit")
        return normalized

    @staticmethod
    def _confidence(value: Any) -> float | None:
        if value is None:
            return None
        try:
            confidence = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence must be numeric") from exc
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        return confidence
