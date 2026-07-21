from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


PACK_SCHEMA_VERSION = "neo_public_knowledge_pack/v1"
SELECTION_SCHEMA_VERSION = "neo_public_knowledge_selection/v1"
PUBLIC_REVIEW_STATUS = "approved_public"
SOURCE_POLICY = "canonical_claims_stories_wins_bio_resume_timeline_only"

DEFAULT_LIMIT = 5
MAX_LIMIT = 8
DEFAULT_MAX_CONTEXT_CHARS = 3_600
DEFAULT_MAX_RESPONSE_CHARS = 1_200
MIN_CONTEXT_CHARS = 256
MAX_CONTEXT_CHARS = 6_000

_ENTRY_KINDS = {"bio", "claim", "story", "win"}
_ROOT_KEYS = {
    "schema_version",
    "pack_version",
    "source_bundle_version",
    "curated_on",
    "persona_id",
    "display_name",
    "audiences",
    "purpose",
    "source_policy",
    "review_status",
    "entries",
}
_ENTRY_KEYS = {
    "id",
    "kind",
    "title",
    "statement",
    "evidence",
    "use_when",
    "topics",
    "keywords",
    "default_rank",
    "review_status",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b")
_INTERNATIONAL_PHONE_RE = re.compile(r"(?<!\w)\+\d{1,3}(?:[\s().-]*\d){7,14}(?!\d)")
_ABSOLUTE_POSIX_PATH_RE = re.compile(
    r"""
    (?<![A-Za-z0-9:/])/(?!/)(?:
        (?:Users|home|private|etc|var|app|opt|root|tmp|srv|usr|bin|Library|
           Applications|System|Volumes|dev|proc|run)
           (?:/[A-Za-z0-9._~+%=-]+)*/?
      | [A-Za-z0-9._~+-]+/[A-Za-z0-9._~+%=-]+
           (?:/[A-Za-z0-9._~+%=-]+)*/?
    )
    (?=$|[\s\"'`,;:)\]}])
    """,
    re.IGNORECASE | re.VERBOSE,
)
_ABSOLUTE_WINDOWS_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/][^\s\\/:*?\"<>|]+(?:[\\/][^\s\\/:*?\"<>|]+)*"
    r"|(?<![\\/:])(?:\\\\|//)[^\s\\/]+[\\/][^\s\\/]+)",
    re.IGNORECASE,
)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"\b(?:"
    r"[a-z0-9_-]*(?:api[_-]?key|access[_-]?key|private[_-]?key|token|secret|password|passwd)"
    r"|(?:api|access|private)\s+key|client\s+secret"
    r")"
    r"\s*(?:=|:)\s*\S+",
    re.IGNORECASE,
)
_PROMPT_CONTROL_RE = re.compile(
    r"""
    \b(?:
        (?:ignore|disregard|forget)\s+(?:all\s+)?(?:the\s+)?
            (?:previous|prior|above|earlier|system|developer)\s+
            (?:instructions?|prompts?|rules?)
      | override\s+(?:the\s+)?(?:system|developer|previous|prior|hidden)?\s*
            (?:instructions?|prompts?|rules?)
      | (?:reveal|show|print|repeat|expose|exfiltrate)\s+(?:the\s+)?
            (?:system|developer|hidden|internal)\s+(?:prompts?|instructions?|rules?)
      | (?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)
      | (?:set|change|replace|override)\s+(?:your\s+|the\s+)?role
      | follow\s+(?:these|my|the\s+following)\s+instructions?
    )\b
    | (?:^|\s)(?:system|developer|assistant)\s*:\s*\S
    | \brole\s*(?:=|:)\s*(?:system|developer|assistant|user)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
_FORBIDDEN_MARKERS = (
    ".codex/",
    ".openclaw/",
    "authorization: bearer",
    "begin private key",
    "control_plane_service_token",
    "firebase_service_account",
    "neo_guest_signing_secret",
    "openai_api_key",
    "pending delta",
    "raw brain memory",
    "system prompt",
    "unapproved brain",
    "unreviewed brain",
)
_STOP_WORDS = {
    "a",
    "about",
    "am",
    "an",
    "and",
    "are",
    "as",
    "at",
    "background",
    "be",
    "can",
    "could",
    "do",
    "does",
    "experience",
    "feeze",
    "fit",
    "for",
    "from",
    "he",
    "her",
    "his",
    "how",
    "i",
    "in",
    "is",
    "it",
    "johnnie",
    "me",
    "neo",
    "of",
    "on",
    "or",
    "our",
    "she",
    "tell",
    "that",
    "the",
    "their",
    "them",
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
    "why",
    "with",
    "work",
    "would",
    "you",
    "your",
}


class NeoPublicKnowledgeError(ValueError):
    """Raised when the curated guest-safe pack violates its public contract."""


def resolve_public_knowledge_path() -> Path:
    relative_path = (
        Path("knowledge")
        / "persona"
        / "feeze"
        / "public"
        / "v1"
        / "neo_public_knowledge.json"
    )
    module_path = Path(__file__).resolve()
    # Railway may make ``backend/`` the build root, while local development
    # imports this module from the repository root. Support both layouts and
    # still fail closed when neither contains the approved pack.
    roots = (
        module_path.parents[2],
        module_path.parents[3],
        Path.cwd().resolve(),
    )
    candidates: list[Path] = []
    for root in roots:
        candidate = root / relative_path
        if candidate not in candidates:
            candidates.append(candidate)
        if candidate.is_file():
            return candidate
    return candidates[0]


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _iter_strings(nested)
        return
    if isinstance(value, list):
        for nested in value:
            yield from _iter_strings(nested)


def _validate_public_text(pack: dict[str, Any]) -> None:
    for value in _iter_strings(pack):
        normalized = " ".join(value.split())
        lowered = normalized.lower()
        if _ABSOLUTE_POSIX_PATH_RE.search(normalized) or _ABSOLUTE_WINDOWS_PATH_RE.search(normalized):
            raise NeoPublicKnowledgeError("Public knowledge contains an absolute path.")
        if _CREDENTIAL_ASSIGNMENT_RE.search(normalized):
            raise NeoPublicKnowledgeError("Public knowledge contains a credential-like assignment.")
        if _EMAIL_RE.search(normalized):
            raise NeoPublicKnowledgeError("Public knowledge contains an email address.")
        if _PHONE_RE.search(normalized) or _INTERNATIONAL_PHONE_RE.search(normalized):
            raise NeoPublicKnowledgeError("Public knowledge contains a phone number.")
        if _PROMPT_CONTROL_RE.search(normalized):
            raise NeoPublicKnowledgeError("Public knowledge contains prompt-control text.")
        if any(marker in lowered for marker in _FORBIDDEN_MARKERS):
            raise NeoPublicKnowledgeError("Public knowledge contains a forbidden private marker.")


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NeoPublicKnowledgeError(f"{field} must be non-empty text.")
    return value.strip()


def _require_tags(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise NeoPublicKnowledgeError(f"{field} must be a non-empty list.")
    tags: list[str] = []
    for item in value:
        tag = _require_text(item, field=field)
        if not _TAG_RE.fullmatch(tag):
            raise NeoPublicKnowledgeError(f"{field} contains an invalid tag.")
        tags.append(tag)
    if len(tags) != len(set(tags)):
        raise NeoPublicKnowledgeError(f"{field} contains duplicate tags.")
    return tags


def validate_public_knowledge_pack(pack: Any) -> dict[str, Any]:
    if not isinstance(pack, dict):
        raise NeoPublicKnowledgeError("Public knowledge pack must be a JSON object.")
    unexpected_root_keys = set(pack) - _ROOT_KEYS
    missing_root_keys = _ROOT_KEYS - set(pack)
    if unexpected_root_keys or missing_root_keys:
        raise NeoPublicKnowledgeError("Public knowledge pack fields do not match the v1 contract.")

    if pack.get("schema_version") != PACK_SCHEMA_VERSION:
        raise NeoPublicKnowledgeError("Unsupported public knowledge schema version.")
    pack_version = _require_text(pack.get("pack_version"), field="pack_version")
    if not _SEMVER_RE.fullmatch(pack_version):
        raise NeoPublicKnowledgeError("pack_version must use semantic versioning.")
    _require_text(pack.get("source_bundle_version"), field="source_bundle_version")
    curated_on = _require_text(pack.get("curated_on"), field="curated_on")
    if not _ISO_DATE_RE.fullmatch(curated_on):
        raise NeoPublicKnowledgeError("curated_on must use YYYY-MM-DD format.")
    _require_text(pack.get("persona_id"), field="persona_id")
    _require_text(pack.get("display_name"), field="display_name")
    _require_tags(pack.get("audiences"), field="audiences")
    _require_text(pack.get("purpose"), field="purpose")
    if pack.get("source_policy") != SOURCE_POLICY:
        raise NeoPublicKnowledgeError("Public knowledge source policy is not allowed.")
    if pack.get("review_status") != PUBLIC_REVIEW_STATUS:
        raise NeoPublicKnowledgeError("Public knowledge pack is not approved for guest use.")

    entries = pack.get("entries")
    if not isinstance(entries, list) or not entries:
        raise NeoPublicKnowledgeError("Public knowledge pack must contain entries.")

    entry_ids: set[str] = set()
    ranks: set[int] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise NeoPublicKnowledgeError(f"entries[{index}] must be an object.")
        if set(entry) != _ENTRY_KEYS:
            raise NeoPublicKnowledgeError(f"entries[{index}] fields do not match the v1 contract.")
        entry_id = _require_text(entry.get("id"), field=f"entries[{index}].id")
        if not _TAG_RE.fullmatch(entry_id):
            raise NeoPublicKnowledgeError(f"entries[{index}].id is invalid.")
        if entry_id in entry_ids:
            raise NeoPublicKnowledgeError("Public knowledge entry ids must be unique.")
        entry_ids.add(entry_id)

        kind = _require_text(entry.get("kind"), field=f"entries[{index}].kind")
        if kind not in _ENTRY_KINDS:
            raise NeoPublicKnowledgeError(f"entries[{index}].kind is not public-safe.")
        for field in ("title", "statement", "evidence", "use_when"):
            _require_text(entry.get(field), field=f"entries[{index}].{field}")
        _require_tags(entry.get("topics"), field=f"entries[{index}].topics")
        _require_tags(entry.get("keywords"), field=f"entries[{index}].keywords")
        rank = entry.get("default_rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            raise NeoPublicKnowledgeError(f"entries[{index}].default_rank must be a positive integer.")
        if rank in ranks:
            raise NeoPublicKnowledgeError("Public knowledge default ranks must be unique.")
        ranks.add(rank)
        if entry.get("review_status") != PUBLIC_REVIEW_STATUS:
            raise NeoPublicKnowledgeError(f"entries[{index}] is not approved for guest use.")

    _validate_public_text(pack)
    return pack


def load_public_knowledge_pack() -> dict[str, Any]:
    """Load only the repository-owned public pack; callers cannot select another source."""

    pack_path = resolve_public_knowledge_path()
    try:
        payload = json.loads(pack_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NeoPublicKnowledgeError("Public knowledge pack is unavailable.") from exc
    except json.JSONDecodeError as exc:
        raise NeoPublicKnowledgeError("Public knowledge pack is invalid JSON.") from exc
    return validate_public_knowledge_pack(payload)


def _tokenize(value: str) -> set[str]:
    tokens: set[str] = set()
    normalized = value.lower().replace("easyoutfit", "easy outfit").replace("_", " ")
    for token in _TOKEN_RE.findall(normalized):
        if token in _STOP_WORDS or (len(token) < 3 and token != "ai"):
            continue
        tokens.add(token)
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            tokens.add(token[:-1])
    return tokens


def _normalized_phrase(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.lower().replace("_", " ")))


def _score_entry(entry: dict[str, Any], query_terms: set[str], query_phrase: str) -> int:
    if not query_terms:
        return 0

    keyword_terms = _tokenize(" ".join(entry["keywords"]))
    topic_terms = _tokenize(" ".join(entry["topics"]))
    title_terms = _tokenize(entry["title"])
    statement_terms = _tokenize(entry["statement"])
    evidence_terms = _tokenize(entry["evidence"])
    use_when_terms = _tokenize(entry["use_when"])

    score = 0
    score += 12 * len(query_terms & keyword_terms)
    score += 9 * len(query_terms & topic_terms)
    score += 6 * len(query_terms & title_terms)
    score += 4 * len(query_terms & statement_terms)
    score += 3 * len(query_terms & evidence_terms)
    score += 2 * len(query_terms & use_when_terms)

    all_entry_terms = keyword_terms | topic_terms | title_terms | statement_terms | evidence_terms | use_when_terms
    matched_terms = query_terms & all_entry_terms
    score += round(10 * len(matched_terms) / max(len(query_terms), 1))

    searchable_text = _normalized_phrase(
        " ".join(
            [
                entry["title"],
                entry["statement"],
                entry["evidence"],
                entry["use_when"],
                " ".join(entry["topics"]),
                " ".join(entry["keywords"]),
            ]
        )
    )
    if len(query_phrase) >= 4 and query_phrase in searchable_text:
        score += 18

    if score > 0:
        if "story" in query_terms and entry["kind"] == "story":
            score += 12
        if query_terms & {"achievement", "result", "results", "win"} and entry["kind"] == "win":
            score += 12
        if query_terms & {"approach", "believe", "belief", "perspective", "principle"} and entry["kind"] == "claim":
            score += 10
    return score


def _validated_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise NeoPublicKnowledgeError(f"limit must be between 1 and {MAX_LIMIT}.")
    return limit


def _validated_context_limit(max_chars: int) -> int:
    if (
        not isinstance(max_chars, int)
        or isinstance(max_chars, bool)
        or not MIN_CONTEXT_CHARS <= max_chars <= MAX_CONTEXT_CHARS
    ):
        raise NeoPublicKnowledgeError(
            f"max_chars must be between {MIN_CONTEXT_CHARS} and {MAX_CONTEXT_CHARS}."
        )
    return max_chars


def select_public_knowledge(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Select only curated public entries using stable lexical scoring."""

    selected_limit = _validated_limit(limit)
    pack = load_public_knowledge_pack()
    return _select_from_pack(query, pack=pack, limit=selected_limit)


def _select_from_pack(
    query: str,
    *,
    pack: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    query_text = str(query or "")[:1_000]
    query_terms = _tokenize(query_text)
    query_phrase = _normalized_phrase(query_text)

    ranked = [
        (
            _score_entry(entry, query_terms, query_phrase),
            int(entry["default_rank"]),
            str(entry["id"]),
            entry,
        )
        for entry in pack["entries"]
    ]
    if {"easy", "outfit"}.issubset(query_terms):
        easy_outfit_entries = [item for item in ranked if "easy-outfit" in str(item[3]["id"])]
        easy_outfit_entries.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [dict(item[3]) for item in easy_outfit_entries[:limit]]

    relevant = [item for item in ranked if item[0] > 0]
    if relevant:
        relevant.sort(key=lambda item: (-item[0], item[1], item[2]))
        chosen = relevant[:limit]
    else:
        ranked.sort(key=lambda item: (item[1], item[2]))
        chosen = ranked[:limit]
    return [dict(item[3]) for item in chosen]


def _render_entry(entry: dict[str, Any]) -> str:
    lines = [f"[{entry['kind'].upper()}] {entry['title']}", entry["statement"]]
    if entry["evidence"] != entry["statement"]:
        lines.append(f"Evidence: {entry['evidence']}")
    lines.append(f"Best for: {entry['use_when']}")
    return "\n".join(lines)


def _render_bounded_context(
    pack: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    max_chars: int,
) -> tuple[str, list[dict[str, Any]]]:
    header = (
        f"APPROVED PUBLIC PROFESSIONAL KNOWLEDGE — v{pack['pack_version']}\n"
        "Use only these facts. If a requested detail is absent, say that the detail is not available."
    )
    blocks = [header]
    included: list[dict[str, Any]] = []
    kind_priority = {"win": 0, "story": 1, "bio": 2, "claim": 3}
    ordered_entries = sorted(
        enumerate(entries),
        key=lambda item: (kind_priority.get(str(item[1]["kind"]), 4), item[0]),
    )
    for _index, entry in ordered_entries:
        rendered_entry = _render_entry(entry)
        candidate = "\n\n".join([*blocks, rendered_entry])
        if len(candidate) > max_chars:
            break
        blocks.append(rendered_entry)
        included.append(entry)
    return "\n\n".join(blocks), included


def _render_approved_response(
    entries: list[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_RESPONSE_CHARS,
) -> str:
    """Join only whole approved statements without copying the guest query."""

    statements: list[str] = []
    seen: set[str] = set()
    response_chars = 0
    for entry in entries:
        statement = str(entry["statement"]).strip()
        if not statement or statement in seen:
            continue
        separator_chars = 1 if statements else 0
        if response_chars + separator_chars + len(statement) > max_chars:
            break
        statements.append(statement)
        seen.add(statement)
        response_chars += separator_chars + len(statement)
    return " ".join(statements)


def build_public_knowledge_context(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """Render a bounded, guest-safe context block from the curated pack."""

    selected_limit = _validated_limit(limit)
    context_limit = _validated_context_limit(max_chars)
    pack = load_public_knowledge_pack()
    entries = _select_from_pack(query, pack=pack, limit=selected_limit)
    context, _included = _render_bounded_context(
        pack,
        entries,
        max_chars=context_limit,
    )
    return context


def build_public_knowledge_selection(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> dict[str, Any]:
    """Return the deterministic selection envelope intended for future guest wiring."""

    selected_limit = _validated_limit(limit)
    context_limit = _validated_context_limit(max_chars)
    pack = load_public_knowledge_pack()
    entries = _select_from_pack(query, pack=pack, limit=selected_limit)
    context, included = _render_bounded_context(
        pack,
        entries,
        max_chars=context_limit,
    )
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "pack_version": pack["pack_version"],
        "persona_id": pack["persona_id"],
        "entry_ids": [entry["id"] for entry in included],
        "selected_count": len(included),
        "context": context,
        "response": _render_approved_response(included),
    }
