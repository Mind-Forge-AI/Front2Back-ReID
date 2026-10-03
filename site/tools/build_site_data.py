"""Build the static data files used by the Front2Back-ReID project page.

Usage:  python site/tools/build_site_data.py <path-to-AsymOvertake-ReID>

Reads (read-only) the restored export's provenance and the paper's science-pack
figures from the research repository, plus this release's annotations, and writes:
  site/data/results.json   paper results (Tables 3-4, strata, human reference)
  site/data/trials.json    per-pair task data for the "Try the task" tab
  site/silhouettes/*.png   black-on-white silhouette crops (paper's mask condition)
No participant-identifying data is read or written.
"""
import csv, json, math, re, sqlite3, sys
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "AsymOvertake-ReID"
PROV = SRC / "export/front2back-reid-v1/provenance"
PACK = SRC / "paper/latex/figures/science_pack"
OUT = ROOT / "site/data"

def jl(p): return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
def r1(x): return None if x is None else round(100 * x, 1)

# ---------------------------------------------------------------- models
MODELS = [  # key, label, family, access, provider, params, reasoning modes run
    ("llava_onevision_0_5b", "LLaVA-OneVision 0.5B", "open", "Local", "Local", "0.5B"),
    ("llama4_scout_groq", "Llama 4 Scout", "open", "API", "Groq", "17B/109B"),
    ("qwen3_6_27b_groq", "Qwen 3.6 27B", "open", "API", "Groq", "27B"),
    ("gpt5_5", "GPT-5.5", "closed", "API", "OpenAI", "n/d"),
    ("gpt5_4_mini", "GPT-5.4 mini", "closed", "API", "OpenAI", "n/d"),
    ("gemini_2_5_pro", "Gemini 2.5 Pro", "closed", "API", "Google AI Studio", "n/d"),
    ("gemini_2_5_flash", "Gemini 2.5 Flash", "closed", "API", "Google AI Studio", "n/d"),
]
BASELINES = [("random_gallery", "Random gallery"), ("hsv_histogram", "HSV histogram"),
             ("dinov2_vitb14", "DINOv2 ViT-B/14"), ("siglip2_base", "SigLIP2 Base")]

# Paper Tables 3 and 4 (Rank-1 %, 95% BCa). Source of truth for the leaderboard.
T = lambda a, lo, hi: {"acc": a, "lo": lo, "hi": hi}
TABLE = {
  "none": {
    "random_gallery":      {"front_crop": T(17.8, 14.4, 21.2)},
    "hsv_histogram":       {"front_crop": T(47.6, 43.0, 51.8)},
    "dinov2_vitb14":       {"front_crop": T(49.4, 44.8, 53.6)},
    "siglip2_base":        {"front_crop": T(74.0, 69.8, 77.6)},
    "llava_onevision_0_5b":{"rgb_full": T(27.4, 23.4, 31.2), "front_crop": T(27.4, 23.4, 31.2), "front_mask": T(27.4, 23.4, 31.2)},
    "llama4_scout_groq":   {"rgb_full": T(54.8, 50.2, 59.0), "front_crop": T(61.4, 56.8, 65.4), "front_mask": T(34.2, 30.0, 38.2)},
    "qwen3_6_27b_groq":    {"rgb_full": T(63.6, 59.2, 67.6), "front_crop": T(74.6, 70.4, 78.0), "front_mask": T(32.2, 28.0, 36.2)},
    "gpt5_5":              {"rgb_full": T(58.4, 53.8, 62.4), "front_crop": T(74.8, 70.6, 78.2), "front_mask": T(36.8, 32.4, 40.8)},
    "gpt5_4_mini":         {"rgb_full": T(44.6, 40.0, 48.8), "front_crop": T(58.4, 53.8, 62.4), "front_mask": T(28.6, 24.6, 32.6)},
    "gemini_2_5_flash":    {"rgb_full": T(50.6, 46.0, 54.8), "front_crop": T(64.0, 59.6, 68.0), "front_mask": T(25.2, 21.4, 29.0)},
  },
  "medium": {
    "gpt5_5":           {"rgb_full": T(62.8, 58.2, 66.8), "front_crop": T(76.6, 72.6, 80.0), "front_mask": T(43.8, 39.4, 48.0)},
    "gpt5_4_mini":      {"rgb_full": T(58.8, 54.2, 62.8), "front_crop": T(71.0, 66.6, 74.6), "front_mask": T(40.0, 35.6, 44.2)},
    "gemini_2_5_pro":   {"rgb_full": T(60.6, 56.0, 64.6), "front_crop": T(71.8, 67.4, 75.4), "front_mask": T(34.6, 30.4, 38.6)},
    "gemini_2_5_flash": {"rgb_full": T(54.4, 49.8, 58.6), "front_crop": T(67.2, 62.8, 71.0), "front_mask": T(32.0, 27.8, 36.0)},
  },
}
HUMAN = {"rgb_full": T(94.0, 91.6, 95.8), "front_crop": T(92.2, 89.6, 94.4)}

