from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.content_lifecycle_service import (
    ContentLifecycleService,
    PrivateContentArtifactStore,
)
from app.services.integrated_controller_readiness_service import (
    CONTROLLER_QUEUE_UNAVAILABLE,
    READINESS_MESSAGES,
    integrated_controller_queue_readiness,
)
from app.services.integrated_system_store import IntegratedSystemStore, default_database_path
from app.services.integrated_variant_generation_service import (
    project_variant_generation_eligibility,
    validate_variant_generation_eligibility,
)
from app.services.source_sharing_policy_service import (
    credential_free_public_url,
    source_remote_sharing,
)


PROJECTION_SCHEMA = "integrated_content_portfolio/v1"
SNAPSHOT_TYPE = "integrated_content_portfolio"
WORKSPACE_KEY = "feezie-os"
MAX_OPPORTUNITIES = 50
MAX_SOURCES = 50
MAX_POSTS = 25
MAX_REVISIONS_PER_POST = 20
MAX_BODY_BYTES = 40_000
MAX_DISCOVERIES_PER_SOURCE = 12
MAX_EVIDENCE_PER_SOURCE = 6
MAX_INTERPRETATIONS_PER_EVIDENCE = 8
MAX_MERGED_ALIASES_PER_SOURCE = 12
MAX_LEARNING_EVENTS_PER_POST = 20
MAX_PERSONA_ITEMS_PER_POST = 12
MAX_DECISION_ITEMS_PER_POST = 12
MAX_SUMMARY_ITEMS = 50
MAX_EVIDENCE_EXCERPT_CHARS = 480
MAX_EVIDENCE_ARTIFACT_BYTES = 2 * 1024 * 1024
INTERPRETATION_PROVENANCE_KINDS = frozenset(
    {"independent_agent", "deterministic_policy", "synthesized_lens"}
)

_PRIVATE_TEXT_TOKENS = (
    "/Users/",
    "/home/",
    "file://",
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
)
_CONTROL_OPTIONS: dict[str, dict[str, Any]] = {
    "hook": {
        "label": "Hook",
        "values": ["direct", "question", "story", "contrarian"],
        "default": "direct",
    },
    "length": {
        "label": "Length",
        "values": ["short", "medium", "long"],
        "default": "medium",
    },
    "tone": {
        "label": "Tone",
        "values": ["measured", "direct", "reflective"],
        "default": "measured",
    },
    "audience_emphasis": {
        "label": "Audience emphasis",
        "values": ["AI systems operators", "education and operations leaders", "technology hiring managers"],
        "default": "",
    },
    "value_emphasis": {
        "label": "Value emphasis",
        "values": ["practical application", "human consequence", "systems lesson"],
        "default": "",
    },
    "story_emphasis": {
        "label": "Story emphasis",
        "values": ["lived moment", "operating tension", "lesson payoff"],
        "default": "",
    },
    "evidence_emphasis": {
        "label": "Evidence emphasis",
        "values": ["source claim", "supporting proof", "attribution"],
        "default": "",
    },
    "call_to_action": {
        "label": "Call to action",
        "values": ["invite discussion", "ask for examples", "invite collaboration"],
        "default": "",
    },
}
_IMPLEMENTED_CONTROLLER_CAPABILITIES = {
    "owner_requested_post": True,
    "portfolio_selected_drafting": True,
    "variant_generation": True,
    "variant_selection": True,
    "variant_rejection": True,
    "manual_edit_classification": True,
    "owner_approval": True,
    "publication_confirmation": True,
    "persona_promotion": True,
    "persona_reversal": True,
    "decision_resolution": True,
}
_QUEUE_BACKED_CONTROLLER_CAPABILITIES = frozenset(
    {
        "owner_requested_post",
        "variant_generation",
        "variant_selection",
        "variant_rejection",
        "manual_edit_classification",
        "owner_approval",
        "publication_confirmation",
        "persona_reversal",
        "decision_resolution",
    }
)
_QUEUE_SAFE_BEHAVIOR = (
    "The owner action remains disabled until the signed local-action queue is ready."
)
_PROJECTION_SAFE_BEHAVIOR = (
    "Owner actions remain disabled until a valid current projection is available."
)
_CONTROLLER_REASON_CODES = frozenset({*READINESS_MESSAGES, "projection_unavailable"})


class IntegratedContentProjectionError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_artifact_root(database_path: Path | str | None = None) -> Path:
    database = Path(database_path or default_database_path()).expanduser().resolve()
    return database.parent / "artifacts"


def _controller_fields(
    *,
    readiness: dict[str, Any] | None = None,
    projection_available: bool = True,
) -> tuple[dict[str, bool], list[dict[str, str]]]:
    capabilities = dict(_IMPLEMENTED_CONTROLLER_CAPABILITIES)
    if not projection_available:
        capabilities = {key: False for key in capabilities}
        return capabilities, [
            {
                "capability": key,
                "reason_code": "projection_unavailable",
                "safe_behavior": _PROJECTION_SAFE_BEHAVIOR,
            }
            for key in capabilities
        ]

    current = readiness or integrated_controller_queue_readiness()
    if current.get("ready") is True:
        return capabilities, []
    reason_code = str(current.get("reason_code") or "")
    if reason_code not in READINESS_MESSAGES:
        reason_code = CONTROLLER_QUEUE_UNAVAILABLE
    for key in _QUEUE_BACKED_CONTROLLER_CAPABILITIES:
        capabilities[key] = False
    return capabilities, [
        {
            "capability": key,
            "reason_code": reason_code,
            "safe_behavior": _QUEUE_SAFE_BEHAVIOR,
        }
        for key in sorted(_QUEUE_BACKED_CONTROLLER_CAPABILITIES)
    ]


def _project_controller_health(
    *,
    state: str,
    reason_codes: list[str],
    controller_gaps: list[dict[str, str]],
    counts: dict[str, Any],
) -> tuple[str, list[str]]:
    """Keep readable data available while making an unavailable write path explicit."""

    retained = [code for code in reason_codes if code not in _CONTROLLER_REASON_CODES]
    current = sorted({
        str(gap.get("reason_code") or CONTROLLER_QUEUE_UNAVAILABLE)
        for gap in controller_gaps
    })
    projected_reasons = list(dict.fromkeys([*retained, *current]))
    if controller_gaps:
        return ("error" if state == "error" else "degraded"), projected_reasons
    if state == "degraded" and not retained:
        has_data = any(int(counts.get(key) or 0) > 0 for key in ("sources", "opportunities", "posts"))
        return ("ready" if has_data else "empty"), []
    return state, projected_reasons


