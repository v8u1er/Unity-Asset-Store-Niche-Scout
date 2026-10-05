"""Analytical tests for chunk 4B — sample persistence, overlap, summaries.

Source of truth: ``Documents/SRS-lean.md`` §5.1/§6.3/§6.5 (``LREQ-SMP-080``), the
frozen plan
``Documents/plans/chunk-4B-sample-persistence-overlap-and-sampling-summaries.md``
(§5 interface contract, §9.2 fixtures O1-O10, §9.3 node list), and the frozen
remediation plan ``Documents/plans/chunk-24-systematic-strata.md`` (§3.2/§3.3
renamed geometry columns and ``stratum_statistics_json`` key set, §8.1 O8/O9
re-baseline). Every analytical node carries
``@pytest.mark.lreq("LREQ-SMP-080")`` and has a ``tests/traceability.json`` entry
keyed by its base node ID.

Golden values are hand-derived from the SRS formulas in the comment next to the
assertion; the overlap percentage is asserted against the unrounded ``float64``
expression (Q-7), never against a rounded literal.

No network, no credentials, no clock reads in test code, and no ``sqlite3``:
the repository is exercised only through the frozen Chunk 2 public API, with the
database under pytest ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest
from fixtures import sampling_persistence_fixtures as pf

import niche_scout.sampling as sampling
from niche_scout import database
from niche_scout.models import SamplingBasis

# --------------------------------------------------------------------------
# Helpers (pure; no assertions on behavior under test).
# --------------------------------------------------------------------------


def _run(categories, *, run_id: str = "run-4b"):
    """Build a pure ``RunSamplingResult`` from a category -> records mapping."""
    return sampling.select_run_sample(categories, run_id=run_id)


def _repository(tmp_path, name: str = "chunk4b.sqlite") -> database.SqliteRepository:
    """Open a fresh repository under ``tmp_path`` (no live path, no network)."""
    return database.SqliteRepository(tmp_path / name)


def _seed_run(repository, run_id: str, categories) -> None:
    """Insert the ``runs`` row and one ``category_scores`` row per category.

    This is the Chunk 3 runtime order chunk 4B depends on: the ``runs`` row and
    the ``(run_id, category)`` row exist (via ``set_category_status``) before
    ``persist_run_sampling`` runs.
    """
    repository.insert_run(pf.run_record(run_id))
    for category in categories:
        repository.set_category_status(
            run_id,
            category,
            pf.census_report_discovery_status(),
            computed_at_utc=pf.COMPUTED_AT_UTC,
        )


def _overlap_by_category(run, result):
    """Index a ``RunOverlapResult`` by category."""
    return {entry.category: entry for entry in result.categories}


def _summary_by_category(repository, run_id):
    """Index persisted ``category_scores`` rows by category."""
    return {row.category: row for row in repository.get_category_scores(run_id)}


def _strata_json(row):
    """Parse a persisted ``stratum_statistics_json`` into its object list."""
    return json.loads(row.stratum_statistics_json)


def _census_stratum(run):
    """Return the single stratum of the census category of an O6-like run."""
    return run.by_category[pf.CENSUS_CATEGORY].strata[0]


# --------------------------------------------------------------------------
# 9.3 — pure overlap (O1-O5)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_counts_shared_categories():
    """O1: two 3-member categories share ``s1`` -> each counts one other."""
    run = _run(pf.o1_categories())
    result = sampling.compute_overlap(run)
    # SRS §6.5: count OTHER categories sharing >= 1 sampled identity.
    # Overlap/A sees Overlap/B (s1) -> 1; Overlap/B sees Overlap/A (s1) -> 1.
    expected = pf.o1_expected()
    assert result.run_id == run.run_id
    by_category = _overlap_by_category(run, result)
    assert set(by_category) == set(expected)
    for category, (count, _percentage) in expected.items():
        assert by_category[category].overlap_category_count == count


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_percentage_is_exact_ratio():
    """O1: the percentage is ``100 * 1 / 3`` for both categories."""
    run = _run(pf.o1_categories())
    by_category = _overlap_by_category(run, sampling.compute_overlap(run))
    # SRS §6.5 derivation: Overlap/A sampled identities {a1, a2, s1}; exactly
    # one of the three (s1) appears in another category, so the numerator is 1
    # and the denominator the category's enriched sample size, 3:
    #     percentage = 100 * 1 / 3 = 33.333333333333336 (float64).
    exact = 100.0 * 1 / 3
    for category in (pf.CATEGORY_A, pf.CATEGORY_B):
        assert by_category[category].overlap_sample_percentage == pytest.approx(
            exact, abs=1e-9
        )


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_percentage_is_unrounded_float64():
    """Q-7: the persisted percentage is stored unrounded (``float64``)."""
    run = _run(pf.o1_categories())
    by_category = _overlap_by_category(run, sampling.compute_overlap(run))
    # Same derivation as above; the value must equal the unrounded float64
    # expression, so a rounded 33.33 (or 33.333333) fails.
    exact = 100.0 * 1 / 3
    value = by_category[pf.CATEGORY_A].overlap_sample_percentage
    assert value != 33.33
    assert value != 33.333333
    assert value == pytest.approx(exact, abs=1e-9)


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_zero_when_disjoint():
    """O2: disjoint categories are a measured ``0``/``0.0``, never ``None``."""
    run = _run(pf.o2_categories())
    by_category = _overlap_by_category(run, sampling.compute_overlap(run))
    expected = pf.o2_expected()
    for category, (count, percentage) in expected.items():
        assert by_category[category].overlap_category_count == count
        assert by_category[category].overlap_sample_percentage == pytest.approx(
            percentage, abs=1e-9
        )


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_single_category():
    """O3: a lone non-empty category has no other category -> ``0``/``0.0``."""
    run = _run(pf.o3_categories())
    by_category = _overlap_by_category(run, sampling.compute_overlap(run))
    expected = pf.o3_expected()
    for category, (count, percentage) in expected.items():
        assert by_category[category].overlap_category_count == count
        assert by_category[category].overlap_sample_percentage == pytest.approx(
            percentage, abs=1e-9
        )


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_null_percentage_for_empty_category():
    """O4: a zero-member category is ``None``, never ``0.0`` (SRS §1.2)."""
    run = _run(pf.o4_categories())
    by_category = _overlap_by_category(run, sampling.compute_overlap(run))
    empty = by_category[pf.ZERO_CATEGORY]
    assert empty.overlap_category_count == 0
    assert empty.overlap_sample_percentage is None
    # The neighbouring non-empty category is a measured zero, not None.
    assert by_category[pf.CATEGORY_A].overlap_sample_percentage == pytest.approx(
        0.0, abs=1e-9
    )


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_three_way_share():
    """O5: one identity in A, B, C -> each counts the other two, 100.0."""
    run = _run(pf.o5_categories())
    by_category = _overlap_by_category(run, sampling.compute_overlap(run))
    expected = pf.o5_expected()
    assert tuple(by_category) == (pf.CATEGORY_A, pf.CATEGORY_B, pf.CATEGORY_C)
    for category, (count, percentage) in expected.items():
        assert by_category[category].overlap_category_count == count
        assert by_category[category].overlap_sample_percentage == pytest.approx(
            percentage, abs=1e-9
        )
    # The union is exactly one identity, counted once per category (SRS §6.5).
    assert run.enrichment_identity_keys == pf.o5_union_identity_keys()


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_preserves_category_order():
    """Overlap follows ``RunSamplingResult`` category order, including empty."""
    categories = {
        pf.CATEGORY_B: pf.records_for(pf.O1_CATEGORY_B_KEYS),
        pf.ZERO_CATEGORY: (),
        pf.CATEGORY_A: pf.records_for(pf.O1_CATEGORY_A_KEYS),
    }
    run = _run(categories)
    result = sampling.compute_overlap(run)
    assert result.run_id == run.run_id
    assert tuple(entry.category for entry in result.categories) == (
        pf.CATEGORY_B,
        pf.ZERO_CATEGORY,
        pf.CATEGORY_A,
    )
    assert tuple(result.by_category) == tuple(categories)
    # An empty run yields an empty tuple (plan §5.1 edge contract).
    assert sampling.compute_overlap(_run({})).categories == ()


@pytest.mark.lreq("LREQ-SMP-080")
def test_compute_overlap_does_not_inflate_enrichment_counts():
    """Overlap never inflates enrichment counts or identity keys."""
    run = _run(pf.o1_categories())
    sampling.compute_overlap(run)
    # SRS §6.5 / dependency map §5 item 7: the union stays two categories'
    # worth of distinct identities (3 + 3 - 1 shared == 5), never 6.
    assert len(run.enrichment_identity_keys) == 5
    for category in (pf.CATEGORY_A, pf.CATEGORY_B):
        result = run.by_category[category]
        assert result.enriched_sample_count == len(result.members) == 3
        assert result.discovered_population_count == 3


# --------------------------------------------------------------------------
# 9.3 — sample_members materialization (O6)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_persist_writes_one_membership_per_selected_member(tmp_path):
    """O6: one persisted row per pure selected member, read back keyed."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            report = database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
    finally:
        repository.close()

    expected_total = len(run.by_category[pf.CENSUS_CATEGORY].members) + len(
        run.by_category[pf.LARGE_CATEGORY].members
    )
    assert report.run_id == run.run_id
    assert report.sample_members_written == expected_total
    assert (
        expected_total
        == pf.CENSUS_N + pf.o6_expected_selected_counts()[pf.LARGE_CATEGORY]
    )
    assert report.mismatches == ()


