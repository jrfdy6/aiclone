from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from app.services.content_lifecycle_service import PrivateContentArtifactStore
from app.services.integrated_content_projection_service import default_artifact_root
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.source_intake_adapter_service import SourceAdapterEnvelope, SourceIntakeAdapterService
from app.services.source_intake_contract_service import canonical_source_identity, canonicalize_external_url
from app.services.source_intake_execution_service import SourceIntakeExecutionService
from app.services.source_evidence_interpretation_service import (
    InterpretationLensService,
    SourceEvidenceService,
)


OPPORTUNITY_SCHEMA = "social_engagement_opportunity/v1"
ACTION_SCHEMA = "social_engagement_action/v1"
ALLOWED_PLATFORMS = frozenset({"linkedin", "instagram"})
ALLOWED_ENGAGEMENT_TYPES = frozenset({"comment", "message", "post"})
ALLOWED_ASSISTED_ACTIONS = frozenset({"prepare_copy", "open_native_surface"})
PROHIBITED_PLATFORM_MUTATIONS = frozenset(
    {"publish", "comment", "message", "repost", "like", "follow", "send", "schedule"}
)
PLATFORM_HOSTS = {
    "linkedin": frozenset({"linkedin.com", "www.linkedin.com", "m.linkedin.com"}),
    "instagram": frozenset({"instagram.com", "www.instagram.com"}),
}
MAX_VISIBLE_TEXT_CHARS = 20_000
MAX_DRAFT_CHARS = 10_000
MAX_TITLE_CHARS = 500
MAX_AUTHOR_CHARS = 300
EVIDENCE_EXTRACTOR_NAME = "owner_attested_visible_social_text"
EVIDENCE_EXTRACTOR_VERSION = "1.0.0"
INTERPRETATION_LENS_NAME = "social_engagement_assistance_boundary"
INTERPRETATION_LENS_VERSION = "1.0.0"


class SocialEngagementAssistError(ValueError):
    pass


class SocialEngagementOpportunityNotFound(SocialEngagementAssistError):
    pass


class SocialEngagementConflict(SocialEngagementAssistError):
    pass


class RemoteSocialAssistAuthorityUnavailable(SocialEngagementAssistError):
    """Raised before Railway can create a second writable social authority."""


class ProhibitedSocialMutation(PermissionError):
    pass


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _exact_text(value: Any) -> str:
    return str(value or "")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _platform(value: Any) -> str:
    platform = _clean(value).lower()
    if platform not in ALLOWED_PLATFORMS:
        raise SocialEngagementAssistError("platform must be linkedin or instagram")
    return platform


def _engagement_type(value: Any) -> str:
    engagement_type = _clean(value).lower()
    if engagement_type not in ALLOWED_ENGAGEMENT_TYPES:
        raise SocialEngagementAssistError("engagement type must be comment, message, or post")
    return engagement_type


