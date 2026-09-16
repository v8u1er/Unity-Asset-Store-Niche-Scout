# Chunk 2 — SQLite implementation and repository behavior

Status: VERIFIED
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-00.md (Status: VERIFIED)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 3 (Coveo discovery adapter and streamed raw persistence)
  Chunk 4B (Sample persistence, overlap, and sampling summaries)
  Chunk 6A (Identity preflight planner and gate)
  Chunk 6B (Unique enrichment executor and persistence)
  Chunk 10 (Pipeline orchestration)
  Chunk 11 (Report renderer and read-only dashboard)

## 1. Goal

Chunk 0 froze the persistence *contract* — `SCHEMA_VERSION`, the `Repository`
protocol, `DDL_STATEMENTS`/`CREATE_TABLE_STATEMENTS`/`TABLE_COLUMNS`/
`TABLE_PRIMARY_KEYS`/`TABLE_INDEXES`, and the five frozen row dataclasses — but
deliberately executed nothing: no connection, no DDL run, no transaction, no
savepoint, no insert. This chunk owns the physical SQLite implementation behind
that frozen contract so that the rest of the pipeline can persist an audit
trail. It makes true, for the first time, that a `runs` row plus streamed
`raw_discovery_observations`, `sample_members`, `enrichment_observations`, and
`category_scores` rows can be written to one local SQLite database, read back
as the frozen typed records, and survive failure isolation: duplicate sample
membership is rejected by the primary key, `(run_id, category)` is enforced for
scores, a failed category commits or rolls back only its own observation group,
secrets can never enter a persisted record or an error summary, and no
discovered response set has to be held in memory to be persisted. It also
publishes the public SQLite surface as `Documents/interfaces/chunk-02.md` so
Chunks 3, 4B, 6A, 6B, 10, and 11 can build against frozen persistence
signatures instead of the module's source.

## 2. Scope

### In scope

- The physical SQLite implementation of a `Repository` structurally compatible
  with the frozen `Repository` protocol (identical signatures, no redefinition
  of any method it already declares).
- Connection lifecycle: construction from a `pathlib.Path`, connection
  establishment, `close`, and a context-manager form.
- Connection pragmas: `foreign_keys = ON`, `journal_mode = WAL`,
  `busy_timeout`, `synchronous = NORMAL`.
- Schema initialization/migration entry point keyed on the frozen
  `SCHEMA_VERSION = "1.0.0"`, applying the frozen DDL in dependency order
  (`runs` before its referencing tables, index last).
- Streamed insertion of raw discovery observations: an incremental
  `append`/`iter`-consuming API that flushes batches as it consumes an
  iterable, in addition to the batch
  `insert_raw_discovery_observations` from the frozen protocol (LREQ-NFR-010
  persistence support).
- Transaction/savepoint primitives and category-isolated transaction
  boundaries, including nested savepoint semantics (release on success, roll
  back to savepoint on failure) that leave already-committed category work
  intact.
- Insert-vs-upsert semantics per table, documented per table in section 5.9,
  including the update path for post-discovery fields
  (`asset_identity_key`, `stratum_index`, `is_duplicate`,
  `duplicate_of_observation_id`).
- Run/category status transition APIs, including the run-level
  `update_run_status` from the frozen protocol and category status transitions
  that record one category's failure without touching unrelated categories.
- Exact exception types raised on constraint violation (duplicate sample
  membership, duplicate score row, duplicate run/enrichment row, foreign-key
  violation) and on calling into a closed/uninitialized repository.
- Boolean/int encoding for SQLite (`bool` ⇄ `INTEGER` `0`/`1`) and `None`
  round-tripping for every nullable column, with no zero substitution.
- Redacted error summaries and structured JSON columns persisted verbatim as
  the text the frozen models produced.

### Explicitly out of scope (and who owns it instead)

- **Defining the schema, the protocol, the enums, or the row dataclasses.**
  Chunk 0 is the primary implementation chunk and completion chunk for
  `LREQ-ARCH-010`, `LREQ-ARCH-020`, `LREQ-NFR-050`, and `LREQ-NFR-060`. This
  chunk consumes `DDL_STATEMENTS`, `TABLE_COLUMNS`, `TABLE_PRIMARY_KEYS`,
  `TABLE_INDEXES`, `SCHEMA_VERSION`, and the five record classes and SHALL NOT
  edit them, add columns, or add tables.
- **Sampling materialization.** Chunk 2 is the *supporting contract chunk* for
  `LREQ-SMP-080` (persistence support only). The primary implementation is
  Chunk 4B, and the completion chunks are Chunk 4B and Chunk 6B. Chunk 2
  provides `insert_sample_members`, sample reads, and upsert/update paths for
  sampling summaries; it does not select samples, compute `N_h`/`n_h`,
  materialize `sample_members` from a sampling result, compute overlap counts,
  or decide pending placement of `u_demand_h`/`u_recent_h`/`u_quality_h`.
  Chunk 4B does that; Chunk 6B finalizes the usable counts.
- **At-most-once enrichment behavior.** Chunk 2 is a *supporting chunk* for
  `LREQ-GQL-080`. The primary owner is Chunk 6B and the completion chunk is
  Chunk 6B. Chunk 2 provides the `(run_id, asset_identity_key)` primary key,
  the upsert path, and `get_enrichment_observation` so an existing observation
  can be reused; it does not decide that a sample identity has already been
  enriched, does not deduplicate the sampled-identity union, and does not reuse
  preflight responses.
- **Streamed discovery and redaction behavior.** Chunk 2 is a *supporting
  chunk* for `LREQ-NFR-010`; the primary owner and completion chunk is Chunk 3.
  Chunk 2 provides a streaming-capable persistence sink; Chunk 3 owns the
  network streaming, pagination, and memory behavior.
- **Secret handling at the boundary.** Chunk 2 is the *primary owner* of
  `LREQ-SEC-020` (the SRS module column for `LREQ-SEC-020` names
  `config.py`, `collector.py`, `database.py`), with supporting chunks Chunk 0,
  Chunk 3, and Chunk 5 and completion chunk Chunk 13. Inside this chunk that
  means only the persistence-side obligation: no secret reaches a persisted
  column or a persisted/logged error summary. Environment reading, log
  redaction, and source-control hygiene remain with Chunks 0, 3, 5, and 12.
- **Run orchestration and status policy.** Chunk 10 is the primary
  implementation chunk for orchestrating category failures and run completion.
  Chunk 2 provides the transition APIs and the isolation guarantee; Chunk 10
  decides when they are called.
- **Preflight gating.** Chunk 6A is the primary implementation chunk for
  preflight planning and gating. Chunk 2 persists preflight-shaped data
  (`identity_preflight_status`, `identity_preflight_summary_json`,
  `preflight_selected`, per-operation enrichment outcomes) but enforces no gate.
- **Metric eligibility, normalization, scoring, report, and CLI behavior.**
  Chunks 7A/7B/8/9A/9B/11/12 own those; Chunk 2 only stores their outputs.
- **End-to-end and golden-vector acceptance verification.** Chunk 13 owns
  `LREQ-TST-080`/`LREQ-TST-090` and the full acceptance suite; Chunk 2's
  `tests/test_database.py` verifies persistence behavior in isolation.

## 3. Requirements this chunk must satisfy

