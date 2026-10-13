"""Deterministic, read-only contract audit. Prints measured facts only.

Run from the project root:  python contract_audit.py
Does not modify any project file and makes no LLM / network calls.
"""
import csv
import math
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("PROJECT_ROOT", os.getcwd())).resolve()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONHASHSEED", "0")

from src.data.network_loader import NetworkLoader, WORLDSMALL_FILES   # noqa: E402
from src.optimization.data import Problem, Port, Service, Demand, Fleet, FleetClass   # noqa: E402
from src.utils import fuel_cost as fc   # noqa: E402


def hdr(t):
    print(f"\n=== {t} " + "=" * max(0, 70 - len(t)))


def raw(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


# ---------------------------------------------------------------- M1 loader
hdr("M1  loader facts (canonical WorldSmall)")
ld = NetworkLoader()
net = ld.load_network()
fleet = ld.load_fleet()
rep = ld.validation_report
d = rep["demands"]
print("ports                :", len(net["ports"]))
print("demand rows          :", len(net["demands"]))
print("directed dist pairs  :", rep["distances"]["directed_pairs"])
print("raw FFE/week         :", d["raw_weekly_ffe"])
print("converted TEU/week   :", round(d["converted_weekly_teu"], 1))
print("raw gross USD/week   :", d["raw_gross_revenue_usd_per_week"])
print("conv gross USD/week  :", round(d["converted_gross_revenue_usd_per_week"], 2))
print("demand_scale         :", d["demand_scale"])
print("fleet classes/total  :", len(fleet.classes), fleet.total_vessels)
k_nonDefault = sum(1 for x in raw(WORLDSMALL_FILES["demand"])
                   if abs(net_k := (0)) is None)  # placeholder to keep flake quiet
from src.data.network_loader import ffe_to_teu_factor   # noqa: E402
lanes = [(r["Origin"].strip(), r["Destination"].strip()) for r in raw(WORLDSMALL_FILES["demand"])]
non_default = [(o, dd, ffe_to_teu_factor(o, dd)) for o, dd in lanes if ffe_to_teu_factor(o, dd) != 2.0]
print("lanes with non-2.0 factor:", len(non_default), non_default)
print("fleet fees  (panama,suez):",
      {c.vessel_class: (c.panama_fee, c.suez_fee) for c in fleet.classes})
dist_rows = raw(WORLDSMALL_FILES["distance"])
print("IsPanama=1 pairs:", sum(1 for r in dist_rows if r["IsPanama"].strip() == "1"),
      " IsSuez=1 pairs:", sum(1 for r in dist_rows if r["IsSuez"].strip() == "1"),
      " non-blank Draft:", sum(1 for r in dist_rows if r["Draft"].strip() != ""))

# ---------------------------------------------------------------- M2 fuel table vs fleet
hdr("M2  hard-coded fuel table vs fleet_data.csv")
print(f"{'class':14s} {'cap(fleet)':>10s} {'cap(table)':>10s} {'t/day(fleet@design)':>20s} {'t/day(table)':>12s} {'design kn':>9s} {'table kn':>9s}")
for c in fleet.classes:
    t = fc.VESSEL_FUEL_CONSUMPTION[c.vessel_class]
    print(f"{c.vessel_class:14s} {c.capacity_teu:10.0f} {t['capacity']:10.0f} "
          f"{c.bunker_consumption_tons_per_day:20.1f} {t['consumption_tons_per_day']:12.1f} "
          f"{c.design_speed:9.1f} {t['speed_knots']:9.1f}")
print("fuel table speeds exceed fleet maxSpeed for:",
      [c.vessel_class for c in fleet.classes
       if fc.VESSEL_FUEL_CONSUMPTION[c.vessel_class]["speed_knots"] > c.max_speed])

# ---------------------------------------------------------------- M3 candidate services
hdr("M3  candidate service contract vs fleet (deterministic seed)")
random.seed(12345)
import numpy as np   # noqa: E402
np.random.seed(12345)
problem = Problem(ports=net["ports"], services=[], demands=net["demands"],
                  distance_matrix=net["distance_matrix"], fleet=fleet)
from src.agents.service_generator_agent import ServiceGeneratorAgent   # noqa: E402
agent = ServiceGeneratorAgent(name="audit_svc_gen", model="none")
svcs_raw = agent.generate_services(problem)
n_dict = sum(1 for s in svcs_raw if isinstance(s, dict))
print("candidates generated:", len(svcs_raw), " of which plain dict (un-normalised):", n_dict)
# normalise like RegionalAgent does
from src.utils.fuel_cost import map_capacity_to_vessel_class   # noqa: E402
norm = []
for i, s in enumerate(svcs_raw):
    if isinstance(s, Service):
        norm.append(s)
    else:
        cap = s.get("capacity", 5000)
        norm.append(Service(id=i, ports=s["ports"], capacity=cap,
                            weekly_cost=s.get("weekly_cost", 150_000),
                            cycle_time=s.get("cycle_time", 14),
                            vessel_class=s.get("vessel_class", map_capacity_to_vessel_class(cap))))
cap_by_class = {c.vessel_class: c for c in fleet.classes}
max_cap = max(c.capacity_teu for c in fleet.classes)
print("fleet max single-vessel capacity (TEU):", max_cap)
over = [s for s in norm if s.capacity > max_cap]
print("services whose capacity exceeds every fleet vessel:", len(over), "of", len(norm))
print("capacity distribution:", dict(sorted(Counter(s.capacity for s in norm).items())))
mism = [s for s in norm if s.vessel_class in cap_by_class and s.capacity != cap_by_class[s.vessel_class].capacity_teu]
print("services whose capacity != fleet capacity of their vessel_class:", len(mism), "of", len(norm))
print("cycle_time distribution (days):", dict(sorted(Counter(s.cycle_time for s in norm).items())))

dm = net["distance_matrix"]


def route_nm(ports, closed):
    legs = list(zip(ports, ports[1:]))
    if closed and ports[0] != ports[-1]:
        legs.append((ports[-1], ports[0]))
    tot, missing = 0.0, 0
    for a, b in legs:
        if a == b:
            continue
        if b in dm.get(a, {}):
            tot += dm[a][b]
        else:
            missing += 1
    return tot, missing


infeasible = 0
ratio = []
same_port_legs = 0
for s in norm:
    spec = cap_by_class.get(s.vessel_class)
    speed = spec.max_speed if spec else 20.0
    nm, _ = route_nm(s.ports, closed=True)
    sail_days = nm / (speed * 24.0)
    ratio.append(s.cycle_time / sail_days if sail_days > 0 else float("inf"))
    if sail_days > s.cycle_time:
        infeasible += 1
    same_port_legs += sum(1 for a, b in zip(s.ports, s.ports[1:]) if a == b)
print(f"services whose closed-route sailing time at the class MAX speed exceeds cycle_time: {infeasible} of {len(norm)}")
ratio_sorted = sorted(r for r in ratio if math.isfinite(r))
print("cycle_time / min sailing days  (min, median, max):",
      round(ratio_sorted[0], 3), round(ratio_sorted[len(ratio_sorted) // 2], 3), round(ratio_sorted[-1], 3))
print("consecutive identical-port legs (distance 0 / missing from matrix):", same_port_legs)

# vessels needed to sustain weekly service vs fleet
need = sum(math.ceil(max(s.cycle_time, 7) / 7) for s in norm)
print("sum of ceil(cycle_time/7) over ALL candidates (1 weekly sailing each):", need, " fleet:", fleet.total_vessels)

# ---------------------------------------------------------------- M7 fuel known values + fallbacks
hdr("M7  fuel_cost known values and fallbacks")
v = fc.calculate_voyage_fuel_cost(1000.0, "Feeder_450")
print("1000 nm, Feeder_450 (16 kn, 15 t/d, $600/t):", round(v, 2),
      " hand:", round(1000 / (16 * 24 * 0.9) * 15 * 600, 2))
mini = {"A": {"B": 1000.0}, "B": {"A": 1000.0}}
print("weekly, route A-B, cycle 7:", round(fc.calculate_weekly_fuel_cost(["A", "B"], mini, "Feeder_450", 7), 2))
print("weekly, route A-B-A, cycle 14:", round(fc.calculate_weekly_fuel_cost(["A", "B", "A"], mini, "Feeder_450", 14), 2))
def _try(label, fn):
    try:
        print(label, "->", round(fn(), 2))
    except Exception as exc:                      # noqa: BLE001 - audit output only
        print(label, "-> RAISES", type(exc).__name__ + ":", str(exc)[:90])


_try("weekly, route A-A-B (same-port leg), cycle 7 ", lambda: fc.calculate_weekly_fuel_cost(["A", "A", "B"], mini, "Feeder_450", 7))
_try("weekly, route A-Z (Z unknown), cycle 7       ", lambda: fc.calculate_weekly_fuel_cost(["A", "Z"], mini, "Feeder_450", 7))
_try("voyage, unknown class 'Nope'                 ", lambda: fc.calculate_voyage_fuel_cost(1000.0, "Nope"))
_try("weekly, cycle_time 0                         ", lambda: fc.calculate_weekly_fuel_cost(["A", "B"], mini, "Feeder_450", 0))

# ---------------------------------------------------------------- M9 port-cost sensitivity
hdr("M9  port-cost unit basis sensitivity (raw per-FFE-named columns)")
rawp = raw(WORLDSMALL_FILES["ports"])
s_full = sum(float(r["CostPerFULL"]) for r in rawp) / len(rawp)
s_var = sum(float(r["PortCallCostPerFFE"]) for r in rawp) / len(rawp)
print(f"mean raw CostPerFULL = {s_full:.2f}  PortCallCostPerFFE = {s_var:.2f}")
print(f"loader x2.0  -> handling per TEU mean = {2*s_full:.2f}")
print(f"dimensional  /2 -> handling per TEU mean = {s_full/2:.2f}   (ratio loader/dimensional = 4.0)")
mean_rev_teu = sum(dd.revenue_per_teu * dd.weekly_teu for dd in net["demands"]) / sum(dd.weekly_teu for dd in net["demands"])
print(f"weighted mean revenue per TEU = {mean_rev_teu:.2f}")
