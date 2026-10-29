"""
Schedule reliability and port congestion, by Monte Carlo (2026-10-29, feature #7).

POST /api/reliability {run, target_on_time_pct, target_late_days, congested_ports, congestion_factor, seed}

Every service sails its pro-forma rotation (the leg sail days of the engine's service model, one port stay per call,
first departure Monday 00:00, round voyage = vessels x 7 / departures; the time beyond sailing and port stays is the
buffer, spent at the first port). Many vessel-rotations are simulated:

  * at each call the vessel may meet a disruption (berth congestion, weather, port productivity): with probability p
    it is held for an exponential time of mean mu days before it can sail on;
  * on each leg the vessel recovers delay by sailing faster, up to its class's LINERLIB max speed:
    recoverable = leg sail days x (1 - service speed / max speed);
  * the buffer at the first port absorbs what is left at the end of the round voyage;
  * a vessel still a whole departure interval (7 / frequency days) or more behind when its next round voyage should
    start is re-phased into the next departure slot - the carrier blanks a sailing, as lines do to restore a
    schedule - and the cargo booked on the blanked sailing waits for that later departure.

A call is on time when the vessel arrives within one day of its scheduled arrival - Sea-Intelligence's definition for
its Global Liner Performance report. p and mu are not guessed: they are fitted so that this plan's simulated network
matches a published market level (default Sea-Intelligence, June 2026: 62.6 % of calls on time, late vessels 5.31 days
late on average). Services then differ by their own structure - buffer, speed headroom, number of calls.

Congestion: the ports named in `congested_ports` get `congestion_factor` x the disruption probability; the fitted p and
mu stay those of the uncongested network, so the scenario shows what the congestion costs the plan.

Cargo: every flow the flow LP routes rides its path's segments. At a transhipment port the cargo needs the engine's
minimum connection time (transshipment_min_hours) and boards the first departure of the next service after that; if
the incoming vessel is late (or the outgoing one leaves early relative to the delayed cargo), it waits for the next
departure, 7 / frequency days later. A TEU is on time when it reaches its destination within one day of the pro-forma
plan. Services are simulated independently of each other.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import whatif

router = APIRouter()

CHAINS = 64                  # parallel vessel chains per service
WARM = 3                     # rotations discarded while the buffer-carried delay settles
MEASURED = 8                 # rotations measured per chain
ON_TIME_DAYS = 1.0
CARGO_SAMPLES = 256
MAX_TRIES = 8                # departures tried at a transhipment port before giving up
DEFAULT_TARGET = {"on_time_pct": 62.6, "late_days": 5.31,
                  "source": "Sea-Intelligence Global Liner Performance, June 2026 (press release 400)",
                  "url": "https://sea-intelligence.com/press-room/400-global-schedule-reliability-drops-to-62-6-in-june-2026"}
_cal_cache: Dict[Tuple, Dict] = {}


class ReliabilityRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})
    target_on_time_pct: float = Field(DEFAULT_TARGET["on_time_pct"], ge=20, le=95)
    target_late_days: float = Field(DEFAULT_TARGET["late_days"], ge=1.5, le=15)
    congested_ports: List[str] = Field(default_factory=list, max_length=20)
    congestion_factor: float = Field(3.0, ge=1, le=10)
    seed: int = Field(1, ge=0, le=10_000)


# ── one service ──

def service_struct(m, f: float, vessels: int, max_speed: float, stay: float) -> Dict:
    sail = np.asarray(m.leg_sail_days, dtype=float)
    n = len(sail)
    dep_t = np.concatenate([[0.0], np.cumsum(sail + stay)[:-1]])        # departure from call i
    arr_t = dep_t + sail                                                 # arrival at call i + 1 (n = back at call 0)
    rv = vessels * 7.0 / f
    rf = max(0.0, 1.0 - m.speed_knots / max_speed) if max_speed > 0 else 0.0
    return {"id": m.service_id, "ports": list(m.ports), "n": n, "f": f, "vessels": vessels, "sail": sail,
            "dep_t": dep_t, "arr_t": arr_t, "round_voyage": rv, "buffer": max(0.0, rv - float(sail.sum()) - n * stay),
            "recover": sail * rf, "recover_frac": rf, "speed": m.speed_knots, "max_speed": max_speed}


def draws(sv: Dict, rng: np.random.Generator) -> Dict:
    shape = (CHAINS, WARM + MEASURED + 1, sv["n"])
    return {"u": rng.random(shape), "e": rng.exponential(1.0, shape)}


def simulate(sv: Dict, dr: Dict, p: np.ndarray, mu: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Arrival delays arr[c, r, i] (at call i + 1) and departure delays dep[c, r, i] (from call i) against the slot the
    vessel sails in, days; slip[c, r] = departure slots skipped (blank sailings) before round voyage r."""
    hold = np.where(dr["u"] < p[None, None, :], dr["e"] * mu, 0.0)
    C, R, n = hold.shape
    arr = np.empty((C, R, n))
    dep = np.empty((C, R, n))
    slip = np.zeros((C, R))
    period = 7.0 / sv["f"]
    d = np.zeros(C)
    for r in range(R):
        k = np.floor(d / period)
        slip[:, r] = k
        d = d - k * period
        cur = d
        for i in range(n):
            dep[:, r, i] = cur
            cur = np.maximum(0.0, cur - sv["recover"][i])
            arr[:, r, i] = cur
            cur = cur + hold[:, r, i]
        d = np.maximum(0.0, cur - sv["buffer"])
    return arr, dep, slip


