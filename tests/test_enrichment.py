"""Analytical tests for chunk 6B §5.1-§5.3 — union, projection, execution.

Source of truth: ``Documents/SRS-lean.md`` §4.2 (``LREQ-GQL-080``) and §11
(``LREQ-NFR-020``/``LREQ-NFR-030``), and the frozen plan
``Documents/plans/chunk-6B-unique-enrichment-executor-and-persistence.md`` §5 and
§9. Every node carries one of the four markers ``LREQ-GQL-080``,
``LREQ-NFR-020``, ``LREQ-NFR-030``, ``LREQ-SMP-080`` with a matching
``tests/traceability.json`` entry keyed by its base node ID (plan §9).
``LREQ-TST-030/040/080`` are Chunk 13's marker pass and are not attached here.

Golden values are hand-derived from the plan §9 vectors, never read off the
implementation: the overlap union has three unique members and five category
references; the reuse split leaves two pending; the projection is
``pending * interval``.

No network, no credentials, no clock reads, and no ``sqlite3``: the transport
and the retrieval timestamp are caller-injected, and the repository is a
pytest ``tmp_path`` SQLite seeded through the frozen Chunk 2 persistence paths.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import timedelta, timezone

import pytest
from fixtures import enrichment_fixtures as ef

import niche_scout.metrics as metrics
import niche_scout.pipeline as pipeline
from niche_scout.models import (
    MIN_USABLE_SAMPLES_PER_STRATUM,
    PageViewSemanticsStatus,
)

# --------------------------------------------------------------------------
# Helpers (pure wiring; no assertions on behavior under test).
# --------------------------------------------------------------------------


def _open(tmp_path):
    """Open a fresh repository under ``tmp_path`` (no live path, no network)."""
    from niche_scout import database

    return database.SqliteRepository(tmp_path / "chunk6b.sqlite")


def _seeded(tmp_path, run):
    """Open a repository and insert the run row through the frozen path."""
    repository = _open(tmp_path)
    ef.seed_run(repository, run)
    return repository


def _union(run, already_enriched=()):
    """Call ``compute_enrichment_union`` with the reuse key set."""
    return pipeline.compute_enrichment_union(
        run, already_enriched_keys=set(already_enriched)
    )


def _projection(union, *, interval=ef.PROJECTION_INTERVAL):
    """Call ``build_enrichment_projection`` with the frozen fixture counts."""
    return pipeline.build_enrichment_projection(
        union,
        discovered_canonical_assets=10,
        sampled_assets=len(union.members),
        per_request_interval_seconds=interval,
    )


def _no_sleep(_seconds: float) -> None:
    """Supply a no-op sleeper so retry backoff never slows an isolation node."""


def _by_reuse(union) -> dict[str, bool]:
    """Return ``{identity: reused_from_preflight}`` for the union members."""
    return {
        member.asset_identity_key: member.reused_from_preflight
        for member in union.members
    }


def _enrich(
    repository, run, union, projection, transport, *, preflight_status="passed"
):
    """Call ``enrich_unique_identities`` with the frozen signature seams."""
    return pipeline.enrich_unique_identities(
        repository,
        run,
        preflight_status=preflight_status,
        credentials=ef.GQL_CREDENTIALS,
        transport=transport,
        correlation_mode=ef.EXPLICIT_KEY,
        retrieved_at_utc=ef.RETRIEVED_AT_UTC,
        union=union,
        projection=projection,
        sleep=_no_sleep,
    )


# --------------------------------------------------------------------------
# 9 — §5.1 union and reuse (LREQ-GQL-080)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-080")
def test_union_overlapping_categories_dedups_identities():
    """A shared identity appears once in the union, not once per category."""
    run = ef.overlap_run()
    union = _union(run)
    # Plan §9 overlap golden (E1): A is in categories 1 and 2, B in 2 and 3, C
    # in 3; the union is the three unique identities (A, B, C).
    keys = tuple(member.asset_identity_key for member in union.members)
    assert keys == ef.OVERLAP_MEMBERS
    assert len(union.members) == len(set(keys)) == ef.OVERLAP_EXECUTED_CALLS
    # The union order matches the 4A convenience view exactly.
    assert keys == run.enrichment_identity_keys
    assert union.run_id == run.run_id


@pytest.mark.lreq("LREQ-GQL-080")
def test_union_preserves_first_seen_order_and_source_categories():
    """The union keeps first-seen order and carries every referencing category."""
    run = ef.overlap_run()
    union = _union(run)
    # Plan §9 overlap golden: first-seen order is (A, B, C) in
    # (category order, member order); A is claimed by category 1 first.
    assert tuple(member.union_rank for member in union.members) == (1, 2, 3)
    by_key = {member.asset_identity_key: member for member in union.members}
    assert by_key["A"].source_categories == (ef.CATEGORY_1, ef.CATEGORY_2)
    assert by_key["A"].first_category == ef.CATEGORY_1
    assert by_key["B"].source_categories == (ef.CATEGORY_2, ef.CATEGORY_3)
    assert by_key["B"].first_category == ef.CATEGORY_2
    assert by_key["C"].source_categories == (ef.CATEGORY_3,)
    assert by_key["C"].first_category == ef.CATEGORY_3


@pytest.mark.lreq("LREQ-GQL-080")
def test_union_reuse_split_excludes_preflight_keys():
    """Reuse keys partition the members and are excluded from pending."""
    run = ef.overlap_run()
    union = _union(run, ef.REUSE_KEYS)
    # Plan §9 reuse golden (E2): A is already persisted by the preflight, so it
    # is reuse-only and the remainder (B, C) is pending.
    assert union.reuse_keys == ef.REUSE_KEYS
    assert union.pending_keys == ef.PENDING_KEYS
    assert set(union.reuse_keys).isdisjoint(union.pending_keys)
    assert set(union.reuse_keys) | set(union.pending_keys) == set(ef.OVERLAP_MEMBERS)
    assert _by_reuse(union) == {"A": True, "B": False, "C": False}


@pytest.mark.lreq("LREQ-GQL-080")
def test_union_reference_count_never_inflates_execution(tmp_path):
    """Five category references execute three requests, never five."""
    run = ef.overlap_run()
    union = _union(run)
    # Plan §9 overlap golden: category references sum to 5 (1 + 2 + 2) while the
    # unique identities -- and so the executions -- are 3.
    assert union.category_reference_count == ef.OVERLAP_CATEGORY_REFERENCE_COUNT
    assert len(union.members) == ef.OVERLAP_EXECUTED_CALLS
    repository = _seeded(tmp_path, run)
    try:
        transport = ef.success_transport(ef.OVERLAP_MEMBERS)
        report = _enrich(repository, run, union, _projection(union), transport)
        assert transport.call_count == ef.OVERLAP_EXECUTED_CALLS
        assert report.executed_identity_count == ef.OVERLAP_EXECUTED_CALLS
        assert report.executed_identity_count != union.category_reference_count
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9 — §5.2 projection and logging (LREQ-NFR-020)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-020")
def test_projection_minimum_seconds_from_interval():
    """The projection is pending count times the caller's interval."""
    run = ef.overlap_run()
    union = _union(run, ef.REUSE_KEYS)
    assert union.pending_keys == ef.PENDING_KEYS
    projection = _projection(union, interval=ef.PROJECTION_INTERVAL)
    # Plan §9 projection golden: 2 pending * 0.5 s = 1.0 s, and the four
    # LREQ-NFR-020 quantities are the reuse/pending split.
    assert projection.pending_enrichment_identities == ef.PROJECTION_PENDING
    assert projection.per_request_interval_seconds == pytest.approx(
        ef.PROJECTION_INTERVAL
    )
    assert projection.projected_minimum_enrichment_seconds == pytest.approx(
        ef.PROJECTION_MINIMUM_SECONDS, abs=1e-9
    )
    assert projection.unique_enrichment_identities == len(union.members)
    assert projection.reused_preflight_identities == len(union.reuse_keys)
    assert projection.unique_enrichment_identities == (
        projection.reused_preflight_identities
        + projection.pending_enrichment_identities
    )


