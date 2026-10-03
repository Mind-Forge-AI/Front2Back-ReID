"""OpenAI Responses API (GPT-5.5, GPT-5.4 mini). Needs OPENAI_API_KEY."""

from __future__ import annotations

import os

from . import ProviderError, data_url, http_json, timed

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def chat(model_id: str, images: list[dict], text: str, *, temperature: float = 0, max_tokens: int = 700,
         reasoning_effort: str | None = None, image_detail: str = "high", **_: object) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ProviderError("OPENAI_API_KEY is not set.")
    content = [{"type": "input_image", "image_url": data_url(im), "detail": image_detail} for im in images]
    content.append({"type": "input_text", "text": text})
    body = {"model": model_id, "input": [{"role": "user", "content": content}],
            "temperature": temperature, "max_output_tokens": max_tokens}
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    raw, ms = timed(lambda: http_json("POST", f"{BASE_URL}/responses", {"Authorization": f"Bearer {key}"}, body, 180, "OpenAI"))
    return {"text": _text(raw), "latency_ms": ms, "usage": raw.get("usage", {}), "raw": raw}


def _text(raw: dict) -> str:
    if isinstance(raw.get("output_text"), str):
        return raw["output_text"]
    chunks = []
    for item in raw.get("output") or []:
        for part in (item or {}).get("content") or []:
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "\n".join(chunks)
