"""
War-risk premiums and piracy incidents on the plan's lanes (2026-10-29, feature #19).

Listed areas: Joint War Committee circular JWLA-035 (16 September 2026), "JWC Listed Areas, Hull War, Piracy,
Terrorism and Related Perils" (lmalloyds.com). Hull war cover for a voyage into a listed area needs an additional
premium (AP), quoted as a percentage of the insured hull value for a 7-day period. The defined waters are drawn
from the circular's own coordinates:

  Persian/Arabian Gulf, Gulf of Oman, Indian Ocean, Gulf of Aden and Southern Red Sea: the Red Sea south of 25.5 N;
    from the Pakistan coast at 25 19'15"N 65 E; 10 48'N 65 E; 10 48'N 60 15'E; 6 45'S 48 45'E; Somalia border
    1 40'S 41 34'E (the land side of the polygon is irrelevant: lanes do not cross land).
  Gulf of Guinea: Togo coast 6 06'45"N 1 12'E; 0 40'S 3 00'E; Cape Lopez 0 40'S 8 42'E.
  Cabo Delgado: Mozambique/Tanzania territorial sea between 10 19.6'S and 13 30'S.
  Black Sea and Sea of Azov, excluding the territorial waters of countries other than Russia and Ukraine
    (approximate polygon: the circular defines it in words, not coordinates).
  Named countries (ports and waters to 12 nm): Benin, Djibouti, Eritrea, Libya, Nigeria, Somalia, Sudan, Togo,
    Bahrain, Iran, Iraq, Israel, Kuwait, Lebanon, Oman, Qatar, Saudi Arabia, Syria, UAE, Yemen, Russia, Venezuela.

Rates: underwriters quote per vessel and voyage; the defaults are published market levels (source and date on each)
and every one can be changed in the request. Inside the big Indian Ocean area the market quotes very different
levels (Strait of Hormuz / Gulf 7.5-10 %, Bab al-Mandab 0.5 %, off western Saudi Arabia 0.1 %, S&P Global / Marsh,
July 2026), so that area is split into three rate zones, but one visit to it is charged once, at the highest rate
of the zones the visit touches.

Model: a service's rotation is walked leg by leg on its sea lane (backend/searoutes.py, great circle when no lane).
A visit is a run of consecutive legs touching the same listed area (a leg touches it when any point of its lane,
sampled every 0.1 deg, or its arrival port lies inside). Each visit costs one 7-day premium per departure:
weekly cost = departures per week x sum over visits (rate x hull value). A port call in a named country outside the
drawn areas counts as its own visit. Hull value = USD per TEU of capacity x the class capacity (an assumption the
request sets). Not modelled: visits longer than 7 days needing extra cover, crew war bonus, cargo war cover, K&R.

Piracy incidents: NGA Anti-Shipping Activity Messages (ASAM, msi.nga.mil) for the last 12 months, cached on disk;
when the service is down the response says so and the cost model is unaffected.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend import port_activity, searoutes

JWC_CIRCULAR = {"id": "JWLA-035", "date": "2026-09-16",
                "url": "https://lmalloyds.com/wp-content/uploads/2026/09/JWLA-035-Black-Sea.pdf"}

IO_AREA = [(32.0, 25.5), (39.5, 25.5), (47.5, 31.5), (57.5, 31.5), (65.0, 27.0), (65.0, 25.3208), (65.0, 10.8),
           (60.25, 10.8), (48.75, -6.75), (41.5667, -1.6667), (35.0, 8.0), (32.0, 20.0)]

AREAS = {
    "indian_ocean": {"label": "Persian/Arabian Gulf, Gulf of Oman, Indian Ocean, Gulf of Aden and Southern Red Sea",
                     "polygon": IO_AREA, "drawn": "JWLA-035 coordinates"},
    "gulf_of_guinea": {"label": "Gulf of Guinea", "drawn": "JWLA-035 coordinates",
                       "polygon": [(1.2, 6.1125), (3.0, -0.6667), (8.7, -0.6667), (9.8, 1.0), (10.5, 4.5), (9.0, 7.0),
                                   (1.2, 7.0)]},
    "cabo_delgado": {"label": "Cabo Delgado", "drawn": "JWLA-035 coordinates",
                     "polygon": [(40.315, -10.327), (40.574, -10.172), (40.828, -13.4995), (40.527, -13.5),
                                 (39.5, -12.0)]},
    "black_sea": {"label": "Black Sea and Sea of Azov (Russian and Ukrainian waters, high seas)",
                  "drawn": "approximate (the circular defines it in words)",
                  "polygon": [(28.35, 41.95), (28.35, 43.7), (28.9, 44.1), (29.75, 45.15), (30.3, 46.6), (33.5, 46.2),
                              (35.3, 47.3), (39.4, 47.4), (38.3, 45.9), (37.6, 44.6), (39.95, 43.4), (41.3, 42.0),
                              (41.3, 41.75), (36.0, 42.3), (35.0, 42.25), (33.0, 42.2), (31.0, 41.5), (29.2, 41.45)]},
}

# rate zones: (id, area, label, test on (lon, lat) inside the area, default % of hull value, source)
SRC_SP = ("S&P Global / Marsh, reported by Al Jazeera 23 Jul 2026 (aljazeera.com/economy/2026/7/23)")
ZONES = [
    {"id": "gulf_hormuz", "area": "indian_ocean", "label": "Persian Gulf, Strait of Hormuz, Gulf of Oman",
     "rule": "lat >= 22.4 and lon >= 47.5", "default_pct": 7.5, "source": SRC_SP + ": 7.5-10 % (was 1-3 %)"},
    {"id": "red_sea_central", "area": "indian_ocean", "label": "Red Sea 15.5-25.5 N (off western Saudi Arabia)",
     "rule": "lon < 44 and lat >= 15.5", "default_pct": 0.1, "source": SRC_SP + ": 0.1 %"},
    {"id": "bab_al_mandab", "area": "indian_ocean", "label": "Bab al-Mandab, Gulf of Aden, NW Indian Ocean",
     "rule": "rest of the area", "default_pct": 0.5, "source": SRC_SP + ": 0.5 % (up to 1 % reported Oct 2026)"},
    {"id": "black_sea", "area": "black_sea", "label": "Black Sea and Sea of Azov", "rule": "whole area",
     "default_pct": 1.0, "source": "The Insurer 21 Jul 2026: above 1 % (0.6-2 % reported Jul-Aug 2026)"},
    {"id": "gulf_of_guinea", "area": "gulf_of_guinea", "label": "Gulf of Guinea", "rule": "whole area",
     "default_pct": 0.3, "source": "industry guides 2025: 0.3-0.7 % per voyage (no 2026 figure found)"},
    {"id": "cabo_delgado", "area": "cabo_delgado", "label": "Cabo Delgado", "rule": "whole area",
     "default_pct": 0.3, "source": "assumption: no published figure found (set to the Gulf of Guinea level)"},
]
NAMED_COUNTRIES = {"BJ": "Benin", "DJ": "Djibouti", "ER": "Eritrea", "LY": "Libya", "NG": "Nigeria", "SO": "Somalia",
                   "SD": "Sudan", "TG": "Togo", "BH": "Bahrain", "IR": "Iran", "IQ": "Iraq", "IL": "Israel",
                   "KW": "Kuwait", "LB": "Lebanon", "OM": "Oman", "QA": "Qatar", "SA": "Saudi Arabia", "SY": "Syria",
                   "AE": "United Arab Emirates", "YE": "Yemen", "RU": "Russia", "VE": "Venezuela"}
NAMED_CALL = {"default_pct": 0.7, "source": "Israel 7-day call 0.7-1.0 % (2025 reports); applied to every "
                                            "named-country call outside the drawn areas (assumption)"}
HULL_USD_PER_TEU = 15000.0     # assumption: insured hull value per TEU of capacity (set it to the fleet's values)
SAMPLE_DEG = 0.1
ASAM_URL = "https://msi.nga.mil/api/publications/asam?output=json"
TTL_ASAM = 24 * 3600


# ── geometry ──

def inside(lon: np.ndarray, lat: np.ndarray, poly: Sequence[Tuple[float, float]]) -> np.ndarray:
    """Ray casting for many points against one polygon (lon, lat in degrees, lon in -180..180)."""
    x = np.asarray(lon, float)
    y = np.asarray(lat, float)
    res = np.zeros(x.shape, bool)
    pts = list(poly)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        cross = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        res ^= cross & (x < xi)
    return res


def densify(coords: List[List[float]], step: float = SAMPLE_DEG) -> Tuple[np.ndarray, np.ndarray]:
    """Points along a polyline every `step` degrees, longitudes folded into -180..180."""
    xs, ys = [], []
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        n = max(1, int(np.ceil(max(abs(x2 - x1), abs(y2 - y1)) / step)))
        t = np.linspace(0, 1, n, endpoint=False)
        xs.append(x1 + (x2 - x1) * t)
        ys.append(y1 + (y2 - y1) * t)
    xs.append(np.array([coords[-1][0]]))
    ys.append(np.array([coords[-1][1]]))
    x = np.concatenate(xs)
    return ((x + 180.0) % 360.0) - 180.0, np.concatenate(ys)


def zone_of(lon: np.ndarray, lat: np.ndarray, area: str) -> np.ndarray:
    """Rate-zone index (into ZONES) per point of an area, -1 outside it."""
    out = np.full(np.shape(lon), -1, int)
    ins = inside(lon, lat, AREAS[area]["polygon"])
    if area == "indian_ocean":
        z_gulf = next(i for i, z in enumerate(ZONES) if z["id"] == "gulf_hormuz")
        z_red = next(i for i, z in enumerate(ZONES) if z["id"] == "red_sea_central")
        z_bam = next(i for i, z in enumerate(ZONES) if z["id"] == "bab_al_mandab")
        gulf = ins & (lat >= 22.4) & (lon >= 47.5)
        red = ins & ~gulf & (lon < 44) & (lat >= 15.5)
        out[ins] = z_bam
        out[red] = z_red
        out[gulf] = z_gulf
    else:
        out[ins] = next(i for i, z in enumerate(ZONES) if z["area"] == area)
    return out


def leg_zones(coords: List[List[float]]) -> Dict[str, List[int]]:
    """{area: [rate-zone indices touched]} for one leg's lane."""
    lon, lat = densify(coords)
    out = {}
    for area in AREAS:
        z = zone_of(lon, lat, area)
        hit = sorted(set(int(v) for v in z if v >= 0))
        if hit:
            out[area] = hit
    return out


