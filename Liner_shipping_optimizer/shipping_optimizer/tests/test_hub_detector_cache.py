"""HubDetector's demand-score cache must never serve one problem's scores to another.

``id()`` values are reused after an object is freed; a cache keyed by ``id`` alone then
returned the (stale) scores of a different problem, which made the candidate pool
depend on allocation history (observed: the same seed gave different pools in
different processes).
"""
import gc
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization.data import Demand, Port, Problem
from src.services.hub_detector import HubDetector


def _problem(o, d, teu):
    return Problem(ports=[Port(o, o, 0, 0), Port(d, d, 0, 0)], services=[],
                   demands=[Demand(o, d, teu, 100.0)], distance_matrix={o: {d: 1.0}, d: {o: 1.0}})


def test_a_second_problem_never_receives_the_scores_of_a_freed_one():
    """Whether CPython hands the freed address to the next object depends on the
    allocator state of the whole test process, so the id-reuse situation is not left to
    chance: when the address was not reused naturally, the freed problem's cache entry is
    re-registered under the new problem's id - exactly the state a real reuse produces."""
    natural, forced = 0, 0
    for _ in range(300):
        p1 = _problem("A", "B", 100.0)
        assert dict(HubDetector(p1).compute_demand_scores()) == {"A": 100.0, "B": 100.0}
        old_id = id(p1)
        stale_entry = HubDetector._demand_cache.get(old_id)
        del p1
        gc.collect()
        p2 = _problem("X", "Y", 999.0)
        if id(p2) == old_id:
            natural += 1
        elif stale_entry is not None:
            HubDetector._demand_cache[id(p2)] = stale_entry
            forced += 1
        scores = dict(HubDetector(p2).compute_demand_scores())
        assert scores == {"X": 999.0, "Y": 999.0}, scores
    # the reuse scenario was exercised on every iteration, naturally or by construction
    assert natural + forced == 300


def test_a_stale_entry_registered_under_a_reused_id_is_ignored():
    p1 = _problem("A", "B", 100.0)
    HubDetector(p1).compute_demand_scores()
    p2 = _problem("X", "Y", 999.0)
    # simulate id reuse: p2's id now points at p1's cache entry
    HubDetector._demand_cache[id(p2)] = HubDetector._demand_cache[id(p1)]
    assert dict(HubDetector(p2).compute_demand_scores()) == {"X": 999.0, "Y": 999.0}


def test_the_same_problem_is_still_served_from_the_cache():
    p = _problem("A", "B", 100.0)
    first = HubDetector(p).compute_demand_scores()
    assert HubDetector(p).compute_demand_scores() is first


def test_detected_hubs_follow_the_problem_not_the_history():
    a = _problem("A", "B", 100.0)
    assert set(HubDetector(a).detect_hubs(top_k=2)) == {"A", "B"}
    del a
    gc.collect()
    b = _problem("X", "Y", 5.0)
    assert set(HubDetector(b).detect_hubs(top_k=2)) == {"X", "Y"}
