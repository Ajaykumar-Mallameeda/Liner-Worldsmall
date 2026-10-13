"""Issue 7 - the FFE-native paper-comparison evaluator is separate from the operational model and verified where the paper allows."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.benchmark.paper_evaluator import (FfeData, evaluate, load_worldsmall_ffe, net_profit, vessels_needed)

DESIGN_JSON = ROOT / "reports" / "issue7_paper_mode" / "paper_table6_design.json"


def _toy():
    ports = {p: {"pf": 100.0, "pv": 1.0, "pl": 10.0, "pt": 20.0} for p in "ABC"}
    dist = {("A", "B"): (240.0, 0, 0), ("B", "A"): (240.0, 0, 0), ("B", "C"): (240.0, 0, 0), ("C", "B"): (240.0, 0, 0)}
    classes = {"X": {"cap": 100.0, "n_avail": 5.0, "tc": 1000.0, "speed": 10.0, "fuel_sea": 10.0, "fuel_idle": 1.0,
                     "panama": None, "suez": None}}
    dem = [{"o": "A", "d": "B", "ffe": 150.0, "rev": 500.0}, {"o": "B", "d": "C", "ffe": 50.0, "rev": 800.0}]
    return FfeData(ports, dem, dist, classes)


def test_vessel_formula_is_distance_over_speed_plus_one_day_per_port_over_seven():
    d = _toy()
    # 480 nm round trip at 10 kn = 2 days sailing + 2 port days = 4 days -> 4/7 vessels
    assert vessels_needed(d, ["A", "B"], "X") == pytest.approx(4.0 / 7.0)


def test_greedy_routes_by_revenue_and_respects_capacity():
    d = _toy()
    r = evaluate(d, [{"ports": ["A", "B"], "class": "X"}, {"ports": ["B", "C"], "class": "X"}])
    # A->B demand 150 > capacity 100 on the A-B service: 100 carried, 50 rejected; B->C 50 carried
    assert r["served_ffe"] == pytest.approx(150.0)
    assert r["rejected_ffe"] == pytest.approx(50.0)
    assert r["rejected_penalty"] == pytest.approx(50.0 * 1000.0)
    assert r["revenue"] == pytest.approx(100 * 500 + 50 * 800)
    assert r["handling_and_transshipment"] == pytest.approx(150 * 2 * 10.0)


def test_transfer_pays_p_t_once():
    d = _toy()
    d.demands = [{"o": "A", "d": "C", "ffe": 40.0, "rev": 900.0}]
    r = evaluate(d, [{"ports": ["A", "B"], "class": "X"}, {"ports": ["B", "C"], "class": "X"}])
    assert r["served_ffe"] == pytest.approx(40.0)
    assert r["handling_and_transshipment"] == pytest.approx(40 * (10 + 10 + 20))


def test_unused_vessels_are_credited_at_the_time_charter_rate():
    d = _toy()
    r = evaluate(d, [{"ports": ["A", "B"], "class": "X"}])
    used = 4.0 / 7.0
    assert r["unused_vessel_profit"] == pytest.approx((5.0 - used) * 1000.0 * 7.0)


def test_ffe_native_scaling_invariance():
    """Scaling demand and capacity by the same factor scales flows; the profit terms scale linearly."""
    d1 = _toy()
    d2 = _toy()
    for x in d2.demands:
        x["ffe"] *= 2
    d2.classes["X"]["cap"] *= 2
    a = evaluate(d1, [{"ports": ["A", "B"], "class": "X"}, {"ports": ["B", "C"], "class": "X"}])
    b = evaluate(d2, [{"ports": ["A", "B"], "class": "X"}, {"ports": ["B", "C"], "class": "X"}])
    assert b["served_ffe"] == pytest.approx(2 * a["served_ffe"])
    assert b["revenue"] == pytest.approx(2 * a["revenue"])
    assert b["coverage"] == pytest.approx(a["coverage"])


@pytest.mark.skipif(not DESIGN_JSON.exists(), reason="paper Table 6 design extract not present")
def test_paper_table6_vessel_counts_are_reproduced():
    """Verified against the paper (Table 6): n = (sum nm / (design speed x 24) + 1 day per port) / 7 for all 19 schedules."""
    data = load_worldsmall_ffe(ROOT / "data" / "raw" / "WorldSmall")
    d = json.loads(DESIGN_JSON.read_text(encoding="utf-8"))
    from src.benchmark.paper_evaluator import class_by_capacity
    for s, cap, n in zip(d["schedules"], d["caps"], d["vessels"]):
        got = vessels_needed(data, s[:-1], class_by_capacity(data, cap))
        assert got == pytest.approx(n, abs=0.01 + 0.005 * n)


def test_operational_model_does_not_import_the_benchmark():
    for p in (ROOT / "src" / "network").glob("*.py"):
        assert "src.benchmark" not in p.read_text(encoding="utf-8"), p.name
