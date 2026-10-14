#!/usr/bin/env bash
# Sequential job runner. usage: run_job_list.sh <jobs.tsv> <out_dir>
# jobs.tsv columns (tab separated): tag, seed, tree_root, env (comma separated NAME=VAL or "-")
# A job whose output already exists is skipped (re-runs never overwrite).  Order = file order.
JOBS="$1"; OUTD="$2"
HERE="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/decision_phase/d05_final"
PY="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/venv/Scripts/python.exe"
mkdir -p "$OUTD/outputs" "$OUTD/runs"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
[ -f "$OUTD/run_order.tsv" ] || printf 'seq\ttag\tseed\ttree\tenv\tstart\tend\trc\n' > "$OUTD/run_order.tsv"
n=$(($(wc -l < "$OUTD/run_order.tsv")-1))
while IFS=$'\t' read -r tag seed tree envs; do
  [ -z "$tag" ] && continue
  name="${tag}_seed${seed}"
  [ -f "$OUTD/outputs/${name}.json" ] && continue
  st=$(date +%FT%T)
  ( if [ "$envs" != "-" ]; then IFS=',' read -ra KV <<< "$envs"; for kv in "${KV[@]}"; do export "$kv"; done; fi
    "$PY" "$HERE/global_stage_experiment.py" "$tree" "$OUTD/outputs/${name}.json" "$seed" 120 prod > "$OUTD/runs/${name}.log" 2>&1 ); rc=$?
  n=$((n+1)); printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$n" "$tag" "$seed" "$tree" "$envs" "$st" "$(date +%FT%T)" "$rc" >> "$OUTD/run_order.tsv"
done < "$JOBS"
echo JOBS_DONE >> "$OUTD/run_order.tsv"
