"""Dataset packages: source -> canonical JSON, isolation between datasets, rebuild safety, WorldSmall unchanged.

World-1000's full validation (~1 min: a million-pair geometry check) runs when ``LINER_FULL_VALIDATION=1``;
otherwise its recorded manifest validation, hashes and counts are checked (the build script validated it).
"""
import builtins
import csv
import hashlib
import json
import os
from pathlib import Path

import pytest

import src.data.dataset_registry as reg
from src.data.dataset_registry import list_datasets, resolve_dataset, sha256_file
from src.data.dataset_validation import summarize, validate_dataset
from src.data.network_loader import NetworkLoader
from src.data.problem_json import (CONVERTER_VERSION, ProblemJsonError, build_problem_dict, dumps_problem,
                                   load_problem_json, problem_differences, validate_problem_dict)
from src.utils import fuel_cost

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["WorldSmall", "baltic", "WAF", "World-500", "World-1000"]
EXPECTED_COUNTS = {   # ports, demand records, directed pairs, vessels
    "WorldSmall": (47, 1764, 2162, 263), "baltic": (12, 22, 132, 6), "WAF": (20, 37, 380, 42),
    "World-500": (500, 18796, 249500, 2570), "World-1000": (1000, 35171, 999000, 4514)}
FULL = os.environ.get("LINER_FULL_VALIDATION") == "1"


def manifest(key):
    return json.loads(resolve_dataset(key).manifest_path.read_text(encoding="utf-8"))


def tsv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def fingerprint(problem):
    h = hashlib.sha256()
    for p in problem.ports:
        h.update(repr(p).encode())
    for d in problem.demands:
        h.update(repr(d).encode())
    for o, row in problem.distance_matrix.items():
        h.update(o.encode() + repr(sorted(row.items())).encode())
    for c in problem.fleet.classes:
        h.update(repr(c).encode())
    h.update(repr(sorted(problem.distance_matrix.canal_flags.items())).encode())
    return h.hexdigest()


