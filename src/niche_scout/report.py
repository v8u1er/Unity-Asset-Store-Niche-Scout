"""Read-only report read model and local renderers (SRS-lean §10).

This module is **I/O + render**: it reads persisted rows through the frozen
``SqliteRepository`` read surface, reconstructs one :class:`RunReportView`, and
turns it into a self-contained HTML report, a plain-text equivalent, or a local
Plotly **Dash application**. It performs no network I/O, reads no clock, and
recomputes no metric, component, normalized value, composite score, evidence
grade, rankability, or sensitivity statistic: every displayed value is a
persisted value rendered verbatim (display rounding only).

The dashboard surface is a served **Dash app** (Chunk 31): a pure
:func:`build_dashboard_layout` / :func:`build_dashboard_app` pair plus the
surviving pure figure builders, with fixed component ``id``s from
:data:`DASHBOARD_COMPONENT_IDS` and fixed chart ``div_id``s from
:data:`DASHBOARD_CHART_IDS`. The static ``run --report`` path
(:func:`render_run_report_html` / :func:`render_run_report_text` /
:func:`write_run_report`) keeps its self-contained-HTML guarantee and is
untouched by the Dash layer.

Null, explicit zero, invalid, and unavailable remain distinct. A persisted
``None`` becomes ``None`` in the view and an explicit "unavailable" marker in
output; it is never converted to ``0``, ``0.0``, ``False``, or ``""``. The
schema's ``NOT NULL DEFAULT 0``/``0.0`` pre-scoring placeholders for the three
``usable_*_sample_count`` columns and the three stratum eligibility coverages
are presented as unavailable while ``score_state`` is ``unavailable`` (Chunk 4B
interface §5.3; SRS §1.2).
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc
from dash import html as dash_html

from .database import SqliteRepository, parse_stratum_statistics
from .models import (
    MIN_REQUIRED_COMPONENT_COVERAGE,
    STRONG_COMPONENT_COVERAGE,
    W_C,
    W_D,
    W_Q,
    W_R,
    CategoryScoreRecord,
    DiscoveryStatus,
    EvidenceGrade,
    IdentityPreflightStatus,
    PageViewSemanticsStatus,
    RankabilityStatus,
    RunRecord,
    ScoreState,
    WarningCode,
)

COMPONENT_RENDER_ORDER: tuple[str, ...] = ("D", "C", "R", "Q")
"""Fixed component render order; the report never imports the scoring order."""

#: Composite component weights ``(component, weight)`` in render order. Sourced
#: from the frozen ``models`` constants (SRS §14); never restated as literals.
COMPONENT_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("D", W_D),
    ("C", W_C),
    ("R", W_R),
    ("Q", W_Q),
)
"""Composite weights ``(("D", W_D), ("C", W_C), ("R", W_R), ("Q", W_Q))``."""

#: Evidence-grade ordinal, weakest first. Derived from the ``EvidenceGrade``
#: enum (``reversed``) so the ordinal source is the enum, not a second literal.
EVIDENCE_GRADE_ORDER: tuple[str, ...] = tuple(
    grade.value for grade in reversed(list(EvidenceGrade))
)
"""``("insufficient", "weak", "moderate", "strong")``."""

#: Stratum eligibility coverage reference thresholds, from the SRS §14 constants.
COVERAGE_REFERENCE_THRESHOLDS: tuple[tuple[str, float], ...] = (
    ("minimum", MIN_REQUIRED_COMPONENT_COVERAGE),
    ("strong", STRONG_COMPONENT_COVERAGE),
)
"""``(("minimum", 0.50), ("strong", 0.80))``."""

#: Fixed ``(chart key, div_id)`` pairs so Plotly never generates a random id.
#: Chunk 31 amends this tuple: the ``status_heatmap`` and ``component_dumbbell``
#: pairs are removed (R2/R4); the five surviving charts keep their ids.
DASHBOARD_CHART_IDS: tuple[tuple[str, str], ...] = (
    ("score_bar", "niche-scout-score-bar"),
    ("contribution_stack", "niche-scout-contribution-stack"),
    ("policy_bump", "niche-scout-policy-bump"),
    ("population_lollipop", "niche-scout-population-lollipop"),
    ("score_quality_scatter", "niche-scout-score-quality-scatter"),
)
"""Fixed dashboard ``div_id`` values, one per rendered chart (five charts)."""

_DASHBOARD_CHART_ID: dict[str, str] = dict(DASHBOARD_CHART_IDS)

#: Fixed ``(component id, role)`` pairs for the Dash layout tree, so no component
#: id is generated at runtime and layout determinism is machine-checkable.
DASHBOARD_COMPONENT_IDS: tuple[tuple[str, str], ...] = (
    ("chart-score-bar", "score-bar"),
    ("chart-contribution-stack", "contribution-stack"),
    ("chart-policy-bump", "policy-bump"),
    ("chart-population-lollipop", "population-lollipop"),
    ("chart-score-quality-scatter", "score-quality-scatter"),
    ("kpi-strip", "kpi-strip"),
    ("primary-table", "primary-table"),
    ("detail-panel", "detail-panel"),
    ("category-selector", "category-selector"),
    ("footnote", "footnote"),
)
"""Fixed Dash component ``id`` values, one per layout element (plan §5.1)."""

#: Fixed ``(chart component id, chart key)`` pairs mapping a Dash component id to
#: its :data:`DASHBOARD_CHART_IDS` key.
_DASHBOARD_COMPONENT_CHART_IDS: tuple[tuple[str, str], ...] = tuple(
    (component_id, chart_key)
    for (component_id, _role), (chart_key, _div_id) in zip(
        DASHBOARD_COMPONENT_IDS, DASHBOARD_CHART_IDS
    )
)

_NA = "n/a"
"""Explicit unavailable marker for charts; distinct from a measured ``0``."""

#: Plain-language vocabulary for the Dash UI (plan §5.7). Keys are the internal
#: field tokens; values are ``(human label, one-line plain explanation)``. UI
#: text uses the human label, never the raw field name or a bare acronym.
_DASHBOARD_LABELS: dict[str, tuple[str, str]] = {
    "D": (
        "Demand",
        "How much demand the category shows, from the discovered page-view "
        "index; read it as a trailing-7-day view count.",
    ),
    "C": (
        "Competition",
        "How crowded the category is by verified catalog breadth; read it as "
        "crowding, which is unavailable when breadth is incomplete.",
    ),
    "R": (
        "Recent supply",
        "How much recent supply and how new the assets are; read it as "
        "recent-ness, not total supply.",
    ),
    "Q": (
        "Quality",
        "How highly rated the assets are; read it as observed rating strength, "
        "not sales.",
    ),
    "composite": (
        "Composite score (within-run heuristic)",
        "A deterministic blend of Demand, Competition, Recent supply, and "
        "Quality; read it as a within-run ranking aid, not a sales or revenue "
        "forecast.",
    ),
    "coverage": (
        "Data coverage",
        "The share of the discovered population in strata with enough usable "
        "observations; read it as coverage, not as sample fraction.",
    ),
    "sample_fraction": (
        "Sample fraction",
        "The share of the discovered population that was sampled; read it as a "
        "sampling share, not as data coverage.",
    ),
    "evidence_grade": (
        "Evidence strength",
        "An ordinal label (insufficient, weak, moderate, strong); read it as "
        "evidence strength, not statistical confidence.",
    ),
    "top_3_stability": (
        "Top-3 rank stability",
        "How stable the top three ranks are across scoring policies; read "
        "'n/a' as too few rankable candidates.",
    ),
    "top_5_stability": (
        "Top-5 rank stability",
        "How stable the top five ranks are across scoring policies; read "
        "'n/a' as too few rankable candidates.",
    ),
    "maximum_rank_displacement": (
        "Max rank shift across policies",
        "The largest rank movement of any category between scoring policies; "
        "read a larger value as less stable ordering.",
    ),
    "rankability": (
        "Rankable?",
        "Whether the category has enough evidence to be ranked; non-rankable "
        "categories stay visible.",
    ),
}
"""Plain-language label vocabulary used by the Dash layout (plan §5.7)."""

#: Fixed one-line caption per chart (D-5), keyed by :data:`DASHBOARD_CHART_IDS`
#: chart key.
_DASHBOARD_CHART_CAPTIONS: dict[str, str] = {
    "score_bar": (
        "This shows the composite score by rank; read it as best-first, with "
        "refused categories listed at the bottom and off the score axis."
    ),
    "contribution_stack": (
        "This shows each scored category's weighted Demand/Competition/Recent "
        "supply/Quality contributions; read the stack height as the composite "
        "score, with a missing component contributing no segment."
    ),
    "policy_bump": (
        "This shows each category's rank under the three scoring policies; read "
        "a flat line as a stable rank and a crossing line as sensitivity to the "
        "policy."
    ),
    "population_lollipop": (
        "This shows the discovered population beside the enriched sample size on "
        "a log scale; read a small marker as a small sample, and a diamond at "
        "0 as a measured zero population."
    ),
    "score_quality_scatter": (
        "This shows composite score against quality with marker size set by "
        "sample fraction; read it as a secondary diagnostic, not a prediction."
    ),
}
"""One-line plain-language caption per chart, shown under each chart title."""

#: Chart titles, using the human vocabulary (never raw field names).
_DASHBOARD_CHART_TITLES: dict[str, str] = {
    "score_bar": "Composite score by rank",
    "contribution_stack": "Weighted component contributions",
    "policy_bump": "Policy rank comparison",
    "population_lollipop": "Population and sample size (log scale)",
    "score_quality_scatter": "Composite score vs quality (marker = sample fraction)",
}

#: Marker size used when ``sample_fraction`` is unavailable (documented fallback,
#: never treated as ``0``).
_SAMPLE_FRACTION_FALLBACK_MARKER: float = 8.0
#: Marker-size floor; a larger ``sample_fraction`` renders a larger marker.
_SAMPLE_FRACTION_MIN_MARKER: float = 6.0

#: Fixed x position of the explicit-zero population marker, placed left of the
#: smallest log-scale tick so a measured ``0`` is off the log axis (R5).
_POPULATION_EXPLICIT_ZERO_X: float = 0.1

#: Fixed x position of the refused-row ``n/a`` text annotations on the score bar
#: (they sit at the axis origin with no bar; they never share the scored axis).
_REFUSED_ANNOTATION_X: float = 0.0

#: Fixed pixel height for every Dash chart row.
_DASHBOARD_CHART_HEIGHT: int = 360

#: Ordinal ``(grade, colour)`` pairs for the evidence-grade colour on the score
#: bar (R4). Sourced from :data:`EVIDENCE_GRADE_ORDER` so the ordinal source is
#: the enum, not a second literal.
_EVIDENCE_GRADE_COLOURS: tuple[tuple[str, str], ...] = tuple(
    zip(EVIDENCE_GRADE_ORDER, ("#c98b8b", "#e0a458", "#8fb9a8", "#8fd694"))
)

HEURISTIC_STATEMENT: str = (
    "This score is a deterministic, within-run heuristic computed from "
    "marketplace signals and, for larger categories, a stratified sample. It "
    "has not been calibrated against sales, revenue, downloads, or conversion, "
    "and it is not a statistically representative estimate of the marketplace. "
    "The report distinguishes the following, and does not treat the left-hand "
    "value as the right-hand value: pagination completion is not immutable "
    "snapshot completeness; the page-view index is a trailing-7-day view count, "
    "stable within a run and refreshed at most daily, not a lifetime or "
    "daily-average rate; "
    "descriptive midranks are not inferential percentiles; stratum eligibility "
    "coverage is not sample fraction; deterministic-sample evidence is not "
    "statistical representativeness; and evidence grade is not statistical "
    "confidence."
)
"""Fixed LREQ-RPT-050 statement. Constant text, never composed per render."""

_UNAVAILABLE = "unavailable"
_MISSING_CLASS = "missing"

#: Raw metric input labels and their ``RawMetricInputs`` attributes. All six are
#: stratum-expanded sample-based values, so each is labelled inferred.
_RAW_METRIC_FIELDS: tuple[tuple[str, str], ...] = (
    ("demand per asset raw", "demand_per_asset_raw"),
    ("demand median raw", "demand_median_raw"),
    ("breadth raw", "breadth_raw"),
    ("recent share raw", "recent_share_raw"),
    ("median age raw", "median_age_raw"),
    ("quality raw", "quality_raw"),
)

#: Displayed values that are persisted marketplace observations.
_OBSERVED_LABELS: tuple[str, ...] = (
    "discovered population (observed)",
    "sample size (observed)",
    "census flag (observed)",
    "unique enrichment count (observed)",
    "sample fraction (observed)",
    "sampling basis (observed)",
    "cross-category overlap count (observed)",
    "sample shared with other categories (%) (observed)",
)

#: Displayed values that are sample-based stratum-expanded inferences.
_INFERRED_LABELS: tuple[str, ...] = (
    "demand per asset raw (inferred)",
    "demand median raw (inferred)",
    "breadth raw (inferred)",
    "recent share raw (inferred)",
    "median age raw (inferred)",
    "quality raw (inferred)",
    "demand stratum eligibility coverage (inferred)",
    "recent supply stratum eligibility coverage (inferred)",
    "quality stratum eligibility coverage (inferred)",
    "component D/C/R/Q (inferred)",
    "composite score (inferred)",
    "top_3_stability / top_5_stability (inferred)",
    "maximum_score_delta / maximum_rank_displacement (inferred)",
)

#: Concise formula/explanations shown in every category detail (LREQ-RPT-030).
_FORMULA_EXPLANATIONS: tuple[str, ...] = (
    "Composite score is a within-run heuristic over the available components "
    f"(D {W_D:.2f} x C {W_C:.2f} x R {W_R:.2f} x Q {W_Q:.2f}), renormalized "
    "over the available components only; it is not a sales, revenue, or "
    "download forecast.",
    "D (demand) consumes the discovered page-view index, shrunk by demand "
    "stratum eligibility coverage.",
    "C (competition) consumes verified catalog breadth; unbounded or incomplete "
    "breadth makes it unavailable.",
    "R (recent supply) consumes the recent share and median asset age, shrunk by "
    "recent-supply stratum eligibility coverage.",
    "Q (quality) consumes rating-derived quality, shrunk by quality stratum "
    "eligibility coverage.",
    "sample_fraction = enriched sample size / discovered population; it is a "
    "sampling share, not stratum eligibility coverage and not statistical "
    "representativeness.",
    "Stratum eligibility coverage is the share of the discovered population in "
    "strata that meet the applicable usable-observation minimum; it is not "
    "sample fraction.",
    "Midrank positions are descriptive within-run relative positions, not "
    "inferential percentiles.",
    "The page-view index is a trailing-7-day view count, stable within a run "
    "and refreshed at most daily, not a lifetime or daily-average rate.",
    "Pagination completion is not immutable snapshot completeness.",
    "Evidence grade is an operational within-run grade, not statistical confidence.",
)

#: Primary-table columns: ``(label, CategoryReportRow attribute)``. Every
#: LREQ-RPT-020 field is present exactly once.
_PRIMARY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("category", "category"),
    ("rank", "rank"),
    ("composite score", "market_opportunity_score"),
    ("D", "component_d"),
    ("C", "component_c"),
    ("R", "component_r"),
    ("Q", "component_q"),
    ("discovered population", "discovered_population_count"),
    ("sample size", "enriched_sample_count"),
    ("census flag", "sample_is_census"),
    ("unique enrichment count", "unique_enrichment_count"),
    ("sample fraction", "sample_fraction"),
    ("sampling basis", "sampling_basis"),
    ("cross-category overlap count", "overlap_category_count"),
    ("usable demand count", "usable_demand_sample_count"),
    ("usable recent supply count", "usable_recent_supply_sample_count"),
    ("usable quality count", "usable_quality_sample_count"),
    ("demand stratum eligibility coverage", "demand_stratum_eligibility_coverage"),
    (
        "recent supply stratum eligibility coverage",
        "recent_supply_stratum_eligibility_coverage",
    ),
    ("quality stratum eligibility coverage", "quality_stratum_eligibility_coverage"),
    ("evidence grade", "evidence_grade"),
    ("rankability", "rankability_status"),
    ("discovery status", "discovery_status"),
    ("page-view semantic status", "page_view_semantics_status"),
    ("top_3_stability", "top_3_stability"),
    ("top_5_stability", "top_5_stability"),
    ("maximum_score_delta", "maximum_score_delta"),
    ("maximum_rank_displacement", "maximum_rank_displacement"),
    ("sensitivity warning", "sensitivity_warning"),
    ("sample shared with other categories (%)", "overlap_sample_percentage"),
)

_INLINE_CSS = (
    "body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:1.5rem;"
    "color:#1b1b1b}"
    "table{border-collapse:collapse;font-size:0.85rem}"
    "th,td{border:1px solid #bbb;padding:0.25rem 0.4rem;text-align:left}"
    "th{background:#eee;cursor:pointer}"
    "td.missing{color:#a33}"
    "section.category-detail{border:1px solid #ccc;border-radius:4px;"
    "padding:0.6rem;margin:0.8rem 0}"
    "code{background:#f4f4f4;padding:0 0.2rem}"
    ".heuristic{background:#fff8dc;border:1px solid #e0c060;padding:0.6rem}"
)

_SORT_SCRIPT = (
    "(function(){"
    'var tables=document.querySelectorAll("table.sortable");'
    "tables.forEach(function(table){"
    'var headers=table.querySelectorAll("thead th");'
    "headers.forEach(function(th,index){"
    'th.addEventListener("click",function(){'
    "var tbody=table.tBodies[0];"
    "var rows=Array.prototype.slice.call(tbody.rows);"
    'var ascending=th.getAttribute("data-order")!=="asc";'
    "rows.sort(function(a,b){"
    "var x=a.cells[index].textContent.trim();"
    "var y=b.cells[index].textContent.trim();"
    "var nx=parseFloat(x);var ny=parseFloat(y);"
    "if(!isNaN(nx)&&!isNaN(ny)){return ascending?nx-ny:ny-nx;}"
    "if(x<y){return ascending?-1:1;}"
    "if(x>y){return ascending?1:-1;}"
    "return 0;});"
    "rows.forEach(function(row){tbody.appendChild(row);});"
    'headers.forEach(function(other){other.removeAttribute("data-order");});'
    'th.setAttribute("data-order",ascending?"asc":"desc");});});});})();'
)


class ReportError(RuntimeError):
    """Base class for report read-model and render failures."""


class RunNotFoundError(ReportError):
    """Raised when a requested ``run_id`` has no ``runs`` row."""


@dataclass(frozen=True, slots=True)
class StratumReportRow:
    """One parsed ``stratum_statistics_json`` object (Chunk 4B §5.2 keys)."""

    stratum_index: int
    stratum_offset: int
    stratum_stride: int
    population_count: int
    selected_count: int
    usable_demand_count: int | None
    usable_recent_count: int | None
    usable_quality_count: int | None
    usable_status: str
    eligibility_rule: str | None


@dataclass(frozen=True, slots=True)
class ReportWarning:
    """A displayed warning code with its category, or ``None`` for run level.

    ``code`` is a ``models.WarningCode`` value or a preflight/limitation code
    already observed by Chunk 10; it is never invented here.
    """

    code: str
    category: str | None


@dataclass(frozen=True, slots=True)
class RawMetricInputs:
    """The six persisted raw metric values (LREQ-RPT-030 metric inputs).

    Each field is ``None`` when the persisted value is null/unavailable; a
    ``None`` is never coerced to ``0.0``.
    """

    demand_per_asset_raw: float | None
    demand_median_raw: float | None
    breadth_raw: float | None
    recent_share_raw: float | None
    median_age_raw: float | None
    quality_raw: float | None


@dataclass(frozen=True, slots=True)
class RunSensitivitySummary:
    """Run-level persisted ranking-sensitivity summary.

    Parsed from ``ranking_sensitivity_json`` (the rows are category-sorted and
    carry one identical payload); no value is ever recomputed. Every field is
    ``None`` when the persisted value is null/absent. ``None`` is never coerced
    to ``0``/``0.0``/``False``; ``policies`` is ``()`` when absent.
    """

    policies: tuple[str, ...]
    top_3_stability: float | None
    top_5_stability: float | None
    maximum_score_delta: float | None
    maximum_rank_displacement: int | None
    warning: bool | None
    reference_set_size: int | None
    displacement_threshold: float | None


@dataclass(frozen=True, slots=True)
class CategoryReportRow:
    """One category as shown in the primary table and the detail panel.

    Every optional field is ``None`` when the persisted value is null or
    unavailable; a field is never converted to ``0``, ``0.0``, ``False``, or an
    empty string. ``rank`` is ``None`` for a category absent from
    ``ranking_sensitivity_json.ranked_categories``. ``warnings`` preserves the
    persisted code set sorted and deduplicated, and is ``()`` when
    ``warnings_json`` is ``[]``. The three ``usable_*_sample_count`` values and
    the three stratum eligibility coverages are ``None`` while ``score_state``
    is ``unavailable`` (pre-scoring placeholders).
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
    rank_demand_heavy: int | None
    rank_competition_heavy: int | None
    breadth_completeness_status: str | None
    breadth_source: str | None


