from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


GENERIC_PHRASES = [
    "this is important",
    "in today's world",
    "leverage",
    "game changer",
    "synergy",
    "more than ever",
]

AUTHORITY_MARKERS = [
    "the challenge is",
    "the harder part is",
    "the real challenge is",
    "the real question is",
    "the point is",
    "the issue is",
    "you cannot",
    "it is not",
    "it isn't",
    "it is",
    "the move is",
]

HEDGE_MARKERS = [
    " kind of ",
    " sort of ",
    " maybe ",
    " might ",
    " can sometimes ",
]

SOFTENING_PATTERNS = [
    "less ",
    "more ",
]


def normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def clean_sentence(value: str | None) -> str:
    text = normalize_inline_text(value)
    if not text:
        return ""
    return text[:-1] if text.endswith(".") else text


def ensure_period(text: str) -> str:
    cleaned = normalize_inline_text(text)
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round_score(value: float) -> float:
    return round(value, 1)


def detect_expression_structure(text: str | None) -> str:
    cleaned = clean_sentence(text)
    lowered = cleaned.lower()
    if not cleaned:
        return "none"
    if re.search(r"not because .+? but because .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-causal"
    if re.search(r"isn[’']t .+?, it[’']s .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-direct"
    if re.search(r"not .+?\. it is .+$", lowered, flags=re.IGNORECASE):
        return "contrast-direct"
    if "not a substitute for" in lowered:
        return "boundary-substitute"
    if re.search(r"can augment .+?, but humans still need to .+$", cleaned, flags=re.IGNORECASE):
        return "boundary-augment"
    if re.search(r"if you want better .+?, start with .+$", cleaned, flags=re.IGNORECASE):
        return "directive-start-with"
    return "plain"


def similarity_ratio(a: str | None, b: str | None) -> float:
    left = normalize_inline_text(a).lower()
    right = normalize_inline_text(b).lower()
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, left, right).ratio(), 3)


def analyze_expression(text: str | None) -> dict[str, Any]:
    cleaned = clean_sentence(text)
    lowered = cleaned.lower()
    structure = detect_expression_structure(cleaned)
    warnings: list[str] = []

    if not cleaned:
        return {
            "text": "",
            "structure": "none",
            "overall": 0.0,
            "contrast_strength": 0.0,
            "authority": 0.0,
            "specificity": 0.0,
            "genericity_penalty": 0.0,
            "warnings": ["no expression content"],
        }

    words = cleaned.split()
    contrast_strength = 5.0
    authority = 5.0
    specificity = 5.0
    genericity_penalty = 0.0
    overall = 5.6

    if structure.startswith("contrast"):
        contrast_strength += 2.8
        overall += 1.1
    elif structure.startswith("boundary"):
        contrast_strength += 1.8
        overall += 0.7
    elif structure == "directive-start-with":
        contrast_strength += 1.4
        overall += 0.5

    if any(marker in lowered for marker in AUTHORITY_MARKERS):
        authority += 1.8
        overall += 0.7

    if any(pattern in lowered for pattern in HEDGE_MARKERS):
        authority -= 0.8
        overall -= 0.4
        warnings.append("hedged phrasing")

    if structure.startswith("contrast") and all(pattern in lowered for pattern in SOFTENING_PATTERNS):
        authority -= 1.0
        contrast_strength -= 1.2
        overall -= 0.8
        warnings.append("contrast softened into balancing language")

    if 8 <= len(words) <= 26:
        specificity += 1.0
        overall += 0.4
    elif len(words) > 34:
        specificity -= 0.6
        overall -= 0.3
        warnings.append("sentence is long")

    if re.search(r"\b(ai|student|students|families|staff|workflow|judgment|trust|ownership|handoff|leadership)\b", lowered):
        specificity += 0.6
        overall += 0.2

    if any(phrase in lowered for phrase in GENERIC_PHRASES):
        genericity_penalty += 1.6
        overall -= 1.0
        warnings.append("contains generic phrasing")

    return {
        "text": ensure_period(cleaned),
        "structure": structure,
        "overall": round_score(clamp(overall, 1.0, 10.0)),
        "contrast_strength": round_score(clamp(contrast_strength, 1.0, 10.0)),
        "authority": round_score(clamp(authority, 1.0, 10.0)),
        "specificity": round_score(clamp(specificity, 1.0, 10.0)),
        "genericity_penalty": round_score(clamp(genericity_penalty, 0.0, 10.0)),
        "warnings": warnings[:3],
    }


