"""Voyage fuel cost from the canonical fleet specification.

Single source of truth
    ``data/raw/WorldSmall/fleet_data.csv`` is the only source of vessel fuel
    parameters. ``NetworkLoader.load_fleet`` registers what it loads here
    (``register_fleet_specification``); the table below is *derived* from it. The
    former hard-coded "Clarksons Research 2024" table disagreed with the fleet file
    (capacities 5000/8000 vs 4200/7500; speeds above the class maximum) and is
    retired - kept only as a comment further down.

Model (one operating point, as the source supplies)
    sea days   = distance_nm / (designSpeed * 24)          [* 1 / weather factor]
    fuel (t)   = sea days * ``Bunker ton per day at designSpeed``
    fuel (USD) = fuel (t) * bunker price
    in port    = port days * ``Idle Consumption ton/day`` * price   (service model)
    No consumption-vs-speed law is assumed: the source gives consumption at the
    design speed only. The bunker price is not in the fleet file; the documented
    LINERLIB value (600 USD/t) is used as an explicit, overridable assumption.

Unit / time-basis contract
    distance      nautical miles        speed        knots
    consumption   metric tonnes / day   price        USD per metric tonne
    A rotation is CLOSED: the return leg to the first port is costed exactly once
    (``[a, b]`` and ``[a, b, a]`` have the same cost). Missing distance, unknown
    class or an unregistered fleet are errors - no synthetic distance, no
    substitute class, no zero.
"""

import math
import numbers
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FuelCostError(ValueError):
    """Invalid fuel-cost input. Subclasses ``ValueError`` so existing broad
    handlers still observe it; it is never converted to a zero cost here."""


class MissingDistanceError(FuelCostError):
    """A leg between two distinct ports has no distance in the matrix."""


class UnknownVesselClassError(FuelCostError):
    """The vessel class has no fuel data in the registered fleet specification."""


# ----------------------------------------------------------------------------------
# RETIRED hard-coded table (history only - never read):
#
# VESSEL_FUEL_CONSUMPTION = {
#     "Feeder_450":    {"capacity": 450,  "consumption_tons_per_day": 15,  "speed_knots": 16},
#     "Feeder_800":    {"capacity": 800,  "consumption_tons_per_day": 25,  "speed_knots": 17},
#     "Panamax_1200":  {"capacity": 1200, "consumption_tons_per_day": 35,  "speed_knots": 18},
#     "Panamax_2400":  {"capacity": 2400, "consumption_tons_per_day": 55,  "speed_knots": 19},
#     "Post_panamax":  {"capacity": 5000, "consumption_tons_per_day": 80,  "speed_knots": 22},
#     "Super_panamax": {"capacity": 8000, "consumption_tons_per_day": 100, "speed_knots": 23},
# }   # source string was "Clarksons Research 2024"; contradicted fleet_data.csv
# ----------------------------------------------------------------------------------

# Derived from the registered fleet specification (empty until a fleet is loaded).
VESSEL_FUEL_CONSUMPTION: Dict[str, Dict] = {}

# Bunker price: NOT in the canonical files. LINERLIB benchmark documentation states a
# bunker cost of 600 USD per metric ton; it is an explicit assumption, overridable.
BUNKER_PRICE_PER_TON = 600.0  # $/ton
BUNKER_PRICE_SOURCE = "assumed: LINERLIB benchmark documentation (600 USD per metric ton)"

# IP-2 — weather speed factor bounds. A factor of 1.0 means "no adjustment".
WEATHER_SPEED_FACTOR_MIN = 0.5
WEATHER_SPEED_FACTOR_MAX = 1.5


def register_fleet_specification(fleet) -> int:
    """Replace the fuel table with the specification of ``fleet`` (a loaded
    ``Fleet``). Returns the number of classes registered."""
    VESSEL_FUEL_CONSUMPTION.clear()
    for c in getattr(fleet, "classes", []) or []:
        VESSEL_FUEL_CONSUMPTION[c.vessel_class] = {
            "capacity": c.capacity_teu,
            "consumption_tons_per_day": c.bunker_consumption_tons_per_day,
            "idle_tons_per_day": c.idle_consumption_tons_per_day,
            "speed_knots": c.design_speed,
            "min_speed_knots": c.min_speed,
            "max_speed_knots": c.max_speed,
            "source": "data/raw/WorldSmall/fleet_data.csv (canonical fleet specification)",
        }
    return len(VESSEL_FUEL_CONSUMPTION)


