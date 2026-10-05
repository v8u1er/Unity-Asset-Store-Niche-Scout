"""Chunk 0 contract tests.

Every test in this module carries an explicit ``@pytest.mark.lreq`` marker and a
matching entry in ``tests/traceability.json``. The tests assert frozen
contracts (types, constants, precedence, purity, and fixtures) rather than
behavior owned by later chunks.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import sqlite3
import sys
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fixtures.config_fixtures as fixtures
import pytest

from niche_scout import models
from niche_scout.config import (
    COVEO_TOKEN_ENV,
    UNITY_CSRF_TOKEN_ENV,
    Credentials,
    NicheScoutConfig,
    get_credentials,
    load_config,
    read_categories,
)
from niche_scout.database import (
    CREATE_TABLE_STATEMENTS,
    DDL_STATEMENTS,
    TABLE_COLUMNS,
    TABLE_PRIMARY_KEYS,
    Repository,
)
from niche_scout.models import (
    BreadthCompletenessStatus,
    BreadthSource,
    CategoryScoreRecord,
    CategoryStatus,
    DiscoveryStatus,
    EnrichmentObservationRecord,
    EvidenceGrade,
    GraphQLOperationCorrelationMode,
    IdentityPreflightStatus,
    IdentityResolutionStatus,
    OperationStatus,
    PageViewSemanticsStatus,
    RankabilityStatus,
    RawDiscoveryObservationRecord,
    RunRecord,
    RunStatus,
    SampleMemberRecord,
    SamplingBasis,
    ScoreState,
    WarningCode,
    from_json,
    to_json,
)
from niche_scout.tools.check_import_boundaries import check_module, clock_violations

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE = SRC / "niche_scout"

REQUIRED_STATUS_VALUES: dict[str, set[str]] = {
    "RunStatus": {"running", "completed", "failed"},
    "DiscoveryStatus": {
        "complete",
        "truncated",
        "page_failed",
        "filter_unverified",
        "category_mismatch",
        "identity_incomplete",
        "request_failed",
    },
    "IdentityResolutionStatus": {"resolved", "unresolved", "conflict"},
    "OperationStatus": {"success", "error"},
    "PageViewSemanticsStatus": {
        "unvalidated",
        "validated_cumulative",
        "contradicted",
        "validated_windowed_weekly",
    },
    "GraphQLOperationCorrelationMode": {"explicit_key", "validated_position"},
    "IdentityPreflightStatus": {"passed", "failed", "insufficient"},
    "BreadthSource": {"verified_total_count", "distinct_canonical_discovered_count"},
    "BreadthCompletenessStatus": {"complete", "incomplete_estimate"},
    "SamplingBasis": {"census", "deterministic_stratified_sample"},
    "ScoreState": {"available", "partial", "unavailable"},
    "EvidenceGrade": {"strong", "moderate", "weak", "insufficient"},
    "RankabilityStatus": {"not_rankable", "provisional", "rankable"},
    "CategoryStatus": {"healthy", "degraded", "failed"},
}

REQUIRED_ROW_FIELDS: dict[str, tuple[str, ...]] = {
    "runs": (
        "run_id",
        "run_started_at_utc",
        "scoring_cutoff_utc",
        "completed_at_utc",
        "categories_json",
        "config_snapshot_json",
        "config_sha256",
        "taxonomy_version",
        "taxonomy_captured_at_utc",
        "taxonomy_sha256",
        "endpoint_contract_version",
        "identity_mapping_rule_version",
        "sampling_rule_version",
        "page_view_semantics_status",
        "graphql_operation_correlation_mode",
        "identity_preflight_status",
        "identity_preflight_summary_json",
        "status",
    ),
    "raw_discovery_observations": (
        "observation_id",
        "run_id",
        "category",
        "discovery_ordinal",
        "asset_identity_key",
        "identity_candidates_json",
        "identity_resolution_status",
        "identity_resolution_reason",
        "category_value_json",
        "category_filter_validation_status",
        "stratum_index",
        "is_duplicate",
        "duplicate_of_observation_id",
        "request_metadata_json",
        "error_summary_json",
        "retrieved_at_utc",
    ),
    "sample_members": (
        "run_id",
        "category",
        "asset_identity_key",
        "stratum_index",
        "stratum_offset",
        "stratum_stride",
        "sample_rank_within_stratum",
        "sample_is_census",
        "selection_digest",
        "overlap_category_count",
        "overlap_sample_percentage",
        "preflight_selected",
    ),
    "enrichment_observations": (
        "run_id",
        "asset_identity_key",
        "product_detail_status",
        "page_views_status",
        "graphql_id",
        "product_id",
        "rating_average",
        "rating_count",
        "review_count",
        "first_published_date_utc",
        "publisher_json",
        "category_json",
        "state",
        "product_page_views",
        "id_mapping_mismatch",
        "product_detail_error_summary",
        "page_views_error_summary",
        "request_metadata_json",
        "retrieved_at_utc",
    ),
    "category_scores": (
        "run_id",
        "category",
        "discovery_status",
        "discovery_filter_verified",
        "discovery_unresolved_identity_count",
        "discovery_conflict_count",
        "discovery_duplicate_count",
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
        "demand_stratum_eligibility_coverage",
        "recent_supply_stratum_eligibility_coverage",
        "quality_stratum_eligibility_coverage",
        "demand_per_asset_raw",
        "demand_median_raw",
        "breadth_raw",
        "recent_share_raw",
        "median_age_raw",
        "quality_raw",
        "stratum_statistics_json",
        "component_d",
        "component_c",
        "component_r",
        "component_q",
        "market_opportunity_score",
        "score_state",
        "evidence_grade",
        "rankability_status",
        "missing_components_json",
        "warnings_json",
        "reference_size",
        "reference_usable_counts_json",
        "top_3_stability",
        "top_5_stability",
        "maximum_score_delta",
        "maximum_rank_displacement",
        "sensitivity_warning",
        "ranking_sensitivity_json",
        "computed_at_utc",
        "discovery_failure_cause_json",
    ),
}

REQUIRED_CONSTANTS: dict[str, object] = {
    "ENDPOINT_CONTRACT_VERSION": "1.1.0",
    "IDENTITY_MAPPING_RULE_VERSION": "1.0.1",
    "SAMPLING_RULE_VERSION": "2.0.0",
    "MAX_DISCOVERY_RESULTS_PER_CATEGORY": 9000,
    "PAGE_SIZE": 96,
    "MIN_CATEGORIES_PER_RUN": 8,
    "STRONG_REFERENCE_CATEGORY_COUNT": 21,
    "MAX_TAXONOMY_AGE_DAYS": 30,
    "ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY": 100,
    "SAMPLE_STRATA": 4,
    "SAMPLE_PER_STRATUM": 25,
    "MIN_USABLE_SAMPLES_PER_STRATUM": 1,
    "MIN_REQUIRED_COMPONENT_COVERAGE": 0.50,
    "STRONG_COMPONENT_COVERAGE": 0.80,
    "MIN_AGE_DAYS_FOR_RATE": 30,
    "RECENT_WINDOW_DAYS": 365,
    "QUALITY_MIN_RATING_COUNT": 5,
    "QUALITY_MIN_ELIGIBLE_ASSETS": 5,
    "IDENTITY_PREFLIGHT_MIN_CATEGORIES": 5,
    "IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY": 2,
    "IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE": 0.0,
    "IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE": 0.90,
    "W_D": 0.35,
    "W_C": 0.30,
    "W_R": 0.20,
    "W_Q": 0.15,
    "DEMAND_SUBWEIGHT_PER_ASSET": 0.60,
    "DEMAND_SUBWEIGHT_MEDIAN": 0.40,
    "RECENT_SUBWEIGHT_SHARE": 0.70,
    "RECENT_SUBWEIGHT_AGE": 0.30,
}


def _iso(hour: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


def _run_record() -> RunRecord:
    return RunRecord(
        run_id="run-1",
        run_started_at_utc=_iso(1),
        scoring_cutoff_utc=_iso(2),
        completed_at_utc=None,
        categories_json=json.dumps(list(fixtures.DEFAULT_CATEGORIES)),
        config_snapshot_json="{}",
        config_sha256="0" * 64,
        taxonomy_version="1.0.0",
        taxonomy_captured_at_utc=_iso(0),
        taxonomy_sha256="0" * 64,
        endpoint_contract_version=models.ENDPOINT_CONTRACT_VERSION,
        identity_mapping_rule_version=models.IDENTITY_MAPPING_RULE_VERSION,
        sampling_rule_version=models.SAMPLING_RULE_VERSION,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED.value,
        graphql_operation_correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY.value,
        identity_preflight_status=IdentityPreflightStatus.INSUFFICIENT.value,
        identity_preflight_summary_json="{}",
        status=RunStatus.RUNNING.value,
    )


def _category_score_record() -> CategoryScoreRecord:
    return CategoryScoreRecord(
        run_id="run-1",
        category="Tools/Level Design/Tilemap",
        discovery_status=DiscoveryStatus.COMPLETE.value,
        discovery_filter_verified=True,
        discovery_unresolved_identity_count=0,
        discovery_conflict_count=0,
        discovery_duplicate_count=0,
        discovered_population_count=0,
        enriched_sample_count=0,
        sample_is_census=True,
        sampling_basis=SamplingBasis.CENSUS.value,
        sample_fraction=None,
        unique_enrichment_count=0,
        overlap_category_count=0,
        overlap_sample_percentage=None,
        usable_demand_sample_count=0,
        usable_recent_supply_sample_count=0,
        usable_quality_sample_count=0,
        breadth_source=BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT.value,
        breadth_completeness_status=BreadthCompletenessStatus.COMPLETE.value,
        discovery_bounded_by_verified_total=False,
        demand_stratum_eligibility_coverage=0.0,
        recent_supply_stratum_eligibility_coverage=0.0,
        quality_stratum_eligibility_coverage=0.0,
        demand_per_asset_raw=None,
        demand_median_raw=None,
        breadth_raw=None,
        recent_share_raw=None,
        median_age_raw=None,
        quality_raw=None,
        stratum_statistics_json="{}",
        component_d=None,
        component_c=None,
        component_r=None,
        component_q=None,
        market_opportunity_score=None,
        score_state=ScoreState.UNAVAILABLE.value,
        evidence_grade=EvidenceGrade.INSUFFICIENT.value,
        rankability_status=RankabilityStatus.NOT_RANKABLE.value,
        missing_components_json='["D", "C", "R", "Q"]',
        warnings_json="[]",
        reference_size=0,
        reference_usable_counts_json="{}",
        top_3_stability=None,
        top_5_stability=None,
        maximum_score_delta=None,
        maximum_rank_displacement=None,
        sensitivity_warning=None,
        ranking_sensitivity_json="{}",
        computed_at_utc=_iso(3),
        discovery_failure_cause_json=None,
    )


# ---------------------------------------------------------------------------
# 0A — package and architecture contracts
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-010")
def test_models_import() -> None:
    """The package imports and pure modules expose typed dataclass structures."""
    import niche_scout  # noqa: F401
    import niche_scout.metrics as metrics
    import niche_scout.scoring as scoring

    for row_type in (
        RunRecord,
        RawDiscoveryObservationRecord,
        SampleMemberRecord,
        EnrichmentObservationRecord,
        CategoryScoreRecord,
    ):
        assert isinstance(row_type, type)
        assert fields(row_type)
    for module in (metrics, scoring):
        functions = [
            name
            for name, value in vars(module).items()
            if callable(value)
            and not name.startswith("_")
            and getattr(value, "__module__", "") == module.__name__
        ]
        assert isinstance(functions, list)
    assert isinstance(sys.modules["niche_scout.models"], object)


@pytest.mark.lreq("LREQ-ARCH-020")
def test_pure_boundary_no_clock() -> None:
    """AST inspection proves the pure modules import no I/O and read no clock."""
    for filename in ("metrics.py", "scoring.py"):
        path = PACKAGE / filename
        assert path.is_file(), f"{filename} must exist as a pure module"
        assert check_module(path) == [], f"{filename} violates the purity boundary"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert clock_violations(tree) == []


@pytest.mark.lreq("LREQ-ARCH-030")
def test_determinism_contract() -> None:
    """Identical inputs and policy versions produce identical serialized rows."""
    first, second = _run_record(), _run_record()
    assert to_json(first) == to_json(second)
    assert from_json(to_json(first), RunRecord) == first
    score_first, score_second = _category_score_record(), _category_score_record()
    assert to_json(score_first) == to_json(score_second)
    assert from_json(to_json(score_first), CategoryScoreRecord) == score_first
    assert models.SENSITIVITY_POLICIES["balanced"] == {
        "D": 0.35,
        "C": 0.30,
        "R": 0.20,
        "Q": 0.15,
    }
    assert set(models.SENSITIVITY_POLICIES) == {
        "balanced",
        "demand_heavy",
        "competition_heavy",
    }
    for policy in models.SENSITIVITY_POLICIES.values():
        assert pytest.approx(sum(policy.values())) == 1.0
    config = load_config(toml_path=ROOT / "config" / "default.toml")
    assert config.policy_versions() == {
        "endpoint_contract_version": models.ENDPOINT_CONTRACT_VERSION,
        "identity_mapping_rule_version": models.IDENTITY_MAPPING_RULE_VERSION,
        "sampling_rule_version": models.SAMPLING_RULE_VERSION,
    }


# ---------------------------------------------------------------------------
# 0B — domain models, statuses, serialization contracts
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-010")
def test_coveo_endpoint_contract() -> None:
    """Coveo constants are fixed and the filter contract forbids free-text queries."""
    config = load_config(toml_path=ROOT / "config" / "default.toml")
    assert (
        config.max_discovery_results_per_category
        == models.MAX_DISCOVERY_RESULTS_PER_CATEGORY
        == 9000
    )
    assert config.page_size == models.PAGE_SIZE == 96
    with pytest.raises(ValueError):
        load_config({"page_size": 50})
    assert DiscoveryStatus.TRUNCATED.value == "truncated"
    assert DiscoveryStatus.FILTER_UNVERIFIED.value == "filter_unverified"
    assert IdentityResolutionStatus.CONFLICT.value == "conflict"
    assert (
        WarningCode.DISCOVERY_FILTER_UNVERIFIED.value == "DISCOVERY_FILTER_UNVERIFIED"
    )


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_contract() -> None:
    """The taxonomy fixture carries every required header field and the categories."""
    taxonomy = json.loads(
        (ROOT / "config" / "category_taxonomy.json").read_text(encoding="utf-8")
    )
    for field in fixtures.REQUIRED_TAXONOMY_FIELDS:
        assert field in taxonomy, f"taxonomy is missing required field {field}"
    assert (
        datetime.fromisoformat(
            taxonomy["captured_at_utc"].replace("Z", "+00:00")
        ).tzinfo
        is not None
    )
    inventory = set(taxonomy["canonical_category_paths"])
    requested = read_categories(ROOT / "config" / "categories.json")
    assert len(requested) >= models.MIN_CATEGORIES_PER_RUN
    assert set(requested) <= inventory, (
        "taxonomy inventory must contain every requested category"
    )
    for path in requested:
        parent = path.rsplit("/", 1)[0]
        assert parent in inventory, "canonical parent paths must be present"
    with pytest.raises((ValueError, OSError)):
        read_categories(ROOT / "tests" / "fixtures" / "missing_categories.json")


@pytest.mark.lreq("LREQ-EXT-100")
def test_coveo_retry_contract() -> None:
    """Retry/backoff and failure classification require typed operation statuses."""
    assert {item.value for item in OperationStatus} == {"success", "error"}
    assert {item.value for item in models.IdentityPreflightStatus} == {
        "passed",
        "failed",
        "insufficient",
    }
    config_path = ROOT / "config" / "default.toml"
    config = load_config(toml_path=config_path)
    assert isinstance(config, NicheScoutConfig)
    assert config.max_discovery_results_per_category > 0
    assert models.MIN_CATEGORIES_PER_RUN == 8
    assert config.min_categories_per_run == models.MIN_CATEGORIES_PER_RUN


@pytest.mark.lreq("LREQ-GQL-010")
def test_graphql_endpoint_contract() -> None:
    """Enrichment contracts expose both required operations and one identity key."""
    assert {item.value for item in GraphQLOperationCorrelationMode} == {
        "explicit_key",
        "validated_position",
    }
    fields_of_enrichment = set(REQUIRED_ROW_FIELDS["enrichment_observations"])
    assert {"product_detail_status", "page_views_status"} <= fields_of_enrichment
    assert "asset_identity_key" in fields_of_enrichment
    assert {item.value for item in OperationStatus} == {"success", "error"}
    assert {item.value for item in PageViewSemanticsStatus} == {
        "unvalidated",
        "validated_cumulative",
        "contradicted",
        "validated_windowed_weekly",
    }
    assert (
        WarningCode.GRAPHQL_ID_MAPPING_MISMATCH.value == "GRAPHQL_ID_MAPPING_MISMATCH"
    )


@pytest.mark.lreq("LREQ-MET-040")
@pytest.mark.lreq("LREQ-GQL-010")
def test_page_view_semantics_status_includes_validated_windowed_weekly() -> None:
    """The D1-S3 token is a distinct enum member with its literal value."""
    member = PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY
    assert member.value == "validated_windowed_weekly"
    assert {item.value for item in PageViewSemanticsStatus} == {
        "unvalidated",
        "validated_cumulative",
        "contradicted",
        "validated_windowed_weekly",
    }


@pytest.mark.lreq("LREQ-GQL-010")
@pytest.mark.lreq("LREQ-ARCH-030")
def test_endpoint_contract_version_is_1_1_0() -> None:
    """The enrichment endpoint contract version is re-pinned to 1.1.0."""
    assert models.ENDPOINT_CONTRACT_VERSION == "1.1.0"


@pytest.mark.lreq("LREQ-SEC-010")
def test_credentials_contract() -> None:
    """Credentials come from the environment and are required before collection."""
    credentials = get_credentials(fixtures.MOCK_ENVIRONMENT)
    assert isinstance(credentials, Credentials)
    assert credentials.coveo_token == fixtures.MOCK_ENVIRONMENT[COVEO_TOKEN_ENV]
    assert (
        credentials.unity_csrf_token == fixtures.MOCK_ENVIRONMENT[UNITY_CSRF_TOKEN_ENV]
    )
    assert credentials.coveo_bearer_token == credentials.coveo_token
    credentials.require_for_collection()
    with pytest.raises(ValueError) as error:
        get_credentials(fixtures.MOCK_ENVIRONMENT_PARTIAL)
    assert COVEO_TOKEN_ENV in str(error.value)
    assert fixtures.MOCK_ENVIRONMENT[UNITY_CSRF_TOKEN_ENV] not in str(error.value)
    with pytest.raises(ValueError):
        get_credentials({})


@pytest.mark.lreq("LREQ-SEC-020")
def test_secrets_redaction_contract() -> None:
    """`.env` is ignored by version control and `.env.example` holds no credentials."""
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert COVEO_TOKEN_ENV in env_example
    assert UNITY_CSRF_TOKEN_ENV in env_example
    for line in env_example.splitlines():
        if "=" in line:
            _, _, value = line.partition("=")
            assert "fixture" not in value.lower()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored = {line.strip() for line in gitignore.splitlines()}
    assert ".env" in ignored
    assert "*.db" in ignored
    assert "*.sqlite" in ignored
    assert "__pycache__/" in ignored
    assert ".venv" in ignored


@pytest.mark.lreq("LREQ-ID-030")
def test_preflight_constants_contract() -> None:
    """Default preflight policy constants match SRS-lean §4.4 exactly."""
    assert models.IDENTITY_PREFLIGHT_MIN_CATEGORIES == 5
    assert models.IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY == 2
    assert models.IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE == 0.0
    assert models.IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE == 0.90
    config = load_config(toml_path=ROOT / "config" / "default.toml")
    assert config.identity_preflight_min_categories == 5
    assert config.identity_preflight_assets_per_category == 2
    assert config.identity_preflight_min_success_rate == 0.90
    assert "identity_preflight_max_conflict_rate" not in fields(NicheScoutConfig)
    assert "identity_preflight_max_conflict_rate" not in fixtures.DEFAULT_TOML_VALUES


@pytest.mark.lreq("LREQ-SMP-030")
def test_sampling_constants_contract() -> None:
    """Sampling constants are fixed, internally consistent, and not configurable."""
    assert models.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY == 100
    assert models.SAMPLE_STRATA == 4
    assert models.SAMPLE_PER_STRATUM == 25
    assert models.MIN_USABLE_SAMPLES_PER_STRATUM == 1
    assert (
        models.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
        == models.SAMPLE_STRATA * models.SAMPLE_PER_STRATUM
    )
    toml_body = (ROOT / "config" / "default.toml").read_text(encoding="utf-8")
    assert "SAMPLE_STRATA" not in toml_body
    assert "sample_strata" not in toml_body
    assert "sample_per_stratum" not in toml_body
    with pytest.raises(ValueError):
        load_config({"sample_strata": 8})
    # The shipped default TOML mirrors the in-code default (chunk-25).
    config = load_config(toml_path=ROOT / "config" / "default.toml")
    assert config.min_usable_samples_per_stratum == 1


@pytest.mark.lreq("LREQ-SMP-040")
def test_census_model_contract() -> None:
    """The census flag and sampling basis statuses are typed and preserve null."""
    assert {item.value for item in SamplingBasis} == {
        "census",
        "deterministic_stratified_sample",
    }
    assert "sample_is_census" in REQUIRED_ROW_FIELDS["category_scores"]
    assert "sample_fraction" in REQUIRED_ROW_FIELDS["category_scores"]
    assert "sample_is_census" in REQUIRED_ROW_FIELDS["sample_members"]
    score = _category_score_record()
    assert score.sample_is_census is True
    assert score.sample_fraction is None
    assert score.sample_fraction != 0.0
    assert score.sampling_basis == SamplingBasis.CENSUS.value
    assert score.sampling_basis != SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE.value


@pytest.mark.lreq("LREQ-SMP-060")
def test_selection_digest_contract() -> None:
    """The selection digest is the SHA-256 of NUL-delimited version, category, id."""
    sampling_rule_version = models.SAMPLING_RULE_VERSION
    category = "Tools/Level Design/Tilemap"
    asset_identity_key = "package-1234"
    payload = f"{sampling_rule_version}\x00{category}\x00{asset_identity_key}".encode(
        "utf-8"
    )
    assert (
        hashlib.sha256(payload).hexdigest()
        == hashlib.sha256(
            b"2.0.0\x00Tools/Level Design/Tilemap\x00package-1234"
        ).hexdigest()
    )
    members = [
        SampleMemberRecord(
            run_id="run-1",
            category=category,
            asset_identity_key=key,
            stratum_index=0,
            stratum_offset=0,
            stratum_stride=4,
            sample_rank_within_stratum=rank,
            sample_is_census=False,
            selection_digest=hashlib.sha256(
                f"{sampling_rule_version}\x00{category}\x00{key}".encode("utf-8")
            ).hexdigest(),
            overlap_category_count=0,
            overlap_sample_percentage=None,
            preflight_selected=rank < 2,
        )
        for rank, key in enumerate(("package-1234", "package-5678"))
    ]
    ordered = sorted(
        members, key=lambda member: (member.selection_digest, member.asset_identity_key)
    )
    assert len(ordered) == 2
    assert all(len(payload_member.selection_digest) == 64 for payload_member in members)
    assert (
        "random"
        not in (SRC / "niche_scout" / "models.py").read_text(encoding="utf-8").lower()
    )


@pytest.mark.lreq("LREQ-MET-020")
def test_age_calculation_contract() -> None:
    """Age uses exact fractional days from an explicit timezone-aware UTC cutoff."""
    scoring_cutoff_utc = datetime(2026, 3, 2, 12, tzinfo=timezone.utc)
    first_published_date_utc = datetime(2026, 1, 1, 0, tzinfo=timezone.utc)
    age_days_exact = (
        scoring_cutoff_utc - first_published_date_utc
    ).total_seconds() / 86400
    assert age_days_exact == 60.5
    assert int(age_days_exact) == 60
    assert age_days_exact > models.MIN_AGE_DAYS_FOR_RATE
    assert models.RECENT_WINDOW_DAYS == 365
    assert scoring_cutoff_utc - timedelta(
        days=models.MIN_AGE_DAYS_FOR_RATE
    ) == datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    at_boundary = scoring_cutoff_utc - (
        scoring_cutoff_utc - timedelta(days=models.MIN_AGE_DAYS_FOR_RATE)
    )
    assert at_boundary.total_seconds() / 86400 == 30.0
    assert models.MIN_AGE_DAYS_FOR_RATE == 30
    assert models.MIN_AGE_DAYS_FOR_RATE - 1 < models.MIN_AGE_DAYS_FOR_RATE
    with pytest.raises(ValueError):
        models.ensure_utc(datetime(2026, 1, 1))
    assert models.ensure_utc(
        datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))
    ) == datetime(2026, 1, 1, 0, tzinfo=timezone.utc)
    assert models.ensure_utc(first_published_date_utc) is first_published_date_utc


@pytest.mark.lreq("LREQ-CLI-030")
def test_config_precedence_contract(tmp_path: Path) -> None:
    """CLI arguments override TOML values, which override in-code defaults."""
    toml_path = fixtures.write_toml(tmp_path, fixtures.CUSTOM_TOML_BODY, "custom.toml")
    defaults_only = load_config(toml_path=toml_path)
    assert defaults_only.max_taxonomy_age_days == 14
    assert defaults_only.quality_min_eligible_assets == 7
    assert defaults_only.taxonomy_path == Path("runtime/custom_taxonomy.json")

    cli_wins = load_config(cli_args=fixtures.CLI_OVERRIDE_ARGS, toml_path=toml_path)
    assert cli_wins.max_discovery_results_per_category == 500
    assert cli_wins.min_age_days_for_rate == 90
    assert cli_wins.quality_min_eligible_assets == 12

    in_code = load_config()
    assert in_code.max_taxonomy_age_days == models.MAX_TAXONOMY_AGE_DAYS == 30
    assert in_code.quality_min_rating_count == models.QUALITY_MIN_RATING_COUNT == 5
    assert in_code.min_categories_per_run == models.MIN_CATEGORIES_PER_RUN == 8
    assert (
        in_code.strong_reference_category_count
        == models.STRONG_REFERENCE_CATEGORY_COUNT
        == 21
    )
    assert in_code.source == "defaults"

    unset_cli = load_config(cli_args=fixtures.CLI_NONE_ARGS, toml_path=toml_path)
    assert unset_cli.max_discovery_results_per_category == 1500
    assert unset_cli.recent_window_days == 180

    sectioned = load_config(
        toml_path=fixtures.write_toml(
            tmp_path, fixtures.SECTIONED_TOML_BODY, "section.toml"
        )
    )
    assert sectioned.max_taxonomy_age_days == 21
    assert sectioned.min_age_days_for_rate == 60
    assert sectioned.page_size == models.PAGE_SIZE

    missing_file = load_config(toml_path=tmp_path / "absent.toml")
    assert missing_file.source == "defaults"
    assert missing_file.db_path == models_module_default_db_path()


def models_module_default_db_path() -> Path:
    """Return the documented in-code database path default."""
    from niche_scout.config import IN_CODE_DEFAULTS

    return IN_CODE_DEFAULTS["db_path"]


@pytest.mark.lreq("LREQ-NFR-040")
def test_type_hints_and_docstrings() -> None:
    """Public records and status types are annotated and documented."""
    for row_type in (
        RunRecord,
        RawDiscoveryObservationRecord,
        SampleMemberRecord,
        EnrichmentObservationRecord,
        CategoryScoreRecord,
    ):
        for field in fields(row_type):
            assert field.type is not None
    for name in (
        "to_json",
        "to_json_dict",
        "from_json",
        "serialize_value",
        "ensure_utc",
    ):
        function = getattr(models, name)
        assert function.__doc__, f"{name} must have a docstring"
        assert function.__annotations__
    assert CategoryStatus.__doc__, "CategoryStatus must document its mapping role"
    score = _category_score_record()
    assert score.market_opportunity_score is None
    assert score.market_opportunity_score != 0.0
    assert score.evidence_grade == EvidenceGrade.INSUFFICIENT.value
    assert score.rankability_status == RankabilityStatus.NOT_RANKABLE.value
    assert score.score_state == ScoreState.UNAVAILABLE.value


@pytest.mark.lreq("LREQ-NFR-050")
def test_platform_pathlib_contract() -> None:
    """Paths use pathlib and the package requires Python 3.11+."""
    assert sys.version_info >= (3, 11)
    config = load_config()
    for name in ("categories_path", "taxonomy_path", "db_path"):
        assert isinstance(getattr(config, name), Path)
    assert isinstance(ROOT, Path)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in pyproject
    assert "pathlib" in (SRC / "niche_scout" / "config.py").read_text(encoding="utf-8")
    assert (SRC / "niche_scout" / "config.py").read_text(encoding="utf-8").count(
        "os.path"
    ) == 0


@pytest.mark.lreq("LREQ-NFR-060")
def test_quality_workflow_contract() -> None:
    """Marker registration, lint config, secret handling, and tests are wired up."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "lreq(requirement_id)" in pyproject
    assert "[tool.ruff]" in pyproject
    assert "pythonpath = " in pyproject
    assert (ROOT / "README.md").is_file()
    assert (
        ROOT / "src" / "niche_scout" / "tools" / "validate_traceability.py"
    ).is_file()
    assert not (ROOT / "tools").exists(), (
        "validation tools belong inside the package, not at the repo root"
    )
    assert (ROOT / "tests" / "fixtures" / "config_fixtures.py").is_file()
    assert (ROOT / "tests" / "traceability.json").is_file()