# ── cost model ──

def rates_with(overrides: Optional[Dict[str, float]]) -> Dict[str, float]:
    r = {z["id"]: z["default_pct"] for z in ZONES}
    r["named_call"] = NAMED_CALL["default_pct"]
    for k, v in (overrides or {}).items():
        if k in r and v is not None and 0 <= float(v) <= 50:
            r[k] = float(v)
    return r


def visits(rotation: Sequence[str], legs: Dict[Tuple[str, str], Dict[str, List[int]]],
           port_area: Dict[str, Optional[str]]) -> List[Dict]:
    """Visits of one rotation to listed areas: runs of consecutive legs touching an area (cyclic), each with the
    rate zones it touches; plus named-country calls outside the drawn areas."""
    n = len(rotation)
    pairs = [(rotation[i], rotation[(i + 1) % n]) for i in range(n)]
    out = []
    for area in AREAS:
        touch = [area in legs.get(p, {}) for p in pairs]
        if not any(touch):
            continue
        if all(touch):
            runs = [list(range(n))]
        else:
            start = touch.index(False)       # walk from a leg outside the area so runs never wrap mid-way
            runs, cur = [], []
            for k in range(1, n + 1):
                i = (start + k) % n
                if touch[i]:
                    cur.append(i)
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                runs.append(cur)
        for run in runs:
            zones = sorted({z for i in run for z in legs[pairs[i]][area]})
            out.append({"area": area, "legs": [list(pairs[i]) for i in run], "zones": [ZONES[z]["id"] for z in zones]})
    for p in rotation:
        c = p[:2]
        if c in NAMED_COUNTRIES and port_area.get(p) is None:
            out.append({"area": "named_country", "port": p, "country": NAMED_COUNTRIES[c], "zones": ["named_call"]})
    return out


