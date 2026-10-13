"""Build the run register: one row per recorded test/benchmark run.

usage: python -I register_runs.py <runs_dir> <out_dir> [label ...]

For every ``<label>.meta.txt`` in ``runs_dir`` it records the command, working tree
(+ SHA-256 of the tree manifest and the number of files), start time, elapsed time,
exit code, the assertion scorecard (orchestrator runs) or the pytest summary
(focused runs), and - when ``<label>.pipeline_output.json`` exists - the headline KPIs
and the LLM-fallback facts of that run (rate limits are ignored by design: HTTP 429
-> deterministic fallback text, recorded here, never a reason to skip a run).

Output: ``run_register.json`` and ``run_register.md`` in ``out_dir``. Nothing is
deleted or overwritten except those two generated files.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
RUNS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
ONLY = set(sys.argv[3:])
OUT.mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_meta(p: Path) -> dict:
    d = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line and not line.startswith("---"):
            k, _, v = line.partition(":")
            d.setdefault(k.strip(), v.strip())
    return d


def kpis(art: Path) -> dict:
    j = json.loads(art.read_text(encoding="utf-8"))
    nl = j.get("network_ledger") or {}
    w = nl.get("weekly_usd") or {}
    dm = nl.get("demand_teu_per_week") or {}
    fp = (nl.get("assumptions") or {}).get("fuel_pricing") or {}
    gen = (nl.get("assumptions") or {}).get("candidate_generation") or {}
    agg = (j.get("llm_runtime_aggregate") or {}).get("coordinator") or {}
    sm = j.get("summary_metrics") or {}
    gm = (j.get("decision_output") or {}).get("global_metrics") or {}
    fleet = nl.get("fleet_by_class") or {}
    return {
        "status": j.get("status"), "ledger_verified": nl.get("verified"), "milp_status": nl.get("status"),
        "best_iteration": j.get("best_iteration"),
        "iteration_profits": [round(e.get("profit", 0)) for e in j.get("iteration_audit", [])],
        "weekly_profit": w.get("operating_profit"), "revenue": w.get("revenue"),
        "total_cost": w.get("total_operating_cost"), "fuel_cost": w.get("fuel_cost"),
        "margin_pct": (100 * w["profit_margin_on_revenue"]) if w.get("profit_margin_on_revenue") is not None else None,
        "coverage_pct": dm.get("coverage_pct"), "served_teu": dm.get("served"),
        "services_operated": (nl.get("services") or {}).get("operated"),
        "candidates_offered": (nl.get("services") or {}).get("candidates_offered"),
        "vessels_deployed": sum(v.get("used", 0) for v in fleet.values()),
        "vessels_by_class": {k: v.get("used", 0) for k, v in fleet.items() if v.get("used")},
        "violations": len(nl.get("violations") or []),
        "global_metrics_total_cost": gm.get("total_cost"),
        "global_metrics_margin_pct": gm.get("profit_margin_pct"),
        "pricing_mode": fp.get("mode"), "pricing_snapshot": fp.get("snapshot_id"),
        "pricing_sha256": fp.get("sha256"),
        "demand_loops": (gen.get("demand_coherent_loops") or {}).get("budget_per_regional_problem"),
        "class_screening": (gen.get("class_screening") or {}).get("mode"),
        "pipeline_runtime_sec": sm.get("total_runtime"),
        "llm_coordinator_429": agg.get("coordinator_429_count"),
        "llm_coordinator_fallback": agg.get("coordinator_fallback"),
        "llm_decision_source": agg.get("coordinator_decision_source"),
        "artifact_sha256": sha(art),
    }


rows = []
for meta in sorted(RUNS.glob("*.meta.txt")):
    label = meta.name[: -len(".meta.txt")]
    if ONLY and label not in ONLY:
        continue
    m = parse_meta(meta)
    log = RUNS / f"{label}.log"
    text = ANSI.sub("", log.read_text(encoding="utf-8", errors="replace")) if log.exists() else ""
    row = {"label": label, "command": m.get("command"), "tree": m.get("tree"),
           "started": m.get("started"), "elapsed_s": m.get("elapsed_s"), "exit_code": m.get("exit_code")}
    tree = m.get("tree")
    if tree:
        mf = Path(tree).parent / (Path(tree).name + ".manifest.json")
        if mf.exists():
            row["tree_manifest_sha256"] = sha(mf)
            row["tree_files"] = len(json.loads(mf.read_text()))
    sc = re.search(r"Passed\s*:\s*(\d+)/(\d+)", text)
    fl = re.search(r"Failed\s*:\s*(\d+)/(\d+)", text)
    wr = re.search(r"Warnings:\s*(\d+)", text)
    if sc:
        row["assertions_passed"], row["assertions_total"] = int(sc.group(1)), int(sc.group(2))
        row["assertions_failed"] = int(fl.group(1)) if fl else None
        row["warnings"] = int(wr.group(1)) if wr else None
        row["failed_assertions"] = [ln.strip()[:160] for ln in text.splitlines()
                                    if re.match(r"\s+-\s{2}", ln)][:10]
    summ = re.findall(r"(\d+ (?:passed|failed)[^\n]*)", text)
    if summ:
        row["pytest_summary"] = summ[-1][:160]
    art = RUNS / f"{label}.pipeline_output.json"
    if art.exists():
        try:
            row["kpis"] = kpis(art)
        except Exception as exc:                                  # noqa: BLE001
            row["kpis_error"] = f"{type(exc).__name__}: {exc}"
    rows.append(row)

(OUT / "run_register.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
lines = ["# Run register (every recorded test / benchmark run)", "",
         "LLM rate limits (HTTP 429) are ignored by design: the deterministic fallback text is used and its",
         "count is recorded per run below. Commands are `python -m pytest ...` from the snapshot tree.", "",
         "| label | exit | elapsed s | assertions / summary | profit USD/wk | margin % | coverage % | services | vessels | mode | 429 |",
         "|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|"]
for r in rows:
    k = r.get("kpis") or {}
    summ = (f"{r['assertions_passed']}/{r['assertions_total']} (failed {r['assertions_failed']})"
            if "assertions_passed" in r else r.get("pytest_summary", ""))
    prof = k.get("weekly_profit")
    mode = f"{k.get('pricing_mode', '')}|{k.get('demand_loops', '')}|{k.get('class_screening', '')}" if k else ""
    lines.append(
        f"| {r['label']} | {r.get('exit_code')} | {r.get('elapsed_s')} | {summ} | "
        f"{'' if prof is None else format(prof, ',.0f')} | "
        f"{'' if k.get('margin_pct') is None else format(k['margin_pct'], '.2f')} | "
        f"{'' if k.get('coverage_pct') is None else format(k['coverage_pct'], '.2f')} | "
        f"{k.get('services_operated', '')} | {k.get('vessels_deployed', '')} | {mode} | "
        f"{k.get('llm_coordinator_429', '')} |")
(OUT / "run_register.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(rows)} runs -> {OUT}")
