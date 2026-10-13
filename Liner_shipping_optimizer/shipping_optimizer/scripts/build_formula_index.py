"""Emit MULTI_AGENT_FORMULA_INDEX.json.

Read-only with respect to src/, backend/, tests/, data/. The formula records
below are transcribed from the source files cited in each `evidence` field;
this script does not re-derive them, it serialises the audit's findings so
tests/test_economic_metric_documentation.py can verify each cited line still
contains what the document claims.

Classification vocabulary (per the audit's source hierarchy):
  IMPLEMENTED DEFINITION | PAPER DEFINITION | DATASET FIELD | DERIVED METRIC
  ENGINEERING CONVENTION | ASSUMPTION | REPORTED METRIC | NOT IMPLEMENTED
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each entry: id, name, layer, classification, statement (the formula as written
# in the audit), code evidence (path, line, expected substring), notes.
FORMULAS = [
    {
        "id": "F01",
        "name": "Revenue per TEU (dataset path)",
        "layer": "data_loading",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "revenue_per_teu = Revenue_1 * ffe_to_teu_factor",
        "evidence": [{"file": "src/data/network_loader.py", "line": 109,
                      "expect": "revenue_per_teu = float(row[\"Revenue_1\"]) * ffe_to_teu_factor"}],
        "note": "Volume AND unit rate are both multiplied by the same factor, so "
                "total revenue is scaled by factor^2. See F02.",
    },
    {
        "id": "F02",
        "name": "FFE->TEU conversion factor lookup",
        "layer": "data_loading",
        "classification": "ENGINEERING CONVENTION",
        "statement": "ffe_to_teu_factor = FFE_TO_TEU_CONVERSIONS.get(f\"{origin}-{dest}\", 2.0)",
        "evidence": [{"file": "src/data/network_loader.py", "line": 103,
                      "expect": "FFE_TO_TEU_CONVERSIONS.get(lane_key, 2.0)"}],
        "note": "Table at network_loader.py:74-91 has 26 keys; two ('CNSHA-USA NY', "
                "'JPTYO-USA NY') contain a literal space and can never match. The "
                "majority of WorldSmall lanes therefore take the 2.0 default.",
    },
    {
        "id": "F03",
        "name": "Weekly demand volume",
        "layer": "data_loading",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "weekly_teu = FFEPerWeek * ffe_to_teu_factor",
        "evidence": [{"file": "src/data/network_loader.py", "line": 106,
                      "expect": "weekly_teu = float(row[\"FFEPerWeek\"]) * ffe_to_teu_factor"}],
        "note": "",
    },
    {
        "id": "F04",
        "name": "Legacy JSON demand scaling",
        "layer": "data_loading",
        "classification": "ENGINEERING CONVENTION",
        "statement": "d.weekly_teu *= DEMAND_SCALE  (DEMAND_SCALE = 6)",
        "evidence": [{"file": "src/data/network_loader.py", "line": 275,
                      "expect": "DEMAND_SCALE = 6"}],
        "note": "Applied unconditionally to whichever JSON is loaded; the instance "
                "auto-detection that would exempt WorldSmall lives only in the test "
                "harness, not in NetworkLoader.",
    },
    {
        "id": "F05",
        "name": "Port handling cost",
        "layer": "data_loading",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "handling_cost = CostPerFULL * 2.0",
        "evidence": [{"file": "src/data/network_loader.py", "line": 45,
                      "expect": "costperfull\"]) * 2.0"}],
        "note": "See F06-F08: three of four port cost columns are scaled, one is not.",
    },
    {
        "id": "F06",
        "name": "Port fixed call cost (UNSCALED)",
        "layer": "data_loading",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "port_call_cost = PortCallCostFixed   (no FFE->TEU scaling)",
        "evidence": [{"file": "src/data/network_loader.py", "line": 47,
                      "expect": "port_call_cost=float(row[\"portcallcostfixed\"])"}],
        "note": "The only port cost column NOT multiplied by 2.0.",
    },
    {
        "id": "F07",
        "name": "Transshipment port cost",
        "layer": "data_loading",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "transshipment_cost = CostPerFULLTrnsf * 2.0",
        "evidence": [{"file": "src/data/network_loader.py", "line": 48,
                      "expect": "costperfulltrnsf\"]) * 2.0"}],
        "note": "",
    },
    {
        "id": "F08",
        "name": "Variable port call cost",
        "layer": "data_loading",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "variable_port_call_cost = PortCallCostPerFFE * 2.0",
        "evidence": [{"file": "src/data/network_loader.py", "line": 49,
                      "expect": "portcallcostperffe\"]) * 2.0"}],
        "note": "",
    },
    {
        "id": "F09",
        "name": "Vessels required per service",
        "layer": "fleet",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "vessels_required = ceil(service.cycle_time * frequency / 7)",
        "evidence": [
            {"file": "src/optimization/hub_milp.py", "line": 149,
             "expect": "math.ceil(service.cycle_time * freq / 7)"},
            {"file": "src/optimization/frequency_ga.py", "line": 133,
             "expect": "math.ceil(self.problem.services[i].cycle_time * f / 7)"},
        ],
        "note": "Identical formula in the MILP and the GA; both are weekly-cadence.",
    },
    {
        "id": "F10",
        "name": "Fleet size constraint (MILP)",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "sum(vessels_used) <= fleet_size",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 389,
                      "expect": "total_vessels_used <= self.fleet_size"}],
        "note": "fleet_size defaults to 300 (hub_milp.py:61) and is never passed by "
                "regional_agent.py:363-373, so the MILP is constrained to 300 while "
                "the GA is constrained to 263. See D-F08.",
    },
    {
        "id": "F11",
        "name": "Sailing days",
        "layer": "fuel",
        "classification": "ENGINEERING CONVENTION",
        "statement": "sailing_days = distance_nm / (speed_knots * 24 * 0.9)",
        "evidence": [{"file": "src/utils/fuel_cost.py", "line": 144,
                      "expect": "0.9"}],
        "note": "The 0.9 is an implicit weather/inefficiency allowance.",
    },
    {
        "id": "F12",
        "name": "Missing-pair distance fallback",
        "layer": "fuel",
        "classification": "ENGINEERING CONVENTION",
        "statement": "total_distance += 500.0  when an OD pair is absent from the matrix",
        "evidence": [{"file": "src/utils/fuel_cost.py", "line": 205,
                      "expect": "500.0"}],
        "note": "Enters the fuel objective silently. WorldSmall needs no fallback "
                "(2,162/2,162 pairs present); WorldLarge would use many.",
    },
    {
        "id": "F13",
        "name": "Weekly fuel cost",
        "layer": "fuel",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "weekly_fuel_cost = cycle_fuel_cost * (7.0 / cycle_time_days)",
        "evidence": [{"file": "src/utils/fuel_cost.py", "line": 214,
                      "expect": "7.0 / cycle_time"}],
        "note": "",
    },
    {
        "id": "F14",
        "name": "Bunker price",
        "layer": "fuel",
        "classification": "ASSUMPTION",
        "statement": "BUNKER_PRICE_PER_TON = 600.0 USD/t",
        "evidence": [{"file": "src/utils/fuel_cost.py", "line": 62,
                      "expect": "600.0"}],
        "note": "Hardcoded. Not present in any dataset file.",
    },
    {
        "id": "F15",
        "name": "MILP revenue",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "revenue = sum_d( demands[d].revenue_per_teu * flow[(d,s)] )",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 295,
                      "expect": "revenue_per_teu * flow"}],
        "note": "",
    },
    {
        "id": "F16",
        "name": "MILP operating cost",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "operating_cost = sum_s( services[s].weekly_cost * max(1, round(freq[s])) )",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 305,
                      "expect": "operating_cost = sum("}],
        "note": "weekly_cost is a hardcoded heuristic in "
                "service_generator_agent.py, NOT derived from the dataset "
                "tc_rate_daily. No daily->weekly bridge exists.",
    },
    {
        "id": "F17",
        "name": "MILP fuel cost",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "fuel_cost = sum_s( calculate_weekly_fuel_cost(...) * max(1, round(freq[s])) )",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 313,
                      "expect": "fuel_cost = sum("}],
        "note": "",
    },
    {
        "id": "F18",
        "name": "MILP port handling cost",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "port_handling_cost = sum over routed demand of the per-port tariff",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 335,
                      "expect": "for (d, s), var in flow.items():"}],
        "note": "The same handled quantity is appended once per port a service "
                "touches (hub_milp.py:335-338), so a 5-port loop books 5x the "
                "single-transshipment charge.",
    },
    {
        "id": "F19",
        "name": "Uncovered-demand penalty (MILP)",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "unserved_penalty = alpha_unserved * sum_d(unserved[d]),  alpha_unserved = 300.0 USD/TEU",
        "evidence": [
            {"file": "src/optimization/hub_milp.py", "line": 59,
             "expect": "alpha_unserved: float"},
            {"file": "src/optimization/hub_milp.py", "line": 355,
             "expect": "RAISED to $300/TEU"},
        ],
        "note": "The GA layers use alpha_unserved = 50.0 "
                "(service_ga.py:63, hierarchical_ga.py:22) - a 6x disagreement "
                "between the layer that selects the chromosome and the layer "
                "that prices it.",
    },
    {
        "id": "F20",
        "name": "MILP profit objective",
        "layer": "milp",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "profit = revenue - operating_cost - fuel_cost - transship_cost "
                     "- port_handling_cost - unserved_penalty",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 358,
                      "expect": "profit_expr"}],
        "note": "See F21 - the reported 'profit' is this PLUS a coverage shaping term.",
    },
    {
        "id": "F21",
        "name": "Coverage reward shaping term",
        "layer": "milp",
        "classification": "DERIVED METRIC",
        "statement": "coverage_reward = (w_coverage / w_profit) * "
                     "(satisfied / total_demand_teu) * abs(operating_cost + 1)",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 367,
                      "expect": "coverage_reward = ("}],
        "note": "Added INTO the maximise objective (hub_milp.py:373) and included in "
                "the returned 'profit' (hub_milp.py:471). Non-linear in candidate "
                "operating cost, therefore not comparable across chromosomes and "
                "NOT an economic quantity.",
    },
    {
        "id": "F22",
        "name": "Reported transshipment cost (flat)",
        "layer": "milp",
        "classification": "REPORTED METRIC",
        "statement": "transship_cost_v = self.tc_per_teu * sum(flow)   with tc_per_teu = 80.0",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 477,
                      "expect": "transship_cost_v    = sum("}],
        "note": "The OBJECTIVE uses a per-port tariff "
                "(hub_milp.py:326-329, 0-1720 USD/TEU); the REPORTED figure uses the "
                "flat 80.0 constant. The reported number is not the optimised number.",
    },
    {
        "id": "F23",
        "name": "Reported total cost (MILP)",
        "layer": "milp",
        "classification": "REPORTED METRIC",
        "statement": "total_cost = operating_cost + fuel_cost + transship_cost + port_cost",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 509,
                      "expect": "total_cost_v"}],
        "note": "Excludes the unserved penalty that F20 subtracts.",
    },
    {
        "id": "F24",
        "name": "ServiceGA profit (8 terms)",
        "layer": "ga",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "profit = revenue - operating - fuel - transship - port "
                     "- unserved_penalty - overcap_penalty - alignment_penalty "
                     "- negative_service_penalty",
        "evidence": [{"file": "src/optimization/service_ga.py", "line": 340,
                      "expect": "profit"}],
        "note": "A different 9-term aggregation from the MILP's 6-term F20.",
    },
    {
        "id": "F25",
        "name": "ServiceGA revenue yield factor",
        "layer": "ga",
        "classification": "ENGINEERING CONVENTION",
        "statement": "yield_factor = 0.6 + 0.4 * (served / effective_capacity)",
        "evidence": [{"file": "src/optimization/service_ga.py", "line": 242,
                      "expect": "yield_factor"}],
        "note": "Revenue is discounted by load factor. No counterpart exists in the "
                "MILP objective, so the two layers price identical flow differently.",
    },
    {
        "id": "F26",
        "name": "ServiceGA fitness (production branch)",
        "layer": "ga",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "fitness = ObjectiveWeights('profit_first').calculate_weighted_score(normalized) "
                     "= 10.0*profit_n + 0.01*coverage_n + 0.1*cost_n",
        "evidence": [
            {"file": "src/optimization/service_ga.py", "line": 383,
             "expect": "self.objective_weights.calculate_weighted_score(normalized)"},
            {"file": "src/optimization/normalization.py", "line": 114,
             "expect": "PROFIT_FIRST_WEIGHTS"},
        ],
        "note": "Because CONFIG.objective_mode == 'profit_first' "
                "(optimizer_config.py:15), the w_profit/w_coverage/w_cost read at "
                "service_ga.py:83-85 (and written by consensus at "
                "orchestrator_agent.py:793-798) are used ONLY by the unreachable "
                "'legacy' branch at service_ga.py:372-378. See D-C01.",
    },
    {
        "id": "F27",
        "name": "FrequencyGA fitness (fuel omitted)",
        "layer": "ga",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "fitness = revenue - operating_cost - transship_cost "
                     "- overcap_penalty - port_cost",
        "evidence": [{"file": "src/optimization/frequency_ga.py", "line": 211,
                      "expect": "return revenue - operating_cost - transship_cost - overcap_penalty - port_cost"}],
        "note": "fuel_cost IS computed at frequency_ga.py:161-166 and then never "
                "subtracted here (only logged at :205-208). FrequencyGA therefore "
                "systematically over-values high-frequency long-haul services "
                "relative to ServiceGA, which does subtract fuel.",
    },
    {
        "id": "F28",
        "name": "FrequencyGA transshipment proxy",
        "layer": "ga",
        "classification": "ENGINEERING CONVENTION",
        "statement": "transship_cost = hub_ratio * satisfied * demands[0].revenue_per_teu * 0.05",
        "evidence": [{"file": "src/optimization/frequency_ga.py", "line": 201,
                      "expect": "0.05"}],
        "note": "Uses demands[0] - the FIRST lane's rate - as a network-wide average, "
                "and a hardcoded 5% factor. hub_ratio is clamped to [0.3, 0.7] "
                "(frequency_ga.py:197).",
    },
    {
        "id": "F29",
        "name": "Overcapacity penalty",
        "layer": "ga",
        "classification": "ENGINEERING CONVENTION",
        "statement": "overcap_penalty = beta * unused_capacity * (operating_cost / total_capacity)",
        "evidence": [
            {"file": "src/optimization/frequency_ga.py", "line": 192,
             "expect": "self.beta * unused_cap"},
            {"file": "src/optimization/service_ga.py", "line": 338,
             "expect": "self.beta * unused_cap"},
        ],
        "note": "beta = 0.015 (frequency_ga.py:28).",
    },
    {
        "id": "F30",
        "name": "Regional coverage (clamped)",
        "layer": "reporting",
        "classification": "REPORTED METRIC",
        "statement": "satisfied = min(satisfied, total_demand); "
                     "coverage_percent = satisfied / total_demand * 100",
        "evidence": [{"file": "src/agents/regional_agent.py", "line": 442,
                      "expect": "satisfied = min(satisfied, total_demand)"}],
        "note": "total_demand is captured PRE-optimization (regional_agent.py:183) "
                "while satisfied is summed over MILP hub clusters that double-count "
                "cross-cluster OD pairs. The clamp pins Asia and Americas to a "
                "hardcoded 100.0%. See D-F16.",
    },
    {
        "id": "F31",
        "name": "Global demand-weighted coverage",
        "layer": "reporting",
        "classification": "REPORTED METRIC",
        "statement": "global_demand_weighted_coverage = total_satisfied / "
                     "(total_satisfied + total_unserved) * 100",
        "evidence": [{"file": "src/agents/coordinator_agent.py", "line": 297,
                      "expect": "total_satisfied / true_global_demand * 100"}],
        "note": "Neither numerator nor denominator is a partition of true demand: "
                "sat+uns = 308,785.2 vs true total demand 276,446.8.",
    },
    {
        "id": "F32",
        "name": "Orchestrator aggregate coverage (computed then discarded)",
        "layer": "reporting",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "coverage = min(total_satisfied, true_global_demand) / true_global_demand * 100",
        "evidence": [{"file": "src/agents/orchestrator_agent.py", "line": 305,
                      "expect": "coverage"}],
        "note": "Computed at :304-308 against the TRUE global demand, then "
                "immediately overwritten at :992-1001 by F31. This is the only place "
                "in the codebase that uses the correct denominator.",
    },
    {
        "id": "F33",
        "name": "profit_margin_pct - orchestrator form",
        "layer": "reporting",
        "classification": "REPORTED METRIC",
        "statement": "profit_margin_pct = profit / (profit + total_cost) * 100   "
                     "where total_cost = all four components = 845,462,791.04",
        "evidence": [{"file": "src/agents/orchestrator_agent.py", "line": 1027,
                      "expect": "weekly_profit / (weekly_profit + total_cost) * 100"}],
        "note": "Yields 24.5486 -> 24.5. Matches docs/DATA_DICTIONARY.md:241.",
    },
    {
        "id": "F34",
        "name": "profit_margin_pct - coordinator form (DIVERGENT)",
        "layer": "reporting",
        "classification": "REPORTED METRIC",
        "statement": "profit_margin_pct = total_profit / (total_profit + total_cost) * 100 "
                     "where total_cost = sum(operating_cost) = 103,217,500.0",
        "evidence": [{"file": "src/agents/coordinator_agent.py", "line": 281,
                      "expect": "total_cost       = sum(s.get(\"operating_cost\", 0.0)"}],
        "note": "Yields 72.715 -> 72.7. The field named 'total_cost' holds operating "
                "cost alone. Same field name, different meaning, in the same "
                "artifact. See D-F15.",
    },
    {
        "id": "F35",
        "name": "Annualisation",
        "layer": "reporting",
        "classification": "ENGINEERING CONVENTION",
        "statement": "annual_profit = weekly_profit * 52",
        "evidence": [{"file": "src/agents/orchestrator_agent.py", "line": 1017,
                      "expect": "annual_profit  = metrics[\"annual_profit\"]"}],
        "note": "",
    },
    {
        "id": "F36",
        "name": "Transshipment flat default",
        "layer": "milp",
        "classification": "ENGINEERING CONVENTION",
        "statement": "DEFAULT_TRANSSHIP_COST = 80.0 USD/TEU",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 13,
                      "expect": "DEFAULT_TRANSSHIP_COST = 80.0"}],
        "note": "",
    },
    {
        "id": "F37",
        "name": "Uncovered-demand penalty (GA layers)",
        "layer": "ga",
        "classification": "IMPLEMENTED DEFINITION",
        "statement": "unserved_penalty = alpha_unserved * unserved_demand,  alpha_unserved = 50.0",
        "evidence": [
            {"file": "src/optimization/service_ga.py", "line": 63,
             "expect": "alpha_unserved"},
            {"file": "src/optimization/hierarchical_ga.py", "line": 22,
             "expect": "alpha_unserved"},
        ],
        "note": "Six times smaller than the MILP's 300.0 (F19).",
    },
    {
        "id": "F38",
        "name": "Service weekly cost",
        "layer": "service_generation",
        "classification": "ASSUMPTION",
        "statement": "weekly_cost = base * (closest_size / reference_size)",
        "evidence": [{"file": "src/agents/service_generator_agent.py", "line": 127,
                      "expect": "weekly_cost"}],
        "note": "A size-scaled heuristic (150k for direct, 150k/180k/280k hub loops, "
                "200k trunk, 70k feeders). NOT derived from the dataset tc_rate_daily, "
                "which is loaded and never read. See D-F04.",
    },
    {
        "id": "F39",
        "name": "Fleet cost vocabulary (loaded, never read)",
        "layer": "fleet",
        "classification": "NOT IMPLEMENTED",
        "statement": "tc_rate_daily, idle_consumption_tons_per_day, panama_fee, "
                     "suez_fee, bunker_consumption_tons_per_day, design_speed, "
                     "min_speed, max_speed, capacity_teu, draft",
        "evidence": [{"file": "src/data/network_loader.py", "line": 192,
                      "expect": "capacity_teu"}],
        "note": "Parsed from fleet_data.csv into FleetClass at network_loader.py:192-221 "
                "and then read by no generator, GA, MILP or validator. Idle and canal "
                "cost terms therefore do not exist anywhere in the cost model.",
    },
    {
        "id": "F40",
        "name": "Vessel fuel consumption (hardcoded, overrides dataset)",
        "layer": "fuel",
        "classification": "ASSUMPTION",
        "statement": "VESSEL_FUEL_CONSUMPTION: hardcoded Clarksons 2024 table",
        "evidence": [{"file": "src/utils/fuel_cost.py", "line": 20,
                      "expect": "VESSEL_FUEL_CONSUMPTION"}],
        "note": "Contradicts data/raw/WorldSmall/fleet_data.csv: Feeder_450 15 vs "
                "18.8 t/day; Super_panamax 100 vs 126.9 t/day. The dataset column "
                "Bunker_ton_per_day_at_designSpeed is ignored.",
    },
    {
        "id": "F41",
        "name": "utilization",
        "layer": "reporting",
        "classification": "NOT IMPLEMENTED",
        "statement": "No utilization metric is computed or reported anywhere in the pipeline",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 147,
                      "expect": "def _vessels_required"}],
        "note": "pipeline_output.json contains no 'utilization' field. Per-service "
                "'load' and 'capacity' exist, and unused capacity enters the GA "
                "objectives only as a penalty (F29), never as a reported metric.",
    },
    {
        "id": "F42",
        "name": "Minimum coverage constraint",
        "layer": "milp",
        "classification": "NOT IMPLEMENTED",
        "statement": "DEFAULT_MIN_COVERAGE = 0.0 - coverage is penalty-driven, not constraint-driven",
        "evidence": [{"file": "src/optimization/hub_milp.py", "line": 16,
                      "expect": "DEFAULT_MIN_COVERAGE"}],
        "note": "No hard coverage floor is ever enforced. shared_context "
                "coverage_target = 70.0 (orchestrator_agent.py:822) is never read.",
    },
]

# Findings carried forward from the two-stage audit, keyed for JSON output.
FINDINGS = [
    {"id": "F-01", "title": "Unit of account is TEU via a lane-specific multiplier; revenue scales by its square",
     "severity": "critical", "class": "F01,F02,F03", "layer": "data_loading"},
    {"id": "F-02", "title": "Second, incompatible demand path applies an unconditional DEMAND_SCALE = 6",
     "severity": "critical", "class": "F04", "layer": "data_loading"},
    {"id": "F-03", "title": "Four port cost columns converted inconsistently (three scaled, one not)",
     "severity": "major", "class": "F05,F06,F07,F08", "layer": "data_loading"},
    {"id": "F-04", "title": "Entire LINERLIB fleet cost vocabulary loaded and never read",
     "severity": "critical", "class": "F38,F39", "layer": "fleet"},
    {"id": "F-05", "title": "Fuel model is a hardcoded table that contradicts the dataset",
     "severity": "major", "class": "F40", "layer": "fuel"},
    {"id": "F-06", "title": "weekly_cost is a hardcoded heuristic with no daily->weekly bridge",
     "severity": "critical", "class": "F38", "layer": "service_generation"},
    {"id": "F-07", "title": "FrequencyGA computes fuel_cost then omits it from its fitness",
     "severity": "critical", "class": "F27", "layer": "ga"},
    {"id": "F-08", "title": "GA constrained to 263 vessels, MILP to 300 - not passed through",
     "severity": "major", "class": "F09,F10", "layer": "fleet"},
    {"id": "F-09", "title": "coverage_reward is a USD-scaled shaping term inside the MILP objective",
     "severity": "major", "class": "F21", "layer": "milp"},
    {"id": "F-10", "title": "Reported profit != revenue - total_cost; 'cost' and 'total_cost' are different sums",
     "severity": "critical", "class": "F20,F21,F23", "layer": "reporting"},
    {"id": "F-11", "title": "Two transshipment formulas: per-port tariff in objective, flat 80.0 when reported",
     "severity": "major", "class": "F22,F36", "layer": "milp"},
    {"id": "F-12", "title": "GA penalises uncovered demand at 50 USD/TEU, MILP at 300",
     "severity": "major", "class": "F19,F37", "layer": "ga"},
    {"id": "F-13", "title": "Port handling charged once per port touched, not per transshipment",
     "severity": "major", "class": "F18", "layer": "milp"},
    {"id": "F-14", "title": "Distance matrix has 17,169 duplicate OD pairs resolved by last-write-wins",
     "severity": "major", "class": "F11,F12", "layer": "data_loading"},
    {"id": "F-15", "title": "profit_margin_pct is two numbers in one artifact (24.5 and 72.7)",
     "severity": "critical", "class": "F33,F34", "layer": "reporting"},
    {"id": "F-16", "title": "Regional coverage is clamped to 100%; sat+uns exceeds true demand by 32,338 TEU",
     "severity": "critical", "class": "F30,F31,F32", "layer": "reporting"},
    {"id": "F-17", "title": "summary_metrics accounting identity holds exactly",
     "severity": "info", "class": "F23", "layer": "reporting"},
    {"id": "F-18", "title": "problem_analysis reports '0 services' during a 309-service run",
     "severity": "minor", "class": "-", "layer": "reporting"},
    {"id": "F-19", "title": "All LLM calls failed in the recorded run; result came entirely from fallbacks",
     "severity": "major", "class": "-", "layer": "llm"},
    {"id": "F-20", "title": "adaptive_budget IS wired; three of its five outputs are discarded",
     "severity": "info", "class": "-", "layer": "ga"},
    {"id": "F-21", "title": "No random seeding anywhere; runs are not reproducible",
     "severity": "critical", "class": "-", "layer": "reproducibility"},
    {"id": "F-22", "title": "Silent 500 nm fallback enters the fuel objective for missing OD pairs",
     "severity": "major", "class": "F12", "layer": "fuel"},
    {"id": "F-23", "title": "LLM weight chain terminates unused: profit_first branch ignores problem weights",
     "severity": "critical", "class": "F26", "layer": "ga"},
    {"id": "F-24", "title": "SharedContext has no read-side consumer; consensus archetype output is a dead end",
     "severity": "major", "class": "-", "layer": "agents"},
    {"id": "F-25", "title": "Per-service records do not reconcile with summary_metrics (305 vs 309 records)",
     "severity": "critical", "class": "-", "layer": "reporting"},
    {"id": "F-26", "title": "No test asserts any accounting identity; test_milp asserts only profit is not None",
     "severity": "critical", "class": "-", "layer": "tests"},
    {"id": "F-27", "title": "Iteration loop can never exit early: MIN_ITERATIONS == MAX_ITERATIONS == 3",
     "severity": "minor", "class": "-", "layer": "agents"},
    {"id": "F-28", "title": "Pipeline artifact carries no seed, timestamp, commit or input hash",
     "severity": "critical", "class": "F35", "layer": "reproducibility"},
]


def main():
    out = {
        "generated_by": "scripts/build_formula_index.py",
        "classification_vocabulary": [
            "IMPLEMENTED DEFINITION", "PAPER DEFINITION", "DATASET FIELD",
            "DERIVED METRIC", "ENGINEERING CONVENTION", "ASSUMPTION",
            "REPORTED METRIC", "NOT IMPLEMENTED",
        ],
        "formula_count": len(FORMULAS),
        "formulas": FORMULAS,
        "findings": FINDINGS,
    }
    dest = ROOT / "MULTI_AGENT_FORMULA_INDEX.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {dest.name}: {len(FORMULAS)} formulas, {len(FINDINGS)} findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())