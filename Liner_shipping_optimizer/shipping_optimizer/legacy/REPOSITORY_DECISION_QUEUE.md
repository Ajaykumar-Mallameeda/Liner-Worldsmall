# REPOSITORY DECISION QUEUE — Human Review Required

This is the human-reviewable companion to the master audit. Each item is grouped by the recommended action and includes evidence and confidence.

**Action legend:**

* **KEEP** — file is required at runtime, deployment, or for documentation/provenance.
* **MOVE TO PRIVATE ARCHIVE** — file is not runtime-required but has provenance, IP, or historical value.
* **DELETE** — file is evidence-supported dead/redundant; safe to remove.
* **CONSOLIDATE** — file has a duplicate; merge and archive the redundant copy.
* **INVESTIGATE** — file's role is unclear from static evidence; needs human review.
* **IP/LEGAL REVIEW** — file may be IP/patent-sensitive; needs review before any public release.
* **HIGH RISK** — file contains or references secrets, foreign code, or other risk; needs immediate attention.

---

## A. KEEP / CONFIDENT (no action)

These files are required at runtime, deployment, or for authoritative user-facing documentation.

| Path | Purpose | Why KEEP | Confidence |
| --- | --- | --- | --- |
| `src/**` | Core runtime (agents, optimization, llm, validation, pipeline, data, services, decomposition, utils) | Live runtime; called by `tests/test_orchestrator.py` and indirectly by the backend. | High |
| `tests/test_orchestrator.py` | Runtime driver | The sole producer of `pipeline_output.json` per audit prompt. | High |
| `tests/test_iteration_selection.py` | PROJECT X iteration selection tests | Required for iteration correctness. | High |
| `tests/test_multi_agent_coordination.py` | Multi-agent coordination tests | Required for orchestration correctness. | High |
| `tests/test_regional_agent_activation.py` | Regional activation tests | Required for regional agents. | High |
| `tests/test_service_generator_activation.py` | Service generator activation tests | Required. | High |
| `tests/test_regional_policy_validator_v2.py` | Regional policy validator tests | Required. | High |
| `tests/test_ga.py`, `tests/test_milp.py`, `tests/test_clustering.py`, `tests/test_data_loader.py`, `tests/test_regional_agent.py`, `tests/test_service_generation.py`, `tests/test_setup.py`, `tests/test_llm.py` | Smaller test modules | Required. | High |
| `backend/unified_main.py` | Active unified FastAPI server | Authoritative entry per its docstring. | High |
| `backend/routes/{pipeline,metrics,regions,websocket}.py` | HTTP + WS routes | Required. | High |
| `backend/services/{pipeline_service,optimization_service}.py` | Service layer | Required. | High |
| `backend/real_orchestrator_integration.py` | Real-orchestrator driver | Used by the live dashboard for re-runs. | High |
| `backend/websocket_manager.py`, `backend/event_validator.py`, `backend/event_schemas.py`, `backend/api_models.py`, `backend/models/schemas.py` | WS/event support | Required. | High |
| `frontend/src/**` | React dashboard | Live frontend. | High |
| `frontend/index.html`, `frontend/package.json`, `frontend/postcss.config.js`, `frontend/tailwind.config.js`, `frontend/vite.config.js` | Frontend build | Required. | High |
| `frontend/public/vite.svg` | Vite asset | Required. | High |
| `docs/**` | User-facing documentation | Authoritative. | High |
| `data/datasets/*` | Datasets | Required by `tests/test_orchestrator.py`. | High |
| `data/raw/{ports,port_mapping,demand_world_large,distance_dense,fleet_world_large}.csv` | Raw data | Required. | High |
| `Dockerfile`, `requirements.txt` | Build/deps | Required. | High |
| `README.md`, `CHANGELOG.md`, `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CITATION.cff` | Standard docs | Required for open-source / GitHub. | High |
| `src/README.md` | src/ doc | Required. | High |
| `pipeline_output.json` (root) | Runtime truth | Required by backend. | High |
| `frontend/mock-server.cjs` | Dev mock | Required for frontend dev. | High |
| `frontend/test_api.js` | Frontend API test | Required. | High |
| `src/validation/regional_policy_validator_v2.py` | Active validator v2 | Required. | High |
| `assets/architecture/*.svg` | Architecture diagrams | Authoritative docs. | High |
| `assets/dashboard/*.png` (most) | Dashboard screenshots | Documentation. | High |
| `assets/benchmarks/*.png` | Benchmark screenshots | Documentation. | High |
| `assets/runtime/*.svg` | Runtime diagrams | Documentation. | High |
| `SYSTEM_TRUTH_REPORT.md` | Active truth | Authoritative. | High |
| `REPOSITORY_FINALIZATION_REPORT.md` | Finalization summary | Authoritative. | High |
| `frontend/dist/index.html` | Vite build output | Required (live). | High |
| `frontend/dist/vite.svg` | Vite asset in build | Required (live). | High |
| `frontend/dist/assets/index-66d7e027.js` | Built JS | Required (live). | High |
| `frontend/dist/assets/index-d2de4eda.css` | Built CSS | Required (live). | High |
| `free-claude-code/` | Third-party Claude Code fork | Gitignored; not part of the project. KEEP only because gitignored — do not bring into tree. | High |
| `graphify-out/` | Graphify tool cache | Gitignored. | High |
| `venv/` | Python virtualenv | Gitignored. | High |
| `.claude/`, `frontend/.claude/` | Per-user tool state | Ignored. | High |

