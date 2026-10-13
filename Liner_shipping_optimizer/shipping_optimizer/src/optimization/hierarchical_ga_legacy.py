"""LEGACY COPY (verbatim) of the pre-network-model implementation, kept for reference.
Not imported by the pipeline. Superseded by src/network/* (see reports/overnight_tasks_2_to_4).
"""
import logging
import time
from typing import Dict, Any

from src.optimization.service_ga    import ServiceGA
from src.optimization.frequency_ga  import FrequencyGA
from src.config.optimizer_config import CONFIG

logger = logging.getLogger(__name__)


class HierarchicalGA:
    def __init__(
        self,
        problem,
        # pass-through to ServiceGA
        pop_size: int   = 80,
        generations: int = 120,
        w_profit: float  = 0.5,
        w_coverage: float = 0.4,
        w_cost: float    = 0.1,
        alpha_unserved: float = 50.0,

        transship_cost_per_teu: float = 80.0,
        port_cost_per_teu: float = 0.0,  # Default to 0 to force use of dataset costs
        # pass-through to FrequencyGA
        max_freq: int    = 3,
        # runtime budget
        max_runtime_sec: float = 60.0,
        # demand threshold for service filtering
        min_route_demand_threshold: float = 0.0,   # TEU — 0 = keep all
        # objective mode
        objective_mode: str = "profit_first",  # "legacy" or "profit_first"
        # adaptive stagnation limits
        stagnation_limit: int = 0,
    ):
        self.problem  = problem
        self.max_time = max_runtime_sec

        self._sga_kwargs = dict(
            pop_size      = pop_size,
            generations   = generations,
            w_profit      = w_profit,
            w_coverage    = w_coverage,
            w_cost        = w_cost,
            alpha_unserved = alpha_unserved,
            stagnation_limit = stagnation_limit,

            transship_cost_per_teu = transship_cost_per_teu,
            port_cost_per_teu = port_cost_per_teu,
            objective_mode = objective_mode,
        )
        self._fga_kwargs = dict(max_freq = max_freq)
        self.min_demand_threshold = min_route_demand_threshold

    # ------------------------------------------------------------------ #
    #  Smart service pre-filter                                             #
    # ------------------------------------------------------------------ #
    def _filter_services(self) -> None:
        """
        Remove services that cover zero demand corridors or have a
        clearly negative expected margin.  Operates in-place on problem.services.
        """
        corridor_set = set()
        for d in self.problem.demands:
            corridor_set.add((d.origin, d.destination))

        # Calculate average revenue per TEU for more accurate margin checks
        total_demand = sum(d.weekly_teu for d in self.problem.demands)
        avg_rev_per_teu = sum(d.weekly_teu * d.revenue_per_teu for d in self.problem.demands) / total_demand if total_demand > 0 else 150

        kept = []
        for svc in self.problem.services:
            port_set = set(svc.ports)
            # Check if any demand corridor is directly covered
            covers = any(
                o in port_set and d in port_set
                for (o, d) in corridor_set
            )

            # Enhanced profitability gate
            # 1. Estimate direct demand for this service
            direct_demand = 0.0
            for d in self.problem.demands:
                if d.origin in port_set and d.destination in port_set:
                    direct_demand += d.weekly_teu

            # 2. Calculate expected revenue at realistic utilization (60% for direct, 30% for indirect)
            expected_utilization = 0.6 if direct_demand > 0 else 0.3
            expected_teu = svc.capacity * expected_utilization
            expected_revenue = expected_teu * avg_rev_per_teu

            # 3. Estimate total costs (weekly + fuel + port)
            estimated_fuel = svc.weekly_cost * 0.3  # Fuel typically ~30% of operating cost
            estimated_port = len(svc.ports) * 5000  # Rough port cost estimate
            total_estimated_cost = svc.weekly_cost + estimated_fuel + estimated_port

            # 4. Check margin - apply enhanced profitability gate with strategic exceptions
            expected_margin = expected_revenue - total_estimated_cost
            margin_pct = expected_margin / total_estimated_cost if total_estimated_cost > 0 else -1.0

            # Enhanced strategic classification
            is_strategic = (
                len(svc.ports) <= 2 and  # Direct services
                expected_utilization > 0.5  # With high utilization
            )
            is_feeder_critical = (
                len(svc.ports) == 2 and
                direct_demand == 0 and  # No direct demand (pure feeder)
                any(p in port_set for p in ['HKG', 'SIN', 'ROT', 'NYC'])  # Connects to major hub
            )
            is_hub_connector = (
                len(svc.ports) == 2 and
                port_set.intersection(['HKG', 'SIN', 'ROT', 'NYC', 'SHA', 'CNXHG', 'SGSIN', 'NLRTM', 'USLAX'])  # Hub ports
            )

            # Tiered profitability requirements
            if is_strategic:
                min_margin_pct = 0.0  # No minimum for strategic services
            elif is_feeder_critical:
                min_margin_pct = -0.15  # Allow 15% loss for critical feeders
            elif is_hub_connector:
                min_margin_pct = -0.10  # Allow 10% loss for hub connectors
            else:
                min_margin_pct = 0.05  # 5% minimum margin for regular services

            # Additional checks for service viability
            capacity_efficiency = expected_teu / svc.capacity if svc.capacity > 0 else 0
            teu_threshold = max(500, svc.capacity * 0.1)  # Minimum 10% utilization or 500 TEU

            margin_ok = margin_pct > min_margin_pct or (covers and margin_pct > -0.05)
            utilization_ok = capacity_efficiency > 0.1 or expected_teu > teu_threshold

            if covers and margin_ok and utilization_ok:
                kept.append(svc)

        before = len(self.problem.services)
        self.problem.services = kept
        logger.info("service_filter", before=before, after=len(kept))

    # ------------------------------------------------------------------ #
    #  Main run                                                             #
    # ------------------------------------------------------------------ #
    def run(self, seed_chromosome: dict = None) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # ── Pre-filter services ────────────────────────────────────────
        self._filter_services()

        if not self.problem.services:
            logger.warning("no_services_after_filter")
            return {"services": [], "frequencies": [], "coverage_estimate": 0.0}

        # ── Level 1: service selection ─────────────────────────────────
        service_ga   = ServiceGA(self.problem, **self._sga_kwargs)
        seed_services = seed_chromosome.get("services") if seed_chromosome else None
        best_services = service_ga.run(seed_solution=seed_services)

        elapsed = time.perf_counter() - t0
        if elapsed > self.max_time * 0.8:
            if CONFIG.verbose_runtime_logs:
                logger.warning("ga_runtime_budget_near | elapsed=%.2fs", elapsed)

        # ── Level 2: frequency optimisation ───────────────────────────
        freq_ga   = FrequencyGA(self.problem, best_services, **self._fga_kwargs)
        best_freq = freq_ga.run()
        import math

        # Determine fleet size limit from problem fleet data, or fall back to
        # a reasonable default when no fleet is provided (legacy behavior).
        fleet_size = 300  # legacy default
        if self.problem.fleet is not None and self.problem.fleet.total_vessels > 0:
            fleet_size = self.problem.fleet.total_vessels

        def _vessels(services_mask, frequencies):
            return sum(
                math.ceil(self.problem.services[i].cycle_time * max(1, frequencies[i]) / 7)
                for i, v in enumerate(services_mask)
                if v == 1 and i < len(frequencies)
            )

        vessels_used = _vessels(best_services, best_freq)
        if vessels_used > fleet_size:
            logger.info("post_ga_fleet_prune | vessels=%d limit=%d", vessels_used, fleet_size)
            # Score each active service by efficiency: demand served per vessel
            active = [
                (i, service_ga.service_direct_demand[i] /
                    max(1, math.ceil(self.problem.services[i].cycle_time * best_freq[i] / 7)))
                for i in range(len(best_services))
                if best_services[i] == 1 and i < len(best_freq) and best_freq[i] > 0
            ]
            # Sort ascending: lowest efficiency first
            active.sort(key=lambda x: x[1])
            for svc_idx, _ in active:
                if vessels_used <= fleet_size:
                    break
                vessels_freed = math.ceil(
                    self.problem.services[svc_idx].cycle_time * best_freq[svc_idx] / 7
                )
                best_services[svc_idx] = 0
                best_freq[svc_idx] = 0
                vessels_used -= vessels_freed
            logger.info("post_ga_fleet_prune_done | vessels_now=%d", vessels_used)

        # ── Coverage estimate from GA fitness info ─────────────────────
        total_demand = sum(d.weekly_teu for d in self.problem.demands)
        satisfied    = sum(
            min(
                self.problem.services[i].capacity * best_freq[i],
                service_ga.service_direct_demand[i]
            )
            for i in range(len(best_services)) if best_services[i] == 1
        )
        coverage_estimate = min(satisfied, total_demand) / (total_demand or 1.0) * 100

        ga_total_elapsed = time.perf_counter() - t0

        chromosome = {
            "services":          best_services,
            "frequencies":       best_freq,
            "coverage_estimate": coverage_estimate,
            #flag set True when GA output is too weak to warrant MILP
            "skip_milp":         coverage_estimate < 30.0,
            # Adaptive-budget telemetry (Phase A/B/C)
            "service_ga_telemetry":    getattr(service_ga, "_telemetry", None),
            "frequency_ga_telemetry":  getattr(freq_ga,   "_telemetry", None),
            "ga_total_elapsed_sec":    round(ga_total_elapsed, 4),
        }

        logger.info(
            "hierarchical_ga_complete",
            services_selected = sum(best_services),
            coverage_estimate = coverage_estimate,
            elapsed_sec       = round(ga_total_elapsed, 2),
            service_ga_gen    = chromosome["service_ga_telemetry"].get("actual_generations_executed") if chromosome["service_ga_telemetry"] else None,
            freq_ga_gen       = chromosome["frequency_ga_telemetry"].get("actual_generations_executed") if chromosome["frequency_ga_telemetry"] else None,
        )
        return chromosome