Ownership roles below are the exact matrix labels from
`Documents/requirements-dependency-map.md` "Ownership and test traceability
matrix" (lines 45–136); normative text is quoted from `Documents/SRS-lean.md`.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-SEC-020 | **Primary owner**; Supporting chunks: Chunk 0, Chunk 3, Chunk 5; Completion chunk: Chunk 13. (Matrix row, line 69.) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern SHALL be ignored by version control." (SRS-lean.md lines 351–352.) Chunk 2 owns the SQLite clause and the error-message clause **as they apply to persisted records**: no credential value, token, cookie, header, or connection string may appear in any column this chunk writes, and every persisted error summary must already be redacted. Chunk 0 owns `.env` ignoring (verified). | §4.3 |
| LREQ-SMP-080 | **Supporting contract chunk** for persistence support only. Primary owner: Chunk 4B; Supporting chunks: Chunk 2, Chunk 4A, Chunk 6B; Completion chunks: Chunk 4B, Chunk 6B. (Matrix row, line 81.) | "Every category SHALL persist discovered population size, sample enrichment sample size, usable sample size by component, stratum boundaries, stratum sizes and selected counts, selected identity keys or a reproducible selection digest, sampling-rule version, census flag, and duplicate/cross-category overlap counts." "For every stratum, the persisted summary SHALL include `N_h` (discovered population), `n_h` (sampled population), `u_demand_h`, `u_recent_h`, and `u_quality_h`, together with the eligibility rule used for each usable count." "For a census category, all discovered canonical assets SHALL be selected and `sample_is_census` SHALL be true; its stratum summaries SHALL retain the same `N_h`, `n_h`, and usable-count fields used by the sampled estimator." (lines 472–481.) "The following SHALL be persisted as distinct values: `discovered_population_count`, `enriched_sample_count`, `usable_demand_sample_count`, `usable_recent_supply_sample_count`, and `usable_quality_sample_count` as distinct values. `enriched_sample_count` SHALL never replace the discovered population." (lines 483–487.) Chunk 2's share: the `sample_members` primary key, the per-category/stratum persistence paths, upsert semantics for summary fields, and read-back fidelity. It does not compute any of these values. | §5, LREQ-SMP-080 (lines 472–489) |
| LREQ-GQL-080 | **Supporting chunk** for persistence support only. Primary owner: Chunk 6B; Supporting chunks: Chunk 2, Chunk 5, Chunk 6A; Completion chunk: Chunk 6B. (Matrix row, line 67.) | "A unique sampled identity SHALL be enriched at most once per run, regardless of how many category samples reference it. The result SHALL be joined to every referencing category." (lines 336–338.) Chunk 2's share: a `(run_id, asset_identity_key)` primary key that makes two enrichment rows for one identity per run impossible, plus an upsert path and `get_enrichment_observation` so a prior (e.g. preflight) result can be retrieved and reused. Chunk 2 does not decide at-most-once execution, does not own `enrichment_observations` reads, and does not join results to referencing categories. | §4.2 |
| LREQ-NFR-010 | **Supporting chunk** for persistence support only. Primary owner: Chunk 3; Supporting chunks: Chunk 2; Completion chunk: Chunk 3. (Matrix row, line 121.) | "Discovery persistence SHALL be streamed and SHALL not require all responses in memory." (lines 1162–1163.) Chunk 2's share: a persistence sink that accepts an iterable of `RawDiscoveryObservationRecord` and flushes without materializing the whole sequence (section 5.5). Chunk 3 owns network-level streaming and the end-to-end memory behavior. | §11 |
| LREQ-NFR-020 | **Supporting chunk** for persistence support only. Primary owner: Chunk 6B; Supporting chunks: Chunk 2, Chunk 6A; Completion chunk: Chunk 10. (Matrix row, line 122.) | "Before bulk enrichment, log discovered canonical assets, sampled assets, unique enrichment identities, and projected minimum enrichment time." (lines 1165–1166.) The SRS `Module` column for LREQ-NFR-020 names `collector.py`, `pipeline.py` (dependency map line 285), and Chunk 2 is named by the matrix as a supporting chunk because the three counted quantities are repository reads. Chunk 2's share: cheap, typed **query surface** for those three counts — `count_discovery_observations(run_id)`, `count_sample_members(run_id)`, and `count_distinct_enrichment_identities(run_id)` over `raw_discovery_observations`, `sample_members`, and `enrichment_observations` respectively, plus the general read APIs (`get_run`, `get_sample_members`, `get_enrichment_observation`, `get_category_scores`, `iter_raw_discovery_observations`). Those three tables are Chunk 2's own, so the counts Chunk 6B's log statement uses can only come from this read surface (section 5.10). Chunk 2 **does not log anything**; the logging itself is Chunk 6B's, and the completion chunk is Chunk 10. | §11 |
| LREQ-EXT-050 | **Supporting chunk** only. Primary owner: Chunk 3; Supporting chunks: Chunk 1, Chunk 2; Completion chunk: Chunk 3. (Matrix row, line 54.) | Chunk 2 provides no discovery behavior. Its share per the dependency map `Module` column (`collector.py`, line 157) is that persisted discovery observations can be read back per `(run_id, category)` in `discovery_ordinal` order, so verified `totalCount`, natural terminal page, truncation, failed page, filter uncertainty, category mismatch, and zero-results states survive the round trip without being flattened to zero. The corresponding SRS text is LREQ-EXT-050 in §4.1; the normative pagination wording is quoted in the Chunk 3 plan, not here. | §4.1 |
| LREQ-EXT-070 | **Supporting chunk** only. Primary owner: Chunk 1; Supporting chunks: Chunk 2; Completion chunk: Chunk 3. (Matrix row, line 56.) | Chunk 2 provides no identity resolution. Its share per the dependency map `Module` column (`validation.py`, line 159) is that `identity_resolution_status` and `identity_resolution_reason` round-trip verbatim as `resolved`/`unresolved`/`conflict`, and that `asset_identity_key` stays `NULL` for unresolved and conflicting observations instead of being filled with a placeholder. | §4.1 |
| LREQ-EXT-090 | **Supporting chunk** only. Primary owner: Chunk 3; Supporting chunks: Chunk 1, Chunk 2; Completion chunk: Chunk 10. (Matrix row, line 58.) | Chunk 2's share per the dependency map `Module` column (`collector.py`, `validation.py`, `pipeline.py`, line 161) is persistence-side only: a failed page's observation state and redacted error summary survive the round trip as a failure and never read back as zero assets. The Chunk 10 completion chunk owns warning generation and non-rankable mapping. | §4.1 |
| LREQ-GQL-050 | **Supporting chunk** only. Primary owner: Chunk 5; Supporting chunks: Chunk 1, Chunk 2; Completion chunk: Chunk 5. (Matrix row, line 64.) | Chunk 2's share per the dependency map `Module` column (`collector.py`, line 172) is that independent operation outcomes persist in separate columns (`product_detail_status`, `page_views_status`, `graphql_id`/`product_id`, `rating_*`, `review_count`, `first_published_date_utc`, `product_page_views`, and the two per-operation error summaries), so a valid ProductDetail survives a failed PageViews and vice versa. | §4.2 |
| LREQ-ID-010 | **Supporting chunk** only. Primary owner: Chunk 6A; Supporting chunks: Chunk 2, Chunk 4B, Chunk 5; Completion chunk: Chunk 6A. (Matrix row, line 70.) | Chunk 2's share per the dependency map `Module` column (`pipeline.py`, `sampling.py`, line 188) is the `preflight_selected` column on `sample_members` plus a read/update path so the deterministic preflight selection is persisted, as LREQ-ID-010 requires. Chunk 2 does not select the preflight set. | §4.4 |
| LREQ-ID-020 | **Supporting chunk** only. Primary owner: Chunk 6A; Supporting chunks: Chunk 1, Chunk 2, Chunk 5; Completion chunk: Chunk 6A. (Matrix row, line 71.) | Chunk 2's share per the dependency map `Module` column (`collector.py`, `validation.py`, `pipeline.py`, line 189) is that preflight operation outcomes persist through the same `enrichment_observations` upsert path with independent operation statuses and correlation mode recorded in `request_metadata_json`. Chunk 2 performs no preflight execution or gate decision. | §4.4 |
| LREQ-ID-040 | **Supporting chunk** only. Primary owner: Chunk 6A; Supporting chunks: Chunk 2, Chunk 5; Completion chunks: Chunk 6A, Chunk 10. (Matrix row, line 73.) | Chunk 2's share per the dependency map `Module` column (`pipeline.py`, `database.py`, line 191) is that `identity_preflight_status` and `identity_preflight_summary_json` on `runs` are writable after run creation, so `passed`/`failed`/`insufficient` and the summary survive the round trip. Chunk 6A owns the pass/fail decision; Chunk 10 owns "`failed preflight blocks bulk enrichment, successful results reused`". | §4.4 |
| LREQ-NRM-020 | **Supporting chunk** only. Primary owner: Chunk 8; Supporting chunks: Chunk 2; Completion chunk: Chunk 10. (Matrix row, line 94.) | "`reference_size = category_count - 1`. Field-specific usable reference counts SHALL be stored separately." (lines 881–882.) Chunk 2's share per the dependency map `Module` column (`scoring.py`, `database.py`, line 227) is that `reference_size` and `reference_usable_counts_json` persist as separate columns on `category_scores` and round-trip without being recomputed or aliased. Chunk 8 computes them; Chunk 10 completes them in a persisted run. | §8 |
| LREQ-SEN-020 | **Supporting chunk** only. Primary owner: Chunk 9B; Supporting chunks: Chunk 8, Chunk 9A; Completion chunk: Chunk 10. (Matrix row, line 109.) | "Report top-three membership stability, top-five membership stability, each category's rank under each policy, maximum rank displacement, and maximum score displacement. The persisted field names SHALL include `top_3_stability`, `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, and `sensitivity_warning`." (lines 1068–1072.) "If fewer than `k` rankable categories exist, the value is null rather than padded with unavailable categories." (lines 1086–1087.) Chunk 2's share per the dependency map `Module` column (`scoring.py`, `database.py`, line 257) is that those five columns persist and round-trip; in particular a null stability value stays `NULL` and is never written as `0.0`. Chunk 9B computes the diagnostics; Chunk 10 persists a completed run. | §9 |
| LREQ-RPT-020 | **Supporting chunk** only. Primary owner: Chunk 11; Supporting chunks: Chunk 4B, Chunk 8, Chunk 9B, Chunk 10; Completion chunk: Chunk 11. (Matrix row, line 113, which names Chunk 2 via the dependency map `Module` column for LREQ-RPT-020 at line 266: `report.py` only.) | Chunk 2 provides no rendering. Its share is that every field the primary table must show — "indeed `sample size`, census flag, unique enrichment count, sample fraction, sampling basis, cross-category overlap count, usable count and stratum eligibility coverage per component, evidence grade, rankability, discovery status, page-view semantic status, `top_3_stability`, `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, sensitivity warning, and the percentage of the category sample shared with other categories" (lines 1113–1119) — is readable back from `category_scores`/`sample_members` as the typed record. The dependency map matrix does **not** list Chunk 2 as a supporting chunk for LREQ-RPT-020; the row is recorded here only because the Chunk 11 read model consumes this chunk's read APIs. | §10 |
| LREQ-TST-080 | **Supporting chunk** only. Primary owner: Chunk 13; Supporting chunks: "All runtime chunks"; Completion chunk: Chunk 13. (Matrix row, line 134.) | "An end-to-end fixture SHALL exercise category validation, pagination, duplicate/overlapping identities, four-stratum sampling, one enrichment per unique sampled identity, partial GraphQL failure, metrics, scoring, evidence, sensitivity, SQLite persistence, and report rendering." (lines 1261–1264.) Chunk 2's share is the "SQLite persistence" clause, verified in `tests/test_end_to_end.py`; Chunk 13 owns the whole fixture. | §13 |

### Chunk 2 role summary

- **Primary owner:** `LREQ-SEC-020` (SQLite and error-message clauses; completion in Chunk 13).
- **Supporting contract chunk (persistence only, explicit):** `LREQ-SMP-080`
  (completed by Chunks 4B and 6B), `LREQ-GQL-080` (completed by Chunk 6B),
  `LREQ-NFR-010` (completed by Chunk 3).
- **Supporting chunk, no primary claim:** `LREQ-NFR-020` (primary Chunk 6B,
  completed by Chunk 10), plus `LREQ-EXT-050`, `LREQ-EXT-070`, `LREQ-EXT-090`,
  `LREQ-GQL-050`, `LREQ-ID-010`, `LREQ-ID-020`, `LREQ-ID-040`, `LREQ-NRM-020`,
  `LREQ-SEN-020`, `LREQ-RPT-020`, `LREQ-TST-080`.

Nothing in this table is inferred from the dispatch message: every ownership
label is the matrix's own wording (lines 45–136) and every normative sentence is
quoted from `Documents/SRS-lean.md` at the cited lines. The Chunk 2 dependency
map section (lines 483–518) names exactly four supporting contracts —
`LREQ-SMP-080`, `LREQ-GQL-080`, `LREQ-NFR-010`, `LREQ-SEC-020` — which agrees
with the matrix rows above.

## 4. Interface contracts consumed

Chunk 0 is the only prerequisite. `Documents/interfaces/chunk-00.md` is
`Status: VERIFIED`. The fragments below are copied from that file (and, where
the interface file abbreviates, expanded from
`Documents/plans/chunk-00-project-skeleton-and-contracts.md` §5.3/§5.4, which
the interface file references as its source plan). There is no
`Documents/interfaces/chunk-01.md`; nothing else may be assumed (section 12).

### 4.1 Persistence contract (interface file §6, lines 313–361)

```python
SCHEMA_VERSION = "1.0.0"

class Repository(Protocol):
    def insert_run(self, run: RunRecord) -> None: ...
    def update_run_status(self, run_id: str, status: str,
                          completed_at_utc: Optional[datetime] = None) -> None: ...
    def insert_raw_discovery_observations(self, observations: Sequence[RawDiscoveryObservationRecord]) -> None: ...
    def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None: ...
    def insert_enrichment_observations(self, observations: Sequence[EnrichmentObservationRecord]) -> None: ...
    def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None: ...
    def get_run(self, run_id: str) -> Optional[RunRecord]: ...
    def iter_raw_discovery_observations(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservationRecord]: ...
    def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
    def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]: ...
    def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...
```

```python
DDL_STATEMENTS: tuple[str, ...]              # 5 CREATE TABLE + 1 CREATE INDEX
CREATE_TABLE_STATEMENTS: dict[str, str]      # table name -> CREATE TABLE string
TABLE_COLUMNS: dict[str, tuple[str, ...]]    # table name -> column names, in order
TABLE_PRIMARY_KEYS: dict[str, tuple[str, ...]]
TABLE_INDEXES: dict[str, tuple[str, ...]]    # index name -> CREATE INDEX string
```

Table primary keys (interface file lines 346–357):

| Table | Primary key |
|---|---|
| `runs` | `run_id` |
| `raw_discovery_observations` | `observation_id` |
| `sample_members` | `(run_id, category, asset_identity_key)` |
| `enrichment_observations` | `(run_id, asset_identity_key)` |
| `category_scores` | `(run_id, category)` |

Index: `idx_raw_discovery_observations_run_category_ordinal` on
`raw_discovery_observations (run_id, category, discovery_ordinal)`.
"Column types use `TEXT`/`INTEGER`/`REAL`; UTC fields are `TEXT` ISO-8601. The
module validates its own specification at import (`_validate_specification`), so
a drift between DDL text, `TABLE_COLUMNS`, and `TABLE_PRIMARY_KEYS` fails fast."
The DDL already declares `FOREIGN KEY (run_id) REFERENCES runs (run_id)` on the
four child tables and `NOT NULL` on the columns listed as non-nullable;
`asset_identity_key` and `stratum_index` on `raw_discovery_observations` and
`product_page_views` on `enrichment_observations` are nullable exactly as the
DDL shows.

### 4.2 Frozen record dataclasses (`niche_scout.models`, interface file §4.1 lines 178–215; plan §5.3 lines 290–428)

All are `@dataclass(frozen=True)` on a private UTC-validating base that rejects
naive datetimes. Field names and order are frozen; status/state fields are
stored as `str` (the enum `value`). Exact declaration (plan §5.3):

