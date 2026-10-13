# Overnight Tasks 8A · 8B · 9 · 10 — final report

**Date:** 2026-10-11 · **Scope:** WorldSmall only (no WorldLarge file was read) · **Baseline:** the tree as found
(U7 code), frozen as snapshot `M0` with a SHA-256 manifest · **Not done, by instruction:** Task 11 (two-transfer paths),
Task 12 (route-level GA operators).

## 1. Status

| Task | Status | Focused tests | Orchestrator | Ledger | Baseline comparison |
|---|---|---|---|---|---|
| 8A — F-15 accounting | **PASS** | `test_decision_economics` 25/25; flipped F-15 tripwires pass; 135 passed in the artifact-dependent set | 327/327 at the gate (310 + 17 new); 342/342 final | 0 violations; section O recomputes cost, revenue, profit, margin from raw data = `global_metrics` to the dollar | same captured plans replayed: margin 25.9 % → **11.28 %** (= ledger); selected iteration and evaluation score unchanged |
| 8B — regional bunker pricing | **PARTIAL** | `test_bunker_pricing` 67/67 | 342/342 final (legacy default) ×3; market-price mode **349/349 ×3** on the final tree (the earlier run on the legacy pool: 337/339, two honest "services selected" failures) | 0 violations; ledger reconciles against the exact pinned snapshot (id + SHA-256), per-service price recomputed independently | same captured inputs: legacy pool $2.0–4.2 M (600) vs $0.1–0.4 M (market; exact optimum 0.85 M); final pool $8.8 M vs **$3.05 M** (optimal 2.7–3.5 M); end-to-end market mode $4.25 M (n=3); **default kept at legacy 600 USD/t — approved decision (§11)** |
| 9 — demand-coherent generation | **PASS** | `test_demand_coherent` 27/27, `test_hub_detector_cache` 4/4, `test_regional_ownership` 8/8 | 342/342 | 0 violations in 130+ controlled runs | 5 seeds, paired: **+$2.70 M/wk (5/5 seeds)**, coverage 8.5 → 12.9 % |
| 10 — class screening | **PASS** | `test_class_screening` 35/35 | 342/342 | 0 violations | on the Task 9 pool **+$2.80 M/wk (5/5)**; combined vs original **+$5.50 M/wk (5/5)**, coverage 8.5 → 20.0 % |

Recertification: orchestrator **342/342** on every final-tree run; broader suite **0 newly failing** against the frozen
baseline in both artifact states (§4); the remaining 52–53 failures are the baseline's own (29 missing audit documents,
LLM-mock activation tests, phase-8 command centre, SHA pins, `test_setup`).

## 2. Economic and operational comparison

### 2a. End-to-end orchestrator (full pipeline incl. regional GA/MILP/coordinator; unseeded; mean of n runs)
*Note: the final-default column is the three runs `FINAL7_default_run1..3` on the final code state (342/342 each; the production code `src/`, `backend/`, `data/` is byte-identical across the three snapshots and the focused-test snapshot, only reports/docs and one added test file differ - tree-manifest SHA-256 per run in `evidence/comparisons/run_register.md`). Earlier final-default runs on preceding code states (`FINAL2_default_run1..3`: 8.99 / 10.93 / 8.32 M, `FINAL4_default_run1` 8.96 M, `FINAL6_default_run1` 9.52 M; all 342/342) are in `evidence/runs/` and the run register.*

