"""Compare the candidate-pool dumps written by ``pool_dump.py``.

usage: python -I pool_compare.py <dump_dir> <out.md> <seed> [<seed> ...]

Expects ``base_s<seed>.json`` (frozen baseline tree), ``final_off_s<seed>.json`` (final tree,
LINER_DEMAND_LOOP_BUDGET=0 and LINER_CLASS_SCREEN=0) and ``final_default_s<seed>.json``
(final tree, defaults). The claim checked is: baseline == final(both switches 0), element
by element and in order (ports, vessel class, capacity, cycle time of every candidate that
survives the regional filter). Exit status 1 when any seed differs.
"""
import json
import sys
from collections import Counter
from pathlib import Path

d = Path(sys.argv[1])
out = Path(sys.argv[2])
seeds = [int(s) for s in sys.argv[3:]]
lines = [
    "# Candidate pool: frozen baseline vs final tree with both switches at 0",
    "",
    "One interpreter per tree and seed (`PYTHONHASHSEED=0`, `python -I`). A candidate is "
    "`(ports, vessel class, capacity, cycle time)`; lists are compared in order.",
    "",
    "| seed | region | baseline | final, switches 0/0 | identical (ordered) | final, defaults | added by defaults | removed by defaults |",
    "|---:|---|---:|---:|:---:|---:|---:|---:|",
]
all_same = True
for s in seeds:
    b = json.loads((d / f"base_s{s}.json").read_text())[str(s)]
    o = json.loads((d / f"final_off_s{s}.json").read_text())[str(s)]
    f = json.loads((d / f"final_default_s{s}.json").read_text())[str(s)]
    for r in b:
        same = b[r] == o[r]
        all_same &= same
        key = lambda x: (tuple(x[0]), x[1], x[2], x[3])        # noqa: E731
        cb, cf = Counter(map(key, b[r])), Counter(map(key, f[r]))
        added = sum((cf - cb).values())
        removed = sum((cb - cf).values())
        lines.append(f"| {s} | {r} | {len(b[r])} | {len(o[r])} | {'yes' if same else '**NO**'} | "
                     f"{len(f[r])} | {added} | {removed} |")
lines += ["", f"**Result: {'IDENTICAL for every seed and region' if all_same else 'DIFFERENCES FOUND'}.**", ""]
out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
sys.exit(0 if all_same else 1)
