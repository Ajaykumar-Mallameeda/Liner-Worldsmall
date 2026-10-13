"""Physical feasibility of candidate liner services.

A candidate is a closed rotation: an ordered sequence of distinct ports, sailed with
one vessel class, returning to its first port. This module derives everything that
follows from the route and the vessel class -- and nothing is invented:

    legs            consecutive ports plus the closing leg, each exactly once
    sailing time    distance [nm] / (speed [kn] * 24)  [days], speed = class designSpeed
    port time       calls * port_stay_hours / 24        [days]  (EXPLICIT ASSUMPTION)
    cycle time      sailing + port                      [days]; declared = ceil()
    vessels         ceil(cycle_time_days * weekly_frequency / 7)
    capacity        the selected vessel class capacity (``Capacity FFE``, PROVISIONAL unit)

Route representation. ``Service.ports`` may be an open list ``[a, b, c]`` (closure
implied) or an explicitly closed list ``[a, b, c, a]``; both denote the same
rotation and :func:`rotation_legs` yields the closing leg exactly once.

Rejected candidates are returned with structured reasons; callers must not pass
them to the optimisers. Missing distances, unknown classes or invalid speeds are
rejections -- never replaced by a default.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

HOURS_PER_DAY = 24.0
DAYS_PER_WEEK = 7.0
_EPS = 1e-9

# ---- stable rejection identifiers -------------------------------------------------
R_TOO_FEW_PORTS = "fewer_than_two_distinct_ports"
R_REPEATED_PORT = "repeated_port_in_rotation"
R_UNKNOWN_PORT = "unknown_port"
R_MISSING_DISTANCE = "missing_directed_distance"
R_INVALID_DISTANCE = "invalid_distance"
R_UNKNOWN_CLASS = "unknown_vessel_class"
R_NO_VESSELS = "vessel_class_has_no_vessels"
R_INVALID_SPEED = "invalid_vessel_speed"
R_INVALID_CAPACITY = "invalid_vessel_capacity"
R_IMPOSSIBLE_AT_MAX_SPEED = "declared_cycle_time_impossible_at_max_speed"
R_DECLARED_TOO_SHORT = "declared_cycle_time_shorter_than_required"
R_EXCEEDS_INVENTORY = "required_vessels_exceed_class_inventory"

ALL_REASONS = (
    R_TOO_FEW_PORTS, R_REPEATED_PORT, R_UNKNOWN_PORT, R_MISSING_DISTANCE,
    R_INVALID_DISTANCE, R_UNKNOWN_CLASS, R_NO_VESSELS, R_INVALID_SPEED,
    R_INVALID_CAPACITY, R_IMPOSSIBLE_AT_MAX_SPEED, R_DECLARED_TOO_SHORT,
    R_EXCEEDS_INVENTORY,
)


class ServiceFeasibilityError(ValueError):
    """A required input (fleet, class, frequency, ...) is missing or invalid."""


def _finite(x) -> bool:
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x))


@dataclass(frozen=True)
class PortTimeAssumptions:
    """Time spent in port per call. NOT measured data: the canonical WorldSmall files
    carry no port-time column, so this is an explicit, configurable assumption."""

    port_stay_hours: float = 24.0
    basis: str = (
        "assumed: LINERLIB benchmark documentation states a minimum port stay of "
        "24 hours for all ports; no port-time column exists in the canonical files. "
        "Cargo-handling time is not modelled (no source)."
    )

    def __post_init__(self):
        if not _finite(self.port_stay_hours) or self.port_stay_hours < 0:
            raise ServiceFeasibilityError(
                f"port_stay_hours must be a finite number >= 0, got {self.port_stay_hours!r}"
            )


DEFAULT_PORT_TIME = PortTimeAssumptions()


# =====================================================================================
# Route helpers
# =====================================================================================
def rotation_ports(route: Sequence) -> List:
    """Unique port sequence of a rotation (a trailing return to the first port dropped)."""
    ports = list(route)
    if len(ports) >= 2 and ports[0] == ports[-1]:
        ports = ports[:-1]
    return ports


def rotation_legs(route: Sequence) -> List[Tuple]:
    """Directed legs of the closed rotation, the closing leg included exactly once.

    ``[a, b]`` -> ``[(a, b), (b, a)]``; ``[a, b, c]`` and ``[a, b, c, a]`` ->
    ``[(a, b), (b, c), (c, a)]``. Fewer than two distinct ports have no legs.
    """
    ports = rotation_ports(route)
    n = len(ports)
    if n < 2:
        return []
    return [(ports[i], ports[(i + 1) % n]) for i in range(n)]


def required_vessels(cycle_time_days: float, weekly_frequency: int) -> int:
    """Vessels needed to keep ``weekly_frequency`` departures per week:
    ``ceil(cycle_time_days * weekly_frequency / 7)``. Zero frequency needs zero vessels."""
    if not _finite(cycle_time_days) or cycle_time_days <= 0:
        raise ServiceFeasibilityError(
            f"cycle_time_days must be a finite number > 0, got {cycle_time_days!r}"
        )
    if (not _finite(weekly_frequency) or weekly_frequency < 0
            or weekly_frequency != int(weekly_frequency)):
        raise ServiceFeasibilityError(
            f"weekly_frequency must be a whole number >= 0, got {weekly_frequency!r}"
        )
    if weekly_frequency == 0:
        return 0
    return int(math.ceil(round(cycle_time_days * weekly_frequency / DAYS_PER_WEEK, 9)))


# =====================================================================================
# Evaluation result
# =====================================================================================
@dataclass
class ServiceFeasibility:
    ports: List                       # unique rotation order (closing leg implied)
    vessel_class: str = ""
    legs: List[Tuple] = field(default_factory=list)       # (from, to, nm)
    capacity_teu: Optional[float] = None
    speed_knots: Optional[float] = None
    weekly_vessel_cost: Optional[float] = None            # tc_rate_daily * 7, per vessel
    distance_nm: Optional[float] = None
    sailing_days: Optional[float] = None
    port_days: Optional[float] = None
    cycle_days: Optional[float] = None                    # exact, design speed
    cycle_days_at_max_speed: Optional[float] = None
    cycle_time_days: Optional[int] = None                 # declared = ceil(cycle_days)
    required_vessels_one_departure: Optional[int] = None  # at 1 departure / week
    class_inventory: Optional[int] = None
    declared_cycle_time_days: Optional[float] = None
    capacity_unit_status: str = "provisional"
    port_time_basis: str = ""
    reasons: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return not self.reasons

    def required_vessels(self, weekly_frequency: int) -> int:
        if self.cycle_time_days is None:
            raise ServiceFeasibilityError("cycle time is undefined for an infeasible candidate")
        return required_vessels(self.cycle_time_days, weekly_frequency)

    def to_dict(self) -> Dict:
        d = dict(self.__dict__)
        d["feasible"] = self.feasible
        return d


# =====================================================================================
# Evaluation
# =====================================================================================
def evaluate_rotation(
    route: Sequence,
    vessel,
    distance_matrix: Dict,
    *,
    known_ports: Optional[Iterable] = None,
    port_time: PortTimeAssumptions = DEFAULT_PORT_TIME,
    declared_cycle_time_days: Optional[float] = None,
    capacity_unit_status: str = "provisional",
) -> ServiceFeasibility:
    """Derive and validate the physical properties of one candidate rotation.

    ``vessel`` is a ``FleetClass`` (``None`` -> unknown class). ``distance_matrix`` is
    ``{from: {to: nautical miles}}``. If ``declared_cycle_time_days`` is given it is
    CHECKED against the derived requirement (rejected if too short); callers that
    recalculate simply omit it.
    """
    ports = rotation_ports(route)
    out = ServiceFeasibility(
        ports=list(ports),
        vessel_class=getattr(vessel, "vessel_class", "") or "",
        declared_cycle_time_days=declared_cycle_time_days,
        capacity_unit_status=capacity_unit_status,
        port_time_basis=port_time.basis,
    )
    bad = out.reasons.append
    note = out.details.append

    # ---- route -------------------------------------------------------------------
    if len(ports) < 2:
        bad(R_TOO_FEW_PORTS)
        note(f"route {list(route)!r} has {len(ports)} distinct port(s)")
    if len(set(ports)) != len(ports):
        bad(R_REPEATED_PORT)
        dup = sorted({p for p in ports if ports.count(p) > 1}, key=str)
        note(f"ports visited more than once per rotation: {dup}")
    if known_ports is not None:
        known = set(known_ports)
        unknown = [p for p in ports if p not in known]
        if unknown:
            bad(R_UNKNOWN_PORT)
            note(f"ports not in the network: {unknown}")

    # ---- vessel ------------------------------------------------------------------
    speed = capacity = None
    if vessel is None:
        bad(R_UNKNOWN_CLASS)
        note("vessel class is not in the fleet specification")
    else:
        qty = getattr(vessel, "quantity", 0)
        if not _finite(qty) or qty <= 0:
            bad(R_NO_VESSELS)
            note(f"class {out.vessel_class!r} has no vessels (quantity={qty!r})")
        out.class_inventory = int(qty) if _finite(qty) else None
        speed = getattr(vessel, "design_speed", None)
        lo, hi = getattr(vessel, "min_speed", None), getattr(vessel, "max_speed", None)
        if not (_finite(speed) and speed > 0 and _finite(lo) and _finite(hi)
                and 0 < lo <= speed <= hi):
            bad(R_INVALID_SPEED)
            note(f"speeds must satisfy 0 < min <= design <= max; got "
                 f"min={lo!r} design={speed!r} max={hi!r}")
            speed = None
        capacity = getattr(vessel, "capacity_teu", None)
        if not (_finite(capacity) and capacity > 0):
            bad(R_INVALID_CAPACITY)
            note(f"capacity must be a finite number > 0, got {capacity!r}")
            capacity = None
        rate = getattr(vessel, "tc_rate_daily", None)
        if _finite(rate) and rate >= 0:
            out.weekly_vessel_cost = float(rate) * DAYS_PER_WEEK

    # ---- legs / distances (never a substitute value) ----------------------------
    legs, total_nm, legs_ok = [], 0.0, len(ports) >= 2
    for a, b in rotation_legs(ports):
        row = distance_matrix.get(a) if isinstance(distance_matrix, dict) else None
        d = row.get(b) if isinstance(row, dict) else None
        if d is None:
            bad(R_MISSING_DISTANCE)
            note(f"no directed distance {a} -> {b}")
            legs_ok = False
        elif not (_finite(d) and d > 0):
            bad(R_INVALID_DISTANCE)
            note(f"invalid distance {a} -> {b}: {d!r}")
            legs_ok = False
        else:
            legs.append((a, b, float(d)))
            total_nm += float(d)
    if legs_ok:
        out.legs = legs
        out.distance_nm = total_nm

    # ---- time and vessels ---------------------------------------------------------
    if legs_ok and speed is not None:
        out.speed_knots = float(speed)
        out.capacity_teu = float(capacity) if capacity is not None else None
        out.sailing_days = total_nm / (speed * HOURS_PER_DAY)
        out.port_days = len(ports) * port_time.port_stay_hours / HOURS_PER_DAY
        out.cycle_days = out.sailing_days + out.port_days
        max_speed = float(vessel.max_speed)
        out.cycle_days_at_max_speed = total_nm / (max_speed * HOURS_PER_DAY) + out.port_days
        out.cycle_time_days = int(math.ceil(round(out.cycle_days, 9)))
        out.required_vessels_one_departure = required_vessels(out.cycle_time_days, 1)

        if declared_cycle_time_days is not None:
            dct = declared_cycle_time_days
            if not (_finite(dct) and dct > 0):
                bad(R_DECLARED_TOO_SHORT)
                note(f"declared cycle time must be a finite number > 0, got {dct!r}")
            elif dct + _EPS < out.cycle_days_at_max_speed:
                bad(R_IMPOSSIBLE_AT_MAX_SPEED)
                note(f"declared {dct} d < {out.cycle_days_at_max_speed:.3f} d "
                     f"needed even at max speed")
            elif dct + _EPS < out.cycle_days:
                bad(R_DECLARED_TOO_SHORT)
                note(f"declared {dct} d < {out.cycle_days:.3f} d needed at design speed")

        inv = out.class_inventory
        if inv is not None and inv > 0 and out.required_vessels_one_departure > inv:
            bad(R_EXCEEDS_INVENTORY)
            note(f"needs {out.required_vessels_one_departure} vessels for one weekly "
                 f"departure; class {out.vessel_class!r} has {inv}")
    return out


# =====================================================================================
# Vessel-class choice and re-assignment
# =====================================================================================
def choose_vessel_class(target_capacity_teu: float, fleet):
    """Fleet class whose capacity is nearest to ``target_capacity_teu`` (ties -> the
    smaller vessel). Classes without vessels are not eligible. This is a sizing
    heuristic, not source data; the chosen class's own inputs are then used as-is."""
    return rank_vessel_classes(target_capacity_teu, fleet)[0]


