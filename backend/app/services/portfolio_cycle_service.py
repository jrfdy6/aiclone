from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping

from app.services.integrated_memory_readiness_service import (
    READINESS_SCHEMA_VERSION,
    _ready_receipt_matches_current_consolidation,
    _receipt_hash_is_current,
)
from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow
from app.services.workspace_registry_service import (
    _validated_goal_contract,
    active_portfolio_workspace_keys,
    workspace_registry_entry,
)
from app.utils.ai_clone_clock import (
    CLOCK_AUTHORITY,
    CLOCK_SCHEMA_VERSION,
    same_utc_observation_second,
    utc_iso,
)


CONCLUSION_KINDS = frozenset({"conclusion", "healthy_no_change"})
PROVENANCE_KINDS = frozenset({"independent_agent", "deterministic_policy", "synthesized_lens"})
OPS_HEALTHY_SUBSYSTEM_STATES = frozenset(
    {"ready", "healthy", "complete", "completed", "available", "ok"}
)
OPS_UNHEALTHY_SUBSYSTEM_STATES = frozenset(
    {"degraded", "failed", "unhealthy", "not_verified", "unavailable", "unknown"}
)
NON_BLOCKING_OPS_HEALTH_KEYS = frozenset(
    {"backup_recovery", "firestore_readiness"}
)
WORKSPACE_GOAL_AUTHORITY_FUTURE_TRIGGER = (
    "Restore the existing private Shared Ops workspace-goal authority with a complete "
    "workspace_goal_contract/v1 entry for this workspace, then rerun the workspace cycle."
)
SHARED_OPS_WORKSPACE_KEY = "shared_ops"


class PortfolioCycleConflict(ValueError):
    pass


