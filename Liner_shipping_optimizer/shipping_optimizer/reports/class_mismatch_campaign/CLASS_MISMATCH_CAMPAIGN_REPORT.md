# Class-mismatch campaign — single report (WorldSmall only, 2026-10-15)

Branch `campaign/20261013-issues-1-8`. Nothing was pushed. No default, input file, assumption, solver limit (CBC single thread, 120 s) or objective was changed; every new behaviour is an opt-in flag, OFF by default.
Base of every run: frozen tree = commit `49ecd92` source + the opt-in modules of this campaign (`C:\Users\WINDOWS\Liner-Worldsmall_exp\tree_fix1`), `PYTHONHASHSEED=0`, runs strictly one after another, rotating arm order, 120 s. All retention rules were written in `PREDECLARATION.md` (addenda 1-6) **before** the runs they govern; where a rule or value was chosen after seeing earlier data this is said.

## 1. Verdict

| Item | Result |
|---|---|
| Starting point (arm B = VUB + Local Search, 20 seeds) | profit 30.12 M USD/week, coverage 33.9 %, 29.4 services, fleet utilisation 0.683 |
| **T2** (B + trunk candidates, set-cover selection) — **retained** (all predeclared criteria met) | **38.94 M (+8.83, 20/20 seeds, worst +4.47)**, coverage **40.6 %**, 27.5 services, utilisation 0.632 |
| **C3** (T2 idea scaled up + MILP support cap) — highest mean, **not retained under the stated rule** | **42.47 M (+12.36 vs B, 20/20; +3.53 vs T2, 17/20)**, coverage **44.0 %** (max 47.9), 28.1 services, utilisation 0.619; **two seeds lose > 3 M vs T2** (seed 0 −4.4, seed 19 −6.5) |
| End to end with the GA (full orchestrator, n = 1 each) | default 25.75 M / 30.4 % → C3 flags **45.26 M / 50.2 %**; both verified, 0 violations; assertions 364/364 (default) and 369/369 (C3) |
| 70 % coverage | **not met and not reachable with this pool**: best single plan 50.2 % (end to end) / 47.9 % (global stage); a 60 % floor is **infeasible** on 3 of 5 seeds (§6) |
| Status | experimental flags only; promotion is an owner decision. `READY FOR EXPERIMENTAL WORK ONLY` — canal tariff, handling unit, capacity unit and transit file remain unverified |

## 2. Diagnosis (seed 0, read-only; `tools/class_diag.py`, `tools/trunk_proto.py`, `outputs/class_diag_seed0.json`)

1. The production pool of 1,205 rotations was **79 % Feeder_450** (950 rotations for a class that owns 24 vessels), 160 Feeder_800, 67 Panamax_2400, 26 Panamax_1200, 2 Super_panamax and **0 Post_panamax**. Only 76 of the 1,204 feasible Feeder_450 rotations earn money stand-alone; the rest keep the legacy nearest-capacity class.
2. Every pool rotation in every class: **Post_panamax feasible on 250, profitable stand-alone on 0; Super_panamax feasible on 404, profitable on 0** (draft excludes 752 / 507, canals 203 / 149). The pool holds only thin 2–5 port rotations that an 8,400-TEU ship cannot fill.
3. Rotations grown **with the large class fixed** (up to eight ports, draft-eligible hubs): 53 of 56 Post_panamax, 32 of 51 Super_panamax, 60 of 60 Panamax_2400 rotations are profitable stand-alone (best +8.5 / +13.1 / +6.9 M/week, ~10 vessels each; not additive).
   → the large classes were idle because **the candidate generator (≤ 5 ports, growth scored per vessel) never produced a rotation they could fill**.
4. With plain trunks (arm T) the offered Post_panamax trunks were still not chosen: all shared the same Asia–Europe hubs and the Super_panamax trunk absorbed that cargo (`outputs/trunk_offer_seed0.json`) → set-cover selection (T2).
5. About the GA: the pool handed to the global MILP is **every filtered candidate service, not the GA's selection** (`orchestrator_agent.py:464`). The GA contributes only warm-start frequency hints through the regional MILP. The global-stage runs of this campaign pass no hints; §7 measures the full pipeline.

