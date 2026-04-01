#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_strategy_utils import (  # noqa: E402
    DEFAULT_POSITIONING_MODEL,
    DEFAULT_PRIORITY_LANES,
    clean_text,
    drafts_root,
    first_heading,
    infer_primary_lane,
    load_social_feed_items,
    now_iso,
    parse_frontmatter_markdown,
    plans_root,
    priority_lane_label,
    publish_posture_for_item,
    read_text,
    role_alignment_for_lane,
    risk_level_for_item,
    slugify,
    workspace_root,
    workspace_source_path,
    write_json,
    write_text,
)


@dataclass
class PlanCandidate:
    source_kind: str
    title: str
    category: str
    role_alignment: str
    risk_level: str
    publish_posture: str
    hook: str
    rationale: str
    source_path: str
    score: float
    priority_lane: str
    theme: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "title": self.title,
            "category": self.category,
            "role_alignment": self.role_alignment,
            "risk_level": self.risk_level,
            "publish_posture": self.publish_posture,
            "hook": self.hook,
            "rationale": self.rationale,
            "source_path": self.source_path,
            "score": round(self.score, 1),
            "priority_lane": self.priority_lane,
            "theme": self.theme,
        }


def _workspace_dir_from_arg(path: str | None) -> Path:
    return Path(path).resolve() if path else workspace_root()


def _heading_title_from_filename(path: Path) -> str:
    label = path.stem
    label = label.split("_", 1)[1] if "_" in label else label
    return clean_text(label.replace("-", " ").title())


def _draft_candidate_from_path(path: Path, workspace_dir: Path) -> PlanCandidate:
    frontmatter, body = parse_frontmatter_markdown(path)
    lane = clean_text(frontmatter.get("lane")) or "current-role"
    title = clean_text(frontmatter.get("title")) or first_heading(body, _heading_title_from_filename(path))
    hook = clean_text(frontmatter.get("hook"))
    if not hook:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                hook = stripped
                break
    priority_lane = clean_text(frontmatter.get("priority_lane")) or priority_lane_label(lane)
    return PlanCandidate(
        source_kind="draft",
        title=title,
        category=clean_text(frontmatter.get("category")) or "value",
        role_alignment=clean_text(frontmatter.get("role_alignment")) or role_alignment_for_lane(lane),
        risk_level=clean_text(frontmatter.get("risk_level")) or "low",
        publish_posture=clean_text(frontmatter.get("publish_posture")) or "owner_review_required",
        hook=hook,
        rationale=clean_text(frontmatter.get("why_now")) or "Draft already exists and is waiting for owner review.",
        source_path=workspace_source_path(path.relative_to(workspace_dir).as_posix()),
        score=float(frontmatter.get("score") or 18.0),
        priority_lane=priority_lane,
        theme=clean_text(frontmatter.get("theme")),
    )


def load_draft_candidates(workspace_dir: Path) -> tuple[list[PlanCandidate], set[str]]:
    candidates: list[PlanCandidate] = []
    source_refs: set[str] = set()
    for path in sorted(drafts_root(workspace_dir).glob("*.md")):
        if path.name == "README.md" or path.name.startswith("queue_"):
            continue
        candidate = _draft_candidate_from_path(path, workspace_dir)
        candidates.append(candidate)
        frontmatter, _ = parse_frontmatter_markdown(path)
        raw_source_path = clean_text(frontmatter.get("source_path"))
        if raw_source_path:
            source_refs.add(workspace_source_path(raw_source_path))
    return candidates, source_refs


def load_media_candidates(_ingestions_root: Path) -> list[PlanCandidate]:
    return []


def _research_signal_record(item: dict[str, Any]) -> dict[str, Any]:
    lane = infer_primary_lane(item)
    return {
        "source_kind": clean_text(item.get("source_lane")) or "market_signal",
        "title": clean_text(item.get("title")) or "Untitled signal",
        "theme": clean_text(item.get("title")) or "Untitled signal",
        "priority_lane": priority_lane_label(lane),
        "role_alignment": role_alignment_for_lane(lane),
        "summary": clean_text(item.get("summary")),
        "pain_points": [],
        "language_patterns": [clean_text(entry) for entry in (item.get("standout_lines") or []) if clean_text(entry)],
        "headline_candidates": [clean_text(entry) for entry in (item.get("standout_lines") or []) if clean_text(entry)],
        "source_path": workspace_source_path(item.get("source_path")),
    }


def _candidate_from_feed_item(item: dict[str, Any]) -> PlanCandidate:
    lane = infer_primary_lane(item)
    standout_lines = [clean_text(entry) for entry in (item.get("standout_lines") or []) if clean_text(entry)]
    hook = standout_lines[0] if standout_lines else clean_text(item.get("core_claim")) or clean_text(item.get("title"))
    return PlanCandidate(
        source_kind=clean_text(item.get("source_lane")) or "market_signal",
        title=clean_text(item.get("title")) or "Untitled signal",
        category="value",
        role_alignment=role_alignment_for_lane(lane),
        risk_level=risk_level_for_item(item),
        publish_posture=publish_posture_for_item(item),
        hook=hook,
        rationale=clean_text(item.get("why_it_matters")) or clean_text(item.get("summary")),
        source_path=workspace_source_path(item.get("source_path")),
        score=float(item.get("ranking", {}).get("total") or 0.0),
        priority_lane=priority_lane_label(lane),
        theme=clean_text(item.get("title")),
    )


