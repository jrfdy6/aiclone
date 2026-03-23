#!/usr/bin/env python3
"""Compile the LinkedIn workspace social feed artifacts for the LinkedIn workspace."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = ROOT / "workspaces" / "linkedin-content-os"
RESEARCH_ROOT = WORKSPACE_ROOT / "research" / "market_signals"
PLANS_ROOT = WORKSPACE_ROOT / "plans"
WATCHLIST_PATH = WORKSPACE_ROOT / "research" / "watchlists.yaml"
LENS_IDS = [
    "admissions",
    "entrepreneurship",
    "personal-story",
    "program-leadership",
    "therapist-referral",
    "enrollment-management",
    "ai-entrepreneurship",
]

LENS_CONFIG = {
    "admissions": {
        "label": "Admissions",
        "opening": "This is exactly where admissions teams carry more strategic signal than they usually get credit for.",
        "addition": "The questions families repeat usually show you where the message or experience still needs work.",
        "implication": "When teams treat those conversations as input, both content and enrollment get sharper.",
        "short_comment": "Exactly. Admissions teams usually hear the truth first.",
    },
    "entrepreneurship": {
        "label": "Entrepreneurship",
        "opening": "This is a good reminder that the edge is usually in the system, not just the idea.",
        "addition": "The people closest to the work usually see the friction and demand patterns first.",
        "implication": "Builders who turn that signal into process move faster than the ones chasing novelty.",
        "short_comment": "Exactly. The edge is usually in the system.",
    },
    "personal-story": {
        "label": "Personal Story",
        "opening": "This lands for me because I have seen the same pattern up close.",
        "addition": "A lot of the lesson only becomes obvious once you are the one carrying the follow-through.",
        "implication": "That is usually where the work stops being theoretical and starts becoming personal.",
        "short_comment": "This one feels very real to me.",
    },
    "program-leadership": {
        "label": "Program Leadership",
        "opening": "This is where leadership shows up in the operating system, not just the message.",
        "addition": "The teams closest to the work usually hear the signal first, but it only matters if leaders turn it into shared process.",
        "implication": "That is how insight becomes execution instead of staying anecdotal.",
        "short_comment": "Exactly. Insight only matters if it becomes process.",
    },
    "therapist-referral": {
        "label": "Therapy / Referral",
        "opening": "This resonates because trust is usually built in the quality of the handoff, not the headline.",
        "addition": "People can feel the difference between being managed and being genuinely understood.",
        "implication": "The stronger the trust signal, the easier it is for referrals and relationships to compound.",
        "short_comment": "Yes. Trust is built in the handoff.",
    },
    "enrollment-management": {
        "label": "Enrollment Mgmt",
        "opening": "This is a useful enrollment reminder because small clarity gaps show up downstream as larger conversion problems.",
        "addition": "When teams hear the same confusion repeatedly, it is usually a signal to tighten the journey rather than just work harder inside it.",
        "implication": "Better listening usually improves both follow-up quality and fit.",
        "short_comment": "Exactly. Repeated confusion is usually a journey problem.",
    },
    "ai-entrepreneurship": {
        "label": "AI + Ops",
        "opening": "Completely agree. Most of the leverage question lives in the system around the work, not the tool by itself.",
        "addition": "When context, ownership, and workflow are messy, better models rarely fix the underlying execution problem.",
        "implication": "That is why AI value usually shows up after the operating context gets cleaner.",
        "short_comment": "Exactly. Context is usually the real bottleneck.",
    },
}


def clean_sentence(value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split()).strip()
    if not text:
        return ""
    return text[:-1] if text.endswith(".") else text


def pick_core_line(signal: dict[str, Any]) -> str:
    candidates = signal.get("headline_candidates") or []
    if candidates:
        return clean_sentence(candidates[0])
    return clean_sentence(signal.get("summary")) or clean_sentence(signal.get("title")) or "this post"


def pick_supporting_line(signal: dict[str, Any], core_line: str) -> str:
    candidates = [clean_sentence(value) for value in (signal.get("headline_candidates") or [])]
    for candidate in candidates:
        if candidate and candidate != core_line:
            return candidate
    summary = clean_sentence(signal.get("summary"))
    if summary and summary != core_line:
        return summary
    return ""


def join_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def ensure_period(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text if text.endswith((".", "!", "?")) else f"{text}."


def build_comment_copy(config: dict[str, str], core_line: str, supporting_line: str, why_it_matters: str) -> str:
    second_sentence = supporting_line or core_line
    if second_sentence:
        second_sentence = f"{second_sentence}. {config['addition']}"
    else:
        second_sentence = config["addition"]
    parts = [
        config["opening"],
        second_sentence,
        why_it_matters or config["implication"],
    ]
    return join_parts([ensure_period(part) for part in parts])


def build_short_comment_copy(config: dict[str, str], core_line: str) -> str:
    quick = clean_sentence(config.get("short_comment"))
    if quick:
        return ensure_period(quick)
    if core_line:
        return ensure_period(core_line)
    return "Agreed."


def build_repost_copy(
    config: dict[str, str],
    title: str,
    core_line: str,
    supporting_line: str,
    priority_lane: str,
) -> str:
    lead = core_line or title
    angle_tail = f"In my world, this connects directly to {priority_lane.lower()}." if priority_lane else ""
    parts = [
        lead,
        config["opening"],
        supporting_line if supporting_line and supporting_line != lead else "",
        config["addition"],
        angle_tail,
        config["implication"],
    ]
    return join_parts([ensure_period(part) for part in parts])


def build_comment_variants(signal: dict[str, Any], title: str) -> dict[str, dict[str, str]]:
    why_it_matters = clean_sentence(signal.get("why_it_matters"))
    core_line = pick_core_line(signal)
    supporting_line = pick_supporting_line(signal, core_line)
    priority_lane = clean_sentence(signal.get("priority_lane"))

    variants: dict[str, dict[str, str]] = {}
    for lens_id in LENS_IDS:
        config = LENS_CONFIG[lens_id]
        comment = build_comment_copy(config, core_line, supporting_line, why_it_matters)
        short_comment = build_short_comment_copy(config, core_line)
        repost = build_repost_copy(config, title, core_line, supporting_line, priority_lane)
        variants[lens_id] = {
            "label": config["label"],
            "comment": " ".join(comment.split()),
            "short_comment": " ".join(short_comment.split()),
            "repost": " ".join(repost.split()),
            "why_this_angle": f"Use a {config['label'].lower()} framing for this signal.",
        }
    return variants


def load_watchlist() -> dict[str, Any]:
    if not WATCHLIST_PATH.exists():
        return {}
    with WATCHLIST_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def parse_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def read_signals() -> list[dict[str, Any]]:
    signals = []
    for path in sorted(RESEARCH_ROOT.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        meta["source_path"] = path.relative_to(WORKSPACE_ROOT).as_posix()
        meta["id"] = path.stem
        signals.append(meta)
    return signals


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_signal(signal: dict[str, Any], watchlist: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    created_dt = parse_datetime(signal.get("created_at")) or now
    age_hours = max(0, round((now - created_dt).total_seconds() / 3600))
    topics = signal.get("topics") or []
    lenses: list[str] = []
    priority_people = watchlist.get("priority_people", [])
    priority_weight = 0.5

    author = signal.get("author", "Unknown")
    for person in priority_people:
        if person.get("name") and person["name"].lower() in str(author).lower():
            priority_weight = max(priority_weight, person.get("priority_weight", 0.6))
            lenses.extend(person.get("lenses", []))

    if priority_lane := signal.get("priority_lane"):
        lenses.append(priority_lane.lower().replace(" ", "-"))

    topic_match = len(set(topics) & set(watchlist.get("topics", [])))
    source_platform = signal.get("source_platform", "linkedin")
    source_quality = 40 if source_platform == "linkedin" else 5
    if signal.get("headline_candidates"):
        source_quality += 10
    if signal.get("source_type") == "post":
        source_quality += 5

    ranking = {
        "priority_network": round(priority_weight * 100, 1),
        "topic_match": topic_match * 10,
        "recency": max(0, 100 - age_hours),
        "engagement": signal.get("engagement", {}).get("likes", 0) * 0.1,
        "persona_fit": 10 if signal.get("role_alignment") else 0,
        "source_quality": source_quality,
    }
    ranking["total"] = sum(ranking.values())

    title = signal.get("title") or (signal.get("headline_candidates") or ["Untitled"])[0]
    lens_variants = build_comment_variants(signal, title)

    return {
        "id": f"{signal.get('source_platform', 'unknown')}__{signal.get('id')}",
        "platform": signal.get("source_platform", "linkedin"),
        "source_lane": signal.get("source_kind", "market_signal"),
        "capture_method": signal.get("capture_method", "manual"),
        "title": title,
        "author": author,
        "source_url": signal.get("source_url"),
        "source_path": signal.get("source_path"),
        "published_at": signal.get("created_at"),
        "captured_at": signal.get("captured_at") or signal.get("created_at"),
        "summary": signal.get("summary"),
        "standout_lines": (signal.get("headline_candidates") or [])[:2],
        "engagement": signal.get("engagement", {"likes": 0, "comments": 0, "shares": 0}),
        "ranking": ranking,
        "lenses": list(dict.fromkeys(lenses)),
        "comment_draft": signal.get("comment_angle") or "Draft a thoughtful, concise comment with operator context.",
        "repost_draft": signal.get("post_angle") or signal.get("summary") or "",
        "lens_variants": lens_variants,
        "why_it_matters": signal.get("why_it_matters"),
        "notes": signal.get("language_patterns", []),
    }


def build_feed() -> dict[str, Any]:
    watchlist = load_watchlist()
    signals = read_signals()
    items = [normalize_signal(signal, watchlist) for signal in signals]
    items.sort(key=lambda item: item["ranking"]["total"], reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "strategy_mode": "production",
        "items": items,
    }


def write_artifacts(feed: dict[str, Any]) -> None:
    json_path = PLANS_ROOT / "social_feed.json"
    md_path = PLANS_ROOT / "social_feed.md"
    PLANS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(feed, indent=2), encoding="utf-8")

    lines = ["# LinkedIn Social Feed", f"Updated {feed['generated_at']}", ""]
    for item in feed["items"]:
        lines.append(f"- {item['platform']} · {item['title']} ({item['author']})")
        if item.get("source_url"):
            lines.append(f"  - {item['source_url']}")
        lines.append(f"  - score: {item['ranking']['total']:.1f}")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    feed = build_feed()
    write_artifacts(feed)


if __name__ == "__main__":
    main()
