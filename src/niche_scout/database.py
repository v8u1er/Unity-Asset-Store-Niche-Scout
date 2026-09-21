"""SQLite schema specification and physical repository implementation.

Chunk 0 froze the persistence *contract*: the DDL strings below, the
``Repository`` protocol, and the ``SCHEMA_VERSION`` value. This module adds the
physical implementation behind that contract — connection lifecycle, pragmas,
schema initialization, streamed and batch insert paths, transactions and
savepoints, category isolation, status transitions, and the read/count surface.

Importing this module executes no DDL and no DML: the only import-time side
effect is the pre-existing :func:`_validate_specification` check.

Null, zero, invalid, and unavailable remain distinct states. No code path in
this module converts ``None``, a missing value, or an invalid value into ``0``,
``0.0``, ``""``, or ``False``; a failed page-view operation stays ``NULL`` and
zero is never an error sentinel. Error messages carry table and column names
only — never a record value, an identity string, a header, or a token.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Optional, Protocol, Sequence

from .models import (
    BreadthCompletenessStatus,
    BreadthSource,
    CategoryFilterValidationStatus,
    CategoryScoreRecord,
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
    ensure_utc,
)
from .sampling import CategorySamplingResult, RunSamplingResult, compute_overlap

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

_INDEXES: dict[str, str] = {
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

TABLE_INDEXES: dict[str, str] = dict(_INDEXES)


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


# --------------------------------------------------------------------------
# Exception hierarchy
# --------------------------------------------------------------------------


class DatabaseError(RuntimeError):
    """Base class for every persistence failure raised by this module."""


class RepositoryError(DatabaseError):
    """Raised when a repository method is called in an invalid lifecycle state."""


class ClosedRepositoryError(RepositoryError):
    """Raised when a method is called after close()."""


class SchemaVersionError(DatabaseError):
    """Raised when an existing database file's schema version cannot be used."""


class UniqueConstraintViolation(DatabaseError):
    """Raised when an INSERT/upsert would create a duplicate logical row."""


class ForeignKeyConstraintViolation(DatabaseError):
    """Raised when a row references a run_id that does not exist."""


class InvalidRecordValueError(DatabaseError):
    """Raised when a record field cannot be encoded for a constrained column."""


# --------------------------------------------------------------------------
# Internal encoding helpers
# --------------------------------------------------------------------------

_SCHEMA_METADATA_TABLE = "schema_metadata"
_CREATE_SCHEMA_METADATA = (
    "CREATE TABLE IF NOT EXISTS schema_metadata ("
    "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
)

# Only these four raw-observation columns are writable after discovery.
_RAW_IDENTITY_COLUMNS = (
    "asset_identity_key",
    "stratum_index",
    "is_duplicate",
    "duplicate_of_observation_id",
)

# Index name -> (table, columns), mirroring the originating CREATE INDEX text.
_INDEX_TARGETS: dict[str, tuple[str, tuple[str, ...]]] = {}
_INDEX_ON_PATTERN = re.compile(
    r"ON\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)"
)
for _index_name, _index_statement in TABLE_INDEXES.items():
    _match = _INDEX_ON_PATTERN.search(_index_statement)
    if _match is None:
        raise RuntimeError(f"{_index_name}: index statement does not name a table")
    _INDEX_TARGETS[_index_name] = (
        _match.group(1),
        tuple(
            column.strip()
            for column in _match.group(2).split(",")
            if column.strip()
        ),
    )

_SAVEPOINT_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Per-column enum allow-lists. Every status/state column named in the chunk's
# invariants is constrained to exactly the frozen interface values.
_ENUM_COLUMNS: dict[tuple[str, str], tuple[str, ...]] = {
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
    ("category_scores", "evidence_grade"): tuple(
        item.value for item in EvidenceGrade
    ),
    ("category_scores", "rankability_status"): tuple(
        item.value for item in RankabilityStatus
    ),
}

# Discovered per column by inspecting the frozen DDL: INTEGER columns holding
# booleans and INTEGER columns that may be NULL. Nothing here is assumed.
_INTEGER_COLUMNS: dict[str, frozenset[str]] = {}
_NULLABLE_COLUMNS: dict[str, frozenset[str]] = {}
for _table_name, _statement in CREATE_TABLE_STATEMENTS.items():
    _integers: set[str] = set()
    _nullables: set[str] = set()
    for _line in _statement.splitlines():
        _parts = _line.strip().rstrip(",").split()
        if len(_parts) < 2 or not _parts[0].isidentifier():
            continue
        if _parts[1] == "INTEGER":
            _integers.add(_parts[0])
        if "NOT NULL" not in _line:
            _nullables.add(_parts[0])
    _INTEGER_COLUMNS[_table_name] = frozenset(_integers)
    _NULLABLE_COLUMNS[_table_name] = frozenset(_nullables)

_BOOLEAN_COLUMNS: dict[str, tuple[str, ...]] = {
    "raw_discovery_observations": ("is_duplicate",),
    "sample_members": ("sample_is_census", "preflight_selected"),
    "enrichment_observations": ("id_mapping_mismatch",),
    "category_scores": (
        "discovery_filter_verified",
        "sample_is_census",
        "discovery_bounded_by_verified_total",
        "sensitivity_warning",
    ),
}

# UTC datetime columns: declared TEXT and named as timestamps.
_DATETIME_COLUMNS: dict[str, tuple[str, ...]] = {
    table: tuple(name for name in columns if name.endswith("_utc"))
    for table, columns in TABLE_COLUMNS.items()
}

# Columns excluded from a plain-INSERT statement because the DDL supplies a
# default that is known before scoring. Every entry is a concrete value, never
# a null marker: this table exists to fill DDL-declared ``NOT NULL`` columns
# with a pre-scoring default, so a sentinel meaning "write NULL" would be a lie
# about the column being nullable. Encoding the distinction between null, zero,
# and unavailable is the row codec's job (``_encode_column``), which leaves a
# nullable column's ``None`` to round-trip as ``NULL``.
_IMPLICIT_NOT_NULL_DEFAULTS: dict[str, dict[str, object]] = {
    "category_scores": {
        "discovery_filter_verified": 0,
        "discovery_unresolved_identity_count": 0,
        "discovery_conflict_count": 0,
        "discovery_duplicate_count": 0,
        "discovered_population_count": 0,
        "enriched_sample_count": 0,
        "sample_is_census": 0,
        "sampling_basis": SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE.value,
        "unique_enrichment_count": 0,
        "overlap_category_count": 0,
        "usable_demand_sample_count": 0,
        "usable_recent_supply_sample_count": 0,
        "usable_quality_sample_count": 0,
        "breadth_source": BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT.value,
        "breadth_completeness_status": BreadthCompletenessStatus.COMPLETE.value,
        "discovery_bounded_by_verified_total": 0,
        "demand_stratum_eligibility_coverage": 0.0,
        "recent_supply_stratum_eligibility_coverage": 0.0,
        "quality_stratum_eligibility_coverage": 0.0,
        "stratum_statistics_json": "[]",
        "score_state": ScoreState.UNAVAILABLE.value,
        "evidence_grade": EvidenceGrade.INSUFFICIENT.value,
        "rankability_status": RankabilityStatus.NOT_RANKABLE.value,
        "missing_components_json": "[]",
        "warnings_json": "[]",
        "reference_size": 0,
        "reference_usable_counts_json": "{}",
"ranking_sensitivity_json": "{}",
    },
}


def _bindable(table: str) -> tuple[str, ...]:
    """Columns a plain INSERT may bind, in DDL order.

    A ``NOT NULL`` column with an implicit default is *bindable when the record
    supplies a value and defaulted only when the record supplies ``None``*,
    which is the encoding contract of section 5.9 (lines 760-769): an optional
    field is either SQL ``NULL`` and read back as ``None``, or the value the
    record actually carried -- "Never as ``0``, ``0.0``, ``\"\", or ``False``."
    Excluding a column merely because it appears in the default table would
    report a supplied ``72`` back as ``0``, which is exactly that violation,
    and the frozen DDL declares no ``DEFAULT`` clause, so the default table is
    not a licence to overwrite. A nullable column is never excluded.
    """
    implicit = _IMPLICIT_NOT_NULL_DEFAULTS.get(table, {})
    nullable = _NULLABLE_COLUMNS[table]
    return tuple(
        column
        for column in TABLE_COLUMNS[table]
        if column in nullable or column not in implicit
    )


def _record_columns_with_non_none(
    table: str, record: object
) -> tuple[str, ...]:
    """Columns of ``table`` for which the record supplies a non-``None`` value.

    This is the per-record form of :func:`_columns_with_non_none`, used by the
    plain-INSERT path: the record's own values win for every ``NOT NULL``
    column it populates, and :data:`_IMPLICIT_NOT_NULL_DEFAULTS` fills only the
    columns it left as ``None``.
    """
    return tuple(
        column
        for column in TABLE_COLUMNS[table]
        if getattr(record, column, None) is not None
    )


def _default_for(table: str, column: str) -> object:
    return _IMPLICIT_NOT_NULL_DEFAULTS[table][column]


