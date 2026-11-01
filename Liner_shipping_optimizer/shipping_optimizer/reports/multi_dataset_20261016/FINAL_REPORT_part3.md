
---
# Analysis

## Regional datasets (real LINERLIB)
* **Baltic** (12 ports, 22 ODs, 6 vessels): +0.63 M USD/week (0.60–0.65), 61 % coverage, 3 services, 4–5 of 6 vessels deployed; the global MILP closed on its restricted set in under a second.
  Small networks have few options, so seed-to-seed variation comes from the regional GA/MILP/LLM stages, not from the global solve.
* **WAF** (20 ports, 37 ODs, 42 vessels): +5.03 M USD/week (4.93–5.18), 79 % coverage, 8–9 services, 30–31 of 42 vessels. Both profitable; neither was tuned (no cost, fleet, path or solver change).
* Expected low-signal items, not defects: a Baltic region with no services (reported as an outcome note), 0.50 productive load factor on WAF.

## Synthetic datasets — economics looked high, so it was checked
World-500/1000 profits (165 M / 194 M USD/week) are 4x WorldSmall's. Checked, not accepted at face value: the independent ledger recomputation agrees to the cent on every run (0 discrepancies);
revenue per served TEU is 1,067 / 1,021 USD against WorldSmall's 1,086 (same order); the cost mix is the same shape as WorldSmall's (handling + fuel + vessel hire dominate); the plans serve only
14 % / 10.5 % of a 2.7 M / 4.7 M TEU/week demand, i.e. the optimizer picks the lucrative lanes of a much larger demand pool; margin 38–40 % vs 32 %. So the figures are the correct arithmetic of the generated
inputs, and the generated inputs are the uncertain part (rates are distance-regressed from LINERLIB; the synthetic network has no real-world competition for capacity, ports or canals). Do not read them as
real-world profit.

## Scalability, World-500 → World-1000 (measured; see the scalability table)
* Inputs: ports x2.00, ODs x1.87, **distance records x4.00** (complete matrix, 249,500 → 999,000), demand x1.76.
* **Data loading grows super-linearly with the distance matrix** (6.3 → 22.6 s, x3.6; the JSON/CSV equivalence proof is a part of it) but is 3 % of the run.
* The **optimization workload does not grow like the inputs**: candidate services offered 2,762 → 2,934 (x1.06), MILP variables x1.82, constraints x1.80, global solver integer phase 83 → 79 s (it is bounded by
  the accepted 120 s budget; 1 of 3 runs per size hit the time limit), model + path build 12.3 → 11.2 s, pipeline total 574 → 715 s (**x1.25 for 2x the ports**), peak memory of the pipeline process
  0.58 → 1.09 GB (x1.9; all interpreter processes together: mean 0.77 / 1.25 GB, up to 1.15 / 1.57 GB), CBC peak 72 → 118 MB. Runtime did not double with the ports; the reason is the pipeline's fixed budgets and caps
  (candidate-generation budgets, 10 paths per OD, the 120 s solver budget), not a property of the problem.
* **Solution quality did not scale with the network**: coverage falls 14.4 % → 10.5 %; ODs without any path rise 9,710 → 24,761 (x2.55; 52 % → 70 % of ODs); services 74 → 86; vessels assigned 727 → 893 of 2,570 / 4,514
  (deployment ratio 0.28 → 0.20). Because the candidate pool barely grows while the OD set doubles, a larger share of demand has no candidate path. The path model's recorded reasons are
  the transit-time limit (9,210 / 17,151 ODs) and no connection (539 / 7,636). I did not isolate whether transit limits, pool size or both cause this (that would need experiments on the generation settings, which are
  frozen for C3); treat "the WorldSmall-calibrated candidate generation under-serves a 1000-port network" as the measured symptom, not a proven cause.
* Gap to the LP bound of the capped model: 24 % (World-500) and 41 % (World-1000) vs 7–12 % on the regional sets; it is not an optimality gap of the final plan and no plan is claimed optimal.

## Which runs failed, timed out, or were weak
* Failed / infeasible / no incumbent / killed: **none**. Global-model time limit reached: WorldSmall 3/3 (as in the accepted baseline), World-500 1/3, World-1000 1/3.
* An earlier WorldSmall feedback iteration logged `global_reconciliation_failed (Not Solved)`; the pipeline recovered in a later iteration and the final plan is verified (seed 0 log).
* Weak economics: none negative. Lowest is Baltic (0.6 M; tiny network). Weak *coverage* is the synthetic pair (10–14 %).

