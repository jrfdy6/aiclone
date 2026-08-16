from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

import fcntl


APPROVED_PROVENANCE = frozenset({"human_published", "human_edited"})
APPROVED_STATUSES = frozenset({"approved", "verified"})
CLOUD_SAFE_PRIVACY = frozenset({"public", "cloud_ok_excerpt"})
LOCAL_SAFE_PRIVACY = frozenset({"public", "cloud_ok_excerpt", "local_only"})
POSITIVE_KINDS = frozenset({"positive", "voice_example"})
VOICE_REVIEW_PACKET_SCHEMA_VERSION = "ai_clone_voice_review/v1"
VOICE_REVIEW_PACKET_SOURCE = "feezie_owner_review"
VOICE_REVIEW_DECISIONS = frozenset({"approve", "revise", "park"})
MAX_VOICE_REVIEW_PACKET_BYTES = 256 * 1024
DEFAULT_STOCK_PHRASES = (
    "that is the operating model",
    "the workflow tells the truth",
    "operator clarity wins",
    "clarity keeps the advantage",
    "read that again",
    "write that down",
)
VOICE_MIN_RELEVANCE = 0.2
VOICE_MIN_SEMANTIC_SUPPORT = 0.68
VOICE_RETRIEVAL_NOISE_TERMS = frozenset(
    {
        "audience",
        "category",
        "content",
        "direct",
        "expert",
        "invitation",
        "linkedin",
        "post",
        "posts",
        "tone",
        "type",
        "value",
    }
)
VOICE_ROUTING_FIELDS = (
    "audience",
    "canonical_pillar",
    "career_signal",
    "employer_proximity",
    "treatment",
    "domain",
    "lane",
)
VOICE_ROUTE_DOMAIN_PRIORITY = (
    "domain",
    "canonical_pillar",
    "treatment",
    "career_signal",
    "audience",
    "lane",
)
VOICE_ROUTE_DOMAIN_MARKERS = {
    "tech_ai": frozenset(
        {
            "ai",
            "ai native",
            "ai systems",
            "automation",
            "practical ai systems",
            "product operations",
            "tech ai",
            "tech proof",
            "technical program",
            "technology",
        }
    ),
    "education": frozenset(
        {
            "admissions",
            "education",
            "education admissions",
            "education anchor",
            "family referral and trust building systems",
            "students",
            "trust systems",
        }
    ),
    "leadership": frozenset(
        {
            "leadership",
            "leadership operator",
            "operator leadership",
            "program leadership",
        }
    ),
}
VOICE_ENTRY_DOMAIN_MARKERS = {
    "tech_ai": frozenset(
        {
            "agent",
            "agents",
            "ai",
            "ai systems",
            "artificial intelligence",
            "automation",
            "coding",
            "model",
            "models",
            "product",
            "product operations",
            "software",
            "systems",
            "tech",
            "technical",
            "technology",
            "tool",
            "tools",
            "workflow",
            "workflows",
        }
    ),
    "education": frozenset(
        {
            "admissions",
            "education",
            "families",
            "family",
            "post secondary",
            "school",
            "student",
            "students",
            "trust",
        }
    ),
    "leadership": frozenset(
        {
            "communication",
            "executive presence",
            "leadership",
            "management",
            "operator leadership",
            "professional development",
        }
    ),
}
VOICE_PERSONAL_BUILD_MARKERS = frozenset(
    {
        "automation",
        "build",
        "builder",
        "building",
        "design",
        "experiment",
        "personal build",
        "product",
        "project",
        "shipped",
        "software",
        "systems",
        "tool",
        "workflow",
    }
)
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "here",
        "hers",
        "him",
        "his",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "she",
        "so",
        "that",
        "the",
        "their",
        "them",
        "there",
        "they",
        "this",
        "to",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    }
)
FUNCTION_WORDS = STOPWORDS | frozenset(
    {
        "about",
        "after",
        "again",
        "all",
        "also",
        "because",
        "before",
        "can",
        "could",
        "did",
        "do",
        "does",
        "how",
        "just",
        "more",
        "most",
        "no",
        "not",
        "now",
        "only",
        "out",
        "over",
        "should",
        "then",
        "through",
        "too",
        "up",
        "very",
        "why",
        "would",
    }
)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "]",
    flags=re.UNICODE,
)
_EMBEDDING_CACHE: dict[tuple[str, str], list[float]] = {}
_OLLAMA_UNAVAILABLE_UNTIL = 0.0


