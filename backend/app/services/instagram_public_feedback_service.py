from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.services.workspace_snapshot_store import upsert_snapshot


INSTAGRAM_WEB_APP_ID = "936619743392459"
INSTAGRAM_WEB_PROFILE_URL = "https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
SNAPSHOT_TYPE = "instagram_public_feedback"
ANALYTICS_SUBDIR = Path("analytics") / "instagram_public"
SUMMARY_FILENAME = "instagram_public_feedback_summary.json"
SUMMARY_MARKDOWN_FILENAME = "instagram_public_feedback_summary.md"
FUSION_PILLARS = (
    "Family Clarity",
    "Partner Credibility",
    "Behind-the-Scenes",
    "Leadership POV",
)
PILLAR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Family Clarity": (
        "family",
        "families",
        "parent",
        "parents",
        "learner",
        "learners",
        "student",
        "students",
        "homework cafe",
        "1:1",
        "one-to-one",
        "personalized",
        "flexible",
        "scheduling",
        "learning experience",
        "social emotional",
    ),
    "Partner Credibility": (
        "partner",
        "partners",
        "referral",
        "referrals",
        "counselor",
        "counselors",
        "therapist",
        "therapists",
        "professional",
        "community partner",
        "workshop",
        "open house",
        "invite",
        "join us",
    ),
    "Behind-the-Scenes": (
        "campus",
        "classroom",
        "visited",
        "celebrated",
        "this week",
        "had a blast",
        "field trip",
        "homework cafe",
        "students practiced",
        "we celebrated",
        "we visited",
    ),
    "Leadership POV": (
        "we're proud",
        "we are proud",
        "our model",
        "our approach",
        "we believe",
        "mission",
        "why",
        "what makes us",
        "here’s what makes",
        "our team",
        "our faculty",
    ),
}
AUDIENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "families": (
        "family",
        "families",
        "parent",
        "parents",
        "caregiver",
        "caregivers",
        "student",
        "students",
        "learner",
        "learners",
        "homework cafe",
    ),
    "partners": (
        "partner",
        "partners",
        "referral",
        "referrals",
        "counselor",
        "counselors",
        "therapist",
        "therapists",
        "professional",
        "community partner",
    ),
    "leadership": (
        "leadership",
        "leader",
        "leaders",
        "director",
        "faculty",
        "staff",
        "our team",
        "our model",
        "our approach",
    ),
}
EVENT_KEYWORDS = ("event", "workshop", "open house", "join us", "yoga", "visit", "visiting", "celebrated")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _caption_from_node(node: dict[str, Any]) -> str:
    edges = (((node.get("edge_media_to_caption") or {}).get("edges")) or [])
    if not edges:
        return ""
    first = edges[0] if isinstance(edges[0], dict) else {}
    caption_node = first.get("node") if isinstance(first.get("node"), dict) else {}
    return str(caption_node.get("text") or "").strip()


def _summarize_caption(text: str, *, max_len: int = 160) -> str:
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1].rstrip() + "…"


