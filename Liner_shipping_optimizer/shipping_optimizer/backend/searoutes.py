"""
Sea-lane geometry for the map (read-only).

Every leg of a plan is drawn along a real maritime route instead of a curved arc. Routes come from the
`searoute` package (Eurostat's maritime network + Dijkstra): suitable for visualisation and distance
checks, NOT for navigation. For each port pair the response carries

    coords        [[lon, lat], ...] with longitudes unwrapped (no ±180 jump), simplified
    nm            length of that sea route in nautical miles
    model_nm      the distance the optimizer uses (the dataset's LINERLIB distance matrix)
    passages      straits / canals the route passes (searoute names: suez, panama, malacca, ...)
    model_canal   LINERLIB's own flags for the selected distance record: {"suez": 0/1, "panama": 0/1}

`avoid` re-routes around passages (e.g. avoid=suez,babalmandab sends Asia-Europe legs round the Cape);
the Northwest Passage and the Bering Strait are always avoided (not liner routes). Results are cached in
memory and on disk (SEAROUTE_CACHE_DIR, default D:/liner_scratch_continuation/searoute_cache when D: exists).
"""

from __future__ import annotations

import json
import os
import threading
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

ALWAYS_AVOID = ("northwest", "bering")
VALID_PASSAGES = {"babalmandab", "bosporus", "gibraltar", "suez", "panama", "ormuz", "malacca", "sunda",
                  "chili", "south_africa"}
MAX_PAIRS = 4000
SIMPLIFY_DEG = 0.05          # drop vertices closer than this to the previous kept one (display only)

_lock = threading.Lock()
_mem: Dict[str, Dict] = {}   # cache key -> route record


def _cache_dir() -> Path:
    env = os.environ.get("SEAROUTE_CACHE_DIR")
    if env:
        return Path(env)
    if Path("D:/").exists():
        return Path("D:/liner_scratch_continuation/searoute_cache")
    return Path(__file__).resolve().parent.parent / "data" / "cache" / "searoute"


@lru_cache(maxsize=8)
def _dataset(dataset: str) -> Dict:
    from src.data.dataset_registry import resolve_dataset
    try:
        info = resolve_dataset(dataset)
    except Exception as exc:  # unknown dataset key
        raise HTTPException(status_code=404, detail=f"unknown dataset {dataset!r}: {exc}")
    raw = json.loads(Path(info.json_path).read_text(encoding="utf-8"))
    ports = {p["id"]: (float(p["longitude"]), float(p["latitude"])) for p in raw.get("ports", [])}
    canal, alternatives = {}, {}
    for rec in raw.get("distance_alternatives", []) or []:
        alternatives[(rec["from"], rec["to"])] = list(rec.get("records", []))
        sel = next((r for r in rec.get("records", []) if r.get("selected")), None)
        if sel:
            canal[(rec["from"], rec["to"])] = {"suez": int(sel.get("is_suez") or 0), "panama": int(sel.get("is_panama") or 0)}
    for a, b, pan, sue in raw.get("canal_flags", []) or []:      # rows are [origin, destination, is_panama, is_suez]
        canal.setdefault((a, b), {"suez": int(sue or 0), "panama": int(pan or 0)})
    return {"key": raw.get("dataset", {}).get("key", dataset), "ports": ports,
            "dm": raw.get("distance_matrix", {}), "canal": canal, "alternatives": alternatives}


def _unwrap(coords: List[List[float]]) -> List[List[float]]:
    out: List[List[float]] = []
    shift = 0.0
    for i, (lon, lat) in enumerate(coords):
        if i:
            prev = coords[i - 1][0]
            d = lon - prev
            if d > 180:
                shift -= 360
            elif d < -180:
                shift += 360
        out.append([round(lon + shift, 3), round(lat, 3)])
    return out


def _simplify(coords: List[List[float]]) -> List[List[float]]:
    if len(coords) <= 2:
        return coords
    kept = [coords[0]]
    for c in coords[1:-1]:
        if abs(c[0] - kept[-1][0]) + abs(c[1] - kept[-1][1]) >= SIMPLIFY_DEG:
            kept.append(c)
    kept.append(coords[-1])
    return kept


def _disk_path(ds_key: str, avoid_key: str) -> Path:
    # .v2: from 2026-10-28 failed routes (two-point lines) are no longer cached; older files are ignored
    return _cache_dir() / f"{ds_key.lower()}__{avoid_key or 'none'}.v2.json"


