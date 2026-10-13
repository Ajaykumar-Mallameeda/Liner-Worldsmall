"""HubMILP - cargo allocation for a chromosome, on the canonical network model.

The class keeps its public name, constructor and result keys, but the
formulation is no longer a private copy: it delegates to ``src.network`` so that
the GA stages, the regional MILP and the global reconciliation all price a
service identically and the same independent ledger validates every result.
(The previous implementation is preserved verbatim in ``hub_milp_legacy.py``.)

Semantics (fixed by the chromosome, as before)
    services[i] == 1 and frequencies[i] == f > 0   service operates f departures/week
    services[i] == 1 and frequencies[i] == 0       NOT operated (never rounded up to 1)
    capacity       capacity * f on EVERY leg of the closed rotation
    vessels        ceil(cycle_time * f / 7), per class, against the real inventory
    profit         revenue - vessel - fuel - port-call - handling - transshipment
                   (independent ledger); the optimiser's own penalty is reported
                   separately as ``objective_value`` / ``unserved_penalty``
A frequency the fleet cannot sustain returns an explicit ``Infeasible`` status.

Legacy parameters that no longer have an effect (kept so callers do not break):
``max_transfer_pairs`` (paths are enumerated exhaustively up to
``max_services_per_demand`` per OD), ``transship_cost_per_teu`` and
``port_cost_per_teu`` (per-port costs come from the data; a flat default is never
substituted), ``port_capacity`` and ``w_profit`` / ``w_coverage`` (no coverage
reward exists any more).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from src.config.optimizer_config import CONFIG
from src.network.economics import (
    DEFAULT_ASSUMPTIONS, EconomicsAssumptions, assumptions_for_problem,
)
from src.network.plan import Candidate, NetworkPlanner

logger = logging.getLogger(__name__)

DEFAULT_TRANSSHIP_COST = 80.0
DEFAULT_PORT_COST      = 15.0
DEFAULT_PORT_CAPACITY  = 1e9
DEFAULT_MIN_COVERAGE   = 0.0

_STATUS = {
    "optimal":      "Optimal",
    "feasible":     "Feasible",          # time-limited incumbent: valid, not proven optimal
    "infeasible":   "Infeasible",
    "not_solved":   "Not Solved",
    "solver_error": "Solver Error",
    "invalid_input": "Invalid Input",
}


class HubMILP:
    def __init__(
        self,
        problem,
        chromosome,
        max_services_per_demand: int  = 10,
        max_transfer_pairs: int       = 2000,
        transship_cost_per_teu: float = DEFAULT_TRANSSHIP_COST,
        port_cost_per_teu: float      = DEFAULT_PORT_COST,
        port_capacity: float          = DEFAULT_PORT_CAPACITY,
        min_coverage: float           = DEFAULT_MIN_COVERAGE,
        w_profit: float               = 0.5,
        w_coverage: float             = 0.4,
        alpha_unserved: float         = 300.0,
        time_limit: int               = 120,
        fleet_size: Optional[int]     = None,
        *,
        port_capacity_override: Optional[Dict] = None,
        assumptions: EconomicsAssumptions = DEFAULT_ASSUMPTIONS,
    ):
        self.problem    = problem
        self.chromosome = chromosome
        self.max_paths_per_od = max(1, int(max_services_per_demand))
        self.alpha      = float(alpha_unserved)
        self.time_limit = time_limit
        self.fleet_size = fleet_size          # None -> the real fleet inventory
        self.min_coverage = float(min_coverage or 0.0)
        self.assumptions = assumptions
        self.port_capacity_override: Dict = (
            dict(port_capacity_override) if isinstance(port_capacity_override, dict) else {}
        )
        self.last_plan = None                 # the PlanResult of the last solve()

        # IP-3 port-capacity map (unchanged contract): 50000 + 0.1 * demand per port,
        # scaled once by a congestion override clamped to [0, 1]. It is only ENFORCED
        # when an override exists, so no invented capacity binds by default.
        self.port_lookup: Dict = {p.id: p for p in problem.ports}
        demand_score = defaultdict(float)
        for d in problem.demands:
            demand_score[d.origin] += d.weekly_teu
            demand_score[d.destination] += d.weekly_teu
        self.port_capacity_map = {
            p.id: 50000 + 0.1 * demand_score[p.id] for p in problem.ports
        }
        for port_id, factor in self.port_capacity_override.items():
            key = str(port_id)
            if key not in self.port_capacity_map:
                continue
            try:
                fv = float(factor)
            except (TypeError, ValueError):
                continue
            if fv != fv or fv in (float("inf"), float("-inf")):
                continue
            self.port_capacity_map[key] *= min(1.0, max(0.0, fv))

    def _port_cap(self, port_id) -> float:
        # override keys may be str or int; the map is keyed by Port.id (str)
        return self.port_capacity_map.get(str(port_id), 50000)

    # ------------------------------------------------------------------ #
    def _invalid(self, message: str, reasons=()) -> Dict:
        total = float(sum(d.weekly_teu for d in self.problem.demands))
        return self._empty("invalid_input", total, message, list(reasons))

    def _empty(self, status: str, total: float, message: str = "", reasons=()) -> Dict:
        return {
            "status": _STATUS.get(status, status), "valid": False, "message": message,
            "reasons": list(reasons),
            "profit": 0.0, "objective_value": 0.0, "revenue": 0.0,
            "cost": 0.0, "fuel_cost": 0.0, "transship_cost": 0.0, "port_cost": 0.0,
            "total_cost": 0.0, "coverage": 0.0, "satisfied_demand": 0.0,
            "direct_demand": 0.0, "transship_demand": 0.0,
            "total_demand": total, "unserved_demand": total,
            "num_direct_vars": 0, "num_transfer_vars": 0, "num_services_used": 0,
            "selected_services": [], "frequencies": {}, "violations": [],
        }

    # ------------------------------------------------------------------ #
    def solve(self) -> Dict:
        problem = self.problem
        services = problem.services
        mask = self.chromosome.get("services", [])
        freqs = self.chromosome.get("frequencies", [])
        total_demand = float(sum(d.weekly_teu for d in problem.demands))

        if getattr(problem, "fleet", None) is None or not problem.fleet.classes:
            return self._invalid("problem.fleet is required: no default fleet is assumed",
                                 ["missing_fleet"])

        candidates: List[Candidate] = []
        fixed: Dict[str, int] = {}
        for i, svc in enumerate(services):
            if i >= len(mask) or not mask[i]:
                continue
            if i >= len(freqs):
                return self._invalid(f"service {svc.id}: selected without a frequency",
                                     ["missing_frequency"])
            f = freqs[i]
            if not isinstance(f, (int, float)) or f != f or f < 0 or f != int(f):
                return self._invalid(f"service {svc.id}: frequency {f!r} is not a whole number >= 0",
                                     ["invalid_frequency"])
            f = int(f)
            if f == 0:
                continue                      # selected but not scheduled: not operated
            if not svc.vessel_class:
                return self._invalid(f"service {svc.id}: no vessel class (no default is assumed)",
                                     ["unknown_vessel_class"])
            candidates.append(Candidate(str(svc.id), tuple(svc.ports), svc.vessel_class))
            fixed[str(svc.id)] = f

        assumptions = assumptions_for_problem(problem, self.assumptions)   # IP-2 weather factor

        try:
            planner = NetworkPlanner(problem, assumptions=assumptions,
                                     max_paths_per_od=self.max_paths_per_od)
        except ValueError as exc:
            return self._invalid(str(exc), ["missing_fleet"])

        total_limit = self.fleet_size
        port_cap = dict(self.port_capacity_map) if self.port_capacity_override else None
        plan = planner.plan(
            candidates, fixed_frequencies=fixed, unserved_penalty_per_teu=self.alpha,
            time_limit_sec=float(self.time_limit), lp_guided=False,
            total_vessel_limit=total_limit, port_capacity=port_cap,
            min_served_fraction=self.min_coverage or None,
        )
        self.last_plan = plan

        if plan.rejected_candidates:
            # a selected, scheduled service that cannot be modelled is an input error,
            # never "zero cost": say which and why
            bad = plan.rejected_candidates[0]
            return self._invalid(
                f"{len(plan.rejected_candidates)} selected service(s) cannot be modelled; "
                f"first: {bad.get('detail') or bad.get('service')}",
                sorted({r for b in plan.rejected_candidates for r in b.get("reasons", [])}),
            )
        if not plan.ok:
            out = self._empty(plan.status, total_demand,
                              plan.message or (plan.solution.message if plan.solution else ""),
                              [v["type"] for v in plan.infeasibility])
            out["violations"] = list(plan.infeasibility)
            return out

        led, sol = plan.ledger, plan.solution
        n_direct = sum(1 for di, k, _ in sol.flows if plan.paths[di][k].kind == "direct")
        direct_teu = sum(t for di, k, t in sol.flows if plan.paths[di][k].kind == "direct")
        transfer_teu = sum(t for di, k, t in sol.flows if plan.paths[di][k].kind != "direct")
        by_id = {str(s.id): s for s in services}

        rows = []
        for sid, r in led.service_rows.items():
            if r["load"] <= 0:
                continue
            cost = r["vessel_cost"] + r["fuel_cost"] + r["port_cost"]
            rows.append({
                "id": sid,
                "ports": list(by_id[sid].ports) if sid in by_id else r["ports"],
                "load": float(r["load"]),
                "capacity": float(r["capacity_per_departure"]),
                "vessel_class": r["vessel_class"],
                "vessel_cost": float(r["vessel_cost"]),
                "fuel_cost": float(r["fuel_cost"]),
                "port_cost": float(r["port_cost"]),
                "revenue": float(r["revenue"]),
                "cost": float(cost),
                "weekly_profit": float(r["revenue"] - cost),
                "margin_pct": round((r["revenue"] - cost) / r["revenue"] * 100, 2) if r["revenue"] > 0 else 0.0,
                # real-world time and scheduling of the selected service
                "frequency_per_week": int(r["frequency"]),
                "vessels": int(r["vessels"]),
                "cycle_time_days": int(r["cycle_time_days"]),
            })

        port_cost_total = led.port_call_fixed_cost + led.handling_cost + led.port_variable_cost
        out = {
            "status": _STATUS[plan.status],
            "valid": led.valid,
            "message": plan.message,
            "reasons": [],
            "profit": float(led.operating_profit),                 # accounting profit
            "objective_value": float(sol.objective_value),         # incl. optimiser penalty
            "revenue": float(led.revenue),
            "cost": float(led.vessel_cost),                        # vessel hire (legacy key)
            "fuel_cost": float(led.fuel_cost),
            "transship_cost": float(led.transshipment_cost),
            "port_cost": float(port_cost_total),
            "total_cost": float(led.operating_cost),
            "coverage": float(led.coverage * 100.0),
            "satisfied_demand": float(led.served_teu),
            "direct_demand": float(direct_teu),
            "transship_demand": float(transfer_teu),
            "total_demand": float(led.total_demand_teu),
            "unserved_demand": float(led.unserved_teu),
            "num_direct_vars": n_direct,
            "num_transfer_vars": len(sol.flows) - n_direct,
            "num_services_used": len(rows),
            "selected_services": rows,
            "frequencies": dict(plan.frequencies),
            "violations": list(led.violations),
            "reconciliation": dict(plan.reconciliation),
            "unserved_penalty": float(sol.objective_components.get("unserved_penalty", 0.0)),
            "vessels_by_class": dict(led.vessels_by_class),
        }
        if CONFIG.verbose_runtime_logs:
            print(f"HUB_MILP: status={out['status']} profit={out['profit']:.2f} "
                  f"revenue={out['revenue']:.2f} cost={out['total_cost']:.2f} "
                  f"coverage={out['coverage']:.2f}%")
        return out
