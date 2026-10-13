import logging
import random
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.agents.base                          import BaseAgent
from src.services.hub_detector                import HubDetector
from src.services.candidate_service_generator import CandidateServiceGenerator
from src.services.demand_coherent import (
    config_from_environment as demand_loop_config_from_environment,
    generate_demand_coherent_rotations,
)
from src.services.class_screening import (
    ClassScreener, config_from_environment as class_screen_config_from_environment,
)
from src.services.route_operators import (
    config_from_environment as route_operator_config_from_environment,
    generate_operator_rotations,
)
from src.optimization.data                    import Problem, Service
from src.utils.fuel_cost                      import map_capacity_to_vessel_class
from src.services.service_feasibility         import (
    CandidateReport, DEFAULT_PORT_TIME, ServiceFeasibilityError,
    evaluate_rotation, rank_vessel_classes,
)
from src.validation.archetype_validator       import validate_archetype_params, DEFAULT_ARCHETYPE_PARAMS
from src.llm.actuation                        import actuation_ledger
from src.llm.client                           import llm_client
from src.optimization.adaptive_budget         import get_service_generation_params, AdaptiveBudget, ComplexitySignals

logger = logging.getLogger(__name__)


class ServiceGeneratorAgent(BaseAgent):

    def __init__(self, name: str, model: str):
        super().__init__(name=name, role="Shipping Service Generator", model=model, llm_role="service_generator")
        self._metrics = {
            "llm_calls": 0,
            "json_parse_success": 0,
            "validator_executed": 0,
            "fallback_count": 0,
        }
        # Filled by generate_services(): what was generated / accepted / rejected.
        self.last_candidate_report = CandidateReport()
        # Report of the demand-coherent multi-port generator (None when disabled).
        self.last_demand_coherent_report = None
        # Report of the per-rotation vessel-class screening (None when disabled).
        self.last_class_screening_report = None
        # Report of the route-level operators / elitism (Task 21; None when disabled).
        self.last_route_operator_report = None

    def get_system_prompt(self) -> str:
        return (
            "You are a liner shipping service design specialist.\n\n"
            "Advise on service archetypes for a given port network. "
            "Ground every recommendation in the network statistics provided. "
            "Every statement must cite a specific number. "
            "Do not use vague language. Do not repeat the question."
        )

    # ------------------------------------------------------------------
    # Core service generation
    # ------------------------------------------------------------------
    def generate_services(self, problem: Problem, archetype_params: Optional[Dict] = None) -> List[Service]:
        logger.info('service_generation_started | ports=%s demands=%s', len(problem.ports), len(problem.demands))

        hub_detector = HubDetector(problem)
        hubs         = hub_detector.detect_hubs(top_k=20)   # use top-20 hubs
        hub_set      = set(hubs)
        top10_hubs   = hubs[:10]

        services: List[Service] = []
        sid = 0

        # ── Feasibility screening (physical service model) ─────────────────
        # Every candidate is a closed rotation sailed by ONE class of the
        # canonical fleet. Capacity, speed, vessel cost and the cycle time are
        # derived from that class and the route's directed distances; a
        # candidate that cannot be evaluated is rejected with a reason and never
        # enters the pool. No default fleet, class, distance or capacity exists.
        fleet = getattr(problem, "fleet", None)
        if fleet is None or not getattr(fleet, "classes", None):
            raise ServiceFeasibilityError(
                "problem.fleet is required to generate candidate services "
                "(load it with NetworkLoader.load_fleet / load_problem); no default "
                "fleet or vessel class is assumed"
            )
        port_time = DEFAULT_PORT_TIME
        known_ports = set(problem.distance_matrix)
        unit_status = getattr(fleet, "capacity_unit_status", "provisional")
        report = CandidateReport(capacity_unit_status=unit_status,
                                 port_time_basis=port_time.basis)

        # Per-rotation class screening (Task 10). Off (k = 0) reproduces the legacy
        # nearest-capacity assignment exactly; on, every registered class is evaluated
        # for each rotation and only ``k`` feasible, economically promising
        # alternatives are offered (LINER_CLASS_SCREEN=k).
        screen_cfg = class_screen_config_from_environment()
        screener = None
        if screen_cfg.enabled:
            from src.network.economics import assumptions_for_problem
            screener = ClassScreener(problem, fleet, assumptions_for_problem(problem), screen_cfg)
        self.last_class_screening_report = screener.report if screener is not None else None
        seen_pairs = set()          # (canonical rotation, class), used when screening

        def _canonical_key(route, cname):
            p = list(route)
            if len(p) >= 2 and p[0] == p[-1]:
                p = p[:-1]
            i = min(range(len(p)), key=lambda k: p[k]) if p else 0
            return (tuple(p[i:] + p[:i]), cname)

        def _emit(route, target_capacity, section, legacy_cycle, vessel=None):
            """Evaluate one candidate rotation and append it only if feasible."""
            nonlocal sid
            if screener is not None and vessel is None:
                return _emit_screened(route, target_capacity, section, legacy_cycle)
            return _emit_single(route, target_capacity, section, legacy_cycle, vessel)

        def _make_service(route, feas, section):
            nonlocal sid
            svc = Service(
                id=sid, ports=list(route),
                capacity=feas.capacity_teu, weekly_cost=feas.weekly_vessel_cost,
                cycle_time=feas.cycle_time_days, speed=feas.speed_knots,
                vessel_class=feas.vessel_class,
                distance_nm=feas.distance_nm,
                required_vessels=feas.required_vessels_one_departure,
                capacity_unit_status=feas.capacity_unit_status,
            )
            # provenance of the candidate (which generator section proposed it)
            svc.origin_section = section
            services.append(svc)
            sid += 1
            return svc

        def _emit_screened(route, target_capacity, section, legacy_cycle):
            """Offer the screened class alternatives of this rotation (best first)."""
            names = screener.alternatives(route, target_capacity)
            if not names:
                # no feasible class: fall back to the canonical path so that the
                # rejection and its reasons are recorded exactly as before
                return _emit_single(route, target_capacity, section, legacy_cycle, None)
            first = None
            screened = screener.screen(route, target_capacity)
            evidence = {e.vessel_class: e.promising for e in screened.selected}
            for nm in names:
                v = fleet.get_class(nm)
                feas = evaluate_rotation(
                    route, v, problem.distance_matrix, known_ports=known_ports,
                    port_time=port_time, capacity_unit_status=unit_status)
                key = _canonical_key(route, nm)
                if feas.feasible and key in seen_pairs:
                    report.duplicate_rotation_class += 1
                    continue
                report.record(section, feas, legacy_declared=legacy_cycle)
                if not feas.feasible:
                    continue
                seen_pairs.add(key)
                svc = _make_service(route, feas, section)
                # provenance only: True when the class was chosen on positive
                # stand-alone economics (the regional filter does not read it)
                svc.economically_screened = bool(evidence.get(nm, False))
                if first is None:
                    first = svc
                    if screened.legacy_fallback:
                        # same meaning as in the legacy path: the nearest-capacity
                        # class could not carry the rotation
                        report.class_fallbacks += 1
            return first

        def _emit_single(route, target_capacity, section, legacy_cycle, vessel=None):
            nonlocal sid

            def _eval(v):
                return evaluate_rotation(
                    route, v, problem.distance_matrix,
                    known_ports=known_ports, port_time=port_time,
                    capacity_unit_status=unit_status,
                )

            if vessel is not None:
                feas = _eval(vessel)               # class named by the caller
            else:
                # Nearest-capacity class first; if the rotation is not locally
                # feasible with it (e.g. it needs more vessels than the class owns)
                # the next-nearest class is tried. The first failure is reported
                # if none works.
                feas = None
                for rank, cand in enumerate(rank_vessel_classes(target_capacity, fleet)):
                    trial = _eval(cand)
                    if feas is None:
                        feas = trial
                    if trial.feasible:
                        if rank > 0:
                            report.class_fallbacks += 1
                        feas = trial
                        break
            report.record(section, feas, legacy_declared=legacy_cycle)
            if not feas.feasible:
                return None
            if screener is not None:
                seen_pairs.add(_canonical_key(route, feas.vessel_class))
            return _make_service(route, feas, section)

        # ── Apply archetype params to influence generation mix ─────────
        params = archetype_params or {}
        arch_mix = params.get("archetype_mix", {})
        if not arch_mix:
            arch_mix = {k: v for k, v in params.items() if k.endswith("_ratio")} or {
                "direct_ratio": 0.60, "hub_loop_ratio": 0.15, "feeder_ratio": 0.20, "trunk_ratio": 0.05
            }
        vb = params.get("vessel_bias", params.get("vessel_bias", "balanced"))
        ratios_valid = all(k in arch_mix for k in ("direct_ratio", "hub_loop_ratio", "feeder_ratio", "trunk_ratio"))

        # ── Adaptive budget for service-generation targets ───────────────
        # Use complexity-signal-driven targets as the primary source.
        # Fallback to LLM-influenced or hardcoded values when unavailable.
        try:
            from src.optimization.adaptive_budget import compute_complexity_signals
            cs = compute_complexity_signals(
                num_ports=len(problem.ports),
                demands=problem.demands,
                fleet=getattr(problem, "fleet", None),
            )
            ab = AdaptiveBudget.from_signals(cs)
            gen_params = get_service_generation_params(ab)
            n_direct_raw = gen_params["direct_target"]
            hub_loop_count_raw = gen_params["hub_loop_target"]
            feeder_target_raw = gen_params["feeder_target"]
            heuristic_target_raw = gen_params["heuristic_target"]
            trunk_target_raw = gen_params["trunk_target"]
            logger.info('adaptive_budget_loaded | direct=%s hub_loop=%s feeder=%s heuristic=%s trunk=%s', n_direct_raw, hub_loop_count_raw, feeder_target_raw, heuristic_target_raw, trunk_target_raw)
        except Exception:
            # Fallback to static defaults (no adaptive overhead)
            n_direct_raw = 500
            hub_loop_count_raw = 10
            feeder_target_raw = 100
            heuristic_target_raw = 150
            trunk_target_raw = 45

        if ratios_valid:
            dr = arch_mix["direct_ratio"]
            hl = arch_mix["hub_loop_ratio"]
            fr = arch_mix["feeder_ratio"]
            BASE_DR, BASE_HL, BASE_FR = 0.60, 0.15, 0.20
            n_direct = min(n_direct_raw, max(200, int(n_direct_raw * dr / max(BASE_DR, 0.01))))
            hub_loop_count = max(2, int(hub_loop_count_raw * hl / max(BASE_HL, 0.01)))
            feeder_count_target = max(20, int(feeder_target_raw * fr / max(BASE_FR, 0.01)))
            logger.info('archetype_params_applied | direct_ratio=%s hub_loop_ratio=%s feeder_ratio=%s trunk_ratio=%s', dr, hl, fr, arch_mix.get("trunk_ratio", 0.05))
        else:
            n_direct = n_direct_raw
            hub_loop_count = hub_loop_count_raw
            feeder_count_target = feeder_target_raw

        # ── A: Direct services for top-N high-demand corridors ─────────
        top_demands  = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)
        n_direct = min(n_direct, len(top_demands))
        for d in top_demands[:n_direct]:
            if d.origin == d.destination:
                continue
            # Match vessel capacity to demand (with 20% buffer for growth)
            demand_teu = d.weekly_teu
            target_capacity = max(1000, demand_teu * 1.2)  # Min 1000 TEU, 20% buffer

            # Sizing target: nearest standard size. The vessel class is the fleet
            # class nearest to it; its OWN capacity, speed and cost are then used.
            standard_sizes = [1000, 2000, 4500, 8000, 12000, 16000]
            closest_size = min(standard_sizes, key=lambda x: abs(x - target_capacity))

            _emit([d.origin, d.destination], closest_size, "direct", 14)
        logger.info('direct_services_added | count=%s', report.accepted_by_section.get("direct", 0))

        # ── B: Multi-port regional loop services via each hub ───────────
        # Each loop visits the hub + its top-N spoke ports.
        # This is the key driver of transshipment coverage.
        demand_by_port = defaultdict(float)
        for d in problem.demands:
            demand_by_port[d.origin]      += d.weekly_teu
            demand_by_port[d.destination] += d.weekly_teu

        loop_count = 0
        for hub in top10_hubs:
            # Find the top-20 spoke ports by demand volume for this hub
            hub_demand_pairs = [
                (d.weekly_teu, d.origin if d.destination == hub else d.destination)
                for d in problem.demands
                if d.origin == hub or d.destination == hub
            ]
            hub_demand_pairs.sort(reverse=True)
            top_spokes = list(dict.fromkeys(p for _, p in hub_demand_pairs[:40]))[:20]

            if not top_spokes:
                continue

            # Create 4-service loops: hub + 5 spokes each
            loop_size = 5
            for start in range(0, min(len(top_spokes), 20), loop_size):
                batch = top_spokes[start:start + loop_size]
                if len(batch) < 2:
                    continue
                route = [hub] + batch + [hub]  # loop back to hub

                # Calculate total demand for this hub loop
                loop_demand = sum(
                    d.weekly_teu for d in problem.demands
                    if all(p in route for p in [d.origin, d.destination])
                )

                # Sizing target from actual demand; the vessel class is the fleet
                # class nearest to it and supplies capacity, speed and cost.
                if loop_demand > 8000:
                    target = 14000
                elif loop_demand > 4000:
                    target = 10000
                else:
                    target = 8000

                if _emit(route, target, "hub_loop", 21) is not None:
                    loop_count += 1
        logger.info('hub_loop_services_added | count=%s', loop_count)

        # ── C: Hub-to-hub trunk routes ──────────────────────────────────
        trunk_count = 0
        for i in range(len(top10_hubs)):
            for j in range(i + 1, len(top10_hubs)):
                if _emit([top10_hubs[i], top10_hubs[j]], 12000, "trunk", 14) is not None:
                    trunk_count += 1
        logger.info('trunk_services_added | count=%s', trunk_count)

        # ── D: Feeder services — every spoke to best hub ────────────────
        # Essential for transshipment: spoke -> hub -> destination.
        spoke_ports = [p.id for p in problem.ports if p.id not in hub_set]

        # Demand-weighted hub affinity for each spoke
        hub_affinity: Dict[int, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for d in problem.demands:
            if d.origin in hub_set and d.destination not in hub_set:
                hub_affinity[d.destination][d.origin] += d.weekly_teu
            if d.destination in hub_set and d.origin not in hub_set:
                hub_affinity[d.origin][d.destination] += d.weekly_teu

        feeder_count = 0
        for spoke in spoke_ports:
            hub_flows = hub_affinity.get(spoke, {})
            # Connect to top-2 hubs (for redundancy and better MILP routing)
            best_hubs = sorted(hub_flows, key=hub_flows.get, reverse=True)[:2]
            if not best_hubs:
                best_hubs = top10_hubs[:1]

            for best_hub in best_hubs:
                if best_hub == spoke:
                    continue

                # Calculate total demand for this spoke-hub pair
                spoke_demand = sum(
                    d.weekly_teu for d in problem.demands
                    if (d.origin == spoke and d.destination == best_hub) or
                       (d.origin == best_hub and d.destination == spoke)
                )

                # Size vessel based on demand with calibrated sizing
                if spoke_demand > 5000:
                    target_capacity = spoke_demand * 1.2  # 20% buffer for high-demand
                    standard_sizes = [4500, 8000, 10000, 14000]
                elif spoke_demand > 2000:
                    target_capacity = spoke_demand * 1.3  # 30% buffer for medium-demand
                    standard_sizes = [2000, 4500, 8000]
                elif spoke_demand > 500:
                    target_capacity = spoke_demand * 1.5  # 50% buffer for low-demand
                    standard_sizes = [500, 1000, 2000, 4500]
                else:
                    target_capacity = 500  # Minimum viable size
                    standard_sizes = [500, 1000]

                closest_size = min(standard_sizes, key=lambda x: abs(x - target_capacity))

                if _emit([spoke, best_hub], closest_size, "feeder", 7) is not None:
                    feeder_count += 1
        logger.info('feeder_services_added | count=%s', feeder_count)

        # ── E: Heuristic base candidate pool ───────────────────────────
        # Use adaptive heuristic target instead of fixed 150.
        heuristic_limit = min(heuristic_target_raw, len(top_demands)) if heuristic_target_raw else 150
        from src.utils.rng import streams as _streams
        generator = CandidateServiceGenerator(
            problem, rng=_streams("candidate_generator", getattr(self, "rng_label", None) or self.name).py)
        generator._service_id_counter = sid
        base_services = generator.generate_services(num_services=heuristic_limit)
        # CandidateServiceGenerator yields plain {"ports": [...]} records. They go
        # through the same screening as every other candidate and are converted to
        # ``Service`` objects (optimisers read ``.ports`` / ``.capacity``). A record
        # that names its own vessel class is evaluated with that class; an unknown
        # name is a rejection, not a substitution.
        for rec in base_services:
            named = rec.get("vessel_class")
            vessel = fleet.get_class(named) if named else None
            if named and vessel is None:
                feas = evaluate_rotation(rec["ports"], None, problem.distance_matrix,
                                         known_ports=known_ports, port_time=port_time,
                                         capacity_unit_status=unit_status)
                feas.vessel_class = str(named)
                report.record("heuristic", feas, legacy_declared=rec.get("cycle_time", 14))
                continue
            _emit(rec["ports"], rec.get("capacity", 5000), "heuristic",
                  rec.get("cycle_time", 14), vessel=vessel)
        logger.info('heuristic_services_added | count=%s', report.accepted_by_section.get("heuristic", 0))

        # ── F: demand-coherent multi-port closed rotations (Task 9) ─────
        # Grown from the strongest OD opportunities, ride-feasible cargo only,
        # budgeted and de-duplicated against everything generated above. Disabled
        # with LINER_DEMAND_LOOP_BUDGET=0.
        dc_cfg = demand_loop_config_from_environment()
        self.last_demand_coherent_report = None
        if dc_cfg.enabled and dc_cfg.budget > 0:
            existing = [(list(s.ports), s.vessel_class) for s in services]
            proposals, dc_report = generate_demand_coherent_rotations(
                problem, fleet, existing, dc_cfg)
            emitted = 0
            for pr in proposals:
                if _emit(list(pr.ports), pr.target_capacity_teu, "demand_loop", None) is not None:
                    emitted += 1
            self.last_demand_coherent_report = dc_report
            logger.info('demand_loop_services_added | proposed=%s emitted=%s grown=%s seeds=%s',
                        len(proposals), emitted, dc_report.grown_candidates, dc_report.seeds_used)

        # ── G: route-level operators and elitism (Task 21) ──────────────
        # Edits the rotations that matter (the previous iteration's operated rotations when
        # the orchestrator supplies them, else the pool's best stand-alone rotations) and
        # re-offers the elites; every variant is evaluated with the canonical service model.
        # Disabled unless LINER_ROUTE_OPERATORS > 0 or LINER_ELITISM=1.
        ro_cfg = route_operator_config_from_environment()
        self.last_route_operator_report = None
        if ro_cfg.enabled:
            from src.network.economics import assumptions_for_problem
            from src.services.class_screening import ClassScreener as _CS, ClassScreeningConfig as _CSC
            existing_ro = [(list(s.ports), s.vessel_class) for s in services]
            feedback = getattr(problem, "network_feedback", None)
            elite_pool = None
            if not feedback and ro_cfg.budget > 0:
                scr = _CS(problem, fleet, assumptions_for_problem(problem), _CSC(k=1))
                scored = []
                for s in services:
                    cls_ = fleet.get_class(s.vessel_class)
                    if cls_ is None:
                        continue
                    ev_ = scr.evaluate_class(list(s.ports), cls_)
                    if ev_.feasible and ev_.promising:
                        scored.append((-ev_.standalone_profit_best, len(scored), list(s.ports), s.vessel_class))
                scored.sort()
                elite_pool = [(p, c) for _, _, p, c in scored[:ro_cfg.elites]]
            proposals_ro, ro_report = generate_operator_rotations(
                problem, fleet, existing_ro, ro_cfg, feedback=feedback, elite_pool=elite_pool)
            emitted_ro = 0
            for pr in proposals_ro:
                sect = "elite" if pr.operator == "elite" else "route_operator"
                if _emit(list(pr.ports), pr.target_capacity_teu, sect, None,
                         vessel=fleet.get_class(pr.vessel_class)) is not None:
                    emitted_ro += 1
            self.last_route_operator_report = ro_report
            logger.info('route_operator_services_added | proposed=%s emitted=%s elites=%s variants=%s',
                        len(proposals_ro), emitted_ro, ro_report.elites_in, ro_report.variants_evaluated)

        self.last_candidate_report = report
        logger.info(
            "candidate_services_generated | accepted=%d rejected=%d generated=%d",
            report.accepted, report.rejected, report.generated,
        )
        return services

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        logger.info('service_generator_agent_started | agent=%s', self.name)
        problem: Problem = input_data["problem"]

        num_ports    = len(problem.ports)
        num_lanes    = len(problem.demands)
        total_demand = sum(d.weekly_teu for d in problem.demands)
        avg_demand   = total_demand / num_lanes if num_lanes else 0
        median_demand = sorted([d.weekly_teu for d in problem.demands])[num_lanes // 2] if num_lanes else 0

        top_demands  = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)
        top3_teu     = sum(d.weekly_teu for d in top_demands[:3])
        top3_share   = round(top3_teu / total_demand * 100, 1) if total_demand else 0
        top500_share = round(sum(d.weekly_teu for d in top_demands[:500]) / total_demand * 100, 1) if total_demand else 0

        hub_detector = HubDetector(problem)
        hubs         = hub_detector.detect_hubs(top_k=20)
        hub_ids_str  = ", ".join(str(h) for h in hubs[:10])
        spoke_count  = max(0, num_ports - 20)

        # Correct strategy selection: based on demand dispersion
        if median_demand <= 10 and num_lanes > 1000:
            archetype = "HYBRID"
            rationale = (
                f"Median demand is only {median_demand} TEU/lane across {num_lanes} lanes — "
                f"consolidation via hubs is essential. Top-500 corridors ({top500_share}% of demand) "
                f"served direct; remaining {num_lanes-500} low-demand corridors served via hub transshipment."
            )
        elif top3_share > 35:
            archetype = "HUB-AND-SPOKE"
            rationale = (
                f"Top-3 share {top3_share}% indicates concentrated demand — "
                f"hub trunk routes between [{hub_ids_str}] form the backbone."
            )
        else:
            archetype = "HYBRID"
            rationale = (
                f"Top-3 share {top3_share}% with avg {avg_demand:.1f} TEU/lane — "
                f"direct services for top-500 corridors plus hub routing for the rest."
            )

        corridor_table = "\n".join(
            f"  {i+1}. Port {d.origin:>5} -> Port {d.destination:>5}: "
            f"{d.weekly_teu:>8,.0f} TEU/wk"
            for i, d in enumerate(top_demands[:5])
        )

        prompt = (
            f"Liner shipping service design for {num_ports}-port network.\n\n"
            f"NETWORK STATS:\n"
            f"  Ports: {num_ports}, Lanes: {num_lanes}, Median demand/lane: {median_demand} TEU\n"
            f"  Total demand: {total_demand:,.0f} TEU, Avg: {avg_demand:.1f} TEU/lane\n"
            f"  Top-3 share: {top3_share}%, Top-500 share: {top500_share}%\n"
            f"  Hub ports: [{hub_ids_str}] ({len(hubs)} detected)\n\n"
            f"TOP-5 CORRIDORS:\n{corridor_table}\n\n"
            f"ARCHETYPE: {archetype}\n"
            f"RATIONALE: {rationale}\n\n"
            f"In 2 sentences: (1) confirm archetype citing median demand {median_demand} TEU "
            f"and total {total_demand:,.0f} TEU; "
            f"(2) expected GA retention out of ~{len(problem.services) if problem.services else 800} candidates."
        )

        try:
            strategy = self.call_llm(prompt, temperature=0.1)
        except Exception:
            strategy = (
                f"Strategy: {'C' if archetype == 'HYBRID' else 'A'}\n"
                f"Selected: {'hybrid' if archetype == 'HYBRID' else 'hub_and_spoke'}\n"
                f"Reason 1: {rationale}\n"
                f"Reason 2: {num_ports} ports x {num_lanes} lanes -> hub ports [{hub_ids_str}].\n"
                f"Hub Ports: [{hub_ids_str}]"
            )

        # ── Generate structured archetype params from LLM + validation ──
        parse_succeeded = False
        try:
            json_prompt = prompt + (
                "\n\nReturn ONLY valid JSON (no markdown, no preamble):\n"
                '{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, '
                '"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, '
                '"vessel_bias": "small"|"balanced"|"large", '
                '"hub_focus": ["PORT_ID", ...], '
                '"notes": "<brief rationale>"}'
            )
            raw_json = self.call_llm(json_prompt, temperature=0.1)
            self._metrics["llm_calls"] += 1
            logger.info('archetype_params_generated | tag=%s raw_len=%s', "AI_GENERATED", len(raw_json))
            logger.info('p1e_raw_svcgen | raw_len=%s raw_preview=%s', len(raw_json), raw_json[:200])
            import json as _json
            import re as _re
            text = raw_json.strip()
            text = _re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = _re.sub(r"\n?```$", "", text)
            try:
                parsed = _json.loads(text.strip())
                self._metrics["json_parse_success"] += 1
            except _json.JSONDecodeError:
                m = _re.search(r"\{.*\}", text, _re.DOTALL)
                parsed = _json.loads(m.group()) if m else {}
                if parsed:
                    self._metrics["json_parse_success"] += 1
            parse_succeeded = bool(parsed)
            archetype_params = validate_archetype_params(parsed)
            self._metrics["validator_executed"] += 1
            tag = "AI_FALLBACK" if not parse_succeeded else "AI_VALIDATED"
            logger.info('archetype_params_generated | tag=%s params=%s parse_ok=%s', tag, archetype_params, parse_succeeded)
        except Exception:
            archetype_params = dict(DEFAULT_ARCHETYPE_PARAMS)
            self._metrics["fallback_count"] += 1
            logger.info('archetype_params_generated | tag=%s reason=%s', "AI_FALLBACK", "LLM parse failed, using defaults")

        services         = self.generate_services(problem, archetype_params=archetype_params)
        problem.services = services
        logger.info('services_attached_to_problem | count=%s', len(services))
        if parse_succeeded:
            # the validated archetype parameters were handed to the generator (observability tag only)
            logger.info('archetype_params_applied | tag=%s params=%s', "AI_APPLIED", archetype_params)

        # Phase L + M — actuation record.
        act = actuation_ledger.begin(f"service_generator_{self.name}")
        rec = llm_client.last_response
        if rec is not None:
            act.provider = rec.provider
            act.model = rec.model
            act.role = rec.role or "service_generator"
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
        is_default = (
            archetype_params.get("direct_ratio") == 0.60
            and archetype_params.get("hub_loop_ratio") == 0.15
            and archetype_params.get("feeder_ratio") == 0.20
            and archetype_params.get("trunk_ratio") == 0.05
        )
        act.decision_source = "llm" if not is_default else "rule-based"
        act.ai_generated = act.decision_source == "llm"
        # Service generator decisions reach downstream when the candidate
        # pool is consumed by the regional agent.  This is always true by
        # construction: ``generate_services`` always returns services.
        act.decision_consumed = True
        act.total_latency_sec = round(time.perf_counter() - t0, 4)

        return {
            "agent":              self.name,
            "strategy":           strategy,
            "services_generated": len(services),
            "services":           services,
            "archetype_params":   archetype_params,
            "candidate_feasibility": self.last_candidate_report.to_dict(),
            "demand_coherent": (self.last_demand_coherent_report.to_dict()
                                if self.last_demand_coherent_report is not None else None),
            "class_screening": (self.last_class_screening_report.to_dict()
                                if self.last_class_screening_report is not None else None),
            "llm_runtime_metrics": dict(self._metrics),
            "llm_actuation":      act.to_dict(),
        }