@pytest.mark.lreq("LREQ-NFR-020")
def test_projection_zero_pending_is_measured_zero():
    """No pending identities yields a measured 0.0, never None."""
    run = ef.overlap_run()
    union = _union(run, ef.all_reused_keys())
    assert union.pending_keys == ()
    projection = _projection(union, interval=ef.PROJECTION_INTERVAL)
    # Plan §9 projection golden: pending == 0 -> 0.0 for any interval.
    assert projection.pending_enrichment_identities == 0
    assert projection.projected_minimum_enrichment_seconds == 0.0
    assert projection.projected_minimum_enrichment_seconds is not None
    zero_interval = _projection(union, interval=0.0)
    assert zero_interval.projected_minimum_enrichment_seconds == 0.0


@pytest.mark.lreq("LREQ-NFR-020")
def test_projection_log_line_contains_no_credential_or_identity(caplog):
    """The single log line carries counts only, never a secret or identity."""
    run = ef.overlap_run()
    union = _union(run, ef.REUSE_KEYS)
    projection = _projection(union)
    with caplog.at_level(logging.INFO, logger="niche_scout.pipeline"):
        pipeline.log_enrichment_projection(projection)
    messages = [record.getMessage() for record in caplog.records]
    # LREQ-NFR-020 / LREQ-SEC-010/020: exactly one line with the four named
    # quantities, and no credential, cookie, header value, body marker, identity
    # key, or category string.
    assert len(messages) == 1
    line = messages[0]
    assert "pre-enrichment projection" in line
    assert str(projection.pending_enrichment_identities) in line
    for sentinel in ef.CREDENTIAL_SENTINELS:
        assert sentinel not in line
    for identity in ef.OVERLAP_MEMBERS:
        assert identity not in line
    for category in (ef.CATEGORY_1, ef.CATEGORY_2, ef.CATEGORY_3):
        assert category not in line


