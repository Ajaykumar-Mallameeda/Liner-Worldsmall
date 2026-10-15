# Continuation report, 2026-10-15/16: paper-cost parity, C3 baseline, lane / path / dual experiments

Continues `FINAL_CAMPAIGN_WORK_REPORT.md`, `CAMPAIGN_CONTINUATION_REPORT.md` and `reports/class_mismatch_campaign/`. WorldSmall only; Baltic, WAF and WorldLarge were not read or run; nothing was pushed.
Paths are relative to `Liner_shipping_optimizer/shipping_optimizer/` unless stated. Evidence root: `reports/continuation_20261015/` (`INDEX` below).

## 0. Verdict

**Primary verdict: `NO REPEATABLE IMPROVEMENT`** (operational experiments). C3 remains the working configuration; every new feature is opt-in and OFF; the solver backend (PuLP/CBC, single thread) and the 120-second budget were not changed.

| workstream | status |
|---|---|
| 1 repository, inputs, C3 baseline | **PASS**: recoverable, hashes match, baseline frozen; a drift check shows the baseline is machine-dependent (section 3) |
| 2 solver-status and displayed economics | **PASS**: status semantics already in `HEAD`; this campaign removed the remaining demo-number and zero fallbacks; 17/17 Node tests, Vite build compiles; 29 documentation tests still fail (pre-existing, unchanged set) |
| 3 six paper-cost-parity targets | **PASS**: 23 rows VERIFIED, 3 PROVISIONAL, 1 UNRESOLVED; two evaluator defects found and fixed; the authors' own solution log reproduces to the precision it prints |
| 4 trans-Pacific / Atlantic trunk family | **NOT RETAINED / inconclusive**: the family is nearly empty; no repeatable benefit |
| 5 targeted path additions | **REJECTED** after three bounded attempts |
| 6 dual-price screening of rejected candidates | **Existing rule kept**: the dual price does not rank the candidates (rank correlation 0.03 against 0.51 for the stand-alone profit) |
| 7 coverage diagnosis | **DONE**: overlapping causes quantified; no further intervention supported, none made |
| 8 external assumptions | **DONE**: disposition of 13 items (`ws8_assumptions/ASSUMPTION_DISPOSITION.md`); nothing promoted to verified without a primary source |
| 9 final comparison | **DONE**, with a limitation that matters: the machine was on battery / Balanced power and under Windows servicing; CBC failed to find an incumbent on a control arm that solved 20/20 earlier (section 8) |
| 10 report and checkpoints | this file; selective commit (section 14) |

**Recommendation: keep C3 as the working configuration.** Do not promote the lane family, targeted paths or dual screening. The honest limit of the optimiser experiments is the environment, not only the ideas (section 8).

## 1. Revisions and working tree

* Start: branch `campaign/20261013-issues-1-8`, `HEAD 3bff834`. Working tree: 45 status entries - 5 modified tracked files (`P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md`, `SYSTEM_TRUTH_REPORT.md`, `frontend/public/pipeline_output.json`, `reports/decision_phase/d07/outputs/fortnightly_seed2.{json,log}`) and many untracked reports/documents. Recovery material saved in `ws1_provenance/` (`start_git_status.txt`, `start_git_log.txt`, patches of the modified tracked files, a copy of the dirty `pipeline_output.json`). Tag `baseline-t11-20261013` exists.
* The five pre-existing modified tracked files and the untracked files outside this campaign are **left untouched and not staged**.
* End: `HEAD 2e26572` (one commit on top of `3bff834`); the 5 pre-existing modified tracked files and all unrelated untracked files remain exactly as they were.

## 2. Inputs and baseline provenance (Workstream 1)