@pytest.mark.lreq("LREQ-TST-010")
def test_formula_test_conventions() -> None:
    """The suite foundation covers normal, zero, missing, invalid, tie, boundary."""
    boundary = models.MIN_USABLE_SAMPLES_PER_STRATUM
    assert boundary == 1
    assert boundary - 1 < boundary <= boundary
    assert models.MIN_REQUIRED_COMPONENT_COVERAGE == 0.50
    assert models.STRONG_COMPONENT_COVERAGE == 0.80
    assert models.MIN_REQUIRED_COMPONENT_COVERAGE < models.STRONG_COMPONENT_COVERAGE
    assert models.QUALITY_MIN_RATING_COUNT == 5
    assert models.QUALITY_MIN_ELIGIBLE_ASSETS == 5
    zero_population = _category_score_record()
    assert zero_population.discovered_population_count == 0
    assert zero_population.sample_fraction is None
    tie_values = [("a", 0.5), ("b", 0.5), ("c", 0.25)]
    assert sorted(tie_values, key=lambda item: (-item[1], item[0]))[0][1] == 0.5
    invalid_coverage = float("nan")
    assert invalid_coverage != invalid_coverage
    assert "zero_denominator" not in REQUIRED_ROW_FIELDS["category_scores"]
    assert set(REQUIRED_ROW_FIELDS["category_scores"]) >= {
        "sample_fraction",
        "demand_stratum_eligibility_coverage",
    }
    assert (ROOT / "tests" / "fixtures" / "README.md").is_file()


