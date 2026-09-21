"""Chunk 9B analytical tests — sensitivity, final evidence, final rankability.

Every expected value is a fixture constant from
``tests/fixtures/sensitivity_fixtures.py`` (imported as ``sfx``), hand-derived
from SRS-lean.md §9.1 (LREQ-EVD-010/-030/-040), §9.2 (LREQ-EVD-050), §9.3
(LREQ-SEN-010/-020/-030/-040), with §8.1 (LREQ-NRM-020), §3.3
(LREQ-ARCH-010/-020/-030), §11 (LREQ-NFR-040), and §13
(LREQ-TST-010/-060/-070/-090), matching plan
``chunk-9B-sensitivity-final-evidence-and-final-rankability.md`` §9. No live
network, no credentials, no clock reads, and no randomness: every fact is an
explicit literal.

The module imports the Chunk 9B public surface from ``niche_scout.scoring``.
Before the implementation lands that import raises ``ImportError``, which is the
required missing-implementation shape for a test-author-first chunk: the test
file is syntactically valid and fails only because the implementation is
missing.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import fixtures.sensitivity_fixtures as sfx
import pytest

from niche_scout import scoring
from niche_scout.models import (
    MIN_CATEGORIES_PER_RUN,
    MIN_REQUIRED_COMPONENT_COVERAGE,
    SENSITIVITY_POLICIES,
    STRONG_COMPONENT_COVERAGE,
    STRONG_REFERENCE_CATEGORY_COUNT,
    W_C,
    W_D,
    W_Q,
    W_R,
    EvidenceGrade,
    RankabilityStatus,
)
from niche_scout.scoring import (
    CategorySensitivityRank,
    ComponentValues,
    FieldUsableCounts,
    NotRankableReason,
    PreSensitivityCategoryInput,
    PreSensitivityDecision,
    PreSensitivityEvidenceState,
    PreSensitivityRankabilityState,
    ProvisionalReason,
    SampleEvidenceFacts,
    SensitivityDiagnostics,
    balanced_composite,
    evaluate_sensitivity,
    final_evidence_grade,
    final_rankability_status,
    ranked_under_policy,
)
from niche_scout.tools.check_import_boundaries import (
    FORBIDDEN_MODULES,
    check_module,
    clock_violations,
)

# ---------------------------------------------------------------------------
# Fixture lookups and local construction helpers (inputs and lookups only;
# expectations come from the fixture tables)
# ---------------------------------------------------------------------------

SENSITIVITY_VECTORS_BY_LABEL: dict[str, dict[str, object]] = dict(
    sfx.SENSITIVITY_VECTORS
)

FINAL_RANKABILITY_VECTORS_BY_LABEL: dict[
    str, tuple[dict[str, object], bool | None, str]
] = {
    label: (overrides, warning, expected)
    for label, overrides, warning, expected in sfx.FINAL_RANKABILITY_VECTORS
}

SCORING_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "niche_scout" / "scoring.py"
)

#: The Chunk 9B public callables that must carry type hints and docstrings
#: (LREQ-NFR-040; plan §7).
SENSITIVITY_FUNCTION_NAMES: tuple[str, ...] = (
    "ranked_under_policy",
    "evaluate_sensitivity",
    "final_evidence_grade",
    "final_rankability_status",
)

#: The Chunk 9B public typed structures, docstring-checked with the callables.
SENSITIVITY_CLASS_NAMES: tuple[str, ...] = (
    "CategorySensitivityRank",
    "SensitivityDiagnostics",
    "SampleEvidenceFacts",
)


def _diagnostics(
    label: str,
) -> tuple[dict[str, object], object, tuple, tuple, SensitivityDiagnostics]:
    """Build one sensitivity case from a fixture vector and evaluate it.

    ``base_candidates`` is the frozen Chunk 9A candidate set (the fixture builder
    makes every category base-rankable), ``all_metrics``/``scores`` are aligned
    in the vector's canonical order, and ``reference_set_size`` is the explicit
    leave-one-out peer count of the run (R3).
    """
    vector = SENSITIVITY_VECTORS_BY_LABEL[label]
    components = vector["components"]
    base_candidates = sfx.make_candidate_set(
        tuple(components), vector["run_category_count"]
    )
    all_metrics, scores = sfx.make_metrics_and_scores(components)
    diagnostics = evaluate_sensitivity(
        base_candidates,
        all_metrics,
        scores,
        reference_set_size=vector["reference_set_size"],
    )
    return vector, base_candidates, all_metrics, scores, diagnostics


def _component_values(
    components: dict[str, tuple[float, float, float, float]],
) -> dict[str, ComponentValues]:
    """Map fixture ``(D, C, R, Q)`` tuples to ``ComponentValues`` literals."""
    return {
        category: ComponentValues(
            demand=demand,
            competition=competition,
            recent_supply=recent_supply,
            quality=quality,
        )
        for category, (
            demand,
            competition,
            recent_supply,
            quality,
        ) in components.items()
    }


def _ranked_categories(vector: dict[str, object], policy: str) -> list[str]:
    """Return one policy's rank order from the fixture's 1-based rank table."""
    ranks = vector["expected_ranks_by_policy"][policy]
    return [category for category, _ in sorted(ranks.items(), key=lambda item: item[1])]


def _evidence(**overrides: object) -> PreSensitivityCategoryInput:
    """Build the Chunk 9A evidence input from the base facts plus overrides.

    ``field_usable_counts`` is stored as a six-key mapping in the fixture; the
    test constructs the Chunk 9A ``FieldUsableCounts`` from it (fixture design
    note).
    """
    facts = dict(sfx.FINAL_EVIDENCE_BASE_EVIDENCE_KWARGS)
    facts.update(overrides)
    counts = facts.pop("field_usable_counts")
    return PreSensitivityCategoryInput(
        category="c-0",
        field_usable_counts=FieldUsableCounts(**counts),
        **facts,
    )


def _sample(**overrides: object) -> SampleEvidenceFacts:
    """Build the ``SampleEvidenceFacts`` from the base facts plus overrides."""
    facts = dict(sfx.FINAL_EVIDENCE_BASE_SAMPLE_KWARGS)
    facts.update(overrides)
    return SampleEvidenceFacts(category="c-0", **facts)


def _decision(**overrides: object) -> PreSensitivityDecision:
    """Build the Chunk 9A decision from the base facts plus overrides.

    The fixture stores enum-typed facts as their frozen string values; the test
    constructs the ``StrEnum`` members and reason tuples because the
    implementation distinguishes states by identity (fixture design note).
    """
    facts = dict(sfx.FINAL_EVIDENCE_BASE_DECISION_KWARGS)
    facts.update(overrides)
    return PreSensitivityDecision(
        category="c-0",
        evidence_state=PreSensitivityEvidenceState(facts["evidence_state"]),
        rankability_state=PreSensitivityRankabilityState(facts["rankability_state"]),
        not_rankable_reasons=tuple(
            NotRankableReason(reason) for reason in facts["not_rankable_reasons"]
        ),
        provisional_reasons=tuple(
            ProvisionalReason(reason) for reason in facts["provisional_reasons"]
        ),
        base_rankable=facts["base_rankable"],
    )


def _evidence_row(
    label: str,
) -> tuple[EvidenceGrade, SampleEvidenceFacts, dict[str, object], object]:
    """Evaluate one final-evidence fixture row; returns grade/sample/vector."""
    vector = sfx.FINAL_EVIDENCE_GRADE_VECTORS[label]
    sample = _sample(**vector["sample_overrides"])
    decision = _decision(**vector["decision_overrides"])
    grade = final_evidence_grade(
        _evidence(**vector["evidence_overrides"]),
        sample,
        decision,
        run_category_count=vector["run_category_count"],
        sensitivity_warning=vector["sensitivity_warning"],
    )
    return grade, sample, vector, decision


def _rankability(label: str) -> tuple[PreSensitivityDecision, bool | None, str]:
    """Build one final-rankability fixture row's decision, warning, expected."""
    overrides, warning, expected = FINAL_RANKABILITY_VECTORS_BY_LABEL[label]
    return _decision(**overrides), warning, expected