```python
@dataclass(frozen=True)
class RunRecord:
    run_id: str
    run_started_at_utc: datetime
    scoring_cutoff_utc: Optional[datetime]
    completed_at_utc: Optional[datetime]
    categories_json: str
    config_snapshot_json: str
    config_sha256: str
    taxonomy_version: str
    taxonomy_captured_at_utc: datetime
    taxonomy_sha256: str
    endpoint_contract_version: str
    identity_mapping_rule_version: str
    sampling_rule_version: str
    page_view_semantics_status: str
    graphql_operation_correlation_mode: str
    identity_preflight_status: str
    identity_preflight_summary_json: str
    status: str

@dataclass(frozen=True)
class RawDiscoveryObservationRecord:
    observation_id: str
    run_id: str
    category: str
    discovery_ordinal: int
    asset_identity_key: Optional[str]
    identity_candidates_json: str
    identity_resolution_status: str
    identity_resolution_reason: Optional[str]
    category_value_json: str
    category_filter_validation_status: str
    stratum_index: Optional[int]
    is_duplicate: bool
    duplicate_of_observation_id: Optional[str]
    request_metadata_json: str
    error_summary_json: Optional[str]
    retrieved_at_utc: datetime

@dataclass(frozen=True)
class SampleMemberRecord:
    run_id: str
    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    sample_rank_within_stratum: int
    sample_is_census: bool
    selection_digest: str
    overlap_category_count: int
    overlap_sample_percentage: Optional[float]
    preflight_selected: bool

@dataclass(frozen=True)
class EnrichmentObservationRecord:
    run_id: str
    asset_identity_key: str
    product_detail_status: str
    page_views_status: str
    graphql_id: Optional[str]
    product_id: Optional[str]
    rating_average: Optional[float]
    rating_count: Optional[int]
    review_count: Optional[int]
    first_published_date_utc: Optional[datetime]
    publisher_json: Optional[str]
    category_json: Optional[str]
    state: Optional[str]
    product_page_views: Optional[int]
    id_mapping_mismatch: bool
    product_detail_error_summary: Optional[str]
    page_views_error_summary: Optional[str]
    request_metadata_json: str
    retrieved_at_utc: datetime

@dataclass(frozen=True)
class CategoryScoreRecord:
    run_id: str
    category: str
    discovery_status: str
    discovery_filter_verified: bool
    discovery_unresolved_identity_count: int
    discovery_conflict_count: int
    discovery_duplicate_count: int
    discovered_population_count: int
    enriched_sample_count: int
    sample_is_census: bool
    sampling_basis: str
    sample_fraction: Optional[float]
    unique_enrichment_count: int
    overlap_category_count: int
    overlap_sample_percentage: Optional[float]
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: str
    breadth_completeness_status: str
    discovery_bounded_by_verified_total: bool
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    demand_per_asset_raw: Optional[float]
    demand_median_raw: Optional[float]
    breadth_raw: Optional[float]
    recent_share_raw: Optional[float]
    median_age_raw: Optional[float]
    quality_raw: Optional[float]
    stratum_statistics_json: str
    component_d: Optional[float]
    component_c: Optional[float]
    component_r: Optional[float]
    component_q: Optional[float]
    market_opportunity_score: Optional[float]
    score_state: str
    evidence_grade: str
    rankability_status: str
    missing_components_json: str
    warnings_json: str
    reference_size: int
    reference_usable_counts_json: str
    top_3_stability: Optional[float]
    top_5_stability: Optional[float]
    maximum_score_delta: Optional[float]
    maximum_rank_displacement: Optional[int]
    sensitivity_warning: Optional[bool]
    ranking_sensitivity_json: str
    computed_at_utc: datetime
```

`CategoryScoreRecord` "Contains **no** duplicate alias columns such as
`sample_size`, `demand_usable_count`, `recent_supply_usable_count`, or
`quality_usable_count`." (interface file lines 210–212.)

### 4.3 Serialization helpers (`niche_scout.models`, interface file §4.2 lines 217–230)

```python
def to_json(instance: Any) -> str: ...
def to_json_dict(instance: Any) -> dict[str, Any]: ...
def from_json(payload: str, row_type: type[T]) -> T: ...
def ensure_utc(value: datetime) -> datetime: ...
```

- "Datetime fields serialize to ISO-8601 UTC and round-trip through
  `to_json`/`from_json` without precision loss."
- "`None` round-trips as `None`; it is never coerced to `0`/`""`."
- "`from_json` validates that the payload is an object of the expected record
  type and that UTC fields remain timezone-aware."

### 4.4 Enums and status strings persisted as TEXT (interface file §2, lines 55–103; source `models.py`)

```python
class RunStatus(str, Enum):                        # running | completed | failed
class DiscoveryStatus(str, Enum):                  # complete | truncated | page_failed | filter_unverified
                                                   # | category_mismatch | identity_incomplete | request_failed
class IdentityResolutionStatus(str, Enum):         # resolved | unresolved | conflict
class OperationStatus(str, Enum):                  # success | error
class PageViewSemanticsStatus(str, Enum):          # unvalidated | validated_cumulative | contradicted
class GraphQLOperationCorrelationMode(str, Enum):  # explicit_key | validated_position
class IdentityPreflightStatus(str, Enum):          # passed | failed | insufficient
class BreadthSource(str, Enum):                    # verified_total_count | distinct_canonical_discovered_count
class BreadthCompletenessStatus(str, Enum):        # complete | incomplete_estimate
class SamplingBasis(str, Enum):                    # census | deterministic_stratified_sample
class ScoreState(str, Enum):                       # available | partial | unavailable
class EvidenceGrade(str, Enum):                    # strong | moderate | weak | insufficient
class RankabilityStatus(str, Enum):                # not_rankable | provisional | rankable
class CategoryStatus(str, Enum):                   # healthy | degraded | failed
class CategoryFilterValidationStatus(str, Enum):   # verified | mismatch | unverified
```

`CategoryStatus` "is internal orchestration state; it is never surfaced as a
discovery status, score state, evidence grade, or rankability status."

`LREQ-GQL-060`'s `resolved` values and the `DiscoveryStatus` list are the values
this chunk must round-trip; it does not act on them.

### 4.5 Constants this chunk may cite (interface file §3, lines 107–168)

`SCHEMA_VERSION = "1.0.0"` (persistence); `MIN_USABLE_SAMPLES_PER_STRATUM = 5`
and `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100` / `SAMPLE_STRATA = 4` /
`SAMPLE_PER_STRATUM = 25` are read-only context for tests that build sample
fixtures. Chunk 2 SHALL NOT redefine or add constants.

### 4.6 Verification tooling (interface file §8, lines 432–479)

- `python -m niche_scout.tools.check_import_boundaries` → exit 0, prints
  `Import boundaries valid for metrics.py, scoring.py`.
- `python -m niche_scout.tools.validate_traceability` → exit 0. Its docstring
  states "Chunk 0 intentionally checks its own seven requirements only; later
  chunks widen the required set as their requirements become testable." It is
  hard-wired to Chunk 0's requirement block, so it validates the matrix
  globally (unknown IDs, marker/matrix mismatch, marker without matrix entry,
  orphan nodes) but does **not** enumerate Chunk 2's requirements. Its
  completeness direction (every individual LREQ has at least one mapped test)
  therefore does not cover Chunk 2; the marker-without-entry direction does.
  Section 10 records the consequence. Note that `validate_traceability.py` cites
  nothing at a line number in this plan; the tool's own source is not read here.
- `tests/fixtures/config_fixtures.py` exports `DEFAULT_CATEGORIES` (eight
  canonical category paths), TOML bodies, CLI override dicts, and mock
  environment mappings. It contains no persistence fixtures.

## 5. Interface contract this chunk produces

This section is written to become `Documents/interfaces/chunk-02.md` verbatim
when frozen. Everything below is public: downstream chunks may depend on these
names and semantics and SHALL NOT redefine them.

### 5.1 Module ownership

`src/niche_scout/database.py` remains the only module in this chunk. It is an
I/O module: it may import `sqlite3`, `logging` only for module-private debug
diagnostics that carry no record content, and `pathlib`. It SHALL NOT be
imported by `metrics.py` or `scoring.py` (enforced by
`check_import_boundaries`).

### 5.2 Public names added to `src/niche_scout/database.py`

```python
SCHEMA_VERSION: str                       # unchanged, frozen at "1.0.0"

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
```

Exception semantics:

| Condition | Exception | Notes |
|---|---|---|
| Duplicate `(run_id, category, asset_identity_key)` in `sample_members` | `UniqueConstraintViolation` | Message is generic: it names the table and the key column names only, never the identity value. |
| Duplicate `(run_id, category)` in `category_scores` | `UniqueConstraintViolation` | Insert path raises; upsert path must be requested explicitly (5.9). |
| Duplicate `run_id` in `runs` | `UniqueConstraintViolation` | Same rule. |
| Duplicate `(run_id, asset_identity_key)` in `enrichment_observations` | `UniqueConstraintViolation` | Same rule. |
| Duplicate `observation_id` in `raw_discovery_observations` | `UniqueConstraintViolation` | Same rule. |
| Child row for an unknown `run_id` | `ForeignKeyConstraintViolation` | Requires `foreign_keys = ON` (5.4). |
| Non-UTC / naive datetime reaching a UTC column | `InvalidRecordValueError` | Records already reject naive datetimes (`_UtcRecord`); this is the defensive second line. |
| Enum-backed column given a value outside its allowed set | `InvalidRecordValueError` | Allowed sets are exactly the interface file §2 values (section 6.7). |
| Any method after `close()` | `ClosedRepositoryError` | Never a silent no-op. |
| Metastore `schema_version` mismatch with `SCHEMA_VERSION` | `SchemaVersionError` | Raised by `initialize_schema` (5.5). |

All exceptions derive from `DatabaseError`; a caller may catch
`DatabaseError` to handle any persistence problem, and the exception `str()`
SHALL not contain record values, identities, or JSON payloads.

### 5.3 Construction, connection, and lifecycle

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

    @property
    def db_path(self) -> Path: ...
    @property
    def schema_version(self) -> str: ...
    @property
    def is_closed(self) -> bool: ...
    @property
    def connection(self) -> sqlite3.Connection: ...   # escape hatch for read-only diagnostics; never for writes by other chunks

    def close(self) -> None: ...
    def __enter__(self) -> "SqliteRepository": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...   # always closes; never swallows an exception

    @classmethod
    def connect(
        cls,
        db_path: "Path | str",
        *,
        initialize: bool = True,
        busy_timeout_ms: int = 5000,
        synchronous: str = "NORMAL",
        create_parent_directory: bool = True,
    ) -> "SqliteRepository": ...
