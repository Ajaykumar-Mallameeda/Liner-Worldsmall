"""Build a standard git-format patch between two source trees WITHOUT modifying either.

usage: python make_patch.py <base_dir> <target_dir> <out_patch>

A throw-away git repository holds only the object database; the two trees are read in
place through GIT_WORK_TREE, so nothing is copied into or deleted from them. reports/
and logs/ are excluded. Renames are detected. The tool asserts that the input trees
are byte-for-byte unchanged afterwards.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE, TARGET, OUT = (Path(a).resolve() for a in sys.argv[1:4])
EXCLUDE = [":(exclude)reports", ":(exclude)logs"]


def fingerprint(root: Path):
    h = hashlib.sha256()
    n = 0
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel.split("/")[0] in ("reports", "logs"):
                continue
            h.update(rel.encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
            n += 1
    return n, h.hexdigest()


before = (fingerprint(BASE), fingerprint(TARGET))
gitdir = Path(tempfile.mkdtemp(prefix="mkpatch_"))
env = dict(os.environ, GIT_DIR=str(gitdir / "g"), GIT_CONFIG_NOSYSTEM="1", HOME=str(gitdir))
CFG = ["-c", "core.autocrlf=false", "-c", "core.safecrlf=false", "-c", "core.longpaths=true",
       "-c", "core.quotepath=off", "-c", "user.name=scratch", "-c", "user.email=s@example.invalid"]


def git(*args, work_tree=None, capture=False):
    e = dict(env)
    if work_tree is not None:
        e["GIT_WORK_TREE"] = str(work_tree)
    r = subprocess.run(["git", *CFG, *args], env=e, cwd=str(work_tree or gitdir),
                       stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    if r.returncode not in (0, 1):
        raise SystemExit(f"git {' '.join(args)} failed ({r.returncode})")
    return r.stdout


# Nothing is deleted by this tool: the temporary object database is left in place
# (it is a unique directory under the system temp folder) and the input trees are only read.
subprocess.run(["git", "init", "-q", env["GIT_DIR"]], check=True, env=env)
git("add", "-A", "-f", "--", ".", *EXCLUDE, work_tree=BASE)
git("commit", "-q", "-m", "base", work_tree=BASE)
git("rm", "-r", "-q", "--cached", "--ignore-unmatch", ".", work_tree=TARGET)
git("add", "-A", "-f", "--", ".", *EXCLUDE, work_tree=TARGET)
patch = git("diff", "--cached", "--binary", "-M", "HEAD", work_tree=TARGET, capture=True)

OUT.write_bytes(patch)
after = (fingerprint(BASE), fingerprint(TARGET))
assert before == after, "input trees changed during patch creation"
files = [l for l in patch.decode("utf-8", "replace").splitlines() if l.startswith("diff --git")]
print(f"patch: {OUT.name} bytes={len(patch)} sha256={hashlib.sha256(patch).hexdigest()} "
      f"files={len(files)} inputs_unchanged=True base={before[0][0]} target={before[1][0]}")
for l in files:
    print("  ", l.replace("diff --git ", ""))