def rank_vessel_classes(target_capacity_teu: float, fleet) -> List:
    """Eligible fleet classes ordered by closeness of capacity to the target
    (ties -> smaller vessel first)."""
    if fleet is None or not getattr(fleet, "classes", None):
        raise ServiceFeasibilityError(
            "no fleet specification: candidate services need the canonical fleet "
            "(problem.fleet); no default vessel class or capacity is assumed"
        )
    if not _finite(target_capacity_teu) or target_capacity_teu <= 0:
        raise ServiceFeasibilityError(
            f"target capacity must be a finite number > 0, got {target_capacity_teu!r}"
        )
    eligible = [c for c in fleet.classes
                if _finite(c.quantity) and c.quantity > 0
                and _finite(c.capacity_teu) and c.capacity_teu > 0]
    if not eligible:
        raise ServiceFeasibilityError("fleet has no vessel class with vessels and capacity")
    return sorted(eligible, key=lambda c: (abs(c.capacity_teu - target_capacity_teu), c.capacity_teu))


def reassign_vessel_class(feasibility: ServiceFeasibility, new_class: str, fleet,
                          distance_matrix: Dict, **kwargs) -> ServiceFeasibility:
    """Change a candidate's vessel class and RECOMPUTE everything that depends on it
    (speed, sailing and cycle time, capacity, vessel cost, inventory check). The old
    derived values are never carried over."""
    vessel = fleet.get_class(new_class) if fleet is not None else None
    return evaluate_rotation(feasibility.ports, vessel, distance_matrix, **kwargs)


