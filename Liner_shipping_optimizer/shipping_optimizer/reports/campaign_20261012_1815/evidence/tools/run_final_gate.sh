#!/usr/bin/env bash
# Final-tree gate, chained after run_extra.sh: snapshot the live tree (T10_final = T9 + the per-region/iteration candidate
# stream label + the orchestrator test's flag assertions), then
#   G10_fin  orchestrator x3, final configuration, unseeded
#   G10_base orchestrator x3, no flag (assertion count must be 362 + 2)
#   R2c / R2d  orchestrator x3 each with LINER_SEED = 11 / 12 and the final configuration
#   FINAL_suite  whole test suite (orchestrator test excluded) from an isolated copy
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
T="$CAMP/tools"; R="$CAMP/runs"
until grep -q EXTRA_DONE "$R/P5_extra.driver.txt" 2>/dev/null; do sleep 30; done
echo "=== SNAPSHOT $(date +%H:%M:%S)"
"$PROJ/venv/Scripts/python.exe" -I "$T/mksnap.py" T10_final
SNAP="D:/liner_scratch/snap_T10_final"
FIN="LINER_MILP_VUB=1,LINER_LOCAL_SEARCH=1,LINER_CLASS_VARIANTS=0.10"
echo "=== G10_fin $(date +%H:%M:%S)";  bash "$T/run_orch.sh" "$SNAP" G10_fin 3 "$FIN" > "$R/G10_fin.driver.txt" 2>&1
echo "=== G10_base $(date +%H:%M:%S)"; bash "$T/run_orch.sh" "$SNAP" G10_base 3 "-" > "$R/G10_base.driver.txt" 2>&1
echo "=== R2c $(date +%H:%M:%S)";      bash "$T/run_orch.sh" "$SNAP" R2c_seed11 3 "LINER_SEED=11,${FIN}" > "$R/R2c.driver.txt" 2>&1
echo "=== R2d $(date +%H:%M:%S)";      bash "$T/run_orch.sh" "$SNAP" R2d_seed12 3 "LINER_SEED=12,${FIN}" > "$R/R2d.driver.txt" 2>&1
echo "=== FINAL_suite $(date +%H:%M:%S)"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_|BUNKER_)[A-Za-z0-9_]*'); do unset "$v"; done
SNAP_SOURCE="$SNAP" "$PROJ/venv/Scripts/python.exe" -I "$T/snaprun.py" FINAL_suite FINAL_suite -- tests --ignore=tests/test_orchestrator.py -q -p no:cacheprovider --tb=line > "$R/FINAL_suite.driver.txt" 2>&1
echo "GATE_DONE $(date +%H:%M:%S)"
