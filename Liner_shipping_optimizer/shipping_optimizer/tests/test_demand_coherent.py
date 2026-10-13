"""Task 9 - demand-coherent multi-port closed-rotation generation.

Synthetic network (clearly labelled), directed distances in nautical miles:

    A->B 1000  B->A 1050   B->C 800  C->B 820   C->D 900  D->C 900
    D->A 1400  A->D 1380   A->C 1700 C->A 1700  B->D 1500 D->B 1500
    E is far from everything (no demand touches it)

    V: 1,000 TEU, design 12 kn, TC 8,000/d, 20 t/d sea, 2 t/d idle, 5 vessels
    W: 3,000 TEU, design 16 kn, TC 15,000/d, 50 t/d sea, 4 t/d idle, 3 vessels
    bunker 600 USD/t, port stay 24 h, port call 1,000 USD, no per-TEU port charges
"""
import math
import os
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.economics import assumptions_for_problem
from src.network.plan import Candidate, NetworkPlanner
from src.services.demand_coherent import (
    ENV_BUDGET, R_BUDGET, R_DUPLICATE_OF_POOL, R_NO_RIDE_FEASIBLE_DEMAND,
    DemandCoherentConfig, _canonical, config_from_environment,
    generate_demand_coherent_rotations,
)
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem
from src.services.service_feasibility import evaluate_rotation

DM = {
    "A": {"B": 1000.0, "C": 1700.0, "D": 1380.0, "E": 9000.0},
    "B": {"A": 1050.0, "C": 800.0, "D": 1500.0, "E": 9000.0},
    "C": {"A": 1700.0, "B": 820.0, "D": 900.0, "E": 9000.0},
    "D": {"A": 1400.0, "B": 1500.0, "C": 900.0, "E": 9000.0},
    "E": {"A": 9000.0, "B": 9000.0, "C": 9000.0, "D": 9000.0},
}


def fleet():
    return Fleet(classes=[
        FleetClass("V", 5, 1000.0, 8000.0, draft=9, min_speed=10, max_speed=14, design_speed=12,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0),
        FleetClass("W", 3, 3000.0, 15000.0, draft=12, min_speed=12, max_speed=18, design_speed=16,
                   bunker_consumption_tons_per_day=50.0, idle_consumption_tons_per_day=4.0),
    ])


def problem(demands, dm=None):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABCDE"]
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=dm or DM, fleet=fleet())


DEMANDS = [
    Demand("A", "B", 400.0, 1000.0, max_transit_days=30.0),
    Demand("B", "A", 300.0, 1000.0, max_transit_days=30.0),
    Demand("B", "C", 350.0, 1000.0, max_transit_days=30.0),
    Demand("C", "D", 300.0, 1000.0, max_transit_days=30.0),
    Demand("D", "A", 250.0, 1000.0, max_transit_days=30.0),
    Demand("A", "C", 200.0, 1000.0, max_transit_days=30.0),
]
CFG = DemandCoherentConfig(budget=10, max_ports=4, seed_pairs=10, neighbourhood=4)


def run(demands=None, existing=(), cfg=CFG, dm=None):
    pr = problem(demands if demands is not None else DEMANDS, dm)
    return generate_demand_coherent_rotations(pr, pr.fleet, existing, cfg), pr


