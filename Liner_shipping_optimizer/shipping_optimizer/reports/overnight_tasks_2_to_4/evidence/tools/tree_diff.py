"""Hash-compare two source trees and list added / removed / modified files.

usage: python -I tree_diff.py <base_dir> <work_dir>
"""
import hashlib
import sys
from pathlib import Path

BASE, WORK = Path(sys.argv[1]), Path(sys.argv[2])
SKIP_TOP = {"venv", "logs", ".pytest_cache", ".git"}
SKIP_PART = {"__pycache__", "node_modules"}


def scan(root):
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        if parts[0] in SKIP_TOP or SKIP_PART & set(parts) or rel.endswith(".pyc"):
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


b, w = scan(BASE), scan(WORK)
added = sorted(set(w) - set(b))
removed = sorted(set(b) - set(w))
modified = sorted(k for k in set(b) & set(w) if b[k] != w[k])
print(f"base files={len(b)} work files={len(w)}")
print(f"\n== modified ({len(modified)})")
for k in modified:
    print("  M", k)
print(f"\n== added ({len(added)})")
for k in added:
    print("  A", k)
print(f"\n== removed ({len(removed)})")
for k in removed:
    print("  D", k)
