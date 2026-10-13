import re
import time
import logging
from typing import Dict, Any, List
from src.llm.evaluator                  import LLMEvaluator
from src.agents.base                    import BaseAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.optimization.data              import Problem, Service
from src.optimization.hierarchical_ga   import HierarchicalGA
from src.optimization.hub_milp          import HubMILP
from src.services.hub_detector          import HubDetector
from src.utils.fuel_cost                import map_capacity_to_vessel_class
from src.validation.regional_policy_validator import validate_regional_policy, DEFAULT_REGIONAL_POLICY
from src.llm.actuation                  import actuation_ledger
from src.llm.client                     import llm_client
from src.network.metrics                import classify_margin, margin_verdict_label
from src.services.regional_filter       import (
    MODE_ECONOMIC, filter_mode, select_economic,
)
from src.optimization.adaptive_budget   import (
    compute_complexity_signals,
    AdaptiveBudget,
    get_filter_params,
    get_service_ga_params,
    get_frequency_ga_params,
    get_milp_params,
)

logger = logging.getLogger(__name__)

# ── Shared cost constants — identical in GA and MILP ──────────────────
TRANSSHIP_COST_PER_TEU = 80.0
PORT_COST_PER_TEU      = 0.0  # Use dataset port costs only
ALPHA_UNSERVED         = 300.0
MIN_COVERAGE_FLOOR     = 0.0
MAX_TRANSFER_PAIRS     = 2000


# --------------------------------------------------------------------
# IP-3 (Phase 7) port-capacity override
# --------------------------------------------------------------------
# The override map is built locally (no ``maritime.optimizer_bridge``
# import) to honor the network-isolation boundary: no
# ``src/`` module may import ``maritime.*`` (see
# ``tests/architecture/test_network_isolation.py`` and
# ``tests/maritime/test_network_boundary.py``). The function is
# structurally identical to
# ``maritime.optimizer_bridge.congestion_port_capacity`` followed by
# a port-id intersection, but it lives in the optimizer agent so
# the contract is enforced by tests without a runtime import.

DEFAULT_IP3_KAPPA = 0.3
DEFAULT_IP3_MIN_CONFIDENCE = 0.6


def _is_finite_number(v) -> bool:
    if not isinstance(v, (int, float)):
        return False
    return v == v and v not in (float("inf"), float("-inf"))


def _ip3_port_capacity_override(sub) -> Dict:
    """Build the IP-3 port-capacity override map for a cluster.

    Reads ``sub.maritime_features`` (attached upstream by
    ``OrchestratorAgent`` via IP-1). The cluster's port set is
    intersected with the override map so we only ever touch ports
    that exist in this cluster's ``Problem``. Returns an empty
    dict when maritime is disabled, when the attached features
    carry no congestion override, or when the intersection is
    empty. The empty-dict default keeps the existing HubMILP
    synthetic capacity map byte-equivalent to the pre-maritime
    path.
    """
    if sub is None:
        return {}
    mf = getattr(sub, "maritime_features", None)
    if mf is None:
        return {}
    raw_override = getattr(mf, "congestion_override", None)
    if not raw_override:
        return {}
    # Build a name -> port_id index from the cluster's ports.
    name_to_id: Dict[str, str] = {}
    for p in getattr(sub, "ports", []) or []:
        pid = getattr(p, "id", None)
        if pid is None:
            continue
        name_to_id[str(pid)] = str(pid)
        for attr in ("unlocode", "name", "code", "port_id"):
            v = getattr(p, attr, None)
            if isinstance(v, str) and v:
                name_to_id.setdefault(v, str(pid))
    out: Dict[str, float] = {}
    for key, info in raw_override.items():
        if not isinstance(info, dict):
            continue
        conf = info.get("confidence")
        score = info.get("score")
        if not _is_finite_number(conf) or not _is_finite_number(score):
            continue
        if conf < DEFAULT_IP3_MIN_CONFIDENCE:
            continue
        s = max(0.0, min(1.0, float(score)))
        factor = 1.0 - DEFAULT_IP3_KAPPA * s
        if factor < 0.0:
            factor = 0.0
        if factor > 1.0:
            factor = 1.0
        port_key = name_to_id.get(str(key))
        if port_key is None:
            continue
        out[port_key] = factor
    return out


