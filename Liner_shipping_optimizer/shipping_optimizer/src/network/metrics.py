"""Canonical network economics for the decision layer (F-15).

The decision layer (coordinator evaluation, iteration scoring, the public
``decision_output.global_metrics``) used to read ``operating_cost`` from the
regional results.  That field is the *vessel-hire component* of the cost (see
``summary_metrics``: hire + fuel + port + transshipment = ``total_cost``), so the
"total cost" and "profit margin" it produced covered only part of the network's
cost and disagreed with the verified ledger (margin 25.9 % vs 11.3 % on the same
plan).

This module is the single definition used by every decision-layer consumer:

    revenue       = ledger revenue                          (weekly USD)
    total_cost    = hire + fuel + port calls + handling + transshipment
                    + per-TEU port charges                  (all-in, weekly USD)
    profit        = revenue - total_cost                    (no unserved penalty)
    margin_pct    = 100 * profit / revenue                  (None if undefined)
    vessel_hire   = the hire component, kept as a diagnostic only

Authority.  When a *verified* network ledger is supplied its ``weekly_usd`` block
is the authority and the regional numbers are only cross-checked against it (they
are an additive partition of the ledger).  When the ledger is missing or not
verified the margin is NOT reported as a verified figure: ``accounting_status``
says so and, for an unverified ledger, ``profit_margin_pct`` is ``None``.

Nothing here changes any optimisation result; it only fixes what is *reported and
compared*.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

#: tolerance for "the regional partition sums to the ledger" (USD per week)
PARTITION_ABS_TOL = 1.0
PARTITION_REL_TOL = 1e-6

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUS_NOT_EVALUATED = "not_evaluated"

#: Advisory profit-margin band (owner decision, Task 14).  The margin on revenue at
#: which a network is classified "at or above target".  It is a *verdict band*: it
#: never changes physical feasibility, the accounting status, the solver status, a
#: rerun decision or the choice of an iteration.
MARGIN_TARGET_PCT = 15.0

MARGIN_AT_OR_ABOVE_TARGET = "at_or_above_target"   # verified, margin >= target
MARGIN_BELOW_TARGET = "below_target"               # verified, 0 <= margin < target
MARGIN_LOSS = "loss"                               # verified, margin < 0
MARGIN_UNDEFINED = "undefined"                     # verified ledger, revenue <= 0
MARGIN_UNVERIFIED = "unverified"                   # ledger absent / not verified


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(PARTITION_ABS_TOL, PARTITION_REL_TOL * max(abs(a), abs(b)))


def classify_margin(
    margin_pct: Optional[float],
    accounting_verified: Optional[bool],
    target_pct: float = MARGIN_TARGET_PCT,
) -> Dict[str, Any]:
    """Advisory verdict band of a profit margin on revenue.

    ``margin_pct`` is the ledger margin (``None`` when undefined or unverified) and
    ``accounting_verified`` the verification state of the ledger it came from
    (``True`` / ``False`` / ``None`` = not evaluated).  The result only *describes*
    the margin: ``advisory`` is always ``True`` and ``blocks_acceptance`` always
    ``False``, so a feasible, verified, positive-profit network is never rejected,
    re-run or de-selected because it falls below the target.

    An unverified or undefined margin is never turned into a number: the band says
    why and ``margin_pct`` is ``None``.
    """
    base = {"target_pct": float(target_pct), "advisory": True, "blocks_acceptance": False}
    if accounting_verified is not True:
        return {**base, "band": MARGIN_UNVERIFIED, "margin_pct": None,
                "note": "accounting not independently verified; no margin verdict"}
    m = _num(margin_pct)
    if m is None:
        return {**base, "band": MARGIN_UNDEFINED, "margin_pct": None,
                "note": "margin undefined (no revenue)"}
    if m < 0.0:
        band, note = MARGIN_LOSS, f"margin {m:.1f}% is a loss"
    elif m >= target_pct - 1e-9:
        band, note = MARGIN_AT_OR_ABOVE_TARGET, f"margin {m:.1f}% >= advisory target {target_pct:.1f}%"
    else:
        band, note = MARGIN_BELOW_TARGET, (
            f"margin {m:.1f}% < advisory target {target_pct:.1f}% (advisory only; the "
            f"network remains feasible and its profit is unchanged)")
    return {**base, "band": band, "margin_pct": m, "note": note}


def margin_verdict_label(verdict: Dict[str, Any], good_above_pct: float) -> str:
    """Text label used by the report writers: ``Good`` above ``good_above_pct``,
    ``Moderate`` at or above the advisory target, ``Poor`` below it or at a loss,
    ``Undefined`` when there is no revenue, ``Not verified`` when the accounting is
    not verified."""
    band = verdict.get("band")
    if band == MARGIN_UNVERIFIED:
        return "Not verified"
    if band == MARGIN_UNDEFINED:
        return "Undefined"
    if band == MARGIN_AT_OR_ABOVE_TARGET:
        return "Good" if verdict["margin_pct"] > good_above_pct else "Moderate"
    return "Poor"


def canonical_network_economics(
    regional_results: Sequence[Dict[str, Any]],
    network_ledger: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the canonical weekly economics of one iteration.

    Parameters
    ----------
    regional_results:
        Regional result dicts (``weekly_profit``, ``total_cost``, ``operating_cost``).
        After the global stage they are an additive partition of the ledger.
    network_ledger:
        The ``network_ledger`` block of the same iteration (or ``None`` when the
        caller has none).

    Returned keys: ``revenue``, ``total_cost``, ``vessel_hire_cost``, ``profit``,
    ``profit_margin_pct``, ``accounting_status``, ``accounting_verified``,
    ``accounting_basis``, ``accounting_issues``.
    """
    issues: List[str] = []
    profit_r = 0.0
    cost_r = 0.0
    hire_r = 0.0
    missing_cost: List[str] = []
    for r in regional_results or []:
        profit_r += _num(r.get("weekly_profit")) or 0.0
        hire_r += _num(r.get("operating_cost")) or 0.0
        tc = _num(r.get("total_cost"))
        if tc is None:
            missing_cost.append(str(r.get("region", r.get("agent", "?"))))
        else:
            cost_r += tc
    regional_complete = bool(regional_results) and not missing_cost
    if missing_cost:
        issues.append("regions without a total_cost: " + ", ".join(missing_cost))

    out: Dict[str, Any] = {
        "revenue": None, "total_cost": cost_r if regional_complete else None,
        "vessel_hire_cost": hire_r, "profit": profit_r,
        "profit_margin_pct": None,
        "accounting_status": STATUS_NOT_EVALUATED, "accounting_verified": None,
        "accounting_basis": "regional_sum", "accounting_issues": issues,
    }

    if network_ledger is None:
        # No ledger supplied: the regional identity revenue = profit + total_cost is
        # still arithmetic, but nothing here has been independently verified.
        if regional_complete:
            out["revenue"] = profit_r + cost_r
            if out["revenue"] > 0:
                out["profit_margin_pct"] = 100.0 * profit_r / out["revenue"]
        issues.append("no network ledger supplied; figures are not independently verified")
        return out

    verified = bool(network_ledger.get("verified"))
    wk = network_ledger.get("weekly_usd") or {}
    if not verified or not isinstance(wk, dict) or _num(wk.get("revenue")) is None:
        out.update(
            accounting_status=STATUS_UNVERIFIED, accounting_verified=False,
            accounting_basis="regional_sum_unverified",
        )
        msg = str(network_ledger.get("message") or network_ledger.get("status") or "ledger not verified")
        issues.append(f"network ledger not verified: {msg}")
        # profit / total cost remain the regional numbers (labelled unverified);
        # a margin on unverified revenue is not reported.
        return out

    revenue = _num(wk.get("revenue"))
    total_cost = _num(wk.get("total_operating_cost"))
    profit = _num(wk.get("operating_profit"))
    hire = _num(wk.get("vessel_cost"))
    if total_cost is None or profit is None or hire is None:
        out.update(accounting_status=STATUS_UNVERIFIED, accounting_verified=False,
                   accounting_basis="regional_sum_unverified")
        issues.append("network ledger weekly_usd is incomplete")
        return out

    consistent = True
    if not _close(revenue - total_cost, profit):
        consistent = False
        issues.append(
            f"ledger identity broken: revenue {revenue:,.2f} - cost {total_cost:,.2f} "
            f"!= profit {profit:,.2f}")
    if regional_complete:
        for label, got, want in (("profit", profit_r, profit),
                                 ("total_cost", cost_r, total_cost),
                                 ("vessel hire", hire_r, hire)):
            if not _close(got, want):
                consistent = False
                issues.append(f"regional {label} sum {got:,.2f} != ledger {want:,.2f}")
    else:
        issues.append("regional results incomplete; the verified ledger is the only authority")

    out.update(
        revenue=revenue, total_cost=total_cost, vessel_hire_cost=hire, profit=profit,
        profit_margin_pct=(100.0 * profit / revenue if revenue > 0 else None),
        accounting_basis="network_ledger",
        accounting_status=STATUS_VERIFIED if consistent else STATUS_UNVERIFIED,
        accounting_verified=consistent,
    )
    if not consistent:
        out["profit_margin_pct"] = None
    return out
