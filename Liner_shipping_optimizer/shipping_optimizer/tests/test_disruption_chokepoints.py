"""Closure scenarios and chokepoint exposure (backend/disruption.py, backend/chokepoints.py, /api/whatif closures)."""

import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import chokepoints, disruption

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}


# ── pure helpers ──

def test_resolve_merges_preset_and_rejects_unknown_names():
    closed, avoid, p = disruption.resolve("red_sea", ["ormuz"], [])
    assert closed == ("babalmandab", "ormuz") and avoid == ("panama",) and p["label"]
    # a passage both closed and avoided is reported once, as closed
    assert disruption.resolve(None, ["suez"], ["suez", "panama"])[:2] == (("suez",), ("panama",))
    with pytest.raises(ValueError):
        disruption.resolve("atlantis", [], [])
    with pytest.raises(ValueError):
        disruption.resolve(None, ["atlantis"], [])


def test_rotation_legs_include_the_return_leg():
    assert disruption.rotation_legs(["A", "B", "C"]) == [("A", "B"), ("B", "C"), ("C", "A")]
    assert disruption.rotation_legs(["A", "B", "A"]) == [("A", "B"), ("B", "A")]
    assert disruption.rotation_legs(["A"]) == []


def test_crossed_uses_linerlib_canal_flags_and_sea_lane_straits():
    route = {"passages": ["panama", "gibraltar"], "model_canal": {"suez": 0, "panama": 0}}
    # the lanes snapped a port across Panama, but LINERLIB's distance does not use the canal
    assert disruption.crossed(route, ["panama", "gibraltar"]) == ["gibraltar"]
    assert disruption.crossed({"passages": [], "model_canal": {"suez": 1, "panama": 0}}, ["suez"]) == ["suez"]
    # no LINERLIB record: fall back to the sea lane
    assert disruption.crossed({"passages": ["suez"]}, ["suez"]) == ["suez"]


def test_close_ports_skips_or_suspends():
    services = [{"id": "a", "ports": ["X", "Y", "Z"]}, {"id": "b", "ports": ["X", "Y"]}, {"id": "c", "ports": ["P", "Q"]}]
    sailing, rep = disruption.close_ports(services, ["y"])
    assert [s["id"] for s in sailing] == ["a", "c"] and sailing[0]["ports"] == ["X", "Z"]
    assert rep["services_skipping"] == [{"id": "a", "skips": ["Y"]}]
    assert [s["id"] for s in rep["suspended_services"]] == ["b"]
    assert rep["closed_ports"] == ["Y"]


def test_summarise_portwatch_windows_and_yoy():
    last = dt.date(2026, 10, 25)
    rows = []
    for i in range(400):
        d = last - dt.timedelta(days=i)
        rows.append({"portid": "chokepoint6", "date": d.isoformat(), "n_total": 10 if i < 30 else 100,
                     "n_container": 2 if i < 30 else 20, "capacity_container": 0})
    s = chokepoints.summarise_portwatch(rows)["ormuz"]
    assert s["data_through"] == "2026-10-25"
    assert s["last30"]["container"] == 2.0 and s["year_before"]["container"] == 20.0
    assert len(s["weekly_container"]) == 52 and s["weekly_container"][-1] == 2.0


# ── endpoints on a recorded WorldSmall run ──

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("searoute")
    from backend import run_catalog, whatif
    try:
        run_catalog._dataset_dir("worldsmall")
    except Exception:
        pytest.skip("no WorldSmall benchmark runs")
    app = FastAPI()
    app.include_router(whatif.router)
    app.include_router(chokepoints.router)
    return TestClient(app)


def test_whatif_red_sea_sends_legs_round_the_cape(client):
    base = client.post("/api/whatif", json={"run": RUN}).json()
    r = client.post("/api/whatif", json={"run": RUN, "preset": "red_sea"})
    assert r.status_code == 200
    body = r.json()
    rep = body["disruption"]
    assert rep["closed_passages"] == ["babalmandab"] and rep["detour_avoid"] == ["panama"]
    assert rep["rerouted_legs"], "an Asia-Europe plan must have legs through Bab-el-Mandeb"
    for leg in rep["rerouted_legs"]:
        assert leg["nm_after"] >= leg["nm_before"]
        assert "babalmandab" not in leg["via_after"] and "panama" not in leg["via_after"]
    assert rep["extra_nm_per_week"] > 0
    assert rep["vessels_after"] >= rep["vessels_before"]
    assert body["scenario"]["profit"] < body["baseline"]["profit"] == pytest.approx(base["baseline"]["profit"])
    assert "red_sea" in body["presets"]


