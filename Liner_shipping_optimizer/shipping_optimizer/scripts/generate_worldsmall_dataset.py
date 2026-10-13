#!/usr/bin/env python3
"""
Generate WorldSmall benchmark dataset package and structured JSON.

This script reads the official LINERLIB WorldSmall source files and produces:
  1. Filtered CSV files in data/raw/WorldSmall/
  2. A structured JSON in data/datasets/worldsmall_shipping_problem.json

Conversion rules (documented):
  - Ports: UNLocode -> id, Latitude/Lon -> latitude/longitude
    handling_cost = CostPerFULL * 2  (matching existing large JSON convention)
    transshipment_cost = CostPerFULLTrnsf * 2
    variable_port_call_cost = PortCallCostPerFFE * 2  (FFE -> TEU conversion)
  - Demand: FFEPerWeek * 2 = weekly_teu; Revenue_1 * 2 = revenue_per_teu
    (matching existing large JSON convention)
  - Distance: raw distance values used as-is
  - Services: intentionally left empty — derived layer, not raw LINERLIB data
"""

import csv
import hashlib
import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent
RAW_GLOBAL = BASE / "data" / "raw"
RAW_WS = BASE / "data" / "raw" / "WorldSmall"
DS_DIR = BASE / "data" / "datasets"
REPORTS_DIR = BASE / "reports"

# Source files (global originals)
PORTS_SRC = RAW_GLOBAL / "ports.csv"
DIST_SRC = RAW_GLOBAL / "distance_dense.csv"
DEMAND_SRC = RAW_WS / "Demand_WorldSmall_Fixed_Sep.csv"
FLEET_SRC = RAW_WS / "fleet_WorldSmall.csv"
FLEET_DATA_SRC = RAW_WS / "fleet_data.csv"

# Output files
PORTS_OUT = RAW_WS / "ports.csv"
DIST_OUT = RAW_WS / "dist_dense.csv"
DEMAND_OUT = RAW_WS / "Demand_WorldSmall_Fixed_Sep.csv"
FLEET_OUT = RAW_WS / "fleet_WorldSmall.csv"
FLEET_DATA_OUT = RAW_WS / "fleet_data.csv"
JSON_OUT = DS_DIR / "worldsmall_shipping_problem.json"
HASH_FILE = REPORTS_DIR / "worldsmall_hashes.txt"


def read_tab_csv(path: Path) -> list[dict]:
    """Read a tab-separated CSV file and return list of dicts.

    Handles the LINERLIB quirk where the header row may be written as a
    single field containing embedded tabs (e.g. 'col1\tcol2\t...').
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter="\t")
        raw_header = next(reader)
        # If the first row has only one element that contains tabs, re-split it
        if len(raw_header) == 1 and "\t" in raw_header[0]:
            fieldnames = raw_header[0].split("\t")
        else:
            fieldnames = raw_header
        rows = []
        for row in reader:
            if len(row) == 1 and "\t" in row[0]:
                row = row[0].split("\t")
            rows.append(dict(zip(fieldnames, row)))
        return rows


def write_tab_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    """Write list of dicts as tab-separated CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Step 1: Determine WorldSmall port set from demand file
# ---------------------------------------------------------------------------
print("=" * 60)
print("Generating LINERLIB WorldSmall dataset")
print("=" * 60)

demand_rows = read_tab_csv(DEMAND_SRC)
all_ports_in_demand = sorted({row["Origin"] for row in demand_rows} |
                             {row["Destination"] for row in demand_rows})
print(f"\n[1] WorldSmall port set: {len(all_ports_in_demand)} ports")
for p in all_ports_in_demand:
    print(f"    {p}")

# ---------------------------------------------------------------------------
# Step 2: Copy raw source files as-is
# ---------------------------------------------------------------------------
import shutil

print("\n[2] Copying raw source files to data/raw/WorldSmall/")
for src, dst in [
    (DEMAND_SRC, DEMAND_OUT),
    (FLEET_SRC, FLEET_OUT),
    (FLEET_DATA_SRC, FLEET_DATA_OUT),
]:
    if src.resolve() == dst.resolve():
        print(f"    {dst.name} (same file, skipping copy)")
    else:
        shutil.copy2(src, dst)
        print(f"    {dst.name} ({dst.stat().st_size} bytes)")

# ---------------------------------------------------------------------------
# Step 3: Filter ports.csv to WorldSmall ports
# ---------------------------------------------------------------------------
print("\n[3] Filtering ports.csv to WorldSmall ports")
all_ports_raw = read_tab_csv(PORTS_SRC)
ws_ports = [p for p in all_ports_raw if p["UNLocode"] in all_ports_in_demand]
ws_ports.sort(key=lambda r: r["UNLocode"])
write_tab_csv(PORTS_OUT, ws_ports, list(ws_ports[0].keys()))
print(f"    Wrote {len(ws_ports)} ports to {PORTS_OUT}")

