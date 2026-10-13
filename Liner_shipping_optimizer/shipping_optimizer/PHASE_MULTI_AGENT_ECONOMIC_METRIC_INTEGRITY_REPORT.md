# PHASE MA — MULTI-AGENT ECONOMIC-METRIC INTEGRITY REPORT

**Deliverable set:** `MULTI_AGENT_ARCHITECTURE_FORMULATIONS_ECONOMIC_METRIC_INTEGRITY.md`
· 7 JSON artifacts · `tests/test_economic_metric_documentation.py` · this report.

**Scope executed:** documentation and read-only audit. No scientific behaviour was
modified. No git operation was performed at any point.

---

## Final verdict

# METRIC DEFINITIONS VERIFIED WITH DOCUMENTED DIFFERENCES

This is one of the three permitted verdicts. It is **not** a statement that the
metrics are correct — it states that each metric now has exactly one verified
definition, that every divergence is documented with evidence, and that the
remaining gaps are recorded rather than assumed away.

Read the verdict strictly. It does not certify the economics. §AD lists what must
change before any external comparison is attempted.

---

## A. Mandate and constraints

| Constraint | Status |
|---|---|
| No git operations | Honoured — none performed |
| Documentation and audit only | Honoured — no `src/`, `backend/`, `frontend/` file modified |
| No retraining, reruns, parameter or algorithm changes | Honoured |
| Final benchmark not run | Honoured — the contract *specifies* how, the phase did not run it |
| RL source verified independently | **Impossible** — the source is absent; every RL cell is `RL-REF`, `is_verified: false` |
| No false comparability asserted | Honoured — six-criterion test; comparability graded, never inferred from a shared name |
| No ranking, scores or superiority claims | Honoured — enforced by a test |

## B. Method

1. Complete AST-derived file inventory — 146 files, 39,286 lines.
2. AST-derived dependency graph — 448 internal edges, no name inference.
3. Trace every economic formula from CSV column → loader transform → objective →
   reported field, with `file:LINE` and `EXEC` reproduction where numeric.
4. Reconcile the books at each reporting layer.
5. Compare against RL without fabricating comparability.
6. Validate with a documentation test suite that is adversarial toward the document.

## C. Evidence discipline

Seven source tags (`SRC`, `DATA`, `EXEC`, `REPORT`, `RL-REF`, `NOT ESTABLISHED`) and
eight classification labels, applied per the mandate.

**47/47 formula citations resolve against the live source.** Every citation is
verified by an automated test, so this document cannot drift from the code without
failing the suite.

## D. Audit coverage

| Area | Status | Sections |
|---|---|---|
| File inventory & dependency graph | complete | 3–4 |
| Data model & loading | complete | 5, 9, 22, 34 |
| Orchestrator & regional agents | complete | 6–7 |
| LLM layer | complete | 8 |
| Service generation | complete | 10 |
| GA (3 levels) + fitness | complete | 11–12 |
| MILP formulation | complete | 13 |
| Economics (revenue→profit) | complete | 15–17 |
| Coverage / utilization / fleet | complete | 18–20 |
| Distance model | complete | 21 |
| Metric lineage | complete | 26–27 |
| Accounting reconciliation | complete | 22 |
| RL comparison | complete, GRAY where unestablished | 32 |
| Paper traceability | complete | 33 |
| Reproducibility | complete | 28–29 |
| Benchmarks | **contract only — not run** | 35.1 |

## E. Artifact under audit

`pipeline_output.json`, 1,663,473 bytes, mtime 2026-10-03 21:54 +0530, WorldSmall.

**This file was rewritten mid-audit.** An earlier read returned 309 services,
$275.08 M profit, 88.3692 % coverage; the current file returns 314 / $296.07 M /
88.9116 %. Every figure in the deliverables is re-derived from the current file.

That substitution is itself a finding (§G) and is the reason the Benchmark Contract
requires hash pinning.

## F. Findings summary

28 findings: **13 critical, 11 major, 2 minor, 2 informational.**

