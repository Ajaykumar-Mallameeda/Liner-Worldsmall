"""Compare pytest JUnit XML results across trees.

usage: python -I compare_suites.py LABEL=path.xml [LABEL=path.xml ...] [--out report.md]
The first label is the reference. Reports counts per label and, for each later label,
tests that: newly fail, were fixed, are only present on one side, changed to/from skip/xfail.
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

args = [a for a in sys.argv[1:] if not a.startswith("--out")]
out_path = None
if "--out" in sys.argv:
    out_path = sys.argv[sys.argv.index("--out") + 1]
    args = [a for a in args if a != out_path]


def load(path):
    res = {}
    for tc in ET.parse(path).getroot().iter("testcase"):
        tid = f'{tc.get("classname")}::{tc.get("name")}'
        st = "pass"
        for ch in tc:
            if ch.tag in ("failure", "error"):
                st = "FAIL"
            elif ch.tag == "skipped":
                st = "xfail" if (ch.get("type") or "").endswith("xfail") else "skip"
        res[tid] = st
    return res


runs = {}
for a in args:
    label, p = a.split("=", 1)
    runs[label] = load(p)

lines = []
P = lines.append
P("## Counts")
P("| tree | total | pass | FAIL | skip | xfail |")
P("|---|---|---|---|---|---|")
for lb, r in runs.items():
    c = Counter(r.values())
    P(f"| {lb} | {len(r)} | {c['pass']} | {c['FAIL']} | {c['skip']} | {c['xfail']} |")

labels = list(runs)
ref = labels[0]
for lb in labels[1:]:
    a, b = runs[ref], runs[lb]
    P(f"\n## {ref} -> {lb}")
    newly_fail = sorted(t for t in b if b[t] == "FAIL" and a.get(t) not in ("FAIL",))
    fixed = sorted(t for t in a if a[t] == "FAIL" and b.get(t) in ("pass",))
    both_fail = sorted(t for t in a if a[t] == "FAIL" and b.get(t) == "FAIL")
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    changed = sorted(t for t in set(a) & set(b) if a[t] != b[t] and t not in newly_fail and t not in fixed)
    P(f"- failing in both: {len(both_fail)}")
    P(f"- newly failing in {lb} (pass/skip/xfail/absent in {ref}): {len(newly_fail)}")
    for t in newly_fail:
        P(f"  - `{t}`  [{ref}: {a.get(t, 'absent')}]")
    P(f"- fixed in {lb} (FAIL in {ref}, pass in {lb}): {len(fixed)}")
    for t in fixed:
        P(f"  - `{t}`")
    P(f"- other status changes: {len(changed)}")
    for t in changed:
        P(f"  - `{t}`: {a[t]} -> {b[t]}")
    P(f"- only in {ref}: {len(only_a)}")
    for t in only_a:
        P(f"  - `{t}` [{a[t]}]")
    P(f"- only in {lb}: {len(only_b)}")
    for t in only_b:
        P(f"  - `{t}` [{b[t]}]")

text = "\n".join(lines)
print(text)
if out_path:
    open(out_path, "w", encoding="utf-8").write(text + "\n")