def _explicit_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def classify_ops_subsystem_health(system_health: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the closed Ops health taxonomy and fail closed on drift."""

    normalized_health: dict[str, str] = {}
    for raw_key, raw_value in system_health.items():
        key = str(raw_key).strip().lower()
        value = raw_value
        if isinstance(value, bool):
            state = "healthy" if value else "failed"
        else:
            if isinstance(value, Mapping):
                value = value.get("state") or value.get("status")
            state = str(value or "unknown").strip().lower().replace(" ", "_")
            if state.startswith("failed:"):
                state = "failed"
            elif state.startswith("degraded:"):
                state = "degraded"
        if (
            state not in OPS_HEALTHY_SUBSYSTEM_STATES
            and state not in OPS_UNHEALTHY_SUBSYSTEM_STATES
        ):
            state = "unknown"
        normalized_health[key] = state
    unhealthy_keys = sorted(
        key
        for key, state in normalized_health.items()
        if state not in OPS_HEALTHY_SUBSYSTEM_STATES
    )
    warning_only_keys = sorted(
        set(unhealthy_keys).intersection(NON_BLOCKING_OPS_HEALTH_KEYS)
    )
    blocking_keys = sorted(set(unhealthy_keys) - NON_BLOCKING_OPS_HEALTH_KEYS)
    return {
        "normalized_health": dict(sorted(normalized_health.items())),
        "unhealthy_keys": unhealthy_keys,
        "warning_only_keys": warning_only_keys,
        "blocking_keys": blocking_keys,
    }


def workspace_goal_contract_validation_error(
    workspace_key: str,
    goal: Any,
) -> str | None:
    """Return the existing canonical goal validator's bounded error, if any."""

    try:
        _validated_goal_contract(workspace_key, goal)
    except ValueError as exc:
        return " ".join(str(exc).split())[:500]
    return None


def _shared_ops_goal_contract() -> tuple[dict[str, Any], str | None]:
    """Read the existing private Shared Ops goal authority without inventing one."""

    try:
        entry = workspace_registry_entry(SHARED_OPS_WORKSPACE_KEY)
    except (KeyError, ValueError):
        return {}, "canonical Shared Ops workspace-goal authority is unavailable or invalid"
    raw_goal = entry.get("goal_contract")
    goal = dict(raw_goal) if isinstance(raw_goal, Mapping) else {}
    error = workspace_goal_contract_validation_error(
        SHARED_OPS_WORKSPACE_KEY,
        goal,
    )
    if error:
        return {}, "canonical Shared Ops workspace-goal authority is unavailable or invalid"
    return goal, None


def _healthy_no_change_validation_error(
    workspace_key: str,
    payload: Mapping[str, Any],
) -> str | None:
    goal_error = workspace_goal_contract_validation_error(
        workspace_key,
        payload.get("goal"),
    )
    if goal_error:
        return f"healthy_no_change requires a complete canonical workspace goal: {goal_error}"
    no_action = payload.get("no_action")
    if not isinstance(no_action, list):
        return "healthy_no_change requires an explicit no-action receipt"
    if not any(
        isinstance(item, Mapping)
        and item.get("selected") is True
        and bool(str(item.get("reason") or item.get("summary") or "").strip())
        and bool(str(item.get("future_trigger") or item.get("trigger") or "").strip())
        for item in no_action
    ):
        return "healthy_no_change requires one selected no-action reason and future trigger"
    return None


def active_portfolio_workspaces(registry_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> list[str]:
    return sorted(active_portfolio_workspace_keys([dict(entry) for entry in registry_entries]))


class PortfolioCycleService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def start_cycle(
        self,
        *,
        portfolio_cycle_id: str,
        cycle_date: date,
        expected_workspaces: list[str],
        readiness_id: str,
        morning_brief_ref: str | None = None,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        self.store.migrate()
        expected = sorted({item.strip() for item in expected_workspaces if item.strip()})
        if not expected:
            raise ValueError("portfolio cycle requires at least one active workspace")
        now = _utcnow()
        idempotency_key = f"portfolio-cycle:{portfolio_cycle_id}"
        with self.store.connection() as connection:
            readiness = connection.execute("SELECT * FROM readiness_receipts WHERE readiness_id=?", (readiness_id,)).fetchone()
            if not readiness:
                raise ValueError("portfolio cycle requires a persisted memory readiness receipt")
            try:
                readiness_payload = json.loads(readiness["recall_probe_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("portfolio cycle readiness payload is invalid") from exc
            if (
                not isinstance(readiness_payload, dict)
                or readiness_payload.get("schema_version") != READINESS_SCHEMA_VERSION
                or str(readiness_payload.get("cycle_id") or "") != portfolio_cycle_id
                or str(readiness_payload.get("status") or "") != str(readiness["status"])
                or str(readiness_payload.get("consolidation_id") or "")
                != str(readiness["consolidation_id"] or "")
                or not _receipt_hash_is_current(readiness_payload)
            ):
                raise ValueError("portfolio cycle readiness receipt is not bound to this exact cycle")
            consolidation = None
            if readiness["consolidation_id"]:
                consolidation = connection.execute(
                    "SELECT * FROM memory_consolidations WHERE consolidation_id=?",
                    (readiness["consolidation_id"],),
                ).fetchone()
                if not consolidation:
                    raise ValueError("portfolio cycle readiness references a missing consolidation")
            if readiness["status"] == "ready" and not _ready_receipt_matches_current_consolidation(
                connection, dict(readiness), cycle_id=portfolio_cycle_id
            ):
                raise ValueError("portfolio cycle requires current exact-cycle memory readiness")

            semantic_observed_at = None
            if observed_at is not None:
                semantic_observed_at = _explicit_utc(observed_at)
                if semantic_observed_at is None:
                    raise ValueError(
                        "portfolio cycle observation must be timezone-aware UTC"
                    )
            if semantic_observed_at is None and consolidation is not None:
                semantic_observed_at = _explicit_utc(consolidation["window_end"])
            if semantic_observed_at is None:
                raise ValueError("portfolio cycle requires an explicit observation when consolidation is unavailable")
            if semantic_observed_at.date() != cycle_date:
                raise ValueError("portfolio cycle observation does not match its UTC cycle date")
            if consolidation is not None:
                consolidation_observed_at = _explicit_utc(consolidation["window_end"])
                if consolidation_observed_at is None:
                    raise ValueError("Dream consolidation requires a timezone-aware UTC window_end")
                if not same_utc_observation_second(
                    consolidation_observed_at, semantic_observed_at
                ):
                    raise ValueError("portfolio cycle observation does not match its Dream consolidation")

            core_metadata = {
                "expected_workspaces": expected,
                "readiness_id": readiness_id,
                "consolidation_id": readiness["consolidation_id"],
                "observed_at": semantic_observed_at.isoformat(),
            }
            metadata = {**core_metadata, "morning_brief_ref": morning_brief_ref}
            initial_status = "waiting" if readiness["status"] == "ready" else "degraded"
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO portfolio_cycles(
                        portfolio_cycle_id,cycle_date,status,expected_workspace_count,created_at,idempotency_key,metadata_json
                    ) VALUES (?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (portfolio_cycle_id, cycle_date.isoformat(), initial_status, len(expected), now, idempotency_key, _canonical_json(metadata)),
                )
                row = connection.execute("SELECT * FROM portfolio_cycles WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                stored_metadata = json.loads(row["metadata_json"]) if row else {}
                stored_core = {
                    key: stored_metadata.get(key)
                    for key in core_metadata
                }
                if (
                    not row
                    or row["portfolio_cycle_id"] != portfolio_cycle_id
                    or row["cycle_date"] != cycle_date.isoformat()
                    or int(row["expected_workspace_count"]) != len(expected)
                    or row["idempotency_key"] != idempotency_key
                    or stored_core != core_metadata
                ):
                    raise PortfolioCycleConflict("portfolio cycle idempotency conflict")
                stored_brief = stored_metadata.get("morning_brief_ref")
                if stored_brief and morning_brief_ref and stored_brief != morning_brief_ref:
                    raise PortfolioCycleConflict("portfolio cycle idempotency conflict")
                if not stored_brief and morning_brief_ref:
                    stored_metadata["morning_brief_ref"] = morning_brief_ref
                    connection.execute(
                        "UPDATE portfolio_cycles SET metadata_json=? WHERE portfolio_cycle_id=?",
                        (_canonical_json(stored_metadata), portfolio_cycle_id),
                    )
                    row = connection.execute(
                        "SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?",
                        (portfolio_cycle_id,),
                    ).fetchone()
                self._append_event(
                    connection,
                    event_type="portfolio_cycle.started",
                    aggregate_type="portfolio_cycle",
                    aggregate_id=portfolio_cycle_id,
                    payload={"status": initial_status, "expected_workspace_count": len(expected)},
                    provenance={"readiness_id": readiness_id},
                    idempotency_key=f"portfolio-cycle-started:{portfolio_cycle_id}",
                )
                connection.execute("COMMIT")
                return dict(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def record_workspace_conclusion(
        self,
        *,
        portfolio_cycle_id: str,
        workspace_key: str,
        conclusion_kind: str,
        provenance_kind: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if conclusion_kind not in CONCLUSION_KINDS:
            raise ValueError("invalid workspace conclusion kind")
        if provenance_kind not in PROVENANCE_KINDS:
            raise ValueError("invalid workspace conclusion provenance")
        workspace_key = workspace_key.strip()
        now = _utcnow()
        with self.store.connection() as connection:
            cycle = connection.execute("SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()
            if not cycle:
                raise ValueError("unknown portfolio cycle")
            expected = json.loads(cycle["metadata_json"]).get("expected_workspaces") or []
            if workspace_key not in expected:
                raise ValueError("workspace is not active in this portfolio cycle")
            conclusion_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:workspace-conclusion:{idempotency_key}"))
            normalized_payload = self._normalize_conclusion_payload(payload)
            cycle_metadata = json.loads(cycle["metadata_json"])
            cycle_observed_at = _explicit_utc(cycle_metadata.get("observed_at"))
            if cycle_observed_at is None:
                raise PortfolioCycleConflict(
                    "portfolio cycle is missing its explicit UTC observation"
                )
            claimed_cycle_id = str(normalized_payload.get("cycle_id") or "").strip()
            if claimed_cycle_id and claimed_cycle_id != portfolio_cycle_id:
                raise PortfolioCycleConflict(
                    "workspace conclusion cycle identity does not match its portfolio cycle"
                )
            claimed_observed_at = normalized_payload.get("observed_at")
            if claimed_observed_at:
                parsed_claim = _explicit_utc(claimed_observed_at)
                if parsed_claim is None or not same_utc_observation_second(
                    parsed_claim, cycle_observed_at
                ):
                    raise PortfolioCycleConflict(
                        "workspace conclusion observation does not match its portfolio cycle"
                    )
            normalized_payload["cycle_id"] = portfolio_cycle_id
            normalized_payload["observed_at"] = cycle_observed_at.isoformat()
            if conclusion_kind == "healthy_no_change":
                validation_error = _healthy_no_change_validation_error(
                    workspace_key,
                    normalized_payload,
                )
                if validation_error:
                    raise ValueError(validation_error)
            normalized_payload_json = _canonical_json(normalized_payload)
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO workspace_conclusions(
                        conclusion_id,portfolio_cycle_id,workspace_key,conclusion_kind,provenance_kind,
                        payload_json,created_at,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        conclusion_id,
                        portfolio_cycle_id,
                        workspace_key,
                        conclusion_kind,
                        provenance_kind,
                        normalized_payload_json,
                        now,
                        idempotency_key,
                    ),
                )
                row = connection.execute("SELECT * FROM workspace_conclusions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if (
                    not row
                    or row["portfolio_cycle_id"] != portfolio_cycle_id
                    or row["workspace_key"] != workspace_key
                    or row["conclusion_kind"] != conclusion_kind
                    or row["provenance_kind"] != provenance_kind
                    or row["payload_json"] != normalized_payload_json
                ):
                    raise PortfolioCycleConflict("workspace conclusion idempotency conflict")
                self._append_event(
                    connection,
                    event_type="workspace.concluded",
                    aggregate_type="workspace_conclusion",
                    aggregate_id=row["conclusion_id"],
                    payload={
                        "portfolio_cycle_id": portfolio_cycle_id,
                        "workspace_key": workspace_key,
                        "conclusion_kind": conclusion_kind,
                        "cycle_id": normalized_payload.get("cycle_id") or portfolio_cycle_id,
                        "observed_at": normalized_payload.get("observed_at"),
                        "summary": normalized_payload["summary"],
                        "goal": normalized_payload.get("goal") or {},
                        "changes_since_prior": self._bounded_event_items(
                            normalized_payload.get("changes_since_prior")
                        ),
                        "system_decisions": self._bounded_event_items(
                            normalized_payload.get("system_decisions")
                        ),
                        "actions_taken": self._bounded_event_items(
                            normalized_payload.get("actions_taken")
                        ),
                        "completed_work": self._bounded_event_items(
                            normalized_payload.get("completed_work")
                        ),
                        "failed_work": self._bounded_event_items(
                            normalized_payload.get("failed_work")
                        ),
                        "carried_forward": self._bounded_event_items(
                            normalized_payload.get("carried_forward")
                        ),
                        "blockers": self._bounded_event_items(
                            normalized_payload.get("blockers")
                        ),
                        "decisions": self._bounded_event_items(normalized_payload.get("decisions")),
                        "owner_decisions": self._bounded_event_items(
                            normalized_payload.get("owner_decisions")
                        ),
                        "no_action": self._bounded_event_items(normalized_payload.get("no_action")),
                        "recommendation_resolutions": self._bounded_event_items(
                            normalized_payload.get("recommendation_resolutions")
                        ),
                        "next_cycle_inputs": self._bounded_event_items(
                            normalized_payload.get("next_cycle_inputs")
                        ),
                        "recommended_next_actions": self._bounded_event_items(
                            normalized_payload.get("recommended_next_actions")
                        ),
                        "reference_only": self._bounded_event_items(
                            normalized_payload.get("reference_only")
                        ),
                    },
                    provenance={"provenance_kind": provenance_kind},
                    idempotency_key=f"workspace-concluded:{idempotency_key}",
                )
                count = connection.execute("SELECT COUNT(*) FROM workspace_conclusions WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()[0]
                new_status = "ready" if count == cycle["expected_workspace_count"] and cycle["status"] != "degraded" else cycle["status"]
                connection.execute("UPDATE portfolio_cycles SET status=? WHERE portfolio_cycle_id=?", (new_status, portfolio_cycle_id))
                connection.execute("COMMIT")
                return dict(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def conclude_ops(
        self,
        *,
        portfolio_cycle_id: str,
        system_health: Mapping[str, Any],
        ops_decisions: list[Mapping[str, Any]] | None = None,
        owner_calls: list[Mapping[str, Any]] | None = None,
        recommended_next_actions: list[str] | None = None,
        observed_at: datetime | None = None,
        workspace_cycle_evaluations: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self.store.connection() as connection:
            cycle = connection.execute("SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()
            if not cycle:
                raise ValueError("unknown portfolio cycle")
            existing = connection.execute("SELECT * FROM ops_conclusions WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()
            metadata = json.loads(cycle["metadata_json"])
            cycle_observed_at = _explicit_utc(metadata.get("observed_at"))
            if cycle_observed_at is None:
                raise PortfolioCycleConflict(
                    "portfolio cycle is missing its explicit timezone-aware UTC observation"
                )
            conclusion_observed_at = (
                _explicit_utc(observed_at)
                if observed_at is not None
                else cycle_observed_at
            )
            if conclusion_observed_at is None:
                raise PortfolioCycleConflict(
                    "Ops conclusion requires a timezone-aware UTC observation"
                )
            if not same_utc_observation_second(
                conclusion_observed_at, cycle_observed_at
            ):
                raise PortfolioCycleConflict(
                    "Ops conclusion observation does not match its portfolio cycle"
                )
            expected = metadata.get("expected_workspaces") or []
            rows = connection.execute("SELECT * FROM workspace_conclusions WHERE portfolio_cycle_id=? ORDER BY workspace_key", (portfolio_cycle_id,)).fetchall()
            by_workspace = {row["workspace_key"]: row for row in rows}
            missing = sorted(set(expected) - set(by_workspace))
            readiness = connection.execute("SELECT * FROM readiness_receipts WHERE readiness_id=?", (metadata.get("readiness_id"),)).fetchone()
            readiness_payload = json.loads(readiness["recall_probe_json"]) if readiness else {}
            degraded_warnings: list[str] = []
            if readiness_payload.get("status") != "ready":
                degraded_warnings.append(
                    f"Memory readiness is degraded at {readiness_payload.get('failed_component') or 'unknown component'}; using last verified memory from {readiness_payload.get('last_verified_memory_at') or 'unknown time'}."
                )
            if missing:
                degraded_warnings.append(f"Missing workspace conclusions: {', '.join(missing)}.")
            health_verdict = classify_ops_subsystem_health(system_health)
            unhealthy = health_verdict["unhealthy_keys"]
            if unhealthy:
                degraded_warnings.append(f"Unhealthy or unverified subsystems: {', '.join(unhealthy)}.")
            workspace_updates = []
            blockers: list[dict[str, Any]] = []
            urgent: list[dict[str, Any]] = []
            workspace_decisions: list[dict[str, Any]] = []
            workspace_recommendations: list[dict[str, Any]] = []
            workspace_recursion: list[dict[str, Any]] = []
            underway: list[dict[str, Any]] = []
            completed: list[dict[str, Any]] = []
            evidence_links: list[dict[str, Any]] = []
            goal_authority_failures: list[str] = []
            for key in expected:
                row = by_workspace.get(key)
                if not row:
                    workspace_updates.append({"workspace_key": key, "state": "missing", "summary": "No conclusion receipt received."})
                    continue
                payload = json.loads(row["payload_json"])
                payload_blockers = list(payload.get("blockers") or [])
                goal_error = workspace_goal_contract_validation_error(
                    key,
                    payload.get("goal"),
                )
                if goal_error:
                    goal_authority_failures.append(key)
                    if not any(
                        isinstance(item, Mapping)
                        and item.get("reason_code") == "workspace_goal_authority_blocked"
                        for item in payload_blockers
                    ):
                        payload_blockers.append(
                            {
                                "kind": "workspace_goal_authority_blocked",
                                "reason_code": "workspace_goal_authority_blocked",
                                "summary": "Goal-directed workspace evaluation is blocked by unavailable or invalid canonical goal authority.",
                                "reason": goal_error,
                                "future_trigger": WORKSPACE_GOAL_AUTHORITY_FUTURE_TRIGGER,
                                "route": "ops",
                            }
                        )
                workspace_updates.append({"workspace_key": key, "state": row["conclusion_kind"], "summary": payload["summary"], "provenance_kind": row["provenance_kind"]})
                blockers.extend({"workspace_key": key, **item} for item in payload_blockers)
                urgent.extend({"workspace_key": key, **item} for item in payload["urgent_escalations"])
                workspace_decisions.extend({"workspace_key": key, **item} for item in payload["decisions"])
                underway.extend({"workspace_key": key, **item} for item in payload["work_underway"])
                completed.extend({"workspace_key": key, **item} for item in payload["completed_work"])
                evidence_links.extend({"workspace_key": key, **item} for item in payload["evidence_links"])
                workspace_recommendations.extend(
                    {"workspace_key": key, **item}
                    for item in payload["recommended_next_actions"]
                )
                workspace_recursion.append(
                    {
                        "workspace_key": key,
                        "goal": payload.get("goal") or {},
                        "changes_since_prior": payload.get("changes_since_prior") or [],
                        "system_decisions": payload.get("system_decisions") or [],
                        "actions_taken": payload.get("actions_taken") or [],
                        "completed_work": payload.get("completed_work") or [],
                        "failed_work": payload.get("failed_work") or [],
                        "carried_forward": payload.get("carried_forward") or [],
                        "owner_decisions": payload.get("owner_decisions") or [],
                        "blocked": payload_blockers,
                        "no_action": payload.get("no_action") or [],
                        "recommendations": payload.get("recommended_next_actions") or [],
                        "reference_only": payload.get("reference_only") or [],
                        "recommendation_resolutions": payload.get("recommendation_resolutions") or [],
                        "next_cycle_inputs": payload.get("next_cycle_inputs") or [],
                    }
                )
            if goal_authority_failures:
                degraded_warnings.append(
                    "Workspace goal authority is unavailable or invalid: "
                    f"{', '.join(sorted(goal_authority_failures))}."
                )
            combined_recommendations = [
                *workspace_recommendations,
                *(
                    {"summary": item.strip(), "route": "ops"}
                    for item in recommended_next_actions or []
                    if item.strip()
                ),
            ]
            deduped_recommendations: list[dict[str, Any]] = []
            seen_recommendations: set[tuple[str, str]] = set()
            for item in combined_recommendations:
                identity = (
                    str(item.get("workspace_key") or "ops"),
                    str(item.get("summary") or item.get("title") or "").strip().lower(),
                )
                if not identity[1] or identity in seen_recommendations:
                    continue
                seen_recommendations.add(identity)
                deduped_recommendations.append(item)
            ops_recommendations: list[dict[str, Any]] = []
            seen_ops_recommendations: set[str] = set()
            for item in recommended_next_actions or []:
                summary = item.strip() if isinstance(item, str) else ""
                identity = summary.lower()
                if not summary or identity in seen_ops_recommendations:
                    continue
                seen_ops_recommendations.add(identity)
                ops_recommendations.append({"summary": summary, "route": "ops"})
                if len(ops_recommendations) >= 100:
                    break
            shared_ops_goal, shared_ops_goal_error = _shared_ops_goal_contract()
            shared_ops_blockers = [dict(item) for item in blockers]
            if shared_ops_goal_error:
                degraded_warnings.append(
                    "Shared Ops goal authority is unavailable or invalid."
                )
                shared_ops_blockers.append(
                    {
                        "kind": "workspace_goal_authority_blocked",
                        "reason_code": "shared_ops_goal_authority_blocked",
                        "summary": "Shared Ops reconciliation is degraded because its canonical goal authority is unavailable or invalid.",
                        "reason": shared_ops_goal_error,
                        "future_trigger": WORKSPACE_GOAL_AUTHORITY_FUTURE_TRIGGER,
                        "route": "ops",
                    }
                )
            shared_ops_no_action: list[dict[str, Any]] = []
            all_projects_no_change = bool(workspace_recursion) and len(
                workspace_recursion
            ) == len(expected) and all(
                bool(item.get("no_action")) for item in workspace_recursion
            )
            if (
                all_projects_no_change
                and not shared_ops_blockers
                and not list(ops_decisions or [])
                and not list(owner_calls or [])
                and not ops_recommendations
                and shared_ops_goal
            ):
                shared_ops_no_action.append(
                    {
                        "selected": True,
                        "summary": "Shared Ops reconciled every active project and found no eligible cross-workspace disposition beyond the recorded project no-action receipts.",
                        "trigger": str(shared_ops_goal.get("no_action_trigger") or ""),
                    }
                )
            shared_ops_next_cycle_inputs: list[dict[str, Any]] = []
            for workspace_item in workspace_recursion:
                workspace_key = str(workspace_item.get("workspace_key") or "")
                for raw_input in workspace_item.get("next_cycle_inputs") or []:
                    if isinstance(raw_input, Mapping):
                        shared_ops_next_cycle_inputs.append(
                            {"workspace_key": workspace_key, **dict(raw_input)}
                        )
            shared_ops_next_cycle_inputs.extend(dict(item) for item in ops_recommendations)
            shared_ops_next_cycle_inputs.append(
                {
                    "kind": "canonical_ops_reconciliation_receipt",
                    "summary": "The next Dream consolidation consumes this Ops disposition and the linked workspace conclusion receipts through the existing structured-memory lane.",
                    "trigger": "A later portfolio cycle starts with a distinct ai_clone_utc observation.",
                }
            )
            status = "degraded" if degraded_warnings else "complete"
            conclusion_observed_iso = utc_iso(
                conclusion_observed_at,
                seconds=False,
            )
            final_payload = {
                "schema_version": "ops_standup_summary_conclusion/v1",
                "portfolio_cycle_id": portfolio_cycle_id,
                "cycle_date": cycle["cycle_date"],
                "observed_at": conclusion_observed_iso,
                "clock": {
                    "schema_version": CLOCK_SCHEMA_VERSION,
                    "authority": CLOCK_AUTHORITY,
                    "timezone": "UTC",
                    "observed_at": conclusion_observed_iso,
                },
                "status": status,
                "workspace_updates": workspace_updates,
                "ai_clone_process_updates": {
                    "memory_readiness": readiness_payload,
                    "morning_brief_ref": metadata.get("morning_brief_ref"),
                },
                "endpoint_and_subsystem_health": health_verdict["normalized_health"],
                "work_underway": underway,
                "completed_work": completed,
                "blockers": blockers,
                "urgent_escalations": urgent,
                "workspace_decisions": workspace_decisions,
                "workspace_recursion": workspace_recursion,
                "shared_ops_reconciliation": {
                    "summary": (
                        f"Shared Ops reconciled {len(workspace_recursion)} of "
                        f"{len(expected)} active project workspace conclusions."
                    ),
                    "goal": shared_ops_goal,
                    "evaluated": workspace_updates,
                    "system_decisions": [dict(item) for item in ops_decisions or []],
                    "actions_taken": [
                        {
                            "kind": "portfolio_reconciliation",
                            "summary": (
                                f"Reconciled {len(workspace_recursion)} of {len(expected)} "
                                "active project workspace conclusions without executing project work."
                            ),
                            "status": status,
                        }
                    ],
                    "owner_calls": [dict(item) for item in owner_calls or []],
                    "blocked": shared_ops_blockers,
                    "no_action": shared_ops_no_action,
                    "recommendations": ops_recommendations,
                    "reference_only": [
                        {
                            "classification": "reference_only",
                            **{
                                key: value
                                for key, value in dict(item).items()
                                if key != "route"
                            },
                        }
                        for item in evidence_links
                    ],
                    "next_cycle_inputs": shared_ops_next_cycle_inputs,
                },
                "ops_decisions": [dict(item) for item in ops_decisions or []],
                "owner_calls": [dict(item) for item in owner_calls or []],
                "degraded_system_warnings": degraded_warnings,
                "supporting_evidence_links": evidence_links,
                "recommended_next_actions": deduped_recommendations,
                "workspace_cycle_evaluations": self._bounded_event_items(
                    workspace_cycle_evaluations
                ),
            }
            ops_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:ops-conclusion:{portfolio_cycle_id}"))
            now = _utcnow()
            final_payload_json = _canonical_json(final_payload)
            if existing and existing["status"] == status and existing["payload_json"] == final_payload_json:
                return self._ops_response(dict(existing))
            if existing and existing["status"] == "complete":
                raise PortfolioCycleConflict(
                    "complete Ops conclusion replay inputs changed"
                )
            connection.execute("BEGIN IMMEDIATE")
            try:
                if existing:
                    connection.execute(
                        """UPDATE ops_conclusions SET payload_json=?,status=?,created_at=?
                        WHERE ops_conclusion_id=? AND status!='complete'""",
                        (final_payload_json, status, now, existing["ops_conclusion_id"]),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0] != 1:
                        raise PortfolioCycleConflict("Ops conclusion changed before repair")
                    ops_id = existing["ops_conclusion_id"]
                else:
                    connection.execute(
                        """INSERT INTO ops_conclusions(
                            ops_conclusion_id,portfolio_cycle_id,payload_json,status,created_at,idempotency_key
                        ) VALUES (?,?,?,?,?,?)""",
                        (ops_id, portfolio_cycle_id, final_payload_json, status, now, f"ops-conclusion:{portfolio_cycle_id}"),
                    )
                attempt_number = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM ops_conclusion_attempts WHERE ops_conclusion_id=?", (ops_id,)
                    ).fetchone()[0]
                ) + 1
                attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:ops-attempt:{ops_id}:{attempt_number}"))
                connection.execute(
                    """INSERT INTO ops_conclusion_attempts(
                        attempt_id,ops_conclusion_id,attempt_number,payload_json,status,created_at
                    ) VALUES (?,?,?,?,?,?)""",
                    (attempt_id, ops_id, attempt_number, final_payload_json, status, now),
                )
                connection.execute(
                    "UPDATE portfolio_cycles SET status=?,completed_at=? WHERE portfolio_cycle_id=?",
                    (status, now, portfolio_cycle_id),
                )
                self._append_event(
                    connection,
                    event_type="ops.concluded" if attempt_number == 1 else "ops.reconcluded",
                    aggregate_type="ops_conclusion",
                    aggregate_id=ops_id,
                    payload={
                        "portfolio_cycle_id": portfolio_cycle_id,
                        "observed_at": final_payload.get("observed_at"),
                        "status": status,
                        "missing_workspaces": missing,
                        "attempt_number": attempt_number,
                        "recommended_next_actions": self._bounded_event_items(
                            final_payload.get("recommended_next_actions")
                        ),
                        "owner_calls": self._bounded_event_items(final_payload.get("owner_calls")),
                        "workspace_decisions": self._bounded_event_items(
                            final_payload.get("workspace_decisions")
                        ),
                        "goal": self._bounded_mapping(
                            final_payload["shared_ops_reconciliation"].get("goal") or {}
                        ),
                        "system_decisions": self._bounded_event_items(
                            final_payload["shared_ops_reconciliation"].get("system_decisions")
                        ),
                        "actions_taken": self._bounded_event_items(
                            final_payload["shared_ops_reconciliation"].get("actions_taken")
                        ),
                        "blockers": self._bounded_event_items(
                            final_payload["shared_ops_reconciliation"].get("blocked")
                        ),
                        "owner_decisions": self._bounded_event_items(
                            final_payload["shared_ops_reconciliation"].get("owner_calls")
                        ),
                        "no_action": self._bounded_event_items(
                            final_payload["shared_ops_reconciliation"].get("no_action")
                        ),
                        "next_cycle_inputs": self._bounded_event_items(
                            final_payload["shared_ops_reconciliation"].get("next_cycle_inputs")
                        ),
                    },
                    provenance={"workspace_conclusion_ids": [row["conclusion_id"] for row in rows]},
                    idempotency_key=f"ops-concluded:{portfolio_cycle_id}:attempt:{attempt_number}",
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return self._ops_response(
                dict(connection.execute("SELECT * FROM ops_conclusions WHERE ops_conclusion_id=?", (ops_id,)).fetchone())
            )

    @staticmethod
    def _normalize_conclusion_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        summary = " ".join(str(payload.get("summary") or "").split()).strip()
        if not summary:
            raise ValueError("workspace conclusion summary is required")
        normalized = {
            "summary": summary[:1000],
            "cycle_id": " ".join(str(payload.get("cycle_id") or "").split())[:200] or None,
            "observed_at": " ".join(str(payload.get("observed_at") or "").split())[:100] or None,
        }
        goal = payload.get("goal")
        normalized["goal"] = PortfolioCycleService._bounded_mapping(goal) if isinstance(goal, Mapping) else {}
        for key in (
            "changes_since_prior",
            "system_decisions",
            "actions_taken",
            "work_underway",
            "completed_work",
            "failed_work",
            "carried_forward",
            "blockers",
            "urgent_escalations",
            "decisions",
            "owner_decisions",
            "no_action",
            "recommendation_resolutions",
            "next_cycle_inputs",
            "evidence_links",
            "recommended_next_actions",
            "reference_only",
        ):
            raw_items = payload.get(key) or []
            if not isinstance(raw_items, list):
                raise ValueError(f"{key} must be a list")
            items = []
            for raw in raw_items[:100]:
                if isinstance(raw, dict):
                    item = {str(k): v for k, v in raw.items() if isinstance(v, (str, int, float, bool)) or v is None}
                else:
                    item = {"summary": " ".join(str(raw).split())[:500]}
                route = str(item.get("route") or "").strip().lower()
                if key != "reference_only" and route in {"", "uncertain"}:
                    item["route"] = "ops"
                items.append(item)
            normalized[key] = items
        return normalized

    @staticmethod
    def _bounded_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for raw_key, cell in list(value.items())[:20]:
            key = str(raw_key)[:80]
            if isinstance(cell, bool) or isinstance(cell, (int, float)) or cell is None:
                output[key] = cell
            elif isinstance(cell, str):
                output[key] = " ".join(cell.split())[:1000]
            elif isinstance(cell, list):
                output[key] = [
                    " ".join(str(item).split())[:500]
                    for item in cell[:20]
                    if isinstance(item, (str, int, float, bool))
                ]
        return output

    @staticmethod
    def _bounded_event_items(value: Any) -> list[dict[str, Any]]:
        """Project only bounded decision/recommendation facts into durable events."""

        items: list[dict[str, Any]] = []
        for raw in value if isinstance(value, list) else []:
            source = raw if isinstance(raw, dict) else {"summary": raw}
            item: dict[str, Any] = {}
            for raw_key, cell in list(source.items())[:12]:
                key = str(raw_key)[:80]
                if isinstance(cell, bool) or isinstance(cell, (int, float)) or cell is None:
                    item[key] = cell
                elif isinstance(cell, str):
                    item[key] = " ".join(cell.split())[:500]
            if item:
                items.append(item)
            if len(items) >= 12:
                break
        return items

    @staticmethod
    def _append_event(
        connection: Any,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        provenance: Mapping[str, Any],
        idempotency_key: str,
    ) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,
                provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,'portfolio_cycle',?,?, '[]',?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (event_id, event_type, aggregate_type, aggregate_id, _utcnow(), _canonical_json(dict(payload)), _canonical_json(dict(provenance)), idempotency_key),
        )

    @staticmethod
    def _ops_response(row: dict[str, Any]) -> dict[str, Any]:
        return {**json.loads(row["payload_json"]), "ops_conclusion_id": row["ops_conclusion_id"], "created_at": row["created_at"]}
