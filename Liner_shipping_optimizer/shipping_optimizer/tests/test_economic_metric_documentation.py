"""Documentation-validation tests for the Phase MA economic-metric integrity audit.

SCOPE AND INTENT
----------------
These tests validate that the audit's DOCUMENTATION is faithful to the code and
to the recorded artifact. They do not validate the system's economics, and they
are NOT a substitute for economic tests that the project does not currently
have (see `test_no_economic_assertions_exist` for the record).

They are deliberately adversarial toward the documentation: if a cited line
number drifts, if a formula loses its evidence, if a claimed reconciliation
stops holding, or if an RL cell loses its RL-REF provenance, these tests fail.

THEY MUST NEVER BE WEAKENED TO MAKE THE DOCUMENTATION PASS. If a test here
fails, the correct response is to re-verify the underlying claim against the
source and either correct the document or correct the code - in the latter case,
under an explicitly authorised repair phase, not by relaxing the assertion.

These tests do not modify, and must not be modified to accommodate, the
scientific test suite. `tests/test_worldsmall_integration.py` pins the FFE->TEU
x2 conversion and the DEMAND_SCALE x6 factor as expected behaviour; those
assertions are load-bearing for the current economics and are left untouched.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "pipeline_output.json"
DOC = ROOT / "MULTI_AGENT_ARCHITECTURE_FORMULATIONS_ECONOMIC_METRIC_INTEGRITY.md"

FORMULA_INDEX = ROOT / "MULTI_AGENT_FORMULA_INDEX.json"
METRIC_MATRIX = ROOT / "MULTI_AGENT_ECONOMIC_METRIC_MATRIX.json"
METRIC_LINEAGE = ROOT / "MULTI_AGENT_METRIC_LINEAGE.json"
RL_MATRIX = ROOT / "MULTI_AGENT_RL_COMPARISON_MATRIX.json"
DATASET_COMPARABILITY = ROOT / "MULTI_AGENT_DATASET_COMPARABILITY.json"
PAPER_TRACEABILITY = ROOT / "MULTI_AGENT_PAPER_TRACEABILITY.json"
DEP_MAP = ROOT / "MULTI_AGENT_FILE_DEPENDENCY_MAP.json"

ALL_ARTIFACTS = [FORMULA_INDEX, METRIC_MATRIX, METRIC_LINEAGE, RL_MATRIX,
                 DATASET_COMPARABILITY, PAPER_TRACEABILITY, DEP_MAP]

CLASSIFICATION_VOCABULARY = {
    "IMPLEMENTED DEFINITION", "PAPER DEFINITION", "DATASET FIELD", "DERIVED METRIC",
    "ENGINEERING CONVENTION", "ASSUMPTION", "REPORTED METRIC", "NOT IMPLEMENTED",
}
GRADE_VOCABULARY = {"GREEN", "YELLOW", "RED", "GRAY"}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _lines(rel):
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()


# --------------------------------------------------------------------------- #
# 1. Artifact presence and parseability                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", ALL_ARTIFACTS, ids=lambda p: p.name)
def test_artifact_exists_and_parses(path):
    assert path.exists(), f"missing audit artifact: {path.name}"
    data = _load(path)
    assert isinstance(data, dict), f"{path.name} must be a JSON object"


def test_artifact_declares_its_generator():
    for path in ALL_ARTIFACTS:
        data = _load(path)
        assert data.get("generated_by"), f"{path.name} must record its generator script"


# --------------------------------------------------------------------------- #
# 2. Formula index: every citation must resolve to the cited line               #
# --------------------------------------------------------------------------- #
def test_every_formula_has_evidence():
    index = _load(FORMULA_INDEX)
    assert index["formulas"], "formula index is empty"
    for formula in index["formulas"]:
        assert formula.get("id"), "formula without an id"
        assert formula.get("statement"), f"{formula['id']} has no statement"
        assert formula.get("evidence"), f"{formula['id']} has no evidence"
        assert formula.get("classification") in CLASSIFICATION_VOCABULARY, (
            f"{formula['id']} classification {formula.get('classification')!r} "
            f"is outside the mandated vocabulary")


def test_every_formula_citation_resolves():
    """The core discipline: a `file:line` citation must still say what we claim."""
    index = _load(FORMULA_INDEX)
    failures = []
    for formula in index["formulas"]:
        for ev in formula["evidence"]:
            rel, line_no, expect = ev["file"], ev["line"], ev["expect"]
            target = ROOT / rel
            if not target.exists():
                failures.append(f"{formula['id']}: missing file {rel}")
                continue
            lines = _lines(rel)
            if line_no < 1 or line_no > len(lines):
                failures.append(f"{formula['id']}: {rel}:{line_no} out of range "
                                f"(file has {len(lines)} lines)")
                continue
            if expect not in lines[line_no - 1]:
                failures.append(
                    f"{formula['id']}: {rel}:{line_no} does not contain {expect!r}\n"
                    f"          actual: {lines[line_no - 1].strip()[:110]!r}")
    assert not failures, "citation drift detected:\n" + "\n".join(failures)


def test_formula_ids_are_unique():
    index = _load(FORMULA_INDEX)
    ids = [f["id"] for f in index["formulas"]]
    assert len(ids) == len(set(ids)), "duplicate formula ids"


# --------------------------------------------------------------------------- #
# 3. Arithmetic reproduction from the recorded artifact                         #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def output():
    if not ARTIFACT.exists():
        pytest.skip("pipeline_output.json not present")
    return _load(ARTIFACT)


def test_summary_cost_components_sum_to_total_cost(output):
    """F-17: the four components sum to total_cost exactly."""
    sm = output["summary_metrics"]
    total = (sm["operating_cost"] + sm["fuel_cost"]
             + sm["port_cost"] + sm["transship_cost"])
    assert abs(total - sm["total_cost"]) < 1e-6, (
        f"cost components {total} != total_cost {sm['total_cost']}")


def test_revenue_minus_total_cost_equals_profit(output):
    """F-17: the accounting identity holds to IEEE-754 rounding."""
    sm = output["summary_metrics"]
    residual = abs(sm["revenue"] - sm["total_cost"] - sm["weekly_profit"])
    assert residual < 1e-3, (
        f"revenue - total_cost - weekly_profit residual {residual} exceeds "
        f"floating-point tolerance")


def test_profit_margin_pct_has_one_definition(output):
    """F-15 REPAIRED (tripwire flipped deliberately, as its own docstring required).

    Before the repair ``decision_output.global_metrics.profit_margin_pct`` used the
    vessel-hire-only denominator (about 26 %) while the ledger margin on revenue was
    about 11 %.  Now there is ONE definition: profit / revenue on the all-in cost
    basis.  The vessel-hire-only ratio is kept only as the diagnostic
    ``vessel_hire_cost``; it is never again reported as the margin.
    """
    sm = output["summary_metrics"]
    gm = output["decision_output"]["global_metrics"]
    on_total_cost = sm["weekly_profit"] / (sm["weekly_profit"] + sm["total_cost"]) * 100
    on_operating_cost = (sm["weekly_profit"]
                         / (sm["weekly_profit"] + sm["operating_cost"]) * 100)
    assert gm["profit_margin_pct"] is not None, (
        "global_metrics.profit_margin_pct is None although the run is verified")
    assert abs(gm["profit_margin_pct"] - on_total_cost) < 0.05, (
        "global_metrics.profit_margin_pct no longer equals profit/(profit+total_cost); "
        "the F-15 repair regressed")
    assert abs(gm["profit_margin_pct"] - on_operating_cost) > 1.0, (
        "global_metrics.profit_margin_pct has fallen back to the vessel-hire-only "
        "denominator; the F-15 repair regressed")
    ledger = output["network_ledger"]["weekly_usd"]["profit_margin_on_revenue"]
    assert ledger is not None and abs(gm["profit_margin_pct"] - 100.0 * ledger) < 0.05, (
        "global_metrics.profit_margin_pct disagrees with the independent ledger margin")


def test_total_cost_field_is_unambiguous(output):
    """F-15 REPAIRED: ``total_cost`` now has one value in the whole artifact, and the
    vessel-hire component is exposed under its own name."""
    sm = output["summary_metrics"]
    gm = output["decision_output"]["global_metrics"]
    assert abs(sm["total_cost"] - gm["total_cost"]) < 1.0, (
        "summary_metrics.total_cost and global_metrics.total_cost diverge again; "
        "the F-15 repair regressed")
    assert abs(gm["vessel_hire_cost"] - sm["operating_cost"]) < 1.0, (
        "global_metrics.vessel_hire_cost is not the vessel-hire component")
    assert gm["total_cost"] > gm["vessel_hire_cost"], (
        "all-in cost must exceed its vessel-hire component (fuel and port costs are > 0)")
    ledger = output["network_ledger"]["weekly_usd"]
    assert abs(gm["total_cost"] - ledger["total_operating_cost"]) < 1.0


def test_regional_coverage_is_not_clamped(output):
    """F-16 REPAIRED: every region reports coverage = satisfied / its true demand
    (no clamp to 100) and satisfied + unserved partitions that demand exactly.
    The numbers come from the verified network ledger, not from each region's
    own MILP."""
    for r in output["regional_results"]:
        tot = r["total_demand"]
        if tot <= 0:
            continue
        assert abs(r["satisfied_demand"] + r["unserved_demand"] - tot) < 1e-6 * max(1.0, tot), (
            f"{r['region']}: satisfied + unserved is not a partition of its demand")
        assert abs(r["coverage_percent"] - r["satisfied_demand"] / tot * 100) < 0.01, (
            f"{r['region']}: coverage_percent is not satisfied / total_demand")


def test_satisfied_plus_unserved_equals_true_demand(output):
    """F-16 REPAIRED: satisfied + unserved is a partition of the true demand."""
    sm = output["summary_metrics"]
    true_demand = sum(r["total_demand"] for r in output["regional_results"])
    assert abs((sm["satisfied_demand"] + sm["unserved_demand"]) - true_demand)         < 1e-6 * max(1.0, true_demand), (
        "satisfied+unserved no longer equals true demand; the F-16 repair regressed")


def test_summary_coverage_denominator_is_true_demand(output):
    """F-16 REPAIRED: summary coverage is satisfied / true demand."""
    sm = output["summary_metrics"]
    true_demand = sum(r["total_demand"] for r in output["regional_results"])
    assert abs(sm["coverage"] - sm["satisfied_demand"] / true_demand * 100) < 0.01


def test_service_record_count_matches_headline(output):
    """F-25 REPAIRED: the enumerated service records are the headline count."""
    sm = output["summary_metrics"]
    assert len(output["selected_services"]) == sm["total_services"], (
        "service records no longer match total_services; the F-25 repair regressed")


# --------------------------------------------------------------------------- #
# 4. The FFE -> TEU unit distortion                                             #
# --------------------------------------------------------------------------- #
def test_demand_file_is_byte_identical_to_rl_master():
    """F-01: MA copies the LINERLIB demand file verbatim; distortion is downstream."""
    import hashlib
    # Canonical WorldSmall demand file. The former flat path data/raw/demand_world_small.csv
    # no longer exists; this file is byte-identical to it (same md5 pin below).
    path = ROOT / "data" / "raw" / "WorldSmall" / "Demand_WorldSmall_Fixed_Sep.csv"
    assert path.is_file(), f"canonical WorldSmall demand file missing: {path}"
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    assert digest == "68f75334f57975c19b8a6b1a3da199ea", (
        f"WorldSmall demand file changed (md5 {digest}); the dataset comparability "
        f"findings in MULTI_AGENT_DATASET_COMPARABILITY.json must be re-verified")


def test_revenue_is_four_times_the_raw_csv_product():
    """F-01: volume AND unit rate are each scaled, so revenue scales by 4.

    This is the single largest distortion in the economic model and it is
    undocumented in every normative spec.
    """
    import csv
    path = ROOT / "data" / "raw" / "WorldSmall" / "Demand_WorldSmall_Fixed_Sep.csv"
    assert path.is_file(), f"canonical WorldSmall demand file missing: {path}"
    raw = 0.0
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            raw += float(row["FFEPerWeek"]) * float(row["Revenue_1"])

    ds_path = ROOT / "data" / "datasets" / "worldsmall_shipping_problem.json"
    if not ds_path.exists():
        pytest.skip("WorldSmall JSON dataset not present")
    data = _load(ds_path)
    baked = sum(d["weekly_teu"] * d["revenue_per_teu"] for d in data["demands"])

    ratio = baked / raw
    assert abs(ratio - 4.0) < 0.001, (
        f"revenue scaling ratio is {ratio}, expected 4.0; the F-01 finding has "
        f"changed and the document must be updated")


def test_ffe_to_teu_table_has_unreachable_keys():
    """F-01: two table keys contain a literal space and can never match."""
    src = (ROOT / "src" / "data" / "network_loader.py").read_text(encoding="utf-8")
    assert '"CNSHA-USA NY"' in src and '"JPTYO-USA NY"' in src, (
        "the malformed FFE->TEU keys are gone; re-verify the default-2.0 share "
        "claim in the document")


def test_demand_scale_still_applies_unconditionally():
    """F-02: the x6 scale is applied to whichever JSON is loaded, with no
    instance detection in NetworkLoader."""
    lines = _lines("src/data/network_loader.py")
    assert any("DEMAND_SCALE = 6" in l for l in lines), (
        "DEMAND_SCALE = 6 not found; the loader's second demand path has changed")


# --------------------------------------------------------------------------- #
# 5. LLM influence: the weight chain terminates unused                          #
# --------------------------------------------------------------------------- #
def test_production_objective_mode_is_profit_first():
    """F-23: the branch that reads problem weights is the unreachable one."""
    lines = _lines("src/config/optimizer_config.py")
    assert any('objective_mode: str = "profit_first"' in l for l in lines), (
        "objective_mode is no longer profit_first; the weight-inertness finding "
        "(F-23) must be re-derived")


def test_profit_first_weights_are_hardcoded_constants():
    src = (ROOT / "src" / "optimization" / "normalization.py").read_text(encoding="utf-8")
    assert "PROFIT_FIRST_WEIGHTS" in src
    assert "'profit': 10.0" in src, (
        "PROFIT_FIRST_WEIGHTS changed; re-derive the F-23 inertness chain")


def test_service_ga_reads_problem_weights():
    """Documented as read (service_ga.py:83-85) but consumed only by the
    unreachable 'legacy' branch. If this read disappears, F-23 is stale."""
    src = (ROOT / "src" / "optimization" / "service_ga.py").read_text(encoding="utf-8")
    assert 'getattr(problem,"profit_weight"' in src or \
           'getattr(problem, "profit_weight"' in src, (
        "ServiceGA no longer reads problem.profit_weight; F-23 must be re-derived")


# --------------------------------------------------------------------------- #
# 6. Fleet limit inconsistency                                                  #
# --------------------------------------------------------------------------- #
def test_milp_has_no_phantom_default_fleet():
    """F-08 REPAIRED (Task 3/5): HubMILP no longer defaults to a 300-vessel fleet.
    ``fleet_size=None`` means "the real per-class inventory of problem.fleet"."""
    lines = _lines("src/optimization/hub_milp.py")
    assert any("fleet_size: Optional[int]" in l and "None" in l for l in lines), (
        "HubMILP's fleet_size default is no longer None; re-verify the fleet-limit repair")
    assert not any("fleet_size: int = 300" in l for l in lines)


def test_regional_agent_leaves_fleet_to_the_problem_inventory():
    """F-08 REPAIRED: the regional agent does not invent a fleet cap; the limits are
    the per-class inventories of ``problem.fleet`` (enforced in the network MILP)."""
    lines = _lines("src/agents/regional_agent.py")
    milp_calls = [(i + 1, l) for i, l in enumerate(lines) if "HubMILP(" in l]
    assert milp_calls, "HubMILP construction not found in regional_agent"
    for line_no, _ in milp_calls:
        window = " ".join(lines[line_no - 1: line_no + 14])
        assert "fleet_size=300" not in window.replace(" ", ""), (
            f"regional_agent.py:{line_no} passes a hard-coded 300-vessel fleet")


def test_worldsmall_fleet_totals_263():
    """The authoritative fleet is the loaded inventory (263 vessels); the 300 literal
    that used to cap FrequencyGA is gone."""
    sys.path.insert(0, str(ROOT))
    from src.data.network_loader import NetworkLoader
    fleet = NetworkLoader().load_fleet()
    assert sum(int(c.quantity) for c in fleet.classes) == 263
    lines = _lines("src/optimization/frequency_ga.py")
    assert not any("300  # legacy default" in l for l in lines), (
        "FrequencyGA has a hard-coded 300-vessel default again")


# --------------------------------------------------------------------------- #
# 7. Alpha disagreement between layers                                         #
# --------------------------------------------------------------------------- #
def test_ga_and_milp_alpha_disagree():
    """F-12: GA prices uncovered demand at 50 USD/TEU, the MILP at 300."""
    sga = (ROOT / "src" / "optimization" / "service_ga.py").read_text(encoding="utf-8")
    milp = (ROOT / "src" / "optimization" / "hub_milp.py").read_text(encoding="utf-8")
    assert "alpha_unserved" in sga
    assert "alpha_unserved: float" in milp and "300.0" in milp


def test_frequency_ga_fitness_is_net_of_fuel():
    """F-07 REPAIRED: FrequencyGA no longer returns revenue-only fitness. Its fitness
    subtracts ``ServiceModel.weekly_fixed_cost(f)`` = vessel hire + rotation fuel +
    port calls (src/network/economics.py)."""
    src = (ROOT / "src" / "optimization" / "frequency_ga.py").read_text(encoding="utf-8")
    assert "weekly_fixed_cost" in src, "FrequencyGA fitness no longer subtracts the full service cost"
    assert not [l for l in _lines("src/optimization/frequency_ga.py")
                if l.strip().startswith("return revenue")], (
        "FrequencyGA fitness is revenue-only again (F-07 regression)")
    econ = (ROOT / "src" / "network" / "economics.py").read_text(encoding="utf-8")
    assert "def weekly_fixed_cost" in econ and "fuel" in econ


# --------------------------------------------------------------------------- #
# 8. Unused dataset vocabulary                                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field", [
    "tc_rate_daily", "panama_fee", "suez_fee",
    "idle_consumption_tons_per_day", "bunker_consumption_tons_per_day",
])
def test_fleet_cost_fields_are_unread_outside_the_loader(field):
    """F-04 (updated): the LINERLIB cost vocabulary is consumed ONLY by the sanctioned
    canonical economic modules. ``panama_fee`` / ``suez_fee`` remain unread (no canal
    routing in the data), so any new reader must be a deliberate, reviewed decision.
    """
    # Deliberate repairs: modules that are SANCTIONED to read a field. Task 3 prices a
    # candidate's vessel cost from the class's TC rate in the feasibility module.
    # Readers of the LINERLIB cost vocabulary are now confined to the canonical economic
    # modules: the service model, the independent ledger, the feasibility module and the
    # fleet-derived fuel table. Anything else reading these fields is a second source.
    _econ = {"src/network/economics.py", "src/network/ledger.py"}
    sanctioned = {
        "tc_rate_daily": _econ | {"src/services/service_feasibility.py"},
        "idle_consumption_tons_per_day": _econ | {"src/utils/fuel_cost.py"},
        "bunker_consumption_tons_per_day": _econ | {"src/utils/fuel_cost.py"},
    }
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel == "src/data/network_loader.py" or rel == "src/optimization/data.py":
            continue
        if "__pycache__" in rel:
            continue
        if rel in sanctioned.get(field, ()):
            continue
        if field in path.read_text(encoding="utf-8", errors="replace"):
            offenders.append(rel)
    assert not offenders, (
        f"{field} is now read outside the loader by: {offenders}. "
        f"F-04 (unused fleet cost vocabulary) is stale.")


def test_bunker_price_is_hardcoded():
    lines = _lines("src/utils/fuel_cost.py")
    assert any("600.0" in l for l in lines), (
        "the hardcoded bunker price changed; F-05 must be re-derived")


# --------------------------------------------------------------------------- #
# 9. Reproducibility                                                            #
# --------------------------------------------------------------------------- #
#: Task 17 (campaign 2026-10-12): seeding exists in ONE place, ``src/utils/rng.py``, and only acts when
#: ``LINER_SEED`` is set (unset = the process-global generators, i.e. the behaviour the F-21/F-28
#: findings describe).  Any other file that seeds or builds a generator is still a finding that must be
#: re-derived.  Behaviour of the module itself: tests/test_rng_control.py.
_SEEDING_ALLOWED = {"src/utils/rng.py"}


def test_no_random_seeding_in_production_code():
    """F-21/F-28: runs cannot be reproduced. If seeding has been added OUTSIDE the one opt-in
    module (``src/utils/rng.py``, ``LINER_SEED``), this test fails and must be updated in the same
    commit."""
    seeds = []
    for sub in ("src", "scripts"):
        for path in (ROOT / sub).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "__pycache__" in rel or rel in _SEEDING_ALLOWED:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pat in (r"\brandom\.seed\s*\(", r"\bnp\.random\.seed\s*\(",
                        r"\bdefault_rng\s*\(", r"\bRandomState\s*\("):
                if re.search(pat, text):
                    seeds.append(f"{rel}: {pat}")
    assert not seeds, (
        f"seeding has been added at {seeds}; the reproducibility findings "
        f"(F-21, F-28) must be re-derived")


def test_artifact_carries_no_provenance_stamp():
    """F-28: the artifact records no seed, timestamp, commit or input hash."""
    raw = ARTIFACT.read_text(encoding="utf-8")
    for marker in ("experiment_id", "run_id", "git_commit", "schema_version",
                   "input_hash", "random_seed"):
        assert marker not in raw, (
            f"the artifact now carries {marker!r}; the reproducibility finding "
            f"(F-28) must be re-derived")


# --------------------------------------------------------------------------- #
# 10. RL comparison discipline                                                  #
# --------------------------------------------------------------------------- #
def test_every_rl_cell_carries_rl_ref_provenance():
    """Spec section 18: no comparability may be asserted from a shared name."""
    matrix = _load(RL_MATRIX)
    assert matrix["comparisons"], "RL comparison matrix is empty"
    for cell in matrix["comparisons"]:
        rl = cell["rl"]
        assert rl["provenance"] == "RL-REF", (
            f"{cell['metric']}: RL cell must cite RL-REF, not primary evidence")
        assert rl["is_verified"] is False, (
            f"{cell['metric']}: the RL source does not exist in this repository; "
            f"no RL cell may claim independent verification")
        assert rl["rl_ref_section"], f"{cell['metric']}: RL cell lacks a section cite"


def test_rl_grades_use_the_mandated_vocabulary():
    matrix = _load(RL_MATRIX)
    for cell in matrix["comparisons"]:
        assert cell["rl"]["comparability"] in GRADE_VOCABULARY, (
            f"{cell['metric']}: grade {cell['rl']['comparability']!r} is outside "
            f"{sorted(GRADE_VOCABULARY)}")


def test_rl_comparisons_apply_the_six_criterion_test():
    matrix = _load(RL_MATRIX)
    expected = {"definition", "units", "term_membership",
                "demand_basis", "fleet_basis", "distance_basis"}
    for cell in matrix["comparisons"]:
        assert set(cell["criterion_test"]) == expected, (
            f"{cell['metric']}: criterion test must name all six criteria")


def test_no_verdict_ranking_language_in_rl_matrix():
    """Spec section 37: no scores, rankings, winners or superiority claims."""
    forbidden = ("better", "worse", "best", "worst", "winner", "loser",
                 "superior", "outperform", "rank ")
    raw = RL_MATRIX.read_text(encoding="utf-8").lower()
    for word in forbidden:
        assert word not in raw, (
            f"the RL comparison matrix contains ranking language ({word!r}); "
            f"comparability must not be expressed as preference")


def test_grade_summary_matches_the_comparisons():
    matrix = _load(RL_MATRIX)
    computed = {}
    for cell in matrix["comparisons"]:
        g = cell["rl"]["comparability"]
        computed[g] = computed.get(g, 0) + 1
    for grade in GRADE_VOCABULARY:
        expected = computed.get(grade, 0)
        assert matrix["grade_summary"].get(grade) == expected, (
            f"grade_summary[{grade}] disagrees with the comparison rows")


# --------------------------------------------------------------------------- #
# 11. Dataset comparability                                                    #
# --------------------------------------------------------------------------- #
def test_dataset_comparability_records_the_unit_reconciliation():
    data = _load(DATASET_COMPARABILITY)
    unit = data["unit_reconciliation"]
    assert unit["measured"]["ratio"] == 4.0
    assert unit["rl_unit"].startswith("unknown"), (
        "the RL unit basis is NOT ESTABLISHED and must be recorded as such "
        "rather than asserted")


def test_dataset_comparability_grades_are_justified():
    data = _load(DATASET_COMPARABILITY)
    for entry in data["comparability_matrix"]:
        assert entry["status"] in GRADE_VOCABULARY
        assert entry.get("basis"), f"{entry['dimension']} has no stated basis"


# --------------------------------------------------------------------------- #
# 12. Metric matrix internal consistency                                       #
# --------------------------------------------------------------------------- #
def test_metric_matrix_classifications_are_in_vocabulary():
    matrix = _load(METRIC_MATRIX)
    for metric in matrix["metrics"]:
        assert metric["class"] in CLASSIFICATION_VOCABULARY, (
            f"{metric['metric']}: classification {metric['class']!r} is outside "
            f"the mandated vocabulary")
        assert metric.get("unit"), f"{metric['metric']} declares no unit"


def test_metric_matrix_declares_non_reconciling_metrics(output):
    matrix = _load(METRIC_MATRIX)
    flagged = {m["metric"] for m in matrix["metrics"] if m["reconciles"] is False}
    for name in ("total_cost", "profit_margin_pct", "coverage"):
        assert name in flagged, (
            f"{name} must be recorded as non-reconciling; the matrix is stale")


def test_metric_lineage_stages_are_labelled():
    lineage = _load(METRIC_LINEAGE)
    valid = CLASSIFICATION_VOCABULARY | {"IMPLEMENTED DEFINITION"}
    for entry in lineage["lineage"]:
        assert entry["path"], f"{entry['metric']} has an empty lineage"
        for stage in entry["path"]:
            assert stage["stage"] in valid, (
                f"{entry['metric']}: lineage stage {stage['stage']!r} is "
                f"outside the vocabulary")
            assert stage["artifact"], f"{entry['metric']}: a lineage stage names no artifact"


# --------------------------------------------------------------------------- #
# 13. Dependency map                                                            #
# --------------------------------------------------------------------------- #
def test_dependency_map_totals_are_self_consistent():
    dep = _load(DEP_MAP)
    totals = dep["totals"]
    assert totals["files"] == len(dep["files"])
    assert totals["lines"] == sum(f["lines"] for f in dep["files"].values())
    assert totals["classes"] == sum(len(f["classes"]) for f in dep["files"].values())
    assert totals["functions"] == sum(len(f["functions"]) for f in dep["files"].values())
    assert totals["internal_import_edges"] == len(dep["edges"])


def test_dependency_edges_reference_known_files():
    dep = _load(DEP_MAP)
    known = set(dep["files"])
    for edge in dep["edges"]:
        assert edge["source"] in known, f"edge source {edge['source']} not scanned"
        assert edge["target"] in known, f"edge target {edge['target']} not scanned"
        assert edge["source"] != edge["target"], "self-edge in the import graph"


def test_economic_core_is_present_in_the_dependency_graph():
    """The modules the economics depend on must be in the scanned graph, or the
    document's architecture claims rest on an incomplete map."""
    dep = _load(DEP_MAP)
    required = [
        "src/optimization/hub_milp.py",
        "src/optimization/service_ga.py",
        "src/optimization/frequency_ga.py",
        "src/optimization/hierarchical_ga.py",
        "src/utils/fuel_cost.py",
        "src/data/network_loader.py",
        "src/agents/orchestrator_agent.py",
        "src/agents/regional_agent.py",
    ]
    missing = [r for r in required if r not in dep["files"]]
    assert not missing, f"economic core missing from the dependency map: {missing}"


