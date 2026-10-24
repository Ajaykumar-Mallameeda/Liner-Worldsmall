"""Validation of a dataset package: schema, connectivity, units, constraints, source-to-JSON agreement.

``validate_dataset(spec)`` returns a list of check records ``{"check", "ok", "severity", "detail"}``.
``severity`` is ``"error"`` (the dataset must not be optimised) or ``"warning"`` (reported, not blocking).
It reads the package only through the production loader (so units are converted exactly once, there) and
the raw tables for the source-side counts; it never modifies anything.
"""
from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from src.data.dataset_registry import DatasetSpec, resolve_dataset
from src.data.problem_json import (ProblemJsonError, load_problem_json, problem_differences, validate_problem_dict)

EARTH_RADIUS_NM = 3440.065
DRAFT_TOL = 1e-9


def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(math.sqrt(a))


def _read_tsv(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


class _Checks(list):
    def add(self, name: str, ok: bool, detail: str = "", severity: str = "error"):
        self.append({"check": name, "ok": bool(ok), "severity": severity, "detail": detail})

    @property
    def blocking(self):
        return [c for c in self if not c["ok"] and c["severity"] == "error"]


def validate_dataset(dataset, *, check_json: bool = True, json_path: Optional[Path] = None) -> List[dict]:
    """Run every package check for ``dataset``; JSON checks are skipped (and reported) if ``check_json`` is False."""
    from src.data.network_loader import NetworkLoader, DataValidationError

    spec: DatasetSpec = resolve_dataset(dataset)
    ck = _Checks()

    # 1 --- the five source files exist (no fallback to another dataset)
    missing = spec.missing_inputs()
    ck.add("source files present", not missing, f"missing: {missing}" if missing else
           ", ".join(p.name for p in spec.input_paths().values()))
    if missing:
        return ck

    # 2 --- loader schema validation (header, numeric, duplicate keys, units, fleet-class agreement)
    loader = NetworkLoader(dataset=spec)
    try:
        net = loader.load_network()
        fleet = loader.load_fleet()
    except (DataValidationError, FileNotFoundError, ValueError) as exc:
        ck.add("loader schema validation", False, f"{type(exc).__name__}: {exc}")
        return ck
    ports, demands, matrix = net["ports"], net["demands"], net["distance_matrix"]
    rep = loader.validation_report
    ck.add("loader schema validation", True,
           f"{len(ports)} ports, {len(demands)} demands, {rep['distances']['directed_pairs']} directed pairs, "
           f"{len(fleet.classes)} classes")
    ck.add("no port excluded by the loader", not rep["ports"]["excluded"], f"{rep['ports']['excluded']}")

    ids = {p.id for p in ports}
    # 3 --- demand endpoints / unrelated records
    ends = {x for d in demands for x in (d.origin, d.destination)}
    ck.add("demand endpoints belong to the port set", ends <= ids, f"stray: {sorted(ends - ids)[:5]}")
    ck.add("every port is used by a demand", ends == ids, f"ports without demand: {sorted(ids - ends)[:5]}",
           severity="warning" if spec.kind == "real_linerlib" else "error")
    ck.add("no duplicate OD pairs / self loops", len({(d.origin, d.destination) for d in demands}) == len(demands)
           and all(d.origin != d.destination for d in demands))
    ck.add("demand values finite and positive",
           all(math.isfinite(d.weekly_teu) and d.weekly_teu > 0 and math.isfinite(d.revenue_per_teu)
               and d.revenue_per_teu > 0 for d in demands))
    ck.add("transit limits present, positive, in days",
           all(d.max_transit_days is not None and d.max_transit_days > 0 for d in demands),
           f"range {min(d.max_transit_days for d in demands):g}..{max(d.max_transit_days for d in demands):g} d"
           if all(d.max_transit_days for d in demands) else "missing transit limit")

    # 4 --- port attributes
    ck.add("port attributes valid (draft>0, coordinates, costs>=0)",
           all(p.draft > 0 and -90 <= p.latitude <= 90 and -180 <= p.longitude <= 180 and p.handling_cost >= 0
               and p.port_call_cost >= 0 and p.transshipment_cost >= 0 and p.variable_port_call_cost >= 0
               for p in ports))
    coords = Counter((p.latitude, p.longitude) for p in ports)
    dup_coord = [c for c, n in coords.items() if n > 1]
    ck.add("no two ports share a coordinate", not dup_coord, f"{dup_coord[:3]}", severity="warning")

    # 5 --- connectivity and distance integrity
    pairs = sum(len(r) for r in matrix.values())
    n = len(ids)
    ck.add("complete directed distance matrix", pairs == n * (n - 1) and all(
        o not in matrix.get(o, {}) for o in ids), f"{pairs} of {n * (n - 1)} directed pairs")
    ck.add("distances positive and finite",
           all(math.isfinite(v) and v > 0 for r in matrix.values() for v in r.values()))
    by = {p.id: p for p in ports}
    below = ratios = 0
    worst = 1e9
    culprits: Counter = Counter()
    for o, row in matrix.items():
        po = by[o]
        for d, v in row.items():
            pd_ = by[d]
            h = haversine_nm(po.latitude, po.longitude, pd_.latitude, pd_.longitude)
            if h > 1.0:
                r = v / h
                worst = min(worst, r)
                ratios += 1
                if r < 0.95:
                    below += 1
                    culprits[o] += 1
                    culprits[d] += 1
    top = ", ".join(f"{p} ({by[p].name}; lat {by[p].latitude}, lon {by[p].longitude}) in {n}"
                    for p, n in culprits.most_common(3))
    ck.add("distances not shorter than the geodesic (5% source margin)", below == 0,
           f"{below} of {ratios} pairs below 0.95 x geodesic; min ratio {worst:.3f}; ports most involved "
           f"(suspect coordinates in the source table): {top}",
           severity="warning" if spec.kind == "real_linerlib" else "error")
    asym = sum(1 for o, row in matrix.items() for d, v in row.items() if matrix.get(d, {}).get(o) not in (None, v))
    ck.add("distance symmetry (informational; directions are kept separate)", True,
           f"{asym} asymmetric directed pairs", severity="warning")
    flagged = set(matrix.canal_flags)
    ck.add("canal flags refer to existing pairs", all(o in matrix and d in matrix[o] for o, d in flagged))
    ck.add("edge drafts refer to existing pairs", all(o in matrix and d in matrix[o] for o, d in matrix.edge_draft))

    # 6 --- fleet / draft eligibility
    classes = {c.vessel_class: c for c in fleet.classes}
    ck.add("fleet classes exist in the class table with valid specs",
           all(c.capacity_teu > 0 and c.draft > 0 and c.min_speed <= c.design_speed <= c.max_speed for c in classes.values()))
    ck.add("fleet quantities non-negative integers and fleet non-empty",
           all(isinstance(c.quantity, int) and c.quantity >= 0 for c in classes.values()) and fleet.total_vessels > 0,
           f"{fleet.total_vessels} vessels: " + ", ".join(f"{k}={c.quantity}" for k, c in classes.items()))
    uncallable = [p.id for p in ports if not any(c.draft <= p.draft + DRAFT_TOL and c.quantity > 0
                                                 for c in classes.values())]
    ck.add("every port can be called by at least one owned class (draft)", not uncallable,
           f"{len(uncallable)} ports, e.g. {uncallable[:5]}")
    stranded = sum(d.weekly_teu for d in demands if d.origin in uncallable or d.destination in uncallable)
    ck.add("demand at ports no class can call", stranded == 0, f"{stranded:,.0f} TEU/week stranded", severity="warning")

    # 7 --- source-side counts vs the loaded problem (raw files read independently of the loader)
    paths = spec.input_paths()
    raw_ports, raw_dem = _read_tsv(paths["ports"]), _read_tsv(paths["demand"])
    raw_dist, raw_fleet = _read_tsv(paths["distance"]), _read_tsv(paths["fleet"])
    ck.add("source rows == loaded records",
           (len(raw_ports), len(raw_dem), len(raw_dist), len(raw_fleet)) ==
           (len(ports), len(demands), pairs, len(fleet.classes)),
           f"ports {len(raw_ports)}/{len(ports)}, demand {len(raw_dem)}/{len(demands)}, "
           f"distance {len(raw_dist)}/{pairs}, fleet {len(raw_fleet)}/{len(fleet.classes)}")
    raw_ffe = sum(float(r["FFEPerWeek"]) for r in raw_dem)
    ck.add("FFE -> TEU applied exactly once (TEU = 2 x source FFE)",
           math.isclose(sum(d.weekly_teu for d in demands), 2 * raw_ffe, rel_tol=1e-12),
           f"{raw_ffe:,.0f} FFE -> {sum(d.weekly_teu for d in demands):,.0f} TEU")
    ck.add("gross revenue preserved by the conversion",
           math.isclose(sum(d.weekly_teu * d.revenue_per_teu for d in demands),
                        sum(float(r["FFEPerWeek"]) * float(r["Revenue_1"]) for r in raw_dem), rel_tol=1e-9))
    raw_cap = {r["Vessel class"]: float(r["Capacity FFE"]) for r in _read_tsv(paths["fleet_data"])}
    ck.add("capacity converted exactly once (TEU = 2 x Capacity FFE)",
           all(math.isclose(c.capacity_teu, 2 * raw_cap[k], rel_tol=1e-12) for k, c in classes.items()))

    # 8 --- canonical JSON agrees with the package
    if not check_json:
        ck.add("canonical JSON checked", True, "skipped by request", severity="warning")
        return ck
    jp = Path(json_path) if json_path else spec.json_path
    if not jp.is_file():
        ck.add("canonical JSON present", False, f"{jp} not found")
        return ck
    try:
        jproblem, meta = load_problem_json(spec, jp)
    except ProblemJsonError as exc:
        ck.add("canonical JSON valid", False, str(exc))
        return ck
    ck.add("canonical JSON valid and declares this dataset", True, f"{meta['counts']}")
    from src.optimization.data import Problem
    csv_problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=matrix, fleet=fleet)
    diffs = problem_differences(csv_problem, jproblem)
    ck.add("JSON == CSV package (every field the optimizer reads)", not diffs, "; ".join(diffs) or "identical")
    return ck


def summarize(checks: List[dict]) -> Dict[str, int]:
    return {"checks": len(checks), "passed": sum(c["ok"] for c in checks),
            "blocking_failures": sum((not c["ok"]) and c["severity"] == "error" for c in checks),
            "warnings": sum((not c["ok"]) and c["severity"] == "warning" for c in checks)}
