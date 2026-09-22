# Chunk 11 — Report renderer and read-only dashboard

Status: FROZEN (2026-09-22, after lead rulings on §12; §12.0 records the rulings)
Depends on (frozen interfaces required before this plan can be trusted):
  `Documents/interfaces/chunk-4B.md`, `chunk-7B.md`, `chunk-08.md`,
  `chunk-9A.md`, `chunk-9B.md`, `chunk-10.md`
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 12 (CLI `dashboard` calls the renderer), Chunk 13 (rendered-report
  acceptance assertions).

## 1. Goal

Make a completed or failed run inspectable from local persistence alone. This
chunk adds a database read model and a renderer in `report.py` that turns the
rows written by Chunks 3/4B/6A/6B/8/9A/9B/10 into a self-contained, sortable,
read-only audit/diagnostic view: a primary table with every mandatory field, a
per-category detail panel with formulas/inputs/strata/warnings/timestamps, and
an explicit heuristic statement. It performs database reads and local rendering
only; it never initiates discovery or enrichment, never reads the clock, and
never recomputes a metric or score.

## 2. Scope

### In scope
- The `report.py` read model: `RunReportView` / `CategoryReportRow` /
  `StratumReportRow`, loaded from a `SqliteRepository` by `run_id`.
- The `report.py` renderer: deterministic self-contained HTML and plain text
  output; a sortable primary table; a category detail panel.
- A failed-run fallback read path: one row per requested category when
  `category_scores` rows are absent, joined from `runs`, raw discovery
  observations, `sample_members`, and the persisted preflight fields.
- Warning/limitation display using only `models.WarningCode` values (SRS
  Appendix C) and the redacted limitation strings already persisted/returned by
  Chunk 10 — no new vocabulary.
- Display of non-rankable categories and the LREQ-RPT-050 heuristic statement
  and required distinctions.
- Tests in `tests/test_report.py` + fixtures, with `@pytest.mark.lreq` and
  `tests/traceability.json` entries (this chunk's routing is `impl-fast`, which
  writes tests too; there is no separate `test-author` stage).

### Explicitly out of scope (and who owns it instead)
- The `niche-scout dashboard` / `niche-scout run` commands, argument parsing,
  configuration precedence, exit codes, and run selection are **Chunk 12**
  (LREQ-CLI-010/-020/-030/-040). LREQ-RPT-010's command interface is completed
  by Chunk 12; Chunk 11 supplies the renderer that command calls.
- Any recomputation of metrics, normalization, components, scores, evidence,
  rankability, or sensitivity: **Chunks 7B/8/9A/9B**. The report reads persisted
  values only. `metrics.py` and `scoring.py` are untouched.
- The persisted JSON shapes `warnings_json` and `missing_components_json`
  (frozen by `interfaces/chunk-10.md` §6) are parsed read-only and **never
  redefined**.
