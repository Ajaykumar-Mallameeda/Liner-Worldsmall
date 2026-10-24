#!/usr/bin/env python3
"""Build the canonical JSON problem file and manifest of each dataset from its OWN source package.

    python scripts/multi_dataset/build_problem_json.py --dataset all
    python scripts/multi_dataset/build_problem_json.py --dataset baltic --check     # rebuild in memory, compare with disk
    python scripts/multi_dataset/build_problem_json.py --dataset WorldSmall --replace   # replace a file whose content changed

Writes  data/datasets/<id>_json.json   and   data/datasets/<id>_manifest.json   (deterministic: no timestamps).
Rules: an existing file with identical content is left alone; a differing one is replaced only with
``--replace`` and only after it was copied to ``data/datasets/_backups/`` with its hash in the name; nothing
is ever deleted; a dataset that fails validation produces no JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.data.dataset_registry import DATASETS, list_datasets, resolve_dataset, sha256_file          # noqa: E402
from src.data.dataset_validation import summarize, validate_dataset                                   # noqa: E402
from src.data.problem_json import CONVERTER_VERSION, SCHEMA_VERSION, build_problem_dict, dumps_problem  # noqa: E402


def _rel(p: Path) -> str:
    try:
        return str(Path(p).relative_to(ROOT)).replace("\\", "/")
    except ValueError:                       # a temporary / external location (tests)
        return str(p)


def _backup(path: Path) -> Path:
    bdir = path.parent / "_backups"
    bdir.mkdir(exist_ok=True)
    dst = bdir / f"{path.stem}.{sha256_file(path)[:12]}{path.suffix}"
    if not dst.exists():
        shutil.copy2(path, dst)
    return dst


def _put(path: Path, data: bytes, replace: bool) -> str:
    if path.exists():
        if path.read_bytes() == data:
            return "unchanged"
        if not replace:
            raise SystemExit(f"{path} exists with different content; use --replace (a backup is taken first)")
        b = _backup(path)
        path.write_bytes(data)
        return f"replaced (backup {b.name})"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return "written"


def build_one(key: str, replace: bool, check: bool) -> int:
    spec = resolve_dataset(key)
    # validate the package itself BEFORE building anything: a dataset that fails produces no problem file
    pre = validate_dataset(spec, check_json=False)
    blocking = [c for c in pre if not c["ok"] and c["severity"] == "error"]
    if blocking:
        print(f"[{spec.key}] validation FAILED - no JSON written:")
        for c in blocking:
            print(f"    {c['check']}: {c['detail']}")
        return 1
    obj, loader_report = build_problem_dict(spec)
    data = dumps_problem(obj)

    if check:
        same = spec.json_path.is_file() and spec.json_path.read_bytes() == data
        print(f"[{spec.key}] --check: {'identical to disk' if same else 'DIFFERS from disk or missing'} "
              f"(sha256 of rebuild {hashlib.sha256(data).hexdigest()[:16]})")
        return 0 if same else 1

    state = _put(spec.json_path, data, replace)
    checks = validate_dataset(spec, check_json=True)
    summ = summarize(checks)
    prov = obj["provenance"]
    manifest = {
        "dataset": spec.key, "label": spec.label, "kind": spec.kind, "description": spec.description,
        "schema": {"name": obj["schema"], "version": SCHEMA_VERSION, "converter_version": CONVERTER_VERSION,
                   "build_id": prov["build_id"]},
        "source_package": {"dir": obj["dataset"]["source_dir"], "files": prov["inputs"]},
        "shared_references": [prov["distance_alternatives_source"]] if (prov["distance_alternatives_source"] or {}).get("shared_reference") else [],
        "distance_alternatives_source": prov["distance_alternatives_source"],
        "problem_json": {"path": _rel(spec.json_path),
                         "sha256": sha256_file(spec.json_path), "bytes": spec.json_path.stat().st_size},
        "counts": {
            "ports": len(obj["ports"]), "demand_records": len(obj["demands"]),
            "unique_od_pairs": len({(d["origin"], d["destination"]) for d in obj["demands"]}),
            "directed_distance_pairs": sum(len(r) for r in obj["distance_matrix"].values()),
            "pairs_with_distance_alternatives": len(obj["distance_alternatives"]),
            "distance_records_incl_alternatives": sum(len(a["records"]) for a in obj["distance_alternatives"])
            + sum(len(r) for r in obj["distance_matrix"].values()) - len(obj["distance_alternatives"]),
            "canal_flagged_pairs": len(obj["canal_flags"]), "pairs_with_draft_limit": len(obj["edge_draft"]),
            "fleet_classes": len(obj["fleet"]["classes"]),
            "vessels_total": sum(c["quantity"] for c in obj["fleet"]["classes"]),
            "vessels_by_class": {c["vessel_class"]: c["quantity"] for c in obj["fleet"]["classes"]},
        },
        "totals": {"weekly_demand_teu": sum(d["weekly_teu"] for d in obj["demands"]),
                   "weekly_gross_revenue_usd": sum(d["weekly_teu"] * d["revenue_per_teu"] for d in obj["demands"])},
        "validation": {"summary": summ, "checks": checks},
        "output_dir": _rel(spec.output_dir),
    }
    gen = spec.raw_dir / "generation_manifest.json"
    if gen.is_file():
        manifest["generation_manifest"] = {"file": gen.name, "sha256": sha256_file(gen)}
    mdata = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    mstate = _put(spec.manifest_path, mdata, True) if spec.manifest_path.exists() else _put(spec.manifest_path, mdata, False)
    print(f"[{spec.key}] json {state}, manifest {mstate}; ports={manifest['counts']['ports']} "
          f"demands={manifest['counts']['demand_records']} pairs={manifest['counts']['directed_distance_pairs']} "
          f"vessels={manifest['counts']['vessels_total']}; checks {summ}")
    for c in checks:
        if not c["ok"]:
            print(f"    {c['severity'].upper()}: {c['check']}: {c['detail']}")
    return 1 if summ["blocking_failures"] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", nargs="+", default=["all"], help="dataset key(s) or 'all'")
    ap.add_argument("--replace", action="store_true", help="replace a differing canonical JSON (after backing it up)")
    ap.add_argument("--check", action="store_true", help="rebuild in memory and compare with the file on disk")
    a = ap.parse_args(argv)
    keys = [s.key for s in list_datasets()] if a.dataset == ["all"] else [resolve_dataset(k).key for k in a.dataset]
    rc = 0
    for k in keys:
        if resolve_dataset(k).missing_inputs():
            print(f"[{k}] source package incomplete - skipped: {resolve_dataset(k).missing_inputs()[:2]}")
            rc |= 1
            continue
        rc |= build_one(k, a.replace, a.check)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
