"""Inert fixtures for the Chunk 12 CLI-command suite.

Data and small construction helpers only: this module contains no assertions and
no logic under test, so a defect in it cannot mask a CLI, precedence, or
exit-code defect.

Sources (read, not paraphrased from memory):

- ``Documents/SRS-lean.md`` §10 (``LREQ-RPT-010``, ``LREQ-CLI-010`` ..
  ``LREQ-CLI-040``), §4.3 (``LREQ-SEC-010``), §13 (``LREQ-TST-080``), and §14
  (the non-configurable ``MIN_CATEGORIES_PER_RUN``).
- ``Documents/plans/chunk-12-cli-commands-and-configuration-precedence.md`` §5
  (proposed public surface), §8 (edge cases), §9 (test plan and golden vectors),
  §12 (Rulings 1-8).
- Frozen interfaces consumed: ``chunk-00.md`` §5, ``chunk-03.md`` §5,
  ``chunk-05.md`` §5.3/§5.4, ``chunk-10.md`` §2-§3, ``chunk-11.md`` §3-§5.

No live network, no real credentials, no ``.env``, no clock read: the clock is a
caller-advanced fixed instant, the transports are in-memory recorders, and every
datetime is a fixed aware-UTC literal. The credential literals are deliberately
non-secret fixture strings.

Golden facts asserted by ``tests/test_cli.py`` (hand-derived, no clock):

- A CLI override wins over both TOML and the in-code default:
  ``--max-discovery-results-per-category 500`` over TOML ``1500`` and default
  ``9000`` resolves to ``500`` with ``source == "cli"``.
- A TOML value wins over the default when the key is absent from ``cli_args``:
  TOML ``min_age_days_for_rate = 45`` resolves to ``45`` with
  ``source == "toml"``.
- A key absent from both resolves to the documented in-code default
  (``recent_window_days == 365``).
- An unset option is absent, never the in-code default: an argparse ``None`` for
  ``recent_window_days`` with TOML ``recent_window_days = 180`` resolves to
  ``180`` (chunk-00 §5).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fixtures import config_fixtures, report_fixtures
from niche_scout import database
from niche_scout.config import NicheScoutConfig

__all__ = [
    "CLI_OVERRIDE_ARGV",
    "CLI_OVERRIDE_EXPECTED",
    "CUSTOM_TOML_BODY",
    "DEFAULT_RECENT_WINDOW_DAYS",
    "DEFAULT_TOML_BODY",
    "DASHBOARD_TOML_BODY",
    "EXPECTED_REPORT_FILENAME",
    "GRAPHQL_ENDPOINT",
    "RecordingRepositoryFactory",
    "RecordingUrllib",
    "ReportRecorder",
    "RecordingWriteReport",
    "TRANSPORT_SENTINELS",
    "UrllibRequest",
    "UrllibResponse",
    "dashboard_app_recorder",
    "dashboard_options",
    "dashboard_repository",
    "empty_repository",
    "graphql_body",
    "graphql_headers",
    "graphql_request",
    "multi_run_dashboard_repository",
    "run_dashboard_recorder",
    "run_options",
    "scenario_artifacts",
    "seed_run",
    "write_categories_file",
    "write_run_config",
    "write_toml_file",
]

# ---------------------------------------------------------------------------
# TOML bodies. DEFAULT_TOML_BODY/CUSTOM_TOML_BODY are reused verbatim from
# ``config_fixtures``; DASHBOARD_TOML_BODY only pins the database path, because
# ``load_config`` rejects an unknown key (chunk-00 §5).
# ---------------------------------------------------------------------------

DEFAULT_TOML_BODY: str = config_fixtures.DEFAULT_TOML_BODY
CUSTOM_TOML_BODY: str = config_fixtures.CUSTOM_TOML_BODY
DASHBOARD_TOML_BODY: str = 'db_path = "runtime/dashboard.sqlite3"'

#: The documented in-code default for ``recent_window_days`` (chunk-00 §5).
DEFAULT_RECENT_WINDOW_DAYS = 365

#: The golden CLI override table (plan §9): value 500 over TOML 1500 over
#: in-code default 9000.
CLI_OVERRIDE_ARGV: tuple[str, ...] = ("--max-discovery-results-per-category", "500")
CLI_OVERRIDE_EXPECTED = 500

EXPECTED_REPORT_FILENAME = "report.html"

#: Sentinel strings that must never appear on the CLI's stdout/stderr
#: (LREQ-SEC-010/020). They are deliberately non-secret fixture values.
TRANSPORT_SENTINELS: tuple[str, ...] = (
    "fixture-cli-bearer-token",
    "fixture-cli-csrf-token",
    "fixture-cli-response-body",
)


def write_toml_file(directory: Path, body: str, *, name: str) -> Path:
    """Write ``body`` as a TOML file under ``directory`` and return its path."""
    path = Path(directory) / name
    path.write_text(body + "\n", encoding="utf-8")
    return path


def write_categories_file(
    directory: Path, categories: Sequence[str], *, name: str = "categories.json"
) -> Path:
    """Write a bare JSON array of category paths and return its path."""
    path = Path(directory) / name
    path.write_text(json.dumps(list(categories)), encoding="utf-8")
    return path


#: The ``NicheScoutConfig`` fields a run-local TOML fixture serializes, in the
#: order ``load_config`` resolves them. Every value comes from a caller-supplied
#: config object, never from the implementation under test.
_CONFIG_TOML_FIELDS: tuple[str, ...] = (
    "categories_path",
    "taxonomy_path",
    "db_path",
    "max_discovery_results_per_category",
    "page_size",
    "min_categories_per_run",
    "strong_reference_category_count",
    "max_taxonomy_age_days",
    "min_usable_samples_per_stratum",
    "min_age_days_for_rate",
    "recent_window_days",
    "quality_min_rating_count",
    "quality_min_eligible_assets",
    "identity_preflight_min_categories",
    "identity_preflight_assets_per_category",
    "identity_preflight_min_success_rate",
)


def _toml_scalar(value: Any) -> str:
    """Render one config value as a TOML scalar (paths as forward-slash strings)."""
    if isinstance(value, Path):
        return '"' + value.as_posix() + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def write_run_config(
    directory: Path,
    config: NicheScoutConfig,
    *,
    name: str = "cli_scenario.toml",
    **overrides: Any,
) -> Path:
    """Write a run-local TOML carrying every field of ``config``.

    The CLI resolves configuration from this file, so the run-local scenario
    paths, discovery cap, and preflight knobs reach ``run_pipeline`` without any
    live path. ``overrides`` replaces individual fields before writing. Paths use
    forward slashes so a Windows backslash is not read as a TOML escape.
    """
    values = {
        field_name: getattr(config, field_name) for field_name in _CONFIG_TOML_FIELDS
    }
    values.update(overrides)
    body = "\n".join(
        f"{field_name} = {_toml_scalar(values[field_name])}"
        for field_name in _CONFIG_TOML_FIELDS
    )
    return write_toml_file(directory, body, name=name)


# ---------------------------------------------------------------------------
# CliOptions factories. The attribute set is the plan §5 ``CliOptions`` field
# list; the factories build it without importing ``cli`` so a pre-implementation
# collection error cannot cascade.
# ---------------------------------------------------------------------------


def _options(**values: Any) -> Any:
    """Build a ``cli.CliOptions`` with the plan §5 field defaults applied."""
    from niche_scout.cli import CliOptions

    fields = {
        "categories_path": Path("config") / "categories.json",
        "config_path": Path("config") / "default.toml",
        "db_path": Path("runtime") / "niche_scout.sqlite3",
        "run_id": None,
        "report_path": None,
        "report_format": "html",
        "accept_terms": True,
    }
    fields.update(values)
    return CliOptions(**fields)


def run_options(
    categories_path: Path,
    config_path: Path,
    db_path: Path,
    *,
    run_id: str | None = None,
    report_path: Path | None = None,
    report_format: str = "html",
    accept_terms: bool = True,
) -> Any:
    """Return ``run``-shaped options pointing at the temp artifacts."""
    return _options(
        categories_path=categories_path,
        config_path=config_path,
        db_path=db_path,
        run_id=run_id,
        report_path=report_path,
        report_format=report_format,
        accept_terms=accept_terms,
    )


def dashboard_options(config_path: Path, db_path: Path, *, run_id: str | None) -> Any:
    """Return ``dashboard``-shaped options; ``run_id`` is the required selector."""
    return _options(config_path=config_path, db_path=db_path, run_id=run_id)


# ---------------------------------------------------------------------------
# Repository factories and seeders.
# ---------------------------------------------------------------------------


class RecordingRepositoryFactory:
    """A callable ``open_repository`` recording every db path it was given.

    It returns a real ``database.SqliteRepository`` for that path, so the
    injected seam behaves exactly like the production one while exposing
    ``paths`` for assertions and ``last`` for closing/reading.
    """

    def __init__(self) -> None:
        self.paths: list[Path] = []
        self.repositories: list[database.SqliteRepository] = []

    def __call__(self, db_path: Path) -> database.SqliteRepository:
        self.paths.append(Path(db_path))
        repository = database.SqliteRepository(Path(db_path))
        self.repositories.append(repository)
        return repository

    @property
    def last(self) -> database.SqliteRepository:
        return self.repositories[-1]

    def close_all(self) -> None:
        for repository in self.repositories:
            repository.close()


def empty_repository(path: Path) -> database.SqliteRepository:
    """Open a fresh repository at ``path`` (pytest temp; no live path)."""
    return database.SqliteRepository(Path(path))


def seed_run(
    repository: database.SqliteRepository,
    run: Any = None,
    scores: Sequence[Any] = (),
) -> None:
    """Insert one ``runs`` row and optional ``category_scores`` rows."""
    record = run if run is not None else report_fixtures.run_record(("Alpha/Ranked",))
    with repository.transaction():
        repository.insert_run(record)
        if scores:
            repository.insert_category_scores(list(scores))


def dashboard_repository(path: Path, *categories: str) -> database.SqliteRepository:
    """Open a repository seeded with one completed run for the dashboard test."""
    repository = empty_repository(path)
    names = tuple(categories) or (report_fixtures.CATEGORY_ALPHA,)
    rows = (
        report_fixtures.scored_rows_for(names[0], names[-1])
        if len(names) > 1
        else (report_fixtures.category_score_record(names[0]),)
    )
    seed_run(repository, report_fixtures.run_record(names), rows)
    return repository


#: Two fixed, distinct ``run_started_at_utc`` instants for the latest-run test.
EARLIER_RUN_STARTED_AT_UTC = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
LATER_RUN_STARTED_AT_UTC = datetime(2025, 1, 2, 3, 4, 6, tzinfo=timezone.utc)


def multi_run_dashboard_repository(
    path: Path,
    *,
    earlier_run_id: str = "run-earlier",
    later_run_id: str = "run-later",
) -> database.SqliteRepository:
    """Seed two completed runs with distinct fixed start instants.

    Both runs carry one rankable ``Alpha/Ranked`` score row; the later run has
    the greater ``run_started_at_utc``, so ``get_latest_run_id`` selects it. All
    timestamps are fixed aware-UTC literals (no clock read).
    """
    repository = empty_repository(path)
    earlier = report_fixtures.run_record(
        (report_fixtures.CATEGORY_ALPHA,),
        run_id=earlier_run_id,
        run_started_at_utc=EARLIER_RUN_STARTED_AT_UTC,
    )
    later = report_fixtures.run_record(
        (report_fixtures.CATEGORY_ALPHA,),
        run_id=later_run_id,
        run_started_at_utc=LATER_RUN_STARTED_AT_UTC,
    )
    with repository.transaction():
        repository.insert_run(earlier)
        repository.insert_run(later)
        repository.insert_category_scores(
            [
                replace(
                    report_fixtures.category_score_record(
                        report_fixtures.CATEGORY_ALPHA
                    ),
                    run_id=earlier_run_id,
                ),
                replace(
                    report_fixtures.category_score_record(
                        report_fixtures.CATEGORY_ALPHA
                    ),
                    run_id=later_run_id,
                ),
            ]
        )
    return repository


# ---------------------------------------------------------------------------
# Recording urllib seam for ``build_graphql_transport`` (no live network).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UrllibRequest:
    """The recorded shape of one ``urllib.request.Request`` construction."""

    full_url: str
    data: bytes | None
    headers: Mapping[str, str]
    method: str | None


class UrllibResponse:
    """The minimal context-manager response the production callable reads."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = int(status)
        self._body = bytes(body)

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "UrllibResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class RecordingUrllib:
    """A ``urllib.request``-shaped recorder double.

    It exposes ``Request`` and ``urlopen`` so
    ``niche_scout.cli.build_graphql_transport`` can use it without any live
    request. ``calls`` holds the recorded ``UrllibRequest`` values and
    ``urlopen_calls`` the same values, one per opened request.
    """

    def __init__(self, body: bytes = b"{}", *, status: int = 200) -> None:
        self._body = bytes(body)
        self._status = int(status)
        self.requests: list[UrllibRequest] = []
        self.urlopen_calls: list[UrllibRequest] = []
        self.response_headers: Mapping[str, str] = {}

    def Request(
        self,
        url: str,
        data: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        *,
        method: str | None = None,
    ) -> UrllibRequest:
        recorded = UrllibRequest(
            full_url=str(url),
            data=data,
            headers=dict(headers or {}),
            method=method,
        )
        self.requests.append(recorded)
        return recorded

    def urlopen(self, request: UrllibRequest, timeout: float | None = None) -> Any:
        self.urlopen_calls.append(request)
        return UrllibResponse(self._status, self._body)


