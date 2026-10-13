# Unresolved owner decisions (consolidated, 2026-10-13)

"Blocks" = blocks the next implementation phase.  Recommendations are engineering recommendations, not approvals.

| ID | Question | Options | Evidence and trade-offs | Recommended | Blocks |
|---|---|---|---|---|---|
| **D-01** | Unit of fleet column `Capacity FFE` | (a) FFE → `capacity_teu = 2×`; (b) TEU as loaded; (c) keep provisional, report both | RL paper p.15/p.9 defines capacity in FFE and never uses TEU; primary LINERLIB report unavailable; S2: levels ×1.6–2.5, default found no plan on 1/3 seeds at ×2; ranking default < final unchanged in 23/23 pairs | (a) once the owner has confirmed against the LINERLIB report; until then (c) | **YES** |
| **D-02** | Adopt a separate "paper mode" (rejection penalty 1000/FFE, unused-vessel TC credit, fractional vessels, port-variable cost on `pv·vcap`, no transit limit)? | yes (flag-selected) / no | Required for any like-for-like comparison with arXiv:2411.09068; two code paths | yes, as a separate mode; operations unchanged | Yes for benchmark comparison only |
| **D-03** | Per-lane FFE→TEU factors 1.75–2.1 (6 ODs) | remove (k = 2) / source / keep | unsourced; contradicts `TEU_PER_FFE`; −47.2 TEU | remove or source | No (needed for invariance tests) |
| **D-04** | Use the revised LINERLIB transit file | adopt / keep with recorded reason | 13.0 % of demand differ; authors recommend revised; no measurable effect at n = 3 | adopt for benchmark comparisons | No |
| **D-05** | Which accepted-for-approval profile to promote | none / local search only / expanded (C1 + LS + 10 % variants) | LS +2.28 M 20/20 (lowest risk); expanded +3.25 M pooled on T8, +2.6–2.9 M hold-out on final code; increment over LS inconclusive (14/20) | LS only first | No |
| **D-06** | Transfer dwell convention (3.5 d + 48 h) and port stay 24 h | keep / replace with sourced values | provisional; ±2–3 M | keep; supply source | No |
| **D-07** | Are sub-weekly (fortnightly) frequencies in scope? | yes / no | A10; integer weekly `f` makes thin routes expensive; 60.7 % of unserved demand "not economic" | clarify before any model work | No |
| **D-08** | Canal-fee schedule (A12) and fuel-system data (A7); licensed bunker series (A6) | supply / accept 600 USD/t | blanks in fleet file; snapshot covers 5 of 47 ports, no licence | supply or accept | No |
| **D-09** | HiGHS backend and 300 s stage budget | adopt / keep CBC 120 s | `task15`: HiGHS 300 s recommended; interacts with the economic regional filter at 120 s | keep CBC 120 s until D-01 resolved | No |
| **D-10** | `LINER_SEED` as the experiment default | yes / no | reproducible pool/GA; CBC still wall-clock | yes for experiments only | No |
| **D-11** | Retire / restore the 9 xfail regional tests; authorise the documentation-drift suite | retire / restore / re-audit | 29 failing documentation tests, 6 genuine drift after regeneration | re-audit | No |
| **D-12** | Verdict band 20 % vs 25 %; Tier-0 consumer defects T0-1…T0-8 | decide | `tier0_consumer_recertification.md` | decide before any frontend work | No |
| **D-13** | Version control baseline | commit live tree T11 to a branch and copy `snap_*` manifests into the project / leave | HEAD tree empty, project untracked; rollback depends on single copies on `D:` | commit and copy | **Yes** for safe implementation |
| **D-14** | Authorise a scalability ladder (synthetic or WorldLarge) | yes / no | no evidence beyond 47 ports | decide separately; not needed for Oct 20 | No |
