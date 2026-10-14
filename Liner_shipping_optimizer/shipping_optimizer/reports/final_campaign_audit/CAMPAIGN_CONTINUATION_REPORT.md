# Campaign continuation report: current-code experiment, decision workstreams, hardening (2026-10-14/15)

Continues `FINAL_CAMPAIGN_WORK_REPORT.md` (audit, commit `49ecd92`). Paths are relative to `Liner_shipping_optimizer/shipping_optimizer/`.
WorldSmall only. Nothing pushed. No canonical input, solver budget, default or flag was changed.

**Verdict: `READY FOR EXPERIMENTAL WORK ONLY`.** The 70 % coverage target is not met (best plan 36.4 %, mean 33.9 % for the best profile).
Operational use stays blocked by external facts listed in section 9.

## 1. Commits of this continuation (branch `campaign/20261013-issues-1-8`, start `64bcf73`)
| commit | content |
|---|---|
| `49ecd92` | checkpoint: audit report + assumption-register fix (canal fees are charged) and its pinned test |
| `2affc06` | solver-status semantics (`src/network/solve_semantics.py`, `network_milp.py`, `plan.py`, `reconcile.py`, 11 tests) |
| `b1a04b5` | frontend output contract (`utils/metrics.js`, 8 consumers, 15 node tests) |
| `05e43cf` | test contracts: golden hashes test the real invariant; region count rule; telemetry keys |
| `ffb4f6f` | predeclaration of the single coverage intervention and its retention criteria (before its runs) |
| (this report + experiment artifacts) | see section 11 |

## 2. Current-code 20-seed paired experiment (task 1)
* Code under test: the `49ecd92` source tree frozen as a copy (`C:\Users\WINDOWS\Liner-Worldsmall_exp\tree_49ecd92`); later commits only add status fields, they do not touch economics or the solve.
  Inputs: copied from the live tree and hash-verified (demand `fd46294e…`, fleet `a8986ee2…`, fleet_data `5054eb51…`, ports `b6c8c3b6…`, dist `8edf8cdf…`), recorded per run in `per_seed_*.csv` (`input_hashes`).
* Solver: PuLP 2.7.0 / CBC 2.10.3 single thread, 120 s stage limit, `PYTHONHASHSEED=0`, `LINER_SEED` unset, no other `LINER_*` variable except the arm's flags. Python 3.11.9.
* Runs strictly one after another; arm order alternates with seed parity (even: A,B; odd: B,A); order, start/end times and exit codes in `run_order.csv` (A/B) and `run_order.tsv` (all other arms). Output files carry their sha256 in the CSV. Machine: no other optimisation ran; only light edits and file reads.
* Every seed is in the CSV; 0 missing, 0 `not_solved`, 0 `invalid_plan` in any arm.

### 2.1 Arm A (current default) vs arm B (VUB + Local Search), seeds 0-19 (`per_seed_A_B.csv`, `summary_A_B.md`)
| metric (mean of 20) | A default | B VUB+LS |
|---|---:|---:|
| solved / invalid | 20 / 0 | 20 / 0 |
| revenue M USD/wk | 97.95 | 106.16 |
| costs M: vessel / fuel / port-call incl. canal+capacity / handling / transshipment | 16.71 / 29.11 / 8.55 / 17.55 / 1.33 | 17.09 / 29.56 / 8.73 / 19.29 / 1.38 |
| total cost M | 73.24 | 76.05 |
| **profit M USD/wk** (median; sd; min; max) | **24.71** (27.43; 5.67; 7.51; 29.61) | **30.12** (30.13; 1.03; 28.58; 31.98) |
| margin % | 25.0 | 28.4 |
| coverage % (max) | 31.2 (36.2) | 33.9 (36.4) |
| served TEU/wk | 86,353 | 93,611 |
| services / departures | 28.1 / 30.8 | 29.4 / 31.5 |
| vessels assigned / owned (fleet utilisation) | 175.6 / 263 (0.667) | 179.8 / 263 (0.683) |
| service leg load factor; mean-leg; network (carried/offered TEU-legs) | 0.596; 0.609; 0.582 | 0.631; 0.645; 0.618 |
| max p90 transit days | 43.9 | 39.2 |
| hard-constraint / transit violations | 0 / 0 | 0 / 0 |
| stage wall s | 124.1 | 116.7 |