def service_costs(prep: Dict, rates: Dict[str, float], hull_usd_per_teu: float,
                  avoid: Tuple[str, ...] = ()) -> Dict:
    """War-risk exposure and weekly premium per operated service of `prep` (whatif._prepare / _variant)."""
    lookup = prep["planner"].port_lookup
    fleet = {c.vessel_class: c for c in prep["problem"].fleet.classes}
    pairs = sorted({(f, t) for i in prep["freq"] for f, t, _ in prep["models"][i].legs})
    routes = searoutes.routes_for(prep["dataset"], pairs, avoid)
    legs: Dict[Tuple[str, str], Dict[str, List[int]]] = {}
    lane_src = {}
    for a, b in pairs:
        r = routes.get(f"{a}|{b}")
        if r and len(r.get("coords") or []) >= 2:
            coords, lane_src[(a, b)] = r["coords"], "searoute"
        else:
            pa, pb = lookup.get(a), lookup.get(b)
            if pa is None or pb is None:
                continue
            coords, lane_src[(a, b)] = [[pa.longitude, pa.latitude], [pb.longitude, pb.latitude]], "great-circle"
        legs[(a, b)] = leg_zones(coords)
    port_area = {}
    for p, rec in lookup.items():
        port_area[p] = next((a for a in AREAS if inside(np.array([rec.longitude]), np.array([rec.latitude]),
                                                         AREAS[a]["polygon"])[0]), None)
    services, by_zone = [], {}
    total = 0.0
    for i, f in prep["freq"].items():
        m = prep["models"][i]
        cap = float(fleet[m.vessel_class].capacity_teu or 0)
        hull = hull_usd_per_teu * cap
        vs = visits(list(m.ports), legs, port_area)
        if not vs:
            continue
        rows = []
        for v in vs:
            pct = max(rates[z] for z in v["zones"])
            top = max(v["zones"], key=lambda z: rates[z])
            per_visit = pct / 100.0 * hull
            rows.append({**v, "rate_pct": pct, "rate_zone": top, "premium_per_visit": round(per_visit),
                         "weekly": round(per_visit * f)})
            agg = by_zone.setdefault(top, {"zone": top, "visits_per_week": 0.0, "weekly": 0.0, "services": set()})
            agg["visits_per_week"] += f
            agg["weekly"] += per_visit * f
            agg["services"].add(m.service_id)
        weekly = sum(r["weekly"] for r in rows)
        total += weekly
        services.append({"id": m.service_id, "vessel_class": m.vessel_class, "frequency_per_week": f,
                         "hull_value_usd": round(hull), "visits": rows, "weekly": round(weekly)})
    services.sort(key=lambda s: -s["weekly"])
    zones = [{**v, "services": sorted(v["services"]), "weekly": round(v["weekly"])} for v in by_zone.values()]
    zones.sort(key=lambda z: -z["weekly"])
    return {"weekly_total": round(total), "per_service": {s["id"]: s["weekly"] for s in services},
            "services": services, "zones": zones, "rates_pct": rates, "hull_usd_per_teu": hull_usd_per_teu,
            "legs_on_great_circle": sum(1 for v in lane_src.values() if v == "great-circle")}


