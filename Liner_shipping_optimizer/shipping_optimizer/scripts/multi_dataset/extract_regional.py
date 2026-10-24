#!/usr/bin/env python3
"""Extract the LINERLIB regional instances (Baltic, WAF) into their own ``data/raw/<dataset>`` packages.

Source: the LINERLIB-master archive (tab-delimited despite the ``.csv`` extension). The repository copy
``data/LINERLIB-master`` is verified byte-for-byte against the archive when ``--zip`` is given.

Per dataset the script writes (selected RAW source lines - nothing is re-serialised, nothing invented):

    ports.csv                    ports of the instance (every port of the demand file), source columns/values
    Demand_<X>.csv               the source demand file (byte copy)
    dist_dense.csv               ONE record per directed pair: the model-selected alternative (see below)
    dist_dense_all_alternatives.csv   EVERY source record among the instance's ports (all route alternatives)
    fleet_<X>.csv                the source regional fleet file (byte copy)
    fleet_data.csv               the source rows of the classes the regional fleet uses (header + selected rows)
    Demand_WAF_tt.csv            (WAF only) the source's revised-transit-time variant, kept for provenance;
                                 NOT used by default (WorldSmall's accepted C3 uses the original TransitTime)

Route alternatives: ``dist_dense.csv`` of LINERLIB lists, for some pairs, several records (e.g. through
Suez and around the Cape, with ``IsSuez`` / ``Draft`` flags). The accepted model takes ONE distance per
directed pair together with its canal flags (``LinerDistanceMatrix``). WorldSmall's canonical file is the
FIRST listed record of every pair, and in the whole source that is also the SHORTEST record. The same rule
is applied here and is *verified*, not assumed: the script fails if the first record is not the shortest
or if two records tie with different canal flags. The unselected alternatives are preserved (all-alternatives
file, and ``distance_alternatives`` in the canonical JSON), so nothing is silently dropped.

Never overwrites a file whose content differs (it stops instead); never deletes.

    python scripts/multi_dataset/extract_regional.py [--source DIR] [--zip ZIP] [--out-root DIR] [--datasets baltic WAF]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_SOURCE = ROOT / "data" / "LINERLIB-master" / "data"
DEFAULT_OUT_ROOT = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports" / "multi_dataset_20261016" / "01_regional_extraction"

# registry key -> (directory name, source demand, source fleet, revised transit variant)
REGIONAL = {
    "baltic": ("baltic", "Demand_Baltic.csv", "fleet_Baltic.csv", None),
    "WAF": ("WAF", "Demand_WAF.csv", "fleet_WAF.csv", "transittime_revision/Demand_WAF_tt.csv"),
}
PORT_COLS = ["UNLocode", "name", "Country", "Cabotage_Region", "D_Region", "Longitude", "Latitude", "Draft",
             "CostPerFULL", "CostPerFULLTrnsf", "PortCallCostFixed", "PortCallCostPerFFE"]
NUMERIC_PORT_COLS = ["Longitude", "Latitude", "Draft", "CostPerFULL", "CostPerFULLTrnsf",
                     "PortCallCostFixed", "PortCallCostPerFFE"]
DIST_COLS = ["fromUNLOCODe", "ToUNLOCODE", "Distance", "Draft", "IsPanama", "IsSuez"]


class ExtractionError(RuntimeError):
    pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_lines(path: Path):
    """(header_line_bytes, [(raw_line_bytes, fields)]) of a tab-delimited file; raw lines are kept verbatim."""
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    if not lines:
        raise ExtractionError(f"{path.name}: empty file")
    header = lines[0].decode("utf-8").rstrip("\r\n").split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        rows.append((ln, ln.decode("utf-8").rstrip("\r\n").split("\t")))
    return lines[0], header, rows


def verify_zip(source: Path, zip_path: Path) -> dict:
    """Every file of the archive's ``data`` tree must equal the repository copy byte for byte."""
    checked = diffs = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir() or "/data/" not in info.filename:
                continue
            rel = info.filename.split("/data/", 1)[1]
            target = source / rel
            checked += 1
            if not target.is_file() or sha256_bytes(z.read(info)) != sha256_bytes(target.read_bytes()):
                diffs += 1
    if diffs:
        raise ExtractionError(f"{diffs} of {checked} data files differ between {zip_path.name} and {source}")
    return {"zip": str(zip_path), "zip_sha256": sha256_bytes(zip_path.read_bytes()), "data_files_checked": checked,
            "differences": 0}


def write_new(path: Path, data: bytes, written: list):
    """Create ``path``; an existing file must already hold exactly these bytes (never overwritten)."""
    if path.exists():
        if path.read_bytes() != data:
            raise ExtractionError(f"{path} exists with different content; refusing to overwrite (no deletion policy)")
        written.append((path, "unchanged"))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    written.append((path, "written"))


