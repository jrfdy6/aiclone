from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


EDIT_CLASSES = frozenset(
    {
        "factual",
        "voice",
        "audience",
        "strategy",
        "evidence_attribution",
        "safety_privacy",
        "platform",
        "worldview",
        "one_off",
    }
)
LEARNING_EVENTS = frozenset(
    {
        "manual_edit",
        "variant_selected",
        "variant_rejected",
        "owner_approved",
        "publication_confirmed",
        "performance_verified",
        "meaningful_conversation_proposed",
        "meaningful_conversation_confirmed",
        "meaningful_conversation_rejected",
        "owner_feedback",
    }
)
_PLATFORM_HOSTS = {
    "linkedin": ("linkedin.com",),
    "instagram": ("instagram.com",),
}


class ContentLearningConflict(ValueError):
    pass


def _parse_aware_past(value: Any, *, label: str, now: datetime) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > now:
        raise ValueError(f"{label} cannot be in the future")
    return parsed.isoformat()


def _validate_publication_url(platform: str, value: Any) -> str:
    if platform not in _PLATFORM_HOSTS:
        raise ValueError("publication platform must be linkedin or instagram")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("publication confirmation requires a public URL")
    parsed = urlparse(value.strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(hostname == host or hostname.endswith(f".{host}") for host in _PLATFORM_HOSTS[platform]):
        raise ValueError("publication URL does not match the confirmed platform")
    if not parsed.path or parsed.path == "/":
        raise ValueError("publication URL must identify the published item")
    return value.strip()


class ContentLearningService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store
        self.store.migrate()

    def record(
        self,
        *,
        post_id: str,
        revision_id: str,
        event_kind: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        edit_classification: str | None = None,
    ) -> dict[str, Any]:
        if event_kind not in LEARNING_EVENTS:
            raise ValueError("unsupported learning event")
        if event_kind == "manual_edit" and edit_classification not in EDIT_CLASSES:
            raise ValueError("manual edits require one approved classification")
        if event_kind != "manual_edit" and edit_classification is not None:
            raise ValueError("edit classification belongs only on manual edits")
        normalized_payload = dict(payload)
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:learning:{idempotency_key}"))
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                revision = connection.execute(
                    """SELECT r.*,a.content_sha256,p.status AS post_status,p.current_revision_id,
                    p.opportunity_id,o.truth_state,o.safety_state,o.attribution_state,o.metadata_json
                    FROM content_revisions r
                    JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                    JOIN canonical_posts p ON p.post_id=r.post_id
                    JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
                    WHERE r.revision_id=? AND r.post_id=?""",
                    (revision_id, post_id),
                ).fetchone()
                if not revision:
                    raise ValueError("learning event must reference a revision belonging to the post")

                existing = connection.execute(
                    "SELECT * FROM learning_events WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    if event_kind == "manual_edit":
                        normalized_payload = self._validate_manual_edit(
                            revision=revision,
                            payload=normalized_payload,
                        )
                    elif event_kind == "owner_approved":
                        normalized_payload = self._normalize_owner_approval(
                            revision=revision,
                            payload=normalized_payload,
                            now=now_dt,
                        )
                    elif event_kind in {"variant_selected", "variant_rejected"}:
                        normalized_payload = self._validate_variant_decision(
                            revision=revision,
                            payload=normalized_payload,
                            event_kind=event_kind,
                        )
                    elif event_kind == "publication_confirmed":
                        normalized_payload = self._normalize_publication_attestation(
                            revision=revision,
                            payload=normalized_payload,
                            now=now_dt,
                        )
                    if (
                        existing["post_id"] != post_id
                        or existing["revision_id"] != revision_id
                        or existing["event_kind"] != event_kind
                        or existing["edit_classification"] != edit_classification
                        or existing["payload_json"] != _canonical_json(normalized_payload)
                    ):
                        raise ContentLearningConflict("learning event idempotency conflict")
                    self._append_event(
                        connection,
                        learning_event_id=existing["learning_event_id"],
                        post_id=post_id,
                        revision_id=revision_id,
                        event_kind=event_kind,
                        edit_classification=edit_classification,
                        occurred_at=existing["occurred_at"],
                        idempotency_key=idempotency_key,
                    )
                    connection.execute("COMMIT")
                    result = dict(existing)
                    result["payload"] = json.loads(result.pop("payload_json"))
                    return result

                if event_kind == "manual_edit":
                    normalized_payload = self._validate_manual_edit(
                        revision=revision,
                        payload=normalized_payload,
                    )
                elif event_kind == "owner_approved":
                    normalized_payload = self._validate_owner_approval(
                        revision=revision,
                        payload=normalized_payload,
                        now=now_dt,
                    )
                elif event_kind in {"variant_selected", "variant_rejected"}:
                    normalized_payload = self._validate_variant_decision(
                        revision=revision,
                        payload=normalized_payload,
                        event_kind=event_kind,
                    )
                elif event_kind == "publication_confirmed":
                    normalized_payload = self._validate_publication_confirmation(
                        connection,
                        revision=revision,
                        payload=normalized_payload,
                        now=now_dt,
                    )
                elif event_kind == "performance_verified":
                    if not self._has_exact_event(connection, post_id, revision_id, "publication_confirmed"):
                        raise ContentLearningConflict("verified performance requires an exact confirmed publication")
                    if normalized_payload.get("verified") is not True or not str(normalized_payload.get("evidence_ref") or "").strip():
                        raise ValueError("verified performance requires verified=true and an evidence_ref")
                elif event_kind.startswith("meaningful_conversation_"):
                    if not str(normalized_payload.get("interaction_ref") or "").strip():
                        raise ValueError("meaningful conversation events require an interaction_ref")
                if event_kind == "meaningful_conversation_confirmed":
                    proposed = self._has_interaction_event(
                        connection,
                        post_id=post_id,
                        revision_id=revision_id,
                        event_kind="meaningful_conversation_proposed",
                        interaction_ref=normalized_payload.get("interaction_ref"),
                    )
                    if not proposed and normalized_payload.get("confirmed_by_owner") is not True:
                        raise ContentLearningConflict(
                            "conversation confirmation requires a prior proposal or explicit owner confirmation"
                        )

                payload_json = _canonical_json(normalized_payload)
                cursor = connection.execute(
                    """INSERT INTO learning_events(
                        learning_event_id,post_id,revision_id,event_kind,edit_classification,
                        payload_json,occurred_at,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        event_id,
                        post_id,
                        revision_id,
                        event_kind,
                        edit_classification,
                        payload_json,
                        now,
                        idempotency_key,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM learning_events WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if (
                    not row
                    or row["post_id"] != post_id
                    or row["revision_id"] != revision_id
                    or row["event_kind"] != event_kind
                    or row["edit_classification"] != edit_classification
                    or row["payload_json"] != payload_json
                ):
                    raise ContentLearningConflict("learning event idempotency conflict")

                if cursor.rowcount == 1 and event_kind == "owner_approved":
                    metadata = json.loads(revision["metadata_json"])
                    integrity = metadata.get("integrity") if isinstance(metadata.get("integrity"), dict) else {}
                    integrity.update(
                        {
                            "privacy_state": "pass",
                            "owner_integrity_confirmed": True,
                            "owner_integrity_confirmed_at": now,
                            "owner_integrity_revision_id": revision_id,
                        }
                    )
                    metadata["integrity"] = integrity
                    connection.execute(
                        """UPDATE content_opportunities
                        SET safety_state='pass',metadata_json=?,updated_at=? WHERE opportunity_id=?""",
                        (_canonical_json(metadata), now, revision["opportunity_id"]),
                    )
                    connection.execute(
                        "UPDATE canonical_posts SET status='approved',current_revision_id=?,updated_at=? WHERE post_id=?",
                        (revision_id, now, post_id),
                    )
                elif cursor.rowcount == 1 and event_kind == "variant_selected":
                    if revision["post_status"] == "published":
                        raise ContentLearningConflict("a published post cannot select a new unpublished variant")
                    connection.execute(
                        "UPDATE canonical_posts SET status='review',current_revision_id=?,updated_at=? WHERE post_id=?",
                        (revision_id, now, post_id),
                    )
                elif cursor.rowcount == 1 and event_kind == "publication_confirmed":
                    connection.execute(
                        "UPDATE canonical_posts SET status='published',current_revision_id=?,updated_at=? WHERE post_id=?",
                        (revision_id, now, post_id),
                    )
                    connection.execute(
                        """UPDATE content_opportunities SET status='published',updated_at=?
                        WHERE opportunity_id=(SELECT opportunity_id FROM canonical_posts WHERE post_id=?)""",
                        (now, post_id),
                    )

                self._append_event(
                    connection,
                    learning_event_id=row["learning_event_id"],
                    post_id=post_id,
                    revision_id=revision_id,
                    event_kind=event_kind,
                    edit_classification=edit_classification,
                    occurred_at=row["occurred_at"],
                    idempotency_key=idempotency_key,
                )
                connection.execute("COMMIT")
                result = dict(row)
                result["payload"] = json.loads(result.pop("payload_json"))
                return result
            except Exception:
                connection.execute("ROLLBACK")
                raise

    @classmethod
    def _validate_owner_approval(cls, *, revision: Any, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
        payload = cls._normalize_owner_approval(revision=revision, payload=payload, now=now)
        if revision["current_revision_id"] != revision["revision_id"]:
            raise ContentLearningConflict("owner approval must bind the exact selected revision")
        if revision["truth_state"] != "pass" or revision["safety_state"] not in {"pass", "owner_review_required"}:
            raise ContentLearningConflict("owner approval cannot clear unresolved truth or safety gates")
        metadata = json.loads(revision["metadata_json"])
        integrity = metadata.get("integrity") if isinstance(metadata.get("integrity"), dict) else {}
        privacy_state = str(integrity.get("privacy_state") or metadata.get("privacy_state") or revision["safety_state"])
        if privacy_state not in {"pass", "owner_review_required"}:
            raise ContentLearningConflict("owner approval cannot clear an unresolved privacy gate")
        if revision["attribution_state"] not in {"pass", "required"}:
            raise ContentLearningConflict("owner approval cannot clear unresolved attribution")
        return payload

    @staticmethod
    def _validate_manual_edit(*, revision: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if revision["revision_kind"] != "edit" or not revision["parent_revision_id"]:
            raise ContentLearningConflict("manual edit learning must reference an immutable edit revision")
        if payload.get("changed_by_owner") is not True:
            raise ValueError("manual edit learning requires changed_by_owner=true")
        if payload.get("parent_revision_id") != revision["parent_revision_id"]:
            raise ContentLearningConflict("manual edit learning must bind the exact parent revision")
        if payload.get("revision_sha256") != revision["content_sha256"]:
            raise ContentLearningConflict("manual edit learning must bind the exact edited revision bytes")
        return payload

    @staticmethod
    def _normalize_owner_approval(*, revision: Any, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
        if payload.get("approved_by_owner") is not True:
            raise ValueError("owner approval requires approved_by_owner=true")
        if payload.get("revision_sha256") != revision["content_sha256"]:
            raise ContentLearningConflict("owner approval must bind the exact revision bytes")
        confirmation = payload.get("integrity_confirmation")
        expected_confirmation = {
            "truth": True,
            "safety": True,
            "privacy": True,
            "attribution": True,
        }
        if confirmation != expected_confirmation:
            raise ValueError("owner approval requires explicit truth, safety, privacy, and attribution confirmation")
        payload["approved_at"] = _parse_aware_past(payload.get("approved_at"), label="approved_at", now=now)
        return payload

    @staticmethod
    def _validate_variant_decision(*, revision: Any, payload: dict[str, Any], event_kind: str) -> dict[str, Any]:
        if revision["revision_kind"] != "variant":
            raise ContentLearningConflict("variant decisions must reference a linked variant revision")
        authority_key = "selected_by_owner" if event_kind == "variant_selected" else "rejected_by_owner"
        if payload.get(authority_key) is not True:
            raise ValueError(f"{event_kind} requires {authority_key}=true")
        if payload.get("revision_sha256") != revision["content_sha256"]:
            raise ContentLearningConflict("variant decision must bind the exact revision bytes")
        return payload

    def _validate_publication_confirmation(
        self,
        connection: Any,
        *,
        revision: Any,
        payload: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        payload = self._normalize_publication_attestation(
            revision=revision,
            payload=payload,
            now=now,
        )
        if revision["post_status"] != "approved" or revision["current_revision_id"] != revision["revision_id"]:
            raise ContentLearningConflict("publication requires the exact current revision to be canonically owner-approved")
        approval = connection.execute(
            """SELECT payload_json,occurred_at FROM learning_events
            WHERE post_id=? AND revision_id=? AND event_kind='owner_approved'
            ORDER BY occurred_at DESC,learning_event_id DESC LIMIT 1""",
            (revision["post_id"], revision["revision_id"]),
        ).fetchone()
        if not approval:
            raise ContentLearningConflict("publication requires a prior canonical owner approval")
        approval_payload = json.loads(approval["payload_json"])
        if approval_payload.get("revision_sha256") != revision["content_sha256"]:
            raise ContentLearningConflict("publication approval no longer matches the exact revision")
        latest_selection = connection.execute(
            """SELECT occurred_at FROM learning_events
            WHERE post_id=? AND event_kind='variant_selected'
            ORDER BY occurred_at DESC,learning_event_id DESC LIMIT 1""",
            (revision["post_id"],),
        ).fetchone()
        if latest_selection and datetime.fromisoformat(approval["occurred_at"]) < datetime.fromisoformat(latest_selection["occurred_at"]):
            raise ContentLearningConflict("publication requires owner approval after the latest variant selection")
        approved_at = datetime.fromisoformat(str(approval_payload["approved_at"]))
        if datetime.fromisoformat(payload["published_at"]) < approved_at:
            raise ContentLearningConflict("publication cannot predate owner approval")
        return payload

    @staticmethod
    def _normalize_publication_attestation(
        *,
        revision: Any,
        payload: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        if payload.get("confirmed_by_owner") is not True:
            raise ValueError("publication confirmation requires confirmed_by_owner=true")
        if payload.get("revision_sha256") != revision["content_sha256"]:
            raise ContentLearningConflict("publication confirmation must bind the exact revision bytes")
        platform = str(payload.get("platform") or "").strip().lower()
        payload["platform"] = platform
        payload["public_url"] = _validate_publication_url(platform, payload.get("public_url"))
        payload["published_at"] = _parse_aware_past(payload.get("published_at"), label="published_at", now=now)
        return payload

    @staticmethod
    def _has_exact_event(connection: Any, post_id: str, revision_id: str, event_kind: str) -> bool:
        return bool(
            connection.execute(
                "SELECT 1 FROM learning_events WHERE post_id=? AND revision_id=? AND event_kind=? LIMIT 1",
                (post_id, revision_id, event_kind),
            ).fetchone()
        )

    @staticmethod
    def _has_interaction_event(
        connection: Any,
        *,
        post_id: str,
        revision_id: str,
        event_kind: str,
        interaction_ref: Any,
    ) -> bool:
        interaction_ref = str(interaction_ref or "").strip()
        if not interaction_ref:
            raise ValueError("meaningful conversation events require an interaction_ref")
        for row in connection.execute(
            "SELECT payload_json FROM learning_events WHERE post_id=? AND revision_id=? AND event_kind=?",
            (post_id, revision_id, event_kind),
        ):
            if str(json.loads(row["payload_json"]).get("interaction_ref") or "").strip() == interaction_ref:
                return True
        return False

    @staticmethod
    def _append_event(
        connection: Any,
        *,
        learning_event_id: str,
        post_id: str,
        revision_id: str,
        event_kind: str,
        edit_classification: str | None,
        occurred_at: str,
        idempotency_key: str,
    ) -> None:
        event_key = f"learning:{idempotency_key}"
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
        actor_type = "owner" if event_kind in {
            "manual_edit",
            "variant_selected",
            "variant_rejected",
            "owner_approved",
            "publication_confirmed",
            "owner_feedback",
        } else "content_learning"
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                payload_json,provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                f"learning.{event_kind}",
                "canonical_post",
                post_id,
                occurred_at,
                actor_type,
                _canonical_json(
                    {
                        "learning_event_id": learning_event_id,
                        "revision_id": revision_id,
                        "event_kind": event_kind,
                        "edit_classification": edit_classification,
                    }
                ),
                _canonical_json({"authority": "canonical_content_lifecycle/v1"}),
                "[]",
                event_key,
            ),
        )
