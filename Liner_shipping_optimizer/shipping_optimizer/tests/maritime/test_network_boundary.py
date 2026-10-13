"""Network-boundary tests: the optimizer must never import maritime network
code, and the maritime package must not leak network imports into
optimization/pipeline/validation/services/decomposition/data.
"""

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MARITIME_ROOT = REPO_ROOT / "maritime"
SRC_ROOT = REPO_ROOT / "src"

NETWORK_ROOTS = {"requests", "urllib", "httpx", "aiohttp", "websockets", "socket", "ftplib", "smtplib"}


def _imports_in(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


def _imported_modules(path: Path) -> set:
    """Return the set of full module names that the file imports (top-level
    names and dotted names)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_optimizer_modules_have_no_maritime_imports():
    offenders = []
    for path in SRC_ROOT.rglob("*.py"):
        mods = _imported_modules(path)
        if any(m == "maritime" or m.startswith("maritime.") for m in mods):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"optimizer modules import maritime: {offenders}"


def test_core_optimizer_dirs_have_no_maritime_imports():
    targets = ["optimization", "pipeline", "validation", "services", "decomposition", "data"]
    offenders = []
    for d in targets:
        p = SRC_ROOT / d
        if not p.is_dir():
            continue
        for path in p.rglob("*.py"):
            mods = _imported_modules(path)
            if any(m == "maritime" or m.startswith("maritime.") for m in mods):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"core optimizer dirs import maritime: {offenders}"


def test_maritime_ingestion_uses_only_stdlib_urllib():
    """The ingestion + live layer is the only place where network is allowed."""
    allowed_packages = [MARITIME_ROOT / "ingestion", MARITIME_ROOT / "live"]
    for pkg in allowed_packages:
        if not pkg.is_dir():
            continue
        for path in pkg.rglob("*.py"):
            roots = _imports_in(path)
            for r in roots:
                if r in {"urllib", "urllib.request", "urllib.error", "urllib.error", "socket"}:
                    # urllib and socket are stdlib and permitted in the ingestion layer.
                    continue
                if r in NETWORK_ROOTS:
                    pytest.fail(f"maritime network layer imports non-stdlib network: {r} in {path}")


def test_maritime_non_ingestion_modules_have_no_network_imports():
    """Modules outside maritime/ingestion (and maritime/live) must NOT make network calls.

    Phase 4 added the ``maritime.live`` package as a SECOND permitted
    network boundary (alongside ``maritime.ingestion``). It is the
    only place where live HTTP / MQTT access for external maritime
    sources is allowed. Everything else (schemas, storage, intelligence,
    quality, normalization, feature adapters) must remain network-free.
    """
    for path in MARITIME_ROOT.rglob("*.py"):
        if "ingestion" in path.parts:
            continue
        if "live" in path.parts:
            continue
        roots = _imports_in(path)
        for r in roots:
            assert r not in NETWORK_ROOTS, (
                f"non-ingestion maritime module {path} imports {r}"
            )


def test_feature_adapter_does_not_import_network():
    fa = MARITIME_ROOT / "feature_adapter.py"
    if not fa.exists():
        pytest.skip("feature_adapter.py missing")
    roots = _imports_in(fa)
    for r in roots:
        assert r not in NETWORK_ROOTS, f"feature_adapter.py imports {r}"


def test_maritime_does_not_import_optimizer():
    """The maritime layer must not import anything from src/."""
    for path in MARITIME_ROOT.rglob("*.py"):
        mods = _imported_modules(path)
        bad = {m for m in mods if m == "src" or m.startswith("src.")}
        assert not bad, f"maritime module {path} imports from src/: {bad}"
