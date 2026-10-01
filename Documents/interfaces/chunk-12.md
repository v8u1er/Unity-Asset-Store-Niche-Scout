# Chunk 12 — CLI commands and configuration precedence (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-12-cli-commands-and-configuration-precedence.md` §5 (`Status: FROZEN`, 2026-09-22, as frozen after the lead rulings recorded in §12), reproduced as the frozen public contract.
Implementation: `src/niche_scout/cli.py` (the one-line stub is replaced), new `src/niche_scout/__main__.py`, and the `[project.scripts]` entry in `pyproject.toml`.

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/cli.py` | **I/O + orchestration** | Argument parsing, process exit, credentials via `config.get_credentials`, repository/transport construction, calling `pipeline.run_pipeline` and the Chunk 11 renderer. May import `config`, `database`, `pipeline`, `report`, `models`, `urllib.request`, and the collector transport modules. Never reads the environment except through `config.get_credentials`; never reads credentials from a file or `argv`; never restates a frozen numeric constant. |
| `src/niche_scout/__main__.py` | entry point | `raise SystemExit(main())` so `python -m niche_scout` reaches `cli.main`. |
| `pyproject.toml` | packaging | `[project.scripts] niche-scout = "niche_scout.cli:main"`. |

`report.py` SHALL NOT import `cli.py`, so the `cli -> report` edge stays one-directional and no report/CLI cycle exists. No source file outside the Chunk 12 plan §6 table was touched; `database.py` was not touched (Ruling 3 adds no repository read).

## 2. Constants

```python
PROG: str = "niche-scout"

EXIT_OK: int = 0              # completed run, including an 8-20 category provisional run
EXIT_RUNTIME_ERROR: int = 1   # every runtime failure, including a preflight-failed run
EXIT_USAGE_ERROR: int = 2     # argparse-compatible usage or configuration error
```

## 3. Exception surface

```python
class CliError(RuntimeError): ...
```

Raised on a value-domain argument/usage failure (e.g. blank `--run-id`, out-of-domain `--report-format`). Its message never contains a secret.

## 4. Public types

```python
@dataclass(frozen=True, slots=True)
class CliOptions:
    categories_path: Path
    config_path: Path
    db_path: Path            # from resolved config; no --db flag (Ruling 7 A1)
    run_id: str | None       # dashboard: --run-id, required (Ruling 3)
    report_path: Path | None # run: render only when provided (Ruling 5)
    report_format: str       # "html" | "text"; default "html" (Ruling 5)
    config_overrides: Mapping[str, Any] = field(default_factory=dict)
```

`config_overrides` is the carrier for supplied-ness: it holds only the SRS §14
"Configurable? Yes" numeric settings the user actually passed, keyed by their
frozen `NicheScoutConfig` field names. An unset option is absent, so
`resolve_config` can never pass an in-code default as a CLI override
(`LREQ-CLI-030`, `interfaces/chunk-00.md` §5). The six fields above keep the
plan §5 names and semantics; this mapping is the addition that carries
supplied-ness and the supplied values.

## 5. Public functions

```python
def build_parser() -> argparse.ArgumentParser:
    """Parser with `run` and `dashboard`. Unset options default to None so
    `load_config` sees absence. `dashboard` requires `--run-id` (no default, no
    `--latest`). `run` accepts `--report PATH` and `--report-format html|text`
    (default html). Exposes the SRS §14 configurable numeric settings as
    overrides; `--page-size`/`--min-categories-per-run`/
    `--strong-reference-category-count` are not exposed."""

def parse_options(argv: Sequence[str]) -> CliOptions:
    """Parse at the argparse level. Raises `SystemExit` on argparse usage error
    (exit code 2) and `CliError` on a value-domain error. Reads no clock,
    environment, network, or database."""

def resolve_config(
    options: CliOptions, *, environ: Mapping[str, str] | None = None
) -> config.NicheScoutConfig:
    """Call `load_config(cli_args=<options.config_overrides>, toml_path=options.config_path)`.
    Keys the user did not pass are absent, never the in-code default.
    `environ` is accepted for symmetry and is never read here."""

