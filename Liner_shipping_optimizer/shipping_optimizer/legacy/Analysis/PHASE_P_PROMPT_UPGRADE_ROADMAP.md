# PHASE P — P7: PROMPT UPGRADE ROADMAP

## ROI Rankings

| Rank | Opportunity | Effort | Impact | Risk | Phase |
|---|---|---|---|---|---|
| **1** | Fix executive summary bug (Prompt #7 empty response) | 1 hour | **CRITICAL** - eliminates corrupted output | None | P+1a |
| **2** | Merge/remove display-only prompts (#2, #4, #6) | 2 hours | **40% cost reduction** | Low | P+1a |
| **3** | Inject SharedContext into coordinator (#1) | 4 hours | **Weight decisions informed by full state** | Medium | P+1b |
| **4** | Inject regional metrics into service gen (#3) | 3 hours | **Service pools aligned with regions** | Low | P+1b |
| **5** | Inject convergence history into coordinator (#1) | 3 hours | **Prevent weight oscillations** | Medium | P+1b |
| **6** | Add trade-off reasoning to coordinator (#1) | 4 hours | **Better coverage-vs-profit decisions** | Medium | P+1c |
| **7** | Inject consensus-awareness into all active prompts | 4 hours | **Agents know how decisions were modified** | Medium | P+1c |
| **8** | Cross-region network effects in coordinator | 8 hours | **Global optimization awareness** | High | P+1d |
| **9** | Inject fleet economics awareness | 6 hours | **Better vessel assignment** | Medium | P+1d |
| **10** | Inject regional intelligence metrics into coordinator | 3 hours | **Region-aware global decisions** | Low | P+1b |

## Suggested Sprint Plan: P+1

### Sprint P+1a — Quick Wins (1-2 days)
1. Fix Prompt #7: Replace LLM call with rule-based fallback (remove the buggy code path)
2. Merge Prompt #2 into #3: Combine strategy + archetype into single JSON prompt
3. Merge Prompt #4 into #5: Combine regional strategy + explanation into single assessment prompt
4. Remove Prompt #6: Delete the analyze_problem() LLM call, use fallback directly

### Sprint P+1b — Context Injection (2-3 days)
1. Inject SharedContext dict into Coordinator Decisions prompt
2. Inject top-3 regional metrics into ServiceGen Archetype prompt
3. Inject iteration history into Coordinator prompt
4. Inject regional priority data into Coordinator prompt

### Sprint P+1c — Intelligence (3-4 days)
1. Add trade-off reasoning: "If coverage_weight increases, profit_weight must decrease — quantify the trade-off"
2. Add consensus awareness: "Your previous weight suggestion was modified to X by consensus — comment"
3. Add convergence awareness: "Last 3 iterations had trajectory X — what should change?"

### Sprint P+1d — Advanced (future)
1. Cross-region network effects reasoning
2. Fleet economics injection
3. Risk assessment reasoning

## Expected Outcomes

| Metric | Current | After P+1a | After P+1b | After P+1c |
|---|---|---|---|---|
| LLM calls per run | 9 | 6 (-33%) | 6 | 6 |
| Prompt token waste | 54% | ~15% | ~15% | ~10% |
| Convergence iterations | 2 (no convergence) | 2 | 2-3 (may converge) | 2-3 (converges) |
| Coverage delta/iteration | -1.7pp | n/a | +3-5pp | +5-8pp |
| Bug count | 1 critical | 0 | 0 | 0 |
