# Chunk 4B — Sample persistence, overlap, and sampling summaries

Status: DRAFT
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-02.md (Status: VERIFIED) — the frozen persistence
  contract: `sample_members` / `category_scores` column sets, the write/read
  APIs, the transaction regime, and the exception semantics.
  Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md
  (Status: FROZEN) — the pure result structures this chunk materializes. No
  `Documents/interfaces/chunk-4A.md` exists (see §13, claim C-2); the frozen
  4A plan §5 and `src/niche_scout/sampling.py` are used as the contract.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 6A (preflight selection writes `preflight_selected` on the rows this
  chunk inserts), Chunk 6B (finalizes the `u_*` placeholders this chunk
  writes), Chunk 7B (LREQ-MET-030/050/060/100 consume persisted stratified
  `N_h`/`n_h` and usable counts), Chunk 11 (LREQ-RPT-020/030/050 read the
  persisted sample fraction, sampling basis, and overlap fields),
  Chunk 13 (`LREQ-TST-020` closure).

> **This plan is BLOCKED.** §12 carries open questions that must be ruled on
> before a test author can write the persistence tests without guessing. The
> central one (Q-1) is that the frozen schema's category-level
> `usable_*_sample_count` columns are `INTEGER NOT NULL` with no representable
> "pending" state, while the Chunk 4B gate requires usable-count fields to be
> "explicitly marked pending rather than presented as measured values". The
> plan is complete in structure but **not freezable** until §12 is ruled.

## 1. Goal

Chunk 4A computes a deterministic, pure sampling result and persists nothing.
This chunk makes the audit trail true: it takes the pure `RunSamplingResult`,
derives the cross-category overlap that can only be computed after every
category sample is selected, writes one `sample_members` row per selected
identity and one per-category sampling summary (census flag, sampling basis,
sample fraction, sampling-rule version, overlap counts, and the per-stratum
`N_h`/`n_h` summary) into the frozen SQLite tables, and verifies by read-back
that the persisted values equal the pure result. It adds no table, column, or
index, and it does not fabricate a usable count: `u_demand_h`, `u_recent_h`,
and `u_quality_h` are left explicitly pending for Chunk 6B.

## 2. Scope

### In scope

- **Overlap computation (pure).** From the completed `RunSamplingResult`,
  compute per category the number of *other* categories sharing at least one
  sampled canonical identity and the overlap sample percentage, per SRS §6.5.
  Overlap is computed from unique canonical identities after all samples are
  selected.
- **`sample_members` materialization.** One row per selected member carrying
  `stratum_index`, `stratum_start_ordinal`, `stratum_end_ordinal`,
  `sample_rank_within_stratum`, `sample_is_census`, `selection_digest`, and the
  overlap fields (§6.3).
- **Per-category sampling summary.** `discovered_population_count`,
  `enriched_sample_count`, `sample_is_census`, `sampling_basis`,
  `sample_fraction`, `sampling_rule_version` (run-level), and the overlap
  fields.
- **Per-stratum summary.** `N_h`, `n_h`, the ordinal boundaries, and explicit
  **pending** placeholders for `u_demand_h`, `u_recent_h`, `u_quality_h`,
  together with the (still pending) eligibility-rule slot, persisted in
  `category_scores.stratum_statistics_json` — the only frozen home for
  per-stratum counts (SRS §6.5).
- **Persisted-value verification.** A read-back comparison of the persisted
  `sample_members` and the persisted category summary against the pure 4A
  result, deterministic and order-stable.
- **Tests:** `tests/test_sampling_persistence.py` and SQLite round-trip /
  overlap fixtures, written **before** the implementation (routing: `impl-deep`;
  test-author first).

### Explicitly out of scope (and who owns it instead)

- **Post-enrichment finalization of `u_demand_h`, `u_recent_h`, `u_quality_h`,
  and the authoritative sample summaries.** Chunk 4B is the *primary
  implementation/completion* chunk for `LREQ-SMP-080`; Chunk 6B is the second
  completion chunk and owns finalization. 4B must leave the `u_*` values
  explicitly pending, never fabricated as `0`.
- **Metric eligibility rules for the usable counts.** Chunks 7A (primitives)
  and 7B (estimators). 4B writes no eligibility rule the SRS does not yet
  define.
- **Stratum eligibility coverage.** `demand_stratum_eligibility_coverage`,
  `recent_supply_stratum_eligibility_coverage`, and
  `quality_stratum_eligibility_coverage` are Chunk 7B/8 outputs; 4B must not
  compute or fabricate them. `sample_fraction` must stay distinct from them.
- **Preflight selection.** `preflight_selected` is Chunk 6A's decision
  (`LREQ-ID-010`). 4B inserts the membership row and must supply a value for
  the `NOT NULL` column (see Q-5).
- **`unique_enrichment_count` and enrichment execution.** Chunks 6A/6B own
  at-most-once enrichment and the run-wide distinct count (SRS §6.5); 4B does
  not write a fabricated `0` as a measured enrichment count (Q-1(b)).
- **Pipeline orchestration, run/category status policy, warnings, and report
  rendering.** Chunks 10/11.
- **Any schema change.** No new table, column, index, constraint, or enum.
  `SCHEMA_VERSION` stays `"1.0.0"`.
