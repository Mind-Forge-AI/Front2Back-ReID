"""Rank-1 scoring on the frozen 500-pair set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .data import Benchmark


class ScoreError(ValueError):
    pass


def load_predictions(path: str | Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def hits(bench: Benchmark, predictions: Iterable[dict], *, strict: bool = True) -> dict[str, int]:
    """Per-pair 1/0 correctness for every pair in the benchmark (missing -> 0).

    strict=True rejects unknown pairs, duplicates and aliases outside the pair's gallery.
    Records with ``candidate_id: null`` (unparsed model output) count as wrong.
    """
    seen: dict[str, int] = {}
    for p in predictions:
        pid, cand = p.get("pair_id"), p.get("candidate_id")
        if pid not in bench.pairs:
            raise ScoreError(f"Unknown pair ID: {pid}")
        if pid in seen:
            raise ScoreError(f"Duplicate prediction: {pid}")
        if cand is not None and cand not in bench[pid].aliases and strict:
            raise ScoreError(f"Invalid candidate {cand} for {pid}")
        seen[pid] = int(cand == bench.answer(pid))
    return {pid: seen.get(pid, 0) for pid in bench.pairs}


def score(bench: Benchmark, predictions: Iterable[dict], *, ci: bool = False) -> dict:
    predictions = list(predictions)
    h = hits(bench, predictions)
    submitted = {p["pair_id"] for p in predictions}
    out = {"pairs": len(h), "submitted": len(submitted), "missing": len(h) - len(submitted),
           "correct": sum(h.values()), "rank1": sum(h.values()) / len(h)}
    if ci:
        from .stats import bca_interval

        out["rank1_bca95"] = bca_interval(list(h.values()))
    return out
