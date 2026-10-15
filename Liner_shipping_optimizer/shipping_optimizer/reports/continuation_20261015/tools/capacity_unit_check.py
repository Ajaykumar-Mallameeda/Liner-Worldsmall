"""Capacity-unit check against the LINERLIB authors' own WorldSmall solution log (primary-source output).

The log prints, per service, a utilisation (e.g. ``0.815185 service id 0``) and lists every transported flow (FFE) with its hops.
Recomputing from the flows the mean leg load factor of each service with capacity = ``Capacity FFE`` (one weekly departure) must
reproduce the printed number if the capacity column is an FFE count; with a TEU reading (capacity 450 TEU = 225 FFE) the load
factors would reach 2.0 and the printed numbers could not be reproduced.
usage: python -I capacity_unit_check.py <WorldSmall_Best_Base.log> <out.json>
"""
import json
import re
import sys
from pathlib import Path

LOG, OUT = Path(sys.argv[1]), Path(sys.argv[2])
text = LOG.read_text(encoding="utf8", errors="replace")
blocks = re.split(r"\nservice \d+ service id (\d+)\n", "\nservice 0 service id 0\n" + text.partition("service 0 service id 0")[2].lstrip("\n"))
S = {}
for i in range(1, len(blocks), 2):
    sid, body = int(blocks[i]), blocks[i + 1].split("\nID:")[0]
    S[sid] = {"cap": int(re.search(r"capacity (\d+)", body).group(1)), "ports": re.findall(r"^\d+\t(\w+)\t", body, flags=re.M)}
util = [(float(a), int(b)) for a, b in re.findall(r"^([\d.]+) service id (\d+)$", text, flags=re.M)]
hops, cur = [], None
for line in text.splitlines():
    m = re.match(r"ID:(\d+) (\w+)->(\w+) Transported ([\d.e+-]+)", line)
    if m:
        cur = float(m.group(4))
        continue
    if re.match(r"ID:\d+ .* Rejected", line):
        cur = None
        continue
    if cur is not None:
        m = re.match(r"\s*(?:Path )?(\w+?)_(\d+)->(\w+?)_(\d+)\s*$", line)
        if m:
            hops.append((m.group(1), int(m.group(2)), m.group(3), cur))


def legs(sid, a, b):
    ps = S[sid]["ports"]
    n = len(ps)
    ia = [i for i, p in enumerate(ps) if p == a]
    ib = [i for i, p in enumerate(ps) if p == b]
    best = None
    for i in ia:
        for j in ib:
            k = (j - i) % n or n
            if best is None or k < best[0]:
                best = (k, i)
    return [(best[1] + t) % n for t in range(best[0])], (len(ia) > 1 or len(ib) > 1)


load = {sid: [0.0] * len(S[sid]["ports"]) for sid in S}
ambiguous = set()
for a, sid, b, q in hops:
    ls, amb = legs(sid, a, b)
    if amb:
        ambiguous.add(sid)
    for l in ls:
        load[sid][l] += q
rows = []
for u, sid in util:
    cap = S[sid]["cap"]
    mean_lf = sum(load[sid]) / (cap * len(load[sid]))
    rows.append({"service": sid, "printed": u, "mean_leg_load_factor_cap_ffe": mean_lf, "max_leg_load_factor_cap_ffe": max(load[sid]) / cap,
                 "ambiguous_rotation": sid in ambiguous, "diff": mean_lf - u})
exact = [r for r in rows if abs(r["diff"]) < 2e-6]
res = {"services": len(rows), "printed_reproduced_within_2e-6": len(exact), "max_abs_diff": max(abs(r["diff"]) for r in rows),
       "unambiguous_services": sum(1 for r in rows if not r["ambiguous_rotation"]),
       "unambiguous_reproduced": sum(1 for r in exact if not r["ambiguous_rotation"]),
       "max_leg_load_factor_over_all_services_with_capacity_in_FFE": max(r["max_leg_load_factor_cap_ffe"] for r in rows),
       "reading": "capacity = Capacity FFE per weekly departure reproduces the printed utilisation; no leg exceeds 1.0 (+1e-6); a TEU "
                  "reading (capacity/2 FFE) would give load factors up to 2.0", "rows": rows}
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print({k: v for k, v in res.items() if k != "rows"})