```

- `__init__` opens the connection immediately, applies pragmas, and (when
  `initialize=True`) calls `initialize_schema()`. It SHALL NOT execute any DDL
  at *import* time (module import stays side-effect free apart from the existing
  `_validate_specification()`).
- `create_parent_directory=True` creates the database file's parent directory
  with `pathlib.Path.mkdir(parents=True, exist_ok=True)`; `db_path` may be
  `"file::memory:?cache=shared"`-style URI only if the caller passes
  `uri=True` — out of scope for v1, tests use `tmp_path`.
- `close()` is idempotent; a second call is a no-op.
- The same connection SHALL be reused for every method on one instance; nested
  `with` use of the instance is not supported (single-thread, single-connection;
  see 5.7 and section 12 Q5, closed by human decision).
- `SqliteRepository` satisfies the frozen `Repository` protocol structurally.
  The protocol SHALL NOT be re-declared, subclassed into a second protocol, or
  edited.

### 5.4 Connection pragmas (applied on every connection, in this order)

These four pragmas are **implementation choices** made by this chunk. No
requirement in `Documents/SRS-lean.md` or
`Documents/requirements-dependency-map.md` names a pragma, a journal mode, or a
concurrency behavior; the "Purpose" column below therefore states what each
pragma does operationally, not what a requirement demands.

| Pragma | Value | Purpose |
|---|---|---|
| `PRAGMA foreign_keys = ON` | `ON` | Makes the DDL's `REFERENCES runs (run_id)` clauses enforced, so orphan child rows raise `ForeignKeyConstraintViolation`. Required for this chunk's own declared constraint behavior. |
| `PRAGMA journal_mode = WAL` | `WAL`, result value verified and asserted by the implementation | Local implementation choice for the rollback-journal mode: writes are append-oriented to the write-ahead log and a crash mid-write leaves prior commits intact. No requirement in the source documents calls for a particular journal mode; this is not a concurrent-read design. |
| `PRAGMA busy_timeout = <busy_timeout_ms>` | default `5000` | Local implementation choice bounding how long a writer waits for a lock before raising `SQLITE_BUSY`. It makes a lock conflict a bounded delay instead of an immediate failure. No requirement in the source documents mandates lock-wait behavior. |
| `PRAGMA synchronous = NORMAL` | `NORMAL` (or the caller's value) | Local implementation choice for durability versus fsync cost; acceptable because the database is a local audit trail that is re-creatable by a rerun. |

`foreign_keys` SHALL be set per connection, because SQLite does not persist it
in the file. `initialize_schema` SHALL verify that `foreign_keys` is `1` and
raise `DatabaseError` if it is not.

The repository instance is single-thread and single-connection (5.7). The
`journal_mode` and `busy_timeout` pragmas are not justified here by any
concurrent-reader requirement: the dependency map's runtime order places report
and dashboard reads downstream of `Pipeline result persistence → report read
model` (dependency map §2, line 352), i.e. after a run reaches `completed` or
`failed`, so no document describes reading the database during a run's writes.

### 5.5 Schema initialization and migration

```python
def initialize_schema(self, *, check_version: bool = True) -> str: ...
```

- Creates a private metastore table if absent:
  `CREATE TABLE IF NOT EXISTS schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)`
  holding `("schema_version", SCHEMA_VERSION)` and `("applied_at_utc", <ISO-8601 UTC>)`.
  This table is **not** one of the five SRS tables, is not exposed through
  `TABLE_COLUMNS`/`TABLE_PRIMARY_KEYS`/`TABLE_INDEXES`, and is documented here
  so downstream chunks do not treat it as a data table.
- Applies `DDL_STATEMENTS` in order, using `CREATE TABLE IF NOT EXISTS`-safe
  semantics: an existing table with the same name is left untouched.
- If `schema_metadata.schema_version` exists and differs from `SCHEMA_VERSION`:
  raise `SchemaVersionError` (never migrate silently, never delete data).
- Returns `SCHEMA_VERSION` on success.
- Running `initialize_schema` twice on the same file is a no-op and returns the
  same version.
- **No `ALTER TABLE`, no column additions, no destructive migration in v1.**
  Any future version bump is a separate coordination task.

### 5.6 Streaming raw-observation persistence (LREQ-NFR-010 persistence support)

```python
def insert_raw_discovery_observations(
    self, observations: Sequence[RawDiscoveryObservationRecord]
) -> None: ...                     # frozen protocol method; batch convenience

def append_raw_discovery_observations(
    self,
    observations: "Iterable[RawDiscoveryObservationRecord]",
    *,
    batch_size: int = 500,
) -> int: ...                      # streamed sink; returns the number of rows written

def stream_raw_discovery_observations(
    self, run_id: str
) -> "Iterator[RawDiscoveryObservationRecord]": ...   # re-export of the protocol iterator
```

- The only row type in this section is `RawDiscoveryObservationRecord`, the
  frozen Chunk 0 dataclass (`Documents/interfaces/chunk-00.md` §4.1 lines
  187–193; declared in full in section 4.2). No alias name exists for it.
- `append_raw_discovery_observations` consumes the iterable **incrementally**:
  it reads at most `batch_size` records into memory, calls
  `executemany` for that batch, then continues. It never calls `list()` on the
  argument and never builds a second full-size container. `batch_size` must be
  `>= 1`; otherwise `ValueError`.
- `append_raw_discovery_observations` SHALL only be called from inside an
  active `category_transaction(run_id, category)` block. Called outside one it
  raises `RepositoryError` before consuming the iterable; it does not open a
  transaction of its own, because category isolation is the caller's
  declaration, not something the sink may infer from the records.
- Each batch is written inside its own savepoint inside that category's
  transaction (5.7). A mid-stream failure therefore unwinds only that
  category's savepoint: batches already released inside the same category stay
  in effect, sibling categories are untouched, and the pre-existing run rows
  remain committed. The failure raises `DatabaseError` naming the record count,
  not the record content.
- `insert_raw_discovery_observations` is exactly
  `append_raw_discovery_observations(observations, batch_size=len(observations) or 1)`
  semantics-wise; it exists only so the frozen protocol signature is satisfied,
  and it carries the same inside-`category_transaction` precondition.
- `stream_raw_discovery_observations(run_id, category)` returns records ordered
  by `discovery_ordinal` ascending, then `observation_id` ascending. The
  iterator is lazy and fetches rows in a fetch-many loop; it SHALL not be used
  by other chunks to mutate the database.

### 5.7 Transactions, savepoints, and category isolation

```python
from contextlib import contextmanager

@contextmanager
def transaction(self) -> Iterator["SqliteRepository"]:
    """Outermost transaction. Commits on clean exit, rolls back on exception."""

@contextmanager
def savepoint(self, name: str) -> Iterator["SqliteRepository"]:
    """Nested SAVEPOINT <name>. RELEASE on clean exit, ROLLBACK TO on exception."""

@contextmanager
def category_transaction(self, run_id: str, category: str) -> Iterator["SqliteRepository"]:
    """Category-isolated unit of work. See isolation rules below."""

def in_category_transaction(self) -> bool: ...
    """True while this instance is inside an active category_transaction block."""
```

Isolation rules (the observable guarantee, not the mechanism):

- A failure raised inside `category_transaction(run_id, category)` rolls back
  only the observations written inside that block for that category. Rows for
  other categories, and rows for the same run written before the block, remain
  committed. Re-raising the original exception is the intended use. This is the
  mechanism behind the Gate line "A failed category does not roll back
  unrelated category observations."
- `category_transaction` may be nested inside `transaction`; it uses a savepoint
  when a transaction is already open and a plain transaction otherwise.
- Inside a category block, `append_raw_discovery_observations` and
  `insert_raw_discovery_observations` wrap **each `batch_size` batch in its own
  savepoint** (named from the category, with a monotonically increasing
  suffix). A batch failure rolls back to the start of the failing batch only,
  then propagates, so the enclosing `category_transaction` unwinds that
  category alone. Batches already released stay in effect for the same
  category, and no other category is involved.
- `append_raw_discovery_observations` outside an active
  `category_transaction` raises `RepositoryError` (5.6). `in_category_transaction()`
  is the public predicate downstream chunks may consult; it reads instance
  state only and never the database.
- Savepoint names are generated from the category when the caller does not
  supply one; a supplied name must match `[A-Za-z_][A-Za-z0-9_]*` or
  `ValueError` is raised (SQLite cannot parameterize savepoint names).
- `transaction`/`savepoint` are re-entrant only through `savepoint`; opening a
  second outer `transaction` on the same instance raises `RepositoryError`.
- One `SqliteRepository` instance is single-thread, single-connection. The
  instance reuses one `sqlite3.Connection` for every method and provides no
  thread-sharing, pool, or re-entrancy guarantee beyond savepoint nesting.
  (Chunk 2 Plan Q5, resolved by human decision: no source document describes
  concurrent access to the database.)
- Uncommitted work SHALL never be visible to a second connection handling the
  same file; commit-on-clean-exit is the mechanism.

### 5.8 Status transition APIs

```python
# Frozen protocol method, now implemented:
def update_run_status(
    self, run_id: str, status: str, completed_at_utc: Optional[datetime] = None
) -> None: ...

# New:
def update_run_preflight(
    self,
    run_id: str,
    *,
    identity_preflight_status: Optional[str] = None,
    identity_preflight_summary_json: Optional[str] = None,
    graphql_operation_correlation_mode: Optional[str] = None,
    page_view_semantics_status: Optional[str] = None,
) -> None: ...

def set_category_status(
    self, run_id: str, category: str, discovery_status: str
) -> None: ...
```

- `update_run_status` accepts only `running`, `completed`, `failed`
  (`RunStatus`); any other value raises `InvalidRecordValueError`. It raises
  `KeyError` if `run_id` does not exist (a silent no-op would hide an
  orchestration bug).
- Passing `completed_at_utc=None` leaves the stored value unchanged; passing an
  aware UTC datetime sets it. It SHALL NOT read the clock (the caller supplies
  the value; LREQ-ARCH-020 discipline for orchestration code).
- `update_run_preflight` writes only the fields whose keyword is not `None`, so
  a caller can set preflight status and summary independently.
- `set_category_status(run_id, category, discovery_status)` **upserts into
  `category_scores`**: it writes `discovery_status` for that one
  `(run_id, category)` row and creates the row on first write if it does not
  exist yet, because discovery happens well before scoring and the row is
  populated incrementally over the run's lifetime rather than written once at
  the end. The insert half fills only the discovery-phase columns the caller
  can know at that time plus the frozen `NOT NULL` defaults required by the
  DDL; every scoring-phase column stays at its DDL default and is finalized
  later by `upsert_category_scores`. It never waits for a row that Chunks
  8/9/10 have not created yet, and it leaves every other `(run_id, category)`
  row untouched.
- Category-level failure has **no** dedicated persisted column. It is carried
  by the existing `category_scores.discovery_status`, `warnings_json`,
  `evidence_grade`, and `rankability_status`, per
  `Documents/requirements-dependency-map.md` §6.5 (lines 1174–1179) and the
  Chunk 10 Gate (line 1005). A standalone persisted `category_status` field
  would have to be added and documented as a schema change; Chunk 2 does not
  add one, and the frozen DDL has no such column.

### 5.9 Insert-versus-upsert semantics, per table

Insert semantics below are the **default** for every method; nothing upserts
silently.

| Table | Default method behavior | Explicit upsert path |
|---|---|---|
| `runs` | `insert_run` → plain `INSERT`; duplicate `run_id` raises `UniqueConstraintViolation`. | none (a corrected run must be a new `run_id`) |
| `raw_discovery_observations` | `insert_raw_discovery_observations` / `append_...` → plain `INSERT` on `observation_id`; duplicate raises `UniqueConstraintViolation`. | `update_raw_discovery_identity(observations: Iterable[RawDiscoveryObservationRecord]) -> int` — an `UPDATE ... SET asset_identity_key, stratum_index, is_duplicate, duplicate_of_observation_id WHERE observation_id = ?` by primary key. Only those four post-discovery columns are updatable; the caller must set `is_duplicate=True` and `duplicate_of_observation_id` for duplicate canonical records, which is how the `(run_id, category, discovery_ordinal)` index stays honest. |
| `sample_members` | `insert_sample_members` → plain `INSERT`; duplicate `(run_id, category, asset_identity_key)` raises `UniqueConstraintViolation`. **This is the gate bullet.** | `upsert_sample_members(members) -> int` — `INSERT ... ON CONFLICT (run_id, category, asset_identity_key) DO UPDATE SET` the summary columns (`stratum_index`, `stratum_start_ordinal`, `stratum_end_ordinal`, `sample_rank_within_stratum`, `sample_is_census`, `selection_digest`, `overlap_category_count`, `overlap_sample_percentage`, `preflight_selected`). Chunk 4B uses this to re-materialize corrected summaries; it cannot create a second membership. |
| `enrichment_observations` | `insert_enrichment_observations` → plain `INSERT`; duplicate `(run_id, asset_identity_key)` raises `UniqueConstraintViolation`. | `upsert_enrichment_observation(observation) -> None` — `ON CONFLICT (run_id, asset_identity_key) DO UPDATE SET` every non-key column. Chunk 6B uses this to record one identity's single enrichment and to store a post-enrichment correction; the primary key makes a second identity row impossible. |
| `category_scores` | `insert_category_scores` → plain `INSERT`; duplicate `(run_id, category)` raises `UniqueConstraintViolation`. **This is the gate bullet.** | `upsert_category_scores(scores) -> int` — `ON CONFLICT (run_id, category) DO UPDATE SET` every non-key column. Chunk 6B/Chunk 10 use this to finalize usable counts and sensitivity fields on an existing row. |

Column-by-column SQLite encoding:

- `bool` fields → `INTEGER` `0`/`1`; read back as `bool(0)`/`bool(1)`.
- `datetime` fields → `TEXT` ISO-8601 UTC; read back through the same
  serialization contract as `models.from_json` so UTC awareness is preserved.
- `Optional[...]` fields → SQL `NULL`; read back as `None`. **Never** as `0`,
  `0.0`, `""`, or `False`.
- JSON fields (`*_json`) → `TEXT` stored exactly as given; the repository does
  not re-serialize or normalize them.
- `int`/`float` fields → `INTEGER`/`REAL`.

### 5.10 Read APIs

All reads return the frozen dataclasses, reconstructed column-by-column (not by
echoing the input object) so a round trip is genuinely exercised:

```python
def get_run(self, run_id: str) -> Optional[RunRecord]: ...
def iter_raw_discovery_observations(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservationRecord]: ...
def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]: ...
def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...