# ---------------------------------------------------------------------------
# LREQ-SEN-010 — fixed policies and weights
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-010")
def test_sensitivity_policy_vocabulary_and_weights() -> None:
    """The three fixed sensitivity policies and weights (SRS §9.3 LREQ-SEN-010).

    Lines 1060-1066 fix the policy weights; the fixture table is an independent
    transcription, so equality against it checks the vocabulary. Plan §5 fixes
    the evaluation order and the top-k order, and every policy's weights sum to
    1.0.
    """
    expected_weights = sfx.SENSITIVITY_POLICY_WEIGHTS
    assert set(SENSITIVITY_POLICIES) == set(expected_weights)
    assert tuple(SENSITIVITY_POLICIES) == sfx.SENSITIVITY_POLICY_ORDER_EXPECTED
    assert set(scoring.SENSITIVITY_POLICY_ORDER) == set(SENSITIVITY_POLICIES)
    for policy, weights in expected_weights.items():
        assert SENSITIVITY_POLICIES[policy] == weights, policy
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9), policy
    assert scoring.SENSITIVITY_POLICY_ORDER == sfx.SENSITIVITY_POLICY_ORDER_EXPECTED
    assert scoring.SENSITIVITY_TOP_K == sfx.SENSITIVITY_TOP_K_EXPECTED


@pytest.mark.lreq("LREQ-SEN-010")
@pytest.mark.lreq("LREQ-SCR-060")
def test_sensitivity_balanced_policy_equals_primary_weights() -> None:
    """The balanced policy is exactly the primary composite weights.

    SRS §8.3 / §9.3 LREQ-SCR-060 with plan §5.2 step 2: ``balanced`` uses
    ``models.W_D/W_C/W_R/W_Q`` (0.35/0.30/0.20/0.15), so the balanced
    recomputation equals the primary score. The three policies are pairwise
    distinct, so the balanced equality is not vacuous.
    """
    balanced = SENSITIVITY_POLICIES["balanced"]
    demand_heavy = SENSITIVITY_POLICIES["demand_heavy"]
    competition_heavy = SENSITIVITY_POLICIES["competition_heavy"]
    assert balanced == sfx.BALANCED_POLICY_WEIGHTS
    assert (balanced["D"], balanced["C"], balanced["R"], balanced["Q"]) == (
        W_D,
        W_C,
        W_R,
        W_Q,
    )
    assert balanced != demand_heavy
    assert balanced != competition_heavy
    assert demand_heavy != competition_heavy


# ---------------------------------------------------------------------------
# LREQ-SEN-020 — ranks, stability, displacements, typed diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-020")
def test_sensitivity_ranks_only_fixed_candidates() -> None:
    """Only the frozen ``base_rankable_candidates`` are ranked (SRS §9.3).

    LREQ-SEN-020 line 1077: categories outside the candidate set stay visible on
    their own rows but are excluded from the ranked set. A base candidate
    missing from ``all_metrics`` is a caller breach -> ``ValueError`` (plan §5.2
    step 1).
    """
    vector = SENSITIVITY_VECTORS_BY_LABEL["stable"]
    components = vector["components"]
    candidates = tuple(components)
    merged = dict(components)
    merged["n-1"] = (0.5, 0.5, 0.5, 0.5)
    merged["n-2"] = (0.5, 0.5, 0.5, 0.5)
    base = sfx.make_candidate_set(candidates, vector["run_category_count"])
    metrics, scores = sfx.make_metrics_and_scores(merged)
    diagnostics = evaluate_sensitivity(
        base,
        metrics,
        scores,
        reference_set_size=vector["reference_set_size"],
    )
    assert diagnostics.ranked_categories == candidates
    assert tuple(row.category for row in diagnostics.categories) == candidates
    assert "n-1" not in diagnostics.ranked_categories
    assert "n-2" not in diagnostics.ranked_categories

    dropped = dict(components)
    dropped.pop(candidates[-1])
    short_metrics, short_scores = sfx.make_metrics_and_scores(dropped)
    with pytest.raises(ValueError):
        evaluate_sensitivity(
            base,
            short_metrics,
            short_scores,
            reference_set_size=vector["reference_set_size"],
        )


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_sensitivity_deterministic_tie_break_by_category_path() -> None:
    """Ties break by ascending lexical category path (SRS §9.3 line 1074).

    The stable vector ties ``A`` and ``C`` at 0.60 under ``demand_heavy``; the
    fixture ranks break the tie ``A`` then ``C``. Reversing the candidate
    sequence changes nothing, so the order comes from the sort key
    ``(-score, category)`` and not from container iteration (LREQ-ARCH-030).
    """
    vector = SENSITIVITY_VECTORS_BY_LABEL["stable"]
    components = vector["components"]
    candidates = tuple(components)
    demand_scores = vector["expected_scores_by_policy"]["demand_heavy"]
    assert demand_scores["A"] == pytest.approx(demand_scores["C"], abs=1e-9)
    expected = _ranked_categories(vector, "demand_heavy")
    assert expected.index("A") < expected.index("C")
    component_map = _component_values(components)
    policy = SENSITIVITY_POLICIES["demand_heavy"]
    for ordered in (candidates, tuple(reversed(candidates))):
        ranked = ranked_under_policy(ordered, component_map, policy=policy)
        assert [category for category, _ in ranked] == expected


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-TST-070")
def test_sensitivity_top_k_stability() -> None:
    """Top-3/top-5 stability equals the policy top-k intersection (SRS §9.3).

    LREQ-SEN-020 lines 1082-1087 define
    ``|T_k,balanced ∩ T_k,demand ∩ T_k,competition| / k``. Each value is
    re-checked against the fixture rank tables; the stable vector sits exactly at
    the ``2/3`` boundary, the top-three vector at ``1/3``, and the displacement
    vector at ``2/3`` with ``0.8`` for k=5 (LREQ-TST-070).
    """
    for label in ("stable", "top_three", "displacement"):
        vector = SENSITIVITY_VECTORS_BY_LABEL[label]
        _, _, _, _, diagnostics = _diagnostics(label)
        for k, attribute, key in (
            (3, "top_3_stability", "expected_top_3_stability"),
            (5, "top_5_stability", "expected_top_5_stability"),
        ):
            actual = getattr(diagnostics, attribute)
            assert actual == pytest.approx(vector[key], abs=1e-9), (label, k)
            common = set(_ranked_categories(vector, "balanced")[:k])
            for policy in ("demand_heavy", "competition_heavy"):
                common &= set(_ranked_categories(vector, policy)[:k])
            assert actual == pytest.approx(len(common) / k, abs=1e-9), (label, k)


