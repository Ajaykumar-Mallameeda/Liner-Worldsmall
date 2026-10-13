"""Compare the live project tree with a recorded snapshot manifest (read-only)."""
import hashlib, json, os, sys

root = sys.argv[1]
manifest = json.load(open(sys.argv[2]))
prefixes = tuple(sys.argv[3:]) or ("src/", "backend/", "data/", "tests/")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

missing, differ, same = [], [], 0
for rel, want in manifest.items():
    if not rel.replace("\\", "/").startswith(prefixes):
        continue
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        missing.append(rel)
        continue
    if sha(p) != want:
        differ.append(rel)
    else:
        same += 1

# files present in live tree under the prefixes but not in manifest
extra = []
for pre in prefixes:
    base = os.path.join(root, pre.rstrip("/"))
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".pytest_cache")]
        for f in fn:
            if f.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
            if rel not in manifest and rel.replace("/", "\\") not in manifest:
                extra.append(rel)

print("manifest entries compared:", same + len(differ) + len(missing))
print("identical:", same)
print("differ:", len(differ))
for r in differ[:40]:
    print("  DIFF", r)
print("missing in live tree:", len(missing))
for r in missing[:40]:
    print("  MISSING", r)
print("extra in live tree (not in manifest):", len(extra))
for r in extra[:40]:
    print("  EXTRA", r)
