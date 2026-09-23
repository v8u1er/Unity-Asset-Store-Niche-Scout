"""Chunk 13 quality-tooling tests: validator, checkers, workflow, and NFR gates.

Each node carries the ``@pytest.mark.lreq`` marker set recorded for it in
``tests/traceability.json``. The suite exercises the widened traceability
validator (R6), the scope-prohibition and secret checkers (R1/R5), the R4 import
edges, the R9 workflow runner seam, and the ``LREQ-NFR-040``/``LREQ-NFR-050``
public-surface and environment gates.

No node makes a live network call, reads the system clock, opens ``.env``, or
writes outside pytest ``tmp_path``. Synthetic fixtures are written to ``tmp_path``
only.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest

from niche_scout.tools import check_import_boundaries as cib
from niche_scout.tools import check_scope_prohibitions as csp
from niche_scout.tools import check_secrets as cs
from niche_scout.tools import quality_workflow as qw
from niche_scout.tools import validate_traceability as vt

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "niche_scout"


# ---------------------------------------------------------------------------
# Traceability validator (LREQ-TST-010)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_required_set_is_every_defined_lreq() -> None:
    """The required set is the whole SRS definition list, not one chunk's subset.

    The validator widens the Chunk 0 seven-ID required set to
    ``defined_ids(srs_text)`` (89 IDs), so every defined requirement must be
    referenced by at least one mapped test (R6).
    """
    srs_text = vt.SRS_PATH.read_text(encoding="utf-8")
    defined = vt.defined_ids(srs_text)
    required = vt.required_ids(srs_text)

    assert required == defined
    assert len(required) == 89


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_marker_parser_reads_all_arguments(tmp_path: Path) -> None:
    """``test_markers`` parses every argument of a multi-argument marker (R6).

    The single-argument parser this replaces silently misclassified 99
    multi-argument markers as unmarked; the widened parser returns both IDs.
    """
    module = tmp_path / "test_multi.py"
    module.write_text(
        "import pytest\n\n\n"
        '@pytest.mark.lreq("LREQ-X-001", "LREQ-X-002")\n'
        "def test_multi() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    marked = vt.test_markers(module)
    assert marked == {"tests/test_multi.py::test_multi": {"LREQ-X-001", "LREQ-X-002"}}


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_exemption_set_is_exactly_three() -> None:
    """The non-analytical exemption is exactly the three contract node IDs (R2c).

    The exemption suppresses only the *unmarked* complaint; an exempt node that
    does carry markers is still subject to exact marker/matrix equality.
    """
    assert vt.NON_ANALYTICAL_EXEMPT == frozenset(
        {
            "tests/test_collector.py::test_module_imports_without_side_effects",
            "tests/test_collector.py::test_request_body_builder_signature_is_stable",
            "tests/test_sampling.py::test_sampling_module_imports_are_pure",
        }
    )
    unmarked = {
        "tests/test_sample.py::test_unmarked": set(),
        "tests/test_sampling.py::test_sampling_module_imports_are_pure": set(),
    }
    assert vt.unmarked_analytical_tests(unmarked) == [
        "tests/test_sample.py::test_unmarked"
    ]


def _synthetic_validator_root(tmp_path: Path, matrix: dict[str, list[str]]) -> Path:
    """Write one synthetic test module and matrix under ``tmp_path``."""
    (tmp_path / "test_sample.py").write_text(
        "import pytest\n\n\n"
        '@pytest.mark.lreq("LREQ-X-001")\n'
        "def test_covered() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "traceability.json").write_text(json.dumps(matrix), encoding="utf-8")
    return tmp_path


def _patch_synthetic_validator(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    matrix: dict[str, list[str]],
) -> None:
    """Point the validator at a synthetic tree with a one-ID defined set.

    ``load_matrix`` is patched as well as ``TRACEABILITY_PATH`` because its
    default argument binds the real path at import time.
    """
    monkeypatch.setattr(vt, "TESTS_DIR", root)
    monkeypatch.setattr(vt, "TRACEABILITY_PATH", root / "traceability.json")
    monkeypatch.setattr(vt, "load_matrix", lambda path=None: dict(matrix))
    monkeypatch.setattr(vt, "defined_ids", lambda _text: {"LREQ-X-001"})
    monkeypatch.setattr(vt, "required_ids", lambda _text: {"LREQ-X-001"})


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_main_passes_on_consistent_synthetic_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A consistent synthetic tree passes: marker set equals matrix entry."""
    matrix = {"tests/test_sample.py::test_covered": ["LREQ-X-001"]}
    root = _synthetic_validator_root(tmp_path, matrix)
    _patch_synthetic_validator(monkeypatch, root, matrix)

    assert vt.main([]) == 0


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_main_fails_on_marker_matrix_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A marked test whose matrix entry differs fails in both directions."""
    matrix = {"tests/test_sample.py::test_covered": ["LREQ-X-999"]}
    root = _synthetic_validator_root(tmp_path, matrix)
    _patch_synthetic_validator(monkeypatch, root, matrix)

    assert vt.main([]) == 1


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_main_fails_on_orphan_matrix_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matrix entry with no matching test node is an orphan and fails."""
    matrix = {
        "tests/test_sample.py::test_covered": ["LREQ-X-001"],
        "tests/test_sample.py::test_ghost": ["LREQ-X-001"],
    }
    root = _synthetic_validator_root(tmp_path, matrix)
    _patch_synthetic_validator(monkeypatch, root, matrix)

    assert vt.main([]) == 1


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_main_fails_on_unmarked_test_outside_exemption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any unmarked analytical test outside the three-ID exemption fails."""
    root = tmp_path
    (root / "test_sample.py").write_text(
        "def test_unmarked() -> None:\n    pass\n", encoding="utf-8"
    )
    _patch_synthetic_validator(monkeypatch, root, {})

    assert vt.main([]) == 1


@pytest.mark.lreq("LREQ-TST-010")
def test_traceability_validator_passes_on_current_tree(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real tree validates: 89 required/defined IDs and the 3 exemptions."""
    code = vt.main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "89 required/defined LREQ IDs" in captured.out
    assert "3 exempted non-analytical nodes" in captured.out


