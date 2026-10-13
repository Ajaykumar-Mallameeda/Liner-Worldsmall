"""LEGACY COPY (verbatim) of the pre-network-model implementation, kept for reference.
Not imported by the pipeline. Superseded by src/network/* (see reports/overnight_tasks_2_to_4).
"""
"""
Fuel Cost Calculation Module for Liner Shipping Optimizer

Implements voyage fuel cost based on:
- Vessel class consumption rates
- Sailing distance
- Bunker fuel prices

Based on industry standard consumption figures.

Unit / time-basis contract
--------------------------
    distance           nautical miles (nm)
    speed              knots (nm per hour)
    consumption        metric tonnes of bunker per sailing day
    price              USD per metric tonne
    voyage cost        USD for sailing the given distance once
    weekly cost        USD per week for ONE vessel sailing the given route as a
                       rotation of ``cycle_time_days`` days

The route is used exactly as given: consecutive ports are legs; the function
does not add a closing leg, so a caller that models a rotation must include the
return leg. A leg between two identical ports is a zero-length leg. A leg
between two distinct ports with no entry in the distance matrix is an error
(``MissingDistanceError``): no synthetic distance is ever substituted. An
unknown vessel class is an error (``UnknownVesselClassError``): no substitute
class is ever priced in its place. Idle (in-port) consumption is not modelled.
"""

import math
import numbers
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class FuelCostError(ValueError):
    """Invalid fuel-cost input. Subclasses ``ValueError`` so existing broad
    handlers still observe it; it is never converted to a zero cost here."""


class MissingDistanceError(FuelCostError):
    """A leg between two distinct ports has no distance in the matrix."""


class UnknownVesselClassError(FuelCostError):
    """The vessel class has no consumption data in ``VESSEL_FUEL_CONSUMPTION``."""

# Industry standard fuel consumption by vessel class
# Based on 2024 maritime industry data
# Consumption in tons per day at service speed
#
# NOTE (documented defect D-FUEL-TABLE): this table is a second source of truth
# that disagrees with data/raw/WorldSmall/fleet_data.csv (capacity for
# Post_panamax/Super_panamax; t/day and speed for every class). The values are
# kept unchanged here; tests/test_shared_contracts.py carries the strict-xfail
# acceptance test for aligning them with the loaded fleet specification.
VESSEL_FUEL_CONSUMPTION = {
    "Feeder_450": {
        "capacity": 450,
        "consumption_tons_per_day": 15,
        "speed_knots": 16,
        "source": "Clarksons Research 2024"
    },
    "Feeder_800": {
        "capacity": 800,
        "consumption_tons_per_day": 25,
        "speed_knots": 17,
        "source": "Clarksons Research 2024"
    },
    "Panamax_1200": {
        "capacity": 1200,
        "consumption_tons_per_day": 35,
        "speed_knots": 18,
        "source": "Clarksons Research 2024"
    },
    "Panamax_2400": {
        "capacity": 2400,
        "consumption_tons_per_day": 55,
        "speed_knots": 19,
        "source": "Clarksons Research 2024"
    },
    "Post_panamax": {
        "capacity": 5000,
        "consumption_tons_per_day": 80,
        "speed_knots": 22,
        "source": "Clarksons Research 2024"
    },
    "Super_panamax": {
        "capacity": 8000,
        "consumption_tons_per_day": 100,
        "speed_knots": 23,
        "source": "Clarksons Research 2024"
    }
}

# Bunker fuel prices as of 2024
# Using IFO 380 (intermediate fuel oil 380 cSt) - most common for container vessels
# Price in USD per metric ton
BUNKER_PRICE_PER_TON = 600.0  # $/ton
BUNKER_PRICE_SOURCE = "Bunker Index 2024 Average"

# IP-2 — weather speed factor bounds. A factor of 1.0 means "no
# adjustment". Values outside [WEATHER_SPEED_FACTOR_MIN,
# WEATHER_SPEED_FACTOR_MAX] are clamped; non-finite input falls
# back to the pre-maritime path (returns ``None``).
WEATHER_SPEED_FACTOR_MIN = 0.5
WEATHER_SPEED_FACTOR_MAX = 1.5


