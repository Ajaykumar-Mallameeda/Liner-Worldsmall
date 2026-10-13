#!/usr/bin/env bash
# Tasks 19-21 controlled runs: one process per (seed, variant); at most PAR at once.
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
    B0)    ;;                                                       # frozen Tasks 14-16 configuration
    P10)   export T15_MAX_PATHS=10 ;;
    B30)   export T15_MAX_PATHS=30 ;;                               # larger-path reference (fastest)
    C)     export LINER_PATH_SELECTION=cost_aware ;;
    C30)   export LINER_PATH_SELECTION=cost_aware T15_MAX_PATHS=30 ;;   # larger-path reference
    CA)    export LINER_PATH_SELECTION=cost_aware LINER_PATH_BUDGET=adaptive ;;
    CM)    export LINER_PATH_SELECTION=cost_aware LINER_MAX_TRANSFERS=2 ;;
    CMALL) export LINER_PATH_SELECTION=cost_aware LINER_MAX_TRANSFERS=2 LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;
    CAMALL) export LINER_PATH_SELECTION=cost_aware LINER_PATH_BUDGET=adaptive LINER_MAX_TRANSFERS=2 \
                   LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;
    FMALL) export LINER_MAX_TRANSFERS=2 LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;   # fastest + two transfers
    F1)    export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 ;;
    F2)    export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;
    F1A)   export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_PATH_BUDGET=adaptive ;;
    F1T)   export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_CLASS_TIME_FEASIBLE=1 ;;
    F1O)   export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_ROUTE_OPERATORS=30 ;;
    F1AT)  export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_PATH_BUDGET=adaptive LINER_CLASS_TIME_FEASIBLE=1 ;;
    F1ATO) export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_PATH_BUDGET=adaptive LINER_CLASS_TIME_FEASIBLE=1 LINER_ROUTE_OPERATORS=30 ;;
    R)     export LINER_FLOW_REOPT=1 ;;                                     # B0 + flow re-optimisation
    RC)    export LINER_FLOW_REOPT=1 LINER_PATH_SELECTION=cost_aware ;;
    RFA)   export LINER_FLOW_REOPT=1 LINER_PATH_BUDGET=adaptive ;;
    RH3)   export LINER_FLOW_REOPT=1 LINER_PATH_SELECTION=hybrid ;;
    RMH)   export LINER_FLOW_REOPT=1 LINER_MAX_TRANSFERS=2 LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;
    RTF)   export LINER_FLOW_REOPT=1 LINER_CLASS_TIME_FEASIBLE=1 ;;
    ROP)   export LINER_FLOW_REOPT=1 LINER_ROUTE_OPERATORS=30 ;;
    RTFOP) export LINER_FLOW_REOPT=1 LINER_CLASS_TIME_FEASIBLE=1 LINER_ROUTE_OPERATORS=30 ;;
    RFULL) export LINER_FLOW_REOPT=1 LINER_PATH_SELECTION=hybrid LINER_PATH_BUDGET=adaptive LINER_MAX_TRANSFERS=2 LINER_CLASS_TIME_FEASIBLE=1 LINER_ROUTE_OPERATORS=30 ;;
    H3)    export LINER_PATH_SELECTION=hybrid ;;                            # 7 fastest + 3 cheapest
    H5)    export LINER_PATH_SELECTION=hybrid LINER_PATH_HYBRID_SLOTS=5 ;;
    FA)    export LINER_PATH_BUDGET=adaptive ;;                             # fastest ranking, adaptive budgets
    HMALL) export LINER_PATH_SELECTION=hybrid LINER_MAX_TRANSFERS=2 LINER_PATH_MULTI_HOP_MIN_ALT=100000 ;;
    HA)    export LINER_PATH_SELECTION=hybrid LINER_PATH_BUDGET=adaptive ;;
    TF)    export LINER_CLASS_TIME_FEASIBLE=1 ;;                           # Task 21-A
    OP)    export LINER_ROUTE_OPERATORS=30 ;;                              # Task 21-B (no feedback)
    TFOP)  export LINER_CLASS_TIME_FEASIBLE=1 LINER_ROUTE_OPERATORS=30 ;;
    FULL)  export LINER_PATH_SELECTION=hybrid LINER_PATH_BUDGET=adaptive LINER_MAX_TRANSFERS=2 \
                  LINER_CLASS_TIME_FEASIBLE=1 LINER_ROUTE_OPERATORS=30 ;;
    *) echo "unknown variant $V" >&2; return 2 ;;
  esac
  if [ "$SOLVER" = "highs" ]; then export NETWORK_MILP_BACKEND=highs; fi
  "$PROJ/venv/Scripts/python.exe" -I "$EV/tools/global_stage_experiment.py" \
    "$ROOT" "$EV/outputs/${NAME}.json" "$S" "$TL" "$STRAT" > "$EV/runs/${NAME}.log" 2>&1
  echo "done $NAME rc=$?"
}
export -f run_one
export ROOT TAG SOLVER TL STRAT EV PROJ
< "$jobs_file" xargs -P "$PAR" -L 1 bash -c 'run_one "$0" "$1"'
echo "BATCH_DONE $TAG"
