"""Characterise the margin-verdict behaviour of a source tree (before/after Task 14).

usage:  cd <tree root> && python -I characterize_margin.py <out.json>

Uses only APIs that exist in BOTH the Tasks 8-10 baseline and the Task 14 tree, so the same
file can be run against each and the outputs compared.  Fixtures are the hand-computed
ones of ``tests/test_margin_verdict.py`` (revenue / all-in cost): 9.1 %, exactly 15 %,
33.3 %, a loss, zero revenue and an unverified ledger.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from src.agents.coordinator_agent import CoordinatorAgent                    # noqa: E402
from src.agents.orchestrator_agent import OrchestratorAgent                  # noqa: E402
from src.pipeline.iteration_selection import IterationSelector, VALID_ITERATION_STATUS  # noqa: E402


def regions(revenue, total_cost):
    out = []
    for name, share in (("Asia", 0.6), ("Europe", 0.4)):
        rev, cost = revenue * share, total_cost * share
        out.append({
            "region": name, "status": "Feasible", "weekly_profit": rev - cost,
            "operating_cost": 0.3 * cost, "total_cost": cost, "coverage_percent": 20.0,
            "satisfied_demand": 200.0 * share, "unserved_demand": 800.0 * share,
            "services_selected": 2,
            "profit_margin_pct": round((rev - cost) / rev * 100, 1) if rev > 0 else 0,
            "selected_services": [{"id": f"{name}_1"}],
        })
    return out


def ledger(revenue, total_cost, verified=True):
    return {"verified": verified, "status": "feasible" if verified else "invalid_plan",
            "message": "", "weekly_usd": {
                "revenue": revenue, "vessel_cost": 0.3 * total_cost,
                "total_operating_cost": total_cost, "operating_profit": revenue - total_cost,
                "profit_margin_on_revenue": (revenue - total_cost) / revenue if revenue > 0 else None}}


CASES = {
    "below_15 (9.09 %)": (1_100_000.0, 1_000_000.0, True),
    "exactly_15": (1_000_000.0, 850_000.0, True),
    "above_15 (33.3 %)": (1_500_000.0, 1_000_000.0, True),
    "loss (-11.1 %)": (900_000.0, 1_000_000.0, True),
    "zero_revenue": (0.0, 0.0, True),
    "unverified_ledger": (1_500_000.0, 1_000_000.0, False),
}

coord = CoordinatorAgent()
result = {"coordinator": {}, "selector": {}, "regional_explanation": {}}
for name, (rev, cost, ok) in CASES.items():
    regs = copy.deepcopy(regions(rev, cost))
    if rev == 0.0:
        regs = [dict(r, weekly_profit=0.0, total_cost=0.0, operating_cost=0.0) for r in regs]
    m = coord._calculate_global_metrics(regs, ledger(rev, cost, ok))
    ev = coord._evaluate_system(m, [])
    fb = coord._generate_feedback_signals([], m, ev, 0)
    result["coordinator"][name] = {
        "profit": m["total_profit"], "margin_pct": m["profit_margin_pct"],
        "accounting_verified": m["accounting_verified"],
        "score": ev["score"], "status": ev["status"], "reasons": ev["reasons"],
        "margin_verdict": ev.get("margin_verdict"),
        "needs_rerun": fb["needs_rerun"], "rerun_reason": fb["rerun_reason"],
    }

# iteration selector: an undefined margin and the LLM prompt
def it(i, profit, total, margin):
    return {"iteration": i, "status": VALID_ITERATION_STATUS,
            "metrics": {"weekly_profit": profit, "annual_profit": profit * 52,
                        "operating_cost": 1e5, "total_cost": total,
                        "global_demand_weighted_coverage": 20.0, "average_regional_coverage": 20.0,
                        "unserved_demand": 100.0, "services_deployed": 2,
                        "profit_margin_pct": margin},
            "regional_results": [{"region": "Asia", "weekly_profit": profit}],
            "selected_services": [{"id": f"s{i}"}], "weights_used": {},
            "network_ledger": {"verified": True}}

sel = IterationSelector()
a, b = it(0, 500_000.0, 2_000_000.0, None), it(1, 500_000.0, 2_000_000.0, 0.0)
cards = sel.build_scorecards([a, b])
result["selector"]["scorecard_margin_of_undefined_iteration"] = cards[0]["profit_margin_pct"]
result["selector"]["selected_when_margins_are_None_vs_0.0"] = sel.select([a, b])["selected_iteration"]
try:
    prompt = sel._build_llm_prompt(cards, [a, b], [0, 1])
    result["selector"]["prompt_margin_line"] = [l for l in prompt.splitlines() if "Profit margin" in l]
except Exception as exc:                                         # noqa: BLE001
    result["selector"]["prompt_margin_line"] = f"{type(exc).__name__}: {exc}"

for margin, profit, cost in ((15.0, 100.0, 900.0), (14.9, 100.0, 900.0), (25.0, 100.0, 900.0),
                             (0, 0.0, 0.0)):
    r = {"profit_margin_pct": margin, "coverage_percent": 20.0, "weekly_profit": profit,
         "total_cost": cost, "services_selected": 2, "satisfied_demand": 10.0,
         "unserved_demand": 40.0, "transship_cost": 0.0, "port_cost": 0.0}
    text = OrchestratorAgent._rule_based_explanation(r).splitlines()
    result["regional_explanation"][f"margin={margin} profit={profit}"] = text[:2]

json.dump(result, open(sys.argv[1], "w", encoding="utf-8"), indent=1, sort_keys=True, default=str)
print("written", sys.argv[1])
