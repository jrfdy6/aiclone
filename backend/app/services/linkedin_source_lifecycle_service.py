from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_KEY = "linkedin-content-os"
WORKSPACE_RELATIVE = "workspaces/linkedin-content-os"

STAGE_CONFIG: dict[str, dict[str, Any]] = {
    "feed_only": {
        "priority": 10,
        "label": "Needs decision",
        "visibility": "needs_decision",
        "primary_surface": "feed",
        "primary_action": "review_source",
        "next_action_label": "Review source",
        "reason": "This source is visible in the feed and has not advanced into a downstream FEEZIE lane yet.",
    },
    "comment_candidate": {
        "priority": 20,
        "label": "Comment candidate",
        "visibility": "needs_decision",
        "primary_surface": "feed",
        "primary_action": "draft_comment",
        "next_action_label": "Draft comment",
        "reason": "This source is available as a reaction/comment opportunity.",
    },
    "weekly_plan": {
        "priority": 30,
        "label": "Weekly plan",
        "visibility": "in_workflow",
        "primary_surface": "weekly_plan",
        "primary_action": "open_weekly_plan",
        "next_action_label": "Use planned seed",
        "reason": "This source is already selected in the active weekly plan.",
    },
    "post_seed": {
        "priority": 40,
        "label": "Potential post",
        "visibility": "potential_post",
        "primary_surface": "post_seed",
        "primary_action": "open_post_seed",
        "next_action_label": "Open potential post",
        "reason": "This source has already been admitted as a standalone post seed.",
    },
    "latent_seed": {
        "priority": 45,
        "label": "Needs anecdote",
        "visibility": "needs_anecdote",
        "primary_surface": "latent_seed",
        "primary_action": "add_anecdote",
        "next_action_label": "Work latent seed",
        "reason": "This source was preserved as a latent seed and needs proof, taste, or an anecdote before drafting.",
    },
    "owner_review": {
        "priority": 60,
        "label": "Owner review",
        "visibility": "owner_review",
        "primary_surface": "owner_review",
        "primary_action": "approve_revise_or_park",
        "next_action_label": "Open owner review",
        "reason": "A draft exists and is waiting for approve, revise, or park.",
    },
    "rejected": {
        "priority": 58,
        "label": "Not for FEEZIE",
        "visibility": "rejected",
        "primary_surface": "feed_feedback",
        "primary_action": "none",
        "next_action_label": "Rejected",
        "reason": "The owner marked this source as not useful for the FEEZIE content loop.",
    },
    "banked": {
        "priority": 70,
        "label": "Banked",
        "visibility": "banked",
        "primary_surface": "banked_posts",
        "primary_action": "open_banked_post",
        "next_action_label": "Open banked post",
        "reason": "The owner-approved copy is banked as a potential LinkedIn post.",
    },
    "parked": {
        "priority": 75,
        "label": "Parked",
        "visibility": "resolved",
        "primary_surface": "archive",
        "primary_action": "none",
        "next_action_label": "Parked",
        "reason": "This source or draft was parked and should not appear as active feed work.",
    },
    "scheduled": {
        "priority": 80,
        "label": "Scheduled",
        "visibility": "scheduled",
        "primary_surface": "publishing_schedule",
        "primary_action": "open_schedule_receipt",
        "next_action_label": "Open schedule receipt",
        "reason": "The post has a host-confirmed LinkedIn scheduling receipt.",
    },
    "published": {
        "priority": 90,
        "label": "Published",
        "visibility": "published",
        "primary_surface": "analytics",
        "primary_action": "review_performance",
        "next_action_label": "Review performance",
        "reason": "The post has publication evidence or analytics attached.",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _slugify(value: Any) -> str:
    lowered = _clean(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def _normalize_url(value: Any) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    return raw.rstrip("/").lower()


def _workspace_relative_path(value: Any, linkedin_root: Path) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    raw = raw.replace("\\", "/").removeprefix("./")
    workspace_root = linkedin_root.parent.parent
    try:
        raw_path = Path(raw).expanduser()
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
            if resolved == linkedin_root.resolve() or linkedin_root.resolve() in resolved.parents:
                return f"{WORKSPACE_RELATIVE}/{resolved.relative_to(linkedin_root.resolve()).as_posix()}"
            if resolved == workspace_root.resolve() or workspace_root.resolve() in resolved.parents:
                return resolved.relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        pass
    if raw.startswith(f"{WORKSPACE_RELATIVE}/"):
        return raw
    if raw == WORKSPACE_RELATIVE:
        return raw
    if raw.startswith("/Users/neo/.openclaw/workspace/"):
        return raw.removeprefix("/Users/neo/.openclaw/workspace/")
    if raw.startswith("research/") or raw.startswith("plans/") or raw.startswith("drafts/") or raw.startswith("docs/") or raw.startswith("analytics/"):
        return f"{WORKSPACE_RELATIVE}/{raw}"
    return raw


def _workspace_local_path(value: Any, linkedin_root: Path) -> str:
    normalized = _workspace_relative_path(value, linkedin_root)
    prefix = f"{WORKSPACE_RELATIVE}/"
    return normalized.removeprefix(prefix) if normalized.startswith(prefix) else normalized


def _path_match_keys(value: Any, linkedin_root: Path) -> list[str]:
    normalized = _workspace_relative_path(value, linkedin_root)
    if not normalized:
        return []
    local = _workspace_local_path(normalized, linkedin_root)
    keys = [f"path:{normalized.lower()}"]
    if local and local != normalized:
        keys.append(f"path:{local.lower()}")
    return list(dict.fromkeys(keys))


def _match_keys(
    *,
    linkedin_root: Path,
    title: Any = "",
    source_url: Any = "",
    source_path: Any = "",
    draft_path: Any = "",
    queue_id: Any = "",
) -> list[str]:
    keys: list[str] = []
    url = _normalize_url(source_url)
    if url:
        keys.append(f"url:{url}")
    keys.extend(_path_match_keys(source_path, linkedin_root))
    keys.extend(_path_match_keys(draft_path, linkedin_root))
    queue = _clean(queue_id).upper()
    if queue:
        keys.append(f"queue:{queue}")
    title_slug = _slugify(title)
    if title_slug != "untitled":
        keys.append(f"title:{title_slug}")
    return list(dict.fromkeys(keys))


def _artifact_path(path: Any, linkedin_root: Path) -> str:
    return _workspace_relative_path(path, linkedin_root)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fields: dict[str, str] = {}
    for raw_line in text[4:end].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields, text[end + 5 :]


def _parse_queue_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key = ""
    for raw_line in block.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- ") and ":" in stripped and not raw_line.startswith("  "):
            key, value = stripped[2:].split(":", 1)
            current_key = key.strip().lower()
            fields[current_key] = _strip_markdown_value(value)
            continue
        if current_key and raw_line.startswith("  ") and stripped:
            fields[current_key] = f"{fields.get(current_key, '')}\n{_strip_markdown_value(stripped)}".strip()
    return fields


def _strip_markdown_value(value: Any) -> str:
    cleaned = _clean(value)
    cleaned = re.sub(r"^`(.+)`$", r"\1", cleaned)
    cleaned = cleaned.replace("**", "")
    return cleaned


def _extract_path_from_status(value: Any) -> str:
    cleaned = _clean(value)
    match = re.search(r"\(`([^`]+)`\)", cleaned)
    if match:
        return match.group(1).strip()
    match = re.search(r"`([^`]+)`", cleaned)
    return match.group(1).strip() if match else ""


def _queue_blocks(queue_text: str) -> list[tuple[str, str, str]]:
    matches = list(re.finditer(r"^###\s+(FEEZIE-\d+)\s+-\s+(.+)$", queue_text, flags=re.MULTILINE))
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(queue_text)
        blocks.append((match.group(1).strip(), match.group(2).strip(), queue_text[start:end].strip()))
    return blocks


def _stage_from_publish_posture(publish_posture: Any, owner_decision: Any = "") -> str:
    posture = _clean(publish_posture).lower()
    decision = _clean(owner_decision).lower()
    if decision == "park" or posture in {"hold_private", "owner_parked", "parked"}:
        return "parked"
    if decision == "approve" or posture in {"approved", "owner_approved"}:
        return "banked"
    if posture == "owner_review_required" or decision == "revise":
        return "owner_review"
    return "owner_review" if posture else "weekly_plan"


def _merge_item(items_by_key: dict[str, dict[str, Any]], key_index: dict[str, str], candidate: dict[str, Any]) -> None:
    keys = [str(key) for key in candidate.get("match_keys") or [] if str(key).strip()]
    if not keys:
        keys = [f"title:{_slugify(candidate.get('title'))}"]
        candidate["match_keys"] = keys
    canonical_key = next((key_index[key] for key in keys if key in key_index), keys[0])
    existing = items_by_key.get(canonical_key)
    if existing is None:
        item = dict(candidate)
        item["source_key"] = canonical_key
        item["match_keys"] = list(dict.fromkeys(keys))
        item["artifact_paths"] = list(dict.fromkeys(item.get("artifact_paths") or []))
        item["evidence"] = dict(item.get("evidence") or {})
        items_by_key[canonical_key] = item
        for key in item["match_keys"]:
            key_index[key] = canonical_key
        return

    existing_keys = list(dict.fromkeys([*(existing.get("match_keys") or []), *keys]))
    existing["match_keys"] = existing_keys
    for key in existing_keys:
        key_index[key] = canonical_key

    for field in ("title", "author", "source_url", "source_path", "source_platform", "source_kind", "queue_id", "draft_path"):
        if not existing.get(field) and candidate.get(field):
            existing[field] = candidate[field]

    existing["artifact_paths"] = list(dict.fromkeys([*(existing.get("artifact_paths") or []), *(candidate.get("artifact_paths") or [])]))
    evidence = dict(existing.get("evidence") or {})
    evidence.update({key: value for key, value in dict(candidate.get("evidence") or {}).items() if value not in (None, "", [])})
    existing["evidence"] = evidence

    current_priority = STAGE_CONFIG.get(str(existing.get("stage") or "feed_only"), {}).get("priority", 0)
    candidate_priority = STAGE_CONFIG.get(str(candidate.get("stage") or "feed_only"), {}).get("priority", 0)
    if candidate_priority >= current_priority:
        for field in ("stage", "reason", "primary_surface", "primary_action", "visibility", "next_action_label", "stage_label"):
            if candidate.get(field):
                existing[field] = candidate[field]
        for field in ("scheduled_at", "release_packet_path", "receipt_path"):
            if candidate.get(field):
                existing[field] = candidate[field]


def _candidate(
    *,
    linkedin_root: Path,
    stage: str,
    title: Any,
    source_url: Any = "",
    source_path: Any = "",
    draft_path: Any = "",
    queue_id: Any = "",
    author: Any = "",
    source_platform: Any = "",
    source_kind: Any = "",
    reason: str = "",
    artifact_paths: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    config = STAGE_CONFIG[stage]
    normalized_source_path = _workspace_relative_path(source_path, linkedin_root)
    normalized_draft_path = _workspace_relative_path(draft_path, linkedin_root)
    artifacts = [_artifact_path(path, linkedin_root) for path in (artifact_paths or []) if _clean(path)]
    if normalized_draft_path:
        artifacts.append(normalized_draft_path)
    payload = {
        "title": _clean(title) or _clean(queue_id) or "Untitled source",
        "author": _clean(author),
        "source_url": _clean(source_url),
        "source_path": normalized_source_path,
        "source_platform": _clean(source_platform),
        "source_kind": _clean(source_kind),
        "queue_id": _clean(queue_id).upper(),
        "draft_path": normalized_draft_path,
        "stage": stage,
        "stage_label": config["label"],
        "visibility": config["visibility"],
        "primary_surface": config["primary_surface"],
        "primary_action": config["primary_action"],
        "next_action_label": config["next_action_label"],
        "reason": reason or config["reason"],
        "artifact_paths": list(dict.fromkeys(artifacts)),
        "match_keys": _match_keys(
            linkedin_root=linkedin_root,
            title=title,
            source_url=source_url,
            source_path=source_path,
            draft_path=draft_path,
            queue_id=queue_id,
        ),
        "evidence": dict(evidence or {}),
    }
    payload.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    return payload


def _add_feed_items(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
    social_feed: dict[str, Any] | None,
) -> None:
    for item in (social_feed or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage="feed_only",
                title=item.get("title"),
                source_url=item.get("source_url"),
                source_path=item.get("source_path"),
                author=item.get("author"),
                source_platform=item.get("platform") or item.get("source_platform"),
                source_kind=item.get("source_lane") or item.get("source_type"),
                evidence={
                    "feed_item_id": item.get("id"),
                    "feed_score": ((item.get("ranking") or {}).get("total") if isinstance(item.get("ranking"), dict) else None),
                },
            ),
        )


def _add_reaction_queue_items(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
    reaction_queue: dict[str, Any] | None,
) -> None:
    queue = reaction_queue or {}
    for bucket, stage in (("comment_opportunities", "comment_candidate"), ("post_seeds", "post_seed"), ("latent_post_seeds", "latent_seed")):
        for item in queue.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            _merge_item(
                items_by_key,
                key_index,
                _candidate(
                    linkedin_root=linkedin_root,
                    stage=stage,
                    title=item.get("title"),
                    source_url=item.get("source_url"),
                    source_path=item.get("source_path"),
                    author=item.get("author"),
                    source_platform=item.get("source_platform"),
                    source_kind=bucket,
                    evidence={
                        "reaction_queue_bucket": bucket,
                        "qualification_route": item.get("qualification_route"),
                        "publish_posture": item.get("publish_posture"),
                        "latent_reason": item.get("latent_reason"),
                    },
                ),
            )


def _add_weekly_plan_items(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
    weekly_plan: dict[str, Any] | None,
) -> None:
    for item in (weekly_plan or {}).get("recommendations") or []:
        if not isinstance(item, dict):
            continue
        source_kind = _clean(item.get("source_kind")).lower()
        publish_posture = _clean(item.get("publish_posture")).lower()
        stage = "weekly_plan"
        if source_kind == "draft" or publish_posture == "owner_review_required":
            stage = "owner_review"
        elif publish_posture in {"approved", "owner_approved"}:
            stage = "banked"
        elif publish_posture in {"hold_private", "owner_parked", "parked"}:
            stage = "parked"
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage=stage,
                title=item.get("title"),
                source_path=item.get("source_path"),
                source_kind=item.get("source_kind"),
                reason="This item appears in the active weekly plan.",
                artifact_paths=[item.get("source_path")] if item.get("source_path") else [],
                evidence={
                    "weekly_plan_source_kind": item.get("source_kind"),
                    "publish_posture": item.get("publish_posture"),
                    "priority_lane": item.get("priority_lane"),
                },
            ),
        )


def _add_rejected_feedback_items(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
) -> None:
    feedback_path = linkedin_root / "analytics" / "feed_feedback.jsonl"
    for event in _read_jsonl(feedback_path):
        if _clean(event.get("decision")).lower() != "reject":
            continue
        title = event.get("title") or event.get("feed_item_id") or "Rejected source"
        notes = _clean(event.get("notes"))
        reason = notes or "The owner marked this source Not for FEEZIE from the feed decision surface."
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage="rejected",
                title=title,
                source_url=event.get("source_url"),
                source_path=event.get("source_path"),
                author=event.get("author"),
                source_platform=event.get("platform"),
                source_kind="feed_feedback_rejection",
                reason=reason,
                artifact_paths=[feedback_path],
                evidence={
                    "feedback_decision": event.get("decision"),
                    "feed_item_id": event.get("feed_item_id"),
                    "recorded_at": event.get("recorded_at"),
                    "lens": event.get("lens"),
                    "notes": event.get("notes"),
                    "evaluation_overall": event.get("evaluation_overall"),
                    "source_expression_quality": event.get("source_expression_quality"),
                },
            ),
        )


