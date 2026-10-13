"""
Vessel-capacity unit contract (Task 2, revised in Issue 1 of the 2026-10-13 campaign).

Question: what unit is the fleet column ``Capacity FFE``?
Finding: the primary LINERLIB report is unavailable; the secondary source (RL paper
arXiv:2411.09068, App. A.1 / section 6.1) defines vessel capacity as a number of FFEs. The
loader therefore converts the column ONCE to TEU (x2) and records the status as
``secondary_source``. These tests pin that behaviour and make it impossible to present the
convention as source-verified ("verified") without a primary / authoritative source entry.
(The broader dimensional invariants live in ``tests/test_unit_contract.py``.)

Canonical files are read from data/raw/WorldSmall and compared with an independent
``csv`` read; malformed input uses small synthetic fixtures in tmp_path.
"""

import csv
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import network_loader as nl
from src.data.network_loader import (
    CAPACITY_INTERNAL_UNIT,
    CAPACITY_SOURCE_COLUMN,
    CAPACITY_UNIT_PROVENANCE,
    CAPACITY_UNIT_STATUS,
    DataValidationError,
    NetworkLoader,
    WORLDSMALL_FILES,
)
from src.optimization.data import Fleet, FleetClass, Problem


def _raw(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


QTY_HEADER = ["Vessel class", "Quantity"]
SPEC_HEADER = ["Vessel class", "Capacity FFE", "TC rate daily (fixed Cost)", "draft", "minSpeed",
               "maxSpeed", "designSpeed", "Bunker ton per day at designSpeed",
               "Idle Consumption ton/day", "panamaFee", "suezFee"]


def _write(path, header, rows):
    path.write_text("\n".join("\t".join(str(c) for c in r) for r in [header] + rows) + "\n",
                    encoding="utf-8")
    return path


def _spec(cls, capacity):
    return [cls, capacity, 8000, 10, 10, 20, 15, 30, 3, 1000, 2000]


@pytest.fixture
def loader():
    return NetworkLoader()


# ---------------------------------------------------------------------------
# Fleet-field interpretation: an FFE count, converted once (x2) to TEU
# ---------------------------------------------------------------------------
class TestFieldInterpretation:
    def test_every_class_capacity_equals_the_raw_column_value(self, loader):
        raw = {r["Vessel class"].strip(): float(r["Capacity FFE"])
               for r in _raw(WORLDSMALL_FILES["fleet_data"])}
        assert len(raw) == 6
        loaded = {c.vessel_class: c.capacity_teu for c in loader.load_fleet().classes}
        assert loaded == {k: 2.0 * v for k, v in raw.items()}   # exact: x2 once, no rounding

    def test_canonical_capacities(self, loader):
        loaded = {c.vessel_class: c.capacity_teu for c in loader.load_fleet().classes}
        assert loaded == {"Feeder_450": 900.0, "Feeder_800": 1600.0, "Panamax_1200": 2400.0,
                          "Panamax_2400": 4800.0, "Post_panamax": 8400.0, "Super_panamax": 15000.0}

    def test_synthetic_value_is_doubled_exactly_once(self, loader, tmp_path):
        q = _write(tmp_path / "q.csv", QTY_HEADER, [["X", 1]])
        s = _write(tmp_path / "s.csv", SPEC_HEADER, [_spec("X", 1234)])
        assert loader.load_fleet(q, s).get_class("X").capacity_teu == 2468.0


# ---------------------------------------------------------------------------
# Class identity consistency between the two fleet files and the model
# ---------------------------------------------------------------------------
class TestClassIdentity:
    def test_both_fleet_files_name_the_same_classes(self):
        q = {r["Vessel class"].strip() for r in _raw(WORLDSMALL_FILES["fleet"])}
        s = {r["Vessel class"].strip() for r in _raw(WORLDSMALL_FILES["fleet_data"])}
        assert q == s and len(q) == 6

    def test_model_classes_are_those_names_and_lookup_returns_the_right_spec(self, loader):
        fleet = loader.load_fleet()
        names = {c.vessel_class for c in fleet.classes}
        assert names == {r["Vessel class"].strip() for r in _raw(WORLDSMALL_FILES["fleet"])}
        raw_cap = {r["Vessel class"].strip(): float(r["Capacity FFE"])
                   for r in _raw(WORLDSMALL_FILES["fleet_data"])}
        for name in names:
            assert fleet.get_class(name).capacity_teu == 2.0 * raw_cap[name]
        assert fleet.get_class("Not_A_Class") is None

    def test_classes_missing_from_either_file_are_rejected(self, loader, tmp_path):
        q = _write(tmp_path / "q.csv", QTY_HEADER, [["A", 1], ["B", 1]])
        s = _write(tmp_path / "s.csv", SPEC_HEADER, [_spec("A", 100)])
        with pytest.raises(DataValidationError, match="vessel classes do not match"):
            loader.load_fleet(q, s)


# ---------------------------------------------------------------------------
# Source status is declared, propagated, and cannot silently become "verified"
# ---------------------------------------------------------------------------
class TestProvisionalStatus:
    def test_constants_declare_the_secondary_source_ffe_reading(self):
        assert CAPACITY_SOURCE_COLUMN == "Capacity FFE"
        assert CAPACITY_INTERNAL_UNIT == "TEU"
        assert CAPACITY_UNIT_STATUS == "secondary_source"
        assert CAPACITY_UNIT_PROVENANCE["raw_unit"] == "FFE"
        assert CAPACITY_UNIT_PROVENANCE["capacity_feasibility_is_conditional"] is True
        assert CAPACITY_UNIT_PROVENANCE["authoritative_source"] is None
        assert "arXiv:2411.09068" in CAPACITY_UNIT_PROVENANCE["secondary_source"]

    def test_verified_status_requires_an_authoritative_source(self):
        """Invariant: 'verified' is only legal together with a named source."""
        if CAPACITY_UNIT_PROVENANCE["status"] == "verified":
            src = CAPACITY_UNIT_PROVENANCE["authoritative_source"]
            assert isinstance(src, str) and src.strip(), "verified without a cited source"
            assert CAPACITY_UNIT_PROVENANCE["capacity_feasibility_is_conditional"] is False
        else:
            assert CAPACITY_UNIT_PROVENANCE["status"] in ("provisional", "secondary_source")
            assert CAPACITY_UNIT_PROVENANCE["capacity_feasibility_is_conditional"] is True

    def test_evidence_trail_is_recorded_and_states_no_unit_definition_was_found(self):
        ev = CAPACITY_UNIT_PROVENANCE["evidence_checked"]
        assert len(ev) >= 4 and all(isinstance(e, str) and e for e in ev)
        assert any("not retrievable" in e or "not checked" in e for e in ev)     # primary source
        assert "capacity_teu would equal the loaded value" in CAPACITY_UNIT_PROVENANCE["unapplied_alternative"]

    def test_loaded_fleet_carries_the_status(self, loader):
        fleet = loader.load_fleet()
        assert fleet.capacity_unit == "TEU"
        assert fleet.capacity_unit_status == "secondary_source"
        assert fleet.capacity_source_column == "Capacity FFE"

    def test_problem_built_by_the_loader_exposes_the_status(self, loader):
        problem = loader.load_problem()
        assert isinstance(problem, Problem)
        assert problem.fleet.capacity_unit_status == "secondary_source"

    def test_validation_report_states_the_assumption(self, loader):
        loader.load_fleet()
        cu = loader.validation_report["fleet"]["capacity_unit"]
        assert cu["status"] == "secondary_source"
        assert cu["conversion_applied"].startswith("x2")
        assert cu["capacity_feasibility_is_conditional"] is True

    def test_hand_built_fleet_defaults_to_provisional(self):
        f = Fleet(classes=[FleetClass(vessel_class="X", quantity=1, capacity_teu=10.0)])
        assert f.capacity_unit_status == "provisional" and f.capacity_unit == "TEU"

    def test_report_copy_cannot_mutate_the_module_constant(self, loader):
        loader.load_fleet()
        loader.validation_report["fleet"]["capacity_unit"]["status"] = "verified"
        assert nl.CAPACITY_UNIT_PROVENANCE["status"] == "secondary_source"


# ---------------------------------------------------------------------------
# Missing or malformed capacity inputs are rejected, never defaulted
# ---------------------------------------------------------------------------
class TestMalformedCapacity:
    @pytest.mark.parametrize("value", ["", "0", "-450", "abc", "nan", "inf", "-inf"])
    def test_invalid_capacity_is_rejected_and_names_the_column(self, value, loader, tmp_path):
        q = _write(tmp_path / "q.csv", QTY_HEADER, [["X", 1]])
        s = _write(tmp_path / "s.csv", SPEC_HEADER, [_spec("X", value)])
        with pytest.raises(DataValidationError, match="Capacity FFE"):
            loader.load_fleet(q, s)

    def test_missing_capacity_column_is_rejected(self, loader, tmp_path):
        header = [h for h in SPEC_HEADER if h != "Capacity FFE"]
        row = [v for h, v in zip(SPEC_HEADER, _spec("X", 100)) if h != "Capacity FFE"]
        q = _write(tmp_path / "q.csv", QTY_HEADER, [["X", 1]])
        s = _write(tmp_path / "s.csv", header, [row])
        with pytest.raises(DataValidationError, match="Capacity FFE"):
            loader.load_fleet(q, s)

    def test_rejected_capacity_never_produces_a_default_class(self, loader, tmp_path):
        q = _write(tmp_path / "q.csv", QTY_HEADER, [["X", 1]])
        s = _write(tmp_path / "s.csv", SPEC_HEADER, [_spec("X", "")])
        with pytest.raises(DataValidationError):
            loader.load_fleet(q, s)
        assert "fleet" not in loader.validation_report or \
            loader.validation_report["fleet"].get("classes") != 1