def describe() -> Dict:
    """Areas, rate zones (with defaults and sources) and named countries, for the UI and the map."""
    return {
        "circular": JWC_CIRCULAR,
        "areas": [{"id": k, "label": v["label"], "drawn": v["drawn"], "polygon": [list(p) for p in v["polygon"]]}
                  for k, v in AREAS.items()],
        "zones": [{k: z[k] for k in ("id", "area", "label", "rule", "default_pct", "source")} for z in ZONES],
        "named_countries": NAMED_COUNTRIES, "named_call": NAMED_CALL, "hull_usd_per_teu": HULL_USD_PER_TEU,
        "basis": "additional premium per 7-day visit, % of insured hull value; hull value = USD/TEU x capacity",
    }


# ── piracy incidents (NGA ASAM) ──

def _asam_fetch() -> List[Dict]:
    req = urllib.request.Request(ASAM_URL, headers={"User-Agent": "liner-shipping-optimizer/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    data = json.loads(body)
    rows = data.get("asam") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("unexpected ASAM payload")
    return rows


def asam_incidents(days: int = 365, today: Optional[dt.date] = None) -> Dict:
    val, status = port_activity._cached("nga_asam.json", TTL_ASAM, _asam_fetch)
    rows = val.get("data")
    if not rows:
        return {"status": "unavailable", "error": val.get("error"), "incidents": [], "source": ASAM_URL}
    today = today or dt.date.today()
    since = today - dt.timedelta(days=days)
    out = []
    for r in rows:
        try:
            d = dt.date.fromisoformat(str(r.get("date"))[:10])
            lat, lon = float(r.get("latitude")), float(r.get("longitude"))
        except (TypeError, ValueError):
            continue
        if d >= since:
            out.append({"date": d.isoformat(), "lat": lat, "lon": lon, "victim": r.get("victim"),
                        "hostility": r.get("hostility"), "navarea": r.get("navArea"),
                        "description": (r.get("description") or "")[:400]})
    out.sort(key=lambda x: x["date"], reverse=True)
    return {"status": status, "fetched_on": val.get("fetched_on"), "incidents": out, "days": days, "source": ASAM_URL}


# ── routes ──

from fastapi import APIRouter, Query  # noqa: E402

router = APIRouter()


@router.get("/api/war-risk/areas")
def get_areas():
    return describe()


@router.get("/api/war-risk/piracy")
def get_piracy(days: int = Query(365, ge=7, le=1825)):
    return asam_incidents(days)
