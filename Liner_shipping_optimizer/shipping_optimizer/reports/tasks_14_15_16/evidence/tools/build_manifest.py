"""Build ``experiment_manifest.json`` for Tasks 14-16 (read-only; writes the manifest only).

usage: python -I build_manifest.py <project_root> <report_dir> <out.json>

Records the frozen baseline identity, canonical WorldSmall input hashes, patch hashes, tool
versions and the registry of recorded runs / experiment outputs with the SHA-256 of each file,
so a reader can check that nothing in the evidence was altered after the fact.
"""
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

root, rep, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(*a):
    try:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception as exc:                                   # noqa: BLE001
        return f"unavailable: {exc}"


ws = root / "data" / "raw" / "WorldSmall"
inputs = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(ws.glob("*")) if p.is_file()}
prior = root / "reports" / "overnight_tasks_8_9_10" / "patches"
patches = {}
for d in (prior, rep / "evidence" / "patches"):
    for p in sorted(d.glob("*.patch")):
        patches[p.relative_to(root).as_posix()] = sha(p)

evidence = {}
for sub in ("runs", "outputs", "comparisons"):
    for p in sorted((rep / "evidence" / sub).glob("*")):
        if p.is_file():
            evidence[p.relative_to(root).as_posix()] = sha(p)

try:
    import pulp
    pulp_v = pulp.__version__
except Exception:                                              # noqa: BLE001
    pulp_v = None
try:
    import scipy
    scipy_v = scipy.__version__
except Exception:                                              # noqa: BLE001
    scipy_v = None

manifest = {
    "schema": 1,
    "scope": "Tasks 14, 15, 16 (WorldSmall only; no WorldLarge read)",
    "repository_root": str(root),
    "git": {"head": git("rev-parse", "--short", "HEAD"), "head_subject": git("log", "-1", "--pretty=%s"),
            "tracked_status": "project directory is untracked (git status: ??); the frozen snapshot, "
                              "not a commit, identifies the baseline"},
    "baseline": {
        "snapshot": r"D:\liner_scratch\snap_B0_orch1",
        "identity": "src/, backend/, data/, tests/ byte-identical (211/211) to the Tasks 8-10 final tree "
                    "(evidence/comparisons/baseline_tree_identity_B0_vs_final_tasks_8_9_10.txt)",
    },
    "canonical_inputs": inputs,
    "patches": patches,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "pulp": pulp_v,
    "scipy": scipy_v,
    "cbc": "CBC 2.10.3 (bundled with PuLP; evidence/outputs/*.json solver.cbc_banner)",
    "cpu_note": "Time-limited CBC incumbents depend on available CPU. Valid comparisons use the same "
                "concurrency cap (run_t15_jobs.sh PAR); the contaminated 10-process run is kept and labelled.",
    "evidence_files_sha256": evidence,
}
out.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
print("wrote", out, "evidence files:", len(evidence), "patches:", len(patches))
