from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from typing import Any

from app.routes import content_generation as content_generation_module


LOCAL_TEMPLATE_PROVIDER = "local_template"
LOCAL_TEMPLATE_MODEL = "local-template-v1"
DETERMINISTIC_QUALITY_GATE_VERSION = "feezie_deterministic_quality_gate/v2"
LOCAL_TEMPLATE_STOCK_LINES = {
    "the prompt is not the system. the workflow is.",
    "the edge comes from clarity, not from piling on more tools.",
    "that lesson showed up in the build before it showed up in the copy.",
    "that sounds smart right up until the handoff breaks.",
    "operator clarity wins.",
    "clarity keeps the advantage.",
    "that is what the build taught us.",
    "that is operator work.",
    "that is the operating model.",
    "that is the part worth carrying forward.",
    "ignore that if you want. the workflow will still expose it.",
}
DIAGNOSIS_CLOSER_PRESCRIPTION_PATTERNS = (
    re.compile(
        r"\b(?:you|we|teams?|leaders?|operators?|reviewers?|organizations?)\s+"
        r"(?:need|needs|should|must|have\s+to|has\s+to)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^(?:so\s+)?(?:start|stop|require|check|verify|make\s+sure|use|build|add|ask|define|set|"
        r"create|keep|treat|look\s+for|watch\s+for)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:operating\s+rule|rule\s+of\s+thumb|checklist|next\s+step|recommendation|call\s+to\s+action)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bi\s+(?:will|shall|plan\s+to|intend\s+to|am\s+going\s+to|['’]ll|['’]m\s+going\s+to)\s+"
        r"(?:add|apply|build|check|confirm|keep|require|review|test|use|verify)\b",
        flags=re.IGNORECASE,
    ),
)
APPLICATION_CAUSAL_RECONSTRUCTION_PATTERNS = (
    re.compile(r"\b(?:root|underlying)\s+cause\b", flags=re.IGNORECASE),
    re.compile(r"\bthis\s+happens\s+because\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:fails?|breaks?|goes\s+wrong|becomes\s+unreliable)\s+because\b", flags=re.IGNORECASE),
    re.compile(
        r"\bthe\s+reason\b.{0,80}\b(?:fail|fails|break|breaks|wrong|thin|unreliable)\b",
        flags=re.IGNORECASE,
    ),
)
APPLICATION_RULE_LEAD_PATTERNS = (
    re.compile(
        r"^(?:do\s+not|don['’]t|never)\s+[a-z][a-z'-]*"
        r"(?:\s+[a-z0-9][a-z0-9'-]*){0,12}\s+(?:before|until|unless|without)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^(?:ask|attach|build|check|clarify|confirm|define|document|keep|make|name|preserve|"
        r"require|review|route|separate|set|show|start|stop|surface|test|treat|use|verify)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^before\b.{1,160},\s*(?:ask|attach|build|check|clarify|confirm|define|document|keep|"
        r"make|name|preserve|require|review|route|separate|set|show|start|stop|surface|test|"
        r"treat|use|verify)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^i\s+(?:always|only)\s+(?:ask|attach|block|build|check|clarify|confirm|define|"
        r"document|keep|make|name|preserve|require|review|route|separate|set|show|start|stop|"
        r"surface|test|treat|use|verify)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^i\s+(?:ask|attach|block|build|check|clarify|confirm|define|document|keep|make|"
        r"name|preserve|require|review|route|separate|set|show|start|stop|surface|test|treat|"
        r"use|verify)\b.{0,160}\b(?:after|before|once|when|until|unless|without|only\s+if)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^i\s+(?:do\s+not|don['’]t|never|will\s+not|won['’]t)\s+[a-z][a-z'-]*"
        r"(?:\s+[a-z0-9][a-z0-9'-]*){0,12}\s+(?:before|until|unless|without)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^i\s+(?:have|use)\s+(?:(?:a|one|this)\s+)?(?:boundary|check|gate|rule|standard|test)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^my\s+(?:boundary|check|gate|rule|standard|test)\s+(?::|is\b)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^before\s+i\b.{1,120},\s+i\s+(?:(?:always|only)\s+)?(?:ask|attach|block|"
        r"build|check|clarify|confirm|define|document|keep|make|name|preserve|require|review|"
        r"route|separate|set|show|start|stop|surface|test|treat|use|verify)\b",
        flags=re.IGNORECASE,
    ),
)

