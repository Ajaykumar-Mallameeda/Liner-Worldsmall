# Structured LLM interface — paper-ready subsection

Source: `src/agents/base.py`, `src/llm/client.py`, `src/llm/providers/*`, the prompt builders in `src/agents/*.py` and `src/pipeline/iteration_selection.py`, and the validators in `src/validation/*`. Checked against the stored output of a Baltic run (`llm_runtime_metrics`, `llm_runtime_aggregate`). Written 2026-10-18.

Suggested place in the paper: Section "Methodology", after the description of the agents (it extends B.10 of `METHODOLOGY_FOR_PAPER.md`).

---

## X. Structured prompting interface of the language-model components

**Message structure.** Every language-model call is a two-message chat request: a fixed *system* message that states the agent's role and the rules of evidence, and a *user* message assembled by the calling agent. The user message is plain text. It is never a free-form question: the agent computes all quantities first (from the problem data or from the verified ledger), inserts them as numbers, and appends the format that the reply must follow. All calls use a low sampling temperature (0.1) and a bounded reply length (2,000 tokens). A provider router selects the model from the call's role (orchestrator, regional, service generator, coordinator, iteration selector), caches repeated requests, switches provider when one is rate-limited or unreachable, and returns the reply as a single string; provider, model, latency and error class are recorded separately for each call.

**Anatomy of a user message.** Each prompt has the same three blocks:

1. *Grounding block* — the numbers the reply may rely on, given as labelled lines (for example the counts of ports and lanes, total weekly demand in TEU, the share of the three largest corridors, and the five largest corridors as `origin -> destination: volume TEU/week`). For the decision calls this block carries the verified economics of the iteration (weekly profit, revenue, all-in cost, margin, coverage) and the list of weak regions.
2. *Decision context* (some calls) — a rule-based conclusion already reached by the system, such as the selected strategy or archetype and the rule that selected it. The model is asked to confirm and justify it with the supplied figures, not to discover it.
3. *Output contract* — either a fixed text template with named fields (`Strategy:`, `Reason 1:`, `Verdict:`, `Strengths:` …) in which every bullet must cite a supplied number, or, for machine-consumed replies, a JSON object whose keys and numeric ranges are stated in the prompt, introduced by the instruction "Return ONLY valid JSON (no markdown, no preamble)". Free-text prompts additionally end with an instruction to follow the format strictly.

**Calls and reply formats.**

| Call | Role | Grounding input | Reply format | Where the reply goes |
|---|---|---|---|---|
| Problem analysis | orchestrator | network size, total/average demand, density, top-5 share, top-5 corridors | text: `Size`, three `Complexity Drivers`, `Demand Concentration`, `Decomposition Rationale` | stored as narrative; not used by the optimiser |
| Regional strategy | regional | regional counts, median demand, top-3 share, hub ports, corridor table, rule-based decision | text: `Strategy` (A/B/C), `Selected`, `Reason 1`, `Reason 2`, `Hub Ports` | stored as narrative |
| Regional explanation | regional | regional solver results (profit, cost items, margin, coverage, unserved TEU), corridors | text: `Verdict` (Good/Moderate/Poor), `Strengths`, `Weaknesses`, `Improvement Actions` | stored as narrative |
| Service-design hint | service generator | network statistics and the rule-based archetype with its rationale | JSON: `direct_ratio`, `hub_loop_ratio`, `feeder_ratio`, `trunk_ratio` (each 0.05–0.80), `vessel_bias` (small / balanced / large), `hub_focus` (port IDs), `notes` | validated, then used as the mix of candidate families |
| Coordinator decision | coordinator | metrics of the iteration (verified profit, revenue, all-in cost, margin, regional and global coverage, evaluation score), number of conflicts, weak regions | JSON: `actions` (region, action, expected gain), `priorities`, `weight_adjustments` (profit, coverage, cost weights in [0, 1]), `notes` | weights validated, then passed to the feedback step |
| Iteration choice | iteration selector | one block per completed iteration (profit, all-in cost, margin, coverage, unserved volume, services, convergence score, conflicts, violations, regional lines) and the list of valid iteration numbers | JSON: `selected_iteration`, `confidence`, `reasoning`, `tradeoffs`, `objective_assessment` (profit, coverage, total cost, margin, regional balance) | accepted only if the iteration exists and is valid; otherwise the deterministic rule decides |

**Parsing and validation.** A reply is trimmed; for JSON replies, Markdown fences are removed and the object is parsed, with a second attempt that extracts the first `{…}` block. A validator then enforces the contract before anything is used: candidate-family ratios are clamped to [0.05, 0.80] and rescaled to sum to one, the vessel bias must be one of the three allowed values, the three weights are clamped and normalised to sum to one, and an iteration choice must belong to the set of valid iterations. Free-text replies must contain the required field names and at least one multi-digit number, and are re-requested once if they do not.

**Fallbacks and what the replies may influence.** If a call fails, times out, is rate-limited on all providers, or fails validation, the agent uses a rule-based result in the same format (a template filled with the same numbers, default family ratios, rule-derived weights, or the deterministic Pareto-and-score selection). Each decision is tagged with its source (model or rule). The replies are advisory: no model output enters the service model, the network optimisation, the post-solution improvement or the ledger. The only channels through which a reply can alter which plans are explored are the family mix of the candidate generator and the weight hints; the selection of an iteration is decided by the deterministic rule, and a model may only choose among iterations that passed it. Counters of calls, parse successes, validations, fallbacks, provider switches and error classes are stored with every run.

**Illustrative exchange (coordinator).** *Input (abridged):* "Global shipping network decision — iteration 1 results: Total profit: $X/week; Global demand-weighted coverage: Y%; Total cost (all-in): $Z/week; Conflicts detected: n; Weak regions (coverage < 70%): … Return ONLY valid JSON … {actions, priorities, weight_adjustments{profit_weight, coverage_weight, cost_weight}, notes}". *Output:* a JSON object such as `{"actions":[{"region":"…","action":"…","expected_gain":"…"}],"priorities":["…","…"],"weight_adjustments":{"profit_weight":0.5,"coverage_weight":0.4,"cost_weight":0.1},"notes":"…"}`.

---

## Notes for the authors (not paper text)

1. **Do not call the executive summary a model output.** It is a template filled with ledger numbers (`src/agents/orchestrator_agent.py`, around line 1216). `docs/ARCHITECTURE_BLOCK_DIAGRAM.md` marks it `[LLM]`; that mark is wrong.
2. **Hard-coded fallback strings.** When a free-text reply scores below 0.5 on the internal quality scorer, or both attempts fail, `BaseAgent.call_llm` returns a fixed placeholder ("Strategy: C / Reason 1: Balanced network design across 50+ ports…"). If you quote stored `strategy` text as an example of model output, check that it is not this placeholder.
3. **Pre-computed rule.** In the strategy and service-design prompts the system supplies the rule-based conclusion; describe the model's role as confirmation and justification, not as the decision maker, to stay accurate.
4. **Disclosure.** Some benchmark runs executed with the provider rate-limited (all calls fell back). State this and cite the per-run counters (`llm_runtime_aggregate`, and `llm_failed_call_lines` in the benchmark summaries).