@dataclass(frozen=True, slots=True)
class RunReportView:
    """The whole read model for one run.

    ``categories`` is ordered by ``(-rank, category)`` for ranked rows, then by
    ascending category for unranked rows, so rendering is deterministic.
    ``limitations`` carries redacted run-level limitation strings; it is ``()``
    because no confirmed run-level persisted column exists (never a fabricated
    zero).
    """

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
    sensitivity: RunSensitivitySummary | None


# --------------------------------------------------------------------------
# Read model
# --------------------------------------------------------------------------


def load_run_report_view(repository: SqliteRepository, run_id: str) -> RunReportView:
    """Read one run's report model. Database reads only; no clock, no network.

    Raises :class:`RunNotFoundError` when ``get_run(run_id)`` is ``None``. Uses
    one ``category_scores`` row per category as the primary source. When no row
    exists for a category named in ``runs.categories_json`` (the defensive
    failed-run fallback), builds the same one-row-per-category audit view from
    ``runs`` alone: ``evidence_grade = "insufficient"``,
    ``rankability_status = "not_rankable"``, and an ``IDENTITY_PREFLIGHT_FAILED``
    warning when preflight is ``failed`` or ``insufficient``. Every other
    unavailable field is ``None``; nothing is fabricated.
    """
    run = repository.get_run(run_id)
    if run is None:
        raise RunNotFoundError(f"run_id not found: {run_id}")

    categories = _requested_categories(run.categories_json)
    scores = {row.category: row for row in repository.get_category_scores(run_id)}

    rows_by_category: dict[str, CategoryReportRow] = {}
    for category in categories:
        score = scores.get(category)
        if score is None:
            rows_by_category[category] = _fallback_row(run, category)
        else:
            rows_by_category[category] = _row_from_score(score, run)

    ordered = _order_rows(rows_by_category)
    return RunReportView(
        run_id=run.run_id,
        status=run.status,
        run_started_at_utc=run.run_started_at_utc,
        scoring_cutoff_utc=run.scoring_cutoff_utc,
        completed_at_utc=run.completed_at_utc,
        identity_preflight_status=run.identity_preflight_status,
        page_view_semantics_status=run.page_view_semantics_status,
        categories=ordered,
        warnings=_collect_warnings(run, ordered),
        limitations=(),
        heuristic_statement=HEURISTIC_STATEMENT,
        sensitivity=_run_sensitivity(tuple(scores.values())),
    )


