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
    rank: int | None                  # rank_balanced from ranking_sensitivity_json.categories; None when absent
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
- `rank` is `rank_balanced` from `ranking_sensitivity_json.categories`; absent → `None`.
  An empty candidate set / `ranking_sensitivity_json == "{}"` renders no rank and
  no stability.
- Output is self-contained and deterministic: explicit ordering, no RNG, no
  external asset URL, byte-identical for a fixed view.

## 8. What downstream chunks may rely on

- Chunk 12: `render_dashboard_html(repository, run_id)` for the `dashboard`
  command and `write_run_report(...)` for `run`; `RunNotFoundError` for selection
  failure. Chunk 12 owns run selection; Chunk 11 added no repository method.
- Every displayed value is persisted-only; nothing in the report is recomputed.

## 9. Chunk 24 revision — stratum columns in the report (2026-09-28)

**This section supersedes the stratum report fields above.** Operator-authorized
remediation (chunk-24; see `Documents/interfaces/chunk-24.md`).

- `StratumReportRow` carries `stratum_offset`/`stratum_stride` instead of
  `stratum_start_ordinal`/`stratum_end_ordinal`, parsed from the renamed
  `stratum_statistics_json` keys.
- HTML/text rendering shows the stratum's offset and stride in place of the
  ordinal interval; the "Sample strata" table otherwise renders persisted values
  verbatim.

## 10. Chunk 30 revision — dark-mode Plotly dashboard (2026-09-30)

Operator-authorized (chunk-30 D-1..D-4; plan
`chunk-30-dark-mode-plotly-dashboard.md` §2/§12). This section supersedes the
affected lines above.

- **Constants (§2).** Add `COMPONENT_WEIGHTS`, `EVIDENCE_GRADE_ORDER`,
  `COVERAGE_REFERENCE_THRESHOLDS`, `DASHBOARD_CHART_IDS`, all sourced from
  `models`/SRS §14 (never hard-coded). `EVIDENCE_GRADE_ORDER` equals the
  `EvidenceGrade` enum reversed (insufficient→strong).
- **`CategoryReportRow` (§4).** Appends `rank_demand_heavy: int | None`,
  `rank_competition_heavy: int | None`, `breadth_completeness_status: str | None`,
  `breadth_source: str | None`.
- **New type.** `RunSensitivitySummary` (frozen, `slots=True`): `policies`,
  `top_3_stability`, `top_5_stability`, `maximum_score_delta`,
  `maximum_rank_displacement`, `warning`, `reference_set_size`,
  `displacement_threshold`; every optional field is `None` when the persisted value
  is null/absent (never `0`/`False`).
- **`RunReportView` (§4).** Appends `sensitivity: RunSensitivitySummary | None`.
- **New function.** `render_run_dashboard_html(view: RunReportView) -> str` — one
  self-contained dark-mode HTML document with inline Plotly JS, fixed `div_id`s,
  no `<script src>`/`<link>`/CDN, deterministic and byte-identical for a fixed
  view; includes `HEURISTIC_STATEMENT`, the primary table, and the category detail
  panel.
- **`render_dashboard_html` (§5).** Signature unchanged; its body is repointed to
  `render_run_dashboard_html(load_run_report_view(repository, run_id))`.
  Self-containment and database-reads-only guarantees are unchanged.
- **Rank locant correction (§4 line 72, §7 line 197).** The display rank is
  `rank_balanced` from `ranking_sensitivity_json.categories`, **not**
  `ranked_categories` (`report.py:550-579`, `LREQ-SEN-020`); the earlier text is
  superseded.
- **Display rules (§7).** The category × status heatmap shows numeric D/R/Q
  stratum eligibility coverage (with the 0.50/0.80 reference lines) plus a C
  column carrying `breadth_completeness_status`/`breadth_source`, **never labelled
  "coverage"**; evidence grade uses an ordinal colour scale; a measured `0`
  renders as `0`, distinct from the `n/a` null marker; refused categories never
  share the scored axis with rankable ones; no confidence interval or error bar;
  coverage and `sample_fraction` stay distinctly labelled. `report.py` may import
  `plotly`; all other boundary rules (§1) are unchanged.