def call_probs(sv: Dict, p: float, congested: set, factor: float) -> np.ndarray:
    """Disruption probability at the call each leg arrives at."""
    ports = sv["ports"]
    return np.array([min(1.0, p * (factor if ports[(i + 1) % sv["n"]] in congested else 1.0)) for i in range(sv["n"])])


def network_stats(svs: List[Dict], drs: List[Dict], p: float, mu: float, congested: set = frozenset(),
                  factor: float = 1.0, keep: bool = False) -> Dict:
    on = late_sum = late_n = tot = blanks = slots = 0.0
    sims = []
    for sv, dr in zip(svs, drs):
        arr, dep, slip = simulate(sv, dr, call_probs(sv, p, congested, factor), mu)
        blanks += float(slip[:, WARM:WARM + MEASURED].sum()) * sv["f"] / (CHAINS * MEASURED)
        slots += sv["f"]
        a = arr[:, WARM:WARM + MEASURED, :]
        w = sv["f"] / a.size                     # weight: calls per week
        late = a > ON_TIME_DAYS
        on += float((~late).sum()) * w
        late_sum += float(a[late].sum()) * w
        late_n += float(late.sum()) * w
        tot += a.size * w
        if keep:
            sims.append((arr, dep, slip))
    return {"on_time": on / tot if tot else 1.0, "late_days": late_sum / late_n if late_n else 0.0, "sims": sims,
            "blank_share": blanks / slots if slots else 0.0}


def calibrate(svs: List[Dict], drs: List[Dict], target_on: float, target_late: float) -> Dict:
    """mu by bisection on the late vessels' mean delay; inside, p by bisection on the on-time share."""
    def fit_p(mu):
        lo, hi = 0.0, 1.0
        if network_stats(svs, drs, 1.0, mu)["on_time"] > target_on:
            return 1.0
        for _ in range(18):
            mid = (lo + hi) / 2
            if network_stats(svs, drs, mid, mu)["on_time"] > target_on:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lo, hi = 0.05, 40.0
    best = None
    for _ in range(18):
        mu = math.sqrt(lo * hi)
        p = fit_p(mu)
        st = network_stats(svs, drs, p, mu)
        best = (p, mu, st)
        if st["late_days"] < target_late:
            lo = mu
        else:
            hi = mu
    p, mu, st = best
    ok = abs(st["on_time"] - target_on) < 0.01 and abs(st["late_days"] - target_late) < 0.15
    return {"p": p, "mu_days": mu, "on_time": st["on_time"], "late_days": st["late_days"], "matched": ok}


# ── cargo ──