# --------------------------------------------------------------------------
# 9 — §5.3 execution (LREQ-GQL-080, LREQ-NFR-020, LREQ-NFR-030)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-080")
def test_enrich_executes_one_request_per_pending_identity(tmp_path):
    """Each pending identity is requested exactly once, in pending order."""
    run = ef.overlap_run()
    union = _union(run)
    repository = _seeded(tmp_path, run)
    try:
        transport = ef.success_transport(ef.OVERLAP_MEMBERS)
        report = _enrich(repository, run, union, _projection(union), transport)
        # Plan §9 overlap golden: three pending identities, one call each.
        assert transport.call_count == ef.OVERLAP_EXECUTED_CALLS
        assert transport.requested_identities == ef.OVERLAP_MEMBERS
        assert transport.distinct_requested_identities == ef.OVERLAP_MEMBERS
        assert report.executed_identity_count == ef.OVERLAP_EXECUTED_CALLS
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-GQL-080")
def test_enrich_does_not_request_reused_preflight_identities(tmp_path):
    """A persisted preflight identity is reused, never requested again."""
    run = ef.overlap_run()
    repository = _seeded(tmp_path, run)
    try:
        repository.upsert_enrichment_observation(ef.observation_record(run.run_id, "A"))
        before = repository.get_enrichment_observation(run.run_id, "A")
        union = _union(run, ef.REUSE_KEYS)
        transport = ef.success_transport(ef.PENDING_KEYS)
        report = _enrich(repository, run, union, _projection(union), transport)
        # Plan §9 reuse golden (E2): only B and C are requested; A keeps its
        # preflight row byte-identical.
        assert transport.requested_identities == ef.PENDING_KEYS
        assert "A" not in transport.requested_identities
        assert transport.call_count == ef.REUSE_EXECUTED_CALLS
        assert report.reused_identity_count == len(ef.REUSE_KEYS)
        assert report.executed_identity_count == ef.REUSE_EXECUTED_CALLS
        after = repository.get_enrichment_observation(run.run_id, "A")
        assert after == before
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-NFR-030")
def test_enrich_failed_asset_does_not_abort_unrelated_assets(tmp_path):
    """One failed asset is persisted and the remaining identities still run."""
    run = ef.overlap_run()
    union = _union(run)
    repository = _seeded(tmp_path, run)
    try:
        transport = ef.mixed_transport(("B", "C"), failing=("A",))
        report = _enrich(repository, run, union, _projection(union), transport)
        # LREQ-NFR-030 (SRS-lean:1168-1169): A's transport failure is persisted
        # and never aborts B or C; failures stay visible in the observation. The
        # failing identity may be retried by the Chunk 5 policy, so the isolation
        # invariant is the distinct identity set, not the raw call count.
        assert transport.distinct_requested_identities == ef.OVERLAP_MEMBERS
        assert set(transport.requested_identities) == set(ef.OVERLAP_MEMBERS)
        assert report.executed_identity_count == ef.OVERLAP_EXECUTED_CALLS
        assert report.persisted_identity_count == ef.OVERLAP_EXECUTED_CALLS
        assert report.failed_identity_count == 1
        failed = repository.get_enrichment_observation(run.run_id, "A")
        assert failed is not None
        assert failed.product_detail_status == "error"
        assert failed.page_views_status == "error"
        for key in ("B", "C"):
            observation = repository.get_enrichment_observation(run.run_id, key)
            assert observation is not None
            assert observation.product_detail_status == "success"
            assert observation.page_views_status == "success"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-GQL-080")
def test_enrich_persists_every_pending_identity_observation(tmp_path):
    """Every pending identity is upserted and read back as one row."""
    run = ef.overlap_run()
    union = _union(run)
    repository = _seeded(tmp_path, run)
    try:
        transport = ef.success_transport(ef.OVERLAP_MEMBERS)
        report = _enrich(repository, run, union, _projection(union), transport)
        # Gate line 763: the persisted row count equals the union size and every
        # member has its own (run_id, asset_identity_key) observation.
        assert report.persisted_identity_count == len(union.members)
        assert repository.count_distinct_enrichment_identities(run.run_id) == len(
            union.members
        )
        for key in ef.OVERLAP_MEMBERS:
            observation = repository.get_enrichment_observation(run.run_id, key)
            assert observation is not None
            assert observation.asset_identity_key == key
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-GQL-080")
def test_enrich_failed_preflight_issues_zero_requests(tmp_path):
    """A failed preflight issues zero requests and writes nothing."""
    run = ef.overlap_run()
    union = _union(run)
    repository = _seeded(tmp_path, run)
    try:
        transport = ef.success_transport(ef.OVERLAP_MEMBERS)
        report = _enrich(
            repository,
            run,
            union,
            _projection(union),
            transport,
            preflight_status="failed",
        )
        # Gate line 761: the failed branch is a persisted, readable state, not an
        # exception; zero requests and zero rows.
        assert transport.call_count == 0
        assert report.executed_identity_count == 0
        assert report.persisted_identity_count == 0
        assert report.failed_identity_count == 0
        assert report.reused_identity_count == 0
        assert repository.count_distinct_enrichment_identities(run.run_id) == 0
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-GQL-080")
def test_enrich_insufficient_preflight_issues_zero_requests(tmp_path):
    """An insufficient preflight issues zero requests, reporting reuse only."""
    run = ef.overlap_run()
    repository = _seeded(tmp_path, run)
    try:
        repository.upsert_enrichment_observation(ef.observation_record(run.run_id, "A"))
        union = _union(run, ef.REUSE_KEYS)
        transport = ef.success_transport(ef.PENDING_KEYS)
        report = _enrich(
            repository,
            run,
            union,
            _projection(union),
            transport,
            preflight_status="insufficient",
        )
        # Gate line 761: no bulk request on `insufficient`; the already-persisted
        # preflight row is reported as reuse, not as a new execution.
        assert transport.call_count == 0
        assert report.executed_identity_count == 0
        assert report.persisted_identity_count == 0
        assert report.failed_identity_count == 0
        assert report.reused_identity_count == len(ef.REUSE_KEYS)
        assert repository.count_distinct_enrichment_identities(run.run_id) == 1
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-NFR-020")
def test_enrich_logs_projection_before_first_request(tmp_path, caplog):
    """The projection line is emitted before the first bulk request."""
    run = ef.overlap_run()
    union = _union(run)
    repository = _seeded(tmp_path, run)
    logged_at_call: list[bool] = []

    def _snapshot(_key: str) -> None:
        logged_at_call.append(
            any(
                "pre-enrichment projection" in record.getMessage()
                for record in caplog.records
            )
        )

    try:
        transport = ef.EnrichmentTransport(
            ef.success_bodies(ef.OVERLAP_MEMBERS), on_call=_snapshot
        )
        with caplog.at_level(logging.INFO, logger="niche_scout.pipeline"):
            _enrich(repository, run, union, _projection(union), transport)
        # LREQ-NFR-020: the log statement precedes bulk enrichment, so at every
        # request the projection was already recorded.
        assert len(logged_at_call) == ef.OVERLAP_EXECUTED_CALLS
        assert all(logged_at_call)
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9 — §5.4 cutoff capture and finalization (LREQ-SMP-080)
# --------------------------------------------------------------------------


