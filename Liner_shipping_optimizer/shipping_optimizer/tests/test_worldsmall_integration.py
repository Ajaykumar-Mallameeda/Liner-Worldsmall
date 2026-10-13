"""
WorldSmall runtime integration tests.

Verifies that the WorldSmall benchmark instance loads correctly through
the existing runtime architecture without requiring artificial demand
scaling or hardcoded fleet limits.

Dataset policy: the only real dataset read here is ``data/raw/WorldSmall``
(plus the legacy WorldSmall JSON artifact, which is asserted to be *rejected*).
Dataset isolation is verified with SYNTHETIC foreign-identifier fixtures built
in ``tmp_path``; no WorldLarge raw file, WorldLarge JSON artifact or any other
dataset is opened by this module.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import network_loader as nl
from src.data.network_loader import DataValidationError, NetworkLoader
from src.optimization.data import Problem, Fleet


BASE = Path(__file__).parent.parent
WS_CSV_DIR = BASE / "data" / "raw" / "WorldSmall"
WS_JSON = BASE / "data" / "datasets" / "worldsmall_shipping_problem.json"

# SYNTHETIC foreign identifiers: not WorldSmall ports and not real UN/LOCODEs.
# They stand in for "ports of some other dataset" without reading that dataset.
FOREIGN_IDS = ("ZZFO1", "ZZFO2")

PORT_HEADER = ["UNLocode", "name", "Country", "Longitude", "Latitude", "Draft",
               "CostPerFULL", "CostPerFULLTrnsf", "PortCallCostFixed", "PortCallCostPerFFE"]
DEMAND_HEADER = ["Origin", "Destination", "FFEPerWeek", "Revenue_1", "TransitTime"]
DIST_HEADER = ["fromUNLOCODe", "ToUNLOCODE", "Distance", "Draft", "IsPanama", "IsSuez"]


def _raw_rows(path):
    """Independent tab-separated read of a raw file (no NetworkLoader involved)."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path, header, rows):
    path.write_text(
        "\n".join("\t".join(str(c) for c in r) for r in [header] + rows) + "\n",
        encoding="utf-8",
    )
    return path


def _port_row(pid):
    return [pid, f"Port {pid}", "X", 10.0, 20.0, 12, 100, 50, 1000, 5]


# ---------------------------------------------------------------------------
# Test 1 — WorldSmall load
# ---------------------------------------------------------------------------
class TestWorldSmallLoad:
    def test_ports_count(self):
        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        assert len(ports) == 47

    def test_demands_count(self):
        loader = NetworkLoader()
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        assert len(demands) == 1764

    def test_distance_entries(self):
        loader = NetworkLoader()
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        total = sum(len(v) for v in dist.values())
        assert total == 2162

    def test_all_ports_in_distance_matrix(self):
        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        port_ids = {p.id for p in ports}
        matrix_keys = set(dist.keys())
        missing = port_ids - matrix_keys
        assert not missing, f"Ports missing from distance matrix: {missing}"

    def test_unique_origins_and_destinations(self):
        loader = NetworkLoader()
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        origins = {d.origin for d in demands}
        destinations = {d.destination for d in demands}
        assert len(origins) == 47
        assert len(destinations) == 47

    def test_no_duplicate_od_pairs(self):
        loader = NetworkLoader()
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        pairs = [(d.origin, d.destination) for d in demands]
        assert len(pairs) == len(set(pairs)), "Duplicate OD pairs found"

    def test_all_demands_reference_valid_ports(self):
        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        valid_ids = {p.id for p in ports}
        bad = [d for d in demands if d.origin not in valid_ids or d.destination not in valid_ids]
        assert not bad, f"Demands reference invalid ports: {bad[:5]}"


