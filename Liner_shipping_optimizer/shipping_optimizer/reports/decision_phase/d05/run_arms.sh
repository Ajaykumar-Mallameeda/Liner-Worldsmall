#!/usr/bin/env bash
# Paired N-arm batch (Issue 2+): for each seed ALL arms run concurrently (equal machine load), seeds in sequence.
# usage: run_arms.sh <tree_root> "<seeds>" <time_limit_sec> "<tag>=<NAME=VAL,NAME=VAL|->;<tag>=...;..." <out_dir>
ROOT="${1:?root}"; SEEDS="${2:?seeds}"; TL="${3:?tl}"; ARMS="${4:?arms}"; OUT="${5:?outdir}"
HERE="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/decision_phase/d05"
PY="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/venv/Scripts/python.exe"
mkdir -p "$OUT/outputs" "$OUT/runs"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
run_arm() {
  local tag="$1" seed="$2" envs="$3" name="$1_seed$2"
  (
    if [ "$envs" != "-" ] && [ -n "$envs" ]; then
      IFS=',' read -ra KV <<< "$envs"; for kv in "${KV[@]}"; do export "$kv"; done
    fi
    "$PY" "$HERE/global_stage_experiment.py" "$ROOT" "$OUT/outputs/${name}.json" "$seed" "$TL" prod > "$OUT/runs/${name}.log" 2>&1
    echo "done $name rc=$? $(date +%H:%M:%S)"
  )
}
IFS=';' read -ra ARMLIST <<< "$ARMS"
for S in $SEEDS; do
  for a in "${ARMLIST[@]}"; do tag="${a%%=*}"; envs="${a#*=}"; run_arm "$tag" "$S" "$envs" & done
  wait
done
echo "ARMS_DONE $(date +%H:%M:%S)"
