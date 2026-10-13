"""C2 - exact-LP local search over the operated service set (``LINER_LOCAL_SEARCH``, default OFF).

Contract
  * default OFF: nothing changes, the plan reports ``local_search.enabled = False``;
  * every move is evaluated with the exact cargo LP (same terms as the MILP objective / ledger);
    a move that breaks fleet inventory, capacity, a transit limit or the coverage floor is never
    accepted; a move that adds served TEU but lowers profit is never accepted;
  * the search starts from a feasible plan and ends no worse (profit) and never serves less;
  * the deadline is hard (no move after it), and the stage budget is split, not extended;
  * the final plan passes the independent ledger; its status is ``feasible`` (never ``optimal``).
"""
import dataclasses
import itertools
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.local_search as ls
import src.network.network_milp as nm
from src.network.flow_reopt import reoptimize_flows
from src.network.paths import BUDGET_FIXED, SELECT_FASTEST, build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0},
      "C": {"A": 1600.0, "B": 600.0}}
CANDS = [Candidate("ab", ("A", "B"), "V"), Candidate("abc", ("A", "B", "C"), "V"),
         Candidate("bc", ("B", "C"), "V")]


def _problem(demands, capacity=1000.0, quantity=40, port_call=1000.0):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=port_call,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=quantity, capacity_teu=capacity, tc_rate_daily=8000.0,
                   min_speed=10.0, design_speed=12.0, max_speed=14.0,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM,
                   fleet=Fleet(classes=[v]))


def _demands():
    return [Demand("A", "B", 1500.0, 1000.0), Demand("B", "A", 1200.0, 1000.0),
            Demand("B", "C", 800.0, 900.0), Demand("A", "C", 300.0, 1500.0)]


def _setup(problem, fixed=None, **kw):
    planner = NetworkPlanner(problem)
    plan = planner.plan(CANDS, demands=problem.demands, fixed_frequencies=fixed, time_limit_sec=60.0, **kw)
    assert plan.ok, plan.message
    cfg = dataclasses.replace(planner.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED)
    limits = {c.vessel_class: c.quantity for c in problem.fleet.classes}

    def all_paths():
        return build_paths(problem.demands, plan.models, planner.port_lookup, planner.assumptions,
                           max_paths_per_od=10 ** 9, config=cfg)
    return planner, plan, limits, all_paths


def _profit(sol, models, demands, paths):
    rev = sum(demands[di].revenue_per_teu * t for di, k, t in sol.flows)
    port = sum(paths[di][k].port_cost_per_teu * t for di, k, t in sol.flows)
    fx = sum(models[s].weekly_fixed_cost(f) for s, f in sol.frequencies.items() if f > 0)
    return rev - port - fx


CFG = ls.LocalSearchConfig(enabled=True)


