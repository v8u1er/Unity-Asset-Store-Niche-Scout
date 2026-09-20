# Chunk 4A — Canonical populations and deterministic sampling engine

Status: FROZEN
Last amended: 2026-09-20 — human rulings on all eight open questions applied;
§12 resolved in place; §6 purity-tool row removed per the Q-8 ruling (all eight
rulings are "recommended" options; each correction is dated and marked, none is
substituted silently).
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-00.md (Status: VERIFIED) — typed models, enums,
  constants, purity boundary, traceability conventions.
  Documents/interfaces/chunk-01.md (Status: VERIFIED) — identity resolution
  result (`IdentityResolutionResult`, `IdentityResolutionStatus`), which is the
  sole canonicality input to population construction.
  Documents/interfaces/chunk-02.md (Status: VERIFIED) — repository read surface
  and record types; **no runtime dependency and no import** (Chunk 4A is pure).
  Documents/interfaces/chunk-03.md (Status: VERIFIED) — the discovery-time raw
  observation shape this chunk consumes (`discovery_ordinal`,
  `asset_identity_key` nullable, `is_duplicate`, `stratum_index` nullable).
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 4B (Sample persistence, overlap, and sampling summaries) — consumes the
  pure result types to materialize `sample_members` and stratum summaries.
  Chunk 7B (raw estimators) — supporting chunk for `LREQ-MET-070`; consumes the
  canonical population/stratum shapes, not the sample selection.
  Chunk 13 (acceptance suite) — `LREQ-TST-020` closure happens there.

## 1. Goal

Today `src/niche_scout/sampling.py` is a one-line stub. This chunk makes it the
deterministic sampling engine: it takes already-persisted raw discovery
observations for one run and category, keeps only the validated canonical
identities resolved by Chunk 1, orders them by the stable discovery ordinal,
applies census behaviour at `N <= 100` and four contiguous ordinal strata above
100, selects within each stratum by a SHA-256 digest over
`sampling_rule_version + NUL + category + NUL + asset_identity_key`, and returns
a fully typed, pure result carrying every value later chunks need — census flag,
`sampling_basis`, `sample_fraction`, per-stratum `N_h`/`n_h`/ordinal boundaries,
selected identity keys, per-member selection digests, and reduced-stratum
counts. It persists nothing: the pure result is the contract, and Chunk 4B
materializes it. No RNG, no clock, no I/O, and no fabricated zeros.

## 2. Scope

### In scope

- Canonical population construction for one `(run_id, category)` from
  discovery observations: keep only rows whose canonical identity resolved
  (`asset_identity_key` non-null, not a duplicate), deduplicate by identity,
  retain the first valid discovery ordinal, and record the collapse count.
- Ordinal ordering: population ordered ascending by retained discovery ordinal,
  ties broken deterministically by identity key.
- Census behaviour for canonical population `N <= 100`: single stratum holding
  ordinals `1..N`, all canonical assets selected, `sample_is_census = True`,
  `sampling_basis = "census"`, `sample_fraction = 1.0` for non-empty, `null` for
  `N == 0`.
- Four-stratum behaviour for `N > 100`: contiguous ordinal strata with
  boundaries `floor(h*N/4)+1 .. floor((h+1)*N/4)`, 1-based, final stratum
  receiving any remainder; per-stratum target of 25 selections.
- Reduced strata: any stratum with fewer than 25 eligible assets selects all of
  them and records the reduced target count.
- SHA-256 NUL-delimited digest per candidate; sort by `(digest,
  asset_identity_key)`; select the first `SAMPLE_PER_STRATUM`.
- Typed, frozen result structures (`CanonicalPopulation`, `SamplingStratum`,
  `SampledMember`, `CategorySamplingResult`, `RunSamplingResult`) carrying every
  value the persistence layer later needs, with the persistence columns'
  per-member `sample_rank_within_stratum` assigned 1-based from the stratification
  order defined here.
- Digest rule-version sensitivity: changing the sampling-rule version changes
  the digest and therefore the selection for a large category.

### Explicitly out of scope (and who owns it instead)

- **Persistence of `sample_members`, sampling summaries, per-stratum `N_h`,
  `n_h`, usable-count placeholders, and overlap counts.** Chunk 4A is the
  *supporting contract chunk* and *pure calculation* for `LREQ-SMP-080`; the
  **primary implementation chunk is Chunk 4B** (completion chunks 4B and 6B).
  `LREQ-SMP-080` is **not** claimed as complete here — this chunk returns a pure
  result and performs no SQLite materialization. Chunk 6B later finalizes
  `u_demand_h`, `u_recent_h`, and `u_quality_h`.
- **Cross-category overlap counts and percentages.** Overlap is computed after
  all category samples are selected (Chunk 4B). `RunSamplingResult` carries no
  overlap field.
- **Usable counts (`u_demand_h`, `u_recent_h`, `u_quality_h`).** These depend on
  enrichment eligibility (Chunks 6B and 7A). Chunk 4A must **not** emit a
  fabricated `0` for them; it emits nothing, and 4B writes explicit pending
  placeholders.
- **Identity resolution and duplicate marking.** Chunk 1 (`resolve_canonical_identity`)
  and Chunk 3 (`discover_category`) produce them. Chunk 4A consumes
  `asset_identity_key`, `is_duplicate`, and `discovery_ordinal`; it does not
  re-resolve, re-canonicalize, or re-mark duplicates, and does not write them
  back through `update_raw_discovery_identity` (no I/O).
- **Strata `N_h`/`n_h` construction for metric purposes.** Chunk 4A computes the
  stratum geometry from ordinals; strata *eligibility* and `N_h`/`n_h` weighting
  in estimators are Chunks 7A/7B (LREQ-MET-030, MET-050, MET-060, MET-100).
  `stratum_index` is what ties the two together, and this chunk defines it.
- **Sampling constants becoming configurable.** `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`,
  `SAMPLE_STRATA`, and `SAMPLE_PER_STRATUM` are fixed for lean v1; they are read
  from `models.py` and never exposed as parameters (LREQ-SMP-030).
- **Pipeline orchestration, run rejection, warnings, and report wording.**
  Chunks 10/11/12. This chunk returns typed results and emits no `WarningCode`.
- **Preflight selection.** `preflight_selected` on a `SampleMemberRecord` is
  Chunk 6A's decision. Chunk 4A returns members; it does not select preflight
  assets and does not populate that field.
- **Traceability-validator widening** — Chunk 13 (`LREQ-NFR-060`).

## 3. Requirements this chunk must satisfy

