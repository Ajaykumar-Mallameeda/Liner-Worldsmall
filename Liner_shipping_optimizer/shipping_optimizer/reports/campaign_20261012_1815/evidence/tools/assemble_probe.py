"""assemble_probe.py <out_name> <body_file>: header of the controlled harness (imports, data, pool construction;
everything before its "strategies" section) + a body file -> a standalone probe script next to this file.
usage of the result: python <out_name> <tree_root> <out.json> <seed> <time_limit_sec>"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
out = HERE / sys.argv[1]
if out.exists():
    raise SystemExit(f"{out} exists - not overwriting")
h = (HERE / "global_stage_experiment.py").read_text(encoding="utf-8")
cut = h.index("# ----------------------------------------------------------------------------- strategies")
out.write_text(h[:cut] + (HERE / sys.argv[2]).read_text(encoding="utf-8"), encoding="utf-8")
print("written", out)
