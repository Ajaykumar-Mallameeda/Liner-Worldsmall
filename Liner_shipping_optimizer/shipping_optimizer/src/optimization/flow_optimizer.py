class FlowOptimizer:

    def __init__(self, problem, milp_result, chromosome=None):

        self.problem = problem
        self.result = milp_result
        self.chromosome = chromosome

    def compute_metrics(self):

        satisfied = self.result.get("satisfied_demand", 0)
        profit = self.result.get("profit", 0)

        total_demand = sum(d.weekly_teu for d in self.problem.demands)

        coverage = satisfied / total_demand if total_demand else 0

        # Capacity supplied by chosen services
        capacity = 0
        vessels = 0

        if self.chromosome:

            for i, svc in enumerate(self.problem.services):

                if self.chromosome["services"][i]:

                    freq = self.chromosome["frequencies"][i]

                    capacity += svc.capacity * freq

                    vessels += max(1, int(svc.cycle_time / 7)) * freq

        utilization = satisfied / capacity if capacity else 0

        # Hub usage statistics
        port_calls = {}

        if self.chromosome:

            for i, svc in enumerate(self.problem.services):

                if self.chromosome["services"][i]:

                    for p in svc.ports:

                        port_calls[p] = port_calls.get(p, 0) + 1

        top_hubs = sorted(
            port_calls.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {

            "profit": profit,

            "coverage": coverage,

            "satisfied_demand": satisfied,

            "total_demand": total_demand,

            "capacity": capacity,

            "capacity_utilization": utilization,

            "vessels_required": vessels,

            "services_used": sum(self.chromosome["services"]) if self.chromosome else 0,

            "top_hubs": top_hubs

        }