## 3. What was built (all opt-in, default OFF; tests in `tests/`)

| Flag | Effect | Where |
|---|---|---|
| `LINER_TRUNK_CANDIDATES=N`, `LINER_TRUNK_MAX_PORTS` | N class-forced multi-port trunk rotations per under-subscribed class (stand-alone profit must be > 0, draft-eligible ports, near-duplicates dropped) | `src/network/trunk_candidates.py`, `reconcile.py`; `tests/test_trunk_candidates.py` (12) |
| `LINER_TRUNK_DIVERSE=1` | set-cover selection: largest class first, ODs already carried by a chosen trunk count 25 % for later trunks | same |
| `LINER_MILP_LP_ROUND_START=1` | CBC warm start from the rounded LP relaxation, repaired to the fleet limits | `network_milp.py`; `tests/test_lp_round_start.py` — **rejected, no benefit (§5)** |
| `LINER_MILP_SUPPORT_CAP=K` | integer problem keeps at most K of the LP-support services (those carrying the most LP cargo) | `network_milp.py`; same test file (6 tests in total) |

Additions are ordinary candidates: the global MILP decides with their real costs and the independent ledger verifies the plan.
Targeted regression tests (92 earlier, plus the new files) pass; `frontend/public/pipeline_output.json` was unchanged by them. The full suite was **not** re-run (last known: 29 failed, all `test_economic_metric_documentation.py`); the default orchestrator passes 364/364 after the changes (§7).

## 4. Results of the first batch (20 paired seeds, vs arm B of `current_code_experiment`)

| Arm | Change | Profit M/wk | Δ vs B | Seeds higher | Coverage % | Verdict |
|---|---|---:|---:|---:|---:|---|
| B | – | 30.12 | – | – | 33.9 | reference |
| T | trunks N = 6 | 33.14 | +3.02 | 20/20 | 34.3 | retained |
| **T2** | N = 6 + set-cover | **38.94** | **+8.83** (min +4.47) | **20/20** | **40.6** | **retained**; vs T: +5.81, 20/20 |
| V | class variants 0.10, floor −0.5 M | 28.22 | −1.80 | 7/19 | 33.2 | rejected (1 not solved) |
| P | adaptive path budget | 29.76 | −0.36 | 10/20 | 33.9 | rejected |

T2 mechanism (means, B → T2): Super_panamax vessels used 0.1 → 9.1 of 10; **Post_panamax 0 → 10.7 of 58**; revenue 106.2 → 125.2 M; total cost 76.1 → 86.3 M; cost per served TEU 812 → 768 USD; "fleet inventory exhausted" 41.8 % → 25.1 % of demand; 133 of 550 operated services are trunks.
Independent checks (all plans): `independent_check.py` pass; port-call + canal cost recomputed = ledger to 0.0 USD; no draft violation; no class above inventory (`independent_check_*.json`, `port_canal_independent_*.json`).

## 5. Screening of the remaining issues on top of T2 (seeds 0–9 vs T2; rule of addendum 2/3)

Rule: carried on only if mean ≥ +0.3 M, higher on ≥ 7/10, no failed run, no seed loses > 3 M.

| Arm | Targets | Mean Δ vs T2 | Higher | Failed | Verdict |
|---|---|---:|---:|---|---|
| T3: 12 trunks/class, ≤ 10 ports | idle Post_panamax, coverage | +0.71 | 6/9 | seed 7 not solved; seed 9 22.9 M (−16.3) | rejected — **8 of 10 seeds reach 39–45.5 M and up to 48 % coverage; CBC fails at the larger size** |
| H: search-only class variants | hidden services | +0.57 | 2/10 | – | rejected |
| Pa: adaptive path budget | 10-path cap | −0.73 | 1/5 solved | **5 of 10 not solved** | rejected |
| Rt: revised transit file (scenario tree) | input-side blocks | +1.11 | 7/10 | min −11.2 (seed 1) | rejected as a candidate; the transit file stays an owner decision |
| Hg: HiGHS backend (5 seeds) | LP-guided restriction | −3.95 | 0/5 | – (coverage −7.7 pp) | rejected |
| L / L2: LP-rounding warm start on T3 / T2 | CBC no-incumbent | −1.11 / −0.29 | 5/9 / 1/10 | L: seeds 7, 9 unchanged | rejected — the failure is not a missing start |

