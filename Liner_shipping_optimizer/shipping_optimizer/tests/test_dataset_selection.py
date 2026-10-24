"""Dataset registry and the dataset selection of ``tests/test_orchestrator.py``.

Covers: every choice resolves to its own folder / JSON / output directory, unknown names fail cleanly, a missing
input or JSON fails without any fallback, the interactive menu is never shown outside a terminal, the selection
reaches the loader and the output metadata, and the pre-existing WorldSmall behaviour is the default.
No optimizer run happens here (those are in the per-dataset run artifacts).
"""
import subprocess
import sys
from pathlib import Path

import pytest

import src.data.dataset_registry as reg
from src.data.dataset_registry import (DATASETS, DatasetNotAvailableError, UnknownDatasetError, list_datasets,
                                       menu_choices, resolve_dataset)
from src.data.network_loader import DataValidationError, NetworkLoader
from src.data.problem_json import ProblemJsonError, load_problem_json

import tests.test_orchestrator as orch

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["WorldSmall", "baltic", "WAF", "World-500", "World-1000"]

EXPECTED = {
    "WorldSmall": ("data/raw/WorldSmall", "worldsmall_json.json"),
    "baltic": ("data/raw/baltic", "baltic_json.json"),
    "WAF": ("data/raw/WAF", "waf_json.json"),
    "World-500": ("data/raw/World-500", "world500_json.json"),
    "World-1000": ("data/raw/World-1000", "world1000_json.json"),
}


class TestRegistry:
    def test_five_datasets_in_menu_order(self):
        assert [s.key for s in list_datasets()] == KEYS
        assert list(menu_choices()) == ["1", "2", "3", "4", "5"]

    @pytest.mark.parametrize("key", KEYS)
    def test_each_choice_resolves_to_its_own_folder_and_json(self, key):
        spec = resolve_dataset(key)
        raw, js = EXPECTED[key]
        assert spec.raw_dir == (ROOT / raw)
        assert spec.json_path == ROOT / "data" / "datasets" / js
        assert spec.manifest_path.name == js.replace("_json.json", "_manifest.json")
        assert all(p.parent == spec.raw_dir for p in spec.input_paths().values())

    def test_paths_are_pairwise_disjoint(self):
        dirs = [s.raw_dir for s in list_datasets()]
        assert len(set(dirs)) == len(dirs)
        assert len({s.json_path for s in list_datasets()}) == 5
        assert len({s.output_dir for s in list_datasets()}) == 5
        for a in list_datasets():
            for b in list_datasets():
                if a is not b:
                    assert not a.raw_dir.is_relative_to(b.raw_dir)

    @pytest.mark.parametrize("name,key", [("worldsmall", "WorldSmall"), ("WORLD_SMALL", "WorldSmall"), ("Baltic", "baltic"),
                                          ("waf", "WAF"), ("world 500", "World-500"), ("World-1000", "World-1000"),
                                          ("w500", "World-500"), ("1000", "World-1000")])
    def test_names_are_normalised(self, name, key):
        assert resolve_dataset(name).key == key

    @pytest.mark.parametrize("bad", ["", "nosuch", "world-750", "WorldLarge", "worldlarge", "large", "../WorldSmall"])
    def test_unknown_choice_fails_cleanly(self, bad):
        with pytest.raises(UnknownDatasetError, match="choose one of"):
            resolve_dataset(bad)

    def test_none_is_worldsmall_only_when_nothing_was_requested(self):
        assert resolve_dataset(None).key == "WorldSmall"

    def test_worldlarge_is_not_a_registered_dataset(self):
        assert "WorldLarge" not in DATASETS

    def test_describe_reports_paths_and_hashes(self):
        d = resolve_dataset("baltic").describe()
        assert set(d["inputs"]) == {"ports", "demand", "distance", "fleet", "fleet_data"}
        assert all(len(v["sha256"]) == 64 for v in d["inputs"].values())
        assert len(d["json"]["sha256"]) == 64 and d["dataset"] == "baltic"