def _finalize(
    category,
    observations,
    *,
    cutoff=ef.SCORING_CUTOFF_UTC,
    semantics=PageViewSemanticsStatus.UNVALIDATED,
    **overrides,
):
    """Call ``finalize_stratum_counts`` with the frozen fixture cutoff.

    ``overrides`` carries the additive chunk-21 policy parameters
    (``min_usable_samples_per_stratum``, ``min_age_days_for_rate``,
    ``quality_min_rating_count``) for the non-default tests only.
    """
    return pipeline.finalize_stratum_counts(
        category,
        observations,
        scoring_cutoff_utc=cutoff,
        page_view_semantics_status=semantics,
        **overrides,
    )


def _finalize_enrichment(repository, run, union, **overrides):
    """Call ``finalize_enrichment`` with the fixed caller-supplied timestamps.

    ``overrides`` carries the additive chunk-21 policy parameters for the
    non-default tests only; an empty mapping keeps the frozen default call.
    """
    return pipeline.finalize_enrichment(
        repository,
        run,
        scoring_cutoff_utc=ef.SCORING_CUTOFF_UTC,
        computed_at_utc=ef.RETRIEVED_AT_UTC,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
        union=union,
        **overrides,
    )


def _assert_consistency(repository, run, report):
    """Call ``assert_finalization_consistency`` with the frozen fixture cutoff."""
    return pipeline.assert_finalization_consistency(
        repository,
        run,
        report,
        scoring_cutoff_utc=ef.SCORING_CUTOFF_UTC,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
    )


def _chunk7b_metric_inputs(repository, run, category):
    """Build the Chunk 7B inputs from the persisted members and observations.

    Field copy only, mirroring the production call: a null stays null (hard
    rule 2). The agreement node calls the real
    ``metrics.compute_category_raw_metrics`` on this input rather than the
    pipeline wrapper.
    """
    by_stratum: dict[int, list[metrics.MetricObservation]] = {}
    for member in repository.get_sample_members(run.run_id, category.category):
        record = repository.get_enrichment_observation(
            run.run_id, member.asset_identity_key
        )
        assert record is not None
        by_stratum.setdefault(member.stratum_index, []).append(
            metrics.MetricObservation(
                product_page_views=record.product_page_views,
                first_published_date_utc=record.first_published_date_utc,
                state=record.state,
                id_mapping_mismatch=record.id_mapping_mismatch,
                rating_average=record.rating_average,
                rating_count=record.rating_count,
                product_detail_status=record.product_detail_status,
                page_views_status=record.page_views_status,
            )
        )
    strata = tuple(
        metrics.StratumMetricInput(
            stratum_index=stratum.stratum_index,
            discovered_population_count=stratum.population_count,
            sampled_population_count=stratum.selected_count,
            observations=tuple(by_stratum[stratum.stratum_index]),
        )
        for stratum in category.strata
    )
    return (
        metrics.CategoryMetricInput(
            category=category.category,
            scoring_cutoff_utc=ef.SCORING_CUTOFF_UTC,
            page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
            strata=strata,
        ),
        metrics.BreadthMetricInput(
            verified_total_count=None,
            distinct_canonical_discovered_count=category.population.size,
        ),
    )


