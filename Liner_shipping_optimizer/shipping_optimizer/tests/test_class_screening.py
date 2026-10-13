"""Task 10 - per-rotation vessel-class screening.

Synthetic network and fleet (hand-computed expectations):

    A<->B 1000 / 1050 nm ; B<->C 800 / 820 ; A<->C 1700 / 1700
    demand A->B 400 TEU and B->A 300 TEU at 1,000 USD/TEU, 30 d limit
    price 600 USD/t, port stay 24 h, port call 1,000 USD

    V: 1,000 TEU, 12 kn, 8,000/d, 20 t/d sea, 2 idle, 5 vessels
    W: 3,000 TEU, 16 kn, 15,000/d, 50 t/d sea, 4 idle, 3 vessels
    X:   500 TEU, 10 kn, 4,000/d, 12 t/d sea, 1 idle, 0 vessels   (registered, none owned)
    Z: 2,000 TEU, design speed 0 (invalid source data)

Rotation A-B (2,050 nm round trip):
    V: sea 2050/(12*24) = 7.1181 d, cycle ceil(9.1181) = 10 d, 2 vessels at f=1,
       fuel (7.1181*20 + 2*2) = 146.36 t -> 87,816.7 USD, hire 2*56,000 = 112,000,
       port calls 2,000, net revenue 700,000  => profit 498,183
    W: sea 2050/(16*24) = 5.3385 d, cycle 8 d, 2 vessels, fuel (5.3385*50 + 8) = 274.9 t
       -> 164,949 USD, hire 2*105,000 = 210,000, port 2,000          => profit 323,051
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.economics import assumptions_for_problem
from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem
from src.services.class_screening import (
    ENV_SCREEN, ClassScreener, ClassScreeningConfig, config_from_environment,
)
from src.services.service_feasibility import ServiceFeasibilityError

DM = {
    "A": {"B": 1000.0, "C": 1700.0},
    "B": {"A": 1050.0, "C": 800.0},
    "C": {"A": 1700.0, "B": 820.0},
}


def fleet(*, with_invalid=False):
    classes = [
        FleetClass("V", 5, 1000.0, 8000.0, draft=9, min_speed=10, max_speed=14, design_speed=12,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0),
        FleetClass("W", 3, 3000.0, 15000.0, draft=12, min_speed=12, max_speed=18, design_speed=16,
                   bunker_consumption_tons_per_day=50.0, idle_consumption_tons_per_day=4.0),
        FleetClass("X", 0, 500.0, 4000.0, draft=7, min_speed=8, max_speed=12, design_speed=10,
                   bunker_consumption_tons_per_day=12.0, idle_consumption_tons_per_day=1.0),
    ]
    if with_invalid:
        classes.append(FleetClass("Z", 4, 2000.0, 9000.0, draft=10, min_speed=0, max_speed=0,
                                  design_speed=0.0, bunker_consumption_tons_per_day=30.0,
                                  idle_consumption_tons_per_day=3.0))
    return Fleet(classes=classes)


def problem(demands=None, fl=None):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABC"]
    d = demands if demands is not None else [
        Demand("A", "B", 400.0, 1000.0, max_transit_days=30.0),
        Demand("B", "A", 300.0, 1000.0, max_transit_days=30.0)]
    return Problem(ports=ports, services=[], demands=d, distance_matrix=DM, fleet=fl or fleet())


def screener(k=2, pr=None):
    pr = pr or problem()
    return ClassScreener(pr, pr.fleet, assumptions_for_problem(pr), ClassScreeningConfig(k=k)), pr


V_SEA = 2050.0 / (12 * 24)
W_SEA = 2050.0 / (16 * 24)
V_FUEL = (V_SEA * 20 + 2 * 2) * 600.0
W_FUEL = (W_SEA * 50 + 2 * 4) * 600.0
V_PROFIT = 700_000 - (2 * 56_000 + V_FUEL + 2_000)
W_PROFIT = 700_000 - (2 * 105_000 + W_FUEL + 2_000)


# ====================================================== 1/4/5  evaluation per class
class TestEveryClassIsEvaluatedWithCanonicalEconomics:
    def test_all_registered_classes_appear_in_the_diagnostics(self):
        s, _ = screener()
        res = s.screen(["A", "B"], 1000.0)
        assert [e.vessel_class for e in res.evaluations] == ["V", "W", "X"]

    def test_hand_computed_economics_of_each_feasible_class(self):
        s, _ = screener()
        ev = {e.vessel_class: e for e in s.screen(["A", "B"], 1000.0).evaluations}
        v, w = ev["V"], ev["W"]
        assert v.feasible and w.feasible
        assert v.cycle_time_days == 10 and w.cycle_time_days == 8
        assert v.vessels_f1 == 2 and w.vessels_f1 == 2
        assert v.best_frequency == 1 and w.best_frequency == 1
        assert v.fuel_cost_best == pytest.approx(V_FUEL)
        assert w.fuel_cost_best == pytest.approx(W_FUEL)
        assert v.fixed_cost_best == pytest.approx(2 * 56_000 + V_FUEL + 2_000)
        assert w.fixed_cost_best == pytest.approx(2 * 105_000 + W_FUEL + 2_000)
        assert v.standalone_profit_best == pytest.approx(V_PROFIT)
        assert w.standalone_profit_best == pytest.approx(W_PROFIT)
        assert v.profit_per_vessel == pytest.approx(V_PROFIT / 2)

    def test_fuel_and_hire_are_class_specific(self):
        s, _ = screener()
        ev = {e.vessel_class: e for e in s.screen(["A", "B"], 1000.0).evaluations}
        assert ev["V"].fuel_tonnes_best != ev["W"].fuel_tonnes_best
        assert ev["V"].fixed_cost_best != ev["W"].fixed_cost_best

    def test_frequency_ceiling_comes_from_cycle_and_inventory(self):
        s, _ = screener()
        ev = {e.vessel_class: e for e in s.screen(["A", "B"], 1000.0).evaluations}
        assert ev["V"].max_departures == math.floor(7 * 5 / 10)       # 3
        assert ev["W"].max_departures == math.floor(7 * 3 / 8)        # 2
        assert ev["V"].inventory == 5 and ev["W"].inventory == 3

    def test_per_leg_capacity_is_cap_times_frequency(self):
        # 2,500 TEU each way: V needs f=3 (3,000 >= 2,500) but only 700 served per...
        d = [Demand("A", "B", 2500.0, 1000.0, max_transit_days=30.0),
             Demand("B", "A", 2500.0, 1000.0, max_transit_days=30.0)]
        s, _ = screener(pr=problem(d))
        v = {e.vessel_class: e for e in s.screen(["A", "B"], 1000.0).evaluations}["V"]
        assert v.best_frequency in (2, 3)
        assert v.served_teu_best <= 2 * 1000.0 * v.best_frequency + 1e-9     # cap * f on both legs
        w = {e.vessel_class: e for e in s.screen(["A", "B"], 3000.0).evaluations}["W"]
        assert w.best_frequency == 1                                         # 3,000 TEU covers 2,500
        assert w.served_teu_best == pytest.approx(5000.0)


# ============================================ 2/6/7  feasibility is never overridden
class TestFeasibilityAndInventory:
    def test_class_without_vessels_is_never_assigned(self):
        s, _ = screener(k=6)
        res = s.screen(["A", "B"], 500.0)             # nominal capacity match: class X (500 TEU)
        x = next(e for e in res.evaluations if e.vessel_class == "X")
        assert not x.feasible and "vessel_class_has_no_vessels" in x.reasons
        assert "X" not in [e.vessel_class for e in res.selected]

    def test_nominal_capacity_match_does_not_override_inventory(self):
        # legacy rule: nearest capacity to 500 TEU is X (none owned) -> next feasible
        s, _ = screener(k=1)
        res = s.screen(["A", "B"], 500.0)
        assert res.legacy_class == "V"
        assert [e.vessel_class for e in res.selected] == ["V"]

    def test_rotation_needing_more_vessels_than_owned_is_infeasible_for_that_class(self):
        # a very long rotation: W (3 vessels) needs more than it owns, V (5) may too
        dm = {"A": {"B": 6000.0}, "B": {"A": 6000.0}}
        pr = problem()
        pr.distance_matrix = dm
        s = ClassScreener(pr, pr.fleet, assumptions_for_problem(pr), ClassScreeningConfig(k=2))
        res = s.screen(["A", "B"], 1000.0)
        w = next(e for e in res.evaluations if e.vessel_class == "W")
        assert not w.feasible and "required_vessels_exceed_class_inventory" in w.reasons

    def test_invalid_class_data_is_an_explicit_reason_not_a_default(self):
        pr = problem(fl=fleet(with_invalid=True))
        s = ClassScreener(pr, pr.fleet, assumptions_for_problem(pr), ClassScreeningConfig(k=6))
        res = s.screen(["A", "B"], 2000.0)
        z = next(e for e in res.evaluations if e.vessel_class == "Z")
        assert not z.feasible and "invalid_vessel_speed" in z.reasons
        assert "Z" not in [e.vessel_class for e in res.selected]

    def test_missing_distance_makes_every_class_infeasible(self):
        pr = problem()
        pr.distance_matrix = {"A": {"B": 1000.0}, "B": {}, "C": {}}
        s = ClassScreener(pr, pr.fleet, assumptions_for_problem(pr), ClassScreeningConfig(k=2))
        res = s.screen(["A", "B"], 1000.0)
        assert res.selected == [] and res.reason == "no_feasible_class_for_rotation"
        assert all("missing_directed_distance" in e.reasons for e in res.evaluations)

    def test_no_fleet_is_an_error(self):
        pr = problem()
        with pytest.raises(ServiceFeasibilityError):
            ClassScreener(pr, None, assumptions_for_problem(pr), ClassScreeningConfig(k=2))


# ================================================================== 3/8/9  selection
class TestSelection:
    def test_best_profit_first_then_productivity_up_to_k(self):
        s, _ = screener(k=2)
        sel = s.screen(["A", "B"], 1000.0).selected
        assert [e.vessel_class for e in sel] == ["V", "W"]
        assert sel[0].selected_because == "highest_standalone_profit"
        assert sel[1].selected_because in ("highest_profit_per_vessel", "next_best_standalone_profit")

    def test_the_configured_maximum_is_respected(self):
        for k in (1, 2, 3):
            s, _ = screener(k=k)
            assert len(s.screen(["A", "B"], 1000.0).selected) <= k
        s, _ = screener(k=1)
        assert [e.vessel_class for e in s.screen(["A", "B"], 1000.0).selected] == ["V"]

    def test_the_largest_or_nearest_class_is_not_chosen_automatically(self):
        # target 3,000 TEU: the nearest class is W; the best economics are V's
        s, _ = screener(k=1)
        res = s.screen(["A", "B"], 3000.0)
        assert res.legacy_class == "W"
        assert [e.vessel_class for e in res.selected] == ["V"]

    def test_unprofitable_rotation_keeps_the_legacy_class_not_the_cheapest_ship(self):
        # stand-alone loss is no evidence about which class suits a feeder/transfer role;
        # "least loss" would always pick the cheapest, smallest class
        d = [Demand("A", "B", 5.0, 100.0, max_transit_days=30.0)]
        s, _ = screener(k=3, pr=problem(d))
        res = s.screen(["A", "B"], 3000.0)                # legacy (nearest capacity) = W
        assert all(not e.promising for e in res.evaluations if e.feasible)
        assert res.legacy_class == "W"
        assert [e.vessel_class for e in res.selected] == ["W"]
        assert res.selected[0].selected_because == "no_profitable_class_legacy_class_kept"
        assert res.selected[0].promising is False

    def test_when_the_legacy_class_is_infeasible_the_least_loss_class_is_used(self):
        d = [Demand("A", "B", 5.0, 100.0, max_transit_days=30.0)]
        s, _ = screener(k=3, pr=problem(d))
        res = s.screen(["A", "B"], 500.0)                 # nearest is X (no vessels) -> V is legacy
        assert res.legacy_class == "V" and [e.vessel_class for e in res.selected] == ["V"]

    def test_rotation_without_direct_cargo_keeps_the_legacy_class(self):
        d = [Demand("A", "C", 400.0, 1000.0, max_transit_days=30.0)]
        s, _ = screener(k=2, pr=problem(d))
        res = s.screen(["A", "B"], 1000.0)               # C is not on the rotation
        assert [e.vessel_class for e in res.selected] == [res.legacy_class]
        assert res.selected[0].selected_because == "no_direct_cargo_evidence_legacy_class"

    def test_transit_time_infeasible_cargo_is_not_valued(self):
        d = [Demand("A", "B", 400.0, 1000.0, max_transit_days=1.0)]      # sailing alone is 3.5 d
        s, _ = screener(k=2, pr=problem(d))
        res = s.screen(["A", "B"], 1000.0)
        assert all(e.direct_ride_feasible_ods == 0 for e in res.evaluations if e.feasible)

    def test_screening_is_deterministic(self):
        a, _ = screener(k=2)
        b, _ = screener(k=2)
        ra, rb = a.screen(["A", "B", "C"], 1500.0), b.screen(["A", "B", "C"], 1500.0)
        assert [e.to_dict() for e in ra.evaluations] == [e.to_dict() for e in rb.evaluations]
        assert [e.vessel_class for e in ra.selected] == [e.vessel_class for e in rb.selected]

    def test_report_counts_what_was_screened(self):
        s, _ = screener(k=2)
        s.screen(["A", "B"], 1000.0)
        s.screen(["A", "B"], 1000.0)                      # cached: counted once
        s.screen(["B", "C"], 1000.0)
        r = s.report.to_dict()
        assert r["rotations_screened"] == 2
        assert r["alternatives_emitted"] >= 2
        assert r["infeasible_combinations_by_reason"].get("vessel_class_has_no_vessels", 0) >= 2


# ========================================================= 10  the ledger agrees
class TestLedgerValidatesTheSelectedClass:
    def test_selected_alternatives_plan_and_the_ledger_confirms_vessels_and_class(self):
        s, pr = screener(k=2)
        alts = s.alternatives(["A", "B"], 1000.0)
        cands = [Candidate(f"s{i}", ("A", "B"), c) for i, c in enumerate(alts)]
        res = NetworkPlanner(pr, assumptions=assumptions_for_problem(pr)).plan(cands, time_limit_sec=30)
        assert res.ok, res.message
        led = res.ledger
        inv = {c.vessel_class: c.quantity for c in pr.fleet.classes}
        for cname, used in led.vessels_by_class.items():
            assert cname in inv and used <= inv[cname]
        # the plan operates exactly one of the alternatives on this single OD pair
        assert len(led.service_rows) == 1
        row = next(iter(led.service_rows.values()))
        want = {"V": (2, 56_000 * 2), "W": (2, 105_000 * 2)}[row["vessel_class"]]
        assert row["vessels"] == want[0] and row["vessel_cost"] == pytest.approx(want[1])
        assert res.reconciliation["reconciled"]

    def test_ledger_rejects_a_class_that_is_not_registered_or_has_no_vessels(self):
        pr = problem()
        kw = dict(port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
                  bunker_price_usd_per_t=600.0)
        plb = {p.id: p for p in pr.ports}
        led = compute_ledger([LedgerService("s", ("A", "B"), "NOPE", 1)], [], pr.demands, pr.fleet,
                             DM, plb, **kw)
        assert any(v["type"] == "unknown_vessel_class" for v in led.violations)
        led = compute_ledger([LedgerService("s", ("A", "B"), "X", 1)], [], pr.demands, pr.fleet,
                             DM, plb, **kw)
        assert any(v["type"] == "fleet_exceeded" for v in led.violations)

    def test_ledger_flags_too_many_departures_of_a_screened_class(self):
        pr = problem()
        kw = dict(port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
                  bunker_price_usd_per_t=600.0)
        led = compute_ledger([LedgerService("s", ("A", "B"), "W", 5)], [], pr.demands, pr.fleet, DM,
                             {p.id: p for p in pr.ports}, **kw)
        assert any(v["type"] == "fleet_exceeded" and v["class"] == "W" for v in led.violations)


# =========================================================================== config
class TestConfiguration:
    def test_environment(self):
        assert config_from_environment({}).k == 1                    # default: best class
        assert config_from_environment({ENV_SCREEN: "0"}).enabled is False   # legacy
        assert config_from_environment({ENV_SCREEN: "2"}).k == 2
        with pytest.raises(ValueError):
            config_from_environment({ENV_SCREEN: "-1"})
        with pytest.raises(ValueError):
            config_from_environment({ENV_SCREEN: "two"})

    def test_diagnostic_enumeration_offers_every_feasible_class_and_only_those(self):
        cfg = config_from_environment({ENV_SCREEN: "all"})
        assert cfg.economic_screen is False and cfg.k >= 3
        pr = problem()
        s = ClassScreener(pr, pr.fleet, assumptions_for_problem(pr), cfg)
        res = s.screen(["A", "B"], 1000.0)
        assert [e.vessel_class for e in res.selected] == ["V", "W"]      # X has no vessels
        assert all(e.selected_because.startswith("diagnostic_enumeration") for e in res.selected)

    def test_invalid_config_is_rejected(self):
        with pytest.raises(ValueError):
            ClassScreeningConfig(k=-1)
        with pytest.raises(ValueError):
            ClassScreeningConfig(k=1, max_frequency=0)


# ================================================ 11  WorldSmall: six registered classes
class TestWorldSmallClasses:
    @pytest.fixture(scope="class")
    def ws(self):
        from src.data.network_loader import NetworkLoader
        root = Path(__file__).resolve().parents[1] / "data" / "raw" / "WorldSmall"
        L = NetworkLoader()
        ports = L.load_ports(root / "ports.csv")
        dem = L.load_demands(root / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = L.load_distance_matrix(root / "dist_dense.csv")
        fl = L.load_fleet(root / "fleet_WorldSmall.csv", root / "fleet_data.csv")
        for p in ports:
            dist.setdefault(p.id, {})
        return Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fl)

    def test_all_six_registered_classes_are_evaluated_but_few_are_offered(self, ws):
        s = ClassScreener(ws, ws.fleet, assumptions_for_problem(ws), ClassScreeningConfig(k=2))
        names = {c.vessel_class for c in ws.fleet.classes}
        assert len(names) == 6
        for route in (["CNSHA", "NLRTM"], ["SGSIN", "AEJEA", "EGPSD"], ["MYPKG", "MYTPP"]):
            res = s.screen(route, 4000.0)
            assert {e.vessel_class for e in res.evaluations} == names
            assert 1 <= len(res.selected) <= 2
            inv = {c.vessel_class: c.quantity for c in ws.fleet.classes}
            for e in res.selected:
                assert e.feasible and e.vessels_f1 <= inv[e.vessel_class]

    def test_a_short_feeder_leg_can_use_a_class_the_legacy_rule_never_offers(self, ws):
        s = ClassScreener(ws, ws.fleet, assumptions_for_problem(ws), ClassScreeningConfig(k=6))
        res = s.screen(["MYPKG", "MYTPP"], 1000.0)
        feasible = {e.vessel_class for e in res.evaluations if e.feasible}
        assert {"Feeder_450", "Panamax_1200"} <= feasible        # feasible, merely never "nearest"


# ===================================== integration with the production generator / filter
class TestGeneratorAndRegionalFilterIntegration:
    @pytest.fixture(scope="class")
    def ws(self):
        from src.data.network_loader import NetworkLoader
        root = Path(__file__).resolve().parents[1] / "data" / "raw" / "WorldSmall"
        L = NetworkLoader()
        ports = L.load_ports(root / "ports.csv")
        dem = L.load_demands(root / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = L.load_distance_matrix(root / "dist_dense.csv")
        fl = L.load_fleet(root / "fleet_WorldSmall.csv", root / "fleet_data.csv")
        for p in ports:
            dist.setdefault(p.id, {})
        return ports, dem, dist, fl

    def _generate(self, ws, screen, loops=0, seed=11):
        import os
        import random
        from src.agents.service_generator_agent import ServiceGeneratorAgent
        ports, dem, dist, fl = ws
        pr = Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fl)
        saved = {k: os.environ.get(k) for k in (ENV_SCREEN, "LINER_DEMAND_LOOP_BUDGET")}
        try:
            if screen is None:
                os.environ.pop(ENV_SCREEN, None)
            else:
                os.environ[ENV_SCREEN] = str(screen)
            os.environ["LINER_DEMAND_LOOP_BUDGET"] = str(loops)
            random.seed(seed)
            agent = ServiceGeneratorAgent(name="t", model="none")
            services = agent.generate_services(pr, archetype_params=None)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return agent, services, pr

    def test_zero_is_the_legacy_pool_exactly_and_unset_is_the_default(self, ws):
        _, legacy_a, _ = self._generate(ws, 0)
        _, legacy_b, _ = self._generate(ws, 0)
        assert [(tuple(s.ports), s.vessel_class) for s in legacy_a] ==                [(tuple(s.ports), s.vessel_class) for s in legacy_b]
        assert not any(getattr(s, "economically_screened", False) for s in legacy_a)
        _, unset, _ = self._generate(ws, None)
        _, one, _ = self._generate(ws, 1)
        assert [(tuple(s.ports), s.vessel_class) for s in unset] ==                [(tuple(s.ports), s.vessel_class) for s in one]

    def test_alternatives_per_rotation_never_exceed_k(self, ws):
        from src.network.reconcile import canonical_rotation
        for k in (1, 2):
            _, services, _ = self._generate(ws, k)
            classes = {}
            for s in services:
                classes.setdefault(canonical_rotation(s.ports), set()).add(s.vessel_class)
            assert max(len(v) for v in classes.values()) <= k

    def test_no_rotation_class_pair_is_offered_twice_when_screening(self, ws):
        from src.network.reconcile import canonical_rotation
        agent, services, _ = self._generate(ws, 2)
        keys = [(canonical_rotation(s.ports), s.vessel_class) for s in services]
        assert len(keys) == len(set(keys))
        assert agent.last_candidate_report.duplicate_rotation_class >= 0

    def test_every_offered_class_is_feasible_and_registered(self, ws):
        _, services, pr = self._generate(ws, 2)
        for s in services:
            cls = pr.fleet.get_class(s.vessel_class)
            assert cls is not None and cls.quantity > 0
            assert s.required_vessels <= cls.quantity

    def test_screened_services_have_positive_standalone_economics(self, ws):
        agent, services, pr = self._generate(ws, 1)
        sc = ClassScreener(pr, pr.fleet, assumptions_for_problem(pr), ClassScreeningConfig(k=1))
        flagged = [s for s in services if getattr(s, "economically_screened", False)]
        assert flagged, "some rotations have a profitable class on WorldSmall"
        for s in flagged[:40]:
            ev = {e.vessel_class: e for e in sc.screen(s.ports, s.capacity).evaluations}[s.vessel_class]
            assert ev.feasible and ev.promising and ev.standalone_profit_best > 0

    def test_report_is_attached_to_the_agent(self, ws):
        agent, _, _ = self._generate(ws, 2)
        r = agent.last_class_screening_report
        assert r is not None and r.rotations_screened > 0
        assert r.alternatives_emitted >= r.rotations_screened - r.rotations_without_feasible_class

    def test_the_regional_filter_is_not_bypassed_by_screening(self, ws, monkeypatch):
        """Measured decision (ablation ``+noexempt``): screened classes face the same
        regional margin test and cap as every legacy candidate. The test removes
        Feeder_450 whatever its economics; only demand-coherent loops are exempt.

        This pins the LEGACY filter (``LINER_REGIONAL_FILTER=legacy``): Task 16 adds an
        economic filter, selected by default while the Task 9/10 generators are on, which
        does not apply the class-level margin guess (see ``tests/test_regional_filter.py``).
        The assertion below is unchanged."""
        monkeypatch.setenv("LINER_REGIONAL_FILTER", "legacy")
        from src.agents.regional_agent import RegionalAgent
        from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals
        from src.optimization.data import Service
        ports, dem, dist, fl = ws
        f450 = fl.get_class("Feeder_450")
        # The legacy margin guess is ``capacity x 0.5 x 150 > weekly_cost``.  The weekly cost
        # of one Feeder_450 (35,000) used to exceed 450 x 75; with the capacity in TEU
        # (900 since Issue 1) it no longer does, so the fixture states the intended premise
        # explicitly: a service whose weekly cost is just above the guess, which the
        # legacy filter must remove whatever its class or provenance.
        base = dict(ports=["MYPKG", "MYTPP"], capacity=f450.capacity_teu,
                    weekly_cost=f450.capacity_teu * 0.5 * 150 + 1.0, vessel_class="Feeder_450")
        a = Service(id="legacy_f450", **base)
        b = Service(id="screened_f450", **base)
        b.economically_screened = True
        c = Service(id="loop_f450", **base)
        c.origin_section = "demand_loop"
        pr = Problem(ports=ports, services=[a, b, c], demands=dem, distance_matrix=dist, fleet=fl)
        agent = RegionalAgent("regional_t", "Asia", "none")
        budget = AdaptiveBudget.from_signals(
            compute_complexity_signals(num_ports=len(pr.ports), demands=pr.demands, fleet=fl))
        kept = {s_.id for s_ in agent._filter_services(pr, budget).services}
        assert kept == {"loop_f450"}
