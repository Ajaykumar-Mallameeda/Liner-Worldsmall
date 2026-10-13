# Task 8B — region-aware bunker fuel pricing

**Status: PARTIAL.** The pricing *model*, its snapshot format, validation, per-service resolution, ledger verification and
tests are complete and verified (orchestrator 332/332 in the default mode at the gate and 342/342 in the final code; the regional mode runs end to end and verifies
with zero violations). What is **not** complete is source-backed *data*: only 5 of the 47 WorldSmall ports have a direct
observation (public pages, one day, no licence to redistribute) and there is no licensed regional feed. The default pricing
therefore **remains the labelled legacy assumption, 600 USD/t uniform** — approved by the product owner as the
reproducibility benchmark (§7); the pinned market-price snapshot is a separate, explicitly selected scenario.

## 1. What the repository contained
Nothing but the 600 USD/t constant. Searched `src/`, `maritime/`, `backend/`, `data/`, `docs/`, `scripts/`, `legacy/`, `tests/`:
no price by port, region or hub; no fuel grade; no timestamp, currency or source; no ingestion or cache. The
LINERLIB documentation value (600 USD/t, "assumed") was the only price, used for every service in every region.
`fleet_data.csv` gives t/day at design speed and idle t/day for one speed per class — no consumption-versus-speed curve. None
was invented. WorldSmall has 47 ports; their `D_Region` column is a cost/region label, not a bunker market.

## 2. Design decision record

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Granularity | **named bunkering port** (UN/LOCODE) observations plus one **global reference**; no price is inferred from geography or from the `D_Region` label | the only evidence that links a service to a price is the ports on its rotation |
| 2 | Fuel grade | one grade per snapshot (**VLSFO** shipped); a run requests a grade (`BUNKER_FUEL_GRADE`) and a snapshot of another grade is rejected (`grade_mismatch`) | VLSFO / HSFO / MGO differ by roughly 10–95 % (Singapore: VLSFO 889.5 and MGO 1,281 on 9 Oct, HSFO 778 on 6 Oct; Rotterdam 6 Oct: HSFO 613 / VLSFO 682.5 / MGO 1,340); the fleet file states neither grade nor scrubbers, so VLSFO (compliant fuel, no scrubber) is an **assumption** |
| 3 | Source and timestamp | every price carries `observed_on`, `source`, `source_url`, `provenance ∈ {observed, derived, assumed}`; snapshot carries `as_of`, `max_age_days`, `currency`, `unit`, `licence_note` | auditability |
| 4 | Bunkering location | each service buys all its fuel at **one declared port: the cheapest observed bunkering port on its rotation** (tie → smallest UN/LOCODE), reported per service as `bunkering_port` | liners do bunker where it is cheap on a closed weekly loop; stated as an **optimistic bound**, never as "bought at every visited port" |
| 5 | Multiple ports | single declared port (above); the alternative rule `reference_only` prices every service at the reference (isolates *level* from *regional structure*) | simplest rule that is explicit |
| 6 | Regional aggregation | none is performed. The reference is a *published index* (Ship & Bunker Global 20 Ports Average) taken as is, not computed here | no multi-observation estimate is defensible from one day of public quotes |
| 7 | Staleness | (a) every observation within `max_age_days` of `as_of` at load; (b) `valuation_date` (default `as_of`, a **pinned** run input — never the wall clock) within `max_age_days` of `as_of` unless `allow_stale` | a replay must not start failing because time passed |
| 8 | Missing data | explicit `BunkerPriceError` with reasons; a rotation with no observed port uses the reference **only when** `fallback = "reference"` and records `basis = global_reference`; `fallback = "error"` rejects the candidate (`bunker_price_unavailable`); a price is never zero and never silently the legacy constant | stated requirement |
| 9 | Reproducibility | snapshot id + **SHA-256** of its canonical JSON are emitted in `network_ledger.assumptions.fuel_pricing`; the test recomputes the hash from the described entries | exact prices are pinned |
| 10 | Uncertainty | no probability claim; sensitivity = whole-snapshot scaling ×0.8 / ×1.2 and the `reference_uniform` ablation (§6) | the data support a level, not a distribution |

