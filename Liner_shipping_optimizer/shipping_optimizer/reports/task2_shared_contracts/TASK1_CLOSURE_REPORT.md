# Task 1 closure report — WorldSmall data loader

Date: 2026-10-10 · Tree: `C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer`
Decision: **ACCEPTED** (loader contract), with one change that needs your explicit review (§5, port-cost basis).
The integration test `tests/test_orchestrator.py` still **FAILS** exactly as it did at baseline (same six assertions);
that is a statement about the economics downstream of the loader, not about the loader (see §7).

Everything below was measured or read from code; items I could not establish are listed as unresolved in §9.

---------------------------------------------------------------------------------------------------

## 1. Starting baseline (before any edit)

| Item | Value |
|---|---|
| Command | `python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider` |
| Environment | Windows 11, Python 3.11.9 (project `venv`), pytest 7.4.4, numpy 1.26.3, pulp 2.7.0, pandas 3.0.5, scikit-learn 1.4.2 |
| Run 1 (unmodified tree) | 1 failed · 258/264 internal assertions passed · 6 failed · 8 warnings · 208 s · weekly profit −156,023,852 |
| Run 2 (unmodified tree, clean bytecode cache) | 1 failed · 258/264 · 6 failed · 9 warnings · 199 s · weekly profit −145,937,200 |
| Failing assertions (identical in both runs) | `Global weekly profit > 0`, `Network is profitable (profit margin > 0)`, `Weekly profit > 0` ×2, `Annual profit > 0`, `Profit margin > 0` |
| Rest of suite (`pytest tests --ignore=tests/test_orchestrator.py`) | **57 failed · 785 passed · 45 skipped** (IDs saved in `evidence/baseline_suite_failed_ids.txt`) |

Notes on the baseline:
* The historical "29 passing integration tests" is not reproducible; the primary test is a single pytest function that runs the whole
  pipeline and counts 264 internal assertions.
* The traceback printed an `OneDrive\Desktop\...` path. That is a stale `.pyc` `co_filename` copied with the folder; `tests`/`src`
  resolve to this working tree (verified with `importlib.util.find_spec`). A second, older copy of the project exists at
  `C:\Users\WINDOWS\OneDrive\Desktop\Liner_shipping_optimizer\...`; 11 source/test files differ from this tree and its `data/raw` layout is the
  old flat one. I did not touch it.
* The git repository has no tracked files for this directory (everything is untracked), so there is no `git diff` safety net. I took a
  pristine copy + SHA-256 manifest of `src/ tests/ scripts/ data/raw` first; `evidence/` and `changes.patch` are relative to it.
* The pipeline is unseeded (no `random.seed`/`np.random.seed` anywhere) and GA/MILP are wall-clock capped, so run-to-run variation is real:
  two baseline runs differ by ~7% in profit and 170 vs 180 services.

## 2. What `tests/test_orchestrator.py` actually verifies (Step 1.1)

| Question | Answer |
|---|---|
| Entry point | one pytest function, `test_orchestrator()`, calling the real `OrchestratorAgent().process({"problem": ...})` |
| Problem source | `load_worldsmall_problem()` → `NetworkLoader.load_ports/load_demands/load_distance_matrix/load_fleet` with the explicit canonical `data/raw/WorldSmall` paths. The legacy JSON `load_problem(filename)` helper defined in the file is **not** used by this test. |
| Mocks | none. Real GA, real MILP (PuLP/CBC). LLM calls are real with a rule-based fallback (Groq returned HTTP 429 for some roles in run 1). |
| Genuinely verified | the data contract (47 ports, 1,764 demand rows, 2,162 directed pairs, 263 vessels/6 classes, TEU/FFE ≈ 2.0, no ×6), structural keys, ranges, annual = weekly×52, funnel monotonicity, ids unique, iteration count/audit shape |
| Tautologies / weak | `revenue == profit + total_cost` (the aggregator *defines* revenue that way), `Σ regional profit ≈ global profit` (global is the sum), per-service `profit == revenue − cost` (computed that way), LLM text-format checks, "phase/pathway" checks that test presence of keys |
| **Not verified at all** | that "profit" is accounting profit; that revenue is measured; fleet feasibility (vessel counts); capacity/frequency semantics; unit consistency of any cost; demand double counting; solver status per cluster; that coverage is relative to true demand |
| Side effects | writes `pipeline_output.json` (root, `frontend/public`, `frontend/dist` if present) and `SYSTEM_TRUTH_REPORT.md` even when assertions fail; writes `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md` only if all assertions pass — and that report contains hard-coded sample rows and "ESTIMATED" 30/40/20/10 % cost splits, i.e. fabricated numbers |
| Stale-artifact dependence | none for its own assertions; other tests (`tests/maritime/test_phase8_*`, `test_economic_metric_documentation`) read the generated JSON from disk |

