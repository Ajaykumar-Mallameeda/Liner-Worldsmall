"""LLM actuation ledger.

A lightweight, thread-safe tracker that records per-agent LLM calls,
capturing provider / model / latency / status / decision_source /
decision_consumed.  This is the substrate for the
"AI decision actually consumed downstream" audit mandated by Phase M.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


logger = logging.getLogger("llm.actuation")


@dataclass
class ActuationRecord:
    component: str               # "coordinator" | "iteration_selector" | ...
    provider: str = ""
    model: str = ""
    role: str = ""
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    fallback_uses: int = 0
    cache_hits: int = 0
    error_429: int = 0
    error_timeout: int = 0
    error_connection: int = 0
    error_auth: int = 0
    error_invalid_model: int = 0
    error_invalid_json: int = 0
    error_unknown: int = 0
    latency_sec: float = 0.0
    total_latency_sec: float = 0.0
    decision_source: str = "unknown"     # "llm" | "rule-based"
    decision_consumed: bool = False
    ai_generated: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LLMActuationLedger:
    """Thread-safe accumulator of per-component LLM actuations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[ActuationRecord] = []
        self._by_component: Dict[str, ActuationRecord] = {}

    def begin(self, component: str) -> ActuationRecord:
        rec = ActuationRecord(component=component)
        with self._lock:
            self._records.append(rec)
            self._by_component[component] = rec
        return rec

    def get(self, component: str) -> Optional[ActuationRecord]:
        with self._lock:
            return self._by_component.get(component)

    def all(self) -> List[ActuationRecord]:
        with self._lock:
            return list(self._records)

    def summary(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for r in self.all():
            out[r.component] = r.to_dict()
        return out


# Module-level singleton — every agent writes into the same ledger.
actuation_ledger = LLMActuationLedger()
