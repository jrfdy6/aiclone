from __future__ import annotations

import re
from typing import Any

from app.services.social_expression_engine import analyze_expression, structure_family


_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "into",
    "over",
    "under",
    "they",
    "them",
    "their",
    "have",
    "has",
    "had",
    "more",
    "than",
    "what",
    "when",
    "where",
    "which",
    "about",
    "after",
    "before",
    "because",
    "while",
    "would",
    "could",
    "should",
    "your",
    "you",
    "just",
    "only",
    "still",
    "usually",
}

_STANCE_COUNTERWEIGHT_PATTERNS: list[tuple[list[str], str]] = [
    (
        ["what compounds is", "stops being the moat", "distribution", "user trust", "moat"],
        "The article is separating the visible product race from the deeper compounding layer underneath it.",
    ),
    (
        ["interface", "infrastructure", "background layer", "built on top of"],
        "The article is separating the interface moment from the infrastructure shift underneath it.",
    ),
    (
        ["jobs", "workforce", "automated", "reconfigured", "white collar", "disappear faster"],
        "The article is separating workforce transition from total-collapse storytelling.",
    ),
    (
        ["education", "degree", "skills", "relevance", "affordability", "students are actually entering"],
        "The article is separating prestige signaling from relevance, affordability, and durable skill formation.",
    ),
    (
        ["regulation", "governance", "rules", "policy", "fear-driven", "blanket"],
        "The article is separating adaptive governance from blanket rules that do not match the system.",
    ),
    (
        ["ownership", "ip", "asset", "margin", "customer relationship", "commercial space"],
        "The article is separating inspiration from leverage and asking who actually owns the asset.",
    ),
    (
        ["adoption", "makes their life easier", "leadership tells them", "announcement", "repeatable"],
        "The article is separating announcement from adoption and symbolic agreement from real use.",
    ),
    (
        ["design", "governance problem", "law of physics", "companion", "safety"],
        "The article is separating design choices from inevitability language.",
    ),
    (
        ["visible", "underlying", "handoff", "decision rules", "one layer lower", "real issue"],
        "The article is redirecting the reader from the visible headline toward the underlying operating system.",
    ),
]


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _clean_sentence(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    return normalized[:-1] if normalized.endswith(".") else normalized


def _ensure_period(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if part.strip()]


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    for needle in needles:
        token = needle.lower()
        if token in lowered:
            return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        normalized = _normalize_inline_text(value)
        lowered = normalized.lower()
        if not normalized or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
    return cleaned


def _keyword_terms(text: str, *, limit: int = 12) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower()):
        if token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        results.append(token)
        if len(results) >= limit:
            break
    return results


def _match_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def _build_article_stance_packet(
    *,
    combined: str,
    article_kind: str,
    article_stance: str,
    source_expression: str,
    source_expression_text: str,
) -> tuple[float, str, str, list[str]]:
    lowered = combined.lower()
    evidence: list[str] = []
    counterweight = ""

    for terms, summary in _STANCE_COUNTERWEIGHT_PATTERNS:
        matched = _match_terms(lowered, terms)
        if matched:
            evidence.extend(matched[:2])
            if not counterweight:
                counterweight = summary

    if source_expression_text:
        evidence.append(source_expression_text)

    evidence = _dedupe(evidence)[:4]

    stance_reason_map = {
        "nuance": "The article is not just naming the topic. It is redirecting attention toward the hidden variable underneath the headline.",
        "advocate": "The article is pushing the reader toward a concrete operating move, not just describing the landscape.",
        "warn": "The article is using risk language to move the reader from surface observation toward downstream failure modes.",
        "speculate": "The article is reading the current signal as part of a bigger shift and asking the reader to reinterpret the category.",
        "translate": "The article is translating a surface observation into an operator lesson about how the system actually behaves.",
    }
    stance_reason = stance_reason_map.get(article_stance, stance_reason_map["translate"])

    confidence = 7.2 if article_stance == "translate" else 7.8
    if source_expression not in {"none", "plain"}:
        confidence += 0.4
    if counterweight:
        confidence += 0.3
    if evidence:
        confidence += min(len(evidence), 3) * 0.15
    if article_kind in {"trend", "warning", "operator_lesson"}:
        confidence += 0.2

    return min(confidence, 9.2), stance_reason, counterweight, evidence


