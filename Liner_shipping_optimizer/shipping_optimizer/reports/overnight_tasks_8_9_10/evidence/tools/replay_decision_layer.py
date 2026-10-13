"""Task 8A evidence: replay ONE captured pipeline artifact through the decision layer.

The routes, candidates, ledger and regional numbers are taken from a captured
``pipeline_output.json`` (U7, M0, ...) and are NOT recomputed, so any difference
between the old and the new decision layer is caused by the metric definition
alone - not by a different plan.

usage:
    python -I replay_decision_layer.py <tree_with_src> <pipeline_output.json> <label> <out.json>

Run it once with ``tree_with_src`` = the frozen baseline snapshot (old code) and once
with the modified tree (new code); both print one JSON object.  ``compare`` mode
merges two such outputs:

    python -I replay_decision_layer.py --compare old.json new.json
"""
import json
import sys
from pathlib import Path


def _replay(tree: Path, artifact: Path, label: str) -> dict:
    sys.path.insert(0, str(tree))
    from src.agents.coordinator_agent import CoordinatorAgent          # noqa: E402
    from src.pipeline.iteration_selection import IterationSelector     # noqa: E402

    out = json.loads(artifact.read_text(encoding="utf-8"))
    coord = CoordinatorAgent()
    led_final = out.get("network_ledger") or {}
    result = {"label": label, "tree": str(tree), "artifact": str(artifact),
              "artifact_best_iteration": out.get("best_iteration"),
              "iterations": []}

    snapshots = []
    for it in out.get("iteration_results", []):
        regional = it.get("regional_results") or []
        ledger = it.get("network_ledger")
        # old coordinator: no ledger parameter; new coordinator: ledger of the iteration
        try:
            gm = coord._calculate_global_metrics(json.loads(json.dumps(regional)), ledger)
        except TypeError:
            gm = coord._calculate_global_metrics(json.loads(json.dumps(regional)))
        ev = coord._evaluate_system(gm, [])
        wk = (ledger or {}).get("weekly_usd") or {}
        result["iterations"].append({
            "iteration": it.get("iteration"),
            "global_metrics": {k: gm.get(k) for k in (
                "total_profit", "total_cost", "vessel_hire_cost", "revenue",
                "profit_margin_pct", "accounting_status", "accounting_verified")},
            "evaluation": {"score": ev["score"], "status": ev["status"], "reasons": ev["reasons"]},
            "ledger": {k: wk.get(k) for k in (
                "revenue", "vessel_cost", "total_operating_cost", "operating_profit",
                "profit_margin_on_revenue")},
            "ledger_verified": (ledger or {}).get("verified"),
        })
        # snapshot as the code under test would build it: keep stored metrics, but
        # let the replayed coordinator economics override what it owns.
        m = dict(it.get("metrics") or {})
        if "vessel_hire_cost" in gm:                # new code
            m.update({k: gm[k] for k in ("total_cost", "revenue", "profit_margin_pct",
                                         "vessel_hire_cost", "accounting_verified",
                                         "accounting_status") if k in gm})
            m["operating_cost"] = gm["vessel_hire_cost"]
        snap = dict(it)
        snap["metrics"] = m
        snapshots.append(snap)

    sel = IterationSelector().select(json.loads(json.dumps(snapshots)), llm_callable=None)
    result["selection"] = {
        "selected_iteration": sel.get("selected_iteration"),
        "pareto_optimal_iterations": sel.get("pareto_optimal_iterations"),
        "candidate_iterations": sel.get("candidate_iterations"),
        "cost_ranks": {c["iteration"]: c.get("cost_rank") for c in sel.get("scorecards", [])},
        "scores": {c["iteration"]: c.get("overall_candidate_score") for c in sel.get("scorecards", [])},
    }
    result["final_ledger_margin_pct"] = (
        100.0 * led_final["weekly_usd"]["profit_margin_on_revenue"]
        if (led_final.get("weekly_usd") or {}).get("profit_margin_on_revenue") is not None else None)
    return result


def _compare(old_p: Path, new_p: Path) -> str:
    old, new = json.loads(old_p.read_text()), json.loads(new_p.read_text())
    lines = [f"# Decision-layer replay: {old['label']}",
             f"artifact: `{old['artifact']}`",
             f"old tree: `{old['tree']}`  \nnew tree: `{new['tree']}`", "",
             "| iter | profit | ledger margin % | OLD total_cost | NEW total_cost | OLD margin % | NEW margin % | OLD eval | NEW eval |",
             "|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for o, n in zip(old["iterations"], new["iterations"]):
        og, ng = o["global_metrics"], n["global_metrics"]
        lm = o["ledger"].get("profit_margin_on_revenue")
        fmt = lambda v, f="{:,.0f}": ("n/a" if v is None else f.format(v))
        lines.append(
            f"| {o['iteration']} | {fmt(og['total_profit'])} | {fmt(None if lm is None else 100*lm, '{:.2f}')} "
            f"| {fmt(og['total_cost'])} | {fmt(ng['total_cost'])} "
            f"| {fmt(og['profit_margin_pct'], '{:.2f}')} | {fmt(ng['profit_margin_pct'], '{:.2f}')} "
            f"| {o['evaluation']['score']}/5 {o['evaluation']['status']} "
            f"| {n['evaluation']['score']}/5 {n['evaluation']['status']} |")
    lines += ["", f"selected iteration: artifact={old['artifact_best_iteration']}  "
                  f"old selector={old['selection']['selected_iteration']}  "
                  f"new selector={new['selection']['selected_iteration']}",
              f"pareto set: old={old['selection']['pareto_optimal_iterations']} "
              f"new={new['selection']['pareto_optimal_iterations']}",
              f"cost ranks (1 = cheapest): old(hire)={old['selection']['cost_ranks']} "
              f"new(all-in)={new['selection']['cost_ranks']}"]
    return "\n".join(lines)


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        print(_compare(Path(sys.argv[2]), Path(sys.argv[3])))
    else:
        # importing ``src`` prints configuration banners, so the result goes to a file
        Path(sys.argv[4]).write_text(
            json.dumps(_replay(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]), indent=1),
            encoding="utf-8")