# New, for orchestration and reporting convenience:
def count_raw_discovery_observations(self, run_id: str, category: str) -> int: ...
def count_distinct_enrichment_observations(self, run_id: str) -> int: ...
def count_discovery_observations(self, run_id: str) -> int: ...
def count_sample_members(self, run_id: str) -> int: ...
def count_distinct_enrichment_identities(self, run_id: str) -> int: ...

# Lifecycle predicate required by the streaming contract (5.6/5.7):
def in_category_transaction(self) -> bool: ...
```

- `count_discovery_observations(run_id)` is the run-wide discovered-canonical
  observation count. `count_sample_members(run_id)` is the run-wide sampled
  member count. `count_distinct_enrichment_identities(run_id)` is the run-wide
  count of distinct `asset_identity_key` values in `enrichment_observations`;
  because `(run_id, asset_identity_key)` is that table's primary key it equals
  the row count for the run, and it is named for the quantity
  `LREQ-NFR-020` counts rather than for the storage shape.
- These three are Chunk 2's actual supporting-contract obligation for
  `LREQ-NFR-020`: Chunk 6B's pre-enrichment log statement needs
  discovered-canonical, sampled, and unique-enrichment counts, and those counts
  can only be obtained by querying this chunk's own tables
  (`raw_discovery_observations`, `sample_members`,
  `enrichment_observations`). Chunk 2 still **does not log anything**; it
  supplies the read surface (see the section 3 `LREQ-NFR-020` row).
- `count_raw_discovery_observations(run_id, category)` and
  `count_distinct_enrichment_observations(run_id)` are the per-category and
  alternate-spelling helpers retained from the earlier draft; they remain public
  and are covered by the same test as the three run-wide counts.
- All `count_*` methods issue a single `SELECT count(...)`/`COUNT(DISTINCT ...)`
  and never materialize rows, so a caller can answer the pre-enrichment counts
  without loading or scanning whole tables into memory.

- Ordering: `iter_raw_discovery_observations` by `discovery_ordinal`, then
  `observation_id`; `get_sample_members` by `stratum_index`, then
  `sample_rank_within_stratum`; `get_category_scores` by `category`
  (lexical ascending, matching LREQ-SEN-020's deterministic tie-break order).
- `get_enrichment_observation` returns `None` when the identity is not present;
  a row with `product_page_views IS NULL` returns a record whose
  `product_page_views is None`.
- The `count_*` helpers exist so LREQ-NFR-020's counts (supporting chunk
  role) and the report read model can be answered without loading all rows;
  they are not the logging itself.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/database.py` | Modified | Keep the frozen `SCHEMA_VERSION`, DDL specification constants, and `Repository` protocol exactly as they are; add the physical SQLite implementation (`SqliteRepository`, pragmas, `initialize_schema`, streamed/batch/upsert insert paths, transactions and savepoints, category isolation, status transitions, read APIs, and the `DatabaseError` exception hierarchy). |
| `tests/test_database.py` | New | Analytical test module for every LREQ in section 3, using `tmp_path` SQLite files and fixtures built from the frozen dataclasses. |
| `tests/traceability.json` | Modified | Add the `tests/test_database.py` base node IDs produced in section 9, mapped 1:1 to section 3's LREQ IDs. |

No other file is in scope. If implementation appears to require a change to
`models.py`, `config.py`, `pyproject.toml`,
`src/niche_scout/tools/validate_traceability.py`, or the DDL/protocol constants
in `database.py`, that is section 12 Q3/Q4 (resolved: flag it, do not edit it).

## 7. Task breakdown

Ordered checklist, each item tagged with the LREQ ID(s) it implements.

- [ ] Add `DatabaseError`, `RepositoryError`, `ClosedRepositoryError`,
  `SchemaVersionError`, `UniqueConstraintViolation`,
  `ForeignKeyConstraintViolation`, `InvalidRecordValueError`, all with
  redaction-safe messages. (LREQ-SEC-020)
- [ ] Define the SQLite-to-record column-codec helpers: bool ⇄ INTEGER,
  aware-UTC datetime ⇄ ISO-8601 TEXT, `None` ⇄ `NULL`, JSON text passthrough,
  and the enum-value allow-list check per status column. (LREQ-SEC-020,
  LREQ-SMP-080)
- [ ] Implement `SqliteRepository.__init__`/`connect`/`close`/
  `__enter__`/`__exit__`/`is_closed`/`connection` with `pathlib.Path` handling
  and parent-directory creation, and raise `ClosedRepositoryError` from every
  method after `close()`. (LREQ-SEC-020, LREQ-NFR-010)
- [ ] Apply and verify the four pragmas (`foreign_keys`, `journal_mode`,
  `busy_timeout`, `synchronous`) on every connection, asserting
  `foreign_keys = 1` and the `journal_mode` result before any DDL.
  (LREQ-SMP-080, LREQ-GQL-080)
- [ ] Implement `initialize_schema` with the private `schema_metadata` table,
  ordered `DDL_STATEMENTS` execution, idempotent re-invocation, and
  `SchemaVersionError` on an unsupported existing version. (LREQ-SEC-020)
- [ ] Implement `insert_run` and `update_run_status` against the frozen
  signatures, with `RunStatus` validation and `completed_at_utc`
  leave-unchanged-on-`None` semantics. (LREQ-SEC-020)
- [ ] Implement `update_run_preflight` and `set_category_status` so preflight
  status/summary placement and a single category's discovery status can be
  written without touching unrelated rows. (LREQ-ID-010, LREQ-ID-020,
  LREQ-ID-040, LREQ-EXT-050, LREQ-EXT-090)
- [ ] Implement `append_raw_discovery_observations` as the streamed sink plus
  `insert_raw_discovery_observations` as the batch convenience that satisfies
  the frozen protocol, with `batch_size` validation. (LREQ-NFR-010,
  LREQ-EXT-050, LREQ-EXT-070, LREQ-EXT-090)
- [ ] Implement `update_raw_discovery_identity` for the post-discovery columns
  `asset_identity_key`, `stratum_index`, `is_duplicate`,
  `duplicate_of_observation_id`. (LREQ-EXT-050, LREQ-EXT-070, LREQ-EXT-090)
- [ ] Implement `insert_sample_members` as a plain insert whose primary key
  rejects duplicate membership, plus `upsert_sample_members` for
  re-materialized summary columns. (LREQ-SMP-080, LREQ-ID-010)
- [ ] Implement `insert_enrichment_observations` as a plain insert whose primary
  key enforces one row per `(run_id, asset_identity_key)`, plus
  `upsert_enrichment_observation`, preserving independently nullable
  per-operation fields so partial GraphQL success and a null
  `product_page_views` round-trip. (LREQ-GQL-080, LREQ-GQL-050, LREQ-ID-020)
- [ ] Implement `insert_category_scores` as a plain insert that enforces
  `(run_id, category)`, plus `upsert_category_scores` for finalization,
  including `reference_size`/`reference_usable_counts_json` and the five
  sensitivity columns with null-preserving behavior. (LREQ-NRM-020,
  LREQ-SEN-020, LREQ-RPT-020)
- [ ] Implement `transaction`, `savepoint`, and `category_transaction` with the
  documented isolation guarantee and the savepoint-name validation rule.
  (LREQ-SMP-080, LREQ-NFR-010)
- [ ] Implement the read APIs (`get_run`,
  `iter_raw_discovery_observations`, `get_sample_members`,
  `get_enrichment_observation`, `get_category_scores`,
  `count_raw_discovery_observations`,
  `count_distinct_enrichment_observations`) with `from_json`-equivalent
  reconstruction and the documented ordering. (LREQ-NFR-020, LREQ-RPT-020,
  LREQ-NRM-020, LREQ-GQL-050)
- [ ] Write `tests/test_database.py` covering every bullet in section 9, with
  record fixtures built from the frozen dataclasses and a `tmp_path` database
  per test. (LREQ-SEC-020, LREQ-SMP-080, LREQ-GQL-080, LREQ-NFR-010,
  LREQ-NFR-020, LREQ-EXT-050, LREQ-EXT-070, LREQ-EXT-090, LREQ-GQL-050,
  LREQ-ID-010, LREQ-ID-020, LREQ-ID-040, LREQ-NRM-020, LREQ-SEN-020,
  LREQ-RPT-020, LREQ-TST-080)
- [ ] Add the new base node IDs and their LREQ arrays to
  `tests/traceability.json`, and confirm no existing entry was reworded.
  (LREQ-TST-080)
- [ ] Run `python -m pytest tests/test_database.py`, `python -m pytest` (whole
  suite, to prove nothing upstream broke),
  `python -m niche_scout.tools.check_import_boundaries`, and
  `python -m niche_scout.tools.validate_traceability`; all must exit 0.
  (LREQ-SEC-020, LREQ-TST-080)

## 8. Edge cases and invariants

### 8.1 Dependency-map "Edge cases" column for every LREQ this chunk owns

| LREQ ID | Edge cases (dependency map, quoted) | Chunk 2's persistence-side assertion |
|---|---|---|
| LREQ-SEC-020 | "No secrets in source control, logs, SQLite, or errors; `.env` ignored" (line 182) | A record built with a token-shaped error summary is either written exactly as the caller redacted it or rejected by `InvalidRecordValueError`; no repository exception message contains a record value; a scan of every TEXT column after a full fixture run finds no credential-shaped substring. |
| LREQ-SMP-080 | "Chunk 4B materializes `sample_members`, summaries, per-stratum `N_h`, `n_h`, and usable-count fields/placeholders; census versus sample; overlap counts; sample fraction distinct from coverage" (line 204) | `sample_members` accepts both census and sampled rows with the same columns; `sample_fraction`, `overlap_sample_percentage`, and `overlap_category_count` survive the round trip; `sample_fraction` and eligibility coverage remain separate columns with separate values. |
| LREQ-GQL-080 | "Cross-category overlap; at most one enrichment execution per unique identity per run, including successful preflight reuse; bulk enrichment is blocked until the preflight gate passes" (line 175) | Two categories referencing one identity cannot produce two rows: the second plain insert raises `UniqueConstraintViolation`, and the upsert path overwrites the single existing row. Chunk 2 enforces no gate. |
| LREQ-NFR-010 | "Large discovery results must not require all responses in memory" (line 284) | `append_raw_discovery_observations` writes a generator of records without materializing it; a test asserts the sink works on a non-seekable, single-pass iterator. |
| LREQ-NFR-020 | "Log canonical count, sample count, unique enrichment count, and projected minimum time before enrichment" (line 285) | The four counts' inputs are answerable from `count_raw_discovery_observations`, `get_sample_members`, `count_distinct_enrichment_observations` without loading unrelated rows. |
| LREQ-EXT-050 | "Verified `totalCount`, natural terminal page, truncation, failed page, filter uncertainty, category mismatch, zero results" (line 157) | Each terminal state is a stored `discovery_status` string; a zero-result category is an empty observation set with a persisted status, never a fabricated zero-asset row. |
| LREQ-EXT-070 | "Conflicting candidates, unresolved candidates, exclusion from denominator and enrichment" (line 159) | `unresolved`/`conflict` rows persist with `asset_identity_key IS NULL` and their candidates JSON intact. |
| LREQ-EXT-090 | "Warning generation; competition not fully rankable; failed page must not become zero assets" (line 161) | A failed page's observation persists with `error_summary_json` present and no numeric substitution; the JSON `None`/absence distinction survives. |
| LREQ-GQL-050 | "Retain valid ProductDetail when page views fail, and vice versa" (line 172) | `product_detail_status` and `page_views_status` are independent columns; each combination round-trips. |
| LREQ-ID-010 | "At least 2 assets from 5 categories where possible; reduced coverage; categories with fewer than 2 assets" (line 188) | `preflight_selected` persists `False`/`True` per sample member; a category with fewer than two selected members is representable with no special casing. |
| LREQ-ID-020 | "Chunk 6A invokes the Chunk 5 adapter for every preflight identity and validates both operations; request ID rejection, incompatible returned identity, page-view package mismatch, invalid correlation mode, and either-operation partial success" (line 189) | Preflight-shaped `enrichment_observations` rows persist through the same upsert path, with both operation statuses and `request_metadata_json` correlation detail intact. |
| LREQ-ID-040 | "Zero attempted identities gives `insufficient`, failed preflight blocks bulk enrichment, successful results reused" (line 191) | `identity_preflight_status` persists `insufficient` as a distinct value from `failed`; `identity_preflight_summary_json` holds the rate summary with null rates where the SRS requires null. |
| LREQ-NRM-020 | "`category_count - 1`; field-specific usable counts; 21 categories means 20 peers" (line 227) | `reference_size = 20` for a 21-category run persists as `20`, and `reference_usable_counts_json` stays a separate column. |
| LREQ-SEN-020 | "Chunk 9B returns a complete typed diagnostic; Chunk 10 persists it; ranks only the fixed `base_rankable_candidates`; top 3/top 5, deterministic tie-breaking, null when too few candidates, rank and score displacement" (line 257) | `top_3_stability`/`top_5_stability`/`maximum_score_delta`/`maximum_rank_displacement`/`sensitivity_warning` are nullable columns; a null stability value round-trips as `NULL`, never `0.0`. |
| LREQ-RPT-020 | "All required score, coverage, sample, evidence, status, and sensitivity fields" (line 266) | Every column the primary table needs is present on the frozen records and readable through `get_category_scores`/`get_sample_members`. |
| LREQ-TST-080 | "Category validation, pagination, duplicates, overlap, sample, one enrichment per identity, partial GraphQL, SQLite, report" (line 304) | The SQLite clause is verifiable in isolation here; the full fixture is Chunk 13's. |

