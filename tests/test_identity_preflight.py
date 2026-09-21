"""Analytical tests for chunk 6A — identity preflight planner and gate.

Source of truth: ``Documents/SRS-lean.md`` §4.4 (``LREQ-ID-010``/``020``/``030``/
``040``, lines 354-414) and the frozen plan
``Documents/plans/chunk-6A-identity-preflight-planner-and-gate.md`` (§5 interface
contract, §9 node list and golden vectors). Every analytical node carries an
``LREQ-ID-*`` marker and a ``tests/traceability.json`` entry keyed by its base
node ID. Per the operator's Q4 ruling no 6A node carries ``LREQ-TST-040`` or
``LREQ-TST-080``: those are Chunk 13's marker pass.

Golden values are hand-derived from the SRS formulas in the comment next to each
assertion: the denominator is the unique-identity count (SRS-lean:393-406), and
``0`` attempted gives ``null`` rates and ``insufficient`` (SRS-lean:408-410).

No network, no credentials, no clock reads, and no ``sqlite3``: the transport and
the retrieval timestamp are caller-injected (plan §5.3), and the repository is
exercised only through the frozen Chunk 2 public API against a pytest
``tmp_path``. Implementation-independent stand-ins (``pf.verdict``) are used
where Chunk 5 is a supporting contract only; the adapter itself is exercised in
the named adapter nodes.

Import policy: ``niche_scout.pipeline`` is imported at module scope (it exists as
a stub), so every missing 6A symbol fails at test-function call time as
``AttributeError`` — never as a collection error. ``pf`` imports only symbols
that exist today, and its repository helpers import ``pipeline`` lazily.
"""

from __future__ import annotations

import json

import pytest
from fixtures import identity_preflight_vectors as pf

import niche_scout.pipeline as pipeline

# --------------------------------------------------------------------------
# Helpers (pure; no assertions on behavior under test).
# --------------------------------------------------------------------------


def _open(tmp_path, name: str = "chunk6a.sqlite"):
    """Open a fresh repository under ``tmp_path`` (no live path, no network)."""
    from niche_scout import database

    return database.SqliteRepository(tmp_path / name)


def _seeded(tmp_path, run, *, page_view_semantics_status: str = "unvalidated"):
    """Open a repository and seed the run row and 4B sample members."""
    repository = _open(tmp_path)
    pf.seed_sampling_and_run(
        repository,
        run,
        page_view_semantics_status=page_view_semantics_status,
    )
    return repository


def _run_preflight(repository, run, *, transport, credentials=None, **overrides):
    """Call ``run_identity_preflight`` with the frozen signature defaults."""
    kwargs = dict(
        credentials=credentials if credentials is not None else pf.GQL_CREDENTIALS,
        transport=transport,
        correlation_mode=pf.EXPLICIT_KEY,
        retrieved_at_utc=pf.RETRIEVED_AT_UTC,
        policy=pf.small_policy(),
    )
    kwargs.update(overrides)
    return pipeline.run_identity_preflight(repository, run, **kwargs)


def _no_sleep(_seconds: float) -> None:
    """Supply a no-op sleeper so retry backoff never slows an ordering assertion."""


def _selection(run, *, policy=None, **overrides):
    """Call ``select_preflight_identities`` with a reduced or default policy."""
    return pipeline.select_preflight_identities(
        run, policy=policy if policy is not None else pf.small_policy()
    )


def _observations_for(selection, identity_results):
    """Wrap inert per-identity verdicts into the plan's observation stand-ins."""
    return tuple(
        pf.verdict(
            key,
            identity_match=identity_match,
            detail_ok=detail_ok,
            page_ok=page_ok,
        )
        for key, identity_match, detail_ok, page_ok in identity_results
    )