# ============================================================ validity of every proposal
class TestEveryProposalIsAValidClosedRotation:
    def test_proposals_exist_and_are_multi_port(self):
        (props, rep), _ = run()
        assert props, "the synthetic network has clear multi-port opportunities"
        assert all(3 <= p.n_ports <= CFG.max_ports for p in props)

    def test_distinct_ports_and_all_legs_including_the_return_leg_have_a_distance(self):
        (props, _), pr = run()
        for p in props:
            assert len(set(p.ports)) == len(p.ports)
            for i, a in enumerate(p.ports):
                b = p.ports[(i + 1) % len(p.ports)]
                assert DM[a].get(b), f"{p.ports}: no distance {a}->{b}"

    def test_vessels_cycle_and_cost_follow_the_canonical_model(self):
        (props, _), pr = run()
        for p in props:
            cls = pr.fleet.get_class(p.vessel_class)
            assert cls is not None, "a registered class"
            nm = sum(DM[a][p.ports[(i + 1) % len(p.ports)]] for i, a in enumerate(p.ports))
            sea = nm / (cls.design_speed * 24.0)
            cycle = math.ceil(round(sea + len(p.ports) * 1.0, 9))
            assert p.cycle_time_days == cycle
            assert p.cycle_days == pytest.approx(sea + len(p.ports))
            assert p.vessels_at_f1 == math.ceil(round(cycle / 7.0, 9))
            assert p.vessels_at_f1 <= cls.quantity                    # inventory respected
            fuel_t = sea * cls.bunker_consumption_tons_per_day + len(p.ports) * cls.idle_consumption_tons_per_day
            fixed = p.vessels_at_f1 * cls.tc_rate_daily * 7 + fuel_t * 600.0 + len(p.ports) * 1000.0
            assert p.fixed_cost_f1 == pytest.approx(fixed)
            assert p.standalone_profit_f1 == pytest.approx(p.net_revenue_f1 - fixed)

    def test_every_proposal_passes_the_production_feasibility_screen(self):
        (props, _), pr = run()
        for p in props:
            f = evaluate_rotation(list(p.ports), pr.fleet.get_class(p.vessel_class), DM,
                                  known_ports=set(DM))
            assert f.feasible, (p.ports, f.reasons)

    def test_served_teu_never_exceeds_requested_or_leg_capacity(self):
        (props, _), pr = run()
        for p in props:
            cap = pr.fleet.get_class(p.vessel_class).capacity_teu
            assert p.served_teu_f1 <= p.requested_teu + 1e-9
            assert p.served_teu_f1 <= cap * p.n_ports + 1e-9           # at most cap on every leg


# ===================================================================== no invention
class TestNothingIsInvented:
    def test_missing_directed_distance_is_never_substituted(self):
        dm = {k: dict(v) for k, v in DM.items()}
        del dm["B"]["C"]                      # B->C unknown
        (props, rep), _ = run(dm=dm)
        for p in props:
            for i, a in enumerate(p.ports):
                b = p.ports[(i + 1) % len(p.ports)]
                assert (a, b) != ("B", "C"), f"{p.ports} uses the missing leg"
        assert rep.rejected.get("missing_directed_distance", 0) > 0

    def test_transit_time_infeasible_demand_is_not_counted_as_served(self):
        tight = [Demand(d.origin, d.destination, d.weekly_teu, d.revenue_per_teu, max_transit_days=0.5)
                 for d in DEMANDS]
        (props, rep), _ = run(demands=tight)
        assert props == []
        assert rep.rejected.get(R_NO_RIDE_FEASIBLE_DEMAND, 0) > 0

    def test_ride_time_limit_is_applied_per_od(self):
        # only A->B is ever carried within its limit: a rotation whose ride A->B
        # exceeds the limit must not claim it
        d = [Demand("A", "B", 400.0, 1000.0, max_transit_days=1.0),   # direct sail is 3.5 d
             Demand("B", "C", 350.0, 1000.0, max_transit_days=30.0),
             Demand("C", "D", 300.0, 1000.0, max_transit_days=30.0)]
        (props, _), _ = run(demands=d)
        for p in props:
            # A->B can never be ride-feasible, so it contributes no requested TEU
            assert p.requested_teu <= 350.0 + 300.0 + 1e-9

    def test_unreachable_isolated_port_is_not_added(self):
        (props, _), _ = run()
        assert all("E" not in p.ports for p in props)