## Limits on any claim of real-world scalability
1. Synthetic data: positions are not coastline-checked, distances are approximations, one distance record per pair, demand/rates are bootstrapped from six small LINERLIB instances; the fleet rule copies WorldSmall's demand-per-vessel ratio.
2. One random population (seed 20261016) and 3 seeds per size; single machine (16 CPUs, 15.7 GB, one run at a time); time-limited CBC and rate-limited LLM fallbacks make runs non-bit-reproducible.
3. Two sizes only (500, 1000): a growth *factor* between two points, not a scaling law.
4. The pipeline's budgets/caps are frozen for C3 (by instruction), so the scaling observed is that of this configuration, not of the underlying problem; coverage on the larger networks says the configuration was calibrated for 47 ports.
5. Model size is the final global MILP only (regional stage MILPs are smaller and reported per call in `dataset_run.global_milp_calls`); candidate-rejection counts by constraint of the service generator and the solver subprocess memory are not exposed by the pipeline (listed as `not_exposed` in the metrics).
6. WorldSmall-reference figures are the owner's, reported not independently verified; three seeds do not re-estimate them.

# Deliverables and where they are
| deliverable | location |
|---|---|
| Baltic / WAF packages | `data/raw/baltic`, `data/raw/WAF` (+ `reports/multi_dataset_20261016/01_regional_extraction/`) |
| World-500 / World-1000 + generation manifests | `data/raw/World-500`, `data/raw/World-1000` (`generation_manifest.json`) |
| Canonical JSON + manifests (5) | `data/datasets/*_json.json`, `*_manifest.json` (previous builds in `data/datasets/_backups/`) |
| Selection interface | `tests/test_orchestrator.py` (`--dataset`, `--datasets`, `--list`, `--seed`, `--output-dir`, menu), `src/data/dataset_registry.py` |
| Tests | `tests/test_dataset_selection.py`, `test_dataset_packages.py`, `test_synthetic_datasets.py` |
| Run artifacts and logs | `reports/multi_dataset_20261016/runs/<dataset>/seed<S>/` (`pipeline_output.json`, `run.log`, `driver_record.json`, `run_metadata.json`), `logs/`, `runs/metrics.json`, `runs/tables.md` |
| Provenance report | `reports/multi_dataset_20261016/PROVENANCE_REPORT.md` (paths, hashes, counts, validation per dataset, real vs synthetic, source defects) |
| Baseline protection | `reports/multi_dataset_20261016/00_baseline_protect/` |
| How-to | `docs/MULTI_DATASET.md` |

## Changed / new files
New (code): `src/data/dataset_registry.py`, `src/data/dataset_validation.py`, `src/data/problem_json.py`, `scripts/multi_dataset/{protect_baseline,extract_regional,generate_synthetic,build_problem_json,run_campaign,collect_metrics,build_report_tables,build_provenance_report}.py`,
`tests/test_dataset_selection.py`, `tests/test_dataset_packages.py`, `tests/test_synthetic_datasets.py`, `docs/MULTI_DATASET.md`.
New (data, git-ignored by `data/*`): `data/raw/{baltic,WAF,World-500,World-1000}/`, `data/raw/_backups/`, `data/datasets/{baltic,waf,world500,world1000,worldsmall}_{json,manifest}.json`, `data/datasets/_backups/`.
Modified: `src/data/network_loader.py` (optional `dataset=` argument, lazy path properties; default behaviour and messages for WorldSmall unchanged; +61/-30), `tests/test_orchestrator.py` (selection, per-dataset oracle input,
outcome policy, output isolation, model-size recorder, CLI; WorldSmall assertions unchanged), `tests/test_economic_metric_documentation.py` (seeding allow-list entry for the generator).
Not mine (pre-existing uncommitted work, untouched): `src/network/{network_milp,plan,reconcile,trunk_candidates}.py`, the archived experimental modules, the pipeline artifacts at the repo root (see the 14:29 note).
`data/raw/WorldSmall` and `data/datasets/{worldsmall,large}_shipping_problem.json`: not modified.

## Rollback (commands for you to run; I deleted and reverted nothing)
```
git show HEAD:Liner_shipping_optimizer/shipping_optimizer/src/data/network_loader.py > src/data/network_loader.py     # loader to HEAD
git diff HEAD -- tests/test_orchestrator.py tests/test_economic_metric_documentation.py > multi_dataset_test_changes.patch  # keep/inspect
# pre-campaign test_orchestrator.py (it already had your uncommitted edits): reports/multi_dataset_20261016/00_baseline_protect/copies/tests/test_orchestrator.py.pre_multi_dataset
# new code and data are additive: remove  src/data/{dataset_registry,dataset_validation,problem_json}.py  scripts/multi_dataset/  tests/test_dataset_*.py tests/test_synthetic_datasets.py
#   data/raw/{baltic,WAF,World-500,World-1000,_backups}  data/datasets/*_json.json (except the two historical *_shipping_problem files) data/datasets/*_manifest.json data/datasets/_backups
# repo-root artifacts overwritten at 14:29: restore from reports/multi_dataset_20261016/00_baseline_protect/copies/
```