I did not modify this file. My runner script restores the three files it overwrites after each run (verified byte-identical to the originals).

## 3. Source verification (Steps 2.1–2.4)

| Check | Result (measured) |
|---|---|
| Canonical files | `ports.csv`, `Demand_WorldSmall_Fixed_Sep.csv`, `dist_dense.csv`, `fleet_WorldSmall.csv`, `fleet_data.csv` all present in `data/raw/WorldSmall` |
| Delimiter | all five are **tab-separated** despite `.csv` |
| Look-alike files | `WorldSmall/demand_world_small.csv`, `fleet_world_small.csv` are byte-identical to the canonical ones; `WorldLarge/{ports,demand,fleet}_world_small*.csv` are byte-identical copies of WorldSmall data **sitting inside the WorldLarge directory** (this is the real "misleading file name" case) |
| Ports | 47 |
| Demand | 1,764 rows; 138,247 FFE/wk raw → 276,446.8 TEU/wk converted; raw gross revenue 264,870,100 USD/wk = converted 264,870,100 USD/wk (invariant holds per row, tested for all 1,764); demand scale 1 |
| Lane factors | 6 lanes differ from 2.0 (AEJEA→DEHAM 2.1, CNSHA→DEHAM 2.1, AEJEA→NLRTM 2.1, CNSHA→NLRTM 2.1, BRSSZ→USLAX 1.9, CNSHA→USLAX 1.85); the factor table has 26 keys, 6 of which are WorldSmall lanes (the other 20 have an end that is not a WorldSmall port, e.g. `GBSOU`, `USAOS`, `SGSGP`) |
| Distances | 2,162 directed pairs = 47×46; none missing, none duplicated, none ≤ 0; no 500 nm fallback exists in the loader |
| Fleet | 6 classes, 263 vessels (24/29/68/74/58/10); `Capacity FFE` used as `capacity_teu` unchanged (450 … 7,500), not doubled |
| Canal data | `dist_dense.csv` flags 340 pairs `IsPanama=1` and 586 `IsSuez=1`; `Draft` is non-blank on 340 rows; `panamaFee` is **blank** for Post_panamax and Super_panamax |
| Callers | defaults are used by `test_data_loader/test_ga/test_milp/test_clustering/test_service_generation`; `test_orchestrator.py`, `test_worldsmall_integration.py` and `scripts/run_pipeline_benchmark.py` pass explicit canonical paths |

## 4. Changes (each separately verified)

### S1 — explicit-path dataset boundary (`src/data/network_loader.py`)
* **Defect.** Explicit paths were trusted: nothing prevented a WorldLarge file from being loaded and combined with WorldSmall inputs, and
  `load_problem(json)` decided dataset identity from the file *name* only (`"worldsmall" in name`).
