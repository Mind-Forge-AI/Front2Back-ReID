"""Export each paper run's per-pair answer for the project page (optional).

Usage:
  python site/tools/extract_model_picks.py <full-verified.sqlite> <path-to-AsymOvertake-ReID>

The database is opened read-only (immutable). Only model outputs are read: for each
canonical paper run (listed in the restored export's provenance/results.json) we keep
pair_id -> picked candidate alias, the model's reported confidence, and its one-sentence
evidence. No participant, session or human-response data is touched.

Writes site/data/model_picks.json. Then set "model_picks_url": "site/data/model_picks.json"
in site-config.json so the Try and Explore tabs show model picks.
"""
import json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if len(sys.argv) < 3:
    raise SystemExit(__doc__)
DB, SRC = Path(sys.argv[1]), Path(sys.argv[2])
PROV = SRC / "export/front2back-reid-v1/provenance"

res = json.loads((PROV / "results.json").read_text(encoding="utf-8"))
runs = res["canonical_runs"]
sources = [json.loads(l) for l in (PROV / "pair_sources.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
pair_of = {s["annotation_id"]: s["pair_id"] for s in sources}
alias_of = {s["pair_id"]: {d["detection_id"]: f"C{i + 1}" for i, d in enumerate(s["candidate_detections"])} for s in sources}
truth = {json.loads(l)["pair_id"]: json.loads(l)["correct_candidate_id"] for l in (ROOT / "annotations/ground_truth.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True)
cols = {r[1] for r in con.execute("pragma table_info(model_evaluation_responses)")}
need = {"run_id", "annotation_id", "selected_detection_id"}
if not need <= cols:
    raise SystemExit(f"model_evaluation_responses lacks {need - cols}")
has_parsed = "parsed_json" in cols

out, report = {}, []
for key, run_id in runs.items():
    q = f"select annotation_id, selected_detection_id{', parsed_json' if has_parsed else ''} from model_evaluation_responses where run_id = ?"
    picks = {}
    for row in con.execute(q, (run_id,)):
        ann, det = row[0], row[1]
        pid = pair_of.get(ann)
        if not pid:
            continue
        parsed = {}
        if has_parsed and row[2]:
            try:
                parsed = json.loads(row[2]) or {}
            except (TypeError, ValueError):
                parsed = {}
        alias = alias_of[pid].get(det) or (parsed.get("candidate_id") if parsed.get("candidate_id") in alias_of[pid].values() else None)
        if not alias:
            continue  # unparsable / unlisted -> scored wrong in the paper; omit
        entry = {"c": alias}
        conf = parsed.get("confidence")
        if isinstance(conf, (int, float)):
            entry["p"] = round(float(conf), 3)
        reason = parsed.get("reasoning")
        if isinstance(reason, str) and reason.strip():
            entry["r"] = reason.strip()[:240]
        picks[pid] = entry
    if not picks:
        report.append(f"{key}: no responses found for run {run_id}")
        continue
    acc = 100 * sum(v["c"] == truth[p] for p, v in picks.items()) / 500
    ref = res["overall"].get(key, {}).get("accuracy")
    note = "" if ref is None else f" (paper {100 * ref:.1f})"
    report.append(f"{key}: {len(picks)} pairs, accuracy {acc:.1f}{note}")
    out[key] = {"run_id": run_id, "picks": picks}

(ROOT / "site/data/model_picks.json").write_text(json.dumps({"schema_version": "front2back_model_picks.v1", "runs": out}, separators=(",", ":")), encoding="utf-8")
print("\n".join(report))
print(f"Wrote site/data/model_picks.json with {len(out)} runs.")
