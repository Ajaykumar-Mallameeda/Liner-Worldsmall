# Task 17 — full-pipeline random-number control and reproducibility

**Status:** `ACCEPT FOR OWNER APPROVAL` as an opt-in control (`LINER_SEED`, default unset = behaviour unchanged).  **Not claimed:** bit-identical
end-to-end runs — three wall-clock / external sources of variation remain by design (§4) and were measured, not assumed (§3).

## 1. What exists

`src/utils/rng.py` (new, 59 lines) — one module owns all seeding.

| | unset (default) | `LINER_SEED=<n>` (non-negative integer) |
|---|---|---|
| generators | the process-global `random` / `numpy.random`, exactly as before | every stochastic component draws from **its own** generator, seed = first 63 bits of `sha256(n | component | region | …)` (independent of `PYTHONHASHSEED`) |
| consequence | nothing changes | results do not depend on which thread ran first or on region execution order (the orchestrator runs regions in a thread pool; a shared global generator cannot give that) |
| malformed value | `ValueError` naming the variable | — |

Components wired (each takes an optional generator and falls back to the global one, so direct callers and every pre-existing test are
unaffected): `ServiceGA` (`rng`, `np_rng`), `FrequencyGA` (`rng`), `HierarchicalGA` (derives both with labels `service_ga` /
`frequency_ga` + an `rng_label`), `CandidateServiceGenerator` (`rng`), `ServiceGeneratorAgent` (label `candidate_generator` + agent
name), `RegionalAgent` (passes `rng_label = "<region>#<call index>"` to its GA, so a region's repeated calls get distinct, repeatable streams).  `ServiceGA._crossover` became an instance method so it can use the instance generator.  No
algorithm, parameter or acceptance rule changed.

## 2. Tests (11 new in `tests/test_rng_control.py`, 1 updated)

unset ⇒ the global generators; parsing and errors; derived seeds are stable (a pinned value, `4587962692285842661`) and label-dependent;
seeded streams repeat; **the same seed gives the same GA result whatever the state of the global generators**; seeded components never
touch the global generators (the global state is unchanged after the call); two seeds give different streams; order independence (regions
evaluated in either order give identical results); `FrequencyGA` and `CandidateServiceGenerator` repeat for the same seed; unseeded
generators still honour `random.seed(...)` by the caller.  The existing finding-F-21/F-28 test
(`test_no_random_seeding_in_production_code`) now exempts exactly one file, `src/utils/rng.py`: see
`test_failure_remediation_report.md` §2b.

## 3. Measured reproducibility

### 3.1 R1 — the controlled global stage, replicates under identical load (`evidence/comparisons/R1_replicates.md`)

Seeds 0 – 4; per seed four processes at once: two copies of the default configuration and two copies of the final candidate (C1 + LS + 10 %
class variants), `PYTHONHASHSEED=0`, CBC 120 s.

| configuration | seeds with identical plan (pair A vs B) | pool / path-set / integer-problem size / dual bound equal | max \|Δ profit\| |
|---|---|---|---:|
| default | **5 / 5** | 5 / 5 | 0 USD |
| final candidate | **5 / 5** | 5 / 5 | 0 USD |

Under an identical load pattern the whole controlled stage — pool, paths, relaxation, time-limited incumbent, local search, ledger — is
**bit-reproducible**, and the default arm equals the recorded Tasks 19 – 21 results to the dollar on all five seeds.  What is *not* stable is the
incumbent *across load patterns*: the same configuration on the same seed gave 13.95 M and 11.36 M (seed 12, final candidate, batches H5 and C9
of Phase 5, which differed only in what else the machine was doing).  Time-limited CBC returns the best incumbent found in 105 s of
wall-clock; a different load pattern is a different search trajectory.  This is a property of the solver budget, not of the model or of any
random-number source, and it is why every comparison in this campaign runs its arms concurrently.

### 3.2 R2 — the full pipeline (`tests/test_orchestrator.py`), three concurrent runs per condition (`evidence/comparisons/R2_*.md`)

Compared run against run, for every iteration and region: services generated / kept by the regional filter, GA generations and best
fitness, the regional selected-service sets, the global plan (service, class, frequency) and the profit.

| condition (3 runs each) | generated / filtered counts | GA generations + best fitness | regional selected sets | global plan | profit |
|---|---|---|---|---|---|
| unseeded, default code (Phase 2 blocks) | differ | differ | differ | differ | differ |
| unseeded, final candidate | differ | differ | differ | differ | differ |
| `LINER_SEED=11` | **identical** (9 iterations) | **identical** | **identical** | **identical** | **identical** (14,698,021 USD/wk in all 9) |
| `LINER_SEED=12` | **identical** | **identical** | differ in 2 of 9 iteration-slots (both in run 1) | differ in those slots | differ in those slots (15.47 and 15.23 against 14.54 M) |

* **Everything the random-number sources produce is reproducible under a seed:** candidate counts, the regional filter, the GA's path
  (generations, fitness) — in 18 of 18 seeded iteration-slot comparisons.  Unseeded, none of them repeats.
* **The global plan repeated in 16 of 18 slots.**  The two slots that differed (seed 12, iterations 0 and 2 of run 1; run 2 and run 3
  agree with each other in all three iterations) have identical inputs and identical regional GA results; only the *global* stage's incumbent
  differs — the time-limited CBC under a different load history
  (the three orchestrator runs share the machine and their LLM back-off timings differ).  It is the same wall-clock effect as in §3.1, here
  without the equal-load protection of the controlled harness.
* **Defect found by this comparison (fixed in the final tree):** in the seeded runs *all three iterations of one run were identical*
  (same candidate pool, same global plan).  The candidate generator drew its stream from one label for every region and every call
  (`"candidate_generator" + "svc_gen"`), so repeated iterations — whose purpose is exploration, the best of three is selected — repeated
  themselves.  Seeding must make a run *repeatable*, not *uniform*: each (region, call) now has its own stream
  (`svc_agent.rng_label = "<region>#<call>"`; `tests/test_rng_control.py::TestCandidateGeneratorStreamsPerRegionAndCall`).  The R2 rows
  above are from **before** that change; the repeat on the final tree is §3.3.
* Not a source of variation in these runs: the genetic algorithms' wall-clock cap (all 189 regional GA executions in the orchestrator
  outputs of this campaign stopped by stagnation, longest 0.88 s against a 55 – 60 s cap); string-hash randomisation (the orchestrator
  runs do not pin `PYTHONHASHSEED`, and the six seeded runs agree).

