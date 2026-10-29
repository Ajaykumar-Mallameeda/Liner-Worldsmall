"""
Emissions of the plan on screen (2026-10-28, features #14-#18): CO2 per TEU and CII, EU ETS cost, ECA low-sulphur
fuel, slow steaming, and the profit-vs-CO2 front. Read-only, like backend/whatif.py: the recorded services, their
frequencies and vessel classes are fixed; the flow LP re-routes cargo and the ledger prices it.

Fuel (per service and leg, from the engine's own service model)
    sea:   leg sail days x class `Bunker ton per day at designSpeed` x (speed / design speed)^3
    berth: port stay days x class `Idle Consumption ton/day`, at every call
  At design speed this is exactly the engine's fuel. The engine assumes no consumption-vs-speed law; the slow-steaming
  slider (#17) applies the cube law (the fuel model of the LINERLIB paper, Brouer et al. 2014) and is labelled so. The
  speed range is the deployed classes' own LINERLIB min / max speed. A slower plan needs more vessels per weekly
  departure (the ledger's rule); a service whose class runs out of vessels is suspended.

CO2 = fuel x Cf (IMO MEPC.364(79)): 3.114 t/t for the main bunker (heavy fuel / VLSFO), 3.206 t/t for marine gas oil.

ECA (#16): SOx emission control areas (0.10 % S) from Marine Regions (backend/data/eca_zones.geojson, incl. the
  Mediterranean ECA in force 2025-05-01). The share of each leg's sea lane inside an ECA, and berth time in ECA or EU
  ports (EU Sulphur Directive, 0.10 % S at berth), burns marine gas oil at the bunker price + a premium (slider).

EU ETS (#15): CO2 of voyages between two EU/EEA ports of call 100 %, into or out of the EU/EEA 50 %, at berth in an
  EU/EEA port 100 %, times the phase-in (2024 40 %, 2025 70 %, 2026+ 100 %). Tanger Med and East Port Said are not
  ports of call (neighbouring container transhipment ports, Implementing Regulation (EU) 2023/2297): a voyage is
  measured between the ports of call around them. Cost = covered CO2 x EUA price (EUR, slider) x EUR/USD (ECB).

CII (#14): attained AER = CO2 / (DWT x distance) per round voyage of a vessel; reference 1984 x DWT^-0.489, rating
  boundaries 0.83 / 0.94 / 1.07 / 1.19 (container ships, MEPC.353(78) / MEPC.354(78)); reduction factor by year
  (MEPC.338(76) and MEPC.400(83)). LINERLIB gives no deadweight: DWT = capacity x an adjustable t/TEU (assumption).
"""

from __future__ import annotations

import dataclasses
import json
import math
import time
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import searoutes, whatif

router = APIRouter()

CF_MAIN = 3.114          # t CO2 / t fuel, heavy fuel oil (MEPC.364(79))
CF_MGO = 3.206           # t CO2 / t fuel, diesel / gas oil
NM_KM = 1.852
EU_EEA = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
          "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "NO", "IS"}
ETS_NOT_PORTS_OF_CALL = {"MAPTM", "EGPSD"}            # Implementing Regulation (EU) 2023/2297
ETS_PHASE_IN = {2024: 0.40, 2025: 0.70}               # 100 % from 2026
CII_A, CII_C = 1984.0, 0.489
CII_DD = (0.83, 0.94, 1.07, 1.19)
CII_Z = {2023: 5.0, 2024: 7.0, 2025: 9.0, 2026: 11.0, 2027: 13.625, 2028: 16.25, 2029: 18.875, 2030: 21.5}
ECA_FILE = Path(__file__).resolve().parent / "data" / "eca_zones.geojson"
FX_FALLBACK = 1.08
FX_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=1&format=jsondata"
FRONT_POINTS = 7
_fx: Dict = {}


class EmissionsRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})
    speed_factor: float = Field(1.0, ge=0.5, le=1.3)
    eua_eur_per_t: float = Field(75.0, ge=0, le=500)
    eur_usd: Optional[float] = Field(None, gt=0.3, lt=3.0)
    ets: bool = True
    ets_year: int = Field(2026, ge=2024, le=2030)
    eca: bool = True
    mgo_premium_usd_per_t: float = Field(200.0, ge=0, le=1500)
    cii_year: int = Field(2026, ge=2023, le=2030)
    dwt_per_teu: float = Field(13.0, ge=6, le=20)


