"""Validate bidirectional requirement-to-test traceability for Chunk 0."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRS_PATH = ROOT / "Documents" / "SRS-lean.md"
DEPENDENCY_MAP_PATH = ROOT / "Documents" / "requirements-dependency-map.md"
TRACEABILITY_PATH = ROOT / "tests" / "traceability.json"
LREQ_PATTERN = re.compile(r"\bLREQ-[A-Z]+-\d{3}\b")
WILDCARD_PATTERN = re.compile(r"`(LREQ-[A-Z]+)-\*`")


def individual_ids(text: str) -> set[str]:
    return set(LREQ_PATTERN.findall(text))


def defined_ids(text: str) -> set[str]:
    appendix = text.split("## Appendix B", 1)[1]
    prefixes = {match.group(1) for match in WILDCARD_PATTERN.finditer(appendix)}
    return {item for item in individual_ids(text) if item.rsplit("-", 1)[0] in prefixes}


def chunk_zero_requirements(text: str) -> set[str]:
    section = text.split("## Chunk 0", 1)[1].split("## Chunk 1", 1)[0]
    requirements = section.split("Requirements primarily covered:", 1)[1].split("Gate:", 1)[0]
    return individual_ids(requirements)


def test_markers(path: Path) -> dict[str, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    marked: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
            continue
        requirements: set[str] = set()
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or ast.unparse(decorator.func) != "pytest.mark.lreq":
                continue
            if len(decorator.args) == 1 and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                requirements.add(decorator.args[0].value)
        marked[f"tests/{path.name}::{node.name}"] = requirements
    return marked


def main() -> int:
    srs_text = SRS_PATH.read_text(encoding="utf-8")
    defined = defined_ids(srs_text)
    required = chunk_zero_requirements(DEPENDENCY_MAP_PATH.read_text(encoding="utf-8"))
    try:
        matrix = json.loads(TRACEABILITY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read traceability JSON: {exc}")
        return 1
    if not isinstance(matrix, dict) or any(not isinstance(key, str) or not isinstance(value, list) for key, value in matrix.items()):
        print("Traceability must map test node IDs to arrays of LREQ IDs")
        return 1
    referenced = {req for values in matrix.values() for req in values if isinstance(req, str)}
    unknown = sorted(referenced - defined)
    missing_required = sorted(required - referenced)
    tests = {}
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tests.update(test_markers(path))
    missing_nodes = sorted(node for node in tests if tests[node] and node not in matrix)
    marker_mismatch = sorted(
        node for node, markers in tests.items() if markers and set(matrix.get(node, ())) != markers
    )
    invalid_nodes = sorted(node for node in matrix if node not in tests)
    if unknown or missing_required or missing_nodes or marker_mismatch or invalid_nodes:
        if unknown:
            print(f"Unknown requirement IDs: {', '.join(unknown)}")
        if missing_required:
            print(f"Chunk 0 requirements without mapped tests: {', '.join(missing_required)}")
        if missing_nodes:
            print(f"Tests with markers but no matrix entry: {', '.join(missing_nodes)}")
        if marker_mismatch:
            print(f"Marker/matrix mismatch: {', '.join(marker_mismatch)}")
        if invalid_nodes:
            print(f"Matrix nodes not found in tests: {', '.join(invalid_nodes)}")
        return 1
    print(f"Traceability valid for {len(required)} Chunk 0 requirements and {len(matrix)} test nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
