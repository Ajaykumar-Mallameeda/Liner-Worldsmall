#!/usr/bin/env python3
"""Deterministic generator of the synthetic World-500 / World-1000 benchmark datasets.

    python scripts/multi_dataset/generate_synthetic.py                    # both sizes, seed 20261016
    python scripts/multi_dataset/generate_synthetic.py --sizes 500 --out-root <dir>

These are SYNTHETIC networks, not observations. They are calibrated on the LINERLIB benchmark so that the
accepted optimizer sees the same kind of inputs (same file formats, class table, canal / draft conventions) at
500 and 1000 ports. Generation is separate from the optimizer and reads only LINERLIB source files (never
WorldLarge, never the repository's WorldSmall package) and writes only below ``data/raw/World-<N>/``.

Method (version GENERATOR_VERSION; every parameter and every input hash is written to
``data/raw/World-<N>/generation_manifest.json``):

1. Ports.  A common population of 1000 ports is built once (World-500 = its first 500 ports; a stratified
   round-robin over the anchors keeps every prefix regionally balanced). Each synthetic port is attached to a REAL
   "anchor" port of LINERLIB (anchors: ports with a complete record - draft, costs >= 0, coordinates - that
   also have mutual routed distances in ``dist_dense.csv``). Position = anchor + Gaussian offset (sigma in
   nautical miles); draft = anchor draft (85 %) or a draw from the empirical draft levels; the four cost fields =
   anchor value x lognormal(0, within-country dispersion measured on the source). Identifiers ``ZZ000`` ...
   ``ZZ999``: ``ZZ`` is not an assigned country code, so they cannot collide with a real UN/LOCODE (asserted).
2. Distances.  Geodesic (haversine) distance of the synthetic positions x the routing circuity of the
   anchors' selected LINERLIB record (clipped to [1, 3]); canal flags and draft limit of that record are copied,
   so the existing canal-fee and draft rules apply unchanged. Two ports of one anchor use the median circuity
   of short real legs. One (shortest) record per directed pair - the accepted model's convention; synthetic
   route alternatives are not generated. APPROXIMATED shipping distances: no coastline, strait or
   traffic-separation data was used.
3. Demand.  Sparse gravity network: per-port out-degree ~ lognormal with the geometric mean of the four
   full-size LINERLIB instances' mean out-degrees; partners drawn without replacement with probability
   proportional to partner mass / (1 + distance/1500 nm); the reverse OD is added with the pooled real
   probability, with a lognormal directional imbalance measured on real reverse pairs. FFE per week is drawn from
   the pooled real distribution by stratified quantile sampling (same marginal as a bootstrap, without the
   heavy-tail wander of the sample mean, so both sizes have the same demand intensity); Revenue_1 = exp(a + b ln
   distance + residual) with (a, b) fitted on the pooled real instances and residuals drawn the same way;
   TransitTime = clip(round(rho x distance / (14 kn x 24)), 3, 70) days with rho drawn the same way from the
   real transit / sailing-time ratios. Every drawn value is limited to the support observed in LINERLIB (FFE per
   OD <= pooled maximum, Revenue_1 within the pooled range, transit 3-70 days); synthetic distances are integer
   nm rounded UP, so never below the geodesic.
4. Fleet.  Same rule for both sizes, calibrated against DEMAND VOLUME (not port count): vessels in total =
   round(weekly FFE / FFE-per-vessel of WorldSmall) with WorldSmall's class mix (min 1 per class). The class
   table (``fleet_data.csv``) is a byte copy of the LINERLIB file. The fleet is therefore not inflated to
   guarantee coverage or profit; it is the same demand-per-vessel ratio as the reference case.

Nothing is tuned after seeing optimizer output. Regenerating with the same generator version, seed, numpy
version and source files reproduces every file byte for byte (``--check``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data" / "LINERLIB-master" / "data"
DEFAULT_OUT_ROOT = ROOT / "data" / "raw"

GENERATOR_VERSION = "1.0.1"
DEFAULT_SEED = 20261016
POPULATION = 1000
SIZES = (500, 1000)
EARTH_RADIUS_NM = 3440.065

# calibration instances (LINERLIB). WorldLarge is deliberately NOT used.
CALIBRATION = ("WorldSmall_Fixed_Sep", "EuropeAsia", "Mediterranean", "Pacific", "Baltic", "WAF")
FULL_SIZE = ("WorldSmall_Fixed_Sep", "EuropeAsia", "Mediterranean", "Pacific")     # for the out-degree statistic
FLEET_REFERENCE = ("WorldSmall_Fixed_Sep", "fleet_WorldSmall.csv")                 # fleet mix + demand-per-vessel

PORT_JITTER_NM = 100.0          # std of the offset of a synthetic port from its anchor
DRAFT_INHERIT_P = 0.85
GRAVITY_SCALE_NM = 1500.0
CIRCUITY_CLIP = (1.0, 3.0)
LOCAL_LEG_NM = 500.0            # anchor pairs closer than this use the local circuity
TT_RANGE = (3, 70)              # observed range of the LINERLIB TransitTime column
COST_COLS = ("CostPerFULL", "CostPerFULLTrnsf", "PortCallCostFixed", "PortCallCostPerFFE")
PORT_HEADER = "UNLocode\tname\tCountry\tCabotage_Region\tD_Region\tLongitude\tLatitude\tDraft\t" \
              "CostPerFULL\tCostPerFULLTrnsf\tPortCallCostFixed\tPortCallCostPerFFE"
LIMITATIONS = [
    "synthetic positions are not checked against coastlines: some may lie on land or in an impossible place",
    "distances are approximated (geodesic x anchor routing circuity); no strait, canal geometry or traffic data; "
    "the triangle inequality is not enforced (measured and reported)",
    "only one (shortest) record per directed pair; no synthetic route alternatives",
    "port mass is iid lognormal: no hub hierarchy beyond what the gravity weights induce",
    "demand, revenue and transit are bootstrapped from six LINERLIB instances that differ in scale; the pooled "
    "distribution is a modelling choice, not a measurement of any real trade",
    "the fleet rule reproduces WorldSmall's demand-per-vessel ratio; it does not guarantee that the fleet is "
    "adequate (or too large) for a 500/1000 port network",
    "the population is one random draw (seed recorded); economic results on it are not statements about real shipping",
]


# ------------------------------------------------------------------------------------------------ small helpers
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stream(seed: int, *labels) -> np.random.Generator:
    """Independent generator per component, stable across Python hash randomisation."""
    h = hashlib.sha256(("|".join([str(seed)] + [str(x) for x in labels])).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def read_tsv(path: Path):
    lines = path.read_bytes().decode("utf-8").splitlines()
    header = lines[0].split("\t")
    return header, [ln.split("\t") for ln in lines[1:] if ln.strip()]


def stratified_draw(rng, pool, m):
    """m draws from the empirical distribution of ``pool`` by stratified quantile sampling (one draw per equal-
    probability stratum, strata visited in random order). Same marginal as a plain bootstrap, but the sample mean
    of a heavy-tailed pool does not wander with m, so World-500 and World-1000 get the same demand intensity."""
    u = (rng.permutation(m) + rng.random(m)) / m
    return np.quantile(np.asarray(pool, dtype=float), u)


def haversine_matrix(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    dlat = la[None, :] - la[:, None]
    dlon = lo[None, :] - lo[:, None]
    a = np.sin(dlat / 2) ** 2 + np.cos(la)[:, None] * np.cos(la)[None, :] * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_NM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def fmt_g(v: float) -> str:
    return f"{v:g}"


# ------------------------------------------------------------------------------------------------ calibration
def load_source(src: Path):
    hdr, rows = read_tsv(src / "ports.csv")
    ports = {r[0]: dict(zip(hdr, r)) for r in rows}
    dh, drows = read_tsv(src / "dist_dense.csv")
    first = {}
    for r in drows:                                    # first listed record = shortest (verified by the regional extraction)
        first.setdefault((r[0], r[1]), r)
    demand = {}
    for name in CALIBRATION:
        h, rs = read_tsv(src / f"Demand_{name}.csv")
        demand[name] = [(r[0], r[1], float(r[2]), float(r[3]), float(r[4])) for r in rs]
    return ports, first, demand


def anchors_from(ports, first):
    """Real ports with a complete, loader-valid record and mutual routed distances (the largest such set)."""
    ok = set()
    for pid, p in ports.items():
        try:
            vals = [float(p[c]) for c in ("Longitude", "Latitude", "Draft") + COST_COLS]
        except ValueError:
            continue
        if vals[2] > 0 and all(v >= 0 for v in vals[3:]) and abs(vals[1]) <= 90 and abs(vals[0]) <= 180:
            ok.add(pid)
    have = {k for k in first}
    keep = set(p for p in ok if any((p, q) in have for q in ok))
    while True:                                        # prune until every pair among the anchors has both directions
        deg = {a: sum(((a, b) in have and (b, a) in have) for b in keep if b != a) for a in keep}
        worst = min(deg, key=lambda a: (deg[a], a))
        if deg[worst] == len(keep) - 1:
            break
        keep.remove(worst)
    return sorted(keep)


def calibrate(ports, first, demand, anchors):
    """All statistics the generator uses, measured on the LINERLIB sources."""
    pdata = {p: (float(ports[p]["Latitude"]), float(ports[p]["Longitude"])) for p in ports
             if ports[p]["Latitude"] and ports[p]["Longitude"]}

    # within-country dispersion of each cost field (log scale, positive values only)
    by_country = {}
    for p in anchors:
        by_country.setdefault(ports[p]["Country"], []).append(p)
    disp = {}
    for c in COST_COLS:
        res = []
        for members in by_country.values():
            v = [math.log(float(ports[m][c])) for m in members if float(ports[m][c]) > 0]
            if len(v) >= 2:
                mu = sum(v) / len(v)
                res += [x - mu for x in v]
        disp[c] = float(np.std(res)) if len(res) > 5 else 0.3
    # circuity of local (short) real legs, over ALL real routed pairs with coordinates
    local, circ_all = [], []
    lat = np.array([pdata[p][0] for p in sorted(pdata)])
    lon = np.array([pdata[p][1] for p in sorted(pdata)])
    idx = {p: i for i, p in enumerate(sorted(pdata))}
    H = haversine_matrix(lat, lon)
    for (o, d), r in first.items():
        if o in idx and d in idx and H[idx[o], idx[d]] > 1.0:
            ratio = float(r[2]) / H[idx[o], idx[d]]
            circ_all.append(ratio)
            if H[idx[o], idx[d]] < LOCAL_LEG_NM:
                local.append(ratio)
    local_circuity = float(np.median(local))

    # demand statistics
    ffe = np.array([x[2] for n in CALIBRATION for x in demand[n]])
    ods = {}
    rev_hits, rev_tot = 0, 0
    mean_deg, mass_sd, imb = [], [], []
    for n in CALIBRATION:
        pairs = {(o, d): (f, r, t) for o, d, f, r, t in demand[n]}
        ods[n] = pairs
        rev_hits += sum((d, o) in pairs for (o, d) in pairs)
        rev_tot += len(pairs)
        origins = {}
        for (o, d) in pairs:
            origins[o] = origins.get(o, 0) + 1
        if n in FULL_SIZE:
            mean_deg.append(float(np.mean(list(origins.values()))))
        tot = {}
        for (o, d), (f, r, t) in pairs.items():
            tot[o] = tot.get(o, 0.0) + f
        if len(tot) >= 10:
            mass_sd.append(float(np.std(np.log(list(tot.values())))))
        for (o, d), (f, r, t) in pairs.items():
            if (d, o) in pairs and o < d:
                imb.append(math.log(f / pairs[(d, o)][0]))
    deg_log_sd = []
    for n in FULL_SIZE:
        c = {}
        for (o, d) in ods[n]:
            c[o] = c.get(o, 0) + 1
        deg_log_sd.append(float(np.std(np.log(list(c.values())))))
    # revenue ~ distance regression and transit / sailing-time ratio, on the pooled instances
    x, y, rho = [], [], []
    for n in CALIBRATION:
        for (o, d), (f, r, t) in ods[n].items():
            rec = first.get((o, d))
            if rec is not None and float(rec[2]) > 0:
                x.append(math.log(float(rec[2])))
                y.append(math.log(r))
                rho.append(t / (float(rec[2]) / (14.0 * 24.0)))
    x, y = np.array(x), np.array(y)
    b, a = np.polyfit(x, y, 1)
    resid = y - (a + b * x)
    return {
        "anchors": len(anchors),
        "cost_log_dispersion_within_country": disp,
        "local_circuity_median": local_circuity,
        "circuity_all_pairs_quantiles": {str(q): float(np.quantile(circ_all, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        "mean_out_degree_by_full_size_instance": dict(zip(FULL_SIZE, mean_deg)),
        "out_degree_geometric_mean": float(np.exp(np.mean(np.log(mean_deg)))),
        "out_degree_log_sd": float(np.mean(deg_log_sd)),
        "port_mass_log_sd": float(np.mean(mass_sd)),
        "reverse_od_probability": rev_hits / rev_tot,
        "directional_imbalance_log_sd": float(np.std(imb)),
        "ffe_pool_size": int(ffe.size), "ffe_mean": float(ffe.mean()), "ffe_median": float(np.median(ffe)),
        "ffe_support": [float(ffe.min()), float(ffe.max())],
        "revenue_support": [float(min(r for n in CALIBRATION for (_, _, _, r, _) in demand[n])),
                            float(max(r for n in CALIBRATION for (_, _, _, r, _) in demand[n]))],
        "revenue_regression": {"intercept": float(a), "slope": float(b), "residual_sd": float(resid.std()), "n": int(x.size)},
        "transit_ratio_rho_quantiles": {str(q): float(np.quantile(rho, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        "_arrays": {"ffe": ffe, "resid": resid, "rho": np.array(rho)},
    }


# ------------------------------------------------------------------------------------------------ population
def build_population(seed, ports, first, anchors, cal, n_total=POPULATION):
    rng = stream(seed, "ports")
    A = len(anchors)
    order = rng.permutation(A)
    aidx = np.array([order[k % A] for k in range(n_total)])            # stratified round-robin over permuted anchors
    anchor_ids = [anchors[i] for i in aidx]
    alat = np.array([float(ports[p]["Latitude"]) for p in anchor_ids])
    alon = np.array([float(ports[p]["Longitude"]) for p in anchor_ids])
    off_n = rng.normal(0, PORT_JITTER_NM, n_total) / 60.0                      # degrees of latitude
    off_e = rng.normal(0, PORT_JITTER_NM, n_total) / 60.0 / np.maximum(np.cos(np.radians(alat)), 0.2)
    lat = np.clip(alat + off_n, -85.0, 85.0)
    lon = ((alon + off_e + 180.0) % 360.0) - 180.0
    lat, lon = np.round(lat, 4), np.round(lon, 4)

    drafts_real = np.array(sorted({float(ports[p]["Draft"]) for p in anchors}))
    freq = np.array([sum(float(ports[p]["Draft"]) == d for p in anchors) for d in drafts_real], dtype=float)
    inherit = rng.random(n_total) < DRAFT_INHERIT_P
    drawn = rng.choice(drafts_real, size=n_total, p=freq / freq.sum())
    draft = np.where(inherit, [float(ports[p]["Draft"]) for p in anchor_ids], drawn)

    costs = {}
    disp = cal["cost_log_dispersion_within_country"]
    for c in COST_COLS:
        base = np.array([float(ports[p][c]) for p in anchor_ids])
        factor = np.exp(rng.normal(0, disp[c], n_total))
        costs[c] = np.round(base * factor, 2)                                   # a zero anchor value stays zero

    ids = [f"ZZ{k:03d}" for k in range(n_total)]
    return {"ids": ids, "anchor_idx": aidx, "anchor_ids": anchor_ids, "lat": lat, "lon": lon, "draft": draft,
            "costs": costs, "country": [ports[p]["Country"] for p in anchor_ids],
            "cabotage": [ports[p]["Cabotage_Region"] for p in anchor_ids], "dregion": [ports[p]["D_Region"] for p in anchor_ids],
            "anchor_name": [ports[p]["name"] for p in anchor_ids]}


def anchor_tables(ports, first, anchors):
    """Anchor-level circuity ratio, canal flags and draft limit (selected record of every anchor pair)."""
    A = len(anchors)
    lat = np.array([float(ports[p]["Latitude"]) for p in anchors])
    lon = np.array([float(ports[p]["Longitude"]) for p in anchors])
    H = haversine_matrix(lat, lon)
    ratio = np.full((A, A), np.nan)
    pan = np.zeros((A, A), dtype=np.int8)
    sue = np.zeros((A, A), dtype=np.int8)
    dlim = np.full((A, A), np.nan)
    for i, a in enumerate(anchors):
        for j, b in enumerate(anchors):
            if i == j:
                continue
            r = first[(a, b)]
            ratio[i, j] = float(r[2]) / H[i, j] if H[i, j] > 1.0 else np.nan
            pan[i, j], sue[i, j] = int(float(r[4] or 0)), int(float(r[5] or 0))
            dlim[i, j] = float(r[3]) if r[3].strip() else np.nan
    return H, ratio, pan, sue, dlim


def distances_for(pop, n, tables, cal):
    """Distance, canal flags and draft limit matrices of the first ``n`` synthetic ports."""
    H, ratio, pan, sue, dlim = tables
    ai = pop["anchor_idx"][:n]
    lat, lon = pop["lat"][:n], pop["lon"][:n]
    hav = haversine_matrix(lat, lon)
    R = ratio[ai[:, None], ai[None, :]].copy()
    near = H[ai[:, None], ai[None, :]] < LOCAL_LEG_NM
    same = ai[:, None] == ai[None, :]
    R[np.isnan(R) | near | same] = cal["local_circuity_median"]
    clipped = int(((R < CIRCUITY_CLIP[0]) | (R > CIRCUITY_CLIP[1])).sum())
    R = np.clip(R, *CIRCUITY_CLIP)
    dist = np.maximum(np.ceil(hav * R), 1.0)          # integer nm, never below the geodesic
    P = np.where(near | same, 0, pan[ai[:, None], ai[None, :]]).astype(np.int8)
    S = np.where(near | same, 0, sue[ai[:, None], ai[None, :]]).astype(np.int8)
    DL = np.where(near | same, np.nan, dlim[ai[:, None], ai[None, :]])
    np.fill_diagonal(dist, 0)
    return dist, P, S, DL, hav, clipped


# ------------------------------------------------------------------------------------------------ demand
def build_demand(seed, n, dist, cal):
    rng = stream(seed, "demand", n)
    arr = cal["_arrays"]
    mass = np.exp(rng.normal(0, cal["port_mass_log_sd"], n))
    kbar, ksd = cal["out_degree_geometric_mean"], cal["out_degree_log_sd"]
    k = np.clip(np.round(np.exp(rng.normal(np.log(kbar) - ksd ** 2 / 2, ksd, n))), 1, min(n - 1, int(0.5 * n))).astype(int)
    weight = np.log(mass)[None, :] - np.log1p(dist / GRAVITY_SCALE_NM)
    pairs = set()
    for i in range(n):
        score = weight[i] + rng.gumbel(size=n)
        score[i] = -np.inf
        top = np.argpartition(-score, k[i])[: k[i]]
        for j in sorted(top.tolist()):
            pairs.add((i, int(j)))
    p_rev = cal["reverse_od_probability"]
    fwd = sorted(pairs)
    flip = rng.random(len(fwd)) < p_rev
    for (i, j), f in zip(fwd, flip):
        if f:
            pairs.add((j, i))
    # every port takes part in at least one OD
    used = np.zeros(n, dtype=bool)
    for i, j in pairs:
        used[i] = used[j] = True
    for i in np.flatnonzero(~used).tolist():
        j = int(np.argmin(dist[i] + np.where(np.arange(n) == i, np.inf, 0)))
        pairs.add((i, j))
    ordered = sorted(pairs)
    m = len(ordered)

    ffe = np.maximum(np.round(stratified_draw(rng, arr["ffe"], m) * np.exp(rng.normal(0, 0.1, m))), 1).astype(int)
    index = {p: t for t, p in enumerate(ordered)}
    imb_sd = cal["directional_imbalance_log_sd"]
    for t, (i, j) in enumerate(ordered):                 # reverse volume = forward x lognormal imbalance
        if i < j and (j, i) in index:
            ffe[index[(j, i)]] = max(1, int(round(ffe[t] * math.exp(rng.normal(0, imb_sd)))))
    lo, hi = cal["ffe_support"]
    ffe = np.clip(ffe, int(lo), int(hi))                  # limited to the volumes observed in LINERLIB
    d_od = np.array([dist[i, j] for i, j in ordered])
    reg = cal["revenue_regression"]
    rev = np.exp(reg["intercept"] + reg["slope"] * np.log(d_od) + stratified_draw(rng, arr["resid"], m))
    rlo, rhi = cal["revenue_support"]
    rev = np.clip(np.round(rev / 10.0) * 10.0, rlo, rhi).astype(int)          # limited to the observed rate range
    tt = np.clip(np.round(stratified_draw(rng, arr["rho"], m) * d_od / (14.0 * 24.0)), *TT_RANGE).astype(int)
    return ordered, ffe, rev, tt, mass, k


# ------------------------------------------------------------------------------------------------ fleet
def fleet_rule(src: Path, total_ffe: float):
    """(per-class quantities, rule description) from WorldSmall's demand-per-vessel ratio and class mix."""
    _, drows = read_tsv(src / f"Demand_{FLEET_REFERENCE[0]}.csv")
    ws_ffe = sum(float(r[2]) for r in drows)
    _, frows = read_tsv(src / FLEET_REFERENCE[1])
    qty = {r[0]: int(r[1]) for r in frows}
    ws_total = sum(qty.values())
    ffe_per_vessel = ws_ffe / ws_total
    total = max(len(qty), int(round(total_ffe / ffe_per_vessel)))
    shares = {c: q / ws_total for c, q in qty.items()}
    raw = {c: max(1, int(round(shares[c] * total))) for c in qty}
    rule = {"rule": "vessels_total = round(weekly_FFE / FFE_per_vessel_WorldSmall); class mix = WorldSmall mix; min 1 per class",
            "reference": {"demand_file": f"Demand_{FLEET_REFERENCE[0]}.csv", "fleet_file": FLEET_REFERENCE[1],
                          "weekly_ffe": ws_ffe, "vessels": ws_total, "ffe_per_vessel": ffe_per_vessel,
                          "class_shares": shares},
            "target_vessels_total": total, "vessels_by_class": raw, "vessels_total": sum(raw.values()),
            "calibrated_against": "weekly demand volume (not port count); identical for World-500 and World-1000"}
    return raw, rule


