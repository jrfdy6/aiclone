from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

from app.services.content_lifecycle_service import ContentLifecycleService
from app.services.content_portfolio_selection_service import (
    INTENT_TARGETS,
    PILLAR_TARGETS,
    normalize_portfolio_pillar,
)
from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


INTERPRETATION_PROVENANCE_KINDS = frozenset(
    {"independent_agent", "deterministic_policy", "synthesized_lens"}
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


class SourceEvidenceService:
    """The sole structured evidence writer; extraction execution remains an adapter concern."""

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store
        self.store.migrate()

    def record(self, *, source_id: str, extractor_name: str, extractor_version: str, evidence_refs: list[Mapping[str, Any]], confidence: float | None, idempotency_key: str, artifact_id: str | None = None) -> dict[str, Any]:
        source_id = _clean(source_id)
        extractor_name = _clean(extractor_name)
        extractor_version = _clean(extractor_version)
        idempotency_key = _clean(idempotency_key)
        if not source_id or not extractor_name or not extractor_version or not idempotency_key:
            raise ValueError("evidence source, extractor identity, version, and idempotency key are required")
        if confidence is not None and not 0 <= confidence <= 1:
            raise ValueError("evidence confidence must be between zero and one")
        if not evidence_refs:
            raise ValueError("evidence requires at least one source-bound reference")
        if not artifact_id:
            raise ValueError("authoritative evidence requires a captured source artifact")
        normalized_refs = [dict(item) for item in evidence_refs]
        if any(not _clean(item.get("kind")) for item in normalized_refs):
            raise ValueError("every evidence reference requires a kind")
        evidence_refs_json = _canonical_json(normalized_refs)
        evidence_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:evidence:{idempotency_key}"))
        now = _utcnow()
        with self.store.connection() as connection:
            source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
            if not source:
                raise ValueError("unknown source")
            if source["merged_into_source_id"]:
                raise ValueError("evidence must bind the active canonical source")
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
            if artifact_id not in {source["raw_artifact_id"], source["transcript_artifact_id"]}:
                raise ValueError("evidence artifact is not the canonical captured artifact for this source")
            artifact = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
            ).fetchone()
            if not artifact:
                raise ValueError("unknown evidence artifact")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO evidence_records(evidence_id,source_id,extractor_name,extractor_version,artifact_id,evidence_refs_json,confidence,created_at,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING",
                    (evidence_id, source_id, extractor_name, extractor_version, artifact_id, evidence_refs_json, confidence, now, idempotency_key),
                )
                row = connection.execute("SELECT * FROM evidence_records WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if not row or any(
                    row[key] != value
                    for key, value in {
                        "source_id": source_id,
                        "extractor_name": extractor_name,
                        "extractor_version": extractor_version,
                        "artifact_id": artifact_id,
                        "evidence_refs_json": evidence_refs_json,
                        "confidence": confidence,
                    }.items()
                ):
                    raise ValueError("evidence idempotency conflict")
                self._event(
                    connection,
                    "source.evidence_extracted",
                    "evidence",
                    row["evidence_id"],
                    {
                        "artifact_id": artifact_id,
                        "confidence": confidence,
                        "evidence_reference_count": len(normalized_refs),
                        "extractor_name": extractor_name,
                        "extractor_version": extractor_version,
                        "source_id": source_id,
                    },
                    f"evidence:{idempotency_key}",
                    actor_type="evidence_extractor",
                    provenance={"execution_kind": "authoritative_extraction"},
                    artifact_refs=[artifact_id],
                )
                connection.execute("COMMIT")
                return self._response(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _response(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["evidence_refs"] = json.loads(result.pop("evidence_refs_json"))
        return result

    @staticmethod
    def _event(
        connection: Any,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        key: str,
        *,
        actor_type: str,
        provenance: Mapping[str, Any],
        artifact_refs: list[str] | None = None,
    ) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{key}"))
        payload_json = _canonical_json(dict(payload))
        provenance_json = _canonical_json(dict(provenance))
        artifact_refs_json = _canonical_json(artifact_refs or [])
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                payload_json,provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                _utcnow(),
                actor_type,
                payload_json,
                provenance_json,
                artifact_refs_json,
                key,
            ),
        )
        row = connection.execute(
            "SELECT * FROM system_events WHERE idempotency_key=?", (key,)
        ).fetchone()
        if not row or any(
            row[field] != value
            for field, value in {
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "actor_type": actor_type,
                "payload_json": payload_json,
                "provenance_json": provenance_json,
                "artifact_refs_json": artifact_refs_json,
            }.items()
        ):
            raise ValueError("system event idempotency conflict")