| ID | Finding | Severity |
|---|---|---|
| F-01 | Revenue inflated 4× — volume *and* rate both scaled; undocumented everywhere | critical |
| F-02 | Second demand path applies `DEMAND_SCALE = 6` unconditionally | critical |
| F-03 | Four port cost columns, one rule applied three times | major |
| F-04 | Entire fleet cost vocabulary loaded, never read; idle & canal terms absent | critical |
| F-05 | Fuel model hardcoded, contradicts the shipped dataset | major |
| F-06 | `weekly_cost` is a heuristic with no daily→weekly bridge | critical |
| F-07 | FrequencyGA computes fuel, then omits it from fitness | critical |
| F-08 | GA constrained to 263 vessels, MILP to 300 | major |
| F-09 | `coverage_reward` is a USD-scaled shaping term inside the objective | major |
| F-10 | Six different profit formulas; reported ≠ optimised | critical |
| F-11 | Two transshipment formulas; reported ≠ optimised | major |
| F-12 | GA penalises uncovered demand at 50 USD/TEU, MILP at 300 | major |
| F-13 | Port handling charged per port touched, not per transshipment | major |
| F-14 | 17,169 duplicated OD pairs, differing distances, silent last-write-wins | major |
| F-15 | `profit_margin_pct` is two numbers (26.4 and 73.6) in one artifact | critical |
| F-16 | Regional coverage clamped to 100 %; denominator inflated 11.6 % | critical |
| F-17 | `summary_metrics` accounting identity holds exactly | info |
| F-18 | `problem_analysis` reports "0 services" during a 314-service run | minor |
| F-19 | All 22 LLM calls failed; result came entirely from fallbacks | major |
| F-20 | `adaptive_budget` is wired, but 3 of 5 outputs are discarded | info |
| F-21 | No random seeding anywhere | critical |
| F-22 | Silent 500 nm fallback enters the fuel objective | major |
| F-23 | LLM weight chain terminates unused — `profit_first` ignores Problem weights | critical |
| F-24 | SharedContext write-only; consensus archetype a dead end | major |
| F-25 | Per-service records ≠ summary (61 % profit gap; 308 vs 314) | critical |
| F-26 | No test asserts any economic identity | critical |
| F-27 | Iteration loop cannot exit early (`MIN == MAX == 3`) | minor |
| F-28 | No seed, timestamp, commit or input hash in the artifact | critical |

## G. Artifact volatility

`EXEC` — `pipeline_output.json` was replaced during this audit. Observed across two
reads separated by minutes:

| Quantity | Earlier read | Current read |
|---|---|---|
| file size | 1,626,651 | 1,663,473 |
| total_services | 309 | 314 |
| weekly_profit | 275,077,113.70 | 296,065,092.08 |
| coverage | 88.3692 | 88.9116 |
| profit_margin_pct | 72.7 | 73.6 |
| total_runtime | 313.8 | 255.8 |

No provenance field distinguishes the runs (§28). **Any result reported without a
hash can be silently replaced between production and audit.**

## H. Formula index

42 formulas: 20 `IMPLEMENTED DEFINITION`, 9 `ENGINEERING CONVENTION`,
6 `REPORTED METRIC`, 3 `ASSUMPTION`, 3 `NOT IMPLEMENTED`, 1 `DERIVED METRIC`.

Notable absences from the implemented set: no utilization metric, no enforced
coverage constraint, no idle or canal cost term, no charter-rate derivation.

## I. Unit integrity

Dataset FFE/week → TEU/week via a **lane-specific** multiplier (default 2.0). Because
volume *and* rate are both multiplied, revenue scales by **f² = 4.0** for WorldSmall
(measured: 264,870,100 → 1,059,480,400, ratio exactly 4.0).

The conversion table has 26 keys, two of which contain a literal space and can never
match. Costs are not scaled by 4.

## J. Accounting reconciliation

| Layer | Balances? | Note |
|---|---|---|
| `summary_metrics` | **yes** | components sum exactly; identity holds to 5.96e-08 |
| regional → summary | **yes** | exact on all 8 economic fields |
| `summary_metrics` ↔ `global_metrics` | **no** | `total_cost` differs by 721,091,931.50 (87.2 %) |
| `selected_services` → summary | **no** | profit differs by +180,847,468.75 (61 %) |
| service count | **no** | 308 records vs 314 headline |
| regional coverage | **no** | clamped; `sat+uns` exceeds true demand by 32,024.4 |

