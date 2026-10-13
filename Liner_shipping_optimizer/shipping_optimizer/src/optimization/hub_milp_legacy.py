"""LEGACY COPY (verbatim) of the pre-network-model implementation, kept for reference.
Not imported by the pipeline. Superseded by src/network/* (see reports/overnight_tasks_2_to_4).
"""
import logging
import pulp
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from src.utils.fuel_cost import (
    calculate_weekly_fuel_cost,
    _normalize_weather_speed_factor,
)
from src.config.optimizer_config import CONFIG

logger = logging.getLogger(__name__)

DEFAULT_TRANSSHIP_COST = 80.0
DEFAULT_PORT_COST      = 15.0
DEFAULT_PORT_CAPACITY  = 1e9
DEFAULT_MIN_COVERAGE   = 0.0    # penalty-driven, not constraint-driven


# --------------------------------------------------------------------
# IP-2 (Phase 7) — local-only fuel-cost kwarg builder
# --------------------------------------------------------------------
# This helper is structurally identical to
# ``maritime.optimizer_bridge.fuel_cost_kwargs`` but is duplicated
# here (rather than imported) so the optimizer package has no
# compile-time dependency on the maritime package. The
# network-isolation boundary tests in
# ``tests/architecture/test_network_isolation.py`` enforce that no
# ``src/`` module may import ``maritime.*``. The two helpers are
# covered by the IP-2 test suite in
# ``tests/maritime/test_phase7_integration.py``.
def _maritime_fuel_cost_kwargs(problem) -> Dict:
    if problem is None:
        return {}
    mf = getattr(problem, "maritime_features", None)
    if mf is None:
        return {}
    wsf = getattr(mf, "weather_speed_factor", None)
    if wsf is None:
        return {}
    safe = _normalize_weather_speed_factor(wsf)
    if safe is None:
        return {}
    return {"weather_speed_factor": safe}


