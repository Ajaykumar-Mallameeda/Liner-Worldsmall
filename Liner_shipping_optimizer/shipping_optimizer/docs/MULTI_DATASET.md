# Multi-dataset support (WorldSmall, baltic, WAF, World-500, World-1000)

One selected dataset -> one explicit source package -> one validated canonical JSON -> one isolated execution -> one isolated result set.

| key | kind | source package (`data/raw/…`) | canonical JSON (`data/datasets/…`) | manifest | run outputs |
|---|---|---|---|---|---|
| `WorldSmall` | LINERLIB | `WorldSmall/` (pre-existing, never rewritten) | `worldsmall_json.json` | `worldsmall_manifest.json` | legacy locations (repo root, `frontend/`) unless `--output-dir` |
| `baltic` | LINERLIB | `baltic/` | `baltic_json.json` | `baltic_manifest.json` | `reports/dataset_runs/baltic/` |
| `WAF` | LINERLIB | `WAF/` | `waf_json.json` | `waf_manifest.json` | `reports/dataset_runs/WAF/` |
| `World-500` | synthetic | `World-500/` | `world500_json.json` | `world500_manifest.json` | `reports/dataset_runs/World-500/` |
| `World-1000` | synthetic | `World-1000/` | `world1000_json.json` | `world1000_manifest.json` | `reports/dataset_runs/World-1000/` |

`src/data/dataset_registry.py` is the only place that maps a name to paths. Names are case-insensitive, `-`/`_`/spaces are
ignored (`world 500`, `WORLD_500`, `w500`), anything path-like is unknown. There is no fallback: a missing input or JSON
is an error naming the file.

## Running
```
python tests/test_orchestrator.py --list
python tests/test_orchestrator.py --dataset baltic --seed 0 --output-dir <dir>      # explicit, never prompts
python tests/test_orchestrator.py                                                   # terminal: numbered menu; otherwise WorldSmall
python tests/test_orchestrator.py --datasets baltic WAF --seed 0                    # batch: sequential, one process each
python scripts/multi_dataset/run_campaign.py --datasets baltic WAF --seeds 0 1 2    # seeds x datasets, records wall time + memory
```
`pytest tests/test_orchestrator.py` runs WorldSmall (or `LINER_DATASET=<name>`), never a prompt. The selection changes which
inputs are loaded and where outputs go; it does not change the solver, the economics or the C3 flags.
For non-WorldSmall datasets economic *outcomes* (profit > 0, services > 0) are reported, not asserted; integrity checks
(ledger, units, feasibility, accounting) stay hard assertions. WorldSmall keeps every assertion.

## Building the packages
```
python scripts/multi_dataset/extract_regional.py --zip "<LINERLIB-master.zip>"     # baltic, WAF  (source files, verbatim rows)
python scripts/multi_dataset/generate_synthetic.py [--check | --replace]           # World-500, World-1000 (seed 20261016)
python scripts/multi_dataset/build_problem_json.py --dataset all [--check]         # canonical JSON + manifest + validation
python scripts/multi_dataset/protect_baseline.py                                   # Phase A snapshot of the WorldSmall/C3 baseline
```
Existing differing files are never overwritten silently: `--replace` copies them to a `_backups` folder first.

## Canonical JSON (schema `liner-shipping-problem` v1, `src/data/problem_json.py`)
Keeps the legacy keys `ports`, `demands`, `services`, `distance_matrix` and their field names and adds `schema`,
`schema_version`, `dataset` (identity), `units`, `canal_flags`, `edge_draft`, `distance_alternatives`, `fleet`,
`provenance`. Values are stored after the loader-boundary conversion (1 FFE = 2 TEU applied once, when the file is built).
At the start of every run the JSON is loaded from the dataset's own path and proven identical (every field, in order) to the
Problem its own CSV package produces; the run records both hashes.

The historical files `data/datasets/worldsmall_shipping_problem.json` (legacy x2 unit convention, no fleet; the loader
rejects it and `tests/test_worldsmall_integration.py` asserts that) and `large_shipping_problem.json` (discarded, unsuitable
data) are kept untouched, are not canonical and are never loaded by the selection.

## Route alternatives and canal fees
`dist_dense.csv` of LINERLIB lists several records for some pairs (Suez / Panama / around the Cape). The accepted model takes
ONE record per directed pair with its canal flags; WorldSmall's file is the first listed record, which in the whole source is
also the shortest. Baltic/WAF apply the same rule (verified by the extraction, not assumed) and keep every record
(`dist_dense_all_alternatives.csv`, `distance_alternatives` in the JSON). Canal fees and draft limits are charged by the
unchanged accepted rules (`src/network/physical_rules.py`).

## Synthetic datasets
See `data/raw/World-<N>/generation_manifest.json` (every parameter, calibration statistic, input hash, the fleet rule and the
limitations) and the header of `scripts/multi_dataset/generate_synthetic.py`. They are synthetic benchmarks calibrated on
LINERLIB, not observations; positions are not checked against coastlines and distances are approximations.
