# Class-mismatch campaign — single report (WorldSmall only, 2026-10-15)

Branch `campaign/20261013-issues-1-8`; commits `fb760ad` (diagnosis, trunk generator, predeclaration) and `e51e711` (set-cover selection, T2 predeclaration).
Nothing was pushed. No default, input file, assumption, solver limit (CBC single thread, 120 s) or objective was changed; every new behaviour is an opt-in flag.
Base for every run: frozen tree = commit `49ecd92` source + the trunk module (`C:\Users\WINDOWS\Liner-Worldsmall_exp\tree_fix1`), `PYTHONHASHSEED=0`, runs strictly one after another, seeds 0–19.

## 1. Verdict

| Item | Result |
|---|---|
| Best configuration found | arm **T2** = VUB + Local Search + `LINER_TRUNK_CANDIDATES=6` + `LINER_TRUNK_DIVERSE=1` |
| Profit | **38.94 M USD/week** (min 33.35, max 42.37) vs 30.12 M for arm B (VUB + Local Search): **+8.83 M, higher on 20 of 20 seeds, worst seed +4.47 M** |
| Coverage | **40.6 %** (min 31.5, max 45.0) vs 33.9 %: +6.8 pp, higher on 19 of 20 seeds. **The 70 % target is NOT met.** |
| Validity | 80 campaign runs (T, V, P, T2 × 20 seeds): the 79 solved plans pass `independent_check.py` (the one failure is V seed 0, status not_solved); ledger violations 0, transit violations 0; port-call + canal cost recomputed independently = ledger to 0.0 USD on 40 plans (T, T2); no draft violation on 550 operated services; no class above its inventory |
| Status | **experimental flags, not promoted.** Defaults are unchanged. Promotion is an owner decision |
| Readiness | still `READY FOR EXPERIMENTAL WORK ONLY` — material assumptions (canal tariff, handling unit, capacity unit, transit file) remain unverified |

## 2. What was wrong (diagnosis, seed 0, read-only; `tools/class_diag.py`, `outputs/class_diag_seed0.json`)

1. The production pool of 1,205 rotations was **79 % Feeder_450** (950 rotations for a class that owns 24 vessels), 160 Feeder_800, 67 Panamax_2400, 26 Panamax_1200, 2 Super_panamax and **0 Post_panamax**.
   Only 76 of the 1,204 feasible Feeder_450 rotations earn money stand-alone; the rest keep the legacy nearest-capacity class (`class_screening`: "no profitable class — legacy class kept").
2. Every pool rotation was evaluated in every class. **Post_panamax: feasible on 250 rotations, profitable stand-alone on 0. Super_panamax: feasible on 404, profitable on 0.** Draft excludes 752 / 507 rotations and canals 203 / 149.
   The pool holds only thin 2–5 port rotations that an 8,400-TEU ship cannot fill (best Post_panamax stand-alone: −0.24 M with 586 TEU served).
3. Growing rotations **with the large class fixed** (up to eight ports, draft-eligible hubs; `tools/trunk_proto.py`): 53 of 56 Post_panamax rotations, 32 of 51 Super_panamax and 60 of 60 Panamax_2400 rotations are profitable stand-alone (best +8.5 M, +13.1 M, +6.9 M/week; each about 10 vessels). Stand-alone profits overlap and are not additive.
   → The large classes were idle because **the candidate generator (≤ 5 ports, growth scored per vessel) never produced a rotation they could fill**, not because the optimiser rejected them.
4. With trunks added (arm T), the 6 offered Post_panamax trunks were still not used: all offered trunks shared the same Asia–Europe hubs and the Super_panamax trunk absorbed that cargo (`outputs/trunk_offer_seed0.json`). → set-cover selection (T2).

## 3. What was built (all opt-in, default OFF)

