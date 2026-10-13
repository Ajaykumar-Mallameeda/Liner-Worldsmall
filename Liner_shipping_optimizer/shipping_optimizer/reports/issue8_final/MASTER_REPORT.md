# Master report - controlled resolution campaign, WorldSmall, 2026-10-13

Branch `campaign/20261013-issues-1-8` (from `baseline-t11-20261013`, unchanged). The Issue 8 commit sits on top of `87a5cbd`.
Scope: WorldSmall only; no WorldLarge/Baltic/WAF run; nothing pushed; `.env` never read or printed.

## 1. Issue-by-issue status
| issue | status | commit | what changed |
|---|---|---|---|
| 0 baseline | **PASS** | `95b8c74` (+ `259d379`, `95817f7`) | tracked baseline of the T11 tree + evidence; restore verified 1,572/1,572 |
| 1 unit contract | **PASS** | `7460391` | `Capacity FFE` x2 once at the loader (secondary-source evidence; status `secondary_source`), six unsourced lane factors removed, 18 new unit tests (12 failed before the change), contract-pinning tests updated with stated reasons |
| 2 corrected baseline | **PASS** (default is unstable) | `66f3191` | corrected-unit default 24.6 M/wk (4.7-33.5) on the first batch; full suite classified identical to the baseline tag (41 = 41) |
| 3 solver | **PASS** evidence + hardening; **no promotion** | `707c2f8` | VUB alone 29/30 seed-pairs higher; LS alone unsafe (2 not_solved + 1 invalid plan in 20); VUB+LS 20/20 higher; no-incumbent guard (CBC empty result -> `not_solved`) + 3 tests |
| 4 coverage | **PASS** (quantified); intervention not retained | `f558e89` | path cap/ranking is the largest model restriction; class inventory binding; cost-aware ranking only 5/10 seeds and unusable on plain CBC |
| 5 utilisation / register | **PASS** | `18eeea9` | `src/network/opportunities.py` (read-only), operational vs commercial statuses, 4 tests |
| 6 assumptions | **PASS WITH BLOCKERS** | `d2ea1de` | `assumption_register` in every result (13 entries), one-at-a-time sensitivities, canal-fee exposure; D-04/D-06/D-07/D-08 open |
| 7 paper benchmark | **PASS** (profit comparison refused) | `87a5cbd` | `src/benchmark/paper_evaluator.py`; vessel counts reproduced 19/19; the paper's profit is not reproducible |
| 8 final validation | **PASS for validation; NOT READY for operations** | this commit | below |

Changed source files (campaign total): `src/data/network_loader.py`, `src/network/network_milp.py` (guard), `src/network/reconcile.py` (+2 lines),
`src/network/strategy_report.py` (unit string), new `src/network/opportunities.py`, `src/network/assumption_register.py`,
`src/benchmark/paper_evaluator.py`; tests: 5 new files + 8 updated (see `git diff --stat baseline-t11-20261013..HEAD`).

## 2. Final validation (actual output in this directory)
| step | result |
|---|---|
| unit + loader tests | `test_unit_contract`, `test_capacity_units`, `test_worldsmall_loader`, `test_worldsmall_integration`: pass (inside the full suite below) |
| candidate generation / network / ledger / feasibility tests | all in the full suite, no new failure |
| `tests/test_orchestrator.py` | **364/364 assertions, 0 failed**, score 100 (`orchestrator_final_clean.log`) |
| full suite `pytest tests` | **41 failed / 1,391 passed / 20 skipped / 9 xfailed**; failing ids **identical** to the baseline tag under the same conditions (`fail_final.txt` vs `../issue2_corrected_baseline/fail_base_full.txt`: 0 differences); the 35 new tests all pass |
| output schema / consumers | `tests/architecture/test_output_contract.py` on the fresh orchestrator artifact: 7 pass, 1 fail (`regions == 5`, pre-existing, reproduced on the baseline tag); the new field is additive (`network_ledger.assumptions.assumption_register`, 13 entries present in the artifact); the frontend was **not** executed - NOT VERIFIED |
| paired performance, 20 seeds, CBC 120 s, final tree | section 3 |

The 41 failures are the documented documentation-drift set plus 13 artifact-dependent tests (golden SHA / output contract). The full suite
itself leaves a truncated `pipeline_output.json` (reproduced on the baseline tag). Nothing was weakened, skipped or deleted.