class SocialArticleUnderstandingService:
    def analyze(self, signal: dict[str, Any], lane_id: str) -> dict[str, Any]:
        title = _normalize_inline_text(signal.get("title"))
        summary = _normalize_inline_text(signal.get("summary"))
        core_claim = _normalize_inline_text(signal.get("core_claim"))
        supporting_claims = [_normalize_inline_text(item) for item in (signal.get("supporting_claims") or []) if _normalize_inline_text(item)]
        raw_text = _normalize_inline_text(signal.get("raw_text"))
        why_it_matters = _normalize_inline_text(signal.get("why_it_matters"))
        role_alignment = _normalize_inline_text(signal.get("role_alignment"))
        topic_tags = [str(item) for item in (signal.get("topic_tags") or []) if str(item).strip()]

        combined = " ".join([title, summary, core_claim, " ".join(supporting_claims), raw_text[:1800], why_it_matters]).strip()
        thesis = core_claim or summary or title

        domains: list[str] = []
        if _contains_any(combined, ["ai", "agent", "model", "llm", "prompt", "automation"]):
            domains.append("ai")
        if _contains_any(combined, ["education", "higher ed", "student", "school", "college", "faculty"]):
            domains.append("education")
        if _contains_any(combined, ["admissions", "enrollment", "student journey", "prospect", "family"]):
            domains.append("admissions")
        if _contains_any(combined, ["leadership", "leader", "team", "manager", "culture", "accountability"]):
            domains.append("leadership")
        if _contains_any(combined, ["builder", "founder", "distribution", "product", "market", "customer"]):
            domains.append("entrepreneurship")
        if _contains_any(combined, ["workflow", "handoff", "ownership", "cadence", "operations", "execution", "process"]):
            domains.append("ops")
        if not domains and lane_id:
            domains.append(lane_id)
        domains = _dedupe(domains)

        if _contains_any(combined, ["senate", "passes bill", "law", "lawsuit", "court", "government"]):
            article_kind = "news"
        elif _contains_any(combined, ["becoming", "trend", "future", "moat", "era"]):
            article_kind = "trend"
        elif _contains_any(combined, ["fails", "risk", "warning", "pressure", "harder questions", "breaks"]):
            article_kind = "warning"
        elif _contains_any(combined, ["lesson", "move", "pattern", "real issue", "real gap"]):
            article_kind = "operator_lesson"
        else:
            article_kind = "analysis"

        if _contains_any(combined, ["but", "however", "missing piece", "one layer lower", "deeper issue", "not enough"]):
            article_stance = "nuance"
        elif _contains_any(combined, ["should", "must", "need to", "the job is", "the point is", "the move is"]):
            article_stance = "advocate"
        elif _contains_any(combined, ["fails", "warning", "risk", "pressure", "harder questions", "cut", "cuts"]):
            article_stance = "warn"
        elif _contains_any(combined, ["trend", "becoming", "shifting", "emerging"]):
            article_stance = "speculate"
        else:
            article_stance = "translate"

        expression_inputs = _dedupe(
            [
                *supporting_claims[:3],
                summary,
                core_claim,
                *_split_sentences(raw_text)[:4],
            ]
        )
        expression_packets = [analyze_expression(item) for item in expression_inputs if _normalize_inline_text(item)]
        expression_packets.sort(
            key=lambda packet: (
                packet.get("structure") not in {"none", "plain"},
                float(packet.get("overall") or 0.0),
                float(packet.get("contrast_strength") or 0.0),
            ),
            reverse=True,
        )
        best_expression = expression_packets[0] if expression_packets else {}
        source_expression = str(best_expression.get("structure") or "plain")
        if source_expression in {"none", ""}:
            source_expression = "plain"
        if source_expression == "plain":
            if re.search(r"\bnot\b.+\bbut\b", combined.lower()):
                source_expression = "contrast"
            elif _contains_any(combined, ["if you want", "start with", "the job is", "the move is", "should"]):
                source_expression = "directive"
            elif _contains_any(combined, ["i learned", "i have seen", "personally", "my experience", "familiar"]):
                source_expression = "story"
            elif _contains_any(combined, ["instead", "rather than", "one layer lower"]):
                source_expression = "boundary"
        source_expression_quality = float(best_expression.get("overall") or (6.4 if source_expression != "plain" else 5.5))
        source_expression_text = _normalize_inline_text(best_expression.get("text"))
        source_expression_family = structure_family(source_expression)

        if "ai" in domains:
            world_context = "This sits inside the shift from tool access toward workflow design, evaluation, and operator judgment."
        elif "admissions" in domains:
            world_context = "This sits inside the trust, clarity, and student-journey pressure that admissions teams hear before the rest of the institution catches up."
        elif "education" in domains:
            world_context = "This sits inside the higher-ed pressure cycle where policy, staffing, trust, and delivery questions eventually reach students and families."
        elif "leadership" in domains:
            world_context = "This sits inside the leadership problem of turning a pattern into standards, coaching, and repeatable team behavior."
        elif "entrepreneurship" in domains:
            world_context = "This sits inside the founder/operator problem of turning repeated market signal into a compounding system."
        elif "ops" in domains:
            world_context = "This sits inside the delivery layer where ownership, handoffs, process, and follow-through decide whether the idea survives."
        else:
            world_context = "This sits inside a real operating environment, not only an abstract idea space."

        stakes = why_it_matters
        if not stakes:
            if article_kind == "news":
                stakes = "The article is describing a live shift with downstream effects on trust, execution, and decision-making."
            elif article_kind == "warning":
                stakes = "The article is pointing at a failure mode that will surface in the real work if teams ignore it."
            else:
                stakes = "The article matters because it changes how the work should be understood and responded to in practice."

        seen_before = bool(domains)
        novelty_reason = (
            "shift_signal" if _contains_any(combined, ["becoming", "changing", "different", "new", "before"]) else "recurring_pattern"
        )
        if novelty_reason == "shift_signal":
            article_world_position = "This looks like a familiar domain pattern with a new or changing operating pressure."
        else:
            article_world_position = "This looks like a recurring operating pattern the system should recognize."

        audience_impacted = []
        if "admissions" in domains or "education" in domains:
            audience_impacted.extend(["students", "families", "institutions"])
        if "leadership" in domains or "ops" in domains:
            audience_impacted.extend(["teams", "operators"])
        if "entrepreneurship" in domains or "ai" in domains:
            audience_impacted.extend(["builders", "decision makers"])
        audience_impacted = _dedupe(audience_impacted) or ["operators"]

        article_stance_confidence, article_stance_reason, article_stance_counterweight, article_stance_evidence = (
            _build_article_stance_packet(
                combined=combined,
                article_kind=article_kind,
                article_stance=article_stance,
                source_expression=source_expression,
                source_expression_text=source_expression_text,
            )
        )

        article_view = _ensure_period(" ".join(part for part in [thesis, stakes] if part))
        evidence = _dedupe(
            [
                f"domains={', '.join(domains) or 'unknown'}",
                f"kind={article_kind}",
                f"stance={article_stance}",
                f"expression={source_expression}",
                f"expression_family={source_expression_family}",
                f"terms={', '.join(_keyword_terms(combined))}",
            ]
        )
        if source_expression_text:
            evidence.append(f"source_expression_text={source_expression_text}")

        return {
            "title": title,
            "thesis": _ensure_period(thesis),
            "supporting_claims": [_ensure_period(item) for item in supporting_claims[:3]],
            "topic_tags": topic_tags,
            "primary_domain": domains[0] if domains else lane_id,
            "secondary_domains": domains[1:3],
            "world_domains": domains,
            "article_kind": article_kind,
            "article_stance": article_stance,
            "article_stance_confidence": round(article_stance_confidence, 1),
            "article_stance_reason": _ensure_period(article_stance_reason),
            "article_stance_counterweight": _ensure_period(article_stance_counterweight),
            "article_stance_evidence": article_stance_evidence,
            "source_expression": source_expression,
            "source_expression_family": source_expression_family,
            "source_expression_quality": round(source_expression_quality, 1),
            "source_expression_text": source_expression_text,
            "world_context": _ensure_period(world_context),
            "world_stakes": _ensure_period(stakes),
            "article_world_position": _ensure_period(article_world_position),
            "audience_impacted": audience_impacted,
            "role_alignment": role_alignment or lane_id,
            "seen_before": seen_before,
            "novelty_reason": novelty_reason,
            "article_view": article_view,
            "keyword_terms": _keyword_terms(combined),
            "evidence": evidence,
            "missing_fields": [field for field, value in {
                "thesis": thesis,
                "world_context": world_context,
                "article_stance": article_stance,
                "article_world_position": article_world_position,
            }.items() if not _normalize_inline_text(str(value))],
        }


social_article_understanding_service = SocialArticleUnderstandingService()
