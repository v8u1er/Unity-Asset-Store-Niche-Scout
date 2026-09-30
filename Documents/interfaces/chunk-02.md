# Chunk 2 — SQLite implementation and repository behavior (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-02-sqlite-implementation-and-repository.md`
Verified at: working tree state 2026-09-16; gates `python -m pytest tests/test_database.py -q`
(23 passed, exit 0), `python -m pytest tests -q` (91 passed, 1 failed — see §8),
`python -m niche_scout.tools.check_import_boundaries` (exit 0),
`python -m niche_scout.tools.validate_traceability` (exit 0),
`python -m pytest tests -q --collect-only` (92 tests, exit 0).

This file is the **public contract** other chunks build against. It is not the
full source; read `src/niche_scout/database.py` for implementation detail.
Everything below is frozen: downstream chunks may consume these names and
semantics, and SHALL NOT redefine them. Chunk 2 is an **I/O** module: it is the
only module that imports `sqlite3`. `metrics.py` and `scoring.py` remain pure
and unmodified.

**What this chunk is.** Chunk 0 froze the persistence *contract* and executed
nothing. Chunk 2 owns the physical SQLite implementation behind it: connection
lifecycle, pragmas, schema initialization keyed on `SCHEMA_VERSION`, streamed
raw-observation persistence, transactions/savepoints with category isolation,
status transitions, and the read/count surface. It adds **no table, no column,
no index, and no constant**, and modifies no frozen Chunk 0 name.

---

## 1. Module and boundary rules

| Module | Kind | Rule |
|---|---|---|
| `src/niche_scout/database.py` | **I/O** | Frozen schema specification + `Repository` protocol + physical SQLite implementation |

- `database.py` may import `sqlite3`, `pathlib`, `contextlib`, `datetime`,
  `re`, `collections.abc`, and `typing`. It SHALL NOT be imported by
  `metrics.py` or `scoring.py`
  (`python -m niche_scout.tools.check_import_boundaries` → exit 0,
  `Import boundaries valid for metrics.py, scoring.py`).
- `models.py` was **not** modified by this chunk
  (`git diff --stat src/niche_scout/models.py` → empty). The five frozen row
  dataclasses, every enum, every constant, `SCHEMA_VERSION`, `DDL_STATEMENTS`,
  `CREATE_TABLE_STATEMENTS`, `TABLE_COLUMNS`, `TABLE_PRIMARY_KEYS`,
  `TABLE_INDEXES`, and every existing `Repository` protocol signature are
  consumed unchanged. New names are **additive only**.
- No DDL and no DML at import time. Importing `niche_scout.database` opens no
  connection and creates no file; only the pre-existing `_validate_specification()`
  and two identifier-format checks run at import.
- `metrics.py`/`scoring.py` purity is untouched: no clock read was added to any
  pure module, and no repository method reads the system clock for a record
  column (`scoring_cutoff_utc` and every `*_at_utc` value are caller-supplied).
- **Null, zero, invalid, and unavailable stay distinct.** No code path converts
  `None`/missing/invalid to `0`, `0.0`, `""`, or `False` on write or on read.
- Determinism: identical inputs plus an identical `SCHEMA_VERSION` produce
  structurally identical rows; ordering is fixed (see §5).

---

## 2. Public names added to `niche_scout.database`

### 2.1 Constants / containers

```python
SCHEMA_VERSION = "1.1.0"                        # Chunk 23 additive correction (was "1.0.0")

DDL_STATEMENTS: tuple[str, ...]                 # 5 CREATE TABLE + 1 CREATE INDEX
CREATE_TABLE_STATEMENTS: dict[str, str]         # table name -> CREATE TABLE string
TABLE_COLUMNS: dict[str, tuple[str, ...]]       # table name -> column names, in order
TABLE_PRIMARY_KEYS: dict[str, tuple[str, ...]]  # table name -> primary-key columns
TABLE_INDEXES: dict[str, str]                   # index name -> CREATE INDEX string
```

