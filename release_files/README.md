# Front2Back-ReID v1.1 (dataset)

500 manually verified front-to-rear vehicle handovers from 20 recordings on South African roads. Each pair asks: which labelled rear-camera candidate is the vehicle highlighted in the front camera?

- **Paper:** [arXiv:2609.39492](https://arxiv.org/abs/2609.39492), submitted to the ACCV 2026 CV4DC workshop (under review)
- **Code:** <https://github.com/Mind-Forge-AI/Front2Back-ReID>, covering the loader, baselines, VLM harness and table scripts
- **Project page:** <https://mind-forge-ai.github.io/Front2Back-ReID/>

## Check the download

```bash
python -m pip install Pillow
python verify.py          # PASS: 500 pairs, answers, media files, and checksums verified.
```

## Layout

```text
annotations/pairs.jsonl         the task, one pair per line (no answers)
annotations/ground_truth.jsonl  answers: keep out of prompts, use only to score
splits/test500.txt              fixed evaluation order, P0001-P0500
data/camera_splits/<seq>/FL|RL/ original front-left / rear-left frames, 640x360
data/object_detections/.../masks/FL/  front-target masks (white = target)
inputs/P0001 ... P0500/         front_marked.jpg, front_crop.jpg, rear_marked.jpg (convenience renders)
evaluate.py  verify.py  checksums.sha256  dataset_stats.json
```

Boxes are pixel `[x1, y1, x2, y2]` with the origin at top-left. Candidates `C1…CK` are in a fixed order (ascending x1, then y1), and the aliases are the only identifiers to show a model. 844 unique frames are reused across the 500 pairs.

## Score

One JSON object per line, `{"pair_id": "P0001", "candidate_id": "C2"}`:

```bash
python evaluate.py predictions.jsonl            # Rank-1 over all 500 pairs
python evaluate.py predictions.jsonl --ci       # + 95% bootstrap interval
```

Missing pairs count as wrong. Unknown pairs, duplicates and aliases that aren't in that pair's gallery stop the script with an error. Chance is about 17%.

To reproduce the paper's inputs exactly, use `front2back.render` from the code repository. The `inputs/` images here are convenience renders, and their box styling differs.

## Notes

- **No train split:** all 500 pairs are test pairs, and frames repeat across pairs.
- **Gallery size vs vehicle count:** gallery size *Kᵢ* includes non-vehicle road users. The paper's difficulty plots use the vehicle-only count *Vᵢ*, which differs on 164 pairs (see `dataset_stats.json`).
- **Daytime dominates:** 97.6% of pairs are daytime.

## Citation

```bibtex
@article{motsoehli2026front2back,
  title   = {Front-to-Back: Benchmarking Vision-Language Models for Asymmetric Cross-View Vehicle Re-Identification},
  author  = {Mots'oehli, Moseli and Babeli, Thulani},
  journal = {arXiv preprint arXiv:2609.39492},
  year    = {2026},
  doi     = {10.48550/arXiv.2609.39492}
}
```
