"""Analytical tests for Chunk 12 — CLI commands and configuration precedence.

Source of truth: ``Documents/SRS-lean.md`` §10 (``LREQ-RPT-010``,
``LREQ-CLI-010`` through ``LREQ-CLI-040``), §4.3 (``LREQ-SEC-010``), §13
(``LREQ-TST-080``), §14 (the non-configurable ``MIN_CATEGORIES_PER_RUN``); the
frozen plan
``Documents/plans/chunk-12-cli-commands-and-configuration-precedence.md`` §5
(public surface), §8 (edge cases), §9 (test plan), §12 (Rulings 1-8); and the
consumed interfaces ``chunk-00``, ``chunk-03``, ``chunk-05``, ``chunk-10``,
``chunk-11``.

Every analytical node carries ``@pytest.mark.lreq(...)`` and a matching
``tests/traceability.json`` entry keyed by its base node ID.

No network, no credentials, and no clock reads: the transports are in-memory
recorders, the clock is ``pipeline_fixtures.FixedClock``, the database lives
under pytest ``tmp_path``, and the renderer is a capturing recorder. The one
production function exercised end to end — ``build_graphql_transport`` — is
tested through a monkeypatched ``urllib.request`` seam (recording in memory).
"""

from __future__ import annotations

import argparse
import importlib
import io
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest
from fixtures import cli_fixtures as cf
from fixtures import config_fixtures

from niche_scout import cli, config, database, models, report

# --------------------------------------------------------------------------
# Constants read from their owners, never restated (SRS §14 is non-configurable).
# --------------------------------------------------------------------------

MIN_CATEGORIES_PER_RUN = models.MIN_CATEGORIES_PER_RUN


def _pipeline_fixtures():
    """Return the Chunk 10 fixture module (imported lazily, by fixture name)."""
    from fixtures import pipeline_fixtures as pf

    return pf


def _report_fixtures():
    """Return the Chunk 11 fixture module (imported lazily, by fixture name)."""
    from fixtures import report_fixtures as rf

    return rf


def _buffers() -> tuple[io.StringIO, io.StringIO]:
    """Return fresh in-memory stdout/stderr buffers."""
    return io.StringIO(), io.StringIO()


def _environment() -> Mapping[str, str]:
    """Return the non-secret fixture credential environment."""
    return config_fixtures.MOCK_ENVIRONMENT


def _noop_write_report(repository, run_id, output_path, *, fmt="html"):
    """An injected no-op writer, so no report file is produced for a test."""
    _ = repository, run_id, fmt
    return Path(output_path)


def _scenario(directory: Path, *, run_id: str = "run-12-e2e") -> cf.ScenarioArtifacts:
    """Write and return the eight-category CLI scenario under ``directory``."""
    return cf.scenario_artifacts(directory, run_id=run_id)


def _run_command(artifacts: cf.ScenarioArtifacts, **overrides):
    """Invoke ``cli.run_command`` on the scenario with injected recorders."""
    options = overrides.pop("options", None)
    command = overrides.pop("command", cli.run_command)
    values = {
        "environ": _environment(),
        "clock": artifacts.scenario.clock,
        "sleeper": lambda _seconds: None,
        "coveo_transport": artifacts.scenario.coveo_transport,
        "graphql_transport": artifacts.scenario.graphql_transport,
        "template_path": artifacts.template_path,
        "open_repository": cf.RecordingRepositoryFactory(),
        "write_report": _noop_write_report,
        "stdout": io.StringIO(),
        "stderr": io.StringIO(),
    }
    values.update(overrides)
    if options is None:
        options = cf.run_options(
            artifacts.categories_path,
            artifacts.config_path,
            artifacts.db_path,
            run_id=artifacts.run_id,
        )
    return command(options, **values)


def _action_option_strings(parser: argparse.ArgumentParser) -> set[str]:
    """Return every option string of ``parser`` and its subparsers."""
    found: set[str] = set()
    stack: list[argparse.ArgumentParser] = [parser]
    while stack:
        current = stack.pop()
        for action in current._actions:
            found.update(action.option_strings)
            if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                stack.extend(action.choices.values())
    return found