# ---------------------------------------------------------------------------
# Test 2 — Demand integrity (no DEMAND_SCALE applied)
# ---------------------------------------------------------------------------
class TestDemandIntegrity:
    def test_no_demand_scale_on_worldsmall_json_path(self):
        """WorldSmall JSON should NOT have DEMAND_SCALE=6 applied."""
        from tests.test_orchestrator import load_problem
        problem = load_problem(str(WS_JSON))
        # AOLAD->AEJEA: raw CSV has FFEPerWeek=1, Revenue_1=2290
        # JSON generator applies x2: weekly_teu=2.0, revenue_per_teu=4580.0
        # load_problem with auto-detection should use scale=1 (no extra scaling)
        sample = next(
            (d for d in problem.demands
             if d.origin == "AOLAD" and d.destination == "AEJEA"),
            None,
        )
        assert sample is not None
        assert sample.weekly_teu == 2.0, f"Expected 2.0, got {sample.weekly_teu}"
        assert sample.revenue_per_teu == 4580.0, f"Expected 4580.0, got {sample.revenue_per_teu}"

    def test_worldsmall_total_teu_is_unscaled(self):
        """No legacy demand multiplier is applied to WorldSmall.

        Total TEU is the raw FFE total times the lane factors (1.85-2.1). The
        legacy x6 multiplier (a WorldLarge-only convention) would give ~12x.
        Both sides are read from WorldSmall; the raw side bypasses the loader.
        """
        path = WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv"
        raw_ffe = sum(float(r["FFEPerWeek"]) for r in _raw_rows(path))
        teu = sum(d.weekly_teu for d in NetworkLoader().load_demands(path))
        assert raw_ffe == 138247
        assert teu == pytest.approx(276_446.8, abs=0.5)
        assert 1.85 <= teu / raw_ffe <= 2.1, f"TEU/FFE = {teu / raw_ffe:.3f}"

    def test_csv_path_no_scaling(self):
        """CSV loader path should not apply any DEMAND_SCALE."""
        loader = NetworkLoader()
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        sample = next(
            (d for d in demands
             if d.origin == "AOLAD" and d.destination == "AEJEA"),
            None,
        )
        assert sample is not None
        # CSV loader applies FFE x 2.0 factor (default lane factor)
        # Raw: FFEPerWeek=1 -> weekly_teu=2.0
        assert sample.weekly_teu == 2.0


# ---------------------------------------------------------------------------
# Test 3 — Fleet integrity
# ---------------------------------------------------------------------------
class TestFleetIntegrity:
    def test_fleet_classes_count(self):
        loader = NetworkLoader()
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        assert len(fleet.classes) == 6

    def test_fleet_total_vessels(self):
        loader = NetworkLoader()
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        assert fleet.total_vessels == 263

    def test_fleet_quantities_match_csv(self):
        loader = NetworkLoader()
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        expected = {
            "Feeder_450": 24,
            "Feeder_800": 29,
            "Panamax_1200": 68,
            "Panamax_2400": 74,
            "Post_panamax": 58,
            "Super_panamax": 10,
        }
        for cls_name, expected_qty in expected.items():
            actual = fleet.quantity_of(cls_name)
            assert actual == expected_qty, f"{cls_name}: expected {expected_qty}, got {actual}"

    def test_fleet_capacity_specs_loaded(self):
        """fleet_data.csv specs should be loaded for WorldSmall."""
        loader = NetworkLoader()
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        post = fleet.get_class("Post_panamax")
        assert post is not None
        assert post.capacity_teu == 4200.0, f"Expected 4200, got {post.capacity_teu}"
        assert post.design_speed > 0
        assert post.bunker_consumption_tons_per_day > 0

    def test_problem_carries_fleet(self):
        """Problem dataclass should accept and store a Fleet instance."""
        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        problem = Problem(
            ports=ports, services=[],
            demands=demands, distance_matrix=dist, fleet=fleet,
        )
        assert problem.fleet is not None
        assert problem.fleet.total_vessels == 263


