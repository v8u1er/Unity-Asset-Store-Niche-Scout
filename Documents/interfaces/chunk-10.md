# Chunk 10 — Pipeline orchestration (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-10-pipeline-orchestration.md` §5 (`Status: FROZEN`, 2026-09-22, as amended by the lead ruling recorded in §5.8), reproduced as the frozen public contract.
Implementation: `src/niche_scout/pipeline.py` (additive; the Chunk 6A/6B names in that module are unchanged) and one additive method in `src/niche_scout/database.py`.

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/pipeline.py` | **I/O / orchestration** | Run sequencing, transaction boundaries, status transitions, and the run-level outcome value. Reads no clock: every timestamp comes from the caller-injected `clock`. Performs no protocol behavior; it calls the Chunk 3/5 adapters and the Chunk 4B/6A/6B orchestration helpers. |
| `src/niche_scout/database.py` | **I/O** | Two additive additions, no schema change: the §5.5 non-empty `runs` provenance guard and the §5.8 `update_run_scoring_cutoff` writer. |

Purity is unchanged: `metrics.py` and `scoring.py` are untouched and still import no I/O module (`check_import_boundaries` passes).

## 2. Public entry point

```python
@dataclass(frozen=True, slots=True)
class PipelineResult:
    """The run outcome returned to the caller (Chunk 12 maps it to an exit code)."""
    run_id: str
    status: str                       # RunStatus value: completed | failed
    scoring_cutoff_utc: datetime | None
    categories: tuple[str, ...]       # requested categories, declared order
    identity_preflight_status: str    # IdentityPreflightStatus value
    category_scores_written: int
    limitations: tuple[str, ...]      # redacted; names category and field only

    @property
    def succeeded(self) -> bool: ...  # True iff status == RunStatus.COMPLETED.value


def run_pipeline(
    *,
    config: NicheScoutConfig,
    categories: Sequence[str],
    credentials: Credentials,
    repository: SqliteRepository,
    clock: Callable[[], datetime],
    coveo_transport: CoveoTransport,
    graphql_transport: GraphQLTransport,
    sleeper: Callable[[float], None] = time.sleep,
    run_id: str | None = None,
    taxonomy_path: Path | None = None,
    template_path: "Path | str" = COVEO_TEMPLATE_PATH,
    correlation_mode: GraphQLOperationCorrelationMode = GraphQLOperationCorrelationMode.EXPLICIT_KEY,
    preflight_policy: PreflightPolicy | None = None,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    taxonomy_sha256: str | None = None,
) -> PipelineResult: ...
```

## 3. Semantics of `run_pipeline`

Executes one complete run in the SRS §3.2 order (plan §5.1/§5.2 steps 1–18):

1. Requested categories are the caller-supplied `categories` in declared order.
2. Configuration and taxonomy are validated **before any network request**; a
   failure raises `PipelineConfigurationError` / `TaxonomyInvalidError` and
   touches no transport.
3. The `RunRecord` is created with a **non-empty** `taxonomy_sha256`
   (`taxonomy_sha256_for(payload)` when not caller-supplied), the policy
   versions, `categories_json` in declared order, the config snapshot, and a
   seeded `identity_preflight_summary_json` (the column is `TEXT NOT NULL`).
4. Each category is discovered inside one `category_transaction`; a failed
   category is recorded as its `DiscoveryStatus` and never aborts another
   (LREQ-NFR-030).
5–7. Raw observations are persisted before canonicalization; canonical
   populations and the deterministic sample are built and materialized (Chunk
   4B), all with caller-supplied timestamps.
8. The identity preflight (Chunk 6A) runs and persists its artifacts before the
   gate returns.
9. Only when the gate is `passed`: the unique sampled-identity union is computed,
   the projection is logged via `log_enrichment_projection` **before** the first
   request (LREQ-NFR-020), and `enrich_unique_identities` executes.
10. `capture_scoring_cutoff_utc(clock())` is called exactly once, after
    enrichment and before metric computation; the same value is persisted once
    through `update_run_scoring_cutoff` and passed to every pure call and to
    `finalize_enrichment` (LREQ-ARCH-020).
11. `finalize_enrichment` finalizes the authoritative per-stratum usable counts
    before metrics.
12–16. Metrics → LOO references → scores → the fixed `base_rankable_candidates`
    → sensitivity **only over that set** → final evidence and rankability
    (Chunks 7B/8/9A/9B; no writes).
17–18. One `upsert_category_scores` pass writes the full `CategoryScoreRecord`
    rows; the run is then marked `completed`.

Null / edge behaviour:

- A preflight status of `failed` **or** `insufficient` returns
  `PipelineResult(status=RunStatus.FAILED.value, scoring_cutoff_utc=None,
  limitations=<...>)` after persisting one null-score `category_scores` row per
  requested category with `evidence_grade = insufficient`,
  `rankability_status = not_rankable`, and explicit preflight warnings. Zero
  bulk-enrichment requests are issued, and metric/score/ranking computation is
  skipped.
- An existing `failed` run status is never overwritten with `completed`.
- Runs with fewer than `MIN_CATEGORIES_PER_RUN` (8, non-configurable per SRS §14)
  requested categories are rejected with `PipelineConfigurationError` before any
  transport call, before any run row, and before ranking. The rejection uses the
  frozen `models.MIN_CATEGORIES_PER_RUN` constant, not
  `config.min_categories_per_run`.
- `run_pipeline` never calls `sys.exit` and never parses `argv`; the exit code is
  Chunk 12's.

## 4. `PipelineResult` invariants

- `succeeded` is `True` iff `status == RunStatus.COMPLETED.value`.
- `scoring_cutoff_utc is None` iff the run did not reach step 10 (preflight
  failure or an aborted run); on a completed run the persisted
  `runs.scoring_cutoff_utc` equals this value.
- `limitations` is a tuple of redacted strings naming a category and a field
  only; it never contains an identity string, a header value, a token, or a
  response body (LREQ-SEC-010/020).
- `category_scores_written` is the number of `(run_id, category)` rows the final
  persistence pass wrote; it is a count, never a fabricated `0` standing in for a
  failed write.

## 5. Diagnostics and helpers this chunk produces

```python
class PipelineError(RuntimeError): ...                # base for run-level aborts
class PipelineConfigurationError(PipelineError): ...  # invalid/missing config, run-size rejection
class TaxonomyInvalidError(PipelineError): ...        # invalid/stale/incomplete taxonomy

