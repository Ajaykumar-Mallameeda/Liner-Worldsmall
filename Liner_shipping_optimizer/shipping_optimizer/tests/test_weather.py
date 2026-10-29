"""Sea state and currents along the plan's lanes (backend/weather.py, features #12 and #13)."""

import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import weather as w

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}


def test_bearing_and_along_track_conventions():
    assert w.bearing([0, 0], [0, 1]) == pytest.approx(0.0, abs=1e-9)          # north
    assert w.bearing([0, 0], [1, 0]) == pytest.approx(90.0, abs=1e-6)         # east
    assert w.bearing([0, 1], [0, 0]) == pytest.approx(180.0, abs=1e-9)
    # a 1 kn current flowing east (u=1): full help sailing east, full hindrance sailing west, none sailing north
    assert w.along_track(1.0, 0.0, 90.0) == pytest.approx(1.0)
    assert w.along_track(1.0, 0.0, 270.0) == pytest.approx(-1.0)
    assert w.along_track(1.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-12)


def test_summarise_reads_direction_as_flowing_to():
    h = {"time": ["t0", "t1", "t2"], "wave_height": [1.0, 4.5, None],
         "ocean_current_velocity": [2.0, 2.0, None], "ocean_current_direction": [90, 90, None]}
    s = w.summarise(h)
    assert s["hs_max"] == 4.5 and s["hs_max_at"] == "t1" and s["hrs_ge4"] == 1 and s["hrs_ge6"] == 0
    assert s["u"] == pytest.approx(2.0) and s["v"] == pytest.approx(0.0, abs=1e-12)   # flowing east
    empty = w.summarise({"time": ["t0"], "wave_height": [None], "ocean_current_velocity": [None], "ocean_current_direction": [None]})
    assert empty["hs_max"] is None and empty["u"] is None


def test_pieces_cover_the_lane():
    lane = [[0, 0], [10, 0], [10, 10]]
    ps = w.pieces(lane, 250)
    total = sum(p["nm"] for p in ps)
    assert total == pytest.approx(w._hav_nm(lane[0], lane[1]) + w._hav_nm(lane[1], lane[2]), rel=1e-9)
    assert all(p["nm"] <= 250 + 1e-9 for p in ps)
    assert ps[0]["course"] == pytest.approx(90, abs=0.5) and ps[-1]["course"] == pytest.approx(0, abs=0.5)


def test_sea_state_classes_follow_wmo_3700():
    assert w.sea_state(2.0)["code"] == 4 and w.sea_state(2.0)["risk"] == "low"
    assert w.sea_state(2.5)["code"] == 4                                  # upper bounds inclusive
    assert w.sea_state(3.0) == {"code": 5, "name": "very rough", "risk": "moderate"}
    assert w.sea_state(5.0)["risk"] == "high" and w.sea_state(7.0)["risk"] == "severe"
    assert w.sea_state(16.0)["code"] == 9 and w.sea_state(None)["code"] is None


def test_time_ratio_with_and_against_the_current():
    ps = [{"nm": 100.0, "mid": [0, 0], "course": 90.0}, {"nm": 100.0, "mid": [1, 0], "course": 90.0}]
    assert w.time_ratio(ps, 10.0, lambda p: 0.0) == pytest.approx(1.0)
    assert w.time_ratio(ps, 10.0, lambda p: 1.0) == pytest.approx(10 / 11)
    assert w.time_ratio(ps, 10.0, lambda p: -1.0) == pytest.approx(10 / 9)
    assert w.time_ratio(ps, 10.0, lambda p: None) == pytest.approx(1.0)     # land / no data = still water
    assert w.time_ratio(ps, 10.0, lambda p: -20.0) == pytest.approx(2.0)    # never below half speed


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("searoute")
    from backend import run_catalog
    try:
        run_catalog._dataset_dir("worldsmall")
    except Exception:
        pytest.skip("no WorldSmall benchmark runs")
    app = FastAPI()
    app.include_router(w.router)
    return TestClient(app)


def test_endpoint_is_consistent(client):
    b = client.post("/api/weather/legs", json={"run": RUN, "forecast_days": 7}).json()
    if b.get("status") == "unavailable":
        pytest.skip(f"Open-Meteo unreachable: {b.get('error')}")
    assert b["legs"] and b["services"] and b["points"]
    assert sum(b["risk_counts"].values()) == sum(1 for l in b["legs"] if l["risk"])
    hs = [l["hs_max_m"] for l in b["legs"] if l["hs_max_m"] is not None]
    assert hs == sorted(hs, reverse=True)
    for s in b["services"]:
        assert s["sea_days_current"] == pytest.approx(sum(l["current_days"] for l in s["legs"]), abs=0.01)
        assert s["vessels_current"] == math.ceil(s["cycle_days_current"] * s["departures_per_week"] / 7.0)
        assert s["vessels_plan"] == math.ceil(s["cycle_days_plan"] * s["departures_per_week"] / 7.0)
    assert b["totals"]["vessels_plan"] == sum(s["vessels_plan"] for s in b["services"])
    assert client.post("/api/weather/legs", json={"run": RUN, "forecast_days": 9}).status_code == 422