@pytest.mark.lreq("LREQ-SMP-080")
def test_capture_scoring_cutoff_normalizes_and_rejects_naive():
    """The single capture normalizes aware offsets and rejects a naive value."""
    naive = ef.FINALIZATION_NAIVE_DATE_UTC
    with pytest.raises(ValueError):
        pipeline.capture_scoring_cutoff_utc(naive)
    # An aware value in another offset is converted to UTC (ruling C).
    offset = timezone(timedelta(hours=2))
    result = pipeline.capture_scoring_cutoff_utc(
        ef.SCORING_CUTOFF_UTC.astimezone(offset)
    )
    assert result == ef.SCORING_CUTOFF_UTC
    assert result.tzinfo == timezone.utc
    # An already-UTC value is returned unchanged and never read from the clock.
    assert pipeline.capture_scoring_cutoff_utc(ef.SCORING_CUTOFF_UTC) == (
        ef.SCORING_CUTOFF_UTC
    )


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_stratum_counts_from_observations():
    """The hand-computed golden 4/5/3 counts and N_h/n_h are finalized."""
    finalizations = _finalize(
        ef.finalization_category(), ef.finalization_observations()
    )
    assert len(finalizations) == 1
    final = finalizations[0]
    # Plan §9 finalization golden (LREQ-SMP-080): one stratum, N_h == 10,
    # n_h == 6, and the Chunk 7A counts 4 / 5 / 3.
    assert (final.N_h, final.n_h) == (
        ef.FINALIZATION_POPULATION,
        ef.FINALIZATION_SAMPLE,
    )
    assert final.u_demand_h == ef.FINALIZATION_U_DEMAND
    assert final.u_recent_h == ef.FINALIZATION_U_RECENT
    assert final.u_quality_h == ef.FINALIZATION_U_QUALITY
    assert final.usable_status == ef.FINALIZATION_USABLE_STATUS


