#!/usr/bin/env bash
# Seed-major sequential batch of the global-stage experiment (WorldSmall only, CBC 120 s, single thread).
# usage: TREE_ROOT=<tree> run_arms.sh "<seeds>" "<tag>=<ENV,ENV|->;<tag>=..."   (arm order rotates with the seed)
# Base flags of every arm (same as the class-mismatch campaign): LINER_MILP_VUB=1 LINER_LOCAL_SEARCH=1; arm flags are added.
BASE="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
ROOT="${TREE_ROOT:?set TREE_ROOT to the frozen tree (.../shipping_optimizer)}"
HERE="$BASE/reports/continuation_20261015/tools"
OUTD="$BASE/reports/continuation_20261015"
PY="$BASE/venv/Scripts/python.exe"
SEEDS="$1"; ARMS="$2"
for v in $(env | grep -oE '^(TREE|LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
IFS=';' read -ra L <<< "$ARMS"
mkdir -p "$OUTD/outputs" "$OUTD/runs"
[ -f "$OUTD/run_order_B4.csv" ] || echo "seq,seed,arm,env,tree,start,end,rc" > "$OUTD/run_order_B4.csv"
n=$(wc -l < "$OUTD/run_order_B4.csv")
for S in $SEEDS; do
  k=${#L[@]}; ORD=(); for ((i=0;i<k;i++)); do ORD+=("${L[$(( (i+S) % k ))]}"); done
  for a in "${ORD[@]}"; do
    tag="${a%%=*}"; envs="${a#*=}"; name="${tag}_seed${S}"
    [ -f "$OUTD/outputs/${name}.json" ] && continue
    st=$(date +%FT%T)
    ( export LINER_MILP_VUB=1 LINER_LOCAL_SEARCH=1
      if [ "$envs" != "-" ]; then IFS=',' read -ra KV <<< "$envs"; for kv in "${KV[@]}"; do export "$kv"; done; fi
      "$PY" "$HERE/global_stage_experiment_v4.py" "$ROOT" "$OUTD/outputs/${name}.json" "$S" 120 prod > "$OUTD/runs/${name}.log" 2>&1 ); rc=$?
    n=$((n+1)); echo "$n,$S,$tag,\"$envs\",$ROOT,$st,$(date +%FT%T),$rc" >> "$OUTD/run_order_B4.csv"
  done
done
echo BATCH_DONE >> "$OUTD/run_order_B4.csv"
