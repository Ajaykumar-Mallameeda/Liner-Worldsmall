"""Live AIS layer (backend/ais.py): category mapping and the position/metadata join, offline."""

from backend import ais


def test_ship_category_follows_itu_types():
    assert ais.ship_category(70) == "cargo" and ais.ship_category(79) == "cargo"
    assert ais.ship_category(80) == "tanker" and ais.ship_category(89) == "tanker"
    assert ais.ship_category(60) == "passenger"
    assert ais.ship_category(30) == "fishing"
    assert ais.ship_category(52) == "tug / towing"
    assert ais.ship_category(55) == "service"
    assert ais.ship_category(None) == "other" and ais.ship_category(99) == "other"


def test_build_joins_metadata_drops_stale_and_scales_draught():
    now = 1_800_000_000_000
    def feat(mmsi, ts, heading=511, cog=45.0):
        return {"geometry": {"coordinates": [20.0, 60.0]},
                "properties": {"mmsi": mmsi, "timestampExternal": ts, "sog": 12.3, "cog": cog, "heading": heading}}
    locs = {"features": [feat(1, now - 5 * 60_000, heading=90), feat(2, now - 90 * 60_000), feat(3, now - 60_000)]}
    vessels = [{"mmsi": 1, "name": " BOX ONE ", "shipType": 71, "draught": 124, "destination": "FIHEL"},
               {"mmsi": 2, "name": "OLD", "shipType": 80, "draught": 50}]
    b = ais.build(locs, vessels, now)
    by = {v["mmsi"]: v for v in b["vessels"]}
    assert set(by) == {1, 3}                                      # 90 min old position dropped
    one = by[1]
    assert one["name"] == "BOX ONE" and one["category"] == "cargo" and one["draught_m"] == 12.4
    assert one["heading"] == 90 and one["age_min"] == 5.0 and one["destination"] == "FIHEL"
    three = by[3]
    assert three["category"] == "other" and three["name"] is None and three["draught_m"] is None
    assert three["heading"] == 45.0                               # 511 = heading not available -> course
    assert b["counts"] == {"cargo": 1, "other": 1}
