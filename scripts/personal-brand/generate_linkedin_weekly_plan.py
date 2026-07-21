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
    load_rejected_source_index,
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
    source_identity_keys,
    workspace_root,
    workspace_source_path,
    write_json,
    write_text,
)
from linkedin_idea_qualification import load_or_build_idea_qualification_payload, qualification_indexes  # noqa: E402


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
    qualification_route: str = ""
    qualification_reason: str = ""

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
            "qualification_route": self.qualification_route,
            "qualification_reason": self.qualification_reason,
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


def _stale_reaction_draft_candidate(path: Path, workspace_dir: Path, report: dict[str, Any]) -> PlanCandidate:
    candidate = _draft_candidate_from_path(path, workspace_dir)
    failures = ", ".join(clean_text(entry) for entry in (report.get("failure_dimensions") or []) if clean_text(entry))
    suggested_fix = clean_text(report.get("suggested_fix"))
    route = clean_text(report.get("route")) or "discard"
    candidate.publish_posture = "stale_reaction_draft"
    candidate.qualification_route = route
    candidate.qualification_reason = " ".join(
        part
        for part in [
            "Existing reaction-seed draft no longer passes idea qualification.",
            f"failures={failures}." if failures else "",
            suggested_fix,
        ]
        if part
    ).strip()
    candidate.rationale = candidate.qualification_reason
    return candidate


def load_draft_candidates(workspace_dir: Path) -> tuple[list[PlanCandidate], list[PlanCandidate], set[str]]:
    qualification_payload = load_or_build_idea_qualification_payload(workspace_dir)
    _, qualification_by_source_path = qualification_indexes(qualification_payload)
    candidates: list[PlanCandidate] = []
    stale_candidates: list[PlanCandidate] = []
    source_refs: set[str] = set()
    for path in sorted(drafts_root(workspace_dir).glob("*.md")):
        if path.name == "README.md" or path.name.startswith("queue_") or path.name.startswith("feezie_owner_review_packet_"):
            continue
        frontmatter, _ = parse_frontmatter_markdown(path)
        source_kind = clean_text(frontmatter.get("source_kind"))
        raw_source_path = workspace_source_path(clean_text(frontmatter.get("source_path")))
        if source_kind == "reaction_seed" and raw_source_path:
            report = qualification_by_source_path.get(raw_source_path)
            route = clean_text((report or {}).get("route"))
            if route and route != "pass":
                stale_candidates.append(_stale_reaction_draft_candidate(path, workspace_dir, report or {}))
                source_refs.add(raw_source_path)
                continue
        candidate = _draft_candidate_from_path(path, workspace_dir)
        candidates.append(candidate)
        if raw_source_path:
            source_refs.add(workspace_source_path(raw_source_path))
    return candidates, stale_candidates, source_refs


def load_media_candidates(_ingestions_root: Path) -> list[PlanCandidate]:
    return []