def _instagram_permalink(shortcode: str) -> str:
    return f"https://www.instagram.com/p/{shortcode}/"


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _keyword_score(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _classify_pillar(caption: str) -> str:
    normalized = _normalize_text(caption)
    scores = {pillar: _keyword_score(normalized, keywords) for pillar, keywords in PILLAR_KEYWORDS.items()}
    best_pillar = max(scores, key=scores.get) if scores else "Family Clarity"
    if scores.get(best_pillar, 0) > 0:
        return best_pillar
    if any(token in normalized for token in ("partner", "referral", "counselor", "therapist")):
        return "Partner Credibility"
    if any(token in normalized for token in ("proud", "approach", "model", "mission")):
        return "Leadership POV"
    if any(token in normalized for token in ("campus", "classroom", "visited", "celebrated", "week")):
        return "Behind-the-Scenes"
    return "Family Clarity"


def _classify_audience(caption: str, pillar: str) -> str:
    normalized = _normalize_text(caption)
    scores = {audience: _keyword_score(normalized, keywords) for audience, keywords in AUDIENCE_KEYWORDS.items()}
    best_audience = max(scores, key=scores.get) if scores else "families"
    if scores.get(best_audience, 0) > 0:
        return best_audience
    if pillar == "Partner Credibility":
        return "partners"
    if pillar == "Leadership POV":
        return "leadership"
    return "families"


def _is_event_signal(caption: str) -> bool:
    normalized = _normalize_text(caption)
    return any(keyword in normalized for keyword in EVENT_KEYWORDS)


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _build_breakdown(posts: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    breakdown: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        label = str(post.get(key) or "unknown").strip() or "unknown"
        groups.setdefault(label, []).append(post)
    for label, group in groups.items():
        engagements = [int(item.get("visible_engagement") or 0) for item in group]
        top_post = max(group, key=lambda item: int(item.get("visible_engagement") or 0), default={})
        breakdown.append(
            {
                "label": label,
                "post_count": len(group),
                "average_visible_engagement": round(mean(engagements), 2) if engagements else 0.0,
                "total_visible_engagement": sum(engagements),
                "top_post_shortcode": str(top_post.get("shortcode") or "").strip(),
                "top_post_url": str(top_post.get("url") or "").strip(),
                "top_post_visible_engagement": int(top_post.get("visible_engagement") or 0),
            }
        )
    breakdown.sort(key=lambda item: (-_safe_float(item.get("average_visible_engagement")), -int(item.get("post_count") or 0), item.get("label") or ""))
    return breakdown


def _posts_in_window(posts: list[dict[str, Any]], *, days: int, now: datetime) -> int:
    count = 0
    for post in posts:
        taken_at = str(post.get("taken_at") or "").strip()
        if not taken_at:
            continue
        try:
            taken_dt = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - taken_dt).days <= days:
            count += 1
    return count


def _latest_post_age_days(posts: list[dict[str, Any]], *, now: datetime) -> int | None:
    latest: datetime | None = None
    for post in posts:
        taken_at = str(post.get("taken_at") or "").strip()
        if not taken_at:
            continue
        try:
            taken_dt = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if latest is None or taken_dt > latest:
            latest = taken_dt
    if latest is None:
        return None
    return max((now - latest).days, 0)


def _opportunity_signals(
    posts: list[dict[str, Any]],
    pillar_breakdown: list[dict[str, Any]],
    audience_breakdown: list[dict[str, Any]],
    *,
    posts_last_7d: int,
) -> tuple[list[str], list[str], list[str]]:
    opportunities: list[str] = []
    next_focus: list[str] = []
    signal_lines: list[str] = []

    if pillar_breakdown:
        lead_pillar = pillar_breakdown[0]
        opportunities.append(
            f"{lead_pillar['label']} is the strongest visible-response pillar in the recent sample with average visible engagement {lead_pillar['average_visible_engagement']}."
        )
        next_focus.append(
            f"Keep one near-term post inside `{lead_pillar['label']}` while translating the same theme into a second audience-specific angle."
        )
        signal_lines.append(
            f"Visible response is currently led by `{lead_pillar['label']}`."
        )

    seen_pillars = {str(item.get("label") or "") for item in pillar_breakdown}
    for pillar in FUSION_PILLARS:
        if pillar not in seen_pillars:
            opportunities.append(f"`{pillar}` has no recent visible post in the public sample, which leaves that narrative lane underrepresented.")
            next_focus.append(f"Ship a `{pillar}` post in the next cycle so the weekly mix stays balanced.")

    audience_labels = {str(item.get("label") or ""): item for item in audience_breakdown}
    family_count = int((audience_labels.get("families") or {}).get("post_count") or 0)
    partner_count = int((audience_labels.get("partners") or {}).get("post_count") or 0)
    if partner_count == 0:
        opportunities.append("No clearly partner-facing post appears in the recent public sample.")
        next_focus.append("Publish a partner-facing credibility post next so referral trust does not disappear from the lane.")
    elif family_count == 0:
        opportunities.append("No clearly family-facing post appears in the recent public sample.")
        next_focus.append("Publish a family-clarity post next so the primary audience stays visible.")

    if posts_last_7d < 4:
        opportunities.append(f"Recent cadence is below the 4-post weekly target with only {posts_last_7d} sampled post(s) in the last 7 days.")
        next_focus.append("Use the next weekly cycle to reach the 4-post cadence target before expanding narrative experiments.")
        signal_lines.append("Weekly cadence is currently below the 4-post target.")
    else:
        signal_lines.append("Weekly cadence is on track against the 4-post target.")

    event_posts = [post for post in posts if post.get("event_signal")]
    if event_posts:
        opportunities.append(f"Recent public posts include {len(event_posts)} event-related signal(s) that can support pre-event framing or post-event extraction.")
        next_focus.append("Use the next event-related post to make the institution's point of view more explicit before and after the event.")
        signal_lines.append("The recent sample contains event-related posts that can feed the event engine.")
    else:
        next_focus.append("Identify 1 to 2 event-relevant posts or campus moments so the event engine is not empty this week.")

    deduped_opportunities = list(dict.fromkeys(opportunities))[:5]
    deduped_next_focus = list(dict.fromkeys(next_focus))[:5]
    deduped_signals = list(dict.fromkeys(signal_lines))[:4]
    return deduped_opportunities, deduped_next_focus, deduped_signals


def _media_kind(node: dict[str, Any]) -> str:
    typename = str(node.get("__typename") or "").strip()
    if typename == "GraphVideo":
        return "video"
    if typename == "GraphSidecar":
        return "carousel"
    return "image"


def _post_from_edge(edge: dict[str, Any]) -> dict[str, Any]:
    node = edge.get("node") if isinstance(edge.get("node"), dict) else {}
    shortcode = str(node.get("shortcode") or "").strip()
    caption = _caption_from_node(node)
    pillar = _classify_pillar(caption)
    audience = _classify_audience(caption, pillar)
    likes = _safe_int(((node.get("edge_liked_by") or {}).get("count")))
    comments = _safe_int(((node.get("edge_media_to_comment") or {}).get("count")))
    visible_engagement = likes + comments
    timestamp = node.get("taken_at_timestamp")
    taken_at = None
    if isinstance(timestamp, (int, float)):
        taken_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": str(node.get("id") or "").strip(),
        "shortcode": shortcode,
        "url": _instagram_permalink(shortcode) if shortcode else "",
        "media_kind": _media_kind(node),
        "taken_at": taken_at,
        "caption_excerpt": _summarize_caption(caption),
        "audience": audience,
        "content_pillar": pillar,
        "event_signal": _is_event_signal(caption),
        "likes": likes,
        "comments": comments,
        "visible_engagement": visible_engagement,
        "accessibility_caption": str(node.get("accessibility_caption") or "").strip(),
    }


