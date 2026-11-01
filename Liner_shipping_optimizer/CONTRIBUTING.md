# Contributing

Thank you for considering a contribution to the Liner Shipping Network Optimizer. This document describes the development workflow, engineering conventions, and priority areas for improvement.

---

## Development Setup

```bash
git clone https://github.com/112301021/Liner_shipping_optimizer.git
cd Liner_shipping_optimizer/shipping_optimizer

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, black, mypy, ruff

cp .env.example .env
# Add your OPENROUTER_API_KEY
```

---

## Branch Strategy

```
main              ← stable, tagged releases only
dev               ← integration branch (PRs merge here)
feat/<name>       ← new features
fix/<name>        ← bug fixes
perf/<name>       ← performance improvements
refactor/<name>   ← structural refactoring
```

Create a branch from `dev`, not `main`.

---

## Pull Request Requirements

Before submitting a PR:

- [ ] `pytest tests/` passes (unit + integration tests)
- [ ] `ruff check src/` passes (linting)
- [ ] `mypy src/` passes on changed modules
- [ ] New functionality has corresponding tests
- [ ] Architecture changes update `docs/SYSTEM_ARCHITECTURE.md`
- [ ] Data structure changes update `docs/DATA_DICTIONARY.md`
- [ ] PR description explains *why*, not just *what*

---

## Priority Improvement Areas

These are the highest-value engineering contributions, ordered by impact:

### 1. Distance memoization in HubMILP (performance — quick win)

**File:** `src/optimization/hub_milp.py`

```python
from functools import lru_cache

@lru_cache(maxsize=200_000)
def _get_distance(self, origin: int, destination: int) -> float:
    return self.problem.distance_matrix.get(origin, {}).get(destination, 1e9)
```

Expected impact: 2–5× MILP speedup on WorldLarge.

### 2. Immutable Problem snapshots (correctness)

**File:** `src/agents/orchestrator_agent.py`, `_apply_feedback` method

```python
from copy import deepcopy

def _apply_feedback(self, problem: Problem, decision_output: Dict) -> Problem:
    snapshot = deepcopy(problem)   # never mutate the shared object
    # apply weight adjustments to snapshot
    return snapshot
```

### 3. Full async regional execution (scalability)

**File:** `src/agents/orchestrator_agent.py`

```python
import asyncio

async def _run_regions_async(self, agents, regional_problems):
    tasks = [
        asyncio.create_task(asyncio.to_thread(agent.process, {"problem": rp}))
        for agent, rp in zip(agents, regional_problems.values())
    ]
    return await asyncio.gather(*tasks)
```

### 4. WebSocket event schema standardization (reliability)

All backend components should emit events through a single validated path. Currently some components bypass `EventValidator`. A simple `@dataclass` event schema with `to_json()` would eliminate the schema mismatches causing frontend integration failures.

### 5. Adaptive MILP transfer pair limit (correctness on dense networks)

Replace the hardcoded `MAX_TRANSFER_PAIRS = 2000` with a density-adaptive formula:

```python
demand_density = len(problem.demands) / max(len(problem.ports) ** 2, 1)
max_pairs = min(2000, max(500, int(1000 / demand_density)))
```

---

## Code Style

- Type hints on all public functions and methods
- Google-style docstrings for public APIs
- Structured logging via `structlog` — never `print()`
- Constants at module level, not scattered as magic numbers
- No mutable default arguments

---

## Testing

```bash
# Unit tests only (fast, no API key required)
pytest tests/test_clustering.py tests/test_ga.py tests/test_milp.py -v

# Full integration test (requires API key, 5–10 minutes)
python tests/test_orchestrator.py

# Coverage report
pytest --cov=src --cov-report=term-missing tests/
```

Test files live alongside the modules they test under `tests/`. Integration tests that require the full pipeline are in `tests/test_orchestrator.py` and are clearly marked as slow.

---

## Commit Convention

```
type(scope): short description

Types: feat · fix · perf · refactor · test · docs · chore
Scope: agent · ga · milp · decomp · api · deploy · data
```

Example:
```
perf(milp): add lru_cache memoization to distance lookups

Reduces HubMILP solve time by 3.2× on WorldLarge instance
by caching the O(n²) distance matrix lookups. Cache size
set to 200K entries (~6 MB overhead for 435-port network).
```

---

## Reporting Issues

Include:

1. Python version, OS
2. Instance size (ports, demands)
3. Full error message and stack trace
4. Steps to reproduce
5. What you expected vs. what happened

Use the GitHub issue template.