# --------------------------------------------------------------------------------------------- per dataset
@pytest.mark.parametrize("key", KEYS)
class TestEachPackage:
    def test_source_files_exist_in_the_datasets_own_directory(self, key):
        spec = resolve_dataset(key)
        assert spec.missing_inputs() == []
        assert spec.json_path.is_file() and spec.manifest_path.is_file()

    def test_manifest_hashes_match_the_files_on_disk(self, key):
        spec, man = resolve_dataset(key), manifest(key)
        assert man["dataset"] == key
        for role, p in spec.input_paths().items():
            rec = next(v for v in man["source_package"]["files"].values() if v["file"] == p.name)
            assert rec["sha256"] == sha256_file(p), f"{key}/{p.name} changed since the manifest was built"
        assert man["problem_json"]["sha256"] == sha256_file(spec.json_path)

    def test_json_declares_its_own_identity_and_schema(self, key):
        obj = json.loads(resolve_dataset(key).json_path.read_text(encoding="utf-8"))
        validate_problem_dict(obj, resolve_dataset(key))
        assert obj["dataset"]["key"] == key and obj["schema_version"] == 1
        assert obj["provenance"]["build_id"] == manifest(key)["schema"]["build_id"]
        assert obj["services"] == []

    def test_record_counts(self, key):
        n_ports, n_dem, n_pairs, n_ves = EXPECTED_COUNTS[key]
        c = manifest(key)["counts"]
        assert (c["ports"], c["demand_records"], c["directed_distance_pairs"], c["vessels_total"]) == \
               (n_ports, n_dem, n_pairs, n_ves)
        problem, meta = load_problem_json(key)
        assert meta["counts"]["ports"] == n_ports and meta["counts"]["demands"] == n_dem
        assert meta["counts"]["directed_distance_pairs"] == n_pairs and problem.fleet.total_vessels == n_ves
        assert meta["counts"]["ports"] == len(tsv(resolve_dataset(key).input_paths()["ports"]))
        assert meta["counts"]["demands"] == len(tsv(resolve_dataset(key).input_paths()["demand"]))

    def test_demand_endpoints_and_fleet_classes_are_valid(self, key):
        problem, _ = load_problem_json(key)
        ids = {p.id for p in problem.ports}
        assert all(d.origin in ids and d.destination in ids for d in problem.demands)
        spec_rows = {r["Vessel class"] for r in tsv(resolve_dataset(key).input_paths()["fleet_data"])}
        assert {c.vessel_class for c in problem.fleet.classes} == spec_rows
        assert all(c.capacity_teu > 0 and c.quantity >= 0 for c in problem.fleet.classes)
        assert all(d.max_transit_days and d.max_transit_days > 0 for d in problem.demands)

    def test_manifest_records_a_clean_validation(self, key):
        v = manifest(key)["validation"]["summary"]
        assert v["blocking_failures"] == 0 and v["passed"] >= 25

    def test_loading_the_json_reads_only_this_datasets_json(self, key, monkeypatch):
        if key == "World-1000":
            pytest.skip("covered by the smaller datasets; the load itself is exercised by the run")
        opened = []
        real_open = builtins.open
        monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
        real_read = Path.read_text
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (opened.append(str(self)), real_read(self, *a, **k))[1])
        load_problem_json(key)
        data_reads = [p for p in opened if (os.sep + "data" + os.sep) in p or "/data/" in p]
        assert data_reads and all(Path(p) == resolve_dataset(key).json_path for p in data_reads), data_reads

    def test_json_equals_the_csv_package_for_every_optimizer_field(self, key):
        if key == "World-1000":
            pytest.skip("equality is checked at the start of every run and by the full validation")
        spec = resolve_dataset(key)
        problem, _ = load_problem_json(key)
        loader = NetworkLoader(dataset=spec)
        net = loader.load_network()
        from src.optimization.data import Problem
        csv_problem = Problem(ports=net["ports"], services=[], demands=net["demands"],
                              distance_matrix=net["distance_matrix"], fleet=loader.load_fleet())
        assert problem_differences(csv_problem, problem) == []

    def test_json_derived_totals_agree_with_independent_arithmetic_on_the_raw_files(self, key):
        if key == "World-1000":
            pytest.skip("same arithmetic as the smaller datasets")
        spec = resolve_dataset(key)
        problem, _ = load_problem_json(key)
        rows = tsv(spec.input_paths()["demand"])
        raw_ffe = sum(float(r["FFEPerWeek"]) for r in rows)
        raw_gross = sum(float(r["FFEPerWeek"]) * float(r["Revenue_1"]) for r in rows)
        assert sum(d.weekly_teu for d in problem.demands) == pytest.approx(2 * raw_ffe, rel=1e-12)
        assert sum(d.weekly_teu * d.revenue_per_teu for d in problem.demands) == pytest.approx(raw_gross, rel=1e-9)
        raw_cap = {r["Vessel class"]: float(r["Capacity FFE"]) for r in tsv(spec.input_paths()["fleet_data"])}
        assert {c.vessel_class: c.capacity_teu for c in problem.fleet.classes} == {k: 2 * v for k, v in raw_cap.items()}
        raw_d = {(r["fromUNLOCODe"], r["ToUNLOCODE"]): float(r["Distance"]) for r in tsv(spec.input_paths()["distance"])}
        assert all(problem.distance_matrix[o][d] == v for (o, d), v in list(raw_d.items())[:5000])

    def test_full_validation_has_no_blocking_failure(self, key):
        if key == "World-1000" and not FULL:
            pytest.skip("set LINER_FULL_VALIDATION=1 (about a minute)")
        checks = validate_dataset(key)
        assert summarize(checks)["blocking_failures"] == 0, [c for c in checks if not c["ok"] and c["severity"] == "error"]


# --------------------------------------------------------------------------------------------- regional specifics
class TestRegionalSources:
    @pytest.mark.parametrize("key,ports,classes", [("baltic", 12, {"Feeder_450", "Feeder_800"}),
                                                    ("WAF", 20, {"Feeder_450", "Feeder_800"})])
    def test_regional_package_matches_its_linerlib_source(self, key, ports, classes):
        src = ROOT / "data" / "LINERLIB-master" / "data"
        spec = resolve_dataset(key)
        demand_name = spec.files["demand"]
        assert (spec.raw_dir / demand_name).read_bytes() == (src / demand_name).read_bytes()
        assert (spec.raw_dir / spec.files["fleet"]).read_bytes() == (src / spec.files["fleet"]).read_bytes()
        src_ports = {r["UNLocode"]: r for r in tsv(src / "ports.csv")}
        mine = tsv(spec.input_paths()["ports"])
        assert len(mine) == ports
        assert all(r == src_ports[r["UNLocode"]] for r in mine)               # source values untouched
        ends = {r["Origin"] for r in tsv(src / demand_name)} | {r["Destination"] for r in tsv(src / demand_name)}
        assert {r["UNLocode"] for r in mine} == ends                              # no unrelated port leaks in
        src_fd = {r["Vessel class"]: r for r in tsv(src / "fleet_data.csv")}
        assert {r["Vessel class"] for r in tsv(spec.input_paths()["fleet_data"])} == classes
        assert all(r == src_fd[r["Vessel class"]] for r in tsv(spec.input_paths()["fleet_data"]))

    def test_all_route_alternatives_are_preserved_and_the_model_uses_the_shortest(self):
        spec = resolve_dataset("WAF")
        alts = tsv(spec.raw_dir / "dist_dense_all_alternatives.csv")
        used = tsv(spec.input_paths()["distance"])
        assert len(alts) == 402 and len(used) == 380                           # 22 pairs have a second (Cape) record
        best = {}
        for r in alts:
            k = (r["fromUNLOCODe"], r["ToUNLOCODE"])
            best[k] = min(best.get(k, 1e18), float(r["Distance"]))
        assert all(float(r["Distance"]) == best[(r["fromUNLOCODe"], r["ToUNLOCODE"])] for r in used)
        obj = json.loads(spec.json_path.read_text(encoding="utf-8"))
        assert len(obj["distance_alternatives"]) == 22 and len(obj["canal_flags"]) == 22
        assert all(sum(r["selected"] for r in a["records"]) == 1 for a in obj["distance_alternatives"])

    def test_waf_revised_transit_variant_is_kept_but_not_used(self):
        spec = resolve_dataset("WAF")
        assert (spec.raw_dir / "Demand_WAF_tt.csv").is_file() and "Demand_WAF_tt.csv" not in spec.files.values()

    def test_baltic_has_no_canal_pair(self):
        assert len(json.loads(resolve_dataset("baltic").json_path.read_text(encoding="utf-8"))["canal_flags"]) == 0


