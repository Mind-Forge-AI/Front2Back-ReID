#!/usr/bin/env python3
"""Rebuild the paper's Tables 3-4 from per-pair prediction files.

  python scripts/make_tables.py --data data/front2back-reid-v1.1 --runs runs
  python scripts/make_tables.py --data data/front2back-reid-v1.1 --runs runs --latex tables.tex

Reads every runs/<model>__<condition>__<reasoning>.jsonl with all 500 pairs answered,
computes Rank-1 with 95% BCa intervals (100,000 resamples, seed 32025), the context gap
(full RGB - crop) and paired reasoning gains, and compares each cell with the paper.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from front2back import Benchmark  # noqa: E402
from front2back.baselines import BASELINES  # noqa: E402
from front2back.data import CONDITION_LABELS, CONDITIONS  # noqa: E402
from front2back.scoring import hits, load_predictions  # noqa: E402
from front2back.stats import bca_interval, paired_bca_interval  # noqa: E402
from front2back.vlm import MODELS  # noqa: E402

PAPER = json.loads((Path(__file__).resolve().parents[1] / "front2back" / "resources" / "paper_results.json").read_text())
LABELS = {**BASELINES, **{k: m.label for k, m in MODELS.items()}}
ORDER = [*BASELINES, "llava_onevision_0_5b", "llama4_scout_groq", "qwen3_6_27b_groq", "gpt5_5", "gpt5_4_mini", "gemini_2_5_pro", "gemini_2_5_flash"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--json", help="write all numbers to this JSON file")
    ap.add_argument("--latex", help="write LaTeX table rows to this file")
    ap.add_argument("--resamples", type=int, default=100_000)
    args = ap.parse_args()
    bench = Benchmark(args.data)
    cells = {}
    for path in sorted(Path(args.runs).glob("*__*__*.jsonl")):
        model, cond, eff = path.stem.split("__")
        preds = load_predictions(path)
        if len({p["pair_id"] for p in preds if p.get("status", "parsed") != "provider_error"}) < len(bench):
            print(f"skip {path.name}: incomplete run", file=sys.stderr)
            continue
        h = hits(bench, [p for p in preds if p.get("status", "parsed") != "provider_error"])
        x = [h[pid] for pid in bench.pairs]
        lo, hi = bca_interval(x, resamples=args.resamples)
        cells[(model, cond, eff)] = {"hits": x, "acc": 100 * sum(x) / len(x), "lo": 100 * lo, "hi": 100 * hi}
    if not cells:
        sys.exit(f"no complete runs found in {args.runs}")

    out, latex = {"cells": {}, "reasoning_effects": [], "paired": {}}, []
    for eff in ("none", "medium"):
        rows = [m for m in ORDER if any((m, c, eff) in cells or (eff == "medium" and (m, c, "none") in cells and m in BASELINES) for c in CONDITIONS)]
        rows = [m for m in rows if any((m, c, eff) in cells for c in CONDITIONS)]
        if not rows:
            continue
        print(f"\n{'Table 3' if eff == 'none' else 'Table 4'}: Rank-1 (%), reasoning {'disabled' if eff == 'none' else 'medium effort'}")
        print(f"{'Method':<22}" + "".join(f"{CONDITION_LABELS[c]:>24}" for c in CONDITIONS) + f"{'Δctx':>8}   paper check")
        for m in rows:
            line, tex, checks = f"{LABELS.get(m, m):<22}", [LABELS.get(m, m)], []
            for c in CONDITIONS:
                v = cells.get((m, c, eff))
                if not v:
                    line += f"{'–':>24}"; tex.append("–"); continue
                line += f"{v['acc']:>8.1f} [{v['lo']:.1f}–{v['hi']:.1f}]".rjust(24)
                tex.append(f"{v['acc']:.1f} {{\\scriptsize[{v['lo']:.1f}–{v['hi']:.1f}]}}")
                ref = PAPER["cells"].get(f"{m}__{c}__{eff}")
                if ref:
                    checks.append("ok" if abs(ref["acc"] - round(v["acc"], 1)) < 0.05 else f"{CONDITION_LABELS[c]} paper {ref['acc']}")
                out["cells"][f"{m}__{c}__{eff}"] = {k: round(v[k], 2) for k in ("acc", "lo", "hi")}
            full, crop = cells.get((m, "rgb_full", eff)), cells.get((m, "front_crop", eff))
            ctx = f"{full['acc'] - crop['acc']:+.1f}" if full and crop else "–"
            print(line + f"{ctx:>8}   " + (", ".join(sorted(set(checks))) or "no paper value"))
            latex.append(" & ".join([*tex, ctx]) + r" \\")
    print("\nPaired reasoning gains (medium - disabled, points, 95% BCa)")
    for (m, c, eff), v in sorted(cells.items()):
        base = cells.get((m, c, "none"))
        if eff == "medium" and base:
            d, (lo, hi) = paired_bca_interval(v["hits"], base["hits"], resamples=args.resamples)
            print(f"  {LABELS.get(m, m):<18} {CONDITION_LABELS[c]:<12} {100 * d:+5.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]")
            out["reasoning_effects"].append({"model": m, "condition": c, "delta": round(100 * d, 2), "lo": round(100 * lo, 2), "hi": round(100 * hi, 2)})
    a, b = cells.get(("gpt5_5", "front_crop", "medium")), cells.get(("siglip2_base", "front_crop", "none"))
    if a and b:
        d, (lo, hi) = paired_bca_interval(a["hits"], b["hits"], resamples=args.resamples)
        print(f"\nGPT-5.5 (R) vs SigLIP2 on crops: {100 * d:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]  (paper +2.6 [-2.2, 7.4])")
        out["paired"]["gpt5_5_medium_vs_siglip2_crop"] = {"delta": round(100 * d, 2), "lo": round(100 * lo, 2), "hi": round(100 * hi, 2)}
    print("\nPoint estimates should match the paper exactly. BCa bounds can differ by about"
          " 0.2 points (one pair) because the original resampling stream wasn't archived.")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1))
    if args.latex:
        Path(args.latex).write_text("\n".join(latex) + "\n")


if __name__ == "__main__":
    main()
