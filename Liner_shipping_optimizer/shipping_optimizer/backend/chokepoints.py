"""
Chokepoints: how exposed the plan is, what real traffic through them looks like, and which closures or port
losses hurt most (read-only).

POST /api/chokepoints/exposure   {run}            passages the plan's legs cross, with TEU / week through each
GET  /api/chokepoints/portwatch                   IMF PortWatch daily transit calls (last 30 days vs a year ago)
POST /api/resilience             {run, target, limit}
     target "passages": close each passage the plan crosses, one at a time (with the preset's detour rule)
     target "ports":    close each of the `limit` most-called ports, one at a time
     Every case is the what-if re-evaluation (backend/whatif.py: flow LP over every valid path, priced by the
     ledger) of the recorded plan with that one disruption, ranked by the weekly profit it costs.

Leg loads come from the same re-evaluation at 1x demand / 1x fuel as the what-if baseline; passages from
the sea-lane network (backend/searoutes.py), with Suez / Panama on LINERLIB's own canal flags.

PortWatch (IMF / University of Oxford, https://portwatch.imf.org) counts AIS-observed transit calls per day.
It is cached on disk for 12 hours (PORTWATCH_CACHE_DIR, default D:/liner_scratch_continuation when D: exists).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import disruption, searoutes, whatif

router = APIRouter()

# searoute passage id -> PortWatch chokepoint, and a point to draw it at ([lon, lat]).
CHOKEPOINTS: Dict[str, Dict] = {
    "suez": {"name": "Suez Canal", "portwatch": "chokepoint1", "at": [32.35, 30.6]},
    "panama": {"name": "Panama Canal", "portwatch": "chokepoint2", "at": [-79.7, 9.1]},
    "bosporus": {"name": "Bosporus", "portwatch": "chokepoint3", "at": [29.05, 41.12]},
    "babalmandab": {"name": "Bab-el-Mandeb", "portwatch": "chokepoint4", "at": [43.4, 12.6]},
    "malacca": {"name": "Strait of Malacca", "portwatch": "chokepoint5", "at": [100.8, 2.6]},
    "ormuz": {"name": "Strait of Hormuz", "portwatch": "chokepoint6", "at": [56.4, 26.5]},
    "south_africa": {"name": "Cape of Good Hope", "portwatch": "chokepoint7", "at": [18.5, -34.8]},
    "gibraltar": {"name": "Strait of Gibraltar", "portwatch": "chokepoint8", "at": [-5.6, 35.95]},
    "sunda": {"name": "Sunda Strait", "portwatch": "chokepoint19", "at": [105.8, -6.0]},
    "chili": {"name": "Strait of Magellan", "portwatch": "chokepoint21", "at": [-70.6, -53.4]},
}
PORTWATCH_URL = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
                 "Daily_Chokepoints_Data/FeatureServer/0/query")
PORTWATCH_TTL_SEC = 12 * 3600
PORTWATCH_DAYS = 400


class RunRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})


class ResilienceRequest(RunRequest):
    target: str = Field("passages", pattern="^(passages|ports)$")
    limit: int = Field(25, ge=1, le=60)


def _exposure(prep: Dict, base: Dict) -> Dict:
    legs = [(lg["from"], lg["to"], lg["load_teu"], s["id"]) for s in base["per_service"] for lg in s["legs"]]
    freq = {prep["models"][i].service_id: f for i, f in prep["freq"].items()}
    routes = searoutes.routes_for(prep["dataset"], sorted({(a, b) for a, b, _, _ in legs}), ())
    by: Dict[str, Dict] = defaultdict(lambda: {"teu_per_week": 0.0, "services": set(), "legs": [], "sailings_per_week": 0})
    carried_teu_legs = sum(t for _, _, t, _ in legs)
    for a, b, teu, sid in legs:
        r = routes.get(f"{a}|{b}")
        if not r:
            continue
        for p in disruption.crossed(r, list(CHOKEPOINTS)):
            e = by[p]
            e["teu_per_week"] += teu
            e["services"].add(sid)
            e["sailings_per_week"] += freq.get(sid, 0)
            e["legs"].append({"from": a, "to": b, "service": sid, "teu": round(teu, 1)})
    out = []
    for p, e in by.items():
        out.append({"id": p, "name": CHOKEPOINTS[p]["name"], "at": CHOKEPOINTS[p]["at"],
                    "teu_per_week": round(e["teu_per_week"], 1),
                    "share_of_teu_legs_pct": round(100.0 * e["teu_per_week"] / carried_teu_legs, 2) if carried_teu_legs else None,
                    "services": sorted(e["services"]), "sailings_per_week": e["sailings_per_week"],
                    "legs": sorted(e["legs"], key=lambda x: -x["teu"])[:12],
                    "preset": next((k for k, v in disruption.PRESETS.items() if v["closed"] == [p]), None)})
    out.sort(key=lambda x: -x["teu_per_week"])
    return {"passages": out, "carried_teu_legs_per_week": round(carried_teu_legs, 1),
            "legs_without_sea_lane": sum(1 for a, b, _, _ in legs if f"{a}|{b}" not in routes)}


@router.post("/api/chokepoints/exposure")
def exposure(req: RunRequest):
    """Passages the plan's legs cross, with the TEU per week the baseline re-evaluation carries through each."""
    with whatif._lock:
        key, out = whatif._run_output(req.run)
        prep = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
        base = whatif._evaluate(prep, 1.0, 1.0)
    res = _exposure(prep, base)
    return {"run": req.run, "dataset": prep["dataset"], **res,
            "method": "baseline flow-LP leg loads (1x demand, 1x fuel); passages from the searoute sea lane of each "
                      "leg, Suez / Panama from LINERLIB's canal flags; a TEU crossing on two legs counts twice"}


