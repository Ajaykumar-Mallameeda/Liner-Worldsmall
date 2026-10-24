"""Canonical JSON problem file of a dataset (one per dataset, schema ``liner-shipping-problem`` v1).

The pre-existing problem files (``data/datasets/worldsmall_shipping_problem.json``,
``large_shipping_problem.json``) carry only ports / demands / services / distance_matrix, were generated
with a legacy x2 unit convention and have no fleet, canal flags, draft limits or transit limits - the
optimizer's production path never read them (``NetworkLoader.load_problem`` even rejects the WorldSmall
one). This schema keeps their four keys and their record field names (so ``Port(**p)`` / ``Demand(**d)``
still work) and adds what the optimizer, the candidate generator and the independent ledger actually need.

Units: every value is stored AFTER the loader-boundary conversion (``NetworkLoader``: 1 FFE = 2 TEU;
capacity x2, demand x2, per-FFE rates / 2). The file is built from the package by the loader itself, so
the conversion happens exactly once, at the loader boundary, and ``load_problem_json`` applies none.

    ports[]            id name latitude longitude handling_cost[USD/TEU] draft[m] port_call_cost[USD/call]
                       transshipment_cost[USD/TEU] variable_port_call_cost[USD/TEU]
    demands[]          origin destination weekly_teu[TEU/wk] revenue_per_teu[USD/TEU] max_transit_days[d]
    services[]         always empty (generated at run time)
    distance_matrix    {origin: {destination: nautical miles}}  the record the model uses for every directed pair
    canal_flags[]      [origin, destination, is_panama, is_suez]  of the used record
    edge_draft[]       [origin, destination, draft_limit_m]       of the used record
    distance_alternatives[]  every source record of pairs that have more than one (selected one marked)
    fleet              capacity_unit(+status, source column) and classes[]: every FleetClass field (quantity, capacity,
                       hire rate, draft, speeds, consumption, canal fees - null = blank in the source)
    provenance         converter version, build id, input file hashes

Nothing in the file is a timestamp: an unchanged package and converter produce identical bytes.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.data.dataset_registry import DatasetSpec, PROJECT_ROOT, resolve_dataset, sha256_file
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

SCHEMA_NAME = "liner-shipping-problem"
SCHEMA_VERSION = 1
CONVERTER_VERSION = "1.0.1"

_PORT_FIELDS = ("id", "name", "latitude", "longitude", "handling_cost", "draft", "port_call_cost",
                "transshipment_cost", "variable_port_call_cost")
_DEMAND_FIELDS = ("origin", "destination", "weekly_teu", "revenue_per_teu", "max_transit_days")
_CLASS_FIELDS = tuple(f.name for f in dataclasses.fields(FleetClass))        # the dataclass is the schema
_TOP_KEYS = ("schema", "schema_version", "dataset", "units", "ports", "demands", "services", "distance_matrix",
             "canal_flags", "edge_draft", "distance_alternatives", "fleet", "provenance")

UNITS = {
    "distance": "nautical miles", "demand": "TEU per week (= 2 x source FFEPerWeek)",
    "revenue_per_teu": "USD per TEU (= source Revenue_1 / 2)", "capacity": "TEU per vessel (= 2 x source Capacity FFE)",
    "handling_cost": "USD per TEU (= source CostPerFULL / 2)", "transshipment_cost": "USD per TEU (= source CostPerFULLTrnsf / 2)",
    "variable_port_call_cost": "USD per TEU (= source PortCallCostPerFFE / 2)", "port_call_cost": "USD per call (unchanged)",
    "draft": "metres", "max_transit_days": "days (source TransitTime, interpreted as days)",
    "vessel_hire_rate": "USD per vessel-day", "canal_fee": "USD per transit (null = blank in source: class cannot pass)",
    "conversion": "applied once at the NetworkLoader boundary when the file is built; load_problem_json applies none",
}


class ProblemJsonError(ValueError):
    """The canonical problem file is missing, malformed, of another dataset, or inconsistent."""


# -- distance alternatives
ALTERNATIVES_SOURCES = {
    # dataset -> ("own", file inside raw_dir) | ("shared", path of a genuinely invariant LINERLIB reference file)
    "WorldSmall": ("shared", PROJECT_ROOT / "data" / "LINERLIB-master" / "data" / "dist_dense.csv"),
    "baltic": ("own", "dist_dense_all_alternatives.csv"),
    "WAF": ("own", "dist_dense_all_alternatives.csv"),
}


def _rel(p) -> str:
    try:
        return str(Path(p).relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:                       # a temporary / external location (tests)
        return str(p)


def _alternatives_file(spec: DatasetSpec) -> Optional[Tuple[str, Path]]:
    src = ALTERNATIVES_SOURCES.get(spec.key)
    if src is None:
        return None
    kind, ref = src
    return kind, (spec.raw_dir / ref if kind == "own" else Path(ref))


def read_distance_alternatives(spec: DatasetSpec, port_ids) -> Tuple[List[dict], Optional[dict]]:
    """Source records of the dataset's directed pairs that have more than one record, plus the reference used."""
    src = _alternatives_file(spec)
    if src is None:
        return [], None
    kind, path = src
    if not path.is_file():
        raise ProblemJsonError(f"{spec.key}: distance-alternatives source not found: {path}")
    ids = set(port_ids)
    groups: Dict[Tuple[str, str], List[dict]] = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            o, d = r["fromUNLOCODe"].strip(), r["ToUNLOCODE"].strip()
            if o in ids and d in ids and o != d:
                groups.setdefault((o, d), []).append({
                    "distance": float(r["Distance"]), "draft": float(r["Draft"]) if r["Draft"].strip() else None,
                    "is_panama": int(float(r["IsPanama"] or 0)), "is_suez": int(float(r["IsSuez"] or 0))})
    out = []
    for (o, d), recs in groups.items():
        if len(recs) > 1:
            recs[0]["selected"] = True            # WorldSmall's accepted rule: first listed record (= the shortest)
            for r in recs[1:]:
                r["selected"] = False
            out.append({"from": o, "to": d, "records": recs})
    out.sort(key=lambda x: (x["from"], x["to"]))
    ref = {"kind": kind, "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/") if path.is_relative_to(PROJECT_ROOT) else str(path),
           "sha256": sha256_file(path), "pairs_in_dataset": len(groups), "pairs_with_alternatives": len(out),
           "shared_reference": kind == "shared"}
    return out, ref