@pytest.mark.lreq("LREQ-SEN-020")
def test_sensitivity_top_k_null_when_too_few_candidates() -> None:
    """Fewer than ``k`` candidates yield null, never a padded value (SRS §9.3).

    LREQ-SEN-020 lines 1086-1087: two candidates give ``None`` for both top-k
    values while displacements stay computable; one candidate (the minimum
    boundary) behaves the same. The ranked tuple is never padded to 3 or 5
    entries.
    """
    for label in ("two_candidate", "one_candidate"):
        vector, _, _, _, diagnostics = _diagnostics(label)
        assert diagnostics.top_3_stability is None, label
        assert diagnostics.top_5_stability is None, label
        assert diagnostics.maximum_score_delta == pytest.approx(
            vector["expected_maximum_score_delta"], abs=1e-9
        ), label
        assert (
            diagnostics.maximum_rank_displacement
            == vector["expected_maximum_rank_displacement"]
        ), label
        assert diagnostics.ranked_categories == tuple(vector["components"]), label
        assert len(diagnostics.categories) == len(vector["components"]), label


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-TST-070")
def test_sensitivity_empty_candidate_set_null_outputs() -> None:
    """An empty candidate set yields explicit nulls (dependency-map §6.2/§6.3).

    SRS §9.3 LREQ-SEN-020 lines 1086-1087: the 8-category minimum run has no
    candidate, every stability/displacement/warning output is ``None``, and
    ``categories == ()``; the diagnostic still records ``reference_set_size``
    and ``displacement_threshold`` so the empty status is explicit.
    """
    vector, base, _, _, diagnostics = _diagnostics("zero_candidate")
    assert vector["run_category_count"] == MIN_CATEGORIES_PER_RUN
    assert base.base_rankable_candidates == ()
    assert diagnostics.ranked_categories == ()
    assert diagnostics.categories == ()
    assert diagnostics.top_3_stability is None
    assert diagnostics.top_5_stability is None
    assert diagnostics.maximum_score_delta is None
    assert diagnostics.maximum_rank_displacement is None
    assert diagnostics.warning is None
    assert diagnostics.reference_set_size == vector["reference_set_size"]
    assert diagnostics.displacement_threshold == pytest.approx(
        vector["displacement_threshold"], abs=1e-9
    )


@pytest.mark.lreq("LREQ-SEN-020")
def test_sensitivity_max_score_and_rank_displacement() -> None:
    """Per-category and run-level displacements match the vectors (SRS §9.3).

    LREQ-SEN-020 lines 1088-1090: ``maximum_score_delta`` is the maximum absolute
    difference against the balanced score; ``maximum_rank_displacement`` is the
    maximum absolute rank difference across policies. Each per-category score
    delta is re-derived from the fixture's policy scores.
    """
    for label in ("stable", "top_three", "displacement"):
        vector, _, _, _, diagnostics = _diagnostics(label)
        scores_by_policy = vector["expected_scores_by_policy"]
        rows = {row.category: row for row in diagnostics.categories}
        for category, expected_delta in vector["expected_max_score_delta"].items():
            row = rows[category]
            assert row.maximum_score_delta == pytest.approx(expected_delta, abs=1e-9)
            derived = max(
                abs(
                    scores_by_policy["demand_heavy"][category]
                    - scores_by_policy["balanced"][category]
                ),
                abs(
                    scores_by_policy["competition_heavy"][category]
                    - scores_by_policy["balanced"][category]
                ),
            )
            assert row.maximum_score_delta == pytest.approx(derived, abs=1e-9)
            assert (
                row.maximum_rank_displacement
                == vector["expected_max_rank_displacement"][category]
            )
        assert diagnostics.maximum_score_delta == pytest.approx(
            vector["expected_maximum_score_delta"], abs=1e-9
        )
        assert (
            diagnostics.maximum_rank_displacement
            == vector["expected_maximum_rank_displacement"]
        )


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-SEN-040")
def test_sensitivity_does_not_add_or_remove_candidates() -> None:
    """A non-candidate never enters the ranked set and no candidate leaves it.

    SRS §9.3 LREQ-SEN-020 line 1077 with LREQ-SEN-040: the ranked set is exactly
    the frozen candidate tuple. A non-candidate that would outrank every
    candidate is still excluded, and the candidate tuple is unchanged after the
    call.
    """
    vector = SENSITIVITY_VECTORS_BY_LABEL["displacement"]
    components = vector["components"]
    candidates = tuple(components)
    merged = dict(components)
    merged["n-extra"] = (1.0, 1.0, 1.0, 1.0)
    base = sfx.make_candidate_set(candidates, vector["run_category_count"])
    metrics, scores = sfx.make_metrics_and_scores(merged)
    diagnostics = evaluate_sensitivity(
        base, metrics, scores, reference_set_size=vector["reference_set_size"]
    )
    assert base.base_rankable_candidates == candidates
    assert diagnostics.ranked_categories == candidates
    assert {row.category for row in diagnostics.categories} == set(candidates)
    assert "n-extra" not in diagnostics.ranked_categories


@pytest.mark.lreq("LREQ-SEN-020")
def test_sensitivity_returns_typed_diagnostics() -> None:
    """The complete typed diagnostic carries the persisted field names.

    SRS §9.3 LREQ-SEN-020 lines 1068-1072 name ``top_3_stability``,
    ``top_5_stability``, ``maximum_score_delta``, ``maximum_rank_displacement``,
    and ``sensitivity_warning``; plan §5 adds ``policies``, ``ranked_categories``,
    ``categories``, ``reference_set_size`` and ``displacement_threshold`` so
    Chunk 10 can persist the diagnostic without recomputation.
    """
    vector, _, _, _, diagnostics = _diagnostics("stable")
    assert isinstance(diagnostics, SensitivityDiagnostics)
    assert diagnostics.policies == sfx.SENSITIVITY_POLICY_ORDER_EXPECTED
    assert isinstance(diagnostics.ranked_categories, tuple)
    assert all(
        isinstance(row, CategorySensitivityRank) for row in diagnostics.categories
    )
    for name in (
        "top_3_stability",
        "top_5_stability",
        "maximum_score_delta",
        "maximum_rank_displacement",
        "warning",
    ):
        assert hasattr(diagnostics, name), name
    assert diagnostics.reference_set_size == vector["reference_set_size"]
    assert isinstance(diagnostics.displacement_threshold, float)
    assert diagnostics.displacement_threshold == pytest.approx(
        vector["displacement_threshold"], abs=1e-9
    )
    assert isinstance(diagnostics.warning, bool)
    candidate_count = len(diagnostics.ranked_categories)
    for row in diagnostics.categories:
        assert isinstance(row.category, str)
        assert isinstance(row.score_balanced, float)
        assert isinstance(row.score_demand_heavy, float)
        assert isinstance(row.score_competition_heavy, float)
        for rank_name in (
            "rank_balanced",
            "rank_demand_heavy",
            "rank_competition_heavy",
        ):
            rank = getattr(row, rank_name)
            assert isinstance(rank, int), rank_name
            assert 1 <= rank <= candidate_count, rank_name
        assert isinstance(row.maximum_score_delta, float)
        assert isinstance(row.maximum_rank_displacement, int)
        assert isinstance(row.warning, bool)


# ---------------------------------------------------------------------------
# LREQ-SEN-030 — warning thresholds and the null contract
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-030")
def test_sensitivity_warning_top_three_boundary() -> None:
    """The top-3 clause fires only strictly below ``2/3`` (SRS §9.3).

    LREQ-SEN-030 line 1093: ``top_3_stability < 2/3``. The stable vector sits
    exactly at ``2/3`` (intersection ``{C, D}``) and must not warn; the
    top-three-only vector at ``1/3`` warns for every base-candidate row and at
    the run level (R4).
    """
    stable = SENSITIVITY_VECTORS_BY_LABEL["stable"]
    _, _, _, _, at_boundary = _diagnostics("stable")
    assert at_boundary.top_3_stability == pytest.approx(2.0 / 3.0, abs=1e-9)
    assert not (at_boundary.top_3_stability < 2.0 / 3.0)
    assert at_boundary.warning is False
    assert all(row.warning is False for row in at_boundary.categories)
    assert (
        stable["expected_maximum_rank_displacement"] <= stable["displacement_threshold"]
    )

    top_three = SENSITIVITY_VECTORS_BY_LABEL["top_three"]
    _, _, _, _, warns = _diagnostics("top_three")
    assert warns.top_3_stability == pytest.approx(1.0 / 3.0, abs=1e-9)
    assert warns.top_3_stability < 2.0 / 3.0
    assert warns.warning is True
    assert all(row.warning is True for row in warns.categories)
    assert (
        top_three["expected_maximum_rank_displacement"]
        <= top_three["displacement_threshold"]
    )