# ---------------------------------------------------------------------------
# Frozen Chunk 5 request/header values for the transport test.
# ---------------------------------------------------------------------------

#: The frozen batch endpoint (chunk-05 §5.1). Declared locally so this fixture
#: does not import a collector module.
GRAPHQL_ENDPOINT = "https://assetstore.unity.com/api/graphql/batch"


def graphql_body() -> dict[str, Any]:
    """Return a minimal JSON body standing in for ``request.body_json``."""
    return {"operations": ["ProductDetail", "ProductPageViews"]}


def graphql_request() -> Any:
    """Return a minimal object exposing the frozen ``GraphQLBatchRequest`` names."""
    return _RequestDouble(
        asset_identity_key="fixture-asset-0001",
        body_json=json.dumps(graphql_body(), sort_keys=True, separators=(",", ":")),
        endpoint=GRAPHQL_ENDPOINT,
    )


def graphql_headers() -> Mapping[str, str]:
    """Return the caller-supplied header map, with a non-secret value.

    Chunk 17 R1 (option (a)): the adapter's ``build_graphql_headers`` emits both
    the ``x-csrf-token`` header and the matching ``cookie: _csrf=<same value>``.
    This fixture double carries both so ``build_graphql_transport`` can be
    asserted to forward them verbatim. The value is a non-secret fixture literal.
    """
    token = "fixture-cli-csrf-token"
    return {"x-csrf-token": token, "cookie": f"_csrf={token}"}