# --------------------------------------------------------------------------- #
# 14. The main document                                                         #
# --------------------------------------------------------------------------- #
def test_main_document_exists_with_required_sections():
    if not DOC.exists():
        pytest.fail(f"main deliverable missing: {DOC.name}")
    text = DOC.read_text(encoding="utf-8")
    for heading in ("## 1.", "## 10.", "## 20.", "## 30.",
                    "Appendix A", "Appendix F"):
        assert heading in text, f"main document lacks {heading}"


def test_main_document_defines_the_source_hierarchy():
    text = DOC.read_text(encoding="utf-8")
    for tag in ("SRC", "DATA", "EXEC", "RL-REF", "NOT ESTABLISHED"):
        assert tag in text, f"main document never uses the {tag} source tag"


def test_main_document_records_the_llm_influence_verdict():
    text = DOC.read_text(encoding="utf-8")
    assert "LLM" in text
    assert re.search(r"no LLM output changes the final optimization result", text,
                     re.IGNORECASE), (
        "the document must record that no LLM output changes the optimisation "
        "result - this is a load-bearing finding, not an aside")


def test_main_document_cites_rl_as_unverified():
    text = DOC.read_text(encoding="utf-8")
    assert "RL-REF" in text
    assert re.search(r"not (?:independently )?re-verified", text, re.IGNORECASE), (
        "every RL claim must be marked as not re-verified")