class RegionalAgent(BaseAgent):

    def __init__(self, name: str, region: str, model: str):
        super().__init__(name=name, role=f"Regional Optimizer - {region}", model=model, llm_role="regional")
        self.region    = region
        self.evaluator = LLMEvaluator()

    def get_system_prompt(self) -> str:
        return (
            f"You are a liner shipping network optimisation analyst for the {self.region} region.\n\n"
            "Your output is consumed by the Global Decision Agent for network-wide coordination.\n"
            "1. Every claim must cite a specific number from the data.\n"
            "2. No vague language: 'consider', 'explore', 'may', 'could potentially'.\n"
            "3. Strategy reasons must name specific port IDs or TEU volumes.\n"
            "4. Improvement actions must be specific and measurable."
        )

    def is_valid_explanation(self, text: str) -> bool:
        required = ["Verdict:", "Strength", "Weakness", "Improvement"]
        return all(r in text for r in required) and bool(re.search(r"\d{2,}", text))

    # ------------------------------------------------------------------ #
    #  Hub-based cluster decomposition                                      #
    # ------------------------------------------------------------------ #
    def split_by_hubs(self, problem: Problem, num_hubs: int = 5) -> Dict:
        hub_detector = HubDetector(problem)
        hubs         = hub_detector.detect_hubs(top_k=num_hubs)
        clusters     = {h: [] for h in hubs}
        for p in problem.ports:
            closest_hub = min(
                hubs,
                key=lambda h: problem.distance_matrix.get(h, {}).get(p.id, 1e9),
            )
            clusters[closest_hub].append(p)
        return clusters

    # ------------------------------------------------------------------ #
    #  Smart service filter — adaptive cap, same margin check               #
    # ------------------------------------------------------------------ #
    def _filter_services(self, problem: Problem, adaptive_budget: AdaptiveBudget) -> Problem:
        """
        Keep services covering demand corridors with positive margin.
        Uses adaptive filter cap from budget policy instead of fixed 400.

        ``LINER_REGIONAL_FILTER`` (``src/services/regional_filter.py``) selects the legacy
        class-level margin guess + class-ratio cap, or the economic selection, which keeps
        the candidates with the best canonical stand-alone economics up to the same cap.
        """
        corridor_set = {(d.origin, d.destination) for d in problem.demands}
        if filter_mode() == MODE_ECONOMIC:
            return self._filter_services_economic(problem, adaptive_budget, corridor_set)
        kept = []
        # Demand-coherent rotations (Task 9) carry their own demand-based economic
        # evidence and their own budget; they neither pass through the crude
        # capacity x 150 USD margin test below nor use up slots of the legacy cap, so
        # enabling them can only ADD candidates.
        #
        # Classes chosen by the per-rotation screening (Task 10) are NOT exempt: the
        # test below is what removes every Feeder_450 (450 x 0.5 x 150 = 33,750 < its
        # 35,000 weekly hire) whatever its economics, and exempting screened classes
        # was measured (5 seeds, tools/pool_experiment.py ``+noexempt``) to give no
        # gain - 8.76 M vs 8.42 M USD/week with the exemption - so the filter stays
        # as it was for them. Replacing the margin guess is a separate decision.
        own_screened = []
        for svc in problem.services:
            if getattr(svc, "origin_section", "") in ("demand_loop", "elite", "route_operator"):
                own_screened.append(svc)
                continue
            port_set = set(svc.ports)
            covers   = any(o in port_set and d in port_set for (o, d) in corridor_set)
            margin   = (svc.capacity * 0.5 * 150) > svc.weekly_cost
            if covers and margin:
                kept.append(svc)

        filter_params = get_filter_params(adaptive_budget)
        max_services = filter_params["max_services"]
        kept = sorted(kept, key=lambda s: s.capacity / (s.weekly_cost + 1), reverse=True)[:max_services]
        kept = kept + own_screened

        problem.services = kept
        logger.info('services_filtered | region=%s count=%s max_services=%s', self.region, len(kept), max_services)
        return problem

    def _filter_services_economic(self, problem: Problem, adaptive_budget: AdaptiveBudget,
                                  corridor_set) -> Problem:
        """Economic candidate selection (Task 16): same corridor test and same cap as the
        legacy filter, but the cap keeps the best stand-alone economics from the canonical
        service model instead of the best class ratio; no vessel class is treated specially."""
        from src.network.economics import assumptions_for_problem
        from src.services.class_screening import ClassScreener, ClassScreeningConfig

        fleet = getattr(problem, "fleet", None)
        screener = ClassScreener(problem, fleet, assumptions_for_problem(problem),
                                 ClassScreeningConfig(k=1))

        def stand_alone_profit(svc):
            cls = fleet.get_class(getattr(svc, "vessel_class", "")) if fleet is not None else None
            if cls is None:
                return None                                  # unknown class: never a value
            ev = screener.evaluate_class(list(svc.ports), cls)
            return float(ev.standalone_profit_best) if ev.feasible else None

        max_services = get_filter_params(adaptive_budget)["max_services"]
        kept, loops, report = select_economic(problem.services, corridor_set, max_services,
                                              stand_alone_profit)
        self.last_filter_report = report
        problem.services = kept + loops
        logger.info('services_filtered | region=%s mode=economic count=%s max_services=%s '
                    'cut_by_cap=%s no_corridor=%s economics_unavailable=%s',
                    self.region, len(problem.services), max_services, report.cut_by_cap,
                    report.no_corridor, report.economics_unavailable)
        return problem

    # ------------------------------------------------------------------ #
    #  Main pipeline                                                        #
    # ------------------------------------------------------------------ #
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        logger.info('regional_agent_started | agent=%s region=%s', self.name, self.region)
        problem: Problem = input_data["problem"]

        # Capture regional total demand BEFORE any splitting/modification
        total_demand = sum(d.weekly_teu for d in problem.demands)
        num_ports    = len(problem.ports)
        num_lanes    = len(problem.demands)
        avg_demand   = total_demand / num_lanes if num_lanes else 0
        median_demand = sorted([d.weekly_teu for d in problem.demands])[num_lanes // 2] if num_lanes else 0

        top_demands  = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)
        top5         = top_demands[:5]
        top3_teu     = sum(d.weekly_teu for d in top_demands[:3])
        top3_share   = round(top3_teu / total_demand * 100, 1) if total_demand else 0

        corridor_table = "\n".join(
            f"  {i+1}. Port {d.origin:>5} -> Port {d.destination:>5}: "
            f"{d.weekly_teu:>8,.0f} TEU/wk  "
            f"({d.weekly_teu / total_demand * 100:.1f}% of regional demand)"
            for i, d in enumerate(top5)
        )

        hub_detector  = HubDetector(problem)
        detected_hubs = hub_detector.detect_hubs(top_k=5)
        hub_ids_str   = ", ".join(str(h) for h in detected_hubs)

        # Strategy based on demand dispersion 
        if median_demand <= 10 and num_lanes > 500:
            strat_code = "C"
            strat_name = "hybrid"
            decision_rule = (
                f"Select C (Hybrid): median demand {median_demand} TEU/lane with {num_lanes} lanes "
                f"-> consolidation via hub routing essential for low-demand corridors."
            )
        elif top3_share > 35:
            strat_code = "A"
            strat_name = "hub_and_spoke"
            decision_rule = f"Select A (Hub-and-spoke): top-3 share {top3_share}% > 35%."
        else:
            strat_code = "C"
            strat_name = "hybrid"
            decision_rule = (
                f"Select C (Hybrid): top-3 share {top3_share}% with avg {avg_demand:.1f} TEU/lane."
            )

        strategy_prompt = (
            f"REGIONAL DATA - {self.region.upper()}:\n"
            f"  Ports: {num_ports}, Lanes: {num_lanes}, Median demand: {median_demand} TEU/lane\n"
            f"  Total demand: {total_demand:,.0f} TEU/wk, Top-3 share: {top3_share}%\n"
            f"  Hub ports: [{hub_ids_str}]\n\n"
            f"TOP-5 CORRIDORS:\n{corridor_table}\n\n"
            f"DECISION RULE: {decision_rule}\n\n"
            f"STRICT FORMAT:\n"
            f"Strategy: <A | B | C>\n"
            f"Selected: <hub_and_spoke | direct | hybrid>\n"
            f"Reason 1: [cite median demand {median_demand} TEU/lane and >=1 port ID]\n"
            f"Reason 2: [cite port count {num_ports} and lane count {num_lanes}]\n"
            f"Hub Ports: [{hub_ids_str}]"
        )

        try:
            strategy = self.call_llm(strategy_prompt, temperature=0.1)
            if not any(c.isdigit() for c in strategy):
                strategy += f"\nReason 3: Demand {total_demand:,.0f} TEU across {num_ports} ports."
        except Exception:
            strategy = (
                f"Strategy: {strat_code}\nSelected: {strat_name}\n"
                f"Reason 1: Median demand {median_demand} TEU/lane across {num_lanes} lanes "
                f"-> hub consolidation required for {num_lanes-500} low-demand corridors.\n"
                f"Reason 2: {num_ports} ports x {num_lanes} lanes -> hub ports [{hub_ids_str}].\n"
                f"Hub Ports: [{hub_ids_str}]"
            )

        # ── Service generation ─────────────────────────────────────────
        svc_agent  = ServiceGeneratorAgent(name="svc_gen", model=self.model)
        # LINER_SEED: every (region, call) draws its own candidate-generator stream - regions and
        # iterations differ from each other but repeat from run to run; unseeded runs ignore the label
        self._svc_calls = getattr(self, "_svc_calls", 0) + 1
        svc_agent.rng_label = f"{self.region}#{self._svc_calls}"
        svc_result = svc_agent.process({"problem": problem})
        services   = svc_result["services"]
        services_generated = len(services)
        svc_archetype_params = svc_result.get("archetype_params", {})

        norm: List[Service] = []
        # Region-prefix ensures globally unique service IDs (e.g. asia_svc_001)
        region_prefix = self.region.lower().replace(" ", "_")
        for i, s in enumerate(services):
            if isinstance(s, Service):
                norm.append(s)
            else:
                # The generator screens every candidate and returns Service objects.
                # A bare record would need an invented capacity / cost / cycle time
                # (the former 5000 / 150000 / 14 defaults); refuse it instead.
                raise TypeError(
                    f"candidate #{i} is a {type(s).__name__}, not a screened Service: "
                    f"unscreened records cannot enter the optimisation pool "
                    f"(no capacity, cost or cycle time is assumed)"
                )
        # Namespace service IDs with region prefix to avoid global collisions
        for idx, s in enumerate(norm):
            s.id = f"{region_prefix}_svc_{idx:03d}"
        problem.services = norm

        # ── Compute adaptive budget for this region ────────────────────
        try:
            region_cs = compute_complexity_signals(
                num_ports=len(problem.ports),
                demands=problem.demands,
                fleet=problem.fleet,
            )
            region_budget = AdaptiveBudget.from_signals(region_cs)
        except Exception:
            # Fallback: create minimal budget with safe defaults
            region_budget = AdaptiveBudget(
                signals=compute_complexity_signals(
                    num_ports=len(problem.ports),
                    demands=problem.demands,
                    fleet=getattr(problem, "fleet", None),
                )
            )

        # ── Smart service filter ───────────────────────────────────────
        problem           = self._filter_services(problem, region_budget)
        services_filtered = len(problem.services)

        # ── HierarchicalGA with adaptive params ────────────────────────
        logger.info("hierarchical_ga_started")
        sga_params = get_service_ga_params(region_budget)
        freq_params = get_frequency_ga_params(region_budget)
        try:
            self._ga_calls = getattr(self, "_ga_calls", 0) + 1
            ga = HierarchicalGA(
                problem,
                rng_label           = f"{self.region}#{self._ga_calls}",
                pop_size            = sga_params["pop_size"],
                generations         = sga_params["generations"],
                w_profit            = getattr(problem, "profit_weight", 0.5),
                w_coverage          = getattr(problem, "coverage_weight", 0.4),
                w_cost              = getattr(problem, "cost_weight", 0.1),
                alpha_unserved      = ALPHA_UNSERVED,
                max_runtime_sec     = 55.0,
                transship_cost_per_teu = TRANSSHIP_COST_PER_TEU,
                port_cost_per_teu   = PORT_COST_PER_TEU,
                objective_mode      = getattr(problem, "objective_mode", "profit_first"),
                # Pass adaptive stagnation limits through
                **({"stagnation_limit": sga_params["stagnation_limit"]} if sga_params.get("stagnation_limit") else {}),
            )
            chromosome        = ga.run()
            services_selected = sum(chromosome["services"])
            logger.info('ga_complete | services_selected=%s service_ga_gen=%s freq_ga_gen=%s', services_selected, chromosome.get("service_ga_telemetry", {}).get("actual_generations_executed"), chromosome.get("frequency_ga_telemetry", {}).get("actual_generations_executed"))
        except Exception as e:
            logger.error('ga_failed | region=%s error=%s', self.region, str(e))
            # Fallback to empty chromosome
            chromosome = {
                "services": [0] * len(problem.services),
                "frequencies": [0] * len(problem.services),
                "coverage_estimate": 0.0,
                "skip_milp": False
            }
            services_selected = 0

        # ── MILP: ONE region-level allocation ──────────────────────────
        # Before: one MILP per hub cluster, each charged the WHOLE chromosome's
        # vessel / fuel / port-call cost and the results summed (cost counted once per
        # cluster, cross-cluster OD counted twice). The region's demands are already a
        # disjoint partition (by origin), so a single allocation is additive and exact.
        logger.info("milp_region_started | region=%s services=%d", self.region, len(problem.services))
        milp_params = get_milp_params(region_budget)
        sub = Problem(
            ports           = problem.ports,
            services        = problem.services,
            demands         = problem.demands,
            distance_matrix = problem.distance_matrix,
            fleet           = problem.fleet,
        )
        # services call at ports of other regions: carry the full port catalogue so
        # their port costs are looked up, never assumed to be zero
        sub.port_catalog = getattr(problem, "port_catalog", None)
        milp = HubMILP(
            sub,
            chromosome,
            transship_cost_per_teu = TRANSSHIP_COST_PER_TEU,
            port_cost_per_teu      = PORT_COST_PER_TEU,
            alpha_unserved         = ALPHA_UNSERVED,
            min_coverage           = MIN_COVERAGE_FLOOR,
            max_transfer_pairs     = milp_params["max_transfer_pairs"],
            time_limit             = milp_params["time_limit"],
            port_capacity_override = _ip3_port_capacity_override(sub),
        )
        try:
            result = milp.solve()
            logger.info("milp_region_complete | region=%s status=%s", self.region,
                        result.get("status", "unknown"))
        except Exception as e:
            # An exception is a failure, reported as one: status + message, never a
            # zero-cost "success".
            logger.error("milp_region_failed | region=%s error=%s", self.region, e)
            total_dem = sum(d.weekly_teu for d in sub.demands)
            result = {
                "status": "Solver Error", "valid": False, "message": f"{type(e).__name__}: {e}",
                "profit": 0.0, "cost": 0.0, "fuel_cost": 0.0, "transship_cost": 0.0,
                "port_cost": 0.0, "total_cost": 0.0, "coverage": 0.0,
                "satisfied_demand": 0.0, "direct_demand": 0.0, "transship_demand": 0.0,
                "total_demand": total_dem, "unserved_demand": total_dem,
                "selected_services": [],
            }
        cluster_results = [result]          # (name kept: a single region-level result)
        milp_failed = result.get("status") not in ("Optimal", "Feasible") \
            or result.get("valid", True) is False
        if milp_failed:
            logger.error("regional_result_not_usable | region=%s status=%s message=%s",
                         self.region, result.get("status"), result.get("message", ""))

        # Selected services (already one row per service)
        all_selected_services = []
        for svc in result.get("selected_services", []):
            row = dict(svc)
            row["region"] = self.region
            rev = row.get("revenue", 0.0) or 0.0
            cst = row.get("cost", 0.0) or 0.0
            row["weekly_profit"] = rev - cst
            row["margin_pct"] = round((rev - cst) / rev * 100, 2) if rev > 0 else 0.0
            all_selected_services.append(row)
        # the number of services that actually carry cargo in the verified plan
        services_selected = len(all_selected_services)

        # ── Aggregate (one result: nothing is summed twice) ──────────────
        profit         = result["profit"]
        operating_cost = result["cost"]
        fuel_cost      = result.get("fuel_cost", 0)
        transship_cost = result["transship_cost"]
        port_cost      = result["port_cost"]
        total_cost     = result["total_cost"]
        satisfied      = min(result["satisfied_demand"], total_demand)
        unserved_teu   = result["unserved_demand"]
        coverage       = satisfied / total_demand * 100 if total_demand else 0.0

        # Derived metrics
        uncovered_pct      = round(100 - coverage, 1)
        profit_per_service = round(profit / services_selected, 0) if services_selected else 0
        cost_per_service   = round(total_cost / services_selected, 0) if services_selected else 0
        profit_margin_pct  = round(
            profit / (profit + total_cost) * 100, 1
        ) if (profit + total_cost) > 0 else 0
        uncovered_teu_abs  = total_demand * (100 - coverage) / 100

        # candidate pool for the global reconciliation stage (read by the orchestrator)
        self.last_candidate_pool = [
            {"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class}
            for s in problem.services
        ]
        self.last_milp_result = result

        top_unserved  = top_demands[0] if top_demands else None
        unserved_line = (
            f"Port {top_unserved.origin} -> Port {top_unserved.destination}: "
            f"{top_unserved.weekly_teu:,.0f} TEU/week"
            if top_unserved else "N/A"
        )

        # ── LLM explanation ────────────────────────────────────────────
        explanation_prompt = (
            f"Maritime logistics analyst evaluating {self.region.upper()} region.\n\n"
            f"SOLVER RESULTS:\n"
            f"  Services generated/filtered/selected: {services_generated}/{services_filtered}/{services_selected}\n"
            f"  Weekly profit: ${profit:,.0f} | Annual: ${profit * 52:,.0f}\n"
            f"  Cost: Operating ${operating_cost:,.0f} | Transship ${transship_cost:,.0f} | Port ${port_cost:,.0f}\n"
            f"  Margin: {profit_margin_pct}% | Profit/svc: ${profit_per_service:,.0f}/wk\n"
            f"  Coverage: {coverage:.1f}% | Unserved: {uncovered_pct:.1f}% ({unserved_teu:,.0f} TEU/wk)\n"
            f"  Hub ports: [{hub_ids_str}]\n\n"
            f"TOP-5 CORRIDORS:\n{corridor_table}\n\n"
            f"STRICT FORMAT:\n"
            f"Verdict: <Good | Moderate | Poor>\n"
            f"  [Cite margin {profit_margin_pct}% and coverage {coverage:.1f}%]\n\n"
            f"Strengths:\n"
            f"- [Cite profit ${profit:,.0f} and profit/service]\n"
            f"- [Cite coverage {coverage:.1f}% and satisfied TEU]\n\n"
            f"Weaknesses:\n"
            f"- [Cite unserved {uncovered_pct:.1f}% = {unserved_teu:,.0f} TEU/wk]\n"
            f"- [Cite transship ${transship_cost:,.0f} and port ${port_cost:,.0f}]\n\n"
            f"Improvement Actions:\n"
            f"- [Action 1: target {unserved_line}]\n"
            f"- [Action 2: hub [{hub_ids_str}] expansion for {uncovered_pct:.1f}% gap]"
        )

        try:
            explanation = ""
            for _ in range(2):
                explanation = self.call_llm(explanation_prompt, temperature=0.1)
                if self.is_valid_explanation(explanation):
                    break
            if not self.is_valid_explanation(explanation):
                raise ValueError("invalid")
        except Exception:
            # advisory 15 % band (shared definition); no revenue -> no margin
            verdict = margin_verdict_label(
                classify_margin(
                    profit_margin_pct if (profit + total_cost) > 0 else None,
                    not milp_failed),
                good_above_pct=25.0)
            explanation = (
                f"Verdict: {verdict}\n"
                f"  Profit margin {profit_margin_pct}% with coverage {coverage:.1f}%.\n\n"
                f"Strengths:\n- Weekly profit ${profit:,.0f} ({services_selected} services) -> ${profit_per_service:,.0f}/service/week.\n- Satisfied {satisfied:,.0f} TEU/wk at {coverage:.1f}% coverage.\n\n"
                f"Weaknesses:\n- {uncovered_pct:.1f}% unserved ({unserved_teu:,.0f} TEU/wk).\n- Transshipment ${transship_cost:,.0f} + port ${port_cost:,.0f}/wk.\n\n"
                f"Improvement Actions:\n- Add services to {unserved_line} corridor.\n- Expand hub [{hub_ids_str}] by {int(uncovered_pct/5 + 1)} services."
            )

        elapsed = time.perf_counter() - t0

        # ── Phase L + M — actuation record for this region ─────────────
        act = actuation_ledger.begin(f"regional_{self.region}")
        rec = llm_client.last_response
        if rec is not None:
            act.provider = rec.provider
            act.model = rec.model
            act.role = rec.role or "regional"
            act.attempts = 1
            if rec.status == "ok" and rec.error_type.value == "none":
                act.successes = 1
            else:
                act.failures = 1
            if rec.fallback:
                act.fallback_uses = 1
            et = rec.error_type.value
            if et == "http_429":            act.error_429 = 1
            elif et == "timeout":           act.error_timeout = 1
            elif et == "connection":        act.error_connection = 1
            elif et == "auth":              act.error_auth = 1
            elif et == "invalid_model":     act.error_invalid_model = 1
            elif et == "invalid_json":      act.error_invalid_json = 1
            else:                           act.error_unknown = 1
            act.latency_sec = round(rec.latency_ms / 1000.0, 4)
        act.decision_source = "llm" if rec is not None and rec.status == "ok" and not rec.fallback else "rule-based"
        act.ai_generated = act.decision_source == "llm"
        act.decision_consumed = True
        act.total_latency_sec = round(elapsed, 4)

        # ── Regional policy validation ──────────────────────────────────
        try:
            derived = {}
            hub_detector_local = HubDetector(problem)
            detected = hub_detector_local.detect_hubs(top_k=5)
            top_demands_reg = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)

            num_lanes_reg = len(problem.demands)
            density_val = num_lanes_reg / (max(1, len(problem.ports)) * (max(1, len(problem.ports) - 1) / 2)) * 100 if len(problem.ports) > 1 else 0
            density_level = "very_dense" if density_val > 100 else "dense" if density_val > 50 else "moderate" if density_val > 20 else "sparse"

            if density_level in ("very_dense", "dense"):
                vessel_bias_val = "large"
            elif density_level == "moderate":
                vessel_bias_val = "balanced"
            else:
                vessel_bias_val = "small"

            top3_teu_val = sum(d.weekly_teu for d in top_demands_reg[:3])
            top3_share_val = top3_teu_val / max(1, total_demand) * 100 if total_demand else 0

            if top3_share_val > 35:
                cov_base, prof_base = 0.85, 0.15
            elif top3_share_val > 15:
                cov_base, prof_base = 0.65, 0.35
            else:
                cov_base, prof_base = 0.45, 0.55

            if density_level in ("very_dense",):
                cov_base = max(0.15, cov_base - 0.10)
                prof_base = min(0.85, prof_base + 0.10)

            margin_base = {"very_dense": 0.03, "dense": 0.05, "moderate": 0.08, "sparse": 0.10}.get(density_level, 0.05)
            if profit_margin_pct < 10:
                margin_base += 0.05

            regional_policy_data = {
                "coverage_priority": round(cov_base, 2),
                "profit_priority": round(prof_base, 2),
                "min_service_margin": round(min(0.30, margin_base), 2),
                "vessel_bias": vessel_bias_val,
                "hub_focus": [str(h) for h in detected_hubs[:3]],
                "corridor_focus": [[str(top_demands_reg[0].origin), str(top_demands_reg[0].destination)]] if top_demands_reg else [],
                "notes": f"Region {self.region}: dens={density_level}, top3={top3_share_val:.1f}%. Total demand {total_demand:,.0f} TEU/wk.",
                "rationale": [
                    f"density={density_level} -> vessel_bias={vessel_bias_val}",
                    f"margin adjusted for {profit_margin_pct:.1f}% profit margin -> {min(0.30, margin_base):.2f}",
                ],
            }
            validated_policy = validate_regional_policy(
                regional_policy_data,
                valid_port_ids={str(p.id) for p in problem.ports},
                source="rule-based",
            )
            logger.info('regional_policy_validated | tag=%s region=%s policy=%s', "AI_VALIDATED", self.region, validated_policy)
        except Exception as val_err:
            validated_policy = dict(DEFAULT_REGIONAL_POLICY)
            logger.info('regional_policy_validated | tag=%s region=%s error=%s', "AI_FALLBACK", self.region, str(val_err))

        return {
            "agent":               self.name,
            "region":              self.region,
            "status":              cluster_results[0]["status"] if cluster_results else "No result",
            "services_generated":  services_generated,
            "services_filtered":   services_filtered,
            "services_selected":   services_selected,
            "weekly_profit":       profit,
            "annual_profit":       profit * 52,
            "operating_cost":      operating_cost,
            "fuel_cost":           fuel_cost,
            "transship_cost":      transship_cost,
            "port_cost":           port_cost,
            "total_cost":          total_cost,
            "coverage_percent":    coverage,
            "satisfied_demand":    satisfied,
            "unserved_demand":     unserved_teu,
            "total_demand":        total_demand,
            "profit_margin_pct":   profit_margin_pct,
            "profit_per_service":  profit_per_service,
            "cost_per_service":    cost_per_service,
            "uncovered_teu":       uncovered_teu_abs,
            "hub_ports":           detected_hubs,
            "archetype_params":    svc_archetype_params,
            "regional_policy":     validated_policy,
            "strategy":            strategy,
            "explanation":         explanation,
            "selected_services":   all_selected_services,
            "elapsed_sec":         round(elapsed, 1),
            "llm_actuation":       act.to_dict(),
            # Adaptive-budget GA/MILP telemetry (Phase A/B/C)
            "ga_telemetry":        chromosome.get("service_ga_telemetry") if isinstance(chromosome, dict) else None,
            "milp_telemetry": {
                "transfer_pair_budget": milp_params["max_transfer_pairs"] if 'milp_params' in dir() else None,
                "time_limit_sec": milp_params["time_limit"] if 'milp_params' in dir() else None,
                "status": cluster_results[0].get("status") if cluster_results else None,
            },
        }