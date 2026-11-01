# Multi-dataset validation and scalability campaign — final report (2026-10-16)

## Verdict

**`SCALABILITY DEMONSTRATED WITH LIMITATIONS`**

| dataset | status |
|---|---|
| WorldSmall | validated; baseline reproduced (3 seeds); unchanged |
| baltic | extracted, validated, optimised (5 seeds), all runs verified |
| WAF | extracted, validated, optimised (5 seeds), all runs verified |
| World-500 (synthetic) | generated reproducibly, validated, optimised (3 seeds), all runs verified |
| World-1000 (synthetic) | generated reproducibly, validated, optimised (3 seeds), all runs verified |

19 pipeline runs in the campaign table (+1 verification run): 0 failed, 0 infeasible, 0 killed by the wall cap, 0 without an output.
Every run ended `status: complete` with a verified network ledger, 0 failed assertions and 0 discrepancies in the independent
recomputation (section N of `tests/test_orchestrator.py`, which shares no code with `src/network`).
One reservation matters for reading the numbers: the **synthetic** results say how the accepted C3 system behaves on larger networks of
this construction. They are not statements about real shipping (limits below).

## What was asked, what was done

* **Phase A.** Baseline captured before editing (`00_baseline_protect/`): git state (HEAD `47bbdb9`, dirty working tree = the accepted C3 code,
  its source patch saved), every artifact a run overwrites, input hashes (they equal the frozen C3 reference's), C3 flags, solver (PuLP 2.7.0 /
  CBC 2.10.3, 120 s global budget), seed mechanism (`LINER_SEED`, reference used `PYTHONHASHSEED=0`).
* **Phase B.** Baltic and WAF extracted from `LINERLIB-master (1).zip` (the repository copy `data/LINERLIB-master` verified byte-identical, 76 files).
  Source rows are copied verbatim; the port set is derived from the source demand; every route alternative is preserved.
* **Phase C.** Registry (`src/data/dataset_registry.py`), `NetworkLoader(dataset=…)`, `test_orchestrator.py --dataset … | --datasets … | --list |
  --output-dir | --seed | menu on a terminal`. No prompt under pytest/CI/pipes/subprocesses; unknown or missing → clear error, never WorldSmall.
* **Phase D.** `scripts/multi_dataset/generate_synthetic.py` (deterministic, byte-identical regeneration verified, seed 20261016).
* **Mandatory JSON requirement.** One canonical `liner-shipping-problem` v1 file and manifest per dataset in `data/datasets/`, built through the
  loader (units converted once), validated, and proven identical to the CSV package at the start of every run.
* **Phases E–H.** Sequential runs, metrics, scalability measurements, regression tests.

You asked for new datasets in `data/raw/<name>` and JSON in `data/datasets` — that is exactly the layout used; WorldSmall's folder was not touched.

## Decisions worth knowing (and where I deviated from the literal text)

1. **Route alternatives.** The source `dist_dense.csv` has several records for 18,946 directed pairs (Suez/Panama/Cape). The accepted model takes ONE record
   per pair with its canal flags. WorldSmall's canonical file equals the *first listed* record of every pair; I verified that in the whole source this is also the
   *shortest* record (43,056 pairs, 0 exceptions, no tie with different flags). Baltic/WAF use that same verified rule and keep every record (all-alternatives file,
   `distance_alternatives` in the JSON). The model does not choose between alternatives — that would be a formulation change and was not made. Limitation: a class that
   cannot pass the shorter canal route (draft/blank fee) is excluded from the rotation instead of being routed around the Cape (unchanged accepted behaviour).
2. **Legacy JSON files kept.** `worldsmall_shipping_problem.json` (legacy x2 units, no fleet; the loader rejects it and an existing test asserts so) and
   `large_shipping_problem.json` were not regenerated, moved or deleted; the canonical files are the new `*_json.json`. No JSON data was copied from them.
3. **Per-dataset `fleet_data.csv`.** Loader contract: fleet quantity and class files must name the same classes. Baltic/WAF therefore carry the source rows of the two
   classes they use (byte-identical rows). No quantity or class value was invented.
4. **Transit limits** use the original `TransitTime` column, as the accepted WorldSmall configuration does; WAF's revised-transit file is stored (`Demand_WAF_tt.csv`) but unused.
5. **Economic outcomes are reported, not asserted, for non-WorldSmall datasets** (profit > 0, services > 0, …). Integrity assertions (ledger, units, feasibility, accounting) remain hard
   for every dataset; WorldSmall keeps every assertion.
6. **Dataset identity in outputs** lives in `test_scorecard.dataset_run` (the runner-added block), not in a new top-level key: the frozen output contract is unchanged.
7. **Synthetic design.** Ports anchor to real LINERLIB ports (position jitter, costs/draft from the anchor with measured within-country dispersion); distances = geodesic x the anchors'
   real routing circuity (canal flags and draft limits copied, integer nm rounded up so never below the geodesic); demand = sparse gravity network, volumes/rates/transit drawn by stratified
   quantile sampling from the pooled real instances (WorldLarge deliberately not used) and limited to the observed support; fleet = **WorldSmall's demand-per-vessel ratio and class mix**,
   identical rule for both sizes. Two defects of my first draft were found by checking the data before any optimizer run and fixed: demand-per-port differed 25% between the sizes
   (heavy-tail bootstrap variance → stratified sampling) and some volumes/rates left the observed support (clipped to it). The first draft's files are preserved in `data/raw/_backups/`.

