"""The plan's ports against IMF PortWatch, the NGA World Port Index and UNCTAD's port LSCI (backend/port_activity.py)."""

import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import port_activity as pa

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}


def test_match_by_locode_prefers_the_main_container_port_then_nearest():
    db = [
        {"portid": "a", "LOCODE": "SG SIN", "lat": 1.30, "lon": 103.90, "vessel_count_container": 5},
        {"portid": "b", "LOCODE": "SG SIN; SG XXX", "lat": 1.26, "lon": 103.84, "vessel_count_container": 900},
        {"portid": "c", "LOCODE": "", "lat": 51.95, "lon": 4.10, "vessel_count_container": 10},
    ]
    m = pa.match_ports([("SGSIN", 1.27, 103.85), ("NLRTM", 51.92, 4.20), ("ZZZZZ", 0.0, 0.0)], db, "portid", "lat", "lon", "LOCODE")
    assert m["SGSIN"]["row"]["portid"] == "b" and m["SGSIN"]["match"].startswith("UN/LOCODE (1 of 2)")
    assert m["NLRTM"]["row"]["portid"] == "c" and m["NLRTM"]["match"].startswith("nearest")
    assert "ZZZZZ" not in m                                    # nothing within 30 km


def test_summarise_daily_weekly_means_and_year_before():
    last = dt.date(2026, 10, 23)
    rows = []
    for i in range(30):
        rows.append({"portid": "p", "date": (last - dt.timedelta(days=i)).isoformat(), "portcalls_container": 2,
                     "portcalls": 5, "import": 10, "export": 20})
        rows.append({"portid": "p", "date": (last - dt.timedelta(days=365 + i)).isoformat(), "portcalls_container": 1,
                     "portcalls": 3, "import": 0, "export": 0})
    s = pa.summarise_daily(rows)["p"]
    assert s["data_through"] == "2026-10-23" and s["days"] == 30
    assert s["container_calls_per_week"] == 14.0 and s["container_calls_per_week_year_before"] == 7.0
    assert s["all_calls_per_week"] == 35.0 and s["export_t_per_week"] == 140.0


def test_lsci_snapshot_is_quarterly_by_locode():
    d = pa.lsci()
    assert len(d["quarters"]) == 8 and d["latest_quarter"] == d["quarters"][-1]
    assert d["ports"]["CNSHA"]["values"][-1] > 1000 and "Shanghai" in d["ports"]["CNSHA"]["label"]


@pytest.fixture(scope="module")
def client():
    from backend import run_catalog
    try:
        run_catalog._dataset_dir("worldsmall")
    except Exception:
        pytest.skip("no WorldSmall benchmark runs")
    app = FastAPI()
    app.include_router(pa.router)
    return TestClient(app)


def test_activity_endpoint_plan_side_and_sources(client):
    b = client.post("/api/ports/activity", json={"run": RUN}).json()
    ports = {p["code"]: p for p in b["ports"]}
    assert ports and all(p["plan"]["calls_per_week"] >= 1 for p in ports.values())
    # every TEU loaded is discharged somewhere
    assert sum(p["plan"]["teu_loaded"] for p in ports.values()) == pytest.approx(
        sum(p["plan"]["teu_discharged"] for p in ports.values()), rel=1e-6)
    assert b["sources"]["lsci"]["matched"] > 0
    for k in ("portwatch", "wpi"):
        assert b["sources"][k]["status"] in {"hit", "miss", "stale", "unavailable", "none"}
    for p in ports.values():
        w = p.get("wpi")
        if w and p["plan"]["deepest_class_draft_m"]:
            for name, depth in (("channel", w["channel_depth_m"]), ("cargo pier", w["cargo_pier_depth_m"])):
                assert (name in w["check"]) == (depth is not None and depth < p["plan"]["deepest_class_draft_m"])


def test_locate_returns_portwatch_point_or_none(monkeypatch):
    db = {"fetched_at": 1, "fetched_on": "2026-10-29 00:00 UTC", "data": [
        {"portid": "port1114", "portname": "Rotterdam", "country": "The Netherlands", "LOCODE": "NL RTM",
         "lat": 51.9223, "lon": 4.2151, "vessel_count_container": 7045}]}
    monkeypatch.setattr(pa, "_cached", lambda name, ttl, fetch: (db, "hit"))
    app = FastAPI()
    app.include_router(pa.router)
    c = TestClient(app)
    r = c.get("/api/ports/locate", params={"code": "nlrtm", "lat": 51.917, "lon": 4.5}).json()
    assert r["code"] == "NLRTM" and r["status"] == "hit"
    assert r["portwatch"]["portid"] == "port1114" and r["portwatch"]["match"] == "UN/LOCODE"
    assert r["portwatch"]["lon"] == pytest.approx(4.2151) and 18 < r["portwatch"]["km_from_dataset"] < 22
    far = c.get("/api/ports/locate", params={"code": "ZZZZZ", "lat": 0, "lon": 0}).json()
    assert far["portwatch"] is None and far["dataset"] == {"lat": 0, "lon": 0}
