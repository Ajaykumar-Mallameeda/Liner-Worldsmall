"""Bunker (marine fuel) price model: pinned snapshots, per-rotation resolution.

Why this exists
    The canonical files give fuel *quantities* (t/day at design speed, idle t/day)
    but no price. The pipeline used one universal 600 USD/t (LINERLIB benchmark
    documentation). This module makes the price an explicit, versioned, auditable
    INPUT - separate from the quantities - so the optimiser, the service model and
    the independent ledger can all use the same applicable price and the ledger can
    verify cost from tonnes x price.

Two modes
    ``legacy_uniform``    one price for every service (default 600 USD/t). It is the
                          benchmark-era assumption, labelled ``assumed``.
    ``regional_snapshot`` a pinned snapshot of dated observations for named
                          bunkering ports plus an optional global reference.

Resolution rule (regional_snapshot)
    A service's fuel is assumed to be purchased at ONE declared bunkering port: the
    lowest-priced *observed* bunkering port among the ports of its rotation (tie ->
    smallest UN/LOCODE). The rotation's ports are the only evidence linking a
    service to a price; nothing is inferred from geography. This is an explicit
    assumption (an optimistic bound: operators do bunker where it is cheap) and the
    chosen port, price, observation date and basis are reported per service.
    A rotation that calls at no observed port uses the snapshot's *global
    reference* (basis ``global_reference``) when ``fallback == "reference"``, or
    fails with ``BunkerPriceError`` when ``fallback == "error"``. Nothing is ever
    priced at zero and a missing price is never replaced by the legacy constant.

Snapshot file (JSON, ``schema_version`` 1)
    {
      "schema_version": 1, "snapshot_id": "...", "fuel_grade": "VLSFO",
      "currency": "USD", "unit": "USD_per_metric_tonne",
      "as_of": "YYYY-MM-DD", "max_age_days": 14,
      "description": "...", "licence_note": "...",
      "observations": [ {"hub": "SGSIN", "price": 889.5, "observed_on": "YYYY-MM-DD",
                         "provenance": "observed|derived|assumed",
                         "source": "...", "source_url": "...", "note": "...",
                         "bunkering_location": "..."} ],
      "reference":   {"hub": "GLOBAL", ...same fields...}
    }

Reproducibility
    ``BunkerPriceSnapshot.sha256`` is the SHA-256 of the canonical JSON of the
    validated content, so a run is pinned to exact prices by (snapshot_id, sha256).
    Staleness is evaluated against a *pinned* ``valuation_date`` (default: the
    snapshot's ``as_of``), never against the wall clock, so a replay is repeatable.

No consumption-versus-speed law and no FX conversion is implemented: a unit or
currency other than USD per metric tonne is rejected, because a rate would have to
be invented.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

SCHEMA_VERSION = 1
CANONICAL_UNIT = "USD_per_metric_tonne"
CANONICAL_CURRENCY = "USD"

LEGACY_UNIFORM_USD_PER_T = 600.0
LEGACY_SOURCE = "assumed: LINERLIB benchmark documentation (600 USD per metric ton)"

MODE_LEGACY = "legacy_uniform"
MODE_SNAPSHOT = "regional_snapshot"

RULE_CHEAPEST_OBSERVED = "cheapest_observed_port_on_rotation"
RULE_REFERENCE_ONLY = "reference_only"
LOCATION_RULES = (RULE_CHEAPEST_OBSERVED, RULE_REFERENCE_ONLY)

FALLBACK_REFERENCE = "reference"
FALLBACK_ERROR = "error"
FALLBACKS = (FALLBACK_REFERENCE, FALLBACK_ERROR)

PROVENANCES = ("observed", "derived", "assumed")

BASIS_LEGACY = "legacy_uniform"
BASIS_OBSERVED_PORT = "observed_port"
BASIS_REFERENCE = "global_reference"
REFERENCE_HUB = "GLOBAL"

# spellings of the ONE supported unit (no conversion happens: they are synonyms)
_UNIT_SYNONYMS = {
    "usd_per_metric_tonne", "usd/mt", "$/mt", "usd/t", "$/t", "usd/tonne", "usd per metric tonne",
    "usd/metric tonne", "usd_per_mt", "usd per mt",
}


class BunkerPriceError(ValueError):
    """A fuel price cannot be established (never replaced by a default)."""

    def __init__(self, message: str, reasons: Sequence[str] = ()):
        super().__init__(message)
        self.reasons: List[str] = list(reasons)


# ----------------------------------------------------------------------------------
# data classes (frozen + tuples => hashable: they are part of the model-cache key)
# ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class PriceObservation:
    hub: str
    price_usd_per_t: float
    observed_on: str
    provenance: str
    source: str
    source_url: str = ""
    note: str = ""
    # where the fuel behind this price is assumed to be bought (e.g. "alongside at the
    # quoted port"; a global index has no port). Part of the pinned content.
    bunkering_location: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"hub": self.hub, "price_usd_per_t": self.price_usd_per_t,
                "observed_on": self.observed_on, "provenance": self.provenance,
                "source": self.source, "source_url": self.source_url, "note": self.note,
                "bunkering_location": self.bunkering_location}


@dataclass(frozen=True)
class BunkerPriceSnapshot:
    snapshot_id: str
    fuel_grade: str
    as_of: str
    max_age_days: int
    observations: Tuple[PriceObservation, ...]
    reference: Optional[PriceObservation]
    sha256: str
    currency: str = CANONICAL_CURRENCY
    unit: str = CANONICAL_UNIT
    description: str = ""
    licence_note: str = ""

    def observation_for(self, hub: str) -> Optional[PriceObservation]:
        for o in self.observations:
            if o.hub == hub:
                return o
        return None

    @property
    def hubs(self) -> Tuple[str, ...]:
        return tuple(o.hub for o in self.observations)


@dataclass(frozen=True)
class FuelPriceResolution:
    """The price that applies to one rotation and WHY."""

    price_usd_per_t: float
    basis: str                              # legacy_uniform | observed_port | global_reference
    bunkering_port: Optional[str]
    observed_on: Optional[str]
    provenance: str                         # observed | derived | assumed
    snapshot_id: str
    observed_ports_on_rotation: Tuple[Tuple[str, float], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"fuel_price_usd_per_t": self.price_usd_per_t, "fuel_price_basis": self.basis,
                "bunkering_port": self.bunkering_port, "price_observed_on": self.observed_on,
                "price_provenance": self.provenance, "price_snapshot_id": self.snapshot_id}


# ----------------------------------------------------------------------------------
# snapshot loading / validation
# ----------------------------------------------------------------------------------
def _canonical_unit(unit: Any) -> str:
    if isinstance(unit, str) and unit.strip().lower() in _UNIT_SYNONYMS:
        return CANONICAL_UNIT
    raise BunkerPriceError(
        f"unsupported price unit {unit!r}: only USD per metric tonne is supported "
        f"(no conversion factor is invented)", ["unsupported_unit"])


def _parse_date(value: Any, what: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise BunkerPriceError(f"{what} is not an ISO date: {value!r}", ["invalid_snapshot"]) from None


def _parse_observation(raw: Any, *, is_reference: bool = False) -> PriceObservation:
    if not isinstance(raw, Mapping):
        raise BunkerPriceError("price observation must be an object", ["invalid_snapshot"])
    hub = raw.get("hub")
    if not isinstance(hub, str) or not hub.strip():
        raise BunkerPriceError("price observation without a hub", ["invalid_snapshot"])
    price = raw.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        raise BunkerPriceError(
            f"price for {hub!r} must be a finite number > 0, got {price!r} "
            f"(a missing price is never read as zero)", ["invalid_price"])
    prov = raw.get("provenance")
    if prov not in PROVENANCES:
        raise BunkerPriceError(
            f"{hub}: provenance must be one of {PROVENANCES}, got {prov!r}", ["invalid_snapshot"])
    _parse_date(raw.get("observed_on"), f"{hub}.observed_on")
    src = raw.get("source")
    if not isinstance(src, str) or not src.strip():
        raise BunkerPriceError(f"{hub}: a price needs a named source", ["invalid_snapshot"])
    if is_reference and hub != REFERENCE_HUB:
        raise BunkerPriceError(f"the reference observation must use hub {REFERENCE_HUB!r}", ["invalid_snapshot"])
    return PriceObservation(
        hub=hub.strip(), price_usd_per_t=float(price), observed_on=str(raw["observed_on"]),
        provenance=prov, source=src, source_url=str(raw.get("source_url", "") or ""),
        note=str(raw.get("note", "") or ""),
        bunkering_location=str(raw.get("bunkering_location", "") or ""))


def load_snapshot(
    source: Union[str, Path, Mapping[str, Any]],
    *,
    expected_grade: Optional[str] = None,
) -> BunkerPriceSnapshot:
    """Read and validate a snapshot; raise ``BunkerPriceError`` with reasons."""
    if isinstance(source, Mapping):
        data = dict(source)
    else:
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BunkerPriceError(f"cannot read price snapshot {source!s}: {exc}", ["invalid_snapshot"]) from None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise BunkerPriceError(
            f"price snapshot needs schema_version {SCHEMA_VERSION}, got "
            f"{data.get('schema_version') if isinstance(data, dict) else type(data).__name__!r}",
            ["invalid_snapshot"])
    sid = data.get("snapshot_id")
    if not isinstance(sid, str) or not sid.strip():
        raise BunkerPriceError("snapshot_id is required", ["invalid_snapshot"])
    grade = data.get("fuel_grade")
    if not isinstance(grade, str) or not grade.strip():
        raise BunkerPriceError("fuel_grade is required", ["invalid_snapshot"])
    if expected_grade is not None and grade.strip().upper() != expected_grade.strip().upper():
        raise BunkerPriceError(
            f"snapshot {sid!r} prices grade {grade!r} but {expected_grade!r} was requested; "
            f"grades are not interchangeable (VLSFO, HSFO and MGO trade at different prices)",
            ["grade_mismatch"])
    currency = data.get("currency")
    if currency != CANONICAL_CURRENCY:
        raise BunkerPriceError(
            f"snapshot {sid!r} is in {currency!r}; only USD is supported "
            f"(no exchange rate is invented)", ["unsupported_currency"])
    unit = _canonical_unit(data.get("unit"))
    as_of = _parse_date(data.get("as_of"), "as_of")
    max_age = data.get("max_age_days")
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 0:
        raise BunkerPriceError("max_age_days must be an integer >= 0", ["invalid_snapshot"])

    obs_raw = data.get("observations")
    if not isinstance(obs_raw, list):
        raise BunkerPriceError("observations must be a list", ["invalid_snapshot"])
    observations = tuple(_parse_observation(o) for o in obs_raw)
    hubs = [o.hub for o in observations]
    if len(set(hubs)) != len(hubs):
        raise BunkerPriceError(f"duplicate observation for hub(s): {sorted({h for h in hubs if hubs.count(h) > 1})}",
                               ["invalid_snapshot"])
    reference = _parse_observation(data["reference"], is_reference=True) if data.get("reference") else None
    if not observations and reference is None:
        raise BunkerPriceError("a snapshot needs at least one observation or a reference", ["invalid_snapshot"])

    # internal freshness: nothing older than max_age_days relative to the compile date
    for o in list(observations) + ([reference] if reference else []):
        age = (as_of - _parse_date(o.observed_on, f"{o.hub}.observed_on")).days
        if age > max_age:
            raise BunkerPriceError(
                f"{o.hub}: observation of {o.observed_on} is {age} d older than the snapshot "
                f"as_of {as_of} (max_age_days={max_age})", ["stale_price"])
        if age < 0:
            raise BunkerPriceError(
                f"{o.hub}: observation date {o.observed_on} is after the snapshot as_of {as_of}",
                ["invalid_snapshot"])

    canon = json.dumps(
        {"schema_version": SCHEMA_VERSION, "snapshot_id": sid, "fuel_grade": grade.strip().upper(),
         "currency": currency, "unit": unit, "as_of": as_of.isoformat(), "max_age_days": max_age,
         "observations": [o.to_dict() for o in sorted(observations, key=lambda x: x.hub)],
         "reference": reference.to_dict() if reference else None},
        sort_keys=True, separators=(",", ":"))
    return BunkerPriceSnapshot(
        snapshot_id=sid, fuel_grade=grade.strip().upper(), as_of=as_of.isoformat(),
        max_age_days=max_age, observations=observations, reference=reference,
        sha256=hashlib.sha256(canon.encode("utf-8")).hexdigest(), currency=currency, unit=unit,
        description=str(data.get("description", "") or ""),
        licence_note=str(data.get("licence_note", "") or ""))


# ----------------------------------------------------------------------------------
# pricing policy
# ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class FuelPricing:
    mode: str = MODE_LEGACY
    uniform_usd_per_t: Optional[float] = None
    snapshot: Optional[BunkerPriceSnapshot] = None
    location_rule: str = RULE_CHEAPEST_OBSERVED
    fallback: str = FALLBACK_REFERENCE
    valuation_date: Optional[str] = None

    # ---- constructors -------------------------------------------------------------
    @classmethod
    def legacy_uniform(cls, usd_per_t: float = LEGACY_UNIFORM_USD_PER_T) -> "FuelPricing":
        if isinstance(usd_per_t, bool) or not isinstance(usd_per_t, (int, float)) \
                or not math.isfinite(usd_per_t) or usd_per_t < 0:
            raise BunkerPriceError(f"uniform price must be a finite number >= 0, got {usd_per_t!r}",
                                   ["invalid_price"])
        return cls(mode=MODE_LEGACY, uniform_usd_per_t=float(usd_per_t))

    @classmethod
    def from_snapshot(
        cls,
        snapshot: BunkerPriceSnapshot,
        *,
        location_rule: str = RULE_CHEAPEST_OBSERVED,
        fallback: str = FALLBACK_REFERENCE,
        valuation_date: Optional[str] = None,
        allow_stale: bool = False,
    ) -> "FuelPricing":
        if location_rule not in LOCATION_RULES:
            raise BunkerPriceError(f"unknown location rule {location_rule!r}; use one of {LOCATION_RULES}",
                                   ["unknown_location_rule"])
        if fallback not in FALLBACKS:
            raise BunkerPriceError(f"unknown fallback {fallback!r}; use one of {FALLBACKS}",
                                   ["unknown_fallback"])
        if location_rule == RULE_REFERENCE_ONLY and snapshot.reference is None:
            raise BunkerPriceError(
                f"snapshot {snapshot.snapshot_id!r} has no global reference price, which the "
                f"{RULE_REFERENCE_ONLY!r} rule needs", ["missing_reference_price"])
        val = valuation_date or snapshot.as_of
        age = (_parse_date(val, "valuation_date") - _parse_date(snapshot.as_of, "as_of")).days
        if age > snapshot.max_age_days and not allow_stale:
            raise BunkerPriceError(
                f"snapshot {snapshot.snapshot_id!r} (as_of {snapshot.as_of}) is {age} d older than "
                f"the valuation date {val}; max_age_days={snapshot.max_age_days}. Refresh the "
                f"snapshot or pass allow_stale explicitly", ["stale_price"])
        return cls(mode=MODE_SNAPSHOT, snapshot=snapshot, location_rule=location_rule,
                   fallback=fallback, valuation_date=val)

    # ---- resolution -----------------------------------------------------------------
    @property
    def snapshot_id(self) -> str:
        if self.mode == MODE_LEGACY:
            return f"legacy_uniform_{self.uniform_usd_per_t:g}"
        return self.snapshot.snapshot_id  # type: ignore[union-attr]

    @property
    def reference_price_usd_per_t(self) -> Optional[float]:
        """The single price that stands in for 'a' price in scalar-only displays."""
        if self.mode == MODE_LEGACY:
            return self.uniform_usd_per_t
        ref = self.snapshot.reference if self.snapshot else None  # type: ignore[union-attr]
        return ref.price_usd_per_t if ref else None

    def resolve(self, rotation_ports: Sequence[str]) -> FuelPriceResolution:
        if self.mode == MODE_LEGACY:
            return FuelPriceResolution(
                price_usd_per_t=float(self.uniform_usd_per_t), basis=BASIS_LEGACY, bunkering_port=None,
                observed_on=None, provenance="assumed", snapshot_id=self.snapshot_id)
        snap = self.snapshot
        assert snap is not None
        ports = sorted(set(str(p) for p in rotation_ports))
        on_rotation: List[Tuple[str, float]] = []
        if self.location_rule == RULE_CHEAPEST_OBSERVED:
            for p in ports:
                o = snap.observation_for(p)
                if o is not None:
                    on_rotation.append((p, o.price_usd_per_t))
        if on_rotation:
            hub, _ = min(on_rotation, key=lambda t: (t[1], t[0]))
            o = snap.observation_for(hub)
            assert o is not None
            return FuelPriceResolution(
                price_usd_per_t=o.price_usd_per_t, basis=BASIS_OBSERVED_PORT, bunkering_port=hub,
                observed_on=o.observed_on, provenance=o.provenance, snapshot_id=snap.snapshot_id,
                observed_ports_on_rotation=tuple(on_rotation))
        # no observed bunkering port on the rotation (or reference_only)
        if self.location_rule == RULE_CHEAPEST_OBSERVED and self.fallback == FALLBACK_ERROR:
            raise BunkerPriceError(
                f"no observed bunkering port on rotation {list(rotation_ports)} in snapshot "
                f"{snap.snapshot_id!r} and fallback is 'error'", ["no_observed_bunkering_port"])
        if snap.reference is None:
            raise BunkerPriceError(
                f"no observed bunkering port on rotation {list(rotation_ports)} and snapshot "
                f"{snap.snapshot_id!r} has no global reference price", ["no_observed_bunkering_port",
                                                                      "missing_reference_price"])
        r = snap.reference
        return FuelPriceResolution(
            price_usd_per_t=r.price_usd_per_t, basis=BASIS_REFERENCE, bunkering_port=None,
            observed_on=r.observed_on, provenance=r.provenance, snapshot_id=snap.snapshot_id)

    # ---- reporting ------------------------------------------------------------------
    def describe(self) -> Dict[str, Any]:
        if self.mode == MODE_LEGACY:
            return {
                "mode": MODE_LEGACY, "snapshot_id": self.snapshot_id,
                "uniform_price_usd_per_t": self.uniform_usd_per_t, "unit": CANONICAL_UNIT,
                "currency": CANONICAL_CURRENCY, "provenance": "assumed", "source": LEGACY_SOURCE,
                "note": ("one price for every service; benchmark-era assumption, not a regional "
                         "market observation"),
            }
        s = self.snapshot
        assert s is not None
        return {
            "mode": MODE_SNAPSHOT, "snapshot_id": s.snapshot_id, "sha256": s.sha256,
            "fuel_grade": s.fuel_grade, "currency": s.currency, "unit": s.unit,
            "as_of": s.as_of, "max_age_days": s.max_age_days,
            "valuation_date": self.valuation_date, "location_rule": self.location_rule,
            "fallback": self.fallback,
            "location_assumption": (
                "all fuel of a service is bought at the cheapest OBSERVED bunkering port on its "
                "rotation (optimistic bound); a rotation without an observed port is priced at the "
                "snapshot's global reference" if self.location_rule == RULE_CHEAPEST_OBSERVED else
                "every service is priced at the snapshot's global reference"),
            "observations": [o.to_dict() for o in s.observations],
            "reference": s.reference.to_dict() if s.reference else None,
            "description": s.description, "licence_note": s.licence_note,
        }


# ----------------------------------------------------------------------------------
# process-wide configuration (environment), overridable in code
# ----------------------------------------------------------------------------------
_OVERRIDE: List[Optional[FuelPricing]] = []          # stack; empty => use the environment
_ENV_CACHE: Dict[Tuple, FuelPricing] = {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def pricing_from_environment(env: Optional[Mapping[str, str]] = None) -> Optional[FuelPricing]:
    """Pricing requested by the environment, or ``None`` for the legacy default.

    BUNKER_PRICING_MODE      legacy_uniform (default) | regional_snapshot
    BUNKER_UNIFORM_USD_PER_T legacy price (default 600)
    BUNKER_PRICE_SNAPSHOT    path of the snapshot JSON (required for regional_snapshot)
    BUNKER_FUEL_GRADE        grade the snapshot must price (default VLSFO)
    BUNKER_LOCATION_RULE     cheapest_observed_port_on_rotation | reference_only
    BUNKER_FALLBACK          reference | error
    BUNKER_VALUATION_DATE    ISO date (default: the snapshot's as_of)
    A mis-configured regional request raises ``BunkerPriceError``; it never
    degrades to the legacy price.
    """
    e = os.environ if env is None else env
    mode = (e.get("BUNKER_PRICING_MODE") or MODE_LEGACY).strip().lower()
    if mode == MODE_LEGACY:
        raw = e.get("BUNKER_UNIFORM_USD_PER_T")
        if raw in (None, ""):
            return None
        try:
            return FuelPricing.legacy_uniform(float(raw))
        except ValueError:
            raise BunkerPriceError(f"BUNKER_UNIFORM_USD_PER_T is not a number: {raw!r}",
                                   ["invalid_price"]) from None
    if mode != MODE_SNAPSHOT:
        raise BunkerPriceError(
            f"BUNKER_PRICING_MODE must be {MODE_LEGACY!r} or {MODE_SNAPSHOT!r}, got {mode!r}",
            ["unknown_mode"])
    path = e.get("BUNKER_PRICE_SNAPSHOT")
    if not path:
        raise BunkerPriceError(
            f"BUNKER_PRICING_MODE={MODE_SNAPSHOT} needs BUNKER_PRICE_SNAPSHOT (a path); no "
            f"default price is substituted", ["missing_snapshot"])
    p = Path(path)
    if not p.is_absolute():
        p = _project_root() / p
    grade = (e.get("BUNKER_FUEL_GRADE") or "VLSFO").strip()
    key = (str(p), grade, e.get("BUNKER_LOCATION_RULE"), e.get("BUNKER_FALLBACK"),
           e.get("BUNKER_VALUATION_DATE"), p.stat().st_mtime_ns if p.exists() else None)
    if key in _ENV_CACHE:
        return _ENV_CACHE[key]
    snap = load_snapshot(p, expected_grade=grade)
    pricing = FuelPricing.from_snapshot(
        snap, location_rule=e.get("BUNKER_LOCATION_RULE") or RULE_CHEAPEST_OBSERVED,
        fallback=e.get("BUNKER_FALLBACK") or FALLBACK_REFERENCE,
        valuation_date=e.get("BUNKER_VALUATION_DATE") or None)
    _ENV_CACHE[key] = pricing
    return pricing


def active_pricing() -> Optional[FuelPricing]:
    """The pricing the pipeline should use now; ``None`` = legacy default (600 USD/t)."""
    if _OVERRIDE:
        return _OVERRIDE[-1]
    return pricing_from_environment()


@contextlib.contextmanager
def use_pricing(pricing: Optional[FuelPricing]) -> Iterator[None]:
    """Temporarily force the active pricing (tests, controlled comparisons)."""
    _OVERRIDE.append(pricing)
    try:
        yield
    finally:
        _OVERRIDE.pop()