# -- build
def build_problem_dict(spec: DatasetSpec, converter_version: str = CONVERTER_VERSION) -> Tuple[dict, dict]:
    """(problem dict, loader validation report) of ``spec``'s source package, via the production loader."""
    from src.data.network_loader import NetworkLoader          # local import: network_loader imports the registry

    spec.require_inputs()
    loader = NetworkLoader(dataset=spec)
    net = loader.load_network()
    fleet = loader.load_fleet()
    matrix = net["distance_matrix"]
    ports = net["ports"]

    alternatives, alt_ref = read_distance_alternatives(spec, [p.id for p in ports])
    for a in alternatives:                                       # the selected record must be the one the model uses
        sel = next(r for r in a["records"] if r["selected"])
        used = matrix[a["from"]][a["to"]]
        if sel["distance"] != used:
            raise ProblemJsonError(f"{spec.key}: {a['from']}->{a['to']} selected alternative {sel['distance']} "
                                   f"differs from the package distance {used}")

    inputs = {role: {"file": p.name, "sha256": sha256_file(p), "bytes": p.stat().st_size}
              for role, p in spec.input_paths().items()}
    build_id = hashlib.sha256(json.dumps(
        {"schema": SCHEMA_VERSION, "converter": converter_version, "dataset": spec.key,
         "inputs": {k: v["sha256"] for k, v in sorted(inputs.items())},
         "alternatives": alt_ref["sha256"] if alt_ref else None}, sort_keys=True).encode()).hexdigest()

    obj = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "dataset": {"key": spec.key, "label": spec.label, "kind": spec.kind,
                    "source_dir": _rel(spec.raw_dir)},
        "units": UNITS,
        "ports": [{f: getattr(p, f) for f in _PORT_FIELDS} for p in ports],
        "demands": [{f: getattr(d, f) for f in _DEMAND_FIELDS} for d in net["demands"]],
        "services": [],
        "distance_matrix": {o: dict(row) for o, row in matrix.items()},
        "canal_flags": [[o, d, int(p), int(s)] for (o, d), (p, s) in matrix.canal_flags.items()],
        "edge_draft": [[o, d, v] for (o, d), v in matrix.edge_draft.items()],
        "distance_alternatives": alternatives,
        "fleet": {"capacity_unit": fleet.capacity_unit, "capacity_unit_status": fleet.capacity_unit_status,
                  "capacity_source_column": fleet.capacity_source_column,
                  "classes": [{f: getattr(c, f) for f in _CLASS_FIELDS} for c in fleet.classes]},
        "provenance": {"converter_version": converter_version, "build_id": build_id, "inputs": inputs,
                       "distance_alternatives_source": alt_ref,
                       "selection_rule": "one record per directed pair = the first listed = the shortest (verified)"},
    }
    return obj, loader.validation_report