Ownership roles are the exact labels from
`Documents/requirements-dependency-map.md` "Ownership and test traceability
matrix" (lines 45–136). Normative text is quoted from
`Documents/SRS-lean.md` §5.1 unless noted.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-SMP-010 | **Primary implementation chunk**; supporting chunks Chunk 1, 2, 3; completion Chunk 4A. Required tests `LREQ-TST-020`, `LREQ-TST-080`. (Matrix line 74.) | "**LREQ-SMP-010**: Sampling SHALL occur only after canonical discovery identities have been resolved and duplicates have been marked." (SRS §5.1.) Chunk 4A's share: the population builder consumes only canonical-resolved, non-duplicate observations and never fabricates an identity. | §5.1 |
| LREQ-SMP-020 | **Primary implementation chunk**; supporting chunk Chunk 3; completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 75.) | "**LREQ-SMP-020**: The canonical population for a category SHALL be ordered by the stable discovery ordinal assigned during collection. If the endpoint repeats or reorders a record, the first valid ordinal is retained and the duplicate is recorded separately." (SRS §5.1.) | §5.1 |
| LREQ-SMP-030 | **Primary implementation chunk**; supporting chunk Chunk 0; completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 76.) | "**LREQ-SMP-030**: Default sampling constants SHALL be: `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100`, `SAMPLE_STRATA = 4`, `SAMPLE_PER_STRATUM = 25`, `MIN_USABLE_SAMPLES_PER_STRATUM = 5`." … "For lean v1, these sampling constants are fixed… `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = SAMPLE_STRATA * SAMPLE_PER_STRATUM`. Changing the sample size, stratum count, or per-stratum allocation requires a new sampling-rule version and SRS revision; an implementation SHALL not expose one of these values as independently configurable." (SRS §5.1.) | §5.1 |
| LREQ-SMP-040 | **Primary implementation chunk**; supporting chunk Chunk 0; completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 77.) | "**LREQ-SMP-040**: A category with at most 100 canonical discovered assets SHALL be fully enriched. Its `sample_is_census` flag SHALL be true." (SRS §5.1.) | §5.1 |
| LREQ-SMP-050 | **Primary implementation chunk**; supporting chunk Chunk 4A (self); completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 78.) | "**LREQ-SMP-050**: A category with more than 100 canonical discovered assets SHALL be divided into four contiguous ordinal strata of approximately equal population size. The implementation SHALL select 25 assets from each stratum." … "For a large category with canonical population size `N`, stratum `h` (zero-based) SHALL contain ordinals `floor(h*N/SAMPLE_STRATA)+1` through `floor((h+1)*N/SAMPLE_STRATA)`. The final stratum receives any remainder. A census category SHALL use one stratum containing ordinals `1..N`." (SRS §5.1.) | §5.1 |
| LREQ-SMP-060 | **Primary implementation chunk**; supporting chunk Chunk 4A (self); completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 79.) | "**LREQ-SMP-060**: Selection within each stratum SHALL compute a SHA-256 digest of the UTF-8 encoding of the three values joined by a NUL delimiter: `sampling_rule_version + NUL + category + NUL + asset_identity_key`. Assets SHALL be sorted by `(digest, asset_identity_key)` and the first `SAMPLE_PER_STRATUM` assets SHALL be selected. The implementation SHALL NOT use an unseeded random generator or platform-dependent hash function." (SRS §5.1.) | §5.1 |
| LREQ-SMP-070 | **Primary implementation chunk**; supporting chunk Chunk 4A (self); completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 80.) | "**LREQ-SMP-070**: A large-category sample SHALL include assets from early, middle, and late discovery positions. Selecting only the first page or first 100 results is non-conforming." (SRS §5.1.) | §5.1 |
| LREQ-SMP-090 | **Primary implementation chunk**; supporting chunk Chunk 4A (self); completion Chunk 4A. Required test `LREQ-TST-020`. (Matrix line 82.) | "**LREQ-SMP-090**: If a stratum contains fewer than 25 assets, all assets in that stratum SHALL be eligible for selection and the reduced count SHALL be reported." (SRS §5.1.) | §5.1 |

### Supporting/consumed requirements (not owned; contract must match)

| LREQ ID | Role here | What this chunk consumes | SRS section |
|---|---|---|---|
| LREQ-EXT-060 | Consumed upstream contract (primary owner Chunk 3; completion Chunk 3). | Canonical identity resolution outcome; `asset_identity_key` is non-null only for `resolved`. Chunk 4A never re-derives it. | §4.1 |
| LREQ-EXT-070 | Consumed upstream contract (primary owner Chunk 1). | "Conflicting candidates, unresolved candidates, exclusion from denominator and enrichment" — a `conflict`/`unresolved` record is never an ordinary asset and must be excluded from the canonical population. | §4.1 |
| LREQ-EXT-080 | Consumed upstream contract (primary owner Chunk 3). | Exact category-path matching decides which observations belong to the category; Chunk 4A does not re-match paths. | §4.1 |
| LREQ-SMP-080 | **Boundary only** — Chunk 4A is pure calculation; primary implementation is Chunk 4B (completion 4B, 6B). | Chunk 4A returns every value 4B persists (`sampling_basis`, `sample_fraction`, `N_h`, `n_h`, boundaries, selected keys, per-member digests, census flag) as typed fields, and computes no usable counts. | §5.1 |

## 4. Interface contracts consumed

Copied from the frozen interface files; none is redefined here.

**From Chunk 0 (`niche_scout.models`, interface §2–§3):**

```python
SAMPLING_RULE_VERSION: str = "1.0.0"          # models.py declares "1.0.0"
IDENTITY_MAPPING_RULE_VERSION: str = "1.0.1"
ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY: int = 100
SAMPLE_STRATA: int = 4
SAMPLE_PER_STRATUM: int = 25
MIN_USABLE_SAMPLES_PER_STRATUM: int = 5

class SamplingBasis(str, Enum):
    CENSUS = "census"
    DETERMINISTIC_STRATIFIED_SAMPLE = "deterministic_stratified_sample"

class IdentityResolutionStatus(str, Enum):
    RESOLVED = "resolved"; UNRESOLVED = "unresolved"; CONFLICT = "conflict"
```

