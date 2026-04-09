from __future__ import annotations

import hashlib
import json
from typing import Any


def build_pm_trigger_key(*, title: str, workspace_key: str, source: str | None, payload: dict[str, Any]) -> str:
    execution = dict(payload.get("execution") or {})
    normalized = {
        "title": str(title or "").strip(),
        "workspace_key": str(workspace_key or "").strip() or "shared_ops",
        "source": str(source or "").strip(),
        "reason": _payload_value(payload, "reason"),
        "instructions": _normalize_string_list(payload.get("instructions")),
        "acceptance_criteria": _normalize_string_list(payload.get("acceptance_criteria")),
        "artifacts_expected": _normalize_string_list(payload.get("artifacts_expected")),
        "execution": {
            "manager_agent": _payload_value(execution, "manager_agent"),
            "target_agent": _payload_value(execution, "target_agent"),
            "workspace_agent": _payload_value(execution, "workspace_agent"),
            "execution_mode": _payload_value(execution, "execution_mode"),
            "lane": _payload_value(execution, "lane"),
        },
    }
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"openclaw:{digest[:24]}"


def build_content_job_idempotency_key(payload: dict[str, Any]) -> str:
    normalized = {
        "workspace_slug": str(payload.get("workspace_slug") or "linkedin-content-os"),
        "user_id": str(payload.get("user_id") or ""),
        "topic": str(payload.get("topic") or ""),
        "context": str(payload.get("context") or ""),
        "content_type": str(payload.get("content_type") or "linkedin_post"),
        "category": str(payload.get("category") or "value"),
        "tone": str(payload.get("tone") or "expert_direct"),
        "audience": str(payload.get("audience") or "tech_ai"),
        "source_mode": str(payload.get("source_mode") or "persona_only"),
    }
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _payload_value(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
