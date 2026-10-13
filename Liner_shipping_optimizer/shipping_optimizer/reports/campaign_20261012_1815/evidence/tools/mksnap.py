"""Snapshot the live project tree into a NEW directory on D: and write its SHA-256 manifest.

usage: python -I mksnap.py <label>
Never deletes or overwrites: the destination must not exist.  Same exclusions as snaprun.py
(venv, logs, .git, caches, node_modules, evidence directories of the missions).
Prints: snapshot path, file count, manifest-file sha256.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

PROJECT = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
SNAP_ROOT = Path(r"D:\liner_scratch")
SKIP_TOP = {"venv", "logs", ".pytest_cache", ".git"}
SKIP_PART = {"__pycache__", "node_modules"}
SKIP_PREFIX = ("reports/tasks_19_20_21/", "reports/expansion_2026_10_12/", "reports/campaign_")

label = sys.argv[1]
dest = SNAP_ROOT / f"snap_{label}"
if dest.exists():
    raise SystemExit(f"snapshot dir exists (not reusing, not deleting): {dest}")
dest.mkdir(parents=True)
manifest = {}
for p in sorted(PROJECT.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(PROJECT).as_posix()
    parts = rel.split("/")
    if parts[0] in SKIP_TOP or SKIP_PART & set(parts) or rel.endswith(".pyc") or rel.startswith(SKIP_PREFIX):
        continue
    t = dest / rel
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, t)
    manifest[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
(dest / "logs").mkdir(exist_ok=True)
mf = SNAP_ROOT / f"snap_{label}.manifest.json"
mf.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
print(dest, len(manifest), hashlib.sha256(mf.read_bytes()).hexdigest())
