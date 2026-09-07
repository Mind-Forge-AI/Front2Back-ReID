# Front2Back-ReID

Front2Back-ReID is a benchmark for asymmetric cross-view vehicle re-identification. For each of 500 test pairs, identify a marked vehicle in a front-camera image among labelled candidates in a rear-camera image.

## Quick start

1. Unzip the release.
2. Install the validation dependency: `python -m pip install Pillow`.
3. Check the package: `python verify.py`.
4. Browse locally: `python -m http.server 8000 --bind 127.0.0.1`, then open `http://127.0.0.1:8000/`.

The project page is `index.html`; `explorer.html` lets you inspect every pair.

## Files you need

- `annotations/pairs.jsonl`: task pairs, image paths, target/candidate boxes, and input paths.
- `annotations/ground_truth.jsonl`: correct answers. Keep this out of model prompts.
- `splits/test500.txt`: the fixed test order.
- `data/`: original front/rear frames and target masks.
- `inputs/`: ready-to-use marked images and target crops.
- `evaluate.py` and `verify.py`: scoring and validation tools.

## Task and scoring

For each `pair_id`, give the model the front query and rear gallery. Return one candidate ID:

```json
{"pair_id":"P0001","candidate_id":"C2"}
```

Save one JSON object per line in `predictions.jsonl`, then run:

```powershell
python evaluate.py predictions.jsonl
```

The primary metric is top-1 accuracy over the fixed 500 pairs. Missing predictions count as incorrect. Duplicate, unknown, or invalid candidate IDs are rejected. Coordinates are pixel `[x1, y1, x2, y2]` in the original image. `P0001` through `P0500` are stable release aliases.

## Integrity

`checksums.sha256` records every release file. `verify.py` checks hashes, images, masks, boxes, candidate labels, answers, and the fixed split.

## Citation and license

See `CITATION.cff` and `LICENSE`. Please cite the accompanying paper/repository when using the benchmark.

## Hosting the project page

See `PUBLISH_GITHUB_PAGES.md`. The page is static. Set the two download URLs in `site-config.json` after uploading the archive to your file host.