def extract(key: str, source: Path, out_root: Path) -> dict:
    dirname, demand_name, fleet_name, tt_name = REGIONAL[key]
    out = out_root / dirname
    report: dict = {"dataset": key, "source_dir": str(source), "issues": [], "checks": {}}
    issues = report["issues"]

    # ---------------------------------------------------------------- source files
    d_hdr, d_cols, d_rows = read_lines(source / demand_name)
    if d_cols != ["Origin", "Destination", "FFEPerWeek", "Revenue_1", "TransitTime"]:
        raise ExtractionError(f"{demand_name}: unexpected header {d_cols}")
    f_hdr, f_cols, f_rows = read_lines(source / fleet_name)
    fd_hdr, fd_cols, fd_rows = read_lines(source / "fleet_data.csv")
    p_hdr, p_cols, p_rows = read_lines(source / "ports.csv")
    s_hdr, s_cols, s_rows = read_lines(source / "dist_dense.csv")
    if p_cols != PORT_COLS:
        raise ExtractionError(f"ports.csv: unexpected header {p_cols}")
    if s_cols != DIST_COLS:
        raise ExtractionError(f"dist_dense.csv: unexpected header {s_cols}")

    # ---------------------------------------------------------------- demand + port set (derived from the source demand)
    seen = {}
    for n, (_, f) in enumerate(d_rows, start=2):
        if len(f) != 5 or any(x == "" for x in f):
            issues.append(f"{demand_name} line {n}: blank or short field {f}")
            continue
        if f[0] == f[1]:
            issues.append(f"{demand_name} line {n}: self loop {f[0]}")
        if (f[0], f[1]) in seen:
            issues.append(f"{demand_name} line {n}: duplicate OD {f[0]}->{f[1]} (first line {seen[(f[0], f[1])]})")
        seen[(f[0], f[1])] = n
        for col, val in zip(d_cols[2:], f[2:]):
            try:
                if not float(val) > 0:
                    issues.append(f"{demand_name} line {n}: {col}={val} is not > 0")
            except ValueError:
                issues.append(f"{demand_name} line {n}: {col}={val!r} is not numeric")
    port_ids = sorted({f[0] for _, f in d_rows} | {f[1] for _, f in d_rows})
    report["checks"]["demand_rows"] = len(d_rows)
    report["checks"]["unique_od_pairs"] = len(seen)
    report["checks"]["ports_from_demand"] = len(port_ids)

    # ---------------------------------------------------------------- ports
    by_id = {}
    for n, (raw, f) in enumerate(p_rows, start=2):
        if f[0] in by_id:
            issues.append(f"ports.csv line {n}: duplicate port {f[0]}")
        by_id[f[0]] = (raw, f)
    missing_ports = [p for p in port_ids if p not in by_id]
    if missing_ports:
        issues.append(f"demand ports absent from ports.csv: {missing_ports}")
    sel_ports = []
    for pid in port_ids:
        if pid not in by_id:
            continue
        raw, f = by_id[pid]
        rec = dict(zip(PORT_COLS, f))
        blanks = [c for c in PORT_COLS if rec.get(c, "") == ""]
        if blanks:
            issues.append(f"port {pid}: blank required field(s) {blanks}")
        for c in NUMERIC_PORT_COLS:
            try:
                float(rec[c])
            except (ValueError, KeyError):
                issues.append(f"port {pid}: {c}={rec.get(c)!r} is not numeric")
        try:
            lat, lon = float(rec["Latitude"]), float(rec["Longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                issues.append(f"port {pid}: coordinates out of range ({lat}, {lon})")
            if float(rec["Draft"]) <= 0:
                issues.append(f"port {pid}: impossible draft {rec['Draft']}")
            for c in ("CostPerFULL", "CostPerFULLTrnsf", "PortCallCostFixed", "PortCallCostPerFFE"):
                if float(rec[c]) < 0:
                    issues.append(f"port {pid}: negative {c}={rec[c]}")
        except (ValueError, KeyError):
            pass
        sel_ports.append(raw)

    # ---------------------------------------------------------------- distances: all alternatives and the selected record
    idset = set(port_ids)
    all_alt = []
    groups: dict = {}
    for raw, f in s_rows:
        if f[0] in idset and f[1] in idset and f[0] != f[1]:
            all_alt.append(raw)
            groups.setdefault((f[0], f[1]), []).append((raw, f))
    selected = {}
    n_alt_pairs = 0
    for pair, recs in groups.items():
        dists = []
        for raw, f in recs:
            try:
                d = float(f[2])
            except ValueError:
                issues.append(f"dist_dense {pair}: non-numeric Distance {f[2]!r}")
                d = math.inf
            if not d > 0:
                issues.append(f"dist_dense {pair}: non-positive Distance {f[2]!r}")
            dists.append(d)
        first_d = dists[0]
        best = min(dists)
        if len(recs) > 1:
            n_alt_pairs += 1
            if first_d != best:
                issues.append(f"dist_dense {pair}: first listed record ({first_d}) is not the shortest ({best}); "
                              f"the accepted selection rule cannot be applied unchanged")
            ties = [r for r, d in zip(recs, dists) if d == best]
            if len({(r[1][4], r[1][5], r[1][3]) for r in ties}) > 1:
                issues.append(f"dist_dense {pair}: tie between records with different canal/draft attributes")
        selected[pair] = recs[0][0]
    ordered_pairs = sorted(selected)
    missing_pairs = [(a, b) for a in port_ids for b in port_ids if a != b and (a, b) not in selected]
    if missing_pairs:
        issues.append(f"{len(missing_pairs)} directed port pairs have no distance record, e.g. {missing_pairs[:5]}")
    # symmetry of the selected distances (informational: the loader keeps directions separate)
    sel_d = {p: float(selected[p].decode().split("\t")[2]) for p in selected}
    asym = sum(1 for (a, b), v in sel_d.items() if (b, a) in sel_d and sel_d[(b, a)] != v)
    report["checks"].update({
        "distance_records_all_alternatives": len(all_alt), "directed_pairs_selected": len(selected),
        "pairs_with_alternatives": n_alt_pairs, "expected_directed_pairs": len(port_ids) * (len(port_ids) - 1),
        "selected_pairs_asymmetric": asym,
        "canal_flagged_selected_pairs": sum(1 for raw in selected.values()
                                            if raw.decode().rstrip("\r\n").split("\t")[4:6] != ["0", "0"]),
    })

    # ---------------------------------------------------------------- fleet
    if f_cols != ["Vessel class", "Quantity"]:
        raise ExtractionError(f"{fleet_name}: unexpected header {f_cols}")
    classes = [f[0] for _, f in f_rows]
    if len(set(classes)) != len(classes):
        issues.append(f"{fleet_name}: duplicate vessel class")
    spec_by_class = {f[0]: raw for raw, f in fd_rows}
    absent = [c for c in classes if c not in spec_by_class]
    if absent:
        issues.append(f"fleet classes absent from the canonical fleet_data.csv: {absent}")
    sel_spec = [raw for raw, f in fd_rows if f[0] in classes]          # source order, source bytes
    for _, f in f_rows:
        try:
            if int(f[1]) < 0:
                issues.append(f"{fleet_name}: negative quantity for {f[0]}")
        except ValueError:
            issues.append(f"{fleet_name}: non-integer quantity {f[1]!r} for {f[0]}")
    # physical sanity: a class can only call at ports with draft >= class draft (LINERLIB draft rule)
    spec_rec = {f[0]: dict(zip(fd_cols, f)) for _, f in fd_rows}
    elig = {}
    for pid in port_ids:
        if pid in by_id:
            pd_ = float(by_id[pid][1][PORT_COLS.index("Draft")])
            elig[pid] = [c for c in classes if c in spec_rec and float(spec_rec[c]["draft"]) <= pd_ + 1e-9]
    no_class = [p for p, c in elig.items() if not c]
    if no_class:
        issues.append(f"ports no regional fleet class may call at (draft): {no_class}")
    report["checks"].update({"fleet_classes": classes, "fleet_total_vessels": sum(int(f[1]) for _, f in f_rows),
                             "ports_without_eligible_class": no_class})

    # ---------------------------------------------------------------- stop on any source problem BEFORE writing
    report["valid"] = not issues
    if issues:
        return report

    # ---------------------------------------------------------------- write the package
    written: list = []
    write_new(out / "ports.csv", p_hdr + b"".join(sel_ports), written)
    write_new(out / demand_name, (source / demand_name).read_bytes(), written)
    write_new(out / "dist_dense.csv", s_hdr + b"".join(selected[p] for p in ordered_pairs), written)
    write_new(out / "dist_dense_all_alternatives.csv", s_hdr + b"".join(all_alt), written)
    write_new(out / fleet_name, (source / fleet_name).read_bytes(), written)
    write_new(out / "fleet_data.csv", fd_hdr + b"".join(sel_spec), written)
    if tt_name:
        write_new(out / Path(tt_name).name, (source / tt_name).read_bytes(), written)
    report["files"] = {p.name: {"path": str(p), "state": st, "sha256": sha256_bytes(p.read_bytes()), "bytes": p.stat().st_size}
                       for p, st in written}
    report["source_hashes"] = {n: sha256_bytes((source / n).read_bytes()) for n in
                               ("ports.csv", "dist_dense.csv", "fleet_data.csv", demand_name, fleet_name)
                               + ((tt_name,) if tt_name else ())}
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--zip", type=Path, default=None, help="LINERLIB archive to verify the source copy against")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--datasets", nargs="+", default=list(REGIONAL), choices=list(REGIONAL))
    ap.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    a = ap.parse_args(argv)

    summary = {"source": str(a.source)}
    if a.zip:
        summary["archive_verification"] = verify_zip(a.source, a.zip)
        print("archive verified:", summary["archive_verification"])
    a.report_dir.mkdir(parents=True, exist_ok=True)
    rc = 0
    for key in a.datasets:
        rep = extract(key, a.source, a.out_root)
        summary[key] = rep
        (a.report_dir / f"{key}_extraction.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
        print(f"[{key}] valid={rep['valid']} checks={json.dumps(rep['checks'])}")
        for i in rep["issues"]:
            print(f"   ISSUE: {i}")
        rc |= 0 if rep["valid"] else 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
