#!/usr/bin/env bash
# Controlled global-stage batch: one process per seed, at most PAR at once, all from ONE snapshot tree.
#
# usage: run_batch.sh <snapshot_root> <tag> <par> "<seeds>" <time_limit_sec> <strategy> [NAME=VALUE ...]
#   NAME=VALUE pairs are exported to the run (e.g. LINER_MILP_VUB=1).  Every LINER_* / NETWORK_MILP_* /
#   GLOBAL_STAGE_* / T15_* variable of the caller is unset first, so a run sees ONLY what is listed.
# Output: <campaign>/evidence/outputs/<tag>_seed<S>.json, <campaign>/evidence/runs/<tag>_seed<S>.log
ROOT="${1:?snapshot root}"; TAG="${2:?tag}"; PAR="${3:?par}"; SEEDS="${4:?seeds}"; TL="${5:?time limit}"
STRAT="${6:-prod}"; shift 6
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
for kv in "$@"; do export "$kv"; done
run_one() {
  S="$1"
  NAME="${TAG}_seed${S}"
  "$PROJ/venv/Scripts/python.exe" "$CAMP/tools/global_stage_experiment.py" "$ROOT" "$CAMP/outputs/${NAME}.json" "$S" "$TL" "$STRAT" \
    > "$CAMP/runs/${NAME}.log" 2>&1
  echo "done $NAME rc=$? $(date +%H:%M:%S)"
}
export -f run_one
export ROOT TAG TL STRAT PROJ CAMP
echo "$SEEDS" | tr ' ' '\n' | xargs -P "$PAR" -I{} bash -c 'run_one {}'
echo "BATCH_DONE $TAG $(date +%H:%M:%S)"
