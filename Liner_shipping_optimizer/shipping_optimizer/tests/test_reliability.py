"""Schedule reliability / congestion Monte Carlo (backend/reliability.py, feature #7)."""

import types

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import reliability as rl

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}


def _svc(sail=(4.0, 4.0), f=1.0, vessels=2, speed=16.0, vmax=20.0, stay=1.0):
    m = types.SimpleNamespace(service_id="S", ports=("A", "B"), leg_sail_days=list(sail), speed_knots=speed)
    return rl.service_struct(m, f, vessels, vmax, stay)


def _draws(sv, hits):
    """Deterministic draws: hold of `e` days wherever hits[i] (u = 0 < p), nothing elsewhere."""
    shape = (rl.CHAINS, rl.WARM + rl.MEASURED + 1, sv["n"])
    u = np.ones(shape)
    e = np.zeros(shape)
    for (r, i), days in hits.items():
        u[:, r, i] = 0.0
        e[:, r, i] = days
    return {"u": u, "e": e}


def test_schedule_buffer_and_recovery_from_the_service_model():
    sv = _svc()
    assert list(sv["dep_t"]) == [0.0, 5.0] and list(sv["arr_t"]) == [4.0, 9.0]
    assert sv["round_voyage"] == 14.0 and sv["buffer"] == pytest.approx(14 - 8 - 2)
    assert sv["recover_frac"] == pytest.approx(0.2) and list(sv["recover"]) == pytest.approx([0.8, 0.8])


def test_no_disruption_no_delay():
    sv = _svc()
    arr, dep, slip = rl.simulate(sv, _draws(sv, {}), np.array([1.0, 1.0]), 3.0)
    assert not arr.any() and not dep.any() and not slip.any()


def test_hold_is_recovered_at_sea_then_absorbed_by_the_buffer():
    sv = _svc()
    # 2-day hold at B (the call leg 0 arrives at) in round voyage 0
    arr, dep, slip = rl.simulate(sv, _draws(sv, {(0, 0): 2.0}), np.array([1.0, 1.0]), 1.0)
    assert arr[0, 0, 0] == 0.0 and dep[0, 0, 1] == pytest.approx(2.0)
    assert arr[0, 0, 1] == pytest.approx(2.0 - 0.8)          # sped up on leg B -> A
    assert dep[0, 1, 0] == pytest.approx(0.0)                # 1.2 d left, 4 d buffer absorbs it
    assert not slip.any()


def test_a_vessel_a_week_behind_is_re_phased():
    sv = _svc()
    arr, dep, slip = rl.simulate(sv, _draws(sv, {(0, 1): 12.0}), np.array([1.0, 1.0]), 1.0)
    # 12 d hold at A, minus 4 d buffer = 8 d >= one weekly slot: one blank sailing, 1 d left
    assert slip[0, 1] == 1 and dep[0, 1, 0] == pytest.approx(1.0)


@pytest.fixture(scope="module")
def client():
    from backend import run_catalog
    try:
        run_catalog._dataset_dir("worldsmall")
    except Exception:
        pytest.skip("no WorldSmall benchmark runs")
    app = FastAPI()
    app.include_router(rl.router)
    return TestClient(app)


def test_calibrated_to_the_target_and_reproducible(client):
    a = client.post("/api/reliability", json={"run": RUN}).json()
    c = a["calibration"]
    assert c["matched"] and a["plan"]["on_time_pct"] == pytest.approx(62.6, abs=1.0)
    assert a["plan"]["late_days"] == pytest.approx(5.31, abs=0.15)
    assert 0 < c["p"] < 1 and c["mu_days"] > 0
    b = client.post("/api/reliability", json={"run": RUN}).json()
    assert b["plan"]["cargo"] == a["plan"]["cargo"]                         # same seed, same answer
    h = a["plan"]["cargo"]["histogram"]
    assert sum(x["share_pct"] for x in h) == pytest.approx(100, abs=0.5)
    assert h[0]["share_pct"] == a["plan"]["cargo"]["on_time_pct"]


def test_congestion_hurts_the_port_and_the_network(client):
    b = client.post("/api/reliability", json={"run": RUN, "congested_ports": ["CNSHA"], "congestion_factor": 3}).json()
    plan = {p["port"]: p for p in b["plan"]["ports"]}
    scen = {p["port"]: p for p in b["scenario"]["ports"]}
    assert not plan["CNSHA"]["congested"] and scen["CNSHA"]["congested"]
    assert scen["CNSHA"]["departure_on_time_pct"] < plan["CNSHA"]["departure_on_time_pct"] - 5
    assert b["scenario"]["on_time_pct"] < b["plan"]["on_time_pct"]
    assert b["scenario"]["cargo"]["on_time_pct"] < b["plan"]["cargo"]["on_time_pct"]


def test_cargo_without_disruption_is_on_plan():
    from backend import whatif
    key, out = whatif._run_output(RUN)
    prep = whatif._prepare(key, out, whatif._dataset_of(RUN, out))
    ev = whatif._evaluate(prep, 1.0, 1.0, keep_paths=True)
    fleet = {c.vessel_class: c for c in prep["problem"].fleet.classes}
    svs, drs, idx = [], [], []
    rng = np.random.default_rng(1)
    vessels = {r["id"]: r["vessels"] for r in ev["per_service"]}
    for i, f in sorted(prep["freq"].items()):
        m = prep["models"][i]
        sv = rl.service_struct(m, float(f), int(vessels[m.service_id]), float(fleet[m.vessel_class].max_speed), prep["assumptions"].port_stay_days)
        svs.append(sv); drs.append(rl.draws(sv, rng)); idx.append(i)
    st = rl.network_stats(svs, drs, 0.0, 3.0, keep=True)
    assert st["on_time"] == 1.0
    by = {i: (sv, *sim) for i, sv, sim in zip(idx, svs, st["sims"])}
    flows = rl.cargo(ev["path_flows"], by, prep["assumptions"].transshipment_min_hours / 24, np.random.default_rng(2))
    assert flows and all(np.allclose(fl["delay"], 0.0) and not fl["missed"].any() for fl in flows)
