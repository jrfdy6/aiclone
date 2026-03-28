from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.social_feed_builder_service import (
    build_feed as build_social_feed_runtime_payload,
    discover_linkedin_workspace_root,
)
from app.services.social_feedback_service import social_feedback_service
from app.services.social_feed_refresh import social_feed_refresh_service
from app.services.workspace_snapshot_store import get_snapshot_payload, upsert_snapshot


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/app/backend"), Path("/")]
    seen: set[Path] = set()
    for parent in candidates:
        if parent in seen:
            continue
        seen.add(parent)
        if (parent / "workspaces" / "linkedin-content-os").exists() or (parent / "backend" / "workspaces" / "linkedin-content-os").exists():
            return parent
    return current.parents[3]


ROOT = resolve_workspace_root()


def _candidate_roots() -> list[Path]:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, ROOT, Path("/app"), Path("/app/backend"), Path("/")]
    ordered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _find_dir(*relative_patterns: str) -> Path | None:
    for base in _candidate_roots():
        for pattern in relative_patterns:
            candidate = base / pattern
            if candidate.exists() and candidate.is_dir():
                return candidate
    return None


def _find_file(*relative_patterns: str) -> Path | None:
    for base in _candidate_roots():
        for pattern in relative_patterns:
            candidate = base / pattern
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def _discover_linkedin_root() -> Path:
    return discover_linkedin_workspace_root()


def _discover_persona_root() -> Path:
    direct = _find_dir(
        "knowledge/persona/feeze",
        "backend/knowledge/persona/feeze",
        "persona/feeze",
    )
    if direct:
        return direct

    for base in [ROOT, Path.cwd(), Path("/app"), Path("/app/backend")]:
        if not base.exists():
            continue
        match = next(base.rglob("knowledge/persona/feeze/identity/claims.md"), None)
        if match:
            return match.parent.parent

    return ROOT / "knowledge" / "persona" / "feeze"


def _discover_doc_targets() -> list[Path]:
    patterns = [
        ("SOPs/_index.md", "backend/SOPs/_index.md"),
        ("SOPs/direct_postgres_bootstrap.md", "backend/SOPs/direct_postgres_bootstrap.md"),
        ("deliverables/brain-tab-ui-requirements.md", "backend/deliverables/brain-tab-ui-requirements.md"),
        ("docs/persistent_memory_blueprint.md", "backend/docs/persistent_memory_blueprint.md"),
    ]
    targets: list[Path] = []
    for pair in patterns:
        found = _find_file(*pair)
        if found:
            targets.append(found)
    return targets


PERSONA_ROOT = _discover_persona_root()
LINKEDIN_ROOT = _discover_linkedin_root()
DOC_TARGETS = _discover_doc_targets()
WORKSPACE_KEY = "linkedin-content-os"
SNAPSHOT_WEEKLY_PLAN = "weekly_plan"
SNAPSHOT_REACTION_QUEUE = "reaction_queue"
SNAPSHOT_SOCIAL_FEED = "social_feed"
SNAPSHOT_FEEDBACK_SUMMARY = "feedback_summary"