def _implicit_default(table: str, column: str) -> object:
    """Default for a column the record left ``None``.

    A table with no entry in :data:`_IMPLICIT_NOT_NULL_DEFAULTS` (``runs``,
    ``raw_discovery_observations``, ``sample_members``,
    ``enrichment_observations``) has no ``NOT NULL`` column lacking a value, so
    ``None`` here can only mean a column the DDL declares nullable: the
    correct value is SQL ``NULL``, which :func:`_encode_column` already
    produces for ``None``. Returning ``None`` therefore leaves such a column
    exactly as supplied rather than inventing a substitute.
    """
    return _IMPLICIT_NOT_NULL_DEFAULTS.get(table, {}).get(column)


def _validate_enum(table: str, column: str, value: object) -> None:
    allowed = _ENUM_COLUMNS.get((table, column))
    if allowed is None or value is None:
        return
    if value not in allowed:
        raise InvalidRecordValueError(
            f"{table}.{column}: value outside the allowed set "
            f"({', '.join(allowed)})"
        )


def _columns_with_non_none(record: object) -> tuple[str, ...]:
    return tuple(
        name for name in TABLE_COLUMNS[_table_of(record)] if getattr(record, name) is not None
    )


def _table_of(record: object) -> str:
    for table, row_type in _ROW_TYPES.items():
        if isinstance(record, row_type):
            return table
    for table, primary_key in TABLE_PRIMARY_KEYS.items():
        if all(hasattr(record, column) for column in TABLE_COLUMNS[table]):
            return table
    raise InvalidRecordValueError("record type is not a persisted row type")


def _validate_required_columns(record: object) -> None:
    """Reject a ``None`` in a column whose DDL form has no nullable fallback."""
    table = _table_of(record)
    for column in _IMPLICIT_NOT_NULL_DEFAULTS.get(table, {}):
        value = getattr(record, column, None)
        if value is None:
            continue
        if (
            column in _INTEGER_COLUMNS[table]
            and column not in _BOOLEAN_COLUMNS.get(table, ())
            and not isinstance(value, int)
        ):
            raise InvalidRecordValueError(
                f"{table}.{column}: value must be an integer"
            )
        if column in _REAL_COLUMNS.get(table, ()) and not isinstance(
            value, (int, float)
        ):
            raise InvalidRecordValueError(f"{table}.{column}: value must be numeric")


_REAL_COLUMNS: dict[str, tuple[str, ...]] = {
    table: tuple(
        line.strip().rstrip(",").split()[0]
        for line in CREATE_TABLE_STATEMENTS[table].splitlines()
        if line.strip().rstrip(",").split()[1:2] == ["REAL"]
    )
    for table in CREATE_TABLE_STATEMENTS
}


def _encode_column(table: str, column: str, value: object) -> object:
    """Encode a record value for its SQLite column.

    ``None`` always encodes to ``NULL``; it is never replaced by a zero-like
    value.
    """
    if value is None:
        return None
    _validate_enum(table, column, value)
    if column in _DATETIME_COLUMNS[table]:
        if not isinstance(value, datetime):
            raise InvalidRecordValueError(
                f"{table}.{column}: value must be a datetime"
            )
        try:
            return ensure_utc(value).isoformat()
        except ValueError as exc:
            raise InvalidRecordValueError(
                f"{table}.{column}: value must be timezone-aware UTC"
            ) from exc
    if column in _BOOLEAN_COLUMNS.get(table, ()):
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int) and value in (0, 1):
            return value
        raise InvalidRecordValueError(
            f"{table}.{column}: value must be a boolean"
        )
    if value is True or value is False:
        raise InvalidRecordValueError(
            f"{table}.{column}: value must not be a boolean"
        )
    if column in _INTEGER_COLUMNS[table]:
        if not isinstance(value, int):
            raise InvalidRecordValueError(
                f"{table}.{column}: value must be an integer"
            )
        return value
    if column in _REAL_COLUMNS.get(table, ()):
        if not isinstance(value, (int, float)):
            raise InvalidRecordValueError(f"{table}.{column}: value must be numeric")
        return float(value)
    if not isinstance(value, str):
        raise InvalidRecordValueError(f"{table}.{column}: value must be text")
    return value


def _decode_column(table: str, column: str, value: object) -> object:
    if value is None:
        return None
    if column in _DATETIME_COLUMNS[table]:
        try:
            return ensure_utc(datetime.fromisoformat(str(value)))
        except ValueError as exc:
            raise DatabaseError(
                f"{table}.{column}: stored timestamp is not timezone-aware UTC"
            ) from exc
    if column in _BOOLEAN_COLUMNS.get(table, ()):
        return bool(value)
    return value


def _encode_row(record: object, columns: Sequence[str]) -> tuple[object, ...]:
    table = _table_of(record)
    return tuple(_encode_column(table, column, getattr(record, column)) for column in columns)


def _project_row(table: str, columns: Sequence[str], values: Mapping[str, object]):
    payload = {
        column: _decode_column(table, column, values[column])
        for column in columns
        if column in values
    }
    return _ROW_TYPES[table](**payload)


def _placeholder_columns(
    table: str, columns: Sequence[str]
) -> tuple[tuple[str, ...], tuple[tuple[object, ...], ...]]:
    """Return bindable columns plus a row of pre-scoring defaults for the rest.

    The omitted columns are the ``NOT NULL`` ones the module fills itself; the
    frozen DDL declares no ``DEFAULT`` clause, so :data:`_IMPLICIT_NOT_NULL_DEFAULTS`
    is the only source of their value.
    """
    implicit = _IMPLICIT_NOT_NULL_DEFAULTS.get(table, {})
    if not implicit:
        return tuple(columns), ()
    bindable = tuple(column for column in columns if column in _bindable(table))
    omitted = tuple(column for column in columns if column not in bindable)
    return bindable, tuple((_default_for(table, column),) for column in omitted)


# --------------------------------------------------------------------------
# Physical repository
# --------------------------------------------------------------------------


class _Untouched:
    """Sentinel for "no change requested" in partial update APIs."""

    __slots__ = ()


_UNTOUCHED = _Untouched()


