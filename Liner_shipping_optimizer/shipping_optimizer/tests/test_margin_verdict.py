"""Task 14 - the 15 % profit margin is an ADVISORY verdict band.

Owner decision: a physically feasible network with independently verified positive
profit must not be rejected solely because its margin is below 15 %.  The margin is
reported as it is and classified (``at_or_above_target`` / ``below_target`` / ``loss``
/ ``undefined`` / ``unverified``); the classification never changes feasibility, the
accounting status, the solver status, a rerun decision or the selection of an
iteration.

Every expected number is computed by hand from the fixtures below, not by the code
under test.  Nothing here relaxes an existing assertion.
"""

from __future__ import annotations

import copy

import pytest

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.coordinator_agent import MARGIN_TARGET_PCT as COORDINATOR_TARGET
from src.agents.orchestrator_agent import OrchestratorAgent
from src.network.metrics import (
    MARGIN_AT_OR_ABOVE_TARGET, MARGIN_BELOW_TARGET, MARGIN_LOSS, MARGIN_TARGET_PCT,
    MARGIN_UNDEFINED, MARGIN_UNVERIFIED, canonical_network_economics, classify_margin,
    margin_verdict_label,
)
from src.pipeline.iteration_selection import IterationSelector, VALID_ITERATION_STATUS


# ---------------------------------------------------------------------------
# fixtures: a network of two regions with a given revenue and all-in cost
# ---------------------------------------------------------------------------
def _regions(revenue: float, total_cost: float):
    """Asia carries 60 % and Europe 40 % of revenue and of every cost; vessel hire is
    30 % of the all-in cost.  Coverage is the same in every fixture (20 %)."""
    out = []
    for name, share in (("Asia", 0.6), ("Europe", 0.4)):
        rev, cost = revenue * share, total_cost * share
        profit = rev - cost
        out.append({
            "region": name, "agent": f"regional_{name.lower()}", "status": "Feasible",
            "weekly_profit": profit, "operating_cost": 0.3 * cost, "fuel_cost": 0.4 * cost,
            "port_cost": 0.2 * cost, "transship_cost": 0.1 * cost, "total_cost": cost,
            "coverage_percent": 20.0, "satisfied_demand": 200.0 * share,
            "unserved_demand": 800.0 * share, "services_selected": 2,
            "profit_margin_pct": round(profit / rev * 100, 1) if rev > 0 else 0,
            "selected_services": [{"id": f"{name}_1"}, {"id": f"{name}_2"}],
        })
    return out


def _ledger(revenue: float, total_cost: float, verified: bool = True):
    profit = revenue - total_cost
    return {
        "verified": verified,
        "status": "feasible" if verified else "invalid_plan",
        "message": "" if verified else "ledger violations: fleet_exceeded",
        "weekly_usd": {
            "revenue": revenue, "vessel_cost": 0.3 * total_cost, "fuel_cost": 0.4 * total_cost,
            "port_call_fixed_cost": 0.1 * total_cost, "handling_cost": 0.1 * total_cost,
            "transshipment_cost": 0.1 * total_cost, "port_variable_cost": 0.0,
            "total_operating_cost": total_cost, "operating_profit": profit,
            "profit_margin_on_revenue": (profit / revenue) if revenue > 0 else None,
        },
    }


# (revenue, all-in cost) -> margin: 1.1M/1.0M = 9.09 %, 1.0M/0.85M = 15.0 % exactly,
# 1.5M/1.0M = 33.3 %, 0.9M/1.0M = -11.1 % (a loss)
BELOW = (1_100_000.0, 1_000_000.0)
AT = (1_000_000.0, 850_000.0)
ABOVE = (1_500_000.0, 1_000_000.0)
LOSS = (900_000.0, 1_000_000.0)


def _metrics(coord, rev_cost, **ledger_kw):
    rev, cost = rev_cost
    return coord._calculate_global_metrics(
        copy.deepcopy(_regions(rev, cost)), _ledger(rev, cost, **ledger_kw))


