"""Extract the pristine source base from the project zip (excluding venv/frontend/logs/caches).

usage: python -I extract_base.py <zip> <dest_dir>
"""
import sys
import zipfile
from pathlib import Path

ZIP, DEST = Path(sys.argv[1]), Path(sys.argv[2])
PREFIX = "Liner_shipping_optimizer/shipping_optimizer/"
SKIP_TOP = {"venv", "logs", ".pytest_cache"}
SKIP_PART = {"__pycache__", "node_modules"}

if DEST.exists() and any(DEST.iterdir()):
    raise SystemExit(f"destination not empty: {DEST}")
DEST.mkdir(parents=True, exist_ok=True)

n = 0
with zipfile.ZipFile(ZIP) as z:
    for info in z.infolist():
        name = info.filename
        if not name.startswith(PREFIX) or name.endswith("/"):
            continue
        rel = name[len(PREFIX):]
        parts = rel.split("/")
        if parts[0] in SKIP_TOP or SKIP_PART & set(parts):
            continue
        target = (DEST / rel).resolve()
        if DEST.resolve() not in target.parents:       # zip-slip guard
            raise SystemExit(f"unsafe path in archive: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(info))
        n += 1
print(f"extracted {n} files into {DEST}")
