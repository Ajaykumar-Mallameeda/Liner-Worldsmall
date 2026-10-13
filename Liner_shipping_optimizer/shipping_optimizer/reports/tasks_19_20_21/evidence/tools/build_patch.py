"""Build a unified-diff patch (+ SHA-256) of the changes between a baseline tree and the live tree.

usage: python -I build_patch.py <baseline_tree> <live_tree> <out.patch> [<prefix> ...]

Only files under the given path prefixes are compared (default: src/ tests/ backend/ data/).
Line endings are preserved byte-for-byte (several project files are CRLF).  Nothing is
deleted or modified in either tree.  The patch applies with ``git apply`` / ``patch -p1`` from
the baseline root; apply-check is performed by the caller (see the Task 14-16 report).
"""
import difflib
import hashlib
import re
import sys
from pathlib import Path

base, live, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
prefixes = tuple(sys.argv[4:]) or ("src", "tests", "backend", "data")
SKIP = {"__pycache__", ".pytest_cache"}
# split on "\n" only (keeps "\r\n" intact; str.splitlines would also split on \x0c etc.)
LINES = re.compile(r"[^\n]*\n|[^\n]+")


def files(root: Path):
    res = {}
    for pre in prefixes:
        d = root / pre
        if not d.exists():
            continue
        if d.is_file():                       # a prefix may name a single file
            res[d.relative_to(root).as_posix()] = d
            continue
        for p in d.rglob("*"):
            if p.is_file() and not (SKIP & set(p.parts)) and p.suffix != ".pyc":
                res[p.relative_to(root).as_posix()] = p
    return res


A, B = files(base), files(live)
chunks, changed = [], []
for rel in sorted(set(A) | set(B)):
    a = A.get(rel)
    b = B.get(rel)
    ab = a.read_bytes() if a else None
    bb = b.read_bytes() if b else None
    if ab == bb:
        continue
    try:
        at = LINES.findall(ab.decode("utf-8")) if ab is not None else []
        bt = LINES.findall(bb.decode("utf-8")) if bb is not None else []
    except UnicodeDecodeError:
        chunks.append(f"Binary file {rel} differs\n")
        changed.append(rel)
        continue
    for lst in (at, bt):
        if lst and not lst[-1].endswith("\n"):
            lst[-1] += "\n\\ No newline at end of file\n"
    head = [f"diff --git a/{rel} b/{rel}\n"]
    if a is None:
        head.append("new file mode 100644\n")
    fa = "/dev/null" if a is None else f"a/{rel}"
    fb = "/dev/null" if b is None else f"b/{rel}"
    body = list(difflib.unified_diff(at, bt, fromfile=fa, tofile=fb, n=3))
    if not body:
        continue
    chunks.append("".join(head) + "".join(body))
    changed.append(rel)

data = "".join(chunks).encode("utf-8")
out.write_bytes(data)
sha = hashlib.sha256(data).hexdigest()
(out.with_suffix(out.suffix + ".sha256")).write_text(f"{sha}  {out.name}\n", encoding="utf-8")
print(f"{len(changed)} file(s) in patch; sha256 {sha}")
for rel in changed:
    print("  ", rel)
