"""
The plan's ports against outside port data (2026-10-28): #3 IMF PortWatch activity, #6 NGA World Port Index depths and
facilities, #8 UNCTAD port liner shipping connectivity (LSCI).

POST /api/ports/activity {run}
  per port the plan calls:
    plan        weekly calls (sum of the frequencies of the services calling), services, TEU loaded / discharged /
                transhipped per week (flow LP of the What-if baseline), deepest class draft calling, LINERLIB port draft
    portwatch   IMF PortWatch port (matched by UN/LOCODE, else the nearest PortWatch port within 30 km, labelled):
                AIS-observed container-ship port calls per week over the last 30 days of data and the same 30 days a year
                earlier, all port calls, import / export (metric tonnes) - plus the plan's calls as a share of the real
                container calls (a sanity check: a plan above 100 % calls more often than all container ships did)
    wpi         NGA World Port Index (pub. 150): channel / cargo-pier / anchorage depth (m), harbour size, container
                cranes and wharves; depths can be decades old, so a shallower WPI depth than the deepest class draft is
                flagged "check", never treated as infeasible (the engine uses the LINERLIB port draft)
    lsci        UNCTADstat port LSCI, last 8 quarters (average Q1 2023 = 100), from backend/data/lsci_ports.json

PortWatch and WPI responses are cached on disk (12 h / 30 days) and served stale, labelled, when the source is down.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import whatif

router = APIRouter()

PW_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services"
PW_PORTS = f"{PW_BASE}/PortWatch_ports_database/FeatureServer/0/query"
PW_DAILY = f"{PW_BASE}/Daily_Ports_Data/FeatureServer/0/query"
WPI_URL = "https://msi.nga.mil/api/publications/world-port-index?output=json"
LSCI_FILE = Path(__file__).resolve().parent / "data" / "lsci_ports.json"
NEAREST_KM = 30.0
TTL_DAILY = 12 * 3600
TTL_PORTS = 7 * 86400
TTL_WPI = 30 * 86400


class ActivityRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})


def _cache_dir() -> Path:
    env = os.environ.get("PORT_DATA_CACHE_DIR")
    if env:
        return Path(env)
    if Path("D:/").exists():
        return Path("D:/liner_scratch_continuation/port_data_cache")
    return Path(__file__).resolve().parent.parent / "data" / "cache" / "port_data"


def _cached(name: str, ttl: float, fetch):
    """(value, status) from a disk cache: 'hit', 'miss' (fetched), or 'stale' (fetch failed, old copy served)."""
    p = _cache_dir() / name
    old = None
    try:
        old = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    if old and time.time() - old.get("fetched_at", 0) < ttl:
        return old, "hit"
    try:
        val = {"fetched_at": time.time(), "fetched_on": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), "data": fetch()}
    except Exception as exc:  # noqa: BLE001
        if old:
            return {**old, "error": f"{type(exc).__name__}: {exc}"}, "stale"
        return {"fetched_at": None, "fetched_on": None, "data": None, "error": f"{type(exc).__name__}: {exc}"}, "unavailable"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(val), encoding="utf-8")
    except OSError:
        pass
    return val, "miss"


def _arcgis(url: str, params: Dict) -> List[Dict]:
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({**params, "returnGeometry": "false", "f": "json", "resultOffset": offset,
                                    "resultRecordCount": 2000})
        with urllib.request.urlopen(f"{url}?{q}", timeout=90) as r:
            body = json.loads(r.read().decode("utf-8"))
        if "error" in body:
            raise RuntimeError(body["error"].get("message", "ArcGIS query error"))
        feats = body.get("features") or []
        rows += [f["attributes"] for f in feats]
        if not body.get("exceededTransferLimit") or not feats:
            return rows
        offset += len(feats)


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def _locodes(cell) -> List[str]:
    return [c.replace(" ", "").upper() for c in str(cell or "").replace(";", ",").split(",") if c.strip()]


def match_ports(ports: List[Tuple[str, float, float]], db: List[Dict], key: str, lat: str, lon: str,
                locode_field: str) -> Dict[str, Dict]:
    """code -> {row, match, km}: by UN/LOCODE first, else the nearest row within NEAREST_KM. Several rows can share a
    LOCODE (Singapore's anchorages, Port Klang's outports): the one with the most container vessels wins when the
    source counts them (PortWatch), else the nearest."""
    by_code = defaultdict(list)
    for r in db:
        for c in _locodes(r.get(locode_field)):
            by_code[c].append(r)
    out = {}
    for code, la, lo in ports:
        cands = by_code.get(code) or []
        if cands:
            dist = lambda x: _km(la, lo, float(x[lat]), float(x[lon]))
            r = max(cands, key=lambda x: (float(x.get("vessel_count_container") or 0), -dist(x)))                 if any(x.get("vessel_count_container") for x in cands) else min(cands, key=dist)
            out[code] = {"row": r, "match": "UN/LOCODE" + (f" (1 of {len(cands)})" if len(cands) > 1 else ""),
                         "km": round(dist(r), 1)}
            continue
        best = min(((_km(la, lo, float(x[lat]), float(x[lon])), x) for x in db if x.get(lat) is not None),
                   key=lambda t: t[0], default=None)
        if best and best[0] <= NEAREST_KM:
            out[code] = {"row": best[1], "match": f"nearest within {NEAREST_KM:.0f} km", "km": round(best[0], 1)}
    return out


def _pw_ports() -> List[Dict]:
    return _arcgis(PW_PORTS, {"where": "1=1", "outFields": "portid,portname,country,LOCODE,lat,lon,vessel_count_container"})


def _pw_daily(portids: List[str], today: dt.date) -> List[Dict]:
    """Two windows only (a full year of daily rows times out): the last 45 days, and 330-410 days back, which holds
    the 30 days a year before the last data day (PortWatch runs about a week behind)."""
    ids = ",".join(f"'{p}'" for p in portids)
    d = lambda n: (today - dt.timedelta(days=n)).isoformat()
    where = (f"portid IN ({ids}) AND ((date >= DATE '{d(45)}') OR "
             f"(date >= DATE '{d(410)}' AND date <= DATE '{d(330)}'))")
    return _arcgis(PW_DAILY, {"where": where,
                              "outFields": "date,portid,portcalls_container,portcalls,import,export",
                              "orderByFields": "date ASC"})


def summarise_daily(rows: List[Dict]) -> Dict[str, Dict]:
    """portid -> weekly means over the last 30 days of data and the same 30 days a year earlier."""
    by = defaultdict(dict)
    for r in rows:
        d = r.get("date")
        day = dt.datetime.utcfromtimestamp(d / 1000).date() if isinstance(d, (int, float)) else dt.date.fromisoformat(str(d)[:10])
        by[r["portid"]][day] = r
    out = {}
    for pid, days in by.items():
        last = max(days)

        def window(end):
            return [days[end - dt.timedelta(days=i)] for i in range(30) if end - dt.timedelta(days=i) in days]

        now, before = window(last), window(last - dt.timedelta(days=365))
        wk = lambda xs, k: round(7 * sum(float(x.get(k) or 0) for x in xs) / len(xs), 1) if xs else None
        out[pid] = {"data_through": last.isoformat(), "days": len(now),
                    "container_calls_per_week": wk(now, "portcalls_container"),
                    "container_calls_per_week_year_before": wk(before, "portcalls_container"),
                    "all_calls_per_week": wk(now, "portcalls"),
                    "import_t_per_week": wk(now, "import"), "export_t_per_week": wk(now, "export")}
    return out


def _wpi() -> List[Dict]:
    with urllib.request.urlopen(WPI_URL, timeout=120) as r:
        ports = json.loads(r.read().decode("utf-8"))["ports"]
    keep = ("portNumber", "portName", "countryCode", "unloCode", "ycoord", "xcoord", "harborSize", "harborType",
            "chDepth", "cpDepth", "anDepth", "otDepth", "maxVesselLength", "maxVesselBeam", "maxVesselDraft",
            "loContainer", "cranesContainer", "loWharves", "crFixed", "crMobile", "lifts100")
    return [{k: p.get(k) for k in keep} for p in ports]


@lru_cache(maxsize=1)
def lsci() -> Dict:
    return json.loads(LSCI_FILE.read_text(encoding="utf-8"))


def _num(v) -> Optional[float]:
    try:
        x = float(v)
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


@router.get("/api/ports/locate")
def locate(code: str, lat: float, lon: float):
    """PortWatch's point for one port (feature #9: where to centre the Sentinel-2 view). Same matching as the activity
    route: UN/LOCODE first, else the nearest PortWatch port within NEAREST_KM of the dataset point. Uses the cached
    port list only, so it answers in milliseconds once the list is on disk."""
    code = code.strip().upper()
    db, status = _cached("portwatch_ports.json", TTL_PORTS, _pw_ports)
    m = match_ports([(code, lat, lon)], db["data"] or [], "portid", "lat", "lon", "LOCODE").get(code) if db["data"] else None
    pw = None
    if m:
        r = m["row"]
        pw = {"portid": r["portid"], "name": r["portname"], "country": r.get("country"), "lat": float(r["lat"]),
              "lon": float(r["lon"]), "match": m["match"], "km_from_dataset": m["km"],
              "container_vessels": r.get("vessel_count_container")}
    return {"code": code, "dataset": {"lat": lat, "lon": lon}, "portwatch": pw, "status": status,
            "fetched_on": db.get("fetched_on"), "source": "IMF PortWatch ports (ArcGIS)"}


@router.post("/api/ports/activity")
def activity(req: ActivityRequest):
    t0 = time.perf_counter()
    with whatif._lock:
        key, out = whatif._run_output(req.run)
        prep = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
        ev = whatif._evaluate(prep, 1.0, 1.0, keep_flows=True)
    lookup = prep["planner"].port_lookup
    fleet = {c.vessel_class: c for c in prep["problem"].fleet.classes}
    calls: Dict[str, int] = defaultdict(int)
    services: Dict[str, List[str]] = defaultdict(list)
    draft_class: Dict[str, Tuple[float, str]] = {}
    for i, f in prep["freq"].items():
        m = prep["models"][i]
        d = float(fleet[m.vessel_class].draft or 0)
        for p in m.ports:
            calls[p] += f
            services[p].append(m.service_id)
            if d > draft_class.get(p, (0, ""))[0]:
                draft_class[p] = (d, m.vessel_class)
    load, disc, tranship = defaultdict(float), defaultdict(float), defaultdict(float)
    for _od, segs, teu in ev["flows"]:
        load[segs[0][1]] += teu
        disc[segs[-1][2]] += teu
        for s in segs[1:]:
            tranship[s[1]] += teu
    codes = sorted(calls)
    coords = [(c, float(lookup[c].latitude), float(lookup[c].longitude)) for c in codes if c in lookup]

    pw_db, pw_db_status = _cached("portwatch_ports.json", TTL_PORTS, _pw_ports)
    pw_match = match_ports(coords, pw_db["data"] or [], "portid", "lat", "lon", "LOCODE") if pw_db["data"] else {}
    pids = sorted({m["row"]["portid"] for m in pw_match.values()})
    daily, daily_status = (_cached(f"portwatch_daily_{hashlib.sha1(','.join(pids).encode()).hexdigest()[:12]}.json", TTL_DAILY,
                                   lambda: summarise_daily(_pw_daily(pids, dt.date.today()))) if pids else ({"data": {}}, "none"))
    wpi_db, wpi_status = _cached("wpi.json", TTL_WPI, _wpi)
    wpi_match = match_ports(coords, wpi_db["data"] or [], "portNumber", "ycoord", "xcoord", "unloCode") if wpi_db["data"] else {}
    ls = lsci()

    rows = []
    for c in codes:
        port = lookup.get(c)
        lin_draft = _num(getattr(port, "draft", None))
        dmax, dcls = draft_class.get(c, (None, None))
        row = {"code": c, "name": getattr(port, "name", c),
               "plan": {"calls_per_week": calls[c], "services": sorted(services[c]),
                        "teu_loaded": round(load[c], 1), "teu_discharged": round(disc[c], 1),
                        "teu_transhipped": round(tranship[c], 1),
                        "deepest_class": dcls, "deepest_class_draft_m": dmax, "linerlib_draft_m": lin_draft}}
        pm = pw_match.get(c)
        if pm:
            a = (daily["data"] or {}).get(pm["row"]["portid"]) or {}
            real = a.get("container_calls_per_week")
            prev = a.get("container_calls_per_week_year_before")
            row["portwatch"] = {"portid": pm["row"]["portid"], "name": pm["row"]["portname"], "match": pm["match"], "km": pm["km"],
                                **a, "yoy_pct": round((real - prev) / prev * 100, 1) if real is not None and prev else None,
                                "plan_share_of_container_calls_pct": round(calls[c] / real * 100, 1) if real else None}
        wm = wpi_match.get(c)
        if wm:
            w = wm["row"]
            depths = {k: _num(w.get(k)) for k in ("chDepth", "cpDepth", "anDepth")}
            shallow = [k for k, v in (("channel", depths["chDepth"]), ("cargo pier", depths["cpDepth"]))
                       if v is not None and dmax and v < dmax]
            row["wpi"] = {"port_number": w["portNumber"], "name": w["portName"], "match": wm["match"], "km": wm["km"],
                          "channel_depth_m": depths["chDepth"], "cargo_pier_depth_m": depths["cpDepth"],
                          "anchorage_depth_m": depths["anDepth"], "max_vessel_draft_m": _num(w.get("maxVesselDraft")),
                          "harbor_size": w.get("harborSize"), "container_cargo": w.get("loContainer"),
                          "container_cranes": w.get("cranesContainer"), "wharves": w.get("loWharves"),
                          "check": shallow}
        lp = ls["ports"].get(c)
        if lp:
            row["lsci"] = {"label": lp["label"], "values": lp["values"], "latest": next((v for v in reversed(lp["values"]) if v is not None), None)}
        rows.append(row)
    return {
        "run": req.run, "dataset": prep["dataset"], "ports": rows,
        "sources": {
            "portwatch": {"status": daily_status if pids else pw_db_status, "ports_db": pw_db_status, "fetched_on": daily.get("fetched_on"),
                          "error": daily.get("error") or pw_db.get("error"), "matched": len(pw_match),
                          "name": "IMF PortWatch Daily_Ports_Data (AIS-observed port calls)", "url": "https://portwatch.imf.org"},
            "wpi": {"status": wpi_status, "fetched_on": wpi_db.get("fetched_on"), "error": wpi_db.get("error"), "matched": len(wpi_match),
                    "name": "NGA World Port Index (Pub. 150)", "url": "https://msi.nga.mil/Publications/WPI"},
            "lsci": {"status": "snapshot", "quarters": ls["quarters"], "retrieved": ls["retrieved"], "name": ls["source"],
                     "url": ls["source_url"], "matched": sum(1 for r in rows if "lsci" in r)},
        },
        "runtime_sec": round(time.perf_counter() - t0, 2),
    }
