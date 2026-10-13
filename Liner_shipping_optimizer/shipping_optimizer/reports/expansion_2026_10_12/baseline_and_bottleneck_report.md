# Profitable network expansion — baseline, bottleneck diagnosis and experiment plan

**Date:** 2026-10-12 · **Phase:** read-only audit (Part 12 of the master prompt) · **Scope:** WorldSmall only (no WorldLarge file read)
**Status:** no production source file, default, or data file was changed. Everything below was produced by running the
unmodified pipeline from snapshot copies on `D:\liner_scratch`, plus new analysis scripts in this directory.
Evidence index: `evidence/` (`runs/` logs + meta, `outputs/` JSON/CSV, `tools/` scripts). Nothing in `reports/tasks_19_20_21/` was touched.

## 1. Verified repository state

| Item | Result |
|---|---|
| Git root | `C:\Users\WINDOWS\Liner-Worldsmall` (project dir `…\Liner_shipping_optimizer\shipping_optimizer`) |
| Branch / HEAD | `main` / `74bf770` — `Revert "Add liner shipping optimizer worldsmall"` |
| Working tree | the whole project is **untracked** (`?? ../`) and `Liner_shipping_optimizer.zip` is untracked: git carries **no** provenance for this tree. Provenance = the SHA-256 snapshot manifests on `D:\liner_scratch` |
| Live tree vs accepted Tasks 19–21 final tree | **1511 / 1511 files byte-identical** (`snap_T19O_default_run1.manifest.json`, manifest sha `34a8d390…f24c`); re-checked after all runs of this audit: 0 differences |
| Disk | **C: has 1.1 GB free** (D: 206 GB). All snapshots/runs go to D:. Risk for any test that writes to C: |
| Toolchain | Python 3.11.9 · PuLP 2.7.0 + CBC 2.10.3 (single thread) · scipy 1.12.0 · numpy 1.26.3 · pandas 3.0.5 · pytest 7.4.4 · `highspy` **not installed** (HiGHS only via `scipy.optimize.milp`) · CPU i7-1360P, 16 logical cores |
| WorldSmall input hashes (SHA-256) | `Demand_WorldSmall_Fixed_Sep.csv` = `demand_world_small.csv` `fd46294e5b71bcc6f7e49e6803a971a884be2b520c9a3bbd3bfe8f56b4703016` · `dist_dense.csv` `8edf8cdf7a119c341b1bd3bab60a11529dec992335926a49914894c0b0080555` · `fleet_data.csv` `5054eb5178cedbe28e33a3c6dde05e6d226025918f80250b7c148b8d846f458c` · `fleet_WorldSmall.csv` = `fleet_world_small.csv` `a8986ee2bfeda133fdc069292319bfa5f038d329359f519ec22872133a68e216` · `ports.csv` `b6c8c3b6c209222a33c68e1fe074092530082581ed4c5d5e4e6f9937677696ea` |
| Gap in earlier evidence | `reports/tasks_19_20_21/experiment_manifest.json` has `"inputs": {}` — **input hashes were never recorded there**; recorded here for the first time |

## 2. Accepted configuration as it actually is in the code

| Setting | Value (source) |
|---|---|
| Solver / budget | CBC, `GLOBAL_STAGE_TIME_LIMIT_SEC` default 120 (`orchestrator_agent.py:355`), `NETWORK_MILP_BACKEND` default `cbc` |
| LP-guided restriction | on; integer problem restricted to services with LP `f > 1e-6` |
| Paths | `PathConfig` defaults: fastest-first, fixed cap **10 per OD**, `max_transfers=2` (multi-hop only where < 1 direct/1-transfer path), `reoptimize_flows=True`, `repair_profit_floor=True` (`paths.py:80-102`) |
| Pool | demand-coherent loops budget 60, class screening k=1 with time-feasible correction, economic regional filter (caps 508/405/499) |
| Differences from the reported baseline | **none in code.** One reporting difference: the reported 9.18 → 11.52 M figures are 10-seed controlled means; the end-to-end default runs were 12.17–13.88 M |

## 3. Baseline reproduction

