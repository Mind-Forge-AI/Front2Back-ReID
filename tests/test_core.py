"""Run with: FRONT2BACK_DATA=data/front2back-reid-v1.1 pytest -q"""
import json
import os
from pathlib import Path

import pytest

from front2back import Benchmark, ScoreError, bca_interval, score
from front2back.baselines import Baseline
from front2back.prompts import _js_number, schema_example
from front2back.render import crop_window, model_inputs

DATA = os.environ.get("FRONT2BACK_DATA", "data/front2back-reid-v1.1")
needs_data = pytest.mark.skipif(not Path(DATA, "annotations", "pairs.jsonl").exists(), reason="release not downloaded")


def test_js_number_formatting():
    assert _js_number(0.0) == "0" and _js_number(12.5) == "12.5" and _js_number(0.1111) == "0.1111"


def test_bca_degenerate_and_range():
    assert bca_interval([1] * 10) == (1.0, 1.0)
    lo, hi = bca_interval([1] * 70 + [0] * 30, resamples=5000)
    assert 0.6 < lo < 0.7 < hi < 0.8


@needs_data
def test_benchmark_shape_and_scoring():
    bench = Benchmark(DATA)
    assert len(bench) == 500
    oracle = [{"pair_id": p.pair_id, "candidate_id": bench.answer(p.pair_id)} for p in bench]
    assert score(bench, oracle)["rank1"] == 1.0
    with pytest.raises(ScoreError):
        score(bench, [{"pair_id": "P0001", "candidate_id": "C99"}])


@needs_data
def test_inputs_match_release_crops():
    from PIL import Image

    bench = Benchmark(DATA)
    for pair in bench:
        x1, y1, x2, y2 = crop_window(pair)
        with Image.open(bench.root / pair.raw["inputs"]["front_crop"]) as im:
            assert im.size == (x2 - x1, y2 - y1), pair.pair_id
    labels = [im["label"] for im in model_inputs(bench["P0001"], "front_mask")]
    assert labels == ["front_target_mask", "rear_candidates"]


@needs_data
def test_schema_example_probabilities_sum_to_one():
    bench = Benchmark(DATA)
    for pair in list(bench)[:50]:
        probs = json.loads(schema_example(pair))["candidate_probabilities"]
        assert list(probs) == pair.aliases and abs(sum(probs.values()) - 1) < 1e-9


@needs_data
def test_random_and_hsv_reproduce_paper():
    bench = Benchmark(DATA)
    for name, expected in (("random_gallery", 17.8), ("hsv_histogram", 47.6)):
        engine = Baseline(name)
        res = score(bench, [engine.predict(p) for p in bench])
        assert round(100 * res["rank1"], 1) == expected, name
