from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import youtube_watchlist_service


class YouTubeWatchlistServiceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
