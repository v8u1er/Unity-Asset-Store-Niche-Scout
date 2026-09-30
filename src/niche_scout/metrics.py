"""Pure metric contracts and eligibility primitives.

Metric functions in later chunks consume these typed structures. ``None`` is
unavailable and must not be substituted with zero; zero remains a valid value.
All cutoff timestamps are explicit, timezone-aware UTC inputs.

This module is part of the purity boundary (SRS §3.3, LREQ-ARCH-010/020): it
performs no I/O, reads no clock, and imports no collector/database/report/cli or
filesystem module. Every primitive takes plain inputs and returns a typed
result; a product-level value that is null, wrong-typed, negative, non-finite,
naive, or future is *classified* unavailable with a distinct reason and is never
raised away and never converted to ``0`` (LREQ-MET-010).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import (
    MIN_AGE_DAYS_FOR_RATE,
    MIN_REQUIRED_COMPONENT_COVERAGE,
    MIN_USABLE_SAMPLES_PER_STRATUM,
    QUALITY_MIN_ELIGIBLE_ASSETS,
    QUALITY_MIN_RATING_COUNT,
    RECENT_WINDOW_DAYS,
    BreadthCompletenessStatus,
    BreadthSource,
    OperationStatus,
    PageViewSemanticsStatus,
    ensure_utc,
)
from .validation import annotate_state_eligibility


@dataclass(frozen=True, slots=True)
class MetricInput:
    scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus = (
        PageViewSemanticsStatus.UNVALIDATED
    )

    def __post_init__(self) -> None:
        if (
            self.scoring_cutoff_utc.tzinfo is None
            or self.scoring_cutoff_utc.utcoffset()
            != timezone.utc.utcoffset(self.scoring_cutoff_utc)
        ):
            raise ValueError("scoring_cutoff_utc must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class MetricResult:
    value: float | None
    usable_sample_count: int
    eligible_population_count: int
    eligibility_coverage: float | None
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RawMetricBundle:
    demand_per_asset_raw: float | None = None
    demand_median_raw: float | None = None
    breadth_raw: float | None = None
    recent_share_raw: float | None = None
    median_age_raw: float | None = None
    quality_raw: float | None = None


# ---------------------------------------------------------------------------
# Reason vocabulary (module-local)
# ---------------------------------------------------------------------------
#
# The SRS pins the outcome categories required by LREQ-MET-010 (null,
# malformed, wrong type, invalid range, future, naive, negative, non-finite,
# excluded state) but names no machine-readable string for them. This closed
# tuple is a module-local vocabulary; the *spelling* is a recommendation
# (chunk-7A plan §5.1, §12 A-1), matching the ``GraphQLFailureClass`` precedent.
#
# ``METRIC_REASON_MALFORMED`` is retained but produced by no function in this
# module: shape/alias classification is Chunk 1's and per-operation payload
# classification is Chunk 5's, so no primitive here receives an un-parsed shape
# (chunk-7A plan §12 A-6).

METRIC_REASON_NULL: str = "null"
METRIC_REASON_MALFORMED: str = "malformed"
METRIC_REASON_WRONG_TYPE: str = "wrong_type"
METRIC_REASON_INVALID_RANGE: str = "invalid_range"
METRIC_REASON_FUTURE_DATE: str = "future_date"
METRIC_REASON_NAIVE_DATE: str = "naive_date"
METRIC_REASON_NEGATIVE: str = "negative"
METRIC_REASON_NON_FINITE: str = "non_finite"
METRIC_REASON_STATE_EXCLUDED: str = "state_excluded"
METRIC_REASON_STATE_UNKNOWN: str = "state_unknown"
METRIC_REASON_IDENTITY_MISMATCH: str = "identity_mismatch"
METRIC_REASON_AGE_BELOW_MINIMUM: str = "age_below_minimum"
METRIC_REASON_RATING_COUNT_BELOW_MINIMUM: str = "rating_count_below_minimum"
METRIC_REASON_OPERATION_UNAVAILABLE: str = "operation_unavailable"
METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED: str = "page_view_semantics_contradicted"
METRIC_REASON_PAGE_VIEWS_UNAVAILABLE: str = "page_views_unavailable"

METRIC_UNAVAILABLE_REASONS: tuple[str, ...] = (
    METRIC_REASON_NULL,
    METRIC_REASON_MALFORMED,
    METRIC_REASON_WRONG_TYPE,
    METRIC_REASON_INVALID_RANGE,
    METRIC_REASON_FUTURE_DATE,
    METRIC_REASON_NAIVE_DATE,
    METRIC_REASON_NEGATIVE,
    METRIC_REASON_NON_FINITE,
    METRIC_REASON_STATE_EXCLUDED,
    METRIC_REASON_STATE_UNKNOWN,
    METRIC_REASON_IDENTITY_MISMATCH,
    METRIC_REASON_AGE_BELOW_MINIMUM,
    METRIC_REASON_RATING_COUNT_BELOW_MINIMUM,
    METRIC_REASON_OPERATION_UNAVAILABLE,
    METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED,
    METRIC_REASON_PAGE_VIEWS_UNAVAILABLE,
)


# ---------------------------------------------------------------------------
# Typed result structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricTimestamp:
    """A UTC-normalized metric timestamp, or the reason it is unusable.

    ``value_utc`` is non-``None`` iff ``unavailable_reason is None``; the three
    unavailable states — ``None``, a naive datetime, and a wrong-typed value —
    are reported by three distinct reasons (``null``, ``naive_date``,
    ``wrong_type``). An aware value in another offset is converted to UTC, never
    rejected. ``MetricTimestamp(value_utc=None, unavailable_reason=None)`` is an
    invalid state and is never returned.
    """

    value_utc: datetime | None = None
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        """True iff this timestamp is a usable UTC datetime."""
        return self.value_utc is not None and self.unavailable_reason is None


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A single derived metric value, or the reason it is unavailable.

    Field names, types, and the null contract reuse the frozen
    ``MetricResult.value: float | None`` and ``MetricResult.unavailable_reason:
    str | None``: ``value is None`` iff the value is unavailable, and
    ``value == 0.0`` is an explicit valid zero, never an unavailable substitute.
    This is a per-observation primitive with no sample/population counts or
    coverage; the category-level ``MetricResult`` aggregate is assembled by
    Chunk 7B from these values. ``MetricValue(value=None,
    unavailable_reason=None)`` is never returned by a function in this module.
    """

    value: float | None = None
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        """True iff a finite value is present."""
        return self.value is not None and self.unavailable_reason is None


@dataclass(frozen=True, slots=True)
class MetricEligibility:
    """A per-observation eligibility verdict and, when ineligible, its reason.

    ``unavailable_reason`` reuses ``MetricResult.unavailable_reason``'s
    contract: ``None`` iff ``eligible`` is True, else a member of
    ``METRIC_UNAVAILABLE_REASONS``. No numeric value is fabricated for an
    eligibility verdict. ``MetricEligibility(eligible=True,
    unavailable_reason=<non-None>)`` is never returned.
    """

    eligible: bool
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        """True iff the observation is eligible (no unavailable reason)."""
        return self.eligible and self.unavailable_reason is None


# ---------------------------------------------------------------------------
# Internal validation helpers (no I/O, no clock)
# ---------------------------------------------------------------------------


def _require_utc_cutoff(scoring_cutoff_utc: datetime) -> None:
    """Raise ``ValueError`` unless ``scoring_cutoff_utc`` is aware UTC.

    Mirrors ``MetricInput.__post_init__``: the scoring cutoff is a caller/policy
    parameter, never a product-level value, so a breach is raised rather than
    classified.
    """
    if (
        scoring_cutoff_utc.tzinfo is None
        or scoring_cutoff_utc.utcoffset() != timezone.utc.utcoffset(scoring_cutoff_utc)
    ):
        raise ValueError("scoring_cutoff_utc must be timezone-aware UTC")


