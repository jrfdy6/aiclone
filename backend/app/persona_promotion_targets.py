from __future__ import annotations


TARGET_BIO_FACTS = "identity/bio_facts.md"
TARGET_PHILOSOPHY = "identity/philosophy.md"
TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_AUDIENCE_COMMUNICATION = "identity/audience_communication.md"
TARGET_DECISION_PRINCIPLES = "identity/decision_principles.md"
TARGET_CLAIMS = "identity/claims.md"
TARGET_CONTENT_GUARDRAILS = "prompts/content_guardrails.md"
TARGET_OUTREACH_PLAYBOOK = "prompts/outreach_playbook.md"
TARGET_CONTENT_PILLARS = "prompts/content_pillars.md"
TARGET_CHANNEL_PLAYBOOKS = "prompts/channel_playbooks.md"
TARGET_CONTENT_EXAMPLES = "prompts/content_examples.md"
TARGET_TASTE_EXAMPLES = "prompts/taste_examples.md"
TARGET_RESUME = "history/resume.md"
TARGET_TIMELINE = "history/timeline.md"
TARGET_INITIATIVES = "history/initiatives.md"
TARGET_WINS = "history/wins.md"
TARGET_STORIES = "history/story_bank.md"
TARGET_SHIPPING_PROTOCOL = "history/shipping_protocol.md"
TARGET_EXTERNAL_REFERENCES = "references/external_reference_packets.md"
TARGET_PENDING_DELTAS = "inbox/pending_deltas.md"


# These are the only canonical files Brain review is allowed to promote into.
# Keep this deliberately smaller than the complete bundle file set: reference,
# prompt-example, and inbox files are canonical inputs but are not promotion sinks.
PERSONA_PROMOTION_TARGET_FILES = frozenset(
    {
        TARGET_PHILOSOPHY,
        TARGET_VOICE,
        TARGET_DECISION_PRINCIPLES,
        TARGET_CLAIMS,
        TARGET_CONTENT_PILLARS,
        TARGET_RESUME,
        TARGET_INITIATIVES,
        TARGET_WINS,
        TARGET_STORIES,
    }
)


# Static bundle paths protect scaffold writes from a compromised or malformed
# manifest while retaining every file currently owned by the persona bundle.
PERSONA_BUNDLE_FILES = frozenset(
    {
        TARGET_BIO_FACTS,
        TARGET_PHILOSOPHY,
        TARGET_VOICE,
        TARGET_AUDIENCE_COMMUNICATION,
        TARGET_DECISION_PRINCIPLES,
        TARGET_CLAIMS,
        TARGET_CONTENT_GUARDRAILS,
        TARGET_OUTREACH_PLAYBOOK,
        TARGET_CONTENT_PILLARS,
        TARGET_CHANNEL_PLAYBOOKS,
        TARGET_CONTENT_EXAMPLES,
        TARGET_TASTE_EXAMPLES,
        TARGET_RESUME,
        TARGET_TIMELINE,
        TARGET_INITIATIVES,
        TARGET_WINS,
        TARGET_STORIES,
        TARGET_SHIPPING_PROTOCOL,
        TARGET_EXTERNAL_REFERENCES,
        TARGET_PENDING_DELTAS,
    }
)


DEFAULT_PERSONA_BUNDLE_FILES = (
    TARGET_BIO_FACTS,
    TARGET_PHILOSOPHY,
    TARGET_VOICE,
    TARGET_AUDIENCE_COMMUNICATION,
    TARGET_DECISION_PRINCIPLES,
    TARGET_CLAIMS,
    TARGET_CONTENT_GUARDRAILS,
    TARGET_OUTREACH_PLAYBOOK,
    TARGET_CONTENT_PILLARS,
    TARGET_CHANNEL_PLAYBOOKS,
    TARGET_RESUME,
    TARGET_TIMELINE,
    TARGET_INITIATIVES,
    TARGET_WINS,
    TARGET_STORIES,
    TARGET_EXTERNAL_REFERENCES,
    TARGET_PENDING_DELTAS,
)


def validate_persona_promotion_target(value: str | None, *, allow_none: bool = False) -> str | None:
    target_file = str(value or "").strip()
    if not target_file:
        if allow_none:
            return None
        raise ValueError("Provide a canonical persona promotion target file.")
    if target_file not in PERSONA_PROMOTION_TARGET_FILES:
        raise ValueError("Unsupported persona promotion target file.")
    return target_file


def validate_persona_bundle_file(value: str | None) -> str:
    rel_path = str(value or "").strip()
    if rel_path not in PERSONA_BUNDLE_FILES:
        raise ValueError("Unsupported canonical persona bundle file.")
    return rel_path
