"""Application-level conclusion about a MILP solve (decision-phase hardening).

PuLP/CBC reports ``solver_status == "Optimal"`` whenever the solver returned normally, including
when a time limit stopped it with an integer-feasible incumbent and a large gap to the bound
(``prob.sol_status`` then says "integer feasible").  That raw value must not be shown as a proof of
optimality.  ``classify_solve`` derives the claim the evidence supports; the raw backend status is
kept unchanged next to it.

conclusion
    proven_optimal                       solver closed the integer problem over the whole retained model
    optimal_for_restricted_service_set   closed, but only over the LP-support services; the relaxation
                                         bound belongs to the larger model, so this is not a global proof
    feasible_time_limit_gap_unresolved   incumbent, time limit reached, gap above ``MATERIAL_GAP``
    feasible_gap_unresolved              incumbent, stopped before closing, gap above ``MATERIAL_GAP``
    feasible_within_gap_tolerance        incumbent not proven optimal, gap <= ``MATERIAL_GAP``
    no_incumbent                         no usable plan (not_solved / infeasible / solver_error)
The gap is incumbent versus the relaxation bound of the capped model only; it is never negative
(a negative value is reported as ``None`` with ``incumbent_exceeds_bound``).
The post-solve plan is classified separately by ``classify_final_plan``.
"""
from __future__ import annotations

from typing import Dict, Optional

MATERIAL_GAP = 0.01          # relative gap (of |bound|) above which an unclosed incumbent is "unresolved"


def classify_solve(*, usable: bool, closed: bool, restricted: bool, time_limit_reached: bool,
                   incumbent: Optional[float], bound: Optional[float]) -> Dict:
    gap_usd = gap_pct = None
    exceeds = False
    if incumbent is not None and bound is not None:
        g = float(bound) - float(incumbent)
        tol = 1e-6 * max(1.0, abs(float(bound)))
        if g < -tol:
            exceeds = True
        else:
            gap_usd = max(0.0, g)
            gap_pct = 100.0 * gap_usd / abs(float(bound)) if float(bound) else None
    if not usable:
        conclusion = "no_incumbent"
    elif closed and not restricted:
        conclusion = "proven_optimal"
    elif closed:
        conclusion = "optimal_for_restricted_service_set"
    elif gap_pct is not None and gap_pct <= 100.0 * MATERIAL_GAP:
        conclusion = "feasible_within_gap_tolerance"
    elif time_limit_reached:
        conclusion = "feasible_time_limit_gap_unresolved"
    else:
        conclusion = "feasible_gap_unresolved"
    return {"conclusion": conclusion, "proven_optimal": conclusion == "proven_optimal",
            "time_limit_reached": bool(time_limit_reached), "closed_by_solver": bool(closed),
            "restricted_to_lp_support": bool(restricted),
            "gap_usd_per_week": gap_usd, "gap_pct_of_bound": gap_pct, "incumbent_exceeds_bound": exceeds}


def classify_final_plan(*, final: float, bound: Optional[float]) -> Dict:
    """The final plan (after local search / flow re-optimisation) lives outside the capped model."""
    exceeds = bound is not None and float(final) > float(bound) + 1e-6 * max(1.0, abs(float(bound)))
    return {"exceeds_capped_model_bound": bool(exceeds),
            "conclusion": ("final_plan_exceeds_bound_of_a_different_model" if exceeds
                           else "final_plan_not_comparable_to_capped_bound_as_optimality_evidence"),
            "optimality_claim": "none"}