def _requested_categories(payload: str) -> tuple[str, ...]:
    """Parse ``runs.categories_json`` into its declared category names."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReportError(
            "runs.categories_json: stored value is not valid JSON"
        ) from exc
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) for item in decoded
    ):
        raise ReportError(
            "runs.categories_json: stored value is not a JSON array of names"
        )
    return tuple(decoded)


def _row_from_score(score: CategoryScoreRecord, run: RunRecord) -> CategoryReportRow:
    """Build one row from a persisted ``category_scores`` row."""
    pre_scoring = score.score_state == ScoreState.UNAVAILABLE.value

    def _measured(value: object) -> object:
        return None if pre_scoring else value

    rank, rank_demand_heavy, rank_competition_heavy = _ranks_from_sensitivity(
        score.ranking_sensitivity_json, score.category
    )
    return CategoryReportRow(
        category=score.category,
        rank=rank,
        market_opportunity_score=score.market_opportunity_score,
        score_state=score.score_state,
        component_d=score.component_d,
        component_c=score.component_c,
        component_r=score.component_r,
        component_q=score.component_q,
        missing_components=_parse_component_list(score.missing_components_json),
        discovered_population_count=score.discovered_population_count,
        enriched_sample_count=score.enriched_sample_count,
        sample_is_census=score.sample_is_census,
        sampling_basis=score.sampling_basis,
        sample_fraction=score.sample_fraction,
        unique_enrichment_count=score.unique_enrichment_count,
        overlap_category_count=score.overlap_category_count,
        overlap_sample_percentage=score.overlap_sample_percentage,
        usable_demand_sample_count=_measured(score.usable_demand_sample_count),
        usable_recent_supply_sample_count=_measured(
            score.usable_recent_supply_sample_count
        ),
        usable_quality_sample_count=_measured(score.usable_quality_sample_count),
        demand_stratum_eligibility_coverage=_measured(
            score.demand_stratum_eligibility_coverage
        ),
        recent_supply_stratum_eligibility_coverage=_measured(
            score.recent_supply_stratum_eligibility_coverage
        ),
        quality_stratum_eligibility_coverage=_measured(
            score.quality_stratum_eligibility_coverage
        ),
        evidence_grade=score.evidence_grade,
        rankability_status=score.rankability_status,
        discovery_status=score.discovery_status,
        page_view_semantics_status=run.page_view_semantics_status,
        top_3_stability=score.top_3_stability,
        top_5_stability=score.top_5_stability,
        maximum_score_delta=score.maximum_score_delta,
        maximum_rank_displacement=score.maximum_rank_displacement,
        sensitivity_warning=score.sensitivity_warning,
        reference_size=score.reference_size,
        computed_at_utc=score.computed_at_utc,
        warnings=_parse_warnings(score.warnings_json),
        strata=_strata_from_json(score.stratum_statistics_json),
        raw_metric_inputs=RawMetricInputs(
            demand_per_asset_raw=score.demand_per_asset_raw,
            demand_median_raw=score.demand_median_raw,
            breadth_raw=score.breadth_raw,
            recent_share_raw=score.recent_share_raw,
            median_age_raw=score.median_age_raw,
            quality_raw=score.quality_raw,
        ),
        rank_demand_heavy=rank_demand_heavy,
        rank_competition_heavy=rank_competition_heavy,
        breadth_completeness_status=score.breadth_completeness_status,
        breadth_source=score.breadth_source,
    )


def _fallback_row(run: RunRecord, category: str) -> CategoryReportRow:
    """Build the defensive audit row for a category with no score row.

    The failed-run semantics mirror Chunk 10's own missing-row branch: a
    ``request_failed`` discovery status, ``unavailable`` score state,
    ``insufficient`` evidence, ``not_rankable`` status, and an explicit
    ``IDENTITY_PREFLIGHT_FAILED`` warning only when the persisted run-level
    preflight status is ``failed`` or ``insufficient``. No count, timestamp, or
    stratum is derived.
    """
    preflight_failed = run.identity_preflight_status in (
        IdentityPreflightStatus.FAILED.value,
        IdentityPreflightStatus.INSUFFICIENT.value,
    )
    warnings = (
        (WarningCode.IDENTITY_PREFLIGHT_FAILED.value,) if preflight_failed else ()
    )
    return CategoryReportRow(
        category=category,
        rank=None,
        market_opportunity_score=None,
        score_state=ScoreState.UNAVAILABLE.value,
        component_d=None,
        component_c=None,
        component_r=None,
        component_q=None,
        missing_components=COMPONENT_RENDER_ORDER,
        discovered_population_count=None,
        enriched_sample_count=None,
        sample_is_census=None,
        sampling_basis=None,
        sample_fraction=None,
        unique_enrichment_count=None,
        overlap_category_count=None,
        overlap_sample_percentage=None,
        usable_demand_sample_count=None,
        usable_recent_supply_sample_count=None,
        usable_quality_sample_count=None,
        demand_stratum_eligibility_coverage=None,
        recent_supply_stratum_eligibility_coverage=None,
        quality_stratum_eligibility_coverage=None,
        evidence_grade=EvidenceGrade.INSUFFICIENT.value,
        rankability_status=RankabilityStatus.NOT_RANKABLE.value,
        discovery_status=DiscoveryStatus.REQUEST_FAILED.value,
        page_view_semantics_status=run.page_view_semantics_status,
        top_3_stability=None,
        top_5_stability=None,
        maximum_score_delta=None,
        maximum_rank_displacement=None,
        sensitivity_warning=None,
        reference_size=None,
        computed_at_utc=None,
        warnings=warnings,
        strata=(),
        raw_metric_inputs=RawMetricInputs(
            demand_per_asset_raw=None,
            demand_median_raw=None,
            breadth_raw=None,
            recent_share_raw=None,
            median_age_raw=None,
            quality_raw=None,
        ),
        rank_demand_heavy=None,
        rank_competition_heavy=None,
        breadth_completeness_status=None,
        breadth_source=None,
    )


def _order_rows(
    rows_by_category: dict[str, CategoryReportRow],
) -> tuple[CategoryReportRow, ...]:
    """Order ranked rows by ``(rank, category)``, then unranked by category.

    Rank 1 is the best balanced composite score (SRS §9.3 ``LREQ-SEN-020``), so
    ascending ``rank`` renders best-first and keeps the rank column monotone with
    the adjacent composite-score column (plan §6.2, OQ-8). Unranked rows follow,
    ascending by category.
    """
    ranked = [row for row in rows_by_category.values() if row.rank is not None]
    unranked = [row for row in rows_by_category.values() if row.rank is None]
    ranked.sort(key=lambda row: (row.rank, row.category))
    unranked.sort(key=lambda row: row.category)
    return tuple(ranked) + tuple(unranked)


def _rank_from_sensitivity(payload: str, category: str) -> int | None:
    """Return ``rank_balanced`` for ``category`` from ``ranking_sensitivity_json``.

    The payload's ``categories`` list carries the persisted 1-based balanced
    ranks (SRS §9.3 ``LREQ-SEN-020``); ``ranked_categories`` is only the
    base-candidate (requested) order and is never used for the display rank
    (plan §6.2, D4). Returns ``None`` for invalid JSON, a non-object value, a
    missing/empty/non-list ``categories``, no matching entry, a non-mapping
    matching entry, or a missing/non-``int`` ``rank_balanced`` (``bool`` is not
    treated as an ``int``).
    """
    return _ranks_from_sensitivity(payload, category)[0]


def _ranks_from_sensitivity(
    payload: str, category: str
) -> tuple[int | None, int | None, int | None]:
    """Return the three persisted per-policy ranks for ``category``.

    Reads ``rank_balanced``, ``rank_demand_heavy``, and
    ``rank_competition_heavy`` from ``ranking_sensitivity_json.categories``
    (SRS §9.3 ``LREQ-SEN-020``). Any element is ``None`` for an invalid payload,
    a non-object, a missing/empty/non-list ``categories``, no matching entry, a
    non-mapping entry, or a missing/non-``int`` value (``bool`` is not treated as
    an ``int``). A category present in ``categories`` with only ``rank_balanced``
    yields ``(rank_balanced, None, None)``.
    """
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return (None, None, None)
    if not isinstance(decoded, dict):
        return (None, None, None)
    categories = decoded.get("categories")
    if not isinstance(categories, list) or not categories:
        return (None, None, None)
    for entry in categories:
        if not isinstance(entry, dict):
            continue
        if entry.get("category") != category:
            continue
        return (
            _optional_rank(entry.get("rank_balanced")),
            _optional_rank(entry.get("rank_demand_heavy")),
            _optional_rank(entry.get("rank_competition_heavy")),
        )
    return (None, None, None)


def _optional_rank(value: object) -> int | None:
    """Return ``value`` as an ``int`` rank, or ``None`` if it is not one.

    ``bool`` is never accepted as an ``int`` (a ``True`` rank is a decode
    error, not the rank ``1``).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _run_sensitivity(
    scores: Sequence[CategoryScoreRecord],
) -> RunSensitivitySummary | None:
    """Parse the run-level summary from the persisted ``category_scores`` payloads.

    Every scored row carries the same run-level ``ranking_sensitivity_json``,
    but a failed category persists ``"{}"`` and ``get_category_scores`` orders by
    ``category ASC``, so a failed category may sort first. Rows are therefore
    scanned for the first payload that decodes to a non-empty object, and the
    summary is built from it; ``None`` is returned only when no row carries a
    usable payload. Every present-but-null output stays ``None``.
    """
    for score in scores:
        try:
            decoded = json.loads(score.ranking_sensitivity_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(decoded, dict) or not decoded:
            continue
        policies = decoded.get("policies")
        if isinstance(policies, list) and all(
            isinstance(item, str) for item in policies
        ):
            policy_names: tuple[str, ...] = tuple(policies)
        else:
            policy_names = ()
        return RunSensitivitySummary(
            policies=policy_names,
            top_3_stability=_optional_float(decoded.get("top_3_stability")),
            top_5_stability=_optional_float(decoded.get("top_5_stability")),
            maximum_score_delta=_optional_float(decoded.get("maximum_score_delta")),
            maximum_rank_displacement=_optional_rank(
                decoded.get("maximum_rank_displacement")
            ),
            warning=_optional_bool(decoded.get("warning")),
            reference_set_size=_optional_rank(decoded.get("reference_set_size")),
            displacement_threshold=_optional_float(
                decoded.get("displacement_threshold")
            ),
        )
    return None


def _optional_float(value: object) -> float | None:
    """Return ``value`` as a ``float`` or ``None``; ``bool`` is not a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _optional_bool(value: object) -> bool | None:
    """Return ``value`` only when it is a JSON boolean; else ``None``."""
    if isinstance(value, bool):
        return value
    return None


def _parse_component_list(payload: str) -> tuple[str, ...]:
    """Parse ``missing_components_json`` read-only, preserving order."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReportError(
            "category_scores.missing_components_json: stored value is not valid JSON"
        ) from exc
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) for item in decoded
    ):
        raise ReportError(
            "category_scores.missing_components_json: stored value is not a JSON "
            "array of component keys"
        )
    return tuple(decoded)