class InterpretationLensService:
    """Versioned readings only: no downstream mutation methods are exposed."""

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store
        self.store.migrate()

    def record_reading(
        self,
        *,
        evidence_id: str,
        lens_name: str,
        lens_version: str,
        reading: Mapping[str, Any],
        confidence: float | None,
        idempotency_key: str,
        provenance_kind: str = "synthesized_lens",
    ) -> dict[str, Any]:
        evidence_id = _clean(evidence_id)
        lens_name = _clean(lens_name)
        lens_version = _clean(lens_version)
        idempotency_key = _clean(idempotency_key)
        if not evidence_id or not lens_name or not lens_version or not idempotency_key:
            raise ValueError("interpretation evidence, lens identity, version, and idempotency key are required")
        if confidence is not None and not 0 <= confidence <= 1:
            raise ValueError("interpretation confidence must be between zero and one")
        if provenance_kind not in INTERPRETATION_PROVENANCE_KINDS:
            raise ValueError("invalid interpretation provenance kind")
        normalized_reading = dict(reading)
        if not normalized_reading:
            raise ValueError("interpretation reading cannot be empty")
        normalized_reading["_provenance"] = {
            "kind": provenance_kind,
            "schema_version": "interpretation_provenance/v1",
        }
        reading_json = _canonical_json(normalized_reading)
        interpretation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:interpretation:{idempotency_key}"))
        with self.store.connection() as connection:
            if not connection.execute("SELECT 1 FROM evidence_records WHERE evidence_id=?", (evidence_id,)).fetchone():
                raise ValueError("unknown evidence")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO interpretations(
                        interpretation_id,evidence_id,lens_name,lens_version,reading_json,
                        confidence,created_at,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        interpretation_id,
                        evidence_id,
                        lens_name,
                        lens_version,
                        reading_json,
                        confidence,
                        _utcnow(),
                        idempotency_key,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM interpretations WHERE idempotency_key=?", (idempotency_key,)
                ).fetchone()
                if not row or any(
                    row[key] != value
                    for key, value in {
                        "evidence_id": evidence_id,
                        "lens_name": lens_name,
                        "lens_version": lens_version,
                        "reading_json": reading_json,
                        "confidence": confidence,
                    }.items()
                ):
                    raise ValueError("interpretation idempotency conflict")
                SourceEvidenceService._event(
                    connection,
                    "source.interpretation_recorded",
                    "interpretation",
                    row["interpretation_id"],
                    {
                        "confidence": confidence,
                        "evidence_id": evidence_id,
                        "lens_name": lens_name,
                        "lens_version": lens_version,
                        "provenance_kind": provenance_kind,
                    },
                    f"interpretation:{idempotency_key}",
                    actor_type="interpretation_lens",
                    provenance={"assessment_kind": provenance_kind},
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            result = dict(row)
            result["reading"] = json.loads(result.pop("reading_json"))
            return result


class InterpretationSynthesisRouter:
    """Only this boundary may route readings into a ContentOpportunity."""

    def __init__(
        self,
        store: IntegratedSystemStore,
        content: ContentLifecycleService,
        *,
        belief_registry_path: Path | None = None,
    ) -> None:
        self.store = store
        self.content = content
        self.belief_registry_path = belief_registry_path or (
            Path(__file__).resolve().parents[3]
            / "knowledge"
            / "persona"
            / "feeze"
            / "identity"
            / "canonical_beliefs.json"
        )

    def _canonical_beliefs(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self.belief_registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("canonical belief registry is unavailable") from exc
        persona_id = _clean(payload.get("persona_id"))
        expected_persona_id = _clean(os.getenv("AI_CLONE_CANONICAL_PERSONA_ID"))
        if (
            payload.get("schema_version") != "canonical_belief_registry/v1"
            or not persona_id
            or len(persona_id) > 128
            or (expected_persona_id and persona_id != expected_persona_id)
        ):
            raise ValueError("canonical belief registry contract is invalid")
        beliefs = {
            str(item.get("belief_ref") or "").strip(): dict(item)
            for item in payload.get("beliefs") or []
            if isinstance(item, dict)
            and str(item.get("belief_ref") or "").startswith("belief:")
            and str(item.get("claim") or "").strip()
            and str(item.get("source") or "").strip()
        }
        if not beliefs:
            raise ValueError("canonical belief registry contains no governed beliefs")
        return beliefs

    def create_opportunity(
        self,
        *,
        evidence_id: str,
        interpretation_ids: list[str],
        thesis: str,
        canonical_belief_refs: list[str],
        truth_state: str,
        attribution_state: str,
        safety_state: str,
        idempotency_key: str,
        owner_requested: bool = False,
        exploratory_conflict: bool = False,
        canonical_pillar: str | None = None,
        intent: str | None = None,
        portfolio_score: float | None = None,
    ) -> dict[str, Any]:
        evidence_id = _clean(evidence_id)
        thesis = _clean(thesis)
        idempotency_key = _clean(idempotency_key)
        interpretation_ids = list(
            dict.fromkeys(_clean(value) for value in interpretation_ids if _clean(value))
        )
        canonical_belief_refs = list(
            dict.fromkeys(_clean(value) for value in canonical_belief_refs if _clean(value))
        )
        if not evidence_id or not thesis or not idempotency_key:
            raise ValueError("synthesis evidence, thesis, and idempotency key are required")
        if truth_state != "pass" or safety_state not in {"pass", "owner_review_required"} or attribution_state not in {"pass", "required"}:
            raise ValueError("synthesis cannot route through failed truth, safety, or attribution gates")
        if not canonical_belief_refs and not exploratory_conflict:
            raise ValueError("content position requires canonical belief alignment or explicit exploratory conflict")
        canonical_pillar = (
            normalize_portfolio_pillar(canonical_pillar)
            if canonical_pillar is not None
            else None
        )
        classification_values = (canonical_pillar, intent, portfolio_score)
        if any(value is not None for value in classification_values):
            if canonical_pillar not in PILLAR_TARGETS:
                raise ValueError("invalid canonical portfolio pillar")
            if intent not in INTENT_TARGETS:
                raise ValueError("invalid portfolio intent")
            if portfolio_score is None or not 0 <= float(portfolio_score) <= 1:
                raise ValueError("portfolio score must be between zero and one")
        registry = self._canonical_beliefs()
        unknown_beliefs = sorted(set(canonical_belief_refs) - set(registry))
        if unknown_beliefs:
            raise ValueError(f"unknown canonical belief references: {', '.join(unknown_beliefs)}")
        with self.store.connection() as connection:
            evidence = connection.execute("SELECT * FROM evidence_records WHERE evidence_id=?", (evidence_id,)).fetchone()
            if not evidence:
                raise ValueError("unknown evidence")
            count = connection.execute(f"SELECT COUNT(*) FROM interpretations WHERE evidence_id=? AND interpretation_id IN ({','.join('?' for _ in interpretation_ids)})", (evidence_id, *interpretation_ids)).fetchone()[0] if interpretation_ids else 0
            if count != len(interpretation_ids) or not interpretation_ids:
                raise ValueError("synthesis requires source-bound interpretations")
        belief_evidence = [
            {"belief_ref": ref, "claim": registry[ref]["claim"], "source": registry[ref]["source"]}
            for ref in canonical_belief_refs
        ]
        classification = (
            {
                "canonical_pillar": canonical_pillar,
                "intent": intent,
                "portfolio_score": float(portfolio_score),
            }
            if canonical_pillar is not None
            else {}
        )
        synthesis_record = {
            "schema_version": "source_synthesis/v1",
            "idempotency_key": idempotency_key,
            "evidence_id": evidence_id,
            "interpretation_ids": interpretation_ids,
            "canonical_belief_refs": canonical_belief_refs,
            "canonical_belief_evidence": belief_evidence,
            "exploratory_conflict": bool(exploratory_conflict),
            "truth_state": truth_state,
            "safety_state": safety_state,
            "attribution_state": attribution_state,
            **classification,
        }
        result = self.content.create_or_reuse_opportunity(
            thesis=thesis,
            idempotency_key=idempotency_key,
            source_ids=[evidence["source_id"]],
            owner_requested=owner_requested,
            metadata={
                "evidence_id": evidence_id,
                "interpretation_ids": interpretation_ids,
                "canonical_belief_refs": canonical_belief_refs,
                "canonical_belief_evidence": belief_evidence,
                "exploratory_conflict": exploratory_conflict,
                "syntheses": [synthesis_record],
                **classification,
            },
        )
        opportunity_id = result["opportunity"]["opportunity_id"]
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                opportunity = connection.execute(
                    "SELECT * FROM content_opportunities WHERE opportunity_id=?", (opportunity_id,)
                ).fetchone()
                if not opportunity:
                    raise ValueError("routed content opportunity disappeared")
                if (
                    opportunity["status"] == "blocked"
                    or opportunity["truth_state"] == "blocked"
                    or opportunity["safety_state"] == "blocked"
                    or opportunity["attribution_state"] == "blocked"
                ):
                    raise ValueError("synthesis cannot clear an existing content blocker")
                metadata = json.loads(opportunity["metadata_json"])
                syntheses = metadata.get("syntheses")
                if not isinstance(syntheses, list):
                    syntheses = []
                existing_synthesis = next(
                    (
                        item
                        for item in syntheses
                        if isinstance(item, dict)
                        and item.get("idempotency_key") == idempotency_key
                    ),
                    None,
                )
                if existing_synthesis is not None and existing_synthesis != synthesis_record:
                    raise ValueError("synthesis idempotency conflict")
                if existing_synthesis is None:
                    syntheses.append(synthesis_record)
                for field, value in classification.items():
                    existing_value = metadata.get(field)
                    if existing_value is not None and existing_value != value:
                        raise ValueError("equivalent opportunity has conflicting portfolio classification")
                    metadata[field] = value
                metadata["syntheses"] = syntheses
                metadata["canonical_belief_refs"] = sorted(
                    {
                        _clean(value)
                        for item in syntheses
                        if isinstance(item, dict)
                        for value in item.get("canonical_belief_refs", [])
                        if _clean(value)
                    }
                )
                metadata["canonical_belief_evidence"] = [
                    {
                        "belief_ref": ref,
                        "claim": registry[ref]["claim"],
                        "source": registry[ref]["source"],
                    }
                    for ref in metadata["canonical_belief_refs"]
                ]
                effective_safety = (
                    "owner_review_required"
                    if "owner_review_required" in {opportunity["safety_state"], safety_state}
                    else "pass"
                )
                effective_attribution = (
                    "required"
                    if "required" in {opportunity["attribution_state"], attribution_state}
                    else "pass"
                )
                connection.execute(
                    """UPDATE content_opportunities
                    SET truth_state='pass',safety_state=?,attribution_state=?,metadata_json=?,updated_at=?
                    WHERE opportunity_id=?""",
                    (
                        effective_safety,
                        effective_attribution,
                        _canonical_json(metadata),
                        _utcnow(),
                        opportunity_id,
                    ),
                )
                SourceEvidenceService._event(
                    connection,
                    "source.synthesis_routed",
                    "content_opportunity",
                    opportunity_id,
                    {
                        "attribution_state": effective_attribution,
                        "canonical_belief_refs": canonical_belief_refs,
                        "evidence_id": evidence_id,
                        "exploratory_conflict": bool(exploratory_conflict),
                        "interpretation_ids": interpretation_ids,
                        "owner_requested": bool(owner_requested),
                        "safety_state": effective_safety,
                    },
                    f"source-synthesis:{idempotency_key}",
                    actor_type="synthesis_router",
                    provenance={"router_version": "interpretation_synthesis_router/v2"},
                    artifact_refs=[evidence["artifact_id"]] if evidence["artifact_id"] else [],
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        with self.store.connection() as connection:
            result["opportunity"] = dict(
                connection.execute(
                    "SELECT * FROM content_opportunities WHERE opportunity_id=?", (opportunity_id,)
                ).fetchone()
            )
        return result
