# Chunk 23 — Coveo transport-retry and persisted discovery failure cause (labeled post-completion remediation)

Status: **FROZEN** (2026-09-28). All seven prior open questions were answered by the
operator on 2026-09-28 (recorded in `Documents/runs/chunk-23.md`); their resolutions are
recorded as R-A1…R-A7 in §12 and are adopted, not recommended. The authorized frozen-surface
changes are named in §5 and have been applied to `Documents/interfaces/chunk-02.md` and
`Documents/interfaces/chunk-03.md`; `Documents/interfaces/chunk-10.md` is **not** changed
(after the Q3/Q4 answers the plan no longer consumes a new surface from it).

Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-03.md` §2 (constants), §3 (`CategoryDiscoveryResult`,
    `CoveoRequestFailed` + its two new attributes, `CoveoTransportFailureClass`),
    §4 (`fetch_category_page` and `discover_category` signatures, both **unchanged**),
    §6 ("Retry/backoff" with the transport-retry correction, "Per-category failure
    isolation", "Redaction", the durable-cause note) — consumed and amended as recorded
    in §5; the §4 signatures are unchanged.
  - `Documents/interfaces/chunk-02.md` §2.1 (`SCHEMA_VERSION = "1.1.0"`),
    §2.4 (the one authorized column), §2.7 (`set_category_status` with the additive
    `discovery_failure_cause_json` parameter), §2.9 (`*_json` codec), §3 ("No schema
    invention" with the Chunk 23 exception) — consumed and amended as recorded in §5.
  - `Documents/interfaces/chunk-10.md` §4 (`PipelineResult.limitations`), §5
    (`category_status_for`) — consumed unchanged; no new surface consumed and no edit.
  - `Documents/plans/chunk-15-failure-path-limitations-and-logging.md` §12 (carried-forward
    obligation: "Discovery-page failure has no persisted cause ... Owner: none") and
    `Documents/plans/chunk-16-coveo-discovery-record-shape.md` §6 (same class of
    `collector_coveo.py` remediation shape). R2 discharges the chunk-15 obligation for the
    persisted-cause half; the chunk-15 limitation-string behavior is untouched.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  - None. Labeled post-completion remediation (Chunks 14–22 pattern): no
    `requirements-dependency-map.md` §3/§4 gate row, no new interface file, no downstream
    chunk.

## 1. Goal

Two defects on the Coveo discovery failure path, each one small diff:

- **R1.** A transient transport-layer failure — a connection error or socket timeout,
  surfaced by `urllib.request` as `urllib.error.URLError` / `OSError` — currently aborts
  the whole category immediately (`collector_coveo.py:976-980`). It SHALL instead be
  treated as transient and retried under the **existing** bounded exponential-backoff
  policy (`COVEO_MAX_RETRIES`, `COVEO_BACKOFF_BASE_SECONDS`), exactly as a `429`/`5xx`
  response is; permanent failures (auth/CSRF/malformed/authorization) stay non-retrying.
  Cite `LREQ-EXT-100`.
- **R2.** When a category's discovery fails, the cause is collected as
  `ValidationIssue`s in `parent_issues` and then discarded: `_finalize_result` persists
  only the terminal `discovery_status` (`collector_coveo.py:2260-2275`), so
  `DISCOVERY_PAGE_FAILED` is diagnosable only from transient terminal output. The
  category-level failure cause SHALL be persisted in the database in redacted form
  (failure class, HTTP status when available, page index, attempt count). Every persisted
  value SHALL obey `LREQ-SEC-020`. Cite `LREQ-EXT-090`, `LREQ-NFR-030`, `LREQ-NFR-020`,
  `LREQ-RPT-020`, `LREQ-SEC-010/020`.

The two concerns stay separate: R1 changes retry behavior in the fetch loop; R2 changes
what is persisted after the traversal. They touch one shared file
(`collector_coveo.py`) but no shared lines, and R1 can land without R2.

## 2. Scope

### In scope

- **R1 — transient transport retry.** In `fetch_category_page`'s attempt loop, the
  `except (urllib.error.URLError, OSError)` arm (currently a bare
  `raise CoveoRequestFailed(...)`) becomes a retryable classification that consumes the
  same retry budget and the same backoff schedule as the transient-status arm. Bounded:
  at most `max_retries` additional attempts, then the existing terminal
  `CoveoRequestFailed`, now carrying `attempts: int` and
  `failure_class: CoveoTransportFailureClass` (`CoveoTransportFailureClass.TRANSPORT_FAILURE`).
  The message is extended only with the failure-class token and the attempt count; never
  `str(exc)`. `fetch_category_page`'s signature is **unchanged**. (`LREQ-EXT-100`)
- **R2 — persisted, redacted failure cause.** `_finalize_result` writes the category-level
  discovery failure cause, derived from the redacted `ValidationIssue` `code`/`context`
  scalars, to the new nullable `category_scores.discovery_failure_cause_json` column
  through the additive keyword-only `discovery_failure_cause_json` parameter on
  `set_category_status`. The value is canonical JSON text
  (`json.dumps(..., sort_keys=True, separators=(",", ":"))`) carrying exactly
  `failure_class` (`transport_failure` / `http_transient` / `http_permanent`),
  `http_status` (`int` or `null`), `page_index` (`int`), and `attempt_count` (`int`).
  (`LREQ-EXT-090`, `LREQ-NFR-030`, `LREQ-NFR-020`, `LREQ-RPT-020`, `LREQ-SEC-010/020`)

### Frozen surfaces changed (operator-authorized 2026-09-28; see §5/§12)

- `interfaces/chunk-03.md` §3: `CoveoRequestFailed` gains `attempts: int` and
  `failure_class: CoveoTransportFailureClass`; new Coveo-local enum
  `CoveoTransportFailureClass` (`transport_failure` / `http_transient` / `http_permanent`).
  `fetch_category_page` / `discover_category` signatures unchanged.
- `interfaces/chunk-02.md` §2.1: `SCHEMA_VERSION` `"1.0.0"` → `"1.1.0"`; `category_scores`
  gains one nullable column `discovery_failure_cause_json TEXT`.
- `interfaces/chunk-02.md` §2.7: `set_category_status` gains the additive keyword-only
  `discovery_failure_cause_json: Optional[str] = None`; the default leaves the stored
  value unchanged so the scoring-phase `upsert_category_scores` cannot null it.
- `src/niche_scout/models.py`: `CategoryScoreRecord` gains
  `discovery_failure_cause_json: str | None`, so
  `MANDATORY_ROW_FIELDS["category_scores"] == TABLE_COLUMNS["category_scores"]` holds.

### Explicitly out of scope (and who owns it instead)

- **Sampling constants and `SAMPLING_RULE_VERSION`** — chunk 24. Untouched here.
- **The open obligations in `AGENTS.md`** — URI trailing-identifier extraction (identity
  mapping rule 1.0.1), OI-6 (CSRF/session sufficiency), `runs.taxonomy_sha256` empty-hash
  rejection (owner Chunk 10). None is resolved, absorbed, or claimed verified here.
- **`collector_graphql.py`** — its retry path (`GraphQLFailureClass.TRANSPORT_FAILURE`,
  `is_retryable`, `retry_delay_seconds`) is the *precedent* R1 follows, not a surface this
  chunk edits. Owner: Chunk 5.
- **`report.py` and `LREQ-RPT-020` rendering.** Q3 = DB-only. `report.py` is not touched;
  `LREQ-RPT-020`'s primary-table field list is fixed and the cause is **not** rendered in
  this chunk. The persisted column is the durable evidence behind the displayed
  `discovery_status`. Owner of any future rendering: Chunk 11.
- **`Documents/interfaces/chunk-10.md`.** Not changed and no new surface consumed from it;
  `PipelineResult.limitations` and `category_status_for` are consumed unchanged. (Q3/Q4
  answers leave the pipeline only passing values through, which is below the frozen
  interface's level of description.)
- **The failure-path limitation strings and their format** (`category <repr>: <field>`,
  `interfaces/chunk-10.md` §4/§6). Unchanged. Owner: Chunk 15.
- **A `category_status` column.** `interfaces/chunk-02.md` §4: "No `category_status`
  column ... it is carried by the existing `category_scores.discovery_status`,
  `warnings_json`, `evidence_grade`, and `rankability_status`". R2's cause is a *cause*,
  not a status; it must not become a status enum.
- **New CLI flags, environment variables, or dependencies.** None may be invented.
- **Live network.** No live request is made in development or tests.

## 3. Requirements this chunk must satisfy

Chunk 23 is a labeled post-completion remediation and has **no
`requirements-dependency-map.md` §3 section**. Normative text below is quoted/derived from
`SRS-lean.md` at the cited lines.

| LREQ ID | Ownership role here | Normative text (from `SRS-lean.md`, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EXT-100 | **Primary** (R1) | "Requests SHALL be rate-limited and retry transient `429` and `5xx` responses with exponential backoff. Permanent authentication, CSRF, malformed request, or authorization failures SHALL not be retried indefinitely." The operator ruling (2026-09-28) extends "transient" to a transport-layer connection error / socket timeout, retried under the existing policy; permanence and the bound are unchanged. | §4.1 (lines 283–285) |
| LREQ-EXT-090 | **Primary** (R2) | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." The warning already exists (`DISCOVERY_PAGE_FAILED`, Appendix C line 1471); R2 makes its **cause** durable so the warning is diagnosable from the DB. | §4.1 (lines 279–281) |
| LREQ-NFR-030 | **Primary** (R2) | "A failed page or sampled asset SHALL not abort unrelated categories or assets; the failure SHALL remain visible in status and evidence fields." R2 adds a persisted field on which the failure remains visible without terminal output. | §11 (lines 1168–1169) |
| LREQ-NFR-020 | **Supporting** (R2) | "Before bulk enrichment, log discovered canonical assets, sampled assets, unique enrichment identities, and projected minimum enrichment time." Not re-implemented; the persisted cause must not be confused with, or emitted through, the projection line (no new log line is added by R2). | §11 (lines 1165–1166) |
| LREQ-RPT-020 | **Supporting** (R2) | "The primary table SHALL show ... discovery status, ..." The persisted cause is the durable evidence behind the displayed `discovery_status`; it is persisted by this chunk and **not rendered** (Q3 = DB-only). | §10 (lines 1113–1119) |
| LREQ-SEC-010 | **Supporting redaction** (R1/R2) | "Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection." No credential value may reach the persisted cause or an exception message. | §4.3 (lines 348–349) |
| LREQ-SEC-020 | **Supporting redaction** (R1/R2) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern SHALL be ignored by version control." Binds every value persisted by R2 and every token in R1's terminal message. | §4.3 (lines 351–352) |

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source):

- `interfaces/chunk-03.md` §4: `fetch_category_page(request_body, *, headers, url,
  transport, sleeper, rate_limiter=None, max_retries=COVEO_MAX_RETRIES, template=None) ->
  CoveoPageResponse`; `discover_category(category, taxonomy_payload, *, config,
  credentials, reference_utc, sink, transport, sleeper=time.sleep, clock=..., run_id,
  template_path=COVEO_TEMPLATE_PATH, rate_limiter=None, shared_limiter=None) ->
  CategoryDiscoveryResult`.
- `interfaces/chunk-03.md` §2: `COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0`,
  `COVEO_BACKOFF_BASE_SECONDS = 2.0`, `COVEO_MAX_RETRIES = 5`.
- `interfaces/chunk-03.md` §3: `CategoryDiscoveryResult` (incl. `issues:
  tuple[ValidationIssue, ...]`, `pages_fetched: int`); `CoveoRequestFailed`.
- `interfaces/chunk-03.md` §6 "Retry/backoff": "Transient `429` and `5xx` are retried up
  to `COVEO_MAX_RETRIES` additional attempts with exponential backoff from
  `COVEO_BACKOFF_BASE_SECONDS`, honoring a numeric `Retry-After`. A permanent failure
  (any other non-200 status) is raised immediately and never retried." §6 "Per-category
  failure isolation" and §6 "Redaction" bind R1/R2.
- `interfaces/chunk-02.md` §2.4: "Raises `SchemaVersionError` when the stored version
  differs from `SCHEMA_VERSION`; it never migrates silently and never deletes data. ...
  **No `ALTER TABLE`, no column addition, no destructive migration.**" §3: "**No schema
  invention** — no new table (other than the private `schema_metadata`), no new column,
  no `ALTER TABLE`, no index beyond the frozen one."
- `interfaces/chunk-02.md` §2.7: `set_category_status(run_id, category, discovery_status,
  *, computed_at_utc=None)` upserts `category_scores` and "creates the row on first write
  if it does not exist yet".
- `interfaces/chunk-02.md` §2.9: `*_json` columns are stored exactly as given.
- `interfaces/chunk-10.md` §5: `category_status_for(discovery_status, *, warnings,
  evidence_grade, rankability_status) -> CategoryStatus`; roll-up reads only
  `discovery_status`.

**Frozen surfaces amended by this chunk (recorded 2026-09-28; see §5 and §12).**

- `interfaces/chunk-03.md` §3: `CoveoRequestFailed` gains read-only `attempts: int` and
  `failure_class: CoveoTransportFailureClass`; new Coveo-local
  `class CoveoTransportFailureClass(str, Enum)` with exactly `transport_failure`,
  `http_transient`, `http_permanent`. `GraphQLFailureClass` is **not** imported.
- `interfaces/chunk-03.md` §6 "Retry/backoff": the transport-retry correction.
- `interfaces/chunk-03.md` §6: the durable-cause note.
- `interfaces/chunk-02.md` §2.1: `SCHEMA_VERSION = "1.1.0"`;
  `category_scores.discovery_failure_cause_json` (nullable `TEXT`).
- `interfaces/chunk-02.md` §2.4 and §3: the single authorized column-addition exception.
- `interfaces/chunk-02.md` §2.7: `set_category_status(..., *,
  discovery_failure_cause_json: Optional[str] = None)`.
- `src/niche_scout/models.py`: `CategoryScoreRecord.discovery_failure_cause_json:
  str | None` appended last (so `MANDATORY_ROW_FIELDS` parity holds).

**Signature-freeze facts (verified by reading this session).**

- `src/niche_scout/collector_coveo.py:976-980`: the transport arm raises
  `CoveoRequestFailed` immediately — `f"the Coveo discovery request failed at the
  transport layer ({exc.__class__.__name__}) for page {first_result}"`. Only
  `exc.__class__.__name__` is interpolated (no `str(exc)`).
