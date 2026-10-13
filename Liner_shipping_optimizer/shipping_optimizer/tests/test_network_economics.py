"""
Canonical network economics: service model, OD paths, network MILP, ledger.

All fixtures here are SYNTHETIC (clearly labelled) with hand-computed expected values:

    vessel V : 1,000 TEU, design 12 kn (range 10-14), TC 8,000 USD/day,
               bunker 20 t/day at design speed, idle 2 t/day, 5 vessels
    price    : 600 USD/t ; port stay 24 h ; transshipment 48 h ; connection wait 3.5 d
    ports    : fixed call cost 1,000 USD each

    A->B 1,000 nm, B->A 1,200 nm   ->  sailing 2,200/(12*24) = 7.6389 d,
    2 calls = 2 d,  T = 9.6389 d -> declared 10 d, 3 vessels for f=2 (ceil(20/7)).
    fuel / rotation = (7.6389*20 + 2*2) * 600 = 94,066.67
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.economics import (
    DEFAULT_ASSUMPTIONS, EconomicsAssumptions, ServiceModelError, build_service_model,
    estimate_best_frequency,
)
from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
from src.network.paths import build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem


# --------------------------------------------------------------------------- fixtures
def vessel(name="V", qty=5, cap=1000.0, tc=8000.0, lo=10.0, design=12.0, hi=14.0,
           bunker=20.0, idle=2.0):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc,
                      min_speed=lo, design_speed=design, max_speed=hi,
                      bunker_consumption_tons_per_day=bunker, idle_consumption_tons_per_day=idle)


def ports(**over):
    base = dict(handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                variable_port_call_cost=0.0)
    out = {}
    for pid in "ABC":
        kw = dict(base)
        kw.update(over.get(pid, {}))
        out[pid] = Port(pid, pid, 0.0, 0.0, **kw)
    return out


DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0}, "C": {"A": 1600.0, "B": 600.0}}


def problem(demands, *, fleet=None, port_over=None, dm=None):
    pl = ports(**(port_over or {}))
    return Problem(ports=list(pl.values()), services=[], demands=demands,
                   distance_matrix=dm or DM, fleet=fleet or Fleet(classes=[vessel()]))


def planner(prob, **kw):
    return NetworkPlanner(prob, **kw)


SAIL_AB = 2200.0 / (12.0 * 24.0)                 # 7.63889 d for the A<->B rotation
FUEL_AB = (SAIL_AB * 20.0 + 2.0 * 2.0) * 600.0   # 94,066.67 per rotation


# ===================================================================== A. service model
class TestServiceModel:
    def test_exact_values(self):
        pr = problem([])
        m = build_service_model("s", ["A", "B"], pr.fleet.get_class("V"), DM,
                                {p.id: p for p in pr.ports})
        assert m.legs == (("A", "B", 1000.0), ("B", "A", 1200.0))        # closing leg once
        assert m.sea_days == pytest.approx(SAIL_AB)
        assert m.port_days == pytest.approx(2.0)
        assert m.cycle_time_days == 10
        assert m.fuel_cost_per_rotation == pytest.approx(FUEL_AB)
        assert m.port_fixed_per_rotation == 2000.0
        assert m.vessel_week_cost == 56000.0
        assert [m.vessels(f) for f in (0, 1, 2, 3)] == [0, 2, 3, 5]
        assert m.weekly_fixed_cost(2) == pytest.approx(3 * 56000 + 2 * (FUEL_AB + 2000))
        assert m.weekly_leg_capacity(2) == 2000.0

    def test_frequency_limit_comes_from_real_time_and_inventory(self):
        pr = problem([])
        m = build_service_model("s", ["A", "B"], pr.fleet.get_class("V"), DM, {p.id: p for p in pr.ports})
        assert m.max_departures() == 3                  # floor(7*5/10); f=3 needs ceil(30/7)=5
        assert m.vessels(3) == 5 and m.vessels(4) == 6  # the 4th departure is not sustainable
        assert m.max_departures(vessel_budget=2) == 1   # floor(7*2/10)
        assert m.max_departures(vessel_budget=0) == 0

    def test_ride_wraps_over_the_closing_leg(self):
        pr = problem([])
        m = build_service_model("s", ["A", "B", "C"], pr.fleet.get_class("V"), DM, {p.id: p for p in pr.ports})
        legs, days = m.ride("A", "C")                   # A->B->C, B intermediate (1 stay)
        assert legs == (0, 1)
        assert days == pytest.approx((1000 + 600) / 288.0 + 1.0)
        legs, days = m.ride("C", "B")                   # C->A (closing leg), A intermediate, A->B
        assert legs == (2, 0)
        assert days == pytest.approx((1600 + 1000) / 288.0 + 1.0)
        assert m.ride("A", "A") is None and m.ride("A", "Z") is None

    @pytest.mark.parametrize("kw, reason", [
        (dict(design=0.0), "invalid_vessel_speed"),
        (dict(bunker=float("nan")), "missing_fleet_parameter"),
    ])
    def test_missing_or_invalid_fleet_input_is_an_error_not_a_default(self, kw, reason):
        pr = problem([])
        with pytest.raises(ServiceModelError) as e:
            build_service_model("s", ["A", "B"], vessel(**kw), DM, {p.id: p for p in pr.ports})
        assert reason in e.value.reasons

    def test_missing_distance_is_an_error(self):
        pr = problem([])
        with pytest.raises(ServiceModelError) as e:
            build_service_model("s", ["A", "B"], pr.fleet.get_class("V"), {"A": {"B": 1.0}},
                                {p.id: p for p in pr.ports})
        assert "missing_directed_distance" in e.value.reasons

    def test_unprofitable_service_has_best_frequency_zero(self):
        pr = problem([])
        m = build_service_model("s", ["A", "B"], pr.fleet.get_class("V"), DM, {p.id: p for p in pr.ports})
        assert estimate_best_frequency(m, 100.0, 1.0)[0] == 0
        f, margin = estimate_best_frequency(m, 1500.0, 1000.0)
        assert f == 2 and margin == pytest.approx(1_500_000 - m.weekly_fixed_cost(2))


# ======================================================================== B. paths
class TestPaths:
    def _models(self, pr, routes):
        pl = {p.id: p for p in pr.ports}
        return [build_service_model(f"s{i}", r, pr.fleet.get_class("V"), DM, pl)
                for i, r in enumerate(routes)], pl

    def test_transfer_transit_time_includes_port_stays_and_connection_dwell(self):
        d = [Demand("A", "C", 100.0, 1000.0, max_transit_days=20.0)]
        pr = problem(d)
        models, pl = self._models(pr, [["A", "B"], ["B", "C"]])
        paths, stats = build_paths(d, models, pl)
        assert stats.od_transfer_only == 1 and stats.od_with_direct == 0
        p = paths[0][0]
        assert p.kind == "transfer" and p.hub == "B"
        # ride A->B (1000 nm) + 2 d min transshipment + 3.5 d wait + ride B->C (600 nm)
        assert p.transit_days == pytest.approx(1000 / 288.0 + 2.0 + 3.5 + 600 / 288.0)

    def test_time_limit_is_enforced_when_paths_are_built(self):
        need = 1000 / 288.0 + 5.5 + 600 / 288.0                 # 11.056 d
        for limit, expect in ((need - 0.01, 0), (need + 0.01, 1)):
            d = [Demand("A", "C", 100.0, 1000.0, max_transit_days=limit)]
            pr = problem(d)
            models, pl = self._models(pr, [["A", "B"], ["B", "C"]])
            paths, stats = build_paths(d, models, pl)
            assert len(paths.get(0, [])) == expect
            if expect == 0:
                assert stats.od_without_path_time_limit == 1

    def test_no_limit_in_the_source_means_unconstrained(self):
        d = [Demand("A", "C", 100.0, 1000.0, max_transit_days=None)]
        pr = problem(d)
        models, pl = self._models(pr, [["A", "B"], ["B", "C"]])
        assert len(build_paths(d, models, pl)[0][0]) == 1

    def test_per_teu_port_charges_per_path(self):
        d = [Demand("A", "C", 100.0, 1000.0)]
        pr = problem(d, port_over={"A": dict(handling_cost=10, variable_port_call_cost=1),
                                   "C": dict(handling_cost=20, variable_port_call_cost=2),
                                   "B": dict(transshipment_cost=40, variable_port_call_cost=3)})
        models, pl = self._models(pr, [["A", "B"], ["B", "C"]])
        p = build_paths(d, models, pl)[0][0][0]
        assert p.port_cost_per_teu == pytest.approx(10 + 20 + 40)      # per-FFE call charge is per rotation


# ================================================================ C. MILP + ledger
class TestPlanner:
    def _plan(self, demands, routes, fleet=None, port_over=None, **kw):
        pr = problem(demands, fleet=fleet, port_over=port_over)
        pl = planner(pr)
        cands = [Candidate(f"s{i}", tuple(r), "V") for i, r in enumerate(routes)]
        return pr, pl.plan(cands, time_limit_sec=30, **kw)

    def test_single_service_exact_optimum(self):
        d = [Demand("A", "B", 1500.0, 1000.0)]
        pr, res = self._plan(d, [["A", "B"]], port_over={"A": dict(handling_cost=10),
                                                         "B": dict(handling_cost=20)})
        assert res.ok and res.status == "optimal"
        assert res.frequencies == {"s0": 2}
        led = res.ledger
        assert led.vessels_by_service == {"s0": 3}                  # ceil(10*2/7)
        assert led.revenue == pytest.approx(1_500_000.0)
        assert led.vessel_cost == pytest.approx(168_000.0)
        assert led.fuel_cost == pytest.approx(2 * FUEL_AB)
        assert led.port_call_fixed_cost == pytest.approx(2 * 2000.0)
        assert led.handling_cost == pytest.approx(1500 * 30.0)
        assert led.operating_profit == pytest.approx(1_500_000 - 168_000 - 2 * FUEL_AB - 4000 - 45_000)
        assert led.served_teu == pytest.approx(1500.0) and led.unserved_teu == pytest.approx(0.0)
        assert res.reconciliation["reconciled"], res.reconciliation

    def test_profit_equals_revenue_minus_each_cost_line(self):
        d = [Demand("A", "B", 1500.0, 1000.0)]
        _, res = self._plan(d, [["A", "B"]])
        led = res.ledger
        assert led.operating_cost == pytest.approx(
            led.vessel_cost + led.fuel_cost + led.port_call_fixed_cost + led.handling_cost
            + led.transshipment_cost + led.port_variable_cost)
        assert led.operating_profit == pytest.approx(led.revenue - led.operating_cost)

    def test_class_inventory_limits_frequency(self):
        d = [Demand("A", "B", 1500.0, 1000.0)]
        pr = problem(d, fleet=Fleet(classes=[vessel(qty=2)]))
        res = planner(pr).plan([Candidate("s0", ("A", "B"), "V")], time_limit_sec=30)
        assert res.frequencies == {"s0": 1}                         # f=2 would need 3 vessels
        assert res.ledger.vessels_by_class == {"V": 2}
        assert res.ledger.served_teu == pytest.approx(1000.0)
        assert res.ledger.unserved_teu == pytest.approx(500.0)
        assert res.ledger.valid

    def test_unprofitable_demand_is_left_unserved_not_forced(self):
        d = [Demand("A", "B", 10.0, 5.0)]                           # 50 USD of revenue
        _, res = self._plan(d, [["A", "B"]])
        assert res.status == "optimal" and res.frequencies == {}
        assert res.ledger.operating_profit == 0.0 and res.ledger.coverage == 0.0

    def test_transit_time_limit_makes_demand_unserved(self):
        d = [Demand("A", "B", 1500.0, 1000.0, max_transit_days=3.0)]    # direct sail is 3.47 d
        _, res = self._plan(d, [["A", "B"]])
        assert res.frequencies == {} and res.ledger.unserved_teu == pytest.approx(1500.0)
        assert res.path_stats.od_without_path_time_limit == 1

    def test_leg_capacity_is_per_leg_not_per_service(self):
        """f fixed to 1 (1,000 TEU per leg). Legs: AB carries AB+AC, BC carries BC+AC.
        Optimum is AC=400, AB=BC=600 -> 1,600 TEU, not the 1,800 an aggregate cap allows."""
        d = [Demand("A", "B", 600.0, 1000.0), Demand("B", "C", 600.0, 1000.0),
             Demand("A", "C", 600.0, 1000.0)]
        pr = problem(d)
        res = planner(pr).plan([Candidate("r", ("A", "B", "C"), "V")],
                               fixed_frequencies={"r": 1}, time_limit_sec=30)
        assert res.ok
        assert res.ledger.served_teu == pytest.approx(1600.0, abs=1e-4)
        loads = {}
        for di, k, teu in res.solution.flows:
            for seg in res.paths[di][k].segments:
                for leg in seg.legs:
                    loads[leg] = loads.get(leg, 0.0) + teu
        assert max(loads.values()) <= 1000.0 + 1e-6

    def test_transfer_cargo_is_counted_once_in_revenue(self):
        d = [Demand("A", "C", 400.0, 1000.0, max_transit_days=30.0)]
        pr, res = self._plan(d, [["A", "B"], ["B", "C"]],
                             port_over={"B": dict(transshipment_cost=40.0)})
        assert res.ok and len(res.frequencies) == 2
        assert res.ledger.revenue == pytest.approx(400_000.0)       # once, not once per service
        assert res.ledger.transshipment_cost == pytest.approx(400 * 40.0)
        assert res.reconciliation["reconciled"], res.reconciliation

    def test_optimiser_penalty_is_reported_separately_never_as_profit(self):
        d = [Demand("A", "B", 10.0, 5.0)]
        pr = problem(d)
        res = planner(pr).plan([Candidate("s0", ("A", "B"), "V")],
                               unserved_penalty_per_teu=100.0, time_limit_sec=30)
        # the penalty makes serving attractive; the ledger still shows only accounting profit
        assert res.solution.objective_components["unserved_penalty"] >= 0.0
        led = res.ledger
        assert led.operating_profit == pytest.approx(led.revenue - led.operating_cost)
        assert res.reconciliation["reconciled"], res.reconciliation

    def test_rejected_candidates_carry_reasons(self):
        d = [Demand("A", "B", 100.0, 1000.0)]
        pr = problem(d)
        res = planner(pr).plan([Candidate("bad", ("A", "Z"), "V"),
                                Candidate("cls", ("A", "B"), "Nope"),
                                Candidate("ok", ("A", "B"), "V")], time_limit_sec=30)
        reasons = {r["service"]: r["reasons"] for r in res.rejected_candidates}
        assert "unknown_port" in reasons["bad"] and "unknown_vessel_class" in reasons["cls"]
        assert [m.service_id for m in res.models] == ["ok"]


class TestLedgerCatchesInvalidPlans:
    """The ledger must flag a bad plan on its own (it does not trust the optimiser)."""

    def _ledger(self, services, flows, demands, **kw):
        pr = problem(demands, **kw)
        a = DEFAULT_ASSUMPTIONS
        return compute_ledger(services, flows, demands, pr.fleet, pr.distance_matrix,
                              {p.id: p for p in pr.ports}, port_stay_hours=a.port_stay_hours,
                              transshipment_min_hours=a.transshipment_min_hours,
                              transfer_wait_days=a.transfer_wait_days,
                              bunker_price_usd_per_t=a.bunker_price_usd_per_t)

    def _types(self, led):
        return {v["type"] for v in led.violations}

    def test_leg_capacity_exceeded(self):
        d = [Demand("A", "B", 1500.0, 1000.0)]
        led = self._ledger([LedgerService("s", ("A", "B"), "V", 1)],
                           [LedgerFlow(0, (("s", "A", "B"),), 1500.0)], d)
        assert "leg_capacity_exceeded" in self._types(led)
        v = next(v for v in led.violations if v["type"] == "leg_capacity_exceeded")
        assert v["service"] == "s" and v["leg"] == ("A", "B") and v["excess"] == pytest.approx(500.0)

    def test_fleet_exceeded(self):
        d = [Demand("A", "B", 100.0, 1000.0)]
        led = self._ledger([LedgerService("s", ("A", "B"), "V", 4)], [], d)   # needs ceil(40/7)=6 > 5
        assert "fleet_exceeded" in self._types(led)
        assert led.vessels_by_class == {"V": 6}

    def test_overserved_and_transit_and_inactive_service(self):
        d = [Demand("A", "B", 100.0, 1000.0, max_transit_days=3.0)]
        led = self._ledger([LedgerService("s", ("A", "B"), "V", 1)],
                           [LedgerFlow(0, (("s", "A", "B"),), 100.0),
                            LedgerFlow(0, (("s", "A", "B"),), 100.0),
                            LedgerFlow(0, (("ghost", "A", "B"),), 1.0)], d)
        t = self._types(led)
        assert {"demand_overserved", "transit_time_exceeded", "flow_on_inactive_service"} <= t

    def test_invalid_path_and_frequency_and_class(self):
        d = [Demand("A", "B", 100.0, 1000.0)]
        led = self._ledger([LedgerService("s", ("A", "B"), "V", 1),
                            LedgerService("t", ("A", "B"), "Nope", 1),
                            LedgerService("u", ("A", "B"), "V", -1)],
                           [LedgerFlow(0, (("s", "B", "A"),), 10.0)], d)
        assert {"unknown_vessel_class", "invalid_frequency", "invalid_path"} <= self._types(led)

    def test_valid_plan_has_no_violations(self):
        d = [Demand("A", "B", 100.0, 1000.0)]
        led = self._ledger([LedgerService("s", ("A", "B"), "V", 1)],
                           [LedgerFlow(0, (("s", "A", "B"),), 100.0)], d)
        assert led.valid and led.served_teu == 100.0
        assert led.revenue == 100_000.0
