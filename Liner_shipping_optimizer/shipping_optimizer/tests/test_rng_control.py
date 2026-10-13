"""Task 17 - opt-in, centralised random-number control (``LINER_SEED``, src/utils/rng.py).

Contract
  * ``LINER_SEED`` unset: the process-global generators are used exactly as before (the existing
    tests that seed ``random`` / ``numpy.random`` themselves keep working);
  * set: every stochastic component draws from its own generator derived from (seed, component,
    region, call index) - identical across runs, and independent of the order components run in
    (the orchestrator runs regions in a thread pool, so a shared global generator is not).
"""
import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import rng as rngmod
from src.optimization.frequency_ga import FrequencyGA
from src.optimization.service_ga import ServiceGA
from src.services.candidate_service_generator import CandidateServiceGenerator
from tests.test_ga import _build_problem


@pytest.fixture(scope="module")
def problem():
    return _build_problem(seed=4242)


class TestSeedHandling:
    def test_unset_is_none_and_global_generators(self, monkeypatch):
        monkeypatch.delenv("LINER_SEED", raising=False)
        assert rngmod.seed_from_environment() is None
        s = rngmod.streams("service_ga", "Asia#1")
        assert s.py is random and s.np is np.random and s.seed is None

    def test_parsing_and_errors(self, monkeypatch):
        monkeypatch.setenv("LINER_SEED", "17")
        assert rngmod.seed_from_environment() == 17
        monkeypatch.setenv("LINER_SEED", "-1")
        with pytest.raises(ValueError):
            rngmod.seed_from_environment()
        monkeypatch.setenv("LINER_SEED", "abc")
        with pytest.raises(ValueError):
            rngmod.seed_from_environment()

    def test_derived_seeds_are_stable_and_label_dependent(self):
        a = rngmod.derive_seed(7, "service_ga", "Asia#1")
        assert a == rngmod.derive_seed(7, "service_ga", "Asia#1")
        assert a != rngmod.derive_seed(7, "service_ga", "Asia#2")
        assert a != rngmod.derive_seed(7, "frequency_ga", "Asia#1")
        assert a != rngmod.derive_seed(8, "service_ga", "Asia#1")
        # pinned value: the derivation must never depend on PYTHONHASHSEED or the platform
        assert rngmod.derive_seed(7, "service_ga", "Asia#1") == 4587962692285842661

    def test_seeded_streams_repeat(self, monkeypatch):
        monkeypatch.setenv("LINER_SEED", "5")
        s1, s2 = rngmod.streams("x", "r"), rngmod.streams("x", "r")
        assert [s1.py.random() for _ in range(5)] == [s2.py.random() for _ in range(5)]
        assert list(s1.np.integers(0, 100, 5)) == list(s2.np.integers(0, 100, 5))
        assert s1.seed == s2.seed is not None


class TestComponentsAreReproducible:
    def _service_ga(self, problem, seed):
        return ServiceGA(problem, pop_size=20, generations=6, rng=random.Random(seed),
                         np_rng=np.random.default_rng(seed)).run()

    def test_service_ga_same_seed_same_result_whatever_the_global_state(self, problem):
        a = self._service_ga(problem, 11)
        random.seed(999)                       # disturb the global generators between runs
        np.random.seed(999)
        random.random()
        b = self._service_ga(problem, 11)
        assert a == b

    def test_seeded_components_never_touch_the_global_generators(self, problem):
        """With its own generators a component must leave ``random`` / ``numpy.random`` untouched: that is
        what makes its result independent of every other thread's draws."""
        random.seed(123)
        np.random.seed(123)
        py_state, np_state = random.getstate(), np.random.get_state()
        mask = ServiceGA(problem, pop_size=20, generations=3, rng=random.Random(5),
                         np_rng=np.random.default_rng(5)).run()
        FrequencyGA(problem, mask, pop_size=20, generations=3, rng=random.Random(5)).run()
        CandidateServiceGenerator(problem, rng=random.Random(5)).generate_services(20)
        assert random.getstate() == py_state
        after = np.random.get_state()
        assert after[0] == np_state[0] and (after[1] == np_state[1]).all() and after[2:] == np_state[2:]

    def test_the_streams_of_two_seeds_differ(self):
        a, b = random.Random(11), random.Random(12)
        assert [a.random() for _ in range(5)] != [b.random() for _ in range(5)]
        x, y = np.random.default_rng(11), np.random.default_rng(12)
        assert list(x.integers(0, 10 ** 9, 5)) != list(y.integers(0, 10 ** 9, 5))

    def test_order_independence(self, problem):
        """Two components drawing from their own streams give the same results in either order
        (the property a shared global generator lacks under a thread pool)."""
        def run(order):
            out = {}
            for name in order:
                out[name] = self._service_ga(problem, {"A": 21, "B": 22}[name])
            return out
        assert run(["A", "B"]) == run(["B", "A"])

    def test_frequency_ga_same_seed_same_result(self, problem):
        mask = self._service_ga(problem, 31)
        f1 = FrequencyGA(problem, mask, pop_size=20, generations=6, rng=random.Random(3)).run()
        f2 = FrequencyGA(problem, mask, pop_size=20, generations=6, rng=random.Random(3)).run()
        assert list(f1) == list(f2)

    def test_candidate_generator_same_seed_same_pool(self, problem):
        def pool(seed):
            g = CandidateServiceGenerator(problem, rng=random.Random(seed))
            return [tuple(getattr(s, "ports", ())) for s in g.generate_services(40)]
        assert pool(5) == pool(5)

    def test_unseeded_generators_still_honour_global_seeding(self, problem):
        random.seed(77)
        np.random.seed(77)
        a = ServiceGA(problem, pop_size=20, generations=6).run()
        random.seed(77)
        np.random.seed(77)
        b = ServiceGA(problem, pop_size=20, generations=6).run()
        assert a == b


class TestCandidateGeneratorStreamsPerRegionAndCall:
    """Found by the full-pipeline comparison (Phase 7): with one stream label for every region and every
    iteration, a seeded run produced the SAME candidate pool in all iterations, collapsing the
    best-of-three exploration.  Each (region, call) now has its own repeatable stream."""

    def test_labels_give_distinct_but_repeatable_streams(self, monkeypatch):
        monkeypatch.setenv("LINER_SEED", "5")
        from src.utils.rng import streams
        a1 = [streams("candidate_generator", "Asia#1").py.random() for _ in range(3)]
        a1b = [streams("candidate_generator", "Asia#1").py.random() for _ in range(3)]
        a2 = [streams("candidate_generator", "Asia#2").py.random() for _ in range(3)]
        e1 = [streams("candidate_generator", "Europe#1").py.random() for _ in range(3)]
        assert a1 == a1b and a1 != a2 and a1 != e1

    def test_regional_agent_labels_each_call(self):
        import inspect
        from src.agents import regional_agent as ra
        src = inspect.getsource(ra.RegionalAgent.process)
        assert 'svc_agent.rng_label = f"{self.region}#{self._svc_calls}"' in src

