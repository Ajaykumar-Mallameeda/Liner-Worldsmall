"""Path-model statistics per variant (mean over seeds): valid paths, kept, at cap, build seconds,
model variables / constraints, solve seconds.  usage: python -I path_model_table.py <out.md> <glob>... """
import glob
import json
import os
import statistics
import sys

out = sys.argv[1]
rows = {}
for pat in sys.argv[2:]:
    for f in sorted(glob.glob(pat)):
        name = os.path.basename(f)[:-5]
        parts = name.split("_")
        key = (parts[0], parts[2])
        d = json.load(open(f, encoding="utf-8"))
        r = d["runs"][0]
        pm = r.get("path_model") or {}
        s = r.get("solver") or {}
        if not pm:
            continue
        rows.setdefault(key, []).append((pm.get("paths_valid"), pm.get("paths_built"), pm.get("od_at_cap"),
                                         pm.get("paths_dropped_by_cap"), pm.get("path_build_sec"),
                                         pm.get("multi_hop_build_sec"), pm.get("od_multi_hop_enumerated"),
                                         pm.get("paths_multi_hop_kept"), s.get("variables"),
                                         s.get("constraints"), s.get("runtime_sec")))
lines = ["| batch | variant | n | valid paths | kept | ODs at cap | dropped by cap | path build s | multi-hop build s | "
         "ODs multi-hop enumerated | multi-hop paths kept | model variables | constraints | solve s |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]


def mean(vs, i, nd=0):
    xs = [v[i] for v in vs if v[i] is not None]
    return "" if not xs else f"{statistics.mean(xs):,.{nd}f}"


for (tag, var), vs in sorted(rows.items()):
    lines.append(f"| {tag} | {var} | {len(vs)} | {mean(vs, 0)} | {mean(vs, 1)} | {mean(vs, 2)} | {mean(vs, 3)} | "
                 f"{mean(vs, 4, 1)} | {mean(vs, 5, 1)} | {mean(vs, 6)} | {mean(vs, 7)} | {mean(vs, 8)} | "
                 f"{mean(vs, 9)} | {mean(vs, 10, 1)} |")
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
