# Chunk 3 — Coveo discovery adapter and streamed raw persistence (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
Verified at: working tree state 2026-09-17; gates `python -m pytest tests/ -q`
(119 passed, exit 0), `python -m niche_scout.tools.validate_traceability` (exit 0),
`python -m niche_scout.tools.check_import_boundaries` (exit 0).

This file is the **public contract** other chunks build against. It is not the
full source; read `src/niche_scout/collector_coveo.py` for implementation
detail. Everything below is frozen: downstream chunks may consume these names
and semantics, and SHALL NOT redefine them. Chunk 3 is an **I/O/orchestration**
module: it performs network I/O through an injected transport, reads the
captured request template from disk, and persists through the Chunk 2
repository. `metrics.py` and `scoring.py` remain pure and unmodified.

**What this chunk is.** Chunk 3 completes the Coveo side of discovery:
request construction from the operator capture, streamed per-page persistence
of raw observations, pagination with verified `totalCount` handling, rate
limiting and retry, and the *collection-side* integration of Chunk 1's
validation primitives. It consumes three frozen interfaces
(`chunk-00.md`, `chunk-01.md`, `chunk-02.md`) and amends none; the three
consumed files all exist with `Status: VERIFIED`.

---

## 1. Module and boundary rules

| Module | Kind | Rule |
|---|---|---|
| `src/niche_scout/collector_coveo.py` | **I/O + orchestration** | Coveo discovery adapter only: endpoint/headers/request builder, taxonomy preflight, pagination, ordinal + duplicate handling, identity/category classification, retry/backoff, streaming sink |
| `config/coveo_search_template.json` | Data (new) | Captured Coveo discovery request plus provenance header |

- `collector_coveo.py` imports only `hashlib`, `json`, `re`, `time`,
  `urllib.error`, `urllib.request`, `collections.abc`, `contextlib`,
  `dataclasses`, `datetime`, `pathlib`, `typing`, and the package modules
  `config`, `database`, `models`, `validation`. It SHALL NOT import `metrics`,
  `scoring`, `pipeline`, `report`, or `cli`, and SHALL NOT import `collector`
  (that would create an import cycle). The transport is the **standard
  library**; `pyproject.toml` declares `dependencies = []`, so no third-party
  HTTP client is used.
- `time.sleep` and the socket deadline are the adapter's **only** waiting
  primitives. The adapter reads no clock of its own: every timestamp
  (`retrieved_at_utc`) comes from a caller-injected `clock`, and every delay
  goes through a caller-injected `sleeper`.
- `models.py`, `collector_graphql.py`, `config/category_taxonomy.json`,
  `metrics.py`, and `scoring.py` were **not** modified by this chunk.
  `collector.py` received exactly one deliberate facade edit: the GraphQL
  star-import was expanded to an explicit re-export list because
  `collector_graphql` gained `__all__`; no other chunk's symbol was touched.
- **Null, zero, invalid, and unavailable stay distinct.** A failed field stays
  `None`; `total_count` is `None` when the endpoint's `totalCount` is
  unusable; a failed page is a failure, never a zero-asset reading.
- Determinism: identical template + category + page index produce a
  structurally identical request body. There are no random generators; the
  request is a replay of the capture with four mechanical edits.

---

## 2. Constants and vocabularies

```python
COVEO_ENDPOINT = "https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2"
COVEO_ORGANIZATION_ID = "unitytechnologiesproductionmkahteav"
COVEO_TEMPLATE_PATH = Path("config") / "coveo_search_template.json"
COVEO_VISITOR_ID_PLACEHOLDER = "niche-scout-lean-v1"   # fixed; never the captured UUID
COVEO_REQUIRED_HEADERS: tuple[tuple[str, str], ...]    # Content-Type, Accept, Referer
COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0
COVEO_BACKOFF_BASE_SECONDS = 2.0
COVEO_MAX_RETRIES = 5
COVEO_DISCOVERY_FIELD_SET: tuple[str, ...] = (
    "permanentid", "ec_product_id", "ec_name", "ec_category", "publisher_name")
COVEO_FACET_ID = "ec_category"
COVEO_DROPPED_FACET_IDS: tuple[str, ...] = (
    "ec_sale_filters", "ec_price_filter", "ec_rating",
    "first_published_at", "publisher_name")
```