## 11. Chunk 31 revision — Dash app (2026-10-01)

Operator-authorized (chunk-31 D-2/D-3; plan
`chunk-31-dash-plotly-dashboard.md` §6, §12 R1–R8). This section supersedes the
affected lines in §1, §2, §5, §7, and §10.

- **§1 boundary rule.** `report.py` may import `dash` (and `plotly`); all other
  boundary rules are unchanged (no `metrics`/`scoring`/`collector*`/`config`/
  `pipeline`/`cli`, no clock read). The **dashboard** self-containment guarantee is
  amended: the dashboard is a **served local app**, not a self-contained HTML
  document. `render_run_report_html` / `render_run_report_text` /
  `write_run_report` keep the self-contained-HTML guarantee and the `run --report`
  file behaviour unchanged.
- **§2 constants.** Add `DASHBOARD_COMPONENT_IDS`; **remove** the
  `component_dumbbell` and `status_heatmap` pairs from `DASHBOARD_CHART_IDS` (five
  pairs remain: score_bar, contribution_stack, policy_bump, population_lollipop,
  score_quality_scatter).
- **§5 functions.** **Remove** `render_dashboard_html` and
  `render_run_dashboard_html`; add
  `build_dashboard_layout(view: RunReportView) -> html.Div` and
  `build_dashboard_app(view: RunReportView) -> dash.Dash`. The app is **view-only**:
  built from a `RunReportView`, and no callback re-queries the database.
- **§7 display rules.** Every chart carries a one-line plain-language caption and
  correct legends/axis labels (D-5). Per-category `LREQ-RPT-030` detail is
  progressive disclosure for the selected category; the shared formula list appears
  once. The primary table shows **all** `LREQ-RPT-020` labels by default (compact,
  horizontally scrollable). The coverage heatmap is removed (R4); coverage stays
  exact in the table and evidence grade is an ordinal colour on the ranked score
  bar. UI text uses the plain-language label vocabulary in the plan §5.7; tooltips
  say what a number means and what to watch for (not raw field names).

## 12. Chunk 32 revision — dashboard stylesheet and progressive disclosure (2026-10-01)

Operator-authorized (chunk-32 D-1..D-5; plan
`chunk-32-dashboard-visual-design.md` §6, §12 R1–R6). This section amends the
affected lines in §1 and §7. No public surface is added or removed.

- **§1 boundary rule.** `report.py` resolves Dash's `assets_folder` to the packaged
  directory `src/niche_scout/assets/` and ships `assets/*.css` via
  `[tool.setuptools.package-data] niche_scout = ["assets/*.css"]`. No network, no
  clock, no new dependency; all prior boundary rules (§1, §11) are unchanged.
- **§5 functions.** Signatures of `build_dashboard_layout` and
  `build_dashboard_app` are **unchanged**. New **private** helpers only:
  `_dashboard_assets_dir()`, `_disclosure(summary, children, *, open=False,
  className=None)`, `_heuristic_banner(view)`, and the constant
  `_HEURISTIC_SUMMARY`. No public function or constant is added or removed.
- **§7 display rules.** The dashboard loads the packaged `assets/dashboard.css`
  (offline; no external URL, web font, `@import`, or CDN). The `LREQ-RPT-050`
  statement, the shared formula panel, the observed-versus-inferred list, and the
  sample-strata table are rendered inside `<details>` elements whose content
  remains in the DOM; the shared formula panel and the heuristic disclosure start
  **closed**, with the one-line summary `_HEURISTIC_SUMMARY` always visible. The
  footnote keeps the `n/a`-versus-`0` notice and the provisional notice and drops
  the bullets that only restated the shared formula list. All `LREQ-RPT-020/030/
  040/050` content and Appendix C codes remain present.