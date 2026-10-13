"""Maritime ingestion boundary.

All network-capable code for external maritime sources MUST live here. The
optimizer never imports this package — only the feature adapter does, and
the feature adapter calls into the storage layer for cached snapshots, not
into the ingestion layer at runtime.
"""

from .base import IngestionResult, IngestionError, BaseIngestionProvider
from .emodnet import EmodnetProvider, EmodnetConfig

__all__ = [
    "IngestionResult",
    "IngestionError",
    "BaseIngestionProvider",
    "EmodnetProvider",
    "EmodnetConfig",
]
