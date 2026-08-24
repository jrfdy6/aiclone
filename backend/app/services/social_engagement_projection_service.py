from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from app.services.social_engagement_assist_service import (
    ALLOWED_ASSISTED_ACTIONS,
    PROHIBITED_PLATFORM_MUTATIONS,
    SocialEngagementAssistError,
    SocialEngagementAssistService,
    canonical_native_surface_url,
    default_social_engagement_assist_service,
)


PROJECTION_SCHEMA = "social_engagement_assist_projection/v1"
SYNC_SCHEMA = "social_engagement_assist_projection_sync/v1"
WORKSPACE_KEY = "linkedin-content-os"
SNAPSHOT_TYPE = "social_engagement_assist"
MAX_PROJECTION_BYTES = 512 * 1024
MAX_PROJECTION_ITEMS = 25

_ITEM_FIELDS = frozenset(
    {
        "opportunity_id",
        "event_id",
        "source_id",
        "discovery_id",
        "source_event_id",
        "source_gate_event_id",
        "evidence_id",
        "interpretation_id",
        "platform",
        "source_url",
        "source_title",
        "source_author",
        "visible_text",
        "visible_text_sha256",
        "draft_text",
        "draft_sha256",
        "engagement_type",
        "status",
        "created_at",
        "owner_execution_required",
        "external_mutation_performed",
        "provenance",
        "allowed_actions",
        "prohibited_backend_actions",
    }
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def projection_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _parse_utc(value: Any, *, label: str) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 64:
        raise SocialEngagementAssistError(f"{label} is missing or invalid")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SocialEngagementAssistError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SocialEngagementAssistError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _project_opportunity(value: Mapping[str, Any]) -> dict[str, Any]:
    provenance = dict(value.get("provenance") or {})
    return {
        key: value.get(key)
        for key in _ITEM_FIELDS
        if key not in {"provenance", "allowed_actions", "prohibited_backend_actions"}
    } | {
        "provenance": {
            "capture_method": provenance.get("capture_method"),
            "access_context": provenance.get("access_context"),
            "canonical_intake_adapter": provenance.get("canonical_intake_adapter"),
            "canonical_source_event_id": provenance.get("canonical_source_event_id"),
            "discovery_origin": provenance.get("discovery_origin"),
            "discovery_route": provenance.get("discovery_route"),
            "external_source_url": provenance.get("external_source_url"),
            "no_scraping": provenance.get("no_scraping"),
            "social_platform_api_called": provenance.get("social_platform_api_called"),
        },
        "allowed_actions": sorted(ALLOWED_ASSISTED_ACTIONS),
        "prohibited_backend_actions": sorted(PROHIBITED_PLATFORM_MUTATIONS),
    }


def validate_social_engagement_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SocialEngagementAssistError("social engagement projection must be an object")
    expected_top = {
        "schema_version",
        "generated_at",
        "authority",
        "state",
        "counts",
        "opportunities",
    }
    if set(value) != expected_top:
        raise SocialEngagementAssistError("social engagement projection fields are invalid")
    if value.get("schema_version") != PROJECTION_SCHEMA or value.get("authority") != "local_sql":
        raise SocialEngagementAssistError("social engagement projection authority is invalid")
    generated_at = _parse_utc(value.get("generated_at"), label="projection generated_at")
    state = str(value.get("state") or "")
    if state not in {"ready", "empty"}:
        raise SocialEngagementAssistError("social engagement projection state is invalid")
    raw_items = value.get("opportunities")
    if not isinstance(raw_items, list) or len(raw_items) > MAX_PROJECTION_ITEMS:
        raise SocialEngagementAssistError("social engagement projection opportunities are invalid")
    counts = value.get("counts")
    if not isinstance(counts, dict) or set(counts) != {"opportunities"} or counts.get("opportunities") != len(raw_items):
        raise SocialEngagementAssistError("social engagement projection counts are invalid")
    if (state == "empty") != (len(raw_items) == 0):
        raise SocialEngagementAssistError("social engagement projection state does not match its items")

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict) or set(raw) != _ITEM_FIELDS:
            raise SocialEngagementAssistError("social engagement projection item fields are invalid")
        item = dict(raw)
        opportunity_id = str(item.get("opportunity_id") or "").strip()
        if not opportunity_id or len(opportunity_id) > 128 or opportunity_id in seen_ids:
            raise SocialEngagementAssistError("social engagement projection opportunity identity is invalid")
        seen_ids.add(opportunity_id)
        platform = str(item.get("platform") or "").strip().lower()
        item["source_url"] = canonical_native_surface_url(platform, item.get("source_url"))
        visible_text = str(item.get("visible_text") or "")
        draft_text = str(item.get("draft_text") or "")
        if not visible_text.strip() or not draft_text.strip():
            raise SocialEngagementAssistError("social engagement projection text is missing")
        if hashlib.sha256(visible_text.encode("utf-8")).hexdigest() != item.get("visible_text_sha256"):
            raise SocialEngagementAssistError("social engagement projection visible text failed integrity verification")
        if hashlib.sha256(draft_text.encode("utf-8")).hexdigest() != item.get("draft_sha256"):
            raise SocialEngagementAssistError("social engagement projection draft failed integrity verification")
        if item.get("owner_execution_required") is not True or item.get("external_mutation_performed") is not False:
            raise SocialEngagementAssistError("social engagement projection owner boundary is invalid")
        if item.get("status") != "draft_ready" or item.get("engagement_type") not in {"comment", "message", "post"}:
            raise SocialEngagementAssistError("social engagement projection lifecycle is invalid")
        if item.get("allowed_actions") != sorted(ALLOWED_ASSISTED_ACTIONS):
            raise SocialEngagementAssistError("social engagement projection allowed actions are invalid")
        if item.get("prohibited_backend_actions") != sorted(PROHIBITED_PLATFORM_MUTATIONS):
            raise SocialEngagementAssistError("social engagement projection prohibited actions are invalid")
        provenance = item.get("provenance")
        if (
            not isinstance(provenance, dict)
            or provenance.get("no_scraping") is not True
            or provenance.get("social_platform_api_called") is not False
            or provenance.get("external_source_url") != item["source_url"]
        ):
            raise SocialEngagementAssistError("social engagement projection provenance is invalid")
        item["created_at"] = _parse_utc(item.get("created_at"), label="opportunity created_at")
        items.append(item)

    normalized = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": generated_at,
        "authority": "local_sql",
        "state": state,
        "counts": {"opportunities": len(items)},
        "opportunities": items,
    }
    if len(_canonical_json(normalized)) > MAX_PROJECTION_BYTES:
        raise SocialEngagementAssistError("social engagement projection exceeds the 512 KB limit")
    return normalized


def build_social_engagement_projection(
    *,
    service: SocialEngagementAssistService | None = None,
    limit: int = MAX_PROJECTION_ITEMS,
) -> dict[str, Any]:
    canonical = service or default_social_engagement_assist_service()
    projected: list[dict[str, Any]] = []
    for opportunity in canonical.list_opportunities(limit=max(1, min(int(limit), MAX_PROJECTION_ITEMS))):
        item = _project_opportunity(opportunity)
        candidate = {
            "schema_version": PROJECTION_SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "authority": "local_sql",
            "state": "ready",
            "counts": {"opportunities": len(projected) + 1},
            "opportunities": [*projected, item],
        }
        if len(_canonical_json(candidate)) > MAX_PROJECTION_BYTES:
            break
        projected.append(item)
    projection = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": "local_sql",
        "state": "ready" if projected else "empty",
        "counts": {"opportunities": len(projected)},
        "opportunities": projected,
    }
    return validate_social_engagement_projection(projection)