- **Traceability-validator widening.** Chunk 13.

## 3. Requirements this chunk must satisfy

Ownership roles are the labels in
`Documents/requirements-dependency-map.md` "Ownership and test traceability
matrix" (line 81). Normative text is quoted from `Documents/SRS-lean.md`.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-SMP-080 | **Primary implementation/completion chunk**; supporting chunks Chunk 2, Chunk 4A, Chunk 6B; completion chunks Chunk 4B, Chunk 6B. Required tests `LREQ-TST-020`, `LREQ-TST-080`. (Matrix line 81.) | "**LREQ-SMP-080**: Every category SHALL persist discovered population size, sample enrichment sample size, usable sample size by component, stratum boundaries, stratum sizes and selected counts, selected identity keys or a reproducible selection digest, sampling-rule version, census flag, and duplicate/cross-category overlap counts." "For every stratum, the persisted summary SHALL include `N_h` (discovered population), `n_h` (sampled population), `u_demand_h`, `u_recent_h`, and `u_quality_h`, together with the eligibility rule used for each usable count." "For a census category, all discovered canonical assets SHALL be selected and `sample_is_census` SHALL be true; its stratum summaries SHALL retain the same `N_h`, `n_h`, and usable-count fields used by the sampled estimator." "The following SHALL be persisted as distinct values: `discovered_population_count`, `enriched_sample_count`, `usable_demand_sample_count`, `usable_recent_supply_sample_count`, and `usable_quality_sample_count` … `enriched_sample_count` SHALL never replace the discovered population." "`sample_fraction` SHALL be `1.0` for a non-empty census category and `null` when the discovered population is zero." "The selected identity keys SHALL be joined back to every category sample that contains them." (SRS §5.1, §6.5.) | §5.1, §6.3, §6.5 |

Supporting/consumed contract only (not owned here):

| LREQ ID | Role here | What this chunk consumes | SRS section |
|---|---|---|---|
| LREQ-SMP-040/050/060/070/090 | Consumed pure contract (primary owner Chunk 4A; completion Chunk 4A). | The selected members, per-stratum `population_count` (`N_h`) and `selected_count` (`n_h`), ordinal boundaries, `sample_is_census`, `sampling_basis`, `sample_fraction`, and per-member `selection_digest`. 4B persists them; it does not recompute the selection. | §5.1 |
| LREQ-SMP-030 | Consumed constant contract (primary owner Chunk 4A; supporting Chunk 0). | `SAMPLING_RULE_VERSION` is persisted run-level; `SAMPLE_STRATA`/`SAMPLE_PER_STRATUM` are already baked into the 4A result and are not re-read or re-exposed. | §5.1 |
| LREQ-ID-010 | Supporting chunk (primary owner Chunk 6A). | The `preflight_selected` column exists on the rows 4B inserts; 6A updates it. | §4.4 |
| LREQ-TST-020 | Supporting chunk for the sampling-test contract; closure in Chunk 13. | 4B adds persistence tests under `tests/test_sampling_persistence.py`; it does **not** attach `LREQ-TST-020` as a marker (precedent: 4A plan §9.4, Chunk 2 §5). | §13 |

## 4. Interface contracts consumed

Copied from `Documents/interfaces/chunk-02.md` (§2.7, §2.8, §2.9) and
`chunk-4A` plan §5 (§5.3, §5.4). None is redefined.

**From Chunk 4A (pure result types, plan §5.3/§5.4; live in
`src/niche_scout/sampling.py`):**

```python
@dataclass(frozen=True, slots=True)
class SamplingStratum:
    stratum_index: int
    start_ordinal: int
    end_ordinal: int
    population_count: int          # N_h
    selected_count: int            # n_h actually selected
    target_count: int
    is_reduced: bool

@dataclass(frozen=True, slots=True)
class SampledMember:
    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    sample_rank_within_stratum: int
    sample_is_census: bool
    selection_digest: str

@dataclass(frozen=True, slots=True)
class CategorySamplingResult:
    category: str
    population: CanonicalPopulation
    strata: tuple[SamplingStratum, ...]
    members: tuple[SampledMember, ...]
    sampling_basis: SamplingBasis
    sample_is_census: bool
    discovered_population_count: int
    enriched_sample_count: int
    sample_fraction: float | None
    sampling_rule_version: str

@dataclass(frozen=True, slots=True)
class RunSamplingResult:
    run_id: str
    sampling_rule_version: str
    categories: tuple[CategorySamplingResult, ...]
    @property
    def by_category(self) -> Mapping[str, CategorySamplingResult]: ...
    @property
    def enrichment_identity_keys(self) -> tuple[str, ...]: ...
```

**From Chunk 2 (frozen persistence contract, interface §2.7/§2.8):**

```python
class SqliteRepository:
    def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None: ...
    def upsert_sample_members(self, members: Sequence[SampleMemberRecord]) -> int: ...
    def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None: ...
    def upsert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> int: ...
    def set_category_status(self, run_id: str, category: str, discovery_status: str,
                            *, computed_at_utc: datetime | None = None) -> None: ...
    def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
    def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...
    def transaction(self): ...                 # context manager; commits/rolls back
    def category_transaction(self, run_id: str, category: str): ...
```

Frozen semantics relied on:

