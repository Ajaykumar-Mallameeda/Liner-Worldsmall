"""Build the paper-parity matrix (JSON + Markdown) for the six cost-parity targets.

Observed values are read from the stored reconciliation of the authors' solution log
(``ws3_paper_parity/linerlib_log_reconcile.json``) or computed here with the evaluator / ledger; expected values are the
source's own numbers or hand arithmetic.  usage: python -I build_parity_matrix.py <out_dir>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

from src.benchmark.paper_evaluator import evaluate, load_worldsmall_ffe, net_profit
from src.benchmark.paper_ledger import fleet_accounting, objective_ledger, rotation_costs, to_teu_native, hops_from_edges

rec = json.loads((OUT / "linerlib_log_reconcile.json").read_text(encoding="utf-8"))
cap = json.loads((OUT / "capacity_unit_check.json").read_text(encoding="utf-8"))
dsg = json.loads((OUT / "linerlib_design_in_paper_mode.json").read_text(encoding="utf-8"))
dprofits = [r["profit_M"] for r in dsg["rows"] if "profit_M" in r]
closest = min((r for r in dsg["rows"] if "profit_M" in r), key=lambda r: abs(r["ratio_to_paper"] - 1.0))
chk, tv = rec["service_level_checks"], rec["term_vs_log"]
data = load_worldsmall_ffe(ROOT / "data" / "raw" / "WorldSmall")

# --- live observations
rc = rotation_costs(data, ["CNSHA", "JPYOK"], "Post_panamax", fuel_price_usd_per_t=600.0)
design = [{"ports": ["CNSHA", "KRPUS", "USLAX"], "class": "Post_panamax"}, {"ports": ["USLAX", "USCHS", "NLRTM"], "class": "Panamax_2400"},
          {"ports": ["NLRTM", "DEHAM", "GBFXT"], "class": "Feeder_800"}, {"ports": ["CNSHA", "HKHKG", "SGSIN"], "class": "Panamax_1200"}]
ra = evaluate(data, design, canal_basis="per_rotation", return_flows=True)
rb = evaluate(to_teu_native(data), design, canal_basis="per_rotation", return_flows=True)
inv = max(abs(rb[k] - ra[k]) / max(1.0, abs(ra[k])) for k in ("revenue", "rejected_penalty", "handling_and_transshipment",
                                                              "vessel_service_cost", "voyage_cost_without_fuel", "fuel_tonnes_per_week"))
fa = fleet_accounting(data, {"Feeder_450": 10.0})["by_class"]["Feeder_450"]
fb = fleet_accounting(data, {"Feeder_450": 24.0})["by_class"]["Feeder_450"]
fc = fleet_accounting(data, {"Feeder_450": 30.0})["by_class"]["Feeder_450"]


def rel(x):
    return f"{x:.1e}"


rows = [
    # ------------------------------------------------------------------------------------------ 3.1
    ("3.1", "capacity and demand in FFE; conversion once", "paper A.1 (vcap 'maximum number of FFEs', dq 'FFE per week'); loader x2 once",
     "raw files (FFE); operational loader boundary", "FFE (paper) / TEU (operational)", "src/benchmark/paper_evaluator.py (FFE-native); src/data/network_loader.py (x2 once)",
     "tests/test_paper_cost_parity.py::TestUnitContract, tests/test_unit_contract.py", "TEU-native copy == loader values",
     "equal to 1e-12 (all demands, classes, ports)", "VERIFIED (paper-mode); operational capacity x2 stays 'reference_code'"),
    ("3.1", "capacity unit: Capacity FFE is an FFE count per weekly departure", "paper A.1 (v_cap 'maximum number of FFEs'); authors' log utilisation",
     "authors' log: 34 printed utilisations and 1,708 flows (FFE)", "FFE per departure", "reports/continuation_20261015/tools/capacity_unit_check.py",
     "ws3_paper_parity/capacity_unit_check.json", "printed utilisation = mean leg load factor with capacity = Capacity FFE",
     f"{cap['printed_reproduced_within_2e-6']}/{cap['services']} within 2e-6, max diff {cap['max_abs_diff']:.1e} (print rounding of fractional flows); max leg load factor {cap['max_leg_load_factor_over_all_services_with_capacity_in_FFE']:.7f} (a TEU reading would reach 2.0)",
     "VERIFIED against the reference solution (the operational x2 conversion is consistent with it; the operational register keeps its own status until the owner updates it)"),
    ("3.1", "no revenue inflation", "Eq. 29 revenue = rate x FFE delivered", "Demand_WorldSmall_Fixed_Sep.csv; authors' log revenue",
     "USD/week", "paper_ledger.objective_ledger", "TestUnitContract::test_gross_revenue..., log reconciliation", "revenue = sum q x Revenue_1",
     f"authors' log: recomputed {tv['revenue']['recomputed']:,.0f} vs {tv['revenue']['log']:,.0f} (rel {rel(tv['revenue']['rel'])})", "VERIFIED"),
    ("3.1", "representation invariance (FFE-native vs TEU-native)", "1 FFE = 2 TEU; rates per FFE / 2 per TEU; penalty 1000/FFE = 500/TEU",
     "to_teu_native()", "USD, FFE/TEU", "paper_ledger.to_teu_native", "TestUnitContract::test_equivalent_representations...",
     "revenue, costs, coverage, load factor equal; cargo TEU = 2 x FFE", f"max relative difference {inv:.1e}",
     "VERIFIED (the test found and fixed a fixed 1000/unit penalty that was not rescaled)"),
    # ------------------------------------------------------------------------------------------ 3.2
    ("3.2", "sailing time at design speed", "App. A.3: vessels = (distance / design speed + 1 day per port) / 7; Table 6",
     "paper Table 6 (19 schedules); authors' log", "nm / (knots x 24) = days", "paper_ledger.rotation_costs",
     "tests/test_paper_evaluator.py::test_paper_table6_vessel_counts_are_reproduced; TestSailingAndIdleFuel",
     "Table 6 vessel counts 19/19; log sailing fuel at the logged speeds",
     f"19/19 equal to 3 digits; log sailing fuel max rel diff {rel(chk['sailing_fuel_t']['max_rel_diff'])}; distance diff {chk['distance_nm']['max_abs_diff']}",
     "VERIFIED"),
    ("3.2", "sailing fuel = sea days x t/day at design speed", "Eq. 35 term 2 (consumption at design speed 'converted to $')",
     "fleet_data.csv 'Bunker ton per day at designSpeed'", "t/day x days = t", "rotation_costs (design point); cubic law only to reconcile the LINERLIB log",
     "TestSailingAndIdleFuel (six classes, hand arithmetic)", f"CNSHA<->JPYOK Post_panamax: {2080/(16.5*24):.4f} d x 82.2 t/d = 431.758 t",
     f"{rc['sailing_fuel_t']:.3f} t", "VERIFIED (time and tonnes); price: see next row"),
    ("3.2", "idle fuel: one day per port call", "Eq. 35 term 2 (1 x v_fi per port p in s); App. A.3 '1 day at each port'",
     "fleet_data.csv 'Idle Consumption ton/day'; authors' log", "t/day x calls", "rotation_costs",
     "TestSailingAndIdleFuel; log reconciliation", "2 calls x 7.4 t/d = 14.8 t", f"{rc['idle_fuel_t']:.1f} t; log idle burn max rel diff {rel(chk['idle_fuel_t']['max_rel_diff'])}",
     "VERIFIED"),
    ("3.2", "fuel price", "NOT in the paper ('converted to $'); the authors' log prints 'at 600 USD'", "log header text; assumption register",
     "USD/t", "explicit argument; None = unavailable", "TestSailingAndIdleFuel::test_fuel_price_is_never_invented", "no invented price",
     "None leaves fuel_usd and net profit unavailable", "PROVISIONAL (600 USD/t = benchmark input, not a paper value; fuel grade unverified)"),
    ("3.2", "Eq. 35 sailing term as printed: edist / v_s x v_fs x n_{v,s}", "no 24 h/day factor; per-rotation cost multiplied by the fractional vessel count",
     "paper (arXiv HTML and PDF)", "dimensionally ambiguous", "voyage_basis switch (per_rotation | per_vessel)", "ledger/evaluator keep both bases",
     "authors' log: all voyage terms once per weekly rotation, not x n", "PROVISIONAL: per_rotation is supported by the reference output; the paper's own code is not available"),
    # ------------------------------------------------------------------------------------------ 3.3
    ("3.3", "vessel-service cost", "Eq. 33: sum n_{v,s} x TC", "fleet_data.csv TC rate daily; authors' log; paper Table 1",
     "USD/week = n x TC x 7", "paper_ledger.fleet_accounting", "TestFleetAccounting; log reconciliation",
     "log: 34/34 services, 0 USD", f"log: max diff {chk['time_charter_usd_week']['max_abs_diff']} USD; Table 1 LINERLIB column 245,176 vs 245,140 (n x TC x 7 from the stated vessel counts)",
     "VERIFIED (weekly horizon); RL column of Table 1 is 1.3 % above n x TC x 7 - UNRESOLVED residual"),
    ("3.3", "fewer vessels than owned: credit at the TC rate", "Eq. 34", "paper Table 1 (sign and size)", "USD/week", "fleet_accounting",
     "TestFleetAccounting::test_fewer...", f"(24-10) x 5,000 x 7 = 490,000", f"{fa['unused_credit_usd']:,.0f}", "VERIFIED"),
    ("3.3", "exactly the owned fleet", "Eq. 34", "-", "USD/week", "fleet_accounting", "TestFleetAccounting::test_exactly...", "0", f"{fb['unused_credit_usd']:,.0f}", "VERIFIED"),
    ("3.3", "more vessels than owned: charge at the TC rate", "Eq. 34 / paper Table 1 text", "paper Table 1 (-12,596 for 6.34 vessels used)",
     "USD/week", "fleet_accounting", "TestFleetAccounting::test_more..., test_paper_table1_unused_term...", "(24-30) x 35,000 = -210,000",
     f"{fc['unused_credit_usd']:,.0f}; Table 1: -12,596 expected, -12,530 from the rounded vessel counts", "VERIFIED (sign, unit, size within rounding); owned Baltic fleet 4+2 is inferred from the table - PROVISIONAL"),
    ("3.3", "operational C3 keeps hard fleet feasibility", "operational ledger violation 'fleet_exceeded'", "src/network/ledger.py", "vessels",
     "unchanged", "TestFleetAccounting::test_operational_c3_still_rejects_an_over_fleet_plan; tests/test_network_economics.py", "violation raised", "raised", "VERIFIED"),
    # ------------------------------------------------------------------------------------------ 3.4
    ("3.4", "port-call cost: fixed + per-FFE x capacity, every call", "Eq. 35 term 1: (p_f + p_v x v_cap)", "ports.csv; authors' log 'Port call cost'",
     "USD per call", "rotation_costs", "TestPortHandling...::test_one_port_call; log reconciliation", "34/34 services, 0 USD",
     f"max diff {chk['port_call_usd']['max_abs_diff']} USD; total {tv['port_call']['recomputed']:,.0f} vs {tv['port_call']['log']:,.0f}", "VERIFIED"),
    ("3.4", "loading + unloading: p_l per FFE at origin and destination", "Eq. 31 first part", "ports.csv CostPerFULL; authors' flows",
     "USD per FFE", "objective_ledger", "log reconciliation (1,708 flows); test_one_loading_and_unloading...", "sum over logged flows",
     f"handling+transshipment {tv['handling']['recomputed']:,.0f} vs log {tv['handling']['log']:,.0f} (rel {rel(tv['handling']['rel'])}; the log prints 6 digits)",
     "VERIFIED against the reference solution (the technical report's column dictionary was not consulted)"),
    ("3.4", "transshipment: p_t per FFE per change of service, at the port where the earlier service is left", "Eq. 31 second part",
     "ports.csv CostPerFULLTrnsf; authors' flows", "USD per FFE", "objective_ledger; paper_evaluator.transfer_ports (bug fixed)",
     "test_transfer_port_is_where_the_earlier_service_is_left", f"{rec['recomputed_totals']['transfers_counted']} transfers, {rec['recomputed_totals']['transshipment_part']:,.0f} USD inside the total above",
     "included in the total above", "VERIFIED (the evaluator used the wrong port for multi-leg services; fixed, regression test)"),
    ("3.4", "per-FFE vs per-TEU reading of the handling columns", "unit of quantity in the flows is FFE", "authors' log flows are the FFE demand quantities",
     "USD per FFE", "operational loader divides by 2 once", "log reconciliation", "per-TEU reading would double the total",
     "per-FFE reading reproduces the total to 2e-6", "VERIFIED against the reference solution; operational register unchanged"),
    ("3.4", "one-day port stay (paper evaluator)", "App. A.3", "paper Table 6; log idle burn", "days", "PORT_DAYS = 1", "Table 6 test; idle fuel test", "19/19", "19/19", "VERIFIED (paper mode only; operational stay stays 24 h by its own register)"),
    ("3.4", "small end-to-end accounting example", "Eq. 28-35", "hand arithmetic", "USD/week", "evaluate vs objective_ledger",
     "test_small_end_to_end_example_by_hand", "net profit 4,000", "4,000 (both)", "VERIFIED"),
    # ------------------------------------------------------------------------------------------ 3.5
    ("3.5", "canal fee x traversals, once per weekly rotation", "Eq. 35 term 3 (no n_{v,s})", "dist_dense.csv flags; fleet_data.csv fees; authors' log",
     "USD per traversal", "rotation_costs", "TestCanal; log reconciliation", "34/34 counts, within log rounding",
     f"counts equal {chk['traversal_counts_equal']}/34, max diff {chk['canal_usd']['max_abs_diff']} USD; total {tv['canal']['recomputed']:,.0f} vs {tv['canal']['log']:,.0f}", "VERIFIED"),
    ("3.5", "Suez benchmark fees", "benchmark input (six classes)", "fleet_data.csv", "USD per traversal", "unchanged", "TestCanal::test_suez_fee_table...",
     "175,769 / 218,445 / 267,217 / 413,533 / 633,007 / 1,035,376", "equal", "PROVISIONAL: benchmark inputs, not independently verified real tariffs; real applicability unapproved"),
    ("3.5", "blank Panama fee = class cannot pass", "reference rule; no Panama fee for Post/Super-panamax", "fleet_data.csv; authors' solution has no such service",
     "-", "rotation_costs (canal_unpassable)", "TestCanal::test_blank_panama...", "reported, never charged or invented", "reported", "VERIFIED (consistent with the reference solution; no counter-example)"),
    # ------------------------------------------------------------------------------------------ 3.6
    ("3.6", "rejected-demand penalty 1000 USD per FFE, once", "Eq. 30; A.1 'Y_d set to $1000'", "paper; authors' log 'Penalty'", "USD per FFE rejected",
     "objective_ledger", "log reconciliation; test_accepted_demand_earns_once...", "1000 x rejected FFE",
     f"log: {tv['penalty']['recomputed']:,.0f} vs {tv['penalty']['log']:,.0f}", "VERIFIED"),
    ("3.6", "complete objective recomputed independently", "Eq. 28 + 32", "authors' log (speed-optimised LINERLIB solution, no unused credit)",
     "USD/week", "linerlib_log_reconcile.py (raw files + logged flows)", "log reconciliation",
     f"log objective {rec['objective']['log_objective_line']:,.0f}", f"recomputed {rec['objective']['recomputed_from_raw_files_and_logged_flows']:,.0f} (rel {abs(rec['objective']['recomputed_from_raw_files_and_logged_flows']/rec['objective']['log_objective_line']-1):.1e})",
     "VERIFIED for the LINERLIB reference solution; this is not the paper's design-speed model"),
    ("3.6", "paper objective identity on the paper's Table 1", "Eq. 28 / 32", "paper Table 1 (both columns)", "USD", "-", "test_paper_table1_objective_identity",
     "276,428 / 260,948", "276,428 / 260,948 (exact)", "VERIFIED (arithmetic identity; Table 1 is not used as a profit target)"),
    ("3.6", "paper-reported profits for WorldSmall (Table 2)", "-", "paper Table 2", "USD", "-", "reports/issue7_paper_mode", "-",
     f"Issue 7: Table 6 design, 48 variants span -1,406..+95 M vs 32-43 M. This campaign: the LINERLIB solution (butterflies split into simple loops, {dsg['simple_services']} services) in {len(dprofits)} variants (2 demand files x voyage x canal x capacity basis) spans {min(dprofits):,.0f}..{max(dprofits):,.0f} M vs the paper's 32.28 M; closest {closest['profit_M']:.1f} M (x{closest['ratio_to_paper']:.2f}); none within 40 %",
     "UNRESOLVED (horizon of the paper's profit tables, capacity basis of a fractional-vessel service, decomposition and MCF tie-breaking; not an acceptance target)"),
]
cols = ["target", "component", "source equation / definition", "source input and provenance", "units", "implementation", "test", "expected", "observed", "status"]
js = [dict(zip(cols, r)) for r in rows]
(OUT / "parity_matrix.json").write_text(json.dumps(js, indent=1), encoding="utf-8")
md = ["# Paper-cost parity matrix (six targets) - 2026-10-15", "",
      "Scope: the paper's cost equations (Eq. 28-35) and unit conventions only. Cost parity does not prove objective parity, algorithm parity or the paper's profits.",
      "Statuses: VERIFIED = reproduced against a primary source (paper table, authors' reference output) or exact hand arithmetic; PROVISIONAL = used but the source does not settle it; UNRESOLVED = open.", "",
      "| target | component | source equation / definition | provenance | units | implementation | test | expected | observed | status |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    md.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
from collections import Counter
cnt = Counter(r[-1].split(" ")[0].split(":")[0] for r in rows)
md += ["", f"Counts: {dict(cnt)}"]
(OUT / "PARITY_MATRIX.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(dict(cnt), len(rows))