def build_snapshot_from_profile_payload(
    payload: dict[str, Any],
    username: str,
    *,
    sample_size: int = 12,
) -> dict[str, Any]:
    user = (((payload.get("data") or {}).get("user")) or {})
    timeline = ((user.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
    posts = [_post_from_edge(edge) for edge in timeline if isinstance(edge, dict)]
    posts = [post for post in posts if post.get("shortcode")]
    recent_posts = posts[:sample_size]
    now = datetime.now(timezone.utc)
    visible_engagements = [int(post.get("visible_engagement") or 0) for post in recent_posts]
    visible_likes = [int(post.get("likes") or 0) for post in recent_posts]
    visible_comments = [int(post.get("comments") or 0) for post in recent_posts]
    top_post = max(recent_posts, key=lambda item: int(item.get("visible_engagement") or 0), default={})
    posts_last_7d = _posts_in_window(recent_posts, days=7, now=now)
    posts_last_30d = _posts_in_window(recent_posts, days=30, now=now)
    last_post_age_days = _latest_post_age_days(recent_posts, now=now)
    pillar_breakdown = _build_breakdown(recent_posts, "content_pillar")
    audience_breakdown = _build_breakdown(recent_posts, "audience")
    opportunities, next_focus, signal_lines = _opportunity_signals(
        recent_posts,
        pillar_breakdown,
        audience_breakdown,
        posts_last_7d=posts_last_7d,
    )

    followers = _safe_int(((user.get("edge_followed_by") or {}).get("count")))
    following = _safe_int(((user.get("edge_follow") or {}).get("count")))

    snapshot = {
        "generated_at": _iso_now(),
        "source": "instagram_public_web",
        "source_label": "Instagram public web signal",
        "handle": username,
        "profile_url": f"https://www.instagram.com/{username}/",
        "profile": {
            "username": str(user.get("username") or username).strip(),
            "full_name": str(user.get("full_name") or "").strip(),
            "biography": str(user.get("biography") or "").strip(),
            "followers": followers,
            "following": following,
            "external_url": str(user.get("external_url") or "").strip(),
            "category_name": str(user.get("category_name") or "").strip(),
            "is_business_account": bool(user.get("is_business_account")),
            "is_professional_account": bool(user.get("is_professional_account")),
            "timeline_count": _safe_int(((user.get("edge_owner_to_timeline_media") or {}).get("count"))),
        },
        "recent_posts": recent_posts,
        "recent_summary": {
            "sample_size": len(recent_posts),
            "average_visible_likes": round(mean(visible_likes), 2) if visible_likes else 0.0,
            "average_visible_comments": round(mean(visible_comments), 2) if visible_comments else 0.0,
            "average_visible_engagement": round(mean(visible_engagements), 2) if visible_engagements else 0.0,
            "total_visible_engagement": sum(visible_engagements),
            "engagement_per_100_followers": (
                round((sum(visible_engagements) / max(followers, 1)) * 100, 2) if visible_engagements else 0.0
            ),
            "posts_last_7d": posts_last_7d,
            "posts_last_30d": posts_last_30d,
            "last_post_age_days": last_post_age_days,
            "top_post": {
                "shortcode": str(top_post.get("shortcode") or "").strip(),
                "url": str(top_post.get("url") or "").strip(),
                "visible_engagement": int(top_post.get("visible_engagement") or 0),
                "caption_excerpt": str(top_post.get("caption_excerpt") or "").strip(),
            }
            if top_post
            else {},
        },
        "pillar_breakdown": pillar_breakdown,
        "audience_breakdown": audience_breakdown,
        "signal_lines": signal_lines,
        "opportunity_signals": opportunities,
        "recommended_next_focus": next_focus,
        "limitations": [
            "Public-only Instagram signal. This snapshot does not include reach, saves, shares, profile views, DMs, or non-public moderation data.",
            "Use this for narrative resonance checks and cadence review, not private-insights attribution.",
        ],
    }
    return snapshot


def load_workspace_feedback_snapshot(workspace_root: Path | None) -> dict[str, Any]:
    if workspace_root is None:
        return {}
    summary_path = workspace_root / ANALYTICS_SUBDIR / SUMMARY_FILENAME
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    payload.setdefault("json_path", str(summary_path))
    markdown_path = workspace_root / ANALYTICS_SUBDIR / SUMMARY_MARKDOWN_FILENAME
    if markdown_path.exists():
        payload.setdefault("markdown_path", str(markdown_path))
    return payload


class InstagramPublicFeedbackService:
    def fetch_profile_payload(self, username: str) -> dict[str, Any]:
        url = INSTAGRAM_WEB_PROFILE_URL.format(username=quote(username.strip()))
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "X-IG-App-ID": INSTAGRAM_WEB_APP_ID,
                "Accept": "application/json",
                "Referer": f"https://www.instagram.com/{username.strip()}/",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Instagram public profile request failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Instagram public profile request failed: {exc.reason}") from exc

    def build_snapshot(self, username: str, *, sample_size: int = 12) -> dict[str, Any]:
        payload = self.fetch_profile_payload(username)
        return build_snapshot_from_profile_payload(payload, username, sample_size=sample_size)

    def _render_markdown(self, snapshot: dict[str, Any]) -> str:
        profile = dict(snapshot.get("profile") or {})
        recent_summary = dict(snapshot.get("recent_summary") or {})
        lines = [
            "# Instagram Public Feedback Snapshot",
            "",
            f"- Generated: `{snapshot.get('generated_at')}`",
            f"- Handle: `{snapshot.get('handle')}`",
            f"- Source: `{snapshot.get('source_label') or snapshot.get('source')}`",
            f"- Profile URL: `{snapshot.get('profile_url')}`",
            "",
            "## Profile",
            f"- Name: {profile.get('full_name') or profile.get('username') or 'Unknown'}",
            f"- Followers: {profile.get('followers') or 0}",
            f"- Following: {profile.get('following') or 0}",
            f"- Category: {profile.get('category_name') or 'Unknown'}",
            f"- Professional account: {'yes' if profile.get('is_professional_account') else 'no'}",
            "",
            "## Recent Summary",
            f"- Sample size: {recent_summary.get('sample_size') or 0}",
            f"- Average visible likes: {recent_summary.get('average_visible_likes') or 0}",
            f"- Average visible comments: {recent_summary.get('average_visible_comments') or 0}",
            f"- Average visible engagement: {recent_summary.get('average_visible_engagement') or 0}",
            f"- Visible engagement per 100 followers: {recent_summary.get('engagement_per_100_followers') or 0}",
            f"- Posts in last 7 days: {recent_summary.get('posts_last_7d') or 0}",
            f"- Posts in last 30 days: {recent_summary.get('posts_last_30d') or 0}",
            "",
            "## Recent Posts",
        ]
        recent_posts = list(snapshot.get("recent_posts") or [])
        if not recent_posts:
            lines.append("- None.")
        else:
            for post in recent_posts[:8]:
                lines.append(
                    "- `{shortcode}` | {taken_at} | {pillar} for {audience} | likes={likes} comments={comments} | {caption}".format(
                        shortcode=post.get("shortcode") or "unknown",
                        taken_at=post.get("taken_at") or "unknown",
                        pillar=post.get("content_pillar") or "Unknown pillar",
                        audience=post.get("audience") or "unknown audience",
                        likes=post.get("likes") or 0,
                        comments=post.get("comments") or 0,
                        caption=post.get("caption_excerpt") or "No caption excerpt.",
                    )
                )
        lines.extend(["", "## Pillar Response"])
        pillar_breakdown = list(snapshot.get("pillar_breakdown") or [])
        if not pillar_breakdown:
            lines.append("- None.")
        else:
            for item in pillar_breakdown:
                lines.append(
                    f"- {item.get('label')}: posts={item.get('post_count') or 0}, avg_visible_engagement={item.get('average_visible_engagement') or 0}, top_post={item.get('top_post_shortcode') or 'n/a'}"
                )
        lines.extend(["", "## Audience Focus"])
        audience_breakdown = list(snapshot.get("audience_breakdown") or [])
        if not audience_breakdown:
            lines.append("- None.")
        else:
            for item in audience_breakdown:
                lines.append(
                    f"- {item.get('label')}: posts={item.get('post_count') or 0}, avg_visible_engagement={item.get('average_visible_engagement') or 0}"
                )
        lines.extend(["", "## Opportunity Signals"])
        opportunities = list(snapshot.get("opportunity_signals") or [])
        if not opportunities:
            lines.append("- None.")
        else:
            for item in opportunities[:5]:
                lines.append(f"- {item}")
        lines.extend(["", "## Recommended Next Focus"])
        next_focus = list(snapshot.get("recommended_next_focus") or [])
        if not next_focus:
            lines.append("- None.")
        else:
            for item in next_focus[:5]:
                lines.append(f"- {item}")
        lines.extend(["", "## Limits"])
        for item in snapshot.get("limitations") or ["Public-only signal."]:
            lines.append(f"- {item}")
        return "\n".join(lines).rstrip() + "\n"

    def persist_workspace_snapshot(
        self,
        workspace_key: str,
        workspace_root: Path,
        snapshot: dict[str, Any],
    ) -> dict[str, str]:
        analytics_root = workspace_root / ANALYTICS_SUBDIR
        analytics_root.mkdir(parents=True, exist_ok=True)
        summary_path = analytics_root / SUMMARY_FILENAME
        markdown_path = analytics_root / SUMMARY_MARKDOWN_FILENAME
        persisted = dict(snapshot)
        persisted["json_path"] = str(summary_path)
        persisted["markdown_path"] = str(markdown_path)
        summary_path.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(self._render_markdown(persisted), encoding="utf-8")
        upsert_snapshot(
            workspace_key,
            SNAPSHOT_TYPE,
            persisted,
            metadata={"source": "instagram_public_feedback_service", "visibility": "public_web"},
        )
        return {"json_path": str(summary_path), "markdown_path": str(markdown_path)}


instagram_public_feedback_service = InstagramPublicFeedbackService()