| Metric | Frozen baseline M0 (n=1) | Task 8 (legacy configuration) (n=3) | Task 9 (loops 60) (n=2) | Task 10 final (default) (n=3) |
|---|---:|---:|---:|---:|
| Verified weekly profit (USD) | 2,671,085 | 2,997,948 | 6,117,190 | 9,056,448 |
| Profit margin on revenue (%) | 11.5 | 10.7 | 13.2 | 13.3 |
| Cargo coverage (% of demand) | 6.5 | 8.2 | 13.5 | 21.1 |
| Unique served TEU / week | 17,962 | 22,696 | 37,213 | 58,301 |
| Selected services | 8.0 | 9.3 | 11.5 | 18.0 |
| Vessels deployed | 40 | 37 | 80 | 122 |
| Fuel cost per week (USD) | 9,728,592 | 11,106,175 | 19,293,578 | 28,103,044 |
| Candidate count (modelled pool) | 1,083 | 1,089 | 1,220 | 1,174 |
| Global-stage runtime (s) | 25 | 24 | 28 | 116 |
| Whole pipeline runtime (s) | 159 | 75 | 92 | 336 |
| Ledger violations (sum) | 0 | 0 | 0 | 0 |

Per-run weekly profit (USD) / coverage (%) / assertions:

* **Frozen baseline M0**: `M0_orch` 2,671,085 / 6.5% / 310/310 (verified True, MILP feasible)
* **Task 8 (legacy configuration)**: `LEGACY6_run1` 2,342,117 / 7.7% / 342/342 (verified True, MILP feasible); `LEGACY6_run2` 3,441,048 / 8.7% / 342/342 (verified True, MILP feasible); `LEGACY6_run3` 3,210,678 / 8.2% / 342/342 (verified True, MILP feasible)
* **Task 9 (loops 60)**: `T9ONLY6_run1` 6,439,113 / 14.4% / 342/342 (verified True, MILP feasible); `T9ONLY6_run2` 5,795,266 / 12.6% / 342/342 (verified True, MILP feasible)
* **Task 10 final (default)**: `FINAL7_default_run1` 9,022,634 / 18.8% / 342/342 (verified True, MILP feasible); `FINAL7_default_run2` 9,112,217 / 20.1% / 342/342 (verified True, MILP feasible); `FINAL7_default_run3` 9,034,492 / 24.4% / 342/342 (verified True, MILP feasible)


Reading: all three final-default runs are above every legacy-configuration run and every Task-9-only run (9.02 / 9.11 / 9.03 M vs 2.34–3.44 M and 5.80–6.44 M). The pipeline is unseeded, so single runs vary (the legacy configuration alone spans $1.1 M); that is why three runs per setting were taken. The price of the better network is time: whole-pipeline runtime 159 s → 336 s and global MILP 25 s → ~116 s (it now uses most of its 120 s limit).

### 2b. Controlled experiment (same problem, same regional split, same generator seeds 0–4, same global stage)
| Metric | Frozen baseline (original pool) | Task 8 (= baseline pool; pricing/F-15 change reporting, not plans) | Task 9 (+ demand loops) | Task 10 final (+ class screening k=1) |
|---|---:|---:|---:|---:|
| Verified weekly profit | $3.25 M (sd 1.88) | $3.25 M — identical plans by construction | $5.95 M (sd 0.56) | **$8.75 M** (sd 0.47) |
| Profit margin on revenue | 10.8 % | 10.8 % | 13.5 % | 13.8 % |
| Cargo coverage | 8.5 % | 8.5 % | 12.9 % | **20.0 %** |
| Selected services | 9.8 | 9.8 | 11.4 | 17.6 |
| Vessels deployed (of 263) | 42 | 42 | 80 | 115 |
| Candidate count (unique pool) | 1,140 | 1,140 | 1,272 | 1,213 |
| Stand-alone profitable candidates | 10.6 | 10.6 | 75.8 | 90.8 |
| Global MILP runtime (s, 120 s limit) | 23 | 23 | 28 | 104 |
| Ledger violations | 0 | 0 | 0 | 0 |

Full per-seed and paired tables: `evidence/comparisons/task9_task10_final_tables.md`.

