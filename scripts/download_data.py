#!/usr/bin/env python3
"""Download and unpack the Front2Back-ReID release into data/.

  python scripts/download_data.py                 # -> data/front2back-reid-v1.1/
  python scripts/download_data.py --zip path/to/front2back-reid-v1.1.zip   # use a ZIP you already have
"""
import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = json.loads((ROOT / "front2back" / "resources" / "release.json").read_text())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "data"))
    ap.add_argument("--url", default=RELEASE["url"])
    ap.add_argument("--zip", help="an already-downloaded release ZIP")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    archive = Path(args.zip) if args.zip else out / f"{RELEASE['folder']}.zip"
    if not args.zip:
        print(f"Downloading {args.url}\n  -> {archive}")
        with urllib.request.urlopen(args.url, timeout=600) as r, archive.open("wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
    if not zipfile.is_zipfile(archive):
        sys.exit(f"{archive} is not a ZIP. If the link opened a web page, download the file in a browser and pass --zip.")
    digest = sha256(archive)
    if RELEASE.get("sha256") and digest != RELEASE["sha256"]:
        sys.exit(f"SHA-256 mismatch: got {digest}, expected {RELEASE['sha256']}")
    print(f"SHA-256 {digest}")
    with zipfile.ZipFile(archive) as z:
        z.extractall(out)
    folder = out / RELEASE["folder"]
    print(f"Unpacked to {folder}\nNext: python {folder / 'verify.py'}")


if __name__ == "__main__":
    main()
