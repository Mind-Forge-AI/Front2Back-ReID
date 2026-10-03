"""Zero-shot VLM evaluation, matching the paper's request settings.

Every request: one user message with the front image, then the labelled rear gallery,
then the text; temperature 0; max tokens 1100 for reasoning-capable models and 700
otherwise; image detail "high" (OpenAI). Reasoning-capable models take
reasoning_effort "none" or "medium"; the others are always run with reasoning off.
"""

from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass

from .data import Pair
from .prompts import build_prompt, build_user_text
from .providers import ProviderError, parse_json_object
from .render import model_inputs


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    provider: str          # openai | google | groq | llava
    model_id: str
    reasoning: bool        # accepts a reasoning_effort setting
    efforts: tuple[str, ...]  # efforts evaluated in the paper


MODELS = {m.key: m for m in [
    ModelSpec("gpt5_5", "GPT-5.5", "openai", os.environ.get("OPENAI_GPT55_MODEL", "gpt-5.5"), True, ("none", "medium")),
    ModelSpec("gpt5_4_mini", "GPT-5.4 mini", "openai", os.environ.get("OPENAI_GPT54_MINI_MODEL", "gpt-5.4-mini"), True, ("none", "medium")),
    ModelSpec("gemini_2_5_pro", "Gemini 2.5 Pro", "google", os.environ.get("GEMINI_PRO_MODEL", "gemini-2.5-pro"), True, ("medium",)),
    ModelSpec("gemini_2_5_flash", "Gemini 2.5 Flash", "google", os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.5-flash"), True, ("none", "medium")),
    ModelSpec("qwen3_6_27b_groq", "Qwen 3.6 27B", "groq", os.environ.get("GROQ_QWEN_MODEL", "qwen/qwen3.6-27b"), True, ("none",)),
    ModelSpec("llama4_scout_groq", "Llama 4 Scout", "groq", os.environ.get("GROQ_LLAMA_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"), False, ("none",)),
    ModelSpec("llava_onevision_0_5b", "LLaVA-OneVision 0.5B", "llava", os.environ.get("LLAVA_ONEVISION_MODEL", "llava-hf/llava-onevision-qwen2-0.5b-ov-hf"), False, ("none",)),
]}
PROVIDER_MODULES = {"openai": "openai", "google": "gemini", "groq": "groq", "llava": "llava"}


def request_settings(spec: ModelSpec, effort: str) -> dict:
    effort = effort if spec.reasoning else "none"
    settings = {"temperature": 0, "max_tokens": 1100 if spec.reasoning else 700, "image_detail": "high"}
    if spec.provider == "openai":
        settings["reasoning_effort"] = effort
    elif spec.reasoning:
        settings.update(reasoning_effort=effort, include_reasoning=False)
    return settings


def normalize(parsed: dict | None) -> dict:
    parsed = parsed or {}
    probs = parsed.get("candidate_probabilities") if isinstance(parsed.get("candidate_probabilities"), dict) else {}
    clean = {}
    for k, v in probs.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f:
            clean[str(k)] = f
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return {
        "candidate_id": parsed.get("candidate_id").strip() if isinstance(parsed.get("candidate_id"), str) else None,
        "candidate_probabilities": clean,
        "distance_m": num(parsed.get("distance_m")),
        "confidence": num(parsed.get("confidence")),
        "reasoning": parsed.get("reasoning") if isinstance(parsed.get("reasoning"), str) else "",
    }


def map_alias(candidate_id: str | None, pair: Pair) -> str | None:
    if not candidate_id:
        return None
    lookup = {a.lower(): a for a in pair.aliases}
    return lookup.get(candidate_id.strip().lower())


def run_pair(spec: ModelSpec, pair: Pair, condition: str, effort: str = "none", *, retries: int = 4, keep_raw: bool = False) -> dict:
    """Query one model on one pair. Provider failures are retried; after the last
    retry the record has ``status: "provider_error"`` and should be re-run (the paper
    only reports complete N=500 runs)."""
    images = model_inputs(pair, condition)
    prompt = build_prompt(pair, condition)
    text = build_user_text(prompt, [im["label"] for im in images])
    settings = request_settings(spec, effort)
    module = importlib.import_module(f"front2back.providers.{PROVIDER_MODULES[spec.provider]}")
    record = {"pair_id": pair.pair_id, "model": spec.key, "model_id": spec.model_id, "condition": condition,
              "reasoning_effort": effort if spec.reasoning else "none", "settings": settings}
    for attempt in range(retries + 1):
        try:
            reply = module.chat(spec.model_id, images, text, **settings)
            break
        except ProviderError as exc:
            if not exc.retryable or attempt == retries:
                return {**record, "status": "provider_error", "error": str(exc), "candidate_id": None}
            time.sleep(min(60, 2 ** attempt * 3))
    parsed = normalize(parse_json_object(reply["text"]))
    alias = map_alias(parsed["candidate_id"], pair)
    record.update(status="parsed" if alias else "unparsed", candidate_id=alias, raw_candidate_id=parsed["candidate_id"],
                  candidate_probabilities=parsed["candidate_probabilities"], confidence=parsed["confidence"],
                  reasoning=parsed["reasoning"], distance_m=parsed["distance_m"], text=reply["text"],
                  latency_ms=reply["latency_ms"], usage=reply.get("usage", {}))
    if keep_raw:
        record["raw"] = reply.get("raw")
    return record
