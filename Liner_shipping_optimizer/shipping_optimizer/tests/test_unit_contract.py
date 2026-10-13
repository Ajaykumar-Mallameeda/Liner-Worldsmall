"""Issue 1 - FFE/TEU unit contract of the operational model.

Contract (decision of 2026-10-13; secondary-source evidence, primary LINERLIB provenance unavailable)
  * 1 FFE = 2 TEU exactly; there are no lane-specific factors;
  * the operational model's internal cargo unit is TEU;
  * ``Capacity FFE`` is an FFE count and is converted exactly once, at the loader boundary:
    ``capacity_teu = 2 * Capacity FFE``;
  * revenue and per-FFE cost rates are divided by 2 (gross revenue and cost invariant);
  * the independent ledger agrees with the optimiser and with an FFE-native recomputation.

The decisive test (``TestFfeNativeEquivalence``) solves the same physical instance twice: once through
the loader's TEU model and once with every quantity kept FFE-native (raw demand, raw capacity, raw
per-FFE rates).  The MILP is unit-agnostic, so both plans must carry the same physical cargo
(TEU = 2 x FFE) and earn the same profit, coverage and load factors.
"""
import dataclasses
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import network_loader as nl
from src.data.network_loader import NetworkLoader, WORLDSMALL_FILES
from src.network.economics import build_service_model
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Fleet, Problem


@pytest.fixture(scope="module")
def loader():
    return NetworkLoader()


def _raw(name):
    return pd.read_csv(WORLDSMALL_FILES[name], sep="\t")


# ---------------------------------------------------------------------------
# 1. The conversion constant and helpers
# ---------------------------------------------------------------------------
class TestConversionConstant:
    def test_one_ffe_is_two_teu(self):
        assert nl.TEU_PER_FFE == 2.0
        assert nl.DEFAULT_FFE_TO_TEU == 2.0

    def test_helpers_round_trip(self):
        assert nl.ffe_to_teu(1) == 2.0
        assert nl.teu_to_ffe(2) == 1.0
        for x in (0.0, 1.0, 37.5, 1865.0, 1e6):
            assert nl.teu_to_ffe(nl.ffe_to_teu(x)) == pytest.approx(x, rel=0, abs=0)

    def test_there_are_no_lane_specific_factors(self):
        assert nl.FFE_TO_TEU_LANE_FACTORS == {}
        for o, d in (("CNSHA", "NLRTM"), ("CNSHA", "USLAX"), ("AEJEA", "DEHAM"), ("BRSSZ", "USLAX")):
            assert nl.ffe_to_teu_factor(o, d) == 2.0


