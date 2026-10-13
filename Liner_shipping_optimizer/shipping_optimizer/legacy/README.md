# Legacy Archive — README

This directory contains **historical engineering artifacts** from the
AI Vessel Routing System. They are **not** part of the product and are
**not** required for the system to run, but they are preserved for
reference and forensic reasons.

> This is an archive. Move things out of `legacy/` only if you have
> decided they belong back in the product tree.

---

## Why this directory exists

After a complete repository archaeology (see
`../REPOSITORY_CLEANUP_AUDIT.md`, `../REPOSITORY_FILE_CATALOG.csv`,
`../REPOSITORY_RUNTIME_MAP.md`, `../REPOSITORY_DECISION_QUEUE.md`),
the working tree was partitioned into three buckets:

- 🟢 **KEEP** — the product tree (still in place at the repo root).
- 🔵 **ARCHIVE** — private engineering history (this directory).
- 🔴 **DELETE** — confirmed residue (removed at cleanup time).

This `legacy/` directory is the 🔵 ARCHIVE bucket.

The intent: a clean working tree for the user, but the engineering
history is preserved (not deleted) so it can still be inspected.

---

## Contents

| Path | Origin | What it is |
| --- | --- | --- |
| `legacy/Analysis/` | `Analysis/` | Historical engineering analyses (V1 backend freeze certification, validator rejection analysis, algorithm correctness cert, etc.). |
| `legacy/Implemented-plans/` | `Implemented-plans/` | Past sprint / phase implementation plans that have been delivered. |
| `legacy/RuntimeIntegrity/` | `RuntimeIntegrity/` | Runtime integrity reports and validation matrix from earlier program phases. |
| `legacy/research/` | `research/` | Research notes on algorithm selection, trade-off analysis, prior experiments. |
| `legacy/docs-archive/` | repo root (`*.md`, `reference.docx`) | CCEOS-related reports, runtime bibles, AI layer / architecture / code reference docs, master technical documentation, CLAUDE configuration audit, reference template spec/README/docx. |
| `legacy/backend/main_backup.py` | `backend/main_backup.py` | Snapshot of an earlier `backend/main.py`; the active backend is `backend/unified_main.py`. |
| `legacy/_legacy/` | `_legacy/` | Earlier runtime artifacts (server.log, run scripts, an HTML explainer, the "Profit calculation" PDF, an old SQLite DB). |
| `legacy/images/` | `images/` | Mermaid PNG renders generated for documentation. |
| `legacy/raw_responses/` | `raw_responses/` | Captured raw LLM responses used during development. |
| `legacy/scripts/` | `scripts/` | Doc-generation and forensic/investigative scripts that are no longer needed to run the system. Includes the master-doc converter (`.bat`/`.ps1`/`.sh`/`.py`), mermaid extraction/fix scripts, append_ai_doc, caption_map, regional intelligence audit, sg_forensic_trace, trace_deep, regional policy mapping gen, etc. |
| `legacy/logs/` | `logs/` | 1,480 historical `app_*.log` files and 324 files in `llm_forensics/` (raw prompts/responses/validation from prior runs). `.gitkeep` is preserved. |
| `legacy/frontend-evaluation_output.json` | `frontend/evaluation_output.json` | Historical frontend evaluation snapshot. |

---

## Items NOT archived (kept in product tree)

These items were originally on the candidate-delete list but were
**kept** because they are still actively imported or generated:

- `src/validation/regional_policy_validator.py` (v1) — still imported by
  `src/validation/__init__.py:3`, `regional_policy_validator_v2.py:28`,
  `consensus_engine.py:44`, `regional_agent.py:13`, and three test files.
  v2 is the active validator but v1 remains part of the contract; archiving
  it would break active imports. The cleanup decision was to **keep** it.

To retire v1 properly, the callsite imports must be migrated from v1 to v2,
then v1 can be moved here.

---

## Verification

The cleanup that produced this directory:

1. Pre-step: a safe `.env.example` was added (no secrets were committed to
   the Git index — verified via `git ls-files` and `git log --all -- .env`).
2. DELETE phase: empty scaffolding directories (`backend/{cache,config,monitoring,validation}/`,
   the 13 empty subdirs under `backend/src/`, `benchmark/`, `data/processed/`,
   `tests/{integration,load}/`), `_tmp_sel_test.py`, and two stale
   `pipeline_output.json` copies under `frontend/{public,dist}/` were removed.
3. ARCHIVE phase: this directory was populated by moving (not deleting)
   items per the user's tri-bucket strategy.
4. Logs and forensic traces were moved here intact (67 MB / 1,804 files).
   They are gitignored and excluded from working tree.

See `../REPOSITORY_CLEANUP_AUDIT.md` for full evidence and the
four-document inventory.
