"""Read-only: what does LINER_TRUNK_CANDIDATES=N offer, per class, for the production pool of a seed (same pool code as class_diag)?
usage: trunk_offer_check.py <tree_root> <seed> <N> <out.json>"""
import json, sys, random
from collections import Counter
from pathlib import Path
ROOT = Path(sys.argv[1]); SEED = int(sys.argv[2]); N = int(sys.argv[3]); OUT = Path(sys.argv[4])
sys.path.insert(0, str(ROOT))
exec(open(Path(__file__).with_name("class_diag.py"), encoding="utf-8").read().split("a = assumptions_for_problem(base)")[0].split("ROOT = Path(sys.argv[1])")[1].split("\n", 1)[1].replace("sys.path.insert(0, str(ROOT))", ""))
from src.network.trunk_candidates import augment_trunk_candidates
a = assumptions_for_problem(base)
extra, rep = augment_trunk_candidates(base, a, cands, per_class=N, max_ports=8, diverse=(len(sys.argv) > 5 and sys.argv[5] == "diverse"))
by = {}
for x in rep["additions"]:
    by.setdefault(x["vessel_class"], []).append({k: x[k] for k in ("service_id", "ports", "standalone_profit_usd_per_week", "vessels_at_f1", "served_teu_f1")})
out = {"seed": SEED, "N": N, "target_classes": rep["target_classes"], "added": rep["added"], "sec": rep["sec"], "by_class": by}
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({"target_classes": rep["target_classes"], "added": rep["added"], "sec": rep["sec"], "per_class": {k: [(len(v), v[0]["standalone_profit_usd_per_week"]) for v in [vs]][0] for k, vs in by.items()}}, indent=1))