@router.post("/api/resilience")
def resilience(req: ResilienceRequest):
    """Rank single disruptions of the recorded plan by the weekly profit they cost (see module docstring)."""
    t0 = time.perf_counter()
    with whatif._lock:
        key, out = whatif._run_output(req.run)
        prep = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
        base = whatif._evaluate(prep, 1.0, 1.0)
        if req.target == "passages":
            cases = [{"id": p["id"], "label": p["name"], "teu_through": p["teu_per_week"]}
                     for p in _exposure(prep, base)["passages"]]
        else:
            calls: Dict[str, int] = defaultdict(int)
            for s in prep["services_rec"]:
                for p in dict.fromkeys(s["ports"]):
                    calls[p] += 1
            ranked = sorted(calls.items(), key=lambda kv: (-kv[1], kv[0]))[:req.limit]
            cases = [{"id": p, "label": p, "calls": n} for p, n in ranked]
        rows = []
        for c in cases:
            if req.target == "passages":
                preset = next((v for v in disruption.PRESETS.values() if v["closed"] == [c["id"]]), None)
                closed = (c["id"],)
                avoid = tuple(preset["detour_avoid"]) if preset else ()
                vprep, rep = whatif._variant(prep, closed, avoid, ())
            else:
                vprep, rep = whatif._variant(prep, (), (), (c["id"],))
            sc = whatif._evaluate(vprep, 1.0, 1.0)
            rows.append({**c, "profit": sc["profit"], "profit_change": sc["profit"] - base["profit"],
                         "served_teu": sc["served_teu"], "served_change": sc["served_teu"] - base["served_teu"],
                         "vessels_change": sc["vessels"] - base["vessels"], "valid": sc["valid"],
                         "rerouted_legs": len(rep.get("rerouted_legs") or []),
                         "suspended": [s["id"] for s in rep.get("suspended_services") or []],
                         "services_skipping": len(rep.get("services_skipping") or []),
                         "extra_nm_per_week": rep.get("extra_nm_per_week", 0.0)})
    rows.sort(key=lambda r: r["profit_change"])
    return {"run": req.run, "dataset": prep["dataset"], "target": req.target,
            "baseline": {"profit": base["profit"], "served_teu": base["served_teu"], "vessels": base["vessels"]},
            "rows": rows, "runtime_sec": round(time.perf_counter() - t0, 1),
            "method": "each row: the recorded plan with that one passage (with its preset's detour rule) or port "
                      "closed, re-routed by the flow LP and priced by the ledger; ranked by weekly profit lost"}


