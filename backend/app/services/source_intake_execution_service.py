from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from app.services.content_lifecycle_service import PrivateContentArtifactStore
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.source_intake_adapter_service import SourceAdapterEnvelope, SourceIntakeAdapterService
from app.services.source_processing_service import SourceProcessingService


RECEIPT_DISPOSITIONS = frozenset({"complete", "no_change", "degraded", "failed"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class SourceIntakeExecutionService:
    """One ordered entrypoint for registration, gates, capture reuse, and run receipts.

    Feed adapters may perform the minimum network read needed to discover an item,
    but deep capture, transcription, extraction, and writable projections must not
    start until :meth:`register_and_gate` authorizes them.
    """

    def __init__(
        self,
        store: IntegratedSystemStore,
        artifacts: PrivateContentArtifactStore | None = None,
    ) -> None:
        self.store = store
        self.artifacts = artifacts or PrivateContentArtifactStore(store.database_path.parent / "artifacts")
        self.adapter = SourceIntakeAdapterService(store)
        self.processing = SourceProcessingService(store, self.artifacts)

    def register_and_gate(
        self,
        envelope: SourceAdapterEnvelope,
        *,
        relevance_state: str,
        admissibility_state: str,
        reason: str,
        policy_name: str,
        policy_version: str = "1.0.0",
        capture_kind: str = "raw",
    ) -> dict[str, Any]:
        registration = self.adapter.register(envelope)
        gate = self.processing.qualify(
            discovery_id=registration["discovery"]["discovery_id"],
            relevance_state=relevance_state,
            admissibility_state=admissibility_state,
            reason=reason,
            policy_name=policy_name,
            policy_version=policy_version,
        )
        decision = self.processing.processing_decision(
            source_id=registration["source"]["source_id"],
            discovery_id=registration["discovery"]["discovery_id"],
            capture_kind=capture_kind,
        )
        return {"registration": registration, "gate": gate, "decision": decision}

    def captured_text(self, artifact_id: str) -> str:
        with self.store.connection() as connection:
            artifact = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if not artifact:
            raise ValueError("canonical capture artifact is missing")
        text = self.artifacts.read_text(str(artifact["logical_ref"]))
        encoded = text.encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != artifact["content_sha256"]:
            raise ValueError("canonical capture artifact hash mismatch")
        if len(encoded) != artifact["byte_size"]:
            raise ValueError("canonical capture artifact size mismatch")
        return text

    def attach_or_reuse_text(
        self,
        prepared: Mapping[str, Any],
        *,
        text: str,
        capture_kind: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = dict(prepared.get("decision") or {})
        existing_artifact_id = str(decision.get("existing_artifact_id") or "").strip()
        if existing_artifact_id:
            return {
                "source_id": decision["source_id"],
                "artifact_id": existing_artifact_id,
                "text": self.captured_text(existing_artifact_id),
                "reused": True,
            }
        if not decision.get("capture_required"):
            raise ValueError("source has not passed canonical expensive-processing gates")
        captured = self.processing.attach_captured_text(
            source_id=str(decision["source_id"]),
            text=text,
            capture_kind=capture_kind,
            metadata=metadata,
        )
        return {
            "source_id": captured["source_id"],
            "artifact_id": captured["artifact"]["artifact_id"],
            "text": text,
            "reused": bool(captured["reused"]),
            "merged_source_ids": list(captured.get("merged_source_ids") or []),
        }

    def record_run_receipt(
        self,
        *,
        run_kind: str,
        disposition: str,
        counts: Mapping[str, int],
        errors: list[Mapping[str, Any]] | None = None,
        run_id: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_kind = "_".join(str(run_kind or "").strip().lower().split())
        if not normalized_kind:
            raise ValueError("source intake run kind is required")
        if disposition not in RECEIPT_DISPOSITIONS:
            raise ValueError("invalid source intake receipt disposition")
        normalized_counts = {str(key): int(value) for key, value in counts.items()}
        compact_errors = [
            {
                str(key): value
                for key, value in error.items()
                if key in {"stage", "reason", "error_class", "source_ref"}
                and isinstance(value, (str, int, float, bool))
            }
            for error in (errors or [])[:20]
        ]
        occurred_at = _utcnow()
        effective_run_id = str(run_id or occurred_at).strip()
        payload = {
            "schema_version": "source_intake_run_receipt/v1",
            "run_id": effective_run_id,
            "run_kind": normalized_kind,
            "disposition": disposition,
            "counts": normalized_counts,
            "errors": compact_errors,
        }
        fingerprint = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:24]
        return self.store.append_event(
            event_type="source.intake_run_receipt",
            aggregate_type="source_intake_run",
            aggregate_id=f"{normalized_kind}:{effective_run_id}",
            actor_type="source_intake_scheduler",
            payload=payload,
            provenance={"receipt_version": "1.0.0", **dict(provenance or {})},
            idempotency_key=f"source-intake-run:{normalized_kind}:{effective_run_id}:{fingerprint}",
            occurred_at=occurred_at,
        )
