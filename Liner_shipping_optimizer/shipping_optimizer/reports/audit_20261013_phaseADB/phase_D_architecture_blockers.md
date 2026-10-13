# Phase D — Architecture audit and blocker register (read-only)

Evidence labels as in Phase A.  "Source-read" = this audit read the cited file; "REPORTED" = taken from `reports/tasks_19_20_21/architecture_audit.md` (written against the
accepted tree) or the 2026-10-12 campaign and **not** re-derived.  Limits of this audit: no run, no profiling, no line-by-line read of the GA / regional-agent / LLM
modules; the stage trace for those stages is REPORTED.

## 1. Pipeline and data flow

```
data/raw/WorldSmall  --(src/data/network_loader.py: load_ports/demands/distance/fleet)-->  Port, Demand(weekly_teu, revenue_per_teu, max_transit_days), Fleet(capacity_teu ...)
OrchestratorAgent.process (orchestrator_agent.py)  3 iterations, best verified iteration reported
 ├ per region (3 clusters) RegionalAgent.process
 │    ServiceGeneratorAgent.generate_services  (sections A–F + demand loops + class screening + optional variants/operators)
 │    RegionalAgent._filter_services           (regional_filter.py, economic cap)           <- candidates removed before the global MILP
 │    HierarchicalGA (service GA + frequency GA)   regional hints only
 │    HubMILP (NetworkPlanner, fixed frequencies)  regional allocation / hints
 └ reconcile() (reconcile.py)  ONE global stage over the union of regional pools
      NetworkPlanner.plan (plan.py)  -> build_models (economics.py) -> build_paths (paths.py) -> solve_network (network_milp.py, CBC 120 s)
        -> [opt] local_search (local_search.py) -> flow_reopt (flow_reopt.py) -> repair_profit_floor -> [opt] prune_idle_services
        -> compute_ledger (ledger.py, independent recomputation) -> reconciliation / regional partition -> strategy_report / metrics
      -> result JSON / pipeline_output.json -> backend / frontend consumers
```

| # | Stage | Module · function | Key constraint / behaviour | Label |
|---|---|---|---|---|
| 1 | discovery + load | `network_loader.py::load_*`, `_check_dataset_identity` | explicit paths, no fallback dataset; foreign-port rejection; blank canal fee ⇒ `None` (not 0) | Source-read |
| 2 | validation | `_non_negative`, `_positive`, duplicate OD / distance checks | raise `DataValidationError`; `TransitTime` must be positive finite | Source-read |
| 3 | normalisation | `load_demands`: `weekly_teu = FFE·k`, `revenue_per_teu = Revenue_1/k` | `k` = per-lane factor (default 2.0, six WorldSmall ODs use 1.85–2.1) | Source-read |
| 4 | candidates | `service_generator_agent.generate_services`, `demand_coherent`, `route_operators`, `class_variants` | budgets: demand loops 60/region, standard sizes, top-10 hubs ×20 spokes (REPORTED) | REPORTED |
| 5 | class screening | `class_screening.ClassScreener` k = 1 | one economically best class per rotation (+ time-feasible fix) | Source-read (config), REPORTED (effect) |
| 6 | regional filter | `regional_filter.py` | cap `filter_max_services` (508/405/499), loops/elites/operators exempt | Source-read |
| 7 | global selection | `network_milp.solve_network` | variables `f_s` (int), `n_s` (int), `q_p`, `u_d`; LP relaxation → restrict to LP-support services → integer solve | Source-read |
| 8 | vessels / frequency | `economics.py`, `service_feasibility.required_vessels` | `n = ceil(T·f/7)`, `f` integer ≥ 0, fleet per class | Source-read |
| 9 | flows | MILP `q_p`, then `flow_reopt` over ALL valid paths | leg capacity `cap·f` on every leg | Source-read |
| 10 | paths | `paths.build_paths` | direct, 1-transfer, 2-transfer (where < `multi_hop_min_alternatives`=1 alternatives, plus through operated services); cap 10/OD, fastest first | Source-read |
| 11 | transit / dwell | path build + ledger | end-to-end days = ride + port stays + `transfer_dwell` (48 h + 3.5 d = 5.5 d per transfer) ≤ `TransitTime` | Source-read |
| 12 | accounting | `economics.py` / `ledger.py` | profit = revenue − hire − fuel − port fixed − handling − transshipment − port variable; rejection penalty 0 | Source-read |
| 13 | independent ledger | `ledger.compute_ledger` | recomputed from raw matrix / fleet / ports, NOT from service models | Source-read |
| 14 | feasibility / status | `plan.py`, `reconcile.py` | `optimal` only if restricted MILP closed AND no service dropped; else `feasible` | Source-read (docstring) |
| 15 | output | `reconcile`, `strategy_report.py`, `metrics.py`; frontend | `capacity_unit` string states "TEU (… read as TEU; provisional)" | Source-read |