def _load_disk(ds_key: str, avoid_key: str) -> Dict:
    p = _disk_path(ds_key, avoid_key)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_disk(ds_key: str, avoid_key: str, data: Dict) -> None:
    p = _disk_path(ds_key, avoid_key)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass  # cache is optional


def route_pair(ds: Dict, a: str, b: str, avoid: Tuple[str, ...]) -> Optional[Dict]:
    import searoute as sr
    pa, pb = ds["ports"].get(a), ds["ports"].get(b)
    if pa is None or pb is None or a == b:
        return None
    restrictions = list(ALWAYS_AVOID) + [x for x in avoid if x not in ALWAYS_AVOID]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            f = sr.searoute(list(pa), list(pb), units="naut", append_orig_dest=True, return_passages=True,
                            restrictions=restrictions)
    except Exception:
        return None
    # searoute returns an empty, zero-length route (with a warning) when restrictions leave no path
    # and a bare origin-destination line (two points, no network) when it could not route at all
    raw_coords = f.geometry.get("coordinates") or []
    if len(raw_coords) <= 2 or float(f.properties.get("length") or 0.0) <= 0.0:
        return None
    coords = _simplify(_unwrap([list(map(float, c)) for c in f.geometry["coordinates"]]))
    props = f.properties
    model = ds["dm"].get(a, {}).get(b)
    return {"coords": coords, "nm": round(float(props.get("length", 0.0)), 1),
            "model_nm": float(model) if model is not None else None,
            "passages": sorted(set(props.get("traversed_passages") or [])),
            # LINERLIB's flags of the selected record; the dataset lists canal pairs only, so absent = no canal
            "model_canal": ds["canal"].get((a, b), {"suez": 0, "panama": 0}) if model is not None else None}


def routes_for(dataset: str, pairs: List[Tuple[str, str]], avoid: Tuple[str, ...] = ()) -> Dict[str, Dict]:
    ds = _dataset(dataset)
    avoid = tuple(sorted(set(avoid)))
    avoid_key = "+".join(avoid)
    out: Dict[str, Dict] = {}
    with _lock:
        mem_key = f"{ds['key']}|{avoid_key}"
        cache = _mem.get(mem_key)
        if cache is None:
            cache = _load_disk(ds["key"], avoid_key)
            _mem[mem_key] = cache
        dirty = False
        for a, b in pairs:
            k = f"{a}|{b}"
            if k not in cache:
                rec = route_pair(ds, a, b, avoid)
                if rec is None:
                    continue
                cache[k] = rec
                dirty = True
            out[k] = cache[k]
        if dirty:
            _save_disk(ds["key"], avoid_key, cache)
    return out


def _parse_pairs(pairs: str) -> List[Tuple[str, str]]:
    out = []
    for tok in (pairs or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        a, _, b = tok.partition("-")
        if a and b:
            out.append((a.strip().upper(), b.strip().upper()))
    if len(out) > MAX_PAIRS:
        raise HTTPException(status_code=413, detail=f"at most {MAX_PAIRS} pairs per request")
    return out


def _parse_avoid(avoid: Optional[str]) -> Tuple[str, ...]:
    vals = tuple(v.strip().lower() for v in (avoid or "").split(",") if v.strip())
    bad = [v for v in vals if v not in VALID_PASSAGES]
    if bad:
        raise HTTPException(status_code=422, detail=f"unknown passage(s) {bad}; valid: {sorted(VALID_PASSAGES)}")
    return vals


@router.get("/api/searoutes/{dataset}")
def searoutes(dataset: str, pairs: str = Query(..., description="comma list of FROM-TO port ids"),
              avoid: Optional[str] = Query(None, description="comma list of passages to avoid")):
    """Sea-lane geometry, length and passages for each requested port pair (see module docstring)."""
    pp = _parse_pairs(pairs)
    av = _parse_avoid(avoid)
    routes = routes_for(dataset, pp, av)
    return {"dataset": _dataset(dataset)["key"], "avoid": list(av), "always_avoided": list(ALWAYS_AVOID),
            "source": "searoute (Eurostat maritime network) — visualisation, not navigation",
            "routes": routes, "missing": [f"{a}|{b}" for a, b in pp if f"{a}|{b}" not in routes]}
