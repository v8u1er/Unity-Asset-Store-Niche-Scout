# Chunk 4B — Sample persistence, overlap, and sampling summaries (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-4B-sample-persistence-overlap-and-sampling-summaries.md`
(Status: FROZEN; §5 reproduced below).
Verified at: branch `chunk-4B`, gate commit `ddc8827`; `Documents/runs/chunk-4B.md`
records `GATE: PASSED` (gate table and `GATE: PASSED` line, `Documents/runs/chunk-4B.md`
lines 184–209) with `python -m pytest -q` → 216 passed, `python -m niche_scout.tools.validate_traceability`
→ exit 0 (207 matrix nodes, 89 defined LREQ IDs), `python -m niche_scout.tools.check_import_boundaries`
→ exit 0, and `ruff check`/`ruff format --check` clean on the chunk's four live
files (`sampling.py`, `test_sampling_persistence.py`, and the two test fixtures).
`database.py` carries the same six E501s as HEAD and no formatter-clean
guarantee; see `Documents/runs/chunk-4B.md` "Gate — Chunk 4B".

This file is the **public contract** other chunks build against. It is the frozen
4B plan §5 ("Interface contract this chunk produces") reproduced below. That
section declares "This section becomes `Documents/interfaces/chunk-4B.md`
verbatim once the lead freezes it." Two lead-applied deltas on the §5 body are
annotated in place, both mechanical:

1. §5.3 — the plan's signature block omits the keyword-only
   `discovery_status: str | None = None` parameter that the lead ruling of
   2026-09-20 (plan §12 item 10) requires, that the module's own docstring
   documents, and that `persist_run_sampling` passes. The **code block below
   carries the parameter**; the ruling's text is unchanged.
2. §5.3 — the plan's two docstring lines terminate the inline code span one
   character early (``the `usable_*`_sample_count` columns`` and the
   category-level equivalent), an unbalanced-backtick typo for
   `usable_*_sample_count`; the broken form is kept verbatim inside one code
   span of the same lines here so the type name they document stays readable.

Everything else is verbatim.

**Freeze-order note (plan §15).** This file must exist before Chunk 6B's plan is
written: 6B's gate depends on the pending vocabulary and the
`stratum_statistics_json` schema frozen here (§5.2, Q-4).

Additive only. Nothing in `models.py`, `validation.py`, `config.py`,
`database.py`'s frozen Chunk 0/2 names, or `sampling.py`'s 4A names is redefined
or shadowed. No table, column, index, constraint, enum, `SCHEMA_VERSION`, or
pragma changed anywhere in this chunk; the frozen DDL strings and the Chunk 0/2
public signatures are byte-identical to their pre-4B state.

---

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
    discovery_status: str | None = None,
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

### 5.3a Serializer/parser helpers (database.py, additive; used by the contract above)

The frozen `stratum_statistics_json` schema of §5.2 is produced and read back by
two module-level helpers in `database.py`. They are part of this contract
because Chunk 6B rewrites the same column with the `"usable"`/`"unavailable"`/
`"invalid"` tokens and must produce a byte-compatible payload:

```python
#: The token Chunk 4B writes while enrichment eligibility is unknown.
PENDING_USABLE_STATUS = "pending"

#: The frozen usable-status vocabulary of §5.2, in contract order.
USABLE_STATUS_VOCABULARY = ("pending", "usable", "unavailable", "invalid")

#: The frozen ten-key stratum object key set of §5.2. Serialization uses
#: ``json.dumps(value, sort_keys=True, separators=(",", ":"))``, so this is a
#: key *set*; the serialized key order is ``sort_keys``-determined.
STRATUM_STATISTICS_KEYS: tuple[str, ...] = (
    "N_h",
    "eligibility_rule",
    "n_h",
    "stratum_end_ordinal",
    "stratum_index",
    "stratum_start_ordinal",
    "u_demand_h",
    "u_quality_h",
    "u_recent_h",
    "usable_status",
)

def serialize_stratum_statistics(category: CategorySamplingResult) -> str:
    """Serialize one category's strata into the frozen JSON summary (plan §5.2).

    One object per stratum, sorted by ascending ``stratum_index``, with exactly
    the ten keys of :data:`STRATUM_STATISTICS_KEYS`. ``N_h`` is
    ``stratum.population_count``; ``n_h`` is ``stratum.selected_count`` persisted
    as-is, never recalculated here; ``u_demand_h``/``u_recent_h``/``u_quality_h``
    and ``eligibility_rule`` are JSON ``null`` while pending; ``usable_status`` is
    ``"pending"``. An empty population serializes to ``"[]"``. Deterministic:
    ``json.dumps(value, sort_keys=True, separators=(",", ":"))``.
    """

def parse_stratum_statistics(payload: str) -> tuple[dict[str, object], ...]:
    """Parse a ``stratum_statistics_json`` value into its per-stratum objects.

    Raises :class:`DatabaseError` when the stored text is not a JSON array of
    objects, when an object does not carry exactly the frozen ten-key schema, or
    when a ``usable_status`` token is outside the frozen vocabulary.
    """
```

## 4B-1. Divergence from the plan text recorded at verification (not a contract change)

Two implementation facts the frozen plan text does not itself state, both
verified against the live module and the committed tests
(`Documents/runs/chunk-4B.md`): the create path of `upsert_sampling_summary`
raises `InvalidRecordValueError` for a missing row with no `discovery_status`
even though the plan's §5.3 signature block omitted the parameter (the ruling's
own text carries it, and the code block above includes it); and overlap is
computed once per persist/verify call and reused for both the member rows and
the category summary, so a single mismatch cannot arise from two different
overlap computations.

`sampling.py` remains pure: the 4B block imports only names already present in
the module (`Mapping`, `dataclass`, `RunSamplingResult`) and performs no I/O, no
clock read, and no RNG. `database.py` remains the only I/O home for this chunk.