Duplicate calculations: cycle time / vessel count / fuel are computed in `economics.py` (service model) and again in `ledger.py` (by design, "independent") and in
`tests/test_orchestrator.py::_recompute_network` (third copy).  **All three share the loader's converted quantities** → see B-03.

## 2. Coverage and unserved demand

* **Unit of coverage:** TEU/week — `coverage_pct = served_teu / demand_teu`; `demand_teu = 276,446.8` for the whole of WorldSmall (VERIFIED: column in the CSV; equals
  2·138,247 FFE − 47.2).  Not OD counts.
* **Population:** all 1,764 OD rows (no eligibility filter).  ODs with an unattainable limit (41 ODs, 3.37 % of demand) stay in the denominator.
* **Diagnostic attribution (REPORTED, `architecture_audit.md` §4, strategy report, mean of 10 seeds, batch M5):** unserved demand by *principal reason* — not
  economic to open a service 60.7 %, class inventory exhausted 7.8 %, no time-feasible service in the pool 4.6 %, time limit physically unattainable 3.4 %, leg capacity
  exhausted 2.2 %, not profitable per TEU < 0.2 %.  These are a **single principal reason per unserved TEU** (a partition by construction of the report), not independent
  counters — the categories "rejected by transit time" (no time-feasible service) and "excluded by regional/economic filter" are *not* separately attributable:
  a TEU cut by the regional cap shows up as "not economic" or "no service in the pool" depending on what survives (INFERRED).