# ---------------------------------------------------------------------------
# 1  the classifier itself
# ---------------------------------------------------------------------------
class TestClassifier:
    def test_the_target_is_defined_once_and_is_15_percent(self):
        assert MARGIN_TARGET_PCT == 15.0
        assert COORDINATOR_TARGET is MARGIN_TARGET_PCT or COORDINATOR_TARGET == MARGIN_TARGET_PCT

    def test_below_target_is_advisory_and_keeps_the_real_margin(self):
        v = classify_margin(9.09, True)
        assert v["band"] == MARGIN_BELOW_TARGET
        assert v["margin_pct"] == pytest.approx(9.09)
        assert v["advisory"] is True and v["blocks_acceptance"] is False
        assert v["target_pct"] == 15.0

    def test_exactly_at_target_is_at_or_above(self):
        assert classify_margin(15.0, True)["band"] == MARGIN_AT_OR_ABOVE_TARGET
        assert classify_margin(14.999, True)["band"] == MARGIN_BELOW_TARGET

    def test_above_target(self):
        v = classify_margin(33.3, True)
        assert v["band"] == MARGIN_AT_OR_ABOVE_TARGET and v["margin_pct"] == pytest.approx(33.3)

    def test_a_loss_reports_the_negative_margin(self):
        v = classify_margin(-11.1, True)
        assert v["band"] == MARGIN_LOSS and v["margin_pct"] == pytest.approx(-11.1)
        assert v["blocks_acceptance"] is False

    def test_no_revenue_means_no_margin_not_zero(self):
        v = classify_margin(None, True)
        assert v["band"] == MARGIN_UNDEFINED and v["margin_pct"] is None

    @pytest.mark.parametrize("verified", [False, None])
    def test_unverified_accounting_exposes_no_margin_even_if_one_is_passed(self, verified):
        v = classify_margin(22.0, verified)
        assert v["band"] == MARGIN_UNVERIFIED and v["margin_pct"] is None

    def test_labels(self):
        lab = lambda m, ok=True, good=20.0: margin_verdict_label(classify_margin(m, ok), good)  # noqa: E731
        assert lab(15.0) == "Moderate"          # the floor is inclusive (was "Poor" at exactly 15)
        assert lab(14.9) == "Poor"
        assert lab(20.0) == "Moderate" and lab(20.1) == "Good"
        assert lab(-3.0) == "Poor"
        assert lab(None) == "Undefined"
        assert lab(30.0, ok=False) == "Not verified"


# ---------------------------------------------------------------------------
# 2  coordinator: the band is reported, never enforced
# ---------------------------------------------------------------------------
class TestCoordinator:
    def setup_method(self):
        self.coord = CoordinatorAgent()

    def test_below_target_network_keeps_feasible_verified_and_positive(self):
        m = _metrics(self.coord, BELOW)
        assert m["profit_margin_pct"] == pytest.approx(100.0 * 100_000 / 1_100_000, abs=1e-9)
        assert m["total_profit"] == pytest.approx(100_000.0) and m["total_profit"] > 0
        assert m["accounting_verified"] is True and m["accounting_status"] == "verified"
        ev = self.coord._evaluate_system(m, [])
        mv = ev["margin_verdict"]
        assert mv["band"] == MARGIN_BELOW_TARGET and mv["advisory"] and not mv["blocks_acceptance"]
        assert ev["accounting_verified"] is True          # the verdict does not touch it
        assert any("margin" in r and "advisory" in r for r in ev["reasons"])

    def test_margin_does_not_create_a_rerun_or_change_the_feedback(self):
        fb = {}
        for key, rc in (("below", BELOW), ("above", ABOVE)):
            m = _metrics(self.coord, rc)
            ev = self.coord._evaluate_system(m, [])
            fb[key] = self.coord._generate_feedback_signals([], m, ev, iteration=0)
        # same coverage / profit sign / conflicts -> the same feedback, whatever the margin
        assert fb["below"]["rerun_reason"] == fb["above"]["rerun_reason"]
        assert fb["below"]["needs_rerun"] == fb["above"]["needs_rerun"]
        assert fb["below"]["profit_gap"] == fb["above"]["profit_gap"] == 0.0
        assert "margin" not in fb["below"]["rerun_reason"]

    def test_margin_at_exactly_15_earns_the_point_like_a_higher_margin(self):
        scores = {k: self.coord._evaluate_system(_metrics(self.coord, rc), [])["score"]
                  for k, rc in (("below", BELOW), ("at", AT), ("above", ABOVE))}
        assert scores["at"] == scores["above"]
        assert scores["below"] == scores["at"] - 1            # only the advisory point
        ev_at = self.coord._evaluate_system(_metrics(self.coord, AT), [])
        assert ev_at["margin_verdict"]["band"] == MARGIN_AT_OR_ABOVE_TARGET
        assert ev_at["margin_verdict"]["margin_pct"] == pytest.approx(15.0)

    def test_loss_is_reported_with_the_real_negative_margin(self):
        m = _metrics(self.coord, LOSS)
        assert m["total_profit"] == pytest.approx(-100_000.0)
        assert m["profit_margin_pct"] == pytest.approx(-100.0 * 100_000 / 900_000, abs=1e-9)
        ev = self.coord._evaluate_system(m, [])
        assert ev["margin_verdict"]["band"] == MARGIN_LOSS
        assert ev["margin_verdict"]["margin_pct"] < 0
        assert any("profit" in r and "floor" in r for r in ev["reasons"])     # existing floor
        assert ev["accounting_verified"] is True

    def test_zero_revenue_has_no_margin_and_no_fabricated_ratio(self):
        zero = _ledger(0.0, 0.0)
        regions = [dict(r, weekly_profit=0.0, total_cost=0.0, operating_cost=0.0)
                   for r in _regions(1.0, 1.0)]
        m = self.coord._calculate_global_metrics(regions, zero)
        assert m["profit_margin_pct"] is None
        ev = self.coord._evaluate_system(m, [])
        assert ev["margin_verdict"]["band"] == MARGIN_UNDEFINED
        assert ev["margin_verdict"]["margin_pct"] is None
        assert any("unavailable" in r for r in ev["reasons"])

    def test_unverified_ledger_exposes_no_margin_or_profitability_claim(self):
        m = _metrics(self.coord, ABOVE, verified=False)
        assert m["profit_margin_pct"] is None and m["accounting_verified"] is False
        ev = self.coord._evaluate_system(m, [])
        assert ev["margin_verdict"]["band"] == MARGIN_UNVERIFIED
        assert ev["margin_verdict"]["margin_pct"] is None
        assert ev["accounting_verified"] is False

    def test_without_a_ledger_the_regional_margin_earns_no_point(self):
        rev, cost = ABOVE
        m_none = self.coord._calculate_global_metrics(copy.deepcopy(_regions(rev, cost)), None)
        assert m_none["accounting_verified"] is None
        assert m_none["profit_margin_pct"] is not None        # regional identity, unverified
        ev_none = self.coord._evaluate_system(m_none, [])
        ev_ver = self.coord._evaluate_system(_metrics(self.coord, ABOVE), [])
        assert ev_none["margin_verdict"]["band"] == MARGIN_UNVERIFIED
        assert ev_none["score"] == ev_ver["score"] - 1
        assert any("not independently verified" in r for r in ev_none["reasons"])


