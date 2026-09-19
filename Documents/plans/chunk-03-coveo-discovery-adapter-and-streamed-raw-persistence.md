# Chunk 3 — Coveo discovery adapter and streamed raw persistence

Status: VERIFIED
Status footnote (added 2026-09-18, by operator ruling, after empirical
re-derivation; corrected 2026-09-18 to make its first sentence self-contained and
to label each test total by the run that produced it): what changed on
2026-09-18 is this footnote and nothing else — the verification text at the end
of it now carries the run-by-run totals and a superseded-figure note in place of
the bare `119` line that this edit replaced. `Status: VERIFIED` on the line
above is retained deliberately and is unchanged; the suite it was awarded over
is **not** green at this record's working-tree state: `python -m pytest tests/ -q`
reports **6 failed / 140 passed**, and `tests/test_collector.py` reports
**6 failed / 47 passed** (both counts re-derived by three independently shaped
pytest invocations). All six failing node IDs belong to **Chunk 5's
still-in-development test family** and live in `tests/test_collector.py`:
`test_adapter_cannot_bulk_enrich_or_consult_preflight_state` (`LREQ-GQL-010`),
`test_null_required_data_and_wrong_data_shape_are_operation_errors`
(`LREQ-GQL-040`), `test_invalid_state_value_and_missing_identity_are_operation_errors`
(`LREQ-GQL-040`), `test_failed_operation_fields_are_none_never_zero`
(`LREQ-GQL-050`), `test_state_excluded_and_unknown_assets_remain_recorded`
(`LREQ-GQL-060`), and `test_request_metadata_json_carries_required_fields_without_secrets`
(`LREQ-SEC-020`). None of the six documents a defect in a file this chunk owns
(`collector_coveo.py`, `validation.py`, `models.py`); all six defects and all six
fix sites are in Chunk 5's file set (`collector_graphql.py`,
`tests/fixtures/graphql_fixtures.py`). One disclosure so this record is not
overstated: three of the six nodes *execute* Chunk 1/3-owned primitives — the
`validation.py` identity-group rule and `models.py` `OperationStatus` — while
their defects remain Chunk 5's classification logic, and the Chunk 5 plan's §6
lists `validation.py` and `models.py` as deliberately not touched. Chunk 3's own
gate bullets remain satisfied, so this Status is **not** flipped. This footnote
is a record correction, not a re-verification; it does not re-open §10's bullets.
The six failures are named here rather than omitted: six tests do fail.
Verified at: working tree state 2026-09-17; `python -m pytest tests/ -q`
(119 passed, exit 0), `python -m niche_scout.tools.validate_traceability`
(exit 0), `python -m niche_scout.tools.check_import_boundaries` (exit 0).
That same `119 passed, exit 0` sentence is **superseded by the footnote above**:
it was not re-checked in the 2026-09-18 re-derivation and it is **not** the tree
that reports 6 failed / 140 passed. The totals actually observed are
`python -m pytest tests -q` → **6 failed, 140 passed** (146 collected node IDs)
and `python -m pytest tests/test_collector.py -q` → **6 failed, 47 passed**,
both run 2026-09-18 against the working tree that has front-matter and
append-only changes from this record's correction pass only; the **6 failed,
139 passed** recorded in `Documents/plans/tooling-p0-2-traceability-blind-spot.md`
(its §12.1) is the earlier run this one supersedes. The `119 passed, exit 0` in
the line above is kept as the historically recorded figure for the 2026-09-17
state and is not reconciled here: it is stale, and no artifact in this repository
documents the exact suite composition that produced it.
Published contract: `Documents/interfaces/chunk-03.md`.
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-00.md` (VERIFIED — models, constants, `config.py`
    contracts, schema/PK specification, `RunStatus`/`DiscoveryStatus`/
    `WarningCode`/`IdentityResolutionStatus`/`CategoryFilterValidationStatus`
    enums, `to_json`/`to_json_dict`/`ensure_utc`)
  - `Documents/interfaces/chunk-01.md` (VERIFIED — taxonomy, identity,
    exact-category-match, structural-validation, and redaction primitives;
    **one obligation this file places on Chunk 3 remains UNMET and OPEN** — the
    §4.1 URI trailing-identifier extraction rule is inferred and
    **unverified**, and its verification is deferred to a future capture. This
    chunk did not perform it and does not claim to have discharged it; see §8,
    §12.9, and `interfaces/chunk-03.md` §8. No real captured Coveo response
    exists anywhere in the repository)
  - `Documents/interfaces/chunk-02.md` (VERIFIED — `SqliteRepository`,
    `category_transaction`, `insert_raw_discovery_observations` (the page sink,
    §4/§7), `append_raw_discovery_observations`, `update_raw_discovery_identity`,
    `set_category_status`, `in_category_transaction`, read/count APIs)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  - Chunk 4A (`LREQ-SMP-010` supporting chunk is Chunk 3; ordinal ordering source)
  - Chunk 6A / 6B (preflight + enrichment consume discovered canonical identities)
  - Chunk 7B (`LREQ-MET-070` names Chunk 3 as a supporting chunk)
  - Chunk 9A (`LREQ-EVD-020` supporting chunk)
  - Chunk 10 (`LREQ-EXT-090` completion chunk; `LREQ-NFR-030` supporting chunk)
  - Chunk 13 (`LREQ-TST-040`, `LREQ-SEC-010` verification)

## 1. Goal

Make Coveo category discovery real and audit-safe: a live, rate-limited,
retried, facet-filtered paginated search against the parent-SRS Coveo endpoint
that streams every raw observation into the Chunk 2 persistence API inside an
active per-category transaction, assigns each record a stable first-valid
discovery ordinal, marks duplicate re-emissions of an already-seen canonical
identity as separate duplicate rows, classifies each record's identity and
category-filter status through the Chunk 1 primitives, and selects a single
terminal `discovery_status` per category — without ever loading a category's
complete result set into memory and without ever turning a failed or truncated
page into zero assets.

## 2. Scope

### In scope

- Coveo request construction from the captured template
  (`config/coveo_search_template.json`, §12.1): endpoint, required headers,
  `fieldsToInclude`, facet/`currentValues` selection, sort order, page size, and
  offset pagination (`LREQ-EXT-010`, `LREQ-EXT-030`, `LREQ-EXT-040`).
- A discovery-only response reader over the exact five-field set, structurally
  validated through Chunk 1 (no rating/page-view/price/date fields sourced from
  Coveo) (`LREQ-EXT-040`).
- Pagination loop with verified `totalCount` handling, natural terminal page,
  cap truncation, per-page failure isolation, per-category `request_failed`
  handling, and deterministic terminal `discovery_status` selection
  (`LREQ-EXT-050`).
- Ordinal assignment, duplicate classification, and the *collection-side*
  completion of Coveo identity resolution (`LREQ-EXT-050`, `LREQ-EXT-060`,
  `LREQ-EXT-070` Coveo caller side).
- Coveo-side exact-category-filter validation integrated through
  `match_exact_category`, including scalar vs. multi-valued `ec_category`
  (`LREQ-EXT-080`).
- Discovery-quality conditions turned into `DiscoveryStatus` values and the
  *recorded* conditions that make a warning and a non-rankable competition
  outcome mandatory (`LREQ-EXT-090`).
- Rate limiting and retry/backoff for transient `429`/`5xx`, with no endless
  retry of permanent auth/CSRF/malformed-request/authorization failures
  (`LREQ-EXT-100`).
- Streamed persistence of raw observations into
  `insert_raw_discovery_observations` inside `category_transaction`, including
  nullable `asset_identity_key`/`stratum_index`, identity-resolution status and
  reason, category-value JSON, category-filter status, and redacted error
  summaries (`LREQ-NFR-010`).
- Per-category failure isolation: one category's failed page or request never
  aborts another category or asset, and the failure stays visible in the
  persisted status fields (`LREQ-NFR-030`).
- Redacted request metadata and error summaries; never a credential, header
  value, or raw response body (`LREQ-SEC-010` consumer side, `LREQ-SEC-020`
  integration support).

### Explicitly out of scope (and who owns it instead)

- **Canonical population construction, ordinal-ordered population, strata,
  selection, and `LREQ-SMP-020`'s retained-first-ordinal population rule** —
  Chunk 4A is the primary implementation chunk. Chunk 3 is only the supporting
  contract chunk: it *assigns and persists* `discovery_ordinal` and records
  duplicates; it does not build a canonical population or sample.
- **Post-discovery identity canonicalization, duplicate linkage, and stratum
  assignment updates** — the dependency map's Chunk 3 description names these
  as later lifecycle steps; the canonical-record update path belongs to
  Chunks 4A/4B and the update API is Chunk 2's
  `update_raw_discovery_identity`. Chunk 3 persists the discovery-time record
  only (with `asset_identity_key` nullable).
- **GraphQL enrichment, correlation, and operation-level status** —
  Chunk 5 (`collector_graphql.py`), running in parallel. Chunk 3 plans **no**
  edit to that module and does not call it. Chunk 5's GraphQL protocol test
  family is also appended to `tests/test_collector.py` — the module §6 lists as
  *this* chunk's new test file — so that file currently holds both chunks'
  nodes; see the Status footnote at `:4-47`.
- **Identity-preflight planning and gating** — Chunk 6A. **Unique enrichment
  and reuse** — Chunk 6B.
- **`LREQ-EXT-090`'s warning emission and rankability suppression** — Chunk 10
  is the completion chunk for `LREQ-EXT-090` and the primary implementation
  chunk for `LREQ-NFR-030`; Chunk 12 renders the warning. Chunk 3 completes the
  *discovery-side* behavior only (detect the condition, persist it as a
  `DiscoveryStatus`, and expose the per-category condition set on its result);
  see §12.2.
- **Metric eligibility and estimators** — Chunks 7A/7B. Chunk 3 never decides
  whether a value is usable for a metric.
- **Report/CLI behavior, exit codes, run-level status transitions, and the
  run-wide orchestration sequence** — Chunks 10/12.
- **Traceability-validator widening** — Chunk 13 (`LREQ-NFR-060`); see
  `interfaces/chunk-01.md` §6.

## 3. Requirements this chunk must satisfy

Ownership roles below are the dependency map's own labels. Matrix source:
`requirements-dependency-map.md` lines 50–59, 68–69, 121 (`§Ownership and test
traceability matrix`) and 153–163 (`§Coveo discovery and external collection`).
LREQ-SMP-010 (line 74), LREQ-MET-070 (line 89), LREQ-EVD-020 (line 104),
LREQ-TST-040 (line 130), LREQ-TST-030 (line 129), and LREQ-SMP-020 (line 75) are
consulted for the ownership statements in the "Ownership role here" column and in
§12.2.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EXT-010 | Primary implementation chunk | "Discovery SHALL use the parent SRS Coveo endpoint, required headers, captured taxonomy template, and selected-category facet mechanism." | §4.1 |
| LREQ-EXT-030 | Primary implementation chunk | "The Coveo request SHALL contain no free-text `q` or `query` field that could contaminate category filtering with keyword relevance." | §4.1 |
| LREQ-EXT-040 | Primary implementation chunk | "Discovery SHALL use the parent SRS discovery-only field set: `permanentid`, `ec_product_id`, `ec_name`, `ec_category`, and `publisher_name`. Product rating, page views, publication date, and price SHALL NOT be sourced from Coveo for scoring." | §4.1 |
| LREQ-EXT-050 | Primary implementation chunk | "For every requested category, discovery SHALL retrieve all available pages using the same endpoint, filters, sort order, page size, pagination rules, and category predicate. It SHALL stop when the verified `totalCount` is reached, the endpoint returns a natural terminal page, or `MAX_DISCOVERY_RESULTS_PER_CATEGORY` is reached. The discovery status SHALL be one of `complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, or `request_failed`; a failed or truncated page SHALL never be interpreted as zero assets." | §4.1 |
| LREQ-EXT-060 | Primary implementation chunk for the Coveo side; Chunk 1 is the supporting contract chunk for canonicalization | "Each discovery record SHALL retain all non-empty identity candidates from `ec_product_id`, `permanentid`, response-level `clickUri`, and response-level `uri`. Candidates SHALL be canonicalized under one versioned mapping rule." | §4.1 |
| LREQ-EXT-070 | Integration completion chunk (Chunk 1 primary, Chunk 2 supporting) | "If canonical candidates disagree, the record SHALL be marked `conflict` and excluded from the canonical denominator and enrichment set. If no candidate can be canonicalized, it SHALL be marked `unresolved`. Neither case may be silently treated as an ordinary asset." | §4.1 |
| LREQ-EXT-080 | Primary implementation chunk | "Exact category membership SHALL be checked against the canonical taxonomy. Parent paths SHALL NOT match child paths merely by prefix. Scalar and multi-valued category response shapes SHALL be handled explicitly." | §4.1 |
| LREQ-EXT-090 | Primary implementation chunk; **Chunk 10 is the completion chunk** | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." Chunk 3 completes the condition detection and persisted status only; warning production and rankability suppression are completed by Chunk 10 (`interfaces/chunk-01.md` §5 states the same boundary for the primitive layer). See §12.2. | §4.1 |
| LREQ-EXT-100 | Primary implementation chunk | "Requests SHALL be rate-limited and retry transient `429` and `5xx` responses with exponential backoff. Permanent authentication, CSRF, malformed request, or authorization failures SHALL not be retried indefinitely." | §4.1 |
| LREQ-NFR-010 | Primary implementation chunk (integration completion of Chunk 2's sink) | "Discovery persistence SHALL be streamed and SHALL not require all responses in memory." | §11 |
| LREQ-NFR-030 | Supporting contract chunk; **Chunk 10 is the primary implementation chunk** | "A failed page or sampled asset SHALL not abort unrelated categories or assets; the failure SHALL remain visible in status and evidence fields." Chunk 3 supplies the discovery-side isolation and visible status fields. | §11 |
| LREQ-SEC-010 | Supporting contract chunk (Chunk 0 primary; Chunks 12 and 3 as completion chunks for their own adapters) | "Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection." Chunk 3 consumes `get_credentials()`/`Credentials.require_for_collection()` and reads no environment variable of its own. | §4.3 |
| LREQ-SEC-020 | Supporting contract chunk (Chunk 2 primary, Chunk 13 completion) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern SHALL be ignored by version control." Chunk 3 never puts a token, cookie, or `Authorization` header value into persisted metadata or error summaries. | §4.3 |

Definitions from §1.4 that this chunk's behavior depends on: **Discovered
population** ("Distinct canonical asset identities returned by verified
category discovery, excluding unresolved/conflicting identities from the
canonical denominator but retaining them in audit data"), **Usable
observation**, and **Within-run**.

The shared ordinal/duplicate rule (`LREQ-SMP-020`, Chunk 4A primary; Chunk 3
supporting) is stated once, here, and referenced unchanged in §7, §8, and §9:
**the canonical population for a category is ordered by the stable discovery
ordinal assigned during collection; if the endpoint repeats or reorders a
record, the first valid ordinal is retained and the duplicate is recorded
separately.** Chunk 3's obligation is the collection side: assign
`discovery_ordinal` once per emitted record (monotonic, zero-based, per run and
category, in emission order) and, when a record whose canonicalized identity
was already seen earlier in the same run and category arrives again, persist it
as its own row with `is_duplicate = true` and `duplicate_of_observation_id`
pointing at the first row — never overwrite, renumber, or drop it.

## 4. Interface contracts consumed

Copied from the frozen interface files; no signature below is re-derived from
another chunk's source. Three frozen interfaces are consumed
(`chunk-00.md`, `chunk-01.md`, `chunk-02.md`) and **none is amended**; the
consumer relationship from `chunk-02.md` is spelled out in §12.10, and the page
sink it names is `insert_raw_discovery_observations`.

From `interfaces/chunk-00.md` (`niche_scout.models`, `niche_scout.config`):

```python
class DiscoveryStatus(str, Enum):   # complete | truncated | page_failed | filter_unverified
                                    # | category_mismatch | identity_incomplete | request_failed
class IdentityResolutionStatus(str, Enum):      # resolved | unresolved | conflict
class CategoryFilterValidationStatus(str, Enum):  # verified | mismatch | unverified
class WarningCode(str, Enum):       # DISCOVERY_TRUNCATED, DISCOVERY_PAGE_FAILED,
                                    # DISCOVERY_FILTER_UNVERIFIED, CATEGORY_MISMATCH,
                                    # IDENTITY_UNRESOLVED, IDENTITY_CONFLICT, ...
RawDiscoveryObservationRecord  # 16 fields; asset_identity_key: Optional[str],
                               # stratum_index nullable, is_duplicate, duplicate_of_observation_id
MAX_DISCOVERY_RESULTS_PER_CATEGORY = 2000
PAGE_SIZE = 96
ENDPOINT_CONTRACT_VERSION = "1.0.0"
IDENTITY_MAPPING_RULE_VERSION = "1.0.1"   # adapter-side suffix tolerance dropped; chunk-01.md §4.1 already required exact equality
                                          # A Chunk 0 / interface value restated here for context, not a Chunk 3 edit — §6 does not list models.py.
                                          # `state` moved out of the structural required set on 2026-09-18; that change is Chunk 5's, not this chunk's (see §12.13).
def to_json(instance: Any) -> str: ...
def to_json_dict(instance: Any) -> dict[str, Any]: ...
def ensure_utc(value: datetime) -> datetime: ...

COVEO_TOKEN_ENV = "NICHESCOUT_COVEO_BEARER_TOKEN"
@dataclass(frozen=True)
class Credentials:
    coveo_token: str
    unity_csrf_token: str
    @property
    def coveo_bearer_token(self) -> str: ...
    def require_for_collection(self) -> None: ...   # raises ValueError, no secret in message
@dataclass(frozen=True)
class NicheScoutConfig:      # taxonomy_path, db_path, max_discovery_results_per_category,
    ...                      # page_size (fixed 96), max_taxonomy_age_days; policy_versions()
def load_config(cli_args=None, toml_path=None) -> NicheScoutConfig: ...
def read_categories(categories_path: Path) -> Sequence[str]: ...
def get_credentials(environ=None) -> Credentials: ...
```

From `interfaces/chunk-01.md` (`niche_scout.validation`):

```python
def validate_taxonomy(payload, *, requested_categories, reference_utc,
                      max_taxonomy_age_days=MAX_TAXONOMY_AGE_DAYS) -> TaxonomyValidationResult: ...
def taxonomy_path_set(payload: object) -> frozenset[str]: ...
def normalize_category_path(value: str) -> str: ...
def match_exact_category(category_value: object,
                         taxonomy_paths: Container[str]) -> CategoryMatchResult: ...
def discovery_status_for_category_status(
    status: CategoryFilterValidationStatus) -> DiscoveryStatus | None: ...
def collect_identity_candidates(record: Mapping[str, object]) -> tuple[IdentityCandidate, ...]: ...
def canonicalize_identity_candidate(
    raw_value: str, *, mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION) -> str | None: ...
def resolve_canonical_identity(
    record: Mapping[str, object], *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION) -> IdentityResolutionResult: ...
def validate_response_shape(
    payload: object, *, expected_shape: str, required_members: Sequence[str] = (),
    field_types: Mapping[str, type | tuple[type, ...]] | None = None) -> StructuralValidationResult: ...
def redact_value(value: object) -> str: ...
def summarize_validation_issues(issues, *, max_context_chars: int = 256) -> str: ...
```

Frozen semantics this chunk must respect (chunk-01.md §5): every function is
**structural only** — none decides metric usability; `reference_utc` is always
an explicit tz-aware UTC argument; the taxonomy freshness boundary is
inclusive (`age_days_exact <= max_taxonomy_age_days`); exact category matching
is **full-segment equality**, case-insensitive in comparison and
case-preserving in the reported `matched_path`; `discovery_status_for_category_status`
maps `unverified → FILTER_UNVERIFIED`, `mismatch → CATEGORY_MISMATCH`, and
`verified → None`. Redaction never includes credential values,
`Authorization` headers, CSRF tokens, cookies, or full response bodies.

From `interfaces/chunk-02.md` (`niche_scout.database`):

```python
class SqliteRepository:
    def __init__(self, db_path: "Path | str", *, initialize: bool = True,
                 busy_timeout_ms: int = 5000, synchronous: str = "NORMAL",
                 create_parent_directory: bool = True) -> None: ...
    def close(self) -> None: ...
    def __enter__(self) -> "SqliteRepository": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def category_transaction(self, run_id: str, category: str) -> Iterator["SqliteRepository"]: ...
    def in_category_transaction(self) -> bool: ...
    def append_raw_discovery_observations(
        self, observations: "Iterable[RawDiscoveryObservationRecord]",
        *, batch_size: int = 500) -> int: ...
    def insert_raw_discovery_observations(
        self, observations: Sequence[RawDiscoveryObservationRecord]) -> None: ...
    def update_raw_discovery_identity(
        self, observations: Iterable[RawDiscoveryObservationRecord]) -> int: ...
    def iter_raw_discovery_observations(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservationRecord]: ...
    def stream_raw_discovery_observations(self, run_id: str) -> Iterator[RawDiscoveryObservationRecord]: ...
    def count_raw_discovery_observations(self, run_id: str, category: str) -> int: ...
    def set_category_status(self, run_id: str, category: str, discovery_status: str,
                            *, computed_at_utc: "datetime | None" = None) -> None: ...

class RepositoryError(DatabaseError): ...          # raw observation write outside a category transaction
class UniqueConstraintViolation(DatabaseError): ...
class InvalidRecordValueError(DatabaseError): ...
```

This chunk consumes exactly three frozen interfaces (`chunk-00.md`, `chunk-01.md`,
`chunk-02.md`) and amends none. From `chunk-02.md` it consumes
`category_transaction`, `insert_raw_discovery_observations`,
`update_raw_discovery_identity`, `set_category_status`, and the read/count APIs.
The page sink is `insert_raw_discovery_observations` — not
`append_raw_discovery_observations` — and the call pattern is
`category_transaction` + one insert per page; `insert_raw_discovery_observations`
is part of Chunk 2's frozen surface (`interfaces/chunk-02.md` §3, lines 269–270
and 330–333), so using it is consumption, not amendment (rationale and code
basis: §12.10).

Chunk 2 preconditions Chunk 3 depends on, verbatim in effect:

- `insert_raw_discovery_observations(observations)` is "the frozen protocol's
  batch convenience: it is `append_raw_discovery_observations(observations,
  batch_size=max(1, len(observations)))` and carries the **same**
  inside-`category_transaction` precondition" (`interfaces/chunk-02.md` §3).
- `append_raw_discovery_observations` "SHALL only be called from inside an
  active `category_transaction(run_id, category)` block. Called outside one it
  raises `RepositoryError` **before consuming the iterable**."
- It "consumes the iterable **incrementally**: at most `batch_size` records are
  held in memory… It never calls `list()` on the argument and never builds a
  second full-size container."
- Its rollback boundary is the enclosing `category_transaction`'s savepoint,
  which covers every batch prefix already written for that category.
- A duplicate `observation_id` raises `UniqueConstraintViolation`; a naive or
  non-UTC datetime, or an enum-backed value outside its allowed set, raises
  `InvalidRecordValueError`.
- `set_category_status(..., discovery_status, *, computed_at_utc=None)` is the
  status upsert into `category_scores`; a `None` `computed_at_utc` raises
  `InvalidRecordValueError` and writes nothing, so the adapter always supplies
  the caller-injected timestamp.

No interface file is missing for this chunk's prerequisites; the three
required files all exist with `Status: VERIFIED`.

## 5. Interface contract this chunk produces

Public surface in `src/niche_scout/collector_coveo.py` (becomes
`interfaces/chunk-03.md` verbatim once frozen). Names are new; nothing frozen in
Chunks 0–2 is redefined.

```python
COVEO_ENDPOINT = "https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2"
COVEO_ORGANIZATION_ID = "unitytechnologiesproductionmkahteav"
COVEO_TEMPLATE_PATH = Path("config") / "coveo_search_template.json"   # R-B: the capture
COVEO_VISITOR_ID_PLACEHOLDER = "niche-scout-lean-v1"   # fixed; never the captured UUID
COVEO_REQUIRED_HEADERS: tuple[tuple[str, str], ...]   # Authorization is appended at call time
                                                      # = Content-Type, Accept, Referer (§12.5)
COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0
COVEO_BACKOFF_BASE_SECONDS = 2.0
COVEO_MAX_RETRIES = 5
COVEO_DISCOVERY_FIELD_SET: tuple[str, ...] = (
    "permanentid", "ec_product_id", "ec_name", "ec_category", "publisher_name")

@dataclass(frozen=True, slots=True)
class CoveoPageResponse:
    """One structurally validated page. ``total_count`` is None when unverifiable."""
    page_index: int
    first_result: int
    total_count: int | None
    records: tuple[Mapping[str, object], ...]
    request_metadata: Mapping[str, object]      # redacted; never headers or tokens
    issues: tuple[ValidationIssue, ...] = ()

class CoveoDiscoveryError(RuntimeError): ...        # base
class CoveoRequestFailed(CoveoDiscoveryError): ...  # retries exhausted / permanent failure
class CoveoTaxonomyInvalid(CoveoDiscoveryError): ...  # LREQ-EXT-020 pre-network abort

@dataclass(frozen=True, slots=True)
class CategoryDiscoveryResult:
    category: str
    discovery_status: DiscoveryStatus
    ordinal_start: int                  # first ordinal assigned in this category (0-based)
    ordinal_end: int                    # exclusive; equals observations_emitted
    observations_emitted: int           # rows handed to the sink, including duplicates
    canonical_identity_count: int       # distinct resolved keys; unresolved/conflict excluded
    unresolved_identity_count: int
    conflict_identity_count: int
    duplicate_observation_count: int
    pages_fetched: int
    total_count: int | None             # verified totalCount, else None
    api_reported_count: int | None      # parent REQ-EXT-070's API-returned count
    filter_status: CategoryFilterValidationStatus
    conditions: tuple[DiscoveryStatus, ...]   # every applicable condition, severity-ordered
    issues: tuple[ValidationIssue, ...]

def load_coveo_search_template(
    template_path: "Path | str" = COVEO_TEMPLATE_PATH) -> Mapping[str, object]:
    """Read and hash-verify the captured request template (R-B/R-M). Raises
    ``CoveoTaxonomyInvalid`` when the file is missing, malformed, or its committed
    body does not match the provenance header's ``template_sha256``."""

def build_coveo_request_body(
    template: Mapping[str, object], category: str, *,
    page_index: int, page_size: int = PAGE_SIZE) -> dict[str, object]:
    """Replay the captured template with the four mechanical edits of §12.6: the
    target category's ``ec_category`` ``currentValues`` entry marked ``"selected"``
    and every other captured value ``"idle"``, ``fieldsToInclude`` forced to the
    five-field set, ``actionsHistory`` emptied, ``analytics`` dropped,
    ``firstResult = page_index * PAGE_SIZE``, and ``visitorId`` replaced by
    ``COVEO_VISITOR_ID_PLACEHOLDER``. Raises ``ValueError`` if the resulting body
    contains ``q`` or ``query``."""

def build_coveo_headers(bearer_token: str) -> dict[str, str]:
    """``COVEO_REQUIRED_HEADERS`` plus ``Authorization: Bearer <token>``. A leading
    ``"Bearer "``/``"bearer "`` scheme prefix in the supplied value is stripped
    before the scheme is re-applied, so a credential stored as ``"Bearer eyJ…"``
    yields ``Authorization: Bearer eyJ…`` (§12.8)."""

def coveo_search_url(organization_id: str = COVEO_ORGANIZATION_ID) -> str: ...

def validate_discovery_taxonomy(
    taxonomy_payload: object, *, requested_categories: Sequence[str],
    reference_utc: datetime, max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS
) -> TaxonomyValidationResult: ...

def fetch_category_page(
    request_body: Mapping[str, object], *, headers: Mapping[str, str],
    url: str, opener: CoveoOpener, sleeper: Callable[[float], None],
    max_retries: int = COVEO_MAX_RETRIES) -> CoveoPageResponse: ...

def discover_category(
    category: str, taxonomy_payload: object, *, config: NicheScoutConfig,
    credentials: Credentials, reference_utc: datetime,
    sink: CoveoObservationSink, opener: CoveoOpener,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = ...,            # orchestration-injected
    run_id: str) -> CategoryDiscoveryResult: ...
```

`CoveoOpener` is a protocol
(`def open(self, request) -> object` returning an object exposing
`status`/`headers`/`read()`), so every test injects a recording fake and no test
performs network I/O; the production implementation is `urllib.request`-based.
`CoveoObservationSink` is the seam `LREQ-NFR-010` is verified through: it is
constructed by the caller with `(repository, run_id, category, batch_size)` and
its `write(page_observations)` method is only ever called by `discover_category`
inside the repository's active `category_transaction(run_id, category)` block.
Its implementation persists one page's records through
`repository.insert_raw_discovery_observations(page_observations)` — the page sink
of §12.10 — so the adapter never opens a transaction of its own.

This chunk also propagates `runs.taxonomy_sha256` placeholder values it is given
verbatim and never computes or rewrites them (§12.11).

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_coveo.py` | Modified (docstring-only stub → implementation) | Entire Coveo discovery adapter: endpoint/headers/request builder, taxonomy preflight, pagination, ordinal + duplicate handling, identity/category classification, retry/backoff, streaming sink |
| `config/coveo_search_template.json` | New | The captured Coveo discovery request (operator capture `2026-09-17T04:28:28.915Z`) plus its provenance header (`schema_version`, `captured_at_utc`, `source_url`, `template_sha256` over the canonicalized committed body, `organization_id`, `endpoint`). The template source for `build_coveo_request_body` (§12.1, R-B) |
| `tests/test_collector.py` | New | Mocked-HTTP discovery tests, pagination/duplicate/mismatch/retry tests, streaming-persistence integration test |
| `tests/fixtures/coveo_discovery.py` | New | Request fixtures anchored to `config/coveo_search_template.json` plus the §12.6 edits, and redacted Coveo page fixtures (packages, terminal page, `totalCount`-bearing response, `ec_category` scalar and array shapes, malformed record) |
| `tests/fixtures/__init__.py` | Modified | Re-export the new fixture module (matching the existing `validation_fixtures` convention) |
| `tests/traceability.json` | Modified | Add one entry per `tests/test_collector.py` base node ID with its `@pytest.mark.lreq` marker |
| `src/niche_scout/collector.py` | Modified — **deliberately minimal facade edit, flagged by the project rule** | The facade currently does `from .collector_coveo import *`, so exported names reach it only if `collector_coveo.__all__` exists; the edit adds the `__all__` re-export path if the star-import does not propagate the intended surface. No other change: no GraphQL import removed, no `collector_graphql.py` edit, no other chunk's symbol touched. |
| `config/category_taxonomy.json` | **Not touched — byte-identical, §11** | Declined as the request template (the capture lives in `config/coveo_search_template.json`); the all-zero `template_sha256` stays a name-only placeholder whose value is propagated verbatim, and the file is never rewritten (§12.1, §12.11) |
| `config/categories.json` | Not touched | Requested-category source, read via `config.read_categories` |
| `src/niche_scout/models.py` | Not touched (blocking if it seems necessary) | Enums/records are frozen; see §12.3 |
| `src/niche_scout/collector_graphql.py` | Not touched | Chunk 5 owns it and runs in parallel |

## 7. Task breakdown

Three boxes in this list — `:590`, `:603`, and `:626` — carry open `- [ ]`
openers but declare work **Chunk 5 owns**, not this chunk: the first records
interface values consumed rather than edited, and the other two declare test
obligations in Chunk 5's files. They are left as they stand in this pass and are
not a second instruction to edit `collector_graphql.py`; see the Status footnote
at `:4-47` and the dated correction at `:1676-1709`, which record that their
conversion into this plan's §12 obligation/§6 "Not touched" convention is a
deferred, separately-committed change.

- [ ] Declare the module's frozen constants: endpoint + organization id,
  `COVEO_TEMPLATE_PATH`, `COVEO_VISITOR_ID_PLACEHOLDER`, the required header set
  (`COVEO_REQUIRED_HEADERS`, which excludes `sec-ch-ua*`, `sec-fetch-*`,
  `priority`, `pragma`, and `cache-control`), `COVEO_DISCOVERY_FIELD_SET`
  (exactly the five parent-SRS discovery fields),
  `COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0`,
  `COVEO_BACKOFF_BASE_SECONDS = 2.0`, `COVEO_MAX_RETRIES = 5`, and the
  `CoveoOpener`/`CoveoObservationSink` protocols (`LREQ-EXT-010`,
  `LREQ-EXT-040`; §12.5).
- [ ] Implement `load_coveo_search_template`, which reads
  `config/coveo_search_template.json`, verifies the committed body against the
  provenance header's `template_sha256` (SHA-256 over the canonicalized
  committed `request_body`: `json.dumps(body, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)`), and raises `CoveoTaxonomyInvalid`
  on a missing, malformed, or hash-mismatched capture (§12.1, R-B).
- [ ] Implement `coveo_search_url`, `build_coveo_headers` (`Authorization:
  Bearer <token>` — with a leading `"Bearer "`/`"bearer "` prefix in the supplied
  credential stripped before re-prefixing — `Content-Type: application/json`,
  `Accept: application/json`, and `Referer: https://assetstore.unity.com/`; no
  `Origin`), and `build_coveo_request_body` (template replay carrying the
  committed capture's single `ec_category` facet with the target category's
  `currentValues` entry set to `"selected"` and every other captured value
  `"idle"`;
  `fieldsToInclude` forced to the five-field set as the single deliberate
  divergence from "replayed as captured"; `actionsHistory` emptied and
  `analytics` dropped; `firstResult = page_index * PAGE_SIZE`; `visitorId`
  replaced by `COVEO_VISITOR_ID_PLACEHOLDER`; the dropped facets recorded in
  `request_metadata_json` (stating `ec_category` is the sole facet and why the
  `ec_sale_filters`, `ec_price_filter`, `ec_rating`, `first_published_at`, and
  `publisher_name` facets were dropped); a post-condition assertion that neither
  `q` nor `query` appears at any depth) (`LREQ-EXT-010`, `LREQ-EXT-030`,
  `LREQ-EXT-040`; §12.1, §12.5, §12.6).
