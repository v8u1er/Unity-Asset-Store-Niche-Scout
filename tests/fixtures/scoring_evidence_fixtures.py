"""Golden vectors and builders for Chunk 9A pre-sensitivity evidence.

Data only: explicit constants, inert golden-vector tables, and small
keyword-argument builders. There are no assertions here; the expectations live in
``tests/test_scoring_evidence.py``.

Every value below is hand-derived from SRS-lean.md §9.1 (LREQ-EVD-010/-020/-030),
§7.3 (LREQ-MET-070), §4.1 (LREQ-EXT-050/-090), §8.2 (LREQ-SCR-050), and §4.4
(LREQ-ID-040), never copied from the implementation:

* The reason vocabularies and their fixed emission order are the plan §5
  ``NotRankableReason`` / ``NOT_RANKABLE_REASON_ORDER`` and
  ``ProvisionalReason`` / ``PROVISIONAL_REASON_ORDER`` spellings.
* A base-rankable candidate requires the run to have at least
  ``STRONG_REFERENCE_CATEGORY_COUNT = 21`` categories, all four components,
  coverage ``>= MIN_REQUIRED_COMPONENT_COVERAGE = 0.50`` on each sample-derived
  component, a valid leave-one-out reference, and field-specific reference support
  (LREQ-EVD-020 lines 989-994).
* ``provisional`` reasons here are the pre-sensitivity half of LREQ-EVD-030 only
  (run below 21, incomplete breadth fallback, coverage in ``[0.50, 0.80)``). The
  sensitivity clause is Chunk 9B's and has no member here.

Design note on typing: this module is imported by ``tests/test_scoring_evidence.py``
*after* that module has imported the Chunk 9A public surface, but to keep the
fixture module importable on its own (before the implementation lands) every
Chunk 9A name is imported lazily inside a builder function, exactly as
``scoring_fixtures`` does for its ``NormalizedValues`` builders. The module-level
tables hold only plain literals and the already-existing Chunk 0/7B types.

No network, no credentials, no clock reads, no randomness: every value below is an
explicit literal and every builder is total over its arguments.
"""

from __future__ import annotations

from niche_scout.metrics import CategoryRawMetrics, RawMetricBundle
from niche_scout.models import (
    MIN_REQUIRED_COMPONENT_COVERAGE,
    STRONG_COMPONENT_COVERAGE,
    STRONG_REFERENCE_CATEGORY_COUNT,
    BreadthCompletenessStatus,
    BreadthSource,
    DiscoveryStatus,
    IdentityPreflightStatus,
    PageViewSemanticsStatus,
    ScoreState,
)

__all__ = [
    "BASE_CANDIDATE_REASON_VECTOR",
    "CATEGORY_ORDER_FULL_RUN",
    "EIGHT_CATEGORY_COUNT",
    "FULL_RUN_CATEGORY_COUNT",
    "FULL_RUN_REFERENCE_SIZE",
    "FIELD_REFERENCE_SUPPORT_VECTORS",
    "MISALIGNED_INPUT_VECTORS",
    "MIXED_RUN_CATEGORY_COUNT",
    "MIXED_RUN_DEMAND_NONE_CATEGORY",
    "NO_RANKABLE_SURFACE",
    "NOT_RANKABLE_MATRIX",
    "NOT_RANKABLE_REASON_EXPECTED_VALUES",
    "ORDER_VECTOR_REASONS",
    "PRE_SENSITIVITY_FUNCTION_NAMES",
    "PRE_SENSITIVITY_STATE_VECTORS",
    "PROVISIONAL_COVERAGE_VECTORS",
    "PROVISIONAL_REASON_EXPECTED_VALUES",
    "SCORE_STATE_DISTINCTNESS_VECTORS",
    "TWENTY_CATEGORY_COUNT",
    "all_verified_run_metrics",
    "clean_evidence_kwargs",
    "make_base_candidate_inputs",
    "make_field_usable_counts",
    "make_pre_sensitivity_input",
    "make_score_result",
    "verified_metrics",
]