res = json.loads((PROV / "results.json").read_text(encoding="utf-8"))

# Cross-check every reasoning-disabled VLM cell against the recorded results.
mismatch = []
for key, cell in res["overall"].items():
    m, cond, eff = key.split(":")
    if m == "human_reference": continue
    p = TABLE[eff][m][cond]
    if abs(r1(cell["accuracy"]) - p["acc"]) > 0.05 or abs(r1(cell["ci_lower"]) - p["lo"]) > 0.05 or abs(r1(cell["ci_upper"]) - p["hi"]) > 0.05:
        mismatch.append((key, cell, p))
for key, e in res["reasoning_effects"].items():
    m, cond = key.split(":")
    if abs(r1(e["medium"]) - TABLE["medium"][m][cond]["acc"]) > 0.05: mismatch.append((key, e))
for cond, h in res["human_reference"]["conditions"].items():
    if abs(r1(h["accuracy"]) - HUMAN[cond]["acc"]) > 0.05: mismatch.append((cond, h))
if mismatch:
    raise SystemExit(f"Paper table and results.json disagree: {mismatch}")

reasoning = [{"model": k.split(":")[0], "condition": k.split(":")[1], "none": r1(e["none"]), "medium": r1(e["medium"]),
              "delta": r1(e["delta"]), "lo": r1(e["ci_lower"]), "hi": r1(e["ci_upper"])} for k, e in res["reasoning_effects"].items()]

def strata(block, keys):
    out = {}
    for factor, labels in keys.items():
        out[factor] = {m: [{"bin": b, "n": v[b]["n"], "acc": r1(v[b]["accuracy"]), "lo": r1(v[b]["ci_lower"]), "hi": r1(v[b]["ci_upper"])} for b in labels]
                       for m, v in block[factor].items()}
    return out
difficulty = strata(res["results_difficulty_strata"], {
    "candidate_count_bin": ["3", "4-5", "6+"], "front_target_bbox_size_bin": ["large", "medium", "small"],
    "front_target_occlusion_bin": ["none", "partial", "heavy"]})
context = strata(res["results_context_strata"], {
    "weather": ["clear", "overcast", "sun_glare"], "road_context": ["highway", "urban", "suburban"],
    "rear_target_bbox_size_bin": ["large", "medium", "small"], "rear_target_occlusion_bin": ["none", "partial", "heavy"]})
depth_meds = [5.5, 8.7, 12.1, 17.3, 33.7]; area_meds = [0.4, 0.9, 1.4, 2.5, 5.9]
sens = res["results_depth_scale_sensitivity"]
depth = {m: [{"bin": f"{depth_meds[i]} m", "n": c["n"], "acc": r1(c["accuracy"]), "lo": r1(c["ci_lower"]), "hi": r1(c["ci_upper"])} for i, c in enumerate(v)]
         for m, v in sens["front_target_range_value"].items()}
area = {m: [{"bin": f"{area_meds[i]}%", "n": c["n"], "acc": r1(c["accuracy"]), "lo": r1(c["ci_lower"]), "hi": r1(c["ci_upper"])} for i, c in enumerate(v)]
        for m, v in sens["front_target_bbox_area_norm"].items()}

