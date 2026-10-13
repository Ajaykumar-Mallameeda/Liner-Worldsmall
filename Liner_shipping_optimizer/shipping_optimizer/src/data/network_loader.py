"""WorldSmall network loader.

Data contract (all sources live in ``data/raw/WorldSmall`` and are tab-separated
despite the ``.csv`` extension):

    ports.csv                       47 ports   (coordinates in decimal degrees)
    Demand_WorldSmall_Fixed_Sep.csv 1764 OD rows
                                    FFEPerWeek [FFE/week], Revenue_1 [USD/FFE]
    dist_dense.csv                  2162 directed OD pairs, Distance [nautical miles]
    fleet_WorldSmall.csv            vessel-class quantities (263 vessels)
    fleet_data.csv                  per-vessel specifications
                                    ``Capacity FFE`` is an FFE count and is
                                    converted once, here, to TEU:
                                    ``capacity_teu = 2 * Capacity FFE``.
                                    Status ``reference_code``: confirmed by the benchmark authors' reference code (FFE type);
                                    also
                                    defined by the RL paper (arXiv:2411.09068,
                                    App. A.1); the primary LINERLIB report was
                                    not available (``CAPACITY_UNIT_PROVENANCE``).

Unit contract (FFE -> TEU; 1 FFE = 2 TEU):

    quantities     FFEPerWeek [FFE/wk]  * 2.0  -> weekly_teu [TEU/wk]
    revenue rates  Revenue_1  [USD/FFE] / 2.0  -> revenue_per_teu [USD/TEU]
    capacity       Capacity FFE [FFE/vessel] * 2.0 -> capacity_teu [TEU/vessel]
    port costs     CostPerFULL, CostPerFULLTrnsf, PortCallCostPerFFE [USD/FFE]
                   / 2.0                        -> USD/TEU
    fixed cost     PortCallCostFixed [USD per call] -> unchanged

1 FFE = 2 TEU exactly; there are no lane-specific factors (the six factors that
earlier versions applied to WorldSmall lanes had no source and were removed).

The same invariant holds for all per-FFE rates: ``converted TEU flow *
converted USD/TEU == raw FFE flow * raw USD/FFE``. Per-FFE rates are always
DIVIDED when converted to per-TEU rates, never multiplied.

Canal fees: ``panamaFee`` / ``suezFee`` blank in the source means "no value
given", loaded as ``None`` (not 0.0). A blank fee is neither a confirmed zero
fee nor evidence about transit feasibility.

Default paths are explicit and never fall back to another dataset or to a
similarly named file: a missing required file raises ``FileNotFoundError``.

Explicit paths are validated, not trusted: a path inside the managed raw-data
tree but outside ``data/raw/WorldSmall`` is rejected, and a file whose
identifiers mix WorldSmall ports with foreign ports is rejected. Dataset
identity is decided from location and content, never from a file name.
Files outside the raw-data tree (e.g. isolated test fixtures) are accepted
when they are self-consistent.
"""

import csv
import json
import logging
import math
from pathlib import Path

import pandas as pd

from src.optimization.data import Port, Demand, Fleet, FleetClass
from src.utils.fuel_cost import register_fleet_specification

logger = logging.getLogger(__name__)

# --------------------------------
# Canonical WorldSmall sources
# --------------------------------
RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
WORLDSMALL_DIR = RAW_DATA_DIR / "WorldSmall"

WORLDSMALL_FILES = {
    "ports": WORLDSMALL_DIR / "ports.csv",
    "demand": WORLDSMALL_DIR / "Demand_WorldSmall_Fixed_Sep.csv",
    "distance": WORLDSMALL_DIR / "dist_dense.csv",
    "fleet": WORLDSMALL_DIR / "fleet_WorldSmall.csv",
    "fleet_data": WORLDSMALL_DIR / "fleet_data.csv",
}

# --------------------------------
# Unit conversions and scaling
# --------------------------------
# FFE -> TEU: 1 FFE = 2 TEU exactly. Quantities (demand, vessel capacity) are
# multiplied by it and per-FFE rates (revenue, port costs) are divided by it, so that
# weekly_teu * revenue_per_teu == FFEPerWeek * Revenue_1.
DEFAULT_FFE_TO_TEU = 2.0

# Lane-specific FFE -> TEU factors (1.75 - 2.1 "based on typical cargo mix") were applied
# to six WorldSmall lanes in earlier versions. No authoritative source defines them, they
# contradict 1 FFE = 2 TEU and the lane-independent cost conversion, so they are removed.
# The mapping is kept (empty) so that an exception can only be added together with a source.
FFE_TO_TEU_LANE_FACTORS = {}

# Demand scaling is dataset specific. WorldSmall is never scaled beyond the
# FFE -> TEU conversion; the legacy multiplier below belongs to WorldLarge.
WORLDSMALL_DEMAND_SCALE = 1
LEGACY_WORLDLARGE_DEMAND_SCALE = 6