def _add_draft_items(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
) -> None:
    drafts_dir = linkedin_root / "drafts"
    if not drafts_dir.exists():
        return
    for path in sorted(drafts_dir.glob("*.md")):
        if path.name == "README.md" or path.name.startswith("queue_") or path.name.startswith("feezie_owner_review_packet_"):
            continue
        text = _read_text(path)
        frontmatter, body = _parse_frontmatter(text)
        title = frontmatter.get("title") or _first_heading(body) or path.stem
        stage = _stage_from_publish_posture(frontmatter.get("publish_posture"), frontmatter.get("owner_decision"))
        draft_rel = path.relative_to(linkedin_root).as_posix()
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage=stage,
                title=title,
                source_url=frontmatter.get("source_url"),
                source_path=frontmatter.get("source_path"),
                draft_path=draft_rel,
                author=frontmatter.get("author"),
                source_kind=frontmatter.get("source_kind") or frontmatter.get("draft_kind"),
                reason=f"Draft `{WORKSPACE_RELATIVE}/{draft_rel}` has publish_posture `{frontmatter.get('publish_posture') or 'unknown'}`.",
                evidence={
                    "draft_frontmatter": {
                        key: value
                        for key, value in frontmatter.items()
                        if key
                        in {
                            "draft_kind",
                            "source_kind",
                            "publish_posture",
                            "owner_decision",
                            "owner_reviewed_at",
                            "lane",
                            "priority_lane",
                        }
                    },
                },
            ),
        )


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _add_queue_items(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
) -> None:
    queue_path = linkedin_root / "drafts" / "queue_01.md"
    queue_text = _read_text(queue_path)
    if not queue_text:
        return
    for queue_id, title, block in _queue_blocks(queue_text):
        fields = _parse_queue_fields(block)
        approval_status = _clean(fields.get("approval status")).lower()
        status = _clean(fields.get("status")).lower()
        if approval_status in {"owner_approved", "approved"} or status.startswith("approved"):
            stage = "banked"
        elif approval_status in {"owner_parked", "parked"} or status.startswith("parked"):
            stage = "parked"
        else:
            stage = "owner_review"
        draft_path = _extract_path_from_status(fields.get("status"))
        artifacts = [draft_path] if draft_path else []
        if fields.get("owner packet"):
            artifacts.append(fields["owner packet"].split("#", 1)[0])
        if fields.get("banked copy"):
            artifacts.append(fields["banked copy"])
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage=stage,
                title=title,
                draft_path=draft_path,
                queue_id=queue_id,
                source_kind="feezie_queue",
                reason=f"Queue item `{queue_id}` is `{fields.get('approval status') or fields.get('status') or 'active'}`.",
                artifact_paths=artifacts,
                evidence={
                    "queue_status": fields.get("status"),
                    "approval_status": fields.get("approval status"),
                    "owner_packet": fields.get("owner packet"),
                    "banked_copy": fields.get("banked copy"),
                    "host_action": fields.get("host action"),
                },
            ),
        )


