from __future__ import annotations

import json
from typing import Any, Mapping

from app.services.integrated_system_store import IntegratedSystemStore


EVENT_TYPE = "source.feed_signal_normalized"
SCHEMA_VERSION = "source_feed_signal/v1"
NORMALIZER_VERSION = "1.0.0"
MAX_EVENT_BYTES = 32 * 1024
_BODY_KEYS = frozenset(
    {
        "body",
        "body_text",
        "content",
        "full_text",
        "raw",
        "raw_body",
        "raw_text",
        "text",
        "transcript",
    }
)
_TEXT_LIMITS = {
    "title": 500,
    "author": 300,
    "source_url": 2048,
    "source_path": 1024,
    "published_at": 80,
    "captured_at": 80,
    "source_platform": 80,
    "source_type": 80,
    "source_lane": 80,
    "capture_method": 120,
    "priority_lane": 120,
    "role_alignment": 120,
    "risk_level": 120,
    "publish_posture": 120,
    "summary": 2000,
    "why_it_matters": 2000,
    "core_claim": 1200,
}
_LIST_LIMITS = {
    "headline_candidates": (4, 700),
    "supporting_claims": (4, 1000),
    "topics": (12, 300),
    "trust_notes": (8, 500),
    "watchlist_matches": (8, 300),
    "language_patterns": (8, 500),
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _clean_text(value: Any, *, limit: int) -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned[:limit]


def _clean_list(value: Any, *, count: int, item_limit: int) -> list[str]:
    values = value if isinstance(value, list) else ([] if value in (None, "") else [value])
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = _clean_text(item, limit=item_limit)
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue
        seen.add(lowered)
        result.append(cleaned)
        if len(result) >= count:
            break
    return result


def _compact_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        raise ValueError("feed signal metadata nesting is too deep")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clean_text(value, limit=2048)
    if isinstance(value, list):
        return [_compact_metadata(item, depth=depth + 1) for item in value[:16]]
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, item in list(value.items())[:32]:
            normalized_key = _clean_text(key, limit=120)
            if not normalized_key:
                continue
            if normalized_key.lower() in _BODY_KEYS:
                raise ValueError(f"feed signal metadata must not contain source bodies: {normalized_key}")
            compact[normalized_key] = _compact_metadata(item, depth=depth + 1)
        return compact
    return _clean_text(value, limit=2048)


def _normalize_signal(
    signal: Mapping[str, Any],
    *,
    source_id: str,
    artifact_id: str,
    captured_at: str,
) -> dict[str, Any]:
    normalized = {
        key: _clean_text(signal.get(key), limit=limit)
        for key, limit in _TEXT_LIMITS.items()
    }
    normalized["captured_at"] = _clean_text(
        captured_at or normalized.get("captured_at"),
        limit=_TEXT_LIMITS["captured_at"],
    )
    for key, (count, item_limit) in _LIST_LIMITS.items():
        normalized[key] = _clean_list(signal.get(key), count=count, item_limit=item_limit)
    engagement = signal.get("engagement") if isinstance(signal.get("engagement"), dict) else {}
    normalized["engagement"] = {
        key: max(0, int(value))
        for key, value in list(engagement.items())[:8]
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    normalized["source_metadata"] = _compact_metadata(signal.get("source_metadata") or {})
    normalized["source_metadata"].update(
        {
            "canonical_source_id": source_id,
            "canonical_capture_artifact_id": artifact_id,
            "feed_signal_schema": SCHEMA_VERSION,
        }
    )
    normalized["id"] = source_id
    return normalized


class SourceFeedSignalService:
    """Persist and retrieve the compact source-linked input used by the social feed.

    Raw bodies remain in the content-addressed private artifact store. The event
    ledger keeps only bounded normalization facts plus the artifact reference,
    so the feed builder does not depend on a parallel Markdown writer.
    """

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def record(
        self,
        *,
        source_id: str,
        artifact_id: str,
        signal: Mapping[str, Any],
        normalizer_name: str,
        normalizer_version: str = NORMALIZER_VERSION,
    ) -> dict[str, Any]:
        self.store.migrate()
        with self.store.connection() as connection:
            source = connection.execute(
                "SELECT * FROM sources WHERE source_id=? AND merged_into_source_id IS NULL",
                (source_id,),
            ).fetchone()
            artifact = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if not source:
            raise ValueError("feed signal source must be an active canonical source")
        if not artifact or artifact_id not in {
            source["raw_artifact_id"],
            source["transcript_artifact_id"],
        }:
            raise ValueError("feed signal artifact is not attached to its canonical source")
        if source["admissibility_state"] != "admissible" or source["rights_state"] not in {
            "permitted",
            "owner_controlled",
        }:
            raise ValueError("feed signal source has not passed canonical admission and rights gates")

        normalized_name = _clean_text(normalizer_name, limit=120)
        normalized_version = _clean_text(normalizer_version, limit=80)
        if not normalized_name or not normalized_version:
            raise ValueError("feed signal normalizer name and version are required")
        idempotency_key = (
            f"source-feed-signal:{source_id}:{artifact_id}:"
            f"{normalized_name}:{normalized_version}"
        )
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM system_events WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        if existing:
            return dict(existing)
        normalized_signal = _normalize_signal(
            signal,
            source_id=source_id,
            artifact_id=artifact_id,
            captured_at=str(source["captured_at"] or ""),
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "artifact_id": artifact_id,
            "normalizer_name": normalized_name,
            "normalizer_version": normalized_version,
            "signal": normalized_signal,
        }
        encoded = _canonical_json(payload).encode("utf-8")
        if len(encoded) > MAX_EVENT_BYTES:
            raise ValueError("feed signal event exceeds the compact ledger limit")
        return self.store.append_event(
            event_type=EVENT_TYPE,
            aggregate_type="source",
            aggregate_id=source_id,
            actor_type="deterministic_source_normalizer",
            payload=payload,
            provenance={
                "normalization_kind": "deterministic_policy_evaluation",
                "normalizer_name": normalized_name,
                "normalizer_version": normalized_version,
                "source_content_sha256": str(artifact["content_sha256"]),
            },
            artifact_refs=[artifact_id],
            idempotency_key=idempotency_key,
            occurred_at=str(source["captured_at"] or source["updated_at"]),
        )

    def load(self, *, limit: int = 512) -> list[dict[str, Any]]:
        self.store.migrate()
        bounded_limit = max(1, min(int(limit), 2000))
        with self.store.connection() as connection:
            rows = connection.execute(
                """SELECT e.payload_json,e.occurred_at,e.event_id
                   FROM system_events e
                   JOIN sources s ON s.source_id=e.aggregate_id
                   WHERE e.event_type=?
                     AND e.aggregate_type='source'
                     AND s.merged_into_source_id IS NULL
                     AND s.admissibility_state='admissible'
                     AND s.rights_state IN ('permitted','owner_controlled')
                   ORDER BY e.occurred_at DESC,e.event_id DESC
                   LIMIT ?""",
                (EVENT_TYPE, bounded_limit),
            ).fetchall()
        latest_by_source: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("schema_version") != SCHEMA_VERSION:
                continue
            source_id = str(payload.get("source_id") or "").strip()
            signal = payload.get("signal")
            if not source_id or source_id in latest_by_source or not isinstance(signal, dict):
                continue
            latest_by_source[source_id] = dict(signal)
        return sorted(
            latest_by_source.values(),
            key=lambda item: (
                str(item.get("published_at") or item.get("captured_at") or ""),
                str(item.get("id") or ""),
            ),
        )
