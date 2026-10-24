"""Dataset registry: one selected dataset -> one explicit source package -> one canonical JSON ->
one isolated output directory.

Every dataset resolves ALL of its inputs from its own directory below ``data/raw``; its canonical
problem file lives in ``data/datasets``. There is no shared fallback: a file that is missing is an
error, never another dataset's file. Nothing here reads a data file except to hash it.

    from src.data.dataset_registry import resolve_dataset
    spec = resolve_dataset("baltic")          # DatasetSpec; unknown names raise UnknownDatasetError
    spec.input_paths()                         # {"ports": Path, "demand": Path, ...}

Layout (this is the mapping the campaign asked for; WorldSmall keeps its pre-existing file names):

    data/raw/WorldSmall   data/raw/baltic   data/raw/WAF   data/raw/World-500   data/raw/World-1000
    data/datasets/<id>_json.json            canonical problem file (schema: src/data/problem_json.py)
    data/datasets/<id>_manifest.json        provenance, hashes, counts, validation record
    reports/dataset_runs/<key>/             run outputs (WorldSmall's legacy outputs stay where they were)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"
DATASETS_ROOT = PROJECT_ROOT / "data" / "datasets"
RUNS_ROOT = PROJECT_ROOT / "reports" / "dataset_runs"

# the five input roles every dataset package provides (all tab separated despite the ``.csv`` extension)
INPUT_ROLES = ("ports", "demand", "distance", "fleet", "fleet_data")


class DatasetError(ValueError):
    """Base class of dataset-registry errors."""


class UnknownDatasetError(DatasetError):
    """The requested dataset name is not in the registry."""


class DatasetNotAvailableError(DatasetError, FileNotFoundError):
    """A registered dataset's input or JSON file is missing (never substituted by another dataset)."""


@dataclass(frozen=True)
class DatasetSpec:
    key: str                              # canonical identity, written into every JSON / output
    label: str                            # menu label
    kind: str                             # "real_linerlib" | "synthetic"
    raw_dir: Path                         # data/raw/<dir>
    files: Mapping[str, str]              # role -> file name inside raw_dir
    json_name: str                        # data/datasets/<json_name>
    aliases: Tuple[str, ...] = ()
    legacy_outputs: bool = False          # WorldSmall: outputs stay at their pre-existing locations
    description: str = ""

    # ------------------------------------------------------------------ paths
    @property
    def json_path(self) -> Path:
        return DATASETS_ROOT / self.json_name

    @property
    def manifest_path(self) -> Path:
        return DATASETS_ROOT / self.json_name.replace("_json.json", "_manifest.json")

    @property
    def output_dir(self) -> Path:
        return RUNS_ROOT / self.key

    def input_paths(self) -> Dict[str, Path]:
        return {role: self.raw_dir / name for role, name in self.files.items()}

    def missing_inputs(self) -> list:
        return [str(p) for p in self.input_paths().values() if not p.is_file()]

    def require_inputs(self) -> Dict[str, Path]:
        """All five source files, or ``DatasetNotAvailableError`` naming what is missing."""
        missing = self.missing_inputs()
        if missing:
            raise DatasetNotAvailableError(
                f"dataset {self.key!r}: required input file(s) not found: {missing}. "
                f"No fallback to another dataset is attempted.")
        return self.input_paths()

    def require_json(self) -> Path:
        if not self.json_path.is_file():
            raise DatasetNotAvailableError(
                f"dataset {self.key!r}: canonical problem file not found: {self.json_path}. "
                f"Build it with scripts/multi_dataset/build_problem_json.py --dataset {self.key}; "
                f"no other dataset's or historical JSON is used instead.")
        return self.json_path

    def describe(self, with_hashes: bool = True) -> dict:
        """Selected dataset, resolved paths and (optionally) SHA-256 of every input and the JSON."""
        out = {"dataset": self.key, "label": self.label, "kind": self.kind,
               "raw_dir": str(self.raw_dir), "inputs": {}, "json": {"path": str(self.json_path)},
               "output_dir": str(self.output_dir), "legacy_outputs": self.legacy_outputs}
        for role, p in self.input_paths().items():
            out["inputs"][role] = {"path": str(p)}
            if with_hashes and p.is_file():
                out["inputs"][role]["sha256"] = sha256_file(p)
        if with_hashes and self.json_path.is_file():
            out["json"]["sha256"] = sha256_file(self.json_path)
        return out


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(demand: str, fleet: str) -> Dict[str, str]:
    return {"ports": "ports.csv", "demand": demand, "distance": "dist_dense.csv",
            "fleet": fleet, "fleet_data": "fleet_data.csv"}


