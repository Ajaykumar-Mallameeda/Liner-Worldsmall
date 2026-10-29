"""
Market inputs for the What-if (2026-10-29): #20 freight index, #21 bunker prices by port.

#20 Freight rate level. The dataset's revenue per TEU (LINERLIB) is the 1x level. The Drewry World Container Index
  (backend/data/freight_index.json: composite and its eight lanes, dated, with sources) anchors the slider: for each
  WCI lane the dataset holds the same port pair (or a named stand-in), so "today's spot / dataset" is a measured
  ratio, never an assumed base year. Mode "wci_lanes" multiplies the revenue of every OD in a lane's trade (origin
  region -> destination region, LOCODE country and longitude rules below) by that lane's ratio; every other OD takes
  the uniform slider. Per TEU = per FEU / 2. Spot rates are not what the dataset's revenues are (those are average
  realised rates), so the lane ratio says how today's spot market compares, not what a carrier earns.

#21 Bunker price by port. Ship & Bunker's public price pages (shipandbunker.com/prices and its three regional pages)
  show VLSFO prices for a set of ports plus regional and global averages; most other ports are behind a
  subscription and are not read. The public prices become a snapshot in the engine's own format
  (src/network/bunker_prices.py, schema 1: observations by UN/LOCODE, the "Global 20 Ports Average" as the GLOBAL
  reference) and the engine's rule prices each service: all its fuel at the cheapest observed port on its rotation,
  else the global reference. Cached 12 h on disk; served stale (labelled) when the site is down.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend import port_activity

FREIGHT_FILE = Path(__file__).resolve().parent / "data" / "freight_index.json"
SNB_PAGES = ["https://shipandbunker.com/prices", "https://shipandbunker.com/prices/apac",
             "https://shipandbunker.com/prices/emea", "https://shipandbunker.com/prices/am"]
TTL_BUNKER = 12 * 3600
MAX_AGE_DAYS = 14

FAR_EAST = {"CN", "HK", "TW", "KR", "JP", "SG", "MY", "VN", "TH", "ID", "PH", "KH", "MM", "BN"}
NORTH_EUROPE = {"NL", "BE", "DE", "GB", "DK", "SE", "NO", "FI", "PL", "IE", "EE", "LV", "LT"}
MEDITERRANEAN = {"IT", "GR", "TR", "MT", "HR", "SI", "CY", "EG", "MA", "DZ", "TN", "LB", "IL", "SY", "AL", "ME"}


# ── #20 freight ──

def freight_snapshot() -> Dict:
    return json.loads(FREIGHT_FILE.read_text(encoding="utf-8"))


def trade_region(code: str, lon: Optional[float], lat: Optional[float]) -> Optional[str]:
    """WCI trade region of a port: country first, coasts by longitude / latitude where a country spans two."""
    c = code[:2]
    if c in FAR_EAST:
        return "far_east"
    if c in NORTH_EUROPE:
        return "north_europe"
    if c in MEDITERRANEAN:
        return "mediterranean"
    if c == "FR" and lat is not None:
        return "north_europe" if lat >= 46 else "mediterranean"
    if c == "ES" and lat is not None:
        return "north_europe" if lat >= 42.5 else "mediterranean"
    if c == "US" and lon is not None:
        if lon < -100:
            return "us_west_coast"
        if lon > -85:
            return "us_east_coast"      # Gulf of Mexico ports (-97..-85) belong to neither WCI lane
    return None


def lane_ratios(problem, snap: Optional[Dict] = None, lane_usd_per_feu: Optional[Dict[str, float]] = None) -> List[Dict]:
    """Each WCI lane: spot per TEU, the dataset's revenue per TEU on its benchmark pair, and the ratio."""
    snap = snap or freight_snapshot()
    rev = {(d.origin, d.destination): d.revenue_per_teu for d in problem.demands}
    out = []
    for ln in snap["lanes"]:
        feu = float((lane_usd_per_feu or {}).get(ln["id"], ln["usd_per_feu"]))
        bench = tuple(ln["benchmark_od"]) if ln.get("benchmark_od") else None
        base = rev.get(bench) if bench else None
        out.append({"id": ln["id"], "label": ln["label"], "usd_per_feu": feu, "usd_per_teu": feu / 2,
                    "change_wow_pct": ln.get("change_wow_pct"), "trade": ln["trade"],
                    "benchmark_od": list(bench) if bench else None, "benchmark_note": ln.get("benchmark_note"),
                    "dataset_usd_per_teu": base,
                    "ratio": (feu / 2) / base if base else None})
    return out


