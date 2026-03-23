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
        "focus": "frontline conversations, student questions, family trust, message clarity",
    },
    "entrepreneurship": {
        "label": "Entrepreneurship",
        "focus": "leverage, differentiation, execution, distribution, systems",
    },
    "personal-story": {
        "label": "Personal Story",
        "focus": "reflection, lived experience, human stakes, follow-through",
    },
    "program-leadership": {
        "label": "Program Leadership",
        "focus": "leadership, shared process, execution, accountability, operating rhythm",
    },
    "therapist-referral": {
        "label": "Therapy / Referral",
        "focus": "trust, relationships, care quality, referral handoffs, feeling understood",
    },
    "enrollment-management": {
        "label": "Enrollment Mgmt",
        "focus": "pipeline quality, follow-up, conversion, journey clarity, operational friction",
    },
    "ai-entrepreneurship": {
        "label": "AI + Ops",
        "focus": "AI-native operations, context, ownership, workflow design, execution leverage",
    },
}

FORBIDDEN_PHRASES = [
    "agreed.",
    "completely agree.",
    "what stands out",
    "this is directly relevant",
    "this is directly useful",
    "from an admissions lens",
    "from an entrepreneurship lens",
    "from a leadership lens",
    "from an ai and ops lens",
]

PREFERRED_REPLACEMENTS = {
    "agreed.": "That part matters.",
    "completely agree.": "This is the part a lot of teams miss.",
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


def normalize_voice(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    for source, replacement in PREFERRED_REPLACEMENTS.items():
        if normalized.lower().startswith(source):
            normalized = replacement + normalized[len(source) :]
    replacements = {
        "What stands out to me here is": "The deeper issue here is",
        "From an enrollment perspective,": "",
        "From an admissions perspective,": "",
        "From a leadership lens,": "",
        "From an AI and ops lens,": "",
    }
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)
    for phrase in FORBIDDEN_PHRASES:
        normalized = normalized.replace(phrase, "")
        normalized = normalized.replace(phrase.title(), "")
    normalized = " ".join(normalized.split())
    return ensure_period(normalized) if normalized else ""


def clean_reason(value: str) -> str:
    text = clean_sentence(value)
    prefixes = [
        "This is directly useful for your role because ",
        "This is directly relevant to your AI-native intrapreneur positioning because ",
        "This gives you a role-safe education lens for AI content: ",
    ]
    lowered = text.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix.lower()):
            return ensure_period(text[len(prefix) :].strip())
    return ensure_period(text) if text else ""


def build_signal_context(signal: dict[str, Any], core_line: str, supporting_line: str, why_it_matters: str, priority_lane: str) -> dict[str, str]:
    title = clean_sentence(signal.get("title"))
    summary = clean_sentence(signal.get("summary"))
    topics = [clean_sentence(topic) for topic in (signal.get("topics") or []) if clean_sentence(topic)]
    return {
        "title": title,
        "core_line": ensure_period(core_line) if core_line else "",
        "supporting_line": ensure_period(supporting_line) if supporting_line else "",
        "why_it_matters": clean_reason(why_it_matters),
        "priority_lane": ensure_period(priority_lane) if priority_lane else "",
        "summary": ensure_period(summary) if summary else "",
        "topics": ", ".join(topics[:3]),
    }


def contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def infer_signal_profile(ctx: dict[str, str]) -> dict[str, bool]:
    text = " ".join(
        [
            ctx.get("title", ""),
            ctx.get("core_line", ""),
            ctx.get("supporting_line", ""),
            ctx.get("summary", ""),
            ctx.get("topics", ""),
            ctx.get("priority_lane", ""),
        ]
    ).lower()
    return {
        "is_ai": contains_any(text, ["ai", "agent", "model", "workflow", "context"]),
        "is_education": contains_any(text, ["education", "higher ed", "student", "admissions", "enrollment"]),
        "is_admissions": contains_any(text, ["admissions", "prospect", "student journey", "enrollment"]),
        "is_trust": contains_any(text, ["trust", "referral", "family", "human connection", "relationship"]),
    }