> **Version discrepancy, recorded not resolved.** `interfaces/chunk-00.md` §3
> and §7-Consumers list `SAMPLING_RULE_VERSION = "1.0.0"`, while the same file's
> §3 constant block line for `IDENTITY_MAPPING_RULE_VERSION` reads `"1.0.0"`.
> The live `src/niche_scout/models.py:26–27` reads
> `IDENTITY_MAPPING_RULE_VERSION = "1.0.1"` and `SAMPLING_RULE_VERSION = "1.0.0"`.
> Chunk 4A reads the constants from `models.py` and never re-declares them; the
> `interfaces/chunk-00.md` identity-version text is stale relative to the code
> (Chunk 3's `1.0.1` correction). This plan depends on `SAMPLING_RULE_VERSION`
> only, which agrees. No action assigned here; flagged as open question Q-1.

**From Chunk 1 (`niche_scout.validation`, interface §3–§5):**

```python
@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    canonical_identity_key: str | None
    status: IdentityResolutionStatus
    reason: str | None
    candidates: tuple[IdentityCandidate, ...]
    included_in_canonical_denominator: bool
    included_in_enrichment_set: bool
    mapping_rule_version: str
    issues: tuple[ValidationIssue, ...]
```
Frozen semantics relied on: "`canonical_identity_key` is non-`None` **only** for
`resolved`; a `conflict` or `unresolved` record always carries a non-`None`
`reason`, is excluded from both the canonical denominator and the enrichment
set, and is never returned as an ordinary asset." (`chunk-01.md` §3.) Chunk 4A
does not call `resolve_canonical_identity`; production callers pass the already
persisted `asset_identity_key`.

**From Chunk 3 (`niche_scout.collector_coveo`, interface §3/§6), the raw
observation shape:** Chunk 3 persists `RawDiscoveryObservationRecord` with
`discovery_ordinal` assigned "once per emitted record (monotonic, zero-based,
per run and category, in emission order)", `asset_identity_key` non-null only
for `resolved`, `stratum_index` always `None` at discovery time, and duplicates
persisted as their own rows with `is_duplicate=True` and
`duplicate_of_observation_id` pointing at the first row (`chunk-03.md` §6).
Chunk 4A consumes `discovery_ordinal`, `asset_identity_key`, and `is_duplicate`.

**From Chunk 2 (`niche_scout.database`), read-only shape only:** `SampleMemberRecord`
fields (`stratum_index`, `stratum_start_ordinal`, `stratum_end_ordinal`,
`sample_rank_within_stratum`, `sample_is_census`, `selection_digest`), and
`get_sample_members` ordering "by `stratum_index` ASC then
`sample_rank_within_stratum` ASC" (`chunk-02.md` §2.8). Chunk 4A **imports no
database module**; the ordering convention informs what the pure result must
carry.

### 4.1 Input the production caller supplies

Chunk 4A is pure and receives already-read, typed observations. The frozen
`RawDiscoveryObservationRecord` (§6.2 of the SRS) is the persisted shape; the
in-memory population input is defined locally (see §5.2) as
`DiscoveryPopulationRecord`, so that `sampling.py` can accept a projection
without importing `database` and without requiring every persisted column.
Callers construct these from `SqliteRepository.iter_raw_discovery_observations`
or `stream_raw_discovery_observations` (Chunk 2) — that read is I/O and stays in
Chunk 10.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-4A.md` verbatim once frozen.
Everything lives in `src/niche_scout/sampling.py`. All names are additive:
nothing in `models.py`, `validation.py`, `config.py`, or `database.py` is
redefined or shadowed.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/sampling.py` | **Pure** | Canonical population construction, ordering, strata, digest selection, and summary structures only. No I/O, no clock, no randomness, no `sqlite3`, no package I/O module import. |

- `sampling.py` may import `hashlib`, `math` (only `floor`/`ceil` if needed),
  `dataclasses`, `enum`, `collections.abc`, and `typing`, plus `models`. It SHALL
  NOT import `collector`, `collector_coveo`, `collector_graphql`, `database`,
  `pipeline`, `report`, `cli`, `config`, `metrics`, or `scoring`, and SHALL NOT
  import any filesystem/process/network/clock module. `hashlib` is permitted
  because it is a pure in-memory digest, exactly as `validation.py`'s permitted
  `json`; the module must be added to `check_import_boundaries.PURE_MODULES` or
  a dedicated purity test written (see §9 T-PURITY).
- Determinism: identical observations plus an identical `sampling_rule_version`
  produce structurally identical results. No set/dict iteration order affects
  output; all orderings have an explicit total tie-break.
- Null, zero, invalid, and unavailable stay distinct. `sample_fraction` is `1.0`
  for a non-empty census and `null` for a zero population — never `0.0` for an
  empty category. Reduced counts are reported, never silently filled to 25.
- No `WarningCode` is emitted and no warning is persisted.

### 5.1 Constants and vocabularies

```python
#: Re-exported from models for downstream convenience; NOT re-declared values.
SAMPLING_RULE_VERSION: str          # from models
SAMPLE_STRATA: int = 4              # from models
SAMPLE_PER_STRATUM: int = 25        # from models
ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY: int = 100   # from models
CENSUS_POPULATION_THRESHOLD: int = ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY   # 100
NUL_DELIMITER: str = "\x00"
```

`CENSUS_POPULATION_THRESHOLD` is derived from the frozen
`ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` so the `<= 100` census boundary can never
drift from the constants (LREQ-SMP-030/SMP-040). No new numeric literal is
introduced.

### 5.2 Typed input structure

```python
@dataclass(frozen=True, slots=True)
class DiscoveryPopulationRecord:
    """One persisted raw discovery observation, projected for sampling.

    `discovery_ordinal` is the stable 0-based ordinal assigned during
    collection by Chunk 3. `asset_identity_key` is non-None only for a
    `resolved` identity (LREQ-EXT-060/EXT-070). `is_duplicate` is True for a
    repeated canonical record whose first occurrence carries the retained
    ordinal (LREQ-SMP-020).
    """
    discovery_ordinal: int
    asset_identity_key: str | None
    is_duplicate: bool = False
```

> **Q-2 ruling applied (2026-09-20).** The three-field projection stands. The
> input SHALL NOT gain an `identity_resolution_status` field. Exclusion is on
> `asset_identity_key is None` only, and a conflict row is folded into
> `excluded_unresolved_count` exactly as an unresolved row is. Human ruling
> chose option (a).

Null/edge-case contract:
- `asset_identity_key is None` → the record is excluded from the canonical
  population and counted in `excluded_unresolved_count`.
- `is_duplicate is True` → excluded from the canonical population and counted in
  `excluded_duplicate_count`, even when `asset_identity_key` is non-null;
  a *first* valid ordinal is the one retained (LREQ-SMP-020).
- A record with the same `asset_identity_key` as an earlier retained record
  (not flagged `is_duplicate`) → the earlier (lower-ordinal) record is retained
  and the later is counted in `collapsed_repeat_count`. This is the
  "first valid ordinal is retained" rule applied when the flag is absent.
- `discovery_ordinal` must be a non-negative `int`; a `bool` is rejected with
  `ValueError` (`bool` is an `int` subclass in Python and is never an ordinal).
  Negative ordinals raise `ValueError`. A non-`int` raises `ValueError`.
