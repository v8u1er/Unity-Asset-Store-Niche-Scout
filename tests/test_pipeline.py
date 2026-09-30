"""Chunk 10 analytical tests for the run-level pipeline entry point.

Every test here carries exactly the ``@pytest.mark.lreq`` marker set that
``Documents/plans/chunk-10-pipeline-orchestration.md`` section 9 assigns to its
base node ID, plus a matching entry in ``tests/traceability.json``. The module
tests the SRS-prescribed run sequence (SRS §3.2, §3.3, §4.4, §8.1, §9.1, §9.3,
§10, §11) through ``run_pipeline`` with an injected clock, in-memory Coveo and
GraphQL transports over a run-local discovery template (written under pytest's
``tmp_path`` by the fixture, because the committed capture does not list the
scenario's synthetic categories), and a real file-backed repository under
pytest's ``tmp_path``. No test performs network I/O, reads the system clock, or
carries a real credential.

Expected values are derived by hand in ``tests/fixtures/pipeline_fixtures.py``
(or by a frozen fixture builder from an earlier chunk) and are never read off
the implementation.
"""

from __future__ import annotations

import json
import logging
import re
import socket
from pathlib import Path
from typing import Any, Iterator, Sequence

import fixtures.pipeline_fixtures as fx
import pytest
from fixtures import identity_preflight_vectors as pf
from fixtures.scoring_evidence_fixtures import (
    make_pre_sensitivity_input,
    verified_metrics,
)

from niche_scout import models, pipeline, sampling, scoring
from niche_scout.config import Credentials
from niche_scout.database import SqliteRepository
from niche_scout.models import (
    DiscoveryStatus,
    IdentityPreflightStatus,
    RunStatus,
)

# ---------------------------------------------------------------------------
# Chunk 10 surfaces that do not exist until the implementation lands.
#
# The module is written BEFORE ``run_pipeline`` and must still IMPORT so pytest
# can collect it: every pipeline symbol the tests use is resolved at call time
# through :func:`_pipeline_symbol`, so a missing name fails the node that needs
# it instead of failing the whole module's collection. This is the expected
# pre-implementation state for ``run_pipeline``, the two run-level error types,
# ``PipelineResult``, ``taxonomy_sha256_for``, and ``category_status_for``.
# ---------------------------------------------------------------------------


def _pipeline_symbol(name: str) -> Any:
    """Return ``niche_scout.pipeline.<name>`` or fail for that node only.

    The resolver keeps the pre-implementation state per-node: a test that needs
    an unwritten symbol fails with the assertion below, and every other node
    still runs, which is what plan §9's "collected without syntax errors and
    failing only because the implementation is missing" requires.
    """
    value = getattr(pipeline, name, None)
    assert value is not None, f"niche_scout.pipeline.{name} is not implemented yet"
    return value


def _run_pipeline(**kwargs: Any) -> Any:
    """Call the Chunk 10 entry point through the resolver."""
    return _pipeline_symbol("run_pipeline")(**kwargs)

# ---------------------------------------------------------------------------
# Frozen constants used as golden expectations (read from models, not re-declared)
# ---------------------------------------------------------------------------

MIN_CATEGORIES_PER_RUN = models.MIN_CATEGORIES_PER_RUN
STRONG_REFERENCE_CATEGORY_COUNT = models.STRONG_REFERENCE_CATEGORY_COUNT
#: The interval lives in ``collector_graphql`` (the Chunk 5 adapter); the fixture
#: re-exports it as ``ENRICHMENT_INTERVAL_SECONDS`` so the test does not need a
#: second production import.
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = fx.ENRICHMENT_INTERVAL_SECONDS

EXPECTED_PROJECTED_MINIMUM_SECONDS = fx.EXPECTED_PROJECTED_MINIMUM_SECONDS
EXPECTED_PENDING_ENRICHMENT_IDENTITIES = fx.EXPECTED_PENDING_ENRICHMENT_IDENTITIES

#: The number of categories the eight-category scenario declares. It equals the
#: frozen ``MIN_CATEGORIES_PER_RUN`` (8), which SRS §14 marks non-configurable, so
#: the pipeline accepts the run without any threshold override.
SCENARIO_CATEGORY_COUNT = len(fx.END_TO_END_CATEGORIES)
#: The preflight is pinned to the first two eligible categories (two assets each),
#: so the scenario's attempted identities are exactly the fixture's hand-derived
#: three (``900``, ``901``, ``902``; ``900`` is shared and dedups).
SIX_CATEGORY_CONFIG: dict[str, Any] = {
    "identity_preflight_min_categories": 2,
    "identity_preflight_assets_per_category": 2,
}


@pytest.fixture(autouse=True)
def database_paths_stay_under_pytest_temp_base(tmp_path: Path) -> Iterator[Path]:
    """Assert every repository path lives under pytest's temp base."""
    temp_base = Path(tmp_path).resolve().parents[1]
    assert temp_base.is_dir()
    assert Path(tmp_path).resolve().is_relative_to(temp_base)
    yield tmp_path


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _config(
    tmp_path: Path,
    categories: Sequence[str],
    *,
    cap: int | None = None,
    **overrides: Any,
):
    """Write taxonomy/categories fixtures and return a config pointing at them."""
    fx.write_categories(tmp_path, categories)
    fx.write_taxonomy(tmp_path, fx.taxonomy_payload(categories))
    if cap is not None:
        overrides.setdefault("max_discovery_results_per_category", cap)
    return fx.fixture_config(tmp_path, **overrides)


def _run_end_to_end(
    tmp_path: Path,
    *,
    run_id: str = fx.END_TO_END_RUN_ID,
    cap: int = fx.SCENARIO_DISCOVERY_CAP,
    graphql_transport=None,
    coveo_transport=None,
    clock=None,
    on_call_capture: fx.LogCapture | None = None,
    config_overrides: dict[str, Any] | None = None,
    unreconciled_terminal: bool = False,
):
    """Run one full e2e pipeline against the in-memory scenario.

    Returns ``(result, scenario, stored)``; ``stored`` holds the read-back rows
    and the repository is closed before returning.
    """
    template_path = fx.write_run_local_template(tmp_path, fx.END_TO_END_CATEGORIES)
    scenario = fx.end_to_end_scenario(
        template_path=template_path, unreconciled_terminal=unreconciled_terminal
    )
    overrides = {**SIX_CATEGORY_CONFIG, **(config_overrides or {})}
    config = _config(tmp_path, scenario.categories, cap=cap, **overrides)
    fx.install_projection_observer(on_call_capture)
    try:
        repository = SqliteRepository(config.db_path)
        try:
            result = _run_pipeline(
                config=config,
                categories=scenario.categories,
                credentials=fx.fixture_credentials(),
                repository=repository,
                clock=clock if clock is not None else scenario.clock,
                coveo_transport=(
                    coveo_transport
                    if coveo_transport is not None
                    else scenario.coveo_transport
                ),
                graphql_transport=(
                    graphql_transport
                    if graphql_transport is not None
                    else scenario.graphql_transport
                ),
                sleeper=lambda _seconds: None,
                run_id=run_id,
                taxonomy_path=config.taxonomy_path,
                taxonomy_sha256=scenario.taxonomy_sha256,
                template_path=template_path,
            )
            stored = {
                "rows": repository.get_category_scores(result.run_id),
                "run": repository.get_run(result.run_id),
                "samples": {
                    category: repository.get_sample_members(result.run_id, category)
                    for category in scenario.categories
                },
                "observations": repository.count_distinct_enrichment_identities(
                    result.run_id
                ),
                "discovery_counts": repository.count_discovery_observations(
                    result.run_id
                ),
                "sample_count": repository.count_sample_members(result.run_id),
                "config": config,
            }
        finally:
            repository.close()
    finally:
        fx.install_projection_observer(None)
    return result, scenario, stored


def _identity_keys(run) -> tuple[str, ...]:
    return tuple(
        key for category in run.categories for key in category.population.identity_keys
    )