## WorldSmall: unchanged, baseline reproduced

* `data/raw/WorldSmall` untouched; hashes equal the frozen C3 reference (tested); no file added to the folder; default loader still 47 / 1764 / 263.
* Three end-to-end runs through the new selection path (JSON source): profit 42.40 / 45.93 / 46.93 M USD/week, coverage 44.2 / 46.1 / 49.7 %, services 25 / 31 / 30,
  vessels assigned 167 / 173 / 182 of 263; all inside the frozen 20-seed C3 reference range (profit 31.8–47.1 M, coverage 30.1–47.9 %, vessels 93–201) except that coverage 49.7 % is
  0.2 pt above the frozen maximum 47.9 → within the owner's reported 43–50 %. Vessels assigned (167–182) are slightly above the owner's quoted 135–170 band for two of three runs.
  Three seeds are not a re-estimate of the 20-seed distribution; the owner's figures are reported, not independently verified here.
* Pre-existing regression tests: 214 passed before and after the loader change (plus 143 new).

## Tests
`pytest tests` on the final code (excluding the full-pipeline `tests/test_orchestrator.py::test_orchestrator`, which would overwrite the repo-root WorldSmall artifacts; WorldSmall's pipeline was run
through the driver instead): **1629 passed, 31 failed, 24 skipped, 9 xfailed** (log `logs/full_suite_final.log`).
* 30 failures: `tests/test_economic_metric_documentation.py` — they open `MULTI_AGENT_*.json/.md` audit artifacts that were never committed (`git log --all` finds none). Pre-existing, unrelated.
* 1 failure: `tests/architecture/test_output_contract.py::test_top_level_key_set_is_frozen`. It reads the repo-root `pipeline_output.json`, which was **overwritten at 14:29 by an unseeded 819 s WorldSmall run
  that did not come from my driver** (every driver run passes `--seed` and `--output-dir`; I believe you started it, e.g. to try the menu — I cannot verify that). That run used an earlier build of my
  code that still wrote a top-level `dataset_run` key. I fixed the code (identity moved into `test_scorecard`), verified on a fresh output (8/8 contract checks, no extra keys,
  `runs_verify/baltic_seed7`), and did **not** touch your artifact. To clear it: re-run the WorldSmall test, or restore the protected copy
  `cp reports/multi_dataset_20261016/00_baseline_protect/copies/pipeline_output.json pipeline_output.json` (same for `frontend/public/…`, `SYSTEM_TRUTH_REPORT.md`, `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md`).
  Side effect: that run overlapped WAF seeds 1–3 (14:16–14:29), so their wall times may be inflated.
* Regressions my changes caused and I fixed during the campaign (each found by the suite): `../WorldSmall` resolving to WorldSmall (path-like names now unknown); default loader capturing module paths at construction
  (tests re-point them; now read lazily); F-04 scan seeing fleet-cost names in `problem_json.py` (schema now introspects the dataclass); the seeding scan flagging the generator (allow-listed with a reason in
  `tests/test_economic_metric_documentation.py`).
* New: `tests/test_dataset_selection.py`, `tests/test_dataset_packages.py`, `tests/test_synthetic_datasets.py` (143 tests, 4 World-1000 duplicates skipped; set `LINER_FULL_VALIDATION=1` for World-1000's full validation, which the build already ran: 26/26).

Commands: `python -m pytest tests/test_dataset_selection.py tests/test_dataset_packages.py tests/test_synthetic_datasets.py -q` · `python -m pytest tests -q --deselect tests/test_orchestrator.py::test_orchestrator` ·
`python scripts/multi_dataset/run_campaign.py --datasets baltic WAF --seeds 0 1 2 3 4` · `python scripts/multi_dataset/collect_metrics.py` · `python scripts/multi_dataset/build_report_tables.py`.

---
# Results (generated by `scripts/multi_dataset/build_report_tables.py` from `runs/metrics.json`)

Machine: Windows 11, 16 logical CPUs, 15.7 GB RAM (about 4 GB free at the start), PuLP 2.7.0 / CBC 2.10.3, Python 3.11.9, one run at a time, `PYTHONHASHSEED=0`, `LINER_SEED` = seed. LLM providers were rate-limited during the
campaign, so the pipeline's documented deterministic fallbacks were used in places; with the wall-clock-limited CBC this means runs are not bit-reproducible. Memory: peak working set sampled every ~2 s (lower bound); Baltic, WAF
and WorldSmall seed 0 were run with an earlier sampler that measured the venv launcher stub, so their memory figures are omitted (n/a).