## 3. Baseline vs final (paired, seeds 0-19, same data hashes, CBC 120 s, two arms concurrent; `per_seed_final.csv`)
"Baseline" = the unchanged production default on the final tree. "Final candidate" = `LINER_MILP_VUB=1` + `LINER_LOCAL_SEARCH=1`
(**not a default - needs owner approval**). Pre-campaign old-unit numbers (11.9 M default, 24.9 % coverage) are not comparable (capacity was
understated 2x).
| metric (mean of 20) | default | VUB + LS |
|---|---:|---:|
| profit M USD/wk (min .. max) | 32.28 (17.08 .. 39.74) | **38.27** (32.70 .. 43.63) |
| margin % | 32.9 | 35.6 |
| coverage % | 30.9 | 34.0 |
| served TEU/wk | 85,441 | 93,909 |
| services / departures per week | 31.5 / 31.6 | 32.0 / 32.3 |
| vessels used / idle (of 263) | 175 / 88 | 182 / 81 |
| leg load factor / network load factor | 0.557 / 0.534 | 0.607 / 0.573 |
| cost per served TEU (USD) | 774 | 738 |
| max p90 transit (days) | 48.1 | 45.0 |
| gap to the capped model's LP bound % | 58.3 | -4.7 (final plan exceeds the capped-model bound) |
| stage wall time s | 120.9 | 112.1 |
| solved / ledger-valid / ledger violations / transit violations | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 |

Paired VUB + LS minus default: **+6.00 M**, higher on **19/20** seeds (dev 9/10, hold-out 10/10); worst seed -5.26 M (seed 4); coverage +3.1 pp
(17/20 higher). Per-seed profit, revenue, itemised costs, utilisation by class, transit and solver fields are in `per_seed_final.csv`.
In earlier batches under heavier machine load the gain was +8 .. +11 M: the *default* gets better when the machine is less loaded (CBC's
wall-clock incumbent), so the size of the gain depends on load; its sign was positive in 90 of 92 seed-pairs over all campaign batches.

## 4. Does the system reach 70 % coverage?
**No, and nothing measured supports it.** Achieved: 30.9 % (default), 34.0 % (VUB + LS), best single plan 39.7 %. Measured ceilings (Issue 4):
LP relaxations reach 50.6 % with the per-OD path cap lifted and 55-57 % with class inventories x100 (upper bounds, not plans); 3.4 % of
demand is physically unattainable; ~28-31 % of demand is unserved because the small/medium vessel classes are exhausted (the 48-58 idle
Post_panamax vessels do not profitably serve those lanes) and ~27-29 % because no service is worth its weekly cost at the incumbent.
Without more vessels, different cost data, or an economic path ranking solved by a stronger solver, 70 % is structurally out of reach.

## 5. Remaining risks and provisional assumptions
1. **Canal fees are not charged** although the data carries them: 7.4-8.2 M USD/wk (19-21 % of reported profit) if per departure; semantics
   undetermined (the paper's literal reading would be ~10x). Owner decision D-08. **P0 for operational use.**
2. Capacity unit rests on a secondary source; per-FFE cost reading (-16.5 M if wrong), transfer dwell (+4/-7 M), port stay (+2/-8 M), transit file (+4 M).
3. The default solve is unstable (17-40 M across seeds, 4.7 M at its worst in the first batch). Nothing was promoted.
4. `not_solved` can still occur under load; the guard only converts an empty CBC result into an honest `not_solved`.
5. 41 known test failures; the suite corrupts its own artifact.
6. The orchestrator test's utilisation display divides weekly load by per-departure capacity (shows >100 %).
7. Frontend/consumers not executed; LLM providers answered `all_providers_failed` throughout (deterministic fallback text).
8. No scalability evidence beyond 47 ports.

## 6. Rollback
* Behaviour: nothing was promoted; no `LINER_*` variable is set.
* Code: `git revert <commit>` per issue (independent commits 7460391, 707c2f8, 18eeea9, d2ea1de, 87a5cbd), or
  `git checkout baseline-t11-20261013 -- Liner_shipping_optimizer/shipping_optimizer/src Liner_shipping_optimizer/shipping_optimizer/tests`.
* Whole pre-campaign tree: `git checkout baseline/t11-20261013`.

## 7. Recommendation
**Suitable for experimental planning and scenario analysis only; not ready for operational use.** Blocking: canal-fee treatment (D-08),
confirmation of capacity and cost units against the primary LINERLIB report, owner decisions on the transit file and dwell convention
(D-04, D-06), and an owner decision on promoting VUB + LS (recommended: both together, never LS alone).

## 8. Owner decisions outstanding
D-01 capacity/cost units (primary source) - D-02 paper mode adoption - D-04 revised transit file - D-05 promote VUB + LS - D-06 dwell and
port stay - D-07 sub-weekly frequency - D-08 canal fees - D-09 HiGHS / 300 s - D-11 documentation tests - D-12 verdict bands.