# 1 FFE = 2 TEU. The port cost columns are priced per FFE ("per FULL" container,
# USD/FFE; see DATA_DICTIONARY: model fields are USD/TEU), so a per-FFE rate is
# DIVIDED by this factor to obtain the per-TEU rate -- the same direction as
# Revenue_1. It is a property of the unit, not of the lane, so the lane-specific
# revenue factors do not apply to port costs.
TEU_PER_FFE = 2.0

# --------------------------------
# Vessel capacity unit: provenance and status
# --------------------------------
# The fleet specification column is named "Capacity FFE". The LINERLIB files and README
# state no unit; the RL paper that uses the benchmark (Dutta, Lin, Jin, arXiv:2411.09068,
# App. A.1 "vcap: the maximum number of FFEs the vessel can carry at once"; section 6.1
# "capacity of 800 FFEs") defines the capacity in FFE and never uses TEU. Decision of
# 2026-10-13: the column is an FFE count and is converted ONCE, at this boundary, to the
# model's internal TEU. The evidence is a secondary source: the status is therefore
# "reference_code" since the decision phase (the authors' reference implementation types the capacity as FFE),
# never "verified" (that requires the technical report text).
CAPACITY_SOURCE_COLUMN = "Capacity FFE"
CAPACITY_INTERNAL_UNIT = "TEU"
CAPACITY_UNIT_STATUS = "reference_code"     # "verified" requires the technical report (authoritative_source)
CAPACITY_UNIT_PROVENANCE = {
    "source_file": "data/raw/WorldSmall/fleet_data.csv",
    "source_column": CAPACITY_SOURCE_COLUMN,
    "raw_unit": "FFE",
    "internal_unit": CAPACITY_INTERNAL_UNIT,
    "conversion_applied": "x2 once at the loader boundary (capacity_teu = 2 * Capacity FFE)",
    "status": CAPACITY_UNIT_STATUS,
    "authoritative_source": None,
    "reference_code": (
        "LINERLIB reference implementation (benchmark authors): BM_Graph.hpp 'typedef unsigned long long FFE; "
        "//Number of Forty Foot Equivalent containers', bm_data.hpp 'vesselclass(..., FFE capacity, ...)' and "
        "'FFE m_capacity; // The maximal load for the vesseltype'; verified in reports/decision_phase/primary_source_units.md"
    ),
    "secondary_source": (
        "Dutta, Lin, Jin, 'Liner Shipping Network Design with Reinforcement Learning', "
        "arXiv:2411.09068v1, App. A.1 (vcap = maximum number of FFEs) and section 6.1 "
        "(Feeder 800 'with a capacity of 800 FFEs')"
    ),
    "reason": (
        "the dataset documents give the column only by name; the secondary source defines "
        "the capacity of the same vessel classes in FFE; the primary LINERLIB technical "
        "report (Brouer, Pisinger, Sigurd) was not available to confirm it"
    ),
    "capacity_feasibility_is_conditional": True,
    "unapplied_alternative": (
        "if the column were TEU, capacity_teu would equal the loaded value (the earlier "
        "provisional reading, which understated capacity by a factor "
        f"{TEU_PER_FFE} relative to the converted demand)"
    ),
    "evidence_checked": [
        "fleet_data.csv header 'Capacity FFE': column name only, no unit definition",
        "LINERLIB README (github.com/blof/LINERLIB): describes fleet_data.csv as 'all "
        "data on the 6 vessel types'; states no capacity unit (it calls demand 'FFe')",
        "Google OR-tools LINERLIB benchmark page: states no vessel capacity unit",
        "RL paper arXiv:2411.09068 (secondary source): capacity in FFE, p.15 and p.9; the "
        "string 'TEU' does not occur; used as the decision basis",
        "Brouer et al., Transportation Science 48(2) 281-312 (2014), "
        "doi:10.1287/trsc.2013.0471: full text not retrievable in this environment; "
        "not checked (primary source unavailable)",
        "repository documents (MA_02, MA_05, reports/audit_20261013_phaseADB) restate "
        "the column name and the open question; derived, not authoritative",
    ],
}

_PORT_REQUIRED = [
    "unlocode", "name", "latitude", "longitude", "draft",
    "costperfull", "costperfulltrnsf", "portcallcostfixed", "portcallcostperffe",
]
_DEMAND_REQUIRED = ["Origin", "Destination", "FFEPerWeek", "Revenue_1"]
_DISTANCE_REQUIRED = ["fromunlocode", "tounlocode", "distance"]
_FLEET_QTY_REQUIRED = ["Vessel class", "Quantity"]
_FLEET_SPEC_REQUIRED = [
    "Vessel class", "Capacity FFE", "TC rate daily (fixed Cost)", "draft",
    "minSpeed", "maxSpeed", "designSpeed",
    "Bunker ton per day at designSpeed", "Idle Consumption ton/day",
]


class DataValidationError(ValueError):
    """A WorldSmall input file violates its schema or data contract."""