## 3. Fuel prices actually used (the only ones in the repository besides the legacy constant)
| Region / port | Fuel grade | Price | Unit | Observation time | Source | Provenance status |
|---|---|---:|---|---|---|---|
| (all services, default) | assumed VLSFO-equivalent | 600.00 | USD/metric tonne | not dated (benchmark documentation) | LINERLIB benchmark documentation | **assumed** — default |
| Singapore (SGSIN) | VLSFO | 889.50 | USD/mt | 2026-10-09 (page label "F Oct 9"; year inferred) | Ship & Bunker public page | observed |
| Rotterdam (NLRTM) | VLSFO | 715.00 | USD/mt | 2026-10-09 | Ship & Bunker public page | observed |
| Hong Kong (HKHKG) | VLSFO | 949.00 | USD/mt | 2026-10-09 | Ship & Bunker public page | observed |
| LA / Long Beach (USLAX) | VLSFO | 1,044.00 | USD/mt | 2026-10-09 | Ship & Bunker public page | observed (market applied to USLAX) |
| Santos (BRSSZ) | VLSFO | 850.50 | USD/mt | 2026-10-09 (same quote repeated 6–9 Oct) | Ship & Bunker public page | observed, indicative |
| Global 20 Ports Average (reference) | VLSFO | 895.50 | USD/mt | 2026-10-09 | Ship & Bunker public page | observed index |

Snapshot `shipandbunker_vlsfo_2026-10-09`, SHA-256 `a03086668958f79009491600a6294efb90351e6520d739420d9fb6097beb5835`.
42 of 47 WorldSmall ports have no direct observation (they use the reference when the regional mode is on). No licence to
redistribute was found; nothing behind a paywall was used. Details and the design record: `task8_regional_bunker_pricing.md`.

Outputs recorded **before** the `bunkering_location` field was added (`pricing_replay_U4_*`, `T8B_orch2_regional`) carry the earlier snapshot hash `fa39a8f206b3f41569cdece795017107482934f6b6c6a6dd79b017cfe5636f73`; the prices are identical, only the per-price location text is new. Every output labelled `FINAL*` carries `a03086668958…5835`.

**Bunkering-location assumption (recorded in the snapshot for every price, part of the pinned hash):** each port price is a
port-level spot quote, applied only to rotations that call at that port, with the whole rotation's fuel assumed bought
alongside the cheapest observed port it calls at (an optimistic bound); the 20-port average is an index, not a purchase
location, used only for rotations that call at no observed port. The USD 600/t row is the LINERLIB benchmark's own
assumption: it is **not** presented as the October-2026 market median, and the repository holds no historical series that
could support that claim. Revenue is not re-based to offset the higher market prices.

## 4. Tests — commands and results (all in fresh snapshots, never in the project tree)
| Run | Command (from the snapshot root) | Result |
|---|---|---|
| Orchestrator, frozen baseline | `python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider` | 310/310, 206 s |
| Orchestrator, final tree (×3, default) | same | 342/342 each (`FINAL7_default_run1..3`: 393 / 298 / 332 s; profit 9.02 / 9.11 / 9.03 M) |
| Orchestrator, final tree, legacy configuration (×3) | `LINER_DEMAND_LOOP_BUDGET=0 LINER_CLASS_SCREEN=0` + same | 342/342 each |
| Orchestrator, market-price scenario (×3, final tree) | `BUNKER_PRICING_MODE=regional_snapshot BUNKER_PRICE_SNAPSHOT=data/pricing/bunker_snapshot_2026-10-09_vlsfo.json` + same | **349/349 each** (`FINAL7_regional_run1..3`: 77 / 124 / 100 s; profit 4.54 / 3.94 / 4.26 M); the earlier run on the legacy pool (`T8B_orch2_regional`) was 337/339, not relaxed |
| Suite, artifact-free, baseline | `python -m pytest tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider --junitxml=...` | 52 failed / 979 passed / 43 skipped |
| Suite, artifact-free, final | same (`FINAL7_suite_artifact_free`) | **51 failed / 1,143 passed / 46 skipped** (0 newly failing; 1 fixed: `test_llm::test_cache`) |
| Suite, artifact-present, baseline | same | 53 failed / 1,001 passed / 20 skipped |
| Suite, artifact-present, final | same (`FINAL7_suite_artifact_present`) | **53 failed / 1,167 passed / 20 skipped** (0 newly failing; the same 53 baseline failures) |
| Comparison tool | `python evidence/tools/compare_suites.py M0=<xml> FINAL=<xml>` | 0 newly failing in both states; 168 new tests pass (`evidence/comparisons/suite_diff_M0_vs_FINAL7_*.md`); the two renamed F-15 tests appear as removed/added |