### 3.3 R2 again on the final tree (`snap_T11_final`: per-region / per-call candidate streams; `evidence/comparisons/R2_final_tree_seeded.md`)

| condition (3 concurrent runs each, final candidate configuration) | generated / filtered counts | GA generations + fitness | regional selected sets | global plan | profit |
|---|---|---|---|---|---|
| unseeded (`G11_fin`) | differ | differ | differ | differ | differ |
| `LINER_SEED=11` (`R2e`) | **identical** (9 iteration-slots) | **identical** | identical in 8 of 9 slots | identical in **8 of 9** | identical in 8 of 9 (run 2, iteration 2: 15.92 against 15.51 M) |
| `LINER_SEED=12` (`R2f`) | **identical** | **identical** | **identical** | **identical in 9 of 9** | **identical** (15.85, 13.83, 13.48 M for iterations 0 – 2) |

* **Exploration is back:** within a seeded run the three iterations now produce *different* plans (seed 11: 14.46, 13.36, 15.51 M; seed 12:
  15.85, 13.83, 13.48 M) — each repeated exactly by the other two runs.  Before the stream fix all three iterations were the same plan.
* **Everything the application's random numbers produce is identical in 18 of 18 seeded slots** (candidate counts, filter output, GA
  generations and fitness), and the *global plan* is identical in 17 of 18.  The single deviation (seed 11, run 2, iteration 2) has the same inputs,
  the same regional results and a different global incumbent: CBC's wall-clock again.
* So the claim this report makes is exactly: **with `LINER_SEED` the pipeline up to and including the candidate pool is reproducible; the
  final plan is reproducible whenever the time-limited CBC incumbent is, which equal load makes true (R1) and the shared machine of three
  concurrent end-to-end runs makes true 17 times out of 18.**  It does not claim a deterministic solver.


## 4. Inventory of random and timing sources, and what controls each

