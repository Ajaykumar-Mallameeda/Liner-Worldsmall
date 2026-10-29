"""Sentinel-1 radar ship counts (backend/sarships.py): detector on synthetic scenes, footprint and grid geometry,
endpoint shape with the network stubbed."""

import math

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import sarships as sa


def _scene(seed=0, h=300, w=300):
    """Speckled water on the left two thirds, bright land on the right, amplitude like GRD DN."""
    rng = np.random.default_rng(seed)
    water = np.zeros((h, w), bool)
    water[:, : 2 * w // 3] = True
    looks = 4.4                                   # IW GRDH equivalent number of looks
    inten = rng.gamma(looks, 1.0 / looks, (h, w))  # mean-1 multi-look speckle
    inten = np.where(water, 40.0 ** 2 * inten, 300.0 ** 2 * inten)
    return np.sqrt(inten), water


def _plant(amp, y, x, hh=3, ww=6, db=25.0):
    amp[y:y + hh, x:x + ww] = 40.0 * 10 ** (db / 20)


def test_detector_finds_planted_ships_and_nothing_else():
    amp, water = _scene()
    ships = [(40, 30), (100, 120), (160, 60), (220, 150), (270, 40)]
    for y, x in ships:
        _plant(amp, y, x)
    _plant(amp, 150, 260)                         # bright object on land: not a ship
    res = sa.detect(amp, np.ones_like(water), water, 144.0)
    got = sorted((round(t["y"]), round(t["x"])) for t in res["targets"])
    assert len(got) == len(ships)
    for (y, x), (gy, gx) in zip(sorted(ships), got):
        assert abs(gy - (y + 1)) <= 1 and abs(gx - (x + 2.5)) <= 1
    assert all(t["peak_db"] > sa.RATIO_DB for t in res["targets"])


def test_pure_speckle_gives_no_false_alarms():
    for seed in range(3):
        amp, water = _scene(seed)
        assert sa.detect(amp, np.ones_like(water), water, 144.0)["targets"] == []


def test_weak_tiny_and_land_targets_are_rejected():
    amp, water = _scene(1)
    _plant(amp, 50, 50, db=8.0)                   # below RATIO_DB
    _plant(amp, 120, 50, hh=1, ww=1, db=25.0)     # 144 m2 < MIN_M2
    _plant(amp, 200, 201, hh=3, ww=3, db=25.0)    # just past the waterline: land, not counted
    assert sa.detect(amp, np.ones_like(water), water, 144.0)["targets"] == []


def test_bright_ship_does_not_hide_its_neighbour():
    amp, water = _scene(2)
    _plant(amp, 100, 60, hh=6, ww=20, db=45.0)    # very bright hull
    _plant(amp, 100, 95, db=18.0)                 # weaker ship 15 px away (inside the first window)
    assert len(sa.detect(amp, np.ones_like(water), water, 144.0)["targets"]) == 2


def test_geometry_bbox_grid_footprint_and_mercator():
    b = sa.bbox_of(51.92, 4.2, 8.0)
    assert (b[3] - b[1]) * 110.574 == pytest.approx(16.0)
    assert (b[2] - b[0]) * 111.320 * math.cos(math.radians(51.92)) == pytest.approx(16.0)
    w, h, mx, my = sa.grid_size(b, 51.92)
    assert mx == pytest.approx(12.0, abs=0.05) and my == pytest.approx(12.0, abs=0.05)
    square = {"type": "Polygon", "coordinates": [[[3, 51], [6, 51], [6, 53], [3, 53], [3, 51]]]}
    assert sa.covers(square, b)
    half = {"type": "Polygon", "coordinates": [[[3, 51], [4.2, 51], [4.2, 53], [3, 53], [3, 51]]]}
    assert not sa.covers(half, b)
    multi = {"type": "MultiPolygon", "coordinates": [half["coordinates"], [[[4.1, 51], [6, 51], [6, 53], [4.1, 53], [4.1, 51]]]]}
    assert sa.covers(multi, b)
    # same convention as the Sentinel-2 tiles of the frontend (utils/s2tiles.js): Rotterdam z13 tile 4187 / 2707
    gx, gy = sa.merc_px(np.array([4.0]), np.array([51.95]), 13)
    assert int(gx[0] // 256) == 4187 and int(gy[0] // 256) == 2707


def test_endpoint_with_stubbed_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT_DATA_CACHE_DIR", str(tmp_path))
    scenes = [{"id": "S1A_X", "datetime": "2026-10-26T17:32:26Z", "platform": "sentinel-1a", "orbit": "ascending",
               "relative_orbit": 88},
              {"id": "S1A_Y", "datetime": "2026-10-20T17:32:26Z", "platform": "sentinel-1a", "orbit": "ascending",
               "relative_orbit": 88}]
    monkeypatch.setattr(sa, "search_scenes", lambda bbox, limit: scenes[:limit])

    def crop(item, bbox, w, h):
        amp, _ = _scene(0, h, w)
        if item == "S1A_X":
            for y, x in [(40, 30), (100, 120), (160, 60)]:
                _plant(amp, y, x)
        return amp, np.ones((h, w), bool)

    def mask(bbox, w, h):
        return {"water": _scene(0, h, w)[1], "items": ["ESA_WorldCover_10m_2021_v200_TEST"], "no_item_share": 0.0}

    monkeypatch.setattr(sa, "fetch_crop", crop)
    monkeypatch.setattr(sa, "water_mask", mask)
    monkeypatch.setattr(sa, "grid_size", lambda bbox, lat: (300, 300, 12.0, 12.0))
    app = FastAPI()
    app.include_router(sa.router)
    r = TestClient(app).get("/api/sar/ships", params={"code": "nlrtm", "lat": 51.92, "lon": 4.2, "scenes": 2})
    assert r.status_code == 200
    j = r.json()
    assert j["code"] == "NLRTM" and [s["ships"] for s in j["scenes"]] == [3, 0]
    assert j["summary"] == {"scenes_counted": 2, "latest": 3, "median": 1.5, "min": 0, "max": 3}
    assert j["scenes"][0]["image"].startswith("data:image/png;base64,")
    assert j["water_mask"]["items"] == ["ESA_WorldCover_10m_2021_v200_TEST"]
    t = j["scenes"][0]["targets"][0]
    assert j["bbox"][1] <= t["lat"] <= j["bbox"][3] and j["bbox"][0] <= t["lon"] <= j["bbox"][2]


def test_ship_in_a_narrow_basin_is_counted():
    """A 16-px (~190 m) basin cut into land: the window is mostly land, the moored hull still counts.
    (Below 0.35 x 41 px ~ 14 px, about 170 m after erosion, a basin is left out.)"""
    rng = np.random.default_rng(5)
    h = w = 200
    water = np.zeros((h, w), bool)
    water[:, 92:108] = True
    inten = rng.gamma(4.4, 1 / 4.4, (h, w))
    amp = np.sqrt(np.where(water, 40.0 ** 2 * inten, 300.0 ** 2 * inten))
    amp[80:100, 97:101] = 40.0 * 10 ** (25 / 20)
    res = sa.detect(amp, np.ones_like(water), water, 144.0)
    assert len(res["targets"]) == 1 and abs(res["targets"][0]["x"] - 98.5) < 1