# -- deterministic writer
def _compact(v: Any) -> str:
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def dumps_problem(obj: dict) -> bytes:
    """Deterministic bytes: one top-level key per entry, one record / matrix row per line, no timestamps."""
    parts = []
    for k, v in obj.items():
        if isinstance(v, list) and v and isinstance(v[0], (dict, list)):
            body = "[\n" + ",\n".join(_compact(e) for e in v) + "\n]"
        elif isinstance(v, dict) and k == "distance_matrix":
            body = "{\n" + ",\n".join(f"{_compact(o)}:{_compact(row)}" for o, row in v.items()) + "\n}"
        else:
            body = _compact(v)
        parts.append(f"{_compact(k)}:{body}")
    return ("{\n" + ",\n".join(parts) + "\n}\n").encode("utf-8")


# -- schema validation + load
def validate_problem_dict(obj: Any, spec: Optional[DatasetSpec] = None) -> None:
    """Raise ``ProblemJsonError`` unless ``obj`` is a well-formed canonical problem of ``spec``."""
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA_NAME:
        raise ProblemJsonError(
            "not a canonical liner-shipping-problem file (missing/other 'schema'); historical problem files "
            "such as worldsmall_shipping_problem.json / large_shipping_problem.json are not accepted")
    if obj.get("schema_version") != SCHEMA_VERSION:
        raise ProblemJsonError(f"unsupported schema_version {obj.get('schema_version')!r} (expected {SCHEMA_VERSION})")
    missing = [k for k in _TOP_KEYS if k not in obj]
    if missing:
        raise ProblemJsonError(f"missing top-level key(s) {missing}")
    ident = (obj["dataset"] or {}).get("key")
    if spec is not None and ident != spec.key:
        raise ProblemJsonError(f"dataset identity mismatch: file declares {ident!r}, expected {spec.key!r}")
    for name, fields, rec_type in (("ports", _PORT_FIELDS, Port), ("demands", _DEMAND_FIELDS, Demand)):
        if not isinstance(obj[name], list) or not obj[name]:
            raise ProblemJsonError(f"'{name}' must be a non-empty list")
        bad = next((r for r in obj[name] if not isinstance(r, dict) or set(r) != set(fields)), None)
        if bad is not None:
            raise ProblemJsonError(f"'{name}' record fields {sorted(bad) if isinstance(bad, dict) else bad!r} "
                                   f"!= {sorted(fields)}")
    ids = [p["id"] for p in obj["ports"]]
    if len(set(ids)) != len(ids):
        raise ProblemJsonError("duplicate port ids")
    idset = set(ids)
    stray = sorted({x for d in obj["demands"] for x in (d["origin"], d["destination"]) if x not in idset})
    if stray:
        raise ProblemJsonError(f"demand endpoints not in the port list: {stray[:5]}")
    if set(obj["distance_matrix"]) != idset:
        raise ProblemJsonError("distance_matrix rows are not exactly the port list")
    fl = obj["fleet"]
    if not isinstance(fl, dict) or not fl.get("classes"):
        raise ProblemJsonError("'fleet.classes' must be a non-empty list")
    for c in fl["classes"]:
        if set(c) != set(_CLASS_FIELDS):
            raise ProblemJsonError(f"fleet class fields {sorted(c)} != {sorted(_CLASS_FIELDS)}")
    for key in ("capacity_unit", "capacity_unit_status", "capacity_source_column"):
        if key not in fl:
            raise ProblemJsonError(f"fleet.{key} missing")


