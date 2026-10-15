"""Network design MILP over candidate services and OD paths.

Decision variables
    f_s  integer  weekly departures of service s            (0 = not operated)
    n_s  integer  vessels deployed on service s
    q_p  >= 0     TEU/week of OD d routed on path p
    u_d  >= 0     TEU/week of OD d left unserved

Constraints
    demand        sum_p q_p + u_d == weekly_teu_d                     (each OD once)
    leg capacity  sum_{p uses (s,leg)} q_p <= capacity_s * f_s        (EVERY leg)
    vessels       7 * n_s >= cycle_time_days_s * f_s                  (ceil(T f / 7))
    fleet         sum_{s in class c} n_s <= vessels available of c    (per class)

Objective (maximise)
    sum_p (revenue_per_teu_d - port_cost_per_teu_p) q_p
    - sum_s [ vessel_week_cost_s n_s + (rotation_fuel_s + port_fixed_s) f_s ]
    - unserved_penalty * sum_d u_d          <- optimisation-only; default 0.0

With ``unserved_penalty = 0`` the objective IS the operating profit. Any penalty is
reported separately (``objective_components``) and is never part of the ledger.
Transit-time limits are enforced when paths are built (see ``paths.py``).

Solution method (``lp_guided=True``, default when frequencies are free)
    1. solve the LP relaxation (f, n continuous): its value is a valid UPPER BOUND
       on the achievable profit and is reported as ``relaxation_bound``;
    2. keep only the services the relaxation uses and the paths that use only them,
       and solve the integer problem on that restriction.
    The restriction can exclude better integer solutions, so the result is a
    feasible plan with a stated bound, not a proof of optimality: ``status`` is
    ``"optimal"`` only if the restricted MILP closed AND no service was dropped.

Optional strengthening (``LINER_MILP_VUB``, default OFF)
    adds the valid inequality  q[od, p] <= weekly_teu[od] * f[s]  for every path p of an OD and
    every service s the path rides ("variable upper bound" / VUB).  It is implied by the integer
    model (q <= demand, and an operated service has f >= 1; a service with f = 0 carries nothing)
    so it removes no integer-feasible point; it only removes fractional LP points that run a
    service at a small fraction of a weekly sailing.  It is applied to the LP relaxation (bound
    and LP-guided restriction) and to the integer problem alike, and only for free-frequency
    solves (with imposed frequencies it is redundant and skipped).

Backend (``NETWORK_MILP_BACKEND``, default ``cbc``)
    ``cbc``    the bundled CBC through PuLP, as above (the production default).
    ``highs``  OPT-IN.  The unrestricted integer problem (no LP restriction) is solved by
               HiGHS through ``scipy.optimize.milp`` (``scipy`` is already a pinned
               requirement; no package is added).  It applies to free-frequency solves
               only - solves with ``fixed_frequencies`` always use CBC.  HiGHS has no warm
               start in this interface, so ``initial_frequencies`` is not used.  ``status``
               is ``"optimal"`` only when HiGHS reports optimality (relative MIP gap <= 1e-4,
               reported as ``mip_gap``); otherwise the incumbent is ``"feasible"`` and the MIP
               dual bound is reported as ``relaxation_bound``.  An unsupported value is a
               ``solver_error``, never a silent fallback to another solver.
"""

from __future__ import annotations

import logging
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import pulp

from src.network.economics import ServiceModel
from src.network.paths import OdPath

logger = logging.getLogger(__name__)