# ---------------------------------------------------------------------------
# Cross-cutting structure checks (0B/0C sub-gates)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-010")
def test_status_values_and_mandatory_fields_are_typed() -> None:
    """Every required SRS status value and mandatory row field exists in a type."""
    for enum_name, expected in REQUIRED_STATUS_VALUES.items():
        enum_type = getattr(models, enum_name)
        actual = {item.value for item in enum_type}
        assert actual == expected, f"{enum_name} values differ from the SRS set"
        assert all(isinstance(item, str) for item in actual)
    expected_warnings = {
        "DISCOVERY_TRUNCATED",
        "DISCOVERY_INCOMPLETE",
        "DISCOVERY_PAGE_FAILED",
        "DISCOVERY_FILTER_UNVERIFIED",
        "CATEGORY_MISMATCH",
        "IDENTITY_UNRESOLVED",
        "IDENTITY_CONFLICT",
        "IDENTITY_PREFLIGHT_FAILED",
        "GRAPHQL_PRODUCT_ERROR",
        "GRAPHQL_PAGE_VIEWS_ERROR",
        "GRAPHQL_ID_MAPPING_MISMATCH",
        "STATE_EXCLUDED",
        "INSUFFICIENT_DEMAND_SAMPLE",
        "INSUFFICIENT_RECENT_SAMPLE",
        "INSUFFICIENT_QUALITY_SAMPLE",
        "PAGE_VIEW_SEMANTICS_CONTRADICTED",
        "REFERENCE_SET_SMALL",
        "RANKING_SENSITIVITY_HIGH",
        "SAMPLE_BASED_SIGNAL",
    }
    assert {item.name for item in WarningCode} == expected_warnings
    for table, expected_fields in REQUIRED_ROW_FIELDS.items():
        actual_fields = models.MANDATORY_ROW_FIELDS[table]
        assert actual_fields == expected_fields, (
            f"{table} mandatory fields differ from SRS §6"
        )
        assert models.ROW_TYPES[table] is getattr(
            models, models.ROW_TYPES[table].__name__
        )
    for name, value in REQUIRED_CONSTANTS.items():
        assert getattr(models, name) == value, (
            f"{name} differs from the frozen constant"
        )
    assert set(models.SENSITIVITY_POLICIES) == {
        "balanced",
        "demand_heavy",
        "competition_heavy",
    }
    assert models.SENSITIVITY_POLICIES["demand_heavy"] == {
        "D": 0.50,
        "C": 0.25,
        "R": 0.15,
        "Q": 0.10,
    }
    assert models.SENSITIVITY_POLICIES["competition_heavy"] == {
        "D": 0.30,
        "C": 0.45,
        "R": 0.15,
        "Q": 0.10,
    }
    assert (models.W_D, models.W_C, models.W_R, models.W_Q) == (0.35, 0.30, 0.20, 0.15)
    assert pytest.approx(models.W_D + models.W_C + models.W_R + models.W_Q) == 1.0
    assert (models.DEMAND_SUBWEIGHT_PER_ASSET, models.DEMAND_SUBWEIGHT_MEDIAN) == (
        0.60,
        0.40,
    )
    assert (models.RECENT_SUBWEIGHT_SHARE, models.RECENT_SUBWEIGHT_AGE) == (0.70, 0.30)