# =====================================================================================
# Pool-level report
# =====================================================================================
@dataclass
class CandidateReport:
    """What the generator produced, accepted and rejected -- with reasons."""

    capacity_unit_status: str = "provisional"
    port_time_basis: str = ""
    generated: int = 0
    accepted: int = 0
    rejected: int = 0
    rejections_by_reason: Counter = field(default_factory=Counter)
    generated_by_section: Counter = field(default_factory=Counter)
    accepted_by_section: Counter = field(default_factory=Counter)
    accepted_by_class: Counter = field(default_factory=Counter)
    # candidates whose nearest-capacity class was infeasible but a further class was not
    class_fallbacks: int = 0
    # (rotation, class) pairs offered twice by different sections (class screening only)
    duplicate_rotation_class: int = 0
    # legacy hard-coded cycle times (7/14/21 d) that cannot cover the derived requirement
    legacy_cycle_inconsistent: int = 0
    legacy_cycle_checked: int = 0
    rejected_samples: List[Dict] = field(default_factory=list)
    max_samples: int = 25

    def record(self, section: str, feas: ServiceFeasibility, *, legacy_declared: Optional[float] = None):
        self.generated += 1
        self.generated_by_section[section] += 1
        if legacy_declared is not None and feas.cycle_days is not None:
            self.legacy_cycle_checked += 1
            if legacy_declared + _EPS < feas.cycle_days:
                self.legacy_cycle_inconsistent += 1
        if feas.feasible:
            self.accepted += 1
            self.accepted_by_section[section] += 1
            self.accepted_by_class[feas.vessel_class] += 1
        else:
            self.rejected += 1
            for r in feas.reasons:
                self.rejections_by_reason[r] += 1
            if len(self.rejected_samples) < self.max_samples:
                self.rejected_samples.append({
                    "section": section, "ports": feas.ports,
                    "vessel_class": feas.vessel_class,
                    "reasons": list(feas.reasons), "details": list(feas.details),
                })

    def to_dict(self) -> Dict:
        return {
            "capacity_unit_status": self.capacity_unit_status,
            "capacity_feasibility_is_conditional": self.capacity_unit_status != "verified",
            "port_time_basis": self.port_time_basis,
            "generated": self.generated,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "rejections_by_reason": dict(self.rejections_by_reason),
            "generated_by_section": dict(self.generated_by_section),
            "accepted_by_section": dict(self.accepted_by_section),
            "accepted_by_class": dict(self.accepted_by_class),
            "class_fallbacks": self.class_fallbacks,
            "duplicate_rotation_class": self.duplicate_rotation_class,
            "legacy_cycle_time_checked": self.legacy_cycle_checked,
            "legacy_cycle_time_inconsistent": self.legacy_cycle_inconsistent,
            "rejected_samples": self.rejected_samples,
        }
