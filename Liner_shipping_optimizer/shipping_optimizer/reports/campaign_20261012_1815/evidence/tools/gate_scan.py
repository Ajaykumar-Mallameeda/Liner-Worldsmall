"""Cross-experiment gate scan: every solved plan of every arm in evidence/outputs.

usage: python -I gate_scan.py [<tag_prefix> ...] [--out file.md]

For each arm (tag = file name without _seed<S>.json) counts: files, solved plans, ledger valid, ledger violations,
regional accounting verified, MILP/ledger reconciled, negative-profit plans, plans over 120 s of stage wall time
(stage wall = wall_sec_total of the global stage), status histogram.  Exit code 1 when any solved plan fails a gate.
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

OUT = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\reports\campaign_20261012_1815\evidence\outputs")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
outfile = None
if "--out" in sys.argv:
    outfile = Path(sys.argv[sys.argv.index("--out") + 1])
    args = [a for a in args if Path(a) != outfile]
prefixes = args or [""]

arms = collections.defaultdict(lambda: collections.Counter())
fail_files = []
for f in sorted(glob.glob(str(OUT / "*_seed*.json"))):
    name = Path(f).name
    tag = re.sub(r"_seed\d+(_.*)?\.json$", "", name)
    if not any(tag.startswith(p) for p in prefixes):
        continue
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        continue
    for r in d.get("runs", []) or []:
        c = arms[tag]
        c["files"] += 1
        led = r.get("ledger") or {}
        solved = bool(r.get("ok")) and bool(led)
        c[f"status:{r.get('status')}"] += 1
        if not solved:
            c["not_solved"] += 1
            continue
        c["solved"] += 1
        rr = r.get("regional_reconciliation") or {}
        rec = led.get("reconciliation") or {}
        good_valid = led.get("valid") is True
        good_viol = not (led.get("violations") or [])
        good_regional = rr.get("accounting_status") == "verified" and rr.get("accounting_verified") is True and not rr.get("issues")
        good_recon = rec.get("reconciled") is True
        c["ledger_valid"] += good_valid
        c["no_violations"] += good_viol
        c["regional_verified"] += good_regional
        c["reconciled"] += good_recon
        if (led.get("profit") or 0) < 0:
            c["negative_profit"] += 1
        if (r.get("wall_sec_total") or 0) > 120.0:
            c["stage_over_120s"] += 1
        if not (good_valid and good_viol and good_regional and good_recon):
            fail_files.append(name)

lines = ["| arm | files | solved | ledger valid | 0 violations | regional verified | reconciled | negative profit | stage > 120 s | not solved |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
for tag in sorted(arms):
    c = arms[tag]
    lines.append(f"| {tag} | {c['files']} | {c['solved']} | {c['ledger_valid']} | {c['no_violations']} | {c['regional_verified']} | "
                 f"{c['reconciled']} | {c['negative_profit']} | {c['stage_over_120s']} | {c['not_solved']} |")
tot = collections.Counter()
for c in arms.values():
    tot.update(c)
lines.append(f"| **all** | {tot['files']} | {tot['solved']} | {tot['ledger_valid']} | {tot['no_violations']} | {tot['regional_verified']} | "
             f"{tot['reconciled']} | {tot['negative_profit']} | {tot['stage_over_120s']} | {tot['not_solved']} |")
text = "\n".join(lines)
print(text)
if fail_files:
    print("\nFAILING FILES:", fail_files)
if outfile:
    outfile.write_text(text + "\n", encoding="utf-8")
sys.exit(1 if fail_files else 0)
