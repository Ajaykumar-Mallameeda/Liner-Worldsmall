"""Phase 3 — Snapshot rollback helper.

Bounded, deterministic rollback to the most recent verified snapshot.

The helper is intentionally narrow: it does NOT touch the optimizer,
does NOT call the network, and does NOT modify live state. It scans
the dataset directory in lex order, runs the verifier on each
candidate, and returns the highest-priority verified candidate.

This module is the read-side companion to :mod:`maritime.snapshot_publisher`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from .fallback_resolver import (
    FallbackDecision,
    FallbackTier,
    resolve_snapshot_fallback,
)
from .schema_registry import SchemaRegistry
from .freshness_policy import FreshnessConfig


@dataclass(frozen=True)
class RollbackPlan:
    """Outcome of a rollback request.

    The plan is a *recommendation*. The caller (e.g. an operator
    script) decides whether to act on it; the helper never mutates
    state itself.
    """
    dataset: str
    decision: FallbackDecision
    candidates_considered: int
    candidates_verified: int
    candidates_rejected: int

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "decision": self.decision.to_dict(),
            "candidates_considered": self.candidates_considered,
            "candidates_verified": self.candidates_verified,
            "candidates_rejected": self.candidates_rejected,
        }


def plan_rollback(
    *,
    dataset: str,
    snapshot_root: Path,
    registry: Optional[SchemaRegistry] = None,
    config: Optional[FreshnessConfig] = None,
) -> RollbackPlan:
    """Build a rollback plan for ``dataset`` under ``snapshot_root``.

    The plan picks the best verified snapshot according to the
    fallback hierarchy. The previous known-good snapshot is always
    returned when any verified snapshot exists, regardless of how
    recent a failed publication attempt was.
    """
    cfg = config or FreshnessConfig()
    reg = registry or SchemaRegistry.with_defaults()
    decision = resolve_snapshot_fallback(
        dataset=dataset,
        snapshot_root=snapshot_root,
        registry=reg,
        config=cfg,
    )

    base = snapshot_root / dataset
    candidates: List[Path] = []
    if base.is_dir():
        for child in sorted(base.iterdir(), reverse=True):
            if child.is_dir() and (child / "manifest.json").exists():
                candidates.append(child)

    verified = 0
    rejected = 0
    for cand in candidates:
        from .snapshot_verifier import verify_snapshot_directory
        v = verify_snapshot_directory(
            cand,
            compatible_schema_versions=reg.compatible_versions(dataset),
        )
        if v.ok:
            verified += 1
        else:
            rejected += 1

    return RollbackPlan(
        dataset=dataset,
        decision=decision,
        candidates_considered=len(candidates),
        candidates_verified=verified,
        candidates_rejected=rejected,
    )