- Empty string / whitespace-only `asset_identity_key` → `ValueError`: an
  unidentifiable asset is never silently included or silently dropped.

### 5.3 Typed result structures

```python
@dataclass(frozen=True, slots=True)
class CanonicalPopulation:
    """The ordered canonical population for one (run_id, category).

    The ordering is LREQ-SMP-020's: ascending retained discovery ordinal, ties
    broken by `(ordinal, asset_identity_key)`. `ordinals` is the 1-based
    position within this ordered population (position i has ordinal i+1), which
    is the ordinal space LREQ-SMP-050's stratum boundaries are expressed in.
    """
    category: str
    identity_keys: tuple[str, ...]          # ordered, unique; no duplicates
    retained_ordinals: tuple[int, ...]      # 0-based persisted ordinals, same order
    excluded_unresolved_count: int          # asset_identity_key is None (unresolved OR conflict)
    excluded_duplicate_count: int           # is_duplicate True
    collapsed_repeat_count: int             # same identity seen again, flag absent
    @property
    def size(self) -> int: ...              # len(identity_keys); NEVER a fabricated 0 on failure


@dataclass(frozen=True, slots=True)
class SamplingStratum:
    """One ordinal stratum.

    `stratum_index` is 0-based. `start_ordinal`/`end_ordinal` are 1-based
    inclusive positions in the canonical population (`LREQ-SMP-050`:
    `floor(h*N/4)+1 .. floor((h+1)*N/4)`; census: `1..N`). A stratum is always
    non-empty: `end_ordinal >= start_ordinal`.
    """
    stratum_index: int
    start_ordinal: int
    end_ordinal: int
    population_count: int                   # N_h
    selected_count: int                     # n_h actually selected
    target_count: int                       # SAMPLE_PER_STRATUM normally, else reduced
    is_reduced: bool                        # True iff population_count < SAMPLE_PER_STRATUM


@dataclass(frozen=True, slots=True)
class SampledMember:
    """One selected sample member, 1:1 with a future `sample_members` row."""
    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    sample_rank_within_stratum: int         # 1-based, assigned after (digest, key) sort
    sample_is_census: bool
    selection_digest: str                   # lowercase hex, 64 chars


@dataclass(frozen=True, slots=True)
class CategorySamplingResult:
    """The complete pure sampling outcome for one category."""
    category: str
    population: CanonicalPopulation
    strata: tuple[SamplingStratum, ...]
    members: tuple[SampledMember, ...]       # in (stratum_index, sample_rank) order
    sampling_basis: SamplingBasis
    sample_is_census: bool
    discovered_population_count: int         # == population.size
    enriched_sample_count: int               # == len(members), distinct identities
    sample_fraction: float | None            # 1.0 non-empty census; None when N == 0
    sampling_rule_version: str


@dataclass(frozen=True, slots=True)
class RunSamplingResult:
    """All category sampling results for one run, in caller-declared order.

    `by_category` preserves the input category order (never sorted by dict
    iteration) and is the ordering Chunk 4B iterates for persistence.
    """
    run_id: str
    sampling_rule_version: str
    categories: tuple[CategorySamplingResult, ...]
    @property
    def by_category(self) -> Mapping[str, CategorySamplingResult]: ...
    @property
    def enrichment_identity_keys(self) -> tuple[str, ...]:
        """Distinct selected identities across all categories, first-seen order.

        This is the union Chunk 6B enriches once; it is a convenience view and
        carries no overlap counts (overlap is Chunk 4B).
        """
```

> **Unresolved vs conflict split.** The SRS distinguishes "unresolved" from
> "conflicting" candidates (LREQ-EXT-070), but both are persisted with a
> **nullable** `asset_identity_key` (Chunk 3 sets it non-null only for
> `resolved`). Chunk 4A's population input therefore cannot separate the two and
> folds them into `excluded_unresolved_count`; the distinct
> `discovery_unresolved_identity_count` and `discovery_conflict_count` fields on
> `category_scores` (SRS §6.5) are computed by Chunk 10 from the persisted
> `identity_resolution_status` column, which Chunk 4A never reads.
>
> **Q-2 ruling applied (2026-09-20).** Confirmed as written: one
> `excluded_unresolved_count` field, no `identity_resolution_status` on the
> input, no `excluded_conflict_count` field on the result. Option (a).

Null/edge-case contract for the result structures:
- `sample_fraction` is `null` **iff** `discovered_population_count == 0`; it is
  `1.0` for every non-empty census; for a large category it equals
  `enriched_sample_count / discovered_population_count` and is normally `< 1.0`.
  It is never `0.0` for an empty category (LREQ-SMP-080). The denominator is the
  canonical `population.size` (`population.size == discovered_population_count`);
  see **Q-4 ruling applied (2026-09-20)** below.
- `members` contains no duplicate `asset_identity_key` for a category: the
  population is already identity-unique and selection draws from it once.
- `strata` is never empty when `population.size > 0`; for `size == 0` it is an
  empty tuple and `members` is empty.
- `SamplingStratum.is_reduced` is `True` iff `population_count < target_count`;
  `selected_count == population_count` in that case (LREQ-SMP-090).
- `sample_rank_within_stratum` is 1-based and contiguous `1..selected_count`
  within each stratum, ordered by `(selection_digest, asset_identity_key)` — for
  census members too. See **Q-6 ruling applied (2026-09-20)** below.
- Every member, census or sampled, carries the standard NUL-delimited digest; no
  census sentinel. See **Q-5 ruling applied (2026-09-20)** below.

> **Q-4 ruling applied (2026-09-20).** Canonical denominator confirmed:
> `sample_fraction = enriched_sample_count / population.size`, where
> `population.size` is the canonical discovered population after
> unresolved/conflict/duplicate exclusions. The raw-observation-count alternative
> is rejected.

> **Q-5 ruling applied (2026-09-20).** Option (a) confirmed: every census member
> carries the standard `selection_digest` computed by :func:`selection_digest`
> from `(sampling_rule_version, category, asset_identity_key)`. No sentinel value
> is stored on `sample_members.selection_digest`.

> **Q-6 ruling applied (2026-09-20).** Digest order confirmed:
> `sample_rank_within_stratum` is assigned by the `(selection_digest,
> asset_identity_key)` sort for census members exactly as for sampled members.
> The original-discovery-order alternative is rejected.

### 5.4 Public functions