- Any schema change, index, migration, or new persisted column: none.
- Historical run comparison, trend displays, scheduled-run controls,
  run-resume controls, advanced provenance navigation, and network assets
  (CDNs, fonts, remote JS/CSS): omitted per SRS §10 (LREQ-RPT-010's surrounding
  text) and the out-of-scope list in `AGENTS.md`.

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-RPT-010 | Primary — Chunk 11 renders; command completion is Chunk 12 | "Provide a local read-only HTML report or dashboard launched by one command. The required interface SHALL retain: `niche-scout run --categories config/categories.json --config config/default.toml` / `niche-scout dashboard`" | SRS §10 |
| LREQ-RPT-020 | Primary | "The primary table SHALL show category, rank, composite score, `D/C/R/Q`, discovered population, sample size, census flag, unique enrichment count, sample fraction, sampling basis, cross-category overlap count, usable count and stratum eligibility coverage per component, evidence grade, rankability, discovery status, page-view semantic status, `top_3_stability`, `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, sensitivity warning, and the percentage of the category sample shared with other categories." | SRS §10 |
| LREQ-RPT-030 | Primary | "Category details SHALL show formulas or concise explanations, metric inputs, sample strata, warnings, timestamps, and observed-versus-inferred sample-based values." | SRS §10 |
| LREQ-RPT-040 | Primary | "Non-rankable categories SHALL remain visible." | SRS §10 |
| LREQ-RPT-050 | Primary | "The report SHALL state that the score is a deterministic, within-run heuristic … it has not been calibrated against sales, revenue, downloads, or conversion. It SHALL distinguish pagination completion from immutable snapshot completeness, the page-view index from a weekly traffic rate, descriptive midranks from inferential percentiles, stratum eligibility coverage from sample fraction, deterministic-sample evidence from statistical representativeness, and evidence grade from statistical confidence." | SRS §10 |
| LREQ-SMP-080 | Supporting contract consumed (not owned) | Sample fraction/census/coverage fields rendered; `sample_fraction` is `1.0` for a non-empty census, `null` when population is zero, and is distinct from stratum eligibility coverage. | SRS §5.1 |
| LREQ-EVD-010/-020/-040/-050 | Supporting contract consumed | Rankability states and evidence grades are rendered, never re-derived. | SRS §9.1/§9.2 |
| LREQ-SEN-020/-040 | Supporting contract consumed | Persisted sensitivity fields are rendered; diagnostics qualify the balanced score and never replace it. | SRS §9.3 |
| LREQ-CLI-020 | Supporting contract (renderer half) | "The `niche-scout dashboard` command SHALL read the database and SHALL not initiate discovery or enrichment." Chunk 11 guarantees the renderer itself does DB reads only. | SRS §10 |
| LREQ-NFR-040 | Supporting (public function typing) | Public functions carry type hints and docstrings stating null/edge behavior. | SRS §11 |

## 4. Interface contracts consumed

From `interfaces/chunk-10.md` §6 (frozen JSON shapes; **SHALL NOT be
redefined**):
- `category_scores.warnings_json` — compact JSON array of unique warning codes,
  ascending lexical; `"[]"` when empty.
- `category_scores.missing_components_json` — compact JSON array of the missing
  component keys in `("D","C","R","Q")` order; `"[]"` when all four present.
- Other persisted columns consumed read-only: `ranking_sensitivity_json`
  (`{"policies", "ranked_categories", "categories":[{category, score_*,
  rank_*, maximum_score_delta, maximum_rank_displacement, warning}],
  "reference_set_size", "displacement_threshold", "top_3_stability",
  "top_5_stability", "maximum_score_delta", "maximum_rank_displacement",
  "warning"}`), `reference_size`, `reference_usable_counts_json`,
  `stratum_statistics_json`, `strategy_statistics_json` schema
  (`interfaces/chunk-4B.md` §5.2), and `runs.identity_preflight_summary_json` /
  `identity_preflight_status`.

From `interfaces/chunk-4B.md` §5.3a: `parse_stratum_statistics(payload)` returns
the tuple of ten-key stratum objects and raises `DatabaseError` on a malformed
payload. Chunk 11 parses strata through this helper; it does not re-implement
the schema.

From `models.py` (read-only names): `RunRecord`, `CategoryScoreRecord`,
`SampleMemberRecord`, `EnrichmentObservationRecord`, and the enums `RunStatus`,
`DiscoveryStatus`, `PageViewSemanticsStatus`, `IdentityPreflightStatus`,
`BreadthSource`, `BreadthCompletenessStatus`, `SamplingBasis`, `ScoreState`,
`EvidenceGrade`, `RankabilityStatus`, `WarningCode`; constants
`COMPONENT_WEIGHT_KEYS`-equivalent ordering is **not** imported from
`scoring.py` — the report uses the literal `("D","C","R","Q")` render order only.

From `database.py` read surface (all existing, no additions):
- `get_run(run_id) -> RunRecord | None`
- `get_category_scores(run_id) -> Sequence[CategoryScoreRecord]`
- `get_sample_members(run_id, category) -> Sequence[SampleMemberRecord]`
- `iter_raw_discovery_observations(run_id, category) -> Iterator[...]`
- `get_enrichment_observation(run_id, asset_identity_key) -> EnrichmentObservationRecord | None`
- counts: `count_discovery_observations`, `count_sample_members`,
  `count_distinct_enrichment_identities`.

