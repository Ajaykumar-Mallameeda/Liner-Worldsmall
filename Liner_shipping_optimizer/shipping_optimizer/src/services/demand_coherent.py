"""Demand-coherent multi-port closed-rotation generation (Task 9).

Problem this addresses
    The candidate pool was dominated by two-port rotations and by random "heuristic"
    routes; only 12 of ~1,080 candidates were profitable stand-alone and the pool had
    few consolidation services. Enlarging the pool with *more of the same* made the
    production selection worse (solver_findings.md section 1).

What this generator does
    It grows closed rotations of 3..``max_ports`` ports from the strongest OD
    opportunities, one port at a time, and keeps a port only if it adds
    ride-feasible cargo value (transit-time limit respected) that outweighs the
    extra vessel time. Nothing is drawn at random: for fixed inputs the output is
    identical (reproducible by construction).

For every rotation
    * every leg and the return leg use canonical directed distances (a missing
      distance rejects the insertion; none is invented);
    * a vessel class of the canonical fleet supplies speed, capacity, hire, fuel
      and inventory (the class is chosen exactly as the existing sections choose it:
      nearest capacity to a demand-derived target, next-nearest if the rotation
      needs more vessels than the class owns - per-rotation class screening is Task 10);
    * cycle = ceil(sailing + port stays); vessels = ceil(cycle * f / 7);
    * only OD pairs whose ride along the rotation meets ``TransitTime`` count as
      served (ride = sailing + one port stay per intermediate port);
    * leg loads are scaled to the vessel capacity (``cap * f`` on every leg), so a
      rotation cannot "serve" more than it can carry;
    * full weekly cost uses the same service model and the pinned fuel pricing as
      the optimiser and the ledger.

Selection under a budget
    Candidates are ranked by a complementarity-aware score (value of ODs not yet
    directly servable by the existing pool counts fully, already-served ODs are
    discounted) per vessel. A rotation with non-positive stand-alone profit may be
    kept for network complementarity (feeder/trunk combinations), but only up to
    ``complementarity_share`` of the budget and it is flagged
    ``standalone_profitable = False`` - it is never presented as profitable.
    Near-duplicates (>= ``near_duplicate_jaccard`` port overlap) and rotations
    already in the pool are rejected with an explicit reason.

Cargo/revenue/cost accounting is NOT done here: the candidates only enter the pool;
the network MILP and the independent ledger decide what is served and count every
TEU and cost once.
"""

from __future__ import annotations

import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.network.economics import ServiceModelError, build_service_model
from src.services.service_feasibility import (
    ServiceFeasibilityError, rank_vessel_classes, rotation_ports,
)

# ---- stable rejection / skip identifiers -------------------------------------------
R_NO_RIDE_FEASIBLE_DEMAND = "no_ride_feasible_demand"
R_NOT_WORTH_ITS_VESSEL_TIME = "extra_port_does_not_pay_for_its_vessel_time"
R_MISSING_DISTANCE = "missing_directed_distance"
R_MISSING_PORT_RECORD = "missing_port_record"
R_NO_FEASIBLE_CLASS = "no_vessel_class_within_inventory"
R_PRICE_UNAVAILABLE = "bunker_price_unavailable"
R_DUPLICATE_OF_POOL = "duplicate_of_existing_rotation"
R_NEAR_DUPLICATE = "near_duplicate_of_selected_rotation"
R_NO_COMPLEMENTARITY = "no_uncovered_demand_and_not_standalone_profitable"
R_BUDGET = "budget_exhausted"

ENV_BUDGET = "LINER_DEMAND_LOOP_BUDGET"


