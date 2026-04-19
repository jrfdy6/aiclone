from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes.content_generation import (
    CONTENT_EDITOR_MODEL_ALIAS,
    CONTENT_FAST_MODEL_ALIAS,
    ContentLLMProvider,
    _normalize_chat_completion_kwargs,
    _parse_provider_order,
    _provider_is_configured,
    _provider_trace_indicates_fallback,
    _resolve_provider_model,
)


class ProviderTraceFallbackTests(unittest.TestCase):
    def test_multiple_successful_calls_on_same_provider_are_not_counted_as_failover(self) -> None:
        trace = [
            {"provider": "gemini", "actual_model": "gemini-2.5-flash", "status": "success"},
            {"provider": "gemini", "actual_model": "gemini-2.5-flash", "status": "success"},
            {"provider": "gemini", "actual_model": "gemini-2.5-flash", "status": "success"},
        ]

        self.assertFalse(_provider_trace_indicates_fallback(trace))

    def test_failed_call_and_openai_recovery_counts_as_failover(self) -> None:
        trace = [
            {"provider": "gemini", "actual_model": "gemini-2.5-flash", "status": "failed"},
            {"provider": "openai", "actual_model": "gpt-4o-mini", "status": "success"},
        ]

        self.assertTrue(_provider_trace_indicates_fallback(trace))

    def test_same_provider_retry_then_success_is_not_counted_as_failover(self) -> None:
        trace = [
            {"provider": "gemini", "actual_model": "gemini-2.5-flash", "status": "failed", "attempt": 1},
            {"provider": "gemini", "actual_model": "gemini-2.5-flash", "status": "success", "attempt": 2},
        ]

        self.assertFalse(_provider_trace_indicates_fallback(trace))

    def test_provider_aliases_resolve_to_configured_models_for_openai(self) -> None:
        provider = ContentLLMProvider(
            name="openai",
            client=object(),
            fast_model="gpt-5-nano",
            editor_model="gpt-5-mini",
        )

        self.assertEqual(_resolve_provider_model(provider, CONTENT_FAST_MODEL_ALIAS), "gpt-5-nano")
        self.assertEqual(_resolve_provider_model(provider, CONTENT_EDITOR_MODEL_ALIAS), "gpt-5-mini")

    def test_codex_provider_maps_existing_aliases_to_codex_models(self) -> None:
        provider = ContentLLMProvider(
            name="codex",
            client=object(),
            fast_model="gpt-5.4-mini",
            editor_model="gpt-5.4-mini",
        )

        self.assertEqual(_resolve_provider_model(provider, "gpt-4o-mini"), "gpt-5.4-mini")
        self.assertEqual(_resolve_provider_model(provider, "gpt-4o"), "gpt-5.4-mini")

    def test_provider_order_parser_accepts_codex(self) -> None:
        self.assertEqual(_parse_provider_order("codex,gemini,openai"), ["codex", "gemini", "openai"])

    def test_codex_provider_uses_dedicated_or_openai_api_key(self) -> None:
        with patch.dict("os.environ", {"CONTENT_GENERATION_CODEX_API_KEY": "codex-key"}, clear=True):
            self.assertTrue(_provider_is_configured("codex"))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "openai-key"}, clear=True):
            self.assertTrue(_provider_is_configured("codex"))
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_provider_is_configured("codex"))

    def test_gpt5_kwargs_are_normalized_to_max_completion_tokens(self) -> None:
        kwargs = _normalize_chat_completion_kwargs("gpt-5-nano", {"max_tokens": 256, "temperature": 0.2})

        self.assertNotIn("max_tokens", kwargs)
        self.assertEqual(kwargs["max_completion_tokens"], 256)
        self.assertNotIn("temperature", kwargs)


if __name__ == "__main__":
    unittest.main()
