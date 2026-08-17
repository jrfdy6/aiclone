from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Mapping, Sequence


EVIDENCE_CONTRACT_VERSION = "feezie_publish_ready_evidence/v1"
EVIDENCE_READINESS_VERSION = "feezie_evidence_readiness/v1"
EVIDENCE_KEYS = ("concrete_action", "exact_problem", "observable_lesson")
EVIDENCE_QUESTIONS = {
    "concrete_action": "What did you actually build, change, test, or decide here?",
    "exact_problem": "What exact problem or failure made that work necessary?",
    "observable_lesson": "What did you observe or learn from it?",
}

_PATH_RE = re.compile(r"(?:/Users|/home|/private|/tmp)/[^\s,;]+", re.IGNORECASE)
_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s,;]+")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|[A-Fa-f0-9]{32,}|[A-Za-z0-9_-]{48,})\b")
_METRIC_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?%?(?!\w)")
_SPACE_RE = re.compile(r"\s+")
_PUNCT_SPACE_RE = re.compile(r"\s+([,.;:!?])")
_LABELED_EVIDENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<label>observable[ \t]+lesson|action|problem)[ \t]*:",
    re.IGNORECASE,
)
_TRAILING_POST_INSTRUCTION_RE = re.compile(
    r"(?:^|(?<=[.!?])\s+|[\r\n]+)"
    r"(?=(?:"
    r"keep[ \t]+(?:the|this)[ \t]+post\b|"
    r"signal[ \t]+that\b|"
    r"write[ \t]+(?:the|this)[ \t]+post\b|"
    r"(?:the|this)[ \t]+post[ \t]+should\b|"
    r"do[ \t]+not[ \t]+(?:mention|name|say|imply|discuss)\b|"
    r"don['’]t[ \t]+(?:mention|name|say|imply|discuss)\b|"
    r"avoid[ \t]+(?:mentioning|naming|saying|implying|discussing)\b|"
    r"tone[ \t]*:|audience[ \t]*:"
    r"))",
    re.IGNORECASE,
)
_LABELED_EVIDENCE_KEYS = {
    "action": "concrete_action",
    "problem": "exact_problem",
    "observable lesson": "observable_lesson",
}
_KNOWN_INTERNAL_REPLACEMENTS = (
    (re.compile(r"\bAI\s+Clone\b", re.IGNORECASE), "my AI system"),
    (re.compile(r"\bFeezie\s+OS\b", re.IGNORECASE), "the content system"),
    (re.compile(r"\bFEEZIE\b", re.IGNORECASE), "the content system"),
    (re.compile(r"\bDream\s+Cycle\b", re.IGNORECASE), "an internal review cycle"),
    (re.compile(r"\bJean-Claude\b", re.IGNORECASE), "an internal agent"),
    (re.compile(r"\bNeo\b", re.IGNORECASE), "an internal review agent"),
    (re.compile(r"\bYoda\b", re.IGNORECASE), "an internal review agent"),
    (re.compile(r"\bOpenClaw\b", re.IGNORECASE), "an internal agent"),
    (re.compile(r"\bRailway\b", re.IGNORECASE), "the hosted application"),
    (re.compile(r"\bCodex\b", re.IGNORECASE), "the local coding runner"),
    (re.compile(r"\bfusion-os\b", re.IGNORECASE), "an internal workspace"),
    (re.compile(r"\blinkedin-content-os\b", re.IGNORECASE), "the content workflow"),
    (re.compile(r"\bshared_ops\b", re.IGNORECASE), "the shared workflow"),
)


def _configured_private_replacements() -> tuple[tuple[re.Pattern[str], str], ...]:
    """Load owner-specific literal replacements exclusively from private runtime config."""

    raw = str(os.getenv("AI_CLONE_PUBLIC_REDACTION_MAP_JSON") or "").strip()
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    configured_values: list[tuple[str, str]] = []
    for private_value, replacement in payload.items():
        private_text = str(private_value or "").strip()
        public_text = str(replacement or "").strip()
        if len(private_text) < 4 or not public_text:
            continue
        configured_values.append((private_text, public_text))
    configured_values.sort(key=lambda item: (-len(item[0]), item[0].casefold()))
    return tuple(
        (re.compile(re.escape(private_text), re.IGNORECASE), public_text)
        for private_text, public_text in configured_values
    )


