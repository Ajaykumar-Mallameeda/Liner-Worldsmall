"""Integrity counts over every recorded run: ledger violations, reconciliation, solver status, strategy-report
reconciliation, in controlled outputs and orchestrator outputs.  usage: python -I integrity_count.py <evidence_dir>"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

ev = Path(sys.argv[1])
c = Counter()
viol_runs = []
for f in sorted(glob.glob(str(ev / "outputs" / "*.json"))):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:                                              # noqa: BLE001
        continue
    if not isinstance(d, dict) or "runs" not in d or "seed" not in d or "iterations" in d:
        continue
    for r in d["runs"]:
        led = r.get("ledger")
        if not led:
            c["controlled_no_plan(not_solved/other)"] += 1
            continue
        c["controlled_with_plan"] += 1
        if led.get("violations"):
            c["controlled_with_violations"] += 1
            viol_runs.append(Path(f).name)
        rec = led.get("reconciliation") or {}
        if rec.get("reconciled") is False:
            c["controlled_not_reconciled"] += 1
        rr = r.get("regional_reconciliation") or {}
        if rr and rr.get("accounting_verified") is False:
            c["controlled_regional_partition_not_verified"] += 1
        sr = r.get("strategy_report") or {}
        if sr.get("available") and not (sr.get("reconciliation") or {}).get("all"):
            c["controlled_strategy_report_not_reconciled"] += 1
        if sr.get("available"):
            c["controlled_strategy_report_reconciled"] += int(bool((sr.get("reconciliation") or {}).get("all")))
        fr = rec.get("flow_reoptimisation") or {}
        if fr.get("applied") and r.get("solver", {}).get("solution_status") == "optimal":
            c["controlled_optimal_reported_after_reopt"] += 1
for f in sorted(glob.glob(str(ev / "outputs" / "*.json"))):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:                                              # noqa: BLE001
        continue
    if isinstance(d, dict) and "iterations" in d and "runs" in d:
        for r in d["runs"]:
            c["iteration_runs"] += 1
            c["iteration_runs_with_violations"] += int(bool(r.get("violations")))
for f in sorted(glob.glob(str(ev / "runs" / "*.pipeline_output.json"))):
    if Path(f).name.startswith("T19S_"):       # copies made by the suite runs
        continue
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    nl = d.get("network_ledger") or {}
    c["orchestrator_runs"] += 1
    c["orchestrator_verified"] += int(bool(nl.get("verified")))
    c["orchestrator_with_violations"] += int(bool(nl.get("violations")))
    sc = d.get("test_scorecard") or {}
    c["orchestrator_assertions_failed"] += int(sc.get("assertions_failed") or 0)
    sr = nl.get("strategy_report") or {}
    if sr:
        c["orchestrator_strategy_report_reconciled"] += int(bool((sr.get("reconciliation") or {}).get("all")))
for k, v in sorted(c.items()):
    print(f"{k:50s} {v}")
print("runs with violations:", viol_runs[:10])
