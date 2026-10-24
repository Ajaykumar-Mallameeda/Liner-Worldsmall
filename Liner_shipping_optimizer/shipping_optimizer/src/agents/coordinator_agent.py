from __future__ import annotations
import json
import re
import time
from typing import Any, Dict, List, Optional
from src.agents.base   import BaseAgent
from src.utils.config  import Config
from src.utils.logger  import logger
from src.validation.weight_validator import validate_weight_adjustments
from src.llm.actuation import actuation_ledger
from src.llm.client import llm_client
from src.network.metrics import (
    MARGIN_AT_OR_ABOVE_TARGET, MARGIN_TARGET_PCT, MARGIN_UNVERIFIED,
    canonical_network_economics, classify_margin,
)


# ── Thresholds (tunable) ─────────────────────────────────────────────────
COVERAGE_TARGET        = 70.0   # % — below this a rerun is triggered
PROFIT_FLOOR           = 0.0    # weekly USD — negative profit triggers rerun
MAX_CONFLICTS_ALLOWED  = 0      # any overlap triggers resolution pass
MAX_RERUN_ITERATIONS   = 3      # hard cap passed in from orchestrator
# Margin on revenue (all-in cost basis) below which the evaluation does not award
# the efficiency point. 15 % is the "Moderate" verdict floor already used by the
# orchestrator/regional summaries.  It is an ADVISORY verdict band (owner decision,):
# the canonical definition and its classifier live in
# ``src.network.metrics`` (``MARGIN_TARGET_PCT``, ``classify_margin``); the name is
# re-exported here because callers import it from this module.  The band does not
# drive reruns, iteration selection, feasibility, accounting status or solver status.


def _usd(v: Any) -> str:
    return f"${v:,.0f}" if isinstance(v, (int, float)) else "n/a"


def _pct(v: Any) -> str:
    return f"{v:.1f}%" if isinstance(v, (int, float)) else "n/a (not verified)"


