# Chunk 12 — CLI commands and configuration precedence

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  `Documents/interfaces/chunk-00.md` (VERIFIED), `chunk-01.md` (VERIFIED),
  `chunk-03.md` (VERIFIED, production Coveo transport §5),
  `chunk-05.md` (VERIFIED, production GraphQL request/header builders and
  `GraphQLBatchResponse` §5),
  `chunk-6A.md`, `chunk-6B.md`, `chunk-08.md`, `chunk-10.md` (VERIFIED),
  `chunk-11.md` (VERIFIED).
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 13 (end-to-end CLI acceptance and traceability closure; the validator's
  required-set widening and the import-boundary/secret checks include `cli.py`).

## 1. Goal

Make the two SRS-named commands real: `niche-scout run` resolves configuration
through the frozen CLI > TOML > default hierarchy, rejects a too-small run before
ranking, invokes `pipeline.run_pipeline` exactly once, and maps the run outcome to
a process exit code; `niche-scout dashboard` renders one persisted run through the
Chunk 11 read-only renderer and performs database reads only. This chunk also adds
the run-selection needed by the dashboard and the report-renderer invocation that
completes LREQ-RPT-010's command interface, without introducing a report/CLI
dependency cycle.

## 2. Scope

### In scope

- `src/niche_scout/cli.py`: argument parsing, subcommand dispatch (`run`,
  `dashboard`), the CLI → `load_config` wiring (unset options must not shadow
  TOML/defaults), credential acquisition via `config.get_credentials`, repository
  construction/open, `run_pipeline` invocation, `PipelineResult`/exception →
  exit-code mapping, and surfacing the pipeline's redacted limitations.
- Production GraphQL transport composition: a stdlib `urllib` callable built
  **in `cli.py`** from the frozen `build_graphql_batch_request`,
  `build_graphql_headers`, and `GraphQLBatchResponse` (interfaces/chunk-05.md
  §5). `urllib.request` becomes an explicit `cli.py` import (Ruling 1).
- Report-renderer invocation: `run` may call the Chunk 11 renderer **only after**
  `run_pipeline` returns and **only when `--report PATH` is given**; `dashboard`
  calls `render_dashboard_html` and nothing else that could reach the network
  (Ruling 5).
- Run selection for `dashboard`: `--run-id` is **required**; there is no default
  and no `--latest`, and no new `database.py` read is added (Ruling 3).
- The process entry point that makes the `niche-scout ...` command reachable:
  both `[project.scripts]` in `pyproject.toml` and a new
  `src/niche_scout/__main__.py` (Ruling 2).
- Tests for the four LREQ-CLI requirements and their fixtures/traceability
  entries.

### Explicitly out of scope (and who owns it instead)

