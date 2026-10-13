#!/usr/bin/env bash
# End-to-end orchestrator runs (tests/test_orchestrator.py) from isolated snapshot copies, N at a time.
#
# usage: run_orch.sh <source_snapshot> <tag> <n_runs> "<NAME=VAL,NAME=VAL|->"
#   each run:  python snaprun.py <tag>_runK <tag>_runK -- tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider
#   (snaprun copies <source_snapshot> to D:/liner_scratch/snap_<tag>_runK and runs pytest there;
#    log / meta / pipeline_output.json land in <campaign>/evidence/runs).  All N runs start together.
SRC="${1:?source snapshot}"; TAG="${2:?tag}"; N="${3:?n}"; ENVS="${4:--}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
if [ "$ENVS" != "-" ]; then
  IFS=',' read -ra KV <<< "$ENVS"
  for kv in "${KV[@]}"; do export "$kv"; done
fi
pids=()
for k in $(seq 1 "$N"); do
  SNAP_SOURCE="$SRC" "$PROJ/venv/Scripts/python.exe" -I "$CAMP/tools/snaprun.py" "${TAG}_run${k}" "${TAG}_run${k}" -- \
    tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider > "$CAMP/runs/${TAG}_run${k}.driver.txt" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
echo "ORCH_DONE $TAG $(date +%H:%M:%S)"
