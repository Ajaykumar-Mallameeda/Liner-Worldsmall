"""Phase 3 — Schema version registry.

Centralizes schema-version compatibility decisions so the verifier,
the publisher, and the fallback resolver all agree on what counts as
"compatible".

The registry is intentionally simple — a static mapping from
``<dataset_key>`` to a list of compatible schema versions. It has no
I/O, no globals, and no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SchemaPolicy:
    """Per-dataset schema compatibility policy."""
    dataset: str
    compatible_versions: Tuple[str, ...] = ("1.0.0",)
    current_version: str = "1.0.0"

    def is_compatible(self, version: str) -> bool:
        return version in self.compatible_versions


# Default policy: anything we publish today is 1.0.0.
_DEFAULT_POLICY = SchemaPolicy(dataset="__default__")


class SchemaRegistry:
    """In-memory schema-version registry.

    Construct with a mapping of ``{dataset_key: SchemaPolicy}``; use
    :meth:`compatible_versions` and :meth:`is_compatible` to answer
    compatibility questions. Datasets without an explicit policy use
    the default policy (compatible = ``{"1.0.0"}``).
    """

    def __init__(
        self,
        policies: Optional[Mapping[str, SchemaPolicy]] = None,
    ) -> None:
        self._policies: Dict[str, SchemaPolicy] = dict(policies or {})

    @classmethod
    def with_defaults(cls) -> "SchemaRegistry":
        """Return a registry seeded with the standard maritime datasets."""
        return cls(
            policies={
                "emodnet_vessel_density": SchemaPolicy(
                    dataset="emodnet_vessel_density",
                    compatible_versions=("1.0.0",),
                    current_version="1.0.0",
                ),
                "noaa_ais_port_intelligence": SchemaPolicy(
                    dataset="noaa_ais_port_intelligence",
                    compatible_versions=("1.0.0",),
                    current_version="1.0.0",
                ),
            }
        )

    def policy_for(self, dataset: str) -> SchemaPolicy:
        return self._policies.get(dataset, _DEFAULT_POLICY)

    def compatible_versions(self, dataset: str) -> Tuple[str, ...]:
        return self.policy_for(dataset).compatible_versions

    def is_compatible(self, dataset: str, version: str) -> bool:
        return self.policy_for(dataset).is_compatible(version)

    def register(self, policy: SchemaPolicy) -> None:
        """Register or replace a policy for a dataset."""
        self._policies[policy.dataset] = policy
