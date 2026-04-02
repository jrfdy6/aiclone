from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import persona_delta_service
from app.services.content_reservoir_service import build_content_reservoir_payload
from app.services.social_feed_builder_service import (
    build_feed as build_social_feed_runtime_payload,
    discover_linkedin_workspace_root,
)
from app.services.social_feedback_service import social_feedback_service
from app.services.social_feed_refresh import social_feed_refresh_service
from app.services.social_long_form_signal_service import build_long_form_route_summary
from app.services.social_persona_review_service import social_persona_review_service
from app.services.social_source_asset_service import build_source_asset_inventory
from app.services.workspace_snapshot_store import get_snapshot_payload, list_snapshot_payloads, upsert_snapshot


TRANSCRIPT_LIBRARY_SKIP_NAMES = {"README.md", "TEMPLATE.md", "INDEX.md"}


def _count_matching_files(path: Path, pattern: str, *, exclude_names: set[str] | None = None) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    excluded = exclude_names or set()
    return sum(1 for item in path.rglob(pattern) if item.is_file() and item.name not in excluded)


def _workspace_root_score(path: Path) -> tuple[int, int]:
    score = 0
    if (path / "workspaces" / "linkedin-content-os").exists():
        score += 100
    if (path / "backend" / "workspaces" / "linkedin-content-os").exists():
        score += 60
    score += _count_matching_files(path / "knowledge" / "ingestions", "normalized.md") * 20
    score += _count_matching_files(
        path / "knowledge" / "aiclone" / "transcripts",
        "*.md",
        exclude_names=TRANSCRIPT_LIBRARY_SKIP_NAMES,
    ) * 8
    return score, -len(path.parts)


def _external_workspace_roots() -> list[Path]:
    configured = os.environ.get("OPENCLAW_WORKSPACE_ROOT")
    candidates = [configured, "/Users/neo/.openclaw/workspace"]
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path in seen:
            continue
        seen.add(path)
        roots.append(path)
    return roots


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, *_external_workspace_roots(), Path("/app"), Path("/app/backend"), Path("/")]
    seen: set[Path] = set()
    best_root: Path | None = None
    best_score = (-1, 0)
    for parent in candidates:
        if parent in seen:
            continue
        seen.add(parent)
        score = _workspace_root_score(parent)
        if score > best_score:
            best_root = parent
            best_score = score
    if best_root is not None and best_score[0] > 0:
        return best_root
    return current.parents[3]


ROOT = resolve_workspace_root()


def _candidate_roots() -> list[Path]:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, *_external_workspace_roots(), ROOT, Path("/app"), Path("/app/backend"), Path("/")]
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


def _find_richest_dir(*relative_patterns: str, pattern: str, exclude_names: set[str] | None = None) -> Path | None:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for base in _candidate_roots():
        for relative_pattern in relative_patterns:
            candidate = base / relative_pattern
            if not candidate.exists() or not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(resolved)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            _count_matching_files(item, pattern, exclude_names=exclude_names),
            -len(item.parts),
        ),
    )


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


def _discover_doc_roots() -> list[tuple[Path, str]]:
    candidates = [
        (_find_dir("SOPs", "backend/SOPs"), "Operating Docs"),
        (_find_dir("docs", "backend/docs"), "System Docs"),
        (_find_dir("deliverables", "backend/deliverables"), "Reference Docs"),
        (_find_dir("workspaces/linkedin-content-os/docs", "backend/workspaces/linkedin-content-os/docs"), "Workspace Reference"),
    ]
    roots: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for root, label in candidates:
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append((root, label))
    return roots


def _discover_doc_targets() -> list[tuple[Path, str]]:
    patterns = [
        ("AGENTS.md", "backend/AGENTS.md", "Operating Docs"),
        ("CODEX_STARTUP.md", "backend/CODEX_STARTUP.md", "Operating Docs"),
        ("README.md", "backend/README.md", "Reference Docs"),
        ("workspaces/linkedin-content-os/README.md", "backend/workspaces/linkedin-content-os/README.md", "Workspace Reference"),
        ("workspaces/linkedin-content-os/AGENTS.md", "backend/workspaces/linkedin-content-os/AGENTS.md", "Workspace Reference"),
    ]
    targets: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for primary, fallback, label in patterns:
        found = _find_file(primary, fallback)
        if found is None or found in seen:
            continue
        seen.add(found)
        targets.append((found, label))
    return targets


def _ordered_existing_paths(paths: list[Path]) -> list[Path]:
    ordered: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def _workspace_file_roots() -> list[tuple[Path, str]]:
    persona_candidates = _ordered_existing_paths(
        [
            ROOT / "knowledge" / "persona" / "feeze",
            ROOT.parent / "knowledge" / "persona" / "feeze",
            _discover_persona_root(),
        ]
    )
    linkedin_candidates = _ordered_existing_paths(
        [
            ROOT / "workspaces" / "linkedin-content-os",
            ROOT.parent / "workspaces" / "linkedin-content-os",
            _discover_linkedin_root(),
        ]
    )
    roots: list[tuple[Path, str]] = []
    roots.extend((path, "persona-bundle") for path in persona_candidates)
    roots.extend((path, "linkedin-content-os") for path in linkedin_candidates)
    return roots


