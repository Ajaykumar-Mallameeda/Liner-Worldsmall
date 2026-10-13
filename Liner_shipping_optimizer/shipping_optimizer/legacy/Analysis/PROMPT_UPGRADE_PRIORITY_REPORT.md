# PROMPT UPGRADE PRIORITY REPORT

## Ranked by Measured Influence Rather Than Theoretical Potential

**Date:** 2026-06-23 | **Method:** Phase P+0 experimental evidence

---

## Priority Ranking

| Rank | Upgrade | Measured Influence | Potential Impact | Risk | Priority |
|---|---|---|---|---|---|
| 1 | Fix LLM client reliability for JSON prompts | **0% → Expected 80%+** | Critical | Low | **URGENT** |
| 2 | Fix executive summary serialization bug | 0% (broken) → Reliable | Correctness | None | **IMMEDIATE** |
| 3 | Inject SharedContext into coordinator | N/A → High | 3-8pp coverage/iter | Medium | HIGH |
| 4 | Inject iteration history into coordinator | N/A → High | Prevents weight oscillation | Medium | HIGH |
| 5 | Simplify JSON output format (fewer constraints) | 0% → 50%+ success | Enables LLM decisions | Low | HIGH |
| 6 | Merge/remove display-only prompts | 54% waste → 15% waste | Cost reduction | None | MEDIUM |
| 7 | Inject regional intelligence into ServiceGen | N/A → Medium | Differentiated service pools | Low | MEDIUM |
| 8 | Add trade-off reasoning to coordinator | N/A → Medium | Better weight decisions | Medium | MEDIUM |
| 9 | Consensus awareness injection | ~1% → ~15% | Meaningful reconciliation | Medium | LOW |
| 10 | Cross-region network effects | N/A → High (complex) | Global optimization | High | FUTURE |

---

## Rank 1: Fix LLM Client Reliability for JSON Prompts

**Evidence:** Both JSON-format prompts failed 100% of the time. Free-text prompts worked.
**Root cause:** Either:
- LLM model (deepseek-v4-flash-free) cannot reliably produce structured JSON
- JSON parsing in `_parse_json_safe()` is too fragile
- LLM circuit breaker opened early due to unrelated failures

**Action:**
1. Verify LLM client connectivity independently
2. Add explicit logging for "AI_REJECTED: JSON parse failed" at coordinator level
3. Consider prompt-only JSON formatting improvements (simpler schema, fewer required fields)
4. Or swap fallback: try JSON, if it fails, use a smarter structured fallback

**Expected gain:** From 0% → 80%+ success rate for coordinator weight suggestions

---

## Rank 2: Fix Executive Summary Bug

**Evidence:** Empty LLM content → `str(message)` produces raw API object in pipeline output
**Action:** Check `message.content` is non-empty before using; fall back to rule-based summary
**Expected gain:** Eliminates corrupted pipeline output, reduces silent data quality issues

---

## Rank 3: Inject SharedContext into Coordinator

**Evidence:** SharedContext has all data needed for informed decisions; none reaches prompts
**Action:** Add `SharedContext.to_dict()` as additional context in `_generate_decisions()` prompt
**Expected gain:** Prevents weight oscillation, enables evidence-based decisions

---

## Rank 4: Inject Iteration History

**Evidence:** Iteration 0→1 produced worse outcomes but iteration 1 had no memory of this
**Action:** Include last 2-3 iterations' weight/coverage/profit trajectory in coordinator prompt
**Expected gain:** Prevents repeating failed strategies, enables adaptive weight adjustment

---

## Verdict

**Two actions are prerequisite to all prompt upgrades:**
1. Fix LLM reliability (Rank 1) — without this, no prompt change matters
2. Fix executive summary bug (Rank 2) — data corruption undermines trust

Only after Ranks 1-2 should SharedContext injection (Ranks 3-4) proceed. The Phase P assessment ("VERDICT C — redesign required") is confirmed, but the root cause is infrastructure reliability, not prompt quality.
