# Chunk 4A — Canonical populations and deterministic sampling engine (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md`
(Status: FROZEN; §5 reproduced below verbatim, including its ruling notes).
Verified at: branch `chunk-4A`, gate commit `bce4e06`; `Documents/runs/chunk-4A.md`
records `GATE: PASSED` (lines 161–184) with `python -m pytest -q` → 185 passed,
`python -m niche_scout.tools.validate_traceability` → exit 0 (176 matrix nodes,
89 defined LREQ IDs), `python -m ruff format --check` / `ruff check` clean on the
chunk's three files.

This file is the **public contract** other chunks build against. It is the
frozen 4A plan §5 ("Interface contract this chunk produces") reproduced
verbatim — that section declares "This section becomes
`Documents/interfaces/chunk-4A.md` verbatim once frozen" — with the plan's
Q-2/Q-4/Q-5/Q-6/Q-7/Q-8 ruling notes included. Nothing below is redefined:
`sampling.py` is pure and Chunk 4B consumes these names and semantics unchanged.

**Human ruling Q-6, Chunk 4B, 2026-09-20:** the lead creates this file from the
frozen 4A plan §5 before freezing 4B, rather than freezing 4B against a
non-existent dependency file. The rulings recorded below are the 4A human
rulings of 2026-09-20 and are not restated or re-scoped here.

---

## 5. Interface contract this chunk produces

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

## 4A-1. Divergence from the 4A plan text recorded at verification (not a contract change)

The 4A run log records two implementation facts that the frozen plan text does
not itself state and that consumers must know; both were verified against the
live module and the committed tests (`Documents/runs/chunk-4A.md` lines 79–102,
134–159, 161–184):

- `SamplingStratum.is_reduced` is implemented as
  `population_count < SAMPLE_PER_STRATUM` (the block comment here reads
  `target_count`; at the default constants the two are the same predicate, and
  the plan's §5.3 line and §9.2 Fixture D agree with the implementation).
- `select_run_sample` accepts raw observation mappings and coerces them to
  `DiscoveryPopulationRecord`; the run-level fixture tests rely on that.

`sampling.py:19-31` imports only `hashlib`, `collections.abc`, `dataclasses`,
and `niche_scout.models`; the module is pure.
