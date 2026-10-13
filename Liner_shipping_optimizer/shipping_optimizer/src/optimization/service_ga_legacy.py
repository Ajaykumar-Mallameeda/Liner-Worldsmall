"""LEGACY COPY (verbatim) of the pre-network-model implementation, kept for reference.
Not imported by the pipeline. Superseded by src/network/* (see reports/overnight_tasks_2_to_4).
"""
import random
import logging
import heapq
import numpy as np
import time
from collections import defaultdict
from typing import List, Optional, Dict
from src.utils.fuel_cost import (
    calculate_weekly_fuel_cost,
    _normalize_weather_speed_factor,
)
from src.optimization.normalization import ObjectiveNormalizer, ObjectiveWeights
from src.config.optimizer_config import CONFIG

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------
# IP-2 (Phase 7) — local-only fuel-cost kwarg builder
# --------------------------------------------------------------------
# This helper is structurally identical to
# ``maritime.optimizer_bridge.fuel_cost_kwargs`` but is duplicated
# here (rather than imported) so the optimizer package has no
# compile-time dependency on the maritime package. The
# network-isolation boundary tests in
# ``tests/architecture/test_network_isolation.py`` enforce that no
# ``src/`` module may import ``maritime.*``. The two helpers are
# covered by the IP-2 test suite in
# ``tests/maritime/test_phase7_integration.py``.
def _maritime_fuel_cost_kwargs(problem) -> Dict:
    if problem is None:
        return {}
    mf = getattr(problem, "maritime_features", None)
    if mf is None:
        return {}
    wsf = getattr(mf, "weather_speed_factor", None)
    if wsf is None:
        return {}
    safe = _normalize_weather_speed_factor(wsf)
    if safe is None:
        return {}
    return {"weather_speed_factor": safe}


NO_IMPROVE_LIMIT = 8      # Reduced early stop threshold
MAX_RUNTIME = 90          # Hard runtime cap in seconds


