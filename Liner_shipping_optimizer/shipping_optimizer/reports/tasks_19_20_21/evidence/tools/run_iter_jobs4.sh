#!/usr/bin/env bash
# Tasks 19-21 ITERATION-structured controlled runs (3 iterations per seed; see
# iteration_experiment.py): one process per (seed, variant); at most PAR at once.
#
# usage: run_jobs.sh <tree_root> <tag> <par> "<seeds>" "<variants>" <solver> <time_limit_sec> [strategy]
#   solver   cbc   = production global stage (LP-guided restriction, CBC)
#            highs = opt-in NETWORK_MILP_BACKEND=highs (labelled experimental: not the default)
#   variant  names are defined in the case statement below (path / candidate configuration)
#   strategy harness strategy name, default "prod" (the production solve step)
#
# The tree root is a SNAPSHOT (D:/liner_scratch/snap_*), so every output is tied to one tree hash.
ROOT="${1:?tree root}"; TAG="${2:?tag}"; PAR="${3:?par}"
SEEDS="${4:?seeds}"; VARIANTS="${5:?variants}"; SOLVER="${6:?solver}"; TL="${7:?time limit}"
STRAT="${8:-prod}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
EV="$PROJ/reports/tasks_19_20_21/evidence"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
jobs_file="$(mktemp)"
for V in $VARIANTS; do for S in $SEEDS; do echo "$S $V" >> "$jobs_file"; done; done
run_one() {
  S="$1"; V="$2"
  NAME="${TAG}_seed${S}_${V}_${SOLVER}${TL}"
  unset LINER_PATH_SELECTION LINER_MAX_TRANSFERS LINER_PATH_BUDGET LINER_PATH_MULTI_HOP_MIN_ALT \
        LINER_REGIONAL_FILTER LINER_DEMAND_LOOP_BUDGET LINER_CLASS_SCREEN T15_MAX_PATHS \
        LINER_ROUTE_OPERATORS LINER_ELITISM LINER_CLASS_TIME_FEASIBLE LINER_PATH_HYBRID_SLOTS \
        NETWORK_MILP_BACKEND
  case "$V" in
    D)     ;;                                            # the accepted default configuration (no switch)
    RB)    export LINER_FLOW_REOPT=0 LINER_PROFIT_FLOOR_REPAIR=0 LINER_MAX_TRANSFERS=1                   LINER_PATH_SELECTION=fastest LINER_PATH_BUDGET=fixed LINER_CLASS_TIME_FEASIBLE=0                   LINER_ROUTE_OPERATORS=0 LINER_ELITISM=0 ;;     # documented rollback = frozen B0
    DCOV25) export LINER_GLOBAL_MIN_COVERAGE=0.25 ;;    # opt-in epsilon constraint (experimental)
    DCOV27) export LINER_GLOBAL_MIN_COVERAGE=0.27 ;;
    DEL)   export LINER_ELITISM=1 ;;
    DELOP) export LINER_ELITISM=1 LINER_ROUTE_OPERATORS=30 ;;
    DOP)   export LINER_ROUTE_OPERATORS=30 ;;
    DF2)   export LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;
    *) echo "unknown variant $V" >&2; return 2 ;;
  esac
  if [ "$SOLVER" = "highs" ]; then export NETWORK_MILP_BACKEND=highs; fi
  "$PROJ/venv/Scripts/python.exe" -I "$EV/tools/iteration_experiment.py" \
    "$ROOT" "$EV/outputs/${NAME}.json" "$S" "$TL" 3 > "$EV/runs/${NAME}.log" 2>&1
  echo "done $NAME rc=$?"
}
export -f run_one
export ROOT TAG SOLVER TL STRAT EV PROJ
< "$jobs_file" xargs -P "$PAR" -L 1 bash -c 'run_one "$0" "$1"'
echo "BATCH_DONE $TAG"
