"""Batch 6 market inputs of the What-if: #19 war risk (backend/war_risk.py), #20 freight index and #21 bunker prices
by port (backend/market.py), and their wiring into backend/whatif.py."""

import datetime as dt

import numpy as np
import pytest

from backend import market, war_risk, whatif

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}

PAGE = """<table><tr><th>Port / Average</th><th>VLSFO</th><th>IFO380 (HSFO)</th><th>MGO</th><th></th></tr>
<tr data-href="/prices/port/AV-G20"><td>Global 20 Ports Average</td><td>$944.00 +7.50</td><td>$820.50</td><td>$1,550.50</td><td>Oct 28</td></tr>
<tr data-href="/prices/apac/sea/sg-sin-singapore"><td>Singapore</td><td>$1,000.50 +10.50</td><td>x</td><td>x</td><td>Oct 28</td></tr>
<tr data-href="/prices/emea/nwe/nl-rtm-rotterdam"><td>Rotterdam</td><td>$770.00 +6.00</td><td>x</td><td>x</td><td>Oct 28</td></tr>
<tr data-href="/prices/apac/ea/cn-hok-hong-kong"><td>Hong Kong</td><td>$1,005.00</td><td>x</td><td>x</td><td>Oct 28</td></tr>
<tr data-href="/prices/emea/nwe/de-ham-hamburg"><td>Hamburg</td><td>Subscribe &rarr; or Sign in &rarr;</td></tr>
<tr data-href="/prices/am/namatl/us-nyc-new-york"><td>New York</td><td>$862.00</td><td>x</td><td>x</td><td>Dec 30</td></tr>
</table>"""


def test_parse_public_prices_skips_paywalled_rows_and_dates_the_year():
    p = market.parse_prices({"u": PAGE}, dt.date(2027, 1, 2))
    assert set(p["ports"]) == {"SGSIN", "NLRTM", "CNHOK", "USNYC"}          # Hamburg is behind the subscription
    assert p["ports"]["NLRTM"]["vlsfo"] == 770.0 and p["ports"]["SGSIN"]["vlsfo"] == 1000.5
    assert p["averages"]["AV-G20"]["vlsfo"] == 944.0
    assert p["ports"]["USNYC"]["date"] == "2026-12-30"                        # "Dec 30" read on 2 Jan
    assert p["ports"]["SGSIN"]["date"] == "2026-10-28"


def test_market_snapshot_goes_through_the_engine_rule_with_aliases():
    p = market.parse_prices({"u": PAGE}, dt.date(2026, 10, 29))
    pricing, snap = market.market_pricing(p)
    hubs = {o["hub"] for o in snap["observations"]}
    assert "HKHKG" in hubs                                                    # dataset code of CN HOK
    assert snap["dropped_stale"] == [{"hub": "USNYC", "observed_on": "2025-12-30"}]  # 302 d old: left out
    assert "USEWR" not in hubs                                                # so is its alias
    r = pricing.resolve(["CNSHA", "SGSIN", "NLRTM"])
    assert (r.bunkering_port, r.price_usd_per_t, r.basis) == ("NLRTM", 770.0, "observed_port")
    r = pricing.resolve(["AOLAD", "AEJEA"])
    assert (r.bunkering_port, r.price_usd_per_t, r.basis) == (None, 944.0, "global_reference")


class _D:
    def __init__(self, o, d, rev, teu=10.0):
        self.origin, self.destination, self.revenue_per_teu, self.weekly_teu = o, d, rev, teu


class _P:
    demands = [_D("CNSHA", "NLRTM", 1480.0), _D("CNSHA", "USLAX", 805.0), _D("DEHAM", "CNSHA", 400.0),
               _D("USHOU", "BRSSZ", 900.0)]


def _at(lon, lat):
    return type("R", (), {"longitude": lon, "latitude": lat})


def test_trade_regions_and_lane_ratios():
    assert market.trade_region("CNSHA", 121.5, 31.2) == "far_east"
    assert market.trade_region("USLAX", -118.3, 33.7) == "us_west_coast"
    assert market.trade_region("USEWR", -74.1, 40.7) == "us_east_coast"
    assert market.trade_region("USHOU", -95.0, 29.7) is None                  # Gulf coast: no WCI lane
    assert market.trade_region("ESALG", -5.4, 36.1) == "mediterranean"
    assert market.trade_region("FRLEH", 0.1, 49.5) == "north_europe"
    lanes = market.lane_ratios(_P())
    ane = next(l for l in lanes if l["id"] == "asia_north_europe")
    assert ane["ratio"] == pytest.approx(3632 / 2 / 1480)
    assert next(l for l in lanes if l["id"] == "asia_usec")["ratio"] is None   # no CNSHA-USEWR in this problem
    assert next(l for l in lanes if l["id"] == "north_europe_asia")["ratio"] is None
    lookup = {"CNSHA": _at(121.5, 31.2), "NLRTM": _at(4.2, 51.9), "USLAX": _at(-118.3, 33.7), "DEHAM": _at(9.9, 53.5),
              "USHOU": _at(-95.0, 29.7), "BRSSZ": _at(-46.3, -23.9)}
    m, used = market.revenue_multipliers(_P(), lookup, "wci_lanes", 1.1, lanes)
    assert m[0] == pytest.approx(ane["ratio"])
    assert m[1] == pytest.approx(8007 / 2 / 805)
    assert m[2] == 1.1 and m[3] == 1.1                                        # lane without benchmark / no lane
    assert used == {"asia_north_europe": {"ods": 1, "teu": 10.0}, "asia_uswc": {"ods": 1, "teu": 10.0}}
    assert market.revenue_multipliers(_P(), lookup, "uniform", 1.3, lanes)[0] == [1.3] * 4


