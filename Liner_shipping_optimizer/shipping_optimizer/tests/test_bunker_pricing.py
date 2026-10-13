"""Task 8B - region-aware bunker pricing: snapshot, resolution, model and ledger.

Fixtures are SYNTHETIC (the same V / A,B,C network as ``test_network_economics``)
with hand-computed expectations:

    A<->B rotation:  sea 2,200 nm / (12 kn * 24) = 7.63889 d, 2 port days
    fuel tonnes / rotation = 7.63889 * 20 + 2 * 2 = 156.7778 t

The bundled real snapshot (``data/pricing``) is used only to prove it loads and
resolves; no test asserts that regional pricing makes anything more profitable.
"""
import copy
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.bunker_prices import (
    BASIS_LEGACY, BASIS_OBSERVED_PORT, BASIS_REFERENCE, FALLBACK_ERROR, FALLBACK_REFERENCE,
    MODE_LEGACY, MODE_SNAPSHOT, RULE_CHEAPEST_OBSERVED, RULE_REFERENCE_ONLY, BunkerPriceError,
    FuelPricing, active_pricing, load_snapshot, pricing_from_environment, use_pricing,
)
from src.network.economics import (
    DEFAULT_ASSUMPTIONS, EconomicsAssumptions, ServiceModelError, assumptions_for_problem,
    build_service_model,
)
from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "data" / "pricing" / "bunker_snapshot_2026-10-09_vlsfo.json"

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0}, "C": {"A": 1600.0, "B": 600.0}}
TONNES_AB = (2200.0 / (12.0 * 24.0)) * 20.0 + 2.0 * 2.0          # 156.7778 t per rotation


def vessel():
    return FleetClass(vessel_class="V", quantity=5, capacity_teu=1000.0, tc_rate_daily=8000.0,
                      min_speed=10.0, design_speed=12.0, max_speed=14.0,
                      bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)


def problem(demands):
    pl = [Port(pid, pid, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
               transshipment_cost=0.0, variable_port_call_cost=0.0) for pid in "ABC"]
    return Problem(ports=pl, services=[], demands=demands, distance_matrix=DM,
                   fleet=Fleet(classes=[vessel()]))


def snap_dict(**over):
    d = {
        "schema_version": 1, "snapshot_id": "synthetic_test", "fuel_grade": "VLSFO",
        "currency": "USD", "unit": "USD_per_metric_tonne", "as_of": "2026-10-09",
        "max_age_days": 14, "description": "synthetic", "licence_note": "synthetic",
        "observations": [
            {"hub": "A", "price": 700.0, "observed_on": "2026-10-09", "provenance": "observed",
             "source": "synthetic"},
            {"hub": "C", "price": 800.0, "observed_on": "2026-10-08", "provenance": "observed",
             "source": "synthetic"},
        ],
        "reference": {"hub": "GLOBAL", "price": 750.0, "observed_on": "2026-10-09",
                      "provenance": "observed", "source": "synthetic index"},
    }
    d.update(over)
    return d


def regional(**kw):
    return FuelPricing.from_snapshot(load_snapshot(snap_dict()), **kw)


def assumptions_with(pricing):
    return EconomicsAssumptions(fuel_pricing=pricing)


def model(route, pricing=None):
    pr = problem([])
    a = assumptions_with(pricing) if pricing is not None else DEFAULT_ASSUMPTIONS
    return build_service_model("s", route, pr.fleet.get_class("V"), DM,
                               {p.id: p for p in pr.ports}, a)


