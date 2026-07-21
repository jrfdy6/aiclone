from __future__ import annotations

from typing import Any

from app.models import PersonaDelta


def metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def metadata_array(metadata: dict[str, Any] | None, key: str) -> list[Any]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    return value if isinstance(value, list) else []


def normalize_promotion_item(item: dict[str, Any], delta: PersonaDelta) -> dict[str, Any] | None:
    content = str(item.get("content") or "").strip()
    if not content:
        return None

    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    target_file = str(item.get("targetFile") or item.get("target_file") or metadata_text(metadata, "target_file") or "").strip()
    if not target_file:
        return None

    evidence = str(item.get("evidence") or "").strip()
    artifact_summary = str(item.get("artifactSummary") or item.get("artifact_summary") or "").strip() or None
    artifact_kind = str(item.get("artifactKind") or item.get("artifact_kind") or "").strip() or None
    artifact_ref = str(item.get("artifactRef") or item.get("artifact_ref") or "").strip() or None
    delta_summary = str(item.get("deltaSummary") or item.get("delta_summary") or delta.trait or "").strip() or None
    review_interpretation = str(
        item.get("reviewInterpretation")
        or item.get("review_interpretation")
        or metadata_text(metadata, "owner_response_excerpt")
        or delta.notes
        or ""
    ).strip() or None
    capability_signal = str(item.get("capabilitySignal") or item.get("capability_signal") or "").strip() or None
    positioning_signal = str(item.get("positioningSignal") or item.get("positioning_signal") or "").strip() or None
    leverage_signal = str(item.get("leverageSignal") or item.get("leverage_signal") or "").strip() or None
    proof_signal = str(item.get("proofSignal") or item.get("proof_signal") or evidence or "").strip() or None
    proof_strength = str(
        item.get("proofStrength")
        or item.get("proof_strength")
        or ("strong" if str(item.get("kind") or "") == "stat" else "weak" if evidence else "none")
    ).strip() or "none"
    gate_decision = str(item.get("gateDecision") or item.get("gate_decision") or "pending").strip() or "pending"
    gate_reason = str(item.get("gateReason") or item.get("gate_reason") or "").strip() or None
    return {
        "id": str(item.get("id") or f"{delta.id}:{target_file}:{content[:32]}").strip(),
        "kind": str(item.get("kind") or "talking_point").strip() or "talking_point",
        "label": str(item.get("label") or "Promoted item").strip() or "Promoted item",
        "content": content,
        "evidence": evidence or None,
        "target_file": target_file,
        "artifact_summary": artifact_summary,
        "artifact_kind": artifact_kind,
        "artifact_ref": artifact_ref,
        "delta_summary": delta_summary,
        "review_interpretation": review_interpretation,
        "capability_signal": capability_signal,
        "positioning_signal": positioning_signal,
        "leverage_signal": leverage_signal,
        "proof_signal": proof_signal,
        "proof_strength": proof_strength,
        "gate_decision": gate_decision,
        "gate_reason": gate_reason,
        "canon_purpose": metadata_text(item, "canon_purpose") if isinstance(item, dict) else None,
        "canon_value": metadata_text(item, "canon_value") if isinstance(item, dict) else None,
        "canon_proof": metadata_text(item, "canon_proof") if isinstance(item, dict) else None,
        "source_delta_id": delta.id,
        "trait": delta.trait,
        "owner_response_kind": metadata_text(metadata, "owner_response_kind"),
        "owner_response_excerpt": metadata_text(metadata, "owner_response_excerpt"),
        "committed_at": delta.committed_at.isoformat() if delta.committed_at else None,
        "created_at": delta.created_at.isoformat() if delta.created_at else None,
    }


def normalize_selected_promotion_items(delta: PersonaDelta) -> list[dict[str, Any]]:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    committed_items = [entry for entry in metadata_array(metadata, "committed_promotion_items") if isinstance(entry, dict)]
    selected_items = [entry for entry in metadata_array(metadata, "selected_promotion_items") if isinstance(entry, dict)]
    raw_items = committed_items or selected_items
    return [item for item in (normalize_promotion_item(entry, delta) for entry in raw_items) if item]