def _parse_warnings(payload: str) -> tuple[str, ...]:
    """Parse ``warnings_json`` into a sorted, deduplicated tuple of codes."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReportError(
            "category_scores.warnings_json: stored value is not valid JSON"
        ) from exc
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) for item in decoded
    ):
        raise ReportError(
            "category_scores.warnings_json: stored value is not a JSON array of codes"
        )
    return tuple(sorted(set(decoded)))


def _strata_from_json(payload: str) -> tuple[StratumReportRow, ...]:
    """Parse ``stratum_statistics_json`` via the frozen Chunk 4B helper."""
    objects = parse_stratum_statistics(payload)
    return tuple(
        StratumReportRow(
            stratum_index=int(obj["stratum_index"]),
            stratum_offset=int(obj["stratum_offset"]),
            stratum_stride=int(obj["stratum_stride"]),
            population_count=int(obj["N_h"]),
            selected_count=int(obj["n_h"]),
            usable_demand_count=_optional_int(obj["u_demand_h"]),
            usable_recent_count=_optional_int(obj["u_recent_h"]),
            usable_quality_count=_optional_int(obj["u_quality_h"]),
            usable_status=str(obj["usable_status"]),
            eligibility_rule=(
                str(obj["eligibility_rule"])
                if obj["eligibility_rule"] is not None
                else None
            ),
        )
        for obj in objects
    )


def _optional_int(value: object) -> int | None:
    """Return ``value`` as an ``int`` or ``None`` when it is JSON ``null``."""
    if value is None:
        return None
    return int(value)


def _collect_warnings(
    run: RunRecord, rows: tuple[CategoryReportRow, ...]
) -> tuple[ReportWarning, ...]:
    """Aggregate displayed warnings: per-category rows plus run-level codes.

    Run-level codes are derived only from persisted ``runs`` status fields and
    use only ``models.WarningCode`` values; no code is invented.
    """
    collected: list[ReportWarning] = []
    seen: set[tuple[str, str | None]] = set()
    for row in rows:
        for code in row.warnings:
            key = (code, row.category)
            if key not in seen:
                seen.add(key)
                collected.append(ReportWarning(code=code, category=row.category))
    run_codes: list[str] = []
    if run.identity_preflight_status in (
        IdentityPreflightStatus.FAILED.value,
        IdentityPreflightStatus.INSUFFICIENT.value,
    ):
        run_codes.append(WarningCode.IDENTITY_PREFLIGHT_FAILED.value)
    if run.page_view_semantics_status == PageViewSemanticsStatus.CONTRADICTED.value:
        run_codes.append(WarningCode.PAGE_VIEW_SEMANTICS_CONTRADICTED.value)
    for code in sorted(set(run_codes)):
        key = (code, None)
        if key not in seen:
            seen.add(key)
            collected.append(ReportWarning(code=code, category=None))
    return tuple(collected)


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------


def _fmt(value: object) -> str:
    """Format one value for display; ``None`` is an explicit unavailable marker."""
    if value is None:
        return _UNAVAILABLE
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def _esc(value: object) -> str:
    """Escape one display value for HTML text content and attributes."""
    return html.escape(_fmt(value), quote=True)


def _td(value: object) -> str:
    """Render one table cell, flagging an unavailable value with a class."""
    if value is None:
        return f'<td class="{_MISSING_CLASS}">{_UNAVAILABLE}</td>'
    return f"<td>{_esc(value)}</td>"


def _format_timestamp(value: datetime | None) -> str:
    """Render an aware-UTC timestamp as ISO-8601 with a ``Z`` suffix."""
    if value is None:
        return _UNAVAILABLE
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _rankability_note(row: CategoryReportRow) -> str:
    """Explain a row's rankability from persisted fields only."""
    details: list[str] = []
    if row.missing_components:
        details.append("missing components: " + ", ".join(row.missing_components))
    details.append(f"evidence grade: {row.evidence_grade}")
    if row.discovery_status:
        details.append(f"discovery status: {row.discovery_status}")
    if row.page_view_semantics_status:
        details.append(f"page-view semantic status: {row.page_view_semantics_status}")
    if row.warnings:
        details.append("warnings: " + ", ".join(row.warnings))
    if row.rank is None:
        details.append("no rank recorded in ranking_sensitivity_json")
    return f"{row.rankability_status}: " + "; ".join(details)