class TestNoFallback:
    def test_missing_input_file_names_the_file_and_never_substitutes(self, tmp_path, monkeypatch):
        spec = reg.DatasetSpec(key="ghost", label="ghost", kind="real_linerlib", raw_dir=tmp_path / "ghost",
                               files={"ports": "ports.csv", "demand": "d.csv", "distance": "x.csv",
                                      "fleet": "f.csv", "fleet_data": "fd.csv"}, json_name="ghost_json.json")
        with pytest.raises(DatasetNotAvailableError, match="No fallback"):
            spec.require_inputs()
        with pytest.raises(FileNotFoundError, match="No fallback to another dataset"):
            NetworkLoader(dataset=spec).load_ports()

    def test_missing_json_fails_without_falling_back_to_worldsmall(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reg, "DATASETS_ROOT", tmp_path)          # an empty datasets folder
        with pytest.raises(DatasetNotAvailableError, match="canonical problem file not found"):
            load_problem_json("baltic")
        with pytest.raises(ProblemJsonError):
            load_problem_json("WAF", path=tmp_path / "waf_json.json")

    def test_invalid_json_is_an_error(self, tmp_path):
        bad = tmp_path / "baltic_json.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(ProblemJsonError, match="invalid JSON"):
            load_problem_json("baltic", path=bad)

    def test_json_of_another_dataset_is_rejected(self):
        with pytest.raises(ProblemJsonError, match="identity mismatch"):
            load_problem_json("baltic", path=resolve_dataset("WAF").json_path)

    @pytest.mark.parametrize("legacy", ["worldsmall_shipping_problem.json", "large_shipping_problem.json"])
    def test_historical_problem_files_are_never_loaded(self, legacy):
        with pytest.raises(ProblemJsonError, match="not a canonical"):
            load_problem_json("WorldSmall", path=ROOT / "data" / "datasets" / legacy)

    def test_other_dataset_files_are_rejected_by_the_loader_location_guard(self):
        ws_ports = resolve_dataset("WorldSmall").input_paths()["ports"]
        with pytest.raises(DataValidationError, match="reads only baltic"):
            NetworkLoader(dataset="baltic").load_ports(ws_ports)
        baltic_ports = resolve_dataset("baltic").input_paths()["ports"]
        with pytest.raises(DataValidationError, match="reads only WorldSmall"):
            NetworkLoader().load_ports(baltic_ports)


class TestSelectionLogic:
    def test_interactive_session_is_false_under_pytest(self):
        assert orch.interactive_session() is False

    def test_no_request_and_no_terminal_runs_worldsmall_without_prompting(self):
        def boom(*a, **k):
            raise AssertionError("the menu must not be shown")
        assert orch.select_dataset(None, interactive=False, input_fn=boom).key == "WorldSmall"
        assert orch.select_dataset(None, input_fn=boom).key == "WorldSmall"          # interactive_session() is False here

    def test_requested_dataset_never_prompts(self):
        def boom(*a, **k):
            raise AssertionError("the menu must not be shown")
        for k in KEYS:
            assert orch.select_dataset(k, interactive=True, input_fn=boom).key == k

    def test_menu_accepts_numbers_and_names_and_repeats_on_a_bad_answer(self):
        answers = iter(["9", "nosuch", "3"])
        lines = []
        spec = orch.prompt_for_dataset(input_fn=lambda _: next(answers), out=lines.append)
        assert spec.key == "WAF"
        assert any("unknown dataset" in ln for ln in lines)
        assert [orch.prompt_for_dataset(input_fn=lambda _, v=v: v, out=lambda *_: None).key
                for v in ("1", "2", "4", "5", "baltic")] == ["WorldSmall", "baltic", "World-500", "World-1000", "baltic"]

    def test_menu_aborts_on_closed_input_instead_of_defaulting(self):
        def eof(_):
            raise EOFError
        with pytest.raises(SystemExit, match="no dataset selected"):
            orch.prompt_for_dataset(input_fn=eof, out=lambda *_: None)

    def test_unknown_dataset_through_the_cli_exits_2(self):
        assert orch.main(["--dataset", "nosuch", "--non-interactive"]) == 2

    def test_cli_in_a_subprocess_never_blocks_and_rejects_unknown(self):
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_orchestrator.py"), "--dataset", "nosuch"],
                           capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, cwd=str(ROOT))
        assert r.returncode == 2 and "unknown dataset" in r.stderr

    def test_list_option(self, capsys):
        assert orch.main(["--list"]) == 0
        out = capsys.readouterr().out
        for k in KEYS:
            assert k in out


