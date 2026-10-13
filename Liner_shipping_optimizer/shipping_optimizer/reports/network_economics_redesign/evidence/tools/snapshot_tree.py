"""Copy a working tree to a clean snapshot directory with the same exclusions as extract_base.py.

usage: python -I snapshot_tree.py <src_dir> <dest_dir> <manifest_out>
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

SRC, DEST, MANIFEST = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SKIP_TOP = {"venv", "logs", ".pytest_cache", ".git"}
SKIP_PART = {"__pycache__", "node_modules"}

if DEST.exists() and any(DEST.iterdir()):
    raise SystemExit(f"destination not empty: {DEST}")
DEST.mkdir(parents=True, exist_ok=True)

manifest = {}
for p in sorted(SRC.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(SRC).as_posix()
    parts = rel.split("/")
    if parts[0] in SKIP_TOP or SKIP_PART & set(parts) or rel.endswith(".pyc"):
        continue
    t = DEST / rel
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, t)
    manifest[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
(DEST / "logs").mkdir(exist_ok=True)
MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
print(f"snapshot {len(manifest)} files -> {DEST}")
