"""Route-level operators and elitism for the candidate pool.

Why this exists
    The candidate pool is built once per iteration from OD pairs and nothing in
    the pipeline *edits a rotation* or *remembers* a rotation that the global stage found
    worth operating: the regional GA only switches existing candidates on and off.  A good
    structure found in one iteration is therefore not available to the next, and the pool
    contains no neighbours of the rotations that actually carry the network.

What this does (all behind ``LINER_ROUTE_OPERATORS`` / ``LINER_ELITISM``; off = no effect)
    elites     the rotations (ports + vessel class) operated by the best verified network of
               the previous iteration (``problem.network_feedback``), re-offered unchanged -
               the pipeline-level analogue of GA elitism.  Without feedback (first
               iteration) the elites are the pool's own rotations with the best canonical
               stand-alone profit.
    operators  applied to every elite, each variant evaluated with the CANONICAL service
               model (``demand_coherent._Evaluator``: cycle, vessels, capacity, ride times,
               hire, fuel at the pinned price, port calls; transit-time limits respected):
                 insert   one port with real demand towards the rotation (unserved demand of
                          the previous network counts fully, served demand is discounted)
                 remove   the port whose ride-feasible cargo is least
                 swap     exchange two ports (a different visiting order)
                 reclass  the same rotation on another vessel class of the fleet
    selection  variants are ranked by the same complementarity-aware score as a
               rotation already in the pool (same cyclic order and class) is rejected, a
               near-duplicate (>= ``near_duplicate_jaccard`` port overlap AND the same class)
               of an already selected variant is rejected, and the number of variants is
               bounded by ``budget``.  A variant whose stand-alone profit is not positive is
               kept only if it covers demand no pool service carries directly, and only up to
               ``complementarity_share`` of the budget.

Nothing here accounts cargo, revenue or cost: candidates only enter the pool; the network MILP
and the independent ledger decide what is operated.  For fixed inputs the output is
deterministic (no random draw).
"""

from __future__ import annotations

import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.services.demand_coherent import (
    DemandCoherentConfig, _Demand, _Evaluator, _canonical, covered_directed_ods,
)
from src.services.service_feasibility import rotation_ports

ENV_OPERATORS = "LINER_ROUTE_OPERATORS"
ENV_ELITISM = "LINER_ELITISM"

R_DUPLICATE_OF_POOL = "duplicate_of_existing_rotation"
R_NEAR_DUPLICATE = "near_duplicate_of_selected_variant"
R_INFEASIBLE = "infeasible_variant"
R_NO_VALUE = "no_standalone_profit_and_no_uncovered_demand"
R_BUDGET = "budget_exhausted"
R_NOT_BETTER = "not_better_than_its_elite_and_not_complementary"


@dataclass(frozen=True)
class RouteOperatorConfig:
    budget: int = 0                      # operator variants emitted per regional problem
    elites: int = 20                     # elite rotations the operators start from
    insert_neighbourhood: int = 8        # ports tried per insertion
    complementarity_share: float = 0.34
    near_duplicate_jaccard: float = 0.8
    covered_weight: float = 0.25
    sizing_buffer: float = 1.2
    elitism: bool = False                # re-offer the previous iteration's operated rotations
    min_ports: int = 2
    max_ports: int = 6

    @property
    def enabled(self) -> bool:
        return self.budget > 0 or self.elitism

    def __post_init__(self):
        if self.budget < 0 or self.elites < 0 or self.insert_neighbourhood < 1:
            raise ValueError("budget/elites must be >= 0 and insert_neighbourhood >= 1")
        if self.min_ports < 2 or self.max_ports < self.min_ports:
            raise ValueError("need 2 <= min_ports <= max_ports")


def config_from_environment(env: Optional[Dict[str, str]] = None) -> RouteOperatorConfig:
    """``LINER_ROUTE_OPERATORS=<n>`` operator variants per regional problem (0 / unset = off);
    ``LINER_ELITISM=1`` re-offers the previous iteration's operated rotations."""
    e = os.environ if env is None else env
    kw: Dict = {}
    raw = (e.get(ENV_OPERATORS) or "").strip()
    if raw:
        try:
            n = int(raw)
        except ValueError:
            raise ValueError(f"{ENV_OPERATORS} must be an integer, got {raw!r}") from None
        if n < 0:
            raise ValueError(f"{ENV_OPERATORS} must be >= 0, got {n}")
        kw["budget"] = n
    el = (e.get(ENV_ELITISM) or "").strip().lower()
    if el in ("1", "true", "yes", "on"):
        kw["elitism"] = True
    elif el not in ("", "0", "false", "no", "off"):
        raise ValueError(f"{ENV_ELITISM} must be 0 or 1, got {el!r}")
    return RouteOperatorConfig(**kw)


