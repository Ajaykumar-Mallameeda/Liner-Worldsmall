#!/usr/bin/env bash
# Sequential paired batch on a frozen tree. usage: run_paired_sequential.sh "<seeds>" "<tag>=<ENV,ENV|->;<tag>=..." <order_mode>
# order_mode alt: even seeds run arms in listed order, odd seeds reversed (order effect is recorded in run_order.csv).
ROOT="C:/Users/WINDOWS/Liner-Worldsmall_exp/tree_49ecd92/Liner_shipping_optimizer/shipping_optimizer"
HERE="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/decision_phase/d05_final"
OUTD="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/current_code_experiment"
PY="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/venv/Scripts/python.exe"
SEEDS="$1"; ARMS="$2"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
IFS=';' read -ra L <<< "$ARMS"
[ -f "$OUTD/run_order.csv" ] || echo "seq,seed,arm,env,start,end,rc" > "$OUTD/run_order.csv"
n=$(wc -l < "$OUTD/run_order.csv")
for S in $SEEDS; do
  ORD=("${L[@]}"); if [ $((S%2)) -eq 1 ]; then ORD=(); for ((i=${#L[@]}-1;i>=0;i--)); do ORD+=("${L[$i]}"); done; fi
  for a in "${ORD[@]}"; do
    tag="${a%%=*}"; envs="${a#*=}"; name="${tag}_seed${S}"
    [ -f "$OUTD/outputs/${name}.json" ] && continue
    st=$(date +%FT%T)
    ( if [ "$envs" != "-" ]; then IFS=',' read -ra KV <<< "$envs"; for kv in "${KV[@]}"; do export "$kv"; done; fi
      "$PY" "$HERE/global_stage_experiment.py" "$ROOT" "$OUTD/outputs/${name}.json" "$S" 120 prod > "$OUTD/runs/${name}.log" 2>&1 ); rc=$?
    n=$((n+1)); echo "$n,$S,$tag,$envs,$st,$(date +%FT%T),$rc" >> "$OUTD/run_order.csv"
  done
done
echo BATCH_DONE >> "$OUTD/run_order.csv"
