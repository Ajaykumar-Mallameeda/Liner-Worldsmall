"""Candidate variants of ``RegionalAgent._filter_services`` (Task 16 experiment only).

Imported by ``global_stage_experiment.py`` when the environment variable ``T16_FILTER`` is
set; nothing here is production code.  Every variant is class-neutral: no vessel class is
named, and the only per-candidate economics is the canonical stand-alone evaluation
``ClassScreener.evaluate_class`` (the model the optimiser and the ledger use: hire + fuel at
the pinned price + port calls, capacity on every leg, transit-time-feasible cargo).

variants
    legacy         the production filter (class-level margin guess + class-ratio cap)
    nofilter       no margin test and no cap (diagnostic: what the filter removes)
    exempt_screened  legacy test and cap, but a candidate whose class was chosen on positive
                   stand-alone economics (Task 10 screening) is not deleted by the guess
    econ_cap       NO margin test; the cap keeps the economically best candidates
                   (stand-alone profit descending) instead of the best class-ratio
    econ_global    like econ_cap, but a candidate must carry ride-feasible direct cargo of the
                   GLOBAL demand (transit limits included) instead of covering a corridor of the
                   region's own demand set
    econ_prune<N>  stand-alone-profitable candidates, plus the N least-loss candidates that
                   have ride-feasible cargo (a conservative network-role reserve), within the
                   cap; everything else is dropped
In every variant demand-coherent loops (``origin_section == 'demand_loop'``) are exempt
exactly as in production, and a candidate must still cover a demand corridor.
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

VARIANT = os.environ.get("T16_FILTER", "legacy").strip() or "legacy"


def install(RegionalAgent, ClassScreener, ClassScreeningConfig, assumptions_for_problem, log):
    """Replace ``RegionalAgent._filter_services`` by the selected variant and return the
    original so the harness can also report the legacy decision for every candidate."""
    original = RegionalAgent._filter_services

    def _economics(problem, svc, screener_cache):
        key = (tuple(svc.ports), svc.vessel_class)
        hit = screener_cache.get(key)
        if hit is None:
            scr = screener_cache["__screener__"]
            cls = problem.fleet.get_class(svc.vessel_class)
            hit = scr.evaluate_class(list(svc.ports), cls) if cls is not None else None
            screener_cache[key] = hit
        return hit

    def _filter(self, problem, adaptive_budget):
        from src.optimization.adaptive_budget import get_filter_params
        pre = list(problem.services)
        scr = ClassScreener(problem, problem.fleet, assumptions_for_problem(problem),
                            ClassScreeningConfig(k=1))
        cache: Dict = {"__screener__": scr}
        corridor_set = {(d.origin, d.destination) for d in problem.demands}
        max_services = get_filter_params(adaptive_budget)["max_services"]

        # legacy decision for every candidate (reported for all variants)
        legacy_kept = {}
        for svc in pre:
            if getattr(svc, "origin_section", "") == "demand_loop":
                legacy_kept[id(svc)] = "exempt_loop"
                continue
            ps = set(svc.ports)
            covers = any(o in ps and d in ps for (o, d) in corridor_set)
            margin = (svc.capacity * 0.5 * 150) > svc.weekly_cost
            legacy_kept[id(svc)] = ("pass" if (covers and margin) else
                                    "no_corridor" if not covers else "margin_guess")
        rows = []
        for svc in pre:
            ev = _economics(problem, svc, cache)
            rows.append({"id": svc.id, "class": svc.vessel_class,
                         "section": getattr(svc, "origin_section", "unknown"),
                         "ports": list(svc.ports), "legacy": legacy_kept[id(svc)],
                         "feasible": bool(ev.feasible) if ev else False,
                         "standalone_profit": ev.standalone_profit_best if ev else None,
                         "direct_ride_feasible_teu": ev.direct_ride_feasible_teu if ev else 0.0,
                         "best_f": ev.best_frequency if ev else 0})
        by_id = {id(s): r for s, r in zip(pre, rows)}

        if VARIANT == "legacy":
            problem.services = pre
            out = original(self, problem, adaptive_budget)
            kept_ids = {id(s) for s in out.services}
            for s in pre:
                by_id[id(s)]["kept"] = id(s) in kept_ids
            log(self.region, VARIANT, rows, max_services)
            return out

        loops = [s for s in pre if getattr(s, "origin_section", "") == "demand_loop"]
        legacy_part = [s for s in pre if getattr(s, "origin_section", "") != "demand_loop"]

        def covers(s):
            ps = set(s.ports)
            return any(o in ps and d in ps for (o, d) in corridor_set)

        def profit(s):
            r = by_id[id(s)]["standalone_profit"]
            return r if r is not None else float("-inf")

        pool = [s for s in legacy_part if covers(s)]
        if VARIANT == "nofilter":
            kept = pool
        elif VARIANT == "exempt_screened":
            # legacy test and legacy class-ratio cap, except that a candidate whose class was
            # chosen on positive stand-alone economics (Task 10) is not deleted by the guess
            ok = [s for s in pool if (s.capacity * 0.5 * 150) > s.weekly_cost
                  or getattr(s, "economically_screened", False)]
            kept = sorted(ok, key=lambda s: s.capacity / (s.weekly_cost + 1), reverse=True)[:max_services]
        elif VARIANT == "econ_cap":
            order = sorted(range(len(pool)), key=lambda i: (-profit(pool[i]), i))
            kept = [pool[i] for i in sorted(order[:max_services])]   # keep generation order
        elif VARIANT == "econ_global":
            # relevance = ride-feasible direct cargo on the GLOBAL demand (transit-time limits
            # included), not membership of the region's own corridor set; the cap keeps the
            # economically best.  No margin guess, no class named.
            pool_g = [s for s in legacy_part if by_id[id(s)]["direct_ride_feasible_teu"] > 0]
            order = sorted(range(len(pool_g)), key=lambda i: (-profit(pool_g[i]), i))
            kept = [pool_g[i] for i in sorted(order[:max_services])]
        elif VARIANT.startswith("econ_prune"):
            n_reserve = int(VARIANT[len("econ_prune"):] or 0)
            profitable = [i for i, s in enumerate(pool) if profit(s) > 0]
            others = [i for i, s in enumerate(pool)
                      if profit(s) <= 0 and by_id[id(s)]["direct_ride_feasible_teu"] > 0]
            others.sort(key=lambda i: (-profit(pool[i]), i))
            chosen = profitable + others[:n_reserve]
            chosen = sorted(chosen, key=lambda i: (-profit(pool[i]), i))[:max_services]
            kept = [pool[i] for i in sorted(chosen)]
        else:
            raise SystemExit(f"unknown T16_FILTER variant {VARIANT}")
        kept_ids = {id(s) for s in kept} | {id(s) for s in loops}
        for s in pre:
            by_id[id(s)]["kept"] = id(s) in kept_ids
        problem.services = kept + loops
        log(self.region, VARIANT, rows, max_services)
        return problem

    RegionalAgent._filter_services = _filter
    return original