def taxonomy_sha256_for(payload: object) -> str: ...
    """Lowercase-hex SHA-256 over the canonical form of the taxonomy payload
    (``json.dumps(payload, sort_keys=True, separators=(",", ":"),
    ensure_ascii=False).encode("utf-8")``). Raises ValueError for a payload that
    yields an empty digest input. Pure: no I/O, no clock."""

def category_status_for(
    discovery_status: str,
    *,
    warnings: Sequence[str],
    evidence_grade: str,
    rankability_status: str,
) -> CategoryStatus: ...
    """Internal roll-up over fields that are already final. ``page_failed`` /
    ``request_failed`` -> FAILED; ``truncated`` / ``filter_unverified`` /
    ``category_mismatch`` / ``identity_incomplete`` -> DEGRADED; otherwise
    HEALTHY. Never persisted as a column and never surfaced as a discovery
    status, score state, evidence grade, or rankability status."""
```

## 6. Frozen persisted JSON shapes (produced here, consumed read-only by Chunk 11)

- `warnings_json` is `json.dumps(sorted(set(codes)), separators=(",", ":"))` —
  a JSON array of unique warning codes in ascending lexical order, where `codes`
  are `models.WarningCode` values plus the preflight/limitation codes Chunk 10
  observes. An empty set serializes to `"[]"`. Set-then-sort keeps the payload
  independent of iteration order (LREQ-ARCH-030).
- `missing_components_json` is
  `json.dumps([k for k in COMPONENT_WEIGHT_KEYS if component_is_none(k)],
  separators=(",", ":"))` — the component keys whose value is `None`, in the
  fixed `("D", "C", "R", "Q")` order. All four available serializes to `"[]"`.
- Neither payload contains a credential, header value, cookie, response body,
  identity string, or category path (LREQ-SEC-010/020).

Chunk 11 SHALL NOT redefine either shape.

## 7. `runs.taxonomy_sha256` non-empty enforcement (additive to `database.py`)

Two-part, additive, no schema change:

1. `pipeline.py` never constructs an empty hash: `taxonomy_sha256_for` returns a
   64-char digest, and a caller-supplied `taxonomy_sha256` is accepted only when
   it is a `str` with non-whitespace content, else `ValueError`.
2. `database.py` rejects an empty/whitespace value on the `runs` write path with
   `InvalidRecordValueError`, scoped to the five provenance/identity text columns
   (`taxonomy_sha256`, `taxonomy_version`, `endpoint_contract_version`,
   `identity_mapping_rule_version`, `sampling_rule_version`). `None` keeps the
   existing `_validate_required_columns` path; no other table is affected; the
   message names the table and column only, never the value.

Dependency-map §7 assigns this obligation to Chunk 10 (the only chunk that
constructs a `RunRecord`).

## 8. `runs.scoring_cutoff_utc` persistence (additive to `database.py`)

```python
def update_run_scoring_cutoff(
    self, run_id: str, scoring_cutoff_utc: datetime
) -> None: ...
```

Sets `runs.scoring_cutoff_utc` to the single captured cutoff value, mirroring
`update_run_status`: `_check_open()`; aware-UTC encode via `_encode_column`; one
`UPDATE runs SET scoring_cutoff_utc = ? WHERE run_id = ?`; `KeyError` when no row
matches. `run_pipeline` calls it exactly once, immediately after step 10's
capture. The column is nullable by DDL and stays `None` for a run that never
reaches step 10.

## 9. Explicitly not produced here

- Report rendering and the read-only dashboard: **Chunk 11**.
- CLI commands, argument parsing, exit codes, and configuration precedence:
  **Chunk 12**.
- Preflight planning/gating (6A), unique enrichment (6B), raw estimators (7B),
  normalization/scoring (8), pre-sensitivity evidence (9A), sensitivity and final
  evidence/rankability (9B): consumed, never re-derived.
- Rejection of runs with fewer than `MIN_CATEGORIES_PER_RUN` is enforced here
  (LREQ-CLI-040's pipeline half); the CLI's non-zero exit mapping is Chunk 12.

## 10. Known plan/interface inconsistency (recorded, not a defect)

Plan §12 item 4's prose describes the derived `run_id` as "the injected clock plus
a caller-supplied suffix"; the frozen signature (§2 above) has no suffix
parameter, and the implementation derives `run-<isoformat(run_started_at_utc)>`
from the clock alone. Deterministic for a fixed clock; two runs at the same
instant without an explicit `run_id` collide on the `runs` primary key. The frozen
signature governs; a caller wanting distinct same-instant runs passes `run_id`.

Consumers: **Chunks 11, 12, 13**.
