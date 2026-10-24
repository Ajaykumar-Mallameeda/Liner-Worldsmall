"""World-500 / World-1000: exact size, unique collision-free identifiers, reproducible generation, plausible and
sparse structure, one fleet-scaling rule, documented limitations. Synthetic data are never presented as observations.
"""
import csv
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from src.data.dataset_registry import resolve_dataset, sha256_file

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "LINERLIB-master" / "data"
SIZES = {"World-500": 500, "World-1000": 1000}


def tsv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def gen_manifest(key):
    return json.loads((resolve_dataset(key).raw_dir / "generation_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("gen_synth", ROOT / "scripts" / "multi_dataset" / "generate_synthetic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("key,n", SIZES.items())
class TestEachSize:
    def test_exact_port_count_and_unique_ids(self, key, n):
        rows = tsv(resolve_dataset(key).input_paths()["ports"])
        ids = [r["UNLocode"] for r in rows]
        assert len(ids) == n and len(set(ids)) == n
        assert all(len(i) == 5 and i.startswith("ZZ") and i[2:].isdigit() for i in ids)

    def test_ids_cannot_collide_with_real_locodes(self, key, n):
        real = {r["UNLocode"] for r in tsv(SRC / "ports.csv")}
        assert not any(i.startswith("ZZ") for i in real)
        assert not ({r["UNLocode"] for r in tsv(resolve_dataset(key).input_paths()["ports"])} & real)

    def test_attributes_complete_and_drafts_are_real_class_levels(self, key, n):
        rows = tsv(resolve_dataset(key).input_paths()["ports"])
        levels = {float(r["Draft"]) for r in tsv(SRC / "ports.csv") if r["Draft"]}
        for r in rows:
            assert all(r[c] != "" for c in r)
            assert float(r["Draft"]) in levels
            assert -90 <= float(r["Latitude"]) <= 90 and -180 <= float(r["Longitude"]) <= 180
            assert all(float(r[c]) >= 0 for c in ("CostPerFULL", "CostPerFULLTrnsf", "PortCallCostFixed", "PortCallCostPerFFE"))

    def test_ports_are_geographically_grounded_near_real_ports(self, key, n):
        real = [(float(r["Latitude"]), float(r["Longitude"])) for r in tsv(SRC / "ports.csv") if r["Latitude"] and r["Longitude"]]
        rl, ro = np.radians([a for a, _ in real]), np.radians([b for _, b in real])
        far = 0
        for r in tsv(resolve_dataset(key).input_paths()["ports"]):
            la, lo = math.radians(float(r["Latitude"])), math.radians(float(r["Longitude"]))
            a = np.sin((rl - la) / 2) ** 2 + np.cos(rl) * math.cos(la) * np.sin((ro - lo) / 2) ** 2
            far += 2 * 3440.065 * np.arcsin(np.sqrt(a)).min() > 600
        assert far == 0

    def test_demand_is_sparse_valid_and_connects_every_port(self, key, n):
        ports = {r["UNLocode"] for r in tsv(resolve_dataset(key).input_paths()["ports"])}
        rows = tsv(resolve_dataset(key).input_paths()["demand"])
        pairs = {(r["Origin"], r["Destination"]) for r in rows}
        assert len(pairs) == len(rows) and all(o != d for o, d in pairs)
        assert {x for p in pairs for x in p} == ports
        density = len(pairs) / (n * (n - 1))
        assert density < 0.2 and density > 0.01                          # not all-pairs, not empty
        rev = sum((d, o) in pairs for o, d in pairs) / len(pairs)
        assert 0.4 < rev < 0.95
        assert all(float(r["FFEPerWeek"]) >= 1 and 100 <= float(r["Revenue_1"]) < 20000 and 3 <= float(r["TransitTime"]) <= 70
                   for r in rows)

    def test_distances_are_complete_geographic_and_use_the_canal_conventions(self, key, n):
        d = tsv(resolve_dataset(key).input_paths()["distance"])
        assert len(d) == n * (n - 1)
        assert all(float(r["Distance"]) >= 1 for r in d)
        flagged = sum(r["IsPanama"] != "0" or r["IsSuez"] != "0" for r in d)
        assert 0 < flagged < len(d)
        assert all(r["Draft"] == "" or float(r["Draft"]) > 0 for r in d)
        diag = gen_manifest(key)["diagnostics"]
        assert diag["min_geodesic_ratio"] >= 0.999

    def test_manifest_documents_method_seed_inputs_and_limitations(self, key, n):
        m = gen_manifest(key)
        assert m["kind"] == "synthetic" and m["seed"] == 20261016 and m["generator_version"]
        assert m["parameters"]["worldlarge_used"] is False
        assert "Demand_WorldLarge" not in " ".join(m["source_sha256"])
        assert len(m["limitations"]) >= 5 and any("coastline" in x for x in m["limitations"])
        for name, h in m["source_sha256"].items():
            assert sha256_file(SRC / name) == h
        for name, rec in m["files"].items():
            assert sha256_file(resolve_dataset(key).raw_dir / name) == rec["sha256"]
        assert m["population"]["this_dataset_ports"] == n


class TestScalingDesign:
    def test_world_500_ports_are_the_first_500_of_world_1000(self):
        a = (resolve_dataset("World-500").input_paths()["ports"]).read_text(encoding="utf-8").splitlines()
        b = (resolve_dataset("World-1000").input_paths()["ports"]).read_text(encoding="utf-8").splitlines()
        assert a == b[:501]

    def test_same_fleet_rule_for_both_sizes(self):
        m5, m10 = gen_manifest("World-500"), gen_manifest("World-1000")
        r5, r10 = m5["fleet_scaling"], m10["fleet_scaling"]
        assert r5["rule"] == r10["rule"] and r5["reference"] == r10["reference"]
        for m, r in ((m5, r5), (m10, r10)):
            ref = r["reference"]
            assert r["target_vessels_total"] == round(m["diagnostics"]["weekly_ffe"] / ref["ffe_per_vessel"])
            assert abs(r["vessels_total"] - r["target_vessels_total"]) <= 6          # per-class rounding only
            for c, share in ref["class_shares"].items():
                assert r["vessels_by_class"][c] == max(1, round(share * r["target_vessels_total"]))
        assert r5["reference"]["vessels"] == 263        # the reference case is WorldSmall

    def test_fleet_files_and_class_table(self):
        for key in SIZES:
            spec = resolve_dataset(key)
            assert spec.input_paths()["fleet_data"].read_bytes() == (SRC / "fleet_data.csv").read_bytes()
            fleet = {r["Vessel class"]: int(r["Quantity"]) for r in tsv(spec.input_paths()["fleet"])}
            assert fleet == gen_manifest(key)["fleet_scaling"]["vessels_by_class"]

    def test_demand_intensity_is_comparable_between_sizes(self):
        d5, d10 = gen_manifest("World-500")["diagnostics"], gen_manifest("World-1000")["diagnostics"]
        assert abs(d5["ffe_mean_per_od"] / d10["ffe_mean_per_od"] - 1) < 0.15
        assert abs(d5["mean_out_degree"] / d10["mean_out_degree"] - 1) < 0.2

    def test_calibration_was_measured_on_linerlib_not_invented(self):
        c = gen_manifest("World-1000")["calibration"]
        assert c["anchors"] > 100 and 10 < c["out_degree_geometric_mean"] < 40
        assert 0.3 < c["reverse_od_probability"] < 0.95 and c["revenue_regression"]["slope"] > 0


class TestReproducibility:
    def test_regeneration_into_a_temp_folder_is_byte_identical(self, generator, tmp_path):
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500"]) == 0
        for p in (tmp_path / "World-500").iterdir():
            assert p.read_bytes() == (resolve_dataset("World-500").raw_dir / p.name).read_bytes(), p.name

    def test_a_different_seed_gives_a_different_dataset(self, generator, tmp_path):
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500", "--seed", "7"]) == 0
        assert (tmp_path / "World-500" / "ports.csv").read_bytes() != resolve_dataset("World-500").input_paths()["ports"].read_bytes()

    def test_generator_refuses_to_overwrite_a_differing_file(self, generator, tmp_path):
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500"]) == 0
        (tmp_path / "World-500" / "ports.csv").write_text("changed", encoding="utf-8")
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500"]) == 1
        assert (tmp_path / "World-500" / "ports.csv").read_text(encoding="utf-8") == "changed"

    def test_check_mode_detects_drift(self, generator, tmp_path):
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500"]) == 0
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500", "--check"]) == 0
        (tmp_path / "World-500" / "fleet_World-500.csv").write_text("x", encoding="utf-8")
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500", "--check"]) == 1

    def test_generator_is_separate_from_optimizer_logic_and_never_reads_worldlarge(self, generator):
        text = (ROOT / "scripts" / "multi_dataset" / "generate_synthetic.py").read_text(encoding="utf-8")
        assert "from src" not in text and "import src" not in text
        assert all("WorldLarge" not in n for n in generator.CALIBRATION + generator.FULL_SIZE + generator.FLEET_REFERENCE)
        assert "WorldLarge" not in " ".join(generator.source_hashes(SRC))

    def test_replace_backs_up_the_previous_files_first(self, generator, tmp_path):
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500"]) == 0
        (tmp_path / "World-500" / "ports.csv").write_text("old", encoding="utf-8")
        assert generator.main(["--out-root", str(tmp_path), "--sizes", "500", "--replace"]) == 0
        backups = list((tmp_path / "_backups" / "World-500").iterdir())
        assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "old"
        assert (tmp_path / "World-500" / "ports.csv").read_bytes() == resolve_dataset("World-500").input_paths()["ports"].read_bytes()

    def test_values_stay_inside_the_support_observed_in_linerlib(self):
        c = gen_manifest("World-1000")["calibration"]
        for key in SIZES:
            rows = tsv(resolve_dataset(key).input_paths()["demand"])
            assert max(float(r["FFEPerWeek"]) for r in rows) <= c["ffe_support"][1]
            assert c["revenue_support"][0] <= min(float(r["Revenue_1"]) for r in rows)
            assert max(float(r["Revenue_1"]) for r in rows) <= c["revenue_support"][1]