def load_research_candidates(workspace_dir: Path) -> tuple[list[PlanCandidate], list[dict[str, Any]], list[str]]:
    items = load_social_feed_items(workspace_dir)
    research_candidates = [_candidate_from_feed_item(item) for item in items]
    research_signals = [_research_signal_record(item) for item in items]
    research_notes = [signal["source_path"] for signal in research_signals if signal.get("source_path")]
    return research_candidates, research_signals, research_notes


def _priority_lanes_from_candidates(recommendations: list[PlanCandidate], research_signals: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for candidate in recommendations:
        lane = clean_text(candidate.priority_lane)
        if lane and lane not in ordered:
            ordered.append(lane)
    for signal in research_signals:
        lane = clean_text(signal.get("priority_lane"))
        if lane and lane not in ordered:
            ordered.append(lane)
    return ordered[:3] or list(DEFAULT_PRIORITY_LANES)


def plan_payload(
    workspace_dir: Path,
    recommendations: list[PlanCandidate],
    hold_items: list[PlanCandidate],
    research_signals: list[dict[str, Any]],
    research_notes: list[str],
    counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workspace": "workspaces/linkedin-content-os",
        "positioning_model": list(DEFAULT_POSITIONING_MODEL),
        "priority_lanes": _priority_lanes_from_candidates(recommendations, research_signals),
        "recommendations": [item.to_payload() for item in recommendations],
        "hold_items": [item.to_payload() for item in hold_items],
        "market_signals": research_signals,
        "research_notes": research_notes,
        "source_counts": counts,
    }


def _markdown_block(title: str, fields: list[tuple[str, str]]) -> str:
    lines = [f"### {title}"]
    for key, value in fields:
        if clean_text(value):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _plan_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LinkedIn Weekly Plan", f"Generated: {payload.get('generated_at')}", ""]
    lines.append("## Positioning Model")
    for entry in payload.get("positioning_model") or []:
        lines.append(f"- {entry}")
    lines.append("")
    lines.append("## This Week's Priority Lanes")
    for entry in payload.get("priority_lanes") or []:
        lines.append(f"- {entry}")
    lines.append("")
    lines.append("## Recommended Posts")
    recommendations = payload.get("recommendations") or []
    if recommendations:
        for index, item in enumerate(recommendations, start=1):
            lines.append(
                _markdown_block(
                    f"{index}. {item.get('title')}",
                    [
                        ("Source", str(item.get("source_kind") or "")),
                        ("Category", str(item.get("category") or "")),
                        ("Role alignment", str(item.get("role_alignment") or "")),
                        ("Risk level", str(item.get("risk_level") or "")),
                        ("Publish posture", str(item.get("publish_posture") or "")),
                        ("Priority lane", str(item.get("priority_lane") or "")),
                        ("Hook", str(item.get("hook") or "")),
                        ("Why now", str(item.get("rationale") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    else:
        lines.append("_No recommendations yet._")
        lines.append("")
    lines.append("## Market Signals")
    signals = payload.get("market_signals") or []
    if signals:
        for item in signals:
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled signal"),
                    [
                        ("Source", str(item.get("source_kind") or "")),
                        ("Theme", str(item.get("theme") or "")),
                        ("Priority lane", str(item.get("priority_lane") or "")),
                        ("Role alignment", str(item.get("role_alignment") or "")),
                        ("What the market is saying", str(item.get("summary") or "")),
                        ("Language patterns", ", ".join(item.get("language_patterns") or [])),
                        ("Hook candidates", ", ".join(item.get("headline_candidates") or [])),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    else:
        lines.append("_No market signals yet._")
        lines.append("")
    lines.append("## Research Feed")
    for item in payload.get("research_notes") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines)


def build_weekly_plan(workspace_dir: Path) -> dict[str, Any]:
    draft_candidates, draft_source_refs = load_draft_candidates(workspace_dir)
    research_candidates, research_signals, research_notes = load_research_candidates(workspace_dir)
    filtered_research = [item for item in research_candidates if item.source_path not in draft_source_refs]
    all_candidates = sorted(draft_candidates + filtered_research, key=lambda item: (-item.score, item.title.lower()))
    recommendations = [item for item in all_candidates if item.publish_posture != "hold_private"][:5]
    hold_items = [item for item in all_candidates if item.publish_posture == "hold_private" or item.risk_level == "high"][:10]
    payload = plan_payload(
        workspace_dir=workspace_dir,
        recommendations=recommendations,
        hold_items=hold_items,
        research_signals=research_signals,
        research_notes=research_notes,
        counts={
            "drafts": len(draft_candidates),
            "media": 0,
            "research": len(filtered_research),
        },
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the FEEZIE weekly plan artifacts.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_dir = _workspace_dir_from_arg(args.workspace)
    payload = build_weekly_plan(workspace_dir)
    write_json(plans_root(workspace_dir) / "weekly_plan.json", payload)
    write_text(plans_root(workspace_dir) / "weekly_plan.md", _plan_markdown(payload))


if __name__ == "__main__":
    main()