* Canonical inputs (`data/raw/WorldSmall/`), sha256 prefixes: demand `fd46294e5b71bcc6`, dist `8edf8cdf7a119c34`, fleet `a8986ee2bfeda133`, fleet_data `5054eb5178cedbe2`, ports `b6c8c3b6c209222a` - **all equal to the hashes recorded in the earlier artifacts**; full hashes in `ws1_provenance/input_provenance.json`.
* Relation to upstream LINERLIB (`C:\Users\WINDOWS\Downloads\LINERLIB-master (1)`): demand, `fleet_data`, `fleet_WorldSmall` are byte-identical; `ports.csv` is the 47 upstream rows; `dist_dense.csv` is restricted to the 47 ports with one row per directed pair, equal to the upstream **minimum-distance** row (896 pairs have alternative routes upstream that this file does not carry - recorded, not changed). Upstream `Demand_WorldSmall.csv` has **7 ODs with thousands-separator misparses** (e.g. 1.865 instead of 1,865 FFE; 128,281 FFE in total); the canonical `Fixed_Sep` file corrects them. The authors' solution log was produced with the unfixed file.
* Transit files: canonical `fd46294e…`; revised scenario `cb6d5dbe…` (= upstream `transittime_revision/Demand_WorldSmall_tt.csv` values applied to `Fixed_Sep`, 0 differences; 105 values change, the upstream README says 106). The revised file is **not** canonical.
* Frozen C3 baseline (`ws1_provenance/C3_baseline_freeze.{json,md}`, from `reports/class_mismatch_campaign`): C3 = `LINER_MILP_VUB=1 LINER_LOCAL_SEARCH=1 LINER_TRUNK_CANDIDATES=12 LINER_TRUNK_DIVERSE=1 LINER_TRUNK_MAX_PORTS=10 LINER_MILP_SUPPORT_CAP=105`, CBC single thread 120 s, `PYTHONHASHSEED=0`. 20/20 seeds `feasible` (time-limited incumbent; no optimality claim), 0 ledger and 0 transit violations, every artifact sha256 and input hash verified. **Mean profit 42.47 M/week** (median 43.82, min 31.79, max 47.07), coverage 44.0 %, 28.1 services, 163 of 263 vessels assigned (100 idle: 32.4 of 58 Post_panamax, 29.1 of 68 Panamax_1200, 28.0 of 74 Panamax_2400), productive load factor 0.560, profit per assigned vessel 267 k/week, per owned vessel 161 k/week. Mean costs (M): vessel 21.37, fuel 31.19, port call incl. canal 10.19, handling 26.03, transshipment 1.15. Per-seed table in the freeze file.
* The frozen experiment tree (`tree_fix1`) equals `HEAD` source except for the solver-status fields (CRLF-insensitive diff), so the frozen economics apply to `HEAD`.
* **Drift check** (`C3head`, clean `HEAD` snapshot, seeds 0-2, `per_seed_C3head.csv`): seed 0 reproduced to the dollar (34.25 M), seed 2 -1.9 M (44.07 vs 45.97), **seed 1 -11.4 M (25.77 vs 37.13)**; ledger and port/canal recomputation exact (0.0 USD). Consequence: only same-time paired comparisons are trusted (section 8).

## 3. Solver status and displayed economics (Workstream 2)

* Solver-status mapping (commit `2affc06`, unchanged here): raw backend status kept, `conclusion` ∈ {`proven_optimal`, `feasible_time_limit_gap_unresolved`, …}; `plan.status == "optimal"` only when CBC closed the problem and it was not restricted to the LP support. Verified in this campaign by reading `network_milp.py` (`sol.status = "optimal" if (closed and not dropped) else "feasible"`) and by the stored C3 artifacts (all `feasible`).
* Frontend, residual defects found and fixed: `MetricStrip.jsx` showed demo numbers when data were missing (47 ports, 1,764 lanes, 551 services, 276K TEU, 310 s, **88.6 % coverage**); `CommandCenter.jsx` showed `964,949 TEU SERVED`; the runtime adapter and initial state defaulted profit, annual profit, coverage, margin and operating cost to 0; three consoles hid a real negative profit (`> 0` test) or showed `0.0M`. Now a missing figure is `null` and renders as an em dash; real zero and real negative values are kept. Files: `MetricStrip`, `NetworkIntelligenceCanvas`, `p12`, `ExportPanel`, `ScenarioWorkspace`, `SummaryView`, `CommandCenter`, `consoleSelectors.js`, `runtimeAdapter.js`, `useOptimizationState.js`; tests `frontend/tests/metrics.test.mjs` (+2). The earlier commit `b1a04b5` had already removed the 1.16 B profit fallbacks and the per-departure load-factor denominators (grep finds no remaining `1176324858`).
* Commands and results (all actually run): `cd frontend && node --test tests/metrics.test.mjs tests/fleetStats.test.mjs` → **17 pass, 0 fail**; `npx vite build --outDir D:\…\vite_out` → built; narrow pytest set (`test_network_economics, test_solver_status_semantics, test_lp_round_start, test_trunk_candidates, test_trunk_lanes, test_targeted_paths, test_dual_screen, test_paper_cost_parity, test_paper_evaluator, test_unit_contract, test_physical_rules`) → **142 passed**; full suite in a scratch copy without `.env` (`D:\liner_scratch_continuation\tree_suite1`, log `validation/full_suite_scratch.log`) → **29 failed, 1,511 passed, 20 skipped, 9 xfailed** (10 min 14 s). The 29 failing ids are **identical** to the earlier `fail_1.txt` (all in `tests/test_economic_metric_documentation.py`, decision D-11: documentation of the pre-repair code, needs a re-audit or retirement). No new failure. Orchestrator (`python tests/test_orchestrator.py`, scratch copy, rule-based fallback, no external calls): **364/364**, score 100 (`validation/orchestrator_default_scratch.log`). The live `frontend/public/pipeline_output.json` was not touched by these runs.
* Not verified: browser behaviour of the dashboard.

