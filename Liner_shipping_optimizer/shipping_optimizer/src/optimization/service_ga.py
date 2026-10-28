"""ServiceGA - exploratory selection of candidate services (binary chromosome).

This is a SEARCH HEURISTIC. Its fitness is a surrogate built from the canonical
service model (``src.network.economics``): the real rotation time, the vessels it
needs, its weekly cost at the surrogate-best frequency, and the demand it can
carry. It is never reported as profit - the network MILP and the independent
ledger decide that.

What changed versus ``service_ga_legacy.py`` (preserved verbatim):
  * capacity is ``capacity * f`` per week (the ``7 / cycle_time`` factor is gone);
  * cost is vessels*TC + f*(fuel + port calls) from the fleet specification, once
    per week (the old code charged one rotation's fuel regardless of frequency);
  * demand is shared across the services that cover it (capacity is not counted
    once per overlapping service);
  * a selection is repaired against the per-class vessel inventory, so the GA
    cannot rank an unsailable fleet above a feasible one;
  * no arbitrary cost percentages, no fabricated fuel for unknown classes.
"""

import heapq
import logging
import random
import time
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

from src.config.optimizer_config import CONFIG
from src.network.economics import estimate_best_frequency, service_models_for
from src.optimization.normalization import ObjectiveNormalizer, ObjectiveWeights

logger = logging.getLogger(__name__)

NO_IMPROVE_LIMIT = 8      # early stop threshold
MAX_RUNTIME = 90          # hard runtime cap in seconds


