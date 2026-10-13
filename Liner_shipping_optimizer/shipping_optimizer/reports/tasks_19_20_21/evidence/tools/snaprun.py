"""Snapshot the project tree into a NEW uniquely-named directory and run a command there.

(Tasks 19-21 copy of the Tasks 14-16 tool: only the evidence directory differs.)

usage: python -I snaprun.py <label> <log_name> -- <pytest args...>
       python -I snaprun.py <label> <log_name> --script -- <script.py> <args...>

* never deletes anything: the destination must not exist (labels are unique)
* skips venv, logs, caches, node_modules, .git (same exclusions as the Tasks 8-10 / 14-16 tool)
* runs the project's venv python from inside the snapshot with PYTHONPYCACHEPREFIX pointing
  at a per-run directory (no stale .pyc is trusted)
* writes <log_name>.log / <log_name>.meta.txt into ``reports/tasks_19_20_21/evidence/runs``
  and copies ``pipeline_output.json`` next to them when the run produced one
* the snapshot is written to D: (C: is nearly full); the manifest sits beside it

Environment variables of the caller are forwarded unchanged (e.g. LINER_PATH_SELECTION).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
RUNS = PROJECT / "reports" / "tasks_19_20_21" / "evidence" / "runs"
# SNAP_SOURCE: snapshot another tree (e.g. the frozen baseline) instead of the live project;
# SNAP_EXCLUDE: comma-separated relative paths to leave out (e.g. pipeline_output.json)
SOURCE = Path(os.environ.get("SNAP_SOURCE", str(PROJECT)))
EXCLUDE = {x.strip() for x in os.environ.get("SNAP_EXCLUDE", "").split(",") if x.strip()}
SNAP_ROOT = Path(r"D:\liner_scratch")
PY = PROJECT / "venv" / "Scripts" / "python.exe"
SKIP_TOP = {"venv", "logs", ".pytest_cache", ".git"}
SKIP_PART = {"__pycache__", "node_modules"}

label, log_name = sys.argv[1], sys.argv[2]
rest = sys.argv[3:]
script_mode = False
if rest and rest[0] == "--script":
    script_mode = True
    rest = rest[1:]
assert rest and rest[0] == "--", "usage: snaprun.py <label> <log_name> [--script] -- args"
args = rest[1:]

dest = SNAP_ROOT / f"snap_{label}"
if dest.exists():
    raise SystemExit(f"snapshot dir exists (not reusing, not deleting): {dest}")
dest.mkdir(parents=True)
manifest = {}
for p in sorted(SOURCE.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(SOURCE).as_posix()
    parts = rel.split("/")
    if parts[0] in SKIP_TOP or SKIP_PART & set(parts) or rel.endswith(".pyc") or rel in EXCLUDE:
        continue
    # the reports of THIS mission are evidence, not source: never copied into a run tree
    if rel.startswith("reports/tasks_19_20_21/"):
        continue
    t = dest / rel
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, t)
    manifest[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
(dest / "logs").mkdir(exist_ok=True)
(SNAP_ROOT / f"snap_{label}.manifest.json").write_text(
    json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")

RUNS.mkdir(parents=True, exist_ok=True)
log = RUNS / f"{log_name}.log"
meta = RUNS / f"{log_name}.meta.txt"
env = dict(os.environ)
env["PYTHONPYCACHEPREFIX"] = str(SNAP_ROOT / f"pycache_{label}")
env.setdefault("PYTHONUTF8", "1")
cmd = [str(PY), *([] if script_mode else ["-m", "pytest"]), *args]
t0 = time.time()
with open(log, "wb") as fh:
    rc = subprocess.run(cmd, cwd=dest, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode
dt = time.time() - t0
tree_sha = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
extra_env = {k: v for k, v in env.items()
             if k.startswith(("LINER_", "BUNKER_", "GLOBAL_STAGE", "PYTHONHASHSEED", "NETWORK_MILP", "T15_",
                              "T16_", "T19_", "T20_", "T21_"))}
meta.write_text(
    f"tree: {dest}\nsource: {SOURCE}; excluded: {sorted(EXCLUDE)}\n"
    f"command: {' '.join(cmd[1:])}\nexit_code: {rc}\nelapsed_s: {dt:.0f}\n"
    f"started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0))}\nfiles: {len(manifest)}\n"
    f"tree_manifest_sha256: {tree_sha}\nenv: {json.dumps(extra_env, sort_keys=True)}\n",
    encoding="utf-8")
if (dest / "pipeline_output.json").exists():
    shutil.copy2(dest / "pipeline_output.json", RUNS / f"{log_name}.pipeline_output.json")
print(f"exit={rc} elapsed={dt:.0f}s log={log}")
