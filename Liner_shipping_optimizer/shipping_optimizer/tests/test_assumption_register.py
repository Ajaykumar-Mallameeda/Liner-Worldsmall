"""Issue 6 - every result carries the register of provisional / sourced assumptions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader
from src.network.assumption_register import build
from src.network.economics import DEFAULT_ASSUMPTIONS, EconomicsAssumptions

VOCAB = {"SOURCED_PRIMARY_CODE", "SOURCED_SECONDARY", "PROVISIONAL", "UNVERIFIED", "NOT_MODELLED"}


def test_register_is_complete_and_uses_the_values_in_force():
    reg = build(DEFAULT_ASSUMPTIONS, NetworkLoader().load_fleet())
    ids = {r["id"] for r in reg}
    assert {"capacity_unit", "ffe_to_teu", "transit_file", "transfer_dwell", "bunker_price", "canal_fees",
            "weekly_frequency", "cost_units", "port_stay"} <= ids
    for r in reg:
        assert r["status"] in VOCAB and r["source"] and r["affects"] and r["value"]
    by = {r["id"]: r for r in reg}
    assert "600" in by["bunker_price"]["value"]
    assert "24 h" in by["port_stay"]["value"] and "3.5 d" in by["transfer_dwell"]["value"]
    assert by["capacity_unit"]["status"] == "SOURCED_PRIMARY_CODE"


def test_values_follow_the_assumptions_object():
    a = EconomicsAssumptions(port_stay_hours=12.0, transfer_wait_days=1.75)
    by = {r["id"]: r for r in build(a, NetworkLoader().load_fleet())}
    assert "12 h" in by["port_stay"]["value"] and "1.75 d" in by["transfer_dwell"]["value"]


def test_nothing_unsourced_is_labelled_sourced():
    by = {r["id"]: r for r in build(DEFAULT_ASSUMPTIONS, NetworkLoader().load_fleet())}
    for k in ("transfer_dwell", "cost_units", "transit_file"):
        assert by[k]["status"] == "PROVISIONAL"
    for k in ("fuel_grade", "weekly_frequency", "transit_scope"):
        assert by[k]["status"] == "UNVERIFIED"
    assert by["canal_fees"]["status"] == "NOT_MODELLED"