@dataclass(frozen=True, slots=True)
class _RequestDouble:
    asset_identity_key: str
    body_json: str
    endpoint: str


# ---------------------------------------------------------------------------
# Capturing report-renderer recorder for the injected-reportable seam.
# ---------------------------------------------------------------------------


class ReportRecorder:
    """A callable ``report_renderer`` recording each ``(repository, run_id)``.

    It returns a deterministic HTML string without touching the database or the
    network, so a test can assert *whether* the renderer ran and how often
    (plan §9: the renderer runs only after ``run_pipeline`` returns).
    """

    def __init__(self, html: str = "<html>fixture dashboard</html>") -> None:
        self.html = html
        self.calls: list[tuple[Any, str]] = []

    def __call__(self, repository: Any, run_id: str) -> str:
        self.calls.append((repository, run_id))
        return self.html

    @property
    def call_count(self) -> int:
        return len(self.calls)


@dataclass
class RecordingWriteReport:
    """A callable ``write_report`` recording each invocation and writing HTML.

    The write is local and deterministic: it records ``(repository, run_id,
    output_path, fmt)`` and writes ``html`` to the path so the caller can assert
    the file exists without the renderer recomputing anything.
    """

    html: str = "<html>fixture run report</html>"
    calls: list[tuple[Any, str, Path, str]] = field(default_factory=list)

    def __call__(
        self,
        repository: Any,
        run_id: str,
        output_path: Path,
        *,
        fmt: str = "html",
    ) -> Path:
        self.calls.append((repository, run_id, Path(output_path), fmt))
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.html, encoding="utf-8")
        return path

    @property
    def call_count(self) -> int:
        return len(self.calls)


