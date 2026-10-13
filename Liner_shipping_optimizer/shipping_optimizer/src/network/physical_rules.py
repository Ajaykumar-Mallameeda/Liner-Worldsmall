"""Physical operating rules of the LINERLIB benchmark that the service model must honour (decision phase).

Evidence (primary source: the benchmark authors' reference code and their own solution logs in the LINERLIB
repository, ``include/bm_rotation.h``, ``src/bm_reader.cpp`` and ``results/.../WorldSmall_Best_Base.log``;
validated in ``reports/decision_phase/d08``):

* Canal fee.  ``calculate_canal_cost`` = traversals x class fee for ONE round trip, charged once per weekly
  rotation (the log's weekly "Canal costs" equal the sum of its services' per-round-trip canal costs;
  the traversal counts and costs of all 34 services of the best WorldSmall solution are reproduced by this
  rule).  A traversal is a directed leg of the CLOSED rotation flagged ``IsPanama`` / ``IsSuez`` in
  ``dist_dense.csv``.
* Draft feasibility.  ``rotation::is_draft_feasible`` - "there must be draft feasibility between vessel class and
  port calls": the class draft may not exceed the draft of any port it calls at, nor the draft limit given on a
  leg (the file lists a draft only on the Panama edges).  The authors' solution has no violation (0 of 34
  services); the draft values of ``ports.csv`` are exactly the class drafts of the fleet.
* A blank canal fee (Panama for Post_panamax / Super_panamax) means the class cannot pass: such a class
  appears in no Panama traversal of the authors' solution and is also excluded by the Panama edge draft.
  It is never treated as a zero fee.

A distance matrix that carries ``canal_flags`` and ``edge_draft`` (see ``LinerDistanceMatrix``) enables the
rules; a plain dict (synthetic test instances) has no canal or draft information and is not restricted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

DRAFT_TOL = 1e-9


class LinerDistanceMatrix(dict):
    """``matrix[origin][dest] = nautical miles`` plus per-directed-pair canal flags and draft limits."""

    def __init__(self, *a, canal_flags: Optional[Dict[Tuple[str, str], Tuple[int, int]]] = None,
                 edge_draft: Optional[Dict[Tuple[str, str], float]] = None, **kw):
        super().__init__(*a, **kw)
        self.canal_flags: Dict[Tuple[str, str], Tuple[int, int]] = canal_flags or {}   # (is_panama, is_suez)
        self.edge_draft: Dict[Tuple[str, str], float] = edge_draft or {}


@dataclass
class RotationRules:
    canal_fee_per_rotation: float = 0.0
    panama_traversals: int = 0
    suez_traversals: int = 0
    reasons: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


def check_rotation(ports: Sequence[str], vessel, distance_matrix, port_lookup) -> RotationRules:
    """Canal fee and draft feasibility of the closed rotation ``ports`` for ``vessel`` (a FleetClass)."""
    out = RotationRules()
    ports = list(ports)
    if len(ports) >= 2 and ports[0] == ports[-1]:
        ports = ports[:-1]
    legs = [(ports[i], ports[(i + 1) % len(ports)]) for i in range(len(ports))]
    vdraft = float(getattr(vessel, "draft", 0.0) or 0.0)
    if vdraft > 0:
        for p in ports:
            pd_ = float(getattr(port_lookup.get(p), "draft", 0.0) or 0.0)
            if pd_ > 0 and vdraft > pd_ + DRAFT_TOL:
                out.reasons.append("draft_exceeds_port_limit")
                out.details.append(f"class draft {vdraft:g} m > port {p} draft {pd_:g} m")
                break
        edge_draft = getattr(distance_matrix, "edge_draft", None) or {}
        for l in legs:
            ed = edge_draft.get(l)
            if ed is not None and vdraft > ed + DRAFT_TOL:
                out.reasons.append("draft_exceeds_leg_limit")
                out.details.append(f"class draft {vdraft:g} m > leg {l[0]}->{l[1]} limit {ed:g} m")
                break
    flags = getattr(distance_matrix, "canal_flags", None) or {}
    for l in legs:
        pan, sue = flags.get(l, (0, 0))
        out.panama_traversals += int(pan)
        out.suez_traversals += int(sue)
    for n, fee, name in ((out.panama_traversals, getattr(vessel, "panama_fee", None), "Panama"),
                         (out.suez_traversals, getattr(vessel, "suez_fee", None), "Suez")):
        if n <= 0:
            continue
        if fee is None:
            out.reasons.append("canal_not_passable_for_class")
            out.details.append(f"{name} traversed {n}x but the class has no {name} fee (cannot pass)")
        else:
            out.canal_fee_per_rotation += n * float(fee)
    return out
