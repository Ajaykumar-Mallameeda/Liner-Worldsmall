"""
Sea state and ocean currents along the plan's sea lanes (2026-10-29, features #12 and #13).

POST /api/weather/legs {run, forecast_days}
  Every leg the recorded services sail is laid on its sea lane (backend/searoutes.py; great circle when no lane) and
  cut into pieces of at most SAMPLE_NM. At each piece's midpoint the Open-Meteo Marine API gives the hourly forecast
  for the next days: significant wave height (blend of wave models) and the surface current (MeteoFrance SMOC, 0.08°,
  direction = where the current flows to). Open-Meteo is free for non-commercial use (CC BY 4.0, attribute Open-Meteo
  and the model providers); a commercial deployment needs its API key.

#12 Sea-state risk: the worst forecast wave height met anywhere along the leg in the window, named by the WMO sea
  state code (WMO code table 3700: 4 rough 1.25-2.5 m, 5 very rough 2.5-4 m, 6 high 4-6 m, 7 very high 6-9 m,
  8 phenomenal 9-14 m, 9 > 14 m), with the hours at or above 4 m at the worst point. It is a forecast along the lane
  over the window, not a voyage simulation: the pro-forma schedule says nothing about which day a ship passes where.

#13 Currents in sail time: each piece's mean forecast current is projected on the direction of travel; the leg's sail
  time at the service's speed through the water is sum(d / (V + c)) instead of sum(d / V). The ratio scales the plan's
  own leg sail days, the cycle is re-declared in whole days and vessels follow the ledger's rule
  N = ceil(T x f / 7), so a service whose cycle crosses a day boundary shows the vessel it would gain or save.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend import port_activity, searoutes, whatif

router = APIRouter()

API = "https://marine-api.open-meteo.com/v1/marine"
SAMPLE_NM = 250.0            # piece length along the lane
GRID_DEG = 0.5               # pieces closer than this share one forecast point
BATCH = 200                  # locations per request
TTL = 3 * 3600               # forecast cache
MIN_SOG_SHARE = 0.5          # a current never slows a ship below half its speed through the water
WMO_SEA_STATE = [            # (code, name, upper bound m) — WMO code table 3700
    (0, "calm (glassy)", 0.0), (1, "calm (rippled)", 0.1), (2, "smooth", 0.5), (3, "slight", 1.25),
    (4, "rough", 2.5), (5, "very rough", 4.0), (6, "high", 6.0), (7, "very high", 9.0), (8, "phenomenal", 14.0),
    (9, "phenomenal", float("inf")),
]
RISK = {4: "low", 5: "moderate", 6: "high", 7: "severe", 8: "severe", 9: "severe"}


class WeatherRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})
    forecast_days: int = Field(7, ge=1, le=8)


# ── geometry ──

def _hav_nm(a, b) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(h)))


def bearing(a, b) -> float:
    """Initial course from a to b, degrees clockwise from north."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def pieces(coords: List[List[float]], step: float = SAMPLE_NM) -> List[Dict]:
    """Cut a lane into pieces of <= step nm: length, midpoint and course of each."""
    cum = [0.0]
    for p, q in zip(coords, coords[1:]):
        cum.append(cum[-1] + _hav_nm(p, q))
    total = cum[-1]
    if total <= 0:
        return []

    def at(s: float):
        for i in range(1, len(cum)):
            if cum[i] >= s:
                seg = cum[i] - cum[i - 1]
                t = (s - cum[i - 1]) / seg if seg > 0 else 0.0
                p, q = coords[i - 1], coords[i]
                return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]
        return list(coords[-1])

    n = max(1, int(math.ceil(total / step)))
    out = []
    for k in range(n):
        a, b = total * k / n, total * (k + 1) / n
        pa, pb, pm = at(a), at(b), at((a + b) / 2)
        out.append({"nm": b - a, "mid": pm, "course": bearing(pa, pb)})
    return out


def along_track(u: float, v: float, course: float) -> float:
    """Component of a current (u east, v north, kn) along a course (deg from north); + = with the ship."""
    c = math.radians(course)
    return u * math.sin(c) + v * math.cos(c)


def sea_state(hs: Optional[float]) -> Dict:
    if hs is None:
        return {"code": None, "name": None, "risk": None}
    for code, name, hi in WMO_SEA_STATE:
        if hs <= hi:
            return {"code": code, "name": name, "risk": RISK.get(code, "low")}
    return {"code": 9, "name": "phenomenal", "risk": "severe"}


def time_ratio(parts: List[Dict], speed_kn: float, current_of) -> Optional[float]:
    """Sail time with currents / sail time in still water for one leg at speed_kn through the water."""
    if not parts or speed_kn <= 0:
        return None
    still = with_c = 0.0
    for pc in parts:
        c = current_of(pc)
        sog = max(speed_kn * MIN_SOG_SHARE, speed_kn + (c or 0.0))
        still += pc["nm"] / speed_kn
        with_c += pc["nm"] / sog
    return with_c / still if still > 0 else None