# ============================================================== budget / determinism
class TestBudgetDeterminismAndDedup:
    def test_budget_is_respected_and_zero_disables(self):
        (p1, r1), _ = run(cfg=DemandCoherentConfig(budget=1, max_ports=4, seed_pairs=10, neighbourhood=4))
        assert len(p1) <= 1 and r1.rejected.get(R_BUDGET, 0) >= 0
        (p0, _), _ = run(cfg=DemandCoherentConfig(budget=0))
        assert p0 == []
        (pd, _), _ = run(cfg=DemandCoherentConfig(enabled=False))
        assert pd == []

    def test_identical_inputs_give_identical_proposals(self):
        (a, _), _ = run()
        (b, _), _ = run()
        assert [(p.ports, p.vessel_class) for p in a] == [(p.ports, p.vessel_class) for p in b]
        assert [p.weighted_score for p in a] == [p.weighted_score for p in b]

    def test_does_not_depend_on_the_global_random_state(self):
        random.seed(1)
        (a, _), _ = run()
        random.seed(999)
        (b, _), _ = run()
        assert [(p.ports, p.vessel_class) for p in a] == [(p.ports, p.vessel_class) for p in b]

    def test_rotations_already_in_the_pool_are_not_proposed_again(self):
        (first, _), _ = run()
        existing = [(list(first[0].ports), first[0].vessel_class)]
        (second, rep), _ = run(existing=existing)
        keys = {_canonical(p.ports) for p in second}
        assert _canonical(first[0].ports) not in keys
        assert rep.rejected.get(R_DUPLICATE_OF_POOL, 0) >= 1

    def test_no_two_proposals_are_the_same_rotation(self):
        (props, _), _ = run()
        keys = [_canonical(p.ports) for p in props]
        assert len(keys) == len(set(keys))

    def test_existing_two_port_pool_is_untouched_and_still_supported(self):
        existing = [(["A", "B"], "V"), (["B", "C"], "V")]
        (props, _), _ = run(existing=existing)
        assert props and all(p.n_ports >= 3 for p in props)


# ============================================== complementarity is flagged, not faked
class TestComplementarityIsNeverPresentedAsProfit:
    def test_unprofitable_rotations_are_flagged_and_capped(self):
        cfg = DemandCoherentConfig(budget=6, max_ports=4, seed_pairs=10, neighbourhood=4,
                                   complementarity_share=0.34)
        (props, rep), _ = run(cfg=cfg)
        flagged = [p for p in props if not p.standalone_profitable]
        assert all(p.reason_kept == "complementarity_not_standalone_profitable" for p in flagged)
        assert all(p.standalone_profit_f1 <= 0 for p in flagged)
        assert len(flagged) <= int(math.floor(0.34 * 6 + 1e-9))
        assert all(p.standalone_profit_f1 > 0 for p in props if p.standalone_profitable)
        assert rep.complementarity_selected == len(flagged)


# ============================================ accounting: one TEU, one revenue, one cost
class TestDownstreamAccountingIsUnchanged:
    def test_a_generated_loop_is_planned_and_verified_by_the_independent_ledger(self):
        (props, _), pr = run()
        best = max(props, key=lambda p: p.standalone_profit_f1)
        planner = NetworkPlanner(pr, assumptions=assumptions_for_problem(pr))
        res = planner.plan([Candidate("loop", tuple(best.ports), best.vessel_class)], time_limit_sec=30)
        assert res.status in ("optimal", "feasible"), res.message
        led = res.ledger
        assert led is not None and led.valid, led.violations if led else res.message
        assert res.reconciliation["reconciled"]
        # each OD is served at most once and never above its demand
        want = {(d.origin, d.destination): d.weekly_teu for d in DEMANDS}
        for di, s in led.od_served.items():
            d = pr.demands[di]
            assert s <= want[(d.origin, d.destination)] + 1e-6
        assert led.served_teu == pytest.approx(sum(led.od_served.values()))
        # revenue is Sum(teu x rate) once - with one rate of 1,000 USD/TEU
        assert led.revenue == pytest.approx(1000.0 * led.served_teu)

    def test_a_tampered_loop_is_rejected_by_the_ledger(self):
        from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
        pr = problem(DEMANDS)
        kw = dict(port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
                  bunker_price_usd_per_t=600.0)
        plb = {p.id: p for p in pr.ports}
        # repeated port
        led = compute_ledger([LedgerService("s", ("A", "B", "A", "C"), "V", 1)], [], pr.demands,
                             pr.fleet, DM, plb, **kw)
        assert any(v["type"] == "invalid_route" for v in led.violations)
        # a leg with no distance (return leg missing)
        dm = {k: dict(v) for k, v in DM.items()}
        del dm["C"]["A"]
        led = compute_ledger([LedgerService("s", ("A", "B", "C"), "V", 1)], [], pr.demands,
                             pr.fleet, dm, plb, **kw)
        assert any(v["type"] == "missing_distance" for v in led.violations)