# ---------------------------------------------------------------------------
# Run-shape constants (SRS-lean.md §9.1 lines 1013-1017)
# ---------------------------------------------------------------------------

EIGHT_CATEGORY_COUNT: int = 8
TWENTY_CATEGORY_COUNT: int = 20
FULL_RUN_CATEGORY_COUNT: int = STRONG_REFERENCE_CATEGORY_COUNT
MIXED_RUN_CATEGORY_COUNT: int = STRONG_REFERENCE_CATEGORY_COUNT

#: ``STRONG_REFERENCE_CATEGORY_COUNT - 1``: a fully verified target has every one
#: of its peers usable for every raw field (SRS §8.1: one leave-one-out peer per
#: other category).
FULL_RUN_REFERENCE_SIZE: int = STRONG_REFERENCE_CATEGORY_COUNT - 1

#: The canonical ``all_metrics`` order the 21-category run uses (plan §5.1 R3).
CATEGORY_ORDER_FULL_RUN: tuple[str, ...] = tuple(
    f"c-{index}" for index in range(STRONG_REFERENCE_CATEGORY_COUNT)
)

#: The one category in the mixed run whose demand component is unavailable
#: (``component_d = None``) so only ``REQUIRED_DEMAND_DATA_UNAVAILABLE`` fires.
MIXED_RUN_DEMAND_NONE_CATEGORY: str = "c-3"

#: No rankable surface exists in this chunk: sensitivity outputs, final
#: ``evidence_grade``, and final ``rankability_status`` are Chunk 9B's. The test
#: asserts none of these names is exposed by ``niche_scout.scoring``.
NO_RANKABLE_SURFACE: tuple[str, ...] = (
    "compute_sensitivity",
    "final_evidence_grade",
    "final_rankability_status",
)

#: The public Chunk 9A callables that must carry type hints and docstrings
#: (LREQ-NFR-040; plan §7 bullet 8).
PRE_SENSITIVITY_FUNCTION_NAMES: tuple[str, ...] = (
    "field_reference_support_passes",
    "not_rankable_reasons",
    "provisional_reasons",
    "pre_sensitivity_rankability_state",
    "evaluate_pre_sensitivity_evidence",
    "build_base_rankable_candidates",
)

# ---------------------------------------------------------------------------
# Reason-vocabulary expected string values (plan §5 frozen surfaces)
# ---------------------------------------------------------------------------
#
# These are the frozen ``StrEnum`` values; a StrEnum member equals its string
# value, so asserting equality against these literals is a real check of the
# vocabulary (not a tautology).

NOT_RANKABLE_REASON_EXPECTED_VALUES: tuple[str, ...] = (
    "unrecoverable_data_integrity_error",
    "discovery_filter_unverified",
    "unresolved_or_conflicting_identity",
    "identity_preflight_failed",
    "competition_unbounded_or_material_failure",
    "page_view_semantics_contradicted",
    "required_demand_data_unavailable",
    "recent_supply_minimum_not_met",
    "quality_unavailable",
    "no_valid_leave_one_out_reference",
    "field_reference_support_insufficient",
)

PROVISIONAL_REASON_EXPECTED_VALUES: tuple[str, ...] = (
    "run_below_strong_reference",
    "incomplete_breadth_fallback",
    "coverage_below_strong",
)

# ---------------------------------------------------------------------------
# Builders (plain keyword facts; Chunk 9A names imported lazily)
# ---------------------------------------------------------------------------


