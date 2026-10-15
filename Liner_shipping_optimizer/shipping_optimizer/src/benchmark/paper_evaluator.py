"""FFE-native evaluator of the objective of the RL paper (Dutta, Lin, Jin, arXiv:2411.09068, App. A-B).

This is NOT the operational model.  It reproduces, as far as the paper supports, the paper's own
evaluation of a network design so that results can be compared like for like:

  * every quantity is FFE (demand, flow, vessel capacity, revenue rate, port and transshipment rates);
    nothing is converted to TEU and nothing is read through the operational loader;
  * services are weekly rotations with FRACTIONAL vessel counts
        n_s = (sum_legs distance / (design speed * 24) + 1 day per port call) / 7        (App. A.3, p.17)
    (verified: this reproduces the vessel numbers of the paper's Table 6 for all 19 schedules);
  * capacity of a service edge = vessel capacity (FFE per week, one weekly departure);
  * no transit-time constraint, unlimited transfers (Dijkstra on the expanded graph, App. B);
  * cargo is routed by the paper's greedy heuristic (Algorithm 1: demands by descending revenue per FFE,
    cheapest path by handling cost, ship the path capacity, repeat);
  * profit = revenue - rejected-demand penalty - handling - (service + unused + voyage)   (Eq. 28-35)
        service = sum n_s * TC_daily * 7;  unused = -(inventory - sum n) * TC_daily * 7 per class
        (a credit when vessels are spare, a cost when more are used than owned: soft fleet limit).

Interpretation switches (the printed equations are partly illegible / ambiguous; both readings are
evaluated and reported, never silently chosen):
  voyage_basis = "per_rotation" : port-call and fuel costs counted once per weekly rotation
               = "per_vessel"   : multiplied by the fractional vessel count n_s (Eq. 35 read literally)
  port_variable_basis = "capacity" (p_v * vcap per port call, Eq. 35) | "cargo" (p_v per FFE loaded/unloaded)
  canal_basis = "none" | "per_rotation" | "per_vessel"
  capacity_basis = "per_departure" (service edge capacity = vessel capacity per week; physical reading)
                 | "per_vessel"    (vessel capacity x fractional vessel count)

Time horizon: weekly (demand is FFE per week; vessel cost uses the daily TC rate x 7) - INFERRED, the paper
does not state the horizon of its profit tables.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

REJECT_PENALTY_PER_FFE = 1000.0       # paper A.1: Y_d "set to $1000"
PORT_DAYS = 1.0                       # paper p.17: "the required 1 day at each port"


@dataclass
class FfeData:
    ports: Dict[str, Dict]                           # id -> {pf, pv, pl, pt}
    demands: List[Dict]                              # {o, d, ffe, rev}
    dist: Dict[Tuple[str, str], Tuple[float, int, int]]   # (o, d) -> (nm, panama, suez)
    classes: Dict[str, Dict]                         # name -> {cap, n_avail, tc, speed, fuel_sea, fuel_idle, panama, suez}
    unit: str = "FFE"                                # unit of demand, capacity and every per-unit rate in this instance
    penalty_per_unit: float = REJECT_PENALTY_PER_FFE  # rejected-demand penalty per unit (1,000 per FFE = 500 per TEU)


def load_worldsmall_ffe(root: Path) -> FfeData:
    """Raw WorldSmall files, FFE-native (tab separated)."""
    root = Path(root)
    p = pd.read_csv(root / "ports.csv", sep="\t")
    ports = {r.UNLocode: {"pf": float(r.PortCallCostFixed), "pv": float(r.PortCallCostPerFFE),
                          "pl": float(r.CostPerFULL), "pt": float(r.CostPerFULLTrnsf)} for r in p.itertuples()}
    dm = pd.read_csv(root / "Demand_WorldSmall_Fixed_Sep.csv", sep="\t")
    demands = [{"o": r.Origin, "d": r.Destination, "ffe": float(r.FFEPerWeek), "rev": float(r.Revenue_1)}
               for r in dm.itertuples() if r.Origin != r.Destination]
    ds = pd.read_csv(root / "dist_dense.csv", sep="\t")
    dist = {(r.fromUNLOCODe, r.ToUNLOCODE): (float(r.Distance), int(r.IsPanama), int(r.IsSuez)) for r in ds.itertuples()}
    fd = pd.read_csv(root / "fleet_data.csv", sep="\t")
    q = pd.read_csv(root / "fleet_WorldSmall.csv", sep="\t").set_index("Vessel class").Quantity
    classes = {}
    for r in fd.to_dict("records"):
        c = r["Vessel class"].strip()
        classes[c] = {"cap": float(r["Capacity FFE"]), "n_avail": float(q[c]), "tc": float(r["TC rate daily (fixed Cost)"]),
                      "speed": float(r["designSpeed"]), "fuel_sea": float(r["Bunker ton per day at designSpeed"]),
                      "fuel_idle": float(r["Idle Consumption ton/day"]),
                      "panama": None if pd.isna(r.get("panamaFee")) else float(r["panamaFee"]),
                      "suez": None if pd.isna(r.get("suezFee")) else float(r["suezFee"])}
    return FfeData(ports, demands, dist, classes)


def class_by_capacity(data: FfeData, cap: float) -> str:
    for n, c in data.classes.items():
        if abs(c["cap"] - cap) < 1e-9:
            return n
    raise KeyError(f"no vessel class with capacity {cap} FFE")


def vessels_needed(data: FfeData, ports: Sequence[str], cls: str) -> float:
    """Fractional vessels for one weekly departure; ``ports`` is the closed rotation WITHOUT repeating the start."""
    legs = list(zip(ports, list(ports[1:]) + [ports[0]]))
    nm = sum(data.dist[l][0] for l in legs)
    return (nm / (data.classes[cls]["speed"] * 24.0) + PORT_DAYS * len(ports)) / 7.0


def _greedy_mcf(data: FfeData, services: List[Dict]) -> Tuple[List[Tuple[int, List[Tuple[str, int]], float]], Dict[int, float]]:
    """Paper Algorithm 1.  Returns (flows [(demand index, path, FFE)], rejected {demand index: FFE}).
    Nodes: ('P', port) and ('S', port, service).  Edge capacities are shared service legs."""
    # service leg edges: (service, leg index) -> capacity left; node chain per service
    cap_left: Dict[Tuple[int, int], float] = {}
    adj: Dict[Tuple, List[Tuple[Tuple, float, Optional[Tuple[int, int]]]]] = defaultdict(list)
    for si, s in enumerate(services):
        ps = s["ports"]
        n = len(ps)
        for k in range(n):
            a, b = ps[k], ps[(k + 1) % n]
            cap_left[(si, k)] = s["cap"]
            adj[("S", a, si)].append((("S", b, si), 0.0, (si, k)))
        for p in set(ps):
            pr = data.ports[p]
            adj[("P", p)].append((("S", p, si), pr["pl"] / 2.0, None))     # load: half of the p_l pair, see below
            adj[("S", p, si)].append((("P", p), pr["pl"] / 2.0, None))     # unload
            for sj, s2 in enumerate(services):
                if sj != si and p in s2["ports"]:
                    adj[("S", p, si)].append((("S", p, sj), pr["pt"], None))
    order = sorted(range(len(data.demands)), key=lambda i: -data.demands[i]["rev"])
    flows, rejected = [], {}
    for di in order:
        d = data.demands[di]
        rem = d["ffe"]
        src, dst = ("P", d["o"]), ("P", d["d"])
        if src not in adj:
            rejected[di] = rem
            continue
        while rem > 1e-9:
            # Dijkstra over edges with remaining capacity
            dist_, prev = {src: 0.0}, {}
            pq = [(0.0, 0, src)]
            cnt = 0
            while pq:
                c, _, u = heapq.heappop(pq)
                if c > dist_.get(u, 1e18):
                    continue
                if u == dst:
                    break
                for v, w, eid in adj.get(u, ()):
                    if eid is not None and cap_left[eid] <= 1e-9:
                        continue
                    nc = c + w
                    if nc < dist_.get(v, 1e18) - 1e-12:
                        dist_[v] = nc
                        prev[v] = (u, eid)
                        cnt += 1
                        heapq.heappush(pq, (nc, cnt, v))
            if dst not in prev and src != dst:
                break
            path_edges, v = [], dst
            while v != src:
                u, eid = prev[v]
                if eid is not None:
                    path_edges.append(eid)
                v = u
            q = min([rem] + [cap_left[e] for e in path_edges])
            if q <= 1e-9:
                break
            for e in path_edges:
                cap_left[e] -= q
            flows.append((di, path_edges, q))
            rem -= q
        if rem > 1e-9:
            rejected[di] = rem
    return flows, rejected


def transfer_ports(services: List[Dict], edges: List[Tuple[int, int]]) -> List[str]:
    """Ports where a flow changes service.  ``edges`` is the path as ``_greedy_mcf`` returns it (destination to origin).

    The transfer port is the port where the earlier service is left: the end of the last leg the flow rides on it.
    (An earlier version used the start of that leg, which is a different port whenever a service carries the flow over
    more than one leg and the transshipment rates differ between ports.)"""
    fwd = list(reversed(edges))
    hops: List[Tuple[int, int]] = []             # (service, index of the last leg ridden on it)
    for si, k in fwd:
        if hops and hops[-1][0] == si:
            hops[-1] = (si, k)
        else:
            hops.append((si, k))
    out = []
    for si, k in hops[:-1]:
        ps = services[si]["ports"]
        out.append(ps[(k + 1) % len(ps)])
    return out


def evaluate(data: FfeData, design: Sequence[Dict], *, voyage_basis: str = "per_rotation",
             port_variable_basis: str = "capacity", canal_basis: str = "none",
             include_unused: bool = True, capacity_basis: str = "per_departure", return_flows: bool = False) -> Dict:
    """``design``: [{"ports": [closed rotation without the repeated start], "class": name | "capacity": FFE,
    "vessels": optional fractional vessel count (default: from the formula x frequency),
    "frequency": weekly departures (default 1 = the paper's weekly service)}]."""
    services = []
    for s in design:
        cls = s.get("class") or class_by_capacity(data, s["capacity"])
        ports = list(s["ports"])
        f = float(s.get("frequency", 1))              # weekly departures (the paper has one weekly departure)
        n = float(s["vessels"]) if s.get("vessels") is not None else vessels_needed(data, ports, cls) * f
        cap = data.classes[cls]["cap"] * (n if capacity_basis == "per_vessel" else f)
        services.append({"ports": ports, "class": cls, "cap": cap, "n": n, "f": f})
    flows, rejected = _greedy_mcf(data, services)
    # handling: p_l at origin (load) and destination (unload), p_t per transfer - recomputed from the path
    revenue = handle = served = 0.0
    for di, edges, q in flows:
        d = data.demands[di]
        revenue += q * d["rev"]
        served += q
        handle += q * (data.ports[d["o"]]["pl"] + data.ports[d["d"]]["pl"])
        for port in transfer_ports(services, edges):
            handle += q * data.ports[port]["pt"]
    reject_total = sum(rejected.values())
    penalty = data.penalty_per_unit * reject_total
    service_cost = sum(s["n"] * data.classes[s["class"]]["tc"] * 7.0 for s in services)
    used: Dict[str, float] = defaultdict(float)
    for s in services:
        used[s["class"]] += s["n"]
    unused = sum(-(c["n_avail"] - used.get(n, 0.0)) * c["tc"] * 7.0 for n, c in data.classes.items()) if include_unused else 0.0
    voyage = canal_unknown = 0.0
    for s in services:
        c = data.classes[s["class"]]
        ports = s["ports"]
        legs = list(zip(ports, ports[1:] + [ports[0]]))
        nm = sum(data.dist[l][0] for l in legs)
        sea_days = nm / (c["speed"] * 24.0)
        fuel_rot = sea_days * c["fuel_sea"] + PORT_DAYS * len(ports) * c["fuel_idle"]   # tonnes (price applied by caller)
        port_rot = 0.0
        for p in ports:
            pr = data.ports[p]
            port_rot += pr["pf"] + (pr["pv"] * c["cap"] if port_variable_basis == "capacity" else 0.0)
        mult = s["n"] if voyage_basis == "per_vessel" else s["f"]
        voyage += port_rot * mult
        s["fuel_tonnes_rotation"] = fuel_rot * mult
        if canal_basis != "none":
            cm = s["n"] if canal_basis == "per_vessel" else s["f"]
            for l in legs:
                _, pan, sue = data.dist[l]
                for flag, fee in ((pan, c["panama"]), (sue, c["suez"])):
                    if flag:
                        if fee is None:
                            canal_unknown += 1
                        else:
                            voyage += fee * cm
    if port_variable_basis == "cargo":
        pv_cargo = 0.0
        for di, edges, q in flows:
            d = data.demands[di]
            pv_cargo += q * (data.ports[d["o"]]["pv"] + data.ports[d["d"]]["pv"])
        voyage += pv_cargo
    fuel_t = sum(s["fuel_tonnes_rotation"] for s in services)
    res = {"revenue": revenue, "served_ffe": served, "rejected_ffe": reject_total,
            "demand_ffe": sum(d["ffe"] for d in data.demands), "coverage": served / sum(d["ffe"] for d in data.demands),
            "rejected_penalty": penalty, "handling_and_transshipment": handle, "vessel_service_cost": service_cost,
            "unused_vessel_profit": -unused, "voyage_cost_without_fuel": voyage, "fuel_tonnes_per_week": fuel_t,
            "vessels_used": sum(s["n"] for s in services), "canal_fee_unknown_transits": canal_unknown,
            "interpretation": {"voyage_basis": voyage_basis, "port_variable_basis": port_variable_basis, "canal_basis": canal_basis,
                               "capacity_basis": capacity_basis},
            "note": "net profit = revenue - rejected_penalty - handling - service - voyage(without fuel) - fuel_tonnes*price + unused_vessel_profit"}
    if return_flows:
        # raw material for an independent recomputation (``paper_ledger.objective_ledger``): services, flows, rejections
        res["_services"] = services
        res["_flows"] = [(di, list(edges), q) for di, edges, q in flows]
        res["_rejected"] = dict(rejected)
    return res


def net_profit(r: Dict, fuel_price_usd_per_t: float = 600.0) -> float:
    return (r["revenue"] - r["rejected_penalty"] - r["handling_and_transshipment"] - r["vessel_service_cost"]
            - r["voyage_cost_without_fuel"] - r["fuel_tonnes_per_week"] * fuel_price_usd_per_t + r["unused_vessel_profit"])