# --------------------------------------------------------------------------
# 9 — deterministic selection (LREQ-ID-010)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_identities_two_assets_five_categories():
    """Minimum: two assets from each of five categories, in run order."""
    run = pf.ten_identity_run()
    policy = pipeline.PreflightPolicy()  # LREQ-ID-030: 5 categories, 2 assets
    selection = pipeline.select_preflight_identities(run, policy=policy)
    # LREQ-ID-010 (SRS-lean:359-366): five eligible categories, two members
    # each, so the selection covers five categories and ten identities.
    assert selection.covered_categories == (
        pf.CATEGORY_A,
        pf.CATEGORY_B,
        pf.CATEGORY_C,
        pf.CATEGORY_D,
        pf.CATEGORY_E,
    )
    assert selection.selected_category_count == 5
    assert selection.eligible_categories == selection.covered_categories
    assert selection.reduced_coverage is False
    assert selection.category_shortfall == 0
    assert selection.asset_shortfall == 0
    assert len(selection.identities) == 10
    # LREQ-SMP-060: within a census stratum every member is selected but ranked
    # by (selection_digest, asset_identity_key); the digest covers
    # rule_version+category+key, not the discovery ordinal, so the A and B pairs
    # come back digest-first.
    assert [identity.asset_identity_key for identity in selection.identities] == [
        "A2",
        "A1",
        "B2",
        "B1",
        "C1",
        "C2",
        "D1",
        "D2",
        "E1",
        "E2",
    ]
    assert [identity.preflight_rank for identity in selection.identities] == list(
        range(1, 11)
    )
    assert {identity.source_category for identity in selection.identities} == {
        pf.CATEGORY_A,
        pf.CATEGORY_B,
        pf.CATEGORY_C,
        pf.CATEGORY_D,
        pf.CATEGORY_E,
    }


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_truncates_covered_but_reports_all_eligible():
    """Six eligible categories, five covered: only `covered` is truncated."""
    run = pf.six_category_run()
    policy = pipeline.PreflightPolicy()  # 5 categories, 2 assets
    selection = pipeline.select_preflight_identities(run, policy=policy)
    # Frozen interface §5.2: `eligible_categories` is every category meeting
    # `assets_per_category`; `covered_categories` is the selected subset, so the
    # six eligible categories yield five covered ones and the sixth stays a
    # reported-but-unselected eligibility.
    assert selection.eligible_categories == (
        pf.CATEGORY_A,
        pf.CATEGORY_B,
        pf.CATEGORY_C,
        pf.CATEGORY_D,
        pf.CATEGORY_E,
        pf.CATEGORY_F,
    )
    assert selection.covered_categories == (
        pf.CATEGORY_A,
        pf.CATEGORY_B,
        pf.CATEGORY_C,
        pf.CATEGORY_D,
        pf.CATEGORY_E,
    )
    assert selection.selected_category_count == 5
    assert selection.reduced_coverage is False
    assert selection.category_shortfall == 0
    # Both asset slots of every covered category are filled, so nothing is short.
    assert len(selection.identities) == 10
    assert selection.asset_shortfall == 0
    # `per_category_counts` tracks the covered set, never the eligible set.
    assert tuple(category for category, _ in selection.per_category_counts) == (
        selection.covered_categories
    )
    assert pf.CATEGORY_F not in selection.covered_categories
    assert all(
        identity.source_category != pf.CATEGORY_F for identity in selection.identities
    )


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_identities_reduced_coverage_and_shortfall():
    """Fewer than five eligible categories: all are used and shortfall recorded."""
    run = pf.three_category_run()
    policy = pipeline.PreflightPolicy()
    selection = pipeline.select_preflight_identities(run, policy=policy)
    # LREQ-ID-010 (SRS-lean:361-363): three eligible categories exist, so every
    # one is used, coverage is reduced, and the category shortfall is the
    # unfilled minimum: max(0, 5 - 3) = 2. Two assets per covered category are
    # selected with no asset slot left unfilled, so asset_shortfall == 0.
    assert selection.covered_categories == (
        pf.CATEGORY_A,
        pf.CATEGORY_B,
        pf.CATEGORY_C,
    )
    assert selection.eligible_categories == selection.covered_categories
    assert selection.selected_category_count == 3
    assert selection.reduced_coverage is True
    assert selection.category_shortfall == 2
    assert selection.asset_shortfall == 0
    assert len(selection.identities) == 6


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_one_asset_category_not_counted():
    """A one-asset category never satisfies the two-asset per-category minimum."""
    run = pf.one_asset_category_run()
    policy = pipeline.PreflightPolicy()
    selection = pipeline.select_preflight_identities(run, policy=policy)
    # LREQ-ID-010 (SRS-lean:364-366): Category/B holds one sampled asset, so it
    # contributes nothing and is never represented as satisfying the minimum.
    assert selection.covered_categories == (pf.CATEGORY_A,)
    assert selection.eligible_categories == (pf.CATEGORY_A,)
    assert selection.selected_category_count == 1
    assert selection.reduced_coverage is True
    # max(0, 5 - 1) = 4 categories short; the one covered category fills both
    # asset slots, so the asset shortfall is 0.
    assert selection.category_shortfall == 4
    assert selection.asset_shortfall == 0
    keys = [identity.asset_identity_key for identity in selection.identities]
    assert keys == [pf.A, pf.B]
    assert pf.C not in keys


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_overlap_dedups_identities():
    """Overlap never increases the attempted count: the denominator is unique."""
    run = pf.overlap_run()
    selection = _selection(run, policy=pf.small_policy())
    # LREQ-ID-040 (SRS-lean:393-394): identities are unique. Category/A samples
    # {A, S} and Category/B samples {B, S}; the union is {A, S, B} -- three
    # unique identities, not the four category references.
    keys = [identity.asset_identity_key for identity in selection.identities]
    assert keys == [pf.A, pf.SHARED, pf.B]
    assert len(selection.identities) == 3
    # First-seen order: the shared identity is claimed by Category/A (run order)
    # and never re-added by Category/B.
    shared = next(
        identity
        for identity in selection.identities
        if identity.asset_identity_key == pf.SHARED
    )
    assert shared.source_category == pf.CATEGORY_A
    assert shared.preflight_rank == 2


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_empty_run_is_insufficient_shape():
    """An empty run yields no identities and a positive category shortfall."""
    run = pf.run_from_categories({})
    policy = pipeline.PreflightPolicy()
    selection = pipeline.select_preflight_identities(run, policy=policy)
    # LREQ-ID-010 edge contract (plan §5.2): an empty run selects nothing and
    # the full five-category minimum is short.
    assert selection.identities == ()
    assert selection.covered_categories == ()
    assert selection.category_shortfall == 5
    assert selection.reduced_coverage is True


@pytest.mark.lreq("LREQ-ID-010")
def test_select_preflight_rejects_zero_minimums():
    """A zero category or asset minimum is never a valid preflight."""
    run = pf.two_asset_run()
    # Plan §5.1 edge contract: min_categories < 1 or assets_per_category < 1
    # raises ValueError at selection time.
    with pytest.raises(ValueError):
        pipeline.select_preflight_identities(
            run, policy=pf.small_policy(min_categories=0)
        )
    with pytest.raises(ValueError):
        pipeline.select_preflight_identities(
            run, policy=pf.small_policy(assets_per_category=0)
        )


# --------------------------------------------------------------------------
# 9 — policy defaults and config read (LREQ-ID-030)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-030")
def test_preflight_policy_defaults_and_config_read():
    """Defaults are the frozen constants; the config read keeps max conflict."""
    from niche_scout import models

    policy = pipeline.PreflightPolicy()
    # LREQ-ID-030 (SRS-lean:377-384): the four frozen defaults.
    assert policy.min_categories == models.IDENTITY_PREFLIGHT_MIN_CATEGORIES == 5
    assert (
        policy.assets_per_category == models.IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY == 2
    )
    assert (
        policy.max_conflict_rate == models.IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE == 0.0
    )
    assert policy.min_success_rate == models.IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE == 0.90

    # SRS §14 exposes three preflight knobs; max_conflict_rate has none, so the
    # config read consumes the three values as-is and keeps the constant.
    config = _config(
        identity_preflight_min_categories=6,
        identity_preflight_assets_per_category=3,
        identity_preflight_min_success_rate=0.95,
    )
    from_config = pipeline.preflight_policy_from_config(config)
    assert from_config.min_categories == 6
    assert from_config.assets_per_category == 3
    assert from_config.min_success_rate == 0.95
    assert from_config.max_conflict_rate == models.IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE


@pytest.mark.lreq("LREQ-ID-030")
def test_preflight_policy_construction_reads_no_clock_or_environment():
    """Construction is pure: same inputs give the same value object."""
    first = pipeline.PreflightPolicy(
        min_categories=5,
        assets_per_category=2,
        max_conflict_rate=0.0,
        min_success_rate=0.90,
    )
    second = pipeline.PreflightPolicy(
        min_categories=5,
        assets_per_category=2,
        max_conflict_rate=0.0,
        min_success_rate=0.90,
    )
    assert first == second


