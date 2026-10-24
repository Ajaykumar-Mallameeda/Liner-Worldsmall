"""Per-rotation vessel-class screening (Task 10).

Problem this addresses
    Candidate vessel classes were chosen by "nearest capacity to a hard-coded standard
    size" (``rank_vessel_classes``): the same rotation always got the same class
    regardless of its cycle time, the vessels it ties up, the fuel it burns or what
    the cargo can pay. Two of the six registered classes were never offered (Feeder_450
    is removed by the margin filter, Panamax_1200 is never "nearest" to a standard
    size) and "offer every class" is not a fix - it made the production selection
    worse (solver_findings.md section 1).

What this does
    For a rotation it evaluates EVERY registered class (diagnostics: why a class is
    feasible or not, what it would earn) and offers only a small, configurable set of
    alternatives to the optimiser:

      feasibility    canonical rule (``evaluate_rotation``): known class with vessels,
                     valid speeds/capacity, every directed leg has a distance, and the
                     rotation needs no more vessels than the class owns (one weekly
                     departure);
      economics      for the best weekly frequency f <= floor(7 * inventory / cycle):
                     capacity cap*f on EVERY leg, ride-feasible cargo only (transit
                     time limit), vessels ceil(cycle*f/7), hire + fuel (pinned price)
                     + port calls - the same model the optimiser and ledger use;
      selection      among classes with a positive stand-alone profit keep the one
                     with the highest profit and the one with the highest profit per
                     vessel (a scarce fleet rewards productivity), then the next best,
                     up to ``k``. A rotation with NO profitable class keeps the legacy
                     (nearest-capacity) class when it is feasible: stand-alone loss is
                     not evidence about which class helps a feeder/transfer role, and
                     "least loss" would always pick the cheapest, smallest ship. So the
                     screen changes a rotation's class only where the economics give
                     real evidence.

    Stand-alone profit is a screen, never a verdict: the network MILP and the
    independent ledger decide what is operated.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from src.network.economics import ServiceModelError, build_service_model
from src.services.demand_coherent import _Demand
from src.services.service_feasibility import (
    ServiceFeasibilityError, rank_vessel_classes, rotation_ports,
)

ENV_SCREEN = "LINER_CLASS_SCREEN"
ENV_TIME_FEASIBLE = "LINER_CLASS_TIME_FEASIBLE"

R_INFEASIBLE = "class_infeasible_for_rotation"
R_NO_FEASIBLE_CLASS = "no_feasible_class_for_rotation"
WHY_PROFIT = "highest_standalone_profit"
WHY_PRODUCTIVITY = "highest_profit_per_vessel"
WHY_NEXT = "next_best_standalone_profit"
WHY_LEAST_LOSS = "no_profitable_class_least_loss"
WHY_LEGACY = "no_direct_cargo_evidence_legacy_class"
WHY_LEGACY_UNPROFITABLE = "no_profitable_class_legacy_class_kept"
WHY_TIME_FEASIBLE = "legacy_class_cannot_meet_transit_limit_time_feasible_class"


@dataclass(frozen=True)
class ClassScreeningConfig:
    # alternatives offered per rotation; 0 = legacy nearest-capacity class. The default
    # is 1 (the single economically best class): in the controlled 5-seed experiment
    # k = 1 gave +2.5 M USD/week over the Task 9 pool (5/5 seeds) while k = 2 gave
    # +1.4 M, k = 3 +0.6 M and offering every feasible class -2.6 M (see
    # reports/overnight_tasks_8_9_10/task10_vessel_class_screening.md).
    k: int = 1
    max_frequency: int = 14          # upper bound of the frequency search per class
    # False = DIAGNOSTIC naive enumeration: offer every feasible class (no economic
    # screen). It exists to reproduce the "offer every class" experiment; it is not
    # a production setting.
    economic_screen: bool = True
    # A rotation with no profitable class keeps the legacy (nearest-capacity) class -
    # unless that class cannot carry ANY cargo of the rotation inside the transit limits while
    # another class can: then the class that can is offered (best stand-alone result among
    # those).  Off = the Task 10 behaviour exactly.
    time_feasible: bool = False

    def __post_init__(self):
        if self.k < 0 or self.max_frequency < 1:
            raise ValueError("k must be >= 0 and max_frequency >= 1")

    @property
    def enabled(self) -> bool:
        return self.k > 0


def _base_config_from_environment(env: Optional[Dict[str, str]] = None) -> ClassScreeningConfig:
    """``LINER_CLASS_SCREEN``: alternatives kept per rotation; unset = the default
    (1); ``0`` = legacy nearest-capacity assignment; ``all`` = diagnostic enumeration
    of every feasible class (no economic screen)."""
    e = os.environ if env is None else env
    raw = e.get(ENV_SCREEN)
    if raw in (None, ""):
        return ClassScreeningConfig()
    if str(raw).strip().lower() == "all":
        return ClassScreeningConfig(k=99, economic_screen=False)
    try:
        k = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_SCREEN} must be an integer, got {raw!r}") from None
    if k < 0:
        raise ValueError(f"{ENV_SCREEN} must be >= 0, got {k}")
    return ClassScreeningConfig(k=k)


def config_from_environment(env: Optional[Dict[str, str]] = None) -> ClassScreeningConfig:
    """The screening configuration in force: ``LINER_CLASS_SCREEN`` (see above) plus
    ``LINER_CLASS_TIME_FEASIBLE`` (Task 21: do not keep a class that cannot meet any transit
    limit of the rotation when another class can).  Default ON; it acts only while the class
    screening itself is enabled (``LINER_CLASS_SCREEN=0`` is the exact legacy assignment);
    ``LINER_CLASS_TIME_FEASIBLE=0`` restores the Task 10 behaviour."""
    import dataclasses
    e = os.environ if env is None else env
    cfg = _base_config_from_environment(env)
    raw = (e.get(ENV_TIME_FEASIBLE) or "").strip().lower()
    if raw in ("", "1", "true", "yes", "on"):
        return dataclasses.replace(cfg, time_feasible=True)
    if raw not in ("0", "false", "no", "off"):
        raise ValueError(f"{ENV_TIME_FEASIBLE} must be 0 or 1, got {raw!r}")
    return cfg


@dataclass
class ClassEvaluation:
    vessel_class: str
    feasible: bool
    reasons: List[str]
    capacity_teu: float = 0.0
    design_speed: float = 0.0
    inventory: int = 0
    cycle_days: Optional[float] = None
    cycle_time_days: Optional[int] = None
    vessels_f1: Optional[int] = None
    max_departures: int = 0
    direct_ride_feasible_ods: int = 0
    direct_ride_feasible_teu: float = 0.0
    best_frequency: int = 0
    vessels_at_best: int = 0
    served_teu_best: float = 0.0
    net_revenue_best: float = 0.0
    fixed_cost_best: float = 0.0
    fuel_cost_best: float = 0.0
    fuel_tonnes_best: float = 0.0
    standalone_profit_best: float = 0.0
    profit_per_vessel: float = 0.0
    promising: bool = False
    selected_because: str = ""

    def to_dict(self) -> Dict:
        return dict(self.__dict__)


@dataclass
class ScreeningResult:
    ports: Tuple[str, ...]
    legacy_class: Optional[str]
    evaluations: List[ClassEvaluation]
    selected: List[ClassEvaluation]
    reason: str = ""
    # the nearest-capacity class could not carry this rotation (the legacy rule
    # would have had to fall back to a further class)
    legacy_fallback: bool = False


@dataclass
class ScreeningReport:
    rotations_screened: int = 0
    rotations_without_feasible_class: int = 0
    alternatives_emitted: int = 0
    rotations_with_multiple_alternatives: int = 0
    legacy_class_kept: int = 0
    legacy_class_replaced: int = 0
    infeasible_combinations: Counter = field(default_factory=Counter)      # reason -> n
    feasible_combinations: Counter = field(default_factory=Counter)        # class -> n
    promising_combinations: Counter = field(default_factory=Counter)       # class -> n
    selected_by_class: Counter = field(default_factory=Counter)
    selected_because: Counter = field(default_factory=Counter)

    def record(self, res: ScreeningResult) -> None:
        self.rotations_screened += 1
        for e in res.evaluations:
            if e.feasible:
                self.feasible_combinations[e.vessel_class] += 1
                if e.promising:
                    self.promising_combinations[e.vessel_class] += 1
            else:
                for r in e.reasons:
                    self.infeasible_combinations[r] += 1
        if not res.selected:
            self.rotations_without_feasible_class += 1
            return
        self.alternatives_emitted += len(res.selected)
        if len(res.selected) > 1:
            self.rotations_with_multiple_alternatives += 1
        names = [e.vessel_class for e in res.selected]
        if res.legacy_class is not None:
            if res.legacy_class in names:
                self.legacy_class_kept += 1
            else:
                self.legacy_class_replaced += 1
        for e in res.selected:
            self.selected_by_class[e.vessel_class] += 1
            self.selected_because[e.selected_because] += 1

    def to_dict(self) -> Dict:
        return {
            "rotations_screened": self.rotations_screened,
            "rotations_without_feasible_class": self.rotations_without_feasible_class,
            "alternatives_emitted": self.alternatives_emitted,
            "rotations_with_multiple_alternatives": self.rotations_with_multiple_alternatives,
            "legacy_class_kept": self.legacy_class_kept,
            "legacy_class_replaced": self.legacy_class_replaced,
            "infeasible_combinations_by_reason": dict(self.infeasible_combinations),
            "feasible_combinations_by_class": dict(self.feasible_combinations),
            "promising_combinations_by_class": dict(self.promising_combinations),
            "selected_by_class": dict(self.selected_by_class),
            "selected_because": dict(self.selected_because),
        }


# ----------------------------------------------------------------------------------
class ClassScreener:
    """Evaluate all classes of a rotation and select the alternatives to offer."""

    def __init__(self, problem, fleet, assumptions, cfg: ClassScreeningConfig):
        if fleet is None or not getattr(fleet, "classes", None):
            raise ServiceFeasibilityError(
                "problem.fleet is required for class screening; no default class is assumed")
        self.problem, self.fleet, self.a, self.cfg = problem, fleet, assumptions, cfg
        catalog = getattr(problem, "port_catalog", None)
        self.port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
        self.dist = problem.distance_matrix
        self.known = set(self.dist)
        demands = getattr(problem, "global_demands", None) or problem.demands
        self.D = _Demand(demands, self.port_lookup)
        self._cache: Dict[Tuple, ScreeningResult] = {}
        self.report = ScreeningReport()

    # ---- one class on one rotation ---------------------------------------------------
    def evaluate_class(self, ports: Sequence[str], cls) -> ClassEvaluation:
        """Feasibility and stand-alone economics of ``cls`` on the rotation, both from
        the canonical service model (the one the optimiser and the ledger use)."""
        ev = ClassEvaluation(
            vessel_class=cls.vessel_class, feasible=False, reasons=[],
            capacity_teu=float(cls.capacity_teu), design_speed=float(cls.design_speed),
            inventory=int(cls.quantity))
        try:
            m = build_service_model(
                "screen", list(ports), cls, self.dist, self.port_lookup, self.a,
                known_ports=self.known,
                capacity_unit_status=getattr(self.fleet, "capacity_unit_status", "provisional"))
        except ServiceModelError as exc:
            ev.reasons = list(exc.reasons) or ["infeasible"]
            return ev
        ev.feasible = True
        ev.cycle_days, ev.cycle_time_days = m.cycle_days, m.cycle_time_days
        ev.vessels_f1 = m.vessels(1)
        ev.max_departures = m.max_departures()

        ods = []                                   # (teu, net_rate, legs)
        for a in m.ports:
            for b in m.ports:
                if a == b:
                    continue
                k = (a, b)
                teu = self.D.teu.get(k)
                if not teu:
                    continue
                ride = m.ride(a, b)
                if ride is None:
                    continue
                legs, days = ride
                lim = self.D.limit.get(k)
                if lim is not None and days > lim + 1e-9:
                    continue
                ods.append((teu, max(0.0, self.D.net_rate[k]), legs))
        ev.direct_ride_feasible_ods = len(ods)
        ev.direct_ride_feasible_teu = sum(o[0] for o in ods)
        if not ods or ev.max_departures < 1:
            return ev
        # bound the frequency search by what the cargo could ever fill
        peak = {}
        for teu, _, legs in ods:
            for lg in legs:
                peak[lg] = peak.get(lg, 0.0) + teu
        need_f = int(math.ceil(max(peak.values()) / m.capacity_teu))
        fmax = max(1, min(ev.max_departures, need_f, self.cfg.max_frequency))
        best = None
        for f in range(1, fmax + 1):
            cap = m.weekly_leg_capacity(f)
            s_leg = {lg: min(1.0, cap / load) for lg, load in peak.items()}
            served = net = 0.0
            for teu, nr, legs in ods:
                v = teu * min(s_leg[lg] for lg in legs)
                served += v
                net += v * nr
            fixed = m.weekly_fixed_cost(f)
            profit = net - fixed
            if best is None or profit > best[0] + 1e-9:
                best = (profit, f, m.vessels(f), served, net, fixed, m.weekly_fuel_cost(f),
                        f * m.fuel_tonnes_per_rotation)
        if best is not None:
            (ev.standalone_profit_best, ev.best_frequency, ev.vessels_at_best, ev.served_teu_best,
             ev.net_revenue_best, ev.fixed_cost_best, ev.fuel_cost_best, ev.fuel_tonnes_best) = best
            ev.profit_per_vessel = ev.standalone_profit_best / max(1, ev.vessels_at_best)
            ev.promising = ev.standalone_profit_best > 0.0
        return ev

    # ---- selection -----------------------------------------------------------------------
    @staticmethod
    def _rotation_key(ports: Sequence[str]) -> Tuple[str, ...]:
        """The rotation itself: the same cycle in the same direction, whichever port
        it is written from (direction matters: directed distances differ)."""
        p = list(ports)
        i = min(range(len(p)), key=lambda k: p[k]) if p else 0
        return tuple(p[i:] + p[:i])

    def screen(self, route: Sequence[str], target_capacity: float) -> ScreeningResult:
        """Screen one rotation. The outcome is a property of the ROTATION: the same
        rotation proposed by several generator sections (with different sizing
        targets) gets the same alternatives, so the configured maximum per rotation
        holds across the pool. The first sizing target seen decides the legacy class
        of a rotation that has no profitable class (generation order is fixed)."""
        ports = tuple(rotation_ports(route))
        key = self._rotation_key(ports)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        # every registered class is evaluated (a class with no vessels is reported
        # as infeasible with its reason, never silently skipped)
        evals = [self.evaluate_class(ports, c) for c in self.fleet.classes]
        legacy = None
        legacy_fallback = False
        try:
            for rank, c in enumerate(rank_vessel_classes(max(1.0, target_capacity), self.fleet)):
                e = next((x for x in evals if x.vessel_class == c.vessel_class), None)
                if e is not None and e.feasible:
                    legacy = c.vessel_class
                    legacy_fallback = rank > 0
                    break
        except ServiceFeasibilityError:
            legacy = None
        feasible = [e for e in evals if e.feasible]
        selected: List[ClassEvaluation] = []
        if feasible and not self.cfg.economic_screen:
            for e in sorted(feasible, key=lambda x: x.capacity_teu):
                e.selected_because = "diagnostic_enumeration_of_every_feasible_class"
                selected.append(e)
        elif feasible:
            promising = [e for e in feasible if e.promising]
            if promising:
                order = sorted(promising, key=lambda e: (-e.standalone_profit_best, e.capacity_teu))
                first = order[0]
                first.selected_because = WHY_PROFIT
                selected.append(first)
                if self.cfg.k > 1:
                    prod = sorted(promising, key=lambda e: (-e.profit_per_vessel, e.capacity_teu))
                    for e in prod:
                        if e not in selected:
                            e.selected_because = WHY_PRODUCTIVITY
                            selected.append(e)
                            break
                for e in order:
                    if len(selected) >= self.cfg.k:
                        break
                    if e not in selected:
                        e.selected_because = WHY_NEXT
                        selected.append(e)
                selected = selected[:self.cfg.k]
            else:
                has_cargo = any(e.direct_ride_feasible_ods > 0 and e.best_frequency > 0 for e in feasible)
                legacy_eval = next((x for x in feasible if x.vessel_class == legacy), None)
                carriers = [e for e in feasible
                            if e.direct_ride_feasible_ods > 0 and e.best_frequency > 0]
                if (self.cfg.time_feasible and legacy_eval is not None
                        and not (legacy_eval.direct_ride_feasible_ods > 0
                                 and legacy_eval.best_frequency > 0) and carriers):
                    # the legacy class cannot carry anything of this rotation inside the
                    # transit limits; a class that can is offered instead 
                    e = max(carriers, key=lambda x: (x.standalone_profit_best, -x.capacity_teu))
                    e.selected_because = WHY_TIME_FEASIBLE
                    selected = [e]
                elif legacy_eval is not None:
                    legacy_eval.selected_because = WHY_LEGACY_UNPROFITABLE if has_cargo else WHY_LEGACY
                    selected = [legacy_eval]
                else:
                    pool = [e for e in feasible if e.direct_ride_feasible_ods > 0 and e.best_frequency > 0] \
                        or feasible
                    e = max(pool, key=lambda x: (x.standalone_profit_best, -x.capacity_teu))
                    e.selected_because = WHY_LEAST_LOSS if has_cargo else WHY_LEGACY
                    selected = [e]
        res = ScreeningResult(ports=ports, legacy_class=legacy, evaluations=evals, selected=selected,
                              reason="" if selected else R_NO_FEASIBLE_CLASS,
                              legacy_fallback=legacy_fallback)
        self._cache[key] = res
        self.report.record(res)
        return res

    def alternatives(self, route: Sequence[str], target_capacity: float) -> List[str]:
        """Class names to offer for this rotation, best first (empty = none feasible)."""
        return [e.vessel_class for e in self.screen(route, target_capacity).selected]