def _raw_metric_entries(
    row: CategoryReportRow,
) -> tuple[tuple[str, object], ...]:
    """Return the six raw metric input ``(label, value)`` pairs."""
    raw = row.raw_metric_inputs
    if raw is None:
        return tuple((label, None) for label, _ in _RAW_METRIC_FIELDS)
    return tuple(
        (label, getattr(raw, attribute)) for label, attribute in _RAW_METRIC_FIELDS
    )


# --------------------------------------------------------------------------
# HTML renderer
# --------------------------------------------------------------------------


def render_run_report_html(view: RunReportView) -> str:
    """Return one self-contained HTML document for ``view``.

    Inline CSS/JS only: no external script, stylesheet, or asset URL, so opening
    the document issues no network request. Covers every LREQ-RPT-020 column in
    a sortable primary table and every LREQ-RPT-030 item in a per-category detail
    panel. Deterministic for a fixed ``view``; no clock is read.
    """
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Niche Scout report - {_esc(view.run_id)}</title>",
        f"<style>{_INLINE_CSS}</style>",
        "</head>",
        "<body>",
        "<h1>Niche Scout report</h1>",
        _render_run_header_html(view),
        f'<p class="heuristic" id="heuristic">{_esc(view.heuristic_statement)}</p>',
        "<h2>Warnings</h2>",
        _render_run_warnings_html(view),
        "<h2>Primary table</h2>",
        _render_primary_table_html(view),
        "<h2>Category details</h2>",
    ]
    for index, row in enumerate(view.categories):
        parts.append(_render_category_detail_html(view, row, index))
    parts.extend([f"<script>{_SORT_SCRIPT}</script>", "</body>", "</html>"])
    return "\n".join(parts) + "\n"


def _render_run_header_html(view: RunReportView) -> str:
    items = (
        ("Run ID", view.run_id),
        ("Run status", view.status),
        ("Run started (UTC)", _format_timestamp(view.run_started_at_utc)),
        ("Scoring cutoff (UTC)", _format_timestamp(view.scoring_cutoff_utc)),
        ("Completed (UTC)", _format_timestamp(view.completed_at_utc)),
        ("Identity preflight status", view.identity_preflight_status),
        (
            "Page-view semantics (run level)",
            view.page_view_semantics_status,
        ),
    )
    rows = "".join(
        f"<dt>{_esc(label)}</dt><dd>{_esc(value)}</dd>" for label, value in items
    )
    return f'<dl class="run-header">{rows}</dl>'


def _render_run_warnings_html(view: RunReportView) -> str:
    if not view.warnings:
        return '<p class="missing">no warnings recorded</p>'
    items = "".join(
        f"<li><code>{_esc(warning.code)}</code>"
        f" ({_esc(warning.category) if warning.category else 'run level'})</li>"
        for warning in view.warnings
    )
    return f"<ul>{items}</ul>"


def _render_primary_table_html(view: RunReportView) -> str:
    headers = "".join(f"<th>{_esc(label)}</th>" for label, _ in _PRIMARY_COLUMNS)
    body: list[str] = []
    for row in view.categories:
        cells = "".join(
            _td(getattr(row, attribute)) for _, attribute in _PRIMARY_COLUMNS
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        '<table id="primary" class="sortable">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table>"
    )


def _render_category_detail_html(
    view: RunReportView, row: CategoryReportRow, index: int
) -> str:
    parts: list[str] = [f'<section class="category-detail" id="detail-{index}">']
    parts.append(f"<h3>Category: {_esc(row.category)}</h3>")
    parts.append(
        f'<p class="rankability">Rankability: <code>{_esc(row.rankability_status)}'
        f"</code>. {_esc(_rankability_note(row))}</p>"
    )
    parts.append("<h4>Formulas and explanations</h4>")
    parts.append(
        "<ul>"
        + "".join(f"<li>{_esc(line)}</li>" for line in _FORMULA_EXPLANATIONS)
        + "</ul>"
    )
    parts.append("<h4>Metric inputs</h4>")
    parts.append(
        "<ul>"
        + "".join(
            f"<li>{_esc(label)} (inferred): {_esc(value)}</li>"
            for label, value in _raw_metric_entries(row)
        )
        + "</ul>"
    )
    parts.append("<h4>Observed versus inferred</h4>")
    parts.append(
        "<ul>"
        + "".join(f"<li>{_esc(label)}</li>" for label in _OBSERVED_LABELS)
        + "".join(f"<li>{_esc(label)}</li>" for label in _INFERRED_LABELS)
        + "</ul>"
    )
    parts.append("<h4>Sample strata</h4>")
    parts.append(_render_strata_html(row))
    parts.append("<h4>Warnings</h4>")
    if row.warnings:
        parts.append(
            "<ul>"
            + "".join(f"<li><code>{_esc(code)}</code></li>" for code in row.warnings)
            + "</ul>"
        )
    else:
        parts.append('<p class="missing">no warnings recorded</p>')
    parts.append("<h4>Timestamps</h4>")
    parts.append(_render_timestamps_html(view, row))
    parts.append("</section>")
    return "".join(parts)