# ============================================================ 1. snapshot validation
class TestSnapshotValidation:
    def test_loads_and_exposes_provenance(self):
        s = load_snapshot(snap_dict())
        assert s.fuel_grade == "VLSFO" and s.hubs == ("A", "C")
        assert s.observation_for("A").price_usd_per_t == 700.0
        assert s.reference.price_usd_per_t == 750.0
        assert s.observation_for("A").provenance == "observed"

    def test_hash_pins_content_not_formatting(self, tmp_path):
        d = snap_dict()
        p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
        p1.write_text(json.dumps(d, indent=2), encoding="utf-8")
        reordered = dict(reversed(list(d.items())))
        p2.write_text(json.dumps(reordered, separators=(",", ":")), encoding="utf-8")
        assert load_snapshot(p1).sha256 == load_snapshot(p2).sha256
        d2 = copy.deepcopy(d)
        d2["observations"][0]["price"] = 700.5
        assert load_snapshot(d2).sha256 != load_snapshot(d).sha256

    @pytest.mark.parametrize("bad", [0, -5.0, float("nan"), float("inf"), None, "700", True])
    def test_invalid_price_is_an_error_never_zero(self, bad):
        d = snap_dict()
        d["observations"][0]["price"] = bad
        with pytest.raises(BunkerPriceError) as e:
            load_snapshot(d)
        assert "invalid_price" in e.value.reasons

    def test_grade_mismatch_is_detected(self):
        with pytest.raises(BunkerPriceError) as e:
            load_snapshot(snap_dict(), expected_grade="MGO")
        assert "grade_mismatch" in e.value.reasons

    def test_grade_comparison_ignores_case_only(self):
        assert load_snapshot(snap_dict(fuel_grade="vlsfo"), expected_grade="VLSFO").fuel_grade == "VLSFO"

    @pytest.mark.parametrize("unit", ["USD/mt", "$/MT", "USD per metric tonne", "usd_per_metric_tonne"])
    def test_unit_synonyms_are_normalised_not_converted(self, unit):
        s = load_snapshot(snap_dict(unit=unit))
        assert s.unit == "USD_per_metric_tonne"
        assert s.observation_for("A").price_usd_per_t == 700.0       # numbers untouched

    @pytest.mark.parametrize("unit", ["USD/bbl", "USD/short ton", "EUR/mt", "", None])
    def test_unsupported_unit_is_rejected(self, unit):
        with pytest.raises(BunkerPriceError) as e:
            load_snapshot(snap_dict(unit=unit))
        assert "unsupported_unit" in e.value.reasons

    def test_other_currency_is_rejected_no_fx_is_invented(self):
        with pytest.raises(BunkerPriceError) as e:
            load_snapshot(snap_dict(currency="EUR"))
        assert "unsupported_currency" in e.value.reasons

    def test_duplicate_hub_and_missing_source_are_rejected(self):
        d = snap_dict()
        d["observations"].append(copy.deepcopy(d["observations"][0]))
        with pytest.raises(BunkerPriceError):
            load_snapshot(d)
        d = snap_dict()
        d["observations"][0]["source"] = ""
        with pytest.raises(BunkerPriceError):
            load_snapshot(d)

    def test_unknown_provenance_is_rejected(self):
        d = snap_dict()
        d["observations"][0]["provenance"] = "guessed"
        with pytest.raises(BunkerPriceError):
            load_snapshot(d)

    def test_observation_older_than_max_age_is_stale(self):
        d = snap_dict()
        d["observations"][1]["observed_on"] = "2026-09-20"            # 19 d before as_of
        with pytest.raises(BunkerPriceError) as e:
            load_snapshot(d)
        assert "stale_price" in e.value.reasons

    def test_future_observation_is_rejected(self):
        d = snap_dict()
        d["observations"][1]["observed_on"] = "2026-10-12"
        with pytest.raises(BunkerPriceError):
            load_snapshot(d)

    def test_valuation_date_beyond_max_age_is_stale_unless_allowed(self):
        s = load_snapshot(snap_dict())
        with pytest.raises(BunkerPriceError) as e:
            FuelPricing.from_snapshot(s, valuation_date="2026-11-01")
        assert "stale_price" in e.value.reasons
        assert FuelPricing.from_snapshot(s, valuation_date="2026-11-01", allow_stale=True).valuation_date == "2026-11-01"
        assert FuelPricing.from_snapshot(s, valuation_date="2026-10-23").valuation_date == "2026-10-23"  # 14 d

    def test_default_valuation_date_is_the_pinned_as_of_not_the_wall_clock(self):
        assert regional().valuation_date == "2026-10-09"

    def test_the_bundled_snapshot_is_valid_and_covers_only_worldsmall_ports(self):
        s = load_snapshot(BUNDLED, expected_grade="VLSFO")
        assert s.reference is not None and s.reference.price_usd_per_t > 0
        import csv
        with open(ROOT / "data" / "raw" / "WorldSmall" / "ports.csv", encoding="utf-8-sig") as fh:
            codes = {r["UNLocode"] for r in csv.DictReader(fh, delimiter="\t")}
        assert set(s.hubs) <= codes, f"snapshot hubs outside WorldSmall: {set(s.hubs) - codes}"
        for o in s.observations:
            assert o.source and o.source_url and o.observed_on and o.provenance == "observed"


