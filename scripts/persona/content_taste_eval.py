#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "with",
}
FLAT_GENERIC_PATTERNS = (
    re.compile(r"\bin today's\b", re.IGNORECASE),
    re.compile(r"\b(?:workflow clarity|agent orchestration|leadership|ai|clarity)\s+is\s+(?:essential|critical|important)\b", re.IGNORECASE),
    re.compile(r"\bthe real value lies\b", re.IGNORECASE),
    re.compile(r"\bhere(?:'s| is) the takeaway\b", re.IGNORECASE),
    re.compile(r"\b(?:this|that|it)\s+is\s+(?:essential|critical|important|powerful)\b", re.IGNORECASE),
    re.compile(r"\b(?:game changer|unlock potential|drive results|magic happens)\b", re.IGNORECASE),
)
SOFT_GENERIC_PATTERNS = (
    re.compile(r"\bbreaking down silos\b", re.IGNORECASE),
    re.compile(r"\bfostering collaboration\b", re.IGNORECASE),
    re.compile(r"\bmoving in the right direction\b", re.IGNORECASE),
    re.compile(r"\bthis isn['’]?t just\b", re.IGNORECASE),
    re.compile(r"\b(?:fundamental|major|complete)\s+transformation\b", re.IGNORECASE),
    re.compile(r"\bpaving the way\b", re.IGNORECASE),
    re.compile(r"\bbigger picture\b", re.IGNORECASE),
    re.compile(r"\bai thrives when\b", re.IGNORECASE),
    re.compile(r"\b(?:enhance|enhances|enhancing)\s+(?:execution|strategy|collaboration)\b", re.IGNORECASE),
)
GENERIC_CLOSER_PATTERNS = (
    re.compile(r"^let['’]?s\s+(?:keep|continue)\b", re.IGNORECASE),
    re.compile(r"\bcontinue\s+striving\b", re.IGNORECASE),
    re.compile(r"\bkeep pushing\b", re.IGNORECASE),
    re.compile(r"\bmoving in the right direction\b", re.IGNORECASE),
)
TASTE_NEGATIVE_PATTERNS = (
    re.compile(r"\bcohesive system\b", re.IGNORECASE),
    re.compile(r"\bdependable architecture\b", re.IGNORECASE),
    re.compile(r"\bcomprehensive view\b", re.IGNORECASE),
    re.compile(r"\b(?:transition|transitioned|transitioning)\b.*\barchitecture\b", re.IGNORECASE),
    re.compile(r"\bnew level of efficiency\b", re.IGNORECASE),
    re.compile(r"\bstreamlined workflow\b", re.IGNORECASE),
    re.compile(r"\bfunction in unison\b", re.IGNORECASE),
)
TASTE_POSITIVE_PATTERNS = (
    re.compile(r"\breal talk\b", re.IGNORECASE),
    re.compile(r"\btell you what tho\b", re.IGNORECASE),
    re.compile(r"\bmakes no sense\.?\s*period\b", re.IGNORECASE),
    re.compile(r"\bthat will not work\b", re.IGNORECASE),
    re.compile(r"\bthat dog will not hunt\b", re.IGNORECASE),
    re.compile(r"\bwhere'?s the artifact\b", re.IGNORECASE),
    re.compile(r"\bpeople are not gonna use that\b", re.IGNORECASE),
    re.compile(r"\bwrite that down\b", re.IGNORECASE),
    re.compile(r"\bread that again\b", re.IGNORECASE),
    re.compile(r"\bbig shout-out\b", re.IGNORECASE),
    re.compile(r"\by['’]?all\b", re.IGNORECASE),
)
TASTE_CONTRAST_PATTERNS = (
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\binstead of\b", re.IGNORECASE),
    re.compile(r"\bbut\b", re.IGNORECASE),
    re.compile(r"\bif\b", re.IGNORECASE),
)


def _first_content_line(option: str) -> str:
    for line in (option or "").splitlines():
        cleaned = " ".join(line.split()).strip()
        if cleaned:
            return cleaned
    return " ".join((option or "").split()).strip()


def _split_sentences(text: str) -> list[str]:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return []
    return [segment.strip(" -") for segment in re.split(r"(?<=[.!?])\s+", normalized) if segment.strip()]


def _normalized_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _genericity_score(option: str) -> int:
    normalized = " ".join((option or "").lower().split())
    if not normalized:
        return 0
    score = sum(2 for pattern in FLAT_GENERIC_PATTERNS if pattern.search(normalized))
    score += sum(1 for pattern in SOFT_GENERIC_PATTERNS if pattern.search(normalized))
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    if paragraphs and any(pattern.search(paragraphs[-1]) for pattern in GENERIC_CLOSER_PATTERNS):
        score += 2
    return score


def _claim_near_opening(option: str, claim: str) -> bool:
    opening = " ".join((option or "").split())[:220].lower()
    normalized_claim = " ".join((claim or "").split()).lower()
    if not opening or not normalized_claim:
        return False
    if normalized_claim in opening:
        return True
    claim_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_claim)
        if len(token) > 3 and token not in STOPWORDS
    }
    opening_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", opening)
        if len(token) > 3 and token not in STOPWORDS
    }
    return len(claim_terms.intersection(opening_terms)) >= 3


