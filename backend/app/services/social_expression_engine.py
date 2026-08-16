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
    "the real test is",
    "the point is",
    "the issue is",
    "the useful version is",
    "the signal matters once",
    "the pattern only matters once",
    "the pattern only counts once",
    "the idea is only useful once",
    "this gets more useful once",
    "this gets clearer once",
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

STRUCTURE_SIGNAL_MARKERS = {
    "trend-compounding": [
        "what compounds is",
        "stops being the moat",
        "the moat",
    ],
    "cascade-warning": [
        "does not stay confined",
        "harder questions",
        "eventually shows up",
    ],
    "timing-gap": [
        "timing gap",
        "long before",
        "repeatable",
        "repeat it",
    ],
    "contrast-hidden": [
        "visible",
        "underlying",
        "cleaner than",
        "one layer lower",
    ],
    "contrast-causal": [
        "rarely",
        "because",
        "handoff",
        "decision rules",
    ],
}


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
    if "stops being the moat" in lowered or "what compounds is" in lowered:
        return "trend-compounding"
    if "does not stay confined to" in lowered or "doesn't stay confined to" in lowered:
        return "cascade-warning"
    if "timing gap" in lowered:
        return "timing-gap"
    if "long before" in lowered and ("it is whether" in lowered or "whether the" in lowered or "team can repeat" in lowered):
        return "timing-gap"
    if re.search(r"the problem is rarely .+?\. it is whether .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-causal"
    if re.search(r"rarely .+? because .+?\. .+? because .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-causal"
    if re.search(
        r"the real (gap|issue|problem|constraint|test|question) (usually )?(shows up|sits|starts) .+$",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return "contrast-hidden"
    if "visible" in lowered and "underlying" in lowered:
        return "contrast-hidden"
    if re.search(r"not because .+? but because .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-causal"
    if re.search(r"(the issue|the challenge) is not that .+?\. it is that .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-causal"
    if re.search(r"isn[’']t .+?, it[’']s .+$", cleaned, flags=re.IGNORECASE):
        return "contrast-direct"
    if re.search(r"not .+?\. it is .+$", lowered, flags=re.IGNORECASE):
        return "contrast-direct"
    if "not a substitute for" in lowered:
        return "boundary-substitute"
    if "cannot replace" in lowered:
        return "boundary-substitute"
    if re.search(r"can augment .+?, but humans still need to .+$", cleaned, flags=re.IGNORECASE):
        return "boundary-augment"
    if re.search(r"can (support|help) .+?, but (people|humans) still need to .+$", cleaned, flags=re.IGNORECASE):
        return "boundary-augment"
    if re.search(r"the win is augmentation around .+?, while the human layer still has to .+$", cleaned, flags=re.IGNORECASE):
        return "boundary-augment"
    if re.search(r"if you want better .+?, start with .+$", cleaned, flags=re.IGNORECASE):
        return "directive-start-with"
    if re.search(r"if you want better .+?, you have to start .+$", cleaned, flags=re.IGNORECASE):
        return "directive-start-with"
    if re.search(r"(this gets (more useful|clearer) once .+)$", cleaned, flags=re.IGNORECASE):
        return "directive-once"
    if re.search(r"(the (signal|pattern) (matters|only matters|only counts) once .+)$", cleaned, flags=re.IGNORECASE):
        return "directive-once"
    if re.search(r"(the idea is only useful once .+)$", cleaned, flags=re.IGNORECASE):
        return "directive-once"
    if re.search(r"(the useful version is .+)$", cleaned, flags=re.IGNORECASE):
        return "directive-once"
    return "plain"


def structure_family(structure: str) -> str:
    if structure.startswith("contrast"):
        return "contrast"
    if structure.startswith("boundary"):
        return "boundary"
    if structure.startswith("directive"):
        return "directive"
    if structure.startswith("cascade"):
        return "warning"
    if structure.startswith("timing"):
        return "timing"
    if structure.startswith("trend"):
        return "trend"
    return structure


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
    elif structure == "directive-once":
        contrast_strength += 1.8
        overall += 0.8
    elif structure == "cascade-warning":
        contrast_strength += 2.1
        authority += 0.7
        overall += 0.9
    elif structure == "timing-gap":
        contrast_strength += 2.2
        authority += 0.8
        overall += 1.0
    elif structure == "trend-compounding":
        contrast_strength += 1.9
        authority += 0.6
        overall += 0.8

    structure_markers = STRUCTURE_SIGNAL_MARKERS.get(structure, [])
    structure_hits = sum(1 for marker in structure_markers if marker in lowered)
    if structure_hits:
        authority += min(structure_hits, 2) * 0.4
        specificity += min(structure_hits, 2) * 0.3
        overall += min(structure_hits, 2) * 0.25

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

    if 8 <= len(words) <= 30:
        specificity += 1.0
        overall += 0.4
    elif len(words) > 48:
        specificity -= 0.6
        overall -= 0.3
        warnings.append("sentence is long")
    elif len(words) > 30 and structure == "plain":
        specificity -= 0.3
        overall -= 0.2
        warnings.append("sentence is long")
    elif len(words) > 30 and structure != "plain":
        specificity += 0.2

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
        source_family = structure_family(source_structure)
        output_family = structure_family(output_structure)
        structure_preserved = source_structure in {"none", "plain"} or source_family == output_family
        expression_delta = round_score(output["overall"] - source["overall"])

        warnings: list[str] = []
        if source_family == "contrast" and not structure_preserved:
            warnings.append("rewrite lost source contrast structure")
        if source_family == "boundary" and not structure_preserved:
            warnings.append("rewrite weakened source boundary framing")
        if source_family == "directive" and not structure_preserved:
            warnings.append("rewrite weakened source directive framing")
        if source_family == "warning" and not structure_preserved:
            warnings.append("rewrite weakened source warning structure")
        if source_family == "timing" and not structure_preserved:
            warnings.append("rewrite lost source timing structure")
        if source_family == "trend" and not structure_preserved:
            warnings.append("rewrite flattened source trend structure")
        if expression_delta < -0.5:
            warnings.append("rewrite weakened source expression")
        if overlap > 0.92:
            warnings.append("rewrite remains too close to source")

        adjusted_output_quality = output["overall"]
        if expression_delta < 0:
            adjusted_output_quality = round_score(clamp(adjusted_output_quality + expression_delta, 1.0, 10.0))
        if overlap > 0.92:
            adjusted_output_quality = round_score(clamp(adjusted_output_quality - 1.5, 1.0, 10.0))
        if source_family in {"contrast", "boundary", "directive", "warning", "timing", "trend"} and not structure_preserved:
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
                item["structure_preserved"] and item["source_structure"] not in {"none", "plain"},
                item["adjusted_output_quality"],
                -item["overlap_ratio"],
            ),
            reverse=True,
        )
        return assessed[0]


social_expression_engine = SocialExpressionEngine()
