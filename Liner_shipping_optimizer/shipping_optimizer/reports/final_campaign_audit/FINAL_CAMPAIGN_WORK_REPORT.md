# FINAL CAMPAIGN WORK REPORT: Issues 0-8 and Decision Resolution Phase

Audit date 2026-10-14. All repository paths are relative to `Liner_shipping_optimizer/shipping_optimizer/` unless stated otherwise.
Git root is `C:/Users/WINDOWS/Liner-Worldsmall`. This is the only consolidated report of this audit; existing reports are referenced, not modified.

Status words follow the requested vocabulary. "Reported" is what an earlier report says. "Audit-verified" is what this audit observed directly.

---

## 1. Executive Summary

**Readiness category (exactly one): `READY FOR EXPERIMENTAL WORK ONLY`.** The project is **not operationally ready**.

* **All previous targets were not met.** The 70 % coverage target is not met and no measured evidence supports it. Best verified plan coverage is 39.2 % for default or VUB+LS arms of the final batch (42.3 % in one experimental cost-aware arm).
* **Scorecard (targets A-L, one status each; M is the overall verdict):** `PASS - VERIFIED` 1, `PASS - REPORTED ONLY` 0, `PARTIAL` 9, `FAIL` 0, `UNVERIFIED` 0, `BLOCKED - OWNER DECISION` 2.
  Sub-claim level (section 4.2): 4 claims are `FAIL`/mislabelled and 2 are `UNVERIFIED`. The target-level counts hide these, so read section 4.2 as well.
* **Operationally ready: NO.** Material unresolved inputs remain: the cost-unit reading for handling, the transit-time scope, the transfer dwell and port stay, the transit file, no real canal tariff, and no owner approval for any decision.

Most important findings:

1. **Two incompatible cost regimes sit behind the headline numbers.** The 20-seed figures (default 32.28 M, VUB+LS 38.27 M/week) were produced on commit `e0f9d8a`. That code charges **no canal fees, no per-capacity port-call charge, and no draft rule**. The decision phase (`643ef21`, `6ab68d1`) changed all three. Same seeds 0-9 under the later code: default 31.30 -> 26.10 M, VUB+LS 38.03 -> 30.04 M (section 5). **No 20-seed batch exists on the current code.**
2. **The "-5.3 M/week worst seed" is not a profit.** It is a paired difference (VUB+LS minus default, seed 4: -5.26 M). Every one of the 286 recorded solved runs has positive profit (minimum 4.71 M). Reproduced.
3. **"Best single plan 39.7 % coverage" is not traceable.** The highest plan coverage in the final batch is 39.23 % (F_s3, seed 17). Across all batches it is 42.26 % (experimental cost-aware arm, seed 9). The string 39.7 matches only a "share of demand" in an unserved-demand diagnostic, and the 39.74 M profit maximum. Marked `UNVERIFIED`.
4. **Canal-fee semantics are now established at benchmark level.** The authors' reference code and solution log give the rule; I re-ran the validation: 34/34 traversal counts match and cost matches within the log's 6-digit rounding (max difference $4 per service; total 13,935,090 vs 13,935,070). The "65-75 M/week per assigned vessel" reading is refuted by the authors' own solution, whose total canal cost for the whole network is 13.9 M. No real tariff and no owner countersign exist.
5. **Stale declaration found and fixed (the only code change of this audit).** The assumption register shipped in every result still said canal fees were "not charged / NOT_MODELLED" while the ledger charged them. The register and its pinned test are now corrected (section 13).
6. **Solver status label is misleading (P1, open).** The artifact reports `solver_status: "Optimal"` for the capped MILP while its own gap to the relaxation bound is 50-67 %. Observed in both orchestrator runs of this audit.
7. **Frontend still has defects (P1, open):** hardcoded fallback profits of about 1.16 billion USD/week in two files, and three screens that still compute `load / capacity-per-departure` (for example 1324/900 = 147 % beside a ledger leg load factor of 73.6 %).
8. **Test results reproduced:** targeted suites 226/226 pass; orchestrator 364/364 twice; full suite **34 failed / 1,425 passed / 20 skipped / 9 xfailed**. The 34 failing ids are identical to the decision phase's final list and a subset of the earlier 41. The artifact corruption race did not recur (the file stayed valid JSON after the full suite).
9. **Run-to-run variation on identical code is large.** Two orchestrator runs this audit on the same tree gave 30.64 M / 36.8 % and 26.61 M / 34.0 % (the artifact is overwritten by each run, so only the second survives on disk).

---

## 2. Audit Scope and Evidence Standard

| item | observed |
|---|---|
| Working dir / git root | `.../Liner_shipping_optimizer/shipping_optimizer` / `C:/Users/WINDOWS/Liner-Worldsmall` |
| Branch / HEAD at start and end | `campaign/20261013-issues-1-8` / `64bcf73` (no commit made by this audit) |
| Reported final campaign commit | `e0f9d8a`: exists, is the Issue 8 commit; decision-phase commits `643ef21`, `6ab68d1`, `1b71149`, `c6163b4`, `64bcf73` follow it |
| Baseline tag | `baseline-t11-20261013` is an annotated tag -> commit `95b8c74` (1,572 files, `git ls-tree` count verified) |
| Baseline branch | `baseline/t11-20261013` exists but points to **`95817f7`** (the "Issue 0 baseline report" commit), not to the tag's `95b8c74`. The master report uses both names as if they were one. They differ by report files only; no source file differs (checked with `git diff --name-only 95b8c74 95817f7`) |
| Remotes | `origin` -> github; only `origin/main` is known locally, so neither branch nor tag was pushed (verified from `git branch -a`). This audit pushed nothing |
| Environment | Windows 11, Python 3.11.9, Node v24.14.0, CBC via PuLP |
| Executed in this audit | git inspection; recomputation of every per-seed CSV; ledger-arithmetic identity check (286 rows); LINERLIB canal validation script; targeted pytest (226); `tests/test_orchestrator.py` twice; full `pytest tests`; `node --test frontend/tests/fleetStats.test.mjs` (4/4); independent utilisation check on a fresh artifact |
| **Not executed** | any new optimisation batch; frontend in a browser; `tests/architecture/test_output_contract.py` as a stand-alone run (it ran only inside the full suite and fails 1); Baltic/WAF; WorldLarge (not read, not run) |
| Limitations | The LINERLIB technical report is not available locally; evidence is the authors' reference code and solution log at `C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master` (outside the project tree). Per-seed result JSONs were not re-solved (CBC is wall-clock sensitive), so I verified aggregates from the CSVs, not the solves. LLM providers answered `all_providers_failed`/HTTP 429 during orchestrator runs (deterministic fallback text), as in all earlier runs |

Safeguards respected: nothing deleted, reset or cleaned; no push; no canonical data touched (`data/raw/WorldSmall/*` hashes equal `reports/worldsmall_hashes.txt`; `git diff baseline..HEAD -- data` shows only three added scenario files); no default or flag changed; no solver limit changed.