@pytest.mark.lreq("LREQ-SEN-030")
@pytest.mark.lreq("LREQ-NRM-020")
def test_sensitivity_warning_rank_displacement_threshold() -> None:
    """A displacement above ``max(3, 25% of reference-set size)`` warns alone.

    LREQ-SEN-030 lines 1093-1095 with LREQ-NRM-020 (``reference_size =
    category_count - 1``): the displacement vector's ``top_3_stability`` is
    exactly ``2/3`` so the top-3 clause cannot fire, while ``c-8`` moves 6 ranks
    against the ``max(3, 0.25 * 20) = 5.0`` threshold, so only the displacement
    clause explains the ``True``. The top-three vector's maximum displacement 4
    is at or below the threshold and fires no displacement warning.
    """
    vector, _, _, _, diagnostics = _diagnostics("displacement")
    assert diagnostics.top_3_stability == pytest.approx(2.0 / 3.0, abs=1e-9)
    assert not (diagnostics.top_3_stability < 2.0 / 3.0)
    assert vector["reference_set_size"] == vector["run_category_count"] - 1
    expected_threshold = max(3.0, 0.25 * vector["reference_set_size"])
    assert diagnostics.displacement_threshold == pytest.approx(
        expected_threshold, abs=1e-9
    )
    assert diagnostics.displacement_threshold == pytest.approx(
        vector["displacement_threshold"], abs=1e-9
    )
    rows = {row.category: row for row in diagnostics.categories}
    c8 = rows["c-8"]
    assert (
        c8.maximum_rank_displacement == vector["expected_max_rank_displacement"]["c-8"]
    )
    assert vector["expected_max_rank_displacement"]["c-8"] == 6
    assert c8.warning is True
    assert all(
        rows[category].warning is False
        for category in vector["components"]
        if category != "c-8"
    )
    assert diagnostics.warning is True

    _, _, _, _, top_three = _diagnostics("top_three")
    top_three_vector = SENSITIVITY_VECTORS_BY_LABEL["top_three"]
    assert top_three.maximum_rank_displacement == 4
    assert (
        top_three.maximum_rank_displacement
        <= top_three_vector["displacement_threshold"]
    )


@pytest.mark.lreq("LREQ-SEN-030")
def test_sensitivity_warning_is_false_when_top_three_inapplicable() -> None:
    """The top-3 clause is inapplicable when fewer than 3 candidates exist.

    Plan §5.3/R2: the clause contributes nothing when ``top_3_stability is
    None``; the displacement clause is still computable (0 for both candidates),
    so every warning is the explicit boolean ``False``, not ``None`` and not a
    padded top-3 value.
    """
    for label in ("two_candidate", "one_candidate"):
        vector, _, _, _, diagnostics = _diagnostics(label)
        assert diagnostics.top_3_stability is None, label
        assert diagnostics.top_5_stability is None, label
        assert diagnostics.maximum_rank_displacement == 0, label
        assert all(row.warning is False for row in diagnostics.categories), label
        assert diagnostics.warning is False, label
        assert vector["expected_run_warning"] is False, label


@pytest.mark.lreq("LREQ-SEN-030")
def test_sensitivity_warning_is_none_only_without_candidates() -> None:
    """``None`` is reserved for the zero-candidate set (plan §5.3 R2/R4).

    A per-category warning is a ``bool`` whenever at least one base candidate
    exists (the displacement clause is always applicable) and the run-level
    warning is the OR over candidates; only an empty candidate set yields
    ``None`` with no category rows (dependency-map §6.2/§6.3).
    """
    for label, vector in sfx.SENSITIVITY_VECTORS:
        _, _, _, _, diagnostics = _diagnostics(label)
        if not vector["components"]:
            assert diagnostics.categories == ()
            assert diagnostics.warning is None
            continue
        assert diagnostics.ranked_categories != ()
        assert isinstance(diagnostics.warning, bool), label
        for row in diagnostics.categories:
            assert isinstance(row.warning, bool), label
        assert diagnostics.warning is vector["expected_run_warning"], label


@pytest.mark.lreq("LREQ-SEN-030")
@pytest.mark.lreq("LREQ-NRM-020")
def test_sensitivity_reference_set_size_mismatch_raises() -> None:
    """``reference_set_size`` must equal ``run_category_count - 1`` (R3).

    LREQ-NRM-020: ``reference_size = category_count - 1``; LREQ-SEN-030's
    threshold is interpreted with the configured reference-set size. The guard
    accepts the matching value and raises ``ValueError`` on either neighbor
    (R3).
    """
    vector = SENSITIVITY_VECTORS_BY_LABEL["stable"]
    components = vector["components"]
    base = sfx.make_candidate_set(tuple(components), vector["run_category_count"])
    metrics, scores = sfx.make_metrics_and_scores(components)
    accepted = evaluate_sensitivity(
        base, metrics, scores, reference_set_size=vector["reference_set_size"]
    )
    assert vector["reference_set_size"] == vector["run_category_count"] - 1
    assert accepted.reference_set_size == vector["reference_set_size"]
    for bad in (vector["reference_set_size"] - 1, vector["reference_set_size"] + 1):
        with pytest.raises(ValueError):
            evaluate_sensitivity(base, metrics, scores, reference_set_size=bad)

    zero_vector = SENSITIVITY_VECTORS_BY_LABEL["zero_candidate"]
    empty_base = sfx.make_candidate_set((), zero_vector["run_category_count"])
    empty_metrics, empty_scores = sfx.make_metrics_and_scores({})
    accepted_empty = evaluate_sensitivity(
        empty_base,
        empty_metrics,
        empty_scores,
        reference_set_size=zero_vector["reference_set_size"],
    )
    assert accepted_empty.reference_set_size == zero_vector["reference_set_size"]
    with pytest.raises(ValueError):
        evaluate_sensitivity(
            empty_base,
            empty_metrics,
            empty_scores,
            reference_set_size=zero_vector["reference_set_size"] + 1,
        )


@pytest.mark.lreq("LREQ-SEN-030")
@pytest.mark.lreq("LREQ-SEN-040")
def test_sensitivity_warning_does_not_alter_balanced_score() -> None:
    """A raised warning leaves every balanced score exactly as computed.

    LREQ-SEN-030's warning "SHALL not silently alter the primary balanced
    score"; LREQ-SEN-040: diagnostics qualify, never replace. The top-three
    vector warns for every candidate while each ``score_balanced`` still equals
    the aligned primary ``ScoreResult.market_opportunity_score`` and the
    fixture's balanced policy score within ``1e-9``.
    """
    vector, _, _, scores, diagnostics = _diagnostics("top_three")
    assert diagnostics.warning is True
    balanced = vector["expected_scores_by_policy"]["balanced"]
    rows = {row.category: row for row in diagnostics.categories}
    for category, score in zip(diagnostics.ranked_categories, scores):
        row = rows[category]
        assert row.score_balanced == pytest.approx(balanced[category], abs=1e-9)
        assert row.score_balanced == pytest.approx(
            score.market_opportunity_score, abs=1e-9
        )
        expected_rank = vector["expected_ranks_by_policy"]["balanced"][category]
        assert row.rank_balanced == expected_rank


