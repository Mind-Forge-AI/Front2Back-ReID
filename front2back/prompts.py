"""Prompts used for the zero-shot VLM evaluation (prompt version model_eval_prompt.v3).

`build_prompt` reproduces the text sent with every request: the condition template,
the candidate list, and the structured-output contract. The templates ship in
resources/prompt_templates.json. If `tools/export_paper_runs.py` has been run against
the evaluation database, resources/paper_prompts.json holds the exact stored templates
and takes precedence.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .data import Pair

RESOURCES = Path(__file__).with_name("resources")
ROAD_LABELS = {"highway": "Highway", "suburban": "Suburban", "urban": "Urban", "rural": "Rural", "construction_zone": "Construction Zone"}
CONDITION_CONTEXT = (
    "Use the provided images. The front target box is visually labeled T, and candidate boxes in the rear image "
    "are visually labeled C1, C2, etc. No candidate coordinates, detector class labels, or detector confidence "
    "scores are provided in text."
)
CONTRACT_RULES = [
    "candidate_id must exactly match one listed candidate ID.",
    "candidate_probabilities must include every candidate ID exactly once.",
    "candidate_probabilities values must be numbers between 0 and 1 and sum to 1.",
    "Return only the JSON object. Do not include markdown, preamble, <think> tags, or hidden reasoning text.",
    "Do not mention detector class labels or detector confidence scores in the reasoning.",
]


@lru_cache(maxsize=1)
def templates() -> dict[str, str]:
    exact = RESOURCES / "paper_prompts.json"
    source = exact if exact.exists() else RESOURCES / "prompt_templates.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    return data["templates"]


def _js_number(x: float) -> str:
    """Format a number the way JavaScript's JSON.stringify does."""
    if float(x).is_integer():
        return str(int(x))
    return repr(float(x))


def _js_fixed(x: float, digits: int = 4) -> float:
    return float(f"{x:.{digits}f}")


def schema_example(pair: Pair) -> str:
    aliases = pair.aliases
    n = len(aliases)
    u = _js_fixed(1 / n) if n else 1.0
    probs = [u] * (n - 1) + [_js_fixed(1 - u * (n - 1))] if n else []
    prob_text = ",".join(f'"{a}":{_js_number(p)}' for a, p in zip(aliases, probs))
    first = aliases[0] if aliases else "C1"
    return (
        f'{{"candidate_id":"{first}","candidate_probabilities":{{{prob_text}}},'
        f'"distance_m":12.5,"confidence":0,"reasoning":"short visual reason"}}'
    )


def build_prompt(pair: Pair, condition: str, template: str | None = None) -> str:
    template = (template or templates()[condition]).strip()
    filled = (template.replace("{condition_context}", CONDITION_CONTEXT)
              .replace("{road_context_label}", ROAD_LABELS.get(pair.road_context, pair.road_context))
              .replace("{candidates}", ", ".join(pair.aliases)))
    return "\n".join([filled, "", "Required JSON schema:", schema_example(pair), *CONTRACT_RULES])


def build_user_text(prompt: str, image_labels: list[str]) -> str:
    """The text part of the single user message (image captions, blank line, prompt)."""
    return "\n".join([*(f"Image {i + 1}: {label}" for i, label in enumerate(image_labels)), "", prompt])