| Reference | Reproduced here | Verdict |
|---|---|---|
| Controlled seed 0, default config (M7 `D`): 13,196,699 USD/wk, 26.6 %, 30 svc | diagnosis run (2 concurrent jobs): **13,196,699, 26.61 %, 30 svc — identical to the dollar** (`T22_oddiag_seed0_prod.json`); same pool hash `2b873e635d`, 7,122 vars, 2,901 rows, bound 41,272,763.02 | reproduced |
| Same model, heavier load (3 CBC + a test pipeline) | **3,352,138** (raw incumbent ≈ −9.0 M, profit-floor repair triggered) — same pool/model hashes and bound as above (`T22_probe_seed0_*`) | **CBC timing sensitivity, not a model change** |
| Same model, 1 job | 13,450,597, 25.18 %, 26 svc (`T22_oddiag3_seed0_prod.json`) | a third distinct incumbent for identical inputs |
| Orchestrator, accepted default (`T19O_default` 12.17 / 12.59 / 13.88 M, 362/362) | `E0_baseline_orch_run1`: **12.82 M**, margin 15.4 %, coverage **26.16 %**, 32 services, 153 vessels, **362/362 passed**, 417 s, ledger verified, 0 violations, status `complete`, iteration 1 selected (iterations: 3.12 / 12.82 / 9.60 M) | reproduced (n = 1; coverage 0.7 pp above the previous range) |
| Snapshot used | manifest sha `34a8d390…f24c` = accepted final tree | identical |
| 10-seed paired means 9.18 → 11.52 M, 21.2 → 25.3 % | **not re-run** (needs ≈ 20 controlled runs, est. 25–30 min at concurrency 2) | historical; first step of the plan |
| Whole suite (orchestrator test excluded; snapshot `T22_suite_baseline`, 107 s) | **51 failed / 1,257 passed / 46 skipped**; the 51 failing test ids are **identical** to the recorded artifact-free baseline (`T19S_final_free`): pre-existing, none introduced here | reproduced |

Spread of the raw (pre-re-optimisation) CBC incumbent across the 12 default-configuration orchestrator iterations on record
(4 runs × 3): −7.45 … +10.14 M (nine of them 9.1 … 10.1 M). The orchestrator reports the best of 3, which hides this variance.

## 4. Baseline gate values (E0 run)

Revenue 83.07 M, all-in cost 70.25 M, profit **12.82 M/wk**, margin 15.4 %; demand 276,446.8 TEU/wk, served 72,332 (26.16 %);
32 services, 153 of 263 vessels (Feeder_450 0/24, Feeder_800 **29/29**, Panamax_1200 49/68, Panamax_2400 31/74,
Post_panamax 34/58, Super_panamax **10/10**); network load factor 0.646 (nm-weighted 0.677); 243 flows (102 direct, 73 feeder,
34 hub-and-spoke, 34 multi-hop); transit: direct mean 20.4 d / p90 29.1, feeder 30.1 / 37.8, hub 23.0 / 31.5, multi-hop 35.9 / 45.3,
minimum slack 0.02 d, 0 violations; solver `feasible`, dual bound 40.37 M (weak relaxation, see §6), flow re-optimisation +3.62 M,
repair not triggered; regional partition reconciled.

## 5. Unserved-demand diagnosis

### 5.1 What the production label means
`strategy_report._unserved_reason` assigns the **first applicable** cause per OD. `not_economic_to_open_service` is a **residual**:
"some path could be opened with the free fleet and the optimiser did not open it". It is **not** an economic test. It therefore mixes
(7) genuinely unjustified services, (4) paths lost to the cap, and (8) the quality of a time-limited incumbent. The reported
"49–59 % economics" is not evidence of economics.

The label shares are also a property of the incumbent, not of the demand: across the recorded default-configuration runs and the
probes of this audit (seed-0/1 pools, orchestrator runs), the production labels range 22 – 61 % (not economic) and 7 – 39 %
(fleet inventory exhausted) of total demand.