Paired B - A (same seed): mean **+5.41 M**, median +3.62, sd 5.14, min +0.42 (seed 7), max +21.33 (seed 14), B higher on **20/20** seeds; coverage +2.63 pp (19/20).
Vessels assigned / owned by class (A | B): Feeder_450 22.6|23.8 of 24; Feeder_800 26.4|27.9 of 29; Panamax_1200 60.1|59.5 of 68; Panamax_2400 66.2|68.4 of 74; Post_panamax 0|0 of 58; Super_panamax 0.2|0.1 of 10.
Unserved demand by reason (% of all demand, A | B): fleet_inventory_exhausted 36.9|41.8; not_economic_to_open_service 17.3|8.9; no_time_feasible_service_in_pool 7.9|7.9; capacity_exhausted 3.8|3.8; limit_below_fastest_sailing_time 3.4|3.4; not_profitable_to_carry 0.4|0.5.
Solver evidence: status `feasible` in 40/40; incumbent vs LP bound gap of the default 53 % (mean); the frozen-tree artifacts use the legacy gap field (final profit vs bound, mean -1.6 % for B, i.e. the final plan exceeds the capped bound),
which the post-fix code reports as `final_plan` vs `capped_model` (section 3). The default is also the high-variance arm (seed 14: 7.51 M; seed 1: 20.1 M here vs 26.3 M in an earlier sequential batch).
**Supersession:** the old 32.28 M / 38.27 M headline figures (commit `e0f9d8a`, no canal fee, no per-capacity port-call rule, no draft rule) are historical results of the earlier cost model and are not the current baseline. Current baseline: 24.71 M (default) and 30.12 M (VUB+LS).

### 2.2 Independent checks (`independent_check_main.json`, 100 plans of A, B, C, D, BCA; `independent_check_scen.json`, 40 scenario plans)
From raw WorldSmall files and each artifact: vessel cost = sum(vessels x TC x 7) (fleet_data.csv); vessels per class <= owned (fleet_WorldSmall.csv); profit = revenue - itemised costs; costs sum to total; demand total = 2 x sum FFEPerWeek = 276,494 TEU; coverage = served/demand; served + unserved = demand; every leg load factor <= 1 + 1e-6; every service fits its vessel cycle; ledger violations = 0; transit violations = 0.
Result: **140/140 plans pass.** (One plan first failed at tolerance 1e-9: five legs at load factor 1 + 6.3e-9 = 3e-5 TEU of 4,800, CBC feasibility tolerance; the check tolerance is now 1e-6 and documented in the script.)
`port_canal_independent_*.json`: port-call fixed + per-FFE capacity charge + canal fees recomputed from `ports.csv`, `fleet_data.csv`, `dist_dense.csv` flags and each plan's rotations: **maximum |ledger - recomputed| = 0.0 USD/wk over 140 plans** (A,B,C,D,BCA and four scenario arms).
Limit: flow-level revenue and handling cannot be re-derived from the artifacts (they do not store flows); those are covered by the ledger's own validator and the arithmetic identities above.

## 3. Solver-status semantics (task 2), commit `2affc06`
* Raw backend status is kept (`solver_status`, `solver_status_raw`) with a `solver_status_semantics` note; new `conclusion` ∈ {`proven_optimal`, `optimal_for_restricted_service_set`, `feasible_time_limit_gap_unresolved`, `feasible_gap_unresolved`, `feasible_within_gap_tolerance`, `no_incumbent`}, plus `time_limit_reached`, `closed_by_solver`, `restricted_to_lp_support`, gap (never negative: an incumbent above the bound sets `incumbent_exceeds_bound` and a null gap).
* The final plan block carries `exceeds_capped_model_bound`, `conclusion = final_plan_exceeds_bound_of_a_different_model` or `final_plan_not_comparable_to_capped_bound_as_optimality_evidence`, and `optimality_claim = "none"`. Existing keys are unchanged; consumers: `reconcile.py`, `tests/test_orchestrator.py` (only reads `milp_status`; no frontend consumer reads these fields).
* Tests: `tests/test_solver_status_semantics.py` (11 tests: each state, legacy plans, raw status preserved). Live artifact after the change (orchestrator run): `solver_status_raw = Optimal`, `conclusion = feasible_time_limit_gap_unresolved`, gap 52.5 %.
* Not changed: time limit, backend, default.