- `COVEO_REQUIRED_HEADERS` is exactly `Content-Type`, `Accept`, `Referer`.
  `Authorization` is appended at call time by `build_coveo_headers`. Browser
  fingerprint headers (`sec-ch-ua*`, `sec-fetch-*`, `priority`, `pragma`,
  `cache-control`) and `Origin` are **not** sent.
- `COVEO_DISCOVERY_FIELD_SET` is the discovery-only field set. `ec_rating`,
  `ec_price`, `ec_thumbnail`, popularity, and publication-date fields are never
  requested and never read (LREQ-EXT-040).
- `COVEO_FACET_ID` is the single facet the adapter ships. The capture's other
  facets and its `publisher_name` facet are dropped; the drop list is
  computed from the capture actually replayed, so a capture shipping only
  `ec_category` reports no drops rather than a fabricated list.

---

## 3. Typed result and issue structures

```python
@dataclass(frozen=True, slots=True)
class CoveoPageResponse:
    page_index: int
    first_result: int
    total_count: int | None             # None when the endpoint's totalCount is unusable
    records: tuple[Mapping[str, object], ...]
    request_metadata: Mapping[str, object]   # redacted; never headers or tokens
    issues: tuple[ValidationIssue, ...] = ()
    filtered_count: int | None = None
    forbidden_field_presence: tuple[Mapping[str, object], ...] = ()
    @property
    def is_structural_failure(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class CategoryDiscoveryResult:
    category: str
    discovery_status: DiscoveryStatus
    ordinal_start: int                  # first ordinal assigned in this category (0-based)
    ordinal_end: int                    # exclusive; equals observations_emitted
    observations_emitted: int           # rows handed to the sink, duplicates included
    canonical_identity_count: int       # distinct resolved keys; unresolved/conflict excluded
    unresolved_identity_count: int
    conflict_identity_count: int
    duplicate_observation_count: int
    pages_fetched: int
    total_count: int | None             # verified totalCount, else None
    api_reported_count: int | None      # API-returned count, else None
    filter_status: CategoryFilterValidationStatus
    conditions: tuple[DiscoveryStatus, ...]   # every applicable condition, severity-ordered
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class CoveoHttpResponse:
    request_url: str
    status: int
    headers: Mapping[str, str]
    body: bytes

@dataclass(frozen=True, slots=True)
class CategoryPageOutcome:          # what one written page contributed, as persisted
    ordinal_start: int
    ordinal_end: int
    identities: tuple[IdentityResolutionResult, ...]
    category_matches: tuple[CategoryMatchResult, ...]
    duplicates: int = 0

class CoveoDiscoveryError(RuntimeError): ...        # base
class CoveoRequestFailed(CoveoDiscoveryError): ...  # retries exhausted / permanent failure
class CoveoTaxonomyInvalid(CoveoDiscoveryError): ... # pre-network abort
```

`CategoryDiscoveryResult.conditions` keeps **every** applicable condition
visible even though exactly one is selected as `discovery_status`;
`select_terminal_status` and `order_conditions` expose the two pure selection
rules so both properties can be exercised directly. The severity precedence is
a **non-normative predecessor convention** carried from the retired
`SRS-revision2.md` §4.1 `REQ-EXT-095`, not a lean requirement.

`ordinal_end - ordinal_start` always equals `observations_emitted`, and the
durable row count for the category matches both.

---

## 4. Public functions

