#!/usr/bin/env bash
# End-to-end orchestrator (GA + regional MILP + global stage) from a scratch tree WITHOUT .env (no external LLM calls; rule-based fallback).
# usage: run_e2e.sh <tag> "<ENV=VAL,ENV=VAL|->"
TREE="C:/Users/WINDOWS/Liner-Worldsmall_exp/tree_e2e/Liner_shipping_optimizer/shipping_optimizer"
OUT="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/reports/class_mismatch_campaign/e2e"
PY="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer/venv/Scripts/python.exe"
tag="$1"; envs="$2"
for v in $(env | grep -oE '^(TREE|LINER_|NETWORK_MILP|GLOBAL_STAGE|T15_|T16_|T22_|GROQ_API_KEY|CEREBRAS_API_KEY|GOOGLE_API_KEY)[A-Za-z0-9_]*'); do unset "$v"; done
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 LINER_SEED=0
if [ "$envs" != "-" ]; then IFS=',' read -ra KV <<< "$envs"; for kv in "${KV[@]}"; do export "$kv"; done; fi
st=$(date +%FT%T)
( cd "$TREE" && "$PY" tests/test_orchestrator.py > "$OUT/${tag}.log" 2>&1 ); rc=$?
cp "$TREE/pipeline_output.json" "$OUT/${tag}_pipeline_output.json" 2>/dev/null
echo "$tag,$envs,$st,$(date +%FT%T),$rc" >> "$OUT/e2e_order.csv"
