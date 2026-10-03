#!/usr/bin/env python3
"""Evaluate a zero-shot VLM on Front2Back-ReID with the paper's protocol.

  export OPENAI_API_KEY=...            # or GEMINI_API_KEY / GROQ_API_KEY
  python scripts/run_vlm.py --data data/front2back-reid-v1.1 --model gpt5_5 --condition front_crop --reasoning medium

  # every cell the paper reports for one model
  python scripts/run_vlm.py --data data/front2back-reid-v1.1 --model gemini_2_5_flash --all

  # check the exact request without calling an API
  python scripts/run_vlm.py --data data/front2back-reid-v1.1 --model gpt5_5 --condition rgb_full --dry-run P0001

Output: runs/<model>__<condition>__<reasoning>.jsonl, one record per pair. Re-running the
same command resumes: pairs that already have a parsed/unparsed answer are skipped and
provider errors are retried. A cell is complete when all 500 pairs have an answer.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from front2back import CONDITIONS, Benchmark, score  # noqa: E402
from front2back.prompts import build_prompt, build_user_text  # noqa: E402
from front2back.render import model_inputs  # noqa: E402
from front2back.vlm import MODELS, request_settings, run_pair  # noqa: E402


def run_cell(bench, spec, condition, effort, out_dir, workers):
    path = Path(out_dir) / f"{spec.key}__{condition}__{effort}.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("status") in ("parsed", "unparsed"):
                done[rec["pair_id"]] = rec
    todo = [p for p in bench if p.pair_id not in done]
    print(f"{spec.label} · {condition} · reasoning={effort}: {len(done)} done, {len(todo)} to run -> {path}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, rec in enumerate(pool.map(lambda p: run_pair(spec, p, condition, effort), todo), 1):
            if rec["status"] != "provider_error":
                done[rec["pair_id"]] = rec
            else:
                print(f"  {rec['pair_id']}: {rec['error'][:160]}", file=sys.stderr)
            if i % 25 == 0 or i == len(todo):
                print(f"  {len(done)}/{len(bench)}", file=sys.stderr)
                path.write_text("".join(json.dumps(done[p.pair_id]) + "\n" for p in bench if p.pair_id in done), encoding="utf-8")
    path.write_text("".join(json.dumps(done[p.pair_id]) + "\n" for p in bench if p.pair_id in done), encoding="utf-8")
    if len(done) < len(bench):
        print(f"  incomplete: {len(bench) - len(done)} pairs still need an answer; re-run to resume.")
        return
    res = score(bench, done.values(), ci=True)
    lo, hi = res["rank1_bca95"]
    unparsed = sum(r["status"] == "unparsed" for r in done.values())
    print(f"  Rank-1 {100 * res['rank1']:.1f} [{100 * lo:.1f}-{100 * hi:.1f}]  (unparsed counted wrong: {unparsed})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--condition", choices=CONDITIONS)
    ap.add_argument("--reasoning", default="none", choices=["none", "medium"])
    ap.add_argument("--all", action="store_true", help="run every condition x reasoning setting reported in the paper")
    ap.add_argument("--workers", type=int, default=4, help="parallel requests (respect your rate limits)")
    ap.add_argument("--out", default="runs")
    ap.add_argument("--dry-run", metavar="PAIR_ID", help="print the request for one pair and save its images to runs/dry_run/")
    args = ap.parse_args()
    bench, spec = Benchmark(args.data), MODELS[args.model]
    if args.dry_run:
        pair, cond = bench[args.dry_run], args.condition or "rgb_full"
        images = model_inputs(pair, cond)
        out = Path(args.out) / "dry_run"; out.mkdir(parents=True, exist_ok=True)
        for i, im in enumerate(images, 1):
            (out / f"{pair.pair_id}_{i}_{im['label']}.{'png' if im['mime'] == 'image/png' else 'jpg'}").write_bytes(im["bytes"])
        print(json.dumps({"model": spec.model_id, "settings": request_settings(spec, args.reasoning), "images": [im["label"] for im in images]}, indent=2))
        print(build_user_text(build_prompt(pair, cond), [im["label"] for im in images]))
        return
    Path(args.out).mkdir(parents=True, exist_ok=True)
    cells = [(c, e) for c in CONDITIONS for e in spec.efforts] if args.all else [(args.condition or sys.exit("--condition or --all required"), args.reasoning)]
    for cond, effort in cells:
        run_cell(bench, spec, cond, effort, args.out, args.workers)


if __name__ == "__main__":
    main()
