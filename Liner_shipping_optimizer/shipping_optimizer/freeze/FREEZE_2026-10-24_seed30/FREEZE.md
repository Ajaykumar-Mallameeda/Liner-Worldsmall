# Freeze 2026-10-24: engine config + 30-seed benchmark

Taken before frontend work starts. Nothing in the repo was changed, committed or moved to make it.

| file | what it is |
|---|---|
| `manifest.json` | git HEAD `47bbdb9` on `campaign/20261013-issues-1-8` (86 uncommitted paths), Python 3.11.9, Node 24.14.0, hash of `src/config/optimizer_config.py`, hashes of the seed-30 summaries |
| `working_tree_vs_HEAD.patch` | every uncommitted change to tracked files (`git diff HEAD --binary`) |
| `code_snapshot.tar.gz` | all code as it stands, untracked files included: `src/ backend/ scripts/ tests/ frontend/src frontend/tests`, configs, the benchmark driver scripts, and both `pipeline_output.json` copies |
| `code_sha256.json` / `data_sha256.json` | SHA-256 per code file (365) and per input-data file under `data/raw`, `data/datasets` (78) |
| `benchmark_seed30_sha256.json` | SHA-256 + size of all 1,057 files in `Benchmark/seed-30/` (the run artifacts are not copied; 219 MB) |
| `pip_freeze.txt`, `git_status.txt` | environment and tree state |

## Rebuild the frozen code

```
git checkout 47bbdb92fee93b1a07f769f9306f47131d1b9611
git apply --binary freeze/FREEZE_2026-10-24_seed30/working_tree_vs_HEAD.patch
```

Untracked files are not in the patch. Unpack `code_snapshot.tar.gz` over the tree to get them.

## Check that nothing has drifted

Recompute the hashes and compare them with `code_sha256.json` and `benchmark_seed30_sha256.json`. Any file whose hash differs has changed since the freeze.
