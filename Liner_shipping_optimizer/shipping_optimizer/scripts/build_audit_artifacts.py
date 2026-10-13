"""Emit the remaining Phase MA JSON artifacts.

Read-only with respect to src/, backend/, tests/, data/. Writes:
  MULTI_AGENT_ECONOMIC_METRIC_MATRIX.json
  MULTI_AGENT_METRIC_LINEAGE.json
  MULTI_AGENT_RL_COMPARISON_MATRIX.json
  MULTI_AGENT_DATASET_COMPARABILITY.json
  MULTI_AGENT_PAPER_TRACEABILITY.json

Every RL cell carries provenance "RL-REF" and is_verified: false, because the
RL engine's source does not exist in this repository. Comparability grades use
GREEN/YELLOW/RED/GRAY over the six-criterion test and are never inferred from a
shared field name.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MA = "multi_agent"
RL = "rl"
NOT_ESTABLISHED = "NOT ESTABLISHED"


# --------------------------------------------------------------------------- #
# 1. Economic metric matrix                                                   #
# --------------------------------------------------------------------------- #
ECONOMIC_METRIC_MATRIX = [
    {"metric": "weekly_profit", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "revenue - total_cost where total_cost = operating + fuel + port + transship",
     "ma_evidence": "orchestrator_agent.py:1015-1028 (aggregate_results)",
     "reconciles": True,
     "reconciliation_residual_usd": 5.96e-08,
     "note": "summary_metrics identity holds to IEEE-754 rounding. Regional rollup "
             "is exact. Per-service sum does NOT reconcile (see selected_services)."},

    {"metric": "revenue", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "sum_d( weekly_teu_d * revenue_per_teu_d ) at the notional level; "
                      "MILP-priced as sum_d( revenue_per_teu_d * flow[d,s] )",
     "ma_evidence": "orchestrator_agent.py:1019; hub_milp.py:294-300",
     "reconciles": False,
     "note": "weekly_teu AND revenue_per_teu are each multiplied by the FFE->TEU "
             "factor, so total revenue = factor^2 x raw. WorldSmall factor is "
             "uniformly 2.0 => 4.0x the raw FFE x Revenue_1 sum "
             "(264,870,100 -> 1,059,480,400). No cost component is scaled by 4. "
             "This is the largest single distortion in the economic model."},

    {"metric": "operating_cost", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "sum_s( service.weekly_cost * frequency ), weekly_cost a hardcoded heuristic",
     "ma_evidence": "hub_milp.py:305-309; service_generator_agent.py:127",
     "reconciles": True,
     "note": "Not derived from the dataset charter rate. The whole LINERLIB cost "
             "vocabulary (tc_rate_daily, panama_fee, suez_fee, idle_consumption) "
             "is loaded and never read."},

    {"metric": "fuel_cost", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "sum_s( calculate_weekly_fuel_cost(ports, dist, class, cycle) * freq )",
     "ma_evidence": "hub_milp.py:313-323; utils/fuel_cost.py:144,205,214",
     "reconciles": True,
     "note": "82.1% of total cost. Hardcoded Clarksons fuel table contradicts "
             "fleet_data.csv; bunker price 600 USD/t hardcoded; a silent 500 nm "
             "fallback enters for missing OD pairs (WorldSmall needs none)."},

    {"metric": "transship_cost", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "REPORTED uses flat 80.0 USD/TEU * flow; OBJECTIVE uses a "
                      "per-port tariff (0-1720 USD/TEU)",
     "ma_evidence": "hub_milp.py:477-479 (reported) vs 175-188, 326-329 (objective)",
     "reconciles": True,
     "note": "The optimised quantity and the reported quantity are different "
             "formulas. GA layers use yet another form: hub_ratio * satisfied * "
             "avg_rev * 0.05 (frequency_ga.py:201)."},

    {"metric": "port_cost", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "sum over routed demand of (handling + fixed + variable) tariffs",
     "ma_evidence": "hub_milp.py:335-353; hub_milp.py:341-353",
     "reconciles": True,
     "note": "The same handled quantity is appended once per port a service "
             "touches, so an N-port loop books N transshipment charges. Per-service "
             "sum (44,733,198) EXCEEDS the summary (18,664,030) by 2.4x - different "
             "aggregation stage."},

    {"metric": "total_cost", "unit": "USD/week", "class": "REPORTED METRIC",
     "ma_definition": "AMBIGUOUS - two different meanings in one artifact",
     "ma_evidence": "summary_metrics.total_cost = 827,053,181.50 (4 components); "
                    "decision_output.global_metrics.total_cost = 105,961,250.00 "
                    "(operating only, coordinator_agent.py:281)",
     "reconciles": False,
     "note": "The two differ by 721,091,931.50 (87.2%). This single field is the "
             "root cause of the profit_margin_pct divergence."},

    {"metric": "profit_margin_pct", "unit": "percent", "class": "REPORTED METRIC",
     "ma_definition": "AMBIGUOUS - profit/(profit+total_cost) with total_cost meaning "
                      "either all four components (26.4%) or operating cost only (73.6%)",
     "ma_evidence": "orchestrator_agent.py:1027 (26.4) vs coordinator_agent.py:281,316-318 (73.6)",
     "reconciles": False,
     "note": "docs/DATA_DICTIONARY.md:241 defines profit/(profit+cost)*100. The "
             "73.6% path violates that definition. Both appear in the SAME "
             "pipeline_output.json."},

    {"metric": "coverage", "unit": "percent", "class": "REPORTED METRIC",
     "ma_definition": "AMBIGUOUS - at least four distinct values for one run",
     "ma_evidence": "summary_metrics.coverage = global_demand_weighted_coverage = "
                    "satisfied/(satisfied+unserved) = 88.3692",
     "reconciles": False,
     "note": "sat+uns = 308,471.2 exceeds true total demand 276,446.8 by 32,024.4 "
             "TEU (11.6%), so the ratio divides quantities that are not a partition "
             "of demand. Regional average is 98.502. Per-region values are clamped "
             "(regional_agent.py:442) so Asia and Americas report a hardcoded 100.0 "
             "against true 91.8 and 83.6."},

    {"metric": "total_services", "unit": "count", "class": "REPORTED METRIC",
     "ma_definition": "count of MILP-selected services",
     "ma_evidence": "summary_metrics.total_services = 314; len(selected_services) = 308",
     "reconciles": False,
     "note": "A 6-record gap between the headline count and the enumerated list. "
             "The regional rollup of services_selected is exact."},

    {"metric": "utilization", "unit": "percent", "class": "NOT IMPLEMENTED",
     "ma_definition": "not computed or reported anywhere",
     "ma_evidence": "no utilization field in pipeline_output.json",
     "reconciles": None,
     "note": "Unused capacity enters the GA objectives only as a penalty "
             "(frequency_ga.py:192, service_ga.py:338), never as a reported metric. "
             "Any RL utilization figure is UNCOMPARABLE - nothing to compare."},

    {"metric": "unserved_demand", "unit": "TEU/week", "class": "REPORTED METRIC",
     "ma_definition": "sum over MILP hub clusters of unserved TEU",
     "ma_evidence": "regional_agent.py:439; summary_metrics.unserved_demand = 34,204.4",
     "reconciles": False,
     "note": "An independent sum over clusters that double-count cross-cluster OD "
             "pairs. Not reconciled against total_demand. Also inconsistent with "
             "uncovered_teu by roughly an order of magnitude."},

    {"metric": "rejected_demand", "unit": "TEU/week", "class": "NOT IMPLEMENTED",
     "ma_definition": "no such field; the analogue is unserved_demand",
     "ma_evidence": "-", "reconciles": None,
     "note": "Name mismatch alone makes this incomparable to an RL 'rejected' term."},

    {"metric": "annual_profit", "unit": "USD/year", "class": "DERIVED METRIC",
     "ma_definition": "weekly_profit * 52",
     "ma_evidence": "orchestrator_agent.py:1017",
     "reconciles": True,
     "note": "Holds exactly (52 is an integer multiplier, not a 365/7 fraction)."},
]


# --------------------------------------------------------------------------- #
# 2. Metric lineage                                                            #
# --------------------------------------------------------------------------- #
LINEAGE = [
    {"metric": "revenue", "path": [
        {"stage": "DATASET FIELD", "artifact": "Demand_WorldSmall_Fixed_Sep.csv:Revenue_1", "transform": "USD per FFE/week"},
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "network_loader.py:109 / generate_worldsmall_dataset.py:200", "transform": "x ffe_to_teu_factor (default 2.0)"},
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "network_loader.py:106 / :198", "transform": "FFEPerWeek x ffe_to_teu_factor (default 2.0)"},
        {"stage": "DERIVED METRIC", "artifact": "product", "transform": "volume x rate = factor^2 x raw = 4x raw"},
        {"stage": "REPORTED METRIC", "artifact": "summary_metrics.revenue", "transform": "1,123,118,273.58"}]},

    {"metric": "operating_cost", "path": [
        {"stage": "DATASET FIELD", "artifact": "fleet_data.csv:TC rate daily (fixed Cost)", "transform": "loaded into FleetClass at network_loader.py:194"},
        {"stage": "ENGINEERING CONVENTION", "artifact": "service_generator_agent.py:127,176-182", "transform": "DISCARDED - replaced by hardcoded weekly_cost heuristic"},
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "hub_milp.py:305-309", "transform": "sum weekly_cost * max(1,round(freq))"},
        {"stage": "REPORTED METRIC", "artifact": "summary_metrics.operating_cost", "transform": "105,961,250.0"}]},

    {"metric": "fuel_cost", "path": [
        {"stage": "DATASET FIELD", "artifact": "fleet_data.csv:Bunker ton per day at designSpeed", "transform": "loaded at network_loader.py:198"},
        {"stage": "ASSUMPTION", "artifact": "fuel_cost.py:20-62", "transform": "DISCARDED - replaced by hardcoded Clarksons table; bunker price 600 USD/t"},
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "fuel_cost.py:144,214", "transform": "distance/(speed*24*0.9) * consumption * price * (7/cycle_time)"},
        {"stage": "REPORTED METRIC", "artifact": "summary_metrics.fuel_cost", "transform": "679,167,991.51 (82.1% of total cost)"}]},

    {"metric": "profit", "path": [
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "hub_milp.py:358-373", "transform": "6 economic terms + coverage_reward shaping term"},
        {"stage": "DERIVED METRIC", "artifact": "hub_milp.py:471", "transform": "reported 'profit' = objective value, INCLUDING coverage_reward"},
        {"stage": "ENGINEERING CONVENTION", "artifact": "orchestrator_agent.py:1015-1028", "transform": "recomputed as revenue - total_cost (coverage_reward excluded)"},
        {"stage": "REPORTED METRIC", "artifact": "summary_metrics.weekly_profit", "transform": "296,065,092.08"}],
     "note": "The MILP's internal 'profit' and the reported 'weekly_profit' are "
             "different quantities by construction."},

    {"metric": "coverage", "path": [
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "coordinator_agent.py:297", "transform": "satisfied/(satisfied+unserved)*100"},
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "regional_agent.py:442-443", "transform": "min(satisfied,total_demand)/total_demand*100  [CLAMPED]"},
        {"stage": "IMPLEMENTED DEFINITION", "artifact": "orchestrator_agent.py:305", "transform": "correct denominator, computed then discarded at :992-1001"},
        {"stage": "REPORTED METRIC", "artifact": "summary_metrics.coverage", "transform": "88.9116"}]},

    {"metric": "profit_margin_pct", "path": [
        {"stage": "REPORTED METRIC", "artifact": "orchestrator_agent.py:1027", "transform": "profit/(profit+827,053,181.50)*100 = 26.4"},
        {"stage": "REPORTED METRIC", "artifact": "coordinator_agent.py:281,316-318", "transform": "profit/(profit+105,961,250.00)*100 = 73.6"},
        {"stage": "REPORTED METRIC", "artifact": "SYSTEM_TRUTH_REPORT.md:134-138", "transform": "0.0 - a third value, from a report, not the code"}]},
]


# --------------------------------------------------------------------------- #
# 3. RL comparison matrix                                                      #
# --------------------------------------------------------------------------- #
# The RL engine source (mcf/costs.py, policies/, env/, neural/, state/, actions/)
# does NOT exist in this repository. Only RL-REF (the reference .md) is available.
# Every RL cell is therefore provenance RL-REF, is_verified: false.
def rl_cell(rl_ref_section, rl_description, grade, rationale):
    return {"rl_ref_section": rl_ref_section, "rl_description": rl_description,
            "provenance": "RL-REF", "is_verified": False,
            "comparability": grade, "rationale": rationale}


RL_COMPARISON = [
    {"metric": "profit", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "revenue - (operating+fuel+port+transship)", "units": "USD/week",
            "term_membership": "4 cost terms; no idle/canal/charter-depreciation split",
            "demand_basis": "TEU (FFE x 2)", "fleet_basis": "263 (GA) / 300 (MILP)",
            "distance_basis": "data/raw/distance_dense.csv, nautical miles"},
     "rl": rl_cell("RL-REF F-series (economic formulations)",
                   "RL-side profit formulation per the reference document; exact term "
                   "list not re-verified against source", "RED",
                   "Shares the NAME only. Term membership differs (RL reports an idle "
                   "and canal cost vocabulary that MA does not implement at all) and "
                   "the demand basis is a different unit. Fails on term_membership "
                   "and demand_basis.")},

    {"metric": "revenue", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "volume x rate, both x FFE->TEU factor => 4x raw", "units": "USD/week",
            "term_membership": "single notional revenue term", "demand_basis": "TEU",
            "fleet_basis": "n/a", "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF revenue formulation",
                   "RL-side revenue definition; not re-verified", "RED",
                   "Units and scaling basis cannot be reconciled without the RL source. "
                   "MA's 4x unit-scaling of an unreported magnitude is a structural "
                   "difference that no amount of calibration can bridge.")},

    {"metric": "operating_cost", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "hardcoded size-scaled weekly_cost heuristic", "units": "USD/week",
            "term_membership": "one blended term; charter/depreciation/crew/overhead NOT separated",
            "demand_basis": "n/a", "fleet_basis": "263/300 vessel ceiling",
            "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF cost formulations",
                   "RL-side operating cost terms; not re-verified", "RED",
                   "MA's entire fleet cost vocabulary is loaded and unread (F-04). The "
                   "term sets cannot be shown to overlap.")},

    {"metric": "fuel_cost", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "hardcoded Clarksons table x hardcoded 600 USD/t bunker",
            "units": "USD/week", "term_membership": "bunker only; no canal fee",
            "demand_basis": "n/a", "fleet_basis": "vessel class lookup, ignores fleet_data",
            "distance_basis": "nautical miles, 500 nm fallback for missing pairs"},
     "rl": rl_cell("RL-REF fuel formulation",
                   "RL-side fuel terms; not re-verified", "RED",
                   "Different consumption source, different price basis, different "
                   "distance treatment. Fails units, term_membership and distance_basis.")},

    {"metric": "total_cost", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "AMBIGUOUS - 845,462,791.04 or 103,217,500.00 in the same artifact",
            "units": "USD/week", "term_membership": "4 terms (or 1, at the coordinator)",
            "demand_basis": "n/a", "fleet_basis": "n/a", "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF total cost",
                   "RL-side total cost; not re-verified", "GRAY",
                   "MA is not even internally single-valued here. No comparison is "
                   "possible until MA resolves its own definition.")},

    {"metric": "profit_margin_pct", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "AMBIGUOUS - 24.5% or 72.7%", "units": "percent",
            "term_membership": "derived, not independent", "demand_basis": "n/a",
            "fleet_basis": "n/a", "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF margin definition",
                   "RL-side margin definition; not re-verified", "GRAY",
                   "Derived from an ambiguous numerator/denominator pair on the MA side. "
                   "Cannot be compared while MA carries two values.")},

    {"metric": "coverage", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "AMBIGUOUS - satisfied/(satisfied+unserved); per-region clamped",
            "units": "percent", "term_membership": "served demand only",
            "demand_basis": "TEU, but sat+uns exceeds true demand by 11.7%",
            "fleet_basis": "n/a", "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF coverage definition",
                   "RL-side coverage definition; not re-verified", "RED",
                   "A coverage ratio whose numerator and denominator are not a "
                   "partition of the same demand set cannot be compared to any other "
                   "coverage ratio.")},

    {"metric": "demand (total)", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "Demand_WorldSmall_Fixed_Sep.csv x factor, or JSON x factor x DEMAND_SCALE=6",
            "units": "TEU/week", "term_membership": "FFE x lane-specific factor",
            "demand_basis": "two incompatible loaders",
            "fleet_basis": "n/a", "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF demand base",
                   "RL-side demand base; not re-verified", "YELLOW",
                   "The underlying WorldSmall CSV is byte-identical between the two "
                   "systems (MD5 68f75334...). The divergence is entirely in "
                   "post-load transformation, which is inspectable and fixable. This "
                   "is the most reconcilable of the RED cells.")},

    {"metric": "distance matrix", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "data/raw/distance_dense.csv (62,002 rows) and "
                         "WorldSmall/dist_dense.csv (2,162 rows)",
            "units": "nautical miles", "term_membership": "Distance, Draft, IsPanama, IsSuez",
            "demand_basis": "n/a", "fleet_basis": "n/a",
            "distance_basis": "identical to RL master's matrix content"},
     "rl": rl_cell("RL-REF distance base",
                   "RL master's distance matrix", "GREEN",
                   "Content-identical (62,002 rows, 208 ports, 43,056 unique OD; MD5 "
                   "differs only by an added UTF-8 BOM). WorldSmall subset: 2,162 pairs, "
                   "0 missing, 0 duplicate, 0 asymmetric. The only true GREEN cell.")},

    {"metric": "fleet", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "fleet_world_small.csv quantities (263); specifications loaded but unread",
            "units": "vessels", "term_membership": "quantity only is binding",
            "demand_basis": "n/a", "fleet_basis": "GA 263, MILP 300 - INCONSISTENT",
            "distance_basis": "n/a"},
     "rl": rl_cell("RL-REF fleet model",
                   "RL-side fleet model; not re-verified", "YELLOW",
                   "The quantity file is byte-identical (MD5 e5117772...). MA's own "
                   "internal 263-vs-300 inconsistency is a defect to fix on the MA "
                   "side; it is not a difference between the two systems.")},

    {"metric": "utilization", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "NOT COMPUTED", "units": "-", "term_membership": "-",
            "demand_basis": "-", "fleet_basis": "-", "distance_basis": "-"},
     "rl": rl_cell("RL-REF utilization",
                   "RL-side utilization if defined", "GRAY",
                   "MA produces no utilization metric. There is nothing to compare; "
                   "this is an MA gap, not a cross-system difference.")},

    {"metric": "network structure / services", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "candidate rotations generated at runtime, hub/loop/feeder/trunk archetypes",
            "units": "services", "term_membership": "ports + weekly_cost + capacity + cycle_time",
            "demand_basis": "top-demand corridors", "fleet_basis": "capacity->class lookup only",
            "distance_basis": "NOT USED in generation"},
     "rl": rl_cell("RL-REF action space",
                   "RL-side action space; not re-verified", "RED",
                   "MA's candidate space is generated structurally with no distance, "
                   "canal, draft or duration feasibility check. The two search spaces "
                   "are not known to overlap.")},

    {"metric": "objective / control signal", "criterion_test": [
        "definition", "units", "term_membership", "demand_basis", "fleet_basis", "distance_basis"],
     "ma": {"definition": "profit_first: 10.0*profit_n + 0.01*coverage_n + 0.1*cost_n "
                         "(hardcoded, normalization.py:114-118)",
            "units": "dimensionless", "term_membership": "3 normalised components",
            "demand_basis": "TEU", "fleet_basis": "263/300", "distance_basis": "via fuel"},
     "rl": rl_cell("RL-REF reward",
                   "RL-side reward; not re-verified", "RED",
                   "Different search paradigm and a different signal. Fails on "
                   "definition and units. MA's own weights are additionally inert "
                   "(F-23): the configured weights are never read.")},
]


# --------------------------------------------------------------------------- #
# 4. Dataset comparability                                                     #
# --------------------------------------------------------------------------- #
DATASET_COMPARABILITY = {
    "verdict": "DATA LAYER IS RECONCILABLE; POST-LOAD TRANSFORM DIVERGES",
    "method": "MD5 and line-diff comparison against the RL master's data files, "
              "recomputed by this audit",
    "files": [
        {"file": "data/raw/demand_world_small.csv", "instance": "WorldSmall",
         "rows": 1764, "md5": "68f75334f57975c19b8a6b1a3da199ea",
         "rl_counterpart": "Demand_WorldSmall_Fixed_Sep.csv",
         "relation": "BYTE-IDENTICAL", "divergence": None,
         "note": "The CSV is a verbatim copy. MA does not rescale the file; the "
                 "x2 happens downstream in the JSON generator and the CSV loader."},
        {"file": "data/raw/distance_dense.csv", "instance": "WorldLarge",
         "rows": 62002, "unique_od": 43056, "duplicate_od": 17169, "ports": 208,
         "rl_counterpart": "dist_dense.csv", "relation": "CONTENT-IDENTICAL",
         "divergence": "MD5 differs only by an added UTF-8 BOM; line diff is empty",
         "note": "17,169 duplicated OD pairs resolved by last-write-wins at "
                 "network_loader.py:144, silently. Distances differ between "
                 "duplicate copies - this is an unlogged data ambiguity."},
        {"file": "data/raw/WorldSmall/dist_dense.csv", "instance": "WorldSmall",
         "rows": 2162, "unique_od": 2162, "duplicate_od": 0,
         "rl_counterpart": "WorldSmall subset of dist_dense.csv",
         "relation": "EXACT SUBSET", "divergence": None,
         "note": "0 missing, 0 duplicate, 0 asymmetric pairs. The cleanest data "
                 "asset in the repo. WorldSmall needs no 500 nm fallback."},
        {"file": "data/raw/fleet_world_small.csv", "instance": "WorldSmall",
         "rows": 6, "md5": "e51177722ca32220efb040c156366887",
         "rl_counterpart": "fleet_WorldSmall.csv", "relation": "BYTE-IDENTICAL",
         "divergence": None,
         "note": "Quantities only. 263 vessels. Bindings: Feeder_450=24, "
                 "Feeder_800=29, Panamax_1200=68, Panamax_2400=74, "
                 "Post_panamax=58, Super_panamax=10."},
        {"file": "data/raw/WorldSmall/fleet_data.csv", "instance": "WorldSmall",
         "rows": 6, "md5": "fc3618fe9b2ab6cb1cdc3ef53e72df28",
         "rl_counterpart": "fleet_data.csv", "relation": "BYTE-IDENTICAL",
         "divergence": None,
         "note": "Vessel SPECIFICATIONS. Loaded into FleetClass then read by nothing "
                 "(F-04). TC rate daily, Panama fee, Suez fee, idle consumption, "
                 "bunker consumption, speeds and draft are all unused."},
        {"file": "data/raw/ports_world_small.csv", "instance": "WorldSmall",
         "rows": 47, "md5": "5c9ed9b014b4e4e0a850afe719d75301",
         "rl_counterpart": "ports_world_small.csv", "relation": "BYTE-IDENTICAL",
         "divergence": None,
         "note": "47 ports, a strict subset of the 435-row WorldLarge ports file."},
    ],
    "unit_reconciliation": {
        "dataset_unit": "FFE (forty-foot equivalent units) per week",
        "ma_effective_unit": "TEU per week",
        "conversion": "lane-specific multiplier, default 2.0, table at "
                      "network_loader.py:74-91 (26 keys, 2 unreachable due to a "
                      "literal space in 'CNSHA-USA NY' / 'JPTYO-USA NY')",
        "effect_on_revenue": "volume and unit rate are BOTH multiplied, so total "
                             "revenue scales by factor^2 = 4.0x for WorldSmall",
        "measured": {"raw_sum_ffe_x_revenue": 264870100,
                     "json_sum_weekly_teu_x_revenue_per_teu": 1059480400,
                     "ratio": 4.0},
        "rl_unit": "unknown - the RL source is absent. Marked NOT ESTABLISHED.",
    },
    "comparability_matrix": [
        {"dimension": "ports", "status": "GREEN", "basis": "byte-identical files"},
        {"dimension": "demand file (raw)", "status": "GREEN", "basis": "byte-identical"},
        {"dimension": "distance matrix", "status": "GREEN", "basis": "content-identical, clean subset for WorldSmall"},
        {"dimension": "fleet quantities", "status": "GREEN", "basis": "byte-identical"},
        {"dimension": "fleet cost specifications", "status": "YELLOW",
         "basis": "byte-identical, but MA never reads them - the data is available "
                  "for a cost-model repair without touching any other system"},
        {"dimension": "unit of demand", "status": "RED",
         "basis": "MA converts FFE->TEU lane-specifically AND squares it into revenue"},
        {"dimension": "vessel specifications", "status": "RED",
         "basis": "MA substitutes a hardcoded Clarksons table for the dataset's own "
                  "bunker consumption"},
    ],
}


# --------------------------------------------------------------------------- #
# 5. Paper traceability                                                        #
# --------------------------------------------------------------------------- #
PAPER_TRACEABILITY = [
    {"paper_ref": "Brouer, Desaulniers & Pisinger (2014), 'A solution method for the "
                  "Liner Shipping Network Design Problem', Transportation Science 48(2):281-312",
     "role": "BENCHMARK DATASET PROVENANCE",
     "ma_element": "data/raw/*.csv - WorldSmall and WorldLarge instances",
     "traceability": "CONFIRMED",
     "evidence": "The WorldSmall demand, fleet and ports files are byte-identical to "
                 "the RL master's copies of the LINERLIB instances.",
     "caveat": "This is DATA provenance only. It does not establish that the MA "
               "objective, constraints or reported metrics correspond to anything "
               "in the paper."},

    {"paper_ref": "Dutta, Lin & Jin (2024), arXiv:2411.09068v1",
     "role": "RL REFERENCE",
     "ma_element": "The comparison target of this audit",
     "traceability": "NOT ESTABLISHED - SOURCE ABSENT",
     "evidence": "No RL source code exists in this repository. Only the reference "
                 "document RL_ENGINE_ARCHITECTURE_FORMULATIONS_ECONOMIC_INTEGRITY.md "
                 "is available.",
     "caveat": "Every RL cell in this audit is cited from that document and is "
               "explicitly marked not independently re-verified. No claim about "
               "what the RL engine computes is made from primary evidence."},

    {"paper_ref": "Clarksons Research (2024) vessel fuel consumption figures",
     "role": "EXTERNAL ASSUMPTION SOURCE",
     "ma_element": "src/utils/fuel_cost.py:20-62 VESSEL_FUEL_CONSUMPTION",
     "traceability": "CONTRADICTS THE DATASET",
     "evidence": "Feeder_450: 15 t/day hardcoded vs 18.8 in fleet_data.csv. "
                 "Super_panamax: 100 vs 126.9 t/day. Post_panamax capacity 5000 "
                 "vs 4200 TEU.",
     "caveat": "An external commercial reference silently overrides the benchmark "
               "dataset that defines the instance. This must be a deliberate, "
               "cited modelling choice or removed."},

    {"paper_ref": "docs/DATA_DICTIONARY.md (internal normative specification)",
     "role": "PROJECT-OWNED DEFINITION SOURCE",
     "ma_element": "weekly_teu, revenue_per_teu, profit_margin_pct and the regional "
                   "result schema",
     "traceability": "PARTIALLY VIOLATED",
     "evidence": ":241 defines profit_margin_pct = Profit/(Profit+Cost)*100; the "
                 "coordinator's 72.7% path divides by operating cost only. The "
                 "document never mentions FFE, the FFE->TEU conversion, or "
                 "DEMAND_SCALE - the largest transformations in the pipeline are "
                 "undocumented.",
     "caveat": "This is the document a reader would consult. Its silence on the "
               "x2 and x6 factors is why the revenue distortion went unnoticed."},

    {"paper_ref": "docs/BENCHMARKS.md",
     "role": "REPORTED RESULTS SOURCE",
     "ma_element": "Headline benchmark figures",
     "traceability": "STALE - DESCRIBES A DIFFERENT RUN",
     "evidence": "Claims to source all values from pipeline_output.json but reports "
                 "435 ports, 5 regions, $901,690,372 profit and 52.5% coverage "
                 "against the artifact's 47 ports, 3 regions, $275,077,114 and "
                 "88.3692%. Also quotes 'Revenue per TEU $4,587' and 'Cost per "
                 "TEU $3,461' - fields that do not exist in the artifact and are "
                 "not reproducible under any denominator tested.",
     "caveat": "The document declares itself the single runtime truth and is not."},

    {"paper_ref": "SYSTEM_TRUTH_REPORT.md",
     "role": "REPORTED RESULTS SOURCE",
     "ma_element": "Profit margin, region count",
     "traceability": "SELF-CONTRADICTORY",
     "evidence": "Quotes this run's exact profit ($275,077,114) but reports margin "
                 "0.0%; lists 'RegionalAgent (x5)' against a 3-region artifact; "
                 "dated 2026-06-18 while quoting a 2026-09-30 run; concludes 'Can "
                 "the system be truthfully certified? NO' under its own title.",
     "caveat": "Must not be cited as a results source."},

    {"paper_ref": "docs/architecture/PIPELINE_OUTPUT_CONTRACT.json (snapshot 2026-08-26, "
                  "baseline_commit a44b987)",
     "role": "STRUCTURAL CONTRACT",
     "ma_element": "Frozen key sets and structural expectations",
     "traceability": "VIOLATED BY THE CURRENT ARTIFACT",
     "evidence": "Declares 5 regional results; the artifact has 3. "
                 "FROZEN_REGION_KEYS excludes ga_telemetry and milp_telemetry, which "
                 "all 3 regions carry. Working tree is at dbc5997, not a44b987.",
     "caveat": "The artifact's own test_scorecard claims 265 assertions passed, 0 "
               "failed - so these contract tests cannot have run against this "
               "artifact, or ran before the telemetry fields were added."},

    {"paper_ref": "reports/worldsmall_p4_p5_validation_summary.md and the "
                  "worldsmall_* report series (2026-09-12 to 2026-09-13)",
     "role": "PRIOR AUDIT TRAIL",
     "ma_element": "WorldSmall data validation (P4/P5)",
     "traceability": "SUPERSEDED BY THE CURRENT ARTIFACT",
     "evidence": "These reports record weekly profit $262.6M (HubMILP optimal) and "
                 "a 297-service run at 89.58% coverage. The current artifact is "
                 "$275.08M, 309 services, 88.3692%. A separate "
                 "worldsmall_service_generation_optimization_audit.md records a "
                 "third run: $267.55M, 297 services, 89.58%, and 35 of 297 "
                 "negative-profit services in the final JSON.",
     "caveat": "The RL reference document's MA-side figures (527 services, 46.5% "
               "coverage, 78.6% margin) are stale by a further generation. Any "
               "comparison anchored to them is anchored to a superseded run."},
]


def write(name, obj):
    dest = ROOT / name
    dest.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    print("wrote", name)


def main():
    write("MULTI_AGENT_ECONOMIC_METRIC_MATRIX.json", {
        "generated_by": "scripts/build_audit_artifacts.py",
        "artifact_under_audit": "pipeline_output.json",
        "instance": "WorldSmall (47 ports, 1764 lanes, 263 vessels)",
        "metric_count": len(ECONOMIC_METRIC_MATRIX),
        "metrics": ECONOMIC_METRIC_MATRIX,
    })

    write("MULTI_AGENT_METRIC_LINEAGE.json", {
        "generated_by": "scripts/build_audit_artifacts.py",
        "convention": "Each path lists the stages a metric passes through, from the "
                      "dataset column to the reported field. A stage marked DISCARDED "
                      "means the dataset value is loaded and then ignored.",
        "metric_count": len(LINEAGE),
        "lineage": LINEAGE,
    })

    write("MULTI_AGENT_RL_COMPARISON_MATRIX.json", {
        "generated_by": "scripts/build_audit_artifacts.py",
        "rl_source_status": "ABSENT - the RL engine's source code (mcf/costs.py, "
                            "policies/, env/, neural/, state/, actions/) is not present "
                            "in this repository. All RL cells derive from RL-REF only.",
        "grade_vocabulary": ["GREEN", "YELLOW", "RED", "GRAY"],
        "grade_definitions": {
            "GREEN": "All six criteria satisfied and verified from primary evidence.",
            "YELLOW": "Data agrees; the divergence is in post-load transformation, "
                      "which is inspectable and correctable.",
            "RED": "At least one criterion fails structurally (definition, term "
                   "membership or unit basis differs and cannot be reconciled by "
                   "recalibration).",
            "GRAY": "Not established. Either one side does not define the metric, or "
                    "the metric is ambiguous on the MA side, so no comparison exists.",
        },
        "prohibition": "Comparability is never inferred from a shared field name. "
                       "Per spec section 18, two metrics called 'profit' are not the "
                       "same metric merely because they share a name.",
        "comparison_count": len(RL_COMPARISON),
        "grade_summary": {
            g: sum(1 for c in RL_COMPARISON if c["rl"]["comparability"] == g)
            for g in ["GREEN", "YELLOW", "RED", "GRAY"]
        },
        "comparisons": RL_COMPARISON,
    })

    write("MULTI_AGENT_DATASET_COMPARABILITY.json", {
        "generated_by": "scripts/build_audit_artifacts.py",
        **DATASET_COMPARABILITY,
    })

    write("MULTI_AGENT_PAPER_TRACEABILITY.json", {
        "generated_by": "scripts/build_audit_artifacts.py",
        "reference_count": len(PAPER_TRACEABILITY),
        "references": PAPER_TRACEABILITY,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())