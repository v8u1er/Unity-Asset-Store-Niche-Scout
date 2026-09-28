"""Golden date, eligibility, and page-view vectors for the Chunk 7A tests.

Data only: explicit constants and small keyword-argument builders. There are no
assertions and no implementation logic here; the expectations live in
``tests/test_validation.py`` so this module stays inert fixture data.

Every expected float is hand-derived from the SRS formulas:

* ``age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds()
  / 86400`` — SRS-lean.md §7.1 (LREQ-MET-020), Appendix A.
* ``age_normalized_page_view_index = product_page_views * 7 / age_days_exact``
  — SRS-lean.md §7.2 (LREQ-MET-040).
* Recent-window membership is ``0 <= age_days_exact <= RECENT_WINDOW_DAYS``
  — SRS-lean.md §7.4 (LREQ-MET-080).
* Quality eligibility is the SRS-lean.md §7.5 conjunction (LREQ-MET-090).

``CUTOFF_UTC`` is an explicit, timezone-aware UTC instant and every date below is
a constant, so nothing here or in the tests reads the system clock
(LREQ-ARCH-020). No network, no credentials, no real artifacts.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from niche_scout.models import (
    MIN_AGE_DAYS_FOR_RATE,
    QUALITY_MIN_RATING_COUNT,
    RECENT_WINDOW_DAYS,
    OperationStatus,
    PageViewSemanticsStatus,
)

__all__ = [
    "AGE_29D_1H",
    "AGE_30D",
    "AGE_AT_CUTOFF",
    "AGE_FUTURE",
    "AGE_HALF_DAY",
    "AGE_ONE_DAY",
    "CUTOFF_NAIVE",
    "CUTOFF_NON_UTC",
    "CUTOFF_UTC",
    "DATE_29D_1H",
    "DATE_30D",
    "DATE_AT_CUTOFF",
    "DATE_FUTURE",
    "DATE_HALF_DAY",
    "DATE_NAIVE",
    "DATE_OFFSET_30D",
    "DATE_ONE_DAY",
    "INDEX_VECTORS",
    "MIN_AGE_DAYS_FOR_RATE",
    "OPERATION_ERROR",
    "OPERATION_ERROR_VALUE",
    "OPERATION_SUCCESS",
    "OPERATION_SUCCESS_VALUE",
    "PAGE_VIEW_INVALID_VECTORS",
    "QUALITY_MIN_RATING_COUNT",
    "RATING_AVERAGE",
    "RATING_AVERAGE_BOUNDARY_VALID",
    "RATING_AVERAGE_INVALID_VECTORS",
    "RATING_COUNT",
    "RATING_COUNT_INVALID_VECTORS",
    "RECENT_WINDOW_DAYS",
    "RECENT_WINDOW_NON_FINITE_VECTORS",
    "RECENT_WINDOW_VECTORS",
    "SEMANTICS_CONTRADICTED",
    "SEMANTICS_UNVALIDATED",
    "SEMANTICS_VALIDATED_CUMULATIVE",
    "STATE_COMING_SOON",
    "STATE_DRAFT",
    "STATE_EXCLUDED_VECTORS",
    "STATE_MIXED_CASE_PUBLISHED",
    "STATE_PUBLISHED",
    "STATE_WRONG_TYPE_INT",
    "STRATUM_USABLE_VECTORS",
    "WRONG_TYPE_TIMESTAMP_VECTORS",
    "index_kwargs",
    "quality_kwargs",
]

# ---------------------------------------------------------------------------
# Cutoff and date vectors (SRS-lean.md §7.1, LREQ-MET-020)
# ---------------------------------------------------------------------------

#: The explicit scoring cutoff every age below is measured against.
CUTOFF_UTC: datetime = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)

#: A naive cutoff is a caller/policy breach (plan §5.0): it must raise ValueError.
CUTOFF_NAIVE: datetime = datetime(2025, 1, 31, 0, 0)

#: An aware non-UTC cutoff is the same instant but not a UTC tzinfo: also a
#: caller/policy breach. ``2025-01-31T01:00+01:00`` is ``2025-01-31T00:00Z``.
CUTOFF_NON_UTC: datetime = datetime(
    2025, 1, 31, 1, 0, tzinfo=timezone(timedelta(hours=1))
)

#: Equal to the cutoff: age exactly 0.0, a valid zero, never a future date.
DATE_AT_CUTOFF: datetime = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)

#: 30 days before the cutoff: age exactly 30.0 (the inclusive rate threshold).
DATE_30D: datetime = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)

#: 29 days 23 hours before the cutoff: age 29.9583333... — just below the default.
DATE_29D_1H: datetime = datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc)

#: One day after the cutoff: age -1.0, a future date.
DATE_FUTURE: datetime = datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)

#: Aware non-UTC twin of DATE_30D: ``2024-12-31T19:00-05:00`` is ``2025-01-01T00:00Z``.
DATE_OFFSET_30D: datetime = datetime(
    2024, 12, 31, 19, 0, tzinfo=timezone(timedelta(hours=-5))
)

#: A naive datetime (no tzinfo): an unusable product-level timestamp.
DATE_NAIVE: datetime = datetime(2025, 1, 1, 0, 0)

#: Half a day before the cutoff: age exactly 0.5.
DATE_HALF_DAY: datetime = datetime(2025, 1, 30, 12, 0, tzinfo=timezone.utc)

#: Exactly one day before the cutoff: age exactly 1.0 (the smallest valid rate
#: threshold, used to show that no zero-age division can occur).
DATE_ONE_DAY: datetime = datetime(2025, 1, 30, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Hand-derived ages (SRS-lean.md §7.1: seconds / 86400, no floor)
# ---------------------------------------------------------------------------

#: (cutoff - DATE_AT_CUTOFF) / 86400 = 0 s / 86400 = 0.0 (explicit valid zero).
AGE_AT_CUTOFF: float = 0.0

#: (cutoff - DATE_30D) / 86400 = 2_592_000 s / 86400 = 30.0.
AGE_30D: float = 30.0

#: (cutoff - DATE_29D_1H) / 86400 = 2_588_400 s / 86400 = 719/24 = 29.958333333333332.
AGE_29D_1H: float = 29.958333333333332

#: (cutoff - DATE_FUTURE) / 86400 = -86_400 s / 86400 = -1.0 (future).
AGE_FUTURE: float = -1.0

#: (cutoff - DATE_HALF_DAY) / 86400 = 43_200 s / 86400 = 0.5.
AGE_HALF_DAY: float = 0.5

#: (cutoff - DATE_ONE_DAY) / 86400 = 86_400 s / 86400 = 1.0.
AGE_ONE_DAY: float = 1.0

# ---------------------------------------------------------------------------
# Page-view index vectors (SRS-lean.md §7.2: views * 7 / age_days_exact)
# ---------------------------------------------------------------------------

#: ``(product_page_views, age_days_exact, expected index)`` hand-derived as
#: ``views * 7 / age``:
#:   0  * 7 / 30 = 0.0                  (explicit valid zero)
#:   10 * 7 / 30 = 70/30  = 2.3333333333333335
#:   7  * 7 / 30 = 49/30  = 1.6333333333333333
#:   5  * 7 / 30 = 35/30  = 1.1666666666666667
#:   1.0 * 7 / 30 = 7/30  = 0.23333333333333334
INDEX_VECTORS: tuple[tuple[float, float, float], ...] = (
    (0, AGE_30D, 0.0),
    (10, AGE_30D, 2.3333333333333335),
    (7, AGE_30D, 1.6333333333333333),
    (5, AGE_30D, 1.1666666666666667),
    (1.0, AGE_30D, 0.23333333333333334),
)

#: Page-view values that must be classified as unavailable, never raised and
#: never converted to ``0`` (LREQ-MET-010; SRS-lean.md §7.2).
PAGE_VIEW_INVALID_VECTORS: tuple[tuple[str, object], ...] = (
    ("negative", -1),
    ("bool", True),
    ("nan", float("nan")),
    ("infinity", float("inf")),
    ("negative_string", "-1"),
    ("list", [-1]),
)

#: Timestamp values of the wrong product-level type: a ``str``, a ``date`` (which
#: is not a ``datetime``), an ``int``, and a ``list`` (plan §9.2; LREQ-MET-010).
WRONG_TYPE_TIMESTAMP_VECTORS: tuple[tuple[str, object], ...] = (
    ("string", "2025-01-01"),
    ("date_object", date(2025, 1, 1)),
    ("int", 20250101),
    ("list", []),
)

# ---------------------------------------------------------------------------
# Quality vectors (SRS-lean.md §7.5, LREQ-MET-090)
# ---------------------------------------------------------------------------

#: A rating average strictly inside ``[0, 5]`` used by the all-conditions-pass
#: builder below.
RATING_AVERAGE: float = 2.5

#: The inclusive rating-average boundaries: 0.0 and 5.0 are both valid.
RATING_AVERAGE_BOUNDARY_VALID: tuple[float, ...] = (0.0, 5.0)

#: A rating count exactly at the ``QUALITY_MIN_RATING_COUNT`` (5) inclusive minimum.
RATING_COUNT: int = QUALITY_MIN_RATING_COUNT

#: Rating averages that must be classified unavailable (LREQ-MET-090).
RATING_AVERAGE_INVALID_VECTORS: tuple[tuple[str, object], ...] = (
    ("wrong_type_bool", True),
    ("wrong_type_string", "2.5"),
    ("nan", float("nan")),
    ("below_zero", -0.1),
    ("above_five", 5.1),
)

#: Rating counts that must be classified unavailable (LREQ-MET-090).
RATING_COUNT_INVALID_VECTORS: tuple[tuple[str, object], ...] = (
    ("wrong_type_bool", True),
    ("wrong_type_float", 4.5),
    ("negative", -1),
    ("below_minimum", 4),
)

#: Operation-status fixtures. A persisted ``str`` equal to the enum value is
#: accepted by the quality gate (plan §5.3 step 1).
OPERATION_SUCCESS: OperationStatus = OperationStatus.SUCCESS
OPERATION_ERROR: OperationStatus = OperationStatus.ERROR
OPERATION_SUCCESS_VALUE: str = "success"
OPERATION_ERROR_VALUE: str = "error"

#: Page-view semantics fixtures (Chunk 5's vocabulary; 7A consumes them).
SEMANTICS_UNVALIDATED: PageViewSemanticsStatus = PageViewSemanticsStatus.UNVALIDATED
SEMANTICS_VALIDATED_CUMULATIVE: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.VALIDATED_CUMULATIVE
)
SEMANTICS_CONTRADICTED: PageViewSemanticsStatus = PageViewSemanticsStatus.CONTRADICTED

# ---------------------------------------------------------------------------
# Recent-window and usable-stratum vectors (SRS-lean.md §7.4 / §7.2)
# ---------------------------------------------------------------------------

#: ``(age_days_exact, expected membership)``. The window is inclusive at both
#: ends (SRS-lean.md §7.4): 0.0 and 365.0 are inside; 365.0000001 and -0.5 are not.
RECENT_WINDOW_VECTORS: tuple[tuple[float, bool], ...] = (
    (0.0, True),
    (1.0, True),
    (365.0, True),
    (365.0000001, False),
    (-0.5, False),
)

#: Non-finite ages contribute no count and are never inside the window.
RECENT_WINDOW_NON_FINITE_VECTORS: tuple[float, ...] = (
    float("inf"),
    float("-inf"),
    float("nan"),
)

#: ``(usable_observation_count, expected usability)`` at the default minimum 1;
#: the boundary is inclusive (SRS-lean.md §7.2, LREQ-MET-030): ``u_h == 0`` is
#: unusable, and every ``u_h >= 1`` is usable.
STRATUM_USABLE_VECTORS: tuple[tuple[int, bool], ...] = (
    (0, False),
    (1, True),
    (2, True),
    (3, True),
    (4, True),
    (5, True),
    (6, True),
)

# ---------------------------------------------------------------------------
# State fixtures (Chunk 1's annotation vocabulary; LREQ-GQL-060)
# ---------------------------------------------------------------------------

STATE_PUBLISHED: str = "published"
STATE_DRAFT: str = "draft"
STATE_COMING_SOON: str = "coming-soon"

#: A differently cased published state. Chunk 1's frozen annotation compares the
#: state vocabulary case-insensitively (``chunk-01.md`` §5;
#: ``tests/test_identity.py::test_published_state_annotated_eligible``), so this
#: vector is asserted against ``annotate_state_eligibility`` rather than a
#: re-derived rule (see the test that consumes it).
STATE_MIXED_CASE_PUBLISHED: str = "Published"

#: A present non-published state is state-excluded, not state-unknown.
STATE_EXCLUDED_VECTORS: tuple[str, ...] = (STATE_DRAFT, STATE_COMING_SOON)

#: A non-string state is state-unknown via Chunk 1's annotation (plan §5.3).
STATE_WRONG_TYPE_INT: int = 7

# ---------------------------------------------------------------------------
# Builders — keyword-argument dictionaries for the 7A primitives
# ---------------------------------------------------------------------------


def index_kwargs(**overrides: object) -> dict[str, object]:
    """Keyword arguments for ``age_normalized_page_view_index``.

    The defaults satisfy every gate: a published state, a matched identity, the
    explicit ``CUTOFF_UTC``, and the SRS default ``MIN_AGE_DAYS_FOR_RATE``.
    """
    kwargs: dict[str, object] = {
        "scoring_cutoff_utc": CUTOFF_UTC,
        "state": STATE_PUBLISHED,
        "id_mapping_mismatch": False,
        "min_age_days_for_rate": MIN_AGE_DAYS_FOR_RATE,
    }
    kwargs.update(overrides)
    return kwargs


def quality_kwargs(**overrides: object) -> dict[str, object]:
    """Keyword arguments for ``quality_observation_eligibility``.

    The defaults satisfy every SRS-lean.md §7.5 condition: both operations
    succeeded, identity matched, ``state = "published"``, a finite rating average
    in ``[0, 5]``, a rating count at ``QUALITY_MIN_RATING_COUNT``, a usable
    page-view index, and non-contradicted page-view semantics.
    """
    kwargs: dict[str, object] = {
        "product_detail_status": OPERATION_SUCCESS,
        "page_views_status": OPERATION_SUCCESS,
        "id_mapping_mismatch": False,
        "state": STATE_PUBLISHED,
        "rating_average": RATING_AVERAGE,
        "rating_count": RATING_COUNT,
        "page_view_semantics_status": SEMANTICS_UNVALIDATED,
        "product_page_views": 10,
        "first_published_date_utc": DATE_30D,
        "scoring_cutoff_utc": CUTOFF_UTC,
    }
    kwargs.update(overrides)
    return kwargs
