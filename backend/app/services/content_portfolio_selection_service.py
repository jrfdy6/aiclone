from __future__ import annotations

from collections import Counter
import json
from typing import Any, Mapping
import uuid

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


PILLAR_TARGETS = {
    "ai_native": 0.4,
    "leadership_operator": 0.4,
    "trust_systems": 0.2,
}
LEGACY_PILLAR_ALIASES = {
    "ai_product_systems": "ai_native",
    "leadership_operations_adoption": "leadership_operator",
    "education_community_family_trust": "trust_systems",
}
INTENT_TARGETS = {"value": 9 / 11, "invitation": 1 / 11, "personal": 1 / 11}


def normalize_portfolio_pillar(value: Any) -> str:
    """Return the owner-approved editorial_mix/v1 pillar ID.

    The three legacy aliases were briefly emitted by the integrated selector during
    development. Reading them remains supported so existing local rows can be
    selected, but all new receipts and classifications use the governed IDs.
    """

    pillar = str(value or "").strip()
    return LEGACY_PILLAR_ALIASES.get(pillar, pillar)


def _classification(row: Mapping[str, Any]) -> tuple[str, str, float] | None:
    raw = row.get("metadata_json")
    metadata = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    pillar = normalize_portfolio_pillar(metadata.get("canonical_pillar"))
    intent = str(metadata.get("intent") or "").strip()
    if pillar not in PILLAR_TARGETS or intent not in INTENT_TARGETS:
        return None
    try:
        priority = max(0.0, min(1.0, float(metadata.get("portfolio_score", 0.5))))
    except (TypeError, ValueError):
        priority = 0.5
    return pillar, intent, priority


def _automatic_draft_eligible(row: Mapping[str, Any]) -> bool:
    """Keep unresolved exploratory judgment out of unattended drafting.

    A safety-pass opportunity may enter the normal portfolio. An opportunity
    that still requires owner review may enter automatically only when its
    synthesis is already bound to at least one governed canonical belief and is
    not an exploratory conflict. Unaligned or conflicting material remains
    retrievable and owner-selectable without turning a UUID tie-break into an
    owner-content decision.
    """

    safety_state = str(row.get("safety_state") or "").strip()
    if safety_state == "pass":
        return True
    if safety_state != "owner_review_required":
        return False
    raw = row.get("metadata_json")
    try:
        metadata = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    belief_refs = metadata.get("canonical_belief_refs")
    return bool(
        isinstance(belief_refs, list)
        and any(str(item or "").strip() for item in belief_refs)
        and metadata.get("exploratory_conflict") is not True
    )


def rank_portfolio_candidates(
    candidates: list[Mapping[str, Any]],
    *,
    historical_pillars: Mapping[str, int] | None = None,
    historical_intents: Mapping[str, int] | None = None,
    development_slots: int = 3,
) -> list[str]:
    """Select qualified IDs against rolling targets without manufacturing filler."""

    if development_slots not in {2, 3}:
        raise ValueError("normal portfolio development requires two or three slots")
    pillar_counts: Counter[str] = Counter()
    for pillar, count in (historical_pillars or {}).items():
        normalized = normalize_portfolio_pillar(pillar)
        if normalized in PILLAR_TARGETS:
            pillar_counts[normalized] += int(count)
    intent_counts = Counter(historical_intents or {})
    remaining = [
        dict(item)
        for item in candidates
        if not bool(item.get("owner_requested"))
        and _classification(item) is not None
    ]
    selected: list[str] = []
    for _ in range(development_slots):
        if not remaining:
            break
        projected_total = max(1, sum(pillar_counts.values()) + 1)

        def score(item: Mapping[str, Any]) -> tuple[float, float, float, float, str]:
            pillar, intent, priority = _classification(item) or ("", "", 0.0)
            pillar_deficit = PILLAR_TARGETS[pillar] * projected_total - pillar_counts[pillar]
            intent_deficit = INTENT_TARGETS[intent] * projected_total - intent_counts[intent]
            return (
                pillar_deficit + intent_deficit,
                pillar_deficit,
                intent_deficit,
                priority,
                str(item["opportunity_id"]),
            )

        winner = max(remaining, key=score)
        remaining.remove(winner)
        pillar, intent, _priority = _classification(winner) or ("", "", 0.0)
        pillar_counts[pillar] += 1
        intent_counts[intent] += 1
        selected.append(str(winner["opportunity_id"]))
    return selected


