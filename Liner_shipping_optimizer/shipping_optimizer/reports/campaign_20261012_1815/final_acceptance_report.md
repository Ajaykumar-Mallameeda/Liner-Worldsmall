# Final acceptance report — campaign 2026-10-12 (baseline reproduction, MILP strengthening, local search, targeted expansion, data validation, reproducibility, test remediation)

**Scope:** WorldSmall only (no WorldLarge file read) · **Solver / budget:** CBC 2.10.3, single thread, 120 s global stage, unchanged ·
**Production defaults:** unchanged — every new behaviour is behind a default-OFF environment variable; nothing here promotes a flag.
**Status of the project:** *not* complete: 29 documentation tests are blocked, 9 regional tests await an owner decision, and seven maritime
assumptions are unverified or provisional (`maritime_assumption_validation.md`, register A3, A5, A7, A10 – A12, A14).  Everything below is evidence-backed; where evidence is thin it says so.

## 0. The eleven-point decision report

| # | Question | Answer (evidence) |
|---|---|---|
| 1 | Was the accepted baseline reproduced? | **Yes.**  The flags-off tree equals the recorded Tasks 19–21 default arm **to the dollar on 10 of 10 seeds** (batch D5, `phase5` §1) and on 5/5 duplicate runs (R1); the unmodified tree reproduced it on 5/10 seeds in a lighter load pattern, the rest within +1.9 / −0.1 M (CBC's wall-clock incumbent; `phase1`).  Orchestrator default: 13.12 M mean (12.29 – 13.71), 362/362 × 3.  Suite: 51 failed, identical test ids to the historical baseline |
| 2 | Did C1 improve LP strength, profit, coverage, solver stability? | **LP strength: yes** (relaxation bound 41.3 → 16.3 M, ÷ 2.5; integer problem 7.1 k → 3.3 k variables).  **Profit: yes** — +1.85 M (9/10, Phase 2), +1.93 M (9/10, Phase 3), orchestrator +1.07 M × 3.  **Coverage: not claimed** (−0.6 pp in the controlled batch).  **Stability: yes in a measured sense** — with doubled capacity the default found *no* plan on one of three seeds in 120 s, C1 + LS did.  **But** on top of the local search C1 adds only +0.39 M (hold-out 7/10): the two are substitutes on the unexpanded pool; C1 is essential on the expanded pool (−1.39 M without it) |
| 3 | Did local search add value inside the fixed 120 s? | **Yes — the strongest single change:** +2.28 M pooled over 20 seeds, **20/20 seeds higher**, coverage +2.9 pp; hold-out +1.91 / +2.01 / +1.92 M (10/10 each).  The stage is *shorter* (113.7 s mean against 120.7 s).  Orchestrator 14.96 vs 13.12 M × 3 |
| 4 | Which expansions improved the *operated* network? | **class variants in the pool** (ladder, two settings moving together: 5 %/floor 0 = the final candidate +1.12 M 9/10; 10 %/floor −0.5 M +1.39 M 9/10, dev only; 20 %/floor −1 M +0.64 M 7/10): operated at load factor 0.82 – 0.91, mostly Panamax_1200 and Feeder_450.  **Rejected:** restriction-aware path inclusion (no plan on 60 – 80 % of seeds), multi-hop search evaluator (−0.24 M).  **Experimental:** search-only variants (+0.18 M, 15/20) |
| 5 | Did combining the validated changes improve further? | **Against the default: decisively** — +3.25 M, **20/20 seeds**, coverage +4.1 pp, margin +1.6 pp; hold-out 10/10 in three batches; orchestrator 16.16 vs 13.12 M × 3.  **Against the search alone: modestly and not uniformly** — +0.97 M pooled, 14/20 seeds (hold-out replicates 8/10, 7/10, 8/10): *inconclusive* by the 8/10 rule |
| 6 | Maritime assumptions verified / unresolved? | **Verified:** `TransitTime` unit (days; reproduces the upstream revision rule on 105/105 ODs), port 24 h and transshipment 48 h (secondary source), 600 USD/t as the benchmark's value, Feeder_450's economics.  **Contradicted:** use of the unrevised transit file (13.0 % of demand affected).  **Unverified / provisional:** `Capacity FFE` unit (levels move ×1.6 – 2.5), transfer dwell 3.5 d, fuel grade / fuel systems, integer weekly frequency, per-FFE cost units.  **The ranking of default vs final is invariant in all 8 scenarios run** (23/23 pairs).  Absolute profit levels are conditional on the provisional assumptions |
| 7 | Did full-pipeline reproducibility improve? | **Yes, with limits stated.**  `LINER_SEED` (opt-in) makes candidate generation, regional filtering and the GA path identical run to run (18/18 seeded iteration-slots); under equal load the controlled stage is bit-reproducible (10/10 pairs).  The global plan still depends on CBC's wall-clock incumbent (2 of 18 seeded slots differed in the first R2 pair).  A defect found by the comparison (all iterations of a seeded run were identical) was fixed, and the final-tree pair confirms it: candidate counts / GA identical in 18 of 18 seeded slots, global plan identical in 17 of 18, the three iterations of a seeded run differ again |
| 8 | The 51 baseline test failures? | **13 fixed** (1 config, 5 coordination, 3 generator tags, 3 command-center, 1 port pipeline); **9 re-specified under the accepted architecture and held as strict xfail pending owner retirement** (replacement coverage added); **29 unresolved — BLOCKED** (documentation-drift suite; generator output regenerated in scratch: 52/58 pass, 6 fail on genuine drift / a missing authored document).  0 tests deleted, 0 assertions weakened; one *passing* test was updated as its own docstring instructs (§4).  Final tree: **29 failed / 1,341 passed / 46 skipped / 9 xfailed**, 0 failing ids outside the baseline set (1,257 + 13 fixed + 71 new = 1,341) |
| 9 | Do the final plans pass the ledger, feasibility and quality gates? | **Yes, in every solved plan** of every controlled batch (gate scan of every controlled output: 518 plan files, 495 solved; ledger valid 495/495, zero violations 495/495, reconciled 495/495, regional partition 494/495 - the one exception is the plan that exposed the defect fixed in `phase5` section 3 -, negative-profit plans 0; the 23 unsolved are the 22 path-inclusion arms and the default on the doubled-capacity scenario); the MILP objective equals the ledger profit to < 1e-6 relative; 0 transit violations, ≤ 2 transfers, vessels within class inventory |
| 10 | Ready for owner approval vs experimental? | **Ready for approval (opt-in flags):** local search (`LINER_LOCAL_SEARCH`); the expanded profile C1 + LS + 10 % variants; C1; seeding (`LINER_SEED`).  **Inconclusive:** the class variants' increment.  **Experimental only:** search-only variants, 5 % / 20 % variants.  **Rejected:** path inclusion, multi-hop evaluator.  **Blocked:** documentation suite, regional-test retirement, seven assumptions awaiting data or an owner decision |

## 1. Classification of every change (exactly one of five)

| change | flag / file | classification | basis |
|---|---|---|---|
| local search with idle-service prune | `LINER_LOCAL_SEARCH` (+ `_SEC`, `_MOVES`) | **ACCEPT FOR OWNER APPROVAL** | 20/20 vs default on dev + hold-out ×3 batches; stage within budget; 0 violations |
| C1 variable-upper-bound inequality | `LINER_MILP_VUB` | **ACCEPT FOR OWNER APPROVAL** | +1.9 M 9/10 vs default (twice); needed with the expanded pool; substitute for the search otherwise |
| expanded profile = C1 + LS + 10 % class variants | the three flags above + `LINER_CLASS_VARIANTS=0.10` | **ACCEPT FOR OWNER APPROVAL** (as a separate opt-in profile) | +3.25 M, 20/20 vs default; hold-out 10/10 ×3; orchestrator ×3 |
| class variants (floor 0; 5 % and 10 % give the same pool) as an increment | `LINER_CLASS_VARIANTS` | **INCONCLUSIVE** | dev +1.12 M 9/10, hold-out +0.56 M 7/10 over C1 + LS |
| class variants with a negative stand-alone floor (10 % / −0.5 M; 20 % / −1 M) | `LINER_CLASS_VARIANTS_FLOOR` | **EXPERIMENTAL ONLY** | dev +1.39 M 9/10 / +0.64 M 7/10; the best development mean and the largest plans (44 services, 36.2 % coverage) but never run on the hold-out |
| search-only variants (+ `_FLOOR`) | `LINER_LOCAL_SEARCH_VARIANTS` | **EXPERIMENTAL ONLY** | +0.18 M, 15/20; the arm that exposed the accounting defect |
| multi-hop local-search evaluator | `LINER_LOCAL_SEARCH_MULTIHOP` | **REJECT** | −0.24 M, coverage worse 9/10 |
| restriction-aware path inclusion | `LINER_PATH_INCLUDE` | **REJECT** | no plan on 60 – 80 % of seeds |
| central seeding | `LINER_SEED`, `src/utils/rng.py` | **ACCEPT FOR OWNER APPROVAL** | pool / GA reproducible under a seed; does not claim solver determinism |
| regional ownership of search-only variants; owner fallback | `reconcile.py` | **ACCEPT** (defect fix; inert unless the variants are on) | regional totals equal the ledger by construction |
| test-side fixes (13 tests) | `tests/…` | **ACCEPT FOR OWNER APPROVAL** | §4 |
| 9 regional tests held as strict xfail | `tests/test_regional_agent_activation.py` | **BLOCKED** (owner decision) | retirement needs confirmation |
| 29 documentation-drift tests | `tests/test_economic_metric_documentation.py` | **BLOCKED** | re-audit needed |
| assumptions A3, A5, A7, A10 – A12, A14 | `maritime_assumption_validation.md` | **BLOCKED** (evidence / owner input needed) | register |

## 2. Gates (the stated A – G, mapped to prompt §9)

| gate | requirement | result |
|---|---|---|
| **A economic correctness** (9.1) | ledger profit = reported profit; revenue and every cost once; no invented input | **PASS**: reconciliation < 1e-6 relative in every solved plan; no input substituted; operating profit non-negative in all |
| **B profit** (9.1) | mean paired profit > 0 vs the frozen comparator and ≥ 8/10 seeds positive | **PASS** for LS, C1 and the combination vs the default; **not met** for the increments C1-over-LS and variants-over-(C1 + LS) on the hold-out (7/10) — reported as inconclusive, not hidden |
| **C coverage** (9.2) | no coverage gain with a material profit loss; no service-count target | **PASS**: coverage rises with profit in 17 – 18 of 20 seeds; none lost (paired profit never negative against the default) |
| **D physical feasibility** (9.3) | zero fleet / class / capacity / conservation / frequency / transit / transfer / ledger violations; regional reconciliation | **PASS**: 0 in every solved plan; regional partition verified 100 % of the final-code plans (one earlier defect found and fixed: `phase5` §3) |
| **E quality** (9.3) | transit mean / p90 / slack / multi-hop reported; transfer rules preserved | **PASS**: maximum p90 transit by strategy 40.0 – 48.5 d across the arms (default 46.4 d), minimum slack 0.0006 d (the existing rule), ≤ 2 transfers |
| **F tests** (9.5) | relevant unit, equivalence, bound, interaction, feasibility, ledger, reconciliation, orchestrator, full suite | **PASS with stated residue**: 71 new tests (17 C1, 25 local search / variants / prune / ownership, 11 expansion flags, 13 seeding, 5 regional architecture) plus the orchestrator test's N.11 section; orchestrator 364/364 x 3 (default) and 368/368 x 3 (final candidate) on the final tree; suite 29 failed (all documentation-drift, all in the baseline set) / 1,341 passed |
| **G repeatability** (9.4 / Phase 7) | reproducibility quantified, not claimed | **PASS**: R1 10/10 identical pairs under equal load; R2 pool/GA identical under seed; plan-level residue measured |
| solver reporting (9.4) | backend, budget, incumbent, bound, gap, status, runtime, validation, post-MILP change | in every output JSON and in `evidence/comparisons/per_seed_acceptance.csv` (one row per plan: 160 plans of D5 / H5 / C9 / C9b) |

## 3. Findings by kind

**Verified (measured in this campaign, reproduced)**
* default reproduces the recorded baseline (10/10 to the dollar); local search +2.28 M (20/20); the combination +3.25 M (20/20).
* C1's relaxation bound ÷ 2.5, model size ÷ 2; C1 needed once the pool is expanded (−1.39 M without it).
* The class variants that are operated are well loaded (0.82 – 0.91) and mostly Panamax_1200 / Feeder_450; Feeder_450's economics explain its absence from baseline plans.
* `TransitTime` is in days (upstream rule reproduced on 105/105 ODs); 13.0 % of demand has a looser upstream limit.
* Fixed defects: idle service after search + re-routing; regional ownership of search-only variants; candidate-generator stream shared by regions and iterations; flaky weather test.

**Reported historical findings (not re-derived here)**
* Tasks 19 – 21 acceptance figures (9.18 → 11.52 M, 21.2 → 25.3 %); the bunker snapshot provenance (Tasks 8 – 10); Tasks 14 – 16 HiGHS-300 s recommendation.

**New experimental findings**
* LS and C1 are substitutes on the unexpanded pool; complements only through the expanded pool.
* Search-only variants help only with a negative stand-alone floor and only a little; MILP-visible variants beat them.
* Multi-hop evaluation costs the search more in set-up (10.4 s) than it returns.
* Seeding collapsed iteration diversity until the stream label included the call index.

**Inferences (stated as such)**
* Coverage gain with the variants is consistent with relief of class-inventory blocking (C5): not tested separately.
* The 7-of-10 / 8-of-10 results of the increments are consistent with a CBC-incumbent lottery (two same-config replicates differed by up to 2.6 M); the spread, not a defect, limits the rule.

**Unverified assumptions:** A3 (`Capacity FFE`), A5 (3.5 d), A7 (fuel systems), A10 (weekly frequency), A11 – A12, A14 — see the register.

**Unresolved blockers:** documentation suite (29), regional-test retirement (9), `LINER_*` flags not yet defaults by design.

**Owner decisions still required**
1. Which profile to approve: local search only (lowest risk) or the expanded profile (+0.97 M on average, three flags, larger pool).
2. Whether to adopt the revised transit file (13 % of demand; no measurable effect at n = 3).
3. The unit of `Capacity FFE` and the transfer-dwell convention (levels move ×1.6 – 2.5 and ±2 – 3 M).
4. Retire or restore the 9 regional-policy tests; authorise (or retire) the documentation-drift suite.
5. Whether `LINER_SEED` becomes the experiment default (it does not make CBC deterministic).
6. The pre-existing owner items of Tasks 19 – 21 (verdict band 20 vs 25 %, HiGHS 300 s, Tier-0 sign-off) are untouched.

## 4. Tests — before / after (`test_failure_remediation_report.md`)

51 failed / 1,257 passed / 46 skipped (frozen baseline, artifact-free) → **29 failed / 1,341 passed / 46 skipped / 9 xfailed** (final tree).  Fixed 13; strict-xfail 9; blocked 29; deleted 0.
A passing test was updated as its own docstring instructs: `test_no_random_seeding_in_production_code` now exempts exactly
`src/utils/rng.py` (the opt-in module).  The weather test `test_full_cycle` was a pre-existing race (1 of 12 runs on the frozen tree) and is
deterministic now (0 failures in 15 whole-file runs).

## 5. Artifacts, checksums, rollback

* Reports: this directory (`INDEX.md` links every conclusion to its artifact with SHA-256).
* Patch against the accepted tree: `patches/final_vs_accepted.patch` (20 files modified, 8 added; SHA-256 `0dd4256a…e406`, all in `patches/patches.sha256`);
  verified to reproduce the final tree's source and tests exactly from `snap_C0_base` (0 content differences; 26 files differ in line endings only).
* Rollback: `patches/ROLLBACK.md` (behavioural: leave the flags unset; file: reverse-apply the patch or restore from the snapshot).
* Trees (manifest SHA-256 in `INDEX.md`): `snap_C0_base` (accepted, `34a8d390…`), `snap_T9_final` (controlled batches C9 / C9b, first orchestrator groups), `snap_T11_final` (final: = T9 + per-region candidate stream + orchestrator-test flag assertions; `snap_T10_final` is the same tree with a syntax error in the test file — its orchestrator groups aborted in seconds and are kept as evidence of the attempt).
* Per-seed CSV: `evidence/comparisons/per_seed_acceptance.csv`; paired tables: `evidence/comparisons/*.md`; solver logs `evidence/runs/`.

## 6. Limits of the evidence

* 20 generator seeds of one dataset; the hold-out replicates (H5, C9, C9b) share seeds and differ only by load history — they are replicates,
  not independent samples.
* CBC is wall-clock-limited: under a different load pattern the same configuration can land 2.6 M apart; every comparison here is paired
  *within* one concurrent group, and this is why the increments are reported with their seed counts.
* Absolute profit levels are conditional on the provisional assumptions (capacity unit, dwell, bunker price, transit file).
* LLM providers answered `all_providers_failed` in every orchestrator run of this campaign (deterministic fallback text); LLM-driven
  behaviour with a live provider is not represented.
* No WorldLarge or other dataset was run; no real-world validation of any plan was attempted.
* Test-run artifacts: running the weather test on the live tree wrote 63 stub files into `data/maritime/snapshots/` (not an optimiser
  input; left in place; `patches/ROLLBACK.md` §4).
* An orchestrator run (default configuration, 364/364, 12.17 M) was executed in the live project directory at 23:37:57 – 23:44:35,
  **not by this campaign** (see `patches/ROLLBACK.md` §4): it overwrote three generated artifacts and overlapped the `G11_fin` runs.  It is
  not used as evidence anywhere.