def _load_module(module_name: str, script_path: Path) -> Any | None:
    if not script_path.exists():
        return None
    script_dir = str(script_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _first_meaningful_line(raw: str) -> str:
    return next(
        (
            line
            for line in (segment.strip() for segment in raw.splitlines())
            if line and not line.startswith("#")
        ),
        "",
    )


def _walk(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    results: list[Path] = []
    for entry in sorted(dir_path.iterdir(), key=lambda item: item.name):
        if entry.is_dir():
            results.extend(_walk(entry))
        else:
            results.append(entry)
    return results


def _serialize_file(file_path: Path, root: Path, label: str) -> dict[str, str]:
    try:
        relative_path = file_path.relative_to(ROOT).as_posix()
    except ValueError:
        relative_path = file_path.as_posix()
    relative_to_root = file_path.relative_to(root).as_posix()
    segments = relative_to_root.split("/")
    group = f"{label}/{segments[0]}" if len(segments) > 1 else label
    raw = file_path.read_text(encoding="utf-8")
    stat = file_path.stat()
    return {
        "group": group,
        "name": file_path.name,
        "path": relative_path,
        "snippet": _first_meaningful_line(raw),
        "content": raw,
        "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def _load_workspace_files() -> list[dict[str, str]]:
    roots = [
        (PERSONA_ROOT, "persona-bundle"),
        (LINKEDIN_ROOT, "linkedin-content-os"),
    ]
    files: list[dict[str, str]] = []
    for root, label in roots:
        if not root.exists():
            continue
        for file_path in _walk(root):
            if file_path.suffix not in {".md", ".json"}:
                continue
            files.append(_serialize_file(file_path, root, label))
    return files


def _load_doc_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for file_path in DOC_TARGETS:
        if not file_path.exists():
            continue
        raw = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        entries.append(
            {
                "name": file_path.name,
                "path": file_path.relative_to(ROOT).as_posix(),
                "snippet": _first_meaningful_line(raw),
                "content": raw,
                "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )
    return entries


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _extract_markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    section = text[start + len(marker) :].lstrip()
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    return section.strip()


def _split_markdown_blocks(section: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^###\s+(.+)$", section, flags=re.MULTILINE))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        blocks.append((match.group(1).strip(), section[start:end].strip()))
    return blocks


def _clean_markdown_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1]
    return "" if cleaned == "-" else cleaned


def _parse_markdown_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            current_key = key.strip().lower()
            fields[current_key] = _clean_markdown_value(value)
            continue
        if current_key and line.startswith("  ") and stripped:
            existing = fields.get(current_key, "")
            fields[current_key] = f"{existing}\n{stripped}".strip()
    return fields


def _parse_weekly_plan_markdown(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    generated_match = re.search(r"^Generated:\s+(.+)$", text, flags=re.MULTILINE)
    recommendations = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Recommended Posts")):
        fields = _parse_markdown_fields(block)
        title = re.sub(r"^\d+\.\s*", "", heading).strip()
        recommendations.append(
            {
                "source_kind": fields.get("source", ""),
                "title": title,
                "category": fields.get("category", ""),
                "role_alignment": fields.get("role alignment", ""),
                "risk_level": fields.get("risk level", ""),
                "publish_posture": fields.get("publish posture", ""),
                "hook": fields.get("hook", ""),
                "rationale": fields.get("why now", ""),
                "source_path": fields.get("source file", ""),
                "score": 0,
                "priority_lane": fields.get("priority lane", ""),
            }
        )
    market_signals = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Market Signals")):
        fields = _parse_markdown_fields(block)
        market_signals.append(
            {
                "source_kind": fields.get("source", ""),
                "title": heading,
                "theme": fields.get("theme", ""),
                "priority_lane": fields.get("priority lane", ""),
                "role_alignment": fields.get("role alignment", ""),
                "summary": fields.get("what the market is saying", ""),
                "pain_points": [item.strip() for item in fields.get("pain points", "").split(",") if item.strip()],
                "language_patterns": [item.strip() for item in fields.get("language patterns", "").split(",") if item.strip()],
                "headline_candidates": [item.strip() for item in fields.get("hook candidates", "").split(",") if item.strip()],
                "source_path": fields.get("source file", ""),
            }
        )
    positioning_model = [line[2:].strip() for line in _extract_markdown_section(text, "Positioning Model").splitlines() if line.startswith("- ")]
    priority_lanes = [line[2:].strip() for line in _extract_markdown_section(text, "This Week's Priority Lanes").splitlines() if line.startswith("- ")]
    research_notes = [line[2:].strip("`") for line in _extract_markdown_section(text, "Research Feed").splitlines() if line.startswith("- ")]
    draft_count = len([path for path in (LINKEDIN_ROOT / "drafts").glob("*.md") if path.name != "README.md" and not path.name.startswith("queue_")])
    return {
        "generated_at": generated_match.group(1).strip() if generated_match else None,
        "workspace": "workspaces/linkedin-content-os",
        "positioning_model": positioning_model,
        "priority_lanes": priority_lanes,
        "recommendations": recommendations,
        "hold_items": [],
        "market_signals": market_signals,
        "research_notes": research_notes,
        "source_counts": {
            "drafts": draft_count,
            "media": 0,
            "research": len(market_signals),
        },
    }


def _parse_reaction_queue_markdown(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    generated_match = re.search(r"^Generated:\s+(.+)$", text, flags=re.MULTILINE)
    comment_opportunities = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Immediate Comment Opportunities")):
        fields = _parse_markdown_fields(block)
        comment_opportunities.append(
            {
                "title": heading,
                "author": fields.get("source", "").split("/", 1)[1].strip() if "/" in fields.get("source", "") else "",
                "source_platform": fields.get("source", "").split("/", 1)[0].strip("` ").lower() if fields.get("source") else "",
                "source_type": "post",
                "source_url": "",
                "source_path": fields.get("source file", ""),
                "priority_lane": fields.get("lane", ""),
                "role_alignment": "",
                "risk_level": "",
                "publish_posture": "",
                "recommended_move": fields.get("move", ""),
                "hook": fields.get("hook to react to", ""),
                "summary": fields.get("why this matters", ""),
                "why_it_matters": fields.get("why this matters", ""),
                "comment_angle": fields.get("comment angle", ""),
                "suggested_comment": fields.get("suggested comment", "").replace("\n", " ").strip(),
                "post_angle": "",
                "score": 0,
            }
        )
    post_seeds = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Standalone Post Seeds")):
        fields = _parse_markdown_fields(block)
        post_seeds.append(
            {
                "title": heading,
                "author": "",
                "source_platform": "",
                "source_type": "",
                "source_url": "",
                "source_path": fields.get("source file", ""),
                "priority_lane": "",
                "role_alignment": fields.get("role alignment", ""),
                "risk_level": fields.get("risk", ""),
                "publish_posture": "",
                "recommended_move": "save_for_post",
                "hook": "",
                "summary": fields.get("post angle", ""),
                "why_it_matters": "",
                "comment_angle": "",
                "suggested_comment": "",
                "post_angle": fields.get("post angle", ""),
                "score": 0,
            }
        )
    return {
        "generated_at": generated_match.group(1).strip() if generated_match else None,
        "workspace": "workspaces/linkedin-content-os",
        "comment_opportunities": comment_opportunities,
        "post_seeds": post_seeds,
        "background_only": [],
        "counts": {
            "comment_opportunities": len(comment_opportunities),
            "post_seeds": len(post_seeds),
            "background_only": 0,
        },
    }


def _parse_social_feed_markdown(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    updated_match = re.search(r"^Updated\s+(.+)$", text, flags=re.MULTILINE)
    return {
        "generated_at": updated_match.group(1).strip() if updated_match else None,
        "workspace": "linkedin-content-os",
        "strategy_mode": "production",
        "items": [],
    }


def _ingestions_root() -> Path:
    direct = _find_dir("backend/knowledge/ingestions", "knowledge/ingestions")
    if direct:
        return direct
    return ROOT / "knowledge" / "ingestions"


def _build_weekly_plan_payload() -> dict[str, Any] | None:
    script_path = _find_file(
        "backend/scripts/personal-brand/generate_linkedin_weekly_plan.py",
        "scripts/personal-brand/generate_linkedin_weekly_plan.py",
    )
    module = _load_module("generate_linkedin_weekly_plan_runtime", script_path) if script_path else None
    if module is None or not LINKEDIN_ROOT.exists():
        return None
    draft_candidates, draft_source_refs = module.load_draft_candidates(LINKEDIN_ROOT)
    media_candidates = module.load_media_candidates(_ingestions_root())
    research_candidates, research_signals, research_notes = module.load_research_candidates(LINKEDIN_ROOT)
    filtered_research_candidates = [item for item in research_candidates if item.source_path not in draft_source_refs]
    all_candidates = sorted(draft_candidates + media_candidates + filtered_research_candidates, key=lambda item: (-item.score, item.title.lower()))
    recommendations = [item for item in all_candidates if item.publish_posture != "hold_private"][:5]
    hold_items = [item for item in all_candidates if item.publish_posture == "hold_private" or item.risk_level == "high"][:10]
    return module.plan_payload(
        workspace_dir=LINKEDIN_ROOT,
        recommendations=recommendations,
        hold_items=hold_items,
        research_signals=research_signals,
        research_notes=research_notes,
        counts={
            "drafts": len(draft_candidates),
            "media": len(media_candidates),
            "research": len(filtered_research_candidates),
        },
    )


def _build_reaction_queue_payload() -> dict[str, Any] | None:
    script_path = _find_file(
        "backend/scripts/personal-brand/generate_linkedin_reaction_queue.py",
        "scripts/personal-brand/generate_linkedin_reaction_queue.py",
    )
    module = _load_module("generate_linkedin_reaction_queue_runtime", script_path) if script_path else None
    if module is None or not LINKEDIN_ROOT.exists():
        return None
    items = module.load_market_signal_items(LINKEDIN_ROOT)[:8]
    return module.queue_payload(LINKEDIN_ROOT, items)


def _build_social_feed_payload() -> dict[str, Any] | None:
    try:
        payload = build_social_feed_runtime_payload(LINKEDIN_ROOT)
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, payload) else None


def _load_feedback_summary_payload() -> dict[str, Any] | None:
    try:
        return social_feedback_service.load_summary()
    except Exception:
        return _load_json(LINKEDIN_ROOT / "analytics" / "feed_feedback_summary.json")


def _runtime_snapshot_payload(snapshot_type: str) -> dict[str, Any] | None:
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        return (
            _build_weekly_plan_payload()
            or _load_json(LINKEDIN_ROOT / "plans" / "weekly_plan.json")
            or _parse_weekly_plan_markdown(LINKEDIN_ROOT / "plans" / "weekly_plan.md")
        )
    if snapshot_type == SNAPSHOT_REACTION_QUEUE:
        return (
            _build_reaction_queue_payload()
            or _load_json(LINKEDIN_ROOT / "plans" / "reaction_queue.json")
            or _parse_reaction_queue_markdown(LINKEDIN_ROOT / "plans" / "reaction_queue.md")
        )
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        built = _build_social_feed_payload()
        if built:
            return built
        json_payload = _load_json(LINKEDIN_ROOT / "plans" / "social_feed.json")
        if json_payload and _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, json_payload):
            return json_payload
        markdown_payload = _parse_social_feed_markdown(LINKEDIN_ROOT / "plans" / "social_feed.md")
        if markdown_payload and _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, markdown_payload):
            return markdown_payload
        return None
    if snapshot_type == SNAPSHOT_FEEDBACK_SUMMARY:
        return _load_feedback_summary_payload()
    return None


def _persist_snapshot(snapshot_type: str, payload: dict[str, Any], source: str) -> dict[str, Any]:
    upsert_snapshot(
        WORKSPACE_KEY,
        snapshot_type,
        payload,
        metadata={
            "source": source,
            "payload_generated_at": payload.get("generated_at"),
        },
    )
    return payload


def _snapshot_is_usable(snapshot_type: str, payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return False
        first_item = items[0]
        return isinstance(first_item, dict) and bool(first_item.get("lens_variants"))
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        return isinstance(payload.get("recommendations"), list) and isinstance(payload.get("positioning_model"), list)
    if snapshot_type == SNAPSHOT_REACTION_QUEUE:
        return isinstance(payload.get("comment_opportunities"), list) and isinstance(payload.get("post_seeds"), list)
    if snapshot_type == SNAPSHOT_FEEDBACK_SUMMARY:
        return "total_events" in payload
    return True


def _load_snapshot(snapshot_type: str) -> dict[str, Any] | None:
    persisted = get_snapshot_payload(WORKSPACE_KEY, snapshot_type)
    if persisted and _snapshot_is_usable(snapshot_type, persisted):
        return persisted
    payload = _runtime_snapshot_payload(snapshot_type)
    if payload:
        source = "runtime_refresh" if persisted else "runtime_bootstrap"
        return _persist_snapshot(snapshot_type, payload, source)
    return None


class WorkspaceSnapshotService:
    def refresh_persisted_linkedin_os_state(self) -> dict[str, Any]:
        snapshot_types = [
            SNAPSHOT_WEEKLY_PLAN,
            SNAPSHOT_REACTION_QUEUE,
            SNAPSHOT_SOCIAL_FEED,
            SNAPSHOT_FEEDBACK_SUMMARY,
        ]
        refreshed: dict[str, Any] = {}
        for snapshot_type in snapshot_types:
            payload = _runtime_snapshot_payload(snapshot_type)
            if payload:
                refreshed[snapshot_type] = _persist_snapshot(snapshot_type, payload, "refresh")
        return refreshed

    def get_linkedin_os_snapshot(self) -> dict[str, Any]:
        weekly_plan = _load_snapshot(SNAPSHOT_WEEKLY_PLAN)
        reaction_queue = _load_snapshot(SNAPSHOT_REACTION_QUEUE)
        social_feed = _load_snapshot(SNAPSHOT_SOCIAL_FEED)
        feedback_summary = _load_snapshot(SNAPSHOT_FEEDBACK_SUMMARY)
        return {
            "workspace_files": _load_workspace_files(),
            "doc_entries": _load_doc_entries(),
            "weekly_plan": weekly_plan,
            "reaction_queue": reaction_queue,
            "social_feed": social_feed,
            "feedback_summary": feedback_summary,
            "refresh_status": social_feed_refresh_service.get_status(),
        }


workspace_snapshot_service = WorkspaceSnapshotService()