def _logs(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def _projection_messages(messages: Sequence[str]) -> list[str]:
    return [message for message in messages if "enrichment" in message.lower()]


def _logical_categories(run_row: Any) -> tuple[str, ...]:
    """Return the declared categories in ``categories_json``, or ``()``."""
    try:
        decoded = json.loads(run_row.categories_json)
    except (TypeError, ValueError):
        return ()
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) and item for item in decoded
    ):
        return ()
    return tuple(decoded)


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 — the full run and its determinism
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_pipeline_runs_completed_end_to_end(tmp_path: Path) -> None:
    """One complete run persists scores, status, cutoff, and a passing gate."""
    capture = fx.LogCapture()
    result, scenario, stored = _run_end_to_end(tmp_path, on_call_capture=capture)

    assert isinstance(result, _pipeline_symbol("PipelineResult"))
    assert result.succeeded is (result.status == RunStatus.COMPLETED.value)
    assert result.status == RunStatus.COMPLETED.value
    assert result.categories == scenario.categories
    assert result.category_scores_written == len(scenario.categories)
    assert stored["run"].status == RunStatus.COMPLETED.value
    assert stored["run"].completed_at_utc is not None
    assert result.scoring_cutoff_utc == stored["run"].scoring_cutoff_utc

    assert len(stored["rows"]) == len(scenario.categories)
    assert {row.category for row in stored["rows"]} == set(scenario.categories)
    assert all(row.computed_at_utc.tzinfo is not None for row in stored["rows"])
    assert _logical_categories(stored["run"]) == scenario.categories

    # LREQ-NFR-020: the transport hook asserted the projection at call time.
    assert capture.messages, "the enrichment projection log must have been emitted"


@pytest.mark.lreq("LREQ-ARCH-030")
def test_pipeline_is_deterministic_across_repeat_runs(tmp_path: Path) -> None:
    """Two identical runs differ only by run id.

    Byte identity would require a separately defined canonical serialization
    (SRS §3.3); structurally equal logical results are the requirement.
    """
    first, _scenario_a, stored_a = _run_end_to_end(tmp_path, run_id=fx.FIRST_RUN_ID)
    second, _scenario_b, stored_b = _run_end_to_end(tmp_path, run_id=fx.SECOND_RUN_ID)

    assert first.status == second.status
    assert first.scoring_cutoff_utc == second.scoring_cutoff_utc
    assert first.identity_preflight_status == second.identity_preflight_status
    assert first.category_scores_written == second.category_scores_written

    def logical(rows: Sequence[Any]) -> tuple[Any, ...]:
        return tuple(
            tuple(
                getattr(row, field_name)
                for field_name in row.__dataclass_fields__
                if field_name != "run_id"
            )
            for row in rows
        )

    assert logical(stored_a["rows"]) == logical(stored_b["rows"])


@pytest.mark.lreq("LREQ-ARCH-030")
def test_repeat_run_produces_structurally_equal_persisted_rows(
    tmp_path: Path,
) -> None:
    """Re-running the same scenario twice yields the same per-category values."""
    _first, _scenario, stored_a = _run_end_to_end(tmp_path, run_id="run-10-repeat-a")
    _second, _scenario_b, stored_b = _run_end_to_end(tmp_path, run_id="run-10-repeat-b")

    by_category_a = {row.category: row for row in stored_a["rows"]}
    by_category_b = {row.category: row for row in stored_b["rows"]}
    assert set(by_category_a) == set(by_category_b)

    for category, row_a in by_category_a.items():
        row_b = by_category_b[category]
        for field_name in (
            "discovery_status",
            "discovery_filter_verified",
            "discovered_population_count",
            "enriched_sample_count",
            "sample_is_census",
            "sampling_basis",
            "sample_fraction",
            "unique_enrichment_count",
            "overlap_category_count",
            "overlap_sample_percentage",
            "usable_demand_sample_count",
            "usable_recent_supply_sample_count",
            "usable_quality_sample_count",
            "breadth_source",
            "breadth_completeness_status",
            "discovery_bounded_by_verified_total",
            "reference_size",
            "evidence_grade",
            "rankability_status",
        ):
            assert getattr(row_a, field_name) == getattr(row_b, field_name), (
                f"{category}.{field_name} is not reproducible"
            )


# ---------------------------------------------------------------------------
# LREQ-ID-040 — preflight failure
# ---------------------------------------------------------------------------


def _fail_preflight_config(tmp_path: Path):
    """Write the scenario fixtures and return a config whose gate cannot pass.

    ``identity_preflight_min_success_rate=1.0`` (a config knob, SRS §14) with a
    zero-success rejection transport. Returns ``(scenario, config,
    template_path)`` so the caller replays the same run-local template.
    """
    template_path = fx.write_run_local_template(tmp_path, fx.END_TO_END_CATEGORIES)
    scenario = fx.end_to_end_scenario(template_path=template_path)
    fx.write_categories(tmp_path, scenario.categories)
    fx.write_taxonomy(tmp_path, scenario.taxonomy_payload)
    config = fx.fixture_config(
        tmp_path,
        min_categories_per_run=SCENARIO_CATEGORY_COUNT,
        max_discovery_results_per_category=fx.SCENARIO_DISCOVERY_CAP,
        identity_preflight_min_success_rate=1.0,
        identity_preflight_assets_per_category=1,
    )
    return scenario, config, template_path


def _run_with_failing_preflight(tmp_path: Path):
    """Run the scenario against a transport whose preflight cannot pass."""
    scenario, config, template_path = _fail_preflight_config(tmp_path)
    rejecting = fx.graphql_rejecting_transport(tuple(_identity_keys(scenario.run())))
    repository = SqliteRepository(config.db_path)
    try:
        result = _run_pipeline(
            config=config,
            categories=scenario.categories,
            credentials=fx.fixture_credentials(),
            repository=repository,
            clock=scenario.clock,
            coveo_transport=scenario.coveo_transport,
            graphql_transport=rejecting,
            sleeper=lambda _seconds: None,
            run_id=scenario.run_id,
            taxonomy_path=config.taxonomy_path,
            taxonomy_sha256=scenario.taxonomy_sha256,
            template_path=template_path,
        )
        stored = {
            "rows": repository.get_category_scores(result.run_id),
            "run": repository.get_run(result.run_id),
            "observations": repository.count_distinct_enrichment_identities(
                result.run_id
            ),
            "discovery_counts": repository.count_discovery_observations(result.run_id),
            "sample_count": repository.count_sample_members(result.run_id),
            "rejecting": rejecting,
        }
    finally:
        repository.close()
    return result, scenario, config, stored


@pytest.mark.lreq("LREQ-ID-040")
@pytest.mark.lreq("LREQ-NFR-030")
def test_failed_preflight_blocks_enrichment_and_marks_run_failed(
    tmp_path: Path,
) -> None:
    """A sub-threshold preflight stops bulk enrichment and fails the run.

    The rate is computed by the pipeline from the injected GraphQL responses:
    every preflight ``ProductDetail`` carries no usable payload, so the success
    rate is 0.0 under the 1.0 threshold (SRS §4.4).
    """
    result, _scenario, _config, stored = _run_with_failing_preflight(tmp_path)

    assert result.status == RunStatus.FAILED.value
    assert result.succeeded is False
    assert stored["run"].status == RunStatus.FAILED.value
    assert stored["run"].identity_preflight_status == (
        IdentityPreflightStatus.FAILED.value
    )


@pytest.mark.lreq("LREQ-ID-040")
def test_failed_preflight_issues_zero_enrichment_requests(tmp_path: Path) -> None:
    """Bulk enrichment issues zero requests when the gate is failed.

    The persisted summary is the pipeline's own attempt count, so equality with
    the transport's call count proves every request was a preflight attempt and
    that no bulk request followed the failed gate. The gate short-circuit policy
    (whether the loop stops once the rate is unreachable) is not pinned by the
    SRS, so the assertion is against the persisted count, not a literal.
    """
    result, _scenario, _config, stored = _run_with_failing_preflight(tmp_path)
    summary = json.loads(stored["run"].identity_preflight_summary_json)

    assert result.status == RunStatus.FAILED.value
    assert stored["discovery_counts"] == fx.EXPECTED_RAW_DISCOVERY_ROWS, (
        "raw discovery rows are retained, not rolled back"
    )
    assert summary["attempted_unique_identities"] >= 1
    assert len(stored["rejecting"].calls) == summary["attempted_unique_identities"], (
        "every GraphQL request was a preflight attempt; none followed the gate"
    )
    assert stored["observations"] == summary["attempted_unique_identities"], (
        "only the persisted preflight rows exist; no bulk observation was added"
    )