# ------------------------------------------------------------------------------------------------ files
def files_for(seed, n, pop, tables, cal, src: Path):
    dist, P, S, DL, hav, clipped = distances_for(pop, n, tables, cal)
    ordered, ffe, rev, tt, mass, outdeg = build_demand(seed, n, dist, cal)
    ids = pop["ids"][:n]

    ports_lines = [PORT_HEADER]
    for k in range(n):
        c = pop["costs"]
        ports_lines.append("\t".join([
            ids[k], f"Synthetic port {ids[k]} (anchor: {pop['anchor_name'][k]})", pop["country"][k], pop["cabotage"][k],
            pop["dregion"][k], f"{pop['lon'][k]:.4f}", f"{pop['lat'][k]:.4f}", fmt_g(pop["draft"][k]),
            f"{c['CostPerFULL'][k]:.2f}", f"{c['CostPerFULLTrnsf'][k]:.2f}", f"{c['PortCallCostFixed'][k]:.2f}",
            f"{c['PortCallCostPerFFE'][k]:.2f}"]))
    name = f"World-{n}"
    demand_lines = ["Origin\tDestination\tFFEPerWeek\tRevenue_1\tTransitTime"]
    for (i, j), f, r, t in zip(ordered, ffe, rev, tt):
        demand_lines.append(f"{ids[i]}\t{ids[j]}\t{int(f)}\t{int(r)}\t{int(t)}")
    dist_lines = ["fromUNLOCODe\tToUNLOCODE\tDistance\tDraft\tIsPanama\tIsSuez"]
    for i in range(n):
        for j in range(n):
            if i != j:
                dl = "" if np.isnan(DL[i, j]) else fmt_g(DL[i, j])
                dist_lines.append(f"{ids[i]}\t{ids[j]}\t{int(dist[i, j])}\t{dl}\t{int(P[i, j])}\t{int(S[i, j])}")
    total_ffe = float(ffe.sum())
    qty, rule = fleet_rule(src, total_ffe)
    fleet_lines = ["Vessel class\tQuantity"] + [f"{c}\t{q}" for c, q in qty.items()]

    def b(lines):
        return ("\n".join(lines) + "\n").encode("utf-8")

    files = {"ports.csv": b(ports_lines), f"Demand_{name}.csv": b(demand_lines), "dist_dense.csv": b(dist_lines),
             f"fleet_{name}.csv": b(fleet_lines), "fleet_data.csv": (src / "fleet_data.csv").read_bytes()}

    # diagnostics reported in the manifest (never used to adjust anything)
    rng = stream(seed, "diag", n)
    sample = rng.choice(n, size=min(n, 60), replace=False)
    viol = tot = 0
    for a in sample:
        for b_ in sample:
            for c_ in sample:
                if len({a, b_, c_}) == 3:
                    tot += 1
                    viol += dist[a, c_] > dist[a, b_] + dist[b_, c_] + 1e-9
    d_od = np.array([dist[i, j] for i, j in ordered])
    diag = {
        "ports": n, "od_records": len(ordered), "od_density": len(ordered) / (n * (n - 1)),
        "mean_out_degree": len(ordered) / n, "directed_distance_pairs": n * (n - 1),
        "weekly_ffe": total_ffe, "ffe_mean_per_od": float(ffe.mean()), "ffe_median_per_od": float(np.median(ffe)),
        "revenue_mean": float(rev.mean()), "transit_median_days": float(np.median(tt)),
        "reverse_od_share": float(np.mean([(j, i) in set(ordered) for i, j in ordered])) if n <= 300 else None,
        "distance_nm_quantiles": {str(q): float(np.quantile(d_od, q)) for q in (0.05, 0.5, 0.95)},
        "circuity_clipped_pairs": clipped, "canal_flagged_pairs": int(((P > 0) | (S > 0)).sum()),
        "pairs_with_draft_limit": int((~np.isnan(DL)).sum() - np.isnan(np.diag(DL)).sum() * 0),
        "triangle_violation_rate_sampled": viol / max(1, tot),
        "ods_direct_sailing_feasible_at_14kn": float(np.mean(tt >= d_od / (14.0 * 24.0))),
        "min_geodesic_ratio": float(np.min(dist[~np.eye(n, dtype=bool)] / np.maximum(hav[~np.eye(n, dtype=bool)], 1e-9))),
    }
    return name, files, rule, diag


