#!/usr/bin/env bash
# Re-run of the final-tree gate after run_final_gate.sh's orchestrator groups aborted in seconds: the test file in snapshot T10
# had a syntax error introduced by a patch (a literal newline inside an f-string).  Fixed in the live tree; snapshot T11_final
# is made from it.  Order: T10 suite finishes first (idle machine), then
#   G11_fin  orchestrator x3, final configuration, unseeded      G11_base  orchestrator x3, no flag
#   R2e / R2f  orchestrator x3 each, LINER_SEED = 11 / 12 + final configuration
#   FINAL2_suite  whole suite (orchestrator test excluded) from an isolated copy of T11
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
T="$CAMP/tools"; R="$CAMP/runs"
until grep -q "^GATE_DONE" "$R/P5_final_gate.driver.txt" 2>/dev/null; do sleep 15; done
echo "=== SNAPSHOT $(date +%H:%M:%S)"
"$PROJ/venv/Scripts/python.exe" -I "$T/mksnap.py" T11_final
SNAP="D:/liner_scratch/snap_T11_final"
FIN="LINER_MILP_VUB=1,LINER_LOCAL_SEARCH=1,LINER_CLASS_VARIANTS=0.10"
echo "=== G11_fin $(date +%H:%M:%S)";  bash "$T/run_orch.sh" "$SNAP" G11_fin 3 "$FIN" > "$R/G11_fin.driver.txt" 2>&1
echo "=== G11_base $(date +%H:%M:%S)"; bash "$T/run_orch.sh" "$SNAP" G11_base 3 "-" > "$R/G11_base.driver.txt" 2>&1
echo "=== R2e $(date +%H:%M:%S)";      bash "$T/run_orch.sh" "$SNAP" R2e_seed11 3 "LINER_SEED=11,${FIN}" > "$R/R2e.driver.txt" 2>&1
echo "=== R2f $(date +%H:%M:%S)";      bash "$T/run_orch.sh" "$SNAP" R2f_seed12 3 "LINER_SEED=12,${FIN}" > "$R/R2f.driver.txt" 2>&1
echo "=== FINAL2_suite $(date +%H:%M:%S)"
for v in $(env | grep -oE '^(LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_|BUNKER_)[A-Za-z0-9_]*'); do unset "$v"; done
SNAP_SOURCE="$SNAP" "$PROJ/venv/Scripts/python.exe" -I "$T/snaprun.py" FINAL2_suite FINAL2_suite -- tests --ignore=tests/test_orchestrator.py -q -p no:cacheprovider --tb=line > "$R/FINAL2_suite.driver.txt" 2>&1
echo "GATE2_DONE $(date +%H:%M:%S)"
