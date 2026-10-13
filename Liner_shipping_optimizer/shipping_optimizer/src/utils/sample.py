import json
from pathlib import Path
import pandas as pd
import random

from src.optimization.data import Port, Service, Demand, Problem


def load_real_dataset():

    print("Loading CSV datasets...")

    ports_df = pd.read_csv("data/ports.csv", sep="\t")
    demand_df = pd.read_csv("data/Demand_WorldLarge.csv", sep="\t")
    fleet_df = pd.read_csv("data/fleet_WorldLarge.csv", sep="\t")
    dist_df = pd.read_csv("data/dist_dense.csv")

    # --------------------------
    # Ports
    # --------------------------

    ports = []
    port_index = {}

    for i, row in ports_df.iterrows():

        port = Port(
            id=row["UNLocode"],
            name=row["name"],
            latitude=row["Latitude"],
            longitude=row["Longitude"],
            handling_cost=row["CostPerFULL"]
        )

        ports.append(port)
        port_index[row["UNLocode"]] = i

    print(f"Loaded {len(ports)} ports")

   # --------------------------
    # Distance dictionary
    # --------------------------

    dist_matrix = {}

    print("Distance CSV columns:", dist_df.columns.tolist())

    # detect columns automatically
    origin_col = None
    dest_col = None
    dist_col = None

    for c in dist_df.columns:
        lc = c.lower()

        if "orig" in lc or "from" in lc:
            origin_col = c

        if "dest" in lc or "to" in lc:
            dest_col = c

        if "dist" in lc:
            dist_col = c

    if origin_col is None or dest_col is None or dist_col is None:
        raise ValueError("Could not detect distance columns in dist_dense.csv")

    for _, row in dist_df.iterrows():

        o = row[origin_col]
        d = row[dest_col]
        dist = row[dist_col]

        if o in port_index and d in port_index:

            oi = port_index[o]
            di = port_index[d]

            dist_matrix[(oi, di)] = dist
            dist_matrix[(di, oi)] = dist

    print(f"Loaded {len(dist_matrix)} distance pairs")
    # --------------------------
    # Demand
    # --------------------------

    demands = []

    for _, row in demand_df.iterrows():

        if row["Origin"] not in port_index:
            continue

        if row["Destination"] not in port_index:
            continue

        origin = port_index[row["Origin"]]
        destination = port_index[row["Destination"]]

        demands.append(
            Demand(
                origin=origin,
                destination=destination,
                weekly_teu=row["FFEPerWeek"],
                revenue_per_teu=row["Revenue_1"]
            )
        )

    print(f"Loaded {len(demands)} demand lanes")

    # --------------------------
    # Generate Candidate Services
    # using real distances
    # --------------------------

    services = []

    FUEL_COST_PER_NM = 45
    BASE_PORT_CALL_COST = 25000

    for s in range(1200):

        route_length = random.randint(3, 6)

        route = random.sample(range(len(ports)), route_length)

        route.append(route[0])  # close loop

        # Compute route distance
        total_distance = 0

        for i in range(len(route) - 1):

            leg = (route[i], route[i+1])

            if leg in dist_matrix:
                total_distance += dist_matrix[leg]
            else:
                total_distance += 3000  # fallback estimate

        # Service cost calculation
        fuel_cost = total_distance * FUEL_COST_PER_NM
        port_cost = route_length * BASE_PORT_CALL_COST

        weekly_cost = fuel_cost + port_cost

        services.append(
            Service(
                id=s,
                ports=route,
                capacity=random.randint(3000, 8000),
                weekly_cost=weekly_cost,
                cycle_time=random.randint(7, 28)
            )
        )

    print(f"Generated {len(services)} candidate services")

    return Problem(
        ports=ports,
        services=services,
        demands=demands
    )


def save_problem(problem: Problem, filename: str):

    data = {
        "ports": [p.__dict__ for p in problem.ports],
        "services": [s.__dict__ for s in problem.services],
        "demands": [d.__dict__ for d in problem.demands]
    }

    Path("data").mkdir(exist_ok=True)

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":

    print("Generating dataset from real shipping data...")

    problem = load_real_dataset()

    output = "data/large_shipping_problem.json"

    save_problem(problem, output)

    print("+ Dataset created")
    print("Ports:", len(problem.ports))
    print("Services:", len(problem.services))
    print("Demands:", len(problem.demands))