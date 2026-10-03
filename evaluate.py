"""Score candidate-ID predictions on the frozen 500-pair Front2Back-ReID test set.

Usage:
  python evaluate.py predictions.jsonl
  python evaluate.py predictions.jsonl --ci            # add a 95% bootstrap interval
  python evaluate.py predictions.jsonl --per-pair out.csv

predictions.jsonl holds one JSON object per line: {"pair_id": "P0001", "candidate_id": "C2"}.
Missing pairs count as incorrect. Unknown pairs, duplicates and candidate IDs that are not
in that pair's gallery are rejected with an error, so a typo can't silently lower a score.
"""
import argparse
import csv
import json
import random
from pathlib import Path


def score(predictions, pairs, answers):
    galleries = {p["pair_id"]: {c["candidate_id"] for c in p["rear"]["candidates"]} for p in pairs}
    truth = {a["pair_id"]: a["correct_candidate_id"] for a in answers}
    seen, correct = set(), 0
    for prediction in predictions:
        pair_id, candidate = prediction["pair_id"], prediction["candidate_id"]
        if pair_id not in truth:
            raise ValueError(f"Unknown pair ID: {pair_id}")
        if pair_id in seen:
            raise ValueError(f"Duplicate prediction: {pair_id}")
        if candidate not in galleries[pair_id]:
            raise ValueError(f"Invalid candidate {candidate} for {pair_id}")
        seen.add(pair_id)
        correct += candidate == truth[pair_id]
    return {"pairs": len(truth), "submitted": len(seen), "missing": len(truth) - len(seen),
            "correct": correct, "top1_accuracy": correct / len(truth)}


def per_pair(predictions, answers):
    pred = {p["pair_id"]: p["candidate_id"] for p in predictions}
    return [(a["pair_id"], pred.get(a["pair_id"]), a["correct_candidate_id"], int(pred.get(a["pair_id"]) == a["correct_candidate_id"])) for a in answers]


def bootstrap_ci(hits, resamples=10000, seed=32025):
    """Percentile bootstrap over pairs. The paper reports BCa intervals (100,000 resamples),
    which can differ from these by a few tenths of a point."""
    rng, n = random.Random(seed), len(hits)
    stats = sorted(sum(hits[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return stats[int(0.025 * resamples)], stats[int(0.975 * resamples) - 1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--ci", action="store_true", help="add a 95%% percentile-bootstrap interval over pairs")
    parser.add_argument("--per-pair", type=Path, metavar="CSV", help="write pair_id, prediction, answer, correct to a CSV file")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent

    def load(file):
        return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]

    predictions = load(args.predictions)
    pairs, answers = load(root / "annotations/pairs.jsonl"), load(root / "annotations/ground_truth.jsonl")
    result = score(predictions, pairs, answers)
    rows = per_pair(predictions, answers)
    if args.ci:
        lo, hi = bootstrap_ci([r[3] for r in rows])
        result["top1_ci95_percentile_bootstrap"] = [round(lo, 4), round(hi, 4)]
    if args.per_pair:
        with args.per_pair.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["pair_id", "candidate_id", "correct_candidate_id", "correct"])
            w.writerows(rows)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
