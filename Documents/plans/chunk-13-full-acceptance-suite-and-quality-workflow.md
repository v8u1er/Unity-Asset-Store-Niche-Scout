# Chunk 13 — Full acceptance suite and quality workflow

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  `Documents/interfaces/chunk-00.md` (VERIFIED), `chunk-02.md` (VERIFIED),
  `chunk-03.md` (VERIFIED), `chunk-05.md` (VERIFIED), `chunk-10.md` (VERIFIED),
  `chunk-11.md` (VERIFIED), `chunk-12.md` (VERIFIED), and every interface
  `chunk-01/4A/4B/6A/6B/7A/7B/8/9A/9B.md` (all VERIFIED). Chunk 13 also consumes
  the frozen runtime contracts of Chunks 0–12 and edits the Chunk-0 tooling.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  none — this is the final `Recommended execution order` chunk (dependency-map §4
  line 1125).

## 1. Goal

Make the complete decision-grade behavior independently verifiable before release:
add the `tests/test_end_to_end.py` acceptance fixture that drives the frozen
`cli`/`pipeline`/`database`/`report` stack with mocked Coveo and GraphQL responses
and a real on-disk SQLite database; add the golden-vector suite asserting exact
results within `1e-9`; widen `validate_traceability` to a true bidirectional check
over every individually defined `LREQ-*` (all 89, not just Chunk 0's seven); and add
the maintained scope-prohibition check that fails if a retired legacy behavior
(scheduling, resume/checkpoint, historical trends, run comparison, full enrichment,
favorite-count, extra GraphQL fields, alternative collection strategies,
configurable weights, confidence intervals/calibration, automated credential
acquisition, multi-user/cloud) is reintroduced. Chunk 13 writes no runtime feature
and changes no runtime behavior; it adds verification and the commands that run it.

## 2. Scope

### In scope

- End-to-end acceptance fixture: `tests/test_end_to_end.py` plus its fixture
  module, driving the frozen `cli.main`/`cli.run_command` path (and, where the
  CLI seam is not needed, `pipeline.run_pipeline`) with the existing mocked
  transports, a real `database.SqliteRepository` under pytest `tmp_path`, and the
  Chunk 11 renderer. Covers the dependency-map §Chunk 13 gate bullets.
- Golden-vector suite asserting the SRS §13 / Appendix A exact results within
  `1e-9` for the TST-090 vector list, in `tests/fixtures/acceptance_fixtures.py`,
  reusing the existing golden fixtures where they already exist and adding only
  the missing vectors (R11). The 21-category strong-reference behavior is
  satisfied at the scoring layer (R7).
- The widened `src/niche_scout/tools/validate_traceability.py`: required set = all
  89 `defined_ids`; corrected multi-argument marker parser; exact `frozenset`
  non-analytical exemption; the validator command is the "missing markers fail
  local test execution" mechanism (R2, R6).
- The workflow command `src/niche_scout/tools/quality_workflow.py` plus
  documentation of the command set in the run log (R9). Formatting/linting are
  scoped to the files this chunk adds/changes; the repo-wide ruff debt is recorded
  as unchanged and out of scope (R10).
- Secret-handling checks: the new static `src/niche_scout/tools/check_secrets.py`,
  the existing runtime redaction tests, and acceptance-run database-row/report
  scans (R5; LREQ-SEC-020 completion; SRS §4.3).
- Import-boundary checks: keep `check_import_boundaries`'s `PURE_MODULES`
  unchanged and add static edge assertions in `tests/test_quality_tooling.py`
  (R4).
- Deterministic repeat-run checks at the acceptance layer (LREQ-ARCH-030).
- The new scope-prohibition checker and its maintained retired-feature constant,
  scanning the production surface only (R1).

### Explicitly out of scope (and who owns it instead)

- Every runtime feature and frozen contract of Chunks 0–12: consumed unchanged.
  Chunk 13 is a **verification** chunk; it is not a primary or completion
  implementation chunk for any runtime `LREQ-*` except the test requirements
  TST-010..090 and NFR-060, and it is the **integration completion** chunk for
  LREQ-NFR-040 and LREQ-NFR-050 (dependency-map §1 lines 124–125).
- Modifying `metrics.py`, `scoring.py`, `sampling.py`, `validation.py`,
  `models.py`, `config.py`, `database.py`, `collector*`, `pipeline.py`,
  `report.py`, or `cli.py`. If the acceptance suite exposes a runtime defect,
  STOP and report it as a finding; do not silently fix runtime code here. (A
  defect that blocks a gate needs a human/lead ruling because the fix belongs to
  the owning chunk's plan.)
- Fixing pre-existing repo-wide `ruff` debt (recorded unchanged at 245 `check`
  errors / 14 unformatted files by the Chunk 11/12 run logs). R10 fixes the gate
  scope to the files this chunk adds/changes; filling the repo-wide debt would
  require editing frozen runtime modules and is not required.
- Re-opening OI-6 (CSRF/session sufficiency) or the URI trailing-identifier
  extraction (identity mapping rule 1.0.1). Both stay open and unassigned
  (dependency-map §6.4/§7); Chunk 13 may assert only that the frozen behavior did
  not change, never that either is verified.
- `runs.taxonomy_sha256` empty-hash rejection: Chunk 10-owned; Chunk 13 verifies
  the existing node, does not re-implement.
- Re-keying `tests/traceability.json`: the node-ID → array-of-LREQ orientation is
  authoritative (R3). `tests/AGENTS.md` lines 5–13 are a stale-rules finding to be
  recorded in the run log, not edited here.
- A `tests/conftest.py` hook: the validator command is the enforcement mechanism
  (R2, R12). A `[project.scripts]` entry and a 21-category pipeline fixture are
  likewise not added (R7, R9).

## 3. Requirements this chunk must satisfy

Ownership labels are from `requirements-dependency-map.md` §1 ("Ownership and
test traceability matrix", lines 124–135) and §3 Chunk 13. Normative text is
quoted from `Documents/SRS-lean.md`.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-TST-010 | **Primary** (primary Chunk 13; supporting 0/7A/7B/8) | "Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries." | §13 |
| LREQ-TST-020 | **Primary** | "Sampling tests SHALL verify census behavior at 0, 1, 99, and 100 assets; four-stratum selection above 100; deterministic repeated selection; early, middle, and late strata; reduced final strata; changed selection digest for a changed rule version; no duplicate membership; `sampling_basis`; `sample_fraction = 1.0` for non-empty census categories; null sample fraction for zero-population categories; and sample fraction distinct from stratum eligibility coverage." | §13 |
| LREQ-TST-030 | **Primary** (supporting 1/5/6B) | "Identity tests SHALL cover valid canonical candidates, malformed fallback, unresolved identity, conflicting candidates, URI parsing, GraphQL mismatch, and duplicate cross-category identities." | §13 |
| LREQ-TST-040 | **Primary** (supporting 3/5/6A) | "GraphQL tests SHALL cover success, reversed response ordering, missing/ambiguous operation association, operation errors, null data, wrong types, negative/non-finite page views, partial success, state filtering, and permanent authentication/CSRF failures." | §13 |
| LREQ-TST-050 | **Primary** (supporting 7A/7B) | "Date and metric tests SHALL cover UTC normalization, naive dates, exact fractional age, rate-threshold boundaries, future dates, zero page views, recent-window boundaries, weighted strata, missing strata, weighted medians, and zero-denominator quality; zero-population categories; and unequal-stratum quality where `QualityRaw` uses `N_h / n_h` expansion weights." | §13 |
| LREQ-TST-060 | **Primary** (supporting 8/9A/9B) | "Scoring tests SHALL cover midrank ties, all-equal references, missing-component renormalization, coverage shrinkage, contradicted page views, 8-category provisional runs, 21-category strong-reference runs, fixed `base_rankable_candidates` constructed before sensitivity, sensitivity-driven final provisional status, and non-rankability." | §13 |
| LREQ-TST-070 | **Primary** (supporting 9B) | "Sensitivity tests SHALL verify all three policies, rank displacement, top-three/top-five stability, warning thresholds, and preservation of the balanced primary score; the sensitivity candidate set SHALL remain unchanged when a warning is raised; and the balanced policy SHALL equal the primary score weights." | §13 |
| LREQ-TST-080 | **Primary** (supporting all runtime chunks) | "An end-to-end fixture SHALL exercise category validation, pagination, duplicate/overlapping identities, four-stratum sampling, one enrichment per unique sampled identity, partial GraphQL failure, metrics, scoring, evidence, sensitivity, SQLite persistence, and report rendering." | §13 |
| LREQ-TST-090 | **Primary** (supporting all analytical chunks) | "Golden vectors SHALL assert exact results within `1e-9` for sample-aware metrics, normalization, components, composite score, coverage, evidence, and sensitivity outputs. The vectors SHALL include a two-category input rejected before ranking, an 8-category provisional run, and a 21-category strong-reference run, zero-population behavior, unequal-stratum QualityRaw, sample fraction versus stratum eligibility coverage, and sensitivity after base-candidate construction." | §13 |
| LREQ-NFR-060 | **Primary** (primary Chunk 13; supporting Chunk 0) | "Formatting, linting, secret handling, and analytical tests SHALL be part of the normal workflow. Strict project-wide typing, 95% whole-package coverage, and CI-on-every-commit are deferred quality improvements, not lean MVP blockers." | §11 |
| LREQ-NFR-040 | **Integration completion** (primary Chunk 0; supporting 7A/8) | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." Completion here = one acceptance-level static check over the public `metrics`/`scoring` surface; the per-module tests already exist. | §11 |
| LREQ-NFR-050 | **Integration completion** (primary Chunk 0) | "The system SHALL run on Python 3.11+ on Windows, macOS, and Linux using `pathlib` for paths." Completion here = environment smoke assertions re-run at the acceptance layer. | §11 |
| LREQ-SEC-020 | **Integration completion** (primary Chunk 2; supporting 0/3/5) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern SHALL be ignored by version control." Completion here = the static secret-handling check over tracked `src/`, `tests/`, `config/`, and `pyproject.toml` plus the acceptance run's persisted-row and rendered-report scans (R5). | §4.3 |

## 4. Interface contracts consumed

Copied from the frozen interface files; not re-derived from source.

**Chunk 12 — `niche_scout.cli` (`interfaces/chunk-12.md` §2–§6):**

- `PROG`, `EXIT_OK = 0`, `EXIT_RUNTIME_ERROR = 1`, `EXIT_USAGE_ERROR = 2`.
- `CliOptions(categories_path, config_path, db_path, run_id, report_path,
  report_format, config_overrides)`.
- `build_parser()`, `parse_options(argv)`, `resolve_config(options, *, environ=None)`.
- `run_command(options, *, environ=None, clock=_utcnow, sleeper=time.sleep,
  coveo_transport=None, graphql_transport=None,
  open_repository=SqliteRepository, write_report=report.write_run_report,
  template_path=None, stdout=sys.stdout, stderr=sys.stderr) -> int`.
- `dashboard_command(options, *, repository=None, open_repository=SqliteRepository,
  report_renderer=report.render_dashboard_html, stdout=sys.stdout,
  stderr=sys.stderr) -> int`.
- `main(argv=None) -> int`.
- Behavioral contract: preflight-failed run ⇒ `EXIT_RUNTIME_ERROR`; <8 categories ⇒
  `EXIT_USAGE_ERROR` before any transport; `dashboard` requires `--run-id` and is
  database-read-only; no credential/header/cookie/response body printed.

**Chunk 10 — `niche_scout.pipeline` (`interfaces/chunk-10.md` §2–§5):**

- `run_pipeline(*, config, categories, credentials, repository, clock,
  coveo_transport, graphql_transport, sleeper=time.sleep, run_id=None,
  taxonomy_path=None, template_path=COVEO_TEMPLATE_PATH, correlation_mode=...,
  preflight_policy=None, retry_policy=..., taxonomy_sha256=None) -> PipelineResult`.
- `PipelineResult(run_id, status, scoring_cutoff_utc, categories,
  identity_preflight_status, category_scores_written, limitations)` with
  `succeeded` iff `status == RunStatus.COMPLETED.value`.
- `PipelineError` / `PipelineConfigurationError` / `TaxonomyInvalidError`;
  `taxonomy_sha256_for(payload)`; `update_run_scoring_cutoff`.
- Preflight `failed`/`insufficient` ⇒ `status=failed`, one null-score row per
  requested category, zero bulk-enrichment requests.

**Chunk 11 — `niche_scout.report` (`interfaces/chunk-11.md` §3–§5):**

- `RunNotFoundError`; `render_dashboard_html(repository, run_id) -> str`;
  `write_run_report(repository, run_id, output_path, *, fmt="html") -> Path`.
- `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli`
  and reads no clock (the R4 edge assertions test exactly this).

**Chunk 0 — `niche_scout.database` / `models` / `config` (`interfaces/chunk-00.md`):**

- `SqliteRepository(db_path, *, initialize=True, ...)`, `close()`, context-manager;
  `get_run`, `get_category_scores`, and the Chunk 11 read surface (the R8 wrapper
  repository delegates to this surface).
- Frozen `models` enums/constants (`MIN_CATEGORIES_PER_RUN = 8`,
  `STRONG_REFERENCE_CATEGORY_COUNT = 21`, the status vocabularies, including
  `PageViewSemanticsStatus`).
- `config.load_config`, `read_categories`, `get_credentials`, `Credentials`.

**Chunk 0 tooling (consumed and one modified):**

- `src/niche_scout/tools/validate_traceability.py`: `defined_ids(text)`,
  `individual_ids(text)`, `chunk_requirements(text, chunk)`, `test_markers(path)`,
  `collect_tests()`, `load_matrix(path)`, `main(argv) -> int`. Chunk 13 modifies
  this file: `chunk_requirements` is superseded by `required_ids` (all 89 defined
  IDs), and `test_markers` must be fixed to parse every argument (R2, R6).
- `src/niche_scout/tools/check_import_boundaries.py`:
  `PURE_MODULES = ("metrics.py", "scoring.py")`, `imported_module_names(tree)`,
  `clock_violations(tree)`, `check_module(path)`, `main(argv) -> int`. Consumed
  unchanged (R4).

**Existing test fixtures consumed (not modified unless §6 says so):**
`tests/fixtures/pipeline_fixtures.py` (`EndToEndScenario`,
`end_to_end_scenario`, `RecordingCoveoTransport`, `RecordingGraphQLTransport`,
`FailingGraphQLTransport`, `FixedClock`, `fixture_config`, `fixture_credentials`,
`write_run_local_template`, `write_taxonomy`, `write_categories`,
`category_set(count)`), `tests/fixtures/config_fixtures.py`,
`tests/fixtures/report_fixtures.py`, `tests/fixtures/coveo_discovery.py`,
`tests/fixtures/graphql_fixtures.py`, `tests/fixtures/scoring_fixtures.py`,
`tests/fixtures/scoring_evidence_fixtures.py`,
`tests/fixtures/sensitivity_fixtures.py`,
`tests/fixtures/metric_estimator_fixtures.py`.

## 5. Interface contract this chunk produces

Chunk 13 produces **no runtime interface**. It produces three process-level tooling
contracts (which `Documents/interfaces/chunk-13.md` may record verbatim once
frozen) and a test/fixture surface.

**Tooling command contract (normative once frozen):**

```python
# src/niche_scout/tools/validate_traceability.py  (modified)
def defined_ids(srs_text: str) -> set[str]: ...
    """Every individually defined LREQ ID the SRS declares (the SRS Appendix B
    wildcard-prefix set). The measured result is 89 IDs; `defined_ids` is the
    required set (R2a, R6)."""

def test_markers(path: Path) -> dict[str, set[str]]: ...
    """Map pytest node ID -> the FULL marker set. Parses EVERY string argument of
    every `@pytest.mark.lreq(...)` call, so `@pytest.mark.lreq("A", "B")`
    contributes both A and B. This fixes the current single-argument parser
    (validate_traceability.py:86–96), which silently misclassifies the 99
    multi-argument markers as unmarked (R6)."""

NON_ANALYTICAL_EXEMPT: frozenset[str] = frozenset(
    {
        "tests/test_collector.py::test_module_imports_without_side_effects",
        "tests/test_collector.py::test_request_body_builder_signature_is_stable",
        "tests/test_sampling.py::test_sampling_module_imports_are_pure",
    }
)  # exactly these three node IDs (R2c, R6)

def required_ids(srs_text: str) -> set[str]: ...
    """Returns every individually defined LREQ ID (= `defined_ids`). Supersedes
    `chunk_requirements` for the widened check; the validator no longer restricts
    the required set to Chunk 0 (R2a)."""

def unmarked_analytical_tests(
    tests: Mapping[str, set[str]], *, exempt: frozenset[str] = NON_ANALYTICAL_EXEMPT
) -> list[str]: ...
    """Node IDs of test functions that carry no `@pytest.mark.lreq` marker after
    the arity fix and are not in the exact `exempt` set. A non-empty result makes
    `main` return 1 (R2c, R6)."""

def main(argv: list[str] | None = None) -> int: ...
    """Bidirectional check: every matrix reference names a defined LREQ; every
    defined LREQ is referenced by at least one test; every analytical test has a
    marker and a matching matrix entry; marker set equals matrix entry exactly;
    no orphan matrix node; no unmarked analytical test outside
    `NON_ANALYTICAL_EXEMPT`. Exit 0 iff all pass, else 1. This command is the
    "missing markers or entries fail local test execution" mechanism (R2c)."""
```

```python
# src/niche_scout/tools/check_scope_prohibitions.py  (new)
@dataclass(frozen=True, slots=True)
class RetiredFeature:
    token: str          # exact literal; case-sensitive
    reason: str         # cites the source below
    source: str         # document path + locator

RETIRED_FEATURES: tuple[RetiredFeature, ...] = (
    RetiredFeature("--resume", ...),            # retired SRS-revision2 §10 ND-12; SRS §15 (checkpoint/resume deferred)
    RetiredFeature("--checkpoint", ...),        # retired SRS-revision2 §10 ND-12; SRS §15
    RetiredFeature("--schedule", ...),          # SRS §15 (scheduled execution deferred); retired SRS-revision2 §10 ND-7
    RetiredFeature("favorite_count", ...),      # SRS §15 (favorite-count deferred); retired SRS-revision2 §10 ND-9; SRS §1.3
    RetiredFeature("packageInListHotness", ...),# retired SRS-revision2 §10 ND-9; SRS §15
    RetiredFeature("raw_product_details", ...), # SRS §15 (full raw API-response archival deferred)
)  # each entry's reason/source cites SRS §15, SRS §1.3, the retired
   # Documents/retired-documents/SRS-revision2.md §10 ND-* labels, and AGENTS.md
   # "Out of scope" per R1

@dataclass(frozen=True, slots=True)
class ScopeViolation:
    path: Path
    line_number: int    # 1-based
    token: str
    source: str

def iter_production_python_files(root: Path) -> Iterable[Path]: ...
    """Yields `src/niche_scout/**/*.py` only. Tests, config, and pyproject.toml
    are not scanned (R1)."""

def scan_ast(tree: ast.AST, *, features: Sequence[RetiredFeature]) -> list[tuple[int, str]]: ...
    """AST-based detection: matches tokens against `ast.Name`/`ast.Attribute`
    identifiers, function/method argument names, keyword argument names, and
    non-docstring `ast.Constant` string literals. Module/class/function docstrings
    and comments are skipped, so the legitimate prohibition prose at
    collector_graphql.py:343 and database.py:620 does not fail. Returns 1-based
    line numbers and matched tokens."""

def scan_paths(paths, *, features: Sequence[RetiredFeature]) -> list[ScopeViolation]: ...

def main(argv: list[str] | None = None) -> int: ...
    """Exit 0 when no retired token is matched in the production surface; 1 with
    one line per violation (`path:line:token (source)`) otherwise. The module
    docstring records that abstract deferrals with no concrete identifier
    (trends, run comparison, configurable weights, CI) are covered by review, not
    by token search (R1)."""
```

```python
# src/niche_scout/tools/check_secrets.py  (new)
ENV_VAR_NAMES: tuple[str, ...] = (
    "NICHESCOUT_COVEO_BEARER_TOKEN",
    "NICHESCOUT_UNITY_CSRF_TOKEN",
)

@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: Path
    line_number: int    # 1-based
    pattern_class: str  # never the matched value

def scan_text_for_secrets(text: str) -> list[tuple[int, str]]: ...
    """Detect literal credential values anchored on `ENV_VAR_NAMES`, on
    `Bearer <literal>`, and on `X-CSRF-Token: <literal>`. Obvious placeholders
    (`YOUR_TOKEN`, `REDACTED`, `fixture-...`, `.env.example`) are allowed. Returns
    1-based line numbers and a pattern class only, never the matched value (R5)."""

def find_credential_findings(root: Path) -> list[SecretFinding]: ...
    """Walk tracked files under `src/`, `tests/`, `config/`, and `pyproject.toml`;
    assert `.gitignore` contains an `.env` pattern and no tracked `.env` exists.
    A guard, not a proof (R5)."""

def main(argv: list[str] | None = None) -> int: ...
    """Exit 0 iff no finding; else 1 with redacted file/line/class lines."""
```

```python
# src/niche_scout/tools/quality_workflow.py  (new)
STEPS: tuple[str, ...] = (
    "validate_traceability",
    "check_import_boundaries",
    "check_scope_prohibitions",
    "check_secrets",
    "ruff-check",
    "ruff-format-check",
    "pytest",
)  # ordered exactly as R9

Runner = Callable[[Sequence[str]], int]

def run_workflow(*, runner: Runner = _default_runner) -> int: ...
    """Run the steps in `STEPS` order via the injectable `runner` seam, which
    receives the command argv and returns the process exit code. Returns 0 iff all
    steps pass; otherwise the first failing step's exit code. Dependency-free; no
    strict typing, coverage, or CI step is added (R9)."""

def main(argv: list[str] | None = None) -> int: ...
    """CLI entry point for `python -m niche_scout.tools.quality_workflow`;
    delegates to `run_workflow`. No `[project.scripts]` entry is added (R9)."""
```

**Test/fixture surface (for the test author):**

- `tests/fixtures/acceptance_fixtures.py` (new, inert data, exempt from the
  file-size trigger): the 2/8/21-category vectors, the scoring-layer 21-category
  composite vector, the zero-population / unequal-stratum `QualityRaw` /
  sample-fraction-versus-eligibility-coverage / sensitivity-after-base-candidates
  vectors, and the R8 contradicted-page-view wrapper repository (writes
  `PageViewSemanticsStatus.CONTRADICTED.value` on `insert_run`).
- `tests/test_end_to_end.py` (new): LREQ-TST-080 acceptance fixture and the
  TST-090 acceptance cases; may be split per §8 preserved-node-ID rule.
- `tests/test_quality_tooling.py` (new): the three tooling checks, the workflow
  runner seam, the R4 edge assertions, and the NFR-040/050 checks.
- `tests/traceability.json` (modified): new node → LREQ entries; the added
  TST-020/040/050 references and the added `LREQ-SEC-020` marker all update the
  corresponding values in the same change (R2b, R6).
- No `tests/conftest.py` (R2c, R12). No `tests/golden_vectors/` (R11).

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/tools/validate_traceability.py` | modified | Required set = all 89 `defined_ids`; fix `test_markers` multi-argument parsing; exact `NON_ANALYTICAL_EXEMPT` frozenset; fail on any unmarked analytical test outside it; keep both directions and marker/matrix equality (R2, R6). |
| `src/niche_scout/tools/check_scope_prohibitions.py` | new | Maintained `RETIRED_FEATURES` tuple (six exact tokens) + AST scan of `src/niche_scout/**/*.py` only (R1; dependency-map §Chunk 13 gate line 1099; SRS §15; AGENTS.md "Out of scope"). |
| `src/niche_scout/tools/check_secrets.py` | new | Static secret-handling check over `src/`, `tests/`, `config/`, `pyproject.toml`; class-only messages; `.gitignore` `.env` assertion (R5). |
| `src/niche_scout/tools/quality_workflow.py` | new | Ordered, dependency-free workflow runner with an injectable `runner` seam and first-failure exit-code propagation (R9). |
| `tests/test_end_to_end.py` | new (test-author) | LREQ-TST-080 acceptance fixture and the TST-090 acceptance cases; may be split per §8. |
| `tests/test_quality_tooling.py` | new (test-author) | Tests for the widened validator, the scope-prohibition checker, the secret check, and the workflow runner; R4 edge assertions; NFR-040/050 (LREQ-NFR-060/TST-090). |
| `tests/fixtures/acceptance_fixtures.py` | new (test-author) | 2/8/21-category vectors, scoring-layer 21-category composite vector, contradicted-page-view wrapper repository, golden-vector tables (R7, R8, R11). |
| `tests/fixtures/__init__.py` | modified (test-author) | Re-export `acceptance_fixtures`. |
| `tests/test_collector.py` | modified (test-author) | Add `@pytest.mark.lreq("LREQ-SEC-020")` to `test_error_summaries_and_metadata_are_redacted`; add TST-040 markers to the existing GraphQL nodes (reversed order, missing/ambiguous correlation, partial success, negative/non-finite views, state filtering, permanent auth/CSRF) and update each matrix value (R2b, R6, R12). |
| `tests/test_sampling.py` | modified (test-author) | Add TST-020 markers to existing nodes (census 0/1/99/100, four strata, early/middle/late, reduced final stratum, digest change, no-duplicate membership, `sampling_basis`, sample-fraction-vs-coverage) and update each matrix value (R2b, R12). |
| `tests/test_metrics.py`, `tests/test_validation.py` | modified (test-author) | Add TST-050 markers to existing nodes (UTC normalization, naive dates, fractional age, rate threshold, future dates, zero views, recent-window boundary, weighted strata/medians, zero-denominator quality, unequal-stratum `QualityRaw` `N_h/n_h`) and update each matrix value (R2b, R12). |
| `tests/traceability.json` | modified (test-author) | New node → LREQ entries plus the R2b/R6 marker additions; orientation unchanged (node → `[LREQ, ...]`), no re-keying (R3). |

No runtime module (`metrics.py`, `scoring.py`, `sampling.py`, `validation.py`,
`models.py`, `config.py`, `database.py`, `collector*`, `pipeline.py`, `report.py`,
`cli.py`) and no `Documents/` file other than this plan may be touched. No
`pyproject.toml` change is authorized (R9). No `tests/conftest.py` is created
(R2c, R12). If an acceptance test exposes a runtime defect, STOP and report it
instead of editing the runtime module.

## 7. Task breakdown

- [ ] Fix `validate_traceability.test_markers` to parse every argument of
      `@pytest.mark.lreq(...)`; add `required_ids` = all 89 `defined_ids`; add the
      exact `NON_ANALYTICAL_EXEMPT` frozenset; make `main` fail on any unmarked
      analytical test outside it; keep both directions, marker/matrix equality, and
      orphan detection; print anchored counts. Re-run and reproduce the corrected
      set (`mismatch=0`, `unmarked=4`, `orphans=0`); if the actual output differs,
      treat it as authoritative and report the discrepancy. (LREQ-TST-080,
      LREQ-NFR-060; R2, R6)
- [ ] Create `check_scope_prohibitions.py` with the six-token `RETIRED_FEATURES`
      tuple and the AST scan of `src/niche_scout/**/*.py` only, skipping
      docstrings/comments; state the review-only deferrals in the docstring.
      (LREQ-NFR-060, gate line 1099; R1)
- [ ] Create `check_secrets.py`: static scan of `src/`, `tests/`, `config/`,
      `pyproject.toml`; placeholder allowlist; `.gitignore` `.env` assertion;
      class-only failure messages. (LREQ-SEC-020, LREQ-NFR-060; R5)
- [ ] Create `quality_workflow.py` with the ordered `STEPS`, the injectable
      `runner` seam, and first-failure exit-code propagation. (LREQ-NFR-060; R9)
- [ ] Add `tests/test_end_to_end.py` with the LREQ-TST-080 acceptance cases and the
      LREQ-TST-090 acceptance cases, driving mocked Coveo/GraphQL, a real SQLite
      database in `tmp_path`, and the renderer; use the R8 wrapper repository for
      the contradicted-page-view case. (LREQ-TST-080, LREQ-TST-090; R8)
- [ ] Add `tests/fixtures/acceptance_fixtures.py`: 2-category rejection input,
      8-category provisional vector, scoring-layer 21-category composite vector,
      zero-population vector, unequal-stratum `QualityRaw` vector, sample-fraction
      versus stratum-eligibility-coverage vector,
      sensitivity-after-base-candidates vector, and the contradicted-page-view
      wrapper repository. (LREQ-TST-090, LREQ-TST-060; R7, R8, R11)
- [ ] Add the TST-020/040/050 markers to the existing nodes named in §6 (never
      rename a node) and update each `tests/traceability.json` value in the same
      change. (LREQ-TST-020, LREQ-TST-040, LREQ-TST-050; R2b, R12)
- [ ] Add `@pytest.mark.lreq("LREQ-SEC-020")` to
      `tests/test_collector.py::test_error_summaries_and_metadata_are_redacted`
      (its matrix entry already exists). (LREQ-SEC-020; R6)
- [ ] Add `tests/test_quality_tooling.py` asserting the validator, the
      scope-prohibition checker, the secret check, and the workflow runner behave
      per their signatures, plus the R4 edge assertions and NFR-040/050 checks.
      (LREQ-NFR-060, LREQ-NFR-040, LREQ-NFR-050, LREQ-TST-090; R4, R9)
- [ ] Run and record the workflow command set (documented in the run log):
      `python -m niche_scout.tools.quality_workflow` (which runs
      validate_traceability, check_import_boundaries, check_scope_prohibitions,
      check_secrets, ruff check, ruff format --check, pytest -q), and run
      `python -m ruff check` / `python -m ruff format --check` on the files this
      chunk adds/changes. (LREQ-NFR-060; R9, R10)
- [ ] Update `tests/traceability.json` for every new/changed node and re-run the
      widened validator to exit 0; record `tests/AGENTS.md` lines 5–13 as a
      stale-rules finding in the run log. (LREQ-TST-080; R3)

## 8. Edge cases and invariants

- **TST-080 acceptance path.** The end-to-end run must be offline: injected
  recording transports, `FixedClock`, a `tmp_path` database, and a run-local
  taxonomy/template written by the fixture. No live network, no real credential,
  and no wall clock.
- **8–20 categories.** A run in this range is provisional: `base_rankable_candidates`
  is empty and `top_3_stability`/`top_5_stability` (and related sensitivity outputs)
  are `null`; the report shows provisional scores without a ranked recommendation
  set (dependency-map §6.2).
- **Empty/fixed candidate set.** Sensitivity is evaluated only over the fixed
  `base_rankable_candidates`; with fewer than 3 (resp. 5) base candidates the
  stability outputs are `null`, `sensitivity_warning` stays `null` (not `false`/0),
  and sensitivity never adds candidates or changes the balanced score (§6.3).
- **Preflight failure.** Produces a failed run with zero bulk-enrichment requests;
  run status, discovery/sample/preflight observations, and per-category
  limitations remain distinct fields (dependency-map §6.1, §6.5).
- **Partial GraphQL operation success vs contradicted page views (R8).** A valid
  operation's fields may be retained when the sibling fails (LREQ-GQL-050), while
  a `page_view_semantics_status = "contradicted"` value disables D and Q and makes
  the category non-rankable (LREQ-SCR-050), with C/R possibly remaining. The fixture
  produces `contradicted` only through the frozen `cli.run_command(...,
  open_repository=...)` seam using a wrapper repository defined in
  `tests/fixtures/acceptance_fixtures.py` that writes
  `PageViewSemanticsStatus.CONTRADICTED.value` on `insert_run`; the value is not
  clobbered because pipeline `_run_identity_preflight` only overwrites when the
  current value is neither `VALIDATED_CUMULATIVE` nor `CONTRADICTED`. The two
  scenarios must remain distinguishable in persisted rows and the report.
- **21-category strong reference (R7).** Satisfied at the scoring layer: reuse
  `tests/test_scoring.py::test_eight_and_twenty_one_category_run_reference_sizes`
  and add a pinned N=21 composite-score vector whose expected values are
  hand-derived from SRS Appendix A (weights `w_D=0.35`, `w_C=0.30`, `w_R=0.20`,
  `w_Q=0.15`; `reference_size = N−1`) and asserted within `1e-9`. No full
  21-category pipeline fixture is built.
- **Missing is not zero.** The acceptance assertions must distinguish null, valid
  zero, invalid, and unavailable; no fixture may coerce a missing value to `0`.
- **Determinism.** Two runs over identical inputs/policy versions/config produce
  structurally and numerically equal persisted rows (LREQ-ARCH-030). Byte
  equivalence is required only where the report's own test already asserts it.
- **Purity boundary.** `metrics.py` and `scoring.py` remain import- and clock-pure.
  `check_import_boundaries.PURE_MODULES` is unchanged; `report.py` must import none
  of `{cli, pipeline, collector, collector_coveo, collector_graphql, config,
  metrics, scoring}` and must read no clock, and `cli.py` must import `report`
  (one-way `cli → report`); these edges are asserted statically in
  `tests/test_quality_tooling.py` (R4).
- **Marker parser arity (R6).** After the `test_markers` fix the authoritative
  unmarked set is exactly 4: the three `NON_ANALYTICAL_EXEMPT` node IDs and
  `tests/test_collector.py::test_error_summaries_and_metadata_are_redacted`, which
  is fixed by adding the `LREQ-SEC-020` marker (its matrix entry already exists).
  The validator command, not a pytest hook, is the enforcement mechanism (R2c).
- **Scope-prohibition prose (R1).** The AST scan skips module/class/function
  docstrings and comments, so legitimate prohibition prose
  (`collector_graphql.py:343`, `database.py:620`) does not fail; the scan covers
  `src/niche_scout/**/*.py` only.
- **Secret findings (R5).** Failure messages name file, line, and a pattern class
  only, never the matched value; the check is a guard, not a proof.
- **Test-file size.** Per project-rules "File size and concern boundaries", a test
  file reaching ~800–1,000 lines is a review trigger: propose a split along the
  LREQ clusters the markers distinguish (TST-060 scoring / TST-070 sensitivity /
  TST-080 e2e), never a mechanical cut, never a renamed pytest node ID; a moved
  node keeps its ID and gets a `tests/traceability.json` path update in the same
  change. `tests/fixtures/acceptance_fixtures.py` is inert data and exempt.
- **Countable claims.** Any count the plan or report states about tests, markers,
  matrix entries, or defined LREQ IDs must be produced by a named query
  (validator output or a stated AST/grep count), with the method and unit. The
  lead-measured baseline is `defined_ids = 89`, `referenced = 86`, exactly
  `LREQ-TST-020`/`LREQ-TST-040`/`LREQ-TST-050` defined-but-unreferenced, and no
  referenced-but-undefined IDs; the Q6 baseline after the arity fix is
  `mismatch=0`, `unmarked=4`, `orphans=0`.

## 9. Test plan

Test files to create/extend:

- `tests/test_end_to_end.py` (new) — LREQ-TST-080 primary, plus the TST-090
  acceptance cases; may be split per §8 preserving node IDs.
- `tests/test_quality_tooling.py` (new) — the tooling checks, the workflow runner
  seam, the R4 edge assertions, and the NFR-040/050 checks.
- `tests/fixtures/acceptance_fixtures.py` (new) — vectors/scenarios/wrapper
  repository (R7, R8, R11).
- `tests/traceability.json` (modified).
- Existing modules receiving markers (R2b, R6, R12), never renamed:
  `tests/test_sampling.py` (TST-020), `tests/test_collector.py` (TST-040 and the
  `LREQ-SEC-020` marker), `tests/test_metrics.py` and `tests/test_validation.py`
  (TST-050).

Every test below carries `@pytest.mark.lreq(...)` and a matching
`tests/traceability.json` entry (node → `[LREQ, ...]`, the authoritative
orientation per R3). IDs are proposals; the test author may add nodes but must not
rename the ones below.

| Test node ID | LREQ marker(s) | Covers |
|---|---|---|
| `tests/test_end_to_end.py::test_acceptance_run_persists_and_renders` | LREQ-TST-080, LREQ-ARCH-030 | Full mocked run: discovery → sample → preflight → enrich → cutoff → score → sensitivity → report. |
| `tests/test_end_to_end.py::test_acceptance_category_validation_rejects_before_network` | LREQ-TST-080, LREQ-EXT-090 | Invalid taxonomy/category rejects with zero transport calls. |
| `tests/test_end_to_end.py::test_acceptance_pagination_duplicate_and_overlap` | LREQ-TST-080, LREQ-EXT-050 | Pagination completion, duplicate rows, shared identity across categories. |
| `tests/test_end_to_end.py::test_acceptance_four_stratum_sampling_and_one_enrichment_per_identity` | LREQ-TST-080, LREQ-SMP-050 | Four strata; one enrichment request per unique sampled identity. |
| `tests/test_end_to_end.py::test_acceptance_partial_graphql_failure_retains_valid_operation` | LREQ-TST-080, LREQ-GQL-050 | Partial operation success persisted independently. |
| `tests/test_end_to_end.py::test_acceptance_contradicted_page_views_distinct_from_partial_success` | LREQ-TST-080, LREQ-SCR-050 | R8 wrapper repository writes `CONTRADICTED`; D/Q unavailable, category not_rankable, C/R may remain; distinguishable from a failed sibling operation. |
| `tests/test_end_to_end.py::test_acceptance_sqlite_rows_match_pure_results` | LREQ-TST-080, LREQ-SMP-080 | Persisted sample/score rows equal the pure results; null vs zero preserved. |
| `tests/test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields` | LREQ-TST-080, LREQ-RPT-020 | Rendered HTML/text carries the mandatory table and heuristic statement. |
| `tests/test_end_to_end.py::test_acceptance_eight_category_run_is_provisional` | LREQ-TST-080, LREQ-TST-060, LREQ-SEN-020 | Empty candidate set, null stability, provisional scores. |
| `tests/test_end_to_end.py::test_acceptance_preflight_failure_marks_run_failed_zero_enrichment` | LREQ-TST-080, LREQ-ID-040 | Failed run, zero bulk-enrichment requests, limitations retained. |
| `tests/test_end_to_end.py::test_acceptance_sensitivity_never_changes_candidate_set` | LREQ-TST-080, LREQ-SEN-020 | Fixed `base_rankable_candidates`; balanced score preserved. |
| `tests/test_end_to_end.py::test_acceptance_repeat_run_is_deterministic` | LREQ-TST-080, LREQ-ARCH-030 | Two identical runs produce structurally equal persisted rows. |
| `tests/test_end_to_end.py::test_acceptance_cli_run_exits_zero_and_writes_report` | LREQ-TST-080, LREQ-CLI-010, LREQ-RPT-010 | `cli.run_command` path, exit 0, report file written only when requested. |
| `tests/test_end_to_end.py::test_acceptance_dashboard_reads_persisted_run_only` | LREQ-TST-080, LREQ-CLI-020 | `dashboard_command`/renderer read-only; no transport. |
| `tests/test_end_to_end.py::test_acceptance_two_category_run_rejected_before_ranking` | LREQ-TST-080, LREQ-TST-090, LREQ-CLI-040 | The TST-090 two-category rejection vector. |
| `tests/test_end_to_end.py::test_acceptance_zero_population_category_vector` | LREQ-TST-090, LREQ-MET-030 | Zero-population vector: null raws, zero coverage, null sample fraction. |
| `tests/test_end_to_end.py::test_acceptance_unequal_stratum_quality_raw_vector` | LREQ-TST-090, LREQ-MET-100 | `QualityRaw` uses `N_h / n_h`; exact within `1e-9`. |
| `tests/test_end_to_end.py::test_acceptance_sample_fraction_distinct_from_eligibility_coverage` | LREQ-TST-090, LREQ-MET-060 | Distinct measures on the same category. |
| `tests/test_end_to_end.py::test_acceptance_twenty_one_category_composite_vector` | LREQ-TST-090, LREQ-TST-060 | R7 scoring-layer N=21 composite vector; reference size 20; exact within `1e-9`. |
| `tests/test_quality_tooling.py::test_validator_requires_every_defined_lreq` | LREQ-NFR-060, LREQ-TST-080 | `required_ids` equals the SRS-defined set; a missing mapping fails. |
| `tests/test_quality_tooling.py::test_validator_parses_multi_argument_lreq_markers` | LREQ-NFR-060, LREQ-TST-080 | `@pytest.mark.lreq("A", "B")` contributes both IDs (R6). |
| `tests/test_quality_tooling.py::test_validator_fails_on_unmarked_analytical_test` | LREQ-NFR-060 | Synthetic unmarked analytical test ⇒ exit 1; an `NON_ANALYTICAL_EXEMPT` node does not fail. |
| `tests/test_quality_tooling.py::test_validator_marker_matrix_equality_both_directions` | LREQ-NFR-060, LREQ-TST-080 | Marker set equals matrix entry; orphan node fails. |
| `tests/test_quality_tooling.py::test_scope_prohibitions_pass_on_current_tree` | LREQ-NFR-060 | Real tree passes against the six-token `RETIRED_FEATURES`. |
| `tests/test_quality_tooling.py::test_scope_prohibitions_detect_reintroduced_retired_behavior` | LREQ-NFR-060 | Injected retired token in a scratch Python source makes the AST scan fail (mechanism test). |
| `tests/test_quality_tooling.py::test_scope_prohibitions_skip_docstrings_and_comments` | LREQ-NFR-060 | Prohibition prose in a docstring/comment does not fail (R1). |
| `tests/test_quality_tooling.py::test_secret_check_redacts_and_detects_a_literal_credential` | LREQ-NFR-060, LREQ-SEC-020 | Literal credential ⇒ failure without echoing the value; placeholder ⇒ pass. |
| `tests/test_quality_tooling.py::test_secret_check_asserts_gitignore_env` | LREQ-NFR-060, LREQ-SEC-020 | `.gitignore` `.env` pattern present; no tracked `.env` (R5). |
| `tests/test_quality_tooling.py::test_quality_workflow_ordering_and_exit_code_propagation` | LREQ-NFR-060 | Injectable runner records step order; first failing step's exit code is returned; the real pytest is not re-run inside pytest (R9). |
| `tests/test_quality_tooling.py::test_report_import_edges_and_clock_free` | LREQ-NFR-060, LREQ-ARCH-010 | `report.py` imports none of the R4 forbidden set and reads no clock; `cli.py` imports `report` (one-way edge). |
| `tests/test_quality_tooling.py::test_nfr050_environment_smoke` | LREQ-NFR-050 | Python ≥ 3.11; `pathlib` paths; `requires-python` present. |
| `tests/test_quality_tooling.py::test_nfr040_public_metric_scoring_surface_typed_and_documented` | LREQ-NFR-040 | Static check over public `metrics`/`scoring` functions. |
| `tests/test_quality_tooling.py::test_import_boundaries_metrics_scoring_unchanged` | LREQ-NFR-060, LREQ-ARCH-010 | `check_import_boundaries` passes with the unchanged `PURE_MODULES`. |

Notes:

- TST-020/040/050 are hosted on **existing** nodes in `tests/test_sampling.py`,
  `tests/test_collector.py`, `tests/test_metrics.py`, and `tests/test_validation.py`
  (R2b, R12); no new node IDs are required for them, and no node may be renamed.
  Each added marker updates that node's `tests/traceability.json` value in the same
  change.
- The R6 marker fix adds `@pytest.mark.lreq("LREQ-SEC-020")` to
  `tests/test_collector.py::test_error_summaries_and_metadata_are_redacted` (its
  matrix entry already exists). The exact `NON_ANALYTICAL_EXEMPT` set contains only
  `tests/test_collector.py::test_module_imports_without_side_effects`,
  `tests/test_collector.py::test_request_body_builder_signature_is_stable`, and
  `tests/test_sampling.py::test_sampling_module_imports_are_pure`.
- Golden vectors that already exist and must be reused, not re-derived:
  `tests/test_scoring_sensitivity.py::test_sensitivity_golden_vectors`,
  `tests/test_scoring_evidence.py::test_pre_sensitivity_golden_vectors`,
  `tests/test_scoring.py::test_midrank_golden_vectors`,
  `tests/test_scoring.py::test_eight_and_twenty_one_category_run_reference_sizes`.
  The R7 N=21 composite vector is new and its expected values are hand-derived
  from SRS Appendix A, not invented here.
- No test performs network I/O, uses a real credential, reads the wall clock, or
  writes outside pytest `tmp_path`/`.scratch/`.
- `tests/AGENTS.md` lines 5–13 (matrix keyed by LREQ → nodes) are a stale-rules
  finding to be recorded in the run log; the node → LREQ orientation is
  authoritative (R3).

## 10. Definition of done (gate)

Copied verbatim from dependency-map §Chunk 13 (lines 1090–1099):

- Exact golden outputs pass within `1e-9`.
- End-to-end fixture covers all required collection, sampling, enrichment, scoring, persistence, and reporting behaviors.
- 8-category provisional run behaves correctly.
- 21-category strong-reference run behaves correctly.
- Preflight failure produces a failed run and zero bulk-enrichment requests.
- Partial GraphQL operation success and contradicted page-view semantics remain distinguishable.
- Sensitivity is null when the fixed candidate set is empty and never changes that set.
- Every analytical test contains an explicit LREQ marker and a matching matrix entry; missing markers or entries fail local test execution, and a machine-checkable bidirectional traceability check verifies that every required test maps to valid individual `LREQ-*` IDs and every individual `LREQ-*` has at least one required test reference.
- `python -m niche_scout.tools.validate_traceability` passes for `tests/traceability.json` and pytest markers.
- The scope-prohibition check passes against the maintained retired-feature list; no stale requirement from the retired SRS is accidentally implemented.

## 11. Explicit prohibitions

- Chunk 13 SHALL NOT change any runtime behavior, formula, threshold, weight,
  field name, schema column, or status vocabulary. A runtime defect found by an
  acceptance test is reported, not fixed here.
- The acceptance suite SHALL NOT make a live network call, read a real credential,
  open `.env`, or depend on the wall clock.
- The scope-prohibition list SHALL NOT be an allowlist that permits a retired
  feature; it SHALL contain the six `RETIRED_FEATURES` tokens and the scan SHALL
  fail when a token is matched in `src/niche_scout/**/*.py`.
- The secret check SHALL NOT print or persist a matched credential value; a
  violation message names the file, line, and pattern class only (R5).
- `metrics.py` and `scoring.py` SHALL remain free of I/O, network, database, CLI,
  report, and clock imports; `PURE_MODULES` SHALL NOT be extended to
  `sampling.py`/`validation.py`/`models.py` (R4); no plan file or test may weaken
  the purity boundary.
- Chunk 13 SHALL NOT modify `Documents/` (other than this plan), `AGENTS.md`,
  `kilo.jsonc`, or `.kilo/`; `tests/AGENTS.md` is recorded as stale, not edited
  (R3).
- `tests/traceability.json` SHALL NOT be re-keyed; the node → LREQ orientation is
  authoritative (R3).
- Chunk 13 SHALL NOT add `tests/conftest.py` (R2c, R12) or a `[project.scripts]`
  entry, and SHALL NOT add a full 21-category pipeline fixture (R7, R9).
- Chunk 13 SHALL NOT resolve, claim closure of, or imply verification for OI-6
  (CSRF/session sufficiency) or the URI trailing-identifier extraction
  (dependency-map §6.4/§7).
- Chunk 13 SHALL NOT enable strict whole-project typing, a 95% coverage gate, or
  CI-on-every-commit; SRS §11/§15 explicitly defer those. It SHALL NOT clear the
  repo-wide ruff debt and SHALL NOT add a new runtime dependency (R10).

## 12. Rulings

The 11 open questions in the prior DRAFT are resolved by the lead (with advisory
research) and are recorded here as R1–R12. They are not re-opened. There are no
remaining open questions blocking this plan.

**R1 (Q1, retired-feature list).** Store a `RETIRED_FEATURES: tuple[RetiredFeature, ...]` constant inside `src/niche_scout/tools/check_scope_prohibitions.py`. Tokens (exact literals): `--resume`, `--checkpoint`, `--schedule`, `favorite_count`, `packageInListHotness`, `raw_product_details`. Each entry carries `reason` and `source` citing SRS §15 (deferred list), SRS §1.3, the retired `Documents/retired-documents/SRS-revision2.md` §10 `ND-*` labels, and `AGENTS.md` "Out of scope". Scan scope is `src/niche_scout/**/*.py` only (the production surface); do not scan `tests/`, `config/`, or `pyproject.toml`. Detection is AST-based: match tokens against `ast.Name`/`ast.Attribute` identifiers, argument names, keyword argument names, and non-docstring `ast.Constant` string literals; skip module/class/function docstrings and comments. This avoids the legitimate prohibition prose at `collector_graphql.py:343` ("`packageInListHotness` field is requested") and `database.py:620` ("historically rejected only None"). Abstract deferrals with no concrete retired identifier (trends, comparison, configurable weights, CI) are covered by review, not token search; state that in the module docstring.

**R2 (Q2, traceability).** (a) The widened validator's required set is ALL 89 `defined_ids`, so `LREQ-TST-020/040/050` must gain at least one reference each. (b) Mark existing nodes in the requirement-focused modules, never rename: TST-020 → existing `tests/test_sampling.py` nodes (e.g. census/four-strata/reduced-stratum/digest/dedup/basis nodes); TST-040 → existing `tests/test_collector.py` nodes (reversed order, missing correlation key, partial success, negative/non-finite views, state filtering, permanent auth/CSRF); TST-050 → existing `tests/test_metrics.py` and `tests/test_validation.py` nodes (UTC normalization, naive dates, fractional age, rate threshold, future dates, zero views, recent-window boundary, weighted strata/medians, zero-denominator quality, unequal-stratum `QualityRaw` with `N_h/n_h`). Every added marker updates that node's `tests/traceability.json` value in the same change. (c) The deliberate non-analytical exemption mechanism is an exact node-ID `frozenset` constant inside `validate_traceability.py` (three IDs: the two collector contract tests + the sampling purity gate). The "fail local test execution" mechanism is the validator command `python -m niche_scout.tools.validate_traceability` (dependency-map lines 418, 438–439); do NOT add a `tests/conftest.py` hook. R6 below fixes the validator's marker parser.

**R3 (Q3, matrix orientation).** The existing node-ID → array-of-LREQ orientation is authoritative (validate_traceability.py:114–123, dependency-map line 410, actual tests/traceability.json). Do NOT re-key. Record `tests/AGENTS.md` lines 5–13 (LREQ→nodes) as a stale-rules finding in the run log; it is outside this chunk's edit permission.

**R4 (Q4, import boundaries).** Keep `check_import_boundaries.PURE_MODULES = ("metrics.py", "scoring.py")` unchanged. Add static edge assertions in `tests/test_quality_tooling.py`: `report.py` imports none of `{cli, pipeline, collector, collector_coveo, collector_graphql, config, metrics, scoring}` and reads no clock; `cli.py` imports `report` (the one-way cli→report edge). Do NOT extend PURE_MODULES to sampling/validation/models (SRS §15 defers import-linter enforcement; sampling already has its own AST purity gate under a prior ruling).

**R5 (Q5, secrets).** Do both: add the static `src/niche_scout/tools/check_secrets.py` AND keep the existing runtime redaction tests, AND add acceptance-run DB-row/report scans. The static scanner walks tracked files under `src/`, `tests/`, `config/`, and `pyproject.toml`; it detects literal credential values anchored on the frozen env-var names `NICHESCOUT_COVEO_BEARER_TOKEN`/`NICHESCOUT_UNITY_CSRF_TOKEN`, `Bearer <literal>`, and `X-CSRF-Token: <literal>` while allowing obvious placeholders (`YOUR_TOKEN`, `REDACTED`, `fixture-...`, `.env.example`); it asserts `.gitignore` contains an `.env` pattern and that no tracked `.env` exists. Failure messages name file/line and a pattern class only, never the matched value. State that the check is a guard, not a proof.

**R6 (Q6, validator marker parsing + unmarked set).** Chunk 13 MUST fix `test_markers` to parse ALL arguments of `@pytest.mark.lreq(...)` (not only a single argument), because the current single-arg parser silently misclassifies 99 multi-arg markers. After the fix the authoritative unmarked set is exactly 4: exempt the three non-analytical nodes `tests/test_collector.py::test_module_imports_without_side_effects`, `tests/test_collector.py::test_request_body_builder_signature_is_stable`, `tests/test_sampling.py::test_sampling_module_imports_are_pure`; add marker `@pytest.mark.lreq("LREQ-SEC-020")` to `tests/test_collector.py::test_error_summaries_and_metadata_are_redacted` (its matrix entry already exists). The widened validator must fail (exit 1) on any unmarked analytical test outside the exemption set. The implementation must re-run the validator and reproduce the corrected set; if it differs, treat the actual output as authoritative and report the discrepancy.

**R7 (Q7, 21-category vector).** Satisfy the 21-category strong-reference behavior at the SCORING layer: reuse `tests/test_scoring.py::test_eight_and_twenty_one_category_run_reference_sizes` and add a pinned composite-score vector for N=21 whose expected values are hand-derived from SRS Appendix A (§8.3 weights w_D=0.35, w_C=0.30, w_R=0.20, w_Q=0.15; reference size N−1) and asserted within 1e-9. Do NOT build a full 21-category pipeline fixture.

**R8 (Q8, contradicted page views).** Produce `page_view_semantics_status="contradicted"` through the frozen `cli.run_command(..., open_repository=...)` seam with a wrapper repository defined in `tests/fixtures/acceptance_fixtures.py` that writes `PageViewSemanticsStatus.CONTRADICTED.value` on `insert_run` (a CONTRADICTED value is not clobbered by the preflight because pipeline `_run_identity_preflight` only overwrites when the current value is neither `VALIDATED_CUMULATIVE` nor `CONTRADICTED`). Assert D and Q become unavailable and the category is `not_rankable`, while C/R may remain, and that this is distinguishable from the existing partial-GraphQL-failure scenario.

**R9 (Q9, workflow command).** Do both: document the command set in the run log AND add a minimal `src/niche_scout/tools/quality_workflow.py` with `main(argv: list[str] | None = None) -> int` that runs, in order, `validate_traceability`, `check_import_boundaries`, `check_scope_prohibitions`, `check_secrets`, then `ruff check`, `ruff format --check`, and `pytest -q`, returning 0 iff all pass and the first failing step's exit code otherwise. Keep it dependency-free and provide an injectable runner seam so `tests/test_quality_tooling.py` can test ordering/exit-code propagation without re-running pytest inside pytest. Do NOT add strict typing, coverage, or CI (SRS §11 defers them) and do NOT add a `[project.scripts]` entry.

**R10 (Q10, lint scope).** NFR-060 does NOT require the repo-wide ruff debt (245 `check` errors / 14 unformatted files) to be cleared; filling it would require editing frozen runtime modules. The gate requires `ruff check` and `ruff format --check` to pass on the files this chunk adds/changes, and the run log records the repo-wide debt as unchanged and out of scope (matching Chunks 10–12).

**R11 (Q11, vector location).** Put new vectors/scenarios in `tests/fixtures/acceptance_fixtures.py` (inert data, exempt from the file-size trigger). Do NOT create `tests/golden_vectors/` (the validator only globs `tests/test_*.py`).

**R12 (Q12, TST-020/040/050 hosts).** Host the three missing requirement references on existing nodes in `tests/test_sampling.py` (TST-020), `tests/test_collector.py` (TST-040), and `tests/test_metrics.py`/`tests/test_validation.py` (TST-050), as in R2(b). Do not create a `tests/conftest.py`.