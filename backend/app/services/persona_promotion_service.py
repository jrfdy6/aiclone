from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import PersonaDelta, PersonaDeltaUpdate
from app.services import persona_delta_service

TARGET_CLAIMS = "identity/claims.md"
TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_DECISION_PRINCIPLES = "identity/decision_principles.md"
TARGET_CONTENT_PILLARS = "prompts/content_pillars.md"
TARGET_STORIES = "history/story_bank.md"
TARGET_INITIATIVES = "history/initiatives.md"


def _metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_array(metadata: dict[str, Any] | None, key: str) -> list[Any]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    return value if isinstance(value, list) else []


def _normalize_promotion_item(item: dict[str, Any], delta: PersonaDelta) -> dict[str, Any] | None:
    content = str(item.get("content") or "").strip()
    if not content:
        return None

    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    target_file = str(item.get("targetFile") or _metadata_text(metadata, "target_file") or "").strip()
    if not target_file:
        return None

    evidence = str(item.get("evidence") or _metadata_text(metadata, "owner_response_excerpt") or delta.notes or "").strip()
    return {
        "id": str(item.get("id") or f"{delta.id}:{target_file}:{content[:32]}").strip(),
        "kind": str(item.get("kind") or "talking_point").strip() or "talking_point",
        "label": str(item.get("label") or "Promoted item").strip() or "Promoted item",
        "content": content,
        "evidence": evidence or None,
        "target_file": target_file,
        "source_delta_id": delta.id,
        "trait": delta.trait,
        "owner_response_kind": _metadata_text(metadata, "owner_response_kind"),
        "owner_response_excerpt": _metadata_text(metadata, "owner_response_excerpt"),
        "committed_at": delta.committed_at.isoformat() if delta.committed_at else None,
        "created_at": delta.created_at.isoformat() if delta.created_at else None,
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
        selected_items = _metadata_array(metadata, "selected_promotion_items")
        if not selected_items:
            continue
        counts["deltas"] += 1
        for entry in selected_items:
            if not isinstance(entry, dict):
                continue
            normalized = _normalize_promotion_item(entry, delta)
            if not normalized:
                continue
            target_file = normalized["target_file"]
            bucket = by_target_file.setdefault(target_file, [])
            duplicate = any(
                existing.get("content") == normalized["content"] and existing.get("label") == normalized["label"]
                for existing in bucket
            )
            if duplicate:
                continue
            bucket.append(normalized)
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
    selected_items = [entry for entry in _metadata_array(metadata, "selected_promotion_items") if isinstance(entry, dict)]
    if not selected_items:
        raise ValueError("This review item has no selected promotion items.")

    normalized_items = [item for item in (_normalize_promotion_item(entry, delta) for entry in selected_items) if item]
    if not normalized_items:
        raise ValueError("Selected promotion items are missing canonical target information.")

    committed_at = datetime.now(timezone.utc).isoformat()
    update_metadata = {
        "pending_promotion": False,
        "promotion_state": "committed",
        "promotion_committed_at": committed_at,
        "committed_target_files": sorted({item["target_file"] for item in normalized_items}),
        "committed_item_count": len(normalized_items),
        "selected_promotion_items": selected_items,
        "selected_promotion_item_ids": [item["id"] for item in normalized_items if item.get("id")],
    }
    update = PersonaDeltaUpdate(status="committed", metadata=update_metadata)
    return persona_delta_service.update_delta(delta_id, update)
