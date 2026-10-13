#!/usr/bin/env bash
FR="$1"; OUT="$2"
for s in 0 1 2 3 4; do
  bash run_arms.sh "$FR" "$s" 120 "A=-" "$OUT/L2_sequential"
  bash run_arms.sh "$FR" "$s" 120 "B=LINER_MILP_VUB=1" "$OUT/L2_sequential"
  bash run_arms.sh "$FR" "$s" 120 "C=LINER_MILP_VUB=1,LINER_LOCAL_SEARCH=1" "$OUT/L2_sequential"
done
echo L2_DONE
