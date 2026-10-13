"""Apply the ordered patch series to a COPY of the baseline src/ and tests/ in a NEW directory and
compare every file with the final snapshot byte for byte.  Nothing is deleted or modified in place.

usage: python -I verify_patch_series.py <baseline_tree> <final_tree> <patch_dir> <new_work_dir> <p1> <p2> ...
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

base, final, pdir, work = (Path(a).resolve() for a in sys.argv[1:5])
patches = sys.argv[5:]
if work.exists():
    raise SystemExit(f"work dir exists (not reusing, not deleting): {work}")
work.mkdir(parents=True)
for sub in ("src", "tests"):
    shutil.copytree(base / sub, work / sub, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
for p in patches:
    r = subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", str(pdir / p)],
                       cwd=work, capture_output=True, text=True)
    print(("OK   " if r.returncode == 0 else "FAIL ") + p, r.stderr.strip()[:300])
    if r.returncode != 0:
        raise SystemExit(1)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


diff = same = 0
for sub in ("src", "tests"):
    seen = set()
    for f in sorted((work / sub).rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
            rel = f.relative_to(work)
            seen.add(rel)
            g = final / rel
            if g.exists() and sha(f) == sha(g):
                same += 1
            else:
                diff += 1
                print("DIFF", rel)
    for g in sorted((final / sub).rglob("*")):
        if g.is_file() and "__pycache__" not in g.parts and g.suffix != ".pyc" and g.relative_to(final) not in seen:
            diff += 1
            print("MISSING after patches:", g.relative_to(final))
print(f"identical {same}, different {diff}")
sys.exit(0 if diff == 0 else 1)