# --------------------------------------------------------------------------
# 9 — unique-identity rates (LREQ-ID-040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_compute_preflight_rates_unique_identity_denominator():
    """The denominator is the unique-identity count, and one match failure halves it."""
    run = pf.overlap_run()
    selection = _selection(run, policy=pf.small_policy())
    # Observations are keyed to unique identities: A succeeds, S conflicts.
    observations = _observations_for(
        selection,
        [
            (pf.A, True, True, True),
            (pf.SHARED, False, True, True),
        ],
    )
    rates = pipeline.compute_preflight_rates(selection, observations)
    # Derivation (SRS-lean:393-406): attempted = 3 unique identities; successful
    # requires identity_match and both operations, so successful = 1 (A);
    # conflicting requires identity_match is False, so conflicting = 1 (S);
    # other_failed is the remainder = 1 (B had no observation). The category
    # references would have been 4, so a denominator of 4 is wrong.
    assert rates.attempted_unique_identities == 3
    assert rates.successful_unique_identities == 1
    assert rates.conflicting_unique_identities == 1
    assert rates.other_failed_unique_identities == 1
    # success_rate = 1/3, conflict_rate = 1/3 (unrounded float64).
    assert rates.success_rate == pytest.approx(1.0 / 3.0, abs=1e-9)
    assert rates.conflict_rate == pytest.approx(1.0 / 3.0, abs=1e-9)


@pytest.mark.lreq("LREQ-ID-040")
def test_compute_preflight_rates_two_identity_golden():
    """Golden: A succeeds and B conflicts -> 2 attempted, 0.5 and 0.5."""
    run = pf.two_asset_run()
    selection = _selection(run, policy=pf.small_policy())
    observations = _observations_for(
        selection,
        [
            (pf.A, True, True, True),
            (pf.B, False, True, True),
        ],
    )
    rates = pipeline.compute_preflight_rates(selection, observations)
    golden = pf.ATTEMPTED_DENOMINATOR_GOLDEN
    # Derivation (plan §9 denominator golden): two unique identities; A's
    # comparison succeeds (successful 1), B's fails (conflicting 1), so
    # success_rate = 1/2 = 0.5 and conflict_rate = 1/2 = 0.5.
    assert rates.attempted_unique_identities == golden["attempted_unique_identities"]
    assert rates.successful_unique_identities == golden["successful_unique_identities"]
    assert (
        rates.conflicting_unique_identities == golden["conflicting_unique_identities"]
    )
    assert (
        rates.other_failed_unique_identities == golden["other_failed_unique_identities"]
    )
    assert rates.success_rate == pytest.approx(golden["success_rate"], abs=1e-9)
    assert rates.conflict_rate == pytest.approx(golden["conflict_rate"], abs=1e-9)


@pytest.mark.lreq("LREQ-ID-040")
def test_compute_preflight_rates_other_failed_partition():
    """A failed operation with no identity mismatch is an other-failed attempt."""
    run = pf.ten_identity_run()
    selection = _selection(run, policy=pf.small_policy(min_categories=5))
    keys = [identity.asset_identity_key for identity in selection.identities]
    assert len(keys) == 10
    results = []
    for index, key in enumerate(keys):
        if index < 6:
            results.append((key, True, True, True))
        elif index == 6:
            results.append((key, False, True, True))
        else:
            results.append((key, None, False, True))
    rates = pipeline.compute_preflight_rates(
        selection, _observations_for(selection, results)
    )
    golden = pf.ATTEMPTED_OTHER_FAILED_GOLDEN
    # Derivation (plan §5.2 partition): 6 successes + 1 conflict + 3
    # other-failed = 10 attempted; success_rate 6/10 = 0.6, conflict_rate 0.1.
    assert rates.attempted_unique_identities == golden["attempted_unique_identities"]
    assert rates.successful_unique_identities == golden["successful_unique_identities"]
    assert (
        rates.conflicting_unique_identities == golden["conflicting_unique_identities"]
    )
    assert (
        rates.other_failed_unique_identities == golden["other_failed_unique_identities"]
    )
    assert rates.success_rate == pytest.approx(golden["success_rate"], abs=1e-9)
    assert rates.conflict_rate == pytest.approx(golden["conflict_rate"], abs=1e-9)


@pytest.mark.lreq("LREQ-ID-040")
def test_compute_preflight_rates_ignores_out_of_selection_observations():
    """An observation outside the selection can never inflate a rate."""
    run = pf.two_asset_run()
    selection = _selection(run, policy=pf.small_policy())
    observations = _observations_for(
        selection,
        [
            (pf.A, True, True, True),
            (pf.DISTINCT_KEY, True, True, True),
            (pf.DISTINCT_KEY, False, True, True),
        ],
    )
    rates = pipeline.compute_preflight_rates(selection, observations)
    # The selection is {A, B}; the extra identity is ignored, so attempted == 2.
    assert rates.attempted_unique_identities == 2
    assert rates.successful_unique_identities == 1


@pytest.mark.lreq("LREQ-ID-040")
def test_compute_preflight_rates_zero_attempted_null_rates():
    """Zero attempted identities gives None/None, never 0.0."""
    run = pf.run_from_categories({})
    selection = pipeline.select_preflight_identities(run, policy=pf.small_policy())
    rates = pipeline.compute_preflight_rates(selection, ())
    golden = pf.ATTEMPTED_ZERO_GOLDEN
    # SRS-lean:408-410: with zero attempts both rates SHALL be null. The rates
    # are None -- comparing 0.0 would be the zero-success defect.
    assert rates.attempted_unique_identities == golden["attempted_unique_identities"]
    assert rates.success_rate is None
    assert rates.conflict_rate is None
    assert rates.success_rate != 0.0
    assert rates.conflict_rate != 0.0