* **Change.** (a) A path inside `data/raw` but outside `data/raw/WorldSmall` is rejected by resolved location. (b) A ports/demand/distance
  file whose identifiers mix WorldSmall ports with foreign ports is rejected; a file with only foreign ids (isolated fixture) or only WorldSmall ids
  (subset) is accepted. (c) `load_problem(json)` additionally requires non-empty content, ports ⊆ WorldSmall ports, a complete directed
  distance matrix, and numeric equivalence with the canonical load (port costs, per-OD TEU and gross revenue); it now carries the WorldSmall fleet.
* **Callers affected.** none in production (`load_problem(json)` has only test callers).
* **Evidence/tests.** `TestExplicitPathBoundary` (10), `TestExplicitJsonDataset` (7).

### S2 — blank canal fee is not zero (`src/optimization/data.py`, loader)
* **Defect.** blank `panamaFee`/`suezFee` was loaded as `0.0`, i.e. "free", for Post_panamax and Super_panamax.
* **Change.** `FleetClass.panama_fee/suez_fee: Optional[float] = None`; blank → `None`; `validation_report["fleet"]["canal_fee_blank"]` lists them.
  No consumer reads these fields (grep over `src/ tests/ scripts/ backend/`), so no downstream numbers move.
* **Test retargeted (reason below).** `test_blank_fees_are_zero_...` asserted `== 0.0`; it now asserts `is None`.
* **Not inferred:** blank does not mean "cannot transit" either; transit feasibility is unresolved (§9, U-3).

### S3 — port-cost unit basis (`src/data/network_loader.py`) — **needs your review**
* **Defect.** `CostPerFULL`, `CostPerFULLTrnsf`, `PortCallCostPerFFE` are USD **per FFE** (project field tables: `MA_02_DATA_AND_UNIT_SEMANTICS_AUDIT.md`
  "USD per FFE"; and, in the OneDrive copy, `reports/worldsmall_phase1_5_2_audit.md` "USD/FFE"; the model fields are USD/TEU per
  `docs/DATA_DICTIONARY.md`). The loader *multiplied* them by 2.0.
  One FFE is 2 TEU, so a per-FFE rate becomes a per-TEU rate by **dividing** by 2 — the direction the loader already uses for `Revenue_1`.
  The loader's own invariant (`TEU flow × USD/TEU = FFE flow × USD/FFE`) is violated by ×2 and holds for ÷2.
* **Scale of the error (measured).** mean `CostPerFULL` 242.11 USD/FFE → loader gave 484.21 USD/TEU (correct: 121.05); a load plus a discharge
  was therefore 968 USD/TEU against a revenue-weighted mean of 958 USD/TEU — more than the average revenue itself. Error factor: 4.
* **Change.** `/ TEU_PER_FFE` (2.0) for the three per-FFE columns; `PortCallCostFixed` (USD per call) unchanged; the lane-specific revenue
  factors are *not* applied to port costs (port costs belong to the port).
* **Evidence of consequence.** Controlled A/B on `ServiceGA` (same 1,046 candidates, seeds 1–3, only the port-cost basis differs):
  corrected basis selects **185 services (179–193)**, legacy ×2 selects **72 (60–78)** (`evidence/ab_portcost_summary.txt`).
* **Previous documents disagree.** `MA_02`, `MA_09`, the OneDrive `verification/01_GOLDEN_SPECIFICATION.md` and
  `reports/worldsmall_*` all state "×2 … FFE→TEU consistent". None derives it; all assert it. I judged the dimensional argument decisive.
* **To revert** (one line each): change the three `/ TEU_PER_FFE` to `* TEU_PER_FFE` in `load_ports`, and flip the three assertions in
  `TestPortCostBasis`. `scripts/generate_worldsmall_dataset.py` and `data/datasets/worldsmall_shipping_problem.json` (legacy ×2) were not touched.

### S4 — WorldLarge-era tests retargeted (no assertion removed)