## K. GA layer consistency

| Property | ServiceGA | FrequencyGA |
|---|---|---|
| Adaptive pop size | **no** — constant table | **no** — constant 40 |
| Adaptive generations | **yes** | **no** — constant 60 |
| Adaptive stagnation | **yes** | **no** — constant 8 |
| Time limit honoured | 90 s constant (55 s request ignored) | 90 s constant |
| Crossover | single-point | **none** |
| Mutation | 0.10/0.15/0.20 | always, 1 gene |
| Elitism | top-10 | top-10 |
| Repair | **none** | **none** |
| Fuel in fitness | **yes** | **no** (F-07) |

## L. MILP layer consistency

Fleet ceiling 300 vs GA's 263. Coverage constraint declared but never enforced
(`DEFAULT_MIN_COVERAGE = 0.0`). `coverage_reward` is a USD-scaled shaping term
included in the reported profit. Reported transshipment uses a flat 80.0 while the
objective uses a per-port tariff of 0–1,720.

## M. LLM influence determination

**No LLM output changes the final optimization result.** F-23.

The chain is genuinely built: LLM → validate → consensus → `Problem` → `ServiceGA`.
It terminates at `service_ga.py:98`, because `CONFIG.objective_mode = "profit_first"`
routes every run to a branch that ignores the Problem weights and uses hard-coded
constants.

This is stronger than "the LLM calls failed" (§F-19): **even a fully successful LLM
run produces the same answer.**

`SharedContext` is constructed, updated and serialised, and read by nothing.
`final_archetype_params` has no consumer outside the consensus engine.

## N. Reproducibility determination

**A run cannot be reproduced.** Three independent blockers: no seeding (0 occurrences
in `src/`/`scripts/`); no provenance in the artifact; LLM dependence with 0 % success.

## O. Test suite state

Baseline before and after this phase, unchanged: **24 failed, 263 passed**, 431 s.
The 24 failures are pre-existing and are **not** addressed by this documentation
phase; they are recorded, not fixed.

New: `tests/test_economic_metric_documentation.py` — **58 passed**.

Final confirmation run over the whole suite after all deliverables were written:
**24 failed, 321 passed** in 526 s. 321 = 263 baseline + 58 new, so the failure count
and the passing baseline are both unchanged — this phase introduced no regression and
repaired no pre-existing failure.

`test_worldsmall_integration.py` pins the ×2 conversion and `DEMAND_SCALE = 6` as
expected behaviour. Those assertions are load-bearing for the current model and were
left untouched; correcting the economics requires updating them deliberately.

## P. What balances and what does not

**Balances:** the `summary_metrics` block; the regional→summary rollup; the
annualisation identity.

**Does not balance:** `global_metrics` against `summary_metrics`; the per-service
list against either; the service count; the regional coverage figures.

## Q. Documentation integrity

`DATA_DICTIONARY.md` partially violated · `BENCHMARKS.md` stale (describes a
different run; quotes two unreproducible per-TEU figures) · `SYSTEM_TRUTH_REPORT.md`
self-contradictory · `P2_DIAGNOSTIC` contains fabricated derivations and a table
summing to 110 % · `PIPELINE_OUTPUT_CONTRACT.json` violated (declares 5 regions,
artifact has 3).

The artifact's own scorecard claims 265/265 passed — while two contract tests would
fail against it.

## R. RL comparison determination

13 metrics graded on six criteria. **1 GREEN, 2 YELLOW, 7 RED, 3 GRAY.**

Every RL cell cites `RL-REF` and is marked `is_verified: false`. The RL source is
absent from this repository; no RL claim rests on primary evidence.

The single GREEN cell is the **distance matrix** — content-identical to the RL master,
MD5 differing only by an added BOM. The raw demand and fleet files are byte-identical
too. **The data layer is reconcilable; everything that diverges diverges after
loading.**

## S. Same-input reconciliation