# ---------------------------------------------------------------------------
# Dashboard app factory and run_dashboard recorders (Chunk 31).
# ---------------------------------------------------------------------------


class DashboardAppRecorder:
    """A callable app factory recording each ``view`` and returning a sentinel.

    The Chunk 31 ``report_renderer`` seam is an app factory ``(view) -> app``;
    this recorder returns a shared ``app`` object without constructing a Dash
    app, so a test can assert *whether* the factory ran, how often, and against
    which loaded view, with no server and no I/O.
    """

    def __init__(self, app: Any | None = None) -> None:
        self.app = app if app is not None else object()
        self.views: list[Any] = []

    def __call__(self, view: Any) -> Any:
        self.views.append(view)
        return self.app

    @property
    def call_count(self) -> int:
        return len(self.views)


def dashboard_app_recorder(app: Any | None = None) -> DashboardAppRecorder:
    """Return a fresh app-factory recorder (plan §9)."""
    return DashboardAppRecorder(app)


class RunDashboardRecorder:
    """A callable ``run_dashboard`` recorder that never binds a server.

    Records ``(app, host, port, stdout)``-style invocations and returns
    ``EXIT_OK`` without serving. Used to monkeypatch ``cli.run_dashboard`` so the
    suite can exercise the command path without binding loopback.
    """

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls: list[Any] = []

    def __call__(self, app: Any, **kwargs: Any) -> int:
        self.calls.append((app, kwargs))
        return self.exit_code

    @property
    def call_count(self) -> int:
        return len(self.calls)