class TestConfig:
    def test_default_disabled(self, monkeypatch):
        for k in (ls.ENV_ENABLED, ls.ENV_RESERVE, ls.ENV_MOVES):
            monkeypatch.delenv(k, raising=False)
        assert ls.config_from_environment().enabled is False

    def test_parsing_and_errors(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.setenv(ls.ENV_RESERVE, "15")
        monkeypatch.setenv(ls.ENV_MOVES, "add,drop")
        c = ls.config_from_environment()
        assert c.enabled and c.reserve_sec == 15.0 and c.moves == ("add", "drop")
        monkeypatch.setenv(ls.ENV_MOVES, "swap")
        with pytest.raises(ValueError):
            ls.config_from_environment()
        monkeypatch.setenv(ls.ENV_MOVES, "add")
        monkeypatch.setenv(ls.ENV_RESERVE, "soon")
        with pytest.raises(ValueError):
            ls.config_from_environment()
        monkeypatch.setenv(ls.ENV_RESERVE, "15")
        monkeypatch.setenv(ls.ENV_ENABLED, "maybe")
        with pytest.raises(ValueError):
            ls.config_from_environment()

    def test_reserve_never_exceeds_half_the_budget(self):
        assert ls.reserve_for(ls.LocalSearchConfig(enabled=True, reserve_sec=25.0), 120.0) == 25.0
        assert ls.reserve_for(ls.LocalSearchConfig(enabled=True, reserve_sec=25.0), 30.0) == 15.0


class TestDisabledByDefault:
    def test_plan_is_unchanged_and_says_so(self, monkeypatch):
        monkeypatch.delenv(ls.ENV_ENABLED, raising=False)
        pr = _problem(_demands())
        plan = NetworkPlanner(pr).plan(CANDS, demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok
        assert plan.local_search == {"enabled": False, "applied": False, "reason": "disabled"}
        assert plan.stage_timing["milp_budget_sec"] == 60.0
        assert "local_search_sec" not in plan.stage_timing
        assert plan.reconciliation["local_search"]["enabled"] is False


class TestMoves:
    def test_improves_a_poor_incumbent_and_never_exceeds_the_brute_force_optimum(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1})          # a poor, feasible plan
        sol, models = plan.solution, plan.models
        before = _profit(sol, models, pr.demands, plan.paths)
        served_before = sum(t for _, _, t in sol.flows)
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() + 60.0)
        assert rep["applied"] is True and rep["moves"]
        after = _profit(sol, models, pr.demands, plan.paths)
        assert after > before + 1000.0
        assert rep["profit_before"] == pytest.approx(before, rel=1e-9, abs=1e-3)
        assert rep["profit_after"] == pytest.approx(after, rel=1e-9, abs=1e-3)
        assert sum(t for _, _, t in sol.flows) >= served_before - 1e-6        # never serves less
        # brute force over f in {0,1,2}^3 (exact MILP with imposed frequencies, CBC)
        best = float("-inf")
        for f in itertools.product((0, 1, 2), repeat=len(models)):
            fx = {models[i].service_id: f[i] for i in range(len(models))}
            got = nm.solve_network(models, pr.demands, plan.paths, limits, fixed_frequencies=
                                   {i: f[i] for i in range(len(models))}, time_limit_sec=30.0)
            if got.usable:
                best = max(best, got.objective_value)
        assert after <= best + 1.0                                            # a local optimum, not above the global one
        assert after >= before - 1e-6

    def test_final_plan_passes_the_independent_ledger_through_the_planner(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.setenv(ls.ENV_RESERVE, "20")
        pr = _problem(_demands())
        planner = NetworkPlanner(pr)
        plan = planner.plan(CANDS, demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok and plan.ledger.valid and plan.reconciliation["reconciled"] is True
        assert plan.local_search["enabled"] is True
        assert plan.stage_timing["milp_budget_sec"] == 40.0                    # 60 - 20: split, not extended
        assert plan.status in ("feasible", "optimal")
        if plan.local_search.get("applied"):
            assert plan.status == "feasible"                                   # never claims optimality
        assert plan.ledger.operating_profit == pytest.approx(plan.solution.objective_value, abs=1e-3)

    def test_move_that_adds_coverage_but_loses_money_is_not_accepted(self):
        # the only OD that the unoperated service could serve pays less than its fixed cost
        pr = _problem([Demand("A", "B", 1500.0, 1000.0), Demand("B", "C", 20.0, 50.0)])
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1})
        sol, models = plan.solution, plan.models
        served_before = sum(t for _, _, t in sol.flows)
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() + 60.0)
        assert not any(m["move"] == "add" and "bc" in m["service"] for m in rep["moves"])
        assert sum(t for _, _, t in sol.flows) >= served_before - 1e-6
        if rep["applied"]:
            assert rep["gain_usd"] > 0

    def test_drop_that_would_lose_coverage_is_refused(self):
        # a loss-making service whose cargo nothing else can carry (and no other move can make up
        # for it): dropping it raises profit but would lower served TEU - the coverage floor forbids it
        pr = _problem([Demand("A", "B", 600.0, 1000.0), Demand("B", "C", 30.0, 60.0)])
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1, "bc": 1})
        sol, models = plan.solution, plan.models
        served_before = sum(t for _, _, t in sol.flows)
        bc = next(i for i, m in enumerate(models) if m.service_id == "bc")
        assert sol.frequencies.get(bc, 0) == 1
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() + 60.0)
        assert sol.frequencies.get(bc, 0) == 1
        assert sum(t for _, _, t in sol.flows) >= served_before - 1e-6
        assert not any(m["move"] == "drop" and m["service"] == "bc" for m in rep["moves"])

    def test_class_inventory_blocks_an_add(self):
        pr = _problem(_demands(), quantity=1)           # one vessel in total
        planner, plan, limits, all_paths = _setup(pr)
        sol, models = plan.solution, plan.models
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() + 60.0)
        used = sum(models[s].vessels(f) for s, f in sol.frequencies.items() if f > 0)
        assert used <= 1

    def test_expired_deadline_changes_nothing(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1})
        sol, models = plan.solution, plan.models
        before = (dict(sol.frequencies), list(sol.flows))
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() - 1.0)
        assert rep["applied"] is False and rep["terminated_by"] in ("deadline", "deadline_before_search")
        assert (dict(sol.frequencies), list(sol.flows)) == before

    def test_incomplete_incumbent_is_reported_not_guessed(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1})
        sol, models = plan.solution, plan.models
        sol.flows = []
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() + 60.0)
        assert rep["applied"] is False and rep["terminated_by"] == "no_incumbent"

    def test_moves_can_be_restricted(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1})
        sol, models = plan.solution, plan.models
        cfg = ls.LocalSearchConfig(enabled=True, moves=("freq",))
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=cfg,
                              deadline=time.perf_counter() + 60.0)
        assert all(m["move"] in ("up", "down") for m in rep["moves"])


