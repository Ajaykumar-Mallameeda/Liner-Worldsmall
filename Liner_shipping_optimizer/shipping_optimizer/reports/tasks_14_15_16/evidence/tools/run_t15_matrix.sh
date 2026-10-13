#!/usr/bin/env bash
# Task 15 paired-seed matrix: one process per seed, same pool, strategies run sequentially
# inside each process (so every strategy of a seed sees the identical candidate pool).
ROOT="${1:?tree root}"; TL="${2:-120}"; TAG="${3:-t15_matrix}"; shift 3
STRATS="${@:-prod fullint two:40 two:60 A_sa A_pert highs}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
OUT="$PROJ/reports/tasks_14_15_16/evidence/outputs"
RUNS="$PROJ/reports/tasks_14_15_16/evidence/runs"
for SEED in 0 1 2 3 4; do
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 "$PROJ/venv/Scripts/python.exe" -I \
    "$PROJ/reports/tasks_14_15_16/evidence/tools/global_stage_experiment.py" \
    "$ROOT" "$OUT/${TAG}_seed${SEED}.json" $SEED $TL $STRATS \
    > "$RUNS/${TAG}_seed${SEED}.log" 2>&1 &
done
wait
echo done