@dataclass
class OperatorProposal:
    ports: Tuple[str, ...]
    vessel_class: str
    operator: str                      # elite | insert | remove | swap | reclass
    parent: Tuple[str, ...]
    target_capacity_teu: float
    score: float
    standalone_profit_f1: float
    uncovered_ods: int
    n_ports: int
    reason_kept: str = ""

    def to_dict(self) -> Dict:
        d = dict(self.__dict__)
        d["ports"], d["parent"] = list(self.ports), list(self.parent)
        return d


@dataclass
class OperatorReport:
    elites_in: int = 0
    elites_from_feedback: int = 0
    variants_evaluated: int = 0
    selected: int = 0
    elites_reoffered: int = 0
    selected_by_operator: Counter = field(default_factory=Counter)
    rejected: Counter = field(default_factory=Counter)
    config: Optional[RouteOperatorConfig] = None

    def to_dict(self) -> Dict:
        return {"elites_in": self.elites_in, "elites_from_feedback": self.elites_from_feedback,
                "variants_evaluated": self.variants_evaluated, "selected": self.selected,
                "elites_reoffered": self.elites_reoffered,
                "selected_by_operator": dict(self.selected_by_operator),
                "rejected_by_reason": dict(self.rejected),
                "config": dict(self.config.__dict__) if self.config else None}


def _dedupe_key(ports: Sequence[str], cls: str) -> Tuple[Tuple[str, ...], str]:
    return (_canonical(ports), cls)