class TestInteractions:
    def test_flow_reoptimisation_after_a_move_never_lowers_profit(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1})
        sol, models = plan.solution, plan.models
        rep = ls.local_search(models, pr.demands, plan.paths, sol, limits, all_paths, config=CFG,
                              deadline=time.perf_counter() + 60.0)
        assert rep["applied"]
        p0 = _profit(sol, models, pr.demands, plan.paths)

        def full():
            operated = [s for s, f in sol.frequencies.items() if f > 0]
            cfg = dataclasses.replace(planner.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED,
                                      multi_hop_min_alternatives=10 ** 9)
            return build_paths(pr.demands, models, planner.port_lookup, planner.assumptions,
                               max_paths_per_od=10 ** 9, config=cfg, only_services=operated)
        reoptimize_flows(models, pr.demands, plan.paths, sol, full)
        assert _profit(sol, models, pr.demands, plan.paths) >= p0 - 1e-6


class TestVariantsVisibleOnlyToTheSearch:
    """``LINER_LOCAL_SEARCH_VARIANTS``: alternative-class services are modelled AFTER the MILP and offered
    to the search only; the MILP's service set is unchanged."""

    def _problem(self):
        classes = [FleetClass(vessel_class="S", quantity=2, capacity_teu=1000.0, tc_rate_daily=8000.0,
                              min_speed=10.0, design_speed=12.0, max_speed=14.0,
                              bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0),
                   FleetClass(vessel_class="M", quantity=20, capacity_teu=1500.0, tc_rate_daily=9000.0,
                              min_speed=10.0, design_speed=12.0, max_speed=14.0,
                              bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)]
        ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                      variable_port_call_cost=0.0) for p in "ABC"]
        dem = [Demand("A", "B", 800.0, 1500.0), Demand("B", "A", 700.0, 1500.0), Demand("B", "C", 600.0, 1200.0),
               Demand("C", "B", 500.0, 1200.0)]
        return Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=classes))

    def test_extra_services_are_modelled_for_the_search_only(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.setenv(ls.ENV_VARIANTS, "1.0")
        pr = self._problem()
        # 5 candidates of the 2-vessel class S: 2.5 candidates per vessel (>= 2: over-subscribed)
        cands = [Candidate("c0", ("A", "B"), "S"), Candidate("c1", ("B", "C"), "S"),
                 Candidate("c2", ("A", "B", "C"), "S"), Candidate("c3", ("A", "C"), "S"),
                 Candidate("c4", ("A", "C", "B"), "S")]
        plan = NetworkPlanner(pr).plan(cands, demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok and plan.ledger.valid and plan.reconciliation["reconciled"] is True
        assert plan.solution.n_services_considered <= len(cands)             # the MILP never saw the variants
        v = plan.local_search.get("variants")
        assert v is not None and v["added"] >= 1 and v["modelled"] == v["added"]
        assert any(m.service_id.startswith("lv") for m in plan.models)
        for a in plan.local_search["variant_additions"]:
            assert a["service_id"].startswith("lv") and a["vessel_class"] == "M"

    def test_off_by_default(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.delenv(ls.ENV_VARIANTS, raising=False)
        pr = self._problem()
        cands = [Candidate("c0", ("A", "B"), "S"), Candidate("c1", ("B", "C"), "S")]
        plan = NetworkPlanner(pr).plan(cands, demands=pr.demands, time_limit_sec=30.0)
        assert "variants" not in plan.local_search
        assert not any(m.service_id.startswith("lv") for m in plan.models)

    def test_parsing(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_VARIANTS, "0.25")
        assert ls.variants_from_environment() == 0.25
        for bad in ("-1", "2", "x"):
            monkeypatch.setenv(ls.ENV_VARIANTS, bad)
            with pytest.raises(ValueError):
                ls.variants_from_environment()


class TestMultiHopEvaluator:
    def test_parsing(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.delenv(ls.ENV_MULTIHOP, raising=False)
        assert ls.config_from_environment().multi_hop is False
        monkeypatch.setenv(ls.ENV_MULTIHOP, "1")
        assert ls.config_from_environment().multi_hop is True
        monkeypatch.setenv(ls.ENV_MULTIHOP, "maybe")
        with pytest.raises(ValueError):
            ls.config_from_environment()

    def test_plan_with_the_richer_evaluator_is_ledger_verified(self, monkeypatch):
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.setenv(ls.ENV_MULTIHOP, "1")
        pr = _problem(_demands())
        plan = NetworkPlanner(pr).plan(CANDS, demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok and plan.ledger.valid and plan.reconciliation["reconciled"] is True


class TestSearchOnlyVariantFloor:
    """``LINER_LOCAL_SEARCH_VARIANTS_FLOOR``: its own floor, independent of ``LINER_CLASS_VARIANTS_FLOOR``."""

    def test_parsing(self, monkeypatch):
        monkeypatch.delenv(ls.ENV_VARIANTS_FLOOR, raising=False)
        assert ls.variants_floor_from_environment() is None
        monkeypatch.setenv(ls.ENV_VARIANTS_FLOOR, "-250000")
        assert ls.variants_floor_from_environment() == -250000.0
        for bad in ("5", "x", "nan", "-inf"):
            monkeypatch.setenv(ls.ENV_VARIANTS_FLOOR, bad)
            with pytest.raises(ValueError):
                ls.variants_floor_from_environment()

    def test_floor_admits_more_variants_and_the_plan_stays_verified(self, monkeypatch):
        helper = TestVariantsVisibleOnlyToTheSearch()
        pr = helper._problem()
        cands = [Candidate("c0", ("A", "B"), "S"), Candidate("c1", ("B", "C"), "S"),
                 Candidate("c2", ("A", "B", "C"), "S")]
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.setenv(ls.ENV_VARIANTS, "1.0")
        monkeypatch.delenv(ls.ENV_VARIANTS_FLOOR, raising=False)
        base = NetworkPlanner(pr).plan(cands, demands=pr.demands, time_limit_sec=30.0)
        monkeypatch.setenv(ls.ENV_VARIANTS_FLOOR, "-1e12")
        wide = NetworkPlanner(pr).plan(cands, demands=pr.demands, time_limit_sec=30.0)
        assert base.ok and wide.ok and wide.ledger.valid and wide.reconciliation["reconciled"] is True
        vb, vw = base.local_search.get("variants"), wide.local_search.get("variants")
        assert vw is not None and vw["standalone_profit_floor"] == -1e12
        assert (vb or {}).get("standalone_profit_floor", 0.0) == 0.0
        assert vw["added"] >= (vb or {}).get("added", 0)


class TestIdleServicePrune:
    """A service that carries no cargo in the final flows is dropped (found by the hold-out gate: the
    last search move opened a service the final re-routing then left empty)."""

    def test_an_empty_service_is_dropped_and_profit_rises_by_its_fixed_cost(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr, fixed={"ab": 1, "bc": 1})
        sol, models, paths = plan.solution, plan.models, plan.paths
        used = {s for di, k, t in sol.flows for s in paths[di][k].services}
        idle_si = next(i for i in range(len(models)) if i not in used)
        # make that unused service "operated" at f = 1 (the state the gate saw) and book its cost
        before_profit = _profit(sol, models, pr.demands, paths)
        sol.frequencies = {**{s: f for s, f in sol.frequencies.items() if f > 0}, idle_si: 1}
        m = models[idle_si]
        comp = dict(sol.objective_components)
        comp["vessel_cost"] = comp.get("vessel_cost", 0.0) + m.vessel_week_cost * m.vessels(1)
        comp["fuel_cost"] = comp.get("fuel_cost", 0.0) + m.fuel_cost_per_rotation
        comp["port_fixed_cost"] = comp.get("port_fixed_cost", 0.0) + m.port_fixed_per_rotation
        sol.objective_components = comp
        sol.objective_value -= m.weekly_fixed_cost(1)
        assert _profit(sol, models, pr.demands, paths) == pytest.approx(before_profit - m.weekly_fixed_cost(1))
        rep = ls.prune_idle_services(models, paths, sol)
        assert rep["applied"] is True and [d["service"] for d in rep["dropped"]] == [m.service_id]
        assert idle_si not in sol.frequencies and idle_si not in sol.vessels
        assert _profit(sol, models, pr.demands, paths) == pytest.approx(before_profit)
        assert sol.objective_value == pytest.approx(before_profit, rel=1e-9, abs=1e-3)
        assert rep["gain_usd"] == pytest.approx(m.weekly_fixed_cost(1))

    def test_nothing_is_dropped_when_every_service_carries_cargo(self):
        pr = _problem(_demands())
        planner, plan, limits, all_paths = _setup(pr)
        before = dict(plan.solution.frequencies)
        rep = ls.prune_idle_services(plan.models, plan.paths, plan.solution)
        assert rep == {"applied": False, "dropped": [], "gain_usd": 0.0}
        assert dict(plan.solution.frequencies) == before


class TestRegionalAttributionOfSearchOnlyVariants:
    """Every operated service - search-only variants included - lands in exactly one region, so the
    regional costs add up to the network ledger (the gate that found the defect: a cargo-less ``lv``
    service had no owner and its cost vanished from the regional partition)."""

    def test_regional_totals_equal_the_ledger_with_search_only_variants(self, monkeypatch):
        from src.network.reconcile import reconcile
        monkeypatch.setenv(ls.ENV_ENABLED, "1")
        monkeypatch.setenv(ls.ENV_VARIANTS, "1.0")
        monkeypatch.setenv(ls.ENV_VARIANTS_FLOOR, "-1e12")
        helper = TestVariantsVisibleOnlyToTheSearch()
        pr = helper._problem()
        pools = {"R1": [{"id": "c0", "ports": ["A", "B"], "vessel_class": "S"},
                        {"id": "c2", "ports": ["A", "B", "C"], "vessel_class": "S"}],
                 "R2": [{"id": "c1", "ports": ["B", "C"], "vessel_class": "S"}]}
        region_of_od = {("A", "B"): "R1", ("B", "A"): "R1", ("B", "C"): "R2", ("C", "B"): "R2"}
        res = reconcile(pr, pools, region_of_od, ["R1", "R2"], time_limit_sec=40.0)
        assert res.ok, res.message
        led = res.network_ledger["weekly_usd"]
        reg_profit = sum(u["weekly_profit"] for u in res.region_updates.values())
        reg_cost = sum(u["total_cost"] for u in res.region_updates.values())
        assert reg_profit == pytest.approx(led["operating_profit"], rel=1e-9, abs=1e-3)
        assert reg_cost == pytest.approx(led["total_operating_cost"], rel=1e-9, abs=1e-3)
        listed = {x["id"] for u in res.region_updates.values() for x in u["selected_services"]}
        assert listed == {s["id"] for s in res.network_ledger["plan"]["services"]}

    def test_owner_registration_for_search_only_variants(self):
        from src.network.reconcile import _register_variant_owners
        owner = {"asia_1": "Asia", "cv0001": "Europe"}
        proposers = {"asia_1": ["Asia", "Europe"], "cv0001": ["Europe"]}
        _register_variant_owners([{"service_id": "lv0000", "rotation_of": "asia_1"},
                                  {"service_id": "lv0001", "rotation_of": "cv0001"},
                                  {"service_id": "lv0002", "rotation_of": "unknown"}], owner, proposers)
        assert owner["lv0000"] == "Asia" and proposers["lv0000"] == ["Asia", "Europe"]
        assert owner["lv0001"] == "Europe" and proposers["lv0001"] == ["Europe"]
        assert owner["lv0002"] is None and proposers["lv0002"] == []          # unknown source: no invented owner
        _register_variant_owners(None, owner, proposers)                       # nothing to register: no error

    def test_a_service_without_cargo_or_proposer_is_never_dropped_from_the_partition(self):
        from src.network.reconcile import _fallback_owner
        regions = {"Asia": 1, "Europe": 2}
        names = ["Asia", "Europe"]
        assert _fallback_owner(["Europe", "Asia"], "Asia", regions, names) == "Europe"      # first proposer
        assert _fallback_owner([], "Europe", regions, names) == "Europe"                    # rotation owner
        assert _fallback_owner(["Mars"], "Mars", regions, names) == "Asia"                  # nothing known: first region
        assert _fallback_owner([], None, regions, names) == "Asia"
        assert _fallback_owner([], None, {}, []) is None                                    # no regions at all