# --------------------------------
# Public helpers
# --------------------------------
def ffe_to_teu_factor(origin, destination):
    """FFE -> TEU factor for an OD lane: 2.0 unless a sourced exception is registered in
    ``FFE_TO_TEU_LANE_FACTORS`` (none is)."""
    return FFE_TO_TEU_LANE_FACTORS.get(f"{origin}-{destination}", DEFAULT_FFE_TO_TEU)


def ffe_to_teu(ffe):
    """Quantity in FFE -> TEU (1 FFE = 2 TEU)."""
    return ffe * TEU_PER_FFE


def teu_to_ffe(teu):
    """Quantity in TEU -> FFE (1 FFE = 2 TEU)."""
    return teu / TEU_PER_FFE


def demand_scale_for_dataset(dataset_name):
    """Explicit, dataset-specific demand scale.

    WorldSmall is never scaled (1). Anything else keeps the legacy WorldLarge
    multiplier of 6, which is applied by the WorldLarge benchmark only.
    """
    if "worldsmall" in str(dataset_name).lower():
        return WORLDSMALL_DEMAND_SCALE
    return LEGACY_WORLDLARGE_DEMAND_SCALE


# --------------------------------
# Parsing / validation helpers
# --------------------------------
def _clean_name(name):
    """Strip whitespace, BOM and surrounding quote characters from a header."""
    s = str(name).replace("﻿", "")
    while True:
        t = s.strip().strip("\"'").strip()
        if t == s:
            return t
        s = t


def _strip_columns(columns, source, lower=False):
    """Normalize column names; refuse to let normalization merge two columns."""
    cleaned = [_clean_name(c) for c in columns]
    if lower:
        cleaned = [c.lower() for c in cleaned]

    if any(c == "" for c in cleaned):
        raise DataValidationError(f"{source}: empty column name in header {list(columns)}")

    seen, dupes = set(), []
    for c in cleaned:
        if c in seen and c not in dupes:
            dupes.append(c)
        seen.add(c)
    if dupes:
        raise DataValidationError(
            f"{source}: duplicate column names after normalization: {dupes} "
            f"(raw header: {list(columns)})"
        )
    return cleaned


