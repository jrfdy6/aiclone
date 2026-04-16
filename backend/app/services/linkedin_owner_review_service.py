from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import PMCardCreate, PMCardDispatchRequest, PMCardUpdate
from app.services import pm_card_service, workspace_snapshot_service
from app.services.pm_execution_contract_service import build_execution_contract

QUEUE_HEADING_RE = re.compile(r"^###\s+(FEEZIE-\d+)\s*-\s*(.+)$", flags=re.MULTILINE)
PACKET_HEADING_RE = re.compile(r"^##\s+(FEEZIE-\d+)\s+[—-]\s+(.+)$", flags=re.MULTILINE)

STATUS_MAP = {
    "approve": "approved",
    "revise": "revision_requested",
    "park": "parked",
}

APPROVAL_STATUS_MAP = {
    "approve": "owner_approved",
    "revise": "owner_revision_requested",
    "park": "owner_parked",
}

PUBLISH_POSTURE_MAP = {
    "approve": "approved",
    "revise": "owner_review_required",
    "park": "hold_private",
}

PACKET_CHECKBOX_LINES = {
    "approve": "Approve for scheduling",
    "revise": "Revise (note specifics below)",
    "park": "Park for later",
}

PM_WORKSPACE_KEY = "linkedin-os"
OWNER_REVIEW_CARD_SOURCE = "openclaw:workspace-owner-review"
OWNER_REVIEW_LINK_TYPE = "owner_review"
SUPPLEMENTAL_OWNER_REVIEW_SOURCE_KINDS = {"latent_transform"}
SUPPLEMENTAL_OWNER_REVIEW_ID_PREFIX = "LATENT"


def _owner_review_link_id() -> str | None:
    return None


def _linkedin_root() -> Path:
    return workspace_snapshot_service._discover_linkedin_root()


def _queue_path(root: Path) -> Path:
    return root / "drafts" / "queue_01.md"


def _drafts_root(root: Path) -> Path:
    return root / "drafts"


def _latest_owner_packet(root: Path) -> Path | None:
    packets = sorted(_drafts_root(root).glob("feezie_owner_review_packet_*.md"))
    return packets[-1] if packets else None


def _execution_log_path(root: Path) -> Path:
    return root / "memory" / "execution_log.md"


def _read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _clean_markdown_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1]
    return cleaned


def _compact_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _supplemental_queue_id(title: str, draft_rel_path: str) -> str:
    title_slug = _compact_slug(title)
    short_title = "-".join(part for part in title_slug.split("-") if part)[:36].strip("-")
    digest = hashlib.sha1(draft_rel_path.encode("utf-8")).hexdigest()[:6].upper()
    if short_title:
        return f"{SUPPLEMENTAL_OWNER_REVIEW_ID_PREFIX}-{short_title.upper()}-{digest}"
    return f"{SUPPLEMENTAL_OWNER_REVIEW_ID_PREFIX}-{digest}"


def _section_bounds(text: str, heading_re: re.Pattern[str], queue_id: str) -> tuple[int, int] | None:
    matches = list(heading_re.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1).strip() != queue_id:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return match.start(), end
    return None


def _split_queue_blocks(section: str) -> list[tuple[str, str, str]]:
    matches = list(QUEUE_HEADING_RE.finditer(section))
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        blocks.append((match.group(1).strip(), match.group(2).strip(), section[start:end].strip()))
    return blocks


