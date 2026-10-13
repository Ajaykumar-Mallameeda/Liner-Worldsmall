"""FrequencyGA - weekly departures per selected service, from real rotation times.

``f_i`` is the number of departures per week of service ``i``. Its domain is not a
constant: a service whose rotation takes ``T`` days needs ``ceil(T * f / 7)``
vessels, so the largest sustainable frequency is ``floor(7 * N / T)`` for the
vessels ``N`` its class owns (``ServiceModel.max_departures``), further bounded by
the demand that could fill the departures. ``f = 0`` means "not operated" and is
never rounded up to one.

Fitness is a surrogate of weekly operating margin from the canonical service model
(revenue of the carried TEU minus vessels*TC + f*(fuel + port calls)); it is a
search heuristic, not verified profit. A frequency vector that needs more vessels
of a class than exist is repaired, not ranked.

Retired hard-coded values (kept as comments for history):
    MAX_FREQ = 3   # maximum sailings per week per service
    MIN_FREQ = 1
The previous implementation is preserved verbatim in ``frequency_ga_legacy.py``.
"""

import logging
import math
import random
import time
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

from src.config.optimizer_config import CONFIG
from src.network.economics import estimate_best_frequency, service_models_for

logger = logging.getLogger(__name__)

NO_IMPROVE_LIMIT = 8      # early stop threshold
MAX_RUNTIME = 90          # hard runtime cap in seconds

# MAX_FREQ = 3          # RETIRED: frequency is bounded by real time and vessel inventory
# MIN_FREQ = 1          # RETIRED: 0 departures is a valid, explicit decision