### 5.2 New per-OD diagnosis (seed 0, full valid path set of 69,271 paths, exact flow LP, add-one marginal values)
Tool: `evidence/tools/od_offline_t22.py` (evaluator validated: LP over all valid paths of the operated services reproduces the plan's profit **to the dollar** on both plans).
Shares are % of total demand (276,447 TEU/wk).

| Category (primary-cause order) | Production incumbent 13.45 M | Strengthened-model incumbent 15.01 M |
|---|---:|---:|
| C2 transit limit below sailing time (not servable) | 3.37 % | 3.37 % |
| C3 no compatible candidate in pool | 2.53 % | 2.53 % |
| C4 valid path exists only outside the capped model | 0.06 % | 2.21 % |
| C5 fleet inventory / class blocks opening (alt-class variant time-feasible with free vessels: all of it) | 1.69 % | 16.33 % |
| C6 leg capacity of operated services | 5.22 % | 5.40 % |
| C7 not justified at the incumbent, single new-service view (+ per-TEU margin ≤ 0) | 47.4 % | 30.6 % |
| C8a opening ONE service raises profit at the incumbent (optimiser / restriction / cap) | 8.92 % | 5.99 % |
| C8b needs ≥ 2 new services (not evaluated singly) | 5.65 % | 5.67 % |
| served | 25.2 % | 27.9 % |

C7 is conditional on the incumbent and on a single-service view; a multi-service combination can still justify a service.

### 5.3 Marginal value of opening services at the incumbent (exact LP, f = 1 / 2)
| | production incumbent | strengthened incumbent |
|---|---:|---:|
| unopened services with positive add-one profit (all valid paths) | **46** | 20 |
| … when only the paths the capped model held are available | **10** | 1 |
| sum of best positive per-service deltas (not additive) | +6.66 M | +3.32 M |
| greedy add/drop/±f local search (4 moves) | 13.45 → **14.74 M**, served 69.6 → 81.7 k TEU | 15.01 → **16.11 M**, served 77.2 → 87.9 k TEU |
| profitable drop-one moves | 1 (+25 k) | 0 |
| alt-class variants of inventory-blocked rotations with positive add-one value (of 80 tried) | 5 (best +0.35 M) | 9 (best +0.44 M) |

Reading: the path cap hides about 36 of 46 profitable openings from the MILP (Part 3.2 condition 2); the incumbent leaves
+1.1 … +1.3 M that four exact LP-evaluated moves recover; inventory-blocked demand has time-feasible class variants that the pool does
not contain (the pool is 83 % Feeder_800 — 1,288 of 1,551 regional candidates — against 29 Feeder_800 vessels; Panamax_2400 has 58–59
idle vessels, Feeder_450 24).

## 6. Solver and formulation findings

| Finding | Evidence |
|---|---|
| The LP relaxation is very weak: bound **41.3 M** vs incumbents 13–15 M (gap 70–92 %). Services run at a fraction of a weekly sailing (seed 0: 326 of 327 support services have LP frequency < 1) | `network_milp.py` has no inequality linking cargo to an integer sailing (`q ≤ cap·f` only; capacity ≫ OD demand) |
| Valid inequality `q[od,p] ≤ demand[od]·f[s]` for every path/service (cuts no integer point; in-process probe, production untouched) | bound **41.27 → 16.32 M** (seed 0), 41.86 → 16.57 M (seed 1); LP support 283–303 → 109–118 services; restricted MILP 7.1 k → 3.3 k variables; ledger 0 violations, reconciled |
| Same model, same CBC 120 s, with the inequality | seed 0: **14.99 / 15.01 / 15.01 M** in three runs under different loads (prod arm: 3.35 / 13.20 / 13.45 M); seed 1: 14.47 M vs 11.57 M recorded (M7 `D`) |
| Reference | HiGHS 600 s default config: 14.66 / 15.44 M (seeds 0/1, M11) |
| Previous restriction variants (A_sa, A_pert, A_top, progressive) were all ≤ production under CBC | `tasks_14_15_16/task15_milp_strategy_comparison.md` |
| Path cap | 12.3–12.5 k of 53–69 k valid paths kept; 1,004 of 1,764 ODs at cap; delta between "held" and "all" paths in §5.3 |

**Caveat (n = 1–2 seeds, one pair at unequal load):** these are diagnostics, not acceptance evidence. The comparison against the
clean recorded batch (M7) is +1.8 M (seed 0) and +2.9 M (seed 1).

## 7. Ranked opportunities

| # | Experiment | Targeted bottleneck | One variable | Evidence so far |
|---|---|---|---|---|
| 1 | **C1 — strengthen the network MILP with `q ≤ demand·f` (flag `LINER_MILP_VUB`, default off)** | weak LP relaxation → poor restriction and CBC incumbent lottery | model rows only | +1.8 / +2.9 M on 2 seeds, bound ÷2.5, stable across loads |
| 2 | **C2 — exact-LP local search after the MILP (add f=1 / drop / ±f), inside the same 120 s stage budget** | cap-hidden openings, incumbent gap | post-MILP step | +1.1 … +1.3 M on 2 plans in < 30 s of LP |
| 3 | **A — targeted class-variant candidates for inventory-blocked rotations (E1–E3 ladder)**, after C1 | candidate gap: 16 % of demand blocked with a time-feasible variant | pool contents | 5–9 of 80 variants individually positive; blanket offering was −2.6 M under the weak model (Task 10) |
| 4 | B — diagnostic-driven path inclusion (paths of the top add-one services) | path cap | path pool | largely overlaps C2; test after C2 |
| 5 | D — best validated combination | complementarity | — | after A–C |
| 6 | E — HiGHS research (separate, not for production) | solver | backend | owner decision remains |

## 8. Proposed implementation sequence, tests, runtime, rollback

| Phase | Work | Est. runtime | Gate |
|---|---|---|---|
| 0 | (done) audit, probes, diagnostics | — | — |
| 1 | frozen paired baseline: default config, seeds 0–9, CBC 120 s, **arms run concurrently so load is equal** (≤ 2 jobs) | ≈ 15 min | recorded, ledger-clean |
| 2 | C1: implement behind `LINER_MILP_VUB`; unit tests (integer optimum unchanged on small instances; LP bound never above the baseline's; skipped when frequencies are fixed); paired 10 seeds vs Phase 1; 3 × `test_orchestrator.py` | ≈ 15 min + 3 × 7 min | Gates A–G |
| 3 | A: class-variant generator behind a flag, ladder E0–E3 on the C1 model; adversarial tests (no useful path, loss-making complement, inventory-blocked, time-limited result) | ≈ 4 × 15 min | Gates A–G |
| 4 | C2: local search behind a flag; tests incl. interaction with flow re-optimisation / profit-floor repair; budget split inside 120 s | ≈ 15 min + orchestrator | Gates A–G |
| 5 | B and D | ≈ 30 min | Gates A–G |

Rollback: every change behind one environment variable (default off until the owner approves); patch files with SHA-256 next to the
existing `patches/` convention; the accepted tree is preserved as `D:\liner_scratch\snap_T19O_default_run1` (manifest `34a8d390…`);
live-tree equality is re-checked with the manifest after each phase. No file is deleted by any command.

## 9. Missing data / assumptions that limit decisions

* `TransitTime` read as days (unverified): 41 ODs, 3.37 % of demand, below the pure sailing time at the fastest class (Task 18).
* `Capacity FFE` read as TEU (provisional); port stay 24 h, transshipment 48 h + 3.5 d wait are assumptions.
* Feeder_450 (24 vessels) is never operated in any recorded run — economics or a data/screening effect is not established.
* Integer weekly frequency (no fortnightly option) is a modelling choice; whether the source allows other granularities is an input question.
* Bunker-price provenance/licensing (Task 18); full-pipeline RNG control (Task 17); Tier-0 consumers and the 20 % vs 25 % verdict band are separate owner items.
* Model-equivalence of the proposed inequality is argued above and must be proven by the Phase 2 unit tests before any acceptance.

## 10. Confirmation

No production source file, default, environment setting or data file was modified. Files created: this directory only
(`reports/expansion_2026_10_12/`) and snapshot/pycache directories under `D:\liner_scratch\` (`snap_E0_baseline_orch_run1`,
`snap_T22_*`). The orchestrator test wrote `SYSTEM_TRUTH_REPORT.md` only inside its snapshot, not in the live tree.
