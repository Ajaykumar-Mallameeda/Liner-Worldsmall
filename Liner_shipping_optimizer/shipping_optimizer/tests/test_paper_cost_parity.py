"""Paper-comparison cost parity (six targets) - FFE-native evaluator and its independent ledger.

Scope: the paper's cost equations (arXiv:2411.09068, App. A, Eq. 28-35) only; no RL policy, no heuristic-MCF reproduction.
Operational C3 is not touched.  Hand-calculated values are written out as plain arithmetic.

  3.1 units          representation invariance (FFE-native vs TEU-native), loader-boundary agreement, no revenue inflation
  3.2 fuel           sailing time at design speed, one idle day per call, per class, intermediate values and units
  3.3 fleet          fewer / exactly / more vessels than owned; operational C3 still rejects an over-fleet plan
  3.4 port / handling one call, one load/unload, one transshipment, small end-to-end example, evaluator == ledger
  3.5 canal          traversals x class fee once per rotation; blank Panama fee = cannot pass; authors' log (stored result)
  3.6 objective      accepted demand earns once, rejected demand pays 1000/FFE once, full independent recomputation
"""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.benchmark.paper_evaluator import FfeData, evaluate, load_worldsmall_ffe, net_profit, transfer_ports
from src.benchmark.paper_ledger import (fleet_accounting, hops_from_edges, objective_ledger, rotation_costs, to_teu_native)

RAW = ROOT / "data" / "raw" / "WorldSmall"
PARITY = ROOT / "reports" / "continuation_20261015" / "ws3_paper_parity"
LOG = Path(r"C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master\results\BrouerDesaulniersPisinger2014\WorldSmall_Best_Base.log")


@pytest.fixture(scope="module")
def data():
    return load_worldsmall_ffe(RAW)


def _toy():
    ports = {p: {"pf": 100.0, "pv": 1.0, "pl": 10.0, "pt": 20.0} for p in "ABC"}
    dist = {("A", "B"): (240.0, 0, 0), ("B", "A"): (240.0, 0, 0), ("B", "C"): (240.0, 0, 0), ("C", "B"): (240.0, 0, 0)}
    classes = {"X": {"cap": 100.0, "n_avail": 5.0, "tc": 1000.0, "speed": 10.0, "fuel_sea": 10.0, "fuel_idle": 1.0,
                     "panama": None, "suez": None}}
    dem = [{"o": "A", "d": "B", "ffe": 150.0, "rev": 500.0}, {"o": "B", "d": "C", "ffe": 50.0, "rev": 800.0},
           {"o": "A", "d": "C", "ffe": 40.0, "rev": 900.0}]
    return FfeData(ports, dem, dist, classes)


TOY_DESIGN = [{"ports": ["A", "B"], "class": "X"}, {"ports": ["B", "C"], "class": "X"}]


def _flows_from(r):
    """Explicit hop-level flows from the evaluator's raw flows (an independent representation for the ledger)."""
    return r["_services"], r["_flows"], r["_rejected"]


def _ledger_of(data, r, price=600.0, **kw):
    services, flows, rejected = _flows_from(r)
    fl = [{"od": (data.demands[di]["o"], data.demands[di]["d"]), "ffe": q, "hops": hops_from_edges(services, edges)}
          for di, edges, q in flows]
    rej = {(data.demands[di]["o"], data.demands[di]["d"]): q for di, q in rejected.items()}
    return objective_ledger(data, [{"ports": s["ports"], "class": s["class"], "n": s["n"], "f": s["f"]} for s in services],
                            fl, rej, fuel_price_usd_per_t=price, **kw)


