"""Command-line boundary: argument parsing, dispatch, and exit-code mapping.

This module is **I/O + orchestration**. It resolves configuration through the
frozen ``config.load_config`` hierarchy (CLI > TOML > in-code defaults), reads
credentials through ``config.get_credentials`` before any transport is used,
opens the repository, invokes ``pipeline.run_pipeline`` exactly once, and maps
the run outcome to a process exit code. It never reads the environment itself,
never reads credentials from a file or ``argv``, and never restates a frozen
numeric constant (``MIN_CATEGORIES_PER_RUN``, ``PAGE_SIZE``, sampling constants,
composite weights): those stay owned by ``models`` and ``config``.

``dashboard`` reads one persisted run through the Chunk 11 read-only renderer and
prints the HTML to stdout. It constructs no transport and initiates no discovery
or enrichment (``LREQ-CLI-020``).

The production GraphQL transport callable is composed here from the frozen
``collector_graphql.build_graphql_batch_request``, ``build_graphql_headers`` and
``GraphQLBatchResponse`` using the standard library. It sends the frozen
``X-CSRF-Token`` header only: it adds **no** ``Cookie`` header, reads no
environment variable, and makes no CSRF/session sufficiency claim (open item
OI-6 stays open and unassigned).

``report.py`` SHALL NOT import this module, so the ``cli -> report`` edge stays
one-directional and no report/CLI cycle exists.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from . import config, database, pipeline, report

PROG: str = "niche-scout"

EXIT_OK: int = 0
"""Completed run, including an 8-20 category provisional run."""

EXIT_RUNTIME_ERROR: int = 1
"""Every runtime failure, including a preflight-failed run."""

EXIT_USAGE_ERROR: int = 2
"""argparse-compatible usage or configuration error."""

_DEFAULT_GRAPHQL_TIMEOUT_SECONDS: float = 30.0

#: The logger root every package module nests under (``niche_scout.pipeline``
#: is ``logging.getLogger("niche_scout.pipeline")``).
_LOGGER_ROOT: str = "niche_scout"

#: Concise, single-line production format: level, logger, message.
_LOG_FORMAT: str = "%(levelname)s %(name)s: %(message)s"

#: Marker attribute set on the handler this helper installs, so a repeated call
#: can recognize and replace its own handler instead of duplicating it.
_HANDLER_MARKER: str = "_niche_scout_logging_handler"


def _configure_logging(stream: TextIO | None = None) -> None:
    """Attach exactly one INFO ``StreamHandler`` to the ``niche_scout`` logger.

    ``stream`` defaults to the *current* ``sys.stderr``, resolved at call time so
    a caller's captured buffer is honoured. Idempotent: any handler this function
    previously installed is removed before the new one is added, so repeated calls
    leave exactly one marked handler. Called from :func:`main` only — never from
    :func:`run_command` or :func:`dashboard_command` — so direct-call test seams
    stay silent. Reads no environment variable and defines no verbosity flag
    (SRS §10 names none).
    """
    logger = logging.getLogger(_LOGGER_ROOT)
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr if stream is None else stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    setattr(handler, _HANDLER_MARKER, True)
    logger.addHandler(handler)


#: The documented in-code default database path, used as a pre-parse placeholder
#: only. The authoritative value comes from the resolved configuration or the
#: injected ``open_repository`` test seam.
_PLACEHOLDER_DB_PATH: Path = config.DEFAULT_DB_PATH

#: The numeric configuration settings SRS §14 marks configurable (``Yes``). Each
#: is exposed as a CLI override; an unset option stays ``None`` and is therefore
#: absent from ``cli_args`` so it cannot shadow TOML or an in-code default.
#: ``page_size``, ``min_categories_per_run``, and
#: ``strong_reference_category_count`` are excluded because the SRS marks them
#: non-configurable, and ``db_path`` has no flag (Ruling 7 A1).
_INT_CONFIG_OVERRIDE_FIELDS: tuple[str, ...] = (
    "max_discovery_results_per_category",
    "max_taxonomy_age_days",
    "min_usable_samples_per_stratum",
    "min_age_days_for_rate",
    "recent_window_days",
    "quality_min_rating_count",
    "quality_min_eligible_assets",
    "identity_preflight_min_categories",
    "identity_preflight_assets_per_category",
)

_FLOAT_CONFIG_OVERRIDE_FIELDS: tuple[str, ...] = (
    "identity_preflight_min_success_rate",
)


class CliError(RuntimeError):
    """An argument/usage or wiring failure (never a secret-bearing message)."""


@dataclass(frozen=True, slots=True)
class CliOptions:
    """The parsed command options.

    ``db_path`` is carried for the dashboard path and as the run path's
    repository target; production parsing fills a placeholder and ``run_command``
    resolves the rest of the configuration through ``load_config`` (plan §12 A1).

    ``config_overrides`` carries only the configuration settings the user
    actually supplied, keyed by their frozen ``NicheScoutConfig`` field names.
    An unset option is absent, so ``resolve_config`` can never pass the in-code
    default as a CLI override (``LREQ-CLI-030``, chunk-00 §5). The six documented
    plan §5 fields keep their names and semantics; this mapping is the addition
    that carries supplied-ness and the supplied values.
    """

    categories_path: Path
    config_path: Path
    db_path: Path
    run_id: str | None
    report_path: Path | None
    report_format: str
    config_overrides: Mapping[str, Any] = field(default_factory=dict)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """Add the two CLI-level path options shared by both subcommands."""
    parser.add_argument(
        "--categories",
        dest="categories_path",
        type=Path,
        default=None,
        help="JSON category selection file (default: config/categories.json)",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        type=Path,
        default=None,
        help="TOML configuration file (default: config/default.toml)",
    )


def _add_config_override_options(parser: argparse.ArgumentParser) -> None:
    """Add one CLI override flag per SRS §14-configurable setting.

    Every flag defaults to ``None`` so an unset option is absent from
    ``load_config``. ``--page-size`` and the other non-configurable constants are
    deliberately not exposed (plan §5, §11).
    """
    for name in _INT_CONFIG_OVERRIDE_FIELDS:
        parser.add_argument(
            "--" + name.replace("_", "-"),
            dest=name,
            type=int,
            default=None,
            help=f"override the {name} configuration setting",
        )
    for name in _FLOAT_CONFIG_OVERRIDE_FIELDS:
        parser.add_argument(
            "--" + name.replace("_", "-"),
            dest=name,
            type=float,
            default=None,
            help=f"override the {name} configuration setting",
        )


def build_parser() -> argparse.ArgumentParser:
    """Return the ``niche-scout`` parser with ``run`` and ``dashboard``.

    Unset options default to ``None`` so ``load_config`` sees absence and no
    in-code default can be shadowed (chunk-00 §5). ``--page-size`` is not
    exposed as an override point; the frozen 96 validation stays in
    ``load_config``. ``dashboard`` requires ``--run-id``: no default and no
    ``--latest`` (Ruling 3). ``run`` accepts ``--report PATH`` and
    ``--report-format html|text`` (default ``html``, Ruling 5).
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Sample-based, deterministic, within-run heuristic category scoring "
            "for the Unity Asset Store. Not a demand or revenue predictor."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="{run,dashboard}")

    run_parser = subparsers.add_parser(
        "run", help="run one discovery and scoring pipeline"
    )
    _add_common_options(run_parser)
    _add_config_override_options(run_parser)
    run_parser.add_argument(
        "--report",
        dest="report_path",
        type=Path,
        default=None,
        help="write one HTML/text run report to this path after completion",
    )
    run_parser.add_argument(
        "--report-format",
        dest="report_format",
        choices=("html", "text"),
        default=None,
        help="report format when --report is given (default: html)",
    )

    dashboard_parser = subparsers.add_parser(
        "dashboard", help="render one persisted run to stdout"
    )
    _add_common_options(dashboard_parser)
    _add_config_override_options(dashboard_parser)
    dashboard_parser.add_argument(
        "--run-id",
        dest="run_id",
        required=True,
        default=None,
        help="the persisted run to render (required; no default)",
    )

    return parser