class SqliteRepository:
    """Single-thread, single-connection SQLite implementation of ``Repository``.

    The instance reuses one :class:`sqlite3.Connection` for every method. It is
    not thread-safe and provides no sharing or pooling guarantee beyond
    savepoint nesting.
    """

    def __init__(
        self,
        db_path: "Path | str",
        *,
        initialize: bool = True,
        busy_timeout_ms: int = 5000,
        synchronous: str = "NORMAL",
        create_parent_directory: bool = True,
    ) -> None:
        self._path = Path(db_path)
        self._busy_timeout_ms = busy_timeout_ms
        self._synchronous = synchronous
        self._closed = False
        self._outermost_transaction_depth = 0
        self._category_stack: list[tuple[str, str]] = []
        self._batch_counter = 0
        if create_parent_directory:
            parent = self._path.parent
            if str(parent):
                parent.mkdir(parents=True, exist_ok=True)
        # Transaction regime: pysqlite's default ``isolation_level=""``, which
        # opens an implicit ``BEGIN`` before the first DML of a unit of work and
        # commits or rolls back only when this module asks. It is the default
        # that is used here, with no explicit ``isolation_level`` argument.
        #
        # WITHDRAWN CLAIM: an earlier revision of this comment asserted that
        # autocommit and this default "were measured to behave identically" for
        # explicit ``BEGIN``..``COMMIT``, ``ROLLBACK``, ``RELEASE``/``ROLLBACK
        # TO`` and foreign-key enforcement. That measurement was never
        # performed and, for the first two items, could not have succeeded: they
        # are exactly what differs between the two regimes (a ``rollback()`` in
        # autocommit discards nothing, because the row was already committed, so
        # it violates this module's own ``transaction()`` contract). The claim
        # is withdrawn.
        #
        # Why the default and not ``isolation_level=None``: the pragmas applied
        # below are executed before any implicit ``BEGIN`` exists (see
        # ``_apply_pragmas``), so autocommit is not needed to make them take
        # effect, while leaving the default in place keeps ``transaction()``'s
        # documented rollback-on-error contract real rather than nominal. This
        # module owns every boundary explicitly: ``transaction()`` issues the
        # single ``commit()``/``rollback()``, and ``category_transaction()`` and
        # the streamed batch flush use savepoints, whose semantics are identical
        # in both regimes (``RELEASE`` of the outermost savepoint ends the
        # implicit transaction; savepoint nesting is not capped).
        self._connection = sqlite3.connect(str(self._path))
        # Name-addressed row access. The read APIs reconstruct records by
        # column name, and the default row factory yields positional tuples, so
        # every projection would otherwise build an empty mapping and fail on a
        # missing field. The frozen DDL declares no duplicate column names
        # within a table, so a name-keyed mapping is unambiguous.
        self._connection.row_factory = sqlite3.Row
        self._apply_pragmas()
        self._schema_version = SCHEMA_VERSION
        if initialize:
            self.initialize_schema()

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def connect(
        cls,
        db_path: "Path | str",
        *,
        initialize: bool = True,
        busy_timeout_ms: int = 5000,
        synchronous: str = "NORMAL",
        create_parent_directory: bool = True,
    ) -> "SqliteRepository":
        """Construct a repository; identical to calling the constructor."""
        return cls(
            db_path,
            initialize=initialize,
            busy_timeout_ms=busy_timeout_ms,
            synchronous=synchronous,
            create_parent_directory=create_parent_directory,
        )

    @property
    def db_path(self) -> Path:
        return self._path

    @property
    def schema_version(self) -> str:
        return self._schema_version

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def connection(self) -> sqlite3.Connection:
        """Escape hatch for read-only diagnostics; never for writes by peers."""
        self._check_open()
        return self._connection

    def close(self) -> None:
        """Close the connection. Idempotent; a second call is a no-op."""
        if self._closed:
            return
        self._closed = True
        self._category_stack.clear()
        self._outermost_transaction_depth = 0
        try:
            self._connection.close()
        except sqlite3.Error as exc:
            raise DatabaseError("failed to close the database connection") from exc

    def __enter__(self) -> "SqliteRepository":
        self._check_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- pragmas and schema ------------------------------------------------

    def _apply_pragmas(self) -> None:
        """Apply and verify the four pragmas, in the order its plan fixes.

        Every setting is verified by the **read** form of the pragma, never by
        trusting a setter's return row, because a setter's return value says
        nothing about the state the *connection* ended up in:

        - ``foreign_keys = ON`` returns no row at all, so an assertion on its
          result row would be an assertion about a missing value.
        - ``journal_mode = WAL`` returns the mode the engine *computed* for this
          connection, which the frozen plan licenses as a local implementation
          choice, so the assertion belongs on what a later read reports.
        - ``synchronous = NORMAL`` returns no row, and its read form reports a
          small integer (``NORMAL`` is stored as ``1``), so an assertion
          comparing that integer to the configured *name* compares two
          different quantities.

        The writes are issued on a connection that is not inside a transaction,
        which is what makes them take effect: SQLite silently refuses a
        ``foreign_keys`` change made inside one, and ``journal_mode = WAL`` is a
        no-op inside one. ``__init__`` calls this before any statement that
        could open an implicit transaction, and ``PRAGMA journal_mode`` does not
        open one, so the state this method requires holds by construction.
        """
        connection = self._connection
        if connection.in_transaction:
            raise DatabaseError("pragmas cannot be applied inside a transaction")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(_busy_timeout_statement(self._busy_timeout_ms))
        connection.execute(
            f"PRAGMA synchronous = {_synchronous_statement(self._synchronous)}"
        )
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()
        if enabled is None or int(enabled[0]) != 1:
            raise DatabaseError("PRAGMA foreign_keys could not be enabled")
        mode = connection.execute("PRAGMA journal_mode").fetchone()
        if mode is None or str(mode[0]).lower() != WAL_JOURNAL_MODE:
            raise DatabaseError("PRAGMA journal_mode could not be set to WAL")
        timeout = connection.execute("PRAGMA busy_timeout").fetchone()
        if timeout is None or int(timeout[0]) != int(self._busy_timeout_ms):
            raise DatabaseError("PRAGMA busy_timeout could not be applied")
        # ``synchronous`` is stored as an integer level, so the configured name
        # is compared against the name that level denotes, not against the
        # integer itself.
        level = connection.execute("PRAGMA synchronous").fetchone()
        if level is None or _synchronous_level(int(level[0])) != _synchronous_statement(
            self._synchronous
        ):
            raise DatabaseError("PRAGMA synchronous could not be applied")

    def initialize_schema(self, *, check_version: bool = True) -> str:
        """Create the frozen schema if absent and return ``SCHEMA_VERSION``."""
        self._check_open()
        foreign_keys = self._connection.execute("PRAGMA foreign_keys").fetchone()
        if foreign_keys is None or int(foreign_keys[0]) != 1:
            raise DatabaseError("refusing to initialize schema with foreign_keys off")
        self._connection.execute(_CREATE_SCHEMA_METADATA)
        stored = self._connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if stored is not None and str(stored[0]) != SCHEMA_VERSION:
            if check_version:
                raise SchemaVersionError(
                    "schema_metadata.schema_version does not match SCHEMA_VERSION"
                )
        for statement in DDL_STATEMENTS:
            self._connection.execute(_idempotent(statement))
        applied_at = datetime.now(timezone.utc).isoformat()
        self._connection.execute(
            "INSERT INTO schema_metadata (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (SCHEMA_VERSION,),
        )
        self._connection.execute(
            "INSERT INTO schema_metadata (key, value) VALUES ('applied_at_utc', ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (applied_at,),
        )
        self._connection.commit()
        self._schema_version = SCHEMA_VERSION
        return SCHEMA_VERSION

    # -- transactions and savepoints ---------------------------------------

    @contextmanager
    def transaction(self) -> Iterator["SqliteRepository"]:
        """Outermost transaction. Commits on clean exit, rolls back on error."""
        self._check_open()
        if self._outermost_transaction_depth:
            raise RepositoryError("a transaction is already open on this instance")
        self._check_not_in_category_block("transaction")
        # An explicit ``BEGIN`` rather than waiting for pysqlite's implicit one,
        # so that this block's boundary is real from the moment it is entered.
        # Without it, DML performed by a *previous*, unwrapped method call can
        # already have opened an implicit transaction, and this block's
        # ``commit()`` on clean exit would then also commit that earlier work —
        # work this block never saw and must not adopt. ``BEGIN`` makes the
        # transaction this block commits exactly the one it opened.
        if not self._connection.in_transaction:
            self._connection.execute("BEGIN")
        self._outermost_transaction_depth = 1
        try:
            yield self
        except BaseException:
            self._outermost_transaction_depth = 0
            self._connection.rollback()
            raise
        else:
            self._outermost_transaction_depth = 0
            self._connection.commit()
        finally:
            # DML that raises below the Python layer (a cancelled statement in
            # another thread, an interrupt) can leave the implicit transaction
            # open after the branch above has already reported the outcome, and
            # an open transaction here would make every later call on this
            # instance raise "a transaction is already open". This block runs
            # after the commit/rollback above and cannot see a clean exit with
            # work still pending.
            if self._connection.in_transaction:
                self._connection.rollback()

    @contextmanager
    def savepoint(self, name: str) -> Iterator["SqliteRepository"]:
        """Nested ``SAVEPOINT <name>``; ``RELEASE`` or ``ROLLBACK TO``."""
        self._check_open()
        _validate_savepoint_name(name)
        # Ownership is read from the module's depth counter, never from
        # ``in_transaction``. A bare ``SAVEPOINT`` on a fresh connection sets
        # ``in_transaction`` true, so "was I already in a transaction" is true
        # both for a savepoint nested inside a caller's transaction and for one
        # that is the database's outermost; only the first belongs to a caller
        # whose boundary this block must leave alone. Ownership is therefore
        # taken from the counter ``transaction()`` maintains, which is the only
        # place an enclosing boundary this block must not commit can come from.
        # What settles the commit is the unconditional ``RELEASE`` below:
        # releasing the outermost savepoint commits its transaction, and the
        # ``_settle_own_transaction`` call in the clean-exit branch covers the
        # remaining case, in which it was nested and commits nothing.
        owns_outer_transaction = self._transaction_depth() == 0
        # A block that owns the boundary opens a real ``BEGIN``, so the
        # savepoint below is nested inside a transaction this call opened and
        # the ``RELEASE`` that ends it commits this block's rows. Without the
        # explicit ``BEGIN``, a plain statement issued before this block (any
        # unwrapped DML method) would make the savepoint nested, the release
        # would commit nothing, and this block's rows would sit pending until
        # an unrelated later ``transaction()`` happened to commit them.
        if owns_outer_transaction:
            self._outermost_transaction_depth = 1
            if not self._connection.in_transaction:
                self._connection.execute("BEGIN")
        self._connection.execute(f"SAVEPOINT {name}")
        try:
            yield self
        except BaseException:
            self._connection.execute(f"ROLLBACK TO {name}")
            self._release_once(name)
            if owns_outer_transaction:
                # ``ROLLBACK TO`` unwinds the savepoint but leaves the
                # transaction this block opened still open, holding a write
                # lock and its partial work. Only this block can end it.
                self._connection.rollback()
            raise
        else:
            self._release_once(name)
            self._settle_own_transaction(owns_outer_transaction)
        finally:
            if owns_outer_transaction:
                self._outermost_transaction_depth = 0

    def _settle_own_transaction(self, owns_outer_transaction: bool) -> None:
        """Commit a transaction this call opened; never one a peer owns.

        Written work reaches disk only through ``commit()``. A savepoint block
        that turned out to be nested inside a transaction someone else opened
        commits nothing by releasing, which is correct: that transaction belongs
        to the enclosing ``transaction()`` and is committed or rolled back by it.
        But a block that opened the transaction itself has no enclosing owner to
        do that, so releasing its savepoint would leave the rows it wrote
        pending forever — invisible to a second connection and lost on close.
        This call commits only in that case, which is exactly the state it set.
        """
        if owns_outer_transaction and self._connection.in_transaction:
            self._connection.commit()

    @contextmanager
    def category_transaction(
        self, run_id: str, category: str
    ) -> Iterator["SqliteRepository"]:
        """Category-isolated unit of work.

        A failure inside the block unwinds only that category's savepoint;
        sibling categories and already-committed run rows stay intact.
        """
        self._check_open()
        if self.in_category_transaction():
            raise RepositoryError("a category transaction is already active")
        # A category block that has to own the outermost transaction records
        # that it did so, so the ``finally`` below can undo exactly what this
        # call set. Resetting unconditionally would clear a depth that an
        # enclosing ``transaction()`` owns and destroy its commit.
        #
        # "Owns the outermost transaction" is decided by the depth counter this
        # module maintains, not by ``in_transaction``: pysqlite's default regime
        # opens an implicit transaction before the first DML of a *method* call
        # too, so a plainly-called ``insert_run`` leaves ``in_transaction`` true
        # with no ``transaction()`` anywhere. Only ``transaction()`` sets the
        # depth counter, so it is the only thing that can claim ownership of the
        # transaction this block must leave alone.
        owns_outer_transaction = self._transaction_depth() == 0
        if owns_outer_transaction:
            self._outermost_transaction_depth = 1
        name = _savepoint_name(run_id, category)
        # A block that has to own the transaction opens a real ``BEGIN`` rather
        # than riding on an implicit transaction some earlier, unwrapped method
        # call may have left pending. This block then owns exactly one
        # transaction, so ``_settle_own_transaction`` commits exactly that one
        # and the failure path rolls exactly that one back, without adopting or
        # stranding a peer's work and without leaving a write lock behind.
        opened_transaction = owns_outer_transaction and not self._connection.in_transaction
        if opened_transaction:
            self._connection.execute("BEGIN")
        self._connection.execute(f"SAVEPOINT {name}")
        self._category_stack.append((run_id, category, name))
        try:
            yield self
        except BaseException:
            self._connection.execute(f"ROLLBACK TO {name}")
            self._release_once(name)
            if owns_outer_transaction:
                # Undo the whole transaction, not just the savepoint: the
                # savepoint's ``ROLLBACK TO`` leaves the transaction open, so
                # without this the failing category would hold a write lock and
                # leave its partial work pending for whoever commits next.
                self._connection.rollback()
            raise
        else:
            self._release_once(name)
            # Releasing a savepoint commits nothing when it was nested inside a
            # transaction someone else opened, so this call cannot leave rows it
            # is responsible for in limbo: the ``finally`` below hands any
            # transaction this call opened back to a committed state.
            self._settle_own_transaction(owns_outer_transaction)
        finally:
            self._category_stack.pop()
            # Without this reset a category block that raised would leave the
            # depth pinned at 1, and every later ``transaction()`` on this
            # instance would raise "a transaction is already open" forever.
            if owns_outer_transaction:
                self._outermost_transaction_depth = 0

    def in_category_transaction(self) -> bool:
        """True while inside an active ``category_transaction`` block."""
        return bool(self._category_stack)

    # -- run rows ----------------------------------------------------------

    def insert_run(self, run: RunRecord) -> None:
        """Insert one run row. A duplicate ``run_id`` is a violation."""
        self._check_open()
        self._insert_rows("runs", (run,))

    def update_run_status(
        self, run_id: str, status: str, completed_at_utc: Optional[datetime] = None
    ) -> None:
        """Transition a run's status; ``None`` leaves ``completed_at_utc`` alone."""
        self._check_open()
        _validate_enum("runs", "status", status)
        assignments = ["status = ?"]
        values: list[object] = [status]
        if completed_at_utc is not None:
            assignments.append("completed_at_utc = ?")
            values.append(
                _encode_column("runs", "completed_at_utc", completed_at_utc)
            )
        values.append(run_id)
        cursor = self._connection.execute(
            f"UPDATE runs SET {', '.join(assignments)} WHERE run_id = ?",
            tuple(values),
        )
        if cursor.rowcount == 0:
            raise KeyError(run_id)

    def update_run_preflight(
        self,
        run_id: str,
        *,
        identity_preflight_status: Optional[str] = None,
        identity_preflight_summary_json: Optional[str] = None,
        graphql_operation_correlation_mode: Optional[str] = None,
        page_view_semantics_status: Optional[str] = None,
    ) -> None:
        """Write only the preflight/correlation/semantic fields that are not None."""
        self._check_open()
        candidates = {
            "identity_preflight_status": identity_preflight_status,
            "identity_preflight_summary_json": identity_preflight_summary_json,
            "graphql_operation_correlation_mode": graphql_operation_correlation_mode,
            "page_view_semantics_status": page_view_semantics_status,
        }
        assignments: list[str] = []
        values: list[object] = []
        for column, value in candidates.items():
            if value is None:
                continue
            _validate_enum("runs", column, value)
            assignments.append(f"{column} = ?")
            values.append(_encode_column("runs", column, value))
        if not assignments:
            return
        values.append(run_id)
        cursor = self._connection.execute(
            f"UPDATE runs SET {', '.join(assignments)} WHERE run_id = ?",
            tuple(values),
        )
        if cursor.rowcount == 0:
            raise KeyError(run_id)

    def set_category_status(
        self,
        run_id: str,
        category: str,
        discovery_status: str,
        *,
        computed_at_utc: datetime | None = None,
    ) -> None:
        """Upsert one ``(run_id, category)`` discovery status into ``category_scores``.

        Creates the ``category_scores`` row on first write if it does not exist
        yet, because discovery precedes scoring and the row is populated
        incrementally over the run's lifetime.

        ``computed_at_utc`` is required, not inferred: the frozen
        :class:`~niche_scout.models.CategoryScoreRecord` declares the field as a
        non-optional ``datetime``, and this module never reads the system clock,
        so a caller-supplied value is the only way a written row can be
        reconstructed. A ``None`` therefore raises
        :class:`InvalidRecordValueError` instead of inventing a timestamp, and
        no row is written. The error message carries table and column names
        only — never a record value, a header, or an identity string.

        Because the value is always supplied, a conflicting
        ``(run_id, category)`` update always assigns it; there is no
        update-without-timestamp path.
        """
        self._check_open()
        _validate_enum("category_scores", "discovery_status", discovery_status)
        if computed_at_utc is None:
            raise InvalidRecordValueError(
                "category_scores.computed_at_utc: value is required and is not "
                "read from the system clock"
            )
        encoded_computed_at = _encode_column(
            "category_scores", "computed_at_utc", computed_at_utc
        )
        columns = tuple(
            column
            for column in _bindable("category_scores")
            if column
            in {"run_id", "category", "discovery_status", "computed_at_utc"}
        )
        update_columns = tuple(
            column for column in columns if column not in ("run_id", "category")
        )
        values = (run_id, category, discovery_status, encoded_computed_at)
        assignments = ", ".join(
            f"{column} = excluded.{column}" for column in update_columns
        )
        # The remaining ``NOT NULL`` columns are omitted so the DDL default
        # applies. The frozen DDL declares no ``DEFAULT`` clause, so each of
        # them is written explicitly from the module's pre-scoring default
        # table, exactly as the plain-insert path does.
        omitted = _insert_omitted_columns("category_scores")
        self._connection.execute(
            f"INSERT INTO category_scores ({', '.join(columns + omitted)}) "
            f"VALUES ({', '.join('?' for _ in columns + omitted)}) "
            f"ON CONFLICT (run_id, category) DO UPDATE SET {assignments}",
            tuple(values) + tuple(_default_for("category_scores", column) for column in omitted),
        )

    # -- raw discovery observations ----------------------------------------

    def insert_raw_discovery_observations(
        self, observations: Sequence[RawDiscoveryObservationRecord]
    ) -> None:
        """Batch convenience for the frozen protocol; same precondition as append."""
        self.append_raw_discovery_observations(
            observations, batch_size=max(1, len(observations))
        )

    def append_raw_discovery_observations(
        self,
        observations: "Iterable[RawDiscoveryObservationRecord]",
        *,
        batch_size: int = 500,
    ) -> int:
        """Stream observations into the active category transaction.

        Consumes the iterable incrementally, at most ``batch_size`` records at a
        time. Batches are written with a plain ``executemany``, one statement per
        record; the rollback boundary a mid-stream failure needs is the
        enclosing ``category_transaction``'s savepoint, which covers every batch
        prefix this call has already written for that category. See
        ``_flush_raw_batch`` for why no per-batch savepoint is opened here.
        """
        self._check_open()
        if isinstance(batch_size, bool) or not isinstance(batch_size, int):
            raise ValueError("batch_size must be an integer >= 1")
        if batch_size < 1:
            raise ValueError("batch_size must be an integer >= 1")
        if not self.in_category_transaction():
            raise RepositoryError(
                "raw observation writes require an active category_transaction: "
                "category isolation is the caller's declaration, so neither "
                "batch_size nor the observations may be read outside one"
            )
        columns = tuple(TABLE_COLUMNS["raw_discovery_observations"])
        placeholders = ", ".join("?" for _ in columns)
        statement = (
            f"INSERT INTO raw_discovery_observations ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        written = 0
        batch: list[tuple[object, ...]] = []
        try:
            for record in observations:
                batch.append(_encode_row(record, columns))
                if len(batch) >= batch_size:
                    self._flush_raw_batch(statement, batch, written)
                    written += len(batch)
                    batch.clear()
            if batch:
                self._flush_raw_batch(statement, batch, written)
                written += len(batch)
        except sqlite3.IntegrityError as exc:
            raise _integrity_error(
                "raw_discovery_observations", exc, written
            ) from None
        except sqlite3.Error as exc:
            # The platform silently rolls back *all* pending statements here, so
            # the caller's category transaction has to be the thing that decides
            # what survives. It rolls back before this wrapper turns the failure
            # into the published contract, and its rollback covers the released
            # prefix that ``_flush_raw_batch`` cannot.
            raise _run_batch_failure(len(batch), written) from exc
        return written

    def _flush_raw_batch(
        self, statement: str, batch: list[tuple[object, ...]], written: int
    ) -> None:
        """Write one batch inside the enclosing category savepoint.

        This deliberately opens no ``SAVEPOINT`` of its own. A per-batch
        savepoint would be released as soon as the batch succeeded, which is the
        wrong boundary twice over: a prefix of batches that were already
        released cannot be rolled back when a later batch fails, and a release
        inside a block that must roll back leaves the partial batch behind. The
        enclosing ``category_transaction``'s savepoint is the only boundary that
        undoes an already-written prefix, so the batch is written plainly inside
        it and left for that block to release or roll back.

        A failure raised by ``executemany`` here is never caught and re-raised,
        because this method cannot make an honest rollback claim from inside its
        own scope; the caller's category block performs the rollback. Callers
        wrap this call to attach the ``DatabaseError`` contract after the
        rollback has happened.
        """
        self._connection.executemany(statement, batch)

    def stream_raw_discovery_observations(
        self, run_id: str
    ) -> "Iterator[RawDiscoveryObservationRecord]":
        """Iterate every stored observation for a run in ordinal order."""
        self._check_open()
        cursor = self._connection.execute(
            "SELECT * FROM raw_discovery_observations WHERE run_id = ? "
            "ORDER BY category ASC, discovery_ordinal ASC, observation_id ASC",
            (run_id,),
        )
        for row in cursor:
            yield _project_row(
                "raw_discovery_observations",
                TABLE_COLUMNS["raw_discovery_observations"],
                {key: row[key] for key in row.keys()},
            )

    def update_raw_discovery_identity(
        self, observations: "Iterable[RawDiscoveryObservationRecord]"
    ) -> int:
        """Update only the four post-discovery columns, by ``observation_id``."""
        self._check_open()
        statement = (
            "UPDATE raw_discovery_observations SET "
            + ", ".join(f"{column} = ?" for column in _RAW_IDENTITY_COLUMNS)
            + " WHERE observation_id = ?"
        )
        updated = 0
        for record in observations:
            values = tuple(
                _encode_column(
                    "raw_discovery_observations", column, getattr(record, column)
                )
                for column in _RAW_IDENTITY_COLUMNS
            ) + (record.observation_id,)
            try:
                cursor = self._connection.execute(statement, values)
            except sqlite3.IntegrityError as exc:
                raise _integrity_error(
                    "raw_discovery_observations", exc, 0
                ) from None
            updated += cursor.rowcount
        return updated

    # -- sample members ----------------------------------------------------

    def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None:
        """Plain insert; duplicate membership is rejected by the primary key."""
        self._check_open()
        self._insert_rows("sample_members", members)

    def upsert_sample_members(self, members: Sequence[SampleMemberRecord]) -> int:
        """Re-materialize summary columns on the existing membership row."""
        return self._upsert_rows("sample_members", members)

    def mark_preflight_selected(
        self, run_id: str, asset_identity_keys: Sequence[str]
    ) -> int:
        """Set ``sample_members.preflight_selected = True`` for the given keys.

        Scoped to ``(run_id, asset_identity_key)``; returns the number of rows
        changed. A key absent from the run's ``sample_members`` changes no row:
        it is never an error and never a fabricated membership row. No other
        column is assigned and no clock is read.
        """
        self._check_open()
        statement = (
            "UPDATE sample_members SET preflight_selected = 1 "
            "WHERE run_id = ? AND asset_identity_key = ?"
        )
        changed = 0
        for asset_identity_key in asset_identity_keys:
            cursor = self._connection.execute(
                statement, (run_id, asset_identity_key)
            )
            changed += cursor.rowcount
        return changed

    # -- sampling summaries (Chunk 4B) -------------------------------------

    # The eight sampling-phase ``category_scores`` columns this method owns
    # (Q-2 option (a)). Every scoring-phase column is deliberately absent.
    _SAMPLING_PHASE_COLUMNS: tuple[str, ...] = (
        "discovered_population_count",
        "enriched_sample_count",
        "sample_is_census",
        "sampling_basis",
        "sample_fraction",
        "overlap_category_count",
        "overlap_sample_percentage",
        "stratum_statistics_json",
    )

    def upsert_sampling_summary(
        self,
        run_id: str,
        category: str,
        *,
        discovered_population_count: int,
        enriched_sample_count: int,
        sample_is_census: bool,
        sampling_basis: str,
        sample_fraction: float | None,
        overlap_category_count: int,
        overlap_sample_percentage: float | None,
        stratum_statistics_json: str,
        computed_at_utc: datetime,
        discovery_status: str | None = None,
    ) -> None:
        """Write only the sampling-phase ``category_scores`` columns (Q-2 option (a)).

        Creates the ``(run_id, category)`` row if absent, filling every other
        ``NOT NULL`` column from the module's pre-scoring default table
        (``_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]``) and binding the
        supplied sampling-phase values; on conflict it updates **only** the eight
        sampling-phase columns — ``discovered_population_count``,
        ``enriched_sample_count``, ``sample_is_census``, ``sampling_basis``,
        ``sample_fraction``, ``overlap_category_count``,
        ``overlap_sample_percentage``, and ``stratum_statistics_json``. Every
        scoring-phase column, and ``unique_enrichment_count`` / the three
        ``usable_*_sample_count`` columns, are left untouched on the update path.
        ``sampling_basis`` is validated against ``SamplingBasis``.
        ``computed_at_utc`` is required and caller-supplied; this module reads no
        clock and writes nothing on ``None``.

        **Create-if-absent is a defensive fallback (lead ruling 2026-09-20).**
        ``category_scores.discovery_status`` is ``TEXT NOT NULL`` and is the one
        non-sampling ``NOT NULL`` column absent from the module's default table,
        so this method SHALL NOT invent it. ``persist_run_sampling`` forwards the
        ``discovery_status`` it reads from ``get_category_scores``; the Chunk 3
        runtime path always creates the row before 4B runs. If no
        ``(run_id, category)`` row exists and no ``discovery_status`` is
        supplied, the method raises ``InvalidRecordValueError`` naming the table
        and column only. The Q-2 restriction to sampling-phase columns governs
        the **update** path, which is unchanged.
        """
        self._check_open()
        _validate_enum("category_scores", "sampling_basis", sampling_basis)
        if computed_at_utc is None:
            raise InvalidRecordValueError(
                "category_scores.computed_at_utc: value is required and is not "
                "read from the system clock"
            )

        if discovery_status is None:
            # No value supplied: only an existing row can yield one. A missing
            # row is exactly the case the column's ``NOT NULL`` has no answer
            # for, so the fallback refuses rather than inventing a status.
            existing = self._connection.execute(
                "SELECT discovery_status FROM category_scores "
                "WHERE run_id = ? AND category = ?",
                (run_id, category),
            ).fetchone()
            if existing is None:
                raise InvalidRecordValueError(
                    "category_scores.discovery_status: value is required when no "
                    "category_scores row exists"
                )
            discovery_status = existing[0]
        _validate_enum("category_scores", "discovery_status", discovery_status)

        defaults = _IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]
        supplied: dict[str, object] = {
            "run_id": run_id,
            "category": category,
            "discovery_status": discovery_status,
            "computed_at_utc": computed_at_utc,
            "discovered_population_count": discovered_population_count,
            "enriched_sample_count": enriched_sample_count,
            "sample_is_census": sample_is_census,
            "sampling_basis": sampling_basis,
            "sample_fraction": sample_fraction,
            "overlap_category_count": overlap_category_count,
            "overlap_sample_percentage": overlap_sample_percentage,
            "stratum_statistics_json": stratum_statistics_json,
        }
        # Every ``NOT NULL`` column is either caller-supplied or filled from the
        # module's pre-scoring default table; nullable scoring columns are left
        # out entirely so the insert leaves them SQL ``NULL`` and the update
        # leaves them untouched.
        columns = tuple(
            column
            for column in TABLE_COLUMNS["category_scores"]
            if column in supplied or column in defaults
        )
        assignments = ", ".join(
            f"{column} = excluded.{column}" for column in self._SAMPLING_PHASE_COLUMNS
        )
        statement = (
            f"INSERT INTO category_scores ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT (run_id, category) DO UPDATE SET {assignments}"
        )
        values = tuple(
            _encode_column(
                "category_scores",
                column,
                supplied[column] if column in supplied else defaults[column],
            )
            for column in columns
        )
        try:
            self._connection.execute(statement, values)
        except sqlite3.IntegrityError as exc:
            raise _integrity_error("category_scores", exc, 0) from None

    # -- enrichment observations -------------------------------------------

    def insert_enrichment_observations(
        self, observations: Sequence[EnrichmentObservationRecord]
    ) -> None:
        """Plain insert; one row per ``(run_id, asset_identity_key)``."""
        self._check_open()
        self._insert_rows("enrichment_observations", observations)

    def upsert_enrichment_observation(
        self, observation: EnrichmentObservationRecord
    ) -> None:
        """Upsert one identity's single enrichment row."""
        self._upsert_rows("enrichment_observations", (observation,))

    # -- category scores ---------------------------------------------------

    def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None:
        """Plain insert; duplicate ``(run_id, category)`` is rejected."""
        self._check_open()
        self._insert_rows("category_scores", scores)

    def upsert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> int:
        """Finalize existing ``(run_id, category)`` rows."""
        return self._upsert_rows("category_scores", scores)

    # -- reads -------------------------------------------------------------

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        self._check_open()
        row = self._connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return _project_row("runs", TABLE_COLUMNS["runs"], _row_mapping(row))

    def iter_raw_discovery_observations(
        self, run_id: str, category: str
    ) -> Iterator[RawDiscoveryObservationRecord]:
        self._check_open()
        cursor = self._connection.execute(
            "SELECT * FROM raw_discovery_observations "
            "WHERE run_id = ? AND category = ? "
            "ORDER BY discovery_ordinal ASC, observation_id ASC",
            (run_id, category),
        )
        for row in cursor:
            yield _project_row(
                "raw_discovery_observations",
                TABLE_COLUMNS["raw_discovery_observations"],
                _row_mapping(row),
            )

    def get_sample_members(
        self, run_id: str, category: str
    ) -> Sequence[SampleMemberRecord]:
        self._check_open()
        rows = self._connection.execute(
            "SELECT * FROM sample_members WHERE run_id = ? AND category = ? "
            "ORDER BY stratum_index ASC, sample_rank_within_stratum ASC",
            (run_id, category),
        ).fetchall()
        return tuple(
            _project_row("sample_members", TABLE_COLUMNS["sample_members"], _row_mapping(row))
            for row in rows
        )

    def get_enrichment_observation(
        self, run_id: str, asset_identity_key: str
    ) -> Optional[EnrichmentObservationRecord]:
        self._check_open()
        row = self._connection.execute(
            "SELECT * FROM enrichment_observations "
            "WHERE run_id = ? AND asset_identity_key = ?",
            (run_id, asset_identity_key),
        ).fetchone()
        if row is None:
            return None
        return _project_row(
            "enrichment_observations",
            TABLE_COLUMNS["enrichment_observations"],
            _row_mapping(row),
        )

    def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]:
        self._check_open()
        rows = self._connection.execute(
            "SELECT * FROM category_scores WHERE run_id = ? ORDER BY category ASC",
            (run_id,),
        ).fetchall()
        return tuple(
            _project_row(
                "category_scores", TABLE_COLUMNS["category_scores"], _row_mapping(row)
            )
            for row in rows
        )

    def count_raw_discovery_observations(self, run_id: str, category: str) -> int:
        self._check_open()
        return self._count(
            "SELECT count(*) FROM raw_discovery_observations "
            "WHERE run_id = ? AND category = ?",
            (run_id, category),
        )

    def count_distinct_enrichment_observations(self, run_id: str) -> int:
        self._check_open()
        return self._count(
            "SELECT count(DISTINCT asset_identity_key) FROM enrichment_observations "
            "WHERE run_id = ?",
            (run_id,),
        )

    def count_discovery_observations(self, run_id: str) -> int:
        self._check_open()
        return self._count(
            "SELECT count(*) FROM raw_discovery_observations WHERE run_id = ?",
            (run_id,),
        )

    def count_sample_members(self, run_id: str) -> int:
        self._check_open()
        return self._count(
            "SELECT count(*) FROM sample_members WHERE run_id = ?", (run_id,)
        )

    def count_distinct_enrichment_identities(self, run_id: str) -> int:
        self._check_open()
        return self._count(
            "SELECT count(DISTINCT asset_identity_key) FROM enrichment_observations "
            "WHERE run_id = ?",
            (run_id,),
        )

    # -- internals ---------------------------------------------------------

    def _count(self, statement: str, parameters: tuple[object, ...]) -> int:
        row = self._connection.execute(statement, parameters).fetchone()
        return int(row[0]) if row is not None else 0

    def _check_open(self) -> None:
        if self._closed:
            raise ClosedRepositoryError("repository is closed")

    def _check_not_in_category_block(self, method: str) -> None:
        if self._category_stack:
            raise RepositoryError(
                f"{method} is not supported inside an active category transaction"
            )

    def _transaction_depth(self) -> int:
        """Whether a ``transaction()`` block on this instance owns the transaction.

        This reports the module's own nesting state, never
        ``sqlite3.Connection.in_transaction``. pysqlite's default regime opens an
        implicit transaction before the first DML of *any* call, so
        ``in_transaction`` is also true after a plainly-called ``insert_run``
        with no ``transaction()`` anywhere on the stack. Reading that as "an
        enclosing transaction owns this" would make a ``category_transaction``
        treat another method's pending, uncommitted work as a peer's and leave
        it open forever — the rows would never be committed by anyone. Only
        ``transaction()`` sets ``_outermost_transaction_depth``, so it is the
        only thing that can claim ownership here.
        """
        return self._outermost_transaction_depth

    def _release_once(self, name: str) -> None:
        """Release a savepoint exactly once, letting a real failure propagate.

        The previous helper of this name skipped ``RELEASE`` whenever it could
        not see an open transaction and swallowed a failed ``RELEASE`` under the
        same condition. That condition is exactly the one in which an outermost
        savepoint's implicit transaction is already gone (a failing statement
        ended it), so the helper's silent early return was indistinguishable
        from a successful release and hid dropped batches behind a passing test.
        A release is issued unconditionally here; ``savepoint`` and
        ``category_transaction`` are the only callers, both immediately after a
        successful ``SAVEPOINT`` of the same name, so a failure is a real engine
        error and the platform has already rolled the transaction back, making
        that error the only remaining signal.
        """
        self._connection.execute(f"RELEASE {name}")

    def _insert_rows(self, table: str, records: Sequence[object]) -> None:
        if not records:
            return
        columns = tuple(TABLE_COLUMNS[table])
        implicit = tuple(
            column
            for column in columns
            if column not in _bindable(table)
        )
        statement = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        # The frozen DDL declares no DEFAULT clause, so an omitted NOT NULL
        # column has no value the database can supply. Section 5.9 (lines
        # 760-769) requires that a column the record supplies keeps that value
        # while a column the record leaves as None takes the implicit default:
        # the row is therefore assembled per record, not per table, because two
        # records of the same table may populate different columns.
        rows = []
        for record in records:
            supplied = set(_record_columns_with_non_none(table, record))
            rows.append(
                tuple(
                    _encode_column(table, column, getattr(record, column))
                    if column in supplied
                    else _encode_column(
                        table, column, _implicit_default(table, column)
                    )
                    for column in columns
                )
            )
        try:
            self._connection.executemany(statement, rows)
        except sqlite3.IntegrityError as exc:
            raise _integrity_error(table, exc, 0) from None
        except sqlite3.Error as exc:
            raise DatabaseError(
                f"{table}: failed to insert {len(rows)} row(s) "
                f"({', '.join(implicit)})"
            ) from exc

    def _upsert_rows(self, table: str, records: Sequence[object]) -> int:
        if not records:
            return 0
        columns = tuple(TABLE_COLUMNS[table])
        update_columns = tuple(
            column for column in columns if column not in TABLE_PRIMARY_KEYS[table]
        )
        assignments = ", ".join(
            f"{column} = excluded.{column}" for column in update_columns
        )
        statement = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT ({', '.join(TABLE_PRIMARY_KEYS[table])}) "
            f"DO UPDATE SET {assignments}"
        )
        rows = [_encode_row(record, columns) for record in records]
        try:
            self._connection.executemany(statement, rows)
        except sqlite3.IntegrityError as exc:
            raise _integrity_error(table, exc, 0) from None
        except sqlite3.Error as exc:
            raise DatabaseError(
                f"{table}: failed to upsert {len(rows)} row(s)"
            ) from exc
        return len(rows)

    def _insert_columns(self, table: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return (record-bound columns, default-filled columns) for a plain insert.

        ``_IMPLICIT_NOT_NULL_DEFAULTS`` is closed over the frozen DDL: every key
        is a real column, and ``_bindable`` keeps a nullable column bindable.
        The pair returned here is total over the table and unique across it.

        The first tuple is the set of columns this table *may* bind, not the set
        a particular record does bind: which columns that record supplies is
        decided per record by ``_record_columns_with_non_none``, so supplying a
        value for a defaulted ``NOT NULL`` column keeps it rather than
        discarding it.
        """
        bound = tuple(column for column in TABLE_COLUMNS[table] if column in _bindable(table))
        explicit = tuple(
            column for column in TABLE_COLUMNS[table] if column not in bound
        )
        return bound, explicit


def _insert_omitted_columns(table: str) -> tuple[str, ...]:
    """Columns a plain INSERT default-fills when the record supplies ``None``.

    This is the ``explicit`` half of ``SqliteRepository._insert_columns``,
    derived from the same ``_bindable`` predicate so the two cannot drift apart.
    It names the columns that fall back to :data:`_IMPLICIT_NOT_NULL_DEFAULTS`;
    a record that supplies its own value for one of them is bound through
    ``_record_columns_with_non_none`` instead of being overwritten here.
    """
    bindable = set(_bindable(table))
    return tuple(
        column for column in TABLE_COLUMNS[table] if column not in bindable
    )


def _row_mapping(row: sqlite3.Row | tuple) -> dict[str, object]:
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}  # type: ignore[union-attr]
    return {}


def _busy_timeout_statement(busy_timeout_ms: int) -> str:
    """Build the ``busy_timeout`` setter.

    A pragma setter is a SQL fragment interpolated into the statement, so the
    value has to be validated into an integer here rather than trusted as text.
    """
    timeout = int(busy_timeout_ms)
    if timeout < 0:
        raise ValueError("busy_timeout_ms must be >= 0")
    return f"PRAGMA busy_timeout = {timeout}"


# The four levels ``PRAGMA synchronous`` accepts, by canonical name.
_SYNCHRONOUS_LEVELS: frozenset[str] = frozenset({"OFF", "NORMAL", "FULL", "EXTRA"})

# ``PRAGMA synchronous`` reports an integer level even though it is set by name,
# so a verification comparing the read value to the configured name would
# compare an integer to a string. This is the documented numbering SQLite uses.
_SYNCHRONOUS_LEVELS_BY_NUMBER: tuple[str, ...] = ("OFF", "NORMAL", "FULL", "EXTRA")

# ``PRAGMA journal_mode = WAL`` is a local implementation choice (plan 5.4), so
# the mode is verified by reading it back rather than by trusting the setter.
WAL_JOURNAL_MODE = "wal"


def _synchronous_statement(synchronous: str) -> str:
    """Build the ``synchronous`` setter, rejecting anything outside the four levels.

    The level is spliced into the statement as a SQL fragment, so an
    unvalidated string would be an injection surface as well as a silent
    no-op: SQLite accepts an unknown level without error. Only the four
    documented names are allowed.
    """
    name = str(synchronous).strip().upper()
    if name not in _SYNCHRONOUS_LEVELS:
        raise ValueError(
            "synchronous must be one of OFF, NORMAL, FULL, EXTRA"
        )
    return name


def _synchronous_level(number: int) -> str:
    """Name the durability level SQLite reports as an integer."""
    if 0 <= number < len(_SYNCHRONOUS_LEVELS_BY_NUMBER):
        return _SYNCHRONOUS_LEVELS_BY_NUMBER[number]
    raise DatabaseError("PRAGMA synchronous reported an unknown level")


def _run_batch_failure(records_in_batch: int, written: int) -> DatabaseError:
    """The published non-constraint failure, naming counts and no content.

    The batch is rolled back before this is raised, so the count reported is the
    count of the batch that failed and the count of records already written
    before it. Neither field carries a record value, a header, or an identity.
    """
    return DatabaseError(
        "raw_discovery_observations: failed to write a batch of "
        f"{records_in_batch} record(s) after {written} record(s)"
    )


def _idempotent(statement: str) -> str:
    """Rewrite a frozen ``CREATE TABLE`` into a ``CREATE ... IF NOT EXISTS``."""
    if statement.startswith("CREATE TABLE IF NOT EXISTS"):
        return statement
    if statement.startswith("CREATE TABLE "):
        return statement.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
    if statement.startswith("CREATE INDEX "):
        return statement.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
    return statement


def _savepoint_name(run_id: str, category: str) -> str:
    raw = f"category_{run_id}_{category}"
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"category_{cleaned}"
    return cleaned


def _validate_savepoint_name(name: str) -> None:
    if not isinstance(name, str) or not _SAVEPOINT_PATTERN.fullmatch(name):
        raise ValueError("savepoint name must match [A-Za-z_][A-Za-z0-9_]*")


_ROW_TYPES: dict[str, type] = {
    "runs": RunRecord,
    "raw_discovery_observations": RawDiscoveryObservationRecord,
    "sample_members": SampleMemberRecord,
    "enrichment_observations": EnrichmentObservationRecord,
    "category_scores": CategoryScoreRecord,
}

# The frozen DDL names columns but never a SQLite keyword, so a bare table name
# is always a valid identifier here; the module never builds SQL from user data.
_TABLE_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _integrity_error(
    table: str, exc: sqlite3.IntegrityError, written: int
) -> DatabaseError:
    """Map a constraint failure to the declared exception, redaction-safe."""
    message = str(exc)
    if "FOREIGN KEY" in message.upper():
        return ForeignKeyConstraintViolation(
            f"{table}: row references a run_id that does not exist"
        )
    if "UNIQUE" in message.upper() or "PRIMARY KEY" in message.upper():
        if written:
            return UniqueConstraintViolation(
                f"{table}: primary key conflict while streaming after "
                f"{written} record(s) ({', '.join(TABLE_PRIMARY_KEYS[table])})"
            )
        return UniqueConstraintViolation(
            f"{table}: primary key conflict ({', '.join(TABLE_PRIMARY_KEYS[table])})"
        )
    return DatabaseError(f"{table}: constraint failure while writing rows")


# Validate the derived column-name helpers once, so a drift in the frozen DDL
# fails fast instead of producing unchecked SQL identifiers.
for _table_name in TABLE_COLUMNS:
    if not _TABLE_NAME_PATTERN.fullmatch(_table_name):
        raise RuntimeError(f"unexpected table name in the frozen DDL: {_table_name}")


# --------------------------------------------------------------------------
# Chunk 4B — sampling summary serializer, persistence, and verification
# --------------------------------------------------------------------------

#: The frozen ten-key per-stratum object schema (plan §5.2). Serialization uses
#: ``json.dumps(value, sort_keys=True, separators=(",", ":"))``, so the key set
#: is the contract and the key order is ``sort_keys``-determined.
STRATUM_STATISTICS_KEYS: tuple[str, ...] = (
    "N_h",
    "eligibility_rule",
    "n_h",
    "stratum_end_ordinal",
    "stratum_index",
    "stratum_start_ordinal",
    "u_demand_h",
    "u_quality_h",
    "u_recent_h",
    "usable_status",
)

#: The four-token ``usable_status`` vocabulary frozen by Chunk 4B (Q-4).
USABLE_STATUS_VOCABULARY: tuple[str, ...] = (
    "pending",
    "usable",
    "unavailable",
    "invalid",
)

#: The token Chunk 4B writes while enrichment eligibility is unknown.
PENDING_USABLE_STATUS = "pending"

_STRATUM_STATISTICS_KEY_SET = frozenset(STRATUM_STATISTICS_KEYS)


def serialize_stratum_statistics(category: CategorySamplingResult) -> str:
    """Serialize one category's strata into the frozen JSON summary (plan §5.2).

    One object per stratum, sorted by ascending ``stratum_index``, with exactly
    the ten keys of :data:`STRATUM_STATISTICS_KEYS`. ``N_h`` is the stratum's
    discovered population (``population_count``); ``n_h`` is the selected count
    (``selected_count``) that the pure 4A result carries and is persisted as-is,
    never recalculated here; ``u_demand_h``, ``u_recent_h``, ``u_quality_h`` and
    ``eligibility_rule`` are JSON ``null`` while pending; ``usable_status`` is
    ``"pending"``. An empty population serializes to ``"[]"``. Deterministic:
    ``json.dumps(value, sort_keys=True, separators=(",", ":"))``, with no
    dependence on dict/set iteration order.
    """
    payload = [
        {
            "stratum_index": stratum.stratum_index,
            "stratum_start_ordinal": stratum.start_ordinal,
            "stratum_end_ordinal": stratum.end_ordinal,
            "N_h": stratum.population_count,
            "n_h": stratum.selected_count,
            "u_demand_h": None,
            "u_recent_h": None,
            "u_quality_h": None,
            "usable_status": PENDING_USABLE_STATUS,
            "eligibility_rule": None,
        }
        for stratum in sorted(category.strata, key=lambda item: item.stratum_index)
    ]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def parse_stratum_statistics(payload: str) -> tuple[dict[str, object], ...]:
    """Parse a ``stratum_statistics_json`` value into its per-stratum objects.

    A read-back helper for verification: returns the object list exactly as
    stored, preserving serialized values (JSON ``null`` stays ``None``). Raises
    :class:`DatabaseError` when the stored text is not a JSON array of objects,
    when an object does not carry exactly the frozen ten-key schema, or when a
    ``usable_status`` token is outside the frozen vocabulary.
    """
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DatabaseError(
            "category_scores.stratum_statistics_json: stored value is not valid JSON"
        ) from exc
    if not isinstance(decoded, list) or not all(
        isinstance(entry, dict) for entry in decoded
    ):
        raise DatabaseError(
            "category_scores.stratum_statistics_json: stored value is not a JSON "
            "array of objects"
        )
    for entry in decoded:
        if set(entry) != _STRATUM_STATISTICS_KEY_SET:
            raise DatabaseError(
                "category_scores.stratum_statistics_json: stratum object does not "
                "carry the frozen ten-key schema"
            )
        if entry["usable_status"] not in USABLE_STATUS_VOCABULARY:
            raise DatabaseError(
                "category_scores.stratum_statistics_json: usable_status is outside "
                "the frozen vocabulary"
            )
    return tuple(decoded)


@dataclass(frozen=True, slots=True)
class SamplingPersistenceReport:
    """Outcome of a 4B persist or verify pass.

    ``sample_members_written`` is the rows written by ``persist_run_sampling``
    and the rows read by ``verify_persisted_sampling``; ``categories_written``
    is the summaries written or read; ``mismatches`` is empty when verified and
    otherwise names only the column and category (never an identity string).
    """

    run_id: str
    sample_members_written: int
    categories_written: int
    mismatches: tuple[str, ...]


def persist_run_sampling(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    computed_at_utc: datetime,
) -> SamplingPersistenceReport:
    """Materialize ``run`` into ``sample_members`` and the per-category summary.

    ``computed_at_utc`` is required and caller-supplied; this chunk reads no
    clock, so ``None`` raises and writes nothing. Overlap is computed once with
    ``sampling.compute_overlap`` and written to both ``sample_members`` (each
    member row repeats its category's ``CategoryOverlap`` values per Q-3) and the
    category summary (via ``upsert_sampling_summary``). Members are written
    through ``upsert_sample_members``, so re-materializing a run is idempotent
    and can never create a second membership for a
    ``(run_id, category, identity)``; a hand-built duplicate insert is still
    rejected by the primary key (``UniqueConstraintViolation``). Every member
    carries ``preflight_selected=False`` (Q-5). ``runs.sampling_rule_version`` is
    not rewritten. ``u_demand_h``/``u_recent_h``/``u_quality_h`` are written as
    explicit pending placeholders in ``stratum_statistics_json``; the
    category-level ``usable_*`` and ``unique_enrichment_count`` columns are not
    written. A missing ``runs`` row raises ``ForeignKeyConstraintViolation``.
    Returns the counts actually written; ``mismatches`` is empty.
    """
    if computed_at_utc is None:
        raise InvalidRecordValueError(
            "category_scores.computed_at_utc: value is required and is not "
            "read from the system clock"
        )

    overlap_by_category = compute_overlap(run).by_category
    statuses = {
        row.category: row.discovery_status
        for row in repository.get_category_scores(run.run_id)
    }

    members_written = 0
    for category_result in run.categories:
        category_overlap = overlap_by_category[category_result.category]
        records = tuple(
            SampleMemberRecord(
                run_id=run.run_id,
                category=member.category,
                asset_identity_key=member.asset_identity_key,
                stratum_index=member.stratum_index,
                stratum_start_ordinal=member.stratum_start_ordinal,
                stratum_end_ordinal=member.stratum_end_ordinal,
                sample_rank_within_stratum=member.sample_rank_within_stratum,
                sample_is_census=member.sample_is_census,
                selection_digest=member.selection_digest,
                overlap_category_count=category_overlap.overlap_category_count,
                overlap_sample_percentage=category_overlap.overlap_sample_percentage,
                preflight_selected=False,
            )
            for member in category_result.members
        )
        members_written += repository.upsert_sample_members(records)
        repository.upsert_sampling_summary(
            run.run_id,
            category_result.category,
            discovered_population_count=category_result.discovered_population_count,
            enriched_sample_count=category_result.enriched_sample_count,
            sample_is_census=category_result.sample_is_census,
            sampling_basis=category_result.sampling_basis.value,
            sample_fraction=category_result.sample_fraction,
            overlap_category_count=category_overlap.overlap_category_count,
            overlap_sample_percentage=category_overlap.overlap_sample_percentage,
            stratum_statistics_json=serialize_stratum_statistics(category_result),
            computed_at_utc=computed_at_utc,
            discovery_status=statuses.get(category_result.category),
        )

    return SamplingPersistenceReport(
        run_id=run.run_id,
        sample_members_written=members_written,
        categories_written=len(run.categories),
        mismatches=(),
    )


def _mismatch(category: str, column: str) -> str:
    """A redaction-safe mismatch string naming only the category and column."""
    return f"{category}: {column} does not match the pure sampling result"


def verify_persisted_sampling(
    repository: SqliteRepository,
    run: RunSamplingResult,
) -> SamplingPersistenceReport:
    """Read back and compare persisted values against the pure 4A result.

    Deterministic: reads ``get_sample_members``, ``get_category_scores``, and
    ``get_run``, then compares membership (identity set, stratum/rank, census
    flag, ``selection_digest``), the category summary
    (``discovered_population_count``, ``enriched_sample_count``,
    ``sample_is_census``, ``sampling_basis``, ``sample_fraction`` — including
    ``None`` for a zero population and the ``sample_fraction`` ≠
    eligibility-coverage distinction), the overlap fields (category-level on both
    ``sample_members`` and the summary), the per-stratum ``N_h``/``n_h`` and the
    frozen ``stratum_statistics_json`` schema/status tokens (§5.2), and
    ``runs.sampling_rule_version`` against ``run.sampling_rule_version``. It does
    **not** assert the category-level ``usable_*_sample_count`` or
    ``unique_enrichment_count`` as measured values. Returns ``mismatches == ()``
    when every compared value equals the pure result; mismatch strings name the
    column and category only — never an identity string or a secret.
    ``sample_members_written``/``categories_written`` report the rows read.
    """
    mismatches: list[str] = []
    overlap_by_category = compute_overlap(run).by_category

    run_record = repository.get_run(run.run_id)
    if run_record is None:
        mismatches.append(
            f"{run.run_id}: runs row is missing; sampling_rule_version cannot be "
            "verified"
        )
    elif run_record.sampling_rule_version != run.sampling_rule_version:
        mismatches.append(
            f"{run.run_id}: runs.sampling_rule_version does not match the pure "
            "sampling result"
        )

    summaries = {
        row.category: row for row in repository.get_category_scores(run.run_id)
    }

    members_read = 0
    categories_read = 0
    for category_result in run.categories:
        category = category_result.category
        category_overlap = overlap_by_category[category]

        stored_members = repository.get_sample_members(run.run_id, category)
        members_read += len(stored_members)

        pure_by_key = {
            member.asset_identity_key: member for member in category_result.members
        }
        stored_by_key = {row.asset_identity_key: row for row in stored_members}
        if set(pure_by_key) != set(stored_by_key):
            mismatches.append(_mismatch(category, "sample_members.membership"))
        for identity_key in sorted(set(pure_by_key) & set(stored_by_key)):
            pure_member = pure_by_key[identity_key]
            stored_member = stored_by_key[identity_key]
            if stored_member.stratum_index != pure_member.stratum_index:
                mismatches.append(_mismatch(category, "sample_members.stratum_index"))
            if stored_member.stratum_start_ordinal != pure_member.stratum_start_ordinal:
                mismatches.append(
                    _mismatch(category, "sample_members.stratum_start_ordinal")
                )
            if stored_member.stratum_end_ordinal != pure_member.stratum_end_ordinal:
                mismatches.append(
                    _mismatch(category, "sample_members.stratum_end_ordinal")
                )
            if (
                stored_member.sample_rank_within_stratum
                != pure_member.sample_rank_within_stratum
            ):
                mismatches.append(
                    _mismatch(category, "sample_members.sample_rank_within_stratum")
                )
            if stored_member.sample_is_census != pure_member.sample_is_census:
                mismatches.append(
                    _mismatch(category, "sample_members.sample_is_census")
                )
            if stored_member.selection_digest != pure_member.selection_digest:
                mismatches.append(
                    _mismatch(category, "sample_members.selection_digest")
                )
            if (
                stored_member.overlap_category_count
                != category_overlap.overlap_category_count
            ):
                mismatches.append(
                    _mismatch(category, "sample_members.overlap_category_count")
                )
            if not _percentages_equal(
                stored_member.overlap_sample_percentage,
                category_overlap.overlap_sample_percentage,
            ):
                mismatches.append(
                    _mismatch(category, "sample_members.overlap_sample_percentage")
                )

        summary = summaries.get(category)
        if summary is None:
            mismatches.append(_mismatch(category, "category_scores row is missing"))
            continue
        categories_read += 1
        if (
            summary.discovered_population_count
            != category_result.discovered_population_count
        ):
            mismatches.append(
                _mismatch(category, "category_scores.discovered_population_count")
            )
        if summary.enriched_sample_count != category_result.enriched_sample_count:
            mismatches.append(
                _mismatch(category, "category_scores.enriched_sample_count")
            )
        if summary.sample_is_census != category_result.sample_is_census:
            mismatches.append(_mismatch(category, "category_scores.sample_is_census"))
        if summary.sampling_basis != category_result.sampling_basis.value:
            mismatches.append(_mismatch(category, "category_scores.sampling_basis"))
        if not _fractions_equal(
            summary.sample_fraction, category_result.sample_fraction
        ):
            mismatches.append(_mismatch(category, "category_scores.sample_fraction"))
        if summary.overlap_category_count != category_overlap.overlap_category_count:
            mismatches.append(
                _mismatch(category, "category_scores.overlap_category_count")
            )
        if not _percentages_equal(
            summary.overlap_sample_percentage,
            category_overlap.overlap_sample_percentage,
        ):
            mismatches.append(
                _mismatch(category, "category_scores.overlap_sample_percentage")
            )
        expected_strata = serialize_stratum_statistics(category_result)
        if summary.stratum_statistics_json != expected_strata:
            mismatches.append(
                _mismatch(category, "category_scores.stratum_statistics_json")
            )
        else:
            try:
                parse_stratum_statistics(summary.stratum_statistics_json)
            except DatabaseError:
                mismatches.append(
                    _mismatch(category, "category_scores.stratum_statistics_json")
                )

    return SamplingPersistenceReport(
        run_id=run.run_id,
        sample_members_written=members_read,
        categories_written=categories_read,
        mismatches=tuple(mismatches),
    )


def _percentages_equal(left: float | None, right: float | None) -> bool:
    """Compare two nullable overlap percentages exactly, preserving ``None``."""
    if left is None or right is None:
        return left is None and right is None
    return left == right


def _fractions_equal(left: float | None, right: float | None) -> bool:
    """Compare two nullable sample fractions exactly, preserving ``None``."""
    if left is None or right is None:
        return left is None and right is None
    return left == right
