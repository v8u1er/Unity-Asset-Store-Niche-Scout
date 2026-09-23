"""Inert acceptance vectors for the Chunk 13 end-to-end and golden-vector suite.

Data only: explicit constants, small construction helpers, and one wrapper
repository class. There are no assertions here; the expectations live in
``tests/test_end_to_end.py`` and ``tests/test_quality_tooling.py``.

Every expected value below is hand-derived from ``Documents/SRS-lean.md`` and is
written with its derivation; none is read from the implementation.

Sources (read, not paraphrased from memory):

* ``Documents/SRS-lean.md`` §7 (sample-aware estimators), §8.1-§8.3
  (normalization, components, composite score), §9.1-§9.3 (rankability, evidence,
  sensitivity), §13 (``LREQ-TST-080``/``LREQ-TST-090``), §14 (fixed weights and
  thresholds), Appendix A (formula summary).
* ``Documents/plans/chunk-13-full-acceptance-suite-and-quality-workflow.md`` §5
  (produced surface), §8 (edge cases and invariants), §9 (test plan and vectors),
  §12 (rulings R7, R8, R11).
* Frozen interfaces consumed: ``chunk-00.md``, ``chunk-04A.md``,
  ``chunk-07B.md``, ``chunk-08.md``, ``chunk-09A.md``, ``chunk-09B.md``,
  ``chunk-10.md``, ``chunk-11.md``, ``chunk-12.md``.

Existing fixtures are reused, never duplicated: the 8-category scenario and its
transports (:mod:`fixtures.pipeline_fixtures`), the raw-metric vectors
(:mod:`fixtures.metric_estimator_fixtures`), and the scoring/sensitivity vectors
(:mod:`fixtures.scoring_fixtures`, :mod:`fixtures.sensitivity_fixtures`).

No network, no real credentials, no ``.env``, no clock read: the clock is
``fixtures.pipeline_fixtures.FixedClock``, the transports are in-memory, and every
datetime is a fixed aware-UTC literal.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from niche_scout.database import SqliteRepository
from niche_scout.metrics import (
    BreadthCompletenessStatus,
    BreadthSource,
    CategoryRawMetrics,
    RawMetricBundle,
)
from niche_scout.models import (
    MIN_CATEGORIES_PER_RUN,
    STRONG_REFERENCE_CATEGORY_COUNT,
    W_C,
    W_D,
    W_Q,
    W_R,
    PageViewSemanticsStatus,
)

__all__ = [
    "CATEGORY_COUNT_BELOW_MIN",
    "CATEGORY_COUNT_EIGHT",
    "CATEGORY_COUNT_TWENTY_ONE",
    "EIGHT_CATEGORY_PROVISIONAL_EXPECTED",
    "FIXED_COMPOSITE_WEIGHTS",
    "PROVISIONAL_CANDIDATE_COUNT",
    "SAMPLE_FRACTION_VS_COVERAGE_EXPECTED",
    "SENSITIVITY_AFTER_BASE_CANDIDATES_EXPECTED",
    "STRONG_REFERENCE_COMPOSITE_COMPONENTS",
    "STRONG_REFERENCE_COMPOSITE_EXPECTED",
    "STRONG_REFERENCE_CATEGORY_ORDER",
    "STRONG_REFERENCE_METRICS",
    "ContradictedPageViewRepository",
    "TWO_CATEGORY_REJECTION_CATEGORIES",
    "UNEQUAL_STRATUM_QUALITY_RAW_EXPECTED",
    "ZERO_POPULATION_BREADTH",
    "ZERO_POPULATION_EXPECTED",
    "contradicted_repository_factory",
    "close_opened",
    "eight_category_provisional_vector",
    "logical_rows",
    "run_row_categories",
    "sample_fraction_vs_coverage_vector",
    "strong_reference_composite_vector",
    "two_category_rejection_vector",
    "unequal_stratum_quality_raw_vector",
    "utc_now_clock",
    "zero_population_vector",
]

FIXED_COMPOSITE_WEIGHTS: dict[str, float] = {
    "D": W_D,
    "C": W_C,
    "R": W_R,
    "Q": W_Q,
}
"""The fixed Lean v1 primary weights (SRS §8.3/§14), read from ``models``."""

CATEGORY_COUNT_BELOW_MIN: int = 2
"""The smallest rejected run size: ``MIN_CATEGORIES_PER_RUN`` is 8, unconfigurable."""

CATEGORY_COUNT_EIGHT: int = MIN_CATEGORIES_PER_RUN
CATEGORY_COUNT_TWENTY_ONE: int = STRONG_REFERENCE_CATEGORY_COUNT

#: 8-20 category runs have an empty base candidate set, so both stability outputs
#: are null and the run-level warning is null (not ``False``) -- dependency-map
#: §6.2/§6.3; SRS §9.3.
PROVISIONAL_CANDIDATE_COUNT: int = 0
EIGHT_CATEGORY_PROVISIONAL_EXPECTED: dict[str, Any] = {
    "run_category_count": CATEGORY_COUNT_EIGHT,
    "candidate_count": PROVISIONAL_CANDIDATE_COUNT,
    "top_3_stability": None,
    "top_5_stability": None,
    "maximum_score_delta": None,
    "maximum_rank_displacement": None,
    "run_warning": None,
}


# ---------------------------------------------------------------------------
# Two-category rejection vector (LREQ-TST-090, LREQ-CLI-040)
# ---------------------------------------------------------------------------


def two_category_rejection_vector() -> tuple[str, ...]:
    """Return the canonical paths of a two-category run.

    A run with fewer than ``MIN_CATEGORIES_PER_RUN`` (8) requested categories is
    rejected before ranking (SRS §10 ``LREQ-CLI-040``), so this vector has no
    expected scores: the expected behaviour is rejection, and
    ``tests/test_end_to_end.py`` asserts a ``PipelineConfigurationError`` with no
    transport call. The paths are lexically ordered so declared order, canonical
    order, and the lexical tie-break agree.
    """
    return tuple(f"Category/Reject-{index:02d}" for index in range(1, 3))


TWO_CATEGORY_REJECTION_CATEGORIES: tuple[str, ...] = two_category_rejection_vector()


# ---------------------------------------------------------------------------
# 21-category strong-reference composite vector (R7, SRS Appendix A)
# ---------------------------------------------------------------------------
#
# The 21-category behaviour is satisfied at the SCORING layer (R7): no
# 21-category pipeline fixture is built. A run of exactly
# ``STRONG_REFERENCE_CATEGORY_COUNT`` (21) categories gives every target
# ``reference_size = 21 - 1 = 20`` peers (SRS §8.1 LREQ-NRM-020).
#
# The vector fixes every raw field to a single constant per category, so:
#
#   * every ``P_ref`` is a midrank against 20 peers,
#   * the target is the median, so ``L = 10`` and ``E = 0`` (20 distinct
#     peers: one value below the target and one above, for each of the 10 pairs),
#     giving ``P_ref = (10 + 0.5 * 0) / 20 = 0.5`` for every field,
#   * ``D0 = 0.60 * 0.5 + 0.40 * 0.5 = 0.5`` (both demand sub-signals available),
#   * ``C = clamp(1 - 0.5, 0, 1) = 0.5``,
#   * ``Rpressure0 = 0.70 * 0.5 + 0.30 * (1 - 0.5) = 0.35 + 0.15 = 0.5``;
#     ``R0 = 1 - 0.5 = 0.5``,
#   * ``Q0 = 1 - 0.5 = 0.5``,
#   * with coverage 1.0 on each sample-derived component the shrinkage
#     ``clamp(0.5 + coverage * (x0 - 0.5), 0, 1)`` is inert: D = C = R = Q = 0.5.
#
# Composite (SRS §8.3 / Appendix A): all four components available, so
#   W_A = 0.35 + 0.30 + 0.20 + 0.15 = 1.0,
#   S_available = (0.35*0.5 + 0.30*0.5 + 0.20*0.5 + 0.15*0.5) / 1.0
#               = 0.5 * (1.0) / 1.0 = 0.5,
#   market_opportunity_score = clamp(0.5 + 1.0 * (0.5 - 0.5), 0, 1) = 0.5,
#   score_state = "available" (all four components present).
#
# A second vector fixes the four components directly so the exact weight
# arithmetic is visible without re-deriving midranks:
#   D = 0.8, C = 0.6, R = 0.4, Q = 0.2
#   S_available = 0.35*0.8 + 0.30*0.6 + 0.20*0.4 + 0.15*0.2
#               = 0.28 + 0.18 + 0.08 + 0.03 = 0.57
#   score = clamp(0.5 + 1.0 * (0.57 - 0.5), 0, 1) = 0.57

STRONG_REFERENCE_CATEGORY_ORDER: tuple[str, ...] = tuple(
    f"Category/Strong-{index:02d}" for index in range(STRONG_REFERENCE_CATEGORY_COUNT)
)

STRONG_REFERENCE_METRICS: tuple[CategoryRawMetrics, ...] = tuple(
    CategoryRawMetrics(
        category=category,
        raw=RawMetricBundle(
            demand_per_asset_raw=1.0,
            demand_median_raw=2.0,
            breadth_raw=3.0,
            recent_share_raw=4.0,
            median_age_raw=5.0,
            quality_raw=6.0,
        ),
        demand_stratum_eligibility_coverage=1.0,
        recent_supply_stratum_eligibility_coverage=1.0,
        quality_stratum_eligibility_coverage=1.0,
        usable_demand_sample_count=0,
        usable_recent_supply_sample_count=0,
        usable_quality_sample_count=0,
        breadth_source=BreadthSource.VERIFIED_TOTAL_COUNT,
        breadth_completeness_status=BreadthCompletenessStatus.COMPLETE,
    )
    for category in STRONG_REFERENCE_CATEGORY_ORDER
)

#: ``(D, C, R, Q)`` for the median target of the strong-reference run.
STRONG_REFERENCE_COMPOSITE_COMPONENTS: tuple[float, float, float, float] = (
    0.5,
    0.5,
    0.5,
    0.5,
)

#: The expected composite for the all-0.5 components above, exact to ``1e-9``.
STRONG_REFERENCE_COMPOSITE_EXPECTED: float = 0.5


def strong_reference_composite_vector() -> dict[str, Any]:
    """Return the 21-category scoring-layer composite vector (R7).

    ``metrics`` is the 21-category run used as the leave-one-out ordering
    authority; ``target_category`` is its median category. The expected values are
    hand-derived in the module comments above and asserted within ``1e-9``.
    """
    return {
        "run_category_count": CATEGORY_COUNT_TWENTY_ONE,
        "reference_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
        "reference_size_expected": 20,
        "target_category": STRONG_REFERENCE_CATEGORY_ORDER[
            STRONG_REFERENCE_CATEGORY_COUNT // 2
        ],
        "metrics": STRONG_REFERENCE_METRICS,
        "expected_midrank": 0.5,
        "components": STRONG_REFERENCE_COMPOSITE_COMPONENTS,
        "expected_score": STRONG_REFERENCE_COMPOSITE_EXPECTED,
        "weights": dict(FIXED_COMPOSITE_WEIGHTS),
    }


# ---------------------------------------------------------------------------
# Zero-population vector (LREQ-TST-090, LREQ-MET-030/060/080/100)
# ---------------------------------------------------------------------------
#
# A verified zero-result category: ``strata = ()`` and ``N = 0``. SRS §7.2/§7.3:
# every sample-derived raw is null and no estimator evaluates ``N_h / N``;
# ``BreadthRaw = 0`` with ``breadth_source = verified_total_count`` and
# ``breadth_completeness_status = complete``; all three stratum eligibility
# coverages are ``0`` (a value, not null); ``sample_fraction`` is null because
# ``enriched_sample_count = 0``.
#
# The raw-metric side is the frozen Chunk 7B fixture
# (``fixtures.metric_estimator_fixtures.ZERO_POPULATION``); only the paired
# verified-zero breadth input and the expected shape are declared here.

ZERO_POPULATION_BREADTH: Mapping[str, Any] = {
    "verified_total_count": 0,
    "distinct_canonical_discovered_count": 0,
}
ZERO_POPULATION_EXPECTED: dict[str, Any] = {
    "demand_per_asset_raw": None,
    "demand_median_raw": None,
    "breadth_raw": 0.0,
    "recent_share_raw": None,
    "median_age_raw": None,
    "quality_raw": None,
    "demand_stratum_eligibility_coverage": 0.0,
    "recent_supply_stratum_eligibility_coverage": 0.0,
    "quality_stratum_eligibility_coverage": 0.0,
    "usable_demand_sample_count": 0,
    "usable_recent_supply_sample_count": 0,
    "usable_quality_sample_count": 0,
    "sample_fraction": None,
}


def zero_population_vector() -> dict[str, Any]:
    """Return the zero-population acceptance vector (raw side from Chunk 7B)."""
    from fixtures import metric_estimator_fixtures as metric_fx

    return {
        "category_input": metric_fx.ZERO_POPULATION,
        "breadth": dict(ZERO_POPULATION_BREADTH),
        "expected": dict(ZERO_POPULATION_EXPECTED),
    }


# ---------------------------------------------------------------------------
# Unequal-stratum QualityRaw vector (LREQ-TST-090, LREQ-MET-100)
# ---------------------------------------------------------------------------
#
# The frozen Chunk 7B fixture ``QUALITY_UNEQUAL_STRATUM_INPUTS``: two strata,
# ``N_0 = N_1 = 50``, ``n_0 = n_1 = 25``, so each stratum's expansion weight is
# ``N_h / n_h = 2.0``. Stratum 0 has 5 quality-eligible observations with
# ``rating_average = 2.5`` and index 10.0 each; stratum 1 has 5 with
# ``rating_average = 5.0`` and index 10.0 each. SRS §7.5 LREQ-MET-100:
#
#   num_0 = 2.0 * sum((2.5/5) * 10.0) = 2.0 * (5 * 5.0)  = 50.0
#   den_0 = 2.0 * sum(10.0)                              = 100.0
#   num_1 = 2.0 * sum((5.0/5) * 10.0) = 2.0 * (5 * 10.0) = 100.0
#   den_1 = 2.0 * sum(10.0)                              = 100.0
#   QualityRaw = (50.0 + 100.0) / (100.0 + 100.0) = 150.0 / 200.0 = 0.75
#
# ``quality_stratum_eligibility_coverage = 50/100 + 50/100 = 1.0`` and
# ``usable_quality_sample_count = 5 + 5 = 10``.

UNEQUAL_STRATUM_QUALITY_RAW_EXPECTED: dict[str, float] = {
    "quality_raw": 0.75,
    "quality_stratum_eligibility_coverage": 1.0,
    "usable_quality_sample_count": 10.0,
}


def unequal_stratum_quality_raw_vector() -> dict[str, Any]:
    """Return the unequal-stratum ``QualityRaw`` vector (reused Chunk 7B inputs)."""
    from fixtures import metric_estimator_fixtures as metric_fx

    return {
        "category_input": metric_fx.QUALITY_UNEQUAL_STRATA,
        "stratum_inputs": metric_fx.QUALITY_UNEQUAL_STRATUM_INPUTS,
        "expected": dict(UNEQUAL_STRATUM_QUALITY_RAW_EXPECTED),
    }


# ---------------------------------------------------------------------------
# Sample fraction versus stratum eligibility coverage (LREQ-TST-090, LREQ-MET-060)
# ---------------------------------------------------------------------------
#
# The two measures describe different properties on the SAME category (SRS §7.2
# LREQ-MET-060: "It is not the percentage of assets directly observed ... The
# persisted name is ``demand_stratum_eligibility_coverage``; it SHALL not be
# confused with ``sample_fraction``").
#
# The frozen Chunk 7B ``DEMAND_PARTIAL_COVERAGE`` fixture: stratum 0 (N_0 = 75)
# is usable (5 usable indices plus 20 unusable) and stratum 1 (N_1 = 25) has only
# 4 usable indices, below ``MIN_USABLE_SAMPLES_PER_STRATUM`` (5), so it is NOT
# usable. ``demand_stratum_eligibility_coverage = N_0 / N = 75/100 = 0.75`` (the
# unusable stratum's population weight is excluded, not zeroed). The sample
# fraction is a different ratio entirely: 45 sampled rows / 100 discovered =
# 0.45. The two numbers are distinct measures, not two spellings of one number.

SAMPLE_FRACTION_VS_COVERAGE_EXPECTED: dict[str, float] = {
    "demand_stratum_eligibility_coverage": 0.75,
    "sample_fraction": 0.45,
}


def sample_fraction_vs_coverage_vector() -> dict[str, Any]:
    """Return the sample-fraction-versus-coverage vector."""
    from fixtures import metric_estimator_fixtures as metric_fx

    return {
        "category_input": metric_fx.DEMAND_PARTIAL_COVERAGE,
        "discovered_population_count": 100,
        "enriched_sample_count": 45,
        "expected": dict(SAMPLE_FRACTION_VS_COVERAGE_EXPECTED),
    }


# ---------------------------------------------------------------------------
# Sensitivity after base-candidate construction (LREQ-TST-090, LREQ-SEN-020)
# ---------------------------------------------------------------------------
#
# SRS §9.1 LREQ-EVD-020: the implementation SHALL first construct a fixed
# ``base_rankable_candidates`` set, and sensitivity SHALL not be used to construct
# it; SRS §9.3 LREQ-SEN-040: sensitivity diagnostics qualify the balanced score and
# SHALL not silently replace it. The frozen Chunk 9B
# ``SENSITIVITY_STABLE_VECTOR`` (21-category run) exercises exactly this: five base
# candidates over a 21-category run (``reference_set_size = 20``), the balanced
# score preserved, and the sensitivity candidate set unchanged when a warning is
# raised.
#
# The expected values come from that frozen vector, never from the implementation:
# the balanced primary scores, the ranks under the three policies, and the
# ``>= 3`` base-candidate count that makes a stability output computable.

SENSITIVITY_AFTER_BASE_CANDIDATES_EXPECTED: dict[str, Any] = {
    "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "reference_set_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "base_candidate_count": 5,
    "balanced_scores": {
        "A": 0.52,
        "B": 0.48,
        "C": 0.64,
        "D": 0.50,
        "E": 0.20,
    },
    "top_3_stability": 2.0 / 3.0,
    "top_5_stability": 1.0,
    "run_warning": False,
}


def sensitivity_after_base_candidates_vector() -> dict[str, Any]:
    """Return the frozen Chunk 9B stable sensitivity vector plus its expected facts."""
    from fixtures import sensitivity_fixtures as sensitivity_fx

    return {
        "vector": sensitivity_fx.SENSITIVITY_STABLE_VECTOR,
        "expected": dict(SENSITIVITY_AFTER_BASE_CANDIDATES_EXPECTED),
    }


# ---------------------------------------------------------------------------
# Eight-category provisional vector (LREQ-TST-090, LREQ-SEN-020)
# ---------------------------------------------------------------------------


def eight_category_provisional_vector() -> dict[str, Any]:
    """Return the 8-category provisional expected shape (R7: scoring layer only).

    A run of 8-20 categories has an empty ``base_rankable_candidates`` set: every
    stability and displacement output is null, never ``0.0``, and the run-level
    warning is null (dependency-map §6.2/§6.3). The 8-category pipeline fixture is
    the existing ``fixtures.pipeline_fixtures.end_to_end_scenario``; this helper
    only names the expected shape.
    """
    return {
        "run_category_count": CATEGORY_COUNT_EIGHT,
        "expected": dict(EIGHT_CATEGORY_PROVISIONAL_EXPECTED),
    }


# ---------------------------------------------------------------------------
# The contradicted-page-view wrapper repository (R8)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ContradictedRepositoryHandle:
    """The opened wrapper plus the run id it rewrote, for a caller to read back."""

    repository: "ContradictedPageViewRepository"
    run_id: str


@dataclass(frozen=True, slots=True)
class _ContradictedRepositoryHandle:
    """The opened wrapper plus the run id it rewrote, for a caller to read back."""

    repository: "ContradictedPageViewRepository"
    run_id: str


class ContradictedPageViewRepository:
    """A ``SqliteRepository`` wrapper that marks one run's page views contradicted.

    The pipeline writes the run row with ``page_view_semantics_status =
    unvalidated`` inside ``run_pipeline``; this wrapper intercepts that write and
    substitutes ``PageViewSemanticsStatus.CONTRADICTED.value`` for the targeted
    ``run_id`` before delegating to the real repository on disk. The frozen
    preflight write is non-clobbering for a ``contradicted`` value (it only
    overwrites when the current value is neither ``validated_cumulative`` nor
    ``contradicted``), so the run is scored with contradicted page views and D/Q
    become unavailable while C/R may remain and the category is not rankable
    (SRS §8.2 LREQ-SCR-050, §7.5 LREQ-MET-090).
    """

    def __init__(self, db_path: Path, *, run_id: str) -> None:
        self._inner = SqliteRepository(Path(db_path))
        self._run_id = str(run_id)

    # -- write interception -------------------------------------------------

    def insert_run(self, record: Any) -> None:
        """Delegate to the real insert, rewriting the target run's status first.

        ``record`` is a ``models.RunRecord``; when its ``run_id`` is the targeted
        run the page-view semantics status is replaced with ``contradicted`` (the
        only field changed) before the real insert.
        """
        if getattr(record, "run_id", None) == self._run_id:
            record = _with_contradicted_page_views(record)
        self._inner.insert_run(record)

    # -- passthrough --------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """Delegate every other attribute to the wrapped repository."""
        return getattr(self._inner, name)

    def close(self) -> None:
        """Close the wrapped repository."""
        self._inner.close()

    def __enter__(self) -> "ContradictedPageViewRepository":
        """Enter the wrapped repository's context manager."""
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        """Exit the wrapped repository's context manager."""
        return bool(self._inner.__exit__(exc_type, exc, tb))