def _options_from_namespace(namespace: argparse.Namespace) -> CliOptions:
    """Build ``CliOptions`` from a parsed namespace, recording supplied settings.

    Only options whose parsed value is not ``None`` become ``config_overrides``
    entries, so an unset option is absent from ``cli_args`` and cannot shadow a
    TOML value or an in-code default (``LREQ-CLI-030``).
    """
    categories_path = getattr(namespace, "categories_path", None)
    config_path = getattr(namespace, "config_path", None)
    run_id = getattr(namespace, "run_id", None)
    report_path = getattr(namespace, "report_path", None)
    report_format = getattr(namespace, "report_format", None)

    overrides: dict[str, Any] = {}
    if categories_path is not None:
        overrides["categories_path"] = Path(categories_path)
    for name in _INT_CONFIG_OVERRIDE_FIELDS:
        value = getattr(namespace, name, None)
        if value is not None:
            overrides[name] = int(value)
    for name in _FLOAT_CONFIG_OVERRIDE_FIELDS:
        value = getattr(namespace, name, None)
        if value is not None:
            overrides[name] = float(value)

    if run_id is not None and (not isinstance(run_id, str) or not str(run_id).strip()):
        raise CliError("--run-id must be a non-empty run identifier")
    if report_format is not None and report_format not in ("html", "text"):
        raise CliError("--report-format must be 'html' or 'text'")

    return CliOptions(
        categories_path=(
            Path(categories_path)
            if categories_path is not None
            else config.DEFAULT_CATEGORIES_PATH
        ),
        config_path=(
            Path(config_path) if config_path is not None else config.DEFAULT_TOML_PATH
        ),
        db_path=_PLACEHOLDER_DB_PATH,
        run_id=None if run_id is None else str(run_id),
        report_path=None if report_path is None else Path(report_path),
        report_format="html" if report_format is None else str(report_format),
        config_overrides=overrides,
    )