# ── forecast ──

def _key(lon: float, lat: float) -> Tuple[float, float]:
    lon = ((lon + 180.0) % 360.0) - 180.0
    return (round(lon / GRID_DEG) * GRID_DEG, round(lat / GRID_DEG) * GRID_DEG)


def summarise(hourly: Dict) -> Dict:
    """One location's hourly forecast -> worst wave height (and when), hours >= 4 m / >= 6 m, mean current vector."""
    hs = hourly.get("wave_height") or []
    vel = hourly.get("ocean_current_velocity") or []
    dirs = hourly.get("ocean_current_direction") or []
    times = hourly.get("time") or []
    vals = [(h, t) for h, t in zip(hs, times) if h is not None]
    hs_max, hs_at = (max(vals, key=lambda x: x[0]) if vals else (None, None))
    u = v = 0.0
    n = 0
    for s, d in zip(vel, dirs):
        if s is None or d is None:
            continue
        r = math.radians(d)                # direction the current flows TO, clockwise from north
        u += s * math.sin(r)
        v += s * math.cos(r)
        n += 1
    return {"hs_max": hs_max, "hs_max_at": hs_at, "hrs_ge4": sum(1 for h, _ in vals if h >= 4.0),
            "hrs_ge6": sum(1 for h, _ in vals if h >= 6.0), "hours": len(vals),
            "u": u / n if n else None, "v": v / n if n else None}


def _fetch(points: List[Tuple[float, float]], days: int) -> List[Dict]:
    out: List[Dict] = []
    for i in range(0, len(points), BATCH):
        chunk = points[i:i + BATCH]
        q = urllib.parse.urlencode({
            "latitude": ",".join(f"{p[1]:.2f}" for p in chunk), "longitude": ",".join(f"{p[0]:.2f}" for p in chunk),
            "hourly": "wave_height,ocean_current_velocity,ocean_current_direction", "forecast_days": days,
            "wind_speed_unit": "kn", "timezone": "GMT",
        })
        for attempt in range(2):
            try:
                with urllib.request.urlopen(f"{API}?{q}", timeout=120) as r:
                    b = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                # the free tier counts every location as a call (600 / minute): wait out the minute once
                if exc.code != 429 or attempt:
                    raise
                time.sleep(61)
        b = b if isinstance(b, list) else [b]
        out.extend(summarise(x.get("hourly") or {}) for x in b)
    return out


def forecast(points: List[Tuple[float, float]], days: int) -> Tuple[Dict, str]:
    name = "openmeteo_" + hashlib.sha1(json.dumps([days, points]).encode()).hexdigest()[:16] + ".json"
    val, status = port_activity._cached(name, TTL, lambda: _fetch(points, days))
    return val, status


# ── plan ──