def _parse_bullet_fields(block: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    fields: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped and not line.startswith("  "):
            key, value = stripped[2:].split(":", 1)
            current_key = key.strip().lower()
            fields[current_key] = _clean_markdown_value(value)
            continue
        if current_key and stripped.startswith("- ") and line.startswith("  "):
            lists.setdefault(current_key, []).append(_clean_markdown_value(stripped[2:]))
            continue
        if current_key and line.startswith("  ") and stripped:
            existing = fields.get(current_key, "")
            fields[current_key] = f"{existing}\n{_clean_markdown_value(stripped)}".strip()
    return fields, lists


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    frontmatter_text = text[4:end]
    body = text[end + 5 :]
    fields: dict[str, str] = {}
    for raw_line in frontmatter_text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields, body


def _yaml_scalar(value: str) -> str:
    if not value:
        return '""'
    if re.search(r"[:#\s]", value):
        return json.dumps(value)
    return value


def _set_frontmatter_fields(text: str, updates: dict[str, str]) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    frontmatter_lines = text[4:end].splitlines()
    body = text[end + 5 :]
    keys_seen: set[str] = set()
    updated_lines: list[str] = []
    for line in frontmatter_lines:
        if ":" not in line:
            updated_lines.append(line)
            continue
        key, _ = line.split(":", 1)
        normalized_key = key.strip()
        if normalized_key in updates:
            updated_lines.append(f"{normalized_key}: {_yaml_scalar(updates[normalized_key])}")
            keys_seen.add(normalized_key)
        else:
            updated_lines.append(line)
    for key, value in updates.items():
        if key in keys_seen:
            continue
        updated_lines.append(f"{key}: {_yaml_scalar(value)}")
    return f"---\n{'\n'.join(updated_lines)}\n---\n{body}"


def _extract_section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", text[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def _extract_packet_section(packet_text: str, queue_id: str) -> str:
    bounds = _section_bounds(packet_text, PACKET_HEADING_RE, queue_id)
    if bounds is None:
        return ""
    start, end = bounds
    return packet_text[start:end].strip()


def _parse_packet_decision(section: str) -> tuple[str | None, str | None, str | None]:
    current_decision: str | None = None
    for decision, label in PACKET_CHECKBOX_LINES.items():
        if re.search(rf"^- \[[xX]\]\s+{re.escape(label)}\s*$", section, flags=re.MULTILINE):
            current_decision = decision
            break
    recommendation_match = re.search(r"\*\*Recommended action:\*\*\s*(.+)", section)
    notes_match = re.search(r"\*\*Revision notes \(if needed\):\*\*\n(.*?)(?:\n---\n|\Z)", section, flags=re.DOTALL)
    notes = notes_match.group(1).strip() if notes_match else ""
    if notes == "---":
        notes = ""
    return current_decision, recommendation_match.group(1).strip() if recommendation_match else None, notes or None


def _normalize_relative_path(root: Path, raw_path: str) -> str:
    cleaned = _clean_markdown_value(raw_path)
    if not cleaned:
        return ""
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    if cleaned.startswith("drafts/"):
        return cleaned
    try:
        return Path(cleaned).resolve().relative_to(root).as_posix()
    except Exception:
        return cleaned


def _draft_path_from_status(root: Path, status_value: str) -> tuple[str, Path | None]:
    match = re.search(r"\(([^)]+)\)", status_value)
    if not match:
        return "", None
    relative_path = _normalize_relative_path(root, match.group(1))
    if not relative_path:
        return "", None
    return relative_path, root / relative_path


def _assessment_recommendation_text(item: dict[str, Any]) -> str:
    return re.sub(r"\*+", "", str(item.get("packet_recommendation") or "")).strip()


def _build_owner_review_assessment(item: dict[str, Any]) -> dict[str, Any]:
    recommendation_text = _assessment_recommendation_text(item)
    recommendation_lower = recommendation_text.lower()
    source_kind = str(item.get("source_kind") or "").strip()
    latent_reason = str(item.get("latent_reason") or "").strip()
    first_pass_draft = str(item.get("first_pass_draft") or "").strip()
    proof_anchors = [str(anchor).strip() for anchor in (item.get("proof_anchors") or []) if str(anchor).strip()]
    draft_owner_notes = [str(note).strip() for note in (item.get("draft_owner_notes") or []) if str(note).strip()]
    revision_goals = [str(goal).strip() for goal in (item.get("revision_goals") or []) if str(goal).strip()]

    decision = "revise"
    confidence = "medium"
    reasons: list[str] = []
    missing_items: list[str] = []

    if recommendation_text:
        if "park" in recommendation_lower:
            decision = "park"
            confidence = "medium"
            reasons.append("The owner packet already leans toward parking this instead of advancing it.")
        elif "approve" in recommendation_lower and "after" not in recommendation_lower:
            decision = "approve"
            confidence = "high"
            reasons.append("The owner packet already recommends approval or scheduling.")
        elif "revise" in recommendation_lower or "after" in recommendation_lower:
            decision = "revise"
            confidence = "medium"
            reasons.append("The owner packet still frames this as conditional rather than schedule-ready.")

    if source_kind == "latent_transform":
        decision = "revise"
        confidence = "high" if first_pass_draft and revision_goals else "medium"
        reasons.append("This came from the latent transform lane, so it is still being translated into your angle and audience context.")
        if latent_reason == "needs_context_translation":
            missing_items.append("The audience consequence is still implied rather than clearly named.")

    if not first_pass_draft:
        missing_items.append("There is no first-pass draft attached yet.")
    elif len(first_pass_draft.split()) < 70:
        missing_items.append("The first-pass draft is still short enough that the final angle may not be fully expressed.")

    if not proof_anchors:
        missing_items.append("No proof anchors are attached yet.")

    if not str(item.get("core_angle") or "").strip():
        missing_items.append("The core angle is not stated explicitly.")

    if not str(item.get("why_now") or "").strip():
        missing_items.append("The timing or audience consequence is not stated explicitly.")

    if draft_owner_notes:
        reasons.append("The draft already carries explicit owner notes, so the system should not assume it is frictionless.")

    if revision_goals:
        reasons.append("There are named revision goals, which usually means this is closer to revise than approve.")

    if decision == "approve" and missing_items:
        confidence = "medium"
    elif decision == "park" and len(missing_items) >= 2:
        confidence = "high"
    elif decision == "revise" and (revision_goals or source_kind == "latent_transform" or len(missing_items) >= 2):
        confidence = "high"
    elif decision == "revise" and not missing_items:
        confidence = "medium"

    if decision == "approve":
        summary = "System suggestion: approve if the hook and proof feel publicly defensible on one clean read."
        fallback_action = "If you still want to add a story beat, sharper audience consequence, or cleaner proof line, choose Revise instead."
    elif decision == "park":
        summary = "System suggestion: park this unless you already know exactly how it becomes stronger in the next cycle."
        fallback_action = "Only keep it alive if the angle matters strategically and you know what concrete proof or timing change would rescue it."
    else:
        summary = "System suggestion: revise before this moves forward."
        fallback_action = "Approve only if you can already defend the claim, proof, and audience consequence without adding anything material."

    return {
        "suggested_decision": decision,
        "confidence": confidence,
        "summary": summary,
        "reasons": reasons[:3],
        "missing_items": missing_items[:4],
        "fallback_action": fallback_action,
    }


def _build_owner_decision_scaffold(item: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("queue_id") or "this draft").strip()
    core_angle = str(item.get("core_angle") or "").strip()
    why_now = str(item.get("why_now") or "").strip()
    draft_owner_notes = [str(note).strip() for note in (item.get("draft_owner_notes") or []) if str(note).strip()]
    revision_goals = [str(goal).strip() for goal in (item.get("revision_goals") or []) if str(goal).strip()]
    missing_items = [str(entry).strip() for entry in (assessment.get("missing_items") or []) if str(entry).strip()]
    suggested_decision = str(assessment.get("suggested_decision") or "revise").strip() or "revise"

    must_verify = [
        "Read the first-pass draft, not just the PM summary or recommendation.",
    ]
    if core_angle:
        must_verify.append(f"Confirm the draft clearly lands the stated angle: {core_angle}")
    if why_now:
        must_verify.append(f"Confirm the draft makes the current stakes or audience consequence legible: {why_now}")
    if item.get("proof_anchors"):
        must_verify.append("Check that at least one proof anchor or lived proof line is strong enough to defend publicly.")

    approve_when = [
        "The draft is publishable on one clean read without adding anything material.",
        "The claim, proof, and audience consequence feel publicly defensible as written.",
    ]
    if core_angle:
        approve_when.append("The first paragraph and close still support the named core angle.")
    if not missing_items:
        approve_when.append("No obvious gaps remain in the current owner packet.")

    revise_when = [
        "You want one more concrete proof line, story beat, or audience consequence before this moves forward.",
    ]
    revise_when.extend(missing_items[:3])
    revise_when.extend(revision_goals[:3])

    optional_strengtheners = list(dict.fromkeys(draft_owner_notes[:3]))
    if optional_strengtheners:
        revise_when.append("The current draft is close, but you want one of the optional strengtheners applied first.")

    park_when = [
        "You do not want to say this publicly right now, even after a revision pass.",
        "The angle is strategically weak enough that it should leave the active queue instead of consuming more iteration.",
    ]
    if suggested_decision == "park":
        park_when.insert(0, "The current packet already leans toward parking rather than advancing this draft.")

    if suggested_decision == "approve":
        neo_answer_contract = "Approve if it feels publishable on one clean read; otherwise revise with one concrete reason."
    elif suggested_decision == "park":
        neo_answer_contract = "Park unless you already know the concrete proof, timing, or angle change that would rescue it."
    else:
        neo_answer_contract = "Revise unless you can already defend the claim, proof, and audience consequence without adding anything material."

    return {
        "decision_question": f"Should `{title}` move forward now, be revised, or be parked?",
        "recommended_decision": suggested_decision,
        "must_verify": must_verify[:4],
        "approve_when": list(dict.fromkeys(approve_when))[:4],
        "revise_when": list(dict.fromkeys(revise_when))[:4],
        "park_when": list(dict.fromkeys(park_when))[:3],
        "optional_strengtheners": optional_strengtheners,
        "neo_answer_contract": neo_answer_contract,
    }


def _serialize_item(root: Path, queue_id: str, title: str, fields: dict[str, str], list_fields: dict[str, list[str]], packet_path: Path | None) -> dict[str, Any]:
    status_value = fields.get("status", "")
    draft_rel_path, draft_path = _draft_path_from_status(root, status_value)
    draft_text = _read_text(draft_path)
    frontmatter, draft_body = _parse_frontmatter(draft_text)
    packet_text = _read_text(packet_path)
    packet_section = _extract_packet_section(packet_text, queue_id)
    current_decision, recommendation, decision_notes = _parse_packet_decision(packet_section)
    if not current_decision:
        current_decision = frontmatter.get("owner_decision") or None
    current_notes = decision_notes or frontmatter.get("owner_review_notes") or None
    item = {
        "queue_id": queue_id,
        "title": title,
        "lane": fields.get("lane", ""),
        "format": fields.get("format", ""),
        "core_angle": fields.get("core angle", ""),
        "why_now": fields.get("why now", ""),
        "status": status_value.split("(", 1)[0].strip(),
        "approval_status": _clean_markdown_value(fields.get("approval status", "")),
        "draft_path": draft_rel_path,
        "owner_packet_path": packet_path.relative_to(root).as_posix() if packet_path and packet_path.exists() else None,
        "proof_anchors": list_fields.get("proof anchors", []),
        "draft_body": draft_body.strip(),
        "first_pass_draft": _extract_section_body(draft_body, "First-pass draft"),
        "draft_owner_notes": [
            line[2:].strip()
            for line in _extract_section_body(draft_body, "Owner notes").splitlines()
            if line.strip().startswith("- ")
        ],
        "packet_section": packet_section,
        "packet_recommendation": recommendation,
        "current_decision": current_decision,
        "current_notes": current_notes,
        "publish_posture": frontmatter.get("publish_posture", ""),
        "reviewed_at": frontmatter.get("owner_reviewed_at") or None,
        "entry_kind": "queue",
        "source_kind": frontmatter.get("source_kind", "feezie_queue"),
        "source_url": frontmatter.get("source_url") or None,
        "idea_id": frontmatter.get("idea_id") or None,
    }
    item["system_assessment"] = _build_owner_review_assessment(item)
    item["decision_scaffold"] = _build_owner_decision_scaffold(item, item["system_assessment"])
    return item


def _serialize_supplemental_owner_review_item(root: Path, draft_path: Path) -> dict[str, Any] | None:
    draft_text = _read_text(draft_path)
    if not draft_text:
        return None
    frontmatter, draft_body = _parse_frontmatter(draft_text)
    source_kind = str(frontmatter.get("source_kind") or "").strip()
    if source_kind not in SUPPLEMENTAL_OWNER_REVIEW_SOURCE_KINDS:
        return None
    if str(frontmatter.get("publish_posture") or "").strip() != "owner_review_required":
        return None

    draft_rel_path = draft_path.relative_to(root).as_posix()
    title = str(frontmatter.get("title") or draft_path.stem).strip()
    queue_id = _supplemental_queue_id(title, draft_rel_path)
    why_this_exists_fields, _ = _parse_bullet_fields(_extract_section_body(draft_body, "Why this draft exists"))
    source_signal_fields, _ = _parse_bullet_fields(_extract_section_body(draft_body, "Source signal"))
    transform_fields, _ = _parse_bullet_fields(_extract_section_body(draft_body, "Transform brief"))
    revision_goals = [
        line[2:].strip()
        for line in _extract_section_body(draft_body, "Revision goals").splitlines()
        if line.strip().startswith("- ")
    ]
    owner_notes = [
        line[2:].strip()
        for line in _extract_section_body(draft_body, "Owner notes").splitlines()
        if line.strip().startswith("- ")
    ]
    proof_anchors: list[str] = []
    source_file = str(source_signal_fields.get("source file") or "").strip()
    proof_prompt = str(transform_fields.get("proof prompt") or "").strip()
    if source_file:
        proof_anchors.append(f"Source file: {source_file}")
    if proof_prompt:
        proof_anchors.append(f"Proof prompt: {proof_prompt}")

    item = {
        "queue_id": queue_id,
        "title": title,
        "lane": str(frontmatter.get("lane") or ""),
        "format": str(frontmatter.get("draft_kind") or "owner_review"),
        "core_angle": str(transform_fields.get("proposed angle") or ""),
        "why_now": str(source_signal_fields.get("why it matters") or why_this_exists_fields.get("priority lane") or ""),
        "status": "owner_review_draft",
        "approval_status": "owner_review_required",
        "draft_path": draft_rel_path,
        "owner_packet_path": None,
        "proof_anchors": proof_anchors,
        "draft_body": draft_body.strip(),
        "first_pass_draft": _extract_section_body(draft_body, "First-pass transformed draft") or _extract_section_body(draft_body, "First-pass draft"),
        "draft_owner_notes": owner_notes,
        "packet_section": "",
        "packet_recommendation": str(transform_fields.get("promotion rule") or "Revise before promotion into the main FEEZIE queue."),
        "current_decision": frontmatter.get("owner_decision") or None,
        "current_notes": frontmatter.get("owner_review_notes") or None,
        "publish_posture": str(frontmatter.get("publish_posture") or ""),
        "reviewed_at": frontmatter.get("owner_reviewed_at") or None,
        "entry_kind": "supplemental",
        "source_kind": source_kind,
        "source_url": frontmatter.get("source_url") or None,
        "idea_id": frontmatter.get("idea_id") or None,
        "summary": source_signal_fields.get("source summary") or "",
        "revision_goals": revision_goals,
        "latent_reason": frontmatter.get("latent_reason") or None,
        "transform_type": frontmatter.get("transform_type") or None,
        "generated_by": frontmatter.get("generated_by") or None,
    }
    item["system_assessment"] = _build_owner_review_assessment(item)
    item["decision_scaffold"] = _build_owner_decision_scaffold(item, item["system_assessment"])
    return item


def _list_supplemental_owner_review_items(root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for draft_path in sorted(_drafts_root(root).glob("*.md")):
        if draft_path.name == "README.md" or draft_path.name.startswith("queue_") or draft_path.name.startswith("feezie_owner_review_packet_"):
            continue
        item = _serialize_supplemental_owner_review_item(root, draft_path)
        if item is not None:
            items.append(item)
    return items


def _item_from_owner_review_payload(owner_review_payload: dict[str, Any]) -> dict[str, Any] | None:
    queue_id = str(owner_review_payload.get("queue_id") or "").strip()
    if not queue_id:
        return None
    title = str(owner_review_payload.get("title") or queue_id).strip()
    item = {
        "queue_id": queue_id,
        "title": title,
        "lane": str(owner_review_payload.get("lane") or ""),
        "format": str(owner_review_payload.get("format") or ""),
        "core_angle": str(owner_review_payload.get("core_angle") or ""),
        "why_now": str(owner_review_payload.get("why_now") or ""),
        "status": str(owner_review_payload.get("status") or ""),
        "approval_status": str(owner_review_payload.get("approval_status") or ""),
        "draft_path": str(owner_review_payload.get("draft_path") or ""),
        "owner_packet_path": owner_review_payload.get("owner_packet_path"),
        "proof_anchors": list(owner_review_payload.get("proof_anchors") or []),
        "draft_body": "",
        "first_pass_draft": str(owner_review_payload.get("first_pass_draft") or ""),
        "draft_owner_notes": list(owner_review_payload.get("draft_owner_notes") or []),
        "packet_section": "",
        "packet_recommendation": str(owner_review_payload.get("packet_recommendation") or ""),
        "current_decision": owner_review_payload.get("current_decision"),
        "current_notes": owner_review_payload.get("current_notes"),
        "publish_posture": str(owner_review_payload.get("publish_posture") or ""),
        "reviewed_at": owner_review_payload.get("reviewed_at"),
        "entry_kind": str(owner_review_payload.get("entry_kind") or "queue"),
        "source_kind": str(owner_review_payload.get("source_kind") or "feezie_queue"),
        "source_url": owner_review_payload.get("source_url"),
        "idea_id": owner_review_payload.get("idea_id"),
        "summary": str(owner_review_payload.get("summary") or ""),
        "revision_goals": list(owner_review_payload.get("revision_goals") or []),
        "latent_reason": owner_review_payload.get("latent_reason"),
        "transform_type": owner_review_payload.get("transform_type"),
    }
    system_assessment = owner_review_payload.get("system_assessment")
    item["system_assessment"] = system_assessment if isinstance(system_assessment, dict) else _build_owner_review_assessment(item)
    decision_scaffold = owner_review_payload.get("decision_scaffold")
    item["decision_scaffold"] = (
        decision_scaffold if isinstance(decision_scaffold, dict) else _build_owner_decision_scaffold(item, item["system_assessment"])
    )
    return item


def _list_pm_pending_owner_review_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for card in pm_card_service.list_cards(limit=250):
        if str(card.source or "") != OWNER_REVIEW_CARD_SOURCE:
            continue
        if str(card.link_type or "") != OWNER_REVIEW_LINK_TYPE:
            continue
        if str(card.status or "").lower() not in {"review", "todo", "in_progress"}:
            continue
        payload = dict(card.payload or {})
        owner_review_payload = payload.get("owner_review") if isinstance(payload.get("owner_review"), dict) else {}
        if not isinstance(owner_review_payload, dict):
            continue
        if str(owner_review_payload.get("sync_state") or "").strip() != "pending_owner_review":
            continue
        if str(owner_review_payload.get("decision") or "").strip():
            continue
        item = _item_from_owner_review_payload(owner_review_payload)
        if item is not None:
            items.append(item)
    return items


def _find_pm_pending_owner_review_item(queue_id: str) -> dict[str, Any] | None:
    normalized_queue_id = str(queue_id or "").strip()
    if not normalized_queue_id:
        return None
    return next(
        (item for item in _list_pm_pending_owner_review_items() if str(item.get("queue_id") or "").strip() == normalized_queue_id),
        None,
    )


def _is_missing_owner_review_artifact_error(exc: ValueError) -> bool:
    message = str(exc)
    return (
        "Draft file is missing" in message
        or "does not have a draft path" in message
        or "is not present in" in message
    )


def _owner_review_trigger_key(queue_id: str) -> str:
    return f"owner-review:{queue_id}"


def _is_supplemental_owner_review_item(item: dict[str, Any]) -> bool:
    return str(item.get("entry_kind") or "").strip() == "supplemental"


def _owner_review_reason(item: dict[str, Any], decision: str) -> str:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    if _is_supplemental_owner_review_item(item):
        if decision == "approve":
            return (
                f"Owner approved the latent transform draft {title}. Promote it into the next concrete FEEZIE step, "
                "then write the result back to PM and the draft artifacts."
            )
        return (
            f"Owner requested revision for the latent transform draft {title}. Apply the owner notes, update the draft, "
            "and return it to owner review."
        )
    if decision == "approve":
        return (
            f"Owner approved {queue_id} ({title}). Convert the approved draft into the next concrete release step, "
            "then write the result back to PM and the FEEZIE artifacts."
        )
    return (
        f"Owner requested revision for {queue_id} ({title}). Apply the owner notes, update the draft artifacts, "
        "and return the draft to owner review."
    )


def _owner_review_card_title(item: dict[str, Any], decision: str) -> str:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    if _is_supplemental_owner_review_item(item):
        if decision == "approve":
            return f"Promote approved latent draft - {title}"
        return f"Revise latent draft - {title}"
    if decision == "approve":
        return f"Schedule approved FEEZIE draft - {queue_id}"
    return f"Revise FEEZIE draft - {queue_id}"


def _owner_review_instructions(item: dict[str, Any], decision: str, notes: str) -> list[str]:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    draft_path = str(item.get("draft_path") or "").strip()
    packet_path = str(item.get("owner_packet_path") or "").strip()
    base = [
        f"Use `{queue_id}` / {title} as the source of truth for this follow-up.",
        f"Review the current draft at `{draft_path}` and the owner packet at `{packet_path or 'missing owner packet'}` before changing execution state.",
    ]
    if _is_supplemental_owner_review_item(item):
        if decision == "approve":
            base.extend(
                [
                    "Turn the approved latent transform into the next concrete FEEZIE move: promote it into the active publishing plan, package it for scheduling, or explicitly place it into the canonical queue if it now deserves that lane.",
                    "Write the follow-up outcome back to PM and the draft artifacts so the approval loop closes visibly.",
                    "If repo-side work is complete and the only remaining step needs host credentials or an external UI, return explicit host actions with proof requirements instead of leaving a generic follow-up.",
                ]
            )
        else:
            base.extend(
                [
                    "Revise the latent transform draft directly in the FEEZIE workspace and keep the copy grounded in proof and audience consequence.",
                    "Return the draft to owner review once the transform is specific enough to graduate out of the latent lane.",
                ]
            )
    elif decision == "approve":
        base.extend(
            [
                "Turn the approved draft into the next concrete execution step: scheduling, packaging, or explicit publish follow-through.",
                "Write the follow-up outcome back to PM, the draft queue, and the execution log so the approval loop closes visibly.",
                "If the remaining work is host-only, such as LinkedIn scheduling or proof capture outside the repo, return it as explicit host actions with proof requirements.",
            ]
        )
    else:
        base.extend(
            [
                "Revise the draft directly in the FEEZIE workspace and keep the copy grounded in proof.",
                "Return the draft to owner review with updated notes once the requested changes are complete.",
            ]
        )
    if notes.strip():
        base.append(f"Owner notes: {notes.strip()}")
    return base


def _owner_review_acceptance_criteria(item: dict[str, Any], decision: str) -> list[str]:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    if _is_supplemental_owner_review_item(item):
        if decision == "approve":
            return [
                f"`{title}` is promoted out of the latent lane into a concrete next FEEZIE step.",
                "PM write-back makes the promotion outcome explicit and bounded.",
                "Draft or queue artifacts reflect the new active state.",
            ]
        return [
            f"`{title}` is revised directly in the latent draft artifact.",
            "The revised draft is returned to owner review with concrete notes or proof added.",
            "PM write-back explains what changed and what the owner should re-check.",
        ]
    if decision == "approve":
        return [
            f"`{queue_id}` advances from approved draft into a concrete release or scheduling step.",
            "PM write-back records a bounded result with outcomes and any follow-up actions.",
            "The FEEZIE draft artifacts reflect the new post-approval state.",
        ]
    return [
        f"`{queue_id}` is revised directly in the FEEZIE draft artifacts.",
        "The revised draft is returned to owner review instead of stalling in execution.",
        "PM write-back explains what changed and what the owner should re-check.",
    ]


def _owner_review_artifacts_expected(item: dict[str, Any], decision: str) -> list[str]:
    draft_path = str(item.get("draft_path") or "").strip()
    queue_id = str(item.get("queue_id") or "").strip()
    if decision == "approve":
        return [
            draft_path or f"updated draft artifact for {queue_id}",
            "updated PM execution result",
            "bounded scheduling, publishing, or queue artifact showing the next concrete step",
        ]
    return [
        draft_path or f"updated draft artifact for {queue_id}",
        "updated PM execution result",
        "owner-review-ready revision notes in the draft or packet artifacts",
    ]


def _build_owner_review_execution(reason: str) -> dict[str, Any]:
    defaults = pm_card_service.execution_defaults_for_workspace(PM_WORKSPACE_KEY)
    return {
        "lane": "codex",
        "state": "ready",
        "manager_agent": defaults["manager_agent"],
        "target_agent": defaults["target_agent"],
        "workspace_agent": defaults.get("workspace_agent"),
        "execution_mode": defaults["execution_mode"],
        "requested_by": "Neo",
        "assigned_runner": "jean-claude" if str(defaults["execution_mode"]) == "direct" else "codex",
        "reason": reason,
        "last_transition_at": datetime.now(timezone.utc).isoformat(),
        "source": "owner_review",
    }


def _build_owner_review_card_payload(
    item: dict[str, Any],
    *,
    decision: str,
    notes: str,
    draft_rel_path: str,
    packet_rel_path: str | None,
    existing_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    reason = _owner_review_reason(item, decision)
    payload = dict(existing_payload or {})
    artifact_paths = [path for path in [draft_rel_path, packet_rel_path] if path]
    contract = build_execution_contract(
        title=_owner_review_card_title(item, decision),
        workspace_key=PM_WORKSPACE_KEY,
        source="owner_review_followup",
        reason=reason,
        instructions=_owner_review_instructions(item, decision, notes),
        acceptance_criteria=_owner_review_acceptance_criteria(item, decision),
        artifacts_expected=_owner_review_artifacts_expected(item, decision),
    )
    payload.update(
        {
            "workspace_key": PM_WORKSPACE_KEY,
            "source_agent": "Neo",
            "front_door_agent": "Neo",
            "trigger_origin": "owner_review",
            "trigger_key": _owner_review_trigger_key(queue_id),
            "reason": reason,
            "instructions": contract["instructions"],
            "acceptance_criteria": contract["acceptance_criteria"],
            "artifacts_expected": contract["artifacts_expected"],
            "completion_contract": contract["completion_contract"],
            "artifact_paths": artifact_paths,
            "owner_review": {
                "queue_id": queue_id,
                "title": title,
                "decision": decision,
                "notes": notes.strip() or None,
                "draft_path": draft_rel_path,
                "owner_packet_path": packet_rel_path,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "entry_kind": item.get("entry_kind"),
                "source_kind": item.get("source_kind"),
                "source_url": item.get("source_url"),
                "idea_id": item.get("idea_id"),
                "system_assessment": item.get("system_assessment"),
            },
            "execution": _build_owner_review_execution(reason),
        }
    )
    return payload


def _pending_owner_review_card_title(item: dict[str, Any]) -> str:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    if _is_supplemental_owner_review_item(item):
        return f"Owner review - Latent transform - {title}"
    return f"Owner review - {queue_id} - {title}"


def _pending_owner_review_reason(item: dict[str, Any]) -> str:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    if _is_supplemental_owner_review_item(item):
        return (
            f"Owner decision needed for the latent transform draft {title}. Open the card, review the transformed draft, "
            "and choose approve, revise, or park."
        )
    return (
        f"Owner decision needed for {queue_id} ({title}). Open the card, review the draft, "
        "and choose approve, revise, or park."
    )


def _item_needs_owner_review(item: dict[str, Any]) -> bool:
    return (
        str(item.get("approval_status") or "").strip() == "owner_review_required"
        and str(item.get("publish_posture") or "").strip() == "owner_review_required"
        and not str(item.get("current_decision") or "").strip()
    )


def _build_pending_owner_review_card_payload(
    item: dict[str, Any],
    *,
    existing_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_id = str(item.get("queue_id") or "").strip()
    title = str(item.get("title") or queue_id).strip()
    payload = dict(existing_payload or {})
    payload.pop("execution", None)
    payload.pop("latest_execution_result", None)
    payload.pop("latest_manual_review", None)
    payload.update(
        {
            "workspace_key": PM_WORKSPACE_KEY,
            "source_agent": "Neo",
            "front_door_agent": "Neo",
            "trigger_origin": "owner_review",
            "trigger_key": _owner_review_trigger_key(queue_id),
            "reason": _pending_owner_review_reason(item),
            "instructions": [
                f"Review `{title}` in PM Board before any backend worker picks it up.",
                "Read the first-pass draft and attached context before deciding.",
                "Choose Approve, Revise, or Park from the PM card modal.",
            ],
            "owner_review": {
                "queue_id": queue_id,
                "title": title,
                "lane": item.get("lane"),
                "format": item.get("format"),
                "core_angle": item.get("core_angle"),
                "why_now": item.get("why_now"),
                "status": item.get("status"),
                "approval_status": item.get("approval_status"),
                "draft_path": item.get("draft_path"),
                "owner_packet_path": item.get("owner_packet_path"),
                "proof_anchors": item.get("proof_anchors") or [],
                "first_pass_draft": item.get("first_pass_draft"),
                "draft_owner_notes": item.get("draft_owner_notes") or [],
                "packet_recommendation": item.get("packet_recommendation"),
                "current_notes": item.get("current_notes"),
                "publish_posture": item.get("publish_posture"),
                "reviewed_at": item.get("reviewed_at"),
                "sync_state": "pending_owner_review",
                "entry_kind": item.get("entry_kind"),
                "source_kind": item.get("source_kind"),
                "source_url": item.get("source_url"),
                "idea_id": item.get("idea_id"),
                "summary": item.get("summary"),
                "revision_goals": item.get("revision_goals") or [],
                "latent_reason": item.get("latent_reason"),
                "transform_type": item.get("transform_type"),
                "system_assessment": item.get("system_assessment"),
                "decision_scaffold": item.get("decision_scaffold"),
            },
        }
    )
    return payload


def _pending_owner_review_card_is_current(
    existing: Any,
    *,
    title: str,
    payload: dict[str, Any],
) -> bool:
    return (
        str(getattr(existing, "title", "") or "") == title
        and str(getattr(existing, "owner", "") or "") == "Neo"
        and str(getattr(existing, "status", "") or "") == "review"
        and str(getattr(existing, "source", "") or "") == OWNER_REVIEW_CARD_SOURCE
        and str(getattr(existing, "link_type", "") or "") == OWNER_REVIEW_LINK_TYPE
        and getattr(existing, "link_id", None) == _owner_review_link_id()
        and dict(getattr(existing, "payload", {}) or {}) == payload
    )


def sync_owner_review_pm_cards() -> dict[str, Any]:
    payload = list_owner_review_items()
    created_card_ids: list[str] = []
    updated_card_ids: list[str] = []
    skipped_card_ids: list[str] = []
    pending_queue_ids: list[str] = []

    for item in payload.get("items", []):
        if not isinstance(item, dict) or not _item_needs_owner_review(item):
            continue
        queue_id = str(item.get("queue_id") or "").strip()
        title = str(item.get("title") or queue_id).strip()
        if not queue_id:
            continue
        pending_queue_ids.append(queue_id)
        existing = pm_card_service.find_active_card_by_trigger_key(_owner_review_trigger_key(queue_id))
        card_payload = _build_pending_owner_review_card_payload(
            item,
            existing_payload=dict(existing.payload or {}) if existing is not None else None,
        )
        card_title = _pending_owner_review_card_title(item)
        if existing is None:
            card = pm_card_service.create_card(
                PMCardCreate(
                    title=card_title,
                    owner="Neo",
                    status="review",
                    source=OWNER_REVIEW_CARD_SOURCE,
                    link_type=OWNER_REVIEW_LINK_TYPE,
                    link_id=_owner_review_link_id(),
                    payload=card_payload,
                )
            )
            created_card_ids.append(card.id)
            continue
        if _pending_owner_review_card_is_current(existing, title=card_title, payload=card_payload):
            skipped_card_ids.append(existing.id)
            continue
        updated = pm_card_service.update_card(
            existing.id,
            PMCardUpdate(
                title=card_title,
                owner="Neo",
                status="review",
                source=OWNER_REVIEW_CARD_SOURCE,
                link_type=OWNER_REVIEW_LINK_TYPE,
                link_id=_owner_review_link_id(),
                payload=card_payload,
            ),
        )
        updated_card_ids.append(updated.id if updated is not None else existing.id)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pending_count": len(pending_queue_ids),
        "pending_queue_ids": pending_queue_ids,
        "created_card_ids": created_card_ids,
        "updated_card_ids": updated_card_ids,
        "skipped_card_ids": skipped_card_ids,
    }


def record_owner_decision_for_pm_card(card_id: str, decision: str, notes: str | None = None) -> dict[str, Any]:
    card = pm_card_service.get_card(card_id)
    if card is None:
        raise ValueError(f"PM card not found: {card_id}")
    payload = dict(card.payload or {})
    owner_review_payload = payload.get("owner_review") if isinstance(payload.get("owner_review"), dict) else {}
    queue_id = ""
    fallback_item: dict[str, Any] | None = None
    if isinstance(owner_review_payload, dict):
        queue_id = str(owner_review_payload.get("queue_id") or "").strip()
        fallback_item = _item_from_owner_review_payload(owner_review_payload)
    if not queue_id and isinstance(card.link_id, str):
        queue_id = card.link_id.strip()
    if not queue_id:
        raise ValueError(f"PM card {card_id} is not linked to an owner-review queue item.")
    payload_snapshot = list_owner_review_items()
    item = next((entry for entry in payload_snapshot.get("items", []) if entry.get("queue_id") == queue_id), None)
    if item is None:
        item = fallback_item
    if item is None:
        raise ValueError(f"Unknown queue item: {queue_id}")
    result = _record_owner_decision_for_item(item, decision, notes, tolerate_missing_artifacts=True)
    result["source_card_id"] = card_id
    return result


def _queue_owner_review_followup(
    item: dict[str, Any],
    *,
    decision: str,
    notes: str,
    draft_rel_path: str,
    packet_rel_path: str | None,
) -> dict[str, Any]:
    queue_id = str(item.get("queue_id") or "").strip()
    existing = pm_card_service.find_active_card_by_trigger_key(_owner_review_trigger_key(queue_id))

    if decision == "park":
        if existing is None:
            return {
                "status": "noop",
                "message": f"{queue_id} parked. No backend follow-up was active.",
            }
        existing_payload = _build_owner_review_card_payload(
            item,
            decision=decision,
            notes=notes,
            draft_rel_path=draft_rel_path,
            packet_rel_path=packet_rel_path,
            existing_payload=dict(existing.payload or {}),
        )
        execution = dict(existing_payload.get("execution") or {})
        execution.update(
            {
                "state": "cancelled",
                "last_transition_at": datetime.now(timezone.utc).isoformat(),
                "reason": f"{queue_id} was parked during owner review.",
            }
        )
        existing_payload["execution"] = execution
        pm_card_service.update_card(existing.id, PMCardUpdate(status="cancelled", payload=existing_payload))
        return {
            "status": "cancelled",
            "message": f"{queue_id} parked. Cancelled backend follow-up card {existing.id}.",
            "card_id": existing.id,
        }

    title = _owner_review_card_title(item, decision)
    payload = _build_owner_review_card_payload(
        item,
        decision=decision,
        notes=notes,
        draft_rel_path=draft_rel_path,
        packet_rel_path=packet_rel_path,
        existing_payload=dict(existing.payload or {}) if existing is not None else None,
    )

    if existing is None:
            card = pm_card_service.create_card(
                PMCardCreate(
                    title=title,
                    owner="Neo",
                    status="todo",
                    source=OWNER_REVIEW_CARD_SOURCE,
                    link_type=OWNER_REVIEW_LINK_TYPE,
                    link_id=_owner_review_link_id(),
                    payload=payload,
                )
            )
    else:
        card = pm_card_service.update_card(
            existing.id,
            PMCardUpdate(
                title=title,
                owner="Neo",
                status="todo",
                source=OWNER_REVIEW_CARD_SOURCE,
                link_type=OWNER_REVIEW_LINK_TYPE,
                link_id=_owner_review_link_id(),
                payload=payload,
            ),
        )
        if card is None:
            raise ValueError(f"Unable to update owner-review PM card for {queue_id}")

    dispatch_result = pm_card_service.dispatch_card(
        card.id,
        PMCardDispatchRequest(
            target_agent="Jean-Claude",
            lane="codex",
            requested_by="Neo",
            execution_state="queued",
        ),
    )
    if dispatch_result is None:
        raise ValueError(f"Unable to dispatch owner-review PM card for {queue_id}")
    return {
        "status": "queued",
        "message": (
            f"{queue_id} saved as {decision}. Jean-Claude follow-up is queued on backend card {dispatch_result.card.id}."
        ),
        "card_id": dispatch_result.card.id,
        "target_agent": dispatch_result.queue_entry.target_agent,
        "execution_state": dispatch_result.queue_entry.execution_state,
    }


def _split_pending_owner_review_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pending: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    for item in items:
        decision = str(item.get("current_decision") or "").strip().lower()
        if decision:
            resolved.append(item)
        else:
            pending.append(item)
    return pending, resolved


def list_owner_review_items(*, include_resolved: bool = False) -> dict[str, Any]:
    root = _linkedin_root()
    queue_path = _queue_path(root)
    queue_text = _read_text(queue_path)
    packet_path = _latest_owner_packet(root)
    items: list[dict[str, Any]] = []
    if not queue_text:
        supplemental_items = _list_supplemental_owner_review_items(root)
        if not supplemental_items:
            supplemental_items = _list_pm_pending_owner_review_items()
        pending_items, resolved_items = _split_pending_owner_review_items(supplemental_items)
        selected_items = supplemental_items if include_resolved else pending_items
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "queue_path": queue_path.relative_to(root).as_posix(),
            "owner_packet_path": packet_path.relative_to(root).as_posix() if packet_path and packet_path.exists() else None,
            "items": selected_items,
            "pending_count": len(pending_items),
            "resolved_count": len(resolved_items),
            "total_count": len(supplemental_items),
        }
    section = queue_text.split("## Queue", 1)[1] if "## Queue" in queue_text else queue_text
    for queue_id, title, block in _split_queue_blocks(section):
        fields, list_fields = _parse_bullet_fields(block)
        draft_rel_path, draft_path = _draft_path_from_status(root, fields.get("status", ""))
        if not draft_rel_path or draft_path is None or not draft_path.exists():
            continue
        items.append(_serialize_item(root, queue_id, title, fields, list_fields, packet_path))
    items.extend(_list_supplemental_owner_review_items(root))
    if not items:
        items.extend(_list_pm_pending_owner_review_items())
    pending_items, resolved_items = _split_pending_owner_review_items(items)
    selected_items = items if include_resolved else pending_items
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_path": queue_path.relative_to(root).as_posix(),
        "owner_packet_path": packet_path.relative_to(root).as_posix() if packet_path and packet_path.exists() else None,
        "items": selected_items,
        "pending_count": len(pending_items),
        "resolved_count": len(resolved_items),
        "total_count": len(items),
    }


def _update_queue_file(queue_path: Path, queue_id: str, decision: str, draft_rel_path: str, packet_rel_path: str | None) -> None:
    text = _read_text(queue_path)
    bounds = _section_bounds(text, QUEUE_HEADING_RE, queue_id)
    if bounds is None:
        raise ValueError(f"{queue_id} is not present in {queue_path}")
    start, end = bounds
    section = text[start:end]
    section = re.sub(
        r"^- Status: .*$",
        f"- Status: {STATUS_MAP[decision]} (`{draft_rel_path}`)",
        section,
        count=1,
        flags=re.MULTILINE,
    )
    section = re.sub(
        r"^- Approval status: .*$",
        f"- Approval status: `{APPROVAL_STATUS_MAP[decision]}`",
        section,
        count=1,
        flags=re.MULTILINE,
    )
    if packet_rel_path:
        section = re.sub(
            r"^- Owner packet: .*$",
            f"- Owner packet: `{packet_rel_path}` entry for `{queue_id}`",
            section,
            count=1,
            flags=re.MULTILINE,
        )
    updated = f"{text[:start]}{section}{text[end:]}"
    queue_path.write_text(updated, encoding="utf-8")


def _update_owner_packet(packet_path: Path, queue_id: str, decision: str, notes: str) -> None:
    text = _read_text(packet_path)
    bounds = _section_bounds(text, PACKET_HEADING_RE, queue_id)
    if bounds is None:
        raise ValueError(f"{queue_id} is not present in {packet_path}")
    start, end = bounds
    section = text[start:end]
    for candidate, label in PACKET_CHECKBOX_LINES.items():
        mark = "x" if candidate == decision else " "
        section = re.sub(
            rf"^- \[[ xX]\]\s+{re.escape(label)}\s*$",
            f"- [{mark}] {label}",
            section,
            count=1,
            flags=re.MULTILINE,
        )
    replacement_notes = notes.strip()
    section = re.sub(
        r"\*\*Revision notes \(if needed\):\*\*\n.*\Z",
        f"**Revision notes (if needed):**\n{replacement_notes}".rstrip(),
        section,
        count=1,
        flags=re.DOTALL,
    )
    updated = f"{text[:start]}{section}{text[end:]}"
    packet_path.write_text(updated, encoding="utf-8")


def _update_draft_file(draft_path: Path, decision: str, reviewed_at: str, notes: str | None = None) -> None:
    text = _read_text(draft_path)
    updated = _set_frontmatter_fields(
        text,
        {
            "publish_posture": PUBLISH_POSTURE_MAP[decision],
            "owner_decision": decision,
            "owner_reviewed_at": reviewed_at,
            "owner_review_notes": (notes or "").strip(),
        },
    )
    draft_path.write_text(updated, encoding="utf-8")


def _append_execution_log(root: Path, queue_id: str, title: str, decision: str, notes: str, draft_rel_path: str, packet_rel_path: str | None) -> None:
    log_path = _execution_log_path(root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    note_line = notes.strip() or "No additional notes."
    entry = (
        f"\n## Owner Review Decision — {timestamp}\n\n"
        f"- Queue item: `{queue_id}`\n"
        f"- Title: {title}\n"
        f"- Decision: `{decision}`\n"
        f"- Notes: {note_line}\n"
        f"- Draft: `{draft_rel_path}`\n"
        f"- Owner packet: `{packet_rel_path or 'missing'}`\n"
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)

def _record_owner_decision_for_item(
    item: dict[str, Any],
    decision: str,
    notes: str | None = None,
    *,
    tolerate_missing_artifacts: bool = False,
) -> dict[str, Any]:
    root = _linkedin_root()
    queue_path = _queue_path(root)
    packet_path = _latest_owner_packet(root)
    queue_id = str(item.get("queue_id") or "").strip()
    draft_rel_path = str(item.get("draft_path") or "").strip()
    artifact_warnings: list[str] = []
    if not draft_rel_path:
        if not tolerate_missing_artifacts:
            raise ValueError(f"{queue_id} does not have a draft path.")
        artifact_warnings.append(f"{queue_id} has no draft path in the current runtime payload.")
        draft_path = None
    else:
        draft_path = root / draft_rel_path
        if not draft_path.exists():
            if not tolerate_missing_artifacts:
                raise ValueError(f"Draft file is missing for {queue_id}: {draft_rel_path}")
            artifact_warnings.append(f"Draft file is missing for {queue_id}: {draft_rel_path}")
            draft_path = None
    reviewed_at = datetime.now(timezone.utc).isoformat()
    packet_rel_path = packet_path.relative_to(root).as_posix() if packet_path and packet_path.exists() else None
    workflow: dict[str, Any] | None = None

    if str(item.get("entry_kind") or "") == "queue":
        bounds = _section_bounds(_read_text(queue_path), QUEUE_HEADING_RE, queue_id)
        if bounds is not None:
            _update_queue_file(queue_path, queue_id, decision, draft_rel_path, packet_rel_path)
        elif tolerate_missing_artifacts:
            artifact_warnings.append(f"{queue_id} is not present in the live queue artifact at {queue_path.relative_to(root).as_posix()}.")
        else:
            raise ValueError(f"{queue_id} is not present in {queue_path}")
        if packet_path and packet_path.exists():
            packet_bounds = _section_bounds(_read_text(packet_path), PACKET_HEADING_RE, queue_id)
            if packet_bounds is not None:
                _update_owner_packet(packet_path, queue_id, decision, notes or "")
            elif tolerate_missing_artifacts:
                artifact_warnings.append(f"{queue_id} is not present in the live owner packet at {packet_rel_path}.")
            else:
                raise ValueError(f"{queue_id} is not present in {packet_path}")
        elif tolerate_missing_artifacts:
            artifact_warnings.append("Live owner packet is missing in this runtime, so the decision was recorded from PM payload only.")
    if draft_path is not None:
        _update_draft_file(draft_path, decision, reviewed_at, notes)
    _append_execution_log(root, queue_id, str(item.get("title") or queue_id), decision, notes or "", draft_rel_path, packet_rel_path)
    try:
        workflow = _queue_owner_review_followup(
            item,
            decision=decision,
            notes=notes or "",
            draft_rel_path=draft_rel_path,
            packet_rel_path=packet_rel_path,
        )
    except Exception as exc:
        workflow = {
            "status": "error",
            "message": (
                f"{queue_id} saved as {decision}, but backend follow-up failed to queue: {exc}"
            ),
        }

    refreshed = list_owner_review_items()
    refreshed["workflow"] = workflow
    if artifact_warnings:
        refreshed["artifact_warnings"] = artifact_warnings
    return refreshed


def record_owner_decision(queue_id: str, decision: str, notes: str | None = None) -> dict[str, Any]:
    payload = list_owner_review_items()
    item = next((entry for entry in payload.get("items", []) if entry.get("queue_id") == queue_id), None)
    if item is None:
        item = _find_pm_pending_owner_review_item(queue_id)
    if item is None:
        raise ValueError(f"Unknown queue item: {queue_id}")
    try:
        return _record_owner_decision_for_item(item, decision, notes)
    except ValueError as exc:
        fallback_item = _find_pm_pending_owner_review_item(queue_id)
        if fallback_item is None or not _is_missing_owner_review_artifact_error(exc):
            raise
        return _record_owner_decision_for_item(fallback_item, decision, notes, tolerate_missing_artifacts=True)