@dataclass(frozen=True)
class DemandCoherentConfig:
    enabled: bool = True
    # most rotations emitted per call (one regional problem). 60 is where the controlled
    # 5-seed sweep peaked (mean weekly profit: 30 -> 3.9 M, 45 -> 4.8 M, 60 -> 6.0 M,
    # 90 -> 5.9 M, 120 -> 4.9 M; legacy pool 3.2 M); see reports/overnight_tasks_8_9_10.
    budget: int = 60
    min_ports: int = 3               # two-port rotations already exist in the pool
    max_ports: int = 5
    seed_pairs: int = 80             # strongest OD opportunities used as growth seeds
    neighbourhood: int = 12          # ports tried per growth step (strongest demand with the loop)
    covered_weight: float = 0.25     # value of an OD the pool already serves directly
    complementarity_share: float = 0.34
    near_duplicate_jaccard: float = 0.8
    sizing_buffer: float = 1.2       # same 20 % buffer the existing direct section uses

    def __post_init__(self):
        if self.min_ports < 3 or self.max_ports < self.min_ports:
            raise ValueError("need 3 <= min_ports <= max_ports")
        if self.budget < 0 or self.seed_pairs < 0 or self.neighbourhood < 1:
            raise ValueError("budget/seed_pairs must be >= 0 and neighbourhood >= 1")
        if not (0.0 <= self.covered_weight <= 1.0 and 0.0 <= self.complementarity_share <= 1.0):
            raise ValueError("covered_weight and complementarity_share must be in [0, 1]")


def config_from_environment(env: Optional[Dict[str, str]] = None) -> DemandCoherentConfig:
    """``LINER_DEMAND_LOOP_BUDGET``: integer budget per regional problem; ``0`` disables."""
    e = os.environ if env is None else env
    raw = e.get(ENV_BUDGET)
    if raw in (None, ""):
        return DemandCoherentConfig()
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_BUDGET} must be an integer, got {raw!r}") from None
    if n < 0:
        raise ValueError(f"{ENV_BUDGET} must be >= 0, got {n}")
    return DemandCoherentConfig(enabled=n > 0, budget=n)


# ----------------------------------------------------------------------------------
@dataclass
class RotationProposal:
    ports: Tuple[str, ...]
    vessel_class: str
    target_capacity_teu: float
    n_ports: int
    cycle_days: float
    cycle_time_days: int
    vessels_at_f1: int
    ride_feasible_ods: int
    uncovered_ods: int
    requested_teu: float
    served_teu_f1: float
    net_revenue_f1: float
    fixed_cost_f1: float
    standalone_profit_f1: float
    weighted_score: float
    standalone_profitable: bool
    seed_od: Tuple[str, str]
    reason_kept: str = ""

    def to_dict(self) -> Dict:
        d = dict(self.__dict__)
        d["ports"] = list(self.ports)
        d["seed_od"] = list(self.seed_od)
        return d


@dataclass
class DemandCoherentReport:
    seeds_used: int = 0
    grown_candidates: int = 0
    selected: int = 0
    standalone_profitable_selected: int = 0
    complementarity_selected: int = 0
    rejected: Counter = field(default_factory=Counter)
    selected_by_n_ports: Counter = field(default_factory=Counter)
    selected_by_class: Counter = field(default_factory=Counter)
    config: Optional[DemandCoherentConfig] = None

    def to_dict(self) -> Dict:
        return {
            "seeds_used": self.seeds_used, "grown_candidates": self.grown_candidates,
            "selected": self.selected,
            "standalone_profitable_selected": self.standalone_profitable_selected,
            "complementarity_selected": self.complementarity_selected,
            "rejected_by_reason": dict(self.rejected),
            "selected_by_n_ports": dict(self.selected_by_n_ports),
            "selected_by_class": dict(self.selected_by_class),
            "config": dict(self.config.__dict__) if self.config else None,
        }


