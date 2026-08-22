from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Callable, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


AUTOMATIC_RULE = "three_owner_approved_published_posts_two_independent_contexts/v1"
GOVERNED_WRITER_ID = "governed_persona_bundle_writer/v1"
_CANDIDATE_KINDS = frozenset({"factual_continuity", "reversible_pattern", "identity_claim"})


class PersonaLearningConflict(ValueError):
    pass


class PersonaGovernanceBlocked(PersonaLearningConflict):
    pass


GovernedPersonaWriter = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class PersonaLearningService:
    def __init__(
        self,
        store: IntegratedSystemStore,
        *,
        canon_writer: GovernedPersonaWriter | None = None,
    ) -> None:
        self.store = store
        self.canon_writer = canon_writer
        self.store.migrate()

    def create_candidate(
        self,
        *,
        candidate_kind: str,
        claim: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if candidate_kind not in _CANDIDATE_KINDS:
            raise ValueError("unsupported persona candidate kind")
        normalized_claim = dict(claim)
        if not normalized_claim:
            raise ValueError("persona candidate requires a claim")
        claim_json = _canonical_json(normalized_claim)
        candidate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:persona-candidate:{idempotency_key}"))
        now = _utcnow()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO persona_candidates(
                        persona_candidate_id,candidate_kind,claim_json,status,created_at,updated_at,idempotency_key
                    ) VALUES (?,?,?,'pending',?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (candidate_id, candidate_kind, claim_json, now, now, idempotency_key),
                )
                row = connection.execute(
                    "SELECT * FROM persona_candidates WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if not row or row["candidate_kind"] != candidate_kind or row["claim_json"] != claim_json:
                    raise PersonaLearningConflict("persona candidate idempotency conflict")
                self._event(
                    connection,
                    event_type="persona.candidate_created",
                    candidate_id=row["persona_candidate_id"],
                    payload={
                        "candidate_kind": candidate_kind,
                        "claim_sha256": hashlib.sha256(claim_json.encode("utf-8")).hexdigest(),
                    },
                    event_key=f"persona-candidate:{idempotency_key}",
                    actor_type="persona_learning",
                )
                connection.execute("COMMIT")
                return self._candidate_response(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def attach_evidence(
        self,
        *,
        candidate_id: str,
        context_key: str,
        post_id: str,
        revision_id: str,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        """Attach evidence with approval/publication derived from canonical events.

        Callers cannot attest their own lifecycle booleans.  The exact revision,
        source lineage, owner approval, and publication confirmation are resolved
        from the canonical content store at mutation time and again at evaluation.
        """

        context_key = " ".join(context_key.split()).strip()
        if not context_key:
            raise ValueError("persona evidence requires a context key")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if not connection.execute(
                    "SELECT 1 FROM persona_candidates WHERE persona_candidate_id=?",
                    (candidate_id,),
                ).fetchone():
                    raise ValueError("unknown persona candidate")
                revision = connection.execute(
                    """SELECT r.*,p.opportunity_id,p.status AS post_status
                    FROM content_revisions r JOIN canonical_posts p ON p.post_id=r.post_id
                    WHERE r.revision_id=? AND r.post_id=?""",
                    (revision_id, post_id),
                ).fetchone()
                if not revision:
                    raise ValueError("candidate evidence must reference a revision belonging to the post")
                linked_sources = {
                    row["source_id"]
                    for row in connection.execute(
                        "SELECT source_id FROM opportunity_sources WHERE opportunity_id=?",
                        (revision["opportunity_id"],),
                    )
                }
                if source_id is None:
                    if len(linked_sources) != 1:
                        raise ValueError("persona evidence must identify one source when the opportunity has multiple sources")
                    source_id = next(iter(linked_sources))
                if source_id not in linked_sources:
                    raise PersonaLearningConflict("persona evidence source is outside the canonical post lineage")
                binding = json.loads(revision["evidence_binding_json"])
                bound_sources = set(binding.get("source_ids") or [])
                single_bound_source = str(binding.get("source_id") or "").strip()
                if single_bound_source:
                    bound_sources.add(single_bound_source)
                if bound_sources and source_id not in bound_sources:
                    raise PersonaLearningConflict("persona evidence source is absent from the exact revision binding")

                owner_approved, publication_confirmed = self._lifecycle_flags(
                    connection,
                    post_id=post_id,
                    revision_id=revision_id,
                )
                connection.execute(
                    """INSERT INTO persona_candidate_evidence(
                        persona_candidate_id,post_id,revision_id,source_id,context_key,
                        owner_approved,publication_confirmed
                    ) VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(persona_candidate_id,context_key) DO NOTHING""",
                    (
                        candidate_id,
                        post_id,
                        revision_id,
                        source_id,
                        context_key,
                        int(owner_approved),
                        int(publication_confirmed),
                    ),
                )
                row = connection.execute(
                    """SELECT * FROM persona_candidate_evidence
                    WHERE persona_candidate_id=? AND context_key=?""",
                    (candidate_id, context_key),
                ).fetchone()
                if (
                    not row
                    or row["post_id"] != post_id
                    or row["revision_id"] != revision_id
                    or row["source_id"] != source_id
                ):
                    raise PersonaLearningConflict("persona evidence context is immutable and already bound elsewhere")
                # Refresh only lifecycle facts derived from canonical events.  The
                # source/post/revision evidence identity remains immutable.
                connection.execute(
                    """UPDATE persona_candidate_evidence
                    SET owner_approved=?,publication_confirmed=?
                    WHERE persona_candidate_id=? AND context_key=?""",
                    (int(owner_approved), int(publication_confirmed), candidate_id, context_key),
                )
                self._event(
                    connection,
                    event_type="persona.evidence_attached",
                    candidate_id=candidate_id,
                    payload={
                        "post_id": post_id,
                        "revision_id": revision_id,
                        "source_id": source_id,
                        "context_key": context_key,
                        "owner_approved": owner_approved,
                        "publication_confirmed": publication_confirmed,
                        "lifecycle_authority": "canonical_content_learning_events/v1",
                    },
                    event_key=(
                        f"persona-evidence:{candidate_id}:{context_key}:"
                        f"{int(owner_approved)}:{int(publication_confirmed)}"
                    ),
                    actor_type="persona_learning",
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return self.evaluate(candidate_id)

    def evaluate(self, candidate_id: str) -> dict[str, Any]:
        with self.store.connection() as connection:
            candidate = connection.execute(
                "SELECT * FROM persona_candidates WHERE persona_candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                raise ValueError("unknown persona candidate")
            rows = connection.execute(
                "SELECT * FROM persona_candidate_evidence WHERE persona_candidate_id=?",
                (candidate_id,),
            ).fetchall()
            qualifying: list[Any] = []
            for row in rows:
                owner_approved, publication_confirmed = self._lifecycle_flags(
                    connection,
                    post_id=row["post_id"],
                    revision_id=row["revision_id"],
                )
                if owner_approved and publication_confirmed:
                    qualifying.append(row)
        independent = {row["source_id"] or f"context:{row['context_key']}" for row in qualifying}
        approved_posts = {row["post_id"] for row in qualifying}
        return {
            "persona_candidate_id": candidate_id,
            "candidate_kind": candidate["candidate_kind"],
            "status": candidate["status"],
            "qualifying_post_count": len(approved_posts),
            "independent_context_count": len(independent),
            "automatic_promotion_eligible": (
                candidate["candidate_kind"] == "reversible_pattern"
                and candidate["status"] in {"pending", "blocked"}
                and len(approved_posts) >= 3
                and len(independent) >= 2
            ),
        }

    def promote_if_eligible(
        self,
        *,
        candidate_id: str,
        canon_version: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        canon_version = canon_version.strip()
        if not canon_version:
            raise ValueError("persona promotion requires a canon version")
        with self.store.connection() as connection:
            existing_promotion = connection.execute(
                "SELECT * FROM persona_promotions WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing_promotion:
                if (
                    existing_promotion["persona_candidate_id"] != candidate_id
                    or existing_promotion["canon_version"] != canon_version
                ):
                    raise PersonaLearningConflict("persona promotion idempotency conflict")
                result = dict(existing_promotion)
                result["promotion_applied"] = existing_promotion["reversed_at"] is None
                return result
        eligibility = self.evaluate(candidate_id)
        if not eligibility["automatic_promotion_eligible"]:
            raise ValueError("persona candidate does not satisfy the approved automatic-promotion rule")
        with self.store.connection() as connection:
            candidate = connection.execute(
                "SELECT * FROM persona_candidates WHERE persona_candidate_id=?",
                (candidate_id,),
            ).fetchone()
            evidence = [
                dict(row)
                for row in connection.execute(
                    """SELECT * FROM persona_candidate_evidence
                    WHERE persona_candidate_id=? ORDER BY context_key""",
                    (candidate_id,),
                )
            ]
            for item in evidence:
                owner_approved, publication_confirmed = self._lifecycle_flags(
                    connection,
                    post_id=item["post_id"],
                    revision_id=item["revision_id"],
                )
                item["owner_approved"] = int(owner_approved)
                item["publication_confirmed"] = int(publication_confirmed)
                item["lifecycle_authority"] = "canonical_content_learning_events/v1"
        if self.canon_writer is None:
            now = _utcnow()
            with self.store.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        "UPDATE persona_candidates SET status='blocked',updated_at=? WHERE persona_candidate_id=?",
                        (now, candidate_id),
                    )
                    self._event(
                        connection,
                        event_type="persona.promotion_blocked",
                        candidate_id=candidate_id,
                        payload={
                            "promotion_rule": AUTOMATIC_RULE,
                            "canon_version": canon_version,
                            "reason_code": "governed_canon_writer_unavailable",
                        },
                        event_key=f"persona-promotion-blocked:{idempotency_key}",
                        actor_type="persona_learning",
                    )
                    connection.execute("COMMIT")
                except Exception:
                    connection.execute("ROLLBACK")
                    raise
            return {
                "persona_candidate_id": candidate_id,
                "status": "blocked",
                "promotion_applied": False,
                "reason_code": "governed_canon_writer_unavailable",
                "promotion_rule": AUTOMATIC_RULE,
                "canon_version": canon_version,
            }

        request = {
            "schema_version": "persona_canon_write_request/v1",
            "action": "promote",
            "writer_id": GOVERNED_WRITER_ID,
            "persona_candidate_id": candidate_id,
            "candidate_kind": candidate["candidate_kind"],
            "claim": json.loads(candidate["claim_json"]),
            "canon_version": canon_version,
            "promotion_rule": AUTOMATIC_RULE,
            "idempotency_key": idempotency_key,
            "eligibility": eligibility,
            "evidence": evidence,
        }
        try:
            writer_receipt = self._validate_writer_receipt(
                self.canon_writer(request),
                action="promote",
                candidate_id=candidate_id,
                canon_version=canon_version,
            )
        except Exception as exc:
            with self.store.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        "UPDATE persona_candidates SET status='blocked',updated_at=? WHERE persona_candidate_id=?",
                        (_utcnow(), candidate_id),
                    )
                    self._event(
                        connection,
                        event_type="persona.promotion_blocked",
                        candidate_id=candidate_id,
                        payload={
                            "promotion_rule": AUTOMATIC_RULE,
                            "canon_version": canon_version,
                            "reason_code": "governed_canon_writer_failed",
                            "error_class": type(exc).__name__,
                        },
                        event_key=f"persona-promotion-writer-blocked:{idempotency_key}",
                        actor_type="persona_learning",
                    )
                    connection.execute("COMMIT")
                except Exception:
                    connection.execute("ROLLBACK")
                    raise
            raise PersonaGovernanceBlocked("governed persona writer failed; candidate remains blocked") from exc

        promotion_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:persona-promotion:{idempotency_key}"))
        now = _utcnow()
        evidence_receipt = {
            "eligibility": eligibility,
            "evidence": evidence,
            "writer_receipt": writer_receipt,
        }
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO persona_promotions(
                        promotion_id,persona_candidate_id,canon_version,promotion_rule,
                        evidence_receipt_json,promoted_at,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        promotion_id,
                        candidate_id,
                        canon_version,
                        AUTOMATIC_RULE,
                        _canonical_json(evidence_receipt),
                        now,
                        idempotency_key,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM persona_promotions WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if not row or row["persona_candidate_id"] != candidate_id or row["canon_version"] != canon_version:
                    raise PersonaLearningConflict("persona promotion idempotency conflict")
                connection.execute(
                    "UPDATE persona_candidates SET status='promoted',updated_at=? WHERE persona_candidate_id=?",
                    (now, candidate_id),
                )
                self._event(
                    connection,
                    event_type="persona.promoted",
                    candidate_id=candidate_id,
                    payload={
                        "promotion_id": row["promotion_id"],
                        "canon_version": canon_version,
                        "promotion_rule": AUTOMATIC_RULE,
                        "writer_id": GOVERNED_WRITER_ID,
                    },
                    event_key=f"persona-promotion:{idempotency_key}",
                    actor_type="governed_persona_writer",
                )
                connection.execute("COMMIT")
                result = dict(row)
                result["promotion_applied"] = True
                return result
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def reverse(
        self,
        *,
        promotion_id: str,
        reason: str,
        expected_candidate_id: str | None = None,
        expected_canon_version: str | None = None,
    ) -> dict[str, Any]:
        reason = " ".join(reason.split()).strip()
        if not reason:
            raise ValueError("persona reversal requires a reason")
        with self.store.connection() as connection:
            promotion = connection.execute(
                "SELECT * FROM persona_promotions WHERE promotion_id=?",
                (promotion_id,),
            ).fetchone()
            if not promotion:
                raise ValueError("unknown persona promotion")
            if expected_candidate_id is not None and promotion["persona_candidate_id"] != expected_candidate_id:
                raise PersonaLearningConflict("persona reversal candidate binding is stale")
            if expected_canon_version is not None and promotion["canon_version"] != expected_canon_version:
                raise PersonaLearningConflict("persona reversal canon-version binding is stale")
            if promotion["reversed_at"]:
                if promotion["reversal_reason"] != reason[:1000]:
                    raise PersonaLearningConflict("persona promotion was already reversed with a different reason")
                return {
                    "promotion_id": promotion_id,
                    "reversed_at": promotion["reversed_at"],
                    "reversal_reason": promotion["reversal_reason"],
                    "already_reversed": True,
                }
            evidence_receipt = json.loads(promotion["evidence_receipt_json"])
            original_writer_receipt = evidence_receipt.get("writer_receipt")
            if not isinstance(original_writer_receipt, dict):
                raise PersonaGovernanceBlocked(
                    "persona promotion is missing its governed writer receipt"
                )
        if self.canon_writer is None:
            raise PersonaGovernanceBlocked("governed persona writer is required to reverse canonical persona")
        writer_receipt = self._validate_writer_receipt(
            self.canon_writer(
                {
                    "schema_version": "persona_canon_write_request/v1",
                    "action": "reverse",
                    "writer_id": GOVERNED_WRITER_ID,
                    "persona_candidate_id": promotion["persona_candidate_id"],
                    "promotion_id": promotion_id,
                    "canon_version": promotion["canon_version"],
                    "reason": reason[:1000],
                    "idempotency_key": f"reverse:{promotion_id}",
                    "original_writer_receipt": original_writer_receipt,
                }
            ),
            action="reverse",
            candidate_id=promotion["persona_candidate_id"],
            canon_version=promotion["canon_version"],
            promotion_id=promotion_id,
        )
        now = _utcnow()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "UPDATE persona_promotions SET reversed_at=?,reversal_reason=? WHERE promotion_id=? AND reversed_at IS NULL",
                    (now, reason[:1000], promotion_id),
                )
                connection.execute(
                    "UPDATE persona_candidates SET status='reversed',updated_at=? WHERE persona_candidate_id=?",
                    (now, promotion["persona_candidate_id"]),
                )
                self._event(
                    connection,
                    event_type="persona.reversed",
                    candidate_id=promotion["persona_candidate_id"],
                    payload={
                        "promotion_id": promotion_id,
                        "canon_version": promotion["canon_version"],
                        "writer_id": writer_receipt["writer_id"],
                    },
                    event_key=f"persona-reversal:{promotion_id}",
                    actor_type="governed_persona_writer",
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return {
            "promotion_id": promotion_id,
            "reversed_at": now,
            "reversal_reason": reason[:1000],
            "writer_receipt": writer_receipt,
        }

    @staticmethod
    def _candidate_response(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["claim"] = json.loads(result.pop("claim_json"))
        return result

    @staticmethod
    def _lifecycle_flags(connection: Any, *, post_id: str, revision_id: str) -> tuple[bool, bool]:
        events = {
            row["event_kind"]
            for row in connection.execute(
                """SELECT event_kind FROM learning_events
                WHERE post_id=? AND revision_id=?
                AND event_kind IN ('owner_approved','publication_confirmed')""",
                (post_id, revision_id),
            )
        }
        published = bool(
            connection.execute(
                "SELECT 1 FROM canonical_posts WHERE post_id=? AND status='published' AND current_revision_id=?",
                (post_id, revision_id),
            ).fetchone()
        )
        owner_approved = "owner_approved" in events
        return owner_approved, owner_approved and "publication_confirmed" in events and published

    @staticmethod
    def _validate_writer_receipt(
        value: Mapping[str, Any],
        *,
        action: str,
        candidate_id: str,
        canon_version: str,
        promotion_id: str | None = None,
    ) -> dict[str, Any]:
        receipt = dict(value)
        if (
            receipt.get("schema_version") != "persona_canon_write_receipt/v1"
            or receipt.get("writer_id") != GOVERNED_WRITER_ID
            or receipt.get("action") != action
            or receipt.get("persona_candidate_id") != candidate_id
            or receipt.get("canon_version") != canon_version
            or receipt.get("applied") is not True
            or receipt.get("reversible") is not True
        ):
            raise PersonaGovernanceBlocked("governed persona writer returned an invalid mutation receipt")
        if action == "reverse" and receipt.get("promotion_id") != promotion_id:
            raise PersonaGovernanceBlocked("persona reversal receipt does not bind the promotion")
        artifact_refs = receipt.get("artifact_refs")
        if not isinstance(artifact_refs, list) or not artifact_refs or not all(
            isinstance(item, str) and item.strip() for item in artifact_refs
        ):
            raise PersonaGovernanceBlocked("persona writer receipt requires canonical artifact references")
        return receipt

    @staticmethod
    def _event(
        connection: Any,
        *,
        event_type: str,
        candidate_id: str,
        payload: Mapping[str, Any],
        event_key: str,
        actor_type: str,
    ) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                payload_json,provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                event_type,
                "persona_candidate",
                candidate_id,
                _utcnow(),
                actor_type,
                _canonical_json(dict(payload)),
                _canonical_json({"authority": "persona_learning_service/v1"}),
                "[]",
                event_key,
            ),
        )