# ================================================================== 2. resolution
class TestResolution:
    def test_cheapest_observed_port_on_the_rotation(self):
        r = regional().resolve(["B", "C", "A"])
        assert (r.price_usd_per_t, r.bunkering_port, r.basis) == (700.0, "A", BASIS_OBSERVED_PORT)
        assert r.observed_on == "2026-10-09" and r.provenance == "observed"
        assert r.observed_ports_on_rotation == (("A", 700.0), ("C", 800.0))

    def test_rotation_order_and_closing_port_do_not_matter(self):
        p = regional()
        assert p.resolve(["A", "B"]) == p.resolve(["B", "A"]) == p.resolve(["A", "B", "A"])

    def test_only_the_observed_port_present_is_used(self):
        r = regional().resolve(["B", "C"])
        assert (r.price_usd_per_t, r.bunkering_port) == (800.0, "C")

    def test_tie_goes_to_the_smallest_locode(self):
        d = snap_dict()
        d["observations"][1]["price"] = 700.0
        r = FuelPricing.from_snapshot(load_snapshot(d)).resolve(["C", "A"])
        assert r.bunkering_port == "A"

    def test_no_observed_port_uses_the_reference_and_says_so(self):
        r = regional().resolve(["B", "Z"])
        assert (r.price_usd_per_t, r.basis, r.bunkering_port) == (750.0, BASIS_REFERENCE, None)
        assert r.provenance == "observed"           # the index itself is an observation

    def test_fallback_error_fails_explicitly(self):
        with pytest.raises(BunkerPriceError) as e:
            regional(fallback=FALLBACK_ERROR).resolve(["B", "Z"])
        assert "no_observed_bunkering_port" in e.value.reasons

    def test_no_observed_port_and_no_reference_fails(self):
        d = snap_dict()
        d["reference"] = None
        p = FuelPricing.from_snapshot(load_snapshot(d))
        with pytest.raises(BunkerPriceError) as e:
            p.resolve(["B", "Z"])
        assert "missing_reference_price" in e.value.reasons
        assert p.resolve(["A", "B"]).price_usd_per_t == 700.0       # an observed port still works

    def test_reference_only_rule_ignores_observed_ports(self):
        r = regional(location_rule=RULE_REFERENCE_ONLY).resolve(["A", "B"])
        assert (r.price_usd_per_t, r.basis) == (750.0, BASIS_REFERENCE)

    def test_reference_only_needs_a_reference(self):
        d = snap_dict()
        d["reference"] = None
        with pytest.raises(BunkerPriceError):
            FuelPricing.from_snapshot(load_snapshot(d), location_rule=RULE_REFERENCE_ONLY)

    def test_unknown_rule_or_fallback_is_rejected(self):
        with pytest.raises(BunkerPriceError):
            regional(location_rule="nearest_by_geography")
        with pytest.raises(BunkerPriceError):
            regional(fallback="legacy")

    def test_legacy_mode_is_uniform_and_labelled_assumed(self):
        p = FuelPricing.legacy_uniform()
        for rot in (["A", "B"], ["B", "C"], ["Z"]):
            r = p.resolve(rot)
            assert (r.price_usd_per_t, r.basis, r.provenance) == (600.0, BASIS_LEGACY, "assumed")
        assert p.describe()["mode"] == MODE_LEGACY

    def test_describe_pins_the_snapshot(self):
        d = regional().describe()
        s = load_snapshot(snap_dict())
        assert d["mode"] == MODE_SNAPSHOT and d["sha256"] == s.sha256
        assert d["snapshot_id"] == "synthetic_test" and d["fuel_grade"] == "VLSFO"
        assert d["location_rule"] == RULE_CHEAPEST_OBSERVED and d["fallback"] == FALLBACK_REFERENCE
        assert {o["hub"] for o in d["observations"]} == {"A", "C"}
        assert d["reference"]["price_usd_per_t"] == 750.0
        assert "optimistic" in d["location_assumption"]

    def test_resolution_is_deterministic(self):
        p = regional()
        assert [p.resolve(r) for r in (["A", "C"], ["B"], ["C", "B"])] == \
               [p.resolve(r) for r in (["A", "C"], ["B"], ["C", "B"])]


