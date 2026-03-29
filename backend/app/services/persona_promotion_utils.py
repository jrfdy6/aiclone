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
    target_file = str(item.get("targetFile") or metadata_text(metadata, "target_file") or "").strip()
    if not target_file:
        return None

    evidence = str(item.get("evidence") or metadata_text(metadata, "owner_response_excerpt") or delta.notes or "").strip()
    return {
        "id": str(item.get("id") or f"{delta.id}:{target_file}:{content[:32]}").strip(),
        "kind": str(item.get("kind") or "talking_point").strip() or "talking_point",
        "label": str(item.get("label") or "Promoted item").strip() or "Promoted item",
        "content": content,
        "evidence": evidence or None,
        "target_file": target_file,
        "source_delta_id": delta.id,
        "trait": delta.trait,
        "owner_response_kind": metadata_text(metadata, "owner_response_kind"),
        "owner_response_excerpt": metadata_text(metadata, "owner_response_excerpt"),
        "committed_at": delta.committed_at.isoformat() if delta.committed_at else None,
        "created_at": delta.created_at.isoformat() if delta.created_at else None,
    }


def normalize_selected_promotion_items(delta: PersonaDelta) -> list[dict[str, Any]]:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    selected_items = [entry for entry in metadata_array(metadata, "selected_promotion_items") if isinstance(entry, dict)]
    return [item for item in (normalize_promotion_item(entry, delta) for entry in selected_items) if item]
