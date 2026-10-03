"""Thin, dependency-free API adapters (OpenAI, Google Gemini, Groq) plus a local
LLaVA-OneVision runner. Each exposes ``chat(model_id, images, text, **settings)`` and
returns ``{"text", "latency_ms", "usage", "raw"}``.

``images`` is a list of ``{"mime", "bytes"}``; images are sent before the text, as in the
paper's runs.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    """A request failed. ``retryable`` marks rate limits, timeouts and 5xx errors."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def data_url(image: dict) -> str:
    return f"data:{image['mime']};base64,{base64.b64encode(image['bytes']).decode('ascii')}"


def http_json(method: str, url: str, headers: dict, body: dict | None, timeout: int, name: str) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "Front2Back-ReID/1.1", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise ProviderError(f"{name} HTTP {exc.code}: {detail}", retryable=exc.code in (408, 409, 429) or exc.code >= 500) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise ProviderError(f"{name} request failed: {exc}", retryable=True) from exc


def timed(fn):
    start = time.perf_counter()
    out = fn()
    return out, int((time.perf_counter() - start) * 1000)


def parse_json_object(text: str) -> dict | None:
    """Extract the first {...} object from a model reply (tolerates ``` fences)."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    if stripped.startswith("```"):
        stripped = stripped.strip("`").removeprefix("json").strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