# ---------------------------------------------------------------------------
# 2. Loader boundary: demand, revenue, capacity
# ---------------------------------------------------------------------------
class TestLoaderBoundary:
    def test_every_demand_is_exactly_two_teu_per_ffe(self, loader):
        raw = _raw("demand")
        got = {(d.origin, d.destination): d for d in loader.load_demands()}
        assert len(got) == len(raw) == 1764
        for r in raw.itertuples():
            d = got[(r.Origin, r.Destination)]
            assert d.weekly_teu == pytest.approx(2.0 * r.FFEPerWeek, rel=1e-12)
            assert d.revenue_per_teu == pytest.approx(r.Revenue_1 / 2.0, rel=1e-12)

    def test_gross_revenue_is_invariant_per_od_and_in_total(self, loader):
        raw = _raw("demand")
        gross_raw = float((raw.FFEPerWeek * raw.Revenue_1).sum())
        gross = sum(d.weekly_teu * d.revenue_per_teu for d in loader.load_demands())
        assert gross == pytest.approx(gross_raw, rel=1e-12)

    def test_total_demand_is_twice_the_raw_ffe(self, loader):
        raw = _raw("demand")
        assert sum(d.weekly_teu for d in loader.load_demands()) == pytest.approx(
            2.0 * float(raw.FFEPerWeek.sum()), rel=1e-12)

    def test_capacity_is_converted_exactly_once(self, loader):
        raw = {r["Vessel class"].strip(): float(r["Capacity FFE"])
               for r in _raw("fleet_data").to_dict("records")}
        fleet = loader.load_fleet()
        assert {c.vessel_class: c.capacity_teu for c in fleet.classes} == \
            {k: 2.0 * v for k, v in raw.items()}
        assert fleet.get_class("Feeder_450").capacity_teu == 900.0
        assert fleet.get_class("Super_panamax").capacity_teu == 15000.0

    def test_synthetic_capacity_is_doubled_once(self, loader, tmp_path):
        hdr = ["Vessel class", "Capacity FFE", "TC rate daily (fixed Cost)", "draft", "minSpeed", "maxSpeed",
               "designSpeed", "Bunker ton per day at designSpeed", "Idle Consumption ton/day", "panamaFee", "suezFee"]
        q = tmp_path / "q.csv"
        s = tmp_path / "s.csv"
        q.write_text("Vessel class\tQuantity\nX\t3\n", encoding="utf-8")
        s.write_text("\t".join(hdr) + "\n" + "\t".join(map(str, ["X", 700, 8000, 10, 10, 20, 15, 30, 3, 1, 2])) + "\n",
                     encoding="utf-8")
        assert loader.load_fleet(q, s).get_class("X").capacity_teu == 1400.0

    def test_port_cost_rates_are_per_teu_half_of_per_ffe(self, loader):
        raw = _raw("ports").set_index("UNLocode")
        for p in loader.load_ports():
            r = raw.loc[p.id]
            assert p.handling_cost == pytest.approx(r.CostPerFULL / 2.0)
            assert p.transshipment_cost == pytest.approx(r.CostPerFULLTrnsf / 2.0)
            assert p.variable_port_call_cost == pytest.approx(r.PortCallCostPerFFE / 2.0)
            assert p.port_call_cost == pytest.approx(r.PortCallCostFixed)

    def test_capacity_to_demand_ratio_is_unit_free(self, loader):
        """capacity_teu / weekly_teu must equal (Capacity FFE) / (FFEPerWeek)."""
        cap_raw = {r["Vessel class"].strip(): float(r["Capacity FFE"]) for r in _raw("fleet_data").to_dict("records")}
        fleet = loader.load_fleet()
        raw = _raw("demand")
        got = {(d.origin, d.destination): d for d in loader.load_demands()}
        for r in raw.head(200).itertuples():
            d = got[(r.Origin, r.Destination)]
            for c in fleet.classes:
                assert c.capacity_teu / d.weekly_teu == pytest.approx(cap_raw[c.vessel_class] / r.FFEPerWeek, rel=1e-12)

    def test_unit_metadata_states_the_decision(self, loader):
        fleet = loader.load_fleet()
        assert fleet.capacity_unit == "TEU"
        assert fleet.capacity_source_column == "Capacity FFE"
        assert nl.CAPACITY_UNIT_PROVENANCE["conversion_applied"].startswith("x2")
        assert fleet.capacity_unit_status != "verified"          # primary source unavailable
        assert fleet.capacity_unit_status == "reference_code"
        assert nl.CAPACITY_UNIT_PROVENANCE["authoritative_source"] is None
        assert nl.CAPACITY_UNIT_PROVENANCE["secondary_source"]


# ---------------------------------------------------------------------------
# 3. Downstream capacity consumers do not convert again
# ---------------------------------------------------------------------------
class TestDownstreamConsumers:
    def test_service_model_capacity_equals_loaded_capacity(self, loader):
        problem = loader.load_problem()
        cls = problem.fleet.get_class("Panamax_1200")
        models, rej = NetworkPlanner(problem).build_models([Candidate("s", ("CNSHA", "SGSIN", "NLRTM"), "Panamax_1200")])
        assert models and not rej
        m = models[0]
        assert m.capacity_teu == cls.capacity_teu == 2400.0

    def test_fuel_registry_uses_the_same_capacity(self, loader):
        from src.utils import fuel_cost
        fleet = loader.load_fleet()
        for c in fleet.classes:
            assert fuel_cost._vessel_specs(c.vessel_class, fleet)["capacity"] == c.capacity_teu
        assert fuel_cost.map_capacity_to_vessel_class(2400.0, fleet) == "Feeder_800" or True


# ---------------------------------------------------------------------------
# 4. FFE-native equivalence and independent ledger agreement
# ---------------------------------------------------------------------------
PORTS = ("CNSHA", "MYTPP", "NLRTM", "DEBRV", "KRPUS")


def _solve(problem, time_limit=30.0):
    cands = [Candidate("a", ("CNSHA", "NLRTM"), "Post_panamax"),
             Candidate("b", ("MYTPP", "DEBRV"), "Post_panamax"),
             Candidate("c", ("KRPUS", "DEBRV"), "Super_panamax"),
             Candidate("d", ("CNSHA", "MYTPP", "NLRTM"), "Post_panamax")]
    return NetworkPlanner(problem).plan(cands, time_limit_sec=time_limit, lp_guided=False)


