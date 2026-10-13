"""Tabulate ``replay_pricing.py`` outputs: legacy versus market-price scenarios on the same
captured global-stage inputs.

usage: python -I summarize_pricing_replay.py <out.md> <title>=<glob-or-prefix> [...]

Each ``<title>=<prefix>`` names a captured pool; files ``<prefix>_call<N>.json`` (production
LP-guided strategy) and ``<prefix>_call<N>_fullint.json`` (unrestricted integer solve, when
present) are read. Every number is copied from the replay output; nothing is recomputed
except means over calls.
"""
import json
import statistics as st
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
pools = []
for arg in sys.argv[2:]:
    title, _, prefix = arg.partition("=")
    pools.append((title, Path(prefix)))


def load(prefix: Path, suffix: str):
    res = {}
    for n in range(10):
        p = prefix.parent / f"{prefix.name}_call{n}{suffix}.json"
        if p.exists():
            res[n] = json.loads(p.read_text(encoding="utf-8"))
    return res


def cell(r):
    return (f"{r['profit']:,.0f} / {r['coverage_pct']:.1f} % / {r['n_services']} svc / {r['vessels']} ves"
            f" / {r['status']}")


lines = ["# Legacy (600 USD/t) versus market-price scenarios on identical captured inputs", "",
         "Same demand, fleet, captured candidate pool and solver for every row; only the bunker price changes. "
         "USD per week. `regional` = cheapest observed bunkering port on the rotation, else the 895.5 USD/t "
         "reference; `regional_strict` = rotations without an observed port are rejected; ×0.8 / ×1.2 scale "
         "every snapshot price. Violations are the independent ledger's; every scenario reconciles MILP = ledger.", ""]
for title, prefix in pools:
    main = load(prefix, "")
    full = load(prefix, "_fullint")
    if not main:
        continue
    calls = sorted(main)
    scen = list(main[calls[0]]["scenarios"])
    lines += [f"## {title}", "",
              f"Production strategy (LP-guided restriction), {len(calls)} captured global-stage call(s), "
              f"candidates {', '.join(str(main[c]['candidates_offered']) for c in calls)}.", "",
              "| scenario | " + " | ".join(f"call {c}: profit / coverage / services / vessels / status" for c in calls)
              + " | mean profit | ledger violations |",
              "|---|" + "---|" * (len(calls) + 2)]
    for s in scen:
        rs = [main[c]["scenarios"][s] for c in calls]
        viol = sum(len(r.get("violations") or []) for r in rs)
        lines.append(f"| {s} | " + " | ".join(cell(r) for r in rs)
                     + f" | {st.mean(r['profit'] for r in rs):,.0f} | {viol} |")
    if full:
        fcalls = sorted(full)
        fscen = list(full[fcalls[0]]["scenarios"])
        lines += ["", "Unrestricted integer solve (no LP-guided restriction; time limit "
                  f"{full[fcalls[0]]['time_limit_sec']:.0f} s; `optimal` = proven):", "",
                  "| scenario | " + " | ".join(f"call {c}" for c in fcalls) + " |",
                  "|---|" + "---|" * len(fcalls)]
        for s in fscen:
            lines.append(f"| {s} | " + " | ".join(cell(full[c]["scenarios"][s]) for c in fcalls) + " |")
    lines.append("")
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