class ServiceGA:
    # ------------------------------------------------------------------ #
    #  Construction                                                      #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        problem,
        pop_size: int = 80,
        generations: int = 120,
        # Multi-objective weights (legacy for backward compatibility)
        w_profit: float = 0.5,
        w_coverage: float = 0.4,
        w_cost: float = 0.1,
        # Penalty coefficients
        alpha_unserved: float = 50.0,       # $/TEU unserved
        beta_overcapacity: float = 0.02,    # fraction of unused capacity cost
        gamma_alignment: float = 0.3,       # penalty for zero-demand services
        # Transshipment / port cost pass-through estimates
        transship_cost_per_teu: float = 80.0,
        port_cost_per_teu: float = 0.0,  # Default to 0 to force use of dataset costs
        # LLM budget
        llm_budget: int = 0,                # set >0 to enable LLM assist
        # Objective mode
        objective_mode: str = "legacy",    # "legacy" or "profit_first"
        # Adaptive stagnation limit (0 = use default NO_IMPROVE_LIMIT=8)
        stagnation_limit: int = 0,
    ):
        self.problem     = problem
        self.generations = generations
        self.pop_size    = pop_size
        self.stagnation_limit = stagnation_limit if stagnation_limit > 0 else NO_IMPROVE_LIMIT
        self._telemetry: dict = {}  # GA generation telemetry (populated by run())

        # Weights & penalties - use problem weights if available
        self.w_profit   = getattr(problem, "profit_weight", w_profit)
        self.w_coverage = getattr(problem, "coverage_weight", w_coverage)
        self.w_cost     = getattr(problem, "cost_weight", w_cost)
        self.alpha      = alpha_unserved
        self.beta       = beta_overcapacity
        self.gamma      = gamma_alignment
        self.tc_per_teu = transship_cost_per_teu
        self.pc_per_teu = port_cost_per_teu

        self.llm_budget   = llm_budget
        self.mutation_rate = 0.15
        self.fitness_cache: dict = {}

        # Objective normalization and weight configuration
        self.normalizer = ObjectiveNormalizer()
        self.objective_mode = objective_mode or CONFIG.objective_mode
        self.objective_weights = ObjectiveWeights(mode=self.objective_mode)

        self.num_services = len(problem.services)
        self.total_demand = sum(d.weekly_teu for d in problem.demands)

        # ── Pre-build demand index: service_idx → relevant OD demand ──
        self._build_demand_index()

        # ── Adaptive parameter tuning (pure heuristic, no LLM) ────────
        self._tune_parameters()

    # ------------------------------------------------------------------ #
    #  Demand index                                                         #
    # ------------------------------------------------------------------ #
    def _build_demand_index(self):
        # Pre-compute port sets for all services to avoid repeated set creation
        self.service_port_sets = [set(svc.ports) for svc in self.problem.services]

        # Use frozenset for faster corridor lookup (hashable, O(1) access)
        self.corridor_demand: dict = {}
        for d in self.problem.demands:
            key = frozenset([d.origin, d.destination])  # frozenset is hashable
            self.corridor_demand[key] = self.corridor_demand.get(key, 0) + d.weekly_teu

        # service_direct_demand[i] = TEU directly served by service i
        # service_partial_demand[i] = TEU where only one endpoint matches
        self.service_direct_demand  = np.zeros(self.num_services)
        self.service_partial_demand = np.zeros(self.num_services)

        # Vectorized approach: iterate demands once, update all relevant services
        for d in self.problem.demands:
            o, d_port = d.origin, d.destination
            teu = d.weekly_teu

            # Find services that cover this corridor
            for i, port_set in enumerate(self.service_port_sets):
                if o in port_set and d_port in port_set:
                    self.service_direct_demand[i] += teu
                elif o in port_set or d_port in port_set:
                    self.service_partial_demand[i] += teu

        # Debug: ensure at least some services have demand
        if np.sum(self.service_direct_demand) == 0:
            logger.warning("No services have direct demand - this may cause mutation issues")

        # Revenue per TEU (weighted average across demands)
        total_teu = self.total_demand or 1.0
        self.avg_rev_per_teu = sum(
            d.weekly_teu * d.revenue_per_teu for d in self.problem.demands
        ) / total_teu

        logger.debug(
            "demand_index_built",
            services=self.num_services,
            total_demand=self.total_demand,
        )

    # ------------------------------------------------------------------ #
    #  Adaptive parameter tuning (heuristic — no LLM)                    #
    # ------------------------------------------------------------------ #
    def _tune_parameters(self):
        n = self.num_services
        if n < 100:
            self.pop_size      = 60
            self.mutation_rate = 0.10
        elif n < 500:
            self.pop_size      = 100
            self.mutation_rate = 0.15
        else:
            self.pop_size      = 140
            self.mutation_rate = 0.20
        logger.debug("ga_params_tuned", pop_size=self.pop_size, mut=self.mutation_rate)

    # ------------------------------------------------------------------ #
    #  Smart initialisation                                              #
    # ------------------------------------------------------------------ #
    def _random_solution(self) -> List[int]:
        scores = self.service_direct_demand + 0.3 * self.service_partial_demand
        total  = scores.sum() or 1.0
        probs  = scores / total          # probability proportional to demand

        n_select = random.randint(
            max(5, self.num_services // 20),
            max(10, self.num_services // 8),
        )
        selected = np.random.choice(
            self.num_services, size=min(n_select, self.num_services),
            replace=False, p=probs
        )
        sol = [0] * self.num_services
        for idx in selected:
            sol[idx] = 1
        return sol

    # ------------------------------------------------------------------ #
    #  Fitness (demand-driven, multi-objective)                          #
    # ------------------------------------------------------------------ #
    def evaluate(self, services: List[int]) -> float:
        """
        Objective = w1·Profit + w2·Coverage − w3·Cost

        Profit = Revenue − OperatingCost − TransshipCost − PortCost − Penalties
        Revenue  = Σ min(svc.capacity, direct_demand_on_route) × rev_per_teu
        Coverage = satisfied_demand / total_demand

        """
        if not isinstance(services, list):
            return -1e12

        # Use bytes for faster cache key creation - include weights to prevent stale cache
        weight_tuple = (self.w_profit, self.w_coverage, self.w_cost)
        key = bytes(services) + str(weight_tuple).encode()
        if key in self.fitness_cache:
            return self.fitness_cache[key]

        selected_idx = [i for i, v in enumerate(services) if v == 1]
        if not selected_idx:
            return -1e12

        # ── Revenue: demand-driven ─────────────────────────────────────
        satisfied_demand = 0.0
        operating_cost   = 0.0
        fuel_cost        = 0.0
        revenue = 0.0
        port_cost        = 0.0
        alignment_penalty = 0.0
        negative_service_penalty = 0.0

        covered_corridors: dict = {}   # corridor → TEU satisfied

        for i in selected_idx:
            svc    = self.problem.services[i]
            direct = self.service_direct_demand[i]

            
            # ── Capacity adjusted by cycle time ─────────────────────
            effective_capacity = svc.capacity * (7 / (svc.cycle_time or 7))
            served = min(effective_capacity, direct)

            # ── Accumulate satisfied demand ─────────────────────────
            satisfied_demand += served

            # ── Yield-based revenue ───────────────────────────
            yield_factor = 0.6 + 0.4 * (served / (effective_capacity or 1))
            revenue += served * self.avg_rev_per_teu * yield_factor

            # Track corridor coverage (for per-corridor cap)
            port_set = self.service_port_sets[i]
            for corridor_key, teu in self.corridor_demand.items():
                o, d = tuple(corridor_key)
                if o in port_set and d in port_set:
                    covered_corridors[(o, d)] = (
                        covered_corridors.get((o, d), 0) + svc.capacity
                    )

            # Operating cost
            operating_cost += svc.weekly_cost

            # Fuel cost based on vessel class and distance
            fuel_cost += calculate_weekly_fuel_cost(
                svc.ports,
                self.problem.distance_matrix,
                svc.vessel_class or "Post_panamax",
                svc.cycle_time or 7,
                **_maritime_fuel_cost_kwargs(self.problem),
            )

            # Port handling cost (per port call)
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
                    port_cost += served * handling_cost + fixed_cost + served * variable_cost

            # Demand-alignment penalty: penalise services with zero direct demand
            if direct == 0:
                alignment_penalty += self.gamma * svc.weekly_cost

            # Negative service penalty: penalize persistently loss-making services
            service_revenue = served * self.avg_rev_per_teu

            # Calculate actual service costs including fuel
            service_fuel_cost = calculate_weekly_fuel_cost(
                svc.ports,
                self.problem.distance_matrix,
                svc.vessel_class or "Post_panamax",
                svc.cycle_time or 7,
                **_maritime_fuel_cost_kwargs(self.problem),
            )
            service_cost = svc.weekly_cost + service_fuel_cost + (served * port_hc if 'port_hc' in locals() else 0)
            service_margin = service_revenue - service_cost

            if service_margin < 0:
                # Apply stronger penalty for negative margin services
                margin_pct = service_margin / service_cost if service_cost > 0 else -1.0

                # Enhanced penalty structure for P2
                if margin_pct < -0.3:  # More than 30% loss
                    negative_penalty = abs(service_margin) * 1.0  # 100% of loss
                elif margin_pct < -0.2:  # 20-30% loss
                    negative_penalty = abs(service_margin) * 0.7  # 70% of loss
                elif margin_pct < -0.1:  # 10-20% loss
                    negative_penalty = abs(service_margin) * 0.5  # 50% of loss
                else:  # Small loss
                    negative_penalty = abs(service_margin) * 0.2  # 20% of loss

                # Increased cap for stronger impact
                negative_penalty = min(negative_penalty, 100000)  # Max $100k penalty
                negative_service_penalty += negative_penalty

        # Cap satisfied demand at total
        satisfied_demand = min(satisfied_demand, self.total_demand)
        unserved_demand  = max(0.0, self.total_demand - satisfied_demand)

        # ── Revenue ────────────────────────────────────────────────────
       # yield_factor = 0.6 + 0.4 * (satisfied_demand / (total_capacity or 1))
        #revenue = satisfied_demand * self.avg_rev_per_teu * yield_factor

        # ── Transshipment cost (estimated: 20% of satisfied flows use 1 hub) ─
        num_ports = len(self.problem.ports)
        num_hubs  = max(1, int(0.1 * num_ports))  # approx hubs

        hub_ratio = min(0.7, max(0.3, num_hubs / num_ports))

        transship_cost = hub_ratio * satisfied_demand * self.tc_per_teu

        # ── Penalties ──────────────────────────────────────────────────
        # Unserved demand penalty
        unserved_penalty  = self.alpha * unserved_demand
        # Overcapacity penalty (unused capacity costs money)
        total_capacity    = sum(self.problem.services[i].capacity for i in selected_idx)
        unused_cap        = max(0.0, total_capacity - satisfied_demand)
        overcap_penalty   = self.beta * unused_cap * (operating_cost / (total_capacity or 1))

        profit = (
            revenue
            - operating_cost
            - fuel_cost
            - transship_cost
            - port_cost
            - unserved_penalty
            - overcap_penalty
            - alignment_penalty
            - negative_service_penalty
        )

        coverage = satisfied_demand / (self.total_demand or 1.0)

        # Gather all objective components for normalization
        all_components = {
            'profit': profit,
            'coverage': coverage,
            'cost': operating_cost,
            'revenue': revenue,
            'fuel_cost': fuel_cost,
            'port_cost': port_cost,
            'unserved_penalty': unserved_penalty,
            'overcap_penalty': overcap_penalty,
            'transship_cost': transship_cost,
            'alignment_penalty': alignment_penalty,
            'negative_service_penalty': negative_service_penalty,
        }

        # Normalize components
        normalized = self.normalizer.normalize_objective_components(all_components)

        # Calculate weighted score using configured weights
        if self.objective_mode == "legacy":
            # Use legacy weights for backward compatibility
            # Apply weights directly without additional scaling to prevent dominance
            fitness = (
                self.w_profit * normalized['profit']
                + self.w_coverage * normalized['coverage']
                - self.w_cost * normalized['cost']
            )
        else:
            # Use new weight system
            fitness = self.objective_weights.calculate_weighted_score(normalized)

        # Get weight contributions for transparency
        contributions = self._calculate_weight_contributions(normalized)

        # Log detailed objective information
        if CONFIG.verbose_runtime_logs:
            print("\n=== OBJECTIVE FUNCTION BREAKDOWN ===")
            print(f"Objective Mode: {self.objective_mode.upper()}")
            print("\nRaw Components:")
            for name, value in all_components.items():
                print(f"  {name}: {value:,.2f}")

            print("\nNormalized Components:")
            for name, value in normalized.items():
                print(f"  {name}: {value:.6f}")

            print("\nWeight Contributions:")
            for name, percentage in contributions.items():
                weight = self._get_actual_weight(name)
                print(f"  {name}: {percentage:.1f}% (weight: {weight})")

            print(f"\nFinal Fitness Score: {fitness:,.2f}")
            print("=" * 35)

        self.fitness_cache[key] = fitness
        return fitness

    # ------------------------------------------------------------------ #
    #  Helper methods for weight calculations                           #
    # ------------------------------------------------------------------ #
    def _get_actual_weight(self, component: str) -> float:
        """Get the actual weight being used for a component."""
        if component == 'profit':
            return self.w_profit
        elif component == 'coverage':
            return self.w_coverage
        elif component == 'cost':
            return self.w_cost
        else:
            return 0.0

    def _calculate_weight_contributions(self, normalized: Dict[str, float]) -> Dict[str, float]:
        """Calculate actual weight contributions based on applied weights."""
        contributions = {}
        total_score = 0.0
        raw_contributions = {}

        # Use the same calculation as in fitness
        for component in ['profit', 'coverage', 'cost']:
            if component in normalized:
                value = normalized[component]
                weight = self._get_actual_weight(component)

                if component == 'cost':
                    # Cost is subtracted
                    contribution = -weight * value
                else:
                    contribution = weight * value

                raw_contributions[component] = contribution
                total_score += abs(contribution)

        # Convert to percentages
        if total_score > 0:
            for component, contribution in raw_contributions.items():
                contributions[component] = (abs(contribution) / total_score) * 100
        else:
            # If no score, distribute equally
            equal_share = 100.0 / len(raw_contributions)
            contributions = {c: equal_share for c in raw_contributions}

        return contributions

    # ------------------------------------------------------------------ #
    #  GA operators                                                      #
    # ------------------------------------------------------------------ #
    def _mutate(self, sol: List[int]) -> List[int]:
        child = sol.copy()
        # flip a random bit; bias toward activating high-demand services
        if random.random() < 0.5:
            # activate a high-demand service that is currently off
            off_idx = [i for i, v in enumerate(child) if v == 0]
            if off_idx:
                scores = [self.service_direct_demand[i] for i in off_idx]
                total  = sum(scores)
                if total > 0:
                    probs = [s / total for s in scores]
                    idx = random.choices(off_idx, weights=probs)[0]
                else:
                    # Fallback: use partial demand if available, otherwise random
                    partial_scores = [self.service_partial_demand[i] for i in off_idx]
                    if sum(partial_scores) > 0:
                        partial_total = sum(partial_scores)
                        partial_probs = [s / partial_total for s in partial_scores]
                        idx = random.choices(off_idx, weights=partial_probs)[0]
                    else:
                        idx = random.choice(off_idx)
                child[idx] = 1
        else:
            idx = random.randint(0, self.num_services - 1)
            child[idx] = 1 - child[idx]
        return child

    @staticmethod
    def _crossover(p1: List[int], p2: List[int]) -> List[int]:
        point = random.randint(1, len(p1) - 2)
        return p1[:point] + p2[point:]

    # ------------------------------------------------------------------ #
    #  Main GA loop                                                      #
    # ------------------------------------------------------------------ #
    def run(self, seed_solution: list = None) -> List[int]:
        """Run the service-selection GA and return the best binary chromosome.

        Telemetry (actual_generations_executed, early_stop_reason, runtime_seconds,
        best_fitness) is stored on ``self._telemetry`` for downstream consumers.
        """
        population = [self._random_solution() for _ in range(self.pop_size)]
        if seed_solution and len(seed_solution) == self.num_services:
            population[0] = list(seed_solution)
            logger.debug("ga_seeded_with_previous_best")
        fitness    = [self.evaluate(p) for p in population]
        best_fitness = max(fitness)
        no_improve   = 0
        start_time = time.time()
        actual_generations = 0
        early_stop_reason  = "completed"

        for gen in range(self.generations):
            actual_generations += 1
            if time.time() - start_time > MAX_RUNTIME:
                if CONFIG.verbose_runtime_logs:
                    logger.info(f"ga_runtime_cap gen={gen} best_fitness={best_fitness}")
                early_stop_reason = "max_runtime_reached"
                break
            #heapq for faster elite selection
            ranked = heapq.nlargest(10, zip(population, fitness), key=lambda x: x[1])
            elite  = [x[0] for x in ranked]
            population = elite.copy()

            while len(population) < self.pop_size:
                p1 = random.choice(ranked[:20])[0]
                p2 = random.choice(ranked[:20])[0]
                child = self._crossover(p1, p2)
                if random.random() < self.mutation_rate:
                    child = self._mutate(child)
                population.append(child)

            fitness      = [self.evaluate(p) for p in population]
            current_best = max(fitness)

            if current_best > best_fitness:
                best_fitness = current_best
                no_improve   = 0
            else:
                no_improve += 1

            if no_improve >= self.stagnation_limit:
                logger.info(f"ga_early_stop gen={gen} best_fitness={best_fitness} stagnation_limit={self.stagnation_limit}")
                early_stop_reason = "stagnation"
                break

        best = population[int(np.argmax(fitness))]
        elapsed = time.time() - start_time
        self._telemetry = {
            "algorithm":                    "ServiceGA",
            "actual_generations_executed":  actual_generations,
            "max_generations":              self.generations,
            "stagnation_limit":             self.stagnation_limit,
            "early_stop_reason":            early_stop_reason,
            "best_fitness":                 float(best_fitness),
            "runtime_seconds":              round(elapsed, 4),
        }
        logger.info(
            "service_ga_complete",
            services_selected=sum(best),
            best_fitness=best_fitness,
            actual_generations=actual_generations,
            early_stop_reason=early_stop_reason,
            runtime_sec=round(elapsed, 4),
        )
        return best