from __future__ import annotations

import re
from typing import Any


TARGET_INITIATIVES = "history/initiatives.md"

_METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?(?:x|%|k|m|b)?\b", re.IGNORECASE)


def _normalize_inline(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).replace("\xa0", " ").split()).strip()


def _ensure_period(text: str | None) -> str:
    normalized = _normalize_inline(text)
    if not normalized:
        return ""
    return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."


def _has_metric(text: str | None) -> bool:
    normalized = _normalize_inline(text)
    if not normalized:
        return False
    return bool(_METRIC_RE.search(normalized))


def _first_text(*values: Any) -> str | None:
    for value in values:
        normalized = _normalize_inline(str(value) if value is not None else "")
        if normalized:
            return normalized
    return None


def _contains_any(text: str | None, needles: tuple[str, ...]) -> bool:
    normalized = _normalize_inline(text).lower()
    if not normalized:
        return False
    return any(needle in normalized for needle in needles)


def _infer_artifact_summary(item: dict[str, Any]) -> str | None:
    existing = _first_text(item.get("artifact_summary"))
    if existing:
        return existing
    kind = _normalize_inline(str(item.get("kind") or "")).lower()
    content = _first_text(item.get("content"))
    evidence = _first_text(item.get("evidence"))
    if kind == "stat" and content:
        return content
    if kind == "anecdote" and evidence and _has_metric(evidence):
        return evidence
    return None


def _infer_artifact_kind(item: dict[str, Any], artifact_summary: str | None) -> str | None:
    existing = _first_text(item.get("artifact_kind"))
    if existing:
        return existing
    kind = _normalize_inline(str(item.get("kind") or "")).lower()
    if kind == "stat":
        return "metric_or_proof_point"
    if artifact_summary:
        return "artifact_signal"
    return None


def _infer_proof_signal(item: dict[str, Any], artifact_summary: str | None) -> str | None:
    existing = _first_text(item.get("proof_signal"))
    if existing:
        return existing
    return _first_text(artifact_summary, item.get("evidence"), item.get("content"))


def _infer_proof_strength(item: dict[str, Any], artifact_summary: str | None, proof_signal: str | None) -> str:
    existing = _normalize_inline(str(item.get("proof_strength") or "")).lower()
    if existing in {"none", "weak", "strong"}:
        if existing == "strong" and (artifact_summary or _has_metric(proof_signal)):
            return "strong"
        if existing in {"weak", "none"}:
            return existing
    if artifact_summary and (_has_metric(artifact_summary) or _has_metric(proof_signal) or item.get("artifact_ref")):
        return "strong"
    if artifact_summary or proof_signal:
        return "weak"
    return "none"


def _infer_capability_signal(item: dict[str, Any]) -> str | None:
    existing = _first_text(item.get("capability_signal"))
    if existing:
        return existing
    text = _first_text(item.get("artifact_summary"), item.get("proof_signal"), item.get("content"), item.get("delta_summary"))
    if _contains_any(text, ("ai", "agent", "prompt", "model", "workflow", "system")):
        return "Builds and translates AI execution patterns into clear operator guidance."
    if _contains_any(text, ("team", "leadership", "enablement", "process")):
        return "Turns operating patterns into practical guidance for teams and execution."
    return "Adds a usable operating signal that can support future public explanation."


def _infer_positioning_signal(item: dict[str, Any]) -> str | None:
    existing = _first_text(item.get("positioning_signal"))
    if existing:
        return existing
    text = _first_text(item.get("artifact_summary"), item.get("proof_signal"), item.get("content"))
    if _contains_any(text, ("ai", "agent", "prompt", "model")):
        return "Strengthens Johnnie's positioning as an AI systems operator grounded in real execution."
    if _contains_any(text, ("workflow", "process", "system")):
        return "Strengthens Johnnie's positioning as an operator who can connect systems thinking to real implementation."
    return "Strengthens Johnnie's positioning with a concrete, reusable operating signal."


def _infer_leverage_signal(item: dict[str, Any]) -> str | None:
    existing = _first_text(item.get("leverage_signal"))
    if existing:
        return existing
    text = _first_text(item.get("artifact_summary"), item.get("proof_signal"), item.get("content"))
    if _contains_any(text, ("ai", "agent", "prompt", "workflow", "system")):
        return "Creates reusable proof for future writing, planning, and persona claims about AI execution and workflow clarity."
    return "Creates reusable proof that can support future positioning, writing, and canon updates."


def _compose_canon_value(item: dict[str, Any]) -> str | None:
    capability = _first_text(item.get("capability_signal"))
    positioning = _first_text(item.get("positioning_signal"))
    leverage = _first_text(item.get("leverage_signal"))
    pieces = [piece for piece in [capability, positioning, leverage] if piece]
    if not pieces:
        return None
    return " ".join(dict.fromkeys(pieces))


def _compose_canon_purpose(item: dict[str, Any]) -> str | None:
    return _first_text(item.get("artifact_summary"), item.get("content"), item.get("delta_summary"))


def _compose_canon_proof(item: dict[str, Any]) -> str | None:
    return _first_text(item.get("proof_signal"), item.get("artifact_summary"), item.get("evidence"))


def _gate_item(item: dict[str, Any]) -> tuple[str, str | None]:
    target_file = _normalize_inline(str(item.get("target_file") or "")).lower()
    existing_decision = _normalize_inline(str(item.get("gate_decision") or "")).lower()
    if target_file != TARGET_INITIATIVES:
        return (existing_decision if existing_decision in {"allow", "hold", "block"} else "allow", _first_text(item.get("gate_reason")))

    has_artifact_anchor = bool(_first_text(item.get("artifact_summary"), item.get("artifact_ref"), item.get("artifact_kind")))
    proof_strength = _normalize_inline(str(item.get("proof_strength") or "")).lower()
    if has_artifact_anchor and proof_strength == "strong":
        return ("allow", _first_text(item.get("gate_reason")) or "Artifact-backed proof is present.")
    if has_artifact_anchor:
        return ("hold", _first_text(item.get("gate_reason")) or "Artifact anchor exists, but proof strength is not strong enough for initiatives canon.")
    return ("block", _first_text(item.get("gate_reason")) or "Initiatives canon requires an explicit artifact or output anchor.")


def extract_canonical_promotion_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        artifact_summary = _infer_artifact_summary(item)
        artifact_kind = _infer_artifact_kind(item, artifact_summary)
        proof_signal = _infer_proof_signal(item, artifact_summary)
        proof_strength = _infer_proof_strength(item, artifact_summary, proof_signal)
        item["artifact_summary"] = artifact_summary
        item["artifact_kind"] = artifact_kind
        item["artifact_ref"] = _first_text(item.get("artifact_ref"))
        item["delta_summary"] = _first_text(item.get("delta_summary"), item.get("trait"))
        item["review_interpretation"] = _first_text(item.get("review_interpretation"), item.get("owner_response_excerpt"))
        item["proof_signal"] = proof_signal
        item["proof_strength"] = proof_strength
        item["capability_signal"] = _infer_capability_signal(item)
        item["positioning_signal"] = _infer_positioning_signal(item)
        item["leverage_signal"] = _infer_leverage_signal(item)
        item["canon_purpose"] = _ensure_period(_compose_canon_purpose(item))
        item["canon_value"] = _ensure_period(_compose_canon_value(item))
        item["canon_proof"] = _ensure_period(_compose_canon_proof(item))
        gate_decision, gate_reason = _gate_item(item)
        item["gate_decision"] = gate_decision
        item["gate_reason"] = gate_reason
        extracted.append(item)
    return extracted
