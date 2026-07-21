from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import youtube_watchlist_service


class YouTubeWhisperRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        youtube_watchlist_service._clear_whisper_runtime_probe_cache()

    def tearDown(self) -> None:
        youtube_watchlist_service._clear_whisper_runtime_probe_cache()

    def test_whisper_dependency_is_local_only(self) -> None:
        local_requirements_path = BACKEND_ROOT / "requirements-local-media.txt"
        general_requirements = {
            line.strip().lower()
            for line in (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        local_requirements = {
            line.strip().lower()
            for line in local_requirements_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        local_requirements_doc = local_requirements_path.read_text(encoding="utf-8").lower()

        self.assertNotIn("whisper", general_requirements)
        self.assertFalse(any(line.startswith("openai-whisper") for line in general_requirements))
        self.assertIn("openai-whisper==20240930", local_requirements)
        self.assertIn("yt-dlp", local_requirements_doc)
        self.assertIn("ffmpeg", local_requirements_doc)

    def test_configured_local_python_is_preferred_before_fixed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            configured = Path(temp_dir) / "configured-python"
            fallback = Path(temp_dir) / "fallback-python"
            configured.touch(mode=0o700)
            fallback.touch(mode=0o700)
            with patch.dict(
                youtube_watchlist_service.os.environ,
                {youtube_watchlist_service.LOCAL_WHISPER_PYTHON_ENV: str(configured)},
            ), patch.object(
                youtube_watchlist_service,
                "LOCAL_WHISPER_FALLBACK_PYTHON",
                fallback,
            ):
                candidates = youtube_watchlist_service._allowlisted_local_whisper_python_candidates()

        self.assertEqual(candidates, [configured, fallback])

    def test_runtime_requires_real_in_process_load_model_api(self) -> None:
        with patch.object(
            youtube_watchlist_service.importlib.util,
            "find_spec",
            return_value=object(),
        ), patch.object(
            youtube_watchlist_service.importlib,
            "import_module",
            return_value=SimpleNamespace(load_model=lambda _name: object()),
        ), patch.object(
            youtube_watchlist_service,
            "_allowlisted_local_whisper_python_candidates",
            side_effect=AssertionError("fallback probe should not run"),
        ), patch.object(
            youtube_watchlist_service.shutil,
            "which",
            side_effect=lambda name: f"/usr/bin/{name}",
        ):
            runtime = youtube_watchlist_service._transcription_runtime()

        self.assertTrue(runtime["whisper"])
        self.assertTrue(runtime["whisper_in_process"])
        self.assertFalse(runtime["whisper_subprocess"])
        self.assertEqual(runtime["whisper_mode"], "in_process")

    def test_runtime_uses_allowlisted_local_python_fallback(self) -> None:
        fallback = Path("/usr/bin/python3")
        with patch.object(
            youtube_watchlist_service,
            "_in_process_whisper_available",
            return_value=False,
        ), patch.object(
            youtube_watchlist_service,
            "_allowlisted_local_whisper_python_candidates",
            return_value=[fallback],
        ), patch.object(
            youtube_watchlist_service,
            "_probe_local_whisper_python",
            return_value=True,
        ) as probe, patch.object(
            youtube_watchlist_service.shutil,
            "which",
            side_effect=lambda name: f"/usr/bin/{name}",
        ):
            runtime = youtube_watchlist_service._transcription_runtime()

        probe.assert_called_once_with(fallback)
        self.assertTrue(runtime["whisper"])
        self.assertFalse(runtime["whisper_in_process"])
        self.assertTrue(runtime["whisper_subprocess"])
        self.assertEqual(runtime["whisper_mode"], "local_subprocess")
        self.assertNotIn("python", runtime)

    def test_railway_runtime_never_probes_local_media_dependencies(self) -> None:
        with patch.dict(
            youtube_watchlist_service.os.environ,
            {"RAILWAY_ENVIRONMENT": "production"},
            clear=False,
        ), patch.object(
            youtube_watchlist_service,
            "_whisper_runtime_probe",
            side_effect=AssertionError("Railway must not probe a local Whisper runtime"),
        ), patch.object(
            youtube_watchlist_service.shutil,
            "which",
            side_effect=AssertionError("Railway must not probe local media binaries"),
        ):
            runtime = youtube_watchlist_service._transcription_runtime()

        self.assertEqual(runtime["whisper_mode"], "unavailable")
        self.assertFalse(runtime["yt_dlp"])
        self.assertFalse(runtime["ffmpeg"])
        self.assertFalse(runtime["whisper"])

    def test_runtime_probe_is_cached_and_env_override_invalidates_cache(self) -> None:
        default_python = Path("/usr/bin/python3")
        configured_python = Path("/private/tmp/aiclone-whisper-python")

        def candidates() -> list[Path]:
            if youtube_watchlist_service.os.getenv(youtube_watchlist_service.LOCAL_WHISPER_PYTHON_ENV):
                return [configured_python, default_python]
            return [default_python]

        with patch.dict(
            youtube_watchlist_service.os.environ,
            {},
            clear=False,
        ), patch.object(
            youtube_watchlist_service,
            "_in_process_whisper_available",
            return_value=False,
        ) as in_process, patch.object(
            youtube_watchlist_service,
            "_allowlisted_local_whisper_python_candidates",
            side_effect=candidates,
        ), patch.object(
            youtube_watchlist_service,
            "_probe_local_whisper_python",
            return_value=True,
        ) as probe:
            youtube_watchlist_service.os.environ.pop(youtube_watchlist_service.LOCAL_WHISPER_PYTHON_ENV, None)
            first = youtube_watchlist_service._whisper_runtime_probe()
            second = youtube_watchlist_service._whisper_runtime_probe()
            youtube_watchlist_service.os.environ[youtube_watchlist_service.LOCAL_WHISPER_PYTHON_ENV] = str(
                configured_python
            )
            after_override = youtube_watchlist_service._whisper_runtime_probe()

        self.assertEqual(first, ("local_subprocess", default_python))
        self.assertEqual(second, first)
        self.assertEqual(after_override, ("local_subprocess", configured_python))
        self.assertEqual(in_process.call_count, 2)
        self.assertEqual(probe.call_args_list[0].args, (default_python,))
        self.assertEqual(probe.call_args_list[1].args, (configured_python,))
        self.assertEqual(probe.call_count, 2)

    def test_runtime_probe_cache_expires_after_bounded_ttl(self) -> None:
        ttl = youtube_watchlist_service.WHISPER_RUNTIME_PROBE_TTL_SECONDS
        with patch.object(
            youtube_watchlist_service,
            "_uncached_whisper_runtime_probe",
            side_effect=[("unavailable", None), ("in_process", None)],
        ) as probe, patch.object(
            youtube_watchlist_service.time,
            "monotonic",
            side_effect=[100.0, 100.0, 100.0 + ttl - 1, 100.0 + ttl + 1, 100.0 + ttl + 1],
        ):
            first = youtube_watchlist_service._whisper_runtime_probe()
            cached = youtube_watchlist_service._whisper_runtime_probe()
            refreshed = youtube_watchlist_service._whisper_runtime_probe()

        self.assertEqual(first, ("unavailable", None))
        self.assertEqual(cached, first)
        self.assertEqual(refreshed, ("in_process", None))
        self.assertEqual(probe.call_count, 2)

    def test_probe_rejects_module_without_load_model_and_never_uses_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=3,
            stdout=youtube_watchlist_service.LOCAL_WHISPER_RESULT_PREFIX + '{"ok": false}\n',
            stderr="",
        )
        with patch.dict(
            youtube_watchlist_service.os.environ,
            {"OPENAI_API_KEY": "must-not-be-inherited"},
        ), patch.object(youtube_watchlist_service.subprocess, "run", return_value=completed) as run:
            available = youtube_watchlist_service._probe_local_whisper_python(Path("/usr/bin/python3"))

        self.assertFalse(available)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:2], ["/usr/bin/python3", "-c"])
        self.assertEqual(args[0][2], youtube_watchlist_service.LOCAL_WHISPER_PROBE_CODE)
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], youtube_watchlist_service.WHISPER_PROBE_TIMEOUT_SECONDS)
        self.assertNotIn("OPENAI_API_KEY", kwargs["env"])

    def test_transcribe_audio_dispatches_in_process(self) -> None:
        model = Mock()
        model.transcribe.return_value = {"text": "  a local transcript  "}
        audio_path = Path("/private/tmp/video.mp3")
        with patch.object(
            youtube_watchlist_service,
            "_whisper_runtime_probe",
            return_value=("in_process", None),
        ), patch.object(
            youtube_watchlist_service,
            "_whisper_model",
            return_value=model,
        ) as load_model, patch.object(
            youtube_watchlist_service,
            "_transcribe_with_local_whisper_python",
            side_effect=AssertionError("subprocess path should not run"),
        ):
            transcript = youtube_watchlist_service._transcribe_audio(audio_path, "base")

        load_model.assert_called_once_with("base")
        model.transcribe.assert_called_once_with(str(audio_path), verbose=False)
        self.assertEqual(transcript, "a local transcript")

    def test_transcribe_audio_dispatches_to_local_python(self) -> None:
        python_path = Path("/usr/bin/python3")
        audio_path = Path("/private/tmp/video.mp3")
        with patch.object(
            youtube_watchlist_service,
            "_whisper_runtime_probe",
            return_value=("local_subprocess", python_path),
        ), patch.object(
            youtube_watchlist_service,
            "_transcribe_with_local_whisper_python",
            return_value="fallback transcript",
        ) as transcribe, patch.object(
            youtube_watchlist_service,
            "_whisper_model",
            side_effect=AssertionError("in-process path should not run"),
        ):
            transcript = youtube_watchlist_service._transcribe_audio(audio_path, "small")

        transcribe.assert_called_once_with(audio_path, "small", python_path)
        self.assertEqual(transcript, "fallback transcript")

    def test_local_python_transcription_uses_fixed_argv_and_bounded_timeout(self) -> None:
        stdout = (
            "progress output\n"
            + youtube_watchlist_service.LOCAL_WHISPER_RESULT_PREFIX
            + '{"ok": true, "text": "captured locally"}\n'
        )
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        audio_path = Path("/private/tmp/video.mp3")
        python_path = Path("/usr/bin/python3")
        with patch.dict(
            youtube_watchlist_service.os.environ,
            {"CONTROL_PLANE_SERVICE_TOKEN": "must-not-be-inherited"},
        ), patch.object(youtube_watchlist_service.subprocess, "run", return_value=completed) as run:
            transcript = youtube_watchlist_service._transcribe_with_local_whisper_python(
                audio_path,
                "base",
                python_path,
            )

        self.assertEqual(transcript, "captured locally")
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            [
                "/usr/bin/python3",
                "-c",
                youtube_watchlist_service.LOCAL_WHISPER_TRANSCRIBE_CODE,
                str(audio_path),
                "base",
            ],
        )
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], youtube_watchlist_service.WHISPER_TRANSCRIBE_TIMEOUT_SECONDS)
        self.assertNotIn("CONTROL_PLANE_SERVICE_TOKEN", kwargs["env"])

    def test_local_python_transcription_reports_timeout_and_invalid_output(self) -> None:
        with patch.object(
            youtube_watchlist_service.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["python3"], timeout=10),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                youtube_watchlist_service._transcribe_with_local_whisper_python(
                    Path("/private/tmp/video.mp3"),
                    "base",
                    Path("/usr/bin/python3"),
                )

        invalid = subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr="")
        with patch.object(youtube_watchlist_service.subprocess, "run", return_value=invalid):
            with self.assertRaisesRegex(RuntimeError, "invalid transcription result"):
                youtube_watchlist_service._transcribe_with_local_whisper_python(
                    Path("/private/tmp/video.mp3"),
                    "base",
                    Path("/usr/bin/python3"),
                )

    def test_transcribe_audio_rejects_untrusted_model_name(self) -> None:
        with patch.object(
            youtube_watchlist_service,
            "_whisper_runtime_probe",
            side_effect=AssertionError("runtime must not be invoked for an invalid model"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Unsupported local Whisper model"):
                youtube_watchlist_service._transcribe_audio(Path("/private/tmp/video.mp3"), "../../model")


if __name__ == "__main__":
    unittest.main()