def canonical_native_surface_url(platform: str, value: Any) -> str:
    normalized_platform = _platform(platform)
    raw_url = _clean(value)
    raw_parts = urlsplit(raw_url)
    if raw_parts.username or raw_parts.password:
        raise SocialEngagementAssistError("native surface URL must not contain credentials")
    try:
        canonical_url = canonicalize_external_url(raw_url)
    except (TypeError, ValueError) as exc:
        raise SocialEngagementAssistError("native surface URL must use permitted HTTPS") from exc
    parts = urlsplit(canonical_url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in PLATFORM_HOSTS[normalized_platform]:
        raise SocialEngagementAssistError(f"native surface URL must belong to {normalized_platform}")
    return canonical_url


class SocialEngagementAssistService:
    """Owner-controlled social assistance over the canonical local source/event store.

    This service never calls a social platform. It records text the owner supplied
    from an authenticated visible surface, returns copy/open preparation data, and
    rejects every request that names an external mutation.
    """

    def __init__(
        self,
        store: IntegratedSystemStore,
        artifact_store: PrivateContentArtifactStore | None = None,
    ) -> None:
        self.store = store
        self.artifact_store = artifact_store or PrivateContentArtifactStore(default_artifact_root(store.database_path))
        self.intake = SourceIntakeAdapterService(store)
        self.execution = SourceIntakeExecutionService(store, self.artifact_store)

    def capture_opportunity(
        self,
        *,
        platform: str,
        source_url: str,
        visible_text: str,
        draft_text: str,
        engagement_type: str,
        title: str | None = None,
        author: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_platform = _platform(platform)
        normalized_engagement_type = _engagement_type(engagement_type)
        canonical_url = canonical_native_surface_url(normalized_platform, source_url)
        exact_visible_text = _exact_text(visible_text)
        exact_draft_text = _exact_text(draft_text)
        normalized_title = _clean(title)
        normalized_author = _clean(author)
        if not exact_visible_text.strip():
            raise SocialEngagementAssistError("visible source text is required")
        if not exact_draft_text.strip():
            raise SocialEngagementAssistError("prepared draft text is required")
        if len(exact_visible_text) > MAX_VISIBLE_TEXT_CHARS:
            raise SocialEngagementAssistError("visible source text exceeds the assisted-capture limit")
        if len(exact_draft_text) > MAX_DRAFT_CHARS:
            raise SocialEngagementAssistError("prepared draft text exceeds the assisted-capture limit")
        if len(normalized_title) > MAX_TITLE_CHARS or len(normalized_author) > MAX_AUTHOR_CHARS:
            raise SocialEngagementAssistError("source title or author exceeds the assisted-capture limit")

        visible_sha256 = _sha256_text(exact_visible_text)
        draft_sha256 = _sha256_text(exact_draft_text)
        request_key = _clean(idempotency_key)
        if len(request_key) > 200:
            raise SocialEngagementAssistError("idempotency key exceeds 200 characters")
        if not request_key:
            request_key = _sha256_text(
                _canonical_json(
                    {
                        "platform": normalized_platform,
                        "source_url": canonical_url,
                        "visible_sha256": visible_sha256,
                        "draft_sha256": draft_sha256,
                        "engagement_type": normalized_engagement_type,
                    }
                )
            )
        capture_key = f"social-assist-capture:{request_key}"
        existing_event = self._event_by_idempotency_key(capture_key)
        if existing_event:
            existing_payload = json.loads(str(existing_event["payload_json"]))
            expected_identity = {
                "platform": normalized_platform,
                "source_url": canonical_url,
                "visible_text_sha256": visible_sha256,
                "draft_sha256": draft_sha256,
                "engagement_type": normalized_engagement_type,
                "source_title": normalized_title or None,
                "source_author": normalized_author or None,
            }
            if any(existing_payload.get(key) != value for key, value in expected_identity.items()):
                raise SocialEngagementConflict("idempotency key already belongs to another engagement opportunity")
            lineage = self._ensure_projection_lineage(
                source_id=str(existing_payload["source_id"]),
                artifact_id=str(existing_payload["visible_text_artifact_id"]),
                source_url=canonical_url,
                visible_sha256=visible_sha256,
                platform=normalized_platform,
                engagement_type=normalized_engagement_type,
                capture_key=capture_key,
            )
            return {**self._hydrate_event(existing_event), **lineage}

        source_kind = self._compatible_source_kind(canonical_url, normalized_platform)
        envelope = SourceAdapterEnvelope(
            origin="linkedin" if normalized_platform == "linkedin" else "permitted_discovery",
            adapter_name=f"{normalized_platform}_assisted_browser",
            source_kind=source_kind,
            discovery_route=f"{normalized_platform}:owner_attested_authenticated_visible_item",
            external_ref=f"{canonical_url}#{visible_sha256}",
            canonical_url=canonical_url,
            title=normalized_title or None,
            author_or_publisher=normalized_author or None,
            rights_state="permitted",
            metadata={
                "capture_method": "owner_supplied_visible_item",
                "access_context": "owner_attested_authenticated_session",
                "platform": normalized_platform,
                "visible_sha256": visible_sha256,
                "no_scraping": True,
            },
        )
        prepared = self.execution.register_and_gate(
            envelope,
            relevance_state="qualified",
            admissibility_state="admissible",
            reason="owner_attested_authenticated_visible_item",
            policy_name="assisted_social_visible_item_gate",
            capture_kind="raw",
        )
        intake_result = prepared["registration"]
        visible_capture = self.execution.attach_or_reuse_text(
            prepared,
            text=exact_visible_text,
            capture_kind="raw",
            metadata={
                "capture_adapter": f"{normalized_platform}_assisted_browser",
                "capture_version": "1.0.0",
                "artifact_role": "owner_supplied_visible_social_text",
            },
        )
        if _sha256_text(visible_capture["text"]) != visible_sha256:
            raise SocialEngagementConflict(
                "canonical social source already has different captured text"
            )
        visible_artifact = {"artifact_id": visible_capture["artifact_id"]}
        draft_artifact = self._put_private_text(
            exact_draft_text,
            artifact_kind="social_engagement_draft",
            metadata={"artifact_role": "owner_review_social_draft"},
        )
        opportunity_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:social-engagement:{capture_key}"))
        created_at = str(intake_result["discovery"]["discovered_at"])
        payload = {
            "schema_version": OPPORTUNITY_SCHEMA,
            "opportunity_id": opportunity_id,
            "source_id": intake_result["source"]["source_id"],
            "discovery_id": intake_result["discovery"]["discovery_id"],
            "source_event_id": intake_result["event"]["event_id"],
            "source_gate_event_id": prepared["gate"]["gate_event_id"],
            "platform": normalized_platform,
            "source_url": canonical_url,
            "source_title": normalized_title or None,
            "source_author": normalized_author or None,
            "visible_text_artifact_id": visible_artifact["artifact_id"],
            "visible_text_sha256": visible_sha256,
            "canonical_capture_reused": bool(visible_capture["reused"]),
            "draft_artifact_id": draft_artifact["artifact_id"],
            "draft_sha256": draft_sha256,
            "engagement_type": normalized_engagement_type,
            "status": "draft_ready",
            "owner_execution_required": True,
            "external_mutation_performed": False,
            "created_at": created_at,
        }
        provenance = {
            "capture_method": "owner_supplied_visible_item",
            "access_context": "owner_attested_authenticated_session",
            "canonical_intake_adapter": envelope.adapter_name,
            "canonical_source_event_id": intake_result["event"]["event_id"],
            "discovery_origin": envelope.origin,
            "discovery_route": envelope.discovery_route,
            "external_source_url": canonical_url,
            "no_scraping": True,
            "social_platform_api_called": False,
        }
        try:
            event = self.store.append_event(
                event_type="engagement_opportunity.created",
                aggregate_type="engagement_opportunity",
                aggregate_id=opportunity_id,
                actor_type="owner_assisted_browser",
                payload=payload,
                provenance=provenance,
                artifact_refs=[visible_artifact["artifact_id"], draft_artifact["artifact_id"]],
                idempotency_key=capture_key,
                occurred_at=created_at,
            )
        except ValueError as exc:
            raise SocialEngagementConflict("engagement opportunity idempotency conflict") from exc
        lineage = self._ensure_projection_lineage(
            source_id=str(intake_result["source"]["source_id"]),
            artifact_id=str(visible_artifact["artifact_id"]),
            source_url=canonical_url,
            visible_sha256=visible_sha256,
            platform=normalized_platform,
            engagement_type=normalized_engagement_type,
            capture_key=capture_key,
        )
        return {**self._hydrate_event(event), **lineage}

    def list_opportunities(self, *, limit: int = 50) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 100))
        self.store.migrate()
        with self.store.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM system_events
                   WHERE event_type='engagement_opportunity.created'
                   ORDER BY occurred_at DESC, event_id DESC LIMIT ?""",
                (normalized_limit,),
            ).fetchall()
        return [self._hydrate_event(dict(row)) for row in rows]

    def prepare_action(
        self,
        *,
        opportunity_id: str,
        action: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_action = _clean(action).lower()
        if normalized_action in PROHIBITED_PLATFORM_MUTATIONS:
            raise ProhibitedSocialMutation(
                f"{normalized_action} is owner-executed only; backend social mutation is prohibited"
            )
        if normalized_action not in ALLOWED_ASSISTED_ACTIONS:
            raise SocialEngagementAssistError("action must be prepare_copy or open_native_surface")
        opportunity = self.get_opportunity(opportunity_id)
        normalized_request_id = _clean(request_id) or str(uuid.uuid4())
        if len(normalized_request_id) > 200:
            raise SocialEngagementAssistError("request id exceeds 200 characters")
        try:
            event = self.store.append_event(
                event_type="engagement_action.prepared",
                aggregate_type="engagement_opportunity",
                aggregate_id=opportunity_id,
                actor_type="owner_assisted_browser",
                payload={
                    "schema_version": ACTION_SCHEMA,
                    "action": normalized_action,
                    "platform": opportunity["platform"],
                    "owner_execution_required": True,
                    "external_mutation_performed": False,
                },
                provenance={
                    "source_event_id": opportunity["source_event_id"],
                    "native_surface_url": opportunity["source_url"],
                    "social_platform_api_called": False,
                },
                idempotency_key=f"social-assist-action:{opportunity_id}:{normalized_request_id}",
            )
        except ValueError as exc:
            raise SocialEngagementConflict("engagement action idempotency conflict") from exc
        return {
            "schema_version": ACTION_SCHEMA,
            "action_event_id": event["event_id"],
            "action": normalized_action,
            "opportunity_id": opportunity_id,
            "platform": opportunity["platform"],
            "native_surface_url": opportunity["source_url"],
            "draft_text": opportunity["draft_text"] if normalized_action == "prepare_copy" else None,
            "owner_execution_required": True,
            "external_mutation_performed": False,
        }

    def get_opportunity(self, opportunity_id: str) -> dict[str, Any]:
        normalized_id = _clean(opportunity_id)
        self.store.migrate()
        with self.store.connection() as connection:
            row = connection.execute(
                """SELECT * FROM system_events
                   WHERE event_type='engagement_opportunity.created'
                     AND aggregate_type='engagement_opportunity' AND aggregate_id=?""",
                (normalized_id,),
            ).fetchone()
        if not row:
            raise SocialEngagementOpportunityNotFound("engagement opportunity was not found")
        return self._hydrate_event(dict(row))

    def _compatible_source_kind(self, canonical_url: str, platform: str) -> str:
        identity = canonical_source_identity(
            canonical_url=canonical_url,
            external_source_id=None,
            content_sha256=None,
        )
        self.store.migrate()
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT source_kind FROM sources WHERE canonical_identity=?",
                (identity,),
            ).fetchone()
        return str(existing["source_kind"]) if existing else f"{platform}_post"

    def _event_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        self.store.migrate()
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM system_events WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        return dict(row) if row else None

    def _put_private_text(
        self,
        text: str,
        *,
        artifact_kind: str,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        artifact = self.artifact_store.write_text(text, artifact_kind=artifact_kind)
        return self.store.put_artifact(
            artifact_kind=artifact_kind,
            metadata={"private": True, "immutable": True, **dict(metadata)},
            **artifact,
        )

    def _ensure_projection_lineage(
        self,
        *,
        source_id: str,
        artifact_id: str,
        source_url: str,
        visible_sha256: str,
        platform: str,
        engagement_type: str,
        capture_key: str,
    ) -> dict[str, str]:
        """Bind an assisted capture to bounded evidence and deterministic policy context."""

        lineage_key = hashlib.sha256(capture_key.encode("utf-8")).hexdigest()
        evidence = SourceEvidenceService(self.store).record(
            source_id=source_id,
            extractor_name=EVIDENCE_EXTRACTOR_NAME,
            extractor_version=EVIDENCE_EXTRACTOR_VERSION,
            artifact_id=artifact_id,
            evidence_refs=[
                {
                    "kind": "owner_attested_visible_social_text",
                    "source_url": source_url,
                    "content_sha256": visible_sha256,
                    "capture_method": "owner_supplied_visible_item",
                    "no_scraping": True,
                }
            ],
            confidence=1.0,
            idempotency_key=f"social-assist:{lineage_key}:evidence",
        )
        interpretation = InterpretationLensService(self.store).record_reading(
            evidence_id=str(evidence["evidence_id"]),
            lens_name=INTERPRETATION_LENS_NAME,
            lens_version=INTERPRETATION_LENS_VERSION,
            reading={
                "assessment": "eligible only for owner-controlled social assistance",
                "engagement_type": engagement_type,
                "external_mutation_authorized": False,
                "no_scraping": True,
                "owner_execution_required": True,
                "platform": platform,
            },
            confidence=1.0,
            idempotency_key=f"social-assist:{lineage_key}:assistance-boundary-lens",
            provenance_kind="deterministic_policy",
        )
        return {
            "evidence_id": str(evidence["evidence_id"]),
            "interpretation_id": str(interpretation["interpretation_id"]),
        }

    def _hydrate_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        payload = json.loads(str(event["payload_json"]))
        if not isinstance(payload, dict) or payload.get("schema_version") != OPPORTUNITY_SCHEMA:
            raise SocialEngagementAssistError("stored engagement opportunity schema is unsupported")
        visible_text = self._read_artifact(
            str(payload["visible_text_artifact_id"]),
            expected_sha256=str(payload["visible_text_sha256"]),
        )
        draft_text = self._read_artifact(
            str(payload["draft_artifact_id"]),
            expected_sha256=str(payload["draft_sha256"]),
        )
        lineage = self._stored_projection_lineage(
            source_id=str(payload["source_id"]),
            artifact_id=str(payload["visible_text_artifact_id"]),
        )
        return {
            **payload,
            **lineage,
            "event_id": event["event_id"],
            "visible_text": visible_text,
            "draft_text": draft_text,
            "provenance": json.loads(str(event["provenance_json"])),
            "allowed_actions": sorted(ALLOWED_ASSISTED_ACTIONS),
            "prohibited_backend_actions": sorted(PROHIBITED_PLATFORM_MUTATIONS),
        }

    def _stored_projection_lineage(self, *, source_id: str, artifact_id: str) -> dict[str, str | None]:
        with self.store.connection() as connection:
            evidence = connection.execute(
                """SELECT evidence_id FROM evidence_records
                   WHERE source_id=? AND artifact_id=? AND extractor_name=? AND extractor_version=?
                   ORDER BY created_at DESC, evidence_id DESC LIMIT 1""",
                (source_id, artifact_id, EVIDENCE_EXTRACTOR_NAME, EVIDENCE_EXTRACTOR_VERSION),
            ).fetchone()
            interpretation = (
                connection.execute(
                    """SELECT interpretation_id FROM interpretations
                       WHERE evidence_id=? AND lens_name=? AND lens_version=?
                       ORDER BY created_at DESC, interpretation_id DESC LIMIT 1""",
                    (
                        str(evidence["evidence_id"]),
                        INTERPRETATION_LENS_NAME,
                        INTERPRETATION_LENS_VERSION,
                    ),
                ).fetchone()
                if evidence
                else None
            )
        return {
            "evidence_id": str(evidence["evidence_id"]) if evidence else None,
            "interpretation_id": str(interpretation["interpretation_id"]) if interpretation else None,
        }

    def _read_artifact(self, artifact_id: str, *, expected_sha256: str) -> str:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT logical_ref,content_sha256 FROM artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if not row or str(row["content_sha256"]) != expected_sha256:
            raise SocialEngagementAssistError("private engagement artifact is unavailable or corrupt")
        text = self.artifact_store.read_text(str(row["logical_ref"]))
        if _sha256_text(text) != expected_sha256:
            raise SocialEngagementAssistError("private engagement artifact failed integrity verification")
        return text


def default_social_engagement_assist_service(
    database_path: Path | str | None = None,
) -> SocialEngagementAssistService:
    if database_path is None and any(
        str(os.getenv(name) or "").strip()
        for name in (
            "RAILWAY_PROJECT_ID",
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_SERVICE_ID",
        )
    ):
        raise RemoteSocialAssistAuthorityUnavailable(
            "Remote social assistance is unavailable until its signed local-authority queue is active."
        )
    return SocialEngagementAssistService(IntegratedSystemStore(database_path))
