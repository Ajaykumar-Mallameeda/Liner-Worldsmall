# Phase 6 — maritime and economic assumptions: evidence, status, and what each one is worth

**Rule applied.**  Nothing is called verified because the code uses it, and nothing is called wrong because a source is missing.  Each
assumption carries its evidence, an explicit status (`VERIFIED` / `PROVISIONAL` / `UNVERIFIED` / `CONTRADICTED` / `BLOCKED`) and, where a
number could move, a **measured sensitivity** taken on a copy of the tree with exactly that one value changed (never the production tree;
`evidence/tools/mksens_v3.py`, tree diffs in `evidence/outputs/S2_tree_diffs.json`).  Production defaults and the frozen baseline are
unchanged; no scenario below is a recommendation to change a default.  A result that improves when an assumption is relaxed is not
evidence for the relaxation.

**Scope and sources.**  WorldSmall only (no WorldLarge file was read).  Consulted: the project's own files and code; the LINERLIB GitHub
repository (README, file listing, `data/transittime_revision/` README and `Demand_WorldSmall_tt.csv`); Google's OR-tools shipping-benchmark
page for LSNDSP (`developers.google.com/optimization/service/shipping/benchmarks/lsndsp` — a *secondary* source describing a study that uses
LINERLIB); the DTU / INFORMS record of the benchmark paper (abstract only; the technical report was not obtainable here).  The LINERLIB
README itself states **no units** for any column and points to that technical report.  The earlier campaign evidence on bunker prices
(`reports/overnight_tasks_8_9_10/`) is quoted, not re-collected.

## 1. Register