@pytest.mark.parametrize("name,lon,lat,zone", [
    ("Strait of Hormuz", 56.3, 26.5, "gulf_hormuz"), ("Jebel Ali", 55.0, 25.0, "gulf_hormuz"),
    ("Jeddah", 39.1, 21.5, "red_sea_central"), ("Bab al-Mandab", 43.4, 12.6, "bab_al_mandab"),
    ("Salalah", 54.0, 16.9, "bab_al_mandab"), ("Suez", 32.5, 30.0, None), ("Port Said", 32.3, 31.3, None),
    ("Karachi, east of 65E", 67.0, 24.8, None), ("Lagos", 3.4, 6.4, "gulf_of_guinea"), ("Takoradi", -1.75, 4.9, None),
    ("Odesa", 30.75, 46.45, "black_sea"), ("Constanta, Romanian waters", 28.65, 44.17, None),
    ("Bosporus", 29.0, 41.05, None), ("Pemba, Cabo Delgado", 40.6, -12.9, "cabo_delgado"),
])
def test_points_fall_in_the_jwla_035_zones(name, lon, lat, zone):
    hit = None
    for area in war_risk.AREAS:
        z = war_risk.zone_of(np.array([lon]), np.array([lat]), area)[0]
        if z >= 0:
            hit = war_risk.ZONES[z]["id"]
    assert hit == zone, name


def test_densify_folds_unwrapped_longitudes():
    lon, lat = war_risk.densify([[179.0, 0.0], [181.0, 0.0]])
    assert lon.min() >= -180 and lon.max() <= 180 and len(lon) == 21


def test_visits_are_cyclic_runs_plus_named_country_calls():
    legs = {("A", "B"): {"indian_ocean": [0]}, ("B", "C"): {}, ("C", "D"): {"indian_ocean": [2]},
            ("D", "A"): {"indian_ocean": [1]}, ("ILHFA", "A"): {}, ("A", "ILHFA"): {}}
    v = war_risk.visits(["A", "B", "C", "D"], legs, {})
    io = [x for x in v if x["area"] == "indian_ocean"]
    assert len(io) == 1 and io[0]["legs"] == [["C", "D"], ["D", "A"], ["A", "B"]]   # one run across the wrap
    assert io[0]["zones"] == ["gulf_hormuz", "red_sea_central", "bab_al_mandab"]
    v = war_risk.visits(["ILHFA", "A"], legs, {"ILHFA": None})
    assert v == [{"area": "named_country", "port": "ILHFA", "country": "Israel", "zones": ["named_call"]}]


def test_rates_overrides_are_bounded():
    r = war_risk.rates_with({"gulf_hormuz": 9.0, "black_sea": 99, "unknown": 1})
    assert r["gulf_hormuz"] == 9.0 and r["black_sea"] == 1.0 and "unknown" not in r


@pytest.fixture(scope="module")
def seed7():
    try:
        return whatif.whatif(whatif.WhatIfRequest(run=RUN))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"seed-7 benchmark run not available: {exc}")


def test_whatif_war_risk_adds_exactly_its_premiums(seed7):
    r = whatif.whatif(whatif.WhatIfRequest(run=RUN, war_risk=True))
    base, scen, w = r["baseline"], r["scenario"], r["market"]["war_risk"]
    assert scen["war_risk_cost"] == pytest.approx(w["weekly_total"]) and w["weekly_total"] > 0
    assert scen["total_cost"] - base["total_cost"] == pytest.approx(w["weekly_total"])
    assert scen["revenue"] == pytest.approx(base["revenue"])
    s = max(w["services"], key=lambda s: s["weekly"])
    v = s["visits"][0]
    assert v["premium_per_visit"] == pytest.approx(v["rate_pct"] / 100 * s["hull_value_usd"], rel=1e-6)
    assert w["definitions"]["circular"]["id"] == "JWLA-035"


def test_whatif_identities_uniform_rate_one_and_market_at_dataset_price(seed7, monkeypatch):
    same = whatif.whatif(whatif.WhatIfRequest(run=RUN, rate_mode="uniform", rate_multiplier=1.0))
    assert same["scenario"]["profit"] == pytest.approx(seed7["baseline"]["profit"])
    flat = {"ports": {"NLRTM": {"name": "Rotterdam", "vlsfo": 600.0, "date": "2026-10-28", "url": "u"},
                      "SGSIN": {"name": "Singapore", "vlsfo": 600.0, "date": "2026-10-28", "url": "u"}},
            "averages": {"AV-G20": {"name": "G20", "vlsfo": 600.0, "date": "2026-10-28", "url": "u"}},
            "status": "hit", "fetched_on": "2026-10-28"}
    monkeypatch.setattr(market, "bunker_prices", lambda: flat)
    r = whatif.whatif(whatif.WhatIfRequest(run=RUN, bunker_mode="market"))
    assert r["scenario"]["fuel_cost"] == pytest.approx(r["baseline"]["fuel_cost"], rel=1e-9)  # 600 everywhere
    assert r["market"]["bunker"]["reference"]["price"] == 600.0


def test_whatif_freight_lanes_raise_revenue_on_matched_trades(seed7):
    r = whatif.whatif(whatif.WhatIfRequest(run=RUN, rate_mode="wci_lanes"))
    f = r["market"]["freight"]
    assert f["composite"]["usd_per_feu"] == 4585 and len(f["lanes"]) == 8
    assert all(l["ratio"] for l in f["lanes"])                  # WorldSmall holds every benchmark pair
    assert sum(u["ods"] for u in f["lanes_applied"].values()) > 0
    assert r["scenario"]["revenue"] > r["baseline"]["revenue"]  # Asia lanes trade far above the dataset's rates