# WorldSmall keeps its canonical, hash-frozen file names (data/raw/WorldSmall is never rewritten).
_SPECS = (
    DatasetSpec(
        key="WorldSmall", label="WorldSmall (LINERLIB, 47 ports)", kind="real_linerlib",
        raw_dir=RAW_ROOT / "WorldSmall",
        files=_files("Demand_WorldSmall_Fixed_Sep.csv", "fleet_WorldSmall.csv"),
        json_name="worldsmall_json.json", aliases=("worldsmall", "ws"), legacy_outputs=True,
        description="reference case of the accepted C3 configuration"),
    DatasetSpec(
        key="baltic", label="Baltic (LINERLIB regional, 12 ports)", kind="real_linerlib",
        raw_dir=RAW_ROOT / "baltic", files=_files("Demand_Baltic.csv", "fleet_Baltic.csv"),
        json_name="baltic_json.json", aliases=("baltic",),
        description="LINERLIB Baltic instance"),
    DatasetSpec(
        key="WAF", label="WAF (LINERLIB regional, 20 ports)", kind="real_linerlib",
        raw_dir=RAW_ROOT / "WAF", files=_files("Demand_WAF.csv", "fleet_WAF.csv"),
        json_name="waf_json.json", aliases=("waf", "westafrica"),
        description="LINERLIB West Africa instance"),
    DatasetSpec(
        key="World-500", label="World-500 (synthetic, 500 ports)", kind="synthetic",
        raw_dir=RAW_ROOT / "World-500", files=_files("Demand_World-500.csv", "fleet_World-500.csv"),
        json_name="world500_json.json", aliases=("world500", "w500", "500"),
        description="synthetic benchmark calibrated on LINERLIB distributions"),
    DatasetSpec(
        key="World-1000", label="World-1000 (synthetic, 1000 ports)", kind="synthetic",
        raw_dir=RAW_ROOT / "World-1000", files=_files("Demand_World-1000.csv", "fleet_World-1000.csv"),
        json_name="world1000_json.json", aliases=("world1000", "w1000", "1000"),
        description="synthetic benchmark calibrated on LINERLIB distributions"),
)

DATASETS: Dict[str, DatasetSpec] = {s.key: s for s in _SPECS}
DEFAULT_DATASET = "WorldSmall"


def _normalise(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(name)).lower()        # path-like input ("../x", "a/b", "x.y") never matches


_LOOKUP: Dict[str, str] = {}
for _s in _SPECS:
    for _n in (_s.key, *_s.aliases):
        _LOOKUP[_normalise(_n)] = _s.key


def list_datasets() -> Tuple[DatasetSpec, ...]:
    """The datasets in menu order."""
    return _SPECS


def resolve_dataset(name: Optional[str]) -> DatasetSpec:
    """The spec for ``name`` (case, spaces, ``-`` and ``_`` are ignored; anything path-like is unknown). ``None`` -> WorldSmall.

    Unknown names raise ``UnknownDatasetError`` listing the valid choices; there is no fuzzy match
    and no default for a name that was given.
    """
    if name is None:
        return DATASETS[DEFAULT_DATASET]
    if isinstance(name, DatasetSpec):
        return name
    key = _LOOKUP.get(_normalise(name))
    if key is None:
        raise UnknownDatasetError(
            f"unknown dataset {name!r}; choose one of: "
            + ", ".join(f"{s.key}" for s in _SPECS))
    return DATASETS[key]


def menu_choices() -> Dict[str, DatasetSpec]:
    """Numbered interactive-menu entries: '1' .. '5'."""
    return {str(i): s for i, s in enumerate(_SPECS, start=1)}
