from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.services.brain_response_privacy_service import sanitize_brain_text
from app.services.execution_artifact_reference_service import (
    contains_private_filesystem_reference,
)
from app.services.workspace_registry_service import (
    ACTIVE_PORTFOLIO_WORKSPACE_STATUSES,
    _validated_goal_contract,
    workspace_registry_entries,
)
from app.utils.ai_clone_clock import CLOCK_AUTHORITY, CLOCK_SCHEMA_VERSION


PROJECTION_SCHEMA = "ops_workspace_goal_projection/v1"
SNAPSHOT_TYPE = "ops_workspace_goal_contracts"
WORKSPACE_KEY = "shared_ops"
MAX_BYTES = 64 * 1024
MAX_WORKSPACES = 25

_PROJECTION_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "observed_at",
        "clock",
        "state",
        "reason_codes",
        "authority_sha256",
        "projected_contracts_sha256",
        "workspaces",
        "data_policy",
    }
)
_WORKSPACE_FIELDS = frozenset({"workspace_key", "display_name", "goal"})
_GOAL_FIELDS = frozenset(
    {
        "schema_version",
        "goal",
        "progress_signals",
        "phase_gate",
        "no_action_trigger",
    }
)
_DATA_POLICY = {
    "canonical_authority": "private_workspace_repository",
    "railway_role": "authenticated_bounded_workspace_goal_projection",
    "private_bodies_included": False,
    "projection_is_write_authority": False,
}


class OpsWorkspaceGoalProjectionError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_project_entries() -> tuple[dict[str, Any], ...]:
    entries = tuple(
        dict(entry)
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace"
        and entry.get("portfolio_visible") is True
        and str(entry.get("status") or "")
        in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
        and str(entry.get("key") or "").strip()
        and str(entry.get("key") or "").strip() != WORKSPACE_KEY
    )
    keys = [str(entry["key"]) for entry in entries]
    if not entries or len(entries) > MAX_WORKSPACES or len(keys) != len(set(keys)):
        raise OpsWorkspaceGoalProjectionError(
            "The canonical active workspace registry is unavailable or malformed."
        )
    return entries


def _parse_utc(value: Any, *, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw or len(raw) > 100:
        raise OpsWorkspaceGoalProjectionError(f"{field} is missing or invalid")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpsWorkspaceGoalProjectionError(f"{field} is missing or invalid") from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
    ):
        raise OpsWorkspaceGoalProjectionError(f"{field} must use ai_clone_utc")
    return parsed.astimezone(timezone.utc)


def _project_goal(workspace_key: str, value: Any) -> dict[str, Any]:
    try:
        contract = _validated_goal_contract(workspace_key, value)
    except ValueError as exc:
        raise OpsWorkspaceGoalProjectionError(
            f"The canonical goal contract for {workspace_key} is unavailable or invalid."
        ) from exc
    return {
        "schema_version": contract["schema_version"],
        "goal": contract["goal"],
        "progress_signals": list(contract["progress_signals"]),
        "phase_gate": contract["phase_gate"],
        "no_action_trigger": contract["no_action_trigger"],
    }


def _contracts_sha256(workspaces: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            workspaces,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def build_ops_workspace_goal_projection() -> dict[str, Any]:
    entries = _active_project_entries()
    authority_states = {
        str(entry.get("goal_contract_status") or "") for entry in entries
    }
    observed_values = {
        str(entry.get("goal_contract_observed_at") or "").strip()
        for entry in entries
    }
    authority_hashes = {
        str(entry.get("goal_contract_authority_sha256") or "").strip()
        for entry in entries
    }
    if authority_states != {"available_private_authority"}:
        raise OpsWorkspaceGoalProjectionError(
            "The private workspace-goal authority is unavailable or invalid."
        )
    if len(observed_values) != 1 or len(authority_hashes) != 1:
        raise OpsWorkspaceGoalProjectionError(
            "The workspace-goal authority receipt is inconsistent."
        )
    observed_at = next(iter(observed_values))
    authority_sha256 = next(iter(authority_hashes))
    _parse_utc(observed_at, field="observed_at")
    if re.fullmatch(r"[0-9a-f]{64}", authority_sha256) is None:
        raise OpsWorkspaceGoalProjectionError(
            "The workspace-goal authority digest is invalid."
        )

    workspaces = [
        {
            "workspace_key": str(entry["key"]),
            "display_name": str(
                entry.get("portfolio_label")
                or entry.get("display_name")
                or entry["key"]
            ).strip(),
            "goal": _project_goal(str(entry["key"]), entry.get("goal_contract")),
        }
        for entry in entries
    ]
    projection = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _now_iso(),
        "observed_at": observed_at,
        "clock": {
            "schema_version": CLOCK_SCHEMA_VERSION,
            "authority": CLOCK_AUTHORITY,
            "timezone": "UTC",
            "observed_at": observed_at,
        },
        "state": "ready",
        "reason_codes": [],
        "authority_sha256": authority_sha256,
        "projected_contracts_sha256": _contracts_sha256(workspaces),
        "workspaces": workspaces,
        "data_policy": dict(_DATA_POLICY),
    }
    return validate_ops_workspace_goal_projection(projection)


def unavailable_ops_workspace_goal_projection(reason: str) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _now_iso(),
        "observed_at": None,
        "clock": None,
        "state": "unavailable",
        "reason_codes": [str(reason or "projection_unavailable")[:200]],
        "authority_sha256": None,
        "projected_contracts_sha256": None,
        "workspaces": [],
        "data_policy": dict(_DATA_POLICY),
    }