---

## B. MOVE TO PRIVATE ARCHIVE

These files are not runtime-required but have provenance, IP, or historical value. Recommended to move out of the working tree into a private archive after this audit is reviewed.

| Path | Purpose | Why archive | Confidence |
| --- | --- | --- | --- |
| `Analysis/` (47 files) | Investigation, audit, certification, recovery, truth, scoring reports. | Provenance, IP — not runtime. | High |
| `Implemented-plans/PHASE_1_IMPLEMENTATION_REPORT.md` | Phase 1 implementation report. | Historical plan. | High |
| `Implemented-plans/PHASE_2_IMPLEMENTATION_REPORT.md` | Phase 2 implementation report. | Historical plan. | High |
| `Implemented-plans/RESEARCH_BENCHMARK_REPORT.md` | Research benchmark report. | Historical. | High |
| `research/coordinator_audit/` (7 + 1 files) | Coordinator reasoning audit. | Provenance. | High |
| `research/worldxl/reports/WORLDXL_1000_EXPANSION_MASTER_PLAN.md` | Expansion plan. | Provenance. | High |
| `research/worldxl/reports/WORLDXL_DATA_MODEL_AND_ACQUISITION_PLAN.md` | Data model plan. | Provenance. | High |
| `CCEOS_IMPLEMENTATION_SPECIFICATION.md` | CCEOS implementation spec. | Provenance. | High |
| `CCEOS_KNOWLEDGE_CONSOLIDATION_REPORT.md` | CCEOS knowledge consolidation. | Provenance. | High |
| `CCEOS_KNOWLEDGE_MIGRATION_VERIFICATION.md` | CCEOS knowledge migration verification. | Provenance. | High |
| `CCEOS_REPOSITORY_PREPARATION_REPORT.md` | CCEOS repository preparation. | Provenance. | High |
| `CCEOS_V1_CERTIFICATION_REPORT.md` | CCEOS v1 certification. | Provenance. | High |
| `RUNTIME_BIBLE.md` | Runtime bible. | Provenance. | High |
| `RUNTIME_KNOWLEDGE_GRAPH.md` | Runtime knowledge graph. | Provenance. | High |
| `MASTER_TECHNICAL_DOCUMENTATION.md` (V1) | Master docs v1. | Superseded by V2. | High |
| `MASTER_TECHNICAL_DOCUMENTATION_V2.md` | Master docs v2. | Provenance / consolidation candidate. | High |
| `AI_LAYER_REFERENCE.md` | AI layer reference. | Provenance. | High |
| `ARCHITECTURE_REFERENCE.md` | Architecture reference. | Provenance. | High |
| `CODE_REFERENCE.md` | Code reference. | Provenance. | High |
| `CLAUDE_CONFIGURATION_AUDIT.md` | Tooling audit. | Provenance. | High |
| `REFERENCE_TEMPLATE_DESIGN_SPECIFICATION.md` | Reference template design. | Tooling. | High |
| `README-reference-template.md` | Reference template README. | Tooling. | High |
| `reference.docx` | Reference template DOCX. | Tooling. | High |
| `images/mermaid_*.png` (10 PNGs) | Mermaid-generated diagrams. | Tooling output. | High |
| `scripts/append_ai_doc.py`, `scripts/append_ai_doc_part2.py` | Doc-generation scripts. | Tooling. | High |
| `scripts/convert_master.bat`, `.ps1`, `.sh` | Doc conversion. | Tooling. | High |
| `scripts/dump_mermaid.py`, `scripts/extract_mermaid_contexts.py`, `scripts/fix_mermaid.py` | Mermaid doc scripts. | Tooling. | High |
| `scripts/generate_ai_diagrams.py`, `scripts/generate_architecture_diagrams.py` | Diagram generators. | Tooling. | High |
| `scripts/postprocess_docx.py`, `scripts/preprocess_markdown.py` | DOCX/MD doc tools. | Tooling. | High |
| `scripts/caption_map.py` | Caption mapping. | Tooling. | High |
| `scripts/investigate_svcgen.py`, `scripts/sg_forensic_trace.py`, `scripts/sg_intermittent_test.py` | Service-gen investigation. | Tooling. | High |
| `scripts/json_capability_test.py` | JSON capability test. | Tooling. | High |
| `scripts/phase_p0_influence_analysis.py` | Phase P0 influence analysis. | Tooling. | High |
| `scripts/regional_differentiation_report.py` | Regional differentiation report. | Tooling. | High |
| `scripts/regional_intelligence_audit.py` | Regional intelligence audit. | Tooling. | High |
| `scripts/regional_policy_mapping_gen.py` | Regional policy mapping generator. | Tooling. | High |
| `scripts/test_fix_minimal.py` | Test fix minimal. | Tooling. | High |
| `scripts/test_with_stale_state.py` | Test with stale state. | Tooling. | High |
| `scripts/trace_deep.py` | Deep trace. | Tooling. | High |
| `scripts/trace_llmclient.py` | LLM client trace. | Tooling. | High |
| `scripts/verify_fix_loaded.py` | Verify fix loaded. | Tooling. | High |
| `scripts/check_exec_summary.py` | Exec summary check. | Tooling. | High |
| `raw_responses/` (7 JSONs) | Raw LLM responses from an evaluation. | Tooling output. | High |
| `frontend/evaluation_output.json` | Frontend evaluation snapshot. | Not consumed at runtime. | High |
| `logs/` (1,168 app log files) | Per-run application logs. | Tooling/debugging. | High |
| `logs/llm_forensics/` (324 files) | LLM call transcripts. | Tooling/debugging. | High |
| `_legacy/` (7 files: optimization_results.db, server.log, Profit calculation.pdf, run_test.sh, start_live_dashboard.bat, vessel_routing_explainer_.html, vessel_routing_explainer_v2 (1).html) | Early-version artifacts. | Historical. | High |
| `RuntimeIntegrity/*.md` (5 files) | Runtime integrity report set. | Provenance. | High |
| `backend/main_backup.py` | Snapshot of `main.py`. | Historical. | High |
| `src/validation/regional_policy_validator.py` | v1 of regional policy validator; v2 is active. | Historical. | High |