def build_admissions_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_admissions"]:
        comment = join_parts(
            [
                "That part matters.",
                ctx["supporting_line"] or ctx["core_line"],
                "That is usually where the real market signal shows up before the website, campaign, or pitch deck catches up.",
                "When teams feed that back into messaging and follow-up, trust and enrollment both get stronger.",
            ]
        )
        short = "The frontline questions are usually the strategy."
        repost = join_parts(
            [
                ctx["core_line"],
                "Admissions teams usually hear the market before the rest of the institution does.",
                "The repeated questions are often the clearest signal about where message clarity, follow-up, or the student journey still needs work.",
            ]
        )
        return comment, short, repost

    comment = join_parts(
        [
            "This is what teams miss.",
            ctx["supporting_line"] or ctx["core_line"],
            "In admissions work, this same issue usually shows up when teams lose context between inquiry, follow-up, and handoff.",
            "When that context is tighter, the experience feels more human and the pipeline gets stronger.",
        ]
    )
    short = "Context gaps show up fast in admissions."
    repost = join_parts(
        [
            ctx["core_line"],
            "I read this through an admissions lens.",
            "A lot of these problems show up when context breaks between the first conversation, the next follow-up, and what the student or family actually needs.",
        ]
    )
    return comment, short, repost


def build_entrepreneurship_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    comment = join_parts(
        [
            "There is a real builder lesson in this.",
            ctx["supporting_line"] or ctx["core_line"],
            "The edge is usually not the headline idea by itself. It is what you do with that signal operationally.",
            "The builders who turn repeated insight into process usually compound faster.",
        ]
    )
    short = "The edge is usually in the system."
    repost = join_parts(
        [
            ctx["core_line"],
            "This feels more like an execution lesson than a content lesson.",
            "The people closest to the work usually see the friction, demand, and language patterns first, which is where better systems tend to come from.",
        ]
    )
    return comment, short, repost


def build_personal_story_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    comment = join_parts(
        [
            "This hits a nerve for me.",
            ctx["supporting_line"] or ctx["core_line"],
            "A lot of these lessons only become obvious once you are the one carrying the follow-through instead of talking about it from a distance.",
            "That is usually where the insight stops being abstract and starts changing how you work.",
        ]
    )
    short = "This one feels lived-in."
    repost = join_parts(
        [
            ctx["core_line"],
            "I have learned some version of this the hard way.",
            "The part that sticks is usually not the idea itself. It is what becomes clear once you are the person holding the responsibility on the other side of it.",
        ]
    )
    return comment, short, repost


def build_program_leadership_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    comment = join_parts(
        [
            "This is where leadership shows up.",
            ctx["supporting_line"] or ctx["core_line"],
            "The teams closest to the work usually hear the signal first, but leadership matters in what happens next.",
            "If it does not get turned into shared process, it stays as anecdote instead of becoming execution.",
        ]
    )
    short = "Insight only matters if it becomes process."
    repost = join_parts(
        [
            ctx["core_line"],
            "This is a leadership signal as much as a content or systems signal.",
            "Good operators listen for these patterns early, but good leaders turn them into something the broader team can actually use.",
        ]
    )
    return comment, short, repost


def build_therapist_referral_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_trust"] or profile["is_admissions"]:
        comment = join_parts(
            [
                "This is the trust layer people feel.",
                ctx["supporting_line"] or ctx["core_line"],
                "Trust is usually built in whether people feel accurately understood, not just efficiently processed.",
                "That is also why strong handoffs and referrals tend to grow from the quality of the experience itself.",
            ]
        )
        short = "Trust is built in the handoff."
        repost = join_parts(
            [
                ctx["core_line"],
                "What stands out to me here is the trust layer underneath it.",
                "People can feel the difference between a system that is managing them and one that is actually helping them feel understood, which is where referrals usually start to compound.",
            ]
        )
        return comment, short, repost

    comment = join_parts(
        [
            "Even when the topic sounds operational, the trust layer is still there.",
            ctx["supporting_line"] or ctx["core_line"],
            "The difference between helpful and transactional usually shows up in whether people feel understood.",
            "That is often what shapes whether people stay engaged, come back, or refer someone else in.",
        ]
    )
    short = "The trust layer is usually the differentiator."
    repost = join_parts(
        [
            ctx["core_line"],
            "I keep coming back to the trust piece underneath this.",
            "A lot of systems questions are also relationship questions once a real person is living inside the experience.",
        ]
    )
    return comment, short, repost