# =============================================================== 3. configuration
class TestEnvironmentConfiguration:
    def test_default_is_the_legacy_assumption(self):
        assert pricing_from_environment({}) is None

    def test_uniform_override(self):
        p = pricing_from_environment({"BUNKER_UNIFORM_USD_PER_T": "720"})
        assert p.mode == MODE_LEGACY and p.uniform_usd_per_t == 720.0

    def test_regional_without_a_snapshot_is_an_error_not_legacy(self):
        with pytest.raises(BunkerPriceError) as e:
            pricing_from_environment({"BUNKER_PRICING_MODE": "regional_snapshot"})
        assert "missing_snapshot" in e.value.reasons

    def test_unknown_mode_is_an_error(self):
        with pytest.raises(BunkerPriceError):
            pricing_from_environment({"BUNKER_PRICING_MODE": "spot"})

    def test_bundled_snapshot_through_the_environment(self):
        p = pricing_from_environment({
            "BUNKER_PRICING_MODE": "regional_snapshot",
            "BUNKER_PRICE_SNAPSHOT": "data/pricing/bunker_snapshot_2026-10-09_vlsfo.json"})
        assert p.mode == MODE_SNAPSHOT and p.snapshot.fuel_grade == "VLSFO"
        assert p.resolve(["NLRTM", "SGSIN"]).bunkering_port == "NLRTM"      # 715 < 889.5

    def test_requested_grade_must_match_the_snapshot(self):
        with pytest.raises(BunkerPriceError) as e:
            pricing_from_environment({
                "BUNKER_PRICING_MODE": "regional_snapshot", "BUNKER_FUEL_GRADE": "HSFO",
                "BUNKER_PRICE_SNAPSHOT": str(BUNDLED)})
        assert "grade_mismatch" in e.value.reasons

    def test_override_stack_restores(self):
        assert active_pricing() is None
        with use_pricing(regional()):
            assert active_pricing().mode == MODE_SNAPSHOT
            with use_pricing(None):
                assert active_pricing() is None
            assert active_pricing().mode == MODE_SNAPSHOT
        assert active_pricing() is None

    def test_assumptions_for_problem_applies_the_active_pricing(self):
        pr = problem([])
        assert assumptions_for_problem(pr).fuel_pricing is None
        with use_pricing(regional()):
            a = assumptions_for_problem(pr)
            assert a.fuel_pricing is not None and a.fuel_pricing.mode == MODE_SNAPSHOT
        assert assumptions_for_problem(pr).fuel_pricing is None