**Chunk 23 additive correction (2026-09-28, operator-authorized).** `SCHEMA_VERSION` is
bumped `"1.0.0"` → `"1.1.0"` and `category_scores` gains exactly one nullable column,
`discovery_failure_cause_json TEXT`, appended last in the DDL and in
`models.CategoryScoreRecord` (so `TABLE_COLUMNS["category_scores"] ==
models.MANDATORY_ROW_FIELDS["category_scores"]` still holds). It carries the redacted,
canonical-JSON discovery failure cause (`{"attempt_count": int, "failure_class": str,
"http_status": int | null, "page_index": int}`, or `NULL` when there is no recorded
cause). Accepted consequence: an existing `"1.0.0"` database raises `SchemaVersionError`
on open and is **not** migrated and **not** altered; the DDL is applied only as
`CREATE ... IF NOT EXISTS`, so a stale table is never rewritten. No other table, column,
index, constant, or protocol signature changes.

`TABLE_INDEXES` is `dict[str, str]` in the implementation (one index,
`idx_raw_discovery_observations_run_category_ordinal`). The Chunk 0 interface
file annotates the value as `tuple[str, ...]`; the **key set** is what this
chunk's tests assert, so consumers must iterate keys or use the DDL text rather
than indexing into a tuple.

`TABLE_COLUMNS[table]` equals `models.MANDATORY_ROW_FIELDS[table]` exactly for
all five tables (asserted by `tests/test_contracts.py:921`).

Primary keys (unchanged): `runs` → `run_id`; `raw_discovery_observations` →
`observation_id`; `sample_members` → `(run_id, category, asset_identity_key)`;
`enrichment_observations` → `(run_id, asset_identity_key)`; `category_scores` →
`(run_id, category)`.

### 2.2 Exceptions

```python
class DatabaseError(RuntimeError): ...
class RepositoryError(DatabaseError): ...            # invalid lifecycle state
class ClosedRepositoryError(RepositoryError): ...    # any method after close()
class SchemaVersionError(DatabaseError): ...         # metastore version mismatch
class UniqueConstraintViolation(DatabaseError): ...  # duplicate logical row
class ForeignKeyConstraintViolation(DatabaseError): ...  # unknown run_id
class InvalidRecordValueError(DatabaseError): ...    # value cannot be encoded
```

`ClosedRepositoryError` and `SchemaVersionError` subclass `RepositoryError` and
`DatabaseError` respectively (i.e. they are *not* aliases for the names in
`tests/test_contracts.py` — `niche_scout.database.DatabaseError` is the base).
Catching `DatabaseError` catches every persistence failure this module raises.

| Condition | Exception |
|---|---|
| Duplicate `(run_id, category, asset_identity_key)` in `sample_members` | `UniqueConstraintViolation` |
| Duplicate `(run_id, category)` in `category_scores` (plain insert) | `UniqueConstraintViolation` |
| Duplicate `run_id` in `runs` | `UniqueConstraintViolation` |
| Duplicate `(run_id, asset_identity_key)` in `enrichment_observations` | `UniqueConstraintViolation` |
| Duplicate `observation_id` in `raw_discovery_observations` | `UniqueConstraintViolation` |
| Child row for an unknown `run_id` | `ForeignKeyConstraintViolation` |
| Non-UTC / naive datetime, or an enum-backed value outside its allowed set | `InvalidRecordValueError` |
| Any method after `close()` | `ClosedRepositoryError` |
| `schema_metadata.schema_version` ≠ `SCHEMA_VERSION` | `SchemaVersionError` |
| Raw-append called outside a `category_transaction`, or a second outer `transaction()` | `RepositoryError` |
| `update_run_status` for an unknown `run_id` | `KeyError` |
| `batch_size < 1` on `append_raw_discovery_observations` | `ValueError` |
| Savepoint name not matching `[A-Za-z_][A-Za-z0-9_]*` | `ValueError` |

**Redaction (LREQ-SEC-020):** every exception message names table and column
names only. No message contains a record value, an identity string, a JSON
payload, a header, a token, or a bound parameter. Duplicate-key messages report
the key *column names* and never the key *values*.

### 2.3 `SqliteRepository` — construction and lifecycle

