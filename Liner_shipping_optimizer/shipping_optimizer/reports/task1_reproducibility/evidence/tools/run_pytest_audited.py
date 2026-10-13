"""Run pytest in-process with a PEP 578 audit hook that records every file open.

usage: python run_pytest_audited.py <report.json> <pytest args...>

Records (a) any opened path that looks like a WorldLarge / non-WorldSmall dataset file and
(b) the inventory of every file opened under data/raw or data/datasets, so the claim
"the suite reads only data/raw/WorldSmall" is a measurement, not an assumption.
"""
import json
import os
import re
import sys
from pathlib import Path

REPORT = Path(sys.argv[1])
PYTEST_ARGS = sys.argv[2:]

FOREIGN = re.compile(r"worldlarge|large_shipping_problem|world_large|distance_dense|port_mapping", re.I)
DATA = re.compile(r"[\\/]data[\\/](raw|datasets)[\\/]", re.I)

foreign_hits, data_opens = set(), {}


def _hook(event, args):
    if event != "open":
        return
    p = args[0]
    if isinstance(p, int):                       # file descriptor
        return
    try:
        s = os.fsdecode(p)
    except Exception:                            # noqa: BLE001
        return
    if FOREIGN.search(s):
        foreign_hits.add(s)
    if DATA.search(s):
        mode = args[1] if len(args) > 1 and isinstance(args[1], str) else "r"
        data_opens.setdefault(s, set()).add(mode)


sys.addaudithook(_hook)

import pytest  # noqa: E402  (after the hook so collection-time opens are seen)

rc = pytest.main(PYTEST_ARGS)

root = Path.cwd().resolve()


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(root)).replace("\\", "/")
    except Exception:                            # noqa: BLE001
        return p


REPORT.write_text(json.dumps({
    "pytest_exit_code": int(rc),
    "cwd": str(root),
    "foreign_open_hits": sorted(rel(p) for p in foreign_hits),
    "data_files_opened": sorted(rel(p) for p in data_opens),
    "data_files_opened_for_write": sorted(rel(p) for p, m in data_opens.items()
                                          if any(set(x) & set("wax+") for x in m)),
}, indent=1), encoding="utf-8")
print(f"[audit] exit={int(rc)} foreign hits={len(foreign_hits)} data files opened={len(data_opens)} -> {REPORT}")
sys.exit(int(rc))
