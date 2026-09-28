"""Bidirectional requirement-to-test traceability validator.

Checks, against the full SRS-defined requirement set:

* every ``LREQ-*`` referenced by ``tests/traceability.json`` exists in the SRS
  definition list (Appendix B wildcard prefixes);
* every individually defined ``LREQ-*`` is referenced by at least one mapped
  test (the required set is the whole SRS set, not one chunk's subset);
* every analytical test carrying an ``@pytest.mark.lreq`` marker has a matrix
  entry whose LREQ list matches the marker set exactly;
* no matrix entry references a pytest node ID that does not exist;
* every analytical test carries at least one marker, except the exact
  non-analytical node IDs in :data:`NON_ANALYTICAL_EXEMPT`.

The exemption is a deliberate, exact ``frozenset`` of three module-contract
tests that assert import safety or a builder signature and exercise no
requirement behaviour; every other unmarked test makes :func:`main` return 1.

Chunk 0 originally checked its own seven requirements only. Chunk 13 widens the
required set to ``defined_ids(srs_text)`` (all 89 individual IDs) and fixes the
marker parser to read every argument of ``@pytest.mark.lreq(...)``.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRS_PATH = ROOT / "Documents" / "SRS-lean-v2.md"
DEPENDENCY_MAP_PATH = ROOT / "Documents" / "requirements-dependency-map.md"
TESTS_DIR = ROOT / "tests"
TRACEABILITY_PATH = TESTS_DIR / "traceability.json"

LREQ_PATTERN = re.compile(r"\bLREQ-[A-Z]+-\d{3}\b")
WILDCARD_PATTERN = re.compile(r"`(LREQ-[A-Z]+)-\*`")
LREQ_MARKER = "pytest.mark.lreq"

#: The exact node IDs that are deliberately allowed to carry no
#: ``@pytest.mark.lreq`` marker because they exercise a module contract, not an
#: ``LREQ-*`` behaviour: the two ``collector.py`` contract tests and the
#: ``sampling.py`` import-purity gate. R2c/R6 fixes this set at exactly three
#: IDs; any other unmarked test fails the validator.
NON_ANALYTICAL_EXEMPT: frozenset[str] = frozenset(
    {
        "tests/test_collector.py::test_module_imports_without_side_effects",
        "tests/test_collector.py::test_request_body_builder_signature_is_stable",
        "tests/test_sampling.py::test_sampling_module_imports_are_pure",
    }
)


def individual_ids(text: str) -> set[str]:
    """Return every individually written LREQ ID found in ``text``."""
    return set(LREQ_PATTERN.findall(text))


def defined_ids(text: str) -> set[str]:
    """Return the LREQ IDs the SRS actually defines.

    Appendix B declares exhaustive ID ranges as wildcard prefixes; an ID is
    defined only when it belongs to one of those declared ranges.
    """
    if "## Appendix B" not in text:
        raise ValueError("SRS-lean-v2.md is missing Appendix B (traceability matrix)")
    appendix = text.split("## Appendix B", 1)[1]
    prefixes = {match.group(1) for match in WILDCARD_PATTERN.finditer(appendix)}
    return {item for item in individual_ids(text) if item.rsplit("-", 1)[0] in prefixes}


def required_ids(srs_text: str) -> set[str]:
    """Return every individually defined LREQ ID the SRS declares.

    Supersedes :func:`chunk_requirements` for the widened check: the validator
    no longer restricts the required set to one chunk, so every defined
    requirement must be referenced by at least one mapped test.
    """
    return defined_ids(srs_text)


def chunk_requirements(text: str, chunk: str = "0") -> set[str]:
    """Return the requirement IDs listed for ``chunk`` in the dependency map.

    Retained as a public helper for dependency-map inspection; the widened
    validator uses :func:`required_ids` instead.
    """
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
    """Map pytest node ID -> declared LREQ marker set for one test module.

    Parses EVERY string argument of every ``@pytest.mark.lreq(...)`` call, so
    ``@pytest.mark.lreq("A", "B")`` contributes both ``A`` and ``B``. The
    single-argument parser this replaces silently misclassified 99 multi-argument
    markers as unmarked.
    """
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
            for argument in decorator.args:
                if isinstance(argument, ast.Constant) and isinstance(
                    argument.value, str
                ):
                    requirements.add(argument.value)
        marked[f"tests/{path.name}::{node.name}"] = requirements
    return marked


def collect_tests() -> dict[str, set[str]]:
    """Collect marked and unmarked test node IDs across the test suite."""
    tests: dict[str, set[str]] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tests.update(test_markers(path))
    return tests


def unmarked_analytical_tests(
    tests: Mapping[str, set[str]],
    *,
    exempt: frozenset[str] = NON_ANALYTICAL_EXEMPT,
) -> list[str]:
    """Node IDs of test functions with no marker and no exact exemption.

    A non-empty result makes :func:`main` return 1.
    """
    return sorted(
        node for node, markers in tests.items() if not markers and node not in exempt
    )


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
    """Validate traceability in both directions; return a process exit code.

    Fails (exit 1) on an unknown/retired referenced ID, a required ID with no
    mapped test, a marked test with no matrix entry, a marker/matrix mismatch, an
    orphan matrix node, or an unmarked analytical test outside
    :data:`NON_ANALYTICAL_EXEMPT`.
    """
    _ = argv
    srs_text = SRS_PATH.read_text(encoding="utf-8")
    defined = defined_ids(srs_text)
    required = required_ids(srs_text)

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
    unmarked = unmarked_analytical_tests(tests)
    exempt_unmarked = sorted(
        node
        for node, markers in tests.items()
        if not markers and node in NON_ANALYTICAL_EXEMPT
    )

    problems = bool(
        unknown
        or missing_required
        or missing_nodes
        or marker_mismatch
        or orphan_nodes
        or unmarked
    )
    if unknown:
        print(f"Unknown or retired requirement IDs: {', '.join(unknown)}")
    if missing_required:
        print(f"Requirements without mapped tests: {', '.join(missing_required)}")
    if missing_nodes:
        print(
            f"Tests with lreq markers but no matrix entry: {', '.join(missing_nodes)}"
        )
    if marker_mismatch:
        print(f"Marker/matrix LREQ mismatch: {', '.join(marker_mismatch)}")
    if orphan_nodes:
        print(f"Matrix entries not found in the test suite: {', '.join(orphan_nodes)}")
    if unmarked:
        print(
            "Unmarked analytical tests outside the exemption set: "
            f"{', '.join(unmarked)}"
        )
    if problems:
        return 1

    print(
        f"Traceability valid: {len(required)} required/defined LREQ IDs mapped, "
        f"{len(matrix)} matrix nodes, "
        f"{len(unmarked)} unmarked analytical tests outside exemption "
        f"({len(exempt_unmarked)} exempted non-analytical nodes)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