def _render_strata_html(row: CategoryReportRow) -> str:
    if not row.strata:
        return '<p class="missing">no strata recorded</p>'
    headers = (
        "stratum",
        "offset",
        "stride",
        "N_h (discovered population)",
        "n_h (sampled population)",
        "u_demand_h",
        "u_recent_h",
        "u_quality_h",
        "usable status",
        "eligibility rule",
    )
    head = "".join(f"<th>{_esc(label)}</th>" for label in headers)
    body = "".join(
        "<tr>"
        + "".join(
            _td(value)
            for value in (
                stratum.stratum_index,
                stratum.stratum_offset,
                stratum.stratum_stride,
                stratum.population_count,
                stratum.selected_count,
                stratum.usable_demand_count,
                stratum.usable_recent_count,
                stratum.usable_quality_count,
                stratum.usable_status,
                stratum.eligibility_rule,
            )
        )
        + "</tr>"
        for stratum in row.strata
    )
    return (
        '<table class="strata">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _render_timestamps_html(view: RunReportView, row: CategoryReportRow) -> str:
    items = (
        ("Category computed (UTC)", _format_timestamp(row.computed_at_utc)),
        ("Run started (UTC)", _format_timestamp(view.run_started_at_utc)),
        ("Scoring cutoff (UTC)", _format_timestamp(view.scoring_cutoff_utc)),
        ("Completed (UTC)", _format_timestamp(view.completed_at_utc)),
    )
    rows = "".join(
        f"<dt>{_esc(label)}</dt><dd>{_esc(value)}</dd>" for label, value in items
    )
    return f"<dl>{rows}</dl>"


# --------------------------------------------------------------------------
# Dark-mode Plotly dashboard (pure helpers)
# --------------------------------------------------------------------------


def _scored_rows(view: RunReportView) -> tuple[CategoryReportRow, ...]:
    """Rows with ``rank is not None``, in view order.

    These are the only rows allowed on the scored axis; refused/unranked rows
    never share that axis with them.
    """
    return tuple(row for row in view.categories if row.rank is not None)


def _refused_rows(view: RunReportView) -> tuple[CategoryReportRow, ...]:
    """Rows with ``rank is None`` (refused/unranked), in view order.

    They are never placed on the scored axis; they render as ``n/a``
    annotations with no bar.
    """
    return tuple(row for row in view.categories if row.rank is None)


def _component_contributions(
    row: CategoryReportRow,
) -> tuple[tuple[str, float], ...]:
    """Renormalised weighted contributions of the composite score, ordered D,C,R,Q.

    ``contribution_i = W_i * x_i / sum(W_j for available j)`` where an available
    component is one whose value is not ``None``. With all four available the
    contributions sum to the persisted composite score. A missing component is
    omitted (never a zero-height segment); no component available yields ``()``.
    """
    available = [
        (name, weight, getattr(row, f"component_{name.lower()}"))
        for name, weight in COMPONENT_WEIGHTS
    ]
    weight_sum = sum(weight for _, weight, value in available if value is not None)
    if weight_sum == 0.0:
        return ()
    return tuple(
        (name, weight * float(value) / weight_sum)
        for name, weight, value in available
        if value is not None
    )


def _evidence_grade_position(grade: str) -> int | None:
    """Ordinal position in ``EVIDENCE_GRADE_ORDER`` (insufficient=0 .. strong=3).

    Returns ``None`` for an unknown grade so the colour scale stays ordinal
    rather than categorical.
    """
    try:
        return EVIDENCE_GRADE_ORDER.index(grade)
    except ValueError:
        return None


def _policy_rank_rows(
    view: RunReportView,
) -> tuple[tuple[str, int | None, int | None, int | None], ...]:
    """One ``(category, balanced, demand_heavy, competition_heavy)`` per scored row.

    Scored rows only, in view order; no rank is recomputed.
    """
    return tuple(
        (
            row.category,
            row.rank,
            row.rank_demand_heavy,
            row.rank_competition_heavy,
        )
        for row in _scored_rows(view)
    )


def _kpi_tiles(
    view: RunReportView,
) -> tuple[tuple[str, float | int | None], ...]:
    """The three run-level KPI tiles in fixed order; ``None`` is an ``n/a`` tile.

    Reads ``top_3_stability``, ``top_5_stability``, and
    ``maximum_rank_displacement`` from ``view.sensitivity``; ``None`` is never
    rendered as ``0``.
    """
    summary = view.sensitivity
    if summary is None:
        return (
            ("top_3_stability", None),
            ("top_5_stability", None),
            ("maximum_rank_displacement", None),
        )
    return (
        ("top_3_stability", summary.top_3_stability),
        ("top_5_stability", summary.top_5_stability),
        ("maximum_rank_displacement", summary.maximum_rank_displacement),
    )


# --------------------------------------------------------------------------
# Dark-mode Plotly dashboard (figure builders, deterministic; no I/O)
# --------------------------------------------------------------------------


def _policy_axis_labels(view: RunReportView) -> tuple[str, ...]:
    """Return the policy x-axis labels, derived from the persisted policy list.

    Falls back to the frozen three-policy render order when ``view.sensitivity``
    is absent; the values are policy names the report never recomputes.
    """
    summary = view.sensitivity
    if summary is not None and summary.policies:
        return summary.policies
    return ("balanced", "demand_heavy", "competition_heavy")


def _evidence_colour(grade: str) -> str:
    """Return the ordinal evidence-grade colour, or a neutral colour if unknown.

    The scale is ordinal via :data:`EVIDENCE_GRADE_ORDER`/``_EVIDENCE_GRADE_COLOURS``
    (R4); an unrecognised grade maps to the weakest colour rather than to a
    categorical palette.
    """
    position = _evidence_grade_position(grade)
    if position is None:
        return _EVIDENCE_GRADE_COLOURS[0][1]
    return _EVIDENCE_GRADE_COLOURS[position][1]


def _base_layout(title: str) -> dict:
    """Return the fixed dark-mode layout shared by every dashboard figure."""
    return {
        "title": {"text": title, "font": {"color": "#e6e9ee"}},
        "paper_bgcolor": "#1b2029",
        "plot_bgcolor": "#1b2029",
        "font": {"color": "#e6e9ee", "size": 12},
        "margin": {"l": 140, "r": 24, "t": 48, "b": 40},
        "showlegend": True,
        "legend": {"bgcolor": "#222833", "font": {"color": "#e6e9ee"}},
        "xaxis": {"gridcolor": "#2c3440", "zerolinecolor": "#2c3440"},
        "yaxis": {"gridcolor": "#2c3440", "zerolinecolor": "#2c3440"},
    }


def _component_label(name: str) -> str:
    """Return the human label for a component key (``D`` -> ``Demand``)."""
    return _DASHBOARD_LABELS[name][0]


def _score_bar_figure(view: RunReportView) -> go.Figure:
    """Ranked horizontal composite-score bar with a gap before refused rows.

    Evidence grade is encoded as an **ordinal colour** on the bar (R4): the bar
    colours come from :func:`_evidence_colour`, and the exact grade text is in
    the hover and the primary table. The bar trace carries **scored rows only**;
    refused rows render as ``n/a`` text annotations with no bar and never share
    the scored axis. An explicit ``0.0`` renders a zero-length bar labelled ``0``
    while an unavailable (``None``) composite is labelled ``n/a``.
    """
    scored = _scored_rows(view)
    refused = _refused_rows(view)
    labels = [row.category for row in scored]
    values: list[float] = []
    texts: list[str] = []
    colours: list[str] = []
    customdata: list[str] = []
    for row in scored:
        if row.market_opportunity_score is None:
            values.append(0.0)
            texts.append(_NA)
        else:
            values.append(float(row.market_opportunity_score))
            texts.append(format(row.market_opportunity_score, ".6g"))
        colours.append(_evidence_colour(row.evidence_grade))
        customdata.append(row.evidence_grade)
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            text=texts,
            textposition="outside",
            marker={"color": colours},
            customdata=customdata,
            hovertemplate=(
                "%{y}: %{text}<br>evidence strength: %{customdata}<extra></extra>"
            ),
        )
    )
    if refused:
        figure.add_trace(
            go.Scatter(
                x=[_REFUSED_ANNOTATION_X] * (len(refused) + 1),
                y=[" "] + [f"{row.category} (refused)" for row in refused],
                mode="text",
                text=[""] + [_NA] * len(refused),
                textposition="middle right",
                name="refused (n/a)",
                showlegend=False,
                hovertemplate="%{y}: n/a<extra></extra>",
            )
        )
    figure.update_layout(**_base_layout("Composite score by rank"))
    figure.update_xaxes(title={"text": "composite score"})
    figure.update_yaxes(autorange="reversed", title={"text": "category"})
    return figure


def _contribution_figure(view: RunReportView) -> go.Figure:
    """Stacked weighted-contribution bars for the scored rows, rank-sorted.

    A missing component contributes no segment: its value is ``None`` (a gap),
    never a zero-height stack segment (plan §5.3(b); AGENTS.md Hard rule 2).
    The legend uses the plain component names (plan §5.7).
    """
    scored = _scored_rows(view)
    labels = [row.category for row in scored]
    figure = go.Figure()
    contributions_by_row = [_component_contributions(row) for row in scored]
    for name, _weight in COMPONENT_WEIGHTS:
        figure.add_trace(
            go.Bar(
                x=labels,
                y=[
                    dict(contributions).get(name, None)
                    for contributions in contributions_by_row
                ],
                name=_component_label(name),
            )
        )
    figure.update_layout(**_base_layout("Weighted component contributions"))
    figure.update_layout(barmode="stack")
    figure.update_xaxes(title={"text": "category"})
    figure.update_yaxes(title={"text": "weighted contribution to composite score"})
    return figure


def _policy_bump_figure(view: RunReportView) -> go.Figure:
    """Three-policy rank bump chart; a null rank is a gap, never ``0``."""
    policies = _policy_axis_labels(view)
    figure = go.Figure()
    for category, balanced, demand_heavy, competition_heavy in _policy_rank_rows(view):
        ranks = (balanced, demand_heavy, competition_heavy)
        if sum(rank is not None for rank in ranks) < 2:
            continue
        figure.add_trace(
            go.Scatter(
                x=list(policies),
                y=[rank for rank in ranks],
                mode="lines+markers",
                name=category,
                connectgaps=False,
            )
        )
    figure.update_layout(**_base_layout("Policy rank comparison"))
    figure.update_xaxes(title={"text": "scoring policy"})
    figure.update_yaxes(autorange="reversed", title={"text": "rank (1 = best)"})
    return figure


def _population_lollipop_figure(view: RunReportView) -> go.Figure:
    """Log-scale population lollipop with a sample-size marker; ``0`` != ``None``.

    A measured ``0`` population (R5) is a **distinct explicit-zero marker**
    labelled ``0``, placed off the log axis at a fixed ``zero_x`` position; a
    ``None`` (unavailable) renders no population marker and an ``n/a`` label.
    The two states must remain visibly distinct (§1.2; plan §5.3, Q5/R5).
    """
    scored = _scored_rows(view)
    labels: list[str] = []
    populations: list[float | None] = []
    samples: list[float | None] = []
    annotations: list[str] = []
    zero_x: list[float | None] = []
    for row in scored:
        labels.append(row.category)
        value = row.discovered_population_count
        sample = row.enriched_sample_count
        if value is None:
            populations.append(None)
            annotations.append(_NA)
            zero_x.append(None)
        elif value == 0:
            # Off the log axis: a distinct explicit-zero marker labelled ``0``.
            populations.append(None)
            annotations.append("0")
            zero_x.append(_POPULATION_EXPLICIT_ZERO_X)
        else:
            populations.append(float(value))
            annotations.append(format(value, "d"))
            zero_x.append(None)
        samples.append(None if sample is None else float(sample))
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=populations,
            y=labels,
            mode="markers",
            name="discovered population (observed)",
            marker={"size": 12, "color": "#6ea8fe"},
            text=annotations,
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=zero_x,
            y=list(labels),
            mode="markers+text",
            name="discovered population: measured zero",
            marker={
                "size": 12,
                "color": "#f2c14e",
                "symbol": "diamond-open",
                "line": {"width": 2, "color": "#f2c14e"},
            },
            text=["" if value is None else "0" for value in zero_x],
            textposition="middle right",
            hovertemplate="%{y}: measured 0<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=samples,
            y=labels,
            mode="markers",
            name="sample size (observed)",
            marker={"size": 7, "color": "#f2c14e"},
        )
    )
    figure.update_layout(**_base_layout("Population and sample size (log scale)"))
    figure.update_xaxes(type="log", title={"text": "count (log scale)"})
    figure.update_yaxes(title={"text": "category"})
    return figure