def build_enrollment_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_admissions"] or profile["is_education"]:
        comment = join_parts(
            [
                "This is an enrollment signal to me.",
                ctx["supporting_line"] or ctx["core_line"],
                "Repeated confusion is usually a journey problem before it becomes a conversion problem.",
                "The more clearly teams can hear and resolve that friction, the better the downstream fit and follow-through tend to be.",
            ]
        )
        short = "Repeated confusion is usually a journey problem."
        repost = join_parts(
            [
                ctx["core_line"],
                "I read this as an enrollment operations signal.",
                "Small clarity gaps tend to show up later as weaker follow-up, lower conversion, or avoidable friction in the student journey.",
            ]
        )
        return comment, short, repost

    comment = join_parts(
        [
            "I still read this as an enrollment operations issue.",
            ctx["supporting_line"] or ctx["core_line"],
            "From an enrollment perspective, this is what happens when teams do not have enough context to guide the next step well.",
            "That usually shows up later as weaker follow-through and more avoidable friction.",
        ]
    )
    short = "Bad context usually becomes enrollment friction."
    repost = join_parts(
        [
            ctx["core_line"],
            "This still reads like an enrollment operations issue to me.",
            "When context is weak, the next step gets weaker too, and that tends to show up later as drop-off, confusion, or slow follow-through.",
        ]
    )
    return comment, short, repost


def build_ai_ops_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_ai"]:
        comment = join_parts(
            [
                "This is the part a lot of teams miss.",
                ctx["supporting_line"] or ctx["core_line"],
                "Most of the leverage question lives in the operating context around the work, not in the tool by itself.",
                "When context, ownership, and workflow are messy, better models rarely fix the actual execution problem.",
            ]
        )
        short = "Context is usually the real bottleneck."
        repost = join_parts(
            [
                ctx["core_line"],
                "The issue usually is not the model. It is the operating environment around it.",
                "Less demo energy. More operational clarity.",
            ]
        )
        return comment, short, repost

    comment = join_parts(
        [
            "I still read this through an AI and ops lens.",
            ctx["supporting_line"] or ctx["core_line"],
            "Even outside explicit AI conversations, this is still a systems point to me.",
            "The real lift usually comes from cleaner context, clearer ownership, and better execution design around the work.",
        ]
    )
    short = "The systems layer matters more than people think."
    repost = join_parts(
        [
            ctx["core_line"],
            "I still read this through an AI and ops lens.",
            "A lot of these signals become more useful once you translate them into context design, ownership, and workflow clarity.",
        ]
    )
    return comment, short, repost


COMMENT_BUILDERS = {
    "admissions": build_admissions_comment,
    "entrepreneurship": build_entrepreneurship_comment,
    "personal-story": build_personal_story_comment,
    "program-leadership": build_program_leadership_comment,
    "therapist-referral": build_therapist_referral_comment,
    "enrollment-management": build_enrollment_comment,
    "ai-entrepreneurship": build_ai_ops_comment,
}


def build_comment_variants(signal: dict[str, Any], title: str) -> dict[str, dict[str, str]]:
    why_it_matters = clean_sentence(signal.get("why_it_matters"))
    core_line = pick_core_line(signal)
    supporting_line = pick_supporting_line(signal, core_line)
    priority_lane = clean_sentence(signal.get("priority_lane"))
    context = build_signal_context(signal, core_line, supporting_line, why_it_matters, priority_lane)

    variants: dict[str, dict[str, str]] = {}
    for lens_id in LENS_IDS:
        config = LENS_CONFIG[lens_id]
        comment, short_comment, repost = COMMENT_BUILDERS[lens_id](context)
        variants[lens_id] = {
            "label": config["label"],
            "comment": " ".join(normalize_voice(comment).split()),
            "short_comment": " ".join(normalize_voice(short_comment).split()),
            "repost": " ".join(normalize_voice(repost).split()),
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