- [ ] Implement `validate_discovery_taxonomy` over
  `validation.validate_taxonomy` and abort *before any network request* when the
  result is not valid/fresh/complete (`LREQ-EXT-010`, `LREQ-SEC-010`).
- [ ] **Implementer guard:** before wiring the sink, confirm
  `insert_raw_discovery_observations` exists on the implemented
  `SqliteRepository` (`src/niche_scout/database.py`) with its frozen signature.
  If it is absent, STOP and report; do not substitute
  `append_raw_discovery_observations` (R-N, §12.10).
- [ ] Implement `fetch_category_page`: one HTTP request through the injected
  `CoveoOpener` using `urllib.request` in production; classify the response as
  success / transient (`429`, `5xx`) / permanent (401, 403, 400-shape,
  CSRF/auth/malformed-request); structurally validate through
  `validate_response_shape` before reading any record
  (`LREQ-EXT-040`, `LREQ-EXT-100`).
- [ ] Implement the rate limiter and backoff loop: wait at least
  `COVEO_MIN_REQUEST_INTERVAL_SECONDS` between consecutive requests across the
  whole run via the injected `sleeper`, retry transient statuses with
  exponential backoff from `COVEO_BACKOFF_BASE_SECONDS` up to
  `COVEO_MAX_RETRIES`, honor `Retry-After` when present, and never retry a
  permanent failure more than zero additional times (`LREQ-EXT-100`).
