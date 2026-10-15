#!/usr/bin/env bash
# Seed-major sequential batch. usage: run_arms.sh "<seeds>" "<tag>=<ENV,ENV|->;<tag>=..."   (arm order rotates with the seed)
ROOT="C:/Users/WINDOWS/Liner-Worldsmall_exp/tree_fix1/Liner_shipping_optimizer/shipping_optimizer"
HERE="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/decision_phase/d05_final"
OUTD="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/class_mismatch_campaign"
PY="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/venv/Scripts/python.exe"
SEEDS="$1"; ARMS="$2"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
IFS=';' read -ra L <<< "$ARMS"
mkdir -p "$OUTD/outputs" "$OUTD/runs"
[ -f "$OUTD/run_order.csv" ] || echo "seq,seed,arm,env,start,end,rc" > "$OUTD/run_order.csv"
n=$(wc -l < "$OUTD/run_order.csv")
for S in $SEEDS; do
  k=${#L[@]}; ORD=(); for ((i=0;i<k;i++)); do ORD+=("${L[$(( (i+S) % k ))]}"); done
  for a in "${ORD[@]}"; do
    tag="${a%%=*}"; envs="${a#*=}"; name="${tag}_seed${S}"
    [ -f "$OUTD/outputs/${name}.json" ] && continue
    st=$(date +%FT%T)
    ( export LINER_MILP_VUB=1 LINER_LOCAL_SEARCH=1
      if [ "$envs" != "-" ]; then IFS=',' read -ra KV <<< "$envs"; for kv in "${KV[@]}"; do export "$kv"; done; fi
      "$PY" "$HERE/global_stage_experiment.py" "$ROOT" "$OUTD/outputs/${name}.json" "$S" 120 prod > "$OUTD/runs/${name}.log" 2>&1 ); rc=$?
    n=$((n+1)); echo "$n,$S,$tag,$envs,$st,$(date +%FT%T),$rc" >> "$OUTD/run_order.csv"
  done
done
echo BATCH_DONE >> "$OUTD/run_order.csv"
