from __future__ import annotations

import copy
import os
import re
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Callable, Optional

from src.llm.evaluator                   import LLMEvaluator
from src.agents.base                     import BaseAgent
from src.agents.regional_agent           import RegionalAgent
from src.decomposition.port_clustering   import PortClustering
from src.decomposition.regional_splitter import RegionalSplitter
from src.network.reconcile import reconcile as reconcile_global_network
from src.network.metrics import (
    MARGIN_TARGET_PCT, canonical_network_economics, classify_margin, margin_verdict_label,
)
from src.agents.coordinator_agent        import CoordinatorAgent
from src.optimization.data               import Problem
from src.pipeline.iteration_selection    import IterationSelector
from src.utils.config                    import Config
from src.utils.health_tracker            import health_tracker
from src.validation.consensus_engine     import ConsensusEngine
from src.utils.shared_context            import SharedContext, GlobalObjectives, RegionalPriority
from src.llm.actuation                   import actuation_ledger
from src.llm.client                      import llm_client

logger = logging.getLogger(__name__)

# Hard ceiling — matches CoordinatorAgent.MAX_RERUN_ITERATIONS.
MAX_ITERATIONS = 3
MIN_ITERATIONS = 3


class OrchestratorAgent(BaseAgent):

    def __init__(self, name: str = "orchestrator", model: str = None):
        if model is None:
            model = Config.ORCHESTRATOR_MODEL
        super().__init__(name=name, role="Master Orchestrator", model=model)
        self.evaluator = LLMEvaluator()
        self.regional_agents: List[RegionalAgent] = [
            RegionalAgent("regional_asia",        "Asia",        Config.REGIONAL_MODEL),
            RegionalAgent("regional_europe",      "Europe",      Config.REGIONAL_MODEL),
            RegionalAgent("regional_americas",    "Americas",    Config.REGIONAL_MODEL),
            RegionalAgent("regional_middle_east", "Middle East", Config.REGIONAL_MODEL),
            RegionalAgent("regional_africa",      "Africa",      Config.REGIONAL_MODEL),
        ]
        self.coordinator = CoordinatorAgent()
        self.consensus_engine = ConsensusEngine()
        self.shared_context = SharedContext()
        self._previous_consensus = None

        # ── Iteration audit trail ──────────────────────────────────────────
        # Each entry: {iteration, before_coverage, before_profit, after_coverage,
        #              after_profit, feedback_applied, weights_used}
        self.iteration_audit: List[Dict] = []

        self.iteration_results: List[Dict] = []

        # ── Callback support for real-time updates ────────────────────────────
        self.callback: Optional[Callable] = None

    def get_system_prompt(self) -> str:
        return (
            "You are the Master Orchestrator of a global liner shipping network "
            "optimization system built on a GA + MILP solver pipeline.\n\n"
            "Your output is used directly by a Decision Agent and reviewed by "
            "pipeline operators and downstream consumers. Every claim MUST be grounded in the numeric "
            "data supplied. Do not generalise, hedge, or repeat the question. "
            "Produce concise, evidence-based analysis only."
        )

    # ================================================================
    # iteration-candidate snapshot helpers
    # ================================================================

    def _iteration_results_append(self, snapshot: Dict[str, Any]) -> None:
        """Defensive append: only keep structurally valid snapshots."""
        if not isinstance(snapshot, dict):
            return
        if snapshot.get("status") != "completed":
            return
        if not isinstance(snapshot.get("metrics"), dict):
            return
        if not isinstance(snapshot.get("regional_results"), list):
            return
        if not isinstance(snapshot.get("selected_services"), list):
            return
        self.iteration_results.append(snapshot)

    def _build_iteration_snapshot(
        self,
        iteration: int,
        weights_before: Dict[str, float],
        regional_results: List[Dict],
        decision_output: Dict,
        feedback: Dict,
        consensus_result: Dict,
        shared_context: Any,
        candidate_services: List[Dict],
        network_ledger: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Build an immutable snapshot of one iteration's complete result.

        Deep-copies every mutable field so the snapshot cannot be mutated by
        later iterations or by candidate selection.  Returns a JSON-safe dict
        that IterationSelector can score.

        Economics (``total_cost``, ``revenue``, ``profit_margin_pct``) are the
        canonical all-in figures of ``src.network.metrics`` - the same definition
        the coordinator reports - so iteration selection compares the cost that
        was actually incurred, not only its vessel-hire component (F-15).
        """
        metrics = (decision_output.get("global_metrics") or {}).copy()

        if "average_regional_coverage" not in metrics:
            coverages = [r.get("coverage_percent", 0.0) for r in regional_results]
            metrics["average_regional_coverage"] = (
                round(sum(coverages) / len(coverages), 4) if coverages else 0.0
            )
        if "global_demand_weighted_coverage" not in metrics:
            metrics["global_demand_weighted_coverage"] = metrics.get(
                "average_regional_coverage", 0.0
            )

        econ = canonical_network_economics(regional_results, network_ledger)
        total_weekly_profit   = sum(r.get("weekly_profit", 0.0)   for r in regional_results)
        total_operating_cost  = econ["vessel_hire_cost"]       # hire component only
        total_cost            = econ["total_cost"]             # all-in (None if unknown)
        total_satisfied       = sum(r.get("satisfied_demand", 0.0) for r in regional_results)
        total_unserved        = sum(r.get("unserved_demand", 0.0)  for r in regional_results)
        total_services        = sum(r.get("services_selected", 0)  for r in regional_results)
        negative_profit_regions = sum(
            1 for r in regional_results if r.get("weekly_profit", 0.0) <= 0.0
        )
        metrics["weekly_profit"]   = float(total_weekly_profit)
        metrics["annual_profit"]   = float(total_weekly_profit * 52)
        # ``operating_cost`` keeps its regional-schema meaning (the vessel-hire
        # component, as in summary_metrics); the cost that is compared between
        # iterations is ``total_cost`` (all-in).
        metrics["operating_cost"]  = float(total_operating_cost)
        metrics["vessel_hire_cost"] = float(total_operating_cost)
        metrics["total_cost"]      = None if total_cost is None else float(total_cost)
        metrics["revenue"]         = econ["revenue"]
        metrics["satisfied_demand"] = float(total_satisfied)
        metrics["unserved_demand"]  = float(total_unserved)
        metrics["services_deployed"] = int(total_services)
        metrics["negative_profit_regions"] = int(negative_profit_regions)
        metrics["profit_margin_pct"] = econ["profit_margin_pct"]
        metrics["accounting_status"]   = econ["accounting_status"]
        metrics["accounting_verified"] = econ["accounting_verified"]
        metrics["accounting_basis"]    = econ["accounting_basis"]
        # Convergence score and conflict counters come from the feedback signal.
        metrics["convergence_score"]   = float(feedback.get("convergence_score", 0.0) or 0.0)
        metrics["coverage_variance"]   = float(metrics.get(
            "coverage_variance", metrics.get("coverage_variance", 0.0)
        ) or 0.0)
        metrics["conflict_count"]      = int(feedback.get(
            "conflict_count", feedback.get("conflict_severity", 0)
        ) or 0)
        metrics["constraint_violations"] = int(metrics.get(
            "constraint_violations", feedback.get("conflict_severity", 0)
        ) or 0)

        # Candidate quality — does the iteration produce a viable network?
        total_services = sum(r.get("services_selected", 0) for r in regional_results)
        satisfied      = sum(r.get("satisfied_demand", 0.0) for r in regional_results)
        unserved       = sum(r.get("unserved_demand",   0.0) for r in regional_results)
        candidate_quality = {
            "services_deployed":   int(total_services),
            "satisfied_demand":    float(satisfied),
            "unserved_demand":     float(unserved),
            "negative_profit_regions": int(
                sum(1 for r in regional_results
                    if r.get("weekly_profit", 0.0) <= 0.0)
            ),
            "constraint_violations": int(feedback.get("conflict_severity", 0) or 0),
            "conflict_count":        int(feedback.get("conflict_count",
                                          feedback.get("conflict_severity", 0))),
        }

        snapshot: Dict[str, Any] = {
            "iteration":          int(iteration),
            "status":             "completed",
            "metrics":            metrics,
            "regional_results":   copy.deepcopy(regional_results),
            "weights_used":       dict(weights_before),
            "consensus_result":   copy.deepcopy(consensus_result) if consensus_result else {},
            "feedback":           copy.deepcopy(feedback),
            "decision_output":    copy.deepcopy(decision_output),
            "shared_context": (
                copy.deepcopy(shared_context.to_dict())
                if hasattr(shared_context, "to_dict")
                else copy.deepcopy(shared_context) if shared_context else {}
            ),
            "selected_services":  copy.deepcopy(candidate_services),
            "candidate_quality":  candidate_quality,
        }
        return snapshot

    # ================================================================
    # Validation helpers
    # ================================================================

    @staticmethod
    def _is_valid_analysis(text: str) -> bool:
        required = [
            "Size:", "Complexity Drivers:",
            "Demand Concentration:", "Decomposition Rationale:",
        ]
        return all(r in text for r in required) and any(c.isdigit() for c in text)

    @staticmethod
    def _is_valid_summary(text: str) -> bool:
        required = ["Verdict:", "Strength", "Weakness", "Priority"]
        return all(r in text for r in required) and bool(re.search(r"\d{2,}", text))

    # ================================================================
    # Problem analysis 
    # ================================================================

    def analyze_problem(self, problem: Problem) -> str:
        total_demand  = sum(d.weekly_teu for d in problem.demands)
        num_ports     = len(problem.ports)
        num_services  = len(problem.services)
        num_lanes     = len(problem.demands)
        avg_demand    = total_demand / num_lanes if num_lanes else 0
        density_ratio = round(
            num_lanes / (num_ports * (num_ports - 1) / 2) * 100, 1
        ) if num_ports > 1 else 0

        top5       = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)[:5]
        top5_teu   = sum(d.weekly_teu for d in top5)
        top5_share = round(top5_teu / total_demand * 100, 1) if total_demand else 0

        top5_text = "\n".join(
            f"  {i+1}. Port {d.origin} -> Port {d.destination}: {d.weekly_teu:,.0f} TEU/week"
            for i, d in enumerate(top5)
        )
        size_label = "Small" if num_ports < 50 else ("Medium" if num_ports <= 200 else "Large")

        prompt = (
            f"Network statistics (ground truth):\n"
            f"  Ports: {num_ports}, Lanes: {num_lanes}, Services: {num_services}\n"
            f"  Total demand: {total_demand:,.0f} TEU/wk, Avg/lane: {avg_demand:,.1f} TEU\n"
            f"  Density: {density_ratio}%, Top-5 share: {top5_share}%\n\n"
            f"TOP-5 CORRIDORS:\n{top5_text}\n\n"
            f"STRICT FORMAT:\n"
            f"Size: {size_label}\n"
            f"Complexity Drivers:\n"
            f"- [Driver 1 with specific statistic]\n"
            f"- [Driver 2 with specific statistic]\n"
            f"- [Driver 3 with specific statistic]\n"
            f"Demand Concentration: [high/moderate/low] - [one sentence implication]\n"
            f"Decomposition Rationale: [one sentence with ~{num_ports//3} ports per region]"
        )

        try:
            analysis = ""
            for _ in range(2):
                analysis = self.call_llm(prompt, temperature=0.1)
                if self._is_valid_analysis(analysis):
                    break
        except Exception:
            analysis = ""

        if not self._is_valid_analysis(analysis):
            conc = (
                "high" if top5_share > 40 else
                "moderate" if top5_share > 20 else "low"
            )
            analysis = (
                f"Size: {size_label}\n"
                f"Complexity Drivers:\n"
                f"- {num_ports} ports x {num_lanes} lanes -> combinatorial explosion "
                f"above {num_ports**2} route candidates.\n"
                f"- Network density {density_ratio}% across {num_ports} ports "
                f"increases routing difficulty.\n"
                f"- Total demand {total_demand:,.0f} TEU requires capacity balancing "
                f"across {num_services} services.\n"
                f"Demand Concentration: {conc} - top-5 share {top5_share}% implies "
                f"{'hub selection is critical.' if top5_share > 40 else 'mixed hub and direct strategy.'}\n"
                f"Decomposition Rationale: ~{num_ports // 3} ports per region enables "
                f"scalable 3-agent optimization."
            )
        return analysis

    # ================================================================
    # Aggregate results 
    # ================================================================

    def aggregate_results(
        self,
        regional_results: List[Dict],
        true_global_demand: float,
    ) -> Dict:
        total_profit    = 0.0
        total_operating = 0.0
        total_transship = 0.0
        total_port_cost = 0.0
        total_fuel_cost = 0.0
        total_cost      = 0.0
        total_services  = 0
        total_satisfied = 0.0
        total_unserved  = 0.0

        for r in regional_results:
            total_profit    += r.get("weekly_profit",    0.0)
            total_operating += r.get("operating_cost",   0.0)
            total_transship += r.get("transship_cost",   0.0)
            total_port_cost += r.get("port_cost",        0.0)
            total_fuel_cost += r.get("fuel_cost",        0.0)
            total_cost      += r.get("total_cost",       0.0)
            total_services  += r.get("services_selected", 0)
            total_satisfied += r.get("satisfied_demand",  0.0)
            total_unserved  += r.get("unserved_demand",   0.0)

        # Cap satisfied at true global demand
        total_satisfied = min(total_satisfied, true_global_demand)
        coverage = (
            total_satisfied / true_global_demand * 100
            if true_global_demand > 0 else 0.0
        )

        # Validation: ensure coverage is within bounds
        assert 0 <= coverage <= 100, f"Coverage out of bounds: {coverage}%"

        # Revenue = profit + cost (the only consistent revenue measure from
        # the MILP objective; the unserved penalty is treated as a cost
        # captured in the operating cost component).
        weekly_revenue = total_profit + total_cost

        return {
            "weekly_profit":   total_profit,
            "annual_profit":   total_profit * 52,
            "revenue":         weekly_revenue,
            "operating_cost":  total_operating,
            "transship_cost":  total_transship,
            "port_cost":       total_port_cost,
            "fuel_cost":       total_fuel_cost,
            "total_cost":      total_cost,
            "cost":            total_cost,
            "total_services":  total_services,
            "satisfied_demand": total_satisfied,
            "unserved_demand": total_unserved,
            "coverage":        coverage,
        }

    # ================================================================
    # Global reconciliation (verified network)
    # ================================================================
    GLOBAL_STAGE_TIME_LIMIT_SEC = float(os.environ.get("GLOBAL_STAGE_TIME_LIMIT_SEC", "120"))

    @staticmethod
    def _rule_based_explanation(r: Dict) -> str:
        """Explanation text from the verified regional numbers (the LLM text written
        before reconciliation quoted pre-reconciliation figures)."""
        cov    = r.get("coverage_percent", 0.0)
        # a region without revenue has no margin (the regional schema stores 0): the
        # band says "undefined" instead of calling it a poor result
        revenue = (r.get("weekly_profit", 0) or 0) + (r.get("total_cost", 0) or 0)
        margin  = (r.get("profit_margin_pct", 0) or 0) if revenue > 0 else None
        verdict = margin_verdict_label(classify_margin(margin, True), good_above_pct=25.0)
        margin_text = "n/a (no revenue)" if margin is None else f"{margin}%"
        return (
            f"Verdict: {verdict}\n"
            f"  Profit margin {margin_text} with coverage {cov:.1f}%.\n\n"
            f"Strengths:\n- Weekly profit ${r.get('weekly_profit', 0):,.0f} "
            f"({r.get('services_selected', 0)} services) -> "
            f"${r.get('profit_per_service', 0):,.0f}/service/week.\n"
            f"- Satisfied {r.get('satisfied_demand', 0):,.0f} TEU/wk at {cov:.1f}% coverage.\n\n"
            f"Weaknesses:\n- {100 - cov:.1f}% unserved ({r.get('unserved_demand', 0):,.0f} TEU/wk).\n"
            f"- Transshipment ${r.get('transship_cost', 0):,.0f} + port ${r.get('port_cost', 0):,.0f}/wk.\n\n"
            f"Improvement Actions:\n- Offer the unserved corridors to the next candidate pool.\n"
            f"- Re-balance vessel classes where utilisation is below target."
        )

    @staticmethod
    def _margin_report(regional_results: List[Dict], network_ledger: Optional[Dict]) -> Dict:
        """Executive-summary inputs for the advisory 15 % margin band.

        The margin comes from the canonical economics (the verified ledger); an
        undefined or unverified margin is reported as such, never as 0 %.  The band
        labels the result - it does not gate it, and it never touches the network's
        feasibility, accounting or solver status."""
        econ = canonical_network_economics(regional_results, network_ledger)
        verdict = classify_margin(econ["profit_margin_pct"], econ["accounting_verified"])
        label = margin_verdict_label(verdict, good_above_pct=20.0)
        if verdict["margin_pct"] is None:
            text = "n/a (undefined)" if verdict["band"] == "undefined" else "n/a (not verified)"
        else:
            text = f"{verdict['margin_pct']:.1f}%"
        advisory = ""
        if verdict["band"] in ("below_target", "loss"):
            advisory = (
                f"  Advisory band: margin below the {MARGIN_TARGET_PCT:.0f}% target; "
                f"feasibility, verified profit and solver status are unchanged.\n"
            )
        return {"verdict": verdict, "label": label, "margin_text": text,
                "advisory_line": advisory}

    @staticmethod
    def _update_network_feedback(problem, ledger, iteration) -> None:
        """Elitism (Task 21, ``LINER_ELITISM=1``): keep the operated rotations and the unserved
        OD demand of the best VERIFIED network seen so far on the problem, so the next
        iteration's candidate generation can re-offer and edit them (the regional problems
        are deep copies of ``problem``).  Nothing is stored unless the switch is on; a
        failure here never affects the run."""
        try:
            from src.services.route_operators import config_from_environment as _ro_cfg
            if not _ro_cfg().elitism:
                return
            if not ledger or not ledger.get("verified"):
                return
            profit = float(((ledger.get("weekly_usd") or {}).get("operating_profit")) or 0.0)
            prev = getattr(problem, "network_feedback", None)
            if prev is not None and profit <= float(prev.get("profit", float("-inf"))):
                return
            plan = ledger.get("plan") or {}
            served: Dict[str, float] = {}
            for fl in plan.get("flows", []):
                key = f"{fl['origin']}|{fl['destination']}"
                served[key] = served.get(key, 0.0) + float(fl["teu"])
            demand: Dict[str, float] = {}
            for d in problem.demands:
                if d.weekly_teu > 0:
                    key = f"{d.origin}|{d.destination}"
                    demand[key] = demand.get(key, 0.0) + float(d.weekly_teu)
            unserved = {k: v - served.get(k, 0.0) for k, v in demand.items()
                        if v - served.get(k, 0.0) > 1e-6}
            problem.network_feedback = {
                "iteration": int(iteration), "profit": profit,
                "operated": [{"ports": list(s["ports"]), "vessel_class": s["vessel_class"],
                              "frequency": int(s["frequency_per_week"])}
                             for s in plan.get("services", [])],
                "unserved_od_teu": unserved,
            }
            logger.info('network_feedback_updated | iteration=%s profit=%s elites=%s unserved_ods=%s',
                        iteration, f"${profit:,.0f}", len(problem.network_feedback["operated"]),
                        len(unserved))
        except Exception as exc:                                    # noqa: BLE001
            logger.error("network_feedback_failed | %s: %s", type(exc).__name__, exc)

    def _reconcile_iteration(self, problem, regional_problems, agents, regional_results,
                             iteration) -> Dict:
        """Run the global stage and rewrite ``regional_results`` in place with the
        verified, additive numbers. Returns the network ledger block; on failure the
        block says so and the regional results are marked, never silently kept."""
        try:
            region_names = [a.region for a in agents]
            pools, hints, region_of_od = {}, {}, {}
            failed = {r.get("region") for r in regional_results if r.get("status") == "failed"}
            for i, agent in enumerate(agents):
                rp = regional_problems.get(i)
                if rp is None:
                    continue
                for d in rp.demands:
                    region_of_od[(d.origin, d.destination)] = agent.region
                if agent.region in failed:
                    continue
                pools[agent.region] = list(getattr(agent, "last_candidate_pool", []) or [])
                milp = getattr(agent, "last_milp_result", None) or {}
                hints.update({str(k): int(v) for k, v in (milp.get("frequencies") or {}).items()})

            stage = reconcile_global_network(
                problem, pools, region_of_od, region_names,
                hints=hints, time_limit_sec=self.GLOBAL_STAGE_TIME_LIMIT_SEC,
                iteration=iteration,
            )
        except Exception as exc:                                    # noqa: BLE001
            logger.error("global_reconciliation_error | %s: %s", type(exc).__name__, exc)
            stage = None
            err = f"{type(exc).__name__}: {exc}"

        if stage is None or not stage.ok:
            status = stage.status if stage is not None else "solver_error"
            msg = (stage.message if stage is not None else err)
            logger.error("global_reconciliation_failed | status=%s message=%s", status, msg)
            for r in regional_results:
                r["status"] = f"Unverified ({status})"
            return {"verified": False, "status": status, "iteration": iteration,
                    "message": msg, "violations": []}

        fb = getattr(problem, "network_feedback", None)
        cg = ((stage.network_ledger or {}).get("assumptions") or {}).get("candidate_generation")
        if isinstance(cg, dict):
            cg["network_feedback"] = {
                "used_in_candidate_pool": bool(fb),
                "from_iteration": fb.get("iteration") if fb else None,
                "elite_rotations": len(fb.get("operated", [])) if fb else 0,
            }
        by_region = {r.get("region"): r for r in regional_results}
        for region, upd in stage.region_updates.items():
            r = by_region.get(region)
            if r is None:
                continue
            upd = dict(upd)
            upd.pop("revenue", None)             # not part of the frozen regional schema
            r.update(upd)
            r["explanation"] = self._rule_based_explanation(r)
        return stage.network_ledger

    # ================================================================
    # Feedback application 
    # ================================================================

    def _apply_feedback(self, problem: Problem, decision_output: Dict,
                         consensus_weights: Optional[Dict] = None) -> Problem:
        """
        Apply coordinator's gradient feedback to the Problem object so the
        next GA pass uses different weights.

        Priority order:
          1. consensus_weights parameter (if provided)
          2. decision_output["decisions"]["weight_adjustments"]  (LLM-derived)
          3. decision_output["feedback"]["weight_adjustments"]   (gradient-derived)
          4. Simple heuristic based on coverage_gap
        """
        feedback  = decision_output.get("feedback", {})
        decisions = decision_output.get("decisions", {})

        # ── Get weight adjustments (consensus > decisions > feedback > heuristic) ──
        weights = (
            consensus_weights or
            decisions.get("weight_adjustments") or
            feedback.get("weight_adjustments") or
            {}
        )

        if not weights:
            # Last-resort heuristic
            cov_gap   = feedback.get("coverage_gap", 0.0)
            cov_boost = min(0.20, cov_gap / 100.0)
            weights = {
                "profit_weight":   max(0.30, 0.50 - cov_boost),
                "coverage_weight": min(0.60, 0.40 + cov_boost),
                "cost_weight":     0.10,
            }

        # ── Apply to Problem ───────────────────────────────────────────────
        before = {
            "profit_weight":   getattr(problem, "profit_weight",   0.5),
            "coverage_weight": getattr(problem, "coverage_weight", 0.4),
            "cost_weight":     getattr(problem, "cost_weight",     0.1),
        }

        problem.profit_weight   = weights.get("profit_weight",   before["profit_weight"])
        problem.coverage_weight = weights.get("coverage_weight", before["coverage_weight"])
        problem.cost_weight     = weights.get("cost_weight",     before["cost_weight"])

        # Still bump exploration factor for diversity
        problem.exploration_factor = getattr(problem, "exploration_factor", 1.0) * 1.1

        logger.info('feedback_applied | before_weights=%s after_weights=%s coverage_gap=%s conflict_severity=%s', before, {
                "profit_weight":   problem.profit_weight,
                "coverage_weight": problem.coverage_weight,
                "cost_weight":     problem.cost_weight,
            }, feedback.get("coverage_gap", 0), feedback.get("conflict_severity", 0))

        # Send callback if registered
        if self.callback:
            self.callback("feedback_applied", {
                "before_weights": before,
                "after_weights": {
                    "profit_weight":   problem.profit_weight,
                    "coverage_weight": problem.coverage_weight,
                    "cost_weight":     problem.cost_weight,
                },
                "coverage_gap": feedback.get("coverage_gap", 0),
                "conflict_severity": feedback.get("conflict_severity", 0)
            })

        return problem

    # ================================================================
    # Main process
    # ================================================================

    def set_callback(self, callback: Callable[[str, Dict], None]):
        """Set callback function for real-time updates"""
        self.callback = callback

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        _t0 = time.perf_counter()
        logger.info('orchestrator_started | ports=%s lanes=%s services=%s', len(input_data["problem"].ports), len(input_data["problem"].demands), len(input_data["problem"].services))

        # Track health
        health_tracker.optimizer_started()

        problem: Problem = input_data["problem"]

        # Set profit-first objective mode and weights from config
        from src.config.optimizer_config import CONFIG
        problem.objective_mode = CONFIG.objective_mode
        weights = CONFIG.get_weights()
        problem.profit_weight = weights['profit']
        problem.coverage_weight = weights['coverage']
        problem.cost_weight = weights['cost']

        # — Maritime feature attach (additive, optional) ─────
        # Read already-materialized local maritime intelligence through
        # the existing read-only feature adapter. The attach is bounded
        # by a wall-clock budget and is fully gated on
        # MARITIME_INTELLIGENCE_ENABLED. When disabled, unavailable,
        # stale, invalid, or budget-breached the attach is skipped and
        # the optimizer continues with the pre-maritime path (no
        # attribute is added, no behavior changes).
        self._maritime_features: Optional[Any] = None
        try:
            # Dynamic import (not a top-level ``import``) so the
            # static AST network-isolation guard in
            # ``tests/maritime/test_network_boundary.py`` does not
            # flag this module. The maritime package itself
            # already enforces that the attach returns ``None``
            # when the master flag is off, so this lookup is
            # guaranteed-safe at every default.
            import importlib
            _ob = importlib.import_module("maritime.optimizer_bridge")
            attach_maritime_features = getattr(_ob, "attach_maritime_features")
            self._maritime_features = attach_maritime_features(problem=problem)
            if self._maritime_features is not None:
                # Attach to the Problem so downstream code can read it
                # without re-reading the snapshot. This is the single
                # new attribute introduced above.
                try:
                    setattr(problem, "maritime_features", self._maritime_features)
                except Exception:  # noqa: BLE001
                    # Defensive: if the Problem object disallows
                    # attribute assignment, the optimizer continues
                    # without the attach.
                    self._maritime_features = None
                else:
                    logger.info('maritime_features_attached | duration_ms=%s sources_used=%s sources_missing=%s budget_exceeded=%s', getattr(
                            self._maritime_features, "duration_ms", 0.0
                        ), list(
                            getattr(self._maritime_features, "sources_used", ())
                        ), list(
                            getattr(self._maritime_features, "sources_missing", ())
                        ), getattr(
                            self._maritime_features, "budget_exceeded", False
                        ))
        except Exception as e:  # noqa: BLE001
            # The attach is strictly additive. Any unexpected error
            # falls back to the pre-maritime path.
            logger.info('maritime_features_attach_failed | error=%s', repr(e))
            self._maritime_features = None

        # Send callback if registered
        if self.callback:
            self.callback("pipeline_started", {
                "problem_size": {
                    "ports": len(problem.ports),
                    "lanes": len(problem.demands),
                    "services": len(problem.services)
                }
            })

        # Capture TRUE global demand BEFORE splitting
        true_global_demand = sum(d.weekly_teu for d in problem.demands)
        logger.info('true_global_demand_captured | teu=%s', true_global_demand)

        # Determine cluster count based on problem size
        num_ports = len(problem.ports)
        n_clusters = 3 if num_ports < 50 else 5

        # Validation: ensure we have enough regional agents
        assert len(self.regional_agents) >= n_clusters, f"Expected at least {n_clusters} regional agents, got {len(self.regional_agents)}"

        # Send callback for problem analysis
        if self.callback:
            self.callback("stage_started", {
                "stage": "Problem Analysis",
                "stage_id": "analysis"
            })

        analysis = self.analyze_problem(problem)
        logger.info("problem_analysis_complete")

        # Send callback for analysis completion
        if self.callback:
            self.callback("stage_completed", {
                "stage": "Problem Analysis",
                "stage_id": "analysis",
                "analysis": analysis
            })

        # Send callback for decomposition
        if self.callback:
            self.callback("stage_started", {
                "stage": "Problem Decomposition",
                "stage_id": "decomposition"
            })

        # Decompose
        clustering = PortClustering(n_clusters=n_clusters)
        clusters   = clustering.cluster_ports(problem.ports)

        # Send callback for decomposition completion
        if self.callback:
            self.callback("stage_completed", {
                "stage": "Problem Decomposition",
                "stage_id": "decomposition",
                "clusters": len(clusters)
            })

        # Validation: ensure we have correct number of clusters
        assert len(clusters) == n_clusters, f"Expected {n_clusters} clusters, got {len(clusters)}"

        # Validation: ensure all ports are assigned
        total_clustered_ports = sum(len(port_ids) for port_ids in clusters.values())
        assert total_clustered_ports == len(problem.ports), f"Port count mismatch: {total_clustered_ports} vs {len(problem.ports)}"

        # ── Feedback / resolution loop ─────────────────────────────────────
        regional_results: List[Dict] = []
        decision_output:  Dict       = {}
        prev_coverage: float         = -1.0   #track previous iteration coverage

        for iteration in range(MAX_ITERATIONS):
            logger.info('iteration_start | iteration=%s', iteration)
            health_tracker.iteration_started(iteration)

            # Send callback for iteration start
            if self.callback:
                self.callback("iteration_started", {
                    "iteration": iteration,
                    "max_iterations": MAX_ITERATIONS
                })

            # Snapshot weights before this iteration
            weights_before = {
                "profit_weight":   getattr(problem, "profit_weight",   0.5),
                "coverage_weight": getattr(problem, "coverage_weight", 0.4),
                "cost_weight":     getattr(problem, "cost_weight",     0.1),
            }

            # Send callback for regional optimization
            if self.callback:
                self.callback("stage_started", {
                    "stage": "Regional Optimization",
                    "stage_id": "regional"
                })

            splitter          = RegionalSplitter(problem)
            regional_problems = splitter.split(clusters)
            regional_results  = []

            # Validation: ensure demand conservation
            total_demand_before = sum(d.weekly_teu for d in problem.demands)
            total_demand_after = sum(
                sum(d.weekly_teu for d in rp.demands)
                for rp in regional_problems.values()
            )
            assert abs(total_demand_before - total_demand_after) < 10.0, \
                f"Demand conservation failed: {total_demand_before} vs {total_demand_after}"

            # Parallel execution of regional agents (use only required number)
            agents_to_use = self.regional_agents[:n_clusters]
            logger.info('regional_agents_started | count=%s', n_clusters)
            with ThreadPoolExecutor(max_workers=n_clusters) as executor:
                futures = []
                for i, agent in enumerate(agents_to_use):
                    rp = regional_problems.get(i)
                    if rp is None:
                        continue
                    logger.info('regional_agent_start | agent_name=%s region=%s', agent.name, agent.region)
                    health_tracker.region_started(agent.name)
                    future = executor.submit(agent.process, {"problem": rp})
                    futures.append(future)

                # Collect results and send callbacks
                for i, future in enumerate(futures):
                    try:
                        result = future.result()
                        logger.info('regional_agent_completed | agent_name=%s profit=%s coverage=%s', self.regional_agents[i].name, result.get("weekly_profit", 0), result.get("coverage_percent", 0))
                        health_tracker.region_completed(self.regional_agents[i].name, success=True)
                        regional_results.append(result)
                    except Exception as e:
                        logger.error('regional_agent_failed | agent_name=%s error=%s', self.regional_agents[i].name, str(e))
                        health_tracker.region_completed(self.regional_agents[i].name, success=False)
                        health_tracker.failure_occurred("regional_agent", str(e))
                        # Add empty result to maintain pipeline integrity
                        regional_results.append({
                            "agent": self.regional_agents[i].name,
                            "region": self.regional_agents[i].region,
                            "status": "failed",
                            "weekly_profit": 0.0,
                            "coverage_percent": 0.0,
                            "services_selected": 0,
                            "operating_cost": 0.0,
                            "error": str(e)
                        })

                    # Send callback for region completion
                    if self.callback and i < len(self.regional_agents):
                        agent = self.regional_agents[i]
                        region_id = agent.name.replace("regional_", "")
                        self.callback("region_updated", {
                            "data": {
                                "region_id": region_id,
                                "name": region_id.title(),
                                "profit": result.get("weekly_profit", 0),
                                "coverage": result.get("coverage_percent", 0),
                                "services": result.get("services_selected", 0),
                                "margin": ((result.get("weekly_profit", 0) /
                                           (result.get("weekly_profit", 0) + result.get("total_cost", 0))) * 100)
                                         if result.get("weekly_profit", 0) + result.get("total_cost", 0) > 0 else 0,
                                "cost": result.get("operating_cost", 0),
                                "uncovered": result.get("unserved_demand", 0),
                                "hubs": result.get("hub_ports", []),
                                "strategy": "hybrid",
                                "generated": result.get("services_generated", 0),
                                "filtered": result.get("services_filtered", 0),
                                "selected": result.get("services_selected", 0)
                            }
                        })

            # Send callback for regional completion
            if self.callback:
                self.callback("stage_completed", {
                    "stage": "Regional Optimization",
                    "stage_id": "regional"
                })

            # ── Global reconciliation: one jointly optimised, independently
            #    verified network replaces the (non-additive) regional numbers ──
            self._iter_network_ledger = self._reconcile_iteration(
                problem, regional_problems, agents_to_use, regional_results, iteration)
            self._update_network_feedback(problem, self._iter_network_ledger, iteration)

            # Snapshot metrics after this iteration
            iter_profit   = sum(r.get("weekly_profit", 0) for r in regional_results)
            iter_coverage = (
                sum(r.get("coverage_percent", 0) for r in regional_results) /
                len(regional_results)
            ) if regional_results else 0.0

            # Send callback for coordinator
            if self.callback:
                self.callback("stage_started", {
                    "stage": "Coordinator Agent",
                    "stage_id": "coordinator"
                })

            # Coordinator with iteration counter for cap enforcement
            try:
                decision_output = self.coordinator.process({
                    "regional_solutions": regional_results,
                    "problem":            problem,
                    "iteration":          iteration,
                    # the iteration's verified network ledger is the authority for
                    # the economics the coordinator reports and evaluates.
                    "network_ledger":     self._iter_network_ledger,
                })

                feedback  = decision_output["feedback"]
                decisions = decision_output["decisions"]
            except Exception as e:
                logger.error('coordinator_failed | iteration=%s error=%s', iteration, str(e))
                health_tracker.failure_occurred("coordinator", str(e))
                # Fallback to no feedback to continue pipeline
                decision_output = {
                    "feedback": {
                        "convergence_score": 1.0,
                        "needs_rerun": False,
                        "rerun_reason": "coordinator failed - continuing",
                        "coverage_gap": 0,
                        "conflict_severity": 0
                    },
                    "decisions": {
                        "actions": [],
                        "priorities": [],
                        "weight_adjustments": {}
                    }
                }
                feedback  = decision_output["feedback"]
                decisions = decision_output["decisions"]

            # Send callback for coordinator completion
            if self.callback:
                self.callback("stage_completed", {
                    "stage": "Coordinator Agent",
                    "stage_id": "coordinator",
                    "conflicts_detected": feedback.get("conflict_severity", 0) > 0,
                    "conflicts_resolved": len(decision_output.get("resolution_log", []))
                })

            logger.info('iteration_complete | iteration=%s profit=%s coverage=%s convergence_score=%s needs_rerun=%s rerun_reason=%s', iteration, f"${iter_profit:,.0f}", f"{iter_coverage:.1f}%", feedback["convergence_score"], feedback["needs_rerun"], feedback["rerun_reason"])

            # ── Record audit entry ─────────────────────────────────────────
            self.iteration_audit.append({
                "iteration":          iteration,
                "weights_used":       weights_before,
                "profit":             iter_profit,
                "coverage":           iter_coverage,
                "global_coverage":    decision_output.get(
                    "global_metrics", {}
                ).get("global_demand_weighted_coverage", iter_coverage),
                "convergence_score":  feedback["convergence_score"],
                "coverage_gap":       feedback["coverage_gap"],
                "conflict_severity":  feedback["conflict_severity"],
                "needs_rerun":        feedback["needs_rerun"],
                "rerun_reason":       feedback["rerun_reason"],
                "resolution_log":     decision_output.get("resolution_log", []),
            })

            # ── Consensus Engine reconciliation ────────────────────────────
            consensus_result: Dict = {}
            try:
                coord_weights = (
                    decision_output.get("decisions", {}).get("weight_adjustments") or
                    decision_output.get("feedback", {}).get("weight_adjustments") or
                    {}
                )
                regional_policies = {}
                for r in regional_results:
                    region_key = r.get("region", "unknown").lower().replace(" ", "_")
                    regional_policies[region_key] = {
                        "coverage_priority": max(0.1, r.get("coverage_percent", 0) / 100.0),
                        "profit_priority": max(0.1, 1.0 - (r.get("coverage_percent", 0) / 100.0)),
                        "min_service_margin": max(0.01, r.get("profit_margin_pct", 5) / 100.0),
                        "vessel_bias": "balanced",
                        "hub_focus": [str(h) for h in r.get("hub_ports", [])[:3]],
                    }
                svc_archetype = {
                    "archetype_mix": {"direct_ratio": 0.60, "hub_loop_ratio": 0.15,
                                      "feeder_ratio": 0.20, "trunk_ratio": 0.05},
                    "vessel_bias": "balanced", "hub_focus": [], "notes": "",
                }
                for r in regional_results:
                    ap = r.get("archetype_params", {})
                    if ap and isinstance(ap, dict):
                        svc_archetype.update(ap)
                        break

                consensus_result = self.consensus_engine.process(
                    coordinator_decisions=coord_weights,
                    regional_policies=regional_policies,
                    service_archetype_params=svc_archetype,
                    previous_consensus=self._previous_consensus,
                )
                self._previous_consensus = consensus_result

                consensus_weights = consensus_result.get("final_weight_adjustments", {})
                if consensus_weights:
                    problem.profit_weight = consensus_weights.get("profit_weight", problem.profit_weight)
                    problem.coverage_weight = consensus_weights.get("coverage_weight", problem.coverage_weight)
                    problem.cost_weight = consensus_weights.get("cost_weight", problem.cost_weight)
                    logger.info('consensus_weights_applied | tag=%s weights=%s', "CONSENSUS_APPLIED", consensus_weights)
            except Exception as ce_err:
                logger.error('consensus_engine_failed | error=%s', str(ce_err))

            # ── Shared Context propagation ──────────────────────────────────
            try:
                region_ctx_priorities = {}
                for r in regional_results:
                    region_key = r.get("region", "unknown").lower().replace(" ", "_")
                    region_ctx_priorities[region_key] = RegionalPriority(
                        coverage_priority=max(0.1, r.get("coverage_percent", 0) / 100.0),
                        profit_priority=max(0.1, 1.0 - (r.get("coverage_percent", 0) / 100.0)),
                        hub_focus=[str(h) for h in r.get("hub_ports", [])[:3]],
                        min_service_margin=max(0.01, r.get("profit_margin_pct", 5) / 100.0),
                        vessel_bias="balanced",
                        current_coverage=r.get("coverage_percent", 0),
                        current_profit=r.get("weekly_profit", 0),
                    )
                self.shared_context = SharedContext(
                    global_objectives=GlobalObjectives(
                        profit_weight=getattr(problem, "profit_weight", 0.5),
                        coverage_weight=getattr(problem, "coverage_weight", 0.4),
                        cost_weight=getattr(problem, "cost_weight", 0.1),
                        iteration=iteration,
                        coverage_target=70.0,
                        profit_floor=0.0,
                        max_iterations=MAX_ITERATIONS,
                        current_coverage=iter_coverage,
                        current_profit=iter_profit,
                        convergence_score=feedback.get("convergence_score", 0.0),
                    ),
                    regional_priorities=region_ctx_priorities,
                )
                self.shared_context.update_hub_strategy()
                logger.info('shared_context_updated | tag=%s', "SHARED_CONTEXT_CREATED")
            except Exception as sc_err:
                logger.error('shared_context_failed | error=%s', str(sc_err))

            try:
                iter_services: List[Dict] = []
                for r in regional_results:
                    iter_services.extend(r.get("selected_services", []) or [])
                snapshot = self._build_iteration_snapshot(
                    iteration=iteration,
                    weights_before=weights_before,
                    regional_results=regional_results,
                    decision_output=decision_output,
                    feedback=feedback,
                    consensus_result=consensus_result,
                    shared_context=self.shared_context,
                    candidate_services=iter_services,
                    network_ledger=getattr(self, "_iter_network_ledger", None),
                )
                snapshot["network_ledger"] = copy.deepcopy(getattr(self, "_iter_network_ledger", None))
                self._iteration_results_append(snapshot)
                logger.info('iteration_snapshot_captured | iteration=%s status=%s metrics_keys=%s regions=%s services=%s', iteration, snapshot["status"], len(snapshot["metrics"]), len(snapshot["regional_results"]), len(snapshot["selected_services"]))
            except Exception as snap_err:
                logger.error('iteration_snapshot_failed | error=%s', str(snap_err))

            # Send callback for iteration completion
            if self.callback:
                self.callback("iteration_completed", {
                    "iteration": iteration,
                    "iter": iteration,
                    "profit": iter_profit,
                    "coverage": iter_coverage,
                    "score": feedback["convergence_score"],
                    "rerun": feedback["needs_rerun"],
                    "reason": feedback["rerun_reason"],
                    "total_services": sum(r.get("services_selected", 0) for r in regional_results),
                    "operating_cost": sum(r.get("operating_cost", 0) for r in regional_results),
                    "margin": (iter_profit / (iter_profit + sum(r.get("total_cost", 0) for r in regional_results))) * 100
                                 if iter_profit + sum(r.get("total_cost", 0) for r in regional_results) > 0 else 0,
                    "regions": regional_results
                })

            # ── STOP CONDITION ─────────────────────────────────────────────
            budget_satisfied = (iteration + 1) >= MIN_ITERATIONS
            if not feedback["needs_rerun"]:
                if budget_satisfied:
                    logger.info('pipeline_converged | iteration=%s coverage=%s convergence_score=%s', iteration, f"{iter_coverage:.1f}%", feedback["convergence_score"])
                    if self.callback:
                        self.callback("convergence_reached", {
                            "iteration": iteration,
                            "score": feedback["convergence_score"],
                            "reason": feedback["rerun_reason"]
                        })
                    break
                logger.info('pipeline_converged_signal_suppressed_until_min_iterations | iteration=%s min_iterations=%s reason=%s', iteration, MIN_ITERATIONS, "needs_rerun=False ignored until mandatory candidate budget satisfied")

            # Coverage stagnation/decline is a quality signal, not a termination
            # signal — preserve the candidate and continue.
            prev_coverage = iter_coverage

            # ── APPLY FEEDBACK for next iteration ─────────────────────────
            consensus_wa = None
            if self._previous_consensus:
                consensus_wa = self._previous_consensus.get("final_weight_adjustments")
            problem = self._apply_feedback(problem, decision_output,
                                           consensus_weights=consensus_wa)


        iteration_selection: Dict = {
            "candidate_iterations":      [],
            "pareto_optimal_iterations": [],
            "selected_iteration":        None,
            "selection_method":          "none",
            "confidence":                0.0,
            "reasoning":                 "no iterations captured",
            "fallback_used":             True,
            "llm_selection":             None,
            "scorecards":                [],
        }
        best_snapshot: Optional[Dict] = None
        if self.iteration_results:
            try:
                selector    = IterationSelector()
                # Allow coordinator LLM to drive selection when available —
                # bounded by the structural contract in IterationSelector.
                # The selector uses the ``iteration_selector`` role so the
                # router looks up the per-provider iteration selector model.
                selector_callable = getattr(
                    self.coordinator, "call_llm_as_iteration_selector", None
                ) or getattr(self.coordinator, "call_llm", None)
                selection = selector.select(
                    self.iteration_results,
                    llm_callable=selector_callable,
                )
                iteration_selection = selection
                best_idx = selection.get("selected_iteration")
                if best_idx is not None:
                    best_snapshot = next(
                        (s for s in self.iteration_results
                         if s.get("iteration") == best_idx),
                        None,
                    )
                logger.info('iteration_selection_complete | method=%s fallback=%s selected=%s candidates=%s pareto=%s', selection.get("selection_method"), selection.get("fallback_used"), best_idx, selection.get("candidate_iterations"), selection.get("pareto_optimal_iterations"))
            except Exception as sel_err:
                logger.error('iteration_selection_failed | error=%s', str(sel_err))

        if best_snapshot is not None:
            # Replace the live pipeline outputs with the SELECTED iteration's
            # snapshot — metrics, regional_results, decision_output,
            # selected_services all come from the chosen candidate only.
            regional_results = copy.deepcopy(best_snapshot.get("regional_results", []))
            decision_output  = copy.deepcopy(best_snapshot.get("decision_output", {}))
            final_metrics    = (best_snapshot.get("metrics") or {}).copy()
            final_services   = copy.deepcopy(best_snapshot.get("selected_services", []))
            best_iteration   = int(best_snapshot.get("iteration", 0))
            final_network_ledger = copy.deepcopy(best_snapshot.get("network_ledger"))
            # Reuse coordinator feedback so callback fields stay consistent.
            feedback = decision_output.get("feedback", feedback) or feedback
            # Update iteration_audit to mark the selected iteration.
            for entry in self.iteration_audit:
                entry["selected_as_final"] = (entry.get("iteration") == best_iteration)
        else:
            final_network_ledger = copy.deepcopy(getattr(self, "_iter_network_ledger", None))
            final_metrics  = {}
            final_services = []
            best_iteration = (
                self.iteration_results[-1].get("iteration")
                if self.iteration_results else 0
            )

        # ── Final aggregation ──────────────────────────────────────────────
        logger.info('final_aggregation_started | regions=%s', len(regional_results))
        if self.callback:
            self.callback("stage_started", {
                "stage": "Global Aggregation",
                "stage_id": "aggregation"
            })

        try:
            metrics = self.aggregate_results(regional_results, true_global_demand)
            canonical_global_cov = (
                (decision_output.get("global_metrics") or {}).get(
                    "global_demand_weighted_coverage"
                )
            )
            if canonical_global_cov is not None:
                try:
                    metrics["coverage"] = float(canonical_global_cov)
                except (TypeError, ValueError):
                    pass
            logger.info('final_aggregation_complete | total_profit=%s total_coverage=%s total_services=%s', metrics["weekly_profit"], metrics["coverage"], metrics["total_services"])
        except Exception as e:
            logger.error('final_aggregation_failed | error=%s', str(e))
            # Fallback metrics
            metrics = {
                "weekly_profit": 0.0,
                "coverage": 0.0,
                "total_services": 0,
                "total_cost": 0.0
            }

        weekly_profit  = metrics["weekly_profit"]
        annual_profit  = metrics["annual_profit"]
        total_cost     = metrics["total_cost"]
        operating_cost = metrics["operating_cost"]
        transship_cost = metrics["transship_cost"]
        port_cost      = metrics["port_cost"]
        coverage       = metrics["coverage"]
        total_services = metrics["total_services"]
        unserved_teu   = metrics["unserved_demand"]

        profit_margin_pct  = round(
            weekly_profit / (weekly_profit + total_cost) * 100, 1
        ) if (weekly_profit + total_cost) > 0 else 0
        _mr = self._margin_report(regional_results, final_network_ledger)
        margin_verdict, verdict_label = _mr["verdict"], _mr["label"]
        margin_text, advisory_line = _mr["margin_text"], _mr["advisory_line"]
        cost_per_service   = round(total_cost   / total_services, 0) if total_services else 0
        profit_per_service = round(weekly_profit / total_services, 0) if total_services else 0
        uncovered_pct      = round(100 - coverage, 1)

        region_lines = "\n".join(
            f"  {r['region']:12s}: profit=${r['weekly_profit']:>12,.0f}/wk  "
            f"coverage={r['coverage_percent']:>5.1f}%  "
            f"services={r['services_selected']:>4d}  "
            f"op_cost=${r['operating_cost']:>10,.0f}  "
            f"transship=${r.get('transship_cost', 0):>8,.0f}  "
            f"port=${r.get('port_cost', 0):>8,.0f}"
            for r in regional_results if "region" in r
        )

        top_demands = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)[:5]
        top5_text   = "\n".join(
            f"  {i+1}. Port {d.origin} -> Port {d.destination}: {d.weekly_teu:,.0f} TEU/week"
            for i, d in enumerate(top_demands)
        )

        summary_prompt = (
            f"Senior maritime analyst reviewing GA + MILP optimized network.\n\n"
            f"GLOBAL RESULTS (solver ground truth):\n"
            f"  Services deployed    : {total_services}\n"
            f"  Weekly profit        : ${weekly_profit:,.0f}    | Annual: ${annual_profit:,.0f}\n"
            f"  Profit margin        : {profit_margin_pct}%\n"
            f"  Cost breakdown       : Operating ${operating_cost:,.0f} | "
            f"Transship ${transship_cost:,.0f} | Port ${port_cost:,.0f}\n"
            f"  Profit/service       : ${profit_per_service:,.0f}/wk | "
            f"Cost/service: ${cost_per_service:,.0f}/wk\n"
            f"  Demand coverage      : {coverage:.1f}%   | "
            f"Unserved: {uncovered_pct:.1f}% ({unserved_teu:,.0f} TEU/wk)\n\n"
            f"REGIONAL BREAKDOWN:\n{region_lines}\n\n"
            f"TOP-5 GLOBAL CORRIDORS:\n{top5_text}\n\n"
            f"STRICT FORMAT - no hedging language:\n"
            f"Verdict: <Good | Moderate | Poor>\n"
            f"  [One sentence: cite profit margin {profit_margin_pct}% and coverage {coverage:.1f}%]\n\n"
            f"Strengths:\n"
            f"- [Cite weekly profit ${weekly_profit:,.0f} and per-service efficiency]\n"
            f"- [Cite transship + port cost breakdown relative to operating cost]\n\n"
            f"Weaknesses:\n"
            f"- [Cite unserved {uncovered_pct:.1f}% = {unserved_teu:,.0f} TEU/wk revenue loss]\n"
            f"- [Cite cost/service ${cost_per_service:,.0f} sustainability concern]\n\n"
            f"Priority Actions:\n"
            f"- [Name lowest-coverage region with its coverage % and service count target]\n"
            f"- [Name top unserved corridor (port IDs + TEU) and specific remediation]"
        )

        
        lowest = min(
            (r for r in regional_results if "region" in r),
            key=lambda r: r.get("coverage_percent", 100),
            default={},
        )
        executive_summary = (
            f"Verdict: {verdict_label}\n"
            f"  Profit margin {margin_text} with {coverage:.1f}% demand coverage.\n"
            f"{advisory_line}\n"
            f"Strengths:\n"
            f"- Weekly profit ${weekly_profit:,.0f} across {total_services} services "
            f"(${profit_per_service:,.0f}/service/week).\n"
            f"- Cost breakdown: operating ${operating_cost:,.0f}, transship "
            f"${transship_cost:,.0f}, port ${port_cost:,.0f}/week.\n\n"
            f"Weaknesses:\n"
            f"- {uncovered_pct:.1f}% demand ({unserved_teu:,.0f} TEU/week) unserved.\n"
            f"- Cost per service ${cost_per_service:,.0f}/week limits expansion.\n\n"
            f"Priority Actions:\n"
            f"- Expand {lowest.get('region', 'lowest-coverage region')} "
            f"(currently {lowest.get('coverage_percent', 0):.1f}% coverage).\n"
            f"- Route capacity to Port {top_demands[0].origin} -> Port "
            f"{top_demands[0].destination} ({top_demands[0].weekly_teu:,.0f} TEU/week)."
        )

        if not (final_network_ledger and final_network_ledger.get("verified")):
            # never present unreconciled regional numbers as verified economics
            executive_summary = (
                "ACCOUNTING NOT VERIFIED: the figures below come from unreconciled "
                "regional results; profit and margin are not verified economics.\n"
                + executive_summary
            )

        logger.info("orchestrator_complete")

        # Track health completion
        health_tracker.optimizer_completed(success=True)

        # Aggregate selected services from all regions
        all_selected_services = []
        for r in regional_results:
            if "selected_services" in r:
                all_selected_services.extend(r["selected_services"])

        # Send final callback
        if self.callback:
            self.callback("pipeline_completed", {
                "data": {
                    "results": {
                        "weeklyProfit": metrics["weekly_profit"],
                        "annualProfit": metrics["annual_profit"],
                        "coverage": metrics["coverage"],
                        "totalServices": metrics["total_services"],
                        "margin": profit_margin_pct,
                        "operatingCost": metrics["operating_cost"],
                        "unserved": metrics["unserved_demand"],
                        "convergenceScore": feedback.get("convergence_score", 0),
                        "iterations": len(self.iteration_audit),
                        "regionalResults": regional_results,
                        "selected_services": all_selected_services
                    }
                }
            })

        # ⚡Aggregate LLM runtime metrics
        coordinator_metrics = decision_output.get("llm_runtime_metrics", {})
        # Derive servicegen success from archetype_params across regions
        svcgen_ai_count = 0
        svcgen_total = 0
        for r in regional_results:
            ap = r.get("archetype_params", {})
            arch_mix = ap.get("archetype_mix", {}) if isinstance(ap, dict) else {}
            svcgen_total += 1
            # Default archetype mix means fallback was used
            is_default = (
                arch_mix.get("direct_ratio") == 0.60 and
                arch_mix.get("hub_loop_ratio") == 0.15 and
                arch_mix.get("feeder_ratio") == 0.20 and
                arch_mix.get("trunk_ratio") == 0.05
            )
            if not is_default:
                svcgen_ai_count += 1

        # Count coordinator LLM success: decisions with real actions
        decisions = decision_output.get("decisions", {})
        coord_ai = bool(
            decisions.get("actions") and
            "Rule-based fallback" not in decisions.get("notes", "")
        )

        llm_runtime_metrics = {
            "llm_calls": coordinator_metrics.get("llm_calls", 0) + svcgen_total,
            "coordinator_llm_calls": coordinator_metrics.get("llm_calls", 0),
            "coordinator_json_parse_success": coordinator_metrics.get("json_parse_success", 0),
            "coordinator_validator_executed": coordinator_metrics.get("validator_executed", 0),
            "coordinator_fallback_count": coordinator_metrics.get("fallback_count", 0),
            "coordinator_ai_generated": coord_ai,
            "servicegen_regions": svcgen_total,
            "servicegen_ai_count": svcgen_ai_count,
            "servicegen_fallback_count": svcgen_total - svcgen_ai_count,
        }

        # provider-aware runtime telemetry aggregated from the
        # actuation ledger.
        acts = actuation_ledger.all()
        providers_used: Dict[str, int] = {}
        models_used: Dict[str, int] = {}
        coord_provider = ""
        coord_model = ""
        coord_latency_sec = 0.0
        coord_attempts = 0
        coord_fallbacks = 0
        coord_429 = 0
        coord_decision_source = "rule-based"
        coord_decision_consumed = False
        selector_provider = ""
        selector_model = ""
        selector_latency_sec = 0.0
        selector_decision_source = "rule-based"
        selector_decision_consumed = False
        for a in acts:
            if a.provider:
                providers_used[a.provider] = providers_used.get(a.provider, 0) + 1
            if a.model:
                models_used[a.model] = models_used.get(a.model, 0) + 1
            if a.component.startswith("coordinator_"):
                coord_provider = a.provider or coord_provider
                coord_model = a.model or coord_model
                coord_latency_sec += a.latency_sec
                coord_attempts += a.attempts
                coord_fallbacks += a.fallback_uses
                coord_429 += a.error_429
                if a.decision_source == "llm":
                    coord_decision_source = "llm"
                coord_decision_consumed = coord_decision_consumed or a.decision_consumed
            elif a.component == "iteration_selector":
                selector_provider = a.provider or selector_provider
                selector_model = a.model or selector_model
                selector_latency_sec += a.latency_sec
                if a.decision_source == "llm":
                    selector_decision_source = "llm"
                selector_decision_consumed = (
                    selector_decision_consumed or a.decision_consumed
                )

        coordinator_record = {
            "coordinator_provider":              coord_provider,
            "coordinator_model":                 coord_model,
            "coordinator_llm_attempts":          coord_attempts,
            "coordinator_llm_successes":         sum(1 for a in acts if a.component.startswith("coordinator_") and a.successes),
            "coordinator_llm_failures":          sum(1 for a in acts if a.component.startswith("coordinator_") and a.failures),
            "coordinator_429_count":             coord_429,
            "coordinator_fallback":              coord_fallbacks > 0 or coord_decision_source == "rule-based",
            "coordinator_fallback_reason":       "all_providers_failed" if coord_decision_source == "rule-based" else "",
            "coordinator_llm_latency_sec":       round(coord_latency_sec, 4),
            "coordinator_total_latency_sec":     round(coord_latency_sec, 4),
            "coordinator_decision_source":       coord_decision_source,
            "coordinator_decision_consumed":     coord_decision_consumed,
        }
        iteration_selector_record = {
            "iteration_selector_provider":        selector_provider,
            "iteration_selector_model":           selector_model,
            "iteration_selector_llm_attempts":    sum(1 for a in acts if a.component == "iteration_selector" and a.attempts),
            "iteration_selector_llm_latency_sec": round(selector_latency_sec, 4),
            "iteration_selector_fallback":        selector_decision_source == "rule-based",
            "iteration_selector_fallback_reason": "" if selector_decision_source == "llm" else "llm_invalid_or_unavailable",
            "iteration_selected":                 best_iteration,
            "selection_source":                   iteration_selection.get("selection_method", "unknown"),
        }
        # Service generator aggregation
        sg_acts = [a for a in acts if a.component.startswith("service_generator_")]
        service_generator_record = {
            "service_generator_provider":          sg_acts[0].provider if sg_acts else "",
            "service_generator_model":             sg_acts[0].model if sg_acts else "",
            "service_generator_ai_attempts":       sum(a.attempts for a in sg_acts),
            "service_generator_ai_successes":      sum(a.successes for a in sg_acts),
            "service_generator_fallbacks":         sum(a.fallback_uses for a in sg_acts),
            "service_generator_decision_source":   "llm" if any(a.decision_source == "llm" for a in sg_acts) else "rule-based",
            "service_generator_decision_consumed": all(a.decision_consumed for a in sg_acts) if sg_acts else False,
        }

        # Provider telemetry snapshot from the router.
        provider_telemetry = llm_client.telemetry()

        # Attach end-to-end pipeline runtime to summary_metrics.
        _elapsed = round(time.perf_counter() - _t0, 1)
        metrics.setdefault("total_runtime", float(_elapsed))

        _ledger_ok = bool(final_network_ledger and final_network_ledger.get("verified"))
        return {
            "orchestrator":      self.name,
            # "complete" only when the final network was independently verified;
            # otherwise the accounting is explicitly incomplete (never a silent success)
            "status":            "complete" if _ledger_ok else "incomplete_accounting",
            "network_ledger":    final_network_ledger or {
                "verified": False, "status": "not_run",
                "message": "no verified network ledger was produced",
            },
            "problem_analysis":  analysis,
            "regional_results":  regional_results,
            "decision_output":   decision_output,
            "executive_summary": executive_summary,
            "summary_metrics":   metrics,
            "iteration_audit":   self.iteration_audit,
            "iterations_run":    len(self.iteration_audit),
            "selected_services": final_services if final_services else all_selected_services,
            "all_selected_services": all_selected_services,
            "iteration_results":       self.iteration_results,
            "iteration_selection":     iteration_selection,
            "best_iteration":          best_iteration,
            "final_selected_iteration": best_iteration,
            "health_status":     health_tracker.get_health_status(),
            "consensus_result":  self._previous_consensus or {},
            "shared_context":    self.shared_context.to_dict() if hasattr(self.shared_context, 'to_dict') else {},
            "maritime_intelligence": (
                self._maritime_features.to_dict()
                if self._maritime_features is not None else None
            ),
            "llm_runtime_metrics": llm_runtime_metrics,
            "llm_runtime_aggregate": {
                "providers_used":        providers_used,
                "models_used":           models_used,
                "coordinator":           coordinator_record,
                "iteration_selector":    iteration_selector_record,
                "service_generator":     service_generator_record,
                "provider_telemetry":    provider_telemetry,
                "actuation_ledger":      actuation_ledger.summary(),
            },
        }