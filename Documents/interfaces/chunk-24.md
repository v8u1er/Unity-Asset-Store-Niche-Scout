# Chunk 24 — Systematic strata (interface delta)

Status: FROZEN (operator-authorized 2026-09-28; chunk-24 remediation).
Supersedes the four-contiguous-strata geometry of `LREQ-SMP-050` and the
`stratum_start_ordinal`/`stratum_end_ordinal` persistence representation
previously frozen by `Documents/interfaces/chunk-04A.md` and `chunk-4B.md`.

## 14.1 Pure sampling contract (`src/niche_scout/sampling.py`)

```python
def category_stratum_offset(
    category: str,
    *,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> int:
    """Deterministic per-category systematic-partition offset (LREQ-SMP-050).

    payload = (sampling_rule_version + NUL + category).encode("utf-8")
    offset = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % SAMPLE_STRATA

    Range 0..SAMPLE_STRATA-1. Raises ValueError for a non-str or
    empty/whitespace-only category. sampling_rule_version is used verbatim.
    Pure: no I/O, no clock, no RNG, no platform-dependent hash.
    """
```

```python
@dataclass(frozen=True, slots=True)
class SamplingStratum:
    stratum_index: int          # 0-based
    stratum_offset: int         # category offset; 0 for census
    stratum_stride: int         # SAMPLE_STRATA for large; 1 for census
    population_count: int       # N_h
    selected_count: int         # n_h
    target_count: int           # SAMPLE_PER_STRATUM, or the reduced target
    is_reduced: bool            # population_count < SAMPLE_PER_STRATUM
```

`stratum_start_ordinal`/`stratum_end_ordinal` are removed.

```python
def stratum_member_ordinals(
    stratum: SamplingStratum, population_size: int
) -> tuple[int, ...]:
    """Ascending 1-based population ordinals belonging to ``stratum``.

    stride == 1  -> every ordinal in 1..population_size (census).
    stride >= 1  -> ordinals i in 1..population_size with
                    (i - 1 + stratum.stratum_offset) % stratum.stratum_stride
                    == stratum.stratum_index.
    population_size == 0 -> (). population_size < 0 -> ValueError.
    Pure; deterministic; no RNG.
    """
```

```python
def build_strata(
    population: CanonicalPopulation,
    *,
    sample_strata: int = SAMPLE_STRATA,
    per_stratum_target: int = SAMPLE_PER_STRATUM,
    census_threshold: int = CENSUS_POPULATION_THRESHOLD,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> tuple[SamplingStratum, ...]:
    """Systematic strata for a population (LREQ-SMP-040/050/090).

    Census (size <= census_threshold): one stratum, stratum_index=0,
    stratum_offset=0, stratum_stride=1, population_count=size,
    selected_count=target_count=size, is_reduced=(size < per_stratum_target).
    Large: S = sample_strata; offset = category_stratum_offset(...) (always mod
    SAMPLE_STRATA); for h in 0..S-1 a stratum with stratum_offset=offset,
    stratum_stride=S, and population_count = count of i in 1..size with
    (i-1+offset) mod S == h. Raises ValueError when sample_strata < 1 or
    per_stratum_target < 1.
    """
```

```python
@dataclass(frozen=True, slots=True)
class SampledMember:
    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_offset: int
    stratum_stride: int
    sample_rank_within_stratum: int
    sample_is_census: bool
    selection_digest: str
```

`SampledMember.stratum_start_ordinal`/`stratum_end_ordinal` are removed.
`select_stratum_members` enumerates candidates via `stratum_member_ordinals`;
selection by `(selection_digest, asset_identity_key)` is unchanged
(`LREQ-SMP-060`). `select_category_sample`, `select_run_sample`, digest,
overlap, and canonical-population behavior are unchanged.

## 14.2 Persistence contract

- `SCHEMA_VERSION = "1.2.0"`.
- `sample_members` columns `stratum_start_ordinal`/`stratum_end_ordinal`
  are replaced by `stratum_offset`/`stratum_stride` (same `INTEGER NOT NULL`,
  same position between `stratum_index` and `sample_rank_within_stratum`).
- `stratum_statistics_json` frozen ten-key set becomes:
  `N_h, eligibility_rule, n_h, stratum_index, stratum_offset, stratum_stride,
  u_demand_h, u_quality_h, u_recent_h, usable_status`.
- A member's discovery ordinal remains recoverable from
  `raw_discovery_observations.discovery_ordinal`; no new column is added.

## 14.3 Versions

| Constant | Before | After |
|---|---|---|
| `SAMPLING_RULE_VERSION` | `1.0.0` | `2.0.0` |
| `SCHEMA_VERSION` | `1.1.0` | `1.2.0` |

## 14.4 Out of scope

`MIN_USABLE_SAMPLES_PER_STRATUM`, the coverage formulas, and the
evidence/rankability re-baseline are **not** changed here; they are the
declared follow-on `chunk-25` (plan §1.3).