- `collector_coveo.py:952-999`: the attempt loop is `while attempts <= max_retries`,
  `attempts += 1` before the request; transient statuses arm
  `delay = COVEO_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))`, `Retry-After` honored via
  `max(delay, retry_after)`, and `if attempts > max_retries: break` yields the terminal
  `CoveoRequestFailed` at `:1006-1010`. A transport exception currently bypasses this
  entirely.
- `collector_coveo.py:1956-1967` (`_discover_category_in_transaction`): a
  `CoveoRequestFailed` is caught, `DiscoveryStatus.REQUEST_FAILED` is appended, and one
  `_issue("coveo_request_failed", str(exc), category=..., page_index=...)` is appended to
  `parent_issues`. **`str(exc)` currently enters a `ValidationIssue.message`**, whose
  redaction is only `redact_value` on `context` values (`_issue`, `:871-876`) — the
  message itself is not re-redacted.
- `collector_coveo.py:2260-2275` (`_finalize_result`): `issues = tuple(parent_issues) +
  tuple(counters.issues)`, then `repository.set_category_status(run_id, category,
  status.value, computed_at_utc=ensure_utc(computed_at_utc))` — **the issues are
  returned in the result and are not persisted anywhere.**
- `database.py:178-230`: `CREATE TABLE category_scores` has **no** error/summary column;
  `error_summary_json` exists only on `raw_discovery_observations` (`database.py:126`) and
  `product_detail_error_summary`/`page_views_error_summary` only on
  `enrichment_observations` (`database.py:169-170`).