def _doc_root_candidates() -> list[tuple[Path, str]]:
    candidates = [
        (ROOT / "SOPs", "Operating Docs"),
        (ROOT.parent / "SOPs", "Operating Docs"),
        (ROOT / "docs", "System Docs"),
        (ROOT.parent / "docs", "System Docs"),
        (ROOT / "deliverables", "Reference Docs"),
        (ROOT.parent / "deliverables", "Reference Docs"),
        (ROOT / "workspaces" / "linkedin-content-os" / "docs", "Workspace Reference"),
        (ROOT.parent / "workspaces" / "linkedin-content-os" / "docs", "Workspace Reference"),
    ]
    roots: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, label in candidates:
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_dir() or resolved in seen:
            continue
        seen.add(resolved)
        roots.append((resolved, label))
    for path, label in _discover_doc_roots():
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_dir() or resolved in seen:
            continue
        seen.add(resolved)
        roots.append((resolved, label))
    return roots


def _doc_target_candidates() -> list[tuple[Path, str]]:
    candidates = [
        (ROOT / "AGENTS.md", "Operating Docs"),
        (ROOT.parent / "AGENTS.md", "Operating Docs"),
        (ROOT / "CODEX_STARTUP.md", "Operating Docs"),
        (ROOT.parent / "CODEX_STARTUP.md", "Operating Docs"),
        (ROOT / "README.md", "Reference Docs"),
        (ROOT.parent / "README.md", "Reference Docs"),
        (ROOT / "workspaces" / "linkedin-content-os" / "README.md", "Workspace Reference"),
        (ROOT.parent / "workspaces" / "linkedin-content-os" / "README.md", "Workspace Reference"),
        (ROOT / "workspaces" / "linkedin-content-os" / "AGENTS.md", "Workspace Reference"),
        (ROOT.parent / "workspaces" / "linkedin-content-os" / "AGENTS.md", "Workspace Reference"),
    ]
    targets: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, label in candidates:
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_file() or resolved in seen:
            continue
        seen.add(resolved)
        targets.append((resolved, label))
    for path, label in _discover_doc_targets():
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_file() or resolved in seen:
            continue
        seen.add(resolved)
        targets.append((resolved, label))
    return targets


WORKSPACE_KEY = "linkedin-content-os"
SNAPSHOT_WEEKLY_PLAN = "weekly_plan"
SNAPSHOT_REACTION_QUEUE = "reaction_queue"
SNAPSHOT_SOCIAL_FEED = "social_feed"
SNAPSHOT_FEEDBACK_SUMMARY = "feedback_summary"
SNAPSHOT_SOURCE_ASSETS = "source_assets"
SNAPSHOT_PERSONA_REVIEW_SUMMARY = "persona_review_summary"
SNAPSHOT_LONG_FORM_ROUTES = "long_form_routes"
SNAPSHOT_CONTENT_RESERVOIR = "content_reservoir"


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
    files: list[dict[str, str]] = []
    for root, label in _workspace_file_roots():
        if not root.exists():
            continue
        for file_path in _walk(root):
            if file_path.suffix not in {".md", ".json"}:
                continue
            files.append(_serialize_file(file_path, root, label))
    return files


def _load_doc_entries() -> list[dict[str, str]]:
    entries_by_path: dict[str, dict[str, str]] = {}
    for root, label in _doc_root_candidates():
        for file_path in _walk(root):
            if file_path.suffix != ".md":
                continue
            entry = _serialize_file(file_path, root, label)
            entry["group"] = label
            entries_by_path[entry["path"]] = entry

    for file_path, label in _doc_target_candidates():
        raw = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        try:
            relative_path = file_path.relative_to(ROOT).as_posix()
        except ValueError:
            relative_path = file_path.as_posix()
        entries_by_path[relative_path] = {
            "name": file_path.name,
            "path": relative_path,
            "snippet": _first_meaningful_line(raw),
            "content": raw,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "group": label,
        }

    entries = list(entries_by_path.values())
    entries.sort(key=lambda item: item["path"])
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
    linkedin_root = _discover_linkedin_root()
    draft_count = len([path for path in (linkedin_root / "drafts").glob("*.md") if path.name != "README.md" and not path.name.startswith("queue_")])
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