# ---------------------------------------------------------------------------
# Scope prohibitions (LREQ-NFR-050)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-050")
def test_scope_prohibition_tokens_are_exactly_the_six() -> None:
    """``RETIRED_FEATURES`` is exactly the six retired tokens from R1."""
    assert {feature.token for feature in csp.RETIRED_FEATURES} == {
        "--resume",
        "--checkpoint",
        "--schedule",
        "favorite_count",
        "packageInListHotness",
        "raw_product_details",
    }


@pytest.mark.lreq("LREQ-NFR-050")
def test_scope_prohibitions_pass_on_current_tree() -> None:
    """No retired token appears in the production surface today."""
    assert csp.main([]) == 0


@pytest.mark.lreq("LREQ-NFR-050")
def test_scope_prohibitions_detect_injected_token(tmp_path: Path) -> None:
    """A retired token injected into a scratch module is detected and fails."""
    scratch = tmp_path / "injected.py"
    scratch.write_text(
        "def reintroduced() -> int:\n"
        "    favorite_count = 3\n"
        "    return favorite_count\n",
        encoding="utf-8",
    )
    violations = csp.scan_paths([scratch])
    assert {violation.token for violation in violations} == {"favorite_count"}
    assert [violation.line_number for violation in violations] == [2, 3]


@pytest.mark.lreq("LREQ-NFR-050")
def test_scope_prohibitions_skip_docstrings_and_comments(tmp_path: Path) -> None:
    """A token named in a docstring or comment is not a reintroduction.

    The prohibition prose that names a retired field while forbidding it (the
    ``collector_graphql`` docstring) and an explanatory comment must not fail the
    scan, while a real string constant is still caught.
    """
    prose = tmp_path / "prose.py"
    prose.write_text(
        '"""Module docstring mentioning packageInListHotness and --resume."""\n'
        "\n"
        "# A comment about raw_product_details and --checkpoint.\n"
        "def build() -> str:\n"
        '    """Docstring mentioning favorite_count."""\n'
        "    return 'lean'\n",
        encoding="utf-8",
    )
    assert csp.scan_paths([prose]) == []

    literal = tmp_path / "literal.py"
    literal.write_text('VALUE = "raw_product_details"\n', encoding="utf-8")
    assert [violation.token for violation in csp.scan_paths([literal])] == [
        "raw_product_details"
    ]


# ---------------------------------------------------------------------------
# Secret handling (LREQ-SEC-010 / LREQ-SEC-020)
# ---------------------------------------------------------------------------


_QUOTE = chr(34)


def _env_assignment_line(name: str, value: str) -> str:
    """Assemble ``NAME="value"`` without embedding the literal shape in source."""
    return f"{name}={_QUOTE}{value}{_QUOTE}"


def _bearer_line(value: str) -> str:
    """Assemble an ``Authorization: Bearer <value>`` line at runtime."""
    return "Authorization: Bearer " + value


def _csrf_header_line(value: str) -> str:
    """Assemble an ``X-CSRF-Token: <value>`` line at runtime."""
    return "X-CSRF-Token: " + value