# ---------------------------------------------------------------------------
# Step 4: Filter dist_dense.csv to WorldSmall ports
# ---------------------------------------------------------------------------
print("\n[4] Filtering dist_dense.csv to WorldSmall ports")
all_dist_raw = read_tab_csv(DIST_SRC)
# Filter to WorldSmall ports, excluding self-pairs, then deduplicate
# (global distance_dense.csv may contain duplicate entries for the same pair)
seen_pairs = set()
ws_dist = []
for d in all_dist_raw:
    orig = d["fromUNLOCODe"]
    dest = d["ToUNLOCODE"]
    if orig not in all_ports_in_demand:
        continue
    if dest not in all_ports_in_demand:
        continue
    if orig == dest:
        continue
    pair_key = (orig, dest)
    if pair_key in seen_pairs:
        continue
    seen_pairs.add(pair_key)
    ws_dist.append(d)
ws_dist.sort(key=lambda r: (r["fromUNLOCODe"], r["ToUNLOCODE"]))
write_tab_csv(DIST_OUT, ws_dist, list(ws_dist[0].keys()))
print(f"    Wrote {len(ws_dist)} distance pairs to {DIST_OUT}")

# Validate expected count
expected_pairs = len(all_ports_in_demand) * (len(all_ports_in_demand) - 1)
if len(ws_dist) != expected_pairs:
    print(f"    WARNING: Expected {expected_pairs} pairs, got {len(ws_dist)}")
else:
    print(f"    OK: {expected_pairs} directed pairs (47x46)")

# ---------------------------------------------------------------------------
# Step 5: Generate structured JSON
# ---------------------------------------------------------------------------
print("\n[5] Generating worldsmall_shipping_problem.json")

# --- Ports ---
json_ports = []
for p in ws_ports:
    json_ports.append({
        "id": p["UNLocode"],
        "name": p["name"],
        "latitude": float(p["Latitude"]),
        "longitude": float(p["Longitude"]),
        # Conversion: multiply costs by 2 (matching large JSON convention)
        "handling_cost": round(float(p["CostPerFULL"]) * 2, 2),
        "draft": float(p["Draft"]),
        "port_call_cost": float(p["PortCallCostFixed"]),
        "transshipment_cost": round(float(p["CostPerFULLTrnsf"]) * 2, 2),
        # Variable port call cost: PortCallCostPerFFE converted to TEU basis
        "variable_port_call_cost": round(float(p["PortCallCostPerFFE"]) * 2.0, 2),
    })

# --- Demands ---
json_demands = []
for row in demand_rows:
    ffe = float(row["FFEPerWeek"])
    rev = float(row["Revenue_1"])
    json_demands.append({
        "origin": row["Origin"],
        "destination": row["Destination"],
        # FFE -> TEU: * 2 (matches existing convention)
        "weekly_teu": round(ffe * 2, 2),
        # Revenue conversion: * 2 (matches existing convention)
        "revenue_per_teu": round(rev * 2, 2),
    })

# --- Distance matrix ---
json_dist = {}
for d in ws_dist:
    orig = d["fromUNLOCODe"]
    dest = d["ToUNLOCODE"]
    val = d["Distance"]
    if val == "" or val is None:
        continue
    if orig not in json_dist:
        json_dist[orig] = {}
    json_dist[orig][dest] = float(val)

# Ensure all 47 ports appear as keys (even with empty dicts)
for p in all_ports_in_demand:
    if p not in json_dist:
        json_dist[p] = {}

# Sort deterministically
json_dist = dict(sorted(json_dist.items()))
for k in json_dist:
    json_dist[k] = dict(sorted(json_dist[k].items()))

# --- Services (empty — derived layer, not raw data) ---
# Note: Services are not part of the raw LINERLIB WorldSmall dataset.
# They must be generated by the optimization/service-generation layer.
json_services = []

# --- Assemble JSON ---
problem = {
    "ports": json_ports,
    "demands": json_demands,
    "services": json_services,
    "distance_matrix": json_dist,
}

DS_DIR.mkdir(parents=True, exist_ok=True)
with open(JSON_OUT, "w", encoding="utf-8") as f:
    json.dump(problem, f, ensure_ascii=False, indent=2)

print(f"    Wrote {JSON_OUT} ({JSON_OUT.stat().st_size} bytes)")

# ---------------------------------------------------------------------------
# Step 6: Compute hashes
# ---------------------------------------------------------------------------
print("\n[6] Computing SHA-256 hashes")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
hash_lines = []
for label, fpath in [
    ("SOURCE Demand_WorldSmall_Fixed_Sep.csv", DEMAND_SRC),
    ("SOURCE fleet_WorldSmall.csv", FLEET_SRC),
    ("SOURCE fleet_data.csv", FLEET_DATA_SRC),
    ("SOURCE ports.csv", PORTS_SRC),
    ("SOURCE distance_dense.csv", DIST_SRC),
    ("GEN WorldSmall/ports.csv", PORTS_OUT),
    ("GEN WorldSmall/dist_dense.csv", DIST_OUT),
    ("GEN worldsmall_shipping_problem.json", JSON_OUT),
]:
    h = sha256_file(fpath)
    hash_lines.append(f"{h}  {label}")
    print(f"    {h}  {label}")

with open(HASH_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(hash_lines) + "\n")

print(f"\n    Hashes saved to {HASH_FILE}")
print("\nDone.")