| Flag | Effect | Files |
|---|---|---|
| `LINER_TRUNK_CANDIDATES=N` | for each under-subscribed class (< 2 candidates per owned vessel) add N class-forced multi-port trunk rotations (greedy growth by stand-alone profit, ≤ `LINER_TRUNK_MAX_PORTS` = 8 ports, draft-eligible ports only, stand-alone profit must be > 0, near-duplicates dropped) | `src/network/trunk_candidates.py`, hook in `src/network/reconcile.py` |
| `LINER_TRUNK_DIVERSE=1` | classes served largest first; each selected trunk marks the ODs it carries as covered (25 % weight for later trunks); ranking by that marginal score | same |

Additions are ordinary candidates: the global MILP decides with their real fixed and variable costs and the independent ledger verifies the plan. The result's `trunk_candidates` block lists every addition with its provenance.
Tests: `tests/test_trunk_candidates.py` (12) pass; with `tests/architecture`, `test_expansion_flags`, `test_class_screening`, `test_assumption_register`, `test_solver_status_semantics`, `test_utilisation_definitions` — 92 passed, and `frontend/public/pipeline_output.json` was unchanged by the run (same SHA before and after).

## 4. Results (20 paired seeds, paired with arm B of `current_code_experiment`)

Per-seed data: `per_seed_all_arms.csv`; full tables: `summary_all_arms.md`; independent checks: `independent_check_TVP.json`, `independent_check_T2.json`, `port_canal_independent_T_T2.json`.

| Arm | Setting added to B | Profit M/wk | Δ vs B (paired) | Seeds higher | Coverage % | Δ pp | Verdict (criteria predeclared in `PREDECLARATION.md`) |
|---|---|---:|---:|---:|---:|---:|---|
| B | – | 30.12 | – | – | 33.9 | – | reference |
| **T** | trunk candidates, N = 6 | 33.14 | **+3.02** (min +0.23) | **20/20** | 34.3 | +0.4 | **retained (experimental)** |
| **T2** | N = 6 + set-cover selection | **38.94** | **+8.83** (min +4.47) | **20/20** | **40.6** | **+6.8** | **retained (experimental); supersedes T: +5.81 M vs T, higher 20/20, min +2.11** |
| V | class variants 0.10, floor −0.5 M | 28.22 | −1.80 | 7/19 | 33.2 | −0.7 | **rejected** (1 of 20 runs not solved: seed 0) |
| P | adaptive path budget | 29.76 | −0.36 | 10/20 | 33.9 | 0.0 | **rejected** |

Mechanism (means, B → T2):
- Super_panamax vessels used 0.1 → 9.1 of 10; **Post_panamax 0 → 10.7 of 58** (6–7 vessels on 12 seeds, 16–17 on 8 seeds).
- Revenue 106.2 → 125.2 M; total cost 76.1 → 86.3 M; margin 28.4 → 31.1 %.
- Demand blocked by "fleet inventory exhausted" 41.8 % → 25.1 %; "not economic to open a service" 8.9 % → 21.1 % (the label is a residual, see `expansion_2026_10_12` §5.1).
- Cargo moved with no transfer 64.3 k → 88.1 k TEU/week.
- 133 of the 550 operated services over the 20 T2 plans are trunk services.

## 5. Status of every issue proposed as degrading the system

