"""
Sentinel-1 radar ship counts at a port (2026-10-29, feature #10).

GET /api/sar/ships?code=&lat=&lon=&half_km=8&scenes=4
  The latest Sentinel-1 IW GRD acquisitions over a square of 2 x half_km around the point (Microsoft Planetary
  Computer STAC, collection sentinel-1-grd, keyless). For each scene the Planetary Computer data API returns the VV
  amplitude resampled onto a lon/lat grid of about 12 m (the GRD's GCPs are applied server-side), and ships are
  counted on it:

  1. Water mask: ESA WorldCover 2021 (10 m, class 80 "permanent water bodies", which includes the sea inside its
     tiles), read as z13 tiles from the same data API and resampled onto the radar grid, then eroded by
     ERODE_PX so quay edges and the radar's geolocation error stay outside; where WorldCover has no tile (open
     ocean) the pixel counts as water. A mask from the scene itself (Otsu on the amplitude) was tried first and
     failed on land-heavy squares: dark farmland became "water" and field edges "ships".
  2. Ratio CFAR: a water pixel is a target when its intensity is RATIO_DB above the mean water intensity in a
     WINDOW_PX x WINDOW_PX window that is at least WATER_SHARE water (basins down to about 170 m wide pass).
     The background leaves out pixels already RATIO_DB above the crop's median water level, and a second pass
     recomputes it without the first pass's targets, so a very bright ship does not raise its own threshold.
  3. Targets: pixels merged within 2 px (sidelobes of one hull), kept when MIN_M2 <= target area <= MAX_M2.

  It counts bright objects on water: ships moored, at anchor and under way, but also buoys, platforms, wind
  turbines and bright quay structures or crane layover reaching over the water; hulls moored side by side can
  merge into one target (an undercount). No AIS
  ground truth is used (the Planetary Computer copy runs about 2-3 days behind, live AIS is "now"), so the count
  is an estimate to compare scene against scene at one port, not a census.

  Per scene: datetime, platform, orbit direction, targets (lat, lon, area m2, peak dB above background), water km2,
  valid share, and a small PNG of the radar crop (water tinted, targets boxed). Results per scene and square are
  cached on disk (a scene never changes), the water mask per square for a year, the scene list for 6 h.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import io
import json
import math
import struct
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from scipy import ndimage as ndi

from backend import port_activity

router = APIRouter()

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
DATA = "https://planetarycomputer.microsoft.com/api/data/v1/item/bbox"
TILES = "https://planetarycomputer.microsoft.com/api/data/v1/item/tiles/WebMercatorQuad"
COLLECTION = "sentinel-1-grd"
PIXEL_M = 12.0              # requested grid spacing
MAX_PX = 1600               # per side
LOOKBACK_DAYS = 45
WC_COLLECTION = "esa-worldcover"
WC_ZOOM = 13
WC_WATER = 80
ERODE_PX = 2
WINDOW_PX = 41
RATIO_DB = 13.0
WATER_SHARE = 0.35          # 0.7 left out every ship in Hamburg's 100-300 m basins (2 targets vs ~100 hulls seen)
MIN_M2 = 500.0
MAX_M2 = 60000.0
MIN_VALID = 0.9             # a scene covering less of the square is skipped
PNG_PX = 420
TTL_SCENES = 6 * 3600
TTL_RESULT = 365 * 86400


# ── geometry ──

def bbox_of(lat: float, lon: float, half_km: float) -> Tuple[float, float, float, float]:
    dlat = half_km / 110.574
    dlon = half_km / (111.320 * max(0.05, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def grid_size(bbox, lat: float) -> Tuple[int, int, float, float]:
    """(width px, height px, metres per px east, metres per px north) for the bbox at about PIXEL_M."""
    w_m = (bbox[2] - bbox[0]) * 111320.0 * math.cos(math.radians(lat))
    h_m = (bbox[3] - bbox[1]) * 110574.0
    w = min(MAX_PX, max(64, round(w_m / PIXEL_M)))
    h = min(MAX_PX, max(64, round(h_m / PIXEL_M)))
    return w, h, w_m / w, h_m / h


def _in_ring(x: float, y: float, ring) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def covers(geometry: Dict, bbox) -> bool:
    """True when every corner of the bbox lies inside the (multi)polygon footprint."""
    polys = geometry["coordinates"] if geometry.get("type") == "MultiPolygon" else [geometry.get("coordinates") or []]
    corners = [(bbox[0], bbox[1]), (bbox[0], bbox[3]), (bbox[2], bbox[1]), (bbox[2], bbox[3])]
    return all(any(poly and _in_ring(x, y, [tuple(p[:2]) for p in poly[0]]) for poly in polys) for x, y in corners)


# ── detection ──

def detect(amp: np.ndarray, valid: np.ndarray, water: np.ndarray, px_m2: float) -> Dict:
    """Ship targets on one amplitude crop over a given water mask. Returns labelled targets (pixel space)."""
    a = amp.astype(np.float64)
    I = a * a
    water = water & valid
    if water.sum() < WINDOW_PX * WINDOW_PX:
        return {"targets": []}
    share = ndi.uniform_filter(water.astype(float), WINDOW_PX)
    # the background never includes pixels already RATIO_DB above the crop's median water level: a large bright hull
    # would otherwise lift the mean of its own window and hide itself (CFAR self-masking)
    bright = I > np.median(I[water]) * 10 ** (RATIO_DB / 10)
    bg = water & ~ndi.binary_dilation(bright & water, iterations=6)
    for _ in range(2):  # pass 2: background without pass-1 targets and their sidelobes
        cnt = ndi.uniform_filter(bg.astype(float), WINDOW_PX)
        mean = ndi.uniform_filter(np.where(bg, I, 0.0), WINDOW_PX) / np.maximum(cnt, 1e-6)
        ratio = 10 * np.log10(np.maximum(I, 1.0) / np.maximum(mean, 1.0))
        det = (ratio > RATIO_DB) & water & (share > WATER_SHARE) & (cnt > 0.05)
        bg = water & ~ndi.binary_dilation(det, iterations=6)
    lab, n = ndi.label(ndi.binary_dilation(det, iterations=2))
    targets = []
    if n:
        idx = np.arange(1, n + 1)
        area = ndi.sum(det, lab, idx) * px_m2
        peak = ndi.maximum(np.where(det, ratio, -99.0), lab, idx)
        cy_cx = ndi.center_of_mass(det, lab, idx)
        objs = ndi.find_objects(lab)
        for i in range(n):
            if MIN_M2 <= area[i] <= MAX_M2:
                targets.append({"y": float(cy_cx[i][0]), "x": float(cy_cx[i][1]), "area_m2": float(area[i]),
                                "peak_db": float(peak[i]), "box": [objs[i][0].start, objs[i][1].start,
                                                                   objs[i][0].stop, objs[i][1].stop]})
    return {"targets": targets}


def _png(rgb: np.ndarray) -> bytes:
    h, w = rgb.shape[:2]
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def quicklook(amp: np.ndarray, valid: np.ndarray, water: np.ndarray, targets: List[Dict]) -> str:
    """Small PNG (data URL): radar amplitude in grey, water tinted blue, targets boxed in yellow."""
    f = max(1, math.ceil(max(amp.shape) / PNG_PX))
    h, w = amp.shape[0] // f, amp.shape[1] // f
    log_a = np.log10(np.maximum(amp[: h * f, : w * f].astype(float), 1.0)).reshape(h, f, w, f).mean(axis=(1, 3))
    wat = water[: h * f, : w * f].reshape(h, f, w, f).mean(axis=(1, 3)) > 0.5
    ok = valid[: h * f, : w * f].reshape(h, f, w, f).mean(axis=(1, 3)) > 0.5
    lo, hi = np.percentile(log_a[ok], [2, 99.5]) if ok.any() else (0, 1)
    g = np.clip((log_a - lo) / max(hi - lo, 1e-6), 0, 1)
    rgb = np.stack([g, g, g], -1)
    rgb[wat] = rgb[wat] * 0.7 + np.array([0.0, 0.08, 0.28])
    rgb[~ok] = 0.05
    for t in targets:
        y0, x0, y1, x1 = (int(v / f) for v in t["box"])
        y0, x0 = max(y0 - 2, 0), max(x0 - 2, 0)
        y1, x1 = min(y1 + 2, h - 1), min(x1 + 2, w - 1)
        rgb[y0, x0:x1 + 1] = rgb[y1, x0:x1 + 1] = (0.99, 0.88, 0.28)
        rgb[y0:y1 + 1, x0] = rgb[y0:y1 + 1, x1] = (0.99, 0.88, 0.28)
    img = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    return "data:image/png;base64," + base64.b64encode(_png(img)).decode("ascii")


# ── sources ──

def _get(url: str, data: Optional[bytes] = None, timeout: float = 60) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "liner-shipping-optimizer/1.0",
                                                          **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search_scenes(bbox, limit: int) -> List[Dict]:
    end = dt.datetime.utcnow()
    body = {"collections": [COLLECTION], "bbox": list(bbox), "limit": 50,
            "datetime": f"{(end - dt.timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "sortby": [{"field": "datetime", "direction": "desc"}],
            "query": {"sar:instrument_mode": {"eq": "IW"}}}
    feats = json.loads(_get(STAC, json.dumps(body).encode()))["features"]
    out, seen = [], set()
    for f in feats:
        p = f["properties"]
        if "VV" not in (p.get("sar:polarizations") or []) or not covers(f["geometry"], bbox):
            continue
        slot = (p["datetime"][:13], p.get("platform"))  # one acquisition per platform pass
        if slot in seen:
            continue
        seen.add(slot)
        out.append({"id": f["id"], "datetime": p["datetime"], "platform": p.get("platform"),
                    "orbit": p.get("sat:orbit_state"), "relative_orbit": p.get("sat:relative_orbit")})
        if len(out) >= limit:
            break
    return out


def fetch_crop(item: str, bbox, w: int, h: int) -> Tuple[np.ndarray, np.ndarray]:
    path = f"{DATA}/{bbox[0]:.5f},{bbox[1]:.5f},{bbox[2]:.5f},{bbox[3]:.5f}/{w}x{h}.npy"
    q = urllib.parse.urlencode({"collection": COLLECTION, "item": item, "assets": "vv"})
    arr = np.load(io.BytesIO(_get(f"{path}?{q}", timeout=120)), allow_pickle=False)
    return arr[0], arr[-1] > 0


def merc_px(lon: np.ndarray, lat: np.ndarray, z: int) -> Tuple[np.ndarray, np.ndarray]:
    """Web-Mercator global pixel coordinates (256-px tiles) at zoom z."""
    n = 256 * 2 ** z
    rad = np.radians(np.clip(lat, -85.0511, 85.0511))
    return (lon + 180.0) / 360.0 * n, (1 - np.arcsinh(np.tan(rad)) / np.pi) / 2 * n


def water_mask(bbox, w: int, h: int) -> Dict:
    """WorldCover water (class 80) on the w x h lon/lat grid of the bbox, before erosion. Pixels no WorldCover item
    covers are open ocean and count as water."""
    body = {"collections": [WC_COLLECTION], "bbox": list(bbox), "limit": 20}
    items = [f for f in json.loads(_get(STAC, json.dumps(body).encode()))["features"]]
    # the newest version per tile (v200 = 2021 over v100 = 2020)
    by_tile = {}
    for f in sorted(items, key=lambda f: f["id"]):
        by_tile[f["id"].split("_")[-1]] = f["id"]
    lon = bbox[0] + (np.arange(w) + 0.5) * (bbox[2] - bbox[0]) / w
    lat = bbox[3] - (np.arange(h) + 0.5) * (bbox[3] - bbox[1]) / h
    gx, _ = merc_px(lon, np.zeros_like(lon), WC_ZOOM)
    _, gy = merc_px(np.zeros_like(lat), lat, WC_ZOOM)
    ix, iy = np.floor(gx).astype(int), np.floor(gy).astype(int)
    tx0, tx1, ty0, ty1 = ix.min() // 256, ix.max() // 256, iy.min() // 256, iy.max() // 256
    cls = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.uint8)  # 0 = no item
    jobs = [(item, tx, ty) for item in by_tile.values() for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]

    def tile(job):
        item, tx, ty = job
        q = urllib.parse.urlencode({"collection": WC_COLLECTION, "item": item, "assets": "map"})
        try:
            arr = np.load(io.BytesIO(_get(f"{TILES}/{WC_ZOOM}/{tx}/{ty}@1x.npy?{q}")), allow_pickle=False)
        except urllib.error.HTTPError as exc:   # tile outside this item
            if exc.code in (204, 404):
                return job, None
            raise
        return job, np.where(arr[-1] > 0, arr[0], 0).astype(np.uint8)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for (item, tx, ty), arr in ex.map(tile, jobs):
            if arr is not None:
                block = cls[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256]
                np.copyto(block, arr, where=arr > 0)
    grid = cls[(iy - ty0 * 256)[:, None], (ix - tx0 * 256)[None, :]]
    water = (grid == WC_WATER) | (grid == 0)
    return {"water": water, "items": sorted(by_tile.values()), "no_item_share": float((grid == 0).mean())}


def _water_cached(bbox, w: int, h: int) -> Tuple[np.ndarray, Dict]:
    key = hashlib.sha1(f"wc|{bbox[0]:.5f},{bbox[1]:.5f},{bbox[2]:.5f},{bbox[3]:.5f}|{w}x{h}".encode()).hexdigest()[:16]

    def fetch():
        m = water_mask(bbox, w, h)
        return {"bits": base64.b64encode(np.packbits(m["water"]).tobytes()).decode("ascii"), "items": m["items"],
                "no_item_share": m["no_item_share"]}

    val, status = port_activity._cached(f"sar_water_{key}.json", TTL_RESULT, fetch)
    if val.get("data") is None:
        raise RuntimeError(f"WorldCover water mask unavailable: {val.get('error')}")
    d = val["data"]
    bits = np.unpackbits(np.frombuffer(base64.b64decode(d["bits"]), np.uint8))[: w * h].reshape(h, w).astype(bool)
    return bits, {"items": d["items"], "no_item_share": round(d["no_item_share"], 3), "status": status}


def analyse_scene(scene: Dict, bbox, lat: float) -> Dict:
    w, h, mx, my = grid_size(bbox, lat)
    px_m2 = mx * my
    water_full, _ = _water_cached(bbox, w, h)
    water = ndi.binary_erosion(water_full, iterations=ERODE_PX, border_value=1)
    amp, valid = fetch_crop(scene["id"], bbox, w, h)
    valid = valid & (amp > 0)
    vshare = float(valid.mean())
    res = detect(amp, valid, water, px_m2) if vshare >= MIN_VALID else {"targets": []}
    res["water"] = water & valid
    lon0, lat1 = bbox[0], bbox[3]
    dlon, dlat = (bbox[2] - bbox[0]) / w, (bbox[3] - bbox[1]) / h
    targets = [{"lat": round(lat1 - (t["y"] + 0.5) * dlat, 5), "lon": round(lon0 + (t["x"] + 0.5) * dlon, 5),
                "area_m2": round(t["area_m2"]), "peak_db": round(t["peak_db"], 1)} for t in res["targets"]]
    return {**scene, "valid_share": round(vshare, 3), "skipped": vshare < MIN_VALID,
            "ships": len(targets) if vshare >= MIN_VALID else None, "targets": targets,
            "water_km2": round(float(res["water"].sum()) * px_m2 / 1e6, 1),
            "pixel_m": [round(mx, 1), round(my, 1)],
            "image": quicklook(amp, valid, res["water"], res["targets"])}


def _result_cached(scene: Dict, bbox, lat: float) -> Tuple[Dict, str]:
    key = hashlib.sha1(f"{scene['id']}|{bbox[0]:.5f},{bbox[1]:.5f},{bbox[2]:.5f},{bbox[3]:.5f}|{RATIO_DB}|{WINDOW_PX}|wc{ERODE_PX}|g1|s{WATER_SHARE}".encode()).hexdigest()[:16]
    val, status = port_activity._cached(f"sar_{key}.json", TTL_RESULT, lambda: analyse_scene(scene, bbox, lat))
    if val.get("data") is None:
        return {**scene, "error": val.get("error") or "unavailable", "ships": None, "targets": []}, status
    return val["data"], status


@router.get("/api/sar/ships")
def sar_ships(code: str, lat: float = Query(..., ge=-80, le=80), lon: float = Query(..., ge=-180, le=180),
              half_km: float = Query(8.0, ge=2.0, le=12.0), scenes: int = Query(4, ge=1, le=8)):
    bbox = bbox_of(lat, lon, half_km)
    skey = hashlib.sha1(f"{bbox}|{scenes}".encode()).hexdigest()[:16]
    listing, list_status = port_activity._cached(f"sar_scenes_{skey}.json", TTL_SCENES, lambda: search_scenes(bbox, scenes))
    if listing.get("data") is None:
        raise HTTPException(502, f"Planetary Computer STAC unreachable: {listing.get('error')}")
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda s: _result_cached(s, bbox, lat), listing["data"]))
    out = [r for r, _ in results]
    try:
        w, h, _, _ = grid_size(bbox, lat)
        water_meta = _water_cached(bbox, w, h)[1]
    except RuntimeError as exc:
        water_meta = {"error": str(exc)}
    counts = [s["ships"] for s in out if s.get("ships") is not None]
    return {
        "code": code.strip().upper(), "centre": {"lat": lat, "lon": lon}, "half_km": half_km,
        "bbox": [round(v, 5) for v in bbox], "scenes": out,
        "summary": {"scenes_counted": len(counts), "latest": counts[0] if counts else None,
                    "median": float(np.median(counts)) if counts else None,
                    "min": min(counts) if counts else None, "max": max(counts) if counts else None},
        "method": {"ratio_db": RATIO_DB, "window_px": WINDOW_PX, "water_share": WATER_SHARE, "min_m2": MIN_M2,
                   "max_m2": MAX_M2, "pixel_m": PIXEL_M, "lookback_days": LOOKBACK_DAYS},
        "status": {"scenes": list_status, "results": [st for _, st in results], "listed_on": listing.get("fetched_on")},
        "water_mask": {"source": "ESA WorldCover 10 m 2021 v200 (class 80), CC BY 4.0", **water_meta},
        "source": "Copernicus Sentinel-1 IW GRD (ESA), via Microsoft Planetary Computer STAC + data API",
    }