def _long_form_plan_candidate(candidate: dict[str, Any], *, source_kind: str) -> dict[str, Any]:
    lane_hint = str(candidate.get("lane_hint") or "").strip()
    title = str(candidate.get("title") or "Long-form source").strip() or "Long-form source"
    segment = str(candidate.get("segment") or "").strip()
    route_reason = str(candidate.get("route_reason") or "").strip()
    belief_summary = str(candidate.get("belief_summary") or "").strip()
    rationale = route_reason
    if belief_summary:
        rationale = f"{route_reason} Belief: {belief_summary}.".strip()
    return {
        "source_kind": source_kind,
        "title": title,
        "category": "Long-form media",
        "role_alignment": "operator clarity",
        "risk_level": "review",
        "publish_posture": "draft",
        "hook": segment,
        "rationale": rationale,
        "source_path": str(candidate.get("source_path") or ""),
        "score": int(candidate.get("route_score") or 0),
        "priority_lane": lane_hint,
        "source_url": str(candidate.get("source_url") or ""),
        "target_file": str(candidate.get("target_file") or ""),
        "route_reason": route_reason,
        "response_modes": list(candidate.get("response_modes") or []),
        "handoff_lane": str(candidate.get("handoff_lane") or ""),
        "handoff_reason": str(candidate.get("handoff_reason") or ""),
        "secondary_consumers": list(candidate.get("secondary_consumers") or []),
    }


def _augment_weekly_plan_payload(payload: dict[str, Any] | None, long_form_routes: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    if not isinstance(long_form_routes, dict):
        return payload

    candidates = long_form_routes.get("candidates")
    if not isinstance(candidates, list):
        return payload

    media_post_seeds = [
        _long_form_plan_candidate(candidate, source_kind="long_form_post_seed")
        for candidate in candidates
        if isinstance(candidate, dict) and str(candidate.get("handoff_lane") or "") == "post_candidate"
    ][:6]
    brief_awareness_candidates = [
        _long_form_plan_candidate(candidate, source_kind="long_form_brief_awareness")
        for candidate in candidates
        if isinstance(candidate, dict) and str(candidate.get("handoff_lane") or "") == "brief_only"
    ][:6]
    belief_evidence_candidates = [
        _long_form_plan_candidate(candidate, source_kind="long_form_belief_evidence")
        for candidate in candidates
        if isinstance(candidate, dict) and str(candidate.get("handoff_lane") or "") == "persona_candidate"
    ][:6]
    operational_route_candidates = [
        _long_form_plan_candidate(candidate, source_kind="long_form_route_to_pm")
        for candidate in candidates
        if isinstance(candidate, dict) and str(candidate.get("handoff_lane") or "") == "route_to_pm"
    ][:6]

    counts = payload.get("source_counts")
    counts_dict = dict(counts) if isinstance(counts, dict) else {}
    counts_dict["media"] = len(media_post_seeds)
    counts_dict["brief_only"] = len(brief_awareness_candidates)
    counts_dict["belief_evidence"] = len(belief_evidence_candidates)
    counts_dict["route_to_pm"] = len(operational_route_candidates)

    augmented = dict(payload)
    base_generated_at = payload.get("generated_at")
    route_generated_at = long_form_routes.get("generated_at")
    has_route_overlay = bool(media_post_seeds or brief_awareness_candidates or belief_evidence_candidates or operational_route_candidates)
    if has_route_overlay:
        augmented["base_generated_at"] = base_generated_at
        augmented["generated_at"] = route_generated_at or base_generated_at
    augmented["source_counts"] = counts_dict
    augmented["media_post_seeds"] = media_post_seeds
    augmented["brief_awareness_candidates"] = brief_awareness_candidates
    augmented["belief_evidence_candidates"] = belief_evidence_candidates
    augmented["operational_route_candidates"] = operational_route_candidates
    augmented["media_summary"] = {
        "generated_at": route_generated_at,
        "assets_considered": int(long_form_routes.get("assets_considered") or 0),
        "segments_total": int(long_form_routes.get("segments_total") or 0),
        "route_counts": long_form_routes.get("route_counts") or {},
        "primary_route_counts": long_form_routes.get("primary_route_counts") or {},
        "handoff_lane_counts": long_form_routes.get("handoff_lane_counts") or {},
    }
    return augmented


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
    direct = _find_richest_dir("knowledge/ingestions", "backend/knowledge/ingestions", pattern="normalized.md")
    if direct:
        return direct
    return ROOT / "knowledge" / "ingestions"


def _transcripts_root() -> Path:
    direct = _find_richest_dir(
        "knowledge/aiclone/transcripts",
        "backend/knowledge/aiclone/transcripts",
        pattern="*.md",
        exclude_names=TRANSCRIPT_LIBRARY_SKIP_NAMES,
    )
    if direct:
        return direct
    return ROOT / "knowledge" / "aiclone" / "transcripts"


def _build_weekly_plan_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    script_path = _find_file(
        "backend/scripts/personal-brand/generate_linkedin_weekly_plan.py",
        "scripts/personal-brand/generate_linkedin_weekly_plan.py",
    )
    module = _load_module("generate_linkedin_weekly_plan_runtime", script_path) if script_path else None
    if module is None or not linkedin_root.exists():
        return None
    draft_candidates, draft_source_refs = module.load_draft_candidates(linkedin_root)
    media_candidates = module.load_media_candidates(_ingestions_root())
    research_candidates, research_signals, research_notes = module.load_research_candidates(linkedin_root)
    filtered_research_candidates = [item for item in research_candidates if item.source_path not in draft_source_refs]
    all_candidates = sorted(draft_candidates + media_candidates + filtered_research_candidates, key=lambda item: (-item.score, item.title.lower()))
    recommendations = [item for item in all_candidates if item.publish_posture != "hold_private"][:5]
    hold_items = [item for item in all_candidates if item.publish_posture == "hold_private" or item.risk_level == "high"][:10]
    payload = module.plan_payload(
        workspace_dir=linkedin_root,
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
    long_form_routes = _current_long_form_routes_payload()
    return _augment_weekly_plan_payload(payload, long_form_routes)


def _build_reaction_queue_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    script_path = _find_file(
        "backend/scripts/personal-brand/generate_linkedin_reaction_queue.py",
        "scripts/personal-brand/generate_linkedin_reaction_queue.py",
    )
    module = _load_module("generate_linkedin_reaction_queue_runtime", script_path) if script_path else None
    if module is None or not linkedin_root.exists():
        return None
    items = module.load_market_signal_items(linkedin_root)[:8]
    return module.queue_payload(linkedin_root, items)


def _build_social_feed_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    try:
        payload = build_social_feed_runtime_payload(linkedin_root)
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, payload) else None


def _build_source_assets_payload() -> dict[str, Any] | None:
    try:
        payload = build_source_asset_inventory(
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
            repo_root=ROOT,
        )
    except Exception:
        payload = None

    if _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, payload or {}):
        items = payload.get("items") or []
        if items:
            return payload

    fallback = _build_source_assets_from_persona_review()
    if _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, fallback or {}):
        return fallback
    return payload if _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, payload or {}) else None