def _generation_record(gen: int, population, fitness, best_so_far) -> Dict:
    """One entry of ``generation_history``: the population's fitness spread after generation ``gen``
    (0 = the initial population) and the services switched on in that generation's best chromosome."""
    top = max(range(len(fitness)), key=fitness.__getitem__)
    return {"gen": gen, "best": float(fitness[top]), "mean": float(sum(fitness) / len(fitness)),
            "worst": float(min(fitness)), "best_so_far": float(best_so_far),
            "services_on": int(sum(population[top]))}


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
        # Retained for API compatibility; the surrogate keeps penalties out of profit
        alpha_unserved: float = 50.0,
        beta_overcapacity: float = 0.02,
        gamma_alignment: float = 0.3,
        # No longer used: per-port costs come from the data, never a flat default
        transship_cost_per_teu: float = 80.0,
        port_cost_per_teu: float = 0.0,
        llm_budget: int = 0,
        objective_mode: str = "legacy",
        stagnation_limit: int = 0,
        rng=None,
        np_rng=None,
    ):
        # LINER_SEED (src/utils/rng.py): own generators when given, the process-global ones otherwise
        self._rng        = rng if rng is not None else random
        self._np_rng     = np_rng if np_rng is not None else np.random
        self.problem     = problem
        self.generations = generations
        self.pop_size    = pop_size
        self.stagnation_limit = stagnation_limit if stagnation_limit > 0 else NO_IMPROVE_LIMIT
        self._telemetry: dict = {}

        self.w_profit   = getattr(problem, "profit_weight", w_profit)
        self.w_coverage = getattr(problem, "coverage_weight", w_coverage)
        self.w_cost     = getattr(problem, "cost_weight", w_cost)
        self.alpha      = alpha_unserved
        self.beta       = beta_overcapacity
        self.gamma      = gamma_alignment
        self.tc_per_teu = transship_cost_per_teu
        self.pc_per_teu = port_cost_per_teu

        self.llm_budget    = llm_budget
        self.mutation_rate = 0.15
        self.fitness_cache: dict = {}

        self.normalizer = ObjectiveNormalizer()
        self.objective_mode = objective_mode or CONFIG.objective_mode
        self.objective_weights = ObjectiveWeights(mode=self.objective_mode)

        self.num_services = len(problem.services)
        self.total_demand = sum(d.weekly_teu for d in problem.demands)

        self.models = service_models_for(problem)
        self._build_demand_index()
        self._tune_parameters()

    # ------------------------------------------------------------------ #
    #  Demand index and canonical per-service statistics                 #
    # ------------------------------------------------------------------ #
    def _build_demand_index(self):
        problem = self.problem
        self.service_port_sets = [set(svc.ports) for svc in problem.services]

        self.corridor_demand: dict = {}
        for d in problem.demands:
            key = frozenset([d.origin, d.destination])
            self.corridor_demand[key] = self.corridor_demand.get(key, 0) + d.weekly_teu

        # direct = OD with both endpoints on the service; partial = one endpoint
        self.service_direct_demand  = np.zeros(self.num_services)
        self.service_partial_demand = np.zeros(self.num_services)
        by_port: Dict[str, List[int]] = defaultdict(list)
        for i, ps in enumerate(self.service_port_sets):
            for p in ps:
                by_port[p].append(i)
        for d in problem.demands:
            o_set, d_set = set(by_port.get(d.origin, ())), set(by_port.get(d.destination, ()))
            both = o_set & d_set
            for i in both:
                self.service_direct_demand[i] += d.weekly_teu
            for i in (o_set | d_set) - both:
                self.service_partial_demand[i] += d.weekly_teu
        if np.sum(self.service_direct_demand) == 0:
            logger.warning("No services have direct demand - this may cause mutation issues")

        total_teu = self.total_demand or 1.0
        self.avg_rev_per_teu = sum(
            d.weekly_teu * d.revenue_per_teu for d in problem.demands
        ) / total_teu

        # ---- canonical per-service stats (do not depend on the selection) -------
        catalog = getattr(problem, "port_catalog", None)
        ports = dict(catalog) if catalog else {p.id: p for p in problem.ports}

        def pc(pid, name):
            v = getattr(ports.get(pid), name, 0.0)
            return float(v) if isinstance(v, (int, float)) else 0.0

        dem = [d for d in problem.demands if d.weekly_teu > 0]
        od_index = {(d.origin, d.destination): k for k, d in enumerate(dem)}
        self._od_demand = np.array([d.weekly_teu for d in dem], dtype=float)
        self._od_rev    = np.array([d.revenue_per_teu for d in dem], dtype=float)
        self._od_port   = np.array([
            pc(d.origin, "handling_cost") + pc(d.origin, "variable_port_call_cost")
            + pc(d.destination, "handling_cost") + pc(d.destination, "variable_port_call_cost")
            for d in dem], dtype=float)
        limits = [d.max_transit_days if getattr(d, "max_transit_days", None) is not None else float("inf")
                  for d in dem]

        S, K = self.num_services, len(dem)
        self._share = np.zeros((S, K), dtype=np.float32)
        self._cap_wk = np.zeros(S)           # TEU/week at the surrogate-best frequency
        self._fixed = np.zeros(S)            # weekly vessel+fuel+port-call cost at that frequency
        self._vessels = np.zeros(S, dtype=int)
        self._fstar = np.zeros(S, dtype=int)
        self._margin = np.zeros(S)
        self._class: List[Optional[str]] = [None] * S
        for i, m in enumerate(self.models):
            if m is None:
                continue
            self._class[i] = m.vessel_class
            ks = []
            for a in m.ports:
                for b in m.ports:
                    if a == b:
                        continue
                    k = od_index.get((a, b))
                    if k is None:
                        continue
                    ride = m.ride(a, b)
                    if ride is not None and ride[1] <= limits[k] + 1e-9:
                        ks.append(k)
            if not ks:
                continue
            direct = float(self._od_demand[ks].sum())
            self._share[i, ks] = (self._od_demand[ks] / direct).astype(np.float32)
            net_rev = float(((self._od_rev[ks] - self._od_port[ks]) * self._od_demand[ks]).sum() / direct)
            f, margin = estimate_best_frequency(m, direct, net_rev)
            self._fstar[i], self._margin[i] = f, margin
            if f > 0:
                self._cap_wk[i] = m.capacity_teu * f
                self._fixed[i] = m.weekly_fixed_cost(f)
                self._vessels[i] = m.vessels(f)
        fleet = getattr(problem, "fleet", None)
        self._inventory = {c.vessel_class: int(c.quantity) for c in fleet.classes} if fleet else {}
        with np.errstate(divide="ignore", invalid="ignore"):
            self._efficiency = np.where(self._vessels > 0, self._margin / np.maximum(self._vessels, 1), -np.inf)

    # ------------------------------------------------------------------ #
    #  Adaptive parameter tuning (heuristic — no LLM)                    #
    # ------------------------------------------------------------------ #
    def _tune_parameters(self):
        n = self.num_services
        if n < 100:
            self.pop_size, self.mutation_rate = 60, 0.10
        elif n < 500:
            self.pop_size, self.mutation_rate = 100, 0.15
        else:
            self.pop_size, self.mutation_rate = 140, 0.20

    # ------------------------------------------------------------------ #
    #  Fleet feasibility (per class) — repair                            #
    # ------------------------------------------------------------------ #
    def repair(self, services: List[int]) -> List[int]:
        """Drop the least efficient selected services until the vessels they need fit
        every class's real inventory; services without a usable model or with no
        positive surrogate frequency are not operated. Deterministic."""
        sel = [i for i, v in enumerate(services) if v == 1 and self._vessels[i] > 0]
        sel.sort(key=lambda i: -self._efficiency[i])
        used: Dict[str, int] = defaultdict(int)
        keep = []
        for i in sel:
            cls = self._class[i]
            if used[cls] + int(self._vessels[i]) <= self._inventory.get(cls, 0):
                used[cls] += int(self._vessels[i])
                keep.append(i)
        out = [0] * len(services)
        for i in keep:
            out[i] = 1
        return out

    # ------------------------------------------------------------------ #
    #  Smart initialisation                                              #
    # ------------------------------------------------------------------ #
    def _random_solution(self) -> List[int]:
        scores = self.service_direct_demand + 0.3 * self.service_partial_demand
        scores = np.where(self._cap_wk > 0, scores, 0.0)       # only operable services
        total  = scores.sum()
        if total <= 0 or self.num_services == 0:
            return [0] * self.num_services
        probs = scores / total
        n_pos = int((probs > 0).sum())
        n_select = self._rng.randint(max(5, self.num_services // 20), max(10, self.num_services // 8))
        n_select = min(n_select, n_pos)
        selected = self._np_rng.choice(self.num_services, size=n_select, replace=False, p=probs)
        sol = [0] * self.num_services
        for idx in selected:
            sol[idx] = 1
        return sol

    # ------------------------------------------------------------------ #
    #  Fitness (surrogate; NOT verified profit)                          #
    # ------------------------------------------------------------------ #
    def surrogate(self, services: List[int]) -> Dict[str, float]:
        """Surrogate weekly economics of the (repaired) selection."""
        rep = self.repair(services)
        sel = np.fromiter((i for i, v in enumerate(rep) if v == 1), dtype=int)
        if sel.size == 0:
            return dict(selection=rep, served=0.0, revenue=0.0, fixed=0.0, port=0.0,
                        profit=0.0, coverage=0.0, vessels=0, n=0)
        supply = (self._cap_wk[sel, None] * self._share[sel]).sum(axis=0)
        served_od = np.minimum(self._od_demand, supply)
        served = float(served_od.sum())
        revenue = float((served_od * self._od_rev).sum())
        port = float((served_od * self._od_port).sum())
        fixed = float(self._fixed[sel].sum())
        return dict(selection=rep, served=served, revenue=revenue, fixed=fixed, port=port,
                    profit=revenue - fixed - port,
                    coverage=served / (self.total_demand or 1.0),
                    vessels=int(self._vessels[sel].sum()), n=int(sel.size))

    def evaluate(self, services: List[int]) -> float:
        """Objective = w1*profit + w2*coverage - w3*cost over NORMALISED components."""
        if not isinstance(services, list):
            return -1e12
        weight_tuple = (self.w_profit, self.w_coverage, self.w_cost)
        key = bytes(services) + str(weight_tuple).encode()
        if key in self.fitness_cache:
            return self.fitness_cache[key]
        if not any(services):
            return -1e12

        s = self.surrogate(services)
        if s["n"] == 0:
            return -1e12

        all_components = {
            "profit": s["profit"], "coverage": s["coverage"], "cost": s["fixed"],
            "revenue": s["revenue"], "fuel_cost": 0.0, "port_cost": s["port"],
            "unserved_penalty": 0.0, "overcap_penalty": 0.0, "transship_cost": 0.0,
            "alignment_penalty": 0.0, "negative_service_penalty": 0.0,
        }
        normalized = self.normalizer.normalize_objective_components(all_components)
        if self.objective_mode == "legacy":
            fitness = (self.w_profit * normalized["profit"]
                       + self.w_coverage * normalized["coverage"]
                       - self.w_cost * normalized["cost"])
        else:
            fitness = self.objective_weights.calculate_weighted_score(normalized)
        self.fitness_cache[key] = fitness
        return fitness

    # ------------------------------------------------------------------ #
    #  Helper methods for weight calculations                           #
    # ------------------------------------------------------------------ #
    def _get_actual_weight(self, component: str) -> float:
        return {"profit": self.w_profit, "coverage": self.w_coverage, "cost": self.w_cost}.get(component, 0.0)

    def _calculate_weight_contributions(self, normalized: Dict[str, float]) -> Dict[str, float]:
        raw, total = {}, 0.0
        for component in ["profit", "coverage", "cost"]:
            if component in normalized:
                weight = self._get_actual_weight(component)
                contribution = -weight * normalized[component] if component == "cost" \
                    else weight * normalized[component]
                raw[component] = contribution
                total += abs(contribution)
        if total > 0:
            return {c: abs(v) / total * 100.0 for c, v in raw.items()}
        return {c: 100.0 / len(raw) for c in raw} if raw else {}

    # ------------------------------------------------------------------ #
    #  GA operators                                                      #
    # ------------------------------------------------------------------ #
    def _mutate(self, sol: List[int]) -> List[int]:
        child = sol.copy()
        if self._rng.random() < 0.5:
            # activate a high-demand OPERABLE service that is currently off
            off_idx = [i for i, v in enumerate(child) if v == 0 and self._cap_wk[i] > 0]
            if off_idx:
                scores = [self.service_direct_demand[i] for i in off_idx]
                total = sum(scores)
                if total > 0:
                    idx = self._rng.choices(off_idx, weights=[s / total for s in scores])[0]
                else:
                    idx = self._rng.choice(off_idx)
                child[idx] = 1
        else:
            if self.num_services:
                idx = self._rng.randint(0, self.num_services - 1)
                child[idx] = 1 - child[idx]
        return child

    def _crossover(self, p1: List[int], p2: List[int]) -> List[int]:
        if len(p1) < 3:
            return list(p1)
        point = self._rng.randint(1, len(p1) - 2)
        return p1[:point] + p2[point:]

    # ------------------------------------------------------------------ #
    #  Main GA loop                                                      #
    # ------------------------------------------------------------------ #
    def run(self, seed_solution: list = None) -> List[int]:
        """Run the service-selection GA and return the best (fleet-repaired)
        binary chromosome. Telemetry is stored on ``self._telemetry``."""
        population = [self._random_solution() for _ in range(self.pop_size)]
        if seed_solution and len(seed_solution) == self.num_services:
            population[0] = list(seed_solution)
        fitness      = [self.evaluate(p) for p in population]
        best_fitness = max(fitness)
        no_improve   = 0
        start_time   = time.time()
        actual_generations = 0
        early_stop_reason  = "completed"
        # per-generation record for the dashboard's playback; read-only (no RNG draw, no effect on selection)
        history = [_generation_record(0, population, fitness, best_fitness)]

        for gen in range(self.generations):
            actual_generations += 1
            if time.time() - start_time > MAX_RUNTIME:
                early_stop_reason = "max_runtime_reached"
                break
            ranked = heapq.nlargest(10, zip(population, fitness), key=lambda x: x[1])
            elite = [x[0] for x in ranked]
            population = elite.copy()
            pool = ranked[:20]
            while len(population) < self.pop_size:
                p1 = self._rng.choice(pool)[0]
                p2 = self._rng.choice(pool)[0]
                child = self._crossover(p1, p2)
                if self._rng.random() < self.mutation_rate:
                    child = self._mutate(child)
                population.append(child)

            fitness = [self.evaluate(p) for p in population]
            current_best = max(fitness)
            if current_best > best_fitness:
                best_fitness, no_improve = current_best, 0
            else:
                no_improve += 1
            history.append(_generation_record(gen + 1, population, fitness, best_fitness))
            if no_improve >= self.stagnation_limit:
                early_stop_reason = "stagnation"
                break

        best = self.repair(population[int(np.argmax(fitness))])
        elapsed = time.time() - start_time
        self._telemetry = {
            "algorithm":                    "ServiceGA",
            "actual_generations_executed":  actual_generations,
            "max_generations":              self.generations,
            "stagnation_limit":             self.stagnation_limit,
            "early_stop_reason":            early_stop_reason,
            "best_fitness":                 float(best_fitness),
            "runtime_seconds":              round(elapsed, 4),
            "generation_history":           history,
        }
        logger.info("service_ga_complete | selected=%d best_fitness=%s generations=%d stop=%s runtime=%.2fs",
                    sum(best), best_fitness, actual_generations, early_stop_reason, elapsed)
        return best
