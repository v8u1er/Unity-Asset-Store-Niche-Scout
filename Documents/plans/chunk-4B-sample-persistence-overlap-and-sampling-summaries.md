# Chunk 4B — Sample persistence, overlap, and sampling summaries

Status: FROZEN
Last amended: 2026-09-20 — all nine §12 open questions ruled by a human and
applied in place, each with a dated ruling note (no earlier assertion silently
substituted). §12 item 10's recorded inconsistency is **resolved by lead
ruling** (2026-09-20): the Q-2 create-if-absent path is explicitly a defensive
fallback and SHALL NOT invent a `discovery_status`. `persist_run_sampling`
forwards the already-persisted `discovery_status` it reads via
`get_category_scores` whenever the row exists (the Chunk 3 runtime path,
`collector_coveo.py:2208`, always creates it before 4B runs); if no row exists
and no value is available, `upsert_sampling_summary` raises
`InvalidRecordValueError` naming the table and column only. The Q-2 restriction
to "sampling-phase columns" applies to the **update** path, which is unchanged;
the create path's only conflict with the frozen module was
`discovery_status`, and it does not invent one.
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-02.md (Status: VERIFIED) — the frozen persistence
  contract: `sample_members` / `category_scores` column sets, the write/read
  APIs, the transaction regime, and the exception semantics.
  Documents/interfaces/chunk-4A.md (Status: VERIFIED) — the pure result
  structures this chunk materializes, reproduced verbatim from the frozen 4A
  plan §5 (Q-6 action done by the lead).
  Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md
  (Status: FROZEN) — source plan for the 4A interface.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 6A (writes `preflight_selected` on the rows this chunk inserts),
  Chunk 6B (finalizes the `u_*` placeholders this chunk writes; **its plan must
  not be written until `Documents/interfaces/chunk-4B.md` is frozen**),
  Chunk 7B (LREQ-MET-030/050/060/100 consume persisted stratified `N_h`/`n_h`
  and usable counts), Chunk 11 (LREQ-RPT-020/030/050 read the persisted sample
  fraction, sampling basis, and overlap fields; must not render the
  non-authoritative category-level usable placeholders as measured while
  pending), Chunk 13 (`LREQ-TST-020` closure).

## 1. Goal

Chunk 4A computes a deterministic, pure sampling result and persists nothing.
This chunk makes the audit trail true: it takes the pure `RunSamplingResult`,
derives the cross-category overlap that can only be computed after every
category sample is selected, writes one `sample_members` row per selected
identity and one per-category sampling summary (census flag, sampling basis,
sample fraction, sampling-rule version consistency, overlap counts, and the
per-stratum `N_h`/`n_h` summary) into the frozen SQLite tables, and verifies by
read-back that the persisted values equal the pure result. It adds no table,
column, or index. It does not fabricate a usable count: the per-stratum
`u_demand_h`, `u_recent_h`, and `u_quality_h` are JSON `null` with an explicit
`usable_status = "pending"` token inside `stratum_statistics_json`, which is the
authoritative pending state, and the category-level `usable_*_sample_count`
columns are left at the module's pre-scoring placeholder and are explicitly
**non-authoritative** (Chunk 6B finalizes them before any consumer reads them).

## 2. Scope

### In scope

- **Overlap computation (pure).** From the completed `RunSamplingResult`,
  compute per category the number of *other* categories sharing at least one
  sampled canonical identity and the overlap sample percentage, per SRS §6.5.
  Overlap is computed from unique canonical identities after all samples are
  selected; the percentage is stored unrounded `float64`.
- **`sample_members` materialization.** One row per selected member carrying
  `stratum_index`, `stratum_start_ordinal`, `stratum_end_ordinal`,
  `sample_rank_within_stratum`, `sample_is_census`, `selection_digest`, the
  category's `overlap_category_count`/`overlap_sample_percentage` (Q-3 option
  (a): the category-level values repeated on every member row), and the
  documented pre-preflight `preflight_selected = False` placeholder (Q-5).
- **Per-category sampling summary (additive write path).** `discovered_population_count`,
  `enriched_sample_count`, `sample_is_census`, `sampling_basis`,
  `sample_fraction`, `overlap_category_count`, `overlap_sample_percentage`, and
  `stratum_statistics_json`, written through a new additive repository method
  `SqliteRepository.upsert_sampling_summary` that updates **only** these
  sampling-phase columns (Q-2 option (a)). `runs.sampling_rule_version` is
  written at run creation and is verified, not rewritten.
- **Per-stratum summary + pending vocabulary (4B owns and freezes it, Q-4).**
  `stratum_index`, `stratum_start_ordinal`, `stratum_end_ordinal`, `N_h`, `n_h`,
  `u_demand_h`/`u_recent_h`/`u_quality_h` (JSON `null` while pending),
  `usable_status` (4B writes `"pending"`), and `eligibility_rule` (`null` while
  pending; 7A owns its eventual value), persisted in
  `category_scores.stratum_statistics_json` — the only frozen home for
  per-stratum counts (SRS §6.5).
- **Category-level usable counts stay non-authoritative placeholders.** The
  `usable_*_sample_count` and `unique_enrichment_count` columns are **not**
  written by 4B; they remain at the module's pre-scoring default (Chunk 3's
  `set_category_status` already created the row with `0` before 4B runs, and the
  DDL is `INTEGER NOT NULL`). The interface and the verification state they are
  non-authoritative pre-scoring placeholders, never presented as measured; 6B
  finalizes them before any consumer reads them (pipeline gate: 6B sample
  summaries complete before metric calculation).