# ---------------------------------------------------------------------------
# Test 4 — No WorldLarge leakage
# ---------------------------------------------------------------------------
class TestNoWorldLargeLeakage:
    def test_no_worldlarge_demand_file_loaded(self):
        """WorldSmall should never read demand_world_large.csv."""
        loader = NetworkLoader()
        # Direct CSV load should produce exactly 1764 demands
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        assert len(demands) == 1764

    def test_no_worldlarge_ports_loaded(self):
        """WorldSmall should never load from global ports.csv (435 rows)."""
        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        assert len(ports) == 47

    def test_loaded_port_ids_equal_independent_worldsmall_raw_read(self):
        """The loaded port set is exactly the WorldSmall file's identifier set.

        Replaces a check that compared WorldSmall with the WorldLarge port file;
        the identity is now established against WorldSmall's own raw rows, and
        the synthetic foreign identifiers are asserted to be outside that set.
        """
        loader = NetworkLoader()
        raw_ids = {r["UNLocode"].strip() for r in _raw_rows(WS_CSV_DIR / "ports.csv")}
        assert len(raw_ids) == 47
        assert {p.id for p in loader.load_ports(WS_CSV_DIR / "ports.csv")} == raw_ids
        # no-argument default resolves to the same WorldSmall file
        assert {p.id for p in loader.load_ports()} == raw_ids
        assert not raw_ids & set(FOREIGN_IDS), "fixture ids must not be WorldSmall ports"

    def test_distance_matrix_equals_independent_worldsmall_raw_read(self):
        """Every directed pair comes from WorldSmall dist_dense.csv, unaltered."""
        loader = NetworkLoader()
        raw = _raw_rows(WS_CSV_DIR / "dist_dense.csv")
        assert len(raw) == 2162
        default_dist = loader.load_distance_matrix()
        assert default_dist == loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        assert sum(len(v) for v in default_dist.values()) == len(raw)
        for r in raw:
            o, d = r["fromUNLOCODe"].strip(), r["ToUNLOCODE"].strip()
            assert default_dist[o][d] == pytest.approx(float(r["Distance"])), (o, d)

    def test_default_sources_are_the_canonical_worldsmall_files(self):
        """Selected configuration, source identity and loaded data are consistent."""
        loader = NetworkLoader()
        problem = loader.load_problem()
        report = loader.validation_report
        expected = {
            ("ports", "source"): WS_CSV_DIR / "ports.csv",
            ("demands", "source"): WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv",
            ("distances", "source"): WS_CSV_DIR / "dist_dense.csv",
            ("fleet", "quantity_source"): WS_CSV_DIR / "fleet_WorldSmall.csv",
            ("fleet", "specification_source"): WS_CSV_DIR / "fleet_data.csv",
        }
        for (section, key), path in expected.items():
            assert Path(report[section][key]).resolve() == path.resolve(), (section, key)
        # ...and what was loaded is what those sources contain.
        assert len(problem.ports) == report["ports"]["loaded"] == 47
        assert len(problem.demands) == 1764
        assert problem.fleet.total_vessels == 263
        ids = {p.id for p in problem.ports}
        assert all(d.origin in ids and d.destination in ids for d in problem.demands)

    def test_synthetic_foreign_ids_mixed_into_any_input_file_are_rejected(self, tmp_path):
        """A file that mixes WorldSmall and foreign identifiers is a different
        dataset presented as WorldSmall; it is refused for every input role."""
        loader = NetworkLoader()
        ws = sorted(p.id for p in loader.load_ports())[:3]
        mixed = list(ws) + list(FOREIGN_IDS)

        ports = _write_tsv(tmp_path / "ports.csv", PORT_HEADER, [_port_row(i) for i in mixed])
        with pytest.raises(DataValidationError, match="mixes 3 WorldSmall port ids with 2"):
            loader.load_ports(ports)

        demand = _write_tsv(tmp_path / "Demand_WorldSmall_Fixed_Sep.csv", DEMAND_HEADER,
                            [[ws[0], ws[1], 1, 100, 1], [ws[0], FOREIGN_IDS[0], 1, 100, 1]])
        with pytest.raises(DataValidationError, match="demand file mixes"):
            loader.load_demands(demand)

        dist = _write_tsv(tmp_path / "dist_dense.csv", DIST_HEADER,
                          [[ws[0], ws[1], 100, "", 0, 0], [ws[0], FOREIGN_IDS[0], 100, "", 0, 0]])
        with pytest.raises(DataValidationError, match="distance file mixes"):
            loader.load_distance_matrix(dist)

    def test_fully_synthetic_dataset_is_never_combined_with_worldsmall_distances(self, tmp_path):
        """An isolated all-foreign fixture may be unit-tested at file level, but
        it cannot become a Problem: that would pair it with WorldSmall distances."""
        loader = NetworkLoader()
        ports = _write_tsv(tmp_path / "fixture_ports.csv", PORT_HEADER,
                           [_port_row(i) for i in FOREIGN_IDS])
        assert {p.id for p in loader.load_ports(ports)} == set(FOREIGN_IDS)   # isolated: ok

        dataset = tmp_path / "worldsmall_synthetic_foreign.json"             # passes the name gate
        dataset.write_text(json.dumps({
            "ports": [{"id": i, "name": i, "latitude": 1.0, "longitude": 1.0} for i in FOREIGN_IDS],
            "demands": [{"origin": FOREIGN_IDS[0], "destination": FOREIGN_IDS[1],
                         "weekly_teu": 1.0, "revenue_per_teu": 100.0}],
        }), encoding="utf-8")
        with pytest.raises(DataValidationError, match="outside the WorldSmall port set"):
            loader.load_problem(dataset)

    def test_non_worldsmall_raw_location_is_rejected_before_any_table_is_read(
            self, tmp_path, monkeypatch):
        """Location, not content or name, decides - and nothing is parsed first.

        A stand-in raw tree is built in tmp_path so that no real foreign file is
        involved; ``_read_table`` is replaced by a tripwire to prove that the
        rejection happens before the file is loaded.
        """
        raw = tmp_path / "raw"
        (raw / "WorldSmall").mkdir(parents=True)
        (raw / "OtherDataset").mkdir()
        monkeypatch.setattr(nl, "RAW_DATA_DIR", raw)
        monkeypatch.setattr(nl, "WORLDSMALL_DIR", raw / "WorldSmall")

        def tripwire(*args, **kwargs):
            raise AssertionError("a foreign-location file was parsed before being rejected")

        monkeypatch.setattr(nl, "_read_table", tripwire)

        loader = NetworkLoader()
        files = {
            "ports": (raw / "OtherDataset" / "ports.csv", loader.load_ports),
            "demand": (raw / "OtherDataset" / "Demand_WorldSmall_Fixed_Sep.csv", loader.load_demands),
            "distance": (raw / "OtherDataset" / "dist_dense.csv", loader.load_distance_matrix),
        }
        for role, (path, load) in files.items():
            path.write_text("not parsed\n", encoding="utf-8")
            with pytest.raises(DataValidationError, match="reads only WorldSmall"):
                load(path)

    def test_legacy_worldsmall_json_artifact_is_not_loadable_as_production_input(self):
        """data/datasets/worldsmall_shipping_problem.json is a stale generated
        artifact (x2 revenue and port costs). The loader refuses it rather than
        letting it feed the optimizer with different economics than the CSVs."""
        assert WS_JSON.exists(), "legacy artifact expected for this characterization"
        with pytest.raises(DataValidationError, match="disagrees with the canonical"):
            NetworkLoader().load_problem(WS_JSON)


