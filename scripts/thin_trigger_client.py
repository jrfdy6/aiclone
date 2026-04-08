#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")


class ThinTriggerError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def build_api_url(api_url: str, path: str) -> str:
    return f"{api_url.rstrip('/')}/{path.lstrip('/')}"


def request_json(
    api_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        build_api_url(api_url, path),
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_detail = json.loads(detail)
        except json.JSONDecodeError:
            parsed_detail = detail
        raise ThinTriggerError(
            f"HTTP {exc.code} calling {path}",
            status_code=exc.code,
            detail=parsed_detail,
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ThinTriggerError(str(exc)) from exc

    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThinTriggerError(f"Non-JSON response calling {path}: {raw[:200]}") from exc