# ============================================================== 4. service model
class TestServiceModelPricing:
    def test_legacy_mode_reproduces_the_baseline_fuel_calculation(self):
        base = model(["A", "B"])                                    # no pricing configured
        legacy = model(["A", "B"], FuelPricing.legacy_uniform(600.0))
        expected = TONNES_AB * 600.0
        assert base.fuel_cost_per_rotation == pytest.approx(expected)
        assert legacy.fuel_cost_per_rotation == base.fuel_cost_per_rotation
        assert base.fuel_price_basis == BASIS_LEGACY and base.fuel_price_usd_per_t == 600.0

    def test_regional_price_changes_cost_by_tonnes_times_price(self):
        m = model(["A", "B"], regional())
        assert m.fuel_tonnes_per_rotation == pytest.approx(TONNES_AB)
        assert m.fuel_price_usd_per_t == 700.0 and m.bunkering_port == "A"
        assert m.fuel_cost_per_rotation == pytest.approx(TONNES_AB * 700.0)
        bc = model(["B", "C"], regional())                          # only C is observed -> 800
        assert bc.fuel_price_usd_per_t == 800.0 and bc.bunkering_port == "C"

    def test_price_does_not_touch_the_physics(self):
        a, b, c = model(["A", "B"]), model(["A", "B"], regional()), \
            model(["A", "B"], regional(location_rule=RULE_REFERENCE_ONLY))
        for m in (b, c):
            assert m.sea_days == a.sea_days and m.port_days == a.port_days
            assert m.cycle_time_days == a.cycle_time_days
            assert m.fuel_tonnes_per_rotation == a.fuel_tonnes_per_rotation
            assert m.capacity_teu == a.capacity_teu and m.vessel_week_cost == a.vessel_week_cost
            assert m.speed_knots == a.speed_knots                   # no speed/consumption law
            assert [m.vessels(f) for f in range(4)] == [a.vessels(f) for f in range(4)]

    def test_unavailable_price_is_a_model_error_not_a_zero_cost(self):
        d = snap_dict()
        d["observations"] = [d["observations"][1]]                  # only C is observed
        only_c = FuelPricing.from_snapshot(load_snapshot(d), fallback=FALLBACK_ERROR)
        pr = problem([])
        with pytest.raises(ServiceModelError) as e:
            build_service_model("s", ["A", "B"], pr.fleet.get_class("V"), DM,
                                {p.id: p for p in pr.ports}, assumptions_with(only_c))
        assert "bunker_price_unavailable" in e.value.reasons
        assert "no_observed_bunkering_port" in e.value.reasons

    def test_pricing_is_part_of_the_hashable_assumptions(self):
        a1, a2 = assumptions_with(regional()), assumptions_with(regional())
        assert hash(a1) == hash(a2) and a1 == a2
        assert a1 != assumptions_with(regional(location_rule=RULE_REFERENCE_ONLY))