- [ ] Implement the pagination loop in `discover_category`: zero-based
  `page_index`/`first_result` offset traversal with the confirmed
  `first_result = page_index * PAGE_SIZE` convention (capture-confirmed:
  `number` 2 with `firstResult` 96 and `numberOfResults` 96), fixed `PAGE_SIZE`,
  `MAX_DISCOVERY_RESULTS_PER_CATEGORY` cap with the API-reported count retained
  separately, verified-`totalCount` stop, natural-terminal-page stop, and
  per-page failure isolation that ends only the current category
  (`LREQ-EXT-050`; §12.5).
- [ ] Implement the streaming sink: open
  `repository.category_transaction(run_id, category)` once per category, and
  hand each page's records to
  `repository.insert_raw_discovery_observations(page_observations)` as the page
  is produced, so only one page's records are in memory at a time — never a
  per-category list of records (`LREQ-NFR-010`; §12.10).
- [ ] Build each `RawDiscoveryObservationRecord`: monotonic `discovery_ordinal`;
  `identity_candidates_json` from `collect_identity_candidates`;
  `identity_resolution_status`/`identity_resolution_reason` from
  `resolve_canonical_identity`; nullable `asset_identity_key` (non-null only for
  `resolved`); `category_value_json` verbatim;
  `category_filter_validation_status` from `match_exact_category`;
  `stratum_index = None` during discovery; `request_metadata_json` and
  `error_summary_json` redacted via `summarize_validation_issues`/`redact_value`;
  `retrieved_at_utc` from the injected clock; `is_duplicate` /
  `duplicate_of_observation_id` per the §3 ordinal/duplicate rule
  (`LREQ-EXT-040`, `LREQ-EXT-050`, `LREQ-EXT-060`, `LREQ-EXT-080`,
  `LREQ-NFR-010`, `LREQ-SEC-020`).
- [ ] Track per-category identity outcomes: `resolved` records contribute the
  canonical key; `conflict` and `unresolved` records are persisted, excluded
  from the canonical count, and never counted as ordinary assets
  (`LREQ-EXT-060`, `LREQ-EXT-070`).
- [ ] **Record, without claiming to discharge, the extraction obligation this
  chunk inherits.** Implement and test the equality step only; the URI
  trailing-identifier *extraction* rule stays the inferred, **unverified**
  rule of `interfaces/chunk-01.md` §4.1 ("Caveat Chunk 3 must verify (plan
  RN-1, not a defect in this chunk)"). Chunk 3 did not sanity-check it against
  real redacted fixtures and SHALL NOT state or imply anywhere — code comment,
  docstring, test name, `mapping_rule_version` stamp, or metadata — that it did,
  and SHALL NOT re-derive or "improve" the extraction pattern to compensate
  (§12.9; `interfaces/chunk-03.md` §8). The obligation is open, currently owes
  **no chunk**, and is recorded in `requirements-dependency-map.md` §6.4.
- [ ] Implement `discovery_status` selection: compute every applicable condition
  from `DiscoveryStatus` values (including
  `discovery_status_for_category_status(filter_status)`), keep the full
  condition set on `CategoryDiscoveryResult.conditions`, and select the single
  terminal status by the **non-normative predecessor convention** carried from
  the retired `SRS-revision2.md` §4.1 `REQ-EXT-095` — that document is retired,
  and the live normative document for this project is `Documents/SRS-lean.md`,
  which does not itself state this precedence (corrected 2026-09-18: this
  sentence previously read "the retired `SRS-revision2.md` §4.1
  `REQ-EXT-095`" with no live-document qualification, which named a retired
  document where a reader could take it for the governing SRS) —
  `request_failed`, `page_failed`, `filter_unverified`, `category_mismatch`,
  `identity_incomplete`, `truncated`, `complete` (`LREQ-EXT-050`,
  `LREQ-EXT-080`, `LREQ-EXT-090`; §12.4).
- [ ] Per-category failure isolation: catch per-category discovery failures at
  the `discover_category` boundary, return a `CategoryDiscoveryResult` with a
  failure status and populated `error_summary_json` rather than propagating, and
  let the already-committed `category_transaction` for other categories stand
  (`LREQ-NFR-030`).
- [ ] Persist the terminal status through
  `repository.set_category_status(run_id, category, discovery_status, ...)`
  after the category's observations are committed, always passing the
  caller-injected `computed_at_utc` (`LREQ-EXT-090`, `LREQ-NFR-030`).
- [ ] Author `tests/fixtures/coveo_discovery.py` and `tests/test_collector.py`
  with the §9 markers — including the request fixtures anchored to
  `config/coveo_search_template.json` plus the §12.6 edits and the
  credential-normalization test of §12.8 — then add the matching
  `tests/traceability.json` entries (`LREQ-TST-040`).
- [ ] **Interface values consumed, not edited — do NOT change the code for the
  two entries below.** Both were consumed from frozen interfaces and both match
  `src/` today; they are listed here only so a reader does not mistake them for
  this chunk's own decisions:

  - `IDENTITY_MAPPING_RULE_VERSION = "1.0.1"` (`models.py`, Chunk 0's frozen
    value, §4). §12.13 records that the value pre-dates this chunk.
  - `PRODUCT_DETAIL_REQUIRED_MEMBERS` (`collector_graphql.py`, Chunk 5, §4) —
    when the node-5 ruling of §12.13 lands, its member list loses `state`
    (Chunk 5 drops the member from the constant *and* the validator call, so
    `state` lives only in the semantic state group). This bullet is **not** a
    second instruction to edit that file: §6 does not list
    `collector_graphql.py`, and Chunk 5 owns the change.
