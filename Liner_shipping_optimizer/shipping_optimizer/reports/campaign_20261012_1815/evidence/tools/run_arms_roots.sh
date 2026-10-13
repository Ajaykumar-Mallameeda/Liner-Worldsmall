#!/usr/bin/env bash
# Like run_arms.sh, but every arm has its OWN tree (sensitivity scenarios are edited copies):
#   run_arms_roots.sh "<seeds>" <time_limit_sec> "<tag>@<root>=<NAME=VAL,...|->;<tag>@<root>=...;..." [strategy]
# All arms of a seed run concurrently (equal load); seeds one after the other.
SEEDS="${1:?seeds}"; TL="${2:?tl}"; ARMS="${3:?arms}"; STRAT="${4:-prod}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_|BUNKER_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
run_arm() {  # tag root seed envlist
  local tag="$1" root="$2" seed="$3" envs="$4" name="$1_seed$3"
  (
    if [ "$envs" != "-" ] && [ -n "$envs" ]; then
      IFS=',' read -ra KV <<< "$envs"
      for kv in "${KV[@]}"; do export "$kv"; done
    fi
    "$PROJ/venv/Scripts/python.exe" "$CAMP/tools/global_stage_experiment.py" "$root" "$CAMP/outputs/${name}.json" \
      "$seed" "$TL" "$STRAT" > "$CAMP/runs/${name}.log" 2>&1
    echo "done $name rc=$? $(date +%H:%M:%S)"
  )
}
IFS=';' read -ra ARMLIST <<< "$ARMS"
for S in $SEEDS; do
  for a in "${ARMLIST[@]}"; do
    tagroot="${a%%=*}"; envs="${a#*=}"
    tag="${tagroot%%@*}"; root="${tagroot#*@}"
    run_arm "$tag" "$root" "$S" "$envs" &
  done
  wait
done
echo "ARMS_DONE $(date +%H:%M:%S)"