def apply_current_controller_readiness(
    payload: dict[str, Any],
    *,
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replace snapshot-time queue claims with current backend runtime truth."""

    capabilities, gaps = _controller_fields(readiness=readiness)
    state, reason_codes = _project_controller_health(
        state=str(payload.get("state") or "degraded"),
        reason_codes=[str(code) for code in payload.get("reason_codes", [])],
        controller_gaps=gaps,
        counts=payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
    )
    projected = {
        **payload,
        "state": state,
        "reason_codes": reason_codes,
        "controller_capabilities": capabilities,
        "controller_gaps": gaps,
    }
    return validate_integrated_content_projection(projected)


def _safe_public_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return credential_free_public_url(text)
    except ValueError:
        return None


def _bounded_text(value: Any, *, limit: int = 600) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    if not text or any(token.lower() in text.lower() for token in _PRIVATE_TEXT_TOKENS):
        return None
    return text[:limit]


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _bounded_scalar_object(value: Any, *, max_items: int = 8) -> dict[str, Any]:
    """Project a closed, shallow owner-review summary from structured SQL JSON."""

    result: dict[str, Any] = {}
    for raw_key, raw_value in _json_object(value).items():
        key = str(raw_key)
        if key in {"private_notes", "raw_body", "transcript", "local_path", "absolute_path", "payload"}:
            continue
        if isinstance(raw_value, bool) or raw_value is None:
            result[key[:80]] = raw_value
        elif isinstance(raw_value, (int, float)):
            result[key[:80]] = raw_value
        elif isinstance(raw_value, str):
            safe = _bounded_text(raw_value, limit=500)
            if safe is not None:
                result[key[:80]] = safe
        elif isinstance(raw_value, list):
            safe_items = [
                safe
                for item in raw_value[:8]
                if (safe := _bounded_text(item, limit=200)) is not None
            ]
            if safe_items:
                result[key[:80]] = safe_items
        if len(result) >= max_items:
            break
    return result


def _merged_source_aliases(value: Any) -> list[dict[str, Any]]:
    aliases = _json_object(value).get("merged_source_aliases")
    if not isinstance(aliases, list):
        return []
    projected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in aliases:
        if not isinstance(raw, dict):
            continue
        source_id = _bounded_text(raw.get("source_id"), limit=128)
        source_kind = _bounded_text(raw.get("source_kind"), limit=120)
        if not source_id or not source_kind or source_id in seen:
            continue
        seen.add(source_id)
        projected.append(
            {
                "source_id": source_id,
                "source_kind": source_kind,
                "canonical_url": _safe_public_url(raw.get("canonical_url")),
            }
        )
        if len(projected) >= MAX_MERGED_ALIASES_PER_SOURCE:
            break
    return projected


def _read_verified_artifact_text(root: Path, artifact: Any, cache: dict[str, str | None]) -> str | None:
    artifact_id = str(artifact["artifact_id"])
    if artifact_id in cache:
        return cache[artifact_id]
    try:
        target = (root / str(artifact["logical_ref"])).resolve()
        target.relative_to(root.resolve())
        if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_EVIDENCE_ARTIFACT_BYTES:
            cache[artifact_id] = None
            return None
        body = target.read_bytes()
        if hashlib.sha256(body).hexdigest() != artifact["content_sha256"]:
            cache[artifact_id] = None
            return None
        text = body.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        text = None
    cache[artifact_id] = text
    return text


def _evidence_reference(raw: Any, *, artifact_text: str | None, allow_excerpt: bool) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = _bounded_text(raw.get("kind") or "reference", limit=80) or "reference"
    projected: dict[str, Any] = {"kind": kind}
    start = raw.get("start")
    end = raw.get("end")
    if isinstance(start, int) and start >= 0:
        projected["start"] = start
    if isinstance(end, int) and end >= 0 and (not isinstance(start, int) or end >= start):
        projected["end"] = end
    excerpt = None
    if allow_excerpt:
        for key in ("excerpt", "quote", "text"):
            excerpt = _bounded_text(raw.get(key), limit=MAX_EVIDENCE_EXCERPT_CHARS)
            if excerpt:
                break
        if excerpt is None and artifact_text is not None and isinstance(start, int) and isinstance(end, int):
            excerpt = _bounded_text(artifact_text[start:end], limit=MAX_EVIDENCE_EXCERPT_CHARS)
    projected["excerpt"] = excerpt
    public_url = _safe_public_url(raw.get("url") or raw.get("source_url"))
    if public_url:
        projected["source_url"] = public_url
    return projected


def _variant_control_options(
    *,
    source_kinds: set[str],
    evidence_count: int,
    interpretation_lenses: set[str],
    opportunity_metadata: dict[str, Any],
    existing_controls: set[str],
) -> list[dict[str, Any]]:
    keys = ["hook", "length", "tone", "audience_emphasis", "value_emphasis"]
    if source_kinds & {"video", "podcast", "long_form", "manual"} or any(
        "story" in lens or "experience" in lens for lens in interpretation_lenses
    ):
        keys.append("story_emphasis")
    if evidence_count > 0:
        keys.append("evidence_emphasis")
    intent = str(opportunity_metadata.get("intent") or "").strip().lower()
    if intent in {"invitation", "call_to_action", "cta"} or "call_to_action" in existing_controls:
        keys.append("call_to_action")
    return [{"key": key, **_CONTROL_OPTIONS[key]} for key in keys]


def _event_summary(row: Any) -> dict[str, Any]:
    payload = _bounded_scalar_object(row["payload_json"], max_items=6)
    public_url = _safe_public_url(payload.get("public_url"))
    if "public_url" in payload:
        if public_url:
            payload["public_url"] = public_url
        else:
            payload.pop("public_url", None)
    return {
        "learning_event_id": row["learning_event_id"],
        "revision_id": row["revision_id"],
        "event_kind": row["event_kind"],
        "edit_classification": row["edit_classification"],
        "occurred_at": row["occurred_at"],
        "summary": payload,
    }


def _decision_summary(row: Any, links: list[dict[str, str]]) -> dict[str, Any]:
    payload = _json_object(row["payload_json"])
    safe_links = [
        {"surface": str(link.get("surface") or "")[:100], "external_ref": str(link.get("external_ref") or "")[:300]}
        for link in links
        if str(link.get("surface") or "").strip()
        and str(link.get("external_ref") or "").strip()
        and not any(token in str(link.get("external_ref") or "") for token in _PRIVATE_TEXT_TOKENS)
    ][:12]
    route = str(payload.get("route") or "ops").strip().lower()
    if route not in {
        "ops", "workspace", "content", "feezie-os", "fusion-os",
        "easyoutfitapp", "ai-swag-store", "agc", "work-life-tools",
    }:
        route = "ops"
    interaction_mode = "complex" if payload.get("interaction_mode") == "complex" else "simple"
    session_ref = next(
        (
            link["external_ref"]
            for link in safe_links
            if link.get("surface") == "decision_session" and link.get("external_ref")
        ),
        None,
    )
    safe_resolution: dict[str, Any] = {}
    raw_resolution = payload.get("resolution")
    if isinstance(raw_resolution, dict):
        for raw_key, raw_value in list(raw_resolution.items())[:12]:
            key = _bounded_text(raw_key, limit=120)
            if not key or any(token in key.lower() for token in ("private", "path", "transcript", "raw_body")):
                continue
            if isinstance(raw_value, bool) or isinstance(raw_value, (int, float)) or raw_value is None:
                safe_resolution[key] = raw_value
                continue
            value = _bounded_text(raw_value, limit=1_000)
            if value and not any(token in value for token in _PRIVATE_TEXT_TOKENS):
                safe_resolution[key] = value
    return {
        "decision_id": row["decision_id"],
        "decision_type": row["decision_type"],
        "status": row["status"],
        "title": _bounded_text(row["title"], limit=300) or "Untitled decision",
        "state_version": row["state_version"],
        "interaction_mode": interaction_mode,
        "route": route,
        "resolution": safe_resolution,
        "session_ref": (
            _bounded_text(session_ref, limit=300)
            if session_ref and not any(token in session_ref for token in _PRIVATE_TEXT_TOKENS)
            else None
        ),
        "updated_at": row["updated_at"],
        "links": safe_links,
    }


def _persona_summary(connection: Any, row: Any) -> dict[str, Any]:
    evidence = connection.execute(
        """SELECT post_id,revision_id,source_id,context_key,owner_approved,publication_confirmed
        FROM persona_candidate_evidence WHERE persona_candidate_id=? ORDER BY context_key""",
        (row["persona_candidate_id"],),
    ).fetchall()
    qualifying = []
    for item in evidence:
        event_kinds = {
            event["event_kind"]
            for event in connection.execute(
                """SELECT event_kind FROM learning_events
                WHERE post_id=? AND revision_id=?
                AND event_kind IN ('owner_approved','publication_confirmed')""",
                (item["post_id"], item["revision_id"]),
            )
        }
        published_current_revision = bool(
            connection.execute(
                """SELECT 1 FROM canonical_posts
                WHERE post_id=? AND status='published' AND current_revision_id=?""",
                (item["post_id"], item["revision_id"]),
            ).fetchone()
        )
        if {"owner_approved", "publication_confirmed"}.issubset(event_kinds) and published_current_revision:
            qualifying.append(item)
    qualifying_posts = {item["post_id"] for item in qualifying if item["post_id"]}
    independent_contexts = {item["source_id"] or f"context:{item['context_key']}" for item in qualifying}
    promotion = connection.execute(
        """SELECT promotion_id,canon_version,promotion_rule,promoted_at,reversed_at
        FROM persona_promotions WHERE persona_candidate_id=?
        ORDER BY promoted_at DESC,promotion_id DESC LIMIT 1""",
        (row["persona_candidate_id"],),
    ).fetchone()
    return {
        "persona_candidate_id": row["persona_candidate_id"],
        "candidate_kind": row["candidate_kind"],
        "status": row["status"],
        "claim": _bounded_scalar_object(row["claim_json"], max_items=6),
        "evidence_count": len(evidence),
        "qualifying_post_count": len(qualifying_posts),
        "independent_context_count": len(independent_contexts),
        "automatic_promotion_eligible": (
            row["candidate_kind"] == "reversible_pattern"
            and row["status"] in {"pending", "blocked"}
            and len(qualifying_posts) >= 3
            and len(independent_contexts) >= 2
        ),
        "lifecycle_authority": "canonical_content_learning_events/v1",
        "promotion": {
            "promotion_id": promotion["promotion_id"],
            "canon_version": promotion["canon_version"],
            "promotion_rule": promotion["promotion_rule"],
            "promoted_at": promotion["promoted_at"],
            "reversed_at": promotion["reversed_at"],
        } if promotion else None,
        "updated_at": row["updated_at"],
    }


def _validate_persona_projection(items: Any, *, limit: int) -> None:
    fields = {
        "persona_candidate_id", "candidate_kind", "status", "claim", "evidence_count",
        "qualifying_post_count", "independent_context_count", "automatic_promotion_eligible",
        "lifecycle_authority", "promotion", "updated_at",
    }
    promotion_fields = {
        "promotion_id", "canon_version", "promotion_rule", "promoted_at", "reversed_at",
    }
    if not isinstance(items, list) or len(items) > limit:
        raise IntegratedContentProjectionError("invalid persona summary projection")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != fields:
            raise IntegratedContentProjectionError("invalid persona summary projection")
        candidate_id = item.get("persona_candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id or len(candidate_id) > 128 or candidate_id in seen:
            raise IntegratedContentProjectionError("invalid persona candidate identity")
        seen.add(candidate_id)
        if not isinstance(item.get("claim"), dict) or len(item["claim"]) > 6:
            raise IntegratedContentProjectionError("invalid persona claim projection")
        promotion = item.get("promotion")
        if promotion is not None:
            if not isinstance(promotion, dict) or set(promotion) != promotion_fields:
                raise IntegratedContentProjectionError("invalid persona promotion projection")
            if any(
                not isinstance(promotion.get(key), str) or not promotion[key] or len(promotion[key]) > 256
                for key in ("promotion_id", "canon_version", "promotion_rule", "promoted_at")
            ):
                raise IntegratedContentProjectionError("invalid persona promotion binding")
            reversed_at = promotion.get("reversed_at")
            if reversed_at is not None and (not isinstance(reversed_at, str) or not reversed_at or len(reversed_at) > 64):
                raise IntegratedContentProjectionError("invalid persona reversal timestamp")


def _validate_decision_projection(items: Any, *, limit: int) -> None:
    fields = {
        "decision_id", "decision_type", "status", "title", "state_version", "interaction_mode",
        "route", "resolution", "session_ref", "updated_at", "links",
    }
    if not isinstance(items, list) or len(items) > limit:
        raise IntegratedContentProjectionError("invalid decision summary projection")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != fields:
            raise IntegratedContentProjectionError("invalid decision summary projection")
        decision_id = item.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id or len(decision_id) > 128 or decision_id in seen:
            raise IntegratedContentProjectionError("invalid decision identity projection")
        seen.add(decision_id)
        if (
            item.get("status") not in {"open", "in_session", "resolved", "superseded", "canceled", "blocked"}
            or item.get("interaction_mode") not in {"simple", "complex"}
            or item.get("route") not in {
                "ops", "workspace", "content", "feezie-os", "fusion-os",
                "easyoutfitapp", "ai-swag-store", "agc", "work-life-tools",
            }
            or not isinstance(item.get("state_version"), int)
            or isinstance(item.get("state_version"), bool)
            or item["state_version"] < 1
            or not isinstance(item.get("resolution"), dict)
            or len(item["resolution"]) > 12
            or not isinstance(item.get("links"), list)
            or len(item["links"]) > 12
        ):
            raise IntegratedContentProjectionError("invalid decision lifecycle projection")
        if any(
            not isinstance(link, dict)
            or set(link) != {"surface", "external_ref"}
            or not str(link.get("surface") or "").strip()
            or not str(link.get("external_ref") or "").strip()
            for link in item["links"]
        ):
            raise IntegratedContentProjectionError("invalid decision link projection")


def _source_lineage_reference(connection: Any, source_id: str) -> dict[str, Any]:
    source = connection.execute(
        "SELECT source_kind FROM sources WHERE source_id=?",
        (source_id,),
    ).fetchone()
    evidence = connection.execute(
        """SELECT evidence_id FROM evidence_records WHERE source_id=?
        ORDER BY created_at DESC,evidence_id LIMIT ?""",
        (source_id, MAX_EVIDENCE_PER_SOURCE),
    ).fetchall()
    evidence_ids = [item["evidence_id"] for item in evidence]
    interpretations = []
    for evidence_id in evidence_ids:
        interpretations.extend(
            connection.execute(
                """SELECT interpretation_id,lens_name FROM interpretations WHERE evidence_id=?
                ORDER BY created_at,interpretation_id LIMIT ?""",
                (evidence_id, MAX_INTERPRETATIONS_PER_EVIDENCE),
            ).fetchall()
        )
    return {
        "source_kind": source["source_kind"] if source else "unknown",
        "discovery_ids": [
            item["discovery_id"]
            for item in connection.execute(
                """SELECT discovery_id FROM discovery_events WHERE source_id=?
                ORDER BY discovered_at DESC,discovery_id LIMIT ?""",
                (source_id, MAX_DISCOVERIES_PER_SOURCE),
            )
        ],
        "evidence_ids": evidence_ids,
        "interpretation_ids": [item["interpretation_id"] for item in interpretations],
        "interpretation_lenses": {str(item["lens_name"]).lower() for item in interpretations},
        "evidence_count": connection.execute(
            "SELECT COUNT(*) FROM evidence_records WHERE source_id=?",
            (source_id,),
        ).fetchone()[0],
    }


def _read_artifact_body(root: Path, logical_ref: str, expected_sha256: str) -> str:
    target = (root / logical_ref).resolve()
    target.relative_to(root.resolve())
    if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_BODY_BYTES:
        raise IntegratedContentProjectionError("content revision artifact is unavailable")
    body = target.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise IntegratedContentProjectionError("content revision artifact hash mismatch")
    return body.decode("utf-8")


def _browser_attribution(raw_json: str) -> dict[str, Any]:
    try:
        raw = json.loads(raw_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    name = str(raw.get("public_source_name") or "").strip()
    url = _safe_public_url(raw.get("public_source_url"))
    return {
        "required": bool(name or url or raw.get("required") is True),
        "public_source_name": name[:200] or None,
        "public_source_url": url,
    }


def build_integrated_content_projection(
    *,
    store: IntegratedSystemStore | None = None,
    artifact_root: Path | str | None = None,
) -> dict[str, Any]:
    store = store or IntegratedSystemStore()
    store.migrate()
    root = Path(artifact_root or default_artifact_root(store.database_path)).expanduser().resolve()
    lifecycle = ContentLifecycleService(store, PrivateContentArtifactStore(root))
    artifact_text_cache: dict[str, str | None] = {}
    with store.connection() as connection:
        source_count = connection.execute(
            "SELECT COUNT(*) FROM sources WHERE merged_into_source_id IS NULL"
        ).fetchone()[0]
        discovery_count = connection.execute("SELECT COUNT(*) FROM discovery_events").fetchone()[0]
        evidence_total = connection.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0]
        interpretation_total = connection.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0]
        learning_total = connection.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0]
        persona_total = connection.execute("SELECT COUNT(*) FROM persona_candidates").fetchone()[0]
        decision_total = connection.execute("SELECT COUNT(*) FROM decision_records").fetchone()[0]
        origin_counts = {
            row["origin"]: row["count"]
            for row in connection.execute("SELECT origin,COUNT(*) AS count FROM discovery_events GROUP BY origin ORDER BY origin")
        }
        source_rows = connection.execute(
            """SELECT s.*,
                (SELECT COUNT(*) FROM evidence_records e WHERE e.source_id=s.source_id) AS evidence_count
            FROM sources s WHERE s.merged_into_source_id IS NULL
            ORDER BY s.updated_at DESC,s.source_id LIMIT ?""",
            (MAX_SOURCES,),
        ).fetchall()
        sources = []
        source_lineage: dict[str, dict[str, Any]] = {}
        for row in source_rows:
            sharing = source_remote_sharing(row)
            discovery_rows = connection.execute(
                """SELECT discovery_id,origin,discovery_route,external_ref,discovered_at,relevance_state
                FROM discovery_events WHERE source_id=? ORDER BY discovered_at DESC,discovery_id LIMIT ?""",
                (row["source_id"], MAX_DISCOVERIES_PER_SOURCE),
            ).fetchall()
            evidence_rows = connection.execute(
                """SELECT e.*,a.artifact_id AS joined_artifact_id,a.content_sha256 AS artifact_sha256,
                    a.logical_ref AS artifact_logical_ref,a.byte_size AS artifact_byte_size
                FROM evidence_records e LEFT JOIN artifacts a ON a.artifact_id=e.artifact_id
                WHERE e.source_id=? ORDER BY e.created_at DESC,e.evidence_id LIMIT ?""",
                (row["source_id"], MAX_EVIDENCE_PER_SOURCE),
            ).fetchall()
            projected_evidence: list[dict[str, Any]] = []
            interpretation_ids: list[str] = []
            interpretation_lenses: set[str] = set()
            for evidence in evidence_rows:
                artifact = None
                if evidence["joined_artifact_id"]:
                    artifact = {
                        "artifact_id": evidence["joined_artifact_id"],
                        "content_sha256": evidence["artifact_sha256"],
                        "logical_ref": evidence["artifact_logical_ref"],
                        "byte_size": evidence["artifact_byte_size"],
                    }
                artifact_text = None
                allow_excerpt = (
                    artifact
                    and row["admissibility_state"] == "admissible"
                    and row["rights_state"] in {"permitted", "owner_controlled"}
                    and sharing is not None
                )
                if allow_excerpt:
                    artifact_text = _read_verified_artifact_text(root, artifact, artifact_text_cache)
                references = [
                    projected
                    for raw_reference in _json_list(evidence["evidence_refs_json"])[:8]
                    if (
                        projected := _evidence_reference(
                            raw_reference,
                            artifact_text=artifact_text,
                            allow_excerpt=bool(allow_excerpt),
                        )
                    ) is not None
                ]
                interpretation_rows = connection.execute(
                    """SELECT interpretation_id,lens_name,lens_version,reading_json,confidence,created_at
                    FROM interpretations WHERE evidence_id=?
                    ORDER BY created_at,interpretation_id LIMIT ?""",
                    (evidence["evidence_id"], MAX_INTERPRETATIONS_PER_EVIDENCE),
                ).fetchall()
                interpretations = []
                for interpretation in interpretation_rows:
                    interpretation_ids.append(interpretation["interpretation_id"])
                    interpretation_lenses.add(str(interpretation["lens_name"]).lower())
                    raw_reading = _json_object(interpretation["reading_json"])
                    raw_provenance = raw_reading.get("_provenance")
                    provenance_kind = (
                        str(raw_provenance.get("kind") or "").strip()
                        if isinstance(raw_provenance, dict)
                        else ""
                    )
                    if provenance_kind not in INTERPRETATION_PROVENANCE_KINDS:
                        provenance_kind = "synthesized_lens"
                    interpretations.append(
                        {
                            "interpretation_id": interpretation["interpretation_id"],
                            "lens_name": interpretation["lens_name"],
                            "lens_version": interpretation["lens_version"],
                            "provenance_kind": provenance_kind,
                            "reading": _bounded_scalar_object(raw_reading),
                            "confidence": interpretation["confidence"],
                            "created_at": interpretation["created_at"],
                        }
                    )
                projected_evidence.append(
                    {
                        "evidence_id": evidence["evidence_id"],
                        "extractor_name": evidence["extractor_name"],
                        "extractor_version": evidence["extractor_version"],
                        "confidence": evidence["confidence"],
                        "references": references,
                        "interpretations": interpretations,
                        "created_at": evidence["created_at"],
                    }
                )
            discoveries = [
                {
                    "discovery_id": discovery["discovery_id"],
                    "origin": discovery["origin"],
                    "discovery_route": _bounded_text(discovery["discovery_route"], limit=300) or "withheld_private_route",
                    "external_ref": _safe_public_url(discovery["external_ref"])
                    or _bounded_text(discovery["external_ref"], limit=300),
                    "discovered_at": discovery["discovered_at"],
                    "relevance_state": discovery["relevance_state"],
                }
                for discovery in discovery_rows
            ]
            origins = sorted({item["origin"] for item in discovery_rows})
            capture_kinds = []
            if row["raw_artifact_id"]:
                capture_kinds.append("raw")
            if row["transcript_artifact_id"]:
                capture_kinds.append("transcript")
            source_projection = {
                "source_id": row["source_id"],
                "source_kind": row["source_kind"],
                "title": _bounded_text(row["title"] or row["author_or_publisher"], limit=500) or "Untitled source",
                "author_or_publisher": _bounded_text(row["author_or_publisher"], limit=300),
                "canonical_url": _safe_public_url(row["canonical_url"]),
                "origins": origins,
                "discoveries": discoveries,
                "rights_state": row["rights_state"],
                "admissibility_state": row["admissibility_state"],
                "capture": {
                    "captured": bool(capture_kinds),
                    "capture_kinds": capture_kinds,
                    "captured_at": row["captured_at"],
                    "content_sha256": row["content_sha256"],
                },
                "evidence_count": row["evidence_count"],
                "evidence": projected_evidence,
                "merged_source_aliases": _merged_source_aliases(row["metadata_json"]),
                "updated_at": row["updated_at"],
            }
            sources.append(source_projection)
            source_lineage[row["source_id"]] = {
                "source_kind": row["source_kind"],
                "discovery_ids": [item["discovery_id"] for item in discoveries],
                "evidence_ids": [item["evidence_id"] for item in projected_evidence],
                "interpretation_ids": interpretation_ids,
                "interpretation_lenses": interpretation_lenses,
                "evidence_count": int(row["evidence_count"]),
            }
        opportunity_rows = connection.execute(
            """SELECT o.*,
                (SELECT COUNT(*) FROM opportunity_sources os WHERE os.opportunity_id=o.opportunity_id) AS source_count
            FROM content_opportunities o ORDER BY o.owner_requested DESC,o.updated_at DESC LIMIT ?""",
            (MAX_OPPORTUNITIES,),
        ).fetchall()
        post_rows = connection.execute(
            """SELECT p.*,o.thesis FROM canonical_posts p
            JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
            ORDER BY p.updated_at DESC LIMIT ?""",
            (MAX_POSTS,),
        ).fetchall()
        opportunity_projection_by_id: dict[str, dict[str, Any]] = {}
        opportunities: list[dict[str, Any]] = []
        for opportunity in opportunity_rows:
            metadata = _json_object(opportunity["metadata_json"])
            source_ids = [
                item["source_id"]
                for item in connection.execute(
                    "SELECT source_id FROM opportunity_sources WHERE opportunity_id=? ORDER BY source_id",
                    (opportunity["opportunity_id"],),
                )
            ]
            for source_id in source_ids:
                if source_id not in source_lineage:
                    source_lineage[source_id] = _source_lineage_reference(connection, source_id)
            selection = connection.execute(
                """SELECT disposition,reason_json,selected_at FROM portfolio_selections
                WHERE opportunity_id=? ORDER BY selected_at DESC,selection_id DESC LIMIT 1""",
                (opportunity["opportunity_id"],),
            ).fetchone()
            post_id_row = connection.execute(
                "SELECT post_id FROM canonical_posts WHERE opportunity_id=?",
                (opportunity["opportunity_id"],),
            ).fetchone()
            generation_job = connection.execute(
                """SELECT generation_job_id,portfolio_cycle_id,draft_authority,status,
                    attempt_count,post_id,revision_id,generation_receipt_sha256,
                    safe_error_code,updated_at,completed_at
                FROM content_generation_jobs WHERE opportunity_id=?""",
                (opportunity["opportunity_id"],),
            ).fetchone()
            explicit_evidence_ids = [str(metadata["evidence_id"])] if metadata.get("evidence_id") else []
            explicit_interpretation_ids = [
                str(item) for item in metadata.get("interpretation_ids", []) if str(item).strip()
            ] if isinstance(metadata.get("interpretation_ids"), list) else []
            projected_opportunity = {
                "opportunity_id": opportunity["opportunity_id"],
                "thesis": opportunity["thesis"],
                "status": opportunity["status"],
                "owner_requested": bool(opportunity["owner_requested"]),
                "truth_state": opportunity["truth_state"],
                "safety_state": opportunity["safety_state"],
                "attribution_state": opportunity["attribution_state"],
                "source_count": opportunity["source_count"],
                "strategy_contract_ref": _bounded_text(opportunity["strategy_contract_ref"], limit=300),
                "synthesis": {
                    "evidence_ids": explicit_evidence_ids,
                    "interpretation_ids": explicit_interpretation_ids,
                    "canonical_belief_refs": [
                        safe
                        for item in metadata.get("canonical_belief_refs", [])[:12]
                        if (safe := _bounded_text(item, limit=300)) is not None
                    ] if isinstance(metadata.get("canonical_belief_refs"), list) else [],
                    "exploratory_conflict": metadata.get("exploratory_conflict") is True,
                },
                "selection": {
                    "disposition": selection["disposition"],
                    "reason": _bounded_scalar_object(selection["reason_json"], max_items=4),
                    "selected_at": selection["selected_at"],
                } if selection else None,
                "drafting": {
                    "generation_job_id": generation_job["generation_job_id"],
                    "portfolio_cycle_id": generation_job["portfolio_cycle_id"],
                    "draft_authority": generation_job["draft_authority"],
                    "status": generation_job["status"],
                    "attempt_count": generation_job["attempt_count"],
                    "post_id": generation_job["post_id"],
                    "revision_id": generation_job["revision_id"],
                    "generation_receipt_sha256": generation_job["generation_receipt_sha256"],
                    "safe_error_code": _bounded_text(generation_job["safe_error_code"], limit=160),
                    "updated_at": generation_job["updated_at"],
                    "completed_at": generation_job["completed_at"],
                } if generation_job else None,
                "lineage": {
                    "source_ids": source_ids,
                    "evidence_ids": explicit_evidence_ids,
                    "interpretation_ids": explicit_interpretation_ids,
                    "post_id": post_id_row["post_id"] if post_id_row else None,
                },
                "updated_at": opportunity["updated_at"],
            }
            opportunities.append(projected_opportunity)
            opportunity_projection_by_id[opportunity["opportunity_id"]] = projected_opportunity

        decision_rows = connection.execute(
            "SELECT * FROM decision_records ORDER BY updated_at DESC,decision_id LIMIT ?",
            (MAX_SUMMARY_ITEMS,),
        ).fetchall()
        decisions = []
        for decision in decision_rows:
            links = []
            for item in connection.execute(
                "SELECT surface,external_ref FROM decision_links WHERE decision_id=? ORDER BY surface,external_ref",
                (decision["decision_id"],),
            ):
                surface = _bounded_text(item["surface"], limit=100)
                external_ref = _bounded_text(item["external_ref"], limit=300)
                if surface and external_ref and not any(token in external_ref for token in _PRIVATE_TEXT_TOKENS):
                    links.append({"surface": surface, "external_ref": external_ref})
            decisions.append(_decision_summary(decision, links))

        persona_rows = connection.execute(
            "SELECT * FROM persona_candidates ORDER BY updated_at DESC,persona_candidate_id LIMIT ?",
            (MAX_SUMMARY_ITEMS,),
        ).fetchall()
        persona_candidates = [_persona_summary(connection, row) for row in persona_rows]

        posts: list[dict[str, Any]] = []
        for post in post_rows:
            revisions = connection.execute(
                """SELECT r.*,a.content_sha256,a.logical_ref,a.byte_size
                FROM content_revisions r JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE r.post_id=? ORDER BY r.created_at,r.revision_id LIMIT ?""",
                (post["post_id"], MAX_REVISIONS_PER_POST),
            ).fetchall()
            projected_revisions = []
            existing_controls: set[str] = set()
            for revision in revisions:
                controls = _bounded_scalar_object(revision["control_json"], max_items=12)
                existing_controls.update(controls)
                body = _read_artifact_body(
                    root,
                    revision["logical_ref"],
                    revision["content_sha256"],
                )
                projected_revisions.append(
                    {
                        "revision_id": revision["revision_id"],
                        "parent_revision_id": revision["parent_revision_id"],
                        "revision_kind": revision["revision_kind"],
                        "platform": revision["platform"],
                        "controls": controls,
                        "body": body,
                        "content_sha256": revision["content_sha256"],
                        "attribution": _browser_attribution(revision["attribution_json"]),
                        "variant_generation": project_variant_generation_eligibility(
                            lifecycle,
                            post_id=post["post_id"],
                            post_status=post["status"],
                            parent=revision,
                            body_sha256=revision["content_sha256"],
                        ),
                        "created_at": revision["created_at"],
                    }
                )
            opportunity_projection = opportunity_projection_by_id.get(post["opportunity_id"])
            source_ids = list((opportunity_projection or {}).get("lineage", {}).get("source_ids", []))
            source_kinds = {
                source_lineage[source_id]["source_kind"]
                for source_id in source_ids
                if source_id in source_lineage
            }
            discovery_ids = [
                item
                for source_id in source_ids
                for item in source_lineage.get(source_id, {}).get("discovery_ids", [])
            ]
            evidence_ids = list((opportunity_projection or {}).get("lineage", {}).get("evidence_ids", []))
            interpretation_ids = list((opportunity_projection or {}).get("lineage", {}).get("interpretation_ids", []))
            evidence_count = sum(source_lineage.get(source_id, {}).get("evidence_count", 0) for source_id in source_ids)
            interpretation_lenses = {
                lens
                for source_id in source_ids
                for lens in source_lineage.get(source_id, {}).get("interpretation_lenses", set())
            }
            opportunity_row = next((row for row in opportunity_rows if row["opportunity_id"] == post["opportunity_id"]), None)
            opportunity_metadata = _json_object(opportunity_row["metadata_json"]) if opportunity_row else {}
            learning_rows = connection.execute(
                """SELECT * FROM learning_events WHERE post_id=?
                ORDER BY occurred_at DESC,learning_event_id DESC LIMIT ?""",
                (post["post_id"], MAX_LEARNING_EVENTS_PER_POST),
            ).fetchall()
            learning_events = [_event_summary(item) for item in learning_rows]
            post_persona = [
                candidate
                for candidate in persona_candidates
                if connection.execute(
                    "SELECT 1 FROM persona_candidate_evidence WHERE persona_candidate_id=? AND post_id=? LIMIT 1",
                    (candidate["persona_candidate_id"], post["post_id"]),
                ).fetchone()
            ][:MAX_PERSONA_ITEMS_PER_POST]
            lineage_refs = {
                post["post_id"],
                post["opportunity_id"],
                *source_ids,
                *[item["revision_id"] for item in projected_revisions],
            }
            post_decisions = [
                decision
                for decision in decisions
                if any(link["external_ref"] in lineage_refs for link in decision["links"])
            ][:MAX_DECISION_ITEMS_PER_POST]
            posts.append(
                {
                    "post_id": post["post_id"],
                    "opportunity_id": post["opportunity_id"],
                    "thesis": post["thesis"],
                    "status": post["status"],
                    "current_revision_id": post["current_revision_id"],
                    "revisions": projected_revisions,
                    "variant_control_options": _variant_control_options(
                        source_kinds=source_kinds,
                        evidence_count=evidence_count,
                        interpretation_lenses=interpretation_lenses,
                        opportunity_metadata=opportunity_metadata,
                        existing_controls=existing_controls,
                    ),
                    "learning_events": learning_events,
                    "persona_candidates": post_persona,
                    "decisions": post_decisions,
                    "lineage": {
                        "source_ids": source_ids,
                        "discovery_ids": discovery_ids,
                        "evidence_ids": evidence_ids,
                        "interpretation_ids": interpretation_ids,
                        "opportunity_id": post["opportunity_id"],
                        "post_id": post["post_id"],
                        "revision_ids": [item["revision_id"] for item in projected_revisions],
                        "learning_event_ids": [item["learning_event_id"] for item in learning_events],
                        "persona_candidate_ids": [item["persona_candidate_id"] for item in post_persona],
                        "decision_ids": [item["decision_id"] for item in post_decisions],
                    },
                    "updated_at": post["updated_at"],
                }
            )

        learning_counts = {
            row["event_kind"]: row["count"]
            for row in connection.execute(
                "SELECT event_kind,COUNT(*) AS count FROM learning_events GROUP BY event_kind ORDER BY event_kind"
            )
        }
        edit_counts = {
            row["edit_classification"]: row["count"]
            for row in connection.execute(
                """SELECT edit_classification,COUNT(*) AS count FROM learning_events
                WHERE edit_classification IS NOT NULL GROUP BY edit_classification ORDER BY edit_classification"""
            )
        }
        persona_status_counts = dict(Counter(item["status"] for item in persona_candidates))
        decision_status_counts = dict(Counter(item["status"] for item in decisions))
    state = "ready" if sources or opportunities or posts else "empty"
    controller_capabilities, controller_gaps = _controller_fields()
    counts = {
        "sources": source_count,
        "discoveries": discovery_count,
        "opportunities": len(opportunities),
        "posts": len(posts),
        "revisions": sum(len(post["revisions"]) for post in posts),
        "evidence": evidence_total,
        "interpretations": interpretation_total,
        "learning_events": learning_total,
        "persona_candidates": persona_total,
        "decisions": decision_total,
        "origins": origin_counts,
    }
    state, reason_codes = _project_controller_health(
        state=state,
        reason_codes=[],
        controller_gaps=controller_gaps,
        counts=counts,
    )
    return validate_integrated_content_projection(
        {
            "schema_version": PROJECTION_SCHEMA,
            "generated_at": _now_iso(),
            "state": state,
            "reason_codes": reason_codes,
            "counts": counts,
            "sources": sources,
            "opportunities": opportunities,
            "posts": posts,
            "activity_summary": {
                "learning": {"total": learning_total, "by_kind": learning_counts, "edit_classifications": edit_counts},
                "persona": {
                    "total": persona_total,
                    "by_status": persona_status_counts,
                    "automatic_promotion_eligible": sum(1 for item in persona_candidates if item["automatic_promotion_eligible"]),
                    "recent": persona_candidates,
                },
                "decisions": {"total": decision_total, "by_status": decision_status_counts, "recent": decisions},
            },
            "controller_capabilities": controller_capabilities,
            "controller_gaps": controller_gaps,
            "data_policy": {
                "canonical_authority": "mac_local_sql",
                "railway_role": "authenticated_bounded_review_projection",
                "raw_sources_included": False,
                "private_paths_included": False,
                "exact_review_copy_included": True,
                "bounded_evidence_references_included": True,
            },
        }
    )


def validate_integrated_content_projection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != PROJECTION_SCHEMA:
        raise IntegratedContentProjectionError("invalid integrated content projection schema")
    allowed = {
        "schema_version", "generated_at", "state", "reason_codes", "counts", "sources", "opportunities", "posts",
        "activity_summary", "controller_capabilities", "controller_gaps", "data_policy",
    }
    if set(payload) - allowed:
        raise IntegratedContentProjectionError("integrated content projection has undeclared fields")
    if payload.get("state") not in {"ready", "empty", "degraded", "error"}:
        raise IntegratedContentProjectionError("invalid integrated content projection state")
    try:
        generated_at = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntegratedContentProjectionError("invalid generated_at") from exc
    if generated_at.tzinfo is None:
        raise IntegratedContentProjectionError("generated_at must be timezone aware")
    opportunities = payload.get("opportunities")
    sources = payload.get("sources")
    posts = payload.get("posts")
    if not isinstance(sources, list) or len(sources) > MAX_SOURCES:
        raise IntegratedContentProjectionError("invalid source projection")
    if not isinstance(opportunities, list) or len(opportunities) > MAX_OPPORTUNITIES:
        raise IntegratedContentProjectionError("invalid opportunity projection")
    if not isinstance(posts, list) or len(posts) > MAX_POSTS:
        raise IntegratedContentProjectionError("invalid post projection")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(serialized.encode("utf-8")) > 512 * 1024:
        raise IntegratedContentProjectionError("integrated content projection exceeds 512 KB")
    forbidden_tokens = (
        "/Users/", "/home/", "file://", "AI_CLONE_STATE_ROOT", "raw_path", "transcript_body",
        "evidence_binding_json", "BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY",
    )
    if any(token in serialized for token in forbidden_tokens):
        raise IntegratedContentProjectionError("integrated content projection contains private implementation material")
    for source in sources:
        if not isinstance(source, dict) or set(source) != {
            "source_id", "source_kind", "title", "author_or_publisher", "canonical_url", "origins", "discoveries",
            "rights_state", "admissibility_state", "capture", "evidence_count", "evidence", "merged_source_aliases", "updated_at",
        }:
            raise IntegratedContentProjectionError("invalid source lineage projection")
        if not isinstance(source["discoveries"], list) or len(source["discoveries"]) > MAX_DISCOVERIES_PER_SOURCE:
            raise IntegratedContentProjectionError("invalid discovery projection")
        if not isinstance(source["evidence"], list) or len(source["evidence"]) > MAX_EVIDENCE_PER_SOURCE:
            raise IntegratedContentProjectionError("invalid evidence projection")
        aliases = source.get("merged_source_aliases")
        if not isinstance(aliases, list) or len(aliases) > MAX_MERGED_ALIASES_PER_SOURCE:
            raise IntegratedContentProjectionError("invalid merged source alias projection")
        if any(
            not isinstance(alias, dict)
            or set(alias) != {"source_id", "source_kind", "canonical_url"}
            or not str(alias.get("source_id") or "").strip()
            or not str(alias.get("source_kind") or "").strip()
            or (
                alias.get("canonical_url") is not None
                and _safe_public_url(alias["canonical_url"]) != alias["canonical_url"]
            )
            for alias in aliases
        ):
            raise IntegratedContentProjectionError("invalid merged source alias projection")
        capture = source.get("capture")
        if not isinstance(capture, dict) or set(capture) != {"captured", "capture_kinds", "captured_at", "content_sha256"}:
            raise IntegratedContentProjectionError("invalid capture projection")
        digest = capture.get("content_sha256")
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
            raise IntegratedContentProjectionError("invalid source content hash")
        for evidence in source["evidence"]:
            if not isinstance(evidence, dict) or set(evidence) != {
                "evidence_id", "extractor_name", "extractor_version", "confidence", "references", "interpretations", "created_at",
            }:
                raise IntegratedContentProjectionError("invalid evidence lineage projection")
            if not isinstance(evidence["references"], list) or len(evidence["references"]) > 8:
                raise IntegratedContentProjectionError("invalid evidence references")
            if not isinstance(evidence["interpretations"], list) or len(evidence["interpretations"]) > MAX_INTERPRETATIONS_PER_EVIDENCE:
                raise IntegratedContentProjectionError("invalid interpretation projection")
            for reference in evidence["references"]:
                if not isinstance(reference, dict) or set(reference) - {"kind", "start", "end", "excerpt", "source_url"}:
                    raise IntegratedContentProjectionError("invalid evidence reference")
                if len(str(reference.get("excerpt") or "")) > MAX_EVIDENCE_EXCERPT_CHARS:
                    raise IntegratedContentProjectionError("evidence excerpt exceeds browser bound")
            for interpretation in evidence["interpretations"]:
                if not isinstance(interpretation, dict) or set(interpretation) != {
                    "interpretation_id", "lens_name", "lens_version", "provenance_kind", "reading", "confidence", "created_at",
                } or not isinstance(interpretation["reading"], dict) or interpretation["provenance_kind"] not in INTERPRETATION_PROVENANCE_KINDS:
                    raise IntegratedContentProjectionError("invalid named interpretation")
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or set(opportunity) != {
            "opportunity_id", "thesis", "status", "owner_requested", "truth_state", "safety_state",
            "attribution_state", "source_count", "strategy_contract_ref", "synthesis", "selection", "drafting", "lineage", "updated_at",
        }:
            raise IntegratedContentProjectionError("invalid opportunity lineage projection")
        drafting = opportunity.get("drafting")
        if drafting is not None:
            if not isinstance(drafting, dict) or set(drafting) != {
                "generation_job_id", "portfolio_cycle_id", "draft_authority", "status",
                "attempt_count", "post_id", "revision_id", "generation_receipt_sha256",
                "safe_error_code", "updated_at", "completed_at",
            }:
                raise IntegratedContentProjectionError("invalid content drafting projection")
            if (
                drafting.get("draft_authority") not in {"owner_requested", "portfolio_selected"}
                or drafting.get("status") not in {"queued", "running", "succeeded", "failed"}
                or isinstance(drafting.get("attempt_count"), bool)
                or not isinstance(drafting.get("attempt_count"), int)
                or drafting["attempt_count"] < 0
            ):
                raise IntegratedContentProjectionError("invalid content drafting lifecycle")
            receipt_sha = drafting.get("generation_receipt_sha256")
            if receipt_sha is not None and (
                not isinstance(receipt_sha, str)
                or len(receipt_sha) != 64
                or any(char not in "0123456789abcdef" for char in receipt_sha)
            ):
                raise IntegratedContentProjectionError("invalid content drafting receipt hash")
    for post in posts:
        if not isinstance(post, dict) or set(post) != {
            "post_id", "opportunity_id", "thesis", "status", "current_revision_id", "revisions",
            "variant_control_options", "learning_events", "persona_candidates", "decisions", "lineage", "updated_at",
        } or len(post.get("revisions") or []) > MAX_REVISIONS_PER_POST:
            raise IntegratedContentProjectionError("invalid revision projection")
        controls = post.get("variant_control_options")
        if not isinstance(controls, list) or len(controls) > len(_CONTROL_OPTIONS):
            raise IntegratedContentProjectionError("invalid variant control projection")
        control_keys: set[str] = set()
        for control in controls:
            if not isinstance(control, dict) or set(control) != {"key", "label", "values", "default"}:
                raise IntegratedContentProjectionError("invalid variant control option")
            key = control.get("key")
            if key not in _CONTROL_OPTIONS or key in control_keys or control != {"key": key, **_CONTROL_OPTIONS[key]}:
                raise IntegratedContentProjectionError("variant control option is not canonical")
            control_keys.add(key)
        if not isinstance(post.get("learning_events"), list) or len(post["learning_events"]) > MAX_LEARNING_EVENTS_PER_POST:
            raise IntegratedContentProjectionError("invalid learning summary projection")
        _validate_persona_projection(post.get("persona_candidates"), limit=MAX_PERSONA_ITEMS_PER_POST)
        _validate_decision_projection(post.get("decisions"), limit=MAX_DECISION_ITEMS_PER_POST)
        for revision in post.get("revisions") or []:
            if (
                not isinstance(revision, dict)
                or set(revision) != {
                    "revision_id",
                    "parent_revision_id",
                    "revision_kind",
                    "platform",
                    "controls",
                    "body",
                    "content_sha256",
                    "attribution",
                    "variant_generation",
                    "created_at",
                }
                or len(str(revision.get("body") or "").encode("utf-8")) > MAX_BODY_BYTES
            ):
                raise IntegratedContentProjectionError("invalid revision body projection")
            attribution = revision.get("attribution")
            if not isinstance(attribution, dict) or set(attribution) - {"required", "public_source_name", "public_source_url"}:
                raise IntegratedContentProjectionError("invalid attribution projection")
            try:
                validate_variant_generation_eligibility(revision.get("variant_generation"))
            except ValueError as exc:
                raise IntegratedContentProjectionError(
                    "invalid variant-generation eligibility projection"
                ) from exc
    capabilities = payload.get("controller_capabilities")
    if (
        not isinstance(capabilities, dict)
        or set(capabilities) != set(_IMPLEMENTED_CONTROLLER_CAPABILITIES)
        or any(not isinstance(value, bool) for value in capabilities.values())
    ):
        raise IntegratedContentProjectionError("invalid controller capability projection")
    gaps = payload.get("controller_gaps")
    if not isinstance(gaps, list) or any(
        not isinstance(item, dict)
        or set(item) != {"capability", "reason_code", "safe_behavior"}
        or item.get("capability") not in capabilities
        or capabilities[item["capability"]] is not False
        or not _bounded_text(item.get("reason_code"), limit=160)
        or not _bounded_text(item.get("safe_behavior"), limit=300)
        for item in gaps
    ):
        raise IntegratedContentProjectionError("invalid controller gap projection")
    gap_capabilities = [item["capability"] for item in gaps]
    disabled_capabilities = {key for key, available in capabilities.items() if not available}
    if (
        len(gap_capabilities) != len(set(gap_capabilities))
        or set(gap_capabilities) != disabled_capabilities
    ):
        raise IntegratedContentProjectionError("controller gaps do not match disabled capabilities")
    activity = payload.get("activity_summary")
    if not isinstance(activity, dict) or set(activity) != {"learning", "persona", "decisions"}:
        raise IntegratedContentProjectionError("invalid activity summary projection")
    persona_activity = activity.get("persona")
    if (
        not isinstance(persona_activity, dict)
        or set(persona_activity) != {"total", "by_status", "automatic_promotion_eligible", "recent"}
    ):
        raise IntegratedContentProjectionError("invalid persona activity projection")
    _validate_persona_projection(persona_activity.get("recent"), limit=MAX_PERSONA_ITEMS_PER_POST)
    decision_activity = activity.get("decisions")
    if (
        not isinstance(decision_activity, dict)
        or set(decision_activity) != {"total", "by_status", "recent"}
        or not isinstance(decision_activity.get("total"), int)
        or not isinstance(decision_activity.get("by_status"), dict)
    ):
        raise IntegratedContentProjectionError("invalid decision activity projection")
    _validate_decision_projection(decision_activity.get("recent"), limit=MAX_SUMMARY_ITEMS)
    expected_policy = {
        "canonical_authority": "mac_local_sql",
        "railway_role": "authenticated_bounded_review_projection",
        "raw_sources_included": False,
        "private_paths_included": False,
        "exact_review_copy_included": True,
        "bounded_evidence_references_included": True,
    }
    if payload.get("data_policy") != expected_policy:
        raise IntegratedContentProjectionError("invalid integrated content data policy")
    return payload


def unavailable_integrated_content_projection(reason: str = "projection_unavailable") -> dict[str, Any]:
    controller_capabilities, controller_gaps = _controller_fields(
        projection_available=False
    )
    return {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _now_iso(),
        "state": "degraded",
        "reason_codes": [reason],
        "counts": {
            "sources": 0, "discoveries": 0, "opportunities": 0, "posts": 0, "revisions": 0,
            "evidence": 0, "interpretations": 0, "learning_events": 0, "persona_candidates": 0,
            "decisions": 0, "origins": {},
        },
        "sources": [],
        "opportunities": [],
        "posts": [],
        "activity_summary": {
            "learning": {"total": 0, "by_kind": {}, "edit_classifications": {}},
            "persona": {"total": 0, "by_status": {}, "automatic_promotion_eligible": 0, "recent": []},
            "decisions": {"total": 0, "by_status": {}, "recent": []},
        },
        "controller_capabilities": controller_capabilities,
        "controller_gaps": controller_gaps,
        "data_policy": {
            "canonical_authority": "mac_local_sql",
            "railway_role": "authenticated_bounded_review_projection",
            "raw_sources_included": False,
            "private_paths_included": False,
            "exact_review_copy_included": True,
            "bounded_evidence_references_included": True,
        },
    }
