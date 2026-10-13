"""Compare two pytest JUnit XML files: failing sets, newly failing, fixed, new passing tests.

usage: python -I compare_suites.py <baseline.junit.xml> <candidate.junit.xml> <out.md> [label_a label_b]
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def load(path):
    out = {}
    for tc in ET.parse(path).getroot().iter("testcase"):
        key = f"{tc.get('classname')}::{tc.get('name')}"
        if tc.find("failure") is not None or tc.find("error") is not None:
            out[key] = "failed"
        elif tc.find("skipped") is not None:
            out[key] = "skipped"
        else:
            out[key] = "passed"
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
la = sys.argv[4] if len(sys.argv) > 4 else "baseline"
lb = sys.argv[5] if len(sys.argv) > 5 else "candidate"
fa = {k for k, v in a.items() if v == "failed"}
fb = {k for k, v in b.items() if v == "failed"}
new_fail = sorted(k for k in fb if k not in fa and k in a)
new_tests_failing = sorted(k for k in fb if k not in a)
fixed = sorted(k for k in fa if b.get(k) == "passed")
missing = sorted(k for k in a if k not in b)
new_pass = sorted(k for k, v in b.items() if k not in a and v == "passed")
count = lambda d, s: sum(1 for v in d.values() if v == s)                      # noqa: E731
lines = [f"# Suite comparison: {la} vs {lb}", "",
         f"| | {la} | {lb} |", "|---|---:|---:|",
         f"| failed | {count(a, 'failed')} | {count(b, 'failed')} |",
         f"| passed | {count(a, 'passed')} | {count(b, 'passed')} |",
         f"| skipped | {count(a, 'skipped')} | {count(b, 'skipped')} |", "",
         f"* newly failing (present in both, passed before): **{len(new_fail)}**",
         f"* failing new tests: **{len(new_tests_failing)}**",
         f"* fixed (failed before, pass now): {len(fixed)}",
         f"* in the baseline but not run in the candidate: {len(missing)}",
         f"* new passing tests: {len(new_pass)}",
         f"* failing set identical: {fa == fb}", ""]
for title, items in (("Newly failing", new_fail), ("Failing new tests", new_tests_failing),
                     ("Fixed", fixed), ("Missing in candidate", missing)):
    if items:
        lines += [f"## {title}", ""] + [f"- `{k}`" for k in items[:80]] + [""]
Path(sys.argv[3]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines[:16]))