# Human strata (Fig. 12) recovered from the vector figure: y pixel -> % via the y ticks.
svg = (PACK / "results_human_strata.svg").read_text(encoding="utf-8")
uses = re.findall(r'<use xlink:href="#(m[0-9a-f]+)" x="([\d.]+)" y="([\d.]+)"', svg)
by = {}
for mid, x, y in uses: by.setdefault(mid, []).append((float(x), float(y)))
yt = sorted({y for _, y in max((v for v in by.values() if len({x for x, _ in v}) <= 4), key=len)})
# y ticks are 100, 90, 80, 70 from top to bottom
scale = lambda y: 100 - (y - yt[0]) / ((yt[-1] - yt[0]) / 30)
pts_id = [k for k, v in by.items() if len(v) == 12 and len({y for _, y in v}) > 1][0]
cap_id = [k for k, v in by.items() if len(v) == 24][0]
hs_labels = [("Rear-gallery size", ["3", "4-5", "6+"], [90, 326, 584]),
             ("Front-target scale", ["Large", "Med", "Small"], [332, 334, 334]),
             ("Rear-target scale", ["Large", "Med", "Small"], [332, 332, 336]),
             ("Front occlusion", ["None", "Partial", "Heavy"], [754, 190, 56])]
pts = by[pts_id]; caps = by[cap_id]
human_strata = []
for pi, (title, bins, ns) in enumerate(hs_labels):
    row = []
    for bi in range(3):
        x, y = pts[pi * 3 + bi]
        cy = sorted(cy for cx, cy in caps if abs(cx - x) < 0.5)
        n = ns[bi]; k = round(scale(y) / 100 * n)
        row.append({"bin": bins[bi], "n": n, "acc": round(100 * k / n, 1), "hi": round(scale(cy[0]), 1), "lo": round(scale(cy[-1]), 1)})
    human_strata.append({"factor": title, "bins": row})

summ = json.loads((PACK / "human_scores_latency_summary.json").read_text(encoding="utf-8"))
participants = [{"id": r["anonymous_participant"], "rgb_full": float(r["full_rgb_percent"]), "front_crop": float(r["crop_percent"])}
                for r in csv.DictReader((PACK / "human_participant_scores.csv").open(encoding="utf-8"))]
lat = summ["latency_by_correctness"]; cs = summ["condition_summary"]
human = {
    "participants": 25, "judgments": 1000, "trials_per_condition": 20, "time_limit_min": 25,
    "accuracy": HUMAN, "participant_scores": participants,
    "latency_s": {c: {"median": round(cs[c]["all_latency_s"]["median"], 2), "q25": round(cs[c]["all_latency_s"]["q25"], 2), "q75": round(cs[c]["all_latency_s"]["q75"], 2)} for c in ("rgb_full", "front_crop")},
    "latency_by_outcome_s": {k: {"n": v["n"], "median": round(v["median"], 2), "q25": round(v["q25"], 2), "q75": round(v["q75"], 2)} for k, v in lat.items()},
    "comparisons": [{"condition": k.split(":")[0], "model": k.split(":")[1], "effort": k.split(":")[2], "human": r1(v["human_accuracy"]),
                     "model_acc": r1(v["model_accuracy_on_human_subset"]), "delta": r1(v["paired_delta"]), "lo": r1(v["ci_lower"]), "hi": r1(v["ci_upper"])}
                    for k, v in res["human_reference"]["comparisons"].items()],
    "strata": human_strata,
}

composition = [dict(r, count=int(r["count"]), percentage=round(float(r["percentage"]), 1)) for r in csv.DictReader((PROV / "categorical.csv").open(encoding="utf-8"))]

