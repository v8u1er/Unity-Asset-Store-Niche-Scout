"""AST scope-prohibition checker for retired Lean-v1 features.

SRS §15 removes a set of behaviours from the lean implementation and AGENTS.md
"Out of scope" repeats the prohibition. This checker fails when one of the
retired features is reintroduced into the production surface
(``src/niche_scout/**/*.py`` only; tests, config, and ``pyproject.toml`` are not
scanned).

Detection is AST-based and matches the exact literal tokens in
:data:`RETIRED_FEATURES` against:

* ``ast.Name`` / ``ast.Attribute`` identifiers,
* function/method argument names and keyword-argument names,
* non-docstring ``ast.Constant`` string literals.

Module/class/function docstrings and comments are skipped, so the legitimate
prohibition prose that names a retired field while forbidding it (for example the
``packageInListHotness`` note in ``collector_graphql.build_product_detail_operation``
and the "historically rejected only ``None``" note in ``database.py``) does not
fail the scan.

Abstract deferrals with no concrete identifier to search for - historical trends,
run comparison, configurable score weights, and CI - are covered by review, not by
this token search. They are listed in SRS §15 but have no stable literal whose
presence alone proves the feature was implemented.

The check is a maintained guard, not a proof: a retired feature reintroduced under
a different name is out of its reach.

The guard's own definition module is the one production file that legitimately
contains every retired token (inside :data:`RETIRED_FEATURES`), so :func:`main`
excludes this module from the scan. The token literals are the maintained
prohibition list itself, not a reintroduced behavior; without the exclusion the
list could never be stored inside the scanned production surface.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "niche_scout"


@dataclass(frozen=True, slots=True)
class RetiredFeature:
    """One retired literal token and the documents that prohibit it.

    ``token`` is the exact, case-sensitive literal to match. ``reason`` is a short
    prohibition summary; ``source`` names the document path and locator.
    """

    token: str
    reason: str
    source: str


@dataclass(frozen=True, slots=True)
class ScopeViolation:
    """One matched retired token in the production surface."""

    path: Path
    line_number: int
    token: str
    source: str


#: The retired Lean-v1 tokens (R1). Sources: SRS-lean.md §15 (the deferred-scope
#: table) and §1.3; the retired ``Documents/retired-documents/SRS-revision2.md``
#: §10 ``ND-*`` labels; and AGENTS.md "Out of scope".
RETIRED_FEATURES: tuple[RetiredFeature, ...] = (
    RetiredFeature(
        token="--resume",
        reason=(
            "checkpoint/resume support is deferred; an interrupted run restarts "
            "from the beginning"
        ),
        source=(
            "SRS-lean.md §15 (Checkpoint/resume support) + "
            "retired-documents/SRS-revision2.md §10 ND-12"
        ),
    ),
    RetiredFeature(
        token="--checkpoint",
        reason=(
            "checkpoint/resume support is deferred; no checkpoint CLI mechanism exists"
        ),
        source=(
            "SRS-lean.md §15 (Checkpoint/resume support) + "
            "retired-documents/SRS-revision2.md §10 ND-12"
        ),
    ),
    RetiredFeature(
        token="--schedule",
        reason="scheduled execution is deferred; the CLI is invoked manually",
        source=(
            "SRS-lean.md §15 (Scheduled execution) + "
            "retired-documents/SRS-revision2.md §10 ND-7"
        ),
    ),
    RetiredFeature(
        token="favorite_count",
        reason=(
            "favorite-count enrichment is an unvalidated, unused signal and is not "
            "part of the score or required GraphQL fields"
        ),
        source=(
            "SRS-lean.md §15 (Favorite-count enrichment) + "
            "retired-documents/SRS-revision2.md §10 ND-9"
        ),
    ),
    RetiredFeature(
        token="packageInListHotness",
        reason=(
            "the favorite-count field is retired and is not requested in any "
            "GraphQL operation"
        ),
        source=(
            "SRS-lean.md §15 (Favorite-count enrichment) + "
            "retired-documents/SRS-revision2.md §10 ND-9"
        ),
    ),
    RetiredFeature(
        token="raw_product_details",
        reason=(
            "full raw API-response archival is deferred; only required normalized "
            "fields, request metadata, and redacted error summaries remain"
        ),
        source="SRS-lean.md §15 (Full raw API-response archival)",
    ),
)


def iter_production_python_files(root: Path = PACKAGE) -> Iterable[Path]:
    """Yield ``src/niche_scout/**/*.py`` only, in stable sorted order.

    Tests, config, and ``pyproject.toml`` are not scanned (R1); the package's own
    modules under ``src/niche_scout/`` are the production surface.
    """
    return sorted(Path(root).rglob("*.py"))


def _scanned_production_files(root: Path = PACKAGE) -> list[Path]:
    """Yield the production files to scan, excluding this definition module.

    This module stores the retired tokens in :data:`RETIRED_FEATURES`; that is the
    maintained prohibition list, not a reintroduced behavior, so it is never
    scanned.
    """
    own_path = Path(__file__).resolve()
    return [
        path
        for path in iter_production_python_files(root)
        if path.resolve() != own_path
    ]


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Return the ``id()`` of every module/class/function docstring constant."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", ())
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def scan_ast(
    tree: ast.AST, *, features: Sequence[RetiredFeature] = RETIRED_FEATURES
) -> list[tuple[int, str]]:
    """Return 1-based line numbers and matched tokens for one parsed module.

    Matches identifiers, argument names, keyword-argument names, and non-docstring
    string constants. Docstrings and comments are skipped. A line/token pair is
    returned once even when several nodes on it match the same token.
    """
    tokens = {feature.token: feature for feature in features}
    docstrings = _docstring_nodes(tree)
    hits: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    def record(lineno: int, value: str) -> None:
        if value in tokens and (lineno, value) not in seen:
            seen.add((lineno, value))
            hits.append((lineno, value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            record(node.lineno, node.id)
        elif isinstance(node, ast.Attribute):
            record(node.lineno, node.attr)
        elif isinstance(node, ast.arg):
            record(node.lineno, node.arg)
        elif isinstance(node, ast.keyword) and node.arg is not None:
            record(node.lineno, node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                record(node.lineno, node.value)
    return sorted(hits)


def scan_paths(
    paths: Iterable[Path], *, features: Sequence[RetiredFeature] = RETIRED_FEATURES
) -> list[ScopeViolation]:
    """Scan each Python file and return every retired-token violation."""
    violations: list[ScopeViolation] = []
    by_token = {feature.token: feature for feature in features}
    for path in paths:
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for line_number, token in scan_ast(tree, features=features):
            violations.append(
                ScopeViolation(
                    path=Path(path),
                    line_number=line_number,
                    token=token,
                    source=by_token[token].source,
                )
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    """Exit 0 when no retired token is matched in the production surface.

    Otherwise print one ``path:line:token (source)`` line per violation and
    return 1.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else PACKAGE
    violations = scan_paths(_scanned_production_files(root))
    if violations:
        for violation in violations:
            print(
                f"{violation.path}:{violation.line_number}:{violation.token} "
                f"({violation.source})"
            )
        return 1
    print(
        "Scope prohibitions valid: no retired token found in "
        f"{root}/**/*.py ({len(RETIRED_FEATURES)} tokens checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
