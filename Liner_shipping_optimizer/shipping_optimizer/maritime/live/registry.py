"""Phase 4 — Live provider registry.

Maps provider-name strings to provider classes. The registry is the
single place where the live layer enumerates which providers are
known. Adding a new provider means adding an entry here; no other
file in the live layer needs to change.
"""

from __future__ import annotations

import os
from typing import Dict, List, Type

from .digitraffic import DigitrafficProvider
from .provider import BaseLiveProvider


# Map provider name -> provider class. Names are stable identifiers
# (used in env vars and API responses).
_PROVIDER_REGISTRY: Dict[str, Type[BaseLiveProvider]] = {
    "digitraffic": DigitrafficProvider,
    "aisstream": None,  # type: ignore[dict-item]  # explicit placeholder; see PHASE 4 report
}


def register(name: str, cls: Type[BaseLiveProvider]) -> None:
    """Register a provider class under a stable name."""
    if not name or not isinstance(name, str):
        raise ValueError("provider name must be a non-empty string")
    if not (isinstance(cls, type) and issubclass(cls, BaseLiveProvider)):
        raise TypeError(f"{cls!r} is not a BaseLiveProvider subclass")
    _PROVIDER_REGISTRY[name] = cls


def get_provider_class(name: str) -> Type[BaseLiveProvider]:
    """Return the provider class for ``name`` or raise ``KeyError``."""
    cls = _PROVIDER_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown live provider: {name!r}")
    return cls  # type: ignore[return-value]


def list_providers() -> List[Dict[str, str]]:
    """Return a JSON-friendly list of registered provider names.

    The shape is stable so the dashboard can render it directly.
    Disabled-by-default providers are flagged with ``disabled_by_default``.
    """
    out: List[Dict[str, str]] = []
    for name, cls in _PROVIDER_REGISTRY.items():
        if cls is None:
            out.append({
                "name": name,
                "label": name.upper(),
                "license": "unresolved",
                "attribution": "",
                "status": "disabled_by_default",
                "enabled": False,
                "reason": "DEV_ONLY",
            })
            continue
        out.append({
            "name": name,
            "label": getattr(cls, "source", name.upper()),
            "license": "CC BY 4.0" if name == "digitraffic" else "unresolved",
            "attribution": "Fintraffic / digitraffic.fi" if name == "digitraffic" else "",
            "status": "available" if _env_enabled(name) else "off",
            "enabled": _env_enabled(name),
        })
    return out


def _env_enabled(name: str) -> bool:
    """Read ``MARITIME_LIVE_PROVIDER`` and compare with the given name."""
    raw = os.environ.get("MARITIME_LIVE_PROVIDER", "").strip().lower()
    return raw == name.lower() and os.environ.get("MARITIME_LIVE_ENABLED", "0").lower() in (
        "1", "true", "yes", "on",
    )


__all__ = [
    "register",
    "get_provider_class",
    "list_providers",
]