# ---------------------------------------------------------------------------
# Test 5 — Distance integrity
# ---------------------------------------------------------------------------
class TestDistanceIntegrity:
    def test_directed_pairs_count(self):
        loader = NetworkLoader()
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        total = sum(len(v) for v in dist.values())
        assert total == 2162

    def test_no_missing_distances(self):
        """All 47x46 = 2162 directed pairs should exist."""
        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        port_ids = [p.id for p in ports]
        missing = 0
        for o in port_ids:
            for d in port_ids:
                if o == d:
                    continue
                if d not in dist.get(o, {}):
                    missing += 1
        assert missing == 0, f"Missing {missing} distance pairs"

    def test_distance_values_positive(self):
        loader = NetworkLoader()
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        for origin, dests in dist.items():
            for dest, val in dests.items():
                assert val > 0, f"Non-positive distance {origin}->{dest}: {val}"


# ---------------------------------------------------------------------------
# Test 6 — Service generation with empty services
# ---------------------------------------------------------------------------
class TestServiceGeneration:
    def test_empty_services_does_not_prevent_generation(self):
        """A Problem with services=[] should still allow service generation."""
        from src.agents.service_generator_agent import ServiceGeneratorAgent
        from src.optimization.data import Problem, Fleet

        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        problem = Problem(
            ports=ports, services=[],
            demands=demands, distance_matrix=dist, fleet=fleet,
        )
        assert len(problem.services) == 0

        agent = ServiceGeneratorAgent(name="test", model="test-model")
        result = agent.process({"problem": problem})
        assert result["services_generated"] > 0
        assert len(problem.services) > 0