def parse_options(argv: Sequence[str]) -> CliOptions:
    """Parse ``argv`` at the argparse level and return the options.

    Raises argparse's ``SystemExit`` on a usage error and :class:`CliError` on a
    value-domain error. It reads no clock, environment, network, or database.
    """
    parser = build_parser()
    namespace = parser.parse_args(list(argv))
    return _options_from_namespace(namespace)


def resolve_config(
    options: CliOptions, *, environ: Mapping[str, str] | None = None
) -> config.NicheScoutConfig:
    """Resolve configuration through ``load_config`` with explicit overrides only.

    ``cli_args`` carries solely the keys the user passed and resolved to a
    value, so an unset option is absent and can never shadow a TOML value or a
    default (``LREQ-CLI-030``, chunk-00 §5). ``environ`` is accepted for
    symmetry with :func:`run_command` and is never read here; reading the
    environment is ``get_credentials``' responsibility.
    """
    _ = environ
    overrides = dict(options.config_overrides)
    return config.load_config(cli_args=overrides, toml_path=Path(options.config_path))


def build_graphql_transport(
    *, timeout_seconds: float = _DEFAULT_GRAPHQL_TIMEOUT_SECONDS
) -> Callable[..., Any]:
    """Compose the production GraphQL transport callable from ``urllib.request``.

    For each call it sends ``request.body_json`` (UTF-8) to ``request.endpoint``
    with exactly the caller-supplied headers — the frozen ``X-CSRF-Token``
    header only — reads the response body to text, and returns
    ``collector_graphql.GraphQLBatchResponse(http_status, body_text,
    header_names)``. It adds no ``Cookie`` header, reads no environment
    variable, and makes no CSRF/session sufficiency claim (Ruling 1; OI-6 stays
    open and unassigned).
    """
    from . import collector_graphql

    def send(request: Any, headers: Mapping[str, str]) -> Any:
        payload = str(getattr(request, "body_json", "")).encode("utf-8")
        endpoint = str(getattr(request, "endpoint", ""))
        http_request = urllib.request.Request(
            endpoint, data=payload, headers=dict(headers), method="POST"
        )
        with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            body_text = response.read().decode("utf-8")
            header_names = tuple(
                str(name) for name in (getattr(response, "headers", {}) or {})
            )
        return collector_graphql.GraphQLBatchResponse(
            http_status=status,
            body_text=body_text,
            header_names=header_names,
        )

    return send


def _utcnow() -> datetime:
    """Return a timezone-aware UTC instant: the default, injectable clock seam."""
    return datetime.now(timezone.utc)