@dataclass
class NetworkSolution:
    status: str                          # optimal | feasible | infeasible | not_solved | solver_error
    solver_status: str = ""
    message: str = ""
    objective_value: float = 0.0
    relaxation_bound: Optional[float] = None     # LP upper bound on the objective
    frequencies: Dict[int, int] = field(default_factory=dict)     # service index -> f
    vessels: Dict[int, int] = field(default_factory=dict)         # service index -> n
    flows: List[Tuple[int, int, float]] = field(default_factory=list)  # (od, path#, TEU)
    unserved: Dict[int, float] = field(default_factory=dict)
    objective_components: Dict[str, float] = field(default_factory=dict)
    n_variables: int = 0
    n_constraints: int = 0
    n_paths: int = 0
    n_services_considered: int = 0
    n_services_restricted_to: int = 0
    runtime_sec: float = 0.0
    # A time-limited incumbent may carry vessels above ceil(T f / 7): the vessel constraint
    # is only a lower bound, and the solver stops before it removes the slack.  Those
    # vessels are trimmed to the minimum the constraint needs (exactly what the
    # independent ledger charges); the amount removed is reported here.
    vessel_slack_removed: int = 0
    vessel_slack_cost_usd: float = 0.0
    solver_backend: str = "cbc"
    mip_gap: Optional[float] = None              # relative gap reported by the backend (HiGHS)
    # which optional formulation changes were applied (LINER_MILP_VUB ...); empty = the baseline model
    formulation: Dict = field(default_factory=dict)
    # set when the integer problem used a path set rebuilt for the LP-support services
    # (``path_rebuild``): flows then index THIS dict, not the caller's ``paths_by_od``
    paths_by_od: Optional[Dict] = None
    # raw closure facts behind the application-level conclusion (see ``solve_semantics``)
    closed_by_solver: Optional[bool] = None            # CBC sol_status == Optimal (HiGHS: proven within its gap)
    restricted_to_lp_support: bool = False             # integer problem solved on the LP-support services only
    time_limit_reached: bool = False
    integer_phase_sec: float = 0.0
    integer_phase_budget_sec: float = 0.0

    @property
    def usable(self) -> bool:
        """A solution whose values may be reported (optimal, or a feasible incumbent)."""
        return self.status in ("optimal", "feasible")


def _trim_slack_vessels(models, sol: "NetworkSolution", active) -> None:
    """Reduce every service's vessel count to ``ceil(T f / 7)`` (in place).

    Feasibility is preserved by construction: ``7 n >= T f`` holds with equality at the
    minimum, and the per-class fleet constraints only get looser.  The plan (frequencies,
    flows) is unchanged; only the vessel cost that the MILP objective reports falls to what
    the plan actually needs, so the objective equals the independent ledger's profit."""
    slack_n, slack_cost = 0, 0.0
    for si in active:
        need = models[si].vessels(int(sol.frequencies.get(si, 0)))
        have = int(sol.vessels.get(si, 0))
        if have > need:
            slack_n += have - need
            slack_cost += (have - need) * models[si].vessel_week_cost
            sol.vessels[si] = need
    if slack_n:
        sol.vessel_slack_removed = slack_n
        sol.vessel_slack_cost_usd = slack_cost
        sol.objective_components["vessel_cost"] = (
            sol.objective_components.get("vessel_cost", 0.0) - slack_cost)
        sol.objective_value += slack_cost


#: A routed quantity at or below this (TEU/week) is solver feasibility noise, not a flow.
#: HiGHS / CBC accept constraint violations of ~1e-7..1e-9, so a path through a service that
#: is not operated (``q <= capacity * f`` with ``f = 0``) can carry ~1e-9 TEU; reporting it
#: would present a flow on an inactive service.  A quantity above this on an inactive service
#: is NOT dropped: the independent ledger flags it.
FLOW_NOISE_TEU = 1e-6

#: relative MIP gap at which HiGHS's own optimality status is accepted as "optimal" (its
#: default ``mip_rel_gap``); the gap actually reached is always reported in ``mip_gap``
HIGHS_OPTIMAL_GAP = 1e-4


def _backend_name() -> str:
    return (os.environ.get("NETWORK_MILP_BACKEND") or "cbc").strip().lower()


ENV_VUB = "LINER_MILP_VUB"


