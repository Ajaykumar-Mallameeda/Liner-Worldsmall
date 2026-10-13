"""Canonical service model: real rotation time, vessels, capacity and weekly cost.

One definition, used by the GA surrogates, the network MILP and (re-derived
independently) by the ledger.

Frequency
    ``f`` is the number of departures per week (integer >= 0). A rotation takes a
    real time ``T`` (days) = sailing at the class design speed + port stays, so

        vessels      N(f) = ceil(T * f / 7)          (T = declared whole days)
        capacity     cap * f  TEU per week on EVERY leg of the rotation
        per week     N * TC_daily * 7                vessel hire
                   + f * rotation_fuel               fuel (sea + port idle)
                   + f * sum(fixed port-call cost)   port calls

    There is no hard-coded frequency or cycle time: the largest sensible ``f`` is
    derived from T and from the class inventory (``max_departures``).

Fuel (source-backed, one operating point)
    sea days  * ``Bunker ton per day at designSpeed`` * price
  + port days * ``Idle Consumption ton/day``          * price
    The sailing speed is the class ``designSpeed`` - the only speed for which the
    source gives a consumption. No consumption-vs-speed law is assumed. The bunker
    price is NOT in the canonical files: it comes from ``fuel_pricing`` (a pinned
    snapshot, see ``src/network/bunker_prices.py``) or, when none is configured, from
    the labelled legacy assumption ``bunker_price_usd_per_t`` (600 USD/t, uniform).
    Fuel TONNES and the price are kept separate (``fuel_tonnes_per_rotation`` x
    ``fuel_price_usd_per_t``) so the ledger can verify cost independently.

Not modelled (no source): cargo-handling time, slack time of vessels in a weekly
schedule, weather, canal fees/draft limits (blank fees are unknown, not zero).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from src.network.physical_rules import check_rotation
from src.network.bunker_prices import (
    BunkerPriceError, FuelPriceResolution, FuelPricing, LEGACY_UNIFORM_USD_PER_T, active_pricing,
)
from src.services.service_feasibility import (
    PortTimeAssumptions,
    ServiceFeasibility,
    evaluate_rotation,
    required_vessels,
)

DAYS_PER_WEEK = 7.0
HOURS_PER_DAY = 24.0


@dataclass(frozen=True)
class EconomicsAssumptions:
    """Explicit modelling assumptions that the canonical files do not supply."""

    port_stay_hours: float = 24.0
    transshipment_min_hours: float = 48.0
    transfer_wait_days: float = 3.5
    bunker_price_usd_per_t: float = LEGACY_UNIFORM_USD_PER_T
    # Region-aware pricing (None = the uniform legacy price above, bit-for-bit as
    # before). See src/network/bunker_prices.py.
    fuel_pricing: Optional[FuelPricing] = None
    # IP-2 weather adjustment of the sailing speed (1.0 = none); clamped by callers.
    speed_factor: float = 1.0
    basis: str = (
        "assumed (not in the canonical WorldSmall files): LINERLIB benchmark "
        "documentation gives a minimum port stay of 24 h, a minimum transshipment "
        "time of 48 h and a bunker cost of 600 USD/t. transfer_wait_days is the "
        "expected wait for a connecting weekly departure (half a week)."
    )

    def __post_init__(self):
        for name in ("port_stay_hours", "transshipment_min_hours", "transfer_wait_days",
                     "bunker_price_usd_per_t"):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
                raise ValueError(f"{name} must be a finite number >= 0, got {v!r}")
        sf = self.speed_factor
        if not (isinstance(sf, (int, float)) and math.isfinite(sf) and sf > 0):
            raise ValueError(f"speed_factor must be a finite number > 0, got {sf!r}")

    @property
    def effective_fuel_pricing(self) -> FuelPricing:
        """The pricing in force: the configured one, else the uniform legacy price."""
        if self.fuel_pricing is not None:
            return self.fuel_pricing
        return FuelPricing.legacy_uniform(self.bunker_price_usd_per_t)

    def resolve_fuel_price(self, rotation_ports: Sequence[str]) -> FuelPriceResolution:
        """Price that applies to a rotation (raises ``BunkerPriceError``; never 0)."""
        return self.effective_fuel_pricing.resolve(rotation_ports)

    @property
    def port_time(self) -> PortTimeAssumptions:
        return PortTimeAssumptions(self.port_stay_hours)

    @property
    def port_stay_days(self) -> float:
        return self.port_stay_hours / HOURS_PER_DAY

    @property
    def transfer_dwell_days(self) -> float:
        """Time a container spends at a transshipment hub (minimum handling + wait)."""
        return self.transshipment_min_hours / HOURS_PER_DAY + self.transfer_wait_days


DEFAULT_ASSUMPTIONS = EconomicsAssumptions()


class ServiceModelError(ValueError):
    """The service cannot be modelled (missing class, distance, spec ...)."""

    def __init__(self, message: str, reasons: Sequence[str] = ()):
        super().__init__(message)
        self.reasons = list(reasons)


@dataclass(frozen=True)
class ServiceModel:
    """Everything about one candidate service that does not depend on cargo."""

    service_id: str
    vessel_class: str
    ports: Tuple[str, ...]                      # unique rotation order
    legs: Tuple[Tuple[str, str, float], ...]    # (from, to, nm); closing leg last
    leg_sail_days: Tuple[float, ...]
    capacity_teu: float
    speed_knots: float
    sea_days: float
    port_days: float
    cycle_days: float                           # exact
    cycle_time_days: int                        # declared = ceil(cycle_days)
    class_inventory: int
    vessel_week_cost: float                     # TC_daily * 7, per vessel
    fuel_cost_per_rotation: float               # USD, sea + port idle
    fuel_tonnes_per_rotation: float
    port_fixed_per_rotation: float              # sum of fixed port-call costs + canal fees of the rotation
    canal_fee_per_rotation: float = 0.0         # memo: the canal-fee part of ``port_fixed_per_rotation``
    port_capacity_charge_per_rotation: float = 0.0   # memo: sum(callCostPerFFE x capacity) part of it
    canal_traversals: Tuple[int, int] = (0, 0)  # (Panama, Suez) traversals of the closed rotation
    capacity_unit_status: str = "provisional"
    # applicable bunker price and where it came from (fuel cost = tonnes x this price)
    fuel_price_usd_per_t: float = float("nan")
    fuel_price_basis: str = ""
    bunkering_port: Optional[str] = None

    # ---- time/vessel relations -------------------------------------------------
    def vessels(self, departures_per_week: int) -> int:
        """Vessels needed for ``departures_per_week`` (0 departures -> 0 vessels)."""
        return required_vessels(self.cycle_time_days, departures_per_week)

    def max_departures(self, vessel_budget: Optional[int] = None) -> int:
        """Largest weekly frequency the class inventory can sustain for this rotation
        (``floor(7 * N / T)``); ``vessel_budget`` caps N below the class inventory."""
        n = self.class_inventory if vessel_budget is None else min(vessel_budget, self.class_inventory)
        return int(math.floor(round(DAYS_PER_WEEK * n / self.cycle_time_days, 9)))

    def departure_interval_days(self, departures_per_week: int) -> float:
        if departures_per_week <= 0:
            raise ValueError("no departures")
        return DAYS_PER_WEEK / departures_per_week

    # ---- weekly economics --------------------------------------------------------
    def weekly_vessel_cost(self, f: int) -> float:
        return self.vessels(f) * self.vessel_week_cost

    def weekly_fuel_cost(self, f: int) -> float:
        return f * self.fuel_cost_per_rotation

    def weekly_port_fixed_cost(self, f: int) -> float:
        return f * self.port_fixed_per_rotation

    def weekly_fixed_cost(self, f: int) -> float:
        return self.weekly_vessel_cost(f) + self.weekly_fuel_cost(f) + self.weekly_port_fixed_cost(f)

    def weekly_leg_capacity(self, f: int) -> float:
        return self.capacity_teu * f

    # ---- geometry -------------------------------------------------------------------
    def position(self, port: str) -> Optional[int]:
        try:
            return self.ports.index(port)
        except ValueError:
            return None

    def ride(self, a: str, b: str) -> Optional[Tuple[Tuple[int, ...], float]]:
        """Leg indices and transit days when riding the closed rotation from ``a`` to
        ``b`` (forward, wrapping around). Transit = sailing + one port stay at each
        INTERMEDIATE port; time at the origin and at the destination is not counted."""
        ia, ib = self.position(a), self.position(b)
        if ia is None or ib is None or ia == ib:
            return None
        n = len(self.ports)
        legs, days, i = [], 0.0, ia
        while i != ib:
            legs.append(i)
            days += self.leg_sail_days[i]
            i = (i + 1) % n
            if i != ib:
                days += self._port_stay_days
        return tuple(legs), days

    # filled by build_service_model (frozen dataclass -> set through object.__setattr__)
    _port_stay_days: float = 1.0


def _port_attr(port, name: str) -> float:
    v = getattr(port, name, 0.0) if port is not None else 0.0
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else 0.0


def build_service_model(
    service_id: str,
    route: Sequence[str],
    vessel,
    distance_matrix: Dict,
    port_lookup: Dict,
    assumptions: EconomicsAssumptions = DEFAULT_ASSUMPTIONS,
    *,
    known_ports=None,
    capacity_unit_status: str = "provisional",
) -> ServiceModel:
    """Build the model of one candidate; raise ``ServiceModelError`` if it cannot be
    evaluated (never substituting a value)."""
    feas: ServiceFeasibility = evaluate_rotation(
        route, vessel, distance_matrix,
        known_ports=known_ports, port_time=assumptions.port_time,
        capacity_unit_status=capacity_unit_status,
    )
    if not feas.feasible:
        raise ServiceModelError(
            f"service {service_id}: {', '.join(feas.reasons)}: {'; '.join(feas.details)}",
            feas.reasons,
        )
    for fld in ("bunker_consumption_tons_per_day", "idle_consumption_tons_per_day", "tc_rate_daily"):
        val = getattr(vessel, fld, None)
        if not (isinstance(val, (int, float)) and math.isfinite(val) and val >= 0):
            raise ServiceModelError(
                f"service {service_id}: vessel class {vessel.vessel_class!r} has no valid {fld} ({val!r})",
                ["missing_fleet_parameter"],
            )

    missing_ports = [p for p in feas.ports if p not in port_lookup]
    if missing_ports:
        raise ServiceModelError(
            f"service {service_id}: no port record for {missing_ports}; port costs are "
            f"never assumed to be zero", ["missing_port_record"])
    # physical rules of the benchmark: draft feasibility (hard) and canal fees (charged per round trip);
    # see src/network/physical_rules.py for the evidence
    rules = check_rotation(feas.ports, vessel, distance_matrix, port_lookup)
    if rules.reasons:
        raise ServiceModelError(
            f"service {service_id}: {', '.join(sorted(set(rules.reasons)))}: {'; '.join(rules.details)}",
            sorted(set(rules.reasons)))

    try:
        price = assumptions.resolve_fuel_price(feas.ports)
    except BunkerPriceError as exc:
        raise ServiceModelError(
            f"service {service_id}: no applicable bunker price: {exc}",
            ["bunker_price_unavailable", *exc.reasons]) from None

    speed = feas.speed_knots * assumptions.speed_factor
    leg_days = tuple(nm / (speed * HOURS_PER_DAY) for _, _, nm in feas.legs)
    sea_days = sum(leg_days)
    port_days = len(feas.ports) * assumptions.port_stay_days
    fuel_t = sea_days * vessel.bunker_consumption_tons_per_day \
        + port_days * vessel.idle_consumption_tons_per_day
    # LINERLIB port-call cost (reference code ``bm_reader.cpp`` and the authors' solution log, 34/34 services):
    # per call  callCostFixed + callCostPerFFE x vessel capacity, once per weekly rotation, independent of the
    # cargo carried.  ``variable_port_call_cost`` is USD per TEU (= per FFE / 2), so per call it is
    # variable_port_call_cost x capacity_teu.
    port_cap_charge = sum(_port_attr(port_lookup.get(p), "variable_port_call_cost") for p in feas.ports) \
        * float(vessel.capacity_teu)
    port_fixed = sum(_port_attr(port_lookup.get(p), "port_call_cost") for p in feas.ports) \
        + port_cap_charge + rules.canal_fee_per_rotation

    m = ServiceModel(
        service_id=str(service_id),
        vessel_class=vessel.vessel_class,
        ports=tuple(feas.ports),
        legs=tuple(feas.legs),
        leg_sail_days=leg_days,
        capacity_teu=float(vessel.capacity_teu),
        speed_knots=float(speed),
        sea_days=sea_days,
        port_days=port_days,
        cycle_days=sea_days + port_days,
        cycle_time_days=int(math.ceil(round(sea_days + port_days, 9))),
        class_inventory=int(vessel.quantity),
        vessel_week_cost=float(vessel.tc_rate_daily) * DAYS_PER_WEEK,
        fuel_cost_per_rotation=fuel_t * price.price_usd_per_t,
        fuel_tonnes_per_rotation=fuel_t,
        port_fixed_per_rotation=port_fixed,
        canal_fee_per_rotation=rules.canal_fee_per_rotation,
        port_capacity_charge_per_rotation=port_cap_charge,
        canal_traversals=(rules.panama_traversals, rules.suez_traversals),
        capacity_unit_status=capacity_unit_status,
        fuel_price_usd_per_t=price.price_usd_per_t,
        fuel_price_basis=price.basis,
        bunkering_port=price.bunkering_port,
        _port_stay_days=assumptions.port_stay_days,
    )
    return m


def estimate_best_frequency(model: ServiceModel, demand_teu: float,
                            avg_revenue_per_teu: float, vessel_budget: Optional[int] = None) -> Tuple[int, float]:
    """Surrogate used by the GAs: the weekly frequency maximising
    ``min(cap*f, demand) * revenue - weekly_fixed_cost(f)`` (0 if unprofitable).
    Returns ``(f, margin)``. Not verified profit - the network MILP/ledger decide."""
    fmax = model.max_departures(vessel_budget)
    if fmax <= 0 or demand_teu <= 0:
        return 0, 0.0
    f_demand = max(1, int(math.ceil(demand_teu / model.capacity_teu)))
    best_f, best_m = 0, 0.0
    for f in range(1, min(fmax, f_demand) + 1):
        margin = min(model.capacity_teu * f, demand_teu) * avg_revenue_per_teu - model.weekly_fixed_cost(f)
        if margin > best_m:
            best_f, best_m = f, margin
    return best_f, best_m


# =====================================================================================
# Per-problem helpers shared by the GA stages, the regional MILP and the global stage
# =====================================================================================
def assumptions_for_problem(problem, base: EconomicsAssumptions = DEFAULT_ASSUMPTIONS) -> EconomicsAssumptions:
    """``base`` with (a) the configured fuel pricing (``active_pricing()``; the
    uniform legacy price when none is configured) and (b) the IP-2 weather speed
    factor from attached maritime features (clamped to [0.5, 1.5]); unchanged when
    neither applies.

    A mis-configured regional pricing request raises ``BunkerPriceError`` here; it
    is never replaced by the legacy price."""
    cur = base
    if cur.fuel_pricing is None:
        pricing = active_pricing()
        if pricing is not None:
            cur = EconomicsAssumptions(**{**cur.__dict__, "fuel_pricing": pricing})
    mf = getattr(problem, "maritime_features", None)
    wsf = getattr(mf, "weather_speed_factor", None) if mf is not None else None
    if not isinstance(wsf, (int, float)) or isinstance(wsf, bool) \
            or not math.isfinite(wsf):
        return cur
    wsf = min(1.5, max(0.5, float(wsf)))
    if wsf == cur.speed_factor:
        return cur
    return EconomicsAssumptions(**{**cur.__dict__, "speed_factor": wsf})


def service_models_for(problem, assumptions: Optional[EconomicsAssumptions] = None) -> List[Optional[ServiceModel]]:
    """One ``ServiceModel`` per entry of ``problem.services`` (``None`` where the
    service cannot be modelled: no fleet, unknown class, missing distance or port
    record). Cached on the problem object and rebuilt when the service list, fleet
    or assumptions change."""
    assumptions = assumptions or assumptions_for_problem(problem)
    fleet = getattr(problem, "fleet", None)
    services = problem.services
    key = (id(services), len(services), id(fleet), assumptions)
    cache = getattr(problem, "_service_models_cache", None)
    if cache is not None and cache[0] == key:
        return cache[1]
    if fleet is None or not getattr(fleet, "classes", None):
        models: List[Optional[ServiceModel]] = [None] * len(services)
    else:
        catalog = getattr(problem, "port_catalog", None)
        port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
        known = set(problem.distance_matrix)
        status = getattr(fleet, "capacity_unit_status", "provisional")
        models = []
        for svc in services:
            vessel = fleet.get_class(svc.vessel_class) if getattr(svc, "vessel_class", "") else None
            try:
                models.append(build_service_model(
                    str(svc.id), svc.ports, vessel, problem.distance_matrix, port_lookup,
                    assumptions, known_ports=known, capacity_unit_status=status))
            except ServiceModelError:
                models.append(None)
    try:
        problem._service_models_cache = (key, models)
    except Exception:                                              # noqa: BLE001
        pass
    return models