- **Persisted-value verification.** A read-back comparison of the persisted
  `sample_members` and the persisted category summary against the pure 4A
  result, deterministic and order-stable; the verification does **not** assert
  the category-level `usable_*`/`unique_enrichment_count` as measured.
- **Tests:** `tests/test_sampling_persistence.py` and SQLite round-trip /
  overlap fixtures, written **before** the implementation (routing: `impl-deep`;
  test-author first).

### Explicitly out of scope (and who owns it instead)

- **Post-enrichment finalization of `u_demand_h`, `u_recent_h`, `u_quality_h`,
  `usable_*_sample_count`, `unique_enrichment_count`, and the authoritative
  sample summaries.** Chunk 4B is the *primary implementation/completion* chunk
  for `LREQ-SMP-080`; Chunk 6B is the second completion chunk and owns
  finalization. 4B must leave the per-stratum `u_*` explicitly pending and must
  not write the category-level counts.
- **Metric eligibility rules for the usable counts, and `eligibility_rule`.**
  Chunks 7A (primitives) and 7B (estimators). 4B writes `null` for
  `eligibility_rule`.
- **Stratum eligibility coverage.** `demand_stratum_eligibility_coverage`,
  `recent_supply_stratum_eligibility_coverage`, and
  `quality_stratum_eligibility_coverage` are Chunk 7B/8 outputs; 4B must not
  compute or fabricate them. `sample_fraction` must stay distinct from them.
- **Preflight selection.** `preflight_selected` is Chunk 6A's decision
  (`LREQ-ID-010`). 4B writes only the documented `False` placeholder (Q-5);
  6A updates selected rows to `True`. Note for 6A: no frozen method updates
  `preflight_selected` alone (`upsert_sample_members` rewrites all non-key
  columns), so 6A needs a read-modify-write upsert or its own additive method.
- **Enrichment execution and the run-wide distinct enrichment count.**
  Chunks 6A/6B (SRS §6.5); 4B does not write `unique_enrichment_count`.
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

> **Q-1/Q-4 applied (2026-09-20).** The per-stratum usable fields are persisted
> pending via the frozen `stratum_statistics_json` vocabulary (§5.2); the
> category-level `usable_*_sample_count` columns are non-authoritative
> pre-scoring placeholders written by nobody in 4B (Q-1 option (a), §12).
> SRS §6.5: "The stratum summary remains authoritative for the per-stratum
> counts."

Supporting/consumed contract only (not owned here):

| LREQ ID | Role here | What this chunk consumes | SRS section |
|---|---|---|---|
| LREQ-SMP-040/050/060/070/090 | Consumed pure contract (primary owner Chunk 4A; completion Chunk 4A). | The selected members, per-stratum `population_count` (`N_h`) and `selected_count` (`n_h`), ordinal boundaries, `sample_is_census`, `sampling_basis`, `sample_fraction`, and per-member `selection_digest`. 4B persists them; it does not recompute the selection. | §5.1 |
| LREQ-SMP-030 | Consumed constant contract (primary owner Chunk 4A; supporting Chunk 0). | `SAMPLING_RULE_VERSION` is persisted on `runs` at run creation and verified against `RunSamplingResult.sampling_rule_version`; `SAMPLE_STRATA`/`SAMPLE_PER_STRATUM` are already baked into the 4A result and are not re-read or re-exposed. | §5.1 |
| LREQ-ID-010 | Supporting chunk (primary owner Chunk 6A). | The `preflight_selected` column exists on the rows 4B inserts; 4B writes the documented `False` placeholder, 6A updates it (Q-5). | §4.4 |
| LREQ-TST-020 | Supporting chunk for the sampling-test contract; closure in Chunk 13. | 4B adds persistence tests under `tests/test_sampling_persistence.py`; it does **not** attach `LREQ-TST-020` as a marker (precedent: 4A plan §9.4, Chunk 2 §5). | §13 |

## 4. Interface contracts consumed

Copied from `Documents/interfaces/chunk-02.md` (§2.7, §2.8, §2.9),
`Documents/interfaces/chunk-4A.md` (§5.3, §5.4), and the frozen plan §5. None is
redefined.