### 8.2 Invariants stated in the Chunk 2 gate/description and the interface contracts

- `product_page_views` is nullable and SHALL never use zero as an error
  sentinel: a failed PageViews operation stores `NULL`, and no code path
  substitutes `0`.
- No silent zero substitution anywhere: every nullable column reads back as
  `None`, and there is no `value or 0` / `value if value is not None else 0.0`
  pattern in the module.
- No duplicate alias columns in `category_scores`: `sample_size`,
  `demand_usable_count`, `recent_supply_usable_count`, and
  `quality_usable_count` SHALL NOT be added, and the persisted column set SHALL
  equal `TABLE_COLUMNS["category_scores"]` exactly.
- A failed category SHALL NOT roll back unrelated category observations.
- Duplicate sample membership SHALL be rejected by the primary key (not by a
  pre-INSERT `SELECT` only; the constraint is the enforcement point).
- `(run_id, category)` SHALL be enforced for `category_scores`.
- Secrets SHALL NOT be able to enter persisted records: no repository method
  accepts a credentials object, no pragma/URI carries a credential, and
  `DatabaseError` messages contain table/column names only.
- `page_view_semantics_status` SHALL be restricted to `unvalidated`,
  `validated_cumulative`, `contradicted`.
- Enum-backed columns SHALL be constrained to their allowed string values
  (the frozen interface file §2 values, reproduced in section 4.4):
  `status` (`RunStatus`), `discovery_status`
  (`DiscoveryStatus`), `identity_resolution_status`, `category_filter_validation_status`,
  `product_detail_status`/`page_views_status` (`OperationStatus`),
  `breadth_source`, `breadth_completeness_status`, `sampling_basis`,
  `score_state`, `evidence_grade`, `rankability_status`,
  `page_view_semantics_status`, `graphql_operation_correlation_mode`,
  `identity_preflight_status`.
- UTC datetime TEXT round-trip: every datetime column reads back
  timezone-aware UTC with identical instant, including through
  `completed_at_utc` and `scoring_cutoff_utc` which may be `NULL`.
- Raw observations are persisted before canonical populations or samples exist,
  so `asset_identity_key` and `stratum_index` are legitimately `NULL` during
  discovery and are filled later by the update path.
- No DDL or DML is executed at import time; `import niche_scout.database` opens
  no file and creates no database.
- Read-only freedom: no read API mutates state, and `iter_*` methods must
  remain safe to consume partially (an abandoned iterator must not hold a write
  lock — the implementation uses a distinct short-lived cursor/connection for
  the streaming read).

## 9. Test plan

### 9.1 Test file to create

- `tests/test_database.py` — new analytical module. No other test file changes.

### 9.2 Isolation and environment rules

- Every test obtains its database path from pytest's `tmp_path`; no
  repo-relative `runtime/*.sqlite3` file is created, and no test writes into the
  repository tree. A session-level guard (an autouse fixture asserting that
  `Path(tmp_path)` is under the pytest temp base) is recommended.
- Live network calls are forbidden; `tests/test_database.py` imports no
  network library. SQLite is local engine I/O only.
- Fixtures and golden values only; no production database is read.

### 9.3 Fixtures needed

| Fixture | Source | Contents |
|---|---|---|
| `run_record` | built from the frozen `RunRecord` | One `run_id`, aware-UTC `run_started_at_utc`, `scoring_cutoff_utc` both set and unset variants, `status="running"`, `page_view_semantics_status="unvalidated"`, `graphql_operation_correlation_mode="explicit_key"`, `identity_preflight_status="passed"`, `identity_preflight_summary_json` with the correlation metadata |
| `raw_observation_factory` | frozen `RawDiscoveryObservationRecord` | Variants: resolved identity, `unresolved` with `asset_identity_key=None`, `conflict`, `is_duplicate=True` with `duplicate_of_observation_id`, `error_summary_json` present, and a `category_filter_validation_status="mismatch"` row |
| `sample_member_factory` | frozen `SampleMemberRecord` | Census variant (`sample_is_census=True`), sampled variant across `stratum_index` 0–3, `overlap_sample_percentage=None` variant, `preflight_selected` both values |
| `enrichment_factory` | frozen `EnrichmentObservationRecord` | All four operation-status combinations; `product_page_views=None` variant; `page_views_error_summary` set; `rating_average=None`; `first_published_date_utc=None` |
| `category_score_factory` | frozen `CategoryScoreRecord` | Zero-population variant (`discovered_population_count=0`, `sample_fraction=None`), census variant, partial-score variant, null-sensitivity variant (`top_3_stability=None`), 21-category reference variant (`reference_size=20`) |
| `two_categories` | derived from `tests/fixtures/config_fixtures.py::DEFAULT_CATEGORIES` | The first two canonical category paths, so categories match the project config fixtures instead of inventing new strings |
| `credential_shaped_text` | hand-derived, fixture-only | Strings shaped like a bearer token and a CSRF cookie used **only** to assert they never appear in stored text or exception messages |

Reuse `tests/fixtures/config_fixtures.py` for category paths and for the
"no real credentials" discipline (`MOCK_ENVIRONMENT` values are
`fixture-coveo-token`/`fixture-csrf-token` placeholders). No new fixture module
is required; fixtures live inside `tests/test_database.py` to keep the file list
unchanged.

### 9.4 Required pytest LREQ markers and `tests/traceability.json` entries

Every marker below maps 1:1 to a row in section 3. Node IDs are the planned
base node IDs; parameterized tests are mapped by their base node ID.

| Planned base node ID | Marker(s) | Section 3 row |
|---|---|---|
| `tests/test_database.py::test_schema_initialization_is_versioned_and_idempotent` | `LREQ-SEC-020` | LREQ-SEC-020 |
| `tests/test_database.py::test_repository_never_persists_or_leaks_secrets` | `LREQ-SEC-020`, `LREQ-NFR-060` | LREQ-SEC-020 |
| `tests/test_database.py::test_duplicate_sample_membership_is_rejected` | `LREQ-SMP-080` | LREQ-SMP-080 |
| `tests/test_database.py::test_sample_member_round_trip_preserves_nullable_and_census_fields` | `LREQ-SMP-080` | LREQ-SMP-080 |
| `tests/test_database.py::test_at_most_one_enrichment_row_per_run_and_identity` | `LREQ-GQL-080`, `LREQ-TST-030` | LREQ-GQL-080 |
| `tests/test_database.py::test_streamed_raw_append_consumes_single_pass_iterable` | `LREQ-NFR-010` | LREQ-NFR-010 |
| `tests/test_database.py::test_pre_enrichment_counts_are_readable_without_full_scans` | `LREQ-NFR-020` | LREQ-NFR-020 |
| `tests/test_database.py::test_discovery_terminal_states_round_trip_without_zero_substitution` | `LREQ-EXT-050`, `LREQ-EXT-090` | LREQ-EXT-050, LREQ-EXT-090 |
| `tests/test_database.py::test_unresolved_and_conflicting_identities_persist_null_identity_key` | `LREQ-EXT-070` | LREQ-EXT-070 |
| `tests/test_database.py::test_partial_graphql_operation_success_is_stored_independently` | `LREQ-GQL-050` | LREQ-GQL-050 |
| `tests/test_database.py::test_preflight_selection_is_persisted_on_sample_members` | `LREQ-ID-010` | LREQ-ID-010 |
| `tests/test_database.py::test_preflight_observations_persist_both_operations_and_correlation_metadata` | `LREQ-ID-020` | LREQ-ID-020 |
| `tests/test_database.py::test_preflight_status_values_persist_distinctly` | `LREQ-ID-040` | LREQ-ID-040 |
| `tests/test_database.py::test_reference_size_and_usable_counts_persist_separately` | `LREQ-NRM-020` | LREQ-NRM-020 |
| `tests/test_database.py::test_null_sensitivity_diagnostics_round_trip_as_null` | `LREQ-SEN-020` | LREQ-SEN-020 |
| `tests/test_database.py::test_category_score_columns_cover_report_read_model` | `LREQ-RPT-020` | LREQ-RPT-020 |
| `tests/test_database.py::test_category_scores_primary_key_enforced` | `LREQ-SMP-080` | LREQ-SMP-080 (matrix `(run_id, category)` gate bullet) |
| `tests/test_database.py::test_category_isolation_preserves_unrelated_observations` | `LREQ-SMP-080`, `LREQ-EXT-090` | LREQ-SMP-080, LREQ-EXT-090 |
| `tests/test_database.py::test_foreign_key_and_pragma_contracts_are_enforced` | `LREQ-SEC-020`, `LREQ-GQL-080` | LREQ-SEC-020, LREQ-GQL-080 |
| `tests/test_database.py::test_json_and_utc_round_trip_for_all_record_types` | `LREQ-TST-080` | LREQ-TST-080 |
| `tests/test_database.py::test_insert_versus_upsert_semantics_per_table` | `LREQ-SMP-080`, `LREQ-GQL-080`, `LREQ-SEC-020` | LREQ-SMP-080, LREQ-GQL-080, LREQ-SEC-020 |
| `tests/test_database.py::test_enum_backed_columns_reject_unknown_values` | `LREQ-SEC-020`, `LREQ-ID-040` | LREQ-SEC-020, LREQ-ID-040 |
| `tests/test_database.py::test_no_alias_columns_and_no_import_time_ddl` | `LREQ-TST-080` | LREQ-TST-080 |

Notes:

- `LREQ-SEC-020` additionally needs a `LREQ-NFR-060` test reference, because the
  matrix's `Required tests` column for LREQ-SEC-020 is
  "LREQ-TST-080, LREQ-NFR-060" (dependency map line 69). It is attached to
  `test_repository_never_persists_or_leaks_secrets` as the redaction/secret-
  handling workflow check. `LREQ-NFR-060` itself is Chunk 13's requirement; this
  marker only supplies the required test reference and adds no new normative
  obligation to Chunk 2.
