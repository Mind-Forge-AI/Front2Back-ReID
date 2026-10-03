"""Google Gemini generateContent (Gemini 2.5 Pro / Flash). Needs GEMINI_API_KEY (or GOOGLE_API_KEY).

Reasoning: "medium" sets thinkingBudget=2048 and maxOutputTokens>=3000. "none" sets the
budget to 0 for Flash; 2.5 Pro can't disable thinking, so it gets the minimum (128).
Replies are constrained to a JSON schema listing every candidate alias.
"""

from __future__ import annotations

import base64
import os
import re
import urllib.parse

from . import ProviderError, http_json, timed

BASE_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")


def response_schema(candidate_ids: list[str]) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "candidate_id": {"type": "STRING"},
            "candidate_probabilities": {"type": "OBJECT", "required": candidate_ids,
                                        "properties": {c: {"type": "NUMBER", "minimum": 0, "maximum": 1} for c in candidate_ids}},
            "distance_m": {"type": "NUMBER", "minimum": 0},
            "confidence": {"type": "NUMBER", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "STRING"},
        },
        "required": ["candidate_id", "candidate_probabilities", "distance_m", "confidence", "reasoning"],
    }


def chat(model_id: str, images: list[dict], text: str, *, temperature: float = 0, max_tokens: int = 1100,
         reasoning_effort: str | None = "none", **_: object) -> dict:
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise ProviderError("GEMINI_API_KEY is not set.")
    effort = reasoning_effort or "none"
    ids = sorted({m.upper() for m in re.findall(r"\bC\d+\b", text, re.IGNORECASE)}, key=lambda v: int(v[1:]))
    parts = [{"inlineData": {"mimeType": im["mime"], "data": base64.b64encode(im["bytes"]).decode("ascii")}} for im in images]
    parts.append({"text": text})
    config = {
        "temperature": temperature,
        "maxOutputTokens": max(max_tokens, 3000) if effort == "medium" else max_tokens,
        "responseMimeType": "application/json",
        "responseSchema": response_schema(ids),
        "thinkingConfig": {"thinkingBudget": 2048 if effort == "medium" else (128 if "pro" in model_id else 0), "includeThoughts": False},
    }
    url = f"{BASE_URL}/models/{model_id}:generateContent?{urllib.parse.urlencode({'key': key})}"
    raw, ms = timed(lambda: http_json("POST", url, {}, {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}, 180, "Gemini"))
    cands = raw.get("candidates") or []
    parts_out = ((cands[0] or {}).get("content") or {}).get("parts") or [] if cands else []
    text_out = "\n".join(p["text"] for p in parts_out if isinstance(p, dict) and isinstance(p.get("text"), str))
    if not text_out.strip():
        finish = (raw.get("candidates") or [{}])[0].get("finishReason") if raw.get("candidates") else None
        raise ProviderError(f"Gemini returned no answer text (finishReason={finish!r}).", retryable=True)
    return {"text": text_out, "latency_ms": ms, "usage": raw.get("usageMetadata", {}), "raw": raw}