def _score_quality_scatter_figure(view: RunReportView) -> go.Figure:
    """Score-vs-quality scatter; marker size from ``sample_fraction`` (``n/a`` safe)."""
    scored = _scored_rows(view)
    xs: list[float | None] = []
    ys: list[float | None] = []
    sizes: list[float] = []
    labels: list[str] = []
    texts: list[str] = []
    for row in scored:
        xs.append(
            None
            if row.market_opportunity_score is None
            else float(row.market_opportunity_score)
        )
        ys.append(None if row.component_q is None else float(row.component_q))
        if row.sample_fraction is None:
            sizes.append(_SAMPLE_FRACTION_FALLBACK_MARKER)
            texts.append(_NA)
        else:
            sizes.append(
                _SAMPLE_FRACTION_MIN_MARKER + float(row.sample_fraction) * 40.0
            )
            texts.append(format(row.sample_fraction, ".4g"))
        labels.append(row.category)
    figure = go.Figure(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            text=labels,
            marker={"size": sizes, "color": "#8fd694"},
            customdata=texts,
            hovertemplate=(
                "%{text}<br>composite score %{x}<br>"
                "quality %{y}<br>sample fraction %{customdata}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **_base_layout("Composite score vs quality (marker = sample fraction)")
    )
    figure.update_xaxes(title={"text": "composite score"})
    figure.update_yaxes(range=[0.0, 1.0], title={"text": "Quality"})
    return figure


# --------------------------------------------------------------------------
# Dash application (pure layout + app construction; no server, no I/O)
# --------------------------------------------------------------------------


def _chart_figure(chart_key: str, view: RunReportView) -> go.Figure:
    """Return the pure figure for ``chart_key`` from the surviving builders."""
    builders = {
        "score_bar": _score_bar_figure,
        "contribution_stack": _contribution_figure,
        "policy_bump": _policy_bump_figure,
        "population_lollipop": _population_lollipop_figure,
        "score_quality_scatter": _score_quality_scatter_figure,
    }
    return builders[chart_key](view)


def _figure_payload(figure: go.Figure) -> dict:
    """Return a JSON-serializable figure dict for a ``dcc.Graph``.

    ``template=None`` keeps the emitted figure to the figure itself, so two
    calls with the same view compare equal after normalization; the figure is
    converted to its plain ``dict`` form so the Dash component tree serializes.
    """
    figure.update_layout(template=None)
    return figure.to_plotly_json()


def _chart_card(chart_key: str, view: RunReportView) -> "dash_html.Div":
    """Return one chart card: title, one-line caption, and the fixed-id graph."""
    div_id = _DASHBOARD_CHART_ID[chart_key]
    component_id = dict(
        (key, component_id) for component_id, key in _DASHBOARD_COMPONENT_CHART_IDS
    )[chart_key]
    return dash_html.Section(
        [
            dash_html.H3(_DASHBOARD_CHART_TITLES[chart_key]),
            dash_html.P(
                _DASHBOARD_CHART_CAPTIONS[chart_key],
                className="chart-caption",
            ),
            dcc.Graph(
                id=div_id,
                figure=_figure_payload(_chart_figure(chart_key, view)),
                config={"displayModeBar": False, "responsive": True},
                style={"height": f"{_DASHBOARD_CHART_HEIGHT}px"},
            ),
        ],
        id=component_id,
        className="chart-card",
    )


def _kpi_tile(label: str, value: float | int | None) -> "dash_html.Div":
    """Return one KPI tile; ``None`` renders ``n/a`` and is never ``0`` (R8)."""
    human_label, explanation = _DASHBOARD_LABELS[label]
    shown = _NA if value is None else _fmt(value)
    return dash_html.Div(
        [
            dash_html.Span(human_label, className="kpi-label"),
            dash_html.Span(shown, className="kpi-value"),
            dash_html.Span(explanation, className="kpi-note"),
        ],
        className="kpi-tile",
        title=explanation,
    )


def _kpi_strip(view: RunReportView) -> "dash_html.Div":
    """Return the three KPI tiles in fixed order with ``n/a`` for ``None``."""
    return dash_html.Div(
        [_kpi_tile(label, value) for label, value in _kpi_tiles(view)],
        id="kpi-strip",
        className="kpi-strip",
    )


def _table_column_label(label: str, attribute: str) -> str:
    """Return the display header for one primary-table column.

    Every ``_PRIMARY_COLUMNS`` label is displayed verbatim so all 30
    ``LREQ-RPT-020`` labels are visible by default (R5); a separate legend line
    spells the D/C/R/Q component columns out in plain words (D-5).
    """
    _ = attribute
    return label


def _component_legend() -> "dash_html.P":
    """Return the plain-language legend for the D/C/R/Q component columns."""
    pairs = ", ".join(
        f"{name} = {_component_label(name)}" for name, _ in COMPONENT_WEIGHTS
    )
    return dash_html.P(
        f"Component columns: {pairs}.",
        className="component-legend",
    )


def _table_cell(value: object) -> str:
    """Format one primary-table cell; ``None`` is the explicit ``n/a`` marker."""
    if value is None:
        return _NA
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def _primary_table(view: RunReportView) -> "dash_html.Div":
    """Return the compact, horizontally scrollable primary table (R5).

    All ``_PRIMARY_COLUMNS`` labels are present by default (no column picker);
    every category row is shown, including non-rankable rows (LREQ-RPT-040).
    """
    columns = [
        {
            "name": _table_column_label(label, attribute),
            "id": attribute,
        }
        for label, attribute in _PRIMARY_COLUMNS
    ]
    data = [
        {
            attribute: _table_cell(getattr(row, attribute))
            for _, attribute in _PRIMARY_COLUMNS
        }
        for row in view.categories
    ]
    return dash_html.Div(
        dash_table.DataTable(
            id="primary-table-data",
            columns=columns,
            data=data,
            sort_action="native",
            page_size=len(view.categories) or 1,
            style_table={"overflowX": "auto", "width": "100%"},
            style_cell={
                "fontSize": "0.78rem",
                "padding": "2px 6px",
                "textAlign": "left",
                "whiteSpace": "nowrap",
            },
            style_header={"fontWeight": "600"},
        ),
        id="primary-table",
        className="primary-table",
    )


def _detail_metric_rows(row: CategoryReportRow) -> list["dash_html.Li"]:
    """Return the six labelled raw metric-input list items (``n/a`` safe)."""
    return [
        dash_html.Li(
            [
                dash_html.Span(label, className="metric-label"),
                dash_html.Span(" (inferred): ", className="metric-kind"),
                dash_html.Span(_fmt(value)),
            ]
        )
        for label, value in _raw_metric_entries(row)
    ]


def _detail_strata(row: CategoryReportRow) -> "dash_html.Div":
    """Return the sample-strata table for one category, persisted verbatim."""
    if not row.strata:
        return dash_html.P(_NA, className="missing")
    headers = (
        "stratum",
        "offset",
        "stride",
        "N_h (discovered population)",
        "n_h (sampled population)",
        "u_demand_h",
        "u_recent_h",
        "u_quality_h",
        "usable status",
        "eligibility rule",
    )
    head = dash_html.Tr([dash_html.Th(label) for label in headers])
    body = [
        dash_html.Tr(
            [
                dash_html.Td(_table_cell(value))
                for value in (
                    stratum.stratum_index,
                    stratum.stratum_offset,
                    stratum.stratum_stride,
                    stratum.population_count,
                    stratum.selected_count,
                    stratum.usable_demand_count,
                    stratum.usable_recent_count,
                    stratum.usable_quality_count,
                    stratum.usable_status,
                    stratum.eligibility_rule,
                )
            ]
        )
        for stratum in row.strata
    ]
    return dash_html.Table(
        [dash_html.Thead(head), dash_html.Tbody(body)],
        className="strata",
    )


def _detail_panel_children(view: RunReportView, row: CategoryReportRow) -> list:
    """Return the ``LREQ-RPT-030`` detail items for one selected category.

    The shared formula/"how to read" list is **not** here: it is hoisted once in
    the layout (plan §5.2/§5.6). This panel carries the category-specific
    formulas/metric inputs/strata/warnings/timestamps and the observed-versus-
    inferred lists.
    """
    children: list = [
        dash_html.H3(f"Category: {row.category}"),
        dash_html.P(
            [
                dash_html.Span("Rankable? ", className="metric-label"),
                dash_html.Span(row.rankability_status, className="metric-kind"),
                dash_html.Br(),
                dash_html.Span(_rankability_note(row)),
            ],
            className="rankability",
        ),
        dash_html.H4("Metric inputs"),
        dash_html.Ul(_detail_metric_rows(row)),
        dash_html.H4("Observed versus inferred"),
        dash_html.Ul(
            [dash_html.Li(label) for label in _OBSERVED_LABELS]
            + [dash_html.Li(label) for label in _INFERRED_LABELS]
        ),
        dash_html.H4("Sample strata"),
        _detail_strata(row),
        dash_html.H4("Warnings"),
    ]
    if row.warnings:
        children.append(dash_html.Ul([dash_html.Li(code) for code in row.warnings]))
    else:
        children.append(dash_html.P(_NA, className="missing"))
    children.extend(
        [
            dash_html.H4("Timestamps"),
            dash_html.Dl(
                [
                    item
                    for label, value in (
                        ("Category computed (UTC)", row.computed_at_utc),
                        ("Run started (UTC)", view.run_started_at_utc),
                        ("Scoring cutoff (UTC)", view.scoring_cutoff_utc),
                        ("Completed (UTC)", view.completed_at_utc),
                    )
                    for item in (
                        dash_html.Dt(label),
                        dash_html.Dd(_format_timestamp(value)),
                    )
                ]
            ),
        ]
    )
    return children


def _category_select_options(view: RunReportView) -> list[dict[str, str]]:
    """Return one selector option per category, in view order (non-rankable too)."""
    return [
        {
            "label": f"{row.category} ({row.rankability_status})",
            "value": row.category,
        }
        for row in view.categories
    ]


def _default_category(view: RunReportView) -> str:
    """Return the default selected category: the first row, or ``""`` if empty."""
    return view.categories[0].category if view.categories else ""


def _category_selector(view: RunReportView) -> "dash_html.Div":
    """Return the category selector driving the detail panel."""
    return dash_html.Div(
        [
            dash_html.Label("Category", htmlFor="category-selector-value"),
            dcc.Dropdown(
                id="category-selector-value",
                options=_category_select_options(view),
                value=_default_category(view),
                clearable=False,
            ),
        ],
        id="category-selector",
        className="category-selector",
    )


def _shared_formula_panel() -> "dash_html.Div":
    """Return the single shared formula/"how to read" panel (appears once)."""
    return dash_html.Details(
        [
            dash_html.Summary("How to read these numbers (shared)"),
            dash_html.Ul([dash_html.Li(line) for line in _FORMULA_EXPLANATIONS]),
        ],
        className="formula-panel",
        open=True,
    )


def _footnote(view: RunReportView) -> "dash_html.Div":
    """Return the one shared footnote (coverage vs sample fraction; n/a vs 0)."""
    provisional = view.sensitivity is None or all(
        row.rankability_status != "rankable" for row in view.categories
    )
    items = [
        _DASHBOARD_LABELS["coverage"][1],
        _DASHBOARD_LABELS["sample_fraction"][1],
        (
            "A displayed 'n/a' marks an unavailable value and is never the "
            "measured number 0."
        ),
    ]
    if provisional:
        items.append(
            "This run is provisional: no rankable candidates were recorded, so "
            "the stability tiles read 'n/a' and the policy ranks show gaps."
        )
    return dash_html.Div(
        [
            dash_html.H4("Notes"),
            dash_html.Ul([dash_html.Li(item) for item in items]),
        ],
        id="footnote",
        className="footnote",
    )


def _run_header(view: RunReportView) -> "dash_html.Div":
    """Return the run header block (id/status/timestamps/preflight)."""
    items = (
        ("Run ID", view.run_id),
        ("Run status", view.status),
        ("Run started (UTC)", _format_timestamp(view.run_started_at_utc)),
        ("Scoring cutoff (UTC)", _format_timestamp(view.scoring_cutoff_utc)),
        ("Identity preflight status", view.identity_preflight_status),
    )
    return dash_html.Div(
        [
            item
            for label, value in items
            for item in (
                dash_html.Dt(label),
                dash_html.Dd(_fmt(value)),
            )
        ],
        className="run-header",
    )


def build_dashboard_layout(view: RunReportView) -> "dash_html.Div":
    """Return the deterministic initial layout tree for ``view`` (no server, no I/O).

    Pure: no clock, no network, no database. Two calls with the same ``view``
    build equal trees. Every chart's figure is produced by a pure
    ``_x_figure(view)`` builder; every component carries a fixed ``id`` from
    :data:`DASHBOARD_COMPONENT_IDS`. ``HEURISTIC_STATEMENT`` appears verbatim
    exactly once; the primary table carries every ``_PRIMARY_COLUMNS`` label; the
    selected-category detail covers every ``LREQ-RPT-030`` item for one category,
    with the shared formula list hoisted to a single panel. Non-rankable
    categories stay visible in the table and selector (``LREQ-RPT-040``).
    """
    first = view.categories[0] if view.categories else None
    detail_children = (
        _detail_panel_children(view, first)
        if first is not None
        else [dash_html.P("No categories recorded.", className="missing")]
    )
    return dash_html.Div(
        [
            dash_html.Header(
                [
                    dash_html.H1("Niche Scout dashboard"),
                    _run_header(view),
                    dash_html.P(
                        view.heuristic_statement,
                        id="heuristic",
                        className="heuristic",
                    ),
                ],
                className="run-header-block",
            ),
            _kpi_strip(view),
            dash_html.Div(
                [
                    _chart_card(chart_key, view)
                    for chart_key, _div_id in DASHBOARD_CHART_IDS
                ],
                className="chart-grid",
            ),
            dash_html.Section(
                [
                    dash_html.H2("Primary table"),
                    _component_legend(),
                    _primary_table(view),
                ],
                className="primary-table-section",
            ),
            dash_html.Section(
                [
                    dash_html.H2("Category detail"),
                    _shared_formula_panel(),
                    _category_selector(view),
                    dash_html.Div(
                        detail_children,
                        id="detail-panel",
                        className="detail-panel",
                    ),
                ],
                className="detail-section",
            ),
            _footnote(view),
        ],
        className="dashboard",
    )


def build_dashboard_app(view: RunReportView) -> Dash:
    """Return a ``dash.Dash`` whose layout is ``build_dashboard_layout(view)``.

    Pure construction (no ``app.run``, no network, no clock read by this module,
    no repository access). The returned object is safe to construct in a test:
    assert on ``app.layout`` and invoke a callback function directly. Dash's
    default local asset serving is relied on (no CDN); assets are served from
    the installed ``dash`` package, so no external URL is referenced.
    """
    app = Dash(
        __name__,
        serve_locally=True,
        title=f"Niche Scout dashboard - {view.run_id}",
    )
    app.layout = build_dashboard_layout(view)

    @app.callback(
        Output("detail-panel", "children"),
        Input("category-selector-value", "value"),
    )
    def _render_selected_detail(selected_category: str | None):  # noqa: ANN202
        """Return the ``LREQ-RPT-030`` detail for the selected category."""
        row = _rows_by_category(view).get(selected_category)
        if row is None:
            return [dash_html.P("No category selected.", className="missing")]
        return _detail_panel_children(view, row)

    return app


def _rows_by_category(view: RunReportView) -> dict[str, CategoryReportRow]:
    """Return ``{category: row}`` for one loaded view (no I/O, no recompute)."""
    return {row.category: row for row in view.categories}


# --------------------------------------------------------------------------
# Plain-text renderer
# --------------------------------------------------------------------------


def render_run_report_text(view: RunReportView) -> str:
    """Return the plain-text equivalent of the HTML report.

    Carries the same mandatory fields and ``HEURISTIC_STATEMENT``. Deterministic
    for a fixed ``view``; no clock is read.
    """
    lines: list[str] = [
        "NICHE SCOUT REPORT",
        f"Run ID: {view.run_id}",
        f"Run status: {view.status}",
        f"Run started (UTC): {_format_timestamp(view.run_started_at_utc)}",
        f"Scoring cutoff (UTC): {_format_timestamp(view.scoring_cutoff_utc)}",
        f"Completed (UTC): {_format_timestamp(view.completed_at_utc)}",
        f"Identity preflight status: {view.identity_preflight_status}",
        f"Page-view semantics (run level): {view.page_view_semantics_status}",
        "",
        "HEURISTIC STATEMENT",
        view.heuristic_statement,
        "",
        "WARNINGS",
    ]
    if view.warnings:
        lines.extend(
            f"  - {warning.code} "
            f"({warning.category if warning.category else 'run level'})"
            for warning in view.warnings
        )
    else:
        lines.append("  - none recorded")
    lines.extend(["", "PRIMARY TABLE"])
    lines.append("  " + " | ".join(label for label, _ in _PRIMARY_COLUMNS))
    for row in view.categories:
        lines.append(
            "  "
            + " | ".join(
                _fmt(getattr(row, attribute)) for _, attribute in _PRIMARY_COLUMNS
            )
        )
    lines.extend(["", "CATEGORY DETAILS"])
    for row in view.categories:
        lines.extend(_render_category_detail_text(view, row))
    return "\n".join(lines) + "\n"


def _render_category_detail_text(
    view: RunReportView, row: CategoryReportRow
) -> list[str]:
    lines = [
        "",
        f"CATEGORY: {row.category}",
        f"  rankability: {row.rankability_status}",
        f"  rankability note: {_rankability_note(row)}",
        "  formulas and explanations:",
    ]
    lines.extend(f"    - {line}" for line in _FORMULA_EXPLANATIONS)
    lines.append("  metric inputs:")
    lines.extend(
        f"    - {label} (inferred): {_fmt(value)}"
        for label, value in _raw_metric_entries(row)
    )
    lines.append("  observed versus inferred:")
    lines.extend(f"    - {label}" for label in _OBSERVED_LABELS)
    lines.extend(f"    - {label}" for label in _INFERRED_LABELS)
    lines.append("  sample strata:")
    if row.strata:
        lines.extend(
            f"    - stratum {stratum.stratum_index} "
            f"offset {stratum.stratum_offset} stride {stratum.stratum_stride} "
            f"N_h={stratum.population_count} n_h={stratum.selected_count} "
            f"u_demand_h={_fmt(stratum.usable_demand_count)} "
            f"u_recent_h={_fmt(stratum.usable_recent_count)} "
            f"u_quality_h={_fmt(stratum.usable_quality_count)} "
            f"usable_status={stratum.usable_status} "
            f"eligibility_rule={_fmt(stratum.eligibility_rule)}"
            for stratum in row.strata
        )
    else:
        lines.append("    - none recorded")
    lines.append("  warnings:")
    if row.warnings:
        lines.extend(f"    - {code}" for code in row.warnings)
    else:
        lines.append("    - none recorded")
    lines.append("  timestamps:")
    lines.extend(
        (
            f"    - category computed (UTC): {_format_timestamp(row.computed_at_utc)}",
            f"    - run started (UTC): {_format_timestamp(view.run_started_at_utc)}",
            f"    - scoring cutoff (UTC): {_format_timestamp(view.scoring_cutoff_utc)}",
            f"    - completed (UTC): {_format_timestamp(view.completed_at_utc)}",
        )
    )
    return lines


# --------------------------------------------------------------------------
# File output and dashboard convenience
# --------------------------------------------------------------------------


def write_run_report(
    repository: SqliteRepository,
    run_id: str,
    output_path: Path,
    *,
    fmt: str = "html",
) -> Path:
    """Load, render, and write one run report to ``output_path``.

    ``fmt`` is ``"html"`` or ``"text"``; any other value raises ``ValueError``.
    The write is a local filesystem write only (no network) and is
    deterministic: LF line endings and UTF-8. Raises :class:`RunNotFoundError`
    when ``run_id`` has no ``runs`` row. Returns the written path.
    """
    if fmt not in ("html", "text"):
        raise ValueError("fmt must be 'html' or 'text'")
    view = load_run_report_view(repository, run_id)
    rendered = (
        render_run_report_html(view) if fmt == "html" else render_run_report_text(view)
    )
    path = Path(output_path)
    parent = path.parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")
    return path
