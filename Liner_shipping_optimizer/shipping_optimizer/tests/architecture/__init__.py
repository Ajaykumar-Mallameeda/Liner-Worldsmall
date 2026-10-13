"""Phase 0 architecture guard tests.

Lightweight, dependency-free regression guards for the architectural
boundaries established by Phase 0:

- ``test_network_isolation.py`` — the optimizer must never perform or
  prepare-for network ingestion.
- ``test_output_contract.py`` — the pipeline_output.json external contract
  is frozen; future additions are additive-only (IP-5 pattern).
"""
