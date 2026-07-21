#!/usr/bin/env python3
"""Run the Mac-local Neo guest response worker.

The worker keeps one process alive, claims one job at a time, and streams the
bounded Ollama response back to Railway. Guest content is never written to
stdout, stderr, or the local automation ledger.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from automation_run_mirror import build_run_payload, mirror_runs  # noqa: E402
from runtime_http import runtime_secret_value, validate_control_plane_url  # noqa: E402


DEFAULT_API = "https://aiclone-production-32dc.up.railway.app"
DEFAULT_OLLAMA = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_KEEP_ALIVE = -1
DEFAULT_MAX_RESPONSE_CHARS = 7_500
MAX_RESPONSE_CHAR_LIMIT = 7_500
DEFAULT_MAX_PREDICT_TOKENS = 160
MIN_PREDICT_TOKENS = 64
MAX_PREDICT_TOKENS = 256
OLLAMA_NUM_CONTEXT = 4_096
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_CHARS = 8_000
DEFAULT_PROGRESS_INTERVAL_SECONDS = 1.0
DEFAULT_LEASE_HEARTBEAT_SECONDS = 15.0
DEFAULT_PRELOAD_RETRY_SECONDS = 15.0
DEFAULT_MAX_PRELOAD_RETRY_SECONDS = 120.0
DEFAULT_COMPLETION_ATTEMPTS = 3
DEFAULT_COMPLETION_RETRY_SECONDS = 0.5
DEFAULT_IDLE_POLL_SECONDS = 0.5
DEFAULT_MAX_IDLE_POLL_SECONDS = 2.0
DEFAULT_ERROR_BACKOFF_SECONDS = 1.0
DEFAULT_MAX_ERROR_BACKOFF_SECONDS = 15.0
AUTOMATION_ID = "neo_guest"
AUTOMATION_NAME = "Neo Guest Conversation Worker"
WORKER_PROTOCOL_VERSION = 2


class SafeWorkerError(RuntimeError):
    """An operational error whose code is safe for metadata-only logging."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class NeoGuestJobError(SafeWorkerError):
    def __init__(self, job_id: str, code: str):
        super().__init__(code)
        self.job_id = job_id


class NeoGuestCompletionAmbiguous(NeoGuestJobError):
    """The answer may be committed remotely, but its acknowledgement was lost."""


def _new_worker_id() -> str:
    """Create a non-identifying claim owner unique to this worker start."""

    return f"neo-guest-{uuid4().hex}"


def _safe_error_code(error: BaseException, fallback: str = "worker_error") -> str:
    if isinstance(error, SafeWorkerError):
        return error.code
    if isinstance(error, requests.Timeout):
        return "request_timeout"
    if isinstance(error, requests.ConnectionError):
        return "connection_error"
    if isinstance(error, requests.HTTPError):
        status = getattr(getattr(error, "response", None), "status_code", None)
        return f"http_{status}" if isinstance(status, int) else "http_error"
    return fallback


def _headers() -> dict[str, str]:
    token = runtime_secret_value("LOCAL_CODEX_BRIDGE_TOKEN") or runtime_secret_value("CRON_ACCESS_TOKEN")
    if not token:
        raise SafeWorkerError("worker_token_missing")
    return {"X-Local-Codex-Token": token, "Content-Type": "application/json", "Accept": "application/json"}