## 4. Frontend output contract (task 3), commit `b1a04b5`
* Removed fabricated fallbacks: `MapCanvas.jsx` (1,176,324,858 USD profit, 50.9 % coverage, 547 services, 47 ports, 1.8K lanes, 276K TEU), `scenarioEngine.js` (profit, fuel, port, transshipment, total cost, demand, coverage, services, confidence, run id): a missing figure now makes the baseline unavailable (`null`, existing "awaiting baseline" state); coverage is derived from satisfied/unserved demand only when both exist; a real zero is kept.
* Load factor: `RouteTable.jsx` (summary tile and per-service), `FleetDashboard.jsx` (sort, per-service, per-class, per-region) and `FleetIntelligence.jsx` (per-class; found during the audit beyond the three reported spots) use `leg_load_factor` or carried/offered TEU-legs; services without the basis show "—". `ExportPanel.jsx` writes empty cells for missing profit/margin.
* Tests: `frontend/tests/metrics.test.mjs` (11) + existing `fleetStats.test.mjs` (4): **15/15 pass** (missing/null/NaN/boolean vs zero, load above one departure's capacity but valid across departures, scenario baseline missing/zero/ledger-derived).
* `vite build` compiles all JSX (to a scratch directory). **Browser behaviour is not verified** (no browser smoke test was possible in this environment).

## 5. Full-suite failures (task 4)
Starting set: the 34 ids of `fail_audit.txt`. Result after the changes (full run `validation/full_suite_1.log`, `fail_1.txt`): **29 failed, 1,440 passed, 20 skipped, 9 xfailed** (12 min); orchestrator `validation/orchestrator_1.log`: 364/364, score 100. The suite is **not green**.
| group | tests | root cause | action | now |
|---|---:|---|---|---|
| golden SHA of `pipeline_output.json` (phases 5, 6, 7, 9) | 4 | 4: mutable generated artifact compared with hashes of runs that no longer exist (the committed file, `37c775c8…`, matches none of them) | tests now assert the intended invariant: a module must not change the artifact (module-start hash fixture in `tests/conftest.py`); the obsolete constants are no longer used | fixed, pass |
| `test_regions_count_and_keys_frozen` | 1 | stale contract: expected 5 regions; the orchestrator rule is 3 below 50 ports (`n_clusters = 3 if num_ports < 50 else 5`, WorldSmall 47 ports), and two telemetry keys (`ga_telemetry`, `milp_telemetry`, in the frozen baseline tree) were missing from the frozen key set | expected count derived from the same rule; telemetry keys added with comment | fixed, pass |
| `test_economic_metric_documentation.py` | 29 | 2 + 3: seven generated `MULTI_AGENT_*.json` artifacts and one hand-written document are missing from the tree, and the suite documents the pre-repair code (lane factors, `DEMAND_SCALE = 6`, 4x revenue, citations by line number) | generators exist (`scripts/build_*.py`) and were run in a scratch copy: the artifacts regenerate, but ~22 citations then fail (cited code was deliberately removed or moved) and the main document does not exist and has no generator. Regenerating into the tree would pin the discredited behaviour; rewriting 42 formula citations and the document is a documentation re-audit | **left failing, classified**; needs decision D-11 (re-audit vs retire) |
Side effects controlled: tests that rewrite `pipeline_output.json` ran only when no experiment was running; the artifact was valid JSON after the suite.

## 6. Decision workstreams (task 5 of the decision brief)
Statuses: `RESOLVED BY EVIDENCE`, `RESOLVED FOR EXPERIMENTATION`, `BLOCKED ON EXTERNAL AUTHORITY`. "Operational" status is separate and is **not approved for any row**.
All scenario arms below use arm-B settings (VUB + LS), seeds 0-9, one input changed in a copy of the frozen tree, paired with B of the same seed (`per_seed_scenarios.csv`, `summary_scenarios.md`; tree changes in `tools/make_scenario_trees.py`; the scenario value is recorded in each run's assumption register).

### A. Canal fees - RESOLVED FOR EXPERIMENTATION (benchmark rule); operational: BLOCKED ON EXTERNAL AUTHORITY
* Evidence: authors' reference code `calculate_canal_cost` and solution log; `validate_against_linerlib_log.py` re-run: 34/34 traversal counts, cost within the log's rounding (<= $4/service; total 13,935,090 vs 13,935,070); blank Panama fee = class cannot pass. Independent recomputation of the ledger over 140 current plans (A, B, C, D, BCA and four scenario arms): difference 0.0 USD. Regression tests: `tests/test_physical_rules.py` (pass).
* Paired control (`S_canal_off2`: fee 0 in both optimiser economics and ledger): profit **36.83 vs 30.28 M (+6.55 M, 10/10)**, port-call+canal 8.58 -> 2.02 M, services 29.2 -> 33.8, coverage +0.53 pp. Fee exposure of the B plans: 6.80 M/wk (22.6 % of profit), 12.6 services with a canal leg (default plans: 6.66 M, 30 %). The disabled arm is a sensitivity control, not a truth.
* Diagnostic: the first control (`S_canal_off`: ledger charges, optimiser does not) gives 28.22 M (-2.07 M vs B, 1/10): a canal-blind optimiser loses 8.6 M against the fee-aware one. It is not a valid "fees off" arm and is not used for the exposure.
* Label: fees are benchmark inputs, not verified tariffs. Needed to close operationally: a real tariff or an owner-approved fee basis.

### B. Handling-cost units - RESOLVED FOR EXPERIMENTATION (per-FFE reading, supported by primary reference code and log magnitude); operational: BLOCKED ON EXTERNAL AUTHORITY
* Trace: `ports.csv` `CostPerFULL`, `CostPerFULLTrnsf` -> `network_loader.py` lines 465-475 divided by `TEU_PER_FFE` -> `Port.handling_cost` / `transshipment_cost` per TEU -> `ledger.py` 337 `teu x (origin + destination handling)` and transshipment per TEU. Reference code: `moveCost`/`transhipmentCost` are per move of an `FFE`-typed quantity.
* Magnitude check against the authors' own solution log (new here): log handling 61.9856 M for 130,832 transported FFE (138,247 demand - 7,414.6 rejected from the 7.4146 M penalty at 1,000/FFE) = **$474 per FFE**. Current plans: B (handling + transshipment) / (served TEU / 2) = **$442/FFE** (default $437). Reading the columns as per TEU would give about $883/FFE (1.9x the authors').
  The authors' revenue gives the same check on the revenue contract: log revenue 224.4 M vs 264.9 M at 100 % of the demand file (rate x FFE), i.e. $1,715 per transported FFE against a file mean of $1,916.
* Scenario `S_handling_perTEU` (columns read per TEU): profit **13.07 vs 30.28 M (-17.21 M, 0/10)**, coverage 19.7 vs 33.7 %, handling 18.97 M on far less cargo; all plans ledger-valid. Unit reading is the single largest swing of any assumption.
* Remaining external fact: the technical report's column dictionary (per-flow handling not in the log). Label stays `PROVISIONAL`.

### C. Transit file and scope - RESOLVED FOR EXPERIMENTATION (revised file as a named scenario baseline); canonical file unchanged; scope BLOCKED ON EXTERNAL AUTHORITY
* `tools/transit_file_check.py`: canonical `fd46294e…`, revised `cb6d5dbe…`; 1,764 ODs, no missing values; 105 ODs differ in transit time only (quantity and revenue identical), 18,041 FFE = 13.0 % of demand; 104 loosened, 1 tightened (+9.96 days mean).
  Upstream states the revision applies where a direct sailing at 14 kn is impossible within the limit: **all 105 canonical limits are below the direct sailing time at 14 kn** (checked with `dist_dense.csv`); 87 of 105 revised limits are at or above it. 10 unchanged ODs (1,719 FFE) are still below it.
* Paired result `S_rev_transit`: **+2.46 M (10/10), coverage +3.20 pp (10/10)**, 0 transit violations (earlier 5-seed D-06: +1.83 M).
* Justification is provenance and physical feasibility, not the gain. Whether the transit time includes port and transfer time is not stated upstream: scope stays `UNVERIFIED`.

### D. Transfer dwell and port stay - RESOLVED FOR EXPERIMENTATION (24 h and 3.5 d + 48 h kept as the baseline); operational: BLOCKED ON EXTERNAL AUTHORITY
* Reused (valid: economics identical, `git diff c6163b4 49ecd92 -- src` shows only reporting/register text), 5 seeds, concurrent: dwell 1.75 d +0.09 M; dwell 7 d -6.09 M (0/5); stay 12 h -4.09 M (1/5); stay 48 h -7.31 M (0/5).
* New, 10 seeds, sequential: dwell 1.75 d (`S_dwell175`) **+1.57 M (10/10)**, coverage +1.46 pp; stay 12 h (`S_stay12`) **-1.16 M (2/10)**, coverage +0.45 pp.
  So: longer stays/dwell clearly cost profit; shorter dwell is mildly positive; the 12 h stay result is small and its sign differs from the pre-decision-phase value (+1.53 M), i.e. it is model-version dependent. The vessel-cycle rounding (`ceil(T f / 7)`) makes profit non-monotone in T; stay and dwell interact with the candidate pool.
* Decision: keep the documented values (24 h from the benchmark page; 3.5 d + 48 h is a convention). The higher-profit 1.75 d is **not** adopted: no source supports it. Both parameters stay separate and configurable in scenario trees.

### E. VUB and Local Search - RESOLVED FOR EXPERIMENTATION; promotion recommendation below; production default unchanged
Four arms, seeds 0-19, same tree, sequential (`per_seed_E4.csv`, `summary_E4.md`):
| arm | solved/invalid | profit mean (median; sd; min; max) | paired vs A | coverage % | fleet util |
|---|---|---|---|---:|---:|
| A default | 20/0 | 24.71 (27.43; 5.67; 7.51; 29.61) | | 31.2 | 0.667 |
| C VUB alone | 20/0 | 29.15 (28.99; 0.94; 27.95; 32.01) | +4.44 M, 19/20 (min -0.03 seed 7) | 33.3 | 0.681 |
| D Local Search alone | 20/0 | 27.70 (28.63; 2.45; 21.05; 30.61) | +3.00 M, 18/20 (min -0.51 seed 4) | 32.6 | 0.673 |
| B VUB + LS | 20/0 | 30.12 (30.13; 1.03; 28.58; 31.98) | +5.41 M, 20/20 | 33.9 | 0.683 |
B - C: +0.97 M (18/20); B - D: +2.41 M (20/20). Runtime 117-124 s. No failed run in any arm (earlier LS-alone failures - 2 `not_solved`, 1 `invalid_plan` - occurred on older code under concurrent load and are not reproduced here; they stay as documented regression history and LS alone stays excluded).
* Seed-4 reconciliation: in the e0f9d8a batch (two arms concurrent) default seed 4 = 37.96 M and VUB+LS = 32.70 M; the same seed's default was 31.92 M in the Issue 2 and Issue 3 replicates, and VUB+LS gave 32.70 M again (bit-identical). The 37.96 M was a favourable CBC wall-clock draw of the default, not a property of the model. Under the current code seed 4 is A 28.97 vs B 30.58 M; B reproduces the earlier sequential value 30.585 bit-for-bit (3 of 5 seeds identical to the earlier sequential batch; A differs on all 5).
* Acceptance criteria applied (stated here after the data were seen; they are conservative and the result does not hinge on them): 20/20 solved and valid; 0 hard/transit violations; profit higher than the default on >= 18/20; lower dispersion; independent check passes. B meets all.
* **Recommendation to the owner: promote VUB + Local Search together as the production profile** (never LS alone), with CBC 120 s unchanged. Not applied: the production default is unchanged. Rollback is not needed (flags only).

### F. Sub-weekly frequencies - RESOLVED FOR EXPERIMENTATION (deferred, weekly retained); implementation not started
* Existing bounded study (`reports/decision_phase/d07/D07_subweekly_frequency_study.md`, HiGHS 240 s, seeds 0-2, fortnightly twins): dual-bound gain +0.5 to +2.1 M/wk (+2-8 %); coverage not systematically higher; incumbent gains mostly solver convergence.
* New upper bound from the current 20-seed plans (`tools/subweekly_waste.py`): vessel-days paid for but not needed because a service needs `ceil(T f / 7)` whole vessels: **7.18 M/wk for B (23.9 % of profit; range 6.35-8.32), 7.59 M/wk for A (35.9 %)**; 19.9 of 29.4 services run below 60 % slot-time utilisation. This is the most that perfect fractional scheduling could save on these services; the prototype study captured less than a third of it (<= 2.1 M).
* Minimum scope (see the D-07 study table): frequency in half-week units, vessels `ceil(T g / 14)`, per-pair transfer waits, ledger/reconcile/frontend/tests, model size x2 (CBC at 120 s cannot close it). The authors' benchmark solutions are all weekly. Not feasible to implement and validate safely by the deadline; no prototype was built.
* External fact needed: whether sub-weekly services are in the business scope.

## 7. Opportunity register and diagnostics (task 5)
Stale: the Issue 5 register (built on the pre-canal, pre-draft, pre-port-call model) is superseded and must not be used as current evidence. Rebuilt on the current model (`register/register_seed{0,1,2}_B.json`, plans = arm B seeds 0-2, tree `49ecd92`):
* Plans' network profit equals the ledger profit (31.98 / 28.73 / 30.09 M). Operated services with negative network marginal: 1 / 0 / 1; services with negative stand-alone profit but positive network marginal: **14 / 11 / 12** of 30 / 29 / 32.
* 150 of about 1,200 alternatives evaluated per seed (ranked by cheap potential), positive marginal for 26 / 41 / 31; top-40 all `CONDITIONALLY_FEASIBLE` (need vessels beyond the idle inventory of small and medium classes); 58 Post_panamax and 10 Super_panamax idle in every plan; commercial status mostly `UNCERTAIN` (sign changes with fuel +-25 % or capacity x0.5).
* Limits retained: fixed-rest-of-network, one change at a time, 3 seeds, 150-alternative search; no global optimality and no feasibility of combinations is claimed.

## 8. Controlled coverage intervention (task 6)
Predeclared in `INTERVENTION_PREDECLARATION.md` (commit `ffb4f6f`, before the runs): `LINER_PATH_SELECTION=cost_aware` on arm B, 20 paired seeds.
Result (`per_seed_intervention.csv`, `summary_intervention.md`): 20/20 solved, valid, 0 violations, all independent checks pass; profit 30.64 vs 30.12 M (**+0.52 M, higher on 12/20**, min -1.06, max +2.40); coverage 33.2 vs 33.9 % (**-0.71 pp, higher on 6/20**); fleet utilisation 0.667 vs 0.683.
Criteria: (1) pass; (2) mean > 0 pass, >= 14/20 **fail** (12/20); (3) coverage >= +1.0 pp **fail** (-0.71); (4) pass; (5) pass. **REJECTED.** Cost-aware ranking does not raise coverage on the current model, which contradicts the earlier pre-decision-phase signal (+4.7 pp). The inventory bottleneck (41.8 % of demand) is not addressed by path ranking; next candidates are class-inventory-aware candidate design and the revised transit file (+3.2 pp, a data question).

## 9. Remaining external facts (cannot be established from the repository)
| fact | why not available | source or approval needed |
|---|---|---|
| real canal tariff and fee basis | fees in `fleet_data.csv` are benchmark data; the reference rule is for the benchmark model | tariff table or owner approval of the benchmark basis |
| handling/transshipment unit (per FFE move) | log gives only totals; technical report not available | LINERLIB technical report (DTU 19.2010) or a column dictionary for `ports.csv` |
| transit-time scope (port/transfer time included?) and canonical file | upstream README silent | custodian statement; owner decision to adopt the revised file |
| transfer dwell (3.5 d + 48 h) and port stay (24 h) | convention / secondary source | operating policy or source |
| sub-weekly services in scope | business question | owner |
| promotion of VUB + LS | owner-only (production default) | owner approval; evidence in section 6E |
| 29 documentation tests | decision D-11 | owner: re-audit or retire |
Capacity unit stays `reference_code` (authors' code types capacity as FFE), not `verified`.

## 10. Target scorecard
| target | status | evidence |
|---|---|---|
| 70 % demand coverage | **NOT MET** | best plan 36.4 %, B mean 33.9 %; no relaxation or scenario reaches it (`S_rev_transit` 36.9 % mean) |
| productive vessel utilisation | measured, not forced | 0.683 (B) of 263; small/medium classes 95-100 % used, 68 large vessels idle (not economic on the lanes) |
| profitability | positive in all 150 runs | B 30.12 M/wk, margin 28.4 % (advisory 15 % threshold exceeded); benchmark fees and provisional units |
| transit feasibility | met in all accepted plans | 0 transit violations, 140/140 independent checks |
| accounting integrity | verified | profit identity, vessel cost, inventory, port-call+canal recomputation to 0.0 USD |
| reproducibility | partial | B reproduces bit-identically on 3/5 earlier seeds; default does not; artifacts + hashes stored |
| solver-status honesty | fixed in code | raw vs conclusion fields |
| frontend contract | fixed, unit-tested, browser not verified | 15 node tests, build compiles |
| full test suite | **29 failures remain** (documentation suite) | section 5 |
| operational readiness | **NO** | section 9 |

## 11. Reproduce, rollback, final state
* Reproduce a run: `PYTHONHASHSEED=0 venv/Scripts/python.exe reports/decision_phase/d05_final/global_stage_experiment.py <tree> <out.json> <seed> 120 prod` with the arm's `LINER_*` flags; batch drivers `reports/current_code_experiment/run_paired_sequential.sh`, `tools/run_job_list.sh` with `jobs_*.tsv`; tables `tools/build_per_seed.py`, `tools/summarize.py`; checks `tools/independent_check.py`, `tools/port_canal_independent.py`, `tools/transit_file_check.py`, `tools/subweekly_waste.py`; trees `tools/make_scenario_trees.py`.
* Tests: `python tests/test_orchestrator.py`; `python -m pytest tests -q -p no:cacheprovider`; `cd frontend && node --test tests/metrics.test.mjs tests/fleetStats.test.mjs`.
* Rollback by commit: `git revert 05e43cf b1a04b5 2affc06` (independent). The experiment trees are outside the repository and unchanged.
* Limitations: scenario arms are compared with the B runs made hours earlier on the same machine (sequential); 10 seeds for scenarios; frozen-tree artifacts use the legacy gap field; the independent checks cannot re-derive flow-level revenue; criteria for E were applied after seeing the data.

## 12. Next phase
Entry gates: (1) owner decisions on VUB+LS promotion and on D-11; (2) browser smoke test of the dashboard against a fresh artifact. Exit gates: 20-seed batch of the chosen profile on the committed `HEAD`, 20/20 solved, 0 violations, independent checks pass; coverage experiment on class-inventory-aware candidate design predeclared as in section 8 with criteria on coverage >= +2 pp and no profit loss; D-04/D-06 rerun on the approved cost model. Deferred by deadline: sub-weekly frequency, documentation re-audit, scalability beyond 47 ports.