@pytest.mark.lreq("LREQ-SEC-010")
def test_secret_checker_passes_on_current_tree() -> None:
    """The tracked surface carries no literal credential today."""
    assert cs.main([]) == 0


@pytest.mark.lreq("LREQ-SEC-020")
def test_secret_checker_detects_literal_without_echoing_value(tmp_path: Path) -> None:
    """A literal credential is reported by class only, never by value.

    The finding names the file, the 1-based line, and a pattern class; the matched
    value never appears in the finding or the printed failure line.
    """
    literal = "actual-secret-" + "eyJhbGciOiJIUzI1NiJ9"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "leak.py").write_text(
        _bearer_line(literal) + "\n", encoding="utf-8"
    )
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    findings = cs.find_credential_findings(tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.line_number == 1
    assert finding.pattern_class == "literal bearer credential"
    assert literal not in repr(finding)
    assert literal not in finding.pattern_class


@pytest.mark.lreq("LREQ-SEC-020")
def test_secret_checker_allows_placeholders() -> None:
    """Seeds, sentinels, and ``fixture-*`` values are not findings.

    The existing fixtures use exactly these shapes, so the checker must pass them.
    """
    allowed = (
        _env_assignment_line("NICHESCOUT_COVEO_BEARER_TOKEN", "YOUR_TOKEN"),
        _env_assignment_line("NICHESCOUT_UNITY_CSRF_TOKEN", "REDACTED"),
        _env_assignment_line("NICHESCOUT_COVEO_BEARER_TOKEN", "<set-locally>"),
        _env_assignment_line("NICHESCOUT_UNITY_CSRF_TOKEN", "changeme"),
        "Authorization: Bearer fixture-coveo-token",
        "X-CSRF-Token: fixture-csrf-token",
        'COVEO_TOKEN_ENV = "NICHESCOUT_COVEO_BEARER_TOKEN"',
        'environment = {"NICHESCOUT_COVEO_BEARER_TOKEN": raw}',
        "a Coveo bearer credential is required before network collection",
    )
    for line in allowed:
        assert cs.scan_text_for_secrets(line) == [], line


@pytest.mark.lreq("LREQ-SEC-020")
def test_secret_checker_flags_literal_env_assignment_and_csrf_header() -> None:
    """A non-placeholder literal in any of the three forms is a finding."""
    assert cs.scan_text_for_secrets(
        _env_assignment_line("NICHESCOUT_COVEO_BEARER_TOKEN", "realvalue12345")
    ) == [(1, "literal credential assigned to a frozen env var")]
    assert cs.scan_text_for_secrets(
        _bearer_line("eyJhbGciOiJIUzI1NiJ9." + "payload.sig")
    ) == [(1, "literal bearer credential")]
    assert cs.scan_text_for_secrets(_csrf_header_line("abcdef" + "1234567890")) == [
        (1, "literal CSRF header credential")
    ]


@pytest.mark.lreq("LREQ-SEC-010")
def test_secret_checker_asserts_gitignore_env_pattern(tmp_path: Path) -> None:
    """A missing ``.env`` ignore pattern is a finding; a present one is not.

    The check never opens ``.env``: a ``.env`` file that the pattern covers is
    untracked and allowed, and its contents are irrelevant.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("x = 1\n", encoding="utf-8")

    missing = cs.find_credential_findings(tmp_path)
    assert any(
        finding.pattern_class == "missing .gitignore .env pattern"
        for finding in missing
    )

    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        _env_assignment_line("NICHESCOUT_COVEO_BEARER_TOKEN", "unread-secret") + "\n",
        encoding="utf-8",
    )
    after = cs.find_credential_findings(tmp_path)
    assert all(finding.path != Path(".env") for finding in after)
    assert not any(finding.pattern_class.startswith("literal") for finding in after)


# ---------------------------------------------------------------------------
# R4 import edges (LREQ-ARCH-010)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-010")
def test_report_module_has_no_forbidden_imports_or_clock_reads() -> None:
    """``report.py`` imports no orchestration module and reads no clock (R4)."""
    tree = ast.parse(
        (PACKAGE / "report.py").read_text(encoding="utf-8"),
        filename="report.py",
    )
    imported = cib.imported_module_names(tree)
    forbidden = {
        "cli",
        "pipeline",
        "collector",
        "collector_coveo",
        "collector_graphql",
        "config",
        "metrics",
        "scoring",
    }
    assert imported & forbidden == set()
    assert cib.clock_violations(tree) == []


@pytest.mark.lreq("LREQ-ARCH-010")
def test_cli_module_imports_report() -> None:
    """``cli.py`` depends on ``report`` for the dashboard/run render (R4)."""
    tree = ast.parse(
        (PACKAGE / "cli.py").read_text(encoding="utf-8"), filename="cli.py"
    )
    assert "report" in cib.imported_module_names(tree)


@pytest.mark.lreq("LREQ-ARCH-010")
def test_import_boundaries_checker_passes_and_registration_is_unchanged() -> None:
    """The pure-module registration stays exactly ``metrics.py``/``scoring.py``."""
    assert cib.PURE_MODULES == ("metrics.py", "scoring.py")
    assert cib.main([]) == 0


# ---------------------------------------------------------------------------
# R9 workflow ordering and exit-code propagation (LREQ-NFR-050)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-050")
def test_quality_workflow_runs_all_steps_and_returns_zero() -> None:
    """Every step runs in order and an all-pass run returns ``0``."""
    seen: list[tuple[str, ...]] = []

    def runner(argv: list[str]) -> int:
        seen.append(tuple(argv))
        return 0

    assert qw.run_workflow(runner=runner) == 0
    assert len(seen) == len(qw.STEPS)
    modules = [argv[2] for argv in seen if len(argv) > 2]
    assert modules == [
        "niche_scout.tools.validate_traceability",
        "niche_scout.tools.check_import_boundaries",
        "niche_scout.tools.check_scope_prohibitions",
        "niche_scout.tools.check_secrets",
        "ruff",
        "ruff",
        "pytest",
    ]


@pytest.mark.lreq("LREQ-NFR-050")
def test_quality_workflow_stops_at_first_failure_and_propagates_code() -> None:
    """A failing step stops the workflow and its exit code is returned."""
    seen: list[tuple[str, ...]] = []
    failing_index = 3

    def runner(argv: list[str]) -> int:
        seen.append(tuple(argv))
        return 7 if len(seen) == failing_index + 1 else 0

    assert qw.run_workflow(runner=runner) == 7
    assert len(seen) == failing_index + 1


@pytest.mark.lreq("LREQ-NFR-050")
def test_quality_workflow_commands_use_the_current_interpreter() -> None:
    """Every step is a ``python -m`` invocation of the current interpreter."""
    for step, argv in qw.STEP_COMMANDS.items():
        assert argv[0] == sys.executable, step
        assert argv[1] == "-m", step
    assert "mypy" not in {argv[2] for argv in qw.STEP_COMMANDS.values()}
    assert "coverage" not in {argv[2] for argv in qw.STEP_COMMANDS.values()}


# ---------------------------------------------------------------------------
# LREQ-NFR-040 public surface
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-040")
def test_public_metric_and_scoring_functions_have_hints_and_docstrings() -> None:
    """Every public metric/scoring function is fully annotated and documented.

    ``LREQ-NFR-040`` requires type hints plus docstrings that state null and
    edge-case behavior for the public metric and scoring surface.
    """
    import niche_scout.metrics as metrics_module
    import niche_scout.scoring as scoring_module

    problems: list[str] = []
    for module in (metrics_module, scoring_module):
        for name, obj in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(obj):
                continue
            if obj.__module__ != module.__name__:
                continue
            signature = inspect.signature(obj)
            missing = [
                parameter.name
                for parameter in signature.parameters.values()
                if parameter.annotation is inspect.Parameter.empty
                and parameter.kind
                not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
            ]
            if missing:
                problems.append(f"{module.__name__}.{name}: unannotated {missing}")
            if signature.return_annotation is inspect.Signature.empty:
                problems.append(f"{module.__name__}.{name}: no return annotation")
            if not (obj.__doc__ or "").strip():
                problems.append(f"{module.__name__}.{name}: no docstring")

    assert problems == []


# ---------------------------------------------------------------------------
# LREQ-NFR-050 environment smoke
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-050")
def test_environment_is_python_311_or_newer() -> None:
    """The tool targets Python 3.11+ (SRS §11)."""
    assert sys.version_info >= (3, 11)


@pytest.mark.lreq("LREQ-NFR-050")
def test_pyproject_declares_requires_python_and_no_new_tooling() -> None:
    """``pyproject.toml`` declares the interpreter floor and adds no CI/strict step.

    ``LREQ-NFR-050`` scopes the environment to ``pathlib`` and the frozen
    dependency set; no CI, coverage, or strict-typing step is introduced (R9).
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "requires-python" in text
    assert ">=3.11" in text.replace(" ", "")
    assert "mypy" not in text
    assert "[tool.coverage" not in text
    assert "quality_workflow" not in text