results = {
    "schema_version": "front2back_site_results.v1",
    "paper": {"arxiv": "2609.39492", "submitted": "2026-09-30"},
    "bootstrap": {"method": "BCa", "resamples": res["resamples"], "seed": res["seed"]},
    "conditions": {"rgb_full": "Full RGB", "front_crop": "Target crop", "front_mask": "Silhouette"},
    "models": [dict(zip(["key", "label", "family", "access", "provider", "params"], m)) for m in MODELS],
    "baselines": [{"key": k, "label": l} for k, l in BASELINES],
    "table": TABLE, "human": human, "reasoning_effects": reasoning,
    "paired": {"gpt5_5_medium_vs_siglip2_crop": {"delta": 2.6, "lo": -2.2, "hi": 7.4, "only_gpt": 81, "only_siglip": 68}},
    "strata": {"difficulty": difficulty, "context": context, "front_depth": depth, "front_area": area},
    "composition": composition,
}
(OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

# ---------------------------------------------------------------- trials
pairs = jl(ROOT / "annotations/pairs.jsonl")
truth = {x["pair_id"]: x for x in jl(ROOT / "annotations/ground_truth.jsonl")}
paper = {r["annotation_id"]: r for r in csv.DictReader((PROV / "pairs_paper.csv").open(encoding="utf-8"))}
sources = {s["pair_id"]: s["annotation_id"] for s in jl(PROV / "pair_sources.jsonl")}
hard = set(summ.get("both_condition_errors", []))
# Size/truncation bins exactly as used in the paper's analysis (pair_difficulties table of the
# human-evaluation bundle; read-only, difficulty columns only).
con = sqlite3.connect(f"file:{(SRC / 'recovery/onedrive/human-eval-bundle.sqlite').as_posix()}?mode=ro&immutable=1", uri=True)
diff = {r[0]: r[1:] for r in con.execute("select annotation_id, front_target_bbox_size_bin, rear_target_bbox_size_bin, front_target_truncation_bin, rear_target_truncation_bin from pair_difficulties")}
con.close()
trials = []
for p in pairs:
    pid = p["pair_id"]; ann = sources[pid]; row = paper[ann]
    vi = int(row["candidate_count"])
    fa, ra = float(row["front_target_bbox_area_norm"]), float(row["rear_target_bbox_area_norm"])
    depth_m = float(row["front_target_range_value"]) if row["range_source"].startswith("s2m2") else None
    # silhouette: same padded window as the release's front crop, black target on white
    x1, y1, x2, y2 = p["front"]["target_bbox_xyxy"]
    with Image.open(ROOT / p["front"]["target_mask"]) as m:
        m = m.convert("L")
        pad = max(8, math.floor(max(x2 - x1, y2 - y1) * .18 + .5))
        left, top = max(0, math.floor(x1 - pad)), max(0, math.floor(y1 - pad))
        w, h = min(m.width - left, math.ceil(x2 - x1 + 2 * pad)), min(m.height - top, math.ceil(y2 - y1 + 2 * pad))
        sil = ImageOps.invert(m.crop((left, top, left + w, top + h)).point(lambda v: 255 if v >= 128 else 0))
        sil.save(ROOT / f"site/silhouettes/{pid}.png", optimize=True)
    trials.append({
        "id": pid,
        "front": {"marked": p["inputs"]["front_marked"], "crop": p["inputs"]["front_crop"], "silhouette": f"site/silhouettes/{pid}.png",
                  "image": p["front"]["image"], "box": [round(v, 1) for v in p["front"]["target_bbox_xyxy"]]},
        "rear": {"image": p["rear"]["image"], "w": p["rear"]["width"], "h": p["rear"]["height"],
                 "candidates": [{"id": c["candidate_id"], "box": [round(v, 1) for v in c["bbox_xyxy"]]} for c in p["rear"]["candidates"]]},
        "answer": truth[pid]["correct_candidate_id"],
        "tags": {"road": p["road_context"], "time": p["time_of_day"], "weather": p["weather"], "k": len(p["rear"]["candidates"]), "vi": vi,
                 "vi_bin": "3" if vi <= 3 else "4-5" if vi <= 5 else "6+",
                 "front_scale": diff[ann][0], "rear_scale": diff[ann][1], "front_trunc": diff[ann][2], "rear_trunc": diff[ann][3],
                 "front_occ": row["front_target_occlusion_bin"], "rear_occ": row["rear_target_occlusion_bin"],
                 "depth_m": None if depth_m is None else round(depth_m, 1), "human_missed_both": ann in hard},
    })
(OUT / "trials.json").write_text(json.dumps({"schema_version": "front2back_site_trials.v1", "trials": trials}, separators=(",", ":")), encoding="utf-8")
print(f"results.json ok; {len(trials)} trials; {sum(t['tags']['human_missed_both'] for t in trials)} human-hard; human strata:",
      [[b['acc'] for b in s['bins']] for s in human_strata])