```python
def load_coveo_search_template(
    template_path: "Path | str" = COVEO_TEMPLATE_PATH) -> Mapping[str, object]: ...
def build_coveo_request_body(
    template: Mapping[str, object], category: str, *,
    page_index: int, page_size: int = PAGE_SIZE) -> dict[str, object]: ...
def build_coveo_headers(bearer_token: str) -> dict[str, str]: ...
def coveo_search_url(organization_id: str = COVEO_ORGANIZATION_ID) -> str: ...
def find_forbidden_query_field(value: object, *, path: str = "") -> str | None: ...
def reject_free_text_query_members(value: object) -> None: ...
def validate_discovery_taxonomy(
    taxonomy_payload: object, *, requested_categories: Sequence[str],
    reference_utc: datetime, max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS
) -> TaxonomyValidationResult: ...
def fetch_category_page(
    request_body: Mapping[str, object], *, headers: Mapping[str, str], url: str,
    transport: CoveoTransport, sleeper: Callable[[float], None],
    rate_limiter: CoveoRateLimiter | None = None,
    max_retries: int = COVEO_MAX_RETRIES,
    template: Mapping[str, object] | None = None) -> CoveoPageResponse: ...
def resolve_observation_identity(record: Mapping[str, object]) -> IdentityResolutionResult: ...
def select_terminal_status(conditions: Sequence[DiscoveryStatus]) -> DiscoveryStatus: ...
def order_conditions(conditions: Sequence[DiscoveryStatus]) -> tuple[DiscoveryStatus, ...]: ...
def discover_category(
    category: str, taxonomy_payload: object, *, config: NicheScoutConfig,
    credentials: Credentials, reference_utc: datetime, sink: CoveoObservationSink,
    transport: CoveoTransport, sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = ..., run_id: str,
    template_path: "Path | str" = COVEO_TEMPLATE_PATH,
    rate_limiter: CoveoRateLimiter | None = None,
    shared_limiter: CoveoRateLimiter | None = None) -> CategoryDiscoveryResult: ...
```

The injection seams are protocols, so every analytical test injects a
recording fake and **no analytical test performs network I/O**:

```python
class CoveoTransport(Protocol):     # canonical spelling
    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any: ...
class CoveoOpener(Protocol):        # retained alias for the same seam
    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any: ...
class CoveoUrlOpener:               # production implementation (urllib.request)
    def __init__(self, *, timeout_seconds: float = 30.0) -> None: ...
class CoveoRateLimiter:
    def __init__(self, sleeper: Callable[[float], None]) -> None: ...
    @property
    def issued(self) -> int: ...
    def count_issued(self) -> None: ...
```

`send` returns an object exposing `status`, `headers`, and `read()`. The
adapter also accepts a legacy `open(request)`-shaped opener for compatibility;
`CoveoTransport.send` is the canonical contract.

---

## 5. The streaming persistence seam (`LREQ-NFR-010`)

```python
class CoveoObservationSink:
    def __init__(self, repository: SqliteRepository, run_id: str, category: str, *,
                 clock: Callable[[], datetime] | None = None,
                 taxonomy: object = None, batch_size: int = 500) -> None: ...
    @property
    def repository(self) -> SqliteRepository: ...
    @property
    def run_id(self) -> str: ...
    @property
    def category(self) -> str: ...
    @property
    def batch_size(self) -> int: ...
    def write_page(self, page: CoveoPageResponse, *, ordinal_start: int,
                   taxonomy_paths: Container[str],
                   seen_identities: MutableMapping[str, str],
                   limit: int | None = None) -> CategoryPageOutcome: ...
    def write(self, page_observations: Sequence[RawDiscoveryObservationRecord]) -> None: ...
```

- The sink is constructed by the caller with `(repository, run_id, category)`.
  `discover_category` opens **one** `category_transaction(run_id, category)`
  for the whole category and calls the sink once per page, inside that block.
