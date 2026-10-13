#!/usr/bin/env bash
# Phases 5 - 7 as ONE unattended, strictly sequential driver (every step sees an otherwise idle machine).
#
# usage: run_remaining.sh <final_snapshot> "<FINAL_ENV: NAME=VAL,NAME=VAL>" "<LS_ENV>" "<LV_ENV>" [start_step] [end_step]
#   FINAL_ENV = the combined configuration under acceptance (C1 + LS + expansion)
#   LS_ENV    = local search only (the strongest single change of Phase 3)
#   LV_ENV    = FINAL_ENV plus the search-only variants (experimental arm)
# Steps (each writes its own driver file; a failed step does not stop the next):
#   1 D5   dev seeds 0-9    4 arms concurrent: base / ls / e (no search-only variants) / fin
#   2 C9   hold-out 10-19 re-run on the FINAL code (after the idle-service / owner fixes), same arms
#   3 O_fin    orchestrator x3 concurrent, FINAL_ENV, unseeded
#   4 O_base   orchestrator x3, flags off (regression gate on the final tree)
#   5 O_ls     orchestrator x3, LS only
#   6 R2a / R2b orchestrator x3 each with LINER_SEED=11 / 12 and FINAL_ENV
#   7 R1   duplicates: base x2 + fin x2 concurrent, seeds 0-4 (replicate noise under identical load)
#   8 S2   sensitivity: (base, fin) x 2 scenarios per group, seeds 0-2, 4 groups
SNAP="${1:?final snapshot dir}"; FIN="${2:?final env}"; LSE="${3:-LINER_LOCAL_SEARCH=1}"; LVENV="${4:?experimental env (final + search-only variants)}"; START="${5:-1}"; END="${6:-8}"
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
T="$CAMP/tools"; R="$CAMP/runs"
step() { echo "=== STEP $1 $(date +%H:%M:%S)"; }
S=$START
if [ "$S" -le 1 ] && [ "$END" -ge 1 ]; then step 1; bash "$T/run_arms.sh" "$SNAP" "0 1 2 3 4 5 6 7 8 9" 120 \
  "D5_base=-;D5_ls=${LSE};D5_e=${FIN};D5_fin=${LVENV}" > "$R/D5.driver.txt" 2>&1; fi
if [ "$S" -le 2 ] && [ "$END" -ge 2 ]; then step 2; bash "$T/run_arms.sh" "$SNAP" "10 11 12 13 14 15 16 17 18 19" 120 \
  "C9_base=-;C9_ls=${LSE};C9_fin=${FIN};C9_lv=${LVENV}" > "$R/C9.driver.txt" 2>&1; fi
if [ "$S" -le 3 ] && [ "$END" -ge 3 ]; then step 3; bash "$T/run_orch.sh" "$SNAP" O5_fin 3 "$FIN" > "$R/O5_fin.driver.txt" 2>&1; fi
if [ "$S" -le 4 ] && [ "$END" -ge 4 ]; then step 4; bash "$T/run_orch.sh" "$SNAP" O5_base 3 "-" > "$R/O5_base.driver.txt" 2>&1; fi
if [ "$S" -le 5 ] && [ "$END" -ge 5 ]; then step 5; bash "$T/run_orch.sh" "$SNAP" O5_ls 3 "$LSE" > "$R/O5_ls.driver.txt" 2>&1; fi
if [ "$S" -le 6 ] && [ "$END" -ge 6 ]; then step 6;
  bash "$T/run_orch.sh" "$SNAP" R2a_seed11 3 "LINER_SEED=11,${FIN}" > "$R/R2a.driver.txt" 2>&1
  bash "$T/run_orch.sh" "$SNAP" R2b_seed12 3 "LINER_SEED=12,${FIN}" > "$R/R2b.driver.txt" 2>&1; fi
if [ "$S" -le 7 ] && [ "$END" -ge 7 ]; then step 7; bash "$T/run_arms.sh" "$SNAP" "0 1 2 3 4" 120 \
  "R1_baseA=-;R1_baseB=-;R1_finA=${FIN};R1_finB=${FIN}" > "$R/R1.driver.txt" 2>&1; fi
if [ "$S" -le 8 ] && [ "$END" -ge 8 ]; then step 8;
  bash "$T/run_arms_roots.sh" "0 1 2" 120 \
    "S1_base@D:/liner_scratch/snap_S3_S1_tt=-;S1_fin@D:/liner_scratch/snap_S3_S1_tt=${FIN};S2_base@D:/liner_scratch/snap_S3_S2_cap2=-;S2_fin@D:/liner_scratch/snap_S3_S2_cap2=${FIN}" > "$R/S2_g1.driver.txt" 2>&1
  bash "$T/run_arms_roots.sh" "0 1 2" 120 \
    "S3a_base@D:/liner_scratch/snap_S3_S3a_port12=-;S3a_fin@D:/liner_scratch/snap_S3_S3a_port12=${FIN};S3b_base@D:/liner_scratch/snap_S3_S3b_port48=-;S3b_fin@D:/liner_scratch/snap_S3_S3b_port48=${FIN}" > "$R/S2_g2.driver.txt" 2>&1
  bash "$T/run_arms_roots.sh" "0 1 2" 120 \
    "S4a_base@D:/liner_scratch/snap_S3_S4a_dwell=-;S4a_fin@D:/liner_scratch/snap_S3_S4a_dwell=${FIN};S4b_base@D:/liner_scratch/snap_S3_S4b_dwell=-;S4b_fin@D:/liner_scratch/snap_S3_S4b_dwell=${FIN}" > "$R/S2_g3.driver.txt" 2>&1
  bash "$T/run_arms_roots.sh" "0 1 2" 120 \
    "B400_base@${SNAP}=BUNKER_UNIFORM_USD_PER_T=400;B400_fin@${SNAP}=BUNKER_UNIFORM_USD_PER_T=400,${FIN};B1000_base@${SNAP}=BUNKER_UNIFORM_USD_PER_T=1000;B1000_fin@${SNAP}=BUNKER_UNIFORM_USD_PER_T=1000,${FIN}" > "$R/S2_g4.driver.txt" 2>&1
fi
echo "ALL_DONE $(date +%H:%M:%S)"