The orchestrator test was extended with three sections (N.7b pricing recomputed by its own resolver and snapshot-hash check;
O decision layer == ledger; P pool composition and class use): 310 → 342 assertions, **no assertion removed or relaxed**
(the diff removes four lines: a typing import, the scalar-price line it replaces, a print label, and the call that now
assigns its result). LLM rate limits (HTTP 429) were ignored as instructed — the deterministic fallback text is used, and the
count per run is in `evidence/comparisons/run_register.md`.

## 5. Defects found and fixed *during* the run (each with a test; none by weakening an assertion)
| # | Found by | Defect | Fix |
|---|---|---|---|
| 1 | orchestrator gate | with demand loops, the existing per-region assertion "services selected > 0" failed: shared loops were attributed to the first proposer, then to the majority cargo owner, leaving Europe without any service while showing +$4.0 M "profit" | regional service-cost split is now usage-based with a representation phase (totals unchanged; `tests/test_regional_ownership.py`) |
| 2 | F-04 governance test | the two new modules recomputed hire/fuel from raw fleet fields — a "second source" of economics | both now use the canonical `ServiceModel` only; results identical (profit and pool equal to the unit) |
| 3 | a new test | the same rotation proposed by several generator sections got different "legacy" classes, breaking the per-rotation cap | screening is a property of the rotation (cache per rotation) |
| 4 | repeat runs differing across processes | `HubDetector` cached demand scores by `id(problem)`; freed ids are reused, so one problem received another's scores — non-reproducible hubs/loops/feeders | weak-reference identity check (`tests/test_hub_detector_cache.py`) |
| 5 | design review of variant A | "least-loss class" for unprofitable rotations selected Feeder_450 and the regional margin rule then deleted the rotation (pool 1,270 → 398) | rule changed: no profitable class → keep the legacy class |
| 6 | ablation | exempting screened classes from the margin rule gave no gain (8.42 vs 8.76 M) | exemption removed |
| 7 | existing tests | `test_pool_size_changes_with_budget` and the F-15 tripwires encoded behaviour that changed deliberately | the first pinned to the legacy configuration it was written for; the second flipped as its own docstring required |
| 8 | final verification | `test_hub_detector_cache` asserted that CPython had reused a freed address (`reused >= 1`); it failed once inside the large focused test process although every value assertion held (the cache fix was not at fault) | the test now forces the stale entry when the address is not reused naturally, so the scenario is exercised on every iteration; it still fails on the baseline code (checked) |

## 6. What genuinely improved
* **The numbers the decision layer reports are now the ledger's numbers** (F-15): margin 26 % → 11 % on the same plan; iteration
  selection compares all-in cost; unverified accounting cannot be presented as verified.
* **Candidate quality**: stand-alone-profitable candidates 10.6 → 91 of ~1,200; 50 % of the demand-loop candidates are
  profitable stand-alone against ~1 % of the legacy sections'.
* **Plan quality (verified, feasible, profitable)**: mean $3.25 M → $8.75 M per week and coverage 8.5 % → 20.0 % at equal or
  better margin on 5 seeds; the end-to-end pipeline shows the same direction (§2a); run-to-run spread of the pool-driven result
  fell from ±$1.9 M to ±$0.5 M.
* **Reproducibility**: a latent cache defect that made candidate pools process-dependent is gone.
* **Pricing is an input, not a constant**: pinned, hashed, per-service, verified by an independent resolver.

