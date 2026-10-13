# Issue 0 - recoverable version-control baseline (2026-10-13)

Application behaviour: **unchanged** (no source, test, config or data file was edited).

## Verified independently
* Git root `C:\Users\WINDOWS\Liner-Worldsmall`; project `Liner_shipping_optimizer/shipping_optimizer` nested and untracked.
* `main` = `74bf7701b560959a4ec0aeb5e322051802fa9a95`, whose tree is the empty tree `4b825dc6...`; 0 tracked files; no stash; only branch `main` (+ `origin/main`).

## What was done
* New branch `baseline/t11-20261013` (from `main`; `main` untouched).
* Commit `95b8c74` - 1,572 files = snapshot `snap_T11_final` (manifest sha256 `3702d740...683b`, 1,582 entries) minus `.env` (secrets) and the 9 `data/raw/WorldLarge` files (out of scope).
  Includes `data/raw/WorldSmall/*` (force-added; the project .gitignore hides it). Tag `baseline-t11-20261013` points here.
* Commit `259d379` - 2,188 report/evidence files not in the manifest (campaign 2026-10-12 evidence, `reports/audit_20261013_phaseADB`), force-added past `*_REPORT.md`, `*_SUMMARY.md`, `*.csv` ignore rules.
* The project's own `.gitignore` files were not edited.

## Verification
* Live tree vs manifest: 1,579 / 1,582 byte-identical. The 3 that differ are the files overwritten by the out-of-campaign orchestrator run (`P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md`, `SYSTEM_TRUTH_REPORT.md`, `frontend/public/pipeline_output.json`); they are committed as found.
* `git archive 95b8c74` extracted to a fresh scratch directory: 1,572 / 1,572 files equal the live tree and 1,572 / 1,572 manifest entries (line endings normalised; `core.autocrlf=true`, so blob hashes differ from manifest hashes by CRLF only).
* `git diff` on tracked files is empty after the commits.

## Not tracked (deliberate, still on disk)
`.env`, `data/raw/WorldLarge`, `venv/`, `frontend/node_modules/`, caches, `logs/`, `optimization_results.db`, `data/maritime/snapshots` test stubs, `Liner_shipping_optimizer.zip`, and files in `Liner_shipping_optimizer/` outside `shipping_optimizer/`.

## Rollback / restore (non-destructive)
* Compare: `git diff baseline-t11-20261013 -- Liner_shipping_optimizer/shipping_optimizer/src`
* Restore a single file: `git show baseline-t11-20261013:Liner_shipping_optimizer/shipping_optimizer/<path> > <path>`
* Whole tree to a new directory: `git archive baseline-t11-20261013 Liner_shipping_optimizer/shipping_optimizer | tar -x -C <new empty dir>`
* Undo the baseline itself: `git checkout main` (leaves all files in place); the branch/tag can stay.
