"""HierarchicalGA - service selection (ServiceGA) then frequency (FrequencyGA).

Consistency rules enforced here (the previous implementation is preserved verbatim
in ``hierarchical_ga_legacy.py``):

* a service that cannot be modelled (no fleet class, missing distance or port
  record) is removed, never priced with an invented value;
* the pre-filter no longer uses ``0.3 * weekly_cost`` fuel or ``5000 * ports`` port
  cost "estimates" or hub-name lists - candidates are judged by the canonical
  service model inside the GAs;
* the frequency ceiling is derived from each service's real rotation time and its
  class inventory (no ``max_freq = 3``);
* a selected service with frequency 0 is NOT operated: it is removed from the mask
  instead of being counted as one vessel-departure;
* the vessels of the final chromosome fit every class's inventory exactly
  (``ceil(T * f / 7)`` per service).
"""

import logging
import time
from typing import Any, Dict, Optional

import numpy as np

from src.config.optimizer_config import CONFIG
from src.network.economics import service_models_for
from src.optimization.frequency_ga import FrequencyGA
from src.optimization.service_ga import ServiceGA

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
        port_cost_per_teu: float = 0.0,
        # pass-through to FrequencyGA. None = derived from real rotation times and
        # the class inventory. (Retired default: max_freq = 3.)
        max_freq: Optional[int] = None,
        # runtime budget
        max_runtime_sec: float = 60.0,
        # demand threshold for service filtering
        min_route_demand_threshold: float = 0.0,   # TEU — 0 = keep all
        objective_mode: str = "profit_first",
        stagnation_limit: int = 0,
        rng_label: Optional[str] = None,
    ):
        self.problem  = problem
        self.max_time = max_runtime_sec
        # LINER_SEED: streams are derived from (seed, "ga", rng_label); unseeded = global generators
        self._rng_label = rng_label

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
        self._fga_kwargs = {} if max_freq is None else dict(max_freq=max_freq)
        self.min_demand_threshold = min_route_demand_threshold

    # ------------------------------------------------------------------ #
    #  Pre-filter: modellable services that touch a demand corridor        #
    # ------------------------------------------------------------------ #
    def _filter_services(self) -> None:
        """Keep services that can be modelled and whose rotation contains at least one
        demand corridor with a ride inside the demand's transit-time limit. Operates in
        place on ``problem.services``."""
        models = service_models_for(self.problem)
        demands = [d for d in self.problem.demands if d.weekly_teu > 0]
        corridors = {(d.origin, d.destination): d for d in demands}

        kept = []
        for svc, m in zip(self.problem.services, models):
            if m is None:
                continue
            covers = False
            for a in m.ports:
                for b in m.ports:
                    d = corridors.get((a, b)) if a != b else None
                    if d is None:
                        continue
                    ride = m.ride(a, b)
                    lim = getattr(d, "max_transit_days", None)
                    if ride is not None and (lim is None or ride[1] <= lim + 1e-9):
                        covers = True
                        break
                if covers:
                    break
            if covers:
                kept.append(svc)

        before = len(self.problem.services)
        self.problem.services = kept
        logger.info("service_filter | before=%d after=%d", before, len(kept))

    # ------------------------------------------------------------------ #
    #  Main run                                                             #
    # ------------------------------------------------------------------ #
    def run(self, seed_chromosome: dict = None) -> Dict[str, Any]:
        t0 = time.perf_counter()

        self._filter_services()
        if not self.problem.services:
            logger.warning("no_services_after_filter")
            return {"services": [], "frequencies": [], "coverage_estimate": 0.0}

        # ── Level 1: service selection ─────────────────────────────────
        from src.utils.rng import streams as _streams
        _s = _streams("service_ga", self._rng_label)
        service_ga    = ServiceGA(self.problem, rng=_s.py, np_rng=_s.np, **self._sga_kwargs)
        seed_services = seed_chromosome.get("services") if seed_chromosome else None
        best_services = service_ga.run(seed_solution=seed_services)

        elapsed = time.perf_counter() - t0
        if elapsed > self.max_time * 0.8:
            logger.warning("ga_runtime_budget_near | elapsed=%.2fs", elapsed)

        # ── Level 2: frequency optimisation (real rotation times) ──────────
        _f = _streams("frequency_ga", self._rng_label)
        freq_ga   = FrequencyGA(self.problem, best_services, rng=_f.py, **self._fga_kwargs)
        best_freq = freq_ga.run()

        # A service that is not scheduled is not operated: it leaves the mask.
        n = len(best_services)
        mask = [1 if (best_services[i] == 1 and i < len(best_freq) and best_freq[i] > 0) else 0
                for i in range(n)]
        freq = [int(best_freq[i]) if mask[i] else 0 for i in range(n)]

        # Vessel use of the final chromosome, per class (exact), checked against the
        # real inventory. FrequencyGA already repaired it; this is the safety net.
        models = service_models_for(self.problem)
        fleet = getattr(self.problem, "fleet", None)
        inventory = {c.vessel_class: int(c.quantity) for c in fleet.classes} if fleet else {}
        used: Dict[str, int] = {}
        for i in range(n):
            if mask[i] and models[i] is not None:
                used[models[i].vessel_class] = used.get(models[i].vessel_class, 0) + models[i].vessels(freq[i])
        over = {c: (u, inventory.get(c, 0)) for c, u in used.items() if u > inventory.get(c, 0)}
        if over:
            logger.warning("post_ga_fleet_violation | %s", over)

        # ── Coverage estimate (capacity shared across overlapping services) ──
        total_demand = sum(d.weekly_teu for d in self.problem.demands)
        coverage_estimate = 0.0
        if total_demand > 0 and hasattr(service_ga, "_share"):
            supply = np.zeros(len(service_ga._od_demand))
            for i in range(n):
                if mask[i] and models[i] is not None:
                    supply += models[i].capacity_teu * freq[i] * service_ga._share[i]
            served = float(np.minimum(service_ga._od_demand, supply).sum())
            coverage_estimate = min(served, total_demand) / total_demand * 100

        ga_total_elapsed = time.perf_counter() - t0
        chromosome = {
            "services":          mask,
            "frequencies":       freq,
            "coverage_estimate": coverage_estimate,
            "skip_milp":         coverage_estimate < 30.0,
            "vessels_by_class":  used,
            "service_ga_telemetry":    getattr(service_ga, "_telemetry", None),
            "frequency_ga_telemetry":  getattr(freq_ga,   "_telemetry", None),
            "ga_total_elapsed_sec":    round(ga_total_elapsed, 4),
        }
        logger.info(
            "hierarchical_ga_complete | selected=%d coverage_estimate=%.2f elapsed=%.2fs vessels=%s",
            sum(mask), coverage_estimate, ga_total_elapsed, used,
        )
        return chromosome
