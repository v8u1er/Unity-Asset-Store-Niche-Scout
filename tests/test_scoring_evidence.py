"""Chunk 9A analytical tests — pre-sensitivity evidence and base candidates.

Every expected value is a fixture constant from
``tests/fixtures/scoring_evidence_fixtures.py``, hand-derived from SRS-lean.md
§9.1 (LREQ-EVD-010/-020/-030) with §7.3 (LREQ-MET-070), §4.1
(LREQ-EXT-050/-090), §8.2 (LREQ-SCR-050), and §4.4 (LREQ-ID-040), matching plan
``chunk-9A-pre-sensitivity-evidence-and-base-candidates.md`` §9. No live network,
no credentials, no clock reads, and no randomness: every fact is an explicit
literal.

The module imports the Chunk 9A public surface from ``niche_scout.scoring``.
Before the implementation lands that import raises ``ImportError``, which is the
required missing-implementation shape for a test-author-first chunk: the test file
must be syntactically valid and must not fail at collection for any other reason.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import fixtures.scoring_evidence_fixtures as efx
import pytest

from niche_scout import scoring
from niche_scout.models import (
    STRONG_COMPONENT_COVERAGE,
    STRONG_REFERENCE_CATEGORY_COUNT,
    BreadthCompletenessStatus,
    BreadthSource,
    DiscoveryStatus,
    IdentityPreflightStatus,
    PageViewSemanticsStatus,
    RankabilityStatus,
    ScoreState,
)
from niche_scout.scoring import (
    BaseCandidateSet,
    NotRankableReason,
    PreSensitivityEvidenceState,
    PreSensitivityRankabilityState,
    ProvisionalReason,
)
from niche_scout.tools.check_import_boundaries import (
    FORBIDDEN_MODULES,
    check_module,
    clock_violations,
)

# ---------------------------------------------------------------------------
# Chunk 9A public surface (plan §5 frozen signatures)
# ---------------------------------------------------------------------------
#
# The names are imported directly (not reached through the module object) so a
# missing Chunk 9A surface raises ``ImportError`` at import time -- the required
# missing-implementation shape -- instead of an ``AttributeError`` raised while
# aliasing at module scope.

UNRECOVERABLE_DATA_INTEGRITY_ERROR = (
    NotRankableReason.UNRECOVERABLE_DATA_INTEGRITY_ERROR
)
DISCOVERY_FILTER_UNVERIFIED = NotRankableReason.DISCOVERY_FILTER_UNVERIFIED
UNRESOLVED_OR_CONFLICTING_IDENTITY = (
    NotRankableReason.UNRESOLVED_OR_CONFLICTING_IDENTITY
)
IDENTITY_PREFLIGHT_FAILED = NotRankableReason.IDENTITY_PREFLIGHT_FAILED
COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE = (
    NotRankableReason.COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE
)
PAGE_VIEW_SEMANTICS_CONTRADICTED = NotRankableReason.PAGE_VIEW_SEMANTICS_CONTRADICTED
REQUIRED_DEMAND_DATA_UNAVAILABLE = NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE
RECENT_SUPPLY_MINIMUM_NOT_MET = NotRankableReason.RECENT_SUPPLY_MINIMUM_NOT_MET
QUALITY_UNAVAILABLE = NotRankableReason.QUALITY_UNAVAILABLE
NO_VALID_LEAVE_ONE_OUT_REFERENCE = NotRankableReason.NO_VALID_LEAVE_ONE_OUT_REFERENCE
FIELD_REFERENCE_SUPPORT_INSUFFICIENT = (
    NotRankableReason.FIELD_REFERENCE_SUPPORT_INSUFFICIENT
)
RUN_BELOW_STRONG_REFERENCE = ProvisionalReason.RUN_BELOW_STRONG_REFERENCE
INCOMPLETE_BREADTH_FALLBACK = ProvisionalReason.INCOMPLETE_BREADTH_FALLBACK
COVERAGE_BELOW_STRONG = ProvisionalReason.COVERAGE_BELOW_STRONG
NOT_RANKABLE_STATE = PreSensitivityRankabilityState.NOT_RANKABLE
PROVISIONAL_STATE = PreSensitivityRankabilityState.PROVISIONAL
RANKABLE_STATE = PreSensitivityRankabilityState.RANKABLE
SUFFICIENT_EVIDENCE = PreSensitivityEvidenceState.SUFFICIENT
PROVISIONAL_ONLY_EVIDENCE = PreSensitivityEvidenceState.PROVISIONAL_ONLY
INSUFFICIENT_EVIDENCE = PreSensitivityEvidenceState.INSUFFICIENT

#: No sensitivity policy weight, top-k stability, or rank displacement exists in
#: this chunk's surface (plan §2 "Explicitly out of scope"; LREQ-SEN-030 is only a
#: supporting contract here).
NO_SENSITIVITY_INPUTS: tuple[str, ...] = (
    "sensitivity_policy",
    "policy_weights",
)

# ---------------------------------------------------------------------------
# Local construction helpers (inputs only; expectations come from the fixture)
# ---------------------------------------------------------------------------


def _inputs_for(count: int) -> tuple[object, ...]:
    """Build ``count`` clean ``PreSensitivityCategoryInput`` facts."""
    return tuple(efx.make_pre_sensitivity_input(f"c-{index}") for index in range(count))


def _clean_score(**overrides: object) -> object:
    """Build the fully available four-component ``ScoreResult``."""
    return efx.make_score_result(**overrides)


def _evaluate(
    score: object,
    evidence: object,
    *,
    run_category_count: int,
    identity_preflight_status: object = IdentityPreflightStatus.PASSED,
) -> object:
    """Call ``evaluate_pre_sensitivity_evidence`` with explicit facts."""
    return scoring.evaluate_pre_sensitivity_evidence(
        score,
        evidence,
        identity_preflight_status=identity_preflight_status,
        run_category_count=run_category_count,
    )


def _reason_values(reasons: object) -> tuple[str, ...]:
    """Return the emitted reasons as their plain string values, in order."""
    return tuple(reason.value for reason in reasons)


def _full_run(
    *,
    demand_none_category: str | None = None,
    count: int = STRONG_REFERENCE_CATEGORY_COUNT,
) -> tuple[tuple, tuple, tuple]:
    """Build ``(all_metrics, inputs, scores)`` for a fully verified run."""
    metrics = efx.all_verified_run_metrics(count)
    inputs = tuple(
        efx.make_pre_sensitivity_input(metric.category) for metric in metrics
    )
    scores = tuple(
        efx.make_score_result(
            component_d=(None if metric.category == demand_none_category else 0.5)
        )
        for metric in metrics
    )
    return metrics, inputs, scores


# ---------------------------------------------------------------------------
# LREQ-EVD-010 — rankability states
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EVD-010")
def test_pre_sensitivity_rankability_state_vocabulary() -> None:
    """The three pre-sensitivity rankability states exist (SRS §9.1 LREQ-EVD-010).

    The vocabulary is ``not_rankable`` / ``provisional`` / ``rankable``; each
    member equals its frozen string value. The evidence-state vocabulary is the
    distinct LREQ-EVD-010 companion: ``sufficient`` / ``provisional_only`` /
    ``insufficient`` (plan §12 Q2).
    """
    assert {state.value for state in PreSensitivityRankabilityState} == {
        "not_rankable",
        "provisional",
        "rankable",
    }
    assert {state.value for state in PreSensitivityEvidenceState} == {
        "sufficient",
        "provisional_only",
        "insufficient",
    }
    assert tuple(
        state.value for state in scoring.PRE_SENSITIVITY_RANKABILITY_STATES
    ) == ("not_rankable", "provisional", "rankable")


@pytest.mark.lreq("LREQ-EVD-010")
def test_pre_sensitivity_rankability_state_precedence() -> None:
    """``NOT_RANKABLE`` wins over ``base_rankable`` and over ``provisional``.

    SRS §9.1 LREQ-EVD-010 with plan §5.1: ``NOT_RANKABLE`` when any
    ``not_rankable`` reason is present; else ``RANKABLE`` only when the category
    is a base candidate and no provisional reason fires; else ``PROVISIONAL``.
    The fixture table covers every present/absent combination.
    """
    none: tuple[NotRankableReason, ...] = ()
    provisional_none: tuple[ProvisionalReason, ...] = ()
    one_not_rankable: tuple[NotRankableReason, ...] = (
        NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE,
    )
    one_provisional: tuple[ProvisionalReason, ...] = (
        ProvisionalReason.RUN_BELOW_STRONG_REFERENCE,
    )
    for (
        not_present,
        provisional_present,
        base_rankable,
        expected,
    ) in efx.PRE_SENSITIVITY_STATE_VECTORS:
        result = scoring.pre_sensitivity_rankability_state(
            one_not_rankable if not_present else none,
            one_provisional if provisional_present else provisional_none,
            base_rankable=base_rankable,
        )
        assert result.value == expected, (
            not_present,
            provisional_present,
            base_rankable,
        )


@pytest.mark.lreq("LREQ-EVD-010")
def test_pre_sensitivity_rankability_state_is_not_final_rankability_status() -> None:
    """The preliminary state is its own type, not ``models.RankabilityStatus``.

    Plan §5.1 R2: the preliminary state is a ``PreSensitivityRankabilityState``
    and never a ``models.RankabilityStatus``. The two vocabularies share string
    values, so type identity (not value equality) is the check.
    """
    state = scoring.pre_sensitivity_rankability_state((), (), base_rankable=True)
    assert isinstance(state, PreSensitivityRankabilityState)
    assert not isinstance(state, RankabilityStatus)
    assert PreSensitivityRankabilityState is not RankabilityStatus


# ---------------------------------------------------------------------------
# LREQ-EVD-020 — not-rankable reason matrix
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-TST-010")
def test_not_rankable_reason_matrix() -> None:
    """Every LREQ-EVD-020 clause emits exactly its reason (SRS §9.1 lines 980-993).

    ``efx.NOT_RANKABLE_MATRIX`` isolates one clause per row: request/page failure,
    unverified filter and category mismatch, unresolved/conflicting identity,
    preflight ``FAILED`` and ``INSUFFICIENT``, unavailable ``C``/``D``/``R``/``Q``,
    contradicted page views, no reference, and insufficient field support. Each row
    starts from the fully available score and clean facts so only the named clause
    can fire. LREQ-TST-010 coverage: normal (all-clean row), invalid
    (``reference_size = 0``), missing (``None`` components), explicit valid zero
    (a ``FieldUsableCounts`` value of ``0``), and the minimum boundary.
    """
    clean_result = _evaluate(
        _clean_score(),
        efx.make_pre_sensitivity_input("c-0"),
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert clean_result.not_rankable_reasons == ()
    assert clean_result.evidence_state is PreSensitivityEvidenceState.SUFFICIENT
    assert clean_result.rankability_state is PreSensitivityRankabilityState.RANKABLE
    assert clean_result.base_rankable is True

    for (
        label,
        score_overrides,
        evidence_overrides,
        preflight,
        expected,
    ) in efx.NOT_RANKABLE_MATRIX:
        score = efx.make_score_result(**score_overrides)
        evidence = efx.make_pre_sensitivity_input("c-0", **evidence_overrides)
        result = scoring.evaluate_pre_sensitivity_evidence(
            score,
            evidence,
            identity_preflight_status=preflight,
            run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
        )
        assert _reason_values(result.not_rankable_reasons) == expected, label
        assert result.base_rankable is False, label
        assert result.evidence_state is PreSensitivityEvidenceState.INSUFFICIENT, label
        assert (
            result.rankability_state is PreSensitivityRankabilityState.NOT_RANKABLE
        ), label


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_not_rankable_reason_order_is_deterministic() -> None:
    """Reason tuples follow the fixed emission order, not input order.

    SRS §3.3 LREQ-ARCH-030 with plan §5.1: several simultaneous conditions emit
    their reasons in ``NOT_RANKABLE_REASON_ORDER`` regardless of the order the
    facts are written. ``request_failed`` + ``component_d = None`` +
    ``reference_size = 0`` fires unrecoverable, demand, then reference; a second
    call with the same facts written in the opposite order returns byte-identical
    order.
    """
    score = efx.make_score_result(**efx.ORDER_VECTOR_SCORE_OVERRIDES)
    evidence = efx.make_pre_sensitivity_input(
        "c-0", **efx.ORDER_VECTOR_EVIDENCE_OVERRIDES
    )
    first = _reason_values(
        scoring.not_rankable_reasons(
            score,
            evidence,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
    )
    assert first == efx.ORDER_VECTOR_REASONS
    assert first == (
        NotRankableReason.UNRECOVERABLE_DATA_INTEGRITY_ERROR.value,
        NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE.value,
        NotRankableReason.NO_VALID_LEAVE_ONE_OUT_REFERENCE.value,
    )

    alternate = efx.make_pre_sensitivity_input(
        "c-0", **efx.ORDER_VECTOR_ALTERNATE_EVIDENCE_OVERRIDES
    )
    second = _reason_values(
        scoring.not_rankable_reasons(
            score,
            alternate,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
    )
    assert second == first

    full_vocabulary = tuple(
        reason.value for reason in scoring.NOT_RANKABLE_REASON_ORDER
    )
    assert full_vocabulary == efx.NOT_RANKABLE_REASON_EXPECTED_VALUES


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-EXT-090")
def test_discovery_filter_unverified_is_not_rankable() -> None:
    """An unverified filter or category mismatch is not rankable.

    SRS §4.1 LREQ-EXT-090 lines 279-281: a failed page, unverified filter,
    category mismatch, or material identity incompleteness prevents a fully
    rankable competition result. ``discovery_filter_verified = False`` and the
    ``filter_unverified`` / ``category_mismatch`` statuses all emit
    ``DISCOVERY_FILTER_UNVERIFIED`` exactly once, in order.
    """
    cases = (
        (
            {"discovery_filter_verified": False},
            DiscoveryStatus.COMPLETE,
            (NotRankableReason.DISCOVERY_FILTER_UNVERIFIED,),
        ),
        (
            {},
            DiscoveryStatus.FILTER_UNVERIFIED,
            (NotRankableReason.DISCOVERY_FILTER_UNVERIFIED,),
        ),
        (
            {},
            DiscoveryStatus.CATEGORY_MISMATCH,
            (NotRankableReason.DISCOVERY_FILTER_UNVERIFIED,),
        ),
    )
    for evidence_overrides, status, expected in cases:
        evidence = efx.make_pre_sensitivity_input(
            "c-0", discovery_status=status, **evidence_overrides
        )
        reasons = scoring.not_rankable_reasons(
            _clean_score(),
            evidence,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        assert reasons == expected

    verified = efx.make_pre_sensitivity_input("c-0")
    assert (
        scoring.not_rankable_reasons(
            _clean_score(),
            verified,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        == ()
    )


@pytest.mark.lreq("LREQ-EVD-020")
def test_unresolved_or_conflicting_identity_is_not_rankable() -> None:
    """Any surviving unresolved or conflicting identity is not rankable.

    SRS §9.1 LREQ-EVD-020 lines 981-982: "any unresolved or conflicting discovery
    identity remains in the category". The ``identity_incomplete`` status, an
    unresolved count of ``1``, and a conflict count of ``1`` each emit
    ``UNRESOLVED_OR_CONFLICTING_IDENTITY``; a clean category emits nothing.
    """
    cases = (
        {"discovery_status": DiscoveryStatus.IDENTITY_INCOMPLETE},
        {"discovery_unresolved_identity_count": 1},
        {"discovery_conflict_count": 1},
    )
    for overrides in cases:
        evidence = efx.make_pre_sensitivity_input("c-0", **overrides)
        reasons = scoring.not_rankable_reasons(
            _clean_score(),
            evidence,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        assert reasons == (NotRankableReason.UNRESOLVED_OR_CONFLICTING_IDENTITY,)
    clean = efx.make_pre_sensitivity_input("c-0")
    assert (
        scoring.not_rankable_reasons(
            _clean_score(),
            clean,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        == ()
    )


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-ID-040")
def test_identity_preflight_failure_is_not_rankable() -> None:
    """A failed run-level preflight makes the category not rankable.

    SRS §4.4 LREQ-ID-040 lines 386-390 with SRS §9.1 LREQ-EVD-020 line 985: the
    preflight failure is consumed as the run-level parameter and applied as the
    category reason. ``FAILED`` emits ``IDENTITY_PREFLIGHT_FAILED`` while the
    distinct run-level value stays an input fact; a ``PASSED`` preflight with
    otherwise clean facts emits nothing.
    """
    evidence = efx.make_pre_sensitivity_input("c-0")
    assert scoring.not_rankable_reasons(
        _clean_score(),
        evidence,
        identity_preflight_status=IdentityPreflightStatus.FAILED,
    ) == (NotRankableReason.IDENTITY_PREFLIGHT_FAILED,)
    assert (
        scoring.not_rankable_reasons(
            _clean_score(),
            evidence,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        == ()
    )
    # Run status and category not-rankability stay separate facts (plan §8).
    assert IdentityPreflightStatus.FAILED is not IdentityPreflightStatus.PASSED


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-ID-040")
def test_identity_preflight_insufficient_is_not_rankable() -> None:
    """``INSUFFICIENT`` is treated as a preflight failure for the category.

    Plan §12 Q4 resolution with SRS §9.1 LREQ-EVD-020 line 985: a preflight that
    cannot establish identity reliability cannot make any category rankable, so
    ``INSUFFICIENT`` emits ``IDENTITY_PREFLIGHT_FAILED`` exactly as ``FAILED``
    does, with no separate reason code for the distinct run-level value.
    """
    evidence = efx.make_pre_sensitivity_input("c-0")
    assert scoring.not_rankable_reasons(
        _clean_score(),
        evidence,
        identity_preflight_status=IdentityPreflightStatus.INSUFFICIENT,
    ) == (NotRankableReason.IDENTITY_PREFLIGHT_FAILED,)
    failed = scoring.not_rankable_reasons(
        _clean_score(),
        evidence,
        identity_preflight_status=IdentityPreflightStatus.FAILED,
    )
    insufficient = scoring.not_rankable_reasons(
        _clean_score(),
        evidence,
        identity_preflight_status=IdentityPreflightStatus.INSUFFICIENT,
    )
    assert failed == insufficient


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-TST-010")
def test_field_reference_support_requires_consumed_fields() -> None:
    """Field-specific support is required only for available components' fields.

    Plan §12 Q1/R11 with SRS §9.1 LREQ-EVD-020 line 993 and §8.2: Demand consumes
    ``demand_per_asset_raw``/``demand_median_raw``, Competition ``breadth_raw``,
    Recent supply ``recent_share_raw``/``median_age_raw``, Quality ``quality_raw``.
    For an available component, **every** consumed field must have at least one
    usable peer; an unavailable component contributes no requirement, so an unused
    ``0`` field never fails, and the all-four-unavailable case is vacuously
    ``True``. A ``0`` here is a legitimate count, not a missing value
    (LREQ-TST-010 explicit valid zero).
    """
    for (
        label,
        counts_kwargs,
        availability,
        expected,
    ) in efx.FIELD_REFERENCE_SUPPORT_VECTORS:
        counts = efx.make_field_usable_counts(**counts_kwargs)
        assert (
            scoring.field_reference_support_passes(counts, **availability) is expected
        ), label

    # Cross-check through ``not_rankable_reasons``: with ``D`` available, one of
    # its consumed fields at 0 usable peers fails the strict rule, so the reason
    # fires exactly once and the category cannot be a base candidate.
    evidence = efx.make_pre_sensitivity_input(
        "c-0",
        field_usable_counts=efx.make_field_usable_counts(
            demand_per_asset_raw=1,
            demand_median_raw=0,
            breadth_raw=1,
            recent_share_raw=1,
            median_age_raw=1,
            quality_raw=1,
        ),
    )
    result = _evaluate(
        _clean_score(),
        evidence,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.not_rankable_reasons == (
        NotRankableReason.FIELD_REFERENCE_SUPPORT_INSUFFICIENT,
    )
    assert result.base_rankable is False


@pytest.mark.lreq("LREQ-EVD-020")
def test_required_demand_unavailable_is_not_rankable() -> None:
    """A ``None`` demand component emits only ``REQUIRED_DEMAND_DATA_UNAVAILABLE``.

    SRS §9.1 LREQ-EVD-020 line 982: "required demand data is unavailable". The
    other three components stay available and their fields stay usable, so no
    other reason fires; a ``None`` component is never read as ``0.0``.
    """
    score = efx.make_score_result(component_d=None)
    result = _evaluate(
        score,
        efx.make_pre_sensitivity_input("c-0"),
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.not_rankable_reasons == (
        NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE,
    )
    assert score.component_d is None
    assert score.component_c is not None
    assert score.component_r is not None
    assert score.component_q is not None


@pytest.mark.lreq("LREQ-EVD-020")
def test_recent_supply_minimum_not_met_is_not_rankable() -> None:
    """A ``None`` recent-supply component emits ``RECENT_SUPPLY_MINIMUM_NOT_MET``.

    SRS §9.1 LREQ-EVD-020 line 982: "recent-supply minimum evidence is not met".
    Chunk 8 already returns ``None`` for coverage below
    ``MIN_REQUIRED_COMPONENT_COVERAGE``, so this clause reads the component.
    """
    score = efx.make_score_result(component_r=None)
    result = _evaluate(
        score,
        efx.make_pre_sensitivity_input("c-0"),
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.not_rankable_reasons == (
        NotRankableReason.RECENT_SUPPLY_MINIMUM_NOT_MET,
    )


@pytest.mark.lreq("LREQ-EVD-020")
def test_quality_unavailable_is_not_rankable() -> None:
    """A ``None`` quality component emits ``QUALITY_UNAVAILABLE``.

    SRS §9.1 LREQ-EVD-020 line 983: "quality is unavailable under the
    required-component policy".
    """
    score = efx.make_score_result(component_q=None)
    result = _evaluate(
        score,
        efx.make_pre_sensitivity_input("c-0"),
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.not_rankable_reasons == (NotRankableReason.QUALITY_UNAVAILABLE,)


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-SCR-050")
def test_page_view_semantics_contradicted_is_not_rankable() -> None:
    """Contradicted page views are not rankable (SRS §8.2 LREQ-SCR-050).

    Line 949: contradicted semantics make ``D`` and ``Q`` unavailable and the
    category not rankable, while ``C`` and ``R`` may remain. The real Chunk 8
    component replacement is imitated by passing ``component_d = None`` and
    ``component_q = None``; the status itself emits
    ``PAGE_VIEW_SEMANTICS_CONTRADICTED``, and the deduped reason tuple is the
    fixed order at the status's position (before the component reasons).
    """
    evidence = efx.make_pre_sensitivity_input(
        "c-0", page_view_semantics_status=PageViewSemanticsStatus.CONTRADICTED
    )
    score = efx.make_score_result(component_d=None, component_q=None)
    result = _evaluate(
        score,
        evidence,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert _reason_values(result.not_rankable_reasons) == (
        "page_view_semantics_contradicted",
        "required_demand_data_unavailable",
        "quality_unavailable",
    )
    # C and R stay available, as LREQ-SCR-050 allows.
    assert score.component_c is not None
    assert score.component_r is not None

    contradicted_only = efx.make_score_result()
    status_result = _evaluate(
        contradicted_only,
        evidence,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert status_result.not_rankable_reasons == (
        NotRankableReason.PAGE_VIEW_SEMANTICS_CONTRADICTED,
    )


@pytest.mark.lreq("LREQ-EVD-020")
def test_no_valid_leave_one_out_reference_is_not_rankable() -> None:
    """``reference_size = 0`` emits ``NO_VALID_LEAVE_ONE_OUT_REFERENCE``.

    SRS §9.1 LREQ-EVD-020 line 985: "no valid leave-one-out reference exists".
    A one-category run has ``reference_size == 0``; a positive reference is fine.
    ``reference_size`` is a fact supplied explicitly, never re-derived here.
    """
    no_reference = efx.make_pre_sensitivity_input("c-0", reference_size=0)
    assert scoring.not_rankable_reasons(
        _clean_score(),
        no_reference,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    ) == (NotRankableReason.NO_VALID_LEAVE_ONE_OUT_REFERENCE,)

    has_reference = efx.make_pre_sensitivity_input("c-0", reference_size=1)
    assert (
        scoring.not_rankable_reasons(
            _clean_score(),
            has_reference,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        == ()
    )


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-EXT-050")
def test_unrecoverable_data_integrity_error_is_not_rankable() -> None:
    """``request_failed`` and ``page_failed`` are unrecoverable integrity errors.

    SRS §4.1 LREQ-EXT-050 line 263 with SRS §9.1 LREQ-EVD-020 line 985-986: a
    failed page is never interpreted as zero assets, and the category carries an
    unrecoverable data-integrity error. ``truncated`` is a distinct discovery
    status and is not itself an integrity error; its all-four-components
    compatibility is asserted separately.
    """
    for status in (DiscoveryStatus.REQUEST_FAILED, DiscoveryStatus.PAGE_FAILED):
        evidence = efx.make_pre_sensitivity_input("c-0", discovery_status=status)
        assert scoring.not_rankable_reasons(
            _clean_score(),
            evidence,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        ) == (NotRankableReason.UNRECOVERABLE_DATA_INTEGRITY_ERROR,)

    truncated = efx.make_pre_sensitivity_input(
        "c-0", discovery_status=DiscoveryStatus.TRUNCATED
    )
    assert (
        scoring.not_rankable_reasons(
            _clean_score(),
            truncated,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        == ()
    )


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-MET-070")
def test_competition_unbounded_or_material_failure_is_not_rankable() -> None:
    """An unavailable competition component is the unbounded/material failure.

    SRS §7.3 LREQ-MET-070 lines 764-766: competition is unavailable when
    filtering is unverified, a material page failed, identity incompleteness makes
    breadth an unbounded lower bound, or the fallback breadth cannot be bounded.
    The pure-layer expression is ``score.competition is None``; a negative breadth
    signal would be an invalid input and is never a "bounded" alternative. An
    available ``C`` with verified+complete breadth is not this reason.
    """
    unavailable = efx.make_score_result(component_c=None)
    assert scoring.not_rankable_reasons(
        unavailable,
        efx.make_pre_sensitivity_input("c-0"),
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    ) == (NotRankableReason.COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE,)

    available = efx.make_score_result(component_c=0.5)
    assert (
        scoring.not_rankable_reasons(
            available,
            efx.make_pre_sensitivity_input("c-0"),
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        == ()
    )


# ---------------------------------------------------------------------------
# LREQ-EVD-020 — base candidate set construction
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-TST-060")
def test_base_rankable_candidates_require_strong_reference_count() -> None:
    """A clean 21-category run yields every category as a base candidate.

    SRS §9.1 LREQ-EVD-020 lines 989-994: a base-rankable candidate requires at
    least ``STRONG_REFERENCE_CATEGORY_COUNT = 21`` categories in the run, all four
    components, coverage ``>= MIN_REQUIRED_COMPONENT_COVERAGE = 0.50``, a valid
    reference, and field support. A fully verified 21-category run has no
    ``not_rankable`` and no provisional reason, so every category is rankable and
    the candidate tuple is ``("c-0", ..., "c-20")`` in ``all_metrics`` order.
    """
    metrics, inputs, scores = _full_run()
    result = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert isinstance(result, BaseCandidateSet)
    assert result.run_category_count == STRONG_REFERENCE_CATEGORY_COUNT
    assert result.base_rankable_candidates == efx.CATEGORY_ORDER_FULL_RUN
    assert result.base_rankable_candidates == tuple(
        metric.category for metric in metrics
    )
    assert all(decision.base_rankable for decision in result.decisions)
    assert all(
        decision.rankability_state is PreSensitivityRankabilityState.RANKABLE
        for decision in result.decisions
    )
    assert [decision.category for decision in result.decisions] == list(
        efx.CATEGORY_ORDER_FULL_RUN
    )


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-TST-060")
def test_base_rankable_candidates_empty_for_eight_to_twenty_run() -> None:
    """Runs of 8 and 20 categories have an empty base candidate set.

    SRS §9.1 LREQ-EVD-020 lines 990-991 require at least 21 categories for base
    candidacy; SRS §9.1 LREQ-EVD-040 line 1008 forbids labeling an 8-20 category
    run ``rankable``. Both runs yield ``base_rankable_candidates == ()`` and every
    decision provisional.
    """
    for count in (efx.EIGHT_CATEGORY_COUNT, efx.TWENTY_CATEGORY_COUNT):
        metrics, inputs, scores = _full_run(count=count)
        result = scoring.build_base_rankable_candidates(
            metrics,
            inputs,
            scores,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )
        assert result.run_category_count == count
        assert result.base_rankable_candidates == ()
        assert all(not decision.base_rankable for decision in result.decisions)
        assert all(
            decision.rankability_state is PreSensitivityRankabilityState.PROVISIONAL
            for decision in result.decisions
        )
        assert all(
            decision.provisional_reasons
            == (ProvisionalReason.RUN_BELOW_STRONG_REFERENCE,)
            for decision in result.decisions
        )


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_base_rankable_candidates_preserve_all_metrics_order() -> None:
    """Candidates follow the caller's ``all_metrics`` order, not value order.

    Plan §5.1 R3 with SRS §3.3 LREQ-ARCH-030: ``all_metrics`` is the ordering
    authority; ``base_rankable_candidates`` and ``decisions`` follow it. A reverse
    order produces exactly the reversed candidate tuple, so no set/dict iteration
    can be the source of the order.
    """
    metrics, inputs, scores = _full_run()
    forward = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert forward.base_rankable_candidates == efx.CATEGORY_ORDER_FULL_RUN

    reversed_metrics = tuple(reversed(metrics))
    reversed_inputs = tuple(reversed(inputs))
    reversed_scores = tuple(reversed(scores))
    backward = scoring.build_base_rankable_candidates(
        reversed_metrics,
        reversed_inputs,
        reversed_scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert backward.base_rankable_candidates == tuple(
        reversed(efx.CATEGORY_ORDER_FULL_RUN)
    )
    assert [decision.category for decision in backward.decisions] == list(
        backward.base_rankable_candidates
    )


@pytest.mark.lreq("LREQ-EVD-020")
def test_base_rankable_candidates_require_all_components_and_coverage() -> None:
    """Base candidacy needs all four components and minimum coverage.

    SRS §9.1 LREQ-EVD-020 lines 991-993: "all four components are available,
    every required stratum eligibility coverage meets
    ``MIN_REQUIRED_COMPONENT_COVERAGE``". A single ``None`` component, or any
    coverage below ``0.50``, removes exactly that category from the candidate set
    while leaving the other 20 intact.
    """
    metrics, inputs, scores = _full_run()
    baseline = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert baseline.base_rankable_candidates == efx.CATEGORY_ORDER_FULL_RUN

    # One missing component.
    missing = efx.make_score_result(component_c=None)
    scores_with_missing = (scores[0], missing) + scores[2:]
    missing_run = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores_with_missing,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    expected_missing = ("c-0",) + efx.CATEGORY_ORDER_FULL_RUN[2:]
    assert missing_run.base_rankable_candidates == expected_missing

    # One coverage below the required minimum on a sample-derived component.
    # Replace the entry at index 1 in place so the sequences stay aligned with
    # ``metrics`` (c-1 stays c-1).
    low_coverage_inputs = (
        inputs[:1]
        + (
            efx.make_pre_sensitivity_input(
                "c-1", recent_supply_stratum_eligibility_coverage=0.49
            ),
        )
        + inputs[2:]
    )
    low_coverage_run = scoring.build_base_rankable_candidates(
        metrics,
        low_coverage_inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    expected_low_coverage = (
        efx.CATEGORY_ORDER_FULL_RUN[0],
    ) + efx.CATEGORY_ORDER_FULL_RUN[2:]
    assert low_coverage_run.base_rankable_candidates == expected_low_coverage

    # Coverage exactly at the required minimum keeps candidacy (boundary). The
    # 0.50 coverage still fires the provisional COVERAGE_BELOW_STRONG reason, but
    # base candidacy is a separate necessary condition and is unaffected.
    boundary_inputs = (
        inputs[:1]
        + (
            efx.make_pre_sensitivity_input(
                "c-1", recent_supply_stratum_eligibility_coverage=0.50
            ),
        )
        + inputs[2:]
    )
    boundary_run = scoring.build_base_rankable_candidates(
        metrics,
        boundary_inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert boundary_run.base_rankable_candidates == efx.CATEGORY_ORDER_FULL_RUN


@pytest.mark.lreq("LREQ-EVD-020")
def test_base_candidate_construction_does_not_change_score_fields() -> None:
    """Excluding a category never mutates its stored score fields.

    Gate bullet 3 with SRS §9.1 LREQ-EVD-020 line 994: categories with
    insufficient support are excluded from the candidate set without changing
    their stored score fields. ``ScoreResult`` is frozen and is read only, so the
    input tuple, every field, and every score value are identical before and
    after the call.
    """
    category = efx.MIXED_RUN_DEMAND_NONE_CATEGORY
    metrics, inputs, scores = _full_run(demand_none_category=category)
    before = tuple(scores)
    before_fields = tuple(
        (
            score.market_opportunity_score,
            score.score_state,
            score.component_d,
            score.component_c,
            score.component_r,
            score.component_q,
            score.available_component_count,
            score.rankability_status,
            score.evidence_grade,
        )
        for score in scores
    )

    result = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )

    assert tuple(scores) == before
    after_fields = tuple(
        (
            score.market_opportunity_score,
            score.score_state,
            score.component_d,
            score.component_c,
            score.component_r,
            score.component_q,
            score.available_component_count,
            score.rankability_status,
            score.evidence_grade,
        )
        for score in scores
    )
    assert after_fields == before_fields
    assert category not in result.base_rankable_candidates
    assert len(result.base_rankable_candidates) == STRONG_REFERENCE_CATEGORY_COUNT - 1
    excluded = next(
        decision for decision in result.decisions if decision.category == category
    )
    assert excluded.not_rankable_reasons == (
        NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE,
    )
    assert excluded.rankability_state is PreSensitivityRankabilityState.NOT_RANKABLE


@pytest.mark.lreq("LREQ-EVD-020")
def test_build_base_rankable_candidates_rejects_misaligned_inputs() -> None:
    """Length/category misalignment raises ``ValueError``.

    Plan §5.1: the function raises ``ValueError`` when the three sequences differ
    in length or a category at an index does not match across them. A caller
    breach is an error, never a silently dropped or reordered category.
    """
    metrics, inputs, scores = _full_run()
    for label, count in efx.MISALIGNED_INPUT_VECTORS:
        if "inputs" in label:
            bad_inputs = inputs[:-1]
            bad_scores = scores
            assert len(bad_inputs) == count - 1
        else:
            bad_inputs = inputs
            bad_scores = scores[:-1]
            assert len(bad_scores) == count - 1
        with pytest.raises(ValueError):
            scoring.build_base_rankable_candidates(
                metrics,
                bad_inputs,
                bad_scores,
                identity_preflight_status=IdentityPreflightStatus.PASSED,
            )

    mismatched_inputs = (efx.make_pre_sensitivity_input("wrong-category"),) + inputs[1:]
    with pytest.raises(ValueError):
        scoring.build_base_rankable_candidates(
            metrics,
            mismatched_inputs,
            scores,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
        )

    # Scores carry no category field, so only length and the inputs' categories
    # can be mismatched; a same-length clean score tuple is accepted.
    same_length_scores = tuple(
        efx.make_score_result(market_opportunity_score=0.25) for _ in metrics
    )
    result = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        same_length_scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert result.base_rankable_candidates == efx.CATEGORY_ORDER_FULL_RUN


@pytest.mark.lreq("LREQ-EVD-020")
def test_score_state_and_rankability_state_remain_distinct() -> None:
    """``score_state`` and the pre-sensitivity rankability state are separate.

    Gate bullet 2: score state, pre-sensitivity evidence state, and preliminary
    rankability status remain distinct. A ``PARTIAL`` score can be ``PROVISIONAL``
    and an ``AVAILABLE`` score can be ``NOT_RANKABLE``; their value sets are
    disjoint.
    """
    for (
        label,
        score_state,
        expected_rankability_state,
    ) in efx.SCORE_STATE_DISTINCTNESS_VECTORS:
        if expected_rankability_state == "not_rankable":
            # AVAILABLE score but not rankable: D is unavailable as a fact.
            score = efx.make_score_result(
                score_state=score_state,
                component_d=None,
                available_component_count=3,
            )
            evidence = efx.make_pre_sensitivity_input("c-0")
            run_category_count = STRONG_REFERENCE_CATEGORY_COUNT
        else:
            # PARTIAL score, provisional rankability: the 8-category run makes
            # RUN_BELOW_STRONG_REFERENCE fire, so the state is provisional and the
            # category is not a base candidate (fewer than 21 categories).
            score = efx.make_score_result(
                score_state=score_state,
                available_component_count=4,
            )
            evidence = efx.make_pre_sensitivity_input("c-0", reference_size=7)
            run_category_count = efx.EIGHT_CATEGORY_COUNT
        result = _evaluate(
            score,
            evidence,
            identity_preflight_status=IdentityPreflightStatus.PASSED,
            run_category_count=run_category_count,
        )
        assert score.score_state is score_state, label
        assert result.rankability_state.value == expected_rankability_state, label
        if expected_rankability_state == "provisional":
            assert result.base_rankable is False, label

    score_values = {state.value for state in ScoreState}
    rankability_values = {state.value for state in PreSensitivityRankabilityState}
    assert score_values == {"available", "partial", "unavailable"}
    assert rankability_values == {"not_rankable", "provisional", "rankable"}
    assert score_values & rankability_values == set()


# ---------------------------------------------------------------------------
# LREQ-EVD-030 — provisional reasons (pre-sensitivity half only)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EVD-030")
def test_provisional_reason_for_run_below_strong_reference() -> None:
    """A run below 21 categories fires ``RUN_BELOW_STRONG_REFERENCE``.

    SRS §9.1 LREQ-EVD-030 lines 996-998: a score is provisional when the run has
    8-20 categories or fewer than ``STRONG_REFERENCE_CATEGORY_COUNT`` categories.
    The 20-category run also fails base candidacy, because LREQ-EVD-020 lines
    990-991 require at least 21 categories for the base candidate set. A
    21-category run with the same clean facts fires nothing.
    """
    below = _evaluate(
        _clean_score(),
        efx.make_pre_sensitivity_input("c-0"),
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT - 1,
    )
    assert below.provisional_reasons == (ProvisionalReason.RUN_BELOW_STRONG_REFERENCE,)
    assert below.evidence_state is PreSensitivityEvidenceState.PROVISIONAL_ONLY
    assert below.rankability_state is PreSensitivityRankabilityState.PROVISIONAL
    assert below.base_rankable is False

    at_strong = _evaluate(
        _clean_score(),
        efx.make_pre_sensitivity_input("c-0"),
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert at_strong.provisional_reasons == ()
    assert at_strong.evidence_state is PreSensitivityEvidenceState.SUFFICIENT
    assert at_strong.rankability_state is PreSensitivityRankabilityState.RANKABLE


@pytest.mark.lreq("LREQ-EVD-030")
@pytest.mark.lreq("LREQ-MET-070")
def test_provisional_reason_for_incomplete_breadth_fallback() -> None:
    """The incomplete fallback estimate always fires ``INCOMPLETE_BREADTH_FALLBACK``.

    SRS §7.3 LREQ-MET-070 lines 757-759: a category using the fallback breadth
    cannot be ``rankable`` and may be ``provisional`` only when all other required
    evidence passes. SRS §9.1 LREQ-EVD-030 line 998 names "breadth uses the
    incomplete fallback estimate". All other facts are clean, so only this reason
    fires and the state is provisional.
    """
    evidence = efx.make_pre_sensitivity_input(
        "c-0", **efx.PROVISIONAL_BREADTH_FALLBACK_OVERRIDES
    )
    result = _evaluate(
        _clean_score(),
        evidence,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.provisional_reasons == (
        ProvisionalReason.INCOMPLETE_BREADTH_FALLBACK,
    )
    assert result.not_rankable_reasons == ()
    assert result.evidence_state is PreSensitivityEvidenceState.PROVISIONAL_ONLY
    assert result.rankability_state is PreSensitivityRankabilityState.PROVISIONAL


@pytest.mark.lreq("LREQ-EVD-030")
def test_bounded_by_verified_total_does_not_force_provisional() -> None:
    """Verified complete breadth bounded by a verified total fires nothing.

    SRS §9.1 LREQ-EVD-030 lines 1000-1001: "Discovery bounded by a verified total
    is sufficient for rankability and SHALL not by itself force a provisional
    status." A verified, complete, bounded category has no provisional reason.
    """
    evidence = efx.make_pre_sensitivity_input(
        "c-0",
        breadth_source=BreadthSource.VERIFIED_TOTAL_COUNT,
        breadth_completeness_status=BreadthCompletenessStatus.COMPLETE,
        discovery_bounded_by_verified_total=True,
    )
    result = _evaluate(
        _clean_score(),
        evidence,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.provisional_reasons == ()
    assert result.rankability_state is PreSensitivityRankabilityState.RANKABLE
    assert result.base_rankable is True


@pytest.mark.lreq("LREQ-EVD-030")
@pytest.mark.lreq("LREQ-MET-070")
def test_incomplete_breadth_fallback_with_verified_total_is_provisional() -> None:
    """The fallback provisional reason survives a verified-total bound (Q3).

    Plan §12 Q3 with SRS §7.3 LREQ-MET-070 lines 757-759: the provisional reason
    is about the fallback *estimate* itself, so it fires whenever
    ``breadth_completeness_status is INCOMPLETE_ESTIMATE``, including when
    ``discovery_bounded_by_verified_total`` is ``True``. Bounded-by-verified-total
    does not by itself make the category not rankable, so no ``not_rankable``
    reason fires.
    """
    evidence = efx.make_pre_sensitivity_input(
        "c-0",
        breadth_completeness_status=BreadthCompletenessStatus.INCOMPLETE_ESTIMATE,
        discovery_bounded_by_verified_total=True,
    )
    result = _evaluate(
        _clean_score(),
        evidence,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert result.not_rankable_reasons == ()
    assert result.provisional_reasons == (
        ProvisionalReason.INCOMPLETE_BREADTH_FALLBACK,
    )
    assert result.rankability_state is PreSensitivityRankabilityState.PROVISIONAL


@pytest.mark.lreq("LREQ-EVD-030")
def test_provisional_reason_for_coverage_between_minimum_and_strong() -> None:
    """Coverage acceptable but below the strong policy fires ``COVERAGE_BELOW_STRONG``.

    SRS §9.1 LREQ-EVD-030 line 999: "stratum eligibility coverage is acceptable
    but below the strong policy". Acceptable means
    ``>= MIN_REQUIRED_COMPONENT_COVERAGE``; below the strong policy means
    ``< STRONG_COMPONENT_COVERAGE``. The boundary vectors: ``0.79`` fires it,
    ``0.80`` (exactly strong) does not, and ``0.50`` (exactly the required
    minimum, still "acceptable but below the strong policy") fires it while the
    component stays available. A coverage strictly below ``0.50`` is not a
    provisional reason at all -- that component is already unavailable and the
    category is not rankable earlier.
    """
    for label, coverage, expected in efx.PROVISIONAL_COVERAGE_VECTORS:
        evidence = efx.make_pre_sensitivity_input(
            "c-0", demand_stratum_eligibility_coverage=coverage
        )
        result = _evaluate(
            _clean_score(),
            evidence,
            run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
        )
        assert _reason_values(result.provisional_reasons) == expected, label
        if expected:
            assert (
                result.rankability_state is PreSensitivityRankabilityState.PROVISIONAL
            ), label
        else:
            assert (
                result.rankability_state is PreSensitivityRankabilityState.RANKABLE
            ), label

    below_minimum = efx.make_pre_sensitivity_input(
        "c-0", demand_stratum_eligibility_coverage=0.49
    )
    below_minimum_result = _evaluate(
        _clean_score(component_d=None),
        below_minimum,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert below_minimum_result.provisional_reasons == ()
    assert below_minimum_result.not_rankable_reasons == (
        NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE,
    )


@pytest.mark.lreq("LREQ-EVD-030")
@pytest.mark.lreq("LREQ-TST-060")
def test_eight_category_run_is_provisional_never_rankable() -> None:
    """An 8-category run is provisional, never rankable (SRS §9.1 LREQ-EVD-040).

    Lines 1003-1008: a category may be ``rankable`` only when the run contains at
    least 8 categories and the other conditions pass; a run with 8-20 categories
    SHALL never be labeled ``rankable``. The eight-category run scores (8 is the
    minimum) but yields an empty base candidate set and a provisional state.
    """
    metrics, inputs, scores = _full_run(count=efx.EIGHT_CATEGORY_COUNT)
    result = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert result.run_category_count == 8
    assert result.base_rankable_candidates == ()
    for decision in result.decisions:
        assert decision.provisional_reasons == (
            ProvisionalReason.RUN_BELOW_STRONG_REFERENCE,
        )
        assert not decision.base_rankable
        assert decision.rankability_state is PreSensitivityRankabilityState.PROVISIONAL
        assert decision.evidence_state is PreSensitivityEvidenceState.PROVISIONAL_ONLY


@pytest.mark.lreq("LREQ-EVD-030")
def test_pre_sensitivity_state_excludes_sensitivity_high_reason() -> None:
    """The pre-sensitivity provisional vocabulary has no ``sensitivity_high``.

    Plan §2 "Explicitly out of scope" and §5.1: the sensitivity-high clause of
    LREQ-EVD-030 belongs to Chunk 9B and is not a pre-sensitivity input. The
    vocabulary here is exactly ``run_below_strong_reference``,
    ``incomplete_breadth_fallback``, and ``coverage_below_strong``.
    """
    assert set(efx.PROVISIONAL_REASON_EXPECTED_VALUES) == {
        "run_below_strong_reference",
        "incomplete_breadth_fallback",
        "coverage_below_strong",
    }
    assert (
        tuple(reason.value for reason in ProvisionalReason)
        == efx.PROVISIONAL_REASON_EXPECTED_VALUES
    )
    assert not any("sensitivity" in reason.value for reason in ProvisionalReason)
    assert scoring.PROVISIONAL_REASON_ORDER == tuple(ProvisionalReason)
    # No sensitivity parameter exists anywhere on this chunk's callables.
    for name in efx.PRE_SENSITIVITY_FUNCTION_NAMES:
        annotation_text = inspect.getsource(getattr(scoring, name))
        assert "sensitivity" not in annotation_text.replace("_sensitivity", "").replace(
            "pre_sensitivity", ""
        ).replace("PreSensitivity", ""), name


# ---------------------------------------------------------------------------
# LREQ-SEN-030 — supporting contract
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-030")
def test_base_candidate_set_is_fixed_input_to_sensitivity() -> None:
    """The candidate set is fixed before any alternate policy is ranked.

    SRS §9.3 LREQ-SEN-030 lines 1093-1096 with plan §2: Chunk 9A supplies only the
    fixed candidate set and the pre-sensitivity rankability state the warning
    threshold is evaluated over. The set has no sensitivity parameter, and
    repeated construction from identical inputs returns an equal set, so no policy
    can have added or removed a candidate.
    """
    metrics, inputs, scores = _full_run()
    first = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    second = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert first == second
    assert len(first.base_rankable_candidates) == STRONG_REFERENCE_CATEGORY_COUNT
    signature = inspect.signature(scoring.build_base_rankable_candidates)
    assert set(signature.parameters) == {
        "all_metrics",
        "inputs",
        "scores",
        "identity_preflight_status",
        "min_required_component_coverage",
    }
    for unwanted in efx.NO_RANKABLE_SURFACE:
        assert not hasattr(scoring, unwanted), unwanted


# ---------------------------------------------------------------------------
# LREQ-NFR-040 / ARCH-010 / ARCH-020 / ARCH-030 — public contract
# ---------------------------------------------------------------------------

SCORING_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "niche_scout" / "scoring.py"
)


@pytest.mark.lreq("LREQ-NFR-040")
def test_scoring_evidence_public_functions_have_type_hints_and_docstrings() -> None:
    """Every Chunk 9A public function is annotated and documented (SRS §11).

    LREQ-NFR-040: public metric and scoring functions carry type hints plus a
    docstring describing null and edge-case behavior. A ``0``
    ``FieldUsableCounts`` value and a ``None`` component are the null/edge cases
    each function's docstring must state.
    """
    for name in efx.PRE_SENSITIVITY_FUNCTION_NAMES:
        function = getattr(scoring, name)
        assert function.__doc__, f"{name} must have a docstring"
        assert function.__annotations__, f"{name} must be annotated"
        assert "return" in function.__annotations__, f"{name} needs a return type"


@pytest.mark.lreq("LREQ-ARCH-010")
@pytest.mark.lreq("LREQ-ARCH-020")
def test_scoring_evidence_module_is_import_pure_and_clock_free() -> None:
    """``scoring.py`` keeps the SRS §3.3 purity boundary after Chunk 9A.

    LREQ-ARCH-010/-020: no collector, database, report, or CLI import, no network
    or file I/O, no clock read, and no randomness module. The structural checker
    and a direct AST scan both agree.
    """
    source = SCORING_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SCORING_PATH))
    assert check_module(SCORING_PATH) == [], (
        "scoring.py must not import an I/O, network, DB, CLI, or clock module "
        "and must not read the clock"
    )
    assert clock_violations(tree) == []
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported & FORBIDDEN_MODULES == set(), imported & FORBIDDEN_MODULES
    assert imported & {"random", "secrets", "uuid"} == set(), (
        "no randomness or platform-dependent identifiers (plan §11)"
    )


@pytest.mark.lreq("LREQ-ARCH-030")
def test_pre_sensitivity_outputs_are_deterministic() -> None:
    """Identical inputs give equal outputs (SRS §3.3 / LREQ-ARCH-030).

    The reason tuples, the decision tuple, the candidate tuple, and the state are
    all functions of explicit inputs with fixed emission and ``all_metrics``
    orders, so repeated calls compare equal. Reverse input order does not change
    any decision, only the output order.
    """
    metrics, inputs, scores = _full_run()
    first = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    second = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert first == second

    reversed_result = scoring.build_base_rankable_candidates(
        tuple(reversed(metrics)),
        tuple(reversed(inputs)),
        tuple(reversed(scores)),
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert reversed_result.base_rankable_candidates == tuple(
        reversed(first.base_rankable_candidates)
    )
    assert [decision.category for decision in reversed_result.decisions] == list(
        reversed([decision.category for decision in first.decisions])
    )


# ---------------------------------------------------------------------------
# LREQ-TST-010 — golden vectors
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-010")
@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-EVD-030")
def test_pre_sensitivity_golden_vectors() -> None:
    """The hand-derived end-to-end vectors from plan §9.

    Golden vector 1 (fully verified 21-category run): for a target, the
    leave-one-out reference size is ``21 - 1 = 20`` and every field count is
    ``20`` (SRS §8.1), so no ``not_rankable`` and no provisional reason fires and
    the state is ``rankable``. Golden vector 2 (fully verified 8-category run):
    ``8 - 1 = 7`` peers and run size ``8 < 21``, so exactly
    ``RUN_BELOW_STRONG_REFERENCE`` fires and the state is ``provisional``.

    The clean-category facts are asserted to be the ones the vectors describe, so
    a fixture drift cannot silently change the expectation.
    """
    clean = efx.make_pre_sensitivity_input("c-0")
    assert clean.reference_size == efx.FULL_RUN_REFERENCE_SIZE
    assert clean.reference_size == STRONG_REFERENCE_CATEGORY_COUNT - 1
    assert clean.field_usable_counts == efx.make_field_usable_counts(
        demand_per_asset_raw=20,
        demand_median_raw=20,
        breadth_raw=20,
        recent_share_raw=20,
        median_age_raw=20,
        quality_raw=20,
    )
    assert float(clean.demand_stratum_eligibility_coverage) >= 0.50

    full = _evaluate(
        _clean_score(),
        clean,
        run_category_count=STRONG_REFERENCE_CATEGORY_COUNT,
    )
    assert full.not_rankable_reasons == ()
    assert full.provisional_reasons == ()
    assert full.evidence_state is PreSensitivityEvidenceState.SUFFICIENT
    assert full.rankability_state is PreSensitivityRankabilityState.RANKABLE
    assert full.base_rankable is True

    eight_evidence = efx.make_pre_sensitivity_input(
        "c-0",
        reference_size=efx.EIGHT_CATEGORY_COUNT - 1,
        field_usable_counts=efx.make_field_usable_counts(
            demand_per_asset_raw=7,
            demand_median_raw=7,
            breadth_raw=7,
            recent_share_raw=7,
            median_age_raw=7,
            quality_raw=7,
        ),
    )
    eight = _evaluate(
        _clean_score(),
        eight_evidence,
        run_category_count=efx.EIGHT_CATEGORY_COUNT,
    )
    assert eight.not_rankable_reasons == ()
    assert eight.provisional_reasons == (ProvisionalReason.RUN_BELOW_STRONG_REFERENCE,)
    assert eight.evidence_state is PreSensitivityEvidenceState.PROVISIONAL_ONLY
    assert eight.rankability_state is PreSensitivityRankabilityState.PROVISIONAL
    assert eight.base_rankable is False

    # The strong-coverage constant used by the provisional policy is 0.80.
    assert STRONG_COMPONENT_COVERAGE == 0.80
