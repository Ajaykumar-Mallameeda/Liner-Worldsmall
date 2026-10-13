"""List the controlled runs in which the profit-floor repair was evaluated below the floor.
usage: python -I repair_triggers.py "<glob>" """
import glob
import json
import os
import sys

n = trig = 0
for f in sorted(glob.glob(sys.argv[1])):
    d = json.load(open(f, encoding="utf-8"))
    r = d["runs"][0]
    led = r.get("ledger") or {}
    n += 1
    rp = ((led.get("reconciliation") or {}).get("flow_reoptimisation") or {}).get("repair")
    if not rp:
        continue
    if rp.get("applied") or (rp.get("profit_before") is not None and rp["profit_before"] < 0):
        trig += 1
        print(os.path.basename(f)[:-5], "before %.2f M" % (rp["profit_before"] / 1e6),
              "after %s M" % ("%.2f" % (rp["profit_after"] / 1e6) if rp.get("profit_after") is not None else "n/a"),
              "dropped", rp.get("dropped"), "trials", rp.get("trials"),
              "served %.0f -> %s" % (rp.get("served_teu_before") or 0, rp.get("served_teu_after")),
              "|", rp.get("reason"))
print(n, "runs;", trig, "with the repair evaluated below the floor")
