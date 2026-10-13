from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Port:
    """A port node. All monetary fields are USD; per-unit fields are per TEU.

    Units (shared contract, see reports/task2_shared_contracts):
        handling_cost            USD per TEU moved (one load OR one discharge)
        port_call_cost           USD per vessel call (fixed)
        transshipment_cost       USD per TEU transshipped
        variable_port_call_cost  USD per TEU handled in a call
        draft                    metres
    """
    id: str  # Changed from int to str to match JSON data
    name: str
    latitude: float
    longitude: float
    handling_cost: float = 0
    draft: float = 0
    port_call_cost: float = 0
    transshipment_cost: float = 0
    variable_port_call_cost: float = 0


@dataclass
class Service:
    """A candidate liner service.

    Units / time basis (shared contract):
        ports       ordered call sequence of Port ids
        capacity    TEU carried by ONE vessel on ONE sailing
        weekly_cost USD per week for ONE vessel deployed on this service
        cycle_time  days for one vessel to complete the rotation
        speed       knots
        fuel_cost   USD per week (informational; optimisers recompute it)

    A service has no frequency / vessel-count field: those are decision
    variables carried in the optimiser chromosome ("frequencies"), expressed
    as sailings per week.
    """
    id: str  # Globally unique service identifier (e.g., "asia_svc_001")
    ports: List[str]  # Changed to str to match Port IDs
    capacity: float
    weekly_cost: float
    cycle_time: int = 7
    speed: float = 18
    fuel_cost: float = 0
    vessel_class: str = ""  # Added for fuel cost calculation
    # Filled by the feasibility-screened generator (None for hand-built services):
    distance_nm: Optional[float] = None       # closed rotation, return leg included once
    required_vessels: Optional[int] = None    # vessels for ONE departure per week
    capacity_unit_status: str = "provisional" # status of the Capacity FFE -> TEU reading

    def __post_init__(self):
        # Backward-compat: accept int IDs by stringifying them.
        if not isinstance(self.id, str):
            self.id = str(self.id)


@dataclass
class Demand:
    """Weekly OD demand in TEU with its revenue rate in USD per TEU.

    The loader guarantees ``weekly_teu * revenue_per_teu`` equals the source
    ``FFEPerWeek * Revenue_1`` (gross USD per week) for every OD pair.
    """
    origin: str  # Changed to str to match Port IDs
    destination: str  # Changed to str
    weekly_teu: float
    revenue_per_teu: float
    # Maximum end-to-end transit time in DAYS (source column ``TransitTime``).
    # ``None`` means the source gave no limit; a limit is never invented.
    max_transit_days: Optional[float] = None


@dataclass
class FleetClass:
    """A single vessel class with quantity and specifications.

    Units: capacity_teu [TEU/vessel], tc_rate_daily [USD/day/vessel],
    draft [m], *_speed [knots], *_consumption_tons_per_day [metric t/day],
    panama_fee / suez_fee [USD per transit].

    ``panama_fee`` / ``suez_fee`` are ``None`` when the source cell is blank:
    "no value given" is NOT the same as a confirmed fee of 0.0, and a blank
    fee must never be read as free or as feasible transit.
    """
    vessel_class: str
    quantity: int
    capacity_teu: float = 0.0
    tc_rate_daily: float = 0.0
    draft: float = 0.0
    min_speed: float = 0.0
    max_speed: float = 0.0
    design_speed: float = 0.0
    bunker_consumption_tons_per_day: float = 0.0
    idle_consumption_tons_per_day: float = 0.0
    panama_fee: Optional[float] = None
    suez_fee: Optional[float] = None

    @property
    def total_vessels(self) -> int:
        return self.quantity


@dataclass
class Fleet:
    """Collection of vessel classes available for deployment.

    ``capacity_unit`` is the unit in which ``FleetClass.capacity_teu`` is used by
    the model; ``capacity_unit_status`` says whether that reading is backed by
    authoritative source documentation (``"verified"``) or is an assumption
    (``"provisional"``, the default). Any capacity feasibility derived from this
    fleet is conditional on that status. ``capacity_source_column`` names the
    source column the value was read from.
    """
    classes: List[FleetClass] = field(default_factory=list)
    capacity_unit: str = "TEU"
    capacity_unit_status: str = "provisional"
    capacity_source_column: str = "Capacity FFE"

    @property
    def total_vessels(self) -> int:
        return sum(c.quantity for c in self.classes)

    def get_class(self, name: str) -> FleetClass | None:
        for c in self.classes:
            if c.vessel_class == name:
                return c
        return None

    def quantity_of(self, vessel_class: str) -> int:
        c = self.get_class(vessel_class)
        return c.quantity if c else 0


class Problem:

    def __init__(
        self,
        ports: List[Port],
        services: List[Service],
        demands: List[Demand],
        distance_matrix: Dict = None,
        fleet: Fleet = None,
    ):
        self.ports = ports
        self.services = services
        self.demands = demands
        self.distance_matrix = distance_matrix
        self.fleet = fleet

        if self.distance_matrix is None:
            raise ValueError("Problem must include distance_matrix")