# =============================================================================================================== 3.1
class TestUnitContract:
    DESIGN = [{"ports": ["CNSHA", "KRPUS", "USLAX"], "class": "Post_panamax"},
              {"ports": ["USLAX", "USCHS", "NLRTM"], "class": "Panamax_2400"},
              {"ports": ["NLRTM", "DEHAM", "GBFXT"], "class": "Feeder_800"},
              {"ports": ["CNSHA", "HKHKG", "SGSIN"], "class": "Panamax_1200"}]

    def test_teu_native_representation_equals_the_operational_loader_boundary(self, data):
        from src.data.network_loader import NetworkLoader
        loader = NetworkLoader()
        teu = to_teu_native(data)
        got = {(d.origin, d.destination): d for d in loader.load_demands()}
        for d in teu.demands:
            g = got[(d["o"], d["d"])]
            assert d["ffe"] == pytest.approx(g.weekly_teu, rel=1e-12)           # "ffe" now holds TEU
            assert d["rev"] == pytest.approx(g.revenue_per_teu, rel=1e-12)
        for c in loader.load_fleet().classes:
            assert teu.classes[c.vessel_class]["cap"] == pytest.approx(c.capacity_teu, rel=1e-12)   # converted exactly once
        for p in loader.load_ports():
            assert teu.ports[p.id]["pl"] == pytest.approx(p.handling_cost)
            assert teu.ports[p.id]["pt"] == pytest.approx(p.transshipment_cost)
            assert teu.ports[p.id]["pv"] == pytest.approx(p.variable_port_call_cost)
            assert teu.ports[p.id]["pf"] == pytest.approx(p.port_call_cost)

    def test_gross_revenue_at_full_demand_is_not_inflated(self, data):
        teu = to_teu_native(data)
        gross_ffe = sum(d["ffe"] * d["rev"] for d in data.demands)
        gross_teu = sum(d["ffe"] * d["rev"] for d in teu.demands)
        raw = pd.read_csv(RAW / "Demand_WorldSmall_Fixed_Sep.csv", sep="\t")
        raw = raw[raw.Origin != raw.Destination]
        assert gross_ffe == pytest.approx(float((raw.FFEPerWeek * raw.Revenue_1).sum()), rel=1e-12)
        assert gross_teu == pytest.approx(gross_ffe, rel=1e-12)              # not x2, not x4

    def test_equivalent_representations_give_the_same_physical_and_economic_result(self, data):
        a = evaluate(data, self.DESIGN, canal_basis="per_rotation", return_flows=True)
        b = evaluate(to_teu_native(data), self.DESIGN, canal_basis="per_rotation", return_flows=True)
        for k in ("revenue", "rejected_penalty", "handling_and_transshipment", "vessel_service_cost", "unused_vessel_profit",
                  "voyage_cost_without_fuel", "fuel_tonnes_per_week", "vessels_used", "coverage"):
            assert b[k] == pytest.approx(a[k], rel=1e-9, abs=1e-6), k
        assert b["served_ffe"] == pytest.approx(2.0 * a["served_ffe"], rel=1e-9)        # TEU = 2 x FFE (physical cargo)
        assert b["rejected_ffe"] == pytest.approx(2.0 * a["rejected_ffe"], rel=1e-9)
        assert net_profit(b) == pytest.approx(net_profit(a), rel=1e-9)

        def load_factor(r, d):
            carried = offered = 0.0
            for s in r["_services"]:
                offered += d.classes[s["class"]]["cap"] * len(s["ports"])
            for di, edges, q in r["_flows"]:
                carried += q * len(edges)
            return carried / offered
        assert load_factor(a, data) == pytest.approx(load_factor(b, to_teu_native(data)), rel=1e-12)

    def test_no_double_conversion_in_the_ledger(self, data):
        a = evaluate(data, self.DESIGN, canal_basis="per_rotation", return_flows=True)
        b = evaluate(to_teu_native(data), self.DESIGN, canal_basis="per_rotation", return_flows=True)
        la, lb = _ledger_of(data, a), _ledger_of(to_teu_native(data), b)
        assert lb["net_profit_usd"] == pytest.approx(la["net_profit_usd"], rel=1e-9)
        assert lb["revenue_usd"] == pytest.approx(la["revenue_usd"], rel=1e-9)


