#!/usr/bin/env python3
"""Run the paper's crop-based retrieval controls on all 500 pairs.

  python scripts/run_baselines.py --data data/front2back-reid-v1.1 --baseline siglip2_base
  python scripts/run_baselines.py --data data/front2back-reid-v1.1 --baseline all

Writes runs/<baseline>__front_crop__none.jsonl (one prediction per pair) and prints Rank-1
with its 95% BCa interval.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from front2back import Benchmark, score  # noqa: E402
from front2back.baselines import BASELINES, Baseline  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="unzipped front2back-reid-v1.1 folder")
    ap.add_argument("--baseline", default="all", choices=[*BASELINES, "all"])
    ap.add_argument("--out", default="runs")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()
    bench = Benchmark(args.data)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for name in (BASELINES if args.baseline == "all" else [args.baseline]):
        engine = Baseline(name, device=args.device)
        path = Path(args.out) / f"{name}__front_crop__none.jsonl"
        preds = []
        with path.open("w", encoding="utf-8") as f:
            for i, pair in enumerate(bench, 1):
                rec = engine.predict(pair)
                preds.append(rec)
                f.write(json.dumps(rec) + "\n")
                if i % 100 == 0 or i == len(bench):
                    print(f"  {name}: {i}/{len(bench)}", file=sys.stderr)
        res = score(bench, preds, ci=True)
        lo, hi = res["rank1_bca95"]
        print(f"\r{BASELINES[name]:<18} Rank-1 {100 * res['rank1']:.1f} [{100 * lo:.1f}-{100 * hi:.1f}]  -> {path}")


if __name__ == "__main__":
    main()