---

## C. DELETE CANDIDATES

Strong-evidence dead/redundant. **No action was taken in this audit.** Recommended only after human review.

| Path | Evidence | Why delete | Confidence |
| --- | --- | --- | --- |
| `_tmp_sel_test.py` | Docstring: *"Temporary synthetic test for IterationSelector — removed before final."* | Stale temp file. | High |
| `frontend/public/pipeline_output.json` | Stale snapshot, **differs** from root; not consumed by any runtime file. | Drift hazard. | High |
| `frontend/dist/pipeline_output.json` | Stale snapshot, **differs** from root; not consumed by any runtime file. | Drift hazard. | High |
| `frontend/.claude/` | Empty frontend-local tool config; tracked but unused. | Empty. | High |
| `backend/cache/`, `backend/config/`, `backend/monitoring/`, `backend/validation/` | Empty (no files). | Empty scaffold. | High |
| `backend/src/` and 14 subdirectories under it | All empty. | Empty scaffold. | High |
| `benchmark/` | Empty. | Empty scaffold. | High |
| `data/processed/` | Empty. | Empty scaffold. | High |
| `tests/integration/`, `tests/load/` | Empty. | Empty scaffold. | High |
| `.obsidian/core-plugins.json` | Empty file (0 bytes); not consumed. | Empty. | High |
| 1,168 `logs/app_*.log` | Not referenced by any source file. | Debugging-only, not runtime. | High (after `logs/` is gitignored — note: currently gitignored already) |
| `assets/dashboard/landing-dashboard.png` | Per PROJECT X remediation, landing component was removed. Asset is documentation-only. | Not referenced by code. | Medium — confirm with maintainer before delete. |
| `assets/dashboard/export-centre.png` | UK spelling — likely duplicate of `export-center.png`. | Possible duplicate. | Medium |
| `frontend/dist/assets/index-66d7e027.js.map` | Source map. | Usually gitignored. | Medium |