## 7. What did not improve, or regressed — plainly
* **Coverage is still 20 %**: 80 % of demand is unserved. This is a better pool, not a solved network; the LP bound is $44 M/wk.
* **Resource use rose**: vessels 42 → 115 of 263; the global MILP now uses most of its 120 s limit and ends `feasible`
  (never `optimal`); on the Task 9 pool the exact optimum (8.2 M) exceeds what the production strategy extracts (6.4 M) — the
  restriction heuristic, not the pool, is now the binding limit.
* **More is not better**: 2 or 3 class alternatives per rotation, a larger demand-loop budget (120) and "every class" all
  reduce profit; screening on the *legacy* pool alone is neutral (+$0.2 M, 3/5 seeds).
* **Market prices cost a lot of profit, and regional structure is not what drives it**: on identical captured inputs the
  October-2026 snapshot takes the legacy pool to near break-even (exact optimum $0.85 M vs $2.0–4.2 M) and the final pool
  from $8.8 M to $3.05 M per week (exact optimum 2.7–3.5 M; end-to-end $4.25 M). That is the price level against
  benchmark-era revenues (a vintage mismatch, not a forecast); no revenue was re-based.
* Feeder_450 is deployed in no configuration.

## 8. Independently verified vs conditional
**Verified (independent recomputation from raw data in the test, ledger, MILP = ledger):** revenue, every cost line, profit,
margin, served TEU, vessels per class ≤ inventory, per-service fuel price from the pinned snapshot, transit-time limits, per-leg
capacity, demand conservation; tampered plans are rejected. **Conditional on stated assumptions:** `Capacity FFE` read as TEU
(provisional), 24 h port stay, 48 h + 3.5 d transfer dwell, `TransitTime` in days, sailing at design speed only, VLSFO grade,
the "cheapest observed port on the rotation" bunkering rule, the legacy 600 USD/t.
**Is the final run feasible, profitable and verified?** Yes on all three (status `complete`, ledger verified, 0 violations,
positive profit in every iteration). **Optimal?** No: MILP status `feasible`; only a bound ($44–50 M/wk) and, on one seed, an
exact optimum above the incumbent are known. Optimality is unproven.