def _build_long_form_routes_payload() -> dict[str, Any] | None:
    try:
        source_assets_payload = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
        payload = build_long_form_route_summary(
            repo_root=ROOT,
            source_assets=source_assets_payload,
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
        )
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_LONG_FORM_ROUTES, payload) else None


def _current_long_form_routes_payload() -> dict[str, Any] | None:
    runtime = _build_long_form_routes_payload()
    if runtime:
        return runtime
    persisted = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_LONG_FORM_ROUTES)
    return persisted if persisted and _snapshot_is_usable(SNAPSHOT_LONG_FORM_ROUTES, persisted) else None


def _build_content_reservoir_payload() -> dict[str, Any] | None:
    source_assets_payload = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
    if not source_assets_payload:
        source_assets_payload = _build_source_assets_payload()
    try:
        payload = build_content_reservoir_payload(source_assets=source_assets_payload)
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_CONTENT_RESERVOIR, payload or {}) else None


def _load_feedback_summary_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    try:
        return social_feedback_service.load_summary()
    except Exception:
        return _load_json(linkedin_root / "analytics" / "feed_feedback_summary.json")


def _metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_bool(metadata: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(metadata, dict):
        return False
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _metadata_array(metadata: dict[str, Any] | None, key: str) -> list[Any]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    return value if isinstance(value, list) else []


def _has_selectable_promotion_metadata(metadata: dict[str, Any] | None) -> bool:
    return any(
        _metadata_array(metadata, key)
        for key in ("talking_points", "frameworks", "anecdotes", "phrase_candidates", "stats")
    )


def _is_brain_pending_review(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    review_source = _metadata_text(metadata, "review_source")
    if review_source == "long_form_media.segment":
        sync_state = _metadata_text(metadata, "sync_state") or ""
        primary_route = _metadata_text(metadata, "primary_route")
        if sync_state.startswith("stale_"):
            return False
        if _metadata_bool(metadata, "weak_source_fragment"):
            return False
        if primary_route and primary_route != "belief_evidence":
            return False
    if normalized in {"draft", "pending", "in_review"}:
        return True
    return normalized == "reviewed" and _has_selectable_promotion_metadata(metadata) and not _metadata_bool(metadata, "pending_promotion")


def _is_workspace_approved(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    review_source = _metadata_text(metadata, "review_source")
    approval_state = _metadata_text(metadata, "approval_state")
    return normalized == "approved" and (
        review_source == "linkedin_workspace.feed_quote" or approval_state == "approved_from_workspace"
    )


def _persona_review_stage(status: str, metadata: dict[str, Any] | None) -> str:
    normalized = (status or "draft").strip().lower()
    if normalized == "committed":
        return "committed"
    if _metadata_bool(metadata, "pending_promotion"):
        return "pending_promotion"
    if _is_workspace_approved(normalized, metadata):
        return "workspace_saved"
    if _is_brain_pending_review(normalized, metadata):
        return "brain_pending_review"
    if normalized == "approved":
        return "approved_unpromoted"
    return normalized or "draft"


def _build_persona_review_summary_payload() -> dict[str, Any] | None:
    sync_result: dict[str, Any] | None = None
    source_assets_payload = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
    if source_assets_payload:
        try:
            sync_result = social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=ROOT,
                source_assets=source_assets_payload,
                transcripts_root=_transcripts_root(),
                ingestions_root=_ingestions_root(),
            )
        except Exception:
            sync_result = None

    try:
        deltas = persona_delta_service.list_deltas(limit=200)
    except Exception:
        deltas = []

    stage_counts = {
        "brain_pending_review": 0,
        "workspace_saved": 0,
        "approved_unpromoted": 0,
        "pending_promotion": 0,
        "committed": 0,
    }
    status_counts: dict[str, int] = {}
    review_source_counts: dict[str, int] = {}
    target_file_counts: dict[str, int] = {}
    belief_relation_counts: dict[str, int] = {}
    recent: list[dict[str, Any]] = []

    for delta in deltas:
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        status = (delta.status or "draft").strip().lower()
        stage = _persona_review_stage(status, metadata)
        if stage in stage_counts:
            stage_counts[stage] += 1
        status_counts[status] = status_counts.get(status, 0) + 1

        review_source = _metadata_text(metadata, "review_source") or "unknown"
        review_source_counts[review_source] = review_source_counts.get(review_source, 0) + 1

        target_file = _metadata_text(metadata, "target_file")
        if target_file:
            target_file_counts[target_file] = target_file_counts.get(target_file, 0) + 1

        belief_relation = _metadata_text(metadata, "belief_relation")
        if belief_relation:
            belief_relation_counts[belief_relation] = belief_relation_counts.get(belief_relation, 0) + 1

        if len(recent) < 12:
            recent.append(
                {
                    "id": delta.id,
                    "trait": delta.trait,
                    "persona_target": delta.persona_target,
                    "status": status,
                    "stage": stage,
                    "review_source": review_source,
                    "target_file": target_file,
                    "belief_relation": belief_relation,
                    "approval_state": _metadata_text(metadata, "approval_state"),
                    "created_at": delta.created_at.isoformat() if delta.created_at else None,
                    "committed_at": delta.committed_at.isoformat() if delta.committed_at else None,
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": WORKSPACE_KEY,
        "counts": {
            "total": len(deltas),
            **stage_counts,
        },
        "status_counts": status_counts,
        "review_source_counts": review_source_counts,
        "target_file_counts": target_file_counts,
        "belief_relation_counts": belief_relation_counts,
        "recent": recent,
        "long_form_sync": sync_result or {
            "assets_considered": 0,
            "created_count": 0,
            "skipped_existing": 0,
            "skipped_no_segments": 0,
            "resolved_stale": 0,
            "created": [],
        },
    }


def _build_source_assets_from_persona_review() -> dict[str, Any] | None:
    try:
        deltas = persona_delta_service.list_deltas(limit=400)
    except Exception:
        return None

    items_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for delta in deltas:
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        if _metadata_text(metadata, "review_source") != "long_form_media.segment":
            continue

        asset_id = _metadata_text(metadata, "source_asset_id")
        source_path = _metadata_text(metadata, "source_path")
        source_url = _metadata_text(metadata, "source_url")
        evidence_source = _metadata_text(metadata, "evidence_source") or asset_id or source_path or "Long-form source"
        key = (asset_id or source_path or evidence_source, source_path or "", source_url or "")
        existing = items_by_key.get(key)

        candidate = {
            "asset_id": asset_id or f"review-derived-{len(items_by_key) + 1}",
            "title": evidence_source,
            "source_class": _metadata_text(metadata, "source_class") or "long_form_media",
            "source_channel": _metadata_text(metadata, "source_channel") or "unknown",
            "source_type": _metadata_text(metadata, "source_type") or "review_segment",
            "source_url": source_url or "",
            "author": "",
            "captured_at": delta.created_at.isoformat() if delta.created_at else None,
            "source_path": source_path or "",
            "raw_path": "",
            "summary": _metadata_text(metadata, "segment_excerpt") or evidence_source,
            "topics": [],
            "tags": ["review_derived"],
            "response_modes": ["post_seed", "belief_evidence"],
            "routing_status": "review_backfill",
            "feed_ready": False,
            "segmentation_ready": False,
            "origin": "persona_review_backfill",
            "word_count": None,
        }
        if existing is None:
            items_by_key[key] = candidate
            continue

        existing_created = existing.get("captured_at") or ""
        candidate_created = candidate.get("captured_at") or ""
        if candidate_created > existing_created:
            items_by_key[key] = candidate

    items = sorted(
        items_by_key.values(),
        key=lambda item: ((item.get("captured_at") or ""), str(item.get("title") or "").lower()),
        reverse=True,
    )
    if not items:
        return None

    by_channel: dict[str, int] = {}
    for item in items:
        channel = _clean_markdown_value(str(item.get("source_channel") or "")) or "unknown"
        by_channel[channel] = by_channel.get(channel, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": WORKSPACE_KEY,
        "items": items,
        "counts": {
            "total": len(items),
            "long_form_media": len(items),
            "pending_segmentation": 0,
            "feed_ready": 0,
            "by_channel": by_channel,
        },
        "backfill_source": "persona_review_summary",
    }


def _runtime_snapshot_payload(snapshot_type: str) -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        payload = (
            _build_weekly_plan_payload()
            or _load_json(linkedin_root / "plans" / "weekly_plan.json")
            or _parse_weekly_plan_markdown(linkedin_root / "plans" / "weekly_plan.md")
        )
        long_form_routes = _current_long_form_routes_payload()
        return _augment_weekly_plan_payload(payload, long_form_routes)
    if snapshot_type == SNAPSHOT_REACTION_QUEUE:
        return (
            _build_reaction_queue_payload()
            or _load_json(linkedin_root / "plans" / "reaction_queue.json")
            or _parse_reaction_queue_markdown(linkedin_root / "plans" / "reaction_queue.md")
        )
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        built = _build_social_feed_payload()
        if built:
            return built
        json_payload = _load_json(linkedin_root / "plans" / "social_feed.json")
        if json_payload and _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, json_payload):
            return json_payload
        markdown_payload = _parse_social_feed_markdown(linkedin_root / "plans" / "social_feed.md")
        if markdown_payload and _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, markdown_payload):
            return markdown_payload
        return None
    if snapshot_type == SNAPSHOT_FEEDBACK_SUMMARY:
        return _load_feedback_summary_payload()
    if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
        return _build_source_assets_payload()
    if snapshot_type == SNAPSHOT_PERSONA_REVIEW_SUMMARY:
        return _build_persona_review_summary_payload()
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        return _build_long_form_routes_payload()
    if snapshot_type == SNAPSHOT_CONTENT_RESERVOIR:
        return _build_content_reservoir_payload()
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
        return (
            isinstance(first_item, dict)
            and bool(first_item.get("lens_variants"))
            and bool(first_item.get("source_class"))
            and bool(first_item.get("unit_kind"))
            and isinstance(first_item.get("response_modes"), list)
        )
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        return isinstance(payload.get("recommendations"), list) and isinstance(payload.get("positioning_model"), list)
    if snapshot_type == SNAPSHOT_REACTION_QUEUE:
        return isinstance(payload.get("comment_opportunities"), list) and isinstance(payload.get("post_seeds"), list)
    if snapshot_type == SNAPSHOT_FEEDBACK_SUMMARY:
        return "total_events" in payload
    if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
        items = payload.get("items")
        counts = payload.get("counts")
        return isinstance(items, list) and isinstance(counts, dict)
    if snapshot_type == SNAPSHOT_PERSONA_REVIEW_SUMMARY:
        return isinstance(payload.get("counts"), dict) and isinstance(payload.get("recent"), list)
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        return isinstance(payload.get("route_counts"), dict) and isinstance(payload.get("candidates"), list)
    if snapshot_type == SNAPSHOT_CONTENT_RESERVOIR:
        return isinstance(payload.get("counts"), dict) and isinstance(payload.get("items"), list)
    return True


def _social_feed_signature(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    items = payload.get("items") or []
    signature: list[tuple[str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        signature.append(
            (
                str(item.get("platform") or ""),
                str(item.get("source_url") or ""),
                str(item.get("title") or ""),
            )
        )
    return signature


def _source_assets_signature(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    items = payload.get("items") or []
    signature: list[tuple[str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        signature.append(
            (
                str(item.get("asset_id") or ""),
                str(item.get("source_path") or ""),
                str(item.get("title") or ""),
            )
        )
    return signature


def _weekly_plan_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    recommendations = payload.get("recommendations") or []
    brief_awareness_candidates = payload.get("brief_awareness_candidates") or []
    media_post_seeds = payload.get("media_post_seeds") or []
    belief_evidence_candidates = payload.get("belief_evidence_candidates") or []
    operational_route_candidates = payload.get("operational_route_candidates") or []
    source_counts = payload.get("source_counts") or {}
    if not isinstance(recommendations, list):
        recommendations = []
    if not isinstance(brief_awareness_candidates, list):
        brief_awareness_candidates = []
    if not isinstance(media_post_seeds, list):
        media_post_seeds = []
    if not isinstance(belief_evidence_candidates, list):
        belief_evidence_candidates = []
    if not isinstance(operational_route_candidates, list):
        operational_route_candidates = []
    if not isinstance(source_counts, dict):
        source_counts = {}

    def _candidate_signature(items: list[Any]) -> tuple[tuple[str, str, str], ...]:
        signature: list[tuple[str, str, str]] = []
        for item in items[:12]:
            if not isinstance(item, dict):
                continue
            signature.append(
                (
                    str(item.get("title") or ""),
                    str(item.get("source_path") or ""),
                    str(item.get("priority_lane") or ""),
                    str(item.get("handoff_lane") or ""),
                )
            )
        return tuple(signature)

    return (
        tuple(sorted((str(key), int(value)) for key, value in source_counts.items() if isinstance(value, (int, float)))),
        _candidate_signature(recommendations),
        _candidate_signature(brief_awareness_candidates),
        _candidate_signature(media_post_seeds),
        _candidate_signature(belief_evidence_candidates),
        _candidate_signature(operational_route_candidates),
    )


def _source_assets_count(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    counts = payload.get("counts")
    if isinstance(counts, dict):
        total = counts.get("total")
        if isinstance(total, (int, float)):
            return int(total)
    items = payload.get("items")
    return len(items) if isinstance(items, list) else 0


def _content_reservoir_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    counts = payload.get("counts") or {}
    items = payload.get("items") or []
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(items, list):
        items = []

    item_signature: list[tuple[str, str, str, str]] = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        item_signature.append(
            (
                str(item.get("reservoir_id") or ""),
                str(item.get("reservoir_lane") or ""),
                str(item.get("source_path") or ""),
                str(item.get("text") or ""),
            )
        )

    return (
        tuple(sorted((str(key), int(value)) for key, value in counts.items() if isinstance(value, (int, float)))),
        tuple(item_signature),
    )


def _persona_review_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    counts = payload.get("counts") or {}
    status_counts = payload.get("status_counts") or {}
    review_source_counts = payload.get("review_source_counts") or {}
    belief_relation_counts = payload.get("belief_relation_counts") or {}
    recent = payload.get("recent") or []
    long_form_sync = payload.get("long_form_sync") or {}
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(status_counts, dict):
        status_counts = {}
    if not isinstance(review_source_counts, dict):
        review_source_counts = {}
    if not isinstance(belief_relation_counts, dict):
        belief_relation_counts = {}
    if not isinstance(recent, list):
        recent = []
    if not isinstance(long_form_sync, dict):
        long_form_sync = {}

    recent_signature: list[tuple[str, str, str, str, str]] = []
    for item in recent[:12]:
        if not isinstance(item, dict):
            continue
        recent_signature.append(
            (
                str(item.get("id") or ""),
                str(item.get("status") or ""),
                str(item.get("stage") or ""),
                str(item.get("review_source") or ""),
                str(item.get("belief_relation") or ""),
            )
        )

    return (
        tuple(sorted((str(key), int(value)) for key, value in counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in status_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in review_source_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in belief_relation_counts.items() if isinstance(value, (int, float)))),
        tuple(recent_signature),
        (
            int(long_form_sync.get("assets_considered") or 0),
            int(long_form_sync.get("created_count") or 0),
            int(long_form_sync.get("skipped_existing") or 0),
            int(long_form_sync.get("skipped_no_segments") or 0),
            int(long_form_sync.get("resolved_stale") or 0),
        ),
    )


def _long_form_routes_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    route_counts = payload.get("route_counts") or {}
    primary_route_counts = payload.get("primary_route_counts") or {}
    by_channel = payload.get("by_channel") or {}
    candidates = payload.get("candidates") or []
    if not isinstance(route_counts, dict):
        route_counts = {}
    if not isinstance(primary_route_counts, dict):
        primary_route_counts = {}
    if not isinstance(by_channel, dict):
        by_channel = {}
    if not isinstance(candidates, list):
        candidates = []

    candidate_signature: list[tuple[str, str, str, str]] = []
    for item in candidates[:12]:
        if not isinstance(item, dict):
            continue
        candidate_signature.append(
            (
                str(item.get("candidate_id") or ""),
                str(item.get("primary_route") or ""),
                str(item.get("source_channel") or ""),
                str(item.get("target_file") or ""),
            )
        )

    return (
        int(payload.get("assets_considered") or 0),
        int(payload.get("segments_total") or 0),
        int(payload.get("skipped_no_segments") or 0),
        tuple(sorted((str(key), int(value)) for key, value in route_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in primary_route_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in by_channel.items() if isinstance(value, (int, float)))),
        tuple(candidate_signature),
    )


def _load_snapshot(snapshot_type: str) -> dict[str, Any] | None:
    persisted = get_snapshot_payload(WORKSPACE_KEY, snapshot_type)
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _weekly_plan_signature(persisted) != _weekly_plan_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _social_feed_signature(persisted) != _social_feed_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            runtime_count = _source_assets_count(runtime)
            persisted_count = _source_assets_count(persisted)
            if persisted and _snapshot_is_usable(snapshot_type, persisted) and runtime_count == 0 and persisted_count > 0:
                return persisted
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _source_assets_signature(persisted) != _source_assets_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_PERSONA_REVIEW_SUMMARY:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _persona_review_signature(persisted) != _persona_review_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _long_form_routes_signature(persisted) != _long_form_routes_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_CONTENT_RESERVOIR:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            runtime_count = _source_assets_count(runtime)
            persisted_count = _source_assets_count(persisted)
            if persisted and _snapshot_is_usable(snapshot_type, persisted) and runtime_count == 0 and persisted_count > 0:
                return persisted
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _content_reservoir_signature(persisted) != _content_reservoir_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if persisted and _snapshot_is_usable(snapshot_type, persisted):
        return persisted
    payload = _runtime_snapshot_payload(snapshot_type)
    if payload:
        source = "runtime_refresh" if persisted else "runtime_bootstrap"
        return _persist_snapshot(snapshot_type, payload, source)
    return None


def _load_persisted_snapshot(
    snapshot_type: str,
    *,
    persisted_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    persisted = (
        persisted_payloads.get(snapshot_type)
        if isinstance(persisted_payloads, dict)
        else get_snapshot_payload(WORKSPACE_KEY, snapshot_type)
    )
    return persisted if persisted and _snapshot_is_usable(snapshot_type, persisted) else None


class WorkspaceSnapshotService:
    def refresh_persisted_linkedin_os_state(self) -> dict[str, Any]:
        refreshed: dict[str, Any] = {}
        source_assets = _runtime_snapshot_payload(SNAPSHOT_SOURCE_ASSETS)
        if source_assets:
            refreshed[SNAPSHOT_SOURCE_ASSETS] = _persist_snapshot(SNAPSHOT_SOURCE_ASSETS, source_assets, "refresh")

        content_reservoir = _runtime_snapshot_payload(SNAPSHOT_CONTENT_RESERVOIR)
        if content_reservoir:
            refreshed[SNAPSHOT_CONTENT_RESERVOIR] = _persist_snapshot(
                SNAPSHOT_CONTENT_RESERVOIR,
                content_reservoir,
                "refresh",
            )

        long_form_routes = _runtime_snapshot_payload(SNAPSHOT_LONG_FORM_ROUTES)
        if long_form_routes:
            refreshed[SNAPSHOT_LONG_FORM_ROUTES] = _persist_snapshot(SNAPSHOT_LONG_FORM_ROUTES, long_form_routes, "refresh")

        weekly_plan = _runtime_snapshot_payload(SNAPSHOT_WEEKLY_PLAN)
        weekly_plan = _augment_weekly_plan_payload(weekly_plan, long_form_routes)
        if weekly_plan:
            refreshed[SNAPSHOT_WEEKLY_PLAN] = _persist_snapshot(SNAPSHOT_WEEKLY_PLAN, weekly_plan, "refresh")

        for snapshot_type in (
            SNAPSHOT_PERSONA_REVIEW_SUMMARY,
            SNAPSHOT_REACTION_QUEUE,
            SNAPSHOT_SOCIAL_FEED,
            SNAPSHOT_FEEDBACK_SUMMARY,
        ):
            payload = _runtime_snapshot_payload(snapshot_type)
            if payload:
                refreshed[snapshot_type] = _persist_snapshot(snapshot_type, payload, "refresh")
        return refreshed

    def get_linkedin_os_snapshot(
        self,
        *,
        persisted_only: bool = False,
        include_workspace_files: bool = True,
        include_doc_entries: bool = True,
    ) -> dict[str, Any]:
        persisted_payloads = list_snapshot_payloads(WORKSPACE_KEY) if persisted_only else None
        load_snapshot = (
            lambda snapshot_type: _load_persisted_snapshot(snapshot_type, persisted_payloads=persisted_payloads)
            if persisted_only
            else _load_snapshot(snapshot_type)
        )

        source_assets = load_snapshot(SNAPSHOT_SOURCE_ASSETS)
        content_reservoir = load_snapshot(SNAPSHOT_CONTENT_RESERVOIR)
        long_form_routes = load_snapshot(SNAPSHOT_LONG_FORM_ROUTES)
        weekly_plan = load_snapshot(SNAPSHOT_WEEKLY_PLAN)
        weekly_plan = _augment_weekly_plan_payload(weekly_plan, long_form_routes)
        persona_review_summary = load_snapshot(SNAPSHOT_PERSONA_REVIEW_SUMMARY)
        reaction_queue = load_snapshot(SNAPSHOT_REACTION_QUEUE)
        social_feed = load_snapshot(SNAPSHOT_SOCIAL_FEED)
        feedback_summary = load_snapshot(SNAPSHOT_FEEDBACK_SUMMARY)
        return {
            "workspace_files": _load_workspace_files() if include_workspace_files else [],
            "doc_entries": _load_doc_entries() if include_doc_entries else [],
            "weekly_plan": weekly_plan,
            "reaction_queue": reaction_queue,
            "social_feed": social_feed,
            "feedback_summary": feedback_summary,
            "source_assets": source_assets,
            "content_reservoir": content_reservoir,
            "persona_review_summary": persona_review_summary,
            "long_form_routes": long_form_routes,
            "refresh_status": social_feed_refresh_service.get_status(),
        }


workspace_snapshot_service = WorkspaceSnapshotService()