# --------------------------------------------------------------------------------------------- isolation
class TestIsolation:
    def test_sequential_loads_in_any_order_give_the_same_problems(self):
        keys = ["WorldSmall", "baltic", "WAF", "World-500"]
        fp1 = {k: fingerprint(load_problem_json(k)[0]) for k in keys}
        fp2 = {k: fingerprint(load_problem_json(k)[0]) for k in reversed(keys)}
        fp3 = {k: fingerprint(NetworkLoader(dataset=None if k == "WorldSmall" else k).load_problem()) for k in
               ["baltic", "World-500", "WorldSmall", "WAF"]}
        assert fp1 == fp2 == fp3
        assert len(set(fp1.values())) == 4                                      # and they are four different problems

    def test_fuel_registry_follows_the_last_loaded_fleet_not_an_earlier_dataset(self):
        load_problem_json("WorldSmall")
        assert len(fuel_cost.VESSEL_FUEL_CONSUMPTION) == 6
        load_problem_json("baltic")
        assert set(fuel_cost.VESSEL_FUEL_CONSUMPTION) == {"Feeder_450", "Feeder_800"}
        load_problem_json("WorldSmall")
        assert len(fuel_cost.VESSEL_FUEL_CONSUMPTION) == 6

    def test_a_dataset_never_reads_another_datasets_csv(self, monkeypatch):
        opened = []
        real_open = builtins.open
        monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
        NetworkLoader(dataset="WAF").load_problem()
        raw = [Path(p).resolve() for p in opened if "raw" in str(p)]
        assert raw and all(p.is_relative_to(resolve_dataset("WAF").raw_dir.resolve()) for p in raw), raw

    def test_rebuild_writes_only_into_the_given_location(self, tmp_path, monkeypatch):
        """Rebuilding a dataset's JSON/manifest never touches another dataset's files (temp datasets folder)."""
        import importlib.util
        spec_ = importlib.util.spec_from_file_location("bpj", ROOT / "scripts" / "multi_dataset" / "build_problem_json.py")
        bpj = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(bpj)
        before = {k: sha256_file(resolve_dataset(k).json_path) for k in KEYS}
        monkeypatch.setattr(reg, "DATASETS_ROOT", tmp_path)
        assert bpj.build_one("baltic", replace=False, check=False) == 0
        assert sorted(p.name for p in tmp_path.iterdir()) == ["baltic_json.json", "baltic_manifest.json"]
        monkeypatch.undo()
        assert {k: sha256_file(resolve_dataset(k).json_path) for k in KEYS} == before
        assert (tmp_path / "baltic_json.json").read_bytes() == resolve_dataset("baltic").json_path.read_bytes()

    def test_rebuild_is_deterministic_and_refuses_to_replace_silently(self, tmp_path, monkeypatch):
        spec = resolve_dataset("baltic")
        a = dumps_problem(build_problem_dict(spec)[0])
        b = dumps_problem(build_problem_dict(spec)[0])
        assert a == b == spec.json_path.read_bytes()
        import importlib.util
        spec_ = importlib.util.spec_from_file_location("bpj2", ROOT / "scripts" / "multi_dataset" / "build_problem_json.py")
        bpj = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(bpj)
        monkeypatch.setattr(reg, "DATASETS_ROOT", tmp_path)
        (tmp_path / "baltic_json.json").write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit, match="--replace"):
            bpj.build_one("baltic", replace=False, check=False)
        assert (tmp_path / "baltic_json.json").read_text(encoding="utf-8") == "{}"        # untouched
        assert bpj.build_one("baltic", replace=True, check=False) == 0
        assert list((tmp_path / "_backups").iterdir())                                        # old content backed up first

    def test_a_dataset_that_fails_validation_produces_no_json(self, tmp_path, monkeypatch):
        import shutil
        import importlib.util
        raw = tmp_path / "raw_bad"
        shutil.copytree(resolve_dataset("baltic").raw_dir, raw)
        lines = (raw / "Demand_Baltic.csv").read_text(encoding="utf-8").splitlines()
        lines.append("ZZZZZ\tFIRAU\t5\t1000\t10")                              # demand endpoint that is not a port
        (raw / "Demand_Baltic.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        bad = reg.DatasetSpec(key="baltic", label="bad", kind="real_linerlib", raw_dir=raw,
                              files=dict(resolve_dataset("baltic").files), json_name="baltic_json.json")
        monkeypatch.setattr(reg, "DATASETS_ROOT", tmp_path)
        checks = validate_dataset(bad, check_json=False)
        assert summarize(checks)["blocking_failures"] >= 1
        import importlib.util as iu
        spec_ = iu.spec_from_file_location("bpj3", ROOT / "scripts" / "multi_dataset" / "build_problem_json.py")
        bpj = iu.module_from_spec(spec_)
        spec_.loader.exec_module(bpj)
        monkeypatch.setattr(bpj, "resolve_dataset", lambda k: bad)
        assert bpj.build_one("baltic", replace=False, check=False) == 1
        assert not (tmp_path / "baltic_json.json").exists()