```python
def selection_digest(
    category: str, asset_identity_key: str, *,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> str:
    """Return the lowercase hex SHA-256 of
    ``sampling_rule_version + NUL + category + NUL + asset_identity_key``
    encoded as UTF-8 (LREQ-SMP-060). Pure; no platform-dependent hash."""


def build_canonical_population(
    records: Sequence[DiscoveryPopulationRecord], *, category: str,
) -> CanonicalPopulation:
    """Order and deduplicate canonical identities (LREQ-SMP-010/020).

    Retains the lowest discovery ordinal per identity. `records` need not be
    sorted; output is ordered by `(retained_ordinal, asset_identity_key)`.
    An empty `records` yields an empty population with all counts 0.
    Raises ValueError for a malformed record (see §5.2).
    """


def build_strata(
    population: CanonicalPopulation, *,
    sample_strata: int = SAMPLE_STRATA,
    per_stratum_target: int = SAMPLE_PER_STRATUM,
    census_threshold: int = CENSUS_POPULATION_THRESHOLD,
) -> tuple[SamplingStratum, ...]:
    """Return ordinal strata for a population (LREQ-SMP-040/050/090).

    Census (``size <= census_threshold``): one stratum, ordinals ``1..N``,
    target ``per_stratum_target`` if that is below ``N`` else ``N``.
    Large: ``sample_strata`` contiguous strata with
    ``start = floor(h*N/sample_strata)+1``, ``end = floor((h+1)*N/sample_strata)``;
    the final stratum receives any remainder. Empty population → ``()``.
    """


def select_stratum_members(
    population: CanonicalPopulation, stratum: SamplingStratum, *,
    sample_is_census: bool, sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> tuple[SampledMember, ...]:
    """Select up to ``stratum.target_count`` members from ``stratum``.

    Candidates are the population identities at 1-based ordinals
    ``start_ordinal..end_ordinal``. Each is digested by :func:`selection_digest`;
    candidates are sorted by ``(digest, asset_identity_key)`` and the first
    ``target_count`` are selected, ranked 1-based in that order
    (LREQ-SMP-060, LREQ-SMP-090). Deterministic; no RNG.
    """


def select_category_sample(
    records: Sequence[DiscoveryPopulationRecord], *, category: str,
    run_id: str | None = None,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> CategorySamplingResult:
    """Full sampling pipeline for one category (LREQ-SMP-010 … SMP-070, SMP-090).

    Builds the canonical population, decides census vs four-stratum, selects
    members, and computes ``sampling_basis``, ``sample_is_census``,
    ``discovered_population_count``, ``enriched_sample_count``, and
    ``sample_fraction``. Pure. Emits no usable counts and no overlap fields.
    """


def select_run_sample(
    categories: Mapping[str, Sequence[DiscoveryPopulationRecord]], *,
    run_id: str, sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> RunSamplingResult:
    """Run-wide sampling over already-declared categories, preserving input order.

    Each category is sampled independently with
    :func:`select_category_sample`. ``run_id`` is echoed only for
    correlation; no persistence occurs. An empty mapping yields
    ``categories == ()``. The same ``run_id`` is not required to exist.
    Categories are emitted in the caller mapping's insertion order and are
    never sorted (Q-7 ruling applied 2026-09-20).
    """
```

> **Q-7 ruling applied (2026-09-20).** Caller order confirmed:
> `select_run_sample` preserves the caller mapping's insertion order in
> `RunSamplingResult.categories` and `by_category`; it does not sort categories
> lexically, and the SRS does not pin an order. The caller (Chunk 10) decides the
> declared category order.

Null/edge-case contract (LREQ-NFR-040 style — public functions carry type hints
and docstrings stating null/edge behaviour):
- Every function is pure: no clock, no randomness, no file/network/DB access,
  no mutation of its arguments.
- `category` that is empty or whitespace-only raises `ValueError` in
  `selection_digest`, `build_canonical_population`, and
  `select_category_sample`: the digest and the stratum boundary are category
  scoped and an empty category is never a silently shared bucket.
- `select_stratum_members` with `stratum.population_count == 0` returns `()`.
- `select_stratum_members` never returns more than `stratum.target_count`
  members and never fewer than `min(target_count, population_count)`.
- `build_strata` with `sample_strata < 1` or `per_stratum_target < 1` raises
  `ValueError`; the defaults are the frozen constants and production callers do
  not pass these parameters (LREQ-SMP-030: not independently configurable).
- `sample_fraction` is computed as a `float` division of ints and is `null`
  (not `0.0`) when `discovered_population_count == 0`.
- Two calls with identical inputs and an identical `sampling_rule_version`
  return structurally and numerically equal results.