No repository read method lists runs or reads preflight observations directly.
Chunk 11 must not add one (that would be an interface/schema change); see §12.

## 5. Interface contract this chunk produces

`report.py` is **I/O + render** (disk/DB read, string/HTML output). It must not
import `metrics`, `scoring`, `collector*`, `config`, `pipeline`, or `cli`; it
must not perform network I/O or read the clock. Values are read from persistence
only; `report.py` never imports a pure computation module.

```python
# module: src/niche_scout/report.py

COMPONENT_RENDER_ORDER: tuple[str, ...] = ("D", "C", "R", "Q")

HEURISTIC_STATEMENT: str
"""Fixed LREQ-RPT-050 statement: the score is a deterministic, within-run
heuristic over marketplace signals and, for larger categories, a stratified
sample; it is not calibrated against sales, revenue, downloads, or conversion
and is not a statistically representative marketplace estimate. Constant text,
not composed per render."""

class ReportError(RuntimeError): ...
class RunNotFoundError(ReportError): ...

@dataclass(frozen=True, slots=True)
class StratumReportRow:
    """One parsed `stratum_statistics_json` object (chunk-4B §5.2 ten keys)."""
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    population_count: int          # N_h
    selected_count: int            # n_h
    usable_demand_count: int | None      # u_demand_h
    usable_recent_count: int | None      # u_recent_h
    usable_quality_count: int | None     # u_quality_h
    usable_status: str                   # pending | usable | unavailable | invalid
    eligibility_rule: str | None

@dataclass(frozen=True, slots=True)
class ReportWarning:
    """A displayed warning. `code` is a `models.WarningCode` value or a
    preflight/limitation code already observed by Chunk 10. It is never invented
    here."""
    code: str
    category: str | None

@dataclass(frozen=True, slots=True)
class CategoryReportRow:
    """One category as shown in the table and detail panel.

    Every field is `None` when the persisted value is null/unavailable; a field
    is never converted to `0`, `0.0`, `False`, or an empty string. `rank` is
    `None` for a category absent from `ranking_sensitivity_json.ranked_categories`
    (not rankable, not provisional). `warnings` preserves the persisted code set
    (sorted, deduplicated) and is `()` when warnings_json is `[]`.
    `observed_vs_inferred` labels each displayed metric value's provenance; see
    §7 task 6.
    """
    category: str
    rank: int | None
    market_opportunity_score: float | None
    score_state: str
    component_d: float | None
    component_c: float | None
    component_r: float | None
    component_q: float | None
    missing_components: tuple[str, ...]
    discovered_population_count: int | None
    enriched_sample_count: int | None       # "sample size"
    sample_is_census: bool | None
    sampling_basis: str | None
    sample_fraction: float | None
    unique_enrichment_count: int | None
    overlap_category_count: int | None
    overlap_sample_percentage: float | None
    usable_demand_sample_count: int | None
    usable_recent_supply_sample_count: int | None
    usable_quality_sample_count: int | None
    demand_stratum_eligibility_coverage: float | None
    recent_supply_stratum_eligibility_coverage: float | None
    quality_stratum_eligibility_coverage: float | None
    evidence_grade: str
    rankability_status: str
    discovery_status: str
    page_view_semantics_status: str
    top_3_stability: float | None
    top_5_stability: float | None
    maximum_score_delta: float | None
    maximum_rank_displacement: int | None
    sensitivity_warning: bool | None
    reference_size: int | None
    computed_at_utc: datetime | None
    warnings: tuple[str, ...]
    strata: tuple[StratumReportRow, ...]
    raw_metric_inputs: "RawMetricInputs | None"

@dataclass(frozen=True, slots=True)
class RawMetricInputs:
    """The six persisted raw metric values (metric inputs, LREQ-RPT-030)."""
    demand_per_asset_raw: float | None
    demand_median_raw: float | None
    breadth_raw: float | None
    recent_share_raw: float | None
    median_age_raw: float | None
    quality_raw: float | None

@dataclass(frozen=True, slots=True)
class RunReportView:
    """The whole read model for one run. `categories` is ordered by
    `(-rank, category)` for ranked rows, then unranked rows by ascending
    category, so rendering is deterministic. `limitations` are the redacted
    strings already persisted/returned by Chunk 10; `()` when none were
    recorded (never a fabricated zero)."""
    run_id: str
    status: str                        # RunStatus value
    run_started_at_utc: datetime
    scoring_cutoff_utc: datetime | None
    completed_at_utc: datetime | None
    identity_preflight_status: str
    page_view_semantics_status: str
    categories: tuple[CategoryReportRow, ...]
    warnings: tuple[ReportWarning, ...]
    limitations: tuple[str, ...]
    heuristic_statement: str           # == HEURISTIC_STATEMENT

def load_run_report_view(
    repository: "SqliteRepository", run_id: str
) -> RunReportView:
    """Read one run's report model. Database reads only; no clock, no network.

    Raises `RunNotFoundError` when `get_run(run_id)` is `None`. Uses one
    `category_scores` row per category as the primary source. When
    `get_category_scores` returns no row for a category named in
    `runs.categories_json` (the Chunk 10 failed-preflight fallback described in
    dependency-map §Chunk 10 clarification), builds the same one-row-per-category
    view from `runs`, raw discovery observations, `sample_members`, and the
    persisted preflight fields; fields with no persisted or derivable value are
    `None`, never fabricated. Never computes a metric, component, score,
    evidence grade, rankability, or sensitivity value.
    """

def render_run_report_html(view: RunReportView) -> str:
    """Return one self-contained HTML document (inline CSS/JS, no external
    assets, no network) with a sortable primary table covering every LREQ-RPT-020
    column and a detail panel per category covering every LREQ-RPT-030 item.
    Deterministic for a fixed `view`. Does not read the clock."""

def render_run_report_text(view: RunReportView) -> str:
    """Return the plain-text equivalent of the HTML view, carrying the same
    mandatory fields and the HEURISTIC_STATEMENT. Deterministic; no clock."""

def write_run_report(
    repository: "SqliteRepository",
    run_id: str,
    output_path: Path,
    *,
    fmt: str = "html",
) -> Path:
    """`load_run_report_view` + render + write `output_path`. `fmt` is `"html"`
    or `"text"`; any other value raises `ValueError`. Returns the written path.
    Local filesystem write only (disk read/render I/O); no network."""

def render_dashboard_html(repository: "SqliteRepository", run_id: str) -> str:
    """Convenience for the Chunk 12 `dashboard` command: load + render the
    read-only dashboard for `run_id`. Performs database reads only and initiates
    no discovery or enrichment (LREQ-CLI-020). `RunNotFoundError` when absent."""
```

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/report.py` | modified (currently `"""Read-only report boundary."""` only) | Read model + renderers + public surface of §5 |
| `tests/test_report.py` | new | Analytical tests, §9 |
| `tests/fixtures/report_fixtures.py` | new | Inert fixtures/golden vectors, §9 |
| `tests/traceability.json` | modified | Node → LREQ entries for the new tests |

No other source file changes. No repository method is added (see §12 Q1).

## 7. Task breakdown

- [ ] Define the §5 dataclasses/constants and `ReportError` /
      `RunNotFoundError` in `report.py`. (LREQ-RPT-010, LREQ-NFR-040)
- [ ] Implement `load_run_report_view` primary path: `get_run`,
      `get_category_scores`, `parse_stratum_statistics`, parse
      `missing_components_json` / `warnings_json` / `ranking_sensitivity_json`
      read-only; derive `rank` from `ranking_sensitivity_json.ranked_categories`.
      (LREQ-RPT-020, LREQ-RPT-030)
- [ ] Implement the failed-run fallback path (dependency-map Chunk 10
      clarification): when a `category_scores` row is absent for a requested
      category, build the row from `runs.categories_json`,
      `iter_raw_discovery_observations`, `get_sample_members`, and the persisted
      preflight fields; `evidence_grade = "insufficient"`,
      `rankability_status = "not_rankable"`, an `IDENTITY_PREFLIGHT_FAILED`
      warning when preflight status is `failed`/`insufficient`; every other
      unavailable field `None` (never `0`; §8 pre-scoring rule applies).
      (LREQ-RPT-010, LREQ-RPT-040)
- [ ] Implement `render_run_report_html` with a sortable primary table carrying
      every LREQ-RPT-020 column and a category detail panel carrying every
      LREQ-RPT-030 item (formulas/explanations, the six raw metric inputs,
      strata, warnings, timestamps, observed-vs-inferred labels). Include
      `HEURISTIC_STATEMENT` and the LREQ-RPT-050 distinctions on every render.
      (LREQ-RPT-020, LREQ-RPT-030, LREQ-RPT-050)
- [ ] Implement `render_run_report_text`, `write_run_report`,
      `render_dashboard_html`. (LREQ-RPT-010, LREQ-CLI-020 renderer half)
- [ ] Encode the observed-vs-inferred provenance map: which displayed values are
      observed (persisted marketplace observations, e.g. `discovered_population_count`,
      `rating`-derived raws, timestamps) versus inferred/sample-based
      (stratum-expanded raws, coverages, normalized components, composite,
      sensitivity). Fixed labels, no new formula. (LREQ-RPT-030, LREQ-RPT-050)
- [ ] Render non-rankable categories in both table and detail, with the
      not-rankable explanation derived only from persisted fields
      (`rankability_status`, `evidence_grade`, `missing_components_json`,
      warning codes, `discovery_status`, `page_view_semantics_status`).
      (LREQ-RPT-040)
- [ ] Write `tests/fixtures/report_fixtures.py` and `tests/test_report.py`;
      add `tests/traceability.json` entries. (all LREQ-RPT-*, LREQ-TST-080 via
      the validator)

## 8. Edge cases and invariants

- **Missing is not zero.** Null persisted values render as an explicit
  "unavailable"/"—" marker with no numeric value; the view field stays `None`.
  `0` and `0.0` are rendered as measured values only when the row truly
  persisted them (e.g. a verified zero-result category's
  `discovered_population_count = 0`).
- **Pre-scoring NOT NULL zeros are not measured.** `usable_demand/recent/quality_sample_count`
  and the three stratum-eligibility coverages are `NOT NULL DEFAULT 0` /
  `0.0` in the schema, and Chunk 10's failed-preflight rows persist those
  defaults before any scoring. When the row is pre-scoring/unavailable
  (`score_state != "scored"` or the row came from the failed-run fallback), the
  report renders those six values as "unavailable", never as measured `0`/`0.0`
  (chunk-4B interface: these counts are "never presented as measured while
  pending"; SRS §1.2). Measured zeros are rendered as `0` only for rows whose
  score state is scored.
- **Pending strata.** A `stratum_statistics_json` entry with
  `usable_status = "pending"` (or any non-final status) renders as pending/
  unavailable in the detail panel, not as `0` usable.
- **Failed run stays visible.** A run with `status = "failed"`, or an
  empty/absent score row set, still yields one row per requested category and
  renders as an audit/diagnostic report.
- **8–20 category runs.** Provisional scores render, `top_3_stability` /
  `top_5_stability` / displacement fields render `null`, and the report does not
  present the set as a ranked recommendation (dependency-map §6.2/§6.3).
- **Per-category vs run-level page-view semantics.** Each `category_scores` row
  carries its own `page_view_semantics_status` and is authoritative for the
  category column; the `runs.page_view_semantics_status` supplies the run-level
  banner only.
- **Ranking sensitivity qualifies, never replaces.** The displayed composite is
  the persisted balanced score; sensitivity diagnostics are shown alongside it.
- **Determinism.** Same persisted rows + same `view` produce byte-identical
  output; ordering is explicit (`(-rank, category)` then category), never
  set/dict-order dependent.
- **No clock.** All timestamps come from persisted rows; naive datetimes cannot
  arise because persisted values are UTC-aware (`models._UtcRecord`).
- **Warning vocabulary.** Only `models.WarningCode` values and the observed
  preflight/limitation codes appear; the renderer never synthesizes a code.
- **No secret leakage.** Warnings/limitations, request metadata, and error
  summaries must not expose credentials, cookie/header values, identity strings,
  or response bodies; Chunk 10 already redacts — the renderer passes them through
  without expanding them.
- **Self-contained output.** HTML embeds its CSS/JS inline; no external
  script/link/asset URL, so opening the report produces no network activity.

## 9. Test plan

- Test file: `tests/test_report.py` (new). Fixtures:
  `tests/fixtures/report_fixtures.py` (inert data only).
- Fixture build path: construct `CategoryScoreRecord` / `RunRecord` /
  `SampleMemberRecord` fixtures and persist them through a temporary
  `SqliteRepository` (never live network), or build `RunReportView` values
  directly for renderer tests. Golden vectors are hand-derived from SRS §5.1
  (`sample_fraction = 1.0` non-empty census, `null` zero-population),
  §6.5 field semantics, §9.1/§9.2/§9.3 (`null` stability when candidates < k),
  and §10 column list.
- Required markers, 1:1 to §3 LREQ IDs (each test carries at least one):
  - `LREQ-RPT-010` — loader/renderer smoke test; `write_run_report` writes
    local output with no network; `RunNotFoundError` on unknown run.
  - `LREQ-RPT-020` — primary-table fixture asserts every mandatory column is
    present and labelled.
  - `LREQ-RPT-030` — category-detail fixture asserts formulas/explanations,
    the six raw inputs, strata, warnings, timestamps, observed-vs-inferred.
  - `LREQ-RPT-040` — non-rankable category remains visible with its reason.
  - `LREQ-RPT-050` — report contains `HEURISTIC_STATEMENT` and all six required
    distinctions.
  - `LREQ-CLI-020` — `render_dashboard_html` performs database reads only (no
    transport constructed, no network; assert no network call is possible from
    the module surface).
  - `LREQ-NFR-040` — every public function has hints and a docstring naming
    null/edge behavior.
- `tests/traceability.json`: add one entry per new node ID mapping to the
  LREQ-RPT marker(s) it exercises; parameterized tests map by base node ID.
  Run `python -m niche_scout.tools.validate_traceability` before declaring done.
- Golden vectors needed:
  - Rankable category with all four components, `sample_fraction = 0.2`,
    coverage `>= 0.80`, sensitivity fields present.
  - Non-rankable category (`rankability_status = "not_rankable"`,
    `missing_components_json = ["D","Q"]`) that must still render.
  - Failed-preflight run with no `category_scores` rows → fallback row per
    requested category.
  - Zero-population census-exempt category: `discovered_population_count = 0`,
    `sample_fraction = null`, raw metrics `null`, `sample_is_census = false`.
  - Explicit-zero row: `overlap_category_count = 0`,
    `overlap_sample_percentage = 0.0` on a non-empty sample (measured zero, not
    missing).
  - 8–20 category run: `top_3_stability = top_5_stability = null`.
  - All-null/unavailable row: every optional field `None`; warnings `()`.
  - Failed-preflight limitation row whose persisted `usable_*_sample_count` and
    stratum-eligibility coverages are the schema's `0`/`0.0` defaults: the report
    renders them as "unavailable", not measured zeros (§8).

## 10. Definition of done (gate)

Copied verbatim from dependency-map §Chunk 11:

- `dashboard` performs database reads only.
- Reports include every mandatory score, sample, coverage, evidence, and sensitivity field.
- Non-rankable categories remain visible.
- Failed preflight runs remain visible as audit/diagnostic reports even when no metric or score rows were computed.
- Report fixtures assert the required distinctions between pagination completion and immutable snapshot completeness, page-view index and weekly traffic rate, midranks and inferential percentiles, sample fraction and stratum eligibility coverage, deterministic evidence and statistical confidence, and heuristic output versus sales/revenue/conversion/traffic-rate claims.
- Report language does not imply sales forecasting, statistical confidence, or representative marketplace estimation.

## 11. Explicit prohibitions

- `report.py` must not import `metrics.py` or `scoring.py` (and therefore not
  their forbidden dependencies), nor `collector*`, `config`, `pipeline`, or
  `cli`. It must not import any network module.
- `report.py` must not read the clock (`datetime.now`, `utcnow`, `time.time`) or
  accept a clock parameter; all timestamps are persisted values.
- `report.py` must not initiate any HTTP/GraphQL/Coveo request; `dashboard`
  performs database reads only (LREQ-CLI-020).
- `report.py` must not recompute, adjust, or overwrite any metric, component,
  normalized value, composite score, evidence grade, rankability, or
  sensitivity statistic; it renders persisted values verbatim (rounding for
  display only, never altering the stored value).
- `report.py` must not redefine or rewrite `warnings_json` or
  `missing_components_json` (interfaces/chunk-10.md §6), nor the
  `stratum_statistics_json` schema (interfaces/chunk-4B.md §5.2).
- `report.py` must not invent warning/limitation codes or wording outside
  `models.WarningCode` (SRS Appendix C) and the redacted strings Chunk 10
  produced.
- `report.py` must not convert a null/unavailable value to `0`, `0.0`, `False`,
  or an empty string (`or 0`, `.get(k, 0)`, default-0 arguments).
- `report.py` must not present `sample_fraction` as stratum eligibility coverage,
  the page-view index as a weekly traffic rate, midrank positions as inferential
  percentiles, evidence grade as statistical confidence, or the output as sales
  forecasting or a representative marketplace estimate.
- Must not use system-random or network-loaded assets in the HTML; output is
  self-contained and deterministic.
- Must not add a repository method, column, table, index, or schema change;
  must not modify tests written by another agent (`chunk-11` writes its own
  tests this run).

## 12. Open questions / assumptions

### 12.0 Lead rulings (2026-09-22) — plan frozen on these

Each ruling is grounded in cited SRS/dependency-map/interface text or, where the
SRS is silent, is a plan-level choice with the substitutes named. The planner's
six questions are preserved below with their rulings attached.

1. **Dashboard run selection — ruled: (a) `report.py` takes `run_id`; Chunk 12 owns
   selection.** Grounded: dependency-map §Chunk 12 assigns "completed-run and
   failed-run selection for dashboard reads" to Chunk 12; LREQ-CLI-020's module
   cell is `cli.py, report.py` with "CLI is only a caller of the report renderer";
   no repository run-listing method exists (`database.py` `Repository` protocol
   exposes only per-`run_id` reads). Chunk 11 adds **no** repository method and
   touches no file outside §6. If a listing read is needed later it is a Chunk 12
   additive `database.py` read (Chunk 10 precedent, `interfaces/chunk-10.md` §5/§8).
2. **Fallback-row field derivation — ruled: (b) persisted-only; non-derivable
   fields are `None`.** Grounded: dependency-map §Chunk 10's fallback branch exists
   only "if implementation instead omits those rows"; the current implementation
   writes them (`pipeline._persist_failure_limitation_rows`), so the fallback is
   defensive. Deriving counts would re-encode Chunk 3/4B canonicalization
   semantics; SRS §1.2 and §7.2 forbid rendering missing as zero. The persisted
   discovery/sample observations still appear in the detail panel.
3. **Preflight observations source — ruled: (a) run-level summary + per-identity
   `enrichment_observations` suffice; no separate read model.** Grounded:
   `interfaces/chunk-6A.md` §5.5 relocates the preflight-only fields to
   `runs.identity_preflight_summary_json`; zero-attempt `insufficient` runs write
   zero observation rows, which is itself a readable state.
4. **Output format — ruled: HTML is required; the text renderer is in scope as an
   additive convenience.** Grounded: LREQ-RPT-010 names a "local read-only HTML
   report or dashboard"; nothing forbids an extra text renderer. `write_run_report`
   defaults to `html`; `"text"` is the only other accepted `fmt`.
5. **Run-level `limitations` — ruled: render per-category warnings/limitations;
   `RunReportView.limitations` is `()` because no run-level column is confirmed.**
   Grounded: `PipelineResult.limitations` is a return value, not a persisted
   column; `_persist_failure_limitation_rows` persists per-category redacted
   strings into `category_scores.warnings_json`. The run-level limitations from
   `PipelineResult` are Chunk 12's to surface; Chunk 11 must not invent a column.
6. **`rank` source — ruled: derive from
   `ranking_sensitivity_json.ranked_categories`; `rank = None` when absent.**
   Grounded: `interfaces/chunk-9B.md` — `ranked_categories` is exactly
   `BaseCandidateSet.base_rankable_candidates` in the deterministic
   `(-score, category)` order; an empty candidate set records the explicit
   empty-candidate status and returns null stability. The report never derives
   rank by sorting the composite itself.

**Recorded contract hazard (not resolved here; owner Chunk 10).** Chunk 10's
`_persist_failure_limitation_rows` writes `ranking_sensitivity_json="{}"` on
failed-preflight rows, whereas dependency-map §6.3 requires the field to "retain an
explicit empty-candidate or insufficient-candidate status rather than becoming an
empty, ambiguous object", and Chunk 9B's frozen contract emits the full key set
with nulls. Chunk 11 consumes the shape read-only and therefore treats **both**
`"{}"` and an absent/empty `ranked_categories` as "no displayed rank / no
stability"; it must not redefine or rewrite the shape. The wording fix belongs to
Chunk 10/9B, not this chunk.

### 12.1 Planner questions (as raised, now answered by §12.0)

1. **Dashboard run selection.** There is no repository method that lists runs
   (`database.py` has only `get_run(run_id)` and per-run reads), and
   dependency-map §Chunk 12 assigns "completed-run and failed-run selection for
   dashboard reads" to Chunk 12. Assumption for this plan: `report.py` accepts a
   `run_id` and Chunk 12 selects/defaults it. **Confirm** whether Chunk 12 may
   read the DB directly for a run id, or whether a minimal read-only listing
   helper must be added to `database.py` — and if so, by which chunk (adding one
   here would touch a file outside §6).
2. **Fallback-row field derivation.** dependency-map §Chunk 10 says that if
   null-score `category_scores` rows are absent, Chunk 11 "must join runs,
   discovery, samples, and preflight observations to provide the same
   one-row-per-category view." For fields not derivable without re-deriving
   metric semantics (`discovered_population_count`, `enriched_sample_count`,
   coverage values), this plan sets them to `None` rather than computing them.
   **Confirm** that `None` (with the persisted discovery/sample observations
   still shown in the detail panel) satisfies "the same one-row-per-category
   view", or state which fields must be derived from
   `raw_discovery_observations`/`sample_members` and by what rule.
3. **Preflight observations source.** No repository read method returns preflight
   observations directly; successful preflight responses are persisted as
   `enrichment_observations` (`pipeline.persist_preflight`) and the run-level
   summary is `runs.identity_preflight_summary_json`. **Confirm** the renderer
   should surface only the run-level summary/status and per-identity
   `enrichment_observations` (this plan's assumption), or whether a separate
   preflight read model is required.
4. **Output format default.** SRS §10 requires "HTML report or dashboard";
   this plan defaults `write_run_report` to HTML and also offers text. **Confirm**
   text output is desired/in scope (it adds surface and tests) or HTML-only is
   preferred.
5. **Run-level `limitations`.** `PipelineResult.limitations` is returned to
   Chunk 12 but is not clearly persisted per run in a column this chunk can read
   (the fallback writes per-category limitation strings but there is no
   confirmed run-level column). **Confirm** the read source for run-level
   limitations; if none exists, run-level limitations cannot be rendered and the
   per-category warnings are the substitute.
6. **`rank` source.** `category_scores` has no rank column; this plan derives
   `rank` from `ranking_sensitivity_json.ranked_categories` (balanced order).
   **Confirm** that is the authoritative displayed rank, or specify another.