ROLE_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _ensure_sentence(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _primary_claim(brief: dict[str, Any]) -> str:
    return _ensure_sentence(str(brief.get("primary_claim") or ""))


def _proof_evidence(brief: dict[str, Any]) -> str:
    packet = _clean_text(brief.get("proof_packet"))
    if not packet:
        return ""
    if "->" in packet:
        packet = packet.split("->", 1)[1]
    elif ":" in packet:
        left, right = packet.split(":", 1)
        if _clean_text(left).lower() in {"proof", "evidence", "public-facing proof"}:
            packet = right
    return _ensure_sentence(packet)


def _story_sentence(brief: dict[str, Any]) -> str:
    story = _clean_text(brief.get("story_beat"))
    if not story:
        return ""
    return _ensure_sentence(story)


def _public_lane(brief: dict[str, Any]) -> str:
    lane = _clean_text(brief.get("public_lane"))
    if lane:
        return lane
    try:
        option_number = int(brief.get("option_number") or 1)
    except Exception:
        option_number = 1
    return content_generation_module._public_post_lane_for_option(option_number)


def _looks_internal_operator_catalog(text: str) -> bool:
    normalized = _clean_text(text).lower()
    if not normalized:
        return False
    if content_generation_module._looks_like_operator_catalog_sentence(normalized):
        return True
    marker_count = sum(1 for marker in content_generation_module.OPERATOR_CATALOG_MARKERS if marker in normalized)
    return marker_count >= 3


def _sanitize_public_copy(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    cleaned = content_generation_module._rewrite_audience_slug_public_copy(cleaned)
    replacements = (
        (r"\bai clone\s*/\s*brain system\b", "the system"),
        (r"\bpersona soup\b", "raw context"),
        (r"\bproof packets?\b", "proof"),
        (r"\btyped core, proof, story, and example lanes\b", "clear context lanes"),
        (r"\btyped (?:core|proof|story|example|context|support) lanes?\b", "clear context lanes"),
        (r"\btyped lanes?\b", "clear lanes"),
        (r"\bdomain gates?\b", "topic guardrails"),
        (r"\bgreen[- ]or[- ]red board\b", "clear go/no-go check"),
        (r"\bproof lanes?\b", "evidence lanes"),
        (r"\brouted workspace snapshot\b", "shared context"),
        (r"\bdaily briefs\b", "operating rhythm"),
        (r"\bpersona review\b", "editorial review"),
        (r"\blong-form routing\b", "content routing"),
    )
    rewritten = cleaned
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    rewritten = content_generation_module._rewrite_public_system_phrases(rewritten)
    return rewritten


def _public_safe_operator_claim(brief: dict[str, Any], lane: str) -> str:
    raw_claim = _sanitize_public_copy(_primary_claim(brief))
    if raw_claim and not _looks_internal_operator_catalog(raw_claim):
        return raw_claim
    if lane == "market_insight":
        return "AI does not create the edge by itself. Clear operating context does."
    if lane == "build_in_public":
        return "The build made one thing obvious: context has to survive the handoff."
    return "If context dies in the handoff, AI just scales confusion."


def _trim_public_proof(brief: dict[str, Any]) -> str:
    evidence = _sanitize_public_copy(_proof_evidence(brief))
    if not evidence:
        return ""
    lane = _public_lane(brief)
    if _looks_internal_operator_catalog(evidence):
        if lane == "market_insight":
            return "The gains showed up when the workflow, handoff rules, and proof standard got clearer, not when more tooling was layered on."
        if lane == "build_in_public":
            return "Once the workflow carried context cleanly from one step to the next, the system became easier to trust."
        return "Clearer handoffs and clearer proof rules made the workflow more reliable."
    clauses = [segment.strip(" .") for segment in re.split(r"[;]", evidence) if segment.strip()]
    if not clauses:
        return _ensure_sentence(evidence)
    selected: list[str] = []
    metric_added = 0
    for clause in clauses:
        metric_count = len(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", clause))
        if metric_count > 0:
            if metric_added >= 1:
                continue
            metric_added += 1
        selected.append(clause)
        if len(selected) >= 2:
            break
    compact = ". ".join(selected) if selected else clauses[0]
    return _ensure_sentence(compact)


def _bridge_line(mode: str) -> str:
    return {
        "operator_lesson": "The prompt is not the system. The workflow is.",
        "contrarian_reframe": "That sounds smart right up until the workflow slips.",
        "agree_and_extend": "Agreement is easy. Operational follow-through is harder.",
        "drama_tension": "That is where the friction usually shows up.",
        "story_with_payoff": "The lesson only counts if the work changed because of it.",
        "recognition": "That kind of signal is worth naming out loud.",
        "warning": "If that stays fuzzy, the output will drift.",
        "reframe": "That is the difference between sounding prepared and being operationally ready.",
    }.get(mode, "The workflow tells the truth faster than the prompt does.")


def _closing_line(mode: str) -> str:
    return {
        "operator_lesson": "The workflow still has to hold.",
        "contrarian_reframe": "Clarity has to come first.",
        "agree_and_extend": "Clarity is the part that scales.",
        "drama_tension": "That is when the work starts slipping.",
        "story_with_payoff": "That changed how the work ran.",
        "recognition": "That deserves more credit than it gets.",
        "warning": "Ignore that if you want. The workflow will still expose it.",
        "reframe": "The workflow still tells the truth.",
    }.get(mode, "Clarity has to come first.")


def _compose_option(brief: dict[str, Any]) -> str:
    mode = _clean_text(brief.get("framing_mode")) or "operator_lesson"
    lane = _public_lane(brief)
    claim = _ensure_sentence(_public_safe_operator_claim(brief, lane))
    proof = _trim_public_proof(brief)
    story = _ensure_sentence(_sanitize_public_copy(_story_sentence(brief)))
    if re.search(r"\bquiet inefficiency cleanup\b", story, flags=re.IGNORECASE):
        story = "The lesson came from cleaning up quiet workflow friction." if lane == "build_in_public" else ""

    paragraphs: list[str] = []
    if claim:
        paragraphs.append(claim)
    bridge_line = _bridge_line(mode)
    if lane == "market_insight":
        bridge_line = "The edge comes from clarity, not from piling on more tools."
    elif lane == "build_in_public":
        bridge_line = "That lesson showed up in the build before it showed up in the copy."
    bridge = _ensure_sentence(bridge_line)
    if bridge and bridge.lower() not in claim.lower():
        paragraphs.append(bridge)
    if proof:
        paragraphs.append(proof)
    if story:
        paragraphs.append(story)
    closing_line = _closing_line(mode)
    if lane == "market_insight":
        closing_line = "Clarity keeps the advantage."
    elif lane == "operator_lesson":
        closing_line = "Operator clarity wins."
    elif lane == "build_in_public":
        closing_line = "That is what the build taught us."
    closing = _ensure_sentence(closing_line)
    if closing:
        paragraphs.append(closing)
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _public_replacement_line(lane: str) -> str:
    if lane == "market_insight":
        return "Clarity changed the operating edge."
    if lane == "build_in_public":
        return "The build only improved once context stopped getting lost."
    return "Context has to survive the handoff."


def _sanitize_public_option(option: str, lane: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    revised: list[str] = []
    inserted_replacement = False
    replacement_line = _public_replacement_line(lane)
    for paragraph in paragraphs:
        sentences = [content_generation_module._ensure_sentence(sentence.strip()) for sentence in content_generation_module._split_sentences(paragraph) if sentence.strip()]
        kept: list[str] = []
        for sentence in sentences:
            normalized = _sanitize_public_copy(sentence)
            if " ".join(normalized.lower().split()) in content_generation_module.HOUSE_SCAFFOLD_SENTENCES:
                continue
            if _looks_internal_operator_catalog(normalized) or content_generation_module._internal_public_jargon_hits(normalized):
                if not inserted_replacement:
                    kept.append(replacement_line)
                    inserted_replacement = True
                continue
            kept.append(normalized)
        if kept:
            revised.append(" ".join(kept).strip())
    return "\n\n".join(paragraph for paragraph in revised if paragraph)


def _looks_like_label_paragraph(paragraph: str) -> bool:
    normalized = _clean_text(paragraph).strip(".")
    if not normalized:
        return False
    if content_generation_module._phrase_is_flat_label(normalized):
        return True
    if len(normalized.split()) > 5:
        return False
    if re.search(r"\b(?:is|are|was|were|be|am|do|does|did|have|has|had|will|can|should|could|would|not)\b", normalized, flags=re.IGNORECASE):
        return False
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    if not words:
        return False
    if not all(word[:1].isupper() or word.isupper() for word in words):
        return False
    return True


def _stock_template_hit_count(option: str) -> int:
    hits = 0
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    for paragraph in paragraphs:
        normalized_paragraph = _clean_text(paragraph).lower()
        if normalized_paragraph in LOCAL_TEMPLATE_STOCK_LINES:
            hits += 1
            continue
        for sentence in content_generation_module._split_sentences(paragraph):
            normalized_sentence = _clean_text(sentence).lower()
            if normalized_sentence in LOCAL_TEMPLATE_STOCK_LINES:
                hits += 1
    return hits


def _normalized_role_text(value: Any) -> str:
    return " ".join(token.lower().replace("’", "'") for token in ROLE_WORD_RE.findall(str(value or "")))


def _significant_role_terms(value: Any) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", _normalized_role_text(value))
        if len(token) > 2 and token not in content_generation_module.STOPWORDS
    ]


def _assigned_anchor_values(value: Any) -> list[str]:
    if value in (None, "", [], (), set()):
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]
    return list(
        dict.fromkeys(
            _clean_text(item)
            for item in raw_values
            if _clean_text(item)
        )
    )


def _assigned_anchor_is_present(text: str, anchor: str) -> bool:
    normalized_text = _normalized_role_text(text)
    normalized_anchor = _normalized_role_text(anchor)
    if not normalized_text or not normalized_anchor:
        return False
    if normalized_anchor in normalized_text:
        return True
    anchor_terms = set(_significant_role_terms(anchor))
    text_terms = set(_significant_role_terms(text))
    if not anchor_terms:
        return False
    required = 1 if len(anchor_terms) == 1 else 2
    return len(anchor_terms.intersection(text_terms)) >= required


def _bound_role_anchor_terms(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    normalized = [
        str(item or "").strip().lower()
        for item in value
        if str(item or "").strip()
    ]
    if (
        len(normalized) != 2
        or len(set(normalized)) != 2
        or any(not re.fullmatch(r"[a-z][a-z0-9]*", token) for token in normalized)
    ):
        return []
    return normalized


def _bound_role_anchors_are_present(text: str, anchors: list[str]) -> bool:
    normalized_text = _normalized_role_text(text)
    return bool(anchors) and all(
        re.search(rf"\b{re.escape(anchor)}\b", normalized_text, flags=re.IGNORECASE)
        for anchor in anchors
    )


def _structured_application_rule_parts(value: Any) -> dict[str, str]:
    parts: dict[str, str] = {}
    for segment in str(value or "").split("|"):
        if ":" not in segment:
            continue
        label, raw_value = segment.split(":", 1)
        normalized_label = " ".join(label.lower().replace("_", " ").split())
        cleaned_value = _clean_text(raw_value)
        if normalized_label in {
            "decision action",
            "decision object",
            "boundary",
            "rule posture",
        } and cleaned_value:
            parts[normalized_label] = cleaned_value
    return parts


def _role_term_families(terms: set[str]) -> set[str]:
    """Return conservative inflection families for semantic role matching."""

    families = set(terms)
    for term in terms:
        if len(term) > 4 and term.endswith("ies"):
            families.add(term[:-3] + "y")
        elif len(term) > 4 and term.endswith("s") and not term.endswith("ss"):
            families.add(term[:-1])
        if len(term) > 5 and term.endswith("ed"):
            families.add(term[:-2])
            families.add(term[:-1])
        if len(term) > 5 and term.endswith("ing"):
            families.add(term[:-3])
            families.add(term[:-3] + "e")
        if len(term) > 5 and term.endswith("ly"):
            families.add(term[:-2])
    return families


def _role_terms_overlap(left: set[str], right: set[str]) -> bool:
    return bool(_role_term_families(left).intersection(_role_term_families(right)))


def _assigned_application_rule_is_present(opening: str, basis: str) -> bool:
    parts = _structured_application_rule_parts(basis)
    required_parts = {"decision action", "decision object", "boundary"}
    if not required_parts.issubset(parts):
        return _assigned_anchor_is_present(opening, basis)
    opening_terms = set(_significant_role_terms(opening))
    action_terms = set(_significant_role_terms(parts["decision action"]))
    object_terms = set(_significant_role_terms(parts["decision object"]))
    boundary_terms = set(_significant_role_terms(parts["boundary"])) - {
        "before",
        "reliance",
        "visible",
    }
    relation_present = bool(
        re.search(r"\b(?:after|before|once|only\s+if|unless|until|when|without)\b", opening, flags=re.IGNORECASE)
    )
    return bool(
        _role_terms_overlap(action_terms, opening_terms)
        and _role_terms_overlap(object_terms, opening_terms)
        and (not boundary_terms or _role_terms_overlap(boundary_terms, opening_terms))
        and relation_present
    )


def _assigned_application_boundary_is_present(closing: str, basis: str) -> bool:
    """Require a compact next-step payoff without restating the whole opening."""

    parts = _structured_application_rule_parts(basis)
    if not {"decision action", "decision object", "boundary"}.issubset(parts):
        return False
    closing_terms = set(_significant_role_terms(closing))
    boundary_terms = set(_significant_role_terms(parts["boundary"]))
    object_terms = set(_significant_role_terms(parts["decision object"]))
    boundary_present = bool(boundary_terms.intersection(closing_terms))
    object_present = bool(object_terms.intersection(closing_terms))
    action = parts["decision action"].lower()
    action_noun_present = bool(
        action == "check" and re.search(r"\bchecks?\b", closing, flags=re.IGNORECASE)
    )
    return boundary_present and (object_present or action_noun_present)


def _opening_restates_primary_claim(opening: str, claim: str) -> bool:
    normalized_opening = _normalized_role_text(opening)
    normalized_claim = _normalized_role_text(claim)
    if not normalized_opening or not normalized_claim:
        return False
    if normalized_opening == normalized_claim:
        return True
    length_ratio = min(len(normalized_opening), len(normalized_claim)) / max(
        len(normalized_opening),
        len(normalized_claim),
    )
    if length_ratio >= 0.65 and SequenceMatcher(None, normalized_opening, normalized_claim).ratio() >= 0.86:
        return True
    opening_terms = set(_significant_role_terms(opening))
    claim_terms = set(_significant_role_terms(claim))
    shared_count = len(opening_terms.intersection(claim_terms))
    shorter_count = min(len(opening_terms), len(claim_terms))
    containment = shared_count / shorter_count if shorter_count else 0.0
    return length_ratio >= 0.55 and shared_count >= 5 and containment >= 0.80


def _substantial_role_restatement(left: str, right: str) -> bool:
    normalized_left = _normalized_role_text(left)
    normalized_right = _normalized_role_text(right)
    if not normalized_left or not normalized_right:
        return False
    if normalized_left == normalized_right:
        return True
    length_ratio = min(len(normalized_left), len(normalized_right)) / max(
        len(normalized_left),
        len(normalized_right),
    )
    if length_ratio >= 0.65 and SequenceMatcher(None, normalized_left, normalized_right).ratio() >= 0.82:
        return True
    left_terms = set(_significant_role_terms(left))
    right_terms = set(_significant_role_terms(right))
    shared_count = len(left_terms.intersection(right_terms))
    shorter_count = min(len(left_terms), len(right_terms))
    return bool(shorter_count and shared_count >= 3 and shared_count / shorter_count >= 0.80)


def _brief_has_approved_proof(brief: content_generation_module.ContentOptionBrief) -> bool:
    proof_packet = _clean_text(getattr(brief, "proof_packet", ""))
    if not proof_packet:
        return False
    return not bool(
        re.match(
            r"^no\s+(?:approved\s+|strong\s+)?proof(?:\s+packet)?\b",
            proof_packet,
            flags=re.IGNORECASE,
        )
    )


def _current_structured_role(
    brief: content_generation_module.ContentOptionBrief,
) -> str | None:
    """Classify a current role payload from its mutually exclusive semantic fields."""

    diagnosis_fields = (
        _clean_text(getattr(brief, "mechanism_focus", "")),
        _clean_text(getattr(brief, "recognition_basis", "")),
    )
    application_fields = (
        _clean_text(getattr(brief, "decision_rule_basis", "")),
        _clean_text(getattr(brief, "required_context_concepts", "")),
        _clean_text(getattr(brief, "consequence_basis", "")),
    )
    diagnosis_complete = all(diagnosis_fields)
    application_complete = all(application_fields)
    diagnosis_empty = not any(diagnosis_fields)
    application_empty = not any(application_fields)
    if diagnosis_complete and application_empty:
        return "diagnosis"
    if application_complete and diagnosis_empty:
        return "application"
    return None


def _assigned_role_failure_codes(
    option: str,
    brief: content_generation_module.ContentOptionBrief | None,
) -> list[str]:
    """Fail closed when a draft crosses its deterministic argument-role boundary."""

    if brief is None:
        return []
    treatment = _clean_text(brief.thesis_treatment).lower()
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    opening_line = content_generation_module._first_content_line(option)
    opening_sentences = content_generation_module._split_sentences(opening_line)
    opening = opening_sentences[0] if opening_sentences else opening_line
    closing = paragraphs[-1] if paragraphs else ""
    closing_sentences = content_generation_module._split_sentences(closing)
    closing_word_count = len(re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?", closing))
    closing_shape_invalid = len(closing_sentences) != 1 or not 4 <= closing_word_count <= 10
    role_payload_version = (
        _clean_text(getattr(brief, "semantic_payload_version", ""))
    )
    role_payload_v2 = role_payload_version == "feezie_role_payload/v2"
    role_payload_v3 = role_payload_version == "feezie_role_payload/v3"
    current_role_payload = role_payload_v2 or role_payload_v3
    option_word_count = len(ROLE_WORD_RE.findall(option or ""))
    failures: list[str] = []
    if current_role_payload:
        structured_role = _current_structured_role(brief)
        diagnosis_role = structured_role == "diagnosis"
        application_role = structured_role == "application"
        if structured_role is None:
            failures.append("role_payload_assignment_invalid")
    else:
        # Legacy/unversioned briefs retain the original broad text matching.
        diagnosis_role = "diagnos" in treatment
        application_role = "application" in treatment
    if current_role_payload and not 70 <= option_word_count <= 150:
        failures.append("role_word_count_out_of_contract")
    if _opening_restates_primary_claim(opening, _clean_text(getattr(brief, "primary_claim", ""))):
        failures.append("role_opening_restates_primary_claim")
    if diagnosis_role:
        if closing.endswith("?") or any(
            pattern.search(closing)
            for pattern in DIAGNOSIS_CLOSER_PRESCRIPTION_PATTERNS
        ):
            failures.append("role_d1_diagnostic_closer_prescriptive")
        mechanism_anchors = _assigned_anchor_values(getattr(brief, "mechanism_focus", ""))
        recognition_anchors = _assigned_anchor_values(getattr(brief, "recognition_basis", ""))
        diagnosis_body = "\n\n".join(paragraphs[1:-1]) if len(paragraphs) >= 3 else ""
        diagnosis_body_sentences = content_generation_module._split_sentences(diagnosis_body)
        if current_role_payload and sum(
            len(ROLE_WORD_RE.findall(sentence)) >= 6
            for sentence in diagnosis_body_sentences
        ) < 2:
            failures.append("role_d1_diagnosis_body_underdeveloped")
        bound_mechanism_anchors = _bound_role_anchor_terms(
            getattr(brief, "mechanism_anchor_terms", ())
        )
        bound_recognition_anchors = _bound_role_anchor_terms(
            getattr(brief, "recognition_anchor_terms", ())
        )
        mechanism_anchor_missing = (
            not _bound_role_anchors_are_present(diagnosis_body, bound_mechanism_anchors)
            if role_payload_v3
            else bool(
                mechanism_anchors
                and not all(
                    _assigned_anchor_is_present(diagnosis_body, anchor)
                    for anchor in mechanism_anchors
                )
            )
        )
        if mechanism_anchor_missing:
            failures.append("role_d1_mechanism_anchor_missing")
        recognition_anchor_missing = (
            not _bound_role_anchors_are_present(closing, bound_recognition_anchors)
            if role_payload_v3
            else bool(
                recognition_anchors
                and not all(
                    _assigned_anchor_is_present(closing, anchor)
                    for anchor in recognition_anchors
                )
            )
        )
        if recognition_anchor_missing:
            failures.append("role_d1_recognition_anchor_missing")
    if application_role:
        decision_rule_anchors = _assigned_anchor_values(getattr(brief, "decision_rule_basis", ""))
        structured_rule_parts = (
            _structured_application_rule_parts(decision_rule_anchors[0])
            if len(decision_rule_anchors) == 1
            else {}
        )
        structured_v2_rule = bool(
            current_role_payload
            and {"decision action", "decision object", "boundary", "rule posture"}.issubset(
                structured_rule_parts
            )
        )
        if structured_v2_rule:
            # V2 leads are semantic, not a forced literal template: the first
            # sentence must carry its assigned action, object, usable boundary,
            # and boundary relation together.
            rule_is_leading = _assigned_application_rule_is_present(
                opening, decision_rule_anchors[0]
            )
        else:
            # Broad lead-shape matching is retained only for legacy/unstructured briefs.
            rule_is_leading = any(pattern.search(opening) for pattern in APPLICATION_RULE_LEAD_PATTERNS)
        if not rule_is_leading:
            failures.append("role_a1_application_rule_not_leading")

        proof_facet_id = _clean_text(getattr(brief, "proof_facet_id", ""))
        proof_ready = bool(proof_facet_id) or _brief_has_approved_proof(brief)
        proof_paragraph_index = len(paragraphs) - 2 if proof_ready and len(paragraphs) >= 4 else None
        application_owned_paragraphs = [
            paragraph
            for index, paragraph in enumerate(paragraphs)
            if index != proof_paragraph_index
        ]
        application_owned_text = "\n\n".join(application_owned_paragraphs)
        if any(
            pattern.search(application_owned_text)
            for pattern in APPLICATION_CAUSAL_RECONSTRUCTION_PATTERNS
        ):
            failures.append("role_a1_application_reconstructs_cause")
        if proof_ready:
            application_body_paragraphs = paragraphs[1:-2] if len(paragraphs) >= 3 else []
        else:
            application_body_paragraphs = paragraphs[1:-1]
        application_argument = "\n\n".join(
            application_body_paragraphs + ([closing] if closing else [])
        )
        primary_claim = _clean_text(getattr(brief, "primary_claim", ""))
        if primary_claim and any(
            _opening_restates_primary_claim(sentence, primary_claim)
            for sentence in content_generation_module._split_sentences(application_argument)
        ):
            failures.append("role_a1_primary_claim_reconstruction")
        if (
            not structured_v2_rule
            and decision_rule_anchors
            and not all(
                _assigned_application_rule_is_present(opening, anchor)
                for anchor in decision_rule_anchors
            )
        ):
            failures.append("role_a1_decision_rule_anchor_missing")

        application_body = "\n\n".join(application_body_paragraphs)
        body_sentences = content_generation_module._split_sentences(application_body)
        substantive_body_sentence_count = sum(
            len(ROLE_WORD_RE.findall(sentence)) >= 6
            for sentence in body_sentences
        )
        consequence_anchors = _assigned_anchor_values(getattr(brief, "consequence_basis", ""))
        consequence_missing = bool(
            consequence_anchors
            and not all(
                _assigned_anchor_is_present(application_body, anchor)
                for anchor in consequence_anchors
            )
        )
        if substantive_body_sentence_count < 2 or consequence_missing:
            failures.append("role_a1_application_body_underdeveloped")

        context_anchors = _assigned_anchor_values(getattr(brief, "required_context_concepts", ()))
        if context_anchors and not all(
            _assigned_anchor_is_present(application_body, anchor)
            for anchor in context_anchors
        ):
            failures.append("role_a1_required_context_anchor_missing")

        if proof_ready:
            proof_packet = _clean_text(getattr(brief, "proof_packet", ""))
            penultimate = paragraphs[-2] if len(paragraphs) >= 4 else ""
            proof_is_separate = bool(
                penultimate
                and content_generation_module.option_mentions_approved_proof(
                    penultimate,
                    [proof_packet],
                )
            )
            if not proof_is_separate:
                failures.append("role_a1_proof_validation_not_separate")

        if _substantial_role_restatement(opening, closing):
            failures.append("role_a1_closer_restates_opening")
        if (
            structured_v2_rule
            and structured_rule_parts.get("rule posture", "").lower().rstrip(".!?")
            == "owner-confirmed next step"
            and not _assigned_application_boundary_is_present(
                closing,
                decision_rule_anchors[0],
            )
        ):
            failures.append("role_a1_next_step_boundary_missing")
    if (diagnosis_role or application_role) and closing_shape_invalid:
        failures.append("role_closer_length_out_of_contract")
    return list(dict.fromkeys(failures))


def _opening_signature(option: str) -> str:
    first_line = content_generation_module._first_content_line(option).lower()
    terms = [
        token
        for token in re.findall(r"[a-z0-9]+", first_line)
        if token not in content_generation_module.STOPWORDS and token not in {"ai", "an"}
    ]
    return " ".join(terms[:4]).strip()


def _expected_option_count(context_packet: dict[str, Any]) -> int:
    contract = context_packet.get("draft_contract")
    if isinstance(contract, dict):
        raw_count = contract.get("required_option_count")
    else:
        raw_count = None
    if raw_count in (None, ""):
        raw_count = context_packet.get("expected_option_count")
    if raw_count in (None, ""):
        briefs = context_packet.get("planned_option_briefs")
        raw_count = len(briefs) if isinstance(briefs, list) and briefs else 3
    try:
        return max(1, min(10, int(raw_count)))
    except (TypeError, ValueError):
        return 3


def _independent_critic_required(context_packet: dict[str, Any]) -> bool:
    contract = context_packet.get("draft_contract")
    return bool(
        isinstance(contract, dict)
        and contract.get("independent_critic_required") is True
    )


def _normalized_draft_text(option: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(option or "").lower()))


def _draft_terms(option: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", str(option or "").lower())
        if len(token) > 2 and token not in content_generation_module.STOPWORDS
    ]


def _draft_shingles(tokens: list[str], *, size: int = 3) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def evaluate_draft_distinctness(context_packet: dict[str, Any], options: list[str]) -> dict[str, Any]:
    """Return a bounded receipt proving that the queued drafts are not cosmetic variants."""

    expected_count = _expected_option_count(context_packet)
    cleaned_options = [str(option).strip() for option in options if isinstance(option, str) and str(option).strip()]
    failed_reasons: list[str] = []
    if len(cleaned_options) != expected_count:
        failed_reasons.append(f"option_count_mismatch:{len(cleaned_options)}:{expected_count}")
    for index, option in enumerate(cleaned_options, start=1):
        if len(option) < 20:
            failed_reasons.append(f"option_{index}_incomplete")

    briefs = [item for item in (context_packet.get("planned_option_briefs") or []) if isinstance(item, dict)]
    draft_contract = context_packet.get("draft_contract")
    meaningful_difference_required = bool(
        isinstance(draft_contract, dict)
        and draft_contract.get("meaningful_difference_required") is True
    )
    if meaningful_difference_required:
        if len(briefs) < expected_count:
            failed_reasons.append(f"planned_brief_count_mismatch:{len(briefs)}:{expected_count}")
        else:
            for axis in ("thesis_treatment", "proof_progression", "payoff"):
                values = [
                    _normalized_draft_text(str(brief.get(axis) or ""))
                    for brief in briefs[:expected_count]
                ]
                for index, value in enumerate(values, start=1):
                    if not value:
                        failed_reasons.append(f"option_{index}_planned_{axis}_missing")
                populated = [value for value in values if value]
                if len(populated) == expected_count and len(set(populated)) != expected_count:
                    failed_reasons.append(f"planned_{axis}_not_distinct")
            if expected_count == 2:
                required_role_fields = {
                    0: ("mechanism_focus", "recognition_basis"),
                    1: ("decision_rule_basis", "required_context_concepts", "consequence_basis"),
                }
                for brief_index, fields in required_role_fields.items():
                    for field in fields:
                        if not _clean_text(briefs[brief_index].get(field)):
                            failed_reasons.append(
                                f"option_{brief_index + 1}_planned_{field}_missing"
                            )
                diagnosis_focus = _normalized_role_text(briefs[0].get("mechanism_focus"))
                application_focus = _normalized_role_text(briefs[1].get("decision_rule_basis"))
                if diagnosis_focus and diagnosis_focus == application_focus:
                    failed_reasons.append("planned_role_payloads_not_distinct")
                if application_focus and (
                    not re.search(r"\b(?:before|until|unless|without|only if)\b", application_focus)
                    or not re.search(
                        r"\b(?:accept|advance|approve|check|gate|require|review|rule|test|use|verify)\b",
                        application_focus,
                    )
                ):
                    failed_reasons.append("planned_application_decision_gate_missing")
                proof_inventory = {
                    _normalized_role_text(packet)
                    for packet in (context_packet.get("proof_packets") or [])
                    if _normalized_role_text(packet)
                }
                assigned_facets = {
                    _clean_text(brief.get("proof_facet_id")).lower()
                    for brief in briefs[:2]
                    if _clean_text(brief.get("proof_facet_id"))
                }
                if len(proof_inventory) > 1 and len(assigned_facets) < 2:
                    failed_reasons.append("planned_proof_facets_not_distinct")
    if expected_count > 1 and len(briefs) >= expected_count:
        planned_treatments = {
            (
                _clean_text(brief.get("framing_mode")).lower(),
                _clean_text(brief.get("public_lane")).lower(),
                _normalized_draft_text(str(brief.get("primary_claim") or "")),
                _normalized_draft_text(str(brief.get("proof_packet") or "")),
                _normalized_draft_text(str(brief.get("story_beat") or "")),
                _normalized_draft_text(str(brief.get("thesis_treatment") or "")),
                _normalized_draft_text(str(brief.get("proof_progression") or "")),
                _normalized_draft_text(str(brief.get("payoff") or "")),
            )
            for brief in briefs[:expected_count]
        }
        if len(planned_treatments) != expected_count:
            failed_reasons.append("planned_treatments_not_distinct")

    pair_receipts: list[dict[str, Any]] = []
    for left_index in range(len(cleaned_options)):
        for right_index in range(left_index + 1, len(cleaned_options)):
            left = cleaned_options[left_index]
            right = cleaned_options[right_index]
            left_normalized = _normalized_draft_text(left)
            right_normalized = _normalized_draft_text(right)
            left_terms = _draft_terms(left)
            right_terms = _draft_terms(right)
            left_term_set = set(left_terms)
            right_term_set = set(right_terms)
            intersection = len(left_term_set.intersection(right_term_set))
            smaller_term_count = min(len(left_term_set), len(right_term_set))
            term_containment = intersection / smaller_term_count if smaller_term_count else 0.0
            left_shingles = _draft_shingles(left_terms)
            right_shingles = _draft_shingles(right_terms)
            shingle_union = left_shingles.union(right_shingles)
            shingle_jaccard = (
                len(left_shingles.intersection(right_shingles)) / len(shingle_union)
                if shingle_union
                else 0.0
            )
            sequence_similarity = SequenceMatcher(None, left_normalized, right_normalized).ratio()
            left_hook = _normalized_draft_text(content_generation_module._first_content_line(left))
            right_hook = _normalized_draft_text(content_generation_module._first_content_line(right))
            opening_signatures_match = bool(
                _opening_signature(left)
                and _opening_signature(left) == _opening_signature(right)
            )
            pair_failures: list[str] = []
            if left_normalized == right_normalized:
                pair_failures.append("identical_drafts")
            if left_hook and left_hook == right_hook:
                pair_failures.append("same_hook")
            elif opening_signatures_match:
                pair_failures.append("opening_mechanism_repeated")
            if sequence_similarity >= 0.88:
                pair_failures.append("sequence_too_similar")
            if term_containment >= 0.92:
                pair_failures.append("thesis_vocabulary_too_similar")
            if shingle_jaccard >= 0.72:
                pair_failures.append("body_progression_too_similar")
            pair_label = f"option_{left_index + 1}_vs_{right_index + 1}"
            failed_reasons.extend(f"{pair_label}:{reason}" for reason in pair_failures)
            pair_receipts.append(
                {
                    "left_option_index": left_index + 1,
                    "right_option_index": right_index + 1,
                    "sequence_similarity": round(sequence_similarity, 4),
                    "term_containment": round(term_containment, 4),
                    "shingle_jaccard": round(shingle_jaccard, 4),
                    "opening_signatures_match": opening_signatures_match,
                    "passed": not pair_failures,
                    "failed_reasons": pair_failures,
                }
            )

    return {
        "schema_version": "feezie_draft_distinctness/v1",
        "passed": not failed_reasons,
        "required_option_count": expected_count,
        "actual_option_count": len(cleaned_options),
        "failed_reasons": failed_reasons,
        "pairs": pair_receipts,
    }


def _starts_with_persona_bio(option: str) -> bool:
    first_line = content_generation_module._first_content_line(option)
    return bool(re.match(r"^owner\b", first_line, flags=re.IGNORECASE))


STUDENT_SCIENTIST_ACTION_RE = re.compile(
    r"\bi\s+(?:added|audited|built|changed|compared|configured|connected|created|debugged|decided|deployed|"
    r"designed|documented|fixed|implemented|integrated|introduced|mapped|measured|moved|ran|rebuilt|"
    r"refactored|removed|replaced|reviewed|rewired|rewrote|set\s+up|shipped|started|stopped|tested|traced|turned)\b",
    flags=re.IGNORECASE,
)
STUDENT_SCIENTIST_PROBLEM_RE = re.compile(
    r"\b(?:abstract|blocked|broke|broken|conflict|drift|duplicate|empty|failed|failure|generic|inconsistent|"
    r"incorrect|lacked|lost|missing|nonspecific|open-ended|scattered|stale|stuck|unclear|unfinished|unreliable|vague|wrong)\b|"
    r"\bnothing\s+(?:concrete|specific)\b|\b(?:could|did|was|were|would)(?:n['’]t| not)\b",
    flags=re.IGNORECASE,
)
STUDENT_SCIENTIST_OBSERVATION_RE = re.compile(
    r"\b(?:i\s+(?:confirmed|discovered|found|learned|noticed|observed|realized)|became\s+clear|what\s+changed|next\s+test|"
    r"(?:the\s+)?(?:build|draft|output|result|test|checks?|gates?|workflow|system)\s+"
    r"(?:revealed|showed|taught)(?:\s+me)?)\b",
    flags=re.IGNORECASE,
)
STUDENT_SCIENTIST_COMMAND_RE = re.compile(
    r"\b(?:you|leaders?|teams?|builders?|operators?|organizations?)\s+"
    r"(?:must|should|need\s+to|needs\s+to|have\s+to|has\s+to)\b",
    flags=re.IGNORECASE,
)
STUDENT_SCIENTIST_UNIVERSAL_RE = re.compile(
    r"\b(?:always|everyone|every\s+(?:leader|team|builder|operator|organization)|the\s+best|the\s+real\s+systems?)\b",
    flags=re.IGNORECASE,
)
STUDENT_SCIENTIST_UNSUPPORTED_RESULT_RE = re.compile(
    r"\b(?:the|this|that|my|our|a|an|new|added|changed|bounded)?\s*"
    r"(?:change|test|check|gate|fix|workflow|system)\s+"
    r"(?:validated|proved|confirmed|worked|fixed|caught|prevented|blocked|stopped|improved|succeeded)\b",
    flags=re.IGNORECASE,
)


def _student_scientist_evidence_failures(option: str, evidence_contract: dict[str, Any] | None) -> list[str]:
    if not isinstance(evidence_contract, dict):
        return []
    if str(evidence_contract.get("schema_version") or "") != "feezie_publish_ready_evidence/v1":
        return ["student_scientist_contract_invalid"]

    concrete_action = _clean_text(evidence_contract.get("concrete_action"))
    exact_problem = _clean_text(evidence_contract.get("exact_problem"))
    observable_lesson = _clean_text(evidence_contract.get("observable_lesson"))
    if not all((concrete_action, exact_problem, observable_lesson)):
        return ["student_scientist_contract_incomplete"]

    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    word_count = len(ROLE_WORD_RE.findall(option or ""))
    opening_half = "\n\n".join(paragraphs[:2])
    closing_half = "\n\n".join(paragraphs[-2:])
    closing = paragraphs[-1] if paragraphs else ""
    failures: list[str] = []

    if len(paragraphs) not in {3, 4}:
        failures.append("student_scientist_paragraph_count_out_of_contract")
    if not 85 <= word_count <= 150:
        failures.append("student_scientist_word_count_underdeveloped" if word_count < 85 else "student_scientist_word_count_overdeveloped")

    if not (
        STUDENT_SCIENTIST_ACTION_RE.search(opening_half)
        and _assigned_anchor_is_present(option, concrete_action)
    ):
        failures.append("student_scientist_action_missing")
    if not (
        _assigned_anchor_is_present(option, exact_problem)
        and STUDENT_SCIENTIST_PROBLEM_RE.search(option or "")
    ):
        failures.append("student_scientist_problem_missing")
    if not (
        _assigned_anchor_is_present(closing_half, observable_lesson)
        and STUDENT_SCIENTIST_OBSERVATION_RE.search(closing_half)
    ):
        failures.append("student_scientist_lesson_missing")

    if bool(evidence_contract.get("student_scientist_enabled")) and (
        STUDENT_SCIENTIST_COMMAND_RE.search(option or "")
        or STUDENT_SCIENTIST_UNIVERSAL_RE.search(option or "")
    ):
        failures.append("student_scientist_expert_posturing")

    unsupported_result_claim = STUDENT_SCIENTIST_UNSUPPORTED_RESULT_RE.search(option or "")
    evidence_supports_result = any(
        STUDENT_SCIENTIST_UNSUPPORTED_RESULT_RE.search(value)
        for value in (concrete_action, exact_problem, observable_lesson)
    )
    if unsupported_result_claim and not evidence_supports_result:
        failures.append("student_scientist_unsupported_result_claim")

    closing_bound = bool(
        _assigned_anchor_is_present(closing, observable_lesson)
        or _assigned_anchor_is_present(closing, exact_problem)
    )
    if not closing_bound or content_generation_module._genericity_score(closing) > 0:
        failures.append("student_scientist_abstract_payoff")
    return list(dict.fromkeys(failures))


def _local_publishability_failures(
    option: str,
    brief: content_generation_module.ContentOptionBrief | None,
    *,
    evidence_contract: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    if _starts_with_persona_bio(option):
        failures.append("persona_bio_opening")
    if any(_looks_like_label_paragraph(paragraph) for paragraph in paragraphs):
        failures.append("label_paragraph")
    stock_hits = _stock_template_hit_count(option)
    if stock_hits >= 2:
        failures.append(f"stock_template_scaffold:{stock_hits}")
    if brief is not None:
        publishability = content_generation_module._publishability_score(option, brief)
        if publishability < 10:
            failures.append(f"publishability_low:{publishability}")
        failures.extend(_assigned_role_failure_codes(option, brief))
    failures.extend(_student_scientist_evidence_failures(option, evidence_contract))
    return failures


def compose_local_template_options(context_packet: dict[str, Any]) -> list[str]:
    briefs = context_packet.get("planned_option_briefs")
    if not isinstance(briefs, list) or not briefs:
        return []
    expected_option_count = _expected_option_count(context_packet)
    options = [_compose_option(item) for item in briefs if isinstance(item, dict)][:expected_option_count]
    deserialized_briefs = content_generation_module._deserialize_content_option_briefs(briefs)
    if options and deserialized_briefs:
        options = content_generation_module.finalize_planned_options(
            options=options,
            briefs=deserialized_briefs,
            grounding_mode=_clean_text(context_packet.get("grounding_mode")) or "principle_only",
        )
    sanitized_options: list[str] = []
    for index, option in enumerate(options):
        lane = _public_lane(briefs[index] if index < len(briefs) and isinstance(briefs[index], dict) else {})
        sanitized_options.append(_sanitize_public_option(option, lane))
    return sanitized_options


def evaluate_local_quality(context_packet: dict[str, Any], options: list[str]) -> dict[str, Any]:
    briefs = content_generation_module._deserialize_content_option_briefs(context_packet.get("planned_option_briefs"))
    primary_claims = [str(item) for item in (context_packet.get("primary_claims") or []) if str(item).strip()]
    proof_packets = [str(item) for item in (context_packet.get("proof_packets") or []) if str(item).strip()]
    story_beats = [str(item) for item in (context_packet.get("story_beats") or []) if str(item).strip()]
    evidence_contract = context_packet.get("evidence_contract") if isinstance(context_packet.get("evidence_contract"), dict) else None
    grounding_mode = _clean_text(context_packet.get("grounding_mode")) or "principle_only"
    threshold = int(os.getenv("LOCAL_CODEX_QUALITY_GATE_THRESHOLD_PROOF", "76")) if grounding_mode == "proof_ready" else int(
        os.getenv("LOCAL_CODEX_QUALITY_GATE_THRESHOLD_PRINCIPLE", "68")
    )
    critical_warnings = {"claim_not_leading", "weak_closer", "soft_opening_subject", "soft_operator_pronoun", "internal_public_leak", "proof_overloaded"}
    if grounding_mode == "proof_ready":
        critical_warnings.update({"proof_not_visible", "named_reference_missing"})

    expected_option_count = _expected_option_count(context_packet)
    evaluated_options = list(options)
    taste_scores = [
        content_generation_module.score_option_taste(
            option,
            brief=briefs[index] if index < len(briefs) else None,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            grounding_mode=grounding_mode,
        )
        for index, option in enumerate(evaluated_options[:expected_option_count])
    ]

    option_results: list[dict[str, Any]] = []
    aggregate_option_failures: list[str] = []
    for option_index in range(1, expected_option_count + 1):
        taste = taste_scores[option_index - 1] if option_index - 1 < len(taste_scores) else {}
        overall = int(taste.get("overall") or 0)
        warnings = [str(item) for item in (taste.get("warnings") or [])]
        brief = briefs[option_index - 1] if option_index - 1 < len(briefs) else None
        option_failures: list[str] = []
        if option_index > len(evaluated_options):
            option_failures.append("option_missing")
        if overall < threshold:
            option_failures.append(f"below_threshold:{overall}")
        for warning in warnings:
            if warning in critical_warnings:
                option_failures.append(warning)
            if warning.startswith("genericity:"):
                try:
                    genericity = int(warning.split(":", 1)[1])
                except Exception:
                    genericity = 1
                if genericity >= 2:
                    option_failures.append(f"genericity:{genericity}")
        if option_index <= len(evaluated_options):
            for failure in _local_publishability_failures(
                evaluated_options[option_index - 1],
                brief,
                evidence_contract=evidence_contract,
            ):
                option_failures.append(failure)
        option_failures = list(dict.fromkeys(option_failures))
        aggregate_option_failures.extend(
            f"option_{option_index}_{failure}"
            for failure in option_failures
        )
        option_results.append(
            {
                "option_index": option_index,
                "passed": not option_failures,
                "score": overall,
                "threshold": threshold,
                "failed_reasons": option_failures,
            }
        )

    shared_failures: list[str] = []
    if len(evaluated_options) != expected_option_count:
        shared_failures.append(
            f"option_count_mismatch:{len(evaluated_options)}:{expected_option_count}"
        )
    opening_signatures = [
        signature
        for signature in (
            _opening_signature(option)
            for option in evaluated_options[:expected_option_count]
        )
        if signature
    ]
    if len(opening_signatures) >= 2 and len(set(opening_signatures)) < len(opening_signatures):
        shared_failures.append("opening_variety_low")

    draft_distinctness = evaluate_draft_distinctness(context_packet, evaluated_options)
    shared_failures.extend(
        f"draft_distinctness:{reason}"
        for reason in draft_distinctness["failed_reasons"]
        if f"draft_distinctness:{reason}" not in shared_failures
    )
    shared_failures = list(dict.fromkeys(shared_failures))
    shared_passed = not shared_failures
    all_options_passed = all(result["passed"] for result in option_results)
    at_least_one_option_passed = any(result["passed"] for result in option_results)
    passed = shared_passed and all_options_passed
    selection_admission_passed = shared_passed and at_least_one_option_passed
    failed_reasons = list(dict.fromkeys(aggregate_option_failures + shared_failures))
    return {
        "schema_version": DETERMINISTIC_QUALITY_GATE_VERSION,
        "passed": passed,
        "selection_admission_passed": selection_admission_passed,
        "shared_constraints": {
            "passed": shared_passed,
            "failed_reasons": shared_failures,
            "required_option_count": expected_option_count,
            "evaluated_option_count": len(evaluated_options),
        },
        "option_results": option_results,
        "grounding_mode": grounding_mode,
        "threshold": threshold,
        "taste_scores": taste_scores,
        "failed_reasons": failed_reasons,
        "required_option_count": expected_option_count,
        "evaluated_option_count": len(evaluated_options),
        "draft_distinctness": draft_distinctness,
    }


def _strategy_contract_receipt(context_packet: dict[str, Any]) -> dict[str, Any]:
    raw = context_packet.get("strategy_contract")
    if not isinstance(raw, dict):
        return {}
    allowed = (
        "schema_version",
        "contract_hash",
        "approved_at",
        "positioning_model",
        "audience_priority",
        "career_posture",
        "generation_quality_contract",
        "pillars",
        "rolling_topic_mix",
        "intent_mix",
        "weekly_model",
    )
    return {key: raw.get(key) for key in allowed if raw.get(key) not in (None, "", [], {})}


def _candidate_classification_receipt(context_packet: dict[str, Any]) -> dict[str, Any]:
    raw = context_packet.get("candidate_classification")
    if not isinstance(raw, dict):
        return {}
    allowed = (
        "canonical_pillar",
        "career_signal",
        "employer_proximity",
        "employer_safety",
        "proof_posture",
        "publish_posture",
        "treatment",
        "audience",
        "generation_audience",
        "audience_consequence",
        "distinct_thesis",
        "why_now",
        "development_status",
        "classification_state",
        "missing_fields",
    )
    receipt = {key: raw.get(key) for key in allowed if raw.get(key) not in (None, "", [], {})}
    freshness = raw.get("source_freshness")
    if isinstance(freshness, dict):
        freshness_allowed = ("temporality", "state", "dated_at", "age_days", "current_claim_allowed")
        receipt["source_freshness"] = {
            key: freshness.get(key)
            for key in freshness_allowed
            if freshness.get(key) is not None
        }
    return receipt


def _portfolio_learning_receipt(context_packet: dict[str, Any]) -> dict[str, Any]:
    raw = context_packet.get("portfolio_learning")
    if not isinstance(raw, dict) or raw.get("schema_version") != "feezie_portfolio_learning_receipt/v1":
        return {}
    counts = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    policy = raw.get("decision_policy") if isinstance(raw.get("decision_policy"), dict) else {}
    return {
        "schema_version": "feezie_portfolio_learning_receipt/v1",
        "receipt_sha256": str(raw.get("receipt_sha256") or ""),
        "strategy_contract_hash": str(raw.get("strategy_contract_hash") or ""),
        "source_state": str(raw.get("source_state") or "missing"),
        "learning_mode": str(raw.get("learning_mode") or "collect_only"),
        "confidence": str(raw.get("confidence") or "insufficient_sample"),
        "counts": {
            key: int(counts.get(key) or 0)
            for key in (
                "owner_decisions",
                "confirmed_publications",
                "complete_feedback_posts",
                "owner_assessments",
            )
        },
        "decision_policy": {
            key: bool(policy.get(key))
            for key in (
                "qualified_evidence_only",
                "employer_safety_gate_unchanged",
                "proof_gate_unchanged",
                "outcome_reordering_allowed",
                "strategy_contract_mutation_allowed",
                "owner_approval_required_for_contract_change",
                "filler_forbidden",
            )
        },
    }


def build_result_payload(
    *,
    request_payload: dict[str, Any],
    context_packet: dict[str, Any],
    options: list[str],
    provider: str,
    model: str,
    quality_gate: dict[str, Any] | None = None,
    raw_output: str | None = None,
    command_stdout: str | None = None,
    command_stderr: str | None = None,
) -> dict[str, Any]:
    briefs = content_generation_module._deserialize_content_option_briefs(context_packet.get("planned_option_briefs"))
    primary_claims = [str(item) for item in (context_packet.get("primary_claims") or []) if str(item).strip()]
    proof_packets = [str(item) for item in (context_packet.get("proof_packets") or []) if str(item).strip()]
    story_beats = [str(item) for item in (context_packet.get("story_beats") or []) if str(item).strip()]
    grounding_mode = _clean_text(context_packet.get("grounding_mode")) or "principle_only"
    expected_option_count = _expected_option_count(context_packet)
    draft_contract = (
        context_packet.get("draft_contract")
        if isinstance(context_packet.get("draft_contract"), dict)
        else {}
    )
    is_feezie_contract = (
        str(draft_contract.get("schema_version") or "").strip()
        == "feezie_draft_contract/v1"
    )
    preserve_writer_voice = (
        provider == "codex_terminal"
        and str(os.getenv("LOCAL_CODEX_PRESERVE_WRITER_VOICE", "true")).strip().lower() not in {"0", "false", "no", "off"}
    )
    preserve_canonical_writer_order = _independent_critic_required(context_packet)
    safety_only_pre_critic = preserve_writer_voice and preserve_canonical_writer_order
    if briefs:
        # Codex already received a structured plan, public-release rules, and
        # complete owner-written references. Re-running the deterministic
        # template finalizer here used to flatten those drafts into one house
        # voice. Keep its substantive output and apply only the safety scrub.
        if preserve_writer_voice:
            options = options[:expected_option_count]
        else:
            options = content_generation_module.finalize_planned_options(
                options=options[:expected_option_count],
                briefs=briefs,
                grounding_mode=grounding_mode,
            )
        sanitized_options: list[str] = []
        approved_reference_terms = [
            str(item)
            for item in (context_packet.get("approved_references") or [])
            if str(item).strip()
        ]
        audience = str(request_payload.get("audience") or "")
        for index, option in enumerate(options[:expected_option_count]):
            brief = briefs[index] if index < len(briefs) else briefs[-1]
            lane = _public_lane(
                {
                    "option_number": brief.option_number,
                    "public_lane": brief.public_lane,
                }
            )
            if safety_only_pre_critic:
                revised = content_generation_module._sanitize_public_output_safety_only(option, brief)
            else:
                revised = content_generation_module._sanitize_public_output(option, brief)
            revised = content_generation_module._drop_unapproved_reference_sentences(
                revised,
                brief=brief,
                approved_reference_terms=approved_reference_terms,
                audience=audience,
            )
            if safety_only_pre_critic:
                # The reference scrub can synthesize approved proof when it removes
                # an unsafe sentence. Re-run only the safety boundary over that text.
                revised = content_generation_module._sanitize_public_output_safety_only(revised, brief)
            else:
                revised = _sanitize_public_option(revised, lane)
            sanitized_options.append(revised)
        options = sanitized_options
    taste_scores = [
        content_generation_module.score_option_taste(
            option,
            brief=briefs[index] if index < len(briefs) else None,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            grounding_mode=grounding_mode,
        )
        for index, option in enumerate(options[:expected_option_count])
    ]
    ranking_briefs = briefs or [
        content_generation_module.ContentOptionBrief(1, "operator_lesson", "", "", "")
    ]
    if preserve_canonical_writer_order:
        ordered_options = list(options[:expected_option_count])
        ordered_briefs = [
            ranking_briefs[index] if index < len(ranking_briefs) else ranking_briefs[-1]
            for index in range(len(ordered_options))
        ]
        ordered_scores = list(taste_scores[:expected_option_count])
    else:
        ordered_options, ordered_briefs, ordered_scores = content_generation_module._rank_options_by_taste(
            options=options[:expected_option_count],
            briefs=ranking_briefs,
            taste_scores=taste_scores,
            topic=str(request_payload.get("topic") or ""),
            audience=str(request_payload.get("audience") or ""),
        )
    return {
        "success": True,
        "options": ordered_options[:expected_option_count],
        "persona_context": context_packet.get("persona_context_summary"),
        "examples_used": list(context_packet.get("examples_used") or []),
        "diagnostics": {
            "grounding_mode": context_packet.get("grounding_mode"),
            "generation_strategy": provider,
            "intent": context_packet.get("intent") or request_payload.get("category") or "value",
            "strategy_contract": _strategy_contract_receipt(context_packet),
            "candidate_classification": _candidate_classification_receipt(context_packet),
            "portfolio_learning": _portfolio_learning_receipt(context_packet),
            "writer_voice_preservation": preserve_writer_voice,
            "writer_sanitization_policy": (
                "safety_only_pre_critic"
                if safety_only_pre_critic
                else "legacy_editorial_sanitization"
            ),
            "pre_critic_ordering": (
                "canonical_writer_order"
                if preserve_canonical_writer_order
                else "legacy_taste_ranked"
            ),
            "primary_claims": primary_claims,
            "proof_packets": proof_packets,
            "approved_references": list(context_packet.get("approved_references") or []),
            "voice_directives": list(context_packet.get("voice_directives") or []),
            "planned_option_briefs": content_generation_module._serialize_content_option_briefs(ordered_briefs),
            "taste_scores": ordered_scores,
            "topic_anchor_preview": list(context_packet.get("topic_anchor_preview") or []),
            "core_chunk_preview": list(context_packet.get("core_chunk_preview") or []),
            "proof_anchor_preview": list(context_packet.get("proof_anchor_preview") or []),
            "content_signal_source": context_packet.get("content_signal_source") or "persona_only",
            "content_signal_preview": list(context_packet.get("content_signal_preview") or context_packet.get("content_reservoir_preview") or []),
            "content_signal_count": int(context_packet.get("content_signal_count") or context_packet.get("content_reservoir_count") or 0),
            "content_signal_support": list(context_packet.get("content_signal_support") or context_packet.get("content_reservoir_support") or []),
            "content_reservoir_preview": list(context_packet.get("content_reservoir_preview") or context_packet.get("content_signal_preview") or []),
            "content_reservoir_count": int(context_packet.get("content_reservoir_count") or context_packet.get("content_signal_count") or 0),
            "content_reservoir_support": list(context_packet.get("content_reservoir_support") or context_packet.get("content_signal_support") or []),
            "llm_provider_trace": [
                {
                    "provider": provider,
                    "actual_model": model,
                    "status": "success",
                }
            ],
            "source_mode": request_payload.get("source_mode"),
            "quality_gate": quality_gate or {},
            "draft_contract": dict(context_packet.get("draft_contract") or {}),
            "draft_distinctness": evaluate_draft_distinctness(
                context_packet,
                ordered_options[:expected_option_count],
            ),
            **(
                {}
                if is_feezie_contract
                else {
                    "raw_codex_output_preview": (raw_output or "")[:800],
                    "runner_stdout_preview": (command_stdout or "")[-800:],
                    "runner_stderr_preview": (command_stderr or "")[-800:],
                }
            ),
        },
    }


def build_local_template_artifacts(
    *,
    context_packet: dict[str, Any],
    options: list[str],
    quality_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "kind": "quality_gate",
            "label": "quality-gate.json",
            "filename": "quality-gate.json",
            "mime_type": "application/json",
            "content": json.dumps(quality_gate, indent=2) + "\n",
        },
        {
            "kind": "draft_options",
            "label": "local-template-options.json",
            "filename": "local-template-options.json",
            "mime_type": "application/json",
            "content": json.dumps(
                {
                    "provider": LOCAL_TEMPLATE_PROVIDER,
                    "model": LOCAL_TEMPLATE_MODEL,
                    "planned_option_briefs": context_packet.get("planned_option_briefs") or [],
                    "options": options,
                },
                indent=2,
            )
            + "\n",
        },
    ]
