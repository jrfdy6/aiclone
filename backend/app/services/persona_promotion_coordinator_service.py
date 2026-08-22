from __future__ import annotations

from typing import Any, Mapping

from app.services.integrated_persona_canon_writer import IntegratedPersonaCanonWriter
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.persona_learning_service import AUTOMATIC_RULE, PersonaLearningService


class PersonaPromotionCoordinatorService:
    """Promote only canonically eligible reversible patterns after readiness."""

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store
        self.learning = PersonaLearningService(
            store,
            canon_writer=IntegratedPersonaCanonWriter(),
        )

    def run(self, *, cycle_id: str, readiness: Mapping[str, Any]) -> dict[str, Any]:
        readiness_policy = readiness.get("degraded_policy")
        promotion_allowed = (
            readiness.get("status") == "ready"
            and isinstance(readiness_policy, Mapping)
            and readiness_policy.get("fresh_persona_promotion_allowed") is True
        )
        if not promotion_allowed:
            return {
                "schema_version": "persona_promotion_cycle_receipt/v1",
                "cycle_id": cycle_id,
                "status": "degraded",
                "reason_code": "memory_readiness_blocks_fresh_persona_promotion",
                "eligible_count": 0,
                "promoted_count": 0,
                "blocked_count": 0,
                "results": [],
            }

        with self.store.connection() as connection:
            candidate_ids = [
                row["persona_candidate_id"]
                for row in connection.execute(
                    """SELECT persona_candidate_id FROM persona_candidates
                    WHERE candidate_kind='reversible_pattern' AND status IN ('pending','blocked')
                    ORDER BY created_at,persona_candidate_id"""
                )
            ]
        eligible = [
            candidate_id
            for candidate_id in candidate_ids
            if self.learning.evaluate(candidate_id)["automatic_promotion_eligible"]
        ]
        results: list[dict[str, Any]] = []
        for candidate_id in eligible:
            try:
                promotion = self.learning.promote_if_eligible(
                    candidate_id=candidate_id,
                    canon_version=f"automatic-v1:{candidate_id}",
                    idempotency_key=f"automatic:{AUTOMATIC_RULE}:{candidate_id}",
                )
                results.append(
                    {
                        "persona_candidate_id": candidate_id,
                        "status": "promoted" if promotion.get("promotion_applied") else "blocked",
                        "promotion_id": promotion.get("promotion_id"),
                        "reason_code": promotion.get("reason_code"),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "persona_candidate_id": candidate_id,
                        "status": "blocked",
                        "promotion_id": None,
                        "reason_code": "governed_writer_failed",
                        "error_class": type(exc).__name__,
                    }
                )
        promoted_count = sum(item["status"] == "promoted" for item in results)
        blocked_count = sum(item["status"] == "blocked" for item in results)
        return {
            "schema_version": "persona_promotion_cycle_receipt/v1",
            "cycle_id": cycle_id,
            "status": "degraded" if blocked_count else ("complete" if results else "no_change"),
            "reason_code": "governed_writer_blocked" if blocked_count else None,
            "eligible_count": len(eligible),
            "promoted_count": promoted_count,
            "blocked_count": blocked_count,
            "results": results,
        }
