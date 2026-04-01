from __future__ import annotations

from typing import Any


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _ensure_store(ctx: dict[str, Any]) -> dict[str, Any]:
    store = ctx.setdefault("_composition_trace", {})
    store.setdefault("options", {})
    store.setdefault("templates", {})
    store.setdefault("responses", {})
    return store


class SocialTemplateCompositionService:
    def record_option(
        self,
        ctx: dict[str, Any],
        *,
        slot: str,
        options: list[str],
        selected: str,
        selected_index: int,
    ) -> None:
        store = _ensure_store(ctx)
        store["options"][slot] = {
            "slot": slot,
            "selected": _normalize_inline_text(selected),
            "selected_index": selected_index,
            "option_count": len(options),
            "options": [_normalize_inline_text(item) for item in options],
        }

    def record_template(
        self,
        ctx: dict[str, Any],
        *,
        slot: str,
        templates: list[list[str]],
        selected: list[str],
    ) -> None:
        store = _ensure_store(ctx)
        store["templates"][slot] = {
            "slot": slot,
            "selected": list(selected),
            "template_count": len(templates),
        }

    def record_response(
        self,
        ctx: dict[str, Any],
        *,
        slot: str,
        response_kind: str,
        normalized_parts: dict[str, str],
        selected_template: list[str],
        part_order: list[str],
        text: str,
    ) -> None:
        store = _ensure_store(ctx)
        store["responses"][response_kind] = {
            "slot": slot,
            "response_kind": response_kind,
            "normalized_parts": dict(normalized_parts),
            "selected_template": list(selected_template),
            "part_order": list(part_order),
            "pre_normalization_text": _normalize_inline_text(text),
        }

    def build_trace(
        self,
        ctx: dict[str, Any],
        *,
        response_kind: str,
        post_normalization_text: str,
    ) -> dict[str, Any]:
        store = _ensure_store(ctx)
        response_trace = dict((store.get("responses") or {}).get(response_kind) or {})
        options = store.get("options") or {}
        template_slot = str(response_trace.get("slot") or "")
        selected_parts = list(response_trace.get("part_order") or [])
        pre_text = _normalize_inline_text(response_trace.get("pre_normalization_text"))
        post_text = _normalize_inline_text(post_normalization_text)

        def selected_for(slot_fragment: str) -> str:
            for slot, payload in options.items():
                if slot_fragment in slot:
                    return _normalize_inline_text(payload.get("selected"))
            return ""

        normalization_actions: list[str] = []
        if pre_text and post_text and pre_text != post_text:
            normalization_actions.append("voice_normalized")

        trace = {
            "response_kind": response_kind,
            "template_family": template_slot or f"{response_kind}-template",
            "template_slots": list(response_trace.get("selected_template") or []),
            "selected_open_family": "response_open",
            "selected_takeaway_family": "source_takeaway" if "takeaway" in selected_parts else "",
            "selected_bridge_family": "bridge_line" if "bridge" in selected_parts else "",
            "selected_contrast_family": "stance_contrast" if "contrast" in selected_parts else "",
            "selected_main_family": "lane_main",
            "selected_close_family": "lane_close" if "close" in selected_parts else "",
            "selected_parts": selected_parts,
            "part_order": selected_parts,
            "omitted_parts": [part for part in ["open", "takeaway", "bridge", "contrast", "main", "close"] if part not in selected_parts],
            "part_selection_rationale": [
                f"open={selected_for('open') or 'missing'}",
                f"main={selected_for('-main') or 'implicit'}",
                f"close={selected_for('-close') or 'implicit'}",
            ],
            "pre_normalization_text": pre_text,
            "post_normalization_text": post_text,
            "normalization_actions": normalization_actions,
            "repetition_flags": [],
            "missing_fields": [field for field, value in {
                "template_family": template_slot,
                "selected_parts": selected_parts,
                "selected_main_family": "lane_main" if selected_parts else "",
            }.items() if not value],
        }
        return trace


social_template_composition_service = SocialTemplateCompositionService()
