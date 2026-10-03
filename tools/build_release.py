#!/usr/bin/env python3
"""Build front2back-reid-v1.1.zip from a local copy of the dataset (maintainers).

  python tools/build_release.py --dataset path/to/dataset --out release/

--dataset must contain annotations/, data/, inputs/, splits/ and dataset_stats.json.
The ZIP gets those plus release_files/ (README, evaluate.py, verify.py), LICENSE,
CITATION.cff and a fresh checksums.sha256, under a top-level front2back-reid-v1.1/ folder.
"""
import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "front2back-reid-v1.1"
DATASET_ITEMS = ["annotations", "data", "inputs", "splits", "dataset_stats.json"]
EXTRA = {"README.md": ROOT / "release_files/README.md", "evaluate.py": ROOT / "release_files/evaluate.py",
         "verify.py": ROOT / "release_files/verify.py", "LICENSE": ROOT / "LICENSE", "CITATION.cff": ROOT / "CITATION.cff"}


def files(dataset: Path):
    out = {}
    for item in DATASET_ITEMS:
        p = dataset / item
        for f in ([p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())):
            out[f.relative_to(dataset).as_posix()] = f
    out.update(EXTRA)
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--out", default=ROOT / "release", type=Path)
    args = ap.parse_args()
    entries = files(args.dataset)
    checksums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}\n" for rel, p in entries.items())
    args.out.mkdir(parents=True, exist_ok=True)
    zpath = args.out / f"{FOLDER}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, p in entries.items():
            z.write(p, f"{FOLDER}/{rel}", compress_type=zipfile.ZIP_STORED if p.suffix.lower() in (".jpg", ".png") else zipfile.ZIP_DEFLATED)
        z.writestr(f"{FOLDER}/checksums.sha256", checksums)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    (args.out / f"{FOLDER}.zip.sha256").write_text(f"{digest}  {FOLDER}.zip\n")
    print(f"{zpath}  {zpath.stat().st_size / 1e6:.1f} MB  sha256 {digest}")


if __name__ == "__main__":
    main()