def _bootstrap_from_canonical_fleet() -> None:
    """Populate the table from the canonical WorldSmall fleet files when nothing was
    registered yet (so a standalone call uses the same single source, never a copy).
    A load failure leaves the table empty and the caller raises explicitly."""
    try:
        from src.data.network_loader import NetworkLoader
        NetworkLoader().load_fleet()          # registers on success
    except Exception as exc:                  # noqa: BLE001
        logger.warning("fuel_cost_fleet_bootstrap_failed | %s: %s", type(exc).__name__, exc)


def _normalize_weather_speed_factor(value):
    """Validate and clamp a maritime weather speed factor.

    Returns the clamped value in ``[WEATHER_SPEED_FACTOR_MIN,
    WEATHER_SPEED_FACTOR_MAX]`` when the input is a finite number, or ``None`` when
    the input is ``None`` / non-finite.
    """
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    fv = float(value)
    if fv < WEATHER_SPEED_FACTOR_MIN:
        return WEATHER_SPEED_FACTOR_MIN
    if fv > WEATHER_SPEED_FACTOR_MAX:
        return WEATHER_SPEED_FACTOR_MAX
    return fv


def _require_non_negative_number(value, name: str) -> None:
    ok = (
        isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )
    if not ok:
        raise FuelCostError(f"{name} must be a finite number >= 0, got {value!r}")


def _vessel_specs(vessel_class, fleet=None) -> dict:
    """Fuel record of ``vessel_class`` from ``fleet`` or the registered specification;
    never substitutes another class."""
    if fleet is not None:
        c = fleet.get_class(vessel_class)
        if c is None:
            raise UnknownVesselClassError(
                f"unknown vessel class {vessel_class!r}; fleet classes: "
                f"{sorted(x.vessel_class for x in fleet.classes)}. No substitute class is assumed.")
        return {"capacity": c.capacity_teu, "consumption_tons_per_day": c.bunker_consumption_tons_per_day,
                "idle_tons_per_day": c.idle_consumption_tons_per_day, "speed_knots": c.design_speed}
    if not VESSEL_FUEL_CONSUMPTION:
        _bootstrap_from_canonical_fleet()
    if not VESSEL_FUEL_CONSUMPTION:
        raise UnknownVesselClassError(
            f"no fleet specification is registered (vessel class {vessel_class!r}); load the "
            f"canonical fleet with NetworkLoader.load_fleet or pass fleet=")
    try:
        return VESSEL_FUEL_CONSUMPTION[vessel_class]
    except (KeyError, TypeError):
        raise UnknownVesselClassError(
            f"unknown vessel class {vessel_class!r}; known classes: "
            f"{sorted(VESSEL_FUEL_CONSUMPTION)}. No substitute class is assumed."
        ) from None


def map_capacity_to_vessel_class(capacity: float, fleet=None) -> str:
    """The class of the registered specification (or ``fleet``) whose capacity is
    nearest to ``capacity``. Raises when no specification is available - there is no
    default class."""
    if fleet is None and not VESSEL_FUEL_CONSUMPTION:
        _bootstrap_from_canonical_fleet()
    table = (
        {c.vessel_class: {"capacity": c.capacity_teu} for c in fleet.classes}
        if fleet is not None else VESSEL_FUEL_CONSUMPTION
    )
    if not table:
        raise UnknownVesselClassError(
            "no fleet specification is registered; cannot map a capacity to a class")
    return min(table, key=lambda k: (abs(capacity - table[k]["capacity"]), table[k]["capacity"]))