@pytest.mark.lreq("LREQ-SMP-080")
def test_persisted_member_fields_match_pure_result(tmp_path):
    """O6: stratum/rank/census/digest round-trip from the pure result."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        for category in (pf.CENSUS_CATEGORY, pf.LARGE_CATEGORY):
            pure_members = run.by_category[category].members
            stored = repository.get_sample_members(run.run_id, category)
            # Chunk 2 read order: stratum_index ASC then rank ASC.
            assert len(stored) == len(pure_members)
            for stored_row, pure in zip(stored, pure_members):
                assert stored_row.run_id == run.run_id
                assert stored_row.category == pure.category
                assert stored_row.asset_identity_key == pure.asset_identity_key
                assert stored_row.stratum_index == pure.stratum_index
                assert stored_row.stratum_offset == pure.stratum_offset
                assert stored_row.stratum_stride == pure.stratum_stride
                assert (
                    stored_row.sample_rank_within_stratum
                    == pure.sample_rank_within_stratum
                )
                assert stored_row.sample_is_census == pure.sample_is_census
                assert stored_row.selection_digest == pure.selection_digest
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_persisted_digest_is_reproducible(tmp_path):
    """Every persisted digest is recomputable from the SRS formula (SMP-060)."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        for category in (pf.CENSUS_CATEGORY, pf.LARGE_CATEGORY):
            stored = repository.get_sample_members(run.run_id, category)
            assert stored
            for row in stored:
                assert row.selection_digest == pf.expected_digest(
                    category, row.asset_identity_key
                )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_member_overlap_repeats_category_overlap_values(tmp_path):
    """Q-3 option (a): each member row repeats its category's overlap values."""
    run = _run(pf.o1_categories())
    overlap = _overlap_by_category(run, sampling.compute_overlap(run))
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o1_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        for category in (pf.CATEGORY_A, pf.CATEGORY_B):
            rows = repository.get_sample_members(run.run_id, category)
            assert len(rows) == 3
            for row in rows:
                assert (
                    row.overlap_category_count
                    == overlap[category].overlap_category_count
                    == 1
                )
                assert row.overlap_sample_percentage == pytest.approx(
                    overlap[category].overlap_sample_percentage, abs=1e-9
                )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_persisted_overlap_columns_match_pure_overlap(tmp_path):
    """O1 round trip: member and summary overlap columns equal ``compute_overlap``."""
    run = _run(pf.o1_categories())
    overlap = _overlap_by_category(run, sampling.compute_overlap(run))
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o1_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        summaries = _summary_by_category(repository, run.run_id)
        for category in (pf.CATEGORY_A, pf.CATEGORY_B):
            expected = overlap[category]
            summary = summaries[category]
            assert summary.overlap_category_count == expected.overlap_category_count
            assert summary.overlap_sample_percentage == pytest.approx(
                expected.overlap_sample_percentage, abs=1e-9
            )
            for row in repository.get_sample_members(run.run_id, category):
                assert row.overlap_category_count == expected.overlap_category_count
                assert row.overlap_sample_percentage == pytest.approx(
                    expected.overlap_sample_percentage, abs=1e-9
                )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_preflight_selected_is_false_placeholder(tmp_path):
    """Q-5: 4B writes the documented ``False`` pre-preflight placeholder."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        for category in (pf.CENSUS_CATEGORY, pf.LARGE_CATEGORY):
            rows = repository.get_sample_members(run.run_id, category)
            assert rows
            for row in rows:
                assert row.preflight_selected is False
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9.3 — per-category summary round trip (O6) and zero population (O7)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_census_summary_round_trips(tmp_path):
    """O6: the census category persists as census with fraction exactly 1.0."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        row = _summary_by_category(repository, run.run_id)[pf.CENSUS_CATEGORY]
        pure = run.by_category[pf.CENSUS_CATEGORY]
        assert row.discovered_population_count == pf.CENSUS_N
        assert row.enriched_sample_count == pf.CENSUS_N
        assert row.sample_is_census is True
        assert row.sampling_basis == pf.o6_expected_basis()[pf.CENSUS_CATEGORY]
        assert row.sampling_basis == SamplingBasis.CENSUS.value
        # SRS §5.1: a non-empty census has sample_fraction exactly 1.0.
        assert row.sample_fraction == pytest.approx(1.0, abs=1e-9)
        assert (
            row.sample_fraction == pf.o6_expected_sample_fractions()[pf.CENSUS_CATEGORY]
        )
        assert row.discovered_population_count == pure.discovered_population_count
        assert row.enriched_sample_count == pure.enriched_sample_count
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_large_category_summary_round_trips(tmp_path):
    """O6: the 101-population category persists 100 members at 100/101."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        pure = run.by_category[pf.LARGE_CATEGORY]
        # Derivation (plan chunk-24 §2.1): the interleaved partition at N=101
        # gives stratum sizes 26/25/25/25; every stratum selects min(25, N_h)
        # == 25 and none is reduced, so the sample is 25+25+25+25 == 100.
        assert pf.LARGE_N == 101
        assert len(pure.members) == 100
        assert pure.sample_fraction == pytest.approx(100.0 / 101.0, abs=1e-9)
        assert len(pure.members) == pf.o6_expected_selected_counts()[pf.LARGE_CATEGORY]

        row = _summary_by_category(repository, run.run_id)[pf.LARGE_CATEGORY]
        assert row.discovered_population_count == pf.LARGE_N
        assert row.enriched_sample_count == 100
        assert row.sample_is_census is False
        assert (
            row.sampling_basis
            == pf.o6_expected_basis()[pf.LARGE_CATEGORY]
            == SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE.value
        )
        assert row.sample_fraction == pytest.approx(
            pf.o6_expected_sample_fractions()[pf.LARGE_CATEGORY], abs=1e-9
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_zero_population_sample_fraction_is_null_not_zero(tmp_path):
    """O7: a zero-discovered-population summary persists ``NULL``, not ``0.0``."""
    run = _run(pf.o7_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o7_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        row = _summary_by_category(repository, run.run_id)[pf.ZERO_CATEGORY]
        assert row.discovered_population_count == 0
        assert row.enriched_sample_count == 0
        assert row.sample_fraction is None
        assert row.stratum_statistics_json == pf.EMPTY_STRATUM_STATISTICS_JSON
        assert repository.get_sample_members(run.run_id, pf.ZERO_CATEGORY) == ()
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9.3 — per-stratum summary and pending vocabulary (O8/O9)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_stratum_statistics_json_matches_frozen_schema(tmp_path):
    """O9: byte-exact ten-key JSON with the ``pending`` token and null ``u_*``."""
    run = _run(pf.census_one_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.census_one_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        row = _summary_by_category(repository, run.run_id)[pf.DIGEST_VECTOR_CATEGORY]
        assert row.stratum_statistics_json == pf.O9_STRATUM_STATISTICS_JSON

        # The frozen schema is also checkable structurally (plan §5.2).
        entries = _strata_json(row)
        assert len(entries) == 1
        assert tuple(sorted(entries[0])) == tuple(sorted(pf.O9_STRATUM_KEYS))
        entry = entries[0]
        assert entry["stratum_index"] == 0
        assert entry["stratum_offset"] == 0
        assert entry["stratum_stride"] == 1
        assert entry["N_h"] == 1
        assert entry["n_h"] == 1
        assert entry["usable_status"] == pf.PENDING_USABLE_STATUS
        assert entry["usable_status"] in pf.USABLE_STATUS_VOCABULARY
        assert entry["eligibility_rule"] is None
        assert entry["u_demand_h"] is None
        assert entry["u_recent_h"] is None
        assert entry["u_quality_h"] is None
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_stratum_statistics_json_round_trips_n_h_and_geometry(tmp_path):
    """O8: N=101 per-stratum ``N_h``/``n_h``/(offset, stride) survive the round trip.

    Plan chunk-24 §2.1/§8.1: the interleaved partition gives stratum sizes
    26/25/25/25 at N = 101 (the stratum holding ordinal 1 takes the remainder),
    every stratum selects 25 and none is reduced, and each entry carries the
    category's ``(offset, stride)`` = ``(0, 4)``.
    """
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        row = _summary_by_category(repository, run.run_id)[pf.LARGE_CATEGORY]
        entries = _strata_json(row)
        observed = tuple(
            (
                entry["stratum_index"],
                entry["stratum_offset"],
                entry["stratum_stride"],
                entry["N_h"],
                entry["n_h"],
            )
            for entry in entries
        )
        assert observed == pf.O8_EXPECTED_STRATA_N101
        # Stratum ordinals increase with the index, as the frozen schema
        # requires (plan §5.2: sorted by ascending ``stratum_index``).
        assert [entry["stratum_index"] for entry in entries] == [0, 1, 2, 3]
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_pending_usable_status_token_is_pending(tmp_path):
    """Q-4: 4B writes ``usable_status == "pending"`` for every stratum."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        summaries = _summary_by_category(repository, run.run_id)
        for category in (pf.CENSUS_CATEGORY, pf.LARGE_CATEGORY):
            entries = _strata_json(summaries[category])
            assert entries
            for entry in entries:
                assert entry["usable_status"] == "pending"
                assert entry["usable_status"] in pf.USABLE_STATUS_VOCABULARY
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_pending_usable_placeholders_before_enrichment(tmp_path):
    """Q-4: every ``u_*`` is JSON ``null`` and ``eligibility_rule`` null."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        summaries = _summary_by_category(repository, run.run_id)
        for category in (pf.CENSUS_CATEGORY, pf.LARGE_CATEGORY):
            for entry in _strata_json(summaries[category]):
                assert entry["u_demand_h"] is None
                assert entry["u_recent_h"] is None
                assert entry["u_quality_h"] is None
                assert entry["eligibility_rule"] is None
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9.3 — non-authoritative placeholders and the sampling-phase update path
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_category_level_usable_counts_are_non_authoritative_placeholders(tmp_path):
    """O10: the four category-level columns are untouched by ``persist``."""
    run = _run(pf.o10_categories())
    repository = _repository(tmp_path)
    try:
        # Chunk 3 pre-scoring state, created before 4B runs: four zero columns.
        _seed_run(repository, run.run_id, pf.o10_categories())
        before = _summary_by_category(repository, run.run_id)
        for category in pf.o10_categories():
            for column in pf.O10_PLACEHOLDER_COLUMNS:
                assert getattr(before[category], column) == 0

        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        after = _summary_by_category(repository, run.run_id)
        for category in pf.o10_categories():
            for column, expected in pf.O10_EXPECTED_PLACEHOLDERS.items():
                assert getattr(after[category], column) == expected
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_unique_enrichment_count_is_not_written_by_4b(tmp_path):
    """Q-1(b): ``unique_enrichment_count`` keeps its created placeholder."""
    run = _run(pf.o10_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o10_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        summaries = _summary_by_category(repository, run.run_id)
        for category in pf.o10_categories():
            assert summaries[category].unique_enrichment_count == 0
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_upsert_sampling_summary_updates_only_sampling_columns(tmp_path):
    """Q-2 update path: only the eight sampling-phase columns may change."""
    run = _run(pf.census_one_categories())
    repository = _repository(tmp_path)
    scoring_columns = (
        "discovery_status",
        "discovery_filter_verified",
        "discovery_unresolved_identity_count",
        "discovery_conflict_count",
        "discovery_duplicate_count",
        "unique_enrichment_count",
        "usable_demand_sample_count",
        "usable_recent_supply_sample_count",
        "usable_quality_sample_count",
        "breadth_source",
        "breadth_completeness_status",
        "discovery_bounded_by_verified_total",
        "demand_stratum_eligibility_coverage",
        "recent_supply_stratum_eligibility_coverage",
        "quality_stratum_eligibility_coverage",
        "score_state",
        "evidence_grade",
        "rankability_status",
        "missing_components_json",
        "warnings_json",
        "reference_size",
        "reference_usable_counts_json",
        "ranking_sensitivity_json",
    )
    try:
        _seed_run(repository, run.run_id, pf.census_one_categories())
        before = _summary_by_category(repository, run.run_id)[pf.DIGEST_VECTOR_CATEGORY]
        with repository.transaction():
            repository.upsert_sampling_summary(
                run.run_id,
                pf.DIGEST_VECTOR_CATEGORY,
                discovered_population_count=1,
                enriched_sample_count=1,
                sample_is_census=True,
                sampling_basis=SamplingBasis.CENSUS.value,
                sample_fraction=1.0,
                overlap_category_count=0,
                overlap_sample_percentage=0.0,
                stratum_statistics_json=pf.O9_STRATUM_STATISTICS_JSON,
                computed_at_utc=pf.COMPUTED_AT_UTC,
            )
        after = _summary_by_category(repository, run.run_id)[pf.DIGEST_VECTOR_CATEGORY]
        for column in scoring_columns:
            assert getattr(after, column) == getattr(before, column), column
        for column in pf.O10_SAMPLING_PHASE_COLUMNS:
            assert getattr(after, column) is not None
        assert after.discovered_population_count == 1
        assert after.sample_fraction == pytest.approx(1.0, abs=1e-9)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_sample_fraction_distinct_from_eligibility_coverage(tmp_path):
    """4B writes ``sample_fraction`` only; it never fabricates coverage."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        before = _summary_by_category(repository, run.run_id)
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        after = _summary_by_category(repository, run.run_id)
        for category in (pf.CENSUS_CATEGORY, pf.LARGE_CATEGORY):
            # Chunk 3 created them at 0.0; 4B leaves them (Chunk 7B/8 own them)
            # and never substitutes sample_fraction into them.
            assert (
                after[category].demand_stratum_eligibility_coverage
                == before[category].demand_stratum_eligibility_coverage
                == 0.0
            )
            assert (
                after[category].recent_supply_stratum_eligibility_coverage
                == before[category].recent_supply_stratum_eligibility_coverage
                == 0.0
            )
            assert (
                after[category].quality_stratum_eligibility_coverage
                == before[category].quality_stratum_eligibility_coverage
                == 0.0
            )
            fraction = after[category].sample_fraction
            assert fraction == pytest.approx(
                pf.o6_expected_sample_fractions()[category], abs=1e-9
            )
            assert fraction != after[category].demand_stratum_eligibility_coverage
            assert (
                fraction != after[category].recent_supply_stratum_eligibility_coverage
            )
            assert fraction != after[category].quality_stratum_eligibility_coverage
    finally:
        repository.close()