Units: only **USD per metric tonne**. Spellings (`USD/mt`, `$/MT`, `USD per metric tonne`) are *synonyms* and are normalised;
any other unit or currency is rejected — a conversion factor or FX rate would have to be invented.

## 3. Source provenance (the only prices in the repository besides the legacy constant)
Retrieved 2026-10-11 from public Ship & Bunker price pages; each page's latest row is labelled "F Oct 9". The pages show weekday
and month-day only: **the year 2026 is inferred** from the weekday (Friday 9 October is 2026) and the retrieval date. A secondary
report (ShipUniverse, 7 Oct) quoting Ship & Bunker's 6 Oct snapshot (Singapore 890.00, Rotterdam 682.50, Houston 745.50,
Fujairah 979.50, 20-port 876.50) agrees in level.

| Port / market | WorldSmall port | Grade | Price | Unit | Observed | Source (URL) | Provenance |
|---|---|---|---:|---|---|---|---|
| Singapore | SGSIN | VLSFO | 889.50 | USD/mt | 2026-10-09 | Ship & Bunker `/prices/apac/sea/sg-sin-singapore` | observed |
| Rotterdam | NLRTM | VLSFO | 715.00 | USD/mt | 2026-10-09 | Ship & Bunker `/prices/emea/nwe/nl-rtm-rotterdam` | observed |
| Hong Kong | HKHKG | VLSFO | 949.00 | USD/mt | 2026-10-09 | Ship & Bunker `/prices/apac/ea/cn-hok-hong-kong` | observed |
| LA / Long Beach | USLAX | VLSFO | 1,044.00 | USD/mt | 2026-10-09 | Ship & Bunker `/prices/am/nampac/us-lax-la-long-beach` | observed (market "LA/Long Beach" applied to port USLAX) |
| Santos | BRSSZ | VLSFO | 850.50 | USD/mt | 2026-10-09 | Ship & Bunker `/prices/am/samatl/br-ssz-santos` | observed (same quote repeated 6–9 Oct: indicative) |
| Global 20 Ports Average (reference) | — | VLSFO | 895.50 | USD/mt | 2026-10-09 | Ship & Bunker `/prices/av/global/av-g20-global-20-ports-average` | observed index, not a port price |

**Recorded per price** (fields of every observation in the snapshot, all part of the pinned hash): `price`, `observed_on`,
`provenance`, `source`, `source_url`, `note`, `bunkering_location`; the grade, unit and currency are snapshot-level fields
(VLSFO, `USD_per_metric_tonne`, `USD`). **Bunkering-location assumption:** every port price is a *port-level spot quote*
and is applied only to rotations that call at that port, on the declared rule "the whole rotation's fuel is bought
alongside the cheapest observed port it calls at" (an optimistic bound, §2 #4). The reference is a 20-port index, not a
purchase location; it prices only rotations that call at no observed port (`basis = global_reference`). Quote
`USLAX` is the "LA / Long Beach" market applied to the single WorldSmall port Los Angeles.

Snapshot `shipandbunker_vlsfo_2026-10-09`, file `data/pricing/bunker_snapshot_2026-10-09_vlsfo.json`,
SHA-256 `a03086668958f79009491600a6294efb90351e6520d739420d9fb6097beb5835`.
Outputs recorded **before** the `bunkering_location` field was added (`pricing_replay_U4_*`, `T8B_orch2_regional`) carry the earlier snapshot hash `fa39a8f206b3f41569cdece795017107482934f6b6c6a6dd79b017cfe5636f73`; the prices are identical, only the per-price location text is new. Every output labelled `FINAL*` carries `a03086668958…5835`.
Licensing/access: full markets and downloads require login/subscription; no reuse licence is stated on the pages and
`/terms` was not reviewed. The six figures are individual dated observations for audit and benchmark pinning, **not** a
redistributable dataset; clear the provider's terms before sharing the file. Nothing was scraped behind a paywall.
Not available legitimately: Antwerp, Hamburg, Port Said, Algeciras, Durban, Shanghai, Busan, Colombo, Port Klang, Jebel Ali,
Barcelona … (not on the free pages).

