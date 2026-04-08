from __future__ import annotations

import re
from typing import Any


POLICY_VERSION = "content-visibility-policy.v1"
PUBLIC_SOCIAL_CONTENT_TYPES = {"linkedin_post"}
PUBLIC_ALLOWED_USAGE = ["linkedin_post", "operator_post", "social_post"]
GENERIC_PROOF_LABELS = {
    "anecdote",
    "claim",
    "framework",
    "phrase candidate",
    "proof point",
    "promoted item",
    "stat",
    "talking point",
}
_LABEL_CONNECTORS = {"a", "an", "and", "at", "for", "from", "in", "of", "on", "the", "to", "vs"}
_PATH_RE = re.compile(r"/Users/neo/[^\s,)\]]+")
_BACKTICK_RE = re.compile(r"`+")
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"\s+([,.;:])")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_METRIC_RE = re.compile(r"\b\d+(?:[.,]\d+)?%?\b")
_INTERNAL_REPLACEMENTS = (
    (re.compile(r"\bAI Clone\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bBrain System\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bOpenClaw\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bRailway\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bCodex\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bJean-Claude\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bNeo\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bFEEZIE\b", re.IGNORECASE), "the content system"),
    (re.compile(r"\bfusion-os\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\blinkedin-content-os\b", re.IGNORECASE), "the content lane"),
    (re.compile(r"\beasyoutfitapp\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\bai-swag-store\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\bagc\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\bshared_ops\b", re.IGNORECASE), "the shared workflow"),
    (re.compile(r"\bChronicle\b", re.IGNORECASE), "memory"),
    (re.compile(r"\bPM card\b", re.IGNORECASE), "task"),
    (re.compile(r"\bSOP\b", re.IGNORECASE), "playbook"),
    (re.compile(r"\bwork order\b", re.IGNORECASE), "handoff"),
    (re.compile(r"\bwrite-back\b", re.IGNORECASE), "feedback loop"),
    (re.compile(r"\bdispatch\b", re.IGNORECASE), "handoff"),
    (re.compile(r"\bqueue\b", re.IGNORECASE), "workflow"),
    (re.compile(r"\bworkspace lane\b", re.IGNORECASE), "workflow lane"),
    (re.compile(r"\bworkspace agent\b", re.IGNORECASE), "delegated execution"),
)
_LITERAL_LEAK_PATTERNS = (
    re.compile(r"\bdaily briefs?\b", re.IGNORECASE),
    re.compile(r"\bweekly briefs?\b", re.IGNORECASE),
    re.compile(r"\bplanner\b", re.IGNORECASE),
    re.compile(r"\bproof packets?\b", re.IGNORECASE),
    re.compile(r"\bstory beats?\b", re.IGNORECASE),
    re.compile(r"\bcontent reservoir\b", re.IGNORECASE),
    re.compile(r"\brouted workspace state\b", re.IGNORECASE),
    re.compile(r"\bworkspace snapshot\b", re.IGNORECASE),
    re.compile(r"\btyped core\b", re.IGNORECASE),
    re.compile(r"\bdomain gates?\b", re.IGNORECASE),
    re.compile(r"\bpersona soup\b", re.IGNORECASE),
    re.compile(r"\bschema\b", re.IGNORECASE),
)
_ENTITY_LEAK_PATTERNS = (
    re.compile(r"\bAI Clone\b", re.IGNORECASE),
    re.compile(r"\bOpenClaw\b", re.IGNORECASE),
    re.compile(r"\bRailway\b", re.IGNORECASE),
    re.compile(r"\bJean-Claude\b", re.IGNORECASE),
    re.compile(r"\bfusion-os\b", re.IGNORECASE),
    re.compile(r"\blinkedin-content-os\b", re.IGNORECASE),
    re.compile(r"\beasyoutfitapp\b", re.IGNORECASE),
    re.compile(r"\bai-swag-store\b", re.IGNORECASE),
    re.compile(r"\bagc\b", re.IGNORECASE),
)
_SEMANTIC_INTERNAL_MARKERS = (
    "brain",
    "ops",
    "daily brief",
    "weekly brief",
    "planner",
    "snapshot",
    "context packet",
    "proof packet",
    "story beat",
    "typed core",
    "domain gate",
    "content reservoir",
    "routed workspace",
    "prompt packet",
    "write-back",
    "handoff",
    "dispatch",
)
_STUDENT_SUPPORT_TERMS = {
    "2e",
    "admissions",
    "applicant",
    "applicants",
    "education",
    "enrollment",
    "families",
    "family",
    "learning",
    "neurodivergent",
    "parent",
    "parents",
    "prospective",
    "school",
    "schools",
    "student",
    "students",
    "support",
    "twice",
    "exceptional",
}
_STUDENT_SUPPORT_PHRASES = (
    "twice exceptional",
    "twice-exceptional",
    "prospective students",
    "prospective student",
    "neurodivergent student",
    "neurodivergent students",
    "learning support",
)