- The `run_pipeline` orchestration sequence, run-size rejection, preflight gate,
  and status persistence: **Chunk 10**, the primary implementation chunk for the
  pipeline half of LREQ-CLI-040 (dependency-map §Chunk 10 "Supporting
  orchestration behavior for CLI requirements"). Chunk 12 only maps its outcome
  to an exit code.
- The read model, HTML/text renderers, `render_dashboard_html`,
  `RunNotFoundError`, and all recomputation: **Chunk 11** (primary owner for
  LREQ-RPT-010/020/030/040/050). Chunk 12 is a completion chunk for LREQ-RPT-010's
  command interface and a caller for LREQ-CLI-020.
- Configuration precedence semantics (the `load_config` merge, `None`-is-absent
  rule, unknown-key rejection, `source` reporting): **Chunk 0** (primary owner of
  LREQ-CLI-030; see §3). Chunk 12 consumes `load_config` and must pass explicit
  CLI options, never baked defaults.
- Credential reading/redaction and the environment variable names: **Chunk 0**
  (`get_credentials`, `Credentials.require_for_collection`); Chunk 12 is a
  supporting/completion chunk for LREQ-SEC-010 (dependency map line 68) and must
  not read the environment itself outside `get_credentials`.
- Any change that expands a metric/score/evidence/sensitivity formula, adds a
  GraphQL field, or enables a deferred feature: forbidden by the out-of-scope
  list.
- The traceability validator's required-set widening from Chunk 0 to all chunks,
  golden end-to-end acceptance, secret-scanning, and retired-feature static
  checks: **Chunk 13** (LREQ-TST-080/090, LREQ-NFR-060). Chunk 12 only adds
  markers and matrix entries.

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-CLI-010 | **Primary** (dependency map: primary Chunk 12; supporting Chunk 6A, 6B, 8, 10, 11; completion Chunk 12) | "The primary command SHALL be equivalent to: `niche-scout run --categories config/categories.json --config config/default.toml`. It SHALL run one pipeline and exit non-zero on unrecoverable errors." | §10 |
| LREQ-CLI-020 | **Primary** (primary Chunk 12; supporting Chunk 11; completion Chunk 12) | "The `niche-scout dashboard` command SHALL read the database and SHALL not initiate discovery or enrichment." The dependency map's edge-case cell adds: "No discovery or enrichment network calls; CLI is only a caller of the report renderer." | §10 |
| LREQ-CLI-030 | **Primary** for the command wiring; Chunk 0 is primary for the precedence mechanism (dependency map: primary Chunk 12; supporting Chunk 0; completion Chunk 12) | "CLI options SHALL override TOML configuration, which SHALL override documented in-code defaults." | §10 |
| LREQ-CLI-040 | **Primary** for the exit-code mapping and limitation surfacing; Chunk 10 is primary for the rejection itself (dependency map: primary Chunk 12; supporting Chunk 1, 8, 9A, 10; completion Chunk 12) | "The pipeline SHALL reject a run with fewer than `MIN_CATEGORIES_PER_RUN` requested categories before producing a ranking. It SHALL retain a completed run's collection timestamp and explicit limitations in the report." | §10 |
| LREQ-RPT-010 | **Integration completion** (primary Chunk 11; completion Chunk 12) | "Provide a local read-only HTML report or dashboard launched by one command. The required interface SHALL retain: `niche-scout run --categories config/categories.json --config config/default.toml` / `niche-scout dashboard`." Chunk 11 supplies the renderer; Chunk 12 supplies the command that launches it. | §10 |
| LREQ-SEC-010 | **Supporting / completion** (primary Chunk 0; supporting Chunk 3, 5, 12; completion Chunk 3, 5, 12) | "Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection." Chunk 12's share: call `get_credentials` before any pipeline transport is used, and never read the environment itself. | §4.3 |
| LREQ-TST-080 | Consumed matrix obligation (primary Chunk 13) | Every analytical test carries an `@pytest.mark.lreq` marker and a matching `tests/traceability.json` entry; the validator runs clean. | §13 / dependency-map §6.6 |

`MIN_CATEGORIES_PER_RUN` is the frozen SRS §14 constant: `MIN_CATEGORIES_PER_RUN | 8
| No | Minimum comparison set.` Chunk 12 must not restate it as a CLI-overridable
value; `config.min_categories_per_run` is only the carrier and Chunk 10 rejects on
the frozen `models.MIN_CATEGORIES_PER_RUN` (chunk-10 interface §3).

## 4. Interface contracts consumed

Copied from frozen interfaces; not re-derived from source.

**Chunk 0 — `niche_scout.config` (`interfaces/chunk-00.md` §5):**

- `DEFAULT_TOML_PATH`, `DEFAULT_CATEGORIES_PATH`, `DEFAULT_TAXONOMY_PATH`,
  `DEFAULT_DB_PATH`, `COVEO_TOKEN_ENV`, `UNITY_CSRF_TOKEN_ENV`.
- `load_config(cli_args: Optional[dict[str, Any]] = None, toml_path: Optional[Path] = None) -> NicheScoutConfig`.
  Precedence `cli_args` > `toml_path` > in-code defaults; `None` values in
  `cli_args` are absent; unknown keys and a supplied `source` raise `ValueError`;
  `page_size` is validated against the frozen `PAGE_SIZE`.
- `read_categories(categories_path: Path) -> Sequence[str]` (declared order).
- `get_credentials(environ: Optional[Mapping[str, str]] = None) -> Credentials`;
  calls `require_for_collection()`; raises `ValueError` with no secret in the
  message.
- `NicheScoutConfig` field list and `source: str` (only `"cli" | "toml" | "defaults"`).

**Chunk 0 — `niche_scout.database` (`interfaces/chunk-00.md` §6) and Chunk 10
additions (`interfaces/chunk-10.md` §8):**

- `SqliteRepository(db_path, *, initialize=True, ...)`, `close()`,
  context-manager form.
- `get_run(run_id) -> Optional[RunRecord]`, `get_category_scores(run_id)`, plus
  the read surface the Chunk 11 renderer consumes.
- `update_run_scoring_cutoff(run_id, scoring_cutoff_utc)` (Chunk 10).
- No run-listing method exists in the frozen `Repository` protocol (chunk-11
  interface §8: "Chunk 12 owns run selection; Chunk 11 added no repository
  method").

**Chunk 10 — `niche_scout.pipeline` (`interfaces/chunk-10.md` §2–§5):**

- `run_pipeline(*, config, categories, credentials, repository, clock,
  coveo_transport, graphql_transport, sleeper=time.sleep, run_id=None,
  taxonomy_path=None, template_path=COVEO_TEMPLATE_PATH, correlation_mode=...,
  preflight_policy=None, retry_policy=..., taxonomy_sha256=None) -> PipelineResult`.
- `PipelineResult(run_id, status, scoring_cutoff_utc, categories,
  identity_preflight_status, category_scores_written, limitations)` with
  `succeeded` iff `status == RunStatus.COMPLETED.value`.
- `PipelineError` / `PipelineConfigurationError` / `TaxonomyInvalidError`.
- Semantics relied on: config/taxonomy validated before any network; fewer than
  8 categories rejected with `PipelineConfigurationError`; a `failed`/`insufficient`
  preflight returns `status=failed` (does not raise); `run_pipeline` never calls
  `sys.exit` and never parses `argv`.

**Chunk 11 — `niche_scout.report` (`interfaces/chunk-11.md` §3–§5, §8):**

- `RunNotFoundError`.
- `render_dashboard_html(repository: SqliteRepository, run_id: str) -> str` —
  database reads only; raises `RunNotFoundError`.
- `write_run_report(repository, run_id, output_path, *, fmt="html") -> Path` —
  `fmt` in `{"html","text"}`; `ValueError` otherwise.
- `report.py` must not import `metrics`, `scoring`, `collector*`, `config`,
  `pipeline`, `cli`, or any network module.

**Chunk 3 / Chunk 5 — production transport seams (both used by `cli.py`,
Ruling 1):**

- `collector_coveo.CoveoTransport` protocol `send(url, headers, payload) -> Any`
  with production `CoveoUrlOpener(*, timeout_seconds=30.0)` (chunk-03 §5).
  `cli.py` constructs `CoveoUrlOpener` for the production Coveo transport.
- `collector_graphql.GraphQLTransport = Callable[[GraphQLBatchRequest,
  Mapping[str, str]], GraphQLBatchResponse]` (chunk-05 §5.11); **no production
  implementation of this callable exists anywhere in the repository.** `cli.py`
  composes one from `urllib.request` plus the frozen
  `build_graphql_batch_request` / `build_graphql_headers` /
  `GraphQLBatchResponse`, and sends the frozen `X-CSRF-Token` header only
  (Ruling 1). It adds **no** `Cookie` header and makes **no** CSRF/session
  sufficiency claim; OI-6 (dependency-map §7) stays open and unassigned.

## 5. Interface contract this chunk produces

To become `Documents/interfaces/chunk-12.md` verbatim once frozen, with the
2026-09-22 rulings applied. `urllib.request` is an explicit `cli.py` import; the
production GraphQL transport callable is composed in `cli.py`; `run_id` is
required for `dashboard`; the exit-code map is fixed; `run` renders only on
`--report`; `dashboard` prints to stdout; A1/A2 are retained.

**Module boundary (normative):**

- `src/niche_scout/cli.py` is **I/O + orchestration** (argument parsing, process
  exit, repository/transport construction, calling the pipeline and the renderer).
- `cli.py` may import `config`, `database`, `pipeline`, `report`, `models`,
  `urllib.request`, and the collector transport modules. **`report.py` SHALL NOT
  import `cli.py`**, so the `cli -> report` edge stays one-directional and no
  report/CLI cycle exists.
- The production GraphQL callable lives in `cli.py` and is built from the frozen
  `build_graphql_batch_request`, `build_graphql_headers`, and
  `GraphQLBatchResponse`; `cli.py` sends the frozen `X-CSRF-Token` header only,
  adds no `Cookie` header, and does not claim CSRF/session sufficiency (Ruling 1;
  OI-6 open, unassigned).
- `run` SHALL call `pipeline.run_pipeline` first and SHALL call the report
  renderer only **after** it returns (success) and only when `--report PATH` is
  given — never before, never on the failure path. `dashboard` SHALL call only
  `report.render_dashboard_html` (plus the repository reads inside it) and print
  the returned HTML to stdout (Ruling 6).

**Proposed public surface:**

```python
# src/niche_scout/cli.py
PROG: str = "niche-scout"

EXIT_OK: int = 0             # completed run, including an 8-20 provisional run
EXIT_RUNTIME_ERROR: int = 1  # every runtime failure, incl. a preflight-failed run
EXIT_USAGE_ERROR: int = 2    # argparse-compatible usage/configuration errors

class CliError(RuntimeError): ...          # argument/usage or wiring failure

@dataclass(frozen=True, slots=True)
class CliOptions:
    categories_path: Path
    config_path: Path
    db_path: Path                          # from resolved config, not a separate flag
    run_id: str | None                     # dashboard: --run-id, required (Ruling 3)
    report_path: Path | None               # run: render only when provided (Ruling 5)
    report_format: str                     # "html" | "text"; default "html" (Ruling 5)

def build_parser() -> argparse.ArgumentParser: ...
    """Parser with `run` and `dashboard` subcommands. Unset options default to
    None so `load_config` sees absence (chunk-00 §5); `--page-size` is not
    exposed as an override point beyond the frozen 96 validation.

    `dashboard` requires `--run-id`; there is no default and no `--latest`
    (Ruling 3). `run` accepts `--report PATH` and
    `--report-format html|text` (default `html`, Ruling 5)."""

def parse_options(argv: Sequence[str]) -> CliOptions: ...
    """argparse-level parse; raises `SystemExit`/`CliError` on usage error.
    Must not read the clock, environment, network, or database."""

def resolve_config(
    options: CliOptions, *, environ: Mapping[str, str] | None = None
) -> NicheScoutConfig: ...
    """Call `load_config(cli_args=<explicit overrides only>, toml_path=options.config_path)`.
    Keys the user did not pass SHALL be absent (`None`), never the in-code default."""

def build_graphql_transport(*, timeout_seconds: float = 30.0) -> GraphQLTransport: ...
    """Compose the production GraphQL callable in `cli.py` from stdlib
    `urllib.request`. For each call it sends `request.body_json` to
    `request.endpoint` with the caller-supplied headers (the frozen
    `X-CSRF-Token` header only), reads the response body to text, and returns a
    `GraphQLBatchResponse(http_status, body_text, header_names)`. It SHALL NOT
    add a `Cookie` header, SHALL NOT read the environment, and SHALL NOT claim
    CSRF/session sufficiency (Ruling 1; OI-6 open, unassigned)."""

def run_command(
    options: CliOptions,
    *,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = _utcnow,
    sleeper: Callable[[float], None] = time.sleep,
    coveo_transport: CoveoTransport | None = None,
    graphql_transport: GraphQLTransport | None = None,
    open_repository: Callable[[Path], SqliteRepository] = SqliteRepository,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int: ...
    """Run one pipeline and return the process exit code. Credentials are read
    via `get_credentials(environ)` before any transport is used. When
    `coveo_transport` / `graphql_transport` are None, the production transports
    are constructed (`collection_coveo.CoveoUrlOpener` and
    `build_graphql_transport()`), so tests inject recording fakes and the CLI
    uses live ones. Exit codes (Ruling 4): `EXIT_OK` when
    `PipelineResult.succeeded` (including an 8-20 provisional run);
    `EXIT_RUNTIME_ERROR` for every runtime failure, including a preflight-failed
    run where `run_pipeline` returned normally with `status == failed`;
    `EXIT_USAGE_ERROR` for configuration/taxonomy errors. Configuration or
    taxonomy failure produces no network request and no run row. Redacted
    `limitations` are written to `stderr`. The renderer runs only after a
    successful `run_pipeline` return and only when `options.report_path` is
    set."""

def dashboard_command(
    options: CliOptions,
    *,
    repository: SqliteRepository | None = None,
    open_repository: Callable[[Path], SqliteRepository] = SqliteRepository,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int: ...
    """Use `options.run_id` (required, Ruling 3), call
    `report.render_dashboard_html(repository, run_id)`, and print the returned
    HTML to `stdout` (Ruling 6) with no file write and no browser launch.
    Database reads only; no transport is constructed and no discovery/enrichment
    is initiated. `RunNotFoundError` and a missing `run_id` exit non-zero."""

def main(argv: Sequence[str] | None = None) -> int: ...
    """Dispatch to `run_command` or `dashboard_command`; return the exit code.
    Never calls `sys.exit` itself."""
```

**Behavioral contract (to freeze):**

- `main(["--help"])` and `main([])` return `EXIT_USAGE_ERROR` (2, Ruling 4); no
  pipeline or report call is made for `[]`.
- `run` with fewer than `MIN_CATEGORIES_PER_RUN` requested categories returns
  `EXIT_USAGE_ERROR` because `run_pipeline` raises `PipelineConfigurationError`;
  the CLI must not rank, must not write a report, and must not touch a transport.
- Exit codes are keyed on `PipelineResult.succeeded` (Ruling 4): a completed run
  (including an 8–20 category provisional run) returns `EXIT_OK` (0); a
  preflight-failed run returns `EXIT_RUNTIME_ERROR` (1) even though
  `run_pipeline` returned normally (chunk-10 interface §3 and dependency-map
  §Chunk 10 gate line 1003).
- The production GraphQL callable sends the frozen `X-CSRF-Token` header only;
  no `Cookie` header is added and no CSRF/session sufficiency is claimed.
- `run`/`dashboard` never print a credential, header value, cookie, or response
  body; limitations are the pipeline's already-redacted strings.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/cli.py` | modified (currently a one-line docstring) | Parser, `CliOptions`, dispatch, config/credential wiring, `run_pipeline` invocation, exit-code mapping, renderer invocation, `--run-id` selection, and the stdlib `urllib` production GraphQL transport callable (Ruling 1). |
| `src/niche_scout/__main__.py` | new | `raise SystemExit(main())` so `python -m niche_scout` reaches `cli.main` (Ruling 2). |
| `pyproject.toml` | modified | Add `[project.scripts] niche-scout = "niche_scout.cli:main"`; nothing else (Ruling 2). |
| `tests/test_cli.py` | new (test-author) | CLI analytical tests, §9. |
| `tests/fixtures/cli_fixtures.py` | new (test-author) | Inert argv tables, expected resolved configs, and fake repository/transport factories, §9. |
| `tests/traceability.json` | modified (test-author) | New node → LREQ entries; existing `test_pipeline.py` / `test_report.py` entries unchanged. |

`src/niche_scout/database.py` is **not** touched: Ruling 3 selects `--run-id` as
the minimum surface and adds no repository read. No source file outside this
table may be touched. In particular `report.py`, `pipeline.py`, `config.py`,
`models.py`, `database.py`, and the collectors are consumed, never edited.

## 7. Task breakdown

- [ ] Define `PROG`, `EXIT_OK`/`EXIT_RUNTIME_ERROR`/`EXIT_USAGE_ERROR`,
      `CliError`, `CliOptions`, and `build_parser` with `run` and `dashboard`
      subcommands; all option defaults `None`, `dashboard` requires `--run-id`,
      `--report`/`--report-format` on `run`. (LREQ-CLI-010, LREQ-CLI-020,
      LREQ-CLI-030)
- [ ] Implement `parse_options` without clock/env/network/DB reads. (LREQ-CLI-010,
      LREQ-CLI-030)
- [ ] Implement `resolve_config`: pass only explicitly supplied options as
      `cli_args`, `options.config_path` as `toml_path`; let `load_config` enforce
      precedence and reject unknown keys. (LREQ-CLI-030)
- [ ] Implement `build_graphql_transport`: stdlib `urllib.request` POST of
      `request.body_json` to `request.endpoint` with the frozen headers; return
      `GraphQLBatchResponse`; send `X-CSRF-Token` only, no `Cookie` header, no
      environment read, no CSRF/session claim. (LREQ-CLI-010, LREQ-SEC-010)
- [ ] Implement `run_command`: `read_categories`; `get_credentials(environ)`;
      open the repository at `config.db_path`; construct production transports
      when not injected; call `run_pipeline` exactly once with the resolved
      config/categories/credentials; map `PipelineResult.succeeded` and the three
      pipeline error types to `EXIT_OK`/`EXIT_RUNTIME_ERROR`/`EXIT_USAGE_ERROR`;
      surface redacted `limitations`. (LREQ-CLI-010, LREQ-CLI-040, LREQ-SEC-010)
- [ ] Ensure the run-size rejection path exits `EXIT_USAGE_ERROR` before ranking
      and never constructs a transport or renderer call. (LREQ-CLI-040)
- [ ] Invoke `report.write_run_report` **after** `run_pipeline` returns, only
      when `--report PATH` is given, using `--report-format` (default `html`).
      (LREQ-CLI-010, LREQ-RPT-010)
- [ ] Implement `dashboard_command` keyed on the required `--run-id`; call
      `report.render_dashboard_html` and print the HTML to stdout; map
      `RunNotFoundError` to `EXIT_RUNTIME_ERROR`. (LREQ-CLI-020)
- [ ] Implement `main` dispatch, the `pyproject.toml` `[project.scripts]` entry,
      and `src/niche_scout/__main__.py` (Ruling 2). (LREQ-CLI-010, LREQ-CLI-020)
- [ ] Write `tests/fixtures/cli_fixtures.py`, `tests/test_cli.py`, and the
      `tests/traceability.json` entries. (LREQ-TST-080)

## 8. Edge cases and invariants

From dependency-map requirement rows lines 275–278 and the chunk gate:

- **LREQ-CLI-010.** Successful run; unrecoverable error exits non-zero; the
  report renderer may be invoked only after pipeline completion. An exit code is
  a process outcome; it is not stored on the run row and must not overwrite the
  persisted `runs.status`.
- **LREQ-CLI-020.** No discovery or enrichment network call; the CLI is only a
  caller of the report renderer. `dashboard` opens the database read-only in
  effect (no writes) and never constructs a transport.
- **LREQ-CLI-030.** CLI overrides TOML; TOML overrides defaults. An unset CLI
  option is absent (`None`), never the in-code default, so it cannot shadow TOML
  or a default (chunk-00 §5). Unknown keys and a supplied `source` are rejected
  by `load_config`.
- **LREQ-CLI-040.** Fewer than 8 requested categories rejected before ranking; a
  completed run retains its collection timestamp and explicit limitations in the
  report. Preflight failure exits non-zero while preserving run status,
  discovery/sample/preflight observations, and per-category limitations; zero
  bulk-enrichment requests.
- **Preserved distinction (all commands).** Missing/null, explicit zero,
  invalid, and unavailable stay distinct; the CLI passes values through and
  renders nothing itself, so it must not coerce `None` to `0`, `""`, or `False`.
- **Determinism.** Identical inputs, policy versions, and config give the same
  logical result; the CLI adds no RNG and no ordering dependence. The production
  clock is read only here (the orchestration boundary), never in pure code.
- **Secrets.** `get_credentials` is the only environment read; no credential,
  header value, cookie, or response body appears on stdout/stderr or in an
  exception message.

## 9. Test plan

Test file: `tests/test_cli.py` (new). Fixtures: `tests/fixtures/cli_fixtures.py`
(new) plus the existing `tests/fixtures/config_fixtures.py`,
`tests/fixtures/pipeline_fixtures.py`, and `tests/fixtures/report_fixtures.py`.
No test performs network I/O; transports are in-memory recorders and the clock is
a `FixedClock`. The CLI end-to-end path uses an injected `open_repository` into
pytest `tmp_path` and injected recording transports.

Every test below carries `@pytest.mark.lreq(...)` and gets a
`tests/traceability.json` entry keyed by its full node ID with the LREQ list
shown (the current matrix format is node → `[LREQ, ...]`; the Chunk 0-scoped
validator and Chunk 13's widened required set consume it).

| Test node ID (`tests/test_cli.py::...`) | LREQ marker(s) |
|---|---|
| `test_run_command_invokes_pipeline_once_and_exits_zero` | LREQ-CLI-010 |
| `test_run_command_maps_pipeline_configuration_error_to_nonzero` | LREQ-CLI-010, LREQ-CLI-040 |
| `test_run_command_maps_taxonomy_error_to_nonzero_without_network` | LREQ-CLI-010, LREQ-CLI-040 |
| `test_run_command_calls_renderer_only_after_pipeline_returns` | LREQ-CLI-010, LREQ-RPT-010 |
| `test_run_command_does_not_render_on_failure_path` | LREQ-CLI-010 |
| `test_run_command_preflight_failed_exits_nonzero_and_surfaces_limitations` | LREQ-CLI-010, LREQ-CLI-040 |
| `test_run_command_rejects_fewer_than_min_categories_before_ranking` | LREQ-CLI-040 |
| `test_dashboard_reads_database_only_and_never_constructs_a_transport` | LREQ-CLI-020 |
| `test_dashboard_missing_run_is_nonzero` | LREQ-CLI-020 |
| `test_dashboard_selects_completed_and_failed_runs` | LREQ-CLI-020 |
| `test_cli_option_overrides_toml_and_toml_overrides_default` | LREQ-CLI-030 |
| `test_unset_cli_option_does_not_shadow_toml_or_default` | LREQ-CLI-030 |
| `test_unknown_cli_option_is_rejected` | LREQ-CLI-030 |
| `test_no_subcommand_exits_nonzero_without_pipeline_or_report` | LREQ-CLI-010 |
| `test_run_command_never_emits_credentials_or_response_bodies` | LREQ-SEC-010 |
| `test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` | LREQ-CLI-010, LREQ-SEC-010 |
| `test_dashboard_requires_run_id` | LREQ-CLI-020 |
| `test_run_completed_provisional_eight_categories_exits_zero` | LREQ-CLI-010, LREQ-CLI-040 |

Notes:

- `test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` uses a
  recording `urllib` seam (no live network) and asserts the `X-CSRF-Token`
  header is present exactly once and no `Cookie` header is sent (Ruling 1).
- `test_dashboard_requires_run_id` asserts a missing `--run-id` is a usage
  (nonzero) outcome with no renderer call (Ruling 3).

- `test_dashboard_reads_database_only_and_never_constructs_a_transport` mirrors
  `tests/test_report.py::test_render_dashboard_html_is_database_read_only`
  (already mapped to LREQ-CLI-020) at the CLI layer; the two nodes are distinct
  and both stay in the matrix.
- `test_run_command_rejects_fewer_than_min_categories_before_ranking` covers the
  CLI mapping of the pipeline's already-frozen rejection; it does not rename or
  replace `tests/test_pipeline.py::test_run_with_fewer_than_min_categories_is_rejected`
  (LREQ-CLI-040), which remains the pipeline-side node.
- Golden fixture values (hand-derived, no clock):
  - CLI override wins: `--max-discovery-results-per-category 500` over TOML
    `1500` and default `2000` → resolved `500`, `source == "cli"`.
  - TOML wins: TOML `min_age_days_for_rate = 45`, option unset → `45`,
    `source == "toml"` when TOML supplied it.
  - Default wins: key absent from both → the `IN_CODE_DEFAULTS` value, e.g.
    `recent_window_days == 365` when no TOML and no option.
  - Unset option: an argparse `None` for `recent_window_days` with TOML
    `recent_window_days = 180` → `180` (not `None`, not the effect of a shadow).
  These reuse `config_fixtures.DEFAULT_TOML_BODY`, `CUSTOM_TOML_BODY`,
  `CLI_OVERRIDE_ARGS`, and `CLI_NONE_ARGS` where they fit; the exact override
  table lives in `tests/fixtures/cli_fixtures.py`.
- Run fixtures reuse `pipeline_fixtures.end_to_end_scenario`,
  `RecordingCoveoTransport`, `RecordingGraphQLTransport`, `FixedClock`, and
  `fixture_config`; the dashboard fixtures reuse
  `report_fixtures.run_record` / `category_score_record` / `scored_rows_for`.

## 10. Definition of done (gate)

Copied verbatim from dependency-map §Chunk 12:

- `run` invokes pipeline orchestration and may call the report renderer only after completion.
- `dashboard` calls the report renderer and performs database reads only.
- Fewer than 8 categories are rejected before ranking.
- Unrecoverable run errors exit non-zero while preserving run status and limitations.

## 11. Explicit prohibitions

- `report.py` SHALL NOT import `cli.py` (no report/CLI cycle); the `cli -> report`
  edge is one-directional.
- `run` SHALL NOT call the report renderer before `run_pipeline` returns or on
  its failure path.
- `dashboard` SHALL NOT construct or invoke any transport, and SHALL NOT perform
  discovery or enrichment.
- `cli.py` SHALL NOT read the environment except through
  `config.get_credentials`; it SHALL NOT read credentials from files or argv.
- `cli.py` SHALL NOT read the system clock in any way except to construct the
  production `clock` callable passed to `run_pipeline`; it SHALL NOT introduce a
  clock read into pure code.
- `cli.py` SHALL NOT convert `None`/unavailable to `0`, `0.0`, `""`, or `False`
  when passing values or printing limitations.
- `cli.py` SHALL NOT restate or make configurable `MIN_CATEGORIES_PER_RUN`,
  `PAGE_SIZE`, sampling constants, or composite weights; unknown config keys
  remain rejected by `load_config`.
- `cli.py` SHALL NOT add scheduling, resume/checkpoint, historical trends,
  run comparison, bulk enrichment, additional GraphQL fields, favorite-count,
  alternative collection strategies, or any other out-of-scope feature.
- The production GraphQL callable SHALL NOT send a `Cookie` header, SHALL NOT
  read the environment, and SHALL NOT claim CSRF/session sufficiency (OI-6 stays
  open and unassigned).
- `dashboard` SHALL NOT write an output file or launch a browser; it prints the
  rendered HTML to stdout only.
- `dashboard` SHALL NOT use a default run id or a `--latest` flag.
- No test SHALL make a live network call or carry a real credential.

## 12. Rulings (2026-09-22)

The six open questions in the prior DRAFT, plus assumptions A1/A2 and the open
obligations, are resolved by the lead and approved by the user on 2026-09-22.
They are recorded here as Rulings and are not re-opened. There are no remaining
open questions blocking this plan.

1. **Ruling 1 — production GraphQL transport (was Q1).** Chunk 12 composes a
   stdlib `urllib` production GraphQL callable **in `cli.py`** from the frozen
   `build_graphql_batch_request`, `build_graphql_headers`, and
   `GraphQLBatchResponse` (`interfaces/chunk-05.md` §5). `urllib.request` is an
   explicit `cli.py` import. It sends the frozen `X-CSRF-Token` header only; it
   adds **no** `Cookie` header, never claims CSRF/session sufficiency, and
   records OI-6 as open/unassigned. The "new collector module" and "no live
   path" options are rejected.
2. **Ruling 2 — entry point (was Q2).** Add **both**
   `[project.scripts] niche-scout = "niche_scout.cli:main"` in `pyproject.toml`
   **and** a new `src/niche_scout/__main__.py` that does
   `raise SystemExit(main())`. §6 is amended to list both files.
3. **Ruling 3 — dashboard run selection (was Q3).** `niche-scout dashboard`
   requires `--run-id` (the minimum surface; no new repository method). No
   default and no `--latest`. No `database.py` listing read is added.
4. **Ruling 4 — exit codes (was Q4).** `2` for usage/config errors
   (argparse-compatible), `1` for all runtime failures (including a
   preflight-failed run), and `0` for a completed run including an 8–20 category
   provisional run. The mapping is keyed on `PipelineResult.succeeded`.
5. **Ruling 5 — report rendering (was Q5).** `run` renders only when
   `--report PATH` is given; add `--report-format html|text` defaulting to
   `html`. "May call after completion" is permissive.
6. **Ruling 6 — dashboard output (was Q6).** Print the rendered HTML to stdout;
   no file write, no browser launch.
7. **Ruling 7 — assumptions A1/A2 retained.** A1: keep `db_path` from the
   resolved config; no `--db` flag. A2: limitations go to `stderr`, are
   already-redacted, and `None` is never coerced.
8. **Ruling 8 — open obligations.** Record in the interface/plan that OI-6
   remains open and unassigned; the URI trailing-identifier extraction rule and
   the `runs.taxonomy_sha256` empty-hash obligation are untouched by Chunk 12.
