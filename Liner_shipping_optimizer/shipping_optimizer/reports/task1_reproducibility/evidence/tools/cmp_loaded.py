"""Compare two dump_loaded.py outputs field by field.

usage: python cmp_loaded.py <a.json> <b.json>
"""
import json
import math
import sys
from collections import Counter, defaultdict

a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))

for sec in ("ports", "demands", "fleet"):
    ka, kb = set(a[sec]), set(b[sec])
    print(f"[{sec}] keys only in A: {len(ka - kb)}  only in B: {len(kb - ka)}  common: {len(ka & kb)}")
    diffs = defaultdict(list)
    for k in sorted(ka & kb):
        for f in set(a[sec][k]) | set(b[sec][k]):
            va, vb = a[sec][k].get(f, "<absent>"), b[sec][k].get(f, "<absent>")
            same = (math.isclose(va, vb, rel_tol=1e-9, abs_tol=1e-9)
                    if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else va == vb)
            if not same:
                diffs[f].append((k, va, vb))
    if not diffs:
        print("    all common fields identical")
    for f, rows in sorted(diffs.items()):
        ratios = Counter()
        for k, va, vb in rows:
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and vb:
                ratios[round(va / vb, 4)] += 1
        ex = rows[0]
        extra = f"  A/B ratio histogram: {dict(ratios.most_common(4))}" if ratios else ""
        print(f"    field {f!r}: {len(rows)} differ; e.g. {ex[0]}: A={ex[1]!r} B={ex[2]!r}{extra}")

da, db = a["dist"], b["dist"]
n_a = sum(len(v) for v in da.values()); n_b = sum(len(v) for v in db.values())
mism = sum(1 for o in da for t in da[o] if o in db and t in db[o] and not math.isclose(da[o][t], db[o][t], rel_tol=1e-9))
print(f"[dist] pairs A={n_a} B={n_b}; value mismatches on common pairs: {mism}")