**From Chunk 4A (`Documents/interfaces/chunk-4A.md`, VERIFIED; live in
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
    def get_run(self, run_id: str) -> Optional[RunRecord]: ...
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
  rows written. Chunk 2's plan §5.7 names Chunk 4B as its user ("re-materialize
  corrected summaries").
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
  is `INTEGER NOT NULL`; `discovery_status` is `TEXT NOT NULL`;
  `sample_fraction REAL` (nullable); `stratum_statistics_json TEXT NOT NULL`;
  the three `*_stratum_eligibility_coverage` columns are `REAL NOT NULL`.
- `_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]` covers every `NOT NULL`
  column above **except** `discovery_status`, `computed_at_utc`, and the two
  primary-key columns (see §12 item 10, claim C-14).
- No alias column (`sample_size`, `demand_usable_count`, …) exists.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-4B.md` verbatim once the lead
freezes it. It is complete: the §12 item 10 create-path question is resolved by
lead ruling (2026-09-20) — the create path is a defensive fallback that forwards
`discovery_status` and never invents it. All names are additive; nothing in `models.py`,
`validation.py`, `config.py`, `database.py`'s frozen names, or `sampling.py`'s
4A names is redefined or shadowed.

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
    `0.0` (a measured zero), never `None`. The value is stored unrounded.
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
    no I/O, no mutation. `overlap_sample_percentage` is unrounded `float64`
    (Q-7): rounding is a display concern only.
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

> **Q-3 ruling applied (2026-09-20).** Option (a): each `sample_members` row
> repeats its **category's** `CategoryOverlap` values. The SRS defines both
> values only per category (§6.5), and there is no per-identity formula or
> denominator; per-identity values are rejected. See §5.3.

### 5.2 `stratum_statistics_json` schema and usable-status vocabulary (Q-4; 4B owns and freezes it)

`stratum_statistics_json` is a JSON array, one object per stratum, sorted by
ascending `stratum_index`. Each object has exactly these keys:

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

- `N_h == SamplingStratum.population_count`; `n_h == SamplingStratum.selected_count`;
  `stratum_start_ordinal`/`stratum_end_ordinal` are the 1-based inclusive
  population ordinals from the 4A stratum.
- **Usable-status vocabulary (frozen at this freeze).** `usable_status` is one
  of exactly: `"pending"`, `"usable"`, `"unavailable"`, `"invalid"`. Chunk 4B
  writes `"pending"`. Chunk 6B writes the final status from the same four
  tokens. Chunk 7A owns the eventual `eligibility_rule` value. This vocabulary
  is the shared contract 6B and 7A must consume; it is frozen in
  `interfaces/chunk-4B.md`.
- While enrichment eligibility is unknown, every `u_*` is JSON `null`,
  `usable_status` is `"pending"`, and `eligibility_rule` is `null`.
- Serialization is deterministic:
  `json.dumps(value, sort_keys=True, separators=(",", ":"))`; integer counts are
  serialized as JSON integers; `None` is serialized as `null`; there is no
  dependence on dict/set iteration order. The object key set is the ten keys
  above (the serialized key order is `sort_keys`-determined).
- An empty population (zero members, CMS: no strata) serializes to `"[]"`.
- This lives entirely inside the frozen `stratum_statistics_json TEXT` column;
  no schema change.

### 5.3 Persistence and verification API (database.py, additive)

**Category-level usable counts are non-authoritative pre-scoring placeholders.**
The `usable_demand_sample_count`, `usable_recent_supply_sample_count`,
`usable_quality_sample_count`, and `unique_enrichment_count` columns on
`category_scores` are **not** written by Chunk 4B and are never presented as
measured values. They remain at the module's pre-scoring default (`0`), which
Chunk 3's `set_category_status` already wrote when it created the row before 4B
ran (and the DDL is `INTEGER NOT NULL`, so there is no representable pending
state at the category level). The per-stratum `usable_status = "pending"` in
`stratum_statistics_json` is the authoritative pending state (SRS §6.5). Chunk
6B finalizes the category-level values before any consumer reads them; Chunk 11
must not render them as measured while pending. 4B's verification does not read
or assert them.

**`preflight_selected` placeholder.** `sample_members.preflight_selected` is
`NOT NULL` with no module default and membership rows must exist before
preflight selection, so 4B binds the literal `False` as an explicit, documented
pre-preflight placeholder (Q-5). Chunk 6A updates selected rows to `True`. 4B
tests must not present `False` as a preflight result.

```python
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
) -> None:
    """Write only the sampling-phase `category_scores` columns (Q-2 option (a)).

    Creates the `(run_id, category)` row if absent, filling every other
    `NOT NULL` column from the module's pre-scoring default table
    (`_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]`) and binding the supplied
    sampling-phase values; on conflict it updates **only** the eight
    sampling-phase columns listed here — `discovered_population_count`,
    `enriched_sample_count`, `sample_is_census`, `sampling_basis`,
    `sample_fraction`, `overlap_category_count`, `overlap_sample_percentage`,
    and `stratum_statistics_json`. Every scoring-phase column, and
    `unique_enrichment_count` / the three `usable_*_sample_count` columns, are
    left untouched on the update path. `sampling_basis` is validated against
    `SamplingBasis`. `computed_at_utc` is required and caller-supplied; this
    module reads no clock and writes nothing on `None`.

    **Create-if-absent is a defensive fallback (lead ruling 2026-09-20, §12
    item 10).** `category_scores.discovery_status` is `TEXT NOT NULL` and is the
    one non-sampling `NOT NULL` column absent from the module's default table,
    so this method SHALL NOT invent it. `persist_run_sampling` forwards the
    `discovery_status` it reads from `get_category_scores`; the Chunk 3 runtime
    path always creates the row before 4B runs. If no `(run_id, category)` row
    exists and no `discovery_status` is supplied, the method raises
    `InvalidRecordValueError` naming the table and column only. The Q-2
    restriction to sampling-phase columns governs the **update** path, which is
    unchanged.
    """
```

```python
@dataclass(frozen=True, slots=True)
class SamplingPersistenceReport:
    run_id: str
    sample_members_written: int      # rows written by persist; rows read by verify
    categories_written: int          # summaries written by persist; summaries read by verify
    mismatches: tuple[str, ...]      # empty → verified; never a fabricated 0