def generate_operator_rotations(
    problem,
    fleet,
    existing: Sequence[Tuple[Sequence[str], str]],
    cfg: RouteOperatorConfig,
    *,
    assumptions=None,
    feedback: Optional[Dict] = None,
    elite_pool: Optional[Sequence[Tuple[Sequence[str], str]]] = None,
) -> Tuple[List[OperatorProposal], OperatorReport]:
    """Elites and operator variants to add to the pool (never invalid ones).

    ``existing``    (ports, class) of every rotation already in the pool;
    ``feedback``    ``problem.network_feedback`` of the previous iteration (operated rotations,
                    unserved OD TEU) or None;
    ``elite_pool``  without feedback: rotations of the pool ranked by the caller (best first)."""
    report = OperatorReport(config=cfg)
    if not cfg.enabled:
        return [], report
    if assumptions is None:
        from src.network.economics import assumptions_for_problem
        assumptions = assumptions_for_problem(problem)
    catalog = getattr(problem, "port_catalog", None)
    port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
    all_demands = getattr(problem, "global_demands", None) or problem.demands
    D = _Demand(all_demands, port_lookup)
    dc = DemandCoherentConfig(covered_weight=cfg.covered_weight, sizing_buffer=cfg.sizing_buffer)
    covered = covered_directed_ods(existing, problem, fleet, assumptions, D)
    ev = _Evaluator(problem, fleet, assumptions, D, covered, dc)
    known = set(problem.distance_matrix)

    unserved: Dict[Tuple[str, str], float] = {}
    if feedback:
        for key, teu in (feedback.get("unserved_od_teu") or {}).items():
            o, _, t = str(key).partition("|")
            unserved[(o, t)] = float(teu)

    # ---- elites ----------------------------------------------------------------------------
    elites: List[Tuple[Tuple[str, ...], str, str]] = []        # (ports, class, source)
    seen_e = set()
    if feedback and feedback.get("operated"):
        for row in feedback["operated"]:
            ports = tuple(rotation_ports(row.get("ports") or ()))
            cname = row.get("vessel_class")
            if len(ports) < 2 or not cname or fleet.get_class(cname) is None:
                continue
            if not all(p in known for p in ports):
                continue
            k = _dedupe_key(ports, cname)
            if k in seen_e:
                continue
            seen_e.add(k)
            elites.append((ports, cname, "feedback"))
        report.elites_from_feedback = len(elites)
    elif elite_pool:
        for ports, cname in elite_pool:
            ports = tuple(rotation_ports(ports))
            if len(ports) < 2 or fleet.get_class(cname) is None:
                continue
            k = _dedupe_key(ports, cname)
            if k in seen_e:
                continue
            seen_e.add(k)
            elites.append((ports, cname, "pool"))
            if len(elites) >= cfg.elites:
                break
    report.elites_in = len(elites)

    pool_keys = {_dedupe_key(p, c) for p, c in existing}
    out: List[OperatorProposal] = []
    selected_sets: List[Tuple[frozenset, str]] = []

    def accept_duplicate_check(ports, cname) -> Optional[str]:
        if _dedupe_key(ports, cname) in pool_keys:
            return R_DUPLICATE_OF_POOL
        pset = frozenset(ports)
        for s, c in selected_sets:
            if c == cname and len(pset & s) / len(pset | s) >= cfg.near_duplicate_jaccard:
                return R_NEAR_DUPLICATE
        return None

    # elitism: the previous network's rotations come back exactly as they were operated (they
    # are exempt from the duplicate-of-pool test only in the sense that a pool copy already is
    # one: a rotation the pool already holds is not offered twice)
    if cfg.elitism and feedback:
        for ports, cname, src in elites:
            if src != "feedback":
                continue
            if _dedupe_key(ports, cname) in pool_keys:
                report.rejected[R_DUPLICATE_OF_POOL] += 1
                continue
            m, why = ev.evaluate(ports, fleet.get_class(cname))
            if m is None:
                report.rejected[R_INFEASIBLE] += 1
                continue
            out.append(OperatorProposal(
                ports=tuple(ports), vessel_class=cname, operator="elite", parent=tuple(ports),
                target_capacity_teu=max(1.0, m["peak_leg_load"] * cfg.sizing_buffer),
                score=m["score"], standalone_profit_f1=m["standalone"], uncovered_ods=m["uncovered"],
                n_ports=len(ports), reason_kept="elite_of_previous_network"))
            pool_keys.add(_dedupe_key(ports, cname))
            selected_sets.append((frozenset(ports), cname))
            report.elites_reoffered += 1
            report.selected_by_operator["elite"] += 1

    if cfg.budget <= 0:
        report.selected = len(out)
        return out, report

    # ---- variants ----------------------------------------------------------------------------
    def link_value(k) -> float:
        base = D.opportunity(k)
        return base if (not unserved or k in unserved) else base * cfg.covered_weight

    variants: Dict[Tuple, Tuple[Dict, str, Tuple[str, ...], str, Tuple[str, ...]]] = {}

    def consider(ports: Sequence[str], cname: str, op: str, parent: Tuple[str, ...]):
        if len(ports) < cfg.min_ports or len(ports) > cfg.max_ports or len(set(ports)) != len(ports):
            return
        cls = fleet.get_class(cname)
        if cls is None:
            return
        key = _dedupe_key(ports, cname)
        if key in pool_keys or key in variants:
            return
        m, why = ev.evaluate(ports, cls)
        report.variants_evaluated += 1
        if m is None:
            report.rejected[R_INFEASIBLE] += 1
            return
        variants[key] = (m, cname, tuple(ports), op, parent)

    for ports, cname, _src in elites:
        ports = list(ports)
        # insert
        link: Dict[str, float] = defaultdict(float)
        for mem in ports:
            for k in D.by_port.get(mem, ()):
                other = k[1] if k[0] == mem else k[0]
                if other not in ports and other in known:
                    link[other] += link_value(k)
        for P in sorted(link, key=lambda p: (-link[p], p))[:cfg.insert_neighbourhood]:
            best = None
            for pos in range(len(ports)):
                new = ports[:pos + 1] + [P] + ports[pos + 1:]
                m, _why = ev.evaluate(new, fleet.get_class(cname))
                if m is not None and (best is None or m["score"] > best[0]):
                    best = (m["score"], new)
            if best is not None:
                consider(best[1], cname, "insert", tuple(ports))
        # remove
        if len(ports) > cfg.min_ports:
            for i in range(len(ports)):
                consider(ports[:i] + ports[i + 1:], cname, "remove", tuple(ports))
        # swap (different visiting order)
        if len(ports) >= 4:
            for i in range(len(ports)):
                for j in range(i + 2, len(ports)):
                    if i == 0 and j == len(ports) - 1:
                        continue
                    new = list(ports)
                    new[i], new[j] = new[j], new[i]
                    consider(new, cname, "swap", tuple(ports))
        # reclass
        for c in fleet.classes:
            if c.vessel_class != cname:
                consider(ports, c.vessel_class, "reclass", tuple(ports))

    ranked = sorted(variants.items(), key=lambda kv: (-kv[1][0]["score"], kv[0]))
    max_comp = int(math.floor(cfg.complementarity_share * cfg.budget + 1e-9))
    n_comp = 0
    n_variant = 0
    for key, (m, cname, ports, op, parent) in ranked:
        if n_variant >= cfg.budget:
            report.rejected[R_BUDGET] += 1
            continue
        why = accept_duplicate_check(ports, cname)
        if why is not None:
            report.rejected[why] += 1
            continue
        standalone = m["standalone"] > 0.0
        if standalone:
            reason = "standalone_profitable"
        else:
            if m["uncovered"] <= 0:
                report.rejected[R_NO_VALUE] += 1
                continue
            if n_comp >= max_comp:
                report.rejected[R_BUDGET] += 1
                continue
            n_comp += 1
            reason = "complementarity_not_standalone_profitable"
        out.append(OperatorProposal(
            ports=ports, vessel_class=cname, operator=op, parent=parent,
            target_capacity_teu=max(1.0, m["peak_leg_load"] * cfg.sizing_buffer),
            score=m["score"], standalone_profit_f1=m["standalone"], uncovered_ods=m["uncovered"],
            n_ports=len(ports), reason_kept=reason))
        pool_keys.add(key)
        selected_sets.append((frozenset(ports), cname))
        report.selected_by_operator[op] += 1
        n_variant += 1
    report.selected = len(out)
    return out, report