```python
class SqliteRepository:
    def __init__(
        self,
        db_path: "Path | str",
        *,
        initialize: bool = True,
        busy_timeout_ms: int = 5000,
        synchronous: str = "NORMAL",
        create_parent_directory: bool = True,
    ) -> None: ...

    @classmethod
    def connect(cls, db_path: "Path | str", *, initialize: bool = True,
                busy_timeout_ms: int = 5000, synchronous: str = "NORMAL",
                create_parent_directory: bool = True) -> "SqliteRepository": ...

    @property
    def db_path(self) -> Path: ...
    @property
    def schema_version(self) -> str: ...
    @property
    def is_closed(self) -> bool: ...
    @property
    def connection(self) -> sqlite3.Connection: ...  # diagnostics/read-only inspection only

    def close(self) -> None: ...
    def __enter__(self) -> "SqliteRepository": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...  # always closes; never swallows
```

- `__init__` opens the connection immediately, applies and verifies the four
  pragmas, and (when `initialize=True`) calls `initialize_schema()`.
- `close()` is idempotent; a second call is a no-op. After `close()`, every
  method raises `ClosedRepositoryError` — never a silent no-op.
- `create_parent_directory=True` creates the parent directory with
  `pathlib.Path.mkdir(parents=True, exist_ok=True)`.
- `SqliteRepository` satisfies the frozen `Repository` **structurally**; it does
  not subclass or shadow it, and the protocol is not re-declared.

### 2.4 `SqliteRepository` — schema

```python
def initialize_schema(self, *, check_version: bool = True) -> str: ...
```

- Creates the private metastore
  `schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)` holding
  `("schema_version", SCHEMA_VERSION)` and `("applied_at_utc", <ISO-8601 UTC>)`.
  This table is **not** one of the five SRS tables and is absent from
  `TABLE_COLUMNS`/`TABLE_PRIMARY_KEYS`/`TABLE_INDEXES`. Do not treat it as data.
- Applies `DDL_STATEMENTS` in order as `CREATE ... IF NOT EXISTS`; an existing
  table is left untouched. Running it twice is a no-op returning the same
  version.
- Raises `SchemaVersionError` when the stored version differs from
  `SCHEMA_VERSION`; it never migrates silently and never deletes data.
- Raises `DatabaseError` when `foreign_keys` is not `1`.
- No `ALTER TABLE`, no column addition, no destructive migration.
- **Chunk 23 exception (2026-09-28, operator-authorized).** The one column addition
  recorded in §2.1 (`category_scores.discovery_failure_cause_json`) IS the DDL change
  authorized for this repository; it ships as part of `SCHEMA_VERSION = "1.1.0"`. This
  paragraph is the single authorized deviation from the no-column-addition rule above,
  and it does not relax that rule for any other column, table, or index.

### 2.5 `SqliteRepository` — pragmas (applied on every connection, in this order)

| Pragma | Value | Verified by the implementation |
|---|---|---|
| `PRAGMA foreign_keys = ON` | ON | read back, must be `1` |
| `PRAGMA journal_mode = WAL` | `wal` | read back, must be `"wal"` |
| `PRAGMA busy_timeout = <busy_timeout_ms>` | `5000` | read back, must equal the configured value |
| `PRAGMA synchronous = <synchronous>` | `NORMAL` | read back as integer `1`, compared against the *name* that level denotes |

These four pragmas are **local implementation choices**. No requirement in
`SRS-lean.md` or `requirements-dependency-map.md` names a pragma, a journal
mode, or a concurrency behavior. `foreign_keys` is set per connection because
SQLite does not persist it in the file, so a reopened connection re-applies it.

### 2.6 Transaction regime and isolation semantics

```python
@contextmanager
def transaction(self) -> Iterator["SqliteRepository"]: ...
@contextmanager
def savepoint(self, name: str) -> Iterator["SqliteRepository"]: ...
@contextmanager
def category_transaction(self, run_id: str, category: str) -> Iterator["SqliteRepository"]: ...
def in_category_transaction(self) -> bool: ...
```

**Connection regime.** `sqlite3.connect(str(path))` is called with **no
`isolation_level` argument**, i.e. pysqlite's default (`""`). This is *not*
`isolation_level=None` autocommit. Under the default, an implicit `BEGIN` opens
before the first DML of a unit of work and is committed or rolled back only when
this module asks — which is what makes `transaction()`'s rollback-on-error
promise real rather than nominal. This is an internal mechanism change recorded
in plan §12.2 item 1; the published constructor signature never had an
`isolation_level` parameter and still does not.