Diagnosis of T3's failures: the integer problems of seeds 7 and 9 hold 119 and 115 LP-support services (≈ 4.6–4.8 k variables); the T3 seeds that solve well hold 105–111, T2 90–96. CBC fails at a **size threshold**.
**Support cap (the MILP modification that worked).** C3 = T3 settings + `LINER_MILP_SUPPORT_CAP=105` (value chosen after seeing those sizes — stated limitation). Seeds 0–9: 10/10 solved, +2.80 M vs T2, 8/10 higher, coverage +3.56 pp, but seed 0 −4.39 M → fails the 3 M criterion; **hold-out seeds 10–19 run anyway as exploratory (addendum 5)**:

| C3, 20 seeds | value |
|---|---|
| solved / violations | 20/20 / 0; independent check 20/20; port+canal recomputation 0.0 USD; 561 services, 0 draft/inventory violations |
| profit | **42.47 M** (min 31.79) vs T2 38.94, B 30.12 |
| Δ vs T2 | **+3.53 M**, higher 17/20, min −6.54 (seed 19); seeds below −3 M: 0 and 19 → **criterion 4 fails, C3 not retained under the stated rule** |
| Δ vs B | +12.36 M, 20/20, min +2.27 |
| coverage | **43.97 %** (max 47.9) vs 40.64 |
| services / vessels assigned | 28.05 / 162.9 (utilisation 0.619); Post_panamax 25.6 vessels, Super_panamax 8.75 |
| cost per served TEU | 739 USD (B 812, T2 768) |
Drift control (T2 rerun on seeds 0–2): +0.00 / +0.10 / +0.18 M — small, so the stale-baseline concern is minor.
So: **T2 is the robust retained setting; C3 is a higher-mean, higher-variance alternative** for the owner to choose.

## 6. What stops 70 % coverage (measured)

Unserved demand of T2 plans (% of total demand): fleet inventory exhausted 25.1, not economic to open a service 21.1, no time-feasible service in the pool 6.3, transit limit below fastest sailing time 3.4, capacity exhausted 2.9, not profitable to carry 0.6.
The objective is profit (unserved penalty 0); the GA has no say in the global plan. **Coverage-floor sweep** (existing opt-in `LINER_GLOBAL_MIN_COVERAGE` on C3, seeds 0–4, `outputs/F*_seed*.json`):

| Floor | Solved | Result |
|---|---|---|
| 50 % | 1 of 5 | seed 1: 54.1 % coverage, 33.8 M (−3.4 M vs C3), 37 services, 229 vessels, cost/TEU 815 |
| 55 % | 0 of 5 | all `not_solved` (no incumbent in 120 s) |
| 60 % | 0 of 5 | **seeds 0–2 infeasible** (the model with this pool and the 10-path cap cannot reach 60 %), seeds 3–4 not solved |
Conclusion: a forced floor either fails to produce an incumbent in 120 s or is infeasible; 70 % is **not** reachable with the current candidate pool and path cap. This statement is about the capped model, not a proof for the full problem.

## 7. End to end including the GA (scratch tree without `.env`: rule-based fallback, no external calls; `LINER_SEED=0`; n = 1 each; `e2e/`)

| | default flags | C3 flags (VUB, LS, trunks 12 × 10 ports, diverse, cap 105) |
|---|---:|---:|
| selected iteration (best of 3) | 1 | 0 |
| weekly profit (M) | 25.75 | **45.26** |
| coverage (global) | 30.4 % | **50.2 %** (served 138,832 of 276,494 TEU) |
| services | 30 | 31 |
| revenue / total cost (M) | 96.1 / 70.3 | 150.0 / 104.7 |
| network ledger | verified, 0 violations | verified, 0 violations |
| orchestrator assertions | 364/364 | 369/369 |
The GA path (regional GA, regional MILP hints, best of 3 iterations) does not remove the gain: the full pipeline reproduces the direction and size of the global-stage result. n = 1 per setting — indicative, not a distribution.