class HubMILP:
    def __init__(
        self,
        problem,
        chromosome,
        max_services_per_demand: int  = 10,
        max_transfer_pairs: int       = 2000,
        transship_cost_per_teu: float = DEFAULT_TRANSSHIP_COST,
        port_cost_per_teu: float      = DEFAULT_PORT_COST,
        port_capacity: float          = DEFAULT_PORT_CAPACITY,
        min_coverage: float           = DEFAULT_MIN_COVERAGE,
        w_profit: float               = 0.5,
        w_coverage: float             = 0.4,
        alpha_unserved: float         = 300.0,
        time_limit: int               = 120,
        fleet_size: int = 300,
        *,
        # IP-3 (Phase 7): optional congestion-derived port-capacity
        # override map. ``None`` or an empty dict preserves the
        # existing pre-maritime synthetic capacity map unchanged.
        # Keys are port ids (int) as used in ``problem.ports``;
        # values are unitless multiplicative factors in
        # ``[0.0, 1.0]`` (1.0 = no change, 0.0 = full blockage,
        # 0.7 = 30% reduction for moderate congestion, etc.).
        # The map is applied exactly once during construction;
        # the solver itself does not see the override (it just
        # sees the resulting ``port_capacity_map``).
        port_capacity_override: Optional[Dict] = None,
    ):
        self.problem    = problem
        self.chromosome = chromosome

        self.max_svc_per_demand = max_services_per_demand
        self.max_xfer_pairs     = max_transfer_pairs
        self.tc_per_teu         = transship_cost_per_teu
        self.pc_per_teu         = port_cost_per_teu
        self.port_capacity      = port_capacity
        self.min_coverage       = min_coverage
        self.w_profit           = w_profit
        self.w_coverage         = w_coverage
        self.alpha              = alpha_unserved
        self.time_limit         = time_limit
        self.fleet_size         = fleet_size
        # Defensive copy — we never mutate the caller's dict.
        self.port_capacity_override: Dict = (
            dict(port_capacity_override) if isinstance(port_capacity_override, dict)
            else {}
        )

        self.port_lookup: Dict = {p.id: p for p in problem.ports}

        # Index active services by port
        self.port_services: Dict[int, List[int]] = defaultdict(list)
        services_mask = chromosome.get("services", [])
        for s_idx, svc in enumerate(problem.services):
            if s_idx >= len(services_mask) or services_mask[s_idx] == 0:
                continue
            for p in svc.ports:
                self.port_services[p].append(s_idx)

        # Pre-compute port demand for transfer pair prioritisation
        self._port_demand: Dict[int, float] = defaultdict(float)
        for d in problem.demands:
            self._port_demand[d.origin]      += d.weekly_teu
            self._port_demand[d.destination] += d.weekly_teu

        demand_score = defaultdict(float)
        for d in problem.demands:
            demand_score[d.origin] += d.weekly_teu
            demand_score[d.destination] += d.weekly_teu

        self.port_capacity_map = {
            p.id: 50000 + 0.1 * demand_score[p.id]
            for p in problem.ports
        }
        # IP-3: apply congestion-derived port-capacity override.
        # The override is a multiplicative factor in [0, 1] keyed by
        # port id (string). An empty/None override (the default)
        # makes this block a no-op, preserving the existing
        # pre-maritime synthetic capacity map byte-equivalently.
        if self.port_capacity_override:
            for port_id, factor in self.port_capacity_override.items():
                key = str(port_id)
                if key not in self.port_capacity_map:
                    # Unknown port id from the override — ignored.
                    continue
                try:
                    fv = float(factor)
                except (TypeError, ValueError):
                    continue
                if fv != fv or fv in (float("inf"), float("-inf")):
                    continue
                # Clamp into [0, 1]. 1.0 means "no change"; values
                # above 1.0 are rejected to keep the contract
                # monotone (congestion only ever reduces capacity).
                if fv < 0.0:
                    fv = 0.0
                if fv > 1.0:
                    fv = 1.0
                self.port_capacity_map[key] *= fv
    
    def _vessels_required(self, service, freq):
        import math
        return math.ceil(service.cycle_time * freq / 7)
    
    def _port_handling_cost(self, port_id: int) -> float:
        port = self.port_lookup.get(port_id)
        hc   = getattr(port, "handling_cost", 0.0) if port else 0.0
        # Use the actual port handling cost from data instead of default
        return hc if hc > 0 else self.pc_per_teu

    def _total_port_cost(self, port_id: int, teu_amount: float) -> float:
        """Calculate total port cost including handling, fixed, and variable components"""
        port = self.port_lookup.get(port_id)
        if not port:
            return teu_amount * self.pc_per_teu

        # Handling cost (per TEU)
        handling = getattr(port, "handling_cost", 0.0)
        handling_cost = handling  # Use dataset value even if zero

        # Fixed port call cost
        fixed_cost = getattr(port, "port_call_cost", 0.0)

        # Variable port call cost (per TEU)
        variable = getattr(port, "variable_port_call_cost", 0.0)

        return teu_amount * handling_cost + fixed_cost + teu_amount * variable

    def _transshipment_cost_for_flow(self, flow_amount: float, demand_idx: int) -> float:
        # Get origin and destination for this demand
        demand = self.problem.demands[demand_idx]
        # Use hub port's transshipment cost or default
        # For now, use average of origin/destination transshipment costs
        origin_port = self.port_lookup.get(demand.origin)
        dest_port = self.port_lookup.get(demand.destination)

        if origin_port and hasattr(origin_port, 'transshipment_cost') and origin_port.transshipment_cost > 0:
            return origin_port.transshipment_cost * flow_amount
        elif dest_port and hasattr(dest_port, 'transshipment_cost') and dest_port.transshipment_cost > 0:
            return dest_port.transshipment_cost * flow_amount
        else:
            return self.tc_per_teu * flow_amount

    def _port_cap(self, port_id) -> float:
        # The IP-3 override path may emit either str or int keys
        # depending on the caller's port-id convention. Coerce to
        # str before lookup so both work; the underlying
        # ``port_capacity_map`` is built from ``Port.id`` which is
        # always a string.
        return self.port_capacity_map.get(str(port_id), 50000)

    # ------------------------------------------------------------------ #
    #  Compatible services for direct satisfaction                          #
    # ------------------------------------------------------------------ #
    def compatible_services(self) -> Dict[int, List[int]]:
        compat: Dict[int, List[int]] = defaultdict(list)
        for d_idx, demand in enumerate(self.problem.demands):
            origin_svc = set(self.port_services.get(demand.origin, []))
            dest_svc   = set(self.port_services.get(demand.destination, []))
            candidates = origin_svc & dest_svc

            valid = []
            for s_idx in candidates:
                ports = self.problem.services[s_idx].ports
                try:
                    o_pos = ports.index(demand.origin)
                    d_pos = ports.index(demand.destination)
                    if o_pos < d_pos:
                        valid.append(s_idx)
                except ValueError:
                    pass
            compat[d_idx] = valid[: self.max_svc_per_demand]
        return compat

    # ------------------------------------------------------------------ #
    #  Transfer pairs — demand-volume prioritised                           #
    # ------------------------------------------------------------------ #
    def transfer_pairs(self) -> List[Tuple[int, int, int]]:
        """
        Enumerate (s1, s2, hub) pairs where services share a hub port.
        Prioritise by hub demand volume so most impactful pairs are included.
        """
        services_mask = self.chromosome.get("services", [])
        active = [
            i for i, v in enumerate(services_mask)
            if v == 1 and i < len(self.problem.services)
        ]

        seen = set()
        pairs_priority: List[Tuple[float, int, int, int]] = []

        for s1 in active:
            p1 = set(self.problem.services[s1].ports)
            for s2 in active:
                if s1 == s2:
                    continue
                p2   = set(self.problem.services[s2].ports)
                hubs = p1 & p2
                for hub in hubs:
                    key = (s1, s2, hub)
                    if key in seen:
                        continue
                    seen.add(key)
                    priority = self._port_demand.get(hub, 0.0)
                    pairs_priority.append((-priority, s1, s2, hub))

        pairs_priority.sort()
        return [
            (s1, s2, hub)
            for _, s1, s2, hub in pairs_priority[: self.max_xfer_pairs]
        ]

    # ------------------------------------------------------------------ #
    #  Solve MILP — single call                                             #
    # ------------------------------------------------------------------ #
    def solve(self) -> Dict:
        prob   = pulp.LpProblem("ShippingOpt", pulp.LpMaximize)
        compat = self.compatible_services()
        xfer   = self.transfer_pairs()

        total_demand_teu = sum(d.weekly_teu for d in self.problem.demands)

        # Decision variables
        flow: Dict          = {}
        transfer_flow: Dict = {}

        for d, svcs in compat.items():
            for s in svcs:
                flow[(d, s)] = pulp.LpVariable(f"x_{d}_{s}", lowBound=0)

        for d_idx, demand in enumerate(self.problem.demands):
            for s1, s2, hub in xfer:
                svc1 = self.problem.services[s1]
                svc2 = self.problem.services[s2]
                if demand.origin in svc1.ports and demand.destination in svc2.ports:
                    key = (d_idx, s1, s2)
                    if key not in transfer_flow:
                        transfer_flow[key] = pulp.LpVariable(
                            f"t_{d_idx}_{s1}_{s2}", lowBound=0
                        )

        unserved = {
            d: pulp.LpVariable(f"u_{d}", lowBound=0)
            for d in range(len(self.problem.demands))
        }

        # Revenue (actual satisfied demand only)
        revenue = pulp.lpSum(
            self.problem.demands[d].revenue_per_teu * flow[(d, s)]
            for (d, s) in flow
        ) + pulp.lpSum(
            self.problem.demands[d].revenue_per_teu * transfer_flow[(d, s1, s2)]
            for (d, s1, s2) in transfer_flow
        )

        # Operating cost (fixed)
        services_mask = self.chromosome.get("services", [])
        frequencies   = self.chromosome.get("frequencies", [])
        operating_cost = sum(
            self.problem.services[s].weekly_cost * max(1, round(frequencies[s]) if s < len(frequencies) else 1)
            for s in range(len(self.problem.services))
            if s < len(services_mask) and services_mask[s]
        )

        # Fuel cost based on vessel class and distance
        _ip2_fc_kwargs = _maritime_fuel_cost_kwargs(self.problem)
        fuel_cost = sum(
            calculate_weekly_fuel_cost(
                self.problem.services[s].ports,
                self.problem.distance_matrix,
                self.problem.services[s].vessel_class or "Post_panamax",
                self.problem.services[s].cycle_time or 7,
                **_ip2_fc_kwargs,
            ) * max(1, round(frequencies[s]) if s < len(frequencies) else 1)
            for s in range(len(self.problem.services))
            if s < len(services_mask) and services_mask[s]
        )

        # Transshipment cost - use port-specific rates
        transship_cost = pulp.lpSum(
            self._transshipment_cost_for_flow(transfer_flow[(d, s1, s2)], d)
            for (d, s1, s2) in transfer_flow
        )

        # Port handling cost with fixed and variable components
        port_flow_direct: Dict[int, List] = defaultdict(list)
        port_service_counts: Dict[int, Set[int]] = defaultdict(set)

        for (d, s), var in flow.items():
            for p in self.problem.services[s].ports:
                port_flow_direct[p].append(var)
                port_service_counts[p].add(s)

        # Calculate port costs: handling + fixed per service + variable per TEU
        port_handling_cost = pulp.lpSum(
            # Handling cost: per TEU
            self._port_handling_cost(p) * pulp.lpSum(vars_)
            # Variable cost: per TEU
            + pulp.lpSum(var * getattr(self.port_lookup.get(p), "variable_port_call_cost", 0.0) for var in vars_)
            # Fixed cost: per active service (regardless of flow)
            + pulp.lpSum(
                getattr(self.port_lookup.get(p), "port_call_cost", 0.0) *
                max(1, round(self.chromosome.get("frequencies", [])[s]) if s < len(self.chromosome.get("frequencies", [])) else 1)
                for s in port_service_counts[p]
            )
            for p, vars_ in port_flow_direct.items()
        )

        # Unserved demand penalty — RAISED to $300/TEU to force coverage
        unserved_penalty = self.alpha * pulp.lpSum(unserved.values())

        profit_expr = (
            revenue - operating_cost - fuel_cost - transship_cost
            - port_handling_cost - unserved_penalty
        )

        satisfied_expr = (
            pulp.lpSum(flow.values())
            + pulp.lpSum(transfer_flow.values())
        )
        coverage_reward = (
            (self.w_coverage / max(self.w_profit, 1e-6))
            * (satisfied_expr / max(total_demand_teu, 1.0))
            * abs(operating_cost + 1)
        )

        prob += profit_expr + coverage_reward
        
        # ─────────────────────────────────────────────
        # Fleet constraint 
        # ─────────────────────────────────────────────
        services_mask = self.chromosome.get("services", [])
        frequencies   = self.chromosome.get("frequencies", [])

        total_vessels_used = sum(
            self._vessels_required(self.problem.services[s],
                                max(1, round(frequencies[s]) if s < len(frequencies) else 1))
            for s in range(len(self.problem.services))
            if s < len(services_mask) and services_mask[s]
        )

        # Convert to constant constraint (since freq is fixed from GA)
        prob += total_vessels_used <= self.fleet_size

        # Constraints
        for d, demand in enumerate(self.problem.demands):
            prob += (
                pulp.lpSum(flow[(d, s)] for s in compat.get(d, []))
                + pulp.lpSum(
                    transfer_flow[(d2, s1, s2)]
                    for (d2, s1, s2) in transfer_flow if d2 == d
                )
                + unserved[d]
                == demand.weekly_teu
            )

        if self.min_coverage > 0:
            prob += satisfied_expr >= self.min_coverage * total_demand_teu

        for s in range(len(self.problem.services)):
            if s >= len(services_mask) or not services_mask[s]:
                continue
            freq     = max(1, round(frequencies[s]) if s < len(frequencies) else 1)
            svc = self.problem.services[s]
            capacity = self.problem.services[s].capacity * freq * (7 / (svc.cycle_time or 7))
            prob += (
                pulp.lpSum(flow[(d, s)] for (d, s2) in flow if s2 == s)
                + pulp.lpSum(
                    transfer_flow[(d, s1, s2)]
                    for (d, s1, s2) in transfer_flow if s1 == s or s2 == s
                )
                <= capacity
            )

        for p, vars_ in port_flow_direct.items():
            prob += pulp.lpSum(vars_) <= self._port_cap(p)

        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=self.time_limit)
        prob.solve(solver)

        status              = pulp.LpStatus[prob.status]

        # Validate MILP solver status
        if status != "Optimal":
            logger.error(
                "milp_solver_not_optimal | status=%s",
                status
            )
            return {
                "status": status,
                "profit": 0.0,
                "cost": 0.0,
                "fuel_cost": 0.0,
                "transship_cost": 0.0,
                "port_cost": 0.0,
                "total_cost": 0.0,
                "coverage": 0.0,
                "satisfied_demand": 0.0,
                "direct_demand": 0.0,
                "transship_demand": 0.0,
                "total_demand": float(total_demand_teu),
                "unserved_demand": float(total_demand_teu),
                "num_direct_vars": 0,
                "num_transfer_vars": 0,
                "num_services_used": 0,
                "selected_services": []
            }

        import math
        services_mask = self.chromosome.get("services", [])
        frequencies   = self.chromosome.get("frequencies", [])

        total_vessels_used = sum(
            math.ceil(self.problem.services[s].cycle_time * freq / 7)
            for s, freq in enumerate(frequencies)
            if s < len(services_mask) and services_mask[s]
        )

        if total_vessels_used > self.fleet_size:
            logger.warning(
                "fleet_constraint_violated | used=%d limit=%d",
                total_vessels_used,
                self.fleet_size
            )
        profit_v            = pulp.value(prob.objective) or 0.0
        direct_satisfied    = sum(pulp.value(v) or 0.0 for v in flow.values())
        transship_satisfied = sum(pulp.value(v) or 0.0 for v in transfer_flow.values())
        total_satisfied     = direct_satisfied + transship_satisfied
        unserved_teu        = sum(pulp.value(v) or 0.0 for v in unserved.values())
        coverage            = total_satisfied / total_demand_teu * 100 if total_demand_teu else 0.0
        transship_cost_v    = sum(
            self.tc_per_teu * (pulp.value(v) or 0.0) for v in transfer_flow.values()
        )
        # Recalculate port cost with all components
        port_cost_v = 0.0
        for p, vars_ in port_flow_direct.items():
            port = self.port_lookup.get(p)
            if port:
                teu_flow = sum(pulp.value(v) or 0.0 for v in vars_)
                # Handling cost
                handling = getattr(port, "handling_cost", 0.0)
                handling_cost = handling  # Use dataset value even if zero
                # Variable cost
                variable_cost = getattr(port, "variable_port_call_cost", 0.0)
                # Fixed cost per service
                fixed_cost = getattr(port, "port_call_cost", 0.0)
                num_services = len(port_service_counts.get(p, []))
                # Total port cost
                port_cost_v += teu_flow * handling_cost + teu_flow * variable_cost + fixed_cost * num_services
        # Calculate fuel cost
        fuel_cost_v = sum(
            calculate_weekly_fuel_cost(
                self.problem.services[s].ports,
                self.problem.distance_matrix,
                self.problem.services[s].vessel_class or "Post_panamax",
                self.problem.services[s].cycle_time or 7,
                **_ip2_fc_kwargs,
            ) * max(1, round(frequencies[s]) if s < len(frequencies) else 1)
            for s in range(len(self.problem.services))
            if s < len(services_mask) and services_mask[s]
        )

        total_cost_v = operating_cost + fuel_cost_v + transship_cost_v + port_cost_v

        # Objective Weight Calibration Audit - Log raw component values
        # Calculate individual components for logging
        revenue_v = sum((pulp.value(v) or 0.0) * self.problem.demands[d].revenue_per_teu for (d, s), v in flow.items())
        coverage_reward_v = profit_v - (revenue_v - operating_cost - fuel_cost_v - transship_cost_v - port_cost_v - sum(self.alpha * (pulp.value(v) or 0.0) for v in unserved.values()))

        if CONFIG.verbose_runtime_logs:
            print(f"MILP_OBJECTIVES: profit_expr={profit_v:.2f}, coverage_reward={coverage_reward_v:.2f}, "
                  f"revenue={revenue_v:.2f}, operating_cost={operating_cost:.2f}, "
                  f"fuel_cost={fuel_cost_v:.2f}, transship_cost={transship_cost_v:.2f}, "
                  f"port_cost={port_cost_v:.2f}, coverage_pct={coverage:.2f}")

        logger.info(
            "milp_solved",
            status=status, profit=round(profit_v, 2), coverage=round(coverage, 2),
            direct_teu=round(direct_satisfied, 2),
            transship_teu=round(transship_satisfied, 2),
            transfer_pairs=len(transfer_flow),
            unserved=round(unserved_teu, 2),
        )

        # Extract selected services with their loads
        selected_services_data = []
        service_loads = defaultdict(float)
        service_revenue = defaultdict(float)  # per-service revenue attribution
        for (d, s), var in flow.items():
            val = pulp.value(var) or 0.0
            if val > 0:
                service_loads[s] += val
                # Direct flow: revenue_per_teu * value belongs to service s
                service_revenue[s] += self.problem.demands[d].revenue_per_teu * val

        for (d_idx, s1, s2), var in transfer_flow.items():
            val = pulp.value(var) or 0.0
            if val > 0:
                # Transfer flow: split revenue evenly between s1 and s2
                # (freight is paid once for the lane; each leg gets half the credit)
                rev = self.problem.demands[d_idx].revenue_per_teu * val
                service_loads[s1] += val
                service_loads[s2] += val
                service_revenue[s1] += rev / 2.0
                service_revenue[s2] += rev / 2.0

        # Pre-compute per-service fuel cost (constant per service / frequency)
        def _service_fuel(svc, freq):
            if not svc.ports or len(svc.ports) < 2:
                return 0.0
            try:
                return calculate_weekly_fuel_cost(
                    svc.ports,
                    self.problem.distance_matrix,
                    svc.vessel_class or "Post_panamax",
                    svc.cycle_time or 7,
                    **_ip2_fc_kwargs,
                ) * freq
            except Exception:
                return 0.0

        # Allocate port costs proportionally to load on each port
        # port_load[p] = total TEU handled at p across all services
        port_load: Dict[int, float] = defaultdict(float)
        port_service_loads: Dict[int, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for s_idx, load in service_loads.items():
            if load <= 0 or s_idx >= len(self.problem.services):
                continue
            svc = self.problem.services[s_idx]
            for p in svc.ports:
                port_load[p] += load
                port_service_loads[p][s_idx] += load

        for s_idx, load in service_loads.items():
            if load > 0 and s_idx < len(self.problem.services):
                svc = self.problem.services[s_idx]
                # Per-service weekly cost fields
                freq = max(1, round(frequencies[s_idx]) if s_idx < len(frequencies) else 1)
                vessel_cost = float(svc.weekly_cost) * freq
                fuel = _service_fuel(svc, freq)

                # Port cost: proportional to (svc load at port p) / (port total load) * port cost
                port_alloc = 0.0
                for p in svc.ports:
                    p_port = self.port_lookup.get(p)
                    if not p_port or port_load[p] == 0:
                        continue
                    share = port_service_loads[p][s_idx] / port_load[p]
                    handling = getattr(p_port, "handling_cost", 0.0)
                    variable = getattr(p_port, "variable_port_call_cost", 0.0)
                    fixed = getattr(p_port, "port_call_cost", 0.0)
                    # Per-TEU components proportional to load
                    port_alloc += share * (load * handling + load * variable)
                    # Fixed component pro-rated by share
                    port_alloc += share * fixed

                revenue = float(service_revenue.get(s_idx, 0.0))
                total_cost_svc = vessel_cost + fuel + port_alloc
                weekly_profit_svc = revenue - total_cost_svc
                margin_pct = (
                    weekly_profit_svc / revenue * 100
                    if revenue > 0 else 0.0
                )

                selected_services_data.append({
                    "id": svc.id,
                    "ports": svc.ports,
                    "load": float(load),
                    "capacity": float(svc.capacity),
                    "vessel_class": svc.vessel_class or "Post_panamax",
                    "vessel_cost": vessel_cost,
                    "fuel_cost": float(fuel),
                    "port_cost": float(port_alloc),
                    "revenue": revenue,
                    "cost": total_cost_svc,
                    "weekly_profit": weekly_profit_svc,
                    "margin_pct": round(margin_pct, 2),
                })

        return {
            "status":            status,
            "profit":            float(profit_v),
            "cost":              float(operating_cost),
            "fuel_cost":         float(fuel_cost_v),
            "transship_cost":    float(transship_cost_v),
            "port_cost":         float(port_cost_v),
            "total_cost":        float(total_cost_v),
            "coverage":          float(coverage),
            "satisfied_demand":  float(total_satisfied),
            "direct_demand":     float(direct_satisfied),
            "transship_demand":  float(transship_satisfied),
            "total_demand":      float(total_demand_teu),
            "unserved_demand":   float(unserved_teu),
            "num_direct_vars":   len(flow),
            "num_transfer_vars": len(transfer_flow),
            "num_services_used": len(selected_services_data),
            "selected_services": selected_services_data
        }