def make_score_result(
    *,
    market_opportunity_score: float | None = 0.5,
    score_state: ScoreState = ScoreState.AVAILABLE,
    component_d: float | None = 0.5,
    component_c: float | None = 0.5,
    component_r: float | None = 0.5,
    component_q: float | None = 0.5,
    available_component_count: int | None = None,
) -> object:
    """Build a ``ScoreResult`` literal with the four component facts explicit.

    ``ScoreResult`` is a frozen Chunk 0 structure (interfaces/chunk-08.md §2).
    ``available_component_count`` is derived from the four component fields when
    not given, matching the Chunk 8 wiring: a ``None`` component is unavailable
    and is never counted as a zero-weight component (SRS §1.2).
    """
    from niche_scout.scoring import ScoreResult

    if available_component_count is None:
        available_component_count = sum(
            component is not None
            for component in (
                component_d,
                component_c,
                component_r,
                component_q,
            )
        )
    return ScoreResult(
        market_opportunity_score=market_opportunity_score,
        score_state=score_state,
        component_d=component_d,
        component_c=component_c,
        component_r=component_r,
        component_q=component_q,
        available_component_count=available_component_count,
    )


def make_field_usable_counts(
    *,
    demand_per_asset_raw: int = 0,
    demand_median_raw: int = 0,
    breadth_raw: int = 0,
    recent_share_raw: int = 0,
    median_age_raw: int = 0,
    quality_raw: int = 0,
) -> object:
    """Build a ``FieldUsableCounts`` literal.

    Each value is a count, so ``0`` is a legitimate explicit value and means "no
    usable peer value for this field" -- it is not a missing value (plan §5.1
    null/edge behaviour).
    """
    from niche_scout.scoring import FieldUsableCounts

    return FieldUsableCounts(
        demand_per_asset_raw=demand_per_asset_raw,
        demand_median_raw=demand_median_raw,
        breadth_raw=breadth_raw,
        recent_share_raw=recent_share_raw,
        median_age_raw=median_age_raw,
        quality_raw=quality_raw,
    )


def clean_evidence_kwargs() -> dict[str, object]:
    """Return the keyword facts of a fully verified category (plan §9).

    Every fact is explicit and "clean": discovery ``COMPLETE``, filter verified,
    no unresolved or conflicting identities, page views not contradicted, breadth
    verified and complete, coverages ``1.0``, and a valid 20-peer leave-one-out
    reference with all six field counts at ``20``.
    """
    return {
        "discovery_status": DiscoveryStatus.COMPLETE,
        "discovery_filter_verified": True,
        "discovery_unresolved_identity_count": 0,
        "discovery_conflict_count": 0,
        "discovery_bounded_by_verified_total": True,
        "page_view_semantics_status": PageViewSemanticsStatus.UNVALIDATED,
        "breadth_source": BreadthSource.VERIFIED_TOTAL_COUNT,
        "breadth_completeness_status": BreadthCompletenessStatus.COMPLETE,
        "demand_stratum_eligibility_coverage": 1.0,
        "recent_supply_stratum_eligibility_coverage": 1.0,
        "quality_stratum_eligibility_coverage": 1.0,
        "reference_size": FULL_RUN_REFERENCE_SIZE,
        "field_usable_counts": make_field_usable_counts(
            demand_per_asset_raw=FULL_RUN_REFERENCE_SIZE,
            demand_median_raw=FULL_RUN_REFERENCE_SIZE,
            breadth_raw=FULL_RUN_REFERENCE_SIZE,
            recent_share_raw=FULL_RUN_REFERENCE_SIZE,
            median_age_raw=FULL_RUN_REFERENCE_SIZE,
            quality_raw=FULL_RUN_REFERENCE_SIZE,
        ),
    }


def make_pre_sensitivity_input(category: str, **overrides: object) -> object:
    """Build a ``PreSensitivityCategoryInput`` from the clean facts plus overrides.

    ``clean_evidence_kwargs`` supplies every keyword; ``overrides`` replaces only
    the fact(s) a vector varies, so a vector states exactly what it means to
    change. Unknown keywords are rejected by the dataclass itself.
    """
    from niche_scout.scoring import PreSensitivityCategoryInput

    kwargs = clean_evidence_kwargs()
    kwargs.update(overrides)
    return PreSensitivityCategoryInput(category=category, **kwargs)