# ============================================================================ config
class TestConfiguration:
    def test_environment_budget(self):
        assert config_from_environment({}).enabled is True
        assert config_from_environment({ENV_BUDGET: "0"}).enabled is False
        c = config_from_environment({ENV_BUDGET: "12"})
        assert c.enabled and c.budget == 12
        with pytest.raises(ValueError):
            config_from_environment({ENV_BUDGET: "-1"})
        with pytest.raises(ValueError):
            config_from_environment({ENV_BUDGET: "many"})

    def test_invalid_config_is_rejected(self):
        with pytest.raises(ValueError):
            DemandCoherentConfig(min_ports=2)
        with pytest.raises(ValueError):
            DemandCoherentConfig(min_ports=4, max_ports=3)
        with pytest.raises(ValueError):
            DemandCoherentConfig(complementarity_share=1.5)

    def test_missing_fleet_is_an_explicit_error_not_a_default(self):
        from src.services.service_feasibility import ServiceFeasibilityError
        pr = problem(DEMANDS)
        with pytest.raises(ServiceFeasibilityError):
            generate_demand_coherent_rotations(pr, None, [], CFG)


# ======================================= integration with the production generator
class TestServiceGeneratorIntegration:
    @pytest.fixture(scope="class")
    def worldsmall(self):
        from src.data.network_loader import NetworkLoader
        ws = Path(__file__).resolve().parents[1] / "data" / "raw" / "WorldSmall"
        L = NetworkLoader()
        ports = L.load_ports(ws / "ports.csv")
        dem = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = L.load_distance_matrix(ws / "dist_dense.csv")
        fl = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
        for p in ports:
            dist.setdefault(p.id, {})
        return ports, dem, dist, fl

    def _generate(self, worldsmall, budget, seed=7):
        from src.agents.service_generator_agent import ServiceGeneratorAgent
        ports, dem, dist, fl = worldsmall
        pr = Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fl)
        old = os.environ.get(ENV_BUDGET)
        os.environ[ENV_BUDGET] = str(budget)
        try:
            random.seed(seed)
            agent = ServiceGeneratorAgent(name="t", model="none")
            services = agent.generate_services(pr, archetype_params=None)
        finally:
            if old is None:
                os.environ.pop(ENV_BUDGET, None)
            else:
                os.environ[ENV_BUDGET] = old
        return agent, services, pr

    def test_new_services_are_feasible_multi_port_and_within_budget(self, worldsmall):
        agent, services, pr = self._generate(worldsmall, 12)
        new = [s for s in services if getattr(s, "origin_section", "") == "demand_loop"]
        assert 0 < len(new) <= 12
        for s in new:
            assert len(s.ports) >= 3 and len(set(s.ports)) == len(s.ports)
            f = evaluate_rotation(s.ports, pr.fleet.get_class(s.vessel_class), pr.distance_matrix,
                                  known_ports=set(pr.distance_matrix))
            assert f.feasible and s.cycle_time == f.cycle_time_days
            assert s.capacity == pr.fleet.get_class(s.vessel_class).capacity_teu
            assert s.required_vessels <= pr.fleet.get_class(s.vessel_class).quantity
        assert agent.last_demand_coherent_report is not None
        assert agent.last_candidate_report.accepted_by_section["demand_loop"] == len(new)

    def test_disabling_reproduces_the_previous_pool_exactly(self, worldsmall):
        _, with_zero, _ = self._generate(worldsmall, 0)
        _, again, _ = self._generate(worldsmall, 0)
        assert [(s.ports, s.vessel_class) for s in with_zero] == [(s.ports, s.vessel_class) for s in again]
        assert not any(getattr(s, "origin_section", "") == "demand_loop" for s in with_zero)

    def test_enabling_only_adds_services_it_does_not_change_the_others(self, worldsmall):
        _, base, _ = self._generate(worldsmall, 0)
        _, plus, _ = self._generate(worldsmall, 12)
        base_keys = [(tuple(s.ports), s.vessel_class) for s in base]
        plus_keys = [(tuple(s.ports), s.vessel_class) for s in plus
                     if getattr(s, "origin_section", "") != "demand_loop"]
        assert plus_keys == base_keys

    def test_every_new_service_is_linked_to_actual_worldsmall_demand(self, worldsmall):
        from src.network.economics import assumptions_for_problem, build_service_model
        from src.services.demand_coherent import _Demand
        _, services, pr = self._generate(worldsmall, 12)
        catalog = {p.id: p for p in pr.ports}
        D = _Demand(pr.demands, catalog)
        a = assumptions_for_problem(pr)
        new = [s for s in services if getattr(s, "origin_section", "") == "demand_loop"]
        assert new
        for s in new:
            m = build_service_model("t", s.ports, pr.fleet.get_class(s.vessel_class),
                                    pr.distance_matrix, catalog, a)
            ok = 0
            for x in m.ports:
                for y in m.ports:
                    if x == y or (x, y) not in D.teu:
                        continue
                    ride = m.ride(x, y)
                    lim = D.limit.get((x, y))
                    if ride is not None and (lim is None or ride[1] <= lim + 1e-9):
                        ok += 1
            assert ok >= 1, f"{s.ports} carries no ride-feasible WorldSmall demand"

    def test_a_pool_with_new_loops_is_planned_without_duplicate_cargo_or_cost(self, worldsmall):
        from src.network.plan import Candidate, NetworkPlanner
        from src.network.economics import assumptions_for_problem
        _, services, pr = self._generate(worldsmall, 12)
        new = [s for s in services if getattr(s, "origin_section", "") == "demand_loop"][:8]
        old = [s for s in services if getattr(s, "origin_section", "") == "direct"][:20]
        cands = [Candidate(str(s.id), tuple(s.ports), s.vessel_class) for s in new + old]
        res = NetworkPlanner(pr, assumptions=assumptions_for_problem(pr)).plan(cands, time_limit_sec=60)
        assert res.status in ("optimal", "feasible"), res.message
        led = res.ledger
        assert led is not None and led.valid, led.violations if led else res.message
        assert res.reconciliation["reconciled"]
        # a TEU is carried once: served never exceeds demand, per OD and in total
        for di, srv in led.od_served.items():
            assert srv <= pr.demands[di].weekly_teu + 1e-6
        assert led.served_teu <= led.total_demand_teu + 1e-6
        # each service's cost is counted once: vessels/fuel/port-call lines equal the rows
        assert led.vessel_cost == pytest.approx(sum(r["vessel_cost"] for r in led.service_rows.values()))
        assert led.fuel_cost == pytest.approx(sum(r["fuel_cost"] for r in led.service_rows.values()))
        assert led.revenue == pytest.approx(
            sum(srv * pr.demands[di].revenue_per_teu for di, srv in led.od_served.items()), rel=1e-6)

    def test_same_seed_same_pool(self, worldsmall):
        _, a, _ = self._generate(worldsmall, 12, seed=3)
        _, b, _ = self._generate(worldsmall, 12, seed=3)
        assert [(tuple(s.ports), s.vessel_class) for s in a] == [(tuple(s.ports), s.vessel_class) for s in b]
