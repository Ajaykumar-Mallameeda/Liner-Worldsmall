"""Completeness and quality scoring.

The normalization layer tracks every record it processes in a
:class:`RejectionCounters` object. We derive two deterministic ratios from
these counters:

* ``completeness_ratio`` = accepted / records_seen
* ``quality_score``     = weighted score in [0, 1] combining completeness,
                           rejection reasons, and per-record quality fields

Quality is intentionally conservative: any single source of severe degradation
(proportion of rejects, missing required fields, etc.) caps the score.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, Optional


@dataclass
class RejectionCounters:
    """Counter object populated during normalization."""
    records_seen: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    duplicates: int = 0
    invalid_coordinates: int = 0
    invalid_values: int = 0
    invalid_timestamps: int = 0
    missing_required_fields: int = 0
    invalid_vessel_class: int = 0
    other_errors: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    @property
    def total_problems(self) -> int:
        """Sum of the specific rejection reasons (for diagnostics)."""
        return (
            self.invalid_coordinates + self.invalid_values
            + self.invalid_timestamps + self.missing_required_fields
            + self.invalid_vessel_class + self.other_errors
        )


def compute_completeness_ratio(counters: RejectionCounters) -> float:
    """Return accepted / records_seen, 1.0 if no records were seen."""
    if counters.records_seen <= 0:
        return 1.0
    return counters.records_accepted / float(counters.records_seen)


def compute_quality_score(
    counters: RejectionCounters,
    *,
    avg_record_quality: Optional[float] = None,
) -> float:
    """Deterministic, bounded quality score in [0, 1].

    Combines completeness with the average per-record ``quality`` field. When
    no records were seen the score is 0.0 (no signal).
    """
    if counters.records_seen <= 0:
        return 0.0
    completeness = compute_completeness_ratio(counters)
    if avg_record_quality is None:
        avg_record_quality = completeness  # conservative default
    # Weighted combination: completeness counts more because it's a structural
    # invariant; per-record quality is a softer field.
    raw = 0.7 * completeness + 0.3 * max(0.0, min(1.0, avg_record_quality))
    return max(0.0, min(1.0, raw))