def _normalize_weather_speed_factor(value):
    """Validate and clamp a maritime weather speed factor.

    Returns the clamped value in ``[WEATHER_SPEED_FACTOR_MIN,
    WEATHER_SPEED_FACTOR_MAX]`` when the input is a finite
    number, or ``None`` when the input is ``None`` / non-finite.
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


def _vessel_specs(vessel_class) -> dict:
    """Consumption record for ``vessel_class``; never substitutes another class."""
    try:
        return VESSEL_FUEL_CONSUMPTION[vessel_class]
    except (KeyError, TypeError):
        raise UnknownVesselClassError(
            f"unknown vessel class {vessel_class!r}; known classes: "
            f"{sorted(VESSEL_FUEL_CONSUMPTION)}. No substitute class is assumed."
        ) from None


def map_capacity_to_vessel_class(capacity: float) -> str:
    """Map service capacity to closest vessel class"""

    # Find the vessel class with closest capacity
    best_class = None
    min_diff = float('inf')

    for vessel_class, specs in VESSEL_FUEL_CONSUMPTION.items():
        diff = abs(capacity - specs["capacity"])
        if diff < min_diff:
            min_diff = diff
            best_class = vessel_class

    return best_class or "Post_panamax"  # Default fallback

def calculate_voyage_fuel_cost(
    distance_nm: float,
    vessel_class: str,
    bunker_price_per_ton: float = BUNKER_PRICE_PER_TON,
    *,
    weather_speed_factor: float = None,
) -> float:
    """
    Calculate fuel cost for a single voyage

    Args:
        distance_nm: Distance in nautical miles
        vessel_class: Vessel class from VESSEL_FUEL_CONSUMPTION
        bunker_price_per_ton: Fuel price in $/ton
        weather_speed_factor: Optional bounded speed factor in
            ``[0.5, 1.5]`` derived from maritime weather
            intelligence (IP-2). ``None`` (default) preserves the
            existing pre-maritime byte-equivalent path. When a
            value is supplied, the effective voyage time scales
            by ``1.0 / weather_speed_factor`` (so a value of 0.9
            increases fuel consumption by ~11%). Values outside
            ``[0.5, 1.5]`` are clamped; non-finite values fall
            back to the pre-maritime path (no adjustment).

    Returns:
        Fuel cost in USD for the voyage

    Raises:
        UnknownVesselClassError: ``vessel_class`` is not in the table.
        FuelCostError: ``distance_nm`` or ``bunker_price_per_ton`` is not a
            finite number >= 0.
    """

    _require_non_negative_number(distance_nm, "distance_nm")
    _require_non_negative_number(bunker_price_per_ton, "bunker_price_per_ton")
    specs = _vessel_specs(vessel_class)

    # Calculate sailing days
    # Assuming vessel operates at service speed 90% of time (accounting for port time)
    sailing_days = distance_nm / (specs["speed_knots"] * 24 * 0.9)

    # IP-2: weather speed factor — strictly optional. When
    # ``weather_speed_factor`` is None or invalid, sailing_days is
    # unchanged (byte-equivalent to the pre-maritime path).
    wsf = _normalize_weather_speed_factor(weather_speed_factor)
    if wsf is not None and wsf > 0.0:
        sailing_days = sailing_days / wsf

    # Calculate fuel consumption in tons
    fuel_consumed_tons = sailing_days * specs["consumption_tons_per_day"]

    # Calculate cost
    fuel_cost = fuel_consumed_tons * bunker_price_per_ton

    return fuel_cost

def calculate_weekly_fuel_cost(
    service_route: list,
    distance_matrix: Dict,
    vessel_class: str,
    cycle_time_days: int = 7,
    bunker_price_per_ton: float = BUNKER_PRICE_PER_TON,
    *,
    weather_speed_factor: float = None,
) -> float:
    """
    Calculate weekly fuel cost for a service route

    Args:
        service_route: List of port UNLOCODEs in order
        distance_matrix: Distance matrix between ports
        vessel_class: Vessel class
        cycle_time_days: Days for one complete cycle
        bunker_price_per_ton: Fuel price in $/ton
        weather_speed_factor: Optional bounded speed factor in
            ``[0.5, 1.5]`` derived from maritime weather
            intelligence (IP-2). ``None`` (default) preserves the
            existing pre-maritime byte-equivalent path. See
            :func:`calculate_voyage_fuel_cost` for semantics.

    Returns:
        Weekly fuel cost in USD for ONE vessel sailing ``service_route`` as a
        rotation of ``cycle_time_days`` days. A route with fewer than two ports
        has no legs and costs 0.0. The cost of N vessels / sailings per week is
        the caller's multiplication; this function does not know it.

    Raises:
        MissingDistanceError: a leg between two distinct ports has no distance.
        UnknownVesselClassError: ``vessel_class`` is not in the table.
        FuelCostError: ``cycle_time_days`` is not a finite number > 0, or a
            distance / price is invalid.
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

    if len(service_route) < 2:
        return 0.0

    # Total distance of one rotation as listed (no closing leg is added).
    total_distance = 0.0

    for origin, dest in zip(service_route, service_route[1:]):
        if origin == dest:
            continue                      # same port twice in a row: no sailing
        try:
            total_distance += distance_matrix[origin][dest]
        except (KeyError, TypeError):
            raise MissingDistanceError(
                f"no distance for leg {origin} -> {dest}; no synthetic distance is "
                f"substituted (route {list(service_route)})"
            ) from None

    # Calculate fuel cost for one cycle
    cycle_fuel_cost = calculate_voyage_fuel_cost(
        total_distance, vessel_class, bunker_price_per_ton,
        weather_speed_factor=weather_speed_factor,
    )

    # Convert to weekly cost (cycles per week = 7 / cycle_time_days)
    weekly_fuel_cost = cycle_fuel_cost * (7.0 / cycle_time_days)

    return weekly_fuel_cost

def get_vessel_consumption_rate(vessel_class: str) -> float:
    """Daily fuel consumption in metric tons for a vessel class.

    Raises UnknownVesselClassError for a class that is not in the table.
    """
    return _vessel_specs(vessel_class)["consumption_tons_per_day"]

def get_vessel_speed(vessel_class: str) -> float:
    """Service speed in knots for a vessel class.

    Raises UnknownVesselClassError for a class that is not in the table.
    """
    return _vessel_specs(vessel_class)["speed_knots"]