def cargo(path_flows, svs_by_idx: Dict[int, Tuple[Dict, np.ndarray, np.ndarray, np.ndarray]], tmin: float,
          rng: np.random.Generator) -> List[Dict]:
    S = CARGO_SAMPLES
    out = []
    lo_r, hi_r = WARM, WARM + MEASURED          # rotation r, its successor r + 1 exists
    for di, path, teu in path_flows:
        planned = None
        actual = np.zeros(S)
        sched_t = 0.0
        missed = np.zeros(S, dtype=int)
        ok = True
        for k, seg in enumerate(path.segments):
            if seg.service not in svs_by_idx:
                ok = False
                break
            sv, arr, dep, slip = svs_by_idx[seg.service]
            b, a = seg.legs[0], seg.legs[-1]
            wrap = 1 if a < b else 0
            period = 7.0 / sv["f"]
            ride = sv["arr_t"][a] + wrap * sv["round_voyage"] - sv["dep_t"][b]
            if k == 0:
                dep_sched = sv["dep_t"][b]
                c = rng.integers(0, CHAINS, S)
                r = rng.integers(lo_r, hi_r, S)
                # cargo of a blanked sailing leaves with the vessel that takes the slot after it
                actual = dep_sched + dep[c, r, b] + slip[c, r] * period
                sched_t = dep_sched
            else:
                ready_sched = sched_t + tmin
                # first departure of this service from the hub at or after the planned ready time
                kk = math.ceil((ready_sched - sv["dep_t"][b]) / period - 1e-9)
                dep_sched = sv["dep_t"][b] + kk * period
                ready = actual + tmin
                boarded = np.zeros(S, dtype=bool)
                t_dep = np.zeros(S)
                c = np.zeros(S, dtype=int)
                r = np.zeros(S, dtype=int)
                for j in range(MAX_TRIES):
                    cj = rng.integers(0, CHAINS, S)
                    rj = rng.integers(lo_r, hi_r, S)
                    tj = dep_sched + j * period + dep[cj, rj, b] + slip[cj, rj] * period
                    take = (~boarded) & (tj >= ready)
                    t_dep[take], c[take], r[take] = tj[take], cj[take], rj[take]
                    missed[take & (j > 0)] += 1
                    boarded |= take
                if not boarded.all():                       # beyond MAX_TRIES: the last departure tried
                    rest = ~boarded
                    t_dep[rest] = dep_sched + (MAX_TRIES - 1) * period + dep[cj[rest], rj[rest], b] + slip[cj[rest], rj[rest]] * period
                    c[rest], r[rest] = cj[rest], rj[rest]
                    missed[rest] += 1
                actual = t_dep
                sched_t = dep_sched
            # arrival at the segment's end: the same vessel's sampled delay there
            # the same vessel's delay at the segment's end (a later round voyage when the ride wraps past the first port)
            actual = actual - dep[c, r, b] + ride + arr[c, r + wrap, a] + wrap * slip[c, r + wrap] * period
            sched_t = sched_t + ride
        if not ok:
            continue
        planned = sched_t
        delay = actual - planned
        out.append({"od": di, "teu": teu, "kind": path.kind, "services": [svs_by_idx[s.service][0]["id"] for s in path.segments],
                    "hubs": list(path.hubs), "planned_days": planned - _first_dep(path, svs_by_idx),
                    "transit_days_engine": path.transit_days, "delay": delay, "missed": missed})
    return out


def _first_dep(path, svs_by_idx) -> float:
    seg = path.segments[0]
    return svs_by_idx[seg.service][0]["dep_t"][seg.legs[0]]


# ── endpoint ──

def _pct(x: float) -> float:
    return round(100.0 * x, 1)