# --------------------------------------------------------------------------
# 9.3 — idempotence, duplicate rejection, and read-back verification
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_duplicate_membership_is_rejected_and_does_not_duplicate(tmp_path):
    """The PK rejects a duplicate membership; re-persisting adds no second row."""
    run = _run(pf.census_one_categories())
    category = pf.DIGEST_VECTOR_CATEGORY
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, (category,))
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        rows_after_first = repository.get_sample_members(run.run_id, category)
        assert len(rows_after_first) == 1

        # Re-materializing is idempotent: same path, still one membership.
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        rows_after_second = repository.get_sample_members(run.run_id, category)
        assert len(rows_after_second) == 1
        assert (
            rows_after_second[0].asset_identity_key
            == rows_after_first[0].asset_identity_key
        )

        # A hand-built duplicate row is rejected by the primary key.
        duplicate = rows_after_second[0]
        with pytest.raises(database.UniqueConstraintViolation):
            repository.insert_sample_members((duplicate,))
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_persisted_values_verify_against_pure_result(tmp_path):
    """A clean round trip verifies: empty ``mismatches`` and real row counts."""
    run = _run(pf.o6_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o6_categories())
        with repository.transaction():
            persist_report = database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        report = database.verify_persisted_sampling(repository, run)
        assert report.run_id == run.run_id
        assert report.mismatches == ()
        assert report.categories_written == len(pf.o6_categories())
        assert report.sample_members_written == persist_report.sample_members_written
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_verification_reports_a_tampered_value(tmp_path):
    """Negative: a tampered summary value produces a named mismatch."""
    run = _run(pf.census_one_categories())
    category = pf.DIGEST_VECTOR_CATEGORY
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, (category,))
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        # Tamper the persisted summary through the public write path. The
        # forwarded ``discovery_status`` keeps the create path from inventing.
        repository.upsert_sampling_summary(
            run.run_id,
            category,
            discovered_population_count=2,
            enriched_sample_count=1,
            sample_is_census=True,
            sampling_basis=SamplingBasis.CENSUS.value,
            sample_fraction=1.0,
            overlap_category_count=0,
            overlap_sample_percentage=0.0,
            stratum_statistics_json=pf.O9_STRATUM_STATISTICS_JSON,
            computed_at_utc=pf.COMPUTED_AT_UTC,
        )
        report = database.verify_persisted_sampling(repository, run)
        assert report.mismatches != ()
        # Chunk 2 §2.2 / LREQ-SEC-020: mismatch strings name the column and
        # category only -- never an identity string.
        assert any(
            "discovered_population_count" in mismatch for mismatch in report.mismatches
        )
        for mismatch in report.mismatches:
            for row in repository.get_sample_members(run.run_id, category):
                assert row.asset_identity_key not in mismatch
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_verification_does_not_assert_category_usable_counts(tmp_path):
    """Verification never treats the category-level placeholders as measured."""
    run = _run(pf.o10_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.o10_categories())
        with repository.transaction():
            database.persist_run_sampling(
                repository, run, computed_at_utc=pf.COMPUTED_AT_UTC
            )
        report = database.verify_persisted_sampling(repository, run)
        assert report.mismatches == ()
        summaries = _summary_by_category(repository, run.run_id)
        for category in pf.o10_categories():
            for column, expected in pf.O10_EXPECTED_PLACEHOLDERS.items():
                assert getattr(summaries[category], column) == expected
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SMP-080")
def test_persist_requires_explicit_utc_and_reads_no_clock(tmp_path):
    """``persist_run_sampling`` takes ``computed_at_utc`` as a required keyword."""
    import inspect

    run = _run(pf.census_one_categories())
    repository = _repository(tmp_path)
    try:
        _seed_run(repository, run.run_id, pf.census_one_categories())

        signature = inspect.signature(database.persist_run_sampling)
        parameter = signature.parameters["computed_at_utc"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty

        # A ``None`` timestamp cannot be silently substituted by a clock read.
        with pytest.raises(Exception):
            database.persist_run_sampling(repository, run, computed_at_utc=None)
    finally:
        repository.close()