class FrequencyGA:
    def __init__(
        self,
        problem,
        services: List[int],              # binary mask from ServiceGA
        max_freq: Optional[int] = None,   # optional extra cap; None = derived from real times
        pop_size: int = 40,
        generations: int = 60,
        overcap_penalty: float = 0.015,   # kept for API compatibility (not used)
        port_cost_per_teu: float = 0.0,   # kept for API compatibility (data costs are used)
        stagnation_limit: int = 0,
        rng=None,
    ):
        self._rng       = rng if rng is not None else random      # LINER_SEED: own generator when given
        self.problem    = problem
        self.services   = services
        self.max_freq   = max_freq
        self.pop_size   = pop_size
        self.generations = generations
        self.stagnation_limit = stagnation_limit if stagnation_limit > 0 else NO_IMPROVE_LIMIT
        self._telemetry: dict = {}
        self.beta       = overcap_penalty
        self.pc_per_teu = port_cost_per_teu

        self.num_services = len(services)
        self.models = service_models_for(problem)
        # only selected services that can actually be modelled can be scheduled
        self.active_idx = [i for i, v in enumerate(services)
                           if v == 1 and i < len(self.models) and self.models[i] is not None]

        if hasattr(problem, "service_port_sets"):
            self.service_port_sets = problem.service_port_sets
        else:
            self.service_port_sets = [set(svc.ports) for svc in problem.services]

        fleet = getattr(problem, "fleet", None)
        self._inventory = {c.vessel_class: int(c.quantity) for c in fleet.classes} if fleet else {}

        self.route_demand = self._compute_route_demand()
        self._prepare_service_stats()
        self.init_freq = self._analytical_frequency()

    # ------------------------------------------------------------------ #
    def _compute_route_demand(self) -> List[float]:
        """Per active service: weekly TEU of demands with BOTH ends on its rotation
        and a ride within the demand's transit-time limit."""
        route_demand = [0.0] * self.num_services
        self._net_rev = [0.0] * self.num_services           # USD/TEU net of port charges
        catalog = getattr(self.problem, "port_catalog", None)
        ports = dict(catalog) if catalog else {p.id: p for p in self.problem.ports}

        def pc(pid, name):
            v = getattr(ports.get(pid), name, 0.0)
            return float(v) if isinstance(v, (int, float)) else 0.0

        by_origin: Dict[str, list] = {}
        for d in self.problem.demands:
            if d.weekly_teu > 0:
                by_origin.setdefault(d.origin, []).append(d)
        for i in self.active_idx:
            m = self.models[i]
            total = rev = 0.0
            for a in m.ports:
                for d in by_origin.get(a, ()):
                    if d.destination in m.ports and d.destination != a:
                        ride = m.ride(a, d.destination)
                        lim = getattr(d, "max_transit_days", None)
                        if ride is None or (lim is not None and ride[1] > lim + 1e-9):
                            continue
                        total += d.weekly_teu
                        port = (pc(a, "handling_cost") + pc(a, "variable_port_call_cost")
                                + pc(d.destination, "handling_cost")
                                + pc(d.destination, "variable_port_call_cost"))
                        rev += d.weekly_teu * (d.revenue_per_teu - port)
            route_demand[i] = total
            self._net_rev[i] = rev / total if total > 0 else 0.0
        return route_demand

    def _prepare_service_stats(self):
        """Per active service: frequency ceiling from real time + inventory + demand."""
        self.f_cap = [0] * self.num_services
        for i in self.active_idx:
            m = self.models[i]
            f = m.max_departures(self._inventory.get(m.vessel_class))
            if self.route_demand[i] > 0:
                f = min(f, int(math.ceil(self.route_demand[i] / m.capacity_teu)))
            if self.max_freq is not None:
                f = min(f, int(self.max_freq))
            self.f_cap[i] = max(0, f)

    def _analytical_frequency(self) -> List[int]:
        """Surrogate-best frequency per service (0 when no frequency is profitable)."""
        freq = [0] * self.num_services
        for i in self.active_idx:
            if self.route_demand[i] <= 0 or self.f_cap[i] <= 0:
                continue
            f, _ = estimate_best_frequency(self.models[i], self.route_demand[i], self._net_rev[i],
                                           vessel_budget=self._inventory.get(self.models[i].vessel_class))
            freq[i] = min(f, self.f_cap[i])
        return freq

    # ------------------------------------------------------------------ #
    #  Economics of one service at frequency f (surrogate)                 #
    # ------------------------------------------------------------------ #
    def _margin(self, i: int, f: int) -> float:
        if f <= 0:
            return 0.0
        m = self.models[i]
        served = min(m.capacity_teu * f, self.route_demand[i])
        return served * self._net_rev[i] - m.weekly_fixed_cost(f)

    def vessels_needed(self, freq: List[int]) -> Dict[str, int]:
        used: Dict[str, int] = defaultdict(int)
        for i in self.active_idx:
            if freq[i] > 0:
                used[self.models[i].vessel_class] += self.models[i].vessels(freq[i])
        return dict(used)

    def repair(self, freq: List[int]) -> List[int]:
        """Clip to each service's ceiling and lower the frequency of the least
        valuable departures until every class fits its real inventory."""
        out = list(freq)
        for i in range(self.num_services):
            if i not in self.active_idx:
                out[i] = 0
            else:
                out[i] = max(0, min(int(out[i]), self.f_cap[i]))
        for _ in range(10_000):
            used = self.vessels_needed(out)
            over = {c for c, n in used.items() if n > self._inventory.get(c, 0)}
            if not over:
                break
            best, best_ratio = None, None
            for i in self.active_idx:
                f = out[i]
                if f <= 0 or self.models[i].vessel_class not in over:
                    continue
                freed = self.models[i].vessels(f) - self.models[i].vessels(f - 1)
                if freed <= 0:
                    # dropping a departure frees no vessel: only useful if it ends the service
                    continue
                ratio = (self._margin(i, f) - self._margin(i, f - 1)) / freed
                if best is None or ratio < best_ratio:
                    best, best_ratio = i, ratio
            if best is None:
                break
            out[best] -= 1
        return out

    # ------------------------------------------------------------------ #
    #  Population initialisation                                            #
    # ------------------------------------------------------------------ #
    def _random_freq(self) -> List[int]:
        freq = list(self.init_freq)
        for i in self.active_idx:
            freq[i] = max(0, min(self.f_cap[i], freq[i] + self._rng.randint(-1, 1)))
        return freq

    # ------------------------------------------------------------------ #
    #  Fitness                                                              #
    # ------------------------------------------------------------------ #
    def _evaluate(self, freq: List[int]) -> float:
        """Surrogate weekly margin of the repaired frequency vector."""
        rep = self.repair(freq)
        total = 0.0
        for i in self.active_idx:
            total += self._margin(i, rep[i])
        return total

    # ------------------------------------------------------------------ #
    #  GA loop                                                              #
    # ------------------------------------------------------------------ #
    def run(self) -> List[int]:
        """Return the best frequency vector (departures per week, 0 = not operated)."""
        if not self.active_idx:
            self._telemetry = {
                "algorithm": "FrequencyGA", "actual_generations_executed": 0,
                "max_generations": self.generations, "stagnation_limit": self.stagnation_limit,
                "early_stop_reason": "no_candidates", "best_fitness": 0.0, "runtime_seconds": 0.0,
            }
            return [0] * self.num_services

        population = [self._random_freq() for _ in range(self.pop_size)]
        population[0] = list(self.init_freq)                   # analytical solution is always present
        fitness = [self._evaluate(p) for p in population]
        best_fitness = max(fitness)
        no_improve = 0
        start_time = time.time()
        actual_generations = 0
        early_stop_reason = "completed"

        for gen in range(self.generations):
            actual_generations += 1
            if time.time() - start_time > MAX_RUNTIME:
                early_stop_reason = "max_runtime_reached"
                break
            ranked = sorted(zip(population, fitness), key=lambda x: x[1], reverse=True)
            population = [x[0] for x in ranked[:10]]
            while len(population) < self.pop_size:
                child = self._rng.choice(ranked[:20])[0].copy()
                idx = self._rng.choice(self.active_idx)
                child[idx] = self._rng.randint(0, self.f_cap[idx])
                population.append(child)

            fitness = [self._evaluate(p) for p in population]
            current_best = max(fitness)
            if current_best > best_fitness:
                best_fitness, no_improve = current_best, 0
            else:
                no_improve += 1
            if no_improve >= self.stagnation_limit:
                early_stop_reason = "stagnation"
                break

        best = self.repair(population[int(np.argmax(fitness))])
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
        logger.info("frequency_ga_complete | best_fitness=%s generations=%d stop=%s runtime=%.2fs",
                    best_fitness, actual_generations, early_stop_reason, elapsed)
        return best
