from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import PersonaDelta, PersonaDeltaUpdate
from app.persona_promotion_targets import (
    TARGET_CLAIMS,
    TARGET_CONTENT_PILLARS,
    TARGET_DECISION_PRINCIPLES,
    TARGET_INITIATIVES,
    TARGET_STORIES,
    TARGET_VOICE,
    validate_persona_promotion_target,
)
from app.services import persona_delta_service
from app.services.persona_promotion_extractor import extract_canonical_promotion_items
from app.services.persona_promotion_utils import (
    metadata_array,
    metadata_text,
    normalize_selected_promotion_items,
)

ALLOWED_REROUTE_TARGETS = {
    TARGET_CLAIMS,
    TARGET_VOICE,
    TARGET_DECISION_PRINCIPLES,
    TARGET_CONTENT_PILLARS,
    TARGET_STORIES,
}


def build_committed_persona_overlay(limit: int = 500) -> dict[str, Any]:
    try:
        deltas = persona_delta_service.list_deltas(limit=limit, status="committed")
    except Exception:
        deltas = []
    by_target_file: dict[str, list[dict[str, Any]]] = {}
    counts = {"items": 0, "deltas": 0}

    for delta in deltas:
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        selected_items = metadata_array(metadata, "selected_promotion_items")
        if not selected_items:
            continue
        counts["deltas"] += 1
        extracted_items = extract_canonical_promotion_items(normalize_selected_promotion_items(delta))
        for item in extracted_items:
            if not isinstance(item, dict):
                continue
            try:
                target_file = validate_persona_promotion_target(str(item.get("target_file") or ""))
            except ValueError:
                continue
            if target_file is None:  # pragma: no cover - required targets never return None
                continue
            item["target_file"] = target_file
            bucket = by_target_file.setdefault(target_file, [])
            duplicate = any(
                existing.get("content") == item["content"] and existing.get("label") == item["label"]
                for existing in bucket
            )
            if duplicate:
                continue
            bucket.append(item)
            counts["items"] += 1

    for items in by_target_file.values():
        items.sort(
            key=lambda item: (
                item.get("committed_at") or "",
                item.get("created_at") or "",
                item.get("label") or "",
            ),
            reverse=True,
        )

    counts["target_files"] = len(by_target_file)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "by_target_file": by_target_file,
    }


def promote_delta_to_canon(delta_id: str) -> PersonaDelta | None:
    delta = persona_delta_service.get_delta(delta_id)
    if delta is None:
        return None

    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    if delta.status != "approved" or not metadata.get("pending_promotion"):
        raise ValueError("Canon commit requires an owner-approved pending promotion.")
    selected_items = [entry for entry in metadata_array(metadata, "selected_promotion_items") if isinstance(entry, dict)]
    if not selected_items:
        raise ValueError("This review item has no selected promotion items.")

    normalized_items = normalize_selected_promotion_items(delta)
    if not normalized_items:
        raise ValueError("Selected promotion items are missing canonical target information.")
    for item in normalized_items:
        target_file = validate_persona_promotion_target(str(item.get("target_file") or ""))
        if target_file is None:  # pragma: no cover - required targets never return None
            raise ValueError("Selected promotion items are missing canonical target information.")
        item["target_file"] = target_file
    extracted_items = extract_canonical_promotion_items(normalized_items)
    blocked_initiatives = [
        item
        for item in extracted_items
        if item.get("target_file") == TARGET_INITIATIVES and item.get("gate_decision") != "allow"
    ]
    if blocked_initiatives:
        reasons = sorted({str(item.get("gate_reason") or "Initiatives canon requires artifact-backed proof.") for item in blocked_initiatives})
        raise ValueError("Cannot commit to initiatives canon: " + " ".join(reasons))

    committed_at = datetime.now(timezone.utc).isoformat()
    update_metadata = {
        "pending_promotion": False,
        "promotion_state": "committed",
        "promotion_committed_at": committed_at,
        "committed_target_files": sorted({item["target_file"] for item in extracted_items}),
        "committed_item_count": len(extracted_items),
        "selected_promotion_items": selected_items,
        "selected_promotion_item_ids": [item["id"] for item in extracted_items if item.get("id")],
        "committed_promotion_items": extracted_items,
        "local_bundle_sync": {
            "state": "pending",
            "updated_at": committed_at,
        },
    }
    update = PersonaDeltaUpdate(status="committed", metadata=update_metadata)
    return persona_delta_service.update_delta(delta_id, update)


def reroute_delta_promotion(delta_id: str, *, target_file: str) -> PersonaDelta | None:
    delta = persona_delta_service.get_delta(delta_id)
    if delta is None:
        return None

    normalized_target = validate_persona_promotion_target(target_file)
    if normalized_target is None:  # pragma: no cover - required targets never return None
        raise ValueError("Unsupported reroute target.")
    if normalized_target not in ALLOWED_REROUTE_TARGETS:
        raise ValueError("Unsupported reroute target.")

    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    if not metadata.get("pending_promotion"):
        raise ValueError("Only queued promotion items can be rerouted.")

    selected_items = [entry for entry in metadata_array(metadata, "selected_promotion_items") if isinstance(entry, dict)]
    if not selected_items:
        raise ValueError("This review item has no selected promotion items to reroute.")

    current_target = metadata_text(metadata, "target_file")
    if current_target == normalized_target and all(str(item.get("targetFile") or "").strip() == normalized_target for item in selected_items):
        return delta

    rerouted_items: list[dict[str, Any]] = []
    reroute_reason = (
        f"Rerouted from {current_target or 'the previous target'} to {normalized_target} for canon review."
    )
    for item in selected_items:
        rerouted = dict(item)
        rerouted["targetFile"] = normalized_target
        rerouted["gateDecision"] = "allow"
        rerouted["gateReason"] = reroute_reason
        rerouted_items.append(rerouted)

    rerouted_at = datetime.now(timezone.utc).isoformat()
    update_metadata = {
        "target_file": normalized_target,
        "selected_promotion_items": rerouted_items,
        "selected_promotion_item_ids": [str(item.get("id") or "") for item in rerouted_items if str(item.get("id") or "")],
        "selected_promotion_count": len(rerouted_items),
        "promotion_state": "rerouted",
        "pending_promotion": True,
        "rerouted_at": rerouted_at,
        "rerouted_from_target_file": current_target,
        "rerouted_target_file": normalized_target,
        "last_reviewed_at": rerouted_at,
    }
    update = PersonaDeltaUpdate(status="approved", metadata=update_metadata)
    return persona_delta_service.update_delta(delta_id, update)