- `SampleMemberRecord` fields: `run_id, category, asset_identity_key,
  stratum_index, stratum_start_ordinal, stratum_end_ordinal,
  sample_rank_within_stratum, sample_is_census, selection_digest,
  overlap_category_count, overlap_sample_percentage, preflight_selected`.
  Primary key `(run_id, category, asset_identity_key)` rejects duplicate
  membership; a second plain insert raises `UniqueConstraintViolation`.
- `upsert_sample_members` "rewrites the summary columns of an existing
  membership (it cannot create a second membership)" and returns the number of
  rows written.
- `get_sample_members` ordering is `stratum_index` ASC then
  `sample_rank_within_stratum` ASC; `get_category_scores` ordering is `category`
  ASC.
- Nullable columns read back as `None`; no read/write path converts `None` to
  `0`/`0.0`/`""`/`False`.
- `set_category_status` creates the `(run_id, category)` `category_scores` row
  on first write and fills the scoring-phase columns with the module's
  pre-scoring defaults; `upsert_category_scores` "rewrites every non-key column
  of an existing `(run_id, category)` row" and is the Chunk 6B/10 finalization
  path.
- Enum-backed columns validate against the frozen value sets
  (`InvalidRecordValueError`); child rows for an unknown `run_id` raise
  `ForeignKeyConstraintViolation`; `computed_at_utc` is always caller-supplied
  (Chunk 2 never reads the clock).

**From Chunk 0 (`niche_scout.models`):** `SAMPLING_RULE_VERSION = "1.0.0"`,
`SAMPLE_STRATA = 4`, `SAMPLE_PER_STRATUM = 25`, `SamplingBasis`, `RunRecord`,
and `ensure_utc`.

**Frozen schema facts this chunk is bounded by (read from
`src/niche_scout/database.py`):**

- `sample_members`: `overlap_category_count INTEGER NOT NULL`,
  `overlap_sample_percentage REAL` (nullable), `preflight_selected INTEGER NOT
  NULL`. There is **no** entry for `sample_members` in the module's
  `_IMPLICIT_NOT_NULL_DEFAULTS`, so a plain insert binds every column from the
  record.
- `category_scores`: `usable_demand_sample_count`, `usable_recent_supply_sample_count`,
  `usable_quality_sample_count` are `INTEGER NOT NULL`; `unique_enrichment_count`
  is `INTEGER NOT NULL`; `sample_fraction REAL` (nullable);
  `stratum_statistics_json TEXT NOT NULL`; the three
  `*_stratum_eligibility_coverage` columns are `REAL NOT NULL`.
- No alias column (`sample_size`, `demand_usable_count`, …) exists.

## 5. Interface contract this chunk produces

> **Provisional.** The pure overlap contract (§5.1/§5.2) is fully specified by
> the SRS. The persistence contract (§5.3) is **contingent on §12 Q-1..Q-5**
> and is not freezable until those are ruled. This section becomes
> `Documents/interfaces/chunk-4B.md` verbatim once the lead freezes it.

### 5.1 Pure overlap types (sampling.py, additive)

```python
@dataclass(frozen=True, slots=True)
class CategoryOverlap:
    """Overlap of one category's sample with all other categories' samples.

    Per SRS §6.5. `overlap_category_count` counts OTHER categories sharing at
    least one sampled canonical identity; `overlap_sample_percentage` is
    `100 * (<this category's sampled identities that appear in at least one
    other category>) / enriched_sample_count`. It is `None` iff
    `enriched_sample_count == 0`; a non-empty sample with no shared identity is
    `0.0` (a measured zero), never `None`.
    """
    category: str
    overlap_category_count: int
    overlap_sample_percentage: float | None

@dataclass(frozen=True, slots=True)
class RunOverlapResult:
    """Overlap for every category, in the RunSamplingResult category order."""
    run_id: str
    categories: tuple[CategoryOverlap, ...]
    @property
    def by_category(self) -> Mapping[str, CategoryOverlap]: ...
```

```python
def compute_overlap(run: RunSamplingResult) -> RunOverlapResult:
    """Per-category cross-category overlap (SRS §6.5).

    Input is the completed `RunSamplingResult`; overlap is computed from unique
    canonical identities after all samples are selected. A category's members
    are already identity-unique (4A), so a shared identity is counted once per
    category regardless of how many categories contain it. Category order is
    preserved; an empty run yields `categories == ()`. Pure: no RNG, no clock,
    no I/O, no mutation.
    """
```

Edge contract:
- Disjoint categories → `overlap_category_count == 0`, `overlap_sample_percentage == 0.0`.
- One category only → `overlap_category_count == 0`, `overlap_sample_percentage == 0.0` (non-empty sample).
- Zero-member category → `overlap_category_count == 0`, `overlap_sample_percentage is None`.
- An identity shared by `k` categories makes each of those categories count
  the other `k-1`, and each counts that identity once in its percentage
  numerator.
- No overlap value ever increases `enriched_sample_count` or any enrichment /
  preflight count.

### 5.2 `stratum_statistics_json` shape (provisional; see Q-4)

A JSON array, sorted by ascending `stratum_index`, one object per stratum:

