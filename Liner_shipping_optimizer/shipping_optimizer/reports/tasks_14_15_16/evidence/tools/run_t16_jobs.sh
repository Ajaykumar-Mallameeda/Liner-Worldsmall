#!/usr/bin/env bash
# Task 16 controlled runs: one process per (seed, filter variant, solver); at most PAR at once.
#
#   solver "cbc"    = production strategy (LP-guided restriction, CBC), 120 s
#   solver "highs"  = production opt-in HiGHS backend, unrestricted, 600 s (proves the optimum of
#                     the pool when it can: a deterministic measure of what the POOL is worth,
#                     independent of how well a time-limited heuristic happens to search it)
#
# usage: run_t16_jobs.sh <tree_root> <tag> <par> "<seeds>" "<variants>" "<solvers>"
ROOT="${1:?tree root}"; TAG="${2:?tag}"; PAR="${3:?par}"
SEEDS="${4:?seeds}"; VARIANTS="${5:?variants}"; SOLVERS="${6:?solvers}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
OUT="$PROJ/reports/tasks_14_15_16/evidence/outputs"
RUNS="$PROJ/reports/tasks_14_15_16/evidence/runs"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
jobs_file="$(mktemp)"
# longest jobs first so the tail of the queue is short
for SOLVER in highs cbc; do for V in $VARIANTS; do for S in $SEEDS; do
  echo "$S $V $SOLVER" >> "$jobs_file"
done; done; done
run_one() {
  S="$1"; V="$2"; SOLVER="$3"
  NAME="${TAG}_seed${S}_${V}_${SOLVER}"
  if [ "$SOLVER" = "highs" ]; then
    TL=600; export NETWORK_MILP_BACKEND=highs
  else
    TL=120; unset NETWORK_MILP_BACKEND
  fi
  export T16_FILTER="$V"
  # candidate diagnostics (stand-alone economics of every candidate) once per seed, on legacy
  if [ "$V" = "legacy" ] && [ "$SOLVER" = "cbc" ]; then export T15_POOL_DIAG=1; else unset T15_POOL_DIAG; fi
  "$PROJ/venv/Scripts/python.exe" -I "$PROJ/reports/tasks_14_15_16/evidence/tools/global_stage_experiment.py" \
    "$ROOT" "$OUT/${NAME}.json" "$S" "$TL" prod > "$RUNS/${NAME}.log" 2>&1
}
export -f run_one
export ROOT TAG OUT RUNS PROJ
< "$jobs_file" xargs -P "$PAR" -L 1 bash -c 'run_one "$0" "$1" "$2"'
echo done