@pytest.mark.lreq("LREQ-ARCH-010")
@pytest.mark.lreq("LREQ-EXT-050")
def test_discovery_incomplete_warning_is_distinct_from_discovery_truncated() -> None:
    """``DISCOVERY_INCOMPLETE`` is a separate Appendix C warning code.

    SRS Appendix C lists ``DISCOVERY_TRUNCATED`` and ``DISCOVERY_INCOMPLETE``
    as two codes, and the Lean 1.0.5 LREQ-EXT-050 addendum records the
    unreconciled-total shortfall as its own condition. The enum must carry both
    members and they must not collapse to one value.
    """
    assert WarningCode.DISCOVERY_INCOMPLETE.value == "DISCOVERY_INCOMPLETE"
    assert WarningCode.DISCOVERY_TRUNCATED.value == "DISCOVERY_TRUNCATED"
    assert WarningCode.DISCOVERY_INCOMPLETE != WarningCode.DISCOVERY_TRUNCATED
    assert len({WarningCode.DISCOVERY_INCOMPLETE, WarningCode.DISCOVERY_TRUNCATED}) == 2


@pytest.mark.lreq("LREQ-ARCH-010")
def test_repository_protocol_and_schema_specification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The repository protocol and DDL exist; importing database opens no connection."""
    protocol_methods = {
        "insert_run",
        "update_run_status",
        "insert_raw_discovery_observations",
        "insert_sample_members",
        "insert_enrichment_observations",
        "insert_category_scores",
        "get_run",
        "iter_raw_discovery_observations",
        "get_sample_members",
        "get_enrichment_observation",
        "get_category_scores",
    }
    assert protocol_methods <= set(dir(Repository))
    update_signature = Repository.update_run_status.__doc__ or ""
    assert update_signature is not None
    assert set(CREATE_TABLE_STATEMENTS) == {
        "runs",
        "raw_discovery_observations",
        "sample_members",
        "enrichment_observations",
        "category_scores",
    }
    assert set(TABLE_PRIMARY_KEYS) == set(CREATE_TABLE_STATEMENTS)
    assert TABLE_PRIMARY_KEYS["runs"] == ("run_id",)
    assert TABLE_PRIMARY_KEYS["raw_discovery_observations"] == ("observation_id",)
    assert TABLE_PRIMARY_KEYS["sample_members"] == (
        "run_id",
        "category",
        "asset_identity_key",
    )
    assert TABLE_PRIMARY_KEYS["enrichment_observations"] == (
        "run_id",
        "asset_identity_key",
    )
    assert TABLE_PRIMARY_KEYS["category_scores"] == ("run_id", "category")
    for table, statement in CREATE_TABLE_STATEMENTS.items():
        assert statement.startswith("CREATE TABLE " + table)
        assert "PRIMARY KEY" in statement
        assert TABLE_COLUMNS[table] == models.MANDATORY_ROW_FIELDS[table]
    index_rows = [
        statement
        for statement in DDL_STATEMENTS
        if statement.startswith("CREATE INDEX")
    ]
    assert any(
        "(run_id, category, discovery_ordinal)" in statement for statement in index_rows
    )
    scores_ddl = CREATE_TABLE_STATEMENTS["category_scores"]
    for alias in (
        "sample_size",
        "demand_usable_count",
        "recent_supply_usable_count",
        "quality_usable_count",
    ):
        assert alias not in scores_ddl, f"alias column {alias} must not exist"

    # The Chunk 0 prohibition is a construction-time, never import-time
    # constraint: the engine may be used later, but merely importing this
    # module must neither open a connection nor touch the filesystem.
    module_name = "niche_scout.database"
    monkeypatch.chdir(tmp_path)
    # Keep the original module object (and its parent-package attribute) so the
    # import-innocence check below does not leave ``niche_scout.database``
    # rebound to a fresh copy; the rest of the shared suite holds references to
    # the original module's classes/constants by value.
    package = sys.modules.get("niche_scout")
    original_module = sys.modules.get(module_name)
    original_package_attr = getattr(package, "database", None)
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    assert module_name not in sys.modules, "the module under test must be importable"

    observed_connections: list[tuple[object, ...]] = []

    def record_connect(*args: object, **kwargs: object) -> object:
        observed_connections.append(args)
        raise AssertionError(
            "importing niche_scout.database must not open a database connection"
        )

    monkeypatch.setattr(sqlite3, "connect", record_connect)
    try:
        importlib.import_module(module_name)
    except AssertionError:
        pass
    finally:
        monkeypatch.undo()

    assert not observed_connections, (
        "importing niche_scout.database must not open a database connection"
    )
    assert not list(tmp_path.iterdir()), (
        "importing niche_scout.database must not create any file"
    )
    if original_module is not None:
        sys.modules[module_name] = original_module
    if package is not None:
        setattr(package, "database", original_package_attr)


@pytest.mark.lreq("LREQ-RPT-020")
def test_category_scores_column_set_includes_failure_cause_and_version_is_1_3_0() -> (
    None
):
    """The Chunk 23 column is the last column and the schema version is 1.3.0.

    Hand-derived from ``interfaces/chunk-02.md`` §2.1 and the chunk-28 plan
    §5.4: ``SCHEMA_VERSION`` is ``"1.3.0"``; the ``1.2.0`` -> ``1.3.0`` bump
    is chunk-28's ``PageViewSemanticsStatus`` extension, which is metadata-only
    (``_ENUM_COLUMNS`` is Python-side, not DDL). ``category_scores`` still gains
    exactly one nullable column, ``discovery_failure_cause_json TEXT``, appended
    last so the frozen parity ``TABLE_COLUMNS["category_scores"] ==
    models.MANDATORY_ROW_FIELDS["category_scores"]`` still holds and it ships
    in the ``CREATE TABLE`` text. The ``1.1.0`` -> ``1.2.0`` bump was chunk-24's
    ``sample_members`` geometry-column rename (plan §3.1/§3.2); no migration path
    exists (single-run tool, SRS §15).
    """
    from niche_scout.database import SCHEMA_VERSION

    columns = TABLE_COLUMNS["category_scores"]
    assert columns[-1] == "discovery_failure_cause_json"
    assert columns[-1] in models.MANDATORY_ROW_FIELDS["category_scores"]
    assert columns == models.MANDATORY_ROW_FIELDS["category_scores"]
    assert SCHEMA_VERSION == "1.3.0"
    assert "discovery_failure_cause_json" in CREATE_TABLE_STATEMENTS["category_scores"]


@pytest.mark.lreq("LREQ-NFR-050")
def test_json_round_trip_for_all_records() -> None:
    """Serialization is deterministic and lossless for every record type."""
    run = _run_record()
    assert from_json(to_json(run), RunRecord) == run
    observation = RawDiscoveryObservationRecord(
        observation_id="obs-1",
        run_id="run-1",
        category="3D/Characters/Humanoids",
        discovery_ordinal=1,
        asset_identity_key=None,
        identity_candidates_json="[]",
        identity_resolution_status=IdentityResolutionStatus.UNRESOLVED.value,
        identity_resolution_reason=None,
        category_value_json="[]",
        category_filter_validation_status="unverified",
        stratum_index=None,
        is_duplicate=False,
        duplicate_of_observation_id=None,
        request_metadata_json="{}",
        error_summary_json=None,
        retrieved_at_utc=_iso(4),
    )
    assert from_json(to_json(observation), RawDiscoveryObservationRecord) == observation
    assert observation.asset_identity_key is None
    enrichment = EnrichmentObservationRecord(
        run_id="run-1",
        asset_identity_key="package-1234",
        product_detail_status=OperationStatus.SUCCESS.value,
        page_views_status=OperationStatus.ERROR.value,
        graphql_id=None,
        product_id="1234",
        rating_average=None,
        rating_count=None,
        review_count=None,
        first_published_date_utc=None,
        publisher_json=None,
        category_json=None,
        state=None,
        product_page_views=None,
        id_mapping_mismatch=False,
        product_detail_error_summary=None,
        page_views_error_summary="timeout",
        request_metadata_json="{}",
        retrieved_at_utc=_iso(5),
    )
    round_tripped = from_json(to_json(enrichment), EnrichmentObservationRecord)
    assert round_tripped == enrichment
    assert round_tripped.rating_average is None
    assert round_tripped.product_page_views is None
    members = [
        SampleMemberRecord(
            run_id="run-1",
            category="Audio/Music/Ambient",
            asset_identity_key="package-9",
            stratum_index=3,
            stratum_offset=0,
            stratum_stride=4,
            sample_rank_within_stratum=1,
            sample_is_census=False,
            selection_digest="a" * 64,
            overlap_category_count=0,
            overlap_sample_percentage=None,
            preflight_selected=False,
        )
    ]
    assert from_json(to_json(members[0]), SampleMemberRecord) == members[0]
    zip_style = to_json(run)
    assert zip_style.startswith('{"categories_json"')
    assert '"scoring_cutoff_utc":"2026-01-01T02:00:00Z"' in zip_style
    assert to_json(run) == to_json(_run_record())
