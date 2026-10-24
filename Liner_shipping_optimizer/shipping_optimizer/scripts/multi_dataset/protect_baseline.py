#!/usr/bin/env python3
"""Phase A of the multi-dataset campaign: capture and protect the WorldSmall / C3 baseline.

Copies (never moves, never deletes) every artifact that a run of ``tests/test_orchestrator.py``
overwrites into ``reports/multi_dataset_20261016/00_baseline_protect/`` and records the git state,
input hashes, accepted C3 configuration and solver settings in ``baseline_manifest.json``.

    python scripts/multi_dataset/protect_baseline.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "multi_dataset_20261016" / "00_baseline_protect"

# Files that a WorldSmall run overwrites (tests/test_orchestrator.py writes them), plus the JSON problem files.
OVERWRITTEN_BY_RUNS = [
    "pipeline_output.json",
    "frontend/public/pipeline_output.json",
    "frontend/dist/pipeline_output.json",
    "SYSTEM_TRUTH_REPORT.md",
    "P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md",
]
WS_INPUTS = [
    "data/raw/WorldSmall/ports.csv",
    "data/raw/WorldSmall/Demand_WorldSmall_Fixed_Sep.csv",
    "data/raw/WorldSmall/dist_dense.csv",
    "data/raw/WorldSmall/fleet_WorldSmall.csv",
    "data/raw/WorldSmall/fleet_data.csv",
]
JSON_PROBLEMS = [
    "data/datasets/worldsmall_shipping_problem.json",
    "data/datasets/large_shipping_problem.json",
]
REFERENCE = [
    "reports/continuation_20261015/ws1_provenance/C3_baseline_freeze.json",
    "reports/continuation_20261015/ws1_provenance/C3_baseline_freeze.md",
    "reports/continuation_20261015/ws1_provenance/input_provenance.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout


def tree_hash(globs: list[str]) -> dict:
    files = sorted({p for g in globs for p in ROOT.glob(g) if p.is_file() and "__pycache__" not in p.parts})
    h = hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(ROOT)).replace("\\", "/").encode())
        h.update(sha256(p).encode())
    return {"files": len(files), "sha256": h.hexdigest()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    copies = OUT / "copies"
    copies.mkdir(exist_ok=True)

    manifest: dict = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "recoverable WorldSmall / C3 baseline before any multi-dataset change",
        "host": {"python": sys.version.split()[0], "platform": platform.platform()},
    }

    manifest["git"] = {
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "head": git("rev-parse", "HEAD").strip(),
        "status_porcelain_lines": len(git("status", "--porcelain").splitlines()),
        "tracked_modified": [ln for ln in git("status", "--porcelain").splitlines() if not ln.startswith("??")],
        "diff_stat": git("diff", "--stat", "--", ".").splitlines()[-12:],
    }
    # patch of tracked SOURCE changes only (the large generated pipeline_output diffs are covered by the copies below)
    patch = git("diff", "--", "src", "tests", "scripts", "backend")
    (OUT / "tracked_source_changes.patch").write_text(patch, encoding="utf-8")
    manifest["git"]["tracked_source_patch"] = {"file": "tracked_source_changes.patch",
                                               "sha256": hashlib.sha256(patch.encode()).hexdigest(),
                                               "bytes": len(patch.encode())}

    manifest["worldsmall_inputs"] = {p: {"sha256": sha256(ROOT / p), "bytes": (ROOT / p).stat().st_size}
                                     for p in WS_INPUTS}

    saved = {}
    for rel in OVERWRITTEN_BY_RUNS + JSON_PROBLEMS + REFERENCE:
        src = ROOT / rel
        if not src.is_file():
            saved[rel] = {"present": False}
            continue
        dst = copies / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():                      # never overwrite an earlier protection copy
            shutil.copy2(src, dst)
        saved[rel] = {"present": True, "sha256": sha256(src), "protected_copy": str(dst.relative_to(ROOT)).replace("\\", "/"),
                      "copy_sha256": sha256(dst)}
    manifest["protected_artifacts"] = saved

    manifest["source_tree_hashes"] = {
        "src": tree_hash(["src/**/*.py"]),
        "tests/test_orchestrator.py": {"sha256": sha256(ROOT / "tests/test_orchestrator.py")},
    }

    # accepted C3 configuration, solver, budget, seeds - read from the code, not retyped
    text = (ROOT / "tests/test_orchestrator.py").read_text(encoding="utf-8")
    m = re.search(r"C3_CONFIGURATION = \{(.*?)\n\}", text, re.S)
    c3 = dict(re.findall(r'"(LINER_[A-Z_]+)":\s*"([^"]*)"', m.group(1))) if m else {}
    orch = (ROOT / "src/agents/orchestrator_agent.py").read_text(encoding="utf-8")
    manifest["accepted_c3"] = {
        "flags": c3,
        "global_stage_time_limit_sec_default": re.search(r'GLOBAL_STAGE_TIME_LIMIT_SEC", "([0-9.]+)"', orch).group(1),
        "solver_backend_default": "cbc (NETWORK_MILP_BACKEND unset)",
        "seed_mechanism": "LINER_SEED (src/utils/rng.py); unset in tests/test_orchestrator.py; frozen reference used PYTHONHASHSEED=0",
        "cost_model": "src/network/economics.py + ledger.py unchanged by this campaign; bunker 600 USD/t legacy_uniform; "
                      "canal fee = traversals x class fee once per weekly rotation (physical_rules.py)",
        "frozen_reference": "reports/continuation_20261015/ws1_provenance/C3_baseline_freeze.json",
    }
    try:
        import pulp
        manifest["accepted_c3"]["pulp_version"] = pulp.__version__
    except Exception as exc:                          # noqa: BLE001
        manifest["accepted_c3"]["pulp_version"] = f"unavailable: {exc}"

    frozen = json.loads((ROOT / REFERENCE[0]).read_text(encoding="utf-8"))
    on_disk = {p.split("/")[-1]: sha256(ROOT / p)[:16] for p in WS_INPUTS}
    manifest["frozen_reference_check"] = {
        "n_seeds": frozen["n_seeds"],
        "recorded_input_hash_prefixes": frozen["input_hashes_on_disk_16"],
        "current_input_hash_prefixes": on_disk,
        "inputs_match_frozen_reference": all(frozen["input_hashes_on_disk_16"].get(k) == v for k, v in on_disk.items()
                                             if k in frozen["input_hashes_on_disk_16"]),
        "reported_not_independently_verified_here": {
            k: frozen["summary"][k] for k in ("profit_usd_wk", "coverage_pct", "services", "vessels_assigned")},
    }

    (OUT / "baseline_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("git", "frozen_reference_check")}, indent=2)[:3000])
    print("inputs match frozen reference:", manifest["frozen_reference_check"]["inputs_match_frozen_reference"])
    return 0 if manifest["frozen_reference_check"]["inputs_match_frozen_reference"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
