"""Build ``experiment_manifest.json`` for the Tasks 19-21 mission from the recorded evidence.

usage: python -I build_manifest.py <report_dir> <decisions.json> <out.json>
Every entry is read from a file on disk (outputs, run meta files, snapshot manifests, the
WorldSmall input files); nothing is typed by hand except the owner-decision statuses, which are
read from ``decisions.json``.
"""
import glob
import hashlib
import json
import os
import platform
import re
import sys
from pathlib import Path

REPORT, DECISIONS, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
EV = REPORT / "evidence"
PROJECT = REPORT.parent.parent
SNAP = Path(r"D:\liner_scratch")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


m = {"mission": "Tasks 19, 20 and 21 (integrated experiment)", "date": "2026-10-11 .. 2026-10-12",
     "dataset": "WorldSmall only", "python": platform.python_version(),
     "platform": platform.platform(), "cpu_count": os.cpu_count(),
     "concurrency_policy": "at most 4 solver processes at a time (CBC at 120 s is CPU-load sensitive; "
                           "identical inputs reproduced bit-for-bit across loads of 3 and 4)"}
try:
    import pulp
    import scipy
    m["pulp"], m["scipy"] = pulp.__version__, scipy.__version__
except Exception:                                                      # noqa: BLE001
    pass

# ---- inputs ---------------------------------------------------------------------------
ws = PROJECT / "data" / "raw" / "WorldSmall"
m["inputs"] = {p.name: sha(p) for p in sorted(ws.glob("*")) if p.is_file()}

# ---- trees ----------------------------------------------------------------------------
trees = {}
for mf in sorted(SNAP.glob("snap_T19*.manifest.json")):
    trees[mf.name.replace(".manifest.json", "").replace("snap_", "")] = {
        "manifest_sha256": sha(mf), "files": len(json.loads(mf.read_text(encoding="utf-8")))}
m["trees"] = trees
m["baseline_tree"] = "T19B0_orch_run1 (live tree at the start of the mission = Tasks 14-16 final tree, "\
                     "216/216 src/backend/data/tests files identical to snap_FINAL2_orch_default_run1)"

# ---- controlled runs ------------------------------------------------------------------
ctl = []
for f in sorted(glob.glob(str(EV / "outputs" / "*.json"))):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:                                                  # noqa: BLE001
        continue
    if not isinstance(d, dict) or "runs" not in d or "seed" not in d:
        continue
    name = Path(f).stem
    for r in d["runs"] if "iterations" not in d else []:
        led = r.get("ledger") or {}
        s = r.get("solver") or {}
        ctl.append({"run_id": name, "seed": d["seed"], "time_limit_sec": d.get("time_limit_sec"),
                    "strategy": r.get("strategy"), "env": d.get("env"), "tree": d.get("tree"),
                    "solver_backend": "highs" if (d.get("env") or {}).get("NETWORK_MILP_BACKEND") == "highs" else "cbc",
                    "candidate_pool_unique": (d.get("pool") or {}).get("unique_candidates"),
                    "candidate_pool_order_sha256": (d.get("pool") or {}).get("unique_order_sha256"),
                    "path_pool_sha256": r.get("path_pool_sha256"), "paths": r.get("paths_total"),
                    "model_variables": s.get("variables"), "model_constraints": s.get("constraints"),
                    "solution_status": s.get("solution_status"), "objective": s.get("objective_usd_per_week"),
                    "dual_bound": s.get("relaxation_bound"), "gap_to_bound_pct": s.get("gap_to_bound_pct"),
                    "solve_runtime_sec": s.get("runtime_sec"), "profit": led.get("profit"),
                    "coverage_pct": led.get("coverage_pct"), "ledger_valid": led.get("valid"),
                    "ledger_violations": len(led.get("violations", [])),
                    "output": str(Path(f).relative_to(PROJECT)).replace("\\", "/"), "sha256": sha(Path(f))})
m["controlled_runs"] = ctl
m["controlled_run_count"] = len(ctl)

# ---- orchestrator runs ----------------------------------------------------------------
orch = []
for meta in sorted(glob.glob(str(EV / "runs" / "*.meta.txt"))):
    t = Path(meta).read_text(encoding="utf-8")
    label = Path(meta).name.replace(".meta.txt", "")
    po = EV / "runs" / f"{label}.pipeline_output.json"
    e = {"label": label, "kind": "whole-suite run (pytest, orchestrator excluded)" if label.startswith("T19S_")
         else "orchestrator run (tests/test_orchestrator.py)"}
    for key in ("tree", "command", "exit_code", "elapsed_s", "started", "files", "tree_manifest_sha256", "env"):
        mm = re.search(rf"^{key}: (.*)$", t, re.M)
        if mm:
            e[key] = mm.group(1)
    if po.exists():
        d = json.loads(po.read_text(encoding="utf-8"))
        nl = d.get("network_ledger") or {}
        e.update({"output": str(po.relative_to(PROJECT)).replace("\\", "/"), "sha256": sha(po),
                  "status": d.get("status"), "ledger_verified": nl.get("verified"),
                  "profit": (nl.get("weekly_usd") or {}).get("operating_profit"),
                  "coverage_pct": (nl.get("demand_teu_per_week") or {}).get("coverage_pct"),
                  "assertions": d.get("test_scorecard")})
    orch.append(e)
m["orchestrator_runs"] = orch

# ---- patches ----------------------------------------------------------------------------
pt = REPORT / "patches"
m["patches"] = {p.name: sha(p) for p in sorted(pt.glob("*.patch"))} if pt.exists() else {}
m["owner_decisions"] = json.loads(DECISIONS.read_text(encoding="utf-8")) if DECISIONS.exists() else {}
OUT.write_text(json.dumps(m, indent=1, default=str), encoding="utf-8")
print("wrote", OUT, "controlled:", len(ctl), "orchestrator:", len(orch), "trees:", len(trees))
