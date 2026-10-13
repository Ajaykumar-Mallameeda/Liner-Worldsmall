# Phase 8 — the pre-existing test failures: what was wrong, what was done, what is still open

**Rule applied:** no assertion was removed or loosened to obtain a pass.  A test that encoded a *contract the system intentionally no
longer has* was **not** silently edited: it was re-specified against the current contract with the same strength, or marked `xfail(strict=True)`
with the reason stated and replacement coverage added — and is listed below as **awaiting owner confirmation**, not as "fixed".
Baseline = the frozen accepted tree `snap_C0_base`, whole suite excluding `tests/test_orchestrator.py` (which has its own gate):
**51 failed / 1,257 passed / 46 skipped** (identical id set to the recorded Tasks 19–21 artifact-free baseline).

## 1. Matrix (51 baseline failures)

| group | n | root cause (traceback read, not inferred from names) | action | status |
|---|---:|---|---|---|
| `test_setup.py::test_config` | 1 | read `Config.OPENROUTER_API_KEY`; the OpenRouter provider was retired (providers groq / cerebras / google) and `Config.LLM_API_KEY` is the alias of whichever key is present | test updated to the current attribute; **three further assertions added** (models, GA sizes) | **FIXED** (test only) |
| `test_multi_agent_coordination.py` | 5 | tests patched `orchestrator_agent.ServiceGeneratorAgent` (no longer an attribute: the regional agents generate their own candidates), built the orchestrator with `__new__` (skipping the state `process()` reads) and expected `regional_policies` / `coordinator_objectives` on the coordinator / regional inputs | patch targets and construction brought to the current code; the *same intent* is asserted against the current routing: policies reach the `ConsensusEngine` (`regional_policies`, `coordinator_decisions`), the coordinator receives `regional_solutions`, regional agents receive the problem whose objective weights are > 0 | **FIXED** (re-specified; routing difference flagged for the owner, §3) |
| `test_service_generator_activation.py` | 3 | the AI log tags (`AI_GENERATED`, `AI_APPLIED`) were asserted but never emitted by `service_generator_agent`; the agent logs through stdlib `logging` while the tests patched the project logger | **product**: two `logger.info` lines (observability tags only, no behaviour); tests capture both loggers and parse the stdlib `tag=%s` style | **FIXED** |
| `maritime/test_phase8_command_center.py` | 3 | the routing-impact endpoint reads `<repo root>/pipeline_output.json`, an artifact produced by an orchestrator run and absent on a clean tree; the tests drove the endpoint with a patched `json.load` but needed the file to exist | fixture points the module root at a temp tree holding a stub file; no assertion changed | **FIXED** (test isolation) |
| `maritime/test_port_pipeline.py` | 1 | `PORTS_FIXTURE` (synthetic ports JSON) is not shipped with this tree | inline, labelled test ports when the fixture is absent; the asserted property (zero-record ingestion is INVALID whatever the ports) is unchanged | **FIXED** (fixture) |
| `test_regional_agent_activation.py` | 9 | written for an earlier design in which the LLM's policy JSON drove the regional agent (`_filter_services(min_margin)`, `AI_APPLIED` / `AI_REJECTED` for the LLM's policy). The accepted architecture derives the policy from regional metrics (rule-based), validates it, applies the filter chosen by `LINER_REGIONAL_FILTER`; the LLM writes text only | **not** deleted, **not** weakened: `xfail(strict=True)` with the reason on each; **replacement coverage** `tests/test_regional_policy_architecture.py` (5 tests) pins the current contract | **AWAITING OWNER** (retirement of the 9 is the owner's call; strict xfail turns into a failure the day one starts passing) |
| `test_economic_metric_documentation.py` | 29 | the tests need the `MULTI_AGENT_*.json` audit artifacts (7 files) and the main audit document, which are absent from the tree; they are produced by `scripts/build_*.py` from a **transcription of an older code state** (e.g. `revenue_per_teu = Revenue_1 * ffe_to_teu_factor` at `network_loader.py:109`), which the corrected loader contradicts (§2) | nothing done to these 29 | **BLOCKED** (needs a re-audit of the documents against the corrected code; regenerating the old transcription would restate contradicted formulas) |

51 = 1 + 5 + 3 + 3 + 1 + 9 + 29.

## 2. Why the 29 documentation tests are BLOCKED rather than "made to pass"

Facts (each checked, none inferred):

1. `tests/test_economic_metric_documentation.py` validates a *named* set of audit artifacts — seven `MULTI_AGENT_*.json` files and
   `MULTI_AGENT_ARCHITECTURE_FORMULATIONS_ECONOMIC_METRIC_INTEGRITY.md` — and its docstring is explicit: **"THEY MUST NEVER BE WEAKENED TO
   MAKE THE DOCUMENTATION PASS … the correct response is to re-verify the underlying claim against the source and either correct the
   document or correct the code — under an explicitly authorised repair phase"**.
2. None of those names exists in the tree **or in the original zip**.  The zip carries a *later* audit under other names
   (`MA_01 … MA_09`, `MA_09_FORMULA_INDEX.json`, `MULTI_AGENT_INDEPENDENT_FORMULATION_AND_ECONOMIC_TRUTH_AUDIT.md`) and the generator scripts
   `scripts/build_audit_artifacts.py`, `build_formula_index.py`, `build_dependency_map.py`.  The suite and the documents are from different
   naming generations; the tests failed before this campaign and before the zip was unpacked.
3. Experiment, in a scratch copy of the final tree (`D:\liner_scratch\docregen_T8`, not the project tree): the seven artifacts produced by
   running the generator scripts in an earlier scratch tree (`docregen_T2`; the scripts are unchanged since) plus an orchestrator
   `pipeline_output.json` from this campaign.  Result: **52 of 58 tests pass, 6 fail**:
   * `test_every_formula_citation_resolves` — **all 29 formula records cite lines that no longer contain the cited text**: e.g.
     `network_loader.py:109` is cited for `revenue_per_teu = Revenue_1 * ffe_to_teu_factor` (the corrected loader divides by the factor),
     `hub_milp.py:509` is cited in a 265-line file (the hub MILP was split into a legacy module).  This is the drift detector doing its job:
     the transcription is stale;
   * 5 tests on the main document — it does not exist anywhere (authored, not generated).
4. Consequence: the 23 tests that *would* pass after regeneration would pass over a transcription that the citation test itself proves stale.
   Restoring them without the re-audit would make the suite look healthier than the documentation is.  They are left failing, deliberately.

Owner options: **(A)** authorise the documentation-repair phase (re-audit the 29 formula records against the corrected code, author the main
document); **(B)** retire this documentation-drift suite and say so in the change record; **(C)** restore the seven artifacts from the
scripts, accepting that the citation test and the five main-document tests keep failing.  Nothing was done to these 29 tests or files.

## 2b. A passing test that had to be updated (disclosed, not hidden)

`tests/test_economic_metric_documentation.py::test_no_random_seeding_in_production_code` asserts that no production file seeds a generator
(finding F-21/F-28 "runs cannot be reproduced"); its docstring says it "fails and must be updated in the same commit" when seeding is added.
Task 17 adds the opt-in module `src/utils/rng.py` (acts only when `LINER_SEED` is set).  The test now exempts **that one file**
(`_SEEDING_ALLOWED = {"src/utils/rng.py"}`); every other `random.seed` / `np.random.seed` / `default_rng` / `RandomState` in `src/` and
`scripts/` still fails it.  Behaviour of the module itself is pinned by `tests/test_rng_control.py` (11 tests).  If the owner declines
Task 17 the exemption goes with the module (revert: `patches/`).

## 3. Items the owner should look at

| # | item | why it matters |
|---|---|---|
| 1 | coordinator no longer receives `regional_policies`; they go to the consensus engine | the original test asserted the coordinator gets them; the code since moved the hand-off.  If the coordinator *should* see them, that is a product change, not a test change |
| 2 | 9 regional tests retired by strict xfail | confirm retirement (or restore the LLM-policy behaviour) |
| 3 | 29 documentation tests | re-audit needed (above) |
| 4 | `test_full_cycle` (weather) was flaky: §5 | fixed in the test; the adapter's default-window semantics untouched |

## 4. Results after the campaign (live tree snapshot)

Whole suite, `tests/test_orchestrator.py` excluded, from isolated snapshot copies (`python -m pytest tests --ignore=tests/test_orchestrator.py
-q -p no:cacheprovider --tb=line`; logs `evidence/runs/T22_suite_baseline.log` [in `reports/expansion_2026_10_12`], `F1_suite.log`, `FINAL2_suite.log`):

| | frozen baseline (`snap_C0_base`) | intermediate run (`snap_T6`, before the last fixes) | **final tree (`snap_T11_final`)** |
|---|---:|---:|---:|
| failed | 51 | 30 | **29** |
| passed | 1,257 | 1,331 | **1,341** |
| skipped | 46 | 46 | 46 |
| xfailed (strict) | 0 | 9 | 9 |
| failing ids not in the baseline set | – | 1 (the weather race, fixed afterwards) | **0** |
| elapsed | 107 s | 115 s | 106 s |

Accounting: 1,257 + **13** tests fixed + **71** new tests = **1,341** passed, exactly; the 9 xfails are the retired-by-specification regional
tests; the 29 failures are the documentation-drift tests, all of them in the baseline's failing set.  Nothing was deleted; no assertion was removed.

| group | baseline | final | note |
|---|---:|---:|---|
| `test_setup` | 1 failed | 0 | fixed |
| `test_multi_agent_coordination` | 5 failed | 0 | fixed (re-specified to the current contract; §3 item 1) |
| `test_service_generator_activation` | 3 failed | 0 | fixed (product: two log tags) |
| `maritime/test_phase8_command_center` | 3 failed | 0 | fixed (fixture) |
| `maritime/test_port_pipeline` | 1 failed | 0 | fixed (fixture) |
| `test_regional_agent_activation` | 9 failed | 9 xfailed (strict) | held; 5 replacement tests pass |
| `test_economic_metric_documentation` | 29 failed | 29 failed | **BLOCKED** (§2) |

End-to-end (`tests/test_orchestrator.py`, three concurrent runs per configuration on the final tree): default **364/364 × 3**, final candidate
**368/368 × 3** (the two extra always-on state assertions and the flag-contract assertions of the new section N.11 included); earlier
groups on the T9 tree: 362/362 × 3 default, 360/360 × 3 for the search and for the final candidate (two assertions are conditional on
the flow re-optimisation having been applied; after the search it has nothing to gain).  The "artifact-present" suite variant of the earlier
missions (a copy with `pipeline_output.json` present) was not re-run on the final tree; its documentation-test count is the one
quantified in §2 (52 of 58 pass with regenerated artifacts).

## 5. The one new failure seen in the intermediate suite run: `test_phase5_weather::test_full_cycle`

* Seen once in the full-suite run on the modified tree (30 failed vs 29 expected).  **Not caused by this campaign:** it fails 1 of 12 single-test runs
  on the frozen baseline tree too (`assert 0 >= 1` on `forecast_window` records).
* Cause (source read): `WeatherFeatureAdapter.forecast_window()` without an explicit window keeps records with
  `valid_at >= now.replace(microsecond=0)`; the test's `StubProvider` stamps `valid_at = datetime.now()` at fetch time, so when the query
  falls one clock second later the record is dropped — a race inside the test, not a defect of the adapter.
* Fix: the stub stamps `valid_at` one hour ahead (a forecast value is valid in the future); `retrieved_at` stays "now".  The adapter and
  its documented default window (next 24 h) are untouched.  Verification: **0 failures in 15 consecutive whole-file runs**
  (49 passed, 1 skipped each), 0 in the full-suite run recorded in §4.
