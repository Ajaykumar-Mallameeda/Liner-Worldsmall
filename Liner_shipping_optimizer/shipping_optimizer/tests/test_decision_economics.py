"""Task 8A (F-15) - the decision layer reports and compares the canonical economics.

What was wrong: ``decision_output.global_metrics.total_cost`` was the vessel-hire
component only, so ``profit_margin_pct`` (profit / (profit + hire)) read ~26 % while
the ledger margin on revenue was ~11 %; iteration selection ranked on the same
hire-only number.

Every expected value below is computed by hand from the fixture, not by the code
under test.  Nothing here relaxes an existing assertion.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.agents.coordinator_agent import CoordinatorAgent, MARGIN_TARGET_PCT
from src.agents.orchestrator_agent import OrchestratorAgent
from src.network.metrics import (
    STATUS_NOT_EVALUATED, STATUS_UNVERIFIED, STATUS_VERIFIED,
    canonical_network_economics,
)
from src.pipeline.iteration_selection import (
    IterationSelector, PARETO_OBJECTIVES, VALID_ITERATION_STATUS,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# fixture: two regions shaped exactly like the global stage's region updates
# ---------------------------------------------------------------------------
def _region(name, revenue, hire, fuel, port, handling, transship, *, served, demand):
    total_cost = hire + fuel + port + handling + transship
    profit = revenue - total_cost
    return {
        "region": name, "agent": f"regional_{name.lower()}", "status": "Feasible",
        "weekly_profit": profit, "operating_cost": hire, "fuel_cost": fuel,
        "port_cost": port + handling, "transship_cost": transship,
        "total_cost": total_cost, "coverage_percent": served / demand * 100,
        "satisfied_demand": served, "unserved_demand": demand - served,
        "services_selected": 2,
        "selected_services": [{"id": f"{name}_1"}, {"id": f"{name}_2"}],
    }


# Asia: revenue 1,000,000; hire 200,000 fuel 300,000 port 50,000 handling 100,000 transship 20,000
# Europe: revenue 500,000;  hire 100,000 fuel 150,000 port 30,000 handling 40,000  transship 10,000
ASIA = _region("Asia", 1_000_000, 200_000, 300_000, 50_000, 100_000, 20_000, served=800, demand=4000)
EUROPE = _region("Europe", 500_000, 100_000, 150_000, 30_000, 40_000, 10_000, served=300, demand=2000)
REGIONS = [ASIA, EUROPE]

REVENUE = 1_500_000.0
HIRE = 300_000.0
TOTAL_COST = (200_000 + 300_000 + 50_000 + 100_000 + 20_000) \
    + (100_000 + 150_000 + 30_000 + 40_000 + 10_000)          # 670,000 + 330,000 = 1,000,000
PROFIT = REVENUE - TOTAL_COST                                   # 500,000
MARGIN_PCT = 100.0 * PROFIT / REVENUE                           # 33.333...


def _ledger(verified=True, **over):
    wk = {
        "revenue": REVENUE, "vessel_cost": HIRE, "fuel_cost": 450_000.0,
        "port_call_fixed_cost": 80_000.0, "handling_cost": 140_000.0,
        "transshipment_cost": 30_000.0, "port_variable_cost": 0.0,
        "total_operating_cost": float(TOTAL_COST), "operating_profit": float(PROFIT),
        "profit_margin_on_revenue": PROFIT / REVENUE,
    }
    wk.update(over)
    return {"verified": verified, "status": "feasible" if verified else "invalid_plan",
            "message": "" if verified else "ledger violations: fleet_exceeded",
            "weekly_usd": wk}


def test_fixture_arithmetic_is_what_the_comments_say():
    assert TOTAL_COST == 1_000_000 and PROFIT == 500_000
    assert ASIA["total_cost"] == 670_000 and EUROPE["total_cost"] == 330_000


# ---------------------------------------------------------------------------
# 1-3  definitions
# ---------------------------------------------------------------------------
class TestCanonicalDefinitions:
    def test_total_cost_is_the_sum_of_all_cost_categories_not_vessel_hire(self):
        e = canonical_network_economics(REGIONS, _ledger())
        assert e["total_cost"] == pytest.approx(1_000_000.0)
        assert e["vessel_hire_cost"] == pytest.approx(300_000.0)
        assert e["total_cost"] > e["vessel_hire_cost"]

    def test_profit_equals_revenue_minus_total_cost_and_has_no_penalty(self):
        e = canonical_network_economics(REGIONS, _ledger())
        assert e["revenue"] == pytest.approx(1_500_000.0)
        assert e["profit"] == pytest.approx(e["revenue"] - e["total_cost"])
        # unserved demand (4,900 TEU in the fixture) is not part of the profit
        assert e["profit"] == pytest.approx(500_000.0)

    def test_margin_is_profit_over_revenue(self):
        e = canonical_network_economics(REGIONS, _ledger())
        assert e["profit_margin_pct"] == pytest.approx(MARGIN_PCT, abs=1e-6)
        # ... and NOT the vessel-hire-only ratio the defect produced
        hire_only = 100.0 * PROFIT / (PROFIT + HIRE)
        assert abs(e["profit_margin_pct"] - hire_only) > 10.0

    def test_zero_revenue_has_no_margin(self):
        zero = _ledger(revenue=0.0, total_operating_cost=0.0, operating_profit=0.0,
                       vessel_cost=0.0, profit_margin_on_revenue=None)
        regions = [dict(r, weekly_profit=0.0, total_cost=0.0, operating_cost=0.0) for r in REGIONS]
        e = canonical_network_economics(regions, zero)
        assert e["profit_margin_pct"] is None


# ---------------------------------------------------------------------------
# 5  invalid / unverified accounting is never presented as verified
# ---------------------------------------------------------------------------
class TestUnverifiedAccounting:
    def test_verified_ledger_is_reported_as_verified(self):
        e = canonical_network_economics(REGIONS, _ledger())
        assert e["accounting_status"] == STATUS_VERIFIED
        assert e["accounting_verified"] is True
        assert e["accounting_basis"] == "network_ledger"

    def test_unverified_ledger_has_no_margin_and_says_why(self):
        e = canonical_network_economics(REGIONS, _ledger(verified=False))
        assert e["accounting_status"] == STATUS_UNVERIFIED
        assert e["accounting_verified"] is False
        assert e["profit_margin_pct"] is None
        assert e["revenue"] is None
        assert any("not verified" in i for i in e["accounting_issues"])

    def test_ledger_that_disagrees_with_the_regional_partition_is_not_verified(self):
        bad = _ledger(operating_profit=PROFIT + 12_345.0,
                      total_operating_cost=float(TOTAL_COST - 12_345.0))
        e = canonical_network_economics(REGIONS, bad)
        # identity revenue - cost == profit still holds here, but the regional
        # partition no longer sums to the ledger
        assert e["accounting_status"] == STATUS_UNVERIFIED
        assert e["profit_margin_pct"] is None
        assert any("regional" in i for i in e["accounting_issues"])

    def test_broken_ledger_identity_is_not_verified(self):
        bad = _ledger(operating_profit=PROFIT + 1_000.0)
        e = canonical_network_economics(REGIONS, bad)
        assert e["accounting_verified"] is False

    def test_missing_ledger_is_not_evaluated_never_verified(self):
        e = canonical_network_economics(REGIONS, None)
        assert e["accounting_status"] == STATUS_NOT_EVALUATED
        assert e["accounting_verified"] is None

    def test_region_without_total_cost_is_not_silently_zero(self):
        broken = [ASIA, {"region": "Africa", "status": "failed", "weekly_profit": 0.0,
                         "operating_cost": 0.0}]
        e = canonical_network_economics(broken, None)
        assert e["total_cost"] is None and e["profit_margin_pct"] is None
        assert any("Africa" in i for i in e["accounting_issues"])


# ---------------------------------------------------------------------------
# 4  coordinator evaluation consumes the corrected metrics
# ---------------------------------------------------------------------------
class TestCoordinator:
    def setup_method(self):
        self.coord = CoordinatorAgent()

    def test_global_metrics_carry_the_canonical_figures(self):
        m = self.coord._calculate_global_metrics(copy.deepcopy(REGIONS), _ledger())
        assert m["total_cost"] == pytest.approx(1_000_000.0)
        assert m["vessel_hire_cost"] == pytest.approx(300_000.0)
        assert m["revenue"] == pytest.approx(1_500_000.0)
        assert m["total_profit"] == pytest.approx(500_000.0)
        assert m["profit_margin_pct"] == pytest.approx(MARGIN_PCT, abs=1e-6)
        assert m["accounting_verified"] is True
        # identity inside the one dict
        assert m["total_profit"] == pytest.approx(m["revenue"] - m["total_cost"])

    def test_evaluation_awards_the_margin_point_only_on_the_all_in_margin(self):
        m = self.coord._calculate_global_metrics(copy.deepcopy(REGIONS), _ledger())
        ev = self.coord._evaluate_system(m, [])
        assert MARGIN_TARGET_PCT < MARGIN_PCT                       # 33 % clears 15 %
        assert not any("margin" in r for r in ev["reasons"])

        low = _ledger(revenue=1_100_000.0, operating_profit=100_000.0,
                      profit_margin_on_revenue=100_000.0 / 1_100_000.0)
        regions = copy.deepcopy(REGIONS)
        regions[0]["weekly_profit"] -= 400_000.0                     # partition must still add up
        low_regions = copy.deepcopy(regions)
        m2 = self.coord._calculate_global_metrics(low_regions, low)
        ev2 = self.coord._evaluate_system(m2, [])
        assert m2["profit_margin_pct"] == pytest.approx(100.0 * 100_000 / 1_100_000, abs=1e-6)
        assert any("margin" in r for r in ev2["reasons"])            # 9.1 % < 15 %

    def test_unverified_accounting_cannot_earn_the_margin_point(self):
        m = self.coord._calculate_global_metrics(copy.deepcopy(REGIONS), _ledger(verified=False))
        assert m["profit_margin_pct"] is None and m["accounting_verified"] is False
        ev = self.coord._evaluate_system(m, [])
        assert ev["accounting_verified"] is False
        assert any("unavailable" in r for r in ev["reasons"])

    def test_decision_prompt_formats_without_a_margin(self):
        m = self.coord._calculate_global_metrics(copy.deepcopy(REGIONS), _ledger(verified=False))
        ev = self.coord._evaluate_system(m, [])
        seen = {}

        def fake_llm(prompt, temperature=0.1):          # no network: rule-based fallback
            seen["prompt"] = prompt
            return ""

        self.coord.call_llm = fake_llm
        out = self.coord._generate_decisions([], copy.deepcopy(REGIONS), m, ev, iteration=0)
        assert "weight_adjustments" in out
        assert "n/a (not verified)" in seen["prompt"]            # not a fabricated margin
        assert "all-in" in seen["prompt"]

    def test_decision_prompt_quotes_the_all_in_cost_and_margin(self):
        m = self.coord._calculate_global_metrics(copy.deepcopy(REGIONS), _ledger())
        ev = self.coord._evaluate_system(m, [])
        seen = {}
        self.coord.call_llm = lambda prompt, temperature=0.1: seen.setdefault("p", prompt) and ""
        self.coord._generate_decisions([], copy.deepcopy(REGIONS), m, ev, iteration=0)
        assert "$1,000,000/week" in seen["p"]                     # all-in cost
        assert "$300,000/week" in seen["p"]                       # hire component, labelled
        assert "33.3%" in seen["p"]


# ---------------------------------------------------------------------------
# iteration snapshot + selection
# ---------------------------------------------------------------------------
def _decision_stub():
    return {"global_metrics": {"global_demand_weighted_coverage": 10.0}}


class TestSnapshotAndSelection:
    def test_snapshot_metrics_use_the_canonical_economics(self):
        snap = OrchestratorAgent._build_iteration_snapshot(
            None, 0, {}, copy.deepcopy(REGIONS), _decision_stub(), {}, {}, {},
            [{"id": "s"}], network_ledger=_ledger())
        m = snap["metrics"]
        assert m["total_cost"] == pytest.approx(1_000_000.0)
        assert m["operating_cost"] == pytest.approx(300_000.0)     # component, unchanged meaning
        assert m["vessel_hire_cost"] == pytest.approx(300_000.0)
        assert m["revenue"] == pytest.approx(1_500_000.0)
        assert m["profit_margin_pct"] == pytest.approx(MARGIN_PCT, abs=1e-6)
        assert m["weekly_profit"] == pytest.approx(500_000.0)

    def test_cost_objective_is_total_cost(self):
        assert "total_cost" in PARETO_OBJECTIVES and "operating_cost" not in PARETO_OBJECTIVES

    @staticmethod
    def _it(i, *, profit, hire, total, cov=10.0, verified=None, drop_total=False):
        metrics = {"weekly_profit": profit, "annual_profit": profit * 52,
                   "operating_cost": hire, "total_cost": total,
                   "global_demand_weighted_coverage": cov, "average_regional_coverage": cov,
                   "unserved_demand": 100.0, "services_deployed": 2,
                   "profit_margin_pct": 100.0 * profit / (profit + total)}
        if drop_total:
            metrics.pop("total_cost")
        it = {"iteration": i, "status": VALID_ITERATION_STATUS, "metrics": metrics,
              "regional_results": [{"region": "Asia", "weekly_profit": profit}],
              "selected_services": [{"id": f"s{i}"}], "weights_used": {}}
        if verified is not None:
            it["network_ledger"] = {"verified": verified}
        return it

    def test_selection_prefers_lower_all_in_cost_even_when_hire_says_otherwise(self):
        # same profit and coverage; iteration 1 has the HIGHER hire but the LOWER
        # all-in cost.  A hire-only comparison would pick iteration 0.
        a = self._it(0, profit=1_000_000, hire=100_000, total=5_000_000)
        b = self._it(1, profit=1_000_000, hire=300_000, total=4_000_000)
        res = IterationSelector().select([a, b], llm_callable=None)
        assert res["selected_iteration"] == 1
        cards = {c["iteration"]: c for c in res["scorecards"]}
        assert cards[1]["cost_rank"] == 1 and cards[0]["cost_rank"] == 2

    def test_missing_total_cost_makes_the_iteration_invalid_not_free(self):
        good = self._it(0, profit=1_000_000, hire=100_000, total=5_000_000)
        nocost = self._it(1, profit=1_200_000, hire=100_000, total=1.0, drop_total=True)
        res = IterationSelector().select([good, nocost], llm_callable=None)
        assert res["selected_iteration"] == 0
        card = next(c for c in res["scorecards"] if c["iteration"] == 1)
        assert card["selection_status"] == "invalid"
        assert card["invalid_reason"] == "missing_total_cost"

    def test_unverified_iteration_cannot_beat_a_verified_one(self):
        verified = self._it(0, profit=1_000_000, hire=100_000, total=5_000_000, verified=True)
        unverified = self._it(1, profit=9_000_000, hire=100_000, total=1_000_000, verified=False)
        res = IterationSelector().select([verified, unverified], llm_callable=None)
        assert res["selected_iteration"] == 0
        card = next(c for c in res["scorecards"] if c["iteration"] == 1)
        assert card["selection_status"] == "unverified_accounting"

    def test_when_nothing_is_verified_everything_stays_eligible(self):
        a = self._it(0, profit=1_000_000, hire=100_000, total=5_000_000, verified=False)
        b = self._it(1, profit=2_000_000, hire=100_000, total=5_000_000, verified=False)
        res = IterationSelector().select([a, b], llm_callable=None)
        assert res["selected_iteration"] == 1          # best of the (all unverified) set
        assert sorted(res["candidate_iterations"]) == [0, 1]


# ---------------------------------------------------------------------------
# 6  the artifact does not present contradictory values (skips if none present)
# ---------------------------------------------------------------------------
def _artifact():
    p = ROOT / "pipeline_output.json"
    if not p.exists():
        pytest.skip("pipeline_output.json not present")
    return json.loads(p.read_text(encoding="utf-8"))


class TestArtifactIsSelfConsistent:
    def test_every_cost_and_margin_in_the_artifact_agrees(self):
        out = _artifact()
        gm = out["decision_output"]["global_metrics"]
        sm = out["summary_metrics"]
        led = out["network_ledger"]
        if not led.get("verified"):
            pytest.skip("artifact is not a verified run")
        wk = led["weekly_usd"]
        assert gm["total_cost"] == pytest.approx(sm["total_cost"], abs=1.0)
        assert gm["total_cost"] == pytest.approx(wk["total_operating_cost"], abs=1.0)
        assert gm["revenue"] == pytest.approx(wk["revenue"], abs=1.0)
        assert gm["total_profit"] == pytest.approx(wk["operating_profit"], abs=1.0)
        assert gm["total_profit"] == pytest.approx(gm["revenue"] - gm["total_cost"], abs=1.0)
        assert gm["profit_margin_pct"] == pytest.approx(100.0 * wk["profit_margin_on_revenue"], abs=1e-3)
        assert gm["vessel_hire_cost"] == pytest.approx(sm["operating_cost"], abs=1.0)
        assert gm["accounting_verified"] is True

    def test_selected_iteration_snapshot_uses_the_same_economics(self):
        out = _artifact()
        led = out["network_ledger"]
        if not led.get("verified"):
            pytest.skip("artifact is not a verified run")
        sel = next(it for it in out["iteration_results"]
                   if it["iteration"] == out["best_iteration"])
        m = sel["metrics"]
        wk = led["weekly_usd"]
        assert m["total_cost"] == pytest.approx(wk["total_operating_cost"], abs=1.0)
        assert m["profit_margin_pct"] == pytest.approx(100.0 * wk["profit_margin_on_revenue"], abs=1e-3)
        assert m["operating_cost"] == pytest.approx(wk["vessel_cost"], abs=1.0)

    def test_status_complete_only_with_verified_ledger(self):
        out = _artifact()
        assert (out["status"] == "complete") == bool(out["network_ledger"].get("verified"))