# ---------------------------------------------------------------------------
# 3  iteration selection: all-in economics, margin never a gate
# ---------------------------------------------------------------------------
def _it(i, *, profit, total, hire=100_000.0, cov=20.0, verified=True, margin="derive"):
    """An iteration snapshot.  ``margin='derive'`` = profit / (profit + total)."""
    if margin == "derive":
        margin = 100.0 * profit / (profit + total)
    metrics = {"weekly_profit": profit, "annual_profit": profit * 52, "operating_cost": hire,
               "total_cost": total, "global_demand_weighted_coverage": cov,
               "average_regional_coverage": cov, "unserved_demand": 100.0,
               "services_deployed": 2, "profit_margin_pct": margin,
               "accounting_verified": verified}
    it = {"iteration": i, "status": VALID_ITERATION_STATUS, "metrics": metrics,
          "regional_results": [{"region": "Asia", "weekly_profit": profit}],
          "selected_services": [{"id": f"s{i}"}], "weights_used": {}}
    if verified is not None:
        it["network_ledger"] = {"verified": verified}
    return it


class TestIterationSelection:
    def test_a_single_below_target_iteration_is_selected_not_rejected(self):
        only = _it(0, profit=100_000.0, total=1_000_000.0)             # 9.1 %
        res = IterationSelector().select([only], llm_callable=None)
        assert res["selected_iteration"] == 0
        card = res["scorecards"][0]
        assert card["selection_status"] == "candidate"
        assert card["margin_verdict"]["band"] == MARGIN_BELOW_TARGET
        assert card["margin_verdict"]["blocks_acceptance"] is False

    def test_higher_profit_wins_even_with_the_lower_margin(self):
        a = _it(0, profit=1_000_000.0, total=5_000_000.0)              # 16.7 %
        b = _it(1, profit=2_000_000.0, total=20_000_000.0)             # 9.1 %  (< 15 %)
        res = IterationSelector().select([a, b], llm_callable=None)
        assert res["selected_iteration"] == 1
        cards = {c["iteration"]: c for c in res["scorecards"]}
        assert cards[1]["margin_verdict"]["band"] == MARGIN_BELOW_TARGET
        assert cards[0]["margin_verdict"]["band"] == MARGIN_AT_OR_ABOVE_TARGET
        assert cards[1]["selection_status"] == "candidate"

    def test_selection_uses_all_in_cost_not_vessel_hire(self):
        # same profit and coverage; B has the HIGHER hire but the LOWER all-in cost and
        # the better margin.  A hire-only comparison would select A.
        a = _it(0, profit=1_000_000.0, total=5_000_000.0, hire=100_000.0)      # 16.7 %
        b = _it(1, profit=1_000_000.0, total=4_000_000.0, hire=300_000.0)      # 20.0 %
        res = IterationSelector().select([a, b], llm_callable=None)
        assert res["selected_iteration"] == 1
        cards = {c["iteration"]: c for c in res["scorecards"]}
        assert cards[1]["cost_rank"] == 1 and cards[0]["cost_rank"] == 2
        assert cards[1]["margin_rank"] == 1 and cards[0]["margin_rank"] == 2

    def test_undefined_margin_stays_none_on_the_scorecard(self):
        it = _it(0, profit=0.0, total=0.0, margin=None)
        card = IterationSelector().build_scorecards([it])[0]
        assert card["profit_margin_pct"] is None            # not a fabricated 0.0
        assert card["margin_verdict"]["band"] == MARGIN_UNDEFINED
        assert card["margin_verdict"]["margin_pct"] is None

    def test_unverified_iteration_exposes_no_verified_margin(self):
        it = _it(0, profit=1_000_000.0, total=5_000_000.0, verified=False, margin=None)
        card = IterationSelector().build_scorecards([it])[0]
        assert card["accounting_verified"] is False
        assert card["margin_verdict"]["band"] == MARGIN_UNVERIFIED
        assert card["profit_margin_pct"] is None

    def test_a_real_margin_beats_an_undefined_one_on_the_tie_break(self):
        # identical profit / coverage / cost: only the margin tie-break separates them
        a = _it(0, profit=500_000.0, total=2_000_000.0, margin=None)
        b = _it(1, profit=500_000.0, total=2_000_000.0, margin=0.0)
        res = IterationSelector().select([a, b], llm_callable=None)
        assert res["selected_iteration"] == 1

    def test_llm_prompt_is_built_with_an_undefined_margin(self):
        a = _it(0, profit=500_000.0, total=2_000_000.0, margin=None)
        b = _it(1, profit=400_000.0, total=1_000_000.0)
        sel = IterationSelector()
        cards = sel.build_scorecards([a, b])
        prompt = sel._build_llm_prompt(cards, [a, b], [0, 1])
        assert "n/a (undefined or not verified)" in prompt
        assert "advisory band: below_target" in prompt or "advisory band: at_or_above_target" in prompt


