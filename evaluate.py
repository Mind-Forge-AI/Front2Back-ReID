"""Score candidate-ID predictions on the frozen 500-pair test set."""
import argparse
import json
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    def load(file):
        return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line]
    result = score(load(args.predictions), load(root / "annotations/pairs.jsonl"), load(root / "annotations/ground_truth.jsonl"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