def vub_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    """``LINER_MILP_VUB``: add the valid inequality q <= demand * f (see the module docstring).
    Unset / empty / 0 = off (the baseline model).  A malformed value raises ``ValueError``."""
    raw = ((os.environ if env is None else env).get(ENV_VUB) or "").strip().lower()
    if raw in ("", "0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    raise ValueError(f"{ENV_VUB} must be 0 or 1, got {raw!r}")


ENV_LP_ROUND_START = "LINER_MILP_LP_ROUND_START"


def lp_round_start_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    """``LINER_MILP_LP_ROUND_START``: give CBC an integer starting solution built from the LP relaxation
    (frequencies rounded half-up, then repaired to the class fleet limits).  Unset / 0 = off (default).
    A malformed value raises ``ValueError``."""
    raw = ((os.environ if env is None else env).get(ENV_LP_ROUND_START) or "").strip().lower()
    if raw in ("", "0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    raise ValueError(f"{ENV_LP_ROUND_START} must be 0 or 1, got {raw!r}")


def lp_rounded_start(models, lp_f: Dict[int, float], limits: Dict[str, int]) -> Tuple[Dict[int, int], Dict]:
    """Integer frequencies from the LP relaxation's values ``lp_f`` (service index -> f), feasible for the fleet.

    f0 = round-half-up(f_lp) (a service the LP runs at >= 0.25 of a sailing is opened at one weekly sailing);
    vessels needed = ceil(T f0 / 7) per service; while a class needs more vessels than ``limits`` allows, the
    service of that class with the smallest LP frequency loses one sailing (to 0 = not operated).  Nothing
    here prices cargo: the solver completes the start (cargo flows) and may discard it."""
    f0: Dict[int, int] = {}
    for si, v in lp_f.items():
        x = float(v or 0.0)
        r = int(math.floor(x + 0.5))
        if r == 0 and x >= 0.25:
            r = 1
        if r > 0:
            f0[si] = min(r, int(models[si].max_departures(int(limits.get(models[si].vessel_class, models[si].class_inventory)))))
    dropped = 0
    by_class: Dict[str, List[int]] = defaultdict(list)
    for si in f0:
        by_class[models[si].vessel_class].append(si)
    for cls, sis in by_class.items():
        limit = int(limits.get(cls, models[sis[0]].class_inventory))
        while True:
            live = [s for s in sis if f0.get(s, 0) > 0]
            need = sum(models[s].vessels(f0[s]) for s in live)
            if need <= limit or not live:
                break
            worst = min(live, key=lambda s: (float(lp_f.get(s, 0.0)), -models[s].vessels(f0[s]), s))
            f0[worst] -= 1
            dropped += 1
    f0 = {s: f for s, f in f0.items() if f > 0}
    return f0, {"services": len(f0), "sailings": sum(f0.values()), "repair_steps": dropped}


def _solve_highs(res, deadline: float) -> dict:
    """Solve the PuLP model held in ``res`` (built, not solved) with HiGHS through
    ``scipy.optimize.milp`` and write the values back onto the PuLP variables, so the
    caller's extraction code is the same as for CBC.  ``deadline`` is a
    ``time.perf_counter()`` instant: matrix construction counts against the budget.
    Returns ``{"mip_gap", "dual_bound", "error", "message"}``; never raises."""
    info = {"mip_gap": None, "dual_bound": None, "error": None, "message": ""}
    prob = res["prob"]
    if not res["q"]:
        return info
    try:
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp
        from scipy.sparse import coo_matrix

        vars_ = prob.variables()
        idx = {v.name: i for i, v in enumerate(vars_)}
        nvar = len(vars_)
        c = np.zeros(nvar)
        for v, coef in prob.objective.items():
            c[idx[v.name]] = -float(coef)                    # maximise -> minimise
        lo = np.array([-np.inf if v.lowBound is None else float(v.lowBound) for v in vars_])
        hi = np.array([np.inf if v.upBound is None else float(v.upBound) for v in vars_])
        integrality = np.array([1 if v.cat == pulp.LpInteger else 0 for v in vars_])
        rows, cols, vals = [], [], []
        lb = np.full(len(prob.constraints), -np.inf)
        ub = np.full(len(prob.constraints), np.inf)
        for r, con in enumerate(prob.constraints.values()):
            for v, coef in con.items():
                rows.append(r)
                cols.append(idx[v.name])
                vals.append(float(coef))
            rhs = -float(con.constant)
            if con.sense == pulp.LpConstraintLE:
                ub[r] = rhs
            elif con.sense == pulp.LpConstraintGE:
                lb[r] = rhs
            else:
                lb[r] = ub[r] = rhs
        A = coo_matrix((vals, (rows, cols)), shape=(len(prob.constraints), nvar)).tocsr()
        r = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=integrality,
                 bounds=Bounds(lo, hi),
                 options={"time_limit": max(1.0, deadline - time.perf_counter()),
                          "disp": False})
    except Exception as exc:                                   # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    info["message"] = str(getattr(r, "message", ""))
    gap = getattr(r, "mip_gap", None)
    bound = getattr(r, "mip_dual_bound", None)
    info["mip_gap"] = float(gap) if gap is not None and math.isfinite(float(gap)) else None
    if bound is not None and math.isfinite(float(bound)):
        info["dual_bound"] = -float(bound)                     # back to a profit upper bound
    if getattr(r, "x", None) is None:
        # no incumbent: infeasible (status 2) or limit reached without a solution
        prob.status = pulp.LpStatusInfeasible if r.status == 2 else pulp.LpStatusNotSolved
        return info
    for v in vars_:
        v.varValue = float(r.x[idx[v.name]])
    prob.status = pulp.LpStatusOptimal
    proven = (r.status == 0) and (info["mip_gap"] is None or info["mip_gap"] <= HIGHS_OPTIMAL_GAP)
    prob.sol_status = pulp.LpSolutionOptimal if proven else pulp.LpSolutionIntegerFeasible
    return info


def _solver(time_limit_sec: float, threads: Optional[int], warm: bool):
    # threads is opt-in: the bundled parallel CBC stalled (idle, ignoring its time
    # limit) on a 5k-row model, so the default is the single-threaded solver.
    return pulp.PULP_CBC_CMD(
        msg=bool(os.environ.get("NETWORK_MILP_LOG")),
        timeLimit=max(1, int(math.ceil(time_limit_sec))),
        threads=threads if threads and threads > 1 else None,
        warmStart=warm,
    )


def _build_and_solve(
    models, demands, paths_by_od, limits, services: Sequence[int], *, integer: bool,
    penalty: float, fixed: Optional[Dict[int, int]], initial: Optional[Dict[int, int]],
    max_departures_cap: Optional[int], time_limit_sec: float, threads: Optional[int],
    total_vessel_limit: Optional[int] = None,
    port_capacity: Optional[Dict[str, float]] = None,
    min_served_fraction: Optional[float] = None,
    solve: bool = True,
    vub: bool = False,
):
    """Build the model over ``services`` (indices) and solve it (``solve=False``: build
    only, the caller solves with another backend). Returns a dict with
    the PuLP problem, variables and statuses; raises nothing for solver outcomes."""
    keep = set(services)
    # only paths whose every segment service is kept
    sub_paths: Dict[int, List[Tuple[int, OdPath]]] = {}
    used: Dict[int, float] = defaultdict(float)
    for di, plist in paths_by_od.items():
        kept = [(k, p) for k, p in enumerate(plist) if all(s in keep for s in p.services)]
        if kept:
            sub_paths[di] = kept
            for _, p in kept:
                for si in p.services:
                    used[si] += demands[di].weekly_teu
    active = sorted(used)

    prob = pulp.LpProblem("NetworkDesign", pulp.LpMaximize)
    cat = "Integer" if integer else "Continuous"
    f: Dict[int, pulp.LpVariable] = {}
    n: Dict[int, pulp.LpVariable] = {}
    for si in active:
        m = models[si]
        limit = int(limits.get(m.vessel_class, m.class_inventory))
        ub = m.max_departures(limit)
        if max_departures_cap is not None:
            ub = min(ub, int(max_departures_cap))
        ub = min(ub, max(1, int(math.ceil(used[si] / m.capacity_teu))))
        if fixed is not None:
            # imposed exactly; an unsustainable frequency makes the fleet constraint
            # infeasible (explicit status) - it is never silently clipped
            lb = ub = max(0, int(fixed.get(si, 0)))
        else:
            lb = 0
        f[si] = pulp.LpVariable(f"f_{si}", lowBound=lb, upBound=max(ub, 0), cat=cat)
        n[si] = pulp.LpVariable(f"n_{si}", lowBound=0, upBound=max(limit, 0), cat=cat)
        if integer and initial and si in initial:
            f0 = min(max(int(initial[si]), lb), max(ub, 0))
            f[si].setInitialValue(f0)
            n[si].setInitialValue(m.vessels(f0))

    q: Dict[Tuple[int, int], pulp.LpVariable] = {}
    for di, kept in sub_paths.items():
        for k, _ in kept:
            q[(di, k)] = pulp.LpVariable(f"q_{di}_{k}", lowBound=0)
    u = {di: pulp.LpVariable(f"u_{di}", lowBound=0)
         for di, d in enumerate(demands) if d.weekly_teu > 0}

    path_of = {(di, k): p for di, kept in sub_paths.items() for k, p in kept}
    revenue = pulp.lpSum(demands[di].revenue_per_teu * v for (di, k), v in q.items())
    per_teu_port = pulp.lpSum(path_of[(di, k)].port_cost_per_teu * v for (di, k), v in q.items())
    vessel_cost = pulp.lpSum(models[si].vessel_week_cost * n[si] for si in active)
    fuel_cost = pulp.lpSum(models[si].fuel_cost_per_rotation * f[si] for si in active)
    port_fixed = pulp.lpSum(models[si].port_fixed_per_rotation * f[si] for si in active)
    pen = penalty * pulp.lpSum(u.values())
    prob += revenue - per_teu_port - vessel_cost - fuel_cost - port_fixed - pen

    for di, d in enumerate(demands):
        if d.weekly_teu > 0:
            prob += (
                pulp.lpSum(q[(di, k)] for k, _ in sub_paths.get(di, ())) + u[di]
                == d.weekly_teu
            ), f"dem_{di}"
    leg_load: Dict[Tuple[int, int], List[pulp.LpVariable]] = defaultdict(list)
    for (di, k), v in q.items():
        for seg in path_of[(di, k)].segments:
            for leg in seg.legs:
                leg_load[(seg.service, leg)].append(v)
    for (si, leg), vs in leg_load.items():
        prob += pulp.lpSum(vs) <= models[si].capacity_teu * f[si], f"cap_{si}_{leg}"
    vub_rows = 0
    if vub and fixed is None:
        # q[od, p] <= weekly_teu[od] * f[s]  for every service s of path p (valid: see module docstring)
        for (di, k), v in q.items():
            d_teu = float(demands[di].weekly_teu)
            for si in set(path_of[(di, k)].services):
                prob += v <= d_teu * f[si], f"vub_{di}_{k}_{si}"
                vub_rows += 1
    for si in active:
        prob += 7 * n[si] >= models[si].cycle_time_days * f[si], f"veh_{si}"
    by_class: Dict[str, List[int]] = defaultdict(list)
    for si in active:
        by_class[models[si].vessel_class].append(si)
    for cls, sis in by_class.items():
        limit = int(limits.get(cls, models[sis[0]].class_inventory))
        prob += pulp.lpSum(n[si] for si in sis) <= limit, f"fleet_{cls}"
    if total_vessel_limit is not None and active:
        prob += pulp.lpSum(n[si] for si in active) <= int(total_vessel_limit), "fleet_total"
    if port_capacity:
        events: Dict[str, List[Tuple[pulp.LpVariable, float]]] = defaultdict(list)
        for (di, k), v in q.items():
            pth = path_of[(di, k)]
            events[pth.segments[0].from_port].append((v, 1.0))
            events[pth.segments[-1].to_port].append((v, 1.0))
            for hub in pth.transfer_ports:
                events[hub].append((v, 2.0))
        for port, terms in events.items():
            if port in port_capacity:
                prob += (pulp.lpSum(c * v for v, c in terms) <= float(port_capacity[port]),
                         f"port_{port}")
    if min_served_fraction and q:
        total = sum(d.weekly_teu for d in demands if d.weekly_teu > 0)
        prob += pulp.lpSum(q.values()) >= float(min_served_fraction) * total, "min_coverage"

    out = dict(prob=prob, f=f, n=n, q=q, u=u, active=active, terms=dict(
        revenue=revenue, per_teu_port=per_teu_port, vessel_cost=vessel_cost,
        fuel_cost=fuel_cost, port_fixed=port_fixed, pen=pen), status=None, error=None,
        vub_rows=vub_rows)
    if not q or not solve:
        return out
    try:
        prob.solve(_solver(time_limit_sec, threads, bool(integer and initial)))
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _conservation_violations(demands, q, u) -> int:
    """Number of ODs whose returned flows plus unserved quantity do not add up to the demand
    (``sum_p q_p + u_d == weekly_teu_d`` holds in every integer-feasible solution)."""
    served: Dict[int, float] = defaultdict(float)
    for (di, _k), v in q.items():
        served[di] += float(v.varValue or 0.0)
    bad = 0
    for di, uv in u.items():
        d = float(demands[di].weekly_teu)
        if abs(served.get(di, 0.0) + float(uv.varValue or 0.0) - d) > 1e-6 * max(1.0, d) + 1e-3:
            bad += 1
    return bad


def solve_network(
    models: Sequence[ServiceModel],
    demands: Sequence,
    paths_by_od: Dict[int, List[OdPath]],
    class_vessel_limit: Dict[str, int],
    *,
    unserved_penalty_per_teu: float = 0.0,
    fixed_frequencies: Optional[Dict[int, int]] = None,
    initial_frequencies: Optional[Dict[int, int]] = None,
    max_departures_cap: Optional[int] = None,
    time_limit_sec: float = 120.0,
    lp_guided: Optional[bool] = None,
    lp_keep_threshold: float = 1e-6,
    threads: Optional[int] = None,
    total_vessel_limit: Optional[int] = None,
    port_capacity: Optional[Dict[str, float]] = None,
    min_served_fraction: Optional[float] = None,
    path_rebuild=None,
) -> NetworkSolution:
    """Solve the network design problem. Never raises for solver outcomes: the
    status field says what happened and ``usable`` says whether values may be used."""
    t0 = time.perf_counter()
    if unserved_penalty_per_teu < 0 or not math.isfinite(unserved_penalty_per_teu):
        raise ValueError("unserved_penalty_per_teu must be a finite number >= 0")

    referenced = sorted({s for plist in paths_by_od.values() for p in plist for s in p.services})
    sol = NetworkSolution(status="not_solved", n_services_considered=len(referenced),
                          n_paths=sum(len(v) for v in paths_by_od.values()))
    if not referenced:        # nothing can be carried: every OD stays unserved (explicit, valid)
        sol.status, sol.solver_status = "optimal", "no_paths"
        sol.unserved = {di: float(d.weekly_teu) for di, d in enumerate(demands) if d.weekly_teu > 0}
        pen_total = unserved_penalty_per_teu * sum(sol.unserved.values())
        sol.objective_value = -pen_total
        sol.objective_components = {
            "revenue": 0.0, "per_teu_port_cost": 0.0, "vessel_cost": 0.0,
            "fuel_cost": 0.0, "port_fixed_cost": 0.0, "unserved_penalty": pen_total,
        }
        sol.relaxation_bound = -pen_total
        sol.runtime_sec = time.perf_counter() - t0
        return sol

    backend = _backend_name()
    if backend not in ("cbc", "highs"):
        sol.status, sol.solver_status = "solver_error", "invalid_backend"
        sol.message = (f"NETWORK_MILP_BACKEND={backend!r} is not supported (use 'cbc' or "
                       f"'highs'); no other solver was substituted")
        sol.runtime_sec = time.perf_counter() - t0
        return sol
    use_highs = backend == "highs" and fixed_frequencies is None
    sol.solver_backend = "highs" if use_highs else "cbc"
    if use_highs:
        lp_guided = False             # HiGHS takes the unrestricted integer problem
    if lp_guided is None:
        lp_guided = fixed_frequencies is None
    services = referenced
    dropped = False
    paths_int = paths_by_od
    budget = max(1.0, time_limit_sec)
    vub = vub_enabled() and fixed_frequencies is None
    sol.formulation = {"vub_requested": vub_enabled(), "vub_applied": vub, "vub_rows_integer_problem": 0,
                       "vub_rows_lp_relaxation": 0}

    # ---- phase 1: LP relaxation (bound + service restriction) -----------------------
    if lp_guided and fixed_frequencies is None:
        lp = _build_and_solve(models, demands, paths_by_od, class_vessel_limit, referenced,
                              integer=False, penalty=unserved_penalty_per_teu, fixed=None,
                              initial=None, max_departures_cap=max_departures_cap,
                              time_limit_sec=min(60.0, budget * 0.4), threads=threads,
                              total_vessel_limit=total_vessel_limit,
                              port_capacity=port_capacity,
                              min_served_fraction=min_served_fraction, vub=vub)
        sol.formulation["vub_rows_lp_relaxation"] = int(lp.get("vub_rows", 0))
        if lp["error"] or lp["prob"].status != pulp.LpStatusOptimal:
            lp_guided = False        # fall back to the unrestricted integer solve
        else:
            sol.relaxation_bound = float(pulp.value(lp["prob"].objective) or 0.0)
            used = [si for si in lp["active"] if (lp["f"][si].varValue or 0.0) > lp_keep_threshold]
            dropped = len(used) < len(lp["active"])
            services = used
            sol.n_services_restricted_to = len(used)
            if path_rebuild is not None and used:
                # restriction-aware path set (opt-in): the integer problem can only use paths whose
                # services are all in ``used``, so the per-OD path budget is re-spent on those
                try:
                    paths_int = path_rebuild(used)
                    sol.paths_by_od = paths_int
                    sol.formulation["path_include_paths_integer_problem"] = sum(
                        len(v) for v in paths_int.values())
                except Exception as exc:                                  # noqa: BLE001
                    paths_int = paths_by_od
                    sol.paths_by_od = None
                    sol.formulation["path_include_error"] = f"{type(exc).__name__}: {exc}"
            if not used:
                # the relaxation operates nothing: the empty network is the answer
                sol.status, sol.solver_status = "optimal", "lp_operates_nothing"
                sol.unserved = {di: float(d.weekly_teu) for di, d in enumerate(demands) if d.weekly_teu > 0}
                pen_total = unserved_penalty_per_teu * sum(sol.unserved.values())
                sol.objective_value = -pen_total
                sol.objective_components = {
                    "revenue": 0.0, "per_teu_port_cost": 0.0, "vessel_cost": 0.0,
                    "fuel_cost": 0.0, "port_fixed_cost": 0.0, "unserved_penalty": pen_total,
                }
                sol.runtime_sec = time.perf_counter() - t0
                return sol
            budget = max(1.0, time_limit_sec - (time.perf_counter() - t0))
            if lp_round_start_enabled() and initial_frequencies is None and not use_highs:
                try:
                    initial_frequencies, rep_ = lp_rounded_start(
                        models, {si: float(lp["f"][si].varValue or 0.0) for si in used}, class_vessel_limit)
                    sol.formulation["lp_round_start"] = rep_
                except Exception as exc:                                   # noqa: BLE001
                    sol.formulation["lp_round_start_error"] = f"{type(exc).__name__}: {exc}"
    if not sol.n_services_restricted_to:
        sol.n_services_restricted_to = len(services)

    # ---- phase 2: integer problem on the (restricted) service set --------------------
    t_int0 = time.perf_counter()
    res = _build_and_solve(models, demands, paths_int, class_vessel_limit, services,
                           integer=True, penalty=unserved_penalty_per_teu,
                           fixed=fixed_frequencies, initial=initial_frequencies,
                           max_departures_cap=max_departures_cap, time_limit_sec=budget,
                           threads=threads, total_vessel_limit=total_vessel_limit,
                           port_capacity=port_capacity,
                           min_served_fraction=min_served_fraction,
                           solve=not use_highs, vub=vub)
    sol.formulation["vub_rows_integer_problem"] = int(res.get("vub_rows", 0))
    highs_msg = ""
    if use_highs:
        info = _solve_highs(res, t0 + max(1.0, time_limit_sec))
        sol.mip_gap = info["mip_gap"]
        if info["dual_bound"] is not None:
            sol.relaxation_bound = info["dual_bound"]
        if info["error"] and not res["error"]:
            res["error"] = info["error"]
        highs_msg = info["message"]
    prob = res["prob"]
    sol.n_variables = len(res["f"]) + len(res["n"]) + len(res["q"]) + len(res["u"])
    sol.n_constraints = len(prob.constraints)
    sol.runtime_sec = time.perf_counter() - t0
    sol.integer_phase_sec = time.perf_counter() - t_int0
    sol.integer_phase_budget_sec = float(budget)

    if res["error"]:
        sol.status, sol.message = "solver_error", res["error"]
        logger.error("network_milp_solver_error | %s", res["error"])
        return sol
    sol.solver_status = pulp.LpStatus.get(prob.status, str(prob.status))
    if prob.status == pulp.LpStatusInfeasible:
        sol.status = "infeasible"
        return sol
    if prob.status != pulp.LpStatusOptimal:
        sol.status = "not_solved"
        sol.message = f"solver status {sol.solver_status}" + (
            f" ({highs_msg})" if highs_msg else "")
        return sol
    f, n, q, u = res["f"], res["n"], res["q"], res["u"]
    if any(v.varValue is None for v in list(f.values()) + list(q.values())):
        sol.status = "not_solved"
        sol.message = "solver reported optimal but returned no variable values"
        return sol

    # A time-limited CBC run can stop before it has any integer solution and still hand back
    # all-zero variable values with status "Optimal".  Those values are not a plan (the
    # demand rows are equalities, so a real solution always conserves every OD): report
    # "not_solved" instead of an empty plan that only the ledger would reject.
    if getattr(prob, "sol_status", None) == pulp.LpSolutionNoSolutionFound:
        sol.status = "not_solved"
        sol.message = "solver stopped without an integer solution (no incumbent)"
        return sol
    broken = _conservation_violations(demands, q, u)
    if broken:
        sol.status = "not_solved"
        sol.message = (f"solver returned values that do not conserve demand on {broken} OD(s) "
                       f"(no incumbent); reported as not solved")
        return sol

    closed = getattr(prob, "sol_status", 1) == pulp.LpSolutionOptimal
    sol.status = "optimal" if (closed and not dropped) else "feasible"
    sol.closed_by_solver = bool(closed)
    sol.restricted_to_lp_support = bool(dropped)
    sol.time_limit_reached = bool((not closed) and sol.integer_phase_sec >= 0.97 * float(budget))
    sol.objective_value = float(pulp.value(prob.objective) or 0.0)
    sol.frequencies = {si: int(round(f[si].varValue or 0)) for si in res["active"]}
    sol.vessels = {si: int(round(n[si].varValue or 0)) for si in res["active"]}
    for (di, k), v in q.items():
        val = float(v.varValue or 0.0)
        if val > FLOW_NOISE_TEU:
            sol.flows.append((di, k, val))
    sol.unserved = {di: float(u[di].varValue or 0.0) for di in u}
    t = res["terms"]
    sol.objective_components = {
        "revenue": float(pulp.value(t["revenue"]) or 0.0),
        "per_teu_port_cost": float(pulp.value(t["per_teu_port"]) or 0.0),
        "vessel_cost": float(pulp.value(t["vessel_cost"]) or 0.0),
        "fuel_cost": float(pulp.value(t["fuel_cost"]) or 0.0),
        "port_fixed_cost": float(pulp.value(t["port_fixed"]) or 0.0),
        "unserved_penalty": float(pulp.value(t["pen"]) or 0.0),
    }
    _trim_slack_vessels(models, sol, res["active"])
    return sol