## 4. Paper-cost parity (Workstream 3) - the six targets only

Scope kept: no RL policy, no heuristic-MCF rebuild, no change to C3. Code: `src/benchmark/paper_ledger.py` (new; independent itemised ledger, rotation costs, soft fleet accounting, FFE→TEU representation), fixes in `src/benchmark/paper_evaluator.py`; tests `tests/test_paper_cost_parity.py` (31 tests, hand arithmetic in the file); full matrix `ws3_paper_parity/PARITY_MATRIX.md` (+ `.json`); assumptions in `ws8_assumptions/`.

**Source evidence used.** The paper's Appendix A.1-A.3 and Table 1/Table 2 text (arXiv HTML for the equations, because the PDF text layer garbles Eq. 35), and the LINERLIB authors' own WorldSmall solution log (primary-source output). `tools/linerlib_log_reconcile.py` recomputes, from the raw WorldSmall files and the logged flows only: per service distance, sailing fuel (cubic law at the logged speed), idle fuel (one day per call), port-call cost, time-charter cost, canal cost; and from 1,708 logged flows revenue, the rejected-demand penalty, handling and transshipment:

| term | recomputed | log (prints 6 digits) | rel. diff |
|---|---:|---:|---:|
| vessel (TC x 7) | 35,658,000 | 35,658,000 | 0 |
| port calls | 5,565,837 | 5,565,840 | 5e-7 |
| canal | 13,935,090 | 13,935,100 | 7e-7 (34/34 traversal counts) |
| sailing fuel at 600 USD/t | 43,091,251 | 43,091,200 | 1e-6 |
| idle fuel | 765,120 | 765,120 | 0 |
| revenue | 224,422,938 | 224,424,000 | 5e-6 |
| penalty | 7,414,603 | 7,414,600 | 4e-7 |
| handling + transshipment | 61,985,489 | 61,985,600 | 2e-6 |
| objective | 56,007,548 | 56,008,300 | 1e-5 |

Capacity unit: the log's printed utilisation per service equals the mean leg load factor of its flows with capacity = `Capacity FFE` (32/34 within 2e-6, max difference 4e-5, no leg above 1.0000007; a TEU reading would reach 2.0) - `ws3_paper_parity/capacity_unit_check.json`.