_ACTION_RE = re.compile(
    r"\b(?:added|audited|built|changed|compared|configured|connected|created|debugged|decided|deployed|"
    r"designed|documented|fixed|implemented|integrated|introduced|mapped|measured|moved|ran|rebuilt|"
    r"refactored|removed|replaced|reviewed|rewired|rewrote|set\s+up|shipped|started|stopped|tested|traced|turned)\b",
    re.IGNORECASE,
)
_ACTION_OBJECT_RE = re.compile(
    r"\b(?:artifact|automation|bridge|check|component|content|dashboard|document|draft|experiment|frontend|"
    r"gate|handoff|interface|job|page|playbook|post|process|prompt|queue|receipt|record|retrieval|route|"
    r"runner|script|service|step|system|test|tool|workflow)\b",
    re.IGNORECASE,
)
_PROBLEM_RE = re.compile(
    r"\b(?:abstract|blocked|broke|broken|conflict|conflicting|drift|drifted|duplicate|empty|failed|failure|"
    r"generic|inconsistent|incorrect|lacked|lost|missing|nonspecific|open-ended|scattered|stale|stuck|unclear|"
    r"unfinished|unreliable|vague|wrong)\b|\bnothing\s+(?:concrete|specific)\b|"
    r"\b(?:could|did|was|were|would)(?:n['’]t| not)\b",
    re.IGNORECASE,
)
_LESSON_RE = re.compile(
    r"\b(?:became clear|confirmed|discovered|found|learned|noticed|observed|realized|revealed|showed|taught|what changed|works better|"
    r"gets stronger|improves|matters most|the useful lesson)\b",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"^(?:n/?a|none|nothing|not sure|unknown|tbd|todo|something|the thing|general|general idea)[.!]?$",
    re.IGNORECASE,
)
_TOPIC_STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "before",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "why",
    "with",
}
_GENERIC_TOPIC_TERMS = {
    "ai",
    "content",
    "education",
    "future",
    "idea",
    "leadership",
    "linkedin",
    "post",
    "system",
    "tech",
    "technical",
    "technology",
    "workflow",
    "work",
}
_TOPIC_TOKEN_ALIASES = {
    "drafts": "draft",
    "failed": "fail",
    "failure": "fail",
    "failures": "fail",
    "lessons": "lesson",
    "loops": "loop",
    "problems": "problem",
    "schools": "school",
    "tests": "test",
    "tested": "test",
    "testing": "test",
    "transitions": "transition",
}


def _clean_text(value: Any, *, privacy_mode: bool = False, limit: int = 1200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _PATH_RE.sub("a private artifact", text)
    text = _WINDOWS_PATH_RE.sub("a private artifact", text)
    text = _EMAIL_RE.sub("a colleague", text)
    text = _TOKEN_RE.sub("a private identifier", text)
    for pattern, replacement in _KNOWN_INTERNAL_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    if privacy_mode:
        for pattern, replacement in _configured_private_replacements():
            text = pattern.sub(replacement, text)
        text = _METRIC_RE.sub("an internal measure", text)
    text = _PUNCT_SPACE_RE.sub(r"\1", _SPACE_RE.sub(" ", text)).strip(" -,:;")
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" -,:;")
    return text


def anonymize_feezie_public_text(value: Any, *, limit: int = 1200) -> str:
    """Return a bounded public-facing projection for remote execution prompts."""

    return _clean_text(value, privacy_mode=True, limit=limit)


def _evidence_value(key: str, value: Any, *, privacy_mode: bool = False) -> str:
    return _clean_text(value, privacy_mode=privacy_mode)


def _usable(value: str, *, minimum_words: int = 4) -> bool:
    if not value or _PLACEHOLDER_RE.fullmatch(value.strip()):
        return False
    return len(re.findall(r"[A-Za-z0-9]+", value)) >= minimum_words


