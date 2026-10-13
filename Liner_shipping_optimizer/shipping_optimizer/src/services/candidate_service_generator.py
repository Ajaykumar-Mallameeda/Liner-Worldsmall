from collections import defaultdict
import random


class CandidateServiceGenerator:

    def __init__(self, problem, rng=None):

        self.problem = problem
        self._rng = rng if rng is not None else random      # LINER_SEED: own generator when given


    # ------------------------------------------------
    # Find high-demand corridors
    # ------------------------------------------------
    def find_demand_corridors(self, top_k=100):

        corridor_demand = defaultdict(float)

        for d in self.problem.demands:

            key = (d.origin, d.destination)
            corridor_demand[key] += d.weekly_teu

        corridors = sorted(
            corridor_demand.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [c[0] for c in corridors[:top_k]]


    # ------------------------------------------------
    # Generate services along corridors
    # ------------------------------------------------
    def generate_corridor_services(self, corridors):

        services = []

        for origin, destination in corridors:

            route = [origin]

            # optional hub insertion - calibrated for better strategy balance
            hub_prob = 0.25  # Reduced to 25% for more direct services

            # Further reduce hub insertion for high-demand corridors
            corridor_demand = sum(
                d.weekly_teu for d in self.problem.demands
                if d.origin == origin and d.destination == destination
            )
            if corridor_demand > 1000:  # High-demand corridor
                hub_prob = 0.15  # Only 15% hub insertion for major corridors

            if self._rng.random() < hub_prob:
                # Prefer actual major hubs over random ports. The inserted hub must be
                # a third port: a hub equal to the origin or destination would make a
                # rotation that visits a port twice (a zero-length leg).
                major_hubs = ['HKG', 'SIN', 'ROT', 'NYC', 'SHA', 'CNXHG', 'SGSIN', 'NLRTM', 'USLAX', 'DEBRV']
                ends = (origin, destination)
                available_hubs = [h for h in major_hubs
                                  if h in self.problem.distance_matrix and h not in ends]
                if available_hubs:
                    hub = self._rng.choice(available_hubs)
                else:
                    others = [p for p in self.problem.distance_matrix if p not in ends]
                    hub = self._rng.choice(others) if others else None
                if hub is not None:
                    route.append(hub)

            route.append(destination)

            services.append({
                "ports": route
            })

        return services


    # ------------------------------------------------
    # Add regional feeder services
    # ------------------------------------------------
    def generate_feeders(self, hubs, num=100):

        services = []

        ports = [p.id for p in self.problem.ports]

        # Track hub usage to ensure balanced feeder distribution
        hub_usage = {hub: 0 for hub in hubs}
        feeders_per_hub = num // len(hubs)

        for _ in range(num):

            # Choose hub with least feeders for balance
            hub = min(hubs, key=lambda h: hub_usage[h])
            hub_usage[hub] += 1

            # Prefer nearby ports for realistic feeder routes
            nearby_ports = []
            if hub in self.problem.distance_matrix:
                distances = self.problem.distance_matrix[hub]
                # Sort by distance and take closer ports
                sorted_ports = sorted(distances.items(), key=lambda x: x[1])
                nearby_ports = [p for p, d in sorted_ports[:20] if p != hub]

            if nearby_ports:
                spoke = self._rng.choice(nearby_ports)
            else:
                spoke = self._rng.choice(ports)

            if hub == spoke:
                continue

            services.append({
                "ports": [hub, spoke]
            })

        return services


    # ------------------------------------------------
    # Main generation function
    # ------------------------------------------------
    def generate_services(self, num_services=400):

        corridors = self.find_demand_corridors(150)

        corridor_services = self.generate_corridor_services(corridors)

        # detect hubs (top demand ports)
        port_demand = defaultdict(float)

        for d in self.problem.demands:
            port_demand[d.origin] += d.weekly_teu
            port_demand[d.destination] += d.weekly_teu

        hubs = sorted(
            port_demand,
            key=port_demand.get,
            reverse=True
        )[:10]

        feeder_services = self.generate_feeders(hubs, 150)

        all_services = corridor_services + feeder_services

        return all_services[:num_services]