## 8. Status of every issue proposed as degrading the system

| # | Issue | Status | Evidence |
|---|---|---|---|
| 1 | Large classes idle / class mismatch | **Largely fixed (opt-in)**: Super_panamax 9–10 of 10, Post_panamax 10.7 (T2) – 25.6 (C3) of 58 | §4–5. **Not complete: 32+ Post_panamax stay idle** |
| 2 | Profit | **+8.83 M (T2, retained), +12.36 M (C3, higher variance)** vs B | §4–5 |
| 3 | Coverage | **40.6 % (T2), 44.0 % (C3), 50.2 % end to end**; 70 % not met | §5–7 |
| 4 | Number of services | **not improved** (29.4 → 27.5 / 28.1; fewer, larger services) | §4–5 |
| 5 | Fleet utilisation (assigned / owned) | **not improved: 0.683 → 0.632 / 0.619** (97–100 idle); network leg load factor lower | one large ship replaces several small ones |
| 6 | Services hidden by the stand-alone screen | **not resolved** | V, H rejected |
| 7 | 10-path cap | **not resolved** | P rejected (5/10 not solved); cost-aware rejected earlier |
| 8 | LP-guided restriction | **not resolved** | HiGHS (Hg) −3.95 M |
| 9 | MILP non-convergence at larger pools | **mitigated by the support cap** (T3 failures → C3 10/10 and 20/20 solved); gap of the capped model still unresolved | §5 |
| 10 | GA role | **measured**: not a pool selector; full pipeline keeps the gain | §2.5, §7 |
| 11 | Weekly-only frequency | **not addressed** (model + ledger change; earlier bound ≤ +2.1 M/week) | – |
| 12 | Input-side blocks (6.3 % + 3.4 %) | **not fixable by the optimiser**; revised transit file is an owner decision (Rt mixed) | §5 |
| 13 | Cost base assumptions (canal ≈ 7.2 M/week ≈ 17 % of C3 profit; handling unit) | **not resolved** — need an authoritative tariff / technical report | – |

## 9. Limitations

- Retention rules were written before each run, but T2's criteria followed the T results, the cap value 105 followed the observed problem sizes, and C3's hold-out was an exploratory addition after a failed screening (stated in addenda 3–5).
- Arm B and the screening arms were compared with runs made hours apart; the only drift control (T2 rerun, 3 seeds) moved ≤ 0.18 M.
- Stand-alone profits are a screen, not additive; plan profit comes from the independent ledger only. The model does not check port-berth/terminal capacity (not in the WorldSmall files).
- Absolute levels depend on unverified assumptions: capacity unit (`reference_code`), canal tariff (benchmark rule), handling unit (per FFE), unrevised transit file (contradicted vs the benchmark's advice). The paper benchmark stays FFE-native and separate.
- End-to-end results are n = 1 per setting. Full test suite and browser behaviour of the dashboard were not re-verified.

## 10. Reproduce / roll back / next steps

- Runs: `tools/run_arms.sh "<seeds>" "<tag>=<ENV,ENV>"` (frozen trees `tree_fix1`, `tree_fix1_rt`); end to end: `tools/run_e2e.sh <tag> "<ENV,…|->"`; order and return codes: `run_order.csv`, `e2e/e2e_order.csv`. Per-seed tables: `per_seed_all_arms.csv`, `per_seed_C3.csv`; summaries: `summary_all_arms.md`.
- Revert the code: `git revert` the campaign commits (not executed). Flags OFF = previous behaviour exactly (default orchestrator 364/364).
- Recommended next steps (owner decisions): choose between T2 (robust) and C3 (higher mean and coverage, higher variance); a drift-controlled hold-out on fresh seeds before any promotion; then Post_panamax lanes beyond Asia–Europe, sub-weekly frequency, and the open assumptions.
