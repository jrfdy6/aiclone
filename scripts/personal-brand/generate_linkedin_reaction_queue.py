#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_strategy_utils import (  # noqa: E402
    clean_text,
    drafts_root,
    infer_primary_lane,
    load_rejected_source_index,
    load_social_feed_items,
    now_iso,
    parse_frontmatter_markdown,
    plans_root,
    priority_lane_label,
    publish_posture_for_item,
    risk_level_for_item,
    role_alignment_for_lane,
    source_identity_keys,
    workspace_root,
    workspace_source_path,
    write_json,
    write_text,
)
from linkedin_idea_qualification import (  # noqa: E402
    latent_idea_indexes,
    load_or_build_idea_qualification_payload,
    load_or_build_latent_idea_payload,
    qualification_indexes,
)


def _workspace_dir_from_arg(path: str | None) -> Path:
    return Path(path).resolve() if path else workspace_root()


def load_market_signal_items(workspace_dir: Path) -> list[dict[str, Any]]:
    items = load_social_feed_items(workspace_dir)
    ranked = sorted(items, key=lambda item: float((item.get("ranking") or {}).get("total") or 0.0), reverse=True)
    return ranked[:8]


def _qualification_lookup(workspace_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    payload = load_or_build_idea_qualification_payload(workspace_dir)
    lookup, _ = qualification_indexes(payload)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return lookup, {
        "qualified": int(summary.get("pass") or 0),
        "latent": int(summary.get("latent") or 0),
        "discarded": int(summary.get("discard") or 0),
    }


def _latent_lookup(workspace_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_or_build_latent_idea_payload(workspace_dir)
    _, lookup = latent_idea_indexes(payload)
    return lookup


def _base_payload(item: dict[str, Any]) -> dict[str, Any]:
    lane = infer_primary_lane(item)
    standpoint = clean_text(((item.get("belief_assessment") or {}).get("stance"))) or "translate"
    comment_draft = clean_text(item.get("comment_draft"))
    repost_draft = clean_text(item.get("repost_draft"))
    hook = clean_text(item.get("core_claim")) or clean_text(item.get("title"))
    summary = clean_text(item.get("summary"))
    why_it_matters = clean_text(item.get("why_it_matters"))
    return {
        "title": clean_text(item.get("title")) or "Untitled signal",
        "author": clean_text(item.get("author")),
        "source_platform": clean_text(item.get("platform")) or clean_text(item.get("source_platform")),
        "source_type": clean_text(item.get("source_type")) or "post",
        "source_url": clean_text(item.get("source_url")),
        "source_path": workspace_source_path(item.get("source_path")),
        "role_alignment": role_alignment_for_lane(lane),
        "risk_level": risk_level_for_item(item),
        "publish_posture": publish_posture_for_item(item),
        "priority_lane": priority_lane_label(lane),
        "recommended_move": "comment_then_post" if comment_draft and repost_draft else "save_for_post",
        "hook": hook,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "comment_angle": f"Use a {lane} lens and stay grounded in lived work. stance={standpoint}.",
        "suggested_comment": comment_draft,
        "post_angle": repost_draft or f"{hook} {why_it_matters}".strip(),
        "score": round(float((item.get('ranking') or {}).get('total') or 0.0), 1),
    }


def _existing_active_draft_source_paths(workspace_dir: Path) -> set[str]:
    source_paths: set[str] = set()
    for path in sorted(drafts_root(workspace_dir).glob("*.md")):
        if path.name == "README.md" or path.name.startswith("queue_") or path.name.startswith("feezie_owner_review_packet_"):
            continue
        frontmatter, _ = parse_frontmatter_markdown(path)
        source_path = workspace_source_path(clean_text(frontmatter.get("source_path")))
        if source_path:
            source_paths.add(source_path)
    return source_paths


def queue_payload(workspace_dir: Path, items: list[dict[str, Any]]) -> dict[str, Any]:
    qualification_lookup, qualification_summary = _qualification_lookup(workspace_dir)
    latent_lookup = _latent_lookup(workspace_dir)
    active_draft_source_paths = _existing_active_draft_source_paths(workspace_dir)
    rejected_source_keys, rejected_by_key = load_rejected_source_index(workspace_dir)
    comment_opportunities: list[dict[str, Any]] = []
    post_seeds: list[dict[str, Any]] = []
    consumed_post_seeds: list[dict[str, Any]] = []
    rejected_sources: list[dict[str, Any]] = []
    latent_post_seeds: list[dict[str, Any]] = []
    background_only: list[dict[str, Any]] = []
    discarded_post_seed_count = 0

    for item in items:
        payload = _base_payload(item)
        item_keys = source_identity_keys(
            item_id=clean_text(item.get("id")),
            title=payload.get("title"),
            source_url=payload.get("source_url"),
            source_path=payload.get("source_path"),
        )
        rejected_record = next((rejected_by_key[key] for key in item_keys if key in rejected_source_keys), None)
        if rejected_record:
            payload["active_seed"] = False
            payload["lifecycle_stage"] = "rejected"
            payload["rejected_reason"] = clean_text(rejected_record.get("notes")) or "Owner marked this source Not for FEEZIE."
            payload["rejected_at"] = clean_text(rejected_record.get("recorded_at"))
            rejected_sources.append(payload)
            continue
        report = qualification_lookup.get(clean_text(item.get("id"))) or {}
        route = clean_text(report.get("route")) or "discard"
        latent_reason = clean_text(report.get("latent_reason"))
        suggested_fix = clean_text(report.get("suggested_fix"))
        payload["qualification_route"] = route
        payload["qualification_failures"] = [clean_text(entry) for entry in (report.get("failure_dimensions") or []) if clean_text(entry)]
        if latent_reason:
            payload["latent_reason"] = latent_reason
        if suggested_fix:
            payload["suggested_fix"] = suggested_fix
        latent_item = latent_lookup.get(payload["source_path"]) if payload.get("source_path") else None
        transform_plan = (latent_item or {}).get("transform_plan") if isinstance((latent_item or {}).get("transform_plan"), dict) else {}
        if transform_plan:
            payload["transform_type"] = clean_text(transform_plan.get("transform_type"))
            payload["autotransform_ready"] = bool(transform_plan.get("autotransform_ready"))
            payload["proposed_angle"] = clean_text(transform_plan.get("proposed_angle"))
            payload["owner_question"] = clean_text(transform_plan.get("owner_question"))
            payload["proof_prompt"] = clean_text(transform_plan.get("proof_prompt"))
            payload["promotion_rule"] = clean_text(transform_plan.get("promotion_rule"))
            payload["revision_goals"] = [clean_text(entry) for entry in (transform_plan.get("revision_goals") or []) if clean_text(entry)]
        if payload["suggested_comment"]:
            comment_opportunities.append(payload)
        if payload["post_angle"] and route == "pass":
            if payload.get("source_path") in active_draft_source_paths:
                payload["active_seed"] = False
                payload["lifecycle_stage"] = "owner_review"
                payload["consumed_reason"] = "A draft already exists for this source, so it is no longer an active post seed."
                consumed_post_seeds.append(payload)
                continue
            post_seeds.append(payload)
        elif payload["post_angle"] and route == "latent" and clean_text((latent_item or {}).get("transform_status")) != "drafted":
            latent_post_seeds.append(payload)
        elif payload["post_angle"]:
            discarded_post_seed_count += 1
        if not payload["suggested_comment"] and route != "pass" and route != "latent":
            background_only.append(payload)

    return {
        "generated_at": now_iso(),
        "workspace": "workspaces/linkedin-content-os",
        "comment_opportunities": comment_opportunities[:6],
        "post_seeds": post_seeds[:8],
        "consumed_post_seeds": consumed_post_seeds[:8],
        "rejected_sources": rejected_sources[:8],
        "latent_post_seeds": latent_post_seeds[:8],
        "background_only": background_only[:8],
        "counts": {
            "comment_opportunities": min(len(comment_opportunities), 6),
            "post_seeds": min(len(post_seeds), 8),
            "consumed_post_seed_count": min(len(consumed_post_seeds), 8),
            "rejected_source_count": min(len(rejected_sources), 8),
            "latent_post_seeds": min(len(latent_post_seeds), 8),
            "background_only": min(len(background_only), 8),
            "discarded_post_seed_count": discarded_post_seed_count,
        },
        "qualification_summary": qualification_summary,
    }


def _markdown_block(title: str, fields: list[tuple[str, str]]) -> str:
    lines = [f"### {title}"]
    for key, value in fields:
        if clean_text(value):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _queue_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LinkedIn Reaction Queue", f"Generated: {payload.get('generated_at')}", ""]
    qualification_summary = payload.get("qualification_summary") or {}
    if qualification_summary:
        lines.extend(
            [
                "## Qualification Summary",
                f"- Qualified ideas: {qualification_summary.get('qualified', 0)}",
                f"- Latent ideas: {qualification_summary.get('latent', 0)}",
                f"- Discarded ideas: {qualification_summary.get('discarded', 0)}",
                "",
            ]
        )
    lines.append("## Immediate Comment Opportunities")
    comment_items = payload.get("comment_opportunities") or []
    if comment_items:
        for item in comment_items:
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled comment opportunity"),
                    [
                        ("Source", f"`{item.get('source_platform')}` / {item.get('author') or 'unknown'}"),
                        ("Lane", str(item.get("priority_lane") or "")),
                        ("Move", str(item.get("recommended_move") or "")),
                        ("Hook to react to", str(item.get("hook") or "")),
                        ("Why this matters", str(item.get("why_it_matters") or "")),
                        ("Comment angle", str(item.get("comment_angle") or "")),
                        ("Suggested comment", str(item.get("suggested_comment") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    else:
        lines.append("_No immediate comment opportunities yet._")
        lines.append("")
    lines.append("## Standalone Post Seeds")
    post_items = payload.get("post_seeds") or []
    if post_items:
        for item in post_items:
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled post seed"),
                    [
                        ("Role alignment", str(item.get("role_alignment") or "")),
                        ("Risk", str(item.get("risk_level") or "")),
                        ("Post angle", str(item.get("post_angle") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    else:
        lines.append("_No standalone post seeds yet._")
        lines.append("")
    consumed_items = payload.get("consumed_post_seeds") or []
    if consumed_items:
        lines.append("## Consumed Post Seeds")
        for item in consumed_items:
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled consumed post seed"),
                    [
                        ("Lifecycle stage", str(item.get("lifecycle_stage") or "owner_review")),
                        ("Reason", str(item.get("consumed_reason") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    rejected_items = payload.get("rejected_sources") or []
    if rejected_items:
        lines.append("## Rejected Sources")
        for item in rejected_items:
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled rejected source"),
                    [
                        ("Lifecycle stage", str(item.get("lifecycle_stage") or "rejected")),
                        ("Reason", str(item.get("rejected_reason") or "")),
                        ("Rejected at", str(item.get("rejected_at") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            lines.append("")
    lines.append("## Latent Transform Queue")
    latent_items = payload.get("latent_post_seeds") or []
    if latent_items:
        for item in latent_items:
            revision_goals = item.get("revision_goals") or []
            lines.append(
                _markdown_block(
                    str(item.get("title") or "Untitled latent seed"),
                    [
                        ("Role alignment", str(item.get("role_alignment") or "")),
                        ("Latent reason", str(item.get("latent_reason") or "")),
                        ("Transform type", str(item.get("transform_type") or "")),
                        ("Worker-ready", "yes" if item.get("autotransform_ready") else "no"),
                        ("Suggested fix", str(item.get("suggested_fix") or "")),
                        ("Post angle", str(item.get("post_angle") or "")),
                        ("Proposed angle", str(item.get("proposed_angle") or "")),
                        ("Owner question", str(item.get("owner_question") or "")),
                        ("Proof prompt", str(item.get("proof_prompt") or "")),
                        ("Promotion rule", str(item.get("promotion_rule") or "")),
                        ("Source file", str(item.get("source_path") or "")),
                    ],
                )
            )
            if revision_goals:
                lines.append("- Revision goals:")
                for goal in revision_goals:
                    lines.append(f"  - {goal}")
            lines.append("")
    else:
        lines.append("_No latent transform candidates right now._")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the FEEZIE reaction queue artifacts.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_dir = _workspace_dir_from_arg(args.workspace)
    items = load_market_signal_items(workspace_dir)
    payload = queue_payload(workspace_dir, items)
    write_json(plans_root(workspace_dir) / "reaction_queue.json", payload)
    write_text(plans_root(workspace_dir) / "reaction_queue.md", _queue_markdown(payload))


if __name__ == "__main__":
    main()