Verified by MD5: `demand_world_small.csv`, `fleet_world_small.csv`,
`WorldSmall/fleet_data.csv`, `ports_world_small.csv` are **byte-identical** to the RL
master. `distance_dense.csv` is content-identical. The WorldSmall distance subset
(2,162 pairs) is clean: 0 missing, 0 duplicate, 0 asymmetric.

## T. Unit reconciliation

Not achieved. MA's demand is TEU with a lane-specific, revenue-squaring multiplier;
the RL basis is `NOT ESTABLISHED` from the reference document alone.

## U. Distance reconciliation

Verified GREEN. 62,002 rows, 208 ports, 43,056 unique OD, same 17,169 duplicates.
One caveat carried into the contract: MA discards those duplicates by
last-write-wins, and the RL master may resolve them differently.

## V. Fleet comparability

YELLOW. The quantity file is byte-identical. MA's own 263-vs-300 inconsistency is an
internal defect to repair on the MA side, not a cross-system difference.

MA also loads and never reads ten economic fields — charter rate, bunker consumption,
idle consumption, Panama fee, Suez fee, speeds, draft, capacity. **The data needed to
price idle and canal costs ships with the benchmark and is ignored.**

## W. Metric lineage

Six full chains documented with `DISCARDED` markers. Three of the four largest cost
inputs follow the load-then-ignore path.

## X. Single source of truth

**None exists.** Six documents report figures, and they disagree with each other and
with the artifact. `BENCHMARKS.md` declares itself the single runtime truth while
describing a superseded run.

## Y. Paper traceability

LINERLIB provenance **confirmed** (data only). Dutta et al. **not established** —
source absent. Clarksons 2024 **contradicts the dataset**. Three internal documents
violated or stale.

## Z. End-to-end trace

`weekly_profit` passes through ten stages from CSV to headline. It is the product of
all ten, each with its own transformation, and the headline formula is neither the one
the GA ranked nor the one the MILP maximised.

## AA. Computational metrics

255.8 s, 3 iterations, 3 regions. `health_status.iterations` reports 2 against
`iterations_run` = 3 — an internal inconsistency. `RUNTIME_PIPELINE_BENCHMARK.json`
records a different, undated-to-code run.

## AB. Reproducibility determination

Cannot be reproduced. No seed, no provenance, environment-dependent behaviour. The
only deterministic element is KMeans (`random_state=42`).

## AC. Benchmark readiness

**NOT READY.** Beyond the mandate's §36 hold, the preconditions are unmet on the
merits: the headline profit carries a 4× source distortion; the largest cost inputs
override the shipped dataset; `total_cost` and `profit_margin_pct` each have two
values; coverage is clamped and its denominator inflated; runs are not reproducible.

A benchmark today would produce internally consistent, externally meaningless numbers.

---

## AD. Priority repair sequence

Ordered by dependency — each step makes the next one verifiable.

1. **Resolve `total_cost` and `profit_margin_pct`** (F-15). One denominator, one
   value, one definition. *Nothing else can be validated until the headline is
   single-valued.*
2. **Reconcile coverage** (F-16). Remove the clamp at `regional_agent.py:442`; fix
   the denominator; decide whether `sat+uns` or true demand is canonical.
3. **Resolve the revenue unit distortion** (F-01). Declare the FFE→TEU basis once,
   apply it consistently, document it in `DATA_DICTIONARY.md`.
4. **Ground the cost model in the dataset** (F-04, F-05, F-06). Derive `weekly_cost`
   from `tc_rate_daily`; use `fleet_data.csv` bunker consumption; decide whether idle
   and canal terms are in scope. *The data already ships.*
5. **Reconcile service counts and aggregates** (F-25). 308 vs 314; 61 % profit gap.
6. **Add the economic assertions** (F-26). The identities that hold should be pinned;
   the ones that fail should fail loudly.
7. **Add provenance** (F-21, F-28). Seed, hash, commit, timestamp — emitted by the
   pipeline, not by convention.
8. **Reconcile the fleet ceiling** (F-08). 263 in the GA, 300 in the MILP.
9. **Fix the GA/MILP fitness divergences** (F-07, F-09, F-11, F-12, F-13).
10. **Decide the LLM's role** (F-23). Either wire the weights into the production
    fitness branch, or remove the path and document the system as deterministic.