def run_command(
    options: CliOptions,
    *,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = _utcnow,
    sleeper: Callable[[float], None] = time.sleep,
    coveo_transport: Any | None = None,
    graphql_transport: Any | None = None,
    template_path: Path | None = None,
    open_repository: Callable[[Path], database.SqliteRepository] = (
        database.SqliteRepository
    ),
    write_report: Callable[..., Path] = report.write_run_report,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run one pipeline and return the process exit code.

    Credentials are read via ``get_credentials(environ)`` before any transport is
    used. When ``coveo_transport`` / ``graphql_transport`` are ``None`` the
    production transports are constructed, so tests inject recorders and the CLI
    uses the live ones. Exit codes (Ruling 4): ``EXIT_OK`` when
    ``PipelineResult.succeeded`` (including an 8-20 category provisional run);
    ``EXIT_RUNTIME_ERROR`` for every runtime failure, including a preflight-failed
    run that ``run_pipeline`` returned normally with ``status == failed``;
    ``EXIT_USAGE_ERROR`` for configuration/taxonomy errors. Redacted
    ``limitations`` are written to ``stderr``. The renderer runs only after a
    successful ``run_pipeline`` return and only when ``options.report_path`` is
    set.

    The repository is closed only when this function opened it through the
    production ``SqliteRepository``; an injected ``open_repository`` factory is a
    test seam whose repository the caller owns (``dashboard_command`` follows the
    same discipline). ``write_report`` is an injection seam defaulting to
    ``report.write_run_report``; production callers never pass it.
    ``template_path`` is a test seam for the run-local Coveo template; production
    callers leave it ``None`` so ``run_pipeline`` uses its frozen default.
    """
    _ = stdout
    try:
        resolved = resolve_config(options, environ=environ)
        categories = tuple(config.read_categories(Path(options.categories_path)))
        credentials = config.get_credentials(environ)
    except ValueError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_USAGE_ERROR

    owns_repository = open_repository is database.SqliteRepository
    try:
        repository = open_repository(Path(options.db_path))
    except (OSError, database.DatabaseError) as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_RUNTIME_ERROR

    try:
        coveo = (
            coveo_transport if coveo_transport is not None else _build_coveo_transport()
        )
        graphql = (
            graphql_transport
            if graphql_transport is not None
            else build_graphql_transport()
        )
        run_kwargs: dict[str, Any] = {
            "config": resolved,
            "categories": categories,
            "credentials": credentials,
            "repository": repository,
            "clock": clock,
            "coveo_transport": coveo,
            "graphql_transport": graphql,
            "sleeper": sleeper,
            "run_id": options.run_id,
            "taxonomy_path": Path(resolved.taxonomy_path),
        }
        if template_path is not None:
            run_kwargs["template_path"] = template_path
        pipeline_result = pipeline.run_pipeline(**run_kwargs)
        for limitation in pipeline_result.limitations:
            print(limitation, file=stderr)
        if options.report_path is not None and pipeline_result.succeeded:
            written = write_report(
                repository,
                pipeline_result.run_id,
                Path(options.report_path),
                fmt=options.report_format,
            )
            print(written, file=stderr)
    except (pipeline.PipelineConfigurationError, pipeline.TaxonomyInvalidError) as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_USAGE_ERROR
    except pipeline.PipelineError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_RUNTIME_ERROR
    except report.ReportError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_RUNTIME_ERROR
    except (OSError, urllib.error.URLError, database.DatabaseError) as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_RUNTIME_ERROR
    finally:
        if owns_repository:
            try:
                repository.close()
            except database.DatabaseError:
                pass

    return EXIT_OK if pipeline_result.succeeded else EXIT_RUNTIME_ERROR


def dashboard_command(
    options: CliOptions,
    *,
    repository: database.SqliteRepository | None = None,
    open_repository: Callable[[Path], database.SqliteRepository] = (
        database.SqliteRepository
    ),
    report_renderer: Callable[[Any, str], str] = report.render_dashboard_html,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Render one persisted run through the read-only dashboard renderer.

    ``options.run_id`` is required; a missing or blank id is a usage error
    (``EXIT_USAGE_ERROR``) and calls no renderer (Ruling 3). Otherwise
    ``report_renderer(repository, run_id)`` is called once and its HTML printed
    to ``stdout`` — no file write and no browser launch (Ruling 6). Database
    reads only: no transport is constructed and no discovery or enrichment is
    initiated. ``RunNotFoundError`` is a runtime failure.

    ``report_renderer`` is an injection seam that defaults to
    ``report.render_dashboard_html``; production callers never pass it.
    """
    run_id = options.run_id
    if run_id is None or not str(run_id).strip():
        print("error: --run-id is required", file=stderr)
        return EXIT_USAGE_ERROR

    owns_repository = repository is None
    if repository is None:
        try:
            repository = open_repository(Path(options.db_path))
        except (OSError, database.DatabaseError) as exc:
            print(f"error: {exc}", file=stderr)
            return EXIT_RUNTIME_ERROR
    try:
        html = report_renderer(repository, str(run_id))
    except report.ReportError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_RUNTIME_ERROR
    except (OSError, database.DatabaseError) as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_RUNTIME_ERROR
    finally:
        if owns_repository:
            try:
                repository.close()
            except database.DatabaseError:
                pass

    print(html, file=stdout)
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to :func:`run_command` or :func:`dashboard_command`.

    Returns the exit code and never calls ``sys.exit`` itself. ``--help`` prints
    usage and returns ``EXIT_OK``; no subcommand or an unrecognized one is a
    usage error and performs no pipeline or report call.
    """
    _configure_logging()
    parser = build_parser()
    try:
        namespace = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    except SystemExit as exc:
        return EXIT_OK if exc.code in (0, None) else EXIT_USAGE_ERROR

    try:
        options = _options_from_namespace(namespace)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    command = getattr(namespace, "command", None)
    if command == "run":
        return run_command(options)
    if command == "dashboard":
        return dashboard_command(options)
    print(
        f"error: a subcommand is required ('{PROG} run' or '{PROG} dashboard')",
        file=sys.stderr,
    )
    return EXIT_USAGE_ERROR


def _build_coveo_transport() -> Any:
    """Construct the production Coveo transport (the frozen Chunk 3 opener)."""
    from . import collector_coveo

    return collector_coveo.CoveoUrlOpener()
