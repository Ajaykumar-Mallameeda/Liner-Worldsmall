"""
Iteration Candidate Selection

Every completed optimization iteration is a self-contained candidate solution.
The pipeline MUST NOT treat "latest iteration" as "best solution".  This
module implements the multi-objective candidate evaluation that selects the
best iteration and makes that selected iteration the final network result.

Responsibilities:

  1. Build a per-iteration scorecard across all relevant objectives.
  2. Run Pareto dominance analysis — a candidate is dominated only when another
     iteration is no worse on every objective AND strictly better on at least
     one; non-dominated candidates all remain eligible.
  3. Optionally ask the Coordinator/LLM to reason over the complete candidate
     set under a strict structured JSON contract (it must not invent an
     iteration, must not invent metrics, and must not override hard
     constraints).
  4. Validate the LLM selection against hard constraints.
  5. Fall back to a deterministic multi-objective selector when the LLM is
     unavailable, returns invalid JSON, or selects an invalid candidate.

The final network result is ALWAYS constructed from the selected iteration's
own snapshot — never automatically from the latest iteration.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from src.utils.logger import logger
from src.llm.actuation import actuation_ledger
from src.llm.client import llm_client
from src.network.metrics import classify_margin

# ---------------------------------------------------------------------------
# Objective directions
# ---------------------------------------------------------------------------
#   +1  → higher is better
#   -1  → lower is better
#    0  → context-dependent (not scored directly)
OBJECTIVE_DIRECTIONS: Dict[str, int] = {
    "weekly_profit":                   +1,
    "annual_profit":                   +1,
    "profit_margin_pct":               +1,
    "average_regional_coverage":       +1,
    "global_demand_weighted_coverage": +1,
    "convergence_score":               +1,
    # ``total_cost`` is the ALL-IN weekly cost (hire + fuel + port + handling +
    # transshipment).  ``operating_cost`` is only its vessel-hire component; it is
    # kept for display and is NOT an objective (F-15).
    "total_cost":                      -1,
    "operating_cost":                  -1,
    "unserved_demand":                 -1,
    "negative_profit_regions":         -1,
    "constraint_violations":           -1,
    "conflict_count":                  -1,
    "services_deployed":               0,
}

# Objectives used for Pareto dominance (network-quality objectives).
# services_deployed is deliberately excluded — more services is NOT inherently
# better; network quality is what matters.
PARETO_OBJECTIVES: List[str] = [
    "weekly_profit",
    "global_demand_weighted_coverage",
    "total_cost",
    "unserved_demand",
    "negative_profit_regions",
    "constraint_violations",
    "conflict_count",
]

# Weighted scoring — uses the project's active objective weights (profit_first).
DEFAULT_SCORING_WEIGHTS: Dict[str, float] = {
    "weekly_profit":                   0.60,
    "global_demand_weighted_coverage": 0.25,
    "total_cost":                      0.15,
}

# Deterministic tie-breakers, highest priority first.  Directions come from
# OBJECTIVE_DIRECTIONS so "lower is better" objectives sort correctly.
TIE_BREAKERS: List[str] = [
    "weekly_profit",
    "global_demand_weighted_coverage",
    "total_cost",
    "profit_margin_pct",
    "unserved_demand",
]

# Hard-constraint thresholds (structural — not the soft optimization targets).
# An iteration that fails these cannot be selected as the final network.
# The 70% coverage / $0 profit targets are FEEDBACK LOOP triggers, not
# selection disqualifiers — the pipeline legitimately runs below target when
# the iteration cap is reached.
VALID_ITERATION_STATUS = "completed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _metric(card: Dict[str, Any], key: str) -> float:
    val = card.get(key, 0.0)
    try:
        return float(val or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _margin_value(card: Dict[str, Any]) -> float:
    """Sort value of a card's profit margin.  An undefined / unverified margin is
    ``None`` on the card (never a fabricated 0.0 %); for ranking and tie-breaks it
    sorts below every real margin, so it can never win a tie-break."""
    v = card.get("profit_margin_pct")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        return float("-inf")
    return float(v)


def _normalize(values: List[float], direction: int) -> List[float]:
    """Min-max normalize to [0, 1].  Higher-better → max is 1.0.

    A flat series (max == min) normalizes to 1.0 so a candidate is never
    penalized for an objective on which all candidates are identical.
    """
    if not values:
        return []
    mx, mn = max(values), min(values)
    if mx == mn:
        return [1.0] * len(values)
    if direction >= 0:
        return [(v - mn) / (mx - mn) for v in values]
    return [(mx - v) / (mx - mn) for v in values]


def _optional_float(val: Any) -> Optional[float]:
    if isinstance(val, bool) or not isinstance(val, (int, float)) or val != val:
        return None
    return float(val)


def _parse_json_safe(raw: str) -> Dict:
    """Extract JSON from LLM output, stripping markdown fences."""
    if not raw:
        return {}
    text = raw.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        parsed = json.loads(text.strip())
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                pass
    return {}


# ---------------------------------------------------------------------------
# IterationSelector
# ---------------------------------------------------------------------------

class IterationSelector:
    """Multi-objective selection of the best iteration candidate.

    Parameters
    ----------
    scoring_weights:
        Optional override of the weighted-scoring coefficients.  Defaults to
        the project's active objective weights (profit_first) mapped onto the
        three primary objectives.
    """

    def __init__(self, scoring_weights: Optional[Dict[str, float]] = None):
        weights = dict(scoring_weights or DEFAULT_SCORING_WEIGHTS)
        total = sum(weights.values()) or 1.0
        self.scoring_weights: Dict[str, float] = {
            k: round(v / total, 6) for k, v in weights.items()
        }

    # ------------------------------------------------------------------
    # 1. Scorecards
    # ------------------------------------------------------------------

    def build_scorecards(
        self,
        iteration_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build a compact multi-objective scorecard for every iteration."""
        scorecards: List[Dict[str, Any]] = [
            self._scorecard(it) for it in iteration_results
        ]

        # Accounting gate: an iteration whose network ledger failed verification
        # cannot win over one that passed.  If NONE passed, all stay eligible (the
        # orchestrator then reports ``incomplete_accounting``).
        if any(c["selection_status"] == "candidate" and c["accounting_verified"] is True
               for c in scorecards):
            for c in scorecards:
                if c["selection_status"] == "candidate" and c["accounting_verified"] is False:
                    c["selection_status"] = "unverified_accounting"
                    c["invalid_reason"] = "network ledger not verified"

        candidates = [c for c in scorecards if c["selection_status"] == "candidate"]

        self._assign_ranks(candidates, "weekly_profit", "profit_rank", higher_better=True)
        self._assign_ranks(
            candidates, "global_demand_weighted_coverage", "coverage_rank",
            higher_better=True,
        )
        self._assign_ranks(candidates, "total_cost", "cost_rank", higher_better=False)
        self._assign_ranks(candidates, "profit_margin_pct", "margin_rank", higher_better=True)

        self._pareto_dominance(scorecards)
        self._overall_scores(scorecards)

        return scorecards

    def _scorecard(self, it: Dict[str, Any]) -> Dict[str, Any]:
        iteration = it.get("iteration")
        status    = it.get("status", "unknown")
        metrics   = it.get("metrics", {}) or {}
        regional  = it.get("regional_results", []) or []
        services  = it.get("selected_services", []) or []

        valid = (
            status == VALID_ITERATION_STATUS
            and isinstance(metrics, dict)
            and isinstance(regional, list)
            and len(regional) > 0
            and isinstance(services, list)
            and len(services) > 0
        )

        def m(key: str, default: Any = 0.0) -> Any:
            return metrics.get(key, default)

        # A candidate whose all-in cost is unknown cannot be compared on cost; a
        # missing cost is never treated as zero.
        total_cost_raw = metrics.get("total_cost") if isinstance(metrics, dict) else None
        invalid_reason = ""
        if valid and (isinstance(total_cost_raw, bool)
                      or not isinstance(total_cost_raw, (int, float))
                      or total_cost_raw != total_cost_raw):
            valid = False
            invalid_reason = "missing_total_cost"

        # Independent accounting state of this iteration (None = not evaluated).
        ledger = it.get("network_ledger")
        if isinstance(ledger, dict):
            accounting_verified: Optional[bool] = bool(ledger.get("verified"))
        elif isinstance(metrics, dict) and metrics.get("accounting_verified") is not None:
            accounting_verified = bool(metrics.get("accounting_verified"))
        else:
            accounting_verified = None

        return {
            "iteration":                      iteration,
            "status":                         status,
            "selection_status":               "candidate" if valid else "invalid",
            "invalid_reason":                 invalid_reason,
            "accounting_verified":            accounting_verified,
            "weekly_profit":                  float(m("weekly_profit", 0.0) or 0.0),
            "annual_profit":                  float(m("annual_profit", 0.0) or 0.0),
            "operating_cost":                 float(m("operating_cost", 0.0) or 0.0),
            "total_cost":                     float(total_cost_raw) if (
                isinstance(total_cost_raw, (int, float))
                and not isinstance(total_cost_raw, bool)
                and total_cost_raw == total_cost_raw) else 0.0,
            # None = undefined (no revenue) or not verified: never coerced to 0.0 %
            "profit_margin_pct":              _optional_float(m("profit_margin_pct", None)),
            "average_regional_coverage":      float(m("average_regional_coverage", 0.0) or 0.0),
            "global_demand_weighted_coverage": float(m("global_demand_weighted_coverage", 0.0) or 0.0),
            "satisfied_demand":               float(m("satisfied_demand", 0.0) or 0.0),
            "unserved_demand":                float(m("unserved_demand", 0.0) or 0.0),
            "services_deployed":              int(m("services_deployed", 0) or 0),
            "convergence_score":              float(m("convergence_score", 0.0) or 0.0),
            "negative_profit_regions":        int(m("negative_profit_regions", 0) or 0),
            "coverage_variance":              float(m("coverage_variance", 0.0) or 0.0),
            "constraint_violations":          int(m("constraint_violations", 0) or 0),
            "conflict_count":                 int(m("conflict_count", 0) or 0),
            "weights_used":                   it.get("weights_used", {}) or {},
            # Rank / pareto / score fields filled below
            # advisory 15 % band (reported only; it is not a selection criterion)
            "margin_verdict":                 classify_margin(
                _optional_float(m("profit_margin_pct", None)), accounting_verified),
            "profit_rank":                    None,
            "coverage_rank":                  None,
            "cost_rank":                      None,
            "margin_rank":                    None,
            "pareto_optimal":                 False,
            "dominated_by":                   [],
            "overall_candidate_score":        0.0,
        }

    @staticmethod
    def _assign_ranks(
        cards: List[Dict[str, Any]],
        key: str,
        field: str,
        higher_better: bool = True,
    ) -> None:
        value = _margin_value if key == "profit_margin_pct" else (lambda c: _metric(c, key))
        ordered = sorted(cards, key=value, reverse=higher_better)
        for idx, card in enumerate(ordered):
            card[field] = idx + 1

    # ------------------------------------------------------------------
    # 2. Pareto dominance
    # ------------------------------------------------------------------

    @staticmethod
    def _dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """True if a dominates b.

        a dominates b when a is no worse than b on all Pareto objectives AND
        strictly better on at least one.
        """
        no_worse = True
        strictly_better = False
        for key in PARETO_OBJECTIVES:
            direction = OBJECTIVE_DIRECTIONS[key]
            va = _metric(a, key)
            vb = _metric(b, key)
            if direction >= 0:
                if va < vb - 1e-9:
                    no_worse = False
                if va > vb + 1e-9:
                    strictly_better = True
            else:
                if va > vb + 1e-9:
                    no_worse = False
                if va < vb - 1e-9:
                    strictly_better = True
        return no_worse and strictly_better

    def _pareto_dominance(self, scorecards: List[Dict[str, Any]]) -> None:
        candidates = [c for c in scorecards if c["selection_status"] == "candidate"]
        for a in candidates:
            for b in candidates:
                if a is b:
                    continue
                if self._dominates(a, b):
                    b["dominated_by"].append(a["iteration"])
        for c in candidates:
            c["pareto_optimal"] = not c["dominated_by"]

    # ------------------------------------------------------------------
    # 3. Weighted overall scores
    # ------------------------------------------------------------------

    def _overall_scores(self, scorecards: List[Dict[str, Any]]) -> None:
        candidates = [c for c in scorecards if c["selection_status"] == "candidate"]
        for key, weight in self.scoring_weights.items():
            if key not in OBJECTIVE_DIRECTIONS or OBJECTIVE_DIRECTIONS[key] == 0:
                continue
            direction = OBJECTIVE_DIRECTIONS[key]
            values = [_metric(c, key) for c in candidates]
            norms = _normalize(values, direction)
            for card, norm in zip(candidates, norms):
                card["overall_candidate_score"] += weight * norm
        for card in candidates:
            card["overall_candidate_score"] = round(card["overall_candidate_score"], 6)

    # ------------------------------------------------------------------
    # 4. Deterministic fallback selection
    # ------------------------------------------------------------------

    def deterministic_select(
        self,
        scorecards: List[Dict[str, Any]],
    ):
        """Select the best candidate without any LLM.

        Steps:
          1. Keep structurally-valid candidates.
          2. Keep Pareto-optimal candidates (fall back to all valid candidates
             if the Pareto set is somehow empty).
          3. Score with the active objective weights.
          4. Tie-break with the documented priority list.
        """
        candidates = [c for c in scorecards if c["selection_status"] == "candidate"]
        if not candidates:
            return None, "no valid candidates"

        pool = [c for c in candidates if c["pareto_optimal"]]
        if not pool:
            pool = candidates

        def key(c: Dict[str, Any]):
            # Tuple sort: primary = weighted score; then tie-breakers in order.
            return (
                round(_metric(c, "overall_candidate_score"), 9),
                _metric(c, "weekly_profit"),
                _metric(c, "global_demand_weighted_coverage"),
                -_metric(c, "total_cost"),
                _margin_value(c),
                -_metric(c, "unserved_demand"),
            )

        best = max(pool, key=key)
        return best["iteration"], "deterministic_multi_objective"

    # ------------------------------------------------------------------
    # 5. LLM selection (structured contract + validation)
    # ------------------------------------------------------------------

    def llm_select(
        self,
        scorecards: List[Dict[str, Any]],
        iteration_results: List[Dict[str, Any]],
        llm_callable: Optional[Callable[[str, float], str]],
    ):
        """Ask the LLM to select the best iteration under a strict contract.

        The LLM may only select from the pre-validated candidate set.  Any
        invalid JSON, invented iteration, or invalid candidate returns None so
        the caller can fall back to the deterministic selector.
        """
        candidates = [c for c in scorecards if c["selection_status"] == "candidate"]
        if not candidates:
            return None, None, "no valid candidates"
        valid_ids = [c["iteration"] for c in candidates]

        prompt = self._build_llm_prompt(scorecards, iteration_results, valid_ids)
        raw = ""
        if llm_callable is not None:
            try:
                raw = llm_callable(prompt, 0.1) or ""
            except Exception as exc:  # noqa: BLE001 — LLM must never break the pipeline
                logger.warning("iteration_selection_llm_failed", error=str(exc))
                return None, None, "llm call failed"

        parsed = _parse_json_safe(raw)
        selection = self._validate_llm_selection(parsed, valid_ids)
        if selection is None:
            return None, parsed or None, "invalid llm selection"
        return selection, parsed, "llm_multi_objective"

    @staticmethod
    def _validate_llm_selection(
        parsed: Dict[str, Any],
        valid_ids: List[int],
    ) -> Optional[Dict[str, Any]]:
        """Validate an LLM selection against hard constraints.

        The LLM is a decision-maker, not an unrestricted optimizer.  It must
        pick an iteration that exists, completed, and has valid metrics /
        regional results / selected services (the valid_ids set already
        encodes those checks).  It must never invent an iteration.
        """
        if not isinstance(parsed, dict):
            return None
        sel = parsed.get("selected_iteration")
        if sel is None:
            return None
        try:
            sel = int(sel)
        except (TypeError, ValueError):
            return None
        if sel not in valid_ids:
            return None
        return {
            "selected_iteration": sel,
            "confidence":         float(parsed.get("confidence", 0.0) or 0.0),
            "reasoning":          str(parsed.get("reasoning", "") or ""),
            "tradeoffs":          parsed.get("tradeoffs", []) or [],
            "objective_assessment": parsed.get("objective_assessment", {}) or {},
        }

    @staticmethod
    def _build_llm_prompt(
        scorecards: List[Dict[str, Any]],
        iteration_results: List[Dict[str, Any]],
        valid_ids: List[int],
    ) -> str:
        lines: List[str] = []
        lines.append(
            "You are selecting the BEST optimization iteration for a global "
            "liner shipping network."
        )
        lines.append(
            "Each iteration below is an independent candidate solution produced "
            "by the same pipeline."
        )
        lines.append(
            "Evaluate the candidates across ALL objectives — do not reduce to a "
            "single metric.  More services is not automatically better."
        )
        lines.append("")
        for card in scorecards:
            if card["selection_status"] != "candidate":
                continue
            it = card["iteration"]
            lines.append(f"ITERATION {it}:")
            lines.append(f"  Weekly profit: ${card['weekly_profit']:,.0f} | "
                         f"Annual: ${card['annual_profit']:,.0f}")
            lines.append(f"  Total cost (all-in): ${card['total_cost']:,.0f} | "
                         f"of which vessel hire: ${card['operating_cost']:,.0f}")
            _mg = card["profit_margin_pct"]
            lines.append(f"  Profit margin on revenue: "
                         f"{'n/a (undefined or not verified)' if _mg is None else f'{_mg:.1f}%'} "
                         f"(accounting verified: {card['accounting_verified']}; "
                         f"advisory band: {card['margin_verdict']['band']})")
            lines.append(
                f"  Average regional coverage: {card['average_regional_coverage']:.1f}%"
            )
            lines.append(
                f"  Global demand-weighted coverage: "
                f"{card['global_demand_weighted_coverage']:.1f}%"
            )
            lines.append(f"  Unserved demand: {card['unserved_demand']:,.0f} TEU/wk")
            lines.append(f"  Services deployed: {card['services_deployed']}")
            lines.append(f"  Convergence score: {card['convergence_score']:.3f}")
            lines.append(f"  Negative-profit regions: {card['negative_profit_regions']}")
            lines.append(
                f"  Conflict count: {card['conflict_count']} | "
                f"Constraint violations: {card['constraint_violations']}"
            )
            lines.append(f"  Pareto-optimal: {card['pareto_optimal']}")
            snapshot = next(
                (r for r in iteration_results if r.get("iteration") == it), None
            )
            if snapshot:
                for reg in snapshot.get("regional_results", []):
                    lines.append(
                        f"    Region {reg.get('region', '?')}: "
                        f"profit ${reg.get('weekly_profit', 0):,.0f}, coverage "
                        f"{reg.get('coverage_percent', 0):.1f}%, services "
                        f"{reg.get('services_selected', 0)}"
                    )
            lines.append("")
        lines.append("Select exactly ONE iteration from the completed set.")
        lines.append(f"Valid iterations (must choose one): {sorted(valid_ids)}")
        lines.append("You MUST NOT invent an iteration, metric, or number.")
        lines.append("Return ONLY valid JSON (no markdown, no preamble):")
        lines.append(
            """{
  "selected_iteration": 0,
  "confidence": 0.0,
  "reasoning": "...",
  "tradeoffs": ["...", "..."],
  "objective_assessment": {
    "profit": "...",
    "coverage": "...",
    "total_cost": "...",
    "profit_margin": "...",
    "regional_balance": "..."
  }
}"""
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 6. Public orchestration
    # ------------------------------------------------------------------

    def select(
        self,
        iteration_results: List[Dict[str, Any]],
        llm_callable: Optional[Callable[[str, float], str]] = None,
    ) -> Dict[str, Any]:
        """Evaluate all iterations and select the best candidate.

        Returns the full selection record including scorecards and Pareto
        analysis, the selected iteration, and whether the deterministic
        fallback was used.
        """
        scorecards = self.build_scorecards(iteration_results)
        candidates = [c for c in scorecards if c["selection_status"] == "candidate"]

        if not candidates:
            return {
                "candidate_iterations":      [],
                "pareto_optimal_iterations": [],
                "selected_iteration":        None,
                "selection_method":          "none",
                "confidence":                0.0,
                "reasoning":                 "no valid candidates",
                "fallback_used":             True,
                "llm_selection":             None,
                "scorecards":                scorecards,
            }

        # The deterministic policy is the AUTHORITATIVE source of truth for
        # the final ``selected_iteration``.  The LLM may only contribute a
        # qualitative explanation (reasoning, tradeoffs, confidence); it must
        # never override the deterministic winner, even when its structural
        # selection is a valid in-set iteration.
        det_iter, det_method = self.deterministic_select(scorecards)
        best_iter = det_iter
        method = det_method or "deterministic_multi_objective"
        confidence = 0.0
        reasoning = (
            f"Deterministic multi-objective policy selected iteration "
            f"{best_iter} using active objective weights {self.scoring_weights} "
            f"and Pareto analysis."
        )
        fallback_used = False
        llm_payload = None
        llm_choice = None

        if llm_callable is not None:
            llm_choice, llm_payload, status = self.llm_select(
                scorecards, iteration_results, llm_callable,
            )
            if llm_choice is None:
                logger.info(
                    "iteration_selection_fallback", reason=status,
                )

        # The LLM may enrich reasoning, but ``selected_iteration`` is always
        # the deterministic winner.  If the LLM happened to pick the same
        # iteration, we keep its reasoning/confidence as qualitative
        # explanation; otherwise we record the LLM payload for audit but
        # reject the override.
        if llm_choice is not None and best_iter is not None:
            llm_iter = int(llm_choice["selected_iteration"])
            llm_reasoning = llm_choice.get("reasoning", "") or ""
            llm_confidence = float(llm_choice.get("confidence", 0.0) or 0.0)
            valid_card_ids = {
                c["iteration"] for c in scorecards
                if c.get("selection_status") == "candidate"
            }
            if llm_iter == best_iter:
                # LLM agrees with policy — keep its qualitative contribution.
                if llm_reasoning:
                    reasoning = llm_reasoning
                confidence = llm_confidence
            elif llm_iter in valid_card_ids:
                # LLM disagrees with policy — record the override attempt but
                # DO NOT let it change ``selected_iteration``.
                fallback_used = True
                det_card = next(
                    (c for c in scorecards if c["iteration"] == best_iter), None,
                )
                llm_card = next(
                    (c for c in scorecards if c["iteration"] == llm_iter), None,
                )
                det_profit = det_card.get("weekly_profit", 0.0) if det_card else 0.0
                llm_profit = llm_card.get("weekly_profit", 0.0) if llm_card else 0.0
                logger.warning(
                    "iteration_selection_llm_override_rejected",
                    deterministic_iter=best_iter,
                    llm_iter=llm_iter,
                    deterministic_profit=det_profit,
                    llm_profit=llm_profit,
                )
                reasoning = (
                    f"Deterministic policy selected iteration {best_iter} "
                    f"(weekly_profit=${det_profit:,.0f}); LLM proposed "
                    f"iteration {llm_iter} (weekly_profit=${llm_profit:,.0f}) "
                    f"but the deterministic policy has final authority."
                )
            # else: LLM returned an iteration that isn't a candidate (should
            # already have been filtered by _validate_llm_selection, but be
            # defensive) — ignore it entirely.

        candidate_ids = sorted(c["iteration"] for c in candidates)
        pareto_ids = sorted(c["iteration"] for c in candidates if c["pareto_optimal"])


        act = actuation_ledger.begin("iteration_selector")
        rec = llm_client.last_response
        if rec is not None:
            act.provider = rec.provider
            act.model = rec.model
            act.role = rec.role or "iteration_selector"
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
        act.decision_source = "llm" if (not fallback_used and method == "llm_multi_objective") else "rule-based"
        act.ai_generated = act.decision_source == "llm"
        act.decision_consumed = True

        return {
            "candidate_iterations":      candidate_ids,
            "pareto_optimal_iterations": pareto_ids,
            "selected_iteration":        best_iter,
            "selection_method":          method,
            "confidence":                float(confidence),
            "reasoning":                 reasoning,
            "fallback_used":             fallback_used,
            "llm_selection":             llm_payload,
            "scorecards":                scorecards,
            "llm_actuation":             act.to_dict(),
        }