def _read_table(path, required, lower_columns=False):
    """Read a tab-separated WorldSmall table as strings, validating its header."""
    path = Path(path)
    name = path.name

    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            header = next(csv.reader(fh, delimiter="\t"), None)
    except UnicodeDecodeError as exc:
        raise DataValidationError(f"{name}: not valid UTF-8 text: {exc}") from exc
    if not header:
        raise DataValidationError(f"{name}: file is empty (no header row)")

    columns = _strip_columns(header, name, lower=lower_columns)
    missing = [c for c in required if c not in columns]
    if missing:
        hint = ""
        if len(columns) == 1:
            hint = " (only one column found - the file must be tab-separated)"
        raise DataValidationError(
            f"{name}: missing required column(s) {missing}; found {columns}{hint}"
        )

    try:
        df = pd.read_csv(
            path, sep="\t", dtype=str, na_filter=False, encoding="utf-8-sig",
            header=0, names=columns, index_col=False,
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise DataValidationError(f"{name}: malformed tab-separated data: {exc}") from exc

    df = df.fillna("")
    for c in df.columns:
        df[c] = df[c].str.strip()
    if df.empty:
        raise DataValidationError(f"{name}: no data rows")
    return df


def _number(value, source, column, label):
    """Parse a finite float, naming file / column / record on failure."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise DataValidationError(
            f"{source}: column '{column}' at {label}: non-numeric value {value!r}"
        ) from None
    if not math.isfinite(v):
        raise DataValidationError(
            f"{source}: column '{column}' at {label}: non-finite value {value!r}"
        )
    return v


def _non_negative(value, source, column, label):
    v = _number(value, source, column, label)
    if v < 0:
        raise DataValidationError(
            f"{source}: column '{column}' at {label}: negative value {value!r}"
        )
    return v


def _positive(value, source, column, label):
    v = _non_negative(value, source, column, label)
    if v <= 0:
        raise DataValidationError(
            f"{source}: column '{column}' at {label}: value must be > 0, got {value!r}"
        )
    return v


def _identifier(value, source, column, label):
    if not value:
        raise DataValidationError(f"{source}: column '{column}' at {label}: blank identifier")
    return value


class NetworkLoader:

    def __init__(self, data_dir="data"):

        # ``data_dir`` is accepted for backward compatibility; paths are fixed.
        self.data_dir = RAW_DATA_DIR
        self.worldsmall_dir = WORLDSMALL_DIR

        # Populated by every load_* call: counts, totals and exclusions.
        self.validation_report = {}

        # Canonical WorldSmall port identifiers (lazy; see _worldsmall_port_ids).
        self._ws_port_ids = None

    # --------------------------------
    # Path resolution (explicit, no fallback)
    # --------------------------------
    def _resolve(self, key, explicit, description):
        path = WORLDSMALL_FILES[key] if explicit is None else Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(
                f"Required WorldSmall {description} file not found: {path}. "
                f"No fallback to another dataset or file is attempted; restore the file "
                f"or pass an explicit path."
            )
        if explicit is not None:
            self._reject_foreign_location(path, description)
        return path

    # --------------------------------
    # Dataset boundary for explicit paths
    # --------------------------------
    @staticmethod
    def _reject_foreign_location(path, description):
        """Reject a file that lives in the managed raw-data tree but not in WorldSmall.

        Decided from the resolved location only, so a WorldLarge file cannot be
        passed off as WorldSmall by its name. Locations outside the raw-data tree
        (isolated fixtures) are not judged here; see ``_check_dataset_identity``.
        """
        resolved = Path(path).resolve()
        raw_root = RAW_DATA_DIR.resolve()
        ws_root = WORLDSMALL_DIR.resolve()
        if resolved.is_relative_to(raw_root) and not resolved.is_relative_to(ws_root):
            raise DataValidationError(
                f"{Path(path).name}: {description} file {resolved} is inside the raw-data "
                f"tree but not inside {ws_root}; this loader reads only WorldSmall and will "
                f"not load or combine another dataset (e.g. WorldLarge)."
            )

    def _worldsmall_port_ids(self):
        """Port identifiers of the canonical WorldSmall ports file (read once)."""
        if self._ws_port_ids is None:
            ref = Path(WORLDSMALL_FILES["ports"])
            if not ref.is_file():
                raise FileNotFoundError(
                    f"Canonical WorldSmall ports file not found: {ref}; it is required "
                    f"to establish dataset identity for explicit paths."
                )
            df = _read_table(ref, _PORT_REQUIRED, lower_columns=True)
            self._ws_port_ids = frozenset(df["unlocode"])
        return self._ws_port_ids

    def _check_dataset_identity(self, path, kind, ids, source):
        """Reject an explicit file whose identifiers mix WorldSmall and foreign ports.

        * every identifier is a WorldSmall port  -> WorldSmall (or a subset)
        * no identifier is a WorldSmall port     -> isolated fixture, accepted
        * some are and some are not              -> a different dataset presented
                                                    as WorldSmall (or a corrupted
                                                    one); rejected.

        Canonical files are exempt (they define the reference).
        """
        if Path(path).resolve() == Path(WORLDSMALL_FILES[kind]).resolve():
            return
        ws = self._worldsmall_port_ids()
        ids = set(ids)
        known, foreign = ids & ws, ids - ws
        if known and foreign:
            raise DataValidationError(
                f"{source}: {kind} file mixes {len(known)} WorldSmall port ids with "
                f"{len(foreign)} ids outside the WorldSmall port set "
                f"(e.g. {sorted(foreign)[:5]}); a non-WorldSmall dataset cannot be "
                f"loaded as WorldSmall."
            )

    # --------------------------------
    # Load ports
    # --------------------------------
    def load_ports(self, ports_file=None):

        path = self._resolve("ports", ports_file, "ports")
        src = path.name
        df = _read_table(path, _PORT_REQUIRED, lower_columns=True)

        ports = []
        excluded = []
        first_seen = {}

        for n, row in enumerate(df.to_dict("records"), start=1):

            pid = _identifier(row["unlocode"], src, "UNLocode", f"row {n}")
            label = f"row {n} ({pid})"

            if pid in first_seen:
                raise DataValidationError(
                    f"{src}: duplicate port identifier {pid!r} at row {n} "
                    f"(first seen at row {first_seen[pid]})"
                )
            first_seen[pid] = n

            # Ports with unusable coordinates are excluded from the network,
            # visibly: logged and listed in the validation report.
            reason = None
            lat = lon = None
            try:
                lat = _number(row["latitude"], src, "Latitude", label)
                lon = _number(row["longitude"], src, "Longitude", label)
                if not -90.0 <= lat <= 90.0:
                    reason = f"latitude {lat} outside [-90, 90]"
                elif not -180.0 <= lon <= 180.0:
                    reason = f"longitude {lon} outside [-180, 180]"
            except DataValidationError as exc:
                reason = str(exc).split(": ", 1)[-1]
            if reason is not None:
                logger.warning("%s: port %s excluded - %s", src, pid, reason)
                excluded.append({"id": pid, "row": n, "reason": reason})
                continue

            name = row["name"]
            if not name:
                raise DataValidationError(f"{src}: column 'name' at {label}: blank port name")

            ports.append(
                Port(
                    id=pid,
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    handling_cost=_non_negative(row["costperfull"], src, "CostPerFULL", label)
                    / TEU_PER_FFE,
                    draft=_non_negative(row["draft"], src, "Draft", label),
                    port_call_cost=_non_negative(
                        row["portcallcostfixed"], src, "PortCallCostFixed", label
                    ),
                    transshipment_cost=_non_negative(
                        row["costperfulltrnsf"], src, "CostPerFULLTrnsf", label
                    ) / TEU_PER_FFE,
                    variable_port_call_cost=_non_negative(
                        row["portcallcostperffe"], src, "PortCallCostPerFFE", label
                    ) / TEU_PER_FFE,
                )
            )

        self._check_dataset_identity(
            path, "ports", {pid for pid in df["unlocode"]}, src
        )

        self.validation_report["ports"] = {
            "source": str(path),
            "rows": len(df),
            "loaded": len(ports),
            "excluded": excluded,
            "cost_basis": f"per-FFE columns divided by {TEU_PER_FFE} (USD/FFE -> USD/TEU)",
        }
        return ports

    # --------------------------------
    # Load demand
    # --------------------------------
    def load_demands(self, demand_file=None):
        """Load OD demand, converting FFE to TEU without changing gross revenue.

        weekly_teu      = FFEPerWeek * k
        revenue_per_teu = Revenue_1 / k      (Revenue_1 is USD per FFE)

        so weekly_teu * revenue_per_teu == FFEPerWeek * Revenue_1 per lane.
        No dataset-level demand scaling is applied.
        """
        path = self._resolve("demand", demand_file, "demand")
        src = path.name
        df = _read_table(path, _DEMAND_REQUIRED)

        demands = []
        seen = {}
        self_loops = 0
        raw_ffe = raw_gross = 0.0
        transit_values = []

        for n, row in enumerate(df.to_dict("records"), start=1):

            origin = _identifier(row["Origin"], src, "Origin", f"row {n}")
            dest = _identifier(row["Destination"], src, "Destination", f"row {n}")
            label = f"row {n} ({origin}->{dest})"

            ffe = _non_negative(row["FFEPerWeek"], src, "FFEPerWeek", label)
            revenue_per_ffe = _non_negative(row["Revenue_1"], src, "Revenue_1", label)

            if origin == dest:
                self_loops += 1
                logger.warning("%s: %s skipped - origin equals destination", src, label)
                continue

            if (origin, dest) in seen:
                raise DataValidationError(
                    f"{src}: duplicate OD pair {origin}->{dest} at row {n} "
                    f"(first seen at row {seen[(origin, dest)]})"
                )
            seen[(origin, dest)] = n

            k = ffe_to_teu_factor(origin, dest)

            # Optional maximum transit time (days). When the column exists every row
            # must carry a positive finite value: a blank is not "unlimited".
            max_transit = None
            if "TransitTime" in df.columns:
                max_transit = _positive(row["TransitTime"], src, "TransitTime", label)
                transit_values.append(max_transit)

            demands.append(
                Demand(
                    origin=origin,
                    destination=dest,
                    weekly_teu=ffe * k,
                    revenue_per_teu=revenue_per_ffe / k,
                    max_transit_days=max_transit,
                )
            )
            raw_ffe += ffe
            raw_gross += ffe * revenue_per_ffe

        self._check_dataset_identity(
            path, "demand", {i for o, d in seen for i in (o, d)}, src
        )

        self.validation_report["demands"] = {
            "source": str(path),
            "rows": len(df),
            "loaded": len(demands),
            "self_loops_skipped": self_loops,
            "demand_scale": WORLDSMALL_DEMAND_SCALE,
            "raw_weekly_ffe": raw_ffe,
            "converted_weekly_teu": sum(d.weekly_teu for d in demands),
            "raw_gross_revenue_usd_per_week": raw_gross,
            "converted_gross_revenue_usd_per_week": sum(
                d.weekly_teu * d.revenue_per_teu for d in demands
            ),
            # TransitTime is read as the maximum end-to-end transit time in DAYS.
            # The unit is an interpretation (values 3-70 are consistent with days
            # against the directed distances) and is not defined by a document here.
            "max_transit_days": (
                {"min": min(transit_values), "max": max(transit_values),
                 "rows": len(transit_values),
                 "basis": "source column TransitTime, interpreted as days (unverified unit)"}
                if transit_values else None
            ),
        }
        return demands

    # --------------------------------
    # Load distance matrix
    # --------------------------------
    def load_distance_matrix(self, dist_file=None):
        """Load directed distances in nautical miles as ``matrix[origin][dest]``.

        Directions are kept separate; d(A,B) is never assumed to equal d(B,A).
        """
        path = self._resolve("distance", dist_file, "distance")
        src = path.name
        df = _read_table(path, _DISTANCE_REQUIRED, lower_columns=True)

        from src.network.physical_rules import LinerDistanceMatrix
        matrix = LinerDistanceMatrix()
        seen = {}
        has_flags = {"ispanama", "issuez"} <= set(df.columns)

        for n, row in enumerate(df.to_dict("records"), start=1):

            o = _identifier(row["fromunlocode"], src, "fromUNLOCODe", f"row {n}")
            d = _identifier(row["tounlocode"], src, "ToUNLOCODE", f"row {n}")
            label = f"row {n} ({o}->{d})"

            dist = _non_negative(row["distance"], src, "Distance", label)
            if o != d and dist == 0:
                raise DataValidationError(
                    f"{src}: column 'Distance' at {label}: zero distance between distinct ports"
                )

            if (o, d) in seen:
                first_row, first_val = seen[(o, d)]
                kind = "conflicting" if first_val != dist else "repeated"
                raise DataValidationError(
                    f"{src}: duplicate directed pair {o}->{d} at row {n} "
                    f"({kind} distance {first_val} vs {dist}; first seen at row {first_row})"
                )
            seen[(o, d)] = (n, dist)

            matrix.setdefault(o, {})
            matrix[o][d] = dist
            if has_flags:
                # canal traversal flags and the draft limit of the leg (listed on the Panama edges only)
                pan = int(float(row["ispanama"] or 0))
                sue = int(float(row["issuez"] or 0))
                if pan or sue:
                    matrix.canal_flags[(o, d)] = (pan, sue)
                dv = row.get("draft")
                if dv not in (None, "") and not (isinstance(dv, float) and math.isnan(dv)):
                    matrix.edge_draft[(o, d)] = float(dv)

        self._check_dataset_identity(
            path, "distance", {i for o, d in seen for i in (o, d)}, src
        )

        self.validation_report["distances"] = {
            "source": str(path),
            "unit": "nautical miles",
            "directed_pairs": len(seen),
            "canal_flagged_pairs": len(matrix.canal_flags),
            "pairs_with_draft_limit": len(matrix.edge_draft),
        }
        return matrix

    # --------------------------------
    # Load fleet
    # --------------------------------
    def load_fleet(self, fleet_file=None, fleet_data_file=None):
        """Load fleet from CSV files into Fleet dataclass.

        Args:
            fleet_file: Path to vessel class quantities CSV (default fleet_WorldSmall.csv)
                       Expected columns: Vessel class, Quantity
            fleet_data_file: Path to vessel specifications CSV (default fleet_data.csv)
                            Expected columns: Vessel class, Capacity FFE, TC rate daily (fixed Cost),
                                             draft, minSpeed, maxSpeed, designSpeed,
                                             Bunker ton per day at designSpeed, Idle Consumption ton/day,
                                             panamaFee, suezFee

        ``Capacity FFE`` is an FFE count: ``capacity_teu = 2 * Capacity FFE`` (converted
        here, once; nothing downstream converts again). The reading rests on a secondary
        source (see ``CAPACITY_UNIT_PROVENANCE``): the returned ``Fleet`` carries
        ``capacity_unit_status == "reference_code"`` (never "verified"). Quantities and
        specifications must describe exactly the same set of vessel classes.

        Returns:
            Fleet instance with classes populated from both files.
        """
        qty_path = self._resolve("fleet", fleet_file, "fleet quantity")
        spec_path = self._resolve("fleet_data", fleet_data_file, "fleet specification")

        # Load quantities
        qty_src = qty_path.name
        qty_df = _read_table(qty_path, _FLEET_QTY_REQUIRED)
        qty_map = {}
        for n, row in enumerate(qty_df.to_dict("records"), start=1):
            cls_name = _identifier(row["Vessel class"], qty_src, "Vessel class", f"row {n}")
            label = f"row {n} ({cls_name})"
            if cls_name in qty_map:
                raise DataValidationError(
                    f"{qty_src}: duplicate vessel class {cls_name!r} at row {n}"
                )
            q = _non_negative(row["Quantity"], qty_src, "Quantity", label)
            if q != int(q):
                raise DataValidationError(
                    f"{qty_src}: column 'Quantity' at {label}: not an integer: {row['Quantity']!r}"
                )
            qty_map[cls_name] = int(q)

        # Load specifications
        spec_src = spec_path.name
        spec_df = _read_table(spec_path, _FLEET_SPEC_REQUIRED)
        spec_map = {}
        fee_blank = {}   # class -> canal fee columns left blank in the source
        for n, row in enumerate(spec_df.to_dict("records"), start=1):
            cls_name = _identifier(row["Vessel class"], spec_src, "Vessel class", f"row {n}")
            label = f"row {n} ({cls_name})"
            if cls_name in spec_map:
                raise DataValidationError(
                    f"{spec_src}: duplicate vessel class {cls_name!r} at row {n} "
                    f"(conflicting specifications)"
                )

            spec = {
                # "Capacity FFE" is an FFE count: converted to TEU here, once (1 FFE = 2 TEU).
                "capacity_teu": ffe_to_teu(_positive(row["Capacity FFE"], spec_src, "Capacity FFE", label)),
                "tc_rate_daily": _non_negative(
                    row["TC rate daily (fixed Cost)"], spec_src, "TC rate daily (fixed Cost)", label
                ),
                "draft": _positive(row["draft"], spec_src, "draft", label),
                "min_speed": _positive(row["minSpeed"], spec_src, "minSpeed", label),
                "max_speed": _positive(row["maxSpeed"], spec_src, "maxSpeed", label),
                "design_speed": _positive(row["designSpeed"], spec_src, "designSpeed", label),
                "bunker_consumption_tons_per_day": _non_negative(
                    row["Bunker ton per day at designSpeed"], spec_src,
                    "Bunker ton per day at designSpeed", label,
                ),
                "idle_consumption_tons_per_day": _non_negative(
                    row["Idle Consumption ton/day"], spec_src, "Idle Consumption ton/day", label
                ),
            }
            if not spec["min_speed"] <= spec["design_speed"] <= spec["max_speed"]:
                raise DataValidationError(
                    f"{spec_src}: {label}: speeds must satisfy minSpeed <= designSpeed <= maxSpeed "
                    f"(got {spec['min_speed']}, {spec['design_speed']}, {spec['max_speed']})"
                )
            # Optional fee columns. A blank cell is "no value given" (None): it is
            # not a confirmed 0.0 fee and says nothing about transit feasibility.
            for col, key in (("panamaFee", "panama_fee"), ("suezFee", "suez_fee")):
                raw = row.get(col, "")
                if raw == "":
                    spec[key] = None
                    fee_blank.setdefault(cls_name, []).append(col)
                else:
                    spec[key] = _non_negative(raw, spec_src, col, label)
            spec_map[cls_name] = spec

        # Class identifiers must agree across both files.
        no_spec = [c for c in qty_map if c not in spec_map]
        no_qty = [c for c in spec_map if c not in qty_map]
        if no_spec or no_qty:
            raise DataValidationError(
                f"{qty_src} / {spec_src}: vessel classes do not match; "
                f"classes without specifications: {no_spec}; "
                f"classes without quantities: {no_qty}"
            )

        # Combine into Fleet
        classes = []
        for cls_name, qty in qty_map.items():
            specs = spec_map[cls_name]
            fc = FleetClass(
                vessel_class=cls_name,
                quantity=qty,
                capacity_teu=specs["capacity_teu"],
                tc_rate_daily=specs["tc_rate_daily"],
                draft=specs["draft"],
                min_speed=specs["min_speed"],
                max_speed=specs["max_speed"],
                design_speed=specs["design_speed"],
                bunker_consumption_tons_per_day=specs["bunker_consumption_tons_per_day"],
                idle_consumption_tons_per_day=specs["idle_consumption_tons_per_day"],
                panama_fee=specs["panama_fee"],
                suez_fee=specs["suez_fee"],
            )
            classes.append(fc)

        self.validation_report["fleet"] = {
            "quantity_source": str(qty_path),
            "specification_source": str(spec_path),
            "classes": len(classes),
            "total_vessels": sum(c.quantity for c in classes),
            # Blank canal fees are unknown (None), never an implied 0.0 or a
            # statement about whether the class may transit the canal.
            "canal_fee_blank": fee_blank,
            # Capacity unit is an assumption, not a verified fact (see the
            # constants above); consumers must not present capacity feasibility
            # as source-verified while this says "provisional", "secondary_source" or "reference_code".
            "capacity_unit": dict(CAPACITY_UNIT_PROVENANCE),
        }
        logger.info(
            "fleet capacity unit status %s: '%s' (FFE) converted to %s once (x2)",
            CAPACITY_UNIT_STATUS, CAPACITY_SOURCE_COLUMN, CAPACITY_INTERNAL_UNIT,
        )
        fleet = Fleet(
            classes=classes,
            capacity_unit=CAPACITY_INTERNAL_UNIT,
            capacity_unit_status=CAPACITY_UNIT_STATUS,
            capacity_source_column=CAPACITY_SOURCE_COLUMN,
        )
        # One source of truth for vessel fuel parameters: the fuel module's table is
        # derived from this loaded specification (there is no second, hard-coded table).
        register_fleet_specification(fleet)
        return fleet

    # --------------------------------
    # Cross-file validation
    # --------------------------------
    def validate_network(self, ports, demands, distance_matrix):
        """Check demand and distance records against the loaded WorldSmall port set.

        Raises DataValidationError if a demand or distance record references an
        unknown port, or if any directed pair of distinct ports has no distance.
        """
        port_ids = {p.id for p in ports}

        bad_demand = sorted(
            {i for d in demands for i in (d.origin, d.destination) if i not in port_ids}
        )
        if bad_demand:
            raise DataValidationError(
                f"demand references ports not in the WorldSmall port set: {bad_demand[:10]}"
            )

        bad_dist = sorted(
            {i for o, row in distance_matrix.items() for i in (o, *row) if i not in port_ids}
        )
        if bad_dist:
            raise DataValidationError(
                f"distance matrix references ports not in the WorldSmall port set: {bad_dist[:10]}"
            )

        missing = [
            (o, d) for o in sorted(port_ids) for d in sorted(port_ids)
            if o != d and d not in distance_matrix.get(o, {})
        ]
        if missing:
            raise DataValidationError(
                f"{len(missing)} directed port pair(s) have no distance, e.g. {missing[:5]}; "
                f"no synthetic distance is substituted"
            )

        return {"ports": len(port_ids), "demands": len(demands),
                "directed_pairs": sum(len(r) for r in distance_matrix.values())}

    # --------------------------------
    # MAIN LOADER
    # --------------------------------
    def load_network(self, ports_file=None, demand_file=None, dist_file=None):

        ports = self.load_ports(ports_file)
        demands = self.load_demands(demand_file)
        distance_matrix = self.load_distance_matrix(dist_file)

        self.validate_network(ports, demands, distance_matrix)

        port_ids = {p.id for p in ports}

        # ensure every port exists in matrix
        for pid in port_ids:
            distance_matrix.setdefault(pid, {})

        return {
            "ports": ports,
            "demands": demands,
            "distance_matrix": distance_matrix
        }

    # --------------------------------
    # Load full problem (with fleet)
    # --------------------------------
    def load_problem(self, dataset_path=None):
        """Load a Problem.

        With no argument the Problem is built from the canonical WorldSmall CSV
        sources (demand scale 1, fleet from fleet_WorldSmall.csv / fleet_data.csv).

        An explicit JSON dataset path is still accepted for WorldSmall datasets
        only; the demand scale is chosen per dataset (see demand_scale_for_dataset)
        and never inherited from WorldLarge. Distances always come from the
        WorldSmall distance file, so a non-WorldSmall dataset is rejected
        instead of being mixed with WorldSmall distances.
        """
        from src.optimization.data import Problem

        if dataset_path is None:
            network = self.load_network()
            return Problem(
                ports=network["ports"],
                services=[],  # Services are generated at runtime
                demands=network["demands"],
                distance_matrix=network["distance_matrix"],
                fleet=self.load_fleet(),
            )

        dataset_path = Path(dataset_path)
        # The file name is only a first, cheap gate. Dataset identity is
        # established from content below: a WorldLarge dataset that is merely
        # named like a WorldSmall one is rejected there.
        demand_scale = demand_scale_for_dataset(dataset_path.name)
        if demand_scale != WORLDSMALL_DEMAND_SCALE:
            raise DataValidationError(
                f"{dataset_path.name}: not a WorldSmall dataset. This loader reads only "
                f"data/raw/WorldSmall and will not combine other datasets with WorldSmall distances."
            )
        self._reject_foreign_location(dataset_path, "dataset")

        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)

        ports = [Port(**dict(p)) for p in data["ports"]]
        services = []  # Services are generated at runtime
        demands = [Demand(**dict(d)) for d in data["demands"]]

        for d in demands:
            d.weekly_teu *= demand_scale

        name = dataset_path.name
        if not ports or not demands:
            raise DataValidationError(f"{name}: dataset has no ports or no demands")
        foreign = sorted({p.id for p in ports} - self._worldsmall_port_ids())
        if foreign:
            raise DataValidationError(
                f"{name}: {len(foreign)} port(s) are outside the WorldSmall port set "
                f"(e.g. {foreign[:5]}); a non-WorldSmall dataset cannot be loaded as "
                f"WorldSmall and is never combined with WorldSmall distances."
            )

        distance_matrix = self.load_distance_matrix()
        self.validate_network(ports, demands, distance_matrix)
        self._require_canonical_equivalence(name, ports, demands)

        return Problem(
            ports=ports,
            services=services,
            demands=demands,
            distance_matrix=distance_matrix,
            fleet=self.load_fleet(),  # WorldSmall fleet; never the legacy fleet_size=300
        )

    def _require_canonical_equivalence(self, source, ports, demands):
        """An explicit dataset must reproduce the canonical WorldSmall numbers.

        Port cost rates and per-OD quantities / gross revenue are compared with
        the canonical CSV load. A dataset with a different unit basis (e.g. a
        legacy x2 port cost, or revenue multiplied by the FFE->TEU factor) is
        rejected instead of silently changing the economics.
        """
        canon_ports = {p.id: p for p in self.load_ports()}
        canon_dem = {(d.origin, d.destination): d for d in self.load_demands()}
        issues = []

        for p in ports:
            c = canon_ports[p.id]
            for f in ("handling_cost", "port_call_cost", "transshipment_cost",
                      "variable_port_call_cost"):
                a, b = getattr(p, f), getattr(c, f)
                if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
                    issues.append(f"port {p.id} {f}: dataset {a} vs canonical {b}")

        for d in demands:
            c = canon_dem.get((d.origin, d.destination))
            if c is None:
                issues.append(f"demand {d.origin}->{d.destination} not in canonical source")
                continue
            if not math.isclose(d.weekly_teu, c.weekly_teu, rel_tol=1e-9, abs_tol=1e-9):
                issues.append(
                    f"demand {d.origin}->{d.destination} weekly_teu: "
                    f"dataset {d.weekly_teu} vs canonical {c.weekly_teu}"
                )
            g, cg = d.weekly_teu * d.revenue_per_teu, c.weekly_teu * c.revenue_per_teu
            if not math.isclose(g, cg, rel_tol=1e-9, abs_tol=1e-6):
                issues.append(
                    f"demand {d.origin}->{d.destination} gross revenue: "
                    f"dataset {g} vs canonical {cg}"
                )

        if issues:
            raise DataValidationError(
                f"{source}: dataset disagrees with the canonical WorldSmall sources on "
                f"{len(issues)} value(s); e.g. {issues[:3]}. Regenerate it from "
                f"data/raw/WorldSmall or load the CSV sources directly."
            )