def analyse(prep: Dict, days: int) -> Dict:
    lookup = prep["planner"].port_lookup
    pairs = sorted({(f, t) for i in prep["freq"] for f, t, _ in prep["models"][i].legs})
    routes = searoutes.routes_for(prep["dataset"], pairs, ())
    lanes: Dict[Tuple[str, str], Dict] = {}
    for a, b in pairs:
        r = routes.get(f"{a}|{b}")
        if r and len(r.get("coords") or []) >= 2:
            lanes[(a, b)] = {"coords": r["coords"], "source": "searoute"}
        else:
            pa, pb = lookup.get(a), lookup.get(b)
            if pa is None or pb is None:
                continue
            lanes[(a, b)] = {"coords": [[pa.longitude, pa.latitude], [pb.longitude, pb.latitude]], "source": "great-circle"}
        lanes[(a, b)]["pieces"] = pieces(lanes[(a, b)]["coords"])
    keys = sorted({_key(*pc["mid"]) for ln in lanes.values() for pc in ln["pieces"]})
    fc, status = forecast(keys, days)
    data = fc.get("data")
    if not data:
        return {"status": "unavailable", "error": fc.get("error"), "legs": [], "services": [], "points": []}
    at = dict(zip(keys, data))

    def cur(pc):
        s = at.get(_key(*pc["mid"]))
        return along_track(s["u"], s["v"], pc["course"]) if s and s["u"] is not None else None

    legs_out = []
    leg_by: Dict[Tuple[str, str], Dict] = {}
    for (a, b), ln in lanes.items():
        worst, worst_pc = None, None
        for pc in ln["pieces"]:
            s = at.get(_key(*pc["mid"]))
            if s and s["hs_max"] is not None and (worst is None or s["hs_max"] > worst["hs_max"]):
                worst, worst_pc = s, pc
        cs = [c for c in (cur(pc) for pc in ln["pieces"]) if c is not None]
        rec = {"from": a, "to": b, "lane": ln["source"], "nm": round(sum(pc["nm"] for pc in ln["pieces"]), 1),
               "samples": len(ln["pieces"]), "hs_max_m": worst["hs_max"] if worst else None,
               "hs_max_at": worst["hs_max_at"] if worst else None,
               "worst_point": [round(((worst_pc["mid"][0] + 180) % 360) - 180, 2), round(worst_pc["mid"][1], 2)] if worst_pc else None,
               "hrs_ge4_at_worst": worst["hrs_ge4"] if worst else None, "hrs_ge6_at_worst": worst["hrs_ge6"] if worst else None,
               "mean_along_current_kn": round(sum(cs) / len(cs), 3) if cs else None, "services": [], **sea_state(worst["hs_max"] if worst else None)}
        legs_out.append(rec)
        leg_by[(a, b)] = rec

    svc_out = []
    totals = {"vessels_plan": 0, "vessels_current": 0, "sea_days_plan": 0.0, "sea_days_current": 0.0}
    for i, f in prep["freq"].items():
        m = prep["models"][i]
        sea_plan = sea_cur = 0.0
        legs = []
        worst = None
        for (fr, to, nm), d in zip(m.legs, m.leg_sail_days):
            ln = lanes.get((fr, to))
            r = time_ratio(ln["pieces"], m.speed_knots, cur) if ln else None
            dc = d * (r if r else 1.0)
            sea_plan += d
            sea_cur += dc
            lr = leg_by.get((fr, to))
            if lr is not None and m.service_id not in lr["services"]:
                lr["services"].append(m.service_id)
            if lr and lr["hs_max_m"] is not None and (worst is None or lr["hs_max_m"] > worst["hs_max_m"]):
                worst = lr
            legs.append({"from": fr, "to": to, "plan_days": round(d, 3), "current_days": round(dc, 3),
                         "delta_hours": round((dc - d) * 24, 1), "hs_max_m": lr["hs_max_m"] if lr else None,
                         "risk": lr["risk"] if lr else None})
        cyc_plan = int(math.ceil(round(sea_plan + m.port_days, 9)))
        cyc_cur = int(math.ceil(round(sea_cur + m.port_days, 9)))
        v_plan = int(math.ceil(cyc_plan * f / 7.0))
        v_cur = int(math.ceil(cyc_cur * f / 7.0))
        totals["vessels_plan"] += v_plan
        totals["vessels_current"] += v_cur
        totals["sea_days_plan"] += sea_plan * f
        totals["sea_days_current"] += sea_cur * f
        svc_out.append({
            "id": m.service_id, "vessel_class": m.vessel_class, "speed_knots": round(m.speed_knots, 2),
            "departures_per_week": f, "ports": list(m.ports),
            "sea_days_plan": round(sea_plan, 3), "sea_days_current": round(sea_cur, 3),
            "delta_hours": round((sea_cur - sea_plan) * 24, 1),
            "delta_pct": round((sea_cur / sea_plan - 1) * 100, 2) if sea_plan > 0 else None,
            "cycle_days_plan": cyc_plan, "cycle_days_current": cyc_cur, "vessels_plan": v_plan, "vessels_current": v_cur,
            "worst_leg": f"{worst['from']}→{worst['to']}" if worst else None,
            "hs_max_m": worst["hs_max_m"] if worst else None, **{k: (worst or {}).get(k) for k in ("code", "name", "risk")},
            "legs": legs,
        })
    pts = [{"lon": k[0], "lat": k[1], "hs_max_m": s["hs_max"], "hs_max_at": s["hs_max_at"], "hrs_ge4": s["hrs_ge4"],
            "u": None if s["u"] is None else round(s["u"], 3), "v": None if s["v"] is None else round(s["v"], 3),
            **sea_state(s["hs_max"])} for k, s in at.items()]
    risk_counts: Dict[str, int] = {}
    for lr in legs_out:
        if lr["risk"]:
            risk_counts[lr["risk"]] = risk_counts.get(lr["risk"], 0) + 1
    return {
        "status": status, "fetched_on": fc.get("fetched_on"), "error": fc.get("error"),
        "legs": sorted(legs_out, key=lambda r: -(r["hs_max_m"] or -1)),
        "services": sorted(svc_out, key=lambda r: -abs(r["delta_hours"])),
        "points": pts, "risk_counts": risk_counts,
        "totals": {**totals, "sea_days_plan": round(totals["sea_days_plan"], 2),
                   "sea_days_current": round(totals["sea_days_current"], 2)},
    }


@router.post("/api/weather/legs")
def weather_legs(req: WeatherRequest):
    t0 = time.perf_counter()
    with whatif._lock:
        key, out = whatif._run_output(req.run)
        prep = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
    body = analyse(prep, req.forecast_days)
    return {
        "run": req.run, "dataset": prep["dataset"], "forecast_days": req.forecast_days, **body,
        "settings": {"sample_nm": SAMPLE_NM, "grid_deg": GRID_DEG, "min_sog_share": MIN_SOG_SHARE},
        "source": "Open-Meteo Marine API (wave models blend; currents MeteoFrance SMOC 0.08°), CC BY 4.0",
        "source_url": "https://open-meteo.com/en/docs/marine-weather-api",
        "runtime_sec": round(time.perf_counter() - t0, 2),
        "method": __doc__.strip().split("\n\n", 1)[1],
    }