- [ ] **Declare the paired boundary tests for the `collector_graphql.py:1148`
  guard (Chunk 5's file, named here because the correction is ruled in this
  plan's §12.13).** The pair pins *both* halves so the benign half is not
  "fixed" by re-adding `state` to the required set:

  - missing `state` → benign: `state_unknown = True`, no `invalid_state_value`
    issue, and the operation's outcome is decided by the remaining required
    members (the payload is `WRONG_DATA_SHAPE` when another required member is
    missing, and otherwise validates with `state_unknown` recorded);
  - null `state` → the same benign path, and specifically **no**
    `response_null_required_member` for `state`;
  - present-but-UNUSABLE `state` (a non-string) → still
    `invalid_state_value` → `INVALID_STATE_VALUE`. **This half must not
    regress**, which is why it is declared here beside the other two.

  Node names and markers: the three cases are new nodes of the existing
  **`test_invalid_state_value_and_missing_identity_are_operation_errors`**
  family (`LREQ-GQL-040`; declared in the Chunk 5 plan's §9 node list, which
  maps base node IDs and does not name per-case nodes), registered under
  `LREQ-GQL-040` per the existing
  `tests/traceability.json` convention of **one entry per base node ID**, so no
  new node ID and no new LREQ marker is invented here. No LREQ ID is invented
  because none is needed: `LREQ-GQL-040` already owns this node.
- [ ] **Declare the node-6 metadata test (Chunk 5's file, §12.13).**
  `operation_names` and `correlation_keys` must actually appear as the two
  operation names and the caller-supplied keys in `request_metadata_json`, and
  must **not** be replaced by redaction placeholders
  (`"<value redacted: str of length N>"`) — i.e. the values
  `build_request_metadata_json` receives are the values it persists for these
  two keys. Registered under the existing
  **`test_request_metadata_json_carries_required_fields_without_secrets`** node
  (`LREQ-SEC-020`; Chunk 5 plan §9), asserted as a strengthening of that node,
  not as a new marker. The redaction *guarantee* it must not weaken is the
  signature property recorded in Chunk 5 plan §5.10: the function accepts no
  credential, header-value, cookie, or body parameter at all.
- [ ] Run `python -m pytest tests/test_collector.py -q` and
  `python -m niche_scout.tools.validate_traceability` before declaring the
  chunk done.
- [ ] Propagate `runs.taxonomy_sha256` verbatim without computing, validating, or
  rewriting it; the gap belongs to Chunk 10 (§12.11).

## 8. Edge cases and invariants

Drawn from the dependency map's "Edge cases" column for this chunk's LREQs
(lines 153–163) plus the chunk's own gate invariants.

- **`LREQ-EXT-010`** — Endpoint, headers, taxonomy template, and
  selected-category facet must match the capture; a missing capture file or a
  body whose content does not match the provenance header's `template_sha256` is
  a capture problem, not something the adapter may paper over (§12.1).
- **`LREQ-EXT-030`** — Reject accidental `q` or `query` at any nesting depth,
  including after template replay; prevent keyword contamination.
- **`LREQ-EXT-040`** — Missing identity fields must be tolerated as *missing*
  (never fabricated), a forbidden scoring field appearing in a response must not
  be used, and extra response fields must be ignored without error. The
  committed capture's `fieldsToInclude` is a five-field list and its single
  `ec_category` facet stands in place of the original capture's 23 fields and
  six facets; §7 forces that five-field set at build time, so the committed
  file and the request the adapter sends agree on it (§12.1, R-C).
- **`LREQ-EXT-050`** — Verified `totalCount`; natural terminal page; truncation
  at the cap; failed page; filter uncertainty; category mismatch; zero results.
  A failed or truncated page is **never** interpreted as zero assets.
- **`LREQ-EXT-050` / `LREQ-SMP-020`** — If the endpoint repeats or reorders a
  record, the first valid ordinal is retained and the duplicate is recorded
  separately: `is_duplicate = true`, `duplicate_of_observation_id` = the first
  observation's id, same `discovery_ordinal` space, own row, never renumbered.
- **`LREQ-EXT-060`** — Multiple identity aliases, URI fallback, empty candidate
  sets, and a corrected `IDENTITY_MAPPING_RULE_VERSION` mapping must all be
  tolerated; the adapter branches on `IdentityResolutionResult.mapping_rule_version`
  rather than assuming `1.0.0` semantics (`interfaces/chunk-01.md` §4.1,
  "Caveat Chunk 3 must verify (plan RN-1, not a defect in this chunk)" — the
  caveat paragraph in §4.1, cited by title because §4.1 now continues past it
  with three further paragraphs and line numbers there are not stable).
  That correction has now landed: at `1.0.1` a URI-derived candidate must *equal*
  the explicit anchor, with no suffix, prefix, or substring tolerance, because the
  `1.0.0` suffix tolerance rescued genuine `LREQ-EXT-070` conflicts
  (`Documents/SRS-lean.md:270-271`) that `interfaces/chunk-01.md` §4.1 fixes as
  `conflict`. Unparseable-URI abstention is unchanged, so a derivation that
  cannot be canonicalized still contributes nothing rather than a guessed key.
  **`1.0.1`'s equality correction is a different matter from the extraction
  rule, which is unaddressed here:** `1.0.1` changed only how a derived candidate
  is compared, never how it is extracted, so the extraction half of the rule
  stays inferred and **unverified** for this chunk (§12.9; the obligation is
  recorded in `requirements-dependency-map.md` §6.4).
- **`LREQ-EXT-070`** — Conflicting candidates, unresolved candidates, and
  exclusion from the denominator and enrichment set; unresolved/conflict records
  stay in audit data.
- **`LREQ-EXT-080`** — Parent vs. child path (no prefix match), exact match,
  scalar category, multi-valued category.
- **`LREQ-EXT-090`** — Warning generation and a non-fully-rankable competition;
  a failed page must not become zero assets. Chunk 3 records the condition;
  Chunk 10/12 produce the warning and enforce the outcome (§12.2).
- **`LREQ-EXT-100`** — Retry `429` and `5xx`; do not endlessly retry
  authentication, CSRF, malformed-request, or authorization errors.
- **`LREQ-NFR-010`** — Streaming is a memory invariant: the adapter never builds
  a per-category list of records and never calls `list()` on the observation
  stream; the sink's `category_transaction` is open for the whole category, and
  the post-condition `count_raw_discovery_observations(run_id, category) ==
  ordinal_end - ordinal_start` must hold.
- **`LREQ-NFR-030`** — A failed page or category does not abort unrelated
  categories or assets; the failure remains visible in `discovery_status`,
  `error_summary_json`, and the returned `conditions`.
- **Streaming precondition** — `insert_raw_discovery_observations` (like
  `append_raw_discovery_observations`) is only ever called from inside an active
  `category_transaction`; calling it outside raises `RepositoryError` before the
  observations are read.
- **Credential normalization** — a `coveo_bearer_token` supplied as
  `"Bearer eyJ…"` (the `.env` form) must not produce
  `Authorization: Bearer Bearer eyJ…`; the scheme prefix is normalized out before
  re-prefixing (§12.8).
- **Nullable discovery fields** — `asset_identity_key` and `stratum_index` may
  be null during raw persistence; canonical identity, duplicate linkage, and
  stratum assignment are updated after canonicalization/sampling by the owning
  later chunks (§2, out of scope).
- **No fabricated zeros** — a `null`/missing response member stays `None`; a
  zero-result category is valid zero-breadth evidence only when the filter and
  response structure are independently verified, otherwise `filter_unverified`.
- **`runs.taxonomy_sha256`** — the placeholder value the adapter is handed is
  propagated verbatim; Chunk 3 neither validates, computes, nor rewrites it
  (§12.11).

## 9. Test plan

**Test module:** `tests/test_collector.py` (new). **Fixtures:**
`tests/fixtures/coveo_discovery.py` (new), re-exported from
`tests/fixtures/__init__.py`. No live network, no credentials from the real
environment, no clock reads: the opener, sleeper, and clock are injected.

**Ruled-in tests for the identity rule version, and the one ruled out because it
already exists (recorded 2026-09-18).** Two test shapes were proposed against
`IDENTITY_MAPPING_RULE_VERSION = "1.0.1"`; reading the artifacts settled both, so
the fix wave inherits decisions rather than questions:

- **Already present — do not duplicate.** The suffix-as-conflict boundary is
  covered today: `tests/test_identity.py:403-446`
  `test_uri_derived_proper_suffix_of_anchor_is_conflict`
  (`@pytest.mark.lreq("LREQ-EXT-070")`) asserts `CONFLICT` at `:433` for a
  URI-derived identifier that is a proper suffix of the explicit anchor, and
  `tests/traceability.json` already carries its entry. The authoritative
  boundary for consumers is `interfaces/chunk-01.md` §4.1 ("What `1.0.1` is").
  Adding a second copy of it to `tests/test_collector.py` would duplicate a
  frozen node ID's coverage, so it is **not** in this chunk's test list.
- **Uncovered — the adapter side must be named before any removal.** No node in
  `tests/test_collector.py` exercises a *proper suffix* through
  `collector_coveo.resolve_observation_identity`, so a source-only deletion of a
  suffix-acceptance branch would be invisible to this chunk's suite: a
  contributor could change `resolve_observation_identity`'s return statement
  from `all(anchor == key for key in uri_keys)` to
  `all(anchor.endswith(key) or key.endswith(anchor) ...)` and every node here
  would still pass. When the adapter-side change lands (§12.13), the node it
  lands with is
  **`test_adapter_uri_candidate_that_is_a_proper_suffix_of_the_anchor_is_conflict`**
  under `@pytest.mark.lreq("LREQ-EXT-070")` with its own
  `tests/traceability.json` entry, and its assertion is
  `resolve_observation_identity(record).status is IdentityResolutionStatus.CONFLICT`
  — not "not RESOLVED" — because the third state (`UNRESOLVED`) is the
  unparseable-URI abstention and asserting only "not resolved" would pass for an
  abstention as well as for a conflict.

**Fixture inventory (request side anchored to the capture; response side
hand-derived from the redacted recorded response shapes described in the parent
SRS — no live call):**

- **Request fixtures** anchored to `config/coveo_search_template.json` plus the
  four mechanical edits of §12.6, and fixtures that violate them (missing
  template file, `template_sha256` mismatch, a `q`/`query` field injected at some
  depth, more than one `ec_category` entry marked `"selected"`, a facet other
  than `ec_category` present, a `request_metadata_json` that does not record the
  dropped facets).
- Response fixtures (**hand-derived assumptions about the live contract**, not
  capture-derived — §12.9): recorded-shape page of 96 records with `permanentid`
  (+ `ec_product_id` agreeing); `clickUri`/`uri` variants for the URI-identifier
  candidate cases (an identifier that **equals** the explicit id, and one that
  does not). These exercise the *equality* step only; they do not and cannot
  certify the extraction rule, which stays inferred and unverified (§12.9,
  `interfaces/chunk-01.md` §4.1).
- Terminal page shorter than `PAGE_SIZE`; a page whose `totalCount` is reached
  exactly; a `totalCount` larger than the cap (truncation); a page with 0
  results; a malformed page (missing records container); a page missing the
  five-field member set.
- Records with `ec_category` scalar, array-with-exact-match,
  array-without-match, parent-path-only (prefix trap), and `null`.
- Records with conflicting canonical candidates, no canonicalizable candidate,
  and `permanentid`/`ec_product_id` numeric-vs-string equality.
- Malformed/duplicate observation records for the sink-failure test, and a
  duplicate `observation_id` to exercise `UniqueConstraintViolation`.
- Real-SQLite integration fixture: a temporary file-backed
  `SqliteRepository` (Chunk 2), **not** a mock.
- The on-disk `config/category_taxonomy.json` is still the source for
  taxonomy-validation fixtures; it is **not** the request-template source
  (§12.1).

**Markers, mapped 1:1 to §3's LREQ IDs (one or more per ID):**

| Marker | Tests |
|---|---|
| `@pytest.mark.lreq("LREQ-EXT-010")` | `test_coveo_endpoint_headers_and_facet_selection_match_captured_template`; `test_authorization_header_normalizes_a_supplied_bearer_scheme_prefix` |
| `@pytest.mark.lreq("LREQ-EXT-030")` | `test_request_body_rejects_free_text_q_and_query_at_any_depth` |
| `@pytest.mark.lreq("LREQ-EXT-040")` | `test_request_uses_discovery_only_field_set`; `test_response_reader_never_sources_forbidden_scoring_fields`; `test_extra_response_fields_are_ignored_and_missing_identity_fields_stay_missing` |
| `@pytest.mark.lreq("LREQ-EXT-050")` | `test_pagination_stops_at_verified_total_count`; `test_pagination_stops_at_natural_terminal_page`; `test_pagination_truncates_at_max_results_and_retains_api_count`; `test_failed_page_never_becomes_zero_assets`; `test_zero_result_category_requires_verified_filter` |
| `@pytest.mark.lreq("LREQ-EXT-060")` | `test_every_non_empty_identity_candidate_is_retained`; `test_uri_fallback_and_unparseable_candidates_contribute_nothing` |
| `@pytest.mark.lreq("LREQ-EXT-070")` | `test_conflict_and_unresolved_records_are_persisted_and_excluded_from_canonical_count` |
| `@pytest.mark.lreq("LREQ-EXT-080")` | `test_exact_category_match_scalar_and_multivalued`; `test_parent_path_does_not_match_child_path` |
| `@pytest.mark.lreq("LREQ-EXT-090")` | `test_discovery_conditions_are_recorded_and_status_uses_severity_precedence` |
| `@pytest.mark.lreq("LREQ-EXT-100")` | `test_transient_429_and_5xx_are_retried_with_backoff_and_retry_after`; `test_permanent_auth_csrf_and_malformed_request_are_not_retried` |
| `@pytest.mark.lreq("LREQ-NFR-010")` | `test_observations_are_streamed_into_active_category_transaction`; `test_discovery_does_not_materialize_the_result_set` |
| `@pytest.mark.lreq("LREQ-NFR-030")` | `test_failed_category_does_not_abort_other_categories_and_stays_visible` |
| `@pytest.mark.lreq("LREQ-SEC-010")` | `test_credentials_are_required_before_any_request_and_bearer_scheme_is_normalized` |
| `@pytest.mark.lreq("LREQ-SEC-020")` | `test_persisted_metadata_and_error_summaries_contain_no_credentials` |

Non-analytical tests (no marker, and no `traceability.json` entry):
`test_module_imports_without_side_effects`,
`test_request_body_builder_signature_is_stable`.

**`LREQ-NFR-010` verification shape (must exercise the real path, not a
signature assertion):** run `discover_category` against a real
`SqliteRepository` with the injected fake opener while the category transaction
is active; assert `repository.in_category_transaction() is True` from inside the
sink's `write`, assert the observation stream is consumed incrementally by
wrapping the opener so that page *n+1* is only served after page *n*'s records
reached the sink, and assert the final
`count_raw_discovery_observations(run_id, category)` equals the number of
emitted observations. A second case asserts that bypassing the sink
(calling `insert_raw_discovery_observations` outside
`category_transaction`) raises `RepositoryError`.

**`traceability.json` entries to add:** one entry per base node ID above,
mapping to its single `LREQ-*` marker value (parameterized cases map by base
node ID, never per generated case). Do not widen
`tools/validate_traceability.py`'s required set — that is Chunk 13's
`LREQ-NFR-060`; until it lands, cross-check the §3 table against the actual
markers manually.

## 10. Definition of done (gate)

Copied verbatim from `requirements-dependency-map.md` §Chunk 3 Gate:

- No live endpoint is needed for normal tests.
- Failed pages remain failures and are never interpreted as zero assets.
- Raw observations are persisted before canonical populations or samples are constructed.
- During discovery, persist every identity candidate, nullable canonical identity, identity-resolution status, nullable stratum index, and raw error metadata; after canonicalization/sampling, update canonical identity, duplicate linkage, and stratum index before inserting sample memberships.
- Discovery can process one category without loading the complete result set into memory.
- This chunk completes the Coveo-side integration of the validation primitives from Chunk 1; the primitive contracts alone do not satisfy LREQ-EXT-060 or LREQ-EXT-080.

The six bullets are copied verbatim and are not re-scored here. What this
section does not say, and what the Status footnote at `:4-47` now states
instead, is that the suite that was green when this gate was first recorded is
**not** green at the current working-tree state (6 failed / 140 passed overall;
6 failed / 47 passed in `tests/test_collector.py`) because six Chunk 5-family
tests in `tests/test_collector.py` fail. Those failures are not gate bullets
above, and no bullet above was re-checked for them; the footnote is a record
correction and does not re-open this section.

## 11. Explicit prohibitions

- Must not issue any network request before taxonomy validation and credential
  validation have both succeeded.
- Must not use a third-party HTTP client. `pyproject.toml` declares
  `dependencies = []`; the transport is the standard library
  (`urllib.request`/`http.client`/`socket`/`email`), with `time.sleep` and the
  socket deadline as the only waiting primitives. Adding a dependency requires a
  separate coordination task.
- Must not include a free-text `q` or `query` field in any request body, and
  must not forward any template field that reintroduces one.
- Must not add a `facetId`-bearing facet block beyond the single `ec_category`
  facet, must not reuse the discarded `ec_sale_filters`, `ec_price_filter`,
  `ec_rating`, `first_published_at`, or `publisher_name` facets, and must not
  rewrite or synthesize into `config/category_taxonomy.json` (§12.1).
- Must not request or persist `ec_rating`, `ec_price`, `ec_thumbnail`,
  popularity, publication-date, or any other scoring field from Coveo; the
  capture's 23-entry `fieldsToInclude` list SHALL be replaced by the five-field
  set, and its `ec_price_filter`, `ec_rating`, `ec_sale_filters`,
  `first_published_at`, and `publisher_name` facets SHALL be dropped (§12.1).
- Must not send a header that is not in `COVEO_REQUIRED_HEADERS`
  (`Content-Type`, `Accept`, `Referer`) plus the call-time `Authorization`;
  browser-fingerprint headers (`sec-ch-ua*`, `sec-fetch-*`, `priority`,
  `pragma`, `cache-control`) and `Origin` are not sent (§12.5).
- Must not retry a permanent authentication, CSRF, malformed-request, or
  authorization failure, and must not retry without honoring a `Retry-After`
  header when one is present.
- Must not interpret a failed, truncated, unverified, or mismatched page as zero
  assets, and must not report a zero-result category as complete without
  independently verified filter and response structure.
- Must not build a per-category list of observation records, call `list()` on
  the observation stream, or otherwise hold a category's complete result set in
  memory.
- Must not call `insert_raw_discovery_observations` (or
  `append_raw_discovery_observations`) outside an active `category_transaction`,
  and must not open a transaction of its own around that call; the page sink
  never falls back to `append_raw_discovery_observations` (§12.10). The
  implementer SHALL first confirm `insert_raw_discovery_observations` exists on
  the implemented `SqliteRepository`; if it is absent, STOP and report (§7).
- Must not write a bearer token, CSRF token, cookie, `Authorization` header
  value, or raw response body into `request_metadata_json`,
  `error_summary_json`, logs, exception messages, or the database.
- Must not pass a credential value carrying its own scheme into
  `Authorization` unnormalized; the `.env` value is stored as `"Bearer eyJ…"` and
  the scheme prefix SHALL be removed before re-prefixing (§12.8).
- Must not overwrite, renumber, or drop a duplicate observation; the first valid
  ordinal is retained and the duplicate is recorded as its own row.
- Must not synthesize a category, an identity, or a value that the endpoint did
  not return; unresolved and conflict records are never ordinary assets.
- Must not state or imply that the URI trailing-identifier extraction rule was
  verified, sanity-checked against real redacted fixtures, or discharged: that
  obligation is unmet and open, owes no chunk, and is recorded in §12.9 and
  `interfaces/chunk-03.md` §8 (this file's §8 is "Edge cases and invariants"),
  plus `requirements-dependency-map.md` §6.4. Extraction itself stays as
  `interfaces/chunk-01.md` §4.1 defines it — inferred and unverified.
- Must not modify `models.py`, `collector_graphql.py`,
  `config/category_taxonomy.json` (byte-identical — the all-zero
  `template_sha256` is a name-only placeholder), `metrics.py`, or `scoring.py`.
- Must not compute, validate, or rewrite `runs.taxonomy_sha256`; the placeholder
  value is propagated verbatim, and the finding — that no chunk owns the gap and
  Chunk 10 does — is recorded in §12.11.
- Must not import `metrics`, `scoring`, `pipeline`, `report`, or `cli` from
  `collector_coveo.py`.
- Must not edit `collector.py` beyond the single `__all__`/re-export line
  described in §6, and must not import `collector` from
  `collector_coveo.py` (that would create an import cycle).
- Must not implement warning rendering, rankability assignment, score
  computation, sampling, canonicalization updates, or enrichment.

## 12. Resolutions, assumptions, and out-of-scope findings

Every question raised in this section's earlier draft is **resolved** except
where an entry says otherwise; no entry below is an open human decision *about
this chunk's scope, requirements, or gate*. Entries are numbered as the draft
numbered them so earlier reviews remain traceable.

**A second entry likewise records an obligation rather than a closed scope
question: §12.13, which records the node-5 ruling and corrects the refuted
premise it rested on.** Unlike §12.9 the ruling itself *is* closed — the
decision is made and recorded — but the change it describes lands in **Chunk
5's** file (`collector_graphql.py`), which §6 does not list, so no part of it is
this chunk's implementation work. A reader of §12 must not read §12.13 as an
authorization to edit that module.

**One entry records an obligation that is UNMET and OPEN rather than resolved:
§12.9, where `interfaces/chunk-01.md` §4.1's URI trailing-identifier extraction
rule stays inferred and unverified for this chunk and no real captured Coveo
response exists anywhere in the repository. A reader of §12 alone must not come
away thinking that verification is settled.** The two entries that record
open *provenance/ownership* findings rather than closed questions are §12.1's
"OPEN — how the file came to be in its trimmed form" bullet (§12.12) and
§12.11's `runs.taxonomy_sha256` ownership gap; both were already stated as
non-blocking findings and neither is resolved here.

**The Status region is not a §12 entry and is not numbered as one.** One
correction in this section's own record — the 2026-09-18 amendment of the
front-matter `Status:` line to carry a footnote, so that `VERIFIED` beside six
failing tests in `tests/test_collector.py` stops reading as a green-suite claim
— is recorded at the end of §12 as an **unnumbered dated correction** rather
than as a §12.15. It closes no numbered scope question, resolves nothing in
§12.1–§12.14, and touches no gate bullet; the front matter it corrects sits
above §1 and outside this section's numbering. No §12.15 exists and none is
implied by it.

**12.1 RESOLVED — the captured request template is `config/coveo_search_template.json`.**
`LREQ-EXT-010` ("Discovery SHALL use the parent SRS Coveo endpoint, required
headers, captured taxonomy template, and selected-category facet mechanism")
requires a *captured* template, and the earlier draft correctly found that
`config/category_taxonomy.json` is not one: it holds `schema_version`,
`captured_at_utc`, `source_url`, an all-zero `template_sha256`,
`canonical_category_paths` (22 paths), and a `categories` array of
`{path,label,parent}` — no request body at all. Chunk 1's validator
(`TAXONOMY_REQUIRED_HEADER_FIELDS`, `TAXONOMY_INVENTORY_FIELDS`) checks this
file's structure only, which is why `LREQ-EXT-020` can pass on it. The operator
supplied a real browser capture of the Coveo discovery request
(`actionsHistory[0].time = 2026-09-17T04:28:28.915Z`), and that capture is the
template:

- It lives in a **new** file, `config/coveo_search_template.json` (§6): the
  captured request body plus a provenance header (`schema_version`,
  `captured_at_utc`, `source_url`, `template_sha256` computed as SHA-256 over
  the canonicalized committed `request_body` — `json.dumps(body,
  sort_keys=True, separators=(",", ":"), ensure_ascii=False)` — plus the capture
  `organization_id` and `endpoint`). It is authored from the capture facts; the
  capture artifact itself is not in the workspace, so the file is the committed
  record of it. `load_coveo_search_template` reads it and raises
  `CoveoTaxonomyInvalid` when the body does not match the header's hash, so a
  drifted capture fails loudly instead of being papered over.
- `config/category_taxonomy.json` is **not** edited, not extended, and not
  synthesized into — it stays byte-identical, and §11's prohibition on touching
  it stands. The template file is authored from the operator's capture facts
  only; nothing is synthesized into the taxonomy file (R-E). The all-zero
  `template_sha256` therefore remains a name-only placeholder whose value is
  propagated verbatim into `runs.taxonomy_sha256`.
  This is deliberate: the real gap is downstream and belongs to Chunk 10 (the
  only chunk that constructs a `RunRecord`), and "fixing" the taxonomy file
  inside a discovery chunk would lock in an inference neither source document
  states — that the taxonomy inventory was captured from the same artifact as
  this request. The finding is recorded in §12.11 and in the dependency map's
  open-items list.
- **One deliberate exception to "replayed as captured": `fieldsToInclude`, and
  it has two states — the original capture and the committed trim.** This entry
  records both, because the committed artifact no longer carries the shape the
  original capture had and a reader must not mistake the first description below
  for a claim about the file on disk.
  - **The original capture.** The operator's browser capture of the Coveo
    discovery request carried a **23-entry** `fieldsToInclude` list. That list
    included `ec_price`, `ec_price_filter`, `ec_rating`, `ec_rating_count`,
    `ec_sale`, `ec_thumbnails`, `ec_flash_teaser_starts_at`, and
    `ec_flash_promo_starts_at`, and it carried **six** facets: `ec_category`,
    `ec_sale_filters`, `ec_price_filter`, `ec_rating`, `first_published_at`,
    and `publisher_name`. Every scoring-relevant member above is one that this
    adapter must never source.
  - **The committed artifact is the trimmed form, and it is what ships.**
    `config/coveo_search_template.json` today carries a **5-entry**
    `fieldsToInclude` — `permanentid`, `ec_product_id`, `ec_name`,
    `ec_category`, `publisher_name` — and **1** facet, the `ec_category` facet
    alone. These are measured properties of the committed file, not a
    restatement of intent (counted: `python -c` reading the file through
    `json.loads` then `len(body["fieldsToInclude"])` → 5, with the five members
    enumerated in that order, and `len(body["facets"])` → 1, whose only entry
    is `facetId`/`field` `ec_category`, `type: "specific"`,
    `resultsMustMatch: "atLeastOneValue"`, `numberOfValues: 150`; the file also
    carries `schema_version` `"1.0.0"` and a `template_sha256` provenance hash).
  - **Why the trim is required, not optional.** `LREQ-EXT-040`
    (`Documents/SRS-lean.md:254-257`) fixes the discovery-only field set
    verbatim: "Discovery SHALL use the parent SRS discovery-only field set:
    `permanentid`, `ec_product_id`, `ec_name`, `ec_category`, and
    `publisher_name`. Product rating, page views, publication date, and price
    SHALL NOT be sourced from Coveo for scoring." Those two sentences are
    exactly the 5-member set measured above and exactly the members the
    23-entry list carried; the trim is the requirement being met, and §7 forces
    the same five-field set when the adapter builds a request. §11 carries the
    matching prohibition. This is required by `LREQ-EXT-040` and is not a
    defect; it is also the **single** deliberate divergence from "replayed as
    captured" (`superseded 2026-09-17: this bullet previously said
    "§7 forces the five-field set ... this divergence"`).
  - **The facet half of the trim.** The **1** facet the committed file ships is
    `ec_category`, `type: "specific"`, `resultsMustMatch: "atLeastOneValue"`,
    `numberOfValues: 150`, with `currentValues` carrying every captured idle
    `ec_category` value, the target category marked `"selected"` and the rest
    `"idle"` — the selected-category facet mechanism of `LREQ-EXT-010`. The
    other five facets of the original six (the four listed above plus
    `publisher_name`) are dropped, and the drop is recorded in
    `request_metadata_json` with its rationale. For `publisher_name`
    specifically: `fieldsToInclude` is what makes a field present on a returned
    record, while a facet returns a separate aggregation that no requirement
    consumes, and §4.1 never scopes discovery by publisher. The drop list is
    computed against the capture actually replayed, so a committed file that
    ships only `ec_category` reports **no** drops rather than a fabricated list
    (`collector_coveo.py` `request_metadata_json`).
  - **OPEN — how the file came to be in its trimmed form, and which artifact
    §12.1 was originally written against, is not established by any evidence in
    the repository.** The capture is committed, but the repository's history
    does not record its evolution: counted, `git log --oneline --
    config/coveo_search_template.json` returns exactly **one** commit
    (`36da5f7 chore: snapshot working tree as Chunk 5 verification baseline`,
    the snapshot commit), and `git diff HEAD -- config/coveo_search_template.json`
    is empty, so there is no pre-snapshot revision to inspect. Two readings are
    consistent with everything counted and quoted above, and this plan does
    **not** choose between them:
    1. the operator's capture was itself already in the 5-field / 1-facet form,
      and the 23-field / 6-facet description in this entry's earlier draft was
      written against a *different* artifact (an earlier or unredacted capture,
      or a pre-trim working copy) that is no longer in the workspace; or
    2. the file on disk was trimmed after capture and before this snapshot, and
      the 23-field / 6-facet description was accurate at the time it was
      written.
    The consequence for this chunk is the same either way and is therefore
    recorded rather than resolved here: the adapter replays the **committed**
    file, §7 forces the five-field set and the single-facet rule at build time,
    and the code-side constants deliberately assert no count at all
    (`COVEO_DISCOVERY_FIELD_SET` and `COVEO_DROPPED_FACET_IDS` in
    `collector_coveo.py` carry the members, not a length, precisely so no
    number is frozen in code). What is **not** established, and SHALL NOT be
    asserted: whether the trim happened after capture or the narrative was
    written against a different artifact. This open item is a provenance
    question, not a scope question — it does not block this chunk's freeze and
    it is not a decision this plan can clear on its own.

**12.2 RESOLVED — `LREQ-EXT-090` stays detection + persistence only.** The SRS
text requires *both* effects: "A failed page, unverified filter, category
mismatch, or material identity incompleteness SHALL generate a warning and SHALL
prevent a fully rankable competition result for that category." Chunk 3 produces
the `DiscoveryStatus` values, persists them, and exposes the full condition set
on `CategoryDiscoveryResult.conditions`. It does **not** emit a `WarningCode`,
does **not** set rankability, and does **not** claim `LREQ-EXT-090` end to end.
Four independent citations establish that boundary:

1. `requirements-dependency-map.md` line 58:
   `| LREQ-EXT-090 | Chunk 3 | Chunk 1, Chunk 2 | Chunk 10 | LREQ-TST-080 |` —
   primary owner Chunk 3, completion chunk Chunk 10.
2. `requirements-dependency-map.md` line 161 (the §1 Coveo table's module
   column): `collector.py`, `validation.py`, `pipeline.py`. `pipeline.py` is not
   in this chunk's §6 file set, so the orchestration half of the requirement
   cannot be completed here.
3. `requirements-dependency-map.md` line 130:
   `| LREQ-TST-040 | Chunk 13 | Chunk 3, Chunk 5, Chunk 6A | Chunk 13 | LREQ-TST-040 |`
   — primary owner and completion chunk are both Chunk 13. The failure-state
   integration test that would prove the warning/rankability effects end to end
   belongs to Chunk 13, so it cannot be Chunk 3's test.
4. `requirements-dependency-map.md` line 1005 (Chunk 10 gate): "Category-level
   failure is represented internally by a typed `CategoryStatus` (`healthy`,
   `degraded`, `failed`) and mapped to `discovery_status`, warnings,
   `evidence_grade`, and `rankability_status`; it is not a separate persisted
   enum unless the schema explicitly adds that field." `CategoryStatus` is
   Chunk 10's mapping target, and §6.5 (lines 1174–1179) repeats the same
   mapping. `interfaces/chunk-01.md` §5 states the primitive-layer half of the
   same boundary: producing the warning and preventing a rankable result is
   Chunks 10/12.

**12.3 RESOLVED — the SRS status list and the frozen enum agree; no action.**
`LREQ-EXT-050` enumerates `complete`, `truncated`, `page_failed`,
`filter_unverified`, `category_mismatch`, `identity_incomplete`,
`request_failed`. `models.DiscoveryStatus` (restated at `interfaces/chunk-00.md`
§2) has exactly those seven members in that order — verified here against
`interfaces/chunk-00.md` plus this plan's §4 enum restatement, not by citing a
`models.py` line number, since Chunk 2's implementation shifted those lines — so
they line up. The enum stays unmodified in this chunk; if a future requirement
introduces a state outside this list, this plan must be revised rather than the
enum widened or a parallel vocabulary added.

**12.4 RESOLVED — severity precedence stays explicitly non-normative.**
`LREQ-EXT-050` lists the seven terminal statuses but does not say how to choose
between two simultaneously applicable conditions, and `LREQ-EXT-090` names four
conditions that must all be recorded. The precedence used in §7 —
`request_failed`, `page_failed`, `filter_unverified`, `category_mismatch`,
`identity_incomplete`, `truncated`, `complete` — is a **non-normative
predecessor convention** carried from the retired
`Documents/retired-documents/SRS-revision2.md` §4.1 `REQ-EXT-095`. The retired
document is citable only for endpoint details the lean SRS leaves open; the
convention is not upgraded to a lean requirement, and the full condition set on
`CategoryDiscoveryResult.conditions` keeps every applicable condition visible
regardless of which one is selected as terminal.

**12.5 RESOLVED — endpoint details are capture-confirmed.** `LREQ-EXT-010` and
`LREQ-EXT-100` require "the parent SRS Coveo endpoint, required headers" and rate
limiting, but the lean SRS never states the URL, the header set, the rate-limit
interval, the backoff base, or the retry count. Sources: the **retired
predecessor** `SRS-revision2.md` §4.1 for the endpoint and constants, plus the
operator's capture for the wire shape actually observed.

- Endpoint: `POST
  https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2?organizationId=unitytechnologiesproductionmkahteav`
  (`COVEO_ENDPOINT`, `COVEO_ORGANIZATION_ID`). The organization id in that URL
  matches the capture's own organization.
- Offset convention — **confirmed, not best-effort**: the capture is pager
  `number` 2 (1-based) with `firstResult` 96 and `numberOfResults` 96, so
  `firstResult = page_index * PAGE_SIZE` under this plan's 0-based `page_index`
  (`page_index` 1 → 96). The retired document's `OI-7` no longer leaves this open
  for our traversal.
- Headers (`COVEO_REQUIRED_HEADERS`, plus the call-time `Authorization`):
  `Content-Type: application/json`, `Accept: application/json` (the capture
  sends `*/*`; ours is stricter and still valid — recorded divergence), and
  `Referer: https://assetstore.unity.com/` (capture-confirmed). `Origin` is
  **dropped**: the capture sends none. `COVEO_REQUIRED_HEADERS` excludes
  `sec-ch-ua*`, `sec-fetch-*`, `priority`, `pragma`, and `cache-control`.
- `COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0`,
  `COVEO_BACKOFF_BASE_SECONDS = 2.0`, `COVEO_MAX_RETRIES = 5` stand as written,
  taken from the retired predecessor's `REQ-EXT-100`. No new constants, and no
  `config.py`/`models.py` change.
- The retired predecessor's `A-1` (`timezone` "MAY default to `"UTC"`" and does
  not affect `ec_category` filtering) is satisfied by replaying the capture's own
  `timezone` (§12.6) rather than by inventing a default.

**12.6 RESOLVED — the request body is the capture, replayed verbatim minus two
telemetry blocks, with four mechanical edits.** Replayed verbatim: `locale`,
`tab`, `referrer`, `timezone`, `context`, `dictionaryFieldContext`, `searchHub`,
`sortCriteria`, `numberOfResults`, and `facetOptions`. The only omissions are
telemetry: `actionsHistory` → `[]` and `analytics` removed entirely. The four
mechanical edits are `actionsHistory` → `[]`, `analytics` removed,
`firstResult` 96 → 0, and `visitorId` → `COVEO_VISITOR_ID_PLACEHOLDER` (a fixed
constant; never the captured per-browser UUID). The only other divergence is
§12.1's `fieldsToInclude` override and the single-facet rule.

**12.7 RESOLVED — no action.** `discover_category` takes both
`config: NicheScoutConfig` and `credentials: Credentials`, so no new
configuration key is needed: the Coveo rate-limit interval, backoff base, and
retry count are module constants, matching `pyproject.toml`'s `dependencies = []`
and Chunk 0's guard that unsupported configuration keys raise `ValueError`.
Operator configurability of `COVEO_MIN_REQUEST_INTERVAL_SECONDS` or
`COVEO_MAX_RETRIES` would require a `models.py`/`config.py` change owned by
another chunk and stays out of scope.

**12.8 RESOLVED — the credential path, with one required behavior.** The matrix
(line 68) lists completion chunks `Chunk 3, Chunk 5, Chunk 12` for
`LREQ-SEC-010` ("Coveo and Unity CSRF credentials SHALL be read from environment
variables and SHALL be required before network collection"), so this chunk's
obligation is the Coveo adapter's own use of `get_credentials()` before any
network call. The accessor consumed is **`Credentials.coveo_bearer_token`**
(`config.py` lines 104–107; `interfaces/chunk-00.md` §5), an alias property for
the dataclass field `coveo_token`, not a `credentials.coveo_token` accessor on
the wire path. There is **no token-minting step**: the
operator-supplied bearer goes straight into `Authorization`; the earlier draft's
`/rest/search/token` reasoning is deleted as unfounded.

Added required behavior (§7 and §11, tested): `build_coveo_headers` must
normalize a leading `"Bearer "`/`"bearer "` scheme prefix **out** of the supplied
value before re-prefixing. `.env` stores the credential as `"Bearer eyJ…"`
(line 2) and `config.get_credentials()` only `.strip()`s it (`config.py` lines
286–287), so without normalization the wire header would become
`Authorization: Bearer Bearer eyJ…`. No existing test catches this because every
test injects a fake opener.

CSRF stays out of the Coveo adapter: the capture carries no `X-CSRF-Token` and
no cookie, and the Unity CSRF token remains Chunk 5's.

**12.9 REQUEST SIDE SETTLED; RESPONSE SIDE AND THE EXTRACTION VERIFICATION
OBLIGATION REMAIN OPEN (corrected 2026-09-18 — this entry's heading previously
read "RESOLVED on the request side; response-side text stands as written.",
which read as a clean bill of health for the whole entry and is a framing this
plan no longer carries; no substantive text below was deleted, and the
request-side finding it recorded is unchanged and still stands).**
Request-side fixtures anchor to `config/coveo_search_template.json` plus the four
mechanical edits of §12.6; they no longer depend on a hand-derived template. The
response-side fixtures (`totalCount` shape, `ec_category` scalar-vs-array,
`permanentid`/`ec_product_id` typing) remain **hand-derived assumptions about the
live contract**, because the SRS forbids live calls in tests and the capture
covers the request only. So `LREQ-EXT-050`'s "verified `totalCount`" and
`LREQ-EXT-080`'s scalar-vs-array handling are still validated against fixtures
that encode assumptions, not against the live contract itself.

**The two gaps recorded around this entry are distinct and both remain open.**
*This* sentence records the **response-shape** gap: the fields above
(`totalCount` shape, `ec_category` scalar-vs-array, `permanentid`/`ec_product_id`
typing) are asserted against assumptions about the live response, so the
fixtures encode the contract as inferred rather than the contract as captured.
The paragraph below records a different gap — the URI-extraction *rule* of
`interfaces/chunk-01.md` §4.1 — with a different scope, a different owning
document, and a different obligation. Neither paragraph's gap is closed by the
other, and the request-side settlement of §12.1/§12.6 covers neither.
**Outstanding, no chunk:** the response-shape obligation is not owned by any
chunk any more than the extraction obligation is, so a later chunk's brief needs
it recorded rather than assumed closed. It does not name Chunk 3 as its owner
and does not add to Chunk 3's gate.

**Pointer note — disambiguating the two gaps under §12.9 (added
2026-09-18, no substance changed).** The three paragraphs
recorded under this entry are **two separate gaps and a shared ownership
finding**, and closing one says nothing about the other. The **response-shape**
gap is the original body paragraph at the top of this entry alone, and it is
about what the fixtures assume the live response *looks like*: `LREQ-EXT-050`'s
"verified `totalCount`" — result-count integrity, i.e. whether the count a real
response reports can actually be relied on to terminate pagination
(`LREQ-EXT-050`: "It SHALL stop when the verified `totalCount` is reached") —
and `LREQ-EXT-080`'s "Scalar and multi-valued category response shapes SHALL be
handled explicitly". It is **not** about identity or URI extraction, and no part
of it is a statement about how an identifier is derived from a `clickUri`/`uri`
value. The **extraction** gap is the later paragraph below that begins "The
extraction obligation is UNMET and OPEN": it is about the *inferred rule* by
which a URI's trailing numeric segment is read as an identity candidate
(`interfaces/chunk-01.md` §4.1), i.e. how a value is turned into an identity,
not about the shape of the response that carries it. It is **not** a
response-shape finding. **Both gaps remain OPEN and neither is verified** — the
response-shape fixtures still "encode assumptions, not ... the live contract
itself" (the original body sentence, left verbatim above), and the extraction
rule still "stays **inferred and unverified**" (the later paragraph below) — and
the request-side settlement that gives this entry its heading settles neither.
The "**Outstanding, no chunk**" finding is a third thing again: it records that
*ownership* of these obligations is unassigned, not that either obligation has
been discharged, and it applies to both.

**The extraction obligation is UNMET and OPEN, and §12.9 does not discharge it.**
`interfaces/chunk-01.md` §4.1's caveat places an obligation on Chunk 3 —
sanity-check the inferred URI trailing-identifier extraction rule against real
redacted fixtures "before treating it as final" (`interfaces/chunk-01.md`
§4.1 "Caveat Chunk 3 must verify (plan RN-1, not a defect in this chunk)". The
file's §4.1 caveat paragraph is no longer the last word on this obligation:
`interfaces/chunk-01.md` §4.1 now carries three further paragraphs after it —
"Satisfaction condition of the caveat above — explicitly RELAXED by human
ruling", "The exposure deferral leaves open", and "What `1.0.1` is" (the same
dotted section, after the bolded caveat; cited by paragraph title rather than by
line number, which is not stable across edits). The relaxation changes *who may
treat the deferral as satisfying the obligation*; it does not convert the rule
into a verified one, and it does not make the extraction rule verified here.)
**This chunk did not perform that check and does not claim to have discharged
it.** Declaring extraction out of scope for this chunk does not discharge it
either — the obligation is a different document's imposition. The extraction
half of mapping rule `1.0.1` therefore stays **inferred and unverified**, and
**no real captured Coveo response exists anywhere in this repository** to
discharge it against: this chunk's own capture is a **request** capture, so it
could not settle a response-side extraction question even if it had been
examined for that purpose, and `1.0.1` deliberately left extraction untouched
(`interfaces/chunk-01.md` §4.1, "What `1.0.1` is"). The obligation currently
owns **no chunk** and is recorded in
`requirements-dependency-map.md` §6.4 so it survives into a later chunk's brief.
Verified here by reading `interfaces/chunk-01.md` §4.1 in full (its caveat
paragraph through its "What `1.0.1` is" paragraph), not by a search result.

What *is* settled, and is the only part of this entry that ever was: the
**request**-side capture question (§12.1, §12.6) — the adapter replays the
committed `config/coveo_search_template.json` rather than a hand-derived
template. If a real redacted Coveo response capture ever lands, the extraction
rule must be re-examined before this plan's response-side fixtures are treated
as more than assumptions.

**12.10 CONSUMPTION, NOT AMENDMENT — the page sink is
`insert_raw_discovery_observations` inside `category_transaction`.** This chunk
consumes three frozen interfaces (`chunk-00.md`, `chunk-01.md`, `chunk-02.md`)
and amends none. From `chunk-02.md` it consumes `category_transaction`,
`insert_raw_discovery_observations`, `update_raw_discovery_identity`,
`set_category_status`, and the read/count APIs.
`insert_raw_discovery_observations` is part of Chunk 2's frozen surface
(`interfaces/chunk-02.md` §3, lines 269–270 and 330–333), so using it is
consumption. `append_raw_discovery_observations` is **not** swapped in as the
page sink. Code basis (`src/niche_scout/database.py`):

- `insert_raw_discovery_observations` (`database.py` lines 1239–1245) is a thin
  delegation: `self.append_raw_discovery_observations(observations,
  batch_size=max(1, len(observations)))` (line 1243–1245). It is declared in the
  frozen protocol at `interfaces/chunk-02.md` lines 269–270.
- `append_raw_discovery_observations` (`database.py` lines 1247–1272) raises
  `RepositoryError` when `in_category_transaction()` is false (lines 1267–1272),
  so it must be called inside an active `category_transaction` — which §11
  forbids the adapter from opening for itself.
- `category_transaction` (`database.py` lines 1043–1106) opens `BEGIN` when it
  owns the outermost transaction plus `SAVEPOINT` (lines 1076–1079), rolls back
  and releases on `BaseException` (lines 1083–1092), and releases/commits on
  success (lines 1093–1099).

Hence `category_transaction` + insert-per-page is the pattern the database
expects — the append-once-per-page alternative would move the transaction
boundary out of the adapter's control and reintroduce the per-category
in-memory identity state §9 and §11 forbid. **Implementer guard:** confirm
`insert_raw_discovery_observations` exists in the implemented `database.py`
before use; if it is absent, STOP and report (§7).

**12.11 OUT-OF-SCOPE FINDING (does NOT block this freeze) — `runs.taxonomy_sha256`
has no owning chunk.** `RunRecord` validation covers only the UTC fields
(`interfaces/chunk-00.md` §4.1) and the persistence layer rejects only `None`,
not `""` (`database.py`, `taxonomy_sha256 TEXT NOT NULL`), so an empty hash would
persist silently and `LREQ-NFR-020`'s provenance chain could complete with an
empty `taxonomy_sha256` value. Owner: **Chunk 10**, the only chunk that
constructs a `RunRecord`. The finding is recorded in
`requirements-dependency-map.md`'s open-items list (§7) so it survives into
Chunk 10's brief. **Chunk 10 remains the owner; the new
`requirements-dependency-map.md` §6.4 entry is a different, ownerless item — the
deferred URI extraction verification of §12.9 — not a second recording of this
one.** Chunk 3 must **not** implement it: it propagates the placeholder value
verbatim (§12.1, `interfaces/chunk-03.md` §8, §11). This is an out-of-scope
finding, not an open question: no human decision is pending on it, and it does
not block the freeze.

**Pointer note — disambiguating the `§8` pointer in §12.11 (added
2026-09-18, no substance changed).** That parenthetical
previously read `(§12.1, §8, §11)`. The bare `§8` was ambiguous: unqualified, it
reads as this plan's own §8 ("Edge cases and invariants"), whereas it means
`interfaces/chunk-03.md` §8 — a section whose heading and body now read an
open, chunk-less URI-extraction obligation as **owed**.
(corrected 2026-09-18: this clause previously read "`interfaces/chunk-03.md`
§8 — a section that is deliberately **non-contractual** and records an open,
chunk-less URI-extraction obligation", which no longer matched that section's
rewritten heading and body; the "non-contractual" label is dropped and the
em-dash form is retained because the clause sits inside a sentence that began
"whereas it means". The clause's meaning is unchanged.) Two further bare `§8`
pointers in §7 and §11 meant the same thing and were disambiguated in the same
pass; each carried a "Caveat Chunk 3 must verify (plan RN-1, not a defect in this
chunk)" citation that already identified the target. (corrected 2026-09-18: this
sentence previously read "Two further bare `§8` pointers in §7 and §11 meant the
same thing and were disambiguated in the same pass", and its premise is false.
Read of the parent revision `c839f4d^` — re-runnable as
`git show c839f4d^:Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
— shows §7's pointer was **already qualified** at the parent, reading
"`interfaces/chunk-03.md` §8" (`c839f4d^`:522), and `c839f4d` did not change that
line at all; §11 carried **no `§8` pointer at all**, its parenthesis reading
"…recorded in §12.9 and `requirements-dependency-map.md` §6.4"
(`c839f4d^`:776-777), and `c839f4d` **added** the qualified
"`interfaces/chunk-03.md` §8" pointer there. No bare `§8` was disambiguated in
either section; `c839f4d` added one pointer to §11 and left §7 unchanged. The
operative claim below — that the §7 and §11 pointers now name their target
explicitly — is **not** withdrawn and remains true.) Unqualified `§9` and `§11`
pointers were left as they are: both are this plan's own sections when read in
context, and §9/§11 are the plan's own section numbers.

**12.12 RESOLVED — the second numbered resolution entry in §12.1: the committed
capture is 5 fields / 1 facet, and the original capture's 23 fields / 6 facets
are recorded as superseded history, not as a description of the file on disk.**
This entry exists because §12.1 previously described only one state — the
23-field / 6-facet capture — while the artifact it names has carried the trimmed
5-field / 1-facet shape for the whole history the repository records, and a
reader could not tell which was a claim about the file on disk. The two states,
what each one is, and the requirement the trim comes from are set out in §12.1;
this entry records **why the number is where it is** and **what is deliberately
left open**, again numbered so the earlier reviews' numbering is untouched.

- **Both states are now described, and only one of them describes the
  artifact.** §12.1's "the original capture" bullet is the historical state; its
  "the committed artifact is the trimmed form, and it is what ships" bullet is
  the measured current state (counted: `json.loads` over
  `config/coveo_search_template.json`, then `len(request_body["fieldsToInclude"])`
  → 5 and `len(request_body["facets"])` → 1). The 23/6 description is preserved
  because it is the record of what the operator's capture contained and of why
  the adapter must not replay it; it is **not** a claim about the committed file.
- **The trim is attributed, not invented.** `LREQ-EXT-040`
  (`Documents/SRS-lean.md:254-257`) names the five members verbatim and forbids
  sourcing rating, page views, publication date, and price from Coveo for
  scoring; §7 forces the same set at build time and §11 carries the matching
  prohibition. No new normative text is added by this entry.
- **The provenance question stays visibly open.** The repository cannot
  establish whether the file was trimmed after capture or §12.1's narrative was
  written against a different artifact: counted, `git log --oneline --
  config/coveo_search_template.json` returns one commit (the working-tree
  snapshot) and `git diff HEAD` on that path is empty, so there is no earlier
  revision to inspect. §12.1 records both readings and chooses neither. This is
  a provenance finding, not a scope question: it does not block this chunk's
  freeze, and it is deliberately left for a human, because clearing it would
  require asserting a cause that no artifact in the repository evidences.
- **No product behavior depends on the open half.** The adapter replays the
  committed file, forces the five-field set and the single-facet rule at build
  time, and its constants carry members rather than lengths
  (`COVEO_DISCOVERY_FIELD_SET`, `COVEO_DROPPED_FACET_IDS`,
  `COVEO_FACET_ID` in `collector_coveo.py`). The `LREQ-EXT-040` /
  `LREQ-EXT-010` assertions in `tests/test_collector.py` are stated against the
  constants and against the capture's own facet values — not against a length —
  so neither a 5/1 nor a 23/6 committed file changes a tested behavior. This is
  a shape claim about the assertions' subject; the assertion count is not
  asserted here (unverified), and the code-side observation the implementer
  recorded is the strongest available support for it
  (`collector_coveo.py` `COVEO_DISCOVERY_FIELD_SET` /
  `COVEO_DROPPED_FACET_IDS` docstrings, which state that they assert the members
  and not a length).

**Commit-message correction — `c839f4d`'s message misdescribes two of the
changes it landed (recorded 2026-09-18; the commit is NOT amended).** The message
of `c839f4db152a2b1b8865ecbafb3a8cd1d3e1bb46` contains two clauses that do not
describe the landed change, quoted verbatim:

- "retitle and disambiguate the chunk-03 plan's two pointer notes"
- "disambiguate … the bare section-8 pointer"

What the commit actually did, verified by reading both revisions with
`git show c839f4d^:<path>` and `git show c839f4d:<path>` on
`Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`:

- **The two `Pointer note` blocks are new, not retitled.** Both file revisions
  were read in full: `git show c839f4d^:<path>` contains **zero** occurrences of
  the string `Pointer note`, while `git show c839f4d:<path>` contains **two**
  (counted in Python with `str.count` over the decoded blob, unit: occurrences of
  that substring in the whole file, 0 → 2). Independently, scanning the commit's
  own diff for lines that were *added* and contain the same substring yields
  exactly **2** (unit: added diff lines containing `Pointer note`, 2), against
  **63** added lines for that path in total. Nothing was renamed: there was no
  prior block to rename.
- **The authorship is established by pickaxe, re-runnable verbatim:**
  `git log --oneline -S "Pointer note" -- Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
  returns exactly **one** commit — `c839f4db152a2b1b8865ecbafb3a8cd1d3e1bb46
  docs: add verification-discipline rule section and land
  chunk-01/chunk-03/RN-1 corrections` (unit: commits returned, 1). The blocks
  originate with `c839f4d`.
- **Only one bare section-8 pointer ever existed, and it was the §12.11 one.**
  §11 had no `§8` pointer at the parent and gained a **qualified**
  `` `interfaces/chunk-03.md` §8 `` pointer; §7's pointer was already qualified
  and was **left unchanged**. So beyond the §12.11 parenthetical that the pointer
  note above addresses, the commit clarified no bare section-8 pointer, and
  "disambiguate" implies a third such pointer that did not exist. The pointer note
  above carries the same finding with its line citations.

**The commit is deliberately not amended or rebased.** It is stated history, and
this project does not rewrite history: the correction is recorded here instead, so
that a reader who finds the commit message also finds what actually landed. This
note changes no requirement, no scope, and no gate.

**12.13 RULED — `state` moves out of the structural required-member group into
the semantic state group; and this entry also corrects the refuted premise that
the node-5 ruling originally rested on (recorded 2026-09-18).** Two things are
recorded here and they must not be read as one. The **ruling** (§12.13(i)–(iv))
is a decision about Chunk 5's code and about the frozen documents this plan
depends on; the **correction** (§12.13(v)) records an error this plan's earlier
node-5 reasoning made and then withdrew. Neither is Chunk 3 implementation work:
§6 does not list `collector_graphql.py`, and every code change below is Chunk
5's.

**(i) The ruling — what moves, and where to.** `state` leaves the structural
required-member group and joins the semantic state group
(`StateEligibilityAnnotation`, whose `state_unknown` is the
`missing/null/unparsable` state). Concretely: `PRODUCT_DETAIL_REQUIRED_MEMBERS`
(`src/niche_scout/collector_graphql.py:876-885`) loses `state`, and the
`validate_response_shape(..., required_members=...)` call
(`collector_graphql.py:1050-1055`) therefore stops asking Chunk 1 for a
`response_missing_required_member`/`response_null_required_member` verdict on
it. The Chunk 5 plan's E7 (`Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md:1311-1315`),
which reads "`product` present but not an object, a required member missing, and
`state` present but not a string are each an operation error for `ProductDetail`",
is corrected **as one unit with the constant** to match the same plan's §5.8
(`:914-923`, "keeps the raw `state` string in `ProductDetailFields.state`
(verbatim, including a `None` for a missing state)") and E10 (`:1328-1332`, "a
missing, null, or wrong-typed value is `state_unknown`"). Splitting the two —
moving the constant without correcting E7 — is what this entry forbids: it would
leave Chunk 5's frozen plan asserting a check that no longer exists. Note the
wording that must survive the correction: E10's "missing, null, or wrong-typed
value is `state_unknown`" is a rule about the *annotation*, not about the
operation outcome, so correcting E7 does not mean that every missing-null-wrong-
typed `state` is benign — only `missing` and `null` are.

**(ii) The correction — the tie-break source was misattributed.** The node-5
reasoning claimed a frozen interface said something it does not say. The
sentence "Absent, null, and wrong-typed members each produce their own issue
code, stay `None` in the returned fields, and are never substituted with a
default" is at
**`src/niche_scout/collector_graphql.py:1022-1027`, inside the docstring of
`_validate_product_detail_payload`** — it is a **Chunk 5 docstring describing
Chunk 1's behavior**, not text in `interfaces/chunk-01.md`. The interface's
entire prose for its own state function is this two-sentence contract, quoted
verbatim in full:

`Documents/interfaces/chunk-01.md:315-317`
> - **`annotate_state_eligibility`** is an annotation, not a decision:
>   `remains_in_discovered_breadth` is always `True` and the result exposes no
>   D/R/Q eligibility attribute.

That is the *entire* prose contract for the function. It is SILENT on whether a
missing, null, or wrong-typed `state` is an operation error or a benign
annotation, so it cannot be the tie-break source it was said to be, and it does
not outrank the code on that question.

**(iii) Why the ruling is the right one anyway — the mechanical proof, so a
future reader does not have to re-derive it.** The interface is silent, the SRS
is silent on the producing side, and the plan split resolves 2–1 with code
agreement, as follows.

- `Documents/interfaces/chunk-01.md:133-139` defines the annotation's fields:
  `state_value: str | None`, `is_published: bool`, `state_excluded: bool  #
  present but not "published"`, `state_unknown: bool  # missing/null/unparsable`,
  `remains_in_discovered_breadth: bool  # always True (annotation only)`.
- `interfaces/chunk-01.md:272-282` (§4.2) lists `response_missing_required_member`
  and `response_null_required_member` as two distinct codes and states **no
  condition** for either and **no** generic-versus-specific rule, and
  `interfaces/chunk-01.md:284-286` is the only ordering statement in that
  section — it governs issue **sort** order, not check order. (`:3` reads
  `Status: VERIFIED`; `:10-15` declares the body frozen.)
- The condition semantics exist only in
  `src/niche_scout/validation.py:1760-1779`: absent → 
  `response_missing_required_member`; present-but-null →
  `response_null_required_member`; and `:1781-1796` → wrong type →
  `response_wrong_scalar_type`. There is **no state-specific code in Chunk 1**,
  so the codes fire only for members a caller declares as required.
- **The only `state_unknown` mention in the SRS is
  `Documents/SRS-lean.md:329-330` (LREQ-GQL-060)**: "Only `state = \"published\"`
  assets are eligible for D, R, and Q. State-excluded and state-unknown assets
  remain part of discovered breadth." It describes RETENTION of assets that
  already are state-unknown and never what PRODUCES that state.
- The plan splits **2–1**: §5.8 (`chunk-05` `:914-923`, raw state kept
  verbatim, including `None` for a missing state) and E10 (`:1328-1332`) agree
  with the ruling; E7 (`:1311-1315`) contradicts them.
- **Mechanical proof, by reading:** `collector_graphql.py:1050-1055` calls
  `validate_response_shape` with `required_members=PRODUCT_DETAIL_REQUIRED_MEMBERS`
  and does not short-circuit. For `state` absent: `:1137` yields
  `state_value = None`, `:1138` yields `state_unknown = True`, and `:1148`'s
  guard is `state_annotation.state_unknown and state_value is not None` →
  `True and False` → `False`, so **no** `invalid_state_value` fires;
  `:1199-1200` maps that code to `INVALID_STATE_VALUE`, and `:1182-1189` returns
  the class with `product_detail=None` unless the class is `NONE`. So a *state*
  value alone never makes the operation an error on the missing/null path, and
  the fully-built `fields` object carrying `state_unknown=True` is discarded
  when another member fails — no caller can observe a `SUCCESS` operation with
  `state_unknown == True` for a *state* reason. The guard's two sides only
  diverge for a present-but-unusable value: a present non-string yields
  `state_value` non-`None` and `state_unknown=True`, so `:1148` fires and
  `:1154-1157` records `invalid_state_value`, which `:1199-1200` maps to
  `INVALID_STATE_VALUE` — exactly the half that must not regress.

**(iv) The node-5 change is NOT chunk-3-local.** It changes Chunk 5's
observable behavior (`ProductDetail` payloads with a missing or null `state`
stop being operation errors and start validating with the state annotated
unknown), which is why **Chunk 5 gets a retroactive plan and interface first**
and this chunk's fix wave runs after that contract is published rather than
against a document that does not exist yet. This plan records the ruling and
the mechanical proof; it does not build against a Chunk 5 contract that is not
yet published.

**(v) What this plan does NOT do, and why.** No file under `src/` was touched
for this entry, `collector_graphql.py` is not in §6, and the `state` move is
Chunk 5's to land. The tests that pin the change are declared, not written
(§7), because this wave is documentation-only. `interfaces/chunk-03.md` is
**not** edited for this ruling: it contains no claim the ruling falsifies — it
says nothing about `ProductDetail`, `state`, or GraphQL operation outcomes; its
own `mapping_rule_version` discussion is about `LREQ-EXT-060`/`070`/`080`
identity candidates, a different subject. The 2–1 plan split is evidenced above
by reading two separate sections of the Chunk 5 plan, which is permitted as
context; this plan does not edit that file.

**12.14 RULED — the enforced response-side exclusion set and the allowed request
set are different artifacts, and a reader must not collapse them (recorded
2026-09-18).** This entry exists because three artifacts appear to publish
"the forbidden fields of `LREQ-EXT-040`" and only one of them is enforced. All
three were opened and read; the counts are member counts from the AST or from
the literal, not line counts, and each query is stated so it can be re-run.

| Artifact | What it is | Members | Where |
|---|---|---|---|
| `SAMPLE_OUT_OF_SCOPE_FIELDS` | the **test-only** sample set used to walk assertions | **8** | `tests/test_collector.py:85-94` (`tests/` is outside this wave's scope) |
| `COVEO_DISCOVERY_FIELD_SET` | the **allowed request** set — never a prohibition list | **5** | `src/niche_scout/collector_coveo.py:161-167` |
| `COVEO_DROPPED_FACET_IDS` | a **facet-drop** vocabulary, not a field blocklist | **5** | `src/niche_scout/collector_coveo.py:175-181` |

- **The 8.** `("ec_rating", "ec_rating_count", "ec_price", "ec_price_filter",
  "ec_sale", "ec_thumbnails", "first_published_at", "ec_popularity")` — counted
  by `ast.parse` over `tests/test_collector.py` and reading the tuple's `elts`:
  8 (`python -c` AST, unit: tuple elements). It is a *sample* the tests walk; the
  file's own comment says so ("It is not a list the SRS defines") and points at
  the read of the enforcement mechanism.
- **The 5 allowed.** `("permanentid", "ec_product_id", "ec_name", "ec_category",
  "publisher_name")` — counted the same way over
  `src/niche_scout/collector_coveo.py`: 5 (unit: tuple elements). This is the
  set `LREQ-EXT-040` names, and it is the **request** set.
- **The 5 dropped.** `("ec_sale_filters", "ec_price_filter", "ec_rating",
  "first_published_at", "publisher_name")` — counted: 5 (unit: tuple elements).
  These are the capture's facets the adapter drops, not response fields. The
  overlap with the allowed-5 is exactly one member, `publisher_name`.
- **Overlap between the 8 and the 5 allowed is zero**, counted as a set
  intersection over the two tuples above (unit: members). So adopting the 5 as a
  blocklist would not narrow the rule, it would **invert** it: the 5 are the
  members the adapter *requires*.
- **`ec_rating_count` has no `LREQ-EXT-040` authority.** Its own comment
  (`tests/test_collector.py:79-84`) derives it from §4.2's source-separation rule
  ("GraphQL is authoritative for rating, rating count, review count, first
  publication date, page views, publisher, category, state, and product identity
  confirmation. Neither source SHALL provide duplicate scoring fields for the
  same metric.") — rating count has a GraphQL owner, so Coveo sourcing it would
  be a duplicate source rather than an unlisted member. Authority: §4.2, not
  `LREQ-EXT-040`.
- **Nothing in `src/` enforces a member blocklist at all.** Counted by grep over
  `src/`: the only occurrences of the members `ec_rating`, `ec_price`,
  `ec_thumbnail*`, `ec_sale*`, `first_published_at`, or `ec_popularity` are
  `collector_coveo.py:176-179`, inside `COVEO_DROPPED_FACET_IDS` — the
  *facet-id* vocabulary (unit: matching lines in `src/`, 4). A narrower query
  for the substring `ec_rating_count` anywhere in `src/` returns **zero** rows
  (unit: matching lines). So the response-side rule has no blocklist to narrow
  or widen: it is the **allow-list complement** at
  `collector_coveo.py:1123-1130` (`if any(key not in
  _DISCOVERY_RESPONSE_FIELD_SET for key in item)`), which records presence by
  count and record index only. **The 8 is a sample the tests walk, not the
  enforced list** — and a future reader who wants the enforced set should read
  `COVEO_DISCOVERY_FIELD_SET`, not any blocklist.
- **`interfaces/chunk-03.md` carried a prose list here and it was wrong on three
  counts** (misspelled `ec_thumbnails` as `ec_thumbnail`, named an invented
  "popularity" member, and omitted `ec_rating_count`, `ec_price_filter`,
  `ec_sale`, and `first_published_at`); it has been corrected in this wave to
  the allowed-request/complement story above, and its `CoveoPageResponse`
  annotation now states what a `forbidden_field_presence` entry actually is.
  `COVEO_DISCOVERY_FIELD_SET`'s own module comment
  (`collector_coveo.py:153-160`) repeats the capture's "23 entries" figure
  verbatim in `_redacted_request_metadata` (`:774-778`), so that figure is
  persisted into every observation's `request_metadata_json`; it is a restated
  open discrepancy (§12.1, §12.12), not a Chunk 3 measurement, and it is
  recorded here rather than changed, because `collector_coveo.py` is not in §6.
- **What this wave changed, and where.** Exactly one of the three artifacts is
  inside this wave's scope: `interfaces/chunk-03.md`. Its §2 bullet and its
  `CoveoPageResponse` annotation were corrected;
  `tests/test_collector.py:85-94` has no residual defect and was not touched,
  and `collector_coveo.py` is not in §6.

**Dated correction — the framing that produced §12.14 (recorded 2026-09-18).**
An earlier review framed this material as "§12.1 names 8 forbidden fields; §11
names 5" and asked which list was correct. That framing is withdrawn: §12.1
names no 8-member list and §11 names no 5-member list. The real artifacts are
the three rows of §12.14's table, and the "8" and the "5" are different units
(8 members of a test sample; 5 members of the allowed request set), not two
versions of one list. No count in this correction is asserted from the earlier
framing.

**Dated corrections — two locant/name errors in this plan's own review
reasoning (recorded 2026-09-18; the earlier text is quoted, not deleted).**

- **`ProductDetailFields` construction locant.** The review cited the
  construction as `collector_graphql.py:1178`. Read on current HEAD, `:1178` is
  the **`state_annotation=` argument line inside that constructor call**, and
  the constructor call itself begins at `:1160`
  (`fields = ProductDetailFields(`), with `:1177` the `state=` argument line.
  The correction is `:1178 → :1160` for the construction, `:1178` for the
  `state_annotation` argument. Re-runnable read: lines `1160-1189` of
  `src/niche_scout/collector_graphql.py`.
- **The Chunk 5 plan's filename.** The review referred to it as
  `chunk-05.md`. **No such file exists.** The filename is
  `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md`
  (verified by listing `Documents/plans/`: `_TEMPLATE.md`,
  `chunk-00-project-skeleton-and-contracts.md`,
  `chunk-01-pure-taxonomy-identity-and-response-validation.md`,
  `chunk-02-sqlite-implementation-and-repository.md`,
  `chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`,
  `chunk-05-graphql-protocol-adapter-and-response-correlation.md`,
  `tooling-p0-2-traceability-blind-spot.md` — unit: files listed, 7). Every
  reference to the file in this entry uses the full name.

**(vi) One self-correction inside this entry, recorded rather than removed.** An
earlier draft of this entry asserted that `interfaces/chunk-01.md:272-282`
"states no generic-vs-specific rule" — that is correct — but also that a
*false* sentence about the Chunk 5 docstring's location had been corrected by
this author. It had not: this entry **is** that correction, and it was written
after the misattribution was found by reading both locations
(`collector_graphql.py:1022-1027` and `interfaces/chunk-01.md:315-317`) rather
than by trusting a search result.

**Dated correction — the Status region was amended to carry a footnote, so that
`VERIFIED` stops reading as a green-suite claim (recorded 2026-09-18).** The
plan's `Status:` line read `VERIFIED` with no annotation, beside six failing
tests in `tests/test_collector.py`; read together, that juxtaposition stated a
claim this chunk's own gate had passed a green suite, and it did not qualify
which chunk the red tests belonged to. The line now carries a footnote naming
those six nodes and their counts, and the footnote — not this entry — is the
correction; this entry records that it was made and why.

- **`Status: VERIFIED` was retained deliberately, not by inattention.** The six
  failures are another chunk's: they belong to Chunk 5's still-in-development
  test family, they live in `tests/test_collector.py`, and none of them
  documents a defect in a file this chunk owns. Correcting the record was
  therefore the right move and flipping the Status was not.
- **This entry does not re-open §10's gate bullets.** No bullet in §10 was
  re-checked, re-scored, or re-litigated here, and none that the footnote's
  addition touches changes state; the §10 bullets are unchanged and re-read
  after this edit as six verbatim gate bullets followed by a four-line
  non-scoring note recording that they were not re-scored.
- **What is recorded, and where.** This entry is the kind §12's preamble
  describes at `:920-946`: an entry that adds notation to the record without
  closing a scope question. The §7 defect flagged alongside this correction —
  three `- [ ]` boxes at `:590`, `:603`, and `:626` describing work in Chunk 5's
  files, which this plan's own convention would put in §12 and §6 instead — is
  **not** part of this correction, by the same ruling: it is deferred and
  travels in its own commit. No source file, test, fixture, `traceability.json`
  entry, or §10 bullet is touched by this entry; the only file this correction
  edits is this plan.

**Placement, and why this entry is unnumbered.** It follows §12.14 and the
corrections that post-date it, at the end of §12, because it closes no numbered
scope question and resolves nothing in §12.1–§12.14: it records a change to the
front-matter Status region, which is the one region §12's numbered entries do
not cover. No §12.15 exists and none is implied.

**Dated corrections — two stale locants asserted about this document later in
this same chain (recorded 2026-09-19).** Both claims below were re-derived by
reading this file at its current revision rather than carried forward from the
reviews that made them, and each was false at the revision it was asserted
against. The earlier text that carries both locants is retained as superseded,
not deleted; the paragraphs above are quoted, not rewritten, and nothing in
§12.1–§12.14 or in §10's gate bullets changes.

- **The Status footnote's extent is `:4-47`; the earlier locant `:4-27` was
  stale.** Three live paragraphs cite the footnote as `:4-27` — the exclusion
  list at `:144`, the §7 preamble at `:483`, and the §10 preamble at `:865`.
  Read now, the footnote opens at `:4` and its last line is `:47` ("documents
  the exact suite composition that produced it."); `:48` is
  `Published contract:`, the next front-matter field. The footnote grew past
  `:27` at the 2026-09-18 correction pass that the footnote's own second line
  records, so `:4-27` now ends mid-sentence rather than at a boundary. The
  correct citation is `:4-47`. **The earlier draft of this correction asserted
  four such occurrences and also that the footnote "cites itself" at `:4-27`;
  both are wrong** — a substring query over the whole file (unit: occurrences
  of the literal `:4-27`) returns exactly **11** at revision `5c0aa51`, the
  three live prose lines named above plus eight inside this note, which quotes
  the literal deliberately, and none of them is inside the footnote, which
  contains no `:4-27` string at all. The three live occurrences are `:4-27`
  occurrences in the current text; the claim that they are *live* prose rather
  than retained-as-superseded text is this note's own reading of those lines,
  not a query result.
- **The dated correction at the end of §12 that the §7 preamble cites as
  `:1676-1709` is actually `:1673-1732`.** The `:1676-1709` range resolves
  inside a *different* correction: `:1676-1683` is the first bullet of the
  entry headed at `:1673` ("**Dated corrections — two locant/name errors in
  this plan's own review reasoning (recorded 2026-09-18; the earlier text is
  quoted, not deleted).**"), and `:1705` is the hard-wrapped last line of that
  entry's second bullet — the citation therefore stops one line short of the
  entry it names. The block the §7 preamble *describes* — the entry that
  records "their conversion into this plan's §12 obligation/§6 'Not touched'
  convention is a deferred, separately-committed change" — is the entry headed
  at `:1705` ("**Dated correction — the Status region was amended to carry a
  footnote, so that `VERIFIED` stops reading as a green-suite claim (recorded
  2026-09-18).**"), which runs to `:1732` and is followed by the unnumbered
  placement paragraph at `:1734-1738`. The correct citation is `:1705-1732`.
  Two further candidate ranges proposed during the same review are also
  recorded and rejected here: `:1724-1730` is a sub-bullet of the `:1705` entry
  (the deferred-§7 paragraph, not the entry), and `:1750-1794` lies past this
  file's end (its last line is `:1739`).
- **Two locants reported in the earlier investigation are not present in this
  document at all** and are recorded here only so a later reader does not
  re-import them as citations: a sub-bullet at `:1785-1788` (past this file's
  end) and the commit hash `6ea65ce`. Both were reported by an earlier
  investigation and are **not** present in this document. No content behind
  them is recorded here as lost, recovered, or reconstructed: the working-tree
  delta those reports described was independently confirmed to have been
  superseded by committed content, so there is no content to restore.
- **Re-runnable reads for every locant above.** `grep -c ':4-27'` over this
  file (unit: occurrences) = 11 at revision `5c0aa51`; `grep -c ':4-47'` (unit:
  occurrences) = 4 at revision `5c0aa51`, which counts the live Status-footnote
  citations as well as this note's own mentions of the corrected locant.
  `:1673`, `:1705`, `:1732`, and `:1734` were each confirmed by reading those
  lines. The current revision is 1,798 lines (unit: line count obtained by
  splitting the file's 1,797 newlines, i.e. `wc -l` = 1,797).
