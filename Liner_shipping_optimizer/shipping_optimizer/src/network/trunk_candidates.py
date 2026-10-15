"""Class-forced trunk-rotation candidates for under-used vessel classes (opt-in, default OFF).

Problem (measured on the current model, reports/class_mismatch_campaign): the candidate pool is 79 % Feeder_450
(950 of 1,205 rotations for a class that owns 24 vessels) and contains NO rotation for Post_panamax (58 vessels) and
two for Super_panamax (10 vessels).  The generator grows rotations of at most 5 ports, scores growth per vessel (which
favours small ships) and picks the class by the rotation's own cargo.  Evaluating every pool rotation in every class
(`tools/class_diag.py`) shows 0 of 250 feasible Post_panamax variants is profitable stand-alone: the pool holds only
thin 2-5 port rotations, which a 8,400-TEU ship cannot fill.  Growing rotations WITH the large class fixed
(`tools/trunk_proto.py`, eight ports, hubs with enough draft) gives stand-alone-profitable trunks for it.

What this does (``LINER_TRUNK_CANDIDATES`` = rotations to add per class; 0 / unset = OFF)
  1. a class is a *target* when the pool holds fewer than ``PRESSURE_RATIO`` (2.0) candidates per vessel it owns
     (the same rule as ``class_variants``);
  2. for each target class, rotations are grown greedily from the strongest OD pairs between ports whose draft the
     class can call at, adding the port/position that raises the canonical STAND-ALONE PROFIT most
     (``demand_coherent._Evaluator``: feasibility, canal and draft rules, vessels against inventory, ride-feasible
     cargo inside each OD's transit limit, hire + fuel + port calls) up to ``LINER_TRUNK_MAX_PORTS`` (default 8);
  3. only rotations with a POSITIVE stand-alone profit are kept, near-duplicates (Jaccard >= 0.8) are dropped and the
     best ``N`` per class by stand-alone profit are returned.

Nothing here prices cargo or accounts cost: the additions are ordinary candidates; the global MILP decides with their
real fixed and variable costs and the independent ledger verifies the plan.  Stand-alone profit is a screen: a trunk's
cargo overlaps with other services, so its stand-alone profit is NOT additive with the network's.
"""

from __future__ import annotations

import math
import os
import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

ENV_TRUNK = "LINER_TRUNK_CANDIDATES"
ENV_MAX_PORTS = "LINER_TRUNK_MAX_PORTS"
ENV_DIVERSE = "LINER_TRUNK_DIVERSE"          # 1: set-cover selection (demand already covered by a chosen trunk counts 25 %)
PRESSURE_RATIO = 2.0
DEFAULT_MAX_PORTS = 8
HARD_MAX_PORTS = 12
SEED_PAIRS = 60
NEIGHBOURHOOD = 14
NEAR_DUPLICATE_JACCARD = 0.8


def count_from_environment(env: Optional[Dict[str, str]] = None) -> int:
    """Trunk rotations to add per target class (0 = off).  Malformed values raise ``ValueError``."""
    raw = ((os.environ if env is None else env).get(ENV_TRUNK) or "").strip()
    if not raw:
        return 0
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_TRUNK} must be a non-negative integer, got {raw!r}") from None
    if n < 0 or n > 200:
        raise ValueError(f"{ENV_TRUNK} must be in [0, 200], got {n}")
    return n


def max_ports_from_environment(env: Optional[Dict[str, str]] = None) -> int:
    raw = ((os.environ if env is None else env).get(ENV_MAX_PORTS) or "").strip()
    if not raw:
        return DEFAULT_MAX_PORTS
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_MAX_PORTS} must be an integer, got {raw!r}") from None
    if n < 3 or n > HARD_MAX_PORTS:
        raise ValueError(f"{ENV_MAX_PORTS} must be in [3, {HARD_MAX_PORTS}], got {n}")
    return n


