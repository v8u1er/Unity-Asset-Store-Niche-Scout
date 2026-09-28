"""Inert fixtures and golden vectors for the Chunk 11 report suite.

Data and construction helpers only: this module contains no assertions and no
logic under test, so a defect in it cannot mask a read-model or render defect.

Sources (read, not paraphrased from memory):

- ``Documents/SRS-lean.md`` §5.1 (``LREQ-SMP-080`` sample fraction/census),
  §6.5 (``category_scores`` field semantics), §9.1/§9.2/§9.3 (rankability,
  evidence grade, sensitivity nulls), §10 (``LREQ-RPT-010..050``), and
  Appendix C (warning vocabulary).
- ``Documents/plans/chunk-11-report-renderer-and-read-only-dashboard.md`` §5
  (frozen read-model surface), §8 (edge cases), §9 (fixtures and golden vectors).
- Frozen interfaces consumed:
  ``interfaces/chunk-4B.md`` §5.2/§5.3, ``chunk-7B.md``,
  ``chunk-08.md``, ``chunk-9A.md``, ``chunk-9B.md``, ``chunk-10.md`` §6.

No credentials, no network, no clock reads, no file I/O, no ``sqlite3``.
Datetimes are fixed aware-UTC literals, never ``now()``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from niche_scout.models import CategoryScoreRecord, RunRecord

# --------------------------------------------------------------------------
# Fixed aware-UTC timestamps. No clock is ever read (LREQ-ARCH-020).
# --------------------------------------------------------------------------

RUN_ID = "run-11"
RUN_STARTED_AT_UTC = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
SCORING_CUTOFF_UTC = datetime(2025, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
COMPLETED_AT_UTC = datetime(2025, 3, 4, 6, 0, 0, tzinfo=timezone.utc)
TAXONOMY_CAPTURED_AT_UTC = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
COMPUTED_AT_UTC = datetime(2025, 6, 7, 8, 9, 10, tzinfo=timezone.utc)

# --------------------------------------------------------------------------
# Category names used by the report vectors.
# --------------------------------------------------------------------------

CATEGORY_ALPHA = "Alpha/Ranked"
CATEGORY_BRAVO = "Bravo/Ranked"
CATEGORY_CHARLIE = "Charlie/Unranked"
CATEGORY_ZULU = "Zulu/Unranked"
CATEGORY_NON_RANKABLE = "Render/NonRankable"
CATEGORY_ZERO_POPULATION = "Render/ZeroPopulation"
CATEGORY_FALLBACK_ONE = "Fallback/One"
CATEGORY_FALLBACK_TWO = "Fallback/Two"
CATEGORY_PRIMARY = CATEGORY_ALPHA

# --------------------------------------------------------------------------
# Frozen ``stratum_statistics_json`` payloads (one per vector).
# --------------------------------------------------------------------------


def _stratum_object(
    *,
    index: int,
    offset: int,
    stride: int,
    population: int,
    selected: int,
    demand: int | None,
    recent: int | None,
    quality: int | None,
    status: str,
    rule: str | None,
) -> dict[str, object]:
    """Return one ten-key stratum object in the frozen Chunk 4B schema.

    The chunk-24 geometry keys are ``stratum_offset``/``stratum_stride``; both
    strata below belong to one large category, so they share the same offset
    and stride (plan §2.1: one offset per category, stride = SAMPLE_STRATA).
    """
    return {
        "stratum_index": index,
        "stratum_offset": offset,
        "stratum_stride": stride,
        "N_h": population,
        "n_h": selected,
        "u_demand_h": demand,
        "u_recent_h": recent,
        "u_quality_h": quality,
        "usable_status": status,
        "eligibility_rule": rule,
    }


STRATUM_STATISTICS_JSON: str = json.dumps(
    [
        _stratum_object(
            index=0,
            offset=0,
            stride=4,
            population=25,
            selected=25,
            demand=23,
            recent=22,
            quality=21,
            status="usable",
            rule="min_usable_samples_per_stratum",
        ),
        _stratum_object(
            index=1,
            offset=0,
            stride=4,
            population=25,
            selected=25,
            demand=22,
            recent=20,
            quality=20,
            status="usable",
            rule="min_usable_samples_per_stratum",
        ),
    ],
    sort_keys=True,
    separators=(",", ":"),
)

PENDING_STRATUM_STATISTICS_JSON: str = json.dumps(
    [
        _stratum_object(
            index=0,
            offset=0,
            stride=4,
            population=25,
            selected=25,
            demand=None,
            recent=None,
            quality=None,
            status="pending",
            rule=None,
        )
    ],
    sort_keys=True,
    separators=(",", ":"),
)

EMPTY_STRATUM_STATISTICS_JSON = "[]"

# --------------------------------------------------------------------------
# Sensitivity payload builder (Chunk 10 §6 frozen key set).
# --------------------------------------------------------------------------


def ranking_sensitivity_json(
    ranked_categories: tuple[str, ...],
    *,
    top_3_stability: float | None = None,
    top_5_stability: float | None = None,
    maximum_score_delta: float | None = None,
    maximum_rank_displacement: int | None = None,
    warning: bool | None = None,
) -> str:
    """Return a ``ranking_sensitivity_json`` payload with the frozen key set.

    ``ranked_categories`` is recorded in the supplied order; a category absent
    from it has no displayed rank. The empty-candidate case is the explicit
    ``{}`` object Chunk 10 persists on a failed-preflight row.
    """
    payload = {
        "policies": ["balanced", "demand_heavy", "competition_heavy"],
        "ranked_categories": list(ranked_categories),
        "categories": [],
        "reference_set_size": len(ranked_categories),
        "displacement_threshold": 3.0,
        "top_3_stability": top_3_stability,
        "top_5_stability": top_5_stability,
        "maximum_score_delta": maximum_score_delta,
        "maximum_rank_displacement": maximum_rank_displacement,
        "warning": warning,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


EMPTY_RANKING_SENSITIVITY_JSON = "{}"

REFERENCE_USABLE_COUNTS_JSON = json.dumps(
    {
        "demand_per_asset_raw": 20,
        "demand_median_raw": 20,
        "breadth_raw": 20,
        "recent_share_raw": 18,
        "median_age_raw": 18,
        "quality_raw": 17,
    },
    sort_keys=True,
    separators=(",", ":"),
)

# --------------------------------------------------------------------------
# Record factories. Every keyword defaults to a complete scored row; tests pass
# explicit overrides for the edge vectors.
# --------------------------------------------------------------------------

_SCORE_DEFAULTS: dict[str, object] = {
    "discovery_status": "complete",
    "discovery_filter_verified": True,
    "discovery_unresolved_identity_count": 0,
    "discovery_conflict_count": 0,
    "discovery_duplicate_count": 0,
    "discovered_population_count": 500,
    "enriched_sample_count": 100,
    "sample_is_census": False,
    "sampling_basis": "deterministic_stratified_sample",
    "sample_fraction": 0.2,
    "unique_enrichment_count": 100,
    "overlap_category_count": 0,
    "overlap_sample_percentage": 0.0,
    "usable_demand_sample_count": 90,
    "usable_recent_supply_sample_count": 85,
    "usable_quality_sample_count": 80,
    "breadth_source": "verified_total_count",
    "breadth_completeness_status": "complete",
    "discovery_bounded_by_verified_total": True,
    "demand_stratum_eligibility_coverage": 0.85,
    "recent_supply_stratum_eligibility_coverage": 0.82,
    "quality_stratum_eligibility_coverage": 0.81,
    "demand_per_asset_raw": 12.5,
    "demand_median_raw": 10.0,
    "breadth_raw": 500.0,
    "recent_share_raw": 0.25,
    "median_age_raw": 400.0,
    "quality_raw": 0.62,
    "stratum_statistics_json": STRATUM_STATISTICS_JSON,
    "component_d": 0.70,
    "component_c": 0.55,
    "component_r": 0.60,
    "component_q": 0.65,
    "market_opportunity_score": 0.63,
    "score_state": "available",
    "evidence_grade": "moderate",
    "rankability_status": "rankable",
    "missing_components_json": "[]",
    "warnings_json": "[]",
    "reference_size": 20,
    "reference_usable_counts_json": REFERENCE_USABLE_COUNTS_JSON,
    "top_3_stability": 1.0,
    "top_5_stability": 0.8,
    "maximum_score_delta": 0.05,
    "maximum_rank_displacement": 1,
    "sensitivity_warning": False,
    "ranking_sensitivity_json": EMPTY_RANKING_SENSITIVITY_JSON,
    "computed_at_utc": COMPUTED_AT_UTC,
}


def category_score_record(category: str, **overrides: object) -> CategoryScoreRecord:
    """Return a ``CategoryScoreRecord`` for ``category`` with overrides applied."""
    values: dict[str, object] = dict(_SCORE_DEFAULTS)
    values.update(overrides)
    return CategoryScoreRecord(run_id=RUN_ID, category=category, **values)


def run_record(
    categories: tuple[str, ...],
    *,
    run_id: str = RUN_ID,
    **overrides: object,
) -> RunRecord:
    """Return a ``RunRecord`` for ``categories`` in declared order."""
    values: dict[str, object] = {
        "run_id": run_id,
        "run_started_at_utc": RUN_STARTED_AT_UTC,
        "scoring_cutoff_utc": SCORING_CUTOFF_UTC,
        "completed_at_utc": COMPLETED_AT_UTC,
        "categories_json": json.dumps(list(categories), separators=(",", ":")),
        "config_snapshot_json": "{}",
        "config_sha256": "0" * 64,
        "taxonomy_version": "2025.1",
        "taxonomy_captured_at_utc": TAXONOMY_CAPTURED_AT_UTC,
        "taxonomy_sha256": "1" * 64,
        "endpoint_contract_version": "1.0.0",
        "identity_mapping_rule_version": "1.0.1",
        "sampling_rule_version": "2.0.0",
        "page_view_semantics_status": "unvalidated",
        "graphql_operation_correlation_mode": "explicit_key",
        "identity_preflight_status": "passed",
        "identity_preflight_summary_json": "{}",
        "status": "completed",
    }
    values.update(overrides)
    return RunRecord(**values)


def scored_rows_for(
    first: str, second: str
) -> tuple[CategoryScoreRecord, CategoryScoreRecord]:
    """Return two rankable rows whose sensitivity payload ranks ``first`` then
    ``second`` (golden ``rank`` 1 and 2)."""
    payload = ranking_sensitivity_json(
        (first, second),
        top_3_stability=1.0,
        top_5_stability=0.8,
        maximum_score_delta=0.05,
        maximum_rank_displacement=1,
        warning=False,
    )
    return (
        category_score_record(first, ranking_sensitivity_json=payload),
        category_score_record(second, ranking_sensitivity_json=payload),
    )


def pre_scoring_default_row(category: str) -> CategoryScoreRecord:
    """Return the failed-preflight row shape Chunk 10 persists.

    The three ``usable_*_sample_count`` values and the three stratum eligibility
    coverages keep the schema's ``NOT NULL DEFAULT 0``/``0.0`` placeholders while
    ``score_state`` is ``unavailable``; the report must render them unavailable.
    """
    return category_score_record(
        category,
        component_d=None,
        component_c=None,
        component_r=None,
        component_q=None,
        market_opportunity_score=None,
        score_state="unavailable",
        evidence_grade="insufficient",
        rankability_status="not_rankable",
        missing_components_json='["D","C","R","Q"]',
        warnings_json='["IDENTITY_PREFLIGHT_FAILED"]',
        usable_demand_sample_count=0,
        usable_recent_supply_sample_count=0,
        usable_quality_sample_count=0,
        demand_stratum_eligibility_coverage=0.0,
        recent_supply_stratum_eligibility_coverage=0.0,
        quality_stratum_eligibility_coverage=0.0,
        top_3_stability=None,
        top_5_stability=None,
        maximum_score_delta=None,
        maximum_rank_displacement=None,
        sensitivity_warning=None,
        reference_size=0,
        ranking_sensitivity_json=EMPTY_RANKING_SENSITIVITY_JSON,
        stratum_statistics_json=PENDING_STRATUM_STATISTICS_JSON,
    )


def non_rankable_row(category: str) -> CategoryScoreRecord:
    """Return a computable-but-not-rankable row missing components ``D`` and ``Q``."""
    return category_score_record(
        category,
        component_d=None,
        component_q=None,
        market_opportunity_score=None,
        score_state="unavailable",
        evidence_grade="insufficient",
        rankability_status="not_rankable",
        missing_components_json='["D","Q"]',
        warnings_json='["INSUFFICIENT_DEMAND_SAMPLE","INSUFFICIENT_QUALITY_SAMPLE"]',
        ranking_sensitivity_json=EMPTY_RANKING_SENSITIVITY_JSON,
        top_3_stability=None,
        top_5_stability=None,
        maximum_score_delta=None,
        maximum_rank_displacement=None,
        sensitivity_warning=None,
    )


def zero_population_row(category: str) -> CategoryScoreRecord:
    """Return the zero-population census-exempt vector.

    ``discovered_population_count`` is a measured ``0``; ``sample_fraction`` is
    ``null`` (SRS §5.1 zero-population rule); the six raw metrics are ``null``.
    """
    return category_score_record(
        category,
        discovered_population_count=0,
        enriched_sample_count=0,
        sample_is_census=False,
        sample_fraction=None,
        unique_enrichment_count=0,
        overlap_category_count=0,
        overlap_sample_percentage=None,
        usable_demand_sample_count=0,
        usable_recent_supply_sample_count=0,
        usable_quality_sample_count=0,
        demand_per_asset_raw=None,
        demand_median_raw=None,
        breadth_raw=None,
        recent_share_raw=None,
        median_age_raw=None,
        quality_raw=None,
        stratum_statistics_json=EMPTY_STRATUM_STATISTICS_JSON,
        component_d=None,
        component_c=None,
        component_r=None,
        component_q=None,
        market_opportunity_score=None,
        score_state="unavailable",
        evidence_grade="insufficient",
        rankability_status="not_rankable",
        missing_components_json='["D","C","R","Q"]',
        warnings_json="[]",
        reference_size=20,
        top_3_stability=None,
        top_5_stability=None,
        maximum_score_delta=None,
        maximum_rank_displacement=None,
        sensitivity_warning=None,
        ranking_sensitivity_json=EMPTY_RANKING_SENSITIVITY_JSON,
    )


__all__ = [
    "CATEGORY_ALPHA",
    "CATEGORY_BRAVO",
    "CATEGORY_CHARLIE",
    "CATEGORY_FALLBACK_ONE",
    "CATEGORY_FALLBACK_TWO",
    "CATEGORY_NON_RANKABLE",
    "CATEGORY_PRIMARY",
    "CATEGORY_ZERO_POPULATION",
    "CATEGORY_ZULU",
    "COMPLETED_AT_UTC",
    "COMPUTED_AT_UTC",
    "EMPTY_RANKING_SENSITIVITY_JSON",
    "EMPTY_STRATUM_STATISTICS_JSON",
    "PENDING_STRATUM_STATISTICS_JSON",
    "REFERENCE_USABLE_COUNTS_JSON",
    "RUN_ID",
    "RUN_STARTED_AT_UTC",
    "SCORING_CUTOFF_UTC",
    "STRATUM_STATISTICS_JSON",
    "TAXONOMY_CAPTURED_AT_UTC",
    "category_score_record",
    "non_rankable_row",
    "pre_scoring_default_row",
    "ranking_sensitivity_json",
    "run_record",
    "scored_rows_for",
    "zero_population_row",
]
