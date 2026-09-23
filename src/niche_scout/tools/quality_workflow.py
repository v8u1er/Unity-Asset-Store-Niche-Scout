"""Ordered, dependency-free quality workflow runner (R9, ``LREQ-NFR-060``).

SRS §11 (``LREQ-NFR-060``) makes formatting, linting, secret handling, and
analytical tests part of the normal workflow. This module is the one command that
runs the maintained gate in a fixed order:

1. ``validate_traceability``
2. ``check_import_boundaries``
3. ``check_scope_prohibitions``
4. ``check_secrets``
5. ``ruff check``
6. ``ruff format --check``
7. ``pytest -q``

It returns ``0`` only when every step passes, and otherwise the **first** failing
step's exit code. Every step is invoked through the injectable :data:`Runner`
seam, so a test can exercise the ordering and exit-code propagation without
re-running pytest inside pytest. The module adds no dependency, no strict-typing
step, no coverage gate, and no CI step, and it declares no ``[project.scripts]``
entry (SRS §11/§15 defer those).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: The workflow steps in the fixed R9 order.
STEPS: tuple[str, ...] = (
    "validate_traceability",
    "check_import_boundaries",
    "check_scope_prohibitions",
    "check_secrets",
    "ruff-check",
    "ruff-format-check",
    "pytest",
)

#: The command argv for each step. Python module steps use ``sys.executable`` so
#: the same interpreter that runs the workflow runs the tools.
STEP_COMMANDS: dict[str, tuple[str, ...]] = {
    "validate_traceability": (
        sys.executable,
        "-m",
        "niche_scout.tools.validate_traceability",
    ),
    "check_import_boundaries": (
        sys.executable,
        "-m",
        "niche_scout.tools.check_import_boundaries",
    ),
    "check_scope_prohibitions": (
        sys.executable,
        "-m",
        "niche_scout.tools.check_scope_prohibitions",
    ),
    "check_secrets": (
        sys.executable,
        "-m",
        "niche_scout.tools.check_secrets",
    ),
    "ruff-check": (sys.executable, "-m", "ruff", "check"),
    "ruff-format-check": (sys.executable, "-m", "ruff", "format", "--check"),
    "pytest": (sys.executable, "-m", "pytest", "-q"),
}

Runner = Callable[[Sequence[str]], int]


def _default_runner(argv: Sequence[str]) -> int:
    """Run ``argv`` as a subprocess in the repository root and return its code."""
    completed = subprocess.run(list(argv), cwd=str(ROOT), check=False)
    return int(completed.returncode)


def run_workflow(*, runner: Runner = _default_runner) -> int:
    """Run the steps in :data:`STEPS` order; return the first failing exit code.

    The ``runner`` seam receives each step's command argv and returns the process
    exit code. The workflow stops at the first non-zero code and returns it, so a
    later step is never reached after a failure. Returns ``0`` iff every step
    returns ``0``.
    """
    for step in STEPS:
        code = runner(STEP_COMMANDS[step])
        if code != 0:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ``python -m niche_scout.tools.quality_workflow``.

    Delegates to :func:`run_workflow`. ``argv`` is accepted for a conventional
    ``main`` signature; the workflow takes no options. No ``[project.scripts]``
    entry is added (R9).
    """
    _ = argv
    return run_workflow()


def step_commands() -> dict[str, tuple[str, ...]]:
    """Return a copy of the step -> command mapping (read-only inspection)."""
    return dict(STEP_COMMANDS)


if __name__ == "__main__":
    sys.exit(main())