def _add_release_packets(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
) -> None:
    release_dir = linkedin_root / "docs" / "release_packets"
    if not release_dir.exists():
        return
    for path in sorted(release_dir.glob("*schedule_packet*.md")):
        queue_match = re.search(r"(feezie-\d+)", path.name, flags=re.IGNORECASE)
        if not queue_match:
            continue
        queue_id = queue_match.group(1).upper()
        rel = path.relative_to(linkedin_root).as_posix()
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage="banked",
                title=queue_id,
                queue_id=queue_id,
                source_kind="release_packet",
                release_packet_path=f"{WORKSPACE_RELATIVE}/{rel}",
                artifact_paths=[rel],
                reason=f"Release packet `{WORKSPACE_RELATIVE}/{rel}` banks approved copy for host scheduling.",
                evidence={"release_packet_path": f"{WORKSPACE_RELATIVE}/{rel}"},
            ),
        )


def _add_scheduled_receipts(
    items_by_key: dict[str, dict[str, Any]],
    key_index: dict[str, str],
    *,
    linkedin_root: Path,
) -> None:
    analytics_dir = linkedin_root / "analytics"
    if not analytics_dir.exists():
        return
    for path in sorted(analytics_dir.glob("*/scheduled_receipt.json")):
        receipt = _read_json(path)
        if not receipt:
            continue
        queue_id = _clean(receipt.get("queue_id")).upper()
        if not queue_id:
            queue_match = re.search(r"(feezie-\d+)", path.parent.name, flags=re.IGNORECASE)
            queue_id = queue_match.group(1).upper() if queue_match else ""
        if not queue_id:
            continue
        rel = path.relative_to(linkedin_root).as_posix()
        _merge_item(
            items_by_key,
            key_index,
            _candidate(
                linkedin_root=linkedin_root,
                stage="scheduled",
                title=queue_id,
                queue_id=queue_id,
                source_kind="scheduled_receipt",
                receipt_path=f"{WORKSPACE_RELATIVE}/{rel}",
                scheduled_at=receipt.get("scheduled_at_et") or receipt.get("scheduled_at_utc"),
                artifact_paths=[rel, receipt.get("analytics_log_path"), receipt.get("release_packet_path"), receipt.get("publishing_schedule_path")],
                reason=f"Scheduling receipt `{WORKSPACE_RELATIVE}/{rel}` confirms host scheduling.",
                evidence={
                    "scheduled_at_et": receipt.get("scheduled_at_et"),
                    "scheduled_at_utc": receipt.get("scheduled_at_utc"),
                    "asset_decision": receipt.get("asset_decision"),
                    "confirmation_method": receipt.get("confirmation_method"),
                    "screenshot_present": receipt.get("screenshot_present"),
                },
            ),
        )


