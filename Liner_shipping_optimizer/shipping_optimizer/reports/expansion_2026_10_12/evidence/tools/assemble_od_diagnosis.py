"""Assemble ``od_diagnosis_t22.py`` = header of the Tasks 19-21 controlled harness (imports, data
loading, pool construction; everything before its "strategies" section) + ``od_diagnosis_body.py``.

usage: python -I assemble_od_diagnosis.py   (writes next to this file; refuses to overwrite)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent.parent.parent / "tasks_19_20_21" / "evidence" / "tools" / "global_stage_experiment.py"
import sys

OUT = HERE / (sys.argv[1] if len(sys.argv) > 1 else "od_diagnosis_t22.py")
if OUT.exists():
    raise SystemExit(f"{OUT} exists - not overwriting")
h = HARNESS.read_text(encoding="utf-8")
cut = h.index("# ----------------------------------------------------------------------------- strategies")
doc = ('"""T22 read-only per-OD diagnosis of the production plan of one controlled seed.\n'
       'usage: python od_diagnosis_t22.py <tree_root> <out.json> <seed> <time_limit_sec>\n'
       'header = Tasks 19-21 harness (pool construction); body = od_diagnosis_body.py"""\n')
BODY = HERE / (sys.argv[2] if len(sys.argv) > 2 else "od_diagnosis_body.py")
OUT.write_text(doc + h[:cut] + BODY.read_text(encoding="utf-8"), encoding="utf-8")
print("written", OUT)