| Test | Why it contradicted the contract | Now |
|---|---|---|
| `test_data_loader::test_data_loader` (`len(ports) > 50`) | described the WorldLarge defaults | exact 47 / 1,764 / 47 (stronger) |
| `test_worldsmall_integration::test_distance_not_from_worldlarge_file` | `load_distance_matrix()` default is WorldSmall now | compares against the raw WorldLarge file (62,002 rows) read independently + asserts default == WorldSmall |
| `…::test_worldlarge_csv_path_unchanged` | expected defaults to load WorldLarge (333 / 9,622 / 43,056 — post-filter numbers from a loader that no longer exists) | raw WorldLarge files verified directly (435 / 9,622 / 62,002) **and** defaults verified to be WorldSmall (47 / 1,764 / 2,162) |
| `…::test_worldlarge_fleet_loads` | expected the default fleet to be 501 vessels | raw WorldLarge fleet file (6 classes, 501) verified directly; default fleet asserted 263 |
| `…::test_worldsmall_port_ids_not_in_worldlarge_only` | passed **vacuously** (both sides were WorldSmall) | WorldLarge ids read from the raw file; subset relation now meaningful |
| `test_worldsmall_loader::test_revenue_is_divided_not_multiplied_by_the_factor` | fixture used a non-WorldSmall port (`GBSOU`) next to WorldSmall ports | same assertions on the real WorldSmall lane AEJEA→NLRTM (factor 2.1) |
| `test_regional_agent::test_regional_agent` | loaded the **WorldLarge JSON** together with the default (WorldSmall) distance matrix; had **no assertions**; every missing leg was silently priced at 500 nm | uses `NetworkLoader().load_problem()`; assertions added (structure, finite money fields, coverage in [0,100]) |

Not touched although it pins a defect: `test_worldsmall_integration::test_no_demand_scale_on_worldsmall_json_path` asserts
`revenue_per_teu == 4580.0` for a raw 2,290 USD/FFE lane — the revenue-multiplication bug baked into the legacy JSON artifact
(gross revenue 4× canonical). It exercises the legacy `tests/test_orchestrator.load_problem` helper, not the loader; the loader's JSON route now rejects that file.

## 5. Port-cost and canal-fee conclusions (Step 2.5)

| Field | Raw unit | Model unit | Conversion now | Status |
|---|---|---|---|---|
| `CostPerFULL` | USD/FFE (field table) | USD/TEU | ÷ 2.0 | resolved by units; **review S3** |
| `CostPerFULLTrnsf` | USD/FFE | USD/TEU | ÷ 2.0 | same |
| `PortCallCostPerFFE` | USD/FFE (name) | USD/TEU | ÷ 2.0 | same |
| `PortCallCostFixed` | USD per call | USD per call | none | resolved |
| `panamaFee`, `suezFee` | USD per transit (fleet spec) | `Optional[float]` | blank → `None` | resolved: unknown ≠ 0; **not used by any model** |
| `IsPanama`, `IsSuez`, `Draft` (dist) | flags / m | — | not read | unresolved (U-3) |

## 6. Task 1 acceptance gate (Part 2.7)

| # | Condition | Result |
|---|---|---|
| 1 | paths, delimiters, schema, units verified | yes (§3) |
| 2 | revenue invariant passes | yes — per row (1,764) and aggregate (264,870,100) |
| 3 | fleet units and counts verified | yes — 6 / 263, capacity not doubled |
| 4 | dataset isolation tested | yes — 24 new tests; 19 of the 108 loader tests fail on the *original* loader and pass now |
| 5 | cost/fee ambiguities resolved or documented | yes — S2, S3; U-1…U-3 documented |
| 6 | `test_orchestrator.py` re-run and compared | yes — §7 |
| 7 | no unrelated optimizer code changed | yes — no GA/MILP/agent/config file touched in Task 1 |

## 7. Checkpoint A–E

### A. Baseline comparison

| Run | Tree | Result | Weekly profit | Services | Coverage | Fuel | Total cost |
|---|---|---|---|---|---|---|---|
| 1 | original | 258/264, same 6 fail | −156.0 M | 170 | 48.1 % | 214.7 M | 264.3 M |
| 2 | original | 258/264, same 6 fail | −145.9 M | 180 | 55.1 % | 228.4 M | 282.8 M |
| 3 | Task 1 | 258/264, same 6 fail | −326.5 M | 279 | 85.8 % | 532.7 M | 641.4 M |

