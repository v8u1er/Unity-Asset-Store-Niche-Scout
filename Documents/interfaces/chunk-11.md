# Chunk 11 — Report renderer and read-only dashboard (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-11-report-renderer-and-read-only-dashboard.md` §5 (`Status: FROZEN`, 2026-09-22, as frozen after the lead rulings recorded in §12.0), reproduced as the frozen public contract.
Implementation: `src/niche_scout/report.py` (the one-line stub is replaced; no other source file changes).

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/report.py` | **I/O + render** | Disk/DB read and local file write; string/HTML output. Must not import `metrics`, `scoring`, `collector*`, `config`, `pipeline`, `cli`, or any network module. Must not read the clock and takes no clock parameter. Renders persisted values verbatim; never recomputes a metric, component, score, evidence grade, rankability, or sensitivity value. |

Purity is unchanged: `metrics.py` and `scoring.py` are untouched (`check_import_boundaries` passes). The report consumes `database.SqliteRepository` and `database.parse_stratum_statistics` plus read-only `models` names.

## 2. Constants

```python
COMPONENT_RENDER_ORDER: tuple[str, ...] = ("D", "C", "R", "Q")
HEURISTIC_STATEMENT: str   # fixed LREQ-RPT-050 statement; constant text, never composed per render
```

`HEURISTIC_STATEMENT` names the determinism/within-run-heuristic nature, the
not-calibrated-against-sales/revenue/downloads/conversion disclaimer, the
not-statistically-representative disclaimer, and all six required distinctions
(pagination completion vs immutable snapshot completeness; page-view index vs weekly
traffic rate; descriptive midranks vs inferential percentiles; stratum eligibility
coverage vs sample fraction; deterministic-sample evidence vs statistical
representativeness; evidence grade vs statistical confidence).

## 3. Exception surface

```python
class ReportError(RuntimeError): ...
class RunNotFoundError(ReportError): ...
```

`RunNotFoundError` is raised when `get_run(run_id)` returns `None`.

## 4. Public types

```python
@dataclass(frozen=True, slots=True)
class StratumReportRow:
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    population_count: int
    selected_count: int
    usable_demand_count: int | None
    usable_recent_count: int | None
    usable_quality_count: int | None
    usable_status: str
    eligibility_rule: str | None

@dataclass(frozen=True, slots=True)
class ReportWarning:
    code: str                 # a models.WarningCode value or an observed preflight/limitation code; never invented
    category: str | None

@dataclass(frozen=True, slots=True)
class RawMetricInputs:
    demand_per_asset_raw: float | None
    demand_median_raw: float | None
    breadth_raw: float | None
    recent_share_raw: float | None
    median_age_raw: float | None
    quality_raw: float | None

@dataclass(frozen=True, slots=True)
class CategoryReportRow:
    category: str
    rank: int | None                  # from ranking_sensitivity_json.ranked_categories; None when absent
    market_opportunity_score: float | None
    score_state: str
    component_d: float | None
    component_c: float | None
    component_r: float | None
    component_q: float | None
    missing_components: tuple[str, ...]
    discovered_population_count: int | None
    enriched_sample_count: int | None
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
    raw_metric_inputs: RawMetricInputs | None

@dataclass(frozen=True, slots=True)
class RunReportView:
    run_id: str
    status: str
    run_started_at_utc: datetime
    scoring_cutoff_utc: datetime | None
    completed_at_utc: datetime | None
    identity_preflight_status: str
    page_view_semantics_status: str
    categories: tuple[CategoryReportRow, ...]
    warnings: tuple[ReportWarning, ...]
    limitations: tuple[str, ...]
    heuristic_statement: str