def analyse(prep: Dict, req: ReliabilityRequest) -> Dict:
    a = prep["assumptions"]
    fleet = {c.vessel_class: c for c in prep["problem"].fleet.classes}
    ev = whatif._evaluate(prep, 1.0, 1.0, keep_paths=True)
    vessels_by = {r["id"]: r.get("vessels") for r in ev["per_service"]}
    rng = np.random.default_rng(req.seed)
    svs, drs, idx = [], [], []
    for i, f in sorted(prep["freq"].items()):
        m = prep["models"][i]
        v = vessels_by.get(m.service_id) or int(math.ceil(m.cycle_time_days * f / 7.0))
        sv = service_struct(m, float(f), int(v), float(fleet[m.vessel_class].max_speed), a.port_stay_days)
        svs.append(sv)
        drs.append(draws(sv, rng))
        idx.append(i)
    if not svs:
        raise HTTPException(status_code=422, detail="the plan operates no service")
    target_on, target_late = req.target_on_time_pct / 100.0, req.target_late_days
    ck = (prep["key"], round(target_on, 4), round(target_late, 3), req.seed)
    cal = _cal_cache.get(ck)
    if cal is None:
        cal = calibrate(svs, drs, target_on, target_late)
        _cal_cache[ck] = cal
    congested = {p.strip().upper() for p in req.congested_ports if p.strip()}
    base = network_stats(svs, drs, cal["p"], cal["mu_days"], keep=True)
    scen = network_stats(svs, drs, cal["p"], cal["mu_days"], congested, req.congestion_factor, keep=True) if congested else None
    tmin = a.transshipment_min_hours / 24.0

    def summary(stats, flagged: set) -> Dict:
        sims = stats["sims"]
        rows, port_acc = [], defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0])  # arr on, total, late sum, late n, dep on
        for sv, (arr, dep, slip) in zip(svs, sims):
            A = arr[:, WARM:WARM + MEASURED, :]
            D = dep[:, WARM:WARM + MEASURED, :]
            dep_on = (D <= ON_TIME_DAYS).mean(axis=(0, 1))          # column j = departure from call j
            for j in range(sv["n"]):
                port_acc[sv["ports"][j]][4] += dep_on[j] * sv["f"]
            late = A > ON_TIME_DAYS
            per_call = (~late).mean(axis=(0, 1))
            for i in range(sv["n"]):
                port = sv["ports"][(i + 1) % sv["n"]]
                acc = port_acc[port]
                acc[0] += per_call[i] * sv["f"]
                acc[1] += sv["f"]
                li = late[:, :, i]
                acc[2] += float(A[:, :, i][li].sum()) / li.size * sv["f"]
                acc[3] += float(li.mean()) * sv["f"]
            wi = int(np.argmin(per_call))
            rows.append({
                "id": sv["id"], "departures_per_week": sv["f"], "vessels": sv["vessels"], "calls": sv["n"],
                "on_time_pct": _pct(float((~late).mean())),
                "late_days": round(float(A[late].mean()), 2) if late.any() else 0.0,
                "p90_delay_days": round(float(np.quantile(A, 0.9)), 2),
                "buffer_days": round(sv["buffer"], 2), "recover_pct": round(100 * sv["recover_frac"], 1),
                "blank_sailings_per_year": round(float(slip[:, WARM:WARM + MEASURED].mean()) * sv["f"] * 52, 1),
                "speed_knots": round(sv["speed"], 2), "max_speed_knots": sv["max_speed"],
                "worst_call": sv["ports"][(wi + 1) % sv["n"]], "worst_call_on_time_pct": _pct(float(per_call[wi])),
            })
        ports = [{"port": p, "calls_per_week": round(v[1], 2), "on_time_pct": _pct(v[0] / v[1]),
                  "departure_on_time_pct": _pct(v[4] / v[1]),
                  "late_days": round(v[2] / v[3], 2) if v[3] > 0 else 0.0, "congested": p in flagged}
                 for p, v in port_acc.items()]
        by_idx = {i: (sv, arr, dep, slip) for i, sv, (arr, dep, slip) in zip(idx, svs, sims)}
        flows = cargo(ev["path_flows"], by_idx, tmin, np.random.default_rng(req.seed + 7))
        tot = sum(fl["teu"] for fl in flows)
        def wmean(fn):
            return sum(fn(fl) * fl["teu"] for fl in flows) / tot if tot else 0.0
        bins = [(-1e9, 1.0, "on time (≤ 1 day)"), (1.0, 3.0, "1–3 days late"), (3.0, 7.0, "3–7 days"),
                (7.0, 14.0, "7–14 days"), (14.0, 1e9, "over 14 days")]
        hist = [{"label": lab, "share_pct": _pct(wmean(lambda fl, lo=lo, hi=hi: float(((fl["delay"] > lo) & (fl["delay"] <= hi)).mean())))}
                for lo, hi, lab in bins]
        demands = prep["problem"].demands
        by_od: Dict[int, Dict] = {}
        for fl in flows:
            o = by_od.setdefault(fl["od"], {"teu": 0.0, "on": 0.0, "miss": 0.0, "paths": 0, "delays": [], "kinds": set(), "via": set()})
            o["teu"] += fl["teu"]
            o["on"] += float((fl["delay"] <= ON_TIME_DAYS).mean()) * fl["teu"]
            o["miss"] += float((fl["missed"] > 0).mean()) * fl["teu"]
            o["paths"] += 1
            o["delays"].append((fl["delay"], fl["teu"]))
            o["kinds"].add(fl["kind"])
            o["via"].update(fl["hubs"])
        ods = []
        for di, o in by_od.items():
            d = demands[di]
            allv = np.concatenate([x for x, _ in o["delays"]])
            wts = np.concatenate([np.full(len(x), t) for x, t in o["delays"]])
            order = np.argsort(allv)
            cw = np.cumsum(wts[order]) / wts.sum()
            p90 = float(allv[order][min(len(cw) - 1, int(np.searchsorted(cw, 0.9)))])
            ods.append({"origin": d.origin, "destination": d.destination, "teu": round(o["teu"], 1),
                        "on_time_pct": _pct(o["on"] / o["teu"]), "missed_connection_pct": _pct(o["miss"] / o["teu"]),
                        "p90_delay_days": round(p90, 2), "paths": o["paths"], "kinds": sorted(o["kinds"]), "via": sorted(o["via"]),
                        "max_transit_days": getattr(d, "max_transit_days", None)})
        tsh = [fl for fl in flows if len(fl["hubs"])]
        tsh_teu = sum(fl["teu"] for fl in tsh)
        return {
            "on_time_pct": _pct(stats["on_time"]), "late_days": round(stats["late_days"], 2),
            "blank_sailings_pct": _pct(stats["blank_share"]),
            "services": sorted(rows, key=lambda r: r["on_time_pct"]),
            "ports": sorted(ports, key=lambda r: (r["departure_on_time_pct"], -r["calls_per_week"])),
            "cargo": {
                "teu": round(tot, 1), "on_time_pct": _pct(wmean(lambda fl: float((fl["delay"] <= ON_TIME_DAYS).mean()))),
                "mean_delay_days": round(wmean(lambda fl: float(fl["delay"].mean())), 2),
                "missed_connection_pct": _pct(sum(float((fl["missed"] > 0).mean()) * fl["teu"] for fl in tsh) / tsh_teu) if tsh_teu else 0.0,
                "transhipped_teu": round(tsh_teu, 1),
                "direct_on_time_pct": _pct(sum(float((fl["delay"] <= ON_TIME_DAYS).mean()) * fl["teu"] for fl in flows if not fl["hubs"]) / max(1e-9, tot - tsh_teu)),
                "transhipped_on_time_pct": _pct(sum(float((fl["delay"] <= ON_TIME_DAYS).mean()) * fl["teu"] for fl in tsh) / tsh_teu) if tsh_teu else None,
                "histogram": hist,
            },
            "ods": sorted(ods, key=lambda r: (r["on_time_pct"], -r["teu"])),
        }

    out = {"calibration": {**{k: (round(v, 4) if isinstance(v, float) else v) for k, v in cal.items()},
                           "target_on_time_pct": req.target_on_time_pct, "target_late_days": req.target_late_days},
           "plan": summary(base, set())}
    if scen is not None:
        out["scenario"] = summary(scen, congested)
        out["scenario"]["congested_ports"] = sorted(congested)
        out["scenario"]["congestion_factor"] = req.congestion_factor
    return out


@router.post("/api/reliability")
def reliability(req: ReliabilityRequest):
    t0 = time.perf_counter()
    with whatif._lock:
        key, out = whatif._run_output(req.run)
        prep = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
        body = analyse(prep, req)
    return {"run": req.run, "dataset": prep["dataset"], **body,
            "settings": {"chains": CHAINS, "warm_rotations": WARM, "measured_rotations": MEASURED,
                         "cargo_samples": CARGO_SAMPLES, "on_time_days": ON_TIME_DAYS, "seed": req.seed,
                         "transshipment_min_hours": prep["assumptions"].transshipment_min_hours},
            "default_target": DEFAULT_TARGET, "runtime_sec": round(time.perf_counter() - t0, 2),
            "method": __doc__.strip().split("\n\n", 1)[1]}