- `database.py:54`: `SCHEMA_VERSION = "1.0.0"`; `database.py:938-968`
  `initialize_schema` raises `SchemaVersionError` on a stored-version mismatch and applies
  only `CREATE ... IF NOT EXISTS`.
- `tests/test_collector.py`: the harness is `discover(repo, opener, *, ...)` over a real
  file-backed `SqliteRepository`; `RecordingOpener.open(request)` records requests;
  `RecordedResponse(status, body, headers)`; `Recorder()` records sleeper calls. There is
  **no** transport object exposing `send()` and **no** transport that raises in the
  harness today — R1 needs one (a small inline test-local transport, as Chunk 15 did with
  `_ExplodingCoveoTransport`).
- `tests/test_collector.py:1062-1127`: the two existing `LREQ-EXT-100` nodes pin
  `backoffs == [7.0, 4.0, 8.0]` (429/503/500) and `[2.0, 4.0, 8.0, 16.0, 32.0]`
  (exhausted 503s). R1's new backoff values must follow the same
  `2.0 * 2 ** (attempts - 1)` schedule.
- `tests/traceability.json` is committed **node-ID → array of LREQ IDs** (lines 1-5 and
  throughout), e.g. `"tests/test_collector.py::test_transient_429_and_5xx_are_retried_with_backoff_and_retry_after": ["LREQ-EXT-100"]`.
  `tests/AGENTS.md` lines 5–13 describe the opposite orientation and are **stale**; the
  committed file and `validate_traceability.py` govern (chunk-15 plan §4).

## 5. Interface contract this chunk produces

**None.** No `Documents/interfaces/chunk-23.md` is created; no downstream chunk consumes a
new surface. The frozen interfaces named in §4 are **amended in place** (operator-authorized
2026-09-28; the edits are already applied to `interfaces/chunk-02.md` and
`interfaces/chunk-03.md`), and the plan records them as the operative contract:

1. **R1** extends the transient class of `fetch_category_page` to transport-layer
   `URLError`/`OSError` under the existing bounded backoff, and adds two read-only
   attributes to `CoveoRequestFailed` plus a Coveo-local failure-class enum
   (`interfaces/chunk-03.md` §3/§6). The `fetch_category_page` and `discover_category`
   signatures are **unchanged** (Q1 = (b)).