def resolve_voice_corpus_path() -> Path:
    explicit = (os.getenv("AI_CLONE_VOICE_CORPUS_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    state_root = (os.getenv("AI_CLONE_STATE_ROOT") or "").strip()
    if state_root:
        return Path(state_root).expanduser() / "persona" / "voice_corpus.jsonl"
    return Path.home() / ".codex" / "ai-clone" / "state" / "persona" / "voice_corpus.jsonl"


def resolve_voice_preference_path() -> Path:
    explicit = (os.getenv("AI_CLONE_VOICE_PREFERENCE_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return resolve_voice_corpus_path().with_name("voice_preferences.jsonl")


def resolve_voice_influence_path() -> Path:
    explicit = (os.getenv("AI_CLONE_VOICE_INFLUENCE_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return resolve_voice_corpus_path().with_name("voice_influences.jsonl")


def _clean_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", text.lower())


def _topic_words(text: str) -> list[str]:
    return [word for word in _words(text) if word not in STOPWORDS and len(word) > 1]


def _normalize_route_label(value: Any) -> str:
    if isinstance(value, (list, tuple, set, frozenset)):
        return " ".join(
            part
            for part in (_normalize_route_label(item) for item in value)
            if part
        )
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .split()
    )


def _merge_routing_metadata(
    routing_metadata: dict[str, Any] | None = None,
    **routing_fields: Any,
) -> dict[str, Any]:
    merged = dict(routing_metadata) if isinstance(routing_metadata, dict) else {}
    for field in VOICE_ROUTING_FIELDS:
        value = routing_fields.get(field)
        if value not in (None, "", [], {}):
            merged[field] = value
    return {
        field: merged.get(field)
        for field in VOICE_ROUTING_FIELDS
        if merged.get(field) not in (None, "", [], {})
    }


def _label_matches_any(label: str, markers: frozenset[str]) -> bool:
    if not label:
        return False
    return any(label == marker or f" {marker} " in f" {label} " for marker in markers)


def _voice_route_constraints(routing_metadata: dict[str, Any] | None) -> dict[str, Any]:
    metadata = _merge_routing_metadata(routing_metadata)
    target_domain: str | None = None
    domain_source: str | None = None
    for field in VOICE_ROUTE_DOMAIN_PRIORITY:
        label = _normalize_route_label(metadata.get(field))
        if not label:
            continue
        for domain_name, markers in VOICE_ROUTE_DOMAIN_MARKERS.items():
            if _label_matches_any(label, markers):
                target_domain = domain_name
                domain_source = field
                break
        if target_domain:
            break

    employer_proximity = _normalize_route_label(metadata.get("employer_proximity"))
    treatment = _normalize_route_label(metadata.get("treatment"))
    lane = _normalize_route_label(metadata.get("lane"))
    personal_build_required = bool(
        employer_proximity == "personal build"
        or "personal technology" in treatment
        or lane == "build in public"
    )
    return {
        "domain": target_domain,
        "domain_source": domain_source,
        "personal_build_required": personal_build_required,
        "metadata_fields": sorted(metadata),
    }


def _entry_routing_labels(entry: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    values: list[Any] = []
    for field in (
        "topic_tags",
        "domain_tags",
        "audience_tags",
        "domain",
        "audience",
        "canonical_pillar",
        "career_signal",
        "employer_proximity",
        "treatment",
        "lane",
        "post_type",
    ):
        value = entry.get(field)
        if isinstance(value, (list, tuple, set, frozenset)):
            values.extend(value)
        elif value not in (None, ""):
            values.append(value)
    for value in values:
        label = _normalize_route_label(value)
        if not label:
            continue
        labels.add(label)
        labels.update(_topic_words(label))
    return labels


def _voice_entry_is_route_compatible(
    entry: dict[str, Any],
    *,
    constraints: dict[str, Any],
) -> bool:
    labels = _entry_routing_labels(entry)
    target_domain = str(constraints.get("domain") or "")
    if target_domain:
        markers = VOICE_ENTRY_DOMAIN_MARKERS.get(target_domain, frozenset())
        if markers and not labels.intersection(markers):
            return False
    if constraints.get("personal_build_required") and not labels.intersection(VOICE_PERSONAL_BUILD_MARKERS):
        return False
    return True


def _voice_retrieval_query(query: str) -> str:
    return " ".join(
        word
        for word in _topic_words(query)
        if word not in VOICE_RETRIEVAL_NOISE_TERMS
    )


def _normalized_kind(entry: dict[str, Any]) -> str:
    return str(entry.get("kind") or "positive").strip().lower()


def _is_approved_positive(entry: dict[str, Any], *, execution_mode: str) -> bool:
    provenance = str(entry.get("provenance") or "").strip().lower()
    approval = str(entry.get("approval_status") or entry.get("approval") or "").strip().lower()
    privacy = str(entry.get("privacy") or "").strip().lower()
    allowed_privacy = LOCAL_SAFE_PRIVACY if execution_mode == "strict_local" else CLOUD_SAFE_PRIVACY
    return (
        _normalized_kind(entry) in POSITIVE_KINDS
        and provenance in APPROVED_PROVENANCE
        and approval in APPROVED_STATUSES
        and privacy in allowed_privacy
        and len(_clean_text(entry.get("text"))) >= 40
    )


def load_voice_corpus(
    path: Path | str | None = None,
    *,
    execution_mode: str = "cloud",
) -> list[dict[str, Any]]:
    """Load only owner-authored, approved positive examples safe for the execution mode.

    `cloud` is also the correct mode for the local Codex bridge: the bridge runs on
    the owner's machine, but Codex inference is remote. `strict_local` is reserved
    for an on-device model and may include `local_only` examples.
    """

    corpus_path = Path(path).expanduser() if path is not None else resolve_voice_corpus_path()
    if not corpus_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw_line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            raw_entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw_entry, dict) or not _is_approved_positive(raw_entry, execution_mode=execution_mode):
            continue
        text = _clean_text(raw_entry.get("text"))
        entry_id = str(raw_entry.get("id") or hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]).strip()
        if not entry_id or entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        entries.append(
            {
                **raw_entry,
                "id": entry_id,
                "text": text,
                "kind": _normalized_kind(raw_entry),
                "provenance": str(raw_entry.get("provenance") or "").strip().lower(),
                "approval_status": str(raw_entry.get("approval_status") or raw_entry.get("approval") or "").strip().lower(),
                "privacy": str(raw_entry.get("privacy") or "").strip().lower(),
                "channel": str(raw_entry.get("channel") or "linkedin").strip().lower(),
                "post_type": str(raw_entry.get("post_type") or "unspecified").strip().lower(),
                "topic_tags": [str(tag).strip().lower() for tag in (raw_entry.get("topic_tags") or []) if str(tag).strip()],
            }
        )
    return entries


def audit_voice_corpus(path: Path | str | None = None) -> dict[str, Any]:
    corpus_path = Path(path).expanduser() if path is not None else resolve_voice_corpus_path()
    counts: Counter[str] = Counter()
    valid_json_records: list[dict[str, Any]] = []
    if corpus_path.exists():
        for line in corpus_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            counts["lines"] += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                counts["invalid_json"] += 1
                continue
            if not isinstance(entry, dict):
                counts["invalid_record"] += 1
                continue
            valid_json_records.append(entry)
            counts[f"provenance:{str(entry.get('provenance') or 'missing').lower()}"] += 1
            counts[f"privacy:{str(entry.get('privacy') or 'missing').lower()}"] += 1
            counts[f"approval:{str(entry.get('approval_status') or entry.get('approval') or 'missing').lower()}"] += 1
    cloud_entries = load_voice_corpus(corpus_path, execution_mode="cloud")
    local_entries = load_voice_corpus(corpus_path, execution_mode="strict_local")
    counts["valid_json"] = len(valid_json_records)
    counts["cloud_eligible"] = len(cloud_entries)
    counts["strict_local_eligible"] = len(local_entries)
    return {
        "path": str(corpus_path),
        "exists": corpus_path.exists(),
        "counts": dict(sorted(counts.items())),
        "corpus_digest": voice_corpus_digest(local_entries),
        "minimum_recommended_met": len(cloud_entries) >= 15,
        "strong_reference_target_met": len(cloud_entries) >= 30,
    }


def load_voice_influences(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load approved external technique cards without treating them as owner voice."""

    influence_path = Path(path).expanduser() if path is not None else resolve_voice_influence_path()
    if not influence_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line in influence_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw_entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw_entry, dict):
            continue
        entry_id = str(raw_entry.get("id") or "").strip()
        provenance = str(raw_entry.get("provenance") or "").strip().lower()
        approval = str(raw_entry.get("approval_status") or "").strip().lower()
        privacy = str(raw_entry.get("privacy") or "").strip().lower()
        techniques = [
            _clean_text(technique)
            for technique in (raw_entry.get("techniques") or [])
            if _clean_text(technique)
        ]
        if (
            not entry_id
            or entry_id in seen_ids
            or provenance != "external_influence"
            or approval not in APPROVED_STATUSES
            or privacy not in CLOUD_SAFE_PRIVACY
            or not techniques
        ):
            continue
        seen_ids.add(entry_id)
        entries.append(
            {
                **raw_entry,
                "id": entry_id,
                "provenance": provenance,
                "approval_status": approval,
                "privacy": privacy,
                "techniques": techniques,
                "avoid": [_clean_text(item) for item in (raw_entry.get("avoid") or []) if _clean_text(item)],
                "topic_tags": [str(tag).strip().lower() for tag in (raw_entry.get("topic_tags") or []) if str(tag).strip()],
                "text": " ".join(
                    [
                        _clean_text(raw_entry.get("label")),
                        *techniques,
                        *[_clean_text(item) for item in (raw_entry.get("topic_tags") or [])],
                    ]
                ),
            }
        )
    return entries


def voice_corpus_digest(entries: Sequence[dict[str, Any]]) -> str:
    safe_manifest = [
        {
            "id": str(entry.get("id") or ""),
            "text_hash": hashlib.sha256(_clean_text(entry.get("text")).encode("utf-8")).hexdigest(),
            "provenance": str(entry.get("provenance") or ""),
            "privacy": str(entry.get("privacy") or ""),
            "approval_status": str(entry.get("approval_status") or ""),
        }
        for entry in entries
    ]
    serialized = json.dumps(safe_manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _bm25_scores(entries: Sequence[dict[str, Any]], query: str) -> list[float]:
    documents = [_topic_words(_clean_text(entry.get("text"))) for entry in entries]
    query_terms = list(dict.fromkeys(_topic_words(query)))
    if not query_terms:
        return [0.0 for _ in entries]
    document_frequency = Counter(term for terms in documents for term in set(terms))
    average_length = sum(len(terms) for terms in documents) / max(1, len(documents))
    k1 = 1.5
    b = 0.75
    scores: list[float] = []
    for entry, terms in zip(entries, documents):
        frequencies = Counter(terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            df = document_frequency.get(term, 0)
            inverse_frequency = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * len(terms) / max(1.0, average_length))
            score += inverse_frequency * (frequency * (k1 + 1)) / denominator
        tags = set(str(tag).lower() for tag in (entry.get("topic_tags") or []))
        score += 0.8 * len(tags.intersection(query_terms))
        scores.append(score)
    return scores


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def _semantic_retrieval_enabled() -> bool:
    return str(os.getenv("AI_CLONE_VOICE_SEMANTIC_RETRIEVAL", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def _ollama_embedding_endpoint() -> str | None:
    endpoint = str(os.getenv("AI_CLONE_VOICE_EMBEDDING_URL", "http://127.0.0.1:11434/api/embed")).strip()
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None
    return endpoint


def _ollama_embeddings(texts: Sequence[str]) -> list[list[float]] | None:
    global _OLLAMA_UNAVAILABLE_UNTIL

    if not texts or not _semantic_retrieval_enabled():
        return None
    if time.monotonic() < _OLLAMA_UNAVAILABLE_UNTIL:
        return None
    endpoint = _ollama_embedding_endpoint()
    if not endpoint:
        return None
    model = str(os.getenv("AI_CLONE_VOICE_EMBEDDING_MODEL", "embeddinggemma")).strip() or "embeddinggemma"
    results: list[list[float] | None] = [None] * len(texts)
    missing_indices: list[int] = []
    missing_texts: list[str] = []
    for index, text in enumerate(texts):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = _EMBEDDING_CACHE.get((model, digest))
        if cached is not None:
            results[index] = cached
        else:
            missing_indices.append(index)
            missing_texts.append(text)
    if missing_texts:
        body = json.dumps(
            {
                "model": model,
                "input": missing_texts,
                "truncate": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            timeout = max(0.25, min(5.0, float(os.getenv("AI_CLONE_VOICE_EMBEDDING_TIMEOUT_SECONDS", "1.5"))))
        except ValueError:
            timeout = 1.5
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            try:
                backoff = max(
                    5.0,
                    min(3600.0, float(os.getenv("AI_CLONE_VOICE_EMBEDDING_BACKOFF_SECONDS", "300"))),
                )
            except ValueError:
                backoff = 300.0
            _OLLAMA_UNAVAILABLE_UNTIL = time.monotonic() + backoff
            return None
        raw_embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(raw_embeddings, list) or len(raw_embeddings) != len(missing_texts):
            return None
        for position, raw_embedding in enumerate(raw_embeddings):
            if not isinstance(raw_embedding, list) or not raw_embedding:
                _OLLAMA_UNAVAILABLE_UNTIL = time.monotonic() + 300.0
                return None
            try:
                embedding = [float(value) for value in raw_embedding]
            except (TypeError, ValueError):
                _OLLAMA_UNAVAILABLE_UNTIL = time.monotonic() + 300.0
                return None
            index = missing_indices[position]
            results[index] = embedding
            digest = hashlib.sha256(texts[index].encode("utf-8")).hexdigest()
            if len(_EMBEDDING_CACHE) >= 512:
                _EMBEDDING_CACHE.pop(next(iter(_EMBEDDING_CACHE)))
            _EMBEDDING_CACHE[(model, digest)] = embedding
    _OLLAMA_UNAVAILABLE_UNTIL = 0.0
    return [embedding for embedding in results if embedding is not None] if all(results) else None


def _vector_cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _select_voice_exemplars(
    entries: Sequence[dict[str, Any]],
    *,
    query: str,
    limit: int,
    use_semantic: bool | None,
    routing_metadata: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    constraints = _voice_route_constraints(routing_metadata)
    if not entries or limit <= 0:
        return [], {
            "mode": "none",
            "embedding_model": None,
            "candidate_count": len(entries),
            "compatible_candidate_count": 0,
            "eligible_candidate_count": 0,
            "filtered_incompatible_count": 0,
            "reason": "voice_corpus_unavailable" if not entries else "reference_limit_disabled",
            "routing": constraints,
        }
    compatible_entries = [
        entry
        for entry in entries
        if _voice_entry_is_route_compatible(entry, constraints=constraints)
    ]
    if not compatible_entries:
        return [], {
            "mode": "none",
            "embedding_model": None,
            "candidate_count": len(entries),
            "compatible_candidate_count": 0,
            "eligible_candidate_count": 0,
            "filtered_incompatible_count": len(entries),
            "reason": "no_route_compatible_exemplars",
            "routing": constraints,
        }

    retrieval_query = _voice_retrieval_query(query)
    if not retrieval_query:
        return [], {
            "mode": "none",
            "embedding_model": None,
            "candidate_count": len(entries),
            "compatible_candidate_count": len(compatible_entries),
            "eligible_candidate_count": 0,
            "filtered_incompatible_count": len(entries) - len(compatible_entries),
            "reason": "no_meaningful_query_terms",
            "routing": constraints,
        }

    lexical_scores = _bm25_scores(compatible_entries, retrieval_query)
    lexical_maximum = max(lexical_scores) if lexical_scores else 0.0
    normalized_lexical = [
        score / lexical_maximum if lexical_maximum > 0 else 0.0
        for score in lexical_scores
    ]
    semantic_scores: list[float] | None = None
    semantic_requested = _semantic_retrieval_enabled() if use_semantic is None else use_semantic
    if semantic_requested and query.strip():
        embedded = _ollama_embeddings(
            [
                retrieval_query,
                *[_clean_text(entry.get("text")) for entry in compatible_entries],
            ]
        )
        if embedded and len(embedded) == len(compatible_entries) + 1:
            query_embedding = embedded[0]
            semantic_scores = [
                max(0.0, min(1.0, (_vector_cosine(query_embedding, embedding) + 1.0) / 2.0))
                for embedding in embedded[1:]
            ]
    if semantic_scores is not None:
        combined_scores = [
            (0.45 * lexical) + (0.55 * semantic)
            for lexical, semantic in zip(normalized_lexical, semantic_scores)
        ]
        retrieval_mode = "hybrid_local_ollama"
    else:
        combined_scores = normalized_lexical
        retrieval_mode = "lexical_bm25"
    candidates: list[dict[str, Any]] = []
    for index, entry in enumerate(compatible_entries):
        lexical_supported = lexical_scores[index] > 0
        semantic_supported = bool(
            semantic_scores is not None
            and semantic_scores[index] >= VOICE_MIN_SEMANTIC_SUPPORT
        )
        relevance = combined_scores[index]
        if relevance < VOICE_MIN_RELEVANCE or not (lexical_supported or semantic_supported):
            continue
        candidates.append(
            {
                "entry": entry,
                "relevance": relevance,
                "tokens": _topic_words(_clean_text(entry.get("text"))),
            }
        )
    eligible_candidate_count = len(candidates)
    selected: list[dict[str, Any]] = []
    while candidates and len(selected) < min(limit, len(entries)):
        best_index = 0
        best_score = float("-inf")
        for index, candidate in enumerate(candidates):
            diversity_penalty = max(
                (
                    _jaccard(candidate["tokens"], _topic_words(_clean_text(chosen.get("text"))))
                    for chosen in selected
                ),
                default=0.0,
            )
            mode_bonus = 0.12 if all(
                str(chosen.get("post_type") or "") != str(candidate["entry"].get("post_type") or "")
                for chosen in selected
            ) else 0.0
            selection_score = candidate["relevance"] - (0.38 * diversity_penalty) + mode_bonus
            if selection_score > best_score:
                best_score = selection_score
                best_index = index
        selected.append(candidates.pop(best_index)["entry"])
    return selected, {
        "mode": retrieval_mode,
        "embedding_model": (
            str(os.getenv("AI_CLONE_VOICE_EMBEDDING_MODEL", "embeddinggemma")).strip()
            if semantic_scores is not None
            else None
        ),
        "candidate_count": len(entries),
        "compatible_candidate_count": len(compatible_entries),
        "eligible_candidate_count": eligible_candidate_count,
        "filtered_incompatible_count": len(entries) - len(compatible_entries),
        "reason": "selected" if selected else "no_sufficiently_relevant_exemplars",
        "routing": constraints,
    }


def select_voice_exemplars(
    entries: Sequence[dict[str, Any]],
    *,
    query: str,
    limit: int = 4,
    use_semantic: bool | None = None,
    routing_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Select complete, relevant examples while discouraging near-duplicate modes."""

    selected, _ = _select_voice_exemplars(
        entries,
        query=query,
        limit=limit,
        use_semantic=use_semantic,
        routing_metadata=routing_metadata,
    )
    return selected


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])(?:[\"”']*)\s+|\n+", text)
        if sentence.strip()
    ]


def _paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def _rate(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def build_writing_fingerprint(texts: Sequence[str]) -> dict[str, float]:
    clean_texts = [_clean_text(text) for text in texts if _clean_text(text)]
    sentences = [sentence for text in clean_texts for sentence in _sentences(text)]
    sentence_lengths = [len(_words(sentence)) for sentence in sentences if _words(sentence)]
    paragraphs = [paragraph for text in clean_texts for paragraph in _paragraphs(text)]
    paragraph_sentence_lengths = [len(_sentences(paragraph)) for paragraph in paragraphs]
    word_count = sum(len(_words(text)) for text in clean_texts)
    return {
        "sample_count": float(len(clean_texts)),
        "word_count": float(word_count),
        "avg_sentence_words": round(statistics.fmean(sentence_lengths), 3) if sentence_lengths else 0.0,
        "median_sentence_words": round(statistics.median(sentence_lengths), 3) if sentence_lengths else 0.0,
        "short_sentence_rate": round(_rate(sum(length <= 7 for length in sentence_lengths), len(sentence_lengths)), 4),
        "avg_paragraph_sentences": round(statistics.fmean(paragraph_sentence_lengths), 3) if paragraph_sentence_lengths else 0.0,
        "question_rate": round(_rate(sum(sentence.rstrip().endswith("?") for sentence in sentences), len(sentences)), 4),
        "exclamation_rate": round(_rate(sum("!" in sentence for sentence in sentences), len(sentences)), 4),
        "contraction_rate": round(
            _rate(
                sum(
                    bool(
                        re.search(
                            r"\b\w+(?:n['’]t|['’](?:re|ve|ll|d|m|s))\b",
                            sentence,
                            flags=re.IGNORECASE,
                        )
                    )
                    for sentence in sentences
                ),
                len(sentences),
            ),
            4,
        ),
        "first_person_rate": round(
            _rate(sum(bool(re.search(r"\b(?:i|i'm|i've|i'd|my|me|we|our)\b", sentence, flags=re.IGNORECASE)) for sentence in sentences), len(sentences)),
            4,
        ),
        "emoji_per_100_words": round(100 * _rate(sum(len(EMOJI_PATTERN.findall(text)) for text in clean_texts), word_count), 4),
        "hashtag_per_100_words": round(100 * _rate(sum(len(re.findall(r"(?<!\w)#[A-Za-z0-9_]+", text)) for text in clean_texts), word_count), 4),
        "newline_per_100_words": round(100 * _rate(sum(text.count("\n") for text in clean_texts), word_count), 4),
    }


def _style_sequence(text: str) -> list[str]:
    sequence: list[str] = []
    for token in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[.!?,:;—–\-()#]", text.lower()):
        normalized = token.replace("’", "'")
        if normalized in FUNCTION_WORDS or re.fullmatch(r"[.!?,:;—–\-()#]", normalized):
            sequence.append(normalized)
        elif not sequence or sequence[-1] != "<content>":
            sequence.append("<content>")
    return sequence


def _ngrams(values: Sequence[str], size: int = 3) -> Counter[tuple[str, ...]]:
    return Counter(tuple(values[index : index + size]) for index in range(max(0, len(values) - size + 1)))


def _cosine(left: Counter[Any], right: Counter[Any]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _metric_similarity(candidate: dict[str, float], reference: dict[str, float]) -> float:
    scales = {
        "avg_sentence_words": 10.0,
        "median_sentence_words": 9.0,
        "short_sentence_rate": 0.5,
        "avg_paragraph_sentences": 2.5,
        "question_rate": 0.3,
        "exclamation_rate": 0.3,
        "contraction_rate": 0.3,
        "first_person_rate": 0.65,
        "emoji_per_100_words": 3.0,
        "hashtag_per_100_words": 4.0,
        "newline_per_100_words": 10.0,
    }
    similarities = [
        max(0.0, 1.0 - abs(candidate.get(metric, 0.0) - reference.get(metric, 0.0)) / scale)
        for metric, scale in scales.items()
    ]
    return statistics.fmean(similarities) if similarities else 0.0


def _longest_copy_overlap(candidate: str, exemplars: Sequence[str], size: int = 8) -> int:
    candidate_words = _words(candidate)
    if len(candidate_words) < size:
        return 0
    exemplar_ngrams: set[tuple[str, ...]] = set()
    for exemplar in exemplars:
        words = _words(exemplar)
        exemplar_ngrams.update(tuple(words[index : index + size]) for index in range(max(0, len(words) - size + 1)))
    return sum(
        tuple(candidate_words[index : index + size]) in exemplar_ngrams
        for index in range(max(0, len(candidate_words) - size + 1))
    )


def score_voice_fidelity(
    text: str,
    *,
    exemplars: Sequence[str],
    reference_fingerprint: dict[str, float] | None = None,
) -> dict[str, Any]:
    candidate = _clean_text(text)
    clean_exemplars = [_clean_text(exemplar) for exemplar in exemplars if _clean_text(exemplar)]
    if not candidate or not clean_exemplars:
        return {
            "score": None,
            "status": "insufficient_reference_data",
            "warnings": ["voice_corpus_unavailable"],
            "components": {},
        }
    reference = reference_fingerprint or build_writing_fingerprint(clean_exemplars)
    candidate_fingerprint = build_writing_fingerprint([candidate])
    structure_similarity = _metric_similarity(candidate_fingerprint, reference)
    candidate_style = _ngrams(_style_sequence(candidate))
    reference_style = _ngrams([token for exemplar in clean_exemplars for token in _style_sequence(exemplar)])
    style_similarity = _cosine(candidate_style, reference_style)
    candidate_words = _words(candidate)
    reference_vocabulary = set(word for exemplar in clean_exemplars for word in _words(exemplar))
    function_words = [word for word in candidate_words if word in FUNCTION_WORDS]
    function_word_fit = _rate(sum(word in reference_vocabulary for word in function_words), len(function_words))
    copy_overlap = _longest_copy_overlap(candidate, clean_exemplars)
    normalized = candidate.lower()
    repeated_stock = [
        phrase
        for phrase in DEFAULT_STOCK_PHRASES
        if len(re.findall(re.escape(phrase), normalized, flags=re.IGNORECASE)) > 0
    ]
    repeated_short_lines = [
        line
        for line, count in Counter(
            " ".join(line.lower().split())
            for line in re.split(r"\n+|(?<=[.!?])\s+", candidate)
            if 2 <= len(_words(line)) <= 8
        ).items()
        if count > 1
    ]
    copy_penalty = min(18.0, copy_overlap * 4.5)
    catchphrase_penalty = min(18.0, len(repeated_stock) * 6.0 + len(repeated_short_lines) * 4.0)
    score = (
        50.0 * structure_similarity
        + 32.0 * style_similarity
        + 18.0 * function_word_fit
        - copy_penalty
        - catchphrase_penalty
    )
    warnings: list[str] = []
    if copy_overlap:
        warnings.append(f"possible_exemplar_copy:{copy_overlap}")
    if repeated_stock:
        warnings.append("stock_phrase:" + ",".join(repeated_stock))
    if repeated_short_lines:
        warnings.append(f"repeated_short_line:{len(repeated_short_lines)}")
    if structure_similarity < 0.55:
        warnings.append("structure_drift")
    if style_similarity < 0.25:
        warnings.append("rhythm_drift")
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "status": "scored",
        "warnings": warnings,
        "components": {
            "structure_similarity": round(structure_similarity, 4),
            "style_sequence_similarity": round(style_similarity, 4),
            "function_word_fit": round(function_word_fit, 4),
            "copy_overlap_8gram_count": copy_overlap,
            "copy_penalty": round(copy_penalty, 2),
            "catchphrase_penalty": round(catchphrase_penalty, 2),
        },
        "candidate_fingerprint": candidate_fingerprint,
    }


def render_voice_reference_prompt(
    exemplars: Sequence[dict[str, Any]],
    *,
    fingerprint: dict[str, float] | None = None,
) -> str:
    if not exemplars:
        return ""
    fingerprint = fingerprint or build_writing_fingerprint([_clean_text(entry.get("text")) for entry in exemplars])
    metrics = (
        f"typical sentence length ≈ {fingerprint.get('avg_sentence_words', 0):.1f} words; "
        f"short-sentence rate ≈ {fingerprint.get('short_sentence_rate', 0):.0%}; "
        f"first-person rate ≈ {fingerprint.get('first_person_rate', 0):.0%}"
    )
    rendered_examples = []
    for index, entry in enumerate(exemplars, start=1):
        rendered_examples.append(
            "\n".join(
                [
                    f"<VOICE_EXAMPLE_{index} id=\"{entry.get('id')}\" mode=\"{entry.get('post_type')}\">",
                    _clean_text(entry.get("text")),
                    f"</VOICE_EXAMPLE_{index}>",
                ]
            )
        )
    return "\n\n".join(
        [
            "OWNER VOICE REFERENCE CONTRACT:",
            "- These verified examples are style-only. Learn their range, rhythm, directness, and positioning; every fact, name, event, organization, date, metric, and story is forbidden unless approved anchors independently support it.",
            "- Match the pattern, not exact wording. Do not copy an eight-word sequence.",
            "- Choose the mode that fits the intent and prefer natural spoken clarity over generic LinkedIn polish or system jargon.",
            "- Do not force a catchphrase, slogan, rhetorical question, emoji, hashtag, or fragment.",
            f"- Measured reference shape: {metrics}. These are descriptive guardrails, not quotas.",
            *rendered_examples,
        ]
    )


def render_voice_style_metrics_prompt(
    fingerprint: dict[str, float],
    *,
    reason: str,
) -> str:
    """Render aggregate style guidance without exposing an incompatible post."""

    if float(fingerprint.get("sample_count") or 0) <= 0:
        return ""
    metrics = (
        f"typical sentence length ≈ {fingerprint.get('avg_sentence_words', 0):.1f} words; "
        f"short-sentence rate ≈ {fingerprint.get('short_sentence_rate', 0):.0%}; "
        f"first-person rate ≈ {fingerprint.get('first_person_rate', 0):.0%}"
    )
    return "\n".join(
        [
            "OWNER VOICE STYLE-ONLY CONTRACT:",
            "- No route-compatible, sufficiently relevant full-text owner exemplar was eligible for this request.",
            "- Use only the aggregate style signals and directives below. No corpus fact, name, event, organization, date, metric, or story is available as source material.",
            "- Prefer natural spoken clarity, direct thesis language, varied paragraph rhythm, and a concrete payoff over generic LinkedIn polish.",
            "- Do not invent or borrow a personal story, employer reference, event, project, result, or metric to make the post feel specific.",
            "- Do not force a catchphrase, slogan, rhetorical question, emoji, hashtag, or fragment.",
            f"- Measured reference shape: {metrics}. These are descriptive guardrails, not quotas.",
            f"- Retrieval posture: {reason or 'style_metrics_only'}.",
        ]
    )


def render_voice_influence_prompt(influences: Sequence[dict[str, Any]]) -> str:
    if not influences:
        return ""
    cards: list[str] = []
    for index, entry in enumerate(influences, start=1):
        technique_text = "\n".join(f"  - {technique}" for technique in entry.get("techniques") or [])
        avoid_text = "\n".join(f"  - Avoid: {item}" for item in entry.get("avoid") or [])
        cards.append(
            "\n".join(
                value
                for value in (
                    f"<INFLUENCE_CARD_{index} id=\"{entry.get('id')}\" source=\"{entry.get('source_name')}\">",
                    technique_text,
                    avoid_text,
                    f"</INFLUENCE_CARD_{index}>",
                )
                if value
            )
        )
    return "\n\n".join(
        [
            "SECONDARY INFLUENCE CONTRACT:",
            "- These are approved technique abstractions from outside creators. They are not evidence of the owner's vocabulary, biography, beliefs, or lived experience.",
            "- Use at most one technique when it genuinely helps the current post.",
            "- The verified owner examples always win on wording, rhythm, and identity.",
            "- Do not imitate a named speaker, copy signature slogans, recreate co-host banter, or make the owner sound like a different brand.",
            *cards,
        ]
    )


def build_voice_context(
    *,
    query: str,
    path: Path | str | None = None,
    execution_mode: str = "cloud",
    limit: int = 4,
    influence_path: Path | str | None = None,
    influence_limit: int = 2,
    use_semantic: bool | None = None,
    routing_metadata: dict[str, Any] | None = None,
    audience: str | None = None,
    canonical_pillar: str | None = None,
    career_signal: str | None = None,
    employer_proximity: str | None = None,
    treatment: str | None = None,
    domain: str | None = None,
    lane: str | None = None,
) -> dict[str, Any]:
    merged_routing_metadata = _merge_routing_metadata(
        routing_metadata,
        audience=audience,
        canonical_pillar=canonical_pillar,
        career_signal=career_signal,
        employer_proximity=employer_proximity,
        treatment=treatment,
        domain=domain,
        lane=lane,
    )
    entries = load_voice_corpus(path, execution_mode=execution_mode)
    selected, owner_retrieval = _select_voice_exemplars(
        entries,
        query=query,
        limit=limit,
        use_semantic=use_semantic,
        routing_metadata=merged_routing_metadata,
    )
    # Outside technique cards are allowed to enrich an established owner
    # voice, never to substitute for a missing owner corpus.
    influences = load_voice_influences(influence_path) if selected else []
    selected_influences, influence_retrieval = _select_voice_exemplars(
        influences,
        query=query,
        limit=influence_limit,
        use_semantic=use_semantic,
    )
    fingerprint = build_writing_fingerprint([_clean_text(entry.get("text")) for entry in entries])
    owner_prompt = (
        render_voice_reference_prompt(selected, fingerprint=fingerprint)
        if selected
        else render_voice_style_metrics_prompt(
            fingerprint,
            reason=str(owner_retrieval.get("reason") or "style_metrics_only"),
        )
    )
    influence_prompt = render_voice_influence_prompt(selected_influences)
    selection_posture = (
        "full_text_exemplars"
        if selected
        else ("style_metrics_only" if entries else "unavailable")
    )
    return {
        "execution_mode": execution_mode,
        "corpus_path": str(Path(path).expanduser() if path is not None else resolve_voice_corpus_path()),
        "corpus_count": len(entries),
        "corpus_digest": voice_corpus_digest(entries),
        "reference_ids": [str(entry.get("id") or "") for entry in selected],
        "reference_modes": [str(entry.get("post_type") or "") for entry in selected],
        "selection_posture": selection_posture,
        "influence_count": len(influences),
        "influence_ids": [str(entry.get("id") or "") for entry in selected_influences],
        "retrieval": {
            "owner": owner_retrieval,
            "influence": influence_retrieval,
        },
        "fingerprint": fingerprint,
        "prompt_block": "\n\n".join(block for block in (owner_prompt, influence_prompt) if block),
        # This field must remain inside the local worker process. Never include it
        # in a completion payload, artifact, remote cache packet, or log.
        "_local_exemplars": selected,
    }


def score_options(options: Sequence[str], voice_context: dict[str, Any]) -> list[dict[str, Any]]:
    exemplars = [
        _clean_text(entry.get("text"))
        for entry in (voice_context.get("_local_exemplars") or [])
        if isinstance(entry, dict) and _clean_text(entry.get("text"))
    ]
    fingerprint = voice_context.get("fingerprint") if isinstance(voice_context.get("fingerprint"), dict) else None
    return [
        {
            "option_index": index,
            **score_voice_fidelity(option, exemplars=exemplars, reference_fingerprint=fingerprint),
        }
        for index, option in enumerate(options, start=1)
    ]


def public_voice_diagnostics(voice_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_mode": voice_context.get("execution_mode"),
        "corpus_count": int(voice_context.get("corpus_count") or 0),
        "corpus_digest": str(voice_context.get("corpus_digest") or ""),
        "reference_ids": list(voice_context.get("reference_ids") or []),
        "reference_modes": list(voice_context.get("reference_modes") or []),
        "selection_posture": str(voice_context.get("selection_posture") or "unavailable"),
        "influence_count": int(voice_context.get("influence_count") or 0),
        "influence_ids": list(voice_context.get("influence_ids") or []),
        "retrieval": dict(voice_context.get("retrieval") or {}),
        "fingerprint": dict(voice_context.get("fingerprint") or {}),
    }


def _append_jsonl_once(path: Path, payload: dict[str, Any], *, identity_key: str = "id") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    identity = str(payload.get(identity_key) or "").strip()
    flags = os.O_APPEND | os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            if identity:
                for line in handle:
                    try:
                        existing = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(existing, dict) and str(existing.get(identity_key) or "").strip() == identity:
                        return False
            handle.seek(0, os.SEEK_END)
            handle.write(serialized + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            return True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_voice_example(
    *,
    text: str,
    provenance: str,
    approval_status: str,
    privacy: str,
    channel: str = "linkedin",
    post_type: str = "unspecified",
    topic_tags: Sequence[str] = (),
    source_url: str | None = None,
    entry_id: str | None = None,
    path: Path | str | None = None,
) -> dict[str, Any]:
    normalized_text = _clean_text(text)
    normalized_provenance = str(provenance or "").strip().lower()
    normalized_approval = str(approval_status or "").strip().lower()
    normalized_privacy = str(privacy or "").strip().lower()
    if len(normalized_text) < 40:
        raise ValueError("A voice example must contain at least 40 characters.")
    if normalized_provenance not in APPROVED_PROVENANCE:
        raise ValueError("Only human_published or human_edited text can become a positive voice example.")
    if normalized_approval not in APPROVED_STATUSES:
        raise ValueError("A positive voice example must be explicitly approved or verified.")
    if normalized_privacy not in {"public", "cloud_ok_excerpt", "local_only", "sensitive"}:
        raise ValueError("Voice-example privacy must be public, cloud_ok_excerpt, local_only, or sensitive.")
    normalized_id = str(entry_id or "").strip() or (
        f"{normalized_provenance}-" + hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:20]
    )
    payload = {
        "id": normalized_id,
        "text": normalized_text,
        "kind": "positive",
        "provenance": normalized_provenance,
        "approval_status": normalized_approval,
        "privacy": normalized_privacy,
        "channel": str(channel or "linkedin").strip().lower(),
        "post_type": str(post_type or "unspecified").strip().lower(),
        "topic_tags": [str(tag).strip().lower() for tag in topic_tags if str(tag).strip()],
        "source_url": str(source_url or "").strip() or None,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    target_path = Path(path).expanduser() if path is not None else resolve_voice_corpus_path()
    return {
        "created": _append_jsonl_once(target_path, payload),
        "path": str(target_path),
        "entry": payload,
    }


def record_voice_preference(
    *,
    generated_text: str,
    edited_text: str | None = None,
    rejected_texts: Sequence[str] = (),
    context: dict[str, Any] | None = None,
    privacy: str = "local_only",
    promote_edited: bool = False,
    corpus_path: Path | str | None = None,
    preference_path: Path | str | None = None,
) -> dict[str, Any]:
    """Capture the exact generated→edited pair locally.

    Nothing is promoted into the positive corpus unless the owner supplies a
    materially edited final and explicitly requests promotion.
    """

    generated = _clean_text(generated_text)
    edited = _clean_text(edited_text)
    rejected = [_clean_text(item) for item in rejected_texts if _clean_text(item)]
    if not generated:
        raise ValueError("generated_text is required.")
    normalized_privacy = str(privacy or "local_only").strip().lower()
    if normalized_privacy not in {"public", "cloud_ok_excerpt", "local_only", "sensitive"}:
        raise ValueError("Preference privacy must be public, cloud_ok_excerpt, local_only, or sensitive.")
    pair_seed = "\n".join([generated, edited, *rejected, json.dumps(context or {}, sort_keys=True)])
    preference_id = "voice-pref-" + hashlib.sha256(pair_seed.encode("utf-8")).hexdigest()[:20]
    preference = {
        "id": preference_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "generated_text": generated,
        "edited_text": edited or None,
        "rejected_texts": rejected,
        "context": dict(context or {}),
        "privacy": normalized_privacy,
        "has_material_edit": bool(edited and edited != generated),
    }
    target_preference_path = (
        Path(preference_path).expanduser() if preference_path is not None else resolve_voice_preference_path()
    )
    preference_created = _append_jsonl_once(target_preference_path, preference)
    promoted: dict[str, Any] | None = None
    if promote_edited:
        if not edited or edited == generated:
            raise ValueError("Promotion requires a materially edited final draft.")
        promoted = append_voice_example(
            text=edited,
            provenance="human_edited",
            approval_status="approved",
            privacy=normalized_privacy,
            channel=str((context or {}).get("channel") or "linkedin"),
            post_type=str((context or {}).get("post_type") or "owner_edited"),
            topic_tags=list((context or {}).get("topic_tags") or []),
            source_url=str((context or {}).get("source_url") or "") or None,
            entry_id=f"edited-{preference_id}",
            path=corpus_path,
        )
    return {
        "created": preference_created,
        "path": str(target_preference_path),
        "preference_id": preference_id,
        "promoted": promoted,
    }


def _read_local_voice_review_packet(path: Path) -> dict[str, Any]:
    """Read one bounded regular file without following a symlink."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ValueError(f"Voice-review packet not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to open voice-review packet safely: {path}") from exc
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("Voice-review packet must be a regular file.")
        if file_stat.st_size > MAX_VOICE_REVIEW_PACKET_BYTES:
            raise ValueError(
                f"Voice-review packet exceeds the {MAX_VOICE_REVIEW_PACKET_BYTES}-byte local import limit."
            )
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            try:
                payload = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError("Voice-review packet is not valid JSON.") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(payload, dict):
        raise ValueError("Voice-review packet must contain a JSON object.")
    return payload


def import_local_voice_review_packet(
    packet_path: Path | str,
    *,
    preference_path: Path | str | None = None,
) -> dict[str, Any]:
    """Import an explicit browser-downloaded review decision into local preferences.

    This boundary deliberately accepts only `local_only` packets and always calls
    `record_voice_preference` with `promote_edited=False`. Importing a packet can
    therefore teach a later local ranker about an owner decision, but it cannot
    turn generated copy into an approved voice example.
    """

    resolved_packet_path = Path(packet_path).expanduser()
    payload = _read_local_voice_review_packet(resolved_packet_path)
    if str(payload.get("schema_version") or "").strip() != VOICE_REVIEW_PACKET_SCHEMA_VERSION:
        raise ValueError(f"Voice-review packet must use {VOICE_REVIEW_PACKET_SCHEMA_VERSION}.")
    if str(payload.get("source") or "").strip() != VOICE_REVIEW_PACKET_SOURCE:
        raise ValueError("Voice-review packet source is not trusted.")
    if str(payload.get("privacy") or "").strip().lower() != "local_only":
        raise ValueError("Browser review imports must remain local_only.")
    if bool(payload.get("promote_edited")):
        raise ValueError("Browser review imports cannot promote text into the positive voice corpus.")

    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in VOICE_REVIEW_DECISIONS:
        raise ValueError("Voice-review decision must be approve, revise, or park.")
    generated = _clean_text(payload.get("generated_text"))
    if not generated:
        raise ValueError("Voice-review packet must include the exact generated draft.")
    edited = _clean_text(payload.get("edited_text"))
    if decision == "park":
        edited = ""

    raw_rejected = payload.get("rejected_texts")
    if raw_rejected is None:
        raw_rejected = []
    if not isinstance(raw_rejected, list):
        raise ValueError("Voice-review rejected_texts must be a JSON array.")
    rejected = [_clean_text(item) for item in raw_rejected if _clean_text(item)][:10]
    if decision == "park" and generated not in rejected:
        rejected.insert(0, generated)

    raw_context = payload.get("context")
    raw_context = raw_context if isinstance(raw_context, dict) else {}
    context = {
        "source": VOICE_REVIEW_PACKET_SOURCE,
        "decision": decision,
        "queue_id": _clean_text(payload.get("queue_id") or raw_context.get("queue_id")),
        "generation_job_id": _clean_text(
            payload.get("generation_job_id") or raw_context.get("generation_job_id")
        ),
        "generation_option_index": payload.get(
            "generation_option_index",
            raw_context.get("generation_option_index"),
        ),
        "channel": _clean_text(raw_context.get("channel")) or "linkedin",
        "post_type": _clean_text(raw_context.get("post_type")) or "owner_review",
        "topic": _clean_text(raw_context.get("topic")),
        "topic_tags": [
            _clean_text(tag).lower()
            for tag in (raw_context.get("topic_tags") or [])
            if _clean_text(tag)
        ][:12]
        if isinstance(raw_context.get("topic_tags"), list)
        else [],
        "owner_notes": _clean_text(raw_context.get("owner_notes")),
        "captured_via": "browser_download_local_import",
    }
    result = record_voice_preference(
        generated_text=generated,
        edited_text=edited or None,
        rejected_texts=rejected,
        context=context,
        privacy="local_only",
        promote_edited=False,
        preference_path=preference_path,
    )
    return {
        "created": bool(result.get("created")),
        "path": str(result.get("path") or ""),
        "preference_id": str(result.get("preference_id") or ""),
        "decision": decision,
        "has_material_edit": bool(edited and edited != generated),
        "rejected_count": len(rejected),
        "promoted": False,
        "packet_retained": True,
    }