def _with_contradicted_page_views(record: Any) -> Any:
    """Return ``record`` with ``page_view_semantics_status`` set to contradicted."""
    return replace(
        record,
        page_view_semantics_status=PageViewSemanticsStatus.CONTRADICTED.value,
    )


def contradicted_repository_factory(
    run_id: str,
) -> Any:
    """Return an ``open_repository`` seam that yields the contradicted wrapper.

    The callable matches the frozen ``cli.run_command(..., open_repository=...)``
    signature: it receives the resolved ``db_path`` and returns the wrapper, whose
    ``insert_run`` rewrites the target ``run_id``. Every wrapper it opens is
    appended to the callable's ``opened`` list so a caller can release the SQLite
    lock with ``close_opened(opened_repository)``.
    """

    def open_repository(db_path: Path) -> ContradictedPageViewRepository:
        repository = ContradictedPageViewRepository(db_path, run_id=run_id)
        open_repository.opened.append(repository)
        return repository

    open_repository.opened = []
    return open_repository


def close_opened(open_repository: Any) -> None:
    """Close every repository a :func:`contradicted_repository_factory` opened."""
    for repository in list(getattr(open_repository, "opened", ())):
        repository.close()


# ---------------------------------------------------------------------------
# Small helpers shared by the acceptance tests
# ---------------------------------------------------------------------------