def _proof_visible(option: str, proof_packet: str) -> bool:
    if not option or not proof_packet:
        return False
    proof = proof_packet.split("->", 1)[-1].strip()
    return len(_normalized_terms(option).intersection(_normalized_terms(proof))) >= 2


def score_option_taste(option: str, *, primary_claim: str, proof_packet: str, story_beat: str = "") -> dict[str, object]:
    warnings: list[str] = []
    strengths: list[str] = []
    score = 60
    genericity = _genericity_score(option)
    if genericity:
        score -= genericity * 6
        warnings.append(f"genericity:{genericity}")
    else:
        strengths.append("low_genericity")

    if _claim_near_opening(option, primary_claim):
        score += 10
        strengths.append("claim_led_opening")
    else:
        score -= 10
        warnings.append("claim_not_leading")

    if _proof_visible(option, proof_packet):
        score += 10
        strengths.append("proof_grounded")
    else:
        score -= 8
        warnings.append("proof_not_visible")

    negative_hits = [pattern.pattern for pattern in TASTE_NEGATIVE_PATTERNS if pattern.search(option)]
    if negative_hits:
        score -= len(negative_hits) * 6
        warnings.extend("taste_negative" for _ in negative_hits)
    else:
        strengths.append("no_corporate_taste_hits")

    if any(pattern.search(option) for pattern in TASTE_POSITIVE_PATTERNS):
        score += 6
        strengths.append("johnnie_phrase_energy")
    if any(pattern.search(option) for pattern in TASTE_CONTRAST_PATTERNS):
        score += 4
        strengths.append("contrast_present")
    else:
        warnings.append("low_contrast")

    lengths = [len(sentence.split()) for sentence in _split_sentences(option)]
    if lengths:
        if any(length <= 6 for length in lengths):
            score += 3
            strengths.append("short_punchy_sentence")
        else:
            warnings.append("no_short_sentence")
        if (sum(lengths) / len(lengths)) > 18:
            score -= 4
            warnings.append("too_smoothed")
        else:
            strengths.append("spoken_sentence_length")

    if option.count("\n\n") >= 2:
        score += 2
        strengths.append("human_paragraph_cadence")
    else:
        warnings.append("paragraph_cadence_flat")

    first_line = _first_content_line(option)
    if first_line.lower().startswith(("we ", "we’ve ", "we've ", "this ", "it ", "our ")):
        score -= 4
        warnings.append("soft_opening_subject")

    return {
        "overall": max(0, min(100, score)),
        "warnings": warnings,
        "strengths": strengths,
        "first_line": first_line,
        "primary_claim": primary_claim,
        "proof_packet": proof_packet,
        "story_beat": story_beat,
    }


FIXTURES = [
    {
        "name": "johnnie_operator",
        "option": (
            "Prompting alone is not an AI strategy.\n\n"
            "Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, "
            "and proof-aware prompts instead of isolated prompting.\n\n"
            "That is the operating model."
        ),
        "brief": {
            "primary_claim": "Prompting alone is not an AI strategy.",
            "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            "story_beat": "",
        },
    },
    {
        "name": "generic_linkedin",
        "option": (
            "Agent orchestration is critical for driving results.\n\n"
            "This gives teams a cohesive system and a comprehensive view of their work.\n\n"
            "We're moving in the right direction."
        ),
        "brief": {
            "primary_claim": "Prompting alone is not an AI strategy.",
            "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            "story_beat": "",
        },
    },
]


def _score_response_file(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    diagnostics = payload.get("diagnostics") or {}
    briefs = diagnostics.get("planned_option_briefs") or []
    options = payload.get("options") or []
    results: list[dict[str, object]] = []
    for index, option in enumerate(options):
        brief = briefs[index] if index < len(briefs) and isinstance(briefs[index], dict) else {}
        results.append(
            {
                "name": f"option_{index + 1}",
                **score_option_taste(
                    str(option),
                    primary_claim=str(brief.get("primary_claim") or ""),
                    proof_packet=str(brief.get("proof_packet") or ""),
                    story_beat=str(brief.get("story_beat") or ""),
                ),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Johnnie taste scores for generated content.")
    parser.add_argument("--response-file", type=Path, help="Path to a saved content-generation JSON response.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the human summary.")
    args = parser.parse_args()

    if args.response_file:
        results = _score_response_file(args.response_file)
    else:
        results = [
            {
                "name": item["name"],
                **score_option_taste(
                    item["option"],
                    primary_claim=item["brief"]["primary_claim"],
                    proof_packet=item["brief"]["proof_packet"],
                    story_beat=item["brief"]["story_beat"],
                ),
            }
            for item in FIXTURES
        ]

    if args.json:
        print(json.dumps({"results": results}, indent=2))
        return 0

    for result in results:
        print(f'{result["name"]}: {result["overall"]}')
        print(f'  first_line: {result["first_line"]}')
        print(f'  strengths: {", ".join(result["strengths"] or [])}')
        print(f'  warnings: {", ".join(result["warnings"] or [])}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
