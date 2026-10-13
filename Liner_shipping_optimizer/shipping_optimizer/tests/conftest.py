"""Test isolation (decision phase).

``src.utils.health_tracker.health_tracker`` is a process-wide singleton.  Tests that run an
``OrchestratorAgent`` with MagicMock regional agents append MagicMock objects to its ``regions_completed``;
a later test that serialises the orchestrator result (``tests/test_orchestrator.py``) then fails inside
``json.dump`` ("Object of type MagicMock is not JSON serializable"), the error was swallowed and a
TRUNCATED ``pipeline_output.json`` was left on disk (reproduced on the baseline tag, full suite and
``test_multi_agent_coordination.py`` + ``test_orchestrator.py`` in one process).

Resetting the tracker before every test removes the cross-test state without touching any assertion.
"""
import pytest


@pytest.fixture(autouse=True)
def _fresh_health_tracker():
    try:
        from src.utils.health_tracker import health_tracker
    except Exception:                                   # pragma: no cover - module absent in a trimmed tree
        yield
        return
    health_tracker._reset()
    yield
    health_tracker._reset()