@pytest.mark.lreq("LREQ-ID-040")
@pytest.mark.lreq("LREQ-EVD-020")
def test_failed_preflight_retains_discovery_sample_and_preflight_rows(
    tmp_path: Path,
) -> None:
    """Discovery, sample, and preflight observations survive the failure."""
    result, _scenario, _config, stored = _run_with_failing_preflight(tmp_path)

    assert result.status == RunStatus.FAILED.value
    assert stored["run"].status == RunStatus.FAILED.value
    assert stored["discovery_counts"] == fx.EXPECTED_RAW_DISCOVERY_ROWS
    assert stored["sample_count"] == fx.EXPECTED_SAMPLE_MEMBER_ROWS
    summary = json.loads(stored["run"].identity_preflight_summary_json)
    assert set(summary) == set(fx.SUMMARY_JSON_KEY_SET)
    assert summary["attempted_unique_identities"] == len(stored["rejecting"].calls)
    assert summary["attempted_unique_identities"] >= 1
    assert summary["successful_unique_identities"] == 0
    assert summary["status"] == IdentityPreflightStatus.FAILED.value
    assert stored["observations"] == summary["attempted_unique_identities"], (
        "the persisted preflight error rows are retained and no bulk row was added"
    )


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-EXT-090")
def test_failed_preflight_persists_per_category_limitations(tmp_path: Path) -> None:
    """One null-score limitation row per requested category is persisted."""
    result, scenario, _config, stored = _run_with_failing_preflight(tmp_path)

    rows = {row.category: row for row in stored["rows"]}
    assert set(rows) == set(scenario.categories)
    assert result.category_scores_written == len(scenario.categories)

    for category, row in rows.items():
        assert row.market_opportunity_score is None, category
        assert row.evidence_grade == models.EvidenceGrade.INSUFFICIENT.value
        assert row.rankability_status == models.RankabilityStatus.NOT_RANKABLE.value
        assert row.missing_components_json == fx.GOLDEN_MISSING_COMPONENTS_ALL
        assert row.ranking_sensitivity_json
        json.loads(row.ranking_sensitivity_json)
        assert json.loads(row.warnings_json), (
            "explicit preflight warnings are persisted (plan §10 gate bullet)"
        )

    assert result.limitations
    for sentinel in scenario.observed_sentinels:
        for limitation in result.limitations:
            assert sentinel not in limitation


@pytest.mark.lreq("LREQ-ID-040")
def test_failed_preflight_does_not_complete_or_overwrite_failed(
    tmp_path: Path,
) -> None:
    """A failed run is never completed and its terminal timestamp stays null."""
    result, _scenario, _config, stored = _run_with_failing_preflight(tmp_path)

    assert result.status == RunStatus.FAILED.value
    assert stored["run"].status == RunStatus.FAILED.value
    assert stored["run"].completed_at_utc is None


@pytest.mark.lreq("LREQ-ID-040")
def test_insufficient_preflight_leaves_run_non_completed(tmp_path: Path) -> None:
    """Zero attempted preflight identities gives ``insufficient``, not completed.

    Every scenario category holds at most two sampled members, and
    ``identity_preflight_assets_per_category=3`` makes every one of them
    ineligible, so the selection is empty, both rates are null, and the gate is
    ``insufficient`` (SRS §4.4). This is a preflight evidence shortfall, not a
    zero-success result; the GraphQL transport is never called.
    """
    template_path = fx.write_run_local_template(tmp_path, fx.END_TO_END_CATEGORIES)
    scenario = fx.end_to_end_scenario(template_path=template_path)
    fx.write_categories(tmp_path, scenario.categories)
    fx.write_taxonomy(tmp_path, scenario.taxonomy_payload)
    config = fx.fixture_config(
        tmp_path,
        min_categories_per_run=SCENARIO_CATEGORY_COUNT,
        max_discovery_results_per_category=fx.SCENARIO_DISCOVERY_CAP,
        identity_preflight_min_success_rate=1.0,
        identity_preflight_assets_per_category=3,
    )
    repository = SqliteRepository(config.db_path)
    try:
        result = _run_pipeline(
            config=config,
            categories=scenario.categories,
            credentials=fx.fixture_credentials(),
            repository=repository,
            clock=scenario.clock,
            coveo_transport=scenario.coveo_transport,
            graphql_transport=scenario.graphql_transport,
            sleeper=lambda _seconds: None,
            run_id=scenario.run_id,
            taxonomy_path=config.taxonomy_path,
            taxonomy_sha256=scenario.taxonomy_sha256,
            template_path=template_path,
        )
        run_row = repository.get_run(result.run_id)
        summary = json.loads(run_row.identity_preflight_summary_json)
        observations = repository.count_distinct_enrichment_identities(result.run_id)
    finally:
        repository.close()

    assert run_row.identity_preflight_status == (
        IdentityPreflightStatus.INSUFFICIENT.value
    )
    assert run_row.status == RunStatus.FAILED.value
    assert result.status == RunStatus.FAILED.value
    assert summary["attempted_unique_identities"] == 0
    assert summary["success_rate"] is None
    assert summary["conflict_rate"] is None
    assert observations == 0


# ---------------------------------------------------------------------------
# LREQ-NFR-030 / LREQ-EXT-090 — failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-EXT-090")
def test_failed_category_does_not_abort_other_categories(tmp_path: Path) -> None:
    """A category-scoped discovery failure isolates to its own row.

    The truncated category's endpoint reports a verified ``totalCount`` of 2000
    while the run's read cap is ``fx.SCENARIO_DISCOVERY_CAP`` (3), so the frozen
    adapter's cap branch records ``truncated`` — a genuine category-scoped
    discovery condition (``LREQ-EXT-050``/``LREQ-EXT-090``) whose roll-up is
    ``DEGRADED``. With the default ``min_usable_samples_per_stratum`` (5) and
    two-member census samples, the pure Chunk 8/9A/9B chain makes that category
    ``NOT_RANKABLE`` (its required components are unavailable), never
    ``PROVISIONAL``/``RANKABLE``. The verified-total category's row is untouched
    and still carries its scores.
    """
    result, scenario, stored = _run_end_to_end(
        tmp_path,
        run_id="run-10-isolation",
        cap=fx.SCENARIO_DISCOVERY_CAP,
        config_overrides={
            "identity_preflight_min_categories": 1,
            "identity_preflight_assets_per_category": 1,
        },
    )
    rows = {row.category: row for row in stored["rows"]}

    removed = rows[scenario.removed_category]
    assert removed.discovery_status == DiscoveryStatus.TRUNCATED.value
    assert (
        _pipeline_symbol("category_status_for")(
            removed.discovery_status,
            warnings=json.loads(removed.warnings_json),
            evidence_grade=removed.evidence_grade,
            rankability_status=removed.rankability_status,
        )
        is models.CategoryStatus.DEGRADED
    )
    assert removed.evidence_grade == models.EvidenceGrade.INSUFFICIENT.value
    assert removed.rankability_status == models.RankabilityStatus.NOT_RANKABLE.value, (
        "a truncated 2-member census below the stratum minimum has no rankable "
        "competition result"
    )

    survivor = rows[fx.TRANSPORT_VERIFIED_TOTAL_CATEGORY]
    assert survivor.discovery_status == DiscoveryStatus.COMPLETE.value
    assert survivor.discovery_filter_verified is True
    assert result.category_scores_written == len(scenario.categories)


