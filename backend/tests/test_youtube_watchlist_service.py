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
    def test_persisted_payload_never_fetches_network_or_writes(self) -> None:
        persisted = {
            "schema_version": "youtube_watchlist/v1",
            "generated_at": "2026-07-20T12:00:00+00:00",
            "workspace": "linkedin-content-os",
            "data_mode": "local_runner_refresh",
            "runtime": {"can_transcribe": True, "scope": "local_codex_runner"},
            "channels": [{"name": "Saved channel", "videos": [{"title": "Saved video"}]}],
            "counts": {"channels": 1, "videos": 1, "already_ingested": 0},
        }

        with patch.object(youtube_watchlist_service, "get_snapshot_payload", return_value=persisted) as read_snapshot, patch.object(
            youtube_watchlist_service,
            "_http_get",
            side_effect=AssertionError("network read called"),
        ) as network, patch.object(
            youtube_watchlist_service,
            "upsert_snapshot",
            side_effect=AssertionError("state write called"),
        ) as write, patch.object(
            youtube_watchlist_service,
            "_load_watchlist",
            side_effect=AssertionError("fallback config read called"),
        ) as config_read:
            payload = youtube_watchlist_service.build_persisted_youtube_watchlist_payload()

        read_snapshot.assert_called_once_with("linkedin-content-os", "youtube_watchlist")
        network.assert_not_called()
        write.assert_not_called()
        config_read.assert_not_called()
        self.assertEqual(payload.get("data_mode"), "persisted")
        self.assertEqual(((payload.get("channels") or [{}])[0].get("name")), "Saved channel")

    def test_persisted_payload_falls_back_to_configuration_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            (workspace_root / "research").mkdir(parents=True, exist_ok=True)
            (workspace_root / "research" / "watchlists.yaml").write_text(
                """
youtube_channels:
  - name: Saved configuration
    url: https://www.youtube.com/channel/UC_CONFIG
    purpose: Operator learning
    priority_lane: ai
youtube_auto_ingest:
  enabled: true
  max_videos_per_run: 2
""".strip(),
                encoding="utf-8",
            )

            with patch.object(youtube_watchlist_service, "get_snapshot_payload", return_value=None), patch.object(
                youtube_watchlist_service,
                "_http_get",
                side_effect=AssertionError("network read called"),
            ) as network, patch.object(
                youtube_watchlist_service,
                "upsert_snapshot",
                side_effect=AssertionError("state write called"),
            ) as write, patch.object(
                youtube_watchlist_service,
                "_transcription_runtime",
                side_effect=AssertionError("local runtime probe called"),
            ) as runtime_probe:
                payload = youtube_watchlist_service.build_persisted_youtube_watchlist_payload(workspace_root)

        network.assert_not_called()
        write.assert_not_called()
        runtime_probe.assert_not_called()
        self.assertEqual(payload.get("data_mode"), "configuration_only")
        self.assertEqual((payload.get("counts") or {}).get("channels"), 1)
        self.assertEqual((payload.get("counts") or {}).get("videos"), 0)
        self.assertEqual(((payload.get("channels") or [{}])[0].get("channel_id")), "UC_CONFIG")

    def test_transcription_runtime_requires_real_whisper_api(self) -> None:
        youtube_watchlist_service._clear_whisper_runtime_probe_cache()
        self.addCleanup(youtube_watchlist_service._clear_whisper_runtime_probe_cache)
        with patch.object(youtube_watchlist_service.shutil, "which", side_effect=lambda name: "/usr/bin/fake" if name in {"yt-dlp", "ffmpeg"} else None), patch.object(
            youtube_watchlist_service.importlib.util,
            "find_spec",
            side_effect=lambda name: object() if name == "whisper" else None,
        ), patch.object(
            youtube_watchlist_service.importlib,
            "import_module",
            return_value=SimpleNamespace(),
        ), patch.object(
            youtube_watchlist_service,
            "_allowlisted_local_whisper_python_candidates",
            return_value=[],
        ):
            runtime = youtube_watchlist_service._transcription_runtime()

        self.assertTrue(runtime.get("yt_dlp"))
        self.assertTrue(runtime.get("ffmpeg"))
        self.assertFalse(runtime.get("whisper"))
        with patch.object(youtube_watchlist_service, "_transcription_runtime", return_value=runtime):
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
        self.assertEqual(kwargs.get("ingestions_root"), youtube_watchlist_service._ingestions_root())
        self.assertEqual(kwargs.get("reference_root"), youtube_watchlist_service._state_root())

    def test_watchlist_ingest_writes_generated_asset_only_to_private_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "project"
            state_root = Path(temp_dir) / "private-state"
            repo_root.mkdir()
            with patch.object(
                youtube_watchlist_service,
                "_repo_root",
                return_value=repo_root,
            ), patch.object(
                youtube_watchlist_service,
                "_state_root",
                return_value=state_root,
            ), patch.object(
                youtube_watchlist_service,
                "_can_attempt_youtube_transcript",
                return_value=False,
            ), patch.object(
                youtube_watchlist_service.shutil,
                "which",
                return_value=None,
            ):
                result = youtube_watchlist_service._ingest_watchlist_video(
                    url="https://www.youtube.com/watch?v=private-state-proof",
                    title="Private state proof",
                    channel_name="Test channel",
                    run_refresh=False,
                )

            source_path = str(result.get("source_path") or "")
            self.assertTrue(source_path.startswith("memory/source-intelligence/ingestions/"))
            self.assertTrue((state_root / source_path).is_file())
            self.assertFalse((repo_root / "knowledge" / "ingestions").exists())

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

    def test_sync_watchlist_auto_ingest_treats_channel_fetch_failure_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            (workspace_root / "research").mkdir(parents=True, exist_ok=True)
            (workspace_root / "research" / "watchlists.yaml").write_text(
                """
youtube_channels:
  - name: Nate B Jones
    url: https://www.youtube.com/feeds/videos.xml?channel_id=STALE
    priority_lane: program-leadership
    auto_ingest: true
  - name: Champion Leadership
    url: https://www.youtube.com/@championleadership
    priority_lane: program-leadership
    auto_ingest: true
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
                    return {"name": name, "error": "HTTP Error 404: Not Found", "videos": []}
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
                return_value={"asset_id": "asset-champion", "ingestion_mode": "url_only"},
            ) as ingest_video:
                result = youtube_watchlist_service.sync_watchlist_auto_ingest(workspace_root=workspace_root)

        self.assertEqual(result.get("counts", {}).get("ingested"), 1)
        self.assertEqual(result.get("counts", {}).get("warnings"), 1)
        self.assertEqual(result.get("counts", {}).get("errors"), 0)
        warning = (result.get("warnings") or [{}])[0]
        self.assertEqual(warning.get("kind"), "channel_fetch_failed")
        self.assertEqual(warning.get("channel_name"), "Nate B Jones")
        called_urls = [call.kwargs.get("url") for call in ingest_video.call_args_list]
        self.assertEqual(called_urls, ["https://www.youtube.com/watch?v=champ1"])

    def test_backfill_pending_youtube_transcripts_rewrites_pending_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            state_root = repo_root / "private-state"
            ingestions_root = repo_root / "knowledge" / "ingestions" / "2026" / "03" / "pending_watchlist_video"
            ingestions_root.mkdir(parents=True, exist_ok=True)
            normalized_path = ingestions_root / "normalized.md"
            original = """---
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
"""
            normalized_path.write_text(original, encoding="utf-8")

            with patch.object(youtube_watchlist_service, "_repo_root", return_value=repo_root), patch.object(
                youtube_watchlist_service,
                "_state_root",
                return_value=state_root,
            ), patch.object(
                youtube_watchlist_service,
                "_legacy_ingestions_root",
                return_value=repo_root / "knowledge" / "ingestions",
            ), patch.object(
                youtube_watchlist_service,
                "_legacy_transcripts_root",
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
            private_asset_dir = (
                state_root
                / "memory"
                / "source-intelligence"
                / "ingestions"
                / "2026"
                / "03"
                / "pending_watchlist_video"
            )
            updated = (private_asset_dir / "normalized.md").read_text(encoding="utf-8")
            self.assertIn("# Clean Transcript / Document", updated)
            self.assertIn("Build the handoff before the prompt.", updated)
            self.assertNotIn("Transcript capture still pending", updated)
            self.assertEqual(normalized_path.read_text(encoding="utf-8"), original)
            self.assertTrue((private_asset_dir / "raw" / "transcript.txt").exists())
            routing_status = json.loads(
                (private_asset_dir / "routing_status.json").read_text(encoding="utf-8")
            )
            self.assertTrue(routing_status.get("has_transcript"))
            self.assertEqual(
                (result.get("backfilled") or [{}])[0].get("source_path"),
                "memory/source-intelligence/ingestions/2026/03/pending_watchlist_video/normalized.md",
            )

    def test_backfill_pending_youtube_transcripts_uses_subtitles_without_whisper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            state_root = repo_root / "private-state"
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
                "_state_root",
                return_value=state_root,
            ), patch.object(
                youtube_watchlist_service,
                "_legacy_ingestions_root",
                return_value=repo_root / "knowledge" / "ingestions",
            ), patch.object(
                youtube_watchlist_service,
                "_legacy_transcripts_root",
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
            updated = (
                state_root
                / "memory"
                / "source-intelligence"
                / "ingestions"
                / "2026"
                / "03"
                / "pending_watchlist_video"
                / "normalized.md"
            ).read_text(encoding="utf-8")
            self.assertIn("quote-bearing review source", updated)
            self.assertIn("Transcript capture still pending", normalized_path.read_text(encoding="utf-8"))

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