# ---------------------------------------------------------------------------
# Test 7 — WorldSmall-only workflow (replaces the WorldLarge regression class)
#
# The former tests read WorldLarge raw files and the WorldLarge JSON artifact to
# assert properties of WorldLarge itself. The workflow is WorldSmall-only, so
# what remains - and is asserted here against WorldSmall's own raw rows - is
# that the no-argument defaults select WorldSmall and nothing else.
# ---------------------------------------------------------------------------
class TestWorldSmallOnlyWorkflow:
    def test_loader_defaults_are_worldsmall(self):
        loader = NetworkLoader()
        assert len(loader.load_ports()) == 47
        assert len(loader.load_demands()) == 1764
        assert sum(len(v) for v in loader.load_distance_matrix().values()) == 2162

    def test_default_fleet_matches_independent_raw_read(self):
        """Inventory is the WorldSmall file's own Quantity column (not a constant)."""
        raw = {r["Vessel class"].strip(): int(r["Quantity"])
               for r in _raw_rows(WS_CSV_DIR / "fleet_WorldSmall.csv")}
        assert len(raw) == 6 and sum(raw.values()) == 263

        fleet = NetworkLoader().load_fleet()
        assert fleet.total_vessels == 263
        assert len(fleet.classes) == 6
        assert {c.vessel_class: c.quantity for c in fleet.classes} == raw


# ---------------------------------------------------------------------------
# Test 8 — Fleet-derived fleet size in optimizers
# ---------------------------------------------------------------------------
class TestFleetInOptimizers:
    def test_hierarchical_ga_uses_problem_fleet(self):
        """HierarchicalGA should use problem.fleet.total_vessels when available."""
        from src.optimization.hierarchical_ga import HierarchicalGA
        from src.optimization.data import Problem, Fleet, FleetClass

        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        problem = Problem(
            ports=ports, services=[],
            demands=demands, distance_matrix=dist, fleet=fleet,
        )
        # Verify fleet is accessible
        assert problem.fleet is not None
        assert problem.fleet.total_vessels == 263

    def test_frequency_ga_uses_problem_fleet(self):
        """FrequencyGA should use problem.fleet.total_vessels when available."""
        from src.optimization.frequency_ga import FrequencyGA
        from src.optimization.data import Problem, Fleet

        loader = NetworkLoader()
        ports = loader.load_ports(WS_CSV_DIR / "ports.csv")
        demands = loader.load_demands(WS_CSV_DIR / "Demand_WorldSmall_Fixed_Sep.csv")
        dist = loader.load_distance_matrix(WS_CSV_DIR / "dist_dense.csv")
        fleet = loader.load_fleet(
            WS_CSV_DIR / "fleet_WorldSmall.csv",
            WS_CSV_DIR / "fleet_data.csv",
        )
        problem = Problem(
            ports=ports, services=[],
            demands=demands, distance_matrix=dist, fleet=fleet,
        )
        # Verify fleet propagation
        assert problem.fleet.total_vessels == 263
