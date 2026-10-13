"""Compare failure messages of tests that fail in both runs. usage: cmp_fail_msgs.py A.xml B.xml"""
import re, sys, xml.etree.ElementTree as ET
def fails(p):
    d = {}
    for tc in ET.parse(p).getroot().iter("testcase"):
        f = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        if f is not None:
            m = (f.get("message") or "") + " " + (f.text or "")[:400]
            d[f'{tc.get("classname")}::{tc.get("name")}'] = re.sub(r"0x[0-9a-f]+|\d+(\.\d+)?", "N", m)[:260]
    return d
a, b = fails(sys.argv[1]), fails(sys.argv[2])
both = sorted(set(a) & set(b))
chg = [k for k in both if a[k] != b[k]]
print(f"failing in both: {len(both)}; message changed: {len(chg)}")
for k in chg:
    print("  ", k); print("     A:", a[k][:200]); print("     B:", b[k][:200])
print("only in A:", sorted(set(a) - set(b)))
print("only in B:", sorted(set(b) - set(a)))
