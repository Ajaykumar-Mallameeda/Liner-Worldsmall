"""Register of the assumptions that materially affect a reported result.

Every plan carries this list in ``assumptions.assumption_register`` so that a consumer never has to
infer which inputs are sourced and which are provisional.  Values are read from the objects in force
(economics assumptions, fleet, fuel pricing); statuses and sources are fixed statements about the
evidence, reviewed in ``reports/audit_20261013_phaseADB`` and ``reports/issue6_assumptions``.

status vocabulary
    SOURCED_PRIMARY_CODE defined by the benchmark authors' reference code / solution logs (technical report text not read)
    SOURCED_SECONDARY   defined by a secondary source (benchmark page / paper); primary report unavailable
    PROVISIONAL         a modelling convention without a source; the result is conditional on it
    UNVERIFIED          interpretation not confirmed by any available source
    NOT_MODELLED        a real cost / constraint that the model does not include (exposure reported separately)
"""
from __future__ import annotations

from typing import Dict, List


def build(assumptions, fleet=None) -> List[Dict]:
    a = assumptions
    pricing = a.effective_fuel_pricing
    price = (pricing.reference_price_usd_per_t if getattr(pricing, "reference_price_usd_per_t", None) is not None
             else a.bunker_price_usd_per_t)
    cap_status = getattr(fleet, "capacity_unit_status", "provisional") if fleet is not None else "unknown"
    rows = [
        ("capacity_unit", "Vessel capacity unit", "Capacity FFE x 2 -> TEU (converted once at the loader)",
         "SOURCED_PRIMARY_CODE" if cap_status == "reference_code"
         else ("SOURCED_SECONDARY" if cap_status == "secondary_source" else "PROVISIONAL"),
         "LINERLIB reference code types the capacity as FFE (BM_Graph.hpp, bm_data.hpp); RL paper arXiv:2411.09068 "
         "App. A.1 agrees; the technical report text was not available",
         "capacity, coverage, profit levels (x1.6-2.5 against the TEU reading)"),
        ("ffe_to_teu", "FFE -> TEU conversion", "1 FFE = 2 TEU exactly, no lane factors", "SOURCED_SECONDARY",
         "definition of the units; lane factors removed (unsourced)", "demand, revenue rates, per-FFE costs"),
        ("transit_file", "Transit-time limits", "Demand_WorldSmall_Fixed_Sep.csv (original TransitTime, unit days)", "PROVISIONAL",
         "LINERLIB authors recommend the revised file; 13.0 % of demand differs; no decision recorded",
         "coverage of ODs whose limit differs (105 ODs)"),
        ("transit_scope", "TransitTime scope", "end-to-end days including port stays and transfer dwell", "UNVERIFIED",
         "unit reproduced from the upstream revision rule; inclusion of port time not stated by any source", "coverage"),
        ("port_stay", "Port stay per call", f"{a.port_stay_hours:g} h", "SOURCED_SECONDARY",
         "OR-tools LINERLIB benchmark page (minimum port stay 24 h); paper: 1 day", "cycle time, vessels, transit"),
        ("transfer_dwell", "Transfer dwell", f"{a.transshipment_min_hours:g} h minimum + {a.transfer_wait_days:g} d expected wait", "PROVISIONAL",
         "48 h from the benchmark page; the 3.5 d wait is a model convention", "multi-service paths, coverage"),
        ("bunker_price", "Bunker price", f"{price:g} USD/t uniform ({pricing.describe().get('mode', 'legacy_uniform') if hasattr(pricing, 'describe') else 'uniform'})",
         "SOURCED_SECONDARY", "benchmark page (600 USD/t); not a market price; fuel grade / fuel systems unverified", "fuel cost (largest cost item)"),
        ("fuel_grade", "Fuel grade and vessel fuel systems", "VLSFO-equivalent for every vessel", "UNVERIFIED",
         "fleet file carries no fuel-system data", "fuel cost"),
        ("weekly_frequency", "Service frequency granularity", "integer departures per week, vessels = ceil(T f / 7)", "UNVERIFIED",
         "no source defines the allowed frequencies; paper uses fractional vessels", "thin long routes, coverage"),
        ("cost_units", "Port cost units", "CostPerFULL, CostPerFULLTrnsf are USD per FFE (divided by 2 -> per TEU); port call = fixed + PortCallCostPerFFE x vessel capacity per call", "PROVISIONAL",
         "loader contract; no upstream sentence confirms the per-FFE reading", "handling, transshipment, port variable cost"),
        ("canal_fees", "Canal fees (Suez, Panama)",
         "charged: traversals of the closed rotation x class fee, once per weekly departure; blank fee = class cannot pass (never zero)",
         "SOURCED_PRIMARY_CODE",
         "LINERLIB reference code calculate_canal_cost and the authors' WorldSmall solution log (34/34 traversal counts, cost within the log's "
         "rounding); fees are benchmark data, not a verified real tariff; owner countersign (D-08) outstanding", "cost of canal routes, class eligibility"),
        ("rejection_penalty", "Rejected-demand penalty", "none in the operating profit", "PROVISIONAL",
         "paper / benchmark use 1000 USD per rejected unit; operating profit excludes it by definition", "comparability with the paper"),
        ("unused_vessels", "Unused vessels", "no credit and no cost", "PROVISIONAL",
         "paper credits unused vessels at the time-charter rate", "comparability with the paper"),
    ]
    return [{"id": i, "name": n, "value": v, "status": s, "source": src, "affects": aff} for i, n, v, s, src, aff in rows]