**Boundary ownership** is decided by the module's own
`_outermost_transaction_depth` counter, never by
`sqlite3.Connection.in_transaction` (pysqlite's default makes `in_transaction`
true after *any* plain DML call, including one outside any `transaction()`).
A block that owns the boundary issues a real `BEGIN` first.

- `transaction()` commits on clean exit and rolls back on exception. Opening a
  second outer `transaction()` on the same instance raises `RepositoryError`.
  It is not entered from inside an active category block.
- `savepoint(name)` issues `SAVEPOINT <name>`; `RELEASE` on clean exit,
  `ROLLBACK TO <name>` plus `RELEASE` on exception. `name` must match
  `[A-Za-z_][A-Za-z0-9_]*` or `ValueError` is raised (SQLite cannot
  parameterize savepoint names). Nesting savepoints is **not** capped.
- `category_transaction(run_id, category)` is the category-isolated unit of
  work. It may be nested inside `transaction()` (then it is a savepoint) or used
  on its own (then it opens and owns the outermost transaction). A second
  nested `category_transaction` raises `RepositoryError`.
  - **Failure:** the block's savepoint is rolled back; if the block owned the
    outermost transaction it is rolled back too (so no write lock is left
    behind). The original exception propagates unchanged.
  - **Success:** the savepoint is released and, if this block opened the
    transaction, it is committed.
  - The depth counter is reset in a `finally`, so a block that *raised* cannot
    leave the instance permanently unable to open a transaction. After a failed
    category block `in_category_transaction()` is `False` and
    `connection.in_transaction` is `False`.
- **Threading:** one instance is single-thread and single-connection, reusing
  one `sqlite3.Connection`. There is no thread-sharing, pool, or re-entrancy
  guarantee beyond savepoint nesting. A second outer `transaction()` raises.
- Uncommitted work is never visible to a second connection; commit-on-clean-exit
  is the mechanism.

### 2.7 Write APIs

```python
# Runs
def insert_run(self, run: RunRecord) -> None: ...
def update_run_status(self, run_id: str, status: str,
                      completed_at_utc: Optional[datetime] = None) -> None: ...
def update_run_preflight(
    self, run_id: str, *, identity_preflight_status: Optional[str] = None,
    identity_preflight_summary_json: Optional[str] = None,
    graphql_operation_correlation_mode: Optional[str] = None,
    page_view_semantics_status: Optional[str] = None) -> None: ...

# Category status
def set_category_status(self, run_id: str, category: str, discovery_status: str,
                        *, computed_at_utc: Optional[datetime] = None,
                        discovery_failure_cause_json: Optional[str] = None) -> None: ...

# Raw discovery observations
def insert_raw_discovery_observations(
    self, observations: Sequence[RawDiscoveryObservationRecord]) -> None: ...
def append_raw_discovery_observations(
    self, observations: "Iterable[RawDiscoveryObservationRecord]",
    *, batch_size: int = 500) -> int: ...
def update_raw_discovery_identity(
    self, observations: "Iterable[RawDiscoveryObservationRecord]") -> int: ...

# Sample members
def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None: ...
def upsert_sample_members(self, members: Sequence[SampleMemberRecord]) -> int: ...

# Enrichment observations
def insert_enrichment_observations(
    self, observations: Sequence[EnrichmentObservationRecord]) -> None: ...
def upsert_enrichment_observation(self, observation: EnrichmentObservationRecord) -> None: ...

# Category scores
def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None: ...
def upsert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> int: ...
```

- `update_run_status` accepts only `running` / `completed` / `failed`
  (`RunStatus` values); anything else raises `InvalidRecordValueError`. It
  raises `KeyError` for an unknown `run_id` (a silent no-op would hide an
  orchestration bug). `completed_at_utc=None` **leaves the stored value
  unchanged**; an aware UTC datetime sets it. It never reads the clock.
