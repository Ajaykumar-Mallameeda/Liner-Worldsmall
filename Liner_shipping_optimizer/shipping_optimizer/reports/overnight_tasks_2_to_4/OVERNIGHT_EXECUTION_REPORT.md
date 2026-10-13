# Overnight execution report — Tasks 2, 3, 4 (2026-10-10/11)

> **STATUS UPDATE 2026-10-11:** superseded. The Task 3 blockers were resolved, Task 4 implemented and Tasks 5-7 / Phase D completed and verified - see `../network_economics_redesign/FINAL_REPORT.md`. The text below is the historical record of the overnight run and is left unchanged.

| Task | Result | Next authorized |
|---|---|---|
| Baseline freeze | **reproduced** | — |
| 2 — capacity unit | **PASS** (convention retained as PROVISIONAL; unit not verified) | yes |
| 3 — candidate feasibility | **BLOCKED** at the integration gate (candidate model done and verified) | no |
| 4 — fuel from canonical fleet | **NOT STARTED** (gated on Task 3) | no |

Stopped as instructed at the failed gate. Task 5+ untouched. Nothing was deleted (see §6).

## 1. Baseline (frozen before any change; snapshot of the Task 1 tree, byte-identical to the accepted final tree)
Same interpreter and commands for every run; pipeline unseeded (~7 % run-to-run noise).

| | result |
|---|---|
| `tests/test_orchestrator.py` | 258/264, exit 1; the six `profit > 0` assertions fail (`Global weekly profit`, `Network is profitable`, `Weekly profit` ×2, `Annual profit`, `Profit margin`) |
| weekly profit / services / coverage | −303.0 M / 287 / 86.0 % (fuel 510.8 M, port 6.8 M) |
| rest of suite | 56 failed / 856 passed / 20 skipped / 8 xfailed (artifact present) — 53 / 836 / 43 / 8 artifact-free |
| candidate pool at baseline | capacities 1,000–12,000 TEU on 450–7,500 TEU vessels; constant 7/14/21-day cycles |

## 2. Task 2 — PASS
Details: `task2_capacity_verification.md`. Files: `src/data/network_loader.py`,
`src/optimization/data.py`, `tests/test_capacity_units.py` (new, 23 tests). Patch `patches/task2_capacity_unit.patch`.
* Unit **not verified**: no document available here defines `Capacity FFE`; the LINERLIB README and the OR-tools page state
  none, and the defining paper's text could not be retrieved. Kept as TEU capacity (no ×2), recorded as provisional, with the
  evidence trail and the unapplied alternative in `CAPACITY_UNIT_PROVENANCE`, carried on `Fleet`, the loader report and each
  generated `Service`. **Not** in `pipeline_output.json` (frozen output contract has no slot).
* Gate: orchestrator 258/264, same six failures (−318.1 M); suite 57/878/20/8 (+23 tests; the one extra failure is the
  artifact-dependent `…record_count_disagrees_with_headline`, which flips between runs of unchanged code).

## 3. Task 3 — BLOCKED
Details: `task3_service_feasibility.md`. Patch `patches/task3_service_feasibility.patch` (9 files).
* Built a closed-rotation feasibility model (legs incl. return once, speed from `designSpeed`, 24 h/port-call **assumed**,
  cycle = ceil, vessels = ceil(cycle·f/7), inventory, 12 rejection reasons) and wired every candidate through it.
* Result on WorldSmall (4 seeds): 1,046 generated → 1,046 accepted, 0 rejected, 34 class fallbacks; cycle time median 40 d
  (max 136 d); 957–960 of 1,046 legacy declared cycle times (92 %) were too short. First pass had 37 rejections
  (34 inventory, 3 repeated-port) before the class fallback and a source fix.
* Tests: 291 passed / 5 xfailed / 3 baseline failures in the related set; full suite 54 failed / 928 passed / 43 / 5
  vs clean baseline 53 / 836 / 43 / 8 — one newly failing test (`test_regional_agent`, same crash), 53 unchanged.
* **Blocker:** `tests/test_orchestrator.py` crashes in 4/4 runs: `HubMILP` fleet check (`TypeError: A False object cannot be
  passed as a constraint`, the known D-MILP-FLEET) followed by `TypeError` from the error handlers' unsupported logger
  kwargs. Cause: the fleet check rounds zero frequency up to one departure (38 of 57 selected services had f = 0; 260
  vessels "needed" vs 75 real, fleet 263) and the pruning ignores them; the old constant cycle times hid it.
  Remedies fall in MILP failure propagation / GA-frequency semantics, which this plan forbids, and fixing only the logging
  would turn the crash into silent zero results.

## 4. Task 4 — NOT STARTED
`task4_fuel_provenance_and_calculation.md` holds read-only provenance only (fuel fields available, table-vs-fleet
disagreements, callers). Nothing implemented.

## 5. Answers to the closing questions
1. **Task 2 passed; capacity is provisional** (used as TEU, not source-verified).
2. **Task 3 is blocked; 1,046 of 1,046 candidates are locally feasible** under the stated assumptions (port time assumed,
   capacity unit provisional, inventory checked per service only).
3. **Task 4 did not run;** fuel inputs available are t/day at design speed, idle t/day and the speed range; price (600 USD/t)
   is not in the canonical files.
4. **Orchestrator ran after every modification:** baseline ✔, Task 2 ✔ (passes the gate), Task 3 ✔ ×4 (crashes — recorded).
5. **New regressions:** Task 2 none. Task 3: one real (the orchestrator crash, and its regional-agent echo) — caused by a
   pre-existing defect that correct cycle times expose; no new defect was introduced in the candidate model.
6. **Unresolved:** capacity unit; port-time assumption; the zero-frequency/fleet defect and the logger-kwarg handlers;
   D-CAP-FREQ; fuel table vs fleet; 136-day / 20-vessel loops that pass the local test but not network-level value;
   output-contract slot for the capacity flag.
7. **Ready for Task 5?** No. Task 3's gate is open; the fleet/frequency/failure-propagation defects must be resolved
   (their own tasks) before the corrected cycle times can run through the pipeline.

## 6. Tree state, integrity and reversibility
* Real working tree checked read-only against the baseline manifest: **0 baseline files missing**, `legacy/` 140/140.
  Modified: `regional_agent.py`, `service_generator_agent.py`, `network_loader.py`, `optimization/data.py`,
  `candidate_service_generator.py`, `test_economic_metric_documentation.py`, `test_service_generator_activation.py`,
  `test_shared_contracts.py`. New: `service_feasibility.py`, `test_capacity_units.py`, `test_service_feasibility.py`.
* During patch building a **scratch** snapshot lost 550 files to a script of mine; the project tree was untouched. The
  scratch copy was rebuilt from its manifest, the tool rewritten to be read-only, and its Task 2 output reproduced the earlier
  patch hash exactly. No deletion commands were run afterwards.
* Task 3 is applied in the tree; undo with
  `git -c core.autocrlf=false apply -R reports/overnight_tasks_2_to_4/patches/task3_service_feasibility.patch`
  (validated with `--check`; not run). Task 2 stays applied.

## 7. Evidence index
`patches/` (2 patches + sha256) · `evidence/runs/` (meta, logs, JUnit XML: S0, S0clean, T2, T3b/c/d/e) ·
`evidence/comparisons/` (suite diffs, KPIs) · `evidence/tools/` (patch tool, comparer, GA/fleet probe, runners).
The accepted Task 1 report and patch were not modified.
