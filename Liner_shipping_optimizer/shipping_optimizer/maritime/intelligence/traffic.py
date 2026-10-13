"""Traffic feature derivation.

The first three traffic features the program needs:

* traffic_density          — overall density per cell (any vessel class)
* cargo_density            — density per cell for cargo vessels
* tanker_density           — density per cell for tanker vessels
* traffic_hotspot_indicator — per-cell indicator of "this is a hotspot"

All features are derived from canonical records deterministically; the
intensity values are normalized into a [0, 1] ``relative_density`` for
visualization and a raw ``normalized_intensity`` for downstream math.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence

from ..schemas.traffic_density import TrafficDensityRecord, VesselClass
from ..schemas.intelligence import TrafficFeature, TrafficHotspot


# Order matches the prompt's "Required" list. Keep stable.
TRAFFIC_FEATURE_TYPES = {
    "traffic_density": "all",
    "cargo_density": VesselClass.CARGO,
    "tanker_density": VesselClass.TANKER,
}


def _safe_max(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    m = 0.0
    for v in values:
        if v > m:
            m = v
    return m


def _max_for_class(records: Sequence[TrafficDensityRecord], cls: VesselClass) -> float:
    vals = [r.intensity for r in records if r.vessel_class == cls]
    return _safe_max(vals)


def _max_overall(records: Sequence[TrafficDensityRecord]) -> float:
    return _safe_max([r.intensity for r in records])


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return max(0.0, min(1.0, value / max_value))


def _records_for(records: Sequence[TrafficDensityRecord], cls: VesselClass) -> List[TrafficDensityRecord]:
    return [r for r in records if r.vessel_class == cls]


def compute_traffic_features(
    records: Sequence[TrafficDensityRecord],
    *,
    feature_id_prefix: str = "feat",
) -> List[TrafficFeature]:
    """Derive per-cell traffic features for the snapshot.

    Three feature types are produced per spatial cell: ``traffic_density``,
    ``cargo_density``, ``tanker_density``. Each carries the raw and
    normalized intensity plus the relative density (in [0, 1] across
    the whole snapshot for the same feature type).
    """
    if not records:
        return []

    max_all = _max_overall(records)
    max_cargo = _max_for_class(records, VesselClass.CARGO)
    max_tanker = _max_for_class(records, VesselClass.TANKER)

    out: List[TrafficFeature] = []
    # Aggregate per spatial cell so the SAME cell doesn't appear twice.
    by_cell: dict[str, dict] = {}
    for r in records:
        cell = by_cell.setdefault(r.spatial_id, {
            "latitude": r.latitude,
            "longitude": r.longitude,
            "observed_at": r.observed_at,
            "all_intensity": 0.0,
            "cargo_intensity": 0.0,
            "tanker_intensity": 0.0,
        })
        cell["all_intensity"] += r.intensity
        if r.vessel_class == VesselClass.CARGO:
            cell["cargo_intensity"] += r.intensity
        elif r.vessel_class == VesselClass.TANKER:
            cell["tanker_intensity"] += r.intensity
        # Use the most recent observed_at for the cell.
        if r.observed_at > cell["observed_at"]:
            cell["observed_at"] = r.observed_at

    for spatial_id, c in by_cell.items():
        # all
        out.append(TrafficFeature(
            feature_id=f"{feature_id_prefix}:traffic_density:{spatial_id}",
            feature_type="traffic_density",
            spatial_id=spatial_id,
            latitude=c["latitude"],
            longitude=c["longitude"],
            raw_intensity=float(c["all_intensity"]),
            normalized_intensity=_normalize(float(c["all_intensity"]), max_all),
            relative_density=_normalize(float(c["all_intensity"]), max_all),
            observed_at=c["observed_at"],
            vessel_class=VesselClass.OTHER,
        ))
        # cargo
        out.append(TrafficFeature(
            feature_id=f"{feature_id_prefix}:cargo_density:{spatial_id}",
            feature_type="cargo_density",
            spatial_id=spatial_id,
            latitude=c["latitude"],
            longitude=c["longitude"],
            raw_intensity=float(c["cargo_intensity"]),
            normalized_intensity=_normalize(float(c["cargo_intensity"]), max_cargo),
            relative_density=_normalize(float(c["cargo_intensity"]), max_cargo),
            observed_at=c["observed_at"],
            vessel_class=VesselClass.CARGO,
        ))
        # tanker
        out.append(TrafficFeature(
            feature_id=f"{feature_id_prefix}:tanker_density:{spatial_id}",
            feature_type="tanker_density",
            spatial_id=spatial_id,
            latitude=c["latitude"],
            longitude=c["longitude"],
            raw_intensity=float(c["tanker_intensity"]),
            normalized_intensity=_normalize(float(c["tanker_intensity"]), max_tanker),
            relative_density=_normalize(float(c["tanker_intensity"]), max_tanker),
            observed_at=c["observed_at"],
            vessel_class=VesselClass.TANKER,
        ))
    return out


def compute_hotspots(
    records: Sequence[TrafficDensityRecord],
    *,
    top_n: int = 10,
    threshold_quantile: float = 0.9,
) -> List[TrafficHotspot]:
    """Identify the top-``N`` traffic hotspots by total density.

    A hotspot is a spatial cell whose total intensity is in the top
    ``threshold_quantile`` (default 90th percentile) of all cells. The
    dominant vessel class is the class contributing the largest share.
    """
    if not records:
        return []
    by_cell: dict[str, dict] = {}
    for r in records:
        c = by_cell.setdefault(r.spatial_id, {
            "latitude": r.latitude,
            "longitude": r.longitude,
            "observed_at": r.observed_at,
            "intensity": 0.0,
            "by_class": {},
        })
        c["intensity"] += r.intensity
        c["by_class"][r.vessel_class] = c["by_class"].get(r.vessel_class, 0.0) + r.intensity
        if r.observed_at > c["observed_at"]:
            c["observed_at"] = r.observed_at
    if not by_cell:
        return []
    cells_sorted = sorted(by_cell.items(), key=lambda kv: kv[1]["intensity"], reverse=True)
    # Threshold cut
    if cells_sorted:
        n = max(1, int(len(cells_sorted) * (1.0 - threshold_quantile)))
        keep = cells_sorted[: min(len(cells_sorted), max(n, top_n))]
    else:
        keep = []
    out: List[TrafficHotspot] = []
    total_intensity = sum(c["intensity"] for _, c in cells_sorted) or 1.0
    for spatial_id, c in keep:
        dom_cls = max(c["by_class"].items(), key=lambda kv: kv[1])[0] if c["by_class"] else VesselClass.UNKNOWN
        score = c["intensity"] / total_intensity
        out.append(TrafficHotspot(
            spatial_id=spatial_id,
            latitude=c["latitude"],
            longitude=c["longitude"],
            score=score,
            dominant_vessel_class=dom_cls,
            observed_at=c["observed_at"],
        ))
    return out