def _post(
    api: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout: float = 30,
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    endpoint = validate_control_plane_url(f"{api.rstrip('/')}{path}")
    client = session or requests
    request_kwargs: dict[str, Any] = {
        "headers": _headers(),
        "timeout": timeout,
        "allow_redirects": False,
    }
    if payload is not None:
        request_kwargs["json"] = payload
    response = client.post(endpoint, **request_kwargs)
    response.raise_for_status()
    try:
        result = response.json()
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SafeWorkerError("control_plane_response_malformed") from exc
    if not isinstance(result, dict):
        raise SafeWorkerError("control_plane_response_malformed")
    return result


def _verify_worker_capabilities(
    api: str,
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fail closed unless Railway advertises the fenced worker protocol.

    This handshake intentionally has no request body. It must complete before
    a claim request so a newer runner cannot strand a job on an older backend.
    """

    result = _post(
        api,
        "/api/neo/worker/capabilities",
        None,
        timeout=15,
        session=session,
    )
    _validate_worker_protocol(result)
    return result


def _validate_worker_protocol(result: dict[str, Any]) -> None:
    """Reject any response that does not prove the fenced v2 contract."""

    if (
        type(result.get("protocol_version")) is not int
        or result["protocol_version"] != WORKER_PROTOCOL_VERSION
        or type(result.get("lease_seconds")) is not int
        or result["lease_seconds"] < 30
        or result.get("claim_token_required") is not True
    ):
        raise SafeWorkerError("worker_protocol_incompatible")


def _post_progress(
    api: str,
    job_id: str,
    claim_token: str,
    partial_response: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 15,
) -> bool:
    """Best-effort progress delivery; never log or echo the partial response."""

    try:
        _post(
            api,
            f"/api/neo/worker/jobs/{job_id}/progress",
            {"worker_id": claim_token, "partial_response": partial_response},
            timeout=timeout,
            session=session,
        )
        return True
    except Exception:
        # A missing/transient progress endpoint must not discard the final answer.
        return False


class _LeaseHeartbeat:
    """Renew one claim lease without ever carrying guest conversation text."""

    def __init__(
        self,
        *,
        api: str,
        job_id: str,
        claim_token: str,
        interval_seconds: float = DEFAULT_LEASE_HEARTBEAT_SECONDS,
    ) -> None:
        self.api = api
        self.job_id = job_id
        self.claim_token = claim_token
        self.interval_seconds = max(0.05, float(interval_seconds))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._session: requests.Session | None = None
        self._next_deadline: float | None = None

    def _renew(self) -> None:
        # An empty partial is metadata-only and leaves any visible draft intact.
        _post_progress(
            self.api,
            self.job_id,
            self.claim_token,
            "",
            session=self._session,
            timeout=min(10.0, max(1.0, self.interval_seconds)),
        )

    def _run(self) -> None:
        deadline = self._next_deadline
        if deadline is None:
            deadline = time.monotonic() + self.interval_seconds
        while True:
            if self._stop_event.wait(max(0.0, deadline - time.monotonic())):
                return
            self._renew()
            deadline += self.interval_seconds
            now = time.monotonic()
            if deadline <= now:
                missed_intervals = int((now - deadline) // self.interval_seconds) + 1
                deadline += missed_intervals * self.interval_seconds
            self._next_deadline = deadline

    def start(self) -> None:
        if self._thread is not None:
            raise SafeWorkerError("lease_heartbeat_already_started")
        self._session = requests.Session()
        # Anchor the cadence before the synchronous renewal. A slow request may
        # consume part of this interval, but it must not move every later
        # heartbeat by its own duration.
        self._next_deadline = time.monotonic() + self.interval_seconds
        # Renew synchronously once so model startup is recorded before the
        # potentially slow first token, then continue independently.
        self._renew()
        self._thread = threading.Thread(
            target=self._run,
            name="neo-guest-lease-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=min(12.0, max(2.0, self.interval_seconds + 1.0)))
        if self._session is not None:
            self._session.close()
            self._session = None


def _validated_ollama_url(value: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise SafeWorkerError("ollama_endpoint_not_loopback")
    return normalized


def _ollama_model() -> str:
    """Resolve model identity solely from this Mac's trusted configuration."""

    model = str(os.getenv("NEO_OLLAMA_MODEL") or "llama3.2:3b").strip()
    if not model or len(model) > 200 or any(character in model for character in "\r\n"):
        raise SafeWorkerError("ollama_model_invalid")
    return model


def _bounded_history(raw_messages: Any) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list):
        return []

    candidates: list[tuple[int, str, str]] = []
    for index, item in enumerate(raw_messages):
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if content:
            candidates.append((index, str(item["role"]), content))
    if not candidates:
        return []

    newest_user = next((item for item in reversed(candidates) if item[1] == "user"), None)
    selected: dict[int, dict[str, str]] = {}
    remaining_chars = MAX_HISTORY_CHARS

    def add(item: tuple[int, str, str]) -> None:
        nonlocal remaining_chars
        index, role, content = item
        if index in selected or remaining_chars <= 0 or len(selected) >= MAX_HISTORY_MESSAGES:
            return
        bounded = content[:remaining_chars]
        if not bounded:
            return
        selected[index] = {"role": role, "content": bounded}
        remaining_chars -= len(bounded)

    # Reserve the history budget for the newest visitor question before adding
    # surrounding context. This remains true even for malformed histories with
    # many assistant messages after the last user message.
    if newest_user is not None:
        add(newest_user)
    for item in reversed(candidates):
        add(item)
        if remaining_chars <= 0 or len(selected) >= MAX_HISTORY_MESSAGES:
            break

    return [selected[index] for index in sorted(selected)]


def _preload_ollama(
    ollama_url: str,
    timeout: int,
    *,
    session: requests.Session | None = None,
    keep_alive: str | int = DEFAULT_OLLAMA_KEEP_ALIVE,
    model: str | None = None,
) -> bool:
    """Best-effort model preload with an empty prompt and no guest context."""

    endpoint = f"{_validated_ollama_url(ollama_url)}/api/generate"
    client = session or requests
    response = None
    try:
        response = client.post(
            endpoint,
            json={
                "model": model or _ollama_model(),
                "prompt": "",
                "stream": False,
                "keep_alive": keep_alive,
                "options": {"num_ctx": OLLAMA_NUM_CONTEXT},
            },
            timeout=timeout,
            allow_redirects=False,
        )
        response.raise_for_status()
        return True
    except Exception:
        return False
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _ollama_answer(
    packet: dict[str, Any],
    ollama_url: str,
    timeout: int,
    *,
    session: requests.Session | None = None,
    keep_alive: str | int = DEFAULT_OLLAMA_KEEP_ALIVE,
    max_response_chars: int = DEFAULT_MAX_RESPONSE_CHARS,
    max_predict_tokens: int = DEFAULT_MAX_PREDICT_TOKENS,
    progress_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
    on_progress: Callable[[str], None] | None = None,
    model: str | None = None,
) -> str:
    if max_response_chars < 1 or max_response_chars > MAX_RESPONSE_CHAR_LIMIT:
        raise SafeWorkerError("ollama_output_limit_invalid")

    approved_public_response = str(packet.get("approved_public_response") or "").strip()
    if approved_public_response:
        if len(approved_public_response) > max_response_chars:
            raise SafeWorkerError("approved_public_response_too_large")
        return approved_public_response

    if not MIN_PREDICT_TOKENS <= max_predict_tokens <= MAX_PREDICT_TOKENS:
        raise SafeWorkerError("ollama_predict_limit_invalid")

    system = str(packet.get("system_prompt") or "").strip()[:12_000]
    profile = str(packet.get("professional_profile") or "").strip()[:24_000]
    messages = [{"role": "system", "content": f"{system}\n\nAPPROVED PROFESSIONAL PROFILE:\n{profile}"}]
    messages.extend(_bounded_history(packet.get("messages")))

    local_model = model or _ollama_model()
    client = session or requests
    response = client.post(
        f"{_validated_ollama_url(ollama_url)}/api/chat",
        json={
            "model": local_model,
            "messages": messages,
            "stream": True,
            "keep_alive": keep_alive,
            "options": {
                "temperature": 0.35,
                "num_ctx": OLLAMA_NUM_CONTEXT,
                "num_predict": max_predict_tokens,
            },
        },
        stream=True,
        timeout=timeout,
        allow_redirects=False,
    )

    fragments: list[str] = []
    response_chars = 0
    truncated = False
    last_progress_at = time.monotonic()
    last_progress_chars = 0
    try:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                raw_line = raw_line.decode("utf-8", errors="strict")
            try:
                payload = json.loads(raw_line)
            except (TypeError, ValueError, UnicodeError) as exc:
                raise SafeWorkerError("ollama_stream_malformed") from exc
            if not isinstance(payload, dict):
                raise SafeWorkerError("ollama_stream_malformed")
            if payload.get("error"):
                raise SafeWorkerError("ollama_stream_error")

            message = payload.get("message")
            content = str(message.get("content") or "") if isinstance(message, dict) else ""
            if content:
                remaining = max_response_chars - response_chars
                if remaining <= 0:
                    truncated = True
                    break
                bounded_fragment = content[:remaining]
                fragments.append(bounded_fragment)
                response_chars += len(bounded_fragment)
                if len(content) > remaining:
                    truncated = True

                now = time.monotonic()
                if (
                    on_progress is not None
                    and response_chars > last_progress_chars
                    and now - last_progress_at >= progress_interval_seconds
                ):
                    on_progress("".join(fragments))
                    last_progress_at = now
                    last_progress_chars = response_chars

                if truncated or response_chars >= max_response_chars:
                    truncated = truncated or not bool(payload.get("done"))
                    break
            if payload.get("done") is True:
                break
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    answer = "".join(fragments).strip()
    if truncated and answer:
        answer = (answer[: max_response_chars - 1].rstrip() + "…") if max_response_chars > 1 else "…"
    if not answer:
        raise SafeWorkerError("ollama_empty_response")
    return answer


def _completion_error_is_ambiguous(error: BaseException) -> bool:
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(error, SafeWorkerError):
        return error.code == "control_plane_response_malformed"
    if isinstance(error, requests.HTTPError):
        status = getattr(getattr(error, "response", None), "status_code", None)
        return isinstance(status, int) and status >= 500
    return False


def _complete_job_idempotently(
    *,
    api: str,
    job_id: str,
    claim_token: str,
    answer: str,
    session: requests.Session | None = None,
    attempts: int = DEFAULT_COMPLETION_ATTEMPTS,
    retry_seconds: float = DEFAULT_COMPLETION_RETRY_SECONDS,
) -> dict[str, Any]:
    """Retry only outcomes where the first completion may have committed."""

    bounded_attempts = max(1, min(5, int(attempts)))
    delay = max(0.05, min(5.0, float(retry_seconds)))
    last_error: BaseException | None = None
    for attempt in range(bounded_attempts):
        try:
            return _post(
                api,
                f"/api/neo/worker/jobs/{job_id}/complete",
                {"worker_id": claim_token, "response": answer},
                session=session,
            )
        except Exception as exc:
            if not _completion_error_is_ambiguous(exc):
                raise
            last_error = exc
            if attempt + 1 < bounded_attempts:
                time.sleep(delay)
                delay = min(5.0, delay * 2)
    raise SafeWorkerError("completion_ack_ambiguous") from last_error


def run_once(
    *,
    api: str,
    ollama_url: str,
    worker_id: str,
    timeout: int,
    control_session: requests.Session | None = None,
    ollama_session: requests.Session | None = None,
    keep_alive: str | int = DEFAULT_OLLAMA_KEEP_ALIVE,
    max_response_chars: int = DEFAULT_MAX_RESPONSE_CHARS,
    max_predict_tokens: int = DEFAULT_MAX_PREDICT_TOKENS,
    progress_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = DEFAULT_LEASE_HEARTBEAT_SECONDS,
    completion_attempts: int = DEFAULT_COMPLETION_ATTEMPTS,
    completion_retry_seconds: float = DEFAULT_COMPLETION_RETRY_SECONDS,
    model: str | None = None,
    protocol_verified: bool = False,
) -> str | None:
    if not protocol_verified:
        _verify_worker_capabilities(api, session=control_session)
    claimed = _post(
        api,
        "/api/neo/worker/v2/jobs/claim-next",
        {"worker_id": worker_id},
        session=control_session,
    )
    # The versioned claim response is the per-cycle compatibility proof. An
    # older backend has no v2 route, while a malformed response is rejected
    # before either an idle result or a job packet is trusted.
    _validate_worker_protocol(claimed)
    if claimed.get("job_available") is False:
        return None
    if claimed.get("job_available") is not True:
        raise SafeWorkerError("claim_response_malformed")
    job = claimed.get("job")
    if not isinstance(job, dict):
        raise SafeWorkerError("claim_response_malformed")
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        raise SafeWorkerError("claimed_job_id_missing")
    claim_token = str(job.get("claim_token") or "").strip()
    if not claim_token:
        raise SafeWorkerError("claimed_job_token_missing")

    heartbeat = _LeaseHeartbeat(
        api=api,
        job_id=job_id,
        claim_token=claim_token,
        interval_seconds=min(
            max(0.05, heartbeat_interval_seconds),
            max(1.0, float(claimed["lease_seconds"]) / 3.0),
        ),
    )
    try:
        heartbeat.start()
        answer = _ollama_answer(
            job.get("context_packet") or {},
            ollama_url,
            timeout,
            session=ollama_session,
            keep_alive=keep_alive,
            max_response_chars=max_response_chars,
            max_predict_tokens=max_predict_tokens,
            progress_interval_seconds=progress_interval_seconds,
            on_progress=lambda partial: _post_progress(
                api,
                job_id,
                claim_token,
                partial,
                session=control_session,
            ),
            model=model,
        )
        try:
            _complete_job_idempotently(
                api=api,
                job_id=job_id,
                claim_token=claim_token,
                answer=answer,
                session=control_session,
                attempts=completion_attempts,
                retry_seconds=completion_retry_seconds,
            )
        except SafeWorkerError as exc:
            if exc.code == "completion_ack_ambiguous":
                raise NeoGuestCompletionAmbiguous(job_id, exc.code) from exc
            raise
    except NeoGuestCompletionAmbiguous:
        # The backend may already have committed this answer. Never overwrite
        # that uncertain terminal state with a failure.
        raise
    except Exception as exc:
        error_code = _safe_error_code(exc, "neo_response_failed")
        try:
            _post(
                api,
                f"/api/neo/worker/jobs/{job_id}/fail",
                {"worker_id": claim_token, "error": f"Local Neo response failed ({error_code})."},
                session=control_session,
            )
        finally:
            raise NeoGuestJobError(job_id, error_code) from exc
    finally:
        heartbeat.stop()
    return job_id


def _record_job_run(*, api: str, job_id: str, started_at: datetime, status: str, error_code: str | None = None) -> bool:
    finished_at = datetime.now(timezone.utc)
    payload = build_run_payload(
        run_id=f"{AUTOMATION_ID}::{uuid4()}",
        automation_id=AUTOMATION_ID,
        automation_name=AUTOMATION_NAME,
        status=status,
        source="local_launchd_registry",
        runtime="launchd",
        delivered=status == "success",
        delivery_channel="neo_guest_job",
        delivery_target=job_id,
        run_at=started_at,
        finished_at=finished_at,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        error=(error_code or "")[:80] or None,
        owner_agent="Neo",
        scope="shared_ops",
        workspace_key="shared_ops",
        action_required=status != "success",
        metadata={
            "job_id": job_id,
            "model_runtime": "local_ollama",
            "streaming": True,
            "contains_guest_content": False,
        },
    )
    # mirror_runs appends locally before making its best-effort Railway request.
    return mirror_runs(validate_control_plane_url(api), [payload])


def _record_safely(*, api: str, job_id: str, started_at: datetime, status: str, error_code: str | None = None) -> bool | None:
    try:
        return _record_job_run(
            api=api,
            job_id=job_id,
            started_at=started_at,
            status=status,
            error_code=error_code,
        )
    except Exception:
        return None


def run_worker(
    *,
    api: str,
    ollama_url: str,
    worker_id: str,
    timeout: int,
    stop_event: threading.Event,
    once: bool = False,
    keep_alive: str | int = DEFAULT_OLLAMA_KEEP_ALIVE,
    max_response_chars: int = DEFAULT_MAX_RESPONSE_CHARS,
    max_predict_tokens: int = DEFAULT_MAX_PREDICT_TOKENS,
    progress_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = DEFAULT_LEASE_HEARTBEAT_SECONDS,
    preload_retry_seconds: float = DEFAULT_PRELOAD_RETRY_SECONDS,
    max_preload_retry_seconds: float = DEFAULT_MAX_PRELOAD_RETRY_SECONDS,
    idle_poll_seconds: float = DEFAULT_IDLE_POLL_SECONDS,
    max_idle_poll_seconds: float = DEFAULT_MAX_IDLE_POLL_SECONDS,
    error_backoff_seconds: float = DEFAULT_ERROR_BACKOFF_SECONDS,
    max_error_backoff_seconds: float = DEFAULT_MAX_ERROR_BACKOFF_SECONDS,
) -> int:
    idle_delay = max(0.05, idle_poll_seconds)
    idle_ceiling = max(idle_delay, max_idle_poll_seconds)
    error_delay = max(0.1, error_backoff_seconds)
    error_ceiling = max(error_delay, max_error_backoff_seconds)
    preload_delay = max(0.1, preload_retry_seconds)
    preload_ceiling = max(preload_delay, max_preload_retry_seconds)
    control_session = requests.Session()
    ollama_session = requests.Session()
    try:
        try:
            capabilities = _verify_worker_capabilities(api, session=control_session)
            local_model = _ollama_model()
        except Exception as exc:
            error_code = _safe_error_code(exc, "worker_protocol_unavailable")
            print(
                f"neo_guest_worker status=unavailable error_code={error_code}",
                file=sys.stderr,
                flush=True,
            )
            return 1
        effective_heartbeat_seconds = min(
            max(0.05, heartbeat_interval_seconds),
            max(1.0, float(capabilities["lease_seconds"]) / 3.0),
        )
        preloaded = _preload_ollama(
            ollama_url,
            timeout,
            session=ollama_session,
            keep_alive=keep_alive,
            model=local_model,
        )
        next_preload_at = time.monotonic() + preload_delay if not preloaded else None
        print(
            "neo_guest_worker status=started preload=" + ("ready" if preloaded else "unavailable"),
            flush=True,
        )
        while not stop_event.is_set():
            started_at = datetime.now(timezone.utc)
            try:
                job_id = run_once(
                    api=api,
                    ollama_url=ollama_url,
                    worker_id=worker_id,
                    timeout=timeout,
                    control_session=control_session,
                    ollama_session=ollama_session,
                    keep_alive=keep_alive,
                    max_response_chars=max_response_chars,
                    max_predict_tokens=max_predict_tokens,
                    progress_interval_seconds=progress_interval_seconds,
                    heartbeat_interval_seconds=effective_heartbeat_seconds,
                    model=local_model,
                    protocol_verified=True,
                )
            except NeoGuestCompletionAmbiguous as exc:
                # The backend may already contain the final answer. Recording
                # either success or failure would invent terminal truth, so the
                # worker emits metadata-only process state and waits for the
                # backend's durable job state to resolve.
                print(
                    f"neo_guest_worker status=completion_unconfirmed error_code={exc.code}",
                    file=sys.stderr,
                    flush=True,
                )
                if once:
                    return 1
                idle_delay = max(0.05, idle_poll_seconds)
                if stop_event.wait(error_delay):
                    break
                error_delay = min(error_ceiling, error_delay * 2)
                continue
            except NeoGuestJobError as exc:
                mirrored = _record_safely(
                    api=api,
                    job_id=exc.job_id,
                    started_at=started_at,
                    status="error",
                    error_code=exc.code,
                )
                print(
                    f"neo_guest_worker status=failed error_code={exc.code} ledger="
                    + ("unavailable" if mirrored is None else "recorded"),
                    file=sys.stderr,
                    flush=True,
                )
                if once:
                    return 1
                idle_delay = max(0.05, idle_poll_seconds)
                if stop_event.wait(error_delay):
                    break
                error_delay = min(error_ceiling, error_delay * 2)
                continue
            except Exception as exc:
                error_code = _safe_error_code(exc, "control_plane_unavailable")
                print(
                    f"neo_guest_worker status=unavailable error_code={error_code}",
                    file=sys.stderr,
                    flush=True,
                )
                if once:
                    return 1
                if stop_event.wait(error_delay):
                    break
                error_delay = min(error_ceiling, error_delay * 2)
                continue

            error_delay = max(0.1, error_backoff_seconds)
            if job_id:
                # A successful generation proves the configured model is now
                # resident even when the earlier empty preload failed.
                preloaded = True
                next_preload_at = None
                mirrored = _record_safely(
                    api=api,
                    job_id=job_id,
                    started_at=started_at,
                    status="success",
                )
                print(
                    "neo_guest_worker status=completed ledger="
                    + ("unavailable" if mirrored is None else "recorded"),
                    flush=True,
                )
                idle_delay = max(0.05, idle_poll_seconds)
                if once:
                    return 0
                # Immediately check for the next job, while still processing serially.
                continue

            if once:
                print("neo_guest_worker status=idle", flush=True)
                return 0

            if not preloaded and next_preload_at is not None:
                now = time.monotonic()
                if now >= next_preload_at:
                    preloaded = _preload_ollama(
                        ollama_url,
                        timeout,
                        session=ollama_session,
                        keep_alive=keep_alive,
                        model=local_model,
                    )
                    if preloaded:
                        next_preload_at = None
                        print("neo_guest_worker status=ready preload=ready", flush=True)
                    else:
                        preload_delay = min(preload_ceiling, preload_delay * 2)
                        next_preload_at = now + preload_delay

            wait_delay = idle_delay
            if not preloaded and next_preload_at is not None:
                wait_delay = min(
                    wait_delay,
                    max(0.05, next_preload_at - time.monotonic()),
                )
            if stop_event.wait(wait_delay):
                break
            idle_delay = min(idle_ceiling, idle_delay * 2)
    finally:
        control_session.close()
        ollama_session.close()

    print("neo_guest_worker status=stopped", flush=True)
    return 0


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _predict_token_limit(value: str) -> int:
    parsed = int(value)
    if not MIN_PREDICT_TOKENS <= parsed <= MAX_PREDICT_TOKENS:
        raise argparse.ArgumentTypeError(
            f"must be between {MIN_PREDICT_TOKENS} and {MAX_PREDICT_TOKENS}"
        )
    return parsed


def _response_char_limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= MAX_RESPONSE_CHAR_LIMIT:
        raise argparse.ArgumentTypeError(
            f"must be between 1 and {MAX_RESPONSE_CHAR_LIMIT}"
        )
    return parsed


def _ollama_keep_alive(value: str) -> str | int:
    normalized = str(value or "").strip().lower()
    if normalized == "-1":
        return -1
    if re.fullmatch(r"[1-9][0-9]*(?:ms|s|m|h)", normalized):
        return normalized
    raise argparse.ArgumentTypeError("must be -1 or a positive duration such as 30m")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=os.getenv("AI_CLONE_API_URL", DEFAULT_API))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA))
    parser.add_argument("--worker-id", default=_new_worker_id())
    parser.add_argument("--timeout", type=_positive_int, default=180)
    parser.add_argument("--once", action="store_true", help="Claim at most one job, then exit.")
    parser.add_argument(
        "--ollama-keep-alive",
        type=_ollama_keep_alive,
        default=os.getenv("NEO_OLLAMA_KEEP_ALIVE", str(DEFAULT_OLLAMA_KEEP_ALIVE)),
    )
    parser.add_argument("--max-response-chars", type=_response_char_limit, default=DEFAULT_MAX_RESPONSE_CHARS)
    parser.add_argument(
        "--max-predict-tokens",
        type=_predict_token_limit,
        default=os.getenv("NEO_MAX_PREDICT_TOKENS", str(DEFAULT_MAX_PREDICT_TOKENS)),
    )
    parser.add_argument("--progress-interval", type=_positive_float, default=DEFAULT_PROGRESS_INTERVAL_SECONDS)
    parser.add_argument(
        "--lease-heartbeat",
        type=_positive_float,
        default=DEFAULT_LEASE_HEARTBEAT_SECONDS,
    )
    parser.add_argument(
        "--preload-retry",
        type=_positive_float,
        default=DEFAULT_PRELOAD_RETRY_SECONDS,
    )
    parser.add_argument(
        "--max-preload-retry",
        type=_positive_float,
        default=DEFAULT_MAX_PRELOAD_RETRY_SECONDS,
    )
    parser.add_argument("--idle-poll", type=_positive_float, default=DEFAULT_IDLE_POLL_SECONDS)
    parser.add_argument("--max-idle-poll", type=_positive_float, default=DEFAULT_MAX_IDLE_POLL_SECONDS)
    parser.add_argument("--error-backoff", type=_positive_float, default=DEFAULT_ERROR_BACKOFF_SECONDS)
    parser.add_argument("--max-error-backoff", type=_positive_float, default=DEFAULT_MAX_ERROR_BACKOFF_SECONDS)
    args = parser.parse_args()

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)
    return run_worker(
        api=args.api_url,
        ollama_url=args.ollama_url,
        worker_id=args.worker_id,
        timeout=args.timeout,
        stop_event=stop_event,
        once=args.once,
        keep_alive=args.ollama_keep_alive,
        max_response_chars=args.max_response_chars,
        max_predict_tokens=args.max_predict_tokens,
        progress_interval_seconds=args.progress_interval,
        heartbeat_interval_seconds=args.lease_heartbeat,
        preload_retry_seconds=args.preload_retry,
        max_preload_retry_seconds=args.max_preload_retry,
        idle_poll_seconds=args.idle_poll,
        max_idle_poll_seconds=args.max_idle_poll,
        error_backoff_seconds=args.error_backoff,
        max_error_backoff_seconds=args.max_error_backoff,
    )


if __name__ == "__main__":
    raise SystemExit(main())
