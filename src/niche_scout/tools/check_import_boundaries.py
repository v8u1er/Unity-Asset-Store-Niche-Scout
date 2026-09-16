"""AST import-boundary checker for the pure analytical modules.

The purity boundary from SRS-lean §3.3 is enforced structurally rather than by
convention: ``metrics.py`` and ``scoring.py`` may import typed structures from
``models.py`` and pure standard-library helpers, but never I/O, network,
database, CLI, process, or clock modules.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "niche_scout"
PURE_MODULES: tuple[str, ...] = ("metrics.py", "scoring.py")

# Top-level module names that must never be imported by a pure module.
FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        # I/O and orchestration modules of this package.
        "collector",
        "collector_coveo",
        "collector_graphql",
        "database",
        "pipeline",
        "report",
        "cli",
        "config",
        # Filesystem, process, and network standard library.
        "os",
        "io",
        "sys",
        "pathlib",
        "shutil",
        "tempfile",
        "subprocess",
        "socket",
        "sqlite3",
        "sqlite",
        "requests",
        "urllib",
        "urllib3",
        "http",
        "httpx",
        "aiohttp",
        "json",
        "csv",
        "pickle",
        # Logging and time sources.
        "time",
        "logging",
        "platform",
    }
)

# Both the module name and the imported symbol are checked so that
# ``from datetime import datetime`` is allowed while clock reads are caught
# separately by :func:`clock_violations`.
FORBIDDEN_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "now",
        "utcnow",
        "today",
        "time",
        "time_ns",
        "monotonic",
        "perf_counter",
        "localtime",
        "gmtime",
        "sleep",
    }
)

ALLOWED_CLOCK_OWNERS: frozenset[str] = frozenset({"datetime", "date", "time", "dt"})


def imported_module_names(tree: ast.AST) -> set[str]:
    """Return every top-level and relative module name imported by ``tree``.

    ``from .models import RunRecord`` contributes ``models``; ``import os.path``
    contributes ``os``. The checker compares first path segments because that is
    where the boundary actually lives.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.module is None:
                names.update(alias.name.split(".")[0] for alias in node.names)
                continue
            if node.module:
                names.add(node.module.split(".")[-1])
    return names


def clock_violations(tree: ast.AST) -> list[str]:
    """Return clock-reading attribute accesses such as ``datetime.now()``."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in FORBIDDEN_ATTRIBUTES:
            continue
        owner = node.value
        if isinstance(owner, ast.Name) and owner.id in ALLOWED_CLOCK_OWNERS:
            violations.append(f"{ast.unparse(node)}")
        elif isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name):
            if owner.value.id in ALLOWED_CLOCK_OWNERS:
                violations.append(f"{ast.unparse(node)}")
    return sorted(set(violations))


def check_module(path: Path) -> list[str]:
    """Return violation messages for a single pure module file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = [
        f"{path.name}: forbidden import '{name}'"
        for name in sorted(imported_module_names(tree) & FORBIDDEN_MODULES)
    ]
    violations.extend(
        f"{path.name}: forbidden clock read '{item}'" for item in clock_violations(tree)
    )
    return violations


def main(argv: list[str] | None = None) -> int:
    """Validate the purity boundary; return a process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    package = Path(args[0]) if args else PACKAGE

    violations: list[str] = []
    checked: list[str] = []
    for filename in PURE_MODULES:
        path = package / filename
        if not path.is_file():
            violations.append(f"{filename}: missing pure module")
            continue
        checked.append(filename)
        violations.extend(check_module(path))

    if violations:
        print("Import boundary violations found:")
        print("\n".join(violations))
        return 1
    print(f"Import boundaries valid for {', '.join(checked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
