<p align="center"><img src="docs/site/img/mindforge-logo-192.png" height="72" alt="MindForge AI"></p>

<h1 align="center">Front-to-Back: Benchmarking Vision-Language Models for<br>Asymmetric Cross-View Vehicle Re-Identification</h1>

<p align="center">
Moseli Mots'oehli<sup>1,2</sup> · Thulani Babeli<sup>1</sup><br>
<sup>1</sup>MindForge AI, Johannesburg · <sup>2</sup>University of Hawai'i at Mānoa<br>
ACCV 2026 Workshop CV4DC (under review)
</p>

<p align="center">
<a href="https://arxiv.org/abs/2609.39492">Paper</a> ·
<a href="https://mind-forge-ai.github.io/Front2Back-ReID/">Project page</a> ·
<a href="https://mind-forge-ai.github.io/Front2Back-ReID/#try">Try the task</a> ·
<a href="#data">Dataset</a>
</p>

A vehicle seen in a car's **front-left** camera later appears in its **rear-left** camera, seen from the other side. Given the highlighted front target and a closed gallery of labelled rear candidates, pick the same vehicle. **Front2Back-ReID** has 500 manually verified handovers from 20 recordings on South African roads. This repository has the code to load the benchmark, run the paper's baselines and VLMs, and rebuild its tables.

| Rank-1 (%) | Full RGB | Target crop | Silhouette |
|---|---|---|---|
| Humans (n = 25) | **94.0** | **92.2** | – |
| GPT-5.5, medium reasoning | 62.8 | 76.6 | 43.8 |
| SigLIP2 Base, frozen | – | 74.0 | – |
| Random | – | 17.8 | – |

## Setup

```bash
git clone https://github.com/Mind-Forge-AI/Front2Back-ReID.git && cd Front2Back-ReID
pip install -e .                    # core: loader, scoring, BCa, API runners
pip install -e ".[baselines]"       # + HSV, DINOv2, SigLIP2
pip install -e ".[local]"           # + local LLaVA-OneVision
```

<a id="data"></a>
## Data

```bash
python scripts/download_data.py                  # -> data/front2back-reid-v1.1/
python data/front2back-reid-v1.1/verify.py       # checks hashes, images and answers
```

If the download link opens a web page, download the ZIP in a browser and run `python scripts/download_data.py --zip <file>`. The release README describes the file layout and record format.

```python
from front2back import Benchmark
bench = Benchmark("data/front2back-reid-v1.1")
pair = bench["P0001"]          # front image, target box + mask, rear image, candidates C1..CK
pair.aliases, bench.answer("P0001")
```

## Evaluate your method

Write one `{"pair_id": "P0001", "candidate_id": "C2"}` per line, then:

```bash
python scripts/evaluate.py --data data/front2back-reid-v1.1 predictions.jsonl
```

This reports Rank-1 over all 500 pairs with a 95% BCa interval. Missing pairs count as wrong, and unknown or invalid aliases are rejected.

## Reproduce the paper

**Baselines** (no API keys needed):

```bash
python scripts/run_baselines.py --data data/front2back-reid-v1.1 --baseline all
```

**VLMs** use the paper's protocol, implemented in `front2back/vlm.py`:

- **Images:** one request per pair. It sends the front evidence, then the labelled rear gallery, rendered exactly as in the paper's runs (`front2back/render.py`).
- **Prompt:** the v3 prompt (`front2back/prompts.py`).
- **Settings:** temperature 0, and reasoning `none` or `medium` where a model supports it.

```bash
export OPENAI_API_KEY=...  GEMINI_API_KEY=...  GROQ_API_KEY=...
python scripts/run_vlm.py --data data/front2back-reid-v1.1 --model gpt5_5 --all          # every cell for one model
python scripts/run_vlm.py --data data/front2back-reid-v1.1 --model gpt5_5 \
       --condition rgb_full --dry-run P0001                                               # inspect one request
```

Models: `gpt5_5`, `gpt5_4_mini`, `gemini_2_5_pro`, `gemini_2_5_flash`, `qwen3_6_27b_groq`, `llama4_scout_groq`, `llava_onevision_0_5b`. Runs resume automatically, and provider errors are retried. Only complete 500-pair runs are scored, as in the paper. Hosted models change over time, so expect small differences from the paper's June–July 2026 runs.

**Tables 3–4.** Rank-1, 95% BCa intervals, the context gap and paired reasoning gains, each checked against the paper:

```bash
python scripts/make_tables.py --data data/front2back-reid-v1.1 --runs runs
```

Point estimates reproduce exactly. For example, Random is 17.8 and HSV is 47.6. BCa bounds can differ from the paper by about 0.2 points, which is one pair, because the original bootstrap stream wasn't archived.

## Repository layout

```text
front2back/            Python package
  data.py              release loader (Benchmark, Pair)
  render.py            model inputs exactly as evaluated
  prompts.py           v3 prompt + output contract
  vlm.py               model registry and request settings
  providers/           OpenAI, Gemini, Groq, local LLaVA-OneVision
  baselines.py         random, HSV histogram, DINOv2, SigLIP2
  scoring.py stats.py  Rank-1, BCa and paired BCa intervals
scripts/               download_data, evaluate, run_baselines, run_vlm, make_tables
release_files/         README, evaluate.py and verify.py shipped inside the dataset ZIP
tools/build_release.py builds the dataset ZIP (maintainers)
tests/                 pytest (set FRONT2BACK_DATA to the release folder)
docs/                  project page (GitHub Pages)
```

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

Code is released under the MIT License (`LICENSE`). We thank the 25 participants in the human evaluation and Dalitso Chomey for valuable discussions.