- `update_run_preflight` writes only the fields whose keyword is not `None`.
- **`set_category_status(run_id, category, discovery_status, *, computed_at_utc)`**
  upserts into `category_scores`: it writes `discovery_status` for that one
  `(run_id, category)` row and **creates the row on first write if it does not
  exist yet**, because discovery precedes scoring and the row is populated
  incrementally over the run's lifetime. The insert half fills only the
  discovery-phase columns the caller can know plus the frozen `NOT NULL`
  defaults the DDL requires; every scoring-phase column stays at its pre-scoring
  default for `upsert_category_scores` to finalize later. It leaves every other
  `(run_id, category)` row untouched.
  **Chunk 23 additive correction (2026-09-28, operator-authorized).**
  `discovery_failure_cause_json` is a new optional keyword-only parameter. When it is
  `None` — the default, and the only value the scoring-phase `upsert_category_scores`
  ever sees — the stored column is **left unchanged** by the conflict path, so
  finalizing a scored row cannot null a cause written earlier. When it is a string, the
  value is validated as canonical JSON text (`json.dumps(..., sort_keys=True,
  separators=(",", ":"))`) and written on both the insert and the conflict path. The
  value is stored exactly as given (`*_json` codec, §2.9) and is never re-serialized;
  `NULL` means "no recorded cause" and is never `""`.
  **`computed_at_utc` is required.** `CategoryScoreRecord.computed_at_utc` is a
  non-optional `datetime` and this module never reads the system clock, so a
  `None` raises `InvalidRecordValueError` and **writes nothing**. A conflicting
  `(run_id, category)` update always assigns the supplied value; there is no
  path that overwrites an already-scored row's timestamp with `NULL`.
- `append_raw_discovery_observations` consumes the iterable **incrementally**:
  at most `batch_size` records are held in memory, then written with one
  `executemany` per batch. It never calls `list()` on the argument and never
  builds a second full-size container. `batch_size` must be an `int >= 1`
  (`bool` rejected); otherwise `ValueError`.
  - **Precondition:** it SHALL only be called from inside an active
    `category_transaction(run_id, category)` block. Called outside one it
    raises `RepositoryError` **before consuming the iterable**. It does not open
    a transaction of its own, because category isolation is the caller's
    declaration, not something the sink may infer from the records.
  - **Batch failure:** a mid-stream failure raises `DatabaseError` naming the
    record count and the count already written — never record content. The
    rollback boundary is the **enclosing `category_transaction`'s savepoint**,
    which covers every batch prefix already written for that category. No
    per-batch savepoint is opened (plan §12.2 item 3): a released per-batch
    savepoint could not undo an already-written prefix, so the enclosing
    category savepoint is the only boundary that makes the guarantee real. A
    constraint failure still raises `UniqueConstraintViolation`.
  - Returns the number of rows written.
- `insert_raw_discovery_observations(observations)` is the frozen protocol's
  batch convenience: it is `append_raw_discovery_observations(observations,
  batch_size=max(1, len(observations)))` and carries the **same**
  inside-`category_transaction` precondition.
- `update_raw_discovery_identity(observations)` updates **only** the four
  post-discovery columns `asset_identity_key`, `stratum_index`, `is_duplicate`,
  `duplicate_of_observation_id`, matched by `observation_id`. Returns the number
  of rows updated. The caller must set `is_duplicate=True` and
  `duplicate_of_observation_id` for duplicate canonical records; that is how the
  `(run_id, category, discovery_ordinal)` index stays honest.
- Plain inserts are the **default** for every table; nothing upserts silently.
  Every upsert method above is an explicitly named path with a documented
  effect: `upsert_sample_members` rewrites the summary columns of an existing
  membership (it cannot create a second membership);
  `upsert_enrichment_observation` rewrites every non-key column of the one row
  for `(run_id, asset_identity_key)`; `upsert_category_scores` rewrites every
  non-key column of an existing `(run_id, category)` row. Upsert methods return
  the number of rows written; `insert_*` methods return `None`.
- No repository method deletes a row, drops a table, or rewrites a committed
  category's observations as a side effect of another category's failure.

### 2.8 Read and count APIs