def run_dashboard_recorder(exit_code: int = 0) -> RunDashboardRecorder:
    """Return a fresh ``run_dashboard`` recorder (plan §9)."""
    return RunDashboardRecorder(exit_code)


# ---------------------------------------------------------------------------
# The end-to-end scenario bundle.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioArtifacts:
    """Everything the CLI end-to-end path needs, all under ``tmp_path``."""

    scenario: Any
    config: Any
    template_path: Path
    categories_path: Path
    taxonomy_path: Path
    db_path: Path
    config_path: Path
    run_id: str


def scenario_artifacts(directory: Path, *, run_id: str) -> ScenarioArtifacts:
    """Write the eight-category scenario artifacts under ``directory``.

    Reuses ``pipeline_fixtures`` (the Chunk 10 end-to-end scenario, its
    in-memory transports and its fixed clock) and ``fixture_config`` so no live
    path, network call, or clock read can occur. The config pins
    ``max_discovery_results_per_category`` to the fixture's discovery cap and
    sets a permissive preflight so the run completes without a real taxonomy
    inventory mismatch.
    """
    from fixtures import pipeline_fixtures as pf

    template_path = pf.write_run_local_template(directory, pf.END_TO_END_CATEGORIES)
    scenario = pf.end_to_end_scenario(template_path=template_path)
    categories_path = write_categories_file(directory, scenario.categories)
    taxonomy_path = pf.write_taxonomy(directory, scenario.taxonomy_payload)
    config = pf.fixture_config(
        directory,
        min_categories_per_run=pf.MIN_CATEGORIES,
        max_discovery_results_per_category=pf.SCENARIO_DISCOVERY_CAP,
        identity_preflight_min_categories=1,
        identity_preflight_assets_per_category=1,
        identity_preflight_min_success_rate=0.0,
    )
    config_path = write_run_config(directory, config, name="cli_scenario.toml")
    return ScenarioArtifacts(
        scenario=scenario,
        config=config,
        template_path=template_path,
        categories_path=categories_path,
        taxonomy_path=taxonomy_path,
        db_path=config.db_path,
        config_path=config_path,
        run_id=run_id,
    )