def calculate_voyage_fuel_cost(
    distance_nm: float,
    vessel_class: str,
    bunker_price_per_ton: float = BUNKER_PRICE_PER_TON,
    *,
    weather_speed_factor: float = None,
    fleet=None,
) -> float:
    """Fuel cost in USD of sailing ``distance_nm`` at the class design speed.

    ``weather_speed_factor`` (IP-2, clamped to [0.5, 1.5]) scales the sailing time by
    ``1 / factor``; ``None`` leaves it unchanged.

    Raises UnknownVesselClassError / FuelCostError for an unknown class, an
    unregistered fleet, or a non-finite / negative distance or price.
    """
    _require_non_negative_number(distance_nm, "distance_nm")
    _require_non_negative_number(bunker_price_per_ton, "bunker_price_per_ton")
    specs = _vessel_specs(vessel_class, fleet)
    speed = specs["speed_knots"]
    if not (isinstance(speed, numbers.Real) and math.isfinite(speed) and speed > 0):
        raise FuelCostError(f"vessel class {vessel_class!r} has no valid design speed ({speed!r})")

    sailing_days = distance_nm / (speed * 24.0)
    wsf = _normalize_weather_speed_factor(weather_speed_factor)
    if wsf is not None and wsf > 0.0:
        sailing_days = sailing_days / wsf
    return sailing_days * specs["consumption_tons_per_day"] * bunker_price_per_ton


def rotation_distance_nm(service_route, distance_matrix: Dict) -> float:
    """Length of the CLOSED rotation: the listed legs plus the return leg to the first
    port, each counted once (``[a, b]`` and ``[a, b, a]`` are the same rotation)."""
    ports = list(service_route)
    if len(ports) >= 2 and ports[0] == ports[-1]:
        ports = ports[:-1]
    if len(ports) < 2:
        return 0.0
    total = 0.0
    for i, origin in enumerate(ports):
        dest = ports[(i + 1) % len(ports)]
        if origin == dest:
            continue
        try:
            d = distance_matrix[origin][dest]
        except (KeyError, TypeError):
            raise MissingDistanceError(
                f"no distance for leg {origin} -> {dest}; no synthetic distance is "
                f"substituted (route {list(service_route)})"
            ) from None
        _require_non_negative_number(d, f"distance {origin}->{dest}")
        total += d
    return total


def calculate_weekly_fuel_cost(
    service_route: list,
    distance_matrix: Dict,
    vessel_class: str,
    cycle_time_days: int = 7,
    bunker_price_per_ton: float = BUNKER_PRICE_PER_TON,
    *,
    weather_speed_factor: float = None,
    fleet=None,
) -> float:
    """Weekly SEA-fuel cost of ONE vessel sailing the closed rotation continuously:
    ``rotation fuel * 7 / cycle_time_days``.

    The pipeline prices services with ``src.network.economics.ServiceModel`` (which
    also includes port-idle fuel and the weekly departures); this helper remains for
    callers that need a per-vessel figure.

    Raises MissingDistanceError, UnknownVesselClassError or FuelCostError; a route
    with fewer than two distinct ports has no legs and costs 0.0.
    """
    if (
        not isinstance(cycle_time_days, numbers.Real)
        or isinstance(cycle_time_days, bool)
        or not math.isfinite(cycle_time_days)
        or cycle_time_days <= 0
    ):
        raise FuelCostError(
            f"cycle_time_days must be a finite number > 0, got {cycle_time_days!r}"
        )
    total_distance = rotation_distance_nm(service_route, distance_matrix)
    if total_distance == 0.0:
        return 0.0
    cycle_fuel_cost = calculate_voyage_fuel_cost(
        total_distance, vessel_class, bunker_price_per_ton,
        weather_speed_factor=weather_speed_factor, fleet=fleet,
    )
    return cycle_fuel_cost * (7.0 / cycle_time_days)


def get_vessel_consumption_rate(vessel_class: str, fleet=None) -> float:
    """Daily sea consumption (t/day at design speed) of a class."""
    return _vessel_specs(vessel_class, fleet)["consumption_tons_per_day"]


def get_vessel_speed(vessel_class: str, fleet=None) -> float:
    """Design speed in knots of a class."""
    return _vessel_specs(vessel_class, fleet)["speed_knots"]
