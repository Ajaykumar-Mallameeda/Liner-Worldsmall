"""Central, opt-in random-number control (Task 17).

``LINER_SEED`` (a non-negative integer) - unset: every stochastic component keeps drawing from the
process-global generators (``random`` / ``numpy.random``) exactly as before, so nothing changes.

Set: every stochastic component draws from its OWN generator, derived from
``(LINER_SEED, component, region, call index)`` with a stable hash.  Results then do not depend on
which thread ran first or on the order in which regions executed, which the shared global generator
cannot guarantee (the orchestrator runs regions in a thread pool).

What this does NOT control (documented, see reports/campaign_*/task17_reproducibility_report.md):
the wall-clock budgets of the genetic algorithms and of CBC, the LLM providers' answers, and the
iteration order of string sets under a randomised ``PYTHONHASHSEED``.
"""

from __future__ import annotations

import hashlib
import os
import random
from typing import Dict, NamedTuple, Optional

import numpy as np

ENV_SEED = "LINER_SEED"


class Streams(NamedTuple):
    py: object            # ``random.Random`` (seeded) or the ``random`` module (unseeded)
    np: object            # ``numpy.random.Generator`` (seeded) or the ``numpy.random`` module
    seed: Optional[int]   # the derived seed, None when unseeded


def seed_from_environment(env: Optional[Dict[str, str]] = None) -> Optional[int]:
    raw = ((os.environ if env is None else env).get(ENV_SEED) or "").strip()
    if not raw:
        return None
    try:
        v = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_SEED} must be a non-negative integer, got {raw!r}") from None
    if v < 0:
        raise ValueError(f"{ENV_SEED} must be a non-negative integer, got {v}")
    return v


def derive_seed(base: int, *labels) -> int:
    """Stable 63-bit seed of ``base`` and the labels (independent of PYTHONHASHSEED)."""
    h = hashlib.sha256(("|".join([str(int(base))] + [str(x) for x in labels])).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & ((1 << 63) - 1)


def streams(*labels, base_seed: Optional[int] = None) -> Streams:
    """Generators for one component.  Unseeded: the global generators (behaviour unchanged)."""
    base = seed_from_environment() if base_seed is None else base_seed
    if base is None:
        return Streams(random, np.random, None)
    s = derive_seed(base, *labels)
    return Streams(random.Random(s), np.random.default_rng(s), s)