# ----------------------------------------------------------------------------------
class _Demand:
    """Aggregated directed OD table (duplicates summed, revenue-weighted rate, tightest limit)."""

    def __init__(self, demands: Iterable, port_lookup: Dict):
        teu: Dict[Tuple[str, str], float] = defaultdict(float)
        rev: Dict[Tuple[str, str], float] = defaultdict(float)
        lim: Dict[Tuple[str, str], Optional[float]] = {}
        for d in demands:
            if not d.weekly_teu > 0 or d.origin == d.destination:
                continue
            k = (d.origin, d.destination)
            teu[k] += d.weekly_teu
            rev[k] += d.weekly_teu * d.revenue_per_teu
            ml = getattr(d, "max_transit_days", None)
            if ml is not None:
                lim[k] = ml if lim.get(k) is None else min(lim[k], ml)
            else:
                lim.setdefault(k, None)
        self.teu = dict(teu)
        self.limit = lim
        self.rate: Dict[Tuple[str, str], float] = {k: rev[k] / teu[k] for k in teu}
        self.net_rate: Dict[Tuple[str, str], float] = {}
        for (a, b), r in self.rate.items():
            pa, pb = port_lookup.get(a), port_lookup.get(b)
            var = 0.0
            for p in (pa, pb):
                var += float(getattr(p, "handling_cost", 0.0) or 0.0)
                var += float(getattr(p, "variable_port_call_cost", 0.0) or 0.0)
            self.net_rate[(a, b)] = r - var
        self.by_port: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for k in self.teu:
            self.by_port[k[0]].append(k)
            self.by_port[k[1]].append(k)

    def opportunity(self, k: Tuple[str, str]) -> float:
        return self.teu[k] * max(0.0, self.net_rate[k])