def diverse_from_environment(env: Optional[Dict[str, str]] = None) -> bool:
    raw = ((os.environ if env is None else env).get(ENV_DIVERSE) or "").strip().lower()
    if raw in ("", "0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    raise ValueError(f"{ENV_DIVERSE} must be 0 or 1, got {raw!r}")


def _mark_covered(ev, D, ports, cls) -> None:
    """The directed ODs the rotation carries inside their transit limit become 'covered' (discounted for later trunks)."""
    m, _why = ev.model(ports, cls)
    if m is None:
        return
    for a in m.ports:
        for b in m.ports:
            if a == b or not D.teu.get((a, b)):
                continue
            ride = m.ride(a, b)
            if ride is None:
                continue
            lim = D.limit.get((a, b))
            if lim is not None and ride[1] > lim + 1e-9:
                continue
            ev.covered.add((a, b))


def augment_trunk_candidates(problem, assumptions, candidates: Sequence, *, per_class: int,
                             max_ports: int = DEFAULT_MAX_PORTS, deadline: Optional[float] = None,
                             id_prefix: str = "tk", diverse: bool = False,
                             classes: Optional[Sequence[str]] = None, port_filter: Optional[set] = None,
                             seed_groups: Optional[Tuple[set, set]] = None,
                             collect_rejected: Optional[List[Dict]] = None) -> Tuple[List, Dict]:
    """Return (new candidates, report).  Never raises for an unattainable rotation: it is counted in the report.

    Optional restrictions (used by ``trunk_lanes``; all default None = the original behaviour, unchanged):
      ``classes``      explicit target classes instead of the under-subscription rule;
      ``port_filter``  rotations may only call at these ports (in addition to the class draft rule);
      ``seed_groups``  (A, B): every seed OD has one end in A and the other in B, so the rotation joins the two groups;
      ``collect_rejected``  a list that receives every grown rotation rejected for a non-positive stand-alone profit (the
                       input of ``dual_screen``; it changes nothing about what is returned)."""
    from src.network.plan import Candidate
    from src.services.demand_coherent import DemandCoherentConfig, _canonical, _Demand, _Evaluator

    t0 = time.perf_counter()
    rep: Dict = {"requested_per_class": per_class, "max_ports": max_ports, "diverse": bool(diverse), "pool_unique": len(candidates),
                 "added": 0, "target_classes": {}, "additions": [], "sec": 0.0, "stopped_by_deadline": False}
    if per_class <= 0 or not candidates:
        return [], rep
    fleet = problem.fleet
    inventory = {c.vessel_class: int(c.quantity) for c in fleet.classes}
    count = Counter(c.vessel_class for c in candidates)
    if classes is not None:
        targets = [c.vessel_class for c in fleet.classes if c.vessel_class in set(classes) and inventory[c.vessel_class] > 0]
    else:
        targets = [c.vessel_class for c in fleet.classes
                   if inventory[c.vessel_class] > 0 and count.get(c.vessel_class, 0) / inventory[c.vessel_class] < PRESSURE_RATIO]
    rep["target_classes"] = {k: {"candidates": count.get(k, 0), "inventory": inventory[k]} for k in sorted(targets)}
    if not targets:
        rep["reason"] = "no under-subscribed class"
        rep["sec"] = round(time.perf_counter() - t0, 2)
        return [], rep

    catalog = getattr(problem, "port_catalog", None)
    lookup = dict(catalog) if catalog else {p.id: p for p in problem.ports}
    D = _Demand(getattr(problem, "global_demands", None) or problem.demands, lookup)
    cfg = DemandCoherentConfig(max_ports=max(5, max_ports))
    ev = _Evaluator(problem, fleet, assumptions, D, set(), cfg)
    known = set(problem.distance_matrix)
    existing = {(_canonical(c.ports), c.vessel_class) for c in candidates}
    rank = 0
    # diverse mode: classes are served largest first and every chosen trunk marks the ODs it carries as covered
    # (``covered_weight`` 25 % in the growth score of later trunks), so trunks of different classes serve different lanes
    order = (sorted(targets, key=lambda k: (-float(fleet.get_class(k).capacity_teu), k)) if diverse else sorted(targets))
    score_key = "weighted" if diverse else "standalone"
    for cname in order:
        cls = fleet.get_class(cname)
        cdraft = float(getattr(cls, "draft", 0.0) or 0.0)
        elig = {p for p in lookup if p in known and float(getattr(lookup[p], "draft", 0.0) or 0.0) + 1e-9 >= cdraft}
        draft_eligible = len(elig)
        if port_filter is not None:
            elig &= set(port_filter)

        def _cross(k):
            if seed_groups is None:
                return True
            a_, b_ = seed_groups
            return (k[0] in a_ and k[1] in b_) or (k[0] in b_ and k[1] in a_)

        seeds = sorted((k for k in D.teu if k[0] in elig and k[1] in elig and k[0] < k[1] and _cross(k)),
                       key=lambda k: (-D.opportunity(k), k))[:SEED_PAIRS]
        crep = {"draft_eligible_ports": draft_eligible, "eligible_ports": len(elig), "seed_pairs": len(seeds),
                "grown_rotations": 0, "rejected_nonpositive_standalone": 0, "rejected_existing_in_pool": 0,
                "rejected_near_duplicate": 0, "rejected_by_cap": 0, "retained": 0}
        rep.setdefault("per_class", {})[cname] = crep
        grown: Dict[Tuple[str, ...], Dict] = {}
        for sd in seeds:
            if deadline is not None and time.perf_counter() > deadline:
                rep["stopped_by_deadline"] = True
                break
            ports = list(sd)
            cur, _ = ev.evaluate(ports, cls)
            score = (cur[score_key] - (cur["fixed"] if diverse else 0.0)) if cur else -math.inf
            if diverse:
                cur_best = (cur, list(ports)) if cur else None
            for _ in range(max_ports - 2):
                link: Dict[str, float] = defaultdict(float)
                for m_ in ports:
                    for k in D.by_port.get(m_, ()):
                        o = k[1] if k[0] == m_ else k[0]
                        if o not in ports and o in elig:
                            link[o] += D.opportunity(k)
                if not link:
                    break
                best = None
                for P in sorted(link, key=lambda p: (-link[p], p))[:NEIGHBOURHOOD]:
                    for pos in range(len(ports)):
                        new = ports[:pos + 1] + [P] + ports[pos + 1:]
                        m, _w = ev.evaluate(new, cls)
                        if m is None:
                            continue
                        key = ((m["weighted"] - m["fixed"]) if diverse else m["standalone"], tuple(new))
                        if best is None or key[0] > best[0][0] or (key[0] == best[0][0] and key[1] < best[0][1]):
                            best = (key, new, m)
                if best is None or best[0][0] <= score + 1e-9:
                    break
                (score, _), ports, cur = best
                if len(ports) >= 3 and cur is not None:
                    key = _canonical(ports)
                    prev = grown.get(key)
                    if prev is None or cur["standalone"] > prev["m"]["standalone"]:
                        grown[key] = {"ports": list(ports), "m": cur, "seed": sd, "marg": cur["weighted"] - cur["fixed"]}
            if diverse and cur is not None and len(ports) >= 3 and cur["standalone"] > 0.0:
                _mark_covered(ev, D, ports, cls)
        chosen: List[Dict] = []
        crep["grown_rotations"] = len(grown)
        for g in sorted(grown.values(), key=lambda g: (-(g["marg"] if diverse else g["m"]["standalone"]), tuple(g["ports"]))):
            if g["m"]["standalone"] <= 0.0:
                crep["rejected_nonpositive_standalone"] += 1
                if collect_rejected is not None:
                    collect_rejected.append({"ports": list(g["ports"]), "vessel_class": cname,
                                             "standalone": float(g["m"]["standalone"]), "source": id_prefix})
                continue
            if len(chosen) >= per_class:
                crep["rejected_by_cap"] += 1
                continue
            key = _canonical(g["ports"])
            if (key, cname) in existing:
                crep["rejected_existing_in_pool"] += 1
                continue
            pset = set(g["ports"])
            if any(len(pset & set(s["ports"])) / len(pset | set(s["ports"])) >= NEAR_DUPLICATE_JACCARD for s in chosen):
                crep["rejected_near_duplicate"] += 1
                continue
            chosen.append(g)
        crep["retained"] = len(chosen)
        for g in chosen:
            m = g["m"]
            rep["additions"].append({
                "service_id": f"{id_prefix}{rank:04d}", "ports": list(g["ports"]), "vessel_class": cname, "rank": rank,
                "seed_od": list(g["seed"]), "standalone_profit_usd_per_week": round(m["standalone"], 1),
                "vessels_at_f1": m["vessels"], "served_teu_f1": round(m["served"], 1),
                "fixed_cost_usd_per_week": round(m["fixed"], 1), "cycle_time_days": m["cycle_time_days"],
                "reason": "class-forced trunk rotation for an under-subscribed class; positive stand-alone profit"})
            rank += 1
    new = [Candidate(a["service_id"], tuple(a["ports"]), a["vessel_class"]) for a in rep["additions"]]
    rep["added"] = len(new)
    rep["sec"] = round(time.perf_counter() - t0, 2)
    return new, rep