@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-EXT-090")
def test_failed_page_is_not_zero_assets(tmp_path: Path) -> None:
    """A failed discovery page never becomes a zero-breadth category.

    Every Coveo request fails with an HTTP error, so each sampled population is
    empty and each row's discovery status is a failure status, never
    ``complete`` with a zero count.
    """
    template_path = fx.write_run_local_template(tmp_path, fx.END_TO_END_CATEGORIES)
    scenario = fx.end_to_end_scenario(template_path=template_path)
    config = _config(
        tmp_path,
        scenario.categories,
        min_categories_per_run=SCENARIO_CATEGORY_COUNT,
    )
    repository = SqliteRepository(config.db_path)
    try:
        result = _run_pipeline(
            config=config,
            categories=scenario.categories,
            credentials=fx.fixture_credentials(),
            repository=repository,
            clock=scenario.clock,
            coveo_transport=fx.ErrorCoveoTransport(),
            graphql_transport=scenario.graphql_transport,
            sleeper=lambda _seconds: None,
            run_id="run-10-failed-page",
            taxonomy_path=config.taxonomy_path,
            taxonomy_sha256=scenario.taxonomy_sha256,
            template_path=template_path,
        )
        rows = repository.get_category_scores(result.run_id)
        sizes = {
            row.category: repository.count_raw_discovery_observations(
                result.run_id, row.category
            )
            for row in rows
        }
    finally:
        repository.close()

    assert rows
    for row in rows:
        assert row.discovery_status != DiscoveryStatus.COMPLETE.value
        assert sizes[row.category] == 0
        assert row.discovered_population_count == 0
        assert row.demand_per_asset_raw is None, (
            "a failed page must not be read as a zero-value metric"
        )


@pytest.mark.lreq("LREQ-NFR-030")
def test_failed_asset_does_not_abort_other_assets(tmp_path: Path) -> None:
    """One sampled asset's transport failure never aborts its neighbours.

    The transport raises for identity ``C1`` while serving every other identity;
    the run still completes and the sibling identities are requested (SRS §11
    ``LREQ-NFR-030``).
    """
    result, scenario, stored = _run_end_to_end(
        tmp_path,
        run_id="run-10-failed-asset",
        config_overrides={"identity_preflight_assets_per_category": 1},
    )

    requested = scenario.graphql_transport.distinct_requested_identities
    assert fx.failed_enrichment_identity() in requested, (
        "the failing identity was requested at least once"
    )
    assert "C2" in requested, "the sibling identity was still requested"
    assert len(set(requested)) == scenario.union_identity_count
    assert result.status == RunStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# LREQ-CLI-040 — run-size rejection
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-040")
def test_run_with_fewer_than_min_categories_is_rejected(tmp_path: Path) -> None:
    """Fewer than ``MIN_CATEGORIES_PER_RUN`` categories is rejected before ranking.

    ``MIN_CATEGORIES_PER_RUN`` is the frozen constant (8); the configured
    ``min_categories_per_run`` is never lowered here, so a two-category request
    is rejected. Rejection is a ``PipelineConfigurationError`` and Chunk 12 maps
    it to a non-zero exit.
    """
    categories = fx.category_set(fx.CATEGORY_COUNT_BELOW_MIN)
    config = _config(tmp_path, categories)
    assert config.min_categories_per_run == MIN_CATEGORIES_PER_RUN
    repository = SqliteRepository(config.db_path)
    try:
        with pytest.raises(_pipeline_symbol("PipelineConfigurationError")):
            _run_pipeline(
                config=config,
                categories=categories,
                credentials=fx.fixture_credentials(),
                repository=repository,
                clock=lambda: fx.FIXED_CLOCK_START,
                coveo_transport=fx.RecordingCoveoTransport({}),
                graphql_transport=fx.RecordingGraphQLTransport({}),
                sleeper=lambda _seconds: None,
                run_id="run-10-rejected",
                taxonomy_path=config.taxonomy_path,
                taxonomy_sha256=fx.taxonomy_sha256_for(
                    fx.taxonomy_payload(categories)
                ),
            )
        assert repository.get_run("run-10-rejected") is None, (
            "a rejected run persists nothing"
        )
    finally:
        repository.close()


# ---------------------------------------------------------------------------
# LREQ-EVD-020 / LREQ-SEN-020 — provisional run and reference size
# ---------------------------------------------------------------------------


def _presensitivity_inputs(count: int) -> tuple[Any, ...]:
    """Build ``count`` clean Chunk 9A inputs through the frozen fixture builder."""
    return tuple(make_pre_sensitivity_input(f"c-{index}") for index in range(count))


def _synthetic_metrics(count: int) -> tuple[Any, ...]:
    """Build ``count`` fully verified ``CategoryRawMetrics`` (ordering authority)."""
    return tuple(verified_metrics(f"c-{index}") for index in range(count))