---

## D. CONSOLIDATION CANDIDATES

These pairs likely represent the same intent; merge and archive the redundant copy.

| A | B | Recommended action | Confidence |
| --- | --- | --- | --- |
| `backend/unified_main.py` | `backend/main.py` | Pick `unified_main.py`; archive `main.py` (and `main_backup.py`). | High |
| `backend/unified_main.py` | `backend/server.py` | Pick `unified_main.py`; archive `server.py`. | High |
| `backend/main.py` | `backend/main_backup.py` | Pick `main.py` (or `unified_main.py`); archive the other. | High |
| `backend/pipeline_streamer.py` | `backend/services/pipeline_streamer.py` | Investigate; if one is a true duplicate, archive it. | Medium |
| `MASTER_TECHNICAL_DOCUMENTATION.md` (V1) | `MASTER_TECHNICAL_DOCUMENTATION_V2.md` | Consolidate; V2 is likely canonical. | High |
| `src/validation/regional_policy_validator.py` | `src/validation/regional_policy_validator_v2.py` | v2 is active; archive v1. | High |
| `_legacy/vessel_routing_explainer_.html` | `_legacy/vessel_routing_explainer_v2 (1).html` | Move both to archive; v2 supersedes v1. | High |
| `Analysis/PROMPT_INFLUENCE_BASELINE.md` | `Analysis/PROMPT_INFLUENCE_MASTER_REPORT.md` | Consolidate; keep master. | Medium |
| `Analysis/JSON_PARSE_FAILURE_ANALYSIS.md` | `Analysis/JSON_CAPABILITY_VERIFICATION_REPORT.md` | Consolidate. | Medium |
| `Analysis/COORDINATOR_FORENSIC_TRACE.md` | `Analysis/COORDINATOR_INFLUENCE_REPORT.md` | Consolidate. | Medium |
| `Analysis/PROMPT_INFLUENCE_MASTER_REPORT.md` | `Analysis/PHASE_P_PROMPT_TRUTH_AUDIT_MASTER_REPORT.md` | Possibly overlapping. | Low |
| `frontend/src/components/optimization/FleetDashboard.jsx` | `frontend/src/components/optimization/FleetPanel.jsx` | Likely single owner. | Medium |
| `frontend/src/components/optimization/PipelineView.jsx` | `frontend/src/components/optimization/PipeNode.jsx` + `RegionPipelineNode.jsx` | Verify single owner. | Medium |
| `frontend/src/components/optimization/ConflictView.jsx` | `frontend/src/components/optimization/FeedbackView.jsx` | Verify single owner. | Medium |

---

## E. IP / LEGAL REVIEW

These files are likely IP/patent-sensitive and **must** be reviewed before any public release or patent filing.

