"""Trans-Pacific and Atlantic trunk-candidate family (opt-in, default OFF).

Motivation (measured, reports/class_mismatch_campaign and reports/continuation_20261015): with the class-forced trunks
of ``trunk_candidates`` about 32 of 58 Post_panamax vessels stay idle and the Post_panamax trunks all concentrate on the
Asia - Europe hubs.  This family adds a SMALL, explicit set of additional candidates on two lane pairs:

  * ``transpacific``: East/South-East Asia  <->  Pacific-side Americas
  * ``atlantic``    : Europe / West Mediterranean  <->  Atlantic-side Americas

Environment (all unset / 0 = OFF; the existing generators are untouched):
  ``LINER_TRUNK_LANES``          comma list of lanes, e.g. ``transpacific,atlantic``; ``all`` = every lane
  ``LINER_TRUNK_LANE_COUNT``     rotations kept per lane and class (default 2, hard maximum 6)
  ``LINER_TRUNK_LANE_CLASSES``   comma list of vessel classes (default ``Post_panamax,Super_panamax``)
  ``LINER_TRUNK_LANE_MAX_PORTS`` ports per rotation (default 8, 3-12)

Every additional rotation is an ordinary ``Candidate``.  It goes through the same checks as every other candidate:
class draft at every port, canal access and class fee (a blank Panama fee means the class cannot pass), design speed
and cycle time, vessels against inventory, ride-feasible cargo inside each OD's transit limit, positive stand-alone
profit under the canonical economics (``demand_coherent._Evaluator``), then the global MILP, which decides with the
real costs, and the independent ledger.  Nothing is forced into the network.  Rejections are counted per constraint in
the report (``per_class``): grown / non-positive stand-alone profit / already in the pool / near-duplicate / cap.

The port groups below are explicit UN/LOCODE lists derived from the ``D_Region`` column of ``ports.csv`` (checked by
``tests/test_trunk_lanes.py``); a port that is absent from the loaded problem is ignored.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

from src.network.trunk_candidates import augment_trunk_candidates

ENV_LANES = "LINER_TRUNK_LANES"
ENV_COUNT = "LINER_TRUNK_LANE_COUNT"
ENV_CLASSES = "LINER_TRUNK_LANE_CLASSES"
ENV_MAX_PORTS = "LINER_TRUNK_LANE_MAX_PORTS"
DEFAULT_COUNT = 2
HARD_MAX_COUNT = 6
DEFAULT_CLASSES = ("Post_panamax", "Super_panamax")
DEFAULT_MAX_PORTS = 8

# D_Region labels of ports.csv behind each group (WorldSmall)
LANE_GROUPS: Dict[str, Dict[str, Dict]] = {
    "transpacific": {
        "a": {"d_regions": ("Singapore", "Hong Kong", "South China", "North China", "Central China", "Korea", "Japan"),
              "ports": ("MYPKG", "MYTPP", "SGSIN", "TWKHH", "HKHKG", "CNYTN", "CNTAO", "CNSHA", "KRPUS", "JPYOK")},
        "b": {"d_regions": ("Canada West", "US West Coast", "South America West Coast"),
              "ports": ("CAVAN", "USLAX", "PABLB", "ECGYE", "CLSAI")},
        "id_prefix": "tp",
    },
    "atlantic": {
        "a": {"d_regions": ("North Continent Europe", "UK", "West Med"),
              "ports": ("NLRTM", "DEBRV", "DEHAM", "BEANR", "BEZEE", "GBFXT", "ESALG", "MAPTM", "ESBCN", "ITGIT")},
        "b": {"d_regions": ("US East Coast", "US Gulf Coast", "Canada East Coast", "Brazil"),
              "ports": ("USEWR", "USCHS", "USMIA", "CAMTR", "BRSSZ", "UYMVD", "PAMIT")},
        "id_prefix": "at",
    },
}
# PABLB / PAMIT are labelled "US West Coast" in ports.csv; by position PABLB is the Pacific and PAMIT the Atlantic mouth of
# the Panama Canal, so they sit in the Pacific and Atlantic group respectively (a documented, auditable choice).


def lanes_from_environment(env: Optional[Dict[str, str]] = None) -> List[str]:
    raw = ((os.environ if env is None else env).get(ENV_LANES) or "").strip()
    if not raw or raw in ("0", "off", "false"):
        return []
    lanes = [x.strip().lower() for x in raw.split(",") if x.strip()]
    if lanes == ["all"]:
        lanes = sorted(LANE_GROUPS)
    bad = [x for x in lanes if x not in LANE_GROUPS]
    if bad:
        raise ValueError(f"{ENV_LANES}: unknown lane(s) {bad}; allowed: {sorted(LANE_GROUPS)}")
    return list(dict.fromkeys(lanes))


def count_from_environment(env: Optional[Dict[str, str]] = None) -> int:
    raw = ((os.environ if env is None else env).get(ENV_COUNT) or "").strip()
    if not raw:
        return DEFAULT_COUNT
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_COUNT} must be an integer, got {raw!r}") from None
    if n < 1 or n > HARD_MAX_COUNT:
        raise ValueError(f"{ENV_COUNT} must be in [1, {HARD_MAX_COUNT}], got {n}")
    return n


def classes_from_environment(env: Optional[Dict[str, str]] = None) -> Tuple[str, ...]:
    raw = ((os.environ if env is None else env).get(ENV_CLASSES) or "").strip()
    if not raw:
        return DEFAULT_CLASSES
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def max_ports_from_environment(env: Optional[Dict[str, str]] = None) -> int:
    raw = ((os.environ if env is None else env).get(ENV_MAX_PORTS) or "").strip()
    if not raw:
        return DEFAULT_MAX_PORTS
    try:
        n = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_MAX_PORTS} must be an integer, got {raw!r}") from None
    if n < 3 or n > 12:
        raise ValueError(f"{ENV_MAX_PORTS} must be in [3, 12], got {n}")
    return n


def augment_lane_candidates(problem, assumptions, candidates: Sequence, *, lanes: Sequence[str], per_class: int,
                            classes: Sequence[str] = DEFAULT_CLASSES, max_ports: int = DEFAULT_MAX_PORTS,
                            deadline: Optional[float] = None, diverse: bool = True,
                            collect_rejected: Optional[List[Dict]] = None) -> Tuple[List, Dict]:
    """(new candidates, report).  ``candidates`` must include the trunks added before (so duplicates are dropped)."""
    present = {p.id for p in problem.ports}
    new_all: List = []
    report: Dict = {"enabled": True, "lanes": list(lanes), "per_class_per_lane": per_class, "classes": list(classes),
                    "max_ports": max_ports, "by_lane": {}, "added": 0}
    pool = list(candidates)
    for lane in lanes:
        spec = LANE_GROUPS[lane]
        ga = set(spec["a"]["ports"]) & present
        gb = set(spec["b"]["ports"]) & present
        new, rep = augment_trunk_candidates(problem, assumptions, pool, per_class=per_class, max_ports=max_ports,
                                            deadline=deadline, id_prefix=spec["id_prefix"], diverse=diverse,
                                            classes=classes, port_filter=ga | gb, seed_groups=(ga, gb),
                                            collect_rejected=collect_rejected)
        rep["lane"] = lane
        rep["group_a_ports"] = sorted(ga)
        rep["group_b_ports"] = sorted(gb)
        report["by_lane"][lane] = rep
        report["added"] += len(new)
        new_all.extend(new)
        pool.extend(new)            # later lanes do not duplicate rotations of earlier ones
    return new_all, report
