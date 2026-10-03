"""Validate an unzipped Front2Back-ReID release (needs Pillow)."""
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    listed = {p: d for d, p in (line.split("  ", 1) for line in (ROOT / "checksums.sha256").read_text().splitlines())}
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.name != "checksums.sha256" and "__pycache__" not in p.parts}
    missing, extra = set(listed) - actual, actual - set(listed)
    assert not missing, f"missing files: {sorted(missing)[:5]}"
    assert not extra, f"unexpected files: {sorted(extra)[:5]}"
    for path, digest in listed.items():
        assert sha(ROOT / path) == digest, f"hash mismatch: {path}"
    pairs = [json.loads(line) for line in (ROOT / "annotations/pairs.jsonl").read_text().splitlines()]
    answers = {x["pair_id"]: x for x in map(json.loads, (ROOT / "annotations/ground_truth.jsonl").read_text().splitlines())}
    split = (ROOT / "splits/test500.txt").read_text().split()
    assert len(pairs) == len(answers) == len(split) == 500 and split == [p["pair_id"] for p in pairs]
    for pair in pairs:
        assert answers[pair["pair_id"]]["correct_candidate_id"] in [c["candidate_id"] for c in pair["rear"]["candidates"]]
        for path in (pair["front"]["image"], pair["rear"]["image"], pair["front"]["target_mask"], *pair["inputs"].values()):
            with Image.open(ROOT / path) as image:
                image.load()
    print("PASS: 500 pairs, answers, media files, and checksums verified.")


if __name__ == "__main__":
    main()