# =============================================================================================================== 3.2
# CNSHA <-> JPYOK, 1,040 nm each way: 2,080 nm closed rotation, 2 port calls (hand arithmetic; see module docstring)
HAND = {   # class: (design speed kn, sea days, vessels, sailing fuel t, idle fuel t, fuel USD at 600 USD/t)
    "Feeder_450":    (12.0,  2080 / (12.0 * 24),  (2080 / (12.0 * 24) + 2) / 7, 2080 / (12.0 * 24) * 18.8, 2 * 2.4, (2080 / (12.0 * 24) * 18.8 + 4.8) * 600),
    "Feeder_800":    (14.0,  2080 / (14.0 * 24),  (2080 / (14.0 * 24) + 2) / 7, 2080 / (14.0 * 24) * 23.7, 2 * 2.5, (2080 / (14.0 * 24) * 23.7 + 5.0) * 600),
    "Panamax_1200":  (18.0,  2080 / (18.0 * 24),  (2080 / (18.0 * 24) + 2) / 7, 2080 / (18.0 * 24) * 52.5, 2 * 4.0, (2080 / (18.0 * 24) * 52.5 + 8.0) * 600),
    "Panamax_2400":  (16.0,  2080 / (16.0 * 24),  (2080 / (16.0 * 24) + 2) / 7, 2080 / (16.0 * 24) * 57.4, 2 * 5.3, (2080 / (16.0 * 24) * 57.4 + 10.6) * 600),
    "Post_panamax":  (16.5,  2080 / (16.5 * 24),  (2080 / (16.5 * 24) + 2) / 7, 2080 / (16.5 * 24) * 82.2, 2 * 7.4, (2080 / (16.5 * 24) * 82.2 + 14.8) * 600),
    "Super_panamax": (17.0,  2080 / (17.0 * 24),  (2080 / (17.0 * 24) + 2) / 7, 2080 / (17.0 * 24) * 126.9, 2 * 10.0, (2080 / (17.0 * 24) * 126.9 + 20.0) * 600),
}
LITERAL = {   # the same quantities written as numbers (rounded) - guards against a formula drifting together with the code
    "Feeder_450": (7.2222, 1.31746, 135.778, 4.8, 84346.67),
    "Feeder_800": (6.1905, 1.17007, 146.714, 5.0, 91028.57),
    "Panamax_1200": (4.8148, 0.97354, 252.778, 8.0, 156466.67),
    "Panamax_2400": (5.4167, 1.05952, 310.917, 10.6, 192910.00),
    "Post_panamax": (5.2525, 1.03607, 431.758, 14.8, 267934.55),
    "Super_panamax": (5.0980, 1.01401, 646.941, 20.0, 400164.71),
}


class TestSailingAndIdleFuel:
    @pytest.mark.parametrize("cls", list(HAND))
    def test_rotation_fuel_per_class(self, data, cls):
        spd, sea_days, n, sail_t, idle_t, usd = HAND[cls]
        rc = rotation_costs(data, ["CNSHA", "JPYOK"], cls, fuel_price_usd_per_t=600.0)
        assert rc["distance_nm"] == 2080.0
        assert rc["speed_knots"] == spd == data.classes[cls]["speed"]           # design speed, knots
        assert rc["sea_days"] == pytest.approx(sea_days) and rc["port_days"] == 2.0       # 1 day per call, 2 calls
        assert rc["vessels_for_weekly_service"] == pytest.approx(n)
        assert rc["sailing_fuel_t"] == pytest.approx(sail_t)                    # sea days x t/day at design speed
        assert rc["idle_fuel_t"] == pytest.approx(idle_t)                       # 2 days x idle t/day
        assert rc["fuel_usd"] == pytest.approx(usd)
        lit = LITERAL[cls]
        assert (rc["sea_days"], rc["vessels_for_weekly_service"], rc["sailing_fuel_t"], rc["idle_fuel_t"], rc["fuel_usd"]) == pytest.approx(
            lit, rel=2e-5)

    def test_fuel_price_is_never_invented(self, data):
        rc = rotation_costs(data, ["CNSHA", "JPYOK"], "Feeder_450")
        assert rc["fuel_usd"] is None and rc["fuel_price_usd_per_t"] is None
        assert rc["fuel_t"] == pytest.approx(135.7778 + 4.8, rel=1e-5)          # tonnes stay available
        led = objective_ledger(data, [{"ports": ["CNSHA", "JPYOK"], "class": "Feeder_450", "n": 1.3, "f": 1}], [], {},
                               fuel_price_usd_per_t=None)
        assert led["fuel_usd"] is None and led["net_profit_usd"] is None        # explicit unavailable, not a zero

    def test_closing_leg_is_counted_once(self, data):
        a = rotation_costs(data, ["CNSHA", "JPYOK"], "Feeder_450")
        assert a["distance_nm"] == 2 * 1040.0 and a["port_days"] == 2.0      # out, back: not 3 legs, not 3 calls

    def test_cubic_speed_law_only_when_a_speed_is_given(self, data):
        d = rotation_costs(data, ["CNSHA", "JPYOK"], "Feeder_450")
        s = rotation_costs(data, ["CNSHA", "JPYOK"], "Feeder_450", speed_knots=6.0)
        assert s["sea_days"] == pytest.approx(2.0 * d["sea_days"])
        assert s["sailing_fuel_t"] == pytest.approx(d["sailing_fuel_t"] * 2.0 * 0.5 ** 3)      # twice as long, 1/8 per day

    def test_evaluator_agrees_with_the_ledger_rotation_costs(self, data):
        r = evaluate(data, [{"ports": ["CNSHA", "JPYOK"], "class": "Post_panamax"}])
        rc = rotation_costs(data, ["CNSHA", "JPYOK"], "Post_panamax")
        assert r["fuel_tonnes_per_week"] == pytest.approx(rc["fuel_t"])