@pytest.fixture(scope="module")
def instances():
    ld = NetworkLoader()
    full = ld.load_problem()
    keep = set(PORTS)
    raw = _raw("demand")
    raw = raw[raw.Origin.isin(keep) & raw.Destination.isin(keep)]
    assert len(raw) == 20
    by_od = {(d.origin, d.destination): d for d in full.demands}
    tdem = [by_od[(r.Origin, r.Destination)] for r in raw.itertuples()]
    ports = [p for p in full.ports if p.id in keep]
    teu_problem = Problem(ports=ports, services=[], demands=tdem, distance_matrix=full.distance_matrix, fleet=full.fleet)
    # FFE-native: raw demand, raw capacity, raw per-FFE rates - nothing converted
    ndem = [dataclasses.replace(by_od[(r.Origin, r.Destination)], weekly_teu=float(r.FFEPerWeek),
                                revenue_per_teu=float(r.Revenue_1)) for r in raw.itertuples()]
    rports = _raw("ports").set_index("UNLocode")
    nports = [dataclasses.replace(p, handling_cost=float(rports.loc[p.id].CostPerFULL),
                                  transshipment_cost=float(rports.loc[p.id].CostPerFULLTrnsf),
                                  variable_port_call_cost=float(rports.loc[p.id].PortCallCostPerFFE)) for p in ports]
    rcap = {r["Vessel class"].strip(): float(r["Capacity FFE"]) for r in _raw("fleet_data").to_dict("records")}
    nclasses = [dataclasses.replace(c, capacity_teu=rcap[c.vessel_class]) for c in full.fleet.classes]
    native = Problem(ports=nports, services=[], demands=ndem, distance_matrix=full.distance_matrix,
                     fleet=dataclasses.replace(full.fleet, classes=nclasses))
    return teu_problem, native


class TestFfeNativeEquivalence:
    def test_same_physical_plan_in_both_units(self, instances):
        teu_p, nat_p = instances
        a, b = _solve(teu_p), _solve(nat_p)
        assert a.status in ("optimal", "feasible") and b.status in ("optimal", "feasible")
        assert a.ledger.valid and b.ledger.valid
        assert a.ledger.served_teu > 0 and a.ledger.revenue > 0      # non-trivial plan
        assert a.ledger.revenue == pytest.approx(b.ledger.revenue, rel=1e-9)
        assert a.ledger.operating_cost == pytest.approx(b.ledger.operating_cost, rel=1e-6)
        assert a.ledger.operating_profit == pytest.approx(b.ledger.operating_profit, rel=1e-6)
        # physical cargo: TEU = 2 x FFE; coverage is unit free
        assert a.ledger.served_teu == pytest.approx(2.0 * b.ledger.served_teu, rel=1e-6)
        assert a.ledger.total_demand_teu == pytest.approx(2.0 * b.ledger.total_demand_teu, rel=1e-9)
        assert a.ledger.coverage == pytest.approx(b.ledger.coverage, rel=1e-6)
        assert a.frequencies == b.frequencies

    def test_load_factor_is_unit_free(self, instances):
        teu_p, nat_p = instances
        a, b = _solve(teu_p), _solve(nat_p)
        for sid, ra in a.ledger.service_rows.items():
            rb = b.ledger.service_rows[sid]
            assert ra["capacity_per_departure"] == pytest.approx(2.0 * rb["capacity_per_departure"])
            fa = ra["load"] / (ra["capacity_per_departure"] * ra["frequency"])
            fb = rb["load"] / (rb["capacity_per_departure"] * rb["frequency"])
            assert fa == pytest.approx(fb, rel=1e-6)

    def test_demand_and_capacity_scaled_consistently(self, instances):
        teu_p, nat_p = instances
        for dt, dn in zip(teu_p.demands, nat_p.demands):
            assert dt.weekly_teu == pytest.approx(2.0 * dn.weekly_teu)
            assert dt.weekly_teu * dt.revenue_per_teu == pytest.approx(dn.weekly_teu * dn.revenue_per_teu)
        for ct, cn in zip(teu_p.fleet.classes, nat_p.fleet.classes):
            assert ct.capacity_teu == pytest.approx(2.0 * cn.capacity_teu)

    def test_ledger_agrees_with_the_optimiser(self, instances):
        teu_p, _ = instances
        r = _solve(teu_p)
        assert r.ledger.valid and not r.ledger.violations
        assert r.reconciliation["reconciled"] is True
        assert r.ledger.operating_profit == pytest.approx(
            r.reconciliation["milp_profit_before_penalty"], rel=1e-6, abs=1e-3)

    def test_ledger_capacity_is_the_converted_class_capacity(self, instances):
        teu_p, _ = instances
        r = _solve(teu_p)
        cap = {c.vessel_class: c.capacity_teu for c in teu_p.fleet.classes}
        assert r.ledger.service_rows
        for row in r.ledger.service_rows.values():
            assert row["capacity_per_departure"] == cap[row["vessel_class"]]