def verified_metrics(category: str) -> CategoryRawMetrics:
    """Build one fully verified ``CategoryRawMetrics`` (ordering authority only).

    Chunk 9A consumes ``CategoryRawMetrics`` only as the deterministic
    ``all_metrics`` ordering authority (plan §5.1 R3); the coverage/provenance
    facts are supplied again explicitly through ``PreSensitivityCategoryInput``.
    All six raw fields are explicit values and all three coverages are ``1.0``.
    """
    return CategoryRawMetrics(
        category=category,
        raw=RawMetricBundle(
            demand_per_asset_raw=1.0,
            demand_median_raw=1.0,
            breadth_raw=1.0,
            recent_share_raw=1.0,
            median_age_raw=1.0,
            quality_raw=1.0,
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


def all_verified_run_metrics(count: int) -> tuple[CategoryRawMetrics, ...]:
    """Build a ``count``-category run in canonical ``c-0..c-N`` order."""
    return tuple(verified_metrics(f"c-{index}") for index in range(count))


def make_base_candidate_inputs(
    count: int,
    *,
    demand_none_category: str | None = None,
) -> tuple[object, ...]:
    """Build ``count`` clean inputs; optionally one has ``component_d = None``.

    The demand-unavailable category still carries clean *evidence* facts; only the
    ``ScoreResult`` component differs (the fixture's ``scores`` argument supplies
    it), so exactly ``REQUIRED_DEMAND_DATA_UNAVAILABLE`` fires for it.
    """
    return tuple(make_pre_sensitivity_input(f"c-{index}") for index in range(count))


# ---------------------------------------------------------------------------
# NOT_RANKABLE reason matrix (LREQ-EVD-020 lines 980-987)
# ---------------------------------------------------------------------------
#
# Each row is ``(label, score_overrides, evidence_overrides,
# identity_preflight_status, expected_reasons)``. ``score_overrides`` are applied
# over the fully available score (``D = C = R = Q = 0.5``) and
# ``evidence_overrides`` over the clean facts, so every row isolates one clause.
# The expected reason tuple is exactly the one reason the clause names.

_NOT_RANKABLE = IdentityPreflightStatus.PASSED

NOT_RANKABLE_MATRIX: tuple[tuple[str, dict, dict, object, tuple], ...] = (
    # LREQ-EXT-050 line 263: a failed page is never zero assets -> unrecoverable.
    (
        "request_failed",
        {},
        {"discovery_status": DiscoveryStatus.REQUEST_FAILED},
        _NOT_RANKABLE,
        ("unrecoverable_data_integrity_error",),
    ),
    (
        "page_failed",
        {},
        {"discovery_status": DiscoveryStatus.PAGE_FAILED},
        _NOT_RANKABLE,
        ("unrecoverable_data_integrity_error",),
    ),
    # LREQ-EXT-090 lines 279-281: unverified filter / category mismatch -> warning
    # and never fully rankable.
    (
        "filter_unverified_status",
        {},
        {"discovery_status": DiscoveryStatus.FILTER_UNVERIFIED},
        _NOT_RANKABLE,
        ("discovery_filter_unverified",),
    ),
    (
        "category_mismatch_status",
        {},
        {"discovery_status": DiscoveryStatus.CATEGORY_MISMATCH},
        _NOT_RANKABLE,
        ("discovery_filter_unverified",),
    ),
    (
        "filter_verified_false",
        {},
        {"discovery_filter_verified": False},
        _NOT_RANKABLE,
        ("discovery_filter_unverified",),
    ),
    # LREQ-EVD-020 lines 981-982: unresolved or conflicting identity.
    (
        "identity_incomplete_status",
        {},
        {"discovery_status": DiscoveryStatus.IDENTITY_INCOMPLETE},
        _NOT_RANKABLE,
        ("unresolved_or_conflicting_identity",),
    ),
    (
        "unresolved_identity_count_one",
        {},
        {"discovery_unresolved_identity_count": 1},
        _NOT_RANKABLE,
        ("unresolved_or_conflicting_identity",),
    ),
    (
        "conflict_count_one",
        {},
        {"discovery_conflict_count": 1},
        _NOT_RANKABLE,
        ("unresolved_or_conflicting_identity",),
    ),
    # LREQ-EVD-020 line 985: identity preflight fails.
    (
        "preflight_failed",
        {},
        {},
        IdentityPreflightStatus.FAILED,
        ("identity_preflight_failed",),
    ),
    (
        "preflight_insufficient",
        {},
        {},
        IdentityPreflightStatus.INSUFFICIENT,
        ("identity_preflight_failed",),
    ),
    # LREQ-EVD-020 lines 986-987 with LREQ-MET-070 lines 764-766: unbounded /
    # material-failure competition is an unavailable C component.
    (
        "competition_unavailable",
        {"component_c": None},
        {},
        _NOT_RANKABLE,
        ("competition_unbounded_or_material_failure",),
    ),
    # LREQ-SCR-050 line 949: contradicted page views keep C/R but are not rankable.
    (
        "page_views_contradicted",
        {},
        {"page_view_semantics_status": PageViewSemanticsStatus.CONTRADICTED},
        _NOT_RANKABLE,
        ("page_view_semantics_contradicted",),
    ),
    # LREQ-EVD-020 lines 982-984: each required component unavailable.
    (
        "demand_unavailable",
        {"component_d": None},
        {},
        _NOT_RANKABLE,
        ("required_demand_data_unavailable",),
    ),
    (
        "recent_supply_unavailable",
        {"component_r": None},
        {},
        _NOT_RANKABLE,
        ("recent_supply_minimum_not_met",),
    ),
    (
        "quality_unavailable",
        {"component_q": None},
        {},
        _NOT_RANKABLE,
        ("quality_unavailable",),
    ),
    # LREQ-EVD-020 line 985: no valid leave-one-out reference (reference_size 0).
    (
        "no_reference",
        {},
        {"reference_size": 0},
        _NOT_RANKABLE,
        ("no_valid_leave_one_out_reference",),
    ),
    # LREQ-EVD-020 line 993: field-specific reference support fails when an
    # available component's consumed field has no usable peer value.
    (
        "field_reference_support_insufficient",
        {},
        {
            "field_usable_counts": make_field_usable_counts(
                demand_per_asset_raw=0,
                demand_median_raw=FULL_RUN_REFERENCE_SIZE,
                breadth_raw=FULL_RUN_REFERENCE_SIZE,
                recent_share_raw=FULL_RUN_REFERENCE_SIZE,
                median_age_raw=FULL_RUN_REFERENCE_SIZE,
                quality_raw=FULL_RUN_REFERENCE_SIZE,
            )
        },
        _NOT_RANKABLE,
        ("field_reference_support_insufficient",),
    ),
)

# ---------------------------------------------------------------------------
# Simultaneous-condition emission-order vector (LREQ-ARCH-030 determinism)
# ---------------------------------------------------------------------------
#
# ``request_failed`` + ``component_d = None`` + ``reference_size = 0`` fires four
# reasons; they must appear in the fixed NOT_RANKABLE_REASON_ORDER emission order
# (unrecoverable, filtered-identity-count, demand, reference), not in the order
# the facts happen to be written.

ORDER_VECTOR_SCORE_OVERRIDES: dict[str, object] = {"component_d": None}
ORDER_VECTOR_EVIDENCE_OVERRIDES: dict[str, object] = {
    "discovery_status": DiscoveryStatus.REQUEST_FAILED,
    "reference_size": 0,
}
ORDER_VECTOR_REASONS: tuple[str, ...] = (
    "unrecoverable_data_integrity_error",
    "required_demand_data_unavailable",
    "no_valid_leave_one_out_reference",
)

#: Same facts in a different input order (evidence fact first, then component).
#: The emitted reason order must be byte-identical to ``ORDER_VECTOR_REASONS``.
ORDER_VECTOR_ALTERNATE_EVIDENCE_OVERRIDES: dict[str, object] = {
    "reference_size": 0,
    "discovery_status": DiscoveryStatus.REQUEST_FAILED,
}

# ---------------------------------------------------------------------------
# Field-reference-support vectors (LREQ-EVD-020 line 993; plan §12 Q1/R11)
# ---------------------------------------------------------------------------
#
# ``(label, counts_kwargs, availability_flags, expected)``. Support is required
# only for the raw fields each *available* component consumes (SRS §8.2):
#   D <- demand_per_asset_raw, demand_median_raw
#   C <- breadth_raw
#   R <- recent_share_raw, median_age_raw
#   Q <- quality_raw

FIELD_REFERENCE_SUPPORT_VECTORS: tuple[tuple[str, dict, dict, bool], ...] = (
    # (i) demand available from a single sub-signal: demand_median_raw has 0
    # usable peers, but demand_per_asset_raw > 0 satisfies the demand
    # requirement, and every other available component's consumed field is > 0.
    (
        "demand_available_one_of_two_fields",
        {
            "demand_per_asset_raw": 5,
            "demand_median_raw": 0,
            "breadth_raw": 5,
            "recent_share_raw": 5,
            "median_age_raw": 5,
            "quality_raw": 5,
        },
        {
            "demand_available": True,
            "competition_available": True,
            "recent_supply_available": True,
            "quality_available": True,
        },
        True,
    ),
    # (ii) demand available with both consumed counts 0 -> the demand
    # requirement is unsatisfied -> False.
    (
        "demand_available_both_fields_zero",
        {
            "demand_per_asset_raw": 0,
            "demand_median_raw": 0,
            "breadth_raw": 5,
            "recent_share_raw": 5,
            "median_age_raw": 5,
            "quality_raw": 5,
        },
        {
            "demand_available": True,
            "competition_available": True,
            "recent_supply_available": True,
            "quality_available": True,
        },
        False,
    ),
    # (iii) competition available with breadth_raw = 0 -> False.
    (
        "competition_available_breadth_zero",
        {
            "demand_per_asset_raw": 5,
            "demand_median_raw": 5,
            "breadth_raw": 0,
            "recent_share_raw": 5,
            "median_age_raw": 5,
            "quality_raw": 5,
        },
        {
            "demand_available": True,
            "competition_available": True,
            "recent_supply_available": True,
            "quality_available": True,
        },
        False,
    ),
    # (iv) an unused field at 0 never fails: Q is unavailable, so quality_raw = 0
    # contributes no requirement.
    (
        "unused_quality_field_zero_is_ignored",
        {
            "demand_per_asset_raw": 5,
            "demand_median_raw": 5,
            "breadth_raw": 5,
            "recent_share_raw": 5,
            "median_age_raw": 5,
            "quality_raw": 0,
        },
        {
            "demand_available": True,
            "competition_available": True,
            "recent_supply_available": True,
            "quality_available": False,
        },
        True,
    ),
    # (iv-b) the mirror: C unavailable, so breadth_raw = 0 is ignored.
    (
        "unused_breadth_field_zero_is_ignored",
        {
            "demand_per_asset_raw": 5,
            "demand_median_raw": 5,
            "breadth_raw": 0,
            "recent_share_raw": 5,
            "median_age_raw": 5,
            "quality_raw": 5,
        },
        {
            "demand_available": True,
            "competition_available": False,
            "recent_supply_available": True,
            "quality_available": True,
        },
        True,
    ),
    # (v) all four components unavailable -> vacuous True (the category is
    # already not_rankable through the component-availability reasons).
    (
        "all_components_unavailable_is_vacuously_true",
        {
            "demand_per_asset_raw": 0,
            "demand_median_raw": 0,
            "breadth_raw": 0,
            "recent_share_raw": 0,
            "median_age_raw": 0,
            "quality_raw": 0,
        },
        {
            "demand_available": False,
            "competition_available": False,
            "recent_supply_available": False,
            "quality_available": False,
        },
        True,
    ),
)

# ---------------------------------------------------------------------------
# Provisional-reason vectors (LREQ-EVD-030 lines 996-1001)
# ---------------------------------------------------------------------------
#
# ``(label, evidence_overrides, run_category_count, expected_reasons)``. All rows
# start from the clean score (all four components) and clean facts.

PROVISIONAL_COVERAGE_STRONG: float = STRONG_COMPONENT_COVERAGE
PROVISIONAL_COVERAGE_MINIMUM: float = MIN_REQUIRED_COMPONENT_COVERAGE

#: Coverage vectors on one sample-derived component (demand); the others stay at
#: 1.0. 0.79 < 0.80 -> COVERAGE_BELOW_STRONG; 0.80 is the strong boundary and
#: fires nothing; 0.50 is the required minimum boundary and fires nothing.
PROVISIONAL_COVERAGE_VECTORS: tuple[tuple[str, float, object], ...] = (
    (
        "coverage_below_strong",
        0.79,
        ("coverage_below_strong",),
    ),
    (
        "coverage_exactly_strong",
        PROVISIONAL_COVERAGE_STRONG,
        (),
    ),
    (
        "coverage_exactly_minimum",
        PROVISIONAL_COVERAGE_MINIMUM,
        (),
    ),
)

#: The 21-category fallback run: breadth is the incomplete fallback estimate.
#: With ``discovery_bounded_by_verified_total = True`` it still fires the
#: provisional reason (Q3), because the reason is about the estimate itself.
PROVISIONAL_BREADTH_FALLBACK_OVERRIDES: dict[str, object] = {
    "breadth_source": BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT,
    "breadth_completeness_status": BreadthCompletenessStatus.INCOMPLETE_ESTIMATE,
}

# ---------------------------------------------------------------------------
# State-transition vectors (LREQ-EVD-010)
# ---------------------------------------------------------------------------
#
# ``(not_rankable_present, provisional_present, base_rankable, expected_state)``.
# NOT_RANKABLE wins whenever any reason is present; else RANKABLE requires
# base_rankable and no provisional reason; else PROVISIONAL.

PRE_SENSITIVITY_STATE_VECTORS: tuple[tuple[bool, bool, bool, str], ...] = (
    # not_rankable non-empty -> NOT_RANKABLE regardless of the other two.
    (True, False, False, "not_rankable"),
    (True, True, False, "not_rankable"),
    (True, False, True, "not_rankable"),
    (True, True, True, "not_rankable"),
    # no reason; base_rankable and no provisional -> RANKABLE.
    (False, False, True, "rankable"),
    # provisional reason present -> PROVISIONAL even when base_rankable.
    (False, True, True, "provisional"),
    (False, True, False, "provisional"),
    # neither reason and not a base candidate -> PROVISIONAL.
    (False, False, False, "provisional"),
)

# ---------------------------------------------------------------------------
# Distinctness vectors (gate bullet 2; LREQ-EVD-020)
# ---------------------------------------------------------------------------
#
# ``(label, score_state, expected_rankability_state)``: ``score_state`` is
# independent of the pre-sensitivity rankability state.

SCORE_STATE_DISTINCTNESS_VECTORS: tuple[tuple[str, ScoreState, str], ...] = (
    ("partial_score_provisional", ScoreState.PARTIAL, "provisional"),
    ("available_score_not_rankable", ScoreState.AVAILABLE, "not_rankable"),
)

# ---------------------------------------------------------------------------
# Misaligned-input vectors (plan §5.1 ``build_base_rankable_candidates``)
# ---------------------------------------------------------------------------
#
# ``(label, count)``: ``count`` metrics vs ``count - 1`` inputs/scores.

MISALIGNED_INPUT_VECTORS: tuple[tuple[str, int], ...] = (
    ("inputs_one_shorter_than_metrics", FULL_RUN_CATEGORY_COUNT),
    ("scores_one_shorter_than_metrics", FULL_RUN_CATEGORY_COUNT),
)

# ---------------------------------------------------------------------------
# Fully verified base-candidate run (21 categories, plan §9)
# ---------------------------------------------------------------------------

BASE_CANDIDATE_REASON_VECTOR: tuple[str, ...] = ()
