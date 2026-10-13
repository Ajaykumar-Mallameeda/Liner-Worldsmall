"""Print the solver-level fields of controlled-run outputs (status, bound, restriction, size).
usage: python -I solver_fields.py "<glob>" """
import glob
import json
import os
import sys

for f in sorted(glob.glob(sys.argv[1])):
    d = json.load(open(f, encoding="utf-8"))
    r = d["runs"][0]
    s = r.get("solver", {})
    led = r.get("ledger", {})
    print(os.path.basename(f)[:-5], "status", s.get("solution_status"),
          "profit", round((led.get("profit") or 0) / 1e6, 2),
          "bound", round((s.get("relaxation_bound") or 0) / 1e6, 1),
          "gap%", None if s.get("gap_to_bound_pct") is None else round(s["gap_to_bound_pct"], 1),
          "restricted", s.get("services_in_integer_problem"), "/", s.get("services_considered"),
          "vars", s.get("variables"), "cons", s.get("constraints"), "sec", s.get("runtime_sec"),
          "recon", (led.get("reconciliation") or {}).get("reconciled"),
          "slack_removed", (led.get("reconciliation") or {}).get("vessel_slack_removed"))