# --------------------------------------------------------------------------------------------- WorldSmall unchanged
class TestWorldSmallUnchanged:
    FROZEN = {"Demand_WorldSmall_Fixed_Sep.csv": "fd46294e5b71bcc6", "dist_dense.csv": "8edf8cdf7a119c34",
              "fleet_WorldSmall.csv": "a8986ee2bfeda133", "fleet_data.csv": "5054eb5178cedbe2", "ports.csv": "b6c8c3b6c209222a"}

    def test_canonical_inputs_match_the_frozen_c3_hashes(self):
        raw = resolve_dataset("WorldSmall").raw_dir
        assert {n: sha256_file(raw / n)[:16] for n in self.FROZEN} == self.FROZEN

    def test_no_file_was_added_to_the_worldsmall_directory(self):
        names = {p.name for p in resolve_dataset("WorldSmall").raw_dir.iterdir()}
        assert names == {"Demand_WorldSmall_Fixed_Sep.csv", "demand_world_small.csv", "dist_dense.csv", "fleet_WorldSmall.csv",
                         "fleet_world_small.csv", "fleet_data.csv", "ports.csv"}

    def test_default_loader_is_worldsmall(self):
        problem = NetworkLoader().load_problem()
        assert (len(problem.ports), len(problem.demands), problem.fleet.total_vessels) == (47, 1764, 263)
        assert sum(len(r) for r in problem.distance_matrix.values()) == 2162

    def test_legacy_worldsmall_problem_file_is_untouched_and_still_rejected_as_production_input(self):
        legacy = ROOT / "data" / "datasets" / "worldsmall_shipping_problem.json"
        protected = (ROOT / "reports" / "multi_dataset_20261016" / "00_baseline_protect" / "copies" / "data" /
                     "datasets" / "worldsmall_shipping_problem.json")
        assert sha256_file(legacy) == sha256_file(protected)
        from src.data.network_loader import DataValidationError
        with pytest.raises(DataValidationError, match="disagrees with the canonical"):
            NetworkLoader().load_problem(legacy)

    def test_worldsmall_json_selection_rule_equals_the_first_listed_record(self):
        """The accepted file is the first listed LINERLIB record of every pair - and that is the shortest."""
        src = tsv(ROOT / "data" / "LINERLIB-master" / "data" / "dist_dense.csv")
        ws = {(r["fromUNLOCODe"], r["ToUNLOCODE"]): r for r in tsv(resolve_dataset("WorldSmall").input_paths()["distance"])}
        first = {}
        shortest = {}
        for r in src:
            k = (r["fromUNLOCODe"], r["ToUNLOCODE"])
            if k in ws:
                first.setdefault(k, r)
                shortest[k] = min(shortest.get(k, 1e18), float(r["Distance"]))
        assert all(first[k] == ws[k] for k in ws) and all(float(ws[k]["Distance"]) == shortest[k] for k in ws)