# ── geometry ──

@lru_cache(maxsize=1)
def eca_zones() -> Dict:
    return json.loads(ECA_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _eca_rings() -> List[Tuple[str, Tuple[float, float, float, float], List[List[Tuple[float, float]]]]]:
    """(zone name, bbox, rings) per polygon; rings[0] outer, the rest holes."""
    out = []
    for f in eca_zones()["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            rings = [[(float(x), float(y)) for x, y in r] for r in poly]
            xs = [p[0] for p in rings[0]]
            ys = [p[1] for p in rings[0]]
            out.append((f["properties"]["name"], (min(xs), min(ys), max(xs), max(ys)), rings))
    return out


def _in_ring(x: float, y: float, ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def eca_at(lon: float, lat: float) -> Optional[str]:
    """Name of the ECA containing (lon, lat), else None. Longitudes are folded into [-180, 180)."""
    x = ((lon + 180.0) % 360.0) - 180.0
    for name, (x0, y0, x1, y1), rings in _eca_rings():
        if x0 <= x <= x1 and y0 <= lat <= y1 and _in_ring(x, lat, rings[0]) \
                and not any(_in_ring(x, lat, h) for h in rings[1:]):
            return name
    return None


def _hav_nm(a, b) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(h)))


_share_cache: Dict[Tuple[str, str, str], Dict] = {}


def eca_share(dataset: str, a: str, b: str, route: Optional[Dict]) -> Dict:
    """Share of the leg's sea lane inside ECAs (sampled every <= 5 nm), and the zones crossed."""
    key = (dataset, a, b)
    if key in _share_cache:
        return _share_cache[key]
    if not route or len(route.get("coords") or []) < 2:
        res = {"share": None, "zones": []}
    else:
        total = inside = 0.0
        zones = set()
        c = route["coords"]
        for p, q in zip(c, c[1:]):
            d = _hav_nm(p, q)
            n = max(1, int(math.ceil(d / 5.0)))
            for k in range(n):
                t = (k + 0.5) / n
                z = eca_at(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
                if z:
                    inside += d / n
                    zones.add(z)
            total += d
        res = {"share": inside / total if total > 0 else 0.0, "zones": sorted(zones)}
    _share_cache[key] = res
    return res


# ── rules ──

def is_eu(port: str) -> bool:
    return str(port)[:2].upper() in EU_EEA


def ets_leg_factor(ports: Tuple[str, ...], i: int) -> float:
    """EU ETS share of leg i (ports[i] -> ports[i+1], closing leg wraps) of a closed rotation, measured between ports
    of call: Tanger Med / East Port Said are skipped back to the previous / forward to the next port of call."""
    n = len(ports)
    real = [p for p in ports if p not in ETS_NOT_PORTS_OF_CALL]
    if len(real) < 2:
        return 0.0
    j = i
    while ports[j % n] in ETS_NOT_PORTS_OF_CALL:
        j -= 1
    k = i + 1
    while ports[k % n] in ETS_NOT_PORTS_OF_CALL:
        k += 1
    e = int(is_eu(ports[j % n])) + int(is_eu(ports[k % n]))
    return {0: 0.0, 1: 0.5, 2: 1.0}[e]


def ets_phase(year: int) -> float:
    return ETS_PHASE_IN.get(year, 1.0 if year >= 2026 else 0.0)


def cii_rating(aer: float, dwt: float, year: int) -> Dict:
    ref = CII_A * dwt ** (-CII_C)
    req = ref * (1 - CII_Z[year] / 100.0)
    ratio = aer / req
    grade = next((g for g, d in zip("ABCD", CII_DD) if ratio <= d), "E")
    return {"attained": aer, "required": req, "ratio": ratio, "rating": grade}


def eur_usd() -> Dict:
    """ECB reference rate (cached 12 h); a labelled fallback when the ECB is unreachable."""
    now = time.time()
    if _fx and now - _fx["at"] < (12 * 3600 if _fx["v"]["date"] else 300):   # retry a fallback after 5 min
        return _fx["v"]
    try:
        with urllib.request.urlopen(urllib.request.Request(FX_URL, headers={"Accept": "application/json"}), timeout=10) as r:
            d = json.load(r)
        series = next(iter(d["dataSets"][0]["series"].values()))
        obs = next(iter(series["observations"].values()))[0]
        date = d["structure"]["dimensions"]["observation"][0]["values"][-1]["id"]
        v = {"rate": float(obs), "date": date, "source": "ECB euro reference rate"}
    except Exception as exc:  # noqa: BLE001 - offline: say so
        v = {"rate": FX_FALLBACK, "date": None, "source": f"fallback (ECB unreachable: {type(exc).__name__})"}
    _fx.update(at=now, v=v)
    return v


# ── evaluation ──

def speed_range(prep: Dict) -> Dict:
    """Common speed factor every deployed class can sail: [max(min/design), min(max/design)]."""
    fleet = {c.vessel_class: c for c in prep["problem"].fleet.classes}
    classes = sorted({prep["models"][i].vessel_class for i in prep["freq"]})
    lo = max((fleet[c].min_speed / fleet[c].design_speed, c) for c in classes)
    hi = min((fleet[c].max_speed / fleet[c].design_speed, c) for c in classes)
    return {"min": round(lo[0], 4), "max": round(hi[0], 4), "min_binding_class": lo[1], "max_binding_class": hi[1]}


def _speed_variant(base: Dict, s: float) -> Tuple[Dict, List[Dict]]:
    if abs(s - 1.0) < 1e-9:
        return base, []
    vkey = f"{base['key']}|speed={s:.4f}"
    if vkey in whatif._cache:
        return whatif._cache[vkey], whatif._cache[vkey]["speed_rejected"]
    a = base["assumptions"]
    a2 = type(a)(**{**a.__dict__, "speed_factor": s})
    prep, rejected = whatif._build(base["problem"], a2, base["services_rec"], base["max_transfers"], base["dataset"])
    sus = [{"id": r["service"], "reason": "; ".join(whatif.REJECT_REASONS.get(str(x), str(x).replace("_", " "))
                                                  for x in (r.get("reasons") or [])) or "cannot be modelled"}
           for r in rejected]
    prep["speed_rejected"] = sus
    prep["key"] = vkey
    if len(whatif._cache) >= whatif.MAX_VARIANTS:
        for k in list(whatif._cache):
            if k != base["key"]:
                del whatif._cache[k]
                break
    whatif._cache[vkey] = prep
    return prep, sus


def evaluate(prep: Dict, req: EmissionsRequest, fx: float) -> Dict:
    ev = whatif._evaluate(prep, 1.0, 1.0)
    fleet = {c.vessel_class: c for c in prep["problem"].fleet.classes}
    lookup = prep["planner"].port_lookup
    a = prep["assumptions"]
    s = a.speed_factor
    cube = s ** 3
    stay = a.port_stay_days
    phase = ets_phase(req.ets_year) if req.ets else 0.0
    pairs = sorted({(f, t) for i in prep["freq"] for f, t, _ in prep["models"][i].legs})
    routes = searoutes.routes_for(prep["dataset"], pairs, ()) if req.eca else {}
    led_by = {r["id"]: r for r in ev["per_service"]}
    rows = []
    tot = dict(main_t=0.0, mgo_t=0.0, co2=0.0, ets_co2=0.0, fuel_usd=0.0, mgo_extra_usd=0.0, ets_usd=0.0, teu_nm=0.0,
               eca_nm=0.0, nm=0.0)
    for i, f in prep["freq"].items():
        m = prep["models"][i]
        vc = fleet[m.vessel_class]
        price = m.fuel_price_usd_per_t
        main_t = mgo_t = co2 = ets_co2 = eca_nm = nm_tot = 0.0
        legs_out = []
        for li, ((fr, to, nm), days) in enumerate(zip(m.legs, m.leg_sail_days)):
            burn = days * vc.bunker_consumption_tons_per_day * cube
            share = 0.0
            if req.eca:
                sh = eca_share(prep["dataset"], fr, to, routes.get(f"{fr}|{to}"))
                share = sh["share"] or 0.0
            leg_mgo = burn * share
            leg_main = burn - leg_mgo
            leg_co2 = leg_main * CF_MAIN + leg_mgo * CF_MGO
            ef = ets_leg_factor(m.ports, li)
            main_t += leg_main
            mgo_t += leg_mgo
            co2 += leg_co2
            ets_co2 += leg_co2 * ef * phase
            eca_nm += nm * share
            nm_tot += nm
            legs_out.append({"from": fr, "to": to, "nm": round(nm, 1), "eca_share": round(share, 3), "ets_factor": ef,
                             "co2_t": round(leg_co2, 2)})
        for p in m.ports:              # one berth stay per call
            burn = stay * vc.idle_consumption_tons_per_day
            pl = lookup.get(p)
            low_s = req.eca and (is_eu(p) or (pl is not None and eca_at(pl.longitude, pl.latitude) is not None))
            c = burn * (CF_MGO if low_s else CF_MAIN)
            if low_s:
                mgo_t += burn
            else:
                main_t += burn
            co2 += c
            if is_eu(p):
                ets_co2 += c * phase
        # per rotation -> per week
        w = dict(main_t=main_t * f, mgo_t=mgo_t * f, co2=co2 * f, ets_co2=ets_co2 * f)
        fuel_usd = (w["main_t"] + w["mgo_t"]) * price
        mgo_extra = w["mgo_t"] * req.mgo_premium_usd_per_t
        ets_usd = w["ets_co2"] * req.eua_eur_per_t * fx
        lr = led_by.get(m.service_id, {})
        teu_nm = sum(lg["load_teu"] * lg["nm"] for lg in lr.get("legs") or [])
        dwt = vc.capacity_teu * req.dwt_per_teu
        aer = (co2 * 1e6) / (dwt * nm_tot) if nm_tot > 0 else float("nan")   # one vessel's round voyage
        cii = cii_rating(aer, dwt, req.cii_year)
        rows.append({
            "id": m.service_id, "vessel_class": m.vessel_class, "departures_per_week": f, "vessels": lr.get("vessels"),
            "speed_knots": round(m.speed_knots, 2), "fuel_t": round(w["main_t"] + w["mgo_t"], 1), "mgo_t": round(w["mgo_t"], 1),
            "co2_t": round(w["co2"], 1), "ets_co2_t": round(w["ets_co2"], 1), "ets_usd": round(ets_usd, 0),
            "fuel_usd": round(fuel_usd, 0), "mgo_extra_usd": round(mgo_extra, 0),
            "eca_share": round(eca_nm / nm_tot, 3) if nm_tot else 0.0,
            "teu_km": round(teu_nm * NM_KM, 0),
            "g_co2_per_teu_km": round(w["co2"] * 1e6 / (teu_nm * NM_KM), 1) if teu_nm > 0 else None,
            "dwt_assumed": round(dwt), "cii": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in cii.items()},
            "profit_ledger": lr.get("profit"), "legs": legs_out,
        })
        for k, v in w.items():
            tot[k] += v
        tot["fuel_usd"] += fuel_usd
        tot["mgo_extra_usd"] += mgo_extra
        tot["ets_usd"] += ets_usd
        tot["teu_nm"] += teu_nm
        tot["eca_nm"] += eca_nm * f
        tot["nm"] += nm_tot * f
    # The ledger prices fuel at the engine's constant daily burn; replace it with this fuel bill (+ MGO premium, + ETS).
    profit = ev["profit"] + ev["fuel_cost"] - tot["fuel_usd"] - tot["mgo_extra_usd"] - tot["ets_usd"]
    grades: Dict[str, int] = {}
    for r in rows:
        grades[r["cii"]["rating"]] = grades.get(r["cii"]["rating"], 0) + 1
    return {
        "speed_factor": s, "valid": ev["valid"], "violations": ev["violations"],
        "revenue": ev["revenue"], "ledger_profit": ev["profit"], "ledger_fuel_cost": ev["fuel_cost"],
        "fuel_cost": tot["fuel_usd"], "mgo_extra_cost": tot["mgo_extra_usd"], "ets_cost": tot["ets_usd"],
        "profit": profit, "served_teu": ev["served_teu"], "vessels": ev["vessels"],
        "fuel_t": tot["main_t"] + tot["mgo_t"], "mgo_t": tot["mgo_t"], "co2_t": tot["co2"], "ets_co2_t": tot["ets_co2"],
        "co2_per_teu_t": tot["co2"] / ev["served_teu"] if ev["served_teu"] > 0 else None,
        "g_co2_per_teu_km": tot["co2"] * 1e6 / (tot["teu_nm"] * NM_KM) if tot["teu_nm"] > 0 else None,
        "eca_share_of_nm": tot["eca_nm"] / tot["nm"] if tot["nm"] > 0 else 0.0,
        "cii_grades": grades, "services": sorted(rows, key=lambda r: -r["co2_t"]),
    }


def _settings(req: EmissionsRequest, fx: Dict, srange: Dict) -> Dict:
    return {"speed_range": srange, "fx": fx, "eua_eur_per_t": req.eua_eur_per_t, "ets": req.ets, "ets_year": req.ets_year,
            "ets_phase": ets_phase(req.ets_year) if req.ets else 0.0, "eca": req.eca,
            "mgo_premium_usd_per_t": req.mgo_premium_usd_per_t, "cii_year": req.cii_year,
            "cii_reduction_pct": CII_Z[req.cii_year], "dwt_per_teu": req.dwt_per_teu,
            "cf": {"main": CF_MAIN, "mgo": CF_MGO}}


def _resolve(req: EmissionsRequest):
    key, out = whatif._run_output(req.run)
    base = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
    srange = speed_range(base)
    fxv = eur_usd() if req.eur_usd is None else {"rate": req.eur_usd, "date": None, "source": "set by the viewer"}
    return base, srange, fxv


@router.post("/api/emissions")
def emissions(req: EmissionsRequest):
    t0 = time.perf_counter()
    with whatif._lock:
        base, srange, fxv = _resolve(req)
        s = req.speed_factor
        if not (srange["min"] - 1e-9 <= s <= srange["max"] + 1e-9):
            raise HTTPException(status_code=422, detail=f"speed factor {s} outside what the deployed classes can sail "
                                f"({srange['min']:.3f}-{srange['max']:.3f})")
        plan = evaluate(base, req, fxv["rate"])
        sprep, suspended = _speed_variant(base, s)
        scen = plan if sprep is base else evaluate(sprep, req, fxv["rate"])
    return {"run": req.run, "dataset": base["dataset"], "settings": _settings(req, fxv, srange),
            "plan": plan, "scenario": scen, "suspended": suspended,
            "runtime_sec": round(time.perf_counter() - t0, 2), "method": __doc__.strip().split("\n\n", 1)[1]}


@router.post("/api/emissions/front")
def front(req: EmissionsRequest):
    """Profit vs CO2 over the speed range (#18), at the request's ETS / ECA / CII settings."""
    t0 = time.perf_counter()
    with whatif._lock:
        base, srange, fxv = _resolve(req)
        lo, hi = srange["min"], min(1.0, srange["max"])
        steps = sorted({round(lo + (hi - lo) * k / (FRONT_POINTS - 1), 4) for k in range(FRONT_POINTS)} | {1.0})
        pts = []
        for s in steps:
            sprep, suspended = _speed_variant(base, s)
            e = evaluate(sprep, req, fxv["rate"])
            pts.append({"speed_factor": s, "profit": e["profit"], "co2_t": e["co2_t"], "served_teu": e["served_teu"],
                        "vessels": e["vessels"], "valid": e["valid"], "ets_cost": e["ets_cost"],
                        "suspended": [x["id"] for x in suspended], "g_co2_per_teu_km": e["g_co2_per_teu_km"]})
    # Pareto: no other point has both more profit and less CO2
    for p in pts:
        p["efficient"] = not any(q is not p and q["profit"] >= p["profit"] and q["co2_t"] <= p["co2_t"]
                                 and (q["profit"] > p["profit"] or q["co2_t"] < p["co2_t"]) for q in pts)
    return {"run": req.run, "dataset": base["dataset"], "settings": _settings(req, fxv, srange), "points": pts,
            "runtime_sec": round(time.perf_counter() - t0, 2)}


@router.get("/api/eca/zones")
def zones():
    return eca_zones()