def source_hashes(src: Path):
    names = ["ports.csv", "dist_dense.csv", "fleet_data.csv", "fleet_WorldSmall.csv"] + \
            [f"Demand_{n}.csv" for n in CALIBRATION]
    return {n: sha256_bytes((src / n).read_bytes()) for n in names}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--sizes", type=int, nargs="+", default=list(SIZES), choices=list(SIZES))
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare with the files on disk")
    ap.add_argument("--replace", action="store_true", help="overwrite differing files after copying them to <out-root>/_backups/")
    a = ap.parse_args(argv)

    ports, first, demand = load_source(a.source)
    assert not any(p.startswith("ZZ") for p in ports), "a real UN/LOCODE starts with ZZ: identifiers could collide"
    anchors = anchors_from(ports, first)
    cal = calibrate(ports, first, demand, anchors)
    tables = anchor_tables(ports, first, anchors)
    pop = build_population(a.seed, ports, first, anchors, cal)
    assert len(set(pop["ids"])) == POPULATION and not (set(pop["ids"]) & set(ports))
    cal_public = {k: v for k, v in cal.items() if k != "_arrays"}

    rc = 0
    for n in a.sizes:
        name, files, rule, diag = files_for(a.seed, n, pop, tables, cal, a.source)
        out = a.out_root / name
        manifest = {
            "dataset": name, "kind": "synthetic", "generator": "scripts/multi_dataset/generate_synthetic.py",
            "generator_version": GENERATOR_VERSION, "seed": a.seed, "numpy_version": np.__version__,
            "population": {"total_ports_generated": POPULATION, "this_dataset_ports": n,
                           "shared_population_note": "World-500 = first 500 ports of the 1000-port population "
                                                     "(same ports, same attributes); demand and fleet are generated per dataset",
                           "id_scheme": "ZZ000..ZZ999 (ZZ is not an assigned country code; collision with LINERLIB ids asserted impossible)"},
            "parameters": {"port_jitter_nm": PORT_JITTER_NM, "draft_inherit_probability": DRAFT_INHERIT_P,
                           "gravity_scale_nm": GRAVITY_SCALE_NM, "circuity_clip": list(CIRCUITY_CLIP),
                           "local_leg_nm": LOCAL_LEG_NM, "transit_days_range": list(TT_RANGE),
                           "calibration_instances": list(CALIBRATION), "out_degree_instances": list(FULL_SIZE),
                           "worldlarge_used": False},
            "calibration": cal_public, "fleet_scaling": rule, "diagnostics": diag, "limitations": LIMITATIONS,
            "source_dir": str(a.source), "source_sha256": source_hashes(a.source),
            "files": {fn: {"sha256": sha256_bytes(b), "bytes": len(b)} for fn, b in files.items()},
        }
        mbytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        files["generation_manifest.json"] = mbytes
        if a.check:
            same = all((out / fn).is_file() and (out / fn).read_bytes() == b for fn, b in files.items())
            print(f"[{name}] --check: {'regeneration is byte-identical' if same else 'DIFFERS from disk'}")
            rc |= 0 if same else 1
            continue
        out.mkdir(parents=True, exist_ok=True)
        refused = False
        for fn, b in files.items():
            p = out / fn
            if p.exists() and p.read_bytes() != b:
                if not a.replace:
                    print(f"[{name}] {fn} exists with different content; refusing to overwrite (use --replace: backs it up first)")
                    refused = True
                    break
                bdir = a.out_root / "_backups" / name
                bdir.mkdir(parents=True, exist_ok=True)
                (bdir / f"{p.name}.{sha256_bytes(p.read_bytes())[:12]}").write_bytes(p.read_bytes())
                p.write_bytes(b)
            elif not p.exists():
                p.write_bytes(b)
        if refused:
            rc = 1
        else:
            print(f"[{name}] written to {out}: ports={diag['ports']} ODs={diag['od_records']} "
                  f"FFE/wk={diag['weekly_ffe']:,.0f} vessels={rule['vessels_total']} {rule['vessels_by_class']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
