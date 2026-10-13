"""
WorldSmall data-loader regression tests.

Covers the loader data contract only: explicit WorldSmall paths, delimiter and
header normalization, FFE -> TEU conversion (revenue preserving), fleet units,
and strict validation. Canonical source files are read from data/raw/WorldSmall
and compared against an independent ``csv`` read of the same file; malformed
input uses small synthetic fixtures in tmp_path. No other dataset is read.
"""

import csv
import logging
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import network_loader as nl
from src.data.network_loader import (
    DataValidationError,
    NetworkLoader,
    WORLDSMALL_DIR,
    WORLDSMALL_FILES,
    _strip_columns,
    demand_scale_for_dataset,
    ffe_to_teu_factor,
)
from src.optimization.data import Problem

# Audited WorldSmall baseline (verified against the canonical files).
WS_PORTS = 47
WS_DEMAND_ROWS = 1764
WS_DIRECTED_PAIRS = 47 * 46
WS_FLEET_TOTAL = 263
WS_RAW_FFE = 138247
WS_RAW_GROSS_REVENUE = 264_870_100.0
WS_TEU = 276_446.8
WS_FLEET = {
    "Feeder_450": 24,
    "Feeder_800": 29,
    "Panamax_1200": 68,
    "Panamax_2400": 74,
    "Post_panamax": 58,
    "Super_panamax": 10,
}