def persist_run_sampling(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    computed_at_utc: datetime,
) -> SamplingPersistenceReport:
    """Materialize `run` into `sample_members` and the per-category summary.

    `computed_at_utc` is required and caller-supplied; this chunk reads no
    clock. Overlap is computed once with `sampling.compute_overlap` and written
    to both `sample_members` (each member row repeats its category's
    `CategoryOverlap` values per Q-3) and the category summary (via
    `upsert_sampling_summary`). Members are written through
    `upsert_sample_members`, so re-materializing a run is idempotent and can
    never create a second membership for a `(run_id, category, identity)`; a
    hand-built duplicate insert is still rejected by the primary key
    (`UniqueConstraintViolation`). Every member carries
    `preflight_selected=False` (Q-5). `runs.sampling_rule_version` is not
    rewritten. `u_demand_h`/`u_recent_h`/`u_quality_h` are written as explicit
    pending placeholders in `stratum_statistics_json`; the category-level
    `usable_*` and `unique_enrichment_count` columns are not written. A missing
    `runs` row raises `ForeignKeyConstraintViolation`. Returns the counts
    actually written; `mismatches` is empty.
    """

def verify_persisted_sampling(
    repository: SqliteRepository,
    run: RunSamplingResult,
) -> SamplingPersistenceReport:
    """Read back and compare persisted values against the pure 4A result.

    Deterministic: reads `get_sample_members`, `get_category_scores`, and
    `get_run`, then compares membership (identity set, stratum/rank, census
    flag, `selection_digest`), the category summary (`discovered_population_count`,
    `enriched_sample_count`, `sample_is_census`, `sampling_basis`,
    `sample_fraction` — including `None` for a zero population and the
    `sample_fraction` ≠ eligibility-coverage distinction), the overlap fields
    (category-level on both `sample_members` and the summary), the per-stratum
    `N_h`/`n_h` and the frozen `stratum_statistics_json` schema/status tokens
    (§5.2), and `runs.sampling_rule_version` against
    `run.sampling_rule_version`. It does **not** assert the category-level
    `usable_*_sample_count` or `unique_enrichment_count` as measured values.
    Returns `mismatches == ()` when every compared value equals the pure
    result; mismatch strings name the column and category only — never an
    identity string or a secret. `sample_members_written`/`categories_written`
    report the rows read.
    """
```

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/sampling.py` | modified | Add `CategoryOverlap`, `RunOverlapResult`, `compute_overlap` (additive; no existing name redefined). (§5.1) |
| `src/niche_scout/database.py` | modified | Add the additive `SqliteRepository.upsert_sampling_summary` method, `SamplingPersistenceReport`, `persist_run_sampling`, `verify_persisted_sampling`, and the deterministic `stratum_statistics_json` serializer/parser. No DDL, no column, no index, no frozen Chunk 0/2 name changed. (§5.2/§5.3) |
| `tests/test_sampling_persistence.py` | new | Analytical persistence/overlap tests (§9); every analytical node marked `@pytest.mark.lreq("LREQ-SMP-080")`. |
| `tests/fixtures/sampling_persistence_fixtures.py` | new | Inert run/overlap/round-trip fixtures and hand-derived overlap vectors. Data/factories only; no logic under test. |
| `tests/fixtures/__init__.py` | modified | Re-export `sampling_persistence_fixtures` alongside the existing modules. |
| `tests/traceability.json` | modified | Append one entry per §9.3 node (node-ID key → `["LREQ-SMP-080"]`), append-only. |
| `Documents/interfaces/chunk-4B.md` | produced by freeze (lead) | §5 verbatim, once the lead verifies. Not written by this planner. |

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
      `tests/traceability.json` entries (append-only). (LREQ-SMP-080)
- [ ] Implement `CategoryOverlap`, `RunOverlapResult`, `compute_overlap` in
      `sampling.py` (keep the module pure; unrounded `float64`). (LREQ-SMP-080)
- [ ] Implement the deterministic `stratum_statistics_json` serializer with the
      frozen key set and `usable_status = "pending"` token. (LREQ-SMP-080)
- [ ] Implement the additive `SqliteRepository.upsert_sampling_summary` method
      (update only the eight sampling-phase columns) under the §12 item 10
      resolution. (LREQ-SMP-080)
- [ ] Implement `persist_run_sampling` (membership via `upsert_sample_members`
      with category-level overlap repeated per member and
      `preflight_selected=False`; summary via `upsert_sampling_summary`; no
      write of `usable_*`/`unique_enrichment_count`). (LREQ-SMP-080)
- [ ] Implement `verify_persisted_sampling` (read-back equality against the
      pure result; never assert category-level usable counts as measured).
      (LREQ-SMP-080)
- [ ] Run `python -m pytest tests/test_sampling_persistence.py -q`, then the
      full suite, `python -m niche_scout.tools.validate_traceability`, and
      `python -m niche_scout.tools.check_import_boundaries`; report real
      output. (§10)

## 8. Edge cases and invariants

- Overlap is computed from unique canonical identities **after** all category
  samples are selected; overlap must not inflate enrichment counts or preflight
  rates (dependency map §5 item 7).
- Every `sample_members` row repeats its **category's** overlap values (Q-3
  option (a)); there is no per-identity overlap value.
- `overlap_sample_percentage` is stored unrounded `float64` (Q-7); rounding is
  display-only.
- `sample_fraction` is `1.0` for a non-empty census, `None` for a
  zero-population category (persisted as SQL `NULL`, never `0.0`), and
  normally `< 1.0` for a large category.
