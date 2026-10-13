#!/usr/bin/env bash
# Paired controlled batch: for each seed the two arms run CONCURRENTLY (equal machine load for the
# pair), seeds one after the other.  Both arms use the same snapshot tree and the same harness.
#
# usage: run_pairs.sh <snapshot_root> <tagA> <tagB> "<seeds>" <time_limit_sec> "<envA>" "<envB>" [strategy]
#   envA / envB: comma-separated NAME=VALUE list ("-" = none), e.g. "LINER_MILP_VUB=1,LINER_LOCAL_SEARCH=1"
# Output: <campaign>/evidence/outputs/<tag>_seed<S>.json  and  runs/<tag>_seed<S>.log
ROOT="${1:?root}"; TAGA="${2:?tagA}"; TAGB="${3:?tagB}"; SEEDS="${4:?seeds}"; TL="${5:?tl}"
ENVA="${6:--}"; ENVB="${7:--}"; STRAT="${8:-prod}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
run_arm() {  # tag seed envlist
  local tag="$1" seed="$2" envs="$3" name="$1_seed$2"
  (
    if [ "$envs" != "-" ]; then
      IFS=',' read -ra KV <<< "$envs"
      for kv in "${KV[@]}"; do export "$kv"; done
    fi
    "$PROJ/venv/Scripts/python.exe" "$CAMP/tools/global_stage_experiment.py" "$ROOT" "$CAMP/outputs/${name}.json" \
      "$seed" "$TL" "$STRAT" > "$CAMP/runs/${name}.log" 2>&1
    echo "done $name rc=$? $(date +%H:%M:%S)"
  )
}
for S in $SEEDS; do
  run_arm "$TAGA" "$S" "$ENVA" &
  run_arm "$TAGB" "$S" "$ENVB" &
  wait
done
echo "PAIRS_DONE $TAGA $TAGB $(date +%H:%M:%S)"