| # | Issue | Status | Evidence / reason |
|---|---|---|---|
| 1 | Large classes idle, class mismatch | **Largely fixed (opt-in)** | cause found (§2); Super_panamax 10/10 in use; Post_panamax 10.7/58 in use. **Not fully fixed: 47 of 58 Post_panamax remain idle on average** |
| 2 | Profit | **Improved +8.83 M (T2)**, opt-in | §4 |
| 3 | Coverage | **Improved +6.8 pp to 40.6 %**; target 70 % **not met** | §4 |
| 4 | Number of services | **Not improved** (29.4 → 27.5; fewer, larger trunk services) | §4 |
| 5 | Fleet vessel utilisation (assigned / owned) | **Not improved: 0.683 → 0.632** (166 of 263 assigned; 97 idle) | one large ship replaces several small ones; profit rose while this metric fell. Network leg load factor 0.618 → 0.573 |
| 6 | Hidden complementary services (stand-alone screen) | **Not resolved** | arm V (existing class-variant flag with a loss floor) was worse and had a not-solved run |
| 7 | 10-path cap per OD | **Not resolved** | arm P neutral; cost-aware ranking was rejected earlier (+0.52 M, coverage −0.71 pp) |
| 8 | LP-guided restriction | **Not addressed** | changing the solver approach conflicts with the frozen CBC / 120 s rule |
| 9 | 120 s non-convergence / seed variance | **Not resolved**; T2's capped-model gap is 8.2 % (B reports −1.6 % in the legacy field — not comparable) | incumbent still not proven optimal; T2 profit sd 2.08 M across seeds |
| 10 | Weekly-only frequency | **Not addressed** | needs model and ledger changes; earlier study: ≤ +2.1 M/week |
| 11 | Input-side blocks (7.9 % no time-feasible service + 3.4 % limit below fastest sailing time) | **Not fixable by the optimiser** | revised transit file is a named scenario (+2.46 M, +3.2 pp earlier) that needs an owner decision |
| 12 | Cost base set by assumptions (canal fees ≈ 6.7 M/week ≈ 17 % of T2 profit; handling unit) | **Not resolved** | need an authoritative tariff / technical report |

So: **issues 1, 2 and 3 are improved by T2; issue 1 is not complete; issues 4 and 5 did not improve; the remaining items were tested and rejected or not addressed, for the reasons stated.**

## 6. Limitations and things not verified

- Arm B (and T, V, P) were compared with runs made hours apart. No drift control (planned `Bc`) was run; T2 was run ~2 h after T. The paired size of the effects (all seeds, minimum +4.47 M) is far above the +0.0–1 M run-to-run differences seen before, but this is a stated limitation.
- The T2 criteria (addendum 1) were written after seeing T results and before any T2 run; the choice of N = 6 per class and 8 ports was not tuned; only one setting of each was tried.
- Stand-alone profits are a screen, not additive; plan profit comes from the independent ledger only.
- Absolute levels (≈ 39 M/week) depend on unverified assumptions: capacity unit (`reference_code`, ×2 would change levels), canal tariff (benchmark rule, 34/34 services reproduced), handling unit (per FFE), transit file (unrevised file contradicted vs the benchmark advice). The paper benchmark remains FFE-native and separate.
- Not re-run after the change: the orchestrator (364 assertions) and the full test suite (last known: 29 failed, all `test_economic_metric_documentation.py`, plus 1,440 passed). The flags are default OFF and the touched file `reconcile.py` only gains an off-by-default branch and one output key (`trunk_candidates: {enabled: false}`); the output-contract tests pass.
- Browser behaviour of the dashboard remains unverified.
- A weekly service of up to ten 8,400–15,000-TEU ships on a 70-day cycle is feasible by the model's rules; the model does not check port-berth/terminal capacity (none is given in the WorldSmall files).

## 7. Reproduce / roll back

- Reproduce a run: `reports/class_mismatch_campaign/tools/run_arms.sh "<seeds>" "T2=LINER_TRUNK_CANDIDATES=6,LINER_TRUNK_DIVERSE=1"` (needs the frozen tree `tree_fix1`; arms V, P, T used the same script). Run order and return codes: `run_order.csv`.
- Revert the code: `git revert e51e711 fb760ad` (not executed). Flags OFF = previous behaviour exactly.
- Recommended next steps (owner decisions, not done): promote VUB + Local Search + T2 as one profile after a 5-seed drift-controlled hold-out on fresh seeds; investigate the 47 idle Post_panamax vessels (second trunk lane family, e.g. Atlantic / Americas), sub-weekly frequency, and the open assumptions.
