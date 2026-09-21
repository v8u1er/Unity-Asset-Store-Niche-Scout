"""Pure normalization, component, and composite scoring contracts.

This module intentionally contains no I/O, clock access, or orchestration.
Chunk 0 freezes the typed input/output contracts (:class:`ScoringInput`,
:class:`ScoreResult`, :class:`SensitivityResult`); Chunk 8 adds the pure
leave-one-out reference, the six field-specific midrank normalizations, the four
components ``D``/``C``/``R``/``Q``, and the available-component composite score.

Every unavailable value stays ``None`` and is never converted to a fabricated
zero (SRS-lean §1.2). Computations use ``float64`` and an explicit timezone-aware
UTC cutoff is always supplied by the caller; the module never reads the clock.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .metrics import CategoryRawMetrics, RawMetricBundle
from .models import (
    DEMAND_SUBWEIGHT_MEDIAN,
    DEMAND_SUBWEIGHT_PER_ASSET,
    MIN_REQUIRED_COMPONENT_COVERAGE,
    RECENT_SUBWEIGHT_AGE,
    RECENT_SUBWEIGHT_SHARE,
    W_C,
    W_D,
    W_Q,
    W_R,
    BreadthCompletenessStatus,
    BreadthSource,
    EvidenceGrade,
    PageViewSemanticsStatus,
    RankabilityStatus,
    ScoreState,
)

#: Fixed Lean v1 component key order (SRS-lean §8.3). The spelling matches
#: ``models.SENSITIVITY_POLICIES``; the tuple fixes weight summation order so the
#: composite is deterministic and independent of mapping iteration order.
COMPONENT_WEIGHT_KEYS: tuple[str, ...] = ("D", "C", "R", "Q")


@dataclass(frozen=True, slots=True)
class ScoringInput:
    scoring_cutoff_utc: datetime
    demand: float | None = None
    competition: float | None = None
    recent_supply: float | None = None
    quality: float | None = None

    def __post_init__(self) -> None:
        if (
            self.scoring_cutoff_utc.tzinfo is None
            or self.scoring_cutoff_utc.utcoffset()
            != timezone.utc.utcoffset(self.scoring_cutoff_utc)
        ):
            raise ValueError("scoring_cutoff_utc must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class ScoreResult:
    market_opportunity_score: float | None
    score_state: ScoreState
    component_d: float | None = None
    component_c: float | None = None
    component_r: float | None = None
    component_q: float | None = None
    available_component_count: int = 0
    rankability_status: RankabilityStatus = RankabilityStatus.NOT_RANKABLE
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    top_3_stability: float | None = None
    top_5_stability: float | None = None
    maximum_score_delta: float | None = None
    maximum_rank_displacement: int | None = None
    warning: bool = False


# ---------------------------------------------------------------------------
# Chunk 8 — typed structures for LOO reference, normalization, components
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FieldUsableCounts:
    """Per-field count of non-null peer values in a leave-one-out reference.

    Each count is the number of peers contributing a usable (non-``None``) value
    for that field, i.e. the ``m`` used by :func:`midrank`. A count of ``0``
    means the field has no usable reference value; it is a count, never a metric
    value, so ``0`` is a legitimate explicit value here (SRS-lean §8.1,
    LREQ-NRM-020).
    """

    demand_per_asset_raw: int
    demand_median_raw: int
    breadth_raw: int
    recent_share_raw: int
    median_age_raw: int
    quality_raw: int


@dataclass(frozen=True, slots=True)
class LeaveOneOutReference:
    """The reference set for one target: every other category in the run.

    ``reference_size`` is ``category_count - 1`` regardless of how many peers
    carry a usable value for a given field; the field tuples below hold only the
    non-``None`` peer values, in the input order of ``all_metrics``. A field tuple
    may therefore be shorter than ``reference_size`` (SRS-lean §8.1,
    LREQ-NRM-010/-020).
    """

    target_category: str
    reference_size: int
    demand_per_asset_raw: tuple[float, ...]
    demand_median_raw: tuple[float, ...]
    breadth_raw: tuple[float, ...]
    recent_share_raw: tuple[float, ...]
    median_age_raw: tuple[float, ...]
    quality_raw: tuple[float, ...]

    @property
    def field_usable_counts(self) -> FieldUsableCounts:
        """Return the per-field non-null peer counts (LREQ-NRM-020).

        Computed from the stored tuples, so it is always consistent with the
        values :func:`midrank` consumes.
        """
        return FieldUsableCounts(
            demand_per_asset_raw=len(self.demand_per_asset_raw),
            demand_median_raw=len(self.demand_median_raw),
            breadth_raw=len(self.breadth_raw),
            recent_share_raw=len(self.recent_share_raw),
            median_age_raw=len(self.median_age_raw),
            quality_raw=len(self.quality_raw),
        )


@dataclass(frozen=True, slots=True)
class NormalizedValues:
    """The six field-specific midranks of one target against its LOO reference.

    ``None`` means the normalized value is unavailable (a null raw value, or an
    empty usable reference); it is never ``0.0``. A non-null value is the
    descriptive midrank in ``[0, 1]`` from :func:`midrank` (SRS-lean §8.1,
    LREQ-NRM-040).
    """

    demand_per_asset_raw: float | None
    demand_median_raw: float | None
    breadth_raw: float | None
    recent_share_raw: float | None
    median_age_raw: float | None
    quality_raw: float | None


@dataclass(frozen=True, slots=True)
class ComponentValues:
    """The four composite components; ``None`` means unavailable.

    ``demand`` is ``D``, ``competition`` is ``C``, ``recent_supply`` is ``R``,
    and ``quality`` is ``Q`` (SRS-lean §8.2). Values are clamped to ``[0, 1]``
    when available. An unavailable component is excluded from the composite
    weight, never treated as a zero.
    """

    demand: float | None
    competition: float | None
    recent_supply: float | None
    quality: float | None

    @property
    def available_component_count(self) -> int:
        """Return the number of non-``None`` components, in ``0..4``."""
        return sum(
            1
            for component in (
                self.demand,
                self.competition,
                self.recent_supply,
                self.quality,
            )
            if component is not None
        )


@dataclass(frozen=True, slots=True)
class CompositeResult:
    """The available-component composite score and its accounting.

    ``market_opportunity_score`` is ``None`` exactly when fewer than two
    components are available (``score_state`` is then ``unavailable``). It is a
    within-run heuristic, never a sales, revenue, download, or demand prediction.
    ``available_weight`` is ``W_A`` from SRS-lean §8.3.
    """

    market_opportunity_score: float | None
    score_state: ScoreState
    available_component_count: int
    available_weight: float


# ---------------------------------------------------------------------------
# Internal helpers (pure; no I/O, no clock)
# ---------------------------------------------------------------------------


def _finite_float(value: object, *, name: str) -> float:
    """Return ``value`` as a finite ``float``; raise ``ValueError`` otherwise.

    A non-numeric, ``bool``, or non-finite value is a caller/policy breach,
    mirroring ``metrics.weighted_median`` (plan §5 D4). It never fabricates a
    product value.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _require_threshold(value: object) -> float:
    """Validate ``min_required_component_coverage`` to a finite ``float`` in [0, 1].

    Mirrors ``metrics.CategoryMetricInput``'s policy guard (metrics.py:819-823);
    a non-finite or out-of-range threshold is a caller/policy breach.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("min_required_component_coverage must be a float")
    threshold = float(value)
    if not math.isfinite(threshold) or threshold < 0 or threshold > 1:
        raise ValueError("min_required_component_coverage must be in [0, 1]")
    return threshold


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp ``value`` to ``[low, high]`` (both ends inclusive)."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def _shrink(value0: float, coverage: float) -> float:
    """Return ``clamp(0.5 + coverage * (value0 - 0.5), 0, 1)`` (SRS-lean §8.2)."""
    return _clamp(0.5 + coverage * (value0 - 0.5))


# ---------------------------------------------------------------------------
# Chunk 8 — public functions
# ---------------------------------------------------------------------------


def midrank(target: float | None, reference_values: Sequence[float]) -> float | None:
    """Return the midrank ``P_ref(x) = (L + 0.5 * E) / m`` (LREQ-NRM-030).

    ``L = count(r_k < target)`` and ``E = count(r_k == target)`` use exact float
    equality; duplicate reference values stay repeated and count toward ``m``. A
    ``None`` target or an empty ``reference_values`` returns ``None`` (SRS-lean
    §8.1: "If ``m = 0`` or ``x`` is null, the normalized value is null"), never a
    fabricated ``0.0``. A non-finite ``target`` or any non-finite reference
    element raises ``ValueError`` (caller breach, plan §5 D4). The result is a
    descriptive relative position, not an inferential percentile.
    """
    if target is None:
        return None
    target_value = _finite_float(target, name="midrank target")
    if len(reference_values) == 0:
        return None
    below = 0
    equal = 0
    for index, reference_value in enumerate(reference_values):
        value = _finite_float(reference_value, name=f"midrank reference[{index}]")
        if value < target_value:
            below += 1
        elif value == target_value:
            equal += 1
    return (below + 0.5 * equal) / len(reference_values)


def leave_one_out_reference(
    all_metrics: Sequence[CategoryRawMetrics],
    target_category: str,
) -> LeaveOneOutReference:
    """Build the leave-one-out reference for ``target_category`` (SRS-lean §8.1).

    ``reference_size = len(all_metrics) - 1``. The target's own entry is excluded
    from every field tuple; each tuple holds its peers' non-``None`` values in
    ``all_metrics`` order, so referencing is stable under input order. Empty run,
    a ``target_category`` that is not a non-empty ``str``, an absent target, or two
    entries sharing a ``category`` raise ``ValueError`` (caller breaches, plan §5
    D4). A one-category run yields ``reference_size == 0`` with empty tuples — a
    valid empty reference, not an error.
    """
    if not isinstance(target_category, str) or target_category == "":
        raise ValueError("target_category must be a non-empty str")
    if len(all_metrics) == 0:
        raise ValueError("all_metrics must not be empty")
    seen: list[str] = []
    for entry in all_metrics:
        if entry.category in seen:
            raise ValueError(f"duplicate category in all_metrics: {entry.category}")
        seen.append(entry.category)
    if target_category not in seen:
        raise ValueError(
            f"target_category not present in all_metrics: {target_category}"
        )

    peers = [entry for entry in all_metrics if entry.category != target_category]

    def usable(field: str) -> tuple[float, ...]:
        values: list[float] = []
        for peer in peers:
            value = getattr(peer.raw, field)
            if value is not None:
                values.append(value)
        return tuple(values)

    return LeaveOneOutReference(
        target_category=target_category,
        reference_size=len(all_metrics) - 1,
        demand_per_asset_raw=usable("demand_per_asset_raw"),
        demand_median_raw=usable("demand_median_raw"),
        breadth_raw=usable("breadth_raw"),
        recent_share_raw=usable("recent_share_raw"),
        median_age_raw=usable("median_age_raw"),
        quality_raw=usable("quality_raw"),
    )


def normalize_raw_metrics(
    raw: RawMetricBundle,
    reference: LeaveOneOutReference,
) -> NormalizedValues:
    """Normalize the six raws independently against ``reference`` (LREQ-NRM-040).

    Applies :func:`midrank` field by field (no log transform: strictly monotone
    transforms do not change midrank ordering). A ``None`` raw value or an empty
    field reference yields ``None`` for that field only; other fields are
    unaffected. The returned ``None`` values mean unavailable, never ``0.0``
    (SRS-lean §8.1).
    """
    return NormalizedValues(
        demand_per_asset_raw=midrank(
            raw.demand_per_asset_raw, reference.demand_per_asset_raw
        ),
        demand_median_raw=midrank(raw.demand_median_raw, reference.demand_median_raw),
        breadth_raw=midrank(raw.breadth_raw, reference.breadth_raw),
        recent_share_raw=midrank(raw.recent_share_raw, reference.recent_share_raw),
        median_age_raw=midrank(raw.median_age_raw, reference.median_age_raw),
        quality_raw=midrank(raw.quality_raw, reference.quality_raw),
    )


def demand_component(
    normalized: NormalizedValues,
    *,
    demand_stratum_eligibility_coverage: float,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> float | None:
    """Return demand ``D`` or ``None`` when unavailable (LREQ-SCR-010).

    A coverage strictly below ``min_required_component_coverage`` makes ``D``
    unavailable **before** any shrinkage and excludes its weight from the
    composite (SRS-lean §7.5 / §9.1); coverage exactly equal to the threshold is
    available. Otherwise ``D0 = 0.60 * a + 0.40 * b`` when both midranks are
    available, the single available midrank when exactly one is, and ``None``
    when both are ``None``; then ``D = clamp(0.5 + coverage * (D0 - 0.5), 0, 1)``.
    A non-finite or out-of-range ``min_required_component_coverage`` raises
    ``ValueError`` (caller/policy breach).
    """
    threshold = _require_threshold(min_required_component_coverage)
    if demand_stratum_eligibility_coverage < threshold:
        return None
    per_asset = normalized.demand_per_asset_raw
    median = normalized.demand_median_raw
    if per_asset is not None and median is not None:
        demand0: float = (
            DEMAND_SUBWEIGHT_PER_ASSET * per_asset + DEMAND_SUBWEIGHT_MEDIAN * median
        )
    elif per_asset is not None:
        demand0 = per_asset
    elif median is not None:
        demand0 = median
    else:
        return None
    return _shrink(demand0, demand_stratum_eligibility_coverage)


def competition_component(
    normalized: NormalizedValues,
    *,
    breadth_source: BreadthSource,
    breadth_completeness_status: BreadthCompletenessStatus,
) -> float | None:
    """Return competition ``C`` or ``None`` when unavailable (LREQ-SCR-020).

    ``C`` is available only with ``breadth_source is
    BreadthSource.VERIFIED_TOTAL_COUNT`` **and** ``breadth_completeness_status is
    BreadthCompletenessStatus.COMPLETE`` **and** a non-``None``
    ``P_ref(BreadthRaw)``; otherwise it returns ``None``. When available,
    ``C = clamp(1 - P_ref(BreadthRaw), 0, 1)`` with no coverage shrinkage. ``C``
    is not sample-derived and takes no stratum eligibility coverage, so it is
    never gated by ``MIN_REQUIRED_COMPONENT_COVERAGE`` (SRS-lean §8.2). An
    explicit zero breadth midrank is a value and yields ``C = 1.0``.
    """
    if (
        breadth_source is not BreadthSource.VERIFIED_TOTAL_COUNT
        or breadth_completeness_status is not BreadthCompletenessStatus.COMPLETE
    ):
        return None
    breadth = normalized.breadth_raw
    if breadth is None:
        return None
    return _clamp(1.0 - breadth)


def recent_supply_component(
    normalized: NormalizedValues,
    *,
    recent_supply_stratum_eligibility_coverage: float,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> float | None:
    """Return recent supply ``R`` or ``None`` when unavailable (LREQ-SCR-030).

    A coverage strictly below ``min_required_component_coverage`` makes ``R``
    unavailable **before** any shrinkage and excludes its weight from the
    composite (SRS-lean §7.5 / §9.1); coverage exactly equal to the threshold is
    available. Otherwise, with ``s = P_ref(RecentShareRaw)`` and
    ``a = P_ref(MedianAgeRaw)``:
    ``Rpressure0 = 0.70 * s + 0.30 * (1 - a)`` when both are available; the single
    available pressure term (``s`` or ``1 - a``) when exactly one is; ``None``
    when neither is. Then ``R0 = 1 - Rpressure0`` and
    ``R = clamp(0.5 + coverage * (R0 - 0.5), 0, 1)``. (Weighting the single term
    by its renormalized subweight gives the same value; plan §12 D7.) A non-finite
    or out-of-range ``min_required_component_coverage`` raises ``ValueError``.
    """
    threshold = _require_threshold(min_required_component_coverage)
    if recent_supply_stratum_eligibility_coverage < threshold:
        return None
    share = normalized.recent_share_raw
    age = normalized.median_age_raw
    if share is not None and age is not None:
        pressure0: float = RECENT_SUBWEIGHT_SHARE * share + RECENT_SUBWEIGHT_AGE * (
            1.0 - age
        )
    elif share is not None:
        pressure0 = share
    elif age is not None:
        pressure0 = 1.0 - age
    else:
        return None
    recent0 = 1.0 - pressure0
    return _shrink(recent0, recent_supply_stratum_eligibility_coverage)


def quality_component(
    normalized: NormalizedValues,
    *,
    quality_stratum_eligibility_coverage: float,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> float | None:
    """Return quality ``Q`` or ``None`` when unavailable (LREQ-SCR-040).

    A ``quality_stratum_eligibility_coverage`` strictly below
    ``min_required_component_coverage`` makes ``Q`` unavailable before shrinkage
    (SRS-lean §7.5 / §9.1); coverage exactly equal to the threshold is available.
    A ``None`` ``P_ref(QualityRaw)`` also yields ``None``. Otherwise
    ``Q0 = 1 - P_ref(QualityRaw)`` and
    ``Q = clamp(0.5 + coverage * (Q0 - 0.5), 0, 1)``. Chunk 7B already returns a
    null ``QualityRaw`` below the threshold, on contradicted page views, and on a
    zero denominator, so the threshold check here is defensive and cannot change
    a Chunk 7B-produced value. A non-finite or out-of-range
    ``min_required_component_coverage`` raises ``ValueError``.
    """
    threshold = _require_threshold(min_required_component_coverage)
    if quality_stratum_eligibility_coverage < threshold:
        return None
    quality = normalized.quality_raw
    if quality is None:
        return None
    quality0 = 1.0 - quality
    return _shrink(quality0, quality_stratum_eligibility_coverage)


def compute_components(
    normalized: NormalizedValues,
    *,
    demand_stratum_eligibility_coverage: float,
    recent_supply_stratum_eligibility_coverage: float,
    quality_stratum_eligibility_coverage: float,
    breadth_source: BreadthSource,
    breadth_completeness_status: BreadthCompletenessStatus,
    page_view_semantics_status: PageViewSemanticsStatus,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> ComponentValues:
    """Return ``D``/``C``/``R``/``Q`` for one target (SRS-lean §8.2).

    Validates ``min_required_component_coverage`` once, then dispatches to the
    four component functions with the supplied scalars. When
    ``page_view_semantics_status is PageViewSemanticsStatus.CONTRADICTED`` it
    replaces ``demand`` and ``quality`` with ``None`` (LREQ-SCR-050); ``C`` and
    ``R`` are unchanged and may remain available. The status is consumed as an
    explicit caller parameter and is never re-detected from response shape
    (interfaces/chunk-05.md §5.8). An invalid threshold raises ``ValueError``.
    """
    threshold = _require_threshold(min_required_component_coverage)
    components = ComponentValues(
        demand=demand_component(
            normalized,
            demand_stratum_eligibility_coverage=demand_stratum_eligibility_coverage,
            min_required_component_coverage=threshold,
        ),
        competition=competition_component(
            normalized,
            breadth_source=breadth_source,
            breadth_completeness_status=breadth_completeness_status,
        ),
        recent_supply=recent_supply_component(
            normalized,
            recent_supply_stratum_eligibility_coverage=(
                recent_supply_stratum_eligibility_coverage
            ),
            min_required_component_coverage=threshold,
        ),
        quality=quality_component(
            normalized,
            quality_stratum_eligibility_coverage=quality_stratum_eligibility_coverage,
            min_required_component_coverage=threshold,
        ),
    )
    if page_view_semantics_status is PageViewSemanticsStatus.CONTRADICTED:
        return ComponentValues(
            demand=None,
            competition=components.competition,
            recent_supply=components.recent_supply,
            quality=None,
        )
    return components


def renormalized_composite(
    components: ComponentValues,
    weights: Mapping[str, float],
) -> CompositeResult:
    """Combine available components with available-weight renormalization.

    Iterates ``COMPONENT_WEIGHT_KEYS`` in the fixed order ``D, C, R, Q``. A
    component is available iff its value is non-``None``; unavailable components
    are excluded from ``W_A = sum(weights of available components)``, in key
    order. ``weights`` must contain every key with a finite, non-negative value,
    else ``ValueError`` (caller/policy breach). When fewer than two components
    are available the score is ``None`` with ``score_state = unavailable``
    (``W_A`` is still reported). Otherwise, if ``W_A <= 0`` (only zero-weight
    components available) raises ``ValueError``; else
    ``S_available = sum(w_x * x) / W_A`` and
    ``market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)``
    with ``score_state = available`` when all four are available and ``partial``
    otherwise (SRS-lean §8.3 / LREQ-SCR-060).
    """
    resolved: list[tuple[str, float, float]] = []
    total_weight = 0.0
    available_count = 0
    for key in COMPONENT_WEIGHT_KEYS:
        if key not in weights:
            raise ValueError(f"weights is missing component key {key!r}")
        weight = _finite_float(weights[key], name=f"weights[{key!r}]")
        if weight < 0:
            raise ValueError(f"weights[{key!r}] must be non-negative")
        value = getattr(components, _COMPONENT_ATTRS[key])
        if value is None:
            continue
        available_count += 1
        total_weight += weight
        resolved.append((key, weight, value))

    if available_count < 2:
        return CompositeResult(
            market_opportunity_score=None,
            score_state=ScoreState.UNAVAILABLE,
            available_component_count=available_count,
            available_weight=total_weight,
        )
    if total_weight <= 0.0:
        raise ValueError("available component weight must be positive")

    available_sum = 0.0
    for _key, weight, value in resolved:
        available_sum += weight * value
    score_available = available_sum / total_weight
    score = _clamp(0.5 + total_weight * (score_available - 0.5))
    state = ScoreState.AVAILABLE if available_count == 4 else ScoreState.PARTIAL
    return CompositeResult(
        market_opportunity_score=score,
        score_state=state,
        available_component_count=available_count,
        available_weight=total_weight,
    )


def balanced_composite(components: ComponentValues) -> CompositeResult:
    """Return the balanced primary composite for ``components`` (LREQ-SCR-060).

    Uses the fixed Lean v1 weights ``models.W_D/W_C/W_R/W_Q`` (0.35/0.30/0.20/
    0.15), which are not configurable in Lean v1, so this is exactly
    ``renormalized_composite(components, models.SENSITIVITY_POLICIES["balanced"])``
    (SRS-lean §8.3). Because the weights sum to ``1.0``, a four-component score
    equals its ``S_available``. Null/edge behavior matches
    :func:`renormalized_composite`.
    """
    return renormalized_composite(
        components,
        {"D": W_D, "C": W_C, "R": W_R, "Q": W_Q},
    )


def score_category(
    target: CategoryRawMetrics,
    all_metrics: Sequence[CategoryRawMetrics],
    *,
    page_view_semantics_status: PageViewSemanticsStatus,
) -> ScoreResult:
    """Score one target: reference → normalized → components → composite.

    Pure wiring over the Chunk 8 surface; ``target`` must be the entry in
    ``all_metrics`` whose ``category`` it names (else ``ValueError`` through
    :func:`leave_one_out_reference`). ``page_view_semantics_status`` is supplied
    explicitly by the caller and consumed, never detected. The returned
    ``ScoreResult`` reports ``market_opportunity_score``, ``score_state``, the
    four components, and ``available_component_count``;
    ``rankability_status`` and ``evidence_grade`` are left at their Chunk 0
    defaults because Chunk 8 assigns neither (rankability is Chunk 9A's). An
    unavailable component remains ``None`` and is never ``0.0``.
    """
    reference = leave_one_out_reference(all_metrics, target.category)
    normalized = normalize_raw_metrics(target.raw, reference)
    components = compute_components(
        normalized,
        demand_stratum_eligibility_coverage=(
            target.demand_stratum_eligibility_coverage
        ),
        recent_supply_stratum_eligibility_coverage=(
            target.recent_supply_stratum_eligibility_coverage
        ),
        quality_stratum_eligibility_coverage=(
            target.quality_stratum_eligibility_coverage
        ),
        breadth_source=target.breadth_source,
        breadth_completeness_status=target.breadth_completeness_status,
        page_view_semantics_status=page_view_semantics_status,
    )
    composite = balanced_composite(components)
    return ScoreResult(
        market_opportunity_score=composite.market_opportunity_score,
        score_state=composite.score_state,
        component_d=components.demand,
        component_c=components.competition,
        component_r=components.recent_supply,
        component_q=components.quality,
        available_component_count=composite.available_component_count,
    )


#: Maps a ``COMPONENT_WEIGHT_KEYS`` key to its ``ComponentValues`` attribute.
_COMPONENT_ATTRS: dict[str, str] = {
    "D": "demand",
    "C": "competition",
    "R": "recent_supply",
    "Q": "quality",
}