- `select_run_sample` iterates the mapping in insertion order and never sorts
  categories; a duplicate category key is impossible in a mapping, and an empty
  mapping yields `categories == ()`.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/sampling.py` | modified | Replace the stub with the pure sampling engine (§5). No other module edited. |
| `tests/test_sampling.py` | new | Analytical tests §9; all but T-PURITY carry `@pytest.mark.lreq`. |
| `tests/fixtures/sampling_fixtures.py` | new | Population fixtures and hand-computed golden vectors (§9). Data only; no logic. |
| `tests/fixtures/__init__.py` | modified | Re-export `sampling_fixtures` alongside the existing four modules (interface `chunk-00.md` §9 convention). |
| `tests/traceability.json` | modified | Add the entries listed in §9.4. |

> **Q-8 ruling applied (2026-09-20) — correction.** The row previously listed
> here was: `| src/niche_scout/tools/check_import_boundaries.py | modified,
> **conditional** | Only if sampling.py must join PURE_MODULES for the purity
> gate (§9 T-PURITY) … needs the Q-8 ruling. |`. That row is **removed**: the
> human ruling chose option (b), so `src/niche_scout/tools/check_import_boundaries.py`
> is **NOT touched** by Chunk 4A. The purity check is the local AST test in
> `tests/test_sampling.py` (§9 T-PURITY).

No other file is edited. `models.py`, `validation.py`, `config.py`,
`database.py`, `collector*.py`, `src/niche_scout/tools/check_import_boundaries.py`,
and all existing tests and interface docs are untouched.

## 7. Task breakdown

Ordered checklist, each item tagged with the LREQ ID(s) it implements:

- [ ] Import the frozen constants from `models`; do not re-declare numeric values. (LREQ-SMP-030)
- [ ] Define `DiscoveryPopulationRecord`, `CanonicalPopulation`, `SamplingStratum`, `SampledMember`, `CategorySamplingResult`, `RunSamplingResult`. (§5)
- [ ] Implement `selection_digest` with `"\x00".join((rule_version, category, identity))` UTF-8 SHA-256, lowercase hex. (LREQ-SMP-060)
- [ ] Implement `build_canonical_population`: drop unresolved/conflict/duplicate rows, collapse repeated identities to the lowest ordinal, order by `(ordinal, identity)`. (LREQ-SMP-010, LREQ-SMP-020)
- [ ] Implement `build_strata`: census single stratum `1..N`; four contiguous strata by `floor` boundaries with remainder in the final stratum. (LREQ-SMP-040, LREQ-SMP-050)
- [ ] Implement `select_stratum_members`: digest, sort by `(digest, identity)`, take first target, rank 1-based, mark reduced. (LREQ-SMP-060, LREQ-SMP-090)
- [ ] Implement `select_category_sample`: assemble basis, census flag, counts, `sample_fraction`. (LREQ-SMP-030/040/050/070)
- [ ] Implement `select_run_sample` preserving caller category order. (§5.3)
- [ ] Confirm sample-selection coverage across early/middle/late positions for a stratum-spanning fixture. (LREQ-SMP-070)
- [ ] Write `tests/fixtures/sampling_fixtures.py` with the vectors in §9.2. (§9)
- [ ] Write `tests/test_sampling.py` with the markers in §9.3, the local AST purity check (purity gate, §5.0, Q-8 ruling), and add the `tests/traceability.json` entries. (§9.4)
- [ ] Run `python -m pytest tests/test_sampling.py -q`, then the full suite and the two tool commands. (§10)

## 8. Edge cases and invariants

From the dependency map's "Edge cases" column for every owned LREQ, plus the
chunk's own gate text:

- Sampling happens only after canonical identity resolution; conflict and
  unresolved records (both persisted with a null `asset_identity_key`) are
  excluded from the population and never re-entered (map line 197;
  LREQ-SMP-010; see Q-2 for the unresolved/conflict count split).
- The canonical population is ordered by category and discovery ordinal/rule
  (map line 198; LREQ-SMP-020). A repeated or reordered record keeps its first
  valid ordinal; the duplicate is recorded separately (SRS §5.1).
- Default sample size, four strata, threshold at 100, and per-stratum size are
  fixed constants and are not independently configurable (map line 199;
  LREQ-SMP-030).
- Populations of 0, 1, 99, and 100: all assets selected; zero-population
  fraction is `null` (map line 200; LREQ-SMP-040). `N == 101` is the first
  four-stratum population.
- Population above 100: contiguous ordinal boundaries; the final stratum
  receives any remainder (map line 201; LREQ-SMP-050).
- NUL-delimited digest; tie-break by identity; no random generator; a
  rule-version change changes the selection (map line 202; LREQ-SMP-060).
- Early, middle, and late discovery positions must be represented (map line
  203; LREQ-SMP-070). For `N = 101` the four strata are ordinal ranges
  `1..25`, `26..50`, `51..75`, `76..101`.
- A stratum below 25 selects every asset and records the reduced count (map
  line 205; LREQ-SMP-090). With the SRS's `floor` boundaries, a large category's
  smallest stratum is `floor(N/4)`, which is `>= 25` for every `N > 100`, so the
  reachable reduced case is the census stratum of a category with `N < 25`
  (e.g. `N = 24` → target 24, `is_reduced True`). **Q-3 ruling applied
  (2026-09-20):** option (a) confirmed — LREQ-SMP-090 applies to the census
  stratum and to any future non-equal stratification; the reduced-count test is
  written on a census category with `N < 25`. No large-category stratum below 25
  is expected or tested, and no boundary-rule revision is implied.
- `sample_fraction` and stratum eligibility coverage measure different
  properties and are distinct fields (map §5.6; acceptance criterion 22).
  Chunk 4A emits only `sample_fraction`.
- Missing is not zero: an empty category yields `discovered_population_count 0`
  with `sample_fraction None`, never `0.0`.
- The digest is over the *canonical* identity, not the raw URI value, and over
  the category string as supplied; the same identity in two categories yields
  two different digests (category is a digest input), so per-category selection
  is independent and deterministic.

## 9. Test plan

### 9.1 Test files

- `tests/test_sampling.py` (new) — all tests except T-PURITY carry
  `@pytest.mark.lreq("LREQ-...")`.
- `tests/fixtures/sampling_fixtures.py` (new) — population builders and golden
  vectors. Inert data/factories only; no assertions, no logic under test.

### 9.2 Golden vectors and fixtures (hand-computed where the SRS pins them)

The digest vectors are computed from the SRS-pinned formula
`s = f"{rule_version}\0{category}\0{asset_identity_key}".encode("utf-8")`;
`hashlib.sha256(s).hexdigest()`. The test author computes and freezes each
64-char hex value, then cross-checks the implementation against the literal.

- **Fixture A — census boundaries**: four separate populations of exactly 0, 1,
  99, and 100 synthetic identities with ordinals `0..N-1`. Expected:
  `sample_is_census True` for 1/99/100, `sampling_basis == "census"`,
  `len(members) == N`; for `N == 0`: `sampling_basis == "census"`,
  `sample_is_census True`, `len(members) == 0`,
  `sample_fraction is None`. For `N == 1/99/100`: `sample_fraction == 1.0`
  exactly.
- **Fixture B — first four-stratum population**: `N = 101`, ordinals `0..100`.
  Expected strata: `(0, 1, 25, 25)`, `(1, 26, 50, 25)`, `(2, 51, 75, 25)`,
  `(3, 76, 101, 26)`. All four strata are non-reduced; each selects 25;
  `len(members) == 100`; `sample_fraction == 100/101` and is `< 1.0`.
- **Fixture C — remainder belongs to the final stratum**: `N = 200`. Expected
  `floor(h*200/4)+1 .. floor((h+1)*200/4)` → `1..50`, `51..100`, `101..150`,
  `151..200`; every stratum selects 25 of 50.
- **Fixture D — reduced stratum**: the SRS pins reduction only below 25. With
  `floor` boundaries a large category's smallest stratum is `floor(N/4) >= 25`
  for all `N > 100`, so the reachable reduced case is a **census** category with
  `N = 24`: expected one stratum `(index 0, start 1, end 24, population_count 24,
  target_count 24, selected_count 24, is_reduced True)`, `len(members) == 24`,
  `sample_fraction == 1.0`, `sample_is_census True`. Boundary companions:
  `N = 25` → `target_count 25`, `is_reduced False`; `N = 1` → `target_count 1`,
  `is_reduced True`. Also record `N = 105` strata `1..26`, `27..52`, `53..78`,
  `79..105` (each selects 25, none reduced) as the large-category companion.
  **Q-3 ruling applied (2026-09-20):** this census-stratum reading is confirmed,
  the reduced-count test is written here, and no large-category stratum below 25
  is expected.
- **Fixture E — digest determinism and rule-version sensitivity**: one
  population of `N = 101` sampled with `sampling_rule_version="1.0.0"` and again
  with `"1.0.1"` (a test-local string). Expected: at least one stratum's
  selected key set differs, and every member's `selection_digest` differs
  between the two rule versions for the same `(category, key)`. Also assert the
  identical-input repeat is byte-identical across two calls.
- **Fixture F — digest literal**: for
  `(rule_version="1.0.0", category="3D/Characters", key="12345")`, the frozen
  literal is the SHA-256 of
  `b"1.0.0\x003D/Characters\x0012345"`. The test author computes the value once
  and asserts equality; this pins the NUL delimiter and UTF-8 encoding.
- **Fixture G — overlap across categories**: the same identity key appears in
  two categories. Expected: it may appear in both category samples (selection
  is per category), and `RunSamplingResult.enrichment_identity_keys` lists it
  once. No overlap percentage is produced by Chunk 4A.
- **Fixture H — exclusion**: a population containing an unresolved row
  (`asset_identity_key None`), a duplicate row (`is_duplicate True`), and a
  repeated identity without the flag. Expected: `N` counts only canonical
  non-duplicate identities; `excluded_unresolved_count` (conflict rows included;
  Q-2 ruling: one field, no separate conflict count), `excluded_duplicate_count`,
  and `collapsed_repeat_count` are as specified.
- **Fixture I — early/middle/late representation**: `N = 101`; assert the
  selected keys include at least one key from ordinal ranges `1..25`, `26..50`,
  `51..75`, and `76..101` (one per stratum suffices). Also assert the union of
  the selected keys is not a prefix of the population.
- **Fixture J — malformed input**: empty/whitespace `category`; negative or
  non-`int` `discovery_ordinal`; whitespace-only `asset_identity_key`. Expected
  `ValueError` in each case, with no `0` ordinal and no empty-string identity
  substituted.

### 9.3 Test list, mapped to LREQ IDs

| Node (base pytest node ID) | Purpose | LREQ ID(s) |
|---|---|---|
| `test_digest_matches_nul_delimited_sha256_literal` | NUL-delimited UTF-8 SHA-256 literal (Fixture F) | LREQ-SMP-060 |
| `test_digest_changes_with_rule_version` | Rule-version sensitivity (Fixture E) | LREQ-SMP-060 |
| `test_repeated_selection_is_identical` | Determinism across calls | LREQ-SMP-060, LREQ-SMP-050 |
| `test_no_randomness_module_used` | Source/AST check: no `random`, no clock, no I/O import in `sampling.py` | LREQ-SMP-060, LREQ-ARCH-020 |
| `test_census_population_sizes_zero_one_99_100` | Census at 0/1/99/100 (Fixture A, parametrized) | LREQ-SMP-040 |
| `test_census_selects_all_assets` | All canonical assets selected | LREQ-SMP-040 |
| `test_zero_population_fraction_is_null_not_zero` | `sample_fraction is None`, never `0.0` | LREQ-SMP-040 |
| `test_census_sample_fraction_is_exactly_one` | `sample_fraction == 1.0` for non-empty census | LREQ-SMP-040 |
| `test_four_strata_boundaries_at_101` | Four-stratum boundaries, remainder final (Fixture B) | LREQ-SMP-050 |
| `test_four_strata_boundaries_at_200` | Equal-population boundaries (Fixture C) | LREQ-SMP-050 |
| `test_strata_are_contiguous_and_cover_population` | No gap/overlap; union is `1..N` | LREQ-SMP-050 |
| `test_large_category_targets_25_per_stratum` | 25 selected per non-reduced stratum | LREQ-SMP-050 |
| `test_population_ordered_by_discovery_ordinal` | Ordinal ordering (LREQ-SMP-020) | LREQ-SMP-020 |
| `test_first_valid_ordinal_retained_for_repeat` | Repeat keeps lowest ordinal (Fixture H) | LREQ-SMP-020 |
| `test_unresolved_and_conflict_excluded` | Unresolved/conflict never in population | LREQ-SMP-010 |
| `test_duplicate_row_excluded_and_counted` | `is_duplicate` excluded, counted | LREQ-SMP-010 |
| `test_reduced_stratum_selects_all_and_reports_reduced_count` | Reduced-count path (Fixture D) | LREQ-SMP-090 |
| `test_early_middle_late_positions_represented` | Position coverage (Fixture I) | LREQ-SMP-070 |
| `test_sample_is_not_first_page_prefix` | Selection is not the first 100/`PAGE_SIZE` | LREQ-SMP-070 |
| `test_sampling_basis_and_census_flag` | `census` vs `deterministic_stratified_sample` | LREQ-SMP-030, LREQ-SMP-040 |
| `test_default_constants_are_not_configurable` | Constants read from `models`; no parameter overrides in production path | LREQ-SMP-030 |
| `test_malformed_population_input_raises_value_error` | Fixture J | LREQ-SMP-010 |
| `test_no_duplicate_membership_within_category` | Distinct identities in `members` | LREQ-SMP-010 |
| `test_run_sample_preserves_category_order` | Caller mapping order preserved (Q-7 ruling) | LREQ-SMP-010 |
| `test_shared_identity_appears_in_both_categories` | Per-category independence; union dedups (Fixture G) | LREQ-SMP-010 |
| `test_sample_fraction_distinct_from_stratum_aggregates` | `sample_fraction` is its own field; no coverage field emitted | LREQ-SMP-080 |
| `test_census_member_ranks_follow_digest_order` | Census ranks by `(digest, identity)` (Q-6 ruling) | LREQ-SMP-060 |
| `test_census_member_digest_is_standard_nul_digest` | Census digest is the standard digest, no sentinel (Q-5 ruling) | LREQ-SMP-060 |

`test_sampling_module_imports_are_pure` (T-PURITY) is the **local AST purity
check required by the Q-8 ruling** (2026-09-20), not an analytical test; it is
exempt from `@pytest.mark.lreq` and from `tests/traceability.json`, following
the `chunk-03.md` §6 exemption precedent. It asserts `sampling.py` imports no
forbidden module and reads no clock, replacing the conditional edit to
`src/niche_scout/tools/check_import_boundaries.py` that the Q-8 ruling removed.

### 9.4 `tests/traceability.json` entries to add

Each new node ID maps to the individual LREQ IDs it exercises, per §9.3. The
`LREQ-TST-020` marker is **not** attached by Chunk 4A: the matrix assigns
`LREQ-TST-020`'s primary owner to Chunk 13 with Chunks 4A/4B as supporting
chunks, and Chunk 2's `chunk-02.md` §5 records the same deliberate non-attachment
(`LREQ-TST-040`/`TST-020` belong to the files their own chunks own). Closure of
`LREQ-TST-020` happens in Chunk 13.

Example entry shape (the test author adds one line per §9.3 row):

```json
{
  "tests/test_sampling.py::test_digest_matches_nul_delimited_sha256_literal": ["LREQ-SMP-060"],
  "tests/test_sampling.py::test_census_population_sizes_zero_one_99_100": ["LREQ-SMP-040"],
  "tests/test_sampling.py::test_reduced_stratum_selects_all_and_reports_reduced_count": ["LREQ-SMP-090"]
}
```

### 9.5 Fixtures

`tests/fixtures/sampling_fixtures.py` provides: `population(n, prefix)` factory
producing `N` `DiscoveryPopulationRecord`s with ordinals `0..n-1`; the census
vectors A; the large vectors B, C, D, E, F, I; the exclusion vector H; the
shared-identity vector G; and the malformed-input cases J. `tests/fixtures/__init__.py`
re-exports the module. No fixture contains credentials (LREQ-SEC-020).

## 10. Definition of done (gate)

Copied verbatim from the dependency map's Chunk 4A Gate section
(`Documents/requirements-dependency-map.md`, lines 594–601):

- Repeated selection is identical.
- Changing the sampling-rule version changes the digest/selection.
- Populations 0, 1, 99, 100, and greater than 100 behave exactly as specified.
- Early, middle, and late discovery positions are represented.
- Sample fraction remains distinct from stratum eligibility coverage.
- The pure result includes all values required for later persistence, but this
  chunk does not claim physical SQLite materialization.

## 11. Explicit prohibitions

- `sampling.py` SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, `config`,
  `metrics`, or `scoring`, nor any filesystem, process, network, or clock module.
- `sampling.py` SHALL NOT read the system clock and SHALL NOT use `random`,
  `secrets`, `uuid`, or any unseeded or platform-dependent hash.
- `sampling.py` SHALL NOT perform persistence, open a SQLite connection, write a
  file, or emit a log line. `LREQ-SMP-080` materialization is Chunk 4B.
- `sampling.py` SHALL NOT expose `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`,
  `SAMPLE_STRATA`, `SAMPLE_PER_STRATUM`, or the census threshold as
  independently configurable values (LREQ-SMP-030). The optional keyword
  parameters in §5.4 exist for analytical tests and default to the frozen
  constants; no caller-supplied config path reaches them.
- `sampling.py` SHALL NOT fabricate a `0` for a missing value: no `or 0`,
  `.get(k, 0)`, `fillna(0)`, or default-0 parameter. An empty category yields
  `sample_fraction None`, not `0.0`.
- `sampling.py` SHALL NOT emit `u_demand_h`, `u_recent_h`, or `u_quality_h`, and
  SHALL NOT emit overlap counts or percentages.
- `sampling.py` SHALL NOT re-resolve, re-canonicalize, or re-mark identities;
  Chunks 1 and 3 own that.
- `sampling.py` SHALL NOT select preflight assets or populate
  `preflight_selected`; Chunk 6A owns that.
- This chunk SHALL NOT edit `models.py`, `validation.py`, `config.py`,
  `database.py`, the collector modules, `src/niche_scout/tools/check_import_boundaries.py`
  (Q-8 ruling), or any interface document.
- This chunk SHALL NOT add any out-of-scope capability (scheduling,
  resume/checkpoint, historical trends, configurable weights, alternative
  collection strategies, confidence intervals).

## 12. Open questions — RESOLVED by human rulings, 2026-09-20

All eight questions below were ruled on by a human on 2026-09-20, each choosing
the option this plan recommended. No question remains open; the plan is frozen on
these rulings. Each entry records the question as previously written, the ruling,
and where in this plan the ruling is applied. The corrections above are dated and
marked, not silent substitutions of the pre-ruling text.

1. **Q-1 — `interfaces/chunk-00.md` identity-version text is stale.** *RULED
   2026-09-20: option (a).* `interfaces/chunk-00.md` §3 and §7 list
   `IDENTITY_MAPPING_RULE_VERSION = "1.0.0"`, but `src/niche_scout/models.py:26`
   reads `"1.0.1"`. Ruling: leave the stale interface text as-is, record it for
   Chunk 13's document-consistency pass, and do not edit the interface file.
   Applied: Chunk 4A takes nothing from that constant (it uses
   `SAMPLING_RULE_VERSION`, which agrees); no interface file is touched (§6).

2. **Q-2 — what does "conflict" mean at the population input?** *RULED
   2026-09-20: option (a).* Exclude purely on `asset_identity_key is None`;
   report one `excluded_unresolved_count` field; do NOT add
   `identity_resolution_status` to `DiscoveryPopulationRecord`; the three-field
   projection stands; no `excluded_conflict_count` field is added.
   Applied: §5.2 (input) and §5.3 (result) with dated ruling notes; §8, §9
   Fixture H.

3. **Q-3 — is a large-category stratum ever below 25?** *RULED 2026-09-20:
   option (a).* LREQ-SMP-090 applies to the census stratum and to any future
   non-equal stratification; the reduced-count test is written on a census
   category with `N < 25`; no boundary-rule revision is implied.
   Applied: §8 and §9 Fixture D with dated ruling notes; test
   `test_reduced_stratum_selects_all_and_reports_reduced_count` is written on
   Fixture D's `N = 24` census case.

4. **Q-4 — `sample_fraction` denominator.** *RULED 2026-09-20: canonical.*
   The denominator is the canonical `population.size` (==
   `discovered_population_count`); the raw-observation-count alternative is
   rejected. Applied: §5.3 null/edge contract with a dated ruling note.

5. **Q-5 — `SampledMember.selection_digest` for census categories.** *RULED
   2026-09-20: option (a).* Every census member carries the standard
   NUL-delimited digest from :func:`selection_digest`; no sentinel value is
   stored. Applied: §5.3 with a dated ruling note; test
   `test_census_member_digest_is_standard_nul_digest`.

6. **Q-6 — `sample_rank_within_stratum` for census members.** *RULED
   2026-09-20: digest order.* Census ranks are assigned by the
   `(selection_digest, asset_identity_key)` sort; the original-discovery-order
   alternative is rejected. Applied: §5.3 with a dated ruling note; test
   `test_census_member_ranks_follow_digest_order`.

7. **Q-7 — where the run-wide category list comes from.** *RULED 2026-09-20:
   caller order.* `select_run_sample` preserves the caller mapping's insertion
   order and does not sort categories. Applied: §5.4 (`select_run_sample`
   docstring + dated ruling note) and §5.4 null/edge contract; test
   `test_run_sample_preserves_category_order`.

8. **Q-8 — purity-tool registration.** *RULED 2026-09-20: option (b).*
   Chunk 4A writes the local AST purity check in `tests/test_sampling.py`
   (`test_sampling_module_imports_are_pure`) and does **not** edit
   `src/niche_scout/tools/check_import_boundaries.py`.
   Applied: §6 — the conditional purity-tool row is removed and the file is
   listed as untouched; §7 checklist; §9.3 T-PURITY note; §11 prohibition.
