from __future__ import annotations

from typing import Any, Mapping

from app.services.content_learning_service import ContentLearningService
from app.services.content_lifecycle_service import ContentLifecycleService


OWNER_LEARNING_ACTIONS = frozenset(
    {"variant_selected", "variant_rejected", "owner_approved", "publication_confirmed"}
)


class ContentOwnerActionService:
    """Apply exact owner actions to the canonical local content lifecycle."""

    def __init__(self, lifecycle: ContentLifecycleService) -> None:
        self.lifecycle = lifecycle
        self.learning = ContentLearningService(lifecycle.store)

    def record_manual_edit(
        self,
        *,
        post_id: str,
        parent_revision_id: str,
        body: str,
        edit_classification: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        revision_key = f"content-edit:{idempotency_key}"
        self.lifecycle.create_manual_edit(
            post_id=post_id,
            parent_revision_id=parent_revision_id,
            body=body,
            edit_classification=edit_classification,
            idempotency_key=revision_key,
        )
        with self.lifecycle.store.connection() as connection:
            revision = connection.execute(
                """SELECT r.*,a.content_sha256 FROM content_revisions r
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE r.idempotency_key=?""",
                (revision_key,),
            ).fetchone()
        if not revision:
            raise RuntimeError("manual edit revision was not persisted")
        learning_event = self.learning.record(
            post_id=post_id,
            revision_id=revision["revision_id"],
            event_kind="manual_edit",
            edit_classification=edit_classification,
            payload={
                "changed_by_owner": True,
                "parent_revision_id": parent_revision_id,
                "revision_sha256": revision["content_sha256"],
            },
            idempotency_key=f"content-edit-learning:{idempotency_key}",
        )
        return {
            "action": "manual_edit",
            "post_id": post_id,
            "revision_id": revision["revision_id"],
            "revision_sha256": revision["content_sha256"],
            "learning_event_id": learning_event["learning_event_id"],
        }

    def record_learning_action(
        self,
        *,
        post_id: str,
        revision_id: str,
        event_kind: str,
        revision_sha256: str,
        owner_confirmed: bool,
        event_at: str | None,
        integrity_confirmation: Mapping[str, bool] | None,
        platform: str | None,
        public_url: str | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if event_kind not in OWNER_LEARNING_ACTIONS:
            raise ValueError("unsupported owner content action")
        if owner_confirmed is not True:
            raise ValueError("owner content action requires explicit owner confirmation")
        if event_kind == "variant_selected":
            payload: dict[str, Any] = {
                "selected_by_owner": True,
                "revision_sha256": revision_sha256,
            }
        elif event_kind == "variant_rejected":
            payload = {
                "rejected_by_owner": True,
                "revision_sha256": revision_sha256,
            }
        elif event_kind == "owner_approved":
            payload = {
                "approved_by_owner": True,
                "revision_sha256": revision_sha256,
                "approved_at": event_at,
                "integrity_confirmation": dict(integrity_confirmation or {}),
            }
        else:
            payload = {
                "confirmed_by_owner": True,
                "revision_sha256": revision_sha256,
                "platform": platform,
                "public_url": public_url,
                "published_at": event_at,
            }
        learning_event = self.learning.record(
            post_id=post_id,
            revision_id=revision_id,
            event_kind=event_kind,
            payload=payload,
            idempotency_key=f"content-owner-action:{idempotency_key}",
        )
        return {
            "action": event_kind,
            "post_id": post_id,
            "revision_id": revision_id,
            "learning_event_id": learning_event["learning_event_id"],
            "occurred_at": learning_event["occurred_at"],
        }
