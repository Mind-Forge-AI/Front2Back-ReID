#!/usr/bin/env python3
"""Score a predictions file: one {"pair_id": "P0001", "candidate_id": "C2"} per line.

  python scripts/evaluate.py --data data/front2back-reid-v1.1 predictions.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from front2back import Benchmark, ScoreError, score  # noqa: E402
from front2back.scoring import load_predictions  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--data", required=True)
ap.add_argument("predictions")
args = ap.parse_args()
try:
    res = score(Benchmark(args.data), load_predictions(args.predictions), ci=True)
except ScoreError as exc:
    sys.exit(f"error: {exc}")
lo, hi = res.pop("rank1_bca95")
res["rank1_bca95"] = [round(lo, 4), round(hi, 4)]
print(json.dumps(res, indent=2))