- The sink persists one page's records through
  `repository.insert_raw_discovery_observations(page_observations)` — the
  frozen Chunk 2 **page sink** (`interfaces/chunk-02.md` §3). It is **not**
  `append_raw_discovery_observations`, and the adapter never opens a
  transaction of its own. Calling `write` outside an active
  `category_transaction` raises `RepositoryError` (Chunk 2's precondition).
- Page *n+1* is only requested once page *n* is persisted. The traversal keeps
  the per-page *outcome* only, never a page's records, so only one page is ever
  in memory and a category's complete result set is never materialized.
- `discover_category` requires the sink to expose `.repository` so it can open
  the transaction the page sink requires; a sink without it raises `ValueError`.

---

## 6. Behavioral contracts downstream chunks may rely on

- **Order of operations.** Taxonomy validation and credential validation both
  complete **before** the first request; the template capture is
  hash-verified; the category transaction is opened once for the whole
  category; the terminal status is persisted with `set_category_status` after
  the observations are committed. A credential carrying its own `Bearer `
  scheme prefix is normalized before re-prefixing, so `"Bearer eyJ…"` yields
  `Authorization: Bearer eyJ…`.
- **Request construction.** The captured template is replayed verbatim for
  `locale`, `tab`, `referrer`, `timezone`, `context`, `dictionaryFieldContext`,
  `searchHub`, `sortCriteria`, `numberOfResults`, and `facetOptions`. Exactly
  four mechanical edits are applied: `actionsHistory` is emptied, `analytics`
  is dropped, `firstResult = page_index * page_size` (capture-confirmed
  offset convention; `page_index` is zero-based), and `visitorId` is replaced
  by the fixed `COVEO_VISITOR_ID_PLACEHOLDER`. The capture's `facets` block is
  replaced by the single `ec_category` facet with the target category marked
  `"selected"` and every other captured value `"idle"`.
  `fieldsToInclude` is forced to the five-field set — the **single deliberate**
  divergence from "replayed as captured", required by LREQ-EXT-040 and not a
  defect. A body containing `q` or `query` at any depth raises `ValueError`
  (LREQ-EXT-030).
- **Pagination.** One request per page; the read cap
  (`max_discovery_results_per_category`) is enforced against the running
  persisted count, and the requested page size is always the full `page_size`
  (never a remainder). Truncation, request failure, and page failure are
  recorded conditions.
- **Failures are never zero assets.** A failed request or a structurally failed
  page yields no records, is recorded as `request_failed` / `page_failed`, and
  is never read as a zero-breadth category. A zero-result category is
  `complete` only when the response structure validated and the filter verdict
  is `verified`.
- **Retry/backoff.** Transient `429` and `5xx` are retried up to
  `COVEO_MAX_RETRIES` additional attempts with exponential backoff from
  `COVEO_BACKOFF_BASE_SECONDS`, honoring a numeric `Retry-After`. A permanent
  failure (any other non-200 status) is raised immediately and never retried.
  The minimum request interval is applied once per logical page request,
  through the injected `sleeper`; the first request of a run is not delayed.
- **Ordinals and duplicates.** `discovery_ordinal` is assigned once per
  emitted record (monotonic, zero-based, per run and category, in emission
  order). When a record whose canonicalized identity was already seen earlier
  in the same run and category arrives again, it is persisted as its own row
  with `is_duplicate=True` and `duplicate_of_observation_id` pointing at the
  first row — never overwritten, renumbered, or dropped.
- **Discovery-time field population.** Every raw observation carries: all
  non-empty identity candidates (`identity_candidates_json`), the nullable
  canonical identity (`asset_identity_key`, non-null only for `resolved`), the
  identity-resolution status and reason, the response `ec_category` verbatim,
  the category-filter status, a **nullable** `stratum_index` (`None` during
  discovery), the duplicate linkage, redacted request metadata, and a redacted
  `error_summary_json`. No value is fabricated for a missing field.
- **Per-category failure isolation.** A per-category request or page failure
  ends only that category and is returned as a `CategoryDiscoveryResult`
  carrying a failure status and a populated redacted error summary; it never
  propagates and never aborts another category. The failed category's
  already-committed rows and status are untouched.
- **Redaction.** `request_metadata_json`, `error_summary_json`, logs, and
  exception messages never contain a bearer token, CSRF token, cookie,
  `Authorization` header value, or raw response body.
- **Traceability.** Every analytical test in `tests/test_collector.py` carries
  a `@pytest.mark.lreq` marker and a `tests/traceability.json` entry.
  `test_module_imports_without_side_effects` and
  `test_request_body_builder_signature_is_stable` are the two non-analytical
  tests exempted by plan §9.

---

## 7. What downstream chunks must NOT expect from Chunk 3

- **No post-discovery canonicalization update.** Chunk 3 persists the
  discovery-time record only, with `asset_identity_key` nullable and
  `stratum_index` always `None`. It does **not** call
  `update_raw_discovery_identity`, does not link duplicates across
  canonicalization, and does not assign strata. Those are Chunks 4A/4B.
- **No canonical population or sample construction** — Chunk 4A. Chunk 3
  assigns and persists `discovery_ordinal` and records duplicates; it builds
  neither a population nor a sample, and never calls
  `insert_sample_members`/`upsert_sample_members`.
- **No warning emission, rankability assignment, or score computation** —
  Chunk 10 completes `LREQ-EXT-090`; Chunk 12 renders the warning. Chunk 3
  detects the condition, persists it as a `DiscoveryStatus`, and exposes the
  condition set on `CategoryDiscoveryResult.conditions`; it emits no
  `WarningCode` and claims no end-to-end `LREQ-EXT-090`. LREQ-EXT-060/EXT-080
  are **not** satisfied by the Chunk 1 primitive contracts alone.
- **No metric eligibility semantics** — Chunks 7A/7B.
- **No GraphQL enrichment, correlation, or operation-level status** —
  Chunk 5 (`collector_graphql.py`), untouched by this chunk.
- **No identity-preflight planning/gating or unique enrichment/reuse** —
  Chunks 6A/6B.
- **No `runs.taxonomy_sha256` computation or rewriting.** The placeholder
  value is propagated verbatim; the finding that no chunk owns that gap (and
  that Chunk 10 does) is recorded in the plan's §12.11 and the dependency
  map's open items.
- **No report/CLI behavior, exit codes, run-level status transitions, or
  run-wide orchestration** — Chunks 10/12.
- **No traceability-validator widening** — Chunk 13 (`LREQ-NFR-060`).

---

## 8. Adapter-internal behavior explicitly NOT part of this contract

The section records the *implementation shape* of the adapter's identity step.
The requirement-level outcome it produces is the frozen one —
`LREQ-EXT-070`'s three-way `resolved`/`conflict`/`unresolved` plus the
`mapping_rule_version` stamp are guaranteed; the internal `endswith`-era
"contribute nothing" tolerance once described here is **removed** as of mapping
rule `1.0.1` and SHALL NOT be relied on.

`resolve_observation_identity` delegates to
`validation.resolve_canonical_identity` and adopts its verdict whenever that
primitive already yields a canonical key. Only when the primitive returns
`unresolved` does the adapter add a cross-field agreement step: every retained
candidate is read under its own field's mapping rule and every derived key must
**equal** every other derived key — explicit `ec_product_id`/`permanentid`
candidates must agree with each other (two distinct values **are** a conflict),
and a URI-derived candidate — the trailing `-<digits>` identifier of
`clickUri`/`uri` — is a **peer** candidate source that agrees only on equality
after canonicalization. A URI identifier that does not equal the explicit anchor
is a `conflict`, exactly as two disagreeing explicit ids are. Equality is
evaluated on the mapping rule's normalized comparison form, so `"0081"` and
`"81"` are one identity.

**Rule `1.0.1` correction.** Under rule `1.0.0` this step accepted a URI-derived
identifier whenever it was a *suffix* of the explicit anchor
(`anchor.endswith(key)`, e.g. `product-0001` for `.../fixture-1-0001`), and
otherwise contributed nothing. That tolerance had no basis in normative text and
it **rescued genuine `LREQ-EXT-070` disagreements into `resolved`**, so
`1.0.1` — the value `interfaces/chunk-01.md` §4.1 line 231 already reserved for
this correction — removes it. `"1.0.1"` is not a *loosening* of a sample size;
it is a correction whose effect is strictly more `conflict` verdicts, because a
URI-derived identifier now has to match the explicit id exactly.

The one part of the earlier policy that **is** backed by normative text and is
unchanged: a URI-shaped value that does not fit the trailing-identifier pattern
contributes **nothing** and can never vote —
`interfaces/chunk-01.md` §4.1 ("A value that does not fit that pattern
contributes nothing").

Two consequences consumers must not treat as frozen:

- **The URI trailing-identifier rule itself is inferred, not capture-verified.**
  `interfaces/chunk-01.md` §4.1 already flags this (the extraction half of the
  rule is inferred; `"1.0.1"` is reserved for a correction). The capture this
  chunk replays is a **request** capture, not a response capture, so it does not
  settle the rule either, and `1.0.1` deliberately left extraction untouched.
  Consumers SHALL branch on
  `IdentityResolutionResult.mapping_rule_version` rather than assuming `1.0.0`
  or `1.0.1` semantics silently.
- **The adapter's cross-field agreement step is still adapter policy, not a
  Chunk 1 primitive guarantee.** It exists because
  `validation.resolve_canonical_identity` compares the four fields'
  canonicalized values as plain strings and therefore reads an ordinary
  `product-0001` / `permanent-0001` pair as a `conflict`. The step is
  implemented and tested, but downstream chunks SHALL NOT rely on its
  *existence* as a certified invariant: they rely on the requirement-level
  outcome (`LREQ-EXT-070`'s three-way `resolved`/`conflict`/`unresolved` plus the
  `mapping_rule_version` stamp).
