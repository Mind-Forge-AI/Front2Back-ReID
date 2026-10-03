"""Groq chat completions (Llama 4 Scout, Qwen 3.6 27B). Needs GROQ_API_KEY.

Images are sent as OpenAI-style data-URL parts. For reasoning-capable models the
harness passes ``reasoning_effort`` ("none"/"medium") and ``include_reasoning=False``.
"""

from __future__ import annotations

import os

from . import ProviderError, data_url, http_json, timed

BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")


def chat(model_id: str, images: list[dict], text: str, *, temperature: float = 0, max_tokens: int = 700,
         reasoning_effort: str | None = None, include_reasoning: bool | None = None, **_: object) -> dict:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ProviderError("GROQ_API_KEY is not set.")
    content = [{"type": "image_url", "image_url": {"url": data_url(im)}} for im in images]
    content.append({"type": "text", "text": text})
    body = {"model": model_id, "messages": [{"role": "user", "content": content}], "temperature": temperature, "max_tokens": max_tokens}
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    if include_reasoning is not None:
        body["include_reasoning"] = include_reasoning
    raw, ms = timed(lambda: http_json("POST", f"{BASE_URL}/chat/completions", {"Authorization": f"Bearer {key}"}, body, 120, "Groq"))
    choices = raw.get("choices") or []
    msg = (choices[0] or {}).get("message") or {} if choices else {}
    text_out = msg.get("content") if isinstance(msg.get("content"), str) else ""
    return {"text": text_out, "latency_ms": ms, "usage": raw.get("usage", {}), "raw": raw}