```json
[
  {
    "stratum_index": 0,
    "stratum_start_ordinal": 1,
    "stratum_end_ordinal": 25,
    "N_h": 25,
    "n_h": 25,
    "u_demand_h": null,
    "u_recent_h": null,
    "u_quality_h": null,
    "usable_status": "pending",
    "eligibility_rule": null
  }
]
```

- `N_h == SamplingStratum.population_count`, `n_h == SamplingStratum.selected_count`.
- While enrichment eligibility is unknown, every `u_*` is JSON `null`,
  `usable_status` is the pending token, and `eligibility_rule` is `null`.
- Serialization is deterministic: `json.dumps(..., sort_keys=True,
  separators=(",", ":"))`, integer counts as integers.
- The exact pending token and the presence/absence of `usable_status` /
  `eligibility_rule` are **not** pinned by the SRS (Q-4).

### 5.3 Persistence and verification API (provisional; see Q-1, Q-2, Q-3, Q-5)

Proposed additive functions in `src/niche_scout/database.py`:

```python
@dataclass(frozen=True, slots=True)
class SamplingPersistenceReport:
    run_id: str
    sample_members_written: int
    categories_written: int
    mismatches: tuple[str, ...]        # empty → verified; never a fabricated 0

def persist_run_sampling(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    computed_at_utc: datetime,
) -> SamplingPersistenceReport:
    """Materialize `run` into `sample_members` and the per-category summary.

    `computed_at_utc` is required and caller-supplied; this chunk reads no
    clock. Overlap is computed with `sampling.compute_overlap` and written to
    both `sample_members` and the category summary. `u_demand_h`,
    `u_recent_h`, `u_quality_h` are written as explicit pending placeholders,
    never as a measured `0`; category-level usable counts follow the Q-1
    ruling. Returns the counts actually written. A duplicate membership is
    rejected by the primary key (`UniqueConstraintViolation`).
    """

def verify_persisted_sampling(
    repository: SqliteRepository,
    run: RunSamplingResult,
) -> SamplingPersistenceReport:
    """Read back and compare persisted values against the pure 4A result.

    Deterministic: reads `get_sample_members` and `get_category_scores`, then
    compares membership, rank/digest, census flag, sampling basis,
    `sample_fraction` (including `None` for a zero population and the
    `sample_fraction` ≠ eligibility-coverage distinction), overlap fields, and
    the per-stratum `N_h`/`n_h` and pending `u_*`. Returns `mismatches == ()`
    when every persisted value equals the pure result; mismatch strings name
    the column and category only — never an identity string or a secret.
    """
```

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/sampling.py` | modified | Add `CategoryOverlap`, `RunOverlapResult`, `compute_overlap` (additive; no existing name redefined). (§5.1) |
| `src/niche_scout/database.py` | modified | Add `SamplingPersistenceReport`, `persist_run_sampling`, `verify_persisted_sampling` and the per-stratum JSON serializer. No DDL, no column, no index, no frozen name changed. (§5.3) |
| `tests/test_sampling_persistence.py` | new | Analytical persistence/overlap tests (§9); every analytical node marked `@pytest.mark.lreq("LREQ-SMP-080")`. |
| `tests/fixtures/sampling_persistence_fixtures.py` | new | Inert run/overlap/round-trip fixtures and hand-derived overlap vectors. Data/factories only; no logic under test. |
| `tests/fixtures/__init__.py` | modified | Re-export `sampling_persistence_fixtures` alongside the existing modules. |
| `tests/traceability.json` | modified | Append one entry per §9.3 node (node-ID key → `["LREQ-SMP-080"]`). |
| `Documents/interfaces/chunk-4B.md` | produced by freeze (lead) | §5 verbatim, once §12 is ruled and the lead verifies. Not written by this planner. |

No other file is edited. `validation.py`, `metrics.py`, `scoring.py`,
`collector*.py`, `config.py`, `pipeline.py`, `report.py`, `cli.py`, the tools
package, `models.py`, the DDL strings, and all interface documents are
untouched.

## 7. Task breakdown

Test-first (routing: `impl-deep`; test-author before implementation).

- [ ] Write `tests/fixtures/sampling_persistence_fixtures.py` with the overlap
      vectors and round-trip fixtures in §9.2. (LREQ-SMP-080)
- [ ] Write `tests/test_sampling_persistence.py` with the §9.3 nodes, each
      marked `@pytest.mark.lreq("LREQ-SMP-080")`, and add the
      `tests/traceability.json` entries. (LREQ-SMP-080)
- [ ] Implement `CategoryOverlap`, `RunOverlapResult`, `compute_overlap` in
      `sampling.py` (keep the module pure). (LREQ-SMP-080)
- [ ] Implement the deterministic `stratum_statistics_json` serializer and the
      pending `u_*` placeholders. (LREQ-SMP-080)
- [ ] Implement `persist_run_sampling` (membership + per-category summary)
      under the Q-1/Q-2/Q-5 rulings. (LREQ-SMP-080)
- [ ] Implement `verify_persisted_sampling` (read-back equality against the
      pure result). (LREQ-SMP-080)
- [ ] Run `python -m pytest tests/test_sampling_persistence.py -q`, then the
      full suite, `python -m niche_scout.tools.validate_traceability`, and
      `python -m niche_scout.tools.check_import_boundaries`; report real
      output. (§10)

## 8. Edge cases and invariants

- Overlap is computed from unique canonical identities **after** all category
  samples are selected; overlap must not inflate enrichment counts or preflight
  rates (dependency map §5 item 7).
- `sample_fraction` is `1.0` for a non-empty census, `None` for a
  zero-population category (persisted as SQL `NULL`, never `0.0`), and
  normally `< 1.0` for a large category.
- `sample_fraction` is distinct from `*_stratum_eligibility_coverage`; 4B
  writes only `sample_fraction` and must not fabricate coverage (gate bullet;
  acceptance criterion 22).
- Every selected sample has a persisted membership **or** a reproducible
  digest: each row carries the 4A `selection_digest`, and the digest is
  recomputable from `(sampling_rule_version, category, asset_identity_key)`.
- Duplicate membership is rejected by the primary key; re-persisting an
  existing membership cannot create a second row.
- Before enrichment, `u_demand_h`/`u_recent_h`/`u_quality_h` are explicitly
  pending, never measured values.
- A census category's stratum summary retains the same `N_h`, `n_h`, and
  usable-count fields as the sampled estimator (SRS §5.1); its `N_h == n_h`.
- An empty category yields a summary with `discovered_population_count == 0`,
  `enriched_sample_count == 0`, `sample_fraction NULL`, no members, and
  `stratum_statistics_json == "[]"`.
- `preflight_selected` is Chunk 6A's later decision; 4B writes only a
  pre-preflight value for the `NOT NULL` column (Q-5).
- Missing is not zero: no `or 0`, `.get(k, 0)`, or default-0 substitution on
  any metric or summary value.
- Determinism: identical `RunSamplingResult` plus identical persisted state
  produce identical rows and identical verification output; no set/dict
  iteration order affects any written value or ordering.

## 9. Test plan

### 9.1 Test files

- `tests/test_sampling_persistence.py` (new) — every analytical node carries
  `@pytest.mark.lreq("LREQ-SMP-080")`.
- `tests/fixtures/sampling_persistence_fixtures.py` (new) — inert factories and
  vectors only.
- Database lives under pytest `tmp_path`; no live network, no credentials.

### 9.2 Fixtures and golden vectors (hand-computed where the SRS pins them)

- **Fixture O1 — overlap pair.** `Overlap/A` = 3 members `{a1, a2, s1}`,
  `Overlap/B` = 3 members `{b1, b2, s1}` sharing `s1`. Expected per category:
  `overlap_category_count == 1`; `overlap_sample_percentage ==
  100 * 1 / 3 == 33.333333333333336` (assert within `1e-9`).
- **Fixture O2 — no overlap.** Disjoint 2-member categories → count `0`,
  percentage `0.0`.
- **Fixture O3 — single category.** One non-empty category → count `0`,
  percentage `0.0`.
- **Fixture O4 — empty category.** Zero-member category → count `0`,
  percentage `None`; no member rows.
- **Fixture O5 — three-way share.** `s1` in `A`, `B`, `C` (1 member each) →
  each category: count `2`, percentage `100.0`; the union is one identity.
- **Fixture O6 — round-trip run.** A `RunRecord` (`run_id`, aware-UTC
  timestamps, `status="running"`, `sampling_rule_version="1.0.0"`,
  `page_view_semantics_status="unvalidated"`,
  `graphql_operation_correlation_mode="explicit_key"`,
  `identity_preflight_status="passed"`) plus two categories: a census
  (`N=3`) and a large (`N=101`) category. Hand-derived expectations:
  census `sample_fraction == 1.0`, `sample_is_census True`,
  `sampling_basis == "census"`; large `len(members) == 100`,
  `sample_fraction == 100/101`.
- **Fixture O7 — zero-population category.** One category with no records →
  `discovered_population_count 0`, `sample_fraction None`, `strata == ()`,
  `members == ()`, `stratum_statistics_json == "[]"`.
- **Fixture O8 — per-stratum N_h/n_h.** `N=101` strata expected
  `(1,25,25,25)`, `(1,26,50,25)`, `(2,51,75,25)`, `(3,76,101,26)` as
  `(stratum_index, start, end, N_h, n_h)`.

The digest literal for the census/sample rows is the 4A vector
(`tests/fixtures/sampling_fixtures.py::DIGEST_F_HEX`); the persistence test
asserts the stored `selection_digest` equals the pure member digest and the
recomputed digest.

### 9.3 Test list, mapped to LREQ IDs and traceability entries

All nodes map to `["LREQ-SMP-080"]` in `tests/traceability.json` unless noted.
Every key below is the fully qualified node ID; the `…` in the key column is a
display shorthand for the literal prefix
`tests/test_sampling_persistence.py` (for example the row for
`test_census_summary_round_trips` has the key
`tests/test_sampling_persistence.py::test_census_summary_round_trips`).

| Node (base pytest node ID) | Purpose | Marker | traceability.json key |
|---|---|---|---|
| `test_compute_overlap_counts_shared_categories` | Overlap pair (O1) | LREQ-SMP-080 | `tests/test_sampling_persistence.py::test_compute_overlap_counts_shared_categories` |
| `test_compute_overlap_percentage_is_exact_ratio` | Percentage formula (O1) | LREQ-SMP-080 | …`::test_compute_overlap_percentage_is_exact_ratio` |
| `test_compute_overlap_zero_when_disjoint` | Disjoint → measured 0 (O2) | LREQ-SMP-080 | …`::test_compute_overlap_zero_when_disjoint` |
| `test_compute_overlap_single_category` | Single category (O3) | LREQ-SMP-080 | …`::test_compute_overlap_single_category` |
| `test_compute_overlap_null_percentage_for_empty_category` | `None`, not `0.0` (O4) | LREQ-SMP-080 | …`::test_compute_overlap_null_percentage_for_empty_category` |
| `test_compute_overlap_three_way_share` | Three-way identity (O5) | LREQ-SMP-080 | …`::test_compute_overlap_three_way_share` |
| `test_compute_overlap_preserves_category_order` | Order-stable result | LREQ-SMP-080 | …`::test_compute_overlap_preserves_category_order` |
| `test_compute_overlap_does_not_inflate_enrichment_counts` | Counts unchanged by overlap | LREQ-SMP-080 | …`::test_compute_overlap_does_not_inflate_enrichment_counts` |
| `test_persist_writes_one_membership_per_selected_member` | Membership materialization (O6) | LREQ-SMP-080 | …`::test_persist_writes_one_membership_per_selected_member` |
| `test_persisted_member_fields_match_pure_result` | stratum/rank/census/digest | LREQ-SMP-080 | …`::test_persisted_member_fields_match_pure_result` |
| `test_persisted_digest_is_reproducible` | Membership or reproducible digest | LREQ-SMP-080 | …`::test_persisted_digest_is_reproducible` |
| `test_persisted_overlap_columns_match_pure_overlap` | Overlap round trip (O1) | LREQ-SMP-080 | …`::test_persisted_overlap_columns_match_pure_overlap` |
| `test_census_summary_round_trips` | Census summary (O6) | LREQ-SMP-080 | …`::test_census_summary_round_trips` |
| `test_large_category_summary_round_trips` | Sample summary (O6) | LREQ-SMP-080 | …`::test_large_category_summary_round_trips` |
| `test_zero_population_sample_fraction_is_null_not_zero` | NULL, not `0.0` (O7) | LREQ-SMP-080 | …`::test_zero_population_sample_fraction_is_null_not_zero` |
| `test_stratum_statistics_json_round_trips_n_h_and_boundaries` | Per-stratum summary (O8) | LREQ-SMP-080 | …`::test_stratum_statistics_json_round_trips_n_h_and_boundaries` |
| `test_pending_usable_placeholders_before_enrichment` | `u_*` pending, not measured | LREQ-SMP-080 | …`::test_pending_usable_placeholders_before_enrichment` |
| `test_sample_fraction_distinct_from_eligibility_coverage` | Distinct fields; no coverage fabricated | LREQ-SMP-080 | …`::test_sample_fraction_distinct_from_eligibility_coverage` |
| `test_duplicate_membership_is_rejected_and_does_not_duplicate` | PK rejects duplicate | LREQ-SMP-080 | …`::test_duplicate_membership_is_rejected_and_does_not_duplicate` |
| `test_persisted_values_verify_against_pure_result` | Verification passes | LREQ-SMP-080 | …`::test_persisted_values_verify_against_pure_result` |
| `test_verification_reports_a_tampered_value` | Negative: mismatch detected | LREQ-SMP-080 | …`::test_verification_reports_a_tampered_value` |
| `test_persist_requires_explicit_utc_and_reads_no_clock` | No clock in the write path | LREQ-SMP-080 | …`::test_persist_requires_explicit_utc_and_reads_no_clock` |

Parameterized nodes are mapped by their base node ID (dependency map §6.6).

### 9.4 Fixtures

`tests/fixtures/sampling_persistence_fixtures.py` provides: the O1–O5 overlap
populations and expected vectors; the O6 `run_record(run_id)` factory built
from the frozen `RunRecord`; the O6 census/large category populations; the O7
zero-population category; the O8 expected per-stratum table; and the expected
digest. `tests/fixtures/__init__.py` re-exports the module. No fixture contains
credentials (LREQ-SEC-020).

## 10. Definition of done (gate)

Copied verbatim from the dependency map's Chunk 4B Gate section
(`Documents/requirements-dependency-map.md`, lines 628–635):

- Every selected sample has a persisted membership or reproducible digest.
- Per-category and per-stratum summaries survive a database round trip.
- Before enrichment, usable-count fields are explicitly marked pending rather than presented as measured values.
- Overlap is calculated from unique canonical identities after all samples are selected.
- Persisted sample fraction is distinct from per-stratum eligibility coverage.
- A pure sampling test cannot pass this gate without a corresponding persistence verification.

## 11. Explicit prohibitions

- This chunk SHALL NOT add a table, column, index, constraint, enum, or
  `SCHEMA_VERSION` change. The frozen DDL and every frozen Chunk 0/2 name stay
  byte-identical.
- `sampling.py` SHALL remain pure: no `sqlite3`, no filesystem/process/network,
  no clock, no RNG; the new `compute_overlap` performs no I/O.
- No function in this chunk SHALL read the system clock; `computed_at_utc` (and
  any run timestamp) is caller-supplied.
- This chunk SHALL NOT fabricate a `u_demand_h`, `u_recent_h`, or `u_quality_h`
  value, and SHALL NOT present a usable count as measured before enrichment.
- This chunk SHALL NOT write `demand_stratum_eligibility_coverage`,
  `recent_supply_stratum_eligibility_coverage`,
  `quality_stratum_eligibility_coverage`, `unique_enrichment_count`, or any
  raw metric as a fabricated value; those are Chunks 6B/7B/8 outputs.
- This chunk SHALL NOT select preflight assets or decide
  `preflight_selected`; it writes only the pre-preflight value Q-5 fixes.
- This chunk SHALL NOT re-run or alter the 4A selection; it persists the 4A
  result and verifies it.
- No secret, identity token, header, or credential may enter a row or a
  verification message (LREQ-SEC-020).
- This chunk SHALL NOT touch `validation.py`, `metrics.py`, `scoring.py`,
  `collector*.py`, `config.py`, `pipeline.py`, `report.py`, `cli.py`,
  `models.py`, the tools package, or any interface/`Documents/runs/` file.
- This chunk SHALL NOT add any out-of-scope capability (scheduling,
  resume/checkpoint, historical trends, configurable weights, alternative
  collection strategies, confidence intervals).

## 12. Open questions / assumptions

None is resolved here. Each blocks a correct plan or a test author's ability to
write the cited tests without guessing.

1. **Q-1 — category-level `usable_*_sample_count` cannot represent "pending".**
   `category_scores.usable_demand_sample_count`,
   `usable_recent_supply_sample_count`, and `usable_quality_sample_count` are
   `INTEGER NOT NULL` and `CategoryScoreRecord` declares them non-optional
   `int` (models.py lines 475–477; database.py lines 192–194). The gate requires
   usable-count fields to be explicitly pending before enrichment. Options:
   (a) per-stratum `u_*` are `null` plus an explicit pending token inside
   `stratum_statistics_json`, and the category-level columns are left at the
   module's pre-scoring default `0` (which is arguably "presented as measured");
   (b) a sentinel integer (e.g. `-1`) in the category-level columns means
   pending (invented; not in the SRS);
   (c) a schema change to make them nullable or add a status column
   (contradicts the fixed-schema constraint);
   (d) 4B does not write the per-category summary in `category_scores` at all
   (contradicts the gate's "per-category summaries survive a round trip").
   SRS §5.1/§6.5; dependency map 4B gate line 632; 6B gate line 762.
2. **Q-1(b) — `unique_enrichment_count` on an un-enriched row.** It is
   `INTEGER NOT NULL`; SRS §6.5 defines it as a run-wide post-enrichment
   distinct count. Does 4B leave it at `0` (misreadable as measured) or write
   it only in 6B? Same class as Q-1.
3. **Q-2 — no frozen Chunk 2 write path writes only the sampling-phase
   `category_scores` columns.** `upsert_category_scores` "rewrites every
   non-key column" and the chunk-02 plan assigns it to Chunks 6B/10;
   `set_category_status` writes only `discovery_status`. Options:
   (a) 4B adds a new additive repository method (e.g. `upsert_sampling_summary`)
   that writes only the sampling-phase columns and leaves scoring-phase columns
   untouched (a change to a VERIFIED Chunk 2 module — needs a scope ruling);
   (b) 4B builds a full `CategoryScoreRecord` from the existing row plus the
   sampling columns and calls `upsert_category_scores` (writes pre-scoring
   defaults for other chunks' fields);
   (c) some third path. SRS §6.5; `interfaces/chunk-02.md` §2.7.
4. **Q-3 — `sample_members.overlap_category_count`/`overlap_sample_percentage`
   semantics.** SRS §6.3 lists both columns on `sample_members` but defines them
   only per category (§6.5: "…with this category"). Options:
   (a) each member row repeats its category's `CategoryOverlap` values;
   (b) each member row carries per-identity values (how many *other* categories
   contain *that* identity, and a per-identity percentage).
   §6.5's "or its joined sample summary" and the null rule ("null when
   `enriched_sample_count = 0`") read as category-level, but (b) is not
   excluded. The two readings differ whenever a category has both a shared and
   an unshared member.
5. **Q-4 — the pending/`u_*` marker vocabulary and the
   `stratum_statistics_json` shape are not pinned anywhere.** The SRS names
   `N_h`, `n_h`, `u_demand_h`, `u_recent_h`, `u_quality_h` and "the eligibility
   rule used for each usable count", but not a pending token, a
   `usable_status` key, a `null` `eligibility_rule`, or the JSON object keys and
   ordering. Chunk 6B's gate says "explicit unavailable/invalid status", which
   implies a shared status vocabulary 4B and 6B must agree on. Is 4B authorized
   to define this vocabulary (and freeze it in `interfaces/chunk-4B.md`), and
   must 6B/7A use the same tokens?
6. **Q-5 — the `preflight_selected` value 4B writes.** `sample_members` has no
   default entry and `preflight_selected` is `NOT NULL` (models.py line 414;
   database.py line 143), so the insert must bind a value even though
   `LREQ-ID-010` (Chunk 6A) owns the decision. Is writing `False` as an explicit
   pre-preflight placeholder acceptable, or must 4B avoid inserting until 6A
   decides (which would break 4B's own materialization gate)?
7. **Q-6 — `interfaces/chunk-4A.md` does not exist.** The 4A plan §5 declares
   "This section becomes `Documents/interfaces/chunk-4A.md` verbatim once
   frozen", but no such file exists (see §13 claim C-2). This plan uses the
   frozen 4A plan §5 plus `src/niche_scout/sampling.py` as the contract per the
   dispatch brief. Does the lead need to create `interfaces/chunk-4A.md` before
   freezing 4B, or is the frozen plan an accepted substitute?
8. **Q-7 — overlap percentage rounding.** SRS §6.5 gives the formula
   `100 * count / enriched_sample_count` and no rounding rule. 4B stores the
   unrounded `float64` (round only for display, per hard rule 4); confirm no
   rounding at persistence.
9. **Q-8 — where 4B's persistence entry point belongs.** The dependency map's
   module column for `LREQ-SMP-080` names `sampling.py`, `database.py`, and the
   architecture fixes the module boundary, so this plan proposes the additive
   functions in §5.3 inside `database.py` (which already imports `models`).
   Confirm that adding domain-specific persistence functions to the VERIFIED
   `database.py` — rather than `pipeline.py` (Chunk 10) — is in scope.

## 13. Countable claims and evidence labels

Every countable/factual claim in this plan, its label, and how it was obtained.
No command was executed (the shell tool is denied to this planner; see
COMMANDS in the result block), so every claim below is from a file read and is
labelled **read** or **counted-by-reading**, never **verified by tool**.

- **C-1 (counted-by-reading): `tests/traceability.json` is an object keyed by
  pytest node ID, with an array of LREQ IDs as the value.** Method: read lines
  1–178; line 1 is `{`, line 178 is `}`, and every line 2–177 is
  `"<node id>": [<LREQ ids>]`. Count: 176 entry rows (lines 2–177 inclusive).
  Note: `tests/AGENTS.md` line 5 describes the inverse keying; the file itself
  is authoritative here.
- **C-2 (counted-by-reading): only five interface files exist, and
  `interfaces/chunk-4A.md` is not among them.** Method: `glob
  Documents/interfaces/*.md` returned `chunk-00.md`, `chunk-01.md`,
  `chunk-02.md`, `chunk-03.md`, `chunk-05.md` (5 files).
- **C-3 (read): `sampling.py` currently defines the 4A result types and exposes
  14 names in `__all__`; it defines no overlap function or type.** Method: read
  all 570 lines of `src/niche_scout/sampling.py`; `__all__` (lines 33–48) has 14
  entries, no `compute_overlap`.
- **C-4 (read): `CategoryScoreRecord.usable_demand_sample_count`,
  `usable_recent_supply_sample_count`, and `usable_quality_sample_count` are
  non-optional `int`; `unique_enrichment_count` is non-optional `int`.**
  Method: read `src/niche_scout/models.py` lines 450–513 (fields at 475–477 and
  472).
- **C-5 (read): the `category_scores` DDL declares the three `usable_*` columns
  and `unique_enrichment_count` as `INTEGER NOT NULL`, `sample_fraction` as
  nullable `REAL`, and `stratum_statistics_json` as `TEXT NOT NULL`.**
  Method: read `src/niche_scout/database.py` lines 175–230 (columns at 188–194
  and 207).
- **C-6 (read): the `sample_members` DDL declares `overlap_category_count
  INTEGER NOT NULL`, `overlap_sample_percentage REAL` (nullable), and
  `preflight_selected INTEGER NOT NULL`.** Method: read
  `src/niche_scout/database.py` lines 130–147 (columns at 141–143).
- **C-7 (read): `_IMPLICIT_NOT_NULL_DEFAULTS` has an entry only for
  `category_scores`; `sample_members` has none.** Method: read
  `src/niche_scout/database.py` lines 476–507.
- **C-8 (read): `interfaces/chunk-02.md` §2.7 documents `upsert_category_scores`
  as an ON-CONFLICT rewrite of every non-key column, and the chunk-02 plan §5.7
  assigns it to Chunks 6B/10.** Method: read `interfaces/chunk-02.md` lines
  286–347 and `Documents/plans/chunk-02-sqlite-implementation-and-repository.md`
  line 758.
- **C-9 (read, quoted): the Chunk 4B gate bullets** in §10 are copied from
  `Documents/requirements-dependency-map.md` lines 628–635.
- **C-10 (read, quoted): the `LREQ-SMP-080` text** in §3 is quoted from
  `Documents/SRS-lean.md` lines 472–481 and §6.5 lines 483–505.
- **C-11 (read): no fixture module defines a `run_record` factory.** Method:
  grep of `tests/fixtures` for `RunRecord|run_record` returned no matches; §9.4
  therefore adds one.
- **C-12 (read): `tests/test_sampling.py` is 1038 lines** as reported by the
  read tool (line-count footer), not independently verified.

## 14. Assumptions this plan makes explicit

- The routing is `impl-deep`, test-author first; the plan is structured
  test-first.
- `sampling.py` is the home for the pure overlap computation (it is the
  `LREQ-SMP-080` pure module and already owns the 4A result types);
  `database.py` is the home for the I/O persistence and verification.
  (Confirm with Q-8.)
- The lead, not this planner, creates `Documents/interfaces/chunk-4B.md` from
  §5 after §12 is ruled.