def revenue_multipliers(problem, lookup, mode: str, uniform: float, lanes: List[Dict]) -> Tuple[List[float], Dict]:
    """Per-demand revenue multiplier and a summary {lane id: {ods, teu}} of which ODs each lane moved."""
    m = [uniform] * len(problem.demands)
    used: Dict[str, Dict] = {}
    if mode != "wci_lanes":
        return m, used
    by_trade = {tuple(ln["trade"]): ln for ln in lanes if ln["ratio"] is not None}

    def region(p):
        r = lookup.get(p)
        return trade_region(p, getattr(r, "longitude", None), getattr(r, "latitude", None))

    regions = {}
    for i, d in enumerate(problem.demands):
        for p in (d.origin, d.destination):
            if p not in regions:
                regions[p] = region(p)
        ln = by_trade.get((regions[d.origin], regions[d.destination]))
        if ln:
            m[i] = ln["ratio"]
            u = used.setdefault(ln["id"], {"ods": 0, "teu": 0.0})
            u["ods"] += 1
            u["teu"] += d.weekly_teu
    return m, used


# ── #21 bunker ──

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (liner-shipping-optimizer)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="ignore")


def _cells(row: str) -> List[str]:
    return [html.unescape(re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>.*?</t[dh]>", row, flags=re.S)]


def _price(cell: str) -> Optional[float]:
    m = re.match(r"\$?([\d,]+\.\d+|[\d,]+)", cell.strip())
    return float(m.group(1).replace(",", "")) if m else None


def _date(cell: str, today: dt.date) -> Optional[str]:
    try:
        d = dt.datetime.strptime(f"{cell.strip()} {today.year}", "%b %d %Y").date()
    except ValueError:
        return None
    if d > today + dt.timedelta(days=1):    # "Dec 30" read in January belongs to last year
        d = d.replace(year=today.year - 1)
    return d.isoformat()


def parse_prices(pages: Dict[str, str], today: dt.date) -> Dict:
    """Public VLSFO prices by UN/LOCODE and the averages, from the main and regional price pages."""
    ports, averages = {}, {}
    for url, text in pages.items():
        for table in re.findall(r"<table.*?</table>", text, flags=re.S):
            heads = [h.upper() for h in _cells((re.findall(r"<tr.*?</tr>", table, flags=re.S) or [""])[0])]
            if "VLSFO" not in heads:
                continue
            iv = heads.index("VLSFO")
            for row in re.findall(r"<tr.*?</tr>", table, flags=re.S)[1:]:
                href = re.search(r'data-href="([^"]+)"', row)
                cells = _cells(row)
                if not href or len(cells) <= iv or "Subscribe" in " ".join(cells):
                    continue
                price, day = _price(cells[iv]), _date(cells[-1], today)
                if price is None or day is None:
                    continue
                link = "https://shipandbunker.com" + href.group(1)
                m = re.search(r"/prices/[a-z]+/[a-z]+/([a-z]{2})-([a-z]{3})-", href.group(1))
                a = re.search(r"/prices/port/(AV-[A-Z0-9]+)", href.group(1))
                if m:
                    ports[(m.group(1) + m.group(2)).upper()] = {"name": cells[0], "vlsfo": price, "date": day, "url": link}
                elif a:
                    averages[a.group(1)] = {"name": cells[0], "vlsfo": price, "date": day, "url": link}
    return {"ports": ports, "averages": averages}


def _fetch_prices() -> Dict:
    today = dt.date.today()
    pages = {u: _get(u) for u in SNB_PAGES}
    out = parse_prices(pages, today)
    if not out["ports"]:
        raise ValueError("no public VLSFO prices found on the Ship & Bunker pages (layout changed?)")
    return out


def bunker_prices() -> Dict:
    val, status = port_activity._cached("shipandbunker_prices.json", TTL_BUNKER, _fetch_prices)
    return {"status": status, "fetched_on": val.get("fetched_on"), "error": val.get("error"),
            **(val.get("data") or {"ports": {}, "averages": {}})}


# Ship & Bunker's own codes for ports the LINERLIB datasets name differently (same bunkering market)
ALIASES = {"CNHOK": [("HKHKG", "Hong Kong (Ship & Bunker code CN HOK)")],
           "USNYC": [("USEWR", "New York / New Jersey harbour, priced for Newark"), ("USNWK", "New York / New Jersey harbour")],
           "USLAX": [("USLGB", "Los Angeles / Long Beach")]}


def snapshot_dict(prices: Dict) -> Dict:
    """The public prices as a src/network/bunker_prices snapshot (schema 1)."""
    ref = prices["averages"].get("AV-G20")
    if not prices.get("ports") or not ref:
        raise ValueError("bunker prices unavailable")
    newest = max([p["date"] for p in prices["ports"].values()] + [ref["date"]])
    keep, dropped = {}, []
    for code, p in sorted(prices["ports"].items()):
        # the engine refuses a snapshot holding a price more than max_age_days older than its as_of
        if (dt.date.fromisoformat(newest) - dt.date.fromisoformat(p["date"])).days > MAX_AGE_DAYS:
            dropped.append({"hub": code, "observed_on": p["date"]})
        else:
            keep[code] = p
    obs = [{"hub": code, "price": p["vlsfo"], "observed_on": p["date"], "provenance": "observed",
            "source": "Ship & Bunker public price table", "source_url": p["url"], "bunkering_location": p["name"]}
           for code, p in keep.items()]
    have = {o["hub"] for o in obs}
    for code, p in keep.items():
        for alias, where in ALIASES.get(code, []):
            if alias not in have:
                obs.append({"hub": alias, "price": p["vlsfo"], "observed_on": p["date"], "provenance": "observed",
                            "source": "Ship & Bunker public price table", "source_url": p["url"],
                            "bunkering_location": where, "note": f"price listed under {code}"})
                have.add(alias)
    as_of = max([o["observed_on"] for o in obs] + [ref["date"]])
    return {"schema_version": 1, "snapshot_id": f"shipandbunker_vlsfo_{as_of}", "fuel_grade": "VLSFO",
            "currency": "USD", "unit": "USD_per_metric_tonne", "as_of": as_of, "max_age_days": MAX_AGE_DAYS,
            "dropped_stale": dropped,
            "description": "Ship & Bunker public VLSFO prices (ports shown without a subscription)",
            "licence_note": "prices (c) Ship & Bunker; read from its public pages for analysis, attributed",
            "observations": obs,
            "reference": {"hub": "GLOBAL", "price": ref["vlsfo"], "observed_on": ref["date"], "provenance": "observed",
                          "source": "Ship & Bunker Global 20 Ports Average (G20)", "source_url": ref["url"]}}


def market_pricing(prices: Optional[Dict] = None):
    """(FuelPricing, snapshot dict) for the current public prices, via the engine's own loader and rule."""
    from src.network.bunker_prices import FuelPricing, load_snapshot

    prices = prices or bunker_prices()
    snap = snapshot_dict(prices)
    return FuelPricing.from_snapshot(load_snapshot(snap), valuation_date=dt.date.today().isoformat(),
                                     allow_stale=True), snap


# ── routes ──

from fastapi import APIRouter  # noqa: E402

router = APIRouter()


@router.get("/api/market/freight")
def get_freight(dataset: str = "WorldSmall"):
    """The WCI snapshot with each lane's ratio to the dataset's revenue on its benchmark pair."""
    from src.data.problem_json import load_problem_json

    snap = freight_snapshot()
    try:
        problem, _ = load_problem_json(dataset)
        lanes = lane_ratios(problem, snap)
    except Exception:  # noqa: BLE001 - a dataset without the pairs still shows the index
        lanes = lane_ratios(type("P", (), {"demands": []})(), snap)
    return {**{k: snap[k] for k in ("index", "unit", "as_of", "composite", "lane_source", "lane_urls", "per_teu_rule")},
            "dataset": dataset, "lanes": lanes}


@router.get("/api/market/bunker")
def get_bunker():
    p = bunker_prices()
    return {**p, "source": "Ship & Bunker public price pages", "pages": SNB_PAGES,
            "note": "only ports shown without a subscription; others use the Global 20 Ports Average"}
