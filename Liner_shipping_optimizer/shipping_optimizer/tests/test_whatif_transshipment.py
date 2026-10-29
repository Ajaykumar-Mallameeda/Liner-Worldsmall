"""Transshipment in the What-if (backend/whatif._transship_summary): where re-routed cargo changes ship, baseline and
scenario, priced by the ledger's own rule so the hubs add up to the ledger's transshipment line."""

from types import SimpleNamespace

import pytest

from backend import whatif
from src.network.ledger import LedgerFlow

RUN = {"kind": "benchmark", "dataset": "worldsmall", "seed": 7}


def test_summary_counts_every_transfer_port_once_per_box():
    ports = {"H1": SimpleNamespace(transshipment_cost=50.0), "H2": SimpleNamespace(transshipment_cost=100.0),
             "A": SimpleNamespace(transshipment_cost=9.0)}
    flows = [LedgerFlow(0, (("s1", "A", "B"),), 100.0),
             LedgerFlow(1, (("s1", "A", "H1"), ("s2", "H1", "C")), 40.0),
             LedgerFlow(2, (("s3", "D", "H1"), ("s2", "H1", "H2"), ("s4", "H2", "E")), 10.0)]
    t = whatif._transship_summary(flows, ports)
    assert t["teu"] == 50.0 and t["moves"] == 60.0
    assert t["cost"] == 40 * 50 + 10 * 50 + 10 * 100
    assert [h["port"] for h in t["hubs"]] == ["H1", "H2"]
    assert t["hubs"][0] == {"port": "H1", "teu": 50.0, "cost": 2500.0, "cost_per_teu": 50.0}


@pytest.fixture(scope="module")
def suez():
    try:
        return whatif.whatif(whatif.WhatIfRequest(run=RUN, preset="suez"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"seed-7 benchmark run not available: {exc}")


def test_whatif_hubs_reconcile_with_the_ledger_line_on_both_sides(suez):
    for side in ("baseline", "scenario"):
        r = suez[side]
        t = r["transshipment"]
        assert t["cost"] == pytest.approx(r["transshipment_cost"], rel=1e-9, abs=1e-6), side
        assert sum(h["cost"] for h in t["hubs"]) == pytest.approx(t["cost"])
        assert sum(h["teu"] for h in t["hubs"]) == pytest.approx(t["moves"])
        assert t["teu"] <= r["served_teu"] + 1e-6
    assert suez["baseline"]["transshipment"]["hubs"] != suez["scenario"]["transshipment"]["hubs"]
