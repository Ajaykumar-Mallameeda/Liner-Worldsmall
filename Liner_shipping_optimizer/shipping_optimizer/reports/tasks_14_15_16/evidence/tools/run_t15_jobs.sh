#!/usr/bin/env bash
# Task 15/16 controlled runs with a CAP on concurrency.
#
# One process per (seed, strategy); at most PAR run at once.  Time-limited CBC incumbents
# depend on available CPU (measured: the same run at 10 concurrent processes on this 8-core /
# 16-thread machine lost 1-7 M USD/week), so a comparison is only valid when the load is the
# same for every strategy: all strategies below run under the same cap, nothing else heavy.
#
# usage: run_t15_jobs.sh <tree_root> <time_limit_s> <tag> <par> "<seeds>" "<strategies>" [extra env as K=V ...]
ROOT="${1:?tree root}"; TL="${2:?time limit}"; TAG="${3:?tag}"; PAR="${4:?parallelism}"
SEEDS="${5:?seeds}"; STRATS="${6:?strategies}"; shift 6
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
OUT="$PROJ/reports/tasks_14_15_16/evidence/outputs"
RUNS="$PROJ/reports/tasks_14_15_16/evidence/runs"
for kv in "$@"; do export "$kv"; done
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
jobs_file="$(mktemp)"
for S in $SEEDS; do for ST in $STRATS; do echo "$S $ST" >> "$jobs_file"; done; done
run_one() {
  S="$1"; ST="$2"
  SAFE="${ST//[:@]/_}"
  "$PROJ/venv/Scripts/python.exe" -I "$PROJ/reports/tasks_14_15_16/evidence/tools/global_stage_experiment.py" \
    "$ROOT" "$OUT/${TAG}_seed${S}_${SAFE}.json" "$S" "$TL" "$ST" > "$RUNS/${TAG}_seed${S}_${SAFE}.log" 2>&1
}
export -f run_one
export ROOT TL TAG OUT RUNS PROJ
< "$jobs_file" xargs -P "$PAR" -L 1 bash -c 'run_one "$0" "$1"'
echo done