def build_content_release_policy(*, content_type: str, audience: str) -> dict[str, Any]:
    public_surface = content_type in PUBLIC_SOCIAL_CONTENT_TYPES
    return {
        "policy_name": "content_visibility_policy",
        "policy_version": POLICY_VERSION,
        "content_type": content_type,
        "audience": audience,
        "surface": "public_social" if public_surface else "internal",
        "raw_context_access": "blocked" if public_surface else "allowed",
        "proof_packet_policy": {
            "default_visibility": "restricted" if public_surface else "internal",
            "allowed_usage": PUBLIC_ALLOWED_USAGE[:] if public_surface else ["internal_only"],
            "validation_layers": ["literal", "entity", "semantic"] if public_surface else [],
            "transform_order": ["classify", "transform", "validate"] if public_surface else ["classify"],
        },
        "primary_claim_policy": {
            "default_visibility": "restricted" if public_surface else "internal",
            "allowed_usage": PUBLIC_ALLOWED_USAGE[:] if public_surface else ["internal_only"],
            "validation_layers": ["literal", "entity", "semantic"] if public_surface else [],
            "transform_order": ["classify", "transform", "validate"] if public_surface else ["classify"],
        },
        "story_beat_policy": {
            "default_visibility": "restricted" if public_surface else "internal",
            "allowed_usage": PUBLIC_ALLOWED_USAGE[:] if public_surface else ["internal_only"],
            "validation_layers": ["literal", "entity", "semantic"] if public_surface else [],
            "transform_order": ["classify", "transform", "validate"] if public_surface else ["classify"],
        },
    }