```python
def get_run(self, run_id: str) -> Optional[RunRecord]: ...
def iter_raw_discovery_observations(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservationRecord]: ...
def stream_raw_discovery_observations(self, run_id: str) -> Iterator[RawDiscoveryObservationRecord]: ...
def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]: ...
def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...

def count_raw_discovery_observations(self, run_id: str, category: str) -> int: ...
def count_distinct_enrichment_observations(self, run_id: str) -> int: ...
def count_discovery_observations(self, run_id: str) -> int: ...
def count_sample_members(self, run_id: str) -> int: ...
def count_distinct_enrichment_identities(self, run_id: str) -> int: ...
```

- All reads reconstruct the frozen dataclasses **column-by-column** from the
  row, never by echoing the input object, so a round trip is genuinely
  exercised. Datetimes come back timezone-aware UTC; nullable columns come back
  as `None`.
- Ordering is fixed: `iter_raw_discovery_observations` by `discovery_ordinal`
  ASC then `observation_id` ASC; `get_sample_members` by `stratum_index` ASC
  then `sample_rank_within_stratum` ASC; `get_category_scores` by `category`
  ASC (lexical, matching LREQ-SEN-020's deterministic tie-break).
- `get_run`, `get_enrichment_observation` return `None` when absent.
  `get_category_scores` and `get_sample_members` return `tuple[...]`.
- `iter_raw_discovery_observations` is lazy and streams from a cursor; an
  abandoned iterator does not hold a write lock.
- The five `count_*` methods issue a single `SELECT count(...)` /
  `COUNT(DISTINCT ...)` and never materialize rows.
  `count_discovery_observations(run_id)` is the run-wide discovered-canonical
  count; `count_sample_members(run_id)` the run-wide sampled member count;
  `count_distinct_enrichment_identities(run_id)` the run-wide count of distinct
  `asset_identity_key` values in `enrichment_observations` (equal to that
  table's row count for the run, because `(run_id, asset_identity_key)` is its
  primary key). These three are this chunk's supporting-contract obligation for
  **LREQ-NFR-020** — Chunk 6B's pre-enrichment log statement calls them.
  `count_raw_discovery_observations(run_id, category)` and
  `count_distinct_enrichment_observations(run_id)` are the per-category and
  alternate-spelling helpers and are equally public.
- **This chunk logs nothing.** LREQ-NFR-020's log line is Chunk 6B's; the SRS
  `Module` column for it names `collector.py`/`pipeline.py`.

### 2.9 Column codec

| Kind | Encoding | Read back as |
|---|---|---|
| `bool` | `INTEGER` `0`/`1` | `bool` |
| `datetime` | `TEXT` ISO-8601 UTC | timezone-aware UTC `datetime` (same instant) |
| `Optional[...]` | SQL `NULL` | `None` — **never** `0`, `0.0`, `""`, or `False` |
| `*_json` | `TEXT`, stored **exactly as given** | the same text; never re-serialized or normalized |
| `int` / `float` | `INTEGER` / `REAL` | `int` / `float` |

Enum-backed columns are validated against their allowed frozen value sets before
writing; an out-of-set value raises `InvalidRecordValueError`.

**Supplied values win over implicit defaults (plan §12.2 item 6).** The frozen
DDL declares **no `DEFAULT` clause**, so a `NOT NULL` column with no record
value has no value the database can supply. The module therefore holds a
pre-scoring default for those columns and applies it **only when the record
supplies `None`**. A record that supplies a value for such a column keeps it —
returning a supplied `usable_demand_sample_count=72` as `0` would be exactly the
"never as `0`" violation. This applies to the plain-INSERT path for all five
tables; the `upsert_category_scores` conflict path binds the full column set.

---

## 3. Behavioral contracts downstream chunks may rely on

- **Module boundary** — `database.py` is the only `sqlite3` importer;
  `metrics.py`/`scoring.py` stay pure and clock-free.
- **No fabricated values** — no `value or 0`, no
  `value if value is not None else 0.0`, no zero sentinel for a failed
  operation. `enrichment_observations.product_page_views` round-trips as `NULL`
  on a failed PageViews operation.
- **`(run_id, category)`** is enforced for `category_scores`; **duplicate
  sample membership** is rejected by the `sample_members` primary key (the
  constraint is the enforcement point, not a pre-INSERT `SELECT`).
- **At most one enrichment row per `(run_id, asset_identity_key)`** — a second
  plain insert raises `UniqueConstraintViolation`; the upsert path overwrites
  the single existing row. This is the LREQ-GQL-080 persistence guarantee.
- **Category isolation** — a failure inside `category_transaction` rolls back
  only that category's block. Other categories and previously committed run rows
  remain committed, and the instance is immediately usable again.
- **Streaming** — `append_raw_discovery_observations` accepts a single-pass,
  non-seekable iterator and never materializes it (LREQ-NFR-010 persistence
  side).
- **No alias columns** in `category_scores`: `sample_size`,
  `demand_usable_count`, `recent_supply_usable_count`, and
  `quality_usable_count` do not exist, and the persisted column set equals
  `TABLE_COLUMNS["category_scores"]` exactly.
- **No schema invention** — no new table (other than the private
  `schema_metadata`), no new column, no `ALTER TABLE`, no index beyond the
  frozen one. **Chunk 23 exception (2026-09-28, operator-authorized):**
  `category_scores.discovery_failure_cause_json` (§2.1) is the one authorized column,
  and it is carried by `models.CategoryScoreRecord` and
  `models.MANDATORY_ROW_FIELDS["category_scores"]`; no other column, table, index, or
  `ALTER TABLE` is introduced.

---

## 4. What downstream chunks must NOT expect from Chunk 2

- No sampling selection, `N_h`/`n_h` computation, stratum construction, overlap
  computation, or census decision — **Chunk 4A/4B**. This chunk persists what
  4B computes.
- No identity resolution, canonical population construction, or denominator
  enforcement — **Chunks 1, 3, 4A**.
- No network streaming, pagination, or memory behavior — **Chunk 3**. This
  chunk provides the sink; Chunk 3 owns the producer.
- No at-most-once enrichment decision, preflight gate, or result join to
  referencing categories — **Chunks 6A/6B**.
- No run orchestration, category-failure policy, or completion status decision —
  **Chunk 10**. This chunk provides the transition APIs; Chunk 10 calls them.
- No metric eligibility, normalization, scoring, sensitivity diagnostics, report
  rendering, or CLI behavior — **Chunks 7A–12**.
- **No logging of any kind**, and specifically not LREQ-NFR-020's counts — the
  counts are readable, the log line is Chunk 6B's.
- **No `category_status` column.** Category-level failure has no dedicated
  persisted column; it is carried by the existing
  `category_scores.discovery_status`, `warnings_json`, `evidence_grade`, and
  `rankability_status` (dependency map §6.5). A standalone `category_status`
  column would be a documented schema change; the frozen DDL has none. **Chunk 23
  exception (2026-09-28, operator-authorized):** `discovery_failure_cause_json` is a
  redacted *cause* field, not a status enum and not a `category_status` column; the
  status stays carried by the four existing fields.
- **No end-to-end acceptance verification** — Chunk 13 owns LREQ-TST-080/090.

---

## 5. Requirement ownership roles recorded by this chunk

Primary owner: **`LREQ-SEC-020`** (the SQLite clause and the persisted
error-message clause; completed by Chunk 13).

Supporting contract chunk (persistence only, explicit): **`LREQ-SMP-080`**
(completed by Chunks 4B/6B), **`LREQ-GQL-080`** (completed by Chunk 6B),
**`LREQ-NFR-010`** (completed by Chunk 3).

Supporting chunk, no primary claim: **`LREQ-NFR-020`** (primary Chunk 6B,
completed by Chunk 10), plus `LREQ-EXT-050`, `LREQ-EXT-070`, `LREQ-EXT-090`,
`LREQ-GQL-050`, `LREQ-ID-010`, `LREQ-ID-020`, `LREQ-ID-040`, `LREQ-NRM-020`,
`LREQ-SEN-020`, `LREQ-RPT-020`, `LREQ-TST-080`.

Test module: `tests/test_database.py` (23 marked tests, all passing), with
23 matching `tests/traceability.json` entries. Two matrix `Required tests`
references — `LREQ-TST-040` (GraphQL protocol, `test_collector.py`/
`test_identity.py`) and `LREQ-TST-020` (`test_sampling.py`) — are deliberately
**not** attached here: they belong to files Chunks 5 and 4A/4B own, and
attaching them to a persistence test would be a fabricated mapping
(plan §12 Q6). Full closure of `LREQ-GQL-080`/`LREQ-SMP-080`'s required-test
sets happens when those chunks land.

**Chunk 23 additive amendment (2026-09-28, operator-authorized).**
`SCHEMA_VERSION` is `"1.1.0"` (§2.1); `category_scores` has one additional nullable
column, `discovery_failure_cause_json` (§2.1, §2.4, §2.7); `set_category_status` gained
the keyword-only `discovery_failure_cause_json` parameter (§2.7); and
`models.CategoryScoreRecord` / `models.MANDATORY_ROW_FIELDS["category_scores"]` gain the
matching field. No other frozen name changed and no downstream chunk is re-scoped.

---

## 6. Known exception in the repository-wide suite (not a Chunk 2 defect)

`python -m pytest tests -q` reports **91 passed, 1 failed**; the single failure
is `tests/test_contracts.py::test_repository_protocol_and_schema_specification`
at line 938:

```python
assert "sqlite3" not in (SRC / "niche_scout" / "database.py").read_text(encoding="utf-8")
```

That assertion encodes Chunk 0's "no execution" state and is invalidated by
Chunk 2's defining scope: this chunk's goal *is* to put the physical SQLite
implementation — including `import sqlite3` — into `database.py`, and it leaves
`SCHEMA_VERSION`, `DDL_STATEMENTS`, `CREATE_TABLE_STATEMENTS`, `TABLE_COLUMNS`,
`TABLE_PRIMARY_KEYS`, `TABLE_INDEXES`, and every `Repository` protocol signature
byte-identical. `tests/test_contracts.py` is not in Chunk 2's plan §6 file list,
so Chunk 2 does not edit it; the assertion's disposition is a **Chunk 0
document-consistency action**.

pytest reports only the first failure per node, so this node also masks the
assertions at `:918`, `:921`, `:922`, and `:930`. A pre-gate diagnostic
evaluated all 31 assertions in that node independently: **30 PASS, 1 FAIL, and
the failure is `:938` itself** — in particular the exact tuple equality
`TABLE_COLUMNS[table] == models.MANDATORY_ROW_FIELDS[table]` holds for all five
tables. The diagnostic scripts were scratch artifacts and have been deleted per
`.scratch/README.md`; the measurement they produced is recorded in plan §12.2
and in the Chunk 2 gate report.

`python -m pytest tests -q --collect-only` reports **92 tests**, of which
`tests/test_database.py` contributes 23.

---

## 7. Traceability

- `python -m niche_scout.tools.validate_traceability` → exit 0,
  `Traceability valid: 7 Chunk 0 requirements mapped, 92 matrix nodes, 89 defined LREQ IDs`.
- `python -m niche_scout.tools.check_import_boundaries` → exit 0,
  `Import boundaries valid for metrics.py, scoring.py`.
- `validate_traceability.py` remains hard-wired to Chunk 0's requirement block;
  widening it is **deferred to Chunk 13**. Its completeness direction therefore
  does **not** cover Chunk 2, and every chunk between now and Chunk 13 must
  manually cross-check its plan's LREQ table against the actual
  `@pytest.mark.lreq` markers and `tests/traceability.json` entries. Its
  marker-without-entry direction still runs and did pass here.

---

## 8. Chunk 30 revision — read API addition (2026-09-30)

Operator-authorized (chunk-30 D-3; plan `chunk-30-dark-mode-plotly-dashboard.md` §2/§12).
Additive to §2.8; no existing read changes.

- `SqliteRepository.get_latest_run_id(self) -> Optional[str]` — the `run_id` of the run with
  the greatest decoded `run_started_at_utc`; ties break to the lexicographically smallest
  `run_id`; `None` when `runs` is empty. Selection is performed in Python over
  `SELECT run_id, run_started_at_utc FROM runs` because `_encode_column` writes
  `datetime.isoformat()` with variable-width fractional seconds, so a SQL `ORDER BY` on the
  TEXT column is not reliably chronological. Read-only, deterministic, no clock read, no
  network. Added to the `Repository` protocol by `chunk-00.md` §12.