class CoordinatorAgent(BaseAgent):
    """
    Global Decision Agent — coordinates regional results, resolves conflicts,
    and emits machine-usable feedback gradients for the orchestrator.
    """

    def __init__(self, name: str = "coordinator", model: str = None):
        super().__init__(
            name=name,
            role="Global Decision Agent",
            model=model or Config.ORCHESTRATOR_MODEL,
            llm_role="coordinator",
        )
        self._metrics = {
            "llm_calls": 0,
            "llm_success": 0,
            "json_parse_success": 0,
            "validator_executed": 0,
            "fallback_count": 0,
        }

    def get_system_prompt(self) -> str:
        return (
            "You are a global shipping network decision agent act as maritime analyst from global liner shipping company.\n\n"
            "You ANALYZE, DECIDE, and CORRECT — not summarise.\n\n"
            "Rules:\n"
            "- Every decision must cite a specific number.\n"
            "- Actions must be concrete and measurable.\n"
            "- Output valid JSON only when requested.\n"
            "- No hedging language."
        )

    # ================================================================
    # PUBLIC ENTRY POINT
    # ================================================================

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        regional_solutions: List[Dict] = input_data["regional_solutions"]
        iteration: int                 = input_data.get("iteration", 0)

        logger.info(
            "coordinator_started",
            num_regions=len(regional_solutions),
            iteration=iteration,
        )

        t0 = time.perf_counter()

        # 1. Conflict detection
        conflicts = self._identify_conflicts(regional_solutions)

        # 2. Conflict resolution (mutates chromosomes in-place)
        resolution_log = self._resolve_conflicts(conflicts, regional_solutions)

        # 3. Global metrics (economics from the verified network ledger when supplied)
        global_metrics = self._calculate_global_metrics(
            regional_solutions, input_data.get("network_ledger")
        )

        # 4. System evaluation
        evaluation = self._evaluate_system(global_metrics, conflicts)

        # 5. Structured LLM decisions
        decisions = self._generate_decisions(
            conflicts, regional_solutions, global_metrics, evaluation, iteration
        )

        # 6. Machine-usable feedback gradients
        feedback = self._generate_feedback_signals(
            conflicts, global_metrics, evaluation, iteration
        )

        # 7. Phase L + M — actuation ledger for this iteration's Coordinator call.
        act = actuation_ledger.begin(f"coordinator_iter_{iteration}")
        rec = llm_client.last_response
        if rec is not None:
            act.provider = rec.provider
            act.model = rec.model
            act.role = rec.role or "coordinator"
            act.attempts = 1
            if rec.status == "ok" and rec.error_type.value == "none":
                act.successes = 1
            else:
                act.failures = 1
            if rec.fallback:
                act.fallback_uses = 1
            et = rec.error_type.value
            if et == "http_429":            act.error_429 = 1
            elif et == "timeout":           act.error_timeout = 1
            elif et == "connection":        act.error_connection = 1
            elif et == "auth":              act.error_auth = 1
            elif et == "invalid_model":     act.error_invalid_model = 1
            elif et == "invalid_json":      act.error_invalid_json = 1
            else:                           act.error_unknown = 1
            act.latency_sec = round(rec.latency_ms / 1000.0, 4)
        act.decision_source = "llm" if decisions.get("weight_adjustments") and "Rule-based fallback" not in decisions.get("notes", "") else "rule-based"
        act.decision_consumed = True
        act.ai_generated = act.decision_source == "llm"
        act.total_latency_sec = round(time.perf_counter() - t0, 4)

        logger.info(
            "coordinator_complete",
            profit=global_metrics["total_profit"],
            coverage=global_metrics["average_coverage"],
            conflicts=len(conflicts),
            needs_rerun=feedback["needs_rerun"],
            rerun_reason=feedback["rerun_reason"],
            decision_source=act.decision_source,
            ai_generated=act.ai_generated,
        )

        return {
            "agent":           self.name,
            "iteration":       iteration,
            "status":          "evaluated",
            "global_metrics":  global_metrics,
            "evaluation":      evaluation,
            "conflicts":       conflicts,
            "resolution_log":  resolution_log,
            "decisions":       decisions,
            "feedback":        feedback,
            "llm_runtime_metrics": dict(self._metrics),
            "llm_actuation":   act.to_dict(),
        }

    # ================================================================
    # 1. CONFLICT DETECTION
    # ================================================================

    def _identify_conflicts(self, regional_solutions: List[Dict]) -> List[Dict]:
        """
        Detect services deployed in more than one region.

        Handles two chromosome formats:
          A) binary list  [0, 1, 0, 1, ...]  (index = service position)
          B) id list      ["SVC_001", "SVC_042", ...]
        """
        conflicts: List[Dict] = []
        service_to_regions: Dict[Any, List[str]] = {}

        for solution in regional_solutions:
            region   = solution.get("region", "unknown")
            chrom    = solution.get("chromosome", {})
            services = chrom.get("services", [])

            if not services:
                services = [
                    s.get("id") for s in solution.get("selected_services", [])
                    if s.get("id") is not None
                ]
                if not services:
                    continue
            # Detect format
            if isinstance(services[0], int):
                # Format A: binary list
                selected_ids = [
                    i for i, flag in enumerate(services) if flag == 1
                ]
            else:
                # Format B: explicit id list
                selected_ids = list(services)

            for sid in selected_ids:
                if sid not in service_to_regions:
                    service_to_regions[sid] = []
                service_to_regions[sid].append(region)

        for sid, regions in service_to_regions.items():
            if len(regions) > 1:
                conflicts.append({
                    "type":       "service_overlap",
                    "service_id": sid,
                    "regions":    regions,
                })

        logger.info("conflicts_detected", count=len(conflicts))
        return conflicts

    # ================================================================
    # 2. CONFLICT RESOLUTION
    # ================================================================

    def _resolve_conflicts(
        self,
        conflicts: List[Dict],
        regional_solutions: List[Dict],
    ) -> List[Dict]:
        """
        For each overlap, drop the service from the LOWER-profit region.
        Mutates chromosome in the regional_solutions list (used in next GA pass).
        Returns an audit log entry per conflict resolved.
        """
        if not conflicts:
            return []

        # Index solutions by region for O(1) lookup
        by_region = {s["region"]: s for s in regional_solutions}
        resolution_log: List[Dict] = []

        for conflict in conflicts:
            sid     = conflict["service_id"]
            regions = conflict["regions"]

            # Sort by profit — keep in highest-profit region
            sorted_regions = sorted(
                regions,
                key=lambda r: by_region.get(r, {}).get("weekly_profit", 0),
                reverse=True,
            )
            keep_region = sorted_regions[0]
            drop_regions = sorted_regions[1:]

            for drop_r in drop_regions:
                sol   = by_region.get(drop_r)
                if not sol:
                    continue
                chrom = sol.get("chromosome", {})
                svcs  = chrom.get("services", [])

                if not svcs:
                    svcs = [
                        s.get("id") for s in sol.get("selected_services", [])
                        if s.get("id") is not None
                    ]
                    if not svcs:
                        continue

                if isinstance(svcs[0], int):
                    # Binary format: zero out the flag
                    if isinstance(sid, int) and sid < len(svcs):
                        svcs[sid] = 0
                else:
                    # ID format: remove the id
                    if sid in svcs:
                        svcs.remove(sid)

                resolution_log.append({
                    "service_id":    sid,
                    "kept_in":       keep_region,
                    "removed_from":  drop_r,
                    "keep_profit":   by_region.get(keep_region, {}).get("weekly_profit", 0),
                    "drop_profit":   sol.get("weekly_profit", 0),
                })

        logger.info("conflicts_resolved", resolved=len(resolution_log))
        return resolution_log

    # ================================================================
    # 3. GLOBAL METRICS
    # ================================================================

    def _calculate_global_metrics(
        self,
        regional_solutions: List[Dict],
        network_ledger: Optional[Dict] = None,
    ) -> Dict:
        """Network KPIs for one iteration.

        Economics follow ``src.network.metrics.canonical_network_economics``:
        ``total_cost`` is the ALL-IN weekly cost (hire + fuel + port + handling +
        transshipment), ``profit_margin_pct`` is profit / revenue, both from the
        verified ledger when one is supplied.  The vessel-hire component is kept
        under its own name (``vessel_hire_cost``) - it used to be reported here as
        ``total_cost``.
        """
        if not regional_solutions:
            return {
                "total_services": 0, "total_profit": 0.0, "annual_profit": 0.0,
                "average_coverage": 0.0, "min_coverage": 0.0,
                "max_coverage": 0.0, "total_cost": 0.0,
                "total_satisfied_demand": 0.0, "total_unserved_demand": 0.0,
                "vessel_hire_cost": 0.0, "revenue": None, "profit_margin_pct": None,
                "accounting_status": "not_evaluated", "accounting_verified": None,
                "accounting_basis": "regional_sum",
                "accounting_issues": ["no regional solutions"],
            }

        econ = canonical_network_economics(regional_solutions, network_ledger)
        coverages        = [s.get("coverage_percent", 0.0) for s in regional_solutions]
        total_profit     = sum(s.get("weekly_profit", 0.0)        for s in regional_solutions)
        total_satisfied  = sum(s.get("satisfied_demand", 0.0)     for s in regional_solutions)
        total_unserved   = sum(s.get("unserved_demand", 0.0)      for s in regional_solutions)
        total_services   = sum(s.get("services_selected", 0)      for s in regional_solutions)

        average_regional_coverage = (
            sum(coverages) / len(coverages) if coverages else 0.0
        )
        # Global demand weighting: each region's satisfied_demand scaled by
        # its true demand share.  When regional demand weights are unavailable
        # we fall back to the simple satisfied/total ratio.
        true_global_demand = (
            (total_satisfied + total_unserved) if (total_satisfied + total_unserved) > 0
            else 0.0
        )
        global_demand_weighted_coverage = (
            total_satisfied / true_global_demand * 100
            if true_global_demand > 0 else 0.0
        )

        return {
            "total_services":          total_services,
            "total_profit":            total_profit,
            "annual_profit":           total_profit * 52,
            "average_regional_coverage":       round(average_regional_coverage, 4),
            "global_demand_weighted_coverage": round(global_demand_weighted_coverage, 4),
            "average_coverage":        round(average_regional_coverage, 4),  
            "min_coverage":            min(coverages) if coverages else 0.0,
            "max_coverage":            max(coverages) if coverages else 0.0,
            "coverage_variance":       (
                (max(coverages) - min(coverages)) if coverages else 0.0
            ),
            # --- economics (canonical, all-in; see src/network/metrics.py) ---------
            "revenue":                 econ["revenue"],
            "total_cost":              econ["total_cost"],
            "vessel_hire_cost":        econ["vessel_hire_cost"],
            "profit_margin_pct":       econ["profit_margin_pct"],
            "accounting_status":       econ["accounting_status"],
            "accounting_verified":     econ["accounting_verified"],
            "accounting_basis":        econ["accounting_basis"],
            "accounting_issues":       econ["accounting_issues"],
            "total_satisfied_demand":  total_satisfied,
            "total_unserved_demand":   total_unserved,
        }

    # ================================================================
    # 4. SYSTEM EVALUATION
    # ================================================================

    def _evaluate_system(self, metrics: Dict, conflicts: List[Dict]) -> Dict:
        score   = 0
        reasons = []

        regional_coverage = metrics.get(
            "average_regional_coverage", metrics.get("average_coverage", 0.0)
        )

        if regional_coverage >= COVERAGE_TARGET:
            score += 1
        else:
            reasons.append(
                f"regional avg coverage {regional_coverage:.1f}% < target {COVERAGE_TARGET}%"
            )

        if metrics["total_profit"] > PROFIT_FLOOR:
            score += 1
        else:
            reasons.append(f"profit ${metrics['total_profit']:,.0f} <= floor ${PROFIT_FLOOR:,.0f}")

        # Economic efficiency on the ALL-IN cost basis: profit margin on revenue.
        # (This used to compare total_cost < total_profit, which needs a >50 %
        # margin and, with total_cost = vessel hire only, was not an economic test.)
        # The 15 % target is an advisory band: the point is awarded at or above it, the
        # shortfall is only *reported* (``margin_verdict``) and never rejects a feasible,
        # verified, positive-profit network.
        margin = metrics.get("profit_margin_pct")
        margin_verdict = classify_margin(margin, metrics.get("accounting_verified"))
        if margin_verdict["band"] == MARGIN_AT_OR_ABOVE_TARGET:
            score += 1
        elif margin is None:
            reasons.append(
                "profit margin unavailable (accounting "
                f"{metrics.get('accounting_status', 'not_evaluated')})"
            )
        elif margin_verdict["band"] == MARGIN_UNVERIFIED:
            # a margin exists but its ledger was not verified: no efficiency point
            reasons.append(
                f"profit margin {margin:.1f}% not independently verified (accounting "
                f"{metrics.get('accounting_status', 'not_evaluated')})"
            )
        else:
            reasons.append(
                f"profit margin {margin:.1f}% < target {MARGIN_TARGET_PCT}% (advisory)"
            )

        if len(conflicts) <= MAX_CONFLICTS_ALLOWED:
            score += 1
        else:
            reasons.append(f"{len(conflicts)} service overlap conflicts detected")

        if metrics["coverage_variance"] <= 20.0:
            score += 1
        else:
            reasons.append(
                f"coverage variance {metrics['coverage_variance']:.1f}% — "
                "regions imbalanced"
            )

        status = (
            "good"     if 5 >= score >= 3 else
            "moderate" if score == 2.5 else
            "poor"
        )

        return {
            "score":   score,
            "max":     5,
            "status":  status,
            "reasons": reasons,
            "accounting_verified": metrics.get("accounting_verified"),
            # the advisory margin band, reported separately from the composite score
            "margin_verdict": margin_verdict,
        }

    # ================================================================
    # 5. STRUCTURED LLM DECISIONS
    # ================================================================

    def _generate_decisions(
        self,
        conflicts:           List[Dict],
        regional_solutions:  List[Dict],
        metrics:             Dict,
        evaluation:          Dict,
        iteration:           int = 0,
    ) -> Dict:
        """
        Returns a structured dict with 'actions' and 'priorities'.
        LLM output is parsed as JSON; falls back to rule-based decisions
        so the orchestrator always gets machine-usable data.
        """
        weak_regions = [
            s for s in regional_solutions
            if s.get("coverage_percent", 0) < COVERAGE_TARGET
        ]
        weak_summary = "; ".join(
            f"{s['region']} coverage={s.get('coverage_percent', 0):.1f}%"
            for s in weak_regions
        )

        prompt = f"""
Global shipping network decision — iteration {iteration} results:

Metrics:
  Total profit   : ${metrics['total_profit']:,.0f}/week
  Annual profit  : ${metrics['annual_profit']:,.0f}
  Avg regional coverage    : {metrics.get('average_regional_coverage', 0.0):.1f}%
  Global demand-weighted coverage : {metrics.get('global_demand_weighted_coverage', 0.0):.1f}%
  Min coverage   : {metrics['min_coverage']:.1f}%
  Coverage variance: {metrics['coverage_variance']:.1f}%
  Revenue        : {_usd(metrics.get('revenue'))}/week
  Total cost (all-in: hire+fuel+port+handling+transshipment) : {_usd(metrics.get('total_cost'))}/week
  Vessel hire only (component of the above) : {_usd(metrics.get('vessel_hire_cost'))}/week
  Profit margin on revenue : {_pct(metrics.get('profit_margin_pct'))} (accounting: {metrics.get('accounting_status', 'not_evaluated')})
  Evaluation     : {evaluation['status']} (score {evaluation['score']}/{evaluation['max']})

Conflicts detected: {len(conflicts)}
Weak regions (coverage < {COVERAGE_TARGET}%): {weak_summary or 'none'}

Return ONLY valid JSON (no markdown, no preamble):
{{
  "actions": [
    {{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}}
  ],
  "priorities": ["<priority 1>", "<priority 2>"],
  "weight_adjustments": {{
    "profit_weight":   <0.0-1.0>,
    "coverage_weight": <0.0-1.0>,
    "cost_weight":     <0.0-1.0>
  }},
  "notes": "<one sentence with specific numbers>"
}}
"""
        raw = self.call_llm(prompt, temperature=0.1)
        self._metrics["llm_calls"] += 1
        logger.info("p1e_raw_coord", raw_len=len(raw), raw_preview=raw[:200])
        decisions = self._parse_json_safe(raw)

        if decisions:
            self._metrics["json_parse_success"] += 1

        if decisions is not None and "weight_adjustments" in decisions:
            self._metrics["validator_executed"] += 1
            validated = validate_weight_adjustments(
                decisions["weight_adjustments"],
                iteration=0,
                source="coordinator_llm",
            )
            decisions["weight_adjustments"] = validated
            logger.info(
                "coordinator_weight_validated",
                tag="AI_VALIDATED",
                weights=validated,
            )

        if not decisions or "actions" not in decisions:
            self._metrics["fallback_count"] += 1
            # Rule-based fallback — always machine-usable
            actions = []
            regional_coverage = metrics.get(
                "average_regional_coverage", metrics.get("average_coverage", 0.0)
            )
            if regional_coverage < COVERAGE_TARGET:
                for s in weak_regions:
                    actions.append({
                        "region":        s["region"],
                        "action":        "increase coverage_weight in GA",
                        "expected_gain": f"+{COVERAGE_TARGET - s.get('coverage_percent',0):.1f}% coverage",
                    })
            if conflicts:
                actions.append({
                    "region":        "global",
                    "action":        "re-run GA with resolved chromosome",
                    "expected_gain": f"eliminate {len(conflicts)} service overlaps",
                })

            # Derive weight adjustments from regional coverage gap (feedback loop target)
            cov_gap   = max(0, COVERAGE_TARGET - regional_coverage)
            cov_boost = min(0.2, cov_gap / 100.0)
            decisions = {
                "actions":    actions,
                "priorities": [
                    f"Raise regional avg coverage from {regional_coverage:.1f}% to {COVERAGE_TARGET}%",
                    f"Eliminate {len(conflicts)} conflict(s)",
                ],
                "weight_adjustments": {
                    "profit_weight":   max(0.3, 0.5 - cov_boost),
                    "coverage_weight": min(0.6, 0.4 + cov_boost),
                    "cost_weight":     0.1,
                },
                "notes": (
                    f"Rule-based fallback: regional coverage {regional_coverage:.1f}%, "
                    f"profit ${metrics['total_profit']:,.0f}/week, "
                    f"{len(conflicts)} conflicts."
                ),
            }

        # Validate fallback weights too
        decisions["weight_adjustments"] = validate_weight_adjustments(
            decisions["weight_adjustments"],
            iteration=0,
            source="rule-based",
        )
        logger.info(
            "coordinator_weight_validated",
            tag="AI_FALLBACK",
            weights=decisions["weight_adjustments"],
        )

        return decisions

    # ================================================================
    # 6. FEEDBACK SIGNALS — GRADIENT (not just binary)
    # ================================================================

    def _generate_feedback_signals(
        self,
        conflicts:      List[Dict],
        metrics:        Dict,
        evaluation:     Dict,
        iteration:      int,
    ) -> Dict:
        """
        Returns gradient signals so the orchestrator can adjust GA weights
        proportionally, not just flip a rerun flag.

        Fields:
          needs_rerun        bool   — should orchestrator loop again?
          rerun_reason       str    — human-readable reason with numbers
          coverage_gap       float  — how far below target (0 if above)
          profit_gap         float  — how far below floor (0 if above)
          conflict_severity  int    — number of unresolved conflicts
          weight_adjustments dict   — direct GA weight deltas to apply
          convergence_score  float  — 0.0 (bad) → 1.0 (converged)
        """
        coverage   = metrics.get(
            "average_regional_coverage", metrics.get("average_coverage", 0.0)
        )
        global_cov = metrics.get("global_demand_weighted_coverage", coverage)
        profit     = metrics["total_profit"]
        coverage_gap      = max(0.0, COVERAGE_TARGET - coverage)
        profit_gap        = max(0.0, PROFIT_FLOOR - profit)
        conflict_severity = len(conflicts)

        # Determine rerun need
        rerun_reasons = []
        if coverage_gap > 0:
            rerun_reasons.append(
                f"coverage {coverage:.1f}% is {coverage_gap:.1f}pp below {COVERAGE_TARGET}% target"
            )
        if profit_gap > 0:
            rerun_reasons.append(
                f"profit ${profit:,.0f} is ${profit_gap:,.0f} below floor"
            )
        if conflict_severity > MAX_CONFLICTS_ALLOWED:
            rerun_reasons.append(
                f"{conflict_severity} service overlap conflict(s) remain"
            )

        # Hard cap on iterations to prevent infinite loops
        at_iteration_cap = iteration >= MAX_RERUN_ITERATIONS - 1
        needs_rerun      = bool(rerun_reasons) and not at_iteration_cap

        if at_iteration_cap and rerun_reasons:
            rerun_reasons.append(
                f"[CAPPED] max iterations ({MAX_RERUN_ITERATIONS}) reached — halting despite gaps"
            )

        rerun_reason = "; ".join(rerun_reasons) if rerun_reasons else "converged"

        # Gradient weight adjustments (proportional to gap)
        cov_boost  = min(0.25, coverage_gap / 100.0 * 1.5)
        prof_boost = min(0.15, profit_gap / 1_000_000 * 0.1) if profit_gap > 0 else 0.0

        weight_adjustments = {
            "profit_weight":   round(max(0.20, 0.50 - cov_boost + prof_boost), 3),
            "coverage_weight": round(min(0.70, 0.40 + cov_boost), 3),
            "cost_weight":     round(max(0.05, 0.10 - prof_boost), 3),
        }

        # Normalise weights to sum = 1.0
        total = sum(weight_adjustments.values())
        weight_adjustments = {k: round(v / total, 3) for k, v in weight_adjustments.items()}

        # Convergence score: 1.0 = perfect, 0.0 = worst case
        cov_score      = min(1.0, coverage / COVERAGE_TARGET)
        profit_score   = 1.0 if profit > PROFIT_FLOOR else 0.0
        conflict_score = 1.0 if conflict_severity == 0 else max(0.0, 1 - conflict_severity * 0.2)
        convergence_score = round((cov_score + profit_score + conflict_score) / 3.0, 3)

        return {
            "needs_rerun":        needs_rerun,
            "rerun_reason":       rerun_reason,
            "coverage_gap":       round(coverage_gap, 2),
            "profit_gap":         round(profit_gap, 2),
            "conflict_severity":  conflict_severity,
            "weight_adjustments": weight_adjustments,
            "convergence_score":  convergence_score,
            "iteration":          iteration,
            "at_iteration_cap":   at_iteration_cap,
            "average_regional_coverage":       round(coverage, 4),
            "global_demand_weighted_coverage": round(global_cov, 4),
            # Legacy binary flags (backward-compat)
            "conflict_count":     conflict_severity,
            "low_coverage":       coverage_gap > 0,
            "low_profit":         profit_gap > 0,
        }

    # ================================================================
    # HELPERS
    # ================================================================

    def call_llm_as_iteration_selector(self, user_message: str, temperature: float = 0.1) -> str:
        """Call the LLM with the ``iteration_selector`` role.

        The orchestrator passes the coordinator's ``call_llm`` to the
        iteration selector; this entrypoint lets the selector pick the
        correct per-provider model without the orchestrator needing to
        know about provider roles.
        """
        prev_role = self.llm_role
        self.llm_role = "iteration_selector"
        try:
            return self.call_llm(user_message, temperature)
        finally:
            self.llm_role = prev_role

    @staticmethod
    def _parse_json_safe(raw: str) -> Dict:
        """Extract JSON from LLM output, stripping markdown fences."""
        if not raw:
            return {}
        text = raw.strip()
        # Strip ```json ... ``` or ``` ... ```
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            # Try to extract first {...} block
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return {}