def build_source_lifecycle(
    *,
    linkedin_root: Path,
    social_feed: dict[str, Any] | None = None,
    reaction_queue: dict[str, Any] | None = None,
    weekly_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only lifecycle projection over existing FEEZIE artifacts."""

    items_by_key: dict[str, dict[str, Any]] = {}
    key_index: dict[str, str] = {}
    _add_feed_items(items_by_key, key_index, linkedin_root=linkedin_root, social_feed=social_feed)
    _add_reaction_queue_items(items_by_key, key_index, linkedin_root=linkedin_root, reaction_queue=reaction_queue)
    _add_weekly_plan_items(items_by_key, key_index, linkedin_root=linkedin_root, weekly_plan=weekly_plan)
    _add_rejected_feedback_items(items_by_key, key_index, linkedin_root=linkedin_root)
    _add_draft_items(items_by_key, key_index, linkedin_root=linkedin_root)
    _add_queue_items(items_by_key, key_index, linkedin_root=linkedin_root)
    _add_release_packets(items_by_key, key_index, linkedin_root=linkedin_root)
    _add_scheduled_receipts(items_by_key, key_index, linkedin_root=linkedin_root)

    items = sorted(
        items_by_key.values(),
        key=lambda item: (
            -int(STAGE_CONFIG.get(str(item.get("stage") or "feed_only"), {}).get("priority", 0)),
            str(item.get("title") or "").lower(),
        ),
    )
    stage_counts: dict[str, int] = {}
    visibility_counts: dict[str, int] = {}
    for item in items:
        stage = str(item.get("stage") or "feed_only")
        visibility = str(item.get("visibility") or "needs_decision")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        visibility_counts[visibility] = visibility_counts.get(visibility, 0) + 1

    return {
        "schema_version": "source_lifecycle/v1",
        "generated_at": _now_iso(),
        "workspace": WORKSPACE_KEY,
        "source_ref": str(linkedin_root),
        "counts": {
            "total": len(items),
            "by_stage": stage_counts,
            "by_visibility": visibility_counts,
            "needs_decision": visibility_counts.get("needs_decision", 0),
            "in_workflow": sum(count for key, count in visibility_counts.items() if key not in {"needs_decision", "resolved", "rejected", "published"}),
        },
        "items": items,
    }