| Path | Why |
| --- | --- |
| All of `src/` | Core algorithmic and architectural implementation. |
| `data/datasets/*` | Data model; verify if synthetic or proprietary. |
| `data/raw/*` | Verify if synthetic or proprietary. |
| `docs/ARCHITECTURE.md`, `docs/SYSTEM_ARCHITECTURE.md` | Architectural disclosure. |
| `Analysis/*` | Architectural / decision-logic disclosure. |
| `Implemented-plans/*` | Claims / plans. |
| `research/coordinator_audit/*` | Decision logic audit. |
| `research/worldxl/reports/*` | Expansion plans. |
| `CCEOS_*` | CCEOS architecture / migration. |
| `MASTER_TECHNICAL_DOCUMENTATION*` | Master technical disclosure. |
| `AI_LAYER_REFERENCE.md` | AI layer reference. |
| `ARCHITECTURE_REFERENCE.md` | Architecture reference. |
| `CODE_REFERENCE.md` | Code reference. |
| `RUNTIME_BIBLE.md` | Runtime reference. |
| `RUNTIME_KNOWLEDGE_GRAPH.md` | Runtime knowledge graph. |
| `SYSTEM_TRUTH_REPORT.md` | Truth claims. |
| `REPOSITORY_FINALIZATION_REPORT.md` | Finalization summary. |
| `CLAUDE_CONFIGURATION_AUDIT.md` | Tooling audit. |
| `free-claude-code/` | Third-party license review (the repo already imports a fork). |

**Recommendation:** Do **not** publish `src/`, `data/`, `docs/`, or any of the audit-material directories until reviewed by IP counsel.

---

## F. UNKNOWN / HUMAN REVIEW

Insufficient static evidence to classify confidently.

| Path | Question | Why unclear |
| --- | --- | --- |
| `data/raw/*.csv.cr2a_backup` | What is `.cr2a_backup`? Where did these come from? | Unknown extension; no source reference. |
| `frontend/src/components/optimization/FleetDashboard.jsx` vs `FleetPanel.jsx` | Is one obsolete? | Both imported by `MaritimeDashboard.jsx`; need to inspect to confirm single owner. |
| `frontend/src/components/optimization/PipelineView.jsx` + `PipeNode.jsx` + `RegionPipelineNode.jsx` | Is one of the three obsolete? | Need to inspect. |
| `frontend/src/components/optimization/ConflictView.jsx` vs `FeedbackView.jsx` | Is one obsolete? | Need to inspect. |
| `scripts/p1e_validate.py`, `scripts/phase_f_visibility_test.py` | What are they for? | No source reference; likely investigation helpers. |
| `src/pipeline/optimization_pipeline.py`, `src/pipeline/orchestration.py` | Why are they tracked but empty? | Possible placeholder. |
| `src/llm/evaluator_manager.py` | Why is the file only 2 lines? | Possibly placeholder. |
| `backend/services/pipeline_streamer.py` vs `backend/pipeline_streamer.py` | Which is canonical? | Need to inspect. |
| 14 worktree references in `git branch -a` (`worktree-wf_*`, `d4-freeze-safety`, `backup-v1-before-rebase`) | Which are still needed? | Not in current worktree's filesystem. |
| Stash `stash@{0}`, `stash@{1}`, `stash@{2}` | Should any be applied, dropped, or preserved? | Cannot inspect content safely in audit-only mode. |

---

## G. HIGH-RISK FILES

| Path | Risk | Action |
| --- | --- | --- |
| `.env` (contains `OPENCODE_API_KEY=...` and `OPENROUTER_API_KEY=...`) | **TRACKED in Git history; both keys are real.** | **Rotate both keys immediately.** Remove `.env` from the tree. Add a `.env.example` with placeholders. Update `.gitignore` to also include `.env` (already listed, but `.env` is committed). |
| `_legacy/server.log` | Foreign log (Claude Code proxy startup); contains a `NVIDIA_NIM_API_KEY` warning in plain text. | Move to archive; do not commit. |
| `frontend/dist/assets/index-66d7e027.js.map` | Source map can leak source structure. | Usually gitignored; verify. |
| `backend/optimization_results.db` | SQLite; possibly contains historical run data. | Review before publishing. |
| `free-claude-code/` | Third-party code; license review required. | Already gitignored; do not include in any public bundle. |