- `LREQ-GQL-080`'s matrix `Required tests` are "LREQ-TST-030, LREQ-TST-040,
  LREQ-TST-080" (line 67). Only `LREQ-TST-030` (identity fixture/unit tests,
  including "duplicate cross-category identities") is reachable from a
  persistence test; `LREQ-TST-040` is GraphQL protocol testing owned by
  Chunk 5's `test_collector.py`/`test_identity.py`. Attaching `LREQ-TST-040` to
  a database test would be a fabricated mapping, so it is recorded as a scoping
  note in section 12 Q6 instead.
- `LREQ-SMP-080`'s matrix `Required tests` are "LREQ-TST-020, LREQ-TST-080"
  (line 81). `LREQ-TST-020` is `tests/test_sampling.py`, owned by Chunks 4A/4B;
  the persistence half is covered by `LREQ-TST-080`, which Chunk 13 completes.
  Also recorded as a scoping note in section 12 Q6.
- `tests/traceability.json` gains one entry per row above, with values equal to
  the marker set exactly (the validator fails on marker/matrix mismatch). Every
  value array must list distinct `LREQ-*` strings that exist in SRS Appendix B
  ranges.
- `python -m pytest` must stay green across the whole repository: adding markers
  without matrix entries, or matrix entries without nodes, fails the validator.

### 9.5 Verification commands

- `python -m pytest tests/test_database.py` → all pass.
- `python -m pytest` → whole suite passes (proves `tests/test_contracts.py`
  and its traceability entries were not disturbed).
- `python -m niche_scout.tools.check_import_boundaries` → exit 0.
- `python -m niche_scout.tools.validate_traceability` → exit 0.

## 10. Definition of done (gate)

Copied **verbatim** from `Documents/requirements-dependency-map.md` Chunk 2
Gate (lines 510–518):

- Pure sampling and scoring functions do not import or require SQLite.
- Duplicate sample membership is rejected.
- `(run_id, category)` is enforced for category scores.
- Secrets cannot enter persisted records.
- A failed category does not roll back unrelated category observations.
- Streaming insertion APIs and category-isolated transactions/savepoints are available to Chunks 3, 4B, 6A, and 6B.
- Behavioral verification of sampling summaries, unique enrichment, streamed discovery, and collector/error redaction remains in Chunks 3, 4B, 6A, and 6B.

Project-wide gates that also apply to this chunk:

- `python -m niche_scout.tools.validate_traceability` exits 0.
- `python -m niche_scout.tools.check_import_boundaries` exits 0.

Traceability completeness direction for Chunk 2 (section 12 Q3(c)): because
`src/niche_scout/tools/validate_traceability.py` is still hard-wired to the
Chunk 0 requirement block and widening it is deferred to Chunk 13, the
validator's completeness check does not yet cover Chunk 2. The Chunk 2
completeness direction is therefore established by a **manual cross-check** of
section 3's LREQ table against the actual `@pytest.mark.lreq` markers in
`tests/test_database.py` and the corresponding `tests/traceability.json`
entries in the working tree — every section 3 LREQ ID SHALL have at least one
mapped marker and traceability entry. The validator's marker-without-entry
direction still runs (`validate_traceability` continues to fail on a marker
with no matrix entry).

## 11. Explicit prohibitions

- **No SQLite import in pure modules**: `src/niche_scout/metrics.py` and
  `src/niche_scout/scoring.py` SHALL not import `sqlite3`, `database`, or any
  other I/O module; `check_import_boundaries` must keep exiting 0.
- **No changes to the frozen Chunk 0 contract**: the five record dataclasses,
  every enum and status type, all constants and policy versions, `SCHEMA_VERSION`,
  `DDL_STATEMENTS`, `CREATE_TABLE_STATEMENTS`, `TABLE_COLUMNS`,
  `TABLE_PRIMARY_KEYS`, `TABLE_INDEXES`, and every existing `Repository`
  protocol method signature SHALL NOT be modified, renamed, removed, or
  overloaded. New methods are additive only.
- **No derived SQLite implementation**: `SqliteRepository` SHALL not subclass,
  stub, or shadow `Repository`; it satisfies it structurally.
- **No network**: no HTTP client, socket, or URL handling; no dependency on
  `collector*`, `pipeline`, `report`, or `cli`.
- **No clock reads added to pure modules**: `metrics.py` and `scoring.py`
  continue to receive `scoring_cutoff_utc` explicitly, and this chunk does not
  add any `datetime.now()`/`time.time()` call anywhere in the pure boundary.
  Repository methods that need "now" for a `*_at_utc` column SHALL take the
  value from the caller.
- **No secrets persisted or logged**: no repository method accepts a
  credentials object or a connection URI containing a token; no exception
  message, debug log, or `repr` emitted by this module contains a record value,
  a header, or an identity string; `PRAGMA` output and SQL text SHALL not be
  logged with bound parameters.
- **No DDL/DML at import time**: importing `niche_scout.database` SHALL not open
  a connection, create a file, or execute SQL. The only permitted import-time
  side effect is the pre-existing `_validate_specification()`.
- **No schema invention**: no new table, no new column, no `ALTER TABLE`, no
  hardening beyond the matrix's required constraints, no index beyond the frozen
  one (plus the private `schema_metadata` table documented in section 5.5).
- **No chunk-crossing behavior**: no collector streaming or redaction
  (Chunk 3), no sampling materialization, overlap computation, or
  pending-placeholder policy (Chunk 4B), no preflight selection or gate
  decision (Chunk 6A), no unique-enrichment deduplication, response reuse, or
  projection logging (Chunk 6B), no orchestration status policy (Chunk 10), no
  report rendering or read-model shaping (Chunk 11).
- **No silent mutation of committed data**: no repository method deletes rows,
  drops tables, or rewrites a committed category's observations as a side effect
  of another category's failure.
- **No zero substitution**: no code path converts `None`/missing/invalid data to
  `0`, `0.0`, `""`, or `False` on write or on read.

## 12. Resolved decisions (closed)

Status: **closed.** Every item below was resolved by explicit human decision.
No open questions remain, and this section no longer blocks freeze. Each
decision is final: it is not to be re-opened, softened, or supplemented with a
new open question.

**Q1 — Streamed insertion API shape. CLOSED, FINAL.** The streamed sink is the
plain iterable-consuming method
`append_raw_discovery_observations(observations: Iterable[RawDiscoveryObservationRecord], *, batch_size: int = 500) -> int`
(section 5.6), which composes with Chunk 3's generator and requires no
ownership inversion. It SHALL raise if called outside an active
`category_transaction(run_id, category)` block (5.6/5.7). Mechanism for the
Gate bullet "A failed category does not roll back unrelated category
observations": each batch is written inside its own savepoint inside that
category's own transaction, so a mid-stream failure unwinds only that
category's savepoint — sibling categories and already-committed run rows are
untouched.

**Q2 — Category-isolated transaction surface, and what is isolated. CLOSED,
FINAL.** There is no new persisted `category_status` enum and no new
`category_status` column. The dependency map says `CategoryStatus` "is not a
separate persisted enum unless the schema explicitly adds that field"
(`Documents/requirements-dependency-map.md` line 1005, Chunk 10 Gate), and §6.5
(lines 1174–1179) states that category-level failure is represented through
`discovery_status`, warnings, `evidence_grade`, and `rankability_status`. This
plan therefore records a category failure through the existing
`discovery_status` field on `category_scores`, plus `warnings_json`,
`evidence_grade`, and `rankability_status`.
`set_category_status(run_id, category, discovery_status)` SHALL **upsert into
`category_scores`**, creating the row on first write if it does not yet exist,
because discovery precedes scoring and the row is populated incrementally over
the run's lifetime (the SRS §6.5 field order — discovery-phase fields first,
`computed_at_utc` last — reflects that). It SHALL NOT wait for a row that
Chunks 8/9/10 have not created yet. A standalone `category_status` column is
reserved for the case where this proves genuinely insufficient, and then it must
be added and documented, not assumed.

Clarification of this closed decision (added by Chunk 2 implementation; Q2 stays
CLOSED and is not re-opened): the frozen
`CategoryScoreRecord.computed_at_utc` in `models.py` is a **non-optional**
`datetime`, so a `category_scores` row cannot be written without a timestamp and
then read back as that frozen record. `set_category_status` therefore takes a
keyword-only `computed_at_utc` and requires the caller to supply it: when it is
`None` the method raises `InvalidRecordValueError` and writes nothing, because
section 11 forbids this chunk from reading the system clock for any `*_at_utc`
column. The upsert still creates the row on first write, and a conflicting
`(run_id, category)` update always assigns the supplied value — there is no path
that overwrites an already-scored row's timestamp with `NULL`. The DDL is
unchanged: `computed_at_utc TEXT NOT NULL` stays as frozen, and its column is now
bound by this method rather than filled with an implicit `NULL`.

**Q3 — `tests/traceability.json` versus the validator. CLOSED, FINAL, two
parts plus a consequence.** (a) Modifying `tests/traceability.json` IS normal,
expected Chunk 2 work: Chunk 0 designed it to be appended to per-chunk, so
adding this chunk's entries widens nothing. It stays in the section 6 file
list. (b) Widening `validate_traceability.py`'s hardcoded Chunk 0 scope check
(`chunk_requirements(text, chunk="0")`) is a different matter and stays
**deferred to Chunk 13**, the same call as Chunk 1's equivalent question; the
tool file is NOT in the section 6 file list. (c) Consequence, recorded in
section 10: the Chunk 2 completeness direction is established by a **manual
cross-check** of section 3's LREQ table against the actual
`@pytest.mark.lreq` markers and `tests/traceability.json` entries in the working
tree, because the validator's completeness check does not yet cover Chunk 2.
The validator's marker-without-entry direction still runs.

**Q4 — Where `LREQ-NFR-020`'s logging lives. CLOSED, FINAL.** No logging in
`database.py`; that is correctly out of scope, per the SRS `Module` column,
which names `pipeline.py`/`collector.py` (dependency map line 285). Chunk 2's
supporting-contract obligation for `LREQ-NFR-020` is not logging: it is the
count/read query surface exposed in section 5.10 —
`count_discovery_observations(run_id)`, `count_sample_members(run_id)`, and
`count_distinct_enrichment_identities(run_id)` — which Chunk 6B's pre-enrichment
log statement calls, because the three counted quantities can only be obtained
by querying this chunk's own tables. Chunk 2 supplies the reads; Chunk 6B emits
the log line.

**Q5 — Re-entrancy and threading. CLOSED, FINAL.** The concurrency premise is
withdrawn: no source document states any requirement about threading,
concurrency, WAL, or pragmas. There is no requirement describing concurrent
access, and the dependency graph places report/dashboard reads downstream of
`Pipeline result persistence → report read model` — i.e. after a run is
`completed` or `failed`, not during it. The final answer is **single-thread,
single-connection, savepoint-only nesting** (5.3, 5.7). The §5.4 pragma
justifications that cited concurrent readers have been re-worded: `journal_mode`
and `busy_timeout` are presented as local implementation choices, not as
requirement-driven, and no requirement was invented to justify them. If a
live-progress-while-running dashboard ever becomes a real requirement, that is a
new SRS line item to write, not something to design around speculatively now.

**Q6 — Test references Chunk 2 cannot honestly own. CLOSED as a scoping note.**
`LREQ-TST-040` (GraphQL protocol tests, `test_collector.py`/`test_identity.py`)
and `LREQ-TST-020` (`test_sampling.py`) are scoped to files Chunk 2 has no
business writing to. Section 9.4 therefore keeps attaching only the
persistence-side evidence and records the remaining references here rather than
fabricating mappings. Full closure of `LREQ-GQL-080`/`LREQ-SMP-080`'s required
test set happens only once Chunks 5 and 4A/4B land, which the deferred-to-Chunk
13 validator eventually confirms in aggregate. The Chunk 2 gate is therefore not
read as failing on a test reference it cannot own.