# --------------------------------------------------------------------------
# LREQ-CLI-010 — the primary command runs one pipeline; non-zero on errors.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-010")
def test_run_command_invokes_pipeline_once_and_exits_zero(tmp_path: Path) -> None:
    """A completed run returns ``EXIT_OK`` and drives the injected transports.

    The repository is opened at the resolved config's ``db_path``; the pipeline
    ran (the transports were called) and the report renderer either did not run
    (no ``--report``) or ran exactly once after completion.
    """
    artifacts = _scenario(tmp_path)
    factory = cf.RecordingRepositoryFactory()
    stdout, stderr = _buffers()
    code = _run_command(
        artifacts,
        open_repository=factory,
        write_report=_noop_write_report,
        stdout=stdout,
        stderr=stderr,
    )
    factory.close_all()

    assert code == cli.EXIT_OK
    assert factory.paths == [artifacts.db_path]
    assert artifacts.scenario.coveo_transport.call_count > 0
    assert artifacts.scenario.graphql_transport.call_count > 0


@pytest.mark.lreq("LREQ-CLI-010")
def test_run_command_does_not_render_on_failure_path(tmp_path: Path) -> None:
    """A runtime failure exits non-zero and never calls the report renderer.

    The pipeline is forced to abort before it can return (a configuration that
    cannot be satisfied), so ``write_report`` is never invoked.
    """
    pf = _pipeline_fixtures()
    artifacts = _scenario(tmp_path, run_id="run-12-fail")
    rejecting_config = pf.fixture_config(
        tmp_path,
        min_categories_per_run=pf.MIN_CATEGORIES,
        max_discovery_results_per_category=pf.SCENARIO_DISCOVERY_CAP,
        identity_preflight_min_categories=1,
        identity_preflight_assets_per_category=1,
        identity_preflight_min_success_rate=1.0,
    )
    config_path = cf.write_run_config(tmp_path, rejecting_config, name="fail.toml")
    recorder = cf.RecordingWriteReport()
    report_path = tmp_path / "never.html"
    options = cf.run_options(
        artifacts.categories_path,
        config_path,
        artifacts.db_path,
        run_id=artifacts.run_id,
        report_path=report_path,
    )
    rejecting = pf.graphql_rejecting_transport(
        tuple(_sampled_identity_keys(artifacts.scenario))
    )
    code = _run_command(
        artifacts,
        options=options,
        graphql_transport=rejecting,
        write_report=recorder,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == cli.EXIT_RUNTIME_ERROR
    assert recorder.call_count == 0
    assert not report_path.exists()


@pytest.mark.lreq("LREQ-CLI-010")
def test_no_subcommand_exits_nonzero_without_pipeline_or_report() -> None:
    """``main([])`` is a usage error and performs no pipeline or report call."""
    assert cli.main([]) == cli.EXIT_USAGE_ERROR


@pytest.mark.lreq("LREQ-CLI-010")
def test_main_help_returns_ok(capsys: pytest.CaptureFixture[str]) -> None:
    """``main(['--help'])`` prints usage and returns ``EXIT_OK``."""
    assert cli.main(["--help"]) == cli.EXIT_OK
    captured = capsys.readouterr()
    assert "run" in captured.out
    assert "dashboard" in captured.out


@pytest.mark.lreq("LREQ-CLI-010")
def test_main_unknown_subcommand_is_a_usage_error() -> None:
    """An unrecognized subcommand exits 2 with no pipeline or report call."""
    assert cli.main(["explode"]) == cli.EXIT_USAGE_ERROR


# --------------------------------------------------------------------------
# LREQ-CLI-010 / LREQ-RPT-010 — the renderer runs only after completion.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-RPT-010")
def test_run_command_calls_renderer_only_after_pipeline_returns(
    tmp_path: Path,
) -> None:
    """The renderer is called once, only when ``--report PATH`` is given.

    The recorded ``run_id`` equals the pipeline's own ``run_id``, so the
    renderer observed the completed run and not an earlier state; the recorded
    format is the ``--report-format`` value (default ``html``).
    """
    artifacts = _scenario(tmp_path, run_id="run-12-report")
    recorder = cf.RecordingWriteReport()
    report_path = tmp_path / cf.EXPECTED_REPORT_FILENAME
    options = cf.run_options(
        artifacts.categories_path,
        artifacts.config_path,
        artifacts.db_path,
        run_id=artifacts.run_id,
        report_path=report_path,
    )
    factory = cf.RecordingRepositoryFactory()
    code = _run_command(
        artifacts,
        options=options,
        open_repository=factory,
        write_report=recorder,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    factory.close_all()

    assert code == cli.EXIT_OK
    assert recorder.call_count == 1
    _, run_id, written_path, fmt = recorder.calls[0]
    assert run_id == artifacts.run_id
    assert Path(written_path) == report_path
    assert fmt == "html"
    assert report_path.is_file()


@pytest.mark.lreq("LREQ-RPT-010")
def test_run_without_report_option_writes_no_report(tmp_path: Path) -> None:
    """The renderer runs only when ``--report PATH`` is given (Ruling 5)."""
    artifacts = _scenario(tmp_path, run_id="run-12-no-report")
    recorder = cf.RecordingWriteReport()
    factory = cf.RecordingRepositoryFactory()
    code = _run_command(
        artifacts,
        open_repository=factory,
        write_report=recorder,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    factory.close_all()

    assert code == cli.EXIT_OK
    assert recorder.call_count == 0
    assert not list(tmp_path.glob("*.html"))


@pytest.mark.lreq("LREQ-RPT-010")
def test_run_parses_report_path_and_format(tmp_path: Path) -> None:
    """``run --report PATH --report-format text`` parses to the option fields."""
    report_path = tmp_path / "out.txt"
    parsed = cli.parse_options(
        [
            "run",
            "--categories",
            str(tmp_path / "categories.json"),
            "--config",
            str(tmp_path / "default.toml"),
            "--report",
            str(report_path),
            "--report-format",
            "text",
        ]
    )
    assert parsed.report_path == report_path
    assert parsed.report_format == "text"
    assert parsed.run_id is None


# --------------------------------------------------------------------------
# LREQ-CLI-010 / LREQ-CLI-040 — error mapping and rejection before ranking.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-CLI-040")
def test_run_command_maps_pipeline_configuration_error_to_nonzero(
    tmp_path: Path,
) -> None:
    """A too-small run maps ``PipelineConfigurationError`` to ``EXIT_USAGE_ERROR``.

    The CLI must not rank, must not write a report, and must not touch a
    transport (plan §5 behavioral contract).
    """
    pf = _pipeline_fixtures()
    categories = tuple(f"Category/{index:04d}" for index in range(1, 3))
    categories_path = cf.write_categories_file(tmp_path, categories)
    config_path = cf.write_toml_file(
        tmp_path, cf.DASHBOARD_TOML_BODY, name="small.toml"
    )
    coveo = pf.RecordingCoveoTransport({})
    graphql = pf.RecordingGraphQLTransport({})
    recorder = cf.RecordingWriteReport()
    options = cf.run_options(
        categories_path,
        config_path,
        tmp_path / "small.sqlite3",
        report_path=tmp_path / "never.html",
    )
    code = cli.run_command(
        options,
        environ=_environment(),
        coveo_transport=coveo,
        graphql_transport=graphql,
        open_repository=cf.RecordingRepositoryFactory(),
        write_report=recorder,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert MIN_CATEGORIES_PER_RUN == 8
    assert len(categories) < MIN_CATEGORIES_PER_RUN
    assert code == cli.EXIT_USAGE_ERROR
    assert coveo.call_count == 0
    assert graphql.call_count == 0
    assert recorder.call_count == 0


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-CLI-040")
def test_run_command_maps_taxonomy_error_to_nonzero_without_network(
    tmp_path: Path,
) -> None:
    """An invalid taxonomy maps ``TaxonomyInvalidError`` to ``EXIT_USAGE_ERROR``.

    The taxonomy failure happens before any transport call (chunk-10 §3 step 2).
    """
    pf = _pipeline_fixtures()
    categories = pf.compliant_category_paths()
    categories_path = cf.write_categories_file(tmp_path, categories)
    config_path = cf.write_run_config(
        tmp_path, pf.fixture_config(tmp_path), name="taxonomy.toml"
    )
    # A taxonomy missing one requested category is invalid (SRS §4.1 LREQ-EXT-020).
    pf.write_taxonomy(tmp_path, pf.taxonomy_payload(tuple(categories)[:-1]))
    coveo = pf.RecordingCoveoTransport({})
    graphql = pf.RecordingGraphQLTransport({})
    recorder = cf.RecordingWriteReport()
    options = cf.run_options(
        categories_path,
        config_path,
        tmp_path / "taxonomy.sqlite3",
        report_path=tmp_path / "never.html",
    )
    code = cli.run_command(
        options,
        environ=_environment(),
        coveo_transport=coveo,
        graphql_transport=graphql,
        open_repository=cf.RecordingRepositoryFactory(),
        write_report=recorder,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == cli.EXIT_USAGE_ERROR
    assert coveo.call_count == 0
    assert graphql.call_count == 0
    assert recorder.call_count == 0


@pytest.mark.lreq("LREQ-CLI-040")
def test_run_command_rejects_fewer_than_min_categories_before_ranking(
    tmp_path: Path,
) -> None:
    """Fewer than ``MIN_CATEGORIES_PER_RUN`` categories is rejected before ranking.

    This is the CLI mapping of the pipeline's already-frozen rejection. It does
    not rename or replace
    ``tests/test_pipeline.py::test_run_with_fewer_than_min_categories_is_rejected``
    (LREQ-CLI-040), which remains the pipeline-side node. No run row is
    persisted, so the rejection precedes ranking and persistence.
    """
    pf = _pipeline_fixtures()
    categories = pf.category_set(pf.CATEGORY_COUNT_BELOW_MIN)
    categories_path = cf.write_categories_file(tmp_path, categories)
    config_path = cf.write_toml_file(tmp_path, cf.DASHBOARD_TOML_BODY, name="few.toml")
    db_path = tmp_path / "few.sqlite3"
    factory = cf.RecordingRepositoryFactory()
    coveo = pf.RecordingCoveoTransport({})
    graphql = pf.RecordingGraphQLTransport({})
    code = cli.run_command(
        cf.run_options(categories_path, config_path, db_path),
        environ=_environment(),
        coveo_transport=coveo,
        graphql_transport=graphql,
        open_repository=factory,
        write_report=cf.RecordingWriteReport(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    stored = factory.last.get_run("run-rejected")
    factory.close_all()

    assert len(categories) < MIN_CATEGORIES_PER_RUN
    assert code == cli.EXIT_USAGE_ERROR
    assert stored is None
    assert coveo.call_count == 0
    assert graphql.call_count == 0


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-CLI-040")
def test_run_command_preflight_failed_exits_nonzero_and_surfaces_limitations(
    tmp_path: Path,
) -> None:
    """A preflight-failed run returns ``EXIT_RUNTIME_ERROR`` and prints limitations.

    ``run_pipeline`` returns normally with ``status == failed`` (it does not
    raise); the CLI must map that to a non-zero exit and surface the pipeline's
    already-redacted limitation strings on stderr (chunk-10 §3).
    """
    pf = _pipeline_fixtures()
    artifacts = _scenario(tmp_path, run_id="run-12-preflight")
    # The scenario's default preflight covers the first eligible category; a
    # rejecting transport with a success-rate knob of 1.0 forces a failed gate.
    config = pf.fixture_config(
        tmp_path,
        min_categories_per_run=pf.MIN_CATEGORIES,
        max_discovery_results_per_category=pf.SCENARIO_DISCOVERY_CAP,
        identity_preflight_min_categories=1,
        identity_preflight_assets_per_category=1,
        identity_preflight_min_success_rate=1.0,
    )
    config_path = cf.write_run_config(tmp_path, config, name="preflight.toml")
    options = cf.run_options(
        artifacts.categories_path,
        config_path,
        artifacts.db_path,
        run_id=artifacts.run_id,
    )
    rejecting = pf.graphql_rejecting_transport(
        tuple(_sampled_identity_keys(artifacts.scenario))
    )
    factory = cf.RecordingRepositoryFactory()
    stdout, stderr = _buffers()
    code = cli.run_command(
        options,
        environ=_environment(),
        clock=artifacts.scenario.clock,
        sleeper=lambda _seconds: None,
        coveo_transport=artifacts.scenario.coveo_transport,
        graphql_transport=rejecting,
        template_path=artifacts.template_path,
        open_repository=factory,
        write_report=cf.RecordingWriteReport(),
        stdout=stdout,
        stderr=stderr,
    )
    factory.close_all()

    assert code == cli.EXIT_RUNTIME_ERROR
    assert stderr.getvalue().strip() != ""
    assert "preflight" in stderr.getvalue()


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-CLI-040")
def test_run_completed_provisional_eight_categories_exits_zero(
    tmp_path: Path,
) -> None:
    """An eight-category provisional run returns ``EXIT_OK``.

    Eight equals the frozen ``MIN_CATEGORIES_PER_RUN``; the run is provisional
    with an empty candidate set and null stability outputs, and a completed
    provisional run still exits zero (Ruling 4). The persisted collection
    timestamp is retained.
    """
    artifacts = _scenario(tmp_path, run_id="run-12-provisional")
    factory = cf.RecordingRepositoryFactory()
    code = _run_command(
        artifacts,
        open_repository=factory,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    row = factory.last.get_run(artifacts.run_id)
    factory.close_all()

    assert len(artifacts.scenario.categories) == MIN_CATEGORIES_PER_RUN
    assert code == cli.EXIT_OK
    assert row is not None
    assert row.status == models.RunStatus.COMPLETED.value
    assert row.scoring_cutoff_utc is not None


def _sampled_identity_keys(scenario) -> tuple[str, ...]:
    """Return every identity key the fixture scenario plants (fixture-side only)."""
    pf = _pipeline_fixtures()
    return (
        pf.END_TO_END_SHARED_KEY,
        "901",
        "902",
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
        "D1",
        "D2",
        "E1",
        "E2",
    )


# --------------------------------------------------------------------------
# LREQ-CLI-020 — dashboard reads the database only.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-020")
def test_dashboard_reads_database_only_and_never_constructs_a_transport(
    tmp_path: Path,
) -> None:
    """The dashboard renders a persisted run and constructs no transport.

    This mirrors
    ``tests/test_report.py::test_render_dashboard_html_is_database_read_only``
    at the CLI layer; the two nodes are distinct and both stay in the matrix.
    The collector opener and the CLI transport builder are poisoned, so any
    construction attempt fails this node.
    """
    rf = _report_fixtures()
    from niche_scout import collector_coveo

    def poison(*args, **kwargs):
        raise AssertionError("dashboard must not construct a transport")

    original_opener = collector_coveo.CoveoUrlOpener
    original_builder = cli.build_graphql_transport
    collector_coveo.CoveoUrlOpener = poison
    cli.build_graphql_transport = poison
    try:
        db_path = tmp_path / "dashboard.sqlite3"
        config_path = cf.write_toml_file(
            tmp_path, cf.DASHBOARD_TOML_BODY, name="dash.toml"
        )
        repository = cf.dashboard_repository(
            db_path, rf.CATEGORY_ALPHA, rf.CATEGORY_BRAVO
        )
        recorder = cf.ReportRecorder()
        stdout = io.StringIO()
        try:
            code = cli.dashboard_command(
                cf.dashboard_options(config_path, db_path, run_id=rf.RUN_ID),
                repository=repository,
                report_renderer=recorder,
                stdout=stdout,
                stderr=io.StringIO(),
            )
        finally:
            repository.close()
    finally:
        collector_coveo.CoveoUrlOpener = original_opener
        cli.build_graphql_transport = original_builder

    assert code == cli.EXIT_OK
    assert recorder.call_count == 1
    _, run_id = recorder.calls[0]
    assert run_id == rf.RUN_ID
    assert recorder.html in stdout.getvalue()


@pytest.mark.lreq("LREQ-CLI-020")
def test_dashboard_missing_run_is_nonzero(tmp_path: Path) -> None:
    """A run id with no ``runs`` row maps ``RunNotFoundError`` to non-zero."""
    rf = _report_fixtures()
    db_path = tmp_path / "missing.sqlite3"
    config_path = cf.write_toml_file(tmp_path, cf.DASHBOARD_TOML_BODY, name="miss.toml")
    repository = cf.dashboard_repository(db_path, rf.CATEGORY_ALPHA)
    stdout, stderr = _buffers()
    try:
        code = cli.dashboard_command(
            cf.dashboard_options(config_path, db_path, run_id="run-does-not-exist"),
            repository=repository,
            report_renderer=report.render_dashboard_html,
            stdout=stdout,
            stderr=stderr,
        )
    finally:
        repository.close()

    assert code == cli.EXIT_RUNTIME_ERROR
    assert stdout.getvalue() == ""
    assert stderr.getvalue().strip() != ""


@pytest.mark.lreq("LREQ-CLI-020")
def test_dashboard_selects_completed_and_failed_runs(tmp_path: Path) -> None:
    """Both a completed and a failed persisted run render through the dashboard.

    Run selection is the explicit ``--run-id``, never a default or ``--latest``
    (Ruling 3), so a failed run is selectable and renders through the persisted
    failed-run fallback without a scored row of its own.
    """
    rf = _report_fixtures()
    db_path = tmp_path / "both.sqlite3"
    config_path = cf.write_toml_file(tmp_path, cf.DASHBOARD_TOML_BODY, name="both.toml")
    repository = database.SqliteRepository(db_path)
    try:
        completed = rf.run_record((rf.CATEGORY_ALPHA,), run_id="run-11-completed")
        failed = rf.run_record(
            (rf.CATEGORY_ALPHA,),
            run_id="run-11-failed",
            status=models.RunStatus.FAILED.value,
            scoring_cutoff_utc=None,
            completed_at_utc=None,
            identity_preflight_status=models.IdentityPreflightStatus.FAILED.value,
        )
        with repository.transaction():
            repository.insert_run(completed)
            repository.insert_run(failed)
            repository.insert_category_scores(
                [
                    replace(
                        rf.category_score_record(rf.CATEGORY_ALPHA),
                        run_id="run-11-completed",
                    )
                ]
            )
        for run_id in ("run-11-completed", "run-11-failed"):
            stdout = io.StringIO()
            code = cli.dashboard_command(
                cf.dashboard_options(config_path, db_path, run_id=run_id),
                repository=repository,
                report_renderer=report.render_dashboard_html,
                stdout=stdout,
                stderr=io.StringIO(),
            )
            assert code == cli.EXIT_OK
            assert run_id in stdout.getvalue()
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-CLI-020")
def test_dashboard_requires_run_id(tmp_path: Path) -> None:
    """A missing ``--run-id`` is a usage error and calls no renderer (Ruling 3).

    ``dashboard`` has no default run id and no ``--latest`` flag.
    """
    config_path = cf.write_toml_file(tmp_path, cf.DASHBOARD_TOML_BODY, name="req.toml")
    recorder = cf.ReportRecorder()
    stderr = io.StringIO()
    code = cli.dashboard_command(
        cf.dashboard_options(config_path, tmp_path / "none.sqlite3", run_id=None),
        repository=cf.empty_repository(tmp_path / "none.sqlite3"),
        report_renderer=recorder,
        stdout=io.StringIO(),
        stderr=stderr,
    )

    assert code == cli.EXIT_USAGE_ERROR
    assert recorder.call_count == 0


@pytest.mark.lreq("LREQ-CLI-020")
def test_parser_rejects_dashboard_without_run_id() -> None:
    """``dashboard`` without ``--run-id`` is an argparse usage error (Ruling 3)."""
    with pytest.raises(SystemExit) as excinfo:
        cli.parse_options(["dashboard"])
    assert excinfo.value.code == cli.EXIT_USAGE_ERROR


# --------------------------------------------------------------------------
# LREQ-CLI-030 — CLI > TOML > documented in-code default.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-030")
def test_cli_option_overrides_toml_and_toml_overrides_default(
    tmp_path: Path,
) -> None:
    """CLI overrides TOML; TOML overrides the documented in-code default.

    Golden values: ``--max-discovery-results-per-category 500`` over TOML
    ``1500`` and default ``2000`` resolves to ``500`` (``source == "cli"``);
    TOML ``min_age_days_for_rate = 45`` with the option unset resolves to ``45``
    (``source == "toml"``).
    """
    config_path = cf.write_toml_file(tmp_path, cf.CUSTOM_TOML_BODY, name="custom.toml")
    cli_first = cli.resolve_config(
        cli.parse_options(["run", "--config", str(config_path), *cf.CLI_OVERRIDE_ARGV])
    )
    assert cli_first.max_discovery_results_per_category == cf.CLI_OVERRIDE_EXPECTED
    assert cli_first.source == "cli"

    toml_only = cli.resolve_config(
        cli.parse_options(["run", "--config", str(config_path)])
    )
    assert (
        toml_only.min_age_days_for_rate
        == config_fixtures.CUSTOM_TOML_VALUES["min_age_days_for_rate"]
    )
    assert toml_only.source == "toml"


@pytest.mark.lreq("LREQ-CLI-030")
def test_unset_cli_option_does_not_shadow_toml_or_default(tmp_path: Path) -> None:
    """An unset option is absent, never the in-code default.

    An argparse ``None`` for ``recent_window_days`` with TOML
    ``recent_window_days = 180`` resolves to ``180``; a key absent from both
    resolves to the documented in-code default (``recent_window_days == 365``).
    """
    config_path = cf.write_toml_file(tmp_path, cf.CUSTOM_TOML_BODY, name="unset.toml")
    with_none = config.load_config(
        cli_args={"recent_window_days": None}, toml_path=config_path
    )
    assert with_none.recent_window_days == 180

    default_toml = cf.write_toml_file(
        tmp_path, cf.DEFAULT_TOML_BODY, name="default.toml"
    )
    parsed = cli.parse_options(["run", "--config", str(default_toml)])
    assert parsed.report_format == "html"
    resolved = cli.resolve_config(parsed)
    assert resolved.recent_window_days == cf.DEFAULT_RECENT_WINDOW_DAYS


@pytest.mark.lreq("LREQ-CLI-030")
def test_unknown_cli_option_is_rejected() -> None:
    """An option outside the frozen field set is rejected by ``load_config``.

    The fixed sampling constants and composite weights stay non-configurable
    (chunk-00 §5), so an unknown key raises ``ValueError``.
    """
    with pytest.raises(ValueError):
        config.load_config(cli_args={"arg_max": 5})
    with pytest.raises(ValueError):
        config.load_config(cli_args={"w_d": 0.9})


@pytest.mark.lreq("LREQ-CLI-030")
def test_resolve_config_passes_only_explicit_overrides(tmp_path: Path) -> None:
    """``resolve_config`` never bakes an in-code default into ``cli_args``.

    TOML sets ``max_discovery_results_per_category``; because the option was not
    supplied, ``resolve_config`` leaves it untouched and the TOML value wins.
    """
    config_path = cf.write_toml_file(tmp_path, cf.CUSTOM_TOML_BODY, name="resolve.toml")
    options = cli.CliOptions(
        categories_path=Path("config") / "categories.json",
        config_path=config_path,
        db_path=Path("runtime") / "resolve.sqlite3",
        run_id=None,
        report_path=None,
        report_format="html",
    )
    resolved = cli.resolve_config(options)
    assert (
        resolved.max_discovery_results_per_category
        == config_fixtures.CUSTOM_TOML_VALUES["max_discovery_results_per_category"]
    )
    assert resolved.source != "cli"


@pytest.mark.lreq("LREQ-CLI-030")
def test_parse_options_reads_no_environment_or_clock(monkeypatch) -> None:
    """``parse_options`` reads no environment variable and no clock.

    ``cli.datetime`` and ``config.get_credentials`` (the only environment read)
    are poisoned; parsing still succeeds and returns the supplied path unchanged.
    """

    def poison(*args, **kwargs):
        raise AssertionError("parse_options must not read the environment or clock")

    class _PoisonDatetime:
        @classmethod
        def now(cls, *args, **kwargs):
            poison(*args, **kwargs)

        @classmethod
        def utcnow(cls, *args, **kwargs):
            poison(*args, **kwargs)

    monkeypatch.setattr(cli, "datetime", _PoisonDatetime)
    monkeypatch.setattr(cli.config, "get_credentials", poison)

    parsed = cli.parse_options(["run", "--config", "config/default.toml"])
    assert parsed.config_path == Path("config/default.toml")


# --------------------------------------------------------------------------
# LREQ-SEC-010 — credentials flow through get_credentials; no leaks.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-010")
def test_run_command_never_emits_credentials_or_response_bodies(
    tmp_path: Path,
) -> None:
    """No credential, header value, cookie, or response body reaches stdout/stderr.

    The pipeline's limitation strings are already redacted; the CLI adds
    nothing. Every sentinel string is absent from both streams.
    """
    artifacts = _scenario(tmp_path, run_id="run-12-secrets")
    factory = cf.RecordingRepositoryFactory()
    stdout, stderr = _buffers()
    code = _run_command(
        artifacts,
        open_repository=factory,
        stdout=stdout,
        stderr=stderr,
    )
    factory.close_all()

    assert code == cli.EXIT_OK
    streamed = stdout.getvalue() + stderr.getvalue()
    for sentinel in cf.TRANSPORT_SENTINELS:
        assert sentinel not in streamed
    for value in _environment().values():
        assert value not in streamed


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-SEC-010")
def test_build_graphql_transport_sends_csrf_header_only_and_no_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production callable sends ``X-CSRF-Token`` only, never a ``Cookie``.

    A recording ``urllib`` seam replaces ``urllib.request`` so no live request
    is made. The recorded request carries the frozen header map exactly once and
    no ``Cookie`` header, and the returned value is the frozen
    ``GraphQLBatchResponse`` (Ruling 1).
    """
    recorder = cf.RecordingUrllib(cf.TRANSPORT_SENTINELS[2].encode("utf-8"))
    monkeypatch.setattr(cli.urllib, "request", recorder)

    transport = cli.build_graphql_transport()
    response = transport(cf.graphql_request(), cf.graphql_headers())

    assert len(recorder.requests) == 1
    recorded = recorder.requests[0]
    assert recorded.full_url == cf.GRAPHQL_ENDPOINT
    assert recorded.data == cf.graphql_request().body_json.encode("utf-8")
    lowered = {str(name).lower() for name in recorded.headers}
    assert sum(1 for name in lowered if name == "x-csrf-token") == 1
    assert "cookie" not in lowered
    assert response.http_status == 200
    assert response.body_text == cf.TRANSPORT_SENTINELS[2]


@pytest.mark.lreq("LREQ-CLI-010")
def test_run_command_constructs_production_transports_when_not_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no transport is injected the CLI builds the production ones.

    ``collector_coveo.CoveoUrlOpener`` is the production Coveo transport and
    ``cli.build_graphql_transport`` the production GraphQL callable; the fake
    builders record construction without any live I/O.
    """
    built: dict[str, float] = {}

    def fake_graphql(*, timeout_seconds: float = 30.0):
        built["graphql_timeout"] = timeout_seconds
        return lambda request, headers: None

    class _FakeOpener:
        def __init__(self, *, timeout_seconds: float = 30.0) -> None:
            built["coveo_timeout"] = timeout_seconds

    from niche_scout import collector_coveo

    monkeypatch.setattr(cli, "build_graphql_transport", fake_graphql)
    monkeypatch.setattr(collector_coveo, "CoveoUrlOpener", _FakeOpener)

    cli._build_coveo_transport()
    cli.build_graphql_transport()

    assert set(built) == {"graphql_timeout", "coveo_timeout"}


# --------------------------------------------------------------------------
# Parser surface — two subcommands, ``None`` defaults, no ``--latest``.
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-CLI-020")
def test_parser_exposes_two_subcommands_with_none_defaults() -> None:
    """The parser exposes ``run``/``dashboard`` and no ``--latest``.

    Unset options are ``None`` so ``load_config`` sees absence; ``dashboard``
    accepts ``--run-id``; ``run`` exposes no ``--page-size`` override point.
    """
    parser = cli.build_parser()
    options = _action_option_strings(parser)
    assert "--categories" in options
    assert "--config" in options
    assert "--report" in options
    assert "--report-format" in options
    assert "--run-id" in options
    assert "--latest" not in options
    assert "--page-size" not in options

    parsed = cli.parse_options(["dashboard", "--run-id", "run-1"])
    assert parsed.run_id == "run-1"
    assert parsed.report_path is None
    assert parsed.report_format == "html"


@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-CLI-020")
def test_module_entry_point_is_reachable() -> None:
    """``python -m niche_scout`` resolves to ``cli.main`` (Ruling 2)."""
    module = importlib.import_module("niche_scout.__main__")
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "from .cli import main" in source
    assert "SystemExit(main())" in source
    _ = sys  # ``__main__`` raises SystemExit; this module never calls sys.exit.
