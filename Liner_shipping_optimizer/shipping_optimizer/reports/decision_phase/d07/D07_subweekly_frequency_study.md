# D-07 - sub-weekly (fortnightly) frequency: read-only feasibility study

**Nothing in the model was changed.** The weekly-frequency model is untouched. Evidence: `outputs/fortnightly_seed{0,1,2}.json`,
`tools/fortnightly_study.py`. Tree: commit `6ab68d1` (canal fees, draft feasibility, port-call rule in force).

## Method
Same production candidate pool (regional filter applied, per-OD cap 10, VUB inequality on), solved as the **unrestricted integer problem
with HiGHS (240 s)** in two variants: (W) production, weekly frequencies; (F) every candidate gets a *fortnightly twin*: capacity per leg
per week / 2, rotation fuel and port/canal fixed costs / 2, vessels = ceil(T / 14); twin and weekly service may be combined.
Limitations (stated, not hidden): the transfer wait is not doubled for twins (optimistic for connections); the path cap (10 per OD) and the
2,410-model size are unchanged; HiGHS stopped at the time limit in all six solves, so the two incumbents are not equally converged.

## Result (seeds 0-2)
| seed | W incumbent / bound (gap) M USD/wk | F incumbent / bound (gap) | delta incumbent | delta **bound** | coverage W -> F | twins operated | cargo on paths using a twin |
|---|---|---|---:|---:|---|---:|---:|
| 0 | 23.53 / 28.51 (21 %) | 27.39 / 29.03 (6 %) | +3.85 | **+0.53** | 31.5 -> 30.9 % | 23 | 51,498 TEU |
| 1 | 22.05 / 27.47 (25 %) | 27.26 / 28.34 (4 %) | +5.21 | **+0.87** | 27.6 -> 34.1 % | 32 | 63,930 TEU |
| 2 | 24.78 / 26.25 (6 %) | 27.25 / 28.38 (4 %) | +2.46 | **+2.13** | 33.2 -> 33.9 % | 30 | 62,690 TEU |

## Reading
* The incumbent gain (+2.5 .. +5.2 M, 10-24 %) is **mostly solver convergence**: the weekly model is the larger-gap solve in all three
  seeds. The rigorous quantity is the change of the **dual bound** (the best possible value of the capped model): **+0.5 .. +2.1 M/wk
  (+2 .. +8 %)**. That is the most a fortnightly option could add inside this pool and cost basis.
* Coverage does not systematically rise (-0.6 .. +6.5 pp); twins are mostly used on thin rotations to cut vessel and fuel cost (23-32 of
  ~36 operated services were twins, 163-190 vessels against 153-182). Demand "unlocked" is therefore an economic effect on lanes already
  served, not new coverage.
* Fleet: vessels are not saved on average (163 vs 172, 184 vs 153, 190 vs 182); class inventory remains the binding constraint.

## What implementing it would require (not done)
| area | change |
|---|---|
| frequency variable | allow `f` in half-weekly units (`g = 2f` integer) or a per-service `{1/2, 1, 2, ...}` set; capacity `cap * g / 2` per leg per week |
| vessels | `n >= ceil(T * g / 14)` with the 7-day relation generalised; ledger and `required_vessels` must accept a rational frequency |
| transit / connections | expected transfer wait depends on both services' departure intervals (7, 14 days); the path module's single `transfer_wait_days` must become per-pair |
| ledger / reconciliation | frequency type check (`int` today), vessel recomputation, leg capacity `cap * f` with half values |
| output / frontend | `frequency_per_week` becomes fractional; load-factor definitions already use offered TEU-legs |
| tests | unit tests for vessels = ceil(T g / 14), capacity per leg, ledger agreement, transit with 14-day connections; regression against weekly-only plans (must be unchanged when the option is off) |
| runtime | model size roughly doubles (2,410 models, 13,112 paths): CBC at 120 s will not close the gap; HiGHS or a restricted twin set is required |
| business | the source must state that sub-weekly services are in scope (LINERLIB models weekly frequency only; the authors' solutions are all weekly: 'voyage duration in weeks', one departure per week) |

## Recommendation
Do not implement before the owner confirms scope: **the authors' own benchmark uses weekly frequency only**, so a fortnightly option would
leave the benchmark definition. If it is wanted for operations, implement it as a separate opt-in model with the weekly-only behaviour
bit-for-bit unchanged, and measure on the bound (not the incumbent) with a solver that converges. Rollback design: new variable set behind a
flag (`LINER_FREQUENCY_GRID=weekly|biweekly`, default `weekly`); revert = unset.
