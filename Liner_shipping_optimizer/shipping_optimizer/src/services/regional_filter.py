"""Regional candidate filter: economics instead of a hard-coded guess (Task 16).

What the legacy ``RegionalAgent._filter_services`` does
    1. keeps a candidate only if it covers a demand corridor of the region (kept here);
    2. keeps it only if ``capacity * 0.5 * 150 USD > one vessel's weekly hire``.  Capacity
       and hire are properties of the vessel CLASS, so this is a class-level cut that no
       rotation can influence (it rejects a class whose 0.5 x 150 USD/TEU "revenue" is below
       one vessel's hire, whatever the rotation earns; the WorldSmall demand pays 105 - 2,590
       USD/TEU, mean 958).  Measured: it rejects nothing in the production configuration;
    3. ranks the survivors by ``capacity / hire`` - again a class constant, so inside a
       class the order is generation order - and keeps the first ``max_services``.
       The cap therefore drops the *last generated* small-class candidates, not the least
       valuable ones.

Economic filter (this module)
    * the corridor test is unchanged;
    * the margin guess is gone: no class is named or treated specially;
    * the cap keeps the candidates with the best **stand-alone economics** from the canonical
      service model (``ClassScreener.evaluate_class``: hire + fuel at the pinned price + port
      calls, capacity on every leg, transit-time-feasible cargo, best weekly frequency - the
      model the optimiser and the independent ledger use).  Ties keep generation order.
    * a candidate whose economics cannot be evaluated is ranked last and counted
      (``economics_unavailable``) - never given an invented value.
    * stand-alone profit is an ordering signal, not a verdict: the network MILP and the
      ledger decide what is operated.  Candidates with a stand-alone loss are *not* dropped
      while the cap has room: they may be useful feeders or connectors.

Switch ``LINER_REGIONAL_FILTER``: ``auto`` (default) | ``economic`` | ``legacy``.
``auto`` = ``economic`` while the Task 9/10 candidate generators are on (their defaults) and
``legacy`` when both are switched off, so the documented rollback configuration
(``LINER_DEMAND_LOOP_BUDGET=0 LINER_CLASS_SCREEN=0``) still restores the previous pool
element by element.  ``LINER_REGIONAL_FILTER=legacy`` restores the previous filter alone.

Evidence for the default (reports/tasks_14_15_16/task16_regional_filter_economics.md, WorldSmall):

    production CBC 120 s, controlled, 5 paired seeds   legacy 8.64 M/wk   economic 9.15 (+0.51, 4/5)
    end to end, orchestrator (hints, 120 s), 3 runs    legacy 8.48 - 9.19 (7 runs, mean 8.94)
                                                       economic 9.98 / 10.85 / 11.82; 342/342 each
    HiGHS 600 s, controlled                            legacy 9.33 (proven)   economic 11.48 (+2.15, 5/5)

Known interaction: with the opt-in HiGHS backend at the 120 s budget the economic pool is a harder
instance (controlled: 8.67 vs 9.31 M for the legacy pool).  Pair HiGHS with
``LINER_REGIONAL_FILTER=legacy`` at 120 s, or give it a larger global-stage budget.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

ENV_FILTER = "LINER_REGIONAL_FILTER"
MODE_LEGACY = "legacy"
MODE_ECONOMIC = "economic"
MODE_AUTO = "auto"

R_KEPT = "kept"
R_LOOP_EXEMPT = "demand_loop_exempt"
#: candidate sections that carry their own evidence and budget and so neither pass through
#: the corridor/cap test nor use up its slots: Task 9 demand-coherent loops and the Task 21
#: route-operator variants / elites (all absent unless their switch is on)
EXEMPT_SECTIONS = ("demand_loop", "elite", "route_operator")
R_NO_CORRIDOR = "no_corridor"
R_CAP = "cut_by_cap_lowest_economics"


def filter_mode(env: Optional[Dict[str, str]] = None) -> str:
    """Resolve the filter in force (``legacy`` or ``economic``)."""
    e = os.environ if env is None else env
    raw = (e.get(ENV_FILTER) or "").strip().lower()
    if raw in ("", MODE_AUTO):
        from src.services.class_screening import config_from_environment as _screen
        from src.services.demand_coherent import config_from_environment as _loops
        loops, screen = _loops(e), _screen(e)
        generators_on = (loops.enabled and loops.budget > 0) or screen.enabled
        return MODE_ECONOMIC if generators_on else MODE_LEGACY
    if raw not in (MODE_LEGACY, MODE_ECONOMIC):
        raise ValueError(f"{ENV_FILTER} must be one of legacy|economic|auto, got {raw!r}")
    return raw


@dataclass
class FilterReport:
    mode: str = MODE_ECONOMIC
    cap: int = 0
    candidates: int = 0
    demand_loops_exempt: int = 0
    no_corridor: int = 0
    considered: int = 0
    cut_by_cap: int = 0
    kept: int = 0
    economics_unavailable: int = 0
    kept_by_class: Dict[str, int] = field(default_factory=dict)
    cut_by_class: Dict[str, int] = field(default_factory=dict)
    cut_standalone_profit_max: Optional[float] = None       # best stand-alone profit that was cut
    kept_standalone_profit_min: Optional[float] = None      # worst one that was kept

    def to_dict(self) -> Dict:
        return dict(self.__dict__)


def select_economic(
    services: Sequence,
    corridor_set,
    max_services: int,
    evaluate,
) -> Tuple[List, List, FilterReport]:
    """Return ``(kept_non_loop, loops, report)``.

    ``evaluate(service)`` returns the stand-alone weekly profit (USD) of the candidate on its
    own class from the canonical model, or ``None`` when it cannot be evaluated."""
    rep = FilterReport(cap=int(max_services), candidates=len(services))
    loops = [s for s in services if getattr(s, "origin_section", "") in EXEMPT_SECTIONS]
    rep.demand_loops_exempt = len(loops)
    pool = []
    for s in services:
        if getattr(s, "origin_section", "") in EXEMPT_SECTIONS:
            continue
        ports = set(s.ports)
        if any(o in ports and d in ports for (o, d) in corridor_set):
            pool.append(s)
        else:
            rep.no_corridor += 1
    rep.considered = len(pool)
    cache: Dict[Tuple, Optional[float]] = {}
    profit: List[float] = []
    for s in pool:
        key = (tuple(s.ports), getattr(s, "vessel_class", ""))
        if key not in cache:
            cache[key] = evaluate(s)
        v = cache[key]
        if v is None:
            rep.economics_unavailable += 1
            profit.append(float("-inf"))
        else:
            profit.append(float(v))
    order = sorted(range(len(pool)), key=lambda i: (-profit[i], i))
    take = set(order[:max(0, int(max_services))])
    kept = [pool[i] for i in range(len(pool)) if i in take]          # generation order
    cut = [i for i in range(len(pool)) if i not in take]
    rep.kept = len(kept)
    rep.cut_by_cap = len(cut)
    rep.kept_by_class = dict(Counter(getattr(pool[i], "vessel_class", "") for i in take))
    rep.cut_by_class = dict(Counter(getattr(pool[i], "vessel_class", "") for i in cut))
    finite_cut = [profit[i] for i in cut if profit[i] != float("-inf")]
    finite_kept = [profit[i] for i in take if profit[i] != float("-inf")]
    rep.cut_standalone_profit_max = max(finite_cut) if finite_cut else None
    rep.kept_standalone_profit_min = min(finite_kept) if finite_kept else None
    return kept, loops, rep
