"""Bidirectional requirement-to-test traceability validator.

Checks, for Chunk 0's requirement set:

* every LREQ referenced by ``tests/traceability.json`` exists in the SRS
  definition list (Appendix B wildcard prefixes);
* every Chunk 0 requirement from the dependency map has at least one mapped
  test;
* every analytical test carrying an ``@pytest.mark.lreq`` marker has a matrix
  entry whose LREQ list matches the marker exactly;
* no matrix entry references a pytest node ID that does not exist.

Chunk 0 intentionally checks its own seven requirements only; later chunks widen
the required set as their requirements become testable.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRS_PATH = ROOT / "Documents" / "SRS-lean.md"
DEPENDENCY_MAP_PATH = ROOT / "Documents" / "requirements-dependency-map.md"
TESTS_DIR = ROOT / "tests"
TRACEABILITY_PATH = TESTS_DIR / "traceability.json"

LREQ_PATTERN = re.compile(r"\bLREQ-[A-Z]+-\d{3}\b")
WILDCARD_PATTERN = re.compile(r"`(LREQ-[A-Z]+)-\*`")
#: SRS Appendix B rows list several areas in one cell (e.g. ``LREQ-NRM-*``,
#: ``LREQ-SCR-*``), so the backtick form is not always ``<prefix>-*``.
WILDCARD_GROUP_PATTERN = re.compile(r"`(LREQ-[A-Z]+)`")
LREQ_MARKER = "pytest.mark.lreq"


def individual_ids(text: str) -> set[str]:
    """Return every individually written LREQ ID found in ``text``."""
    return set(LREQ_PATTERN.findall(text))


def defined_ids(text: str) -> set[str]:
    """Return the LREQ IDs the SRS actually defines.

    Appendix B declares exhaustive ID ranges as wildcard prefixes; an ID is
    defined only when it belongs to one of those declared ranges.
    """
    if "## Appendix B" not in text:
        raise ValueError("SRS-lean.md is missing Appendix B (traceability matrix)")
    appendix = text.split("## Appendix B", 1)[1]
    prefixes = {match.group(1) for match in WILDCARD_PATTERN.finditer(appendix)}
    # A cell may group several areas, e.g. "| `LREQ-NRM-*`, `LREQ-SCR-*` |":
    # the first prefix is caught above, the rest by the bare backtick form.
    prefixes |= {
        match.group(1)
        for match in WILDCARD_GROUP_PATTERN.finditer(appendix)
        if match.group(1).startswith("LREQ-")
    }
    return {item for item in individual_ids(text) if item.rsplit("-", 1)[0] in prefixes}


def chunk_requirements(text: str, chunk: str = "0") -> set[str]:
    """Return the requirement IDs listed for ``chunk`` in the dependency map."""
    header = f"## Chunk {chunk} "
    if header not in text:
        raise ValueError(
            f"requirements-dependency-map.md has no '{header.strip()}' section"
        )
    section = text.split(header, 1)[1]
    next_header = f"\n## Chunk {int(chunk) + 1} "
    if next_header in section:
        section = section.split(next_header, 1)[0]
    else:
        section = section.split("\n---", 1)[0]
    if "Requirements primarily covered:" not in section:
        raise ValueError(
            f"Chunk {chunk} section has no 'Requirements primarily covered:' block"
        )
    block = section.split("Requirements primarily covered:", 1)[1]
    block = block.split("Gate:", 1)[0]
    return individual_ids(block)


def test_markers(path: Path) -> dict[str, set[str]]:
    """Map pytest node ID -> declared LREQ marker set for one test module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    marked: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        requirements: set[str] = set()
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if ast.unparse(decorator.func) != LREQ_MARKER:
                continue
            if (
                len(decorator.args) == 1
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                requirements.add(decorator.args[0].value)
        marked[f"tests/{path.name}::{node.name}"] = requirements
    return marked


def collect_tests() -> dict[str, set[str]]:
    """Collect marked and unmarked test node IDs across the test suite."""
    tests: dict[str, set[str]] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tests.update(test_markers(path))
    return tests


def load_matrix(path: Path = TRACEABILITY_PATH) -> dict[str, list[str]]:
    """Load the machine-readable test-to-requirement matrix."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("traceability.json must contain a JSON object")
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, list):
            raise ValueError(
                "traceability.json must map node ID strings to arrays of LREQ IDs"
            )
        if any(not isinstance(item, str) for item in value):
            raise ValueError(
                f"traceability.json entry '{key}' must map to strings only"
            )
    return payload


def main(argv: list[str] | None = None) -> int:
    """Validate traceability in both directions; return a process exit code."""
    _ = argv
    srs_text = SRS_PATH.read_text(encoding="utf-8")
    defined = defined_ids(srs_text)
    required = chunk_requirements(DEPENDENCY_MAP_PATH.read_text(encoding="utf-8"))

    try:
        matrix = load_matrix()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Unable to read traceability matrix: {exc}")
        return 1

    tests = collect_tests()
    referenced = {req for values in matrix.values() for req in values}

    unknown = sorted(referenced - defined)
    missing_required = sorted(required - referenced)
    missing_nodes = sorted(
        node for node, markers in tests.items() if markers and node not in matrix
    )
    marker_mismatch = sorted(
        node
        for node, markers in tests.items()
        if markers and set(matrix.get(node, ())) != markers
    )
    orphan_nodes = sorted(node for node in matrix if node not in tests)
    unmarked_tests = sorted(node for node, markers in tests.items() if not markers)

    problems = bool(
        unknown or missing_required or missing_nodes or marker_mismatch or orphan_nodes
    )
    if unknown:
        print(f"Unknown or retired requirement IDs: {', '.join(unknown)}")
    if missing_required:
        print(
            f"Chunk 0 requirements without mapped tests: {', '.join(missing_required)}"
        )
    if missing_nodes:
        print(
            f"Tests with lreq markers but no matrix entry: {', '.join(missing_nodes)}"
        )
    if marker_mismatch:
        print(f"Marker/matrix LREQ mismatch: {', '.join(marker_mismatch)}")
    if orphan_nodes:
        print(f"Matrix entries not found in the test suite: {', '.join(orphan_nodes)}")
    if problems:
        return 1

    if unmarked_tests:
        print(
            f"Note: {len(unmarked_tests)} test(s) carry no lreq marker: {', '.join(unmarked_tests)}"
        )
    print(
        f"Traceability valid: {len(required)} Chunk 0 requirements mapped, "
        f"{len(matrix)} matrix nodes, {len(defined)} defined LREQ IDs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