def _qualification_lookup(workspace_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    payload = load_or_build_idea_qualification_payload(workspace_dir)
    lookup, _ = qualification_indexes(payload)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return lookup, {
        "qualified": int(summary.get("pass") or 0),
        "latent": int(summary.get("latent") or 0),
        "discarded": int(summary.get("discard") or 0),
    }


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


def _research_candidate_from_report(item: dict[str, Any], report: dict[str, Any]) -> PlanCandidate:
    candidate = _candidate_from_feed_item(item)
    route = clean_text(report.get("route"))
    failures = ", ".join(clean_text(entry) for entry in (report.get("failure_dimensions") or []) if clean_text(entry))
    if route == "pass":
        candidate.publish_posture = "qualified_post_seed"
        candidate.qualification_route = "pass"
        candidate.qualification_reason = "Passed idea qualification and is eligible for recommendation."
        return candidate
    candidate.publish_posture = "latent_hold"
    candidate.qualification_route = route or "latent"
    latent_reason = clean_text(report.get("latent_reason"))
    suggested_fix = clean_text(report.get("suggested_fix"))
    candidate.qualification_reason = " ".join(
        part
        for part in [
            f"latent reason={latent_reason}." if latent_reason else "",
            f"failures={failures}." if failures else "",
            suggested_fix,
        ]
        if part
    ).strip()
    candidate.rationale = candidate.qualification_reason or candidate.rationale
    return candidate


def load_research_candidates(workspace_dir: Path) -> tuple[list[PlanCandidate], list[PlanCandidate], list[dict[str, Any]], list[str], dict[str, int]]:
    rejected_source_keys, _ = load_rejected_source_index(workspace_dir)
    items = [
        item
        for item in load_social_feed_items(workspace_dir)
        if not (
            source_identity_keys(
                item_id=clean_text(item.get("id")),
                title=clean_text(item.get("title")),
                source_url=clean_text(item.get("source_url")),
                source_path=clean_text(item.get("source_path")),
            )
            & rejected_source_keys
        )
    ]
    qualification_lookup, qualification_summary = _qualification_lookup(workspace_dir)
    research_candidates: list[PlanCandidate] = []
    latent_candidates: list[PlanCandidate] = []
    for item in items:
        report = qualification_lookup.get(clean_text(item.get("id"))) or {}
        route = clean_text(report.get("route"))
        if route == "pass":
            research_candidates.append(_research_candidate_from_report(item, report))
        elif route == "latent":
            latent_candidates.append(_research_candidate_from_report(item, report))
    research_signals = [_research_signal_record(item) for item in items]
    research_notes = [signal["source_path"] for signal in research_signals if signal.get("source_path")]
    return research_candidates, latent_candidates, research_signals, research_notes, qualification_summary


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
    qualification_summary: dict[str, int],
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
        "qualification_summary": qualification_summary,
    }


def _markdown_block(title: str, fields: list[tuple[str, str]]) -> str:
    lines = [f"### {title}"]
    for key, value in fields:
        if clean_text(value):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _plan_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LinkedIn Weekly Plan", f"Generated: {payload.get('generated_at')}", ""]
    qualification_summary = payload.get("qualification_summary") or {}
    if qualification_summary:
        lines.extend(
            [
                "## Idea Qualification Summary",
                f"- Qualified ideas: {qualification_summary.get('qualified', 0)}",
                f"- Latent ideas: {qualification_summary.get('latent', 0)}",
                f"- Discarded ideas: {qualification_summary.get('discarded', 0)}",
                "",
            ]
        )
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
    lines.append("## Hold / Latent Ideas")
    hold_items = payload.get("hold_items") or []
    latent_count = int(qualification_summary.get("latent", 0) or 0)
    if hold_items:
        for item in hold_items:
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled hold item"),
                    [
                        ("Source", str(item.get("source_kind") or "")),
                        ("Publish posture", str(item.get("publish_posture") or "")),
                        ("Qualification route", str(item.get("qualification_route") or "")),
                        ("Reason", str(item.get("qualification_reason") or item.get("rationale") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    elif latent_count:
        lines.append(
            f"_No active holds. {latent_count} latent idea{'s' if latent_count != 1 else ''} "
            "are tracked separately in `plans/latent_ideas.md`._"
        )
        lines.append("")
    else:
        lines.append("_No hold or latent ideas right now._")
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
    draft_candidates, stale_draft_candidates, draft_source_refs = load_draft_candidates(workspace_dir)
    research_candidates, latent_candidates, research_signals, research_notes, qualification_summary = load_research_candidates(workspace_dir)
    filtered_research = [item for item in research_candidates if item.source_path not in draft_source_refs]
    all_candidates = sorted(draft_candidates + filtered_research, key=lambda item: (-item.score, item.title.lower()))
    recommendations = [item for item in all_candidates if item.publish_posture != "hold_private"][:5]
    draft_hold_items = [item for item in draft_candidates if item.publish_posture == "hold_private" or item.risk_level == "high"]
    stale_draft_hold_items = sorted(stale_draft_candidates, key=lambda item: (-item.score, item.title.lower()))
    hold_items = (draft_hold_items + stale_draft_hold_items)[:10]
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
        qualification_summary=qualification_summary,
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
