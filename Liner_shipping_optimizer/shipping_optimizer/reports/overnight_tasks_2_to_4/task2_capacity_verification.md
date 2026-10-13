# Task 2 — Vessel-capacity unit (`Capacity FFE`)

**Gate: PASS — convention retained as PROVISIONAL, documented, propagated and tested. The unit is NOT verified.**
Next task authorized: yes (an unresolved source gap does not block Task 3; capacity feasibility stays conditional).

## 1. Question
`data/raw/WorldSmall/fleet_data.csv` has a column `Capacity FFE`. The model treats the value as per-vessel capacity in
TEU, unscaled. Is that right, or is the column FFE (so TEU capacity would be 2×)?

## 2. Evidence examined
| Source | What it says about the capacity unit |
|---|---|
| `fleet_data.csv` (canonical, 6 classes, tab-separated) | header `Capacity FFE`; values 450 / 800 / 1,200 / 2,400 / 4,200 / 7,500. Column name only, no unit definition |
| `fleet_WorldSmall.csv` | quantities only (24/29/68/74/58/10 = 263); class names agree with `fleet_data.csv` |
| LINERLIB README (`github.com/blof/LINERLIB`, fetched 2026-10-11) | "Fleet information is gathered in the file fleet_data.csv and contains all data on the 6 vessel types"; **no capacity unit stated**; demands are called "FFe" |
| Upstream `data/fleet_data.csv` (same repository) | same header and numeric values as the local file as rendered by the fetch tool. Establishes **provenance of the file**, not its unit |
| Google OR-tools LINERLIB benchmark page | lists assumptions (bunker 600 USD/t; min. port stay 24 h; min. transshipment 48 h; rejection penalty 1,000 USD); **no vessel-capacity unit** |
| Brouer et al., *Transportation Science* 48(2):281–312 (2014), doi:10.1287/trsc.2013.0471 | the document that would define it; **full text not retrievable here** (paywalled; the saved PDF I obtained was an unrelated conference paper whose text could not be extracted). **Not checked** |
| Repo documents (`MA_02`, `MA_05`, `reports/worldsmall_phase1_5_2_audit.md`, `reports/worldsmall_runtime_integration.md`) | restate the column name ("FFE"); one calls FFE "Freight Freight Equivalent". Derived, not authoritative |
| Loader / data model | `Capacity FFE` → `FleetClass.capacity_teu`, no scaling; the loader's demand conversion is FFE→TEU ×k, so demand and capacity are **not** converted symmetrically |

Not used as evidence (per the brief): the numeric magnitudes, the class-name suffixes, or which reading gives better profit.

## 3. Decision
No authoritative statement was found, so the decision rule's second branch applies: **retain** the established reading
(`Capacity FFE` used as TEU, no ×2), mark it provisional everywhere it matters, and do not scale.

What the choice implies, stated honestly:
* Demand is converted FFE→TEU (×≈2) but capacity is not. If the column really is FFE, every capacity in the model is
  **half** the true TEU capacity, i.e. the current reading is the conservative one for capacity feasibility.
* If it is TEU, the model is consistent.
* Not applied, only recorded: `unapplied_alternative = "capacity in TEU = 2.0 x the loaded value"`.

## 4. Where the value flows (trace) and what depends on it
```
fleet_data.csv "Capacity FFE"
  -> NetworkLoader.load_fleet            src/data/network_loader.py   (_positive(), no scaling)
  -> FleetClass.capacity_teu             src/optimization/data.py
  -> Fleet.capacity_unit / _status       "TEU" / "provisional"        (added in Task 2)
  -> [Task 3] evaluate_rotation          src/services/service_feasibility.py  -> Service.capacity
  -> Service.capacity consumers          regional_agent.py:162,168 (margin filter, ranking)
                                         service_ga.py:201,235,251,336   frequency_ga.py:98,154,187
                                         hierarchical_ga.py:90,128,129,209  flow_optimizer.py:30
                                         hub_milp.py:411,615
```
Before Task 3, `FleetClass.capacity_teu` had **no consumer**: services carried hard-coded capacity buckets. So no
pre-Task-3 result depended on this unit; every result after Task 3 does.

Conclusions that **cannot** be validated until the unit is confirmed: any per-leg or per-service capacity feasibility,
utilization, coverage-by-capacity, and the vessel count needed to carry a given demand.

## 5. Changes
| File | Change |
|---|---|
| `src/data/network_loader.py` | `CAPACITY_SOURCE_COLUMN`, `CAPACITY_INTERNAL_UNIT`, `CAPACITY_UNIT_STATUS="provisional"`, `CAPACITY_UNIT_PROVENANCE` (source, reason, evidence trail, unapplied alternative, `capacity_feasibility_is_conditional`); `load_fleet` records it in `validation_report["fleet"]["capacity_unit"]`, logs it at INFO and returns it on the `Fleet` |
| `src/optimization/data.py` | `Fleet.capacity_unit`, `.capacity_unit_status` (default `"provisional"`), `.capacity_source_column` |
| `tests/test_capacity_units.py` (new, 23 tests) | field read unscaled for all 6 classes (independent raw read); class identity across both files; status declared and carried to `Fleet`/`Problem`/report; invariant "verified requires a named authoritative source"; blank/0/negative/non-numeric/NaN/inf/missing-column rejected without a default class |

Not done on purpose: the frozen pipeline-output contract (`tests/architecture/test_output_contract.py`: top-level,
`summary_metrics`, region and service key sets) has no slot for an assumption flag, and `shared_context` is a structured,
audited object. Publishing the flag in `pipeline_output.json` needs a deliberate contract change, which is outside this
task. Until then the flag is visible on the `Fleet`, in the loader report, in each generated `Service`
(`capacity_unit_status`, Task 3) and in the candidate report — **not** in the final JSON.

## 6. Gate evidence
Same interpreter and commands as the frozen baseline (`evidence/environment` in Task 1).

| | Baseline S0 (unmodified tree) | Task 2 |
|---|---|---|
| `tests/test_orchestrator.py` | 258/264, 6 fail, exit 1 | 258/264, 6 fail, exit 1 |
| failing assertions | `Global weekly profit > 0`, `Network is profitable`, `Weekly profit > 0` ×2, `Annual profit > 0`, `Profit margin > 0` | identical six |
| weekly profit (unseeded, ±7 % noise) | −303,007,866 | −318,102,373 |
| services / coverage | 287 / 86.0 % | 288 / 83.9 % |
| rest of suite | 56 failed / 856 passed / 20 skipped / 8 xfailed | 57 failed / 878 passed / 20 skipped / 8 xfailed |

The one additional suite failure is `test_service_record_count_disagrees_with_headline`, an artifact-dependent
characterization test (asserts the listed-service count differs from the headline; this run listed 288 = 288). It flipped
between runs of unchanged code during Task 1 and is not caused by this change (the change is metadata only). +23 tests, all pass.

Patch: `patches/task2_capacity_unit.patch` (3 files, +267/−5).

## 7. Open
* To verify: obtain the LINERLIB paper's data section (or the DTU technical report 19.2010) and quote the vessel-capacity
  definition; then set `authoritative_source`, flip the status, and the invariant test will enforce the citation.
* Whether to publish the flag in the output contract (see §5).