## 4. Implementation (all in `src/network/`; legacy path unchanged byte-for-byte when no pricing is configured)
| File | Change |
|---|---|
| `bunker_prices.py` (new) | `load_snapshot` (validation, hash), `FuelPricing` (`legacy_uniform` \| `regional_snapshot`), `resolve(rotation)`, environment configuration (`BUNKER_PRICING_MODE`, `BUNKER_PRICE_SNAPSHOT`, `BUNKER_FUEL_GRADE`, `BUNKER_LOCATION_RULE`, `BUNKER_FALLBACK`, `BUNKER_VALUATION_DATE`, `BUNKER_UNIFORM_USD_PER_T`), `use_pricing()` override |
| `economics.py` | `EconomicsAssumptions.fuel_pricing`; `build_service_model` resolves the price per rotation (`ServiceModel.fuel_price_usd_per_t`, `fuel_price_basis`, `bunkering_port`); `fuel_cost_per_rotation = fuel_tonnes × price`; unresolved price → `ServiceModelError(bunker_price_unavailable, …)`; `assumptions_for_problem` applies the active pricing |
| `ledger.py` | `compute_ledger(..., fuel_prices={service_id: {"price": …}})`: tonnes are recomputed from fleet and distances; price per service from the map; a missing/invalid entry is `missing_fuel_price`, never the uniform price |
| `plan.py` | resolves each operated service's price from its own rotation (not copied from the model) and flags `fuel_price_mismatch` if model and ledger disagree |
| `reconcile.py` | emits `assumptions.fuel_pricing` (full pinned description), per-service `fuel_price_usd_per_t / fuel_price_basis / bunkering_port / price_observed_on` in `plan.services` |

Configuration reaches **every** consumer through `assumptions_for_problem`: the GA surrogates and `HubMILP` (via
`service_models_for`), the global MILP, the ledger and the report. A mis-configured regional request raises; it never
degrades to the legacy price (tested).

## 5. Verification
`tests/test_bunker_pricing.py` — 67 tests (65 pricing + 2 pinning the bunkering-location assumption), hand-computed on the synthetic A/B/C network (tonnes/rotation = 156.7778 t):

| Required test | Tests |
|---|---|
| 1 applicable port/region price | cheapest observed port, order/closing-port invariance, tie rule, reference when none observed |
| 2 grade and unit | `grade_mismatch`; unit synonyms normalised; `USD/bbl`, `USD/short ton`, `EUR/mt`, blank → `unsupported_unit` |
| 3 currency | `EUR` rejected, no FX invented |
| 4 pinned snapshot | hash independent of formatting/key order, changes with a price; `describe()` pins id+hash |
| 5 missing price | invalid/zero/negative/NaN/bool/str prices; `fallback=error`; no reference + no hub; regional mode without a path → error, never legacy |
| 6 stale/incompatible | observation older than `max_age_days`; future date; valuation date beyond limit unless `allow_stale`; default valuation date is the pinned `as_of` |
| 7 same inputs in optimiser and ledger | ledger fuel = Σ f × tonnes × model price; `fuel_prices` map used; missing/invalid entry → violation; zero departures cost nothing |
| 8 mathematically expected change | +60 USD/t on the hub with frequencies fixed → Δfuel = 2 × 156.7778 × 60, Δprofit = −Δfuel, revenue and hire unchanged |
| 9 legacy reproduces baseline | `legacy_uniform(600)` = default assumptions = 94,066.67 per rotation |
| 10 no change to physics | sea days, cycle, tonnes, vessels, capacity, speed identical across modes |

Orchestrator (`tests/test_orchestrator.py` §N.7b recomputes the per-service price from the pinned block with its own
resolver — no `src.network` import — and checks the snapshot hash):

