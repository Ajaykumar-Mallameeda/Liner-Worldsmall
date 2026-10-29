"""Emissions, EU ETS, ECA fuel, slow steaming and the profit-vs-CO2 front (backend/emissions.py)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import emissions as em

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}


# ── rules ──

def test_eca_polygons_follow_marpol_limits():
    assert em.eca_at(4.0, 52.0) == "North Sea area"
    assert em.eca_at(20.0, 57.0) == "Baltic Sea area"
    assert em.eca_at(-74.0, 40.0) == "North American area"
    assert em.eca_at(18.0, 35.0) == "Mediterranean Sea area"           # in force 2025-05-01
    assert em.eca_at(28.0, 40.8) == "Mediterranean Sea area"           # Sea of Marmara, south of 41°N
    assert em.eca_at(29.0, 41.5) is None                              # Black Sea
    assert em.eca_at(-6.0, 36.0) is None                              # west of 5°36'W
    assert em.eca_at(-3.0, 46.0) is None                              # Bay of Biscay
    assert em.eca_at(0.0, 0.0) is None
    assert em.eca_at(4.0 + 360, 52.0) == "North Sea area"             # unwrapped longitudes fold back


def test_ets_leg_factor_and_transhipment_rule():
    # NL -> CN -> US -> NL: EU->non-EU 50 %, non-EU->non-EU 0 %, non-EU->EU 50 %
    assert [em.ets_leg_factor(("NLRTM", "CNSHA", "USLAX"), i) for i in range(3)] == [0.5, 0.0, 0.5]
    assert em.ets_leg_factor(("NLRTM", "DEHAM"), 0) == 1.0
    # East Port Said is not a port of call: IT -> EGPSD -> CN counts as an EU departure on both legs
    assert [em.ets_leg_factor(("ITGIT", "EGPSD", "CNSHA"), i) for i in range(3)] == [0.5, 0.5, 0.5]
    assert em.ets_phase(2024) == 0.4 and em.ets_phase(2025) == 0.7 and em.ets_phase(2026) == 1.0


def test_cii_rating_boundaries():
    dwt = 100_000
    ref = 1984 * dwt ** -0.489
    req = ref * (1 - 0.11)
    assert em.cii_rating(req * 0.80, dwt, 2026)["rating"] == "A"
    assert em.cii_rating(req * 0.90, dwt, 2026)["rating"] == "B"
    assert em.cii_rating(req * 1.00, dwt, 2026)["rating"] == "C"
    assert em.cii_rating(req * 1.10, dwt, 2026)["rating"] == "D"
    assert em.cii_rating(req * 1.25, dwt, 2026)["rating"] == "E"
    # a stricter year turns the same ship worse
    assert em.cii_rating(req, dwt, 2030)["ratio"] > em.cii_rating(req, dwt, 2026)["ratio"]


# ── endpoints ──

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("searoute")
    from backend import run_catalog
    try:
        run_catalog._dataset_dir("worldsmall")
    except Exception:
        pytest.skip("no WorldSmall benchmark runs")
    app = FastAPI()
    app.include_router(em.router)
    return TestClient(app)


def test_design_speed_without_rules_is_the_ledger(client):
    b = client.post("/api/emissions", json={"run": RUN, "eca": False, "ets": False, "eur_usd": 1.1}).json()
    p = b["plan"]
    assert p["fuel_cost"] == pytest.approx(p["ledger_fuel_cost"], rel=1e-9)
    assert p["profit"] == pytest.approx(p["ledger_profit"], rel=1e-9)
    assert p["co2_t"] == pytest.approx(p["fuel_t"] * em.CF_MAIN, rel=1e-9)
    assert p["mgo_t"] == 0 and p["ets_cost"] == 0


def test_ets_and_eca_cost_money_and_scale(client):
    a = client.post("/api/emissions", json={"run": RUN, "eua_eur_per_t": 50, "eur_usd": 1.1}).json()["plan"]
    b = client.post("/api/emissions", json={"run": RUN, "eua_eur_per_t": 100, "eur_usd": 1.1}).json()["plan"]
    assert a["ets_cost"] > 0 and b["ets_cost"] == pytest.approx(2 * a["ets_cost"], rel=1e-9)
    assert 0 < a["ets_co2_t"] < a["co2_t"]
    assert a["mgo_t"] > 0 and a["mgo_extra_cost"] == pytest.approx(a["mgo_t"] * 200, rel=1e-9)
    assert 0 < a["eca_share_of_nm"] < 1
    y24 = client.post("/api/emissions", json={"run": RUN, "ets_year": 2024, "eur_usd": 1.1}).json()["plan"]
    y26 = client.post("/api/emissions", json={"run": RUN, "ets_year": 2026, "eur_usd": 1.1}).json()["plan"]
    assert y24["ets_co2_t"] == pytest.approx(0.4 * y26["ets_co2_t"], rel=1e-9)


def test_slow_steaming_cuts_co2_needs_vessels_and_is_bounded(client):
    b = client.post("/api/emissions", json={"run": RUN, "eur_usd": 1.1}).json()
    lo = b["settings"]["speed_range"]["min"]
    s = round(min(1.0, lo + 0.06), 2)
    slow = client.post("/api/emissions", json={"run": RUN, "speed_factor": s, "eur_usd": 1.1}).json()
    assert slow["scenario"]["co2_t"] < slow["plan"]["co2_t"]
    assert slow["scenario"]["vessels"] >= slow["plan"]["vessels"]
    grades = slow["scenario"]["cii_grades"]
    assert grades.get("A", 0) >= b["plan"]["cii_grades"].get("A", 0)
    assert client.post("/api/emissions", json={"run": RUN, "speed_factor": round(lo - 0.05, 2)}).status_code == 422


def test_front_is_ordered_and_marks_efficiency(client):
    f = client.post("/api/emissions/front", json={"run": RUN, "eur_usd": 1.1}).json()
    pts = f["points"]
    assert len(pts) >= 5 and pts[-1]["speed_factor"] == 1.0
    co2 = [p["co2_t"] for p in pts]
    assert co2 == sorted(co2)                      # slower = less CO2
    for p in pts:
        dominated = any(q["profit"] >= p["profit"] and q["co2_t"] <= p["co2_t"]
                        and (q["profit"] > p["profit"] or q["co2_t"] < p["co2_t"]) for q in pts if q is not p)
        assert p["efficient"] == (not dominated)


def test_eca_zones_endpoint(client):
    z = client.get("/api/eca/zones").json()
    names = {f["properties"]["name"] for f in z["features"]}
    assert {"Baltic Sea area", "North Sea area", "North American area", "Mediterranean Sea area"} <= names