def build_graphql_transport(*, timeout_seconds: float = 30.0) -> GraphQLTransport:
    """Compose the production GraphQL callable in `cli.py` from stdlib
    `urllib.request`. Sends `request.body_json` to `request.endpoint` with the
    caller-supplied headers (the frozen `X-CSRF-Token` header only), reads the
    response body to text, and returns a
    `collector_graphql.GraphQLBatchResponse(http_status, body_text, header_names)`.
    Adds no `Cookie` header, reads no environment variable, and claims no
    CSRF/session sufficiency (Ruling 1; OI-6 open and unassigned)."""

def run_command(
    options: CliOptions, *,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = _utcnow,
    sleeper: Callable[[float], None] = time.sleep,
    coveo_transport: CoveoTransport | None = None,
    graphql_transport: GraphQLTransport | None = None,
    open_repository: Callable[[Path], SqliteRepository] = SqliteRepository,
    write_report: Callable[..., Path] = report.write_run_report,
    template_path: Path | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run one pipeline and return the process exit code. Credentials are read
    via `get_credentials(environ)` before any transport is used. When
    `coveo_transport`/`graphql_transport` are None the production transports are
    constructed, so tests inject recorders and the CLI uses the live ones.

    Exit codes (Ruling 4): `EXIT_OK` when `PipelineResult.succeeded` (including an
    8-20 provisional run); `EXIT_RUNTIME_ERROR` for every runtime failure,
    including a preflight-failed run that `run_pipeline` returned normally with
    `status == failed`; `EXIT_USAGE_ERROR` for configuration/taxonomy errors.
    Redacted `limitations` are written to `stderr`. The renderer runs only after
    a successful `run_pipeline` return and only when `options.report_path` is
    set.

    `write_report`, `open_repository`, and `template_path` are injection seams;
    production callers never pass them. A repository opened through the injected
    `open_repository` seam is caller-owned and is not closed here (the same
    discipline as `dashboard_command`)."""

def dashboard_command(
    options: CliOptions, *,
    repository: SqliteRepository | None = None,
    open_repository: Callable[[Path], SqliteRepository] = SqliteRepository,
    report_renderer: Callable[[Any, str], str] = report.render_dashboard_html,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Use `options.run_id` (required, Ruling 3), call
    `report.render_dashboard_html(repository, run_id)`, and print the returned
    HTML to stdout (Ruling 6) with no file write and no browser launch. Database
    reads only; no transport is constructed and no discovery/enrichment is
    initiated. A missing/blank run id and `RunNotFoundError` exit non-zero."""

def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to `run_command` or `dashboard_command`; return the exit code.
    Never calls `sys.exit` itself. `--help` returns `EXIT_OK`; no subcommand or
    an unrecognized one is a usage error and performs no pipeline or report
    call."""
```

## 6. Behavioral contract (frozen)

- `main(["--help"])` prints usage and returns `EXIT_OK`; `main([])` and an
  unknown subcommand return `EXIT_USAGE_ERROR` with no pipeline or report call.
- `dashboard` without `--run-id` is an argparse usage error (exit 2) and calls
  no renderer.
- `run` with fewer than `MIN_CATEGORIES_PER_RUN` requested categories returns
  `EXIT_USAGE_ERROR` because `run_pipeline` raises `PipelineConfigurationError`;
  the CLI ranks nothing, writes no report, and touches no transport.
- Exit codes are keyed on `PipelineResult.succeeded`: a completed run (including
  an 8-20 category provisional run) returns `EXIT_OK`; a preflight-failed run
  returns `EXIT_RUNTIME_ERROR` even though `run_pipeline` returned normally.
- The production GraphQL callable sends the frozen `X-CSRF-Token` header only;
  no `Cookie` header is added and no CSRF/session sufficiency is claimed.
- `run`/`dashboard` never print a credential, header value, cookie, or response
  body; limitations are the pipeline's already-redacted strings, passed through
  to `stderr` without coercing `None`.
- The process exit code is not stored on the run row and never overwrites the
  persisted `runs.status`.

## 7. What downstream chunks may rely on

- The two SRS-named commands exist: `niche-scout run` and `niche-scout dashboard`
  (console script and `python -m niche_scout`).
- `cli.main(argv) -> int` is the process entry point and never calls `sys.exit`
  itself.
- Chunk 13 may extend the traceability validator's required set to include
  `tests/test_cli.py`; every node already carries an `@pytest.mark.lreq` marker
  and a `tests/traceability.json` entry.

## 8. Open obligations (recorded, not resolved)

- **OI-6 (CSRF/session sufficiency)** remains open and unassigned
  (dependency-map §7). Chunk 12 sends the frozen `X-CSRF-Token` header and adds
  no `Cookie`; it makes no sufficiency claim.
- **URI trailing-identifier extraction (identity mapping rule 1.0.1)** is
  untouched by Chunk 12 (dependency-map §6.4).
- **`runs.taxonomy_sha256` empty-hash rejection** is Chunk 10-owned and unchanged
  by this chunk.

## 9. Chunk 30 revision — optional `--run-id` (2026-09-30)

Operator-authorized (chunk-30 D-3; plan
`chunk-30-dark-mode-plotly-dashboard.md` §2/§12). This deliberately **amends
Ruling 3**; Ruling 6 (stdout, no file write, no browser) is retained.

- **`CliOptions.run_id` (§4)** is now the **optional** dashboard selector:
  `--run-id`, or the most recent run by `run_started_at_utc` when absent.
- **`build_parser` (§5).** `dashboard --run-id` is `required=False`,
  `default=None` (still no `--latest`).
- **`dashboard_command` (§5).** When `options.run_id` is `None`, resolve
  `repository.get_latest_run_id()`; if that is `None` (empty `runs` table), print a
  redacted error to `stderr` and return `EXIT_RUNTIME_ERROR` without calling the
  renderer; otherwise call `report_renderer(repository, str(run_id))` as today. A
  given-but-unknown run id still maps `RunNotFoundError` to `EXIT_RUNTIME_ERROR`.
- **Behavioral contract (§6).** The bullet "`dashboard` without `--run-id` is an
  argparse usage error (exit 2)" is superseded: an absent `--run-id` selects the
  most recent run; an empty `runs` table is a runtime failure.
- **§1 note.** `database.py` is now touched by this chunk (adds
  `get_latest_run_id`; see `chunk-00.md` §12 and `chunk-02.md` §8), superseding the
  "`database.py` was not touched" sentence.

## 10. Chunk 31 revision — dashboard serves a local app (2026-10-01)

Operator-authorized (chunk-31 D-2, R7; plan
`chunk-31-dash-plotly-dashboard.md` §6.2/§12). This section **amends Ruling 6**.

- **`dashboard_command` (§5).** Keeps its parameter names; the `report_renderer`
  seam becomes an **app factory** `Callable[[RunReportView], dash.Dash]` defaulting
  to `report.build_dashboard_app`. The command loads the view once
  (`load_run_report_view`), builds the app, then calls
  `run_dashboard(app, stdout=stdout)`. The read-once, read-only, no-transport
  property (`LREQ-CLI-020`) is unchanged.
- **New function.**
  `run_dashboard(app, *, host="127.0.0.1", port=_DEFAULT_DASHBOARD_PORT,
  stdout=sys.stdout) -> int` binds loopback, prints the local URL to `stdout`,
  blocks, and launches no browser. `KeyboardInterrupt` after a successful bind →
  `EXIT_OK`; bind failure → `EXIT_RUNTIME_ERROR`. Production only; tests replace it
  with a recorder and never bind.
- **Behavioral contract (§6).** The Ruling 6 wording "print to `stdout`, no file
  write, no browser launch" is superseded: the command binds loopback, prints the
  **URL** (not the HTML) to `stdout`, performs no file write, and launches no
  browser. A missing/unknown run, an empty `runs` table, or an open failure still
  maps to `EXIT_RUNTIME_ERROR` and calls neither the renderer nor `run_dashboard`.
  No new option (no `--out`).
- **§4 `CliOptions`** unchanged; `run_id` remains the optional selector (§9).
- **§8 open obligations** unchanged (OI-6 stays open and unassigned).