- `sample_fraction` is distinct from `*_stratum_eligibility_coverage`; 4B
  writes only `sample_fraction` and must not fabricate coverage (gate bullet;
  acceptance criterion 22).
- Every selected sample has a persisted membership **or** a reproducible
  digest: each row carries the 4A `selection_digest`, and the digest is
  recomputable from `(sampling_rule_version, category, asset_identity_key)`.
- Duplicate membership is impossible: `persist_run_sampling` uses
  `upsert_sample_members`, so re-materializing cannot add a second row, and the
  primary key rejects a hand-built duplicate insert.
- Before enrichment, per-stratum `u_demand_h`/`u_recent_h`/`u_quality_h` are
  JSON `null` with `usable_status == "pending"` — never measured values. The
  category-level `usable_*_sample_count` and `unique_enrichment_count` columns
  are non-authoritative pre-scoring placeholders and are not written by 4B.
- A census category's stratum summary retains the same `N_h`, `n_h`, and
  usable-count fields as the sampled estimator (SRS §5.1); its `N_h == n_h`.
- An empty category yields a summary with `discovered_population_count == 0`,
  `enriched_sample_count == 0`, `sample_fraction NULL`, no members, and
  `stratum_statistics_json == "[]"`.
- `preflight_selected` is written `False` as a pre-preflight placeholder (Q-5);
  it is not a preflight result.
