"""Interim/final paired screening vs T2 (seeds present in both). usage: screen_peek.py <arm> [<arm>...]"""
import json, sys, glob, re, statistics as st
def load(a):
    d = {}
    for f in glob.glob(f"outputs/{a}_seed*.json"):
        try:
            r = json.load(open(f))["runs"][-1]
        except Exception:
            continue
        l = r.get("ledger") or {}
        s = int(re.search(r"seed(\d+)", f).group(1))
        bc = (r.get("strategy_report") or {}).get("utilisation", {}).get("fleet", {}).get("by_class", {})
        d[s] = (l.get("profit"), l.get("coverage_pct"), l.get("services"), (bc.get("Post_panamax") or {}).get("vessels_used"), r.get("status"), len(l.get("violations") or []))
    return d
T2 = load("T2")
for a in sys.argv[1:]:
    X = load(a); seeds = sorted(s for s in X if s in T2)
    if not seeds: print(a, "no runs"); continue
    ok = [s for s in seeds if X[s][0] is not None]
    dp = [X[s][0] - T2[s][0] for s in ok]; dc = [X[s][1] - T2[s][1] for s in ok]
    print(f"{a}: n={len(seeds)} solved={len(ok)} dProfit mean {st.mean(dp)/1e6:+.2f} M (min {min(dp)/1e6:+.2f}, higher {sum(x>0 for x in dp)}/{len(dp)}) "
          f"dCov {st.mean(dc):+.2f} pp services {st.mean(X[s][2] for s in ok):.1f} (T2 {st.mean(T2[s][2] for s in ok):.1f}) "
          f"Post {st.mean((X[s][3] or 0) for s in ok):.1f} (T2 {st.mean((T2[s][3] or 0) for s in ok):.1f}) viol {sum(X[s][5] for s in ok)} notsolved {len(seeds)-len(ok)}")