* **Missing diagnostics:** (i) cargo lost to the **per-OD path cap** (paths exist but were dropped; not attributed), (ii) cargo lost to the **regional filter cap** before
  the global stage (pre-filter class composition not recorded — assumption A14), (iii) counterfactual value of the unserved cargo ("not economic" is relative to the
  incumbent's weekly costs, not an absolute economic verdict).

## 3. Network architecture: what is optimised jointly vs fixed upstream

| Decision | Status | Evidence |
|---|---|---|
| Which candidate services operate (`f_s ≥ 1`) | **joint** (MILP), over a pool fixed upstream | `network_milp.py` |
| Weekly frequency `f_s`, vessels `n_s` | **joint, integer** | docstring variables |
| Vessel class of a rotation | **upstream heuristic**: class screening k = 1 chooses the best stand-alone class; alternatives only via opt-in class variants | `class_screening.py` |
| Rotation shape / hub | **upstream**: a hub is not a decision variable; hubs emerge from which rotations were generated (top-10 hub detection, 2 best hubs for feeders, loops of 3–5 ports) | REPORTED `architecture_audit.md` §2.1 |
| Direct vs feeder vs hub mix | **outcome**, not a target: only `direct_ratio` acts on generation; labels `hub_and_spoke` / `feeder` are descriptive | REPORTED |
| Feeder-to-mainline capacity | **joint through flows**: a transfer path rides two services, consuming leg capacity on both; capacity itself comes from which pool members open | Source-read |
| 1- and 2-transfer paths | **joint (selection) over an enumerated, capped set**; 2-transfer paths enumerated only for ODs with < 1 shorter alternatives, pool 24/OD, 4 legs per hub | `PathConfig` defaults (Source-read) |
| Per-OD path set | **upstream cap 10, ranked by transit time (a constraint, so no economic information)** | `DEFAULT_MAX_PATHS_PER_OD`, `SELECT_FASTEST` |
| Local search / flow re-opt / repair | **post-processing heuristics** after the MILP (add/drop/freq moves with exact LP) | `local_search.py`, `flow_reopt.py` |

Conclusion (INFERRED from the above): the system optimises *flows, frequencies and vessel counts* jointly, but **hub choice, rotation structure, vessel class and the
path pool are constrained by upstream heuristics**; the MILP bound applies to the capped, restricted model, not to the full LSNDP.

## 4. Path-cap and pool investigation

| Limit | Default | Where | Ranking | Evidence of loss | Bound applies to |
|---|---|---|---|---|---|
| `max_paths_per_od` | 10 | `paths.build_paths` | transit time, then port cost | seed 0: 53,086 valid / 12,326 kept (23 %); 997 of 1,764 ODs at the cap (REPORTED) | capped model only |
| regional `filter_max_services` | 508 / 405 / 499 | `regional_filter.py` | stand-alone economics | `cut_standalone_profit_max` is logged (`FilterReport`) but pre-filter class mix is not (A14) | pre-filter pool not visible |
| demand-loop budget | 60 / region | `demand_coherent.py` | seeded growth from the 80 strongest ODs | tuning sweep peaked at 60 (comment in code, 5 seeds) | – |
| multi-hop pool | 24 / OD, 4 legs / hub | `PathConfig` | cheapest first | 1.5–2.4 % of served TEU; 0 of 90 unreachable ODs rescued (REPORTED) | – |
| LP-guided restriction | all services used by the relaxation | `network_milp.py` | LP support | status is never `optimal` if a service was dropped | restricted model |
| class variants (opt-in) | fraction 0–1 | `class_variants.py` | stand-alone floor | +0.56 M, 7/10 | – |

Whether the cap excludes economically useful paths is **not shown either way**.  Existing evidence: larger caps were intractable for CBC at 120 s (Tasks 14–16: cap 30,
"intractable for a 600 s MILP"); restriction-aware inclusion (`LINER_PATH_INCLUDE`) produced no plan on 60–80 % of seeds.  The measurement that would resolve it
(future authorised task): for the *final plan's* services, re-run `flow_reopt` (already uncapped over valid paths — it never lowers profit) and report the profit gain **by
path rank**; the existing `reopt_gain_usd` column (mean 1.5–6 M for the default arm) already shows that the capped MILP leaves large value on the table, which is
consistent with the cap, the CBC incumbent quality, or both (HYPOTHESIS — not separable from existing evidence).

## 5. Vessel, frequency and fleet constraints

* Inventory per class (24/29/68/74/58/10); `Σ n_s ≤ inventory_c` (Source-read, MILP docstring).
* Cycle time `T` = sailing at the class `designSpeed` (no speed optimisation) + port stays, "declared whole days"; `n = ceil(T·f/7)`; capacity `cap·f` TEU on every leg.
* Integer `f` ≥ 1 per operated service; no fortnightly services (A10, UNVERIFIED).  Long thin routes are expensive under this granularity (REPORTED P1).
* Idle/unused vessels: **no credit and no cost** — the objective has no "unused vessel profit" term (grep of `src/network` found none).  The paper's accounting
  credits unused vessels at the TC rate (RL paper Table 1, Eq. 34).
* Class eligibility: screening can drop a class for a rotation by a *heuristic* (stand-alone profit), not a physical constraint; with class variants Feeder_450 is operated
  at load factor 0.82–0.91, so the heuristic had suppressed a class that is useful at the margin (REPORTED).
* Joint choice of service / class / frequency: frequency and vessels yes; class only among offered candidates.

## 6. Profit and cost accounting

| Term | In MILP objective | In independent ledger | Unit / note |
|---|---|---|---|
| Revenue `q·rev_per_teu` | yes | yes | USD/TEU = Revenue_1 / k (gross invariant) |
| Vessel hire `n·TC·7` | yes | yes | TC daily from `fleet_data.csv` |
| Fuel `f·(sea_days·bunker_t + port_days·idle_t)·price` | yes | yes (tonnes recomputed) | 600 USD/t uniform |
| Port-call fixed `f·ΣPortCallCostFixed` | yes | yes | per call |
| Handling (origin load + destination unload) | yes (in path cost) | yes | `CostPerFULL / 2` per TEU |
| Transshipment | yes | yes | `CostPerFULLTrnsf / 2` per TEU |
| Port variable `PortCallCostPerFFE / 2` | yes — **per TEU of cargo** (paths.py:20–22; ledger.py:291–301) | yes | paper charges `pv × vcap` per vessel call (Eq. 35) — **different basis** |
| Rejection penalty | 0 (`unserved_penalty_per_teu = 0`) | never | paper: 1000 USD per rejected FFE |
| Unused vessels | none | none | paper: credited at TC rate |
| Canal fees | blank = unknown (`None`), loaded as non-charged (A12 PROVISIONAL) | – | |

Double counting / omissions found: none in the internal formulas (REPORTED agreement < 1e-6).  Optimistic assumption candidates: capacity read as TEU is the *pessimistic*
direction (capacity understated if the column is FFE); dwell 3.5 d is sensitive (±2–3 M).  A positive profit is a *ledger* statement under this convention only; it is not
comparable with a penalised benchmark objective.

## 7. Solver and scalability evidence

| Quantity | Value | Label |
|---|---|---|
| Size (seed 0, production pool) | 1,166 candidates; 53,086 valid paths, 12,326 in the model; integer problem ≈ 7.1 k variables (3.3 k with C1) | REPORTED |
| Solver / budget / threads | CBC, 120 s, single thread | VERIFIED (CSV, 160 rows) |
| Termination | `feasible` in 160/160 plans; **never `optimal`** | VERIFIED (CSV) |
| Bound gap (incumbent vs LP bound) | default arm 70.2 – 71.9 % mean; with C1 4.2 – 8.8 % | VERIFIED (CSV recompute) |
| Stage wall time | default 120.6–120.9 s; LS 113–114 s | VERIFIED (CSV) |
| Seed sensitivity | same config, same seeds, different load: up to 2.6 M (13.95 → 11.36 M, seed 12) | REPORTED + VERIFIED in CSV means (D-2) |
| Dominant stage | the global CBC solve (full budget); regional stage includes LLM provider back-off (`all_providers_failed`), 3 s → 32 s per region | REPORTED |
| Memory, model-build time breakdown | not recorded in the CSV | UNKNOWN |

Scalability: the only operational evidence is WorldSmall (47 ports, 1,764 ODs).  Candidate generation and path enumeration grow with ports² (ODs) and with
hubs·spokes²; the MILP variable count grows with paths.  **No inference to 1,000+ ports is made.**

Scalability evidence-gap list (future authorised task): port count, OD count, candidate services, valid / kept paths, MILP variables / constraints / nonzeros, model-build
time, solve time and gap, peak memory, candidate-generation time, flow-reopt time, ledger time — measured on a ladder of instances that varies *size* with density held
fixed, and *density* with size held fixed, each at a fixed time limit **and** to a fixed gap, so algorithmic cost is separated from the 120 s cutoff.

## 8. Result correctness and consumers

* Verification chain: MILP objective = ledger profit (< 1e-6, REPORTED), hard-feasibility checks (fleet, class, capacity, conservation, frequency, transit, transfer),
  regional partition, `optimal` only when nothing was dropped.  Gate scan: 495/495 solved plans pass (REPORTED).
* Presentation risks (REPORTED unless noted):
  * `not_solved` / negative-profit incumbents occurred on loaded machines (B0: −5.6 M on one of ten seeds; 18 of 40 `not_solved` in a degraded batch); the repair contains this but a
    `not_solved` iteration is still possible.
  * Coverage-floor mode skips the profit-floor repair (`plan.py:212`): a loss-making plan (−8.69 M, 6 assertions failed) was produced end-to-end.
  * Tier-0 consumer defects T0-1…T0-8 (null margin handling, two verdict sources, 20 % vs 25 % bands) are `NOT_VERIFIED` (`tier0_consumer_recertification.md`).
  * `strategy_report.py` labels the capacity unit "TEU … provisional" (Source-read) — the provisional flag exists but a consumer that shows only coverage / profit will not show it.
  * LLM providers returned `all_providers_failed` in every campaign orchestrator run; narrative output is the deterministic fallback.

## 9. Ranked blocker register

| ID | Area | Description | Evidence | Conf. | Impact | Quantification | Root cause | Minimal remedy | Risk / trade-off | Depends on | Validation needed | Pri | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **B-01** | units | `Capacity FFE` is used as TEU capacity while demand is converted FFE→TEU (×2) | `network_loader.py:114–140, 675`; RL paper p.15 A.1 "maximum number of FFEs", p.9 "capacity of 800 FFEs"; LINERLIB README states no unit | Strongly supported (paper) / Unknown (primary) | profit, coverage, utilisation, benchmark validity | levels ×1.6–2.5 (S2: 19.7 / 38.1 M vs 12.3 / 15.3 M, n = 3) — REPORTED | the column unit was never sourced; code chose provisional TEU | `capacity_teu = 2 × Capacity FFE` at the loader boundary, after owner confirmation; update `test_capacity_units.py` status with the source | all absolute numbers change; Feeder_450 economics shift; default found no plan in 120 s on 1 of 3 seeds at ×2 | owner decision; B-03 | targeted loader / invariance tests (Phase B §5); orchestrator; paired 10-seed batch | **P0** | **Owner** (D-01) |
| **B-02** | benchmark | No fair comparison with the RL paper is possible: our objective differs (no rejection penalty, no unused-vessel credit, integer `f`/`n`, end-to-end transit limits + 5.5 d transfer dwell, cargo-based port variable cost, 24 h stay vs 1 day, `Capacity` unit) | paper §3 p.3, Eq. 28–35 p.16–17, Table 1 p.9; `network_milp.py` | Confirmed (source) | benchmark validity | NOT MEASURED | different problem variant | define an explicit "paper mode" (flag-selected objective/constraint set) and report both | two code paths to maintain | B-01 | reproduce paper's Baltic/WAF only under owner authorisation | **P0** | Owner (D-02) |
| **B-03** | validation | Independent ledger and the test recomputation share the loader's converted units → a unit error is *common-mode* and invisible to every ledger gate; per-lane FFE→TEU factors (1.75–2.1) are unsourced | `ledger.py` header; `FFE_TO_TEU_LANE_FACTORS`; six ODs affected (−47.2 TEU, −0.017 %) | Confirmed | correctness | 6 ODs, 3.1 k FFE-wk | by design | add a unit-contract test fed from raw FFE and an owner decision on lane factors (1 FFE = 2 TEU) | removing lane factors changes 6 ODs by ≤ 5 % TEU | B-01 | dimensional tests §5 of Phase B | **P0** | Owner (D-03) |
| **B-04** | solver | Incumbent quality: default CBC at 120 s ends with 70 % gap to the LP bound, never `optimal`; wall-clock sensitive (≤ 2.6 M run-to-run) | CSV recompute (gap 70–72 %; 4–9 % with C1) | Confirmed | profit, reproducibility, benchmark validity | +1.9 M (C1), +2.28 M (LS) already measured | weak LP relaxation, time-limited CBC | promote C1 and LS (owner), report gap in every result | seeds do not determinise CBC | owner D-05 | paired 20-seed batch on the live tree T11 | **P1** | Owner |
| **B-05** | economics | 60.7 % of unserved demand is "not economic to open a service"; integer weekly frequency makes thin long routes expensive; fortnightly service unsourced | `architecture_audit.md` §4; A10 | Strongly supported | coverage, utilisation | coverage 24.9 % default → 29.0 % final | frequency granularity + economics | owner confirms whether sub-weekly frequency is in scope; only then a model extension | structural change | A10 | model-level test, not parameter | **P1** | Owner (D-07) |
| **B-06** | candidates | Per-OD path cap 10 (fastest-first, no economic rank) keeps 23 % of valid paths; the MILP bound covers the capped model | `paths.py` | Strongly supported (existence), UNKNOWN (value lost) | profit | NOT MEASURED | tractability | measure value-by-rank (§4); consider economic/hybrid rank *only after* solver strengthened | cost-aware −6.5 M, adaptive −7.4 M under CBC | B-04 | rank-gain diagnostic | **P1** | Engineering |
| **B-07** | network design | Hubs / rotation shapes / vessel class are fixed by generators and screening; class variants (+0.56 M, 7/10) show the screening suppresses useful classes; pre-filter pool composition unrecorded | `class_screening.py`, A14 | Strongly supported | profit, coverage | +1.1 M dev, +0.56 M hold-out (inconclusive) | upstream heuristics | record pre-filter composition; decide on variants after | pool growth ↔ solver time | B-04 | A14 logging run | **P1** | Engineering |
| **B-08** | governance | No VCS baseline: HEAD tree empty, project untracked; rollback relies on single copies on `D:\liner_scratch`; live tree = T11 with no 20-seed paired batch (D-8) | git (VERIFIED), `INDEX.md` | Confirmed | reproducibility | – | repo history | commit the live tree to a branch (owner action), copy snapshots + manifests into the project | none | owner | hash check vs manifest | **P1** | Owner |
| **B-09** | data | Unrevised transit file in use (13.0 % of demand; 104 loosened by +10 d on average); 41 ODs (3.37 %) unservable at any speed; `TransitTime` end-to-end semantics unverified | `maritime_assumption_validation.md` A1/A2 | Confirmed (differences), UNKNOWN (semantics) | coverage | no measurable change n = 3 | file choice never decided | owner decides revised file | – | – | S1 re-run at n ≥ 10 | **P1** | Owner (D-04) |
| **B-10** | assumptions | Transfer dwell 3.5 d + 48 h, port stay 24 h, bunker 600 USD/t, fuel grade — provisional | A4–A7 | Confirmed (provisional) | profit ±2–3 M, coverage ±5 pp | S3/S4 REPORTED | no source | owner supplies convention | – | – | – | **P2** | Owner (D-06) |
| **B-11** | tests/docs | 29 documentation-drift tests failing, 9 regional tests held xfail; `paths.py` docstring says 1 transfer by default | `FINAL_suite.log`; source | Confirmed | reporting | – | drift | owner retires/re-specifies; fix docstring (comment only, later task) | – | – | – | **P2** | Owner |
| **B-12** | consumers | Tier-0 consumer defects and two verdict bands (20 vs 25 %) not dispositioned | `tier0_consumer_recertification.md` | Reported | reporting | – | – | owner decision then frontend fix | – | – | consumer execution | **P2** | Owner |
| **B-13** | reproducibility | `LINER_SEED` default OFF; CBC non-deterministic; unseeded GA | `rng.py`; R1/R2 | Confirmed | reproducibility | 2 of 18 seeded slots differed | wall clock | seed in experiments; report gap | – | – | R1-style pairs | **P2** | Engineering |
| **B-14** | coverage/ops | Coverage-floor mode skips profit repair and produced a loss-making plan | `plan.py:212` (REPORTED) | Reported | correctness | −8.69 M, 1 run | design | pass `floor_teu` into repair (future task) | – | – | ≥ 10 e2e runs | **P2** | Engineering |
| **B-15** | scalability | Nothing is known beyond 47 ports | §7 | Unknown | runtime | NOT MEASURED | – | future scalability ladder | – | – | gap list §7 | **P3** | Owner authorisation |
| **B-16** | LLM layer | No live LLM provider exercised (`all_providers_failed`) | campaign reports | Reported | profit narrative only | – | – | – | – | – | – | **P3** | – |

## 10. Recommended minimal implementation sequence (recommendation only)

1. **Unit contract (B-01, B-03)** — owner decision on the `Capacity FFE` unit and the lane factors; implement at the loader boundary; add the Phase B invariance tests *first*.
2. **Freeze a new baseline on the corrected units** (D-8, B-08): commit the tree, record hashes, run a 10-seed paired batch (default vs final candidate) on T11.
3. **Owner approval of local search (B-04)** — smallest change with the strongest evidence (20/20); C1 only with the expanded pool.
4. **Diagnostics before models (B-06, B-07)**: log pre-filter class mix and path-rank value (read-only instrumentation).
5. **Paper mode (B-02)** only after 1–2, as a separate, flag-selected objective.