# =============================================================================================================== 3.3
class TestFleetAccounting:
    def _fa(self, data, used):
        return fleet_accounting(data, {"Feeder_450": used})["by_class"]["Feeder_450"]       # owned 24, TC 5,000 / day

    def test_fewer_vessels_than_owned_credit(self, data):
        r = self._fa(data, 10.0)
        assert r["case"] == "fewer_than_owned"
        assert r["service_cost_usd"] == 10.0 * 5000 * 7 == 350_000.0
        assert r["unused_credit_usd"] == (24 - 10) * 5000 * 7 == 490_000.0          # spare vessels are rented out: a credit

    def test_exactly_the_owned_fleet(self, data):
        r = self._fa(data, 24.0)
        assert r["case"] == "exactly_owned"
        assert r["service_cost_usd"] == 24 * 35_000.0 == 840_000.0
        assert r["unused_credit_usd"] == 0.0

    def test_more_vessels_than_owned_charge(self, data):
        r = self._fa(data, 30.0)
        assert r["case"] == "more_than_owned"
        assert r["unused_credit_usd"] == (24 - 30) * 35_000.0 == -210_000.0         # the extra 6 are acquired at the TC rate
        net = fleet_accounting(data, {"Feeder_450": 30.0})
        # the whole fleet: net cost of a class = used x TC - (owned - used) x TC = (2 used - owned) x TC; others fully credited
        others = sum(c["n_avail"] * c["tc"] * 7 for n, c in data.classes.items() if n != "Feeder_450")
        assert net["net_fleet_cost_usd"] == pytest.approx(30 * 35_000.0 + 210_000.0 - others)

    def test_paper_table1_unused_term_has_the_same_sign_convention(self):
        """Paper Table 1 (Baltic, classes priced like WorldSmall: Feeder_450 5,000 and Feeder_800 8,000 per day; the
        owned fleet 4 and 2 is inferred from the table itself, see the parity matrix): used 6.34 vessels -> a negative
        'unused vessel profit' (-12,596), used 5.72 -> positive (+6,823)."""
        tc450, tc800 = 5000 * 7, 8000 * 7
        rl = (4 - 4.31) * tc450 + (2 - 2.03) * tc800
        lin = (4 - 3.58) * tc450 + (2 - 2.14) * tc800
        assert rl < 0 < lin
        assert rl == pytest.approx(-12_596, abs=100)       # vessel counts are rounded to 2 decimals in the paper
        assert lin == pytest.approx(6_823, abs=100)
        assert 3.58 * tc450 + 2.14 * tc800 == pytest.approx(245_176, abs=100)       # LINERLIB column: vessel service cost

    def test_operational_c3_still_rejects_an_over_fleet_plan(self):
        from src.network.economics import DEFAULT_ASSUMPTIONS
        from src.network.ledger import LedgerService, compute_ledger
        from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem
        v = FleetClass(vessel_class="V", quantity=5, capacity_teu=1000.0, tc_rate_daily=8000.0, min_speed=10.0,
                       design_speed=12.0, max_speed=14.0, bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
        ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0, variable_port_call_cost=0.0)
                 for p in "AB"]
        dm = {"A": {"B": 1000.0}, "B": {"A": 1200.0}}
        d = [Demand("A", "B", 100.0, 1000.0)]
        pr = Problem(ports=ports, services=[], demands=d, distance_matrix=dm, fleet=Fleet(classes=[v]))
        a = DEFAULT_ASSUMPTIONS
        led = compute_ledger([LedgerService("s", ("A", "B"), "V", 4)], [], d, pr.fleet, pr.distance_matrix,
                             {p.id: p for p in pr.ports}, port_stay_hours=a.port_stay_hours,
                             transshipment_min_hours=a.transshipment_min_hours, transfer_wait_days=a.transfer_wait_days,
                             bunker_price_usd_per_t=a.bunker_price_usd_per_t)
        assert any(x["type"] == "fleet_exceeded" for x in led.violations)           # needs 6 > 5: a hard violation