class _Evaluator:
    """Values a rotation under a class with the CANONICAL service model
    (``src.network.economics.ServiceModel``): cycle, vessels, capacity, ride times,
    hire, fuel at the pinned price and port calls come from that one definition - no
    cost or consumption field is read here."""

    def __init__(self, problem, fleet, assumptions, demand_all: _Demand, covered: set,
                 cfg: DemandCoherentConfig):
        self.dist = problem.distance_matrix
        self.fleet = fleet
        self.a = assumptions
        self.D = demand_all
        self.covered = covered
        self.cfg = cfg
        catalog = getattr(problem, "port_catalog", None)
        self.port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
        self.known = set(problem.distance_matrix)
        self.unit_status = getattr(fleet, "capacity_unit_status", "provisional")
        self._models: Dict[Tuple, Tuple] = {}

    @staticmethod
    def _reason(reasons) -> str:
        """Map the service model's reasons to this module's stable identifiers."""
        r = set(reasons or ())
        if "missing_directed_distance" in r or "invalid_distance" in r:
            return R_MISSING_DISTANCE
        if "missing_port_record" in r or "unknown_port" in r:
            return R_MISSING_PORT_RECORD
        if "bunker_price_unavailable" in r:
            return R_PRICE_UNAVAILABLE
        if "required_vessels_exceed_class_inventory" in r or "vessel_class_has_no_vessels" in r:
            return R_NO_FEASIBLE_CLASS
        return sorted(r)[0] if r else R_NO_FEASIBLE_CLASS

    def model(self, ports: Sequence[str], cls):
        """``(ServiceModel, None)`` or ``(None, reason)``; cached per rotation and class."""
        key = (tuple(ports), cls.vessel_class)
        hit = self._models.get(key)
        if hit is not None:
            return hit
        try:
            res = (build_service_model("dc", list(ports), cls, self.dist, self.port_lookup, self.a,
                                       known_ports=self.known,
                                       capacity_unit_status=self.unit_status), None)
        except ServiceModelError as exc:
            res = (None, self._reason(exc.reasons))
        self._models[key] = res
        return res

    def evaluate(self, ports: Sequence[str], cls, f: int = 1) -> Tuple[Optional[Dict], Optional[str]]:
        """Metrics of the rotation under ``cls`` at ``f`` weekly departures (default 1),
        or ``(None, reason)``. Capacity is ``cap * f`` on every leg; vessels
        ``ceil(cycle * f / 7)``; fuel and port-call cost scale with ``f``."""
        m, why = self.model(ports, cls)
        if m is None:
            return None, why
        if m.max_departures() < f:                       # f departures need more vessels than owned
            return None, R_NO_FEASIBLE_CLASS
        vessels = m.vessels(f)
        fixed = m.weekly_fixed_cost(f)
        cap = m.capacity_teu * f

        ods = []
        load = defaultdict(float)
        for a in m.ports:
            for b in m.ports:
                if a == b:
                    continue
                k = (a, b)
                t = self.D.teu.get(k)
                if not t:
                    continue
                ride = m.ride(a, b)
                if ride is None:
                    continue
                legs, days = ride
                lim = self.D.limit.get(k)
                if lim is not None and days > lim + 1e-9:
                    continue
                ods.append((k, t, legs))
                for lg in legs:
                    load[lg] += t
        if not ods:
            return None, R_NO_RIDE_FEASIBLE_DEMAND
        s_leg = {lg: min(1.0, cap / l) for lg, l in load.items()}
        served = net = weighted = 0.0
        uncovered = 0
        for k, t, legs in ods:
            sc = min(s_leg[lg] for lg in legs)
            v = t * sc
            served += v
            nr = max(0.0, self.D.net_rate[k])
            net += v * nr
            w = self.cfg.covered_weight if k in self.covered else 1.0
            if k not in self.covered:
                uncovered += 1
            weighted += w * v * nr
        peak = max(load.values())
        return {
            "cycle_days": m.cycle_days, "cycle_time_days": m.cycle_time_days, "vessels": vessels,
            "fixed": fixed, "net": net, "weighted": weighted, "served": served,
            "requested": sum(t for _, t, _ in ods), "n_ods": len(ods), "uncovered": uncovered,
            "peak_leg_load": peak, "standalone": net - fixed,
            "score": (weighted - fixed) / max(1, vessels), "cls": cls, "f": f,
            "sea_days": m.sea_days, "port_days": m.port_days,
            "fuel_tonnes": m.fuel_tonnes_per_rotation * f, "fuel_price": m.fuel_price_usd_per_t,
        }, None

    def pick_class(self, target_teu: float, ports: Sequence[str]):
        """First class (nearest capacity to ``target_teu``) whose inventory carries one
        weekly departure of this rotation - the rule ``_emit`` applies."""
        try:
            ranked = rank_vessel_classes(max(1.0, target_teu), self.fleet)
        except ServiceFeasibilityError:
            return None
        for c in ranked:
            m, why = self.evaluate(ports, c)
            if m is not None or why == R_NO_RIDE_FEASIBLE_DEMAND:
                return c
        return None


def _canonical(ports: Sequence[str]) -> Tuple[str, ...]:
    p = list(rotation_ports(ports))
    if not p:
        return tuple()
    i = min(range(len(p)), key=lambda k: p[k])
    return tuple(p[i:] + p[:i])


def covered_directed_ods(existing: Iterable[Tuple[Sequence[str], str]], problem, fleet,
                         assumptions, demand: _Demand) -> set:
    """Directed ODs that some pool service already serves directly within the limit."""
    out = set()
    catalog = getattr(problem, "port_catalog", None)
    port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
    known = set(problem.distance_matrix)
    unit_status = getattr(fleet, "capacity_unit_status", "provisional")
    cache: Dict[Tuple, Optional[object]] = {}
    for ports, cname in existing:
        cls = fleet.get_class(cname)
        if cls is None:
            continue
        p = tuple(rotation_ports(ports))
        if len(p) < 2:
            continue
        key = (p, cname)
        if key not in cache:
            try:
                cache[key] = build_service_model("covered", list(p), cls, problem.distance_matrix,
                                                 port_lookup, assumptions, known_ports=known,
                                                 capacity_unit_status=unit_status)
            except ServiceModelError:
                cache[key] = None
        m = cache[key]
        if m is None:
            continue
        for a in m.ports:
            for b in m.ports:
                if a == b or (a, b) not in demand.teu:
                    continue
                ride = m.ride(a, b)
                if ride is None:
                    continue
                lim = demand.limit.get((a, b))
                if lim is None or ride[1] <= lim + 1e-9:
                    out.add((a, b))
    return out