# SYNTHETIC foreign identifiers: not WorldSmall ports and not real UN/LOCODEs. They stand
# in for "ports belonging to another dataset" so isolation can be tested without reading
# any other dataset (see TestDatasetSeparation.test_synthetic_foreign_ids_are_not_worldsmall_ports).
FOREIGN_IDS = ("ZZFO1", "ZZFO2")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def read_raw(path):
    """Independent tab-separated read of a canonical source (no loader code)."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def write_tsv(path, header, rows):
    path.write_text(
        "\n".join("\t".join(str(c) for c in r) for r in [header] + rows) + "\n",
        encoding="utf-8",
    )
    return path


PORT_HEADER = ["UNLocode", "name", "Country", "Longitude", "Latitude", "Draft",
               "CostPerFULL", "CostPerFULLTrnsf", "PortCallCostFixed", "PortCallCostPerFFE"]
DEMAND_HEADER = ["Origin", "Destination", "FFEPerWeek", "Revenue_1", "TransitTime"]
DIST_HEADER = ["fromUNLOCODe", "ToUNLOCODE", "Distance", "Draft", "IsPanama", "IsSuez"]
QTY_HEADER = ["Vessel class", "Quantity"]
SPEC_HEADER = ["Vessel class", "Capacity FFE", "TC rate daily (fixed Cost)", "draft", "minSpeed",
               "maxSpeed", "designSpeed", "Bunker ton per day at designSpeed",
               "Idle Consumption ton/day", "panamaFee", "suezFee"]


def port_row(pid, lat=20.0, lon=10.0, **over):
    row = {"UNLocode": pid, "name": f"Port {pid}", "Country": "X", "Longitude": lon,
           "Latitude": lat, "Draft": 12, "CostPerFULL": 100, "CostPerFULLTrnsf": 50,
           "PortCallCostFixed": 1000, "PortCallCostPerFFE": 5}
    row.update(over)
    return [row[h] for h in PORT_HEADER]


def spec_row(cls, capacity=1000, **over):
    row = {"Vessel class": cls, "Capacity FFE": capacity, "TC rate daily (fixed Cost)": 8000,
           "draft": 10, "minSpeed": 10, "maxSpeed": 20, "designSpeed": 15,
           "Bunker ton per day at designSpeed": 30, "Idle Consumption ton/day": 3,
           "panamaFee": 1000, "suezFee": 2000}
    row.update(over)
    return [row[h] for h in SPEC_HEADER]


@pytest.fixture
def loader():
    return NetworkLoader()


# ---------------------------------------------------------------------------
# 1-3. Explicit WorldSmall paths, missing files, no fallback
# ---------------------------------------------------------------------------
class TestPaths:
    def test_default_paths_are_the_canonical_worldsmall_files(self):
        expected = {
            "ports": "ports.csv",
            "demand": "Demand_WorldSmall_Fixed_Sep.csv",
            "distance": "dist_dense.csv",
            "fleet": "fleet_WorldSmall.csv",
            "fleet_data": "fleet_data.csv",
        }
        assert set(WORLDSMALL_FILES) == set(expected)
        for key, name in expected.items():
            path = WORLDSMALL_FILES[key]
            assert path == WORLDSMALL_DIR / name
            assert path.parent.name == "WorldSmall"
            assert path.is_file(), f"canonical WorldSmall file missing: {path}"
            assert "worldlarge" not in str(path).lower()

    def test_loader_reports_the_canonical_sources(self, loader):
        loader.load_network()
        loader.load_fleet()
        report = loader.validation_report
        assert Path(report["ports"]["source"]) == WORLDSMALL_FILES["ports"]
        assert Path(report["demands"]["source"]) == WORLDSMALL_FILES["demand"]
        assert Path(report["distances"]["source"]) == WORLDSMALL_FILES["distance"]
        assert Path(report["fleet"]["quantity_source"]) == WORLDSMALL_FILES["fleet"]
        assert Path(report["fleet"]["specification_source"]) == WORLDSMALL_FILES["fleet_data"]


class TestMissingFilesAndNoFallback:
    @pytest.mark.parametrize("key, call", [
        ("ports", lambda ld: ld.load_ports()),
        ("demand", lambda ld: ld.load_demands()),
        ("distance", lambda ld: ld.load_distance_matrix()),
        ("fleet", lambda ld: ld.load_fleet()),
        ("fleet_data", lambda ld: ld.load_fleet()),
    ])
    def test_missing_default_file_raises_and_does_not_fall_back(
        self, key, call, loader, monkeypatch, tmp_path
    ):
        # Decoys with plausible names sit next to the missing file; none may be used.
        for decoy in ("demand_world_small.csv", "fleet_world_small.csv", "ports.csv",
                      "Demand_WorldSmall_Fixed_Sep.csv", "dist_dense.csv", "distance_dense.csv"):
            (tmp_path / decoy).write_text("not,used\n", encoding="utf-8")
        missing = tmp_path / "missing_required_file.csv"
        patched = dict(WORLDSMALL_FILES)
        patched[key] = missing
        monkeypatch.setattr(nl, "WORLDSMALL_FILES", patched)

        with pytest.raises(FileNotFoundError) as exc:
            call(loader)
        assert str(missing) in str(exc.value)
        assert "No fallback" in str(exc.value)

    def test_missing_explicit_path_raises(self, loader, tmp_path):
        with pytest.raises(FileNotFoundError):
            loader.load_demands(tmp_path / "nope.csv")

    def test_fleet_specifications_are_required(self, loader, tmp_path):
        qty = write_tsv(tmp_path / "q.csv", QTY_HEADER, [["A", 1]])
        with pytest.raises(FileNotFoundError):
            loader.load_fleet(qty, tmp_path / "no_specs.csv")


# ---------------------------------------------------------------------------
# 4-6. Delimiter and header normalization
# ---------------------------------------------------------------------------
class TestDelimiterAndHeaders:
    def test_canonical_demand_is_tab_separated_and_parses(self, loader):
        header = WORLDSMALL_FILES["demand"].read_text(encoding="utf-8").splitlines()[0]
        assert "\t" in header and "," not in header
        assert len(loader.load_demands()) == WS_DEMAND_ROWS

    def test_comma_separated_file_is_rejected_with_hint(self, loader, tmp_path):
        p = tmp_path / "comma.csv"
        p.write_text("Origin,Destination,FFEPerWeek,Revenue_1\nA,B,1,100\n", encoding="utf-8")
        with pytest.raises(DataValidationError, match="tab-separated"):
            loader.load_demands(p)

    def test_quoted_and_padded_headers_are_normalized(self, loader, tmp_path):
        p = tmp_path / "demand.csv"
        p.write_text(
            "\"Origin\"\t'Destination'\t FFEPerWeek \t\"  Revenue_1 \"\tTransitTime\n"
            "AAAAA\tBBBBB\t 10 \t2100\t5\n",
            encoding="utf-8",
        )
        demands = loader.load_demands(p)
        assert len(demands) == 1
        assert (demands[0].origin, demands[0].destination) == ("AAAAA", "BBBBB")

    def test_bom_header_is_normalized(self, loader, tmp_path):
        p = tmp_path / "demand.csv"
        p.write_bytes("﻿Origin\tDestination\tFFEPerWeek\tRevenue_1\nA\tB\t1\t100\n".encode("utf-8"))
        assert len(loader.load_demands(p)) == 1

    def test_internal_spaces_and_punctuation_in_names_are_preserved(self):
        cols = _strip_columns([" 'TC rate daily (fixed Cost)' ", '"Idle Consumption ton/day"'], "x")
        assert cols == ["TC rate daily (fixed Cost)", "Idle Consumption ton/day"]

    @pytest.mark.parametrize("header", [
        'Origin\t"Origin"\tFFEPerWeek\tRevenue_1',
        "Origin\t Origin \tFFEPerWeek\tRevenue_1",
        "Origin\tOrigin\tFFEPerWeek\tRevenue_1",
    ])
    def test_duplicate_normalized_headers_are_rejected(self, header, loader, tmp_path):
        p = tmp_path / "demand.csv"
        p.write_text(header + "\nA\tB\t1\t100\n", encoding="utf-8")
        with pytest.raises(DataValidationError, match="duplicate column names"):
            loader.load_demands(p)

    def test_case_collision_is_rejected_where_headers_are_lowercased(self, loader, tmp_path):
        header = PORT_HEADER + ["latitude"]
        p = write_tsv(tmp_path / "ports.csv", header, [port_row("AAAAA") + [1]])
        with pytest.raises(DataValidationError, match="duplicate column names"):
            loader.load_ports(p)

    def test_missing_required_column_is_reported_with_file_and_column(self, loader, tmp_path):
        p = write_tsv(tmp_path / "demand.csv", ["Origin", "Destination", "FFEPerWeek"], [["A", "B", 1]])
        with pytest.raises(DataValidationError) as exc:
            loader.load_demands(p)
        assert "demand.csv" in str(exc.value) and "Revenue_1" in str(exc.value)


# ---------------------------------------------------------------------------
# 7-9. FFE -> TEU conversion preserves revenue; no WorldLarge scaling
# ---------------------------------------------------------------------------
class TestRevenuePreservation:
    def test_audited_baseline_totals(self, loader):
        demands = loader.load_demands()
        raw = read_raw(WORLDSMALL_FILES["demand"])
        assert len(raw) == WS_DEMAND_ROWS
        assert sum(float(r["FFEPerWeek"]) for r in raw) == WS_RAW_FFE
        assert sum(d.weekly_teu for d in demands) == pytest.approx(WS_TEU, rel=1e-9)
        report = loader.validation_report["demands"]
        assert report["raw_weekly_ffe"] == WS_RAW_FFE
        assert report["raw_gross_revenue_usd_per_week"] == WS_RAW_GROSS_REVENUE

    def test_aggregate_gross_revenue_is_preserved(self, loader):
        demands = loader.load_demands()
        raw = read_raw(WORLDSMALL_FILES["demand"])
        raw_gross = sum(float(r["FFEPerWeek"]) * float(r["Revenue_1"]) for r in raw)
        converted_gross = sum(d.weekly_teu * d.revenue_per_teu for d in demands)
        assert raw_gross == WS_RAW_GROSS_REVENUE
        assert converted_gross == pytest.approx(raw_gross, rel=1e-12)

    def test_per_od_revenue_is_preserved(self, loader):
        demands = {(d.origin, d.destination): d for d in loader.load_demands()}
        for r in read_raw(WORLDSMALL_FILES["demand"]):
            o, dst = r["Origin"].strip(), r["Destination"].strip()
            ffe, rev = float(r["FFEPerWeek"]), float(r["Revenue_1"])
            d = demands[(o, dst)]
            k = ffe_to_teu_factor(o, dst)
            assert d.weekly_teu == pytest.approx(ffe * k, rel=1e-12)
            assert d.revenue_per_teu == pytest.approx(rev / k, rel=1e-12)
            assert d.weekly_teu * d.revenue_per_teu == pytest.approx(ffe * rev, rel=1e-12), (o, dst)

    def test_revenue_is_divided_not_multiplied_by_the_factor(self, loader, tmp_path):
        # Both ends of the lane are WorldSmall ports (AEJEA->NLRTM is in the
        # canonical data with lane factor 2.1), so the fixture is a valid
        # WorldSmall-identity file.
        p = write_tsv(tmp_path / "d.csv", DEMAND_HEADER, [
            ["AEJEA", "NLRTM", 10, 2100, 5],   # lane factor 2.1
            ["AOLAD", "AEJEA", 1, 2290, 5],    # default factor 2.0
        ])
        by_od = {(d.origin, d.destination): d for d in loader.load_demands(p)}
        lane = by_od[("AEJEA", "NLRTM")]
        assert lane.weekly_teu == pytest.approx(21.0)
        assert lane.revenue_per_teu == pytest.approx(1000.0)
        default = by_od[("AOLAD", "AEJEA")]
        assert default.weekly_teu == 2.0
        assert default.revenue_per_teu == 1145.0   # not 4580.0

    def test_no_worldlarge_demand_scale_on_worldsmall(self, loader):
        demands = loader.load_demands()
        ratio = sum(d.weekly_teu for d in demands) / WS_RAW_FFE
        assert 1.99 <= ratio <= 2.01, f"TEU/FFE ratio {ratio}; x6 scaling would give ~12"
        assert loader.validation_report["demands"]["demand_scale"] == 1
        assert demand_scale_for_dataset("worldsmall_shipping_problem.json") == 1
        # load_problem() must not apply any extra multiplier on top of load_demands().
        base = {(d.origin, d.destination): d.weekly_teu for d in loader.load_demands()}
        problem = loader.load_problem()
        assert {(d.origin, d.destination): d.weekly_teu for d in problem.demands} == base


# ---------------------------------------------------------------------------
# 10-12. Fleet
# ---------------------------------------------------------------------------
class TestFleet:
    def test_capacity_is_not_doubled(self, loader):
        fleet = loader.load_fleet()
        raw = {r["Vessel class"].strip(): float(r["Capacity FFE"])
               for r in read_raw(WORLDSMALL_FILES["fleet_data"])}
        for c in fleet.classes:
            assert c.capacity_teu == raw[c.vessel_class], c.vessel_class
        assert fleet.get_class("Post_panamax").capacity_teu == 4200.0

    def test_six_classes_and_canonical_inventory(self, loader):
        fleet = loader.load_fleet()
        assert len(fleet.classes) == 6
        assert fleet.total_vessels == WS_FLEET_TOTAL
        assert {c.vessel_class: c.quantity for c in fleet.classes} == WS_FLEET
        for c in fleet.classes:
            assert c.design_speed > 0 and c.bunker_consumption_tons_per_day > 0

    def test_inventory_comes_from_the_file_not_a_constant(self, loader, tmp_path):
        q = write_tsv(tmp_path / "q.csv", QTY_HEADER, [["A", 7], ["B", 5]])
        s = write_tsv(tmp_path / "s.csv", SPEC_HEADER, [spec_row("A"), spec_row("B", 2000)])
        fleet = loader.load_fleet(q, s)
        assert fleet.total_vessels == 12
        assert fleet.get_class("B").capacity_teu == 2000.0

    def test_blank_fees_are_unknown_not_zero_and_other_blanks_are_rejected(self, loader, tmp_path):
        # Task 2 contract: a blank canal fee is "no value given" (None). It is not
        # a confirmed 0.0 fee and not evidence about transit feasibility, so it
        # must never be readable as "free". (Previously asserted == 0.0.)
        q = write_tsv(tmp_path / "q.csv", QTY_HEADER, [["A", 1]])
        s = write_tsv(tmp_path / "s.csv", SPEC_HEADER, [spec_row("A", panamaFee="")])
        cls = loader.load_fleet(q, s).get_class("A")
        assert cls.panama_fee is None
        assert cls.suez_fee == 2000.0            # a given value is kept as-is
        s = write_tsv(tmp_path / "s2.csv", SPEC_HEADER, [spec_row("A", designSpeed="")])
        with pytest.raises(DataValidationError, match="designSpeed"):
            loader.load_fleet(q, s)

    @pytest.mark.parametrize("qty_rows, spec_rows, match", [
        ([["A", 1], ["B", 1]], [["A"]], "without specifications"),
        ([["A", 1]], [["A"], ["B"]], "without quantities"),
        ([["A", 1], ["A", 2]], [["A"]], "duplicate vessel class"),
        ([["A", 1]], [["A"], ["A"]], "duplicate vessel class"),
        ([["A", -1]], [["A"]], "negative"),
        ([["A", 2.5]], [["A"]], "not an integer"),
        ([["A", "x"]], [["A"]], "non-numeric"),
        ([["A", "nan"]], [["A"]], "non-finite"),
    ])
    def test_class_and_quantity_validation(self, qty_rows, spec_rows, match, loader, tmp_path):
        q = write_tsv(tmp_path / "q.csv", QTY_HEADER, qty_rows)
        s = write_tsv(tmp_path / "s.csv", SPEC_HEADER, [spec_row(r[0]) for r in spec_rows])
        with pytest.raises(DataValidationError, match=match):
            loader.load_fleet(q, s)

    @pytest.mark.parametrize("over, match", [
        ({"capacity": 0}, "must be > 0"),
        ({"capacity": -450}, "negative"),
        ({"capacity": "inf"}, "non-finite"),
        ({"capacity": "n/a"}, "non-numeric"),
        ({"minSpeed": 20, "maxSpeed": 10}, "minSpeed <= designSpeed <= maxSpeed"),
        ({"suezFee": -1}, "negative"),
    ])
    def test_specification_validation(self, over, match, loader, tmp_path):
        q = write_tsv(tmp_path / "q.csv", QTY_HEADER, [["A", 1]])
        s = write_tsv(tmp_path / "s.csv", SPEC_HEADER, [spec_row("A", **over)])
        with pytest.raises(DataValidationError, match=match):
            loader.load_fleet(q, s)


# ---------------------------------------------------------------------------
# 13. Ports and coordinates
# ---------------------------------------------------------------------------
class TestPorts:
    def test_canonical_ports(self, loader):
        ports = loader.load_ports()
        raw = read_raw(WORLDSMALL_FILES["ports"])
        assert len(ports) == WS_PORTS == len(raw)
        ids = [p.id for p in ports]
        assert len(set(ids)) == WS_PORTS
        assert loader.validation_report["ports"]["excluded"] == []
        assert all(-90 <= p.latitude <= 90 and -180 <= p.longitude <= 180 for p in ports)
        by_id = {p.id: p for p in ports}
        jea = next(r for r in raw if r["UNLocode"] == "AEJEA")
        assert by_id["AEJEA"].latitude == float(jea["Latitude"])
        assert by_id["AEJEA"].longitude == float(jea["Longitude"])

    def test_duplicate_port_identifier_is_rejected(self, loader, tmp_path):
        p = write_tsv(tmp_path / "ports.csv", PORT_HEADER,
                      [port_row("AAAAA"), port_row("BBBBB"), port_row("AAAAA", lat=1.0)])
        with pytest.raises(DataValidationError, match="duplicate port identifier 'AAAAA'"):
            loader.load_ports(p)

    def test_blank_port_identifier_is_rejected(self, loader, tmp_path):
        p = write_tsv(tmp_path / "ports.csv", PORT_HEADER, [port_row("")])
        with pytest.raises(DataValidationError, match="blank identifier"):
            loader.load_ports(p)

    @pytest.mark.parametrize("over", [
        {"lat": ""}, {"lon": ""}, {"lat": "abc"}, {"lat": "nan"},
        {"lat": 91.0}, {"lat": -90.5}, {"lon": 180.5}, {"lon": -181},
    ])
    def test_unusable_coordinates_are_excluded_visibly(self, over, loader, tmp_path, caplog):
        p = write_tsv(tmp_path / "ports.csv", PORT_HEADER,
                      [port_row("AAAAA"), port_row("BADCO", **{
                          "Latitude": over.get("lat", 20.0), "Longitude": over.get("lon", 10.0)})])
        with caplog.at_level(logging.WARNING, logger="src.data.network_loader"):
            ports = loader.load_ports(p)
        assert [x.id for x in ports] == ["AAAAA"]
        excluded = loader.validation_report["ports"]["excluded"]
        assert [e["id"] for e in excluded] == ["BADCO"] and excluded[0]["reason"]
        assert any("BADCO" in r.getMessage() for r in caplog.records)

    @pytest.mark.parametrize("col, val, match", [
        ("CostPerFULL", "abc", "non-numeric"),
        ("CostPerFULL", "", "non-numeric"),
        ("PortCallCostFixed", -5, "negative"),
        ("Draft", "inf", "non-finite"),
    ])
    def test_invalid_port_numerics_are_rejected(self, col, val, match, loader, tmp_path):
        p = write_tsv(tmp_path / "ports.csv", PORT_HEADER, [port_row("AAAAA", **{col: val})])
        with pytest.raises(DataValidationError, match=match):
            loader.load_ports(p)


# ---------------------------------------------------------------------------
# 14-15. Distances
# ---------------------------------------------------------------------------
class TestDistances:
    def test_canonical_distances_use_the_worldsmall_source_and_nm(self, loader):
        dist = loader.load_distance_matrix()
        raw = read_raw(WORLDSMALL_FILES["distance"])
        assert sum(len(v) for v in dist.values()) == WS_DIRECTED_PAIRS == len(raw)
        for r in raw:
            assert dist[r["fromUNLOCODe"].strip()][r["ToUNLOCODE"].strip()] == float(r["Distance"])
        assert dist["AEJEA"]["AOLAD"] == 6439.0
        assert loader.validation_report["distances"]["unit"] == "nautical miles"

    def test_all_references_are_within_the_worldsmall_port_set(self, loader):
        net = loader.load_network()
        ids = {p.id for p in net["ports"]}
        assert ids == {r["UNLocode"].strip() for r in read_raw(WORLDSMALL_FILES["ports"])}
        assert {i for d in net["demands"] for i in (d.origin, d.destination)} <= ids
        assert set(net["distance_matrix"]) == ids
        assert all(set(row) <= ids for row in net["distance_matrix"].values())

    def test_directed_distances_are_not_symmetrized(self, loader, tmp_path):
        p = write_tsv(tmp_path / "d.csv", DIST_HEADER,
                      [["AAAAA", "BBBBB", 100, "", 0, 0], ["BBBBB", "AAAAA", 120, "", 0, 0]])
        dist = loader.load_distance_matrix(p)
        assert dist["AAAAA"]["BBBBB"] == 100.0 and dist["BBBBB"]["AAAAA"] == 120.0

    @pytest.mark.parametrize("rows, match", [
        ([["A", "B", 100], ["A", "B", 100]], "repeated distance"),
        ([["A", "B", 100], ["A", "B", 101]], "conflicting distance"),
        ([["A", "B", -1]], "negative"),
        ([["A", "B", "inf"]], "non-finite"),
        ([["A", "B", "nan"]], "non-finite"),
        ([["A", "B", "far"]], "non-numeric"),
        ([["A", "B", 0]], "zero distance"),
        ([["", "B", 5]], "blank identifier"),
    ])
    def test_invalid_distance_records_are_rejected(self, rows, match, loader, tmp_path):
        p = write_tsv(tmp_path / "d.csv", DIST_HEADER, [r + ["", 0, 0] for r in rows])
        with pytest.raises(DataValidationError, match=match):
            loader.load_distance_matrix(p)

    def test_missing_directed_pair_fails_without_synthetic_distance(self, loader, tmp_path):
        ports = loader.load_ports(write_tsv(tmp_path / "p.csv", PORT_HEADER,
                                            [port_row("AAAAA"), port_row("BBBBB")]))
        dist = loader.load_distance_matrix(
            write_tsv(tmp_path / "d.csv", DIST_HEADER, [["AAAAA", "BBBBB", 100, "", 0, 0]]))
        with pytest.raises(DataValidationError, match="no distance"):
            loader.validate_network(ports, [], dist)
        assert dist.get("BBBBB", {}).get("AAAAA") is None  # nothing was invented

    def test_unknown_ports_in_demand_or_distance_are_rejected(self, loader, tmp_path):
        ports = loader.load_ports(write_tsv(tmp_path / "p.csv", PORT_HEADER,
                                            [port_row("AAAAA"), port_row("BBBBB")]))
        full = {"AAAAA": {"BBBBB": 1.0}, "BBBBB": {"AAAAA": 1.0}}
        bad_demand = loader.load_demands(write_tsv(tmp_path / "d.csv", DEMAND_HEADER,
                                                   [["AAAAA", "ZZZZZ", 1, 100, 1]]))
        with pytest.raises(DataValidationError, match="demand references ports"):
            loader.validate_network(ports, bad_demand, full)
        with pytest.raises(DataValidationError, match="distance matrix references ports"):
            loader.validate_network(ports, [], {**full, "ZZZZZ": {"AAAAA": 1.0}})


# ---------------------------------------------------------------------------
# 16. Invalid demand numerics / structure
# ---------------------------------------------------------------------------
class TestDemandValidation:
    @pytest.mark.parametrize("ffe, rev, match", [
        ("abc", 100, "non-numeric"),
        ("", 100, "non-numeric"),
        ("nan", 100, "non-finite"),
        ("inf", 100, "non-finite"),
        (-1, 100, "negative"),
        (1, -100, "negative"),
        (1, "n/a", "non-numeric"),
    ])
    def test_invalid_numeric_demand_is_rejected(self, ffe, rev, match, loader, tmp_path):
        p = write_tsv(tmp_path / "d.csv", DEMAND_HEADER, [["AAAAA", "BBBBB", ffe, rev, 1]])
        with pytest.raises(DataValidationError, match=match) as exc:
            loader.load_demands(p)
        assert "d.csv" in str(exc.value) and "AAAAA->BBBBB" in str(exc.value)

    def test_duplicate_od_pair_is_rejected(self, loader, tmp_path):
        p = write_tsv(tmp_path / "d.csv", DEMAND_HEADER,
                      [["AAAAA", "BBBBB", 1, 100, 1], ["AAAAA", "BBBBB", 2, 100, 1]])
        with pytest.raises(DataValidationError, match="duplicate OD pair"):
            loader.load_demands(p)

    def test_self_loops_are_skipped_and_reported(self, loader, tmp_path, caplog):
        p = write_tsv(tmp_path / "d.csv", DEMAND_HEADER,
                      [["AAAAA", "AAAAA", 5, 100, 0], ["AAAAA", "BBBBB", 1, 100, 1]])
        with caplog.at_level(logging.WARNING, logger="src.data.network_loader"):
            demands = loader.load_demands(p)
        assert len(demands) == 1
        assert loader.validation_report["demands"]["self_loops_skipped"] == 1
        assert any("AAAAA->AAAAA" in r.getMessage() for r in caplog.records)

    def test_empty_file_is_rejected(self, loader, tmp_path):
        p = tmp_path / "d.csv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(DataValidationError, match="empty"):
            loader.load_demands(p)
        write_tsv(p, DEMAND_HEADER, [])
        with pytest.raises(DataValidationError, match="no data rows"):
            loader.load_demands(p)


# ---------------------------------------------------------------------------
# 17. WorldLarge separation (names and scale constants only; no WorldLarge file is read)
# ---------------------------------------------------------------------------
class TestDatasetSeparation:
    def test_worldlarge_legacy_scale_is_preserved_and_kept_separate(self):
        assert nl.LEGACY_WORLDLARGE_DEMAND_SCALE == 6
        assert demand_scale_for_dataset("large_shipping_problem.json") == 6
        assert nl.WORLDSMALL_DEMAND_SCALE == 1
        assert demand_scale_for_dataset("worldsmall_shipping_problem.json") == 1

    def test_synthetic_foreign_ids_are_not_worldsmall_ports(self):
        """Guard for every isolation fixture below: the foreign ids really are foreign."""
        ws_ids = {r["UNLocode"].strip() for r in read_raw(WORLDSMALL_FILES["ports"])}
        assert len(FOREIGN_IDS) == 2 and not ws_ids & set(FOREIGN_IDS)

    def test_non_worldsmall_dataset_is_not_mixed_with_worldsmall_distances(self, loader, tmp_path):
        p = tmp_path / "large_shipping_problem.json"
        p.write_text('{"ports": [], "demands": []}', encoding="utf-8")
        with pytest.raises(DataValidationError, match="not a WorldSmall dataset"):
            loader.load_problem(p)

    def test_load_problem_default_is_worldsmall_with_fleet(self, loader):
        problem = loader.load_problem()
        assert isinstance(problem, Problem)
        assert len(problem.ports) == WS_PORTS
        assert len(problem.demands) == WS_DEMAND_ROWS
        assert problem.fleet.total_vessels == WS_FLEET_TOTAL
        assert problem.services == []


# ---------------------------------------------------------------------------
# 19. Port-cost unit basis (USD/FFE -> USD/TEU is a DIVISION by 2.0)
# ---------------------------------------------------------------------------
class TestPortCostBasis:
    def test_per_ffe_rates_are_divided_and_fixed_cost_is_not(self, loader):
        ports = {p.id: p for p in loader.load_ports()}
        raw = read_raw(WORLDSMALL_FILES["ports"])
        assert len(raw) == WS_PORTS
        for r in raw:
            p = ports[r["UNLocode"].strip()]
            assert p.handling_cost == pytest.approx(float(r["CostPerFULL"]) / 2.0, rel=1e-12)
            assert p.transshipment_cost == pytest.approx(float(r["CostPerFULLTrnsf"]) / 2.0, rel=1e-12)
            assert p.variable_port_call_cost == pytest.approx(float(r["PortCallCostPerFFE"]) / 2.0, rel=1e-12)
            assert p.port_call_cost == float(r["PortCallCostFixed"])          # USD per call

    def test_cost_to_move_one_ffe_is_preserved(self, loader):
        """Same invariant as revenue: TEU flow x USD/TEU == FFE flow x USD/FFE."""
        ports = {p.id: p for p in loader.load_ports()}
        for r in read_raw(WORLDSMALL_FILES["ports"]):
            p = ports[r["UNLocode"].strip()]
            one_ffe_in_teu = 2.0
            assert one_ffe_in_teu * p.handling_cost == pytest.approx(float(r["CostPerFULL"]), rel=1e-12)
            assert one_ffe_in_teu * p.variable_port_call_cost == pytest.approx(
                float(r["PortCallCostPerFFE"]), rel=1e-12)

    def test_port_cost_conversion_is_not_lane_dependent(self, loader, tmp_path):
        # Port costs belong to the port, not to a trade lane: the lane-specific
        # revenue factors (e.g. 2.1) must not leak into the cost conversion.
        rows = [port_row("AAAAA", CostPerFULL=210, CostPerFULLTrnsf=84, PortCallCostPerFFE=10)]
        p = loader.load_ports(write_tsv(tmp_path / "p.csv", PORT_HEADER, rows))[0]
        assert (p.handling_cost, p.transshipment_cost, p.variable_port_call_cost) == (105.0, 42.0, 5.0)

    def test_report_states_the_basis(self, loader):
        loader.load_ports()
        assert "divided by 2.0" in loader.validation_report["ports"]["cost_basis"]


# ---------------------------------------------------------------------------
# 20. Canal fees: blank is unknown, not zero
# ---------------------------------------------------------------------------
class TestCanalFees:
    def test_canonical_blank_fees_are_unknown_and_reported(self, loader):
        raw = {r["Vessel class"].strip(): r for r in read_raw(WORLDSMALL_FILES["fleet_data"])}
        fleet = loader.load_fleet()
        blanks = {}
        for c in fleet.classes:
            for col, val in (("panamaFee", c.panama_fee), ("suezFee", c.suez_fee)):
                cell = raw[c.vessel_class][col].strip()
                if cell == "":
                    assert val is None, (c.vessel_class, col)
                    blanks.setdefault(c.vessel_class, []).append(col)
                else:
                    assert val == float(cell), (c.vessel_class, col)
        assert blanks, "the canonical file is expected to contain blank panamaFee cells"
        assert loader.validation_report["fleet"]["canal_fee_blank"] == blanks

    def test_confirmed_zero_stays_zero_and_blank_is_none(self, loader, tmp_path):
        q = write_tsv(tmp_path / "q.csv", QTY_HEADER, [["A", 1], ["B", 1]])
        s = write_tsv(tmp_path / "s.csv", SPEC_HEADER,
                      [spec_row("A", panamaFee=0, suezFee=0), spec_row("B", panamaFee="", suezFee="")])
        fleet = loader.load_fleet(q, s)
        assert (fleet.get_class("A").panama_fee, fleet.get_class("A").suez_fee) == (0.0, 0.0)
        assert (fleet.get_class("B").panama_fee, fleet.get_class("B").suez_fee) == (None, None)

    def test_default_fleet_class_fees_are_unknown(self):
        from src.optimization.data import FleetClass
        c = FleetClass(vessel_class="X", quantity=1)
        assert c.panama_fee is None and c.suez_fee is None


# ---------------------------------------------------------------------------
# 21. Explicit-path dataset boundary (location + content, never the file name)
# ---------------------------------------------------------------------------
class TestExplicitPathBoundary:
    @pytest.fixture
    def raw_tree(self, tmp_path, monkeypatch):
        """A stand-in raw-data tree that mirrors the repo layout, including
        WorldSmall-looking file names inside the WorldLarge directory."""
        raw = tmp_path / "raw"
        (raw / "WorldSmall").mkdir(parents=True)
        (raw / "WorldLarge").mkdir()
        monkeypatch.setattr(nl, "RAW_DATA_DIR", raw)
        monkeypatch.setattr(nl, "WORLDSMALL_DIR", raw / "WorldSmall")
        return raw

    def test_misleading_name_inside_worldlarge_directory_is_rejected(self, loader, raw_tree):
        p = write_tsv(raw_tree / "WorldLarge" / "ports_world_small.csv", PORT_HEADER, [port_row("AAAAA")])
        with pytest.raises(DataValidationError, match="reads only WorldSmall"):
            loader.load_ports(p)
        d = write_tsv(raw_tree / "WorldLarge" / "Demand_WorldSmall_Fixed_Sep.csv", DEMAND_HEADER,
                      [["AAAAA", "BBBBB", 1, 100, 1]])
        with pytest.raises(DataValidationError, match="reads only WorldSmall"):
            loader.load_demands(d)

    def test_any_non_worldsmall_location_in_the_raw_tree_is_rejected(self, loader, raw_tree):
        (raw_tree / "Other").mkdir()
        p = write_tsv(raw_tree / "Other" / "ports.csv", PORT_HEADER, [port_row("AAAAA")])
        with pytest.raises(DataValidationError, match="reads only WorldSmall"):
            loader.load_ports(p)

    def test_file_inside_the_worldsmall_directory_is_accepted(self, loader, raw_tree):
        p = write_tsv(raw_tree / "WorldSmall" / "ports.csv", PORT_HEADER, [port_row("AAAAA")])
        assert [x.id for x in loader.load_ports(p)] == ["AAAAA"]

    def test_isolated_fixture_outside_the_raw_tree_is_accepted(self, loader, tmp_path):
        p = write_tsv(tmp_path / "fixture_ports.csv", PORT_HEADER, [port_row("ZZZ01"), port_row("ZZZ02")])
        assert len(loader.load_ports(p)) == 2

    def test_worldsmall_subset_fixture_is_accepted(self, loader, tmp_path):
        p = write_tsv(tmp_path / "subset.csv", PORT_HEADER, [port_row("AEJEA"), port_row("NLRTM")])
        assert {x.id for x in loader.load_ports(p)} == {"AEJEA", "NLRTM"}

    def test_ports_file_mixing_worldsmall_and_foreign_ids_is_rejected(self, loader, tmp_path):
        # Named like the canonical file, living outside the raw tree: only the
        # content can reveal that it is a different (larger) dataset.
        rows = [port_row(r["UNLocode"].strip()) for r in read_raw(WORLDSMALL_FILES["ports"])]
        rows += [port_row(i) for i in FOREIGN_IDS]         # synthetic foreign ports
        p = write_tsv(tmp_path / "ports.csv", PORT_HEADER, rows)
        with pytest.raises(DataValidationError, match="mixes 47 WorldSmall port ids with 2"):
            loader.load_ports(p)

    def test_demand_and_distance_files_mixing_datasets_are_rejected(self, loader, tmp_path):
        d = write_tsv(tmp_path / "Demand_WorldSmall_Fixed_Sep.csv", DEMAND_HEADER,
                      [["AEJEA", "NLRTM", 1, 100, 1], ["AEJEA", FOREIGN_IDS[0], 1, 100, 1]])
        with pytest.raises(DataValidationError, match="demand file mixes"):
            loader.load_demands(d)
        m = write_tsv(tmp_path / "dist_dense.csv", DIST_HEADER,
                      [["AEJEA", "NLRTM", 100, "", 0, 0], ["AEJEA", FOREIGN_IDS[0], 100, "", 0, 0]])
        with pytest.raises(DataValidationError, match="distance file mixes"):
            loader.load_distance_matrix(m)

    def test_file_role_is_enforced_by_schema(self, loader):
        with pytest.raises(DataValidationError, match="missing required column"):
            loader.load_ports(WORLDSMALL_FILES["demand"])
        with pytest.raises(DataValidationError, match="missing required column"):
            loader.load_demands(WORLDSMALL_FILES["distance"])
        with pytest.raises(DataValidationError, match="missing required column"):
            loader.load_distance_matrix(WORLDSMALL_FILES["ports"])

    def test_canonical_files_pass_when_given_explicitly(self, loader):
        assert len(loader.load_ports(WORLDSMALL_FILES["ports"])) == WS_PORTS
        assert len(loader.load_demands(WORLDSMALL_FILES["demand"])) == WS_DEMAND_ROWS
        assert sum(len(v) for v in loader.load_distance_matrix(WORLDSMALL_FILES["distance"]).values()) == WS_DIRECTED_PAIRS
        assert loader.load_fleet(WORLDSMALL_FILES["fleet"], WORLDSMALL_FILES["fleet_data"]).total_vessels == WS_FLEET_TOTAL

    def test_default_is_never_a_worldlarge_file(self, loader):
        loader.load_network()
        loader.load_fleet()
        report = loader.validation_report
        for section in ("ports", "demands", "distances"):
            assert Path(report[section]["source"]).parent.name == "WorldSmall", section
        for key in ("quantity_source", "specification_source"):
            assert Path(report["fleet"][key]).parent.name == "WorldSmall", key
        assert report["ports"]["loaded"] == WS_PORTS


# ---------------------------------------------------------------------------
# 22. Explicit JSON dataset: identity from content, equivalence to canonical
# ---------------------------------------------------------------------------
def _canonical_json(loader, *, port_cost_factor=1.0, revenue_factor=1.0, qty_factor=1.0, extra_ports=()):
    import dataclasses
    ports = []
    for p in loader.load_ports():
        d = dataclasses.asdict(p)
        for f in ("handling_cost", "transshipment_cost", "variable_port_call_cost"):
            d[f] *= port_cost_factor
        ports.append(d)
    for pid in extra_ports:
        ports.append({"id": pid, "name": pid, "latitude": 1.0, "longitude": 1.0})
    demands = []
    for dm in loader.load_demands():
        d = dataclasses.asdict(dm)
        d["weekly_teu"] *= qty_factor
        d["revenue_per_teu"] *= revenue_factor
        demands.append(d)
    return {"ports": ports, "demands": demands}


class TestExplicitJsonDataset:
    def test_canonical_equivalent_dataset_loads_with_the_worldsmall_fleet(self, loader, tmp_path):
        import json
        p = tmp_path / "worldsmall_fixture.json"
        p.write_text(json.dumps(_canonical_json(loader)), encoding="utf-8")
        problem = loader.load_problem(p)
        assert len(problem.ports) == WS_PORTS and len(problem.demands) == WS_DEMAND_ROWS
        assert problem.fleet is not None and problem.fleet.total_vessels == WS_FLEET_TOTAL

    def test_worldlarge_content_under_a_worldsmall_name_is_rejected(self, loader, tmp_path):
        import json
        data = _canonical_json(loader, extra_ports=FOREIGN_IDS)          # synthetic foreign ports
        p = tmp_path / "worldsmall_shipping_problem.json"      # passes the name gate
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(DataValidationError, match="outside the WorldSmall port set"):
            loader.load_problem(p)

    def test_empty_dataset_with_a_worldsmall_name_is_rejected(self, loader, tmp_path):
        p = tmp_path / "worldsmall_empty.json"
        p.write_text('{"ports": [], "demands": []}', encoding="utf-8")
        with pytest.raises(DataValidationError, match="no ports or no demands"):
            loader.load_problem(p)

    @pytest.mark.parametrize("kwargs, needle", [
        ({"revenue_factor": 2.0, "qty_factor": 1.0}, "gross revenue"),     # revenue x k bug
        ({"qty_factor": 6.0}, "weekly_teu"),                                # WorldLarge x6 scale
        ({"port_cost_factor": 4.0}, "handling_cost"),                       # legacy x2 vs /2 basis
    ])
    def test_dataset_with_a_different_unit_basis_is_rejected(self, loader, tmp_path, kwargs, needle):
        import json
        p = tmp_path / "worldsmall_variant.json"
        p.write_text(json.dumps(_canonical_json(loader, **kwargs)), encoding="utf-8")
        with pytest.raises(DataValidationError, match="disagrees with the canonical") as exc:
            loader.load_problem(p)
        assert needle in str(exc.value)

    def test_dataset_inside_the_worldlarge_directory_is_rejected(self, loader, tmp_path, monkeypatch):
        import json
        raw = tmp_path / "raw"
        (raw / "WorldSmall").mkdir(parents=True)
        (raw / "WorldLarge").mkdir()
        monkeypatch.setattr(nl, "RAW_DATA_DIR", raw)
        monkeypatch.setattr(nl, "WORLDSMALL_DIR", raw / "WorldSmall")
        p = raw / "WorldLarge" / "worldsmall_shipping_problem.json"
        p.write_text(json.dumps(_canonical_json(loader)), encoding="utf-8")
        with pytest.raises(DataValidationError, match="reads only WorldSmall"):
            loader.load_problem(p)


# ---------------------------------------------------------------------------
# 18. Determinism
# ---------------------------------------------------------------------------
class TestDeterminism:
    def test_repeated_loading_is_identical(self):
        a, b = NetworkLoader(), NetworkLoader()
        na, nb = a.load_network(), b.load_network()
        assert na["ports"] == nb["ports"]
        assert na["demands"] == nb["demands"]
        assert na["distance_matrix"] == nb["distance_matrix"]
        assert a.load_fleet() == b.load_fleet()
        # Same instance, second call.
        assert a.load_demands() == na["demands"]
        assert a.validation_report["demands"] == b.validation_report["demands"]
