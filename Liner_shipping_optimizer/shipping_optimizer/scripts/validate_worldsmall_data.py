#!/usr/bin/env python3
"""
Standalone validation script for the LINERLIB WorldSmall dataset package.

Verifies ports, demand, fleet, distance, and JSON outputs against expected values.
Run after generate_worldsmall_dataset.py.
"""

import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW_WS = BASE / "data" / "raw" / "WorldSmall"
JSON_PATH = BASE / "data" / "datasets" / "worldsmall_shipping_problem.json"

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, int, int, str]] = []  # section, item, expected, actual, status


def check(section: str, item: str, expected, actual, tolerance=0):
    if isinstance(expected, (int, float)) and tolerance:
        ok = abs(actual - expected) <= tolerance
    else:
        ok = actual == expected
    status = PASS if ok else FAIL
    results.append((section, item, expected, actual, status))
    symbol = "[OK]" if ok else "[FAIL]"
    print(f"  {symbol} {item}: expected={expected}, actual={actual}  [{status}]")
    return ok


def main():
    all_pass = True

    # ── Ports ──────────────────────────────────────────────
    print("\nPorts")
    with open(RAW_WS / "ports.csv", newline="", encoding="utf-8") as f:
        ports = list(csv.DictReader(f, delimiter="\t"))
    all_pass &= check("Ports", "rows", 47, len(ports))
    codes = [p["UNLocode"] for p in ports]
    all_pass &= check("Ports", "unique UNLOCODEs", 47, len(set(codes)))
    required = {"UNLocode", "name", "Longitude", "Latitude", "Draft",
                "CostPerFULL", "PortCallCostFixed"}
    missing = [k for k in required if k not in ports[0]]
    all_pass &= check("Ports", "missing fields", 0, len(missing), 0)

    # ── Demand ─────────────────────────────────────────────
    print("\nDemand")
    with open(RAW_WS / "Demand_WorldSmall_Fixed_Sep.csv", newline="", encoding="utf-8") as f:
        demands = list(csv.DictReader(f, delimiter="\t"))
    all_pass &= check("Demand", "rows", 1764, len(demands))
    origins = set(r["Origin"] for r in demands)
    dests = set(r["Destination"] for r in demands)
    all_pass &= check("Demand", "unique origins", 47, len(origins))
    all_pass &= check("Demand", "unique destinations", 47, len(dests))
    pairs = [(r["Origin"], r["Destination"]) for r in demands]
    all_pass &= check("Demand", "duplicate OD pairs", 0, len(pairs) - len(set(pairs)))
    nulls = sum(1 for r in demands
                if not r.get("Origin") or not r.get("Destination")
                or not r.get("FFEPerWeek") or not r.get("Revenue_1"))
    all_pass &= check("Demand", "null values", 0, nulls)
    # Every demand origin/dest must exist in ports
    port_set = set(p["UNLocode"] for p in ports)
    bad = [o for o in origins if o not in port_set] + \
          [d for d in dests if d not in port_set]
    all_pass &= check("Demand", "missing port references", 0, len(bad))
    # All demand/revenue values positive
    neg_demand = sum(1 for r in demands if float(r["FFEPerWeek"]) <= 0)
    neg_rev = sum(1 for r in demands if float(r["Revenue_1"]) <= 0)
    all_pass &= check("Demand", "negative demand values", 0, neg_demand)
    all_pass &= check("Demand", "negative revenue values", 0, neg_rev)

    # ── Fleet ──────────────────────────────────────────────
    print("\nFleet")
    with open(RAW_WS / "fleet_WorldSmall.csv", newline="", encoding="utf-8") as f:
        fleet = list(csv.DictReader(f, delimiter="\t"))
    all_pass &= check("Fleet", "classes", 6, len(fleet))
    total_vessels = sum(int(r["Quantity"]) for r in fleet)
    all_pass &= check("Fleet", "total vessels", 263, total_vessels)

    # ── Distance ───────────────────────────────────────────
    print("\nDistance")
    with open(RAW_WS / "dist_dense.csv", newline="", encoding="utf-8") as f:
        dist = list(csv.DictReader(f, delimiter="\t"))
    all_pass &= check("Distance", "pairs", 2162, len(dist))
    # Check no null/zero distances
    bad_dist = sum(1 for r in dist
                   if not r["Distance"] or float(r["Distance"]) <= 0)
    all_pass &= check("Distance", "invalid distances", 0, bad_dist)
    # Check no unexpected WorldLarge-only ports
    ws_dist_origins = set(r["fromUNLOCODe"] for r in dist)
    ws_dests_dist = set(r["ToUNLOCODE"] for r in dist)
    bad_ports = (ws_dist_origins | ws_dests_dist) - port_set
    all_pass &= check("Distance", "unexpected ports", 0, len(bad_ports))

    # ── JSON ───────────────────────────────────────────────
    print("\nJSON")
    with open(JSON_PATH, encoding="utf-8") as f:
        js = json.load(f)
    all_pass &= check("JSON", "ports", 47, len(js.get("ports", [])))
    all_pass &= check("JSON", "demands", 1764, len(js.get("demands", [])))
    dm = js.get("distance_matrix", {})
    all_pass &= check("JSON", "distance origins", 47, len(dm))
    total_dist_entries = sum(len(v) for v in dm.values())
    all_pass &= check("JSON", "distance entries", 2162, total_dist_entries)
    # Verify every demand endpoint exists in ports
    json_port_ids = {p["id"] for p in js.get("ports", [])}
    json_demands = js.get("demands", [])
    bad_ref = [d for d in json_demands
               if d["origin"] not in json_port_ids or d["destination"] not in json_port_ids]
    all_pass &= check("JSON", "demand port references", 0, len(bad_ref))
    # Verify services is empty
    all_pass &= check("JSON", "services empty", True, len(js.get("services", [])) == 0)

    # ── Print summary ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("WORLD SMALL DATASET VALIDATION")
    print("=" * 60)
    failed = [r for r in results if r[4] != PASS]
    for section, item, exp, act, status in results:
        symbol = "✓" if status == PASS else "✗"
        print(f"  {symbol} {section} / {item}: expected={exp}, actual={act}  [{status}]")
    print("-" * 60)
    if failed:
        print(f"FAILED: {len(failed)} check(s) did not pass")
        for _, item, exp, act, _ in failed:
            print(f"  ✗ {item}: expected={exp}, actual={act}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED — WorldSmall dataset validated successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