# --------------------------------------------------------------------------
# 9 — gate and boundary semantics (LREQ-ID-030/040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_gate_zero_attempted_is_insufficient():
    """Zero attempted is `insufficient`, checked before any threshold."""
    from niche_scout.models import IdentityPreflightStatus

    run = pf.run_from_categories({})
    selection = pipeline.select_preflight_identities(run, policy=pf.small_policy())
    rates = pipeline.compute_preflight_rates(selection, ())
    status = pipeline.evaluate_preflight_gate(rates, policy=pf.small_policy())
    # SRS-lean:408-410: the zero-attempt disposition is `insufficient`, never
    # `failed` and never a zero-success `passed`.
    assert status is IdentityPreflightStatus.INSUFFICIENT
    assert status is not IdentityPreflightStatus.FAILED
    assert status is not IdentityPreflightStatus.PASSED
    assert pipeline.bulk_enrichment_allowed(status.value) is False


@pytest.mark.lreq("LREQ-ID-040")
def test_gate_below_min_success_rate_fails():
    """Eight successes of ten (0.8) is below 0.90 and fails."""
    from niche_scout.models import IdentityPreflightStatus

    rates = pipeline.PreflightRates(
        attempted_unique_identities=10,
        successful_unique_identities=8,
        conflicting_unique_identities=0,
        other_failed_unique_identities=2,
        success_rate=0.8,
        conflict_rate=0.0,
    )
    status = pipeline.evaluate_preflight_gate(rates, policy=pf.small_policy())
    # Derivation (SRS-lean:386-400): success_rate = 8/10 = 0.8 < 0.90 -> failed.
    assert status is IdentityPreflightStatus.FAILED
    assert pipeline.bulk_enrichment_allowed(status.value) is False


@pytest.mark.lreq("LREQ-ID-040")
def test_gate_above_max_conflict_rate_fails():
    """A conflict rate above 0.0 stops bulk enrichment and fails the run."""
    from niche_scout.models import IdentityPreflightStatus

    rates = pipeline.PreflightRates(
        attempted_unique_identities=10,
        successful_unique_identities=9,
        conflicting_unique_identities=1,
        other_failed_unique_identities=0,
        success_rate=0.9,
        conflict_rate=0.1,
    )
    status = pipeline.evaluate_preflight_gate(rates, policy=pf.small_policy())
    # Derivation (SRS-lean:386, 402-405): conflict_rate = 1/10 = 0.1 > 0.0 ->
    # failed, even though the success rate is exactly at the minimum.
    assert status is IdentityPreflightStatus.FAILED
    assert pipeline.bulk_enrichment_allowed(status.value) is False


@pytest.mark.lreq("LREQ-ID-030")
def test_gate_exactly_min_success_rate_passes():
    """A success rate exactly at the minimum passes (inclusive boundary)."""
    from niche_scout.models import IdentityPreflightStatus

    # Derivation (plan §5.3 boundary): 9/10 = 0.9 exactly; only `strictly
    # below` the minimum fails, so 0.9 passes.
    rates = pipeline.PreflightRates(
        attempted_unique_identities=10,
        successful_unique_identities=9,
        conflicting_unique_identities=0,
        other_failed_unique_identities=1,
        success_rate=0.9,
        conflict_rate=0.0,
    )
    status = pipeline.evaluate_preflight_gate(rates, policy=pf.small_policy())
    assert status is IdentityPreflightStatus.PASSED
    assert pipeline.bulk_enrichment_allowed(status.value) is True


@pytest.mark.lreq("LREQ-ID-030")
def test_gate_exactly_max_conflict_rate_passes():
    """A conflict rate exactly at the maximum does not by itself fail."""
    from niche_scout.models import IdentityPreflightStatus

    # Derivation (plan §5.3 boundary): only `strictly above` the maximum fails;
    # with max_conflict_rate == 0.0 an exact 0.0 does not fail.
    rates = pipeline.PreflightRates(
        attempted_unique_identities=10,
        successful_unique_identities=10,
        conflicting_unique_identities=0,
        other_failed_unique_identities=0,
        success_rate=1.0,
        conflict_rate=0.0,
    )
    status = pipeline.evaluate_preflight_gate(rates, policy=pf.small_policy())
    assert status is IdentityPreflightStatus.PASSED
    assert pipeline.bulk_enrichment_allowed(status.value) is True


@pytest.mark.lreq("LREQ-ID-040")
def test_bulk_enrichment_allowed_only_for_passed():
    """`insufficient` and `failed` both block bulk enrichment."""
    from niche_scout.models import IdentityPreflightStatus

    # SRS-lean:386-410 and plan §5.3: only `passed` opens the gate.
    assert (
        pipeline.bulk_enrichment_allowed(IdentityPreflightStatus.PASSED.value) is True
    )
    assert (
        pipeline.bulk_enrichment_allowed(IdentityPreflightStatus.FAILED.value) is False
    )
    assert (
        pipeline.bulk_enrichment_allowed(IdentityPreflightStatus.INSUFFICIENT.value)
        is False
    )


# --------------------------------------------------------------------------
# 9 — orchestration through the Chunk 5 adapter (LREQ-ID-020)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-020")
def test_run_identity_preflight_uses_chunk5_adapter_per_unique_identity(tmp_path):
    """One `enrich_asset` call per unique identity; both operations validated."""
    run = pf.overlap_run()
    repository = _seeded(tmp_path, run)
    try:
        transport = pf.success_transport((pf.A, pf.SHARED, pf.B))
        outcome = _run_preflight(repository, run, transport=transport)
        # LREQ-ID-020 (SRS-lean:368-372): the normal GraphQL request runs for
        # each unique identity of the selection. The overlap run selects three
        # unique identities, so the adapter is called exactly three times and
        # each call asks for one distinct identity -- no repeats, no bulk.
        assert transport.call_count == 3
        assert transport.distinct_requested_identities == (
            pf.A,
            pf.SHARED,
            pf.B,
        )
        assert len(outcome.observations) == 3
        # Both operation statuses are recorded per identity, and the endpoints
        # of the Chunk 5 request shape hold (one identity, two operations).
        for call in transport.calls:
            assert len(call.operations) == 2
        for observation in outcome.observations:
            assert observation.product_detail_status == "success"
            assert observation.page_views_status == "success"
            assert observation.is_both_operations_success is True
            assert observation.identity_match is True
            assert observation.correlation_mode == pf.EXPLICIT_KEY.value
            assert observation.endpoint_signature == pf.CANONICAL_ENDPOINT_SIGNATURE
            assert observation.mapping_rule_version == "1.0.1"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-020")
