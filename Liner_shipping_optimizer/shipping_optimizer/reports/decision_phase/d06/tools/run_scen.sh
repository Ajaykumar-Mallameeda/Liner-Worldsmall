#!/usr/bin/env bash
# For each seed the reference (frozen commit tree) and every scenario tree run concurrently with the SAME flags (arg 4).
SEEDS="$1"; TREES="$2"; OUTD="$3"; FLAGS="$4"; REF="$5"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
PY="$PROJ/venv/Scripts/python.exe"; H="$PROJ/reports/issue2_corrected_baseline/tools/global_stage_experiment.py"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
IFS=',' read -ra KV <<< "$FLAGS"; for kv in "${KV[@]}"; do export "$kv"; done
mkdir -p "$OUTD/outputs" "$OUTD/runs"
for S in $SEEDS; do
  "$PY" "$H" "$REF" "$OUTD/outputs/REF_seed$S.json" $S 120 prod > "$OUTD/runs/REF_seed$S.log" 2>&1 &
  for T in T_rev T_dwell175 T_dwell70 T_stay12 T_stay48; do
    "$PY" "$H" "$TREES/$T" "$OUTD/outputs/${T}_seed$S.json" $S 120 prod > "$OUTD/runs/${T}_seed$S.log" 2>&1 &
  done
  wait
  echo "seed $S done $(date +%H:%M:%S)"
done
echo SCEN_DONE
