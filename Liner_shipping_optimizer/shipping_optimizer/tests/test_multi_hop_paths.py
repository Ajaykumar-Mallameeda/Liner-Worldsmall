"""
Tasks 19-21 network layer: bounded two-transfer journeys, cost-aware path selection, adaptive
per-OD path budgets, the ledger's multi-transfer accounting and the strategy report.

All fixtures are SYNTHETIC (clearly labelled) with hand-computed expected values:

    vessel V : 1,000 TEU, design 12 kn, TC 8,000 USD/day, 10 vessels (288 nm/day)
    ports    : A, B, C, D;  A-B 1,000 nm, B-C 600 nm, C-D 800 nm (both directions as listed)
    dwell    : 48 h transshipment + 3.5 d wait = 5.5 d per transfer
    A->B->C->D by three services : 1000/288 + 600/288 + 800/288 + 2 * 5.5 = 19.3333 d
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.economics import DEFAULT_ASSUMPTIONS, build_service_model
from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
from src.network.paths import (
    HARD_MAX_TRANSFERS, BUDGET_ADAPTIVE, OdPath, PathConfig, PathSegment, _allocate_budget,
    _select_cost_aware, build_paths, config_from_environment,
)
from src.network.plan import Candidate, NetworkPlanner
from src.network.strategy_report import build_strategy_report, classify_flow
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

# ------------------------------------------------------------------------------- fixtures
DM = {
    "A": {"B": 1000.0, "C": 1600.0, "D": 2400.0},
    "B": {"A": 1000.0, "C": 600.0, "D": 1400.0},
    "C": {"A": 1600.0, "B": 600.0, "D": 800.0},
    "D": {"A": 2400.0, "B": 1400.0, "C": 800.0},
}
DWELL = 2.0 + 3.5


def vessel(name="V", qty=10, cap=1000.0, tc=8000.0, design=12.0, bunker=20.0):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc,
                      min_speed=design - 2.0, design_speed=design, max_speed=design + 2.0,
                      bunker_consumption_tons_per_day=bunker, idle_consumption_tons_per_day=2.0)


def port_records(**over):
    out = {}
    for pid in "ABCD":
        kw = dict(handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0)
        kw.update(over.get(pid, {}))
        out[pid] = Port(pid, pid, 0.0, 0.0, **kw)
    return out


def problem(demands, *, fleet=None, port_over=None):
    pl = port_records(**(port_over or {}))
    return Problem(ports=list(pl.values()), services=[], demands=demands, distance_matrix=DM,
                   fleet=fleet or Fleet(classes=[vessel()]))


def models_for(pr, routes, cls="V"):
    pl = {p.id: p for p in pr.ports}
    return [build_service_model(f"s{i}", r, pr.fleet.get_class(cls), DM, pl)
            for i, r in enumerate(routes)], pl


TWO = PathConfig(max_transfers=2)
#: the frozen Tasks 14-16 behaviour: fastest ten paths, one transfer, no re-routing / repair
BASELINE = PathConfig(selection="fastest", max_transfers=1, budget="fixed",
                      reoptimize_flows=False, repair_profit_floor=False)
CHAIN = [["A", "B"], ["B", "C"], ["C", "D"]]            # A->D needs two transfers


# ============================================================================== A. config
class TestConfig:
    def test_defaults_of_the_accepted_configuration(self):
        c = config_from_environment({})
        assert (c.selection, c.max_transfers, c.budget) == ("fastest", 2, "fixed")
        assert c.reoptimize_flows is True and c.repair_profit_floor is True

    def test_documented_rollback_is_the_baseline(self):
        env = {"LINER_MAX_TRANSFERS": "1", "LINER_FLOW_REOPT": "0", "LINER_PROFIT_FLOOR_REPAIR": "0",
               "LINER_PATH_SELECTION": "fastest", "LINER_PATH_BUDGET": "fixed"}
        c = config_from_environment(env)
        assert c == BASELINE

    def test_environment_values(self):
        c = config_from_environment({"LINER_PATH_SELECTION": "cost_aware", "LINER_MAX_TRANSFERS": "2",
                                     "LINER_PATH_BUDGET": "adaptive"})
        assert (c.selection, c.max_transfers, c.budget) == ("cost_aware", 2, BUDGET_ADAPTIVE)

    @pytest.mark.parametrize("env", [
        {"LINER_MAX_TRANSFERS": "3"},            # unrestricted path length is not supported
        {"LINER_MAX_TRANSFERS": "-1"},
        {"LINER_MAX_TRANSFERS": "two"},
        {"LINER_PATH_SELECTION": "random"},
        {"LINER_PATH_BUDGET": "huge"},
    ])
    def test_malformed_values_are_errors_never_replaced(self, env):
        with pytest.raises(ValueError):
            config_from_environment(env)

    def test_the_hard_bound_is_two_transfers(self):
        assert HARD_MAX_TRANSFERS == 2
        with pytest.raises(ValueError):
            PathConfig(max_transfers=HARD_MAX_TRANSFERS + 1)


# ====================================================================== B. two transfers
class TestTwoTransfers:
    def test_not_built_under_the_baseline_configuration(self):
        d = [Demand("A", "D", 100.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, CHAIN)
        paths, st = build_paths(d, models, pl, config=BASELINE)
        assert paths == {} and st.od_without_path == 1 and st.od_without_path_no_connection == 1

    def test_built_with_the_exact_transit_time_and_charges(self):
        d = [Demand("A", "D", 100.0, 3000.0, max_transit_days=25.0)]
        pr = problem(d, port_over={"A": dict(handling_cost=10, variable_port_call_cost=1),
                                   "D": dict(handling_cost=20, variable_port_call_cost=2),
                                   "B": dict(transshipment_cost=40, variable_port_call_cost=3),
                                   "C": dict(transshipment_cost=50, variable_port_call_cost=4)})
        models, pl = models_for(pr, CHAIN)
        paths, st = build_paths(d, models, pl, config=TWO)
        (p,) = paths[0]
        assert p.kind == "transfer2" and p.hubs == ("B", "C") and p.n_transfers == 2
        assert p.services == (0, 1, 2)
        assert [(s.from_port, s.to_port) for s in p.segments] == [("A", "B"), ("B", "C"), ("C", "D")]
        assert p.transit_days == pytest.approx((1000 + 600 + 800) / 288.0 + 2 * DWELL)
        # per-TEU charges: handling at origin and destination + transshipment at each hub (the per-FFE port-call
        # charge is a per-rotation capacity charge in the service model, not a cargo charge)
        assert p.port_cost_per_teu == pytest.approx(10 + 20 + 40 + 50)
        assert st.od_rescued_by_multi_hop == 1 and st.paths_multi_hop_kept == 1

    def test_time_limit_is_enforced(self):
        need = (1000 + 600 + 800) / 288.0 + 2 * DWELL
        for limit, expect in ((need - 0.01, 0), (need + 0.01, 1)):
            d = [Demand("A", "D", 100.0, 3000.0, max_transit_days=limit)]
            pr = problem(d)
            models, pl = models_for(pr, CHAIN)
            paths, st = build_paths(d, models, pl, config=TWO)
            assert len(paths.get(0, [])) == expect
            if expect == 0:
                assert st.od_without_path_time_limit == 1

    def test_only_enumerated_where_the_shorter_journeys_are_too_few(self):
        d = [Demand("A", "C", 100.0, 3000.0)]              # a one-transfer journey exists
        pr = problem(d)
        models, pl = models_for(pr, CHAIN)
        paths, st = build_paths(d, models, pl, config=TWO)
        assert st.od_multi_hop_enumerated == 0 and paths[0][0].kind == "transfer"
        # "all ODs" policy enumerates it: a two-transfer journey A-B-?-C needs a third service
        models, pl = models_for(pr, CHAIN + [["B", "C"]])
        _, st = build_paths(d, models, pl, config=PathConfig(max_transfers=2,
                                                             multi_hop_min_alternatives=100))
        assert st.od_multi_hop_enumerated == 1

    def test_never_more_than_two_transfers(self):
        d = [Demand("A", "D", 100.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, [["A", "B"], ["B", "C"], ["C", "D"], ["B", "D"]])
        paths, _ = build_paths(d, models, pl, config=PathConfig(max_transfers=2,
                                                                multi_hop_min_alternatives=100))
        assert max(p.n_transfers for p in paths[0]) <= 2

    def test_a_journey_never_revisits_a_port_or_a_service(self):
        d = [Demand("A", "D", 100.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, [["A", "B", "C"], ["B", "C"], ["C", "D"]])
        paths, _ = build_paths(d, models, pl, config=PathConfig(max_transfers=2,
                                                                multi_hop_min_alternatives=100))
        for p in paths[0]:
            stops = [p.segments[0].from_port] + [s.to_port for s in p.segments]
            assert len(set(stops)) == len(stops)
            assert len(set(p.services)) == len(p.services)


# ================================================================================ C. ledger
class TestLedger:
    FLEET = Fleet(classes=[vessel()])

    def _ledger(self, flows, *, max_transfers, port_over=None):
        pl = port_records(**(port_over or {}))
        svcs = [LedgerService(f"s{i}", tuple(r), "V", 1) for i, r in enumerate(CHAIN)]
        d = [Demand("A", "D", 100.0, 3000.0, max_transit_days=25.0)]
        return compute_ledger(
            svcs, flows, d, self.FLEET, DM, pl, port_stay_hours=24.0, transshipment_min_hours=48.0,
            transfer_wait_days=3.5, bunker_price_usd_per_t=600.0, max_transfers=max_transfers)

    FLOW3 = LedgerFlow(0, (("s0", "A", "B"), ("s1", "B", "C"), ("s2", "C", "D")), 100.0)

    def test_three_segments_are_rejected_under_the_one_transfer_rule(self):
        led = self._ledger([self.FLOW3], max_transfers=1)
        assert any(v["type"] == "invalid_path" for v in led.violations)

    def test_two_transfer_accounting(self):
        led = self._ledger([self.FLOW3], max_transfers=2, port_over={
            "A": dict(handling_cost=10, variable_port_call_cost=1),
            "D": dict(handling_cost=20, variable_port_call_cost=2),
            "B": dict(transshipment_cost=40, variable_port_call_cost=3),
            "C": dict(transshipment_cost=50, variable_port_call_cost=4)})
        assert not [v for v in led.violations if v["type"] != "transit_time_exceeded"], led.violations
        assert led.revenue == pytest.approx(100 * 3000.0)
        assert led.handling_cost == pytest.approx(100 * (10 + 20))
        assert led.transshipment_cost == pytest.approx(100 * (40 + 50))          # every hub
        # decision phase: callCostPerFFE is a per-call CAPACITY charge (LINERLIB reference), not a cargo charge
        assert led.port_variable_cost == 0.0
        cap = self.FLEET.classes[0].capacity_teu
        pv = {"A": 1, "D": 2, "B": 3, "C": 4}
        assert led.port_capacity_charge_cost == pytest.approx(
            sum(cap * sum(pv[p] for p in rot) for rot in CHAIN))
        assert led.served_teu == pytest.approx(100.0)

    def test_every_transfer_adds_its_dwell_to_the_transit_time(self):
        need = (1000 + 600 + 800) / 288.0 + 2 * DWELL
        pl = port_records()
        svcs = [LedgerService(f"s{i}", tuple(r), "V", 1) for i, r in enumerate(CHAIN)]
        for limit, tight in ((need - 0.01, True), (need + 0.01, False)):
            d = [Demand("A", "D", 100.0, 3000.0, max_transit_days=limit)]
            led = compute_ledger(svcs, [self.FLOW3], d, self.FLEET, DM, pl, port_stay_hours=24.0,
                                 transshipment_min_hours=48.0, transfer_wait_days=3.5,
                                 bunker_price_usd_per_t=600.0, max_transfers=2)
            assert any(v["type"] == "transit_time_exceeded" for v in led.violations) == tight

    def test_broken_or_repeating_journeys_are_violations(self):
        broken = LedgerFlow(0, (("s0", "A", "B"), ("s2", "C", "D")), 10.0)
        assert any(v["type"] == "invalid_transfer"
                   for v in self._ledger([broken], max_transfers=2).violations)
        four = LedgerFlow(0, (("s0", "A", "B"), ("s1", "B", "C"), ("s2", "C", "D"), ("s0", "D", "A")), 10.0)
        assert any(v["type"] == "invalid_path" for v in self._ledger([four], max_transfers=2).violations)


# ======================================================================= D. planner / MILP
class TestPlanner:
    def _plan(self, config, port_over=None):
        d = [Demand("A", "D", 500.0, 3000.0, max_transit_days=25.0)]
        pr = problem(d, port_over=port_over)
        pl = NetworkPlanner(pr, path_config=config)
        cands = [Candidate(f"s{i}", tuple(r), "V") for i, r in enumerate(CHAIN)]
        return pr, pl, pl.plan(cands, time_limit_sec=30, lp_guided=False)

    def test_baseline_leaves_the_od_unserved(self):
        _, _, res = self._plan(BASELINE)
        assert res.ledger.served_teu == 0.0

    def test_two_transfer_journey_is_planned_and_verified(self):
        _, pl, res = self._plan(TWO, port_over={"B": dict(transshipment_cost=40),
                                                "C": dict(transshipment_cost=50)})
        assert res.ok and res.status == "optimal", res.message
        assert res.ledger.served_teu == pytest.approx(500.0)
        assert res.ledger.transshipment_cost == pytest.approx(500.0 * 90.0)
        assert res.reconciliation["reconciled"], res.reconciliation
        assert not res.ledger.violations
        (di, k, teu), = res.solution.flows
        assert res.paths[di][k].kind == "transfer2" and teu == pytest.approx(500.0)


# ================================================================== E. selection / budgets
class TestSelection:
    def _two_direct(self):
        fleet = Fleet(classes=[vessel("Big", cap=5000.0, tc=10000.0, design=12.0),
                               vessel("Fast", cap=500.0, tc=20000.0, design=20.0)])
        d = [Demand("A", "B", 300.0, 3000.0)]
        pr = problem(d, fleet=fleet)
        pl = {p.id: p for p in pr.ports}
        models = [build_service_model("fast", ["A", "B"], fleet.get_class("Fast"), DM, pl),
                  build_service_model("big", ["A", "B"], fleet.get_class("Big"), DM, pl)]
        return d, models, pl

    def test_cost_aware_prefers_the_cheaper_capacity_fastest_prefers_speed(self):
        d, models, pl = self._two_direct()
        fast, _ = build_paths(d, models, pl, max_paths_per_od=1, config=BASELINE)
        cost, _ = build_paths(d, models, pl, max_paths_per_od=1, config=PathConfig(selection="cost_aware"))
        assert fast[0][0].services == (0,)          # the 20-knot vessel is faster ...
        assert cost[0][0].services == (1,)          # ... the 5,000 TEU vessel is cheaper per TEU
        both, _ = build_paths(d, models, pl, max_paths_per_od=2, config=PathConfig(selection="cost_aware"))
        by_service = {p.services: p.slot_cost_per_teu for p in both[0]}
        assert by_service[(1,)] < by_service[(0,)]
        assert fast[0][0].slot_cost_per_teu is None            # the baseline does not compute it

    def test_baseline_selection_is_direct_first_then_fastest_transfers(self):
        d = [Demand("A", "C", 100.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, [["A", "C"], ["A", "B"], ["B", "C"], ["A", "B", "C"]])
        full, _ = build_paths(d, models, pl, max_paths_per_od=50, config=BASELINE)
        cut, st = build_paths(d, models, pl, max_paths_per_od=2, config=BASELINE)
        assert [p.services for p in cut[0]] == [p.services for p in full[0][:2]]
        kinds = [p.kind for p in full[0]]
        assert kinds == sorted(kinds, key=lambda k: k != "direct")        # directs first
        assert st.paths_dropped_by_cap == len(full[0]) - 2

    @staticmethod
    def _path(services, cost):
        segs = tuple(PathSegment(s, (0,), "A", "B", 1.0) for s in services)
        return OdPath(od=0, kind="direct" if len(services) == 1 else "transfer", segments=segs,
                      hub=None, transit_days=1.0, port_cost_per_teu=cost, hubs=(),
                      slot_cost_per_teu=0.0)

    def test_reuse_penalty_keeps_the_retained_set_from_near_duplicates(self):
        cands = [self._path((0, 1), 10.0), self._path((0, 1), 10.5), self._path((2,), 12.0)]
        no_pen = _select_cost_aware(list(cands), 2, 0.0)
        pen = _select_cost_aware(list(cands), 2, 0.10)
        assert [p.port_cost_per_teu for p in no_pen] == [10.0, 10.5]
        assert [p.port_cost_per_teu for p in pen] == [10.0, 12.0]

    def test_adaptive_budget_keeps_the_model_size_and_the_bounds(self):
        cfg = PathConfig(selection="cost_aware", budget="adaptive",
                         adaptive_min_paths=2, adaptive_max_paths=8)
        rows = [(0, 40, 1_000_000.0), (1, 40, 10_000.0), (2, 40, 100.0), (3, 3, 5.0), (4, 1, 1e9)]
        total = 10 + 10 + 10 + 3 + 1
        k = _allocate_budget(rows, total, cfg)
        assert sum(k.values()) <= total
        assert k[0] >= k[1] >= k[2]
        assert all(2 <= k[od] or n < 2 for od, n, _ in rows)
        assert all(k[od] <= min(8, n) for od, n, _ in rows)
        assert k[4] == 1 and k[3] == 3

    def test_adaptive_and_cost_aware_keep_the_baseline_number_of_paths(self):
        d = [Demand("A", "C", 100.0 * (i + 1), 3000.0) for i in range(3)] + [Demand("A", "B", 50.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, [["A", "C"], ["A", "B"], ["B", "C"], ["A", "B", "C"], ["A", "C", "B"]])
        base, _ = build_paths(d, models, pl, max_paths_per_od=2, config=BASELINE)
        ada, st = build_paths(d, models, pl, max_paths_per_od=2,
                              config=PathConfig(selection="cost_aware", budget="adaptive",
                                                adaptive_min_paths=1, adaptive_max_paths=5))
        assert sum(len(v) for v in ada.values()) <= sum(len(v) for v in base.values())
        assert st.budget == "adaptive"


# ================================================================== F. strategy report
class TestStrategyReport:
    def _result(self):
        d = [Demand("A", "D", 400.0, 3000.0, max_transit_days=25.0),
             Demand("A", "B", 300.0, 2000.0, max_transit_days=25.0),
             Demand("B", "D", 200.0, 90.0, max_transit_days=3.0)]      # time limit unattainable
        pr = problem(d, port_over={"B": dict(transshipment_cost=40), "C": dict(transshipment_cost=50)})
        pl = NetworkPlanner(pr, path_config=TWO)
        cands = [Candidate(f"s{i}", tuple(r), "V") for i, r in enumerate(CHAIN)]
        res = pl.plan(cands, time_limit_sec=30, lp_guided=False)
        return pr, res

    def test_every_flow_is_counted_once_and_reconciles_with_the_ledger(self):
        pr, res = self._result()
        assert res.ok
        rep = build_strategy_report(res, fleet=pr.fleet, distance_matrix=pr.distance_matrix)
        assert rep["available"] and rep["reconciliation"]["all"], rep["reconciliation"]
        assert rep["totals"]["served_teu"] == pytest.approx(res.ledger.served_teu)
        assert sum(b["served_teu"] for b in rep["by_strategy"].values()) == pytest.approx(
            res.ledger.served_teu)
        assert rep["by_strategy"]["multi_hop"]["served_teu"] == pytest.approx(400.0)
        assert rep["by_strategy"]["multi_hop"]["transfers_per_teu"] == pytest.approx(2.0)
        assert rep["by_strategy"]["direct"]["served_teu"] == pytest.approx(300.0)
        assert all(b["transit_violations"] == 0 for b in rep["by_strategy"].values())

    def test_idle_capacity_closes_the_profit_identity(self):
        pr, res = self._result()
        rep = build_strategy_report(res, fleet=pr.fleet, distance_matrix=pr.distance_matrix)
        parts = sum(b["profit_contribution"] for b in rep["by_strategy"].values())
        assert parts - rep["totals"]["idle_capacity_cost"] == pytest.approx(res.ledger.operating_profit)
        assert rep["totals"]["idle_capacity_cost"] >= 0.0

    def test_unserved_demand_names_its_reason(self):
        pr, res = self._result()
        rep = build_strategy_report(res, fleet=pr.fleet, distance_matrix=pr.distance_matrix)
        # B->D must be done in 3 days: 1400 nm at the fastest class speed (12 kn) needs 4.9 d
        assert "limit_below_fastest_sailing_time" in rep["unserved_by_reason"]
        assert rep["unserved_by_reason"]["limit_below_fastest_sailing_time"]["teu"] == pytest.approx(200.0)

    def test_classification_is_structural(self):
        pr, res = self._result()
        models = res.models
        kinds = {classify_flow(res.paths[di][k], models) for di, k, _ in res.solution.flows}
        assert kinds == {"direct", "multi_hop"}


# ============================================================ G. flow re-optimisation (Task 20)
class TestFlowReoptimisation:
    """SYNTHETIC.  s0 = A<->C on the small class (500 TEU, 2 vessels -> f = 1: 500 TEU per leg),
    s1 = A<->B, s2 = B<->C on class V (1,000 TEU).  A->C demands 1,500 TEU; with ONE path per OD
    the direct rotation is the only kept path, so 1,000 TEU stay unserved although s1 and s2,
    operated for the A->B and B->C cargo, have free capacity.  Re-routing over all valid paths
    carries them (one transfer at B)."""

    def _plan(self, reopt):
        d = [Demand("A", "C", 1500.0, 3000.0, max_transit_days=60.0),
             Demand("A", "B", 300.0, 2000.0, max_transit_days=60.0),
             Demand("B", "C", 300.0, 2000.0, max_transit_days=60.0)]
        fleet = Fleet(classes=[vessel("S", qty=2, cap=500.0), vessel("V", qty=10, cap=1000.0)])
        pr = problem(d, fleet=fleet, port_over={"B": dict(transshipment_cost=20)})
        pl = NetworkPlanner(pr, max_paths_per_od=1, path_config=PathConfig(reoptimize_flows=reopt))
        cands = [Candidate("s0", ("A", "C"), "S"), Candidate("s1", ("A", "B"), "V"),
                 Candidate("s2", ("B", "C"), "V")]
        return pl.plan(cands, time_limit_sec=30, lp_guided=False)

    def test_off_keeps_the_capped_plan(self):
        res = self._plan(False)
        assert res.ok and res.flow_reopt["applied"] is False
        assert res.ledger.served_teu == pytest.approx(500.0 + 300.0 + 300.0)

    def test_on_serves_more_with_the_same_network_and_a_verified_ledger(self):
        off, on = self._plan(False), self._plan(True)
        assert on.ok and on.flow_reopt["applied"] is True, on.flow_reopt
        # same services, frequencies and vessels: no fixed cost moved
        assert on.frequencies == off.frequencies
        assert on.ledger.vessel_cost == pytest.approx(off.ledger.vessel_cost)
        assert on.ledger.fuel_cost == pytest.approx(off.ledger.fuel_cost)
        assert on.ledger.port_call_fixed_cost == pytest.approx(off.ledger.port_call_fixed_cost)
        # ... more cargo, higher verified profit
        # the transfer is limited by the free capacity of s1 and s2 (1,000 - 300 = 700 TEU)
        assert on.ledger.served_teu == pytest.approx(off.ledger.served_teu + 700.0)
        assert on.ledger.operating_profit == pytest.approx(
            off.ledger.operating_profit + 700.0 * (3000.0 - 20.0))
        assert not on.ledger.violations
        assert on.reconciliation["reconciled"], on.reconciliation
        assert on.reconciliation["flow_reoptimisation"]["gain_usd"] == pytest.approx(
            on.ledger.operating_profit - off.ledger.operating_profit, rel=1e-6)
        # the transfer flow rides a path that the cap had removed
        kinds = {on.paths[di][k].kind for di, k, _ in on.solution.flows}
        assert "transfer" in kinds

    def test_the_capacity_of_every_leg_still_binds(self):
        on = self._plan(True)
        load = {}
        for di, k, teu in on.solution.flows:
            for seg in on.paths[di][k].segments:
                for leg in seg.legs:
                    load[(seg.service, leg)] = load.get((seg.service, leg), 0.0) + teu
        for (si, leg), v in load.items():
            f = on.solution.frequencies[si]
            assert v <= on.models[si].capacity_teu * f + 1e-6

    def test_never_applied_to_a_fixed_frequency_solve(self):
        d = [Demand("A", "C", 1500.0, 3000.0, max_transit_days=60.0)]
        pr = problem(d, fleet=Fleet(classes=[vessel("S", qty=2, cap=500.0)]))
        pl = NetworkPlanner(pr, max_paths_per_od=1, path_config=PathConfig(reoptimize_flows=True))
        res = pl.plan([Candidate("s0", ("A", "C"), "S")], fixed_frequencies={"s0": 1}, time_limit_sec=30)
        assert res.flow_reopt["applied"] is False


# ============================================================================ H. network signals
class TestSignals:
    def test_signals_describe_the_candidate_network(self):
        d = [Demand("A", "C", 100.0, 3000.0), Demand("A", "D", 300.0, 3000.0),
             Demand("B", "C", 600.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, CHAIN)          # A-B, B-C, C-D
        _paths, st = build_paths(d, models, pl, config=BASELINE)
        s = st.signals
        # A->C: one transfer path (at B); A->D needs two transfers (none built); B->C: direct
        assert s["od_by_valid_paths"]["0"] == 1 and s["od_by_valid_paths"]["1"] == 2
        assert s["demand_share_without_any_path"] == pytest.approx(300.0 / 1000.0)
        assert s["demand_share_with_direct_path"] == pytest.approx(600.0 / 1000.0)
        assert sum(s["demand_share_by_valid_paths"].values()) == pytest.approx(1.0)
        assert s["port_connectivity"]["ports"] == 4
        assert s["port_connectivity"]["services_per_port_max"] == 2        # B and C
        assert s["transfer_concentration"]["distinct_transfer_ports"] == 1
        assert s["demand_concentration"]["top10_od_share"] == pytest.approx(1.0)

    def test_two_transfer_enumeration_removes_the_unreachable_share(self):
        d = [Demand("A", "D", 300.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, CHAIN)
        _p, base = build_paths(d, models, pl, config=BASELINE)
        _p, multi = build_paths(d, models, pl, config=TWO)
        assert base.signals["demand_share_without_any_path"] == pytest.approx(1.0)
        assert multi.signals["demand_share_without_any_path"] == pytest.approx(0.0)


# ============================================================ I. global stage (reconcile)
class TestGlobalStage:
    """SYNTHETIC end to end through ``reconcile``: the regional partition of a plan that carries
    a two-transfer journey must add up to the ledger (both hubs' transshipment charges
    attributed), and the result carries the strategy report and the re-optimisation record."""

    def _stage(self, monkeypatch, **env):
        from src.network.reconcile import reconcile
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        d = [Demand("A", "D", 500.0, 3000.0, max_transit_days=30.0),
             Demand("B", "C", 200.0, 2000.0, max_transit_days=30.0)]
        pr = problem(d, port_over={"B": dict(transshipment_cost=40), "C": dict(transshipment_cost=50)})
        pools = {"R1": [{"id": f"s{i}", "ports": list(r), "vessel_class": "V"} for i, r in enumerate(CHAIN)]}
        region_of_od = {("A", "D"): "R1", ("B", "C"): "R1"}
        return reconcile(pr, pools, region_of_od, ["R1"], time_limit_sec=30)

    def test_two_transfer_plan_partitions_exactly(self, monkeypatch):
        st = self._stage(monkeypatch, LINER_MAX_TRANSFERS="2", LINER_FLOW_REOPT="1")
        assert st.ok, st.message
        led = st.plan.ledger
        assert not led.violations and st.network_ledger["verified"]
        assert st.network_ledger["assumptions"]["max_transfers_per_od"] == 2
        reg = st.region_updates["R1"]
        assert reg["revenue"] == pytest.approx(led.revenue)
        assert reg["total_cost"] == pytest.approx(led.operating_cost)
        assert reg["transship_cost"] == pytest.approx(led.transshipment_cost)
        assert reg["transship_cost"] == pytest.approx(500.0 * 90.0)        # both hubs, 500 TEU
        assert st.network_ledger["strategy_report"]["reconciliation"]["all"]
        assert "flow_reoptimisation" in st.network_ledger["optimality"]

    def test_documented_rollback_restores_the_one_transfer_baseline(self, monkeypatch):
        for k, v in {"LINER_MAX_TRANSFERS": "1", "LINER_FLOW_REOPT": "0", "LINER_PROFIT_FLOOR_REPAIR": "0",
                     "LINER_PATH_SELECTION": "fastest", "LINER_PATH_BUDGET": "fixed"}.items():
            monkeypatch.setenv(k, v)
        st = self._stage(monkeypatch)
        assert st.network_ledger["assumptions"]["max_transfers_per_od"] == 1
        assert st.plan.ledger.served_teu == pytest.approx(200.0)           # A->D has no 1-transfer path
        assert st.network_ledger["optimality"]["flow_reoptimisation"]["applied"] is False

    def test_default_configuration_routes_the_two_transfer_journey(self, monkeypatch):
        for k in ("LINER_MAX_TRANSFERS", "LINER_FLOW_REOPT", "LINER_PROFIT_FLOOR_REPAIR",
                  "LINER_PATH_SELECTION", "LINER_PATH_BUDGET"):
            monkeypatch.delenv(k, raising=False)
        st = self._stage(monkeypatch)
        assert st.ok and st.network_ledger["verified"]
        assert st.network_ledger["assumptions"]["max_transfers_per_od"] == 2
        assert st.plan.ledger.served_teu == pytest.approx(700.0)           # 500 (two transfers) + 200


# ================================================================== J. only_services restriction
class TestOnlyServices:
    def test_restriction_equals_the_unrestricted_set_filtered(self):
        d = [Demand("A", "C", 100.0, 3000.0), Demand("A", "B", 100.0, 3000.0), Demand("B", "D", 50.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, [["A", "C"], ["A", "B"], ["B", "C"], ["A", "B", "C"], ["C", "D"], ["B", "D"]])
        cfg = PathConfig(max_transfers=2, multi_hop_min_alternatives=10 ** 6)
        full, _ = build_paths(d, models, pl, max_paths_per_od=10 ** 6, config=cfg)
        keep = {0, 1, 2, 5}
        sub, _ = build_paths(d, models, pl, max_paths_per_od=10 ** 6, config=cfg, only_services=keep)

        def keys(paths):
            return {(di, p.services, p.transfer_ports) for di, pl_ in paths.items() for p in pl_}
        want = {k for k in keys(full) if set(k[1]) <= keep}
        assert keys(sub) == want and want


# ============================================================ K. profit-floor repair (Task 20)
class TestProfitFloorRepair:
    """SYNTHETIC.  s0 (A<->B) earns, s1 (C<->D) loses: both are forced on (fixed frequencies), which
    is what a time-limited incumbent can look like.  A floor above the plan's profit makes the
    repair switch s1 off; a plan at or above the floor is left alone."""

    def _incumbent(self):
        from src.network.flow_reopt import repair_profit_floor
        d = [Demand("A", "B", 300.0, 2000.0, max_transit_days=60.0),
             Demand("C", "D", 10.0, 100.0, max_transit_days=60.0)]
        pr = problem(d)
        pl = NetworkPlanner(pr, path_config=BASELINE)
        cands = [Candidate("s0", ("A", "B"), "V"), Candidate("s1", ("C", "D"), "V")]
        res = pl.plan(cands, fixed_frequencies={"s0": 1, "s1": 1}, time_limit_sec=30, lp_guided=False)

        def all_paths():
            return build_paths(res.demands, res.models, pl.port_lookup, pl.assumptions,
                               max_paths_per_od=10 ** 6, config=BASELINE, only_services=[0, 1])
        return res, all_paths, repair_profit_floor

    def test_a_plan_below_the_floor_loses_its_losing_service(self):
        res, all_paths, repair = self._incumbent()
        before = res.ledger.operating_profit
        assert before > 0.0
        rep = repair(res.models, res.demands, res.paths, res.solution, all_paths, floor_usd=before + 1.0)
        assert rep["applied"] and rep["dropped"] == ["s1"], rep
        assert rep["profit_after"] > before
        assert res.solution.frequencies[1] == 0 and res.solution.frequencies[0] == 1
        # the objective the solution now carries is the ledger's profit of the repaired plan
        from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
        a = res.models
        flows = [LedgerFlow(di, tuple((a[s.service].service_id, s.from_port, s.to_port)
                                      for s in res.paths[di][k].segments), t)
                 for di, k, t in res.solution.flows]
        svc = [LedgerService(a[si].service_id, a[si].ports, a[si].vessel_class, int(fr))
               for si, fr in res.solution.frequencies.items() if fr > 0]
        pl_ = {p.id: p for p in problem([]).ports}
        led = compute_ledger(svc, flows, res.demands, Fleet(classes=[vessel()]), DM, pl_,
                             port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
                             bunker_price_usd_per_t=600.0)
        assert not led.violations
        assert led.operating_profit == pytest.approx(res.solution.objective_value, rel=1e-9)

    def test_a_plan_at_or_above_the_floor_is_untouched(self):
        res, all_paths, repair = self._incumbent()
        before = list(res.solution.flows)
        rep = repair(res.models, res.demands, res.paths, res.solution, all_paths, floor_usd=0.0)
        assert rep["applied"] is False and rep["reason"] == "profit floor met"
        assert res.solution.flows == before and res.solution.frequencies[1] == 1


class TestDirectOnly:
    def test_zero_transfers_builds_direct_paths_only(self):
        d = [Demand("A", "C", 100.0, 3000.0), Demand("A", "B", 100.0, 3000.0)]
        pr = problem(d)
        models, pl = models_for(pr, [["A", "B"], ["B", "C"]])
        paths, st = build_paths(d, models, pl, config=PathConfig(max_transfers=0))
        assert set(paths) == {1} and all(p.kind == "direct" for p in paths[1])
        assert st.od_without_path == 1