class TestOutputIsolation:
    def test_worldsmall_keeps_its_legacy_artifact_locations(self):
        o = orch.output_locations(resolve_dataset("WorldSmall"))
        assert o["pipeline_output"] == ROOT / "pipeline_output.json"
        assert o["dir"] == ROOT and o["frontend_public"] == ROOT / "frontend" / "public" / "pipeline_output.json"

    @pytest.mark.parametrize("key", ["baltic", "WAF", "World-500", "World-1000"])
    def test_other_datasets_write_only_below_their_own_directory(self, key):
        o = orch.output_locations(resolve_dataset(key))
        run_dir = ROOT / "reports" / "dataset_runs" / key
        assert o["dir"] == run_dir and o["pipeline_output"] == run_dir / "pipeline_output.json"
        assert o["frontend_public"] is None and o["frontend_dist"] is None
        assert o["pipeline_output"] != ROOT / "pipeline_output.json"

    def test_output_directories_are_distinct(self):
        dirs = {orch.output_locations(s)["run_dir"] for s in list_datasets()}
        assert len(dirs) == 5


class TestSelectionReachesLoaderAndOutputs:
    @pytest.mark.parametrize("key", ["WorldSmall", "baltic", "WAF"])
    def test_selected_dataset_is_what_gets_loaded(self, key):
        problem, info = orch.load_selected_problem(resolve_dataset(key), "json")
        spec = resolve_dataset(key)
        assert problem.dataset_key == key
        assert info["json"]["dataset"] == key and Path(info["json"]["path"]) == spec.json_path
        assert info["counts"]["ports"] == len(problem.ports)
        man = __import__("json").loads(spec.manifest_path.read_text(encoding="utf-8"))
        assert info["counts"]["ports"] == man["counts"]["ports"] and info["counts"]["vessels"] == man["counts"]["vessels_total"]
        assert {p.id for p in problem.ports} == {r.split("\t")[0] for r in
                                                 spec.input_paths()["ports"].read_text(encoding="utf-8").splitlines()[1:]}

    def test_csv_source_path_gives_the_same_problem(self):
        a, _ = orch.load_selected_problem(resolve_dataset("baltic"), "json")
        b, _ = orch.load_selected_problem(resolve_dataset("baltic"), "csv")
        from src.data.problem_json import problem_differences
        assert problem_differences(a, b) == []

    def test_a_tampered_json_is_caught_by_the_csv_cross_check(self, tmp_path, monkeypatch):
        import json
        spec = resolve_dataset("baltic")
        obj = json.loads(spec.json_path.read_text(encoding="utf-8"))
        obj["demands"][0]["weekly_teu"] += 1.0
        monkeypatch.setattr(reg, "DATASETS_ROOT", tmp_path)
        (tmp_path / "baltic_json.json").write_text(json.dumps(obj), encoding="utf-8")
        with pytest.raises(orch.DatasetIntegrityError, match="does not reproduce its CSV package"):
            orch.load_selected_problem(spec, "json")

    def test_oracle_canal_input_is_per_dataset_and_cached_per_dataset(self):
        ws_flags, _ = orch._raw_canal_and_leg_draft("WorldSmall")
        waf_flags, _ = orch._raw_canal_and_leg_draft("WAF")
        bal_flags, _ = orch._raw_canal_and_leg_draft("baltic")
        assert len(waf_flags) == 22 and len(bal_flags) == 0 and len(ws_flags) > 100
        assert ws_flags is not waf_flags
        assert orch._raw_canal_and_leg_draft("WAF")[0] is waf_flags        # cached per dataset

    def test_outcome_policy_asserts_only_for_the_reference_case(self):
        before = list(orch._OUTCOME_NOTES)
        try:
            orch._OUTCOME_STRICT = False
            assert orch.assert_outcome(False, "x") is False        # reported, not raised, not counted as a failure
            assert orch._OUTCOME_NOTES[-1]["outcome_not_met"] == "x"
        finally:
            orch._OUTCOME_STRICT = True
            orch._OUTCOME_NOTES[:] = before


class TestWorldSmallRemainsTheDefault:
    def test_pytest_entry_point_defaults_to_worldsmall(self, monkeypatch):
        monkeypatch.delenv("LINER_DATASET", raising=False)
        called = {}
        monkeypatch.setattr(orch, "run_orchestrator_test", lambda spec, source="json": called.setdefault("k", spec.key))
        orch.test_orchestrator()
        assert called["k"] == "WorldSmall"

    def test_env_selection_is_explicit_and_validated(self, monkeypatch):
        called = {}
        monkeypatch.setattr(orch, "run_orchestrator_test", lambda spec, source="json": called.setdefault("k", spec.key))
        monkeypatch.setenv("LINER_DATASET", "WAF")
        orch.test_orchestrator()
        assert called["k"] == "WAF"
        monkeypatch.setenv("LINER_DATASET", "nosuch")
        with pytest.raises(UnknownDatasetError):
            orch.test_orchestrator()