---

# BENCHMARK CONTRACT

**18 points.** A future benchmark phase satisfies all of them or does not run.
None has been executed in this phase (§36).

### Inputs and identity

1. **Pin inputs by SHA-256**, not by path. Both engines must receive provably
   identical files.
2. **Record the artifact hash** in the run output. A result whose file was replaced
   between production and audit is not a result (§G).
3. **Pin the code state** — commit SHA, `requirements.txt` with hashes, and a
   transitive lockfile.

### Units and terms

4. **One unit of demand**, declared on both sides, with the FFE→TEU multiplier stated
   as a number on both sides and shown equal.
5. **One revenue basis.** No side may scale volume and rate by the same factor
   without the effect being declared and accounted for.
6. **Explicit cost-term match.** Enumerate both engines' term sets and map them item
   by item. MA's set is {operating, fuel, transshipment, port}; idle, canal and
   charter-depreciation **do not exist** and would have to be implemented, not assumed.
7. **No hardcoded constants that override supplied data** (F-04, F-05, F-06). Any
   override must be written down with its source and justification.

### Constraint parity

8. **One fleet ceiling**, identical in both engines (F-08).
9. **One fleet specification basis** — either both use the dataset's cost fields or
   both use hardcoded tables, and the choice is recorded.
10. **One distance policy**, including duplicate resolution. MA currently discards
    17,169 duplicated OD pairs by last-write-wins (F-14); the other engine's policy
    must be checked, not assumed.

### Metric definitions

11. **One definition per metric**, enforced by an assertion in the run itself. No
    metric may carry two values in one output (F-15).
12. **Coverage denominator declared** and reconciled against true demand. No clamp
    may survive into a reported figure (F-16).
13. **Aggregates reconcile.** Service count, per-service sums and headline totals must
    agree (F-25).
14. **Profit is the quantity optimised**, or the difference between the optimised and
    the reported quantity is stated and quantified (F-10).

### Run discipline

15. **Fixed seed, recorded in the output** (F-21).
16. **N ≥ 5 runs per configuration**, reporting mean and spread. The pipeline is
    stochastic by construction; a single run is not evidence.
17. **No LLM-dependent path in the measured configuration**, or the LLM's
    contribution is separately measured and reported. Given F-23, the default is the
    deterministic path.
18. **Reporting discipline.** Every number in a report is traceable to a field in the
    artifact. No estimated, interpolated or illustrative figure appears in a results
    table. The `P2_DIAGNOSTIC` pattern — fabricated fixed-percentage derivations
    presented as economics — is the specific anti-pattern this forbids.

---

## Deliverable manifest

| File | Contents |
|---|---|
| `MULTI_AGENT_ARCHITECTURE_FORMULATIONS_ECONOMIC_METRIC_INTEGRITY.md` | 37 sections + Appendices A–F |
| `MULTI_AGENT_FILE_DEPENDENCY_MAP.json` | 146 files, 39,286 lines, 448 edges |
| `MULTI_AGENT_FORMULA_INDEX.json` | 42 formulas (F01–F42), 28 findings |
| `MULTI_AGENT_ECONOMIC_METRIC_MATRIX.json` | 15 metrics with reconciliation status |
| `MULTI_AGENT_METRIC_LINEAGE.json` | 6 full chains with `DISCARDED` markers |
| `MULTI_AGENT_RL_COMPARISON_MATRIX.json` | 13 metrics, six criteria, all RL-REF |
| `MULTI_AGENT_DATASET_COMPARABILITY.json` | MD5 + line-diff vs RL master |
| `MULTI_AGENT_PAPER_TRACEABILITY.json` | 8 references with status |
| `tests/test_economic_metric_documentation.py` | 58 tests |
| `PHASE_MULTI_AGENT_ECONOMIC_METRIC_INTEGRITY_REPORT.md` | this report |

**Generator scripts** (read-only w.r.t. the codebase):
`scripts/build_dependency_map.py`, `scripts/build_formula_index.py`,
`scripts/build_audit_artifacts.py`.