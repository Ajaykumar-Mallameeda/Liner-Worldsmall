"""Plan a network: candidates -> service models -> OD paths -> MILP -> independent ledger.

``NetworkPlanner.plan`` is the single entry point used by the regional stage, the
global reconciliation stage and ``HubMILP``. The returned ``PlanResult`` carries the
MILP solution AND the independent ledger recomputed from the plan alone, plus a
``reconciliation`` section comparing the two (they must agree when the optimiser
penalty is zero).
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.network.bunker_prices import BunkerPriceError
from src.network.economics import (
    DEFAULT_ASSUMPTIONS, EconomicsAssumptions, ServiceModel, ServiceModelError,
    build_service_model,
)
from src.network.flow_reopt import reoptimize_flows, repair_profit_floor
from src.network.ledger import Ledger, LedgerFlow, LedgerService, compute_ledger
from src.network.local_search import (
    config_from_environment as local_search_config_from_environment, local_search, reserve_for,
    prune_idle_services,
    variants_from_environment as local_search_variants_from_environment,
    variants_floor_from_environment as local_search_variants_floor_from_environment,
)
from src.network.targeted_paths import select_targeted_paths, targeted_from_environment, targeted_resolve_from_environment
from src.network.solve_semantics import classify_solve
from src.network.network_milp import NetworkSolution, solve_network
from src.network.paths import (
    BUDGET_FIXED, DEFAULT_MAX_PATHS_PER_OD, SELECT_FASTEST, OdPath, PathConfig, PathStats, build_paths,
    config_from_environment, path_include_from_environment,
)

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    service_id: str
    ports: Tuple[str, ...]
    vessel_class: str


@dataclass
class PlanResult:
    status: str                                   # mirrors NetworkSolution.status (or "invalid_input")
    message: str = ""
    models: List[ServiceModel] = field(default_factory=list)
    rejected_candidates: List[Dict] = field(default_factory=list)
    demands: List = field(default_factory=list)
    paths: Dict[int, List[OdPath]] = field(default_factory=dict)
    path_stats: Optional[PathStats] = None
    solution: Optional[NetworkSolution] = None
    ledger: Optional[Ledger] = None
    reconciliation: Dict = field(default_factory=dict)
    frequencies: Dict[str, int] = field(default_factory=dict)       # service_id -> f (>0 only)
    infeasibility: List[Dict] = field(default_factory=list)         # structured causes
    fuel_prices: Dict[str, Dict] = field(default_factory=dict)      # service_id -> applied price
    flow_reopt: Dict = field(default_factory=dict)                  # Task 20 flow re-optimisation
    local_search: Dict = field(default_factory=dict)                # C2 exact-LP local search (opt-in)
    stage_timing: Dict = field(default_factory=dict)                # seconds per step of the stage
    #: the capped MILP exactly as the solver returned it (before local search / flow re-optimisation /
    #: repair / vessel trim change the plan): incumbent, bound, termination.  The bound belongs to THIS.
    milp_stage: Dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in ("optimal", "feasible") and self.ledger is not None and self.ledger.valid


class NetworkPlanner:
    def __init__(self, problem, assumptions: EconomicsAssumptions = DEFAULT_ASSUMPTIONS,
                 max_paths_per_od: int = DEFAULT_MAX_PATHS_PER_OD,
                 path_config: Optional[PathConfig] = None):
        if getattr(problem, "fleet", None) is None or not problem.fleet.classes:
            raise ValueError("NetworkPlanner needs problem.fleet (no default fleet is assumed)")
        self.problem = problem
        self.assumptions = assumptions
        self.max_paths_per_od = max_paths_per_od
        # how the path set is selected and how many transfers a journey may have (Task 20);
        # the environment default is the baseline (fastest paths, one transfer)
        self.path_config = path_config if path_config is not None else config_from_environment()
        # A regional problem only lists its own ports, but its services call at ports
        # of other regions: ``port_catalog`` (all ports) is used when present.
        catalog = getattr(problem, "port_catalog", None)
        self.port_lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
        # a port is known if it has distance rows: the full network, not just a region
        self.known_ports = set(problem.distance_matrix)

    # ---- models ----------------------------------------------------------------
    def build_models(self, candidates: Iterable[Candidate]) -> Tuple[List[ServiceModel], List[Dict]]:
        models, rejected, seen = [], [], set()
        for c in candidates:
            if c.service_id in seen:
                rejected.append({"service": c.service_id, "reasons": ["duplicate_service_id"]})
                continue
            seen.add(c.service_id)
            vessel = self.problem.fleet.get_class(c.vessel_class)
            try:
                models.append(build_service_model(
                    c.service_id, c.ports, vessel, self.problem.distance_matrix,
                    self.port_lookup, self.assumptions, known_ports=self.known_ports,
                    capacity_unit_status=getattr(self.problem.fleet, "capacity_unit_status", "provisional"),
                ))
            except ServiceModelError as exc:
                rejected.append({"service": c.service_id, "reasons": exc.reasons, "detail": str(exc)})
        return models, rejected

    # ---- why is it infeasible? -----------------------------------------------------
    @staticmethod
    def _diagnose_infeasibility(models, fixed, limits, total_vessel_limit,
                                min_served_fraction) -> List[Dict]:
        """Causes that can be read off the inputs without re-solving: the vessels the
        fixed frequencies require, per class and in total, against the inventories."""
        causes: List[Dict] = []
        if fixed:
            need: Dict[str, int] = {}
            for si, f in fixed.items():
                if f > 0 and si < len(models):
                    m = models[si]
                    need[m.vessel_class] = need.get(m.vessel_class, 0) + m.vessels(int(f))
            for cls, n in sorted(need.items()):
                avail = int(limits.get(cls, 0))
                if n > avail:
                    causes.append({"type": "fleet_exceeded", "vessel_class": cls,
                                   "required": int(n), "available": avail,
                                   "detail": f"fleet_exceeded: class {cls} needs {n} vessels, "
                                             f"inventory is {avail}"})
            if total_vessel_limit is not None and sum(need.values()) > int(total_vessel_limit):
                causes.append({"type": "total_fleet_exceeded", "required": int(sum(need.values())),
                               "available": int(total_vessel_limit),
                               "detail": f"total_fleet_exceeded: {sum(need.values())} vessels "
                                         f"needed, limit is {int(total_vessel_limit)}"})
        if min_served_fraction and not causes:
            causes.append({"type": "min_served_fraction", "required": float(min_served_fraction),
                           "detail": f"a minimum served fraction of {min_served_fraction:.2%} "
                                     f"is required and may be unattainable"})
        return causes

    # ---- plan --------------------------------------------------------------------
    def plan(
        self,
        candidates: Sequence[Candidate],
        *,
        demands: Optional[Sequence] = None,
        class_vessel_limit: Optional[Dict[str, int]] = None,
        fixed_frequencies: Optional[Dict[str, int]] = None,
        initial_frequencies: Optional[Dict[str, int]] = None,
        unserved_penalty_per_teu: float = 0.0,
        time_limit_sec: float = 120.0,
        lp_guided: Optional[bool] = None,
        total_vessel_limit: Optional[int] = None,
        port_capacity: Optional[Dict[str, float]] = None,
        min_served_fraction: Optional[float] = None,
    ) -> PlanResult:
        t0 = time.perf_counter()
        demands = list(self.problem.demands if demands is None else demands)
        res = PlanResult(status="not_solved", demands=demands)
        models, rejected = self.build_models(candidates)
        res.models, res.rejected_candidates = models, rejected

        limits = {c.vessel_class: c.quantity for c in self.problem.fleet.classes}
        if class_vessel_limit:
            for k, v in class_vessel_limit.items():
                limits[k] = min(limits.get(k, v), int(v))

        paths, pstats = build_paths(demands, models, self.port_lookup, self.assumptions,
                                    max_paths_per_od=self.max_paths_per_od,
                                    config=self.path_config)
        res.paths, res.path_stats = paths, pstats

        index = {m.service_id: i for i, m in enumerate(models)}
        fixed = None
        if fixed_frequencies is not None:
            fixed = {index[s]: int(f) for s, f in fixed_frequencies.items() if s in index}
        init = None
        if initial_frequencies:
            init = {index[s]: int(f) for s, f in initial_frequencies.items() if s in index}

        # Opt-in exact-LP local search (C2, ``LINER_LOCAL_SEARCH``): it takes its time from the SAME
        # stage budget - the MILP gets the budget minus the reserve and the search runs until
        # (start of the plan + budget): model / path construction (~1.4 s) and any overrun of the
        # solver's own time limit come out of the reserve, so the complete stage ends within
        # ``time_limit_sec`` (plus the < 0.2 s of re-routing and the ledger).
        ls_cfg = local_search_config_from_environment()
        ls_applicable = bool(ls_cfg.enabled and fixed is None and not unserved_penalty_per_teu
                             and port_capacity is None and not total_vessel_limit)
        milp_budget = time_limit_sec
        if ls_applicable:
            milp_budget = max(1.0, time_limit_sec - reserve_for(ls_cfg, time_limit_sec))
        res.local_search = ({"enabled": True, "applied": False, "reason": "not run"} if ls_applicable
                            else {"enabled": bool(ls_cfg.enabled), "applied": False,
                                  "reason": ("not applicable to this solve" if ls_cfg.enabled
                                             else "disabled")})
        timing: Dict[str, float] = {"model_and_paths_sec": round(time.perf_counter() - t0, 3)}
        include_k = path_include_from_environment() if fixed is None else 0
        path_rebuild = None
        if include_k > 0:
            import dataclasses as _dc
            cfg_inc = _dc.replace(self.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED)

            def path_rebuild(services_used):
                return build_paths(demands, models, self.port_lookup, self.assumptions,
                                   max_paths_per_od=include_k, config=cfg_inc,
                                   only_services=sorted(services_used))[0]
        targeted_cfg = targeted_from_environment() if fixed is None else None
        path_augment = None
        if targeted_cfg is not None:
            import dataclasses as _dc2
            k_ods, m_paths = targeted_cfg
            t_resolve = targeted_resolve_from_environment()

            def path_augment(lp, current_paths):
                # the paths are enumerated (without a cap) only for the highest-value candidate demands: those whose
                # LP-unserved revenue is largest.  A full enumeration of every demand costs ~30 s of the 120 s stage,
                # which leaves CBC too little time to reach its first incumbent (measured, reports/continuation_20261015).
                cand = []
                for di, d in enumerate(demands):
                    if d.weekly_teu > 0 and di in lp["u"]:
                        u = float(lp["u"][di].varValue or 0.0)
                        if u > 1e-6 * float(d.weekly_teu):
                            cand.append((u * float(d.revenue_per_teu), di))
                cand.sort(key=lambda x: (-x[0], x[1]))
                pick = [di for _v, di in cand[:max(100, 4 * k_ods)]]
                cfg_v = _dc2.replace(self.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED)
                sub, _st = build_paths([demands[di] for di in pick], models, self.port_lookup, self.assumptions,
                                       max_paths_per_od=10 ** 9, config=cfg_v)
                valid = {pick[i]: pl for i, pl in sub.items()}
                allowed = None
                if not t_resolve:
                    allowed = {si for si in lp["active"] if (lp["f"][si].varValue or 0.0) > 1e-6}      # the LP support
                extra, rep = select_targeted_paths(lp, demands, current_paths, valid, k_ods, m_paths, allowed_services=allowed)
                rep["enumerated_ods"] = len(pick)
                rep["resolve_lp"] = bool(t_resolve)
                return extra, rep
        t_solve0 = time.perf_counter()
        sol = solve_network(
            models, demands, paths, limits,
            unserved_penalty_per_teu=unserved_penalty_per_teu,
            fixed_frequencies=fixed, initial_frequencies=init,
            time_limit_sec=milp_budget, lp_guided=lp_guided,
            total_vessel_limit=total_vessel_limit, port_capacity=port_capacity,
            min_served_fraction=min_served_fraction, path_rebuild=path_rebuild, path_augment=path_augment,
        )
        if sol.paths_by_od is not None:
            paths = sol.paths_by_od                  # the path set the integer problem actually used
            res.paths = paths
            sol.formulation["path_include_k"] = include_k
        timing["milp_sec"] = round(time.perf_counter() - t_solve0, 3)
        timing["milp_budget_sec"] = round(milp_budget, 1)
        res.solution = sol
        res.milp_stage = {
            "status": sol.status, "solver_status": sol.solver_status,
            "incumbent_profit_usd_per_week": (float(sol.objective_value)
                                              + float(sol.objective_components.get("unserved_penalty", 0.0))
                                              if sol.usable else None),
            "relaxation_bound_usd_per_week": sol.relaxation_bound,
            "mip_gap_reported_by_backend": sol.mip_gap, "backend": sol.solver_backend,
            "services_in_integer_problem": sol.n_services_restricted_to,
        }
        # ``solver_status`` above is the RAW backend status ("Optimal" = the solver returned normally);
        # the application-level claim the evidence supports is ``conclusion`` (see solve_semantics).
        res.milp_stage["solver_status_semantics"] = (
            "raw backend status; 'Optimal' does not by itself prove optimality (see conclusion)")
        res.milp_stage.update(classify_solve(
            usable=sol.usable, closed=bool(sol.closed_by_solver), restricted=sol.restricted_to_lp_support,
            time_limit_reached=sol.time_limit_reached,
            incumbent=res.milp_stage["incumbent_profit_usd_per_week"], bound=sol.relaxation_bound))
        res.status = sol.status
        res.message = sol.message
        res.flow_reopt = {"applied": False, "reason": "disabled"}
        if ((self.path_config.reoptimize_flows or self.path_config.repair_profit_floor or ls_applicable)
                and sol.usable and fixed is None
                and not unserved_penalty_per_teu and port_capacity is None
                and not total_vessel_limit):
            import dataclasses
            cfg_all = dataclasses.replace(
                self.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED,
                multi_hop_min_alternatives=(10 ** 9 if self.path_config.max_transfers >= 2
                                            else self.path_config.multi_hop_min_alternatives))

            operated = [si for si, fr in sol.frequencies.items() if fr > 0]

            _cache: Dict = {}

            def _all_paths():
                if "v" not in _cache:
                    _cache["v"] = build_paths(demands, models, self.port_lookup, self.assumptions,
                                              max_paths_per_od=10 ** 9, config=cfg_all,
                                              only_services=operated)
                return _cache["v"]

            floor_teu = (float(min_served_fraction)
                         * sum(d.weekly_teu for d in demands if d.weekly_teu > 0)
                         if min_served_fraction else 0.0)
            res.flow_reopt = {"applied": False, "reason": "disabled"}
            if ls_applicable:
                cfg_ls = dataclasses.replace(
                    self.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED,
                    multi_hop_min_alternatives=(10 ** 9 if (ls_cfg.multi_hop and self.path_config.max_transfers >= 2)
                                                else self.path_config.multi_hop_min_alternatives))

                def _ls_paths():
                    return build_paths(demands, models, self.port_lookup, self.assumptions,
                                       max_paths_per_od=10 ** 9, config=cfg_ls)

                t_ls = time.perf_counter()
                ls_variant_report = None
                ls_vf = local_search_variants_from_environment()
                if ls_vf > 0:
                    # alternative-class services of over-subscribed classes, visible ONLY to the search
                    # (not to the MILP, which has already been solved): same canonical model, ids "lv####"
                    from src.network.class_variants import augment_candidates
                    extra_c, ls_variant_report = augment_candidates(
                        self.problem, self.assumptions, candidates, fraction=ls_vf, id_prefix="lv",
                        standalone_floor=local_search_variants_floor_from_environment(),
                        deadline=time.perf_counter() + 5.0)
                    new_models, new_rejected = self.build_models(extra_c)
                    models.extend(new_models)
                    res.rejected_candidates.extend(new_rejected)
                    ls_variant_report["modelled"] = len(new_models)
                    index = {m.service_id: i for i, m in enumerate(models)}   # the ledger looks services up by id
                res.local_search = local_search(models, demands, paths, sol, limits, _ls_paths,
                                                config=ls_cfg, deadline=t0 + float(time_limit_sec),
                                                min_served_teu=floor_teu)
                res.local_search["enabled"] = True
                if ls_variant_report is not None:
                    res.local_search["variants"] = {k: v for k, v in ls_variant_report.items() if k != "additions"}
                    res.local_search["variant_additions"] = ls_variant_report.get("additions", [])
                timing["local_search_sec"] = round(time.perf_counter() - t_ls, 3)
            t_ro = time.perf_counter()
            if self.path_config.reoptimize_flows:
                res.flow_reopt = reoptimize_flows(models, demands, paths, sol, _all_paths,
                                                  min_served_teu=floor_teu)
            timing["flow_reopt_sec"] = round(time.perf_counter() - t_ro, 3)
            t_rp = time.perf_counter()
            if self.path_config.repair_profit_floor and not min_served_fraction:
                res.flow_reopt["repair"] = repair_profit_floor(models, demands, paths, sol, _all_paths)
            timing["repair_sec"] = round(time.perf_counter() - t_rp, 3)
            idle_pruned = None
            if ls_applicable and res.local_search.get("applied"):
                # a service the search opened can end up empty once the cargo is re-routed: drop it
                idle_pruned = prune_idle_services(models, paths, sol)
                res.local_search["idle_pruned"] = idle_pruned
            changed = bool(res.flow_reopt.get("applied")
                           or (res.flow_reopt.get("repair") or {}).get("applied")
                           or res.local_search.get("applied")
                           or (idle_pruned or {}).get("applied"))
            if changed and sol.status == "optimal":
                # the capped model's proven optimum has been improved on with paths outside it:
                # the plan is feasible, and no optimality over the full path set is proven
                sol.status = res.status = "feasible"
                sol.message = (sol.message + "; " if sol.message else "") + \
                    "plan improved outside the solved model (flow re-optimisation / local search / " \
                    "repair): optimality of the capped model no longer claimed"
                res.message = sol.message
        if sol.status == "infeasible":
            res.infeasibility = self._diagnose_infeasibility(
                models, fixed, limits, total_vessel_limit, min_served_fraction)
            if res.infeasibility:
                res.message = "; ".join(v["detail"] for v in res.infeasibility)
            elif not res.message:
                res.message = "network model is infeasible under the stated constraints"
        if not sol.usable:
            return res

        # ---- independent ledger from the plan alone -----------------------------
        t_ledger = time.perf_counter()
        led_services = [
            LedgerService(models[si].service_id, models[si].ports, models[si].vessel_class, int(f))
            for si, f in sol.frequencies.items() if f > 0
        ]
        flows = []
        for di, k, teu in sol.flows:
            segs = tuple((models[s.service].service_id, s.from_port, s.to_port)
                         for s in paths[di][k].segments)
            flows.append(LedgerFlow(di, segs, teu))
        a = self.assumptions
        # The ledger gets the price of every operated service from the pricing in
        # force, resolved here from the service's own rotation - NOT copied from the
        # service model - and the two are compared below.
        fuel_prices: Dict[str, Dict] = {}
        for ls in led_services:
            try:
                r = a.resolve_fuel_price(ls.ports)
            except BunkerPriceError:
                continue                     # the ledger flags the service (missing_fuel_price)
            fuel_prices[ls.service_id] = {"price": r.price_usd_per_t, "basis": r.basis,
                                          "bunkering_port": r.bunkering_port,
                                          "observed_on": r.observed_on}
        res.ledger = compute_ledger(
            led_services, flows, demands, self.problem.fleet,
            self.problem.distance_matrix, self.port_lookup,
            port_stay_hours=a.port_stay_hours,
            transshipment_min_hours=a.transshipment_min_hours,
            transfer_wait_days=a.transfer_wait_days,
            bunker_price_usd_per_t=a.effective_fuel_pricing.reference_price_usd_per_t
            if a.effective_fuel_pricing.reference_price_usd_per_t is not None else float("nan"),
            unserved_reported=sol.unserved,
            speed_factor=a.speed_factor,
            fuel_prices=fuel_prices,
            max_transfers=self.path_config.max_transfers,
        )
        for ls in led_services:
            m = models[index[ls.service_id]]
            lp = fuel_prices.get(ls.service_id, {}).get("price")
            if lp is not None and abs(lp - m.fuel_price_usd_per_t) > 1e-9 * max(1.0, abs(lp)):
                res.ledger.violations.append({
                    "type": "fuel_price_mismatch", "service": ls.service_id,
                    "model_price": m.fuel_price_usd_per_t, "ledger_price": lp})
        res.fuel_prices = fuel_prices
        res.frequencies = {models[si].service_id: f for si, f in sol.frequencies.items() if f > 0}
        if not res.ledger.valid:
            # the optimiser produced a plan that the independent recomputation rejects:
            # that is a defect to surface, never a number to report
            res.infeasibility = [dict(v) for v in res.ledger.violations]
            kinds = sorted({str(v.get("type", "violation")) for v in res.ledger.violations})
            res.message = (f"independent ledger rejected the plan "
                           f"({len(res.ledger.violations)} violation(s): {', '.join(kinds)})")

        # MILP objective (no penalty) must equal ledger profit to numerical tolerance.
        milp_profit = sol.objective_value + sol.objective_components.get("unserved_penalty", 0.0)
        led_profit = res.ledger.operating_profit
        # vessels: the MILP may carry more vessels than the minimum when unprofitable? no -
        # minimisation of cost drives n to ceil(T f/7); a difference is flagged, not hidden.
        scale = max(1.0, abs(led_profit), abs(milp_profit))
        timing["ledger_sec"] = round(time.perf_counter() - t_ledger, 3)
        timing["plan_total_sec"] = round(time.perf_counter() - t0, 3)
        res.stage_timing = timing
        res.reconciliation = {
            "milp_profit_before_penalty": milp_profit,
            "ledger_operating_profit": led_profit,
            "difference": milp_profit - led_profit,
            "relative_difference": (milp_profit - led_profit) / scale,
            "reconciled": abs(milp_profit - led_profit) <= 1e-6 * scale + 1e-3,
            "relaxation_upper_bound": sol.relaxation_bound,
            "services_in_relaxation": sol.n_services_considered,
            "services_in_integer_problem": sol.n_services_restricted_to,
            "unserved_penalty_per_teu": unserved_penalty_per_teu,
            "vessel_slack_removed": sol.vessel_slack_removed,
            "vessel_slack_cost_usd": sol.vessel_slack_cost_usd,
            "flow_reoptimisation": dict(res.flow_reopt),
            "local_search": dict(res.local_search),
            "stage_timing": dict(res.stage_timing),
            "formulation": dict(getattr(sol, "formulation", {}) or {}),
            "runtime_sec": round(time.perf_counter() - t0, 3),
        }
        return res
