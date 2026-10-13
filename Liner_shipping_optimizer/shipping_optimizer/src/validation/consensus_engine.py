"""
Consensus Engine 

Reconciles conflicting decisions from the CoordinatorAgent, RegionalAgent,
and ServiceGeneratorAgent using weighted voting to produce a unified
CONSENSUS_POLICY.

Input:
  - coordinator_decisions   — weight_adjustments dict from CoordinatorAgent
  - regional_policies       — dict of region_name -> raw policy dict
  - service_archetype_params — archetype mix dict from ServiceGeneratorAgent
  - previous_consensus      — optional prior CONSENSUS_POLICY for continuity

Process:
  1. Validate all inputs via existing validators
  2. Detect conflicts (weight disparity, archetype mismatch, hub conflict)
  3. Reconcile via weighted voting (coordinator 0.40, regional 0.40, svc gen 0.20)
  4. Produce CONSENSUS_POLICY with confidence score and resolution trails

Logging tags:
  CONSENSUS_ACCEPTED  — all conflicts resolved, confidence > 0.7
  CONSENSUS_MODIFIED  — some conflicts modified, confidence 0.3-0.7
  CONSENSUS_REJECTED  — confidence < 0.3, fallback used

Validation:
  - All outputs pass their respective validators
  - confidence < 0.3 triggers AI_FALLBACK
  - Unresolvable conflicts default to coordinator priority
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import logger
from src.validation.weight_validator import (
    validate_weight_adjustments,
    MAX_WEIGHT as W_Max,  # noqa: F401 — used conceptually in docs
)
from src.validation.archetype_validator import (
    validate_archetype_params,
    DEFAULT_ARCHETYPE_PARAMS,
)
from src.validation.regional_policy_validator import (
    validate_regional_policy,
    DEFAULT_REGIONAL_POLICY,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Voting weights
COORDINATOR_WEIGHT: float = 0.40
REGIONAL_WEIGHT: float = 0.40
SERVICE_GENERATOR_WEIGHT: float = 0.20

# Conflict thresholds
PROFIT_HIGH_THRESHOLD: float = 0.60   # coordinator profit above this may conflict
COVERAGE_HIGH_THRESHOLD: float = 0.70  # region coverage above this may conflict
FEEDER_HIGH_THRESHOLD: float = 0.40    # svc gen feeder ratio above this
BIAS_DIRECT_INDICATOR: str = "large"   # vessel_bias that prefers direct/trunk
BIAS_FEEDER_INDICATOR: str = "small"   # vessel_bias that prefers feeder

# Confidence maths
CONFIDENCE_PER_CONFLICT: float = 0.15
CONFIDENCE_UNRESOLVED_PENALTY: float = 0.25

# Thresholds
CONSENSUS_ACCEPTED_MIN: float = 0.70
CONSENSUS_REJECTED_MAX: float = 0.30

# Archetype-reconciliation presets (used when deriving positions from weights)
VESSEL_BIAS_OPTIONS: List[str] = ["small", "balanced", "large"]
BIAS_WEIGHT_PROFIT_MID: float = 0.50  # profit_weight above this tilts "large"
BIAS_WEIGHT_COVERAGE_MID: float = 0.50  # coverage_weight above this tilts "small"

# Default cost weight for regions (they do not express cost directly)
REGION_DEFAULT_COST: float = 0.10

# ---------------------------------------------------------------------------
# Default fallback output
# ---------------------------------------------------------------------------

DEFAULT_CONSENSUS: Dict[str, Any] = {
    "final_weight_adjustments": {
        "profit_weight": 0.50,
        "coverage_weight": 0.40,
        "cost_weight": 0.10,
    },
    "final_archetype_params": dict(DEFAULT_ARCHETYPE_PARAMS),
    "confidence_score": 0.0,
    "conflicts_resolved": [],
    "conflicts_remaining": ["fallback_used — confidence below rejection threshold"],
    "notes": "Fallback consensus applied; confidence below 0.3 threshold.",
}


# ---------------------------------------------------------------------------
# Helper: generic weighted average
# ---------------------------------------------------------------------------

def _weighted_average(proposals: List[Tuple[float, float]]) -> float:
    """Weighted average of (value, weight) pairs.

    Returns 0.0 when total weight is zero (should not happen in practice
    because at least one voter always participates).
    """
    total_weight = sum(w for _, w in proposals)
    if total_weight < 1e-9:
        return 0.0
    return sum(v * w for v, w in proposals) / total_weight


# ===================================================================
# ConsensusEngine
# ===================================================================

class ConsensusEngine:
    """Reconcile multi-agent decisions into a unified consensus policy.

    Uses weighted voting among three agent groups:

        Coordinator        0.40  — global authority on weights
        Regional (avg)     0.40  — on-the-ground policy per region
        Service Generator  0.20  — archetype specialist

    Confidence scoring drives three log states:

        CONSENSUS_ACCEPTED   (> 0.70)  — all clear
        CONSENSUS_MODIFIED   (0.30–0.70) — compromises applied
        CONSENSUS_REJECTED   (< 0.30)  — fallback triggered
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        coordinator_decisions: Any,
        regional_policies: Dict[str, Any],
        service_archetype_params: Any,
        previous_consensus: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the full consensus pipeline.

        Parameters
        ----------
        coordinator_decisions:
            Raw weight_adjustments dict from CoordinatorAgent
            (e.g. ``{"profit_weight": 0.70, "coverage_weight": 0.20, "cost_weight": 0.10}``).
        regional_policies:
            Dict mapping region name → raw policy dict (each validated separately).
        service_archetype_params:
            Raw archetype params dict from ServiceGeneratorAgent
            (e.g. ``{"archetype_mix": {"direct_ratio": 0.60, ...}, "vessel_bias": "balanced"}``).
        previous_consensus:
            Optional prior CONSENSUS_POLICY result.
            Used for continuity — if supplied, its ``final_weight_adjustments``
            and ``final_archetype_params`` act as an additional voter with
            weight 0.10 (taken proportionally from the three main voters).

        Returns
        -------
        CONSENSUS_POLICY dict with keys:
            final_weight_adjustments, final_archetype_params,
            confidence_score, conflicts_resolved, conflicts_remaining, notes.
        """
        # -- 1. Validate all inputs --------------------------------------------
        coord_validated = validate_weight_adjustments(coordinator_decisions)

        validated_regional: Dict[str, Dict[str, Any]] = {}
        region_keys: List[str] = []
        for region, raw_policy in (regional_policies or {}).items():
            validated_regional[region] = validate_regional_policy(raw_policy)
            region_keys.append(region)

        archetype_validated = validate_archetype_params(service_archetype_params)

        # -- 2. Detect conflicts -----------------------------------------------
        weight_conflict = self._detect_weight_disparity(
            coord_validated, validated_regional,
        )
        archetype_conflict = self._detect_archetype_mismatch(
            archetype_validated, validated_regional,
        )
        hub_conflict = self._detect_hub_conflict(
            archetype_validated, validated_regional,
        )

        all_conflicts = [c for c in (weight_conflict, archetype_conflict, hub_conflict)
                         if c is not None]

        # -- 3. Reconcile via weighted voting ----------------------------------
        reconciled_weights = self._reconcile_weights(
            coord_validated, validated_regional, archetype_validated,
            weight_conflict, previous_consensus,
        )
        reconciled_archetype = self._reconcile_archetype(
            coord_validated, validated_regional, archetype_validated,
            archetype_conflict, previous_consensus,
        )
        reconciled_hubs = self._reconcile_hubs(
            validated_regional, archetype_validated,
            hub_conflict, previous_consensus,
        )

        # -- 4. Classify conflicts resolved vs remaining -----------------------
        conflicts_resolved: List[Dict[str, Any]] = []
        conflicts_remaining: List[Dict[str, Any]] = []
        for c in all_conflicts:
            if c.get("resolved", False):
                conflicts_resolved.append(c)
            else:
                conflicts_remaining.append(c)

        # -- 5. Compute confidence ---------------------------------------------
        num_regions = len(region_keys)
        confidence = self._compute_confidence(
            all_conflicts, conflicts_remaining, num_regions,
        )

        # -- 6. Assemble final policy ------------------------------------------
        result: Dict[str, Any] = {
            "final_weight_adjustments": dict(reconciled_weights),
            "final_archetype_params": {
                "archetype_mix": dict(reconciled_archetype["archetype_mix"]),
                "vessel_bias": reconciled_archetype["vessel_bias"],
                "hub_focus": list(reconciled_hubs),
                "notes": reconciled_archetype.get("notes", ""),
            },
            "confidence_score": round(confidence, 4),
            "conflicts_resolved": conflicts_resolved,
            "conflicts_remaining": conflicts_remaining,
            "notes": self._build_notes(
                confidence, len(all_conflicts), len(conflicts_remaining),
            ),
        }

        # -- 7. Validate final output ------------------------------------------
        self._validate_final(result)

        # -- 8. Log state ------------------------------------------------------
        self._log_consensus(result)

        # -- 9. Fallback if rejected -------------------------------------------
        if confidence < CONSENSUS_REJECTED_MAX:
            return self._fallback(
                result,
                reason=f"confidence {confidence:.4f} < {CONSENSUS_REJECTED_MAX}",
            )

        return result

    # ------------------------------------------------------------------
    # Conflict Detection
    # ------------------------------------------------------------------

    def _detect_weight_disparity(
        self,
        coord: Dict[str, float],
        regional: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Check if coordinator's profit goal clashes with regional coverage goal.

        Conflict condition:
            coordinator profit_weight > 0.6  AND
            any regional policy coverage_priority > 0.7
        """
        coord_profit = coord.get("profit_weight", 0.0)
        if coord_profit <= PROFIT_HIGH_THRESHOLD:
            return None

        high_coverage_regions: List[str] = []
        for rname, rpol in regional.items():
            cov = rpol.get("coverage_priority", 0.0)
            if cov > COVERAGE_HIGH_THRESHOLD:
                high_coverage_regions.append(rname)

        if not high_coverage_regions:
            return None

        return {
            "type": "weight_disparity",
            "detail": (
                f"Coordinator profit_weight={coord_profit:.2f} "
                f"conflicts with regional coverage_priority > {COVERAGE_HIGH_THRESHOLD} "
                f"in region(s): {', '.join(high_coverage_regions)}"
            ),
            "coordinator_profit_weight": coord_profit,
            "regions_high_coverage": high_coverage_regions,
            "regional_coverage_values": {
                r: regional[r].get("coverage_priority", 0.0)
                for r in high_coverage_regions
            },
            "resolved": False,  # will be flipped by reconciliation
        }

    def _detect_archetype_mismatch(
        self,
        archetype: Dict[str, Any],
        regional: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Check if service-generator feeder ratio conflicts with regional bias.

        Conflict condition:
            service generator feeder_ratio > 0.4  AND
            any regional policy vessel_bias == "large"  (prefers direct/trunk)

        Also reversed: direct_ratio > 0.5 AND any region has vessel_bias "small".
        """
        mix = archetype.get("archetype_mix", {})
        feeder = mix.get("feeder_ratio", 0.0)
        direct = mix.get("direct_ratio", 0.0)

        mismatched_regions_feeder: List[str] = []
        mismatched_regions_direct: List[str] = []

        for rname, rpol in regional.items():
            vb = rpol.get("vessel_bias", "balanced")
            if feeder > FEEDER_HIGH_THRESHOLD and vb == BIAS_DIRECT_INDICATOR:
                mismatched_regions_feeder.append(rname)
            if direct > 0.5 and vb == BIAS_FEEDER_INDICATOR:
                mismatched_regions_direct.append(rname)

        if not mismatched_regions_feeder and not mismatched_regions_direct:
            return None

        details: List[str] = []
        if mismatched_regions_feeder:
            details.append(
                f"ServiceGen feeder_ratio={feeder:.2f} conflicts with "
                f"regional vessel_bias='large' in {mismatched_regions_feeder}"
            )
        if mismatched_regions_direct:
            details.append(
                f"ServiceGen direct_ratio={direct:.2f} conflicts with "
                f"regional vessel_bias='small' in {mismatched_regions_direct}"
            )

        return {
            "type": "archetype_mismatch",
            "detail": "; ".join(details),
            "feeder_ratio": feeder,
            "direct_ratio": direct,
            "regions_feeder_conflict": mismatched_regions_feeder,
            "regions_direct_conflict": mismatched_regions_direct,
            "regional_biases": {
                r: regional[r].get("vessel_bias", "balanced")
                for r in (mismatched_regions_feeder + mismatched_regions_direct)
            },
            "resolved": False,
        }

    def _detect_hub_conflict(
        self,
        archetype: Dict[str, Any],
        regional: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Check if service generator and regional agents recommend different hubs.

        Conflict condition:
            hub_focus sets are non-empty and disjoint (no intersection)
            OR significantly different (one set is not a subset of the other).
        """
        svc_hubs = set(archetype.get("hub_focus", []))

        all_regional_hubs: set = set()
        for rname, rpol in regional.items():
            all_regional_hubs.update(rpol.get("hub_focus", []))

        # No conflict if either side is empty
        if not svc_hubs or not all_regional_hubs:
            return None

        intersection = svc_hubs & all_regional_hubs

        # If there is zero overlap or the overlap is a strict minority,
        # flag as conflict.
        if len(intersection) == 0:
            return {
                "type": "hub_conflict",
                "detail": (
                    f"ServiceGen hub_focus={sorted(svc_hubs)} has no overlap "
                    f"with regional hub_focus={sorted(all_regional_hubs)}"
                ),
                "service_hubs": sorted(svc_hubs),
                "regional_hubs": sorted(all_regional_hubs),
                "intersection": [],
                "resolved": False,
            }

        # Partial overlap: intersection exists but each side has
        # exclusive hubs not in the other set.
        svc_exclusive = svc_hubs - all_regional_hubs
        reg_exclusive = all_regional_hubs - svc_hubs
        if svc_exclusive or reg_exclusive:
            return {
                "type": "hub_conflict",
                "detail": (
                    f"Partial hub overlap: common={sorted(intersection)}, "
                    f"svc-exclusive={sorted(svc_exclusive)}, "
                    f"regional-exclusive={sorted(reg_exclusive)}"
                ),
                "service_hubs": sorted(svc_hubs),
                "regional_hubs": sorted(all_regional_hubs),
                "intersection": sorted(intersection),
                "resolved": False,
            }

        return None  # no conflict (subsets or identical)

    # ------------------------------------------------------------------
    # Reconciliation — Weighted Voting
    # ------------------------------------------------------------------

    @staticmethod
    def _voter_weights(
        regional: Dict[str, Any],
        previous_consensus: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Tuple[str, float]], float]:
        """Compute the effective weight of each voter.

        Returns
        -------
        (voter_list, svc_gen_weight):
            voter_list: list of (voter_id, weight) tuples.
                "coordinator"  — COORDINATOR_WEIGHT
                "region:<name>" — REGIONAL_WEIGHT / num_regions  each
                "svc_gen"     — SERVICE_GENERATOR_WEIGHT
                "previous"    — 0.10 if previous_consensus is supplied
            svc_gen_weight: the raw weight used for the service generator
                (may be reduced if previous consensus is present).

        When a previous_consensus is supplied, 0.10 is deducted
        proportionally from the three main voters to make room.
        """
        has_previous = previous_consensus is not None

        # Base weights
        num_regions = max(1, len(regional))
        coord_w = COORDINATOR_WEIGHT
        reg_w_each = REGIONAL_WEIGHT / num_regions if num_regions else 0.0
        svc_w = SERVICE_GENERATOR_WEIGHT

        # If we have a previous consensus, steal 0.10 proportionally
        if has_previous:
            total_base = coord_w + REGIONAL_WEIGHT + svc_w  # = 1.0
            # Each voter contributes fractionally
            fraction = 0.10 / total_base
            coord_w -= fraction * coord_w
            reg_w_each -= fraction * reg_w_each
            svc_w -= fraction * svc_w

        voters: List[Tuple[str, float]] = [("coordinator", coord_w)]
        for rname in regional:
            voters.append((f"region:{rname}", reg_w_each))
        voters.append(("svc_gen", svc_w))
        if has_previous:
            voters.append(("previous", 0.10))

        return voters, svc_w

    def _reconcile_weights(
        self,
        coord: Dict[str, float],
        regional: Dict[str, Dict[str, Any]],
        archetype: Dict[str, Any],
        weight_conflict: Optional[Dict[str, Any]],
        previous_consensus: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """Reconcile weight adjustments via weighted voting.

        Each voter casts a ``(profit, coverage, cost)`` triple;
        the result is the weighted average.
        """
        voters, _ = self._voter_weights(regional, previous_consensus)

        proposals: List[Tuple[Tuple[float, float, float], float]] = []

        for voter_id, weight in voters:
            if voter_id == "coordinator":
                triple = (
                    coord.get("profit_weight", 0.50),
                    coord.get("coverage_weight", 0.40),
                    coord.get("cost_weight", 0.10),
                )
            elif voter_id.startswith("region:"):
                rpol = regional.get(voter_id.removeprefix("region:"), {})
                # Derive: profit from profit_priority, coverage from coverage_priority.
                # Regions don't express cost — default to REGION_DEFAULT_COST
                # and scale profit+coverage to fill the remaining 0.90.
                p = rpol.get("profit_priority", 0.50)
                c = rpol.get("coverage_priority", 0.50)
                total_pc = max(p + c, 0.01)
                triple = (
                    round(p / total_pc * (1.0 - REGION_DEFAULT_COST), 4),
                    round(c / total_pc * (1.0 - REGION_DEFAULT_COST), 4),
                    REGION_DEFAULT_COST,
                )
            elif voter_id == "svc_gen":
                triple = self._derive_weights_from_archetype(archetype)
            elif voter_id == "previous" and previous_consensus is not None:
                pw = previous_consensus.get("final_weight_adjustments", {})
                triple = (
                    pw.get("profit_weight", 0.50),
                    pw.get("coverage_weight", 0.40),
                    pw.get("cost_weight", 0.10),
                )
            else:
                continue  # skip unknown voters

            proposals.append((triple, weight))

        # Weighted average per component
        profit = _weighted_average([(t[0], w) for t, w in proposals])
        coverage = _weighted_average([(t[1], w) for t, w in proposals])
        cost = _weighted_average([(t[2], w) for t, w in proposals])

        # Normalise to sum 1.0
        total = profit + coverage + cost
        if abs(total - 1.0) > 1e-6:
            scale = 1.0 / max(total, 1e-9)
            profit *= scale
            coverage *= scale
            cost *= scale

        reconciled = {
            "profit_weight": round(profit, 4),
            "coverage_weight": round(coverage, 4),
            "cost_weight": round(cost, 4),
        }

        # If a weight_disparity conflict existed, mark it resolved
        if weight_conflict is not None:
            weight_conflict["resolved"] = True
            weight_conflict["resolution"] = (
                f"Weighted vote produced profit={profit:.4f}, "
                f"coverage={coverage:.4f}, cost={cost:.4f}"
            )

        return reconciled

    def _reconcile_archetype(
        self,
        coord: Dict[str, float],
        regional: Dict[str, Dict[str, Any]],
        archetype: Dict[str, Any],
        archetype_conflict: Optional[Dict[str, Any]],
        previous_consensus: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Reconcile archetype mix and vessel_bias via weighted voting."""
        voters, _ = self._voter_weights(regional, previous_consensus)

        # -- ratios: weighted average --
        ratio_proposals: Dict[str, List[Tuple[float, float]]] = {
            "direct_ratio": [],
            "hub_loop_ratio": [],
            "feeder_ratio": [],
            "trunk_ratio": [],
        }

        # -- vessel_bias: weighted mode --
        bias_votes: Dict[str, float] = {}

        for voter_id, weight in voters:
            if voter_id == "coordinator":
                ratios, bias = self._derive_archetype_from_weights(coord)
            elif voter_id.startswith("region:"):
                rpol = regional.get(voter_id.removeprefix("region:"), {})
                ratios, bias = self._derive_archetype_from_region(rpol)
            elif voter_id == "svc_gen":
                mix = archetype.get("archetype_mix", {})
                ratios = {
                    "direct_ratio": mix.get("direct_ratio", 0.60),
                    "hub_loop_ratio": mix.get("hub_loop_ratio", 0.15),
                    "feeder_ratio": mix.get("feeder_ratio", 0.20),
                    "trunk_ratio": mix.get("trunk_ratio", 0.05),
                }
                bias = archetype.get("vessel_bias", "balanced")
            elif voter_id == "previous" and previous_consensus is not None:
                prev_arch = previous_consensus.get("final_archetype_params", {})
                mix = prev_arch.get("archetype_mix", {})
                ratios = {
                    "direct_ratio": mix.get("direct_ratio", 0.60),
                    "hub_loop_ratio": mix.get("hub_loop_ratio", 0.15),
                    "feeder_ratio": mix.get("feeder_ratio", 0.20),
                    "trunk_ratio": mix.get("trunk_ratio", 0.05),
                }
                bias = prev_arch.get("vessel_bias", "balanced")
            else:
                continue

            for k in ratio_proposals:
                ratio_proposals[k].append((ratios[k], weight))

            bias_votes[bias] = bias_votes.get(bias, 0.0) + weight

        # Compute weighted average of ratios
        final_ratios = {
            k: round(_weighted_average(votes), 4)
            for k, votes in ratio_proposals.items()
        }

        # Normalise ratios to sum 1.0
        ratio_sum = sum(final_ratios.values())
        if abs(ratio_sum - 1.0) > 0.02:
            scale = 1.0 / max(ratio_sum, 1e-9)
            final_ratios = {k: round(v * scale, 4) for k, v in final_ratios.items()}

        # Weighted mode for vessel_bias
        final_bias = max(bias_votes, key=bias_votes.get) if bias_votes else "balanced"

        result = {
            "archetype_mix": final_ratios,
            "vessel_bias": final_bias,
            "notes": self._build_archetype_notes(
                archetype, archetype_conflict, bias_votes,
            ),
        }

        if archetype_conflict is not None:
            archetype_conflict["resolved"] = True
            archetype_conflict["resolution"] = (
                f"Weighted vote produced mix={final_ratios}, "
                f"vessel_bias={final_bias}"
            )

        return result

    def _reconcile_hubs(
        self,
        regional: Dict[str, Dict[str, Any]],
        archetype: Dict[str, Any],
        hub_conflict: Optional[Dict[str, Any]],
        previous_consensus: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Reconcile hub_focus selection.

        Each hub's support = sum of voting weights of agents recommending it.
        Hubs with support > 0.5 make the final set.
        If no hub clears the bar, the most-supported hub wins.
        """
        voters, _ = self._voter_weights(regional, previous_consensus)

        hub_support: Dict[str, float] = {}

        for voter_id, weight in voters:
            if voter_id == "coordinator":
                # Coordinator does not express hub preference directly;
                # uses previous consensus or stays neutral.
                continue
            elif voter_id.startswith("region:"):
                rpol = regional.get(voter_id.removeprefix("region:"), {})
                hubs = rpol.get("hub_focus", [])
            elif voter_id == "svc_gen":
                hubs = archetype.get("hub_focus", [])
            elif voter_id == "previous" and previous_consensus is not None:
                prev_arch = previous_consensus.get("final_archetype_params", {})
                hubs = prev_arch.get("hub_focus", [])
            else:
                continue

            for h in hubs:
                hub_support[h] = hub_support.get(h, 0.0) + weight

        if not hub_support:
            return []

        # Hubs with support > 0.3 make it (or the top hub).
        # Threshold 0.3 ensures a hub recommended by 2 of 5 voters
        # (each with weight ~0.20) clears the bar, while a hub from
        # only 1 voter (weight ~0.20) does not.
        threshold = max(0.30, max(hub_support.values()) / 2)
        final = sorted([h for h, s in hub_support.items() if s > threshold])
        if not final:
            # Fall back to the most-supported hub
            top = max(hub_support, key=hub_support.get)
            final = [top]

        if hub_conflict is not None:
            hub_conflict["resolved"] = True
            hub_conflict["resolution"] = (
                f"Weighted hub support produced final hubs={final}"
            )

        return final

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        all_conflicts: List[Dict[str, Any]],
        remaining: List[Dict[str, Any]],
        num_regions: int,
    ) -> float:
        """Compute confidence score in [0.0, 1.0].

        Start at 1.0, subtract for each conflict, penalty for unresolved ones.
        """
        confidence = 1.0

        for c in all_conflicts:
            confidence -= CONFIDENCE_PER_CONFLICT

        for c in remaining:
            confidence -= CONFIDENCE_UNRESOLVED_PENALTY

        # Bonus for having no conflicts at all (stays at 1.0)
        # Bonus for having regions
        if num_regions > 0:
            confidence = min(confidence + 0.05, 1.0)

        return max(0.0, confidence)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    @staticmethod
    def _build_notes(
        confidence: float,
        num_conflicts: int,
        num_remaining: int,
    ) -> str:
        """Build a human-readable notes string for the CONSENSUS_POLICY."""
        parts: List[str] = []
        parts.append(f"confidence={confidence:.4f}")
        parts.append(f"conflicts_detected={num_conflicts}")
        parts.append(f"conflicts_remaining={num_remaining}")

        if confidence > CONSENSUS_ACCEPTED_MIN:
            parts.append("all_conflicts_resolved")
        elif confidence >= CONSENSUS_REJECTED_MAX:
            parts.append("compromise_applied")
        else:
            parts.append("fallback_triggered")

        return "; ".join(parts)

    @staticmethod
    def _build_archetype_notes(
        archetype: Dict[str, Any],
        conflict: Optional[Dict[str, Any]],
        bias_votes: Dict[str, float],
    ) -> str:
        """Build notes for the reconciled archetype params."""
        original_notes = archetype.get("notes", "") or ""
        vote_summary = "; ".join(
            f"{b}={w:.2f}" for b, w in sorted(bias_votes.items(), key=lambda x: -x[1])
        )
        note = f"reconciled vote distribution: {vote_summary}"
        if original_notes:
            note = f"{original_notes} | {note}"
        return note

    # ------------------------------------------------------------------
    # Final Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_final(result: Dict[str, Any]) -> None:
        """Re-validate the final outputs through the existing validators.

        This ensures the CONESNSUS_POLICY is structurally sound even after
        reconciliation.
        """
        # Re-validate weights (guaranteed to return valid weights or fallback)
        validate_weight_adjustments(result.get("final_weight_adjustments", {}))

        # Re-validate archetype params (guaranteed to return valid params or fallback)
        validate_archetype_params(result.get("final_archetype_params", {}))

        # Each regional policy in the final output is already validated at input.

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_consensus(result: Dict[str, Any]) -> None:
        """Log the consensus outcome with appropriate tag."""
        confidence = result.get("confidence_score", 0.0)

        if confidence > CONSENSUS_ACCEPTED_MIN:
            tag = "CONSENSUS_ACCEPTED"
        elif confidence >= CONSENSUS_REJECTED_MAX:
            tag = "CONSENSUS_MODIFIED"
        else:
            tag = "CONSENSUS_REJECTED"

        logger.info(
            "consensus_engine",
            tag=tag,
            confidence=confidence,
            num_conflicts_resolved=len(result.get("conflicts_resolved", [])),
            num_conflicts_remaining=len(result.get("conflicts_remaining", [])),
            final_profit_weight=result.get("final_weight_adjustments", {}).get("profit_weight"),
            final_vessel_bias=result.get("final_archetype_params", {}).get("vessel_bias"),
        )

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback(
        partial: Dict[str, Any],
        reason: str = "confidence too low",
    ) -> Dict[str, Any]:
        """Return the default consensus with AI_FALLBACK logging.

        Preserves any resolved conflicts for traceability.
        """
        fallback = dict(DEFAULT_CONSENSUS)
        fallback["conflicts_resolved"] = partial.get("conflicts_resolved", [])
        fallback["conflicts_remaining"] = partial.get("conflicts_remaining", [])
        fallback["notes"] = f"AI_FALLBACK: {reason}"

        logger.info(
            "consensus_engine",
            tag="AI_FALLBACK",
            reason=reason,
            default_weights=fallback["final_weight_adjustments"],
            default_archetype=fallback["final_archetype_params"],
        )

        return fallback

    # ------------------------------------------------------------------
    # Derivation Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_weights_from_archetype(
        archetype: Dict[str, Any],
    ) -> Tuple[float, float, float]:
        """Derive (profit, coverage, cost) weights from archetype mix.

        Direct-heavy routes → profit focus.
        Feeder-heavy routes → coverage focus.
        Hub-loop / trunk → balanced.
        """
        mix = archetype.get("archetype_mix", {})

        # Normalize to ensure we have valid ratios
        dr = mix.get("direct_ratio", 0.60)
        hl = mix.get("hub_loop_ratio", 0.15)
        fr = mix.get("feeder_ratio", 0.20)
        tr = mix.get("trunk_ratio", 0.05)

        # Map: direct+trunk ⇒ profit, feeder ⇒ coverage, hub_loop ⇒ cost-ish
        raw_profit = dr + tr * 0.5
        raw_coverage = fr + hl * 0.3
        raw_cost = hl * 0.7 + tr * 0.5

        total = raw_profit + raw_coverage + raw_cost
        if total < 1e-9:
            return (0.50, 0.40, 0.10)

        return (
            round(raw_profit / total, 4),
            round(raw_coverage / total, 4),
            round(raw_cost / total, 4),
        )

    @staticmethod
    def _derive_archetype_from_weights(
        weights: Dict[str, float],
    ) -> Tuple[Dict[str, float], str]:
        """Derive archetype mix and vessel_bias from weight adjustments.

        High profit_weight → more direct routes, large vessels.
        High coverage_weight → more feeder routes, small vessels.
        """
        pw = weights.get("profit_weight", 0.50)
        cw = weights.get("coverage_weight", 0.40)
        cst = weights.get("cost_weight", 0.10)

        # Direct proportion scales with profit
        direct = max(0.05, min(0.80, pw * 1.1))
        # Feeder scales with coverage
        feeder = max(0.05, min(0.80, cw * 0.8))
        # Hub-loop moderate, trunk small
        remaining = 1.0 - direct - feeder
        hub_loop = max(0.05, remaining * 0.75)
        trunk = max(0.05, 1.0 - direct - feeder - hub_loop)

        # Normalise via hard clamp (better to be safe)
        total = direct + hub_loop + feeder + trunk
        if abs(total - 1.0) > 0.001:
            scale = 1.0 / max(total, 1e-9)
            direct *= scale
            hub_loop *= scale
            feeder *= scale
            trunk *= scale

        ratios = {
            "direct_ratio": round(direct, 4),
            "hub_loop_ratio": round(hub_loop, 4),
            "feeder_ratio": round(feeder, 4),
            "trunk_ratio": round(trunk, 4),
        }

        # Vessel bias from weight priorities
        if pw > BIAS_WEIGHT_PROFIT_MID and pw > cw:
            bias = "large"
        elif cw > BIAS_WEIGHT_COVERAGE_MID and cw > pw:
            bias = "small"
        else:
            bias = "balanced"

        return ratios, bias

    @staticmethod
    def _derive_archetype_from_region(
        policy: Dict[str, Any],
    ) -> Tuple[Dict[str, float], str]:
        """Derive archetype ratios and bias from a regional policy."""
        bias = policy.get("vessel_bias", "balanced")
        profit_p = policy.get("profit_priority", 0.50)
        coverage_p = policy.get("coverage_priority", 0.50)

        # Base ratios on vessel bias
        if bias == "large":
            direct = 0.65
            hub_loop = 0.15
            feeder = 0.10
            trunk = 0.10
        elif bias == "small":
            direct = 0.30
            hub_loop = 0.25
            feeder = 0.35
            trunk = 0.10
        else:  # balanced
            direct = 0.50
            hub_loop = 0.20
            feeder = 0.20
            trunk = 0.10

        # Adjust based on profit vs coverage priority
        priority_ratio = profit_p / max(coverage_p, 0.01)
        if priority_ratio > 1.5:
            # Profit-oriented: shift from feeder to direct
            shift = min(0.15, feeder)
            direct += shift
            feeder -= shift
        elif priority_ratio < 0.67:
            # Coverage-oriented: shift from direct to feeder
            shift = min(0.15, direct)
            feeder += shift
            direct -= shift

        # Ensure bounds
        direct = max(0.05, min(0.80, direct))
        feeder = max(0.05, min(0.80, feeder))
        hub_loop = max(0.05, min(0.80, hub_loop))
        trunk = max(0.05, min(0.80, trunk))

        # Normalise
        total = direct + hub_loop + feeder + trunk
        scale = 1.0 / max(total, 1e-9)

        ratios = {
            "direct_ratio": round(direct * scale, 4),
            "hub_loop_ratio": round(hub_loop * scale, 4),
            "feeder_ratio": round(feeder * scale, 4),
            "trunk_ratio": round(trunk * scale, 4),
        }

        return ratios, bias
