# Front2Back-ReID

**Front-to-Back: Benchmarking Vision-Language Models for Asymmetric Cross-View Vehicle Re-Identification**
Moseli Mots'oehli¹˒², Thulani Babeli¹ · ¹MindForge AI, Johannesburg · ²University of Hawai'i at Mānoa
[Paper (arXiv:2609.39492)](https://arxiv.org/abs/2609.39492) · [Project page](https://mind-forge-ai.github.io/Front2Back-ReID/) · [Code and data](https://github.com/Mind-Forge-AI/Front2Back-ReID)

A vehicle seen ahead in a car's **front-left** camera later appears in its **rear-left** camera, seen from the other side. Your matcher gets one highlighted front target and a closed gallery of labelled rear candidates (C1, C2, …, at least three), and must name the one that's the same vehicle. The benchmark has 500 manually verified handovers from 20 recordings on South African roads.

| Rank-1 accuracy (%) | Full RGB | Target crop | Silhouette |
| --- | --- | --- | --- |
| Human participants (n = 25) | **94.0** | **92.2** | – |
| GPT-5.5, medium reasoning (best VLM) | 62.8 | 76.6 | 43.8 |
| SigLIP2 Base, frozen | – | 74.0 | – |
| Random gallery | – | 17.8 | – |

The paper and the project page's Results tab cover all seven VLMs, four retrieval controls, 95% BCa intervals and the difficulty breakdowns.

---

## 1. Get the data (5 minutes)

```bash
# 1. Download front2back-reid-v1.1.zip from the project page and unzip it
# 2. Check the download (needs Pillow only)
python -m pip install Pillow
python verify.py
#   PASS: 500 pairs, answers, media files, and checksums verified.
```

To check the ZIP itself before unzipping, compare its SHA-256 with the published `front2back-reid-v1.1.zip.sha256`:

```bash
sha256sum front2back-reid-v1.1.zip                                   # Linux
shasum -a 256 front2back-reid-v1.1.zip                               # macOS
Get-FileHash .\front2back-reid-v1.1.zip -Algorithm SHA256            # Windows PowerShell
```

To browse the pairs, run `python -m http.server 8000` in the unzipped folder and open <http://localhost:8000/#explore>. Opening `index.html` directly as a file won't load the data.

## 2. What's in the folder

```text
front2back-reid-v1.1/
├── annotations/
│   ├── pairs.jsonl          ← the task: one pair per line (model-safe, no answers)
│   ├── pairs.csv            ← same content as CSV
│   ├── ground_truth.jsonl   ← answers (keep out of prompts)
│   └── ground_truth.csv
├── splits/test500.txt       ← the fixed evaluation order (P0001 … P0500)
├── data/
│   ├── camera_splits/<sequence>/FL|RL/*.jpg   ← original front-left / rear-left frames (640×360)
│   └── object_detections/<sequence>/masks/FL/*.png ← front-target masks
├── inputs/P0001 … P0500/
│   ├── front_marked.jpg     ← full front frame with the target boxed  (Full RGB condition)
│   ├── front_crop.jpg       ← padded crop of the target               (Target crop condition)
│   └── rear_marked.jpg      ← rear frame with labelled candidate boxes (the gallery)
├── site/silhouettes/P0001.png …  ← black-on-white target silhouettes (Silhouette condition)
├── evaluate.py  verify.py  checksums.sha256  dataset_stats.json
└── index.html  project.css  project.js  site/   ← the project page (works offline)
```

There are 844 unique frames: 427 front and 417 rear. Images are reused across pairs, so 500 pairs doesn't mean 1,000 images.

## 3. One record

Each line of `annotations/pairs.jsonl` is one task:

```json
{
  "pair_id": "P0001",
  "road_context": "highway", "time_of_day": "dawn_dusk", "weather": "clear",
  "front": {
    "image": "data/camera_splits/2026_02_09_18_53_11_b5329d02/FL/fl_000915.jpg",
    "width": 640, "height": 360,
    "target_bbox_xyxy": [413.662, 237.403, 494.269, 275.918],
    "target_mask": "data/object_detections/.../FL/..._fl_truck_001.png"
  },
  "rear": {
    "image": "data/camera_splits/2026_02_09_18_53_11_b5329d02/RL/rl_000926.jpg",
    "width": 640, "height": 360,
    "candidates": [
      {"candidate_id": "C1", "bbox_xyxy": [0.0, 114.154, 82.707, 191.047]},
      {"candidate_id": "C2", "bbox_xyxy": [204.577, 160.221, 228.088, 174.155]}
    ]
  },
  "inputs": {
    "front_marked": "inputs/P0001/front_marked.jpg",
    "rear_marked": "inputs/P0001/rear_marked.jpg",
    "front_crop": "inputs/P0001/front_crop.jpg"
  }
}
```

- **Boxes** are pixel `[x1, y1, x2, y2]` in the 640×360 frame, with the origin at top-left. All paths are relative to the dataset root.
- **Candidates** are listed in a frozen order (ascending x1, then y1). The aliases `C1…CK` are the only identifiers to show a model. Detector classes aren't included, on purpose.
- **Masks** are full-frame 8-bit PNGs, with white (255) for the target and black elsewhere. `site/silhouettes/` holds the paper's silhouette input: the mask cropped with the same window as `front_crop.jpg`, black target on white.
- **`ground_truth.jsonl`** has `{"pair_id", "correct_candidate_id", "correct_detection_id"}`. Use it only to score.

## 4. Run a model (minimal Python)

```python
import json
from pathlib import Path
from PIL import Image

ROOT = Path("front2back-reid-v1.1")
pairs = [json.loads(l) for l in (ROOT / "annotations/pairs.jsonl").read_text().splitlines()]

CONDITION = "front_crop"          # "rgb_full" | "front_crop" | "front_mask"

def front_input(p):
    if CONDITION == "rgb_full":
        return Image.open(ROOT / p["inputs"]["front_marked"])
    if CONDITION == "front_crop":
        return Image.open(ROOT / p["inputs"]["front_crop"])
    return Image.open(ROOT / f"site/silhouettes/{p['pair_id']}.png")

with open("predictions.jsonl", "w") as out:
    for p in pairs:
        front = front_input(p)
        rear = Image.open(ROOT / p["inputs"]["rear_marked"])       # labelled gallery
        aliases = [c["candidate_id"] for c in p["rear"]["candidates"]]
        choice = my_matcher(front, rear, aliases)                   # ← your model; must return one alias
        out.write(json.dumps({"pair_id": p["pair_id"], "candidate_id": choice}) + "\n")
```

For a retrieval baseline, crop each candidate from `p["rear"]["image"]` with its `bbox_xyxy` and rank the crops by similarity to the front crop. That's how the paper's SigLIP2 and DINOv2 controls work.

**Matching the paper's VLM protocol:** show only the evidence for one condition and the labelled rear gallery. Never give box coordinates, detector classes or confidences. Set temperature to 0 where the model allows it, and count unparseable outputs or unlisted aliases as wrong. The exact prompt is on the project page (Overview, "Show the full prompt") and in Fig. 6 of the paper.

## 5. Score

```bash
python evaluate.py predictions.jsonl                       # Rank-1 accuracy
python evaluate.py predictions.jsonl --ci                  # + 95% percentile-bootstrap interval
python evaluate.py predictions.jsonl --per-pair hits.csv   # per-pair correctness for your own analysis
```

```json
{"pairs": 500, "submitted": 500, "missing": 0, "correct": 383, "top1_accuracy": 0.766}
```

The primary metric is **Rank-1 (top-1) accuracy over all 500 pairs**. Chance is 1/Kᵢ per pair, about 17% overall. Missing pairs count as wrong. Unknown pair IDs, duplicates and aliases that aren't in that pair's gallery stop the script with an error, so a typo can't silently cost points. The paper's intervals are BCa with 100,000 resamples, so `--ci` (percentile) may differ by a few tenths of a point.

## 6. Things that trip people up

- **There's no train/validation split.** All 500 pairs are the test set. Frames and targets repeat across pairs, so a random split isn't identity-disjoint. Report zero-shot results, or hold out whole recordings and say so.
- **Gallery size isn't the same as vehicle count.** `Kᵢ` (candidates shown) includes non-vehicle road users such as pedestrians. The paper's difficulty plots use the vehicle-only count `Vᵢ`. The two differ on 164 pairs, and both distributions are in `dataset_stats.json`.
- **Overlays are regenerated.** `inputs/` images were re-rendered from the recovered boxes, so their styling can differ slightly from the renderer used in the paper. Pixels, boxes and identities are the same.
- **Daytime dominates.** 97.6% of pairs are daytime, and front-target stereo depth (analysis only) is valid for 341 pairs.

## 7. Integrity

`checksums.sha256` lists a SHA-256 for every file in the release. `verify.py` checks those hashes plus every image, mask, box, candidate label, answer and the fixed split.

## 8. Project-page files (optional)

`index.html` is the project page, and it works offline from a local server. `site/data/` holds the paper results and per-pair metadata it reads, `site/img/` holds the paper figures, and `site/tools/` rebuilds those files from the research repository. `site/tools/extract_model_picks.py` exports each paper run's per-pair answers so the page can show model picks. To turn that on, set `model_picks_url` in `site-config.json`.

## Citation

```bibtex
@article{motsoehli2026front2back,
  title         = {Front-to-Back: Benchmarking Vision-Language Models for Asymmetric Cross-View Vehicle Re-Identification},
  author        = {Mots'oehli, Moseli and Babeli, Thulani},
  journal       = {arXiv preprint arXiv:2609.39492},
  year          = {2026},
  eprint        = {2609.39492},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CV},
  doi           = {10.48550/arXiv.2609.39492}
}
```

See also `CITATION.cff`. Code and tools are under the MIT License (`LICENSE`). For questions about the data, open an issue on GitHub.

## Changelog

- **v1.1 (2026-10-03):** new project page (results, Try the task, explorer), silhouette inputs, `evaluate.py --ci/--per-pair`, citation for arXiv:2609.39492 and an expanded README. The benchmark pairs, galleries and answers are unchanged from v1.
- **v1 (2026-09):** first public release of the 500 restored pairs.