2. **R2** persists the category-level discovery failure cause in one new nullable
   `category_scores` column, `discovery_failure_cause_json`, with a `SCHEMA_VERSION` bump
   `"1.0.0"` → `"1.1.0"`, and an additive keyword-only parameter on `set_category_status`
   (`interfaces/chunk-02.md` §2.1/§2.4/§2.7/§3). `models.CategoryScoreRecord` gains the
   matching field. `interfaces/chunk-10.md` is **not** changed and no new surface is
   consumed from it.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_coveo.py` | modified | R1: retry `URLError`/`OSError` under the existing backoff budget in `fetch_category_page`; add `CoveoTransportFailureClass` and the two `CoveoRequestFailed` attributes. R2: derive the redacted, canonical-JSON cause from the `ValidationIssue` `code`/`context` scalars and pass it to `set_category_status` from `_finalize_result`. |
| `src/niche_scout/database.py` | modified | R2: `SCHEMA_VERSION = "1.1.0"`; `discovery_failure_cause_json TEXT` on `category_scores`; the `set_category_status` parameter and its default-leaves-stored-value-unchanged conflict behavior. |
| `src/niche_scout/models.py` | modified | R2: `CategoryScoreRecord.discovery_failure_cause_json: str | None` appended last, so `MANDATORY_ROW_FIELDS["category_scores"] == TABLE_COLUMNS["category_scores"]`. |
| `src/niche_scout/pipeline.py` | modified (minimal) | R2: pass a cause through only where the pipeline itself writes `set_category_status` (the `_discover_all` except arm at `:2935-2940`); the scoring-phase `upsert_category_scores` must not null an already-written cause. No new interface; no new log line; no limitation-string change. |
| `tests/test_collector.py` | modified | R1 nodes and R2 nodes (§9). |
| `tests/test_database.py` | modified | R2 round-trip and column-parity nodes (§9). |
| `tests/test_contracts.py` | modified (parity only) | The `TABLE_COLUMNS == MANDATORY_ROW_FIELDS` / column-set assertions gain the new column; `SCHEMA_VERSION` pin updated to `"1.1.0"` if one exists. Read the file before editing; report rather than silently rewrite any assertion that contradicts the plan. |
| `tests/traceability.json` | modified | New node → LREQ-array entries (§9). |
| `Documents/interfaces/chunk-02.md` | modified (authorized) | §2.1/§2.4/§2.7/§3/§5 Chunk 23 amendments. |
| `Documents/interfaces/chunk-03.md` | modified (authorized) | §3/§6 Chunk 23 amendments. |
| `Documents/runs/chunk-23.md` | new (lead) | Run log and the seven rulings. |

**Not touched:** `collector_graphql.py`, `report.py`, `cli.py`, `metrics.py`, `scoring.py`,
`validation.py`, `sampling.py`, `config.py`, `collector.py`, `src/niche_scout/tools/**`,
`pyproject.toml`, `config/**`, `tests/fixtures/**` (only if a real assertion requires it —
otherwise byte-identical), `Documents/SRS-lean.md`,
`Documents/requirements-dependency-map.md`, `AGENTS.md`, `kilo.json(c)`, `.kilo/`, and every
other `Documents/interfaces/*` file.

## 7. Design decision points and proposed edits

Line anchors are the working-tree state read this session; they are anchors, not contents.
All seven decision points below were resolved by the operator (2026-09-28); the answers are
recorded in §12 as R-A1…R-A7 and the proposed edits reflect them.

### R1 — retry transient transport failures (Q1 = (b))

**DP1. Where the transport classification lives.** The `except (urllib.error.URLError,
OSError) as exc` arm at `collector_coveo.py:976-980` becomes retryable. A transport exception
produces no HTTP status, so the loop must not re-use `_classify_status(status)`; it arms the
same backoff schedule from the same constants and, when the budget is exhausted, falls
through to the terminal raise. Sketch:

```python
except (urllib.error.URLError, OSError) as exc:
    last_status = None
    last_failure_class = CoveoTransportFailureClass.TRANSPORT_FAILURE
    if attempts > max_retries:
        break
    pending_delay = COVEO_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))
    continue
```

- `str(exc)` is **never** interpolated. Only `exc.__class__.__name__` (as today) or a fixed
  class token.
- The bound is unchanged: `attempts` is incremented once per issued request and the loop
  condition is `attempts <= max_retries`, so at most `max_retries` retries follow the first
  attempt. No infinite retry.
- `Retry-After` cannot apply (no response), so the backoff is exactly
  `COVEO_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1)` — the same schedule the transient
  status path uses when `Retry-After` is absent.
- The terminal message is extended only with the attempt count and the failure-class
  token, e.g. `f"the Coveo discovery request for page {first_result} failed after
  {attempts} attempt(s); retries are exhausted and it is not retried further
  (transport_failure)"`. It must not become a channel for `str(exc)`.

**DP1b. Status-failure class.** The transient-status path must also tag its terminal
`failure_class`: an exhausted `429`/`5xx` is `HTTP_TRANSIENT`; an immediate non-retryable
status is `HTTP_PERMANENT`. Both carry `attempts` (the number actually issued, `>= 1`).

**DP2 (Q1 = (b)). Attempt count reaches the caller.**
`class CoveoRequestFailed(CoveoDiscoveryError)` gains `attempts: int` and
`failure_class: CoveoTransportFailureClass`. Both are set at **every** raise site in
`fetch_category_page` — the three paths are: transport-budget exhausted, transient-budget
exhausted, and the immediate permanent status. `_discover_category_in_transaction`'s
`except CoveoRequestFailed as exc` (`:1956`) reads `exc.attempts` and `exc.failure_class`
from the exception; `fetch_category_page`'s signature is unchanged. The enum is Coveo-local:

```python
class CoveoTransportFailureClass(str, Enum):
    TRANSPORT_FAILURE = "transport_failure"
    HTTP_TRANSIENT = "http_transient"
    HTTP_PERMANENT = "http_permanent"
```

`GraphQLFailureClass` is **not** imported and no GraphQL name is referenced.

### R2 — persist the category-level failure cause (Q2 = (a), Q4 = adapt `set_category_status`, Q5/Q6/Q7 = fixed shapes)

**DP4 (Q4 = extend `set_category_status`; adapter is the writer).** `_finalize_result`
(`collector_coveo.py:2260-2275`) already calls `set_category_status` inside the category
transaction; it is extended to pass a cause. `set_category_status` gains the additive
keyword-only `discovery_failure_cause_json: Optional[str] = None`:

- `None` (the default, and the only value `upsert_category_scores` ever sees) → the stored
  column is **left unchanged** on the conflict path, so a later scoring-phase finalize
  cannot null a cause written during discovery.
- A string → validated as canonical JSON text and written on insert and on conflict; the
  `*_json` codec stores it exactly as given (`interfaces/chunk-02.md` §2.9).

**DP5/DP6 (Q2 = (a), Q6 = fixed name/shape).** `category_scores` gains exactly one
nullable column, appended last so the column-order parity assertion holds:

- Column: `discovery_failure_cause_json TEXT` (nullable).
- Canonical value: `json.dumps(payload, sort_keys=True, separators=(",", ":"))` where
  `payload = {"failure_class": <str>, "http_status": <int | None>, "page_index": <int>,
  "attempt_count": <int>}`.
- `failure_class ∈ {"transport_failure", "http_transient", "http_permanent"}` (Q5).
- `SCHEMA_VERSION` `"1.0.0"` → `"1.1.0"`; `models.CategoryScoreRecord` gains
  `discovery_failure_cause_json: str | None`.

**DP5b (Q7 = `null`).** A pure transport failure has no HTTP status: `http_status` is
persisted as JSON `null` (and the row is non-null), never `0`.

**DP5c. Deriving the cause from the issues (redaction).** `_finalize_result` builds the
cause from `parent_issues`/`counters.issues` for the **first** page-failure issue, reading
only `issue.code` tokens and `issue.context` scalars (`page_index`). `issue.message` is
never read — it may contain `str(exc)` (`collector_coveo.py:1962`). Suggested mapping,
implemented in the adapter, no vocabulary is added outside Q5's three tokens:

| terminal discovery condition | `failure_class` | `http_status` | `page_index` | `attempt_count` |
|---|---|---|---|---|
| `REQUEST_FAILED` (Coveo) | from `CoveoRequestFailed.failure_class`; if absent/`None`, `http_permanent` | `null` for a transport failure; the exhausted status for a status failure | the failing `page_index` from the issue context | `CoveoRequestFailed.attempts`; else `pages_fetched` |
| `PAGE_FAILED` (structural 200) | `http_transient` is **wrong** here; use `http_permanent` only if the structural fault is a status-class fault, else `transport_failure` is **wrong** — see Q-R2open below | `null` | from the issue context | `pages_fetched` |
| unexpected adapter exception (pipeline `_discover_all`) | `transport_failure` | `null` | `0` | `1` |

**Residual ambiguity R-R1 (non-blocking, recorded not resolved).** The three Q5 tokens do
not cleanly describe a **structural 200** page failure (`PAGE_FAILED` from
`response_missing_required_member`): it is neither a transport failure nor an HTTP-status
failure. This plan therefore persists `failure_class = http_permanent` **only** when a real
non-transient status was observed, `transport_failure` when the terminal cause was a
transport exception, and `http_transient` when transient retries were exhausted; for a
structural 200 page failure it persists `http_permanent` **and** records the live ambiguity
in `Documents/runs/chunk-23.md` for the operator. The plan does not invent a fourth token.
This is a recorded limitation, not a blocker: the persisted row still names
`failure_class`/`http_status`/`page_index`/`attempt_count` and is diagnosable.

**DP6 (Q3 = DB-only).** No `report.py` change; the column is not rendered. `LREQ-RPT-020`
stays as the durable-evidence consumer.

**DP7 (redaction contract).** The persisted value carries only the four JSON members above.
It never carries `str(exc)`, a URL, an `Authorization`/cookie/CSRF value, or response-body
text. `interfaces/chunk-03.md` §6 "Redaction" binds it.

## 8. Edge cases and invariants

- **Bound.** `fetch_category_page` issues at most `max_retries + 1` requests regardless of
  failure kind (transient status, transport, or a mix). No unbounded retry.
- **Permanent stays permanent.** A non-transient HTTP status (any other non-200) is raised
  immediately and is never retried; `400`-class auth/CSRF/malformed failures are not
  retried.
- **Backoff schedule unchanged.** Transport retries use
  `COVEO_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1)`; the first transport retry after a
  successful first attempt sleeps `2.0`, then `4.0`, `8.0`, ... up to the budget.
- **Rate limiting unchanged.** One interval sleep per logical page request, through the
  injected `sleeper`; retries are spaced by backoff, not by the interval.
- **No new log line.** R2 persists to the DB; it adds no `niche_scout.pipeline` log line,
  so the chunk-15 `"enrichment"`-substring and sentinel constraints are untouched.
- **Missing is not zero.** `http_status` is persisted as JSON `null` when no HTTP status
  exists (a pure transport failure); it is never persisted as `0`. A category with no
  recorded cause has `NULL` in `discovery_failure_cause_json`, never `""` and never `"{}"`.
- **Default leaves the stored cause unchanged.** `set_category_status`'s
  `discovery_failure_cause_json=None` default must be a no-op on an existing non-null cause
  on the conflict path, so the scoring-phase `upsert_category_scores` cannot null it.
- **Attempts are `>= 1`.** `CoveoRequestFailed.attempts` is always the number actually
  issued for the page. A raise with `attempts == 0` is impossible.
- **Category isolation.** A category that exhausts its transport retries is `request_failed`
  for that category only; sibling categories are unaffected (`LREQ-NFR-030`).
- **Determinism.** The persisted cause depends only on the failure and the attempt count;
  no clock, RNG, or set/dict ordering; the JSON is canonical
  (`sort_keys=True, separators=(",", ":")`).
- **Structural-200 page failure precedence.** A structurally failed 200 page records
  `http_permanent` (no transport failure occurred and no status failed); see §7 DP5c and
  R-R1.

## 9. Test plan

No live network; repository-backed fixtures and injected fakes only. Every analytical test
carries `@pytest.mark.lreq(...)` and a `tests/traceability.json` entry (the committed file
is **node-ID-keyed**; each value is an array of LREQ IDs).

- **Files:** new nodes go in `tests/test_collector.py` (the Chunk 3 requirement home),
  `tests/test_database.py` (column round-trip), and `tests/test_contracts.py` (column and
  version parity). No new test module.
- **Fixtures:** R1 needs one inline test-local transport in `tests/test_collector.py`
  exposing `send(url, headers, payload)` and raising a scripted exception per attempt:

  ```python
  class _ScriptedTransport:
      """A transport that raises a scripted exception per send() call."""

      def __init__(self, script: Sequence[BaseException | int]) -> None: ...
      def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any: ...
  ```

  Attempts whose script entry is an `int` return a `RecordedResponse`-shaped object with
  that status; attempts whose entry is an exception raise it. `RecordingOpener` cannot be
  reused because it is `open(request)`-shaped and cannot raise `URLError`.
- **Proposed nodes and mapping** (R1 nodes and R2 nodes are both in scope now; R2 is no
  longer conditional):

| pytest node ID | `@pytest.mark.lreq(...)` marker args | `tests/traceability.json` value |
|---|---|---|
| `tests/test_collector.py::test_transport_url_error_is_retried_with_backoff_then_succeeds` | `LREQ-EXT-100` | `["LREQ-EXT-100"]` |
| `tests/test_collector.py::test_transport_os_error_is_retried_and_bounded_then_request_failed` | `LREQ-EXT-100` | `["LREQ-EXT-100"]` |
| `tests/test_collector.py::test_transport_retry_budget_is_bounded_and_matches_status_backoff_schedule` | `LREQ-EXT-100` | `["LREQ-EXT-100"]` |
| `tests/test_collector.py::test_transport_failure_message_omits_exception_text_and_secrets` | `LREQ-EXT-100`, `LREQ-SEC-020` | `["LREQ-EXT-100", "LREQ-SEC-020"]` |
| `tests/test_collector.py::test_permanent_status_after_transport_retries_is_not_retried_further` | `LREQ-EXT-100` | `["LREQ-EXT-100"]` |
| `tests/test_collector.py::test_coveo_request_failed_carries_attempts_and_failure_class` | `LREQ-EXT-100`, `LREQ-NFR-030` | `["LREQ-EXT-100", "LREQ-NFR-030"]` |
| `tests/test_collector.py::test_category_failure_cause_is_persisted_redacted_and_sibling_categories_unaffected` | `LREQ-EXT-090`, `LREQ-NFR-030`, `LREQ-SEC-020` | `["LREQ-EXT-090", "LREQ-NFR-030", "LREQ-SEC-020"]` |
| `tests/test_collector.py::test_persisted_failure_cause_is_canonical_json_with_null_http_status` | `LREQ-EXT-090`, `LREQ-SEC-020` | `["LREQ-EXT-090", "LREQ-SEC-020"]` |
| `tests/test_database.py::test_category_failure_cause_column_round_trips_without_zero_substitution` | `LREQ-EXT-090`, `LREQ-RPT-020` | `["LREQ-EXT-090", "LREQ-RPT-020"]` |
| `tests/test_database.py::test_set_category_status_default_leaves_stored_cause_unchanged` | `LREQ-EXT-090` | `["LREQ-EXT-090"]` |
| `tests/test_contracts.py::test_category_scores_column_set_includes_failure_cause_and_version_is_1_1_0` | `LREQ-RPT-020` | `["LREQ-RPT-020"]` |

- **Node sketches and hand-derived expectations.**
  - **Node 1 — transient `URLError` retried then succeeds.** Script
    `[URLError("boom"), 200-with-one-record]`; `sleeper = Recorder()`. Expected:
    `result.discovery_status is DiscoveryStatus.COMPLETE`, `observations_emitted == 1`,
    `backoffs == [COVEO_BACKOFF_BASE_SECONDS]` (`2.0`), and exactly two `send` calls.
  - **Node 2 — `OSError` retried and bounded.** Script = `COVEO_MAX_RETRIES + 1` raises.
    Expected: `result.discovery_status is DiscoveryStatus.REQUEST_FAILED`,
    `send` call count `== COVEO_MAX_RETRIES + 1`, and the sleeper's backoff calls are
    `[2.0, 4.0, 8.0, 16.0, 32.0]` (matching the existing exhausted-503 node's schedule at
    `tests/test_collector.py:1125`).
  - **Node 3 — bound and schedule parity.** A mixed script (transport, then `503`s, then a
    terminal raise) yields the same `2 ** (attempts - 1)` schedule and the same total
    attempt cap as a pure-status script; assert total attempts `== COVEO_MAX_RETRIES + 1`.
  - **Node 4 — redaction.** A script raising `URLError` whose text contains a sentinel
    (e.g. `fx.RECORDED_SENTINELS`-style token, or an inline
    `"https://host/path?token=SECRET"`). Expected: the sentinel appears in **no** persisted
    column (`error_summary_json`, `request_metadata_json`, `discovery_failure_cause_json`)
    and not in the exception message.
  - **Node 5 — permanent after retries.** Script `[URLError(...), 403]`. Expected: the
    `403` is permanent, so no further retry occurs after it; the category is
    `request_failed`; the persisted cause's `failure_class == "http_permanent"` and
    `http_status == 403`.
  - **Node 6 — `CoveoRequestFailed` attributes.** A direct
    `fetch_category_page(...)` call (or the adapter path) with a budget-exhausting script:
    the raised `CoveoRequestFailed` has `attempts == COVEO_MAX_RETRIES + 1` and
    `failure_class is CoveoTransportFailureClass.TRANSPORT_FAILURE`; a `503`-exhausted
    script yields `HTTP_TRANSIENT`; an immediate `403` yields `HTTP_PERMANENT` with
    `attempts == 1`.
  - **Node 7 — cause persisted, redacted, isolated.** Run two categories: one whose
    transport fails the budget, one healthy. Expected: the failed category's persisted row
    has a non-null `discovery_failure_cause_json` whose parsed members are exactly the four
    keys and whose `failure_class` is one of the three tokens, `http_status` is `null` or an
    integer, `page_index` is an integer, `attempt_count` is an integer; the healthy
    category's cause is `null`; no sentinel appears in either row.
  - **Node 8 — canonical JSON and `null` status.** The persisted text equals
    `json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))`, and a transport
    failure yields `http_status is None` (JSON `null`), not `0`.
  - **Node 9 — round trip.** Write a cause via `set_category_status`, read it back through
    `get_category_scores`, and assert exact equality; a row with no cause round-trips as
    `None`, never `""` or `0`.
  - **Node 10 — default preserves the stored cause.** Write a non-null cause, then call
    `set_category_status(..., discovery_failure_cause_json=None)` and
    `upsert_category_scores(row)`; assert the stored cause is unchanged.
  - **Node 11 — contract parity.** `TABLE_COLUMNS["category_scores"] ==
    models.MANDATORY_ROW_FIELDS["category_scores"]` including
    `discovery_failure_cause_json`, and `SCHEMA_VERSION == "1.1.0"`.
- **Existing nodes that must keep passing unchanged (verified by reading this session):**
  `tests/test_collector.py::test_transient_429_and_5xx_are_retried_with_backoff_and_retry_after`
  (`:1062-1096`; asserts `backoffs == [7.0, 4.0, 8.0]`),
  `tests/test_collector.py::test_permanent_auth_csrf_and_malformed_request_are_not_retried`
  (`:1100-1127`; asserts `backoffs == [2.0, 4.0, 8.0, 16.0, 32.0]`),
  `tests/test_collector.py::test_failed_page_never_becomes_zero_assets` (`:734-757`),
  `tests/test_collector.py::test_failed_category_does_not_abort_other_categories_and_stays_visible`
  (`:1273`),
  `tests/test_collector.py::test_persisted_metadata_and_error_summaries_contain_no_credentials`
  (`:1361`),
  `tests/test_contracts.py::test_coveo_retry_contract` (traceability key at
  `tests/traceability.json:358-359`).
  `tests/test_database.py::test_category_score_columns_cover_report_read_model`
  (traceability key `tests/traceability.json:420-421`) encodes the previous column set and
  **must** be updated for the new column; that update is part of this chunk's authorized
  contract change, and the node ID and traceability entry are preserved.
- **Contradiction handling.** If any existing test contradicts the SRS or this plan after
  these changes, the test-author leaves it and reports
  `DISPUTE: <test id> — SRS §x says ...`; it is not silently edited.

## 10. Definition of done (gate)

Chunk 23 has **no `requirements-dependency-map.md` §3 gate**. The gate below is the
dispatch's Definition of Done plus the in-scope Chunk 3 gate bullets this remediation
touches (dependency-map §3 Chunk 3: structural validation before any record is read; a
failed page is never zero assets; the discovery-only field set is the allow-list).

- **Full suite green, with a real, countable bullet.** `python -m pytest -q` reports
  `passed, 0 failed` with the real counts written into `Documents/runs/chunk-23.md`; if an
  unrelated pre-existing failure exists, it is reported verbatim rather than claimed green.
- **All four validators valid:** `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`,
  `python -m niche_scout.tools.check_secrets`.
- **`ruff` clean on changed files** (`ruff format` and `ruff check`) using
  `pyproject.toml` (`line-length = 88`, `select = ["E", "F", "I"]`); a pre-existing
  deviation is reported PARTIAL with the unchanged lines named.
- **R1:** a transient `URLError`/`OSError` is retried under the existing bounded backoff;
  the total attempt count never exceeds `COVEO_MAX_RETRIES + 1`; a permanent failure is
  never retried; `CoveoRequestFailed.attempts`/`failure_class` are set at every raise site;
  no exception text reaches a message or a persisted value.
- **R2:** the category-level failure cause is persisted in redacted form on
  `category_scores.discovery_failure_cause_json` with exactly `failure_class`,
  `http_status` (or `null`), `page_index`, and `attempt_count`; a category with no raw rows
  still records its cause; a sibling category is unaffected; `set_category_status`'s
  default leaves a stored cause unchanged and the scoring-phase `upsert_category_scores`
  cannot null it.
- **Schema/interface reconciliation:** `SCHEMA_VERSION == "1.1.0"`; `TABLE_COLUMNS
  ["category_scores"] == models.MANDATORY_ROW_FIELDS["category_scores"]`;
  `interfaces/chunk-02.md` §2.1/§2.4/§2.7/§3 and `interfaces/chunk-03.md` §3/§6 carry the
  recorded amendments; `interfaces/chunk-10.md` is unchanged.
- **No `report.py`, no `cli.py`, no metric/scoring, and no `collector_graphql.py` change.**
- Tests were written **before** implementation and failed as missing-implementation (no
  collection/syntax error); the red state is recorded.
- Plan, run log, new node→LREQ entries, and the seven rulings (R-A1…R-A7) are recorded.

## 11. Explicit prohibitions

- **Live network in development or tests.** No test calls the real endpoint; every test
  injects a transport.
- **No new retry constant, no new backoff formula, no new threshold.** R1 reuses
  `COVEO_MAX_RETRIES` and `COVEO_BACKOFF_BASE_SECONDS` and the existing
  `2 ** (attempts - 1)` schedule; it does not change the rate-limit interval.
- **No infinite retry.** The transport path consumes the same bounded budget.
- **No failure-class token outside `transport_failure` / `http_transient` /
  `http_permanent`.** Do not import or alias `collector_graphql.GraphQLFailureClass`; the
  enum is Coveo-local.
- **No secret, header value, cookie, token, URL, or response body in a persisted value or
  an exception message.** Only a failure class token, an integer HTTP status, an integer
  page index, and an integer attempt count.
- **No `str(exc)` in a persisted value.** The adapter currently interpolates `str(exc)`
  into a `ValidationIssue.message` (`collector_coveo.py:1962`); R2's derivation reads
  `code`/`context` scalars only, and R1 must not extend that practice.
- **No schema change beyond the one authorized column**
  (`category_scores.discovery_failure_cause_json`) and its `SCHEMA_VERSION` bump; no
  `ALTER TABLE`, no migration, no second column, no index.
- **`fetch_category_page` and `discover_category` signatures unchanged.**
- **Do not resolve the `AGENTS.md` open obligations** (URI trailing-identifier extraction,
  OI-6, `runs.taxonomy_sha256`).
- **Do not touch sampling constants or `SAMPLING_RULE_VERSION`** (chunk 24).
- **Do not edit** `Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`,
  `AGENTS.md`, `kilo.json(c)`, `.kilo/`, or `pyproject.toml`; edit only the two authorized
  interface files.
- **No rename or deletion of an existing pytest node ID or its `tests/traceability.json`
  entry.**
- **One concern per diff.** R1 and R2 land as two separate changes.

## 12. Resolved decisions (operator rulings 2026-09-28) and open questions

### 12.1 Resolved — the seven prior blocking questions

The seven questions below were open in the DRAFT plan. They were answered by the operator on
2026-09-28 (recorded in `Documents/runs/chunk-23.md`) and are **adopted, not recommended**;
each is reflected in §5, §6, §7, §9, §11.

- **R-A1 (was Q1 → (b)).** Add `attempts: int` to `CoveoRequestFailed`. Do **not** change
  the `fetch_category_page` signature. Implemented as §7 DP2; `interfaces/chunk-03.md` §3
  amended.
- **R-A2 (was Q2 → (a)).** Add exactly one nullable `category_scores` column,
  `discovery_failure_cause_json TEXT`, and bump `SCHEMA_VERSION` `"1.0.0"` → `"1.1.0"`;
  reconcile `interfaces/chunk-02.md` §2.1/§2.4/§2.7/§3 and `models.CategoryScoreRecord` +
  `MANDATORY_ROW_FIELDS`. Accepted consequence: an existing `1.0.0` database no longer
  opens (`SchemaVersionError`); there is no silent migration and no `ALTER TABLE`.
- **R-A3 (was Q3 → DB-only).** `report.py` and `LREQ-RPT-020` rendering are out of scope.
- **R-A4 (was Q4).** Add the additive keyword-only `discovery_failure_cause_json` parameter
  on `set_category_status`, written by `_finalize_result`. The default (`None`) leaves the
  stored value unchanged, so the scoring-phase `upsert_category_scores` cannot null it.
- **R-A5 (was Q5).** The persisted token set is exactly
  `transport_failure` / `http_transient` / `http_permanent`, via a Coveo-local
  `str, Enum` (`CoveoTransportFailureClass`); `GraphQLFailureClass` is not imported.
- **R-A6 (was Q6).** Column `discovery_failure_cause_json`; JSON keys `failure_class`,
  `http_status`, `page_index`, `attempt_count`; canonical
  `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
- **R-A7 (was Q7).** A pure transport failure persists `http_status` as JSON `null`, never
  `0`.

### 12.2 Open questions

**None blocking freeze.** One residual, non-blocking ambiguity is recorded rather than
resolved (per `AGENTS.md`: record, do not silently resolve):

- **R-R1 (non-blocking).** The three Q5 tokens do not name a **structural 200** page
  failure (`PAGE_FAILED` from `response_missing_required_member`): it is neither a
  transport failure nor an HTTP-status failure. This plan persists `http_permanent` for it
  (no transport cause, no transient status) and records the ambiguity in
  `Documents/runs/chunk-23.md`; it invents no fourth token. If the operator prefers a
  different token, the persisted value changes but no test node ID or traceability entry
  does.

**Carried-forward obligations (recorded, not resolved, and not owned by this chunk):**
URI trailing-identifier extraction (identity mapping rule 1.0.1) UNVERIFIED; OI-6
(CSRF/session sufficiency) unassigned; `runs.taxonomy_sha256` empty-hash rejection owner
Chunk 10. The chunk-15 plan §12 obligation "Discovery-page failure has no persisted cause —
Owner: none" is **discharged for the persisted-cause half by this chunk** (the
limitation-string half was already chunk 15's).

## 13. Freeze record

This plan is **Status: FROZEN** (2026-09-28). The §9 pytest node IDs are frozen with the
plan and SHALL NOT be renamed by a later change. The two authorized frozen-surface changes
(R-A1 in `interfaces/chunk-03.md`; R-A2/R-A4/R-A6 in `interfaces/chunk-02.md`) are recorded
in §5/§6/§12 and have been applied to those files; `interfaces/chunk-10.md` is unchanged.
`Documents/SRS-lean.md` is not edited; the SRS §6.5/§14 diagnostic-field addition is a
recorded deviation, not an SRS edit — the `category_scores` column is a Chunk 23
`SCHEMA_VERSION "1.1.0"` addition authorized by the operator, and any future SRS
reconciliation is a human/document-consistency action, not this chunk's.

**Task breakdown (routing).**

- [ ] T1 — `test-author`: add the `_ScriptedTransport` helper and the nine new nodes to
  `tests/test_collector.py`/`tests/test_database.py`/`tests/test_contracts.py`, plus the
  eleven `tests/traceability.json` entries (§9). Preserve the node IDs row-for-row; the
  R2 nodes are no longer conditional. (LREQ-EXT-100, LREQ-EXT-090, LREQ-NFR-030,
  LREQ-SEC-020, LREQ-RPT-020)
- [ ] T2 — `test-author`: run the suite and record the red state (the new nodes fail as
  missing-implementation; no collection/syntax error). (all)
- [ ] T3 — `impl-deep`: R1 in `collector_coveo.py` (§7 DP1/DP1b/DP2) — smallest diff, no
  frozen-signature change. (LREQ-EXT-100)
- [ ] T4 — `impl-deep`: R2 — `models.py` field, `database.py` column/version/parameter,
  `collector_coveo.py` `_finalize_result` cause derivation/write, `pipeline.py` cause
  pass-through where it writes `set_category_status` (§7 DP4–DP7). (LREQ-EXT-090,
  LREQ-NFR-030, LREQ-SEC-010/020)
- [ ] T5 — `impl-deep`: run the suite, the four validators, and `ruff` on the changed
  files; report real counts and output. (all)
- [ ] T6 — `spec-reviewer`: plan, diff, tests, run-log evidence, and the two interface-file
  reconciliations. (all)
