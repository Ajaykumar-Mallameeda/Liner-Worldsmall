#!/usr/bin/env bash
# N-arm paired controlled batch: for each seed ALL arms run CONCURRENTLY (equal machine load for the
# whole group), seeds one after the other.  Same snapshot tree, same harness for every arm.
#
# usage: run_arms.sh <snapshot_root> "<seeds>" <time_limit_sec> "<tag>=<NAME=VAL,NAME=VAL|->;<tag>=...;..." [strategy]
#   e.g.  run_arms.sh D:/liner_scratch/snap_T2 "0 1 2" 120 "P4_E0=LINER_MILP_VUB=1;P4_E1=LINER_MILP_VUB=1,LINER_CLASS_VARIANTS=0.05"
# Output: <campaign>/evidence/outputs/<tag>_seed<S>.json and runs/<tag>_seed<S>.log
ROOT="${1:?root}"; SEEDS="${2:?seeds}"; TL="${3:?tl}"; ARMS="${4:?arms}"; STRAT="${5:-prod}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
run_arm() {  # tag seed envlist
  local tag="$1" seed="$2" envs="$3" name="$1_seed$2"
  (
    if [ "$envs" != "-" ] && [ -n "$envs" ]; then
      IFS=',' read -ra KV <<< "$envs"
      for kv in "${KV[@]}"; do export "$kv"; done
    fi
    "$PROJ/venv/Scripts/python.exe" "$CAMP/tools/global_stage_experiment.py" "$ROOT" "$CAMP/outputs/${name}.json" \
      "$seed" "$TL" "$STRAT" > "$CAMP/runs/${name}.log" 2>&1
    echo "done $name rc=$? $(date +%H:%M:%S)"
  )
}
IFS=';' read -ra ARMLIST <<< "$ARMS"
for S in $SEEDS; do
  for a in "${ARMLIST[@]}"; do
    tag="${a%%=*}"; envs="${a#*=}"
    run_arm "$tag" "$S" "$envs" &
  done
  wait
done
echo "ARMS_DONE $(date +%H:%M:%S)"
