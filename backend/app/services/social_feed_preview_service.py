from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.social_signal_extraction import social_signal_extraction_service
from app.services.social_signal_utils import (
    LENS_LABELS,
    build_variants,
    first_meaningful_line,
    normalize_manual_signal,
    normalize_lane,
)


class SocialFeedPreviewService:
    """Thin orchestration layer for manual social-signal previews."""

    def extract_preview_payload(self, html: str) -> dict[str, str]:
        return social_signal_extraction_service.extract_preview_payload(html)

    def fetch_url_preview(self, url: str) -> dict[str, str]:
        return social_signal_extraction_service.fetch_url_preview(url)

    def generate_preview(self, *, url: str | None, text: str | None, title: str | None, priority_lane: str) -> dict[str, Any]:
        extracted_title = ""
        author = "manual preview"
        raw_text = text or ""
        extraction_method = "manual_text"

        if url:
            extracted = self.fetch_url_preview(url)
            raw_text = extracted.get("text", "")
            extracted_title = extracted.get("title", "")
            author = extracted.get("author") or author
            extraction_method = "url_preview"

        raw_text = raw_text.strip()
        if not raw_text:
            raise ValueError("No extractable text found.")

        normalized_lane = normalize_lane(priority_lane)
        signal = normalize_manual_signal(
            raw_text=raw_text,
            title=title or extracted_title or first_meaningful_line(raw_text)[:120],
            url=url,
            author=author,
            priority_lane=normalized_lane,
            source_type="post",
            extraction_method=extraction_method,
        )
        variants = build_variants(signal)
        default_variant = variants.get(normalized_lane) or variants["current-role"]
        belief_assessment = {
            "stance": default_variant["stance"],
            "agreement_level": default_variant["agreement_level"],
            "belief_used": default_variant["belief_used"],
            "belief_summary": default_variant["belief_summary"],
            "experience_anchor": default_variant["experience_anchor"],
            "experience_summary": default_variant["experience_summary"],
            "role_safety": default_variant["role_safety"],
        }
        technique_assessment = {
            "techniques": default_variant["techniques"],
            "emotional_profile": default_variant["emotional_profile"],
            "reason": default_variant["technique_reason"],
        }
        expression_assessment = default_variant["expression_assessment"]

        return {
            "id": f"manual__{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "platform": signal["source_channel"],
            "source_lane": signal["source_lane"],
            "capture_method": signal["capture_method"],
            "title": signal["title"],
            "author": signal["author"],
            "source_url": signal["source_url"],
            "why_it_matters": (
                f"Preview generated from your {'link' if url else 'pasted text'} "
                f"in the {LENS_LABELS.get(normalized_lane, 'active')} lane. Use the lane buttons to shift the framing."
            ),
            "comment_draft": default_variant["comment"],
            "repost_draft": default_variant["repost"],
            "lens_variants": variants,
            "standout_lines": signal["standout_lines"],
            "lenses": [normalized_lane],
            "summary": signal["summary"],
            "core_claim": signal["core_claim"],
            "supporting_claims": signal["supporting_claims"],
            "topic_tags": signal["topic_tags"],
            "trust_notes": signal["trust_notes"],
            "source_metadata": signal["source_metadata"],
            "belief_assessment": belief_assessment,
            "technique_assessment": technique_assessment,
            "expression_assessment": expression_assessment,
            "evaluation": default_variant["evaluation"],
            "ranking": {"total": 999.0},
        }


social_feed_preview_service = SocialFeedPreviewService()