* Pass/fail set: **unchanged** (258 pass; the same six profit-sign assertions fail).
* Broader suite: 57 → 53 failing, 4 fixed, **0 new** failures (final tree; §9 of the Task 2 report).
* Pipeline KPIs moved by far more than the 7 % noise between runs 1 and 2. **This is explained, not hidden:** the port-cost correction makes
  1.6–2.6× more candidate services look viable to `ServiceGA` (pipeline 170/180 → 279/285 services; controlled A/B 72 → 185), and every additional service then carries the (separately defective)
  fuel/cycle-time model. The corrected loader therefore *exposes* the downstream cost-model defect (Task 2, D-SVC-CYCLE) rather than causing it.
  **Do not read −156 M → −326 M as an economic deterioration; the two are not comparable** — the old numbers came from a network suppressed by a 4× port-cost error.

### B. Contract validation (measured)
Raw gross 264,870,100 = converted 264,870,100 USD/wk · 276,446.8 TEU/wk · 47 ports · 1,764 OD · 2,162 directed pairs · 6 classes / 263 vessels ·
capacity 450/800/1,200/2,400/4,200/7,500 · demand scale 1 · handling = CostPerFULL/2 for all 47 ports.

### C. Change impact

| File | Defect | Direct callers | Downstream | Covered by | Remaining risk |
|---|---|---|---|---|---|
| `src/data/network_loader.py` | unvalidated explicit paths; ×2 port costs; blank fee = 0 | tests, `scripts/run_pipeline_benchmark.py`, `tests/test_orchestrator.py` (explicit canonical paths — still accepted) | every optimizer that reads `Port.*_cost` (GA, MILP) | `tests/test_worldsmall_loader.py` | port-cost basis is a judgment (§4 S3) |
| `src/optimization/data.py` | undocumented units; fees default 0.0 | all | none read the fees | loader tests | `FleetClass()` default fees now `None` |
| tests (4 modified, 1 added) | see §4 S4 | — | — | — | — |

### D. Regression review
* `test_orchestrator.py` still exercises the intended active path (real GA+MILP on the WorldSmall CSV load) — yes; unmodified.
* Vacuous passes found and fixed: `test_worldsmall_port_ids_not_in_worldlarge_only`; `test_regional_agent` had no assertions.
* WorldLarge data entering the WorldSmall workflow: the one place it did (`test_regional_agent`) is fixed; the legacy helper
  `tests/test_orchestrator.load_problem(json)` still pairs a JSON dataset with default distances (not used by the primary flow; left untouched on purpose).
* Accounting double counting and solver-failure laundering still exist downstream — **documented, not fixed** (Task 2 report).
* Diff review: 2 production files + 4 modified tests + 1 new test; no GA/MILP/agent/config file changed in Task 1.

### E. Decision
**ACCEPTED** for the loader/data contract. Not a business-correctness validation: the integration test remains failing for downstream reasons.

## 8. Remaining limitations
* U-1 lane-specific FFE→TEU factors have no source in the repo (the table says "based on typical cargo mix").
* U-2 `Capacity FFE` is used numerically as TEU capacity (kept, per instruction). The source column is named FFE and the class names embed
  the same numbers; if the numbers really were FFE, TEU capacity would be 2×. This is the single remaining place where a 2× could hide.
* U-3 canal fees and canal/draft feasibility are not modelled anywhere (340 Panama-flagged and 586 Suez-flagged pairs carry no fee and no restriction).
* The legacy JSON datasets still carry the ×2 revenue/port-cost conventions; the loader now rejects the WorldSmall one with a clear message.

## 9. Unresolved
U-1, U-2, U-3 above; see the Task 2 report for U-4…U-7.