---

## H. GIT CLEANUP RECOMMENDATIONS (RECOMMENDATIONS ONLY — NO ACTIONS TAKEN)

| Action | Recommendation | Confidence |
| --- | --- | --- |
| Investigate 14 stale worktree references | `git worktree list` to enumerate, then prune obsolete ones manually. **Do not delete blindly.** | Medium |
| Preserve all 3 stashes | Per audit-only rule, none applied. Stashes are provenance. | High |
| Preserve 3 tags | `v1.0.0-rc1`, `v1_backend_frozen`, `v1_runtime_integrated`. | High |
| Resolve `frontend/dist/index.html` LF/CRLF diff | Trivial; fix on next commit. | High |
| Rotate API keys in `.env` | **Required.** | High |
| Remove `.env` from Git index | Not needed — `.env` is **not** in the Git index. No action required. | High |
| **Do NOT rewrite history** (filter-repo, filter-branch) | Out of scope. | High |
| **Do NOT delete branches/tags/stashes** | Out of scope. | High |
| **Do NOT force push** | Out of scope. | High |

---

## I. IMMEDIATE ACTIONS (PRIORITY)

1. **Rotate the two API keys in `.env`** (if the working tree may have been shared or copied). (MEDIUM)
2. **Add `.env.example`** with placeholders. (LOW)
3. **Delete `_tmp_sel_test.py`** (docstring says "removed before final"). (LOW)
4. **Delete the two stale `frontend/{public,dist}/pipeline_output.json` copies** (drift hazard). (LOW)
5. **Delete 17+ empty directories** (scaffold residue). (LOW)
6. **Decide backend canonical server**: `unified_main.py` is the documented active; archive `main.py` and `server.py` and `main_backup.py`. (LOW)
7. **Decide frontend landing/dashboard history**: confirm whether `landing-dashboard.png` should remain. (LOW)
8. **Run IP review** on `src/`, `data/`, `docs/`, and the audit material before any release. (HIGH)
9. **Resolve `regional_policy_validator.py` v1 vs v2**: archive v1. (LOW)
10. **Decide on `MASTER_TECHNICAL_DOCUMENTATION.md` vs V2**: keep V2; archive V1. (LOW)
11. **Move the entire audit/analysis/CCEOS/Implemented-plans/research/RuntimeIntegrity/RUNTIME_BIBLE/RUNTIME_KNOWLEDGE_GRAPH/AI_LAYER_REFERENCE/ARCHITECTURE_REFERENCE/CODE_REFERENCE/CLAUDE_CONFIGURATION_AUDIT/REFERENCE_TEMPLATE_DESIGN_SPECIFICATION/README-reference-template/reference.docx/images/raw_responses/eval_output/logs/_legacy/doc-generation scripts** to a private archive. (LOW)

---

## J. NOT INSPECTED

* The full content of every file in the audit (only relevant excerpts and metadata were read). **Confidence remains High for the file-level classifications because decisions are based on path/imports/git status/line counts/static evidence, not on full file reading.**
* The internal details of the 14 detached worktree references (no on-disk presence in the current worktree).
* Stash contents (not applied).
* `.claude/`, `frontend/.claude/`, `free-claude-code/` internals (per-user / third-party).
* `venv/` and `node_modules/` (gitignored).

---

## K. AUDIT DELIVERABLES (NEWLY CREATED)

| File | Purpose |
| --- | --- |
| `REPOSITORY_CLEANUP_AUDIT.md` | Master human-readable audit. |
| `REPOSITORY_FILE_CATALOG.csv` | Per-file classification matrix (CSV). |
| `REPOSITORY_RUNTIME_MAP.md` | Runtime/backend/frontend/iteration/coverage trace. |
| `REPOSITORY_DECISION_QUEUE.md` | This file — human-reviewable decision queue. |

---

END OF DECISION QUEUE.