# ---- PortWatch -------------------------------------------------------------------------------------------
def _pw_cache() -> Path:
    env = os.environ.get("PORTWATCH_CACHE_DIR")
    if env:
        return Path(env) / "portwatch_chokepoints.json"
    if Path("D:/").exists():
        return Path("D:/liner_scratch_continuation/portwatch_cache/portwatch_chokepoints.json")
    return Path(__file__).resolve().parent.parent / "data" / "cache" / "portwatch_chokepoints.json"


def _pw_fetch(since: str) -> List[Dict]:
    ids = ",".join(f"'{c['portwatch']}'" for c in CHOKEPOINTS.values())
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": f"portid IN ({ids}) AND date >= DATE '{since}'",
            "outFields": "date,portid,n_total,n_container,capacity_container",
            "orderByFields": "date ASC", "returnGeometry": "false", "f": "json",
            "resultOffset": offset, "resultRecordCount": 2000,
        })
        with urllib.request.urlopen(f"{PORTWATCH_URL}?{q}", timeout=30) as r:
            body = json.loads(r.read().decode("utf-8"))
        if "error" in body:
            raise RuntimeError(body["error"].get("message", "PortWatch query error"))
        feats = body.get("features") or []
        rows += [f["attributes"] for f in feats]
        if not body.get("exceededTransferLimit") or not feats:
            return rows
        offset += len(feats)


def summarise_portwatch(rows: List[Dict], today: Optional[dt.date] = None) -> Dict[str, Dict]:
    """Per passage: mean daily transits over the last 30 days of data and the same 30 days a year earlier, plus
    weekly means (container ships) for a sparkline."""
    by_port: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for r in rows:
        d = str(r.get("date"))[:10]
        by_port[r["portid"]][d] = r
    out = {}
    for pid, info in CHOKEPOINTS.items():
        days = by_port.get(info["portwatch"], {})
        if not days:
            continue
        last = max(dt.date.fromisoformat(d) for d in days)
        def window(end: dt.date) -> List[Dict]:
            return [days[(end - dt.timedelta(days=i)).isoformat()] for i in range(30)
                    if (end - dt.timedelta(days=i)).isoformat() in days]
        now, year = window(last), window(last - dt.timedelta(days=365))
        mean = lambda xs, k: round(sum(float(x.get(k) or 0) for x in xs) / len(xs), 1) if xs else None
        weekly = []
        for w in range(52, 0, -1):
            end = last - dt.timedelta(days=7 * (w - 1))
            pts = [days[(end - dt.timedelta(days=i)).isoformat()] for i in range(7) if (end - dt.timedelta(days=i)).isoformat() in days]
            weekly.append(mean(pts, "n_container"))
        out[pid] = {
            "name": info["name"], "portwatch_id": info["portwatch"], "data_through": last.isoformat(),
            "last30": {"total": mean(now, "n_total"), "container": mean(now, "n_container"),
                       "container_capacity": mean(now, "capacity_container")},
            "year_before": {"total": mean(year, "n_total"), "container": mean(year, "n_container"),
                            "container_capacity": mean(year, "capacity_container")},
            "weekly_container": weekly,
        }
    return out


@router.get("/api/chokepoints/portwatch")
def portwatch(refresh: bool = False):
    """Daily transit calls through the chokepoints (IMF PortWatch), summarised; cached on disk for 12 h."""
    path = _pw_cache()
    cached = None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    fresh = cached and (time.time() - cached.get("fetched_at", 0) < PORTWATCH_TTL_SEC)
    if fresh and not refresh:
        return {**cached, "cache": "hit"}
    since = (dt.date.today() - dt.timedelta(days=PORTWATCH_DAYS)).isoformat()
    try:
        rows = _pw_fetch(since)
    except Exception as exc:
        if cached:                                  # serve the last good copy, labelled stale
            return {**cached, "cache": "stale", "error": f"PortWatch unreachable: {exc}"}
        raise HTTPException(status_code=503, detail=f"PortWatch unreachable and no cached copy: {exc}")
    body = {"source": "IMF PortWatch (portwatch.imf.org), Daily_Chokepoints_Data: AIS-observed transit calls",
            "fetched_at": time.time(), "fetched_on": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rows": len(rows), "chokepoints": summarise_portwatch(rows)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body), encoding="utf-8")
    except OSError:
        pass
    return {**body, "cache": "miss"}
