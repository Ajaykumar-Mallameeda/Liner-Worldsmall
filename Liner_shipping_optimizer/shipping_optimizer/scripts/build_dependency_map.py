"""AST-derived file inventory and dependency map for the Multi-Agent repo.

Read-only with respect to src/, backend/, scripts/, tests/. Writes one JSON
artifact. Used by the Phase MA economic-metric integrity audit to produce
MULTI_AGENT_FILE_DEPENDENCY_MAP.json without inferring any dependency from
file or symbol names.
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["src", "backend", "scripts", "tests"]
SEP = chr(92)  # backslash, kept out of source to avoid escaping confusion


def module_name(p: Path, rel: str) -> str:
    """Dotted module name derived from the repo-relative path."""
    parts = Path(rel).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def scan():
    files = {}
    for s in SCAN_DIRS:
        base = ROOT / s
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(ROOT).as_posix()
            mod = module_name(p, rel)
            try:
                tree = ast.parse(text)
            except SyntaxError as e:
                files[rel] = {"module": mod, "lines": text.count("\n") + 1,
                              "parse_error": str(e), "imports": [], "classes": [],
                              "functions": []}
                continue
            imports, classes, funcs = [], [], []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imports.append({"module": a.name, "line": node.lineno,
                                        "kind": "import", "alias": a.asname})
                elif isinstance(node, ast.ImportFrom):
                    imported_mod = node.module or ""
                    if node.level:
                        imported_mod = "." * node.level + imported_mod
                    for a in node.names:
                        imports.append({"module": imported_mod, "name": a.name,
                                        "line": node.lineno, "kind": "from",
                                        "alias": a.asname})
                elif isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body
                               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    classes.append({"name": node.name, "line": node.lineno,
                                    "methods": methods})
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.append({"name": node.name, "line": node.lineno})
            files[rel] = {"module": mod, "lines": text.count("\n") + 1,
                          "imports": imports, "classes": classes, "functions": funcs}
    return files


def resolve_internal_edges(files):
    """Map each import to an in-repo target file, if one exists."""
    by_module = {}
    for rel, meta in files.items():
        by_module.setdefault(meta["module"], []).append(rel)

    def resolve(module, imported_name, importer_rel):
        """Resolve an import to a repo file.

        Absolute imports name a module path directly. Relative imports are
        anchored to the importer's package. `from pkg import name` is
        ambiguous: it is a package attribute unless `pkg.name` is itself a
        module, in which case the submodule is the real target.
        """
        if module.startswith("."):
            imp_mod = files[importer_rel]["module"]
            parts = imp_mod.split(".")
            # A package __init__ lives in its own package; a module lives in
            # its parent package.
            pkg = parts if importer_rel.endswith("/__init__.py") else parts[:-1]
            dots = len(module) - len(module.lstrip("."))
            if dots - 1 > len(pkg):
                return None
            base = pkg[: len(pkg) - (dots - 1)]
            target = ".".join(base + ([module.lstrip(".")] if module.lstrip(".") else []))
        else:
            target = module

        if target in by_module:
            return by_module[target][0]
        # `from pkg import mod` -> pkg.mod, when pkg.mod is a real module.
        if imported_name and f"{target}.{imported_name}" in by_module:
            return by_module[f"{target}.{imported_name}"][0]
        return None

    edges = []
    for rel, meta in files.items():
        for imp in meta["imports"]:
            tgt = resolve(imp["module"], imp.get("name"), rel)
            if tgt and tgt != rel:
                edges.append({
                    "source": rel,
                    "target": tgt,
                    "line": imp["line"],
                    "statement": imp["module"] + (("." + imp["name"]) if imp.get("name") else ""),
                    "kind": imp["kind"],
                })
    return edges


def main():
    files = scan()
    edges = resolve_internal_edges(files)
    out = {
        "generated_by": "scripts/build_dependency_map.py",
        "scan_dirs": SCAN_DIRS,
        "totals": {
            "files": len(files),
            "lines": sum(f["lines"] for f in files.values()),
            "classes": sum(len(f["classes"]) for f in files.values()),
            "functions": sum(len(f["functions"]) for f in files.values()),
            "import_statements": sum(len(f["imports"]) for f in files.values()),
            "internal_import_edges": len(edges),
        },
        "files": files,
        "edges": edges,
    }
    dest = ROOT / "MULTI_AGENT_FILE_DEPENDENCY_MAP.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["totals"], indent=1))
    print("wrote", dest.name)


if __name__ == "__main__":
    sys.exit(main())