def run_row_categories(run_row: Any) -> tuple[str, ...]:
    """Return the declared categories in ``runs.categories_json``, or ``()``.

    A malformed or absent payload yields ``()``; the helper never guesses a
    category list.
    """
    try:
        decoded = json.loads(run_row.categories_json)
    except (AttributeError, TypeError, ValueError):
        return ()
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) and item for item in decoded
    ):
        return ()
    return tuple(decoded)


def logical_rows(rows: Sequence[Any]) -> tuple[tuple[Any, ...], ...]:
    """Return ``CategoryScoreRecord`` rows with ``run_id`` removed, for equality.

    Two runs over identical inputs must produce structurally equal persisted rows
    (SRS §3.3 LREQ-ARCH-030); the run id is the one field that legitimately
    differs.
    """
    return tuple(
        tuple(
            getattr(row, field_name)
            for field_name in row.__dataclass_fields__
            if field_name != "run_id"
        )
        for row in rows
    )


def utc_now_clock(value: Any = None) -> Any:
    """Return a clock lambda over an explicit aware-UTC instant.

    Provided so no test needs ``datetime.now``; a caller passes a fixed
    ``datetime`` and receives a callable that always returns it.
    """
    instant = (
        value
        if isinstance(value, datetime)
        else datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
    )
    if instant.tzinfo is None:
        raise ValueError("the fixture clock must be timezone-aware UTC")
    return lambda: instant