# =============================================================================================================== 3.4 / 3.6
class TestPortHandlingTransshipmentAndObjective:
    def test_one_port_call(self, data):
        rc = rotation_costs(data, ["CNSHA", "JPYOK"], "Post_panamax")
        # CNSHA: 6,497 + 6 x 4,200 = 31,697; JPYOK: 16,900 + 1 x 4,200 = 21,100  -> per rotation 52,797
        assert rc["port_call_fixed_usd"] == 6497.0 + 16900.0
        assert rc["port_call_per_ffe_capacity_usd"] == (6.0 + 1.0) * 4200.0
        assert rc["port_call_fixed_usd"] + rc["port_call_per_ffe_capacity_usd"] == 52_797.0

    def test_one_loading_and_unloading_and_one_transshipment(self):
        d = _toy()
        d.demands = [{"o": "A", "d": "B", "ffe": 30.0, "rev": 500.0}]
        r = evaluate(d, TOY_DESIGN, return_flows=True)
        assert r["handling_and_transshipment"] == 30 * (10 + 10)                    # p_l at origin and destination, no p_t
        d.demands = [{"o": "A", "d": "C", "ffe": 30.0, "rev": 500.0}]
        r = evaluate(d, TOY_DESIGN, return_flows=True)
        assert r["handling_and_transshipment"] == 30 * (10 + 10 + 20)               # + p_t once, at B
        led = _ledger_of(d, r)
        assert led["transshipment_usd"] == 30 * 20 and led["handling_loading_unloading_usd"] == 30 * 20

    def test_small_end_to_end_example_by_hand(self):
        d = _toy()
        r = evaluate(d, TOY_DESIGN, canal_basis="per_rotation", return_flows=True)
        # greedy by revenue: A->C (900, 40 FFE) via A-B then B-C; B->C (800, 50); A->B (500, 150: only 60 of the 100 left)
        assert r["served_ffe"] == 40 + 50 + 60 and r["rejected_ffe"] == 90
        led = _ledger_of(d, r)
        hand = {
            "revenue": 40 * 900 + 50 * 800 + 60 * 500,                                  # 106,000
            "penalty": 1000 * 90,                                                       # 90,000
            "handling_ll": 40 * 20 + 50 * 20 + 60 * 20,                                 # 3,000
            "transship": 40 * 20,                                                       # 800 (A->C changes at B)
            "service": (2 * (2 + 2) / 7) * 1000 * 7,                                    # two services, 4 days each: 8,000
            "port_calls": 2 * (2 * (100 + 1 * 100)),                                    # 800
            "fuel": 2 * (2 * 10 + 2 * 1) * 600,                                         # 26,400
        }
        hand["unused_credit"] = (5 - 8 / 7) * 1000 * 7                                  # 5 owned - 8/7 used: 27,000
        profit = (hand["revenue"] - hand["penalty"] - hand["handling_ll"] - hand["transship"] - hand["service"]
                  + hand["unused_credit"] - hand["port_calls"] - hand["fuel"])
        assert profit == pytest.approx(4_000.0)
        assert led["revenue_usd"] == pytest.approx(hand["revenue"])
        assert led["rejected_penalty_usd"] == pytest.approx(hand["penalty"])
        assert led["handling_loading_unloading_usd"] == pytest.approx(hand["handling_ll"])
        assert led["transshipment_usd"] == pytest.approx(hand["transship"])
        assert led["vessel_service_usd"] == pytest.approx(hand["service"])
        assert led["unused_vessel_credit_usd"] == pytest.approx(hand["unused_credit"])
        assert led["port_calls_usd"] == pytest.approx(hand["port_calls"])
        assert led["fuel_usd"] == pytest.approx(hand["fuel"])
        assert led["net_profit_usd"] == pytest.approx(4_000.0)
        assert net_profit(r) == pytest.approx(4_000.0)                                  # evaluator == independent ledger

    def test_accepted_demand_earns_once_rejected_pays_once(self):
        d = _toy()
        r = evaluate(d, TOY_DESIGN, return_flows=True)
        led = _ledger_of(d, r)
        assert led["served_ffe"] + led["rejected_ffe"] == pytest.approx(led["demand_ffe"])       # nothing counted twice or lost
        assert led["revenue_usd"] == pytest.approx(sum(q * d.demands[di]["rev"] for di, _e, q in r["_flows"]))
        assert led["rejected_penalty_usd"] == 1000.0 * led["rejected_ffe"]

    def test_transfer_port_is_where_the_earlier_service_is_left(self):
        """A service carrying a flow over two legs must charge p_t at the END of its last leg (regression: the start of the
        last leg was used, which is a different port whenever a service carries the flow over more than one leg)."""
        d = _toy()
        d.ports["B"]["pt"] = 5.0
        d.ports["C"]["pt"] = 99.0
        d.ports["D"] = dict(d.ports["A"], pt=40.0)
        for p in "ABC":
            d.dist[(p, "D")] = (240.0, 0, 0)
            d.dist[("D", p)] = (240.0, 0, 0)
        d.dist[("A", "C")] = d.dist[("C", "A")] = (480.0, 0, 0)
        d.demands = [{"o": "A", "d": "D", "ffe": 10.0, "rev": 700.0}]
        design = [{"ports": ["A", "B", "C"], "class": "X"}, {"ports": ["C", "D"], "class": "X"}]
        r = evaluate(d, design, return_flows=True)
        assert r["served_ffe"] == 10.0
        services, flows, _ = r["_services"], r["_flows"], r["_rejected"]
        ports_left = transfer_ports(services, flows[0][1])
        assert ports_left == ["C"]                                                      # service 0 is left at C, not at B
        assert r["handling_and_transshipment"] == 10 * (10 + 10 + 99)
        led = _ledger_of(d, r)
        assert led["transshipment_usd"] == 10 * 99

    def test_evaluator_equals_independent_ledger_on_worldsmall(self, data):
        design = TestUnitContract.DESIGN
        r = evaluate(data, design, canal_basis="per_rotation", return_flows=True)
        led = _ledger_of(data, r)
        assert led["revenue_usd"] == pytest.approx(r["revenue"], rel=1e-9)
        assert led["rejected_penalty_usd"] == pytest.approx(r["rejected_penalty"], rel=1e-9)
        assert led["handling_total_usd"] == pytest.approx(r["handling_and_transshipment"], rel=1e-9)
        assert led["vessel_service_usd"] == pytest.approx(r["vessel_service_cost"], rel=1e-9)
        assert led["unused_vessel_credit_usd"] == pytest.approx(r["unused_vessel_profit"], rel=1e-9)
        assert led["port_calls_usd"] + led["canal_usd"] == pytest.approx(r["voyage_cost_without_fuel"], rel=1e-9)
        assert led["fuel_t"] == pytest.approx(r["fuel_tonnes_per_week"], rel=1e-9)
        assert led["net_profit_usd"] == pytest.approx(net_profit(r), rel=1e-9)
        assert led["served_ffe"] + led["rejected_ffe"] == pytest.approx(led["demand_ffe"], rel=1e-9)

    def test_paper_table1_objective_identity(self):
        """Eq. 28 / 32 on the paper's own Table 1 (Baltic, as printed; used only as an arithmetic identity, never as a
        profit target): profit = revenue - rejected - handling - voyage - service + unused."""
        for rev, unused, service, voyage, handling, rejected, profit in (
                (3_688_028, -12_596, 267_898, 634_729, 2_116_377, 380_000, 276_428),      # RL-based solution
                (3_687_260, 6_823, 245_176, 689_083, 2_109_876, 389_000, 260_948)):       # LINERLIB solution
            assert rev - rejected - handling - voyage - service + unused == profit
            assert rejected % 1000 == 0                                                 # 1,000 USD x whole FFE


