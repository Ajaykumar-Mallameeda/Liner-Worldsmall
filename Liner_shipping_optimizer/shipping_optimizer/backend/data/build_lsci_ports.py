"""Build backend/data/lsci_ports.json from UNCTADstat's port liner shipping connectivity index (run once per quarter).

Input:  https://unctadstat-api.unctad.org/bulkdownload/US.PLSCI/US_PLSCI (7-Zip with US_PLSCI.csv; needs py7zr or 7z)
Usage:  python build_lsci_ports.py <US_PLSCI.csv> <output json> <retrieved YYYY-MM-DD>
Keeps the last 8 quarters per port: the index (average Q1 2023 = 100) by UN/LOCODE.
"""
import csv
import json
import sys
from collections import defaultdict

src, out, retrieved = sys.argv[1], sys.argv[2], sys.argv[3]
series = defaultdict(dict)
labels = {}
with open(src, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        v = r["Index (average Q1 2023 = 100)"].strip()
        if not v:
            continue
        series[r["Port"]][r["Quarter"]] = round(float(v), 2)
        labels[r["Port"]] = r["Port Label"]
quarters = sorted({q for s in series.values() for q in s})
keep = quarters[-8:]
body = {
    "source": "UNCTADstat US.PLSCI: Port liner shipping connectivity index, quarterly (average Q1 2023 = 100)",
    "source_url": "https://unctadstat.unctad.org/datacentre/dataviewer/US.PLSCI",
    "licence": "UNCTAD terms of use (free reuse with attribution)",
    "retrieved": retrieved, "quarters": keep, "latest_quarter": keep[-1],
    "ports": {p: {"label": labels[p], "values": [s.get(q) for q in keep]}
              for p, s in sorted(series.items()) if any(q in s for q in keep)},
}
json.dump(body, open(out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
print(len(body["ports"]), "ports", keep[0], "-", keep[-1])