**Q7 — `Blocks` set. CLOSED, FINAL.** `Blocks` = Chunks 3, 4B, 6A, 6B, 10, 11.
Chunk 3 declares it explicitly ("streaming observation emission into the Chunk 2
persistence API"); 4B, 6A, 6B, 10, and 11 all write to or read from
Chunk-2-owned tables even where they do not name it directly — 4B's own gate
requires a "database round trip," 6B is a supporting chunk on `LREQ-NFR-020`
which needs Chunk 2's query surface (Q4), 10 orchestrates the whole persisted
run, and 11 reads `category_scores`/`runs` read-only. Chunk 13 depends on
everything trivially and needs no separate mention.

### 12.1 False claims removed

Two claims that appeared in an earlier draft were checked against the source
documents and found to be false; both are deleted and MUST NOT be reinstated.

- **`LREQ-SEC-020` is NOT absent from Chunk 2's "Supporting contracts" list.**
  It is present at `Documents/requirements-dependency-map.md` line 508:
  `- persistence support for LREQ-SEC-020` (within the Chunk 2 section, lines
  503–508).
- **`LREQ-ADM-010` does not exist.** A case-insensitive search for `ADM` across
  `Documents/` returns zero requirement-ID matches (the only matches are the
  `README.md` filename in directory trees), and no `LREQ-ADM-*` identifier is
  defined in `Documents/SRS-lean.md` Appendix B or in the ownership matrix. Any
  statement about an `LREQ-ADM-010` gap is a fabricated citation and is
  discarded.

### 12.2 Q2-style clarification — the coordinated transaction-mechanism repair

**Added by Chunk 2 implementation. Q2 stays CLOSED and is NOT re-opened.** This
entry follows the section 12 convention established by the subsection directly
above it: it is a clarification *added by Chunk 2 implementation*, not a new
question and not a re-opening of Q2. It records the coordinated repair that the
implementation pass applied to this chunk's own module, so that a reader
comparing `src/niche_scout/database.py` against the frozen plan can see *where*
the decision came from instead of discovering the divergence by reading source.

**It is a post-hoc repair decision, recorded after the fact.** It is **NOT** a
pre-existing frozen decision, and it must not be read as authorization by
hindsight: nothing in sections 5.3, 5.4, or 5.7 approved these mechanisms before
they were written, because these mechanisms did not exist when those sections
were frozen. The record below states why each was chosen; it is not a claim that
the choice was pre-approved.

**Section 11's "no changes to the frozen contract" claim is not falsified by
this amendment, because no published signature moved.** Section 11 (lines
1116–1121) freezes the five record dataclasses, the enums and constants,
`SCHEMA_VERSION`, `DDL_STATEMENTS`, `CREATE_TABLE_STATEMENTS`, `TABLE_COLUMNS`,
`TABLE_PRIMARY_KEYS`, `TABLE_INDEXES`, and every existing `Repository` protocol
method signature. Every one of those is untouched by this amendment. Nothing in
sections 5.2, 5.3, 5.5, 5.6, 5.8, 5.9, or 5.10 is amended here either; the
repair is internal to the module. Section 5.7 already promises only "the
observable guarantee, not the mechanism" (line 661) and already permits
`category_transaction` to use "a savepoint when a transaction is already open and
a plain transaction otherwise" (lines 669–670), so the mechanism choice recorded
below falls inside the freedom 5.7 already granted.

The five items below (with item 6 appended by a later Chunk 2 pass), with the
section each one lands under:

1. **`sqlite3.connect` no longer passes `isolation_level`; pysqlite's default
   (`isolation_level=""`) is used.** Section 5.3's published constructor
   signature (lines 492–502) is unchanged — `isolation_level` was never a
   parameter and still is not one. The default regime opens an implicit `BEGIN`
   before the first DML of a unit of work and commits or rolls back only when
   this module asks, which keeps `transaction()`'s documented
   rollback-on-error promise real rather than nominal. This replaces the
   earlier `isolation_level=None` (autocommit) choice; with autocommit a
   `rollback()` discards nothing because the row was already committed, so the
   `transaction()` contract at lines 646–647 would have been nominal only.
2. **`category_transaction`'s `finally` resets the outermost-transaction depth
   counter.** The reset executes at the end of `category_transaction` so that a
   block that *raised* does not leave the depth pinned at 1 — which would make
   every later `transaction()` on this instance raise "a transaction is already
   open" forever. This is the same defect class as item 5 and is what makes the
   `savepoint()` block's own `finally` reset (line 983–985 of the module)
   meaningful for the category path too. The reset lives in the `finally`, not
   in the success branch, precisely because the failure path is where the leak
   occurred.
3. **`_flush_raw_batch` no longer opens its own `SAVEPOINT`; the enclosing
   category savepoint IS the boundary.** Section 5.7 (lines 672–677) promises
   that "A batch failure rolls back to the start of the failing batch only,
   then propagates, so the enclosing `category_transaction` unwinds that
   category alone" — a guarantee about the *observable* outcome, not about a
   per-batch savepoint, and 5.7's own sentence "the observable guarantee, not
   the mechanism" (line 661) is exactly the freedom this uses. A per-batch
   savepoint was the wrong boundary twice over: a prefix of batches that were
   already released cannot be rolled back when a later batch fails, and a
   release inside a block that must roll back leaves the partial batch behind.
   The enclosing `category_transaction`'s savepoint is the only boundary that
   undoes an already-written prefix for that category, so the batch is written
   plainly inside it and left for that block to release or roll back. The
   batch-failure `DatabaseError` contract (lines 629–630) is unchanged: it
   still names the record count, never the record content.
4. **The bare-`SAVEPOINT` nesting ceiling is removed.** The implementation no
   longer caps savepoint nesting and no longer relies on a bare `SAVEPOINT` to
   establish an implicit transaction. Ownership of the enclosing boundary is
   decided by this module's own depth counter and never by
   `sqlite3.Connection.in_transaction`, because pysqlite's default regime makes
   `in_transaction` true after any plain DML call (a plainly-called `insert_run`
   with no `transaction()` anywhere), so a bare `SAVEPOINT` there would be
   nested inside a transaction *another call* opened and its `RELEASE` would
   commit nothing — leaving rows the block is responsible for pending, invisible
   to a second connection and lost on close. A block that owns the boundary
   therefore opens a real `BEGIN` first (module lines 964–967 and 1036–1039).
5. **`_release_quietly` removed and reclassified as a regression source;
   replaced by `_release_once` and `_settle_own_transaction`.** `_release_quietly`
   skipped `RELEASE` whenever it could not see an open transaction, and
   swallowed a failed `RELEASE` under that same condition. That condition is
   exactly the one in which an outermost savepoint's implicit transaction is
   already gone, so the helper's silent early return was indistinguishable from
   a successful release: it hid dropped batches behind a passing test. It is
   therefore recorded as a **regression source** — a helper that concealed a
   defect rather than one that caused it — and not as an incidental refactor.
   The replacement splits the two responsibilities the old helper conflated:
   `_release_once` issues `RELEASE` unconditionally, letting a real engine error
   propagate, and `_settle_own_transaction` commits only the transaction this
   call opened, never one an enclosing `transaction()` owns. Like item 1, this
   changes no published name: `_release_quietly`, `_release_once`, and
   `_settle_own_transaction` are module-private, and the public surface of
   section 5.2 is unaffected.

6. **The plain-INSERT column exclusion is computed per record, not per table
   (`_bindable` / `_insert_columns` / `_insert_omitted_columns` /
   `_insert_rows`).** Section 5.9's column-by-column encoding contract (lines
   760-769) is the authority, quoted verbatim below in item 6a. The repair adds
   the module-private helper `_record_columns_with_non_none(table, record)` and
   routes the plain-INSERT path through it, so that a `NOT NULL` column keeps
   the value its record supplies and takes the implicit default **only** when
   the record supplies `None`. This is the same class of post-hoc repair as
   items 1-5: it is recorded here after the fact, it is **not** a pre-existing
   frozen decision, and it does not re-open Q2 or Q5 — neither question touched
   the INSERT column list. Section 11's "no changes to the frozen contract"
   claim is not falsified, because no published signature moved: the five
   record dataclasses, the enums and constants, `SCHEMA_VERSION`,
   `DDL_STATEMENTS`, `CREATE_TABLE_STATEMENTS`, `TABLE_COLUMNS`,
   `TABLE_PRIMARY_KEYS`, `TABLE_INDEXES`, and every `Repository` protocol
   method signature are untouched. Item 6 is also consistent with the comment
   block at lines 469-475: `_IMPLICIT_NOT_NULL_DEFAULTS` holds concrete values,
   never null markers, so it can only ever stand in for a column the record
   left unset — reading it as a per-table exclusion instead made it overwrite
   values the record had already supplied.

**a. The governing contract, section 5.9 lines 760-769, quoted verbatim:**

```
- `bool` fields → `INTEGER` `0`/`1`; read back as `bool(0)`/`bool(1)`.
- `datetime` fields → `TEXT` ISO-8601 UTC; read back through the same
  serialization contract as `models.from_json` so UTC awareness is preserved.
- `Optional[...]` fields → SQL `NULL`; read back as `None`. **Never** as `0`,
  `0.0`, `""`, or `False`.
- JSON fields (`*_json`) → `TEXT` stored exactly as given; the repository does
  not re-serialize or normalize them.
- `int`/`float` fields → `INTEGER`/`REAL`.
```

**b. The rule the code now implements.** For a `NOT NULL` column: bind the
record's value when the record provides one; use the implicit default only when
the record provides `None`. The frozen DDL declares no `DEFAULT` clause (lines
176-182 and 1540-1544 of the module), so `_IMPLICIT_NOT_NULL_DEFAULTS` exists
solely to make an INSERT total over `NOT NULL` columns; it is not a licence to
overwrite supplied values. `CategoryScoreRecord` is a frozen dataclass with
every field present, so "absent" can only mean `None`, and the 26 columns the
defect affected are `NOT NULL` — a caller can never legitimately pass `None`
for them anyway. Returning a supplied `usable_demand_sample_count=72` as `0`
is precisely the "Never as `0`, `0.0`, `\"\", or `False`" violation above.

**c. The three sites, changed together.** `_bindable` keeps its `nullable or
column not in implicit` predicate but its docstring now states the
supplied-value rule; `_insert_rows` assembles each row through
`_record_columns_with_non_none` so supplied values win; `_insert_columns`
keeps returning the *possible*-bind set and documents that the per-record
choice is made downstream; `_insert_omitted_columns` now derives its result
from the same `_bindable` predicate instead of re-deriving the exclusion a
third time. `_columns_with_non_none` (module line 541) is the intended helper
for this distinction and is reused here through its per-record counterpart.
Verification was measured, not argued: a field-by-field written-versus-read
round trip with every field explicitly non-null and non-default reports **26
divergences of 49 fields before the repair and 0 of 50 after** (50 because a
subsequent `category_scores` column count is read from `TABLE_COLUMNS`), with
`runs`, `raw_discovery_observations`, `sample_members`, and
`enrichment_observations` each 0 before and after, the `upsert_category_scores`
conflict path 0 before and after, and `None`-valued optional fields still
round-tripping as `None`.

**Pre-gate step: the masked-node diagnostic (`tests/test_contracts.py`).** The
node `tests/test_contracts.py::test_repository_protocol_and_schema_specification`
fails at its `:938` assertion (`assert "sqlite3" not in ... database.py ...`,
`tests/test_contracts.py` lines 938–940). pytest reports only the FIRST failure
per node, so a fresh, clean-*looking* run of that node reports `:938` and leaves
the assertions at `:918`, `:921`, `:922`, and `:930` **never evaluated**. A
diagnostic has already evaluated all 31 assertions in that node independently:
**30 PASS, 1 FAIL, and the single failure is `:938` itself.** Consequence for
this chunk's gate, recorded here so it cannot be lost: the gate SHALL NOT treat
those four masked assertions as passing, and "the suite is green" SHALL NOT be
accepted as evidence for more than the one assertion it actually proves. The
masked-node diagnostic is a **pre-gate step** of this chunk's gate, and running
it is required before section 10's suite-level bullet is read as satisfied. The
disposition of `:938` itself is Chunk 0's document-consistency note, not this
chunk's repair ("Chunk 0 is the primary implementation chunk and completion
chunk for ... `LREQ-ARCH-010`", section 2, lines 74–79); Chunk 2 does not edit
`tests/test_contracts.py`, which is not in section 6's file list (lines
829–834).