@pytest.mark.lreq("LREQ-SMP-080")
@pytest.mark.lreq("LREQ-MET-090")
def test_finalize_stratum_counts_quality_min_rating_count_override():
    """``finalize_stratum_counts`` forwards ``quality_min_rating_count`` to 7A.

    SRS §7.5 / LREQ-MET-090: an observation is quality-eligible only when
    ``rating_count >= QUALITY_MIN_RATING_COUNT``; SRS §14 pins the default at 5
    and marks it Configurable ``Yes``, so the override must reach Chunk 7A's
    ``quality_observation_eligibility`` through this frozen §5.4 caller.

    Hand-computed on a locally built one-stratum category with three members
    whose only non-default field is ``rating_count = 3`` (aware UTC date 100
    days before the cutoff, 4321 page views, both operations successful,
    published state — the golden finalization fields):

    * at ``quality_min_rating_count = 3`` (and ``min_usable_samples_per_stratum
      = 1``) all three pass the rating gate, so ``u_quality_h == 3``;
    * at the default 5 none passes, so ``u_quality_h == 0`` — a measured zero,
      never a reclassification of the observations.
    """
    keys = ("Q1", "Q2", "Q3")
    category = ef.category_result(
        "Category/QualityRatingOverride",
        tuple((key, rank) for rank, key in enumerate(keys, start=1)),
    )
    observations = {
        key: ef.observation_record(
            ef.RUN_ID,
            key,
            rating_count=3,
            first_published_date_utc=ef.FINALIZATION_DATE_UTC,
        )
        for key in keys
    }

    override = _finalize(
        category,
        observations,
        quality_min_rating_count=3,
        min_usable_samples_per_stratum=1,
    )
    assert len(override) == 1
    assert override[0].u_quality_h == 3
    # The rating minimum excludes nothing from the other two components: the
    # same three observations stay demand- and recent-eligible.
    assert override[0].u_demand_h == 3
    assert override[0].u_recent_h == 3

    default = _finalize(category, observations)
    assert len(default) == 1
    assert default[0].u_quality_h == 0


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_counts_missing_observation_not_zero():
    """A missing observation is unavailable: it raises, never a fabricated zero."""
    observations = ef.finalization_observations()
    del observations[ef.FINALIZATION_MEMBERS[3]]
    with pytest.raises(ValueError) as info:
        _finalize(ef.finalization_category(), observations)
    message = str(info.value)
    # The error names the category only, never an identity (redaction-safe).
    assert ef.FINALIZATION_CATEGORY in message
    for key in ef.FINALIZATION_MEMBERS:
        assert key not in message


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_explicit_zero_page_views_counts_toward_demand():
    """Explicit valid page views of 0 yield a usable index of 0.0, not missing."""
    zero_key = "Z"
    category = ef.category_result(ef.FINALIZATION_CATEGORY, ((zero_key, 1),))
    observations = {
        zero_key: ef.observation_record(
            ef.RUN_ID,
            zero_key,
            product_page_views=0,
            first_published_date_utc=ef.FINALIZATION_DATE_UTC,
        )
    }
    final = _finalize(category, observations)[0]
    # Plan §9 / E5: an explicit 0 is a usable index of 0.0 and increments demand.
    assert final.u_demand_h == 1
    index = metrics.age_normalized_page_view_index(
        0,
        ef.FINALIZATION_DATE_UTC,
        scoring_cutoff_utc=ef.SCORING_CUTOFF_UTC,
        state="published",
        id_mapping_mismatch=False,
    )
    assert index.is_available
    assert index.value is not None
    assert index.value == pytest.approx(0.0, abs=1e-9)


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_usable_status_and_eligibility_rule_present():
    """`usable_status` is explicit and the rule names each component's outcome."""
    final = _finalize(ef.finalization_category(), ef.finalization_observations())[0]
    # Gate line 762: an explicit non-pending status plus a non-null rule. The
    # quality count is 3 < MIN_USABLE, so its field names the first dominant
    # unavailable reason (F4's missing date, first in rank order).
    assert final.usable_status == ef.FINALIZATION_USABLE_STATUS
    assert final.eligibility_rule == ef.FINALIZATION_ELIGIBILITY_RULE
    fields = dict(part.split("=", 1) for part in final.eligibility_rule.split(";"))
    assert set(fields) == {"demand", "recent", "quality"}
    assert fields["quality"] == metrics.METRIC_REASON_NULL
    assert fields["recent"] == f"usable:{MIN_USABLE_SAMPLES_PER_STRATUM}"
    assert all(
        value == f"usable:{MIN_USABLE_SAMPLES_PER_STRATUM}"
        or value in metrics.METRIC_UNAVAILABLE_REASONS
        for value in fields.values()
    )

    # The all-usable branch reports ``usable:<min>`` for every component.
    usable_keys = tuple(f"U{rank}" for rank in range(1, 6))
    usable_category = ef.category_result(
        ef.FINALIZATION_CATEGORY,
        tuple((key, rank) for rank, key in enumerate(usable_keys, start=1)),
    )
    usable_observations = {
        key: ef.observation_record(
            ef.RUN_ID, key, first_published_date_utc=ef.FINALIZATION_DATE_UTC
        )
        for key in usable_keys
    }
    usable_final = _finalize(usable_category, usable_observations)[0]
    assert usable_final.usable_status == "usable"
    assert usable_final.eligibility_rule == (
        "demand=usable:5;recent=usable:5;quality=usable:5"
    )


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_serialization_is_byte_deterministic(tmp_path):
    """Two finalization passes over the same observations are byte-identical."""
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        first = _finalize_enrichment(repository, run, union)
        second = _finalize_enrichment(repository, run, union)
        first_json = first.categories[0].stratum_statistics_json
        second_json = second.categories[0].stratum_statistics_json
        # E11 / gate line 763: the frozen ten-key payload re-serializes with
        # identical UTF-8 bytes, never depending on dict or set order.
        assert first_json.encode("utf-8") == second_json.encode("utf-8")
        assert first.categories[0].strata == second.categories[0].strata
        assert first.mismatches == ()
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_zero_population_category_is_empty_and_zero(tmp_path):
    """A zero-population category has no strata and measured-zero counts."""
    zero = ef.zero_population_category()
    # Pure §5.4 edge contract (E8): no strata -> an empty tuple.
    assert _finalize(zero, {}) == ()

    run = ef.finalization_run_with_zero()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        report = _finalize_enrichment(repository, run, union)
        by_category = {row.category: row for row in report.categories}
        assert ef.FINALIZATION_ZERO_CATEGORY in by_category
        final = by_category[ef.FINALIZATION_ZERO_CATEGORY]
        # E8: explicit measured zeros, never a missing population presented as 0.
        assert final.strata == ()
        assert final.usable_demand_sample_count == 0
        assert final.usable_recent_supply_sample_count == 0
        assert final.usable_quality_sample_count == 0
        assert final.stratum_statistics_json == "[]"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_category_counts_equal_sum_over_usable_strata(tmp_path):
    """Category counts are the sums over strata meeting the applicable minimum."""
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        report = _finalize_enrichment(repository, run, union)
        final = report.categories[0]
        # Plan §9 finalization golden: the single stratum carries 4 / 5 / 3.
        assert [entry.u_demand_h for entry in final.strata] == [
            ef.FINALIZATION_U_DEMAND
        ]
        assert [entry.u_recent_h for entry in final.strata] == [
            ef.FINALIZATION_U_RECENT
        ]
        assert [entry.u_quality_h for entry in final.strata] == [
            ef.FINALIZATION_U_QUALITY
        ]

        def usable_sum(value_of):
            return sum(
                value_of(entry)
                for entry in final.strata
                if metrics.stratum_is_usable(
                    value_of(entry),
                    min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
                )
            )

        # SRS §6.5: a category-level count sums u_*_h over only the strata that
        # meet the minimum (5). The demand (4) and quality (3) strata do not, so
        # those counts are a measured 0; recent (5) contributes 5.
        assert final.usable_demand_sample_count == usable_sum(lambda e: e.u_demand_h)
        assert final.usable_recent_supply_sample_count == usable_sum(
            lambda e: e.u_recent_h
        )
        assert final.usable_quality_sample_count == usable_sum(lambda e: e.u_quality_h)
        assert final.usable_demand_sample_count == 0
        assert final.usable_recent_supply_sample_count == ef.FINALIZATION_U_RECENT
        assert final.usable_quality_sample_count == 0
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_agrees_with_chunk7b_compute_category_raw_metrics(tmp_path):
    """Finalized counts equal the real Chunk 7B raw-metric outputs exactly."""
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        report = _finalize_enrichment(repository, run, union)
        final = report.categories[0]
        metric_input, breadth_input = _chunk7b_metric_inputs(
            repository, run, run.categories[0]
        )
        raw = metrics.compute_category_raw_metrics(metric_input, breadth_input)
        # Gate line 763: exact int equality with the pure 7B estimator, never a
        # tolerance and never a value both sides recomputed from the same helper.
        assert raw.usable_demand_sample_count == final.usable_demand_sample_count
        assert raw.usable_recent_supply_sample_count == (
            final.usable_recent_supply_sample_count
        )
        assert raw.usable_quality_sample_count == final.usable_quality_sample_count
        # Hand-derived from SRS §6.5 and the plan §9 golden vectors: the demand
        # (4) and quality (3) strata fall below the minimum 5 and contribute 0,
        # while the recent (5) stratum is usable and contributes 5.
        assert (
            raw.usable_demand_sample_count,
            raw.usable_recent_supply_sample_count,
            raw.usable_quality_sample_count,
        ) == (0, ef.FINALIZATION_U_RECENT, 0)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_unique_enrichment_count_identical_on_every_category(tmp_path):
    """The run-wide distinct enriched count is identical on every category row."""
    run = ef.finalization_run_with_zero()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        report = _finalize_enrichment(repository, run, union)
        expected = repository.count_distinct_enrichment_identities(run.run_id)
        assert expected == len(ef.FINALIZATION_MEMBERS)
        assert len(report.categories) == 2
        assert {row.unique_enrichment_count for row in report.categories} == {expected}
        persisted = {
            row.category: row.unique_enrichment_count
            for row in repository.get_category_scores(run.run_id)
        }
        assert len(persisted) == 2
        assert set(persisted.values()) == {expected}
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_assert_consistency_detects_injected_drift(tmp_path):
    """An injected persisted-count drift is reported; the assertion never raises."""
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        report = _finalize_enrichment(repository, run, union)
        assert report.mismatches == ()
        assert _assert_consistency(repository, run, report) == ()
        # Plan §9 drift golden: persist one category-level u_* value one above
        # its true sum.
        row = repository.get_category_scores(run.run_id)[0]
        repository.upsert_category_scores(
            [
                replace(
                    row,
                    usable_demand_sample_count=row.usable_demand_sample_count + 1,
                )
            ]
        )
        mismatches = _assert_consistency(repository, run, report)
        # Never raises; the mismatch names the category and the column only.
        assert mismatches == (
            f"category {ef.FINALIZATION_CATEGORY!r}: usable_demand_sample_count",
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_assert_consistency_clean_run_returns_no_mismatches(tmp_path):
    """An untouched finalized golden run passes every consistency check.

    The canonical 4/5/3 golden category: demand (4) and quality (3) fall below
    the minimum 5, so their category-level counts are a measured 0, while recent
    (5) is usable and contributes 5 (SRS §6.5; plan §12 A3).
    """
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        report = _finalize_enrichment(repository, run, union)
        final = report.categories[0]
        assert (
            final.usable_demand_sample_count,
            final.usable_recent_supply_sample_count,
            final.usable_quality_sample_count,
        ) == (0, ef.FINALIZATION_U_RECENT, 0)
        assert report.mismatches == ()
        assert _assert_consistency(repository, run, report) == ()
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
@pytest.mark.lreq("LREQ-MET-090")
def test_finalize_enrichment_non_default_policy_is_self_consistent(tmp_path):
    """A non-default policy reaches the finalize sums and check A/B together.

    SRS §5.1 / LREQ-SMP-080 (persisted per-stratum ``u_*_h`` counts and category
    sums) with SRS §7.5 / LREQ-MET-090. On the seeded golden single-category run
    (``N_h = 10``, ``n_h = 6``, hand-computed 4/5/3 component counts):

    * defaults (``M = 5``): demand 4 < 5, recent 5 >= 5, quality 3 < 5, so the
      category sums are ``(0, 5, 0)``;
    * ``min_usable_samples_per_stratum = 1``: every component's stratum is
      usable, so ``(4, 5, 3)``;
    * ``min_age_days_for_rate = 101``: the golden date is exactly 100 days
      before the cutoff, so every dated index is ``age_below_minimum`` and
      demand/quality drop to 0 while recent stays 5 -> ``(0, 5, 0)``.

    ``mismatches == ()`` on each non-default call proves the §5.5 assertion
    received the same parameters: check A's ``stratum_is_usable`` and check B's
    ``CategoryMetricInput`` would otherwise compare a constant/timeout split
    against the non-default finalized counts and return a named mismatch.
    """
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())

        at_defaults = _finalize_enrichment(repository, run, union)
        assert at_defaults.mismatches == ()
        assert (
            at_defaults.categories[0].usable_demand_sample_count,
            at_defaults.categories[0].usable_recent_supply_sample_count,
            at_defaults.categories[0].usable_quality_sample_count,
        ) == (0, ef.FINALIZATION_U_RECENT, 0)

        min_one = _finalize_enrichment(
            repository, run, union, min_usable_samples_per_stratum=1
        )
        assert min_one.mismatches == ()
        assert (
            min_one.categories[0].usable_demand_sample_count,
            min_one.categories[0].usable_recent_supply_sample_count,
            min_one.categories[0].usable_quality_sample_count,
        ) == (
            ef.FINALIZATION_U_DEMAND,
            ef.FINALIZATION_U_RECENT,
            ef.FINALIZATION_U_QUALITY,
        )

        older_rate = _finalize_enrichment(
            repository, run, union, min_age_days_for_rate=101
        )
        assert older_rate.mismatches == ()
        assert (
            older_rate.categories[0].usable_demand_sample_count,
            older_rate.categories[0].usable_recent_supply_sample_count,
            older_rate.categories[0].usable_quality_sample_count,
        ) == (0, ef.FINALIZATION_U_RECENT, 0)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
