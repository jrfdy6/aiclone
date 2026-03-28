from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.services.social_belief_engine import social_belief_engine
from app.services.social_source_asset_service import build_source_asset_inventory

CONTRAST_TERMS = (" not ", " but ", " because ", " however ", " instead ", " rather than ")
PROCESS_TERMS = (
    "system",
    "process",
    "workflow",
    "ownership",
    "handoff",
    "execution",
    "team",
    "leadership",
    "training",
    "change management",
    "culture",
    "standard",
)
AI_TERMS = (" ai ", "agent", "model", "prompt", "automation", "llm", "judgment")
ADMISSIONS_TERMS = (" admissions", " enrollment", " prospect", " student journey", " referral", " family trust")
STORY_TERMS = (" i ", " my ", " we ", " our ", " learned", " experience", " story")
BOILERPLATE_PREFIXES = (
    "thank you",
    "hello",
    "good morning",
    "good afternoon",
    "welcome",
    "one question is",
    "that's a great question",
)
EVENT_META_TERMS = (
    "south by",
    "show of hands",
    "closing keynote",
    "give it up",
    "you guys",
    "this presentation",
    "the slide",
    "today we are talking about",
    "years later to talk to you about",
)
WORLDVIEW_TERMS = (
    "trust",
    "culture",
    "resistance to change",
    "operational efficiencies",
    "customer experience",
    "drive revenue",
    "return on investment",
    "roi",
    "bias",
    "transparency",
    "hallucinations",
    "workflow clarity",
    "leadership",
    "rollout",
    "adoption stalled",
    "process and training approach",
    "more likely to be successful",
    "ai pilots",
    "failing",
)
DIRECT_REACTION_TERMS = (
    "fail",
    "failing",
    "successful",
    "trust",
    "judgment",
    "bias",
    "hallucinations",
    "workflow clarity",
    "rollout",
    "adoption",
    "leadership",
    "replace",
    "more likely",
)
REACTION_DISCOURAGED_PREFIXES = (
    "the ",
    "that's ",
    "a company ",
)
SELF_CREDENTIAL_PATTERNS = (
    r"\bi(?:'ve| have) been working in\b",
    r"\bi am the chief\b",
    r"\bi do have credibility\b",
    r"\bi know what i(?:'m| am) talking about\b",
    r"\bmy book\b",
    r"\bi travel a lot\b",
)
DEFINITION_PATTERNS = (
    r"\bmachine learning is a subset of ai\b",
    r"\bgenerative ai is a subset of machine learning\b",
    r"\buses math and statistical processes\b",
    r"\bmake predictions\b",
)
WEAK_CONTEXT_PATTERNS = (
    r"\bthat element in green\b",
    r"\bquestions when my team is sleeping\b",
    r"\bmy team and i thought\b",
    r"\bwhy does it have to be that way\??$",
    r"\bi(?:'m| am) super proud\b",
    r"\balive in spirit\b",
    r"\bnot very well done\b",
    r"\bchief product officer was presenting\b",
    r"\bshowed me (?:his|her|their) ai dashboard\b",
)
HYPE_PATTERNS = (
    r"\b\d+\s+years in the field of ai\b",
    r"\bthat(?:'s| is) an eternity\b",
    r"\bai magic takes over\b",
    r"\bmost transformative technology of our generation\b",
)
NOISY_LINE_TERMS = (
    "pending owner review",
    "pending routing review",
    "quotes to reuse",
    "open questions",
    "review build implications",
    "review persona implications",
    "validation transcript",
    "media background queue",
)
NOISY_SECTION_HEADINGS = ("owner notes", "follow-ups")
TARGET_CLAIMS = "identity/claims.md"
TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_STORIES = "history/story_bank.md"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def _trim_noise_sections(text: str) -> str:
    if not text:
        return ""
    pattern = re.compile(
        r"^\s*##\s+(?:"
        + "|".join(re.escape(section) for section in NOISY_SECTION_HEADINGS)
        + r")\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    return text[: match.start()].strip() if match else text.strip()


def _normalize_source_line(raw_line: str) -> str:
    line = raw_line.strip()
    if not line:
        return ""
    if line.startswith("#"):
        return ""
    if re.match(r"^- \[[ xX]\]\s+", line):
        return ""
    line = re.sub(r"^\d+\.\s+", "", line)
    line = re.sub(r"^-+\s+", "", line)
    line = re.sub(r"^\*\*[^*]+\*\*:\s*", "", line)
    line = re.sub(r"^(Transcript\s+Host|Host|Speaker\s*\d+|Moderator|Interviewer|Question|Audience):\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^Transcript\s*$", "", line, flags=re.IGNORECASE)
    line = _clean_text(line)
    lowered = line.lower()
    if not line:
        return ""
    if any(term in lowered for term in NOISY_LINE_TERMS):
        return ""
    if lowered.endswith(":") and len(lowered.split()) <= 4:
        return ""
    return line


def _sentence_case(text: str) -> str:
    text = _clean_text(text)
    if not text:
        return ""
    return f"{text[0].upper()}{text[1:]}" if len(text) > 1 else text.upper()


def _ensure_terminal_punctuation(text: str) -> str:
    text = _clean_text(text)
    if not text:
        return ""
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _normalize_worldview_candidate(candidate: str) -> str:
    text = _clean_text(candidate)
    if not text:
        return ""

    text = re.sub(r"^(?:And|But|So|Well)\s+", "", text, flags=re.IGNORECASE)
    text = _clean_text(text)

    patterns: list[tuple[str, Any]] = [
        (
            r"^We're gonna start with leadership and talk a little bit about why (.+)$",
            lambda match: _ensure_terminal_punctuation(_sentence_case(match.group(1))),
        ),
        (
            r"^One story from the conversation described a company that (.+)$",
            lambda match: _ensure_terminal_punctuation(_sentence_case(f"A company {match.group(1)}")),
        ),
        (
            r"^At [^,]+, where we work to identify and implement (.+)$",
            lambda match: _ensure_terminal_punctuation(_sentence_case(f"The practical work is to identify and implement {match.group(1)}")),
        ),
        (
            r"^Even if I identify a handful of those opportunities, how do I overcome (.+)\?$",
            lambda match: _sentence_case(f"The harder problem is overcoming {match.group(1)}."),
        ),
        (
            r"^If your CEO is using it for prompting and for agents, brainstorming with you, doing cross-team groups with you, you're (.+?) because they're talking about it\.$",
            lambda match: _sentence_case(f"If your CEO is visibly using AI for prompting and agents, you're {match.group(1)}."),
        ),
        (
            r"^The better question would be if we rebuilt (.+), what would that look like\?$",
            lambda match: _sentence_case(f"The better question is what it would look like if we rebuilt {match.group(1)}."),
        ),
    ]

    for pattern, builder in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            text = builder(match)
            break

    return _ensure_terminal_punctuation(_sentence_case(text))


def _candidate_sentences(text: str, limit: int = 60) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = _normalize_source_line(raw_line)
        if not line:
            continue
        normalized = re.sub(r"\s+", " ", line)
        raw_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", normalized)
        for part in raw_parts:
            candidate = _clean_text(part)
            candidate = _normalize_worldview_candidate(candidate)
            lowered = candidate.lower()
            if not candidate or lowered in seen:
                continue
            seen.add(lowered)
            sentences.append(candidate)
            if len(sentences) >= limit:
                return sentences
    return sentences


def _bullet_lines(text: str, limit: int = 20) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            candidate = _normalize_source_line(line[2:])
        elif re.match(r"^\d+\.\s+", line):
            candidate = _normalize_source_line(re.sub(r"^\d+\.\s+", "", line))
        else:
            continue
        lowered = candidate.lower()
        if not candidate or lowered in seen:
            continue
        seen.add(lowered)
        items.append(candidate)
        if len(items) >= limit:
            break
    return items


def _read_asset_content(asset: dict[str, Any], repo_root: Path) -> tuple[dict[str, Any], str]:
    rel_path = _clean_text(asset.get("source_path"))
    if not rel_path:
        return {}, ""
    path = repo_root / rel_path
    if not path.exists():
        return {}, ""
    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    return meta, _trim_noise_sections(body)


def _is_boilerplate(sentence: str, asset_title: str) -> bool:
    lowered = f" {_clean_text(sentence).lower()} "
    if any(lowered.strip().startswith(prefix) for prefix in BOILERPLATE_PREFIXES):
        return True
    if any(term in lowered for term in NOISY_LINE_TERMS):
        return True
    title = _clean_text(asset_title).lower()
    if title and lowered.strip() == title:
        return True
    if len(lowered.split()) < 6:
        return True
    return False


def _score_sentence(sentence: str, asset: dict[str, Any]) -> tuple[int, int, int]:
    text = _clean_text(sentence)
    lowered = f" {text.lower()} "
    words = text.split()
    score = 0
    if 8 <= len(words) <= 34:
        score += 3
    elif 6 <= len(words) <= 42:
        score += 1
    else:
        score -= 2
    if any(term in lowered for term in CONTRAST_TERMS):
        score += 3
    if any(term in lowered for term in PROCESS_TERMS):
        score += 2
    if any(term in lowered for term in AI_TERMS):
        score += 2
    if any(term in lowered for term in ADMISSIONS_TERMS):
        score += 2
    if any(term in lowered for term in WORLDVIEW_TERMS):
        score += 2
    if re.search(r"\b\d+\b", text):
        score += 1
    if any(term in lowered for term in STORY_TERMS):
        score += 1
    if _clean_text(asset.get("source_channel")) in {"youtube", "podcast"} and "question" in lowered:
        score -= 1
    if any(term in lowered for term in EVENT_META_TERMS):
        score -= 3
    if any(re.search(pattern, lowered) for pattern in SELF_CREDENTIAL_PATTERNS):
        score -= 4
    if any(re.search(pattern, lowered) for pattern in DEFINITION_PATTERNS):
        score -= 3
    if any(re.search(pattern, lowered) for pattern in WEAK_CONTEXT_PATTERNS):
        score -= 6
    if any(re.search(pattern, lowered) for pattern in HYPE_PATTERNS):
        score -= 5
    if _is_boilerplate(text, _clean_text(asset.get("title"))):
        score -= 4
    return score, len(words), -len(text)


def _extract_segments(asset: dict[str, Any], body: str, max_segments: int) -> list[tuple[str, tuple[int, int, int]]]:
    summary = _clean_text(asset.get("summary"))
    candidates: list[str] = []
    seen: set[str] = set()

    for candidate in _bullet_lines(body, limit=24) + _candidate_sentences(summary, limit=8):
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(candidate)

    body_sentences = _candidate_sentences(body, limit=80)
    for candidate in body_sentences:
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(candidate)

    scored = [
        (candidate, _score_sentence(candidate, asset))
        for candidate in candidates
        if not _is_boilerplate(candidate, _clean_text(asset.get("title")))
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    selected: list[tuple[str, tuple[int, int, int]]] = []
    for candidate, metrics in scored:
        if metrics[0] < 2:
            continue
        candidate_words = set(re.findall(r"[a-z0-9]+", candidate.lower()))
        if any(len(candidate_words & set(re.findall(r"[a-z0-9]+", existing.lower()))) >= min(8, len(candidate_words)) for existing, _ in selected):
            continue
        selected.append((candidate, metrics))
        if len(selected) >= max_segments:
            break
    return selected


def _lane_hint(text: str) -> str:
    lowered = f" {_clean_text(text).lower()} "
    if any(term in lowered for term in AI_TERMS):
        return "ai"
    if any(term in lowered for term in ADMISSIONS_TERMS):
        return "admissions"
    if any(term in lowered for term in STORY_TERMS):
        return "personal-story"
    if any(term in lowered for term in PROCESS_TERMS):
        return "program-leadership"
    return "current-role"


def _choose_target_file(text: str, lane_id: str, assessment: dict[str, str]) -> str:
    lowered = f" {_clean_text(text).lower()} "
    if lane_id == "personal-story" or any(term in lowered for term in ("i learned", "i remember", "my experience", "origin story")):
        return TARGET_STORIES
    if assessment.get("stance") in {"counter", "nuance"} or any(term in lowered for term in CONTRAST_TERMS):
        return TARGET_CLAIMS
    if len(text.split()) <= 18:
        return TARGET_VOICE
    return TARGET_CLAIMS


def _build_signal(asset: dict[str, Any], segment: str) -> dict[str, Any]:
    title = _clean_text(asset.get("title"))
    summary = _clean_text(asset.get("summary"))
    return {
        "title": title,
        "summary": summary,
        "core_claim": segment,
        "supporting_claims": [summary] if summary and summary.lower() != segment.lower() else [],
        "source_class": asset.get("source_class"),
        "source_channel": asset.get("source_channel"),
        "source_type": asset.get("source_type"),
        "source_url": asset.get("source_url"),
        "topic_tags": list(asset.get("topics") or []) + list(asset.get("tags") or []),
    }


def _route_score(segment: str, assessment: dict[str, str], target_file: str, worldview_score: int) -> int:
    lowered = f" {_clean_text(segment).lower()} "
    words = len(segment.split())
    score = worldview_score
    if 8 <= words <= 24:
        score += 3
    elif 6 <= words <= 30:
        score += 1
    else:
        score -= 2
    if re.search(r"\b\d+\b", lowered):
        score += 1
    if any(term in lowered for term in CONTRAST_TERMS):
        score += 1
    if assessment.get("stance") in {"counter", "nuance"}:
        score += 1
    if target_file == TARGET_STORIES:
        score -= 1
    return score


def _is_comment_ready_segment(segment: str, score: int, target_file: str) -> bool:
    cleaned = _clean_text(segment)
    lowered = f" {cleaned.lower()} "
    words = cleaned.split()
    if target_file == TARGET_STORIES:
        return False
    if not 8 <= len(words) <= 18:
        return False
    if score < 12:
        return False
    if any(cleaned.lower().startswith(prefix) for prefix in REACTION_DISCOURAGED_PREFIXES):
        return False
    if re.search(r"\b\d+\b", cleaned):
        return True
    if any(term in lowered for term in CONTRAST_TERMS):
        return True
    return any(term in lowered for term in DIRECT_REACTION_TERMS)


def _is_repost_ready_segment(segment: str, score: int, target_file: str) -> bool:
    cleaned = _clean_text(segment)
    if not _is_comment_ready_segment(cleaned, score, target_file):
        return False
    if len(cleaned.split()) > 15 or score < 14:
        return False
    lowered = f" {cleaned.lower()} "
    return bool(re.search(r"\b\d+\b", cleaned) or any(term in lowered for term in CONTRAST_TERMS))


def _classify_routes(segment: str, assessment: dict[str, str], target_file: str, worldview_score: int) -> tuple[list[str], str, str, int]:
    routes = {"post_seed", "belief_evidence"}
    score = _route_score(segment, assessment, target_file, worldview_score)
    words = len(segment.split())

    if _is_comment_ready_segment(segment, score, target_file):
        routes.add("comment")
    if _is_repost_ready_segment(segment, score, target_file):
        routes.add("repost")

    if "comment" in routes:
        primary = "comment"
        reason = "segment is compact and explicit enough for direct reaction"
    elif target_file == TARGET_VOICE or words <= 18:
        primary = "belief_evidence"
        reason = "segment is better suited to persona language or worldview capture"
    else:
        primary = "post_seed"
        reason = "segment is stronger as an original post angle than a direct reaction"

    ordered = [mode for mode in ("comment", "repost", "post_seed", "belief_evidence") if mode in routes]
    return ordered, primary, reason, score


def _review_key(asset: dict[str, Any], segment: str, target_file: str) -> str:
    source = "|".join(
        [
            _clean_text(asset.get("asset_id")),
            _clean_text(asset.get("source_path")),
            target_file,
            _clean_text(segment).lower(),
        ]
    )
    return f"long-form:{hashlib.sha1(source.encode('utf-8')).hexdigest()[:16]}"


def extract_long_form_candidates(
    *,
    repo_root: Path,
    source_assets: dict[str, Any] | None = None,
    transcripts_root: Path | None = None,
    ingestions_root: Path | None = None,
    max_assets: int = 4,
    max_segments_per_asset: int = 2,
) -> dict[str, Any]:
    inventory = source_assets
    if inventory is None:
        inventory = build_source_asset_inventory(
            transcripts_root=transcripts_root or repo_root / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=ingestions_root or repo_root / "knowledge" / "ingestions",
            repo_root=repo_root,
        )

    items = [
        item
        for item in (inventory.get("items") or [])
        if item.get("source_class") == "long_form_media"
        and any(mode in {"belief_evidence", "post_seed"} for mode in (item.get("response_modes") or []))
    ]

    candidates: list[dict[str, Any]] = []
    assets_considered = 0
    skipped_no_segments = 0
    by_channel: dict[str, int] = {}
    assets: list[dict[str, Any]] = []

    for asset in items[:max_assets]:
        assets_considered += 1
        channel = _clean_text(asset.get("source_channel")) or "unknown"
        by_channel[channel] = by_channel.get(channel, 0) + 1
        _, body = _read_asset_content(asset, repo_root)
        if not body:
            skipped_no_segments += 1
            continue
        segments = _extract_segments(asset, body, max_segments=max_segments_per_asset)
        if not segments:
            skipped_no_segments += 1
            continue

        asset_candidates: list[dict[str, Any]] = []
        for index, (segment, metrics) in enumerate(segments, start=1):
            worldview_score = int(metrics[0])
            lane_id = _lane_hint(segment)
            assessment = social_belief_engine.assess_signal(_build_signal(asset, segment), lane_id)
            target_file = _choose_target_file(segment, lane_id, assessment)
            response_modes, primary_route, route_reason, route_score = _classify_routes(segment, assessment, target_file, worldview_score)
            candidate = {
                "candidate_id": _review_key(asset, segment, target_file),
                "asset_id": _clean_text(asset.get("asset_id")),
                "title": _clean_text(asset.get("title")) or "Untitled asset",
                "source_channel": channel,
                "source_type": _clean_text(asset.get("source_type")),
                "source_url": _clean_text(asset.get("source_url")),
                "source_path": _clean_text(asset.get("source_path")),
                "segment_index": index,
                "segment_total": len(segments),
                "segment": segment,
                "lane_hint": lane_id,
                "target_file": target_file,
                "stance": assessment.get("stance", ""),
                "belief_summary": _clean_text(assessment.get("belief_summary")),
                "experience_summary": _clean_text(assessment.get("experience_summary")),
                "response_modes": response_modes,
                "primary_route": primary_route,
                "route_reason": route_reason,
                "worldview_score": worldview_score,
                "route_score": route_score,
                "assessment": assessment,
                "asset": asset,
            }
            candidates.append(candidate)
            asset_candidates.append(candidate)

        assets.append(
            {
                "asset_id": _clean_text(asset.get("asset_id")),
                "title": _clean_text(asset.get("title")) or "Untitled asset",
                "source_channel": channel,
                "source_path": _clean_text(asset.get("source_path")),
                "extracted_segments": len(asset_candidates),
                "primary_routes": list(dict.fromkeys(item["primary_route"] for item in asset_candidates)),
                "response_modes": list(dict.fromkeys(mode for item in asset_candidates for mode in item["response_modes"])),
            }
        )

    candidates.sort(key=lambda item: (-int(item["route_score"]), item["title"].lower(), item["segment_index"]))
    route_counts = {mode: 0 for mode in ("comment", "repost", "post_seed", "belief_evidence")}
    primary_route_counts = {mode: 0 for mode in ("comment", "repost", "post_seed", "belief_evidence")}
    lane_counts: dict[str, int] = {}
    for candidate in candidates:
        lane = str(candidate["lane_hint"])
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
        primary_route_counts[str(candidate["primary_route"])] += 1
        for mode in candidate["response_modes"]:
            route_counts[str(mode)] += 1

    return {
        "assets_considered": assets_considered,
        "segments_total": len(candidates),
        "skipped_no_segments": skipped_no_segments,
        "route_counts": route_counts,
        "primary_route_counts": primary_route_counts,
        "lane_counts": lane_counts,
        "by_channel": by_channel,
        "assets": assets,
        "candidates": candidates,
    }


def build_long_form_route_summary(
    *,
    repo_root: Path,
    source_assets: dict[str, Any] | None = None,
    transcripts_root: Path | None = None,
    ingestions_root: Path | None = None,
    max_assets: int = 4,
    max_segments_per_asset: int = 2,
) -> dict[str, Any]:
    extracted = extract_long_form_candidates(
        repo_root=repo_root,
        source_assets=source_assets,
        transcripts_root=transcripts_root,
        ingestions_root=ingestions_root,
        max_assets=max_assets,
        max_segments_per_asset=max_segments_per_asset,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets_considered": extracted["assets_considered"],
        "segments_total": extracted["segments_total"],
        "skipped_no_segments": extracted["skipped_no_segments"],
        "route_counts": extracted["route_counts"],
        "primary_route_counts": extracted["primary_route_counts"],
        "lane_counts": extracted["lane_counts"],
        "by_channel": extracted["by_channel"],
        "assets": extracted["assets"],
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "asset_id": item["asset_id"],
                "title": item["title"],
                "source_channel": item["source_channel"],
                "source_url": item["source_url"],
                "source_path": item["source_path"],
                "segment": item["segment"],
                "lane_hint": item["lane_hint"],
                "target_file": item["target_file"],
                "stance": item["stance"],
                "belief_summary": item["belief_summary"],
                "response_modes": item["response_modes"],
                "primary_route": item["primary_route"],
                "route_reason": item["route_reason"],
                "route_score": item["route_score"],
            }
            for item in extracted["candidates"][:12]
        ],
    }
