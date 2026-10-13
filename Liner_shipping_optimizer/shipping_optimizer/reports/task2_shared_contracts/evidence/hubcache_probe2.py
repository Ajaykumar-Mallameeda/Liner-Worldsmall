import gc, os, sys
sys.path.insert(0, os.getcwd())
from src.services.hub_detector import HubDetector
from src.optimization.data import Problem, Port, Demand

def mk(od):
    ports = [Port(id=i, name=i, latitude=0.0, longitude=0.0) for i in "ABCD"]
    return Problem(ports=ports, services=[], demands=[Demand(o, d, t, 1.0) for o, d, t in od], distance_matrix={})

coll = hits = 0; trials = 2000
for k in range(trials):
    a = mk([("A", "B", 100.0)])
    ida = id(a)
    HubDetector(a).detect_hubs(top_k=1)
    del a
    b = mk([("C", "D", 900.0)])
    if id(b) == ida:
        coll += 1
        h = HubDetector(b).detect_hubs(top_k=1)
        if h[0] not in ("C", "D"):
            hits += 1
    # deliberately NOT clearing the class-level cache
print(f"id collisions: {coll}/{trials}; contaminated hub results among collisions: {hits}")
print("cache entries retained at exit:", len(HubDetector._demand_cache))