@pytest.mark.lreq("LREQ-MET-090")
def test_finalize_enrichment_rating_min_matches_seventh_b(tmp_path):
    """The finalize path and check B's 7B input share one rating minimum.

    SRS §7.5 / LREQ-MET-090 with the §8.3 rating-count-straddling fixture: one
    stratum, ``N_h = 25``, ``n_h = 5``, rating counts 2/3/4/5/7 straddling the
    default minimum 5 and the override 3.

    Hand-computed ``u_quality_h`` (``rating_count >= minimum``): at
    ``quality_min_rating_count = 3`` the eligible set is Q2 (3), Q3 (4), Q4 (5),
    Q5 (7) -> 4; Q1 (2) stays below the minimum. At the default 5 only Q4 and Q5
    are eligible -> 2, which is below ``M = 5`` and contributes a measured 0.

    With ``min_usable_samples_per_stratum = 1`` the override call must return
    and persist ``usable_quality_sample_count == 4`` and ``mismatches == ()``:
    if check B's ``CategoryMetricInput`` had not received the same rating
    minimum, its 7B computation (default 5 -> 2) would flag the column.
    """
    run = ef.quality_straddle_finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_quality_straddle_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())

        report = _finalize_enrichment(
            repository,
            run,
            union,
            min_usable_samples_per_stratum=1,
            quality_min_rating_count=3,
        )
        final = report.categories[0]
        assert [entry.u_quality_h for entry in final.strata] == [4]
        assert final.usable_quality_sample_count == 4
        assert report.mismatches == ()
        persisted = repository.get_category_scores(run.run_id)
        assert [row.usable_quality_sample_count for row in persisted] == [4]

        # The default minimum 5 leaves Q4 and Q5 (2 < M = 5): a measured 0.
        default = _finalize_enrichment(repository, run, union)
        assert default.categories[0].usable_quality_sample_count == 0
        assert default.mismatches == ()
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_no_pending_usable_status_after_finalize(tmp_path):
    """A completed run leaves no pending placeholder in any stratum payload."""
    from niche_scout import database

    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        _finalize_enrichment(repository, run, union)
        rows = repository.get_category_scores(run.run_id)
        assert rows
        for row in rows:
            entries = database.parse_stratum_statistics(row.stratum_statistics_json)
            for entry in entries:
                # Gate line 762: no pending status and no null rule on a completed
                # run, and every finalized count is an explicit value.
                assert entry["usable_status"] != database.PENDING_USABLE_STATUS
                assert entry["eligibility_rule"] is not None
                assert entry["u_demand_h"] is not None
                assert entry["u_recent_h"] is not None
                assert entry["u_quality_h"] is not None
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_is_idempotent(tmp_path):
    """Two finalization passes are byte-identical in serialization and counts."""
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        first = _finalize_enrichment(repository, run, union)
        first_rows = {
            row.category: row for row in repository.get_category_scores(run.run_id)
        }
        second = _finalize_enrichment(repository, run, union)
        second_rows = {
            row.category: row for row in repository.get_category_scores(run.run_id)
        }
        assert first.categories == second.categories
        assert first.category_rows_written == second.category_rows_written
        assert first.mismatches == second.mismatches == ()
        for category, first_row in first_rows.items():
            second_row = second_rows[category]
            assert first_row.stratum_statistics_json.encode(
                "utf-8"
            ) == second_row.stratum_statistics_json.encode("utf-8")
            assert (
                first_row.usable_demand_sample_count
                == second_row.usable_demand_sample_count
            )
            assert first_row == second_row
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_finalize_enrichment_merges_consistency_assertion_mismatches(
    tmp_path, monkeypatch
):
    """§5.4 step 4: a 7B-visible divergence surfaces in ``finalize_enrichment``.

    The finalized counts and the persisted rows stay clean; only the Chunk 7B
    estimator is drifted, so a non-empty ``mismatches`` can come only from the
    merged §5.5 assertion. The call never raises and the string names category
    and column only.
    """
    run = ef.finalization_run()
    repository = _open(tmp_path)
    try:
        ef.seed_finalization(repository, run)
        union = pipeline.compute_enrichment_union(run, already_enriched_keys=set())
        clean = _finalize_enrichment(repository, run, union)
        assert clean.mismatches == ()

        real = metrics.compute_category_raw_metrics

        def _drifted(category_input, breadth_input):
            result = real(category_input, breadth_input)
            return replace(
                result,
                usable_demand_sample_count=result.usable_demand_sample_count + 1,
            )

        with monkeypatch.context() as patch:
            patch.setattr(pipeline, "compute_category_raw_metrics", _drifted)
            drifted = _finalize_enrichment(repository, run, union)

        # Only §5.5 check B can observe the drift (the read phase wrote the
        # correct counts), so the merged tuple is exactly one named mismatch.
        assert drifted.mismatches == (
            f"category {ef.FINALIZATION_CATEGORY!r}: usable_demand_sample_count",
        )
        # The persisted rows round-trip cleanly: the residual mismatch is the
        # injected 7B divergence, not a write defect.
        assert _assert_consistency(repository, run, drifted) == ()
    finally:
        repository.close()
