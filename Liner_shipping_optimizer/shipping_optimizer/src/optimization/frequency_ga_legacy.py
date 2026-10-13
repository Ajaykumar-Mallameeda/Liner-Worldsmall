"""LEGACY COPY (verbatim) of the pre-network-model implementation, kept for reference.
Not imported by the pipeline. Superseded by src/network/* (see reports/overnight_tasks_2_to_4).
"""
import math
import random
import logging
import numpy as np
import time
from typing import List
from src.utils.fuel_cost import calculate_weekly_fuel_cost
from src.config.optimizer_config import CONFIG

logger = logging.getLogger(__name__)


NO_IMPROVE_LIMIT = 8      # Reduced early stop threshold
MAX_RUNTIME = 90          # Hard runtime cap in seconds

MAX_FREQ = 3          # maximum sailings per week per service
MIN_FREQ = 1


class FrequencyGA:
    def __init__(
        self,
        problem,
        services: List[int],    # binary mask from ServiceGA
        max_freq: int = MAX_FREQ,
        pop_size: int = 40,
        generations: int = 60,
        overcap_penalty: float = 0.015,   # fraction of unused capacity × weekly_cost
        port_cost_per_teu: float = 0.0,  # Default to 0 to force use of dataset costs
        # Adaptive stagnation limit (0 = use default NO_IMPROVE_LIMIT=8)
        stagnation_limit: int = 0,
    ):
        self.problem    = problem
        self.services   = services
        self.max_freq   = max_freq
        self.pop_size   = pop_size
        self.generations = generations
        self.stagnation_limit = stagnation_limit if stagnation_limit > 0 else NO_IMPROVE_LIMIT
        self._telemetry: dict = {}  # GA generation telemetry (populated by run())
        self.beta       = overcap_penalty
        self.pc_per_teu = port_cost_per_teu

        self.num_services = len(services)
        self.active_idx   = [i for i, v in enumerate(services) if v == 1]

        #pre-computed port sets from problem if available
        if hasattr(problem, 'service_port_sets'):
            self.service_port_sets = problem.service_port_sets
        else:
            self.service_port_sets = [set(svc.ports) for svc in problem.services]

        # ── Route-level demand for each service ──────────────────────
        self.route_demand = self._compute_route_demand()
        # ── Analytical starting frequency for each service ───────────
        self.init_freq    = self._analytical_frequency()

    # ------------------------------------------------------------------ #
    #  Route-level demand computation                                       #
    # ------------------------------------------------------------------ #
    def _compute_route_demand(self) -> List[float]:
        """
        For each active service, sum the weekly TEU of demands where
        BOTH origin and destination are in the service's port list.
        """
        route_demand = [0.0] * self.num_services

        # Pre-group demands by origin for faster lookup
        demand_by_origin = {}
        for d in self.problem.demands:
            demand_by_origin.setdefault(d.origin, []).append(d)

        # For each active service, check demands efficiently
        for i in self.active_idx:
            port_set = self.service_port_sets[i]
            total = 0.0

            # Only check demands originating from ports in the service
            for port in port_set:
                for d in demand_by_origin.get(port, []):
                    if d.destination in port_set:
                        total += d.weekly_teu

            route_demand[i] = total

        return route_demand

    # ------------------------------------------------------------------ #
    #  Analytical frequency estimate                                        #
    # ------------------------------------------------------------------ #
    def _analytical_frequency(self) -> List[int]:
        """
        optimal_freq_i = clamp( ceil( route_demand_i / capacity_i ), 1, max_freq )
        Services with zero demand get frequency 0 (inactive).
        """
        freq = [0] * self.num_services
        for i in self.active_idx:
            demand   = self.route_demand[i]
            capacity = self.problem.services[i].capacity or 1
            if demand > 0:
                raw  = math.ceil(demand / capacity)
                freq[i] = max(MIN_FREQ, min(self.max_freq, raw))
        return freq

    # ------------------------------------------------------------------ #
    #  Population initialisation                                            #
    # ------------------------------------------------------------------ #
    def _random_freq(self) -> List[int]:
        """
        Start near the analytical solution and jitter by ±1.
        """
        freq = list(self.init_freq)
        for i in self.active_idx:
            jitter  = random.randint(-1, 1)
            freq[i] = max(0, min(self.max_freq, freq[i] + jitter))
        return freq

    # ------------------------------------------------------------------ #
    #  Fitness                                                              #
    # ------------------------------------------------------------------ #
    def _evaluate(self, freq: List[int]) -> float:
        """
        fitness = revenue − operating_cost − fuel_cost − port_cost − overcapacity_penalty

        revenue = Σ_i min(capacity_i × freq_i, route_demand_i) × avg_rev/teu
        """
        # ── Early fleet rejection BEFORE expensive computation ──
        # Use problem fleet size if available, otherwise legacy default.
        fleet_size = 300  # legacy default
        if self.problem.fleet is not None and self.problem.fleet.total_vessels > 0:
            fleet_size = self.problem.fleet.total_vessels

        vessels_used_early = sum(
            math.ceil(self.problem.services[i].cycle_time * f / 7)
            for i, f in enumerate(freq)
            if f > 0 and self.services[i] == 1
        )
        if vessels_used_early > fleet_size:
            return -1e9  # reject immediately — skip full evaluation

        total_capacity  = 0.0
        satisfied       = 0.0
        operating_cost  = 0.0
        fuel_cost       = 0.0

        avg_rev = (
            sum(d.weekly_teu * d.revenue_per_teu for d in self.problem.demands)
            / (sum(d.weekly_teu for d in self.problem.demands) or 1.0)
        )

        for i, f in enumerate(freq):
            if f == 0 or self.services[i] == 0:
                continue
            svc       = self.problem.services[i]
            cap       = svc.capacity * f * (7 / (svc.cycle_time or 7))
            demand_i  = self.route_demand[i]
            served_i  = min(cap, demand_i)

            satisfied      += served_i
            total_capacity += cap
            operating_cost += svc.weekly_cost * f
            fuel_cost += calculate_weekly_fuel_cost(
                svc.ports,
                self.problem.distance_matrix,
                svc.vessel_class or "Post_panamax",
                svc.cycle_time or 7
            ) * f

        # Port costs for all services based on frequency
        port_cost = 0.0
        for i, f in enumerate(freq):
            if f == 0 or self.services[i] == 0:
                continue
            svc = self.problem.services[i]
            # Calculate port costs for this service based on frequency
            for p_id in svc.ports:
                port = next((p for p in self.problem.ports if p.id == p_id), None)
                if port:
                    port_hc = getattr(port, "handling_cost", 0.0)
                    port_fixed = getattr(port, "port_call_cost", 0.0)
                    port_var = getattr(port, "variable_port_call_cost", 0.0)
                    # Use actual port costs if available, otherwise default
                    handling_cost = port_hc  # Use dataset value even if zero
                    fixed_cost = port_fixed if port_fixed > 0 else 0
                    variable_cost = port_var if port_var > 0 else 0
                    # Total port cost = handling + fixed + variable per TEU
                    # TEU served is approximate: capacity * frequency * 7 / cycle_time
                    teu_served = min(svc.capacity * f * (7 / (svc.cycle_time or 7)), self.route_demand[i] if i < len(self.route_demand) else 0)
                    port_cost += teu_served * handling_cost + fixed_cost * f + teu_served * variable_cost

        revenue           = satisfied * avg_rev
        unused_cap        = max(0.0, total_capacity - satisfied)
        overcap_penalty   = self.beta * unused_cap * (operating_cost / (total_capacity or 1))
        
        num_ports = len(self.problem.ports)
        num_hubs  = max(1, int(0.1 * num_ports))

        hub_ratio = min(0.7, max(0.3, num_hubs / max(1, num_ports)))

        # Safe access to revenue_per_teu (handle empty demand list)
        avg_rev_per_teu = self.problem.demands[0].revenue_per_teu if self.problem.demands else 1000.0
        transship_cost = hub_ratio * satisfied * avg_rev_per_teu * 0.05

        # Objective Weight Calibration Audit - Log raw component values
        if CONFIG.verbose_runtime_logs:
            print(f"FREQ_GA_OBJECTIVES: revenue={revenue:.2f}, operating_cost={operating_cost:.2f}, "
                  f"fuel_cost={fuel_cost:.2f}, port_cost={port_cost:.2f}, "
                  f"transship_cost={transship_cost:.2f}, overcap_penalty={overcap_penalty:.2f}, "
                  f"satisfied_demand={satisfied:.2f}, total_capacity={total_capacity:.2f}")

        # Fleet already checked at top — no penalty needed here
        return revenue - operating_cost - transship_cost - overcap_penalty - port_cost

    # ------------------------------------------------------------------ #
    #  GA loop                                                              #
    # ------------------------------------------------------------------ #
    def run(self) -> List[int]:
        """Run the frequency-optimisation GA and return the best frequency vector.

        Telemetry (actual_generations_executed, early_stop_reason, runtime_seconds,
        best_fitness) is stored on ``self._telemetry`` for downstream consumers.
        """
        if not self.active_idx:
            self._telemetry = {
                "algorithm":                    "FrequencyGA",
                "actual_generations_executed":  0,
                "max_generations":              self.generations,
                "stagnation_limit":             self.stagnation_limit,
                "early_stop_reason":            "no_candidates",
                "best_fitness":                 0.0,
                "runtime_seconds":              0.0,
            }
            return [0] * self.num_services

        population = [self._random_freq() for _ in range(self.pop_size)]
        fitness    = [self._evaluate(p) for p in population]
        best_fitness = max(fitness)
        no_improve   = 0
        start_time = time.time()
        actual_generations = 0
        early_stop_reason  = "completed"

        for gen in range(self.generations):
            actual_generations += 1
            if time.time() - start_time > MAX_RUNTIME:
                if CONFIG.verbose_runtime_logs:
                    logger.info(f"frequency_ga_runtime_cap gen={gen} best_fitness={best_fitness}")
                early_stop_reason = "max_runtime_reached"
                break
            ranked     = sorted(zip(population, fitness), key=lambda x: x[1], reverse=True)
            population = [x[0] for x in ranked[:10]]

            while len(population) < self.pop_size:
                p1    = random.choice(ranked[:20])[0]
                child = p1.copy()
                # mutate one active service frequency
                if self.active_idx:
                    idx         = random.choice(self.active_idx)
                    child[idx]  = random.randint(0, self.max_freq)
                population.append(child)

            fitness      = [self._evaluate(p) for p in population]
            current_best = max(fitness)

            if current_best > best_fitness:
                best_fitness = current_best
                no_improve   = 0
            else:
                no_improve += 1

            if no_improve >= self.stagnation_limit:
                logger.info(f"frequency_ga_early_stop gen={gen} best_fitness={best_fitness} stagnation_limit={self.stagnation_limit}")
                early_stop_reason = "stagnation"
                break

        best = population[int(np.argmax(fitness))]
        elapsed = time.time() - start_time
        self._telemetry = {
            "algorithm":                    "FrequencyGA",
            "actual_generations_executed":  actual_generations,
            "max_generations":              self.generations,
            "stagnation_limit":             self.stagnation_limit,
            "early_stop_reason":            early_stop_reason,
            "best_fitness":                 float(best_fitness),
            "runtime_seconds":              round(elapsed, 4),
        }
        logger.info(
            "frequency_ga_complete",
            best_fitness=best_fitness,
            actual_generations=actual_generations,
            early_stop_reason=early_stop_reason,
            runtime_sec=round(elapsed, 4),
        )
        return best