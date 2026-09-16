"""Persistence-neutral repository protocol and SQLite schema specification.

Chunk 0 defines contracts only. Opening connections, executing DDL, and
streamed inserts belong to the physical persistence chunk. The DDL strings
below are the frozen schema contract expressed using the exact mandatory field
names from :mod:`niche_scout.models`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterator, Optional, Protocol, Sequence

from .models import (
    CategoryScoreRecord,
    EnrichmentObservationRecord,
    RawDiscoveryObservationRecord,
    RunRecord,
    SampleMemberRecord,
)

SCHEMA_VERSION = "1.0.0"

# Column types are derived from the logical field types in models.py: SQLite
# stores timestamps as ISO-8601 UTC TEXT and booleans as INTEGER 0/1.
_UTC = "TEXT"
_FLAG = "INTEGER"
_INT = "INTEGER"
_REAL = "REAL"
_TEXT = "TEXT"


def _columns(definition: str) -> str:
    return definition


_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "runs": ("run_id",),
    "raw_discovery_observations": ("observation_id",),
    "sample_members": ("run_id", "category", "asset_identity_key"),
    "enrichment_observations": ("run_id", "asset_identity_key"),
    "category_scores": ("run_id", "category"),
}

_INDEXES: dict[str, tuple[str, ...]] = {
    "idx_raw_discovery_observations_run_category_ordinal": (
        "CREATE INDEX idx_raw_discovery_observations_run_category_ordinal "
        "ON raw_discovery_observations (run_id, category, discovery_ordinal)"
    ),
}

# DDL contract strings. Table bodies list the mandatory logical fields in plan
# order; no alias column such as `sample_size` is present.
CREATE_TABLE_RUNS = """
CREATE TABLE runs (
    run_id TEXT NOT NULL,
    run_started_at_utc TEXT NOT NULL,
    scoring_cutoff_utc TEXT,
    completed_at_utc TEXT,
    categories_json TEXT NOT NULL,
    config_snapshot_json TEXT NOT NULL,
    config_sha256 TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    taxonomy_captured_at_utc TEXT NOT NULL,
    taxonomy_sha256 TEXT NOT NULL,
    endpoint_contract_version TEXT NOT NULL,
    identity_mapping_rule_version TEXT NOT NULL,
    sampling_rule_version TEXT NOT NULL,
    page_view_semantics_status TEXT NOT NULL,
    graphql_operation_correlation_mode TEXT NOT NULL,
    identity_preflight_status TEXT NOT NULL,
    identity_preflight_summary_json TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (run_id)
)
""".strip()

CREATE_TABLE_RAW_DISCOVERY_OBSERVATIONS = """
CREATE TABLE raw_discovery_observations (
    observation_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    category TEXT NOT NULL,
    discovery_ordinal INTEGER NOT NULL,
    asset_identity_key TEXT,
    identity_candidates_json TEXT NOT NULL,
    identity_resolution_status TEXT NOT NULL,
    identity_resolution_reason TEXT,
    category_value_json TEXT NOT NULL,
    category_filter_validation_status TEXT NOT NULL,
    stratum_index INTEGER,
    is_duplicate INTEGER NOT NULL,
    duplicate_of_observation_id TEXT,
    request_metadata_json TEXT NOT NULL,
    error_summary_json TEXT,
    retrieved_at_utc TEXT NOT NULL,
    PRIMARY KEY (observation_id),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
)
""".strip()

CREATE_TABLE_SAMPLE_MEMBERS = """
CREATE TABLE sample_members (
    run_id TEXT NOT NULL,
    category TEXT NOT NULL,
    asset_identity_key TEXT NOT NULL,
    stratum_index INTEGER NOT NULL,
    stratum_start_ordinal INTEGER NOT NULL,
    stratum_end_ordinal INTEGER NOT NULL,
    sample_rank_within_stratum INTEGER NOT NULL,
    sample_is_census INTEGER NOT NULL,
    selection_digest TEXT NOT NULL,
    overlap_category_count INTEGER NOT NULL,
    overlap_sample_percentage REAL,
    preflight_selected INTEGER NOT NULL,
    PRIMARY KEY (run_id, category, asset_identity_key),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
)
""".strip()

CREATE_TABLE_ENRICHMENT_OBSERVATIONS = """
CREATE TABLE enrichment_observations (
    run_id TEXT NOT NULL,
    asset_identity_key TEXT NOT NULL,
    product_detail_status TEXT NOT NULL,
    page_views_status TEXT NOT NULL,
    graphql_id TEXT,
    product_id TEXT,
    rating_average REAL,
    rating_count INTEGER,
    review_count INTEGER,
    first_published_date_utc TEXT,
    publisher_json TEXT,
    category_json TEXT,
    state TEXT,
    product_page_views INTEGER,
    id_mapping_mismatch INTEGER NOT NULL,
    product_detail_error_summary TEXT,
    page_views_error_summary TEXT,
    request_metadata_json TEXT NOT NULL,
    retrieved_at_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, asset_identity_key),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
)
""".strip()

CREATE_TABLE_CATEGORY_SCORES = """
CREATE TABLE category_scores (
    run_id TEXT NOT NULL,
    category TEXT NOT NULL,
    discovery_status TEXT NOT NULL,
    discovery_filter_verified INTEGER NOT NULL,
    discovery_unresolved_identity_count INTEGER NOT NULL,
    discovery_conflict_count INTEGER NOT NULL,
    discovery_duplicate_count INTEGER NOT NULL,
    discovered_population_count INTEGER NOT NULL,
    enriched_sample_count INTEGER NOT NULL,
    sample_is_census INTEGER NOT NULL,
    sampling_basis TEXT NOT NULL,
    sample_fraction REAL,
    unique_enrichment_count INTEGER NOT NULL,
    overlap_category_count INTEGER NOT NULL,
    overlap_sample_percentage REAL,
    usable_demand_sample_count INTEGER NOT NULL,
    usable_recent_supply_sample_count INTEGER NOT NULL,
    usable_quality_sample_count INTEGER NOT NULL,
    breadth_source TEXT NOT NULL,
    breadth_completeness_status TEXT NOT NULL,
    discovery_bounded_by_verified_total INTEGER NOT NULL,
    demand_stratum_eligibility_coverage REAL NOT NULL,
    recent_supply_stratum_eligibility_coverage REAL NOT NULL,
    quality_stratum_eligibility_coverage REAL NOT NULL,
    demand_per_asset_raw REAL,
    demand_median_raw REAL,
    breadth_raw REAL,
    recent_share_raw REAL,
    median_age_raw REAL,
    quality_raw REAL,
    stratum_statistics_json TEXT NOT NULL,
    component_d REAL,
    component_c REAL,
    component_r REAL,
    component_q REAL,
    market_opportunity_score REAL,
    score_state TEXT NOT NULL,
    evidence_grade TEXT NOT NULL,
    rankability_status TEXT NOT NULL,
    missing_components_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    reference_size INTEGER NOT NULL,
    reference_usable_counts_json TEXT NOT NULL,
    top_3_stability REAL,
    top_5_stability REAL,
    maximum_score_delta REAL,
    maximum_rank_displacement INTEGER,
    sensitivity_warning INTEGER,
    ranking_sensitivity_json TEXT NOT NULL,
    computed_at_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, category),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
)
""".strip()

DDL_STATEMENTS: tuple[str, ...] = (
    CREATE_TABLE_RUNS,
    CREATE_TABLE_RAW_DISCOVERY_OBSERVATIONS,
    CREATE_TABLE_SAMPLE_MEMBERS,
    CREATE_TABLE_ENRICHMENT_OBSERVATIONS,
    CREATE_TABLE_CATEGORY_SCORES,
    *_INDEXES.values(),
)

# Table name -> DDL contract string, for consumers that select by table.
CREATE_TABLE_STATEMENTS: dict[str, str] = {
    "runs": CREATE_TABLE_RUNS,
    "raw_discovery_observations": CREATE_TABLE_RAW_DISCOVERY_OBSERVATIONS,
    "sample_members": CREATE_TABLE_SAMPLE_MEMBERS,
    "enrichment_observations": CREATE_TABLE_ENRICHMENT_OBSERVATIONS,
    "category_scores": CREATE_TABLE_CATEGORY_SCORES,
}

# Column layout contract: table name -> tuple of column names in DDL order.
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    table: tuple(
        line.strip().split()[0]
        for line in statement.splitlines()
        if line.strip()
        and not line.strip().startswith(("CREATE", "PRIMARY", "FOREIGN", ")"))
    )
    for table, statement in CREATE_TABLE_STATEMENTS.items()
}

TABLE_PRIMARY_KEYS: dict[str, tuple[str, ...]] = dict(_PRIMARY_KEYS)

TABLE_INDEXES: dict[str, tuple[str, ...]] = dict(_INDEXES)


class Repository(Protocol):
    """Persistence protocol consumed by downstream orchestration.

    Chunk 0 defines signatures only; no SQLite implementation exists here.
    """

    def insert_run(self, run: RunRecord) -> None: ...

    def update_run_status(
        self, run_id: str, status: str, completed_at_utc: Optional[datetime] = None
    ) -> None: ...

    def insert_raw_discovery_observations(
        self, observations: Sequence[RawDiscoveryObservationRecord]
    ) -> None: ...

    def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None: ...

    def insert_enrichment_observations(
        self, observations: Sequence[EnrichmentObservationRecord]
    ) -> None: ...

    def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None: ...

    def get_run(self, run_id: str) -> Optional[RunRecord]: ...

    def iter_raw_discovery_observations(
        self, run_id: str, category: str
    ) -> Iterator[RawDiscoveryObservationRecord]: ...

    def get_sample_members(
        self, run_id: str, category: str
    ) -> Sequence[SampleMemberRecord]: ...

    def get_enrichment_observation(
        self, run_id: str, asset_identity_key: str
    ) -> Optional[EnrichmentObservationRecord]: ...

    def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...


def _validate_specification() -> None:
    for table, primary_key in TABLE_PRIMARY_KEYS.items():
        columns = set(TABLE_COLUMNS[table])
        undeclared = sorted(set(primary_key) - columns)
        if undeclared:
            raise RuntimeError(
                f"{table}: primary key column not declared: {', '.join(undeclared)}"
            )


_validate_specification()