| # | source | where | before | now | class of variation |
|---|---|---|---|---|---|
| 1 | service GA (`random`, `numpy.random`) | `src/optimization/service_ga.py` | process-global generators | `rng` / `np_rng` parameters; `HierarchicalGA` derives them from `streams("service_ga", label)` | candidate generation |
| 2 | frequency GA | `src/optimization/frequency_ga.py` | global | `rng` parameter, `streams("frequency_ga", label)` | candidate generation |
| 3 | demand-driven candidate generator | `src/services/candidate_service_generator.py` | global `random` | `rng` parameter | candidate generation |
| 4 | service-generator agent | `src/agents/service_generator_agent.py` | global | `streams("candidate_generator", "<region>#<call>")` | candidate generation |
| 5 | regional agent (GA call index, candidate-generator call index) | `src/agents/regional_agent.py` | – | labels `<region>#<n>`; every call a distinct, repeatable stream | candidate generation |
| 6 | regional agents in a thread pool (completion order) | `orchestrator_agent.py` (`ThreadPoolExecutor`) | shared global generator ⇒ order-dependent | per-component generators ⇒ order-independent (test: `test_order_independence`) | scheduling |
| 7 | legacy GA / MILP modules (`*_legacy.py`), `src/utils/sample.py` | `src/optimization/…_legacy.py` | global `random` | **not imported by any active module** (grep over `src`, `backend`, `maritime`): not on the pipeline's path, left untouched | – |
| 8 | GA wall-clock caps (`MAX_RUNTIME`, 55 – 60 s) | `service_ga.py`, `frequency_ga.py`, `hierarchical_ga.py` | wall-clock | unchanged; **never reached**: 189 of 189 regional GA executions in this campaign's orchestrator outputs stopped by stagnation (longest 0.88 s) | timing (latent) |
| 9 | string-set iteration order (`PYTHONHASHSEED`) | model / candidate construction | randomised per process unless pinned | harness pins `PYTHONHASHSEED=0`; the orchestrator runs do not.  No effect observed: pool, path-set and model hashes equal in all R1 replicates; the six seeded orchestrator runs of R2 agree on everything the GA and filters produce | model construction (latent) |
| 10 | CBC incumbent under a 105 – 120 s wall-clock limit | `network_milp._solver` (PuLP `PULP_CBC_CMD`, single thread) | wall-clock | unchanged (no solver seed is exposed or set) | solver search + environmental timing |
| 11 | LLM providers | agents | answers vary; 429 back-off timing | unchanged; all providers answered `all_providers_failed` in every run here (deterministic fallback text) | external |

### 4.1 The four kinds of variation, separated

* **Candidate-generation nondeterminism — controlled by `LINER_SEED`.**  Unseeded: candidate counts, filtered counts, GA generations and
  fitness differ run to run (R2, unseeded groups).  Seeded: identical in all 18 seeded iteration-slots of the first R2 pair and in all 18 of the final-tree pair (§3.3).
* **Model-construction nondeterminism — none observed, not excluded.**  Pool hash, path-set hash, integer-problem size and dual bound equal
  in all 10 R1 replicate pairs.  Hash-seed randomisation is the one latent source (row 9); pinning it in the harness is the safeguard.
* **Solver-search nondeterminism — present, measured, not removable here.**  Under identical load the time-limited CBC incumbent repeats
  (R1: 10/10 pairs); across load patterns the same configuration moved by up to 2.6 M on one seed (H5 vs C9, seed 12).  Seeding the application
  does not make CBC deterministic; this report does not claim it.
* **Environmental timing effects — present.**  Orchestrator runs share the machine and their LLM back-off timings differ, which changes
  the load history of the global stage: in the seed-12 group two of the nine iteration-slots of one run landed on a different incumbent
  (global profit 15.47 / 15.23 against 14.54 M) with identical inputs.

### 4.2 Methodology that follows (what to do instead of claiming bit-for-bit)

1. Fix `LINER_SEED` and `PYTHONHASHSEED=0`; compare candidate-pool, path-set and model hashes first — a difference there is a defect.
2. Run all arms of a comparison **concurrently** so they see the same load; compare *paired within a seed*, never across batches.
3. Report seed counts for every increment; treat a single seed's profit as one draw of the solver's incumbent distribution (≈ ±1 M, rarely ±2.6 M).
4. For decisions use ≥ 10 paired seeds on development *and* a hold-out set, as done here.

## 5. Summary for the owner

* **What improved:** one opt-in module (59 lines), no algorithm change; with `LINER_SEED` every random draw of candidate generation, the
  regional filter and the genetic algorithms is a function of (seed, component, region, call); regions and iterations draw different streams;
  results no longer depend on thread order.  11 + 2 tests.
* **What is demonstrated:** equal-load replicates of the controlled stage are identical (10/10); three concurrent end-to-end runs with one
  seed agree on every GA / candidate quantity (18/18 slots, twice) and on the final plan in 33 of 36 slots.
* **What is not claimed:** a deterministic solver.  The 120 s CBC incumbent is a function of wall-clock; the remaining spread is measured
  (up to 2.6 M on a seed under a different load pattern) and the comparison methodology of §4.2 contains it.
* **Decision requested:** approve `LINER_SEED` as an opt-in experiment control (default unset = behaviour unchanged); the one exemption in
  `test_no_random_seeding_in_production_code` goes with it.