- `stratum_statistics_json` uses exactly the ten keys and the four-token
  `usable_status` vocabulary in §5.2, serialized with
  `sort_keys=True, separators=(",", ":")`.
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
  100 * 1 / 3 == 33.333333333333336` (assert within `1e-9`; unrounded).
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
  `(0,1,25,25,25)`, `(1,26,50,25,25)`, `(2,51,75,25,25)`, `(3,76,101,26,25)` as
  `(stratum_index, start, end, N_h, n_h)`.
  > **Lead correction applied 2026-09-20 (human ruling (a) on the 4B fixture dispute).**
  > The pre-ruling text read `(1,25,25,25)`, `(1,26,50,25)`, `(2,51,75,25)`,
  > `(3,76,101,26)` — malformed (4-tuples labelled as 5 fields) and with the
  > first entry's stratum index wrong — and it asserted the `N=101` final stratum
  > `n_h == 26`. That was an imported error. The final stratum holds 26 and is
  > **not reduced** (26 ≥ `SAMPLE_PER_STRATUM` = 25, SRS §5.1 LREQ-SMP-090, which
  > thresholds at "fewer than 25"), and LREQ-SMP-050 requires 25 from each
  > stratum; so `n_h == 25`, `selected_count == 25`, `is_reduced False`
  > (`sampling.py:412/:414`), total 100 members, `sample_fraction == 100/101`.
  > This matches §5.2's `n_h == SamplingStratum.selected_count`, the frozen
  > `Documents/interfaces/chunk-4A.md`, the passing 4A tests, and the sibling
  > 4B fixture values (`o6_expected_selected_counts` → 100). The frozen fixture
  > (`tests/fixtures/sampling_persistence_fixtures.py`
  > `O8_EXPECTED_STRATA_N101` and the `o6_expected_sample_fractions` comment) was
  > corrected to match. No source, contract, or traceability change.
- **Fixture O9 — pending JSON vector.** The exact serialized
  `stratum_statistics_json` for the census `N=1` category is
  `[{"N_h":1,"eligibility_rule":null,"n_h":1,"stratum_end_ordinal":1,"stratum_index":0,"stratum_start_ordinal":1,"u_demand_h":null,"u_quality_h":null,"u_recent_h":null,"usable_status":"pending"}]`
  (keys sorted by `sort_keys=True`). This pins the ten-key schema, the
  `"pending"` token, the null `u_*`/`eligibility_rule`, and the serialization.
- **Fixture O10 — placeholder vector.** A `category_scores` row created by
  `set_category_status` has `usable_demand_sample_count == 0`,
  `usable_recent_supply_sample_count == 0`, `usable_quality_sample_count == 0`,
  and `unique_enrichment_count == 0`; after `persist_run_sampling` those four
  values are **unchanged**, while the eight sampling-phase columns carry the
  pure result.

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
| `test_compute_overlap_percentage_is_unrounded_float64` | Unrounded value (Q-7) | LREQ-SMP-080 | …`::test_compute_overlap_percentage_is_unrounded_float64` |
| `test_compute_overlap_zero_when_disjoint` | Disjoint → measured 0 (O2) | LREQ-SMP-080 | …`::test_compute_overlap_zero_when_disjoint` |
| `test_compute_overlap_single_category` | Single category (O3) | LREQ-SMP-080 | …`::test_compute_overlap_single_category` |
| `test_compute_overlap_null_percentage_for_empty_category` | `None`, not `0.0` (O4) | LREQ-SMP-080 | …`::test_compute_overlap_null_percentage_for_empty_category` |
| `test_compute_overlap_three_way_share` | Three-way identity (O5) | LREQ-SMP-080 | …`::test_compute_overlap_three_way_share` |
| `test_compute_overlap_preserves_category_order` | Order-stable result | LREQ-SMP-080 | …`::test_compute_overlap_preserves_category_order` |
| `test_compute_overlap_does_not_inflate_enrichment_counts` | Counts unchanged by overlap | LREQ-SMP-080 | …`::test_compute_overlap_does_not_inflate_enrichment_counts` |
| `test_persist_writes_one_membership_per_selected_member` | Membership materialization (O6) | LREQ-SMP-080 | …`::test_persist_writes_one_membership_per_selected_member` |
| `test_persisted_member_fields_match_pure_result` | stratum/rank/census/digest | LREQ-SMP-080 | …`::test_persisted_member_fields_match_pure_result` |
| `test_persisted_digest_is_reproducible` | Membership or reproducible digest | LREQ-SMP-080 | …`::test_persisted_digest_is_reproducible` |
| `test_member_overlap_repeats_category_overlap_values` | Q-3 option (a) | LREQ-SMP-080 | …`::test_member_overlap_repeats_category_overlap_values` |
| `test_persisted_overlap_columns_match_pure_overlap` | Overlap round trip (O1) | LREQ-SMP-080 | …`::test_persisted_overlap_columns_match_pure_overlap` |
| `test_preflight_selected_is_false_placeholder` | Q-5 `False`, not a preflight result | LREQ-SMP-080 | …`::test_preflight_selected_is_false_placeholder` |
| `test_census_summary_round_trips` | Census summary (O6) | LREQ-SMP-080 | …`::test_census_summary_round_trips` |
| `test_large_category_summary_round_trips` | Sample summary (O6) | LREQ-SMP-080 | …`::test_large_category_summary_round_trips` |
| `test_zero_population_sample_fraction_is_null_not_zero` | NULL, not `0.0` (O7) | LREQ-SMP-080 | …`::test_zero_population_sample_fraction_is_null_not_zero` |
| `test_stratum_statistics_json_matches_frozen_schema` | Ten keys, ordering, token (O9) | LREQ-SMP-080 | …`::test_stratum_statistics_json_matches_frozen_schema` |
| `test_stratum_statistics_json_round_trips_n_h_and_boundaries` | Per-stratum summary (O8) | LREQ-SMP-080 | …`::test_stratum_statistics_json_round_trips_n_h_and_boundaries` |
| `test_pending_usable_status_token_is_pending` | `usable_status == "pending"` (Q-4) | LREQ-SMP-080 | …`::test_pending_usable_status_token_is_pending` |
| `test_pending_usable_placeholders_before_enrichment` | `u_*` JSON null, not measured | LREQ-SMP-080 | …`::test_pending_usable_placeholders_before_enrichment` |
| `test_category_level_usable_counts_are_non_authoritative_placeholders` | Category columns untouched (O10) | LREQ-SMP-080 | …`::test_category_level_usable_counts_are_non_authoritative_placeholders` |
| `test_unique_enrichment_count_is_not_written_by_4b` | Q-1(b) | LREQ-SMP-080 | …`::test_unique_enrichment_count_is_not_written_by_4b` |
| `test_upsert_sampling_summary_updates_only_sampling_columns` | Q-2 update path; scoring columns untouched | LREQ-SMP-080 | …`::test_upsert_sampling_summary_updates_only_sampling_columns` |
| `test_sample_fraction_distinct_from_eligibility_coverage` | Distinct fields; no coverage fabricated | LREQ-SMP-080 | …`::test_sample_fraction_distinct_from_eligibility_coverage` |
| `test_duplicate_membership_is_rejected_and_does_not_duplicate` | PK rejects duplicate; re-persist idempotent | LREQ-SMP-080 | …`::test_duplicate_membership_is_rejected_and_does_not_duplicate` |
| `test_persisted_values_verify_against_pure_result` | Verification passes | LREQ-SMP-080 | …`::test_persisted_values_verify_against_pure_result` |
| `test_verification_reports_a_tampered_value` | Negative: mismatch detected | LREQ-SMP-080 | …`::test_verification_reports_a_tampered_value` |
| `test_verification_does_not_assert_category_usable_counts` | Verification never treats placeholders as measured | LREQ-SMP-080 | …`::test_verification_does_not_assert_category_usable_counts` |
| `test_persist_requires_explicit_utc_and_reads_no_clock` | No clock in the write path | LREQ-SMP-080 | …`::test_persist_requires_explicit_utc_and_reads_no_clock` |

Parameterized nodes are mapped by their base node ID (dependency map §6.6).

### 9.4 Fixtures

`tests/fixtures/sampling_persistence_fixtures.py` provides: the O1–O5 overlap
populations and expected vectors; the O6 `run_record(run_id)` factory built
from the frozen `RunRecord`; the O6 census/large category populations; the O7
zero-population category; the O8 expected per-stratum table; the O9 exact
serialized pending JSON; the O10 placeholder vector; and the expected digest.
`tests/fixtures/__init__.py` re-exports the module. No fixture contains
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
- This chunk SHALL NOT write the category-level `usable_demand_sample_count`,
  `usable_recent_supply_sample_count`, `usable_quality_sample_count`, or
  `unique_enrichment_count` columns, and SHALL NOT present them as measured
  values; they are non-authoritative pre-scoring placeholders finalized by
  Chunk 6B.
- This chunk SHALL NOT write a measured `u_demand_h`, `u_recent_h`, or
  `u_quality_h`; it writes JSON `null` plus `usable_status = "pending"`.
- This chunk SHALL NOT write `demand_stratum_eligibility_coverage`,
  `recent_supply_stratum_eligibility_coverage`,
  `quality_stratum_eligibility_coverage`, or any raw metric as a fabricated
  value; those are Chunks 6B/7B/8 outputs.
- This chunk SHALL NOT write any scoring-phase `category_scores` column;
  `upsert_sampling_summary` updates only the eight sampling-phase columns.
- This chunk SHALL NOT select preflight assets or decide
  `preflight_selected`; it writes only the documented `False` placeholder
  (Q-5), and 4B tests must not present it as a preflight result.
- This chunk SHALL NOT implement per-identity overlap values; each member row
  repeats its category's overlap values (Q-3).
- This chunk SHALL NOT round `overlap_sample_percentage` at persistence.
- This chunk SHALL NOT use `upsert_category_scores` (the Chunk 6B/10
  finalization path) or build a full `CategoryScoreRecord`.
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

## 12. Open questions — RESOLVED by human rulings, 2026-09-20

All nine questions below were ruled on by a human on 2026-09-20. Each entry
records the question as previously written, the ruling, and where in this plan
the ruling is applied. No question is re-opened, and no option outside those
ruled is chosen. One ruling's create-if-absent clause is recorded as internally
inconsistent with the frozen module in item 10; that is a recorded
inconsistency, not a re-opened question, and it is why the status stays DRAFT.

1. **Q-1 — category-level `usable_*_sample_count` cannot represent "pending".**
   *RULED 2026-09-20: option (a).* Per-stratum `u_demand_h`/`u_recent_h`/
   `u_quality_h` are JSON `null` plus an explicit pending token inside
   `stratum_statistics_json`; that JSON is the authoritative pending state (SRS
   §6.5: "The stratum summary remains authoritative for the per-stratum
   counts"). The category-level `usable_*` columns stay at the module's
   pre-scoring default (`0`) — unavoidable and pre-existing, since Chunk 3's
   `set_category_status` (quoted by the ruling as `collector_coveo.py:2208`)
   already creates the row with `0` before 4B runs and the DDL is
   `INTEGER NOT NULL`. The interface and verification state the category-level
   values are **non-authoritative pre-scoring placeholders, never presented as
   measured**; 6B finalizes them before any consumer reads them (pipeline gate:
   6B sample summaries complete before metric calculation), and Chunk 11 must
   not render them as measured while pending. Option (b) `-1` sentinel
   rejected; (c) schema change rejected; (d) omit the category summary
   rejected. Applied: §2, §3, §5.3, §8, §9.3/§9.4 (O10).
2. **Q-1(b) — `unique_enrichment_count` on an un-enriched row.** *RULED
   2026-09-20: 4B does not write it.* Leave it at the pre-scoring default; 6B
   writes the true post-enrichment count. 4B's additive write path excludes the
   column, and 4B's verification must not assert it as measured. Applied: §2,
   §5.3, §8, §9.3 (`test_unique_enrichment_count_is_not_written_by_4b`).
3. **Q-2 — no frozen write path writes only the sampling-phase
   `category_scores` columns.** *RULED 2026-09-20: option (a).* 4B adds an
   additive repository method (`upsert_sampling_summary`) in `database.py` that
   writes only the sampling-phase columns and leaves all scoring-phase columns
   untouched, mirroring `set_category_status`: create the `(run_id, category)`
   row if absent (filling other `NOT NULL` columns from the module's default
   table) and, on conflict, update only the sampling-phase columns. Option (b)
   (full `CategoryScoreRecord` + `upsert_category_scores`) rejected as making
   4B the writer of other chunks' fields. Applied: §2, §5.3, §6, §7.
4. **Q-3 — `sample_members.overlap_*` semantics.** *RULED 2026-09-20: option
   (a).* Each member row repeats its category's `CategoryOverlap` values; the
   SRS defines both values only per category and there is no per-identity
   formula or denominator. Per-identity values are rejected. Applied: §2, §5.1,
   §5.3, §8, §11, §9.3.
5. **Q-4 — pending/`u_*` vocabulary and `stratum_statistics_json` shape.**
   *RULED 2026-09-20: 4B owns and freezes it.* 4B is authorized to define the
   vocabulary and freeze it in `interfaces/chunk-4B.md`; 6B and 7A must consume
   the same tokens. Per stratum: `u_demand_h`, `u_recent_h`, `u_quality_h`
   (`null` while pending), `usable_status`, and `eligibility_rule` (`null` while
   pending; 7A owns its eventual value). 4B writes `usable_status = "pending"`;
   6B writes the final status from the shared set
   (**pending / usable / unavailable / invalid**, spelling fixed at freeze).
   This lives inside the frozen `stratum_statistics_json TEXT` column — no
   schema change. Q-1 and Q-4 are one ruling: option (a) satisfies the gate
   only because this vocabulary makes the pending state explicit and
   authoritative. Applied: §5.2, §8, §9.2 (O9), §9.3.
6. **Q-5 — the `preflight_selected` value 4B writes.** *RULED 2026-09-20:
   write `False`.* 4B binds `False` as an explicit, documented pre-preflight
   placeholder; 6A updates selected rows to `True`. The column is `NOT NULL`
   with no default and the SRS requires membership rows to exist before
   preflight selection; `True` would falsely claim selection. 4B tests must not
   present it as a preflight result. Note added for 6A: no frozen method updates
   `preflight_selected` alone (`upsert_sample_members` rewrites all non-key
   columns), so 6A needs a read-modify-write upsert or its own additive method.
   Applied: §2, §5.3, §8, §9.3.
7. **Q-6 — `interfaces/chunk-4A.md` does not exist.** *RULED 2026-09-20:
   create it. DONE by the lead.* `Documents/interfaces/chunk-4A.md` now exists
   (`Status: VERIFIED`, built from the frozen 4A plan §5). Applied: the
   `Depends on` line and §13 claim C-2 are corrected in place.
8. **Q-7 — overlap percentage rounding.** *RULED 2026-09-20: store unrounded
   `float64`.* No rounding at persistence; round only for display (hard rule
   4). Applied: §5.1, §5.3, §8, §11, §9.3.
9. **Q-8 — where 4B's persistence entry point belongs.** *RULED 2026-09-20:
   additive functions in `database.py`.* Confirmed in scope; the dependency
   map's module column for `LREQ-SMP-080` is `sampling.py`, `database.py`;
   `pipeline.py` is orchestration (Chunk 10) and is not named for SMP-080. Keep
   the pure overlap types/computation in `sampling.py` and the translation,
   repository calls, and read-back verification in `database.py`. Applied: §5,
   §6, §7, §14.

10. **Q-2 create-if-absent path and `category_scores.discovery_status` — RESOLVED
    by lead ruling, 2026-09-20 (was: "recorded inconsistency, kept DRAFT").**
    The ruling says `upsert_sampling_summary` creates the row "if absent (filling
    other `NOT NULL` columns from the module's default table)". But
    `category_scores.discovery_status` is `TEXT NOT NULL` (database.py line
    179) and is **not** a member of
    `_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]` (database.py lines
    476–507), unlike every other non-sampling `NOT NULL` column; see §13 claim
    C-14. `set_category_status` supplies it from a required parameter.

    **Lead ruling (2026-09-20):** the Q-2 restriction to "sampling-phase
    columns" governs the **update** path, which is unchanged. The create path is
    a **defensive fallback that SHALL NOT invent a `discovery_status`**:
    `persist_run_sampling` forwards the `discovery_status` it reads from
    `get_category_scores` when the row exists — the Chunk 3 runtime path
    (`collector_coveo.py:2208`) always creates the `(run_id, category)` row
    before 4B runs — and the fallback raises `InvalidRecordValueError` (naming
    the table and column only) if no row exists and no value is available. The
    previously listed options (a)/(b)/(c) are **not** taken: no new required
    create-only parameter, no added module default, and no silent invention.
    Applied: §5.3 `upsert_sampling_summary` docstring (dated), `persist_run_sampling`
    (`discovery_status` forwarded), §6 and §7, and the status line.

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
- **C-2 (read; corrected 2026-09-20 per Q-6 ruling): `Documents/interfaces/chunk-4A.md`
  now exists and is `Status: VERIFIED`.** Method: read all 374 lines of the
  file, including its header (`Status: VERIFIED`, source plan, verified-at
  branch/commit) and its §5 reproduction. Supersedes the pre-ruling claim that
  only five interfaces existed and 4A was absent.
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
  and `unique_enrichment_count` as `INTEGER NOT NULL`, `discovery_status` as
  `TEXT NOT NULL`, `sample_fraction` as nullable `REAL`, and
  `stratum_statistics_json` as `TEXT NOT NULL`.** Method: read
  `src/niche_scout/database.py` lines 175–230 (columns at 179, 188–194 and 207).
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
- **C-13 (read): the four `usable_status` tokens are a 4B-defined vocabulary,
  not an SRS-defined enum.** Method: read `src/niche_scout/models.py` lines
  94–209 (all enums); no `usable_status` enum exists. The tokens
  `pending/usable/unavailable/invalid` come from the Q-4 ruling.
- **C-14 (read; supports §12 item 10): `_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]`
  does not include `discovery_status`.** Method: read
  `src/niche_scout/database.py` lines 476–507 and enumerate the keys against
  the DDL's `NOT NULL` columns at lines 179–226; the only non-key, non-supplied
  `NOT NULL` columns absent from the table are `discovery_status` and
  `computed_at_utc`.
- **C-15 (quoted, NOT verified by this planner): the ruling's claim that
  Chunk 3's `set_category_status` is at `collector_coveo.py:2208` and creates
  the `category_scores` row with `0` before 4B runs.** Recorded as quoted from
  the human ruling; `collector_coveo.py` was not read by this planner.

## 14. Assumptions this plan makes explicit

- The routing is `impl-deep`, test-author first; the plan is structured
  test-first.
- `sampling.py` is the home for the pure overlap types/computation (it is the
  `LREQ-SMP-080` pure module and already owns the 4A result types);
  `database.py` is the home for the additive repository method, the I/O
  persistence, and the verification (Q-8 ruling).
- The lead, not this planner, creates `Documents/interfaces/chunk-4B.md` from
  §5 after §12 item 10 is resolved and the lead re-reads.
- The status stays DRAFT until §12 item 10 is resolved; all other rulings are
  applied in place.

## 15. Cross-cutting coordination

- **Freeze order.** `Documents/interfaces/chunk-4B.md` must be frozen before
  Chunk 6B's plan is written: 6B's gate depends on the pending vocabulary and
  the `stratum_statistics_json` schema frozen here (§5.2, Q-4).
- **Parallel Chunk 7A.** No source or test file overlap (7A owns
  `validation.py`, `metrics.py`, `tests/test_validation.py`; this chunk owns
  `sampling.py`, `database.py`, `tests/test_sampling_persistence.py`).
  `tests/traceability.json` is keyed by node ID and merges append-only:
  neither `LREQ-SMP-080` nor the `LREQ-MET-*` closure is complete until the
  branches merge.