def _specific_evidence_value(key: str, value: str) -> bool:
    """Reject fluent placeholders before they can become a publish-ready contract."""

    if not _usable(value, minimum_words=5):
        return False
    if key == "concrete_action":
        return bool(_ACTION_RE.search(value))
    if key == "exact_problem":
        return bool(_PROBLEM_RE.search(value))
    if key == "observable_lesson":
        return bool(_LESSON_RE.search(value))
    return False


def _privacy_mode(source_card: Mapping[str, Any]) -> bool:
    return str(source_card.get("proof_posture") or "").strip().lower() == "verified_private_anonymize" or str(
        source_card.get("employer_proximity") or ""
    ).strip().lower() in {"generalized_work", "employer_specific"}


def parse_feezie_labeled_evidence_context(value: Any) -> dict[str, Any]:
    """Parse the owner's explicitly labeled evidence without interpreting free prose.

    Labels must be unique standalone tokens. Once any supported label is
    present, a partial or duplicate triplet is invalid so retrieval cannot silently
    complete a different story. Recognized post-writing instructions after the
    observable lesson stay outside the evidence projection.
    """

    text = str(value or "").strip()
    matches = list(_LABELED_EVIDENCE_RE.finditer(text))
    if not matches:
        return {
            "detected": False,
            "valid": False,
            "values": {},
            "present_fields": [],
            "missing_fields": [],
            "duplicate_fields": [],
            "block_reason": None,
        }

    occurrences: dict[str, list[str]] = {key: [] for key in EVIDENCE_KEYS}
    for index, match in enumerate(matches):
        label = _SPACE_RE.sub(" ", str(match.group("label") or "").strip().lower())
        key = _LABELED_EVIDENCE_KEYS[label]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        candidate = text[match.end():end].strip()
        if key == "observable_lesson":
            instruction = _TRAILING_POST_INSTRUCTION_RE.search(candidate)
            if instruction is not None:
                candidate = candidate[:instruction.start()].strip()
        occurrences[key].append(candidate)

    duplicate_fields = [key for key in EVIDENCE_KEYS if len(occurrences[key]) > 1]
    values = {
        key: entries[0]
        for key, entries in occurrences.items()
        if len(entries) == 1 and entries[0].strip()
    }
    missing_fields = [key for key in EVIDENCE_KEYS if len(occurrences[key]) != 1 or not values.get(key)]
    block_reason = None
    if duplicate_fields:
        block_reason = "owner_labeled_evidence_duplicate"
    elif missing_fields:
        block_reason = "owner_labeled_evidence_partial"
    return {
        "detected": True,
        "valid": not duplicate_fields and not missing_fields,
        "values": values,
        "present_fields": [key for key in EVIDENCE_KEYS if key in values and key not in duplicate_fields],
        "missing_fields": missing_fields,
        "duplicate_fields": duplicate_fields,
        "block_reason": block_reason,
    }


def _topic_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    for raw_token in re.findall(r"[a-z0-9]+", str(value or "").lower()):
        token = _TOPIC_TOKEN_ALIASES.get(raw_token, raw_token)
        if len(token) < 3 or token in _TOPIC_STOPWORDS or token in _GENERIC_TOPIC_TERMS:
            continue
        terms.add(token)
    return terms


def _record_is_topically_relevant(record: Mapping[str, Any], *, topic: str) -> bool:
    """Fail closed unless a stored lesson directly overlaps the requested subject.

    Broad lane words such as ``AI``, ``content``, and ``system`` are deliberately
    ignored. A multi-term topic needs two direct public-field matches, or one match
    carried by the lesson's explicit safe-angle/topic tags. This keeps an otherwise
    concrete record from becoming false lived evidence for an unrelated post.
    """

    requested_terms = _topic_terms(topic)
    if not requested_terms:
        return False
    public_terms = _topic_terms(
        " ".join(
            str(record.get(key) or "")
            for key in ("public_proof", "macro_thesis", "public_takeaway")
        )
    )
    tagged_terms = _topic_terms(f"{record.get('safe_angle') or ''} {record.get('topic_tags') or ''}")
    if requested_terms & tagged_terms:
        return True
    overlap = requested_terms & public_terms
    return bool(overlap) if len(requested_terms) == 1 else len(overlap) >= 2