| Run | Mode | Assertions | Notes |
|---|---|---|---|
| `T8B_orch1_legacy` | legacy_uniform 600 | **332 / 332** | profit 2.57 M, margin 9.3 %, 9 services, 35 vessels, 0 violations |
| `T8B_orch2_regional` | regional_snapshot | 337 / 339 | verified, 0 violations, profit **0.148 M**, 1 service (Post_panamax DEBRV-NLRTM-MYTPP at 715 USD/t via NLRTM), coverage 1.65 %; the 2 failed assertions are "[Asia] / [Europe] Services selected > 0" — an honest outcome, not relaxed |

## 6. Controlled evaluation (same captured candidate pool, demand, fleet, solver; only the price changes)
Captured inputs: `evidence/inputs/U4_global_inputs.pkl` (SHA-256 `a5c603f9…4114f`, 3 global-stage calls, 1,082–1,096
candidates). Production strategy (LP-guided restriction), single-threaded CBC, USD/week:

| scenario | call 0: profit / cov % / services / vessels | call 1 | call 2 |
|---|---|---|---|
| legacy 600 uniform | 1.99 M / 11.0 / 13 / 53 | 2.62 M / 9.0 / 10 / 50 | **4.21 M** / 10.1 / 11 / 42 |
| every service at the reference 895.5 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| **regional snapshot** (cheapest observed port, else 895.5) | 0.12 M / 1.6 / 1 / 9 | 0.41 M / 1.9 / 2 / 8 | 0.15 M / 1.6 / 1 / 8 |
| regional ×0.8 (sensitivity) | 0.93 M / 3.7 / 3 / 26 | 2.71 M / 9.6 / 11 / 51 | 2.16 M / 6.1 / 5 / 32 |
| regional ×1.2 (sensitivity) | 0 | 0 | 0 |

* Call 2 legacy reproduces **4,212,367** — the figure recorded for these inputs in `solver_findings.md` — so the replay
  is the same experiment.
* **The empty plans are partly an artefact of the production restriction heuristic**, so the exact (unrestricted) integer
  optimum was computed for call 1: reference-uniform **$95,938/wk** (1 service, optimal), regional **$846,959/wk** (4 services,
  19 vessels, coverage 4.1 %, optimal, 53 s; the production strategy found 411,961), regional ×1.2 **$67,124/wk**. Under the
  observed October-2026 prices and the benchmark revenue base the WorldSmall network is *barely* viable: the exact
  optimum is $0.85 M/week at 4.1 % coverage versus $2.6–4.2 M at 600 USD/t.
* The unrestricted integer solve is **not** a better tool at 600 USD/t: it does not converge in 280 s (incumbent
  $987,198/wk, status `feasible`, 15 services) while the production LP-guided strategy reaches $2.62 M on the same
  pool. At the higher prices the unrestricted problem is small enough to close (optimal in 18–53 s). Both are
  recorded because the restriction heuristic and the pool jointly bound what any scenario can show.
* Fuel cost per rotation rises 19 % – 74 % (median +49 %) for the same services; the *ranking* of candidates by fuel cost
  is almost unchanged (Spearman 0.995; top-25 overlap 24/25, top-300 293/300): the regional spread (715–1,044 around a
  895.5 reference) matters far less than the price **level**. What changes is which services are worth operating: the 10
  legacy services and the 2 regional services have **no service in common**; the regional plan uses the Rotterdam-priced
  Post_panamax loop and a Feeder_800.
* Every scenario: 0 ledger violations, MILP = ledger (`reconciled = true`).

### 6b. The same comparison on the final default candidate pool (final code, captured inputs `FINAL_global_inputs.pkl`)
The §6 pool is the one *before* Tasks 9–10, which is why the market scenario looked like break-even. The final default
pool (demand loops 60 + class screening k = 1; 1,177 / 1,183 / 1,178 candidates, SHA-256 `7063f820…c08` in
`evidence/inputs/input_hashes.sha256`) was captured from a full orchestrator run and replayed with the final code —
same demand, fleet, pool and solver, only the price changes (full table: `evidence/comparisons/pricing_legacy_vs_market_captured_inputs.md`):