class SocialExpressionEngine:
    """Sentence-level expression analysis for source/output comparisons."""

    def compare(self, source_text: str | None, output_text: str | None) -> dict[str, Any]:
        source = analyze_expression(source_text)
        output = analyze_expression(output_text)
        overlap = similarity_ratio(source_text, output_text)
        source_structure = source["structure"]
        output_structure = output["structure"]
        structure_preserved = source_structure in {"none", "plain"} or source_structure == output_structure
        expression_delta = round_score(output["overall"] - source["overall"])

        warnings: list[str] = []
        if source_structure.startswith("contrast") and not structure_preserved:
            warnings.append("rewrite lost source contrast structure")
        if source_structure.startswith("boundary") and not structure_preserved:
            warnings.append("rewrite weakened source boundary framing")
        if expression_delta < -0.5:
            warnings.append("rewrite weakened source expression")
        if overlap > 0.92:
            warnings.append("rewrite remains too close to source")

        adjusted_output_quality = output["overall"]
        if expression_delta < 0:
            adjusted_output_quality = round_score(clamp(adjusted_output_quality + expression_delta, 1.0, 10.0))
        if overlap > 0.92:
            adjusted_output_quality = round_score(clamp(adjusted_output_quality - 1.5, 1.0, 10.0))
        if source_structure.startswith(("contrast", "boundary")) and not structure_preserved:
            adjusted_output_quality = round_score(clamp(adjusted_output_quality - 1.2, 1.0, 10.0))

        return {
            "source_text": source["text"],
            "output_text": output["text"],
            "source_structure": source_structure,
            "output_structure": output_structure,
            "structure_preserved": structure_preserved,
            "source_expression_quality": source["overall"],
            "output_expression_quality": output["overall"],
            "expression_delta": expression_delta,
            "overlap_ratio": overlap,
            "adjusted_output_quality": adjusted_output_quality,
            "source_detail": source,
            "output_detail": output,
            "warnings": warnings[:4],
        }

    def choose_candidate(self, source_text: str | None, candidates: list[dict[str, str]]) -> dict[str, Any]:
        cleaned_source = ensure_period(clean_sentence(source_text))
        if not cleaned_source:
            return {
                "source_text": "",
                "output_text": "",
                "strategy": "none",
                "source_structure": "none",
                "output_structure": "none",
                "structure_preserved": True,
                "source_expression_quality": 0.0,
                "output_expression_quality": 0.0,
                "expression_delta": 0.0,
                "overlap_ratio": 0.0,
                "adjusted_output_quality": 0.0,
                "warnings": ["no source sentence"],
            }

        assessed: list[dict[str, Any]] = []
        for candidate in candidates:
            text = ensure_period(candidate.get("text", ""))
            if not text:
                continue
            comparison = self.compare(cleaned_source, text)
            comparison["strategy"] = candidate.get("strategy", "candidate")
            assessed.append(comparison)

        if not assessed:
            baseline = self.compare(cleaned_source, "")
            baseline["strategy"] = "none"
            return baseline

        assessed.sort(
            key=lambda item: (
                item["adjusted_output_quality"],
                item["structure_preserved"],
                -item["overlap_ratio"],
            ),
            reverse=True,
        )
        return assessed[0]


social_expression_engine = SocialExpressionEngine()
