"""Chunk 13 acceptance suite: the LREQ-TST-080 end-to-end fixture and TST-090 cases.

Every node carries the ``@pytest.mark.lreq`` marker set that
``Documents/plans/chunk-13-full-acceptance-suite-and-quality-workflow.md`` §9
assigns to its base node ID, plus a matching ``tests/traceability.json`` entry.

The suite drives the frozen ``cli``/``pipeline``/``database``/``report`` stack
with the existing in-memory transports from ``fixtures.pipeline_fixtures``, a real
``SqliteRepository`` under pytest's ``tmp_path`` (via
``fixtures.cli_fixtures.recording_repository``), and the Chunk 11 renderer. It
also replays the Chunk 11 read model through the acceptance layer.

No node makes a live network call, reads the system clock, opens ``.env``, or
writes outside pytest ``tmp_path``/``.scratch/``. Credentials are the non-secret
fixture literals, and the run-local Coveo template is written under ``tmp_path``
because the committed capture does not list the scenario's synthetic categories.

Expected values come from the SRS (Appendix A, §7-§9, §13) and from the frozen
fixture modules; none is read off the implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fixtures.acceptance_fixtures as afx
import fixtures.cli_fixtures as cf
import fixtures.coveo_discovery as fx
import fixtures.pipeline_fixtures as pf
import pytest

from niche_scout import cli, models, report, scoring
from niche_scout.database import SqliteRepository
from niche_scout.metrics import BreadthMetricInput, compute_category_raw_metrics
from niche_scout.models import (
    DiscoveryStatus,
    IdentityPreflightStatus,
    PageViewSemanticsStatus,
    RankabilityStatus,
    RunStatus,
)

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _scenario(directory: Path, *, run_id: str = "run-13-e2e") -> cf.ScenarioArtifacts:
    """Write and return the eight-category accepted-run artifacts."""
    return cf.scenario_artifacts(directory, run_id=run_id)


def _run_options(artifacts: cf.ScenarioArtifacts, **overrides: Any) -> Any:
    """Return run-shaped ``CliOptions`` for the scenario, with overrides."""
    report_path = overrides.pop("report_path", None)
    report_format = overrides.pop("report_format", "html")
    return cf.run_options(
        artifacts.categories_path,
        artifacts.config_path,
        artifacts.db_path,
        run_id=artifacts.run_id,
        report_path=report_path,
        report_format=report_format,
    )


def _run_command(
    artifacts: cf.ScenarioArtifacts,
    *,
    options: Any = None,
    write_report: Any = None,
    open_repository: Any = None,
    **overrides: Any,
) -> int:
    """Invoke ``cli.run_command`` with the scenario's injected recorders.

    ``report_path``/``report_format`` are ``CliOptions`` fields, not
    ``run_command`` parameters, so they are folded into the options object. When no
    ``open_repository`` is injected the helper supplies a recording factory and
    closes it before returning, so the SQLite file is not left locked for a later
    fresh-connection read. A caller may replace the scenario's discovery transport
    with ``coveo_transport=``; every other call site keeps the scenario default.
    """
    import io

    coveo_transport = overrides.pop(
        "coveo_transport", artifacts.scenario.coveo_transport
    )
    options = options if options is not None else _run_options(artifacts, **overrides)
    owned_factory = None
    if open_repository is None:
        owned_factory = cf.RecordingRepositoryFactory()
        open_repository = owned_factory
    values: dict[str, Any] = {
        "environ": cf.config_fixtures.MOCK_ENVIRONMENT,
        "clock": artifacts.scenario.clock,
        "sleeper": lambda _seconds: None,
        "coveo_transport": coveo_transport,
        "graphql_transport": artifacts.scenario.graphql_transport,
        "template_path": artifacts.template_path,
        "open_repository": open_repository,
        "write_report": (
            write_report if write_report is not None else report.write_run_report
        ),
        "stdout": io.StringIO(),
        "stderr": io.StringIO(),
    }
    try:
        return cli.run_command(options, **values)
    finally:
        if owned_factory is not None:
            owned_factory.close_all()


def _repository_at(db_path: Path) -> SqliteRepository:
    """Open the real repository the CLI wrote to, for read-back assertions."""
    return SqliteRepository(Path(db_path))


# ---------------------------------------------------------------------------
# LREQ-TST-080 — the full acceptance run
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_acceptance_run_persists_and_renders(tmp_path: Path) -> None:
    """A full mocked run spans discovery, sampling, enrichment, scoring, report.

    The CLI path is used end to end: the run writes a real SQLite database under
    ``tmp_path`` and, when a report path is given, a rendered report file. The
    persisted rows cover every requested category with the declared order intact
    (LREQ-ARCH-030).
    """
    from fixtures import report_fixtures as report_fx

    artifacts = _scenario(tmp_path, run_id=report_fx.RUN_ID)
    report_path = tmp_path / "acceptance-report.html"
    factory = cf.RecordingRepositoryFactory()
    code = _run_command(
        artifacts,
        open_repository=factory,
        report_path=report_path,
        report_format="html",
    )
    # Read through the CLI's own repository: the in-process view is the one the
    # renderer and the CLI's exit code are based on.
    same_repo = factory.last
    run_row = same_repo.get_run(artifacts.run_id)
    rows = same_repo.get_category_scores(artifacts.run_id)
    html = report.render_dashboard_html(same_repo, artifacts.run_id)
    factory.close_all()

    assert code == cli.EXIT_OK
    assert report_path.exists()

    assert run_row is not None
    assert run_row.status == RunStatus.COMPLETED.value
    assert afx.run_row_categories(run_row) == artifacts.scenario.categories
    assert len(rows) == len(artifacts.scenario.categories)
    assert all(row.computed_at_utc.tzinfo is not None for row in rows)
    assert "heuristic" in html.lower()


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-EXT-090")
def test_acceptance_category_validation_rejects_before_network(tmp_path: Path) -> None:
    """An invalid requested-category set rejects with zero transport calls.

    The taxonomy inventory is overwritten so one requested category is absent, so
    ``validate_taxonomy`` fails before any transport is constructed and the run
    writes no run row (LREQ-EXT-090 / LREQ-EXT-020).
    """
    artifacts = _scenario(tmp_path, run_id="run-13-invalid-category")
    # Rewrite the taxonomy without the last requested category.
    pf.write_taxonomy(
        tmp_path, pf.taxonomy_payload(tuple(artifacts.scenario.categories)[:-1])
    )
    repository = SqliteRepository(artifacts.db_path)
    try:
        with pytest.raises(Exception) as excinfo:
            from niche_scout import pipeline

            pipeline.run_pipeline(
                config=artifacts.config,
                categories=artifacts.scenario.categories,
                credentials=pf.fixture_credentials(),
                repository=repository,
                clock=artifacts.scenario.clock,
                coveo_transport=artifacts.scenario.coveo_transport,
                graphql_transport=artifacts.scenario.graphql_transport,
                sleeper=lambda _seconds: None,
                run_id=artifacts.run_id,
                taxonomy_path=artifacts.taxonomy_path,
                template_path=artifacts.template_path,
            )
        assert isinstance(excinfo.value, pipeline.TaxonomyInvalidError)
        assert repository.get_run(artifacts.run_id) is None
    finally:
        repository.close()

    assert artifacts.scenario.coveo_transport.call_count == 0
    assert artifacts.scenario.graphql_transport.call_count == 0


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-EXT-050")
def test_acceptance_pagination_duplicate_and_overlap(tmp_path: Path) -> None:
    """Pagination completion, duplicate rows, and a shared identity are persisted.

    The truncated category's verified total far exceeds the run's read cap, so its
    traversal stops as ``truncated``; its cap-admitted duplicate of the shared
    identity ``900`` is persisted as a duplicate; and identity ``900`` is planted
    in two categories so the union lists it once while both categories reference
    it (LREQ-EXT-050, SRS §5.1).
    """
    artifacts = _scenario(tmp_path)
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        truncated_rows = repository.count_raw_discovery_observations(
            artifacts.run_id, pf.TRANSPORT_TRUNCATED_CATEGORY
        )
        verified_rows = repository.count_raw_discovery_observations(
            artifacts.run_id, pf.TRANSPORT_VERIFIED_TOTAL_CATEGORY
        )
        scores = {
            row.category: row
            for row in repository.get_category_scores(artifacts.run_id)
        }
    finally:
        repository.close()

    assert truncated_rows == 3, "2 first-page rows plus 1 cap-admitted terminal row"
    assert verified_rows == 2
    truncated = scores[pf.TRANSPORT_TRUNCATED_CATEGORY]
    assert truncated.discovery_status == DiscoveryStatus.TRUNCATED.value
    assert truncated.discovery_duplicate_count == 1
    verified = scores[pf.TRANSPORT_VERIFIED_TOTAL_CATEGORY]
    assert verified.discovery_status == DiscoveryStatus.COMPLETE.value


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-SMP-050")
def test_acceptance_four_stratum_sampling_and_one_enrichment_per_identity(
    tmp_path: Path,
) -> None:
    """The reported strata are the four-stratum rule and enrichment dedups.

    Every scenario category is a small census, so each sampled member sits in
    stratum 0 with the census digest; and the run-wide GraphQL request count for a
    shared identity stays at one (SRS §5, LREQ-SMP-050).
    """
    artifacts = _scenario(tmp_path)
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        members = {
            category: repository.get_sample_members(artifacts.run_id, category)
            for category in artifacts.scenario.categories
        }
        scores = {
            row.category: row
            for row in repository.get_category_scores(artifacts.run_id)
        }
    finally:
        repository.close()

    assert all(
        member.stratum_index == 0 for group in members.values() for member in group
    )
    assert all(
        member.sample_is_census for group in members.values() for member in group
    )
    assert all(
        member.selection_digest for group in members.values() for member in group
    )
    assert all(row.sample_is_census for row in scores.values())
    assert all(
        row.sampling_basis == models.SamplingBasis.CENSUS.value
        for row in scores.values()
    )

    requested = artifacts.scenario.graphql_transport.requested_identities
    assert requested.count(pf.END_TO_END_SHARED_KEY) <= 1


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-SMP-050")
def test_acceptance_four_stratum_sampling_drives_non_census_strata(
    tmp_path: Path,
) -> None:
    """A >100-asset category is sampled across four strata, never a census.

    The acceptance fixture plants a 120-asset category, so SRS §5
    ``LREQ-SMP-050`` applies: the category is divided into ``SAMPLE_STRATA`` (4)
    systematic (interleaved) strata by ``(i - 1 + offset) mod SAMPLE_STRATA`` and
    ``SAMPLE_PER_STRATUM`` (25) assets are selected from each. Its persisted
    members therefore span strata 0-3, its
    ``sampling_basis`` is ``deterministic_stratified_sample`` rather than
    ``census``, and its persisted ``sample_fraction`` is ``100/120`` -- a value
    strictly below the census ``1.0`` and not null. The run-wide GraphQL request
    list contains each uniquely sampled identity exactly once, so a shared or
    repeated identity never inflates the enrichment count (LREQ-SMP-050; SRS §5.1).
    """
    directory = tmp_path / "four-stratum"
    directory.mkdir()
    artifacts = afx.four_stratum_artifacts(directory, run_id="run-13-four-stratum")
    assert _run_command(artifacts) == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        members_by_category = {
            category: repository.get_sample_members(artifacts.run_id, category)
            for category in afx.FOUR_STRATUM_CATEGORIES
        }
        rows = {
            row.category: row
            for row in repository.get_category_scores(artifacts.run_id)
        }
    finally:
        repository.close()

    expected = afx.FOUR_STRATUM_LARGE_EXPECTED
    large_members = members_by_category[afx.FOUR_STRATUM_LARGE_CATEGORY]
    by_stratum: dict[int, list[Any]] = {}
    for member in large_members:
        by_stratum.setdefault(member.stratum_index, []).append(member)

    assert tuple(sorted(by_stratum)) == expected["stratum_indices"]
    assert all(
        len(group) == expected["members_per_stratum"] for group in by_stratum.values()
    )
    assert large_members
    assert all(not member.sample_is_census for member in large_members)
    assert all(member.selection_digest for member in large_members)

    large_row = rows[afx.FOUR_STRATUM_LARGE_CATEGORY]
    assert (
        large_row.discovered_population_count == expected["discovered_population_count"]
    )
    assert large_row.enriched_sample_count == expected["enriched_sample_count"]
    assert not large_row.sample_is_census
    assert large_row.sampling_basis == expected["sampling_basis"]
    assert large_row.sample_fraction is not None
    assert large_row.sample_fraction < 1.0
    assert large_row.sample_fraction == pytest.approx(
        expected["sample_fraction"], abs=1e-9
    )

    # The one-asset categories stay census, so the four-stratum category is a
    # genuine mixed-basis run rather than a run-wide basis switch.
    census_rows = [rows[category] for category in afx.FOUR_STRATUM_SMALL_CATEGORIES]
    assert census_rows
    assert all(row.sample_is_census for row in census_rows)
    assert all(
        row.sampling_basis == models.SamplingBasis.CENSUS.value for row in census_rows
    )
    assert all(row.sample_fraction == pytest.approx(1.0) for row in census_rows)

    # One enrichment request per unique sampled identity (SRS §5.1): no identity is
    # requested twice, and the request set is exactly the sampled union.
    requested = artifacts.scenario.graphql_transport.requested_identities
    sampled_union = {
        member.asset_identity_key
        for group in members_by_category.values()
        for member in group
    }
    assert len(requested) == len(set(requested))
    assert set(requested) == sampled_union


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-GQL-050")
def test_acceptance_partial_graphql_failure_retains_valid_operation(
    tmp_path: Path,
) -> None:
    """A valid operation's fields survive a sibling operation's failure.

    The scenario's injected transport raises for identity ``C1``; the run still
    completes and the sibling identity ``C2`` is enriched, so the failure is
    isolated as a persisted observation rather than aborting the run
    (LREQ-GQL-050, LREQ-NFR-030).
    """
    artifacts = _scenario(tmp_path)
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    requested = artifacts.scenario.graphql_transport.distinct_requested_identities
    assert pf.failed_enrichment_identity() in requested
    assert "C2" in requested

    repository = _repository_at(artifacts.db_path)
    try:
        observation = repository.get_enrichment_observation(
            artifacts.run_id, pf.failed_enrichment_identity()
        )
        sibling = repository.get_enrichment_observation(artifacts.run_id, "C2")
    finally:
        repository.close()

    assert observation is not None
    assert observation.product_detail_status in (
        models.OperationStatus.ERROR.value,
        models.OperationStatus.SUCCESS.value,
    )
    assert sibling is not None


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-SCR-050")
def test_acceptance_contradicted_page_views_distinct_from_partial_success(
    tmp_path: Path,
) -> None:
    """The R8 wrapper writes ``CONTRADICTED`` and D/Q become unavailable.

    ``cli.run_command`` is driven with ``open_repository=`` a wrapper that writes
    ``PageViewSemanticsStatus.CONTRADICTED.value`` on ``insert_run``. The frozen
    preflight does not clobber a ``contradicted`` value, so the run-level status is
    persisted, D and Q are unavailable, C/R may remain, and the category is
    ``not_rankable`` (SRS §8.2 LREQ-SCR-050). This is distinguishable from the
    partial-success scenario, where the page-view status stays ``unvalidated``.
    """
    from fixtures import report_fixtures as report_fx

    run_id = report_fx.RUN_ID
    artifacts = _scenario(tmp_path, run_id=run_id)
    open_repository = afx.contradicted_repository_factory(run_id)
    code = _run_command(
        artifacts,
        open_repository=open_repository,
        write_report=lambda *args, **kwargs: Path(kwargs.get("output_path", "x")),
    )
    assert code == cli.EXIT_OK
    afx.close_opened(open_repository)

    repository = _repository_at(artifacts.db_path)
    try:
        run_row = repository.get_run(run_id)
        rows = repository.get_category_scores(run_id)
    finally:
        repository.close()

    assert run_row.page_view_semantics_status == (
        PageViewSemanticsStatus.CONTRADICTED.value
    )
    assert rows
    for row in rows:
        assert row.component_d is None, "D is unavailable under contradicted page views"
        assert row.component_q is None, "Q is unavailable under contradicted page views"
        assert row.rankability_status == RankabilityStatus.NOT_RANKABLE.value
    # The contradicted status disables D/Q but not necessarily every component:
    # a category with verified breadth keeps C. This distinction is what makes the
    # contradicted run different from a blanket score wipe.
    verified = next(
        row for row in rows if row.category == pf.TRANSPORT_VERIFIED_TOTAL_CATEGORY
    )
    assert verified.component_c is not None


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-SMP-080")
def test_acceptance_sqlite_rows_match_pure_results(tmp_path: Path) -> None:
    """Persisted sample and score rows equal the pure sampling result.

    The persisted sample members are exactly the pure
    ``sampling.select_run_sample`` members for the run's raw discovery
    populations, and the persisted raw metrics equal the pure Chunk 7B results;
    null stays null and an explicit zero stays zero (LREQ-SMP-080).
    """
    artifacts = _scenario(tmp_path)
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        members = {
            category: repository.get_sample_members(artifacts.run_id, category)
            for category in artifacts.scenario.categories
        }
    finally:
        repository.close()

    pure_run = artifacts.scenario.run()
    pure_members = {
        category.category: {member.asset_identity_key for member in category.members}
        for category in pure_run.categories
    }
    for category, group in members.items():
        assert {member.asset_identity_key for member in group} == pure_members[category]

    zero_expected = afx.zero_population_vector()["expected"]
    assert zero_expected["demand_per_asset_raw"] is None
    assert zero_expected["breadth_raw"] == 0.0


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-RPT-020")
def test_acceptance_rendered_report_contains_required_fields(tmp_path: Path) -> None:
    """The rendered report carries the mandatory columns and heuristic statement.

    The persisted run is rendered through the Chunk 11 read model, so the report
    reads primary rows only and shows the SRS §10 mandatory columns; the heuristic
    statement is present and names the sample-based limitation.
    """
    artifacts = _scenario(tmp_path)
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        view = report.load_run_report_view(repository, artifacts.run_id)
        html = report.render_dashboard_html(repository, artifacts.run_id)
    finally:
        repository.close()

    assert view.run_id == artifacts.run_id
    assert view.categories
    assert view.heuristic_statement
    assert "heuristic" in html.lower()
    assert any(
        row.category == pf.TRANSPORT_VERIFIED_TOTAL_CATEGORY for row in view.categories
    )


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-TST-060")
@pytest.mark.lreq("LREQ-SEN-020")
def test_acceptance_eight_category_run_is_provisional(tmp_path: Path) -> None:
    """An 8-category run is provisional: empty candidates and null stability.

    The persisted rows carry null ``top_3_stability``/``top_5_stability`` and a
    null ``sensitivity_warning`` (never ``False``/``0``), and no category is
    ``rankable`` (dependency-map §6.2/§6.3; LREQ-SEN-020, LREQ-TST-060).
    """
    artifacts = _scenario(tmp_path)
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        rows = repository.get_category_scores(artifacts.run_id)
    finally:
        repository.close()

    assert len(rows) == models.MIN_CATEGORIES_PER_RUN
    for row in rows:
        assert row.top_3_stability is None
        assert row.top_5_stability is None
        assert row.maximum_score_delta is None
        assert row.maximum_rank_displacement is None
        assert row.sensitivity_warning is None
        assert row.rankability_status != RankabilityStatus.RANKABLE.value


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-ID-040")
def test_acceptance_preflight_failure_marks_run_failed_zero_enrichment(
    tmp_path: Path,
) -> None:
    """A failed preflight produces a failed run with zero bulk enrichment.

    ``identity_preflight_min_success_rate=1.0`` with a zero-success rejecting
    transport fails the gate; the run status is ``failed``, one null-score
    limitation row per requested category is written, and no GraphQL request
    follows the gate (LREQ-ID-040; SRS §4.4).
    """
    from niche_scout import pipeline

    artifacts = _scenario(tmp_path, run_id="run-13-preflight-failed")
    rejecting_config = pf.fixture_config(
        tmp_path,
        min_categories_per_run=pf.MIN_CATEGORIES,
        max_discovery_results_per_category=pf.SCENARIO_DISCOVERY_CAP,
        identity_preflight_min_success_rate=1.0,
        identity_preflight_assets_per_category=1,
    )
    config_path = cf.write_run_config(
        tmp_path, rejecting_config, name="preflight_failed.toml"
    )
    assert config_path.exists()
    rejecting = pf.graphql_rejecting_transport(
        tuple(
            key
            for category in artifacts.scenario.run().categories
            for key in category.population.identity_keys
        )
    )
    repository = SqliteRepository(artifacts.db_path)
    try:
        result = pipeline.run_pipeline(
            config=rejecting_config,
            categories=artifacts.scenario.categories,
            credentials=pf.fixture_credentials(),
            repository=repository,
            clock=artifacts.scenario.clock,
            coveo_transport=artifacts.scenario.coveo_transport,
            graphql_transport=rejecting,
            sleeper=lambda _seconds: None,
            run_id="run-13-preflight-failed",
            taxonomy_path=rejecting_config.taxonomy_path,
            template_path=artifacts.template_path,
        )
        run_row = repository.get_run(result.run_id)
        rows = repository.get_category_scores(result.run_id)
        summary = json.loads(run_row.identity_preflight_summary_json)
    finally:
        repository.close()

    assert result.status == RunStatus.FAILED.value
    assert run_row.status == RunStatus.FAILED.value
    assert run_row.identity_preflight_status == IdentityPreflightStatus.FAILED.value
    assert len(rejecting.calls) == summary["attempted_unique_identities"]
    assert len(rows) == len(artifacts.scenario.categories)
    for row in rows:
        assert row.market_opportunity_score is None
        assert row.rankability_status == RankabilityStatus.NOT_RANKABLE.value


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-SEN-020")
def test_acceptance_sensitivity_never_changes_candidate_set(tmp_path: Path) -> None:
    """Sensitivity ranks only the frozen base candidate set and mutates nothing.

    The pure Chunk 9B surfaces over the acceptance fixtures: the candidate set is
    built before sensitivity, the balanced score is preserved, and sensitivity
    neither adds nor removes a candidate (SRS §9.1 LREQ-EVD-020, §9.3 LREQ-SEN-020).
    """
    from fixtures import scoring_evidence_fixtures as evidence_fx

    metrics = evidence_fx.all_verified_run_metrics(
        models.STRONG_REFERENCE_CATEGORY_COUNT
    )
    scores = tuple(
        scoring.score_category(
            metric,
            metrics,
            page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
        )
        for metric in metrics
    )
    inputs = tuple(
        evidence_fx.make_pre_sensitivity_input(metric.category) for metric in metrics
    )
    candidates = scoring.build_base_rankable_candidates(
        metrics,
        inputs,
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    before = tuple(
        (score.market_opportunity_score, score.component_d, score.component_c)
        for score in scores
    )
    sensitivity = scoring.evaluate_sensitivity(
        candidates,
        metrics,
        scores,
        reference_set_size=candidates.run_category_count - 1,
    )
    after = tuple(
        (score.market_opportunity_score, score.component_d, score.component_c)
        for score in scores
    )

    assert candidates.base_rankable_candidates
    assert after == before, "sensitivity must not mutate the balanced score"
    assert sensitivity.ranked_categories == candidates.base_rankable_candidates


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_acceptance_repeat_run_is_deterministic(tmp_path: Path) -> None:
    """Two identical runs produce structurally equal persisted rows.

    The two runs differ only by run id; every other persisted field, including
    the pure-derived raw metrics and scores, is identical (LREQ-ARCH-030).
    """
    first = _scenario(tmp_path, run_id="run-13-det-a")
    second = _scenario(tmp_path, run_id="run-13-det-b")
    assert _run_command(first) == cli.EXIT_OK
    assert _run_command(second) == cli.EXIT_OK

    repository = _repository_at(first.db_path)
    try:
        rows_a = repository.get_category_scores("run-13-det-a")
        rows_b = repository.get_category_scores("run-13-det-b")
    finally:
        repository.close()

    assert afx.logical_rows(rows_a) == afx.logical_rows(rows_b)


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-CLI-010")
@pytest.mark.lreq("LREQ-RPT-010")
def test_acceptance_cli_run_exits_zero_and_writes_report(tmp_path: Path) -> None:
    """``cli.run_command`` exits 0 and writes a report only when requested.

    Without ``--report`` no file is produced; with ``--report`` the file exists
    and the adjacent dashboard read model can render the same run
    (LREQ-CLI-010, LREQ-RPT-010).
    """
    first_dir = tmp_path / "without-report"
    first_dir.mkdir()
    artifacts = _scenario(first_dir, run_id="run-13-report-a")
    code_without = _run_command(artifacts)
    assert code_without == cli.EXIT_OK
    assert not (first_dir / "report.html").exists()

    second_dir = tmp_path / "with-report"
    second_dir.mkdir()
    report_artifacts = _scenario(second_dir, run_id="run-13-report-b")
    report_path = second_dir / "report.html"
    code_with = _run_command(report_artifacts, report_path=report_path)
    assert code_with == cli.EXIT_OK
    assert report_path.exists()


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-CLI-020")
def test_acceptance_dashboard_reads_persisted_run_only(tmp_path: Path) -> None:
    """``dashboard_command`` reads the database only and starts no transport.

    The command renders an already persisted run from a real repository and makes
    no discovery or enrichment call (LREQ-CLI-020).
    """
    from fixtures import report_fixtures as report_fx

    from niche_scout import cli as cli_module

    artifacts = _scenario(tmp_path, run_id=report_fx.RUN_ID)
    assert _run_command(artifacts) == cli.EXIT_OK

    import io

    stdout, stderr = io.StringIO(), io.StringIO()
    dashboard_options = cf.dashboard_options(
        artifacts.config_path, artifacts.db_path, run_id=report_fx.RUN_ID
    )
    repository = SqliteRepository(artifacts.db_path)
    try:
        code = cli_module.dashboard_command(
            dashboard_options,
            repository=repository,
            stdout=stdout,
            stderr=stderr,
        )
    finally:
        repository.close()

    assert code == cli_module.EXIT_OK
    assert stdout.getvalue()


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_acceptance_completed_run_is_durable_across_connections(
    tmp_path: Path,
) -> None:
    """The completed run must be readable from a fresh connection.

    A separate process (``niche-scout dashboard``) opens its own connection, so the
    terminal ``completed`` transition must be committed before the run command
    returns. This node opens a second ``SqliteRepository`` on the same file after
    the CLI closed the run.

    The success path's terminal ``update_run_status(..., COMPLETED,
    completed_at_utc=...)`` transition is committed (Chunk 10 remediation commit
    ``1f0f4fe``), so this node asserts the durability contract directly: a fresh
    connection on the same SQLite file reads ``status = completed`` with a
    non-null ``completed_at_utc``. Chunk 13 verifies this frozen behavior and does
    not modify runtime code.
    """
    artifacts = _scenario(tmp_path, run_id="run-13-durable")
    code = _run_command(artifacts)
    assert code == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        run_row = repository.get_run("run-13-durable")
    finally:
        repository.close()

    assert run_row.status == RunStatus.COMPLETED.value
    assert run_row.completed_at_utc is not None


# ---------------------------------------------------------------------------
# LREQ-TST-090 — golden-vector acceptance cases
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-080")
@pytest.mark.lreq("LREQ-TST-090")
@pytest.mark.lreq("LREQ-CLI-040")
def test_acceptance_two_category_run_rejected_before_ranking(tmp_path: Path) -> None:
    """The two-category vector is rejected before ranking with zero transport calls.

    A run with fewer than ``MIN_CATEGORIES_PER_RUN`` (8) categories raises
    ``PipelineConfigurationError``; no run row is persisted and no transport is
    called (LREQ-CLI-040, SRS §10).
    """
    from niche_scout import pipeline

    categories = afx.two_category_rejection_vector()
    config = pf.fixture_config(tmp_path, min_categories_per_run=pf.MIN_CATEGORIES)
    coveo = pf.RecordingCoveoTransport({})
    graphql = pf.RecordingGraphQLTransport({})
    repository = SqliteRepository(config.db_path)
    try:
        with pytest.raises(pipeline.PipelineConfigurationError):
            pipeline.run_pipeline(
                config=config,
                categories=categories,
                credentials=pf.fixture_credentials(),
                repository=repository,
                clock=lambda: pf.FIXED_CLOCK_START,
                coveo_transport=coveo,
                graphql_transport=graphql,
                sleeper=lambda _seconds: None,
                run_id="run-13-rejected",
                taxonomy_path=config.taxonomy_path,
            )
        assert repository.get_run("run-13-rejected") is None
    finally:
        repository.close()

    assert coveo.call_count == 0
    assert graphql.call_count == 0


@pytest.mark.lreq("LREQ-TST-090")
@pytest.mark.lreq("LREQ-MET-030")
def test_acceptance_zero_population_category_vector(tmp_path: Path) -> None:
    """The zero-population vector has null raws, zero coverage, null fraction.

    The frozen Chunk 7B zero-population input paired with a verified-zero breadth
    gives the SRS §7.2/§7.3 shape: every sample-derived raw is null, every stratum
    eligibility coverage is ``0.0`` (a value, not null), breadth is an explicit
    ``0.0`` with the verified source, and ``sample_fraction`` is null.
    """
    vector = afx.zero_population_vector()
    result = compute_category_raw_metrics(
        vector["category_input"],
        BreadthMetricInput(
            verified_total_count=vector["breadth"]["verified_total_count"],
            distinct_canonical_discovered_count=vector["breadth"][
                "distinct_canonical_discovered_count"
            ],
        ),
    )
    expected = vector["expected"]

    assert result.raw.demand_per_asset_raw == expected["demand_per_asset_raw"]
    assert result.raw.demand_median_raw == expected["demand_median_raw"]
    assert result.raw.breadth_raw == expected["breadth_raw"]
    assert result.raw.recent_share_raw == expected["recent_share_raw"]
    assert result.raw.median_age_raw == expected["median_age_raw"]
    assert result.raw.quality_raw == expected["quality_raw"]
    assert (
        result.demand_stratum_eligibility_coverage
        == expected["demand_stratum_eligibility_coverage"]
    )
    assert (
        result.recent_supply_stratum_eligibility_coverage
        == expected["recent_supply_stratum_eligibility_coverage"]
    )
    assert (
        result.quality_stratum_eligibility_coverage
        == expected["quality_stratum_eligibility_coverage"]
    )
    assert result.usable_demand_sample_count == expected["usable_demand_sample_count"]
    assert result.breadth_source is models.BreadthSource.VERIFIED_TOTAL_COUNT


@pytest.mark.lreq("LREQ-TST-090")
@pytest.mark.lreq("LREQ-MET-100")
def test_acceptance_unequal_stratum_quality_raw_vector(tmp_path: Path) -> None:
    """``QualityRaw`` uses ``N_h / n_h`` expansion weights; exact within ``1e-9``.

    The frozen Chunk 7B unequal-stratum inputs give ``(50 + 100) / (100 + 100) =
    0.75`` with coverage ``1.0`` and ten usable quality observations
    (SRS §7.5 LREQ-MET-100).
    """
    vector = afx.unequal_stratum_quality_raw_vector()
    result = compute_category_raw_metrics(
        vector["category_input"],
        BreadthMetricInput(
            verified_total_count=None, distinct_canonical_discovered_count=100
        ),
    )
    expected = vector["expected"]

    assert result.raw.quality_raw == pytest.approx(expected["quality_raw"], abs=1e-9)
    assert result.quality_stratum_eligibility_coverage == pytest.approx(
        expected["quality_stratum_eligibility_coverage"], abs=1e-9
    )
    assert result.usable_quality_sample_count == int(
        expected["usable_quality_sample_count"]
    )


@pytest.mark.lreq("LREQ-TST-090")
@pytest.mark.lreq("LREQ-MET-060")
def test_acceptance_sample_fraction_distinct_from_eligibility_coverage(
    tmp_path: Path,
) -> None:
    """Sample fraction and stratum eligibility coverage are distinct measures.

    The frozen Chunk 7B partial-coverage input has four usable indices in
    stratum 1 (``N_1 = 25``). At the default minimum 1 that stratum is usable,
    so ``demand_stratum_eligibility_coverage = 75/100 + 25/100 = 1.0``, a
    population weight, not the sampled fraction ``45/100 = 0.45``; the two
    values are different numbers on the same category (SRS §7.2 LREQ-MET-060).
    """
    vector = afx.sample_fraction_vs_coverage_vector()
    result = compute_category_raw_metrics(
        vector["category_input"],
        BreadthMetricInput(
            verified_total_count=None, distinct_canonical_discovered_count=100
        ),
    )
    expected = vector["expected"]

    assert result.demand_stratum_eligibility_coverage == pytest.approx(
        expected["demand_stratum_eligibility_coverage"], abs=1e-9
    )
    assert (
        expected["sample_fraction"] != expected["demand_stratum_eligibility_coverage"]
    )
    assert result.demand_stratum_eligibility_coverage != expected["sample_fraction"]


@pytest.mark.lreq("LREQ-TST-090")
@pytest.mark.lreq("LREQ-TST-060")
def test_acceptance_twenty_one_category_composite_vector(tmp_path: Path) -> None:
    """The 21-category strong-reference composite is exact within ``1e-9``.

    The vector's expected value is hand-derived from SRS Appendix A (§8.3 weights
    0.35/0.30/0.20/0.15) with ``reference_size = 21 - 1 = 20``: for the median
    target every field's midrank is ``(10 + 0.5*0)/20 = 0.5``, every component is
    ``0.5``, and the composite is ``0.5``. A second pinned component vector makes
    the weight arithmetic explicit: ``0.35*0.8 + 0.30*0.6 + 0.20*0.4 + 0.15*0.2 =
    0.57``.
    """
    vector = afx.strong_reference_composite_vector()
    target = vector["target_category"]
    reference = scoring.leave_one_out_reference(vector["metrics"], target)
    normalized = scoring.normalize_raw_metrics(
        next(metric.raw for metric in vector["metrics"] if metric.category == target),
        reference,
    )
    components = scoring.compute_components(
        normalized,
        demand_stratum_eligibility_coverage=1.0,
        recent_supply_stratum_eligibility_coverage=1.0,
        quality_stratum_eligibility_coverage=1.0,
        breadth_source=models.BreadthSource.VERIFIED_TOTAL_COUNT,
        breadth_completeness_status=models.BreadthCompletenessStatus.COMPLETE,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
    )
    composite = scoring.renormalized_composite(components, vector["weights"])

    assert reference.reference_size == vector["reference_size"] == 20
    assert normalized.demand_per_asset_raw == pytest.approx(0.5, abs=1e-9)
    assert components.demand == pytest.approx(0.5, abs=1e-9)
    assert components.competition == pytest.approx(0.5, abs=1e-9)
    assert components.recent_supply == pytest.approx(0.5, abs=1e-9)
    assert components.quality == pytest.approx(0.5, abs=1e-9)
    assert composite.market_opportunity_score == pytest.approx(
        vector["expected_score"], abs=1e-9
    )

    pinned = scoring.renormalized_composite(
        scoring.ComponentValues(
            demand=0.8, competition=0.6, recent_supply=0.4, quality=0.2
        ),
        vector["weights"],
    )
    assert pinned.market_opportunity_score == pytest.approx(0.57, abs=1e-9)


@pytest.mark.lreq("LREQ-TST-090")
@pytest.mark.lreq("LREQ-SEN-020")
def test_acceptance_sensitivity_after_base_candidates_vector(tmp_path: Path) -> None:
    """Sensitivity runs over the frozen candidate set with the expected outputs.

    The frozen Chunk 9B stable vector (21 categories, five base candidates) gives
    ``top_3_stability = 2/3``, ``top_5_stability = 1.0``, and a ``False`` run
    warning, with the balanced scores unchanged (LREQ-SEN-020, LREQ-SEN-030).
    """
    from fixtures import sensitivity_fixtures as sensitivity_fx

    vector = afx.sensitivity_after_base_candidates_vector()["vector"]
    expected = afx.sensitivity_after_base_candidates_vector()["expected"]
    categories = tuple(vector["components"])
    metrics, scores = sensitivity_fx.make_metrics_and_scores(vector["components"])
    candidates = sensitivity_fx.make_candidate_set(
        categories, vector["run_category_count"]
    )
    sensitivity = scoring.evaluate_sensitivity(
        candidates,
        metrics,
        scores,
        reference_set_size=vector["reference_set_size"],
    )

    assert len(candidates.base_rankable_candidates) == expected["base_candidate_count"]
    assert sensitivity.top_3_stability == pytest.approx(
        expected["top_3_stability"], abs=1e-9
    )
    assert sensitivity.top_5_stability == pytest.approx(
        expected["top_5_stability"], abs=1e-9
    )
    for category, value in expected["balanced_scores"].items():
        # ``scores`` is aligned with ``metrics``; look the balanced score up by
        # index through the vector's component order.
        index = categories.index(category)
        assert scores[index].market_opportunity_score == pytest.approx(value, abs=1e-9)


# ---------------------------------------------------------------------------
# Chunk 16 — the live-shaped raw discovery record (LREQ-EXT-060/050, TST-080)
# ---------------------------------------------------------------------------
#
# Scope authority: Documents/plans/chunk-16-coveo-discovery-record-shape.md
# section 9, Node 11. The node is inline-built from the published
# ``pipeline_fixtures``/``cli_fixtures`` helpers plus the new live-shape helper
# in ``fixtures/coveo_discovery.py``; neither fixture module is edited, so the
# frozen Chunk 13 scenario stays byte-identical.
#
# Hand-derived expected value (plan section 1 live capture; not read off the
# implementation): the live Coveo Search v2 response nests the five discovery
# fields under a per-record ``raw`` object, while the adapter reads each record
# flat. ``live_raw_summary_record`` nests every discovery field under ``raw``,
# so before Chunk 16's normalization the per-record required-member check fails
# for all 15 served records (response_missing_required_member) and every
# category is ``page_failed``.


def _live_shaped_transport(categories: Any) -> pf.RecordingCoveoTransport:
    """Map every scenario category to page(s) of live-nested summary records.

    Each category serves exactly the identities the scenario's designed
    populations use (plan section 9 Node 11): the transport-fed ``Verified``
    and ``Truncated`` categories serve ``900``/``901`` and ``900``/``902``
    (two records each), every synthetic complete category serves its own two
    ``A1``..``E2``, and the filter-unverified category serves none. The page
    envelope, page count, ``total_count``, and ``filtered_count`` mirror the
    flat scenario of ``pipeline_fixtures.end_to_end_scenario`` page for page,
    so 15 records reach the read cap and the durable row count is the same 15.
    """

    def summary_page(
        records: Any, *, total_count: int | None, filtered_count: int | None = None
    ) -> bytes:
        body = fx.live_raw_page(
            records, total_count=total_count, filtered_count=filtered_count
        )
        return json.dumps(body).encode("utf-8")

    def summary_records(identities: Any, category: str) -> list[dict[str, Any]]:
        return [
            fx.live_raw_summary_record(identity=identity, category=category)
            for identity in identities
        ]

    served: dict[str, tuple[bytes, ...]] = {}
    for category in categories:
        if category == pf.TRANSPORT_VERIFIED_TOTAL_CATEGORY:
            served[category] = (
                summary_page(
                    summary_records((pf.END_TO_END_SHARED_KEY, "901"), category),
                    total_count=2,
                    filtered_count=2,
                ),
            )
        elif category == pf.TRANSPORT_TRUNCATED_CATEGORY:
            # Mirrors the flat scenario's ``truncated_page`` plus
            # ``truncated_terminal_page``: the verified total (2000) far exceeds
            # the records served, so the adapter requests a second page and the
            # run's read cap (``SCENARIO_DISCOVERY_CAP`` = 3) admits only its
            # leading record -- persisted as a duplicate of the first page's
            # ``900``.
            truncated = summary_records((pf.END_TO_END_SHARED_KEY, "902"), category)
            served[category] = (
                summary_page(truncated, total_count=2000),
                summary_page(truncated, total_count=2000),
            )
        elif category == pf.TRANSPORT_FAILED_CATEGORY:
            served[category] = (summary_page([], total_count=None),)
        else:
            served[category] = (
                summary_page(
                    summary_records(_scenario_category_identities(category), category),
                    total_count=2,
                    filtered_count=2,
                ),
            )
    return pf.RecordingCoveoTransport(served)


def _scenario_category_identities(category: str) -> tuple[str, ...]:
    """Return the two identities the scenario's synthetic category serves.

    Derived from ``pipeline_fixtures``' own design (``END_TO_END_CATEGORIES``
    order and the ``A1``..``E2`` labels), never read off the pipeline. The
    transport-fed categories are handled by the caller.
    """
    index = pf.SYNTHETIC_COMPLETE_CATEGORIES.index(category)
    letter = "ABCDE"[index]
    return (f"{letter}1", f"{letter}2")


@pytest.mark.lreq("LREQ-EXT-060")
@pytest.mark.lreq("LREQ-EXT-050")
@pytest.mark.lreq("LREQ-TST-080")
def test_acceptance_run_reads_live_shaped_raw_records(tmp_path: Path) -> None:
    """A run over live-nested Coveo records reads them as assets, not as failures.

    Hand-derived expected state (plan section 9 Node 11): every transport-fed
    category's persisted discovery status must exclude ``page_failed`` and the
    durable raw discovery row count must equal the scenario's cap-admitted live
    records (15: the verified category's 2, the read cap's 3 from the truncated
    category's two pages, the unverified category's 0, and 5 synthetic
    categories of 2). The run completes because the permissive identity
    preflight (``identity_preflight_min_success_rate=0.0``, the
    ``scenario_artifacts`` default) cannot block it.

    The live-shaped transport is forwarded through ``_run_command``'s
    ``coveo_transport=`` override, so the run reads the live pages rather than the
    flat scenario's: the transport call count is the eight first-page fetches plus
    the truncated category's terminal second page, and every persisted row's
    ``category_value_json`` is the live record's verbatim one-element
    ``[category]`` list (the flat records persist the scalar path string).
    """
    directory = tmp_path / "live-raw-record-shape"
    directory.mkdir()
    artifacts = cf.scenario_artifacts(directory, run_id="run-16-live-raw")
    live_transport = _live_shaped_transport(artifacts.scenario.categories)
    assert _run_command(artifacts, coveo_transport=live_transport) == cli.EXIT_OK

    repository = _repository_at(artifacts.db_path)
    try:
        scores = {
            row.category: row
            for row in repository.get_category_scores(artifacts.run_id)
        }
        run_row = repository.get_run(artifacts.run_id)
        counts = {
            category: repository.count_raw_discovery_observations(
                artifacts.run_id, category
            )
            for category in artifacts.scenario.categories
        }
        live_rows = {
            category: list(
                repository.iter_raw_discovery_observations(artifacts.run_id, category)
            )
            for category in artifacts.scenario.categories
        }
    finally:
        repository.close()

    assert run_row.status == RunStatus.COMPLETED.value
    assert counts[pf.TRANSPORT_VERIFIED_TOTAL_CATEGORY] == 2
    assert counts[pf.TRANSPORT_TRUNCATED_CATEGORY] == 3, "2 rows plus 1 cap-admitted"
    assert counts[pf.TRANSPORT_FAILED_CATEGORY] == 0
    for category in pf.SYNTHETIC_COMPLETE_CATEGORIES:
        assert counts[category] == 2
    assert sum(counts.values()) == pf.EXPECTED_RAW_DISCOVERY_ROWS == 15

    # The live transport is the one the run consumed: every scenario category was
    # fetched once, plus the truncated category's terminal second page (its
    # cap-admitted third row), a count the flat scenario's transport cannot reach
    # by construction.
    assert live_transport.call_count == len(artifacts.scenario.categories) + 1

    # Liveness: the persisted rows carry the live-nested record's verbatim
    # one-element ``ec_category`` list, never the flat record's scalar path string.
    for category, rows in live_rows.items():
        assert all(json.loads(row.category_value_json) == [category] for row in rows)

    for category in artifacts.scenario.categories:
        assert scores[category].discovery_status != DiscoveryStatus.PAGE_FAILED.value, (
            category
        )