**Working tree at the end** (details in section 13 and 16): the 5 tracked files that were already modified before this audit are still modified (`P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md`, `SYSTEM_TRUTH_REPORT.md`, `frontend/public/pipeline_output.json`, two `d07/outputs/fortnightly_seed2.*`); the orchestrator and full-suite runs rewrote the first three again (generated outputs). Pre-test copies are in `reports/final_campaign_audit/backup_pre_tests/`. Many untracked outputs from earlier phases remain untracked (`git status` at start lists them).

---

## 3. Previous Phase Commit and Deliverable Verification

`git log --format='%h %p'` confirms a strictly linear chain. Each campaign issue is its own commit with its own diff.

| Issue / phase | Reported commit | In history? | Diff scope (verified by `git show --stat` / name-status) |
|---|---|---|---|
| Baseline T11 | `95b8c74` (+`259d379`) | yes | 1,572 files; evidence reports |
| 0 baseline report | `95817f7` | yes | reports only |
| 1 units | `7460391` | yes | `network_loader.py`, unit tests |
| 2 corrected baseline | `66f3191` | yes | reports, tests classification |
| 3 solver | `707c2f8` | yes | `network_milp.py` guard + `test_milp_no_incumbent.py` |
| 4 coverage | `f558e89` | yes | reports, `paths.py` (+7/-6) |
| 5 register | `18eeea9` | yes | `src/network/opportunities.py` (new, read-only) |
| 6 assumptions | `d2ea1de` | yes | `assumption_register.py` (new) |
| 7 paper evaluator | `87a5cbd` | yes | `src/benchmark/paper_evaluator.py` (new) |
| 8 final validation | `e0f9d8a` | yes | reports |
| Decision: canal + draft + bound scope + load factor | `643ef21` | yes | `physical_rules.py` (new), `ledger.py`, `economics.py`, `reconcile.py`, 5 frontend files, tests |
| Decision: port-call per LINERLIB, D-04 scenario input | `6ab68d1` | yes | `economics.py`, `network_loader.py`, scenario CSV (additive) |
| Decision: capacity status `reference_code`, tracker isolation | `1b71149` | yes | `tests/conftest.py`, loader, **accidentally added `.pyc` files** (untracked again by `c6163b4`) |
| Decision: fleet inventory denominator, D-07 study | `64bcf73` | yes | `strategy_report.py`, `test_utilisation_definitions.py` |

Campaign-wide source/test diff (`git diff --shortstat baseline-t11-20261013 HEAD -- . ':!reports'`): 42 files, 4,036 insertions, 181 deletions. The 41 listed files under `src/`, `tests/`, `frontend/` and `data/scenarios/` are all within stated scope. WorldLarge appears only in three code comments (no read or path). Only environment flags `LINER_MILP_VUB`, `LINER_LOCAL_SEARCH`, `LINER_CLASS_VARIANTS`, `LINER_PATH_SELECTION` exist; source comments state each is default OFF and no source diff sets any of them.

**Mismatches / missing deliverables**

* The DECISION_PHASE_WORK_REPORT covers only part of the decision phase (it says so). Earlier decision-phase work (canal/draft, port-call, capacity status) has no consolidated report; `reports/decision_phase/primary_source_units.md` is the evidence.
* The Issue 8 master report says "restore verified 1,572/1,572". I verified the file count (1,572 in `95b8c74`); byte-equality to the live tree is **REPORTED ONLY** (the live tree was not preserved separately and the zip tree "is not identical", per memory notes).
* No decision memo exists for D-05; `unresolved_decisions.md` (Phase A/D/B audit) still lists D-01 to D-14 as undecided.

---

## 4. Target-by-Target Scorecard

### 4.1 Targets