| # | Assumption | Current interpretation | Evidence | Status | Model impact (measured, §2) | Recommended action |
|---|---|---|---|---|---|---|
| A1 | unit of `TransitTime` | days; the OD's **maximum end-to-end transit time**; read unchanged by the loader (`network_loader.py`, `max_transit_days`) | Upstream revision README: revised pairs are exactly "the origin-destination pairs where a direct sailing at 14 knots average speed is not possible within the allowed transit times".  Reading the local column as days and testing `distance / (14 kn × 24) > TransitTime` flags **115 of 1,764 ODs: 105 are exactly the 105 ODs whose value differs in the upstream revised file** (upstream says 106), plus 10 others.  Under an hours reading only 8 ODs are sailable (`evidence/outputs/A1_transit_unit_check.csv`) | **VERIFIED** (unit; by reproducing the upstream rule — no source states it in words).  **UNVERIFIED** (whether the number includes port stays and transfer dwell: the model charges both against it) | 41 ODs / 3.37 % of demand have a limit below the pure sailing time at the fastest class and are unservable under any network | owner: confirm in the LINERLIB technical report that `TransitTime` is end-to-end including port time |
| A2 | which transit file | the file loaded is `Demand_WorldSmall_Fixed_Sep.csv` (original transit times); the upstream *revised* file is not used | `transittime_revision/` holds `Demand_WorldSmall_tt.csv`; the benchmark page: "As suggested by the LINERLIB authors, [we] only present results using revised transit times".  Local vs revised: **105 ODs = 13.0 % of demand differ; the revision loosens the limit in 104 (mean +10.0 d)**; quantities and revenues identical (the 7 quantities that look different upstream are the thousand-separator truncation `Fixed_Sep` corrects).  No document in the repository records a decision for or against the revision | **CONTRADICTED** (relative to the authors' recommendation; the repository records no reason for the choice) | **S1: no measurable change**: fin − base +3.49 M (ref +3.03 M), 3/3 seeds; levels within ±0.5 M of the reference (below the ≈ 1 M noise of load patterns) | owner decision: adopt the revised file as the benchmark input, or document why not.  Not changed here |
| A3 | `Capacity FFE` | used directly as **TEU** capacity; demand `FFEPerWeek` × 2 → TEU | No document defines the unit; the benchmark page says only "containers".  If the column is FFE, capacity in TEU is 2 × the loaded value while demand is already × 2 — capacity understated by a factor 2 relative to demand | **UNVERIFIED** (provisional model assumption, documented in `network_loader.py`) | **S2: levels change by a factor 1.6 – 2.5** (default 19.7 M, final 38.1 M; the default model finds **no plan at all** on seed 0 in 120 s, the final candidate does: 39.7 M).  Ranking unchanged: fin > base on every solved pair | owner: resolve the unit from the technical report; until then every absolute profit figure carries this caveat |
| A4 | port stay / minimum transshipment time | 24 h at every call; 48 h per transfer | benchmark page: "Minimum port stay time: 24 hours for all ports", "Minimum transshipment time: 48 hours for all ports" (12-h time discretisation).  Not in the canonical WorldSmall files.  Does not vary by class / port in any source | **VERIFIED** against the secondary source; **PROVISIONAL** as to the primary data | S3a 12 h: fin − base +4.83 M; S3b 48 h: +1.92 M (3/3 each); 48 h lowers the default to 11.5 M and coverage to 23 % | keep 24 h; resolve against the technical report |
| A5 | transfer dwell | each transfer = 48 h minimum + **3.5 d** expected wait = **5.5 d**, added **once per transfer** (twice for a two-transfer journey), applied to the end-to-end limit only (no cost) | `economics.py`: "the expected wait for a connecting weekly departure (half a week)"; `paths.py` (`transfer_dwell_days`, `2 × dwell`); the independent ledger recomputes the same convention from the raw assumptions (reported as `transit` violations 0 in every plan).  No source defines the 3.5 d | **PROVISIONAL** (model convention, labelled; not sourced) | S4a 1.75 d: +2.32 M, coverage +5.2 pp; S4b 7.0 d: +2.44 M, default coverage falls to 18.1 %, services 15 (default) / 23 (final) | keep 3.5 d; do not relax to buy coverage; owner to supply the operating convention |
| A6 | bunker price | uniform **600 USD/t** | benchmark page: "Bunker cost: 600 USD per metric ton".  Tasks 8 – 10: the demand file's revenues are the benchmark's own, calibrated to that price; the dated regional snapshot (Ship & Bunker public page, VLSFO, 6 observations, 2026-10-09, `a0308666…5835`) covers 5 of 47 ports, **no licence to redistribute was found**, and is not the default | **VERIFIED** as the benchmark's value; **not a market price** | B400: fin − base +5.64 M (level 16.7 / 22.3 M); B1000: the network collapses to 2 – 4 services (1.06 / 1.59 M, 4 – 5 % coverage) — the benchmark's revenues cannot pay for 1,000 USD/t | keep 600 for controlled comparisons; a market-price scenario needs a licensed series and re-based revenues |
| A7 | fuel grade, vessel fuel systems | price applies to an "assumed VLSFO-equivalent" for every vessel | `fleet_data.csv` carries consumption (t/day at design speed, idle) and no fuel grade, scrubber or dual-fuel field; the snapshot grade is VLSFO | **UNVERIFIED** (no data to test compatibility) | none measurable without data | owner: supply fuel-system data per class, or state the assumption in the benchmark documentation |
| A8 | consumption / price units | t/day × days × USD/t, consumption at design speed scaled by the model's speed rules | the independent ledger recomputes fuel from the same inputs and agrees to < 1e-6 relative in every plan | **VERIFIED** (internal consistency, not against measured consumption) | — | no fabricated consumption curve was introduced |
| A9 | rejection penalty | **none** in the objective: profit = revenue − cost | benchmark page: "Demand rejection penalty (or opportunity cost): 1000 USD for all demands"; the project reports operating profit (`unserved_penalty_per_teu = 0.0`) | **PROVISIONAL** (documented difference of metric, not a defect) | a constant per unserved container ranks plans by coverage; the project's profit levels are not comparable with the benchmark's published objective values | state the metric in every report (done); no change |
| A10 | integer weekly frequency | 1, 2, … departures per week, no fortnightly option | the benchmark page mentions only the 12-hour discretisation; no source defines the allowed frequencies | **UNVERIFIED** (modelling choice; a fortnightly service changes the structure, not a parameter) | not run (needs a model change, outside this campaign) | owner: confirm from the source whether sub-weekly-frequency services are in scope |
| A11 | per-FFE port-cost units (`CostPerFULL`, `CostPerFULLTrnsf`, `PortCallCostPerFFE`) | USD per FFE ÷ 2 → per TEU, same contract as revenue (total revenue invariant) | `network_loader.py` documents the contract; no upstream sentence confirms the per-FFE reading | **PROVISIONAL** | not run | resolve with A3 |
| A12 | canal fees (`panamaFee`, `suezFee`) | one fee per class and canal, charged when the route uses the canal (`dist_dense.csv` `IsPanama` / `IsSuez`) | the fleet file carries the fees; not re-derived in this campaign | **PROVISIONAL** | not run | independent re-derivation if canal routes matter to a decision |
| A13 | `Feeder_450` is (nearly) never operated | an economic outcome, not a data or screening error | §4 below | **VERIFIED** as an economic outcome of the stated data | the class variants operate it at load factor 0.82 – 0.91 where Feeder_800's inventory is exhausted | none |
| A14 | regional candidate filters do not suppress useful classes | not shown either way: the harness records only the post-filter class composition (Feeder_800 ≈ 83 % of the regional pool) | pre-filter composition was not recorded | **UNVERIFIED** (not measured) | the class variants add alternative-class candidates *after* the filter and are accepted on their measured effect (Phase 4) | record pre-filter class composition in the next run |

## 2. Sensitivity of the conclusion (`evidence/comparisons/S3_sensitivity.md`; generated by `evidence/tools/s3_table.py`)

Seeds 0 – 2 (a scenario table, not a statistical test); in each scenario the default (`base`) and the final candidate (`fin` = C1 + LS +
10 % class variants) run **concurrently** on the scenario tree `snap_S3_*` (T9 with one value changed).  Profit is the independent ledger's *under that
scenario's assumption*; levels are not comparable across rows — the difference within a row is the quantity of interest.

| scenario (one change) | pairs | no plan in 120 s (base / fin) | base M/wk | fin M/wk | Δ M | seeds higher | base cov % | fin cov % | Δ cov pp | base svc / ves | fin svc / ves |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| reference (production assumptions, batch D5) | 3 | 0 / 0 | 12.29 | 15.32 | +3.03 | 3/3 | 24.3 | 28.9 | +4.7 | 26 / 132 | 29 / 164 |
| S1 revised `TransitTime` (upstream file) | 3 | 0 / 0 | 11.82 | 15.31 | +3.49 | 3/3 | 23.6 | 29.2 | +5.6 | 24 / 130 | 30 / 170 |
| S2 `Capacity FFE` × 2 | 2 | **1** / 0 | 19.72 | 38.11 | +18.39 | 2/2 | 30.7 | 33.1 | +2.4 | 32 / 188 | 34 / 176 |
| S3a port stay 12 h | 3 | 0 / 0 | 11.28 | 16.11 | +4.83 | 3/3 | 30.2 | 30.7 | +0.5 | 36 / 176 | 36 / 177 |
| S3b port stay 48 h | 3 | 0 / 0 | 11.51 | 13.43 | +1.92 | 3/3 | 23.0 | 27.1 | +4.1 | 23 / 133 | 26 / 163 |
| S4a transfer wait 1.75 d | 3 | 0 / 0 | 13.81 | 16.12 | +2.32 | 3/3 | 25.1 | 30.4 | +5.2 | 26 / 133 | 33 / 170 |
| S4b transfer wait 7.0 d | 3 | 0 / 0 | 10.31 | 12.75 | +2.44 | 3/3 | 18.1 | 23.2 | +5.1 | 15 / 92 | 23 / 139 |
| B400 bunker 400 USD/t | 3 | 0 / 0 | 16.69 | 22.33 | +5.64 | 3/3 | 28.2 | 31.8 | +3.6 | 34 / 205 | 37 / 225 |
| B1000 bunker 1000 USD/t | 3 | 0 / 0 | 1.06 | 1.59 | +0.53 | 3/3 | 4.3 | 5.2 | +0.9 | 2 / 15 | 4 / 18 |

(Gate scan of the eight scenario batches: 48 plans started, 47 solved, **47 of 47** pass the ledger, zero-violation, reconciliation and regional-partition gates; the one plan without a result is the default on S2 seed 0.)

## 3. What the sensitivities imply

1. **The ranking is robust; the levels are not.**  In every one of the eight scenarios the final candidate beats the default on every solved
   pair (23 of 23; plus the one pair where the default has no plan at all).  The gain ranges from +0.5 M (when 1,000 USD/t leaves almost no
   network) to +18 M (doubled capacity).  Nothing in the acceptance evidence of Phase 5 depends on one of these assumptions being right.
2. **The absolute profit levels depend strongly on three unresolved inputs:** the capacity unit (A3, factor 1.6 – 2.5), the bunker price
   (A6, 1.1 – 22 M across 400 – 1,000 USD/t) and the port / transfer allowances (A4, A5, ±2 – 3 M).  The levels quoted in this campaign
   (≈ 12 M default, ≈ 15 M final) are *conditional on the documented provisional assumptions* and must be read that way.
3. **The revised transit file (A2) changes little in these seeds** (±0.5 M, within load-pattern noise): the 41 ODs below the pure sailing
   time stay unservable, and the loosened 104 ODs do not move the optimum measurably at n = 3.
4. **A robustness result the controlled comparison would not show:** with doubled capacity the *default* model found no plan on one of three
   seeds in 120 s (bound 79 M against 31 M with C1), while the strengthened model solved it.  The default's behaviour is fragile when the
   relaxation is loose; C1 (and the search) widen the range of data under which the 120-second solve delivers a plan.
5. **Not done, and why:** no model change was proposed or tested for A8 (fortnightly service), A7 (fuel systems) or A11 – A12 (units, canal
   fees): each needs data or a model extension outside this campaign.

## 4. Feeder_450: an economic outcome, not a data or screening error

Facts (evidence: `evidence/outputs/CLASS_econ_seed0.json`, `fleet_data.csv`; the stand-alone model is the canonical
`ClassScreener.evaluate_class`, 1,149 seed-0 rotations):

| class | inventory | capacity | hire USD/day | hire per slot-day | design kn | bunker t/day | fuel per slot-day @600 | all-in per slot-day at design speed | rotations with positive stand-alone profit | best stand-alone profit USD/wk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Feeder_450** | 24 | 450 | 5,000 | **11.11** | 12 | 18.8 | **25.07** | **36.18** | **8** | **190 k** |
| Feeder_800 | 29 | 800 | 8,000 | 10.00 | 14 | 23.7 | 17.77 | 27.77 | 44 | 899 k |
| Panamax_1200 | 68 | 1,200 | 11,000 | 9.17 | 18 | 52.5 | 26.25 | 35.42 | 35 | 890 k |
| Panamax_2400 | 74 | 2,400 | 21,000 | 8.75 | 16 | 57.4 | 14.35 | 23.10 | 56 | 1.92 M |
| Post_panamax | 58 | 4,200 | 35,000 | 8.33 | 16.5 | 82.2 | 11.74 | 20.08 | 31 | 2.92 M |
| Super_panamax | 10 | 7,500 | 55,000 | 7.33 | 17 | 126.9 | 10.15 | 17.49 | 10 | 3.04 M |

* Feeder_450 has the highest hire per slot-day (11.11 against 7.3 – 10.0 USD) and the highest **all-in** cost per slot-day at design speed
  (36.18 against 17.5 – 35.4 USD); on fuel alone only Panamax_1200 (26.25, an 18-kn design speed at 52.5 t/day) is above it (25.07), and
  Panamax_1200 has 2.7 × the capacity.  At 12 kn it is also the slowest class, so a given rotation needs more vessels per weekly sailing.
* It is therefore never the best class for a rotation with enough cargo, which is why the screening (k = 1: best class per rotation) rarely
  offers it (5 – 14 candidates per region in the seed-2 pool) and no recorded baseline plan operates it.
* It earns its place exactly where the model says it should: thin rotations whose cargo fits 450 TEU, and rotations whose cheaper class is
  out of inventory.  With the class variants the plans of this campaign operate it (final configuration: 1.6 vessels per plan on average;
  with the search-only variants 6.6), at load factors 0.82 – 0.91.
* Status: **VERIFIED as an economic outcome of the stated data** (hire, speed, consumption, capacity), consistent with the baseline plans
  (0 Feeder_450 vessels in each of the 20 default plans of D5 / H5).  What remains unverified is the *data* (A3: whether capacity is in FFE;
  if it is, every class doubles and the picture changes — S2).

## 5. What would resolve the open items

| open item | the evidence needed | who |
|---|---|---|
| A1 (what `TransitTime` includes), A3, A10, A11 | the LINERLIB technical report (Brouer, Pisinger, Sigurd — column definitions and units) or the authors' data dictionary | owner / data custodian |
| A2 | a decision to use `transittime_revision/Demand_WorldSmall_tt.csv` (and to record it), or a recorded reason not to | owner |
| A5 | the intended transfer operating convention (is 3.5 d an expectation, a bound or a bias?) | owner |
| A6, A7 | a licensed, dated bunker series by port and grade, and per-class fuel-system data; revenues re-based to it | owner / procurement |
| A12 | independent canal-fee schedule | owner |
| A14 | pre-filter class composition (one extra logged field in the next run) | engineering |
