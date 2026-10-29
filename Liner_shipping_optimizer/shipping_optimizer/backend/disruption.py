"""
Disruptions for the what-if and the resilience ranking: closed chokepoints and closed ports (read-only).

Closed passages (searoute ids: suez, babalmandab, panama, ormuz, malacca, gibraltar, bosporus, sunda, ...)
-------------------------------------------------------------------------------------------------------
Every leg of the recorded plan (closed rotations, the return leg included) is looked up on the sea-lane
network (backend/searoutes.py). Whether a leg crosses Suez or Panama follows LINERLIB's own canal flags for the
pair (the lanes can snap a port to the wrong side of a canal); straits follow the sea lane. A leg that
crosses a closed passage is re-routed: searoute finds
the shortest lane that avoids the closed passages and the preset's `detour_avoid` passages. The leg's new
distance is

  * the LINERLIB alternative record of that port pair whose canal flags match the detour's canals (the
    dataset's own non-canal distance, e.g. the Cape route), when the dataset has one, else
  * the LINERLIB distance x (detour sea-lane length / normal sea-lane length): the optimizer's distance
    scaled by the detour searoute measures, so legs stay on the dataset's own distance basis.

The leg's canal flags follow the detour (no Suez fee round the Cape) and a canal draft limit no longer
applies once the detour uses no canal. A leg with no open sea lane (a port inside a closed sea, e.g. the
Gulf behind Hormuz) cannot sail: its service is suspended. Services, departures and vessel classes are
otherwise unchanged; the ledger then needs more vessels for the longer cycles and burns more fuel.

Closed ports
------------
Each service skips the closed ports (rotation re-sequenced, the next port follows directly); a service left
with fewer than two ports is suspended. Demand to and from a closed port has no path and goes unserved.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from backend import searoutes

# Ready-made closures. detour_avoid: passages a detour may not use either (with the reason on screen).
PRESETS: Dict[str, Dict] = {
    "red_sea": {
        "label": "Red Sea closed (Bab-el-Mandeb)", "closed": ["babalmandab"], "detour_avoid": ["panama"],
        "note": "As carriers did from December 2023: Asia-Europe services go round the Cape of Good Hope; "
                "detours may not use the Panama Canal. Red Sea ports stay reachable through Suez.",
    },
    "suez": {
        "label": "Suez Canal closed", "closed": ["suez"], "detour_avoid": ["panama"],
        "note": "Like the Ever Given blockage (March 2021): detours round the Cape, not through Panama.",
    },
    "panama": {
        "label": "Panama Canal closed", "closed": ["panama"], "detour_avoid": [],
        "note": "An extreme of the 2023-24 drought restrictions: legs take the next shortest open sea lane.",
    },
    "hormuz": {
        "label": "Strait of Hormuz closed", "closed": ["ormuz"], "detour_avoid": [],
        "note": "Ports inside the Gulf cannot be reached; services calling them are suspended.",
    },
    "malacca": {
        "label": "Strait of Malacca closed", "closed": ["malacca"], "detour_avoid": [],
        "note": "Legs through Malacca take the next shortest open lane (Sunda or Lombok side).",
    },
    "gibraltar": {
        "label": "Strait of Gibraltar closed", "closed": ["gibraltar"], "detour_avoid": [],
        "note": "Mediterranean ports are reachable only through Suez.",
    },
    "bosporus": {
        "label": "Bosporus closed", "closed": ["bosporus"], "detour_avoid": [],
        "note": "Black Sea ports cannot be reached; services calling them are suspended.",
    },
}


def resolve(preset: Optional[str], closed: Sequence[str], detour_avoid: Sequence[str]) -> Tuple[Tuple[str, ...], Tuple[str, ...], Optional[Dict]]:
    """(closed, detour_avoid, preset record) from a preset key and/or explicit lists; unknown names raise ValueError."""
    p = None
    c, d = list(closed or []), list(detour_avoid or [])
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; valid: {sorted(PRESETS)}")
        p = PRESETS[preset]
        c += p["closed"]
        d += p["detour_avoid"]
    bad = [x for x in c + d if x not in searoutes.VALID_PASSAGES]
    if bad:
        raise ValueError(f"unknown passage(s) {bad}; valid: {sorted(searoutes.VALID_PASSAGES)}")
    c_t = tuple(sorted(set(c)))
    return c_t, tuple(sorted(set(d) - set(c_t))), p


def rotation_legs(ports: Sequence[str]) -> List[Tuple[str, str]]:
    """Directed legs of a closed rotation (the return leg included), as the ledger sails it."""
    ps = list(ports)
    if len(ps) >= 2 and ps[0] == ps[-1]:
        ps = ps[:-1]
    return [(ps[i], ps[(i + 1) % len(ps)]) for i in range(len(ps))] if len(ps) >= 2 else []


CANALS = {"suez", "panama"}


def crossed(route: Dict, closed: Sequence[str]) -> List[str]:
    """Closed passages a leg crosses. Canals follow LINERLIB's own flags for the pair (the distance the optimizer
    uses), since the sea-lane network can snap a port to the other side of a canal; straits follow the sea lane."""
    lin = route.get("model_canal") or {}
    out = [p for p in closed if p not in CANALS and p in route["passages"]]
    for c in CANALS & set(closed):
        uses = lin.get(c) if lin else None
        if (int(uses) == 1) if uses is not None else (c in route["passages"]):
            out.append(c)
    return sorted(out)


def _copy_matrix(matrix):
    from src.network.physical_rules import LinerDistanceMatrix
    return LinerDistanceMatrix({o: dict(r) for o, r in matrix.items()},
                               canal_flags=dict(getattr(matrix, "canal_flags", {}) or {}),
                               edge_draft=dict(getattr(matrix, "edge_draft", {}) or {}))


def close_passages(dataset: str, services: List[Dict], matrix, closed: Sequence[str],
                   detour_avoid: Sequence[str] = ()) -> Tuple[object, List[Dict], Dict]:
    """(new distance matrix, services still sailing, report) when `closed` passages are shut (see module doc)."""
    closed, detour_avoid = tuple(sorted(set(closed))), tuple(sorted(set(detour_avoid) - set(closed)))
    legs = sorted({leg for s in services for leg in rotation_legs(s["ports"])})
    base = searoutes.routes_for(dataset, legs, ())
    hit = [leg for leg in legs if f"{leg[0]}|{leg[1]}" in base and crossed(base[f"{leg[0]}|{leg[1]}"], closed)]
    detours = searoutes.routes_for(dataset, hit, closed + detour_avoid) if hit else {}
    alts = searoutes._dataset(dataset).get("alternatives", {})
    m2 = _copy_matrix(matrix)
    rerouted: Dict[Tuple[str, str], Dict] = {}
    blocked: Dict[Tuple[str, str], Dict] = {}
    for a, b in hit:
        k = f"{a}|{b}"
        old_nm = float((matrix.get(a) or {}).get(b) or 0.0)
        det = detours.get(k)
        if det is None or set(det["passages"]) & set(closed + detour_avoid):
            blocked[(a, b)] = {"from": a, "to": b, "via_before": base[k]["passages"]}
            continue
        uses_suez, uses_pan = int("suez" in det["passages"]), int("panama" in det["passages"])
        match = [r for r in alts.get((a, b), []) if int(r.get("is_suez") or 0) == uses_suez
                 and int(r.get("is_panama") or 0) == uses_pan]
        if match:
            rec = min(match, key=lambda r: r["distance"])
            new_nm, source, draft = float(rec["distance"]), "LINERLIB alternative record", rec.get("draft")
        else:
            ratio = det["nm"] / base[k]["nm"] if base[k]["nm"] > 0 else 1.0
            new_nm, source, draft = old_nm * ratio, "LINERLIB distance x searoute detour ratio", None
        if new_nm < old_nm:             # a detour is never shorter: the lanes snapped the ports differently
            new_nm, source = old_nm, source + " (not longer than the normal lane: distance kept)"
        m2.setdefault(a, {})[b] = new_nm
        m2.canal_flags[(a, b)] = (uses_pan, uses_suez)          # (is_panama, is_suez)
        if draft:
            m2.edge_draft[(a, b)] = float(draft)
        elif not (uses_suez or uses_pan):
            m2.edge_draft.pop((a, b), None)                    # no canal on the detour: no canal draft limit
        rerouted[(a, b)] = {"from": a, "to": b, "nm_before": old_nm, "nm_after": round(new_nm, 1),
                            "via_before": base[k]["passages"], "via_after": det["passages"], "source": source}

    sailing, suspended = [], []
    extra_nm = 0.0
    for s in services:
        sl = rotation_legs(s["ports"])
        stop = [rl for rl in sl if rl in blocked]
        if stop:
            suspended.append({"id": s["id"], "reason": f"no open sea lane {stop[0][0]} → {stop[0][1]}",
                              "via_before": blocked[stop[0]]["via_before"]})
            continue
        sailing.append(s)
        f = int(s.get("frequency_per_week") or 0)
        for rl in sl:
            if rl in rerouted:
                rerouted[rl].setdefault("services", []).append(s["id"])
                extra_nm += f * (rerouted[rl]["nm_after"] - rerouted[rl]["nm_before"])
    report = {
        "closed_passages": list(closed), "detour_avoid": list(detour_avoid),
        "legs_checked": len(legs), "legs_without_sea_lane": [f"{a}|{b}" for a, b in legs if f"{a}|{b}" not in base],
        "rerouted_legs": sorted(rerouted.values(), key=lambda r: -(r["nm_after"] - r["nm_before"])),
        "suspended_services": suspended,
        "extra_nm_per_week": round(extra_nm, 1),
    }
    return m2, sailing, report


def close_ports(services: List[Dict], ports: Iterable[str]) -> Tuple[List[Dict], Dict]:
    """(services still sailing with the closed ports skipped, report)."""
    shut = {str(p).upper() for p in ports}
    sailing, changed, suspended = [], [], []
    for s in services:
        keep = [p for p in s["ports"] if p not in shut]
        if len(keep) >= 2 and keep[0] == keep[-1]:
            keep = keep[:-1]
        removed = [p for p in s["ports"] if p in shut]
        if not removed:
            sailing.append(s)
        elif len(set(keep)) < 2:
            suspended.append({"id": s["id"], "reason": f"fewer than two ports left without {', '.join(removed)}"})
        else:
            sailing.append({**s, "ports": keep})
            changed.append({"id": s["id"], "skips": removed})
    return sailing, {"closed_ports": sorted(shut), "services_skipping": changed, "suspended_services": suspended}