class ContentPortfolioSelectionService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store
        self.store.migrate()

    def selection_for_cycle(self, portfolio_cycle_id: str) -> dict[str, Any] | None:
        """Reconstruct an already persisted cycle without reselecting changed state."""

        with self.store.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM portfolio_selections WHERE portfolio_cycle_id=?
                ORDER BY selected_at,opportunity_id""",
                (portfolio_cycle_id,),
            ).fetchall()
            if not rows:
                return None
            event = connection.execute(
                """SELECT payload_json FROM system_events
                WHERE event_type='content_portfolio.selected' AND aggregate_id=?
                ORDER BY occurred_at DESC LIMIT 1""",
                (portfolio_cycle_id,),
            ).fetchone()
        payload: dict[str, Any] = {}
        if event:
            try:
                candidate = json.loads(event["payload_json"])
            except json.JSONDecodeError:
                candidate = {}
            if isinstance(candidate, dict):
                payload = candidate
        selections = []
        for row in rows:
            try:
                reason = json.loads(row["reason_json"])
            except json.JSONDecodeError as exc:
                raise ValueError("persisted portfolio selection reason is malformed") from exc
            if not isinstance(reason, dict):
                raise ValueError("persisted portfolio selection reason must be an object")
            selections.append({**dict(row), "reason": reason})
        selected_ids = sorted(
            row["opportunity_id"] for row in rows if row["disposition"] == "selected"
        )
        persisted_ids = payload.get("selected_opportunity_ids")
        if persisted_ids is not None and persisted_ids != selected_ids:
            raise ValueError("persisted portfolio selection event conflicts with selection rows")
        return {
            "schema_version": "content_portfolio_selection/v1",
            "portfolio_cycle_id": portfolio_cycle_id,
            "selected_opportunity_ids": selected_ids,
            "selections": selections,
            "warnings": payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
            "historical_pillar_counts": payload.get("historical_pillar_counts")
            if isinstance(payload.get("historical_pillar_counts"), dict)
            else {},
            "historical_intent_counts": payload.get("historical_intent_counts")
            if isinstance(payload.get("historical_intent_counts"), dict)
            else {},
            "replayed": True,
        }

    def select(
        self,
        *,
        portfolio_cycle_id: str,
        opportunity_ids: list[str],
        development_slots: int = 3,
        history_window: int = 22,
    ) -> dict[str, Any]:
        if not 11 <= history_window <= 55:
            raise ValueError("portfolio history window must cover one to five 9:1:1 cycles")
        existing = self.selection_for_cycle(portfolio_cycle_id)
        if existing is not None:
            return existing
        unique_ids = list(dict.fromkeys(item.strip() for item in opportunity_ids if item.strip()))
        if not unique_ids:
            raise ValueError("portfolio selection requires candidates")
        with self.store.connection() as connection:
            cycle = connection.execute(
                "SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)
            ).fetchone()
            if not cycle:
                raise ValueError("unknown portfolio cycle")
            placeholders = ",".join("?" for _ in unique_ids)
            rows = connection.execute(
                f"SELECT * FROM content_opportunities WHERE opportunity_id IN ({placeholders})",
                tuple(unique_ids),
            ).fetchall()
            if len(rows) != len(unique_ids):
                raise ValueError("portfolio candidates contain unknown opportunities")
            candidates = [dict(row) for row in rows]
            history_rows = connection.execute(
                """SELECT o.metadata_json FROM portfolio_selections s
                JOIN content_opportunities o ON o.opportunity_id=s.opportunity_id
                WHERE s.disposition='selected' AND s.portfolio_cycle_id IS NOT NULL
                  AND o.owner_requested=0
                  AND s.portfolio_cycle_id!=?
                ORDER BY s.selected_at DESC LIMIT ?""",
                (portfolio_cycle_id, history_window),
            ).fetchall()
        historical_pillars: Counter[str] = Counter()
        historical_intents: Counter[str] = Counter()
        for row in history_rows:
            classification = _classification({"metadata_json": row["metadata_json"]})
            if classification:
                historical_pillars[classification[0]] += 1
                historical_intents[classification[1]] += 1
        gate_eligible = [
            item
            for item in candidates
            if item["status"] in {"qualified", "backlog", "selected", "drafting"}
            and not bool(item["owner_requested"])
            and item["truth_state"] == "pass"
            and item["safety_state"] in {"pass", "owner_review_required"}
            and item["attribution_state"] in {"pass", "required"}
            and _automatic_draft_eligible(item)
        ]
        selected_ids = set(
            rank_portfolio_candidates(
                gate_eligible,
                historical_pillars=historical_pillars,
                historical_intents=historical_intents,
                development_slots=development_slots,
            )
        )
        now = _utcnow()
        results: list[dict[str, Any]] = []
        warnings: list[str] = []
        represented = {
            classification[0]
            for item in gate_eligible
            if (classification := _classification(item)) is not None
        }
        for pillar in PILLAR_TARGETS:
            if pillar not in represented:
                warnings.append(f"No qualified {pillar} opportunity; source or enrich instead of creating filler.")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for item in candidates:
                    opportunity_id = item["opportunity_id"]
                    classification = _classification(item)
                    selected = opportunity_id in selected_ids
                    disposition = "selected" if selected else "held"
                    if bool(item["owner_requested"]):
                        reason = "owner_requested_fast_path"
                    elif (
                        item["truth_state"] == "pass"
                        and item["safety_state"] == "owner_review_required"
                        and item["attribution_state"] in {"pass", "required"}
                        and not _automatic_draft_eligible(item)
                    ):
                        reason = "owner_review_required_before_automatic_drafting"
                    elif item not in gate_eligible:
                        reason = "eligibility_gate_failed"
                    elif classification is None:
                        reason = "portfolio_classification_missing"
                    elif selected:
                        reason = "rolling_40_40_20_and_9_1_1_deficit"
                    else:
                        reason = "qualified_but_not_selected_this_cycle"
                    key = f"content-portfolio:{portfolio_cycle_id}:{opportunity_id}"
                    selection_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:selection:{key}"))
                    reason_payload = {
                        "schema_version": "content_portfolio_selection_reason/v1",
                        "reason": reason,
                        "pillar": classification[0] if classification else None,
                        "intent": classification[1] if classification else None,
                        "portfolio_score": classification[2] if classification else None,
                        "contracts": ["rolling_40_40_20/v1", "rolling_9_1_1/v1"],
                    }
                    connection.execute(
                        """INSERT INTO portfolio_selections(
                            selection_id,portfolio_cycle_id,opportunity_id,disposition,reason_json,selected_at,idempotency_key
                        ) VALUES (?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                        (selection_id, portfolio_cycle_id, opportunity_id, disposition, _canonical_json(reason_payload), now, key),
                    )
                    existing = connection.execute(
                        "SELECT * FROM portfolio_selections WHERE idempotency_key=?", (key,)
                    ).fetchone()
                    if not existing or existing["disposition"] != disposition:
                        raise ValueError("portfolio selection idempotency conflict")
                    if selected and item["status"] not in {"drafting", "review"}:
                        connection.execute(
                            "UPDATE content_opportunities SET status='selected',updated_at=? WHERE opportunity_id=?",
                            (now, opportunity_id),
                        )
                    results.append({**dict(existing), "reason": reason_payload})
                event_key = f"content-portfolio-selected:{portfolio_cycle_id}"
                event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                        payload_json,provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,'content_portfolio.selected','portfolio_cycle',?,?,'portfolio_policy',?,'{}','[]',?)
                    ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        event_id,
                        portfolio_cycle_id,
                        now,
                        _canonical_json(
                            {
                                "selected_opportunity_ids": sorted(selected_ids),
                                "warnings": warnings,
                                "historical_pillar_counts": dict(historical_pillars),
                                "historical_intent_counts": dict(historical_intents),
                            }
                        ),
                        event_key,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return {
            "schema_version": "content_portfolio_selection/v1",
            "portfolio_cycle_id": portfolio_cycle_id,
            "selected_opportunity_ids": sorted(selected_ids),
            "selections": results,
            "warnings": warnings,
            "historical_pillar_counts": dict(historical_pillars),
            "historical_intent_counts": dict(historical_intents),
            "replayed": False,
        }