# =============================================================================================================== 3.5
class TestCanal:
    def test_suez_fee_table_is_the_benchmark_input(self, data):
        fees = {n: c["suez"] for n, c in data.classes.items()}
        assert fees == {"Feeder_450": 175_769.0, "Feeder_800": 218_445.0, "Panamax_1200": 267_217.0,
                        "Panamax_2400": 413_533.0, "Post_panamax": 633_007.0, "Super_panamax": 1_035_376.0}
        assert data.classes["Post_panamax"]["panama"] is None and data.classes["Super_panamax"]["panama"] is None

    def test_traversals_times_class_fee_once_per_rotation(self, data):
        suez = [k for k, v in data.dist.items() if v[2] == 1][:1]
        assert suez, "WorldSmall has Suez legs"
        o, dst = suez[0]
        back = data.dist[(dst, o)]
        rc = rotation_costs(data, [o, dst], "Feeder_800")
        n_sue = data.dist[(o, dst)][2] + back[2]
        assert rc["canal_traversals"]["suez"] == n_sue and n_sue >= 1
        assert rc["canal_usd"] == n_sue * 218_445.0 + rc["canal_traversals"]["panama"] * 115_200.0

    def test_blank_panama_fee_means_cannot_pass_and_no_fee_is_invented(self, data):
        pan = [k for k, v in data.dist.items() if v[1] == 1][:1]
        o, dst = pan[0]
        rc = rotation_costs(data, [o, dst], "Post_panamax")
        assert rc["canal_unpassable"] and rc["canal_usd"] == 0.0 or rc["canal_traversals"]["suez"] > 0
        led = objective_ledger(data, [{"ports": [o, dst], "class": "Post_panamax", "n": 1.0, "f": 1}], [], {}, fuel_price_usd_per_t=600.0)
        assert led["canal_unpassable_transits"], "an unsupported Panama traversal is reported, not silently charged or ignored"

    def test_authors_solution_log_reconciliation_stored_result(self):
        p = PARITY / "linerlib_log_reconcile.json"
        if not p.exists():
            pytest.skip("reconciliation artifact not present")
        r = json.loads(p.read_text(encoding="utf-8"))
        c = r["service_level_checks"]
        assert r["services"] == 34 and c["traversal_counts_equal"] == 34
        assert c["canal_usd"]["max_abs_diff"] <= 4.0 and c["port_call_usd"]["max_abs_diff"] == 0.0
        assert c["time_charter_usd_week"]["max_abs_diff"] == 0.0 and c["distance_nm"]["max_abs_diff"] == 0.0
        assert c["idle_fuel_t"]["max_rel_diff"] < 1e-12 and c["sailing_fuel_t"]["max_rel_diff"] < 1e-4

    @pytest.mark.skipif(not LOG.exists(), reason="authors' LINERLIB log not on this machine")
    def test_authors_solution_log_reconciliation_rerun(self, tmp_path):
        out = tmp_path / "r.json"
        subprocess.run([sys.executable, "-I", str(ROOT / "reports" / "continuation_20261015" / "tools" / "linerlib_log_reconcile.py"),
                        str(LOG), str(out)], check=True, capture_output=True)
        r = json.loads(out.read_text(encoding="utf-8"))
        for term, rel in (("vessel_class_cost", 1e-9), ("idle_burn", 1e-9), ("canal", 1e-5), ("port_call", 1e-5), ("fuel_burn", 1e-5),
                          ("revenue", 1e-5), ("penalty", 1e-5), ("handling", 1e-5)):
            assert abs(r["term_vs_log"][term]["rel"]) <= rel, (term, r["term_vs_log"][term])
        o = r["objective"]
        assert o["recomputed_from_raw_files_and_logged_flows"] == pytest.approx(o["log_objective_line"], rel=1e-4)