@pytest.mark.lreq("LREQ-SEN-040")
@pytest.mark.lreq("LREQ-SCR-060")
def test_sensitivity_preserves_balanced_primary_score() -> None:
    """The balanced recomputation equals the primary score and mutates nothing.

    Plan §9 balanced-preservation vector with SRS §9.3 LREQ-SEN-040 and
    LREQ-SCR-060: for every candidate, ``score_balanced`` equals the primary
    ``market_opportunity_score`` and ``balanced_composite`` within ``1e-9``;
    ``ranked_under_policy`` under the balanced policy matches both; and the
    input ``ScoreResult`` tuple and the candidate set are unchanged after the
    call.
    """
    vector = SENSITIVITY_VECTORS_BY_LABEL["stable"]
    components = vector["components"]
    candidates = tuple(components)
    base = sfx.make_candidate_set(candidates, vector["run_category_count"])
    metrics, scores = sfx.make_metrics_and_scores(components)
    before_scores = tuple(scores)
    before_fields = tuple(
        (
            score.market_opportunity_score,
            score.score_state,
            score.component_d,
            score.component_c,
            score.component_r,
            score.component_q,
            score.available_component_count,
        )
        for score in scores
    )

    diagnostics = evaluate_sensitivity(
        base, metrics, scores, reference_set_size=vector["reference_set_size"]
    )

    after_fields = tuple(
        (
            score.market_opportunity_score,
            score.score_state,
            score.component_d,
            score.component_c,
            score.component_r,
            score.component_q,
            score.available_component_count,
        )
        for score in scores
    )
    assert tuple(scores) == before_scores
    assert after_fields == before_fields
    assert base.base_rankable_candidates == candidates

    component_map = _component_values(components)
    balanced = vector["expected_scores_by_policy"]["balanced"]
    expected_order = _ranked_categories(vector, "balanced")
    ranked = ranked_under_policy(
        base.base_rankable_candidates,
        component_map,
        policy=SENSITIVITY_POLICIES["balanced"],
    )
    assert [category for category, _ in ranked] == expected_order
    rows = {row.category: row for row in diagnostics.categories}
    for category, score in zip(candidates, scores):
        composite = balanced_composite(component_map[category])
        assert composite.market_opportunity_score == pytest.approx(
            balanced[category], abs=1e-9
        )
        assert rows[category].score_balanced == pytest.approx(
            composite.market_opportunity_score, abs=1e-9
        )
        assert rows[category].score_balanced == pytest.approx(
            score.market_opportunity_score, abs=1e-9
        )


# ---------------------------------------------------------------------------
# LREQ-EVD-050 — final evidence grade
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EVD-050")
def test_final_evidence_grade_strong_vector() -> None:
    """The strong fixture row grades ``strong`` (SRS §9.2 lines 1047-1052).

    LREQ-EVD-050: the minimum component sample count is 80 (the boundary), all
    three coverages are exactly ``STRONG_COMPONENT_COVERAGE = 0.80``, discovery
    is verified and complete, identity counts are zero, page views are not
    contradicted, the run is 21 categories, and ``sensitivity_warning is
    False``.
    """
    grade, sample, vector, decision = _evidence_row("strong")
    assert (
        sample.minimum_component_sample_count
        == vector["expected_minimum_component_sample_count"]
    )
    assert sample.minimum_component_sample_count == 80
    assert STRONG_COMPONENT_COVERAGE == 0.80
    assert vector["run_category_count"] == STRONG_REFERENCE_CATEGORY_COUNT
    assert decision.not_rankable_reasons == ()
    assert grade is EvidenceGrade.STRONG
    assert grade.value == "strong"


@pytest.mark.lreq("LREQ-EVD-050")
def test_final_evidence_grade_moderate_vector() -> None:
    """The moderate rows grade ``moderate``, including the 8-category run.

    SRS §9.2 line 1050: ``minimum_component_sample_count >= 40`` (or census
    >= 20), coverages >= 0.50, at least 8 categories, no critical identity
    failure. The 8-category row is computable but provisional, never rankable
    (SRS §9.1 line 1008).
    """
    for label in ("moderate", "eight_category"):
        grade, sample, vector, _ = _evidence_row(label)
        assert (
            sample.minimum_component_sample_count
            == vector["expected_minimum_component_sample_count"]
        ), label
        assert vector["sensitivity_warning"] is False, label
        assert grade is EvidenceGrade.MODERATE, label
    _, _, eight_vector, eight_decision = _evidence_row("eight_category")
    assert eight_vector["run_category_count"] == MIN_CATEGORIES_PER_RUN
    assert (
        eight_decision.rankability_state is PreSensitivityRankabilityState.PROVISIONAL
    )


@pytest.mark.lreq("LREQ-EVD-050")
def test_final_evidence_grade_weak_vector() -> None:
    """The weak rows grade ``weak``: the sub-40 count alone decides.

    SRS §9.2 line 1051: computable but below the moderate policy. A coverage of
    0.60 with a sufficient count would still be ``moderate`` (line 1050), so the
    weak row needs the sub-40 count; a single low component count drags the
    minimum down.
    """
    for label in ("weak", "weak_low_count_and_coverage"):
        grade, sample, vector, _ = _evidence_row(label)
        assert (
            sample.minimum_component_sample_count
            == vector["expected_minimum_component_sample_count"]
        ), label
        assert grade is EvidenceGrade.WEAK, label
    _, _, weak_vector, _ = _evidence_row("weak")
    assert weak_vector["expected_minimum_component_sample_count"] < 40


@pytest.mark.lreq("LREQ-EVD-050")
@pytest.mark.lreq("LREQ-EVD-020")
def test_final_evidence_grade_insufficient_when_not_rankable() -> None:
    """A not-rankable decision grades ``insufficient`` regardless of sample size.

    SRS §9.2 line 1052: "Required evidence is invalid, unavailable, or
    contradictory; category is not rankable". The insufficient row keeps the
    strong sample facts (80) while ``not_rankable_reasons`` is non-empty, so the
    precedence is decision-first, not sample-first (LREQ-EVD-020).
    """
    grade, sample, vector, decision = _evidence_row("insufficient")
    assert decision.not_rankable_reasons != ()
    assert decision.base_rankable is False
    assert sample.minimum_component_sample_count == 80
    assert (
        sample.minimum_component_sample_count
        == vector["expected_minimum_component_sample_count"]
    )
    assert grade is EvidenceGrade.INSUFFICIENT


@pytest.mark.lreq("LREQ-EVD-050")
def test_final_evidence_grade_census_alternative() -> None:
    """A census of 50 earns ``strong``; 20 only ``moderate`` (SRS §9.2 line 1049).

    The census alternative replaces the sample-count condition with
    ``discovered_population_count``. Both rows keep all four components available
    and carry explicit usable counts of ``0`` — an explicit zero, never a
    missing value (SRS §1.2) — so the population threshold alone decides the
    grade.
    """
    for label, expected in (
        ("census_strong", EvidenceGrade.STRONG),
        ("census_moderate", EvidenceGrade.MODERATE),
    ):
        grade, sample, vector, _ = _evidence_row(label)
        population = vector["sample_overrides"]["discovered_population_count"]
        assert sample.sample_is_census is True, label
        assert sample.discovered_population_count == population, label
        assert sample.minimum_component_sample_count == 0, label
        assert grade is expected, label


@pytest.mark.lreq("LREQ-EVD-050")
@pytest.mark.lreq("LREQ-NRM-020")
def test_final_evidence_grade_uses_min_component_sample_count() -> None:
    """The grade uses the minimum of the three usable counts (SRS §9.2).

    Lines 1035-1040 define ``minimum_component_sample_count`` as the minimum of
    the demand/recent-supply/quality usable counts; lines 1049-1050 set the
    80/40 boundaries. ``min(80, 40, 80) = 40`` is ``moderate`` and
    ``min(80, 80, 39) = 39`` is ``weak``; the two high counts cannot lift the
    minimum. The run's leave-one-out reference size is ``category_count - 1``
    (SRS §8.1 LREQ-NRM-020), held at 20 peers in these rows.
    """
    for label in ("min_component_moderate", "min_component_weak"):
        grade, sample, vector, _ = _evidence_row(label)
        overrides = vector["sample_overrides"]
        expected_minimum = min(
            overrides["usable_demand_sample_count"],
            overrides["usable_recent_supply_sample_count"],
            overrides["usable_quality_sample_count"],
        )
        assert sample.minimum_component_sample_count == expected_minimum, label
        assert expected_minimum == vector["expected_minimum_component_sample_count"], (
            label
        )
        assert grade.value == vector["expected_grade"], label


