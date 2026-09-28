"""Read-only report read model and local renderers (SRS-lean §10).

This module is **I/O + render**: it reads persisted rows through the frozen
``SqliteRepository`` read surface, reconstructs one :class:`RunReportView`, and
turns it into a self-contained HTML document or a plain-text equivalent. It
performs no network I/O, reads no clock, and recomputes no metric, component,
normalized value, composite score, evidence grade, rankability, or sensitivity
statistic: every displayed value is a persisted value rendered verbatim
(display rounding only).

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

from .database import SqliteRepository, parse_stratum_statistics
from .models import (
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

HEURISTIC_STATEMENT: str = (
    "This score is a deterministic, within-run heuristic computed from "
    "marketplace signals and, for larger categories, a stratified sample. It "
    "has not been calibrated against sales, revenue, downloads, or conversion, "
    "and it is not a statistically representative estimate of the marketplace. "
    "The report distinguishes the following, and does not treat the left-hand "
    "value as the right-hand value: pagination completion is not immutable "
    "snapshot completeness; the page-view index is not a weekly traffic rate; "
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
    "D (demand) consumes the discovered page-view index and rating signals, "
    "shrunk by demand stratum eligibility coverage.",
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
    "The page-view index is a cumulative page-view signal, not a weekly traffic rate.",
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

    return CategoryReportRow(
        category=score.category,
        rank=_rank_from_sensitivity(score.ranking_sensitivity_json, score.category),
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
    )


def _order_rows(
    rows_by_category: dict[str, CategoryReportRow],
) -> tuple[CategoryReportRow, ...]:
    """Order ranked rows by ``(-rank, category)``, then unranked by category."""
    ranked = [row for row in rows_by_category.values() if row.rank is not None]
    unranked = [row for row in rows_by_category.values() if row.rank is None]
    ranked.sort(key=lambda row: (-row.rank, row.category))
    unranked.sort(key=lambda row: row.category)
    return tuple(ranked) + tuple(unranked)


def _rank_from_sensitivity(payload: str, category: str) -> int | None:
    """Derive the displayed rank from ``ranking_sensitivity_json``; else ``None``."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    ranked = decoded.get("ranked_categories")
    if not isinstance(ranked, list):
        return None
    try:
        position = ranked.index(category)
    except ValueError:
        return None
    return position + 1


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


def render_dashboard_html(repository: SqliteRepository, run_id: str) -> str:
    """Load and render the read-only dashboard for ``run_id``.

    Convenience for the Chunk 12 ``dashboard`` command. Performs database reads
    only and initiates no discovery, enrichment, or network activity
    (LREQ-CLI-020). Raises :class:`RunNotFoundError` when the run is absent.
    """
    return render_run_report_html(load_run_report_view(repository, run_id))
