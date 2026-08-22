"""
AI-Powered Content Generation Routes

Generates content using:
1. User's persona and style from knowledge base
2. High-performing content examples
3. Topic intelligence data
4. PACER/Chris Do frameworks
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
import hashlib
import ipaddress
import os
import json
import re
import secrets
import time
from urllib.parse import urlsplit, urlunsplit

from app.services.embedders import embed_text
from app.services.content_generation_context_service import (
    ContentGenerationContext,
    build_content_generation_context,
)
from app.services.feezie_positioning_contract_service import (
    CAREER_SIGNAL_VALUES,
    EMPLOYER_PROXIMITY_VALUES,
    EMPLOYER_SAFETY_VALUES,
    PROOF_POSTURE_VALUES,
    load_feezie_strategy_contract,
    normalize_feezie_intent,
    normalize_feezie_pillar,
)
from app.services.feezie_portfolio_learning_service import (
    build_feezie_portfolio_learning_receipt,
)
from app.services.feezie_evidence_readiness_service import (
    EVIDENCE_CONTRACT_VERSION,
    EVIDENCE_KEYS,
    anonymize_feezie_public_text,
    evaluate_feezie_evidence_readiness,
)
from app.services.generated_fragment_promotion_service import promote_generated_fragment, undo_generated_fragment_promotion
from app.services.local_codex_context_cache_service import (
    build_context_cache_key,
    load_cached_context_packet,
    write_cached_context_packet,
)
from app.services.local_codex_generation_service import (
    append_job_artifacts,
    cancel_codex_job,
    claim_next_codex_job,
    complete_codex_job,
    create_codex_job,
    fail_codex_job,
    get_codex_job,
    list_codex_jobs,
    list_job_artifacts,
    read_job_artifact_content,
    write_job_artifact,
)
from app.services.linkedin_owner_review_service import ensure_generated_owner_review_item
from app.services.linkedin_performance_ledger_service import linkedin_performance_ledger_service
from app.services.feezie_exception_receipt_service import build_feezie_exception_receipts
from app.services.persona_bundle_context_service import retrieve_bundle_persona_chunks
from app.services.retrieval import retrieve_similar, retrieve_weighted
from app.services.trigger_identity_service import build_content_job_idempotency_key
from app.services.workspace_snapshot_store import get_snapshot_payload

router = APIRouter()

CONTENT_FAST_MODEL_ALIAS = "content-fast"
CONTENT_EDITOR_MODEL_ALIAS = "content-editor"
EMAIL_CONTENT_TYPES = {"email_reply", "email_follow_up", "outbound_email"}
FEEZIE_CODEX_DRAFT_OPTION_COUNT = 2
FEEZIE_CODEX_HOOK_VARIANT_COUNT = 8
FEEZIE_CODEX_DRAFT_CONTRACT_VERSION = "feezie_draft_contract/v1"
FEEZIE_ROLE_PAYLOAD_VERSION = "feezie_role_payload/v4"
FEEZIE_BLIND_CRITIC_RECEIPT_VERSION = "feezie_blind_critic_receipt/v1"
FEEZIE_BLIND_CRITIC_ORDER_STRATEGY = "job_scoped_sha256_sort_non_identity/v1"
FEEZIE_DETERMINISTIC_QUALITY_GATE_VERSION = "feezie_deterministic_quality_gate/v2"
FEEZIE_VOICE_CONTAMINATION_RECEIPT_VERSION = "feezie_voice_exemplar_contamination/v2"
FEEZIE_CRITIC_READY_SCORE = 8
FEEZIE_CRITIC_DIMENSIONS = ("truth", "safety", "intent", "voice", "hook")
FEEZIE_REVISION_CONTRACT_VERSION = "feezie_critic_guided_revision_contract/v1"
FEEZIE_REVISION_RECEIPT_VERSION = "feezie_revision_execution_receipt/v1"
FEEZIE_REMOTE_EXECUTION_CONTEXT_VERSION = "feezie_remote_execution_context/v1"
FEEZIE_REMOTE_PROMPT_POLICY_VERSION = "feezie_remote_prompt_policy/v4"
FEEZIE_CODEX_EXECUTION_PROFILE_VERSION = "feezie_codex_execution_profile/v1"
FEEZIE_REMOTE_JOB_PACKET_VERSION = "feezie_remote_job_packet/v1"
FEEZIE_REMOTE_BOOTSTRAP_PROMPT = (
    "FEEZIE remote-safe execution packet. Reconstruct each isolated writer and critic prompt "
    "only from remote_execution_context, evidence_contract, planned_option_briefs, and the "
    "declared draft and revision contracts."
)
FEEZIE_COMPLETION_RESULT_VERSION = "feezie_completion_result/v1"
FEEZIE_COMPLETION_ARTIFACT_VERSION = "feezie_completion_artifact/v1"
CODEX_COMPLETION_RESULT_VERSION = "codex_completion_result/v1"
FEEZIE_CODEX_MODEL = "gpt-5.6-sol"

CORE_BUNDLE_PATHS = {
    "identity/claims.md",
    "identity/philosophy.md",
    "identity/decision_principles.md",
    "identity/VOICE_PATTERNS.md",
    "identity/audience_communication.md",
    "prompts/content_guardrails.md",
    "prompts/content_pillars.md",
    "prompts/channel_playbooks.md",
    "prompts/outreach_playbook.md",
}
SUPPORT_BUNDLE_PATHS = {
    "identity/bio_facts.md",
    "history/story_bank.md",
    "history/wins.md",
    "history/timeline.md",
    "history/initiatives.md",
    "history/resume.md",
}
LEGACY_PERSONA_SOURCES = (
    "OWNER_PERSONA_OPTIMIZED.md",
    "OWNER_PERSONA.md",
)
LEGACY_EXAMPLE_TAGS = ["LINKEDIN_EXAMPLES"]
PROMPT_SECTION_ORDER = [
    "CORE CANON",
    "SUPPORTING CANON",
    "LEGACY SUPPORT",
    "RETRIEVAL SUPPORT",
]
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
AUDIENCE_FOCUS_TERMS = {
    "tech_ai": {"ai", "agent", "agents", "automation", "operator", "operators", "workflow", "workflows", "prompt", "prompting", "system", "systems", "shipping", "builder", "builders"},
    "leadership": {"leadership", "leaders", "manager", "managers", "team", "teams", "coaching", "culture", "clarity", "decision", "decisions"},
    "leadership_management": {"leadership", "leaders", "manager", "managers", "team", "teams", "coaching", "culture", "clarity", "decision", "decisions", "people", "behavior", "change", "adoption"},
    "education_admissions": {"education", "admissions", "enrollment", "families", "students", "referral", "school", "schools", "trust"},
    "fashion": {"fashion", "style", "closet", "wardrobe", "outfit", "confidence"},
    "neurodivergent": {"neurodivergent", "learning", "students", "families", "support", "fit"},
    "entrepreneurs": {"build", "building", "founder", "founders", "product", "shipping", "market", "customers"},
}
TOPIC_FOCUS_BOOSTS = {
    "workflow clarity": {"workflow", "clarity", "process", "processes", "handoff", "handoffs", "alignment", "operator", "system", "systems", "brain", "ops", "planner", "briefs", "snapshot", "routing"},
    "agent orchestration": {"agent", "agents", "orchestration", "workflow", "workflows", "automation", "prompting", "handoff", "handoffs", "operator", "system", "systems", "brain", "ops", "planner", "briefs", "snapshot", "routing"},
    "ai adoption": {"ai", "adoption", "adopt", "useful", "usage", "workflow", "constraints", "constraint", "operator", "operators", "system", "systems", "handoff", "handoffs", "shared", "state", "behavior"},
    "change management": {"change", "management", "leadership", "leaders", "people", "behavior", "adoption", "adopt", "coaching", "clarity", "execution", "priority", "priorities", "dashboard", "team", "teams"},
    "twice exceptional": {"2e", "admissions", "applicant", "applicants", "exceptional", "families", "family", "gifted", "learning", "neurodivergent", "prospective", "student", "students", "support", "twice"},
    "prospective students": {"admissions", "applicant", "applicants", "families", "family", "fit", "parent", "parents", "prospective", "student", "students", "support"},
    "neurodivergent students": {"2e", "families", "family", "learning", "neurodivergent", "school", "schools", "student", "students", "support", "twice", "exceptional"},
}
STRICT_AUDIENCE_ANCHOR_TERMS = {
    "education_admissions": {"admissions", "applicant", "applicants", "counselor", "counselors", "education", "enrollment", "families", "family", "learning", "parent", "parents", "school", "schools", "student", "students", "support"},
    "tech_ai": {"ai", "agent", "agents", "automation", "brain", "briefs", "handoff", "handoffs", "operator", "ops", "orchestration", "planner", "prompt", "prompting", "routing", "system", "systems", "workflow", "workflows"},
    "leadership_management": {"leadership", "leaders", "people", "behavior", "change", "team", "teams", "coaching", "adoption", "execution", "clarity"},
    "neurodivergent": {"2e", "families", "family", "learning", "neurodivergent", "parent", "parents", "school", "schools", "student", "students", "support", "twice", "exceptional"},
}
STUDENT_SUPPORT_TERMS = {"2e", "admissions", "applicant", "applicants", "education", "enrollment", "exceptional", "families", "family", "learning", "neurodivergent", "parent", "parents", "prospective", "school", "schools", "student", "students", "support", "twice"}
PROOF_KEYWORDS = {
    "built",
    "clarity",
    "evidence",
    "handoff",
    "handoffs",
    "improved",
    "launched",
    "metric",
    "metrics",
    "migration",
    "operator",
    "ops",
    "prompt",
    "prompting",
    "proof",
    "revenue",
    "salesforce",
    "shipped",
    "signal",
    "system",
    "systems",
    "workflow",
}
FRAMING_MODE_GUIDANCE = {
    "contrarian_reframe": "Push against a lazy default belief, then replace it with a sharper operating truth.",
    "agree_and_extend": "Start from agreement, then extend it with a stronger lesson or pattern.",
    "drama_tension": "Use real tension, stakes, or friction from the work without inventing facts.",
    "story_with_payoff": "Use a real eligible story, then land on a clear payoff.",
    "operator_lesson": "Lead through workflow, handoff, prompt, system, or operating-pattern clarity.",
    "recognition": "Center recognition or gratitude when real people or teams are part of the proof.",
    "warning": "Name the failure mode or hidden cost directly and explain why it matters.",
    "reframe": "Take a familiar idea and make the audience see it through a different lens.",
}
PUBLIC_POST_LANES = ("market_insight", "operator_lesson", "build_in_public")
PUBLIC_POST_LANE_GUIDANCE = {
    "market_insight": "Macro market, positioning, or competition lesson. Keep it external-facing and avoid internal build mechanics.",
    "operator_lesson": "Workflow, handoff, or decision-rule lesson with one concrete proof point. Keep the lesson practical and public-safe.",
    "build_in_public": "Talk about what the build taught you in macro terms. No file names, route labels, hidden mechanics, or internal control language.",
}
OPTION_DISTINCTNESS_JOBS = (
    {
        "thesis_treatment": (
            "Diagnosis: challenge the default reading and explain the bounded failure mechanism "
            "without broadening the approved claim."
        ),
        "proof_progression": (
            "Move from the claim to one approved proof detail, then explain what that detail diagnoses."
        ),
        "payoff": (
            "End with a declarative diagnostic implication or observable symptom that sharpens what the "
            "mechanism means. Do not give the reader a filter to use, a decision, rule, check, workflow, "
            "recommendation, or action. Make the final sentence specific and 4 to 10 words."
        ),
    },
    {
        "thesis_treatment": (
            "Rule-first application: lead with one concrete operating rule or check, then make its audience "
            "consequence visible without repeating the diagnosis option."
        ),
        "proof_progression": (
            "Move from the rule or check to the audience consequence, then use one approved proof detail as final "
            "validation. Do not reuse the diagnosis option's claim-to-proof-to-explanation order."
        ),
        "payoff": (
            "Land on the concrete consequence or tradeoff created by applying or ignoring the rule; do not repeat "
            "the rule or restate the first option's conclusion. Make the final sentence specific and 4 to 10 words."
        ),
    },
    {
        "thesis_treatment": (
            "Boundary: show the bounded risk or human consequence if the approved lesson is ignored."
        ),
        "proof_progression": (
            "Move from the risk to one approved proof detail, then show the boundary that contains it."
        ),
        "payoff": (
            "Land on the specific boundary or responsibility the reader should protect."
        ),
    },
)
PRINCIPLE_ONLY_SHARED_CLAIM_DISTINCTNESS_JOBS = (
    {
        "thesis_treatment": (
            "Causal diagnosis only: explain why the default reading fails inside the approved claim. "
            "Do not prescribe a solution, recommend a workflow, or list solution components."
        ),
        "proof_progression": (
            "With no approved proof, move from the claim to the bounded causal mechanism, then to a recognition signal. "
            "Do not turn the diagnosis into a solution architecture."
        ),
        "payoff": (
            "Land on a declarative belief filter that helps the reader recognize the cause. Do not phrase it as "
            "advice and do not give an action plan, rule, check, workflow, or recommendation."
        ),
    },
    {
        "thesis_treatment": (
            "Rule-first application only: start with one concrete operating rule or check, then make the audience "
            "consequence visible. "
            "Do not re-explain why the claim is true or replay the diagnosis."
        ),
        "proof_progression": (
            "With no approved proof, move from the rule or check directly to its audience consequence and boundary. "
            "Do not repeat the first option's causal chain or turn the rule into pseudo-proof."
        ),
        "payoff": (
            "Land on the concrete consequence or tradeoff of applying or ignoring the rule; do not repeat the rule "
            "or summarize the diagnosis."
        ),
    },
)
DIAGNOSIS_PROOF_ROLE_TERMS = frozenset(
    {
        "ambiguity",
        "broke",
        "broken",
        "failed",
        "failure",
        "gap",
        "hidden",
        "missing",
        "risk",
        "unclear",
        "unreliable",
        "vanished",
    }
)
APPLICATION_PROOF_ROLE_TERMS = frozenset(
    {
        "approval",
        "before",
        "boundary",
        "check",
        "confirmed",
        "decision",
        "gate",
        "handoff",
        "owner",
        "required",
        "review",
        "rule",
        "validated",
        "verification",
        "verified",
    }
)
SEMANTIC_ANCHOR_META_TERMS = frozenset(
    {
        "about",
        "after",
        "anonymized",
        "application",
        "approved",
        "assigned",
        "audience",
        "basis",
        "before",
        "boundary",
        "card",
        "claim",
        "concept",
        "concepts",
        "consequence",
        "context",
        "decision",
        "derived",
        "diagnosis",
        "distinct",
        "evidence",
        "expected",
        "focus",
        "input",
        "inputs",
        "confirmed",
        "discovered",
        "found",
        "learned",
        "mechanism",
        "noticed",
        "observed",
        "old",
        "only",
        "outcome",
        "posture",
        "principle",
        "proof",
        "public",
        "recognition",
        "reliance",
        "realized",
        "required",
        "role",
        "rule",
        "safe",
        "selected",
        "source",
        "test",
        "that",
        "their",
        "these",
        "thesis",
        "through",
        "topic",
        "tradeoff",
        "until",
        "visible",
        "when",
        "where",
        "which",
        "will",
        "without",
    }
)
GENERIC_SENTENCE_OPENERS = {
    "Are",
    "Big",
    "Can",
    "Clear",
    "Clarity",
    "Good",
    "Here",
    "How",
    "I",
    "If",
    "It",
    "Listen",
    "Look",
    "Most",
    "Read",
    "Real",
    "Teams",
    "That",
    "The",
    "This",
    "Without",
    "Workflow",
    "Write",
    "Yall",
    "You",
    "Your",
}
UNSUPPORTED_EVIDENCE_PLACEHOLDERS = {
    "article",
    "case study",
    "company",
    "course",
    "podcast",
    "school",
    "talk",
    "university",
    "video",
    "webinar",
}
DEFAULT_VOICE_DIRECTIVES = [
    "Lead with clarity, not hype.",
    "Front-load the thesis instead of warming up slowly.",
    "Use short, punchy lines when the point needs force.",
    "Let strategy lead and let proof support it.",
    "Keep the writing casual, direct, and operator-grounded.",
    "Avoid generic opener formulas like 'X is essential' or 'In today's world'.",
]
AUDIENCE_PROMPT_LABELS = {
    "general": "General professionals",
    "education_admissions": "Education and admissions leaders",
    "tech_ai": "Tech and AI builders, founders, and operators",
    "fashion": "Fashion and style audiences",
    "leadership": "Leaders and managers",
    "leadership_management": "Leaders and managers",
    "neurodivergent": "Neurodivergent people, families, and supporters",
    "entrepreneurs": "Entrepreneurs and founders",
}
FEEZIE_AUDIENCE_ALIASES = {
    "education_leaders": "education_admissions",
    "school_leaders_and_admissions_operators": "education_admissions",
    "ai_systems_operators": "tech_ai",
    "ai_builders_and_operators": "tech_ai",
}
FEEZIE_SOURCE_MODES = {
    "persona_only",
    "reservoir_ranked",
    "selected_source",
    "recent_signals",
    "email_thread_grounded",
}
HOUSE_SCAFFOLD_SENTENCES = {
    "not more reporting.",
    "clearer action.",
    "that is the operating model.",
    "that is where it breaks.",
    "that is when the work slips.",
    "otherwise it's just another tab.",
    "that is the payoff.",
    "that is the part worth carrying forward.",
    "that is what the build taught us.",
    "read that again.",
    "clarity has to come first.",
    "clarity is the part that scales.",
    "that kind of work deserves to be named.",
    "that deserves more credit than it gets.",
}
IDENTITY_SCAFFOLD_PATTERNS = (
    re.compile(r"\beducation changed my (?:life|trajectory)\b", re.IGNORECASE),
    re.compile(r"\bmy education voice\b", re.IGNORECASE),
    re.compile(r"\binstitutional worship\b", re.IGNORECASE),
)
VOICE_DIRECTIVE_HINTS = (
    "lead with",
    "front-load",
    "use short",
    "keep ",
    "avoid ",
    "start from",
    "end with",
    "let ",
    "sound like",
    "tell you what tho",
    "y'all",
    "yall",
    "say it with me",
    "big shout-out",
    "makes no sense",
)
FLAT_GENERIC_PATTERNS = (
    re.compile(r"\bin today's\b", re.IGNORECASE),
    re.compile(r"\b(?:workflow clarity|agent orchestration|leadership|ai|clarity)\s+is\s+(?:essential|critical|important)\b", re.IGNORECASE),
    re.compile(r"\b(?:drive|drives)\s+real\s+results\b", re.IGNORECASE),
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
    re.compile(r"\bit['’]s not just about\b", re.IGNORECASE),
    re.compile(r"\bit['’]s all about\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+now\s+(?:essential|critical|important)\b", re.IGNORECASE),
    re.compile(r"\bconnecting the dots\b", re.IGNORECASE),
    re.compile(r"\bfor effective ai\b", re.IGNORECASE),
    re.compile(r"\bcomponents of the operation must be interconnected\b", re.IGNORECASE),
    re.compile(r"\bthis integration is crucial\b", re.IGNORECASE),
    re.compile(r"\b(?:fundamental|major|complete)\s+transformation\b", re.IGNORECASE),
    re.compile(r"\bpaving the way\b", re.IGNORECASE),
    re.compile(r"\bbigger picture\b", re.IGNORECASE),
    re.compile(r"\bai thrives when\b", re.IGNORECASE),
    re.compile(r"\b(?:empower|empowers|empowering)\b.*\bteam\b", re.IGNORECASE),
)
GENERIC_CLOSER_PATTERNS = (
    re.compile(r"^let['’]?s\s+(?:keep|continue)\b", re.IGNORECASE),
    re.compile(r"\bcontinue\s+striving\b", re.IGNORECASE),
    re.compile(r"\bkeep pushing\b", re.IGNORECASE),
    re.compile(r"\bmoving in the right direction\b", re.IGNORECASE),
)
WEAK_ENDING_PATTERNS = (
    re.compile(r"\btangible impact\b", re.IGNORECASE),
    re.compile(r"\bmeaningful impact\b", re.IGNORECASE),
    re.compile(r"\bbetter outcomes\b", re.IGNORECASE),
    re.compile(r"\beverything(?:['’]s| is) interconnected\b", re.IGNORECASE),
    re.compile(r"\btransforming how we work\b", re.IGNORECASE),
    re.compile(r"\bmaking (?:a|an) (?:real|tangible|meaningful) impact\b", re.IGNORECASE),
    re.compile(r"\bthis changes everything\b", re.IGNORECASE),
)
TASTE_NEGATIVE_PATTERNS = (
    re.compile(r"\bcohesive system\b", re.IGNORECASE),
    re.compile(r"\bdependable architecture\b", re.IGNORECASE),
    re.compile(r"\bcomprehensive view\b", re.IGNORECASE),
    re.compile(r"\bunified approach\b", re.IGNORECASE),
    re.compile(r"\bseamless(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bfor effective ai\b", re.IGNORECASE),
    re.compile(r"\binterconnected\b", re.IGNORECASE),
    re.compile(r"\bthis integration is crucial\b", re.IGNORECASE),
    re.compile(r"\b(?:transition|transitioned|transitioning)\b.*\barchitecture\b", re.IGNORECASE),
    re.compile(r"\bnew level of efficiency\b", re.IGNORECASE),
    re.compile(r"\bstreamlined workflow\b", re.IGNORECASE),
    re.compile(r"\b(?:enhance|enhances|enhancing)\s+(?:execution|strategy|collaboration)\b", re.IGNORECASE),
    re.compile(r"\bfunction in unison\b", re.IGNORECASE),
    re.compile(r"\bmoving in the right direction\b", re.IGNORECASE),
    re.compile(r"\bread that again\b", re.IGNORECASE),
    re.compile(r"\bwrite that down\b", re.IGNORECASE),
    re.compile(r"\bcommand center\b", re.IGNORECASE),
)
INTERNAL_PUBLIC_JARGON_PATTERNS = (
    re.compile(r"\bai clone\s*/\s*brain system\b", re.IGNORECASE),
    re.compile(r"\bpersona soup\b", re.IGNORECASE),
    re.compile(r"\bproof packets?\b", re.IGNORECASE),
    re.compile(r"\btyped (?:core|proof|story|example|context|support) lanes?\b", re.IGNORECASE),
    re.compile(r"\btyped lanes?\b", re.IGNORECASE),
    re.compile(r"\bdomain gates?\b", re.IGNORECASE),
    re.compile(r"\bgreen[- ]or[- ]red board\b", re.IGNORECASE),
    re.compile(r"\bproof lanes?\b", re.IGNORECASE),
    re.compile(r"\bcore, proof, story, and example lanes\b", re.IGNORECASE),
    re.compile(r"\bcanon through typed lanes\b", re.IGNORECASE),
    re.compile(r"\bno proof packet\b", re.IGNORECASE),
    re.compile(r"\brouted workspace snapshot\b", re.IGNORECASE),
    re.compile(r"\bdaily briefs\b", re.IGNORECASE),
    re.compile(r"\bpersona review\b", re.IGNORECASE),
    re.compile(r"\blong-form routing\b", re.IGNORECASE),
    re.compile(r"\bshared workspace state\b", re.IGNORECASE),
    re.compile(r"\bproof-aware prompts?\b", re.IGNORECASE),
    re.compile(r"\btyped retrieval\b", re.IGNORECASE),
    re.compile(
        r"\bbounded (?:comparison|lesson|observation|test detail|writing comparison)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:proof|evidence) posture\b", re.IGNORECASE),
    re.compile(r"\bobservable lesson\b", re.IGNORECASE),
    re.compile(r"\bediting (?:contract|constraint|language)\b", re.IGNORECASE),
    re.compile(r"\bdeterministic preflight\b", re.IGNORECASE),
)
TASTE_POSITIVE_PATTERNS = (
    re.compile(r"\breal talk\b", re.IGNORECASE),
    re.compile(r"\btell you what tho\b", re.IGNORECASE),
    re.compile(r"\bmakes no sense\.?\s*period\b", re.IGNORECASE),
    re.compile(r"\bthat will not work\b", re.IGNORECASE),
    re.compile(r"\bthat dog will not hunt\b", re.IGNORECASE),
    re.compile(r"\bwhere'?s the artifact\b", re.IGNORECASE),
    re.compile(r"\bpeople are not gonna use that\b", re.IGNORECASE),
    re.compile(r"\bbig shout-out\b", re.IGNORECASE),
    re.compile(r"\by['’]?all\b", re.IGNORECASE),
)
TASTE_CONTRAST_PATTERNS = (
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\binstead of\b", re.IGNORECASE),
    re.compile(r"\bbut\b", re.IGNORECASE),
    re.compile(r"\bthan\b", re.IGNORECASE),
    re.compile(r"\bnow\b", re.IGNORECASE),
    re.compile(r"\bpreviously\b", re.IGNORECASE),
    re.compile(r"\bif\b", re.IGNORECASE),
    re.compile(r"\bthat sounds good, but\b", re.IGNORECASE),
)
OPERATOR_CATALOG_MARKERS = (
    "brain",
    "ops",
    "daily briefs",
    "planner",
    "persona review",
    "long-form routing",
    "proof-aware prompts",
    "shared workspace state",
    "explicit handoffs",
    "routed workspace snapshot",
)


class ContentGenerationRequest(BaseModel):
    user_id: str = Field(..., description="User ID for knowledge base lookup")
    topic: str = Field(..., description="Content topic")
    context: Optional[str] = Field(None, description="Additional context")
    content_type: str = Field("linkedin_post", description="Type: linkedin_post, cold_email, linkedin_dm, instagram_post, email_reply, email_follow_up, outbound_email")
    category: str = Field("value", description="FEEZIE post intent: value, invitation, personal")
    pacer_elements: List[str] = Field(default_factory=list, description="PACER elements to include: Problem, Amplify, Credibility, Educate, Request")
    tone: str = Field("expert_direct", description="Tone: expert_direct, inspiring, conversational")
    audience: str = Field("general", description="Target audience: general, education_admissions, tech_ai, fashion, leadership, neurodivergent, entrepreneurs")
    source_mode: str = Field(
        "persona_only",
        description="How generation should attach to evidence: persona_only, reservoir_ranked, selected_source, recent_signals, email_thread_grounded",
    )
    canonical_pillar: str | None = Field(default=None, description="Owner-approved FEEZIE editorial pillar")
    career_signal: str | None = Field(default=None, description="Public career signal: education_anchor, bridge, tech_proof")
    employer_proximity: str | None = Field(default=None, description="Relationship of the proof to the current employer")
    employer_safety: str | None = Field(default=None, description="Employer-safety disposition for the candidate")
    proof_posture: str | None = Field(default=None, description="Proof posture for the candidate")
    treatment: str | None = Field(default=None, description="Optional measurement-pilot treatment")
    option_count: Literal[1, 3] = Field(
        1,
        description=(
            "Generate one canonical result by default. Three options are admitted only "
            "when an explicit legacy generic compatibility caller requests them."
        ),
    )

    @field_validator("category", mode="before")
    @classmethod
    def validate_intent(cls, value: Any) -> str:
        return normalize_feezie_intent(value, default="value")

    @field_validator("audience", mode="before")
    @classmethod
    def validate_audience(cls, value: Any) -> str:
        cleaned = re.sub(r"[\s-]+", "_", str(value or "general").strip().lower())
        cleaned = FEEZIE_AUDIENCE_ALIASES.get(cleaned, cleaned)
        if cleaned not in AUDIENCE_PROMPT_LABELS:
            raise ValueError("Unsupported content-generation audience")
        return cleaned

    @field_validator("source_mode", mode="before")
    @classmethod
    def validate_source_mode(cls, value: Any) -> str:
        cleaned = re.sub(r"[\s-]+", "_", str(value or "persona_only").strip().lower())
        if cleaned not in FEEZIE_SOURCE_MODES:
            raise ValueError("Unsupported content-generation source_mode")
        return cleaned

    @field_validator("canonical_pillar", mode="before")
    @classmethod
    def normalize_canonical_pillar(cls, value: Any) -> str | None:
        if value is None or not str(value).strip():
            return None
        return normalize_feezie_pillar(value)

    @field_validator("career_signal", "employer_proximity", "employer_safety", "proof_posture", "treatment", mode="before")
    @classmethod
    def clean_optional_strategy_value(cls, value: Any) -> str | None:
        cleaned = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
        return cleaned or None

    @field_validator("career_signal")
    @classmethod
    def validate_career_signal(cls, value: str | None) -> str | None:
        if value is not None and value not in CAREER_SIGNAL_VALUES:
            raise ValueError("Unsupported FEEZIE career_signal")
        return value

    @field_validator("employer_proximity")
    @classmethod
    def validate_employer_proximity(cls, value: str | None) -> str | None:
        if value is not None and value not in EMPLOYER_PROXIMITY_VALUES:
            raise ValueError("Unsupported FEEZIE employer_proximity")
        return value

    @field_validator("employer_safety")
    @classmethod
    def validate_employer_safety(cls, value: str | None) -> str | None:
        if value is not None and value not in EMPLOYER_SAFETY_VALUES:
            raise ValueError("Unsupported FEEZIE employer_safety")
        return value

    @field_validator("proof_posture")
    @classmethod
    def validate_proof_posture(cls, value: str | None) -> str | None:
        if value is not None and value not in PROOF_POSTURE_VALUES:
            raise ValueError("Unsupported FEEZIE proof_posture")
        return value


class ContentGenerationResponse(BaseModel):
    success: bool
    options: List[str]
    persona_context: Optional[str] = None
    examples_used: List[str] = []
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class ContentContextAuditResponse(BaseModel):
    success: bool
    persona_context: Optional[str] = None
    grounding_mode: str
    grounding_reason: str
    framing_modes: List[str] = Field(default_factory=list)
    primary_claims: List[str] = Field(default_factory=list)
    proof_packets: List[str] = Field(default_factory=list)
    story_beats: List[str] = Field(default_factory=list)
    audit: Dict[str, Any] = Field(default_factory=dict)


class ContentReservoirSupportItem(BaseModel):
    source_id: str | None = None
    asset_id: str | None = None
    reservoir_lane: str | None = None
    primary_type: str | None = None
    score: int | None = None
    title: str | None = None
    text: str | None = None
    source_path: str | None = None
    source_url: str | None = None


class GeneratedFragmentPromotionRequest(BaseModel):
    user_id: str = Field(..., description="User ID for attribution")
    fragment_text: str = Field(..., description="Selected generated fragment")
    option_text: str = Field(..., description="Full generated option text")
    option_index: int | None = Field(default=None, description="0-based option index")
    topic: str = Field(..., description="Generation topic")
    audience: str = Field(..., description="Generation audience")
    category: str = Field(..., description="Generation category")
    content_type: str = Field("linkedin_post", description="Generation content type")
    source_mode: str = Field("persona_only", description="Generation source mode")
    support_items: list[ContentReservoirSupportItem] = Field(default_factory=list)
    option_brief: Dict[str, Any] | None = Field(default=None, description="Optional framing brief for the chosen option")
    published: bool = Field(default=False, description="Whether the fragment came from a published post")

    @field_validator("category", mode="before")
    @classmethod
    def validate_intent(cls, value: Any) -> str:
        return normalize_feezie_intent(value, default="value")


class GeneratedFragmentPromotionResponse(BaseModel):
    success: bool
    duplicate: bool = False
    delta_id: str
    route_key: str
    route_reason: str
    target_file: str
    target_label: str
    written_files: list[str] = Field(default_factory=list)
    delta: Dict[str, Any] = Field(default_factory=dict)
    message: str


class UndoGeneratedFragmentPromotionRequest(BaseModel):
    delta_id: str = Field(..., description="Committed generated-fragment delta id")


class UndoGeneratedFragmentPromotionResponse(BaseModel):
    success: bool
    already_reverted: bool = False
    delta_id: str
    removed_target_files: list[str] = Field(default_factory=list)
    preserved_target_files: list[str] = Field(default_factory=list)
    message: str


class LocalCodexSourceCard(BaseModel):
    item_key: str | None = Field(default=None, description="Stable key for the selected source item")
    brief_id: str | None = Field(default=None, description="Daily brief that surfaced the source item")
    origin_type: str | None = Field(default=None, description="Product surface or record type that originated the handoff")
    origin_id: str | None = Field(default=None, description="Stable identifier for the originating record")
    owner_reaction: str | None = Field(default=None, description="Owner-provided reaction or framing instruction")
    title: str | None = Field(default=None, description="Public-safe source title")
    summary: str | None = Field(default=None, description="Public-safe source summary")
    hook: str | None = Field(default=None, description="Public-safe standout line or hook")
    source_url: str | None = Field(default=None, description="Original public source URL")
    source_path: str | None = Field(default=None, description="Private source artifact path; never copied into the writer prompt")
    priority_lane: str | None = Field(default=None, description="Workspace interpretation lane")
    source_kind: str | None = Field(default=None, description="Source provenance class")
    route_reason: str | None = Field(default=None, description="Why the source was routed into writing")
    target_file: str | None = Field(default=None, description="Private canonical target hint; never copied into the writer prompt")
    section: str | None = Field(default=None, description="Human-readable source section")
    canonical_pillar: str | None = Field(default=None, description="Owner-approved FEEZIE editorial pillar")
    career_signal: str | None = Field(default=None, description="Owner-approved public career signal")
    employer_proximity: str | None = Field(default=None, description="Owner-approved employer proximity")
    employer_safety: str | None = Field(default=None, description="Owner-approved employer safety disposition")
    proof_posture: str | None = Field(default=None, description="Owner-approved proof posture")
    concrete_action: str | None = Field(default=None, description="Public-safe artifact, action, test, change, or decision")
    exact_problem: str | None = Field(default=None, description="Public-safe exact problem or failure behind the action")
    observable_lesson: str | None = Field(default=None, description="Public-safe observed lesson or next test")
    qualification_route: str | None = Field(default=None, description="Upstream idea qualification route")
    owner_question: str | None = Field(default=None, description="Upstream single owner clarification question")
    proof_prompt: str | None = Field(default=None, description="Upstream public-safe proof-development prompt")
    treatment: str | None = Field(default=None, description="Measurement-pilot treatment")
    publish_posture: str | None = Field(default=None, description="Upstream publish/review posture")
    audience: str | None = Field(default=None, description="Precise owner-approved audience segment")
    audience_consequence: str | None = Field(default=None, description="Why the topic matters to that audience")
    distinct_thesis: str | None = Field(default=None, description="The candidate's differentiated claim")
    why_now: str | None = Field(default=None, description="Verified reason the topic matters now")
    development_status: str | None = Field(default=None, description="Candidate development disposition")
    source_published_at: str | None = Field(default=None, description="Original source publication time when known")
    source_observed_at: str | None = Field(default=None, description="Time the source signal was observed when known")
    freshness_state: str | None = Field(default=None, description="Explicit source freshness state")
    source_temporality: str | None = Field(default=None, description="Whether the source is a trend or evergreen input")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Additional private provenance retained with the job")

    @field_validator("canonical_pillar", mode="before")
    @classmethod
    def normalize_canonical_pillar(cls, value: Any) -> str | None:
        if value is None or not str(value).strip():
            return None
        return normalize_feezie_pillar(value)

    @field_validator("career_signal", "employer_proximity", "employer_safety", "proof_posture", "treatment", "development_status", "freshness_state", "source_temporality", mode="before")
    @classmethod
    def clean_optional_strategy_value(cls, value: Any) -> str | None:
        cleaned = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
        return cleaned or None

    @field_validator("career_signal")
    @classmethod
    def validate_career_signal(cls, value: str | None) -> str | None:
        if value is not None and value not in CAREER_SIGNAL_VALUES:
            raise ValueError("Unsupported FEEZIE career_signal")
        return value

    @field_validator("employer_proximity")
    @classmethod
    def validate_employer_proximity(cls, value: str | None) -> str | None:
        if value is not None and value not in EMPLOYER_PROXIMITY_VALUES:
            raise ValueError("Unsupported FEEZIE employer_proximity")
        return value

    @field_validator("employer_safety")
    @classmethod
    def validate_employer_safety(cls, value: str | None) -> str | None:
        if value is not None and value not in EMPLOYER_SAFETY_VALUES:
            raise ValueError("Unsupported FEEZIE employer_safety")
        return value

    @field_validator("proof_posture")
    @classmethod
    def validate_proof_posture(cls, value: str | None) -> str | None:
        if value is not None and value not in PROOF_POSTURE_VALUES:
            raise ValueError("Unsupported FEEZIE proof_posture")
        return value


class LocalCodexEvidenceAnswers(BaseModel):
    model_config = {"extra": "forbid"}

    concrete_action: str | None = Field(default=None, max_length=1600)
    exact_problem: str | None = Field(default=None, max_length=1600)
    observable_lesson: str | None = Field(default=None, max_length=1600)

    @field_validator("concrete_action", "exact_problem", "observable_lesson", mode="before")
    @classmethod
    def clean_evidence_answer(cls, value: Any) -> str | None:
        cleaned = " ".join(str(value or "").split()).strip()
        return cleaned or None


class LocalCodexJobCreateRequest(ContentGenerationRequest):
    option_count: Literal[2] = Field(
        2,
        description=(
            "Exact two-option count for the deprecated FEEZIE compatibility comparator. "
            "Canonical owner-facing post generation uses the integrated lifecycle instead."
        ),
    )
    tone: str = Field(
        "conversational",
        description="FEEZIE draft posture: direct, curious, evidence-led, and non-guru",
    )
    workspace_slug: str = Field("linkedin-content-os", description="Workspace lane for the Codex job")
    idempotency_key: str | None = Field(default=None, description="Optional explicit idempotency key for thin triggers")
    source_card: LocalCodexSourceCard | None = Field(
        default=None,
        description="Optional typed Brain or Workspace source card used to seed this generation job",
    )
    evidence_answers: LocalCodexEvidenceAnswers | None = Field(
        default=None,
        description="Owner clarification answers accumulated one field at a time",
    )

    @model_validator(mode="after")
    def validate_selected_source(self) -> "LocalCodexJobCreateRequest":
        if self.source_mode == "selected_source" and self.source_card is None:
            raise ValueError("selected_source generation requires a source_card")
        return self


class LocalCodexJobCreateResponse(BaseModel):
    success: bool
    job_id: str | None = None
    status: str
    message: str
    clarification_key: str | None = None
    clarification_question: str | None = None
    evidence_readiness: Dict[str, Any] = Field(default_factory=dict)


class LocalCodexJobStatusResponse(BaseModel):
    success: bool
    job_id: str
    workspace_slug: str
    status: str
    requested_by: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    result: ContentGenerationResponse | None = None
    artifact_count: int = 0


class LocalCodexJobSendToReviewRequest(BaseModel):
    option_index: int = Field(..., ge=0, description="0-based completed option index to send to FEEZIE owner review")


class LocalCodexJobSendToReviewResponse(BaseModel):
    success: bool
    job_id: str
    option_index: int
    queue_id: str
    card_id: str
    duplicate: bool = False
    status: str
    approval_status: str
    publish_posture: str
    owner_review_required: bool
    message: str
    owner_review_item: Dict[str, Any] = Field(default_factory=dict)


class LocalCodexJobArtifactResponse(BaseModel):
    artifact_id: str
    kind: str
    label: str
    filename: str
    mime_type: str
    size_bytes: int | None = None
    created_at: str | None = None
    preview: str | None = None


class LocalCodexJobArtifactsResponse(BaseModel):
    success: bool
    job_id: str
    artifacts: list[LocalCodexJobArtifactResponse] = Field(default_factory=list)


class LocalCodexJobClaimRequest(BaseModel):
    worker_id: str = Field(..., description="Stable worker identity for the local Codex bridge")
    workspace_slug: str | None = Field(default=None, description="Optional workspace filter")


class LocalCodexJobClaimResponse(BaseModel):
    success: bool
    job_available: bool
    job_id: str | None = None
    status: str | None = None
    workspace_slug: str | None = None
    context_packet: Dict[str, Any] | None = None
    request_payload: Dict[str, Any] | None = None


class LocalCodexJobCompleteRequest(BaseModel):
    worker_id: str = Field(..., description="Worker identity completing the job")
    options: list[str] = Field(default_factory=list, description="Completed post options")
    model: str | None = Field(default=None, description="Codex model used for the run")
    raw_output: str | None = Field(default=None, description="Raw JSON/text returned by codex exec")
    command_stdout: str | None = Field(default=None, description="Optional recent stdout from the local runner")
    command_stderr: str | None = Field(default=None, description="Optional recent stderr from the local runner")
    result_payload: Dict[str, Any] | None = Field(default=None, description="Optional prebuilt generation result payload")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Optional text/json artifacts to persist for this job")


class LocalCodexJobFailRequest(BaseModel):
    worker_id: str = Field(..., description="Worker identity reporting the failure")
    error_message: str = Field(..., description="Failure details")


@dataclass
class ContentOptionBrief:
    option_number: int
    framing_mode: str
    primary_claim: str
    proof_packet: str
    story_beat: str
    public_lane: str = ""
    thesis_treatment: str = ""
    proof_progression: str = ""
    payoff: str = ""
    mechanism_focus: str = ""
    recognition_basis: str = ""
    mechanism_anchor_terms: List[str] = field(default_factory=list)
    recognition_anchor_terms: List[str] = field(default_factory=list)
    decision_rule_basis: str = ""
    decision_moment_basis: str = ""
    decision_moment_anchor_terms: List[str] = field(default_factory=list)
    required_context_concepts: str = ""
    consequence_basis: str = ""
    application_closing_anchor_terms: List[str] = field(default_factory=list)
    proof_facet_id: str = ""
    semantic_payload_version: str = ""


@dataclass
class ContentLLMProvider:
    name: str
    client: Any
    fast_model: str
    editor_model: str


class _ContentProviderChatCompletions:
    def __init__(self, router: "ContentLLMRouterClient") -> None:
        self._router = router

    def create(self, *, model: str, **kwargs):
        return self._router.create_chat_completion(model=model, **kwargs)


class _ContentProviderChat:
    def __init__(self, router: "ContentLLMRouterClient") -> None:
        self.completions = _ContentProviderChatCompletions(router)


class ContentLLMRouterClient:
    def __init__(self, providers: List[ContentLLMProvider]) -> None:
        if not providers:
            raise ValueError("No LLM providers configured for content generation")
        self.providers = providers
        self.chat = _ContentProviderChat(self)
        self.provider_trace: List[Dict[str, Any]] = []

    def create_chat_completion(self, *, model: str, **kwargs):
        errors: List[str] = []
        for provider in self.providers:
            actual_model = _resolve_provider_model(provider, model)
            call_kwargs = _normalize_chat_completion_kwargs(actual_model, kwargs)
            max_attempts = 1 + _provider_retry_attempts(provider)
            for attempt in range(1, max_attempts + 1):
                try:
                    response = provider.client.chat.completions.create(model=actual_model, **call_kwargs)
                    self.provider_trace.append(
                        {
                            "provider": provider.name,
                            "requested_model": model,
                            "actual_model": actual_model,
                            "status": "success",
                            "attempt": attempt,
                        }
                    )
                    return response
                except Exception as exc:
                    self.provider_trace.append(
                        {
                            "provider": provider.name,
                            "requested_model": model,
                            "actual_model": actual_model,
                            "status": "failed",
                            "error": str(exc)[:240],
                            "attempt": attempt,
                        }
                    )
                    if attempt < max_attempts and _should_retry_provider(provider, exc):
                        time.sleep(_provider_retry_delay_seconds(provider, attempt))
                        continue
                    if not _should_fallback_provider(exc):
                        raise
                    errors.append(f"{provider.name}:{actual_model}:{exc}")
                    break
        raise RuntimeError("All content-generation providers failed: " + " | ".join(errors))


def _normalized_chunk_key(item: Dict[str, Any]) -> str:
    return " ".join(str(item.get("chunk") or "").split()).strip().lower()


def _item_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _source_name(item: Dict[str, Any]) -> str:
    metadata = _item_metadata(item)
    return str(metadata.get("file_name") or metadata.get("source") or "")


def _bundle_path(item: Dict[str, Any]) -> str:
    metadata = _item_metadata(item)
    return str(metadata.get("bundle_path") or item.get("source_file_id") or "")


def _with_prompt_section(item: Dict[str, Any], section: str) -> Dict[str, Any]:
    hydrated = dict(item)
    metadata = dict(_item_metadata(item))
    metadata["prompt_section"] = section
    hydrated["metadata"] = metadata
    return hydrated


def _append_unique(
    destination: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    *,
    limit: int,
    seen: set[str],
    section: str,
) -> None:
    for item in candidates:
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        destination.append(_with_prompt_section(item, section))
        if len(destination) >= limit:
            return


def _collect_prompt_visible_chunks(
    *,
    persona_chunks: List[Dict[str, Any]],
    topic_anchor_chunks: List[Dict[str, Any]],
    eligible_story_chunks: List[Dict[str, Any]],
    proof_anchor_chunks: List[Dict[str, Any]],
    topic: str,
    audience: str,
) -> List[Dict[str, Any]]:
    visible: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(items: List[Dict[str, Any]], *, limit: int | None = None) -> None:
        for item in items:
            key = _normalized_chunk_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            visible.append(item)
            if limit is not None and len(visible) >= limit:
                return

    core_chunks = [
        item
        for item in persona_chunks
        if str(_item_metadata(item).get("prompt_section") or "") == "CORE CANON"
    ]
    add(core_chunks, limit=4)
    add(topic_anchor_chunks)
    add(proof_anchor_chunks)
    add(eligible_story_chunks)

    if len(visible) < 5:
        focus_terms = _focus_terms(topic, audience)
        supporting_chunks = [
            item
            for item in persona_chunks
            if str(_item_metadata(item).get("prompt_section") or "") == "SUPPORTING CANON"
            and _passes_audience_anchor_gate(_split_use_when_text(str(item.get("chunk") or ""))[0], audience, topic)
            and _chunk_focus_score(_split_use_when_text(str(item.get("chunk") or ""))[0], focus_terms, topic) > 0
        ]
        add(supporting_chunks, limit=6)

    return visible


def curate_persona_prompt_chunks(
    *,
    bundle_chunks: List[Dict[str, Any]],
    legacy_support_chunks: List[Dict[str, Any]],
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 9,
) -> List[Dict[str, Any]]:
    core_chunks = [item for item in bundle_chunks if _bundle_path(item) in CORE_BUNDLE_PATHS]
    support_chunks = [item for item in bundle_chunks if _bundle_path(item) in SUPPORT_BUNDLE_PATHS]
    bundle_other_chunks = [
        item
        for item in bundle_chunks
        if _bundle_path(item) not in CORE_BUNDLE_PATHS and _bundle_path(item) not in SUPPORT_BUNDLE_PATHS
    ]
    legacy_chunks = [
        item
        for item in legacy_support_chunks
        if _source_name(item) in LEGACY_PERSONA_SOURCES and item.get("persona_tag") != "LINKEDIN_EXAMPLES"
    ]
    retrieval_support_chunks = [
        item
        for item in retrieved_chunks
        if _source_name(item) not in LEGACY_PERSONA_SOURCES and item.get("persona_tag") != "LINKEDIN_EXAMPLES"
    ]

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    _append_unique(curated, core_chunks, limit=min(top_k, 4), seen=seen, section="CORE CANON")
    _append_unique(curated, support_chunks, limit=min(top_k, 7), seen=seen, section="SUPPORTING CANON")
    _append_unique(curated, legacy_chunks, limit=min(top_k, 9), seen=seen, section="LEGACY SUPPORT")
    _append_unique(curated, bundle_other_chunks, limit=min(top_k, 9), seen=seen, section="SUPPORTING CANON")
    _append_unique(curated, retrieval_support_chunks, limit=top_k, seen=seen, section="RETRIEVAL SUPPORT")
    return curated[:top_k]


def retrieve_legacy_support_chunks(
    *,
    user_id: str,
    query_embedding: List[float],
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    for source_name in LEGACY_PERSONA_SOURCES:
        items = retrieve_similar(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
            source_filter=source_name,
        )
        if items:
            return items
    return []


def retrieve_curated_example_chunks(
    *,
    user_id: str,
    query_embedding: List[float],
    content_type: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    if content_type == "linkedin_post":
        for source_name in LEGACY_PERSONA_SOURCES:
            items = retrieve_similar(
                user_id=user_id,
                query_embedding=query_embedding,
                top_k=top_k,
                tag_filter=LEGACY_EXAMPLE_TAGS,
                source_filter=source_name,
            )
            if items:
                return items
    return retrieve_similar(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )


def filter_example_chunks_by_topic(
    example_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, Dict[str, Any]]] = []
    for item in example_chunks:
        primary_text, _ = _split_use_when_text(str(item.get("chunk") or ""))
        score = _chunk_focus_score(primary_text, focus_terms, topic)
        if score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience, topic):
            continue
        ranked.append((score, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in sorted(ranked, key=lambda entry: entry[0], reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def summarize_persona_context(persona_chunks: List[Dict[str, Any]], topic: str) -> Optional[str]:
    normalized_topic = " ".join((topic or "").lower().split())
    if normalized_topic:
        for item in persona_chunks:
            chunk = str(item.get("chunk") or "")
            if normalized_topic in chunk.lower():
                return chunk[:200]
    for preferred_section in PROMPT_SECTION_ORDER:
        for item in persona_chunks:
            if _item_metadata(item).get("prompt_section") == preferred_section:
                return str(item.get("chunk") or "")[:200]
    return None


def _focus_terms(topic: str, audience: str) -> set[str]:
    normalized_topic = " ".join((topic or "").lower().split())
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_topic)
        if len(token) > 2 and token not in STOPWORDS
    }
    for phrase, boosts in TOPIC_FOCUS_BOOSTS.items():
        if phrase in normalized_topic:
            tokens.update(boosts)
    tokens.update(AUDIENCE_FOCUS_TERMS.get(audience, set()))
    return tokens


def _is_student_support_topic(topic: str, audience: str) -> bool:
    if audience in {"education_admissions", "neurodivergent"}:
        return True
    normalized_topic = " ".join((topic or "").lower().split())
    if not normalized_topic:
        return False
    if any(
        phrase in normalized_topic
        for phrase in (
            "twice exceptional",
            "twice-exceptional",
            "prospective students",
            "prospective student",
            "neurodivergent student",
            "neurodivergent students",
            "learning support",
        )
    ):
        return True
    tokens = set(re.findall(r"[a-z0-9]+", normalized_topic))
    return bool(tokens.intersection(STUDENT_SUPPORT_TERMS))


def _is_tech_ai_topic(topic: str, audience: str) -> bool:
    if audience == "tech_ai":
        return True
    normalized_topic = " ".join((topic or "").lower().split())
    return any(
        phrase in normalized_topic
        for phrase in (
            "workflow clarity",
            "agent orchestration",
            "ai adoption",
            "prompting",
            "automation",
            "handoff",
            "handoffs",
        )
    )


def _is_leadership_topic(topic: str, audience: str) -> bool:
    if audience in {"leadership", "leadership_management"}:
        return True
    normalized_topic = " ".join((topic or "").lower().split())
    return any(
        phrase in normalized_topic
        for phrase in (
            "change management",
            "leadership",
            "team",
            "coaching",
            "manager",
            "stakeholder",
        )
    )


def _is_fashion_topic(topic: str, audience: str) -> bool:
    if audience == "fashion":
        return True
    normalized_topic = " ".join((topic or "").lower().split())
    return any(term in normalized_topic for term in ("fashion", "style", "outfit", "wardrobe", "closet"))


def _is_entrepreneur_topic(topic: str, audience: str) -> bool:
    if audience == "entrepreneurs":
        return True
    normalized_topic = " ".join((topic or "").lower().split())
    return any(term in normalized_topic for term in ("founder", "founders", "startup", "product"))


def _topic_required_anchor_terms(topic: str, audience: str) -> set[str]:
    required_terms: set[str] = set()
    normalized_topic = " ".join((topic or "").lower().split())
    market_topic = any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants"))
    if _is_student_support_topic(topic, audience):
        required_terms.update(STUDENT_SUPPORT_TERMS)
    elif _is_tech_ai_topic(topic, audience) and not market_topic:
        required_terms.update(STRICT_AUDIENCE_ANCHOR_TERMS.get("tech_ai", set()))
    elif _is_leadership_topic(topic, audience):
        required_terms.update(STRICT_AUDIENCE_ANCHOR_TERMS.get("leadership_management", set()))
    elif _is_fashion_topic(topic, audience):
        required_terms.update(AUDIENCE_FOCUS_TERMS.get("fashion", set()))
    elif _is_entrepreneur_topic(topic, audience):
        required_terms.update(AUDIENCE_FOCUS_TERMS.get("entrepreneurs", set()))
    elif audience == "neurodivergent":
        required_terms.update(STRICT_AUDIENCE_ANCHOR_TERMS.get("neurodivergent", set()))
    return required_terms


def _chunk_focus_score(chunk: str, focus_terms: set[str], topic: str) -> int:
    normalized_chunk = " ".join((chunk or "").lower().split())
    normalized_topic = " ".join((topic or "").lower().split())
    if not normalized_chunk:
        return 0
    score = sum(1 for term in focus_terms if term and term in normalized_chunk)
    if normalized_topic and normalized_topic in normalized_chunk:
        score += 4
    return score


def _split_use_when_text(chunk: str) -> tuple[str, str]:
    normalized_chunk = " ".join((chunk or "").split())
    parts = normalized_chunk.split(" Use when:", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return normalized_chunk, ""


def _render_anchor_chunk(item: Dict[str, Any], *, include_use_when: bool = False) -> str:
    chunk = str(item.get("chunk") or "").strip()
    primary_text, use_when_text = _split_use_when_text(chunk)
    if include_use_when and use_when_text:
        return f"{primary_text} Use when: {use_when_text}"
    return primary_text


def _unique_texts(items: List[str], *, limit: int) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for item in items:
        normalized = " ".join((item or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
        if len(unique) >= limit:
            break
    return unique


def _prompt_topic_anchor_text(
    *,
    topic_anchor_chunks: List[Dict[str, Any]],
    primary_claims: List[str],
    limit: int,
) -> str:
    preferred = _unique_texts(primary_claims, limit=limit)
    if preferred:
        return "\n".join(f"- {item}" for item in preferred)
    return "\n".join(f"- {_render_anchor_chunk(item)}" for item in topic_anchor_chunks[:limit]) or "- No topic anchors available."


def _prompt_proof_anchor_text(
    *,
    proof_anchor_chunks: List[Dict[str, Any]],
    proof_packets: List[str],
    limit: int,
) -> str:
    preferred = _unique_texts([_proof_packet_evidence_text(packet) for packet in proof_packets], limit=limit)
    if preferred:
        return "\n".join(f"- {item}" for item in preferred)
    return "\n".join(f"- {_render_anchor_chunk(item)}" for item in proof_anchor_chunks[:limit]) or "- No strong proof anchor found."


def _prompt_story_anchor_text(
    *,
    story_anchor_chunks: List[Dict[str, Any]],
    story_beats: List[str],
    limit: int,
) -> str:
    preferred = _unique_texts(story_beats, limit=limit)
    if preferred:
        return "\n".join(f"- {item}" for item in preferred)
    if story_anchor_chunks:
        return "\n".join(f"- {_render_anchor_chunk(item, include_use_when=True)}" for item in story_anchor_chunks[:limit])
    return "- No approved story beat."


def _passes_audience_anchor_gate(chunk: str, audience: str, topic: str = "") -> bool:
    required_terms = _topic_required_anchor_terms(topic, audience)
    if not required_terms:
        return True
    normalized_chunk = " ".join((chunk or "").lower().split())
    return any(term in normalized_chunk for term in required_terms)


def select_topic_anchor_chunks(
    persona_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, int, Dict[str, Any]]] = []
    section_priority = {
        "CORE CANON": 4,
        "SUPPORTING CANON": 3,
        "LEGACY SUPPORT": 2,
        "RETRIEVAL SUPPORT": 1,
    }
    for item in persona_chunks:
        chunk = str(item.get("chunk") or "")
        primary_text, use_when_text = _split_use_when_text(chunk)
        focus_score = (_chunk_focus_score(primary_text, focus_terms, topic) * 3) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if focus_score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience, topic):
            continue
        section = str(_item_metadata(item).get("prompt_section") or "RETRIEVAL SUPPORT")
        priority = section_priority.get(section, 0)
        ranked.append((focus_score, priority, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, item in sorted(ranked, key=lambda entry: (entry[0], entry[1]), reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def select_eligible_story_chunks(
    persona_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    story_candidates: List[tuple[int, Dict[str, Any]]] = []
    for item in persona_chunks:
        tag = str(item.get("persona_tag") or "")
        section = str(_item_metadata(item).get("prompt_section") or "")
        if section == "CORE CANON":
            continue
        if tag not in {"EXPERIENCES", "VENTURES"}:
            continue
        primary_text, use_when_text = _split_use_when_text(str(item.get("chunk") or ""))
        score = (_chunk_focus_score(primary_text, focus_terms, topic) * 2) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience, topic):
            continue
        story_candidates.append((score, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in sorted(story_candidates, key=lambda entry: entry[0], reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def _proof_signal_score(chunk: str) -> int:
    normalized_chunk = " ".join((chunk or "").lower().split())
    if not normalized_chunk:
        return 0
    score = 0
    if "evidence:" in normalized_chunk:
        score += 4
    if "proof:" in normalized_chunk or "public-facing proof:" in normalized_chunk:
        score += 4
    if re.search(r"\b\d[\d.,x%$m]*\b", normalized_chunk):
        score += 3
    score += sum(1 for term in PROOF_KEYWORDS if term in normalized_chunk)
    return score


def select_proof_anchor_chunks(
    persona_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, int, int, Dict[str, Any]]] = []
    section_priority = {
        "CORE CANON": 4,
        "SUPPORTING CANON": 3,
        "LEGACY SUPPORT": 2,
        "RETRIEVAL SUPPORT": 1,
    }
    minimum_focus = 2 if audience == "tech_ai" or _is_student_support_topic(topic, audience) else 1
    for item in persona_chunks:
        chunk = str(item.get("chunk") or "")
        primary_text, _ = _split_use_when_text(chunk)
        focus_score = _chunk_focus_score(primary_text, focus_terms, topic)
        proof_score = _proof_signal_score(primary_text)
        if focus_score <= 0 and proof_score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience, topic):
            continue
        if proof_score > 0 and focus_score < minimum_focus:
            continue
        section = str(_item_metadata(item).get("prompt_section") or "RETRIEVAL SUPPORT")
        priority = section_priority.get(section, 0)
        ranked.append((focus_score * 4 + proof_score, proof_score, priority, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, _, item in sorted(ranked, key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def build_topic_focus_guidance(
    *,
    topic: str,
    audience: str,
    eligible_story_chunks: List[Dict[str, Any]],
) -> str:
    lines = [
        f'TOPIC DISCIPLINE: Stay tightly on "{topic}".',
        "Lead with the core claim or operating lesson, not a broad personal recap.",
    ]

    if audience == "tech_ai":
        lines.extend(
            [
                "Stay in the operator / AI systems lane: workflow clarity, prompting, automation, handoffs, and shipped execution.",
                "Do not reach for family, fashion, school, or community stories unless one appears in the eligible story anchors below.",
            ]
        )
    elif _is_student_support_topic(topic, audience):
        lines.extend(
            [
                "Keep the student, family, support, or counselor lens visible in every option.",
                "Do not borrow generic B2B trust, legacy-tech, or market-language proof unless it clearly comes back to the student experience.",
            ]
        )
    elif audience in {"leadership", "leadership_management"}:
        lines.extend(
            [
                "Stay in the leadership lane: clarity, coaching, team temperature, stakeholder influence, and operating cadence.",
                "Do not default to product-building or fashion stories unless the eligible story anchors make that link explicit.",
            ]
        )
    elif _is_fashion_topic(topic, audience):
        lines.extend(
            [
                "Stay in the fashion and personal-style lane: confidence, wardrobe choices, fit, and lived transformation.",
                "Do not drift into generic founder, leadership, or AI-systems language unless the topic explicitly requires it.",
            ]
        )
    elif _is_entrepreneur_topic(topic, audience):
        lines.extend(
            [
                "Stay in the founder / builder lane: market choices, customers, product decisions, and tradeoffs.",
                "Do not drift into generic school, family, or style anecdotes unless the eligible story anchors make that connection explicit.",
            ]
        )

    if eligible_story_chunks:
        lines.append("A personal story is optional. If you use one, it must come from the eligible story anchors below and connect to the topic in one sentence.")
    else:
        lines.append("No directly relevant story anchor was found. Do not force an anecdote. Use principle + proof instead.")
    return "\n".join(f"- {line}" for line in lines)


def build_proof_guidance(proof_anchor_chunks: List[Dict[str, Any]]) -> str:
    if proof_anchor_chunks:
        return "\n".join(
            [
                "- Each option must include at least one concrete proof anchor, named system, metric, or evidence phrase from the PROOF ANCHORS section below.",
                "- Prefer proof over abstraction: systems, migrations, shipped surfaces, prompting patterns, handoffs, metrics, or role-grounded evidence.",
                "- Do not make up numbers. If the proof anchor is qualitative, keep it qualitative but concrete.",
                "- Do not translate one metric into another. Keep the original subject and meaning of every proof anchor intact.",
            ]
        )
    return "\n".join(
        [
            "- No strong proof anchor was found. Stay concrete about process, role, and workflow mechanics.",
            "- Do not invent metrics or accomplishments.",
        ]
    )


def _clean_voice_directive(text: str) -> str:
    directive = " ".join((text or "").strip().strip("-*").split())
    directive = re.sub(r"^[A-Za-z][A-Za-z /&'()-]+:\s*", "", directive)
    return directive.strip()


def _extract_voice_directives(persona_chunks: List[Dict[str, Any]], *, limit: int = 8) -> List[str]:
    directives: List[str] = []
    seen: set[str] = set()
    for item in persona_chunks:
        metadata = _item_metadata(item)
        bundle_path = str(metadata.get("bundle_path") or item.get("source_file_id") or "")
        chunk = str(item.get("chunk") or "")
        tag = str(item.get("persona_tag") or "")
        if bundle_path != "identity/VOICE_PATTERNS.md" and "VOICE" not in tag and "voice" not in chunk.lower():
            continue
        for raw_line in re.split(r"[\r\n]+", chunk):
            directive = _clean_voice_directive(raw_line)
            lowered = directive.lower()
            if not directive or len(directive) < 10:
                continue
            if lowered in seen:
                continue
            if "voice patterns" in lowered or "reusable language patterns" in lowered:
                continue
            if any(hint in lowered for hint in VOICE_DIRECTIVE_HINTS):
                seen.add(lowered)
                directives.append(directive)
            if len(directives) >= limit:
                return directives
    for directive in DEFAULT_VOICE_DIRECTIVES:
        lowered = directive.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        directives.append(directive)
        if len(directives) >= limit:
            break
    return directives


def _public_post_lane_for_option(option_number: int) -> str:
    if option_number <= 0:
        return PUBLIC_POST_LANES[0]
    return PUBLIC_POST_LANES[(option_number - 1) % len(PUBLIC_POST_LANES)]


def _public_post_lane(brief: ContentOptionBrief | None) -> str:
    if brief and str(brief.public_lane or "").strip():
        return str(brief.public_lane).strip()
    if brief:
        return _public_post_lane_for_option(int(brief.option_number or 1))
    return PUBLIC_POST_LANES[0]


def _semantic_planning_fragments(*values: str) -> List[str]:
    """Return bounded, ordered fragments without adding facts to planner input."""

    fragments: List[str] = []
    seen: set[str] = set()
    for value in values:
        for raw_line in re.split(r"[\r\n]+", str(value or "")):
            line = " ".join(raw_line.strip().lstrip("-* ").split()).strip()
            if not line:
                continue
            if ":" in line:
                label, candidate = line.split(":", 1)
                if len(label.split()) <= 5 and candidate.strip():
                    line = candidate.strip()
            for raw_fragment in re.split(r"(?<=[.!?])\s+|\s*[;|]\s*", line):
                fragment = " ".join(raw_fragment.split()).strip(" -")
                if not fragment:
                    continue
                if len(fragment) > 320:
                    fragment = fragment[:320].rsplit(" ", 1)[0].rstrip(" ,;:")
                key = fragment.lower().rstrip(".!?")
                if not key or key in seen:
                    continue
                seen.add(key)
                fragments.append(fragment)
    return fragments


def _labeled_semantic_context_value(request_context: str, *labels: str) -> str:
    wanted = {" ".join(label.lower().replace("_", " ").split()) for label in labels}
    for raw_line in re.split(r"[\r\n]+", str(request_context or "")):
        if ":" not in raw_line:
            continue
        label, value = raw_line.split(":", 1)
        normalized_label = " ".join(label.strip().lower().replace("_", " ").split())
        cleaned_value = " ".join(value.split()).strip()
        if normalized_label in wanted and cleaned_value:
            return cleaned_value[:320].rstrip(" ,;:")
    return ""


def _semantic_planning_concept_items(*values: str, limit: int = 6) -> List[str]:
    blocked_terms = set(STOPWORDS).union(
        {
            "anonymized",
            "approved",
            "audience",
            "card",
            "claim",
            "consequence",
            "context",
            "distinct",
            "evidence",
            "expected",
            "outcome",
            "platform",
            "public",
            "safe",
            "selected",
            "source",
            "test",
            "thesis",
            "topic",
            "tradeoff",
            "writing",
        }
    )
    concepts: List[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]+", str(value or "")):
            normalized = token.lower().strip("'-")
            if len(normalized) < 4 or normalized in blocked_terms or normalized in seen:
                continue
            seen.add(normalized)
            concepts.append(normalized)
            if len(concepts) >= limit:
                return concepts
    return concepts


def _semantic_planning_concepts(*values: str, limit: int = 6) -> str:
    return ", ".join(_semantic_planning_concept_items(*values, limit=limit))


def _semantic_decision_object(*values: str) -> str:
    """Choose one bounded decision object already named by approved inputs."""

    source = " ".join(str(value or "") for value in values).lower()
    candidates = (
        ("ai output", "AI output"),
        ("handoff", "handoff"),
        ("draft", "draft"),
        ("output", "output"),
        ("answer", "answer"),
        ("recommendation", "recommendation"),
        ("decision", "decision"),
        ("result", "result"),
        ("workflow", "workflow"),
        ("system", "system"),
        ("agent", "agent output"),
        ("content", "content"),
        ("plan", "plan"),
        ("brief", "brief"),
        ("post", "post"),
        ("evidence", "evidence packet"),
        ("source", "source"),
        ("signal", "signal"),
    )
    positioned = [
        (match.start(), label)
        for needle, label in candidates
        if (match := re.search(rf"\b{re.escape(needle)}s?\b", source))
    ]
    if positioned:
        return min(positioned, key=lambda item: item[0])[1]
    fallback = _semantic_planning_concept_items(*values, limit=1)
    return fallback[0] if fallback else "result"


def _semantic_context_phrase(
    concepts: str,
    *,
    decision_object: str,
    fallback_values: tuple[str, ...],
) -> tuple[str, int]:
    object_terms = set(re.findall(r"[a-z0-9]+", decision_object.lower()))
    items = [
        item.strip()
        for item in str(concepts or "").split(",")
        if item.strip() and item.strip().lower() not in object_terms
    ]
    for item in _semantic_planning_concept_items(*fallback_values, limit=6):
        if item.lower() in object_terms or item in items:
            continue
        items.append(item)
        if len(items) >= 3:
            break
    items = items[:3]
    if not items:
        return "approved context", 1
    if len(items) == 1:
        return items[0], 1
    if len(items) == 2:
        return f"{items[0]} and {items[1]}", 2
    return f"{items[0]}, {items[1]}, and {items[2]}", 3


def _semantic_application_gate(
    *,
    claim: str,
    request_context: str,
    proof_evidence: str,
    required_context: str,
) -> tuple[str, str]:
    """Render atomic, topic-bound gate fields without prewriting public copy."""

    decision_object = _semantic_decision_object(claim, request_context, proof_evidence)
    context_phrase, concept_count = _semantic_context_phrase(
        required_context,
        decision_object=decision_object,
        fallback_values=(request_context, proof_evidence, claim),
    )
    agreement = "is" if concept_count == 1 else "are"
    decision_rule = (
        f"Decision action: accept | decision object: {decision_object} | "
        f"boundary: {context_phrase} {agreement} visible before reliance | "
        "rule posture: derived principle."
    )
    consequence = (
        f"Consequence boundary: reviewability before reliance on {decision_object} | "
        f"visible basis: {context_phrase}."
    )
    return decision_rule, consequence


def _select_semantic_planning_basis(
    fragments: List[str],
    *,
    preferred_terms: frozenset[str] | set[str],
    fallback: str,
    exclude: str = "",
) -> str:
    excluded = " ".join(str(exclude or "").lower().split()).rstrip(".!?")
    candidates = [
        fragment
        for fragment in fragments
        if " ".join(fragment.lower().split()).rstrip(".!?") != excluded
    ] or fragments
    if not candidates:
        return " ".join(str(fallback or "").split()).strip()[:320]

    def rank(item: tuple[int, str]) -> tuple[int, int, int, int]:
        index, fragment = item
        terms = set(re.findall(r"[a-z0-9]+", fragment.lower()))
        role_score = len(terms.intersection(preferred_terms))
        relation_score = int(
            bool(
                re.search(
                    r"\b(?:before|because|if|instead|so that|unless|when|while|without)\b",
                    fragment,
                    flags=re.IGNORECASE,
                )
            )
        )
        specificity = min(24, len([term for term in terms if len(term) > 3 and term not in STOPWORDS]))
        return role_score, relation_score, specificity, -index

    return max(enumerate(candidates), key=rank)[1]


def _proof_semantic_facet_id(proof_packet: str) -> str:
    evidence = " ".join(_proof_packet_evidence_text(proof_packet).lower().split()).strip(" .")
    if not evidence or re.match(r"^no\s+(?:approved\s+|strong\s+)?proof(?:\s+packet)?\b", evidence):
        return ""
    return f"proof-facet-{hashlib.sha256(evidence.encode('utf-8')).hexdigest()[:16]}"


def _partition_semantic_request_context(request_context: str) -> tuple[str, str, str]:
    """Keep base, audience-consequence, and why-now planner inputs separate."""

    base_lines: List[str] = []
    audience_consequence = ""
    why_now = ""
    for raw_line in re.split(r"[\r\n]+", str(request_context or "")):
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        label = ""
        value = ""
        if ":" in line:
            raw_label, raw_value = line.split(":", 1)
            label = " ".join(raw_label.strip().lower().replace("_", " ").split())
            value = " ".join(raw_value.split()).strip()
        if label == "audience consequence" and value:
            if not audience_consequence:
                audience_consequence = value[:320].rstrip(" ,;:")
            continue
        if label == "why now" and value:
            if not why_now:
                why_now = value[:320].rstrip(" ,;:")
            continue
        base_lines.append(line)
    return "\n".join(base_lines), audience_consequence, why_now


def _semantic_anchor_candidates(text: str, *, exclude_terms: set[str] | frozenset[str] = frozenset()) -> List[str]:
    """Return ordered, unique, lowercase substantive tokens from one proposition."""

    blocked = set(STOPWORDS).union(SEMANTIC_ANCHOR_META_TERMS)
    excluded = {str(term).strip().lower() for term in exclude_terms if str(term).strip()}
    anchors: List[str] = []
    seen: set[str] = set()
    for raw_token in re.findall(r"[A-Za-z][A-Za-z0-9]*", str(text or "")):
        token = raw_token.lower()
        if (len(token) < 3 and token != "ai") or token in blocked or token in excluded or token in seen:
            continue
        seen.add(token)
        anchors.append(token)
    return anchors


def _semantic_application_owned_terms(*values: str) -> set[str]:
    owned: set[str] = set()
    for value in values:
        owned.update(_semantic_anchor_candidates(value))
    return owned


def _semantic_basis_with_anchor_terms(
    proposition: str,
    *,
    alternatives: List[str],
    exclude_terms: set[str],
    field_name: str,
) -> tuple[str, List[str]]:
    """Bind exactly two anchors to an approved full proposition or fail closed."""

    candidates: List[str] = []
    seen: set[str] = set()
    for value in (proposition, *alternatives):
        normalized = " ".join(str(value or "").split()).strip()
        key = normalized.lower().rstrip(".!?")
        if not normalized or key in seen:
            continue
        seen.add(key)
        candidates.append(normalized[:320].rstrip(" ,;:"))
    for candidate in candidates:
        anchor_terms = _semantic_anchor_candidates(candidate, exclude_terms=exclude_terms)
        if len(anchor_terms) >= 2:
            return candidate, anchor_terms[:2]
    combined = " ".join(candidates).strip()[:320].rstrip(" ,;:")
    combined_anchor_terms = _semantic_anchor_candidates(combined, exclude_terms=exclude_terms)
    if len(combined_anchor_terms) >= 2:
        return combined, combined_anchor_terms[:2]
    raise ValueError(f"{field_name} requires two approved, non-application semantic anchor terms")


def _empty_role_semantic_payload(proof_packet: str) -> Dict[str, Any]:
    return {
        "mechanism_focus": "",
        "recognition_basis": "",
        "mechanism_anchor_terms": [],
        "recognition_anchor_terms": [],
        "decision_rule_basis": "",
        "decision_moment_basis": "",
        "decision_moment_anchor_terms": [],
        "required_context_concepts": "",
        "consequence_basis": "",
        "application_closing_anchor_terms": [],
        "proof_facet_id": _proof_semantic_facet_id(proof_packet),
        "semantic_payload_version": FEEZIE_ROLE_PAYLOAD_VERSION,
    }


def _build_canonical_pair_semantic_payloads(
    *,
    diagnosis_claim: str,
    diagnosis_proof_packet: str,
    application_claim: str,
    application_proof_packet: str,
    request_context: str,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Jointly bind the first diagnosis/application pair to exclusive semantic jobs."""

    base_context, audience_consequence, why_now = _partition_semantic_request_context(request_context)
    diagnosis_proof = (
        _proof_packet_evidence_text(diagnosis_proof_packet)
        if _proof_semantic_facet_id(diagnosis_proof_packet)
        else ""
    )
    application_proof = (
        _proof_packet_evidence_text(application_proof_packet)
        if _proof_semantic_facet_id(application_proof_packet)
        else ""
    )

    application_payload = _empty_role_semantic_payload(application_proof_packet)
    application_context = "\n".join(
        value for value in (base_context, audience_consequence) if str(value or "").strip()
    )
    required_context = _semantic_planning_concepts(
        audience_consequence,
        base_context,
        application_claim,
        application_proof,
    )
    decision_basis, bounded_consequence = _semantic_application_gate(
        claim=application_claim,
        request_context=application_context,
        proof_evidence=application_proof,
        required_context=required_context,
    )
    consequence = audience_consequence or bounded_consequence
    application_payload.update(
        {
            "decision_rule_basis": decision_basis,
            "required_context_concepts": required_context,
            "consequence_basis": consequence,
        }
    )
    application_owned_terms = _semantic_application_owned_terms(
        decision_basis,
        required_context,
        consequence,
    )
    shared_claim_terms = set(_semantic_anchor_candidates(diagnosis_claim))
    application_owned_terms.difference_update(shared_claim_terms)
    normalized_diagnosis_proof = " ".join(diagnosis_proof.lower().split()).rstrip(".!?")
    normalized_application_proof = " ".join(application_proof.lower().split()).rstrip(".!?")
    if normalized_application_proof and normalized_application_proof != normalized_diagnosis_proof:
        application_owned_terms.update(_semantic_anchor_candidates(application_proof))

    mechanism_fragments = _semantic_planning_fragments(
        diagnosis_proof,
        base_context,
        diagnosis_claim,
    )
    mechanism = _select_semantic_planning_basis(
        mechanism_fragments,
        preferred_terms=DIAGNOSIS_PROOF_ROLE_TERMS.union(
            {"drift", "loss", "lost", "uncertainty", "weak", "weaker"}
        ),
        fallback=diagnosis_claim,
    )
    recognition_fragments = _semantic_planning_fragments(
        why_now,
        base_context,
        diagnosis_proof,
        diagnosis_claim,
    )
    recognition = why_now or _select_semantic_planning_basis(
        recognition_fragments,
        preferred_terms=DIAGNOSIS_PROOF_ROLE_TERMS.union(
            {"drift", "rework", "signal", "trust", "visible"}
        ),
        fallback=diagnosis_claim,
        exclude=mechanism,
    )
    if " ".join(recognition.lower().split()).rstrip(".!?") == " ".join(mechanism.lower().split()).rstrip(".!?"):
        recognition = diagnosis_claim

    mechanism, mechanism_anchor_terms = _semantic_basis_with_anchor_terms(
        mechanism,
        alternatives=mechanism_fragments,
        exclude_terms=application_owned_terms,
        field_name="mechanism_focus",
    )
    normalized_mechanism = " ".join(mechanism.lower().split()).rstrip(".!?")
    if " ".join(recognition.lower().split()).rstrip(".!?") == normalized_mechanism:
        recognition = diagnosis_claim
    recognition_alternatives = [
        fragment
        for fragment in recognition_fragments
        if " ".join(fragment.lower().split()).rstrip(".!?") != normalized_mechanism
    ]
    recognition_alternatives.append(mechanism)
    recognition, recognition_anchor_terms = _semantic_basis_with_anchor_terms(
        recognition,
        alternatives=recognition_alternatives,
        exclude_terms=application_owned_terms,
        field_name="recognition_basis",
    )
    diagnosis_payload = _empty_role_semantic_payload(diagnosis_proof_packet)
    diagnosis_payload.update(
        {
            "mechanism_focus": mechanism,
            "recognition_basis": recognition,
            "mechanism_anchor_terms": mechanism_anchor_terms,
            "recognition_anchor_terms": recognition_anchor_terms,
        }
    )
    return diagnosis_payload, application_payload


def _build_option_framing_plan(
    *,
    framing_modes: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    request_context: str = "",
    option_count: int = 1,
) -> List[Dict[str, Any]]:
    approved_framing_modes = framing_modes or ["operator_lesson", "contrarian_reframe", "reframe"]
    approved_claims = primary_claims or ["Stay tightly inside the topic anchors."]
    approved_proofs = proof_packets or ["No proof packet approved. Use principle and operator language only."]
    approved_stories = story_beats or []
    normalized_claims = {
        " ".join((claim or "").lower().split()).strip()
        for claim in approved_claims
        if " ".join((claim or "").split()).strip()
    }
    proof_available = any(
        " ".join((packet or "").split()).strip()
        and not re.match(
            r"^no\s+(?:approved\s+|strong\s+)?proof(?:\s+packet)?\b",
            " ".join((packet or "").lower().split()).strip(),
        )
        for packet in proof_packets
    )
    principle_only_shared_claim = (
        option_count >= 2
        and len(normalized_claims) == 1
        and not proof_available
    )

    labeled_proof_indices = {
        proof_index
        for proof_index, packet in enumerate(approved_proofs)
        if _proof_packet_label(packet) and not _phrase_is_flat_label(_proof_packet_label(packet))
    }
    preselected_role_proof_indices: Dict[int, int] = {}
    if option_count >= 2 and len(approved_proofs) > 1:
        proof_terms = [
            set(re.findall(r"[a-z0-9]+", _proof_packet_evidence_text(packet).lower()))
            for packet in approved_proofs
        ]

        def pair_rank(pair: tuple[int, int]) -> tuple[int, int, int, int, int, int, int]:
            diagnosis_index, application_index = pair
            diagnosis_score = len(proof_terms[diagnosis_index].intersection(DIAGNOSIS_PROOF_ROLE_TERMS))
            application_score = len(proof_terms[application_index].intersection(APPLICATION_PROOF_ROLE_TERMS))
            union = proof_terms[diagnosis_index].union(proof_terms[application_index])
            overlap = (
                len(proof_terms[diagnosis_index].intersection(proof_terms[application_index])) / len(union)
                if union
                else 1.0
            )
            diversity_score = int(round((1.0 - overlap) * 1000))
            role_coverage = int(diagnosis_score > 0) + int(application_score > 0)
            lane_score = int(diagnosis_index not in labeled_proof_indices) + int(
                application_index in labeled_proof_indices
            )
            return (
                role_coverage,
                min(diagnosis_score, application_score),
                diagnosis_score + application_score,
                diversity_score,
                lane_score,
                -diagnosis_index,
                -application_index,
            )

        candidate_pairs = [
            (diagnosis_index, application_index)
            for diagnosis_index in range(len(approved_proofs))
            for application_index in range(len(approved_proofs))
            if diagnosis_index != application_index
        ]
        if candidate_pairs:
            diagnosis_index, application_index = max(candidate_pairs, key=pair_rank)
            preselected_role_proof_indices = {0: diagnosis_index, 1: application_index}

    used_proof_indices: set[int] = set(preselected_role_proof_indices.values())

    def pick_proof(index: int, lane: str, distinctness_job: Dict[str, str]) -> str:
        if index in preselected_role_proof_indices:
            return approved_proofs[preselected_role_proof_indices[index]]
        default_index = index % len(approved_proofs)
        default_proof = approved_proofs[default_index]
        labeled_proofs = [
            packet
            for packet in approved_proofs
            if _proof_packet_label(packet) and not _phrase_is_flat_label(_proof_packet_label(packet))
        ]
        unlabeled_proofs = [
            packet for packet in approved_proofs if packet not in labeled_proofs
        ]
        treatment = str(distinctness_job.get("thesis_treatment") or "").lower()
        role_terms: frozenset[str] = frozenset()
        if "application" in treatment:
            role_terms = APPLICATION_PROOF_ROLE_TERMS
        elif "diagnos" in treatment:
            role_terms = DIAGNOSIS_PROOF_ROLE_TERMS
        if role_terms and len(approved_proofs) > 1:
            available_indices = [
                proof_index
                for proof_index in range(len(approved_proofs))
                if proof_index not in used_proof_indices
            ] or list(range(len(approved_proofs)))

            def role_rank(proof_index: int) -> tuple[int, int, int]:
                packet = approved_proofs[proof_index]
                terms = set(re.findall(r"[a-z0-9]+", _proof_packet_evidence_text(packet).lower()))
                role_score = len(terms.intersection(role_terms))
                lane_score = int(
                    (lane == "market_insight" and packet in unlabeled_proofs)
                    or (lane in {"operator_lesson", "build_in_public"} and packet in labeled_proofs)
                )
                return role_score, lane_score, -proof_index

            selected_index = max(available_indices, key=role_rank)
            used_proof_indices.add(selected_index)
            return approved_proofs[selected_index]
        if lane == "market_insight" and unlabeled_proofs:
            selected = unlabeled_proofs[index % len(unlabeled_proofs)]
        elif lane in {"operator_lesson", "build_in_public"} and labeled_proofs:
            selected = labeled_proofs[index % len(labeled_proofs)]
        else:
            selected = default_proof
        try:
            used_proof_indices.add(approved_proofs.index(selected))
        except ValueError:
            used_proof_indices.add(default_index)
        return selected

    plan: List[Dict[str, Any]] = []
    for index in range(option_count):
        mode = approved_framing_modes[index % len(approved_framing_modes)]
        claim = approved_claims[index % len(approved_claims)]
        lane = _public_post_lane_for_option(index + 1)
        if principle_only_shared_claim and index < len(PRINCIPLE_ONLY_SHARED_CLAIM_DISTINCTNESS_JOBS):
            distinctness_job = PRINCIPLE_ONLY_SHARED_CLAIM_DISTINCTNESS_JOBS[index]
        else:
            distinctness_job = OPTION_DISTINCTNESS_JOBS[index % len(OPTION_DISTINCTNESS_JOBS)]
        proof = pick_proof(index, lane, distinctness_job)
        story = approved_stories[index % len(approved_stories)] if approved_stories else ""
        plan.append(
            {
                "option": str(index + 1),
                "mode": mode,
                "lane": lane,
                "claim": claim,
                "proof": proof,
                "story": story,
                "thesis_treatment": distinctness_job["thesis_treatment"],
                "proof_progression": distinctness_job["proof_progression"],
                "payoff": distinctness_job["payoff"],
                **_empty_role_semantic_payload(proof),
            }
        )
    if len(plan) >= 2:
        diagnosis_payload, application_payload = _build_canonical_pair_semantic_payloads(
            diagnosis_claim=str(plan[0]["claim"]),
            diagnosis_proof_packet=str(plan[0]["proof"]),
            application_claim=str(plan[1]["claim"]),
            application_proof_packet=str(plan[1]["proof"]),
            request_context=request_context,
        )
        plan[0].update(diagnosis_payload)
        plan[1].update(application_payload)
    return plan


def _render_option_framing_plan(option_plan: List[Dict[str, Any]]) -> str:
    if not option_plan:
        return "- No explicit option framing plan."
    rendered: List[str] = []
    for item in option_plan:
        parts = [
            f"Option {item.get('option')}: `{item.get('mode')}`",
            f"public lane: `{item.get('lane')}` ({PUBLIC_POST_LANE_GUIDANCE.get(str(item.get('lane') or ''), 'Keep the option in one clear public-facing posture.')})",
            f"lead claim: {item.get('claim')}",
            f"supporting proof: {item.get('proof')}",
        ]
        story = str(item.get("story") or "")
        if story:
            parts.append(f"optional story beat: {story}")
        parts.extend(
            [
                f"thesis treatment: {item.get('thesis_treatment')}",
                f"proof progression: {item.get('proof_progression')}",
                f"payoff: {item.get('payoff')}",
            ]
        )
        for key, label in (
            ("mechanism_anchor_terms", "mechanism anchor terms"),
            ("recognition_anchor_terms", "recognition anchor terms"),
        ):
            values = [str(value).strip() for value in item.get(key) or [] if str(value).strip()]
            if values:
                parts.append(f"{label}: {', '.join(values)}")
        for key, label in (
            ("mechanism_focus", "mechanism focus"),
            ("recognition_basis", "recognition basis"),
            ("decision_rule_basis", "decision-rule basis"),
            ("required_context_concepts", "required context concepts"),
            ("consequence_basis", "consequence basis"),
            ("proof_facet_id", "proof facet id"),
        ):
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(f"{label}: {value}")
        rendered.append("- " + " | ".join(parts))
    return "\n".join(rendered)


def _first_content_line(option: str) -> str:
    for line in (option or "").splitlines():
        cleaned = " ".join(line.split()).strip()
        if cleaned:
            return cleaned
    return " ".join((option or "").split()).strip()


def _starts_with_third_person_persona_bio(text: str) -> bool:
    first_line = _first_content_line(text)
    if not first_line:
        return False
    subject = r"(?:owner|[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,2})"
    return bool(
        re.match(
            rf"^{subject}\s+(?:treats|keeps|built|started|learned)\b",
            first_line,
            flags=re.IGNORECASE,
        )
        or re.match(
            rf"^{subject}\s+(?:is|was)\s+(?:(?:an?|the)\s+)?(?:"
            r"ai\s+practitioner|technology\s+builder|tech\s+builder|education\s+operations\s+leader|"
            r"operator|builder|founder|leader|professional|entrepreneur|technologist|engineer|product\s+manager"
            r")\b",
            first_line,
            flags=re.IGNORECASE,
        )
        or re.match(
            rf"^{subject}\s+(?:is|was)\s+building\s+at\s+the\s+intersection\b",
            first_line,
            flags=re.IGNORECASE,
        )
    )


def _significant_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 3 and token not in STOPWORDS
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


def _internal_public_jargon_hits(text: str) -> list[str]:
    normalized = " ".join((text or "").split())
    if not normalized:
        return []
    hits = [pattern.pattern for pattern in INTERNAL_PUBLIC_JARGON_PATTERNS if pattern.search(normalized)]
    lowered = normalized.lower()
    if sum(1 for marker in OPERATOR_CATALOG_MARKERS if marker in lowered) >= 3:
        hits.append("operator_catalog_markers")
    for sentence in _split_sentences(normalized):
        if _looks_like_operator_catalog_sentence(sentence):
            hits.append("operator_catalog_sentence")
            break
    return hits


def _proof_overload_score(text: str) -> int:
    sentences = [sentence.strip() for sentence in _split_sentences(text or "") if sentence.strip()]
    if not sentences:
        return 0
    overload = 0
    for sentence in sentences:
        word_count = len(sentence.split())
        comma_count = sentence.count(",")
        semicolon_count = sentence.count(";")
        metric_count = len(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", sentence))
        if metric_count >= 3:
            overload += 1
        if word_count >= 34 and (comma_count >= 3 or semicolon_count >= 1):
            overload += 1
    return overload


def _lane_signal_counts(text: str) -> dict[str, int]:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return {lane: 0 for lane in PUBLIC_POST_LANES}
    lane_terms = {
        "market_insight": {"market", "competition", "advantage", "leaders", "entrants", "positioning", "adoption", "margin", "category"},
        "operator_lesson": {"workflow", "handoff", "operator", "decision", "loop", "clarity", "execution", "system", "context"},
        "build_in_public": {"we", "built", "fixed", "learned", "finally", "rewired", "stopped", "shipped", "changed", "rebuilt"},
    }
    counts: dict[str, int] = {}
    for lane, terms in lane_terms.items():
        counts[lane] = sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", normalized))
    return counts


def _publishability_score(option: str, brief: ContentOptionBrief | None, *, topic: str = "", audience: str = "") -> int:
    score = 0
    if _internal_public_jargon_hits(option):
        score -= 16
    else:
        score += 8
    if _starts_with_third_person_persona_bio(option):
        score -= 10
    else:
        score += 2
    proof_overload = _proof_overload_score(option)
    if proof_overload:
        score -= min(12, proof_overload * 6)
    else:
        score += 6
    lane = _public_post_lane(brief)
    lane_counts = _lane_signal_counts(option)
    lane_focus = lane_counts.get(lane, 0)
    other_focus = max((count for key, count in lane_counts.items() if key != lane), default=0)
    if lane_focus >= 2 and other_focus <= lane_focus:
        score += 5
    elif lane_focus == 0 and other_focus >= 2:
        score -= 6
    elif lane_focus >= 1 and other_focus >= 2:
        score -= 3
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    if 2 <= len(paragraphs) <= 4:
        score += 3
    elif len(paragraphs) <= 1:
        score -= 4
    opening_word_count = len((_first_content_line(option) or "").split())
    if 4 <= opening_word_count <= 14:
        score += 2
    elif opening_word_count >= 24:
        score -= 4
    if audience == "tech_ai" and any(term in " ".join((topic or "").lower().split()) for term in ("workflow", "agent", "ai", "orchestration")):
        if re.search(r"\bworkflow\b|\bhandoff\b|\boperator\b|\bclarity\b", (option or "").lower()):
            score += 2
    return score


def _proof_packet_is_available(packet: str) -> bool:
    normalized = " ".join((packet or "").lower().split()).strip()
    if not normalized:
        return False
    return not bool(
        re.match(
            r"^no\s+(?:approved\s+|strong\s+)?proof(?:\s+packet)?\b",
            normalized,
        )
    )


def score_option_taste(
    option: str,
    *,
    brief: ContentOptionBrief | None = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    grounding_mode: str | None = None,
) -> Dict[str, Any]:
    cleaned = (option or "").strip()
    primary_claims = primary_claims or []
    proof_packets = proof_packets or []
    story_beats = story_beats or []
    active_brief = brief or ContentOptionBrief(
        option_number=1,
        framing_mode="operator_lesson",
        primary_claim=primary_claims[0] if primary_claims else "",
        proof_packet=proof_packets[0] if proof_packets else "",
        story_beat=story_beats[0] if story_beats else "",
    )
    resolved_grounding_mode = " ".join((grounding_mode or "").lower().split()).strip()
    if not resolved_grounding_mode:
        resolved_grounding_mode = (
            "proof_ready"
            if _proof_packet_is_available(active_brief.proof_packet)
            else "principle_only"
        )
    proof_required = resolved_grounding_mode == "proof_ready"
    warnings: List[str] = []
    strengths: List[str] = []
    score = 60

    genericity = _genericity_score(cleaned)
    if genericity:
        score -= genericity * 6
        warnings.append(f"genericity:{genericity}")
    else:
        strengths.append("low_genericity")

    first_line = _first_content_line(cleaned)
    if (
        _assigned_application_rule_near_opening(cleaned, active_brief)
        or _assigned_diagnosis_claim_near_opening(cleaned, active_brief)
        or _claim_near_opening(cleaned, active_brief.primary_claim)
    ):
        score += 10
        strengths.append("claim_led_opening")
    else:
        score -= 10
        warnings.append("claim_not_leading")
    if _starts_with_third_person_persona_bio(cleaned):
        score -= 10
        warnings.append("persona_bio_opening")
    else:
        strengths.append("no_persona_bio_opening")

    if proof_required:
        if option_mentions_approved_proof(cleaned, [active_brief.proof_packet] if active_brief.proof_packet else proof_packets):
            score += 10
            strengths.append("proof_grounded")
        else:
            score -= 8
            warnings.append("proof_not_visible")
        if _brief_prefers_operator_voice(active_brief) and _brief_requires_named_reference_specificity(active_brief):
            if _option_has_named_reference_specificity(cleaned, active_brief):
                score += 4
                strengths.append("named_reference_specificity")
            else:
                score -= 8
                warnings.append("named_reference_missing")
        elif _brief_prefers_operator_voice(active_brief):
            strengths.append("anonymized_reference_boundary_respected")
    else:
        strengths.append("principle_only_evidence_boundary")

    internal_hits = _internal_public_jargon_hits(cleaned)
    if internal_hits:
        score -= min(18, len(internal_hits) * 6)
        warnings.append("internal_public_leak")
    else:
        strengths.append("public_safe_language")

    proof_overload = _proof_overload_score(cleaned)
    if proof_overload:
        score -= min(12, proof_overload * 6)
        warnings.append("proof_overloaded")
    else:
        strengths.append("proof_density_controlled")

    negative_hits = [pattern.pattern for pattern in TASTE_NEGATIVE_PATTERNS if pattern.search(cleaned)]
    if negative_hits:
        score -= len(negative_hits) * 6
        warnings.extend("taste_negative" for _ in negative_hits)
    else:
        strengths.append("no_corporate_taste_hits")

    positive_hits = [pattern.pattern for pattern in TASTE_POSITIVE_PATTERNS if pattern.search(cleaned)]
    if positive_hits:
        score += min(8, len(positive_hits) * 3)
        strengths.append("owner_phrase_energy")

    contrast_hits = [pattern.pattern for pattern in TASTE_CONTRAST_PATTERNS if pattern.search(cleaned)]
    if contrast_hits:
        score += min(6, len(contrast_hits) * 2)
        strengths.append("contrast_present")
    else:
        warnings.append("low_contrast")

    sentences = _split_sentences(cleaned)
    if sentences:
        lengths = [len(sentence.split()) for sentence in sentences if sentence.split()]
        if lengths:
            if any(length <= 6 for length in lengths):
                score += 3
                strengths.append("short_punchy_sentence")
            else:
                warnings.append("no_short_sentence")
            average_length = sum(lengths) / len(lengths)
            if average_length > 18:
                score -= 4
                warnings.append("too_smoothed")
            elif average_length < 15:
                score += 2
                strengths.append("spoken_sentence_length")
    if cleaned.count("\n\n") >= 1:
        score += 2
        strengths.append("human_paragraph_cadence")
    else:
        warnings.append("paragraph_cadence_flat")

    last_sentence = ""
    for sentence in reversed(_split_sentences(cleaned)):
        normalized_sentence = " ".join(sentence.split()).strip()
        if normalized_sentence:
            last_sentence = normalized_sentence
            break
    if last_sentence and _closer_needs_sharpening(last_sentence, active_brief):
        score -= 6
        warnings.append("weak_closer")
    elif last_sentence:
        score += 4
        strengths.append("sharp_closer")

    if first_line.lower().startswith(("we ", "we’ve ", "we've ", "this ", "it ", "our ")):
        score -= 4
        warnings.append("soft_opening_subject")
    if _brief_prefers_operator_voice(active_brief):
        if re.search(r"(?mi)^(?:now,\s*)?we\b", cleaned):
            score -= 4
            warnings.append("soft_operator_pronoun")

    overall = max(0, min(100, score))
    return {
        "overall": overall,
        "warnings": warnings,
        "strengths": strengths,
        "first_line": first_line,
        "grounding_mode": resolved_grounding_mode,
    }


def _option_needs_voice_sharpening(option: str) -> bool:
    lowered = " ".join((option or "").lower().split())
    if not lowered:
        return False
    if any(pattern.search(lowered) for pattern in FLAT_GENERIC_PATTERNS):
        return True
    if _genericity_score(option) >= 2:
        return True
    first_line = _first_content_line(option)
    first_line_lower = first_line.lower()
    if first_line_lower.startswith(("workflow clarity is", "agent orchestration is", "leadership is", "clarity is", "ai is")):
        return True
    if first_line_lower.startswith(("this is", "that is", "it is")) and len(first_line.split()) <= 10:
        return True
    return False


def _options_need_voice_sharpening(options: List[str]) -> bool:
    meaningful_options = [option for option in options if option.strip()]
    if not meaningful_options:
        return False
    if any(_option_needs_voice_sharpening(option) for option in meaningful_options):
        return True
    first_words = []
    for option in meaningful_options:
        first_line = _first_content_line(option)
        if not first_line:
            continue
        first_words.append(re.findall(r"[A-Za-z']+", first_line)[0].lower())
    return len(first_words) >= 2 and len(set(first_words)) == 1


def _runtime_is_production() -> bool:
    explicit = (os.getenv("CONTENT_GENERATION_RUNTIME") or "").strip().lower()
    if explicit in {"production", "prod"}:
        return True
    if explicit in {"development", "dev", "local"}:
        return False
    return bool(
        os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_ENVIRONMENT_ID")
        or os.getenv("K_SERVICE")
        or (os.getenv("NODE_ENV") or "").strip().lower() == "production"
    )


def _content_generation_stability_mode() -> str:
    return " ".join((os.getenv("CONTENT_GENERATION_STABILITY_MODE") or "").lower().split())


def _writer_temperature(audience: str) -> float:
    if _content_generation_stability_mode() == "benchmark":
        return 0.2 if audience == "tech_ai" else 0.28
    return 0.55 if audience == "tech_ai" else 0.72


def _critic_temperature() -> float:
    if _content_generation_stability_mode() == "benchmark":
        return 0.15
    return 0.25


def _refinement_temperature() -> float:
    if _content_generation_stability_mode() == "benchmark":
        return 0.12
    return 0.35


def _final_editor_temperature() -> float:
    if _content_generation_stability_mode() == "benchmark":
        return 0.12
    return 0.35


def _proof_enforcement_temperature() -> float:
    if _content_generation_stability_mode() == "benchmark":
        return 0.1
    return 0.2


def _legacy_generation_temperature(audience: str) -> float:
    if _content_generation_stability_mode() == "benchmark":
        return 0.25 if audience == "tech_ai" else 0.35
    return 0.68 if audience == "tech_ai" else 0.85


def _env_flag_enabled(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _require_direct_content_generation_enabled(override_token: str | None) -> None:
    if not _runtime_is_production():
        return
    if _env_flag_enabled("CONTENT_GENERATION_DIRECT_ROUTES_ENABLED"):
        return
    expected_override = (os.getenv("CONTENT_GENERATION_DIRECT_OVERRIDE_TOKEN") or "").strip()
    provided_override = (override_token or "").strip()
    if expected_override and provided_override:
        if secrets.compare_digest(provided_override, expected_override):
            return
        raise HTTPException(status_code=401, detail="Invalid direct content generation override token")
    raise HTTPException(
        status_code=403,
        detail="Direct content generation is disabled in production. Queue /api/content-generation/codex-jobs instead.",
    )


def _expected_local_codex_token() -> str:
    return (os.getenv("LOCAL_CODEX_BRIDGE_TOKEN") or os.getenv("CRON_ACCESS_TOKEN") or "").strip()


def _require_local_codex_token(x_local_codex_token: str | None) -> None:
    expected = _expected_local_codex_token()
    if expected:
        supplied = (x_local_codex_token or "").strip()
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="Invalid local Codex bridge token")
        return
    if _runtime_is_production():
        raise HTTPException(status_code=503, detail="Local Codex bridge token is not configured")


def _serialize_content_option_briefs(briefs: List[ContentOptionBrief]) -> List[Dict[str, Any]]:
    return [
        {
            "option_number": brief.option_number,
            "framing_mode": brief.framing_mode,
            "primary_claim": brief.primary_claim,
            "proof_packet": brief.proof_packet,
            "story_beat": brief.story_beat,
            "public_lane": brief.public_lane or _public_post_lane_for_option(brief.option_number),
            "thesis_treatment": brief.thesis_treatment,
            "proof_progression": brief.proof_progression,
            "payoff": brief.payoff,
            "mechanism_focus": brief.mechanism_focus,
            "recognition_basis": brief.recognition_basis,
            "mechanism_anchor_terms": list(brief.mechanism_anchor_terms),
            "recognition_anchor_terms": list(brief.recognition_anchor_terms),
            "decision_rule_basis": brief.decision_rule_basis,
            "decision_moment_basis": brief.decision_moment_basis,
            "decision_moment_anchor_terms": list(brief.decision_moment_anchor_terms),
            "required_context_concepts": brief.required_context_concepts,
            "consequence_basis": brief.consequence_basis,
            "application_closing_anchor_terms": list(brief.application_closing_anchor_terms),
            "proof_facet_id": brief.proof_facet_id,
            "semantic_payload_version": brief.semantic_payload_version,
        }
        for brief in briefs
    ]


def _deserialize_bound_anchor_terms(value: Any) -> List[str]:
    """Preserve an already-bound literal anchor list across the job boundary.

    V3 role anchors are selected from a specific approved proposition before
    serialization. Re-running the generic topic-keyword selector here can drop
    an intentionally concrete source word such as ``evidence`` because that
    word is also planner metadata in other contexts. Validate the wire shape,
    but never silently re-select or substitute its terms.
    """

    if not isinstance(value, (list, tuple)) or len(value) > 8:
        return []
    normalized = [str(item or "").strip().lower() for item in value]
    if any(
        not token
        or len(token) > 64
        or not re.fullmatch(r"[a-z][a-z0-9]*", token)
        for token in normalized
    ):
        return []
    return normalized


def _deserialize_content_option_briefs(items: List[Dict[str, Any]] | None) -> List[ContentOptionBrief]:
    briefs: List[ContentOptionBrief] = []
    for index, item in enumerate(items or [], start=1):
        if not isinstance(item, dict):
            continue
        briefs.append(
            ContentOptionBrief(
                option_number=int(item.get("option_number") or index),
                framing_mode=str(item.get("framing_mode") or "operator_lesson"),
                primary_claim=_ensure_sentence(str(item.get("primary_claim") or "")),
                proof_packet=str(item.get("proof_packet") or ""),
                story_beat=str(item.get("story_beat") or ""),
                public_lane=str(item.get("public_lane") or _public_post_lane_for_option(int(item.get("option_number") or index))),
                thesis_treatment=str(item.get("thesis_treatment") or ""),
                proof_progression=str(item.get("proof_progression") or ""),
                payoff=str(item.get("payoff") or ""),
                mechanism_focus=str(item.get("mechanism_focus") or ""),
                recognition_basis=str(item.get("recognition_basis") or ""),
                mechanism_anchor_terms=_deserialize_bound_anchor_terms(
                    item.get("mechanism_anchor_terms")
                ),
                recognition_anchor_terms=_deserialize_bound_anchor_terms(
                    item.get("recognition_anchor_terms")
                ),
                decision_rule_basis=str(item.get("decision_rule_basis") or ""),
                decision_moment_basis=str(item.get("decision_moment_basis") or ""),
                decision_moment_anchor_terms=_deserialize_bound_anchor_terms(
                    item.get("decision_moment_anchor_terms")
                ),
                required_context_concepts=str(item.get("required_context_concepts") or ""),
                consequence_basis=str(item.get("consequence_basis") or ""),
                application_closing_anchor_terms=_deserialize_bound_anchor_terms(
                    item.get("application_closing_anchor_terms")
                ),
                proof_facet_id=str(item.get("proof_facet_id") or ""),
                semantic_payload_version=str(item.get("semantic_payload_version") or ""),
            )
        )
    return briefs


def _content_signal_chunks(content_context: ContentGenerationContext) -> List[Dict[str, Any]]:
    signal_chunks = getattr(content_context, "content_signal_chunks", None)
    if isinstance(signal_chunks, list):
        return signal_chunks
    reservoir_chunks = getattr(content_context, "content_reservoir_chunks", None)
    return reservoir_chunks if isinstance(reservoir_chunks, list) else []


def _content_signal_source(content_context: ContentGenerationContext) -> str:
    return str(getattr(content_context, "content_signal_source", "") or "persona_only")


def _serialize_content_signal_support(content_context: ContentGenerationContext) -> List[Dict[str, Any]]:
    return [
        {
            "source_id": str(item.get("source_id") or ""),
            "asset_id": str(item.get("source_file_id") or ""),
            "signal_lane": str((item.get("metadata") or {}).get("source_lane") or ""),
            "source_kind": str((item.get("metadata") or {}).get("source_kind") or ""),
            "reservoir_lane": str((item.get("metadata") or {}).get("content_reservoir_lane") or ""),
            "primary_type": str((item.get("metadata") or {}).get("claim_type") or ""),
            "score": int((item.get("weighted_score") or item.get("similarity_score") or 0)),
            "title": str((item.get("metadata") or {}).get("file_name") or ""),
            "text": str(item.get("chunk") or "")[:400],
            "source_path": str((item.get("metadata") or {}).get("source_path") or ""),
            "source_url": str((item.get("metadata") or {}).get("source_url") or ""),
        }
        for item in _content_signal_chunks(content_context)[:8]
    ]


def _serialize_content_reservoir_support(content_context: ContentGenerationContext) -> List[Dict[str, Any]]:
    return _serialize_content_signal_support(content_context)


def _source_card_payload(source_card: LocalCodexSourceCard | None) -> Dict[str, Any]:
    if source_card is None:
        return {}
    return source_card.model_dump(exclude_none=True)


def _source_card_identity_digest(source_card: LocalCodexSourceCard | None) -> str:
    payload = _source_card_payload(source_card)
    if not payload:
        return ""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _feezie_remote_source_card_projection(
    source_card: LocalCodexSourceCard | None,
) -> Dict[str, Any]:
    """Project only public-safe source metadata needed by downstream owner review.

    The Railway job is a remote execution envelope, not a private source archive.
    Stable source identifiers, local paths, target files, arbitrary provenance, raw
    proof fields, and owner clarification fields therefore stay outside the job.
    A digest preserves cache/source identity without retaining those inputs.
    """

    if source_card is None:
        return {}

    projected: Dict[str, Any] = {}
    text_fields = (
        "title",
        "summary",
        "hook",
        "owner_reaction",
        "route_reason",
        "priority_lane",
        "source_kind",
        "section",
    )
    for field_name in text_fields:
        value = anonymize_feezie_public_text(
            _public_source_card_text(
                getattr(source_card, field_name, None),
                source_card=source_card,
                limit=1200,
            ),
            limit=1200,
        )
        if value:
            projected[field_name] = value

    source_url = _public_source_card_url(source_card.source_url)
    if source_url:
        projected["source_url"] = source_url

    identity_digest = _source_card_identity_digest(source_card)
    if identity_digest:
        projected["source_identity_sha256"] = identity_digest
    return projected


def _feezie_private_request_identity_digest(req: LocalCodexJobCreateRequest) -> str:
    """Bind cache identity to private inputs without persisting their contents."""

    serialized = json.dumps(
        req.model_dump(exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _public_source_card_text(
    value: Any,
    *,
    source_card: LocalCodexSourceCard | None,
    limit: int = 1600,
) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return ""
    if source_card is not None:
        for private_reference in (source_card.source_path, source_card.target_file):
            private_value = " ".join(str(private_reference or "").split()).strip()
            if private_value:
                normalized = re.sub(re.escape(private_value), "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?:/Users|/home|/private|/tmp)/[^\s,;]+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[A-Za-z]:\\[^\s,;]+", "", normalized)
    normalized = re.sub(
        r"\b(?:backend|frontend|history|identity|knowledge|memory|prompts|sops|workspaces)/[^\s,;]+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = " ".join(normalized.split()).strip(" -,:;")
    return normalized[:limit]


def _public_source_card_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    hostname = str(parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return ""
    if (
        hostname in {"localhost", "0.0.0.0"}
        or hostname.startswith("127.")
        or hostname.startswith("10.")
        or hostname.startswith("192.168.")
        or hostname.endswith((".internal", ".local"))
    ):
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))[:1200]


def _parse_source_datetime(value: Any) -> datetime | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(cleaned[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_card_freshness_receipt(source_card: LocalCodexSourceCard | None) -> Dict[str, Any]:
    if source_card is None:
        return {
            "state": "not_applicable",
            "temporality": "none",
            "published_at": None,
            "observed_at": None,
            "age_days": None,
            "current_claim_allowed": False,
        }

    provenance = source_card.provenance
    published_raw = source_card.source_published_at or provenance.get("published_at")
    observed_raw = (
        source_card.source_observed_at
        or provenance.get("observed_at")
        or provenance.get("captured_at")
    )
    published_at = _parse_source_datetime(published_raw)
    observed_at = _parse_source_datetime(observed_raw)
    date_origin = "published_at" if published_at is not None else "observed_at" if observed_at is not None else None
    dated_at = published_at or observed_at
    if dated_at is None:
        path_match = re.search(r"(?:^|/)(\d{4}-\d{2}-\d{2})__", str(source_card.source_path or ""))
        if path_match:
            dated_at = _parse_source_datetime(path_match.group(1))
            date_origin = "source_filename"

    temporality = str(source_card.source_temporality or "").strip().lower()
    if not temporality:
        source_kind = str(source_card.source_kind or "").strip().lower()
        temporality = "trend" if source_kind in {"market_signal", "social_signal", "trend"} else "unknown"

    declared_state = str(source_card.freshness_state or "").strip().lower() or None
    age_days: int | None = None
    if dated_at is not None:
        age_days = max(0, int((datetime.now(timezone.utc) - dated_at).total_seconds() // 86400))

    if temporality == "evergreen":
        state = "evergreen"
    elif age_days is None:
        state = declared_state or "unknown"
    elif temporality == "trend":
        state = "current" if age_days <= 14 else "aging" if age_days <= 30 else "stale"
    else:
        state = "dated_recent" if age_days <= 30 else "dated_stale"

    return {
        "state": state,
        "declared_state": declared_state,
        "temporality": temporality,
        "published_at": published_at.isoformat() if published_at is not None else None,
        "observed_at": observed_at.isoformat() if observed_at is not None else None,
        "dated_at": dated_at.isoformat() if dated_at is not None else None,
        "date_origin": date_origin,
        "age_days": age_days,
        "current_claim_allowed": state == "current",
    }


def _source_card_public_context(source_card: LocalCodexSourceCard | None) -> str:
    if source_card is None:
        return ""
    lines: list[str] = []
    public_fields = (
        ("Title", source_card.title),
        ("Summary", source_card.summary),
        ("Source line", source_card.hook),
        ("Why it was routed", source_card.route_reason),
        ("Owner reaction", source_card.owner_reaction),
        ("Public lane", source_card.priority_lane),
        ("Source kind", source_card.source_kind),
        ("Section", source_card.section),
        ("Canonical pillar", source_card.canonical_pillar),
        ("Career signal", source_card.career_signal),
        ("Employer proximity", source_card.employer_proximity),
        ("Employer safety", source_card.employer_safety),
        ("Proof posture", source_card.proof_posture),
        ("Concrete action", source_card.concrete_action),
        ("Exact problem", source_card.exact_problem),
        ("Observable lesson", source_card.observable_lesson),
        ("Measurement treatment", source_card.treatment),
        ("Publish posture", source_card.publish_posture),
        ("Audience segment", source_card.audience),
        ("Audience consequence", source_card.audience_consequence),
        ("Distinct thesis", source_card.distinct_thesis),
        ("Why now", source_card.why_now),
        ("Development status", source_card.development_status),
        ("Source published", source_card.source_published_at),
        ("Source observed", source_card.source_observed_at),
        ("Declared freshness", source_card.freshness_state),
        ("Source temporality", source_card.source_temporality),
    )
    for label, value in public_fields:
        rendered = _public_source_card_text(value, source_card=source_card)
        if rendered:
            lines.append(f"{label}: {rendered}")
    source_url = _public_source_card_url(source_card.source_url)
    if source_url:
        lines.append(f"Original source: {source_url}")
    provenance_labels = {
        "author": "Author",
        "platform": "Platform",
        "publication": "Publication",
        "published_at": "Published",
        "source_label": "Source label",
        "capture_method": "Capture method",
    }
    for key, label in provenance_labels.items():
        rendered = _public_source_card_text(source_card.provenance.get(key), source_card=source_card, limit=500)
        if rendered:
            lines.append(f"{label}: {rendered}")
    if not lines:
        return ""
    return "Selected source card (public-safe writing context):\n" + "\n".join(lines)


def _local_codex_request_context(req: LocalCodexJobCreateRequest) -> str:
    base_context = str(req.context or "").strip()
    if req.source_card is not None:
        base_context = _public_source_card_text(base_context, source_card=req.source_card, limit=6000)
    source_context = _source_card_public_context(req.source_card)
    return "\n\n".join(part for part in (base_context, source_context) if part).strip()


def _feezie_generation_strategy_projection() -> Dict[str, Any]:
    contract = load_feezie_strategy_contract()
    positioning = contract["positioning"]
    editorial = contract["editorial_mix"]
    return {
        "schema_version": contract["schema_version"],
        "contract_hash": contract["contract_hash"],
        "approved_at": positioning["approved_at"],
        "positioning_model": list(positioning["positioning_model"]),
        "audience_priority": dict(positioning["audience_priority"]),
        "career_posture": dict(positioning["career_posture"]),
        "generation_quality_contract": dict(positioning["generation_quality_contract"]),
        "pillars": [
            {
                "id": pillar["id"],
                "label": pillar["label"],
                "career_signal": pillar["career_signal"],
            }
            for pillar in editorial["pillars"]
        ],
        "rolling_topic_mix": dict(editorial["rolling_topic_mix"]),
        "intent_mix": dict(editorial["intent_mix"]),
        "weekly_model": dict(editorial["weekly_model"]),
    }


def _feezie_portfolio_learning_projection() -> Dict[str, Any]:
    """Load the privacy-safe performance projection used by planner/writer/critic.

    Railway reads the aggregate snapshot mirrored by the private local ledger.
    A local backend may fall back to that same private ledger. Any missing,
    stale, incompatible, or corrupt source fails to collect-only behavior.
    """

    summary: Dict[str, Any] | None = None
    try:
        snapshot = get_snapshot_payload("feezie-os", "publication_performance_summary")
        if isinstance(snapshot, dict):
            summary = snapshot
    except Exception:
        summary = None
    if summary is None:
        try:
            local_summary = linkedin_performance_ledger_service.load_summary()
            if isinstance(local_summary, dict):
                summary = local_summary
        except Exception:
            summary = None
    return build_feezie_portfolio_learning_receipt(
        summary,
        strategy_contract=load_feezie_strategy_contract(),
    )


def _default_generation_pillar(*, audience: str, priority_lane: str | None) -> str | None:
    lane = re.sub(r"[\s_]+", "-", str(priority_lane or "").strip().lower())
    if lane in {"ai", "ops-pm", "entrepreneurship", "entrepreneurs", "tech-ai"} or audience in {"tech_ai", "entrepreneurs"}:
        return "ai_native"
    if lane in {"current-role", "program-leadership", "leadership", "enrollment-management"} or audience == "leadership":
        return "leadership_operator"
    if lane in {"admissions", "referral", "therapy", "education", "education-admissions"} or audience == "education_admissions":
        return "trust_systems"
    return None


def _resolve_feezie_generation_classification(
    *,
    req: LocalCodexJobCreateRequest,
    content_context: ContentGenerationContext,
    strategy: Dict[str, Any],
) -> Dict[str, Any]:
    source_card = req.source_card

    def selected(field: str) -> str | None:
        explicit = str(getattr(req, field, None) or "").strip()
        if explicit:
            return explicit
        if source_card is None:
            return None
        source_value = str(getattr(source_card, field, None) or "").strip()
        return source_value or None

    canonical_pillar = selected("canonical_pillar") or _default_generation_pillar(
        audience=req.audience,
        priority_lane=source_card.priority_lane if source_card is not None else None,
    )
    pillar_index = {
        str(item.get("id") or ""): item
        for item in strategy.get("pillars") or []
        if isinstance(item, dict)
    }
    career_signal = selected("career_signal")
    if not career_signal and canonical_pillar in pillar_index:
        career_signal = str(pillar_index[canonical_pillar].get("career_signal") or "") or None
    employer_proximity = selected("employer_proximity")
    if not employer_proximity and re.search(
        r"\bpersonal\s+AI\s+Clone\s+build\b",
        str(req.context or ""),
        flags=re.IGNORECASE,
    ):
        # This exact owner-authored phrase is an explicit classification signal;
        # broader free-text inference remains intentionally disabled.
        employer_proximity = "personal_build"
    employer_safety = selected("employer_safety")
    proof_posture = selected("proof_posture")
    treatment = selected("treatment")
    source_freshness = _source_card_freshness_receipt(source_card)

    if not employer_safety:
        employer_safety = "owner_review_required"
    if not proof_posture:
        proof_posture = "principle_only" if content_context.grounding_mode == "principle_only" else "owner_confirmation_required"

    missing = [
        field
        for field, value in (
            ("canonical_pillar", canonical_pillar),
            ("career_signal", career_signal),
            ("employer_proximity", employer_proximity),
        )
        if not value
    ]
    return {
        "canonical_pillar": canonical_pillar or "unclassified",
        "career_signal": career_signal or "unclassified",
        "employer_proximity": employer_proximity or "unclassified",
        "employer_safety": employer_safety,
        "proof_posture": proof_posture,
        "treatment": treatment,
        "publish_posture": str(source_card.publish_posture or "").strip() if source_card is not None else None,
        "audience": (str(source_card.audience or "").strip() if source_card is not None else "") or req.audience,
        "generation_audience": req.audience,
        "audience_consequence": (
            anonymize_feezie_public_text(source_card.audience_consequence, limit=500)
            if source_card is not None
            else None
        ),
        "distinct_thesis": (
            anonymize_feezie_public_text(source_card.distinct_thesis, limit=500)
            if source_card is not None
            else None
        ),
        "why_now": (
            anonymize_feezie_public_text(source_card.why_now, limit=500)
            if source_card is not None
            else None
        ),
        "development_status": str(source_card.development_status or "").strip() if source_card is not None else None,
        "source_freshness": source_freshness,
        "classification_state": "complete" if not missing else "owner_review_required",
        "missing_fields": missing,
    }


def _local_codex_cache_request_payload(req: LocalCodexJobCreateRequest) -> Dict[str, Any]:
    """Return a cache fingerprint that cannot become a second private source store."""

    request_digest = _feezie_private_request_identity_digest(req)
    user_digest = hashlib.sha256(str(req.user_id or "").encode("utf-8")).hexdigest()
    return {
        "user_id": f"sha256:{user_digest}",
        "topic": anonymize_feezie_public_text(req.topic, limit=320),
        "context": f"private-input-sha256:{request_digest}",
        "content_type": req.content_type,
        "category": req.category,
        "tone": "direct_curiosity_evidence_led",
        "audience": req.audience,
        "source_mode": req.source_mode,
        "canonical_pillar": req.canonical_pillar,
        "career_signal": req.career_signal,
        "employer_proximity": req.employer_proximity,
        "employer_safety": req.employer_safety,
        "proof_posture": req.proof_posture,
        "treatment": req.treatment,
    }


def _build_local_codex_idempotency_key(
    req: LocalCodexJobCreateRequest,
    *,
    context_cache_key: str | None = None,
) -> str:
    if str(req.idempotency_key or "").strip():
        return str(req.idempotency_key).strip()
    identity_payload = _local_codex_cache_request_payload(req)
    return build_content_job_idempotency_key(
        {
            "workspace_slug": req.workspace_slug,
            "user_id": req.user_id,
            "topic": req.topic,
            "context": identity_payload.get("context") or "",
            "content_type": req.content_type,
            "category": req.category,
            "tone": req.tone,
            "audience": req.audience,
            "source_mode": req.source_mode,
            "canonical_pillar": req.canonical_pillar,
            "career_signal": req.career_signal,
            "employer_proximity": req.employer_proximity,
            "employer_safety": req.employer_safety,
            "proof_posture": req.proof_posture,
            "treatment": req.treatment,
            "context_cache_key": context_cache_key or _feezie_generation_strategy_projection()["contract_hash"],
        }
    )


def _trim_job_error(message: str | None) -> str | None:
    normalized = " ".join((message or "").split()).strip()
    if not normalized:
        return None
    return normalized[:1200]


def _claim_is_flat_topic_label(claim: str) -> bool:
    normalized = _ensure_sentence(claim)
    if not normalized:
        return True
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    if len(words) > 3:
        return False
    if re.search(
        r"\b(?:is|isn't|isnt|are|was|were|be|becomes|beats|matters|wins|fails|works|holds|scales|changes|hurts|helps|keeps|strengthens|weakens|drives|creates)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return False
    return True


def _local_codex_primary_claims(*, topic: str, audience: str, primary_claims: List[str]) -> List[str]:
    topic_sentence = _ensure_sentence(topic)
    normalized_topic = " ".join((topic or "").lower().split())
    market_topic = any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants"))
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, str]] = []
    for claim in primary_claims:
        normalized_claim = _ensure_sentence(claim)
        if not normalized_claim:
            continue
        if market_topic and not re.search(
            r"\bmarket\b|\bcompetition\b|\bcompetitive\b|\bmeaner\b|\badvantage\b|\bpressure\b|\bentrants\b",
            normalized_claim,
            flags=re.IGNORECASE,
        ):
            continue
        score = len(_significant_terms(normalized_claim).intersection(focus_terms))
        if topic_sentence and topic_sentence.lower() in normalized_claim.lower():
            score += 4
        if _starts_with_third_person_persona_bio(normalized_claim):
            score -= 2
        ranked.append((score, normalized_claim))

    selected: List[str] = []
    seen: set[str] = set()
    if topic_sentence and not _claim_is_flat_topic_label(topic_sentence):
        selected.append(topic_sentence)
        seen.add(topic_sentence.lower())
    for score, claim in sorted(ranked, key=lambda item: item[0], reverse=True):
        key = claim.lower()
        if key in seen:
            continue
        if _claim_is_flat_topic_label(claim):
            continue
        if score <= 0 and selected:
            continue
        if _starts_with_third_person_persona_bio(claim) and selected:
            continue
        seen.add(key)
        selected.append(claim)
        if len(selected) >= 3:
            break
    if not selected:
        return primary_claims[:3]
    while len(selected) < min(3, max(1, len(primary_claims) or 1)):
        selected.append(selected[-1])
    return selected[:3]


def _local_codex_safe_anchor_chunks(chunks: List[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
    safe_chunks: List[Dict[str, Any]] = []
    for item in chunks:
        rendered = _render_anchor_chunk(item)
        if _starts_with_third_person_persona_bio(rendered):
            continue
        if _internal_public_jargon_hits(rendered):
            continue
        safe_chunks.append(item)
        if len(safe_chunks) >= limit:
            break
    if safe_chunks:
        return safe_chunks
    fallback_chunks = [
        item for item in chunks
        if not _starts_with_third_person_persona_bio(_render_anchor_chunk(item))
    ]
    return fallback_chunks[:limit] if fallback_chunks else chunks[:limit]


def _local_codex_story_beats(*, topic: str, story_beats: List[str]) -> List[str]:
    normalized_topic = " ".join((topic or "").lower().split())
    market_topic = any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants"))
    filtered: List[str] = []
    for beat in story_beats:
        normalized = _ensure_sentence(beat)
        if not normalized:
            continue
        if market_topic and re.search(
            r"\bai constraint breakthrough\b|\bquiet inefficiency cleanup\b|\bschema\b|\bprompt\b|\bvalidation\b|\bworkflow\b",
            normalized,
            flags=re.IGNORECASE,
        ):
            continue
        filtered.append(normalized)
    return filtered


def _local_codex_proof_packets(*, topic: str, proof_packets: List[str]) -> List[str]:
    normalized_topic = " ".join((topic or "").lower().split())
    market_topic = any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants"))
    filtered: List[str] = []
    for packet in proof_packets:
        evidence = _proof_packet_evidence_text(packet)
        if _internal_public_jargon_hits(evidence):
            continue
        if market_topic and re.search(
            r"\bai clone\b|\bnamed product\b|\bfrontier(?:-model)?\b|\bluxury\b|\bschema\b|\bvalidation\b|\bworkflow discipline\b|\binstruction-layer\b",
            packet,
            flags=re.IGNORECASE,
        ):
            continue
        filtered.append(packet)
    if market_topic and filtered:
        public_packets = [
            packet
            for packet in filtered
            if re.search(
                r"\bdashboard\b|\bsalesforce\b|\boutreach\b|\breferrals?\b|\bmeetings?\b|\bterritory\b|\bleadership\b|\bpriority\b",
                packet,
                flags=re.IGNORECASE,
            )
        ]
        if public_packets:
            return public_packets
    return filtered or proof_packets[:]


def _local_codex_approved_references(
    *,
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
) -> List[str]:
    references = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    filtered: List[str] = []
    for reference in references:
        if _starts_with_third_person_persona_bio(reference):
            continue
        if _internal_public_jargon_hits(reference):
            continue
        filtered.append(reference)
    return filtered


def _feezie_evidence_readiness(
    *,
    req: LocalCodexJobCreateRequest,
    content_context: ContentGenerationContext,
) -> Dict[str, Any]:
    source_card_payload = req.source_card.model_dump(exclude_none=True) if req.source_card is not None else {}
    answer_payload = req.evidence_answers.model_dump(exclude_none=True) if req.evidence_answers is not None else {}
    return evaluate_feezie_evidence_readiness(
        topic=req.topic,
        owner_context=req.context,
        owner_answers=answer_payload,
        source_card=source_card_payload,
        content_signal_chunks=_content_signal_chunks(content_context),
        qualification_route=source_card_payload.get("qualification_route"),
        existing_owner_question=source_card_payload.get("owner_question"),
    )


def _evidence_readiness_response_projection(readiness: Dict[str, Any]) -> Dict[str, Any]:
    """Return only bounded readiness metadata to the browser.

    The complete public-safe evidence remains in the private job context packet; an
    incomplete request never echoes source text or private records to Railway/UI.
    """

    allowed = (
        "schema_version",
        "status",
        "ready",
        "missing_fields",
        "present_fields",
        "field_sources",
        "clarification_key",
        "clarification_question",
        "block_reason",
        "retrieved_record_id_sha256",
        "receipt_sha256",
    )
    return {key: readiness.get(key) for key in allowed if readiness.get(key) is not None}


def _validated_evidence_contract(value: Any) -> Dict[str, Any]:
    contract = dict(value) if isinstance(value, dict) else {}
    if contract.get("schema_version") != EVIDENCE_CONTRACT_VERSION:
        raise ValueError("FEEZIE publish-ready evidence contract is missing or incompatible.")
    missing = [key for key in EVIDENCE_KEYS if not str(contract.get(key) or "").strip()]
    if missing:
        raise ValueError(f"FEEZIE publish-ready evidence contract is incomplete: {', '.join(missing)}")
    if contract.get("author_posture") != "learning_in_public":
        raise ValueError("FEEZIE technology-authority posture must remain learning_in_public.")
    return contract


def _student_scientist_enabled(*, req: LocalCodexJobCreateRequest, classification: Dict[str, Any]) -> bool:
    return bool(
        req.audience == "tech_ai"
        or str(classification.get("canonical_pillar") or "") == "ai_native"
        or str(classification.get("career_signal") or "") == "tech_proof"
        or str(classification.get("employer_proximity") or "") == "personal_build"
    )


_FEEZIE_OWNER_FUTURE_BOUNDARY_RE = re.compile(
    r"(?:,\s*|;\s*|\.\s+)(?:so\s+|and\s+)?(?="
    r"i\s+(?:will|shall|plan\s+to|intend\s+to|am\s+going\s+to|am\s+keeping)|"
    r"i['’](?:ll|m\s+going\s+to|m\s+keeping)\b|"
    r"(?:evidence|the|this|that|my|our|every)(?:\s+[a-z][a-z0-9'-]*){0,4}\s+"
    r"(?:must|should|will|needs?\s+to)\b)",
    flags=re.IGNORECASE,
)
_FEEZIE_OBSERVATION_PREFIX_RE = re.compile(
    r"^(?:"
    r"i\s+(?:confirmed|discovered|found|learned|noticed|observed|realized)\s+that|"
    r"(?:the|this)\s+(?:synthetic\s+)?"
    r"(?:build|comparison|cycle|exercise|replay|review|run|scenario|test|walkthrough)\s+"
    r"(?:confirmed|demonstrated|discovered|exposed|found|revealed|showed|taught)"
    r"(?:\s+me)?(?:\s+that)?"
    r")\s+",
    flags=re.IGNORECASE,
)
_FEEZIE_LESSON_ANCHOR_EXCLUSIONS = frozenset(
    {
        "about",
        "after",
        "appeared",
        "became",
        "began",
        "begin",
        "before",
        "build",
        "comparison",
        "created",
        "cycle",
        "depended",
        "earlier",
        "exercise",
        "exposed",
        "first",
        "found",
        "had",
        "learned",
        "learning",
        "let",
        "made",
        "making",
        "needs",
        "noticed",
        "not",
        "observation",
        "observed",
        "only",
        "point",
        "replay",
        "revealed",
        "review",
        "run",
        "scenario",
        "showed",
        "synthetic",
        "taught",
        "test",
        "tied",
        "visible",
        "walkthrough",
        "when",
        "where",
        "which",
        "without",
    }
)
_FEEZIE_SEPARATE_FOCUS_RE = re.compile(
    r"^(?P<focus>.+?)\s+(?:are|is)\s+(?:separate|distinct|different)\s+"
    r"(?:checks?|gates?|criteria|requirements?|things?)\b",
    flags=re.IGNORECASE,
)
_FEEZIE_NOT_FOCUS_RE = re.compile(
    r"^(?P<left>.+?)\s+is\s+not\s+(?P<right>.+)$",
    flags=re.IGNORECASE,
)
_FEEZIE_COMPARATIVE_FOCUS_RE = re.compile(
    r"^(?P<left>.+?)\s+(?:matters|works)\s+(?:more|better)\s+than\s+(?P<right>.+)$",
    flags=re.IGNORECASE,
)
_FEEZIE_LESSON_OBJECT_PATTERNS = (
    re.compile(
        r"\bmade\s+(?P<object>.+?)\s+(?:independently\s+)?"
        r"(?:actionable|clearer|distinguishable|inspectable|legible|visible)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\blet\s+(?P<object>.+?)\s+(?:advance|begin|continue|move|start)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bmaking\s+(?P<object>.+?)\s+(?:clear|inspectable|legible|visible)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:can\s+)?sharpen(?:ed|s)?\s+(?P<object>.+?)\s+when\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<object>.+?)\s+(?:appeared|became|created|depended|emerged|made|surfaced)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<object>.+?)\s+(?:earlier|later)\s+when\b",
        flags=re.IGNORECASE,
    ),
)
_FEEZIE_PROBLEM_CONSEQUENCE_RE = re.compile(
    r"(?:,\s*so\s+|;\s*so\s+|\bwhich\s+meant\s+)(?P<consequence>.+)$",
    flags=re.IGNORECASE,
)
_FEEZIE_IMPLEMENTED_GATE_RELATION_RE = re.compile(
    r"\b(?P<relation>only\s+when|only\s+if|unless|without|before|until|when)\b",
    flags=re.IGNORECASE,
)
_FEEZIE_OBSERVATION_OBJECT_SUBJECT_RE = re.compile(
    r"^(?P<object>.+?)\s+(?:"
    r"made|let|became|appeared|created|sharpened|can\s+sharpen|"
    r"depends?\s+on|depended\s+on"
    r")\b",
    flags=re.IGNORECASE,
)
_FEEZIE_OBSERVATION_OBJECT_TIMING_RE = re.compile(
    r"^(?P<object>.+?)\s+(?:earlier|first)\s+(?:when|before|at)\b",
    flags=re.IGNORECASE,
)
_FEEZIE_OBSERVATION_VISIBLE_BOUNDARY_RE = re.compile(
    r"\bmaking\s+(?:the\s+)?(?P<object>[a-z][a-z0-9'’-]*"
    r"(?:\s+[a-z][a-z0-9'’-]*){1,8}?\s+boundary)\s+visible\b",
    flags=re.IGNORECASE,
)
_FEEZIE_IMPLEMENTED_GATE_VERB_RE = re.compile(
    r"\b(?P<verb>accepts?|accepted|adds?|added|advances?|advanced|allows?|allowed|checks?|checked|"
    r"counts?|counted|keeps?|kept|publishes?|published|queues?|queued|releases?|released|"
    r"requires?|required|trusts?|trusted|treats?|treated|uses?|used|validates?|validated)\b",
    flags=re.IGNORECASE,
)
_FEEZIE_GATE_VERB_BASE = {
    "accepted": "accept",
    "accepts": "accept",
    "added": "add",
    "adds": "add",
    "advanced": "advance",
    "advances": "advance",
    "allowed": "allow",
    "allows": "allow",
    "checked": "check",
    "checks": "check",
    "counted": "count",
    "counts": "count",
    "keeps": "keep",
    "kept": "keep",
    "published": "publish",
    "publishes": "publish",
    "queued": "queue",
    "queues": "queue",
    "released": "release",
    "releases": "release",
    "required": "require",
    "requires": "require",
    "trusted": "trust",
    "trusts": "trust",
    "treated": "treat",
    "treats": "treat",
    "used": "use",
    "uses": "use",
    "validated": "validate",
    "validates": "validate",
}
_FEEZIE_ACTION_AUXILIARIES = frozenset(
    {
        "am",
        "are",
        "be",
        "been",
        "being",
        "can",
        "could",
        "did",
        "do",
        "does",
        "had",
        "has",
        "have",
        "is",
        "may",
        "might",
        "must",
        "shall",
        "should",
        "was",
        "were",
        "will",
        "would",
    }
)
_FEEZIE_ACTION_MODIFIERS = frozenset(
    {
        "actually",
        "already",
        "also",
        "even",
        "just",
        "never",
        "not",
        "now",
        "only",
        "previously",
        "recently",
        "simply",
        "still",
        "then",
    }
)
_FEEZIE_AUXILIARY_LEXICAL_ACTION_RE = re.compile(
    r"^(?:[a-z][a-z'-]*ly\s+)*(?P<verb>"
    r"[a-z][a-z'-]*(?:ed|en|ing)|built|brought|caught|chose|cut|drove|found|gave|"
    r"held|kept|led|left|lost|made|met|paid|put|ran|read|said|saw|sent|set|sold|"
    r"split|taught|told|took|understood|won|wrote"
    r")\b",
    flags=re.IGNORECASE,
)


def _feezie_lesson_focus_clause(recognition: str) -> str:
    """Prefer the decisive supported clause over a broad setup clause."""

    clauses = [
        clause.strip(" -,:;.!?")
        for clause in re.split(r"\s*;\s*|(?<=[.!?])\s+", str(recognition or ""))
        if clause.strip(" -,:;.!?")
    ]
    for clause in reversed(clauses):
        if (
            _FEEZIE_SEPARATE_FOCUS_RE.match(clause)
            or _FEEZIE_NOT_FOCUS_RE.match(clause)
            or _FEEZIE_COMPARATIVE_FOCUS_RE.match(clause)
        ):
            return clause
    return clauses[-1] if clauses else ""


def _feezie_lesson_anchor_terms(recognition: str) -> List[str]:
    """Select source words for role grounding without setup scaffolding."""

    focus_clause = _feezie_lesson_focus_clause(recognition)
    blocked = set(STOPWORDS).union(_FEEZIE_LESSON_ANCHOR_EXCLUSIONS)
    ordered: List[str] = []
    for source in (focus_clause, recognition):
        for token in re.findall(r"[a-z][a-z0-9]*", source.lower()):
            if len(token) < 3 or token in blocked or token in ordered:
                continue
            ordered.append(token)
    return ordered


_FEEZIE_CONSEQUENCE_DERIVATIONAL_FAMILIES = (
    frozenset({"ready", "readiness"}),
)


def _feezie_conservative_inflection_family(term: str) -> set[str]:
    """Return only ordinary grammatical forms for a source-bound term."""

    normalized = "".join(re.findall(r"[a-z0-9]+", str(term or "").lower()))
    if not normalized:
        return set()
    family = {normalized}
    if len(normalized) > 4 and normalized.endswith("ies"):
        family.add(normalized[:-3] + "y")
    elif len(normalized) > 4 and normalized.endswith("s") and not normalized.endswith("ss"):
        family.add(normalized[:-1])
    if len(normalized) > 5 and normalized.endswith("ed"):
        family.add(normalized[:-2])
        family.add(normalized[:-1])
    if len(normalized) > 5 and normalized.endswith("ing"):
        family.add(normalized[:-3])
        family.add(normalized[:-3] + "e")
    if len(normalized) > 5 and normalized.endswith("ly"):
        family.add(normalized[:-2])
    return family


def _feezie_diagnosis_opening_terms(value: str) -> set[str]:
    """Return the exact term class enforced by the diagnosis hook gate."""

    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 3 and token not in STOPWORDS
    }


def _feezie_application_closing_anchor_terms(
    recognition: str,
    consequence_basis: str,
) -> List[str]:
    """Keep application anchors lesson-derived and consequence-compatible."""

    lesson_terms = _feezie_lesson_anchor_terms(recognition)
    if len(lesson_terms) < 2:
        raise ValueError("FEEZIE observable lesson cannot produce two closing anchors.")
    consequence_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", str(consequence_basis or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }

    def consequence_compatible(term: str) -> bool:
        if term in {"can", "could", "may", "might"}:
            return False
        if term in consequence_terms:
            return True
        term_family = _feezie_conservative_inflection_family(term)
        if any(
            term_family.intersection(_feezie_conservative_inflection_family(source_term))
            for source_term in consequence_terms
        ):
            return True
        return any(
            term in family and bool(family.intersection(consequence_terms))
            for family in _FEEZIE_CONSEQUENCE_DERIVATIONAL_FAMILIES
        )

    compatible = [term for term in lesson_terms if consequence_compatible(term)]
    return compatible[:2] if len(compatible) >= 2 else lesson_terms[:2]


def _feezie_clean_focus_operand(value: str) -> str:
    cleaned = " ".join(str(value or "").split()).strip(" -,:;.!?")
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+by\s+(?:itself|themselves)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" -,:;.!?")


def _feezie_supported_lesson_object(recognition: str) -> str:
    """Project a natural decision object directly from the supported lesson.

    Falling back to two isolated anchor tokens produced grammatical artifacts
    such as ``missing and evidence`` and ``trust and human``.  These bounded
    patterns retain a contiguous source phrase around the lesson's own
    predicate.  If no usable two-to-eighteen-word phrase exists, callers keep
    the conservative anchor fallback.
    """

    focus_clause = _feezie_lesson_focus_clause(recognition)
    for pattern in _FEEZIE_LESSON_OBJECT_PATTERNS:
        match = pattern.search(focus_clause)
        if match is None:
            continue
        projected = _feezie_clean_focus_operand(match.group("object"))
        word_count = len(re.findall(r"[A-Za-z0-9]+", projected))
        if not 2 <= word_count <= 18:
            continue
        projected_terms = {
            token
            for token in re.findall(r"[a-z0-9]+", projected.lower())
            if token not in STOPWORDS
        }
        recognition_terms = set(re.findall(r"[a-z0-9]+", focus_clause.lower()))
        if projected_terms and projected_terms.issubset(recognition_terms):
            return projected
    return ""


def _feezie_implemented_gate_projection(concrete_action: str) -> tuple[str, str, str] | None:
    """Project an action/object/boundary only when the owner's action states one."""

    action = " ".join(str(concrete_action or "").split()).strip()
    relation_match = _FEEZIE_IMPLEMENTED_GATE_RELATION_RE.search(action)
    if relation_match is None:
        return None
    prefix = action[: relation_match.start()].strip(" -,:;.!?")
    boundary_tail = action[relation_match.end():].strip(" -,:;.!?")
    # Bind the gate to its own clause. Later implementation sentences are
    # evidence context, not part of the decision boundary.
    boundary_tail = re.split(r"(?<=[.!?])\s+", boundary_tail, maxsplit=1)[0].strip(" -,:;.!?")
    verb_matches = list(_FEEZIE_IMPLEMENTED_GATE_VERB_RE.finditer(prefix))
    if not verb_matches or len(re.findall(r"[A-Za-z0-9]+", boundary_tail)) < 2:
        return None
    verb_match = verb_matches[-1]
    decision_action = _FEEZIE_GATE_VERB_BASE.get(
        verb_match.group("verb").lower(),
        verb_match.group("verb").lower(),
    )
    decision_object = prefix[verb_match.end():].strip(" -,:;.!?")
    if not 1 <= len(re.findall(r"[A-Za-z0-9]+", decision_object)) <= 18:
        return None
    relation = " ".join(relation_match.group("relation").lower().split())
    if relation == "only when":
        relation = "only if"
    return decision_action, decision_object, f"{relation} {boundary_tail}"


def _feezie_implemented_gate_action_basis(concrete_action: str) -> str:
    """Return the distinct first-person action facet left after gate projection."""

    action = " ".join(str(concrete_action or "").split()).strip()
    relation_match = _FEEZIE_IMPLEMENTED_GATE_RELATION_RE.search(action)
    if relation_match is None:
        return ""
    prefix = action[: relation_match.start()].strip(" -,:;.!?")
    verb_matches = list(_FEEZIE_IMPLEMENTED_GATE_VERB_RE.finditer(prefix))
    if not verb_matches:
        return ""
    gate_verb = verb_matches[-1]
    first_person = re.search(r"\bi\s+[a-z][a-z'-]*\b", prefix, flags=re.IGNORECASE)
    if first_person is None or first_person.start() >= gate_verb.start():
        return ""

    candidate = prefix[first_person.start() : gate_verb.start()].strip(" -,:;.!?")
    connectors = list(
        re.finditer(r"\b(?:and|so|that|which|to)\b", candidate, flags=re.IGNORECASE)
    )
    if connectors:
        trimmed = candidate[: connectors[-1].start()].strip(" -,:;.!?")
        if len(re.findall(r"[A-Za-z0-9]+", trimmed)) >= 3:
            candidate = trimmed
    candidate = re.sub(
        r"\b(?:and|so|that|which|to)\s*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip(" -,:;.!?")
    predicate_match = re.match(
        r"i\s+(?P<verb>[a-z][a-z'-]*)\b",
        candidate,
        flags=re.IGNORECASE,
    )
    if predicate_match is None or len(re.findall(r"[A-Za-z0-9]+", candidate)) < 3:
        return ""
    gate_base = _FEEZIE_GATE_VERB_BASE.get(
        gate_verb.group("verb").lower(),
        gate_verb.group("verb").lower(),
    )
    residual_verb = predicate_match.group("verb").lower()
    if residual_verb in _FEEZIE_ACTION_AUXILIARIES:
        predicate_tail = candidate[predicate_match.end() :].strip()
        while predicate_tail:
            modifier_match = re.match(r"(?P<word>[a-z][a-z'-]*)\b", predicate_tail, flags=re.IGNORECASE)
            if (
                modifier_match is None
                or modifier_match.group("word").lower()
                not in _FEEZIE_ACTION_MODIFIERS.union(_FEEZIE_ACTION_AUXILIARIES)
            ):
                break
            predicate_tail = predicate_tail[modifier_match.end() :].strip()
        lexical_match = _FEEZIE_AUXILIARY_LEXICAL_ACTION_RE.match(predicate_tail)
        if lexical_match is None:
            return ""
        residual_verb = lexical_match.group("verb").lower()
    if residual_verb == gate_base or _FEEZIE_GATE_VERB_BASE.get(residual_verb) == gate_base:
        return ""
    return candidate[0].upper() + candidate[1:] + "."


def _feezie_role_safe_lesson_projection(observable_lesson: str) -> tuple[str, str]:
    """Separate recognition from an explicit owner future-action tail.

    The evidence contract remains untouched. These projections only keep the
    diagnosis from prescribing and give the application role a grammatical,
    evidence-contained object to check.
    """

    full_lesson = " ".join(str(observable_lesson or "").split()).strip()
    split = _FEEZIE_OWNER_FUTURE_BOUNDARY_RE.search(full_lesson)
    observation = (full_lesson[: split.start()] if split else full_lesson).rstrip(" -,:;.!?")
    recognition = _FEEZIE_OBSERVATION_PREFIX_RE.sub("", observation).strip(" -,:;.!?")
    if len(re.findall(r"[A-Za-z0-9]+", recognition)) < 3:
        raise ValueError("FEEZIE observable lesson cannot produce a bounded recognition signal.")

    focus_clause = _feezie_lesson_focus_clause(recognition)
    focus_match = _FEEZIE_SEPARATE_FOCUS_RE.match(focus_clause)
    if focus_match:
        decision_object = _feezie_clean_focus_operand(focus_match.group("focus"))
    elif (not_match := _FEEZIE_NOT_FOCUS_RE.match(focus_clause)):
        decision_object = (
            f"{_feezie_clean_focus_operand(not_match.group('left'))} and "
            f"{_feezie_clean_focus_operand(not_match.group('right'))}"
        )
    elif (comparison := _FEEZIE_COMPARATIVE_FOCUS_RE.match(focus_clause)):
        decision_object = (
            f"{_feezie_clean_focus_operand(comparison.group('left'))} and "
            f"{_feezie_clean_focus_operand(comparison.group('right'))}"
        )
    else:
        decision_object = _feezie_supported_lesson_object(focus_clause or recognition)
        if not decision_object:
            anchors = _feezie_lesson_anchor_terms(focus_clause or recognition)
            if len(anchors) < 2:
                raise ValueError("FEEZIE observable lesson cannot produce a source-bound decision object.")
            decision_object = f"{anchors[0]} and {anchors[1]}"
    decision_object = " ".join(decision_object.split()).strip(" -,:;.!?")
    if not 2 <= len(re.findall(r"[A-Za-z0-9]+", decision_object)) <= 18:
        raise ValueError("FEEZIE decision object is outside the bounded role contract.")
    return recognition + ".", decision_object


def _feezie_source_bound_observation_object(
    recognition: str,
    *,
    legacy_object: str,
) -> str:
    """Project a grammatical application object from one contiguous source phrase."""

    source = " ".join(str(recognition or "").split()).strip(" -,:;.!?")
    normalized_source = source.lower()

    def source_candidate(value: str) -> str:
        candidate = _feezie_clean_focus_operand(value)
        word_count = len(re.findall(r"[A-Za-z0-9]+", candidate))
        if not 2 <= word_count <= 12:
            return ""
        if " ".join(candidate.lower().split()) not in normalized_source:
            return ""
        return candidate

    focus_clause = _feezie_lesson_focus_clause(source)
    focus_match = _FEEZIE_SEPARATE_FOCUS_RE.match(focus_clause)
    if focus_match:
        candidate = source_candidate(focus_match.group("focus"))
        if candidate:
            return candidate
    not_match = _FEEZIE_NOT_FOCUS_RE.match(focus_clause)
    if not_match:
        for operand in (not_match.group("left"), not_match.group("right")):
            candidate = source_candidate(operand)
            if candidate:
                return candidate
        # A one-word X-is-not-Y comparison has no usable multiword operand.
        # The role projection already built this exact, source-bound pair; it
        # is the only non-contiguous fallback permitted here.
        paired_candidate = _feezie_clean_focus_operand(legacy_object)
        paired_terms = set(re.findall(r"[a-z0-9]+", paired_candidate.lower()))
        source_terms = set(re.findall(r"[a-z0-9]+", normalized_source))
        if (
            2 <= len(re.findall(r"[A-Za-z0-9]+", paired_candidate)) <= 4
            and paired_terms
            and paired_terms.issubset(source_terms.union({"and"}))
        ):
            return paired_candidate
    comparison = _FEEZIE_COMPARATIVE_FOCUS_RE.match(focus_clause)
    if comparison:
        candidate = source_candidate(comparison.group("left"))
        if candidate:
            return candidate

    for pattern in (
        _FEEZIE_OBSERVATION_OBJECT_SUBJECT_RE,
        _FEEZIE_OBSERVATION_OBJECT_TIMING_RE,
        _FEEZIE_OBSERVATION_VISIBLE_BOUNDARY_RE,
    ):
        match = pattern.search(focus_clause)
        if not match:
            continue
        candidate = source_candidate(match.group("object"))
        if candidate:
            return candidate

    candidate = source_candidate(legacy_object)
    if candidate:
        return candidate
    raise ValueError(
        "FEEZIE observable lesson cannot produce a contiguous natural decision object."
    )


def _feezie_source_bound_observation_boundary(recognition: str) -> str:
    """Keep an observation boundary source-bound without producing `when when`."""

    focus_clause = _feezie_lesson_focus_clause(recognition)
    relation_match = _FEEZIE_IMPLEMENTED_GATE_RELATION_RE.search(focus_clause)
    if relation_match is not None:
        boundary_tail = focus_clause[relation_match.end():].strip(" -,:;.!?")
        if len(re.findall(r"[A-Za-z0-9]+", boundary_tail)) >= 2:
            relation = " ".join(relation_match.group("relation").lower().split())
            if relation == "only when":
                relation = "only if"
            return f"{relation} {boundary_tail}"
    if len(re.findall(r"[A-Za-z0-9]+", focus_clause)) < 3:
        raise ValueError("FEEZIE observable lesson cannot produce a bounded application boundary.")
    return f"when {focus_clause}"


def _feezie_decision_moment_focus(decision_moment_basis: str) -> str:
    """Remove planner scaffolding while preserving the approved decision condition."""

    basis = " ".join(str(decision_moment_basis or "").split()).strip(" -,:;.!?")
    focus = re.sub(
        r"^(?:the\s+)?(?:(?:design\s+)?decision|distinction|test|story)\s+"
        r"(?:appears|matters|becomes\s+useful|is\s+useful)\s+"
        r"(?:whenever|when|at)\s+",
        "",
        basis,
        count=1,
        flags=re.IGNORECASE,
    ).strip(" -,:;.!?")
    word_count = len(re.findall(r"[A-Za-z0-9]+", focus))
    if not 2 <= word_count <= 24:
        raise ValueError("FEEZIE decision moment cannot produce a bounded opening basis.")
    return focus


def _feezie_decision_moment_anchor_terms(decision_moment_basis: str) -> List[str]:
    focus = _feezie_decision_moment_focus(decision_moment_basis)
    anchors = _semantic_anchor_candidates(
        focus,
        exclude_terms={
            "appears",
            "becomes",
            "could",
            "every",
            "matters",
            "useful",
            "whenever",
        },
    )
    if len(anchors) < 2:
        raise ValueError("FEEZIE decision moment requires two substantive opening anchors.")
    return anchors[:2]


def _feezie_application_rule_projection(
    *,
    concrete_action: str,
    observable_lesson: str,
    decision_moment_basis: str = "",
) -> tuple[str, str, str, str]:
    """Return a source-bound application gate without inventing a future action."""

    full_lesson = " ".join(str(observable_lesson or "").split()).strip()
    future_split = _FEEZIE_OWNER_FUTURE_BOUNDARY_RE.search(full_lesson)
    recognition, lesson_object = _feezie_role_safe_lesson_projection(full_lesson)
    if future_split is not None:
        future_tail = full_lesson[future_split.start():].strip(" -,:;.!?")
        boundary_match = _FEEZIE_IMPLEMENTED_GATE_RELATION_RE.search(future_tail)
        if boundary_match is not None:
            boundary_tail = future_tail[boundary_match.end():].strip(" -,:;.!?")
            if len(re.findall(r"[A-Za-z0-9]+", boundary_tail)) >= 2:
                relation = " ".join(boundary_match.group("relation").lower().split())
                if relation == "only when":
                    relation = "only if"
                return "check", lesson_object, f"{relation} {boundary_tail}", "owner-confirmed next step"

    implemented_gate = _feezie_implemented_gate_projection(concrete_action)
    implemented_action_basis = _feezie_implemented_gate_action_basis(concrete_action)
    if implemented_gate is not None and implemented_action_basis:
        decision_action, decision_object, boundary = implemented_gate
        return decision_action, decision_object, boundary, "owner-confirmed implemented gate"

    if str(decision_moment_basis or "").strip():
        decision_moment = _feezie_decision_moment_focus(decision_moment_basis)
        return (
            "frame",
            decision_moment,
            f"when {decision_moment}",
            "owner-approved decision moment",
        )

    focus_clause = _feezie_lesson_focus_clause(recognition)
    comparison = _FEEZIE_COMPARATIVE_FOCUS_RE.match(focus_clause)
    if comparison is not None:
        left = _feezie_clean_focus_operand(comparison.group("left"))
        right = _feezie_clean_focus_operand(comparison.group("right"))
        return "prioritize", left, f"before {right}", "owner-confirmed observation"

    # A fully source-bound fallback is intentionally less forceful than an
    # invented owner commitment. The critic can still withhold weak prose.
    observation_object = _feezie_source_bound_observation_object(
        recognition,
        legacy_object=lesson_object,
    )
    observation_boundary = _feezie_source_bound_observation_boundary(recognition)
    return "check", observation_object, observation_boundary, "owner-confirmed observation"


def _feezie_problem_consequence_projection(exact_problem: str) -> str:
    problem = " ".join(str(exact_problem or "").split()).strip()
    match = _FEEZIE_PROBLEM_CONSEQUENCE_RE.search(problem)
    consequence = (match.group("consequence") if match else problem).strip(" -,:;.!?")
    if len(re.findall(r"[A-Za-z0-9]+", consequence)) < 5:
        raise ValueError("FEEZIE exact problem cannot produce a supported consequence.")
    return consequence + "."


def _bind_publish_ready_evidence_to_briefs(
    briefs: List[ContentOptionBrief],
    evidence_contract: Dict[str, Any],
    *,
    audience_consequence: str = "",
    decision_moment_basis: str,
    strategic_opening_basis: str,
) -> None:
    """Make the role-specific semantic gates compatible with the same lived evidence.

    The pair still performs two different jobs: diagnosis explains the observed
    failure, while application turns the lesson into a bounded decision gate.
    Neither role may drift to a planner-created abstraction.
    """

    if len(briefs) != FEEZIE_CODEX_DRAFT_OPTION_COUNT:
        raise ValueError("FEEZIE evidence binding requires exactly two planned option briefs.")
    concrete_action = str(evidence_contract["concrete_action"]).strip()
    exact_problem = str(evidence_contract["exact_problem"]).strip()
    observable_lesson = str(evidence_contract["observable_lesson"]).strip()
    strategic_opening = " ".join(str(strategic_opening_basis or "").split()).strip()
    if not strategic_opening:
        raise ValueError("FEEZIE diagnosis requires a public-safe strategic opening basis.")
    strategic_terms = _feezie_diagnosis_opening_terms(strategic_opening)
    if len(strategic_terms) < 2:
        raise ValueError(
            "FEEZIE diagnosis strategic opening basis needs at least two substantive public-safe terms."
        )
    recognition_basis, _lesson_object = _feezie_role_safe_lesson_projection(observable_lesson)
    decision_moment = _feezie_decision_moment_focus(decision_moment_basis)
    decision_moment_anchors = _feezie_decision_moment_anchor_terms(decision_moment)
    decision_action, decision_object, decision_boundary, rule_posture = _feezie_application_rule_projection(
        concrete_action=concrete_action,
        observable_lesson=observable_lesson,
        decision_moment_basis=decision_moment,
    )
    paragraph_two_action = (
        _feezie_implemented_gate_action_basis(concrete_action)
        if rule_posture == "owner-confirmed implemented gate"
        else concrete_action
    )
    if not paragraph_two_action:
        raise ValueError("FEEZIE application cannot separate its opening gate from paragraph-two action.")
    # The planner's explicit audience consequence is the authoritative
    # application payoff when the selected source card supplies one.  The
    # exact-problem projection is only a safe fallback; replacing a stronger
    # audience consequence with the whole problem made application drafts
    # repeat the diagnosis and left their closers without a concrete payoff.
    consequence_basis = (
        " ".join(str(audience_consequence or "").split()).strip(" -,:;.!?") + "."
        if str(audience_consequence or "").strip()
        else _feezie_problem_consequence_projection(exact_problem)
    )
    problem_anchor_candidates = _semantic_anchor_candidates(exact_problem)
    problem_anchors = [
        candidate
        for candidate in problem_anchor_candidates
        if not any(
            _feezie_conservative_inflection_family(candidate).intersection(
                _feezie_conservative_inflection_family(strategic_term)
            )
            for strategic_term in strategic_terms
        )
    ]
    lesson_focus = _feezie_lesson_focus_clause(recognition_basis)
    lesson_anchors = _feezie_lesson_anchor_terms(lesson_focus or recognition_basis)
    if len(problem_anchors) < 2:
        raise ValueError(
            "FEEZIE evidence needs two exact-problem anchors that do not overlap the strategic opening basis."
        )
    if len(lesson_anchors) < 2:
        raise ValueError("FEEZIE evidence needs at least two substantive lesson terms.")

    diagnosis, application = briefs
    diagnosis.framing_mode = "bounded_evidence_diagnosis"
    # The writer, opaque critic, and deterministic hook gate must grade the
    # same public-safe strategic tension. The exact problem and both of its
    # anchors remain reserved for paragraph two.
    diagnosis.primary_claim = strategic_opening
    diagnosis.proof_packet = concrete_action
    diagnosis.story_beat = recognition_basis
    diagnosis.mechanism_focus = exact_problem
    diagnosis.mechanism_anchor_terms = problem_anchors[:2]
    diagnosis.recognition_basis = recognition_basis
    diagnosis.recognition_anchor_terms = lesson_anchors[:2]

    application.framing_mode = "bounded_evidence_application"
    application.primary_claim = consequence_basis
    application.proof_packet = concrete_action
    application.story_beat = recognition_basis
    application.decision_moment_basis = decision_moment
    application.decision_moment_anchor_terms = decision_moment_anchors
    application.required_context_concepts = (
        f"Paragraph-two action: {paragraph_two_action} | Exact problem: {exact_problem}"
    )
    application.consequence_basis = consequence_basis
    application.application_closing_anchor_terms = _feezie_application_closing_anchor_terms(
        recognition_basis,
        consequence_basis,
    )
    application.decision_rule_basis = (
        f"Decision action: {decision_action} | decision object: {decision_object} | "
        f"boundary: {decision_boundary} | rule posture: {rule_posture}."
    )


def _feezie_codex_execution_profile() -> Dict[str, Any]:
    return {
        "schema_version": FEEZIE_CODEX_EXECUTION_PROFILE_VERSION,
        "substrate": "codex_cli_saved_login",
        "writer": {
            "model": FEEZIE_CODEX_MODEL,
            "reasoning_effort": "high",
        },
        "revision": {
            "model": FEEZIE_CODEX_MODEL,
            "reasoning_effort": "high",
        },
        "critic": {
            "model": FEEZIE_CODEX_MODEL,
            "reasoning_effort": "medium",
        },
    }


def _feezie_remote_safe_context_projection(
    *,
    topic: str,
    audience: str,
    intent: str,
    classification: Dict[str, Any],
    evidence_contract: Dict[str, Any],
    audience_consequence: str = "",
    student_scientist_enabled: bool,
) -> Dict[str, Any]:
    """Return the one closed remote-safe context shared by production and acceptance."""

    safe_topic = anonymize_feezie_public_text(topic, limit=320)
    projected_evidence_contract = {
        key: evidence_contract[key]
        for key in (
            "schema_version",
            "status",
            "author_posture",
            "concrete_action",
            "exact_problem",
            "observable_lesson",
            "field_sources",
            "retrieved_record_id_sha256",
            "missing_fields",
            "contract_sha256",
        )
        if key in evidence_contract
    }
    bounded_consequence = " ".join(str(audience_consequence or "").split()).strip()
    if bounded_consequence:
        projected_evidence_contract["audience_consequence"] = bounded_consequence
    projected_evidence_contract["student_scientist_enabled"] = bool(student_scientist_enabled)
    return {
        "packet_schema_version": FEEZIE_REMOTE_JOB_PACKET_VERSION,
        "prompt": FEEZIE_REMOTE_BOOTSTRAP_PROMPT,
        "remote_execution_context": {
            "schema_version": FEEZIE_REMOTE_EXECUTION_CONTEXT_VERSION,
            "topic": safe_topic,
            "audience": audience,
            "intent": intent,
            "tone": "direct_curiosity_evidence_led",
            "canonical_pillar": str(classification.get("canonical_pillar") or "unclassified"),
            "career_signal": str(classification.get("career_signal") or "unclassified"),
            "employer_safety": str(classification.get("employer_safety") or "caution"),
            "proof_posture": str(classification.get("proof_posture") or "verified_public"),
            "author_posture": "learning_in_public",
        },
        "remote_prompt_policy": {
            "schema_version": FEEZIE_REMOTE_PROMPT_POLICY_VERSION,
            "raw_context_excluded": True,
            "private_paths_excluded": True,
            "raw_voice_examples_excluded": True,
            "source_bodies_excluded": True,
            "allowed_evidence": [
                "remote_execution_context",
                "publish_ready_evidence_contract",
            ],
        },
        "evidence_contract": projected_evidence_contract,
    }


def _build_local_codex_context_packet(
    *,
    req: LocalCodexJobCreateRequest,
    content_context: ContentGenerationContext,
    evidence_contract: Dict[str, Any],
) -> Dict[str, Any]:
    evidence_contract = _validated_evidence_contract(evidence_contract)
    codex_execution_profile = _feezie_codex_execution_profile()
    strategy_contract = _feezie_generation_strategy_projection()
    portfolio_learning = _feezie_portfolio_learning_projection()
    generation_quality_contract = dict(strategy_contract.get("generation_quality_contract") or {})
    if (
        int(generation_quality_contract.get("required_option_count") or 0) != FEEZIE_CODEX_DRAFT_OPTION_COUNT
        or int(generation_quality_contract.get("maximum_option_count") or 0) != FEEZIE_CODEX_DRAFT_OPTION_COUNT
        or int(generation_quality_contract.get("hook_variants_per_option") or 0) != FEEZIE_CODEX_HOOK_VARIANT_COUNT
        or generation_quality_contract.get("meaningful_difference_required") is not True
        or generation_quality_contract.get("independent_critic_required") is not True
    ):
        raise ValueError("The owner-approved FEEZIE generation quality contract is unavailable or inconsistent.")
    classification = _resolve_feezie_generation_classification(
        req=req,
        content_context=content_context,
        strategy=strategy_contract,
    )
    if classification["employer_safety"] == "blocked":
        raise ValueError("FEEZIE generation is blocked by the owner-approved employer-safety classification.")
    safe_topic = anonymize_feezie_public_text(req.topic, limit=320)
    distinct_thesis = (
        anonymize_feezie_public_text(req.source_card.distinct_thesis, limit=500)
        if req.source_card is not None and req.source_card.distinct_thesis
        else ""
    )
    local_primary_claims = _local_codex_primary_claims(
        topic=distinct_thesis or safe_topic,
        audience=req.audience,
        primary_claims=[
            value
            for value in (
                distinct_thesis,
                safe_topic,
                str(evidence_contract.get("exact_problem") or ""),
                str(evidence_contract.get("observable_lesson") or ""),
            )
            if value
        ],
    )
    # The owner-confirmed triplet is the only proof every draft may rely on. It is
    # already public-safe and prevents a ranked but unrelated reservoir item from
    # replacing the lived action/problem/lesson that admitted the request.
    local_proof_packets = [
        "Owner-confirmed implementation evidence -> "
        f"Action: {evidence_contract['concrete_action']} "
        f"Problem: {evidence_contract['exact_problem']}"
    ]
    local_story_beats = [str(evidence_contract["observable_lesson"])]
    effective_grounding_mode = "proof_ready"
    effective_grounding_reason = "Owner-confirmed public-safe action, problem, and observable lesson are present."
    if classification.get("proof_posture") in {None, "", "principle_only", "owner_confirmation_required", "missing"}:
        classification["proof_posture"] = "verified_public"
    public_request_context = _local_codex_request_context(req)
    _base_request_context, request_audience_consequence, request_why_now = (
        _partition_semantic_request_context(public_request_context)
    )
    audience_consequence = " ".join(
        str(classification.get("audience_consequence") or "").split()
    ).strip()
    if not audience_consequence:
        audience_consequence = request_audience_consequence
    decision_moment_basis = " ".join(
        str(
            classification.get("why_now")
            or request_why_now
            or classification.get("distinct_thesis")
            or safe_topic
        ).split()
    ).strip()
    briefs = plan_content_option_briefs(
        primary_claims=local_primary_claims,
        proof_packets=local_proof_packets,
        story_beats=local_story_beats,
        framing_modes=content_context.framing_modes,
        request_context=public_request_context,
        option_count=FEEZIE_CODEX_DRAFT_OPTION_COUNT,
    )
    _bind_publish_ready_evidence_to_briefs(
        briefs,
        evidence_contract,
        audience_consequence=audience_consequence,
        decision_moment_basis=decision_moment_basis,
        strategic_opening_basis=safe_topic,
    )
    student_scientist_enabled = _student_scientist_enabled(req=req, classification=classification)
    if student_scientist_enabled:
        for brief in briefs:
            brief.public_lane = "build_in_public"
    local_topic_anchor_chunks = _local_codex_safe_anchor_chunks(content_context.topic_anchor_chunks, limit=3)
    local_proof_anchor_chunks = _local_codex_safe_anchor_chunks(content_context.proof_anchor_chunks, limit=2)
    local_story_anchor_chunks = _local_codex_safe_anchor_chunks(content_context.story_anchor_chunks, limit=1)
    voice_directives = _extract_voice_directives(content_context.persona_chunks, limit=8)
    approved_references = _local_codex_approved_references(
        primary_claims=local_primary_claims,
        proof_packets=local_proof_packets,
        story_beats=local_story_beats,
    )
    prompt = build_local_codex_writer_prompt(
        topic=req.topic,
        context=public_request_context,
        audience=req.audience,
        grounding_mode=effective_grounding_mode,
        grounding_reason=effective_grounding_reason,
        topic_anchor_chunks=local_topic_anchor_chunks,
        proof_anchor_chunks=local_proof_anchor_chunks,
        story_anchor_chunks=local_story_anchor_chunks,
        briefs=briefs,
        voice_directives=voice_directives,
        approved_references=approved_references,
        intent=req.category,
        strategy_contract=strategy_contract,
        classification=classification,
        disallowed_moves=content_context.disallowed_moves,
    )
    prompt += f"""

PUBLISH-READY EVIDENCE CONTRACT:
- Contract: {evidence_contract['schema_version']}
- Concrete action: {evidence_contract['concrete_action']}
- Exact problem: {evidence_contract['exact_problem']}
- Observable lesson: {evidence_contract['observable_lesson']}
- Audience consequence: {audience_consequence or 'Not separately supplied; use only the exact-problem fallback.'}
- Decision moment: {decision_moment_basis}
- Author posture: {evidence_contract['author_posture']}

EVIDENCE-BINDING RULES:
- The evidence triplet is a factual ceiling, not one shared outline for both drafts. The assigned role decides where each supported fact belongs.
- The diagnosis draft uses the action as bounded proof, explains the exact observed problem, and lands on the observable lesson as recognition.
- The application draft leads with the supported gate, uses the action and problem only as decision context, records the lesson as a bounded learning observation, and lands on the decision boundary or concrete consequence rather than repeating the diagnosis payoff.
- Write as the person running and documenting a bounded experiment, not as an expert teaching a universal framework.
- Do not tell leaders, teams, builders, or the reader what they must, should, need to, or have to do.
- Do not use universal authority claims such as `always`, `never`, `everyone`, `the best`, or `the real systems`.
- Use exactly 3 or 4 short paragraphs and 85 to 150 words per draft.
- The closing paragraph must fulfill its assigned role and remain directly traceable to the evidence; an abstract maxim is not publishable.
- Do not invent a result, metric, person, employer, or causal outcome beyond this contract.
"""
    prompt += f"""

PORTFOLIO LEARNING CONTRACT:
- The JSON receipt below contains aggregate operating guidance, never public facts for the post.
- When learning_mode is collect_only, ignore outcome patterns; only the owner-approved mix and pilot deficits may guide treatment emphasis.
- When learning_mode is advisory_sequencing or strategy_review_eligible, use only the bounded aggregate tendencies to avoid repeated voice/quality failures. Do not claim that a pillar, hook, format, or treatment performed better in the post itself.
- This receipt cannot admit weak evidence, relax employer safety or proof rules, mutate the strategy contract, or bypass independent critic and owner approval.
- Never create filler merely to satisfy a mix deficit.

PORTFOLIO_LEARNING_RECEIPT_JSON
{json.dumps(portfolio_learning, ensure_ascii=True, sort_keys=True)}
"""
    prompt += """

FINAL RESPONSE CONTRACT:
- Replace the earlier delimiter-based output instruction.
- Do not use ---OPTION--- in the final answer.
- Return only JSON.
- Return an object with exactly one key: "options".
- "options" must be an array of exactly 2 complete post drafts.
- Each option must be a string.
- The two drafts must use meaningfully different thesis treatments, not cosmetic rewrites of one post.
- No markdown fences.
- No commentary outside the JSON object.
- Do not edit files or attempt to save anything locally.
"""
    # The bridge reconstructs writer and critic prompts from the typed remote-safe
    # fields below. Persisting the much larger locally assembled prompt would copy
    # persona excerpts, source previews, and private provenance into Railway even
    # though current FEEZIE execution never reads them.
    remote_projection = _feezie_remote_safe_context_projection(
        topic=safe_topic,
        audience=req.audience,
        intent=req.category,
        classification=classification,
        evidence_contract=evidence_contract,
        audience_consequence=audience_consequence,
        student_scientist_enabled=student_scientist_enabled,
    )
    return {
        **remote_projection,
        "workspace_slug": req.workspace_slug,
        "requested_model": codex_execution_profile["writer"]["model"],
        "codex_execution_profile": codex_execution_profile,
        "expected_option_count": FEEZIE_CODEX_DRAFT_OPTION_COUNT,
        "draft_contract": {
            "schema_version": FEEZIE_CODEX_DRAFT_CONTRACT_VERSION,
            "required_option_count": FEEZIE_CODEX_DRAFT_OPTION_COUNT,
            "maximum_option_count": FEEZIE_CODEX_DRAFT_OPTION_COUNT,
            "meaningful_difference_required": generation_quality_contract["meaningful_difference_required"],
            "independent_writer_calls_required": True,
            "writer_calls_per_option": 1,
            "independent_critic_required": generation_quality_contract["independent_critic_required"],
            "critic_reviews_per_option": 1,
            "hook_variants_per_option": generation_quality_contract["hook_variants_per_option"],
        },
        "revision_contract": {
            "schema_version": FEEZIE_REVISION_CONTRACT_VERSION,
            "enabled": True,
            "trigger": "non_ready_after_initial_blind_critic",
            "revision_calls_per_non_ready_option": 1,
            "model_retries_per_revision": 0,
            "preserve_ready_sibling_exactly": True,
            "fresh_blind_critic_required_after_revision": True,
        },
        "portfolio_learning": portfolio_learning,
        "intent": req.category,
        "strategy_contract": strategy_contract,
        "candidate_classification": classification,
        "grounding_mode": effective_grounding_mode,
        "grounding_reason": effective_grounding_reason,
        "primary_claims": local_primary_claims,
        "proof_packets": local_proof_packets,
        "story_beats": local_story_beats,
        "approved_references": approved_references,
        "planned_option_briefs": _serialize_content_option_briefs(briefs),
    }


def _feezie_remote_request_payload(
    req: LocalCodexJobCreateRequest,
    context_packet: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the closed request envelope persisted with a Railway FEEZIE job."""

    remote_context = (
        dict(context_packet.get("remote_execution_context") or {})
        if isinstance(context_packet.get("remote_execution_context"), dict)
        else {}
    )
    classification = (
        dict(context_packet.get("candidate_classification") or {})
        if isinstance(context_packet.get("candidate_classification"), dict)
        else {}
    )
    payload: Dict[str, Any] = {
        "packet_schema_version": FEEZIE_REMOTE_JOB_PACKET_VERSION,
        "workspace_slug": req.workspace_slug,
        "topic": str(remote_context.get("topic") or "").strip(),
        "content_type": req.content_type,
        "category": str(remote_context.get("intent") or req.category).strip(),
        "tone": str(remote_context.get("tone") or "direct_curiosity_evidence_led").strip(),
        "audience": str(remote_context.get("audience") or req.audience).strip(),
        "source_mode": req.source_mode,
        "canonical_pillar": str(classification.get("canonical_pillar") or "unclassified"),
        "career_signal": str(classification.get("career_signal") or "unclassified"),
        "employer_proximity": str(classification.get("employer_proximity") or "unclassified"),
        "employer_safety": str(classification.get("employer_safety") or "owner_review_required"),
        "proof_posture": str(classification.get("proof_posture") or "verified_public"),
    }
    treatment = str(classification.get("treatment") or "").strip()
    if treatment:
        payload["treatment"] = treatment
    source_card = _feezie_remote_source_card_projection(req.source_card)
    if source_card:
        payload["source_card"] = source_card
    return payload


def _assert_feezie_remote_job_payload_safe(value: Any) -> None:
    """Fail closed if a closed Railway job packet regains raw/private fields."""

    forbidden_keys = {
        "context",
        "evidence_answers",
        "source_path",
        "target_file",
        "provenance",
        "source_card_public_context",
        "persona_context_summary",
        "examples_used",
        "content_signal_support",
        "content_reservoir_support",
    }

    def validate(node: Any) -> None:
        if isinstance(node, dict):
            for raw_key, child in node.items():
                key = str(raw_key).strip().lower()
                exclusion_receipt = key.startswith("raw_") and key.endswith("_excluded") and child is True
                if key in forbidden_keys or (key.startswith("raw_") and not exclusion_receipt):
                    raise ValueError("FEEZIE remote job payload retained a raw or private field.")
                validate(child)
            return
        if isinstance(node, list):
            for child in node:
                validate(child)

    validate(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if re.search(
        r"(?:/Users|/home|/private|/tmp)/|[A-Za-z]:\\|"
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        encoded,
        flags=re.IGNORECASE,
    ):
        raise ValueError("FEEZIE remote job payload retained a private path or email address.")


def _persist_job_artifacts(job_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if content is None:
            continue
        stored.append(
            write_job_artifact(
                job_id=job_id,
                kind=str(item.get("kind") or "artifact"),
                label=str(item.get("label") or item.get("filename") or "artifact"),
                content=str(content),
                filename=str(item.get("filename") or f"{str(item.get('kind') or 'artifact')}.txt"),
                mime_type=str(item.get("mime_type") or "text/plain"),
            )
        )
    return stored


def queue_local_codex_job(req: LocalCodexJobCreateRequest) -> dict[str, Any]:
    cache_request_payload = _local_codex_cache_request_payload(req)
    cache_key, snapshot_hash = build_context_cache_key(
        workspace_slug=req.workspace_slug,
        request_payload=cache_request_payload,
    )
    cached = load_cached_context_packet(
        cache_key=cache_key,
        workspace_slug=req.workspace_slug,
        snapshot_hash=snapshot_hash,
        request_payload=cache_request_payload,
    )
    context_packet = cached.get("context_packet") if isinstance(cached, dict) else None
    cached_evidence = context_packet.get("evidence_contract") if isinstance(context_packet, dict) else None
    cached_remote_context = context_packet.get("remote_execution_context") if isinstance(context_packet, dict) else None
    cached_remote_policy = context_packet.get("remote_prompt_policy") if isinstance(context_packet, dict) else None
    cached_execution_profile = context_packet.get("codex_execution_profile") if isinstance(context_packet, dict) else None
    cached_briefs = context_packet.get("planned_option_briefs") if isinstance(context_packet, dict) else None
    cached_diagnosis = (
        cached_briefs[0]
        if isinstance(cached_briefs, list)
        and len(cached_briefs) == FEEZIE_CODEX_DRAFT_OPTION_COUNT
        and isinstance(cached_briefs[0], dict)
        else None
    )
    cache_hit = bool(
        isinstance(context_packet, dict)
        and context_packet.get("packet_schema_version") == FEEZIE_REMOTE_JOB_PACKET_VERSION
        and isinstance(cached_evidence, dict)
        and cached_evidence.get("schema_version") == EVIDENCE_CONTRACT_VERSION
        and all(str(cached_evidence.get(key) or "").strip() for key in EVIDENCE_KEYS)
        and isinstance(cached_remote_context, dict)
        and cached_remote_context.get("schema_version") == FEEZIE_REMOTE_EXECUTION_CONTEXT_VERSION
        and isinstance(cached_remote_policy, dict)
        and cached_remote_policy.get("schema_version") == FEEZIE_REMOTE_PROMPT_POLICY_VERSION
        and cached_execution_profile == _feezie_codex_execution_profile()
        and isinstance(cached_diagnosis, dict)
        and " ".join(str(cached_diagnosis.get("primary_claim") or "").split()).strip()
        == " ".join(str(cached_remote_context.get("topic") or "").split()).strip()
        and " ".join(str(cached_diagnosis.get("mechanism_focus") or "").split()).strip()
        == " ".join(str(cached_evidence.get("exact_problem") or "").split()).strip()
    )
    if not cache_hit:
        content_context: ContentGenerationContext = build_content_generation_context(
            user_id=req.user_id,
            topic=req.topic,
            context=_local_codex_request_context(req) or None,
            content_type=req.content_type,
            category=req.category,
            tone=req.tone,
            audience=req.audience,
            source_mode=req.source_mode,
        )
        evidence_readiness = _feezie_evidence_readiness(req=req, content_context=content_context)
        if evidence_readiness.get("status") == "blocked":
            return {
                "id": None,
                "status": "blocked",
                "evidence_readiness": _evidence_readiness_response_projection(evidence_readiness),
            }
        if evidence_readiness.get("ready") is not True:
            return {
                "id": None,
                "status": "clarification_required",
                "evidence_readiness": _evidence_readiness_response_projection(evidence_readiness),
            }
        context_packet = _build_local_codex_context_packet(
            req=req,
            content_context=content_context,
            evidence_contract=dict(evidence_readiness.get("contract") or {}),
        )
        _assert_feezie_remote_job_payload_safe(context_packet)
        write_cached_context_packet(
            cache_key=cache_key,
            workspace_slug=req.workspace_slug,
            snapshot_hash=snapshot_hash,
            request_payload=cache_request_payload,
            context_packet=context_packet,
        )
    if not isinstance(context_packet, dict):
        raise RuntimeError("Unable to build local Codex context packet.")
    context_packet = dict(context_packet)
    context_packet["cache_key"] = cache_key
    context_packet["snapshot_hash"] = snapshot_hash
    context_packet["cache_hit"] = cache_hit
    request_payload = _feezie_remote_request_payload(req, context_packet)
    _assert_feezie_remote_job_payload_safe(request_payload)
    _assert_feezie_remote_job_payload_safe(context_packet)
    job = create_codex_job(
        workspace_slug=req.workspace_slug,
        requested_by="owner",
        request_payload=request_payload,
        context_packet=context_packet,
        idempotency_key=_build_local_codex_idempotency_key(req, context_cache_key=cache_key),
    )
    artifacts = _persist_job_artifacts(
        str(job.get("id") or ""),
        [
            {
                "kind": "context_packet",
                "label": "context-packet.json",
                "filename": "context-packet.json",
                "mime_type": "application/json",
                "content": json.dumps(context_packet, indent=2) + "\n",
            },
            {
                "kind": "request_payload",
                "label": "request-payload.json",
                "filename": "request-payload.json",
                "mime_type": "application/json",
                "content": json.dumps(request_payload, indent=2) + "\n",
            },
        ],
    )
    if artifacts:
        job = append_job_artifacts(job_id=str(job.get("id") or ""), artifacts=artifacts)
    return job


def _build_local_codex_result_payload(
    *,
    job: Dict[str, Any],
    options: List[str],
    model: str | None,
    raw_output: str | None,
    command_stdout: str | None,
    command_stderr: str | None,
) -> Dict[str, Any]:
    request_payload = job.get("request_payload") if isinstance(job.get("request_payload"), dict) else {}
    packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    draft_contract = packet.get("draft_contract") if isinstance(packet.get("draft_contract"), dict) else {}
    is_feezie_contract = (
        str(draft_contract.get("schema_version") or "").strip()
        == FEEZIE_CODEX_DRAFT_CONTRACT_VERSION
    )
    briefs = _deserialize_content_option_briefs(packet.get("planned_option_briefs"))
    trimmed_options = [option.strip() for option in options if isinstance(option, str) and option.strip()][:3]
    if briefs:
        trimmed_options = finalize_planned_options(
            options=trimmed_options,
            briefs=briefs,
            grounding_mode=str(packet.get("grounding_mode") or "principle_only"),
        )
        approved_reference_terms = list(packet.get("approved_references") or [])
        audience = str(request_payload.get("audience") or "")
        trimmed_options = [
            _drop_unapproved_reference_sentences(
                _sanitize_public_output(
                    option,
                    briefs[index] if index < len(briefs) else briefs[-1],
                ),
                brief=briefs[index] if index < len(briefs) else briefs[-1],
                approved_reference_terms=approved_reference_terms,
                audience=audience,
            )
            for index, option in enumerate(trimmed_options)
        ]
        taste_scores = [
            score_option_taste(
                option,
                brief=briefs[index] if index < len(briefs) else None,
                primary_claims=list(packet.get("primary_claims") or []),
                proof_packets=list(packet.get("proof_packets") or []),
                story_beats=list(packet.get("story_beats") or []),
                grounding_mode=str(packet.get("grounding_mode") or "principle_only"),
            )
            for index, option in enumerate(trimmed_options)
        ]
        trimmed_options, briefs, taste_scores = _rank_options_by_taste(
            options=trimmed_options,
            briefs=briefs,
            taste_scores=taste_scores,
            topic=str(request_payload.get("topic") or ""),
            audience=str(request_payload.get("audience") or ""),
        )
        trimmed_options, taste_scores = _repair_weak_ranked_options(
            options=trimmed_options,
            briefs=briefs,
            taste_scores=taste_scores,
            topic=str(request_payload.get("topic") or ""),
            audience=str(request_payload.get("audience") or ""),
            grounding_mode=str(packet.get("grounding_mode") or "principle_only"),
            primary_claims=list(packet.get("primary_claims") or []),
            proof_packets=list(packet.get("proof_packets") or []),
            story_beats=list(packet.get("story_beats") or []),
            approved_reference_terms=approved_reference_terms,
        )
        trimmed_options, briefs, taste_scores = _rank_options_by_taste(
            options=trimmed_options,
            briefs=briefs,
            taste_scores=taste_scores,
            topic=str(request_payload.get("topic") or ""),
            audience=str(request_payload.get("audience") or ""),
        )
    else:
        taste_scores = []
    return {
        "success": True,
        "options": trimmed_options,
        "persona_context": packet.get("persona_context_summary"),
        "examples_used": list(packet.get("examples_used") or []),
        "diagnostics": {
            "grounding_mode": packet.get("grounding_mode"),
            "generation_strategy": "codex_terminal",
            "primary_claims": list(packet.get("primary_claims") or []),
            "proof_packets": list(packet.get("proof_packets") or []),
            "approved_references": list(packet.get("approved_references") or []),
            "voice_directives": list(packet.get("voice_directives") or []),
            "planned_option_briefs": _serialize_content_option_briefs(briefs),
            "taste_scores": taste_scores,
            "topic_anchor_preview": list(packet.get("topic_anchor_preview") or []),
            "core_chunk_preview": list(packet.get("core_chunk_preview") or []),
            "proof_anchor_preview": list(packet.get("proof_anchor_preview") or []),
            "content_signal_source": packet.get("content_signal_source") or "persona_only",
            "content_signal_preview": list(packet.get("content_signal_preview") or packet.get("content_reservoir_preview") or []),
            "content_signal_count": int(packet.get("content_signal_count") or packet.get("content_reservoir_count") or 0),
            "content_signal_support": list(packet.get("content_signal_support") or packet.get("content_reservoir_support") or []),
            "content_reservoir_preview": list(packet.get("content_reservoir_preview") or packet.get("content_signal_preview") or []),
            "content_reservoir_count": int(packet.get("content_reservoir_count") or packet.get("content_signal_count") or 0),
            "content_reservoir_support": list(packet.get("content_reservoir_support") or packet.get("content_signal_support") or []),
            "llm_provider_trace": [
                {
                    "provider": "codex_terminal",
                    "actual_model": model or str(packet.get("requested_model") or "gpt-5.4-mini"),
                    "status": "success",
                }
            ],
            "source_mode": request_payload.get("source_mode"),
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


def _feezie_draft_contract(job: Dict[str, Any]) -> Dict[str, Any]:
    packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    contract = packet.get("draft_contract")
    if not isinstance(contract, dict):
        return {}
    if str(contract.get("schema_version") or "") != FEEZIE_CODEX_DRAFT_CONTRACT_VERSION:
        return {}
    return dict(contract)


def _feezie_revision_contract(job: Dict[str, Any]) -> Dict[str, Any]:
    packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    contract = packet.get("revision_contract")
    if contract is None:
        return {}
    if not isinstance(contract, dict):
        raise ValueError("The FEEZIE revision contract is malformed.")
    expected = {
        "schema_version": FEEZIE_REVISION_CONTRACT_VERSION,
        "enabled": True,
        "trigger": "non_ready_after_initial_blind_critic",
        "revision_calls_per_non_ready_option": 1,
        "model_retries_per_revision": 0,
        "preserve_ready_sibling_exactly": True,
        "fresh_blind_critic_required_after_revision": True,
    }
    if contract != expected:
        raise ValueError("The FEEZIE revision contract is unsupported or inconsistent.")
    return dict(contract)


def _feezie_content_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").strip().encode("utf-8")).hexdigest()


def _feezie_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _valid_feezie_sha256(value: Any, *, allow_empty: bool = False) -> bool:
    cleaned = str(value or "").strip().lower()
    if allow_empty and not cleaned:
        return True
    return re.fullmatch(r"[a-f0-9]{64}", cleaned) is not None


def _feezie_pair_sha256(option_hashes: List[str]) -> str:
    return hashlib.sha256(
        json.dumps(
            option_hashes,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _validate_feezie_voice_contamination_receipt(
    receipt: Any,
    *,
    options: List[str],
    required: bool,
) -> Dict[str, Any] | None:
    """Admit only the bounded no-copy receipt that the server cannot recompute."""

    if receipt is None and not required:
        return None
    if not isinstance(receipt, dict):
        raise ValueError("FEEZIE completion requires a bounded voice-contamination receipt.")
    allowed_keys = {
        "schema_version",
        "passed",
        "exemplar_count",
        "evaluated_option_count",
        "blocked_option_count",
        "blocker_codes",
        "pair_sha256",
        "option_results",
        "contains_exemplar_text",
    }
    if set(receipt) != allowed_keys:
        raise ValueError("The FEEZIE voice-contamination receipt is unbounded or incomplete.")
    if receipt.get("schema_version") != FEEZIE_VOICE_CONTAMINATION_RECEIPT_VERSION:
        raise ValueError("The FEEZIE voice-contamination receipt has an unsupported schema.")
    if not isinstance(receipt.get("passed"), bool) or receipt.get("contains_exemplar_text") is not False:
        raise ValueError("The FEEZIE voice-contamination receipt violates its no-copy contract.")

    def bounded_int(name: str, *, maximum: int) -> int:
        value = receipt.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
            raise ValueError(f"The FEEZIE voice-contamination receipt has an invalid {name}.")
        return value

    expected_option_hashes = [_feezie_content_sha256(option) for option in options]
    expected_option_count = len(expected_option_hashes)
    pair_sha = str(receipt.get("pair_sha256") or "").strip().lower()
    if not _valid_feezie_sha256(pair_sha) or pair_sha != _feezie_pair_sha256(expected_option_hashes):
        raise ValueError(
            "The FEEZIE voice-contamination receipt is not bound to the exact final draft pair."
        )

    bounded_int("exemplar_count", maximum=64)
    evaluated_count = bounded_int("evaluated_option_count", maximum=FEEZIE_CODEX_DRAFT_OPTION_COUNT)
    blocked_count = bounded_int("blocked_option_count", maximum=FEEZIE_CODEX_DRAFT_OPTION_COUNT)
    if evaluated_count != expected_option_count:
        raise ValueError("The FEEZIE voice-contamination receipt does not cover the final draft pair.")

    def bounded_codes(value: Any) -> List[str]:
        if (
            not isinstance(value, list)
            or len(value) > 32
            or any(
                not isinstance(item, str)
                or re.fullmatch(r"[a-z0-9_:-]{1,160}", item.strip().lower()) is None
                for item in value
            )
        ):
            raise ValueError("The FEEZIE voice-contamination receipt has invalid blocker codes.")
        normalized = [item.strip().lower() for item in value]
        if normalized != sorted(set(normalized)):
            raise ValueError("The FEEZIE voice-contamination blocker codes are not canonical.")
        return normalized

    top_codes = bounded_codes(receipt.get("blocker_codes"))
    raw_results = receipt.get("option_results")
    if not isinstance(raw_results, list) or len(raw_results) != expected_option_count:
        raise ValueError("The FEEZIE voice-contamination receipt has invalid option coverage.")
    all_finding_codes: set[str] = set()
    observed_blocked_count = 0
    seen_indices: set[int] = set()
    for expected_index, raw_result in enumerate(raw_results, start=1):
        if not isinstance(raw_result, dict) or set(raw_result) != {
            "option_index",
            "option_sha256",
            "passed",
            "blocker_codes",
            "findings",
        }:
            raise ValueError("The FEEZIE voice-contamination receipt contains an invalid option row.")
        option_index = raw_result.get("option_index")
        if (
            isinstance(option_index, bool)
            or not isinstance(option_index, int)
            or option_index != expected_index
            or option_index in seen_indices
        ):
            raise ValueError("The FEEZIE voice-contamination option order is invalid.")
        seen_indices.add(option_index)
        option_sha = str(raw_result.get("option_sha256") or "").strip().lower()
        if (
            not _valid_feezie_sha256(option_sha)
            or option_sha != expected_option_hashes[expected_index - 1]
        ):
            raise ValueError(
                "The FEEZIE voice-contamination receipt is not bound to the exact final option bytes."
            )
        if not isinstance(raw_result.get("passed"), bool):
            raise ValueError("The FEEZIE voice-contamination option verdict is invalid.")
        row_codes = bounded_codes(raw_result.get("blocker_codes"))
        findings = raw_result.get("findings")
        if not isinstance(findings, list) or len(findings) > 32:
            raise ValueError("The FEEZIE voice-contamination findings exceed their bound.")
        finding_codes: set[str] = set()
        finding_identities: set[tuple[str, str, str]] = set()
        for finding in findings:
            if not isinstance(finding, dict) or set(finding) not in (
                {"code", "reference_id_sha256", "match_sha256"},
                {"code", "reference_id_sha256", "match_sha256", "matched_token_count"},
            ):
                raise ValueError("The FEEZIE voice-contamination finding is unbounded.")
            code = str(finding.get("code") or "").strip().lower()
            reference_sha = str(finding.get("reference_id_sha256") or "").strip().lower()
            match_sha = str(finding.get("match_sha256") or "").strip().lower()
            if (
                re.fullmatch(r"[a-z0-9_:-]{1,160}", code) is None
                or not _valid_feezie_sha256(reference_sha)
                or not _valid_feezie_sha256(match_sha)
            ):
                raise ValueError("The FEEZIE voice-contamination finding has an invalid commitment.")
            if "matched_token_count" in finding:
                token_count = finding.get("matched_token_count")
                if isinstance(token_count, bool) or not isinstance(token_count, int) or not 1 <= token_count <= 500:
                    raise ValueError("The FEEZIE voice-contamination token count is invalid.")
            identity = (code, reference_sha, match_sha)
            if identity in finding_identities:
                raise ValueError("The FEEZIE voice-contamination finding is duplicated.")
            finding_identities.add(identity)
            finding_codes.add(code)
        if row_codes != sorted(finding_codes) or raw_result.get("passed") is not (not findings):
            raise ValueError("The FEEZIE voice-contamination option receipt is internally inconsistent.")
        if findings:
            observed_blocked_count += 1
        all_finding_codes.update(finding_codes)

    if (
        blocked_count != observed_blocked_count
        or top_codes != sorted(all_finding_codes)
        or receipt.get("passed") is not (observed_blocked_count == 0)
    ):
        raise ValueError("The FEEZIE voice-contamination aggregate receipt is internally inconsistent.")
    return json.loads(json.dumps(receipt, ensure_ascii=True))


def _merge_feezie_voice_contamination_gate(
    quality_gate: Dict[str, Any],
    contamination_gate: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Reproduce the bounded local merge while retaining server quality authority."""

    merged = json.loads(json.dumps(quality_gate, ensure_ascii=True))
    if contamination_gate is None:
        return merged
    merged["voice_exemplar_contamination"] = contamination_gate
    if contamination_gate.get("passed") is True:
        return merged
    merged["passed"] = False
    failed_reasons = [str(item) for item in (merged.get("failed_reasons") or []) if str(item)]
    contamination_reasons: List[str] = []
    for code in contamination_gate.get("blocker_codes") or []:
        reason = f"voice_exemplar_contamination:{code}"
        contamination_reasons.append(reason)
        if reason not in failed_reasons:
            failed_reasons.append(reason)
    shared_constraints = (
        dict(merged.get("shared_constraints"))
        if isinstance(merged.get("shared_constraints"), dict)
        else {}
    )
    shared_failures = [
        str(item)
        for item in (shared_constraints.get("failed_reasons") or [])
        if str(item)
    ]
    for reason in contamination_reasons or ["voice_exemplar_contamination:unknown"]:
        if reason not in shared_failures:
            shared_failures.append(reason)
        if reason not in failed_reasons:
            failed_reasons.append(reason)
    shared_constraints["passed"] = False
    shared_constraints["failed_reasons"] = shared_failures
    merged["shared_constraints"] = shared_constraints
    merged["selection_admission_passed"] = False
    merged["failed_reasons"] = failed_reasons
    return merged


def _canonical_feezie_quality_gate(
    *,
    context_packet: Dict[str, Any],
    options: List[str],
    submitted_quality_gate: Any,
    require_contamination: bool,
    compare_full_receipt: bool,
) -> Dict[str, Any]:
    """Recompute the current server gate and reject worker/server contract drift."""

    if not isinstance(submitted_quality_gate, dict):
        raise ValueError("FEEZIE completion requires the explicit deterministic quality-gate v2 receipt.")
    if str(submitted_quality_gate.get("schema_version") or "") != FEEZIE_DETERMINISTIC_QUALITY_GATE_VERSION:
        raise ValueError("FEEZIE completion requires the explicit deterministic quality-gate v2 receipt.")
    # Imported lazily because the local execution service intentionally imports
    # this route module for established public-copy helpers.
    from app.services.local_content_generation_execution_service import evaluate_local_quality

    server_gate = evaluate_local_quality(context_packet, options)
    contamination = _validate_feezie_voice_contamination_receipt(
        submitted_quality_gate.get("voice_exemplar_contamination"),
        options=options,
        required=require_contamination,
    )
    canonical = _merge_feezie_voice_contamination_gate(server_gate, contamination)
    submitted = json.loads(json.dumps(submitted_quality_gate, ensure_ascii=True))
    expected = canonical if compare_full_receipt else _project_feezie_quality_gate(canonical)
    if submitted != expected:
        raise ValueError(
            "The FEEZIE deterministic quality-gate receipt is stale or does not match the current server validator."
        )
    return canonical


def _feezie_expected_blind_critic_plan(
    *,
    job_scope: str,
    options: List[str],
) -> Dict[str, Any]:
    """Reconstruct the worker's opaque IDs from the exact final draft bytes."""

    scope = str(job_scope or "").strip()
    if not scope:
        raise ValueError("The independent critic receipt is missing its durable job scope.")
    entries: List[Dict[str, Any]] = []
    for canonical_index, option in enumerate(options, start=1):
        option_sha = _feezie_content_sha256(option)
        critic_option_id = "draft_" + hashlib.sha256(
            (
                f"feezie-critic-option/v1\0{scope}\0{canonical_index}\0"
                f"{option_sha}"
            ).encode("utf-8")
        ).hexdigest()[:16]
        shuffle_key = hashlib.sha256(
            f"feezie-critic-order/v1\0{scope}\0{critic_option_id}".encode("utf-8")
        ).hexdigest()
        entries.append(
            {
                "critic_option_id": critic_option_id,
                "canonical_option_index": canonical_index,
                "shuffle_key": shuffle_key,
            }
        )
    critic_order = sorted(entries, key=lambda entry: str(entry["shuffle_key"]))
    canonical_order = [int(entry["canonical_option_index"]) for entry in critic_order]
    identity_order = list(range(1, len(entries) + 1))
    if len(entries) > 1 and canonical_order == identity_order:
        rotation_seed = hashlib.sha256(
            f"feezie-critic-rotation/v1\0{scope}".encode("utf-8")
        ).hexdigest()
        offset = 1 + (int(rotation_seed, 16) % (len(entries) - 1))
        critic_order = critic_order[offset:] + critic_order[:offset]
    mapping_rows = [
        {
            "critic_option_id": str(entry["critic_option_id"]),
            "canonical_option_index": int(entry["canonical_option_index"]),
        }
        for entry in critic_order
    ]
    return {
        "job_scope_sha256": hashlib.sha256(scope.encode("utf-8")).hexdigest(),
        "critic_order": mapping_rows,
        "option_id_to_index": {
            str(entry["critic_option_id"]): int(entry["canonical_option_index"])
            for entry in entries
        },
    }


def _feezie_final_critic_job_scope(
    *,
    job: Dict[str, Any],
    revision_receipt: Any,
) -> str:
    """Infer whether the returned critic reviewed initial or revised final bytes."""

    job_id = str(job.get("id") or "").strip()
    revision_contract = _feezie_revision_contract(job)
    if not revision_contract:
        return job_id
    if not job_id:
        raise ValueError("The revision-enabled FEEZIE critic receipt is missing its durable job identity.")
    if (
        not isinstance(revision_receipt, dict)
        or revision_receipt.get("schema_version") != FEEZIE_REVISION_RECEIPT_VERSION
    ):
        raise ValueError("FEEZIE completion requires a revision execution receipt.")
    status = str(revision_receipt.get("status") or "").strip().lower()
    if status == "completed":
        return f"{job_id}:final"
    if status in {"not_required", "failed"}:
        return f"{job_id}:initial"
    raise ValueError("The FEEZIE revision execution receipt has an invalid status.")


def _build_feezie_editorial_readiness(
    *,
    critic_review: Dict[str, Any],
    deterministic_quality_gate: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the sole server-authoritative readiness view from bounded evidence."""

    contamination_gate = (
        deterministic_quality_gate.get("voice_exemplar_contamination")
        if isinstance(deterministic_quality_gate.get("voice_exemplar_contamination"), dict)
        else None
    )
    contamination_passed = contamination_gate is None or contamination_gate.get("passed") is True
    contamination_results = {
        int(item.get("option_index") or 0): item
        for item in ((contamination_gate or {}).get("option_results") or [])
        if isinstance(item, dict) and int(item.get("option_index") or 0) > 0
    }
    option_results = {
        int(item.get("option_index") or 0): item
        for item in (deterministic_quality_gate.get("option_results") or [])
        if isinstance(item, dict) and int(item.get("option_index") or 0) > 0
    }
    shared_constraints = (
        deterministic_quality_gate.get("shared_constraints")
        if isinstance(deterministic_quality_gate.get("shared_constraints"), dict)
        else {}
    )
    shared_constraints_passed = shared_constraints.get("passed") is True
    selection_admission_passed = deterministic_quality_gate.get("selection_admission_passed") is True
    batch_all_options_passed = deterministic_quality_gate.get("passed") is True
    critic_status = str(critic_review.get("status") or "unavailable").strip().lower()
    if critic_status != "completed":
        return {
            "ready": False,
            "status": "critic_unavailable" if critic_status == "unavailable" else "critic_not_run",
            "critic_status": critic_status,
            "ready_score_threshold": FEEZIE_CRITIC_READY_SCORE,
            "quality_gate_schema_version": FEEZIE_DETERMINISTIC_QUALITY_GATE_VERSION,
            "deterministic_quality_receipt_valid": True,
            "deterministic_quality_gate_passed": selection_admission_passed and contamination_passed,
            "batch_all_options_quality_passed": batch_all_options_passed,
            "shared_constraints_passed": shared_constraints_passed,
            "selection_admission_passed": selection_admission_passed,
            "voice_exemplar_contamination_passed": contamination_passed,
            "semantic_distinctness_passed": False,
            "pair_attribution_valid": False,
            "pair_affected_option_indices": [],
            "draft_distinctness": {},
            "option_local_ready_count": 0,
            "ready_option_count": 0,
            "option_reviews": [],
            "blocking_reasons": [
                str(critic_review.get("reason") or "independent_critic_not_completed")
            ],
        }

    semantic_distinctness = (
        critic_review.get("draft_distinctness")
        if isinstance(critic_review.get("draft_distinctness"), dict)
        else {}
    )
    semantic_distinctness_passed = semantic_distinctness.get("passed") is True
    critic_reviews = [
        item
        for item in (critic_review.get("reviews") or [])
        if isinstance(item, dict)
    ]
    expected_non_ready_indices = sorted(
        int(item.get("option_index") or 0)
        for item in critic_reviews
        if int(item.get("option_index") or 0) > 0
        and str(item.get("verdict") or "").strip().lower() != "ready"
    )
    raw_affected_indices = semantic_distinctness.get("affected_option_indices", [])
    affected_indices_well_formed = bool(
        isinstance(raw_affected_indices, list)
        and all(
            not isinstance(index, bool) and isinstance(index, int) and index > 0
            for index in raw_affected_indices
        )
        and len(set(raw_affected_indices)) == len(raw_affected_indices)
    )
    pair_affected_option_indices = (
        sorted(raw_affected_indices) if affected_indices_well_formed else []
    )
    pair_attribution_valid = bool(
        affected_indices_well_formed
        and (
            (semantic_distinctness_passed and not pair_affected_option_indices)
            or (
                not semantic_distinctness_passed
                and bool(pair_affected_option_indices)
                and pair_affected_option_indices == expected_non_ready_indices
            )
        )
    )
    shared_failures = [
        str(reason)
        for reason in (shared_constraints.get("failed_reasons") or [])
        if str(reason)
    ]
    enriched_reviews: List[Dict[str, Any]] = []
    for review in critic_reviews:
        option_index = int(review.get("option_index") or 0)
        dimensions = review.get("dimension_scores") if isinstance(review.get("dimension_scores"), dict) else {}
        deterministic_result = option_results.get(option_index) or {}
        contamination_result = contamination_results.get(option_index) or {}
        deterministic_blockers = list(
            dict.fromkeys(
                [
                    str(reason)
                    for reason in (deterministic_result.get("failed_reasons") or [])
                    if str(reason)
                ]
                + shared_failures
                + [
                    str(code)
                    for code in (contamination_result.get("blocker_codes") or [])
                    if str(code)
                ]
            )
        )
        deterministic_option_passed = (
            shared_constraints_passed
            and deterministic_result.get("passed") is True
            and contamination_passed
            and not deterministic_blockers
        )
        unresolved_issues = [
            str(issue)
            for issue in (review.get("issues") or [])
            if str(issue).strip()
        ]
        option_local_ready = (
            str(review.get("verdict") or "").strip().lower() == "ready"
            and int(review.get("score") or 0) >= FEEZIE_CRITIC_READY_SCORE
            and int(dimensions.get("truth") or 0) >= FEEZIE_CRITIC_READY_SCORE
            and int(dimensions.get("safety") or 0) >= FEEZIE_CRITIC_READY_SCORE
            and all(int(dimensions.get(name) or 0) >= 7 for name in ("intent", "voice", "hook"))
            and not unresolved_issues
            and deterministic_option_passed
        )
        pair_admission_passed = bool(
            pair_attribution_valid
            and (
                semantic_distinctness_passed
                or option_index not in pair_affected_option_indices
            )
        )
        option_ready = option_local_ready and pair_admission_passed
        enriched_reviews.append(
            {
                **review,
                "option_local_ready": option_local_ready,
                "pair_admission_passed": pair_admission_passed,
                "editorially_ready": option_ready,
                "deterministic_quality_passed": deterministic_option_passed,
                "deterministic_score": deterministic_result.get("score"),
                "deterministic_threshold": deterministic_result.get("threshold"),
                "deterministic_blocked": not deterministic_option_passed,
                "deterministic_blocking_reasons": deterministic_blockers,
            }
        )
    option_local_ready_count = sum(
        1 for review in enriched_reviews if review.get("option_local_ready") is True
    )
    ready_option_count = sum(1 for review in enriched_reviews if review.get("editorially_ready") is True)
    deterministic_gate_passed = selection_admission_passed and contamination_passed
    ready = (
        deterministic_gate_passed
        and shared_constraints_passed
        and pair_attribution_valid
        and semantic_distinctness_passed
        and ready_option_count > 0
    )
    all_blocked = bool(enriched_reviews) and all(
        str(review.get("verdict") or "").strip().lower() == "blocked"
        for review in enriched_reviews
    )
    blocking_reasons: List[str] = []
    if not deterministic_gate_passed:
        blocking_reasons.append("deterministic_quality_gate_failed")
    if not shared_constraints_passed:
        blocking_reasons.append("deterministic_shared_constraints_failed")
    if not contamination_passed:
        blocking_reasons.append("voice_exemplar_contamination_detected")
    if not semantic_distinctness_passed:
        blocking_reasons.append("critic_found_drafts_not_meaningfully_different")
    if not pair_attribution_valid:
        blocking_reasons.append("critic_pair_attribution_malformed")
    if ready_option_count == 0:
        blocking_reasons.append("critic_found_no_ready_option")
    return {
        "ready": ready,
        "status": "ready" if ready else ("blocked" if all_blocked or not contamination_passed else "revision_required"),
        "critic_status": critic_status,
        "ready_score_threshold": FEEZIE_CRITIC_READY_SCORE,
        "quality_gate_schema_version": FEEZIE_DETERMINISTIC_QUALITY_GATE_VERSION,
        "deterministic_quality_receipt_valid": True,
        "deterministic_quality_gate_passed": deterministic_gate_passed,
        "batch_all_options_quality_passed": batch_all_options_passed,
        "shared_constraints_passed": shared_constraints_passed,
        "selection_admission_passed": selection_admission_passed,
        "voice_exemplar_contamination_passed": contamination_passed,
        "semantic_distinctness_passed": semantic_distinctness_passed,
        "pair_attribution_valid": pair_attribution_valid,
        "pair_affected_option_indices": pair_affected_option_indices,
        "draft_distinctness": semantic_distinctness,
        "option_local_ready_count": option_local_ready_count,
        "ready_option_count": ready_option_count,
        "option_reviews": enriched_reviews,
        "blocking_reasons": blocking_reasons,
    }


def _validate_feezie_revision_execution_receipt(
    *,
    receipt: Any,
    final_options: List[str],
    critic_review: Dict[str, Any],
    readiness: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate bounded revision topology without admitting draft or issue copy."""

    if not isinstance(receipt, dict):
        raise ValueError("FEEZIE completion requires a revision execution receipt.")
    allowed_keys = {
        "schema_version",
        "status",
        "failure_code",
        "canonical_order_preserved",
        "retry_allowed",
        "initial_critic_call_count",
        "initial_critic_status",
        "initial_critic_reason",
        "revision_call_count",
        "final_critic_call_count",
        "final_critic_status",
        "final_critic_reason",
        "original_pair_sha256",
        "final_pair_sha256",
        "initial_critic_receipt_sha256",
        "final_critic_receipt_sha256",
        "options",
        "contains_post_copy",
        "contains_critic_issue_copy",
    }
    if set(receipt) != allowed_keys:
        raise ValueError("The FEEZIE revision execution receipt is unbounded or incomplete.")
    if receipt.get("schema_version") != FEEZIE_REVISION_RECEIPT_VERSION:
        raise ValueError("The FEEZIE revision execution receipt has an unsupported schema.")
    status = str(receipt.get("status") or "").strip().lower()
    if status not in {"not_required", "completed", "failed"}:
        raise ValueError("The FEEZIE revision execution receipt has an invalid status.")
    if (
        receipt.get("canonical_order_preserved") is not True
        or receipt.get("retry_allowed") is not False
        or receipt.get("contains_post_copy") is not False
        or receipt.get("contains_critic_issue_copy") is not False
    ):
        raise ValueError("The FEEZIE revision execution receipt violates its safety contract.")

    def bounded_count(name: str, *, maximum: int) -> int:
        value = receipt.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
            raise ValueError(f"The FEEZIE revision receipt has an invalid {name}.")
        return value

    initial_critic_calls = bounded_count("initial_critic_call_count", maximum=1)
    revision_calls = bounded_count("revision_call_count", maximum=FEEZIE_CODEX_DRAFT_OPTION_COUNT)
    final_critic_calls = bounded_count("final_critic_call_count", maximum=1)
    if initial_critic_calls != 1:
        raise ValueError("The FEEZIE revision receipt must record exactly one initial critic attempt.")
    initial_critic_status = str(receipt.get("initial_critic_status") or "").strip().lower()
    final_critic_status = str(receipt.get("final_critic_status") or "").strip().lower()
    if initial_critic_status not in {"completed", "unavailable", "not_run"}:
        raise ValueError("The FEEZIE revision receipt has an invalid initial critic status.")
    if final_critic_status not in {"completed", "unavailable", "not_run"}:
        raise ValueError("The FEEZIE revision receipt has an invalid final critic status.")
    for reason_key in ("initial_critic_reason", "final_critic_reason"):
        reason_value = str(receipt.get(reason_key) or "").strip()
        if len(reason_value) > 160 or (
            reason_value and re.fullmatch(r"[a-z0-9_:-]{1,160}", reason_value) is None
        ):
            raise ValueError("The FEEZIE revision receipt has an invalid critic reason code.")

    failure_code = str(receipt.get("failure_code") or "").strip().lower()
    if failure_code and re.fullmatch(r"[a-z0-9_:-]{1,96}", failure_code) is None:
        raise ValueError("The FEEZIE revision receipt has an invalid failure code.")
    if status == "failed":
        if not failure_code or readiness.get("ready") is True:
            raise ValueError("A failed FEEZIE revision receipt must fail editorial readiness closed.")
    elif failure_code:
        raise ValueError("A successful FEEZIE revision receipt cannot carry a failure code.")

    original_pair_sha = str(receipt.get("original_pair_sha256") or "").strip().lower()
    final_pair_sha = str(receipt.get("final_pair_sha256") or "").strip().lower()
    initial_critic_sha = str(receipt.get("initial_critic_receipt_sha256") or "").strip().lower()
    final_critic_sha = str(receipt.get("final_critic_receipt_sha256") or "").strip().lower()
    if not _valid_feezie_sha256(original_pair_sha) or not _valid_feezie_sha256(final_pair_sha):
        raise ValueError("The FEEZIE revision receipt has an invalid pair commitment.")

    if len(final_options) != FEEZIE_CODEX_DRAFT_OPTION_COUNT:
        raise ValueError("The FEEZIE revision receipt requires exactly two final options.")
    raw_rows = receipt.get("options")
    if not isinstance(raw_rows, list) or len(raw_rows) != FEEZIE_CODEX_DRAFT_OPTION_COUNT:
        raise ValueError("The FEEZIE revision receipt must cover exactly two canonical options.")
    row_keys = {
        "canonical_option_index",
        "action",
        "attempt_count",
        "original_post_sha256",
        "final_post_sha256",
        "revision_prompt_sha256",
        "bounded_findings_sha256",
        "role_contract_sha256",
        "attempt_output_sha256",
        "changed",
        "error_code",
    }
    rows: Dict[int, Dict[str, Any]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict) or set(raw_row) != row_keys:
            raise ValueError("The FEEZIE revision receipt contains an invalid option row.")
        option_index = raw_row.get("canonical_option_index")
        if (
            isinstance(option_index, bool)
            or not isinstance(option_index, int)
            or option_index not in {1, 2}
            or option_index in rows
        ):
            raise ValueError("The FEEZIE revision receipt option coverage is invalid.")
        action = str(raw_row.get("action") or "").strip().lower()
        attempt_count = raw_row.get("attempt_count")
        changed = raw_row.get("changed")
        if action not in {"preserved", "revised", "revision_failed"}:
            raise ValueError("The FEEZIE revision receipt has an invalid option action.")
        if isinstance(attempt_count, bool) or attempt_count not in {0, 1} or not isinstance(changed, bool):
            raise ValueError("The FEEZIE revision receipt has invalid per-option topology.")

        digest_fields = {
            name: str(raw_row.get(name) or "").strip().lower()
            for name in (
                "original_post_sha256",
                "final_post_sha256",
                "revision_prompt_sha256",
                "bounded_findings_sha256",
                "role_contract_sha256",
                "attempt_output_sha256",
            )
        }
        if (
            not _valid_feezie_sha256(digest_fields["original_post_sha256"])
            or not _valid_feezie_sha256(digest_fields["final_post_sha256"])
            or not _valid_feezie_sha256(digest_fields["role_contract_sha256"])
        ):
            raise ValueError("The FEEZIE revision receipt has an invalid option commitment.")
        error_code = str(raw_row.get("error_code") or "").strip().lower()
        if error_code and re.fullmatch(r"[a-z0-9_:-]{1,96}", error_code) is None:
            raise ValueError("The FEEZIE revision receipt has an invalid option error code.")

        if action == "preserved":
            if (
                attempt_count != 0
                or changed
                or digest_fields["original_post_sha256"] != digest_fields["final_post_sha256"]
                or any(
                    digest_fields[name]
                    for name in (
                        "revision_prompt_sha256",
                        "bounded_findings_sha256",
                        "attempt_output_sha256",
                    )
                )
                or error_code
            ):
                raise ValueError("A preserved FEEZIE option has contradictory revision evidence.")
        else:
            if (
                attempt_count != 1
                or not _valid_feezie_sha256(digest_fields["revision_prompt_sha256"])
                or not _valid_feezie_sha256(digest_fields["bounded_findings_sha256"])
            ):
                raise ValueError("An attempted FEEZIE revision lacks bounded call evidence.")
            if action == "revision_failed":
                if (
                    status != "failed"
                    or changed
                    or digest_fields["original_post_sha256"] != digest_fields["final_post_sha256"]
                    or digest_fields["attempt_output_sha256"]
                    or not error_code
                ):
                    raise ValueError("A failed FEEZIE revision row is internally inconsistent.")
            elif (
                not _valid_feezie_sha256(digest_fields["attempt_output_sha256"])
                or error_code
            ):
                raise ValueError("A successful FEEZIE revision row lacks its output commitment.")
            elif status == "completed" and (
                not changed
                or digest_fields["original_post_sha256"] == digest_fields["final_post_sha256"]
            ):
                raise ValueError("A completed FEEZIE revision did not change its target option.")

        expected_final_sha = _feezie_content_sha256(final_options[option_index - 1])
        if not secrets.compare_digest(expected_final_sha, digest_fields["final_post_sha256"]):
            raise ValueError("The FEEZIE revision receipt does not match the final option copy.")
        rows[option_index] = {**raw_row, **digest_fields, "error_code": error_code}

    if set(rows) != {1, 2} or [int(row.get("canonical_option_index") or 0) for row in raw_rows] != [1, 2]:
        raise ValueError("The FEEZIE revision receipt did not preserve canonical option order.")
    if revision_calls != sum(int(rows[index]["attempt_count"]) for index in (1, 2)):
        raise ValueError("The FEEZIE revision receipt call count does not match its option rows.")
    computed_original_pair = _feezie_pair_sha256(
        [str(rows[index]["original_post_sha256"]) for index in (1, 2)]
    )
    computed_final_pair = _feezie_pair_sha256(
        [str(rows[index]["final_post_sha256"]) for index in (1, 2)]
    )
    if (
        not secrets.compare_digest(computed_original_pair, original_pair_sha)
        or not secrets.compare_digest(computed_final_pair, final_pair_sha)
    ):
        raise ValueError("The FEEZIE revision receipt pair commitment does not match its option rows.")

    final_critic_receipt_sha = _feezie_json_sha256(critic_review)
    if status == "not_required":
        if (
            revision_calls != 0
            or final_critic_calls != 0
            or initial_critic_status != "completed"
            or final_critic_status != "completed"
            or original_pair_sha != final_pair_sha
            or not _valid_feezie_sha256(initial_critic_sha)
            or initial_critic_sha != final_critic_sha
            or not secrets.compare_digest(final_critic_sha, final_critic_receipt_sha)
            or any(rows[index]["action"] != "preserved" for index in (1, 2))
        ):
            raise ValueError("The no-revision FEEZIE receipt is internally inconsistent.")
    elif status == "completed":
        if (
            revision_calls not in {1, 2}
            or final_critic_calls != 1
            or initial_critic_status != "completed"
            or final_critic_status != "completed"
            or not _valid_feezie_sha256(initial_critic_sha)
            or not _valid_feezie_sha256(final_critic_sha)
            or initial_critic_sha == final_critic_sha
            or not secrets.compare_digest(final_critic_sha, final_critic_receipt_sha)
            or any(rows[index]["action"] == "revision_failed" for index in (1, 2))
        ):
            raise ValueError("The completed FEEZIE revision receipt is internally inconsistent.")
    else:
        if final_critic_sha:
            raise ValueError("A failed FEEZIE revision receipt cannot claim a completed final critic.")
        if not initial_critic_sha:
            if revision_calls != 0 or final_critic_calls != 0:
                raise ValueError("An initial-critic failure cannot claim later revision calls.")
        elif not _valid_feezie_sha256(initial_critic_sha):
            raise ValueError("The failed FEEZIE revision receipt has an invalid initial critic commitment.")

    return dict(receipt)


def _validate_feezie_blind_critic_receipt(
    *,
    receipt: Any,
    reviews: List[Dict[str, Any]],
    options: List[str],
    job_scope: str,
) -> None:
    expected_option_count = len(options)
    if not isinstance(receipt, dict):
        raise ValueError("The independent critic must include a blind-review audit receipt.")
    allowed_keys = {
        "schema_version",
        "independent_execution",
        "opaque_identity_used",
        "original_numbering_withheld_from_critic",
        "original_order_withheld_from_critic",
        "writer_option_plan_withheld_from_critic",
        "deterministic_shuffle",
        "non_identity_permutation",
        "order_strategy",
        "option_count",
        "job_scope_sha256",
        "critic_order",
        "mapping_commitment_sha256",
        "contains_draft_copy",
        "opaque_role_contracts_used",
        "contains_role_payload_copy",
        "role_contract_commitment_sha256",
    }
    if set(receipt) != allowed_keys:
        raise ValueError("The blind-review audit receipt is unbounded or incomplete.")
    if str(receipt.get("schema_version") or "") != FEEZIE_BLIND_CRITIC_RECEIPT_VERSION:
        raise ValueError("The blind-review audit receipt has an unsupported schema.")
    required_true = (
        "independent_execution",
        "opaque_identity_used",
        "original_numbering_withheld_from_critic",
        "original_order_withheld_from_critic",
        "writer_option_plan_withheld_from_critic",
        "deterministic_shuffle",
        "non_identity_permutation",
    )
    if any(receipt.get(field) is not True for field in required_true):
        raise ValueError("The critic did not prove independent blinded randomized review.")
    if receipt.get("contains_draft_copy") is not False:
        raise ValueError("The blind-review audit receipt must not contain draft copy.")
    if (
        receipt.get("opaque_role_contracts_used") is not True
        or receipt.get("contains_role_payload_copy") is not False
        or not _valid_feezie_sha256(receipt.get("role_contract_commitment_sha256"))
    ):
        raise ValueError("The blind-review audit receipt has invalid role-card evidence.")
    if str(receipt.get("order_strategy") or "") != FEEZIE_BLIND_CRITIC_ORDER_STRATEGY:
        raise ValueError("The blind-review audit receipt has an unknown ordering strategy.")
    if int(receipt.get("option_count") or 0) != expected_option_count:
        raise ValueError("The blind-review audit receipt does not cover both FEEZIE drafts.")

    if not _valid_feezie_sha256(receipt.get("job_scope_sha256")) or not _valid_feezie_sha256(
        receipt.get("mapping_commitment_sha256")
    ):
        raise ValueError("The blind-review audit receipt has an invalid commitment.")

    expected_plan = _feezie_expected_blind_critic_plan(
        job_scope=job_scope,
        options=options,
    )
    if not secrets.compare_digest(
        str(receipt.get("job_scope_sha256") or "").strip().lower(),
        str(expected_plan["job_scope_sha256"]),
    ):
        raise ValueError("The blind-review audit receipt is bound to the wrong job scope.")

    critic_order = receipt.get("critic_order")
    if not isinstance(critic_order, list) or len(critic_order) != expected_option_count:
        raise ValueError("The blind-review audit receipt has invalid critic-order evidence.")
    option_id_to_index: Dict[str, int] = {}
    canonical_order: List[int] = []
    for row in critic_order:
        if not isinstance(row, dict) or set(row) != {"critic_option_id", "canonical_option_index"}:
            raise ValueError("The blind-review audit receipt contains an invalid mapping row.")
        critic_option_id = str(row.get("critic_option_id") or "").strip()
        canonical_index = int(row.get("canonical_option_index") or 0)
        if (
            not re.fullmatch(r"draft_[0-9a-f]{16}", critic_option_id)
            or critic_option_id in option_id_to_index
            or canonical_index < 1
            or canonical_index > expected_option_count
            or canonical_index in canonical_order
        ):
            raise ValueError("The blind-review audit receipt does not uniquely map every opaque option.")
        option_id_to_index[critic_option_id] = canonical_index
        canonical_order.append(canonical_index)
    if canonical_order == list(range(1, expected_option_count + 1)):
        raise ValueError("The independent critic received the original draft order.")
    if critic_order != expected_plan["critic_order"]:
        raise ValueError("The blind-review audit receipt does not match the exact final draft bytes.")
    mapping_json = json.dumps(critic_order, sort_keys=True, separators=(",", ":"))
    expected_commitment = hashlib.sha256(mapping_json.encode("utf-8")).hexdigest()
    if not secrets.compare_digest(
        expected_commitment,
        str(receipt.get("mapping_commitment_sha256") or ""),
    ):
        raise ValueError("The blind-review audit mapping commitment does not match its evidence.")
    if option_id_to_index != expected_plan["option_id_to_index"]:
        raise ValueError("The blind-review opaque identifiers do not match the exact final draft bytes.")

    seen_review_ids: set[str] = set()
    for review in reviews:
        critic_option_id = str(review.get("critic_option_id") or "").strip()
        option_index = int(review.get("option_index") or 0)
        if (
            critic_option_id in seen_review_ids
            or option_id_to_index.get(critic_option_id) != option_index
        ):
            raise ValueError("The critic results do not map exactly once to each blinded draft.")
        seen_review_ids.add(critic_option_id)
    if seen_review_ids != set(option_id_to_index):
        raise ValueError("The critic results omit a blinded draft receipt.")


def _validate_feezie_codex_completion_result(
    *,
    job: Dict[str, Any],
    result_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and attach server-computed evidence for the binding FEEZIE draft contract."""

    contract = _feezie_draft_contract(job)
    if not contract:
        return result_payload
    revision_contract = _feezie_revision_contract(job)
    expected_option_count = int(contract.get("required_option_count") or FEEZIE_CODEX_DRAFT_OPTION_COUNT)
    maximum_option_count = int(contract.get("maximum_option_count") or expected_option_count)
    if expected_option_count != FEEZIE_CODEX_DRAFT_OPTION_COUNT or maximum_option_count != expected_option_count:
        raise ValueError("The FEEZIE draft contract must require and cap the run at exactly two options.")

    options = result_payload.get("options")
    if not isinstance(options, list):
        raise ValueError("FEEZIE completion must include an options array.")
    cleaned_options = [str(option).strip() for option in options if isinstance(option, str) and str(option).strip()]
    if len(cleaned_options) != expected_option_count or len(options) != expected_option_count:
        raise ValueError("FEEZIE completion must include exactly two non-empty draft options.")

    packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    diagnostics = result_payload.get("diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        result_payload["diagnostics"] = diagnostics
    diagnostics["draft_contract"] = contract
    if revision_contract:
        diagnostics["revision_contract"] = revision_contract
    quality_gate = _canonical_feezie_quality_gate(
        context_packet=packet,
        options=cleaned_options,
        submitted_quality_gate=diagnostics.get("quality_gate"),
        require_contamination=bool(revision_contract),
        compare_full_receipt=True,
    )
    diagnostics["quality_gate"] = quality_gate
    diagnostics["draft_distinctness"] = dict(quality_gate.get("draft_distinctness") or {})
    technical_completion = diagnostics.get("technical_completion")
    if isinstance(technical_completion, dict):
        technical_completion["draft_count"] = len(cleaned_options)

    critic_review = _closed_feezie_critic_receipt(diagnostics.get("critic_review"))
    diagnostics["critic_review"] = critic_review
    critic_status = str(critic_review.get("status") or "").strip().lower()
    if critic_status not in {"completed", "unavailable", "not_run"}:
        raise ValueError("FEEZIE completion has an invalid independent critic status.")

    submitted_readiness = diagnostics.get("editorial_readiness")
    if not isinstance(submitted_readiness, dict):
        raise ValueError("FEEZIE completion must include an editorial-readiness receipt.")
    if critic_status == "completed":
        reviews = critic_review.get("reviews")
        if not isinstance(reviews, list) or len(reviews) != expected_option_count:
            raise ValueError("The independent critic must return one review for each of the two FEEZIE drafts.")
        critic_scope = _feezie_final_critic_job_scope(
            job=job,
            revision_receipt=diagnostics.get("revision_execution"),
        )
        _validate_feezie_blind_critic_receipt(
            receipt=critic_review.get("blind_review_receipt"),
            reviews=reviews,
            options=cleaned_options,
            job_scope=critic_scope,
        )
        seen_indices: set[int] = set()
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError("The independent critic returned an invalid option review.")
            option_index = int(review.get("option_index") or 0)
            if option_index < 1 or option_index > expected_option_count or option_index in seen_indices:
                raise ValueError("Independent critic option indices must uniquely cover both FEEZIE drafts.")
            seen_indices.add(option_index)
            dimensions = review.get("dimension_scores")
            score = review.get("score")
            verdict = str(review.get("verdict") or "").strip().lower()
            if (
                isinstance(score, bool)
                or not isinstance(score, int)
                or not 1 <= score <= 10
                or verdict not in {"ready", "revise", "blocked"}
            ):
                raise ValueError("Each independent critic review must include a bounded score and verdict.")
            issues = review.get("issues")
            if verdict != "ready" and not issues:
                raise ValueError("A non-ready independent critic verdict must include a concrete issue.")
            if (
                not isinstance(dimensions, dict)
                or set(dimensions) != set(FEEZIE_CRITIC_DIMENSIONS)
                or any(
                    isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 10
                    for value in dimensions.values()
                )
            ):
                raise ValueError("Each independent critic review must include exactly the five bounded quality dimensions.")
            hooks = [str(hook).strip() for hook in (review.get("hook_variants") or []) if str(hook).strip()]
            if len(hooks) != FEEZIE_CODEX_HOOK_VARIANT_COUNT or len({hook.lower() for hook in hooks}) != len(hooks):
                raise ValueError("Each independently criticized FEEZIE draft must include exactly eight unique hook variants.")

        semantic_distinctness = critic_review.get("draft_distinctness")
        if not isinstance(semantic_distinctness, dict) or not isinstance(semantic_distinctness.get("passed"), bool):
            raise ValueError("The independent critic must return a semantic draft-distinctness judgment.")
        if [int(review.get("option_index") or 0) for review in reviews] != list(
            range(1, expected_option_count + 1)
        ):
            raise ValueError("Independent critic reviews must preserve canonical option order after mapping.")

    readiness = _build_feezie_editorial_readiness(
        critic_review=critic_review,
        deterministic_quality_gate=quality_gate,
    )
    if json.loads(json.dumps(submitted_readiness, ensure_ascii=True)) != readiness:
        raise ValueError(
            "The FEEZIE editorial-readiness receipt does not match the final critic and current server quality gate."
        )
    diagnostics["editorial_readiness"] = readiness

    if revision_contract:
        _validate_feezie_revision_execution_receipt(
            receipt=diagnostics.get("revision_execution"),
            final_options=cleaned_options,
            critic_review=critic_review,
            readiness=readiness,
        )
    result_payload["options"] = cleaned_options
    return result_payload


def _completion_text(value: Any, *, limit: int = 1200) -> str:
    return str(value or "").strip()[:limit]


def _completion_text_list(value: Any, *, limit: int = 32, item_limit: int = 500) -> List[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for text in (_completion_text(item, limit=item_limit) for item in value[:limit])
        if text
    ]


def _codex_worker_receipt(worker_id: Any) -> str:
    """Preserve worker lease equality without storing a caller-supplied identity."""

    normalized = str(worker_id or "").strip()
    return f"worker-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def _project_feezie_draft_contract(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    return {
        key: raw.get(key)
        for key in (
            "schema_version",
            "required_option_count",
            "maximum_option_count",
            "meaningful_difference_required",
            "independent_writer_calls_required",
            "writer_calls_per_option",
            "independent_critic_required",
            "critic_reviews_per_option",
            "hook_variants_per_option",
        )
        if raw.get(key) is not None
    }


def _project_feezie_revision_contract(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    return {
        key: raw.get(key)
        for key in (
            "schema_version",
            "enabled",
            "trigger",
            "revision_calls_per_non_ready_option",
            "model_retries_per_revision",
            "preserve_ready_sibling_exactly",
            "fresh_blind_critic_required_after_revision",
        )
        if raw.get(key) is not None
    }


def _project_feezie_distinctness_receipt(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected: Dict[str, Any] = {
        key: raw.get(key)
        for key in (
            "schema_version",
            "passed",
            "required_option_count",
            "actual_option_count",
        )
        if raw.get(key) is not None
    }
    reason = _completion_text(raw.get("reason"), limit=800)
    if reason:
        projected["reason"] = reason
    projected["failed_reasons"] = _completion_text_list(
        raw.get("failed_reasons"), limit=32, item_limit=160
    )
    pairs: List[Dict[str, Any]] = []
    for item in raw.get("pairs") or []:
        if not isinstance(item, dict):
            continue
        pairs.append(
            {
                key: item.get(key)
                for key in (
                    "left_option_index",
                    "right_option_index",
                    "sequence_similarity",
                    "term_containment",
                    "shingle_jaccard",
                    "opening_signatures_match",
                    "passed",
                )
                if item.get(key) is not None
            }
            | {
                "failed_reasons": _completion_text_list(
                    item.get("failed_reasons"), limit=16, item_limit=160
                )
            }
        )
    projected["pairs"] = pairs[:6]
    return projected


def _project_feezie_option_review(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected: Dict[str, Any] = {
        key: raw.get(key)
        for key in (
            "option_index",
            "score",
            "verdict",
            "option_local_ready",
            "pair_admission_passed",
            "editorially_ready",
            "deterministic_quality_passed",
            "deterministic_score",
            "deterministic_threshold",
            "deterministic_blocked",
        )
        if raw.get(key) is not None
    }
    critic_option_id = _completion_text(raw.get("critic_option_id"), limit=40)
    if re.fullmatch(r"draft_[0-9a-f]{16}", critic_option_id):
        projected["critic_option_id"] = critic_option_id
    dimensions = raw.get("dimension_scores") if isinstance(raw.get("dimension_scores"), dict) else {}
    projected["dimension_scores"] = {
        key: dimensions.get(key)
        for key in ("truth", "safety", "intent", "voice", "hook")
        if dimensions.get(key) is not None
    }
    projected["issues"] = _completion_text_list(raw.get("issues"), limit=16, item_limit=500)
    projected["hook_variants"] = _completion_text_list(
        raw.get("hook_variants"),
        limit=FEEZIE_CODEX_HOOK_VARIANT_COUNT,
        item_limit=500,
    )
    projected["deterministic_blocking_reasons"] = _completion_text_list(
        raw.get("deterministic_blocking_reasons"), limit=32, item_limit=160
    )
    return projected


def _project_feezie_blind_critic_receipt(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected = {
        key: raw.get(key)
        for key in (
            "schema_version",
            "independent_execution",
            "opaque_identity_used",
            "original_numbering_withheld_from_critic",
            "original_order_withheld_from_critic",
            "writer_option_plan_withheld_from_critic",
            "deterministic_shuffle",
            "non_identity_permutation",
            "order_strategy",
            "option_count",
            "job_scope_sha256",
            "mapping_commitment_sha256",
            "contains_draft_copy",
            "opaque_role_contracts_used",
            "contains_role_payload_copy",
            "role_contract_commitment_sha256",
        )
        if raw.get(key) is not None
    }
    projected["critic_order"] = [
        {
            "critic_option_id": _completion_text(item.get("critic_option_id"), limit=40),
            "canonical_option_index": item.get("canonical_option_index"),
        }
        for item in (raw.get("critic_order") or [])[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
        if isinstance(item, dict)
    ]
    return projected


def _project_feezie_critic_receipt(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected: Dict[str, Any] = {
        "status": _completion_text(raw.get("status"), limit=40),
        "reviews": [
            _project_feezie_option_review(item)
            for item in (raw.get("reviews") or [])[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
            if isinstance(item, dict)
        ],
        "draft_distinctness": _project_feezie_distinctness_receipt(
            raw.get("draft_distinctness")
        ),
    }
    reason = _completion_text(raw.get("reason"), limit=160)
    if reason:
        projected["reason"] = reason
    failure_stage = _completion_text(raw.get("failure_stage"), limit=80)
    if failure_stage:
        projected["failure_stage"] = failure_stage
    exception_class = _completion_text(raw.get("exception_class"), limit=80)
    if exception_class:
        projected["exception_class"] = exception_class
    if raw.get("attempt_count") == 1:
        projected["attempt_count"] = 1
    message = _completion_text(raw.get("message"), limit=240)
    if message:
        projected["message"] = message
    if isinstance(raw.get("blind_review_receipt"), dict):
        projected["blind_review_receipt"] = _project_feezie_blind_critic_receipt(
            raw.get("blind_review_receipt")
        )
    return projected


def _closed_feezie_critic_receipt(value: Any) -> Dict[str, Any]:
    """Validate the exact bounded critic shape, then preserve its hash verbatim."""

    if not isinstance(value, dict):
        raise ValueError("The FEEZIE critic receipt is missing.")
    raw = dict(value)
    status = str(raw.get("status") or "").strip().lower()
    if status == "completed":
        if set(raw) != {
            "status",
            "draft_distinctness",
            "blind_review_receipt",
            "reviews",
        }:
            raise ValueError("The completed FEEZIE critic receipt is unbounded.")
        distinctness = raw.get("draft_distinctness")
        if (
            not isinstance(distinctness, dict)
            or set(distinctness) != {"passed", "reason"}
            or not isinstance(distinctness.get("passed"), bool)
            or not str(distinctness.get("reason") or "").strip()
            or len(str(distinctness.get("reason") or "")) > 800
        ):
            raise ValueError("The completed FEEZIE critic distinctness receipt is unbounded.")
        reviews = raw.get("reviews")
        if not isinstance(reviews, list) or len(reviews) != FEEZIE_CODEX_DRAFT_OPTION_COUNT:
            raise ValueError("The completed FEEZIE critic review coverage is invalid.")
        review_keys = {
            "option_index",
            "critic_option_id",
            "score",
            "verdict",
            "dimension_scores",
            "issues",
            "hook_variants",
        }
        for review in reviews:
            if not isinstance(review, dict) or set(review) != review_keys:
                raise ValueError("A completed FEEZIE critic option receipt is unbounded.")
            issues = review.get("issues")
            hooks = review.get("hook_variants")
            if (
                not isinstance(issues, list)
                or len(issues) > 6
                or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in issues)
                or not isinstance(hooks, list)
                or len(hooks) != FEEZIE_CODEX_HOOK_VARIANT_COUNT
                or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in hooks)
            ):
                raise ValueError("A completed FEEZIE critic copy receipt exceeds its bounds.")
    elif status in {"unavailable", "not_run"}:
        allowed_keys = {
            "status",
            "reason",
            "failure_stage",
            "exception_class",
            "attempt_count",
            "message",
            "reviews",
        }
        if (
            not set(raw).issubset(allowed_keys)
            or set(raw) - {"failure_stage", "exception_class", "attempt_count", "message"}
            != {"status", "reason", "reviews"}
            or raw.get("reviews") != []
        ):
            raise ValueError("The unavailable FEEZIE critic receipt is unbounded.")
        reason = str(raw.get("reason") or "").strip()
        failure_stage = str(raw.get("failure_stage") or "").strip()
        exception_class = str(raw.get("exception_class") or "").strip()
        message = str(raw.get("message") or "").strip()
        if re.fullmatch(r"[a-z0-9_:-]{1,160}", reason) is None:
            raise ValueError("The unavailable FEEZIE critic reason code is invalid.")
        if failure_stage and re.fullmatch(r"[a-z0-9_:-]{1,80}", failure_stage) is None:
            raise ValueError("The unavailable FEEZIE critic failure stage is invalid.")
        if exception_class and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,79}", exception_class) is None:
            raise ValueError("The unavailable FEEZIE critic exception class is invalid.")
        allowed_messages = {
            "Independent critic failed closed at a bounded execution stage.",
            "Final independent critic failed closed at a bounded execution stage.",
            "Independent critic timed out and failed closed.",
            "Final independent critic timed out and failed closed.",
            "Revision failed before an admissible final critic verdict.",
        }
        if message and message not in allowed_messages:
            raise ValueError("The unavailable FEEZIE critic message is not a generic stage receipt.")
        if "attempt_count" in raw and raw.get("attempt_count") != 1:
            raise ValueError("The unavailable FEEZIE critic attempt receipt is invalid.")
    else:
        raise ValueError("The FEEZIE critic receipt has an unsupported status.")
    _assert_feezie_completion_payload_safe({"critic_review": raw})
    return json.loads(json.dumps(raw, ensure_ascii=True))


def _project_feezie_voice_contamination_receipt(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected = {
        key: raw.get(key)
        for key in (
            "schema_version",
            "passed",
            "exemplar_count",
            "evaluated_option_count",
            "blocked_option_count",
            "pair_sha256",
            "contains_exemplar_text",
        )
        if raw.get(key) is not None
    }
    projected["blocker_codes"] = _completion_text_list(
        raw.get("blocker_codes"), limit=32, item_limit=160
    )
    option_results: List[Dict[str, Any]] = []
    for item in raw.get("option_results") or []:
        if not isinstance(item, dict):
            continue
        findings = [
            {
                key: finding.get(key)
                for key in ("code", "reference_id_sha256", "match_sha256", "matched_token_count")
                if finding.get(key) is not None
            }
            for finding in (item.get("findings") or [])[:32]
            if isinstance(finding, dict)
        ]
        option_results.append(
            {
                "option_index": item.get("option_index"),
                "option_sha256": item.get("option_sha256"),
                "passed": item.get("passed"),
                "blocker_codes": _completion_text_list(
                    item.get("blocker_codes"), limit=32, item_limit=160
                ),
                "findings": findings,
            }
        )
    projected["option_results"] = option_results[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
    return projected


def _project_feezie_quality_gate(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected: Dict[str, Any] = {
        key: raw.get(key)
        for key in (
            "schema_version",
            "passed",
            "selection_admission_passed",
            "required_option_count",
            "evaluated_option_count",
        )
        if raw.get(key) is not None
    }
    projected["failed_reasons"] = _completion_text_list(
        raw.get("failed_reasons"), limit=64, item_limit=180
    )
    shared = raw.get("shared_constraints") if isinstance(raw.get("shared_constraints"), dict) else {}
    projected["shared_constraints"] = {
        key: shared.get(key)
        for key in ("passed", "required_option_count", "evaluated_option_count")
        if shared.get(key) is not None
    } | {
        "failed_reasons": _completion_text_list(
            shared.get("failed_reasons"), limit=32, item_limit=180
        )
    }
    projected["option_results"] = [
        {
            key: item.get(key)
            for key in ("option_index", "passed", "score", "threshold")
            if item.get(key) is not None
        }
        | {
            "failed_reasons": _completion_text_list(
                item.get("failed_reasons"), limit=32, item_limit=180
            )
        }
        for item in (raw.get("option_results") or [])[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
        if isinstance(item, dict)
    ]
    projected["draft_distinctness"] = _project_feezie_distinctness_receipt(
        raw.get("draft_distinctness")
    )
    if isinstance(raw.get("voice_exemplar_contamination"), dict):
        projected["voice_exemplar_contamination"] = _project_feezie_voice_contamination_receipt(
            raw.get("voice_exemplar_contamination")
        )
    return projected


def _project_feezie_revision_execution(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected = {
        key: raw.get(key)
        for key in (
            "schema_version",
            "status",
            "failure_code",
            "canonical_order_preserved",
            "retry_allowed",
            "initial_critic_call_count",
            "initial_critic_status",
            "initial_critic_reason",
            "revision_call_count",
            "final_critic_call_count",
            "final_critic_status",
            "final_critic_reason",
            "original_pair_sha256",
            "final_pair_sha256",
            "initial_critic_receipt_sha256",
            "final_critic_receipt_sha256",
            "contains_post_copy",
            "contains_critic_issue_copy",
        )
        if raw.get(key) is not None
    }
    projected["options"] = [
        {
            key: item.get(key)
            for key in (
                "canonical_option_index",
                "action",
                "attempt_count",
                "original_post_sha256",
                "final_post_sha256",
                "revision_prompt_sha256",
                "bounded_findings_sha256",
                "role_contract_sha256",
                "attempt_output_sha256",
                "changed",
                "error_code",
            )
            if item.get(key) is not None
        }
        for item in (raw.get("options") or [])[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
        if isinstance(item, dict)
    ]
    return projected


def _project_feezie_editorial_readiness(value: Any) -> Dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    projected = {
        key: raw.get(key)
        for key in (
            "ready",
            "status",
            "critic_status",
            "ready_score_threshold",
            "quality_gate_schema_version",
            "deterministic_quality_receipt_valid",
            "deterministic_quality_gate_passed",
            "batch_all_options_quality_passed",
            "shared_constraints_passed",
            "selection_admission_passed",
            "voice_exemplar_contamination_passed",
            "semantic_distinctness_passed",
            "pair_attribution_valid",
            "pair_affected_option_indices",
            "option_local_ready_count",
            "ready_option_count",
        )
        if raw.get(key) is not None
    }
    projected["draft_distinctness"] = _project_feezie_distinctness_receipt(
        raw.get("draft_distinctness")
    )
    projected["option_reviews"] = [
        _project_feezie_option_review(item)
        for item in (raw.get("option_reviews") or [])[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
        if isinstance(item, dict)
    ]
    projected["blocking_reasons"] = _completion_text_list(
        raw.get("blocking_reasons"), limit=64, item_limit=180
    )
    return projected


def _project_feezie_completion_result(
    *,
    job: Dict[str, Any],
    result_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist only the public drafts and closed quality/critic receipts."""

    packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    request_payload = job.get("request_payload") if isinstance(job.get("request_payload"), dict) else {}
    diagnostics = (
        dict(result_payload.get("diagnostics") or {})
        if isinstance(result_payload.get("diagnostics"), dict)
        else {}
    )
    options = [
        str(option).strip()
        for option in (result_payload.get("options") or [])
        if isinstance(option, str) and str(option).strip()
    ][:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
    traces: List[Dict[str, Any]] = []
    for item in diagnostics.get("llm_provider_trace") or []:
        if not isinstance(item, dict):
            continue
        trace = {
            key: _completion_text(item.get(key), limit=160)
            for key in (
                "provider",
                "actual_model",
                "reasoning_effort",
                "status",
                "error_code",
                "failure_stage",
            )
            if _completion_text(item.get(key), limit=160)
        }
        if trace:
            traces.append(trace)

    strategy = packet.get("strategy_contract") if isinstance(packet.get("strategy_contract"), dict) else {}
    classification = (
        packet.get("candidate_classification")
        if isinstance(packet.get("candidate_classification"), dict)
        else {}
    )
    source_freshness = (
        classification.get("source_freshness")
        if isinstance(classification.get("source_freshness"), dict)
        else {}
    )
    classification_projection = {
        key: _completion_text(classification.get(key), limit=1200)
        for key in (
            "canonical_pillar",
            "career_signal",
            "employer_proximity",
            "employer_safety",
            "proof_posture",
            "treatment",
            "publish_posture",
            "audience",
            "generation_audience",
            "audience_consequence",
            "distinct_thesis",
            "why_now",
            "development_status",
            "classification_state",
        )
        if _completion_text(classification.get(key), limit=1200)
    }
    missing_fields = _completion_text_list(
        classification.get("missing_fields"), limit=32, item_limit=120
    )
    if missing_fields:
        classification_projection["missing_fields"] = missing_fields
    if source_freshness:
        classification_projection["source_freshness"] = {
            key: (
                source_freshness.get(key)
                if key in {"age_days", "current_claim_allowed"}
                else _completion_text(source_freshness.get(key), limit=120)
            )
            for key in (
                "state",
                "declared_state",
                "temporality",
                "published_at",
                "observed_at",
                "dated_at",
                "date_origin",
                "age_days",
                "current_claim_allowed",
            )
            if source_freshness.get(key) is not None
        }

    revision_execution = _project_feezie_revision_execution(
        diagnostics.get("revision_execution")
    )
    critic_review = _closed_feezie_critic_receipt(diagnostics.get("critic_review"))
    editorial_readiness = _project_feezie_editorial_readiness(
        diagnostics.get("editorial_readiness")
    )
    projected_diagnostics: Dict[str, Any] = {
        "grounding_mode": str(packet.get("grounding_mode") or "proof_ready"),
        "generation_strategy": "codex_terminal",
        "intent": str(packet.get("intent") or request_payload.get("category") or "value"),
        "strategy_contract": {
            key: _completion_text(strategy.get(key), limit=160)
            for key in ("schema_version", "contract_hash", "approved_at")
            if _completion_text(strategy.get(key), limit=160)
        },
        "candidate_classification": classification_projection,
        "planned_option_briefs": [
            {
                key: item.get(key)
                for key in (
                    "option_number",
                    "framing_mode",
                    "primary_claim",
                    "proof_packet",
                    "story_beat",
                )
                if item.get(key) not in (None, "")
            }
            for item in (packet.get("planned_option_briefs") or [])[:FEEZIE_CODEX_DRAFT_OPTION_COUNT]
            if isinstance(item, dict)
        ],
        "llm_provider_trace": traces[:12],
        "source_mode": request_payload.get("source_mode"),
        "draft_contract": _project_feezie_draft_contract(packet.get("draft_contract")),
        "revision_contract": _project_feezie_revision_contract(packet.get("revision_contract")),
        "revision_execution": revision_execution,
        "draft_distinctness": _project_feezie_distinctness_receipt(
            diagnostics.get("draft_distinctness")
        ),
        "quality_gate": _project_feezie_quality_gate(diagnostics.get("quality_gate")),
        "technical_completion": {
            "status": "completed",
            "writer_status": "completed",
            "draft_count": len(options),
            "drafts_preserved": True,
            **(
                {"revision_status": revision_execution.get("status")}
                if revision_execution.get("status")
                else {}
            ),
        },
        "critic_review": critic_review,
        "editorial_readiness": editorial_readiness,
    }
    if revision_execution:
        _validate_feezie_revision_execution_receipt(
            receipt=revision_execution,
            final_options=options,
            critic_review=critic_review,
            readiness=editorial_readiness,
        )
    projected = {
        "schema_version": FEEZIE_COMPLETION_RESULT_VERSION,
        "success": True,
        "options": options,
        "diagnostics": projected_diagnostics,
    }
    _assert_feezie_completion_payload_safe(projected)
    return projected


def _project_generic_codex_completion_result(result_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep intended output plus bounded operational metadata for non-FEEZIE jobs."""

    diagnostics = (
        dict(result_payload.get("diagnostics") or {})
        if isinstance(result_payload.get("diagnostics"), dict)
        else {}
    )
    traces: List[Dict[str, Any]] = []
    for item in diagnostics.get("llm_provider_trace") or []:
        if not isinstance(item, dict):
            continue
        trace = {
            key: _completion_text(item.get(key), limit=160)
            for key in ("provider", "actual_model", "reasoning_effort", "status", "error_code", "failure_stage")
            if _completion_text(item.get(key), limit=160)
        }
        if trace:
            traces.append(trace)
    projected_diagnostics = {
        key: _completion_text(diagnostics.get(key), limit=160)
        for key in (
            "grounding_mode",
            "generation_strategy",
            "draft_mode",
            "draft_type",
            "source_mode",
        )
        if _completion_text(diagnostics.get(key), limit=160)
    }
    projected_diagnostics["llm_provider_trace"] = traces[:8]
    return {
        "schema_version": CODEX_COMPLETION_RESULT_VERSION,
        "success": True,
        "options": [
            str(option).strip()
            for option in (result_payload.get("options") or [])
            if isinstance(option, str) and str(option).strip()
        ][:3],
        "diagnostics": projected_diagnostics,
    }


def _assert_feezie_completion_payload_safe(value: Any) -> None:
    _assert_feezie_remote_job_payload_safe(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded.encode("utf-8")) > 256 * 1024:
        raise ValueError("FEEZIE completion result exceeds the closed receipt size bound.")
    if re.search(
        r"\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[A-Z0-9]{16})\b|\b(?:api[ _-]?key|authorization|password|secret|token)"
        r"\s*(?::|=|\bis\b)\s*\S+|<VOICE_EXAMPLE_|<INFLUENCE_CARD_|"
        r"^(?:TOPIC|PROOF|STORY) ANCHORS?:|^TARGET WRITER JOB:",
        encoded,
        flags=re.IGNORECASE | re.MULTILINE,
    ):
        raise ValueError("FEEZIE completion result retained a credential, prompt, or source body marker.")


def _feezie_completion_artifacts(
    *,
    result_payload: Dict[str, Any],
    initial_critic_receipt: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Rebuild approved artifacts from the projected result; never trust worker content."""

    diagnostics = result_payload.get("diagnostics") if isinstance(result_payload.get("diagnostics"), dict) else {}
    artifact_specs: tuple[tuple[str, str, Any], ...] = (
        *(
            (
                (
                    "editorial_critic_initial",
                    "initial-editorial-critic-review.json",
                    initial_critic_receipt,
                ),
            )
            if isinstance(initial_critic_receipt, dict)
            else ()
        ),
        (
            "quality_gate",
            "quality-gate.json",
            diagnostics.get("quality_gate"),
        ),
        (
            "editorial_critic",
            "editorial-critic-review.json",
            diagnostics.get("critic_review"),
        ),
        (
            "revision_execution",
            "revision-execution-receipt.json",
            diagnostics.get("revision_execution"),
        ),
    )
    items: List[Dict[str, Any]] = []
    for kind, filename, content in artifact_specs:
        if not isinstance(content, dict) or not content:
            continue
        envelope = {
            "schema_version": FEEZIE_COMPLETION_ARTIFACT_VERSION,
            "kind": kind,
            "receipt": content,
        }
        _assert_feezie_completion_payload_safe(envelope)
        items.append(
            {
                "kind": kind,
                "label": filename,
                "filename": filename,
                "mime_type": "application/json",
                "content": json.dumps(envelope, ensure_ascii=True, indent=2) + "\n",
            }
        )
    return items


def _feezie_initial_critic_receipt_from_artifacts(
    *,
    requested_artifacts: List[Dict[str, Any]],
    result_payload: Dict[str, Any],
    required: bool,
) -> Dict[str, Any] | None:
    """Read only the exact initial-critic artifact and bind it to its receipt hash."""

    candidates = [
        item
        for item in requested_artifacts
        if isinstance(item, dict)
        and str(item.get("kind") or "").strip().lower() == "editorial_critic"
        and str(item.get("label") or "").strip() == "initial-editorial-critic-review.json"
    ]
    if not candidates:
        if required:
            raise ValueError("FEEZIE completion requires the initial independent-critic artifact.")
        return None
    if len(candidates) != 1:
        raise ValueError("FEEZIE completion received multiple initial independent-critic artifacts.")
    candidate = candidates[0]
    if (
        str(candidate.get("filename") or "").strip()
        != "initial-editorial-critic-review.json"
        or str(candidate.get("mime_type") or "").strip().lower() != "application/json"
    ):
        raise ValueError("The initial independent-critic artifact metadata is invalid.")
    content = candidate.get("content")
    if not isinstance(content, str) or len(content.encode("utf-8")) > 64 * 1024:
        raise ValueError("The initial independent-critic artifact exceeds its size bound.")
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("The initial independent-critic artifact is not valid JSON.") from exc
    initial_receipt = _closed_feezie_critic_receipt(parsed)
    diagnostics = result_payload.get("diagnostics") if isinstance(result_payload.get("diagnostics"), dict) else {}
    revision_execution = (
        diagnostics.get("revision_execution")
        if isinstance(diagnostics.get("revision_execution"), dict)
        else {}
    )
    expected_sha = str(
        revision_execution.get("initial_critic_receipt_sha256") or ""
    ).strip().lower()
    if expected_sha:
        if not secrets.compare_digest(expected_sha, _feezie_json_sha256(initial_receipt)):
            raise ValueError("The initial independent-critic artifact does not match its revision receipt.")
    elif str(initial_receipt.get("status") or "").strip().lower() == "completed":
        raise ValueError("A completed initial critic is missing its revision-receipt commitment.")
    return initial_receipt


def _safe_feezie_artifact_preview(
    *,
    job: Dict[str, Any],
    artifact: Dict[str, Any],
) -> str | None:
    """Expose only artifacts that exactly match a server-owned closed envelope."""

    artifact_id = str(artifact.get("artifact_id") or "")
    artifact_kind = str(artifact.get("kind") or "").strip().lower()
    if not artifact_id:
        return None
    expected_metadata = {
        "context_packet": ("context-packet.json", "application/json"),
        "request_payload": ("request-payload.json", "application/json"),
        "editorial_critic_initial": (
            "initial-editorial-critic-review.json",
            "application/json",
        ),
        "quality_gate": ("quality-gate.json", "application/json"),
        "editorial_critic": ("editorial-critic-review.json", "application/json"),
        "revision_execution": ("revision-execution-receipt.json", "application/json"),
    }
    metadata = expected_metadata.get(artifact_kind)
    if metadata is None:
        return None
    expected_filename, expected_mime_type = metadata
    if (
        str(artifact.get("label") or "") != expected_filename
        or str(artifact.get("filename") or "") != expected_filename
        or str(artifact.get("mime_type") or "") != expected_mime_type
    ):
        return None
    try:
        content = read_job_artifact_content(
            job_id=str(job.get("id") or ""),
            artifact_id=artifact_id,
        )
        parsed = json.loads(content or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None

    if artifact_kind in {"context_packet", "request_payload"}:
        expected = job.get(artifact_kind)
        if (
            not isinstance(expected, dict)
            or expected.get("packet_schema_version") != FEEZIE_REMOTE_JOB_PACKET_VERSION
            or parsed != expected
        ):
            return None
        try:
            _assert_feezie_remote_job_payload_safe(parsed)
        except ValueError:
            return None
        return str(content)[:2000]

    result_payload = job.get("result_payload")
    if (
        not isinstance(result_payload, dict)
        or result_payload.get("schema_version") != FEEZIE_COMPLETION_RESULT_VERSION
    ):
        return None
    if artifact_kind == "editorial_critic_initial":
        if set(parsed) != {"schema_version", "kind", "receipt"} or (
            parsed.get("schema_version") != FEEZIE_COMPLETION_ARTIFACT_VERSION
            or parsed.get("kind") != artifact_kind
        ):
            return None
        try:
            initial_receipt = _closed_feezie_critic_receipt(parsed.get("receipt"))
        except ValueError:
            return None
        diagnostics = (
            result_payload.get("diagnostics")
            if isinstance(result_payload.get("diagnostics"), dict)
            else {}
        )
        revision_execution = (
            diagnostics.get("revision_execution")
            if isinstance(diagnostics.get("revision_execution"), dict)
            else {}
        )
        expected_sha = str(
            revision_execution.get("initial_critic_receipt_sha256") or ""
        ).strip().lower()
        if expected_sha:
            if not secrets.compare_digest(
                expected_sha,
                _feezie_json_sha256(initial_receipt),
            ):
                return None
        elif str(initial_receipt.get("status") or "").strip().lower() == "completed":
            return None
        return str(content)[:2000]
    try:
        expected_items = _feezie_completion_artifacts(
            result_payload=result_payload,
        )
    except ValueError:
        return None
    matching_items = [
        item for item in expected_items if str(item.get("kind") or "") == artifact_kind
    ]
    if len(matching_items) != 1:
        return None
    expected_item = matching_items[0]
    try:
        expected_payload = json.loads(str(expected_item.get("content") or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if parsed != expected_payload:
        return None
    return str(content)[:2000]


def _build_local_codex_status_response(job: Dict[str, Any]) -> LocalCodexJobStatusResponse:
    closed_feezie_job = bool(_feezie_draft_contract(job))
    result_payload = job.get("result_payload")
    result: ContentGenerationResponse | None = None
    if isinstance(result_payload, dict):
        try:
            if closed_feezie_job:
                if result_payload.get("schema_version") != FEEZIE_COMPLETION_RESULT_VERSION:
                    raise ValueError("Legacy FEEZIE result is not safe to expose.")
                expected_result = _project_feezie_completion_result(
                    job=job,
                    result_payload=result_payload,
                )
                if expected_result != result_payload:
                    raise ValueError("FEEZIE result does not match the closed completion schema.")
            result = ContentGenerationResponse(**result_payload)
        except (TypeError, ValueError):
            result = None
    error_message = _trim_job_error(job.get("error_message"))
    if closed_feezie_job and error_message:
        error_message = "Local generation failed."
    return LocalCodexJobStatusResponse(
        success=True,
        job_id=str(job.get("id") or ""),
        workspace_slug=str(job.get("workspace_slug") or ""),
        status=str(job.get("status") or "pending"),
        requested_by=None if closed_feezie_job else str(job.get("requested_by") or ""),
        created_at=str(job.get("created_at") or ""),
        started_at=str(job.get("started_at") or ""),
        completed_at=str(job.get("completed_at") or ""),
        error_message=error_message,
        result=result,
        artifact_count=len([item for item in (job.get("artifacts") or []) if isinstance(item, dict)]),
    )


def _parse_provider_order(value: str) -> List[str]:
    # Owner decision 2026-08-21: Llama-family generation is retired system-wide.
    # Keep unknown/retired provider names fail-closed so a stale environment
    # variable cannot silently restore an owner-facing Ollama/Llama path.
    allowed = {"openai", "gemini", "codex"}
    ordered: List[str] = []
    seen: set[str] = set()
    for raw in (value or "").split(","):
        provider = raw.strip().lower()
        if not provider or provider not in allowed or provider in seen:
            continue
        seen.add(provider)
        ordered.append(provider)
    return ordered


def _default_content_provider_order() -> List[str]:
    configured = _parse_provider_order(os.getenv("CONTENT_GENERATION_PROVIDER_ORDER", ""))
    if configured:
        return configured
    if _runtime_is_production():
        return ["gemini", "openai"]
    # Local generation must not silently depend on a local generative model.
    return ["openai", "gemini"]


def _default_email_content_provider_order() -> List[str]:
    configured = _parse_provider_order(os.getenv("CONTENT_GENERATION_EMAIL_PROVIDER_ORDER", ""))
    if configured:
        return configured
    return _default_content_provider_order()


def _request_uses_email_provider_policy(req: "ContentGenerationRequest | None" = None) -> bool:
    if not req:
        return False
    return (
        str(req.content_type or "").strip().lower() in EMAIL_CONTENT_TYPES
        or str(req.source_mode or "").strip().lower() == "email_thread_grounded"
    )


def _normalize_openai_base_url(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        return normalized
    try:
        parsed = urlsplit(normalized)
    except ValueError as exc:
        raise ValueError("Content-generation provider base URL is invalid.") from exc
    hostname = str(parsed.hostname or "").strip().lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "ollama" in normalized.lower()
    ):
        raise ValueError("Content-generation provider base URL must be a public HTTPS endpoint.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if (
        (address is not None and not address.is_global)
        or hostname in {"localhost", "0.0.0.0"}
        or hostname.endswith((".internal", ".local"))
    ):
        raise ValueError("Content-generation provider base URL must be a public HTTPS endpoint.")
    return normalized if normalized.endswith("/") else f"{normalized}/"


def _validated_generation_model(value: str) -> str:
    """Reject retired model identities before an allowed provider is invoked."""

    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 200 or any(character in normalized for character in "\r\n"):
        raise ValueError("Content-generation model configuration is invalid.")
    if "llama" in normalized.lower() or "ollama" in normalized.lower():
        raise ValueError("Llama-family generation is retired and cannot be configured.")
    return normalized


def _provider_is_configured(name: str) -> bool:
    if name == "openai":
        return bool((os.getenv("OPENAI_API_KEY") or "").strip())
    if name == "codex":
        return bool((os.getenv("CONTENT_GENERATION_CODEX_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip())
    if name == "gemini":
        return bool((os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip())
    return False


def _uses_fast_model_alias(requested_model: str) -> bool:
    normalized = (requested_model or "").strip().lower()
    if not normalized:
        return True
    return any(token in normalized for token in ("mini", "nano", "flash", "fast"))


def _resolve_provider_model(provider: ContentLLMProvider, requested_model: str) -> str:
    normalized = (requested_model or "").strip().lower()
    if normalized == CONTENT_FAST_MODEL_ALIAS:
        return _validated_generation_model(provider.fast_model)
    if normalized == CONTENT_EDITOR_MODEL_ALIAS:
        return _validated_generation_model(provider.editor_model or provider.fast_model)
    if normalized:
        _validated_generation_model(requested_model)
    if provider.name == "openai":
        return _validated_generation_model(requested_model or provider.fast_model)
    if _uses_fast_model_alias(requested_model):
        return _validated_generation_model(provider.fast_model)
    return _validated_generation_model(provider.editor_model or provider.fast_model)


def _is_retryable_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return True
    message = str(exc).lower()
    return any(signal in message for signal in ("429", "rate limit", "resource_exhausted", "quota"))


def _provider_retry_attempts(provider: ContentLLMProvider) -> int:
    explicit = os.getenv("CONTENT_GENERATION_PROVIDER_RETRY_ATTEMPTS", "").strip()
    if explicit.isdigit():
        return max(0, int(explicit))
    if provider.name == "gemini":
        return 1
    return 0


def _provider_retry_delay_seconds(provider: ContentLLMProvider, attempt: int) -> float:
    explicit = os.getenv("CONTENT_GENERATION_PROVIDER_RETRY_DELAY_SECONDS", "").strip()
    if explicit:
        try:
            return max(0.0, float(explicit))
        except ValueError:
            pass
    if provider.name == "gemini":
        return min(3.0, float(attempt))
    return 0.0


def _should_retry_provider(provider: ContentLLMProvider, exc: Exception) -> bool:
    return provider.name == "gemini" and _is_retryable_rate_limit_error(exc)


def _normalize_chat_completion_kwargs(actual_model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(kwargs)
    model_name = (actual_model or "").strip().lower()
    if model_name.startswith("gpt-5"):
        if "max_tokens" in normalized and "max_completion_tokens" not in normalized:
            normalized["max_completion_tokens"] = normalized.pop("max_tokens")
        if "temperature" in normalized and normalized.get("temperature") != 1:
            normalized.pop("temperature", None)
    return normalized


def _should_fallback_provider(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    message = str(exc).lower()
    if status_code in {401, 402, 403, 404, 408, 409, 429, 500, 502, 503, 504}:
        return True
    fallback_signals = (
        "insufficient_quota",
        "resource_exhausted",
        "quota",
        "billing",
        "credit",
        "api key",
        "authentication",
        "connection refused",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "overloaded",
        "model not found",
        "does not exist",
        "max retries exceeded",
    )
    return any(signal in message for signal in fallback_signals)


def _provider_timeout_seconds(provider_name: str, req: "ContentGenerationRequest | None" = None) -> float | None:
    uses_email_policy = _request_uses_email_provider_policy(req)
    candidates: List[str] = []
    if uses_email_policy:
        candidates.extend(
            [
                os.getenv(f"CONTENT_GENERATION_EMAIL_{provider_name.upper()}_TIMEOUT_SECONDS", "").strip(),
                os.getenv("CONTENT_GENERATION_EMAIL_PROVIDER_TIMEOUT_SECONDS", "").strip(),
            ]
        )
    candidates.extend(
        [
            os.getenv(f"CONTENT_GENERATION_{provider_name.upper()}_TIMEOUT_SECONDS", "").strip(),
            os.getenv("CONTENT_GENERATION_PROVIDER_TIMEOUT_SECONDS", "").strip(),
        ]
    )
    for raw in candidates:
        if not raw:
            continue
        try:
            timeout_seconds = float(raw)
        except ValueError:
            continue
        if timeout_seconds > 0:
            return timeout_seconds
    return 12.0 if uses_email_policy else 45.0


def _content_provider_order_for_request(req: "ContentGenerationRequest | None" = None) -> List[str]:
    if _request_uses_email_provider_policy(req):
        return _default_email_content_provider_order()
    return _default_content_provider_order()


def get_openai_client(req: "ContentGenerationRequest | None" = None):
    """Get routed LLM client for content generation."""
    import openai

    providers: List[ContentLLMProvider] = []
    for provider_name in _content_provider_order_for_request(req):
        if not _provider_is_configured(provider_name):
            continue
        timeout_seconds = _provider_timeout_seconds(provider_name, req)
        if provider_name == "codex":
            codex_api_key = os.getenv("CONTENT_GENERATION_CODEX_API_KEY") or os.getenv("OPENAI_API_KEY")
            codex_base_url = _normalize_openai_base_url(os.getenv("CONTENT_GENERATION_CODEX_BASE_URL", ""))
            codex_fast_model = _validated_generation_model(
                os.getenv("CONTENT_GENERATION_CODEX_FAST_MODEL", "gpt-5.4-mini")
            )
            codex_editor_model = _validated_generation_model(
                os.getenv("CONTENT_GENERATION_CODEX_EDITOR_MODEL", codex_fast_model)
            )
            client_kwargs: Dict[str, Any] = {
                "api_key": codex_api_key,
                "timeout": timeout_seconds,
                # The provider router owns retries and fallback.  Hidden SDK
                # retries defeat its bounded attempt and timeout receipts.
                "max_retries": 0,
            }
            if codex_base_url:
                client_kwargs["base_url"] = codex_base_url
            providers.append(
                ContentLLMProvider(
                    name="codex",
                    client=openai.OpenAI(**client_kwargs),
                    fast_model=codex_fast_model,
                    editor_model=codex_editor_model,
                )
            )
            continue
        if provider_name == "openai":
            openai_fast_model = _validated_generation_model(
                os.getenv("CONTENT_GENERATION_OPENAI_FAST_MODEL", "gpt-4o-mini")
            )
            openai_editor_model = _validated_generation_model(
                os.getenv(
                    "CONTENT_GENERATION_OPENAI_EDITOR_MODEL",
                    os.getenv("CONTENT_GENERATION_EDITOR_MODEL", "gpt-4o-mini"),
                )
            )
            providers.append(
                ContentLLMProvider(
                    name="openai",
                    client=openai.OpenAI(
                        api_key=os.getenv("OPENAI_API_KEY"),
                        # Do not inherit OPENAI_BASE_URL: that implicit SDK
                        # override could redirect this allowed provider name to
                        # a retired local OpenAI-compatible model server.
                        base_url="https://api.openai.com/v1/",
                        timeout=timeout_seconds,
                        max_retries=0,
                    ),
                    fast_model=openai_fast_model,
                    editor_model=openai_editor_model,
                )
            )
            continue
        if provider_name == "gemini":
            gemini_base_url = _normalize_openai_base_url(
                os.getenv(
                    "GEMINI_OPENAI_BASE_URL",
                    "https://generativelanguage.googleapis.com/v1beta/openai/",
                )
            )
            gemini_fast_model = _validated_generation_model(
                os.getenv("CONTENT_GENERATION_GEMINI_FAST_MODEL", "gemini-2.5-flash")
            )
            gemini_editor_model = _validated_generation_model(
                os.getenv("CONTENT_GENERATION_GEMINI_EDITOR_MODEL", gemini_fast_model)
            )
            providers.append(
                ContentLLMProvider(
                    name="gemini",
                    client=openai.OpenAI(
                        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
                        base_url=gemini_base_url,
                        timeout=timeout_seconds,
                        max_retries=0,
                    ),
                    fast_model=gemini_fast_model,
                    editor_model=gemini_editor_model,
                )
            )
            continue
    if not providers:
        raise ValueError(
            "No reliable content-generation provider is configured. Set GEMINI_API_KEY, "
            "OPENAI_API_KEY, or CONTENT_GENERATION_CODEX_API_KEY. Local Llama-family "
            "generation is retired and cannot be enabled by provider-order configuration."
        )
    return ContentLLMRouterClient(providers)


def _final_editor_model() -> str:
    return CONTENT_EDITOR_MODEL_ALIAS


def _use_compact_staged_generation(client: Any, *, content_type: str) -> bool:
    if content_type != "linkedin_post":
        return False
    explicit = (os.getenv("CONTENT_GENERATION_COMPACT_STAGED_MODE") or "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    providers = getattr(client, "providers", []) or []
    primary_provider = str(getattr(providers[0], "name", "")).lower() if providers else ""
    return primary_provider == "gemini"


def _split_example_references(example_chunks: List[Dict[str, Any]], *, limit: int = 3) -> tuple[List[str], List[str]]:
    good_examples: List[str] = []
    avoid_examples: List[str] = []
    for item in example_chunks[:limit]:
        chunk = " ".join(str(item.get("chunk") or "").split()).strip()
        if not chunk:
            continue
        normalized = chunk.lower()
        if normalized.startswith(("avoid patterns:", "avoid fillers:")):
            avoid_examples.append(chunk[:500])
        else:
            good_examples.append(chunk[:500])
    return good_examples, avoid_examples


def build_content_prompt(
    topic: str,
    context: str,
    content_type: str,
    category: str,
    pacer_elements: List[str],
    tone: str,
    persona_chunks: List[Dict],
    example_chunks: List[Dict],
    audience: str = "general",
    topic_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    eligible_story_chunks: Optional[List[Dict[str, Any]]] = None,
    proof_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    grounding_mode: Optional[str] = None,
    grounding_reason: Optional[str] = None,
    framing_modes: Optional[List[str]] = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    disallowed_moves: Optional[List[str]] = None,
    option_count: Literal[1, 3] = 1,
) -> str:
    """Build the prompt for content generation."""
    if option_count not in {1, 3}:
        raise ValueError("content generation supports one canonical option or three legacy options")
    audience_label = _audience_prompt_label(audience)
    topic_anchor_chunks = topic_anchor_chunks or select_topic_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    eligible_story_chunks = eligible_story_chunks or select_eligible_story_chunks(persona_chunks, topic=topic, audience=audience, limit=3)
    proof_anchor_chunks = proof_anchor_chunks or select_proof_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    primary_claims = primary_claims or []
    proof_packets = proof_packets or []
    story_beats = story_beats or []
    topic_anchor_text = _prompt_topic_anchor_text(
        topic_anchor_chunks=topic_anchor_chunks,
        primary_claims=primary_claims,
        limit=4,
    )
    eligible_story_text = _prompt_story_anchor_text(
        story_anchor_chunks=eligible_story_chunks,
        story_beats=story_beats,
        limit=3,
    ) if eligible_story_chunks or story_beats else "- No directly relevant story anchor found. Do not force one."
    proof_anchor_text = _prompt_proof_anchor_text(
        proof_anchor_chunks=proof_anchor_chunks,
        proof_packets=proof_packets,
        limit=4,
    ) if proof_anchor_chunks or proof_packets else "- No strong proof anchor found. Stay concrete about process and role."
    topic_focus_guidance = build_topic_focus_guidance(
        topic=topic,
        audience=audience,
        eligible_story_chunks=eligible_story_chunks,
    )
    proof_guidance = build_proof_guidance(proof_anchor_chunks)
    grounding_mode = grounding_mode or ("proof_ready" if proof_anchor_chunks else "principle_only")
    grounding_reason = grounding_reason or (
        "Concrete proof anchors are available, so the post can lead with real evidence."
        if proof_anchor_chunks
        else "No strong proof anchor was found, so the post should stay principle-led."
    )
    approved_framing_modes = framing_modes or ["operator_lesson", "contrarian_reframe", "reframe"]
    framing_modes_text = "\n".join(
        f"- `{mode}`: {FRAMING_MODE_GUIDANCE.get(mode, mode.replace('_', ' '))}"
        for mode in approved_framing_modes
    )
    disallowed_moves = disallowed_moves or []
    primary_claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- No primary claims were pre-composed. Stay tightly inside the topic anchors."
    proof_packets_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No approved proof packets. Use principle only."
    story_beats_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No story beat approved for this request."
    disallowed_moves_text = "\n".join(f"- {move}" for move in disallowed_moves) or "- No extra banned moves."
    approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    approved_reference_text = "\n".join(f"- {term}" for term in approved_reference_terms) or "- No approved named references."
    voice_directives = _extract_voice_directives(persona_chunks, limit=8)
    voice_directives_text = "\n".join(f"- {directive}" for directive in voice_directives)
    option_framing_plan = _build_option_framing_plan(
        framing_modes=approved_framing_modes,
        primary_claims=primary_claims,
        proof_packets=proof_packets,
        story_beats=story_beats,
        option_count=option_count,
    )
    option_framing_plan_text = _render_option_framing_plan(option_framing_plan)
    option_plan_heading = (
        "## OPTION FRAMING PLAN (follow this for the canonical post):"
        if option_count == 1
        else "## OPTION FRAMING PLAN (follow this so the three options do not collapse into one shape):"
    )
    option_grounding_instruction = (
        "Ground the canonical post in the topic anchors first. Biography is support, not the main point."
        if option_count == 1
        else "Ground every option in the topic anchors first. Biography is support, not the main point."
    )
    option_proof_instruction = (
        "The canonical post must include at least one concrete proof anchor, named system, or explicit operating signal from the proof anchors above when available."
        if option_count == 1
        else "Each option must include at least one concrete proof anchor, named system, or explicit operating signal from the proof anchors above when available."
    )
    option_generation_instruction = (
        "Generate exactly 1 canonical content option. Do not generate hidden alternatives or a second thesis."
        if option_count == 1
        else "Generate 3 different options with varying hooks/angles."
    )
    option_framing_instruction = (
        "Use the single approved framing mode in the OPTION FRAMING PLAN."
        if option_count == 1
        else "Use a different approved framing mode for each option so the three drafts do not collapse into one flat shape."
    )
    option_plan_instruction = (
        "Follow the OPTION FRAMING PLAN. The canonical post must keep one hook, posture, and payoff."
        if option_count == 1
        else "Follow the OPTION FRAMING PLAN above. Option 1, 2, and 3 should feel materially different in hook, posture, and payoff."
    )
    option_claim_instruction = (
        "Pick one PRIMARY CLAIM for the canonical post and stay inside it. Do not merge multiple weak ideas together."
        if option_count == 1
        else "Pick one PRIMARY CLAIM per option and stay inside it. Do not merge multiple weak ideas together."
    )
    option_proof_ready_instruction = (
        "If `proof_ready`, the canonical post must use one APPROVED PROOF PACKET faithfully. Keep the original subject and meaning intact."
        if option_count == 1
        else "If `proof_ready`, each option must use one APPROVED PROOF PACKET faithfully. Keep the original subject and meaning intact."
    )
    output_instruction = (
        "Generate exactly 1 canonical content option. Output only that option; do not use an option separator:"
        if option_count == 1
        else 'Generate 3 content options, separated by "---OPTION---":'
    )
    
    visible_persona_chunks = _collect_prompt_visible_chunks(
        persona_chunks=persona_chunks,
        topic_anchor_chunks=topic_anchor_chunks,
        eligible_story_chunks=eligible_story_chunks,
        proof_anchor_chunks=proof_anchor_chunks,
        topic=topic,
        audience=audience,
    )

    # Group visible chunks by prompt layer so canon stays ahead of support, without flooding the prompt with off-topic history.
    persona_sections: Dict[str, List[str]] = {}
    for c in visible_persona_chunks:
        tag = str(c.get("persona_tag", "GENERAL")).replace("_", " ").title()
        section = str(_item_metadata(c).get("prompt_section") or "RETRIEVAL SUPPORT")
        chunk_text = _render_anchor_chunk(c)
        if not chunk_text:
            continue
        persona_sections.setdefault(section, []).append(f"- [{tag}] {chunk_text}")

    persona_parts = []
    for section in PROMPT_SECTION_ORDER:
        chunks = persona_sections.get(section)
        if chunks:
            persona_parts.append(f"### {section}\n" + "\n".join(chunks))
    persona_text = "\n\n".join(persona_parts)
    
    good_examples, avoid_examples = _split_example_references(example_chunks, limit=3)
    good_examples_text = "\n---\n".join(good_examples) if good_examples else "No additional positive examples available."
    avoid_examples_text = "\n---\n".join(avoid_examples) if avoid_examples else "No additional avoid-pattern examples available."
    
    # Anti-AI writing filter
    anti_ai_rules = """
## CRITICAL WRITING RULES - FOLLOW STRICTLY

NEVER use generic LLM patterns such as:
- "In today's world", "In today's fast-paced", "In the realm of"
- "Furthermore", "Moreover", "Additionally", "However"
- "Let's dive into", "Let's explore", "Let's unpack"
- "This is important because", "It's worth noting"
- "At the end of the day", "When it comes to"
- "I'm excited to", "I'm thrilled to", "I'm passionate about"
- "Game-changer", "Leverage", "Synergy", "Paradigm shift"
- Corporate buzzwords and emotionally flat summaries
- Obvious transitional phrases

Emulate human writing style:
- Direct, clear, and confident
- Short sentences when emphasizing key ideas
- Precise and concrete language
- No filler transitions
- Vary sentence length to feel human
- Lead with insight, not recap
- Avoid AI cadence

CRITICAL STYLE RULES:
- Open with a HOOK that creates tension or reframes a common belief
- Use short, punchy sentences for emphasis
- Break lines for rhythm and visual impact
- Be specific and concrete, not abstract
- End with a question that invites engagement
- Avoid soft recap openings
- NO generic statements like "It's a chance to reflect"
- Lead with INSIGHT, not setup

VOICE SOURCE RULES:
- Treat the approved examples supplied with this request as the only authority for personal rhythm and phrasing
- Never turn an illustrative instruction into a first-person fact
- Use only names, places, relationships, metrics, and events that appear in eligible evidence
- If the approved examples are missing, stay neutral and request stronger evidence instead of imitating a private biography
- Tighten every sentence and make every word earn its place
"""

    # Channel-specific examples - USE REAL POSTS FROM PERSONA, not fabricated stories
    channel_examples = {
        "linkedin_post": """
Use the knowledge-base examples below as the primary post references.

Match their rhythm:
- strong hook up top
- short line breaks
- specific names, systems, and stakes
- recognition where it is earned
- a clean close, not a generic recap

VOICE RULES:
- Derive openers, pivots, emphasis, rhythm, and closers from the approved examples supplied with this request
- Each option must use a meaningfully different opener
- Never invent a signature phrase or assume an old example is still approved
- Use recognition or tags only when the named person and relationship are present in eligible evidence
- Use approved examples for rhythm and specificity, never for copy-paste
""",
        "cold_email": """
EMAIL STYLE RULES (based on this person's voice):

Structure:
- Personal connection in opening
- Short paragraphs, easy to skim
- Reflective tone, not salesy
- One clear CTA
- "Warmly" or similar human closing

Voice markers to include:
- Use the supplied approved examples to determine personal voice
- Direct, confident language when supported by those examples
- Reference real experiences only when they appear in the approved persona evidence for this request
- NO corporate jargon
- Authentic, not overly polished

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
""",
        "email_reply": """
EMAIL REPLY STYLE (thread-grounded):

Structure:
- answer the actual message
- short skimmable paragraphs
- one clear next step
- no social-post rhythm

Voice markers:
- direct and warm
- grounded in the sender's request
- no invented familiarity
- no jargon-heavy filler

Rules:
- do not fabricate pricing, compliance posture, or prior relationship
- do not force personal-story framing
- preserve a clean professional close
""",
        "email_follow_up": """
EMAIL FOLLOW-UP STYLE:

Structure:
- quickly re-anchor the thread
- clarify the one thing needed next
- keep the ask narrow

Voice markers:
- concise
- warm but direct
- operational, not salesy

Rules:
- assume the recipient is skimming
- one concrete CTA only
- do not restate the entire thread
""",
        "outbound_email": """
OUTBOUND EMAIL STYLE:

Structure:
- specific opener
- why this outreach is relevant
- one clear ask

Voice markers:
- personal and credible
- no corporate jargon
- no generic cold-pitch cadence

Rules:
- stay contextual
- do not oversell
- keep the note easy to scan
""",
        "linkedin_dm": """
LINKEDIN DM STYLE (based on this person's voice):

Structure:
- Opens casual ("Hey —" or similar)
- Short, under 10 seconds to read
- Personal detail from REAL experiences
- Ends with genuine question
- NO pitch, NO ask for a call

Voice markers:
- Casual but professional when supported by the approved examples
- Reference real work only when it appears in the approved persona evidence for this request
- Feels like a message from a friend

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
""",
        "instagram_post": """
INSTAGRAM STYLE (based on this person's voice):

Structure:
- Opens with short punchy line
- **Bold** key statements
- Stacked short phrases for rhythm
- Emoji sparingly at end (🙏, 💜, ✨)
- Ends with question or reflection

Voice markers:
- Casual, warm, authentic when supported by the approved examples
- Reference real experiences
- Personal but not oversharing

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
"""
    }
    
    channel_example = channel_examples.get(content_type, "")
    
    # Audience-specific guidance with examples
    audience_guidance = {
        "general": """TARGET AUDIENCE: General professional audience
- Write for smart professionals across industries
- Use clear, accessible language
- Focus on universal themes: growth, reflection, connection
- Avoid niche jargon""",

        "education_admissions": """TARGET AUDIENCE: Education & Admissions professionals
- Speak to enrollment managers, admissions counselors, program directors
- Reference: yield optimization, pipeline management, student recruitment, family conversations
- Focus on BUSINESS of education, not teaching/classroom
- Use operator language only when approved evidence shows direct responsibility

HOOK RULE:
- Replace broad education commentary with one approved observation, action, or consequence

EVIDENCE RULE:
- Draw only from eligible story anchors and proof supplied for this request
- Never infer an employer, institution, metric, identity trait, or personal history""",

        "tech_ai": """TARGET AUDIENCE: Tech & AI professionals
- Speak to builders, founders, operators who use AI as a tool
- Reference: shipping, automation, building in public, efficiency
- Focus on practical applications, not hype
- Claim building, shipping, or iteration only when the approved evidence proves it

HOOK RULE:
- Replace generic AI commentary with one approved implementation detail, failure, test, or operating consequence

SPECIFIC STORIES TO DRAW FROM:
- Only use a story if it appears in the eligible story anchors below
- Prefer operator proof: workflow clarity, prompting, automation, handoffs, shipped systems
- Only use institutions, employers, or named projects when they appear directly in the approved proof or story anchors for this request""",

        "fashion": """TARGET AUDIENCE: Fashion & Style enthusiasts
- Use visual, sensory language
- Reference: personal style, wardrobe, self-expression, confidence
- Keep it relatable, not high-fashion exclusive
- Style is identity, not vanity

HOOK RULE:
- Use one concrete, approved wardrobe observation and explain the observable lesson without inventing a relationship or memory

EVIDENCE RULE:
- Draw only from eligible story anchors and proof supplied for this request
- Never invent a family story, origin story, purchase history, or product name""",

        "leadership": """TARGET AUDIENCE: Leaders & Managers
- Speak to people who manage teams and navigate organizational complexity
- Reference: coaching, developing people, driving results, decision-making
- Focus on practical leadership, not theoretical
- Claim management scope, targets, or culture work only when the approved evidence proves it

HOOK RULE:
- Replace generic leadership advice with one approved decision, behavior change, or operating consequence

EVIDENCE RULE:
- Draw only from eligible story anchors and proof supplied for this request
- Never invent team size, past employers, coaching stories, metrics, or named frameworks""",

        "neurodivergent": """TARGET AUDIENCE: Neurodivergent community & supporters
- Speak to families, professionals, and neurodivergent individuals
- Reference: different learning styles, finding the right fit, accommodations
- Never infer the author's health, disability, diagnosis, family relationship, or lived identity
- Use first-person identity framing only when the approved evidence explicitly authorizes it for this request

HOOK RULE:
- Replace generalized advocacy with one approved observation or consequence, without inventing a diagnosis or student story

EVIDENCE RULE:
- Draw only from eligible story anchors and proof supplied for this request
- Never infer a health, disability, family, student, or employment fact""",

        "entrepreneurs": """TARGET AUDIENCE: Entrepreneurs & Founders
- Speak to people building something from scratch
- Reference: shipping, pivoting, customer discovery, building in public
- Focus on action and results, not theory
- Describe a named product or venture only when it appears in approved proof for this request

HOOK RULE:
- Replace generic founder advice with one approved product decision, test, customer observation, or operating consequence

EVIDENCE RULE:
- Draw only from eligible story anchors and proof supplied for this request
- Never invent a venture, employer, institution, nonprofit, or founder origin story"""
    }
    
    audience_context = audience_guidance.get(audience, audience_guidance["general"])
    
    # Owner-approved FEEZIE intent guidance.
    category_guidance = {
        "value": """VALUE CONTENT (9 out of 11 posts)
Pure value. Teaching, insights, observations. NO selling. Make them smarter.

PURPOSE: Build authority and trust. Give without asking.

VALUE HOOK RULE:
- Lead with one approved observation, tension, decision, or consequence instead of a numbered-tip or generic-advice opener

VALUE CONTENT RULES:
- Lead with the insight, not the setup
- Share frameworks, not platitudes
- Use specific numbers and outcomes
- End with reflection or question, NOT a pitch
- NO "DM me" or "link in bio" on value posts""",

        "invitation": """INVITATION CONTENT (1 out of 11 posts)
Make one clear, relevant invitation without turning the post into a generic sales pitch.

PURPOSE: Convert earned attention into a useful next conversation, test, collaboration, event, or product-feedback loop.

EXAMPLE INVITATION HOOKS:
❌ "I'm excited to announce my new project."
✅ "I'm testing one part of a product with the people who experience this problem most often."

❌ "If you're interested in learning more about my services..."
✅ "If you are building AI into a real operating workflow, I want to compare where the handoff still breaks."

❌ "I'd love to connect with anyone who might benefit from this."
✅ "I'm looking for five people willing to test this decision flow and tell me where it becomes confusing."

INVITATION CONTENT RULES:
- Lead with a useful belief, build, test, or consequence; do not lead with a consulting pitch
- Be specific about who the invitation is for and why their participation matters
- Use a bounded CTA: beta test, product feedback, collaboration, event, speaking, or relevant conversation
- Do not imply a public job search, exit from education, or employer endorsement
- No fabricated scarcity, inflated proof, or vague "DM me" engagement bait
- The post must still deliver value even if the reader never accepts the invitation.""",

        "personal": """PERSONAL CONTENT (1 out of 11 posts)
Behind-the-scenes. The real you. Struggles included. Vulnerability builds trust.

PURPOSE: Humanize yourself. Let people connect with the person, not just the professional.

PERSONAL HOOK RULE:
- Start inside one approved moment, object, decision, or consequence
- Never invent a relative, hometown, institution, identity detail, struggle, or personal history

PERSONAL CONTENT RULES:
- Specific details: names, places, objects, moments
- Show the struggle, not just the win
- Vulnerability, not oversharing
- Connect personal story to broader meaning
- End with reflection or question that invites others to share"""
    }
    
    # Channel-specific system prompts - PRESERVE AUTHENTIC VOICE
    channel_prompts = {
        "linkedin_post": """You write LinkedIn posts grounded in the approved private voice context supplied with this request.

VOICE PRESERVATION (CRITICAL):
- Derive casual markers, rhythm, hooks, recognition patterns, and closers from the approved examples
- Never invent a signature phrase when the approved examples do not support it
- Keep natural spoken language when the examples support it
- DO NOT make it sound corporate or generic

Tone:
- confident and direct
- warm and casual (NOT stiff or formal)
- grounded in real experience
- punchy, not verbose

Writing rules:
- lead with insight or hook, not setup
- vary sentence length
- short paragraphs (1-3 sentences)
- use REAL stories from persona data
- end with question or reflection
- hashtags grouped at end

Voice audit:
- Does it sound like the approved LinkedIn examples?
- Are only evidenced voice markers preserved?
- Is the rhythm punchy, not flat?
- Would this person actually post this?""",

        "cold_email": """You write emails that are professional but still sound like THIS PERSON.

VOICE PRESERVATION:
- Keep direct, confident language
- Can include casual warmth
- Reference real experiences from persona
- NO corporate jargon

Tone:
- direct and confident
- warm but professional
- clean and human

Structure:
- strong opening
- short paragraphs
- one clear CTA
- human closing ("Warmly" etc.)

Voice audit:
- Does it sound authentic to this person?
- Is it direct without being cold?""",

        "email_reply": """You write email replies that are grounded in a live thread.

VOICE PRESERVATION:
- Keep direct, human language
- Be warm without sounding casual to the point of drift
- Stay anchored to what the sender actually asked
- NO fabricated relationship history
- NO unsupported promises or commitments

Tone:
- clear and competent
- skimmable
- operationally useful

Structure:
- acknowledge the message
- answer or clarify the next step
- end with one concrete CTA
- close like a real operator, not a marketer

Voice audit:
- Does this reply feel grounded in the actual thread?
- Does it avoid social-post cadence?
- Does it stay helpful without overcommitting?""",

        "email_follow_up": """You write follow-up emails that move a thread forward cleanly.

VOICE PRESERVATION:
- Keep the note short
- Re-anchor the last relevant point
- Ask for exactly one next-step item

Tone:
- warm
- direct
- efficient

Rules:
- no corporate filler
- no long recap paragraphs
- no invented urgency

Voice audit:
- Would a busy person read this quickly?
- Is the ask specific?
- Does it avoid sounding generic?""",

        "outbound_email": """You write proactive emails that are specific, contextual, and credible.

VOICE PRESERVATION:
- Keep direct, human language
- Reference real context only
- Avoid generic cold-email cliches

Tone:
- warm
- credible
- not overly polished

Structure:
- relevant opening
- tight reason for reaching out
- one clear CTA

Voice audit:
- Does this feel specific to the recipient?
- Is it direct without sounding templated?""",

        "linkedin_dm": """You write DMs that feel human, concise, and non-salesy.

VOICE PRESERVATION:
- Derive personal phrasing from approved examples only
- Short and punchy
- Reference real work from persona

Tone:
- casual and warm
- confident, not salesy
- conversational

Rules:
- under 10 seconds to read
- one question or insight
- NO pitch language
- feels personal

Voice audit:
- Would you send this to a friend?
- Is it too formal or stiff?""",

        "instagram_post": """You write Instagram captions grounded in the approved private voice context.

VOICE PRESERVATION:
- Derive personal phrasing from approved examples only
- Emojis sparingly (🙏 💜 ✨)
- Punchy rhythm, stacked phrases
- Personal but not oversharing

Tone:
- casual and thoughtful
- warm and authentic
- visually descriptive

Rules:
- short paragraphs, white space
- open with hook
- end with question or reflection
- NO brand voice, NO corporate

Voice audit:
- Does it sound like a real person?
- Is the rhythm natural?"""
    }
    
    channel_prompt = channel_prompts.get(content_type, channel_prompts["linkedin_post"])
    
    # PACER elements
    pacer_guidance = ""
    if pacer_elements:
        pacer_map = {
            "Problem": "Start by identifying a specific problem your audience faces",
            "Amplify": "Amplify the pain - what happens if they don't solve it?",
            "Credibility": "Establish why you're qualified to speak on this",
            "Educate": "Provide actionable value and insights",
            "Request": "End with a clear call-to-action"
        }
        pacer_guidance = "Include these PACER elements:\n" + "\n".join([f"- {p}: {pacer_map.get(p, '')}" for p in pacer_elements])
    
    prompt = f"""{anti_ai_rules}

{channel_prompt}

{channel_example}

---

{audience_context}

---

## PERSONA STACK (core canon first, then support, then legacy):
{persona_text if persona_text else "No persona data available - use a professional, authentic voice."}

## TOPIC ANCHORS (highest priority):
{topic_anchor_text}

## ELIGIBLE STORY / PROOF ANCHORS:
{eligible_story_text}

## PROOF ANCHORS:
{proof_anchor_text}

## GOOD STYLE REFERENCES:
{good_examples_text}
- Borrow shape, rhythm, conviction, and pacing from these.
- Do not borrow facts or named stories unless they also appear in the PERSONA STACK / ANCHORS above.

## AVOID PATTERN REFERENCES:
{avoid_examples_text}
- Treat these as anti-patterns.
- Do not reproduce their sentence shapes, generic framing, or consultant language.

## CONTENT REQUEST:
- **Topic:** {topic}
- **Context:** {context or "General"}
- **Audience:** {audience_label}
- **Category:** {category.upper()} - {category_guidance.get(category, "")}

CRITICAL: The content MUST be about "{topic}". 
- If the topic is a PERSON'S NAME: The post MUST mention them BY NAME multiple times. Feature them prominently - share what you learned from them, celebrate their work, or tell a story involving them. Do NOT write a generic post that ignores the person.
- If the topic is a concept: The post should explore that concept directly.

IMPORTANT: If Context is provided above (not "General"), you MUST incorporate that specific context into the content. Reference the situation, event, or details mentioned in the context directly.

{pacer_guidance}

## TOPIC DISCIPLINE:
{topic_focus_guidance}

## PROOF DISCIPLINE:
{proof_guidance}

## GROUNDING MODE:
- Current mode: `{grounding_mode}`
- {grounding_reason}
- This mode controls what kind of claim is allowed. Do not upgrade weak support into hard proof.
- `proof_ready`: use named systems, artifacts, and evidence only from TOPIC / PROOF anchors.
- `story_supported`: use at most one eligible story and keep it tied to the operating lesson.
- `principle_only`: do not reach for named projects, employers, metrics, or case studies unless they already appear in the TOPIC anchors.

## APPROVED FRAMING MODES (preserve the legacy rhetorical edge):
{framing_modes_text}

{option_plan_heading}
{option_framing_plan_text}

## PRIMARY CLAIMS YOU MAY MAKE:
{primary_claims_text}

## APPROVED PROOF PACKETS:
{proof_packets_text}

## OPTIONAL STORY BEATS:
{story_beats_text}

## ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

## DISALLOWED MOVES:
{disallowed_moves_text}

## VOICE SHAPING RULES:
{voice_directives_text}

## NARRATIVE ARC (follow this structure):
1. **HOOK/CONTEXT** - Start with something relatable, surprising, or attention-grabbing. Use voice markers.
2. **OPERATING LESSON** - Build the post around a real lesson, framework, proof point, or experience from the topic anchors.
3. **REFLECTION/CTA** - Tie it back to the audience with insight or a question. End strong.

## INSTRUCTIONS:
1. Write AS this person using their actual experiences and perspectives.
2. Follow the 3-part structure above, but do NOT force a personal story when the topic anchors are principle-led.
3. {option_grounding_instruction}
4. Only use a personal anecdote if it appears in the eligible story/proof anchors above.
5. If there is no eligible story anchor, stay with proof, principle, and operating insight.
6. Start from one PRIMARY CLAIM as the strategic thesis of the post. Do not let a proof packet become the whole headline unless the primary claim itself is already phrased that way.
7. {option_proof_instruction}
8. If you use a metric, keep its original subject intact. Never convert a participation, utilization, or revenue metric into a generic productivity or completion-time claim.
9. Use proof packets to support the thesis, not to replace the thesis.
10. Be specific and actionable, not generic.
11. {option_generation_instruction}
10. Keep the writing vivid. Use tension, agreement, contrast, or drama only when it stays grounded in the approved framing modes above.
11. {option_framing_instruction}
12. {option_plan_instruction}
12. {option_claim_instruction}
13. {option_proof_ready_instruction}
14. If `principle_only`, do not mention named systems, employers, projects, or metrics unless they already appear in PRIMARY CLAIMS.
15. If a named reference is not in APPROVED PROOF PACKETS, OPTIONAL STORY BEATS, or ONLY THESE NAMED REFERENCES, remove it.
16. Use the VOICE SHAPING RULES above. Keep the language casual, sharp, and spoken. Do not flatten the writing into generic professional summaries.

## ANTI-HALLUCINATION RULES (CRITICAL):
- ONLY use anecdotes, stories, and facts that appear in the PERSONA section above
- If you need a personal story, it must come from the ELIGIBLE STORY / PROOF ANCHORS section above
- NEVER invent stories about family members, objects, or experiences not in the persona
- If no relevant anecdote exists, use a general reflection instead of fabricating
- Only reference named ventures, employers, systems, programs, or stories if they appear in the TOPIC / ELIGIBLE STORY / PROOF anchors above
- Do not reach into broad biography memory for extra names just because they are real somewhere else in the persona bundle
- Do not borrow a weakly related story just to make the post feel more personal

## VOICE MARKERS TO USE:
- "Yall" / "Y'all" as casual opener
- "Tell you what tho" as pivot
- "Say it with me: 🗣️" for engagement
- "Big shout-out to..." for recognition
- "Makes no sense. Period." for punchy closer
- "I'm here for it" for endorsement
- "#stayready" "#staytuned" for hashtags

Output only the content. No notes, no explanations.

{output_instruction}
"""
    
    return prompt


def parse_content_options(raw_content: str) -> List[str]:
    def _clean_option(text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(r"^#+\s*OPTION\s+\d+\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\*\*OPTION\s+\d+\*\*\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\*\*Option\s+\d+:\s*`[^`]+`\*\*\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^Option\s+\d+:\s*`?[^`\n]+`?\s*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _split_on_option_headings(text: str) -> List[str]:
        heading_pattern = re.compile(
            r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?\s*option\s+\d+(?::\s*`?[^`\n]+`?)?(?:\*\*)?\s*"
        )
        matches = list(heading_pattern.finditer(text))
        if len(matches) < 2:
            return []
        options: List[str] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            cleaned = _clean_option(text[start:end])
            if cleaned:
                options.append(cleaned)
        return options

    if "---OPTION 1---" in raw_content:
        options = re.split(r"---OPTION \d+---", raw_content)
        return [_clean_option(opt) for opt in options if opt.strip()]
    if "---OPTION---" in raw_content:
        return [_clean_option(opt) for opt in raw_content.split("---OPTION---") if opt.strip()]
    split_options = _split_on_option_headings(raw_content)
    if split_options:
        return split_options
    return [_clean_option(raw_content)] if raw_content.strip() else []


def _ensure_sentence(text: str) -> str:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return ""
    if normalized[-1] not in ".!?":
        normalized += "."
    return normalized


def _ensure_public_sentence(text: str) -> str:
    normalized = _ensure_sentence(text)
    if normalized and normalized[0].islower():
        normalized = normalized[0].upper() + normalized[1:]
    return normalized


def _split_sentences(text: str) -> List[str]:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return []
    return [segment.strip(" -") for segment in re.split(r"(?<=[.!?])\s+", normalized) if segment.strip()]


def plan_content_option_briefs(
    *,
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
    request_context: str = "",
    option_count: int = 1,
) -> List[ContentOptionBrief]:
    option_plan = _build_option_framing_plan(
        framing_modes=framing_modes,
        primary_claims=primary_claims,
        proof_packets=proof_packets,
        story_beats=story_beats,
        request_context=request_context,
        option_count=option_count,
    )
    briefs: List[ContentOptionBrief] = []
    for item in option_plan:
        try:
            option_number = int(str(item.get("option") or "1"))
        except ValueError:
            option_number = len(briefs) + 1
        briefs.append(
            ContentOptionBrief(
                option_number=option_number,
                framing_mode=str(item.get("mode") or "operator_lesson"),
                primary_claim=_ensure_sentence(str(item.get("claim") or "")),
                proof_packet=str(item.get("proof") or ""),
                story_beat=str(item.get("story") or ""),
                public_lane=str(item.get("lane") or _public_post_lane_for_option(option_number)),
                thesis_treatment=str(item.get("thesis_treatment") or ""),
                proof_progression=str(item.get("proof_progression") or ""),
                payoff=str(item.get("payoff") or ""),
                mechanism_focus=str(item.get("mechanism_focus") or ""),
                recognition_basis=str(item.get("recognition_basis") or ""),
                mechanism_anchor_terms=list(item.get("mechanism_anchor_terms") or []),
                recognition_anchor_terms=list(item.get("recognition_anchor_terms") or []),
                decision_rule_basis=str(item.get("decision_rule_basis") or ""),
                decision_moment_basis=str(item.get("decision_moment_basis") or ""),
                decision_moment_anchor_terms=list(item.get("decision_moment_anchor_terms") or []),
                required_context_concepts=str(item.get("required_context_concepts") or ""),
                consequence_basis=str(item.get("consequence_basis") or ""),
                application_closing_anchor_terms=list(
                    item.get("application_closing_anchor_terms") or []
                ),
                proof_facet_id=str(item.get("proof_facet_id") or ""),
                semantic_payload_version=str(item.get("semantic_payload_version") or ""),
            )
        )
    return briefs


def _render_content_option_briefs(briefs: List[ContentOptionBrief]) -> str:
    lines: List[str] = []
    for brief in briefs:
        lines.extend(
            [
                f"### OPTION {brief.option_number}",
                f"- Framing mode: `{brief.framing_mode}`",
                f"- Public post lane: `{brief.public_lane or _public_post_lane_for_option(brief.option_number)}`",
                f"- Strategic claim: {brief.primary_claim or 'Stay inside the topic anchors.'}",
                f"- Supporting proof: {_writer_brief_proof_text(brief.proof_packet) or 'No approved proof packet.'}",
                f"- Optional story beat: {brief.story_beat or 'No approved story beat.'}",
                f"- Thesis treatment: {brief.thesis_treatment or 'No distinct thesis treatment assigned.'}",
                f"- Proof progression: {brief.proof_progression or 'No distinct proof progression assigned.'}",
                f"- Payoff: {brief.payoff or 'No distinct payoff assigned.'}",
            ]
        )
        if brief.mechanism_anchor_terms:
            lines.append(f"- Mechanism anchor terms: {', '.join(brief.mechanism_anchor_terms)}")
        if brief.recognition_anchor_terms:
            lines.append(f"- Recognition anchor terms: {', '.join(brief.recognition_anchor_terms)}")
        if brief.decision_moment_anchor_terms:
            lines.append(
                f"- Decision moment anchor terms: {', '.join(brief.decision_moment_anchor_terms)}"
            )
        if brief.application_closing_anchor_terms:
            lines.append(
                "- Application closing anchor terms: "
                + ", ".join(brief.application_closing_anchor_terms)
            )
        for value, label in (
            (brief.mechanism_focus, "Mechanism focus"),
            (brief.recognition_basis, "Recognition basis"),
            (brief.decision_rule_basis, "Decision-rule basis"),
            (brief.decision_moment_basis, "Decision moment basis"),
            (brief.required_context_concepts, "Required context concepts"),
            (brief.consequence_basis, "Consequence basis"),
            (brief.proof_facet_id, "Proof facet ID"),
        ):
            if str(value or "").strip():
                lines.append(f"- {label}: {str(value).strip()}")
    return "\n".join(lines)


def _normalized_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _audience_prompt_label(audience: str) -> str:
    normalized = " ".join((audience or "").lower().split()).strip()
    if not normalized:
        return "General professionals"
    label = AUDIENCE_PROMPT_LABELS.get(normalized)
    if label:
        return label
    return normalized.replace("_", " ").replace("-", " ").title()


def _rewrite_audience_slug_public_copy(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    rewritten = cleaned
    replacements = (
        (r"\btech_ai leads?\b", "AI leaders"),
        (r"\btech_ai builders?\b", "tech and AI builders"),
        (r"\btech_ai founders?\b", "tech and AI founders"),
        (r"\btech_ai operators?\b", "tech and AI operators"),
        (r"\btech_ai teams?\b", "tech and AI teams"),
        (r"\btech_ai workflows?\b", "AI workflows"),
        (r"\btech_ai\b", "tech and AI teams"),
        (r"\beducation_admissions\b", "education and admissions"),
        (r"\bleadership_management\b", "leadership and management"),
    )
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    return rewritten


def _proof_packet_evidence_text(packet: str) -> str:
    parts = (packet or "").split("->", 1)
    text = parts[1].strip() if len(parts) == 2 else (packet or "").strip()
    text = text.split(" Use when:", 1)[0]
    text = re.sub(r"^(?:wins?|initiative|proof|story|example):\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _proof_packet_label(packet: str) -> str:
    parts = (packet or "").split("->", 1)
    return parts[0].strip() if len(parts) == 2 else ""


def _reference_is_publicly_nameable(reference: str) -> bool:
    normalized = " ".join((reference or "").split()).strip(" .")
    if not normalized or _phrase_is_flat_label(normalized):
        return False
    if re.search(
        r"\b(?:anonymous|anonymized|private|redacted|synthetic|test)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\b(?:claim|evidence|example|observation|packet|proof|story)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return False
    return True


def _writer_brief_proof_text(packet: str) -> str:
    label = _proof_packet_label(packet)
    if label and _reference_is_publicly_nameable(label):
        return (packet or "").strip()
    return _proof_packet_evidence_text(packet)


def _looks_like_malformed_reference_bridge(sentence: str) -> bool:
    normalized = " ".join((sentence or "").split()).strip()
    if not normalized:
        return False
    if not re.search(r"\bmakes this concrete\.?$", normalized, flags=re.IGNORECASE):
        return False
    label = re.sub(r"\bmakes this concrete\.?$", "", normalized, flags=re.IGNORECASE).strip(" .")
    if not label:
        return True
    lowered = label.lower()
    if lowered.startswith(("from ", "and ", "but ", "so ", "because ", "during ", "after ", "before ")):
        return True
    tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*", label)
    if not tokens:
        return True
    allowed = {"a", "an", "and", "at", "for", "from", "in", "of", "on", "the", "to", "vs"}
    titled = 0
    for token in tokens:
        token_lower = token.lower()
        if token_lower in allowed:
            continue
        if token[:1].isupper() or token.isupper():
            titled += 1
            continue
        return True
    return titled == 0


def _looks_like_identity_scaffold(sentence: str) -> bool:
    normalized = " ".join((sentence or "").split())
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in IDENTITY_SCAFFOLD_PATTERNS)


def _append_approved_reference(approved: List[str], seen: set[str], phrase: str | None) -> None:
    normalized_phrase = " ".join((phrase or "").split()).strip(" .")
    key = normalized_phrase.lower()
    if not normalized_phrase or len(key) < 3 or key in seen:
        return
    seen.add(key)
    approved.append(normalized_phrase)


def _collect_curated_reference_phrases(text: str) -> list[str]:
    normalized_text = " ".join((text or "").split())
    if not normalized_text:
        return []

    phrases: list[str] = []
    if re.search(r"\b\d", normalized_text):
        phrases.append(normalized_text.rstrip("."))
    phrases.extend(
        phrase.strip()
        for phrase in re.findall(
            r"(explicit handoffs|shared workspace state|proof-aware prompts|routed workspace snapshot|bundle-first content generation|long-form routing|daily briefs|workflow clarity|agent orchestration|AI systems operator|operator guidance|prompting plus agent usage|AI execution patterns)",
            normalized_text,
            flags=re.IGNORECASE,
        )
    )
    return phrases


def _phrase_is_flat_label(phrase: str) -> bool:
    normalized = " ".join((phrase or "").split()).strip(" .").lower()
    if not normalized:
        return True
    return normalized in {
        "agent orchestration",
        "daily briefs",
        "long-form routing",
        "planner",
        "persona review",
        "proof-aware prompts",
        "routed workspace snapshot",
        "shared workspace state",
        "workflow clarity",
        "operator guidance",
        "ai execution patterns",
        "ai systems operator",
    }


def _extract_approved_reference_terms(
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
) -> List[str]:
    approved: List[str] = []
    seen: set[str] = set()
    for packet in proof_packets:
        label = _proof_packet_label(packet)
        if _reference_is_publicly_nameable(label):
            _append_approved_reference(approved, seen, label)
        for phrase in _collect_curated_reference_phrases(_proof_packet_evidence_text(packet)):
            _append_approved_reference(approved, seen, phrase)
    for text in primary_claims + story_beats:
        for phrase in _collect_curated_reference_phrases(text):
            _append_approved_reference(approved, seen, phrase)
    return approved[:12]


def _option_has_named_reference_specificity(option: str, brief: ContentOptionBrief) -> bool:
    option_terms = _normalized_terms(option)
    if not option_terms:
        return False
    candidate_references = _extract_approved_reference_terms(
        [brief.primary_claim],
        [brief.proof_packet] if brief.proof_packet else [],
        [brief.story_beat] if brief.story_beat else [],
    )
    label = _proof_packet_label(brief.proof_packet)
    if _reference_is_publicly_nameable(label):
        candidate_references = [label] + candidate_references
    for reference in candidate_references:
        if not _reference_is_publicly_nameable(reference):
            continue
        reference_terms = _normalized_terms(reference)
        if len(reference_terms) < 2:
            continue
        if len(option_terms.intersection(reference_terms)) >= 2:
            return True
    return False


def _brief_requires_named_reference_specificity(brief: ContentOptionBrief) -> bool:
    return _reference_is_publicly_nameable(_proof_packet_label(brief.proof_packet))


def _render_public_post_guardrails() -> str:
    lines = [
        "- Stay inside the assigned PUBLIC POST LANE for each option.",
        f"- `market_insight`: {PUBLIC_POST_LANE_GUIDANCE['market_insight']}",
        f"- `operator_lesson`: {PUBLIC_POST_LANE_GUIDANCE['operator_lesson']}",
        f"- `build_in_public`: {PUBLIC_POST_LANE_GUIDANCE['build_in_public']}",
        "- Ban internal phrases like `persona soup`, `proof packet`, `typed lanes`, `domain gates`, or `green-or-red board`.",
        "- Never write about the author in third person. Do not open with `the owner is...`, `the owner treats...`, or `the owner is building...`.",
        "- Translate internal mechanics into public language: prefer `clear handoffs`, `clear ownership`, `context survived the handoff`, or `proof stayed attached` over `shared workspace state`, `typed retrieval`, `proof-aware prompts`, or `operating rhythm`.",
        "- If the topic is a market or competition claim, the first line must speak to that market claim directly. Do not pivot the opener into prompting, workflow, or tooling unless the topic itself is about that.",
        "- Use at most two concrete proof details in one option. If the proof contains many metrics or steps, choose the strongest one or two and stop.",
        "- Do not turn internal control logic or system plumbing into public copy.",
    ]
    return "\n".join(lines)


def build_planned_writer_prompt(
    *,
    topic: str,
    context: str,
    audience: str,
    grounding_mode: str,
    grounding_reason: str,
    topic_anchor_chunks: List[Dict[str, Any]],
    proof_anchor_chunks: List[Dict[str, Any]],
    story_anchor_chunks: List[Dict[str, Any]],
    briefs: List[ContentOptionBrief],
    good_examples: List[str],
    voice_directives: List[str],
    approved_references: List[str],
    disallowed_moves: List[str],
) -> str:
    option_count = max(len(briefs), 1)
    option_suffix = "" if option_count == 1 else "s"
    separator_instruction = (
        "Output only the canonical option; do not add an option heading or hidden alternative."
        if option_count == 1
        else f"Output only the {option_count} options, separated by ---OPTION---."
    )
    audience_label = _audience_prompt_label(audience)
    topic_anchor_text = _prompt_topic_anchor_text(
        topic_anchor_chunks=topic_anchor_chunks,
        primary_claims=[brief.primary_claim for brief in briefs if brief.primary_claim],
        limit=4,
    )
    proof_anchor_text = _prompt_proof_anchor_text(
        proof_anchor_chunks=proof_anchor_chunks,
        proof_packets=[brief.proof_packet for brief in briefs if brief.proof_packet],
        limit=3,
    )
    story_anchor_text = _prompt_story_anchor_text(
        story_anchor_chunks=story_anchor_chunks,
        story_beats=[brief.story_beat for brief in briefs if brief.story_beat],
        limit=2,
    )
    good_examples_text = "\n".join(f"- {example}" for example in good_examples[:2]) or "- No extra style references."
    voice_text = "\n".join(f"- {directive}" for directive in voice_directives[:8]) or "\n".join(
        f"- {directive}" for directive in DEFAULT_VOICE_DIRECTIVES[:6]
    )
    approved_reference_text = "\n".join(f"- {reference}" for reference in approved_references) or "- No approved named references."
    disallowed_text = "\n".join(f"- {move}" for move in disallowed_moves) or "- No extra banned moves."
    public_post_guardrails = _render_public_post_guardrails()
    briefs_text = _render_content_option_briefs(briefs)
    topic_specific_guardrails = []
    normalized_topic = " ".join((topic or "").lower().split())
    if audience == "education_admissions" and any(term in normalized_topic for term in ("faculty", "senate", "bill", "policy")):
        topic_specific_guardrails.append(
            "Keep the policy / school / faculty signal visible. Translate it for families and admissions, but do not turn the post into a generic community-marketing update."
        )
    if _is_student_support_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the student / family / support lens visible in every option. Do not let the copy drift into generic B2B trust or legacy-tech analogies."
        )
        topic_specific_guardrails.append(
            "If you talk about trust, make it family, student, or admissions trust. Do not use customer-language."
        )
    if any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants")):
        topic_specific_guardrails.append(
            "Keep the market / competition claim visible in the opener. Do not let the first line drift into workflow or prompting language unless the topic itself explicitly names workflow, prompting, or orchestration."
        )
    if _is_fashion_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the copy grounded in personal style, fit, confidence, and transformation. Do not drift into founder, leadership, or systems jargon unless the topic explicitly requires it."
        )
    if _is_entrepreneur_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the copy grounded in customers, product choices, and market tradeoffs. Do not drift into generic education or family language unless the topic explicitly requires it."
        )
    topic_specific_guardrail_text = "\n".join(f"- {line}" for line in topic_specific_guardrails) or "- No extra topic-specific guardrails."
    return f"""You are the writer stage in a planner -> writer -> critic content system.

Write exactly {option_count} LinkedIn post option{option_suffix}{', separated by ---OPTION---' if option_count > 1 else ''}.
Write one option for each planned brief below.

Topic: {topic}
Context: {context or "General"}
Audience: {audience_label}

GROUNDING MODE:
- `{grounding_mode}`
- {grounding_reason}

TOPIC ANCHORS:
{topic_anchor_text}

PROOF ANCHORS:
{proof_anchor_text}

APPROVED STORY ANCHORS:
{story_anchor_text}

GOOD STYLE REFERENCES:
{good_examples_text}

VOICE DIRECTIVES:
{voice_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

PUBLIC POST GUARDRAILS:
{public_post_guardrails}

DISALLOWED MOVES:
{disallowed_text}

TOPIC-SPECIFIC GUARDRAILS:
{topic_specific_guardrail_text}

PLANNED OPTION BRIEFS:
{briefs_text}

WRITER RULES:
- Use the planned strategic claim as the center of each option.
- Let proof support the claim. Do not let the proof packet become the whole headline unless the claim is already proof-shaped.
- Use casual, direct, spoken rhythm.
- Keep short paragraphs and line breaks.
- Stay specific and operator-grounded.
- Write in first person or direct thesis voice. Never describe the author from the outside in third person.
- Start faster. Lead with tension, contrast, recognition, warning, or operator insight.
- Make each option land differently. Do not collapse the options into the same hook or rhythm.
- Treat each brief's thesis treatment, proof progression, and payoff as a hard structural job. Do not copy those labels into public prose.
- When briefs share a claim or proof source, create difference through the assigned diagnosis, application, or boundary job; never invent another fact just to force variety.
- Do not use generic openings like "X is essential", "X is critical", "In today's world", or "Here's the takeaway".
- Do not use public-facing shorthand like `shared workspace state`, `shared state`, `typed retrieval`, `proof-aware prompts`, `operating rhythm`, or `AI Clone / Brain System`. Translate them into public language instead.
- If the topic is a market or competition claim, keep the opener on that claim. Do not switch the first line to prompting, workflow, or tooling unless the topic itself is about prompting, workflow, or orchestration.
- Do not invent stories, names, employers, or metrics.
- If no story is approved, do not force one.
- Borrow rhythm and shape from GOOD STYLE REFERENCES, not their facts.
- If a line sounds like generic LinkedIn advice, replace it with sharper operator language.
- Return exactly {option_count} complete option{option_suffix}{', each separated by ---OPTION---' if option_count > 1 else ''}.
- Do not add standalone filler fragments like "Why?", "This.", "That.", or a one-line restatement of the opener.
- Use at most one short punch line per option, and only if it adds new meaning.
- Do not stack multiple short contrast fragments before the proof.
- Do not use meta-directives like "Read that again" or "Write that down".
- Do not echo internal audience slugs like `tech_ai` or `education_admissions`.
- Do not use house scaffold lines like `That is the operating model.`, `That is where it breaks.`, or `Otherwise it's just another tab.`.

{separator_instruction}
"""


def build_local_codex_writer_prompt(
    *,
    topic: str,
    context: str,
    audience: str,
    grounding_mode: str,
    grounding_reason: str,
    topic_anchor_chunks: List[Dict[str, Any]],
    proof_anchor_chunks: List[Dict[str, Any]],
    story_anchor_chunks: List[Dict[str, Any]],
    briefs: List[ContentOptionBrief],
    voice_directives: List[str],
    approved_references: List[str],
    intent: str = "value",
    strategy_contract: Dict[str, Any] | None = None,
    classification: Dict[str, Any] | None = None,
    disallowed_moves: List[str] | None = None,
) -> str:
    intent = normalize_feezie_intent(intent, default="value")
    strategy_contract = dict(strategy_contract or {})
    classification = dict(classification or {})
    audience_label = _audience_prompt_label(audience)
    topic_anchor_text = _prompt_topic_anchor_text(
        topic_anchor_chunks=topic_anchor_chunks,
        primary_claims=[brief.primary_claim for brief in briefs if brief.primary_claim],
        limit=3,
    )
    proof_anchor_text = _prompt_proof_anchor_text(
        proof_anchor_chunks=proof_anchor_chunks,
        proof_packets=[brief.proof_packet for brief in briefs if brief.proof_packet],
        limit=2,
    )
    story_anchor_text = _prompt_story_anchor_text(
        story_anchor_chunks=story_anchor_chunks,
        story_beats=[brief.story_beat for brief in briefs if brief.story_beat],
        limit=1,
    )
    voice_text = "\n".join(f"- {directive}" for directive in voice_directives[:6]) or "\n".join(
        f"- {directive}" for directive in DEFAULT_VOICE_DIRECTIVES[:5]
    )
    approved_reference_text = "\n".join(f"- {reference}" for reference in approved_references[:8]) or "- No approved named references."
    briefs_text = _render_content_option_briefs(briefs)
    normalized_topic = " ".join((topic or "").lower().split())
    topic_specific_guardrails = []
    if any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants")):
        topic_specific_guardrails.append(
            "Keep the opener on the market / competition claim. Do not pivot line one into workflow or prompting unless the topic itself explicitly does that."
        )
        topic_specific_guardrails.append(
            "Do not use stock operator slogans like `That is the operating model.` or workflow-specific contrast lines like `Not more reporting. Clearer action.` in a market / competition post."
        )
    if audience == "education_admissions" and any(term in normalized_topic for term in ("faculty", "senate", "bill", "policy")):
        topic_specific_guardrails.append(
            "Keep the policy / faculty / school signal visible. Do not rewrite it into a generic leadership or family-experience post."
        )
    if _is_student_support_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the student / family / support lens visible. Do not borrow customer-trust or legacy-tech-cycle proof unless it clearly maps back to the student experience."
        )
    if _is_fashion_topic(topic, audience):
        topic_specific_guardrails.append(
            "Stay in fit, confidence, wardrobe, and lived style language. Do not drift into founder or systems language."
        )
    if _is_entrepreneur_topic(topic, audience):
        topic_specific_guardrails.append(
            "Stay in market, customer, product, and founder tradeoff language. Do not drift into school or family framing."
        )
    topic_specific_text = "\n".join(f"- {line}" for line in topic_specific_guardrails) or "- No extra topic-specific guardrails."
    positioning_lines = [
        str(item).strip()
        for item in strategy_contract.get("positioning_model") or []
        if str(item).strip()
    ]
    positioning_text = "\n".join(f"- {line}" for line in positioning_lines) or "- Preserve the owner's approved positioning and do not infer a career exit."
    intent_rules = {
        "value": "Teach, observe, frame, or show a useful operating lesson. Do not add a sales ask.",
        "invitation": "Deliver a useful post and make one bounded invitation for beta testing, product feedback, collaboration, an event, speaking, or a relevant conversation. Do not turn it into a consulting pitch.",
        "personal": "Use a verified personal or behind-the-scenes story and connect it to a broader meaning. Do not manufacture vulnerability or make unsupported career announcements.",
    }
    classification_text = "\n".join(
        f"- {label}: {classification.get(field) or 'unclassified'}"
        for field, label in (
            ("canonical_pillar", "Canonical pillar"),
            ("career_signal", "Career signal"),
            ("employer_proximity", "Employer proximity"),
            ("employer_safety", "Employer safety"),
            ("proof_posture", "Proof posture"),
            ("treatment", "Measurement treatment"),
            ("publish_posture", "Publish posture"),
            ("audience", "Audience segment"),
            ("audience_consequence", "Audience consequence"),
            ("distinct_thesis", "Distinct thesis"),
            ("why_now", "Why now"),
            ("development_status", "Development status"),
            ("classification_state", "Classification state"),
        )
    )
    source_freshness = classification.get("source_freshness")
    if not isinstance(source_freshness, dict):
        source_freshness = {}
    source_freshness_text = "\n".join(
        f"- {label}: {source_freshness.get(field) if source_freshness.get(field) is not None else 'unknown'}"
        for field, label in (
            ("temporality", "Source temporality"),
            ("state", "Computed freshness"),
            ("dated_at", "Source date"),
            ("age_days", "Source age in days"),
            ("current_claim_allowed", "May call this current/trending"),
        )
    )
    disallowed_text = "\n".join(
        f"- {str(item).strip()}"
        for item in (disallowed_moves or [])
        if str(item).strip()
    ) or "- Do not invent facts, proof, private details, employer endorsement, or career-exit language."
    option_count = len(briefs)
    option_scope = "both" if option_count == 2 else "all"
    normalized_brief_claims = {
        " ".join((brief.primary_claim or "").lower().split()).strip()
        for brief in briefs
        if " ".join((brief.primary_claim or "").split()).strip()
    }
    principle_only_shared_claim_separation = ""
    if (
        " ".join((grounding_mode or "").lower().split()).strip() == "principle_only"
        and len(briefs) == 2
        and len(normalized_brief_claims) == 1
    ):
        principle_only_shared_claim_separation = """
PRINCIPLE-ONLY SHARED-CLAIM SEPARATION:
- No approved proof is available. Do not invent an example, pseudo-proof, metric, project, or story to create variety.
- Option 1 owns the causal diagnosis. Explain only why the default reading fails and end with a declarative, non-prescriptive belief filter that helps the reader recognize the cause. Do not phrase it as advice, prescribe a solution, recommend a workflow, list solution components, describe a target architecture, or direct any audience action.
- Option 2 owns the rule-first application. Start with one concrete operating rule or check, move to its audience consequence, and end on the resulting consequence or tradeoff. Do not re-explain why the claim is true, replay Option 1's causal chain, repeat the opening rule at the close, or summarize its diagnosis.
- The two bodies may share the approved claim, but they must not follow the same ordered argument or recommendation sequence. If they can be summarized with the same sequence, rewrite one before returning it.
""".strip()
    return f"""Write exactly {option_count} LinkedIn post option{'s' if option_count != 1 else ''} for the topic below.

Topic: {topic}
Context: {context or "General"}
Audience: {audience_label}

OWNER-APPROVED FEEZIE STRATEGY:
- Contract: {strategy_contract.get('schema_version') or 'feezie_strategy_contract/v1'}
- Contract hash: {strategy_contract.get('contract_hash') or 'unavailable'}
- Public posture: show technology ambition through shipped proof while preserving education, current-role, community, and trust credibility.
- Do not announce a pivot out of education, a next chapter, or a public job search unless the owner explicitly requested it.
{positioning_text}

POST INTENT:
- Intent: {intent}
- {intent_rules[intent]}
- The 9 value / 1 invitation / 1 personal mix is a rolling portfolio target; it never justifies a weak or ungrounded post.

CANDIDATE CLASSIFICATION:
{classification_text}
- `blocked` employer safety means stop rather than draft. `owner_review_required`, `owner_confirmation_required`, `missing`, or `unclassified` must remain visibly provisional and cannot be presented as verified proof.

SOURCE FRESHNESS RECEIPT:
{source_freshness_text}
- Plan-generation time is not evidence that a source is current. If `May call this current/trending` is false, do not describe the source or topic as new, current, recent, hot, trending, or happening now. You may use it only as a dated example or an evergreen pattern that the available proof supports.

GROUNDING MODE:
- `{grounding_mode}`
- {grounding_reason}

TOPIC ANCHORS:
{topic_anchor_text}

PROOF ANCHORS:
{proof_anchor_text}

OPTIONAL STORY ANCHOR:
{story_anchor_text}

VOICE RULES:
{voice_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

DISALLOWED MOVES:
{disallowed_text}

TOPIC-SPECIFIC GUARDRAILS:
{topic_specific_text}

OPTION PLAN:
{briefs_text}

{principle_only_shared_claim_separation}

PUBLIC POST RULES:
- Write public post copy, not internal build notes.
- Never write about the author in third person. Do not open with `the owner is...`, `the owner treats...`, or `the owner is building...`.
- Translate internal mechanics into public language. Do not use phrases like `shared workspace state`, `shared state`, `typed retrieval`, `proof-aware prompts`, `daily briefs`, or `routed workspace snapshot`.
- Keep each option on its assigned lane and strategic claim.
- Keep each option faithful to the stated post intent and candidate classification.
- Use proof to support the claim, not replace it.
- Keep 2 to 4 short paragraphs per option.
- Use at most two concrete proof details in one option.
- No generic opener formulas. No filler fragments. No meta directives like `Read that again` or `Write that down`.
- Do not echo internal audience slugs like `tech_ai` or `education_admissions`.
- Do not use house scaffold lines like `That is the operating model.`, `That is where it breaks.`, or `Otherwise it's just another tab.`.
- Do not invent names, employers, projects, stories, or metrics.
- The first line is the hook. Make {option_scope} hooks materially different in mechanism and language; do not rewrite the same opening.
- Each complete draft must use a different thesis treatment, proof progression, and payoff. A new hook on substantially the same body is not a different option.
- Follow the assigned Thesis treatment, Proof progression, and Payoff in each option plan. These are hard structural jobs, not suggestions and not text to copy into the post.
- If both options use the same bounded claim or proof, option 1 must diagnose the mechanism in claim-to-proof-to-explanation order while option 2 must lead with a rule or check, move to the audience consequence, and place any proof last as validation. Do not repeat the same diagnosis, evidence order, or conclusion.
- Make the closing paragraph fulfill the assigned payoff with a specific filter, rule, check, boundary, or consequence. Do not merely restate the hook.
- Write for the intended audience consequence, not for generic virality.

OUTPUT RULES:
- Write exactly {option_count} complete option{'s' if option_count != 1 else ''} in order.
- Each option must be distinct in thesis treatment, hook, proof progression, and payoff, even when the approved claim and proof are shared.
- Keep the writing spoken, direct, and publishable.
"""


def write_planned_options(
    *,
    client: Any,
    topic: str,
    context: str,
    audience: str,
    grounding_mode: str,
    grounding_reason: str,
    topic_anchor_chunks: List[Dict[str, Any]],
    proof_anchor_chunks: List[Dict[str, Any]],
    story_anchor_chunks: List[Dict[str, Any]],
    briefs: List[ContentOptionBrief],
    good_examples: List[str],
    voice_directives: List[str],
    approved_references: List[str],
    disallowed_moves: List[str],
) -> List[str]:
    if not briefs:
        return []
    response = client.chat.completions.create(
        model=CONTENT_FAST_MODEL_ALIAS,
        messages=[
            {
                "role": "system",
                "content": "You are a ghostwriter. Follow the planned briefs exactly and keep the writing human, sharp, and grounded.",
            },
            {
                "role": "user",
                "content": build_planned_writer_prompt(
                    topic=topic,
                    context=context,
                    audience=audience,
                    grounding_mode=grounding_mode,
                    grounding_reason=grounding_reason,
                    topic_anchor_chunks=topic_anchor_chunks,
                    proof_anchor_chunks=proof_anchor_chunks,
                    story_anchor_chunks=story_anchor_chunks,
                    briefs=briefs,
                    good_examples=good_examples,
                    voice_directives=voice_directives,
                    approved_references=approved_references,
                    disallowed_moves=disallowed_moves,
                ),
            },
        ],
        temperature=_writer_temperature(audience),
        max_tokens=1800,
    )
    parsed = parse_content_options(response.choices[0].message.content or "")
    return parsed[: len(briefs)] if len(parsed) >= len(briefs) else parsed


def build_planned_critic_prompt(
    *,
    topic: str,
    audience: str,
    grounding_mode: str,
    briefs: List[ContentOptionBrief],
    rough_options: List[str],
    avoid_examples: List[str],
    voice_directives: List[str],
    approved_references: List[str],
) -> str:
    option_count = max(len(rough_options), 1)
    option_suffix = "" if option_count == 1 else "s"
    separator_instruction = (
        "Output only the rewritten canonical option; do not add an option heading or hidden alternative."
        if option_count == 1
        else "Output only the rewritten options, separated by ---OPTION---."
    )
    audience_label = _audience_prompt_label(audience)
    options_text = "\n---OPTION---\n".join(rough_options)
    avoid_text = "\n".join(f"- {example}" for example in avoid_examples[:3]) or "- No extra avoid-pattern examples."
    voice_text = "\n".join(f"- {directive}" for directive in voice_directives[:8]) or "\n".join(
        f"- {directive}" for directive in DEFAULT_VOICE_DIRECTIVES[:6]
    )
    approved_reference_text = "\n".join(f"- {reference}" for reference in approved_references) or "- No approved named references."
    public_post_guardrails = _render_public_post_guardrails()
    briefs_text = _render_content_option_briefs(briefs)
    topic_specific_guardrails = []
    normalized_topic = " ".join((topic or "").lower().split())
    if audience == "education_admissions" and any(term in normalized_topic for term in ("faculty", "senate", "bill", "policy")):
        topic_specific_guardrails.append(
            "Keep the policy / school / faculty signal visible. If the rewrite turns into a generic family-experience post, pull it back toward the actual policy impact."
        )
    if _is_student_support_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the student / family / support lens visible. If the rewrite drifts into generic B2B trust or legacy-tech language, pull it back toward the actual student experience."
        )
    if any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants")):
        topic_specific_guardrails.append(
            "Keep the first line on the market / competition claim. If the rewrite drifts into workflow or prompting first, pull it back unless the topic itself explicitly names workflow, prompting, or orchestration."
        )
    if _is_fashion_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the rewrite in style, fit, confidence, and lived transformation. Pull it back if it drifts into generic business language."
        )
    if _is_entrepreneur_topic(topic, audience):
        topic_specific_guardrails.append(
            "Keep the rewrite in customer, market, product, and founder tradeoffs. Pull it back if it drifts into unrelated family, school, or style framing."
        )
    topic_specific_guardrail_text = "\n".join(f"- {line}" for line in topic_specific_guardrails) or "- No extra topic-specific guardrails."
    return f"""You are the critic stage in a planner -> writer -> critic content system.

Topic: {topic}
Audience: {audience_label}
Grounding mode: {grounding_mode}

PLANNED OPTION BRIEFS:
{briefs_text}

AVOID PATTERN REFERENCES:
{avoid_text}

VOICE DIRECTIVES:
{voice_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

PUBLIC POST GUARDRAILS:
{public_post_guardrails}

TOPIC-SPECIFIC GUARDRAILS:
{topic_specific_guardrail_text}

DRAFTS TO CRITIQUE:
{options_text}

CRITIC RULES:
- Keep exactly {option_count} option{option_suffix}{' separated by ---OPTION---' if option_count > 1 else ''}.
- Preserve the approved facts, claim meaning, and proof meaning.
- Remove generic consultant phrasing.
- If an option opens with a flat generic statement, rewrite the opening around the planned strategic claim.
- If an option opens by describing the author in third person, rewrite it into first-person or direct thesis voice.
- Keep the writing casual, direct, and spoken.
- Do not add new names, metrics, or stories.
- Keep each option aligned with its planned framing mode.
- Do not imitate the AVOID PATTERN REFERENCES.
- Delete filler beats like "Why?" or short standalone restatements that repeat the opener.
- If a short punch line does not add new meaning, remove it.
- Translate internal operator phrasing into public language. Do not leave phrases like `shared workspace state`, `typed retrieval`, or `proof-aware prompts` in the final copy.

{separator_instruction}
"""


def critique_planned_options(
    *,
    client: Any,
    topic: str,
    audience: str,
    grounding_mode: str,
    briefs: List[ContentOptionBrief],
    rough_options: List[str],
    avoid_examples: List[str],
    voice_directives: List[str],
    approved_references: List[str],
) -> List[str]:
    if not rough_options:
        return rough_options
    response = client.chat.completions.create(
        model=CONTENT_FAST_MODEL_ALIAS,
        messages=[
            {
                "role": "system",
                "content": "You are a strict editorial critic. Keep the facts, but rewrite generic or weak phrasing.",
            },
            {
                "role": "user",
                "content": build_planned_critic_prompt(
                    topic=topic,
                    audience=audience,
                    grounding_mode=grounding_mode,
                    briefs=briefs,
                    rough_options=rough_options,
                    avoid_examples=avoid_examples,
                    voice_directives=voice_directives,
                    approved_references=approved_references,
                ),
            },
        ],
        temperature=_critic_temperature(),
        max_tokens=1800,
    )
    rewritten = parse_content_options(response.choices[0].message.content or "")
    return rewritten[: len(briefs)] if len(rewritten) >= len(briefs) else rough_options


def _extract_named_reference_candidates(text: str) -> set[str]:
    candidates: set[str] = set()
    cleaned = re.sub(r"[*_`#]", " ", text or "")
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        tokens = re.findall(r"[A-Za-z][A-Za-z/&+-]*", sentence)
        for index, token in enumerate(tokens):
            if not token:
                continue
            if index == 0 and token in GENERIC_SENTENCE_OPENERS:
                continue
            if token.lower() in STOPWORDS:
                continue
            if re.fullmatch(r"[A-Z]{2,}", token) or re.fullmatch(r"[A-Z][a-z]+", token):
                if len(token) >= 4 or token.isupper():
                    candidates.add(token.lower())
    return candidates


def option_uses_unapproved_reference(
    option: str,
    *,
    approved_reference_terms: List[str],
    audience: str,
) -> bool:
    approved_terms = _normalized_terms(" ".join(approved_reference_terms))
    approved_terms.update(_extract_named_reference_candidates(" ".join(approved_reference_terms)))
    if _extract_named_reference_candidates(option) - approved_terms:
        return True

    if audience == "tech_ai":
        option_text = " ".join((option or "").lower().split())
        for placeholder in UNSUPPORTED_EVIDENCE_PLACEHOLDERS:
            if placeholder in option_text and placeholder not in approved_terms:
                return True
    return False


def option_mentions_approved_proof(option: str, proof_packets: List[str]) -> bool:
    option_terms = _normalized_terms(option)
    if not option_terms or not proof_packets:
        return False
    for packet in proof_packets:
        packet_terms = _normalized_terms(_proof_packet_evidence_text(packet))
        if len(option_terms.intersection(packet_terms)) >= 2:
            return True
    return False


def _replace_flat_opening_with_claim(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    claim = _ensure_sentence(brief.primary_claim)
    if not cleaned or not claim:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return cleaned
    first_paragraph = paragraphs[0]
    opening_needs_reset = any(pattern.search(first_paragraph) for pattern in FLAT_GENERIC_PATTERNS)
    if not opening_needs_reset and not _sentence_is_signal_bearing(first_paragraph, brief):
        opening_needs_reset = any(pattern.search(first_paragraph) for pattern in TASTE_NEGATIVE_PATTERNS)
    if not opening_needs_reset:
        return cleaned
    first_sentences = _split_sentences(first_paragraph)
    if len(first_sentences) > 1:
        replacement = " ".join(first_sentences[1:]).strip()
        paragraphs[0] = replacement if replacement else claim
    else:
        paragraphs[0] = claim
    if claim.lower() not in " ".join(paragraphs).lower():
        paragraphs.insert(0, claim)
    return "\n\n".join(segment for segment in paragraphs if segment)


def _claim_near_opening(option: str, claim: str) -> bool:
    opening = " ".join((option or "").split())[:220].lower()
    normalized_claim = " ".join((claim or "").split()).lower()
    if not opening or not normalized_claim:
        return False
    if re.search(r"\bprompting alone\b", normalized_claim, flags=re.IGNORECASE) and re.search(
        r"\bprompting alone\b",
        opening,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(r"\bagent orchestration\b", normalized_claim, flags=re.IGNORECASE) and re.search(
        r"\bagent orchestration\b|\boperating pattern\b|\boperating model\b",
        opening,
        flags=re.IGNORECASE,
    ):
        return True
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


def _assigned_application_rule_near_opening(option: str, brief: ContentOptionBrief) -> bool:
    treatment = " ".join(str(brief.thesis_treatment or "").lower().split())
    decision_basis = " ".join(str(brief.decision_rule_basis or "").split()).strip()
    if "application" not in treatment or not decision_basis:
        return False
    opening = " ".join((option or "").split())[:220].lower()
    basis_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", decision_basis.lower())
        if len(token) > 3 and token not in STOPWORDS
    }
    opening_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", opening)
        if len(token) > 3 and token not in STOPWORDS
    }
    required = min(2, len(basis_terms))
    return bool(required and len(basis_terms.intersection(opening_terms)) >= required)


def _feezie_role_term_variants(term: str) -> set[str]:
    """Return conservative grammatical variants for a source-bound role term."""

    normalized = "".join(re.findall(r"[a-z0-9]+", str(term or "").lower()))
    if not normalized:
        return set()
    variants = {normalized}
    if len(normalized) > 6 and normalized.endswith("ty"):
        variants.add(normalized[:-2])
    if len(normalized) > 5 and normalized.endswith("ies"):
        variants.add(normalized[:-3] + "y")
    if len(normalized) > 5 and normalized.endswith("ing"):
        variants.add(normalized[:-3])
        variants.add(normalized[:-3] + "e")
    if len(normalized) > 5 and normalized.endswith("ed"):
        variants.add(normalized[:-2])
        variants.add(normalized[:-1])
    if len(normalized) > 4 and normalized.endswith("s") and not normalized.endswith("ss"):
        variants.add(normalized[:-1])
    return {value for value in variants if len(value) >= 4}


def _feezie_role_term_overlap_count(left: set[str], right: set[str]) -> int:
    """Count one-to-one exact or conservative grammatical term matches."""

    remaining = set(right)
    matches = 0
    for left_term in sorted(left):
        left_variants = _feezie_role_term_variants(left_term)
        matched = next(
            (
                right_term
                for right_term in sorted(remaining)
                if left_variants.intersection(_feezie_role_term_variants(right_term))
            ),
            None,
        )
        if matched is not None:
            matches += 1
            remaining.remove(matched)
    return matches


def _assigned_diagnosis_claim_near_opening(
    option: str,
    brief: ContentOptionBrief,
) -> bool:
    """Recognize the current topic-led diagnosis hook without spending its problem.

    V4 reserves both exact-problem anchors for paragraph two, so the older
    requirement that sentence one contain a mechanism anchor directly
    contradicted the writer and paragraph-role contracts.  Current hooks must
    instead retain at least two substantive terms from their remote-safe
    strategic topic while consuming neither reserved problem anchor.
    """

    if str(getattr(brief, "semantic_payload_version", "") or "").strip() != FEEZIE_ROLE_PAYLOAD_VERSION:
        return False
    diagnosis_fields = (
        str(getattr(brief, "mechanism_focus", "") or "").strip(),
        str(getattr(brief, "recognition_basis", "") or "").strip(),
    )
    application_fields = (
        str(getattr(brief, "decision_rule_basis", "") or "").strip(),
        str(getattr(brief, "required_context_concepts", "") or "").strip(),
        str(getattr(brief, "consequence_basis", "") or "").strip(),
    )
    if not all(diagnosis_fields) or any(application_fields):
        return False
    opening = (_first_content_line(option) or "").lower()
    opening_terms = _feezie_diagnosis_opening_terms(opening)
    claim_terms = _feezie_diagnosis_opening_terms(str(brief.primary_claim or ""))
    mechanism_anchors = [
        str(token or "").strip().lower()
        for token in (getattr(brief, "mechanism_anchor_terms", ()) or ())
        if str(token or "").strip()
    ]
    reserved_problem_anchor_present = any(
        re.search(rf"\b{re.escape(anchor)}\b", opening)
        for anchor in mechanism_anchors
    )
    opening_word_count = len(re.findall(r"[A-Za-z0-9]+", opening))
    return bool(
        not reserved_problem_anchor_present
        and 5 <= opening_word_count <= 16
        and _feezie_role_term_overlap_count(claim_terms, opening_terms) >= 2
    )


def _force_claim_lead(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    claim = _ensure_sentence(brief.primary_claim)
    if not cleaned or not claim:
        return cleaned
    if _claim_near_opening(cleaned, claim):
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return claim
    return "\n\n".join([claim] + paragraphs)


def _stabilize_claim_opening(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    claim = _ensure_sentence(brief.primary_claim)
    if not cleaned or not claim:
        return cleaned
    if _claim_near_opening(cleaned, claim):
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return claim
    first_paragraph = paragraphs[0]
    opening_has_blocked_taste = any(pattern.search(first_paragraph) for pattern in FLAT_GENERIC_PATTERNS)
    if not opening_has_blocked_taste and not _sentence_is_signal_bearing(first_paragraph, brief):
        opening_has_blocked_taste = any(pattern.search(first_paragraph) for pattern in TASTE_NEGATIVE_PATTERNS)
    if not opening_has_blocked_taste:
        return cleaned
    paragraphs[0] = claim
    return "\n\n".join(paragraphs)


def _opening_line_from_brief(brief: ContentOptionBrief) -> str:
    claim = brief.primary_claim or ""
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    combined = f"{claim} {evidence}".lower()
    if brief.framing_mode == "contrarian_reframe":
        if re.search(r"\bmarket\b|\bcompetition\b|\bmeaner\b|\badvantage\b|\bpressure\b|\bentrants\b", combined, flags=re.IGNORECASE):
            return _ensure_sentence(claim)
        if re.search(r"\bprompting alone\b", combined, flags=re.IGNORECASE):
            return "Prompting alone is not the strategy."
        if re.search(r"\bartifact\b", combined, flags=re.IGNORECASE):
            return "No artifact? Keep it at the level of principle."
        return "The default read is wrong."
    if brief.framing_mode == "warning":
        if re.search(r"\bexplicit handoffs\b", evidence, flags=re.IGNORECASE) and re.search(
            r"\bshared workspace state\b", evidence, flags=re.IGNORECASE
        ):
            return "Without explicit handoffs and shared state, it breaks."
        if _brief_prefers_operator_voice(brief):
            return "Without that, it breaks."
    if brief.framing_mode == "operator_lesson":
        if re.search(r"\bexplicit handoffs\b", evidence, flags=re.IGNORECASE) and re.search(
            r"\bshared workspace state\b", evidence, flags=re.IGNORECASE
        ):
            return "AI only helps when the workflow is coordinated."
    return ""


def _shape_opening_by_mode(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    opening = _opening_line_from_brief(brief)
    if not opening:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return opening
    first_paragraph = paragraphs[0]
    first_sentences = [_ensure_sentence(sentence.strip()) for sentence in _split_sentences(first_paragraph) if sentence.strip()]
    if not first_sentences:
        paragraphs[0] = opening
        return "\n\n".join(paragraphs)
    current_opening = first_sentences[0]
    if current_opening.lower() == opening.lower():
        return cleaned
    if brief.framing_mode not in {"contrarian_reframe", "warning", "operator_lesson"}:
        return cleaned
    if brief.framing_mode in {"warning", "operator_lesson"} and _claim_near_opening(cleaned, brief.primary_claim):
        return cleaned
    remainder_sentences = [
        sentence
        for sentence in first_sentences[1:]
        if not _sentence_is_opening_restatement(sentence, opening, brief)
    ]
    remainder = " ".join(remainder_sentences).strip()
    paragraphs[0] = " ".join(part for part in [opening, remainder] if part).strip()
    return "\n\n".join(paragraphs)


def _force_brief_proof_support(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned or not brief.proof_packet:
        return cleaned
    if option_mentions_approved_proof(cleaned, [brief.proof_packet]):
        return cleaned
    evidence = _ensure_public_sentence(_proof_packet_evidence_text(brief.proof_packet))
    if not evidence:
        return cleaned
    evidence = _rewrite_public_system_phrases(evidence)
    evidence = _rewrite_internal_public_jargon(evidence)
    evidence = _rewrite_soft_operator_sentences(evidence, brief)
    if _internal_public_jargon_hits(evidence):
        evidence = _operator_system_sentence_from_brief(brief) or _named_reference_sentence_from_brief(brief) or evidence
    evidence = _ensure_public_sentence(evidence)
    if not evidence:
        return cleaned
    return f"{cleaned}\n\n{evidence}".strip()


def _sentence_is_signal_bearing(sentence: str, brief: ContentOptionBrief) -> bool:
    normalized = " ".join((sentence or "").split()).strip()
    if not normalized:
        return False
    if option_mentions_approved_proof(normalized, [brief.proof_packet]):
        return True
    if re.search(r"\b\d[\d.,x%$m]*\b", normalized):
        return True
    anchor_terms = _significant_terms(
        f"{brief.primary_claim} {_proof_packet_evidence_text(brief.proof_packet)} {brief.story_beat}"
    )
    if not anchor_terms:
        return False
    sentence_terms = _significant_terms(normalized)
    return len(anchor_terms.intersection(sentence_terms)) >= 3


def _contrast_line_from_brief(brief: ContentOptionBrief) -> str:
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    combined = f"{brief.primary_claim} {evidence}"
    if _brief_is_market_competition_lane(brief):
        return ""
    if not evidence:
        return ""
    instead_match = re.search(r"\binstead of ([^.]+)", evidence, flags=re.IGNORECASE)
    if instead_match:
        phrase = re.sub(r"^(?:the|a|an)\s+", "", instead_match.group(1).strip(" ."), flags=re.IGNORECASE)
        if phrase:
            if re.search(r"\bisolated prompting\b", phrase, flags=re.IGNORECASE):
                return "Not prompting in isolation."
            if re.search(r"\bliving in isolated tools\b|\bisolated tools\b", phrase, flags=re.IGNORECASE):
                return "Not fragmented tools."
            return _ensure_sentence(f"Not {phrase}")
    if re.search(r"\bshared workspace state\b", evidence, flags=re.IGNORECASE):
        return "Shared state."
    if re.search(r"\bexplicit handoffs\b", evidence, flags=re.IGNORECASE):
        return "Explicit handoffs."
    if re.search(r"\bdashboard\b|\breporting\b|\bvisibility\b", combined, flags=re.IGNORECASE) and re.search(
        r"\bexecution\b|\boutreach\b|\bpriority\b|\bpriorities\b|\bpipeline\b",
        combined,
        flags=re.IGNORECASE,
    ):
        return "Visibility should change the next move."
    if re.search(r"\baccess\b", combined, flags=re.IGNORECASE) and re.search(r"\badoption\b", combined, flags=re.IGNORECASE):
        return "Not access on paper. Adoption in practice."
    if re.search(r"\bfamily trust\b|\btrust-building\b|\breferral\b|\benrollment\b", combined, flags=re.IGNORECASE):
        return "Not a brochure problem. A trust problem."
    return ""


def _option_mentions_specific_contrast(option: str, brief: ContentOptionBrief) -> bool:
    cleaned = (option or "").strip()
    if not cleaned:
        return False
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    if not evidence:
        return any(pattern.search(cleaned) for pattern in TASTE_CONTRAST_PATTERNS)
    instead_match = re.search(r"\binstead of ([^.]+)", evidence, flags=re.IGNORECASE)
    if instead_match:
        phrase = re.sub(r"^(?:the|a|an)\s+", "", instead_match.group(1).strip(" ."), flags=re.IGNORECASE)
        if phrase:
            phrase_terms = _significant_terms(phrase)
            option_terms = _significant_terms(cleaned)
            if phrase_terms and (
                phrase_terms.issubset(option_terms)
                or len(phrase_terms.intersection(option_terms)) >= max(1, len(phrase_terms) - 1)
            ):
                return True
            if re.search(r"\bisolated prompting\b", phrase, flags=re.IGNORECASE) and re.search(
                r"\bprompting in isolation\b|\bisolated prompting\b|\bprompting alone\b",
                cleaned,
                flags=re.IGNORECASE,
            ):
                return True
        return False
    return any(pattern.search(cleaned) for pattern in TASTE_CONTRAST_PATTERNS)


def _punch_line_from_brief(brief: ContentOptionBrief) -> str:
    phrases = _collect_curated_reference_phrases(
        f"{brief.primary_claim} {_proof_packet_evidence_text(brief.proof_packet)} {brief.story_beat}"
    )
    for phrase in phrases:
        normalized = " ".join((phrase or "").split()).strip(" .")
        if _phrase_is_flat_label(normalized):
            continue
        if any(ch.isdigit() for ch in normalized):
            continue
        words = normalized.split()
        if 1 < len(words) <= 4:
            return _ensure_sentence(normalized.capitalize())
    if re.search(r"\boperating pattern\b", brief.primary_claim, flags=re.IGNORECASE):
        return "The workflow has to hold."
    if re.search(r"\bartifact\b", brief.primary_claim, flags=re.IGNORECASE):
        return "The proof has to hold."
    return ""


def _mid_punch_line_from_brief(brief: ContentOptionBrief, option: str) -> str:
    if _brief_is_market_competition_lane(brief):
        return ""
    existing = " ".join((option or "").lower().split())
    if brief.framing_mode == "contrarian_reframe" and re.search(
        r"\bprompting alone\b", brief.primary_claim, flags=re.IGNORECASE
    ):
        for candidate in ("That will not work.", "That dog will not hunt."):
            if candidate.lower() not in existing:
                return candidate
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    for candidate, pattern in (
        ("Explicit handoffs.", r"\bexplicit handoffs\b"),
        ("Shared state.", r"\bshared workspace state\b"),
        ("Proof-aware prompts.", r"\bproof-aware prompts\b"),
    ):
        if re.search(pattern, evidence, flags=re.IGNORECASE) and candidate.lower() not in existing:
            return candidate
    fallback = _punch_line_from_brief(brief)
    if fallback and fallback.lower() not in existing:
        return fallback
    if brief.framing_mode == "warning" and "that is when the work slips." not in existing:
        return "That is when the work slips."
    return ""


def _brief_prefers_operator_voice(brief: ContentOptionBrief) -> bool:
    text = f"{brief.primary_claim} {_proof_packet_evidence_text(brief.proof_packet)} {brief.story_beat}"
    return bool(_significant_terms(text).intersection(STRICT_AUDIENCE_ANCHOR_TERMS.get("tech_ai", set())))


def _brief_is_market_competition_lane(brief: ContentOptionBrief) -> bool:
    claim_text = f"{brief.primary_claim} {brief.story_beat}"
    return bool(
        re.search(
            r"\bmarket\b|\bcompetition\b|\bcompetitive\b|\bmeaner\b|\badvantage\b|\bpressure\b|\bentrants\b|\bcategory\b",
            claim_text,
            flags=re.IGNORECASE,
        )
    )


def _operator_system_sentence_from_brief(brief: ContentOptionBrief) -> str:
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    if re.search(r"\brouted workspace snapshot\b", evidence, flags=re.IGNORECASE):
        return "Context survives the handoff."
    if re.search(r"\bshared workspace state\b", evidence, flags=re.IGNORECASE) and re.search(
        r"\bexplicit handoffs\b", evidence, flags=re.IGNORECASE
    ):
        return "Shared state keeps context alive across the handoff."
    if re.search(r"\bproof-aware prompts\b", evidence, flags=re.IGNORECASE) and re.search(
        r"\bexplicit handoffs\b", evidence, flags=re.IGNORECASE
    ):
        return "Prompts only help when the handoff stays explicit."
    if re.search(r"\bshared workspace state\b", evidence, flags=re.IGNORECASE):
        return "Shared state keeps context alive."
    if re.search(r"\bexplicit handoffs\b", evidence, flags=re.IGNORECASE):
        return "Explicit handoffs keep context alive."
    if re.search(r"\bproof-aware prompts\b", evidence, flags=re.IGNORECASE):
        return "Proof-aware prompts only work when context survives."
    return ""


def _looks_like_operator_catalog_sentence(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    marker_count = sum(1 for marker in OPERATOR_CATALOG_MARKERS if marker in normalized)
    if marker_count < 3:
        return False
    if "," in normalized or re.search(r"\b(?:and|around|across|same|shared|run|runs|running|unified|essential|critical|important)\b", normalized):
        return True
    return False


def _named_reference_sentence_from_brief(brief: ContentOptionBrief) -> str:
    label = " ".join((_proof_packet_label(brief.proof_packet) or "").split()).strip()
    if not _reference_is_publicly_nameable(label):
        return ""
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    if re.search(r"\brouted workspace snapshot\b", evidence, flags=re.IGNORECASE):
        return _ensure_sentence(f"{label} made the handoff visible")
    if re.search(r"\bshared workspace state\b|\bexplicit handoffs\b", evidence, flags=re.IGNORECASE):
        return _ensure_sentence(f"{label} made the handoff explicit")
    return _ensure_sentence(f"{label} makes this concrete")


def _ensure_named_reference_specificity(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned or not _brief_prefers_operator_voice(brief):
        return cleaned
    if _option_has_named_reference_specificity(cleaned, brief):
        return cleaned
    reference_sentence = _named_reference_sentence_from_brief(brief)
    if not reference_sentence:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return reference_sentence
    insert_at = 1 if len(paragraphs) > 1 else len(paragraphs)
    paragraphs.insert(insert_at, reference_sentence)
    return "\n\n".join(paragraphs)


def _strong_closer_from_brief(brief: ContentOptionBrief) -> str:
    claim = brief.primary_claim or ""
    evidence = _proof_packet_evidence_text(brief.proof_packet)
    combined = f"{claim} {evidence}".lower()
    if _brief_is_market_competition_lane(brief):
        return ""
    if any(
        term in combined
        for term in (
            "student",
            "students",
            "family",
            "families",
            "parent",
            "parents",
            "admissions",
            "enrollment",
            "support",
            "neurodivergent",
            "twice-exceptional",
            "twice exceptional",
        )
    ):
        if brief.framing_mode == "warning":
            return "The student still has to stay visible."
        if brief.framing_mode == "agree_and_extend":
            return "That is what families actually feel."
        return "The student has to stay visible."
    if re.search(r"\bworkflow clarity\b|\badoption\b|\buseful\b", combined, flags=re.IGNORECASE):
        return "The workflow still has to hold."
    if re.search(r"\bprompting alone\b", combined, flags=re.IGNORECASE):
        if brief.framing_mode == "warning":
            return "The workflow has to carry the load."
        if brief.framing_mode == "contrarian_reframe":
            return "Prompting alone is not enough."
        return "The workflow has to carry the load."
    if _brief_prefers_operator_voice(brief):
        if brief.framing_mode == "warning":
            return "That is when the work starts slipping."
        if brief.framing_mode == "agree_and_extend":
            return "Clarity is the part that scales."
        return "Clarity has to come first."
    if re.search(r"\bartifact\b", combined, flags=re.IGNORECASE):
        return "The proof has to hold."
    if brief.framing_mode == "warning":
        return "That is when the work starts slipping."
    if brief.framing_mode == "recognition":
        return "That kind of work deserves to be named."
    return _punch_line_from_brief(brief)


def _closer_needs_sharpening(sentence: str, brief: ContentOptionBrief) -> bool:
    normalized = " ".join((sentence or "").split()).strip()
    if not normalized:
        return True
    if any(pattern.search(normalized) for pattern in WEAK_ENDING_PATTERNS):
        return True
    if any(pattern.search(normalized) for pattern in GENERIC_CLOSER_PATTERNS):
        return True
    if _brief_prefers_operator_voice(brief) and re.match(r"^(?:now,\s*)?we\b", normalized, flags=re.IGNORECASE):
        return True
    lowered = normalized.lower()
    if lowered in {
        "that is the operating model.",
        "show me the artifact.",
        "prompting alone is not the strategy.",
        "prompting alone will not hold.",
        "without that, the system breaks.",
        "otherwise it's just another tab.",
        "agreement is easy. operating it is harder.",
        "that kind of work matters.",
    }:
        return False
    if len(normalized.split()) > 11 and not any(pattern.search(normalized) for pattern in TASTE_CONTRAST_PATTERNS):
        return True
    return False


def _ensure_contrast_shape(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    contrast_line = _contrast_line_from_brief(brief)
    contrast_terms = _significant_terms(contrast_line)
    option_terms = _significant_terms(cleaned)
    already_has_target_contrast = bool(
        contrast_terms
        and (
            contrast_terms.issubset(option_terms)
            or len(contrast_terms.intersection(option_terms)) >= max(2, len(contrast_terms) - 1)
        )
    )
    if _option_mentions_specific_contrast(cleaned, brief) and (already_has_target_contrast or not contrast_line):
        return cleaned
    if not contrast_line:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return contrast_line
    if len(paragraphs) == 1:
        return "\n\n".join([paragraphs[0], contrast_line])
    return "\n\n".join([paragraphs[0], contrast_line] + paragraphs[1:])


def _ensure_paragraph_cadence(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    revised: List[str] = []
    for paragraph in paragraphs:
        sentences = [_ensure_sentence(sentence.strip()) for sentence in _split_sentences(paragraph) if sentence.strip()]
        if not sentences:
            continue
        deduped_sentences: List[str] = []
        for sentence in sentences:
            normalized_sentence = " ".join(sentence.lower().split())
            if deduped_sentences and normalized_sentence == " ".join(deduped_sentences[-1].lower().split()):
                continue
            deduped_sentences.append(sentence)
        sentences = deduped_sentences or sentences
        if _content_generation_stability_mode() == "benchmark" and len(sentences) >= 2:
            revised.append(sentences[0])
            remainder = " ".join(sentences[1:]).strip()
            if remainder:
                revised.append(remainder)
        elif len(paragraph.split()) > 28 and len(sentences) >= 2:
            revised.append(sentences[0])
            remainder = " ".join(sentences[1:]).strip()
            if remainder:
                revised.append(remainder)
        else:
            revised.append(" ".join(sentences).strip())
    if not any(len(sentence.split()) <= 6 for paragraph in revised for sentence in _split_sentences(paragraph)):
        punch_line = _mid_punch_line_from_brief(brief, "\n\n".join(revised))
        if punch_line and all(punch_line.lower() not in paragraph.lower() for paragraph in revised):
            insert_at = len(revised)
            if len(revised) >= 3:
                insert_at = len(revised) - 1
            revised.insert(insert_at, punch_line)
    return "\n\n".join(paragraph for paragraph in revised if paragraph)


def _ensure_short_sentence_presence(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    if any(len(sentence.split()) <= 6 for sentence in _split_sentences(cleaned)):
        return cleaned
    punch_line = _mid_punch_line_from_brief(brief, cleaned) or _strong_closer_from_brief(brief)
    if not punch_line:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if any(punch_line.lower() in paragraph.lower() for paragraph in paragraphs):
        return cleaned
    insert_at = len(paragraphs)
    if len(paragraphs) >= 2:
        insert_at = len(paragraphs) - 1
    paragraphs.insert(insert_at, punch_line)
    return "\n\n".join(paragraphs)


def _clean_generic_sentences(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    revised_paragraphs: List[str] = []
    for paragraph in paragraphs:
        sentences = _split_sentences(paragraph)
        if not sentences:
            continue
        kept: List[str] = []
        for index, sentence in enumerate(sentences):
            is_last_sentence = index == len(sentences) - 1
            normalized_sentence = _rewrite_audience_slug_public_copy(sentence.strip())
            if not normalized_sentence:
                continue
            if " ".join(normalized_sentence.lower().split()) in HOUSE_SCAFFOLD_SENTENCES:
                continue
            if _brief_is_market_competition_lane(brief) and normalized_sentence.lower() in {
                "not more reporting.",
                "clearer action.",
                "that is the operating model.",
                "otherwise it's just another tab.",
                "without that, the system breaks.",
                "agreement is easy.",
                "operating it is harder.",
            }:
                continue
            if re.fullmatch(r"(?:this|that|it)\.?", normalized_sentence, flags=re.IGNORECASE):
                continue
            if _looks_like_malformed_reference_bridge(normalized_sentence):
                continue
            if any(pattern.search(normalized_sentence) for pattern in GENERIC_CLOSER_PATTERNS) and not _sentence_is_signal_bearing(normalized_sentence, brief):
                continue
            if any(pattern.search(normalized_sentence) for pattern in SOFT_GENERIC_PATTERNS) and not _sentence_is_signal_bearing(normalized_sentence, brief):
                continue
            if _internal_public_jargon_hits(normalized_sentence) and len(normalized_sentence.split()) <= 6:
                continue
            if any(pattern.search(normalized_sentence) for pattern in INTERNAL_PUBLIC_JARGON_PATTERNS) and not option_mentions_approved_proof(normalized_sentence, [brief.proof_packet]):
                continue
            if _looks_like_identity_scaffold(normalized_sentence) and not _sentence_is_signal_bearing(normalized_sentence, brief):
                continue
            if any(pattern.search(normalized_sentence) for pattern in TASTE_NEGATIVE_PATTERNS) and not _sentence_is_signal_bearing(normalized_sentence, brief):
                continue
            if is_last_sentence and len(sentences) > 1 and _genericity_score(normalized_sentence) > 0 and not _sentence_is_signal_bearing(normalized_sentence, brief):
                continue
            kept.append(_ensure_sentence(normalized_sentence))
        if kept:
            revised_paragraphs.append(" ".join(kept).strip())
    return "\n\n".join(revised_paragraphs) if revised_paragraphs else cleaned


def _sentence_is_opening_restatement(sentence: str, opening: str, brief: ContentOptionBrief) -> bool:
    normalized_sentence = " ".join((sentence or "").split()).strip()
    normalized_opening = " ".join((opening or "").split()).strip()
    if not normalized_sentence or not normalized_opening:
        return False
    if _sentence_is_signal_bearing(normalized_sentence, brief):
        return False
    if normalized_sentence.lower() == normalized_opening.lower():
        return True
    if re.match(
        r"^(?:that|this|it)(?:['’]s| is) not (?:a |an )?(?:viable |real )?(?:ai )?(?:strategy|plan|approach)\.?$",
        normalized_sentence,
        flags=re.IGNORECASE,
    ):
        return bool(re.search(r"\bnot\b.*\b(?:strategy|plan|approach)\b", normalized_opening, flags=re.IGNORECASE))
    if re.match(r"^(?:that|this|it)(?: just)? (?:isn't|is not)\.?$", normalized_sentence, flags=re.IGNORECASE):
        return bool(re.search(r"\bnot\b.*\b(?:strategy|plan|approach)\b", normalized_opening, flags=re.IGNORECASE))
    opening_terms = _significant_terms(normalized_opening)
    sentence_terms = _significant_terms(normalized_sentence)
    if not opening_terms or not sentence_terms:
        return False
    overlap = opening_terms.intersection(sentence_terms)
    if len(overlap) >= min(3, len(sentence_terms)):
        return True
    return False


def _drop_opening_restatement(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if len(paragraphs) < 2:
        return cleaned
    opening = paragraphs[0]
    for index in range(1, len(paragraphs)):
        follow_up_sentences = [_ensure_sentence(sentence.strip()) for sentence in _split_sentences(paragraphs[index]) if sentence.strip()]
        if not follow_up_sentences:
            continue
        if _sentence_is_opening_restatement(follow_up_sentences[0], opening, brief):
            remaining = follow_up_sentences[1:]
            if remaining:
                paragraphs[index] = " ".join(remaining).strip()
            else:
                paragraphs.pop(index)
            break
    return "\n\n".join(paragraphs)


def _paragraph_is_filler_fragment(paragraph: str, opening: str, brief: ContentOptionBrief) -> bool:
    normalized = " ".join((paragraph or "").split()).strip()
    if not normalized:
        return True
    if re.fullmatch(r"(?:and\s+)?why\??", normalized, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"(?:this|that|it)\.?", normalized, flags=re.IGNORECASE):
        return True
    if _sentence_is_signal_bearing(normalized, brief):
        return False
    if _sentence_is_opening_restatement(normalized, opening, brief):
        return True
    if len(normalized.split()) <= 5 and not re.search(
        r"\b(?:is|are|was|were|means|matters|keeps|holds|helps|deserve|deserves|need|needs|trust|fit|support|see|sees|work|works)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if len(normalized.split()) <= 5:
        opening_terms = _significant_terms(opening)
        fragment_terms = _significant_terms(normalized)
        if fragment_terms and fragment_terms.issubset(opening_terms):
            return True
        if re.search(r"\b(?:isolated|isolation|alone)\b", normalized, flags=re.IGNORECASE) and re.search(
            r"\bprompt", normalized, flags=re.IGNORECASE
        ):
            if re.search(r"\bprompting alone\b|\bnot\b.+\bstrategy\b", opening, flags=re.IGNORECASE):
                return True
    return False


def _drop_filler_fragment_paragraphs(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if len(paragraphs) < 2:
        return cleaned
    opening = paragraphs[0]
    revised: List[str] = [opening]
    for paragraph in paragraphs[1:]:
        if _paragraph_is_filler_fragment(paragraph, opening, brief):
            continue
        revised.append(paragraph)
    return "\n\n".join(revised)


def _synthesize_planned_option(brief: ContentOptionBrief) -> str:
    opening = _opening_line_from_brief(brief) or _ensure_sentence(brief.primary_claim)
    if brief.framing_mode == "contrarian_reframe" and brief.primary_claim:
        opening = _ensure_sentence(brief.primary_claim)
    evidence = _ensure_sentence(_proof_packet_evidence_text(brief.proof_packet))
    story = _ensure_sentence(brief.story_beat)
    closer = _strong_closer_from_brief(brief)

    paragraphs: List[str] = []
    if opening:
        paragraphs.append(opening)
    if evidence and not _sentence_is_opening_restatement(evidence, opening, brief):
        paragraphs.append(evidence)
    elif story and not _sentence_is_opening_restatement(story, opening, brief):
        paragraphs.append(story)
    if closer and closer.lower() not in " ".join(paragraphs).lower():
        paragraphs.append(closer)
    synthesized = "\n\n".join(paragraph for paragraph in paragraphs if paragraph).strip()
    return synthesized or _ensure_sentence(brief.primary_claim)


def _recover_missing_planned_options(options: List[str], briefs: List[ContentOptionBrief]) -> List[str]:
    if not briefs:
        return []
    recovered: List[str] = []
    for index, brief in enumerate(briefs):
        existing = options[index].strip() if index < len(options) and options[index] else ""
        recovered.append(existing or _synthesize_planned_option(brief))
    return recovered


def _compress_operator_fragment(text: str) -> str:
    fragment = " ".join((text or "").split()).strip(" .")
    if not fragment:
        return ""
    replacements = (
        (r"^context travels across the system\b", "Context travels."),
        (r"^context travels\b", "Context travels."),
        (r"^explicit handoffs\b", "Explicit handoffs."),
        (r"^shared workspace state\b", "Shared state."),
        (r"^proof-aware prompts\b", "Proof-aware prompts."),
    )
    for pattern, replacement in replacements:
        if re.search(pattern, fragment, flags=re.IGNORECASE):
            return replacement
    return _ensure_sentence(fragment[:1].upper() + fragment[1:])


def _rewrite_internal_public_jargon(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    sentence_level_rewrites = (
        (r"\bshared (?:workspace )?state keeps context alive across the handoff\b", "Context survives the handoff"),
        (r"\bcontext continuity keeps context alive across the handoff\b", "Context survives the handoff"),
        (r"\bone (?:routed workspace snapshot|shared context|context survives the handoff) now keeps context alive(?: across the handoff)?\b", "Context survives the handoff"),
        (r"\bshared workspace state carries that intent\b", "Context has to survive the handoff"),
        (r"\bproof-aware prompts?\b", "prompts tied to proof"),
    )
    rewritten = cleaned
    for pattern, replacement in sentence_level_rewrites:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    replacements = (
        (r"\bai clone\s*/\s*brain system\b", "the system"),
        (r"\bpersona soup\b", "raw context"),
        (r"\bproof packets?\b", "proof"),
        (r"\btyped core, proof, story, and example lanes\b", "clear context lanes"),
        (r"\btyped (?:core|proof|story|example|context|support) lanes?\b", "clear context lanes"),
        (r"\btyped lanes?\b", "clear lanes"),
        (r"\btyped retrieval\b", "retrieval with clear context"),
        (r"\bdomain gates?\b", "topic guardrails"),
        (r"\bgreen[- ]or[- ]red board\b", "clear go/no-go check"),
        (r"\bproof lanes?\b", "evidence lanes"),
        (r"\bcanon through typed lanes\b", "clear context lanes"),
        (r"\brouted workspace snapshot\b", "context survives the handoff"),
        (r"\bdaily briefs\b", "operating rhythm"),
        (r"\bpersona review\b", "editorial review"),
        (r"\blong-form routing\b", "content routing"),
        (r"\bshared workspace state\b", "context survives the handoff"),
        (r"\bexplicit handoffs\b", "clear handoffs"),
    )
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    return rewritten


def _compress_operator_contrast_fragment(text: str) -> str:
    fragment = " ".join((text or "").split()).strip(" .")
    if not fragment:
        return ""
    fragment = re.sub(r"^getting lost in\s+", "", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"^(?:the|a|an)\s+", "", fragment, flags=re.IGNORECASE)
    if re.search(r"\bisolated prompt", fragment, flags=re.IGNORECASE):
        return "Not isolated prompts."
    if len(fragment.split()) <= 4:
        return _ensure_sentence(f"Not {fragment}")
    return ""


def _rewrite_soft_operator_sentences(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned or not _brief_prefers_operator_voice(brief):
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    revised_paragraphs: List[str] = []
    for paragraph in paragraphs:
        sentences = _split_sentences(paragraph)
        if not sentences:
            continue
        rewritten: List[str] = []
        for sentence in sentences:
            normalized = " ".join(sentence.split()).strip()
            if not normalized:
                continue
            normalized = re.sub(r"^(?:wins?|initiative|proof|story|example):\s*", "", normalized, flags=re.IGNORECASE)
            base_sentence = normalized.rstrip(".!?")
            if _phrase_is_flat_label(base_sentence):
                continue
            integrate_match = re.match(
                r"^(?:our|the) system now integrates (.+?) into (?:a )?unified approach$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if integrate_match:
                payload = integrate_match.group(1).rstrip(".")
                rewritten.append(_ensure_sentence(f"Now {payload} run on the same system"))
                continue
            rely_match = re.match(r"^(?:now,\s*)?we rely on (.+)$", base_sentence, flags=re.IGNORECASE)
            if rely_match:
                payload = rely_match.group(1).rstrip(".")
                rewritten.append(_ensure_sentence(f"Now it runs on {payload}"))
                continue
            means_rely_match = re.match(r"^(?:this means )?we rely on (.+?) instead of (.+)$", base_sentence, flags=re.IGNORECASE)
            if means_rely_match:
                payload = means_rely_match.group(1).rstrip(".")
                contrast = means_rely_match.group(2).rstrip(".")
                rewritten.append(_ensure_sentence(f"Now it runs on {payload}"))
                contrast_sentence = _compress_operator_contrast_fragment(contrast)
                if contrast_sentence:
                    rewritten.append(contrast_sentence)
                continue
            abstract_match = re.match(
                r"^(?:this|that) (?:approach|system|setup) (?:ensures|means|keeps) (.+?) instead of (.+)$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if abstract_match:
                leading = _compress_operator_fragment(abstract_match.group(1))
                contrast = _compress_operator_contrast_fragment(abstract_match.group(2))
                if leading:
                    rewritten.append(leading)
                if contrast:
                    rewritten.append(contrast)
                continue
            if re.match(
                r"^it['’]s not just about asking the right questions; it['’]s about orchestrating .+$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append("The operating model is the strategy.")
                continue
            if re.match(
                r"^.+\bare now essential to (?:our |the )?content generation$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append(_operator_system_sentence_from_brief(brief) or "Context survives the handoff.")
                continue
            if re.match(
                r"^(?:the )?.+?\s+(?:illustrates|make(?:s|d))\s+this\s+clear(?:ly)?$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append(_named_reference_sentence_from_brief(brief) or _ensure_sentence(normalized))
                continue
            if re.match(
                r"^previously, we dealt with malformed json and inconsistent schema discipline$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append("Malformed JSON kept breaking the flow.")
                continue
            if re.match(
                r"^previously, we faced issues with malformed json and (?:weak|inconsistent) schema discipline$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append("Malformed JSON and weak schema discipline kept breaking the flow.")
                continue
            if re.match(
                r"^we(?:['’]?re| are) enhancing output handling and validation, even as we continue to improve reliability$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append("Output handling is stricter now. Reliability is better, but not done.")
                continue
            if re.match(
                r"^we(?:['’]?ve| have) transitioned to (?:a )?unified .+\brouted workspace snapshot\b.*$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append(_operator_system_sentence_from_brief(brief) or "One routed workspace snapshot now holds the system.")
                continue
            tightened_match = re.match(
                r"^(?:now,\s*)?we(?:['’]?ve| have) tightened (.+)$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if tightened_match:
                payload = tightened_match.group(1).strip(" .")
                if re.search(r"\boutput handling\b|\bvalidation\b", payload, flags=re.IGNORECASE):
                    rewritten.append("Output handling is tighter now.")
                else:
                    rewritten.append(_ensure_sentence(f"{payload[:1].upper() + payload[1:]} is tighter now"))
                continue
            tightening_match = re.match(
                r"^(?:now,\s*)?we(?:['’]?re| are) (?:tightening|making stricter) (.+)$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if tightening_match:
                payload = tightening_match.group(1).strip(" .")
                if re.search(r"\boutput handling\b|\bvalidation\b", payload, flags=re.IGNORECASE):
                    rewritten.append("Output handling is tighter now.")
                else:
                    rewritten.append(_ensure_sentence(f"{payload[:1].upper() + payload[1:]} is tighter now"))
                continue
            unified_match = re.match(
                r"^with (.+?), we(?:['’]?ve| have) unified (.+?) around (.+)$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if unified_match:
                payload = unified_match.group(2).strip(" .")
                target = unified_match.group(3).strip(" .")
                rewritten.append(_ensure_sentence(f"{payload[:1].upper() + payload[1:]} now run on {target}"))
                continue
            unified_simple_match = re.match(
                r"^with (.+?), we(?:['’]?ve| have) unified (.+)$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if unified_simple_match:
                payload = unified_simple_match.group(2).strip(" .")
                rewritten.append(_ensure_sentence(f"{payload[:1].upper() + payload[1:]} now run together"))
                continue
            began_building_match = re.match(
                r"^we began building (.+?)(?: as (.+))?$",
                base_sentence,
                flags=re.IGNORECASE,
            )
            if began_building_match:
                subject = began_building_match.group(1).strip(" .")
                descriptor = (began_building_match.group(2) or "").strip(" .")
                if descriptor:
                    rewritten.append(_ensure_sentence(f"{subject[:1].upper() + subject[1:]} started as {descriptor}"))
                else:
                    rewritten.append(_ensure_sentence(f"{subject[:1].upper() + subject[1:]} started there"))
                continue
            if re.match(
                r"^for effective ai, .+\binterconnected\b.*$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append("Operator context has to travel.")
                continue
            if re.match(
                r"^this integration is crucial; without it, the system breaks$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                continue
            if re.match(
                r"^with this setup, context flows seamlessly, enhancing .+$",
                base_sentence,
                flags=re.IGNORECASE,
            ):
                rewritten.append(_operator_system_sentence_from_brief(brief) or "Context travels.")
                continue
            if re.search(r"\bcontext flows seamlessly\b", base_sentence, flags=re.IGNORECASE):
                rewritten.append(_operator_system_sentence_from_brief(brief) or "Context travels.")
                continue
            if _looks_like_operator_catalog_sentence(base_sentence):
                rewritten.append(_operator_system_sentence_from_brief(brief) or "Operator context has to travel.")
                continue
            if re.match(r"^everything(?:['’]s| is) interconnected\b", base_sentence, flags=re.IGNORECASE):
                continue
            if re.match(r"^(?:it|that)(?:['’]s| is) making (?:a|an) (?:real|tangible|meaningful) impact\b", base_sentence, flags=re.IGNORECASE):
                continue
            rewritten.append(_ensure_sentence(normalized))
        if rewritten:
            revised_paragraphs.append(" ".join(rewritten).strip())
    return "\n\n".join(revised_paragraphs) if revised_paragraphs else cleaned


def _public_safe_claim_from_brief(brief: ContentOptionBrief) -> str:
    claim = _ensure_sentence(brief.primary_claim)
    if not claim:
        return ""
    stripped = claim.rstrip(".")
    if re.match(r"^owner treats (.+?) as (.+)$", stripped, flags=re.IGNORECASE):
        match = re.match(r"^owner treats (.+?) as (.+)$", stripped, flags=re.IGNORECASE)
        if match:
            subject = match.group(1).strip(" .")
            complement = match.group(2).strip(" .")
            return _ensure_sentence(f"{subject[:1].upper() + subject[1:]} is {complement}")
    if re.match(r"^owner keeps moving work from (.+?) into (.+)$", stripped, flags=re.IGNORECASE):
        match = re.match(r"^owner keeps moving work from (.+?) into (.+)$", stripped, flags=re.IGNORECASE)
        if match:
            source = match.group(1).strip(" .")
            target = match.group(2).strip(" .")
            return _ensure_sentence(f"The work has to move from {source} into {target}")
    if re.match(r"^owner is building at the intersection of (.+)$", stripped, flags=re.IGNORECASE):
        match = re.match(r"^owner is building at the intersection of (.+)$", stripped, flags=re.IGNORECASE)
        if match:
            subject = match.group(1).strip(" .")
            return _ensure_sentence(f"The work sits at the intersection of {subject}")
    if _starts_with_third_person_persona_bio(claim):
        return ""
    return claim


def _rewrite_persona_bio_opening(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned or not _starts_with_third_person_persona_bio(cleaned):
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return cleaned
    first_paragraph_sentences = [
        _ensure_sentence(sentence.strip())
        for sentence in _split_sentences(paragraphs[0])
        if sentence.strip()
    ]
    remaining_sentences = [
        sentence
        for sentence in first_paragraph_sentences
        if not _starts_with_third_person_persona_bio(sentence)
    ]
    replacement = _opening_line_from_brief(brief) or _public_safe_claim_from_brief(brief)
    if replacement:
        paragraphs[0] = " ".join([replacement] + remaining_sentences).strip()
    elif remaining_sentences:
        paragraphs[0] = " ".join(remaining_sentences).strip()
    else:
        paragraphs = paragraphs[1:]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _strip_lane_label_opening(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return cleaned
    first_paragraph = paragraphs[0]
    rewritten = re.sub(
        r"^(?:operator lesson|market insight|build[ -]in[ -]public|contrarian reframe|reframe|recognition)\s*:\s*",
        "",
        first_paragraph,
        flags=re.IGNORECASE,
    )
    rewritten = re.sub(
        r"^warning(?:\s+for\s+[^:]+)?\s*:\s*",
        "",
        rewritten,
        flags=re.IGNORECASE,
    )
    rewritten = rewritten.strip()
    if rewritten and rewritten != first_paragraph:
        paragraphs[0] = _ensure_public_sentence(rewritten)
    return "\n\n".join(paragraphs)


def _rewrite_public_story_beat_phrases(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    rewritten = cleaned
    replacements = (
        (r"\bQuiet Inefficiency Cleanup\b", "quiet inefficiency"),
        (r"\bAI Constraint Breakthrough\b", "the constraint that changed the workflow"),
    )
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    return rewritten


def _rewrite_public_house_phrases(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    rewritten = cleaned
    rewritten = re.sub(
        r"(?im)^\s*Not more reporting\.\s*Clearer action\.\s*(?:\n\s*)?",
        "",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^\s*That is when the work slips\.\s*(?:\n\s*)?",
        "",
        rewritten,
    )
    rewritten = re.sub(
        r"\bWarning from the build log:\b",
        "Warning:",
        rewritten,
        flags=re.IGNORECASE,
    )
    return rewritten.strip()


def _rewrite_public_system_phrases(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    rewritten = cleaned
    replacements = (
        (r"\bone Salesforce command center\b", "one shared operating view"),
        (r"\bSalesforce command center\b", "shared operating view"),
        (r"\bSalesforce dashboard\b", "shared dashboard"),
        (r"\bcommand center\b", "shared operating view"),
        (r"\bagent orchestration\b", "coordinated workflow"),
        (r"\borchestrated workflow clarity\b", "coordinated workflow"),
        (r"\boperating pattern\b", "workflow design"),
        (r"\boperating model\b", "workflow design"),
        (r"\boperator pattern\b", "workflow design"),
        (r"\bThe operator lesson:\s*", ""),
        (r"\bThe market insight:\s*", ""),
        (r"\bThe build[ -]in[ -]public lesson:\s*", ""),
        (r"\bMy operator lesson:\s*", ""),
        (r"\bSo I build in public:\s*", ""),
        (r"\bbuild[ -]in[ -]public ritual\b", "build-in-public habit"),
        (r"\bThe prompt is not the system\. The workflow is\.", "The workflow matters more than the tool."),
        (r"\bmap the system,\s*then let automation run\b", "get the workflow clear, then let automation run"),
        (r"\bOtherwise you(?:['’]?re| are) just pouring GPUs on top of low-trust reporting\b", "Otherwise automation just speeds up low-trust reporting"),
        (r"\bquiet inefficiency is the fastest market insight you can ship right now\b", "Quiet inefficiency is usually the signal to fix first"),
    )
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    return rewritten.strip()


def _drop_redundant_label_tail(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if len(paragraphs) < 2:
        return cleaned
    last_paragraph = paragraphs[-1]
    if len(last_paragraph.split()) > 4:
        return cleaned
    prior_text = " ".join(paragraphs[:-1]).lower()
    if last_paragraph.lower() in prior_text:
        return "\n\n".join(paragraphs[:-1])
    last_terms = _significant_terms(last_paragraph)
    prior_terms = _significant_terms(" ".join(paragraphs[:-1]))
    if last_terms and last_terms.issubset(prior_terms):
        return "\n\n".join(paragraphs[:-1])
    return cleaned


def _sentence_has_unapproved_reference(
    sentence: str,
    *,
    approved_reference_terms: List[str],
    audience: str,
) -> bool:
    approved_terms = _normalized_terms(" ".join(approved_reference_terms))
    approved_terms.update(_extract_named_reference_candidates(" ".join(approved_reference_terms)))
    if _extract_named_reference_candidates(sentence) - approved_terms:
        return True
    if audience == "tech_ai":
        lowered = " ".join((sentence or "").lower().split())
        for placeholder in UNSUPPORTED_EVIDENCE_PLACEHOLDERS:
            if placeholder in lowered and placeholder not in approved_terms:
                return True
    return False


def _drop_unapproved_reference_sentences(
    option: str,
    *,
    brief: ContentOptionBrief,
    approved_reference_terms: List[str],
    audience: str,
) -> str:
    cleaned = (option or "").strip()
    if not cleaned or not approved_reference_terms:
        return cleaned
    if not option_uses_unapproved_reference(
        cleaned,
        approved_reference_terms=approved_reference_terms,
        audience=audience,
    ):
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    revised_paragraphs: List[str] = []
    for paragraph in paragraphs:
        kept_sentences: List[str] = []
        for sentence in _split_sentences(paragraph):
            normalized = _ensure_sentence(sentence.strip())
            if not normalized:
                continue
            if _sentence_has_unapproved_reference(
                normalized,
                approved_reference_terms=approved_reference_terms,
                audience=audience,
            ):
                continue
            kept_sentences.append(normalized)
        if kept_sentences:
            revised_paragraphs.append(" ".join(kept_sentences).strip())
    revised = "\n\n".join(revised_paragraphs).strip()
    if not revised:
        revised = _synthesize_planned_option(brief)
    if brief.proof_packet and not option_mentions_approved_proof(revised, [brief.proof_packet]):
        revised = _force_brief_proof_support(revised, brief)
    return revised


def _drop_meta_thesis_scaffold(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if len(paragraphs) < 2:
        return cleaned
    scaffold_pattern = re.compile(
        r"^(?:the key (?:insight|lesson|point) is that|here(?:'s| is) the thing|the default read is wrong)\b",
        flags=re.IGNORECASE,
    )
    revised: List[str] = []
    for index, paragraph in enumerate(paragraphs):
        if not scaffold_pattern.match(paragraph):
            revised.append(paragraph)
            continue
        other_paragraphs = [segment for inner_index, segment in enumerate(paragraphs) if inner_index != index]
        other_text = "\n\n".join(other_paragraphs)
        if _claim_near_opening(other_text, brief.primary_claim) or any(
            _sentence_is_signal_bearing(candidate, brief) for candidate in other_paragraphs
        ):
            continue
        revised.append(paragraph)
    return "\n\n".join(revised) if revised else cleaned


def _dedupe_repeated_paragraphs(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    deduped: List[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        normalized = " ".join(paragraph.lower().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(paragraph)
    return "\n\n".join(deduped)


def _normalize_public_acronyms(option: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    rewritten = _rewrite_audience_slug_public_copy(cleaned)
    rewritten = re.sub(r"\bai\b", "AI", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bapi\b", "API", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bjson\b", "JSON", rewritten, flags=re.IGNORECASE)
    return rewritten


def _ensure_sharp_landing(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if not paragraphs:
        return cleaned
    closer = _strong_closer_from_brief(brief)
    if not closer:
        return cleaned
    last_paragraph = paragraphs[-1]
    sentences = [_ensure_sentence(sentence.strip()) for sentence in _split_sentences(last_paragraph) if sentence.strip()]
    kept_sentences: List[str] = []
    for sentence in sentences:
        if _closer_needs_sharpening(sentence, brief) and not _sentence_is_signal_bearing(sentence, brief):
            continue
        kept_sentences.append(sentence)
    if kept_sentences:
        paragraphs[-1] = " ".join(kept_sentences).strip()
    else:
        paragraphs.pop()
    if not paragraphs:
        paragraphs.append(closer)
        return "\n\n".join(paragraphs)
    trailing_sentences = _split_sentences(paragraphs[-1])
    trailing = trailing_sentences[-1] if trailing_sentences else ""
    if _closer_needs_sharpening(trailing, brief):
        if len(paragraphs[-1].split()) <= 8:
            paragraphs[-1] = closer
        elif closer.lower() not in " ".join(paragraphs).lower():
            paragraphs.append(closer)
    elif len(paragraphs) < 2 and closer.lower() not in paragraphs[-1].lower():
        paragraphs.append(closer)
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _paragraph_has_coherence_bridge(paragraph: str, brief: ContentOptionBrief) -> bool:
    normalized = " ".join((paragraph or "").lower().split())
    if not normalized:
        return False
    if any(
        phrase in normalized
        for phrase in (
            "that is why",
            "which is why",
            "the lesson",
            "warning for",
            "before you",
            "otherwise",
            "that is where",
        )
    ):
        return True
    return False


def _ensure_coherent_progression(option: str, brief: ContentOptionBrief) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    if len(paragraphs) <= 2:
        return cleaned

    opening = paragraphs[0]
    remainder = paragraphs[1:]
    if not remainder:
        return cleaned

    support_index = next(
        (
            index
            for index, paragraph in enumerate(remainder)
            if option_mentions_approved_proof(paragraph, [brief.proof_packet])
            or _option_has_named_reference_specificity(paragraph, brief)
            or _sentence_is_signal_bearing(paragraph, brief)
        ),
        None,
    )
    if support_index is not None and support_index > 0:
        support_paragraph = remainder.pop(support_index)
        remainder.insert(0, support_paragraph)

    rebuilt = [opening]
    rebuilt.extend(remainder)

    if len(rebuilt) >= 3:
        second_paragraph = rebuilt[1]
        third_paragraph = rebuilt[2]
        if _paragraph_has_coherence_bridge(second_paragraph, brief) and (
            option_mentions_approved_proof(third_paragraph, [brief.proof_packet])
            or _option_has_named_reference_specificity(third_paragraph, brief)
        ):
            rebuilt[1], rebuilt[2] = rebuilt[2], rebuilt[1]

    deduped: List[str] = []
    seen: set[str] = set()
    for paragraph in rebuilt:
        normalized = " ".join(paragraph.lower().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(paragraph)
    return "\n\n".join(deduped)


def finalize_planned_options(
    *,
    options: List[str],
    briefs: List[ContentOptionBrief],
    grounding_mode: str,
) -> List[str]:
    finalized: List[str] = []
    for index, option in enumerate(options):
        brief = briefs[index] if index < len(briefs) else briefs[-1]
        revised = _replace_flat_opening_with_claim(option, brief)
        revised = _rewrite_persona_bio_opening(revised, brief)
        revised = _strip_lane_label_opening(revised)
        revised = _rewrite_public_story_beat_phrases(revised)
        revised = _rewrite_public_house_phrases(revised)
        revised = _rewrite_public_system_phrases(revised)
        revised = _force_claim_lead(revised, brief)
        revised = _shape_opening_by_mode(revised, brief)
        if grounding_mode == "proof_ready":
            revised = _force_brief_proof_support(revised, brief)
        revised = _ensure_contrast_shape(revised, brief)
        revised = _clean_generic_sentences(revised, brief)
        revised = _rewrite_internal_public_jargon(revised)
        revised = _rewrite_soft_operator_sentences(revised, brief)
        revised = _drop_opening_restatement(revised, brief)
        revised = _drop_filler_fragment_paragraphs(revised, brief)
        revised = _drop_meta_thesis_scaffold(revised, brief)
        revised = _ensure_paragraph_cadence(revised, brief)
        revised = _ensure_sharp_landing(revised, brief)
        revised = _rewrite_soft_operator_sentences(revised, brief)
        revised = _ensure_named_reference_specificity(revised, brief)
        revised = _ensure_short_sentence_presence(revised, brief)
        revised = _ensure_coherent_progression(revised, brief)
        revised = _drop_redundant_label_tail(revised)
        revised = _dedupe_repeated_paragraphs(revised)
        revised = _stabilize_claim_opening(revised, brief)
        revised = _normalize_public_acronyms(revised)
        if grounding_mode == "proof_ready":
            revised = _force_brief_proof_support(revised, brief)
        finalized.append(revised)
    return finalized[: len(briefs)]


def _sanitize_public_output(option: str, brief: ContentOptionBrief) -> str:
    revised = (option or "").strip()
    if not revised:
        return revised
    revised = _rewrite_persona_bio_opening(revised, brief)
    revised = _strip_lane_label_opening(revised)
    revised = _rewrite_public_story_beat_phrases(revised)
    revised = _rewrite_public_house_phrases(revised)
    revised = _rewrite_public_system_phrases(revised)
    revised = _clean_generic_sentences(revised, brief)
    revised = _rewrite_internal_public_jargon(revised)
    revised = _rewrite_soft_operator_sentences(revised, brief)
    revised = _drop_opening_restatement(revised, brief)
    revised = _drop_filler_fragment_paragraphs(revised, brief)
    revised = _drop_meta_thesis_scaffold(revised, brief)
    revised = _ensure_paragraph_cadence(revised, brief)
    revised = _ensure_sharp_landing(revised, brief)
    revised = _rewrite_soft_operator_sentences(revised, brief)
    revised = _ensure_coherent_progression(revised, brief)
    revised = _drop_redundant_label_tail(revised)
    revised = _dedupe_repeated_paragraphs(revised)
    revised = _stabilize_claim_opening(revised, brief)
    revised = _normalize_public_acronyms(revised)
    return revised


def _sanitize_public_output_safety_only(option: str, brief: ContentOptionBrief) -> str:
    """Remove public-release hazards without editing the writer's structure or payoff.

    Independent criticism needs to inspect the writer's actual treatments. Cadence,
    coherence, and landing edits belong after that comparison; applying them here can
    turn different drafts into the same house-shaped post. This path therefore keeps
    only the transformations required to prevent persona-bio, internal-jargon, lane-
    label, audience-slug, and private-story-beat leakage.
    """

    revised = (option or "").strip()
    if not revised:
        return revised
    revised = _rewrite_persona_bio_opening(revised, brief)
    revised = _strip_lane_label_opening(revised)
    revised = _rewrite_public_story_beat_phrases(revised)
    revised = _rewrite_internal_public_jargon(revised)

    # Known internal phrases are rewritten above. If an operator-catalog sentence
    # still trips the contamination detector, remove only that unsafe sentence;
    # leave every safe paragraph and sentence in its writer-authored position.
    if _internal_public_jargon_hits(revised):
        safe_paragraphs: List[str] = []
        for paragraph in re.split(r"\n\s*\n", revised):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            safe_sentences = [
                _ensure_sentence(sentence.strip())
                for sentence in _split_sentences(paragraph)
                if sentence.strip() and not _internal_public_jargon_hits(sentence)
            ]
            if safe_sentences:
                safe_paragraphs.append(" ".join(safe_sentences).strip())
        revised = "\n\n".join(safe_paragraphs).strip()
        if not revised:
            revised = _public_safe_claim_from_brief(brief)

    return _normalize_public_acronyms(revised)


def build_proof_enforcement_prompt(
    *,
    topic: str,
    audience: str,
    rough_options: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
    voice_directives: Optional[List[str]] = None,
) -> str:
    option_count = max(len(rough_options), 1)
    option_suffix = "" if option_count == 1 else "s"
    separator_instruction = (
        "Output only the rewritten canonical option; do not add an option heading or hidden alternative."
        if option_count == 1
        else "Output only the rewritten options, separated by ---OPTION---."
    )
    audience_label = _audience_prompt_label(audience)
    options_text = "\n---OPTION---\n".join(rough_options)
    claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- Stay inside the topic."
    proof_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No proof packets available."
    story_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No approved story beats."
    approved_references = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    approved_reference_text = "\n".join(f"- {reference}" for reference in approved_references) or "- No approved named references."
    framing_text = "\n".join(
        f"- `{mode}`: {FRAMING_MODE_GUIDANCE.get(mode, mode.replace('_', ' '))}"
        for mode in framing_modes
    ) or "- `operator_lesson`"
    voice_text = "\n".join(f"- {directive}" for directive in (voice_directives or DEFAULT_VOICE_DIRECTIVES[:6]))
    public_post_guardrails = _render_public_post_guardrails()
    option_plan_text = _render_option_framing_plan(
        _build_option_framing_plan(
            framing_modes=framing_modes,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            option_count=option_count,
        )
    )
    return f"""You are repairing draft posts that are too generic and are not carrying the approved proof strongly enough.

Topic: {topic}
Audience: {audience_label}

PRIMARY CLAIMS:
{claims_text}

APPROVED PROOF PACKETS:
{proof_text}

OPTIONAL STORY BEATS:
{story_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

PUBLIC POST GUARDRAILS:
{public_post_guardrails}

APPROVED FRAMING MODES:
{framing_text}

OPTION FRAMING PLAN:
{option_plan_text}

VOICE SHAPING RULES:
{voice_text}

DRAFTS TO REWRITE:
{options_text}

REWRITE RULES:
- Keep exactly {option_count} option{option_suffix}.
- Each option must use one PRIMARY CLAIM.
- Each option must explicitly mention at least one named system, artifact, or evidence phrase from an APPROVED PROOF PACKET.
- Only use named references that appear in the APPROVED PROOF PACKETS, OPTIONAL STORY BEATS, or ONLY THESE NAMED REFERENCES list above.
- Remove unsupported references like videos, schools, employers, or projects that are not explicitly approved above.
- When an APPROVED PROOF PACKET contains `label -> evidence`, use the evidence side, not just the label side.
- Keep the original proof meaning intact. Do not generalize it into vague productivity language.
- Do not use phrases like seamless, unlock potential, drive results, or everything flows.
- Preserve the person's casual rhythm and punchy style.
- Follow the assigned framing mode for every option.
- Use the assigned OPTION FRAMING PLAN without introducing extra options or theses.
- Delete filler beats like "Why?" and remove standalone restatements of the opener.
- Do not stack multiple short fragments before the proof line.

{separator_instruction}
"""


def build_refinement_prompt(
    *,
    topic: str,
    audience: str,
    persona_chunks: List[Dict[str, Any]],
    rough_options: List[str],
    topic_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    eligible_story_chunks: Optional[List[Dict[str, Any]]] = None,
    proof_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    grounding_mode: Optional[str] = None,
    grounding_reason: Optional[str] = None,
    framing_modes: Optional[List[str]] = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    disallowed_moves: Optional[List[str]] = None,
) -> str:
    option_count = max(len(rough_options), 1)
    option_suffix = "" if option_count == 1 else "s"
    separator_instruction = (
        "Output only the rewritten canonical option; do not add an option heading or hidden alternative."
        if option_count == 1
        else "Output only the rewritten options, separated by ---OPTION---."
    )
    audience_label = _audience_prompt_label(audience)
    topic_anchor_chunks = topic_anchor_chunks or select_topic_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    eligible_story_chunks = eligible_story_chunks or select_eligible_story_chunks(persona_chunks, topic=topic, audience=audience, limit=3)
    proof_anchor_chunks = proof_anchor_chunks or select_proof_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    primary_claims = primary_claims or []
    proof_packets = proof_packets or []
    story_beats = story_beats or []
    topic_anchor_text = _prompt_topic_anchor_text(
        topic_anchor_chunks=topic_anchor_chunks,
        primary_claims=primary_claims,
        limit=4,
    )
    eligible_story_text = _prompt_story_anchor_text(
        story_anchor_chunks=eligible_story_chunks,
        story_beats=story_beats,
        limit=3,
    ) if eligible_story_chunks or story_beats else "- No directly relevant story anchor found. Do not force one."
    proof_anchor_text = _prompt_proof_anchor_text(
        proof_anchor_chunks=proof_anchor_chunks,
        proof_packets=proof_packets,
        limit=4,
    ) if proof_anchor_chunks or proof_packets else "- No strong proof anchor found. Stay concrete about process and role."
    grounding_mode = grounding_mode or ("proof_ready" if proof_anchor_chunks else "principle_only")
    grounding_reason = grounding_reason or (
        "Concrete proof anchors are available, so the post can stay specific."
        if proof_anchor_chunks
        else "No strong proof anchor was found, so the post should stay principle-led."
    )
    approved_framing_modes = framing_modes or ["operator_lesson", "contrarian_reframe", "reframe"]
    framing_modes_text = "\n".join(
        f"- `{mode}`: {FRAMING_MODE_GUIDANCE.get(mode, mode.replace('_', ' '))}"
        for mode in approved_framing_modes
    )
    disallowed_moves = disallowed_moves or []
    primary_claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- No pre-composed primary claims."
    proof_packets_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No approved proof packets."
    story_beats_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No approved story beats."
    disallowed_moves_text = "\n".join(f"- {move}" for move in disallowed_moves) or "- No extra banned moves."
    approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    approved_reference_text = "\n".join(f"- {term}" for term in approved_reference_terms) or "- No approved named references."
    public_post_guardrails = _render_public_post_guardrails()
    voice_directives = _extract_voice_directives(persona_chunks, limit=8)
    voice_directives_text = "\n".join(f"- {directive}" for directive in voice_directives)
    option_framing_plan_text = _render_option_framing_plan(
        _build_option_framing_plan(
            framing_modes=approved_framing_modes,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            option_count=option_count,
        )
    )
    rough_text = "\n---OPTION---\n".join(rough_options)
    return f"""You are revising drafted posts so they sound sharper, more specific, and more faithful to this person's canon.

Topic: {topic}
Audience: {audience_label}

TOPIC ANCHORS:
{topic_anchor_text}

ELIGIBLE STORY / PROOF ANCHORS:
{eligible_story_text}

PROOF ANCHORS:
{proof_anchor_text}

GROUNDING MODE:
- `{grounding_mode}`
- {grounding_reason}

APPROVED FRAMING MODES:
{framing_modes_text}

OPTION FRAMING PLAN:
{option_framing_plan_text}

PRIMARY CLAIMS YOU MAY MAKE:
{primary_claims_text}

APPROVED PROOF PACKETS:
{proof_packets_text}

OPTIONAL STORY BEATS:
{story_beats_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

PUBLIC POST GUARDRAILS:
{public_post_guardrails}

DISALLOWED MOVES:
{disallowed_moves_text}

VOICE SHAPING RULES:
{voice_directives_text}

ROUGH OPTIONS TO REWRITE:
{rough_text}

REVISION RULES:
- Keep exactly {option_count} option{option_suffix}.
- Preserve the person's casual voice and punchy rhythm.
- Remove generic filler, motivational fluff, and any language that could apply to anyone.
- Make sure each option clearly leads with one approved PRIMARY CLAIM.
- Use APPROVED PROOF PACKETS as supporting evidence, not as the whole thesis unless the approved claim is already proof-shaped.
- Preserve the dramatic, contrarian, agreement, or tension-based framing when it is grounded in the approved framing modes above.
- Ban phrases like "magic happens", "synergy", "game changer", "nice-to-have", "backbone", and "thrive in AI".
- Every option must be grounded in the topic anchors above.
- Only use a personal anecdote if it appears in the eligible story / proof anchors above.
- Each option must include at least one concrete proof anchor, named system, evidence phrase, or metric from the PROOF ANCHORS above when available.
- Never translate one metric into another. If a proof anchor mentions participation, utilization, or revenue, keep that exact subject or omit the number.
- If no eligible story anchor exists, do not force a story. Stay with proof, pattern, and operating insight.
- Replace vague claims with concrete operator language: workflow, handoff, prompt, system, proof, constraint, operating cadence.
- Do not rely on the label side of a proof packet when the evidence side contains the real operator proof.
- Cut weak setup lines. Start faster.
- Use one PRIMARY CLAIM per option and make it legible in the first lines.
- Use the OPTION FRAMING PLAN above so each option lands with a different rhetorical posture.
- Use the VOICE SHAPING RULES above. Keep the writing spoken, specific, and sharp.
- Do not describe the author in third person. Rewrite `the owner is...` / `the owner treats...` / `the owner is building...` into first-person or direct thesis voice.
- Do not leave internal shorthand like `shared workspace state`, `typed retrieval`, `proof-aware prompts`, or `operating rhythm` in public copy. Translate them into macro language instead.
- If `proof_ready`, tie each option to one APPROVED PROOF PACKET and preserve its exact meaning.
- If `principle_only`, remove stray named examples that are not explicitly present in PRIMARY CLAIMS.
- If a named reference is not in the APPROVED PROOF PACKETS, OPTIONAL STORY BEATS, or ONLY THESE NAMED REFERENCES list, remove it.
- Delete filler beats like "Why?" and remove short standalone restatements that only repeat the opener.
- Keep each option as one clear opener, one proof-bearing middle, and one sharp landing.

{separator_instruction}
"""


def build_voice_sharpen_prompt(
    *,
    topic: str,
    audience: str,
    rough_options: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
    voice_directives: List[str],
) -> str:
    option_count = max(len(rough_options), 1)
    option_suffix = "" if option_count == 1 else "s"
    separator_instruction = (
        "Output only the sharpened canonical option; do not add an option heading or hidden alternative."
        if option_count == 1
        else "Output only the rewritten options, separated by ---OPTION---."
    )
    audience_label = _audience_prompt_label(audience)
    options_text = "\n---OPTION---\n".join(rough_options)
    claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- Stay tightly inside the topic."
    proof_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No approved proof packets."
    story_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No approved story beats."
    voice_text = "\n".join(f"- {directive}" for directive in voice_directives) or "\n".join(
        f"- {directive}" for directive in DEFAULT_VOICE_DIRECTIVES[:6]
    )
    option_plan_text = _render_option_framing_plan(
        _build_option_framing_plan(
            framing_modes=framing_modes,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            option_count=option_count,
        )
    )
    approved_reference_text = "\n".join(
        f"- {reference}"
        for reference in _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    ) or "- No approved named references."
    public_post_guardrails = _render_public_post_guardrails()
    return f"""You are the final editorial pass. The facts are already approved. Your job is to make the writing sound sharper, more strategic, and more like this person.

Topic: {topic}
Audience: {audience_label}

PRIMARY CLAIMS:
{claims_text}

APPROVED PROOF PACKETS:
{proof_text}

OPTIONAL STORY BEATS:
{story_text}

OPTION FRAMING PLAN:
{option_plan_text}

VOICE SHAPING RULES:
{voice_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

PUBLIC POST GUARDRAILS:
{public_post_guardrails}

DRAFTS TO SHARPEN:
{options_text}

SHARPENING RULES:
- Keep exactly {option_count} option{option_suffix}.
- Do not add new facts, names, or proof.
- Preserve the approved claim and proof meaning exactly.
- Remove flat openers like "X is essential", "X is critical", or "In today's world".
- Start faster. Lead with tension, contrast, recognition, warning, or operator insight.
- Keep the writing casual, direct, and punchy.
- Use the OPTION FRAMING PLAN so each option lands differently.
- Do not collapse the options into the same rhythm or hook.
- Keep line breaks and cadence human.
- If a line sounds like generic LinkedIn advice, replace it with sharper operator language.
- Do not use third-person persona framing in public posts.
- Translate internal operator shorthand into macro public language.
- Delete filler beats like "Why?" and cut repeated opener lines.
- Keep one strong punch line, not a stack of fragments.
- Do not use meta directives like "Read that again" or "Write that down".

{separator_instruction}
"""


def refine_generated_options(
    *,
    client: Any,
    topic: str,
    audience: str,
    content_type: str,
    persona_chunks: List[Dict[str, Any]],
    rough_options: List[str],
    topic_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    eligible_story_chunks: Optional[List[Dict[str, Any]]] = None,
    proof_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    grounding_mode: Optional[str] = None,
    grounding_reason: Optional[str] = None,
    framing_modes: Optional[List[str]] = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    disallowed_moves: Optional[List[str]] = None,
) -> List[str]:
    if content_type != "linkedin_post" or not rough_options:
        return rough_options

    response = client.chat.completions.create(
        model=CONTENT_FAST_MODEL_ALIAS,
        messages=[
            {
                "role": "system",
                "content": "You are a strict editorial pass. Make the writing sharper and more concrete without changing the author's voice.",
            },
            {
                "role": "user",
                "content": build_refinement_prompt(
                    topic=topic,
                    audience=audience,
                    persona_chunks=persona_chunks,
                    rough_options=rough_options,
                    topic_anchor_chunks=topic_anchor_chunks,
                    eligible_story_chunks=eligible_story_chunks,
                    proof_anchor_chunks=proof_anchor_chunks,
                    grounding_mode=grounding_mode,
                    grounding_reason=grounding_reason,
                    framing_modes=framing_modes,
                    primary_claims=primary_claims,
                    proof_packets=proof_packets,
                    story_beats=story_beats,
                    disallowed_moves=disallowed_moves,
                ),
            },
        ],
        temperature=_refinement_temperature(),
        max_tokens=1800,
    )
    refined = parse_content_options(response.choices[0].message.content or "")
    return refined[: len(rough_options)] if len(refined) >= len(rough_options) else rough_options


def sharpen_editorial_options(
    *,
    client: Any,
    topic: str,
    audience: str,
    content_type: str,
    grounding_mode: str,
    persona_chunks: List[Dict[str, Any]],
    rough_options: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
) -> List[str]:
    if content_type != "linkedin_post" or not rough_options or not _options_need_voice_sharpening(rough_options):
        return rough_options
    voice_directives = _extract_voice_directives(persona_chunks, limit=8)
    messages = [
        {
            "role": "system",
            "content": "You are a final editorial sharpener. Improve rhetoric and cadence without changing approved facts or voice.",
        },
        {
            "role": "user",
            "content": build_voice_sharpen_prompt(
                topic=topic,
                audience=audience,
                rough_options=rough_options,
                primary_claims=primary_claims,
                proof_packets=proof_packets,
                story_beats=story_beats,
                framing_modes=framing_modes,
                voice_directives=voice_directives,
            ),
        },
    ]
    try:
        response = client.chat.completions.create(
            model=_final_editor_model(),
            messages=messages,
            temperature=_final_editor_temperature(),
            max_tokens=1800,
        )
    except Exception:
        response = client.chat.completions.create(
            model=CONTENT_FAST_MODEL_ALIAS,
            messages=messages,
            temperature=_final_editor_temperature(),
            max_tokens=1800,
        )
    sharpened = parse_content_options(response.choices[0].message.content or "")
    sharpened = sharpened[: len(rough_options)] if len(sharpened) >= len(rough_options) else rough_options
    if grounding_mode == "proof_ready" and proof_packets:
        approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
        if not all(
            option_mentions_approved_proof(option, proof_packets)
            and not option_uses_unapproved_reference(
                option,
                approved_reference_terms=approved_reference_terms,
                audience=audience,
            )
            for option in sharpened
        ):
            return rough_options
    baseline_score = sum(
        score_option_taste(
            option,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            grounding_mode=grounding_mode,
        )["overall"]
        for option in rough_options
    )
    sharpened_score = sum(
        score_option_taste(
            option,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            grounding_mode=grounding_mode,
        )["overall"]
        for option in sharpened
    )
    if sharpened_score + 3 < baseline_score:
        return rough_options
    return sharpened


def enforce_grounding_on_options(
    *,
    client: Any,
    topic: str,
    audience: str,
    content_type: str,
    grounding_mode: str,
    rough_options: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
) -> List[str]:
    if content_type != "linkedin_post" or grounding_mode != "proof_ready" or not proof_packets or not rough_options:
        return rough_options
    approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    if all(
        option_mentions_approved_proof(option, proof_packets)
        and not option_uses_unapproved_reference(
            option,
            approved_reference_terms=approved_reference_terms,
            audience=audience,
        )
        for option in rough_options
    ):
        return rough_options

    response = client.chat.completions.create(
        model=CONTENT_FAST_MODEL_ALIAS,
        messages=[
            {
                "role": "system",
                "content": "You are a strict factual editor. Keep the voice, but force the writing to carry the approved proof explicitly.",
            },
            {
                "role": "user",
                "content": build_proof_enforcement_prompt(
                    topic=topic,
                    audience=audience,
                    rough_options=rough_options,
                    primary_claims=primary_claims,
                    proof_packets=proof_packets,
                    story_beats=story_beats,
                    framing_modes=framing_modes,
                    voice_directives=DEFAULT_VOICE_DIRECTIVES[:6],
                ),
            },
        ],
        temperature=_proof_enforcement_temperature(),
        max_tokens=1800,
    )
    repaired = parse_content_options(response.choices[0].message.content or "")
    return repaired[: len(rough_options)] if len(repaired) >= len(rough_options) else rough_options


def _generate_legacy_options(
    *,
    client: Any,
    req: ContentGenerationRequest,
    content_context: ContentGenerationContext,
    persona_chunks: List[Dict[str, Any]],
    example_chunks: List[Dict[str, Any]],
) -> List[str]:
    prompt = build_content_prompt(
        topic=req.topic,
        context=req.context or "",
        content_type=req.content_type,
        category=req.category,
        pacer_elements=req.pacer_elements,
        tone=req.tone,
        persona_chunks=persona_chunks,
        example_chunks=example_chunks,
        audience=req.audience,
        topic_anchor_chunks=content_context.topic_anchor_chunks,
        eligible_story_chunks=content_context.story_anchor_chunks,
        proof_anchor_chunks=content_context.proof_anchor_chunks,
        grounding_mode=content_context.grounding_mode,
        grounding_reason=content_context.grounding_reason,
        framing_modes=content_context.framing_modes,
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        disallowed_moves=content_context.disallowed_moves,
        option_count=req.option_count,
    )
    response = client.chat.completions.create(
        model=CONTENT_FAST_MODEL_ALIAS,
        messages=[
            {
                "role": "system",
                "content": """You are a ghostwriter who perfectly mimics a specific person's voice.

CRITICAL RULES:
1. Use the EXACT voice patterns from the persona data (casual phrases, rhythm, signature expressions)
2. ONLY use stories, anecdotes, and facts EXPLICITLY mentioned in the persona data below
3. NEVER invent or fabricate stories - if no relevant story exists, speak generally about the topic
4. DO NOT make up family stories, childhood memories, or personal details not in the persona
5. Preserve casual markers like "Yall", "Tell you what tho", "Say it with me"
6. Keep punchy rhythm - short sentences, stacked phrases
7. DO NOT over-polish or make it sound generic/corporate
8. Stay focused on the user's TOPIC and CONTEXT - don't drift to unrelated subjects
9. Treat TOPIC ANCHORS as higher priority than generic biography
10. Only use a personal anecdote if it appears in ELIGIBLE STORY / PROOF ANCHORS
""",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=_legacy_generation_temperature(req.audience),
        max_tokens=2000,
    )
    raw_content = response.choices[0].message.content or ""
    options = parse_content_options(raw_content)
    options = refine_generated_options(
        client=client,
        topic=req.topic,
        audience=req.audience,
        content_type=req.content_type,
        persona_chunks=persona_chunks,
        rough_options=options,
        topic_anchor_chunks=content_context.topic_anchor_chunks,
        eligible_story_chunks=content_context.story_anchor_chunks,
        proof_anchor_chunks=content_context.proof_anchor_chunks,
        grounding_mode=content_context.grounding_mode,
        grounding_reason=content_context.grounding_reason,
        framing_modes=content_context.framing_modes,
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        disallowed_moves=content_context.disallowed_moves,
    )
    options = enforce_grounding_on_options(
        client=client,
        topic=req.topic,
        audience=req.audience,
        content_type=req.content_type,
        grounding_mode=content_context.grounding_mode,
        rough_options=options,
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        framing_modes=content_context.framing_modes,
    )
    options = sharpen_editorial_options(
        client=client,
        topic=req.topic,
        audience=req.audience,
        content_type=req.content_type,
        grounding_mode=content_context.grounding_mode,
        persona_chunks=persona_chunks,
        rough_options=options,
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        framing_modes=content_context.framing_modes,
    )
    return options[: req.option_count]


def _generate_staged_options(
    *,
    client: Any,
    req: ContentGenerationRequest,
    content_context: ContentGenerationContext,
    persona_chunks: List[Dict[str, Any]],
    example_chunks: List[Dict[str, Any]],
) -> tuple[List[str], List[ContentOptionBrief], str, Dict[str, Any]]:
    good_examples, avoid_examples = _split_example_references(example_chunks, limit=3)
    voice_directives = _extract_voice_directives(persona_chunks, limit=8)
    approved_references = _extract_approved_reference_terms(
        content_context.primary_claims,
        content_context.proof_packets,
        content_context.story_beats,
    )
    fallback_trace: Dict[str, Any] = {
        "events": [],
        "recovered_missing_option_count": 0,
        "critic_used_rough_options": False,
        "used_consolidated_refinement": False,
        "used_compact_single_pass": False,
        "legacy_fallback_triggered": False,
        "legacy_fallback_reason": "",
        "final_option_count_before_cap": 0,
    }
    briefs = plan_content_option_briefs(
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        framing_modes=content_context.framing_modes,
        option_count=req.option_count,
    )
    rough_options = write_planned_options(
        client=client,
        topic=req.topic,
        context=req.context or "",
        audience=req.audience,
        grounding_mode=content_context.grounding_mode,
        grounding_reason=content_context.grounding_reason,
        topic_anchor_chunks=content_context.topic_anchor_chunks,
        proof_anchor_chunks=content_context.proof_anchor_chunks,
        story_anchor_chunks=content_context.story_anchor_chunks,
        briefs=briefs,
        good_examples=good_examples,
        voice_directives=voice_directives,
        approved_references=approved_references,
        disallowed_moves=content_context.disallowed_moves,
    )
    if not rough_options:
        fallback_trace["events"].append(
            {
                "stage": "writer",
                "reason": "writer_returned_no_options",
                "action": "escalate_to_legacy_if_needed",
            }
        )
        return [], briefs, "planner_writer_critic", fallback_trace
    if len(rough_options) < len(briefs):
        missing_briefs = briefs[len(rough_options):]
        retry_options = write_planned_options(
            client=client,
            topic=req.topic,
            context=req.context or "",
            audience=req.audience,
            grounding_mode=content_context.grounding_mode,
            grounding_reason=content_context.grounding_reason,
            topic_anchor_chunks=content_context.topic_anchor_chunks,
            proof_anchor_chunks=content_context.proof_anchor_chunks,
            story_anchor_chunks=content_context.story_anchor_chunks,
            briefs=missing_briefs,
            good_examples=good_examples,
            voice_directives=voice_directives,
            approved_references=approved_references,
            disallowed_moves=content_context.disallowed_moves,
        )
        if retry_options:
            rough_options = (rough_options + retry_options)[: len(briefs)]
        if len(rough_options) < len(briefs):
            fallback_trace["recovered_missing_option_count"] = len(briefs) - len(rough_options)
            fallback_trace["events"].append(
                {
                    "stage": "writer",
                    "reason": "writer_returned_too_few_options",
                    "action": "recovered_from_planned_briefs",
                    "count": fallback_trace["recovered_missing_option_count"],
                }
            )
            rough_options = _recover_missing_planned_options(rough_options, briefs)
    if _use_compact_staged_generation(client, content_type=req.content_type):
        fallback_trace["used_compact_single_pass"] = True
        fallback_trace["events"].append(
            {
                "stage": "refinement",
                "reason": "used_compact_single_pass",
                "action": "writer_absorbed_refinement_rules",
            }
        )
        finalized = rough_options
    else:
        fallback_trace["used_consolidated_refinement"] = True
        fallback_trace["events"].append(
            {
                "stage": "refinement",
                "reason": "used_consolidated_refinement",
                "action": "collapsed_critic_grounding_and_editorial_passes",
            }
        )
        finalized = refine_generated_options(
            client=client,
            topic=req.topic,
            audience=req.audience,
            content_type=req.content_type,
            persona_chunks=persona_chunks,
            rough_options=rough_options,
            topic_anchor_chunks=content_context.topic_anchor_chunks,
            eligible_story_chunks=content_context.story_anchor_chunks,
            proof_anchor_chunks=content_context.proof_anchor_chunks,
            grounding_mode=content_context.grounding_mode,
            grounding_reason=content_context.grounding_reason,
            framing_modes=content_context.framing_modes,
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            disallowed_moves=content_context.disallowed_moves,
        )
    finalized = finalize_planned_options(
        options=finalized,
        briefs=briefs,
        grounding_mode=content_context.grounding_mode,
    )
    fallback_trace["final_option_count_before_cap"] = len(finalized)
    return finalized[: req.option_count], briefs, "planner_writer_critic", fallback_trace


def _provider_trace_indicates_fallback(provider_trace: List[Dict[str, Any]]) -> bool:
    if not provider_trace:
        return False
    distinct_providers = {
        str(entry.get("provider") or "").strip().lower()
        for entry in provider_trace
        if str(entry.get("provider") or "").strip()
    }
    if len(distinct_providers) > 1:
        return True
    return not any(str(entry.get("status") or "").lower() == "success" for entry in provider_trace)


def _legacy_generation_fallback_allowed(req: ContentGenerationRequest) -> bool:
    """Keep the retired generator reachable only to the explicit three-option caller."""

    return req.option_count == 3


async def run_content_generation(req: ContentGenerationRequest) -> ContentGenerationResponse:
    content_context: ContentGenerationContext = build_content_generation_context(
        user_id=req.user_id,
        topic=req.topic,
        context=req.context,
        content_type=req.content_type,
        category=req.category,
        tone=req.tone,
        audience=req.audience,
        source_mode=req.source_mode,
    )
    persona_chunks = content_context.persona_chunks

    if persona_chunks:
        tag_summary = {}
        for chunk in persona_chunks:
            tag = chunk.get("persona_tag", "UNKNOWN")
            tag_summary[tag] = tag_summary.get(tag, 0) + 1
        print(f"[content_gen] Retrieved persona chunks by tag: {tag_summary}", flush=True)
    example_chunks = content_context.example_chunks
    client = get_openai_client(req)
    options, option_briefs, generation_strategy, fallback_trace = _generate_staged_options(
        client=client,
        req=req,
        content_context=content_context,
        persona_chunks=persona_chunks,
        example_chunks=example_chunks,
    )
    if not options:
        if not _legacy_generation_fallback_allowed(req):
            raise RuntimeError(
                "Canonical staged generation returned no options; "
                "the legacy generator is disabled for canonical requests."
            )
        options = _generate_legacy_options(
            client=client,
            req=req,
            content_context=content_context,
            persona_chunks=persona_chunks,
            example_chunks=example_chunks,
        )
        option_briefs = plan_content_option_briefs(
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            framing_modes=content_context.framing_modes,
            option_count=max(len(options), req.option_count),
        )
        generation_strategy = "legacy_fallback"
        fallback_trace["legacy_fallback_triggered"] = True
        fallback_trace["legacy_fallback_reason"] = "staged_generation_returned_no_options"
        fallback_trace.setdefault("events", []).append(
            {
                "stage": "generation",
                "reason": "staged_generation_returned_no_options",
                "action": "used_legacy_generator",
            }
        )
    options = options[: req.option_count]
    approved_references = _extract_approved_reference_terms(
        content_context.primary_claims,
        content_context.proof_packets,
        content_context.story_beats,
    )
    voice_directives = _extract_voice_directives(persona_chunks, limit=8)
    option_framing_plan = _build_option_framing_plan(
        framing_modes=content_context.framing_modes,
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        option_count=req.option_count,
    )
    topic_anchor_preview = [
        _render_anchor_chunk(item)[:220]
        for item in content_context.topic_anchor_chunks[:4]
    ]
    core_chunk_preview = [
        _render_anchor_chunk(item)[:220]
        for item in content_context.core_chunks[:4]
    ]
    proof_anchor_preview = [
        _render_anchor_chunk(item)[:220]
        for item in content_context.proof_anchor_chunks[:4]
    ]
    taste_scores = [
        score_option_taste(
            option,
            brief=option_briefs[index] if index < len(option_briefs) else None,
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            grounding_mode=content_context.grounding_mode,
        )
        for index, option in enumerate(options[: req.option_count])
    ]
    options, option_briefs, taste_scores = _rank_options_by_taste(
        options=options[: req.option_count],
        briefs=option_briefs,
        taste_scores=taste_scores,
        topic=req.topic,
        audience=req.audience,
    )
    options, taste_scores = _repair_weak_ranked_options(
        options=options[: req.option_count],
        briefs=option_briefs,
        taste_scores=taste_scores,
        topic=req.topic,
        audience=req.audience,
        grounding_mode=content_context.grounding_mode,
        primary_claims=content_context.primary_claims,
        proof_packets=content_context.proof_packets,
        story_beats=content_context.story_beats,
        approved_reference_terms=approved_references,
    )
    options, option_briefs, taste_scores = _rank_options_by_taste(
        options=options[: req.option_count],
        briefs=option_briefs,
        taste_scores=taste_scores,
        topic=req.topic,
        audience=req.audience,
    )
    provider_trace = getattr(client, "provider_trace", [])

    return ContentGenerationResponse(
        success=True,
        options=options[: req.option_count],
        persona_context=content_context.persona_context_summary,
        examples_used=[c.get("metadata", {}).get("source", "")[:50] for c in example_chunks[:3]],
        diagnostics={
            "grounding_mode": content_context.grounding_mode,
            "generation_strategy": generation_strategy,
            "primary_claims": content_context.primary_claims,
            "raw_primary_claims": content_context.raw_primary_claims,
            "public_safe_primary_claims": content_context.public_safe_primary_claims,
            "raw_proof_packets": content_context.raw_proof_packets,
            "proof_packets": content_context.proof_packets,
            "public_safe_proof_packets": content_context.public_safe_proof_packets,
            "raw_story_beats": content_context.raw_story_beats,
            "story_beats": content_context.story_beats,
            "public_safe_story_beats": content_context.public_safe_story_beats,
            "content_release_policy": content_context.content_release_policy,
            "approved_references": approved_references,
            "voice_directives": voice_directives,
            "option_framing_plan": option_framing_plan,
            "planned_option_briefs": [
                {
                    "option_number": brief.option_number,
                    "framing_mode": brief.framing_mode,
                    "primary_claim": brief.primary_claim,
                    "proof_packet": brief.proof_packet,
                    "story_beat": brief.story_beat,
                }
                for brief in option_briefs
            ],
            "taste_scores": taste_scores,
            "topic_anchor_preview": topic_anchor_preview,
            "core_chunk_preview": core_chunk_preview,
            "proof_anchor_preview": proof_anchor_preview,
            "content_signal_source": _content_signal_source(content_context),
            "content_signal_preview": [
                str(item.get("chunk") or "")[:220]
                for item in _content_signal_chunks(content_context)[:6]
            ],
            "content_signal_count": len(_content_signal_chunks(content_context)),
            "content_signal_support": [
                {
                    "source_id": str(item.get("source_id") or ""),
                    "asset_id": str(item.get("source_file_id") or ""),
                    "signal_lane": str((item.get("metadata") or {}).get("source_lane") or ""),
                    "source_kind": str((item.get("metadata") or {}).get("source_kind") or ""),
                    "reservoir_lane": str((item.get("metadata") or {}).get("content_reservoir_lane") or ""),
                    "primary_type": str((item.get("metadata") or {}).get("claim_type") or ""),
                    "score": int((item.get("weighted_score") or item.get("similarity_score") or 0)),
                    "title": str((item.get("metadata") or {}).get("file_name") or ""),
                    "text": str(item.get("chunk") or "")[:400],
                    "source_path": str((item.get("metadata") or {}).get("source_path") or ""),
                    "source_url": str((item.get("metadata") or {}).get("source_url") or ""),
                }
                for item in _content_signal_chunks(content_context)[:8]
            ],
            "content_reservoir_preview": [
                str(item.get("chunk") or "")[:220]
                for item in _content_signal_chunks(content_context)[:6]
            ],
            "content_reservoir_count": len(_content_signal_chunks(content_context)),
            "content_reservoir_support": _serialize_content_signal_support(content_context),
            "fallback_trace": fallback_trace,
            "provider_fallback_used": _provider_trace_indicates_fallback(provider_trace),
            "llm_request_count": len(provider_trace),
            "llm_provider_trace": provider_trace,
            "source_mode": req.source_mode,
        },
    )


def _mode_priority_bonus(mode: str) -> int:
    return {
        "contrarian_reframe": 4,
        "warning": 3,
        "operator_lesson": 2,
        "drama_tension": 1,
    }.get(mode or "", 0)


def _topic_alignment_score(
    *,
    option: str,
    brief: ContentOptionBrief,
    topic: str,
    audience: str,
) -> int:
    normalized_topic = " ".join((topic or "").lower().split())
    opening = _first_content_line(option).lower()
    claim = (brief.primary_claim or "").lower()
    text = " ".join(
        part
        for part in [
            option or "",
            brief.primary_claim or "",
            _proof_packet_evidence_text(brief.proof_packet),
            brief.story_beat or "",
        ]
        if part
    ).lower()
    if not text:
        return 0
    focus_terms = _focus_terms(topic, audience)
    required_terms = _topic_required_anchor_terms(topic, audience)
    score = min(6, sum(1 for term in focus_terms if term and term in text))
    if required_terms:
        required_hits = sum(1 for term in required_terms if term in text)
        if required_hits >= 2:
            score += min(5, required_hits)
        elif audience != "general" or _is_student_support_topic(topic, audience):
            score -= 6
    if normalized_topic and (normalized_topic in opening or normalized_topic in claim):
        score += 6
    elif normalized_topic and normalized_topic in text:
        score += 3
    if normalized_topic == "ai adoption":
        adoption_core_hits = sum(
            1
            for term in (
                "adoption",
                "adopt",
                "useful",
                "usage",
            )
            if term in text
        )
        adoption_operator_hits = sum(
            1
            for term in (
                "workflow",
                "constraints",
                "constraint",
                "operator",
                "shared state",
                "handoff",
                "behavior",
            )
            if term in text
        )
        if adoption_core_hits >= 1 and adoption_operator_hits >= 1:
            score += min(3, adoption_core_hits) + min(3, adoption_operator_hits)
        else:
            score -= 8
    if normalized_topic == "agent orchestration":
        orchestration_thesis_hits = sum(
            1
            for term in (
                "agent orchestration",
                "orchestration",
                "prompting alone",
                "prompting plus",
                "operating pattern",
                "operating model",
                "operator pattern",
            )
            if term in text
        )
        orchestration_handoff_hits = sum(
            1
            for term in (
                "handoff",
                "handoffs",
                "shared state",
                "workspace state",
                "context alive",
                "routed workspace snapshot",
            )
            if term in text
        )
        opening_has_thesis = any(
            term in opening
            for term in (
                "agent orchestration",
                "orchestration",
                "prompting alone",
                "prompting plus",
                "operating pattern",
                "operating model",
                "operator pattern",
            )
        )
        if orchestration_thesis_hits >= 1 and orchestration_handoff_hits >= 1:
            score += min(4, orchestration_thesis_hits) + min(3, orchestration_handoff_hits)
        else:
            if orchestration_thesis_hits == 0:
                score -= 10
            if orchestration_handoff_hits == 0:
                score -= 5
        if not opening_has_thesis and orchestration_handoff_hits >= 1:
            score -= 6
    if any(term in normalized_topic for term in ("market", "competition", "meaner", "advantage", "pressure", "entrants")):
        market_terms = ("market", "competition", "competitive", "advantage", "pressure", "entrants", "category")
        process_terms = ("prompting", "workflow", "handoff", "handoffs", "shared state", "shared workspace state", "orchestration")
        market_hits = sum(1 for term in market_terms if term in text)
        opening_market_hits = sum(1 for term in market_terms if term in opening)
        opening_process_hits = sum(1 for term in process_terms if term in opening)
        if market_hits >= 2:
            score += 4
        else:
            score -= 6
        if opening_market_hits == 0 and opening_process_hits >= 1:
            score -= 8
    if normalized_topic == "change management" or audience in {"leadership", "leadership_management"}:
        people_hits = sum(
            1
            for term in (
                "people",
                "behavior",
                "leadership",
                "team",
                "teams",
                "coaching",
                "adoption",
                "clarity",
                "execution",
                "priority",
                "priorities",
            )
            if term in text
        )
        score += min(4, people_hits) if people_hits >= 2 else -4
    if audience == "education_admissions" and any(term in normalized_topic for term in ("faculty", "senate", "bill", "policy")):
        policy_hits = sum(
            1
            for term in (
                "faculty",
                "senate",
                "bill",
                "policy",
                "policies",
                "school",
                "schools",
                "education",
                "educators",
                "higher-ed",
            )
            if term in text
        )
        score += min(4, policy_hits) if policy_hits >= 2 else -5
    if _is_student_support_topic(topic, audience):
        student_hits = sum(
            1
            for term in (
                "student",
                "students",
                "family",
                "families",
                "parent",
                "parents",
                "admissions",
                "enrollment",
                "support",
                "learning",
                "applicant",
                "applicants",
                "prospective",
                "neurodivergent",
                "twice exceptional",
                "twice-exceptional",
            )
            if term in text
        )
        score += min(5, student_hits) if student_hits >= 2 else -8
        if any(term in text for term in ("customer trust", "technology cycle", "tech cycle", "desktop to cloud", ".com crash", "com crash")):
            score -= 8
        if any(term in opening for term in ("customer trust", "technology cycle", "tech cycle")):
            score -= 6
    return score


def _rank_options_by_taste(
    *,
    options: List[str],
    briefs: List[ContentOptionBrief],
    taste_scores: List[Dict[str, Any]],
    topic: str = "",
    audience: str = "",
) -> tuple[List[str], List[ContentOptionBrief], List[Dict[str, Any]]]:
    ranked: List[tuple[int, int, int]] = []
    for index, option in enumerate(options[:3]):
        brief = briefs[index] if index < len(briefs) else briefs[-1]
        taste = taste_scores[index] if index < len(taste_scores) else {}
        overall = int(taste.get("overall") or 0)
        alignment = _topic_alignment_score(
            option=option,
            brief=brief,
            topic=topic,
            audience=audience,
        )
        publishability = _publishability_score(
            option,
            brief,
            topic=topic,
            audience=audience,
        )
        ranked.append(
            (
                overall + _mode_priority_bonus(brief.framing_mode) + alignment + publishability,
                overall + alignment + publishability,
                index,
            )
        )
    ordered_indices = [index for _, _, index in sorted(ranked, reverse=True)]
    ordered_options = [options[index] for index in ordered_indices]
    ordered_briefs = [briefs[index] if index < len(briefs) else briefs[-1] for index in ordered_indices]
    ordered_tastes = [taste_scores[index] if index < len(taste_scores) else {} for index in ordered_indices]
    return ordered_options, ordered_briefs, ordered_tastes


def _repair_weak_ranked_options(
    *,
    options: List[str],
    briefs: List[ContentOptionBrief],
    taste_scores: List[Dict[str, Any]],
    topic: str,
    audience: str,
    grounding_mode: str,
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    approved_reference_terms: List[str],
) -> tuple[List[str], List[Dict[str, Any]]]:
    repaired_options: List[str] = []
    repaired_tastes: List[Dict[str, Any]] = []
    for index, option in enumerate(options[:3]):
        brief = briefs[index] if index < len(briefs) else briefs[-1]
        current_taste = taste_scores[index] if index < len(taste_scores) else {}
        current_overall = int(current_taste.get("overall") or 0)
        current_warnings = set(current_taste.get("warnings") or [])
        current_publishability = _publishability_score(
            option,
            brief,
            topic=topic,
            audience=audience,
        )
        weakest_slot = index == min(2, max(0, len(options[:3]) - 1))

        needs_repair = bool(
            current_overall < 60
            or "claim_not_leading" in current_warnings
            or "weak_closer" in current_warnings
            or (
                weakest_slot
                and (
                    current_overall < 78
                    or current_publishability < 14
                    or "named_reference_missing" in current_warnings
                    or "no_short_sentence" in current_warnings
                )
            )
        )
        if not needs_repair:
            repaired_options.append(option)
            repaired_tastes.append(current_taste)
            continue

        candidate = _synthesize_planned_option(brief)
        candidate = finalize_planned_options(
            options=[candidate],
            briefs=[brief],
            grounding_mode=grounding_mode,
        )[0]
        candidate = _force_claim_lead(candidate, brief)
        candidate = _drop_unapproved_reference_sentences(
            _sanitize_public_output(candidate, brief),
            brief=brief,
            approved_reference_terms=approved_reference_terms,
            audience=audience,
        )
        public_claim = _public_safe_claim_from_brief(brief)
        if public_claim and "claim_not_leading" in current_warnings:
            paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", candidate) if segment.strip()]
            if not paragraphs or paragraphs[0].lower() != public_claim.lower():
                candidate = "\n\n".join([public_claim] + paragraphs).strip()
        candidate_taste = score_option_taste(
            candidate,
            brief=brief,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
            grounding_mode=grounding_mode,
        )
        candidate_warnings = set(candidate_taste.get("warnings") or [])
        candidate_publishability = _publishability_score(
            candidate,
            brief,
            topic=topic,
            audience=audience,
        )
        candidate_total = int(candidate_taste.get("overall") or 0) + candidate_publishability
        current_total = current_overall + current_publishability
        replace_candidate = False
        if current_overall < 60:
            structural_warning_fixes = {
                warning
                for warning in {"claim_not_leading", "named_reference_missing", "proof_overloaded", "weak_closer"}
                if warning in current_warnings and warning not in candidate_warnings
            }
            replace_candidate = bool(
                int(candidate_taste.get("overall") or 0) > current_overall
                or candidate_total > current_total
                or structural_warning_fixes
            )
        else:
            required_margin = 1 if weakest_slot else 3
            replace_candidate = candidate_total >= (current_total + required_margin)
        if replace_candidate:
            repaired_options.append(candidate)
            repaired_tastes.append(candidate_taste)
        else:
            repaired_options.append(option)
            repaired_tastes.append(current_taste)
    return repaired_options, repaired_tastes


@router.post("/codex-jobs", response_model=LocalCodexJobCreateResponse, deprecated=True)
async def create_local_codex_job(req: LocalCodexJobCreateRequest):
    try:
        job = queue_local_codex_job(req)
        status = str(job.get("status") or "pending")
        readiness = job.get("evidence_readiness") if isinstance(job.get("evidence_readiness"), dict) else {}
        if status == "clarification_required":
            return LocalCodexJobCreateResponse(
                success=True,
                job_id=None,
                status=status,
                message="One concrete detail is still needed before FEEZIE can draft.",
                clarification_key=str(readiness.get("clarification_key") or "") or None,
                clarification_question=str(readiness.get("clarification_question") or "") or None,
                evidence_readiness=readiness,
            )
        if status == "blocked":
            return LocalCodexJobCreateResponse(
                success=False,
                job_id=None,
                status=status,
                message="This idea is not admitted to drafting under the current qualification and evidence rules.",
                evidence_readiness=readiness,
            )
        return LocalCodexJobCreateResponse(
            success=True,
            job_id=str(job.get("id") or ""),
            status=status,
            message="Queued for the local generation worker.",
            evidence_readiness={
                "schema_version": "feezie_evidence_readiness/v1",
                "status": "ready",
                "ready": True,
                "missing_fields": [],
                "present_fields": list(EVIDENCE_KEYS),
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        print(f"Local Codex job create error: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Unable to queue local Codex job: {str(exc)}") from exc


@router.post("/context-audit", response_model=ContentContextAuditResponse)
async def audit_content_context(req: ContentGenerationRequest):
    try:
        content_context = build_content_generation_context(
            user_id=req.user_id,
            topic=req.topic,
            context=req.context,
            content_type=req.content_type,
            category=req.category,
            tone=req.tone,
            audience=req.audience,
            source_mode=req.source_mode,
            include_audit=True,
            allow_snapshot_rebuild=False,
        )
        return ContentContextAuditResponse(
            success=True,
            persona_context=content_context.persona_context_summary,
            grounding_mode=content_context.grounding_mode,
            grounding_reason=content_context.grounding_reason,
            framing_modes=content_context.framing_modes,
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            audit=content_context.audit,
        )
    except Exception as exc:
        print(f"Content context audit error: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Unable to audit content context: {str(exc)}") from exc


@router.post("/codex-jobs/claim-next", response_model=LocalCodexJobClaimResponse)
async def claim_local_codex_job(
    req: LocalCodexJobClaimRequest,
    x_local_codex_token: str | None = Header(default=None, alias="X-Local-Codex-Token"),
):
    _require_local_codex_token(x_local_codex_token)
    try:
        worker_receipt = _codex_worker_receipt(req.worker_id)
        job = claim_next_codex_job(
            worker_id=worker_receipt,
            workspace_slug=req.workspace_slug,
        )
        if not job:
            # A job claimed before this privacy boundary may still carry the
            # former raw worker id. Resume it once, then completion rewrites the
            # lease to the opaque receipt.
            job = claim_next_codex_job(
                worker_id=req.worker_id,
                workspace_slug=req.workspace_slug,
            )
        if not job:
            return LocalCodexJobClaimResponse(success=True, job_available=False)
        return LocalCodexJobClaimResponse(
            success=True,
            job_available=True,
            job_id=str(job.get("id") or ""),
            status=str(job.get("status") or "running"),
            workspace_slug=str(job.get("workspace_slug") or ""),
            context_packet=job.get("context_packet") if isinstance(job.get("context_packet"), dict) else None,
            request_payload=job.get("request_payload") if isinstance(job.get("request_payload"), dict) else None,
        )
    except Exception as exc:
        print(f"Local Codex job claim error: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Unable to claim local Codex job: {str(exc)}") from exc


@router.get("/codex-jobs/exception-receipts")
async def get_local_codex_job_exception_receipts():
    """Return bounded generation exceptions without draft text or prompts."""

    try:
        jobs = list_codex_jobs(limit=24)
        return build_feezie_exception_receipts(generation_jobs=jobs)
    except Exception as exc:
        print(f"Local Codex exception receipt error: {type(exc).__name__}", flush=True)
        raise HTTPException(status_code=500, detail="Unable to build content-generation exception receipts.") from exc


@router.get("/codex-jobs/{job_id}", response_model=LocalCodexJobStatusResponse)
async def get_local_codex_job(job_id: str):
    job = get_codex_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local Codex job not found")
    return _build_local_codex_status_response(job)


def _require_v2_selected_quality_result(
    *,
    quality_gate: Dict[str, Any],
    selected_option_index: int,
    expected_option_count: int,
) -> Dict[str, Any]:
    """Verify the shared v2 gate and one selected result without requiring a clean sibling."""

    failure = "Selected option did not pass its deterministic quality receipt; regenerate before owner review."
    if (
        str(quality_gate.get("schema_version") or "")
        != FEEZIE_DETERMINISTIC_QUALITY_GATE_VERSION
        or expected_option_count < 1
        or selected_option_index < 1
        or selected_option_index > expected_option_count
    ):
        raise ValueError(failure)

    shared = (
        quality_gate.get("shared_constraints")
        if isinstance(quality_gate.get("shared_constraints"), dict)
        else {}
    )
    shared_failures = shared.get("failed_reasons")
    if (
        shared.get("passed") is not True
        or shared_failures != []
        or shared.get("required_option_count") != expected_option_count
        or shared.get("evaluated_option_count") != expected_option_count
        or quality_gate.get("required_option_count") != expected_option_count
        or quality_gate.get("evaluated_option_count") != expected_option_count
    ):
        raise ValueError(failure)

    raw_results = quality_gate.get("option_results")
    if not isinstance(raw_results, list) or len(raw_results) != expected_option_count:
        raise ValueError(failure)
    option_results: Dict[int, Dict[str, Any]] = {}
    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            raise ValueError(failure)
        result_index = raw_result.get("option_index")
        score = raw_result.get("score")
        threshold = raw_result.get("threshold")
        result_failures = raw_result.get("failed_reasons")
        result_passed = raw_result.get("passed")
        if (
            isinstance(result_index, bool)
            or not isinstance(result_index, int)
            or result_index < 1
            or result_index > expected_option_count
            or result_index in option_results
            or isinstance(score, bool)
            or not isinstance(score, int)
            or score < 0
            or score > 100
            or isinstance(threshold, bool)
            or not isinstance(threshold, int)
            or threshold < 1
            or threshold > 100
            or not isinstance(result_failures, list)
            or any(not isinstance(reason, str) or not reason.strip() for reason in result_failures)
            or len(set(result_failures)) != len(result_failures)
            or not isinstance(result_passed, bool)
            or result_passed != (score >= threshold and not result_failures)
        ):
            raise ValueError(failure)
        option_results[result_index] = raw_result

    if set(option_results) != set(range(1, expected_option_count + 1)):
        raise ValueError(failure)
    computed_batch_passed = all(result.get("passed") is True for result in option_results.values())
    computed_selection_passed = any(result.get("passed") is True for result in option_results.values())
    if (
        not isinstance(quality_gate.get("passed"), bool)
        or quality_gate.get("passed") != computed_batch_passed
        or not isinstance(quality_gate.get("selection_admission_passed"), bool)
        or quality_gate.get("selection_admission_passed") != computed_selection_passed
    ):
        raise ValueError(failure)

    selected = option_results.get(selected_option_index)
    if not isinstance(selected, dict) or selected.get("passed") is not True:
        raise ValueError(failure)
    return selected


def _revalidate_feezie_persisted_completion_receipts(
    *,
    job_id: str,
    result_payload: Dict[str, Any],
    context_packet: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Recheck projected Railway state before an exact-copy owner handoff."""

    options = [
        str(option).strip()
        for option in (result_payload.get("options") or [])
        if isinstance(option, str) and str(option).strip()
    ]
    if len(options) != FEEZIE_CODEX_DRAFT_OPTION_COUNT:
        raise ValueError("The stored FEEZIE result no longer contains its exact final draft pair.")
    diagnostics = (
        result_payload.get("diagnostics")
        if isinstance(result_payload.get("diagnostics"), dict)
        else {}
    )
    job = {"id": job_id, "context_packet": context_packet}
    revision_contract = _feezie_revision_contract(job)
    quality_gate = _canonical_feezie_quality_gate(
        context_packet=context_packet,
        options=options,
        submitted_quality_gate=diagnostics.get("quality_gate"),
        require_contamination=bool(revision_contract),
        compare_full_receipt=False,
    )
    critic_review = _closed_feezie_critic_receipt(diagnostics.get("critic_review"))
    try:
        readiness = _build_feezie_editorial_readiness(
            critic_review=critic_review,
            deterministic_quality_gate=quality_gate,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("The stored FEEZIE critic receipt is no longer valid.") from exc
    projected_readiness = _project_feezie_editorial_readiness(readiness)
    if diagnostics.get("editorial_readiness") != projected_readiness:
        raise ValueError(
            "The stored FEEZIE editorial-readiness receipt no longer matches the exact final drafts."
        )

    # Reuse the full completion validator for critic byte/scope binding and the
    # no-copy revision topology after restoring the server-only full receipts.
    candidate = json.loads(json.dumps(result_payload, ensure_ascii=True))
    candidate_diagnostics = candidate.setdefault("diagnostics", {})
    candidate_diagnostics["quality_gate"] = quality_gate
    candidate_diagnostics["editorial_readiness"] = readiness
    _validate_feezie_codex_completion_result(job=job, result_payload=candidate)
    return _project_feezie_quality_gate(quality_gate), projected_readiness


def _require_editorially_ready_option(
    *,
    result_payload: Dict[str, Any],
    context_packet: Dict[str, Any],
    option_index: int,
    job_id: str | None = None,
) -> Dict[str, Any]:
    diagnostics = result_payload.get("diagnostics") if isinstance(result_payload.get("diagnostics"), dict) else {}
    readiness = diagnostics.get("editorial_readiness") if isinstance(diagnostics.get("editorial_readiness"), dict) else {}
    quality_gate = diagnostics.get("quality_gate") if isinstance(diagnostics.get("quality_gate"), dict) else {}
    quality_gate_schema = str(quality_gate.get("schema_version") or "").strip()
    is_v2_quality_gate = quality_gate_schema == FEEZIE_DETERMINISTIC_QUALITY_GATE_VERSION
    contract = context_packet.get("draft_contract") if isinstance(context_packet.get("draft_contract"), dict) else {}
    expected_option_count = int(
        contract.get("required_option_count")
        or len(result_payload.get("options") or [])
        or FEEZIE_CODEX_DRAFT_OPTION_COUNT
    )
    revision_contract = _feezie_revision_contract({"context_packet": context_packet})
    if revision_contract and job_id:
        quality_gate, readiness = _revalidate_feezie_persisted_completion_receipts(
            job_id=job_id,
            result_payload=result_payload,
            context_packet=context_packet,
        )
    if revision_contract:
        final_options = [
            str(option).strip()
            for option in (result_payload.get("options") or [])
            if isinstance(option, str) and str(option).strip()
        ]
        critic_review = (
            diagnostics.get("critic_review")
            if isinstance(diagnostics.get("critic_review"), dict)
            else {}
        )
        _validate_feezie_revision_execution_receipt(
            receipt=diagnostics.get("revision_execution"),
            final_options=final_options,
            critic_review=critic_review,
            readiness=readiness,
        )
    if quality_gate_schema and not is_v2_quality_gate:
        raise ValueError(
            "Selected option did not pass its deterministic quality receipt; regenerate before owner review."
        )
    if is_v2_quality_gate:
        readiness_admitted = str(readiness.get("critic_status") or "").strip().lower() == "completed"
    else:
        # Schema-less receipts retain their original all-options-or-none posture.
        readiness_admitted = (
            quality_gate.get("passed") is True
            and readiness.get("ready") is True
            and str(readiness.get("status") or "").strip().lower() == "ready"
            and str(readiness.get("critic_status") or "").strip().lower() == "completed"
            and readiness.get("deterministic_quality_gate_passed") is True
            and readiness.get("blocking_reasons") in (None, [])
        )
    if not readiness_admitted:
        status = str(readiness.get("status") or "critic_missing")
        reasons = ", ".join(str(item) for item in (readiness.get("blocking_reasons") or []) if str(item).strip())
        detail = f" ({reasons})" if reasons else ""
        raise ValueError(f"Option is not editorially ready: {status}{detail}.")

    reviews = readiness.get("option_reviews") if isinstance(readiness.get("option_reviews"), list) else []
    if str(contract.get("schema_version") or "") == FEEZIE_CODEX_DRAFT_CONTRACT_VERSION:
        review_indices = [
            item.get("option_index")
            for item in reviews
            if isinstance(item, dict)
            and isinstance(item.get("option_index"), int)
            and not isinstance(item.get("option_index"), bool)
        ]
        if (
            len(result_payload.get("options") or []) != expected_option_count
            or len(reviews) != expected_option_count
            or len(review_indices) != expected_option_count
            or set(review_indices) != set(range(1, expected_option_count + 1))
        ):
            raise ValueError("The FEEZIE two-draft critic contract is incomplete; regenerate before owner review.")
    option_review = next(
        (
            item
            for item in reviews
            if isinstance(item, dict) and int(item.get("option_index") or 0) == option_index + 1
        ),
        None,
    )
    if not isinstance(option_review, dict) or option_review.get("editorially_ready") is not True:
        issues = ", ".join(
            str(item)
            for item in ((option_review or {}).get("issues") or [])
            if str(item).strip()
        )
        detail = f" ({issues})" if issues else ""
        raise ValueError(
            f"Selected option is not editorially ready and still needs editorial revision{detail}."
        )
    if is_v2_quality_gate:
        _require_v2_selected_quality_result(
            quality_gate=quality_gate,
            selected_option_index=option_index + 1,
            expected_option_count=expected_option_count,
        )
        if (
            option_review.get("deterministic_quality_passed") is not True
            or option_review.get("deterministic_blocked") is not False
        ):
            raise ValueError(
                "Selected option did not pass its deterministic quality receipt; regenerate before owner review."
            )
    if str(contract.get("schema_version") or "") == FEEZIE_CODEX_DRAFT_CONTRACT_VERSION:
        hook_variants = [
            str(hook).strip()
            for hook in (option_review.get("hook_variants") or [])
            if str(hook).strip()
        ]
        if len(hook_variants) != FEEZIE_CODEX_HOOK_VARIANT_COUNT or len({hook.lower() for hook in hook_variants}) != len(hook_variants):
            raise ValueError("The selected draft lacks its exact eight-hook independent critic receipt.")
        diagnostics = result_payload.get("diagnostics") if isinstance(result_payload.get("diagnostics"), dict) else {}
        distinctness = diagnostics.get("draft_distinctness") if isinstance(diagnostics.get("draft_distinctness"), dict) else {}
        critic_review = diagnostics.get("critic_review") if isinstance(diagnostics.get("critic_review"), dict) else {}
        semantic_distinctness = (
            critic_review.get("draft_distinctness")
            if isinstance(critic_review.get("draft_distinctness"), dict)
            else {}
        )
        if distinctness.get("passed") is not True or semantic_distinctness.get("passed") is not True:
            raise ValueError("The two drafts were not proven meaningfully different; regenerate before owner review.")

    classification = (
        context_packet.get("candidate_classification")
        if isinstance(context_packet.get("candidate_classification"), dict)
        else {}
    )
    if str(classification.get("employer_safety") or "").strip().lower() == "blocked":
        raise ValueError("Selected option is blocked by the employer-safety classification.")

    generated_contract = (
        context_packet.get("strategy_contract")
        if isinstance(context_packet.get("strategy_contract"), dict)
        else {}
    )
    generated_hash = str(generated_contract.get("contract_hash") or "").strip()
    current_hash = str(load_feezie_strategy_contract().get("contract_hash") or "").strip()
    if not generated_hash or generated_hash != current_hash:
        raise ValueError("The FEEZIE strategy contract changed after generation; regenerate before owner review.")
    return option_review


@router.post(
    "/codex-jobs/{job_id}/send-to-review",
    response_model=LocalCodexJobSendToReviewResponse,
)
async def send_local_codex_option_to_review(
    job_id: str,
    req: LocalCodexJobSendToReviewRequest,
    legacy_compatibility: bool = False,
):
    if not legacy_compatibility:
        raise HTTPException(
            status_code=409,
            detail=(
                "The historical two-option owner-review handoff is disabled by default; "
                "use the canonical integrated-content lifecycle or explicitly enable "
                "the rollback-only compatibility path."
            ),
        )
    job = get_codex_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local Codex job not found")
    if str(job.get("status") or "").strip().lower() != "completed":
        raise HTTPException(status_code=409, detail="Only a completed Codex job can be sent to owner review")
    result_payload = job.get("result_payload") if isinstance(job.get("result_payload"), dict) else {}
    options = result_payload.get("options") if isinstance(result_payload.get("options"), list) else []
    if req.option_index >= len(options):
        raise HTTPException(
            status_code=400,
            detail=f"option_index {req.option_index} is out of range for {len(options)} completed options",
        )
    selected_option = options[req.option_index]
    if not isinstance(selected_option, str) or not selected_option.strip():
        raise HTTPException(status_code=409, detail=f"Completed option {req.option_index} is empty or invalid")
    request_payload = job.get("request_payload") if isinstance(job.get("request_payload"), dict) else {}
    context_packet = job.get("context_packet") if isinstance(job.get("context_packet"), dict) else {}
    try:
        _require_editorially_ready_option(
            result_payload=result_payload,
            context_packet=context_packet,
            option_index=req.option_index,
            job_id=job_id,
        )
        review = ensure_generated_owner_review_item(
            legacy_compatibility=True,
            job_id=job_id,
            option_index=req.option_index,
            option_text=selected_option.strip(),
            request_payload=request_payload,
            context_packet=context_packet,
            generation_diagnostics=(
                result_payload.get("diagnostics")
                if isinstance(result_payload.get("diagnostics"), dict)
                else {}
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        print(f"Local Codex send-to-review error: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Unable to create FEEZIE owner-review item: {str(exc)}") from exc

    item = review.get("item") if isinstance(review.get("item"), dict) else {}
    approval_status = str(item.get("approval_status") or "")
    publish_posture = str(item.get("publish_posture") or "")
    owner_review_required = approval_status == "owner_review_required" and publish_posture == "owner_review_required"
    if not owner_review_required:
        raise HTTPException(status_code=500, detail="Generated option did not enter the required owner-review state")
    duplicate = bool(review.get("duplicate"))
    return LocalCodexJobSendToReviewResponse(
        success=True,
        job_id=job_id,
        option_index=req.option_index,
        queue_id=str(item.get("queue_id") or review.get("queue_id") or ""),
        card_id=str(review.get("card_id") or ""),
        duplicate=duplicate,
        status=str(item.get("status") or "owner_review_draft"),
        approval_status=approval_status,
        publish_posture=publish_posture,
        owner_review_required=True,
        message=str(review.get("message") or ("Owner-review item already exists." if duplicate else "Sent to FEEZIE owner review.")),
        owner_review_item=item,
    )


@router.get("/codex-jobs/{job_id}/artifacts", response_model=LocalCodexJobArtifactsResponse)
async def get_local_codex_job_artifacts(job_id: str):
    try:
        artifacts = list_job_artifacts(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = get_codex_job(job_id) or {}
    closed_feezie_job = bool(_feezie_draft_contract(job))
    rendered: list[LocalCodexJobArtifactResponse] = []
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "")
        artifact_kind = str(artifact.get("kind") or "")
        preview = None
        if closed_feezie_job:
            preview = _safe_feezie_artifact_preview(job=job, artifact=artifact)
            if preview is None:
                continue
        elif artifact_id:
            try:
                content = read_job_artifact_content(job_id=job_id, artifact_id=artifact_id)
            except ValueError:
                content = None
            if content:
                preview = content[:2000]
        rendered.append(
            LocalCodexJobArtifactResponse(
                artifact_id=artifact_id,
                kind=artifact_kind,
                label=str(artifact.get("label") or ""),
                filename=str(artifact.get("filename") or ""),
                mime_type=str(artifact.get("mime_type") or "text/plain"),
                size_bytes=int(artifact.get("size_bytes") or 0) or None,
                created_at=str(artifact.get("created_at") or ""),
                preview=preview,
            )
        )
    return LocalCodexJobArtifactsResponse(success=True, job_id=job_id, artifacts=rendered)


@router.post("/codex-jobs/{job_id}/complete", response_model=LocalCodexJobStatusResponse)
async def complete_local_codex_job(
    job_id: str,
    req: LocalCodexJobCompleteRequest,
    x_local_codex_token: str | None = Header(default=None, alias="X-Local-Codex-Token"),
):
    _require_local_codex_token(x_local_codex_token)
    job = get_codex_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local Codex job not found")
    result_payload = req.result_payload if isinstance(req.result_payload, dict) else None
    if result_payload is None:
        if _feezie_draft_contract(job):
            raise HTTPException(
                status_code=400,
                detail="FEEZIE completion requires the full independent-critic result payload.",
            )
        trimmed_options = [option.strip() for option in req.options if isinstance(option, str) and option.strip()][:3]
        if len(trimmed_options) != 3:
            raise HTTPException(status_code=400, detail="Codex completion must include exactly 3 non-empty options")
        result_payload = _build_local_codex_result_payload(
            job=job,
            options=trimmed_options,
            model=req.model,
            raw_output=req.raw_output,
            command_stdout=req.command_stdout,
            command_stderr=req.command_stderr,
        )
    is_feezie_job = bool(_feezie_draft_contract(job))
    try:
        result_payload = _validate_feezie_codex_completion_result(job=job, result_payload=result_payload)
        if is_feezie_job:
            result_payload = _project_feezie_completion_result(
                job=job,
                result_payload=result_payload,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        if is_feezie_job:
            initial_critic_receipt = _feezie_initial_critic_receipt_from_artifacts(
                requested_artifacts=req.artifacts,
                result_payload=result_payload,
                required=bool(_feezie_revision_contract(job)),
            )
            artifact_items = _feezie_completion_artifacts(
                result_payload=result_payload,
                initial_critic_receipt=initial_critic_receipt,
            )
        else:
            artifact_items = req.artifacts
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    completed = complete_codex_job(
        job_id=job_id,
        worker_id=_codex_worker_receipt(req.worker_id),
        result_payload=result_payload,
    )
    artifacts = _persist_job_artifacts(job_id, artifact_items)
    if artifacts:
        completed = append_job_artifacts(job_id=job_id, artifacts=artifacts)
    return _build_local_codex_status_response(completed)


@router.post("/codex-jobs/{job_id}/fail", response_model=LocalCodexJobStatusResponse)
async def fail_local_codex_job(
    job_id: str,
    req: LocalCodexJobFailRequest,
    x_local_codex_token: str | None = Header(default=None, alias="X-Local-Codex-Token"),
):
    _require_local_codex_token(x_local_codex_token)
    job = get_codex_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local Codex job not found")
    closed_feezie_job = bool(_feezie_draft_contract(job))
    try:
        failed = fail_codex_job(
            job_id=job_id,
            worker_id=_codex_worker_receipt(req.worker_id),
            error_message=(
                "Local generation failed."
                if closed_feezie_job
                else _trim_job_error(req.error_message) or "Local generation failed."
            ),
        )
        return _build_local_codex_status_response(failed)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/codex-jobs/{job_id}/cancel", response_model=LocalCodexJobStatusResponse)
async def cancel_local_codex_job(job_id: str):
    try:
        canceled = cancel_codex_job(job_id)
        return _build_local_codex_status_response(canceled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate", response_model=ContentGenerationResponse)
async def generate_content(
    req: ContentGenerationRequest,
    x_content_generation_direct_override: str | None = Header(default=None, alias="X-Content-Generation-Direct-Override"),
):
    """
    Generate AI-powered content using persona and examples from knowledge base.
    """
    _require_direct_content_generation_enabled(x_content_generation_direct_override)
    try:
        return await run_content_generation(req)
    except Exception as e:
        print(f"Content generation error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")


@router.post("/promote-fragment", response_model=GeneratedFragmentPromotionResponse)
async def promote_content_fragment(req: GeneratedFragmentPromotionRequest):
    try:
        return GeneratedFragmentPromotionResponse(
            **promote_generated_fragment(
                user_id=req.user_id,
                fragment_text=req.fragment_text,
                option_text=req.option_text,
                option_index=req.option_index,
                topic=req.topic,
                audience=req.audience,
                category=req.category,
                content_type=req.content_type,
                source_mode=req.source_mode,
                support_items=[item.model_dump(exclude_none=True) for item in req.support_items],
                option_brief=req.option_brief,
                published=req.published,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        print(f"Content fragment promotion error: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Content fragment promotion failed: {str(exc)}") from exc


@router.post("/undo-promoted-fragment", response_model=UndoGeneratedFragmentPromotionResponse)
async def undo_promoted_content_fragment(req: UndoGeneratedFragmentPromotionRequest):
    try:
        return UndoGeneratedFragmentPromotionResponse(**undo_generated_fragment_promotion(delta_id=req.delta_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        print(f"Content fragment undo error: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Content fragment undo failed: {str(exc)}") from exc


@router.post("/quick-generate")
async def quick_generate(
    topic: str,
    content_type: str = "linkedin_post",
    category: str = "value",
    user_id: str = "default",
    x_content_generation_direct_override: str | None = Header(default=None, alias="X-Content-Generation-Direct-Override"),
):
    """Quick endpoint for simple content generation."""
    _require_direct_content_generation_enabled(x_content_generation_direct_override)
    req = ContentGenerationRequest(
        user_id=user_id,
        topic=topic,
        content_type=content_type,
        category=category,
    )
    return await run_content_generation(req)