def load_problem_json(dataset, path: Optional[Path] = None) -> Tuple[Problem, dict]:
    """The Problem of a dataset's canonical JSON, built in the loader's order, with no conversion applied.

    ``path`` defaults to the dataset's own canonical file; there is no fallback to another file. The fuel
    module's fleet specification is registered from the loaded fleet, exactly as ``NetworkLoader.load_fleet``.
    """
    from src.network.physical_rules import LinerDistanceMatrix
    from src.utils.fuel_cost import register_fleet_specification

    spec = resolve_dataset(dataset)
    path = Path(path) if path is not None else spec.require_json()
    if not path.is_file():
        raise ProblemJsonError(f"{spec.key}: canonical problem file not found: {path}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProblemJsonError(f"{path.name}: invalid JSON: {exc}") from exc
    validate_problem_dict(obj, spec)

    ports = [Port(**p) for p in obj["ports"]]
    demands = [Demand(**d) for d in obj["demands"]]
    matrix = LinerDistanceMatrix()
    for o, row in obj["distance_matrix"].items():
        matrix[o] = dict(row)
    matrix.canal_flags = {(o, d): (int(p), int(s)) for o, d, p, s in obj["canal_flags"]}
    matrix.edge_draft = {(o, d): float(v) for o, d, v in obj["edge_draft"]}
    fl = obj["fleet"]
    fleet = Fleet(classes=[FleetClass(**c) for c in fl["classes"]], capacity_unit=fl["capacity_unit"],
                  capacity_unit_status=fl["capacity_unit_status"], capacity_source_column=fl["capacity_source_column"])
    register_fleet_specification(fleet)
    problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=matrix, fleet=fleet)
    meta = {"dataset": spec.key, "path": str(path), "sha256": sha256_file(path), "schema_version": obj["schema_version"],
            "build_id": obj["provenance"]["build_id"], "converter_version": obj["provenance"]["converter_version"],
            "counts": {"ports": len(ports), "demands": len(demands),
                       "directed_distance_pairs": sum(len(r) for r in matrix.values()),
                       "fleet_classes": len(fleet.classes), "vessels": fleet.total_vessels}}
    return problem, meta


# -- equivalence
def problem_differences(a: Problem, b: Problem, limit: int = 20) -> List[str]:
    """Differences between two Problems in every field the optimizer consumes (empty list = identical)."""
    diffs: List[str] = []

    def add(msg):
        if len(diffs) < limit:
            diffs.append(msg)

    if [asdict(p) for p in a.ports] != [asdict(p) for p in b.ports]:
        add("ports differ (values or order)")
    if [asdict(d) for d in a.demands] != [asdict(d) for d in b.demands]:
        add("demands differ (values or order)")
    ma, mb = a.distance_matrix, b.distance_matrix
    if list(ma) != list(mb):
        add("distance_matrix row order/keys differ")
    else:
        for o in ma:
            if list(ma[o].items()) != list(mb[o].items()):
                add(f"distance_matrix row {o} differs")
                break
    if getattr(ma, "canal_flags", {}) != getattr(mb, "canal_flags", {}):
        add("canal_flags differ")
    if getattr(ma, "edge_draft", {}) != getattr(mb, "edge_draft", {}):
        add("edge_draft differ")
    fa, fb = a.fleet, b.fleet
    if [asdict(c) for c in fa.classes] != [asdict(c) for c in fb.classes] or \
            (fa.capacity_unit, fa.capacity_unit_status, fa.capacity_source_column) != \
            (fb.capacity_unit, fb.capacity_unit_status, fb.capacity_source_column):
        add("fleet differs")
    if a.services or b.services:
        add("services are not empty")
    return diffs