@pytest.mark.lreq("LREQ-EVD-050")
@pytest.mark.lreq("LREQ-SEN-030")
def test_final_evidence_grade_sensitivity_demotes_strong() -> None:
    """``sensitivity_warning is True`` blocks ``strong`` (plan §5.4; R6).

    SRS §9.2 line 1049 requires "acceptable sensitivity"; with every other strong
    fact satisfied, the warning ``True`` demotes the grade to ``moderate`` (no
    sensitivity condition is attached to the moderate row).
    """
    grade, _, vector, _ = _evidence_row("strong_warning_true")
    assert vector["sensitivity_warning"] is True
    assert grade is EvidenceGrade.MODERATE
    assert grade is not EvidenceGrade.STRONG


@pytest.mark.lreq("LREQ-EVD-050")
@pytest.mark.lreq("LREQ-SEN-030")
def test_final_evidence_grade_null_warning_is_not_strong() -> None:
    """A ``None`` warning cannot earn ``strong`` (plan §5.4 R6).

    A not-evaluated sensitivity (``None``) is not "acceptable sensitivity", so
    the strong grade is unreachable; the grade falls to ``moderate``. ``None``
    is never read as ``False`` (SRS §1.2).
    """
    grade, _, vector, _ = _evidence_row("strong_null_warning")
    assert vector["sensitivity_warning"] is None
    assert grade is EvidenceGrade.MODERATE
    assert grade is not EvidenceGrade.STRONG


# ---------------------------------------------------------------------------
# LREQ-EVD-040 / LREQ-EVD-030 — final rankability
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EVD-040")
def test_final_rankability_requires_base_and_sensitivity() -> None:
    """``rankable`` needs a base-rankable decision and ``warning is False``.

    SRS §9.1 LREQ-EVD-040 lines 1003-1007: the category must be in
    ``base_rankable_candidates`` and the final sensitivity thresholds must pass.
    Without the base candidacy (pre-sensitivity provisional) the result is
    ``provisional`` even when the warning is ``False``; with both it is
    ``rankable``.
    """
    base_decision, warning, _ = _rankability("rankable_warning_false")
    assert warning is False
    assert (
        final_rankability_status(base_decision, sensitivity_warning=warning)
        is RankabilityStatus.RANKABLE
    )

    provisional_decision, warning, _ = _rankability("pre_sensitivity_provisional")
    assert provisional_decision.base_rankable is False
    assert warning is False
    assert (
        final_rankability_status(provisional_decision, sensitivity_warning=warning)
        is RankabilityStatus.PROVISIONAL
    )


@pytest.mark.lreq("LREQ-EVD-040")
@pytest.mark.lreq("LREQ-EVD-030")
@pytest.mark.lreq("LREQ-SEN-040")
def test_final_rankability_sensitivity_demotes_to_provisional() -> None:
    """A sensitivity warning demotes only to provisional (SRS §9.1).

    LREQ-EVD-040 lines 1009-1010: sensitivity failure changes final rankability
    to provisional, and does not change the fixed candidate set or the balanced
    primary score. The rankable+warning fixture row is the unit case; the
    end-to-end path uses the displacement vector's actual ``True`` warning and
    the stable vector's actual ``False`` warning.
    """
    decision, warning, _ = _rankability("rankable_warning_true")
    assert warning is True
    assert (
        final_rankability_status(decision, sensitivity_warning=warning)
        is RankabilityStatus.PROVISIONAL
    )

    vector, base, _, scores, diagnostics = _diagnostics("displacement")
    candidates = tuple(vector["components"])
    assert diagnostics.warning is True
    assert base.base_rankable_candidates == candidates
    status = final_rankability_status(decision, sensitivity_warning=diagnostics.warning)
    assert status is RankabilityStatus.PROVISIONAL
    assert base.base_rankable_candidates == candidates
    for row, score in zip(diagnostics.categories, scores):
        assert row.score_balanced == pytest.approx(
            score.market_opportunity_score, abs=1e-9
        )

    _, _, _, _, stable = _diagnostics("stable")
    assert stable.warning is False
    assert (
        final_rankability_status(decision, sensitivity_warning=stable.warning)
        is RankabilityStatus.RANKABLE
    )


@pytest.mark.lreq("LREQ-EVD-040")
@pytest.mark.lreq("LREQ-EVD-030")
def test_final_rankability_null_warning_is_provisional() -> None:
    """A ``None`` warning on a rankable decision yields ``provisional`` (R7).

    SRS §9.1 LREQ-EVD-040 line 1007: the final sensitivity thresholds must pass;
    a not-demonstrated (``None``) warning is the conservative ``provisional``.
    The branch is unreachable for a base candidate (R2/R3) but is defined and
    tested.
    """
    decision, warning, _ = _rankability("rankable_warning_none")
    assert warning is None
    status = final_rankability_status(decision, sensitivity_warning=warning)
    assert status is RankabilityStatus.PROVISIONAL
    assert status is not RankabilityStatus.RANKABLE


@pytest.mark.lreq("LREQ-EVD-040")
def test_final_rankability_never_demotes_to_not_rankable() -> None:
    """Sensitivity can never demote a category to ``not_rankable`` (SRS §9.1).

    LREQ-EVD-040 lines 1009-1010: sensitivity failure changes final rankability
    to provisional. A pre-sensitivity ``not_rankable`` stays ``not_rankable``
    for either warning value; for every other row the result is never
    ``not_rankable``.
    """
    decision, warning, _ = _rankability("pre_sensitivity_not_rankable")
    assert warning is True
    assert (
        final_rankability_status(decision, sensitivity_warning=True)
        is RankabilityStatus.NOT_RANKABLE
    )
    assert (
        final_rankability_status(decision, sensitivity_warning=False)
        is RankabilityStatus.NOT_RANKABLE
    )
    for label, overrides, row_warning, _ in sfx.FINAL_RANKABILITY_VECTORS:
        row_decision = _decision(**overrides)
        status = final_rankability_status(row_decision, sensitivity_warning=row_warning)
        if (
            row_decision.rankability_state
            is PreSensitivityRankabilityState.NOT_RANKABLE
        ):
            assert status is RankabilityStatus.NOT_RANKABLE, label
        else:
            assert status is not RankabilityStatus.NOT_RANKABLE, label


@pytest.mark.lreq("LREQ-EVD-040")
@pytest.mark.lreq("LREQ-EVD-030")
def test_eight_to_twenty_run_never_rankable() -> None:
    """The 8-category minimum run is never ``rankable`` (SRS §9.1 line 1008).

    LREQ-EVD-040: a run with 8-20 categories SHALL never be labeled ``rankable``;
    it may be provisional. The minimum run has an empty candidate set and a null
    sensitivity warning, and its pre-sensitivity provisional decision stays
    provisional through the final mapping.
    """
    vector, base, _, _, diagnostics = _diagnostics("zero_candidate")
    assert vector["run_category_count"] == MIN_CATEGORIES_PER_RUN
    assert base.base_rankable_candidates == ()
    assert diagnostics.warning is None
    decision, _, _ = _rankability("pre_sensitivity_provisional")
    status = final_rankability_status(decision, sensitivity_warning=diagnostics.warning)
    assert status is RankabilityStatus.PROVISIONAL
    assert status is not RankabilityStatus.RANKABLE