@pytest.mark.lreq("LREQ-EVD-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_eight_category_run_has_empty_candidates_and_null_stability(
    tmp_path: Path,
) -> None:
    """An 8-category run is provisional with no candidates and null stability.

    The pure Chunk 9A/9B surfaces over a real 8-category sampling result: the
    dependency-map §6.2/§6.3 null contract gives an empty
    ``base_rankable_candidates`` and null ``top_3_stability`` /
    ``top_5_stability``, never ``0.0``.
    """
    records = {
        f"c-{index}": fx.population_records((f"k-{index}",))
        for index in range(fx.CATEGORY_COUNT_8)
    }
    run = sampling.select_run_sample(records, run_id="run-10-synthetic")
    metrics = _synthetic_metrics(fx.CATEGORY_COUNT_8)
    scores = tuple(
        scoring.score_category(
            metric,
            metrics,
            page_view_semantics_status=models.PageViewSemanticsStatus.UNVALIDATED,
        )
        for metric in metrics
    )
    candidates = scoring.build_base_rankable_candidates(
        metrics,
        _presensitivity_inputs(fx.CATEGORY_COUNT_8),
        scores,
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    sensitivity = scoring.evaluate_sensitivity(
        candidates,
        metrics,
        scores,
        reference_set_size=candidates.run_category_count - 1,
    )

    assert run.enrichment_identity_keys == tuple(
        f"k-{index}" for index in range(fx.CATEGORY_COUNT_8)
    )
    assert candidates.base_rankable_candidates == ()
    assert sensitivity.top_3_stability is None
    assert sensitivity.top_5_stability is None
    assert sensitivity.maximum_score_delta is None
    assert sensitivity.maximum_rank_displacement is None


@pytest.mark.lreq("LREQ-NRM-020")
def test_twenty_one_category_run_stores_reference_size_20(tmp_path: Path) -> None:
    """A 21-category run stores ``reference_size = 20``, never 21 peers.

    ``STRONG_REFERENCE_CATEGORY_COUNT = 21`` is a run-size threshold, not a peer
    count (SRS §8.1); the pure LOO reference for a 21-category run has 20 peers.
    """
    metrics = _synthetic_metrics(fx.CATEGORY_COUNT_21)
    target = metrics[0].category
    reference = scoring.leave_one_out_reference(metrics, target)

    assert reference.reference_size == fx.CATEGORY_COUNT_21 - 1 == 20
    assert reference.target_category == target
    assert all(
        len(values) <= reference.reference_size
        for values in (
            reference.demand_per_asset_raw,
            reference.demand_median_raw,
            reference.breadth_raw,
            reference.recent_share_raw,
            reference.median_age_raw,
            reference.quality_raw,
        )
    )
    assert fx.STRONG_REFERENCE == STRONG_REFERENCE_CATEGORY_COUNT


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 — cutoff captured once
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_scoring_cutoff_is_captured_once_and_threaded_to_pure_calls(
    tmp_path: Path,
) -> None:
    """The pipeline reads the injected clock and captures the cutoff once.

    The clock counts every call, so an extra post-enrichment read is visible;
    the captured value is the one persisted on the run row and returned on the
    result.
    """
    clock = fx.FixedClock()
    result, _scenario, stored = _run_end_to_end(
        tmp_path, run_id="run-10-cutoff", clock=clock
    )

    assert result.scoring_cutoff_utc is not None
    assert stored["run"].scoring_cutoff_utc == result.scoring_cutoff_utc
    assert result.scoring_cutoff_utc in clock.timestamps
    assert all(timestamp.tzinfo is not None for timestamp in clock.timestamps)
    assert result.status == RunStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# LREQ-NFR-020 — the pre-enrichment projection
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-020")
def test_enrichment_projection_is_logged_before_first_request(
    tmp_path: Path,
) -> None:
    """The projection is logged before the first bulk-enrichment request.

    The GraphQL transport's ``on_call`` hook asserts the log is already present
    when the first request is made, so a log emitted afterwards fails.
    """
    capture = fx.LogCapture()
    result, _scenario, _stored = _run_end_to_end(
        tmp_path, run_id="run-10-projection-order", on_call_capture=capture
    )

    assert result.status == RunStatus.COMPLETED.value
    assert any("enrichment" in message.lower() for message in capture.messages)


@pytest.mark.lreq("LREQ-NFR-020")
def test_projection_contains_required_counts_and_minimum_time(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The log carries the four SRS-named quantities and the minimum time.

    Expected minimum time, hand-derived from the plan §9 vector:
    ``pending_count * DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`` with
    ``pending_count = 10`` (the preflight attempts ``900``, ``901``, ``902``; the
    union of thirteen sampled identities leaves ``A1``, ``A2``, ``B1``, ``B2``,
    ``C1``, ``C2``, ``D1``, ``D2``, ``E1``, ``E2`` pending) and the production
    interval ``DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`` (0.5 s), so 5.0 s.
    """
    capture = fx.LogCapture()
    with caplog.at_level(logging.INFO):
        logging.getLogger().addHandler(capture)
        try:
            result, _scenario, _stored = _run_end_to_end(
                tmp_path, run_id="run-10-projection-values", on_call_capture=capture
            )
        finally:
            logging.getLogger().removeHandler(capture)

    assert result.status == RunStatus.COMPLETED.value
    projection = _projection_messages(capture.messages + _logs(caplog))
    assert projection, "an enrichment projection line must be logged"

    combined = "\n".join(projection)
    minimum = EXPECTED_PROJECTED_MINIMUM_SECONDS
    union_count = fx.EXPECTED_UNION_IDENTITY_COUNT
    assert f"discovered_canonical_assets={union_count}" in combined
    assert f"sampled_assets={union_count}" in combined
    assert f"unique_enrichment_identities={union_count}" in combined
    assert (
        f"reused_preflight_identities={fx.EXPECTED_PREFLIGHT_ATTEMPTS}" in combined
    )
    assert (
        f"pending_enrichment_identities={EXPECTED_PENDING_ENRICHMENT_IDENTITIES}"
        in combined
    )
    assert f"projected_minimum_enrichment_seconds={minimum}" in combined, (
        f"the projected minimum time {minimum} is logged "
        f"(pending {EXPECTED_PENDING_ENRICHMENT_IDENTITIES} * interval "
        f"{DEFAULT_MIN_REQUEST_INTERVAL_SECONDS})"
    )


@pytest.mark.lreq("LREQ-NFR-020")
def test_projection_log_contains_no_secret_or_identity(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No projection log line carries a credential, identity, or response body."""
    capture = fx.LogCapture()
    with caplog.at_level(logging.INFO):
        logging.getLogger().addHandler(capture)
        try:
            _run_end_to_end(
                tmp_path, run_id="run-10-projection-redaction", on_call_capture=capture
            )
        finally:
            logging.getLogger().removeHandler(capture)

    projection = _projection_messages(capture.messages + _logs(caplog))
    assert projection
    for message in projection:
        for sentinel in fx.RECORDED_SENTINELS:
            assert sentinel not in message
        for identity in ("900", "901", "902"):
            assert identity not in message, "no identity string belongs in the log line"


# ---------------------------------------------------------------------------
# LREQ-EXT-090 / LREQ-CLI-040 — no network before validation
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-040")
@pytest.mark.lreq("LREQ-EXT-090")
def test_invalid_configuration_causes_no_network_request(tmp_path: Path) -> None:
    """A configuration failure raises before any transport is touched."""
    categories = fx.category_set(fx.CATEGORY_COUNT_8)
    config = _config(tmp_path, categories)
    coveo = fx.RecordingCoveoTransport({})
    graphql = fx.RecordingGraphQLTransport({})
    repository = SqliteRepository(config.db_path)
    try:
        with pytest.raises(_pipeline_symbol("PipelineConfigurationError")):
            _run_pipeline(
                config=config,
                categories=categories,
                credentials=Credentials(coveo_token="", unity_csrf_token=""),
                repository=repository,
                clock=lambda: fx.FIXED_CLOCK_START,
                coveo_transport=coveo,
                graphql_transport=graphql,
                sleeper=lambda _seconds: None,
                run_id="run-10-invalid-config",
                taxonomy_path=config.taxonomy_path,
                taxonomy_sha256=fx.EXPECTED_TAXONOMY_SHA256,
            )
    finally:
        repository.close()

    assert coveo.call_count == 0
    assert graphql.call_count == 0


@pytest.mark.lreq("LREQ-EXT-090")
def test_invalid_taxonomy_causes_no_network_request(tmp_path: Path) -> None:
    """An invalid or stale taxonomy raises before any transport is touched."""
    categories = fx.category_set(fx.CATEGORY_COUNT_8)
    config = _config(tmp_path, categories)
    # Overwrite the taxonomy with a payload missing one requested category, so
    # validation rejects it (SRS §4.1 LREQ-EXT-020).
    fx.write_taxonomy(tmp_path, fx.taxonomy_payload(tuple(categories)[:-1]))
    coveo = fx.RecordingCoveoTransport({})
    graphql = fx.RecordingGraphQLTransport({})
    repository = SqliteRepository(config.db_path)
    try:
        with pytest.raises(_pipeline_symbol("TaxonomyInvalidError")):
            _run_pipeline(
                config=config,
                categories=categories,
                credentials=fx.fixture_credentials(),
                repository=repository,
                clock=lambda: fx.FIXED_CLOCK_START,
                coveo_transport=coveo,
                graphql_transport=graphql,
                sleeper=lambda _seconds: None,
                run_id="run-10-invalid-taxonomy",
                taxonomy_path=config.taxonomy_path,
                taxonomy_sha256=fx.EXPECTED_TAXONOMY_SHA256,
            )
    finally:
        repository.close()

    assert coveo.call_count == 0
    assert graphql.call_count == 0


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 — taxonomy provenance
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_taxonomy_sha256_is_non_empty_and_matches_golden(tmp_path: Path) -> None:
    """The run row's taxonomy hash is the non-empty golden digest (plan §5.4).

    The golden value is derived here from the fixture payload by the canonical
    JSON convention, never read off the implementation.
    """
    scenario = fx.end_to_end_scenario()
    payload = dict(scenario.taxonomy_payload)
    expected = fx.taxonomy_sha256_for(payload)
    _result, _scenario, stored = _run_end_to_end(tmp_path, run_id="run-10-hash")

    stored_hash = stored["run"].taxonomy_sha256
    assert stored_hash
    assert len(stored_hash) == 64
    assert stored_hash == stored_hash.lower()
    assert all(character in "0123456789abcdef" for character in stored_hash)
    assert stored_hash == expected
    assert _pipeline_symbol("taxonomy_sha256_for")(payload) == expected


@pytest.mark.lreq("LREQ-ARCH-030")
def test_run_record_seeds_required_not_null_columns(tmp_path: Path) -> None:
    """Every NOT NULL run column carries a real value at insert."""
    _result, scenario, stored = _run_end_to_end(tmp_path, run_id="run-10-not-null")
    run_row = stored["run"]
    assert run_row is not None
    assert run_row.taxonomy_sha256
    assert run_row.taxonomy_version
    assert run_row.endpoint_contract_version
    assert run_row.identity_mapping_rule_version
    assert run_row.sampling_rule_version
    assert run_row.identity_preflight_summary_json
    summary = json.loads(run_row.identity_preflight_summary_json)
    assert set(summary) == set(fx.SUMMARY_JSON_KEY_SET)
    assert run_row.config_sha256
    assert run_row.config_snapshot_json
    assert run_row.categories_json
    assert _logical_categories(run_row) == scenario.categories


# ---------------------------------------------------------------------------
# LREQ-SEN-020 / LREQ-EVD-020 — sensitivity is read-only
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-EVD-020")
def test_sensitivity_does_not_change_candidate_set_or_balanced_score(
    tmp_path: Path,
) -> None:
    """Sensitivity reports over the frozen candidate set and mutates nothing."""
    metrics = _synthetic_metrics(fx.CATEGORY_COUNT_21)
    scores = tuple(
        scoring.score_category(
            metric,
            metrics,
            page_view_semantics_status=models.PageViewSemanticsStatus.UNVALIDATED,
        )
        for metric in metrics
    )
    candidates = scoring.build_base_rankable_candidates(
        metrics,
        _presensitivity_inputs(fx.CATEGORY_COUNT_21),
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

    assert after == before, "the balanced score and components are immutable"
    assert sensitivity.ranked_categories == candidates.base_rankable_candidates, (
        "sensitivity ranks exactly the frozen candidate set, in its order"
    )
    assert set(sensitivity.ranked_categories) <= {metric.category for metric in metrics}


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-EVD-020")
def test_final_evidence_and_rankability_are_persisted_per_category(
    tmp_path: Path,
) -> None:
    """Every row carries a final evidence grade and rankability status.

    With ``min_usable_samples_per_stratum = 5`` and two-member census samples,
    every component coverage is 0.0, so every category of this below-21-category
    run is ``insufficient`` / ``not_rankable``: the filter-unverified category and
    the verified-total category alike. The node proves the Chunk 9B fields are
    persisted per category and are never a fabricated zero; it does not require a
    non-insufficient grade.
    """
    _result, scenario, stored = _run_end_to_end(tmp_path, run_id="run-10-final")
    rows = {row.category: row for row in stored["rows"]}
    grades = {grade.value for grade in models.EvidenceGrade}
    rankability = {status.value for status in models.RankabilityStatus}

    for category, row in rows.items():
        assert row.evidence_grade in grades, category
        assert row.rankability_status in rankability, category
        assert row.ranking_sensitivity_json
        json.loads(row.ranking_sensitivity_json)

    unverified = rows[fx.TRANSPORT_FAILED_CATEGORY]
    assert unverified.evidence_grade == models.EvidenceGrade.INSUFFICIENT.value
    assert unverified.rankability_status == models.RankabilityStatus.NOT_RANKABLE.value
    assert json.loads(unverified.warnings_json), (
        "an unverified filter generates a warning (SRS §4.1 LREQ-EXT-090)"
    )

    verified = rows[fx.TRANSPORT_VERIFIED_TOTAL_CATEGORY]
    assert verified.evidence_grade == models.EvidenceGrade.INSUFFICIENT.value
    assert verified.rankability_status == models.RankabilityStatus.NOT_RANKABLE.value
    assert verified.reference_size == len(scenario.categories) - 1


# ---------------------------------------------------------------------------
# LREQ-ID-040 — at most one enrichment per unique identity
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_shared_sampled_identity_is_enriched_once(tmp_path: Path) -> None:
    """A cross-category shared identity is requested at most once for enrichment.

    Identity ``900`` is planted in both the verified-total and the truncated
    categories; the preflight selects it once, so no later phase and no
    re-run of the same identity may ask for it again — the run-wide request
    count for ``900`` stays at one.
    """
    _result, scenario, stored = _run_end_to_end(
        tmp_path,
        run_id="run-10-shared",
        config_overrides={"identity_preflight_assets_per_category": 1},
    )

    requested = scenario.graphql_transport.requested_identities
    assert requested.count(fx.END_TO_END_SHARED_KEY) <= 1, (
        "the shared identity must be requested at most once run-wide"
    )
    sampled_keys = {
        record["asset_identity_key"]
        for category in scenario.records().values()
        for record in category
    }
    assert set(requested) <= sampled_keys | {fx.END_TO_END_SHARED_KEY}
    assert len(set(requested)) <= scenario.union_identity_count


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 — injected seams
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_run_uses_injected_clock_transports_and_sleeper(tmp_path: Path) -> None:
    """The run uses only the injected clock, transports, and sleeper.

    A sentinel monkeypatch makes a real socket connect fatal, so a live call
    would fail the node rather than pass silently.
    """
    monkeypatch = pytest.MonkeyPatch()

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the pipeline must not open a socket")

    monkeypatch.setattr(socket.socket, "connect", refuse, raising=False)
    try:
        result, scenario, _stored = _run_end_to_end(
            tmp_path, run_id="run-10-injected"
        )
    finally:
        monkeypatch.undo()

    assert result.status == RunStatus.COMPLETED.value
    assert scenario.coveo_transport.call_count > 0
    assert scenario.graphql_transport.call_count > 0


# ---------------------------------------------------------------------------
# Chunk 15 — failure-path limitation truthfulness and production logging.
#
# Source of truth: ``Documents/plans/chunk-15-failure-path-limitations-and-
# logging.md`` §9 (nodes 1-6) and §7 (the frozen log templates); the LREQ
# sections it cites: LREQ-EVD-020 (SRS §9.1), LREQ-ID-040 (§4.4),
# LREQ-NFR-020/LREQ-NFR-030 (§11), LREQ-SEC-020 (§4.3).
#
# The plan's §9 node 5 originally proposed an ``_ExplodingCoveoTransport`` whose
# ``send`` raises. That cannot reach ``pipeline._discover_all``'s ``except`` arm:
# the adapter calls ``transport.send`` inside ``discover_category``'s per-page
# ``try/except Exception`` (lead-verified against the source), which turns the
# raise into ``DiscoveryStatus.PAGE_FAILED``. The arm is exercised here by
# replacing the ``discover_category`` symbol ``pipeline`` imports as a module
# global (``pipeline.py:39``), which is the seam the frozen node ID and marker
# set still pin.
# ---------------------------------------------------------------------------


def _failure_path_config(tmp_path: Path):
    """Write the end-to-end fixtures and return the failing-gate run inputs.

    Mirrors ``test_insufficient_preflight_leaves_run_non_completed``: every
    category holds at most two sampled members and
    ``identity_preflight_assets_per_category = 3`` makes every one of them
    ineligible, so the selection is empty, both rates are null, and the gate is
    ``insufficient`` (SRS §4.4). Returns ``(scenario, config, template_path)``.
    """
    template_path = fx.write_run_local_template(tmp_path, fx.END_TO_END_CATEGORIES)
    scenario = fx.end_to_end_scenario(template_path=template_path)
    fx.write_categories(tmp_path, scenario.categories)
    fx.write_taxonomy(tmp_path, scenario.taxonomy_payload)
    config = fx.fixture_config(
        tmp_path,
        min_categories_per_run=SCENARIO_CATEGORY_COUNT,
        max_discovery_results_per_category=fx.SCENARIO_DISCOVERY_CAP,
        identity_preflight_assets_per_category=3,
        identity_preflight_min_success_rate=1.0,
    )
    return scenario, config, template_path


def _complete_coveo_transport() -> fx.RecordingCoveoTransport:
    """Return an all-``complete`` Coveo transport over the declared categories.

    Plan §9 node 2 recipe: one page per category with two agreeing-identity
    records and a verified ``totalCount``/``totalCountFiltered`` pair of two, so
    every persisted row's ``discovery_status`` is ``complete``.
    """
    return fx.RecordingCoveoTransport(
        {
            category: (
                fx.coveo_page(
                    [
                        fx.coveo_record(0, f"k{index}-a", category),
                        fx.coveo_record(1, f"k{index}-b", category),
                    ],
                    total_count=2,
                    filtered_count=2,
                ),
            )
            for index, category in enumerate(fx.END_TO_END_CATEGORIES)
        }
    )


def _run_failure_path(
    tmp_path: Path,
    *,
    run_id: str,
    coveo_transport: Any,
    graphql_transport: Any | None = None,
    discover_category: Any | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
):
    """Run the failing-gate scenario with an explicit injection seam.

    ``graphql_transport=None`` uses the scenario's transport (never called,
    because the empty preflight selection stops bulk enrichment before any
    request). When ``discover_category`` is given, the ``pipeline`` module global
    is replaced for the run and restored before returning, so no later node
    inherits it. Returns ``(result, scenario, config, rows)``; ``rows`` is the
    persisted ``category_scores`` read-back taken before the repository closes.
    """
    scenario, config, template_path = _failure_path_config(tmp_path)
    restore = None
    if discover_category is not None:
        assert monkeypatch is not None, (
            "a discover_category replacement needs a monkeypatch"
        )
        restore = _pipeline_symbol("discover_category")
        monkeypatch.setattr(pipeline, "discover_category", discover_category)
    repository = SqliteRepository(config.db_path)
    try:
        result = _run_pipeline(
            config=config,
            categories=scenario.categories,
            credentials=fx.fixture_credentials(),
            repository=repository,
            clock=scenario.clock,
            coveo_transport=coveo_transport,
            graphql_transport=(
                graphql_transport
                if graphql_transport is not None
                else scenario.graphql_transport
            ),
            sleeper=lambda _seconds: None,
            run_id=run_id,
            taxonomy_path=config.taxonomy_path,
            taxonomy_sha256=scenario.taxonomy_sha256,
            template_path=template_path,
        )
        rows = repository.get_category_scores(result.run_id)
    finally:
        if restore is not None:
            monkeypatch.setattr(pipeline, "discover_category", restore)
        repository.close()
    return result, scenario, config, rows


@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-EVD-020")
def test_failure_path_limitations_use_discovery_status_when_rollup_is_failed(
    tmp_path: Path,
) -> None:
    """A discovery-failed category is named by ``discovery_status``.

    Golden (hand-derived, plan §9 node 1 from the ``interfaces/chunk-10.md`` §5
    roll-up rule): ``request_failed`` is ``CategoryStatus.FAILED``, so R1 appends
    ``f"category {category!r}: discovery_status"`` for every requested category
    and never the run-level ``identity_preflight_status`` field. Every category
    is ``request_failed`` because ``ErrorCoveoTransport`` answers each discovery
    request with HTTP 500 (SRS §4.1), and the empty preflight selection leaves
    the gate ``insufficient`` (SRS §4.4): two independent failure kinds, one
    limitation field each (SRS §9.1 ``LREQ-EVD-020``).
    """
    result, scenario, _config, _rows = _run_failure_path(
        tmp_path,
        run_id="run-15-discovery-limitations",
        coveo_transport=fx.ErrorCoveoTransport(),
    )

    assert result.status == RunStatus.FAILED.value
    assert result.identity_preflight_status == (
        IdentityPreflightStatus.INSUFFICIENT.value
    )
    assert result.limitations == tuple(
        f"category {category!r}: discovery_status"
        for category in fx.END_TO_END_CATEGORIES
    )
    for limitation in result.limitations:
        assert "identity_preflight_status" not in limitation
    assert len(result.limitations) == len(scenario.categories), (
        "one limitation per requested category; no run-level string"
    )


@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-ID-040")
def test_failure_path_limitations_use_identity_preflight_status_when_discovery_healthy(
    tmp_path: Path,
) -> None:
    """A healthy category on a failed run is named by the preflight field.

    Golden (hand-derived, plan §9 node 2): the all-complete transport makes every
    persisted row ``DiscoveryStatus.COMPLETE.value``, so ``category_status_for``
    is ``HEALTHY`` and R1's ``elif`` fires for every requested category; the
    empty preflight selection leaves the gate ``insufficient`` (SRS §4.4), so
    every limitation is ``f"category {category!r}: identity_preflight_status"``.
    """
    result, _scenario, _config, rows = _run_failure_path(
        tmp_path,
        run_id="run-15-preflight-limitations",
        coveo_transport=_complete_coveo_transport(),
    )

    assert result.status == RunStatus.FAILED.value
    assert result.identity_preflight_status == (
        IdentityPreflightStatus.INSUFFICIENT.value
    )
    assert rows, "the failure path persists one row per requested category"
    for row in rows:
        assert row.discovery_status == DiscoveryStatus.COMPLETE.value, row.category
    assert result.limitations == tuple(
        f"category {category!r}: identity_preflight_status"
        for category in fx.END_TO_END_CATEGORIES
    )


@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-SEC-020")
def test_failure_path_limitation_strings_name_category_and_field_only(
    tmp_path: Path,
) -> None:
    """Every limitation is ``category <repr>: <field>`` and carries no value.

    The format is frozen by ``interfaces/chunk-10.md`` §4 and the field set by
    plan §8; the fixture identities (including the ``k<index>-<letter>`` records
    of the sibling all-complete transport) and every recorded sentinel must be
    absent (SRS §4.3 ``LREQ-SEC-020``).
    """
    result, scenario, _config, _rows = _run_failure_path(
        tmp_path,
        run_id="run-15-limitation-format",
        coveo_transport=fx.ErrorCoveoTransport(),
    )
    fixture_identities = ("k0-a", "900", "901", "902")

    assert result.limitations
    assert len(result.limitations) == len(scenario.categories)
    for limitation in result.limitations:
        assert re.fullmatch(
            r"category .+: (discovery_status|identity_preflight_status)", limitation
        ), limitation
        assert any(
            f"category {category!r}: " in limitation
            for category in fx.END_TO_END_CATEGORIES
        ), limitation
        for sentinel in fx.RECORDED_SENTINELS:
            assert sentinel not in limitation
        for identity in fixture_identities:
            assert identity not in limitation


@pytest.mark.lreq("LREQ-NFR-030")
def test_discovery_outcome_log_line_is_emitted_on_pipeline_logger(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """One per-category discovery outcome line reaches the pipeline logger.

    Plan §7 E2 template: category, terminal discovery status, ordered condition
    codes, and issue codes only. A failed discovery rolls up to ``FAILED``, so
    the record is a WARNING. No message contains ``"enrichment"`` (the
    LREQ-NFR-020 projection filter keeps its scope) or a recorded sentinel. The
    condition/issue token lists are discovery-internal and are asserted as
    present, not by exact value.
    """
    with caplog.at_level(logging.INFO, logger="niche_scout.pipeline"):
        result, _scenario, _config, _rows = _run_failure_path(
            tmp_path,
            run_id="run-15-discovery-outcome",
            coveo_transport=fx.ErrorCoveoTransport(),
        )
    messages = _logs(caplog)
    prefix = f"category {fx.END_TO_END_CATEGORIES[0]}: discovery "
    outcome = [
        record
        for record in caplog.records
        if record.name == "niche_scout.pipeline"
        and record.getMessage().startswith(prefix)
    ]

    assert outcome, f"no discovery outcome line for {prefix!r}"
    assert all(record.levelno == logging.WARNING for record in outcome)
    assert any("conditions=[" in record.getMessage() for record in outcome)
    assert any("issues=[" in record.getMessage() for record in outcome)
    assert result.status == RunStatus.FAILED.value
    for message in messages:
        assert "enrichment" not in message.lower()
        for sentinel in fx.RECORDED_SENTINELS:
            assert sentinel not in message


@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-SEC-020")
def test_discovery_failure_log_omits_exception_message_and_sentinels(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A discovery-request exception logs its class name only, never its message.

    The ``discover_category`` symbol ``pipeline._discover_all`` calls is replaced
    by a raiser (a raising transport ``send`` is caught inside the adapter's
    per-page ``try`` and becomes ``PAGE_FAILED``, so a transport cannot reach
    this ``except`` arm). The warning is exactly
    ``f"category {category}: discovery request failed (RuntimeError)"`` for every
    requested category, and the raising message — a recorded sentinel — appears
    in no record (SRS §4.3 ``LREQ-SEC-020``). The run still fails gracefully with
    every category isolated (SRS §11 ``LREQ-NFR-030``).
    """

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(fx.RECORDED_SENTINELS[4])

    with caplog.at_level(logging.INFO, logger="niche_scout.pipeline"):
        result, scenario, _config, _rows = _run_failure_path(
            tmp_path,
            run_id="run-15-discovery-request-failed",
            coveo_transport=fx.RecordingCoveoTransport({}),
            graphql_transport=fx.RecordingGraphQLTransport({}),
            discover_category=boom,
            monkeypatch=monkeypatch,
        )
    messages = _logs(caplog)

    for category in scenario.categories:
        expected = f"category {category}: discovery request failed (RuntimeError)"
        matching = [
            record for record in caplog.records if record.getMessage() == expected
        ]
        assert matching, expected
        assert matching[0].levelno == logging.WARNING
        assert matching[0].name == "niche_scout.pipeline"
    assert all(fx.RECORDED_SENTINELS[4] not in message for message in messages)
    assert result.status == RunStatus.FAILED.value


@pytest.mark.lreq("LREQ-ID-040")
@pytest.mark.lreq("LREQ-NFR-030")
def test_run_level_preflight_and_run_status_lines_are_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """One run-level preflight line and one run-status line are emitted.

    Hand-derived from plan §7 E5/E6 and SRS §4.4 (``attempted = 0`` ⇒ both rates
    null, status ``insufficient``): the preflight line is exactly
    ``identity preflight: status=insufficient attempted=0 successful=0
    conflicting=0 other_failed=0`` and the failure path logs
    ``f"run {run_id}: failed"``. No identity or sentinel appears.
    """
    run_id = "run-15-run-lines"
    with caplog.at_level(logging.INFO, logger="niche_scout.pipeline"):
        result, _scenario, _config, _rows = _run_failure_path(
            tmp_path,
            run_id=run_id,
            coveo_transport=_complete_coveo_transport(),
        )
    messages = _logs(caplog)

    assert result.status == RunStatus.FAILED.value
    assert (
        "identity preflight: status=insufficient attempted=0 successful=0 "
        "conflicting=0 other_failed=0"
    ) in messages
    assert f"run {run_id}: failed" in messages
    for message in messages:
        for identity in ("k0-a", "k1-a"):
            assert identity not in message
        for sentinel in fx.RECORDED_SENTINELS:
            assert sentinel not in message


# ---------------------------------------------------------------------------
# Chunk 28 / LREQ-MET-040 — the run-level page-view semantics token
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-MET-040")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_run_seeds_validated_windowed_weekly_semantics(tmp_path: Path) -> None:
    """A new run row records the validated trailing-7-day semantics (D1-S3).

    ``run_pipeline`` seeds ``PAGE_VIEW_SEMANTICS_CONTRACT``; with the extended
    preflight non-clobber guard the completed run still reads the new token.
    """
    _result, _scenario, stored = _run_end_to_end(tmp_path)

    assert stored["run"].page_view_semantics_status == "validated_windowed_weekly"


@pytest.mark.lreq("LREQ-MET-040")
@pytest.mark.lreq("LREQ-SCR-050")
def test_preflight_preserves_validated_windowed_weekly_status(tmp_path: Path) -> None:
    """A run pre-seeded with the new token is not clobbered back to unvalidated.

    Mirrors the ``tests/test_identity_preflight.py`` non-clobber nodes with the
    chunk-28 token: the guard must preserve ``validated_windowed_weekly``
    exactly as it preserves ``validated_cumulative``/``contradicted``.
    """
    run = pf.two_asset_run()
    repository = SqliteRepository(tmp_path / "chunk28-non-clobber.sqlite3")
    try:
        pf.seed_sampling_and_run(
            repository,
            run,
            page_view_semantics_status="validated_windowed_weekly",
        )
        pipeline.run_identity_preflight(
            repository,
            run,
            credentials=pf.GQL_CREDENTIALS,
            transport=pf.success_transport((pf.A, pf.B)),
            correlation_mode=pf.EXPLICIT_KEY,
            retrieved_at_utc=pf.RETRIEVED_AT_UTC,
            policy=pf.small_policy(),
        )
        assert (
            pf.page_view_semantics_of(repository, run.run_id)
            == "validated_windowed_weekly"
        )
    finally:
        repository.close()


# ---------------------------------------------------------------------------
# Chunk 29 — the unreconciled-terminal variant (LREQ-EXT-050 / LREQ-EXT-090 /
# LREQ-MET-070)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-050")
@pytest.mark.lreq("LREQ-EXT-090")
def test_unreconciled_total_emits_discovery_incomplete_distinct_from_truncated(
    tmp_path: Path,
) -> None:
    """The unreconciled variant emits ``DISCOVERY_INCOMPLETE`` beside truncated.

    The variant scenario (``unreconciled_terminal=True``) ends the truncated
    category's traversal on an **empty** page while the verified total stays
    2000: persisted = 2, recorded shortfall = 1998 (SRS §4.1 LREQ-EXT-050
    addendum, Lean 1.0.5). Appendix C lists ``DISCOVERY_INCOMPLETE`` and
    ``DISCOVERY_TRUNCATED`` as separate codes, so the persisted row carries
    both, deduplicated and distinct.
    """
    _result, _scenario, stored = _run_end_to_end(
        tmp_path, run_id="run-29-unreconciled-warning", unreconciled_terminal=True
    )
    rows = {row.category: row for row in stored["rows"]}
    row = rows[fx.TRANSPORT_TRUNCATED_CATEGORY]

    assert row.discovery_status == DiscoveryStatus.TRUNCATED.value
    codes = json.loads(row.warnings_json)
    assert "DISCOVERY_INCOMPLETE" in codes
    assert "DISCOVERY_TRUNCATED" in codes
    assert "DISCOVERY_INCOMPLETE" != "DISCOVERY_TRUNCATED"
    assert codes.count("DISCOVERY_INCOMPLETE") == 1
    assert codes.count("DISCOVERY_TRUNCATED") == 1

    # Control: the healthy category of the same run is still complete.
    healthy = rows[fx.TRANSPORT_VERIFIED_TOTAL_CATEGORY]
    assert healthy.discovery_status == DiscoveryStatus.COMPLETE.value


@pytest.mark.lreq("LREQ-MET-070")
@pytest.mark.lreq("LREQ-EXT-050")
def test_unreconciled_total_falls_back_to_incomplete_breadth_and_is_not_rankable(
    tmp_path: Path,
) -> None:
    """The shortfall row takes the fallback breadth chain and is not rankable.

    SRS §7.3 LREQ-MET-070: the unreconciled verified total is not usable, so
    ``BreadthRaw`` is the distinct canonical discovered count (900, 902 -> 2),
    ``breadth_source`` is ``distinct_canonical_discovered_count``, and
    ``breadth_completeness_status`` is ``incomplete_estimate``. ``C`` requires
    verified+complete breadth (SRS §8.2 LREQ-SCR-020) and is therefore
    unavailable, and the category is not rankable (LREQ-EVD-020/030).
    """
    _result, _scenario, stored = _run_end_to_end(
        tmp_path, run_id="run-29-unreconciled-breadth", unreconciled_terminal=True
    )
    rows = {row.category: row for row in stored["rows"]}
    row = rows[fx.TRANSPORT_TRUNCATED_CATEGORY]

    assert row.discovery_status == DiscoveryStatus.TRUNCATED.value
    assert row.breadth_source == (
        models.BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT.value
    )
    assert row.breadth_completeness_status == (
        models.BreadthCompletenessStatus.INCOMPLETE_ESTIMATE.value
    )
    assert row.breadth_raw == fx.UNRECONCILED_PERSISTED_ROWS
    assert row.component_c is None
    assert "C" in json.loads(row.missing_components_json)
    assert row.rankability_status == models.RankabilityStatus.NOT_RANKABLE.value
    assert row.evidence_grade == models.EvidenceGrade.INSUFFICIENT.value


@pytest.mark.lreq("LREQ-EXT-050")
def test_cap_truncated_category_warning_excludes_discovery_incomplete(
    tmp_path: Path,
) -> None:
    """Cap truncation is ``DISCOVERY_TRUNCATED`` only, never incomplete.

    The default scenario's truncated category is stopped by the read cap
    (``SCENARIO_DISCOVERY_CAP``) and its records reconcile with no recorded
    shortfall amount, so the Lean 1.0.5 ``DISCOVERY_INCOMPLETE`` code must not
    appear (SRS Appendix C; SRS §4.1 LREQ-EXT-050 addendum). This is the
    negative of the unreconciled-terminal variant's positive case.
    """
    _result, _scenario, stored = _run_end_to_end(tmp_path, run_id="run-29-cap-warning")
    rows = {row.category: row for row in stored["rows"]}
    row = rows[fx.TRANSPORT_TRUNCATED_CATEGORY]

    assert row.discovery_status == DiscoveryStatus.TRUNCATED.value
    codes = json.loads(row.warnings_json)
    assert "DISCOVERY_TRUNCATED" in codes
    assert "DISCOVERY_INCOMPLETE" not in codes
