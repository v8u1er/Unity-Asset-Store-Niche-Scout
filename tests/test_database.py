"""Chunk 2 analytical tests for the physical SQLite repository.

Every test here carries exactly the ``@pytest.mark.lreq`` marker set that
``Documents/plans/chunk-02-sqlite-implementation-and-repository.md`` section 9.4
assigns to its planned base node ID, and a matching entry in
``tests/traceability.json`` (added by the chunk's traceability step). The tests
are purely local: every database lives under pytest's ``tmp_path``, no live
network call is made, and ``sqlite3`` is the local storage engine only.

This slice covers the repository/schema group only: schema initialization, the
absence of alias columns and import-time DDL, pragma/foreign-key contracts,
insert-versus-upsert semantics, enum-backed column constraints, and stored
JSON/timestamp round trips. Assertions follow the observed behavior of
``niche_scout.database`` and never substitute a zero for an unavailable value.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import fixtures.config_fixtures as fixtures
import pytest

from niche_scout import models
from niche_scout.database import (
    CREATE_TABLE_STATEMENTS,
    DDL_STATEMENTS,
    SCHEMA_VERSION,
    TABLE_COLUMNS,
    TABLE_PRIMARY_KEYS,
    ForeignKeyConstraintViolation,
    InvalidRecordValueError,
    RepositoryError,
    SqliteRepository,
    UniqueConstraintViolation,
)
from niche_scout.models import (
    BreadthCompletenessStatus,
    BreadthSource,
    CategoryFilterValidationStatus,
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
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "niche_scout"
DATABASE_PATH = PACKAGE / "database.py"

# Enum-backed columns as the implementation derives them from the frozen models.
# The mapping is built here from the enum classes themselves, so the test asserts
# the allowed set the column actually carries rather than a paraphrased list.
TABLE_ENUM_COLUMNS: dict[tuple[str, str], tuple[str, ...]] = {
    ("runs", "status"): tuple(item.value for item in RunStatus),
    ("runs", "page_view_semantics_status"): tuple(
        item.value for item in PageViewSemanticsStatus
    ),
    ("runs", "graphql_operation_correlation_mode"): tuple(
        item.value for item in GraphQLOperationCorrelationMode
    ),
    ("runs", "identity_preflight_status"): tuple(
        item.value for item in IdentityPreflightStatus
    ),
    ("raw_discovery_observations", "identity_resolution_status"): tuple(
        item.value for item in IdentityResolutionStatus
    ),
    ("raw_discovery_observations", "category_filter_validation_status"): tuple(
        item.value for item in CategoryFilterValidationStatus
    ),
    ("enrichment_observations", "product_detail_status"): tuple(
        item.value for item in OperationStatus
    ),
    ("enrichment_observations", "page_views_status"): tuple(
        item.value for item in OperationStatus
    ),
    ("category_scores", "discovery_status"): tuple(
        item.value for item in DiscoveryStatus
    ),
    ("category_scores", "sampling_basis"): tuple(item.value for item in SamplingBasis),
    ("category_scores", "breadth_source"): tuple(item.value for item in BreadthSource),
    ("category_scores", "breadth_completeness_status"): tuple(
        item.value for item in BreadthCompletenessStatus
    ),
    ("category_scores", "score_state"): tuple(item.value for item in ScoreState),
    ("category_scores", "evidence_grade"): tuple(item.value for item in EvidenceGrade),
    ("category_scores", "rankability_status"): tuple(
        item.value for item in RankabilityStatus
    ),
}

# Columns whose DDL form is explicitly nullable in the frozen specification.
NULLABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    table: tuple(
        line.strip().split()[0]
        for line in statement.splitlines()
        if line.strip()
        and line.strip().split()[0].isidentifier()
        and "NOT NULL" not in line
    )
    for table, statement in CREATE_TABLE_STATEMENTS.items()
}


def _iso(hour: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures and the temp-path guard
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def database_paths_stay_under_pytest_temp_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[Path]:
    """Refuse to let any repository be constructed outside the pytest temp base.

    This guard is the point of the test module: without it, a test that ignored
    ``tmp_path`` could create a repo-relative ``runtime/*.sqlite3`` file. It
    asserts both the temp base itself and the captured path of every
    ``SqliteRepository`` construction, so a later test that passes a literal or
    repo-relative path fails loudly instead of writing into the tree.
    """
    temp_base = Path(tmp_path).resolve().parents[1]
    assert temp_base.is_dir(), "pytest must provide an existing temp base"
    assert ROOT not in temp_base.parents, (
        "pytest temp base must live outside the repository tree"
    )
    assert Path(tmp_path).resolve().is_relative_to(temp_base)

    observed: list[Path] = []
    # The guard wraps the real connection factory instead of ``__init__`` so it
    # observes every database path without perturbing constructor semantics or
    # pytest's fixture introspection.
    real_connect = sqlite3.connect

    def guarded_connect(database: Any, *args: Any, **kwargs: Any) -> Any:
        observed.append(Path(str(database)).resolve())
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
    yield tmp_path

    if request.node.get_closest_marker("lreq") is None:
        return
    # A test that legitimately constructs no repository (the import-time-DDL
    # check does exactly that) has nothing to prove here, so the guard asserts
    # only about the paths it actually observed.
    if not observed:
        return
    for path in observed:
        assert path.is_relative_to(temp_base), (
            f"a database path escaped the pytest temp base: {path}"
        )
        assert path.suffix == ".sqlite3", (
            "the guard tracks database files, not sidecar artifacts"
        )


@pytest.fixture
def run_record() -> RunRecord:
    """One frozen ``RunRecord`` with a running status and preflight metadata."""
    return RunRecord(
        run_id="run-1",
        run_started_at_utc=_iso(1),
        scoring_cutoff_utc=_iso(2),
        completed_at_utc=None,
        categories_json=json.dumps(list(fixtures.DEFAULT_CATEGORIES)),
        config_snapshot_json=json.dumps({"categories_path": "config/categories.json"}),
        config_sha256="0" * 64,
        taxonomy_version="1.0.0",
        taxonomy_captured_at_utc=_iso(0),
        taxonomy_sha256="1" * 64,
        endpoint_contract_version=models.ENDPOINT_CONTRACT_VERSION,
        identity_mapping_rule_version=models.IDENTITY_MAPPING_RULE_VERSION,
        sampling_rule_version=models.SAMPLING_RULE_VERSION,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED.value,
        graphql_operation_correlation_mode=(
            GraphQLOperationCorrelationMode.EXPLICIT_KEY.value
        ),
        identity_preflight_status=IdentityPreflightStatus.PASSED.value,
        identity_preflight_summary_json=json.dumps(
            {
                "correlation_mode": (
                    GraphQLOperationCorrelationMode.EXPLICIT_KEY.value
                ),
                "category_count": len(fixtures.DEFAULT_CATEGORIES),
            }
        ),
        status=RunStatus.RUNNING.value,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raw_observation(**overrides: Any) -> RawDiscoveryObservationRecord:
    payload: dict[str, Any] = {
        "observation_id": "obs-1",
        "run_id": "run-1",
        "category": fixtures.DEFAULT_CATEGORIES[0],
        "discovery_ordinal": 1,
        "asset_identity_key": "package-1",
        "identity_candidates_json": json.dumps([{"id": "package-1"}]),
        "identity_resolution_status": IdentityResolutionStatus.RESOLVED.value,
        "identity_resolution_reason": None,
        "category_value_json": json.dumps([fixtures.DEFAULT_CATEGORIES[0]]),
        "category_filter_validation_status": (
            CategoryFilterValidationStatus.VERIFIED.value
        ),
        "stratum_index": 0,
        "is_duplicate": False,
        "duplicate_of_observation_id": None,
        "request_metadata_json": json.dumps({"page": 1}),
        "error_summary_json": None,
        "retrieved_at_utc": _iso(4),
    }
    payload.update(overrides)
    return RawDiscoveryObservationRecord(**payload)


def _sample_member(**overrides: Any) -> SampleMemberRecord:
    payload: dict[str, Any] = {
        "run_id": "run-1",
        "category": fixtures.DEFAULT_CATEGORIES[0],
        "asset_identity_key": "package-1",
        "stratum_index": 0,
        "stratum_offset": 0,
        "stratum_stride": 4,
        "sample_rank_within_stratum": 1,
        "sample_is_census": False,
        "selection_digest": "a" * 64,
        "overlap_category_count": 0,
        "overlap_sample_percentage": None,
        "preflight_selected": True,
    }
    payload.update(overrides)
    return SampleMemberRecord(**payload)


def _enrichment(**overrides: Any) -> EnrichmentObservationRecord:
    payload: dict[str, Any] = {
        "run_id": "run-1",
        "asset_identity_key": "package-1",
        "product_detail_status": OperationStatus.SUCCESS.value,
        "page_views_status": OperationStatus.ERROR.value,
        "graphql_id": "gql-1",
        "product_id": "1234",
        "rating_average": None,
        "rating_count": None,
        "review_count": None,
        "first_published_date_utc": None,
        "publisher_json": None,
        "category_json": None,
        "state": "published",
        "product_page_views": None,
        "id_mapping_mismatch": False,
        "product_detail_error_summary": None,
        "page_views_error_summary": "page_views request failed",
        "request_metadata_json": json.dumps(
            {
                "correlation_mode": (
                    GraphQLOperationCorrelationMode.EXPLICIT_KEY.value
                ),
                "operations": ["product_detail", "page_views"],
            }
        ),
        "retrieved_at_utc": _iso(5),
    }
    payload.update(overrides)
    return EnrichmentObservationRecord(**payload)


def _full_category_score(**overrides: Any) -> models.CategoryScoreRecord:
    """A ``category_scores`` row with a value in every persisted column."""
    payload: dict[str, Any] = {
        "run_id": "run-1",
        "category": fixtures.DEFAULT_CATEGORIES[0],
        "discovery_status": DiscoveryStatus.COMPLETE.value,
        "discovery_filter_verified": True,
        "discovery_unresolved_identity_count": 0,
        "discovery_conflict_count": 0,
        "discovery_duplicate_count": 0,
        "discovered_population_count": 0,
        "enriched_sample_count": 0,
        "sample_is_census": True,
        "sampling_basis": SamplingBasis.CENSUS.value,
        "sample_fraction": None,
        "unique_enrichment_count": 0,
        "overlap_category_count": 0,
        "overlap_sample_percentage": None,
        "usable_demand_sample_count": 0,
        "usable_recent_supply_sample_count": 0,
        "usable_quality_sample_count": 0,
        "breadth_source": BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT.value,
        "breadth_completeness_status": BreadthCompletenessStatus.COMPLETE.value,
        "discovery_bounded_by_verified_total": False,
        "demand_stratum_eligibility_coverage": 0.0,
        "recent_supply_stratum_eligibility_coverage": 0.0,
        "quality_stratum_eligibility_coverage": 0.0,
        "demand_per_asset_raw": None,
        "demand_median_raw": None,
        "breadth_raw": None,
        "recent_share_raw": None,
        "median_age_raw": None,
        "quality_raw": None,
        "stratum_statistics_json": json.dumps([{"stratum_index": 0, "N_h": 10}]),
        "component_d": None,
        "component_c": None,
        "component_r": None,
        "component_q": None,
        "market_opportunity_score": None,
        "score_state": ScoreState.UNAVAILABLE.value,
        "evidence_grade": EvidenceGrade.INSUFFICIENT.value,
        "rankability_status": RankabilityStatus.NOT_RANKABLE.value,
        "missing_components_json": json.dumps(["D", "C", "R", "Q"]),
        "warnings_json": json.dumps(["SAMPLE_BASED_SIGNAL"]),
        "reference_size": 0,
        "reference_usable_counts_json": json.dumps({"D": 0}),
        "top_3_stability": None,
        "top_5_stability": None,
        "maximum_score_delta": None,
        "maximum_rank_displacement": None,
        "sensitivity_warning": None,
        "ranking_sensitivity_json": json.dumps({"balanced": {"D": 0.35}}),
        "computed_at_utc": _iso(6),
        "discovery_failure_cause_json": None,
    }
    payload.update(overrides)
    return models.CategoryScoreRecord(**payload)


# ---------------------------------------------------------------------------
# Section 9.3 fixtures
# ---------------------------------------------------------------------------
#
# Plan 9.3 lists seven fixtures. Two of them are the ``run_record`` fixture and
# the ``two_categories`` fixture below; the remaining five are the factory
# helpers ``_raw_observation`` / ``_sample_member`` / ``_enrichment`` /
# ``_full_category_score`` above plus ``_partial_category_score`` and
# ``_credential_shaped_text`` here. Section 9.3 keeps fixtures inside this
# module rather than adding a fixture module, so they live beside the tests
# that use them.


def _partial_category_score(**overrides: Any) -> models.CategoryScoreRecord:
    """A ``category_scores`` row with a partial score and no sensitivity yet."""
    payload = {
        "overlap_sample_percentage": 4.0,
        "usable_demand_sample_count": 72,
        "component_q": None,
        "market_opportunity_score": None,
        "score_state": ScoreState.PARTIAL.value,
        "evidence_grade": EvidenceGrade.WEAK.value,
        "rankability_status": RankabilityStatus.PROVISIONAL.value,
        "missing_components_json": json.dumps(["Q"]),
    }
    payload.update(overrides)
    return _full_category_score(**payload)


@pytest.fixture
def credential_shaped_text() -> dict[str, str]:
    """Token- and cookie-shaped strings used only to prove they never persist.

    They are hand-derived placeholders, not real credentials, and they exist
    solely so the redaction test has something to search every stored text
    column for. ``fixtures.config_fixtures.MOCK_ENVIRONMENT`` keeps the same
    discipline for the config layer.
    """
    return {
        "bearer": "fixture-bearer-token-0f3a1c9d4b7e",
        "csrf": "fixture-csrf-cookie-9a2b4c6d8e0f",
        "connection_string": "sqlite://token=fixture-bearer-token-0f3a1c9d4b7e",
    }


@pytest.fixture
def two_categories() -> tuple[str, str]:
    """The first two canonical category paths from the shared config fixtures."""
    first, second, *_ = fixtures.DEFAULT_CATEGORIES
    return first, second


# ---------------------------------------------------------------------------
# LREQ-SEC-020 — the persisted schema, its version, and its idempotence
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-020")
def test_schema_initialization_is_versioned_and_idempotent(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A frozen schema, one version row, and no destructive re-initialization."""
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        assert repository.schema_version == SCHEMA_VERSION
        assert repository.initialize_schema(check_version=True) == SCHEMA_VERSION
        assert repository.initialize_schema(check_version=True) == SCHEMA_VERSION

        stored_tables = {
            row[0]
            for row in repository.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert set(CREATE_TABLE_STATEMENTS) <= stored_tables
        assert "schema_metadata" in stored_tables, "the private metastore must exist"
        assert set(TABLE_COLUMNS) == set(CREATE_TABLE_STATEMENTS)
        assert set(stored_tables) == set(CREATE_TABLE_STATEMENTS) | {
            "schema_metadata"
        }, "the frozen schema has exactly five data tables plus the metastore"

        for table, columns in TABLE_COLUMNS.items():
            stored_columns = tuple(
                row[1]
                for row in repository.connection.execute(
                    f"PRAGMA table_info({table})"
                )
            )
            assert stored_columns == columns, f"{table} column list drifted from DDL"

        metadata = dict(
            repository.connection.execute(
                "SELECT key, value FROM schema_metadata"
            ).fetchall()
        )
        assert metadata["schema_version"] == SCHEMA_VERSION
        assert metadata["applied_at_utc"] != ""

        repository.insert_run(run_record)
        assert repository.get_run(run_record.run_id) == run_record
        assert (
            repository.initialize_schema(check_version=True)
            == repository.schema_version
            == SCHEMA_VERSION
        )
        assert repository.get_run(run_record.run_id) == run_record, (
            "re-initializing the schema must not delete or rewrite committed rows"
        )


@pytest.mark.lreq("LREQ-ARCH-030")
def test_schema_version_is_1_3_0() -> None:
    """Chunk-28 §5.4: the metadata-only bump for the status-token extension."""
    assert SCHEMA_VERSION == "1.3.0"


@pytest.mark.lreq("LREQ-ARCH-030")
@pytest.mark.lreq("LREQ-MET-040")
def test_enum_allow_list_accepts_validated_windowed_weekly() -> None:
    """The runs allow-list admits the new token and still rejects unknown ones."""
    from niche_scout import database as database_module

    database_module._validate_enum(
        "runs", "page_view_semantics_status", "validated_windowed_weekly"
    )
    with pytest.raises(InvalidRecordValueError):
        database_module._validate_enum(
            "runs", "page_view_semantics_status", "unknown_status_value"
        )


@pytest.mark.lreq("LREQ-ARCH-030")
def test_open_older_schema_raises_unless_check_version_false(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A stored 1.2.0 schema version is refused; check_version=False re-stamps it."""
    from niche_scout.database import SchemaVersionError

    database = tmp_path / "older_schema.sqlite3"
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        repository.connection.execute(
            "UPDATE schema_metadata SET value = ? WHERE key = 'schema_version'",
            ("1.2.0",),
        )
        repository.connection.commit()

    with pytest.raises(SchemaVersionError):
        SqliteRepository(database)

    reopened = SqliteRepository(database, initialize=False)
    try:
        assert reopened.initialize_schema(check_version=False) == SCHEMA_VERSION
        assert reopened.schema_version == SCHEMA_VERSION
        metadata = dict(
            reopened.connection.execute(
                "SELECT key, value FROM schema_metadata"
            ).fetchall()
        )
        assert metadata["schema_version"] == SCHEMA_VERSION
        assert reopened.get_run(run_record.run_id) == run_record, (
            "re-stamping the version must not rewrite committed rows"
        )
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# LREQ-TST-080 — frozen column set, no alias columns, no import-time DDL
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-080")
def test_no_alias_columns_and_no_import_time_ddl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The column set is the frozen one exactly, and importing runs no DDL/DML."""
    data_tables = set(CREATE_TABLE_STATEMENTS)
    assert data_tables == {
        "runs",
        "raw_discovery_observations",
        "sample_members",
        "enrichment_observations",
        "category_scores",
    }, "the schema has exactly the five SRS tables"
    assert set(TABLE_COLUMNS) == data_tables
    assert set(TABLE_PRIMARY_KEYS) == data_tables
    assert set(models.MANDATORY_ROW_FIELDS) == data_tables

    for table, columns in TABLE_COLUMNS.items():
        assert len(columns) == len(set(columns)), f"{table} has a duplicated column"
        assert columns == models.MANDATORY_ROW_FIELDS[table], (
            f"{table} column set must equal the frozen record fields exactly"
        )

    alias_columns = {
        "sample_size",
        "demand_usable_count",
        "recent_supply_usable_count",
        "quality_usable_count",
        "category_status",
    }
    for table, columns in TABLE_COLUMNS.items():
        assert not (set(columns) & alias_columns), f"{table} grew an alias column"
    assert "sample_fraction" in TABLE_COLUMNS["category_scores"]
    assert "demand_stratum_eligibility_coverage" in TABLE_COLUMNS["category_scores"], (
        "sample fraction and eligibility coverage stay distinct columns"
    )

    source = DATABASE_PATH.read_text(encoding="utf-8")
    assert "ALTER TABLE" not in source.upper()
    assert len(TABLE_PRIMARY_KEYS) == len(TABLE_COLUMNS)

    module_name = "niche_scout.database"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    assert module_name not in sys.modules, "the module under test must be importable"

    def refuse_connection(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "importing niche_scout.database must not open a database connection"
        )

    monkeypatch.setattr(sqlite3, "connect", refuse_connection)
    try:
        reimported = importlib.import_module(module_name)
    finally:
        monkeypatch.undo()
    assert not list(tmp_path.iterdir())


# ---------------------------------------------------------------------------
# LREQ-SEC-020, LREQ-GQL-080 — pragma and foreign-key contracts
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-020")
@pytest.mark.lreq("LREQ-GQL-080")
def test_foreign_key_and_pragma_contracts_are_enforced(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Every connection carries the four pragmas and enforces the declared keys."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    with SqliteRepository(database) as repository:
        pragmas = {
            name: repository.connection.execute(f"PRAGMA {name}").fetchone()[0]
            for name in ("foreign_keys", "journal_mode", "busy_timeout", "synchronous")
        }
        assert pragmas["foreign_keys"] == 1, "foreign_keys must be ON per connection"
        assert str(pragmas["journal_mode"]).lower() == "wal"
        assert pragmas["busy_timeout"] == 5000
        # Plan 5.4 promises only "the caller's configured value" for
        # ``synchronous`` and never enumerates a return-value vocabulary, so this
        # asserts the read-back form SQLite actually reports. pysqlite's read
        # form is the integer durability level, not the name the caller set:
        # NORMAL is stored as 1. Asserting the string 'normal' here would assert
        # a vocabulary the plan never published.
        assert pragmas["synchronous"] == 1, (
            "PRAGMA synchronous reads back the integer level; NORMAL is 1"
        )

        with pytest.raises(Exception) as orphan:
            repository.insert_sample_members(
                [_sample_member(run_id="run-absent", asset_identity_key="package-x")]
            )
        assert isinstance(orphan.value, ForeignKeyConstraintViolation), (
            "a child row for an unknown run_id must be a foreign-key violation"
        )
        assert str(orphan.value) == (
            "sample_members: row references a run_id that does not exist"
        )
        assert "package-x" not in str(orphan.value)
        assert repository.get_sample_members("run-absent", fixtures.DEFAULT_CATEGORIES[0]) == ()

        repository.insert_run(run_record)
        with repository.category_transaction(run_record.run_id, category):
            repository.insert_raw_discovery_observations([_raw_observation()])
        assert repository.count_raw_discovery_observations(
            run_record.run_id, fixtures.DEFAULT_CATEGORIES[0]
        ) == 1
        assert repository.count_discovery_observations(run_record.run_id) == 1

    reopened = SqliteRepository(database)
    try:
        assert reopened.schema_version == SCHEMA_VERSION
        assert reopened.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1, (
            "foreign_keys is per connection and must be re-applied on reopen"
        )
        assert reopened.get_run(run_record.run_id) == run_record
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# LREQ-SMP-080, LREQ-GQL-080, LREQ-SEC-020 — insert versus upsert, per table
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
@pytest.mark.lreq("LREQ-GQL-080")
@pytest.mark.lreq("LREQ-SEC-020")
def test_insert_versus_upsert_semantics_per_table(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Plain inserts reject duplicates; only the explicit upsert paths overwrite."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        with pytest.raises(UniqueConstraintViolation):
            repository.insert_run(run_record)

        observation = _raw_observation()
        with repository.category_transaction(run_record.run_id, category):
            repository.insert_raw_discovery_observations([observation])
            with pytest.raises(UniqueConstraintViolation):
                repository.insert_raw_discovery_observations([observation])

        member = _sample_member()
        repository.insert_sample_members([member])
        with pytest.raises(UniqueConstraintViolation):
            repository.insert_sample_members([member])
        assert repository.get_sample_members(run_record.run_id, category) == (member,)

        updated = _sample_member(stratum_index=3, sample_rank_within_stratum=4)
        assert repository.upsert_sample_members([updated]) == 1
        stored = repository.get_sample_members(run_record.run_id, category)
        assert stored == (updated,), "the upsert re-materializes the single membership"
        assert len(stored) == 1, "an upsert cannot create a second membership row"

        enrichment = _enrichment()
        repository.insert_enrichment_observations([enrichment])
        with pytest.raises(UniqueConstraintViolation):
            repository.insert_enrichment_observations([enrichment])
        corrected = _enrichment(product_page_views=0)
        assert repository.upsert_enrichment_observation(corrected) is None
        assert repository.get_enrichment_observation(
            run_record.run_id, enrichment.asset_identity_key
        ) == corrected
        assert repository.count_distinct_enrichment_identities(run_record.run_id) == 1

        scores = _full_category_score()
        repository.insert_category_scores([scores])
        with pytest.raises(UniqueConstraintViolation):
            repository.insert_category_scores([scores])
        assert repository.get_category_scores(run_record.run_id) == (scores,)

        # A different category is a different key, not a duplicate.
        sibling = _full_category_score(category=fixtures.DEFAULT_CATEGORIES[1])
        repository.insert_category_scores([sibling])
        stored_scores = repository.get_category_scores(run_record.run_id)
        assert stored_scores == (scores, sibling), (
            "get_category_scores orders rows lexically by category"
        )
        finalized = _full_category_score(
            market_opportunity_score=0.0,
            score_state=ScoreState.AVAILABLE.value,
            evidence_grade=EvidenceGrade.MODERATE.value,
        )
        assert repository.upsert_category_scores([finalized]) == 1
        assert repository.get_category_scores(run_record.run_id) == (finalized, sibling)
        assert repository.count_sample_members(run_record.run_id) == 1
        assert repository.count_discovery_observations(run_record.run_id) == 1
        assert repository.count_distinct_enrichment_observations(run_record.run_id) == 1
        assert repository.count_raw_discovery_observations(run_record.run_id, category) == 1
        assert set(TABLE_PRIMARY_KEYS) == set(TABLE_COLUMNS)


# ---------------------------------------------------------------------------
# LREQ-SEC-020, LREQ-ID-040 — enum-backed columns reject unknown values
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-020")
@pytest.mark.lreq("LREQ-ID-040")
def test_enum_backed_columns_reject_unknown_values(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Every enum-backed column accepts its frozen values and rejects others."""
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        for column, allowed in TABLE_ENUM_COLUMNS.items():
            table, column_name = column
            assert column_name in TABLE_COLUMNS[table]
            assert len(allowed) == len(set(allowed))
            assert "unknown_status_value" not in allowed

        # Runs: each allowed status is accepted, an unknown one is rejected.
        for status in TABLE_ENUM_COLUMNS[("runs", "status")]:
            repository.update_run_status(run_record.run_id, status)
            assert repository.get_run(run_record.run_id).status == status
        with pytest.raises(InvalidRecordValueError) as rejected:
            repository.update_run_status(run_record.run_id, "unknown_status_value")
        assert "runs.status" in str(rejected.value)
        assert "unknown_status_value" not in str(rejected.value)
        assert repository.get_run(run_record.run_id).status == RunStatus.FAILED.value, (
            "a rejected transition writes nothing"
        )

        # Raw observations: identity resolution and filter validation statuses.
        # Every raw write happens inside the category block plan 5.6 requires.
        category = fixtures.DEFAULT_CATEGORIES[0]
        with repository.category_transaction(run_record.run_id, category):
            for index, status in enumerate(
                TABLE_ENUM_COLUMNS[
                    ("raw_discovery_observations", "identity_resolution_status")
                ]
            ):
                resolved = status == IdentityResolutionStatus.RESOLVED.value
                repository.insert_raw_discovery_observations(
                    [
                        _raw_observation(
                            observation_id=f"obs-{index}",
                            identity_resolution_status=status,
                            asset_identity_key="package-1" if resolved else None,
                        )
                    ]
                )
            with pytest.raises(InvalidRecordValueError):
                repository.insert_raw_discovery_observations(
                    [
                        _raw_observation(
                            observation_id="obs-bad",
                            identity_resolution_status="unknown_status_value",
                        )
                    ]
                )
            for validation_status in TABLE_ENUM_COLUMNS[
                ("raw_discovery_observations", "category_filter_validation_status")
            ]:
                repository.insert_raw_discovery_observations(
                    [
                        _raw_observation(
                            observation_id=f"obs-filter-{validation_status}",
                            category_filter_validation_status=validation_status,
                        )
                    ]
                )
            with pytest.raises(InvalidRecordValueError):
                repository.insert_raw_discovery_observations(
                    [
                        _raw_observation(
                            observation_id="obs-bad-filter",
                            category_filter_validation_status="unknown_status_value",
                        )
                    ]
                )

        # Enrichment: the two independent operation statuses.
        for status in TABLE_ENUM_COLUMNS[("enrichment_observations", "page_views_status")]:
            repository.upsert_enrichment_observation(
                _enrichment(asset_identity_key=f"package-{status}", page_views_status=status)
            )
        for status in TABLE_ENUM_COLUMNS[
            ("enrichment_observations", "product_detail_status")
        ]:
            repository.upsert_enrichment_observation(
                _enrichment(
                    asset_identity_key=f"package-detail-{status}",
                    product_detail_status=status,
                )
            )
        with pytest.raises(InvalidRecordValueError):
            repository.upsert_enrichment_observation(
                _enrichment(asset_identity_key="package-bad", product_detail_status="nope")
            )

        # Sample members carry no enum-backed column.
        assert not [
            column
            for column in TABLE_ENUM_COLUMNS
            if column[0] == "sample_members"
        ]

        # Category scores: discovery status is validated before the row is written.
        repository.set_category_status(
            run_record.run_id,
            category,
            DiscoveryStatus.COMPLETE.value,
            computed_at_utc=_iso(6),
        )
        with pytest.raises(InvalidRecordValueError):
            repository.set_category_status(
                run_record.run_id,
                category,
                "unknown_status_value",
                computed_at_utc=_iso(6),
            )
        stored = {row.category: row for row in repository.get_category_scores(run_record.run_id)}
        assert stored[category].discovery_status == DiscoveryStatus.COMPLETE.value
        assert repository.count_discovery_observations(run_record.run_id) == (
            len(TABLE_ENUM_COLUMNS[("raw_discovery_observations", "identity_resolution_status")])
            + len(TABLE_ENUM_COLUMNS[("raw_discovery_observations", "category_filter_validation_status")])
        ), "only the accepted enum values were written"

        assert "unknown_status_value" not in database.read_bytes().decode(
            "utf-8", errors="ignore"
        ), "a rejected value must never reach the database file"


# ---------------------------------------------------------------------------
# LREQ-TST-080 — stored JSON and timestamp round trips
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-080")
def test_json_and_utc_round_trip_for_all_record_types(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Stored JSON is byte-exact and stored timestamps read back aware-UTC."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    second_category = fixtures.DEFAULT_CATEGORIES[1]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        stored_run = repository.get_run(run_record.run_id)
        assert stored_run == run_record
        run_row = repository.connection.execute(
            f"SELECT {', '.join(TABLE_COLUMNS['runs'])} FROM runs WHERE run_id = ?",
            (run_record.run_id,),
        ).fetchone()
        for index, column in enumerate(TABLE_COLUMNS["runs"]):
            expected = getattr(run_record, column)
            actual = run_row[index]
            if isinstance(expected, datetime):
                assert isinstance(actual, str)
                assert datetime.fromisoformat(actual).tzinfo is not None
                assert datetime.fromisoformat(actual) == expected
            else:
                assert actual == expected, f"runs.{column} was rewritten on write"

        observation = _raw_observation(
            error_summary_json=json.dumps({"error": "page_failed"}),
            identity_resolution_reason="candidates disagreed",
        )
        unreachable = _raw_observation(
            observation_id="obs-2",
            discovery_ordinal=2,
            asset_identity_key=None,
            identity_resolution_status=IdentityResolutionStatus.UNRESOLVED.value,
            identity_resolution_reason=None,
            error_summary_json=None,
            retrieved_at_utc=_iso(7),
        )
        with repository.category_transaction(run_record.run_id, category):
            repository.insert_raw_discovery_observations([observation, unreachable])
        read_back = tuple(
            repository.iter_raw_discovery_observations(run_record.run_id, category)
        )
        assert read_back == (observation, unreachable)
        assert read_back[1].asset_identity_key is None
        assert read_back[1].identity_resolution_reason is None
        assert read_back[1].error_summary_json is None, (
            "an absent error summary stays NULL rather than an empty string"
        )
        assert read_back[0].error_summary_json == json.dumps({"error": "page_failed"})
        assert read_back[0].retrieved_at_utc == observation.retrieved_at_utc

        # Plan 5.6's precondition: neither the batch form nor the streamed sink
        # is callable outside an active category_transaction, and the method
        # raises before reading the observations. The keyword form of
        # ``batch_size`` belongs to ``append_raw_discovery_observations``, whose
        # signature the frozen protocol does not constrain; the batch form takes
        # only ``observations``.
        with pytest.raises(RepositoryError):
            repository.insert_raw_discovery_observations([observation])
        with pytest.raises(RepositoryError):
            repository.append_raw_discovery_observations(iter([observation]))
        assert not repository.in_category_transaction()

        empty_category = repository.get_sample_members(run_record.run_id, second_category)
        assert empty_category == ()

    reopened = SqliteRepository(database)
    try:
        row = reopened.connection.execute(
            "SELECT retrieved_at_utc FROM raw_discovery_observations "
            "WHERE observation_id = ?",
            ("obs-1",),
        ).fetchone()
        assert datetime.fromisoformat(row[0]).tzinfo is not None
    finally:
        reopened.close()

    # The module contains no AST-level "unavailable becomes zero" pattern.
    tree = ast.parse(DATABASE_PATH.read_text(encoding="utf-8"), filename=str(DATABASE_PATH))
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or):
            continue
        rendered = ast.unparse(node)
        leaves = [ast.unparse(value) for value in node.values]
        assert "0" not in leaves, f"zero as an error sentinel: {rendered}"
        assert "0.0" not in leaves, f"zero as an error sentinel: {rendered}"


# ---------------------------------------------------------------------------
# LREQ-SEC-020, LREQ-NFR-060 — secrets never reach a record or an error message
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-020")
@pytest.mark.lreq("LREQ-NFR-060")
def test_repository_never_persists_or_leaks_secrets(
    tmp_path: Path,
    run_record: RunRecord,
    credential_shaped_text: dict[str, str],
) -> None:
    """No secret reaches a column, and no exception message echoes one.

    ``LREQ-NFR-060`` is attached here because the dependency-map matrix lists it
    in ``LREQ-SEC-020``'s required-test column; it adds no new normative
    obligation to this chunk (plan 9.4).
    """
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    leaked = tuple(credential_shaped_text.values())
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        with repository.category_transaction(run_record.run_id, category):
            repository.insert_raw_discovery_observations(
                [
                    _raw_observation(
                        error_summary_json=json.dumps(
                            {"header": credential_shaped_text["bearer"]}
                        ),
                        request_metadata_json=json.dumps(
                            {"cookie": credential_shaped_text["csrf"]}
                        ),
                    )
                ]
            )
        repository.insert_sample_members([_sample_member()])
        repository.insert_enrichment_observations(
            [
                _enrichment(
                    product_detail_error_summary=json.dumps(
                        {"authorization": credential_shaped_text["bearer"]}
                    ),
                    request_metadata_json=json.dumps(
                        {"connection": credential_shaped_text["connection_string"]}
                    ),
                )
            ]
        )
        repository.insert_category_scores([_partial_category_score()])
        repository.set_category_status(
            run_record.run_id,
            fixtures.DEFAULT_CATEGORIES[1],
            DiscoveryStatus.COMPLETE.value,
            computed_at_utc=_iso(9),
        )

        # Every exception message this module raises names table and column
        # names only. A duplicate key and a foreign-key violation are the two
        # messages that could borrow a caller's value if the module naively
        # interpolated the failed row.
        messages: list[str] = []
        try:
            repository.insert_run(run_record)
        except UniqueConstraintViolation as exc:
            messages.append(str(exc))
        try:
            repository.insert_sample_members(
                [_sample_member(run_id=credential_shaped_text["bearer"])]
            )
        except ForeignKeyConstraintViolation as exc:
            messages.append(str(exc))
        assert messages, "both constraint failures must raise the published types"
        for message in messages:
            for secret in leaked:
                assert secret not in message, (
                    "an exception message carried a credential-shaped value"
                )

        # No stored text anywhere in the file carries a credential value. The
        # scan reads the raw file bytes, so it covers pages SQLite has not yet
        # checkpointed as well as the main database image.
        blob = database.read_bytes()
        for secret in leaked:
            assert secret.encode("utf-8") not in blob, (
                "a credential-shaped value reached the database file"
            )

        stored = repository.get_run(run_record.run_id)
        assert stored.config_snapshot_json == run_record.config_snapshot_json
        assert "token" not in stored.identity_preflight_summary_json


# ---------------------------------------------------------------------------
# LREQ-SMP-080 — sample membership and its nullable/census columns
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_duplicate_sample_membership_is_rejected(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """The primary key, not a pre-INSERT SELECT, is the enforcement point."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        member = _sample_member()
        repository.insert_sample_members([member])

        # A second membership for the same (run_id, category, identity) fails
        # even though the summary columns differ: the key is the identity.
        second = _sample_member(stratum_index=3, sample_rank_within_stratum=9)
        with pytest.raises(UniqueConstraintViolation) as duplicate:
            repository.insert_sample_members([second])
        assert "sample_members" in str(duplicate.value)
        assert member.asset_identity_key not in str(duplicate.value), (
            "the duplicate message names the key columns, never the identity"
        )

        # The same identity in a sibling category is a different key.
        sibling = _sample_member(
            category=fixtures.DEFAULT_CATEGORIES[1], asset_identity_key="package-1"
        )
        repository.insert_sample_members([sibling])
        assert repository.count_sample_members(run_record.run_id) == 2
        assert repository.get_sample_members(
            run_record.run_id, fixtures.DEFAULT_CATEGORIES[1]
        ) == (sibling,)
        assert repository.get_sample_members(run_record.run_id, category) == (member,)

        # The constraint is the primary key declared by the frozen contract.
        assert TABLE_PRIMARY_KEYS["sample_members"] == (
            "run_id",
            "category",
            "asset_identity_key",
        )


@pytest.mark.lreq("LREQ-SMP-080")
def test_sample_member_round_trip_preserves_nullable_and_census_fields(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Census and sampled rows share the columns; nulls stay null."""
    database = tmp_path / "niche_scout.sqlite3"
    category, second_category = fixtures.DEFAULT_CATEGORIES[:2]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        census = _sample_member(
            asset_identity_key="package-census",
            sample_is_census=True,
            preflight_selected=False,
            overlap_category_count=0,
            overlap_sample_percentage=None,
        )
        sampled = tuple(
            _sample_member(
                category=second_category,
                asset_identity_key=f"package-s{stratum}",
                stratum_index=stratum,
                stratum_offset=0,
                stratum_stride=4,
                sample_rank_within_stratum=stratum + 1,
                sample_is_census=False,
                overlap_category_count=stratum,
                overlap_sample_percentage=(
                    None if stratum == 0 else float(stratum) / 4.0
                ),
                preflight_selected=stratum % 2 == 0,
            )
            for stratum in range(4)
        )
        repository.insert_sample_members([census, *sampled])

        stored_census = repository.get_sample_members(run_record.run_id, category)
        assert stored_census == (census,)
        assert stored_census[0].sample_is_census is True
        assert stored_census[0].preflight_selected is False
        assert stored_census[0].overlap_sample_percentage is None, (
            "an unavailable overlap percentage stays NULL, never 0.0"
        )

        stored_sampled = repository.get_sample_members(run_record.run_id, second_category)
        assert stored_sampled == tuple(
            sorted(sampled, key=lambda row: (row.stratum_index, row.sample_rank_within_stratum))
        ), "members come back ordered by stratum then rank"
        assert {row.stratum_index for row in stored_sampled} == {0, 1, 2, 3}
        assert [row.preflight_selected for row in stored_sampled] == [
            True,
            False,
            True,
            False,
        ]
        assert stored_sampled[0].overlap_sample_percentage is None
        assert stored_sampled[3].overlap_sample_percentage == 0.75

        # sample_is_census is an INTEGER 0/1 in storage and a bool on read.
        raw = repository.connection.execute(
            "SELECT sample_is_census, sample_fraction FROM category_scores"
        ).fetchall()
        assert raw == [], "no score rows were written yet"


# ---------------------------------------------------------------------------
# LREQ-GQL-080, LREQ-TST-030 — at most one enrichment row per run and identity
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-080")
@pytest.mark.lreq("LREQ-TST-030")
def test_at_most_one_enrichment_row_per_run_and_identity(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Two categories referencing one identity cannot produce two rows."""
    database = tmp_path / "niche_scout.sqllite3"
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        first = _enrichment(asset_identity_key="package-shared")
        repository.insert_enrichment_observations([first])

        # The same identity from a second category's sample is still the same
        # row: the key is (run_id, asset_identity_key), not the category.
        with pytest.raises(UniqueConstraintViolation):
            repository.insert_enrichment_observations(
                [_enrichment(asset_identity_key="package-shared", product_id="5678")]
            )
        assert repository.count_distinct_enrichment_identities(run_record.run_id) == 1

        reused = repository.get_enrichment_observation(
            run_record.run_id, "package-shared"
        )
        assert reused == first, "the prior result is retrievable for reuse"

        corrected = _enrichment(asset_identity_key="package-shared", product_id="5678")
        assert repository.upsert_enrichment_observation(corrected) is None
        assert repository.get_enrichment_observation(
            run_record.run_id, "package-shared"
        ) == corrected
        assert repository.count_distinct_enrichment_identities(run_record.run_id) == 1, (
            "the upsert overwrites the single existing row"
        )

        # An unknown identity reads back as absent rather than as an empty row.
        assert (
            repository.get_enrichment_observation(run_record.run_id, "package-absent")
            is None
        )
        assert TABLE_PRIMARY_KEYS["enrichment_observations"] == (
            "run_id",
            "asset_identity_key",
        )


# ---------------------------------------------------------------------------
# LREQ-NFR-010 — the streamed sink consumes a single-pass iterable
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-010")
def test_streamed_raw_append_consumes_single_pass_iterable(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A generator is written incrementally without being materialized."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    consumed: list[int] = []

    def emit(count: int) -> Iterator[RawDiscoveryObservationRecord]:
        """A non-seekable, single-pass source that records how far it got."""
        for ordinal in range(1, count + 1):
            consumed.append(ordinal)
            yield _raw_observation(
                observation_id=f"obs-{ordinal}",
                discovery_ordinal=ordinal,
                asset_identity_key=f"package-{ordinal}",
            )

    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        with pytest.raises(RepositoryError):
            repository.append_raw_discovery_observations(emit(3))
        assert consumed == [], (
            "the precondition fires before the iterable is read"
        )

        with pytest.raises(ValueError):
            repository.append_raw_discovery_observations(emit(1), batch_size=0)
        with pytest.raises(ValueError):
            repository.append_raw_discovery_observations(emit(1), batch_size=True)
        assert consumed == [], "batch_size is validated before the iterable is read"

        with repository.category_transaction(run_record.run_id, category):
            written = repository.append_raw_discovery_observations(emit(250), batch_size=50)
        assert written == 250
        assert consumed == list(range(1, 251)), "every record was consumed exactly once"
        assert repository.count_raw_discovery_observations(run_record.run_id, category) == 250

        # The sink works on a lazy source with no length and no re-iteration:
        # asking for the same generator twice would already be exhausted.
        second_category = fixtures.DEFAULT_CATEGORIES[1]
        first = _raw_observation(
            observation_id="obs-a", discovery_ordinal=1, category=second_category
        )
        second = _raw_observation(
            observation_id="obs-b", discovery_ordinal=2, category=second_category
        )
        single_pass = (record for record in (first, second))
        with repository.category_transaction(run_record.run_id, second_category):
            assert repository.append_raw_discovery_observations(single_pass) == 2
        assert tuple(
            repository.iter_raw_discovery_observations(
                run_record.run_id, second_category
            )
        ) == (first, second)


# ---------------------------------------------------------------------------
# LREQ-NFR-020 — the pre-enrichment counts are readable without a full scan
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-020")
def test_pre_enrichment_counts_are_readable_without_full_scans(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """The three counted quantities come from single COUNT queries."""
    database = tmp_path / "niche_scout.sqlite3"
    first, second = fixtures.DEFAULT_CATEGORIES[:2]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        assert repository.count_discovery_observations(run_record.run_id) == 0
        assert repository.count_sample_members(run_record.run_id) == 0
        assert repository.count_distinct_enrichment_identities(run_record.run_id) == 0

        with repository.category_transaction(run_record.run_id, first):
            repository.append_raw_discovery_observations(
                (
                    _raw_observation(
                        observation_id=f"obs-first-{ordinal}",
                        discovery_ordinal=ordinal,
                        asset_identity_key=f"package-{ordinal}",
                    )
                    for ordinal in range(1, 4)
                )
            )
        with repository.category_transaction(run_record.run_id, second):
            repository.append_raw_discovery_observations(
                (
                    _raw_observation(
                        observation_id=f"obs-second-{ordinal}",
                        category=second,
                        discovery_ordinal=ordinal,
                        asset_identity_key=f"package-{ordinal + 10}",
                    )
                    for ordinal in range(1, 3)
                )
            )
        repository.insert_sample_members(
            [
                _sample_member(asset_identity_key="package-1"),
                _sample_member(
                    category=second, asset_identity_key="package-11"
                ),
            ]
        )
        repository.insert_enrichment_observations(
            [
                _enrichment(asset_identity_key="package-1"),
                _enrichment(asset_identity_key="package-11"),
            ]
        )

        assert repository.count_discovery_observations(run_record.run_id) == 5
        assert repository.count_sample_members(run_record.run_id) == 2
        assert repository.count_distinct_enrichment_identities(run_record.run_id) == 2
        assert repository.count_raw_discovery_observations(run_record.run_id, first) == 3
        assert repository.count_raw_discovery_observations(run_record.run_id, second) == 2
        assert repository.count_distinct_enrichment_observations(run_record.run_id) == 2

        # Each count is one statement whose result is prepared without
        # materializing rows: the traced SQL is a single SELECT count(...).
        traced: list[str] = []
        repository.connection.set_trace_callback(traced.append)
        try:
            repository.count_discovery_observations(run_record.run_id)
            repository.count_sample_members(run_record.run_id)
            repository.count_distinct_enrichment_identities(run_record.run_id)
        finally:
            repository.connection.set_trace_callback(None)
        assert len(traced) == 3, f"expected one statement per count, got {traced}"
        for statement in traced:
            assert statement.lower().count("select") == 1
            assert "count(" in statement.lower()
            assert "select *" not in statement.lower()

        # An empty run still answers rather than raising.
        assert repository.count_discovery_observations("run-absent") == 0
        assert repository.count_sample_members("run-absent") == 0
        assert repository.count_distinct_enrichment_identities("run-absent") == 0


# ---------------------------------------------------------------------------
# LREQ-EXT-050, LREQ-EXT-090 — discovery terminal states survive the round trip
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-050")
@pytest.mark.lreq("LREQ-EXT-090")
def test_discovery_terminal_states_round_trip_without_zero_substitution(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Every terminal state is a stored status; a failed page is not zero assets."""
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        rows = [
            (
                DiscoveryStatus.COMPLETE.value,
                fixtures.DEFAULT_CATEGORIES[0],
                None,
                CategoryFilterValidationStatus.VERIFIED.value,
            ),
            (
                DiscoveryStatus.TRUNCATED.value,
                fixtures.DEFAULT_CATEGORIES[1],
                None,
                CategoryFilterValidationStatus.VERIFIED.value,
            ),
            (
                DiscoveryStatus.PAGE_FAILED.value,
                fixtures.DEFAULT_CATEGORIES[2],
                json.dumps({"error": "page request failed", "assets_read": 0}),
                CategoryFilterValidationStatus.VERIFIED.value,
            ),
            (
                DiscoveryStatus.FILTER_UNVERIFIED.value,
                fixtures.DEFAULT_CATEGORIES[3],
                None,
                CategoryFilterValidationStatus.UNVERIFIED.value,
            ),
            (
                DiscoveryStatus.CATEGORY_MISMATCH.value,
                fixtures.DEFAULT_CATEGORIES[4],
                None,
                CategoryFilterValidationStatus.MISMATCH.value,
            ),
            (
                DiscoveryStatus.IDENTITY_INCOMPLETE.value,
                fixtures.DEFAULT_CATEGORIES[5],
                None,
                CategoryFilterValidationStatus.VERIFIED.value,
            ),
            (
                DiscoveryStatus.REQUEST_FAILED.value,
                fixtures.DEFAULT_CATEGORIES[6],
                json.dumps({"error": "discovery request failed"}),
                CategoryFilterValidationStatus.UNVERIFIED.value,
            ),
        ]
        observations = []
        for index, (status, category, error, filter_status) in enumerate(rows):
            observation = _raw_observation(
                observation_id=f"obs-{index}",
                category=category,
                discovery_ordinal=1,
                asset_identity_key=None,
                identity_resolution_status=(
                    IdentityResolutionStatus.RESOLVED.value
                    if status == DiscoveryStatus.COMPLETE.value
                    else IdentityResolutionStatus.UNRESOLVED.value
                ),
                category_filter_validation_status=filter_status,
                stratum_index=None,
                error_summary_json=error,
            )
            observations.append(observation)
            repository.set_category_status(
                run_record.run_id,
                category,
                status,
                computed_at_utc=_iso(6),
            )
            with repository.category_transaction(run_record.run_id, category):
                repository.append_raw_discovery_observations([observation])

        stored_scores = {
            row.category: row for row in repository.get_category_scores(run_record.run_id)
        }
        for status, category, error, _filter in rows:
            assert stored_scores[category].discovery_status == status
        failed = stored_scores[fixtures.DEFAULT_CATEGORIES[2]]
        assert failed.discovery_status == DiscoveryStatus.PAGE_FAILED.value
        assert failed.discovered_population_count == 0, (
            "the pre-scoring default is a known zero, not a fabricated asset count"
        )

        for observation in observations:
            stored = next(
                repository.iter_raw_discovery_observations(
                    run_record.run_id, observation.category
                )
            )
            assert stored == observation
            if stored.error_summary_json is None:
                assert stored.error_summary_json is None
            else:
                assert json.loads(stored.error_summary_json)["error"]

        # A zero-result category is an empty observation set with a persisted
        # status, never a fabricated zero-asset row.
        empty = fixtures.DEFAULT_CATEGORIES[7]
        repository.set_category_status(
            run_record.run_id, empty, DiscoveryStatus.COMPLETE.value, computed_at_utc=_iso(6)
        )
        assert tuple(
            repository.iter_raw_discovery_observations(run_record.run_id, empty)
        ) == ()
        assert repository.count_raw_discovery_observations(run_record.run_id, empty) == 0
        stored_empty = {
            row.category: row
            for row in repository.get_category_scores(run_record.run_id)
        }
        assert stored_empty[empty].discovery_status == DiscoveryStatus.COMPLETE.value
        assert stored_empty[empty].category == empty


# ---------------------------------------------------------------------------
# LREQ-EXT-070 — unresolved and conflicting identities keep a NULL key
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-070")
def test_unresolved_and_conflicting_identities_persist_null_identity_key(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A placeholder identity key is never substituted for a real one."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        resolved = _raw_observation(observation_id="obs-resolved")
        unresolved = _raw_observation(
            observation_id="obs-unresolved",
            discovery_ordinal=2,
            asset_identity_key=None,
            identity_resolution_status=IdentityResolutionStatus.UNRESOLVED.value,
            identity_resolution_reason="no candidate carried a stable package id",
        )
        conflicting = _raw_observation(
            observation_id="obs-conflict",
            discovery_ordinal=3,
            asset_identity_key=None,
            identity_candidates_json=json.dumps(
                [{"id": "package-1"}, {"id": "package-2"}]
            ),
            identity_resolution_status=IdentityResolutionStatus.CONFLICT.value,
            identity_resolution_reason="candidates disagreed",
        )
        with repository.category_transaction(run_record.run_id, category):
            repository.append_raw_discovery_observations(
                [resolved, unresolved, conflicting]
            )

        stored = tuple(
            repository.iter_raw_discovery_observations(run_record.run_id, category)
        )
        assert stored == (resolved, unresolved, conflicting)
        reasons = {row.observation_id: row.identity_resolution_reason for row in stored}
        assert reasons["obs-resolved"] is None
        assert reasons["obs-unresolved"] == unresolved.identity_resolution_reason
        assert reasons["obs-conflict"] == conflicting.identity_resolution_reason

        for row in stored[1:]:
            assert row.asset_identity_key is None, (
                "unresolved and conflicting rows must not carry a placeholder key"
            )
            assert row.identity_candidates_json, "the candidates JSON stays intact"
            assert row.identity_resolution_status in {
                IdentityResolutionStatus.UNRESOLVED.value,
                IdentityResolutionStatus.CONFLICT.value,
            }

        raw = repository.connection.execute(
            "SELECT observation_id, asset_identity_key FROM raw_discovery_observations "
            "WHERE run_id = ? ORDER BY discovery_ordinal",
            (run_record.run_id,),
        ).fetchall()
        assert raw[1][1] is None and raw[2][1] is None, (
            "the stored column is SQL NULL, not an empty string"
        )

        # The post-discovery update path is what fills the key later, and only
        # for the four declared columns.
        promoted = _raw_observation(
            observation_id="obs-resolved",
            asset_identity_key="package-resolved",
            stratum_index=2,
            is_duplicate=True,
            duplicate_of_observation_id="obs-unresolved",
        )
        assert repository.update_raw_discovery_identity([promoted]) == 1
        stored_resolved = next(
            repository.iter_raw_discovery_observations(run_record.run_id, category)
        )
        assert stored_resolved.asset_identity_key == "package-resolved"
        assert stored_resolved.stratum_index == 2
        assert stored_resolved.is_duplicate is True
        assert stored_resolved.duplicate_of_observation_id == "obs-unresolved"


# ---------------------------------------------------------------------------
# LREQ-GQL-050 — partial GraphQL operation success is stored independently
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-050")
def test_partial_graphql_operation_success_is_stored_independently(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A valid ProductDetail survives a failed PageViews and vice versa."""
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        both_ok = _enrichment(
            asset_identity_key="package-both",
            product_detail_status=OperationStatus.SUCCESS.value,
            page_views_status=OperationStatus.SUCCESS.value,
            product_page_views=1200,
            rating_average=4.5,
            rating_count=30,
            review_count=12,
        )
        detail_only = _enrichment(
            asset_identity_key="package-detail",
            product_detail_status=OperationStatus.SUCCESS.value,
            page_views_status=OperationStatus.ERROR.value,
            product_page_views=None,
            page_views_error_summary=json.dumps({"error": "page views failed"}),
        )
        views_only = _enrichment(
            asset_identity_key="package-views",
            product_detail_status=OperationStatus.ERROR.value,
            page_views_status=OperationStatus.SUCCESS.value,
            product_page_views=900,
            graphql_id=None,
            product_id=None,
            state=None,
            product_detail_error_summary=json.dumps({"error": "product detail failed"}),
        )
        neither = _enrichment(
            asset_identity_key="package-neither",
            product_detail_status=OperationStatus.ERROR.value,
            page_views_status=OperationStatus.ERROR.value,
            product_page_views=None,
            first_published_date_utc=None,
        )
        repository.insert_enrichment_observations([both_ok, detail_only, views_only, neither])

        for record in (both_ok, detail_only, views_only, neither):
            stored = repository.get_enrichment_observation(
                run_record.run_id, record.asset_identity_key
            )
            assert stored == record, f"{record.asset_identity_key} did not round-trip"
            if record.product_page_views is None:
                assert stored.product_page_views is None
            else:
                assert stored.product_page_views == record.product_page_views

        failed_views = repository.get_enrichment_observation(
            run_record.run_id, detail_only.asset_identity_key
        )
        assert failed_views.product_detail_status == OperationStatus.SUCCESS.value
        assert failed_views.product_page_views is None, (
            "a failed PageViews stores NULL, never 0 as an error sentinel"
        )
        assert failed_views.page_views_error_summary is not None

        failed_detail = repository.get_enrichment_observation(
            run_record.run_id, views_only.asset_identity_key
        )
        assert failed_detail.page_views_status == OperationStatus.SUCCESS.value
        assert failed_detail.product_page_views == 900
        assert failed_detail.graphql_id is None
        assert failed_detail.product_id is None

        raw = repository.connection.execute(
            "SELECT product_page_views FROM enrichment_observations "
            "WHERE asset_identity_key = ?",
            (detail_only.asset_identity_key,),
        ).fetchone()
        assert raw[0] is None, "the stored value is SQL NULL rather than a zero"


# ---------------------------------------------------------------------------
# LREQ-ID-010 — preflight selection is persisted on sample members
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-010")
def test_preflight_selection_is_persisted_on_sample_members(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """``preflight_selected`` is a per-member boolean, including tiny categories."""
    database = tmp_path / "niche_scout.sqlite3"
    rich, thin = fixtures.DEFAULT_CATEGORIES[:2]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        selected = tuple(
            _sample_member(
                asset_identity_key=f"package-{index}",
                stratum_index=index,
                sample_rank_within_stratum=index + 1,
                preflight_selected=index < 2,
            )
            for index in range(4)
        )
        # A category with fewer than two assets is representable with no
        # special casing: one member, selected, and nothing else changes.
        lonely = _sample_member(
            category=thin,
            asset_identity_key="package-lonely",
            stratum_index=0,
            stratum_offset=0,
            stratum_stride=1,
            sample_rank_within_stratum=1,
            sample_is_census=True,
            preflight_selected=True,
        )
        repository.insert_sample_members([*selected, lonely])

        stored = repository.get_sample_members(run_record.run_id, rich)
        assert [row.preflight_selected for row in stored] == [True, True, False, False]
        assert all(isinstance(row.preflight_selected, bool) for row in stored)
        assert repository.get_sample_members(run_record.run_id, thin) == (lonely,)
        assert repository.get_sample_members(run_record.run_id, thin)[0].preflight_selected is True

        # The re-materialization path updates the flag without adding a row.
        flipped = _sample_member(
            asset_identity_key="package-0",
            stratum_index=0,
            sample_rank_within_stratum=1,
            preflight_selected=False,
        )
        assert repository.upsert_sample_members([flipped]) == 1
        assert repository.count_sample_members(run_record.run_id) == 5
        assert repository.get_sample_members(run_record.run_id, rich)[0] == flipped
        assert "preflight_selected" in TABLE_COLUMNS["sample_members"]


# ---------------------------------------------------------------------------
# LREQ-ID-020 — preflight observations persist both operations and correlation
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-020")
def test_preflight_observations_persist_both_operations_and_correlation_metadata(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Preflight rows use the same upsert path with independent statuses."""
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        outcomes = (
            (
                "package-ok",
                OperationStatus.SUCCESS.value,
                OperationStatus.SUCCESS.value,
                GraphQLOperationCorrelationMode.EXPLICIT_KEY.value,
            ),
            (
                "package-detail-only",
                OperationStatus.SUCCESS.value,
                OperationStatus.ERROR.value,
                GraphQLOperationCorrelationMode.VALIDATED_POSITION.value,
            ),
            (
                "package-views-only",
                OperationStatus.ERROR.value,
                OperationStatus.SUCCESS.value,
                GraphQLOperationCorrelationMode.VALIDATED_POSITION.value,
            ),
            (
                "package-both-failed",
                OperationStatus.ERROR.value,
                OperationStatus.ERROR.value,
                GraphQLOperationCorrelationMode.EXPLICIT_KEY.value,
            ),
        )
        for identity, detail, views, mode in outcomes:
            repository.upsert_enrichment_observation(
                _enrichment(
                    asset_identity_key=identity,
                    product_detail_status=detail,
                    page_views_status=views,
                    product_page_views=100 if views == OperationStatus.SUCCESS.value else None,
                    request_metadata_json=json.dumps(
                        {
                            "phase": "identity_preflight",
                            "correlation_mode": mode,
                            "operations": ["product_detail", "page_views"],
                            "request_id_echoed": True,
                        }
                    ),
                )
            )

        for identity, detail, views, mode in outcomes:
            stored = repository.get_enrichment_observation(run_record.run_id, identity)
            assert stored.product_detail_status == detail
            assert stored.page_views_status == views, (
                "the two operation statuses are independent columns"
            )
            metadata = json.loads(stored.request_metadata_json)
            assert metadata["correlation_mode"] == mode
            assert metadata["phase"] == "identity_preflight"
            assert metadata["operations"] == ["product_detail", "page_views"]

        # The upsert path re-records the same identity without a second row.
        before = repository.count_distinct_enrichment_identities(run_record.run_id)
        repository.upsert_enrichment_observation(
            _enrichment(
                asset_identity_key="package-ok",
                product_detail_status=OperationStatus.ERROR.value,
                page_views_status=OperationStatus.SUCCESS.value,
                request_metadata_json=json.dumps({"phase": "identity_preflight"}),
            )
        )
        assert repository.count_distinct_enrichment_identities(run_record.run_id) == before


# ---------------------------------------------------------------------------
# LREQ-ID-040 — preflight status values persist distinctly
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ID-040")
def test_preflight_status_values_persist_distinctly(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """``insufficient``, ``failed``, and ``passed`` are three distinct rows."""
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        for status in (
            IdentityPreflightStatus.PASSED.value,
            IdentityPreflightStatus.FAILED.value,
            IdentityPreflightStatus.INSUFFICIENT.value,
        ):
            run_id = f"run-{status}"
            run = RunRecord(
                **{
                    field: getattr(run_record, field)
                    for field in (
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
                        "identity_preflight_summary_json",
                        "status",
                    )
                },
                run_id=run_id,
                identity_preflight_status=status,
            )
            repository.insert_run(run)
            stored = repository.get_run(run.run_id)
            assert stored.identity_preflight_status == status

        # Write-time update of the status and the summary, independently.
        # The update targets the run the loop actually inserted, not
        # ``run_record``'s own ``run_id``: that row was never persisted here.
        touched_run_id = f"run-{IdentityPreflightStatus.INSUFFICIENT.value}"
        repository.update_run_preflight(
            touched_run_id,
            identity_preflight_status=IdentityPreflightStatus.INSUFFICIENT.value,
            identity_preflight_summary_json=json.dumps(
                {
                    "attempted_identities": 0,
                    "detail_success_rate": None,
                    "page_views_success_rate": None,
                }
            ),
        )
        updated = repository.get_run(touched_run_id)
        assert updated.identity_preflight_status == IdentityPreflightStatus.INSUFFICIENT.value
        summary = json.loads(updated.identity_preflight_summary_json)
        assert summary["attempted_identities"] == 0
        assert summary["detail_success_rate"] is None, (
            "an undefined rate stays null rather than being written as zero"
        )
        assert updated.graphql_operation_correlation_mode == (
            run_record.graphql_operation_correlation_mode
        ), "a field whose keyword was omitted must be left unchanged"

        # Only the summary can be set on its own.
        repository.update_run_preflight(
            touched_run_id,
            identity_preflight_summary_json=json.dumps({"attempted_identities": 3}),
        )
        assert json.loads(
            repository.get_run(touched_run_id).identity_preflight_summary_json
        ) == {"attempted_identities": 3}
        assert repository.get_run(touched_run_id).identity_preflight_status == (
            IdentityPreflightStatus.INSUFFICIENT.value
        ), "the status set earlier must survive a summary-only update"

        with pytest.raises(InvalidRecordValueError):
            repository.update_run_preflight(
                touched_run_id, identity_preflight_status="not_a_status"
            )
        with pytest.raises(KeyError):
            repository.update_run_preflight(
                "run-absent", identity_preflight_status=IdentityPreflightStatus.PASSED.value
            )


# ---------------------------------------------------------------------------
# LREQ-NRM-020 — reference size and usable counts persist separately
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NRM-020")
def test_reference_size_and_usable_counts_persist_separately(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """``reference_size`` is a column of its own, never aliased to a count."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        usable = {
            "D": 72,
            "C": 64,
            "R": 51,
            "Q": 40,
        }
        score = _partial_category_score(
            reference_size=20,
            reference_usable_counts_json=json.dumps(usable),
            usable_demand_sample_count=64,
            usable_recent_supply_sample_count=51,
            usable_quality_sample_count=40,
            enriched_sample_count=100,
            discovered_population_count=120,
        )
        repository.insert_category_scores([score])
        stored = repository.get_category_scores(run_record.run_id)[0]
        assert stored == score
        assert stored.reference_size == 20, "21 categories means 20 peers"
        assert json.loads(stored.reference_usable_counts_json) == usable

        # The count columns keep their own values: the reference size is not
        # recomputed from them and no usable count is derived from the peers.
        assert stored.usable_demand_sample_count == score.usable_demand_sample_count
        assert stored.usable_recent_supply_sample_count == score.usable_recent_supply_sample_count
        assert stored.usable_quality_sample_count == score.usable_quality_sample_count
        assert stored.enriched_sample_count == score.enriched_sample_count
        assert stored.discovered_population_count == score.discovered_population_count
        assert stored.reference_size not in {
            stored.discovered_population_count,
            stored.enriched_sample_count,
            stored.unique_enrichment_count,
            0,
        }

        raw = repository.connection.execute(
            "SELECT reference_size, reference_usable_counts_json, "
            "usable_demand_sample_count, usable_recent_supply_sample_count, "
            "usable_quality_sample_count, enriched_sample_count, "
            "discovered_population_count FROM category_scores WHERE category = ?",
            (category,),
        ).fetchone()
        assert raw[0] == 20
        assert raw[1] == json.dumps(usable)
        assert tuple(raw[2:]) == (64, 51, 40, 100, 120)
        assert "sample_size" not in TABLE_COLUMNS["category_scores"]
        assert "demand_usable_count" not in TABLE_COLUMNS["category_scores"]


# ---------------------------------------------------------------------------
# LREQ-SEN-020 — null sensitivity diagnostics round-trip as NULL
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEN-020")
def test_null_sensitivity_diagnostics_round_trip_as_null(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A null stability value is NULL in storage, never a padded 0.0."""
    database = tmp_path / "niche_scout.sqlite3"
    category, second = fixtures.DEFAULT_CATEGORIES[:2]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        nulls = _full_category_score(
            top_3_stability=None,
            top_5_stability=None,
            maximum_score_delta=None,
            maximum_rank_displacement=None,
            sensitivity_warning=None,
            ranking_sensitivity_json=json.dumps({"policies": ["balanced"]}),
        )
        populated = _partial_category_score(
            category=second,
            top_3_stability=1.0,
            top_5_stability=0.8,
            maximum_score_delta=0.125,
            maximum_rank_displacement=3,
            sensitivity_warning=True,
            ranking_sensitivity_json=json.dumps({"balanced": {"D": 0.35}}),
        )
        repository.insert_category_scores([nulls, populated])

        stored = {row.category: row for row in repository.get_category_scores(run_record.run_id)}
        assert stored[category] == nulls
        assert stored[second] == populated
        for column in (
            "top_3_stability",
            "top_5_stability",
            "maximum_score_delta",
            "maximum_rank_displacement",
            "sensitivity_warning",
        ):
            assert getattr(stored[category], column) is None, f"{column} was padded"
            assert getattr(stored[second], column) is not None

        raw = repository.connection.execute(
            "SELECT top_3_stability, top_5_stability, maximum_score_delta, "
            "maximum_rank_displacement, sensitivity_warning FROM category_scores "
            "WHERE category = ?",
            (category,),
        ).fetchone()
        assert tuple(raw) == (None, None, None, None, None), (
            "the stored columns must be SQL NULL, not 0.0 or 0"
        )
        raw_populated = repository.connection.execute(
            "SELECT top_3_stability, maximum_rank_displacement, sensitivity_warning "
            "FROM category_scores WHERE category = ?",
            (second,),
        ).fetchone()
        assert tuple(raw_populated) == (1.0, 3, 1), (
            "a supplied diagnostic is stored as its own value"
        )
        assert stored[second].sensitivity_warning is True, "an INTEGER 1 reads back as True"

        # Fewer than k rankable categories is representable: the null stays null
        # through an upsert finalization too.
        finalized = _partial_category_score(
            top_3_stability=None,
            top_5_stability=None,
        )
        assert repository.upsert_category_scores([finalized]) == 1
        assert repository.get_category_scores(run_record.run_id)[0].top_3_stability is None


# ---------------------------------------------------------------------------
# LREQ-RPT-020 — the score columns cover the report read model
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-RPT-020")
def test_category_score_columns_cover_report_read_model(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Every field the primary report table shows is readable as the record."""
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    report_fields = (
        "discovered_population_count",
        "enriched_sample_count",
        "sample_is_census",
        "unique_enrichment_count",
        "sample_fraction",
        "sampling_basis",
        "overlap_category_count",
        "overlap_sample_percentage",
        "usable_demand_sample_count",
        "usable_recent_supply_sample_count",
        "usable_quality_sample_count",
        "demand_stratum_eligibility_coverage",
        "recent_supply_stratum_eligibility_coverage",
        "quality_stratum_eligibility_coverage",
        "evidence_grade",
        "rankability_status",
        "discovery_status",
        "top_3_stability",
        "top_5_stability",
        "maximum_score_delta",
        "maximum_rank_displacement",
        "sensitivity_warning",
    )
    assert all(field in TABLE_COLUMNS["category_scores"] for field in report_fields)

    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        repository.insert_sample_members([_sample_member()])
        score = _partial_category_score(
            overlap_sample_percentage=4.0,
            top_3_stability=1.0,
            top_5_stability=0.8,
            maximum_score_delta=0.125,
            maximum_rank_displacement=3,
            sensitivity_warning=False,
        )
        repository.insert_category_scores([score])
        stored = repository.get_category_scores(run_record.run_id)[0]
        assert stored == score
        for field in report_fields:
            assert getattr(stored, field) == getattr(score, field), (
                f"{field} drifted on the round trip"
            )

        # The sample-side half of the read model comes from sample_members.
        members = repository.get_sample_members(run_record.run_id, category)
        assert members == (_sample_member(),)
        assert members[0].sample_is_census is False
        assert members[0].overlap_category_count == 0

        # Page-view semantic status is a runs column, not a score column.
        assert "page_view_semantics_status" in TABLE_COLUMNS["runs"]
        assert repository.get_run(run_record.run_id).page_view_semantics_status == (
            PageViewSemanticsStatus.UNVALIDATED.value
        )
        assert "page_view_semantics_status" not in TABLE_COLUMNS["category_scores"]
        # The percent-shared-with-other-categories figure the report shows.
        assert stored.overlap_sample_percentage == 4.0


# ---------------------------------------------------------------------------
# LREQ-SMP-080 — the (run_id, category) primary key is enforced
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_category_scores_primary_key_enforced(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A duplicate score row fails; the explicit upsert path is what updates."""
    database = tmp_path / "niche_scout.sqlite3"
    first, second = fixtures.DEFAULT_CATEGORIES[:2]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        assert TABLE_PRIMARY_KEYS["category_scores"] == ("run_id", "category")

        score = _partial_category_score()
        repository.insert_category_scores([score])
        with pytest.raises(UniqueConstraintViolation) as duplicate:
            repository.insert_category_scores([score])
        assert "category_scores" in str(duplicate.value)
        assert score.category not in str(duplicate.value)

        # A second category is a different key.
        repository.insert_category_scores([_partial_category_score(category=second)])
        assert repository.count_sample_members(run_record.run_id) == 0
        assert len(repository.get_category_scores(run_record.run_id)) == 2

        # The upsert path is the only way to change an existing row.
        finalized = _partial_category_score(
            usable_demand_sample_count=99,
            score_state=ScoreState.AVAILABLE.value,
            market_opportunity_score=0.42,
        )
        assert repository.upsert_category_scores([finalized]) == 1
        stored = repository.get_category_scores(run_record.run_id)
        assert stored[0] == finalized
        assert stored[1].usable_demand_sample_count == score.usable_demand_sample_count, (
            "upserting one row leaves its sibling untouched"
        )
        assert len(stored) == 2, "an upsert cannot insert a sibling row"

        # A score row for an unknown run is a foreign-key violation.
        with pytest.raises(ForeignKeyConstraintViolation):
            repository.insert_category_scores([_partial_category_score(run_id="run-absent")])
        assert "category_scores" in str(
            pytest.raises(
                ForeignKeyConstraintViolation,
                repository.insert_category_scores,
                [_partial_category_score(run_id="run-absent-2")],
            ).value
        )


# ---------------------------------------------------------------------------
# LREQ-SMP-080, LREQ-EXT-090 — category isolation
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
@pytest.mark.lreq("LREQ-EXT-090")
def test_category_isolation_preserves_unrelated_observations(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """A failed category rolls back only its own block; siblings stay committed."""
    database = tmp_path / "niche_scout.sqlite3"
    first, second, third = fixtures.DEFAULT_CATEGORIES[:3]
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        committed = _raw_observation(
            observation_id="obs-committed", category=first, discovery_ordinal=1
        )
        with repository.category_transaction(run_record.run_id, first):
            repository.append_raw_discovery_observations([committed])
        assert repository.count_raw_discovery_observations(run_record.run_id, first) == 1

        # A failing category writes a batch prefix and then raises. Only that
        # category's group is unwound.
        def failing_records(category: str) -> Iterator[RawDiscoveryObservationRecord]:
            yield _raw_observation(
                observation_id="obs-second-1", category=category, discovery_ordinal=1
            )
            yield _raw_observation(
                observation_id="obs-second-2", category=category, discovery_ordinal=2
            )
            raise RuntimeError("the discovery adapter gave up mid-stream")

        with pytest.raises(RuntimeError):
            with repository.category_transaction(run_record.run_id, second):
                repository.append_raw_discovery_observations(
                    failing_records(second), batch_size=1
                )

        assert repository.count_raw_discovery_observations(run_record.run_id, second) == 0, (
            "the failed category's whole group is unwound"
        )
        assert tuple(
            repository.iter_raw_discovery_observations(run_record.run_id, first)
        ) == (committed,), "the sibling category is untouched"
        assert repository.get_run(run_record.run_id) == run_record, (
            "already-committed run rows survive"
        )

        # The instance is usable afterwards: the failure left no depth pinned
        # and no write lock held.
        assert not repository.in_category_transaction()
        assert not repository.connection.in_transaction, (
            "a failed category must not leave a transaction open"
        )
        with repository.category_transaction(run_record.run_id, third):
            repository.append_raw_discovery_observations(
                [
                    _raw_observation(
                        observation_id="obs-third", category=third, discovery_ordinal=1
                    )
                ]
            )
        assert repository.count_discovery_observations(run_record.run_id) == 2
        with repository.transaction():
            repository.update_run_status(
                run_record.run_id, RunStatus.COMPLETED.value, completed_at_utc=_iso(8)
            )
        assert repository.get_run(run_record.run_id).status == RunStatus.COMPLETED.value

        # A constraint failure inside a category block also isolates.
        duplicate = _raw_observation(
            observation_id="obs-committed", category=first, discovery_ordinal=9
        )
        with pytest.raises(UniqueConstraintViolation):
            with repository.category_transaction(run_record.run_id, first):
                repository.append_raw_discovery_observations(
                    [
                        _raw_observation(
                            observation_id="obs-fourth",
                            category=first,
                            discovery_ordinal=4,
                        ),
                        duplicate,
                    ],
                    batch_size=2,
                )
        assert repository.count_raw_discovery_observations(run_record.run_id, first) == 1
        assert repository.count_discovery_observations(run_record.run_id) == 2


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 — the runs provenance hash rejects an empty or whitespace value
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-090")
@pytest.mark.lreq("LREQ-RPT-020")
def test_category_failure_cause_column_round_trips_without_zero_substitution(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """The failure-cause text round-trips byte for byte; absent stays NULL.

    Hand-derived from ``interfaces/chunk-02.md`` §2.7/§2.9: a canonical cause
    string passed to ``set_category_status`` is stored exactly as given and
    read back unchanged; a row with no recorded cause reads back ``None``,
    never ``""`` and never ``"{}"``.
    """
    database = tmp_path / "niche_scout.sqlite3"
    category, second = fixtures.DEFAULT_CATEGORIES[:2]
    cause = json.dumps(
        {
            "attempt_count": 6,
            "failure_class": "transport_failure",
            "http_status": None,
            "page_index": 1,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        repository.set_category_status(
            run_record.run_id,
            category,
            DiscoveryStatus.REQUEST_FAILED.value,
            computed_at_utc=_iso(6),
            discovery_failure_cause_json=cause,
        )
        repository.set_category_status(
            run_record.run_id,
            second,
            DiscoveryStatus.COMPLETE.value,
            computed_at_utc=_iso(6),
        )
        stored = {
            row.category: row
            for row in repository.get_category_scores(run_record.run_id)
        }
        assert stored[category].discovery_failure_cause_json == cause, (
            "*_json columns are stored exactly as given, never re-serialized"
        )
        assert stored[category].discovery_failure_cause_json == json.dumps(
            json.loads(stored[category].discovery_failure_cause_json),
            sort_keys=True,
            separators=(",", ":"),
        )
        assert json.loads(cause)["http_status"] is None
        assert stored[second].discovery_failure_cause_json is None, (
            "a category with no cause stores NULL, never '' or '{}'"
        )


@pytest.mark.lreq("LREQ-EXT-090")
def test_set_category_status_default_leaves_stored_cause_unchanged(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """The default cause parameter cannot null a cause written earlier.

    Hand-derived from ``interfaces/chunk-02.md`` §2.7: ``discovery_failure_cause_json``
    defaults to ``None`` and, on the conflict path, leaves the stored column
    unchanged. A second ``set_category_status`` call without the keyword and an
    ``upsert_category_scores`` finalize both preserve the original text.
    """
    database = tmp_path / "niche_scout.sqlite3"
    category = fixtures.DEFAULT_CATEGORIES[0]
    cause = json.dumps(
        {
            "attempt_count": 2,
            "failure_class": "http_permanent",
            "http_status": 403,
            "page_index": 0,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with SqliteRepository(database) as repository:
        repository.insert_run(run_record)
        repository.set_category_status(
            run_record.run_id,
            category,
            DiscoveryStatus.REQUEST_FAILED.value,
            computed_at_utc=_iso(6),
            discovery_failure_cause_json=cause,
        )
        repository.set_category_status(
            run_record.run_id,
            category,
            DiscoveryStatus.REQUEST_FAILED.value,
            computed_at_utc=_iso(7),
        )
        after_default = repository.get_category_scores(run_record.run_id)[0]
        assert after_default.discovery_failure_cause_json == cause

        assert repository.upsert_category_scores([_partial_category_score()]) == 1
        after_upsert = repository.get_category_scores(run_record.run_id)[0]
        assert after_upsert.discovery_failure_cause_json == cause, (
            "the scoring-phase upsert must not null the discovery cause"
        )


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 — the runs provenance hash rejects an empty or whitespace value
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_runs_taxonomy_sha256_empty_is_rejected(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """An empty or whitespace ``taxonomy_sha256`` never persists.

    Dependency-map §7 assigns the unmet ``runs.taxonomy_sha256`` obligation to
    Chunk 10: the persistence layer rejects only ``None``, not ``""``, so an
    empty provenance hash would persist silently. The guard is additive and
    scoped to the ``runs`` table's non-nullable provenance strings; a valid
    64-character lowercase-hex value still round-trips unchanged.
    """
    database = tmp_path / "niche_scout.sqlite3"
    with SqliteRepository(database) as repository:
        for rejected_value in ("", "   ", "\t\n"):
            rejected = dataclasses.replace(run_record, taxonomy_sha256=rejected_value)
            with pytest.raises(InvalidRecordValueError) as error:
                repository.insert_run(rejected)
            # The message names the table and column only: never the value.
            # An empty needle is deliberately skipped (which is correct for
            # ``""``? No: the guard is on the stored value, and the message must
            # not echo a whitespace value either).
            message = str(error.value)
            assert "runs" in message
            assert "taxonomy_sha256" in message
            if rejected_value.strip():
                assert rejected_value not in message
            assert message.strip() == message, "the message is not the raw value"
            assert repository.get_run(run_record.run_id) is None, (
                "a rejected provenance hash writes nothing"
            )

        valid = dataclasses.replace(run_record, taxonomy_sha256="a1" * 32)
        repository.insert_run(valid)
        stored = repository.get_run(valid.run_id)
        assert stored is not None
        assert stored.taxonomy_sha256 == "a1" * 32
        assert len(stored.taxonomy_sha256) == 64
        assert stored.taxonomy_sha256 == stored.taxonomy_sha256.lower()
        assert repository.get_run(valid.run_id) == valid

        # The same guard covers the other provenance/identity string columns.
        for column in (
            "taxonomy_version",
            "endpoint_contract_version",
            "identity_mapping_rule_version",
            "sampling_rule_version",
        ):
            broken = dataclasses.replace(valid, **{column: "  "})
            with pytest.raises(InvalidRecordValueError):
                repository.insert_run(broken)

        # A nullable text column is untouched by the guard: supplying None is
        # not this error and must not be turned into one.
        assert stored.scoring_cutoff_utc is not None


# ---------------------------------------------------------------------------
# Chunk 30 — Repository.get_latest_run_id (LREQ-CLI-020, D-3)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-020")
def test_get_latest_run_id_selects_greatest_started_at(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Three distinct start instants -> the row with the greatest one.

    The comparison is on the decoded timezone-aware UTC value, not the stored
    TEXT, because ``datetime.isoformat()`` omits a zero fractional part. The
    fixed literals are ``…:05Z``, ``…:06Z``, and ``2024-12-31T23:59:59Z``.
    """
    repository = SqliteRepository(tmp_path / "latest.sqlite3")
    try:
        runs = (
            dataclasses.replace(
                run_record,
                run_id="run-mid",
                run_started_at_utc=datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            ),
            dataclasses.replace(
                run_record,
                run_id="run-late",
                run_started_at_utc=datetime(2025, 1, 2, 3, 4, 6, tzinfo=timezone.utc),
            ),
            dataclasses.replace(
                run_record,
                run_id="run-old",
                run_started_at_utc=datetime(
                    2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc
                ),
            ),
        )
        with repository.transaction():
            for run in runs:
                repository.insert_run(run)
        assert repository.get_latest_run_id() == "run-late"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-CLI-020")
def test_get_latest_run_id_tie_break_is_deterministic(
    tmp_path: Path, run_record: RunRecord
) -> None:
    """Equal start instants tie-break to the lexicographically smallest run_id."""
    repository = SqliteRepository(tmp_path / "tie.sqlite3")
    try:
        same_start = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with repository.transaction():
            repository.insert_run(
                dataclasses.replace(
                    run_record, run_id="b-run", run_started_at_utc=same_start
                )
            )
            repository.insert_run(
                dataclasses.replace(
                    run_record, run_id="a-run", run_started_at_utc=same_start
                )
            )
        assert repository.get_latest_run_id() == "a-run"
        # Stable across two calls (no dependence on row/set ordering).
        assert repository.get_latest_run_id() == "a-run"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-CLI-020")
def test_get_latest_run_id_none_when_no_runs(tmp_path: Path) -> None:
    """An empty ``runs`` table yields ``None`` (never a fabricated id)."""
    repository = SqliteRepository(tmp_path / "none.sqlite3")
    try:
        assert repository.get_latest_run_id() is None
    finally:
        repository.close()
