"""Validate the public Front2Back-ReID release."""
import hashlib, json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()
# Files that live only in a Git checkout or local working copy, never in the release ZIP.
LOCAL = {"checksums.sha256", ".gitignore", "site/_testbundle.zip"}
def is_local(rel):
    parts = rel.parts
    return rel.as_posix() in LOCAL or parts[0] in {".git", "release", "__pycache__"} or "__pycache__" in parts
def main():
    listed = {path: digest for digest, path in (line.split("  ", 1) for line in (ROOT / "checksums.sha256").read_text().splitlines())}
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and not is_local(p.relative_to(ROOT))}
    assert actual == set(listed), "checksum inventory differs from package"
    for path, digest in listed.items(): assert sha(ROOT / path) == digest, f"hash mismatch: {path}"
    pairs = [json.loads(line) for line in (ROOT / "annotations/pairs.jsonl").read_text().splitlines()]
    answers = {x["pair_id"]: x for x in map(json.loads, (ROOT / "annotations/ground_truth.jsonl").read_text().splitlines())}
    assert len(pairs) == len(answers) == 500
    for pair in pairs:
        assert pair["pair_id"] in answers
        assert answers[pair["pair_id"]]["correct_candidate_id"] in [c["candidate_id"] for c in pair["rear"]["candidates"]]
        for path in (pair["front"]["image"], pair["rear"]["image"], pair["front"]["target_mask"], *pair["inputs"].values()):
            with Image.open(ROOT / path) as image: image.load()
    print("PASS: 500 pairs, answers, media files, and checksums verified.")
if __name__ == "__main__": main()
