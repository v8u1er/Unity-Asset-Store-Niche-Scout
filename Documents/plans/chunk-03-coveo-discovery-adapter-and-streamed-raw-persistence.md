# Chunk 3 — Coveo discovery adapter and streamed raw persistence

Status: VERIFIED
Verified at: working tree state 2026-09-17; `python -m pytest tests/ -q`
(119 passed, exit 0), `python -m niche_scout.tools.validate_traceability`
(exit 0), `python -m niche_scout.tools.check_import_boundaries` (exit 0).
Published contract: `Documents/interfaces/chunk-03.md`.
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-00.md` (VERIFIED — models, constants, `config.py`
    contracts, schema/PK specification, `RunStatus`/`DiscoveryStatus`/
    `WarningCode`/`IdentityResolutionStatus`/`CategoryFilterValidationStatus`
    enums, `to_json`/`to_json_dict`/`ensure_utc`)
  - `Documents/interfaces/chunk-01.md` (VERIFIED — taxonomy, identity,
    exact-category-match, structural-validation, and redaction primitives)
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
  edit to that module and does not call it.
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
IDENTITY_MAPPING_RULE_VERSION = "1.0.0"   # "1.0.1" reserved (chunk-01.md §4.1 caveat)
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
  capture's sole `ec_category` facet with the target category's `currentValues`
  entry set to `"selected"` and every other captured value `"idle"`;
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
- [ ] Implement `discovery_status` selection: compute every applicable condition
  from `DiscoveryStatus` values (including
  `discovery_status_for_category_status(filter_status)`), keep the full
  condition set on `CategoryDiscoveryResult.conditions`, and select the single
  terminal status by the **non-normative predecessor convention** carried from
  the retired `SRS-revision2.md` §4.1 `REQ-EXT-095` —
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
  capture's own `fieldsToInclude` list is discarded in favor of the
  five-field set (§12.1, R-C).
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
  rather than assuming `1.0.0` semantics (`interfaces/chunk-01.md` §4.1 caveat).
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
  does not).
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

Every question raised in this section's earlier draft is now **resolved**; no
entry below is an open human decision. Entries are numbered as the draft numbered
them so earlier reviews remain traceable.

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
- **One deliberate exception to "replayed as captured":** `fieldsToInclude`.
  The capture's 23-entry list includes `ec_price`, `ec_price_filter`, `ec_rating`,
  `ec_rating_count`, `ec_sale`, `ec_thumbnails`, `ec_flash_teaser_starts_at`,
  and `ec_flash_promo_starts_at`, all of which §11 and `LREQ-EXT-040` forbid.
  §7 forces the five-field set (`permanentid`, `ec_product_id`, `ec_name`,
  `ec_category`, `publisher_name`); this divergence is required by
  `LREQ-EXT-040` and is not a defect.
- **The facet block ships exactly one facet.** `ec_category`, `type: "specific"`,
  `resultsMustMatch: "atLeastOneValue"`, `numberOfValues: 150`, and
  `currentValues` carrying every captured idle `ec_category` value with the
  target category marked `"selected"` and the rest `"idle"` — the
  selected-category facet mechanism of `LREQ-EXT-010`. The capture's other four
  facets (`ec_sale_filters`, `ec_price_filter`, `ec_rating`,
  `first_published_at`) and its `publisher_name` facet are dropped, and the drop
  is recorded in `request_metadata_json` with its rationale. For
  `publisher_name` specifically: `fieldsToInclude` is what makes a field present
  on a returned record, while a facet returns a separate aggregation that no
  requirement consumes, and §4.1 never scopes discovery by publisher.

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

**12.9 RESOLVED on the request side; response-side text stands as written.**
Request-side fixtures anchor to `config/coveo_search_template.json` plus the four
mechanical edits of §12.6; they no longer depend on a hand-derived template. The
response-side fixtures (`totalCount` shape, `ec_category` scalar-vs-array,
`permanentid`/`ec_product_id` typing) remain **hand-derived assumptions about the
live contract**, because the SRS forbids live calls in tests and the capture
covers the request only. So `LREQ-EXT-050`'s "verified `totalCount`" and
`LREQ-EXT-080`'s scalar-vs-array handling are still validated against fixtures
that encode assumptions, not against the live contract itself.

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
`requirements-dependency-map.md`'s open-items list so it survives into Chunk 10's
brief. Chunk 3 must **not** implement it: it propagates the placeholder value
verbatim (§12.1, §8, §11). This is an out-of-scope finding, not an open
question: no human decision is pending on it, and it does not block the freeze.