## 9. Recommended next tasks (not implemented)
1. Global-stage strategy: accept the unrestricted integer solve when it closes, and prune rotations that are neither
   stand-alone profitable nor complementary (version A's 398-candidate pool is a lead, unconfirmed on more seeds).
2. A licensed, dated, multi-port bunker feed, then decide default pricing and re-base revenues.
3. Replace the regional margin guess in `_filter_services` by per-rotation economics (Feeder_450).
4. Task 11 (two-transfer paths) and Task 12 (route-level GA operators) as already scoped — each with its own comparison.

## 10. Deliverables
| Item | Path (under `reports/overnight_tasks_8_9_10/`) |
|---|---|
| Final report | `overnight_tasks_8_9_10_final_report.md` |
| F-15 | `task8_f15_accounting.md` |
| Pricing | `task8_regional_bunker_pricing.md` |
| Candidate generation | `task9_candidate_generation.md` |
| Class screening | `task10_vessel_class_screening.md` |
| Outstanding issues | `outstanding_issues.md` |
| Patch + checksum | `patches/overnight_tasks_8_9_10_final.patch`, `patches/patches.sha256` (checksum in `patches/patches.sha256`) |
| Approved-decision evidence | `evidence/comparisons/pool_equivalence_switches_off_vs_baseline.md` (both switches 0 = baseline pool), `evidence/comparisons/pricing_legacy_vs_market_captured_inputs.md` (legacy vs market on identical captured inputs, two pools), `evidence/comparisons/suite_diff_M0_vs_FINAL7_*.md`, `evidence/inputs/FINAL_global_inputs.pkl` (+ hashes) |
| Benchmark evidence | `evidence/` — `runs/` (logs, meta, JUnit, artifacts, MANIFEST), `outputs/` (replay and sweep JSON), `inputs/` (captured pools + hashes), `comparisons/` (tables, run register, suite diffs), `tools/` |

Reproduce the headline comparison: `python -I evidence/tools/pool_experiment.py <snapshot> <out.json> 120 0,1,2,3,4 old loops60 loops60+screen1`
(from a fresh snapshot of the tree; environment switches are set by the tool).

## 11. Approved decisions of 2026-10-11 — implementation and verification

The product owner approved five decisions after the first version of this report. Each is implemented, and each claim
below is backed by a recorded run (labels refer to `evidence/runs/` and `evidence/comparisons/run_register.md`).

### 11.1 Fuel pricing
* **600 USD/t is the default legacy benchmark** (`BUNKER_PRICING_MODE` unset → `legacy_uniform`, labelled `assumed`).
  It is not described anywhere as the October-2026 market median; the repository contains no historical series that
  could support that statement.
* **The market-price scenario is separate and explicitly selected**: `BUNKER_PRICING_MODE=regional_snapshot` with
  `BUNKER_PRICE_SNAPSHOT=data/pricing/bunker_snapshot_2026-10-09_vlsfo.json` (pinned id `shipandbunker_vlsfo_2026-10-09`,
  SHA-256 `a03086668958f79009491600a6294efb90351e6520d739420d9fb6097beb5835`, emitted in every run's
  `network_ledger.assumptions.fuel_pricing` and recomputed by the orchestrator test). **Revenue is not re-based.**
* **Each market price records** source, source URL, fuel grade (VLSFO), unit (USD per metric tonne), observation date
  (2026-10-09) and the bunkering-location assumption (field `bunkering_location`, part of the pinned hash; §3).

Same captured inputs, only the price changes (`evidence/comparisons/pricing_legacy_vs_market_captured_inputs.md`; the
final code reproduces the earlier replay of the legacy pool to the dollar, e.g. 4,212,367):

| captured pool | legacy 600 USD/t (production strategy) | market snapshot | exact optimum under the market snapshot |
|---|---:|---:|---|
| legacy pool (U4, before Tasks 9–10), 3 calls | 1.99 / 2.62 / 4.21 M | 0.12 / 0.41 / 0.15 M (coverage 1.6–1.9 %) | 0.85 M (call 1; proven) |
| **final default pool** (demand loops 60 + screening k 1), 3 calls | 8.52 / 9.06 / 8.87 M (mean 8.82 M) | **2.70 / 3.45 / 2.99 M (mean 3.05 M)**, coverage 10–13 % | 2.74 / 3.45 / 2.99 M (proven) |

End-to-end (unseeded, whole pipeline, final tree): market-price mode **349/349 ×3**, verified, 0 violations,
profit 4.54 / 3.94 / 4.26 M (mean 4.25 M; margin 11.9 %; coverage 11.5 %; 7–9 services) versus the default mode's
9.06 M (342/342 ×3). **Reported as found:** the market-price scenario is profitable on the final pool but at roughly
one third (replay) to one half (end-to-end) of the legacy-price profit, and on the legacy pool it was near break-even.
A 20 % higher price level takes the final pool to 0.9 M. No price, revenue or constraint was adjusted.

### 11.2 Generator defaults and rollback
* Demand loops (budget 60) and class screening (k = 1) are **on by default**, subject to the same gates (342/342 ×3,
  0 violations, 0 newly failing tests). No coverage or profit improvement is forced anywhere.
* **Both options at 0 restore the prior candidate pool exactly** — frozen baseline tree versus final tree with
  `LINER_DEMAND_LOOP_BUDGET=0 LINER_CLASS_SCREEN=0`, one interpreter per seed, `PYTHONHASHSEED=0`, seeds 1–3, every
  region: 508 / 405 / 499 candidates (Asia / Europe / Americas), identical element by element and in order
  (`evidence/comparisons/pool_equivalence_switches_off_vs_baseline.md`; tool `evidence/tools/pool_dump.py` +
  `pool_compare.py`; dumps in `evidence/outputs/pooldump/`). With the defaults the same seeds give 563 / 440 / 548 (seed 1; 562–563 / 433–441 / 543–548 over seeds 1–3).
  Scope of the claim: the pool leaving the generator and the regional filter; the downstream stages are unchanged and
  the end-to-end legacy-configuration runs (`LEGACY6_run1..3`, 342/342) are in the register.
* **Rollback configuration** (reproduces the baseline candidate pool and pricing): `LINER_DEMAND_LOOP_BUDGET=0`,
  `LINER_CLASS_SCREEN=0`, `BUNKER_PRICING_MODE` unset. The F-15 accounting change is independent of these switches.

### 11.3 Usage-based regional cost allocation
* A service's vessel, fuel and fixed port-call cost is charged to **exactly one** region: the region whose cargo rides
  it (representation phase first, then the largest user; a service carrying no attributable cargo falls back to its first
  proposer). Cargo revenue, per-TEU port and transshipment costs follow the cargo's origin region.
* **Reconciliation, line by line** — `tests/test_regional_ownership.py::test_regional_split_reconciles_component_by_
  component_and_counts_no_service_twice` (3 regions, shared services): Σ regional revenue, vessel, fuel, transshipment,
  port, total cost and profit equal the network ledger within 1e-9 relative / 1e-6 absolute; every operated service is
  listed by exactly one region and its costs equal the ledger row's, so no shared cost is counted twice.
* **In the pipeline** — orchestrator §N.6 (Σ regional revenue / cost / profit == network within 1e-6 relative or 5 USD)
  passed in all six final-tree runs (342/342 ×3, 349/349 ×3). The split remains an accounting convention: network totals
  are unaffected by it.

### 11.4 Release gates (after the last code change, final tree)
| Gate | Result |
|---|---|
| Focused tests (pricing, economics, decision layer, demand loops, class screening, ownership, hub cache, iteration selection, metric documentation) | `PR_focus2_fin`: 236 passed, 14 skipped, 29 failed — the 29 are `test_economic_metric_documentation` cases that need the `MULTI_AGENT_*.json` audit artifacts, **absent in the frozen baseline too (identical set)** |
| `tests/test_orchestrator.py`, default configuration ×3 | 342/342 each; ledger `verified`, 0 violations |
| `tests/test_orchestrator.py`, market-price scenario ×3 | 349/349 each; ledger `verified`, 0 violations; per-service prices recomputed by the test's own resolver; snapshot hash matches |
| Independent ledger validation | the test recomputes revenue, every cost line, fleet, capacity, transit time and cargo from raw data and compares with `global_metrics`/ledger (sections N, O); tampered plans are rejected; every replayed scenario reports MILP = ledger |
| Legacy versus market on equivalent captured inputs | §11.1; two captured pools, identical solver settings |
| Broad suite, both artifact states | 0 newly failing (51 / 53 failures are the baseline's own) |
| Constraints | profitability reported on the ledger, per-class fleet inventory, per-leg capacity, transit-time-feasible paths, demand conservation and cargo accounting are enforced by the unchanged planner and re-checked by the independent ledger; none was relaxed |

### 11.5 Scope
Tasks 11 (two-transfer paths) and 12 (route-level GA operators) are **not** implemented; they appear only as
recommendations in §9.

### 11.6 Still open
The 15 % margin target of the advisory coordinator verdict (an existing band, unchanged) and the recertification
sign-off of the Tier-0 components touched remain with the product owner (`outstanding_issues.md`).

Reproduce the approved-decision evidence (fresh snapshots): `python -I evidence/tools/pool_dump.py <tree> <out.json> <seed>` once per tree and seed (final tree with and without `LINER_DEMAND_LOOP_BUDGET=0 LINER_CLASS_SCREEN=0`), then `python -I evidence/tools/pool_compare.py <dump_dir> <out.md> 1 2 3`; `python -I evidence/tools/replay_pricing.py <tree> evidence/inputs/FINAL_global_inputs.pkl <call> <out.json> 120` and `python -I evidence/tools/summarize_pricing_replay.py <out.md> <title>=<prefix>`.