```

Every optional field is `None` when the persisted value is null/unavailable; a
value is never converted to `0`, `0.0`, `False`, or an empty string.
`RunReportView.categories` is ordered `(-rank, category)` for ranked rows then
ascending category for unranked rows (deterministic). `RunReportView.limitations`
is `()` because no run-level limitation column is persisted; per-category warnings
carry the limitations.

## 5. Public functions

```python
def load_run_report_view(repository: "SqliteRepository", run_id: str) -> RunReportView:
    """Read one run's report model. Database reads only; no clock, no network.
    Raises RunNotFoundError when get_run(run_id) is None. One category_scores row
    per category is the primary source; when a requested category has no row, the
    failed-run fallback builds one from runs, raw discovery observations,
    sample_members, and the persisted preflight fields, with non-derivable values
    None (never fabricated). Never computes a metric, component, score, evidence
    grade, rankability, or sensitivity value."""

def render_run_report_html(view: RunReportView) -> str:
    """One self-contained HTML document (inline CSS/JS, no external assets, no
    network) with a sortable primary table covering every LREQ-RPT-020 column and a
    detail panel per category covering every LREQ-RPT-030 item. Deterministic for a
    fixed view; no clock."""

def render_run_report_text(view: RunReportView) -> str:
    """Plain-text equivalent carrying the same mandatory fields and
    HEURISTIC_STATEMENT. Deterministic; no clock."""

def write_run_report(
    repository: "SqliteRepository",
    run_id: str,
    output_path: Path,
    *,
    fmt: str = "html",
) -> Path:
    """load + render + write output_path. fmt is "html" or "text"; any other value
    raises ValueError. Local filesystem write only; no network. Propagates
    RunNotFoundError."""

def render_dashboard_html(repository: "SqliteRepository", run_id: str) -> str:
    """Convenience for the Chunk 12 dashboard command: load + render the read-only
    dashboard for run_id. Database reads only; initiates no discovery or
    enrichment (LREQ-CLI-020). Raises RunNotFoundError when absent."""
```

## 6. Read model and frozen shapes consumed (read-only, never redefined)

- Primary source: `get_run`, `get_category_scores`.
- Fallback when a `category_scores` row is absent (dependency-map §Chunk 10
  clarification): one row per category in `runs.categories_json` built from
  `iter_raw_discovery_observations`, `get_sample_members`, and the persisted
  preflight fields; `evidence_grade = "insufficient"`,
  `rankability_status = "not_rankable"`, `IDENTITY_PREFLIGHT_FAILED` warning when
  preflight is `failed`/`insufficient`.
- Consumed JSON shapes (frozen by `interfaces/chunk-10.md` §6 and
  `interfaces/chunk-4B.md` §5.2): `warnings_json`, `missing_components_json`,
  `ranking_sensitivity_json`, `stratum_statistics_json` (parsed through
  `parse_stratum_statistics`). Chunk 11 parses them read-only and never rewrites
  them.

## 7. Display rules (normative)

- Missing is not zero: a null value renders an explicit "unavailable" marker and
  stays `None` in the view.
- Pre-scoring `NOT NULL DEFAULT 0`/`0.0` values on failed-preflight rows
  (`usable_demand/recent/quality_sample_count`, the three stratum-eligibility
  coverages) render as unavailable when the row is not scored; measured zeros
  render as `0`/`0.0` only for scored rows.
- A `stratum_statistics_json` entry with `usable_status = "pending"` renders as
  pending/unavailable.
- Non-rankable categories remain visible in both table and detail, with the reason
  derived only from persisted fields.
- `rank` comes from `ranking_sensitivity_json.ranked_categories`; absent → `None`.
  An empty candidate set / `ranking_sensitivity_json == "{}"` renders no rank and
  no stability.
- Output is self-contained and deterministic: explicit ordering, no RNG, no
  external asset URL, byte-identical for a fixed view.

## 8. What downstream chunks may rely on

- Chunk 12: `render_dashboard_html(repository, run_id)` for the `dashboard`
  command and `write_run_report(...)` for `run`; `RunNotFoundError` for selection
  failure. Chunk 12 owns run selection; Chunk 11 added no repository method.
- Every displayed value is persisted-only; nothing in the report is recomputed.