def _require_int_minimum(value: object, *, name: str) -> int:
    """Return ``value`` as an ``int >= 0``, rejecting ``bool`` and non-ints.

    A caller/policy parameter breach raises ``ValueError``; ``bool`` is rejected
    explicitly because ``isinstance(True, int)`` is ``True`` in Python.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be an int >= 0")
    return value


def _classify_page_views(product_page_views: object) -> str | None:
    """Classify a product-level page-view value; return a reason or ``None``.

    ``None`` is ``page_views_unavailable``; a ``bool`` or any non-numeric object
    is ``wrong_type``; a non-finite float is ``non_finite``; a numeric value
    below ``0`` is ``negative``. A finite non-negative ``int`` or ``float`` is
    accepted (a float with zero fractional part is the equal integer value).
    Never raises.
    """
    if product_page_views is None:
        return METRIC_REASON_PAGE_VIEWS_UNAVAILABLE
    if isinstance(product_page_views, bool):
        return METRIC_REASON_WRONG_TYPE
    if not isinstance(product_page_views, (int, float)):
        return METRIC_REASON_WRONG_TYPE
    if isinstance(product_page_views, float) and not math.isfinite(product_page_views):
        return METRIC_REASON_NON_FINITE
    if product_page_views < 0:
        return METRIC_REASON_NEGATIVE
    return None


def _classify_date(
    first_published_date_utc: object,
) -> tuple[datetime | None, str | None]:
    """Classify a product-level timestamp to aware UTC; return value and reason.

    ``None`` is ``null``; a non-``datetime`` object is ``wrong_type``; a naive
    datetime is ``naive_date``; an aware value in another offset is converted to
    UTC. Exactly one of the pair is meaningful. Never raises.
    """
    if first_published_date_utc is None:
        return None, METRIC_REASON_NULL
    if not isinstance(first_published_date_utc, datetime):
        return None, METRIC_REASON_WRONG_TYPE
    if first_published_date_utc.tzinfo is None:
        return None, METRIC_REASON_NAIVE_DATE
    return first_published_date_utc.astimezone(timezone.utc), None


def _state_reason(state: object) -> str | None:
    """Return the state eligibility reason for ``state``, or ``None`` if eligible.

    Delegates to Chunk 1's ``annotate_state_eligibility`` rather than
    re-deriving the published/excluded/unknown rule: a published state (matched
    case-insensitively) is eligible; a present non-published state is
    ``state_excluded``; a missing/None/unparsable value is ``state_unknown``.
    """
    annotation = annotate_state_eligibility(state)
    if annotation.is_published:
        return None
    if annotation.state_excluded:
        return METRIC_REASON_STATE_EXCLUDED
    return METRIC_REASON_STATE_UNKNOWN


def _classify_rating_average(rating_average: object) -> str | None:
    """Classify ``rating_average``; return a reason or ``None`` when usable.

    ``None`` is ``null``; a ``bool`` or non-numeric object is ``wrong_type``; a
    non-finite float is ``non_finite``; a value outside the inclusive ``[0, 5]``
    range is ``invalid_range``. Never raises.
    """
    if rating_average is None:
        return METRIC_REASON_NULL
    if isinstance(rating_average, bool) or not isinstance(rating_average, (int, float)):
        return METRIC_REASON_WRONG_TYPE
    if isinstance(rating_average, float) and not math.isfinite(rating_average):
        return METRIC_REASON_NON_FINITE
    if rating_average < 0 or rating_average > 5:
        return METRIC_REASON_INVALID_RANGE
    return None


def _classify_rating_count(
    rating_count: object,
    *,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> str | None:
    """Classify ``rating_count``; return a reason or ``None`` when usable.

    ``None`` is ``null``; a ``bool`` or non-integral numeric object is
    ``wrong_type`` (a finite float with zero fractional part is accepted as the
    equal ``int``, where ``4.5`` is non-integral and therefore wrong-typed); a
    non-finite float is ``non_finite``; an integral value ``< 0`` is
    ``negative``; an integral value ``< quality_min_rating_count`` is
    ``rating_count_below_minimum``. ``quality_min_rating_count`` is a
    caller/policy parameter (SRS §14 ``QUALITY_MIN_RATING_COUNT``, default 5)
    and never a product-level value. Never raises for ``rating_count``.
    """
    if rating_count is None:
        return METRIC_REASON_NULL
    if isinstance(rating_count, bool) or not isinstance(rating_count, (int, float)):
        return METRIC_REASON_WRONG_TYPE
    if isinstance(rating_count, float):
        if not math.isfinite(rating_count):
            return METRIC_REASON_NON_FINITE
        if not rating_count.is_integer():
            return METRIC_REASON_WRONG_TYPE
        integral_count = int(rating_count)
    else:
        integral_count = rating_count
    if integral_count < 0:
        return METRIC_REASON_NEGATIVE
    if integral_count < quality_min_rating_count:
        return METRIC_REASON_RATING_COUNT_BELOW_MINIMUM
    return None


# ---------------------------------------------------------------------------
# Public primitives
# ---------------------------------------------------------------------------


def normalize_metric_timestamp(value: object) -> MetricTimestamp:
    """Normalize a supplied product-level timestamp to timezone-aware UTC.

    Product-level classification (LREQ-MET-010, LREQ-MET-020):

    - ``None`` → ``MetricTimestamp(None, METRIC_REASON_NULL)``.
    - a naive ``datetime`` → ``MetricTimestamp(None, METRIC_REASON_NAIVE_DATE)``:
      ``models.ensure_utc``'s ``ValueError`` is caught and turned into that
      reason, and no local-time ``astimezone`` is applied.
    - an aware ``datetime`` in another offset → converted to UTC with
      ``models.ensure_utc`` and returned available.
    - any other object (a ``str``, ``int``, ``bool``, ``date``, list, …) →
      ``MetricTimestamp(None, METRIC_REASON_WRONG_TYPE)``: a malformed
      product-level value is classified unavailable, never raised away and never
      replaced by a fabricated timestamp.

    No input raises. Pure.
    """
    if value is None:
        return MetricTimestamp(value_utc=None, unavailable_reason=METRIC_REASON_NULL)
    if not isinstance(value, datetime):
        return MetricTimestamp(
            value_utc=None, unavailable_reason=METRIC_REASON_WRONG_TYPE
        )
    try:
        normalized = ensure_utc(value)
    except ValueError:
        return MetricTimestamp(
            value_utc=None, unavailable_reason=METRIC_REASON_NAIVE_DATE
        )
    return MetricTimestamp(value_utc=normalized, unavailable_reason=None)


def age_days_exact(
    first_published_date_utc: object,
    *,
    scoring_cutoff_utc: datetime,
) -> MetricValue:
    """Exact fractional age in days: ``(cutoff - date).total_seconds() / 86400``.

    ``scoring_cutoff_utc`` is a caller/policy parameter, not a product-level
    value: it must be timezone-aware UTC, else ``ValueError`` (mirrors
    ``MetricInput.__post_init__``). ``first_published_date_utc`` is a
    product-level value and is classified, never raised:

    - ``None`` → ``METRIC_REASON_NULL``.
    - a non-``datetime``, non-``None`` object → ``METRIC_REASON_WRONG_TYPE``.
    - a naive ``datetime`` → ``METRIC_REASON_NAIVE_DATE``.
    - a date later than ``scoring_cutoff_utc`` (``age < 0``) →
      ``METRIC_REASON_FUTURE_DATE``.
    - otherwise the exact ``float64`` age is returned, **without floor**; an age
      of exactly ``0.0`` (date == cutoff) is a valid zero and is returned as
      available, not future.

    No age threshold is applied here (LREQ-MET-010, LREQ-MET-020; SRS §7.1).
    Pure.
    """
    _require_utc_cutoff(scoring_cutoff_utc)
    published_utc, reason = _classify_date(first_published_date_utc)
    if reason is not None:
        return MetricValue(value=None, unavailable_reason=reason)
    assert published_utc is not None  # narrowed by the reason check above
    age = (scoring_cutoff_utc - published_utc).total_seconds() / 86400.0
    if age < 0:
        return MetricValue(value=None, unavailable_reason=METRIC_REASON_FUTURE_DATE)
    return MetricValue(value=age, unavailable_reason=None)


def age_normalized_page_view_index(
    product_page_views: object,
    first_published_date_utc: object,
    *,
    scoring_cutoff_utc: datetime,
    state: str | None,
    id_mapping_mismatch: bool,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
) -> MetricValue:
    """The page-view index for one observation (LREQ-MET-040).

    The value is the trailing-7-day (weekly) page-view count,
    ``= product_page_views`` (OQ-11). The symbol name
    ``age_normalized_page_view_index`` is a **historical label** for that weekly
    count: the index is no longer age-normalized and is not a function of
    ``age_days_exact`` above the eligibility floor (two observations with the
    same views and ages ``30`` and ``300`` produce the same index).

    The value is usable only when the page-view value, a valid UTC date no later
    than cutoff, ``age_days_exact >= min_age_days_for_rate``, a matched identity,
    and ``state == "published"`` all pass; otherwise ``value is None`` with a
    distinct reason. An explicit ``product_page_views == 0`` is usable and
    yields ``0.0`` (never unavailable). ``min_age_days_for_rate`` is a
    caller/policy parameter, not a product-level value, and must be ``>= 1``,
    else ``ValueError``; it is an eligibility floor only.

    Deterministic reason precedence (LREQ-MET-010; LREQ-MET-040). Steps 1–5
    classify the product-level page-view value defensively; steps 6–13 follow
    the conjunct order of the LREQ-MET-040 sentence (page-view value, date, age,
    then "a matched, published identity"), with identity checked before
    published state:

    1. ``product_page_views is None`` → ``METRIC_REASON_PAGE_VIEWS_UNAVAILABLE``.
    2. ``product_page_views`` is a ``bool`` → ``METRIC_REASON_WRONG_TYPE``.
    3. ``product_page_views`` is neither ``int`` nor ``float`` →
       ``METRIC_REASON_WRONG_TYPE``.
    4. a non-finite ``float`` → ``METRIC_REASON_NON_FINITE``.
    5. an ``int`` or ``float`` ``< 0`` → ``METRIC_REASON_NEGATIVE``.
    6. ``first_published_date_utc is None`` → ``METRIC_REASON_NULL``.
    7. a non-``datetime``, non-``None`` date → ``METRIC_REASON_WRONG_TYPE``.
    8. naive date → ``METRIC_REASON_NAIVE_DATE``.
    9. date later than cutoff → ``METRIC_REASON_FUTURE_DATE``.
    10. ``age_days_exact < min_age_days_for_rate`` →
        ``METRIC_REASON_AGE_BELOW_MINIMUM`` (covers ``age_days_exact == 0.0``).
    11. ``id_mapping_mismatch is True`` → ``METRIC_REASON_IDENTITY_MISMATCH``.
    12. state not ``"published"`` → ``METRIC_REASON_STATE_EXCLUDED`` or
        ``METRIC_REASON_STATE_UNKNOWN``, via Chunk 1's
        ``annotate_state_eligibility`` (LREQ-GQL-060/GQL-070).
    13. otherwise ``value = float(product_page_views)`` — the weekly view count.

    Chunk 5's per-operation acceptance decision (``PageViewValue`` /
    ``GraphQLFailureClass``) is **not** re-derived; steps 1–5 are Chunk 7A's
    product-level value classification required by LREQ-MET-010. No input
    raises for a product-level value. Pure.
    """
    if isinstance(min_age_days_for_rate, bool) or not isinstance(
        min_age_days_for_rate, int
    ):
        raise ValueError("min_age_days_for_rate must be an int >= 1")
    if min_age_days_for_rate < 1:
        raise ValueError("min_age_days_for_rate must be an int >= 1")
    _require_utc_cutoff(scoring_cutoff_utc)

    reason = _classify_page_views(product_page_views)
    if reason is not None:
        return MetricValue(value=None, unavailable_reason=reason)

    published_utc, reason = _classify_date(first_published_date_utc)
    if reason is not None:
        return MetricValue(value=None, unavailable_reason=reason)
    assert published_utc is not None  # narrowed by the reason check above

    age = (scoring_cutoff_utc - published_utc).total_seconds() / 86400.0
    if age < 0:
        return MetricValue(value=None, unavailable_reason=METRIC_REASON_FUTURE_DATE)
    if age < min_age_days_for_rate:
        return MetricValue(
            value=None, unavailable_reason=METRIC_REASON_AGE_BELOW_MINIMUM
        )

    if id_mapping_mismatch is True:
        return MetricValue(
            value=None, unavailable_reason=METRIC_REASON_IDENTITY_MISMATCH
        )

    state_reason = _state_reason(state)
    if state_reason is not None:
        return MetricValue(value=None, unavailable_reason=state_reason)

    return MetricValue(value=float(product_page_views), unavailable_reason=None)


def metric_state_eligibility(state: str | None) -> MetricEligibility:
    """Published-state metric eligibility (LREQ-GQL-060).

    Calls Chunk 1's ``annotate_state_eligibility``. ``state == "published"``
    (matched case-insensitively) → eligible; a present non-published state →
    ``METRIC_REASON_STATE_EXCLUDED``; a missing/null/unparsable state →
    ``METRIC_REASON_STATE_UNKNOWN``. Both unavailable states remain in
    discovered breadth (that decision is Chunk 1's annotation and is not changed
    here). No exception is raised for any ``state`` value. Pure.
    """
    reason = _state_reason(state)
    if reason is None:
        return MetricEligibility(eligible=True, unavailable_reason=None)
    return MetricEligibility(eligible=False, unavailable_reason=reason)


def is_within_recent_window(
    age_days_exact: float,
    *,
    recent_window_days: int = RECENT_WINDOW_DAYS,
) -> bool:
    """Inclusive recent-window membership: ``0 <= age <= recent_window_days``.

    ``recent_window_days`` must be an ``int >= 0``, else ``ValueError``; it is
    the SRS-configurable ``RECENT_WINDOW_DAYS`` (§14), passed explicitly and
    defaulted from ``models``. A non-finite ``age_days_exact``
    (NaN/±Infinity) returns ``False`` and never contributes a count; ``0.0`` and
    the exact upper boundary are ``True`` (SRS §7.4, LREQ-MET-080). The
    ``age_days_exact`` argument is a product-level-derived value and is never
    raised for: a non-finite age is a ``False`` membership, not an error. Pure.
    """
    _require_int_minimum(recent_window_days, name="recent_window_days")
    if not math.isfinite(age_days_exact):
        return False
    return 0.0 <= age_days_exact <= recent_window_days


def stratum_is_usable(
    usable_observation_count: int,
    *,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
) -> bool:
    """A stratum is usable iff ``usable_observation_count >= min`` (LREQ-MET-030).

    ``usable_observation_count`` must be an ``int >= 0`` (``bool`` rejected with
    ``ValueError``); ``min_usable_samples_per_stratum`` must be an ``int >= 0``.
    The boundary is inclusive: count ``== min`` is usable. Pure; it computes no
    coverage and no stratum weight.
    """
    _require_int_minimum(usable_observation_count, name="usable_observation_count")
    _require_int_minimum(
        min_usable_samples_per_stratum,
        name="min_usable_samples_per_stratum",
    )
    return usable_observation_count >= min_usable_samples_per_stratum


def quality_observation_eligibility(
    *,
    product_detail_status: OperationStatus,
    page_views_status: OperationStatus,
    id_mapping_mismatch: bool,
    state: str | None,
    rating_average: object,
    rating_count: object,
    page_view_semantics_status: PageViewSemanticsStatus,
    product_page_views: object,
    first_published_date_utc: object,
    scoring_cutoff_utc: datetime,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> MetricEligibility:
    """Per-observation quality eligibility (SRS §7.5, LREQ-MET-090).

    An observation is quality-eligible only when every condition holds;
    otherwise ``eligible is False`` with the first failing reason in the order
    SRS §7.5 lists the conditions. Product-level values (``rating_average``,
    ``rating_count``, ``product_page_views``, ``first_published_date_utc``) are
    classified, not raised (LREQ-MET-010):

    1. ``product_detail_status`` or ``page_views_status`` is not
       ``OperationStatus.SUCCESS`` → ``METRIC_REASON_OPERATION_UNAVAILABLE``
       (a persisted ``str`` equal to the enum value compares equal and is
       accepted).
    2. ``id_mapping_mismatch is True`` → ``METRIC_REASON_IDENTITY_MISMATCH``.
    3. state not ``"published"`` → ``METRIC_REASON_STATE_EXCLUDED`` /
       ``METRIC_REASON_STATE_UNKNOWN`` (a wrong-typed ``state`` is
       ``state_unknown`` via Chunk 1's annotation).
    4. ``rating_average``: ``None`` → ``METRIC_REASON_NULL``; a ``bool`` or any
       non-numeric object → ``METRIC_REASON_WRONG_TYPE``; a non-finite ``float``
       → ``METRIC_REASON_NON_FINITE``; outside ``[0, 5]`` →
       ``METRIC_REASON_INVALID_RANGE``.
    5. ``rating_count``: ``None`` → ``METRIC_REASON_NULL``; a ``bool`` or any
       non-integral numeric object → ``METRIC_REASON_WRONG_TYPE`` (a finite
       ``float`` with zero fractional part is accepted as the equal ``int``);
       an integral value ``< 0`` → ``METRIC_REASON_NEGATIVE``;
       ``< quality_min_rating_count`` →
       ``METRIC_REASON_RATING_COUNT_BELOW_MINIMUM``.
    6. the page-view index is unusable (delegated to
       :func:`age_normalized_page_view_index` with ``min_age_days_for_rate``,
       whose steps 1–5 classify ``product_page_views`` and
       ``first_published_date_utc`` the same way) → that function's reason.
    7. ``page_view_semantics_status is PageViewSemanticsStatus.CONTRADICTED`` →
       ``METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED``.
    8. otherwise ``eligible = True``.

    ``rating_count`` is a reliability minimum only and never weights anything
    here. ``contradicted`` is consumed, not detected (Chunk 7B detects it). No
    product-level value raises; only a caller/policy parameter breach does
    (``scoring_cutoff_utc`` not timezone-aware UTC, or ``min_age_days_for_rate``
    / ``quality_min_rating_count`` not an ``int >= 1``). Pure.
    """
    _require_positive_int(min_age_days_for_rate, name="min_age_days_for_rate")
    _require_positive_int(quality_min_rating_count, name="quality_min_rating_count")
    if product_detail_status != OperationStatus.SUCCESS or (
        page_views_status != OperationStatus.SUCCESS
    ):
        return MetricEligibility(
            eligible=False, unavailable_reason=METRIC_REASON_OPERATION_UNAVAILABLE
        )

    if id_mapping_mismatch is True:
        return MetricEligibility(
            eligible=False, unavailable_reason=METRIC_REASON_IDENTITY_MISMATCH
        )

    state_reason = _state_reason(state)
    if state_reason is not None:
        return MetricEligibility(eligible=False, unavailable_reason=state_reason)

    reason = _classify_rating_average(rating_average)
    if reason is not None:
        return MetricEligibility(eligible=False, unavailable_reason=reason)

    reason = _classify_rating_count(
        rating_count, quality_min_rating_count=quality_min_rating_count
    )
    if reason is not None:
        return MetricEligibility(eligible=False, unavailable_reason=reason)

    index = age_normalized_page_view_index(
        product_page_views,
        first_published_date_utc,
        scoring_cutoff_utc=scoring_cutoff_utc,
        state=state,
        id_mapping_mismatch=id_mapping_mismatch,
        min_age_days_for_rate=min_age_days_for_rate,
    )
    if not index.is_available:
        return MetricEligibility(
            eligible=False, unavailable_reason=index.unavailable_reason
        )

    if page_view_semantics_status == PageViewSemanticsStatus.CONTRADICTED:
        return MetricEligibility(
            eligible=False,
            unavailable_reason=METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED,
        )

    return MetricEligibility(eligible=True, unavailable_reason=None)


# ===========================================================================
# Chunk 7B — sample-aware raw estimators
# ===========================================================================
#
# Everything below aggregates Chunk 7A's per-observation primitives into the
# six category-level raw values, the three stratum-eligibility coverages, the
# stratum expansion weight ``N_h / n_h``, and the shared exact-boundary weighted
# median (SRS §7.2–§7.5). It is additive: no Chunk 0/7A name above is changed.
#
# Purity (LREQ-ARCH-010/020): no I/O, no clock, no randomness, no ``json``, and
# no collector/database/report/cli/config/scoring import. ``scoring_cutoff_utc``
# is always an explicit parameter. ``ValueError`` is raised only for caller or
# policy breaches; a product-level value is classified by Chunk 7A and never
# raised away and never turned into ``0`` (SRS §1.2).


# ---------------------------------------------------------------------------
# Aggregate unavailable-reason vocabulary (module-local; §5.1)
# ---------------------------------------------------------------------------
#
# The SRS names the outcome categories ("null when no stratum …", "null when the
# eligible set is too small", "denominator is zero", "coverage below the
# threshold") but no machine-readable string. This closed tuple follows Chunk
# 7A's ``METRIC_UNAVAILABLE_REASONS`` precedent; the string *spelling* is a
# RECOMMENDATION (plan §12 Q-6).

METRIC_REASON_NO_USABLE_STRATUM: str = "no_usable_stratum"
METRIC_REASON_ZERO_POPULATION: str = "zero_population"
METRIC_REASON_EMPTY_USABLE_SAMPLE: str = "empty_usable_sample"
METRIC_REASON_ELIGIBLE_SET_TOO_SMALL: str = "eligible_set_too_small"
METRIC_REASON_ZERO_DENOMINATOR: str = "zero_denominator"
METRIC_REASON_INSUFFICIENT_COVERAGE: str = "insufficient_coverage"

METRIC_AGGREGATE_UNAVAILABLE_REASONS: tuple[str, ...] = (
    METRIC_REASON_NO_USABLE_STRATUM,
    METRIC_REASON_ZERO_POPULATION,
    METRIC_REASON_EMPTY_USABLE_SAMPLE,
    METRIC_REASON_ELIGIBLE_SET_TOO_SMALL,
    METRIC_REASON_ZERO_DENOMINATOR,
    METRIC_REASON_INSUFFICIENT_COVERAGE,
)


# ---------------------------------------------------------------------------
# Typed inputs and results (§5.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """One sampled asset's product-level inputs for every 7B estimator.

    Fields mirror the persisted ``EnrichmentObservationRecord`` columns and are
    passed to Chunk 7A's primitives unchanged; Chunk 7B never re-classifies
    them. ``product_page_views``, ``first_published_date_utc``,
    ``rating_average``, and ``rating_count`` are typed ``object`` because a
    product-level value may be null, wrong-typed, non-finite, or out of range,
    and Chunk 7A *classifies* that rather than raising (LREQ-MET-010).

    ``product_detail_status`` / ``page_views_status`` carry the per-operation
    status; a persisted ``str`` equal to the enum value compares equal and is
    accepted by Chunk 7A.
    """

    product_page_views: object
    first_published_date_utc: object
    state: str | None
    id_mapping_mismatch: bool
    rating_average: object
    rating_count: object
    product_detail_status: OperationStatus
    page_views_status: OperationStatus


@dataclass(frozen=True, slots=True)
class StratumMetricInput:
    """One stratum's authoritative population facts plus its sampled assets.

    ``discovered_population_count`` is ``N_h``; ``sampled_population_count`` is
    ``n_h`` (SRS §7.2: the persisted stratum summary is authoritative for ``N_h``
    and ``n_h``; formulas SHALL not reconstruct population denominators from the
    sample). The usable counts ``u_demand_h`` / ``u_recent_h`` / ``u_quality_h``
    are **not** inputs: Chunk 7B recomputes them from ``observations`` so Chunk
    10 can verify the agreement gate. ``len(observations)`` MUST equal
    ``sampled_population_count``; both require a positive ``int`` (``bool``
    rejected) and a mismatch raises ``ValueError`` at construction.
    """

    stratum_index: int
    discovered_population_count: int
    sampled_population_count: int
    observations: tuple[MetricObservation, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.stratum_index, bool)
            or not isinstance(self.stratum_index, int)
            or self.stratum_index < 0
        ):
            raise ValueError("stratum_index must be an int >= 0")
        _require_positive_int(
            self.discovered_population_count,
            name="discovered_population_count",
        )
        _require_positive_int(
            self.sampled_population_count,
            name="sampled_population_count",
        )
        observations = tuple(self.observations)
        if len(observations) != self.sampled_population_count:
            raise ValueError(
                "len(observations) must equal sampled_population_count "
                f"(got {len(observations)} and {self.sampled_population_count})"
            )


@dataclass(frozen=True, slots=True)
class CategoryMetricInput:
    """Everything the six raw estimators need for one category (SRS §7).

    ``strata`` is in ascending ``stratum_index`` order. ``N = sum(N_h)`` and is
    never supplied separately. Threshold parameters default to the frozen
    ``models`` constants because SRS §14 marks them configurable; production
    callers use the defaults.

    ``quality_min_rating_count`` is **live** for the Chunk 7B quality estimator.
    :func:`_quality_observation_index` forwards it (with
    ``min_age_days_for_rate``) to Chunk 7A's
    :func:`quality_observation_eligibility`, so a caller-supplied override
    changes ``quality_stratum_eligibility_coverage``, ``quality_raw``, and
    ``usable_quality_sample_count`` (LREQ-MET-090; SRS §14 marks it Configurable
    ``Yes``). The field is part of the frozen plan §5.2 contract and is retained
    (and validated at construction) unchanged.

    Construction validates the caller/policy contract (a caller breach raises
    ``ValueError``): ``scoring_cutoff_utc`` must be timezone-aware UTC;
    ``stratum_index`` values must be unique; ``min_usable_samples_per_stratum``
    / ``min_age_days_for_rate`` / ``recent_window_days`` /
    ``quality_min_rating_count`` / ``quality_min_eligible_assets`` must be
    ``int`` (not ``bool``) and (except ``recent_window_days``, ``>= 0``) at
    least ``1``; ``min_required_component_coverage`` must be a finite ``float``
    in ``[0, 1]``. ``page_view_semantics_status`` is consumed as supplied and is
    never detected here (plan §12 Q-1).
    """

    category: str
    scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus
    strata: tuple[StratumMetricInput, ...]
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE
    recent_window_days: int = RECENT_WINDOW_DAYS
    #: Live for Chunk 7B: ``_quality_observation_index`` forwards this to Chunk
    #: 7A's ``quality_observation_eligibility``, so an override changes
    #: ``quality_stratum_eligibility_coverage``, ``quality_raw``, and
    #: ``usable_quality_sample_count`` (LREQ-MET-090). Retained from the frozen
    #: plan §5.2 contract; validated at construction only.
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT
    quality_min_eligible_assets: int = QUALITY_MIN_ELIGIBLE_ASSETS
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE

    def __post_init__(self) -> None:
        _require_utc_cutoff(self.scoring_cutoff_utc)
        _require_int_minimum(
            self.min_usable_samples_per_stratum,
            name="min_usable_samples_per_stratum",
        )
        _require_int_minimum(self.recent_window_days, name="recent_window_days")
        for name in (
            "min_age_days_for_rate",
            "quality_min_rating_count",
            "quality_min_eligible_assets",
        ):
            # ``_require_positive_int`` rejects ``bool`` and non-``int`` and
            # enforces ``>= 1``, matching this class's documented caller
            # contract; a bare ``< 1`` check would let ``True`` act as ``1`` and
            # a ``str`` raise ``TypeError``.
            _require_positive_int(getattr(self, name), name=name)
        coverage = self.min_required_component_coverage
        if isinstance(coverage, bool) or not isinstance(coverage, (int, float)):
            raise ValueError("min_required_component_coverage must be a float")
        if not math.isfinite(coverage) or coverage < 0 or coverage > 1:
            raise ValueError("min_required_component_coverage must be in [0, 1]")
        indices = [stratum.stratum_index for stratum in self.strata]
        if len(indices) != len(set(indices)):
            raise ValueError("stratum_index values must be unique")


@dataclass(frozen=True, slots=True)
class BreadthMetricInput:
    """The already-classified discovery facts for one category (SRS §7.3).

    ``verified_total_count`` is the endpoint ``totalCount`` only when it is
    structurally verified and category-filter-consistent, else ``None`` (Chunk
    3's ``CategoryDiscoveryResult.total_count`` semantics).
    ``distinct_canonical_discovered_count`` is Chunk 3's
    ``canonical_identity_count``: distinct resolved keys with duplicates
    collapsed and unresolved/conflict records excluded. Both must be ``int >= 0``
    (``bool`` rejected), else ``ValueError``.
    """

    verified_total_count: int | None
    distinct_canonical_discovered_count: int

    def __post_init__(self) -> None:
        if self.verified_total_count is not None:
            _require_int_minimum(
                self.verified_total_count,
                name="verified_total_count",
            )
        _require_int_minimum(
            self.distinct_canonical_discovered_count,
            name="distinct_canonical_discovered_count",
        )


@dataclass(frozen=True, slots=True)
class BreadthResult:
    """``BreadthRaw`` plus its provenance (SRS §7.3). Never null (plan Q-4)."""

    breadth_raw: int
    breadth_source: BreadthSource
    breadth_completeness_status: BreadthCompletenessStatus


@dataclass(frozen=True, slots=True)
class CategoryRawMetrics:
    """The frozen ``RawMetricBundle`` plus the SRS-named coverage/count fields.

    ``usable_*_sample_count`` follow SRS §6.5/§7.4: observations contributing
    to strata that satisfy the applicable usable minimum. In particular
    ``usable_recent_supply_sample_count`` is the sum of usable dated
    observations in the Recent-Supply-usable strata only (SRS §7.4), and
    ``usable_demand_sample_count`` is the sum of usable demand indices in the
    demand-usable strata (SRS §6.5), never a count over every stratum.
    """

    category: str
    raw: RawMetricBundle
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: BreadthSource
    breadth_completeness_status: BreadthCompletenessStatus


# ---------------------------------------------------------------------------
# Internal Chunk 7B helpers (pure; no I/O, no clock)
# ---------------------------------------------------------------------------


def _require_positive_int(value: object, *, name: str) -> int:
    """Return ``value`` as an ``int >= 1``; reject ``bool`` and non-ints.

    ``bool`` is rejected explicitly because ``isinstance(True, int)`` is
    ``True``. A caller/policy breach raises ``ValueError``; this guard runs
    before any ``N_h / n_h`` division, so a zero ``n_h`` can never be divided
    by (plan §8).
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an int >= 1")
    return value


def _category_population(strata: Sequence[StratumMetricInput]) -> int:
    """Return ``N = sum(N_h)`` over ``strata``; ``0`` for an empty category.

    No division happens here, so ``N == 0`` is a safe, explicit zero. Callers
    guard on ``N == 0`` before evaluating ``N_h / N``.
    """
    return sum(stratum.discovered_population_count for stratum in strata)


def _stratum_weight(
    total_population: int,
    stratum: StratumMetricInput,
) -> float:
    """Return ``N_h / N`` for a nonzero ``total_population``.

    Raises ``ValueError`` when ``total_population`` is ``0``: the caller must
    have taken the zero-population branch first, so this is a programming
    breach, never a product value (plan §11).
    """
    if total_population == 0:
        raise ValueError("stratum weight N_h / N is undefined when N == 0")
    return stratum.discovered_population_count / total_population


def _age_value(
    observation: MetricObservation,
    scoring_cutoff_utc: datetime,
) -> float | None:
    """Chunk 7A's usable exact age for ``observation``, or ``None``.

    Recent-Supply usability uses the exact age alone (a valid date no later than
    the cutoff, no ``MIN_AGE_DAYS_FOR_RATE`` minimum); the recent-window length
    enters only through ``is_within_recent_window``.
    """
    return age_days_exact(
        observation.first_published_date_utc,
        scoring_cutoff_utc=scoring_cutoff_utc,
    ).value


def _observation_index(
    observation: MetricObservation,
    scoring_cutoff_utc: datetime,
    min_age_days_for_rate: int,
) -> float | None:
    """Chunk 7A's usable index with the estimator's explicit age minimum."""
    index = age_normalized_page_view_index(
        observation.product_page_views,
        observation.first_published_date_utc,
        scoring_cutoff_utc=scoring_cutoff_utc,
        state=observation.state,
        id_mapping_mismatch=observation.id_mapping_mismatch,
        min_age_days_for_rate=min_age_days_for_rate,
    )
    return index.value


def _index_is_usable(
    observation: MetricObservation,
    scoring_cutoff_utc: datetime,
    min_age_days_for_rate: int,
) -> bool:
    """Whether ``observation`` has a Chunk 7A-usable page-view index."""
    return (
        _observation_index(observation, scoring_cutoff_utc, min_age_days_for_rate)
        is not None
    )


def _quality_eligible_count(
    input: CategoryMetricInput,
    stratum: StratumMetricInput,
) -> int:
    """Count quality-eligible observations via Chunk 7A (never re-derived)."""
    return sum(
        1
        for observation in stratum.observations
        if _quality_observation_index(input, observation) is not None
    )


def _quality_observation_index(
    input: CategoryMetricInput,
    observation: MetricObservation,
) -> float | None:
    """The index of a quality-eligible observation, else ``None``.

    Delegates to Chunk 7A's :func:`quality_observation_eligibility` first; when
    eligible, the index itself comes from Chunk 7A's
    :func:`age_normalized_page_view_index` with explicit parameters. Both the age
    minimum (``input.min_age_days_for_rate``) and the rating-count minimum
    (``input.quality_min_rating_count``) are forwarded, so a
    ``CategoryMetricInput`` policy override reaches Chunk 7A (SRS §7.5).
    """
    eligibility = quality_observation_eligibility(
        product_detail_status=observation.product_detail_status,
        page_views_status=observation.page_views_status,
        id_mapping_mismatch=observation.id_mapping_mismatch,
        state=observation.state,
        rating_average=observation.rating_average,
        rating_count=observation.rating_count,
        page_view_semantics_status=input.page_view_semantics_status,
        product_page_views=observation.product_page_views,
        first_published_date_utc=observation.first_published_date_utc,
        scoring_cutoff_utc=input.scoring_cutoff_utc,
        min_age_days_for_rate=input.min_age_days_for_rate,
        quality_min_rating_count=input.quality_min_rating_count,
    )
    if not eligibility.eligible:
        return None
    return _observation_index(
        observation,
        input.scoring_cutoff_utc,
        input.min_age_days_for_rate,
    )


def _coverage_value(total_population: int, usable_weight: float) -> float:
    """Clamp a summed population weight to ``[0, 1]``.

    ``usable_weight`` is only ever built from ``N_h / N`` terms, so the clamp
    guards the pathological all-strata case against float accumulation drift; it
    never renormalizes to the sampled assets (plan §8).
    """
    if total_population == 0:
        return 0.0
    return min(1.0, max(0.0, usable_weight))


def _null_result(
    reason: str,
    *,
    usable_sample_count: int = 0,
    eligible_population_count: int = 0,
    eligibility_coverage: float | None = None,
) -> MetricResult:
    """A null ``MetricResult`` carrying its aggregate unavailable reason."""
    return MetricResult(
        value=None,
        usable_sample_count=usable_sample_count,
        eligible_population_count=eligible_population_count,
        eligibility_coverage=eligibility_coverage,
        unavailable_reason=reason,
    )


def _demand_coverage(input: CategoryMetricInput, total_population: int) -> float:
    """``sum(N_h / N)`` over strata with ``u_demand_h >= min`` (LREQ-MET-060)."""
    if total_population == 0:
        return 0.0
    usable_weight = 0.0
    for stratum in input.strata:
        usable_indices = _usable_index_count(input, stratum)
        if stratum_is_usable(
            usable_indices,
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            usable_weight += _stratum_weight(total_population, stratum)
    return _coverage_value(total_population, usable_weight)


def _usable_index_count(input: CategoryMetricInput, stratum: StratumMetricInput) -> int:
    """Count usable demand indices in ``stratum`` via Chunk 7A."""
    return sum(
        1
        for observation in stratum.observations
        if _index_is_usable(
            observation,
            input.scoring_cutoff_utc,
            input.min_age_days_for_rate,
        )
    )


def _usable_indices(
    input: CategoryMetricInput, stratum: StratumMetricInput
) -> list[float]:
    """Chunk 7A's usable demand indices for ``stratum`` (order preserved)."""
    indices: list[float] = []
    for observation in stratum.observations:
        index = _observation_index(
            observation,
            input.scoring_cutoff_utc,
            input.min_age_days_for_rate,
        )
        if index is not None:
            indices.append(index)
    return indices


def _usable_ages(
    input: CategoryMetricInput, stratum: StratumMetricInput
) -> list[float]:
    """Chunk 7A's usable exact ages for ``stratum`` (order preserved)."""
    ages: list[float] = []
    for observation in stratum.observations:
        age = _age_value(observation, input.scoring_cutoff_utc)
        if age is not None:
            ages.append(age)
    return ages


def _recent_coverage(input: CategoryMetricInput, total_population: int) -> float:
    """``sum(N_h / N)`` over strata with ``u_recent_h >= min`` (LREQ-MET-080)."""
    if total_population == 0:
        return 0.0
    usable_weight = 0.0
    for stratum in input.strata:
        usable_dated = len(_usable_ages(input, stratum))
        if stratum_is_usable(
            usable_dated,
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            usable_weight += _stratum_weight(total_population, stratum)
    return _coverage_value(total_population, usable_weight)


def _recent_share_value(input: CategoryMetricInput, total_population: int) -> float:
    """Renormalized population-weighted mean of usable per-stratum shares."""
    usable_weight = 0.0
    weighted_share = 0.0
    for stratum in input.strata:
        ages = _usable_ages(input, stratum)
        if not ages:
            # No usable date means no per-stratum share; a no-op for the
            # production minimum (>= 1), and a guard against a degenerate
            # policy minimum of 0 dividing by zero.
            continue
        if not stratum_is_usable(
            len(ages),
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            continue
        in_window = sum(
            1
            for age in ages
            if is_within_recent_window(age, recent_window_days=input.recent_window_days)
        )
        weight = _stratum_weight(total_population, stratum)
        usable_weight += weight
        weighted_share += weight * (in_window / len(ages))
    return weighted_share / usable_weight


def _quality_coverage(input: CategoryMetricInput, total_population: int) -> float:
    """``sum(N_h / N)`` over quality-usable strata (LREQ-MET-090)."""
    if total_population == 0:
        return 0.0
    usable_weight = 0.0
    for stratum in input.strata:
        if stratum_is_usable(
            _quality_eligible_count(input, stratum),
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            usable_weight += _stratum_weight(total_population, stratum)
    return _coverage_value(total_population, usable_weight)


# ---------------------------------------------------------------------------
# Public functions (§5.3)
# ---------------------------------------------------------------------------


def stratum_expansion_weight(
    discovered_population_count: int, sampled_population_count: int
) -> float:
    """``N_h / n_h``, the per-observation expansion weight (SRS §7.2, §7.4, §7.5).

    Each argument must be an ``int >= 1`` (a ``bool`` raises ``ValueError``,
    because ``isinstance(True, int)`` is ``True``). Pure. This is the weight used
    by ``DemandMedianRaw``, ``MedianAgeRaw``, and both sums of ``QualityRaw``; it
    is NOT the ``N_h / N`` stratum weight used by ``DemandPerAssetRaw`` and
    ``RecentShareRaw``.
    """
    _require_positive_int(
        discovered_population_count,
        name="discovered_population_count",
    )
    _require_positive_int(sampled_population_count, name="sampled_population_count")
    return discovered_population_count / sampled_population_count


def weighted_median(
    values_and_weights: Sequence[tuple[float, float]],
) -> float | None:
    """Exact-boundary stratum-expanded weighted median (LREQ-MET-050).

    Sort by value ascending, retaining equal values as separate observations in
    input order; let ``T`` be the total weight. Missing, invalid, or unusable
    values contribute no weight, so an entry with weight ``0.0`` contributes
    nothing and an empty (or all-zero-weight) sequence returns ``None`` (SRS
    §7.2: "It is null when the usable weighted sample is empty"). Otherwise walk
    the sorted order accumulating weight and return the first value whose
    cumulative weight is ``>= T / 2``. When that cumulative weight equals exactly
    ``T / 2`` and a next sorted value exists, return ``(value + next_value) / 2``;
    the SRS's "boundary value is the final sorted value" branch is defensive and
    unreachable for ``T > 0`` (the last cumulative weight is ``T > T / 2``) — see
    plan §12 Q-2. A non-finite value or weight, or a negative weight, raises
    ``ValueError`` (caller-contract breach, not a product value). Pure.
    """
    ordered: list[tuple[float, float, int]] = []
    for insertion_index, (value, weight) in enumerate(values_and_weights):
        if isinstance(value, bool) or isinstance(weight, bool):
            raise ValueError("weighted-median values and weights must be numeric")
        if not isinstance(value, (int, float)) or not isinstance(weight, (int, float)):
            raise ValueError("weighted-median values and weights must be numeric")
        if not math.isfinite(value):
            raise ValueError("weighted-median values must be finite")
        if not math.isfinite(weight):
            raise ValueError("weighted-median weights must be finite")
        if weight < 0:
            raise ValueError("weighted-median weights must be non-negative")
        ordered.append((float(value), float(weight), insertion_index))
    # ``values_and_weights`` is a Sequence, so ``enumerate`` order is the input
    # order; equal values keep that order for a stable, deterministic result.
    ordered.sort(key=lambda item: (item[0], item[2]))

    # Accumulate in a plain loop with the same ``+=`` semantics as the
    # cumulative walk below. ``sum`` may apply compensated (Neumaier) summation
    # on CPython 3.12+, which can disagree with the walk for non-binary-exact
    # weights and make the exact-half comparison inconsistent; a plain loop
    # keeps the total and the walk bit-identical for exact binary weights.
    total_weight = 0.0
    for _value, weight, _index in ordered:
        total_weight += weight
    if total_weight == 0.0:
        return None
    half_weight = total_weight / 2.0

    def value_at(index: int) -> float:
        return ordered[index][0]

    cumulative_weight = 0.0
    for position, (_value, weight, _index) in enumerate(ordered):
        cumulative_weight += weight
        if cumulative_weight > half_weight:
            return value_at(position)
        if cumulative_weight == half_weight:
            if position + 1 < len(ordered):
                return (value_at(position) + value_at(position + 1)) / 2.0
            return value_at(position)
    return None  # unreachable for total_weight > 0


def breadth_raw(breadth_input: BreadthMetricInput) -> BreadthResult:
    """Verified discovered canonical breadth (LREQ-MET-070).

    If ``verified_total_count is not None``, return
    ``BreadthResult(verified_total_count, VERIFIED_TOTAL_COUNT, COMPLETE)``.
    Otherwise return
    ``BreadthResult(distinct_canonical_discovered_count,
    DISTINCT_CANONICAL_DISCOVERED_COUNT, INCOMPLETE_ESTIMATE)``. A verified
    zero-result category therefore has ``breadth_raw == 0``. Never ``None``; a
    failed/truncated page is handled by ``Competition`` availability (Chunk 8,
    LREQ-SCR-020), not by a null raw (plan Q-4). Both counts must be
    ``int >= 0``; ``BreadthMetricInput`` enforces that at construction. Pure.
    """
    if breadth_input.verified_total_count is not None:
        return BreadthResult(
            breadth_raw=breadth_input.verified_total_count,
            breadth_source=BreadthSource.VERIFIED_TOTAL_COUNT,
            breadth_completeness_status=BreadthCompletenessStatus.COMPLETE,
        )
    return BreadthResult(
        breadth_raw=breadth_input.distinct_canonical_discovered_count,
        breadth_source=BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT,
        breadth_completeness_status=BreadthCompletenessStatus.INCOMPLETE_ESTIMATE,
    )


def demand_stratum_eligibility_coverage(input: CategoryMetricInput) -> float:
    """``sum(N_h / N)`` over strata with ``u_demand_h >= min``, clamped to ``[0, 1]``.

    Zero when ``N == 0`` (LREQ-MET-030/060). Distinct from ``sample_fraction``
    (``enriched_sample_count / discovered_population_count``, SRS §5.1); Chunk 7B
    never computes or returns ``sample_fraction``. Pure.
    """
    return _demand_coverage(input, _category_population(input.strata))


def demand_per_asset_raw(input: CategoryMetricInput) -> MetricResult:
    """Population-weighted demand mean (LREQ-MET-030; SRS §7.2).

    Usable strata are those with ``u_demand_h >= min_usable_samples_per_stratum``;
    ``stratum_view_mean_h`` is the mean of Chunk 7A's usable indices in stratum
    ``h``; ``stratum_weight_h = N_h / N``. Returns
    ``sum(w_h * mean_h) / sum(w_h)`` over usable strata. Null
    (``METRIC_REASON_ZERO_POPULATION``) when ``N == 0``, and never evaluates
    ``N_h / N`` then; null (``METRIC_REASON_NO_USABLE_STRATUM``) when ``N > 0``
    and no stratum is usable. An explicit valid index of ``0.0`` is a value and
    counts toward the stratum mean. Pure.
    """
    total_population = _category_population(input.strata)
    coverage = _demand_coverage(input, total_population)
    if total_population == 0:
        return _null_result(
            METRIC_REASON_ZERO_POPULATION,
            eligibility_coverage=0.0,
        )

    usable_weight = 0.0
    weighted_mean = 0.0
    usable_sample_count = 0
    eligible_population_count = 0
    for stratum in input.strata:
        indices = _usable_indices(input, stratum)
        if not indices:
            # A stratum with no usable index has no view mean; this is a no-op
            # for the production minimum (>= 1) and keeps a degenerate
            # policy minimum of 0 from dividing by zero.
            continue
        if not stratum_is_usable(
            len(indices),
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            continue
        weight = _stratum_weight(total_population, stratum)
        usable_weight += weight
        weighted_mean += weight * (sum(indices) / len(indices))
        usable_sample_count += len(indices)
        eligible_population_count += stratum.discovered_population_count

    if usable_weight == 0.0:
        return _null_result(
            METRIC_REASON_NO_USABLE_STRATUM,
            eligibility_coverage=coverage,
        )
    return MetricResult(
        value=weighted_mean / usable_weight,
        usable_sample_count=usable_sample_count,
        eligible_population_count=eligible_population_count,
        eligibility_coverage=coverage,
        unavailable_reason=None,
    )


def demand_median_raw(input: CategoryMetricInput) -> MetricResult:
    """Stratum-expanded weighted median of usable indices (LREQ-MET-050).

    Every usable observation (in any stratum) contributes with weight
    ``N_h / n_h``; the shared ``weighted_median`` boundary rule applies. Null when
    the usable weighted sample is empty (``METRIC_REASON_EMPTY_USABLE_SAMPLE``),
    or (``METRIC_REASON_ZERO_POPULATION``) when ``N == 0``. Unusable observations
    contribute no weight and never a zero. Pure.
    """
    total_population = _category_population(input.strata)
    coverage = _demand_coverage(input, total_population)
    if total_population == 0:
        return _null_result(
            METRIC_REASON_ZERO_POPULATION,
            eligibility_coverage=0.0,
        )

    values_and_weights: list[tuple[float, float]] = []
    usable_sample_count = 0
    eligible_population_count = 0
    for stratum in input.strata:
        indices = _usable_indices(input, stratum)
        if indices:
            eligible_population_count += stratum.discovered_population_count
        weight = stratum_expansion_weight(
            stratum.discovered_population_count,
            stratum.sampled_population_count,
        )
        for index in indices:
            values_and_weights.append((index, weight))
        usable_sample_count += len(indices)

    median = weighted_median(values_and_weights)
    if median is None:
        return _null_result(
            METRIC_REASON_EMPTY_USABLE_SAMPLE,
            eligibility_coverage=coverage,
        )
    return MetricResult(
        value=median,
        usable_sample_count=usable_sample_count,
        eligible_population_count=eligible_population_count,
        eligibility_coverage=coverage,
        unavailable_reason=None,
    )


def recent_supply_stratum_eligibility_coverage(
    input: CategoryMetricInput,
) -> float:
    """``sum(N_h / N)`` over strata with ``u_recent_h >= min`` (LREQ-MET-080).

    Zero when ``N == 0``; not renormalized. Distinct from ``sample_fraction``.
    A usable dated count counts a Chunk 7A-usable exact age regardless of the
    recent-window length, per the LREQ-MET-080 usability sentence (plan §8).
    Pure.
    """
    return _recent_coverage(input, _category_population(input.strata))


def recent_share_raw(input: CategoryMetricInput) -> MetricResult:
    """Population-weighted recent share (LREQ-MET-080; SRS §7.4).

    For each usable recent stratum,
    ``stratum_recent_share_h = count(0 <= age <= recent_window_days) / u_recent_h``
    using Chunk 7A's exact ages and inclusive ``is_within_recent_window``; the
    result is ``sum(w_h * share_h) / sum(w_h)`` with ``w_h = N_h / N``,
    renormalized over usable strata. An unusable date reduces ``u_recent_h`` and
    the coverage and is never a zero numerator entry. Null
    (``METRIC_REASON_ZERO_POPULATION``) when ``N == 0``; null
    (``METRIC_REASON_NO_USABLE_STRATUM``) when no stratum is usable. A measured
    share of ``0.0`` is a value. Pure.
    """
    total_population = _category_population(input.strata)
    coverage = _recent_coverage(input, total_population)
    if total_population == 0:
        return _null_result(
            METRIC_REASON_ZERO_POPULATION,
            eligibility_coverage=0.0,
        )

    usable_sample_count = 0
    eligible_population_count = 0
    for stratum in input.strata:
        usable_dated = len(_usable_ages(input, stratum))
        if usable_dated and stratum_is_usable(
            usable_dated,
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            usable_sample_count += usable_dated
            eligible_population_count += stratum.discovered_population_count

    if usable_sample_count == 0:
        return _null_result(
            METRIC_REASON_NO_USABLE_STRATUM,
            eligibility_coverage=coverage,
        )
    value = _recent_share_value(input, total_population)
    return MetricResult(
        value=value,
        usable_sample_count=usable_sample_count,
        eligible_population_count=eligible_population_count,
        eligibility_coverage=coverage,
        unavailable_reason=None,
    )


def median_age_raw(input: CategoryMetricInput) -> MetricResult:
    """Stratum-expanded weighted median of exact ages (LREQ-MET-080).

    Every usable dated observation contributes with weight ``N_h / n_h``; exact
    fractional ages come from Chunk 7A's ``age_days_exact`` and the shared
    ``weighted_median`` boundary rule applies. Null when the usable weighted
    sample is empty (``METRIC_REASON_EMPTY_USABLE_SAMPLE``), or when ``N == 0``
    (``METRIC_REASON_ZERO_POPULATION``). Pure.
    """
    total_population = _category_population(input.strata)
    coverage = _recent_coverage(input, total_population)
    if total_population == 0:
        return _null_result(
            METRIC_REASON_ZERO_POPULATION,
            eligibility_coverage=0.0,
        )

    values_and_weights: list[tuple[float, float]] = []
    usable_sample_count = 0
    eligible_population_count = 0
    for stratum in input.strata:
        ages = _usable_ages(input, stratum)
        if ages:
            eligible_population_count += stratum.discovered_population_count
        weight = stratum_expansion_weight(
            stratum.discovered_population_count,
            stratum.sampled_population_count,
        )
        for age in ages:
            values_and_weights.append((age, weight))
        usable_sample_count += len(ages)

    median = weighted_median(values_and_weights)
    if median is None:
        return _null_result(
            METRIC_REASON_EMPTY_USABLE_SAMPLE,
            eligibility_coverage=coverage,
        )
    return MetricResult(
        value=median,
        usable_sample_count=usable_sample_count,
        eligible_population_count=eligible_population_count,
        eligibility_coverage=coverage,
        unavailable_reason=None,
    )


def quality_stratum_eligibility_coverage(input: CategoryMetricInput) -> float:
    """``sum(N_h / N)`` over strata with ``>= min`` quality-eligible observations.

    Not a count fraction and not renormalized to the sampled assets (LREQ-MET-090;
    SRS §7.5). Zero when ``N == 0``. Pure.
    """
    return _quality_coverage(input, _category_population(input.strata))


def quality_raw(input: CategoryMetricInput) -> MetricResult:
    """Stratum-expanded visibility-weighted quality (LREQ-MET-090/100; SRS §7.5).

    A quality-usable stratum has at least ``min_usable_samples_per_stratum``
    quality-eligible observations (Chunk 7A's ``quality_observation_eligibility``
    with ``page_view_semantics_status``). For each, recompute the Chunk 7A index and
    use ``rating_average``:

    ``num_h = (N_h/n_h) * sum((rating_average_i / 5) * index_i)`` and
    ``den_h = (N_h/n_h) * sum(index_i)``, over quality-eligible observations in
    ``h``; ``QualityRaw = sum(num_h) / sum(den_h)``. Null with, in precedence
    order: ``METRIC_REASON_ZERO_POPULATION`` (``N == 0``),
    ``METRIC_REASON_ELIGIBLE_SET_TOO_SMALL`` (total quality-eligible observations
    below ``quality_min_eligible_assets``),
    ``METRIC_REASON_NO_USABLE_STRATUM`` (no quality-usable stratum),
    ``METRIC_REASON_INSUFFICIENT_COVERAGE``
    (``quality_stratum_eligibility_coverage < min_required_component_coverage``),
    ``METRIC_REASON_ZERO_DENOMINATOR`` (``sum(den_h) == 0.0``), or
    ``METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED`` (run-level status is
    ``CONTRADICTED``, which also makes every observation quality-ineligible
    through Chunk 7A). ``usable_sample_count`` and ``eligible_population_count``
    describe the quality-usable strata (the strata whose ``N_h / N`` terms build
    the coverage) and are returned even when ``.value`` is null; counts are never
    null (SRS §6.5 line 637). ``rating_count`` never weights the formula. The reason
    order above is a documented RECOMMENDATION (plan §12 C-1). Pure.
    """
    total_population = _category_population(input.strata)
    coverage = _quality_coverage(input, total_population)
    if total_population == 0:
        return _null_result(
            METRIC_REASON_ZERO_POPULATION,
            eligibility_coverage=0.0,
        )

    total_eligible = 0
    usable_sample_count = 0
    eligible_population_count = 0
    numerator = 0.0
    denominator = 0.0
    for stratum in input.strata:
        eligible_indices: list[tuple[float, object]] = []
        for observation in stratum.observations:
            index = _quality_observation_index(input, observation)
            if index is not None:
                eligible_indices.append((index, observation.rating_average))
        total_eligible += len(eligible_indices)
        if not eligible_indices:
            # No eligible observation means no stratum numerator/denominator; a
            # no-op for the production minimum (>= 1).
            continue
        if not stratum_is_usable(
            len(eligible_indices),
            min_usable_samples_per_stratum=input.min_usable_samples_per_stratum,
        ):
            continue
        weight = stratum_expansion_weight(
            stratum.discovered_population_count,
            stratum.sampled_population_count,
        )
        stratum_numerator = 0.0
        stratum_denominator = 0.0
        for index, rating_average in eligible_indices:
            rating = float(rating_average)  # Chunk 7A already validated it
            stratum_denominator += index
            stratum_numerator += (rating / 5.0) * index
        numerator += weight * stratum_numerator
        denominator += weight * stratum_denominator
        usable_sample_count += len(eligible_indices)
        eligible_population_count += stratum.discovered_population_count

    if total_eligible < input.quality_min_eligible_assets:
        # The count fields are independent of ``.value`` (frozen chunk-7B
        # interface §4.2; SRS §6.5 line 637 makes counts the non-nullable
        # exception): report the quality-eligible observations over
        # quality-usable strata accumulated above, not a forced ``0``. At the
        # default policy the guard can only fire when no stratum reached
        # ``min_usable_samples_per_stratum``, so these are the same true zeros.
        return _null_result(
            METRIC_REASON_ELIGIBLE_SET_TOO_SMALL,
            usable_sample_count=usable_sample_count,
            eligible_population_count=eligible_population_count,
            eligibility_coverage=coverage,
        )
    if usable_sample_count == 0:
        return _null_result(
            METRIC_REASON_NO_USABLE_STRATUM,
            eligibility_coverage=coverage,
        )
    if coverage < input.min_required_component_coverage:
        return _null_result(
            METRIC_REASON_INSUFFICIENT_COVERAGE,
            usable_sample_count=usable_sample_count,
            eligible_population_count=eligible_population_count,
            eligibility_coverage=coverage,
        )
    if denominator == 0.0:
        return _null_result(
            METRIC_REASON_ZERO_DENOMINATOR,
            usable_sample_count=usable_sample_count,
            eligible_population_count=eligible_population_count,
            eligibility_coverage=coverage,
        )
    if input.page_view_semantics_status == PageViewSemanticsStatus.CONTRADICTED:
        return _null_result(
            METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED,
            eligibility_coverage=coverage,
        )
    return MetricResult(
        value=numerator / denominator,
        usable_sample_count=usable_sample_count,
        eligible_population_count=eligible_population_count,
        eligibility_coverage=coverage,
        unavailable_reason=None,
    )


def compute_raw_metric_bundle(input: CategoryMetricInput) -> RawMetricBundle:
    """The six raw values as the frozen ``RawMetricBundle`` (SRS §8.1 field set).

    Breadth is not derivable from ``CategoryMetricInput``; ``breadth_raw`` is left
    ``None`` here and filled by ``compute_category_raw_metrics``. Every other field
    is the corresponding estimator's ``.value``. Pure.
    """
    return RawMetricBundle(
        demand_per_asset_raw=demand_per_asset_raw(input).value,
        demand_median_raw=demand_median_raw(input).value,
        breadth_raw=None,
        recent_share_raw=recent_share_raw(input).value,
        median_age_raw=median_age_raw(input).value,
        quality_raw=quality_raw(input).value,
    )


def compute_category_raw_metrics(
    input: CategoryMetricInput, breadth_input: BreadthMetricInput
) -> CategoryRawMetrics:
    """All six raw values, the three coverages, the three usable counts, and the
    breadth provenance in one deterministic value (SRS §6.5 field set). Pure.
    """
    breadth = breadth_raw(breadth_input)
    demand_mean = demand_per_asset_raw(input)
    demand_median = demand_median_raw(input)
    recent_share = recent_share_raw(input)
    recent_age = median_age_raw(input)
    quality = quality_raw(input)
    return CategoryRawMetrics(
        category=input.category,
        raw=RawMetricBundle(
            demand_per_asset_raw=demand_mean.value,
            demand_median_raw=demand_median.value,
            breadth_raw=float(breadth.breadth_raw),
            recent_share_raw=recent_share.value,
            median_age_raw=recent_age.value,
            quality_raw=quality.value,
        ),
        demand_stratum_eligibility_coverage=demand_stratum_eligibility_coverage(input),
        recent_supply_stratum_eligibility_coverage=(
            recent_supply_stratum_eligibility_coverage(input)
        ),
        quality_stratum_eligibility_coverage=quality_stratum_eligibility_coverage(
            input
        ),
        # SRS §6.5/§7.4: the demand/recent counts are over the strata that meet
        # the applicable usable minimum, which is precisely what the
        # ``demand_per_asset_raw`` / ``recent_share_raw`` aggregate counts; the
        # medians count every eligible observation in all strata and are not the
        # source of these fields.
        usable_demand_sample_count=demand_mean.usable_sample_count,
        usable_recent_supply_sample_count=recent_share.usable_sample_count,
        usable_quality_sample_count=quality.usable_sample_count,
        breadth_source=breadth.breadth_source,
        breadth_completeness_status=breadth.breadth_completeness_status,
    )