# ======================================================== 5. optimiser <-> ledger
class TestOptimiserAndLedgerShareThePrice:
    def _plan(self, pricing, **kw):
        d = [Demand("A", "B", 1500.0, 1000.0)]
        pr = problem(d)
        pl = NetworkPlanner(pr, assumptions=assumptions_with(pricing))
        return pl.plan([Candidate("s0", ("A", "B"), "V")], time_limit_sec=30, **kw)

    def test_ledger_fuel_equals_departures_x_tonnes_x_the_model_price(self):
        res = self._plan(regional())
        assert res.ok, res.message
        f = res.frequencies["s0"]
        m = res.models[0]
        assert m.fuel_price_usd_per_t == 700.0
        # the ledger recomputes tonnes itself; check it against the hand value
        assert res.ledger.fuel_cost == pytest.approx(f * TONNES_AB * 700.0)
        row = res.ledger.service_rows["s0"]
        assert row["fuel_price_usd_per_t"] == 700.0
        assert row["fuel_tonnes"] == pytest.approx(f * TONNES_AB)
        assert res.fuel_prices["s0"]["price"] == 700.0 and res.fuel_prices["s0"]["basis"] == BASIS_OBSERVED_PORT
        assert res.reconciliation["reconciled"], res.reconciliation
        assert not [v for v in res.ledger.violations if v["type"] == "fuel_price_mismatch"]

    def test_profit_moves_by_exactly_tonnes_times_the_price_change(self):
        # same frequencies, same flows: only the observed price of hub A changes
        d_hi = snap_dict()
        d_hi["observations"][0]["price"] = 760.0
        lo = self._plan(regional(), fixed_frequencies={"s0": 2})
        hi = self._plan(FuelPricing.from_snapshot(load_snapshot(d_hi)), fixed_frequencies={"s0": 2})
        assert lo.ok and hi.ok
        delta_fuel = hi.ledger.fuel_cost - lo.ledger.fuel_cost
        assert delta_fuel == pytest.approx(2 * TONNES_AB * 60.0)
        assert lo.ledger.operating_profit - hi.ledger.operating_profit == pytest.approx(delta_fuel)
        assert hi.ledger.revenue == pytest.approx(lo.ledger.revenue)
        assert hi.ledger.vessel_cost == pytest.approx(lo.ledger.vessel_cost)

    def test_legacy_plan_matches_the_pre_change_hand_value(self):
        res = self._plan(FuelPricing.legacy_uniform(600.0))
        assert res.ledger.fuel_cost == pytest.approx(2 * (TONNES_AB * 600.0))   # FUEL_AB x 2 departures
        assert res.ledger.fuel_cost == pytest.approx(2 * 94_066.6667, rel=1e-6)

    def test_ledger_flags_a_service_with_no_price(self):
        pr = problem([Demand("A", "B", 100.0, 1000.0)])
        led = compute_ledger(
            [LedgerService("s0", ("A", "B"), "V", 1)],
            [LedgerFlow(0, (("s0", "A", "B"),), 100.0)],
            pr.demands, pr.fleet, DM, {p.id: p for p in pr.ports},
            port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
            bunker_price_usd_per_t=600.0, fuel_prices={})
        assert any(v["type"] == "missing_fuel_price" for v in led.violations)
        assert not led.valid

    @pytest.mark.parametrize("bad", [None, float("nan"), -1.0, "700"])
    def test_ledger_rejects_an_invalid_price_entry(self, bad):
        pr = problem([Demand("A", "B", 100.0, 1000.0)])
        led = compute_ledger(
            [LedgerService("s0", ("A", "B"), "V", 1)], [], pr.demands, pr.fleet, DM,
            {p.id: p for p in pr.ports},
            port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
            bunker_price_usd_per_t=600.0, fuel_prices={"s0": {"price": bad}})
        assert any(v["type"] == "missing_fuel_price" for v in led.violations)

    def test_ledger_uses_the_per_service_price_not_the_uniform_one(self):
        pr = problem([Demand("A", "B", 100.0, 1000.0)])
        kw = dict(port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5)
        plb = {p.id: p for p in pr.ports}
        svc = [LedgerService("s0", ("A", "B"), "V", 1)]
        uni = compute_ledger(svc, [], pr.demands, pr.fleet, DM, plb, bunker_price_usd_per_t=600.0, **kw)
        per = compute_ledger(svc, [], pr.demands, pr.fleet, DM, plb, bunker_price_usd_per_t=600.0,
                             fuel_prices={"s0": {"price": 700.0}}, **kw)
        assert uni.fuel_cost == pytest.approx(TONNES_AB * 600.0)
        assert per.fuel_cost == pytest.approx(TONNES_AB * 700.0)

    def test_zero_frequency_service_costs_no_fuel_whatever_the_price(self):
        pr = problem([])
        led = compute_ledger(
            [LedgerService("s0", ("A", "B"), "V", 0)], [], pr.demands, pr.fleet, DM,
            {p.id: p for p in pr.ports},
            port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
            bunker_price_usd_per_t=600.0, fuel_prices={"s0": {"price": 9999.0}})
        assert led.fuel_cost == 0.0 and led.vessel_cost == 0.0

    def test_unpriced_candidate_is_rejected_by_the_planner_with_a_reason(self):
        d = snap_dict()
        d["observations"] = [d["observations"][1]]               # only C observed
        strict = FuelPricing.from_snapshot(load_snapshot(d), fallback=FALLBACK_ERROR)
        pr = problem([Demand("A", "B", 100.0, 1000.0)])
        pl = NetworkPlanner(pr, assumptions=assumptions_with(strict))
        models, rejected = pl.build_models([Candidate("s0", ("A", "B"), "V"),
                                            Candidate("s1", ("B", "C"), "V")])
        assert [m.service_id for m in models] == ["s1"]
        assert rejected[0]["service"] == "s0"
        assert "bunker_price_unavailable" in rejected[0]["reasons"]


class TestBunkeringLocationAssumptionIsPinned:
    def test_each_price_carries_its_location_assumption_and_it_changes_the_hash(self):
        d = snap_dict()
        d["observations"][0]["bunkering_location"] = "alongside at the quoted port"
        s1 = load_snapshot(d)
        assert s1.observation_for("A").bunkering_location == "alongside at the quoted port"
        d2 = copy.deepcopy(d)
        d2["observations"][0]["bunkering_location"] = "something else"
        assert load_snapshot(d2).sha256 != s1.sha256
        assert any(o["bunkering_location"] for o in regional().describe()["observations"]) is False

    def test_the_bundled_snapshot_states_a_location_for_every_price(self):
        s = load_snapshot(BUNDLED, expected_grade="VLSFO")
        assert all(o.bunkering_location for o in s.observations)
        assert s.reference.bunkering_location
        assert all(o.get("bunkering_location") for o in
                   FuelPricing.from_snapshot(s).describe()["observations"])