def _normalize_text(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _split_sentences(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    parts = _SENTENCE_RE.split(normalized)
    return [part.strip() for part in parts if part.strip()]


def _split_label(packet: str) -> tuple[str, str]:
    left, separator, right = str(packet or "").partition("->")
    if separator:
        return _normalize_text(left), _normalize_text(right)
    return "", _normalize_text(packet)


def _sanitize_public_text(text: Any) -> tuple[str, list[str]]:
    cleaned = str(text or "")
    notes: list[str] = []
    if not cleaned.strip():
        return "", notes
    if _PATH_RE.search(cleaned):
        cleaned = _PATH_RE.sub("a durable artifact", cleaned)
        notes.append("stripped_file_path")
    if _BACKTICK_RE.search(cleaned):
        cleaned = _BACKTICK_RE.sub("", cleaned)
        notes.append("stripped_backticks")
    for pattern, replacement in _INTERNAL_REPLACEMENTS:
        if pattern.search(cleaned):
            cleaned = pattern.sub(replacement, cleaned)
            notes.append(f"generalized:{replacement}")
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = _PUNCT_RE.sub(r"\1", cleaned).strip(" -")
    return cleaned, notes


def _semantic_leak_flags(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return ["empty"]
    flags: list[str] = []
    for pattern in _LITERAL_LEAK_PATTERNS:
        if pattern.search(normalized):
            flags.append(f"literal:{pattern.pattern}")
    for pattern in _ENTITY_LEAK_PATTERNS:
        if pattern.search(normalized):
            flags.append(f"entity:{pattern.pattern}")
    lowered = normalized.lower()
    marker_hits = sum(1 for marker in _SEMANTIC_INTERNAL_MARKERS if marker in lowered)
    if marker_hits >= 2:
        flags.append("semantic:internal_operating_language")
    return flags


def _looks_like_voice_fragment(text: str) -> bool:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return False
    return normalized.startswith(
        (
            "reusable phrases:",
            "promoted fragments:",
            "avoid patterns:",
            "good examples:",
            "core tone:",
            "voice rules:",
        )
    )


def _starts_with_third_person_persona_bio(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return bool(
        re.match(
            r"^(?:johnnie)\s+(?:is|treats|keeps|built|started|learned)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_partial_source_fragment(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered.startswith(("and his ", "and her ", "and their ", "but ", "so ", "because ")):
        return True
    if "->" in normalized:
        return True
    if lowered.startswith(("com crash", ". com crash", "from surviving the", "from the .com", "from the com")):
        return True
    return False


def _needs_public_claim_rewrite(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return bool(
        _semantic_leak_flags(normalized)
        or _starts_with_third_person_persona_bio(normalized)
        or _looks_like_voice_fragment(normalized)
        or _looks_like_partial_source_fragment(normalized)
        or _looks_systemy_public_claim(normalized)
    )


def _needs_public_proof_rewrite(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return bool(
        _semantic_leak_flags(normalized)
        or _starts_with_third_person_persona_bio(normalized)
        or _looks_like_partial_source_fragment(normalized)
        or _looks_tool_heavy_public_proof(normalized)
    )


def _looks_like_label_only_story(text: str) -> bool:
    normalized = _normalize_text(text).rstrip(".")
    if not normalized:
        return False
    words = normalized.split()
    if len(words) > 6:
        return False
    if " " not in normalized:
        return True
    lowered_words = {word.lower() for word in words}
    verb_markers = {
        "is",
        "was",
        "were",
        "means",
        "matters",
        "taught",
        "showed",
        "made",
        "kept",
        "stopped",
        "started",
        "learned",
        "changed",
        "helped",
    }
    return not bool(lowered_words & verb_markers)


def _evidence_type(*, proof_text: str, metadata: dict[str, Any]) -> str:
    claim_type = str(metadata.get("claim_type") or "").strip().lower()
    lowered = proof_text.lower()
    if _METRIC_RE.search(proof_text) or bool(metadata.get("artifact_backed")):
        return "direct_proof"
    if claim_type in {"operational", "positioning", "mission"}:
        return "lesson"
    if "story" in claim_type or "anecdote" in lowered:
        return "anecdote"
    return "claim"


def _looks_systemy_public_claim(text: str) -> bool:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return False
    system_markers = (
        "agent orchestration",
        "operating pattern",
        "operating model",
        "operator pattern",
        "prompting plus",
        "prompting alone",
    )
    marker_hits = sum(1 for marker in system_markers if marker in normalized)
    if marker_hits >= 2:
        return True
    if "agent orchestration" in normalized:
        return True
    return False


def _looks_tool_heavy_public_proof(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    lowered = normalized.lower()
    tool_hits = sum(
        1
        for marker in ("salesforce", "dashboard", "command center")
        if marker in lowered
    )
    metric_hits = len(_METRIC_RE.findall(normalized))
    if "command center" in lowered:
        return True
    if tool_hits >= 2:
        return True
    return tool_hits >= 1 and metric_hits >= 2


def _is_student_support_topic(topic: str, audience: str) -> bool:
    if audience in {"education_admissions", "neurodivergent"}:
        return True
    normalized = _normalize_text(topic).lower()
    if not normalized:
        return False
    if any(phrase in normalized for phrase in _STUDENT_SUPPORT_PHRASES):
        return True
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    return bool(tokens.intersection(_STUDENT_SUPPORT_TERMS))


def _looks_like_student_topic_business_drift(text: str) -> bool:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return False
    return any(
        term in lowered
        for term in (
            "customer trust",
            "technology cycle",
            "tech cycle",
            "desktop to cloud",
            ". com crash",
            "com crash",
        )
    )


def _generalize_internal_proof(*, label: str, proof_text: str, topic: str, audience: str) -> str:
    combined = " ".join(part.lower() for part in (label, proof_text, topic, audience) if part)
    if _is_student_support_topic(topic, audience):
        if any(
            term in combined
            for term in (
                "salesforce dashboard",
                "salesforce command center",
                "command center",
                "dashboard transformation",
                "territory coordination",
                "daily brief",
                "weekly brief",
                "planner",
                "snapshot",
                "brain",
                "ops",
                "source of truth",
                "routed workspace",
            )
        ):
            return "A clearer review process made it easier to see both student potential and support needs at the same time."
        if any(term in combined for term in ("com crash", ". com crash", "desktop to cloud", "quarters", "customer trust", "approach to ai")):
            return "The process only earns family trust when nuance survives the review instead of getting flattened."
    if any(term in combined for term in ("salesforce dashboard", "salesforce command center", "command center", "dashboard transformation", "territory coordination")):
        return "One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust."
    if any(term in combined for term in ("daily brief", "weekly brief", "planner", "snapshot", "brain", "ops", "source of truth", "routed workspace")):
        return "One shared source of truth made planning, execution, and follow-through easier to trust."
    if any(term in combined for term in ("proof packet", "story beat", "persona", "content reservoir", "typed core", "domain gate", "writer")):
        return "The writing got stronger when each draft stayed close to clear proof and tighter source boundaries."
    if any(term in combined for term in ("pm card", "dispatch", "write-back", "handoff", "queue", "closure", "review", "workflow lane")):
        return "Execution improves when ownership, handoffs, and follow-through are explicit."
    if any(term in combined for term in ("chronicle", "memory", "history", "dream cycle")):
        return "Systems get more useful when lessons are captured in a form people can reuse."
    sanitized_text, _ = _sanitize_public_text(proof_text)
    sentences = _split_sentences(sanitized_text)
    if sentences:
        return sentences[0].rstrip(".") + "."
    return "Recent work produced a clearer operating lesson the team can reuse."


def _generalize_internal_claim(*, claim_text: str, topic: str, audience: str) -> str:
    combined = " ".join(part.lower() for part in (claim_text, topic, audience) if part)
    if _is_student_support_topic(topic, audience):
        if any(term in combined for term in ("agent orchestration", "operating pattern", "operating model", "operator pattern", "prompting plus", "prompting alone")):
            return "AI should help a review process see the whole student more clearly, not flatten the person in front of it."
        if any(term in combined for term in ("daily brief", "weekly brief", "planner", "snapshot", "brain", "ops", "source of truth", "routed workspace")):
            return "The review works better when everyone can see the same full picture of the student."
        if any(term in combined for term in ("proof packet", "story beat", "persona", "content reservoir", "typed core", "domain gate", "writer")):
            return "The message gets stronger when it stays close to what students and families actually need."
        if any(term in combined for term in ("especially strong", "quietly inefficient", "story type:", "operator cleanup")):
            return "The hardest part is usually not the student. It is the system around the student."
        if any(term in combined for term in ("com crash", ". com crash", "desktop to cloud", "quarters", "customer trust", "approach to ai")):
            return "The right admissions system has to hold both a student's potential and their support needs at the same time."
    if any(term in combined for term in ("agent orchestration", "operating pattern", "operating model", "operator pattern", "prompting plus", "prompting alone")):
        return "AI helps when the workflow is coordinated, not improvised."
    if any(term in combined for term in ("daily brief", "weekly brief", "planner", "snapshot", "brain", "ops", "source of truth", "routed workspace")):
        return "Operator clarity gets stronger when one shared source of truth replaces scattered context."
    if any(term in combined for term in ("proof packet", "story beat", "persona", "content reservoir", "typed core", "domain gate", "writer")):
        return "The writing gets stronger when strategy stays close to clear proof."
    if any(term in combined for term in ("especially strong", "quietly inefficient", "story type:", "operator cleanup")):
        return "The strongest work often starts in quietly inefficient systems, not visibly broken ones."
    if any(term in combined for term in ("com crash", ". com crash", "desktop to cloud", "quarters")):
        return "Discipline and customer trust matter more than chasing every technology cycle."
    if any(term in combined for term in ("his approach to ai", "approach to ai", "customer trust")):
        return "AI should strengthen workflows without coming at the expense of customer trust."
    sanitized_text, _ = _sanitize_public_text(claim_text)
    if sanitized_text.lower().startswith("johnnie treats "):
        sanitized_text = re.sub(r"^Johnnie treats\s+", "", sanitized_text, flags=re.IGNORECASE)
        if " as " in sanitized_text:
            left, right = sanitized_text.split(" as ", 1)
            sanitized_text = f"{left} is {right}"
    elif sanitized_text.lower().startswith("johnnie "):
        sanitized_text = re.sub(r"^Johnnie\s+", "", sanitized_text, flags=re.IGNORECASE)
    sentences = _split_sentences(sanitized_text)
    if sentences:
        text = sentences[0].rstrip(".")
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text + "."
    return "Clearer operating context changes what the system can actually deliver."


def _generalize_story_beat(*, beat_text: str, topic: str, audience: str) -> str:
    combined = " ".join(part.lower() for part in (beat_text, topic, audience) if part)
    if _is_student_support_topic(topic, audience) and any(
        term in combined
        for term in (
            "twice exceptional",
            "twice-exceptional",
            "2e",
            "student",
            "students",
            "family",
            "families",
            "admissions",
            "enrollment",
            "support",
            "neurodivergent",
        )
    ):
        return "The real work is seeing the whole student instead of forcing a simpler label."
    if "quiet inefficiency" in combined:
        return "The real problem is usually quiet inefficiency, not obvious chaos."
    if "constraint breakthrough" in combined:
        return "The breakthrough usually comes from tightening the constraint, not adding more activity."
    if "family clarity" in combined or "admissions" in combined:
        return "Trust rises when people feel processed honestly instead of pushed through a script."
    if any(term in combined for term in ("daily brief", "weekly brief", "planner", "snapshot", "brain", "ops")):
        return "The useful lesson was not the tooling. It was the clarity that came from one shared source of truth."
    sanitized_text, _ = _sanitize_public_text(beat_text)
    if sanitized_text.lower().startswith("johnnie "):
        sanitized_text = re.sub(r"^Johnnie\s+", "", sanitized_text, flags=re.IGNORECASE)
    sentences = _split_sentences(sanitized_text)
    if sentences:
        text = sentences[0].rstrip(".")
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text + "."
    return ""


def _safe_label(label: str, *, public_text: str) -> str:
    cleaned, _ = _sanitize_public_text(label)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered in GENERIC_PROOF_LABELS:
        return ""
    if _looks_like_partial_source_fragment(cleaned):
        return ""
    if "/" in cleaned or len(cleaned.split()) > 6:
        return ""
    tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*", cleaned)
    if tokens:
        titleish_tokens = 0
        for token in tokens:
            token_lower = token.lower()
            if token_lower in _LABEL_CONNECTORS:
                continue
            if token[:1].isupper() or token.isupper():
                titleish_tokens += 1
                continue
            return ""
        if titleish_tokens == 0:
            return ""
    if _semantic_leak_flags(cleaned) or _semantic_leak_flags(public_text):
        return ""
    return cleaned


def build_public_safe_proof_packets(
    *,
    proof_anchor_chunks: list[dict[str, Any]],
    raw_proof_packets: list[str],
    content_type: str,
    topic: str,
    audience: str,
) -> list[dict[str, Any]]:
    public_surface = content_type in PUBLIC_SOCIAL_CONTENT_TYPES
    packets: list[dict[str, Any]] = []
    for index, raw_packet in enumerate(raw_proof_packets):
        raw_text = _normalize_text(raw_packet)
        if not raw_text:
            continue
        chunk = proof_anchor_chunks[index] if index < len(proof_anchor_chunks) else {}
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        label, proof_text = _split_label(raw_text)
        sanitized_proof, sanitize_notes = _sanitize_public_text(proof_text)
        evidence_type = _evidence_type(proof_text=sanitized_proof or proof_text, metadata=metadata)
        transform_rule = "quote"
        policy_notes: list[str] = sanitize_notes[:]

        candidate_text = sanitized_proof or proof_text
        if public_surface:
            leak_flags = _semantic_leak_flags(candidate_text)
            if _looks_like_voice_fragment(raw_text):
                approval_status = "blocked"
                policy_notes.append("voice_fragment")
            elif _needs_public_proof_rewrite(candidate_text) or (
                _is_student_support_topic(topic, audience) and _looks_like_student_topic_business_drift(candidate_text)
            ):
                transform_rule = "generalize"
                policy_notes.extend(leak_flags)
                if _starts_with_third_person_persona_bio(candidate_text):
                    policy_notes.append("third_person_persona")
                    candidate_text = _generalize_internal_claim(
                        claim_text=proof_text,
                        topic=topic,
                        audience=audience,
                    )
                elif _looks_like_partial_source_fragment(candidate_text):
                    policy_notes.append("partial_source_fragment")
                    candidate_text = _generalize_internal_claim(
                        claim_text=proof_text,
                        topic=topic,
                        audience=audience,
                    )
                else:
                    candidate_text = _generalize_internal_proof(
                        label=label,
                        proof_text=proof_text,
                        topic=topic,
                        audience=audience,
                    )
                candidate_text, extra_notes = _sanitize_public_text(candidate_text)
                policy_notes.extend(extra_notes)
                leak_flags = _semantic_leak_flags(candidate_text)
                approval_status = "blocked" if leak_flags else "auto"
                if approval_status == "blocked":
                    policy_notes.extend(leak_flags)
            else:
                approval_status = "auto"
        else:
            approval_status = "auto"

        visibility = "public_safe" if approval_status == "auto" and public_surface else ("internal" if not public_surface else "restricted")
        allowed_usage = PUBLIC_ALLOWED_USAGE[:] if visibility == "public_safe" else (["internal_only"] if not public_surface else [])
        label_text = _safe_label(label, public_text=candidate_text) if visibility == "public_safe" else ""
        public_packet = candidate_text.rstrip(".") + "." if candidate_text else ""
        if label_text:
            public_packet = f"{label_text} -> {public_packet}"

        packets.append(
            {
                "id": f"proof-policy-{index + 1}",
                "raw_packet": raw_text,
                "public_packet": public_packet,
                "visibility": visibility,
                "transform_rule": transform_rule,
                "allowed_usage": allowed_usage,
                "evidence_type": evidence_type,
                "approval_status": approval_status,
                "policy_notes": sorted(set(note for note in policy_notes if note)),
                "source_kind": str(metadata.get("source_kind") or ""),
                "artifact_backed": bool(metadata.get("artifact_backed")),
            }
        )
    return packets


def render_policy_approved_proof_packets(
    *,
    public_safe_proof_packets: list[dict[str, Any]],
    content_type: str,
) -> list[str]:
    if content_type not in PUBLIC_SOCIAL_CONTENT_TYPES:
        return [
            _normalize_text(packet.get("raw_packet"))
            for packet in public_safe_proof_packets
            if _normalize_text(packet.get("raw_packet"))
        ]
    approved: list[str] = []
    seen: set[str] = set()
    for packet in public_safe_proof_packets:
        if str(packet.get("approval_status") or "") != "auto":
            continue
        if content_type not in list(packet.get("allowed_usage") or []):
            continue
        rendered = _normalize_text(packet.get("public_packet"))
        if not rendered or rendered.lower() in seen:
            continue
        seen.add(rendered.lower())
        approved.append(rendered)
    return approved[:4]


def build_public_safe_primary_claims(
    *,
    raw_primary_claims: list[str],
    content_type: str,
    topic: str,
    audience: str,
) -> list[dict[str, Any]]:
    public_surface = content_type in PUBLIC_SOCIAL_CONTENT_TYPES
    claims: list[dict[str, Any]] = []
    for index, raw_claim in enumerate(raw_primary_claims):
        raw_text = _normalize_text(raw_claim)
        if not raw_text:
            continue
        candidate_text, sanitize_notes = _sanitize_public_text(raw_text)
        transform_rule = "quote"
        policy_notes: list[str] = sanitize_notes[:]
        if public_surface:
            leak_flags = _semantic_leak_flags(candidate_text)
            needs_generalize = _needs_public_claim_rewrite(candidate_text) or (
                _is_student_support_topic(topic, audience) and _looks_like_student_topic_business_drift(candidate_text)
            )
            if needs_generalize:
                transform_rule = "generalize"
                if leak_flags:
                    policy_notes.extend(leak_flags)
                if _starts_with_third_person_persona_bio(candidate_text):
                    policy_notes.append("third_person_persona")
                if _looks_like_voice_fragment(candidate_text):
                    policy_notes.append("voice_fragment")
                if _looks_like_partial_source_fragment(candidate_text):
                    policy_notes.append("partial_source_fragment")
                candidate_text = _generalize_internal_claim(
                    claim_text=raw_text,
                    topic=topic,
                    audience=audience,
                )
                candidate_text, extra_notes = _sanitize_public_text(candidate_text)
                policy_notes.extend(extra_notes)
            leak_flags = _semantic_leak_flags(candidate_text)
            approval_status = "blocked" if (leak_flags or _looks_like_voice_fragment(candidate_text)) else "auto"
            if approval_status == "blocked":
                policy_notes.extend(leak_flags)
        else:
            approval_status = "auto"
        visibility = "public_safe" if approval_status == "auto" and public_surface else ("internal" if not public_surface else "restricted")
        allowed_usage = PUBLIC_ALLOWED_USAGE[:] if visibility == "public_safe" else (["internal_only"] if not public_surface else [])
        public_claim = candidate_text.rstrip(".") + "." if candidate_text else ""
        claims.append(
            {
                "id": f"claim-policy-{index + 1}",
                "raw_claim": raw_text,
                "public_claim": public_claim,
                "visibility": visibility,
                "transform_rule": transform_rule,
                "allowed_usage": allowed_usage,
                "evidence_type": "claim",
                "approval_status": approval_status,
                "policy_notes": sorted(set(note for note in policy_notes if note)),
            }
        )
    return claims


def render_policy_approved_primary_claims(
    *,
    public_safe_primary_claims: list[dict[str, Any]],
    content_type: str,
) -> list[str]:
    if content_type not in PUBLIC_SOCIAL_CONTENT_TYPES:
        return [
            _normalize_text(item.get("raw_claim"))
            for item in public_safe_primary_claims
            if _normalize_text(item.get("raw_claim"))
        ]
    approved: list[str] = []
    seen: set[str] = set()
    for item in public_safe_primary_claims:
        if str(item.get("approval_status") or "") != "auto":
            continue
        if content_type not in list(item.get("allowed_usage") or []):
            continue
        rendered = _normalize_text(item.get("public_claim"))
        if not rendered or rendered.lower() in seen:
            continue
        seen.add(rendered.lower())
        approved.append(rendered)
    return approved[:3]


def build_public_safe_story_beats(
    *,
    raw_story_beats: list[str],
    content_type: str,
    topic: str,
    audience: str,
) -> list[dict[str, Any]]:
    public_surface = content_type in PUBLIC_SOCIAL_CONTENT_TYPES
    beats: list[dict[str, Any]] = []
    for index, raw_beat in enumerate(raw_story_beats):
        raw_text = _normalize_text(raw_beat)
        if not raw_text:
            continue
        candidate_text, sanitize_notes = _sanitize_public_text(raw_text)
        transform_rule = "quote"
        policy_notes: list[str] = sanitize_notes[:]
        if public_surface:
            leak_flags = _semantic_leak_flags(candidate_text)
            needs_generalize = bool(
                leak_flags
                or _looks_like_label_only_story(candidate_text)
                or _starts_with_third_person_persona_bio(candidate_text)
                or _looks_like_voice_fragment(candidate_text)
            )
            if needs_generalize:
                transform_rule = "generalize"
                if leak_flags:
                    policy_notes.extend(leak_flags)
                if _looks_like_label_only_story(candidate_text):
                    policy_notes.append("label_only_story")
                if _starts_with_third_person_persona_bio(candidate_text):
                    policy_notes.append("third_person_persona")
                if _looks_like_voice_fragment(candidate_text):
                    policy_notes.append("voice_fragment")
                candidate_text = _generalize_story_beat(
                    beat_text=raw_text,
                    topic=topic,
                    audience=audience,
                )
                candidate_text, extra_notes = _sanitize_public_text(candidate_text)
                policy_notes.extend(extra_notes)
            leak_flags = _semantic_leak_flags(candidate_text)
            approval_status = "blocked" if (not candidate_text or leak_flags or _looks_like_voice_fragment(candidate_text)) else "auto"
            if approval_status == "blocked":
                policy_notes.extend(leak_flags)
        else:
            approval_status = "auto"
        visibility = "public_safe" if approval_status == "auto" and public_surface else ("internal" if not public_surface else "restricted")
        allowed_usage = PUBLIC_ALLOWED_USAGE[:] if visibility == "public_safe" else (["internal_only"] if not public_surface else [])
        public_beat = candidate_text.rstrip(".") + "." if candidate_text else ""
        beats.append(
            {
                "id": f"story-policy-{index + 1}",
                "raw_story_beat": raw_text,
                "public_story_beat": public_beat,
                "visibility": visibility,
                "transform_rule": transform_rule,
                "allowed_usage": allowed_usage,
                "evidence_type": "anecdote",
                "approval_status": approval_status,
                "policy_notes": sorted(set(note for note in policy_notes if note)),
            }
        )
    return beats


def render_policy_approved_story_beats(
    *,
    public_safe_story_beats: list[dict[str, Any]],
    content_type: str,
) -> list[str]:
    if content_type not in PUBLIC_SOCIAL_CONTENT_TYPES:
        return [
            _normalize_text(item.get("raw_story_beat"))
            for item in public_safe_story_beats
            if _normalize_text(item.get("raw_story_beat"))
        ]
    approved: list[str] = []
    seen: set[str] = set()
    for item in public_safe_story_beats:
        if str(item.get("approval_status") or "") != "auto":
            continue
        if content_type not in list(item.get("allowed_usage") or []):
            continue
        rendered = _normalize_text(item.get("public_story_beat"))
        if not rendered or rendered.lower() in seen:
            continue
        seen.add(rendered.lower())
        approved.append(rendered)
    return approved[:3]