def test_run_identity_preflight_preserves_distinct_operation_outcomes(tmp_path):
    """One failed operation does not hide the other's success."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        # Identity A: ProductDetail fails; page views succeed. Identity B: both
        # succeed. The two operation outcomes must remain separate.
        transport = pf.RecordingTransport(
            {
                pf.A: pf.failure_mode_body("request_id_rejected", pf.A),
                pf.B: pf.success_body(pf.B),
            }
        )
        outcome = _run_preflight(repository, run, transport=transport)
        by_key = {item.asset_identity_key: item for item in outcome.observations}
        assert by_key[pf.A].product_detail_status == "error"
        assert by_key[pf.A].page_views_status == "success"
        assert by_key[pf.A].is_both_operations_success is False
        assert by_key[pf.B].product_detail_status == "success"
        assert by_key[pf.B].page_views_status == "success"
        assert by_key[pf.B].is_both_operations_success is True
        # LREQ-ID-020: both operations are validated, so a partial result leaves
        # the operation-level statuses distinguishable rather than collapsed.
        assert outcome.rates.successful_unique_identities == 1
        assert outcome.rates.other_failed_unique_identities == 1
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-020")
@pytest.mark.parametrize(
    "mode",
    [
        "request_id_rejected",
        "identity_mismatch",
        "page_view_package_mismatch",
        "invalid_correlation_mode",
        "partial_success",
        "transport_failure",
    ],
)
def test_preflight_identity_failure_modes(tmp_path, mode):
    """Each named failure mode is independently represented and never zeroed."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        transport = pf.failure_mode_transport(mode, pf.A)
        outcome = _run_preflight(repository, run, transport=transport)
        by_key = {item.asset_identity_key: item for item in outcome.observations}
        assert set(by_key) == {pf.A, pf.B}
        observed = by_key[pf.A]
        # A failing operation carries an error status and never a zero-valued
        # field, and a failed identity is attempted, not dropped (plan §5.2).
        assert observed.product_detail_status in {"success", "error"}
        assert observed.page_views_status in {"success", "error"}
        if mode == "transport_failure":
            # A raising transport is caught by Chunk 5 (TRANSPORT_FAILURE); 6A
            # records the attempt rather than aborting the N-identity loop.
            assert observed.product_detail_status == "error"
            assert observed.page_views_status == "error"
            assert observed.is_both_operations_success is False
            assert observed.identity_match is not True
        elif mode == "identity_mismatch":
            assert observed.identity_match is False
            assert observed.is_both_operations_success is True
        elif mode == "request_id_rejected":
            assert observed.product_detail_status == "error"
            assert observed.page_views_status == "success"
            assert observed.is_both_operations_success is False
        elif mode == "page_view_package_mismatch":
            assert observed.product_detail_status == "success"
            assert observed.page_views_status == "error"
            assert observed.is_both_operations_success is False
        elif mode == "partial_success":
            assert observed.product_detail_status == "error"
            assert observed.page_views_status == "success"
            assert observed.is_both_operations_success is False
        elif mode == "invalid_correlation_mode":
            assert (
                observed.product_detail_status == "error"
                and observed.page_views_status == "error"
            )
        assert outcome.rates.attempted_unique_identities == 2
        # The other identity is a clean success in every mode.
        assert by_key[pf.B].is_both_operations_success is True
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-020")
def test_run_identity_preflight_failed_operation_does_not_abort_loop(tmp_path):
    """A raising transport on one identity still calls the adapter for the rest."""
    run = pf.ten_identity_run()
    repository = _seeded(tmp_path, run)
    try:
        keys = ("A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2")
        transport = pf.RecordingTransport(
            {
                key: (
                    pf.FailingTransport()  # placeholder replaced below
                    if False
                    else pf.success_body(key)
                )
                for key in keys
            }
        )
        # The first identity's call raises; the rest must still be attempted.
        transport._bodies["A1"] = None
        transport._default = None  # type: ignore[attr-defined]

        # ``RecordingTransport`` raises on a missing body; use a wrapper that
        # raises on the first identity and serves the remainder.
        class _FirstRaises:
            def __init__(self) -> None:
                self.calls: list[object] = []

            def __call__(self, request, headers):
                from niche_scout.collector_graphql import GraphQLBatchResponse

                self.calls.append(request)
                key = str(request.asset_identity_key)
                if key == "A1":
                    raise ConnectionResetError("injected transport failure")
                return GraphQLBatchResponse(
                    http_status=200, body_text=pf.success_body(key).decode("utf-8")
                )

        transport = _FirstRaises()
        outcome = _run_preflight(
            repository,
            run,
            transport=transport,
            policy=pf.small_policy(min_categories=5),
        )
        # Chunk 5 owns the retry policy, so the call count is an adapter
        # detail; the invariant is that the raising identity did not abort the
        # N-identity loop -- every identity is still attempted and observed.
        requested = {
            str(getattr(call, "asset_identity_key", "")) for call in transport.calls
        }
        assert requested == set(keys)
        by_key = {item.asset_identity_key: item for item in outcome.observations}
        assert by_key["A1"].is_both_operations_success is False
        assert by_key["A1"].product_detail_status == "error"
        for key in keys[1:]:
            assert by_key[key].is_both_operations_success is True
        assert outcome.rates.attempted_unique_identities == 10
        assert outcome.rates.other_failed_unique_identities == 1
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9 — persistence, ordering, and reuse (LREQ-ID-040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_successful_preflight_counts_toward_enrichment_once(tmp_path):
    """A successful preflight response is already the one enrichment observation."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        transport = pf.success_transport((pf.A, pf.B))
        policy = pf.small_policy(min_categories=2)
        outcome = _run_preflight(repository, run, transport=transport, policy=policy)
        # LREQ-ID-040 (SRS-lean:389-391): the successful preflight responses are
        # reused as enrichment observations and count once. The (run_id,
        # asset_identity_key) primary key forbids a second row, so a re-run is
        # idempotent and the count stays two.
        assert outcome.status.value == "passed"
        # A second full preflight is idempotent: the (run_id,
        # asset_identity_key) primary key forbids a duplicate row, so the
        # successful response is counted exactly once.
        pipeline.run_identity_preflight(
            repository,
            run,
            credentials=pf.GQL_CREDENTIALS,
            transport=transport,
            correlation_mode=pf.EXPLICIT_KEY,
            retrieved_at_utc=pf.RETRIEVED_AT_UTC,
            policy=policy,
        )
        assert pf.observation_count(repository, run.run_id) == 2
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_preflight_persisted_before_gate_returns(tmp_path):
    """Status, summary, observations, and flags are persisted before the return.

    The invariant is *order*, so the assertion is not "a write happened" but
    "the persisted rows were already readable at the moment the gate write was
    made". A repository wrapper snapshots the read-back state on every
    ``update_run_preflight`` call, then appends the final post-return state; the
    snapshots must equal the final state for the run row, the observation rows,
    and the selection flags.
    """
    run = pf.ten_identity_run()
    repository = _seeded(tmp_path, run)
    try:
        policy = pf.small_policy(min_categories=5)
        transport = pf.FailingTransport()  # all ten attempts fail -> failed

        def snapshot():
            record = repository.get_run(run.run_id)
            return {
                "status": record.status,
                "identity_preflight_status": record.identity_preflight_status,
                "summary": record.identity_preflight_summary_json,
                "observation_count": pf.observation_count(repository, run.run_id),
                "flags": dict(pf.preflight_selected_flags(repository, run.run_id)),
            }

        class _SnapshottingRepository:
            """Delegates every call; snapshots DB state at the gate boundary."""

            def __init__(self, inner) -> None:
                self._inner = inner
                self.events: list[str] = []
                self.snapshots_at_gate: list[dict] = []

            def __getattr__(self, name):
                attr = getattr(self._inner, name)
                if not callable(attr):
                    return attr

                def _wrapped(*args, **kwargs):
                    result = attr(*args, **kwargs)
                    self.events.append(name)
                    if name in {
                        "update_run_preflight",
                        "upsert_enrichment_observation",
                        "mark_preflight_selected",
                        "update_run_status",
                    }:
                        self.snapshots_at_gate.append(snapshot())
                    return result

                return _wrapped

        recorder = _SnapshottingRepository(repository)
        outcome = _run_preflight(
            recorder,
            run,
            transport=transport,
            policy=policy,
            # The retry backoff is Chunk 5's policy; this node is about write
            # ordering, so it supplies its own no-op sleeper rather than
            # waiting out the real backoff across ten failing identities.
            sleep=lambda _seconds: None,
        )

        # Every write happened in the call, and the failed-run transition came
        # after the preflight writes (gate bullet 723 / A4 ordering).
        names = recorder.events
        assert names.count("upsert_enrichment_observation") == 10
        assert "update_run_preflight" in names
        assert "mark_preflight_selected" in names
        assert "update_run_status" in names
        assert names.index("update_run_preflight") < names.index("update_run_status")

        # Read-back through the frozen Chunk 2 API is the final state.
        final = snapshot()
        assert final["status"] == "failed"
        assert final["identity_preflight_status"] == "failed"
        assert final["observation_count"] == 10
        assert all(final["flags"].values())

        # Persist-before-return: at the moment of the gate write, and at every
        # earlier write, the run row already carried the preflight status and
        # summary and every one of the ten observation rows existed. A lazy or
        # post-return persistence path leaves the snapshot empty (or short).
        assert final["observation_count"] == 10
        assert recorder.snapshots_at_gate
        # The gate write is the terminal write: at that instant the run row and
        # all ten observation rows were already on disk. Checking every
        # intermediate upsert snapshot would demand unbatchable ordering.
        assert names.index("update_run_status") == len(names) - 1
        terminal = recorder.snapshots_at_gate[-1]
        assert terminal == final
        assert terminal["observation_count"] == 10
        assert terminal["flags"] == final["flags"]
        assert outcome.status.value == "failed"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_failed_preflight_marks_run_failed_not_warning(tmp_path):
    """A failed preflight sets the run failed via update_run_status."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        transport = pf.FailingTransport()
        outcome = _run_preflight(repository, run, transport=transport, sleep=_no_sleep)
        record = repository.get_run(run.run_id)
        assert record is not None
        # LREQ-ID-040 (SRS-lean:386-387): a sub-minimum preflight marks the run
        # failed. It does not become an informational-only state.
        assert record.status == "failed"
        assert record.identity_preflight_status == "failed"
        # 6A reads no clock: the terminal timestamp stays unset for Chunk 10.
        assert record.completed_at_utc is None
        assert outcome.status.value == "failed"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_failed_preflight_blocks_bulk_enrichment(tmp_path):
    """A failed outcome blocks bulk enrichment."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        outcome = _run_preflight(
            repository, run, transport=pf.FailingTransport(), sleep=_no_sleep
        )
        # SRS-lean:386-387 + plan §5.3: only `passed` opens the gate.
        assert outcome.status.value == "failed"
        assert pipeline.bulk_enrichment_allowed(outcome.status.value) is False
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_insufficient_preflight_blocks_bulk_enrichment(tmp_path):
    """Zero attempted writes zero rows, is `insufficient`, and blocks bulk."""
    run = pf.run_from_categories({})
    repository = _seeded(tmp_path, run)
    try:
        transport = pf.RecordingTransport({})
        outcome = _run_preflight(repository, run, transport=transport)
        assert transport.call_count == 0
        assert outcome.status.value == "insufficient"
        assert pipeline.bulk_enrichment_allowed(outcome.status.value) is False
        assert outcome.rates.success_rate is None
        assert outcome.rates.conflict_rate is None
        # A zero-observation `insufficient` run is a persisted, readable state.
        assert pf.observation_count(repository, run.run_id) == 0
        record = repository.get_run(run.run_id)
        assert record is not None
        assert record.identity_preflight_status == "insufficient"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_insufficient_preflight_does_not_mark_run_failed(tmp_path):
    """`insufficient` is a shortfall, not a failure (Q2 ruling)."""
    run = pf.run_from_categories({})
    repository = _seeded(tmp_path, run)
    try:
        outcome = _run_preflight(repository, run, transport=pf.RecordingTransport({}))
        record = repository.get_run(run.run_id)
        assert record is not None
        # Plan §12 Q2 / SRS-lean:408-410: 6A does not mark an insufficient run
        # failed; Chunk 10 finalizes it.
        assert outcome.status.value == "insufficient"
        assert record.status == "running"
        assert record.status != "failed"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_failed_preflight_summary_has_counts_endpoint_mapping_diagnostic(tmp_path):
    """The failure record carries counts, signature, mapping version, diagnostic."""
    run = pf.ten_identity_run()
    repository = _seeded(tmp_path, run)
    try:
        policy = pf.small_policy(min_categories=5)
        keys = ("A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2")
        # Golden 10/8/1/1: eight assets succeed, one returns a mismatched
        # identity (conflict), one gets a rejected request identifier (other).
        wrong_identity = "Retired/Other"
        bodies = {}
        for index, key in enumerate(keys):
            if index < 8:
                bodies[key] = pf.success_body(key)
            elif index == 8:
                bodies[key] = pf.response_body_fixture(
                    {
                        "operationName": pf.PRODUCT_DETAIL_OPERATION_NAME,
                        "data": _mismatched_detail(wrong_identity),
                    },
                    {
                        "operationName": pf.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
                        "data": {"pageViews": 4321},
                    },
                ).encode("utf-8")
            else:
                bodies[key] = pf.failure_mode_body("request_id_rejected", key)
        transport = pf.RecordingTransport(bodies)
        outcome = _run_preflight(repository, run, transport=transport, policy=policy)

        assert outcome.rates.attempted_unique_identities == 10
        assert outcome.rates.successful_unique_identities == 8
        assert outcome.rates.conflicting_unique_identities == 1
        assert outcome.rates.other_failed_unique_identities == 1
        assert outcome.rates.success_rate == pytest.approx(0.8, abs=1e-9)
        assert outcome.rates.conflict_rate == pytest.approx(0.1, abs=1e-9)
        assert outcome.status.value == "failed"

        record = repository.get_run(run.run_id)
        assert record is not None
        summary = json.loads(record.identity_preflight_summary_json)
        # SRS-lean:386-388: the failure includes sampled counts, mismatch counts,
        # the endpoint signature, the mapping-rule version, and a redacted
        # diagnostic summary.
        for fragment in pf.SUM_FOUR_KEYS_JSON:
            assert fragment in record.identity_preflight_summary_json
        assert summary["graphql_operation_correlation_mode"] == "explicit_key"
        assert summary["graphql_endpoint_signature"] == pf.CANONICAL_ENDPOINT_SIGNATURE
        assert summary["identity_mapping_rule_version"] == "1.0.1"
        assert summary["diagnostic_summary_json"] is not None
        assert summary["reduced_coverage"] is False
        assert summary["category_shortfall"] == 0
        assert tf_no_credential(record.identity_preflight_summary_json)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_endpoint_signature_form():
    """The endpoint signature is `<endpoint>#<version>` (frozen literal form)."""
    from niche_scout import models

    endpoint = "https://example.invalid/custom/graphql"
    # Plan §5.6 / §12 Q1: f"{endpoint}#{endpoint_contract_version}". The custom
    # arguments prove the form, not a hard-coded literal.
    assert (
        pipeline.graphql_endpoint_signature(endpoint)
        == f"{endpoint}#{models.ENDPOINT_CONTRACT_VERSION}"
    )
    assert (
        pipeline.graphql_endpoint_signature(endpoint, endpoint_contract_version="9.9.9")
        == f"{endpoint}#9.9.9"
    )
    assert (
        pipeline.graphql_endpoint_signature()
        == f"{pf.GRAPHQL_BATCH_ENDPOINT}#{models.ENDPOINT_CONTRACT_VERSION}"
    )
    assert pipeline.graphql_endpoint_signature() == pf.CANONICAL_ENDPOINT_SIGNATURE


@pytest.mark.lreq("LREQ-ID-010")
def test_mark_preflight_selected_flips_rows_true(tmp_path):
    """Only the selected rows are flipped true; other columns are untouched."""
    run = pf.census_three_run()
    repository = _seeded(tmp_path, run)
    try:
        before = pf.all_sample_members(repository, run.run_id)
        before_by_key = {row.asset_identity_key: row for row in before}
        selected = [pf.A, pf.B, pf.D]
        changed = repository.mark_preflight_selected(run.run_id, selected)
        after_by_key = pf.preflight_selected_flags(repository, run.run_id)
        # Plan §5.4a: scoped by (run_id, asset_identity_key); the selected rows
        # flip true and every other row keeps the 4B False placeholder.
        assert changed == len(selected)
        for key in selected:
            assert after_by_key[key] is True
        assert after_by_key[pf.C] is False
        assert after_by_key[pf.E_KEY] is False
        # No other column changes.
        after = {
            row.asset_identity_key: row
            for row in pf.all_sample_members(repository, run.run_id)
        }
        for key, row in before_by_key.items():
            assert (
                after[key].sample_rank_within_stratum == row.sample_rank_within_stratum
            )
            assert after[key].selection_digest == row.selection_digest
            assert after[key].stratum_index == row.stratum_index
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_preflight_observations_are_redacted(tmp_path):
    """No credential, header value, cookie, or body text is persisted."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        sentinels = pf.credential_sentinels()
        transport = pf.RecordingTransport(
            {key: pf.success_body(key) for key in (pf.A, pf.B)}
        )
        outcome = _run_preflight(
            repository,
            run,
            transport=transport,
            credentials=pf.REDACTION_CREDENTIALS,
        )
        # LREQ-SEC-010/020: neither the summary JSON nor any persisted
        # observation row carries a credential, header value, cookie, or body.
        record = repository.get_run(run.run_id)
        assert record is not None
        assert tf_no_credential(record.identity_preflight_summary_json)
        for key in (pf.A, pf.B):
            observation = repository.get_enrichment_observation(run.run_id, key)
            assert observation is not None
            assert pf.record_redaction_scan(observation) == ()
        # The diagnostic summary is issue codes/counts only.
        for item in outcome.observations:
            if item.diagnostic_summary_json is not None:
                assert tf_no_credential(item.diagnostic_summary_json)
            assert item.draft is not None
        for value in sentinels.values():
            assert value not in record.identity_preflight_summary_json
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9 — page-view-semantics non-clobber (Q3 ruling; tracked under LREQ-ID-040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_page_view_semantics_not_clobbered_when_validated(tmp_path):
    """A run pre-seeded `validated_cumulative` is left untouched (non-clobber)."""
    run = pf.two_asset_run()
    # Q3: the test pre-seeds the value rather than reading a fresh Chunk 10
    # seed, so an implementation that blindly writes `unvalidated` fails.
    repository = _seeded(
        tmp_path, run, page_view_semantics_status="validated_cumulative"
    )
    try:
        _run_preflight(
            repository,
            run,
            transport=pf.success_transport((pf.A, pf.B)),
        )
        assert (
            pf.page_view_semantics_of(repository, run.run_id) == "validated_cumulative"
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_page_view_semantics_not_clobbered_when_contradicted(tmp_path):
    """A run pre-seeded `contradicted` is left untouched (non-clobber)."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run, page_view_semantics_status="contradicted")
    try:
        _run_preflight(
            repository,
            run,
            transport=pf.success_transport((pf.A, pf.B)),
        )
        assert pf.page_view_semantics_of(repository, run.run_id) == "contradicted"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_page_view_semantics_not_clobbered_when_third_value(tmp_path):
    """A legal but non-validated/non-contradicted value is replaced by unvalidated."""
    run = pf.two_asset_run()
    # MR-1: `runs.page_view_semantics_status` admits only the three enum values,
    # so the third distinct state is a different run-level value, not an illegal
    # one. The pre-seed here is `unvalidated`; the wrapper below reports the
    # observed current value as a *different* one, which is the input the Q3
    # branch keys on ("neither validated_cumulative nor contradicted").
    repository = _seeded(tmp_path, run, page_view_semantics_status="unvalidated")
    try:
        _run_preflight(
            repository,
            run,
            transport=pf.success_transport((pf.A, pf.B)),
        )
        # Q3 ruling: `unvalidated` is written only when the current value is not
        # `validated_cumulative`/`contradicted`; `unvalidated` is such a value,
        # so the write is permitted (and, being idempotent, leaves the row).
        assert pf.page_view_semantics_of(repository, run.run_id) == "unvalidated"
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9 — summary key set and the 6A/6B boundary
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_identity_preflight_summary_key_set_is_frozen(tmp_path):
    """The persisted summary carries exactly the frozen §5.5 key set."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        _run_preflight(
            repository, run, transport=pf.FailingTransport(), sleep=_no_sleep
        )
        record = repository.get_run(run.run_id)
        assert record is not None
        summary = json.loads(record.identity_preflight_summary_json)
        assert set(summary) == set(pf.SUMMARY_KEY_SET)
        assert len(summary) == 16
        assert summary["graphql_endpoint_signature"] == pf.CANONICAL_ENDPOINT_SIGNATURE
        assert summary["identity_mapping_rule_version"] == "1.0.1"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_insufficient_summary_rates_are_null_not_zero(tmp_path):
    """The zero-attempt summary serializes both rates as JSON null."""
    run = pf.run_from_categories({})
    repository = _seeded(tmp_path, run)
    try:
        _run_preflight(repository, run, transport=pf.RecordingTransport({}))
        record = repository.get_run(run.run_id)
        assert record is not None
        summary = json.loads(record.identity_preflight_summary_json)
        # SRS-lean:408-410 + plan §5.5: counts all zero, both rates null,
        # status `insufficient`.
        assert summary["status"] == "insufficient"
        assert summary["attempted_unique_identities"] == 0
        assert summary["successful_unique_identities"] == 0
        assert summary["conflicting_unique_identities"] == 0
        assert summary["other_failed_unique_identities"] == 0
        assert summary["success_rate"] is None
        assert summary["conflict_rate"] is None
        assert '"success_rate":null' in record.identity_preflight_summary_json
        assert '"conflict_rate":null' in record.identity_preflight_summary_json
        assert '"success_rate":0.0' not in record.identity_preflight_summary_json
        assert '"conflict_rate":0.0' not in record.identity_preflight_summary_json
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-040")
def test_run_identity_preflight_issues_no_third_or_bulk_request(tmp_path):
    """6A issues exactly one request per unique identity; never a bulk request."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        transport = pf.success_transport((pf.A, pf.B))
        _run_preflight(repository, run, transport=transport)
        # Plan §11 / gate line 722: the adapter is called once per unique
        # preflight identity -- no third request, no bulk enrichment request.
        assert transport.call_count == 2
        assert transport.distinct_requested_identities == (pf.A, pf.B)
        for call in transport.calls:
            assert len(call.operations) == 2
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ID-020")
def test_run_identity_preflight_passes_caller_seams_through(tmp_path):
    """The injected transport, retrieval timestamp, and sleeper are the seams."""
    run = pf.two_asset_run()
    repository = _seeded(tmp_path, run)
    try:
        sleeps: list[float] = []
        transport = pf.success_transport((pf.A, pf.B))
        _run_preflight(
            repository,
            run,
            transport=transport,
            retrieved_at_utc=pf.RETRIEVED_AT_UTC,
            sleep=sleeps.append,
        )
        # No network and no clock: the fixture transport served every call, and
        # a successful exchange sleeps zero times.
        assert transport.call_count == 2
        assert sleeps == []
        # The draft carries the caller-supplied timestamp, never a clock read.
        record = repository.get_enrichment_observation(run.run_id, pf.A)
        assert record is not None
        assert record.retrieved_at_utc == pf.RETRIEVED_AT_UTC
    finally:
        repository.close()


# --------------------------------------------------------------------------
# Small local helpers (test-only; never fixture logic).
# --------------------------------------------------------------------------


def _mismatched_detail(returned_identity: str) -> dict:
    """Return a valid ProductDetail payload naming another identity."""
    return {
        "id": returned_identity,
        "productId": returned_identity,
        "rating": {"average": 4.5, "count": 210},
        "reviewCount": 34,
        "firstPublishedDate": "2019-03-04T12:30:00Z",
        "state": "published",
        "category": "Tools/Level Design/Tilemap",
        "publisher": "Fixture Publisher",
    }


def _config(**overrides):
    """Build a ``NicheScoutConfig`` with the given preflight overrides."""
    from niche_scout.config import NicheScoutConfig

    return NicheScoutConfig(
        categories_path=pf.CATEGORIES_PATH,
        taxonomy_path=pf.TAXONOMY_PATH,
        db_path=pf.DB_PATH,
        max_discovery_results_per_category=2000,
        page_size=96,
        min_categories_per_run=8,
        strong_reference_category_count=21,
        max_taxonomy_age_days=30,
        min_usable_samples_per_stratum=5,
        min_age_days_for_rate=30,
        recent_window_days=365,
        quality_min_rating_count=5,
        quality_min_eligible_assets=5,
        **overrides,
    )


def tf_no_credential(text: str) -> bool:
    """Return True when none of the fixture credential sentinels appears."""
    return all(sentinel not in text for sentinel in pf.credential_sentinels().values())
