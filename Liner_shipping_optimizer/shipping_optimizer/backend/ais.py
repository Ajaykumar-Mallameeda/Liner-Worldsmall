"""
Live AIS vessel positions for the map (2026-10-28, feature #5).

GET /api/ais/live
  Digitraffic (Fintraffic, Finland; open data, CC BY 4.0, no key): every vessel its AIS network heard in the Baltic and
  approaches, joined to its static data (name, AIS ship type, destination, draught). Positions are cached 60 s and
  vessel metadata 1 h, so the map can poll once a minute without loading the service.

Other providers named in the request (#5): AISHub needs an account that contributes a receiving station, and Global
Fishing Watch needs an API token and serves AIS-derived data days late (not live positions). Neither is configured;
the response says so instead of pretending to cover the world.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import time
import urllib.request
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()

LOC_URL = "https://meri.digitraffic.fi/api/ais/v1/locations"
VES_URL = "https://meri.digitraffic.fi/api/ais/v1/vessels"
HEADERS = {"Accept-Encoding": "gzip", "Digitraffic-User": "liner-shipping-optimizer/1.0"}
TTL_LOC = 60
TTL_VES = 3600
MAX_AGE_MIN = 60          # positions older than this are dropped (vessel left coverage)
_mem: Dict[str, Dict] = {}


def _get(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _cached(key: str, ttl: float, url: str):
    e = _mem.get(key)
    if e and time.time() - e["at"] < ttl:
        return e["v"], "hit"
    try:
        v = _get(url)
    except Exception as exc:  # noqa: BLE001
        if e:
            return e["v"], f"stale ({type(exc).__name__})"
        raise
    _mem[key] = {"at": time.time(), "v": v}
    return v, "miss"


def ship_category(t: Optional[int]) -> str:
    """AIS ship type (ITU-R M.1371) -> a coarse category; AIS has no separate code for container ships."""
    t = int(t or 0)
    if 70 <= t <= 79:
        return "cargo"
    if 80 <= t <= 89:
        return "tanker"
    if 60 <= t <= 69:
        return "passenger"
    if t == 30:
        return "fishing"
    if t in (31, 32, 52):
        return "tug / towing"
    if 50 <= t <= 59:
        return "service"
    return "other"


def build(locs: Dict, vessels: List[Dict], now_ms: Optional[float] = None) -> Dict:
    now_ms = now_ms if now_ms is not None else time.time() * 1000
    meta = {v["mmsi"]: v for v in vessels}
    out, counts = [], {}
    for f in locs.get("features") or []:
        p = f.get("properties") or {}
        lon, lat = (f.get("geometry") or {}).get("coordinates", [None, None])[:2]
        ts = p.get("timestampExternal")
        if lon is None or lat is None or ts is None:
            continue
        age = (now_ms - ts) / 60000.0
        if age > MAX_AGE_MIN:
            continue
        m = meta.get(p.get("mmsi"), {})
        cat = ship_category(m.get("shipType"))
        counts[cat] = counts.get(cat, 0) + 1
        hdg = p.get("heading")
        out.append({
            "mmsi": p.get("mmsi"), "name": (m.get("name") or "").strip() or None, "lon": lon, "lat": lat,
            "sog_kn": p.get("sog"), "cog": p.get("cog"), "heading": hdg if hdg is not None and hdg < 360 else p.get("cog"),
            "ship_type": m.get("shipType"), "category": cat, "destination": (m.get("destination") or "").strip() or None,
            "draught_m": (m.get("draught") / 10.0) if m.get("draught") else None, "age_min": round(age, 1),
        })
    return {"vessels": out, "counts": counts}


@router.get("/api/ais/live")
def live():
    try:
        locs, s1 = _cached("loc", TTL_LOC, LOC_URL)
        ves, s2 = _cached("ves", TTL_VES, VES_URL)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Digitraffic AIS unreachable: {type(exc).__name__}: {exc}")
    body = build(locs, ves)
    upd = locs.get("dataUpdatedTime")
    return {
        **body,
        "source": "Digitraffic marine AIS (Fintraffic), open data CC BY 4.0",
        "source_url": "https://www.digitraffic.fi/en/marine-traffic/",
        "coverage": "Baltic Sea and approaches heard by the Finnish AIS network",
        "data_updated": upd, "fetched_on": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cache": {"positions": s1, "vessels": s2}, "max_age_min": MAX_AGE_MIN,
        "providers": {
            "digitraffic": "live (no key)",
            "aishub": "not configured: needs an AISHub account that shares a receiving station",
            "gfw": "not used: Global Fishing Watch needs an API token and its AIS data is days late, not live positions",
        },
    }