def generate_demand_coherent_rotations(
    problem,
    fleet,
    existing_services: Sequence[Tuple[Sequence[str], str]] = (),
    cfg: Optional[DemandCoherentConfig] = None,
    assumptions=None,
) -> Tuple[List[RotationProposal], DemandCoherentReport]:
    """Return at most ``cfg.budget`` demand-coherent closed rotations (never invalid ones).

    ``existing_services``: (ports, vessel_class) of the services already in the pool,
    used to avoid duplicates and to value only demand the pool does not serve yet.
    Seeds come from ``problem.demands`` (a regional problem's own origins); the value of
    a rotation is measured against ``problem.global_demands`` when present, so the
    reverse and cross-region flows it also carries are counted.
    """
    cfg = cfg or DemandCoherentConfig()
    report = DemandCoherentReport(config=cfg)
    if not cfg.enabled or cfg.budget <= 0:
        return [], report
    if fleet is None or not getattr(fleet, "classes", None):
        raise ServiceFeasibilityError(
            "problem.fleet is required to generate demand-coherent rotations; "
            "no default fleet or vessel class is assumed")
    if assumptions is None:
        from src.network.economics import assumptions_for_problem
        assumptions = assumptions_for_problem(problem)

    catalog = getattr(problem, "port_catalog", None)
    port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
    all_demands = getattr(problem, "global_demands", None) or problem.demands
    D = _Demand(all_demands, port_lookup)
    Dseed = _Demand(problem.demands, port_lookup)
    covered = covered_directed_ods(existing_services, problem, fleet, assumptions, D)
    ev = _Evaluator(problem, fleet, assumptions, D, covered, cfg)
    pool_rotations = {_canonical(p) for p, _ in existing_services}
    known = set(problem.distance_matrix)

    # seeds: strongest OD opportunities of this problem's own origins; each undirected
    # pair once (the loop closes both ways anyway)
    seeds, seen_pairs = [], set()
    for k in sorted(Dseed.teu, key=lambda k: (-Dseed.opportunity(k), k)):
        pair = tuple(sorted(k))
        if pair in seen_pairs or k[0] not in known or k[1] not in known:
            continue
        seen_pairs.add(pair)
        seeds.append(k)
        if len(seeds) >= cfg.seed_pairs:
            break
    report.seeds_used = len(seeds)

    ports_universe = [p for p in port_lookup if p in known]
    grown: Dict[Tuple[str, ...], Dict] = {}

    def proposal_from(ports: List[str], cls, m: Dict, seed: Tuple[str, str]) -> RotationProposal:
        return RotationProposal(
            ports=tuple(ports), vessel_class=cls.vessel_class,
            target_capacity_teu=max(1.0, m["peak_leg_load"] * cfg.sizing_buffer),
            n_ports=len(ports), cycle_days=m["cycle_days"], cycle_time_days=m["cycle_time_days"],
            vessels_at_f1=m["vessels"], ride_feasible_ods=m["n_ods"], uncovered_ods=m["uncovered"],
            requested_teu=m["requested"], served_teu_f1=m["served"], net_revenue_f1=m["net"],
            fixed_cost_f1=m["fixed"], standalone_profit_f1=m["standalone"],
            weighted_score=m["score"], standalone_profitable=m["standalone"] > 0.0, seed_od=seed)

    for seed in seeds:
        a, b = seed
        ports = [a, b]
        seed_teu = D.teu.get((a, b), 0.0) + D.teu.get((b, a), 0.0)
        cls = ev.pick_class(seed_teu * cfg.sizing_buffer, ports)
        if cls is None:
            report.rejected[R_NO_FEASIBLE_CLASS] += 1
            continue
        cur, why = ev.evaluate(ports, cls)
        cur_score = cur["score"] if cur else -math.inf
        for _ in range(cfg.max_ports - 2):
            # candidate ports: strongest demand with the current members
            link: Dict[str, float] = defaultdict(float)
            for m_ in ports:
                for k in D.by_port.get(m_, ()):
                    other = k[1] if k[0] == m_ else k[0]
                    if other not in ports and other in known:
                        link[other] += D.opportunity(k)
            if not link:
                break
            neigh = sorted(link, key=lambda p: (-link[p], p))[:cfg.neighbourhood]
            best = None
            for P in neigh:
                for pos in range(len(ports)):
                    new = ports[:pos + 1] + [P] + ports[pos + 1:]
                    m, why = ev.evaluate(new, cls)
                    if m is None:
                        report.rejected[why] += 1
                        continue
                    key = (m["score"], tuple(new))
                    if best is None or key[0] > best[0][0] or (key[0] == best[0][0] and key[1] < best[0][1]):
                        best = (key, new, m)
            if best is None:
                break
            (new_score, _), new_ports, m = best
            if new_score <= cur_score + 1e-9:
                report.rejected[R_NOT_WORTH_ITS_VESSEL_TIME] += 1
                break
            ports, cur, cur_score = new_ports, m, new_score
            if len(ports) >= cfg.min_ports:
                # re-derive the class from the grown rotation's own demand (legacy rule)
                c2 = ev.pick_class(m["peak_leg_load"] * cfg.sizing_buffer, ports) or cls
                m2, why2 = ev.evaluate(ports, c2) if c2 is not cls else (m, None)
                if m2 is None:
                    report.rejected[why2] += 1
                    continue
                key = _canonical(ports)
                prev = grown.get(key)
                if prev is None or m2["score"] > prev["m"]["score"]:
                    grown[key] = {"ports": list(ports), "cls": c2, "m": m2, "seed": seed}
    report.grown_candidates = len(grown)

    # ---- selection under the budget ------------------------------------------------
    ranked = sorted(grown.values(), key=lambda g: (-g["m"]["score"], tuple(g["ports"])))
    selected: List[RotationProposal] = []
    n_comp = 0
    max_comp = int(math.floor(cfg.complementarity_share * cfg.budget + 1e-9))
    for g in ranked:
        if len(selected) >= cfg.budget:
            report.rejected[R_BUDGET] += 1
            continue
        key = _canonical(g["ports"])
        if key in pool_rotations:
            report.rejected[R_DUPLICATE_OF_POOL] += 1
            continue
        pset = set(g["ports"])
        if any(len(pset & set(s.ports)) / len(pset | set(s.ports)) >= cfg.near_duplicate_jaccard
               for s in selected):
            report.rejected[R_NEAR_DUPLICATE] += 1
            continue
        pr = proposal_from(g["ports"], g["cls"], g["m"], g["seed"])
        if pr.standalone_profitable:
            pr.reason_kept = "standalone_profitable"
        else:
            if pr.uncovered_ods <= 0:
                report.rejected[R_NO_COMPLEMENTARITY] += 1
                continue
            if n_comp >= max_comp:
                report.rejected[R_BUDGET] += 1
                continue
            n_comp += 1
            pr.reason_kept = "complementarity_not_standalone_profitable"
        selected.append(pr)
        pool_rotations.add(key)

    report.selected = len(selected)
    report.standalone_profitable_selected = sum(1 for s in selected if s.standalone_profitable)
    report.complementarity_selected = len(selected) - report.standalone_profitable_selected
    for s in selected:
        report.selected_by_n_ports[s.n_ports] += 1
        report.selected_by_class[s.vessel_class] += 1
    return selected, report