@pytest.mark.lreq("LREQ-EVD-010")
def test_final_rankability_states_use_rankability_status() -> None:
    """Final states are ``models.RankabilityStatus``, not the 9A state type.

    SRS §9.1 LREQ-EVD-010 line 978: use ``not_rankable``, ``provisional``, and
    ``rankable``. The final values use the persisted vocabulary and are a
    different type from the pre-sensitivity states with the same string values
    (plan §4.4).
    """
    assert {state.value for state in RankabilityStatus} == {
        "not_rankable",
        "provisional",
        "rankable",
    }
    assert RankabilityStatus is not PreSensitivityRankabilityState
    for label in (
        "rankable_warning_false",
        "rankable_warning_true",
        "pre_sensitivity_not_rankable",
    ):
        decision, warning, _ = _rankability(label)
        status = final_rankability_status(decision, sensitivity_warning=warning)
        assert isinstance(status, RankabilityStatus), label
        assert not isinstance(status, PreSensitivityRankabilityState), label
        assert status.value in {"not_rankable", "provisional", "rankable"}, label


@pytest.mark.lreq("LREQ-EVD-030")
def test_sensitivity_high_provisional_clause_completes_evd030() -> None:
    """The "or sensitivity is high" clause lands only here (SRS §9.1 line 1000).

    LREQ-EVD-030 names sensitivity as a provisional condition; Chunk 9A's
    provisional vocabulary has no sensitivity member, so the clause is completed
    by this chunk's final mapping: a pre-sensitivity ``rankable`` decision with
    empty ``provisional_reasons`` becomes ``provisional`` iff the sensitivity
    warning fires, and stays ``rankable`` when it does not.
    """
    decision, _, _ = _rankability("rankable_warning_true")
    assert decision.rankability_state is PreSensitivityRankabilityState.RANKABLE
    assert decision.provisional_reasons == ()
    assert decision.base_rankable is True
    assert not any("sensitivity" in reason.value for reason in ProvisionalReason)
    assert (
        final_rankability_status(decision, sensitivity_warning=True)
        is RankabilityStatus.PROVISIONAL
    )
    assert (
        final_rankability_status(decision, sensitivity_warning=False)
        is RankabilityStatus.RANKABLE
    )


@pytest.mark.lreq("LREQ-EVD-040")
@pytest.mark.lreq("LREQ-EVD-050")
def test_final_evidence_and_rankability_preserve_candidate_set_and_score() -> None:
    """The final assignments never touch the candidate set or the score.

    Plan §11 with SRS §9.1 LREQ-EVD-040 lines 1009-1010 and LREQ-EVD-050: the
    final grade and status are computed after sensitivity and returned as plain
    values; the frozen candidate tuple and every ``ScoreResult`` field are
    unchanged, and each balanced score still equals the primary score within
    ``1e-9``.
    """
    _, base, _, scores, diagnostics = _diagnostics("stable")
    before_fields = tuple(
        (
            score.market_opportunity_score,
            score.component_d,
            score.component_c,
            score.component_r,
            score.component_q,
            score.available_component_count,
        )
        for score in scores
    )
    candidates_before = base.base_rankable_candidates
    grade, _, _, _ = _evidence_row("strong")
    decision, _, _ = _rankability("rankable_warning_false")
    status = final_rankability_status(decision, sensitivity_warning=diagnostics.warning)
    after_fields = tuple(
        (
            score.market_opportunity_score,
            score.component_d,
            score.component_c,
            score.component_r,
            score.component_q,
            score.available_component_count,
        )
        for score in scores
    )
    assert grade is EvidenceGrade.STRONG
    assert status is RankabilityStatus.RANKABLE
    assert base.base_rankable_candidates == candidates_before
    assert after_fields == before_fields
    for row, score in zip(diagnostics.categories, scores):
        assert row.score_balanced == pytest.approx(
            score.market_opportunity_score, abs=1e-9
        )


# ---------------------------------------------------------------------------
# LREQ-TST-090 / LREQ-TST-010 / LREQ-TST-060 — golden and boundary coverage
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-TST-090")
def test_sensitivity_golden_vectors() -> None:
    """Every fixture vector's expected values within ``1e-9`` (LREQ-TST-090).

    For each of the six labels, the ranked order, all three policy scores and
    ranks, the per-category score/rank displacements and warnings, the run-level
    stabilities, displacements, and warning equal the hand-derived fixture
    values (SRS §9.3 lines 1060-1096). The hand derivations live next to each
    vector in ``tests/fixtures/sensitivity_fixtures.py``.
    """
    for label, vector in sfx.SENSITIVITY_VECTORS:
        _, _, _, _, diagnostics = _diagnostics(label)
        components = vector["components"]
        assert diagnostics.ranked_categories == tuple(components), label
        assert diagnostics.policies == sfx.SENSITIVITY_POLICY_ORDER_EXPECTED, label
        component_map = _component_values(components)
        for policy in sfx.SENSITIVITY_POLICY_ORDER_EXPECTED:
            ranked = ranked_under_policy(
                tuple(components), component_map, policy=SENSITIVITY_POLICIES[policy]
            )
            assert [category for category, _ in ranked] == _ranked_categories(
                vector, policy
            ), (label, policy)
            for category, value in ranked:
                expected_score = vector["expected_scores_by_policy"][policy][category]
                assert value == pytest.approx(expected_score, abs=1e-9), (
                    label,
                    policy,
                    category,
                )
        rows = {row.category: row for row in diagnostics.categories}
        for category in components:
            row = rows[category]
            for policy in sfx.SENSITIVITY_POLICY_ORDER_EXPECTED:
                expected_score = vector["expected_scores_by_policy"][policy][category]
                attribute = {
                    "balanced": "score_balanced",
                    "demand_heavy": "score_demand_heavy",
                    "competition_heavy": "score_competition_heavy",
                }[policy]
                assert getattr(row, attribute) == pytest.approx(
                    expected_score, abs=1e-9
                ), (label, policy, category)
                expected_rank = vector["expected_ranks_by_policy"][policy][category]
                rank_attribute = {
                    "balanced": "rank_balanced",
                    "demand_heavy": "rank_demand_heavy",
                    "competition_heavy": "rank_competition_heavy",
                }[policy]
                assert getattr(row, rank_attribute) == expected_rank, (
                    label,
                    policy,
                    category,
                )
            assert row.maximum_score_delta == pytest.approx(
                vector["expected_max_score_delta"][category], abs=1e-9
            ), (label, category)
            assert (
                row.maximum_rank_displacement
                == vector["expected_max_rank_displacement"][category]
            ), (label, category)
            assert row.warning == vector["expected_warning"][category], (
                label,
                category,
            )
        for attribute, key in (
            ("top_3_stability", "expected_top_3_stability"),
            ("top_5_stability", "expected_top_5_stability"),
            ("maximum_score_delta", "expected_maximum_score_delta"),
            ("maximum_rank_displacement", "expected_maximum_rank_displacement"),
            ("warning", "expected_run_warning"),
        ):
            actual = getattr(diagnostics, attribute)
            expected = vector[key]
            if expected is None:
                assert actual is None, (label, key)
            elif isinstance(expected, float):
                assert actual == pytest.approx(expected, abs=1e-9), (label, key)
            else:
                assert actual == expected, (label, key)
        assert diagnostics.reference_set_size == vector["reference_set_size"], label
        assert diagnostics.displacement_threshold == pytest.approx(
            vector["displacement_threshold"], abs=1e-9
        ), label