def test_whatif_closure_errors(client):
    assert client.post("/api/whatif", json={"run": RUN, "preset": "atlantis"}).status_code == 422
    assert client.post("/api/whatif", json={"run": RUN, "closed_ports": ["XXXXX"]}).status_code == 422


def test_whatif_closed_port_is_skipped(client):
    exp = client.post("/api/chokepoints/exposure", json={"run": RUN}).json()
    assert exp["passages"]
    res = client.post("/api/resilience", json={"run": RUN, "target": "ports", "limit": 2}).json()
    port = res["rows"][0]["id"]
    body = client.post("/api/whatif", json={"run": RUN, "closed_ports": [port]}).json()
    rep = body["disruption"]
    assert rep["closed_ports"] == [port]
    assert rep["services_skipping"] or rep["suspended_services"]
    assert len(res["rows"]) == 2
    assert res["rows"][0]["profit_change"] <= res["rows"][1]["profit_change"]


def test_exposure_shares_and_resilience_order(client):
    exp = client.post("/api/chokepoints/exposure", json={"run": RUN}).json()
    ids = [p["id"] for p in exp["passages"]]
    assert set(ids) <= set(chokepoints.CHOKEPOINTS)
    for p in exp["passages"]:
        assert p["teu_per_week"] > 0 and 0 < p["share_of_teu_legs_pct"] <= 100
    res = client.post("/api/resilience", json={"run": RUN, "target": "passages", "limit": 60}).json()
    changes = [r["profit_change"] for r in res["rows"]]
    assert changes == sorted(changes)
    assert {r["id"] for r in res["rows"]} <= set(ids)
    assert client.post("/api/resilience", json={"run": RUN, "target": "planets"}).status_code == 422


# ── transit finder (backend/transit.py) ──

@pytest.fixture(scope="module")
def tclient(client):
    from backend import transit
    app = FastAPI()
    app.include_router(transit.router)
    return TestClient(app)


def test_transit_finder_matches_engine_rules_and_flow_lp(tclient):
    body = tclient.post("/api/transit", json={"run": RUN, "origin": "cnytn", "destination": "USLAX"}).json()
    assert body["origin"] == "CNYTN" and body["destination"] == "USLAX"
    rows = body["itineraries"]
    assert rows and [r["transit_days"] for r in rows] == sorted(r["transit_days"] for r in rows)
    dm = body["demand"]
    assert dm and dm["max_transit_days"] is not None
    # the flow LP only routes over itineraries within the limit, and never more than the demand
    assert 0 < dm["routed_teu"] <= dm["weekly_teu"] + 1e-6
    assert all(r["within_limit"] for r in rows if r["plan_teu"] > 0)
    for r in rows:
        assert r["transfers"] == len(r["segments"]) - 1 == len(r["hubs"]) <= 2
        assert r["segments"][0]["from"] == "CNYTN" and r["segments"][-1]["to"] == "USLAX"
        for a, b in zip(r["segments"], r["segments"][1:]):
            assert a["to"] == b["from"]
        assert r["departures_per_week"] == min(s["departures_per_week"] for s in r["segments"])
    direct = tclient.post("/api/transit", json={"run": RUN, "origin": "CNYTN", "destination": "USLAX", "max_transfers": 0}).json()
    assert direct["itineraries"] and all(r["transfers"] == 0 for r in direct["itineraries"])


def test_transit_finder_errors(tclient):
    assert tclient.post("/api/transit", json={"run": RUN, "origin": "NLRTM", "destination": "NLRTM"}).status_code == 422
    assert tclient.post("/api/transit", json={"run": RUN, "origin": "NLRTM", "destination": "XXXXX"}).status_code == 422
    assert tclient.post("/api/transit", json={"run": RUN, "origin": "NLRTM", "destination": "CNSHA", "max_transfers": 3}).status_code == 422