def validate_ops_workspace_goal_projection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != PROJECTION_SCHEMA:
        raise OpsWorkspaceGoalProjectionError("invalid workspace-goal projection schema")
    if set(payload) != _PROJECTION_FIELDS:
        raise OpsWorkspaceGoalProjectionError("invalid workspace-goal projection envelope")
    _parse_utc(payload.get("generated_at"), field="generated_at")
    state = payload.get("state")
    reason_codes = payload.get("reason_codes")
    if (
        state not in {"ready", "unavailable"}
        or not isinstance(reason_codes, list)
        or len(reason_codes) > 20
        or any(
            not isinstance(item, str)
            or not item.strip()
            or len(item) > 200
            for item in reason_codes
        )
        or (state == "ready" and reason_codes)
        or (state == "unavailable" and not reason_codes)
    ):
        raise OpsWorkspaceGoalProjectionError("invalid workspace-goal projection state")
    if payload.get("data_policy") != _DATA_POLICY:
        raise OpsWorkspaceGoalProjectionError("invalid workspace-goal projection data policy")

    workspaces = payload.get("workspaces")
    if not isinstance(workspaces, list) or len(workspaces) > MAX_WORKSPACES:
        raise OpsWorkspaceGoalProjectionError("invalid projected workspace goals")
    if state == "unavailable":
        if (
            payload.get("observed_at") is not None
            or payload.get("clock") is not None
            or payload.get("authority_sha256") is not None
            or payload.get("projected_contracts_sha256") is not None
            or workspaces
        ):
            raise OpsWorkspaceGoalProjectionError(
                "unavailable workspace-goal projection cannot claim authority"
            )
    else:
        observed_at = str(payload.get("observed_at") or "")
        _parse_utc(observed_at, field="observed_at")
        clock = payload.get("clock")
        if not isinstance(clock, dict) or clock != {
            "schema_version": CLOCK_SCHEMA_VERSION,
            "authority": CLOCK_AUTHORITY,
            "timezone": "UTC",
            "observed_at": observed_at,
        }:
            raise OpsWorkspaceGoalProjectionError(
                "invalid workspace-goal projection clock"
            )
        authority_sha256 = payload.get("authority_sha256")
        projected_sha256 = payload.get("projected_contracts_sha256")
        if (
            not isinstance(authority_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", authority_sha256) is None
            or not isinstance(projected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", projected_sha256) is None
        ):
            raise OpsWorkspaceGoalProjectionError(
                "invalid workspace-goal projection digest"
            )

        expected_entries = _active_project_entries()
        expected_keys = [str(entry["key"]) for entry in expected_entries]
        projected_keys: list[str] = []
        for item in workspaces:
            if not isinstance(item, dict) or set(item) != _WORKSPACE_FIELDS:
                raise OpsWorkspaceGoalProjectionError(
                    "invalid projected workspace-goal item"
                )
            workspace_key = item.get("workspace_key")
            display_name = item.get("display_name")
            goal = item.get("goal")
            if (
                not isinstance(workspace_key, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", workspace_key)
                or not isinstance(display_name, str)
                or not display_name.strip()
                or len(display_name) > 120
                or not isinstance(goal, dict)
                or set(goal) != _GOAL_FIELDS
                or goal.get("schema_version") != "workspace_goal_contract/v1"
                or not isinstance(goal.get("goal"), str)
                or not str(goal["goal"]).strip()
                or len(goal["goal"]) > 2000
                or not isinstance(goal.get("phase_gate"), str)
                or not str(goal["phase_gate"]).strip()
                or len(goal["phase_gate"]) > 2000
                or not isinstance(goal.get("no_action_trigger"), str)
                or not str(goal["no_action_trigger"]).strip()
                or len(goal["no_action_trigger"]) > 2000
                or not isinstance(goal.get("progress_signals"), list)
                or not goal["progress_signals"]
                or len(goal["progress_signals"]) > 20
                or any(
                    not isinstance(signal, str)
                    or not signal.strip()
                    or len(signal) > 500
                    for signal in goal["progress_signals"]
                )
            ):
                raise OpsWorkspaceGoalProjectionError(
                    "invalid projected workspace-goal item"
                )
            projected_keys.append(workspace_key)
        if projected_keys != expected_keys or len(projected_keys) != len(
            set(projected_keys)
        ):
            raise OpsWorkspaceGoalProjectionError(
                "workspace-goal projection must cover the exact active project portfolio"
            )
        if projected_sha256 != _contracts_sha256(workspaces):
            raise OpsWorkspaceGoalProjectionError(
                "workspace-goal projection digest mismatch"
            )

    try:
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OpsWorkspaceGoalProjectionError(
            "workspace-goal projection is not bounded JSON"
        ) from exc
    if (
        len(serialized.encode("utf-8")) > MAX_BYTES
        or contains_private_filesystem_reference(serialized)
        or sanitize_brain_text(serialized) != serialized
    ):
        raise OpsWorkspaceGoalProjectionError(
            "workspace-goal projection contains private or oversized material"
        )
    return payload


def ops_workspace_goal_projection_semantic_sha256(payload: dict[str, Any]) -> str:
    semantic = json.loads(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    semantic.pop("generated_at", None)
    return hashlib.sha256(
        json.dumps(
            semantic,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
