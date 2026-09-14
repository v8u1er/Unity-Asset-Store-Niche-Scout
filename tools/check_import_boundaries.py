"""Check that pure analytical modules do not import I/O modules."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "niche_scout"
PURE_MODULES = ("metrics.py", "scoring.py")
FORBIDDEN = {
    "collector",
    "collector_coveo",
    "collector_graphql",
    "database",
    "pipeline",
    "report",
    "cli",
}


def imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[-1])
    return names


def main() -> int:
    violations: list[str] = []
    for filename in PURE_MODULES:
        path = PACKAGE / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = imported_module_names(tree) & FORBIDDEN
        violations.extend(f"{filename}: {name}" for name in sorted(forbidden))
    if violations:
        print("Forbidden imports found:")
        print("\n".join(violations))
        return 1
    print("Import boundaries valid for metrics.py and scoring.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