def _public_safe_lesson_records(content_signal_chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in content_signal_chunks:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        if str(metadata.get("visibility") or "").strip().lower() != "public_safe":
            continue
        if str(metadata.get("source_kind") or "").strip() != "content_safe_operator_lessons":
            continue
        record = {
            "record_id": _clean_text(item.get("source_id") or metadata.get("source") or "")[:160],
            "public_proof": _clean_text(metadata.get("public_proof")),
            "macro_thesis": _clean_text(metadata.get("macro_thesis")),
            "public_takeaway": _clean_text(metadata.get("public_takeaway")),
            "safe_angle": _clean_text(metadata.get("safe_angle")),
            "topic_tags": _clean_text(" ".join(str(item) for item in (metadata.get("topic_tags") or []))),
        }
        if any(record.get(key) for key in ("public_proof", "macro_thesis", "public_takeaway")):
            records.append(record)
    return records


def _record_projection(record: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    proof = _clean_text(record.get("public_proof"))
    thesis = _clean_text(record.get("macro_thesis"))
    takeaway = _clean_text(record.get("public_takeaway"))
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    if _usable(proof, minimum_words=6) and _ACTION_RE.search(proof) and _ACTION_OBJECT_RE.search(proof):
        values["concrete_action"] = proof
        sources["concrete_action"] = "retrieved_public_safe_record"
    problem_candidates = (thesis, takeaway, proof)
    for candidate in problem_candidates:
        if _usable(candidate, minimum_words=7) and _PROBLEM_RE.search(candidate):
            values["exact_problem"] = candidate
            sources["exact_problem"] = "retrieved_public_safe_record"
            break
    for candidate in (takeaway, thesis):
        if _usable(candidate, minimum_words=6) and _LESSON_RE.search(candidate):
            values["observable_lesson"] = candidate
            sources["observable_lesson"] = "retrieved_public_safe_record"
            break
    return values, sources


def _best_retrieved_projection(
    content_signal_chunks: Sequence[Mapping[str, Any]],
    *,
    topic: str,
) -> tuple[dict[str, str], dict[str, str], str]:
    best_values: dict[str, str] = {}
    best_sources: dict[str, str] = {}
    best_record_id = ""
    for record in _public_safe_lesson_records(content_signal_chunks):
        if not _record_is_topically_relevant(record, topic=topic):
            continue
        values, sources = _record_projection(record)
        if len(values) > len(best_values):
            best_values = values
            best_sources = sources
            best_record_id = str(record.get("record_id") or "")
    return best_values, best_sources, best_record_id


def _source_card_projection(source_card: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    privacy_mode = _privacy_mode(source_card)
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    for key in EVIDENCE_KEYS:
        value = _evidence_value(key, source_card.get(key), privacy_mode=privacy_mode)
        if _specific_evidence_value(key, value):
            values[key] = value
            sources[key] = "typed_public_safe_source_card"
    return values, sources


def _owner_projection(owner_answers: Mapping[str, Any], *, privacy_mode: bool) -> tuple[dict[str, str], dict[str, str]]:
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    for key in EVIDENCE_KEYS:
        value = _evidence_value(key, owner_answers.get(key), privacy_mode=privacy_mode)
        if _specific_evidence_value(key, value):
            values[key] = value
            sources[key] = "owner_clarification"
    return values, sources


def _labeled_owner_projection(
    labeled_values: Mapping[str, Any],
    *,
    privacy_mode: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    for key in EVIDENCE_KEYS:
        value = _evidence_value(key, labeled_values.get(key), privacy_mode=privacy_mode)
        # The explicit ``Observable lesson:`` label supplies the semantic posture;
        # keep the owner's sentence intact instead of requiring it to repeat
        # "I learned" inside the value. Action and problem retain their stricter
        # content checks.
        specific = (
            _usable(value, minimum_words=5)
            if key == "observable_lesson"
            else _specific_evidence_value(key, value)
        )
        if specific:
            values[key] = value
            sources[key] = "owner_labeled_context"
    return values, sources


def _clarification_receipt(
    *,
    values: Mapping[str, Any],
    sources: Mapping[str, str],
    missing_fields: Sequence[str],
    clarification_key: str,
    clarification_question: str,
    block_reason: str,
    retrieved_record_id: str = "",
) -> dict[str, Any]:
    receipt = {
        "schema_version": EVIDENCE_READINESS_VERSION,
        "status": "clarification_required",
        "ready": False,
        "missing_fields": list(missing_fields),
        "present_fields": [key for key in EVIDENCE_KEYS if key in values],
        "field_sources": {key: sources[key] for key in EVIDENCE_KEYS if key in sources},
        "clarification_key": clarification_key,
        "clarification_question": clarification_question,
        "block_reason": block_reason,
        "retrieved_record_id_sha256": (
            hashlib.sha256(retrieved_record_id.encode("utf-8")).hexdigest() if retrieved_record_id else ""
        ),
    }
    receipt["receipt_sha256"] = _contract_hash(receipt)
    return receipt


def _contract_hash(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(dict(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def complete_test_evidence_contract() -> dict[str, Any]:
    """Return a concrete fixture for legacy route tests; production code never calls this helper."""

    payload = {
        "schema_version": EVIDENCE_CONTRACT_VERSION,
        "status": "ready",
        "author_posture": "learning_in_public",
        "concrete_action": "I changed a workflow and added a review checkpoint before work could advance.",
        "exact_problem": "The earlier workflow allowed unfinished work to look complete and created avoidable rework.",
        "observable_lesson": "I learned that visible closure matters more than adding another layer of automation.",
        "field_sources": {key: "test_fixture" for key in EVIDENCE_KEYS},
        "retrieved_record_id_sha256": "",
        "missing_fields": [],
    }
    payload["contract_sha256"] = _contract_hash(payload)
    return payload


def evaluate_feezie_evidence_readiness(
    *,
    topic: str = "",
    owner_context: Any = None,
    owner_answers: Mapping[str, Any] | None = None,
    source_card: Mapping[str, Any] | None = None,
    content_signal_chunks: Sequence[Mapping[str, Any]] | None = None,
    qualification_route: str | None = None,
    existing_owner_question: str | None = None,
) -> dict[str, Any]:
    """Build the public-safe evidence contract or return exactly one clarification question.

    This consumes only already-public-safe projections. It never copies raw proof, raw stories,
    source paths, or private operator records into an incomplete readiness receipt.
    """

    source_card = dict(source_card or {})
    owner_answers = dict(owner_answers or {})
    privacy_mode = _privacy_mode(source_card)
    labeled_context = parse_feezie_labeled_evidence_context(owner_context)

    retrieved_values, retrieved_sources, retrieved_record_id = _best_retrieved_projection(
        content_signal_chunks or [],
        topic=_clean_text(topic, limit=320),
    )
    source_values, source_sources = _source_card_projection(source_card)
    labeled_values, labeled_sources = _labeled_owner_projection(
        labeled_context.get("values") or {},
        privacy_mode=privacy_mode,
    )
    owner_values, owner_sources = _owner_projection(owner_answers, privacy_mode=privacy_mode)

    values = {**retrieved_values, **source_values, **labeled_values, **owner_values}
    sources = {**retrieved_sources, **source_sources, **labeled_sources, **owner_sources}
    missing = [key for key in EVIDENCE_KEYS if key not in values]
    route = _clean_text(qualification_route or source_card.get("qualification_route")).lower()
    known_question = _clean_text(existing_owner_question or source_card.get("owner_question"), limit=320)

    if route in {"discard", "discarded"}:
        return {
            "schema_version": EVIDENCE_READINESS_VERSION,
            "status": "blocked",
            "ready": False,
            "missing_fields": missing or list(EVIDENCE_KEYS),
            "present_fields": [key for key in EVIDENCE_KEYS if key in values],
            "field_sources": {key: sources[key] for key in EVIDENCE_KEYS if key in sources},
            "clarification_key": None,
            "clarification_question": None,
            "block_reason": "qualification_discarded",
            "retrieved_record_id_sha256": hashlib.sha256(retrieved_record_id.encode("utf-8")).hexdigest() if retrieved_record_id else "",
        }

    if labeled_context.get("detected") and not labeled_context.get("valid"):
        duplicate_fields = [
            key for key in EVIDENCE_KEYS if key in set(labeled_context.get("duplicate_fields") or [])
        ]
        owner_layer_values = {**labeled_values, **owner_values}
        owner_layer_sources = {**labeled_sources, **owner_sources}
        # A later, explicit clarification answer is authoritative for a label
        # that was missing from the original context. Duplicate labels remain
        # ambiguous and must be corrected rather than guessed around.
        invalid_fields = duplicate_fields or [
            key for key in EVIDENCE_KEYS if key not in owner_layer_values
        ]
        if not invalid_fields:
            labeled_context = {**labeled_context, "valid": True}
        else:
            next_key = invalid_fields[0]
            return _clarification_receipt(
                values=owner_layer_values,
                sources=owner_layer_sources,
                missing_fields=invalid_fields,
                clarification_key=next_key,
                clarification_question=EVIDENCE_QUESTIONS[next_key],
                block_reason=(
                    "owner_labeled_evidence_duplicate"
                    if duplicate_fields
                    else "owner_labeled_evidence_partial"
                ),
            )

    if labeled_context.get("detected"):
        owner_layer_values = {**labeled_values, **owner_values}
        owner_layer_sources = {**labeled_sources, **owner_sources}
        owner_layer_missing = [key for key in EVIDENCE_KEYS if key not in owner_layer_values]
        if owner_layer_missing:
            next_key = owner_layer_missing[0]
            return _clarification_receipt(
                values=owner_layer_values,
                sources=owner_layer_sources,
                missing_fields=owner_layer_missing,
                clarification_key=next_key,
                clarification_question=EVIDENCE_QUESTIONS[next_key],
                block_reason="owner_labeled_evidence_nonspecific",
            )

    if missing or route == "latent":
        next_key = missing[0] if missing else "exact_problem"
        question = known_question if route == "latent" and known_question else EVIDENCE_QUESTIONS[next_key]
        receipt = {
            "schema_version": EVIDENCE_READINESS_VERSION,
            "status": "clarification_required",
            "ready": False,
            "missing_fields": missing or [next_key],
            "present_fields": [key for key in EVIDENCE_KEYS if key in values],
            "field_sources": {key: sources[key] for key in EVIDENCE_KEYS if key in sources},
            "clarification_key": next_key,
            "clarification_question": question,
            "block_reason": "qualification_latent" if route == "latent" else "evidence_incomplete",
            "retrieved_record_id_sha256": hashlib.sha256(retrieved_record_id.encode("utf-8")).hexdigest() if retrieved_record_id else "",
        }
        receipt["receipt_sha256"] = _contract_hash(receipt)
        return receipt

    retrieved_record_used = any(source == "retrieved_public_safe_record" for source in sources.values())
    admitted_retrieved_record_id = retrieved_record_id if retrieved_record_used else ""
    contract = {
        "schema_version": EVIDENCE_CONTRACT_VERSION,
        "status": "ready",
        "author_posture": "learning_in_public",
        **{key: values[key] for key in EVIDENCE_KEYS},
        "field_sources": {key: sources[key] for key in EVIDENCE_KEYS},
        "retrieved_record_id_sha256": (
            hashlib.sha256(admitted_retrieved_record_id.encode("utf-8")).hexdigest()
            if admitted_retrieved_record_id
            else ""
        ),
        "missing_fields": [],
    }
    contract["contract_sha256"] = _contract_hash(contract)
    return {
        "schema_version": EVIDENCE_READINESS_VERSION,
        "status": "ready",
        "ready": True,
        "missing_fields": [],
        "present_fields": list(EVIDENCE_KEYS),
        "field_sources": dict(contract["field_sources"]),
        "clarification_key": None,
        "clarification_question": None,
        "block_reason": None,
        "retrieved_record_id_sha256": contract["retrieved_record_id_sha256"],
        "contract": contract,
        "receipt_sha256": _contract_hash(
            {
                "schema_version": EVIDENCE_READINESS_VERSION,
                "status": "ready",
                "contract_sha256": contract["contract_sha256"],
            }
        ),
    }