**Per target.** 3.1 units: TEU-native copy equals the operational loader boundary exactly (capacity converted once, rates halved), gross revenue not inflated, equivalent representations give the same revenue, costs, coverage and load factor (max relative difference 1e-9). 3.2 fuel: sailing time = nm/(24 x design speed) and one idle day per call verified (Table 6: 19/19 schedules; log); six-class hand calculations for a 2,080 nm rotation with intermediate values (e.g. Post_panamax 5.2525 d, 1.03607 vessels, 431.758 t + 14.8 t, 267,934.55 USD at 600 USD/t); the fuel price is not in the paper and is an explicit argument (`None` leaves it unavailable) - **PROVISIONAL** (the log prints 600 USD). 3.3 fleet: service = n x TC x 7; the unused term is a credit for spare vessels and a charge beyond the fleet (three cases tested; paper Table 1 reproduces the sign and size within rounding; owned Baltic fleet inferred); operational C3 still rejects an over-fleet plan (`fleet_exceeded`). 3.4 port/handling: port call = fixed + per-FFE x capacity per call (exact), p_l at both ends and p_t per transfer per FFE (per-FFE reading reproduces the authors' total; the per-TEU reading would double it); one-day stay; small end-to-end example profit 4,000 by hand = evaluator = ledger. 3.5 canal: traversals x class fee once per weekly rotation (34/34, <= 4 USD); blank Panama fee = cannot pass, reported never invented; the Suez fees are benchmark inputs, not tariffs. 3.6 objective: accepted demand earns once, rejected demand pays 1,000 per FFE once, the objective is recomputed independently (`objective_ledger`) and agrees with the evaluator on WorldSmall designs; the paper's Table 1 identity closes exactly for both columns (used as an identity, never as a profit target).

**Defects found and fixed.** (a) `evaluate()` charged the transshipment fee at the *start of the last leg* of the earlier service instead of where that service is left; this changed handling for multi-leg services whenever p_t differs by port (`transfer_ports`, regression test). (b) The 1,000 USD/FFE penalty was a fixed constant: in a TEU-native representation it would have doubled; it is now a per-unit rate carried by the data (`penalty_per_unit`, 500 per TEU).

**Not reproduced / unresolved (honest).** The paper's printed profits for WorldSmall (32-43 M): the Table 6 design (48 interpretation variants, Issue 7) and now the LINERLIB design with butterflies split into 51 simple loops (16 variants: 2 demand files x voyage basis x canal basis x capacity basis) span -391..+90 M; none is within 40 % (closest x0.51). Open: the profit horizon, the capacity basis of a fractional-vessel service, the decomposition and tie-breaking of the paper's own MCF, and whether Eq. 35's `x n_{v,s}` is meant per rotation - the reference output charges every voyage term once per weekly rotation. **Cost parity does not prove objective or algorithm parity; no paper headline is used as a target.**

## 5. Trans-Pacific / Atlantic trunk family (Workstream 4)

Code (opt-in, OFF): `src/network/trunk_lanes.py`, optional restrictions of `trunk_candidates.augment_trunk_candidates` (explicit classes, port filter, cross-group seeds, rejection counters), hook in `reconcile.py`; flags `LINER_TRUNK_LANES=all|transpacific|atlantic`, `LINER_TRUNK_LANE_COUNT` (default 2, max 6), `LINER_TRUNK_LANE_CLASSES` (default Post_panamax, Super_panamax), `LINER_TRUNK_LANE_MAX_PORTS`. Tests: `tests/test_trunk_lanes.py` (9). Every candidate is an ordinary candidate through the same economics and the independent ledger.

**Finding (per-constraint counts, seed 3, identical in every seed):** Atlantic - Super_panamax 24 grown rotations, 24 with non-positive stand-alone profit; Post_panamax 8 eligible ports and **0 seed pairs** (US East ports are 12.5 m deep, Post_panamax needs 13); trans-Pacific - Super_panamax 116 grown, 116 non-positive; Post_panamax 55 grown, 41 non-positive, 2 already in the pool, 9 over the cap, **3 retained**. The family therefore adds 3 candidates per seed; across the clean batch the plan used one of 30 (`tp0000`, seed 1).

**Result** (predeclared criteria `PREDECLARATION_WS4.md`; paired against a control of the same batch): the first batch ran with up to three solves in parallel while Windows servicing held most of the memory and the system drive was full; its control failed on seeds 8-11 and it is **marked contaminated and not used** (kept: `per_seed_L1_partial.csv`). Clean sequential batch Z1 (seeds 0-9, `per_seed_Z1.csv`): control `C3z` solved 6/10, lanes `L1z` 8/10; over the 6 seeds where both solved the mean difference is **-0.69 M** (median +0.64, 4 higher, seeds 0 and 7 lose 8.6 and 4.3 M, coverage +2.0 pp). Criteria not met (needs >= +0.5 M, >= 7/10 higher, no seed losing > 3 M). Seed 7 lost 4.1 M in the contaminated batch too. **Label: not retained, inconclusive; the family is opt-in and should not be used** because the candidates it adds are almost never economic and the differences are inside the solver's trajectory noise.

## 6. Targeted path additions (Workstream 5)

Code (opt-in, OFF): `src/network/targeted_paths.py` and the `path_augment` hook in `network_milp.solve_network` / `plan.py`; flag `LINER_PATH_TARGETED=K:M[:R]` (K demands, M paths each; default 10-path cap untouched; caps 30 x 3 = 90 paths, 1 round). After the first LP relaxation the duals price the excluded valid paths of demands that the relaxation leaves partly unserved (reduced profit = revenue - port charges - dual(demand) - sum dual(leg capacity)); the best K x M are added. **Dual units and signs were validated by finite differences on the solved LP** (`tests/test_targeted_paths.py`: the demand dual equals the objective change for +1 TEU, capacity duals are >= 0; CBC prints duals with 6 digits). Tests: 12.

Diagnostic (`T_STUDY=coverage`, `ws7_coverage_C3e.md`): on 9 control seeds 354 demands per seed have an excluded positive-margin path, with a "margin x unserved TEU" figure of 31.5 M/week that ignores fixed cost, capacity and vessels (an upper-bound-style number, not a benefit); the flow re-optimisation never left an operated path with room and positive margin unused (0 contradictions).

Attempts (each logged before its run): **P1b** (full enumeration + second LP): 0 of 10 solved - the round itself took 27-42 s of the ~105 s MILP budget and CBC (which needs ~90 s to its first incumbent on these pools) found none; **P1s** (10:2) 0 of 3; **P2z** (enumeration limited to 120 demands, second LP kept; clean batch Z1) 3/10 solved - the round still took 27-42 s, dominated by the second LP; **P3** (`30:3:0`, no second LP; round 0.5 s; clean batch Y, `per_seed_Y.csv`): control `C3y` 10/10, P3 9/10 (seed 8 not solved); over 9 pairs the mean difference is **-2.19 M** (median +0.84, 6 higher, seeds 0, 3 and 7 lose 9.6, 5.7 and **17.7 M**, coverage -4.0 pp). The added columns raised the LP bound by 0.2-2.3 M, but the integer plans did not benefit. **Gate 5: rejected; default path cap unchanged; flag stays opt-in, not recommended.** The adaptive-budget approach was not revived.

## 7. Network marginal-value screening (Workstream 6)

Tool (study only, no flag): `src/network/dual_screen.py` - the LP relaxation of the pool gives duals for demand rows, leg capacities and fleet rows; each previously rejected trunk/lane rotation is priced by a small restricted LP over its direct and one-transfer paths (operated capacity priced, not limited), and compared with the ACTUAL LP-bound increment of pool + candidate (`T_STUDY=dual`, seeds 0-2, `PREDECLARATION_WS6.md`, `ws6_dual_study.json`). A direct-only net-revenue price was shown by argument to be useless (it cannot exceed the stand-alone profit) and was replaced. Tests: 3.

Result (251 rejected rotations per seed, 43 evaluated): every rejected rotation prices **positive** (mean dual price of the top 5 = 11.2 M/week) while the actual LP increments are -0.56..+0.26 M; **77 % of the evaluated increments are negative** (adding a service can displace paths inside the 10-path cap); Spearman correlation of the dual price with the actual increment **+0.03** (pooled; per seed -0.08..+0.16) against **+0.51** for the plain stand-alone profit (per seed 0.38-0.66). Dual-top selections had a positive actual increment in 33 % of cases, stand-alone-top in 7 %, random 20 %; the best single increment was +0.26 M. **Gate 6: the existing stand-alone rule is kept; no MILP arm was run because the study gives no support for one.** Standalone-negative rotations with positive network value exist (e.g. +0.2 M LP for a 4-port Post_panamax rotation) but are small and not identifiable by the duals.

## 8. Coverage diagnosis and the environment limit (Workstream 7 and 9)

**Unserved demand** (C3 control plans, seeds 0-8, `T_STUDY=coverage`, `ws7_coverage_C3e.md`): 60.0 % of demand unserved on average in this environment (52-74 %). Causes are overlapping; the exclusive combinations add up: no valid path at all 8.9 % (5.5 % none in the pool, 3.4 % transit limit below the fastest sailing time); inventory-blocked with no openable alternative about 15 %; an alternative path that could be opened with the free fleet but is not worth opening (pure economics) about 7 %; both kinds of path present about 28 % (of which 17 % also has paths excluded by the cap); a full operated leg 3.4 %. Roughly 31 % of demand has a single cause, 29 % overlapping causes. The old single-cause label "fleet inventory exhausted" (25-42 %) therefore overstates the hard inventory limit. No remedy that is safe and supported follows (a coverage floor was already shown to be infeasible or unsolvable); **no additional intervention was made**. Fleet metrics are reported separately: deployment ratio (assigned/owned) 0.52-0.65 depending on the arm and batch, productive load factor 0.55, profit per assigned vessel 257-285 k, per owned vessel about 161 k; idle vessels are not forced into service. Sub-weekly frequency stays deferred (no feasibility study was done).

**Environment limit.** From about 20:00 the machine was on battery with the Balanced power plan (CPU clock about 1.5 of 2.2 GHz base), Windows servicing (`TiWorker`) used up to 7.5 GB of 16 GB, and C: reached 0 bytes free twice (zero-byte outputs appeared and a batch died; they were renamed `*.invalid_*`, not deleted; two old scratch directories were relocated to D: with `robocopy /MOVE`, nothing lost). CBC's time to its first incumbent is sensitive to this: in the clean batch Z1 the control solved 6/10 seeds, in the later batch Y 10/10, while the frozen 20-seed baseline solved 20/20. Seed 0 of the same code gave 34.25 M (earlier runs), 48.18 M (batches Z1/Y) and 39.6/38.6 M for two arms. **Absolute levels of this session's batches are therefore not comparable with the frozen 42.47 M and not with each other; only within-batch pairs are used, and the number of unsolved seeds is reported.**

**Comparison table** (generated by `tools/final_comparison.py`, `FINAL_COMPARISON.md`; means over solved seeds):

| batch | arm | solved | profit M (median; min-max) | coverage % | services | assigned/owned | prod. load | profit per assigned k |
|---|---|---|---|---:|---:|---|---:|---:|
| frozen (reference) | C3 | 20/20 | 42.47 (43.82; 31.8-47.1) | 44.0 | 28.1 | 163/263 | 0.560 | 267 |
| Z1 clean | C3z | 6/10 | 42.11 (41.55; 36.8-48.2) | 43.2 | 27.2 | 157/263 | 0.547 | 272 |
| Z1 clean | L1z (lanes) | 8/10 | 41.68 (41.66; 39.6-43.3) | 45.5 | 27.8 | 171/263 | 0.535 | 244 |
| Z1 clean | P2z (targeted, re-solve) | 3/10 | 36.10 (36.69; 28.6-43.0) | 36.4 | 22.3 | 138/263 | 0.582 | 273 |
| Y clean | C3y | 10/10 | 43.30 (44.04; 36.8-48.2) | 45.7 | 29.2 | 170/263 | 0.546 | 257 |
| Y clean | P3 (targeted, no re-solve) | 9/10 | 41.03 (41.20; 27.3-48.0) | 41.6 | 25.7 | 146/263 | 0.543 | 285 |

Paired (both solved, same batch): L1z - C3z -0.69 M (6 pairs, 4 higher, 2 seeds lose > 3 M); P2z - C3z -2.65 M (2 pairs); P3 - C3y -2.19 M (9 pairs, 6 higher, 3 seeds lose > 3 M). The contaminated first lane batch (L1 - C3c +0.67 M on 11 pairs) is listed in the file for completeness; its `C3c` row counts seeds 16-19 as "failed" although they were never run (disk full).

Ledger and feasibility: all 36 solved plans of batches Z1/Y pass `independent_check.py` (vessel cost, fleet inventory, profit identity, demand conservation, leg load <= 1 + 1e-6, 0 ledger and 0 transit violations) and the port-call + canal recomputation differs from the ledger by **0.0 USD**; 25 of the first batch's solved plans pass as well (`independent_check_*.json`, `port_canal_independent_*.json`). Solver termination: every accepted plan has status `feasible` (time-limited incumbent, no optimality claim); stage wall 121-123 s; unsolved runs are CBC "no incumbent in 120 s" (`not_solved`), never hidden.

**Acceptance principles (section 9 of the brief):** none of the experiments reaches a validated improvement: 1 hard feasibility passed for all accepted plans; 2 ledger passed; 3 solver status honest; 4 backend and budget unchanged; 5 **repeatability not shown** (paired differences straddle zero, large losing seeds, unsolved seeds); 6 no cost or constraint was removed; 7 adverse and failed seeds are listed; 8 baseline recoverable; 9 every feature opt-in. Mixed evidence = inconclusive, not forced positive.

## 9. Frontend and output-contract corrections

See section 3. No browser test was possible.

## 10. Input hashes, flags, artifact locations

Hashes: `ws1_provenance/input_provenance.json`. Flags used: C3 (above); `LINER_TRUNK_LANES=all LINER_TRUNK_LANE_COUNT=3`; `LINER_PATH_TARGETED=30:3` / `30:3:0` / `10:2`; `T_STUDY=coverage|dual` (driver only). Trees (outside the repository, `C:\Users\WINDOWS\Liner-Worldsmall_exp\`): `tree_head_3bff834` (clean `HEAD`), `tree_lanes1`, `tree_pt1` (all new modules, flags off = previous behaviour). Drivers: `tools/run_arms*.sh`, `tools/global_stage_experiment_v{2,3,4}.py` (copies of the Task 15 harness that additionally record the augmentation reports, study hooks and the solver's formulation block). Index of `reports/continuation_20261015/`: `PREDECLARATION_WS{4,5,6}.md` (written before the runs, with dated addenda), `per_seed_*.csv`, `paired_*.json`, `FINAL_COMPARISON.{md,json}`, `ws1_provenance/`, `ws3_paper_parity/`, `ws6_dual_study.json`, `ws7_coverage_C3e.{md,json}`, `ws8_assumptions/`, `validation/`, `outputs/`, `runs/`, `run_order*.csv`.

## 11. Unresolved external evidence and decisions still required

Owner: (1) real canal tariff or approval of the benchmark fee basis; (2) the LINERLIB technical report's column dictionary (handling unit is now verified against the reference solution, the report itself was not seen); (3) update of the operational register wording for the capacity unit (now verified against the reference output); (4) which transit file is canonical and whether the limit includes port/transfer time; (5) whether a class that cannot use a canal should be routed round it (the distance file keeps only the shortest route); (6) sub-weekly frequency in scope; (7) D-11 (29 documentation tests: re-audit or retire); (8) promotion of any experimental flag (none recommended). Paper side (needs the authors or their code): profit horizon, voyage basis of Eq. 35, MCF tie-breaking, which demand file the paper used. Dispositions in `ws8_assumptions/ASSUMPTION_DISPOSITION.md`.

## 12. Rollback

All new behaviour is behind unset environment flags (flags off = previous behaviour exactly; the 364/364 orchestrator run and the 142-test narrow set were obtained with flags off). To remove the code: `git revert <campaign commit>` (`2e26572`; not executed). Files added by this campaign are new (`paper_ledger.py`, `trunk_lanes.py`, `targeted_paths.py`, `dual_screen.py`, four test files, `reports/continuation_20261015/`). Modified: `paper_evaluator.py` (fixes 4(a)/(b), `return_flows`), `trunk_candidates.py` (optional restrictions, counters; defaults unchanged), `reconcile.py` (lane hook), `network_milp.py` / `plan.py` (`path_augment` hook, default None), frontend files in section 3. Relocated scratch (revert: `robocopy D:\liner_scratch_continuation\old_session_scratchpads\<id> <C:\Users\WINDOWS\AppData\Local\Temp\claude\C--Users-WINDOWS-Liner-Worldsmall-Liner-shipping-optimizer-shipping-optimizer>\<id> /E /MOVE` for `636cef3d-a9fd-471a-b230-ac3dd4367b29` and `4de648c7-4db7-4986-a7a8-caad08c69c21`).

## 13. Pre-existing failures and side effects

29 documentation tests (above). `frontend/public/pipeline_output.json`, `SYSTEM_TRUTH_REPORT.md`, `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md` and the d07 outputs were already modified before this campaign and were not staged. Generated artifacts produced by the test runs stayed in the scratch copy on D:. Invalid outputs from full-disk windows are kept as `outputs/*.invalid_*`.

## 14. Checkpoint

Selective commit of: the new/modified `src/` files and four test files above, the frontend sources and Node test, `reports/continuation_20261015/` and this report. Nothing else is staged. Committed as **`2e26572`** on `campaign/20261013-issues-1-8` (211 files, mostly experiment artifacts; `git revert 2e26572` removes everything). Not pushed.
