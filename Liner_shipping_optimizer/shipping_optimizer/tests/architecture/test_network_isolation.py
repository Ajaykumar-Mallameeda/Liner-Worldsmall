"""Network-isolation architecture guard.

Hard architectural constraint (docs/architecture/INTEGRATION_BOUNDARIES.md):

    THE OPTIMIZER MUST NEVER PERFORM NETWORK INGESTION.

        EXTERNAL SOURCE -> INGESTION -> NORMALIZATION -> VALIDATION
            -> SNAPSHOT STORE -> FEATURE ADAPTER -> OPTIMIZER

The optimizer core therefore must not import network-capable libraries. The
sanctioned exception is the LLM provider layer (``src/llm/providers/``), which
is existing, tested behavior and is NOT a maritime data path.

Stdlib-only (ast + pathlib). No new dependencies — by design this test itself
must not violate the rule it enforces.
"""

import ast
from pathlib import Path

import pytest

# Repository root = parent of tests/
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

# Directories where outbound network access is sanctioned today.
NETWORK_SANCTIONED_DIRS = [
    SRC_ROOT / "llm" / "providers",
]

# Network-capable stdlib/third-party modules forbidden in optimizer code.
FORBIDDEN_ROOTS = {
    "requests",
    "urllib",
    "httpx",
    "aiohttp",
    "socket",
    "websockets",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
}
# Dotted names checked against the FULL imported module path as well.
FORBIDDEN_DOTTED = {
    "http.client",
}

ALLOWED_PARTIAL = {
    # urllib.parse / http constants sometimes appear transitively in non-network roles;
    # if a future legitimate need appears, add an explicit, justified allowlist entry here.
}


def _iter_optimizer_files():
    """Yield every .py file under src/ except the sanctioned provider layer."""
    for path in sorted(SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT)
        if any(path.is_relative_to(d) for d in NETWORK_SANCTIONED_DIRS):
            continue
        yield rel, path


def _imported_root_modules(tree):
    """Collect top-level import names + dotted names from an AST."""
    dotted = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dotted.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                dotted.add(node.module)
            elif node.level:  # relative import — not network relevant
                continue
    return dotted


def test_no_network_imports_in_optimizer_modules():
    """No optimizer module may import network-capable libraries."""
    forbidden_full = FORBIDDEN_DOTTED
    forbidden_roots = FORBIDDEN_ROOTS
    violations = []
    for rel, path in _iter_optimizer_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        for dotted in _imported_root_modules(tree):
            if dotted in forbidden_full:
                violations.append(f"{rel}: imports '{dotted}'")
                continue
            if dotted.split(".")[0] in forbidden_roots:
                violations.append(f"{rel}: imports '{dotted}'")
    assert not violations, (
        "Network-isolation violation in optimizer modules "
        "(see docs/architecture/INTEGRATION_BOUNDARIES.md):\n  " + "\n  ".join(violations)
    )


def test_no_http_sockets_constructed_outside_providers():
    """Belt-and-braces: no raw client construction outside the providers layer."""
    patterns = ("requests.", "urlopen(", "httpx.", "aiohttp.", "socket.socket")
    violations = []
    for rel, path in _iter_optimizer_files():
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            if pat in text:
                violations.append(f"{rel}: contains '{pat}'")
    assert not violations, (
        "Possible direct network usage outside the sanctioned provider layer:\n  "
        + "\n  ".join(violations)
    )


def test_no_maritime_ingestion_inside_optimizer_yet():
    """Maritime modules must not exist inside the optimizer import graph.

    Future maritime code lives OUTSIDE src/ (ingestion daemon + feature adapter
    per INTEGRATION_BOUNDARIES.md). If this test fails because someone added a
    maritime module under src/, that module needs an explicit boundary review
    and this guard updated deliberately — not silently.
    """
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in SRC_ROOT.rglob("*.py")
        if "maritime" in p.name.lower()
    ]
    assert not offenders, f"maritime modules inside optimizer source: {offenders}"


@pytest.mark.parametrize(
    "module_dir",
    ["optimization", "pipeline", "validation", "services", "decomposition", "data"],
)
def test_core_optimizer_dirs_have_zero_network_imports(module_dir):
    """Per-directory hard guarantee for the mathematical/decision core."""
    target = SRC_ROOT / module_dir
    assert target.is_dir(), f"expected core directory missing: {target}"
    for path in target.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for dotted in _imported_root_modules(tree):
            assert dotted not in FORBIDDEN_DOTTED, (
                f"{path.relative_to(REPO_ROOT)} imports network-capable '{dotted}'"
            )
            assert dotted.split(".")[0] not in FORBIDDEN_ROOTS, (
                f"{path.relative_to(REPO_ROOT)} imports network-capable '{dotted}'"
            )