# ---------------------------------------------------------------------------
# 4  orchestrator report writers
# ---------------------------------------------------------------------------
class TestReportWriters:
    def _report(self, rc, **kw):
        rev, cost = rc
        return OrchestratorAgent._margin_report(_regions(rev, cost), _ledger(rev, cost, **kw))

    def test_below_target_is_labelled_poor_and_says_it_is_advisory(self):
        r = self._report(BELOW)
        assert r["label"] == "Poor" and r["margin_text"] == "9.1%"
        line = r["advisory_line"].lower()
        assert "advisory" in line and "unchanged" in line
        # the summary test forbids vague wording; the advisory line must not use any
        for vague in ("consider", "explore", "may ", "could potentially", "perhaps"):
            assert vague not in line

    def test_at_target_and_above(self):
        assert self._report(AT)["label"] == "Moderate"
        assert self._report(AT)["advisory_line"] == ""
        assert self._report(ABOVE)["label"] == "Good"
        assert self._report(ABOVE)["margin_text"] == "33.3%"

    def test_loss(self):
        r = self._report(LOSS)
        assert r["label"] == "Poor" and r["margin_text"] == "-11.1%"
        assert r["advisory_line"] != ""

    def test_unverified_is_not_labelled_good_or_poor(self):
        r = self._report(ABOVE, verified=False)
        assert r["label"] == "Not verified"
        assert r["margin_text"] == "n/a (not verified)" and r["advisory_line"] == ""

    def test_zero_revenue_is_undefined(self):
        regions = [dict(r, weekly_profit=0.0, total_cost=0.0, operating_cost=0.0)
                   for r in _regions(1.0, 1.0)]
        r = OrchestratorAgent._margin_report(regions, _ledger(0.0, 0.0))
        assert r["label"] == "Undefined" and r["margin_text"] == "n/a (undefined)"

    def test_regional_explanation_boundaries(self):
        def verdict(margin, profit=100.0, cost=900.0):
            r = {"profit_margin_pct": margin, "coverage_percent": 20.0, "weekly_profit": profit,
                 "total_cost": cost, "services_selected": 2, "satisfied_demand": 10.0,
                 "unserved_demand": 40.0, "transship_cost": 0.0, "port_cost": 0.0}
            return OrchestratorAgent._rule_based_explanation(r).splitlines()[0]
        assert verdict(15.0) == "Verdict: Moderate"       # inclusive floor
        assert verdict(14.9) == "Verdict: Poor"
        assert verdict(25.0) == "Verdict: Moderate" and verdict(25.1) == "Verdict: Good"
        assert verdict(0, profit=0.0, cost=0.0) == "Verdict: Undefined"