@pytest.mark.lreq("LREQ-TST-010")
def test_sensitivity_normal_and_boundary_values() -> None:
    """Normal, explicit zero, missing, invalid, ties, and minimum boundaries.

    LREQ-TST-010. Normal: the stable vector's five candidates. Explicit valid
    zero: ``maximum_score_delta == 0.0`` and rank displacement 0 with one
    candidate, and a census with explicit usable counts of ``0``. Missing:
    ``top_3_stability is None`` and ``warning is None`` cases. Invalid: the
    reference-size guard and the candidate/components contract breaches raise
    ``ValueError``. Ties: the stable demand-heavy pair. Minimum boundaries: one
    candidate; the exact ``2/3`` top-3 boundary; the 80/40/39 sample boundaries;
    coverage 0.80/0.50; run size 8/21 with thresholds 3.0/5.0.
    """
    stable, _, _, _, diagnostics = _diagnostics("stable")
    assert len(diagnostics.categories) == 5
    assert diagnostics.top_3_stability == pytest.approx(2.0 / 3.0, abs=1e-9)

    _, _, _, _, one_candidate = _diagnostics("one_candidate")
    assert one_candidate.maximum_score_delta == 0.0
    assert one_candidate.maximum_rank_displacement == 0
    assert one_candidate.top_3_stability is None

    _, _, _, _, two_candidate = _diagnostics("two_candidate")
    assert two_candidate.top_3_stability is None
    assert two_candidate.top_5_stability is None

    zero_vector, _, _, _, zero_candidate = _diagnostics("zero_candidate")
    assert zero_candidate.warning is None
    assert zero_candidate.displacement_threshold == pytest.approx(
        zero_vector["displacement_threshold"], abs=1e-9
    )
    assert stable["displacement_threshold"] == pytest.approx(5.0, abs=1e-9)

    # Ties: the fixture demand ranks break A before C (SRS §9.3 line 1074).
    tie_order = ranked_under_policy(
        tuple(stable["components"]),
        _component_values(stable["components"]),
        policy=SENSITIVITY_POLICIES["demand_heavy"],
    )
    assert [category for category, _ in tie_order] == _ranked_categories(
        stable, "demand_heavy"
    )

    # Invalid inputs: the reference-size guard and the caller contract breaches.
    candidates = tuple(stable["components"])
    base = sfx.make_candidate_set(candidates, stable["run_category_count"])
    metrics, scores = sfx.make_metrics_and_scores(stable["components"])
    with pytest.raises(ValueError):
        evaluate_sensitivity(
            base,
            metrics,
            scores,
            reference_set_size=stable["reference_set_size"] - 1,
        )
    breached = (sfx.make_score_result(score=0.5, d=None, c=0.5, r=0.5, q=0.5),) + tuple(
        scores
    )[1:]
    with pytest.raises(ValueError):
        evaluate_sensitivity(
            base, metrics, breached, reference_set_size=stable["reference_set_size"]
        )
    dropped = {
        category: value
        for category, value in stable["components"].items()
        if category != candidates[-1]
    }
    dropped_metrics, dropped_scores = sfx.make_metrics_and_scores(dropped)
    with pytest.raises(ValueError):
        evaluate_sensitivity(
            base,
            dropped_metrics,
            dropped_scores,
            reference_set_size=stable["reference_set_size"],
        )

    # Minimum boundaries and the explicit census zero.
    assert MIN_CATEGORIES_PER_RUN == 8
    assert STRONG_REFERENCE_CATEGORY_COUNT == 21
    assert MIN_REQUIRED_COMPONENT_COVERAGE == 0.50
    assert STRONG_COMPONENT_COVERAGE == 0.80
    _, census_sample, _, _ = _evidence_row("census_strong")
    assert census_sample.minimum_component_sample_count == 0


@pytest.mark.lreq("LREQ-TST-060")
def test_scoring_tests_cover_sensitivity_after_base_candidates() -> None:
    """The fixed candidate set is an input; sensitivity drives the final status.

    SRS §13 LREQ-TST-060: scoring tests must cover the fixed
    ``base_rankable_candidates`` constructed before sensitivity,
    sensitivity-driven final provisional status, and non-rankability. The frozen
    signatures (plan §5) take the candidate set as an input and no
    run-category/identity argument; a warning-driven demotion reaches
    ``provisional`` while a not-rankable decision stays ``not_rankable``.
    """
    assert set(inspect.signature(evaluate_sensitivity).parameters) == {
        "base_candidates",
        "all_metrics",
        "scores",
        "reference_set_size",
        "min_required_component_coverage",
    }
    assert set(inspect.signature(ranked_under_policy).parameters) == {
        "candidates",
        "components_by_category",
        "policy",
    }
    assert set(inspect.signature(final_evidence_grade).parameters) == {
        "evidence",
        "sample",
        "decision",
        "run_category_count",
        "sensitivity_warning",
        "min_required_component_coverage",
        "strong_component_coverage",
    }
    assert set(inspect.signature(final_rankability_status).parameters) == {
        "decision",
        "sensitivity_warning",
    }

    vector, base, _, _, diagnostics = _diagnostics("displacement")
    assert diagnostics.warning is True
    assert base.base_rankable_candidates == tuple(vector["components"])
    demote, _, _ = _rankability("rankable_warning_true")
    assert (
        final_rankability_status(demote, sensitivity_warning=diagnostics.warning)
        is RankabilityStatus.PROVISIONAL
    )
    not_rankable, _, _ = _rankability("pre_sensitivity_not_rankable")
    assert (
        final_rankability_status(not_rankable, sensitivity_warning=diagnostics.warning)
        is RankabilityStatus.NOT_RANKABLE
    )


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 / LREQ-ARCH-010 / LREQ-ARCH-020 / LREQ-NFR-040
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_sensitivity_outputs_are_deterministic() -> None:
    """Equal inputs give equal diagnostics, independent of container order.

    SRS §3.3 LREQ-ARCH-030 / plan §8: fixed policy order, fixed top-k order, a
    sort-key tie-break, and no set/dict iteration determine the output. Repeated
    calls compare equal, and reversing ``all_metrics``/``scores`` (still 1:1
    aligned) changes nothing because the ranked set is the frozen candidate
    tuple.
    """
    vector, base, metrics, scores, first = _diagnostics("displacement")
    second = evaluate_sensitivity(
        base, metrics, scores, reference_set_size=vector["reference_set_size"]
    )
    assert second == first
    reversed_diagnostics = evaluate_sensitivity(
        base,
        tuple(reversed(metrics)),
        tuple(reversed(scores)),
        reference_set_size=vector["reference_set_size"],
    )
    assert reversed_diagnostics == first

    component_map = _component_values(vector["components"])
    again = ranked_under_policy(
        base.base_rankable_candidates,
        component_map,
        policy=SENSITIVITY_POLICIES["balanced"],
    )
    reversed_map = dict(reversed(list(component_map.items())))
    reordered = ranked_under_policy(
        base.base_rankable_candidates,
        reversed_map,
        policy=SENSITIVITY_POLICIES["balanced"],
    )
    assert again == reordered


@pytest.mark.lreq("LREQ-ARCH-010")
@pytest.mark.lreq("LREQ-ARCH-020")
def test_sensitivity_module_is_import_pure_and_clock_free() -> None:
    """``scoring.py`` keeps the SRS §3.3 purity boundary after Chunk 9B.

    LREQ-ARCH-010/-020: no collector, database, report, or CLI import, no
    network or file I/O, no clock read, and no randomness module. The structural
    checker and a direct AST scan both agree.
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


@pytest.mark.lreq("LREQ-NFR-040")
def test_sensitivity_public_functions_have_type_hints_and_docstrings() -> None:
    """Every Chunk 9B public name is annotated and documented (SRS §11).

    LREQ-NFR-040: type hints plus a docstring describing null and edge-case
    behavior. ``evaluate_sensitivity`` must state its empty-candidate null
    behavior and ``final_evidence_grade`` its ``None``-warning behavior; the
    typed structures carry docstrings too.
    """
    for name in SENSITIVITY_FUNCTION_NAMES + SENSITIVITY_CLASS_NAMES:
        target = getattr(scoring, name)
        assert target.__doc__, f"{name} must have a docstring"
    for name in SENSITIVITY_FUNCTION_NAMES:
        target = getattr(scoring, name)
        assert target.__annotations__, f"{name} must be annotated"
        assert "return" in target.__annotations__, f"{name} needs a return type"