| ID | Target | Reported | Audit-verified | Evidence | Key finding | Remaining gap | Next action |
|---|---|---|---|---|---|---|---|
| A | Campaign integrity, baseline provenance | PASS | **PARTIAL** | section 3; `git log`; Issue 0 report | Chain, scope, flags, data hashes verified. Baseline tag and baseline branch point to different commits; `.pyc` files were committed then untracked; working tree dirty with generated artifacts | Byte-equality of 1,572 restore is report-only; tag/branch naming ambiguous | Pick one baseline identifier; commit or archive untracked evidence |
| B | Capacity, revenue and unit contract | PASS | **PASS - VERIFIED** | loader lines 14-25, 103, 192-197, 662-708; 226 targeted tests pass; 286-row identity check | `capacity_teu = 2 x Capacity FFE` once at the loader; no lane factors; status `reference_code` (authors' code types capacity as FFE); technical report still unobtained so not `verified`. Profit = revenue - itemised costs on every row (max error 7e-11) | Identity check is arithmetic only, not an independent re-solve of flows | Keep source status as reference-code; obtain LINERLIB report |
| C | Headline reconciliation | n/a | **PARTIAL** | section 5 | All means recompute exactly. Batches are not comparable (two cost regimes, different seeds/arms). "-5.3 M worst seed" is a paired difference. "39.7 % best coverage" untraceable | No batch on current code | Re-run a 20-seed paired batch on `HEAD` (needs authorisation) |
| D | Canal-fee semantics | BLOCKED (D-08) | **PARTIAL** | `validate_against_linerlib_log.py` re-run; `physical_rules.py`; `test_physical_rules.py` | Benchmark-model rule established from primary reference code and reproduced 34/34; implemented, tested, blank Panama fee means "cannot pass" | Fees are benchmark data, not a verified real tariff; no owner countersign; `reports/issue6` exposure figures predate the rule | Owner confirms basis or supplies tariff |
| E | Material cost / operating assumptions | PASS WITH BLOCKERS | **BLOCKED - OWNER DECISION** | section 6.3 | Statuses exposed in every result (13 entries). Sensitivities from Issue 6 reproduce from CSV, but **are not stable under the later cost model** (port stay 12 h: +1.53 -> -4.09 M) | Dwell, port stay, transit file, handling unit, transit scope unresolved | Owner decisions D-04, D-06; custodian confirmation |
| F | Solver variability and bound semantics | PASS | **PARTIAL** | sections 5, 7 | Evidence for VUB/LS reproduces; guard and bound-scope blocks implemented and tested; no promotion | `"Optimal"` label with 50-67 % gap; default still fails under load (2/10 `not_solved` in Issue 4 batch) | Report gap-aware status; keep CBC 120 s frozen |
| G | Coverage and fleet utilisation | PASS | **PARTIAL** | section 8 | Utilisation fix verified by independent re-check; coverage and unserved reasons recompute. **70 % target not met** | Frontend still shows >100 % loads; "fleet inventory exhausted" label coexists with 68 idle large vessels | Fix remaining displays; economics-led candidate work |
| H | Opportunity register | PASS | **PARTIAL** | `issue5_report.md`; 4 tests pass | Scope honest (fixed rest-of-network, 150 of about 1,200 alternatives, 3 seeds) | Built on pre-canal/pre-draft cost model; stale for current economics | Rebuild on current `HEAD` before using |
| I | Paper benchmark isolation | PASS | **PARTIAL** | grep: no `src/network` import of `src/benchmark`; 7 tests pass | Isolation verified; evaluator imports only pandas/stdlib. 19/19 vessel counts and 48 variants are reported only | Not re-executed; profit comparison correctly refused | Re-run `table6` tool if the claim is relied on |
| J | Frontend / output contract | NOT VERIFIED | **PARTIAL** | section 10 | 4/4 node tests pass; artifact schema contract has 1 failing test; hardcoded 1.16 bn fallbacks; leftover `load/capacity` | Frontend never executed in a browser | Fix fallbacks and displays; add contract tests |
| K | Test and regression verification | PASS | **PARTIAL** | section 10 | Results reproduced exactly; no regression versus decision-phase final | 34 failing tests remain (baseline-identical failures are still failures) | D-11 decision; re-baseline golden hashes |
| L | Decision register | open | **BLOCKED - OWNER DECISION** | section 11 | No decision has approval evidence | Everything awaits the owner | Owner session |
| M | Overall readiness | NOT READY for operations | **READY FOR EXPERIMENTAL WORK ONLY** | sections 12, 15 | See verdict | | Section 14 |

### 4.2 Sub-claims that failed or are unverified (not visible in the counts above)

| Claim | Status |
|---|---|
| "Worst seed -5.3 M/week" as a profit | **FAIL** (it is a paired difference; no run is negative) |
| "Best single plan 39.7 % coverage" | **UNVERIFIED** (not found in any per-seed file) |
| Assumption register says canal fees "not charged" | **FAIL**, fixed in this audit |
| Frontend fallback profit 1.16 bn USD/week (`MapCanvas.jsx:89`, `scenarioEngine.js:25`) | **FAIL** (open) |
| Frontend utilisation `load/capacity` in `FleetDashboard.jsx:158`, `RouteTable.jsx:55,102` | **FAIL** (open) |
| Issue 6 sensitivity magnitudes as current guidance | **UNVERIFIED** for the current model (signs flip) |

---

## 5. Headline Metric Reconciliation

Method: `reports/final_campaign_audit/tools/recompute_means.py` reads the raw per-seed CSVs (status `feasible`, profit present). Means are over solved runs; where runs were unsolved I also give the mean counting them as 0. Every run was at CBC single thread, `time_limit_sec = 120`, `PYTHONHASHSEED=0`. Input hashes: fleet `a8986ee2…`, demand `fd46294e…`, ports `b6c8c3b6…`, distances `8edf8cdf…` (`reports/worldsmall_hashes.txt`); the scenario batches change one input as stated.

### 5.1 Reconciliation table

| Reported figure | Recomputed | Batch, seeds, arm, code | Source file | Diff | Explanation | Status |
|---|---:|---|---|---:|---|---|
| Issue 2 default 24.64 M | 24.641 (n=10, all solved; median 26.49, sd 8.35, min 4.71, max 33.52) | I2_base, seeds 0-9, Issue-1 tree | `issue2_corrected_baseline/per_seed_issue2.csv` | 0.00 | Seed 6 produced 4.71 M; replicated later at 34.1 M (CBC wall-clock effect) | PASS - VERIFIED (recompute) |
| Issue 2 "experimental" 35.64 M | 35.643 (n=10; min 33.34, max 38.10) | I2_e = VUB + LS + `LINER_CLASS_VARIANTS=0.10`, seeds 0-9 | same | 0.00 | **Not VUB+LS alone.** It adds class variants. Different arm from the 38.3 M figure | PASS - VERIFIED (recompute) |
| 20-seed default 32.3 M | 32.28 (n=20 solved; median 32.88; sd 4.70; min 17.08; max 39.74) | F_base, seeds 0-19, code `e0f9d8a` (no canal, no per-capacity port call, no draft rule) | `issue8_final/per_seed_final.csv` | 0.02 | Rounding | PASS - VERIFIED (recompute) |
| 20-seed VUB+LS 38.3 M | 38.27 (median 38.75; sd 2.58; min 32.70; max 43.63) | F_s3, seeds 0-19, same code | same | 0.03 | Rounding | PASS - VERIFIED (recompute) |
| Paired gain +6.00 M, 19/20 higher | +6.00, median +6.12, min -5.26 (seed 4), max +22.11, 19/20 | F_s3 minus F_base, aligned on seed, concurrent arms | same | 0 | Paired, same seeds | PASS - VERIFIED |
| Issue 6 reference 39.13 M (VUB+LS), scenarios +4.04 / +3.80 / -7.08 / +1.53 / -8.08 / -16.46 | REF 39.13; T_rev 43.17; dwell1.75 42.93; dwell7 32.06; stay12 40.66; stay48 31.05; costTEU 22.67 | seeds 0-4 only, pre-decision-phase code | `issue6_assumptions/per_seed_scenarios.csv` | 0.00 | Reproduce exactly, but see 5.3 | PASS - VERIFIED (recompute); obsolete for current model |
| Decision-phase D-05: A 26.10, B 29.45, C 30.04 | 26.10 / 29.45 / 30.04 (L1, seeds 0-9); L2 27.59 / 29.71 / 30.51 (seeds 0-4) | arms run concurrently (L1) or sequentially (L2), code `c6163b4` | `decision_phase/d05_final/per_seed_L1.csv`, `per_seed_L2.csv` | 0.00 | Different cost model and seed set than the 20-seed batch | PASS - VERIFIED (recompute) |
| D-06 scenarios (REF 29.79; T_rev +1.83; dwell1.75 +0.09; stay12 -4.09; dwell7 -6.09; stay48 -7.31) | REF 29.79; 31.62; 29.89; 25.71; 23.71; 22.49 | seeds 0-4, arm C, code `c6163b4` | `decision_phase/d06/per_seed_scenarios.csv` | 0.00 | Current-model sensitivities | PASS - VERIFIED (recompute) |

The existing `decision_phase/reconcile/headline_reconciliation.csv` agrees with my recomputation for all 17 batch/arm rows I compared by mean.

### 5.2 Why $24.64 M, $35.64 M, $32.3 M and $38.3 M differ

They are four different experiments, not four estimates of one quantity:

| | seeds | arm | code | concurrency |
|---|---|---|---|---|
| 24.64 | 0-9 | default | Issue-1 tree | 4 arms concurrent |
| 35.64 | 0-9 | VUB + LS + class variants 10 % | Issue-1 tree | 4 arms concurrent |
| 32.28 | 0-19 | default | `e0f9d8a` | 2 arms concurrent |
| 38.27 | 0-19 | VUB + LS | `e0f9d8a` | 2 arms concurrent |

The default's own value on the same seeds 0-9 moves with machine load: I2_base 24.64, I3d_base 28.40, F_base 31.30 (seeds 0-9 of the 20-seed batch). Seed 0 is bit-identical between I2 and F (17.08 M); seed 6 is not (4.71 -> 34.1 M). Therefore unpaired comparison of these means is not a controlled improvement. Only the paired differences inside one concurrent batch are.

### 5.3 The cost-regime break (decisive reconciliation finding)

Seeds 0-9, the same arms, before and after the decision-phase economics (`e0f9d8a` batch vs `c6163b4` batch):

| | profit M/wk | port_call_fixed M | port_variable M | handling M | fuel M | revenue M | fleet inventory column |
|---|---:|---:|---:|---:|---:|---:|---:|
| default, `e0f9d8a` | 31.30 | 0.85 | 0.85 | 16.23 | 29.52 | 96.93 | 263 |
| default, `c6163b4` (arm A) | 26.10 | 8.30 | 0.00 | 17.66 | 28.74 | 98.55 | 205 |
| VUB+LS, `e0f9d8a` | 38.03 | 0.91 | 0.95 | 17.98 | 30.53 | 107.30 | 263 |
| VUB+LS, `c6163b4` (arm C) | 30.04 | 8.59 | 0.00 | 19.15 | 29.43 | 105.53 | 205 |

* Port cost moved 1.70 -> 8.30 M and 1.86 -> 8.59 M. This is the canal fee (7.4-8.2 M predicted by Issue 6) plus the per-capacity port-call charge replacing the per-TEU variable charge. Direction and size are consistent.
* The `205` inventory in the later batch is the **utilisation denominator defect** fixed in `64bcf73` (true 263); the batch pre-dates that fix. Profit is not affected.
* Consequence: the 38.3 M headline is an **upper-bound-like figure that omits ~7-8 M of canal cost and uses a charging basis the benchmark authors do not use.** On the current model the same seeds give 30.04 M (+3.94 M over default 26.10 M; 10/10 seeds higher), and +2.91 M in the sequential L2 run (5/5).
* The default loses ~3.4 M under CPU contention while B/C hardly move (decision report section 2), so the concurrent +3.94 M partly reflects contention. The sequential +2.91 M is the fairer figure.

### 5.4 Negative-profit seed and best coverage

* **Negative profit:** none. Minimum profit over all 286 solved runs is 4.71 M (I2_base seed 6; and 4.71 in I4_base). The "-5.26 M" value is `F_s3 - F_base` at seed 4 (VUB+LS 32.70 M vs default 37.96 M on the same seed). On seed 4 the default happened to reach 37.96 M. Economically valid, not a loss.
* **Best coverage:** final batch default 30.9 % mean, max 35.4; VUB+LS 34.0 % mean, max 39.23 (seed 17). Larger values exist only in other arms: 42.26 % (`I4_s3ca` seed 9, experimental cost-aware path ranking, Issue-3 tree, profit 38.2 M) and 40-41.7 % in the revised-transit scenario (`T_rev`, Issue 6, not canonical input). None equals 39.7.

### 5.5 Remaining unresolved discrepancies

1. No 20-seed paired batch on the current code.
2. The 39.7 % figure.
3. Why the default differs by 3-7 M across batches on identical seeds (CBC wall-clock sensitivity plus load; documented, not reducible without changing solver settings, which this audit must not do).

---

## 6. Financial Model and Unit Validation

### 6.1 FFE/TEU contract (Target B)

* Loader boundary: `src/data/network_loader.py` `TEU_PER_FFE = 2.0` (line 103), `ffe_to_teu` (192), capacity conversion at line 708, demand conversion at the FFEPerWeek read. Per-FFE cost columns divided by 2 at lines 465-475.
* The six per-OD lane factors (1.75-2.1) are gone (`7460391`); invariance tests `tests/test_unit_contract.py` and `tests/test_capacity_units.py` pass in this audit.
* Source classification: `capacity_unit` = `SOURCED_PRIMARY_CODE` (authors' `typedef unsigned long long FFE` and `vesselclass(..., FFE capacity, ...)`; the RL paper agrees). The technical report itself (DTU 19.2010) was not obtained, so I do **not** call it "verified".
* The paper evaluator stays FFE-native; the grep for imports shows no cross-use.

### 6.2 Ledger and cost contract

| item | code | verified how | status |
|---|---|---|---|
| Revenue = demand-weighted per-FFE rate converted once | loader | 286-row identity: revenue - total_cost = profit, items sum to total, served + unserved = demand, coverage = served/demand; max error 7.1e-11 | arithmetic only |
| Port call | `economics.py` 273-279: fixed + callCostPerFFE x capacity per call, per weekly rotation | authors' log: 34/34 services, 5,565,837 USD/wk reproduced (decision-phase evidence; not re-run here) | primary (code + log), reported only |
| Canal fee | `physical_rules.py`, `ledger.py` 176-250 | re-ran `validate_against_linerlib_log.py`: traversal counts 34/34; fee within $4 per service (rounding) | **verified here** |
| Draft | hard rule in `physical_rules.py` and the ledger | decision phase found 23 % of recorded default services violated it | reported only; `test_physical_rules.py` passes |
| Handling / transshipment | per FFE, /2 to per TEU | no per-flow detail in the log | **PROVISIONAL** |
| Fuel | 600 USD/t uniform, design speed only (the benchmark scales burn by (speed/design)^3) | register entries `bunker_price` SECONDARY, `fuel_grade` UNVERIFIED | provisional |
| Vessel cost | TC x 7 per vessel-week | authors' log `Total TC cost` | primary |
| Unserved demand | no rejection penalty in operating profit (paper uses 1,000 USD/FFE) | register `rejection_penalty` | by definition; stated |
| Unused vessels | no credit, no cost | register | provisional |
| Missing inputs | blank Panama fee -> class cannot pass; blank is never zero | `physical_rules.py` header, test | verified |

Profit is calculated from the ledger and never forced to a target (`global_min_coverage` is opt-in; memory notes and code comments agree; no run in the CSVs used a floor).

### 6.3 Assumption register and sensitivities (Target E)

Register entries (artifact of this audit, `network_ledger.assumptions.assumption_register`, 13 entries):
`capacity_unit` PRIMARY_CODE; `ffe_to_teu` SECONDARY; `transit_file` PROVISIONAL; `transit_scope` UNVERIFIED; `port_stay` SECONDARY (24 h); `transfer_dwell` PROVISIONAL (48 h + 3.5 d); `bunker_price` SECONDARY; `fuel_grade` UNVERIFIED; `weekly_frequency` UNVERIFIED; `cost_units` PROVISIONAL; `canal_fees` (**now PRIMARY_CODE**, was stale NOT_MODELLED); `rejection_penalty` PROVISIONAL; `unused_vessels` PROVISIONAL.

Sensitivity reproduction (profit deltas, paired, seeds 0-4, arm VUB+LS):

| assumption | Issue 6 (pre-decision code) | D-06 (current code) | comment |
|---|---:|---:|---|
| revised transit file | +4.04 M, +3.8 pp | +1.83 M, +2.97 pp | direction kept, size halves; one seed -3.75 M |
| transfer dwell 1.75 d | +3.80 M | +0.09 M | effect vanishes |
| transfer dwell 7 d | -7.08 M | -6.09 M | stable |
| port stay 12 h | +1.53 M | **-4.09 M** (1/5 seeds better) | **sign flips** |
| port stay 48 h | -8.08 M | -7.31 M | stable |
| port cost per TEU instead of per FFE | -16.46 M | not re-run on current code | the port-call rule changed, so this scenario no longer describes the current model |

Both columns reproduce from their CSVs. The sign flip shows that one-at-a-time sensitivities are model-version specific; none should be quoted without its code version. The previously reported numbers in the audit prompt are therefore reproduced but **not current**.

Sub-weekly frequency was not implemented. The D-07 study (`reports/decision_phase/d07/D07_subweekly_frequency_study.md`) is read-only: dual-bound movement +0.5 to +2.1 M/wk, HiGHS 240 s, seeds 0-2, stopped at the time limit in all six solves. It supports "needs a separate modelling phase", not an implementation.

---

## 7. Solver and Bound-Scope Audit

**Configuration** (all CSV rows): CBC single thread, 120 s stage limit, `PYTHONHASHSEED=0`, `LINER_SEED` unset, arms of a seed run concurrently. HiGHS 300 s is an owner-gated recommendation (D-09), not enabled.

**Profile comparison (recomputed, paired on seed):**

| profile | batch | mean | vs default (paired) | solved | notes |
|---|---|---:|---|---|---|
| default | F, 20 seeds | 32.28 | | 20/20 | sd 4.70 |
| VUB alone | I2 dev / I3d / I3 hold-out | 34.98 / 35.71 / 35.59 | +10.34 / +7.31 / +8.23 (10/10, 10/10, 9/10) | 30/30 | CSV-reproduced for I2 (+10.34, 10/10) |
| LS alone | I2 dev, I3 hold-out | 35.31 / 35.46 (solved only) | +10.93 (9/9 solved) | **9/10 and 8/10** | see below |
| VUB + LS | F, 20 seeds | 38.27 | +6.00, median +6.12, 19/20 | 20/20 | min paired -5.26 (seed 4) |
| VUB + LS | I3 hold-out / I3d | 38.65 / 38.18 | +11.29 / +9.78 (10/10, 10/10) | 20/20 | |

Larger paired gains in Issues 2-3 than in Issue 8 correspond to a worse default in those batches (24.6 / 27.4 / 28.4 vs 31.3-32.3). The default is the unstable arm.

**Local Search alone is unsafe (verified from CSV):** `I2_ls` seed 8 `not_solved`; `I3_ls` seed 10 `invalid_plan` with `solver_status` "feasible" and **1,748 ledger violations**; `I3_ls` seed 16 `not_solved`. No LS-alone run exists in the final batch, no promotion exists. VUB+LS has 40/40 solved across F, I3 and I3d. Regression coverage: `tests/test_milp_no_incumbent.py` (3 tests, passing) converts an empty CBC result or a demand-nonconserving result into `not_solved`. The Issue 4 default arm still had `not_solved` on 2/10 seeds under 4-way concurrency, so **a missing incumbent can still occur and is reported honestly rather than as an empty plan**.

**Bound scope (verified in code, tests and a live artifact):**

* `reconcile.py` `_capped_gap`, `_capped_model_block`, `_final_plan_block` separate the capped MILP incumbent/bound/gap from the post-solve plan; `tests/test_bound_semantics.py` passes.
* In this audit's first orchestrator run: capped incumbent 26.11 M, bound 52.97 M, gap 26.86 M (50.7 %); final plan 30.64 M; `flow_reoptimisation.applied = true`, `paths_added = 113`, `served_teu` 97,694 -> 101,724 (+4.53 M). So the final plan **does leave the capped model's path set** and is not comparable to its bound. In the second run: final 26.61 M, gap 60.2 %.
* The Issue 8 master table still lists "gap to model bound -4.7 % (final plan exceeds bound)" for VUB+LS. Under the contract this is `exceeds_capped_model_bound`, not a negative gap and not optimality evidence. The CSV was produced before the contract existed.
* **Open defect (P1):** `capped_model.solver_status` is `"Optimal"` in both runs while the gap is 50.7 % and 60.2 % (`mip_gap_reported_by_backend` is `null`). This is the PuLP/CBC status of a time-limited solve and will be read as proven optimality by a consumer. Recommended: report `time_limit_reached_gap_x%` when the gap exceeds a tolerance. Not changed here because it alters a reported field consumed by tests and the frontend.

Variation at the configured limit (default, solved runs): sd 4.7 M over 20 seeds (range 17.08-39.74), seed-to-seed and replicate-to-replicate. VUB+LS sd 2.58 M. Two orchestrator runs on identical code: 30.64 M and 26.61 M.

---

## 8. Coverage, Fleet, and Utilisation Audit

**Definitions (from `strategy_report.py` and the artifact):** coverage = served TEU / demand TEU (TEU-weighted, both converted once). It is covered demand, not "profitable covered demand": the optimiser serves only demand with positive marginal value, but no separate profitable-coverage metric exists. Verified on the fresh artifact: 101,724 / 276,494 = 36.79 % = reported `summary_metrics.coverage`; the six `unserved_by_reason` shares sum to 63.2 % = 100 - 36.8.

**Fleet (263 vessels, fresh artifact, run 1):**

| class | used / available |
|---|---|
| Feeder_450 | 24 / 24 |
| Feeder_800 | 27 / 29 |
| Panamax_1200 | 67 / 68 |
| Panamax_2400 | 74 / 74 |
| Post_panamax | **0 / 58** |
| Super_panamax | **0 / 10** |

Vessel utilisation (assigned / owned) 192/263 = 0.730 (run 1), 185/263 = 0.703 (run 2). The decision-phase defect (0.868 over a 205 denominator) is fixed: `utilisation_independent_check.py` re-run on the fresh artifact reports max difference 0.0 on 31 services, network leg load factor 0.585 independent = reported, vessel utilisation 0.7034 independent = reported. Leg load factor (carried / offered TEU-legs) 0.60-0.62; the three definitions (vessel utilisation, leg/service load factor, network load factor) are now separate fields. Leg-factor arithmetic was independently recomputed from flows and rotations only.

**Bottlenecks (current artifact, share of all demand):** fleet inventory exhausted 46.7 %; no time-feasible service in the pool 8.1 %; capacity exhausted on served OD 4.3 %; transit limit below fastest sailing time 3.4 % (physically unattainable); not economic 0.7 %. Caveat: the label "fleet inventory exhausted" is applied while 68 large vessels sit idle; those vessels are not suited to the small-class lanes. So the binding constraint is the **small/medium class inventory plus candidate design and economics**, not total fleet. Issue 4 (reported) adds: per-OD path cap and ranking are the largest model restriction; LP relaxations reach 50.6 % (path cap lifted) and 55-57 % (class inventories x100). Those are relaxed upper bounds under altered assumptions, not executable schedules, and were not re-run here.

**Target gap:** best verified feasible coverage 39.23 % (final batch), mean 34.0 % for VUB+LS; orchestrator runs 33.98-36.79 %. **70 % is not demonstrated and not supported.** The authors' own base solution (94.2 % transported, no end-to-end transit constraint) differs in problem definition, so it is not evidence either way.

Idle large vessels are not forced into loss-making service; no code path does this (global coverage floor is opt-in).

---

## 9. Paper Benchmark Validation

* Isolation: `src/benchmark/paper_evaluator.py` imports only stdlib and pandas; `grep` finds no import from `src/network`; `tests/test_paper_evaluator.py` (including the no-import test) passes (7 tests, within the 226).
* FFE-native: reads raw files, no loader conversion (module docstring and tests).
* Table 6: 19/19 schedules resolved and fractional vessel counts equal to 3 digits (**reported only**; not re-run here). This confirms distances, design speed, 1 day per port call and a weekly horizon. It does **not** confirm profit.
* Paper profit: 48 interpretation variants range -1,406 to +95 M/wk against the paper's 32-43 M; none within 40 %. The profit horizon, voyage-cost basis (per rotation vs times fractional vessels) and Table 2 row alignment are unresolved. No Table 2 value is used as a target. **The paper's 32-43 M is not reproduced.**
* The operational transit constraint is absent from the paper evaluator by design; the paper states no transit-time constraint (matching the authors' benchmark).
* D-02 (adopt a paper mode) is not decided.

---

## 10. Frontend, Output Contract, and Test Integrity

### 10.1 Consumers checked

* `node --test frontend/tests/fleetStats.test.mjs`: 4/4 pass (cargo above per-departure capacity not shown as >100 %; missing leg data is unknown; vessels summed; volume-weighted aggregation).
* Artifact check: `frontend/public/pipeline_output.json` carries `leg_load_factor` and `weekly_capacity_per_leg` next to `load`/`capacity` (e.g. 1324 / 900, leg load factor 0.7356).
* Defects found by code reading (not by running a browser):
  * `frontend/src/components/optimization/RouteTable.jsx:55` (Avg Load Factor) and `:102-103` (per-service load %), `FleetDashboard.jsx:43-44,158-159` still compute `load / capacity` with per-departure capacity, so they show the >100 % pattern. The decision phase fixed other screens (`FleetPanel`, `FleetIntelligence`, `ServiceDetailPanel`, the RouteTable detail pane) but not these.
  * `MapCanvas.jsx:89` falls back to `1176324858` USD (and 50.9 % coverage, 547 services); `scenarioEngine.js:25` falls back to `1161089814.67` (and fuel 1.70 bn). If the backend field is missing, these show a profit about 40 times the real value as if it were a result. This violates "missing computation must not look like a success".
  * `ExportPanel.jsx:48` and several tables use `|| 0` for missing profit and margin.
* Not done: browser run of the dashboard; a contract test for these screens. Frontend compatibility is **not claimed**.

### 10.2 Tests actually executed in this audit (all from `shipping_optimizer/`, Python 3.11.9)

| # | command | result | notes |
|---|---|---|---|
| 1 | `pytest tests/test_unit_contract.py tests/test_capacity_units.py tests/test_worldsmall_loader.py tests/test_worldsmall_integration.py tests/test_physical_rules.py tests/test_bound_semantics.py tests/test_utilisation_definitions.py tests/test_milp_no_incumbent.py tests/test_paper_evaluator.py tests/test_assumption_register.py tests/test_opportunities.py tests/test_transit_composition.py -q` | **226 passed**, 0 failed, 74.65 s | campaign branch, before my change |
| 2 | `python tests/test_orchestrator.py` | **364/364 assertions, 0 failed**, score 100; weekly profit 30.64 M, coverage 36.8 %; exit 0 | log `orchestrator_audit.log`; calls LLM providers (all failed with 429, deterministic fallback) |
| 3 | `pytest tests -q -p no:cacheprovider` (after #2, sequential) | **34 failed, 1,425 passed, 20 skipped, 9 xfailed**, 753 s; exit 1 | log `full_suite_audit.log`, ids `fail_audit.txt` |
| 4 | `pytest tests/test_assumption_register.py tests/test_physical_rules.py -q` (after my fix) | **12 passed** | targeted check for the change |
| 5 | `python tests/test_orchestrator.py` (after my fix) | **364/364, 0 failed**, score 100; profit 26.61 M, coverage 33.98 %; exit 0 | log `orchestrator_audit_after_fix.log` |
| 6 | `node --test frontend/tests/fleetStats.test.mjs` | 4 pass | |
| 7 | `python -I reports/decision_phase/d08/validate_against_linerlib_log.py` | counts 34/34; 7 services differ by $2-4 from the 6-digit log print | the script's strict 1.0 tolerance reports 27 equal; counts equal in all 34 |
| 8 | `reports/final_campaign_audit/tools/ledger_identity_check.py` | 286 rows, 0 mismatches | arithmetic identities only |

**I did not re-run the full suite after my small register fix.** The fix touches one source file and one test; targeted tests (#4) and the orchestrator (#5) pass. The full-suite result in #3 is from the tree before that edit.

### 10.3 Failure classification (34)

* 29 x `tests/test_economic_metric_documentation.py`: documentation-drift set (D-11, `re-audit`).
* 4 golden-hash tests (`test_phase5_weather`, `test_phase6_congestion`, `test_phase7_integration`, `test_phase9_operational_intelligence`): they pin SHA-256 of `pipeline_output.json` (`ec91fc59…`, `ad33a96e…`, `a578877a…`). The committed file at the baseline tag, `e0f9d8a` and `HEAD` is `37c775c8…`, equal to none of the pinned values, and the regenerated file is `f825d01b…`. **These tests fail for any artifact currently possible, so they are not regressions but are failures.**
* 1 x `tests/architecture/test_output_contract.py::test_regions_count_and_keys_frozen` (`regions == 5`), pre-existing on the baseline per Issue 8.
* Comparison by test id: the 34 are identical to `reports/decision_phase/final/fail_final.txt` (0 differences either way) and a subset of the 41 of `issue8_final/fail_final.txt` (7 fewer: seven `test_output_contract.py` tests that failed in Issue 8 now pass). I did not re-run the baseline tag in this audit, so "identical to the baseline" for the earlier 41 failures is reported only.

### 10.4 Artifact race

* Cause documented in `tests/conftest.py`: the process-wide `health_tracker` singleton collected MagicMock objects from regional-agent tests, so a later `json.dump` of the orchestrator result failed and a truncated `pipeline_output.json` remained. The autouse fixture resets the tracker around every test; `1b71149` also made the write atomic and non-silent.
* Verification: after the full suite in this audit both copies of `pipeline_output.json` are valid JSON (identical hash `f825d01b…`). Earlier suites left corrupt copies (`reports/issue*/pipeline_output_corrupt_after_*.json` exist as evidence). One clean run is evidence, not proof. I did not reproduce the corruption on the baseline tag.
* Note: the corruption was a cross-test state leak, not a parallel race. No parallel process shared the file in this audit.

---

## 11. Decision Register

No decision below has explicit owner approval evidence in the repository. Engineering recommendations are not approvals.

| ID | Question | Evidence | Prior status | Audit status | Authorised changes | If unresolved | Next action / role |
|---|---|---|---|---|---|---|---|
| **D-08** canal fees | Basis of the canal charge | Authors' `calculate_canal_cost` ("for one round trip") and solution log; re-run: 34/34 counts, fee within rounding; blank Panama = cannot pass (class draft 13.0/12.5 m > edge 12.0 m) | BLOCKED | **Implemented from primary reference code; owner countersign and real tariff outstanding** (`PARTIAL`) | Code already charges it (`643ef21`); not owner-approved | Profits are costed on benchmark fees, not a tariff | Owner confirms benchmark fees acceptable or supplies tariff |
| **D-05** VUB+LS | Promote? | 20-seed paired +6.00 M (old code); +2.91 M sequential, +3.94 M concurrent (current code); LS alone unsafe | open | **Tested, not approved, not promoted.** `LINER_MILP_VUB` and `LINER_LOCAL_SEARCH` default OFF in source | none | Operations stay on the unstable default | Owner decision; recommended: both together, never LS alone |
| **D-04** revised transit file | Adopt? | `data/scenarios/WorldSmall_revised_transit_v1/MANIFEST.json`: status "SCENARIO INPUT - not canonical"; 105 ODs changed; upstream does not state whether port time or dwell is included; +1.83 M (current) / +4.04 M (old) | open | **Open; scenario separate and versioned**; not adopted | none | Transit scope stays UNVERIFIED | Owner and custodian |
| **D-06** dwell / port stay | Operating convention | 48 h + 3.5 d dwell is a convention; port stay 24 h from benchmark page; sensitivities section 6.3 (port-stay sign unstable) | open | **Open**; two separate assumptions kept separate | none | +-2 to 8 M conditional | Owner supplies source/policy |
| **D-07** sub-weekly | In scope? | D-07 study read-only; not implemented | open | **Deferred; a separate modelling phase is required** | none | Thin long routes stay expensive | Owner decides scope |
| **D-01** units (primary source) | Capacity/cost units | `capacity` PRIMARY (reference code); port call PRIMARY (code + log); handling/transshipment unit **PROVISIONAL**; technical report not obtained | open | Capacity: strong code evidence, **not "verified"**; handling unit open | none | Largest remaining unit risk is handling | Data custodian: report 19.2010 or column dictionary |
| D-02 paper mode | adopt a separate mode | issue 7 | open | Open | none | no like-for-like benchmark | Owner |
| D-09 HiGHS / 300 s | change backend/limit | task 15 | open | Open; CBC 120 s frozen | none | | Owner |
| D-11 doc-drift tests | retire/restore/re-audit | 29 failing doc tests | open | Open | none | red suite remains | Owner |
| D-12 verdict bands, Tier-0 | decide | `tier0_consumer_recertification.md` | open | Open; consistent with J findings | none | | Owner |
| D-13 version baseline | commit tree | Issue 0 | blocked | Substantially resolved by `95b8c74` (tag) | done | naming ambiguity | Owner picks identifier |
| D-03 lane factors | remove | removed in `7460391` | open | **Resolved in code** (removed, not owner-recorded) | done | | confirm |
| D-10 `LINER_SEED` | | | open | Open | none | | Owner |
| D-14 scalability | | | open | Open | none | | Owner |

---

## 12. Residual Risk Register

| # | Sev | Risk | Evidence | Affected claims | Mitigation | Owner dependency | Closure criterion |
|---|---|---|---|---|---|---|---|
| R1 | **P0** | Headline profits (32.3 / 38.3 M) are on the pre-canal, pre-port-call-rule model; current-model equivalent is 26-30 M | section 5.3 | Any quoted profit or gain | Quote only current-model numbers, with code version | none | 20-seed paired batch on current `HEAD` committed with hashes |
| R2 | **P0** | Material cost assumptions unverified: handling per-FFE unit, transit-time scope, dwell, port stay, transit file; sensitivities flip sign across model versions | section 6.3 | "Operationally costed" | Keep labels PROVISIONAL/UNVERIFIED | D-01, D-04, D-06 | Source or owner approval for each; sensitivities re-run on the approved model |
| R3 | **P0** | Canal fees are benchmark data, no real tariff, no owner countersign | section 11 D-08 | Operational profit | Declared in register | D-08 | Owner confirms or provides tariff |
| R4 | P1 | `solver_status = "Optimal"` with 50-67 % gap | artifacts of both orchestrator runs | Solver quality claims | Gap-aware status field | none | Field reports time-limit/gap; consumer test |
| R5 | P1 | Frontend fallbacks (1.16 bn USD) and per-departure load percentages remain | section 10.1 | Dashboard credibility | Remove fallbacks, use `leg_load_factor`, add consumer test | none | Fixes plus passing contract tests |
| R6 | P1 | Default solve unstable (17-40 M across seeds; load-dependent; `not_solved` possible under load) | CSVs | Reproducibility | VUB+LS candidate; frozen CBC 120 s | D-05, D-09 | Promotion decision with fresh batch |
| R7 | P1 | 34 failing tests; 4 golden-hash tests cannot pass | section 10.3 | "Green suite" | Classify, do not weaken | D-11 | Re-baseline or retire with approval; suite red count documented |
| R8 | P1 | Opportunity register built on obsolete economics | issue 5 date vs `643ef21` | Opportunity list | Rebuild | none | Re-run on `HEAD` |
| R9 | P1 | 39.7 % coverage figure untraceable | section 5.4 | Best-plan claim | Replace by 39.23 % (final batch) | none | Master report corrected |
| R10 | P2 | `baseline/t11-20261013` branch != tag commit | section 2 | Rollback instructions | State one identifier | none | One documented baseline |
| R11 | P2 | `.pyc` committed then untracked (`1b71149`, `c6163b4`); many untracked outputs | git status | Repo hygiene | commit or archive evidence | none | Clean status |
| R12 | P2 | No scalability evidence beyond 47 ports; LLM providers failing | prior reports, run logs | Scale claims | none | D-14 | |

---

## 13. Changes Made During the Audit

One narrow fix, within section 17 policy: reproducible, intended behaviour is established (the ledger charges canal fees since `643ef21`; the register's own docstring defines `NOT_MODELLED` as a cost the model does not include), no business assumption is decided (the register only describes what the code does), a regression test validates it, and it is independently revertible.

* `src/network/assumption_register.py`: `canal_fees` row now `SOURCED_PRIMARY_CODE`, with the charging basis and "owner countersign (D-08) outstanding"; `cost_units` value text updated to state that port calls are fixed + per-FFE x capacity (previously "PortCallCostPerFFE are USD per FFE ... per TEU").
* `tests/test_assumption_register.py`: the pinned assertion `by["canal_fees"]["status"] == "NOT_MODELLED"` replaced by `SOURCED_PRIMARY_CODE` plus `"not charged" not in value`. The old assertion pinned the stale declaration; the change corrects what the test protects, it does not weaken a behavioural check. Diff: 2 files, 9 insertions, 4 deletions (`git diff --stat`).
* Verification: `pytest tests/test_assumption_register.py tests/test_physical_rules.py` 12 passed; `python tests/test_orchestrator.py` 364/364; the fresh artifact shows `canal_fees: SOURCED_PRIMARY_CODE`. Full suite not repeated afterwards (see 10.2).
* Not committed (commit only on request). To commit: `git add Liner_shipping_optimizer/shipping_optimizer/src/network/assumption_register.py Liner_shipping_optimizer/shipping_optimizer/tests/test_assumption_register.py`.
* Rollback: `git checkout -- Liner_shipping_optimizer/shipping_optimizer/src/network/assumption_register.py Liner_shipping_optimizer/shipping_optimizer/tests/test_assumption_register.py`.

Side effects: the orchestrator and full-suite runs rewrote `pipeline_output.json` (root and `frontend/public/`), `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md`, `SYSTEM_TRUTH_REPORT.md` (already modified before the audit). Pre-test copies: `reports/final_campaign_audit/backup_pre_tests/` (`pipeline_output.json`, `root_pipeline_output.json`; the two markdown files were not backed up, only reachable through `git diff` vs HEAD). Restore example: `cp reports/final_campaign_audit/backup_pre_tests/pipeline_output.json frontend/public/pipeline_output.json`.

Findings **not** fixed (need a decision or are outside a minimal edit): frontend fallbacks and `load/capacity` displays; the `"Optimal"` label; stale Issue 8 table row "gap -4.7 %".

---

## 14. Next-Phase Recommendation

**Recommended phase: "re-baseline on the current model, then experimental coverage work". Operational deployment stays blocked.**

Ordered prerequisites:

1. Authorise and run one 20-seed paired batch (default vs VUB+LS) on current `HEAD`, sequentially or with equal load, CBC 120 s, committing per-seed JSON, hashes, environment and the code commit. This replaces the 32.3 / 38.3 figures.
2. Fix the frontend fallbacks and the three `load/capacity` screens; add a consumer test over a real artifact; make the solver-status field gap-aware.
3. Owner session on D-08 (countersign benchmark fees or supply tariff), D-01 handling unit (custodian), D-04 and D-06; re-run the one-at-a-time scenarios on the approved model.
4. Rebuild the opportunity register on `HEAD`.
5. D-11: re-audit the 29 documentation tests; re-baseline or retire the 4 golden-hash tests with approval.
6. Then, and only then, a coverage-optimisation experiment (candidate quality, per-OD path ranking, small/medium class inventory), carried in labelled experimental profiles.

Safe experiments now (labelled provisional, never described as operational profit): VUB+LS arms, scenario trees for D-04/D-06, HiGHS studies, sub-weekly twin study extension.

Blocked by owner decisions: promotion of any profile, the transit file, dwell/port-stay conventions, sub-weekly implementation, HiGHS/300 s, adoption of paper mode.

Explicit exclusions: no WorldLarge, no Baltic/WAF, no change of canonical data or solver limits, no forcing of idle vessels into loss-making services, no promise of 70 % coverage.

---

## 15. Final Verdict

* **Targets met:** B (unit and revenue contract) only.
* **Partially met:** A, C, D, F, G, H, I, J, K.
* **Blocked by owner decisions:** E, L.
* **Failed / unverified at sub-claim level:** "-5.3 M worst seed" as a profit (fails), "39.7 % best coverage" (unverified), stale register (fixed), frontend fallbacks and displays (open), Issue 6 sensitivities as current guidance (unverified).
* **Open P0:** R1, R2, R3. **Open P1:** R4-R9.
* **70 % coverage target:** not met; no evidence it is attainable on the current model.
* **Next optimisation phase may begin: only as experimental work**, after prerequisite 1 gives a trustworthy baseline.
* **Operational deployment: blocked.**
* Independently verified here: headline means and paired differences (recomputed), ledger arithmetic, canal rule vs authors' log, utilisation arithmetic, the 364/364 orchestrator result, the 34-failure suite result, paper evaluator isolation, data hashes and flag defaults. Report-only: Table 6 19/19 and the 48 variants, the LP upper bounds, the port-call log reproduction, baseline-identical status of the earlier 41 failures, byte-level restoration of the 1,572 files.

---

## 16. Evidence Index

| item | path / id |
|---|---|
| This report | `reports/final_campaign_audit/FINAL_CAMPAIGN_WORK_REPORT.md` |
| Scripts written (read-only) | `reports/final_campaign_audit/tools/recompute_means.py`, `ledger_identity_check.py` |
| Logs | `reports/final_campaign_audit/orchestrator_audit.log`, `orchestrator_audit_after_fix.log`, `full_suite_audit.log`, `fail_audit.txt`, `hash_after_orch.txt`, `utilisation_independent_check_audit.json` |
| Temp comparison lists | `reports/final_campaign_audit/_tmp_final.txt`, `_tmp_issue8_final.txt`, `_tmp_issue2_corrected_baseline.txt` (failing-id lists) |
| Backups | `reports/final_campaign_audit/backup_pre_tests/` |
| Per-seed data | `reports/issue2_corrected_baseline/per_seed_issue2.csv`; `reports/issue3_solver/per_seed_{dev_repl,holdout}.csv`; `reports/issue4_coverage/per_seed_issue4.csv`; `reports/issue6_assumptions/per_seed_scenarios.csv`; `reports/issue8_final/per_seed_final.csv`; `reports/decision_phase/d05_final/per_seed_{L1,L2}.csv`; `reports/decision_phase/d06/per_seed_scenarios.csv` |
| Prior reports | `reports/issue8_final/MASTER_REPORT.md`; `reports/decision_phase/final/DECISION_PHASE_WORK_REPORT.md`; `reports/decision_phase/primary_source_units.md`; `reports/audit_20261013_phaseADB/unresolved_decisions.md`; `reports/issue{0,3,5,6,7}_*/*report.md` |
| Existing reconciliation | `reports/decision_phase/reconcile/headline_reconciliation.csv` |
| Canal validation | `reports/decision_phase/d08/validate_against_linerlib_log.py` (log at `C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\...\WorldSmall_Best_Base.log`, outside the project) |
| Code | `src/data/network_loader.py`; `src/network/{economics,ledger,physical_rules,reconcile,strategy_report,assumption_register,network_milp}.py`; `src/benchmark/paper_evaluator.py`; `tests/conftest.py` |
| Frontend defects | `frontend/src/components/console/MapCanvas.jsx:89`; `frontend/src/services/scenario/scenarioEngine.js:25`; `frontend/src/components/optimization/RouteTable.jsx:55,102`; `frontend/src/components/optimization/FleetDashboard.jsx:43,158` |
| Commits | `95b8c74` (tag `baseline-t11-20261013`), `95817f7` (branch `baseline/t11-20261013`), `7460391`, `66f3191`, `707c2f8`, `f558e89`, `18eeea9`, `d2ea1de`, `87a5cbd`, `e0f9d8a`, `643ef21`, `6ab68d1`, `1b71149`, `c6163b4`, `64bcf73` |
| Data hashes | fleet `a8986ee2…`, demand `fd46294e…`, ports `b6c8c3b6…`, dist_dense `8edf8cdf…` (`reports/worldsmall_hashes.txt`); artifact hashes: committed `37c775c8…`, regenerated `f825d01b…`, post-orchestrator-1 `89623f35…` |
| Missing evidence | LINERLIB technical report (DTU 19.2010); per-flow handling detail in the authors' log; any owner approval record; a 20-seed batch on current code; baseline-tag suite re-run; browser run of the frontend |
| Final HEAD | `64bcf73` (unchanged by this audit); the report and the two edited files are uncommitted |

---
**Continuation (2026-10-15):** current-code 20-seed experiment, decision workstreams and hardening are in `CAMPAIGN_CONTINUATION_REPORT.md`. It supersedes the 32.28 / 38.27 M headline figures with 24.71 / 30.12 M (default / VUB+LS) on the current cost model.