def test_main_document_avoids_ranking_language():
    """Spec section 37: the document states comparability, never preference."""
    text = DOC.read_text(encoding="utf-8").lower()
    for phrase in ("rl is better", "rl is worse", "ma outperforms",
                   "rl outperforms", "winner", "loser"):
        assert phrase not in text, (
            f"the main document contains preference language ({phrase!r})")


# --------------------------------------------------------------------------- #
# 15. Record of the coverage gap this project does NOT have                     #
# --------------------------------------------------------------------------- #
def test_no_economic_assertions_exist_in_the_scientific_suite():
    """F-26, recorded so the gap stays visible.

    This test documents an ABSENCE, which is unusual but correct here: it fails
    if someone later adds the economic assertions the project currently lacks,
    forcing them to confirm the findings this audit rests on. It asserts the
    absence of `revenue - total_cost == profit` style checks so that the
    documentation can never claim the suite validates economics when it does not.
    """
    # Match only ASSERTIONS, not prose. tests/test_orchestrator.py:1718-1727
    # computes revenue - cost per service inside a __main__ reporting helper
    # (`section_service_economic_table`), which is never collected by pytest;
    # requiring a leading assert/def-test context keeps that from reading as a
    # real economic test.
    patterns = (r"^\s*assert\b[^\n]*revenue\s*-\s*(?:total_)?cost",
                r"^\s*assert\b[^\n]*total_cost\s*==\s*profit",
                r"^\s*assert\b[^\n]*profit_margin_pct\s*==")
    offenders = []
    for path in (ROOT / "tests").rglob("*.py"):
        if path.name == "test_economic_metric_documentation.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in patterns:
            for match in re.finditer(pat, text):
                line_no = text[:match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line_no}: {pat}")
    assert not offenders, (
        f"economic assertions now exist in the scientific suite at {offenders}. "
        f"F-26 is stale - re-derive it and update this documentation test in the "
        f"same change.")