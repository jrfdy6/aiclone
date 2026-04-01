from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import youtube_watchlist_service


class YouTubeWatchlistServiceTest(unittest.TestCase):
    def test_transcription_runtime_requires_real_whisper_api(self) -> None:
        with patch.object(youtube_watchlist_service.shutil, "which", side_effect=lambda name: "/usr/bin/fake" if name in {"yt-dlp", "ffmpeg"} else None), patch.object(
            youtube_watchlist_service.importlib.util,
            "find_spec",
            side_effect=lambda name: object() if name == "whisper" else None,
        ), patch.object(
            youtube_watchlist_service.importlib,
            "import_module",
            return_value=SimpleNamespace(),
        ):
            runtime = youtube_watchlist_service._transcription_runtime()

        self.assertTrue(runtime.get("yt_dlp"))
        self.assertTrue(runtime.get("ffmpeg"))
        self.assertFalse(runtime.get("whisper"))
        self.assertFalse(youtube_watchlist_service._can_transcribe())

    def test_build_payload_reads_channel_feed_and_marks_existing_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            (workspace_root / "research").mkdir(parents=True, exist_ok=True)
            (workspace_root / "research" / "watchlists.yaml").write_text(
                """
youtube_channels:
  - name: Nate B Jones
    url: https://www.youtube.com/@NateBJones
    purpose: Leadership and AI operator framing
    priority_lane: program-leadership
""".strip(),
                encoding="utf-8",
            )

            html = """
<html>
  <head>
    <link rel="alternate" type="application/rss+xml" title="RSS" href="https://www.youtube.com/feeds/videos.xml?channel_id=UC_TEST" />
  </head>
</html>
"""
            feed = """
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/">
  <title>Nate B Jones</title>
  <entry>
    <title>First video</title>
    <yt:videoId>abc123</yt:videoId>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123" />
    <published>2026-03-29T12:00:00+00:00</published>
    <author><name>Nate B Jones</name></author>
    <media:group>
      <media:description>Useful summary.</media:description>
    </media:group>
  </entry>
</feed>
"""

            def fake_http_get(url: str, *, accept: str | None = None) -> bytes:
                if "@NateBJones" in url:
                    return html.encode("utf-8")
                if "feeds/videos.xml" in url:
                    return feed.encode("utf-8")
                raise AssertionError(f"Unexpected URL requested: {url}")

            with patch.object(youtube_watchlist_service, "_http_get", side_effect=fake_http_get), patch.object(
                youtube_watchlist_service,
                "_extract_existing_source_urls",
                return_value={"https://www.youtube.com/watch?v=abc123"},
            ), patch.object(youtube_watchlist_service, "_transcription_runtime", return_value={"yt_dlp": True, "ffmpeg": True, "whisper": True}):
                payload = youtube_watchlist_service.build_youtube_watchlist_payload(workspace_root)

            self.assertEqual(payload.get("counts", {}).get("channels"), 1)
            self.assertEqual(payload.get("counts", {}).get("videos"), 1)
            self.assertTrue(payload.get("runtime", {}).get("can_transcribe"))
            channel = (payload.get("channels") or [{}])[0]
            video = (channel.get("videos") or [{}])[0]
            self.assertEqual(channel.get("channel_id"), "UC_TEST")
            self.assertEqual(video.get("url"), "https://www.youtube.com/watch?v=abc123")
            self.assertTrue(video.get("already_ingested"))

    def test_run_ingest_job_falls_back_to_url_only_when_transcription_runtime_missing(self) -> None:
        with patch.object(youtube_watchlist_service, "_can_transcribe", return_value=False), patch.object(
            youtube_watchlist_service,
            "_yt_dlp_json",
            return_value={
                "title": "Operator video",
                "description": "This is the first line.\nAnd more detail.",
                "channel": "Nate B Jones",
            },
        ), patch.object(
            youtube_watchlist_service.brain_long_form_ingest_service,
            "register_source",
            return_value={"asset_id": "asset-1", "source_type": "youtube_transcript"},
        ) as register_source:
            job = youtube_watchlist_service.queue_youtube_ingest(
                url="https://www.youtube.com/watch?v=abc123",
                title="",
                summary="",
                author="",
                channel_name="Nate B Jones",
                priority_lane="program-leadership",
                run_refresh=False,
            )
            youtube_watchlist_service.run_ingest_job(job["job_id"])

        jobs = youtube_watchlist_service.list_ingest_jobs()
        stored = next(item for item in jobs if item["job_id"] == job["job_id"])
        self.assertEqual(stored.get("status"), "completed")
        self.assertEqual(stored.get("ingestion_mode"), "url_only")
        _, kwargs = register_source.call_args
        self.assertEqual(kwargs.get("source_type"), "youtube_transcript")
        self.assertIn("Selected from YouTube watchlist", kwargs.get("notes") or "")
        self.assertEqual(kwargs.get("title"), "Operator video")

    def test_sync_watchlist_auto_ingest_only_pulls_enabled_new_videos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            (workspace_root / "research").mkdir(parents=True, exist_ok=True)
            (workspace_root / "research" / "watchlists.yaml").write_text(
                """
youtube_channels:
  - name: Nate B Jones
    url: https://www.youtube.com/@NateBJones
    priority_lane: program-leadership
    auto_ingest: true
  - name: Champion Leadership
    url: https://www.youtube.com/@championleadership
    priority_lane: program-leadership
    auto_ingest: true
  - name: All-In Podcast
    url: https://www.youtube.com/@allin
    priority_lane: entrepreneurship
    auto_ingest: false
youtube_auto_ingest:
  enabled: true
  max_videos_per_run: 2
  per_channel_limit: 1
""".strip(),
                encoding="utf-8",
            )

            def fake_fetch(channel: dict[str, object], *, limit: int, existing_urls: set[str]) -> dict[str, object]:
                name = channel.get("name")
                if name == "Nate B Jones":
                    return {
                        "name": name,
                        "videos": [
                            {
                                "title": "Newest Nate",
                                "url": "https://www.youtube.com/watch?v=nate1",
                                "published_at": "2026-03-30T12:00:00+00:00",
                                "priority_lane": "program-leadership",
                                "channel_name": name,
                                "author": name,
                                "already_ingested": False,
                            }
                        ],
                    }
                if name == "Champion Leadership":
                    return {
                        "name": name,
                        "videos": [
                            {
                                "title": "Newest Champion",
                                "url": "https://www.youtube.com/watch?v=champ1",
                                "published_at": "2026-03-29T12:00:00+00:00",
                                "priority_lane": "program-leadership",
                                "channel_name": name,
                                "author": name,
                                "already_ingested": False,
                            }
                        ],
                    }
                raise AssertionError(f"Unexpected channel fetch: {name}")

            with patch.object(youtube_watchlist_service, "_extract_existing_source_urls", return_value=set()), patch.object(
                youtube_watchlist_service,
                "_fetch_channel_entries",
                side_effect=fake_fetch,
            ), patch.object(
                youtube_watchlist_service,
                "backfill_pending_youtube_transcripts",
                return_value={"backfilled": [], "skipped": [], "errors": [], "counts": {"pending_total": 0, "selected": 0, "backfilled": 0, "skipped": 0, "errors": 0}},
            ), patch.object(
                youtube_watchlist_service,
                "_ingest_watchlist_video",
                side_effect=[
                    {"asset_id": "asset-nate", "ingestion_mode": "url_only"},
                    {"asset_id": "asset-champion", "ingestion_mode": "url_only"},
                ],
            ) as ingest_video:
                result = youtube_watchlist_service.sync_watchlist_auto_ingest(workspace_root=workspace_root)

        self.assertTrue(result.get("enabled"))
        self.assertEqual(result.get("counts", {}).get("ingested"), 2)
        self.assertEqual(len(result.get("ingested") or []), 2)
        self.assertTrue(any(item.get("reason") == "auto_ingest_disabled" for item in (result.get("skipped") or [])))
        called_urls = [call.kwargs.get("url") for call in ingest_video.call_args_list]
        self.assertEqual(called_urls, ["https://www.youtube.com/watch?v=nate1", "https://www.youtube.com/watch?v=champ1"])

    def test_backfill_pending_youtube_transcripts_rewrites_pending_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            ingestions_root = repo_root / "knowledge" / "ingestions" / "2026" / "03" / "pending_watchlist_video"
            ingestions_root.mkdir(parents=True, exist_ok=True)
            normalized_path = ingestions_root / "normalized.md"
            normalized_path.write_text(
                """---
id: pending_watchlist_video
title: Pending Watchlist Video
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
- youtube
- video
tags:
- brain_ingest
- needs_review
source_url: https://www.youtube.com/watch?v=pendingwatchlist
author: unknown
raw_files:
- raw/source.url
word_count:
summary: 'Selected from YouTube watchlist: Selected AI YouTube Channel.'
---

# Source Notes
Selected from YouTube watchlist: Selected AI YouTube Channel.
Priority lane: ai.
Registered from link. Transcript capture still pending.
""",
                encoding="utf-8",
            )

            with patch.object(youtube_watchlist_service, "_repo_root", return_value=repo_root), patch.object(
                youtube_watchlist_service,
                "_ingestions_root",
                return_value=repo_root / "knowledge" / "ingestions",
            ), patch.object(
                youtube_watchlist_service,
                "_transcripts_root",
                return_value=repo_root / "knowledge" / "aiclone" / "transcripts",
            ), patch.object(
                youtube_watchlist_service,
                "_can_transcribe",
                return_value=True,
            ), patch.object(
                youtube_watchlist_service,
                "_transcription_runtime",
                return_value={"yt_dlp": True, "ffmpeg": True, "whisper": True},
            ), patch.object(
                youtube_watchlist_service,
                "_transcribe_youtube_url",
                return_value=(
                    "Agents fail when they lack context from the real workflow. Build the handoff before the prompt.",
                    {"title": "Pending Watchlist Video", "channel": "Selected AI YouTube Channel"},
                ),
            ):
                result = youtube_watchlist_service.backfill_pending_youtube_transcripts(limit=1, run_refresh=False)

            self.assertEqual(result.get("counts", {}).get("backfilled"), 1)
            self.assertEqual((result.get("backfilled") or [{}])[0].get("asset_id"), "pending_watchlist_video")
            updated = normalized_path.read_text(encoding="utf-8")
            self.assertIn("# Clean Transcript / Document", updated)
            self.assertIn("Build the handoff before the prompt.", updated)
            self.assertNotIn("Transcript capture still pending", updated)
            self.assertTrue((ingestions_root / "raw" / "transcript.txt").exists())
            routing_status = json.loads((ingestions_root / "routing_status.json").read_text(encoding="utf-8"))
            self.assertTrue(routing_status.get("has_transcript"))

    def test_backfill_pending_youtube_transcripts_uses_subtitles_without_whisper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            ingestions_root = repo_root / "knowledge" / "ingestions" / "2026" / "03" / "pending_watchlist_video"
            ingestions_root.mkdir(parents=True, exist_ok=True)
            normalized_path = ingestions_root / "normalized.md"
            normalized_path.write_text(
                """---
id: pending_watchlist_video
title: Pending Watchlist Video
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
- youtube
- video
tags:
- brain_ingest
- needs_review
source_url: https://www.youtube.com/watch?v=pendingwatchlist
author: unknown
raw_files:
- raw/source.url
word_count:
summary: 'Selected from YouTube watchlist: Selected AI YouTube Channel.'
---

# Source Notes
Selected from YouTube watchlist: Selected AI YouTube Channel.
Priority lane: ai.
Registered from link. Transcript capture still pending.
""",
                encoding="utf-8",
            )

            with patch.object(youtube_watchlist_service, "_repo_root", return_value=repo_root), patch.object(
                youtube_watchlist_service,
                "_ingestions_root",
                return_value=repo_root / "knowledge" / "ingestions",
            ), patch.object(
                youtube_watchlist_service,
                "_transcripts_root",
                return_value=repo_root / "knowledge" / "aiclone" / "transcripts",
            ), patch.object(
                youtube_watchlist_service,
                "_can_attempt_youtube_transcript",
                return_value=True,
            ), patch.object(
                youtube_watchlist_service,
                "_transcription_runtime",
                return_value={"yt_dlp": True, "ffmpeg": True, "whisper": False},
            ), patch.object(
                youtube_watchlist_service,
                "_transcribe_youtube_url",
                return_value=(
                    "Use the transcript itself as the quote-bearing review source before adding persona interpretation.",
                    {"title": "Pending Watchlist Video", "channel": "Selected AI YouTube Channel"},
                ),
            ):
                result = youtube_watchlist_service.backfill_pending_youtube_transcripts(limit=1, run_refresh=False)

            self.assertEqual(result.get("counts", {}).get("backfilled"), 1)
            self.assertEqual((result.get("backfilled") or [{}])[0].get("asset_id"), "pending_watchlist_video")
            updated = normalized_path.read_text(encoding="utf-8")
            self.assertIn("quote-bearing review source", updated)

    def test_sync_watchlist_auto_ingest_runs_pending_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            (workspace_root / "research").mkdir(parents=True, exist_ok=True)
            (workspace_root / "research" / "watchlists.yaml").write_text(
                """
youtube_channels: []
youtube_auto_ingest:
  enabled: true
  max_videos_per_run: 2
  per_channel_limit: 1
""".strip(),
                encoding="utf-8",
            )

            with patch.object(
                youtube_watchlist_service,
                "backfill_pending_youtube_transcripts",
                return_value={
                    "backfilled": [{"asset_id": "pending_watchlist_video"}],
                    "skipped": [],
                    "errors": [],
                    "counts": {"pending_total": 1, "selected": 1, "backfilled": 1, "skipped": 0, "errors": 0},
                },
            ) as backfill:
                result = youtube_watchlist_service.sync_watchlist_auto_ingest(workspace_root=workspace_root, run_refresh=False)

        self.assertTrue(result.get("enabled"))
        self.assertEqual(result.get("counts", {}).get("backfilled"), 1)
        self.assertEqual((result.get("backfill") or {}).get("counts", {}).get("backfilled"), 1)
        backfill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