| scenario (USD/week, 3 calls) | call 0 | call 1 | call 2 | mean | exact optimum (unrestricted, proven) |
|---|---:|---:|---:|---:|---|
| legacy 600 USD/t | 8.52 M (18.7 %) | 9.06 M (19.7 %) | 8.87 M (19.8 %) | **8.82 M** | not proven in 300 s (incumbents 8.94 / 9.28 / 8.28 M) |
| **market snapshot (regional)** | 2.70 M (10.3 %) | 3.45 M (13.4 %) | 2.99 M (12.7 %) | **3.05 M** | 2.74 / 3.45 / 2.99 M — **optimal** |
| market ×0.8 (sensitivity) | 6.42 M | 7.31 M | 6.99 M | 6.91 M | — |
| market ×1.2 (sensitivity) | 0.41 M | 1.28 M | 0.90 M | 0.86 M | — |
| every service at the 895.5 reference | 1.10 M | 2.07 M | 1.72 M | 1.63 M | 1.10 / 2.07 / 1.72 M — optimal |

(in brackets: cargo coverage). Reading, without adjustment: on the final pool the market-price network is **profitable
but at about one third of the legacy-price profit** (≈ $3.1 M vs ≈ $8.8 M per week, coverage 10–13 % vs ~19 %), and a
20 % higher price level takes it to < $1.3 M. The legacy pool's near-break-even result of §6 was therefore partly a
property of that pool, not only of the price level. Every scenario: 0 ledger violations, MILP = ledger.

End-to-end, market-price mode (`BUNKER_PRICING_MODE=regional_snapshot`, final tree, unseeded; `evidence/runs/FINAL7_regional_run*`):
see the final report §11 for the three runs; the first run completed **349 / 349** assertions (342 + the regional-pricing
checks), verified, profit $4.54 M/week (13.8 % margin), 10.5 % coverage, 8 services — higher than the replayed 3.05 M.
A likely reason is that the pool of that run was itself generated and optimised under the market price (the GA
surrogates and the generator receive the price through `assumptions_for_problem`), whereas the replayed pool was built
under 600 USD/t; this was not isolated here. No price, revenue or constraint was adjusted in any of these runs.

## 7. Why the default stays 600 USD/t — approved decision
The demand file's revenues are the LINERLIB benchmark's, calibrated to its own 600 USD/t. Pricing fuel at **2026-10 spot**
(~895 USD/t) against that revenue base mixes vintages: it measures "what if this 2010s revenue were earned at today's fuel",
not a profitability forecast, and it takes the network from +$2.0–4.2 M to ≈ $0.1–0.4 M per week on the legacy pool and
from ≈ $8.8 M to ≈ $3.1 M per week on the final default pool (§6, §6b). Making it the default would change
the business meaning of every reported profit, which the mission contract reserves for an explicit decision. So:
* default = `legacy_uniform` **labelled `assumed`** (the reported `fuel_pricing.provenance`); no behaviour change;
* region-aware mode is one environment line away, pinned and verified;
* **Decision (approved by the product owner, 2026-10-11):** (a) USD 600/t stays the default **legacy benchmark** for
  reproducibility; (b) the market-price scenario is a *separate, explicitly selected* scenario
  (`BUNKER_PRICING_MODE=regional_snapshot` + pinned snapshot) and revenue is **not** re-based to offset the higher
  prices; (c) USD 600/t is **not** described anywhere as the October-2026 market median — the repository holds no
  historical series that would support such a statement (it is the LINERLIB benchmark's own assumption);
  (d) every market price records source, grade, unit, observation date and bunkering-location assumption (§3).
  Option "re-base revenues" is deliberately not implemented. If the market-price scenario is near break-even or
  unprofitable (as in §6) that is reported as found — no price, revenue or constraint is adjusted.

## 8. Unresolved data dependencies
* A licensed, dated, multi-port bunker feed (≥ the 47 WorldSmall ports or their hubs) — blocked by data availability.
* Confirmation of fuel grade and scrubber fitting per class (not in `fleet_data.csv`).
* A consumption-versus-speed law (not in the source; not invented — sailing is at design speed only).
* The year on the public pages is inferred, not printed.
* The location rule is an assumption (optimistic bound); a multi-port purchase model needs bunkering-call data.
