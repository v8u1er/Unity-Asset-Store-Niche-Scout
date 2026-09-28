# Chunk 24 — Systematic (interleaved) strata sampling-rule revision

Status: DRAFT (planning; freeze blocked on the open questions in §10)
Chunk id: `chunk-24` (remediation chunk; no §3/§4 dependency-map row — chunk-14/23 precedent).
Run log: `Documents/runs/chunk-24.md`. Operator authorization: run log §"Operator
authorization" (2026-09-28) and §"Design decision" D1/D3; answers A1–A3 at run log
lines 115–126.

This plan supersedes the four-contiguous-strata geometry of `LREQ-SMP-050` with a
deterministic **systematic (interleaved) partition** and changes the persisted stratum
geometry from an ordinal interval to `(offset, stride)`. It is **D1 + D3 only** per
operator answer A1.

---

## 1. Scope and out of scope

### 1.1 In scope

- The systematic/interleaved partition rule over the stable discovery ordinal
  (`LREQ-SMP-020` order), replacing the contiguous-ordinal rule of `LREQ-SMP-050`
  (SRS-lean.md:452–459).
- The deterministic per-category `offset` derivation (A3) and its pure function.
- The `(offset, stride)` representation replacing the ordinal interval in
  `SamplingStratum`, `SampledMember`, `sample_members` DDL, `SampleMemberRecord`,
  `stratum_statistics_json`, `StratumReportRow`, and report rendering (A2).
- `SAMPLING_RULE_VERSION` bump (`models.py:27`) and `SCHEMA_VERSION` bump
  `1.1.0 → 1.2.0` (`database.py:54`).
- The enumerated SRS partition edits (§4), applied at implementation under the
  operator authorization recorded in `Documents/runs/chunk-24.md`.

### 1.2 Explicitly NOT in this chunk

- **D2 is out of scope** (operator answer A1): no change to
  `MIN_USABLE_SAMPLES_PER_STRATUM` (stays `5`, `models.py:46`;
  SRS-lean.md:436,1291; `config/default.toml:22`), and no
  coverage/evidence/rankability re-baseline. `pipeline._component_eligibility_rule`
  keeps emitting `usable:5` (`pipeline.py:1647`). Do not touch
  `metrics.py`, `scoring.py`, the three `*_stratum_eligibility_coverage` formulas,
  or `quality_min_eligible_assets`.
- No change to `LREQ-SMP-040` census behavior, `LREQ-SMP-060` within-stratum
  selection (digest, sort, `sample_rank_within_stratum`), `LREQ-SMP-070`'s
  requirement, `LREQ-SMP-080` field set outside the boundary key rename,
  `LREQ-SMP-090` semantics, `LREQ-SMP-010/030` constants other than the version
  string, overlap (§6.5), preflight, or enrichment.
- No change to `raw_discovery_observations.stratum_index` (SRS-lean.md:548,
  `database.py:122`); it is written `None` during discovery
  (`collector_coveo.py:1856`) and is not part of this partition.
- No database migration/ALTER path: the tool is single-run, resume/history is out
  of scope (SRS §15). An existing `1.1.0` database hits the existing
  `create_schema` version-mismatch error (`database.py:949–952`).
- No new config key, no new warning code, no RNG, no clock read in pure code.

### 1.3 Follow-on `chunk-25` boundary (declared, not planned here)

`chunk-25` = **D2**: lower `MIN_USABLE_SAMPLES_PER_STRATUM` 5 → 1 and re-baseline all
coverage/evidence/rankability outputs and their golden vectors. It owns:
`models.MIN_USABLE_SAMPLES_PER_STRATUM` (`models.py:46`), SRS-lean.md:436/1291 and the
§14 table, `config/default.toml:22`, `metrics.py` (`:533, :804`) and `pipeline.py`
(`:1659, :1921, :2120, :2307`) defaults, the `usable:5` → `usable:1` token produced at
`pipeline.py:1647`, and every coverage/grade/rankability vector in `tests/` and
`tests/fixtures/metric_estimator_fixtures.py`. Those files are **not** touched by
chunk-24. `chunk-24` must not be gated on chunk-25 and must not pre-empt it.

---

## 2. Exact stratum-assignment rule

### 2.1 Large category (`population.size > CENSUS_POPULATION_THRESHOLD`, i.e. > 100)

Let `N = population.size`, `S = SAMPLE_STRATA = 4` (models.py:44). Let `offset` be the
per-category constant of §2.2, `0 <= offset < S`. For 1-based population ordinal `i`
(the position in the `LREQ-SMP-020` canonical order, `CanonicalPopulation` docstring
`sampling.py:99–114`):

```text
stratum_index(i) = (i - 1 + offset) mod S
```

- `stratum_stride = S` (`4`) for every large-category stratum.
- Stratum `h`'s member ordinals are the ascending `i` in `1..N` with
  `(i - 1 + offset) mod S == h`.
- Every `i` maps to exactly one `h`; the partition is a disjoint cover of `1..N`.
- Size distribution is the quotient/remainder distribution (`floor(N/S)` or
  `ceil(N/S)` per stratum); because `N >= 101`, every stratum has `>= 25` members, so
  `is_reduced` is `False` for **every** large-category stratum. `LREQ-SMP-090`
  reduction is reachable only via the census branch (§2.3) under these constants.
- `LREQ-SMP-070` (early/middle/late coverage) is satisfied structurally: each stratum
  samples across the whole ordinal axis rather than a contiguous band.
- `LREQ-SMP-060` selection is unchanged: candidates are the stratum's member ordinals,
  digested by `selection_digest(version, category, key)`, sorted by
  `(digest, asset_identity_key)`, first `min(target_count, population_count)` selected,
  ranked 1-based.

### 2.2 Offset derivation (A3, frozen)

```text
offset = int.from_bytes(
    hashlib.sha256(utf8(sampling_rule_version + "\x00" + category)).digest()[:8],
    "big",
) mod SAMPLE_STRATA
```

- NUL delimiter is the existing `NUL_DELIMITER = "\x00"` (`sampling.py:60`); the
  payload is **two** values (`version`, `category`), not the three-value selection
  payload of `LREQ-SMP-060`.
- Digest bytes: first 8 bytes of the raw `digest()`, interpreted big-endian, then
  reduced `mod SAMPLE_STRATA`. No hex reduction, no casing step (category bytes are
  used verbatim as UTF-8).
- Deterministic, no RNG, no clock, no platform-dependent hash. Persisted (not
  recomputed by consumers).
- The function takes the same `sampling_rule_version` string that selection and
  persistence use.

### 2.3 Census category (`size <= 100`, `LREQ-SMP-040`) and reduced strata

Census is unchanged in outcome: one stratum, `stratum_index = 0`, all `N` canonical
assets selected, `selected_count = target_count = N`, `sample_is_census = True`,
`sample_fraction = 1.0`. Its geometry is encoded as
`stratum_offset = 0`, `stratum_stride = 1`, so `stratum_member_ordinals` returns
`1..N` (every `i` satisfies `(i-1+0) mod 1 == 0`). `is_reduced = (N < 25)`
(`LREQ-SMP-090`), unchanged. See OQ-1.

---

## 3. Persistence / representation change (D3, A2)

### 3.1 Version values

| Constant | File:line | Current | New |
|---|---|---|---|
| `SAMPLING_RULE_VERSION` | `models.py:27` | `"1.0.0"` | `"2.0.0"` (proposed — OQ-2) |
| `SCHEMA_VERSION` | `database.py:54` | `"1.1.0"` | `"1.2.0"` |

`config.py` reads both from `models` (`config.py:35,93`); no config edit is required.
The new `SAMPLING_RULE_VERSION` string is an **input to the offset** (§2.2), so every
offset golden vector depends on the exact value.

### 3.2 `sample_members` (DDL + typed record)

Replace the two interval columns with two geometry columns (same type, same
`NOT NULL`):

- `database.py:139–140` DDL:
  `stratum_start_ordinal INTEGER NOT NULL` / `stratum_end_ordinal INTEGER NOT NULL`
  → `stratum_offset INTEGER NOT NULL` / `stratum_stride INTEGER NOT NULL`.
  Column position is preserved (they stay between `stratum_index` and
  `sample_rank_within_stratum`); `TABLE_COLUMNS` is DDL-derived so parity with
  `MANDATORY_ROW_FIELDS` holds once `models.SampleMemberRecord` is changed.
- `models.py:407–408` `SampleMemberRecord`:
  `stratum_start_ordinal: int` / `stratum_end_ordinal: int` →
  `stratum_offset: int` / `stratum_stride: int`.
- `MANDATORY_ROW_FIELDS` / `ROW_TYPES` (`models.py:522–535`) update automatically.
- Member discovery ordinal remains recoverable from
  `raw_discovery_observations.discovery_ordinal` (`database.py:115`), as A2 mandates;
  no new column and no back-reference to a member's ordinal is added.

### 3.3 `stratum_statistics_json` frozen key set (10 keys, renamed two)

`STRATUM_STATISTICS_KEYS` (`database.py:2050–2061`) becomes (sort order is
`json.dumps(sort_keys=True)`, so the tuple is a key *set*; the canonical serialized
order is shown):

```text
N_h, eligibility_rule, n_h, stratum_index, stratum_offset, stratum_stride,
u_demand_h, u_quality_h, u_recent_h, usable_status
```

`stratum_offset`/`stratum_stride` replace `stratum_start_ordinal`/`stratum_end_ordinal`.
`serialize_stratum_statistics` (`database.py:2077–2105`) emits the stratum's
`stratum_offset` and `stratum_stride`; `parse_stratum_statistics`
(`database.py:2108+`) validates against the updated key set (it uses
`_STRATUM_STATISTICS_KEY_SET`, `database.py:2074`). `N_h`/`n_h` semantics are unchanged
(`population_count`/`selected_count`). Empty population still serializes to `"[]"`.

### 3.4 Other I/O touch points

- `persist_run_sampling` member construction: `database.py:2205–2206` binds the two new
  fields from `SampledMember`.
- `verify_persisted_sampling` field comparisons: `database.py:2306–2313` compares
  `stratum_offset`/`stratum_stride` and names those columns in mismatch strings.
- `get_sample_members` / `_project_row` (`database.py:1663–1673`) and
  `upsert_sample_members` (`database.py:1454+`) are column-driven and need no logic
  change beyond the DDL/record rename.
- `report.py`: `StratumReportRow` fields `report.py:221–222`; parse `report.py:599–601`;
  HTML headers/cells `report.py:855–875`; text line `report.py:978–979` (renders
  `ordinals A-B` → `offset O stride S`).
- `pipeline.py`: `_ordered_members` sort key and docstring `pipeline.py:277–303`
  (`member.stratum_start_ordinal` → `member.stratum_offset`, adding
  `member.stratum_stride` for shape); docstrings at `pipeline.py:281,320`. The
  metric-input projection (`pipeline.py:1691–1699, 2202–2211`) uses only
  `stratum_index`/`population_count`/`selected_count` and is unchanged.

---

## 4. Enumerated `Documents/SRS-lean.md` edits

The planner does not edit the SRS. Apply these at implementation, under the operator
authorization recorded in `Documents/runs/chunk-24.md` lines 18–31/115–126. Line refs
are the **current** pre-edit lines (read this session).

| # | Section / LREQ | Current lines | Edit |
|---|---|---|---|
| S1 | §1.4 Definitions — `Stratum` | 113 | Replace "One ordinal segment"; state a stratum is a systematic (interleaved) set of canonical ordinals at a fixed stride with a per-category offset. |
| S2 | §5.1 — `LREQ-SMP-030` versioning note | 445–447 | Add the partition rule to the list of changes that require a new sampling-rule version. |
| S3 | §5.1 — `LREQ-SMP-050` | 452–459 | Replace "four contiguous ordinal strata" and the `floor(h*N/S)+1 .. floor((h+1)*N/S)` interval with the systematic rule `(i-1+offset) mod S`; add the §2.2 offset derivation and keep "select 25 from each stratum". Keep the census sentence `1..N` (encoded `offset=0, stride=1`). |
| S4 | §5.1 — `LREQ-SMP-070` | 468–470 | Add one clause that a systematic/interleaved partition satisfies early/middle/late coverage; do not weaken the prohibition. |
| S5 | §5.1 — `LREQ-SMP-080` | 473 | "stratum boundaries" → "stratum geometry (offset and stride)". |
| S6 | §6.3 `sample_members` field list | 561–562 | Replace `stratum_start_ordinal, stratum_end_ordinal` with `stratum_offset, stratum_stride`. |
| S7 | §14 Configuration reference — `SAMPLE_STRATA` row | 1289 | Purpose "Ordinal strata count." → note it is the systematic stride. Do **not** edit line 1291 (`MIN_USABLE… = 5`) — that is chunk-25/D2. |

Not edited: §5.1 line 436 (`MIN_USABLE_SAMPLES_PER_STRATUM = 5`) and §14 line 1291
(chunk-25). §6.5 line 602 (`stratum_statistics_json`) needs no SRS text change: the
key set is an interface artifact (§5).

---

## 5. Interface-file deltas

| Interface | Delta needed |
|---|---|
| `Documents/interfaces/chunk-4A.md` | §5.1 add `category_stratum_offset`/`stratum_member_ordinals`; §5.3 `SamplingStratum` (`start_ordinal`/`end_ordinal` → `stratum_offset`/`stratum_stride`) and `SampledMember` (same rename); §5.4 `build_strata` gains `sampling_rule_version` kw and rewritten docstring. Also `sampling.py` header docstring lines 1–17. |
| `Documents/interfaces/chunk-4B.md` | §5.2 ten-key JSON schema and byte-exact example (`stratum_start_ordinal`/`stratum_end_ordinal` → `stratum_offset`/`stratum_stride`); §5.3a `STRATUM_STATISTICS_KEYS` block; `serialize_stratum_statistics`/`parse_stratum_statistics` docstrings. |
| `Documents/interfaces/chunk-7B.md` | No functional delta: `StratumMetricInput` carries `stratum_index`/`N_h`/`n_h`/observations only. Record a note that stratum membership changes under the new rule and its golden vectors are re-baselined; coverage formulas and `min_usable…` are untouched. |
| `Documents/interfaces/chunk-11.md` | §4 `StratumReportRow` fields (lines 44–46) renamed; §5/§6 parsing and rendering text ("start ordinal"/"end ordinal" columns → "offset"/"stride"). |
| `Documents/interfaces/chunk-00.md` | §3 `SAMPLING_RULE_VERSION` (line 116) value; `SAMPLE_STRATA` (line 129) purpose; §? `SCHEMA_VERSION` (line 319) `1.0.0` → the live `1.2.0`. |
| **New** `Documents/interfaces/chunk-24.md` | Required: frozen delta file recording the new pure signatures (§6) and the renamed persistence schema, so chunks that consume 4A/4B/11 read one authoritative delta. |

Frozen interface files are append-only in spirit: each delta above must be a marked
revision note naming `chunk-24`, not a silent rewrite.

---

## 6. Typed pure contract (`src/niche_scout/sampling.py`)

All names pure: no I/O, no clock, no RNG, no new imports beyond the existing
`hashlib`/`collections.abc`/`dataclasses` (`sampling.py:21–23`).

```python
def category_stratum_offset(
    category: str,
    *,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> int:
    """Deterministic per-category systematic-partition offset (A3; LREQ-SMP-050).

    payload = (sampling_rule_version + NUL + category).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % SAMPLE_STRATA

    Range 0..SAMPLE_STRATA-1. Raises ValueError for a non-str or
    empty/whitespace-only category (reuses _require_nonempty_category); an empty
    category is never a shared offset bucket. sampling_rule_version is used
    verbatim (no validation). Pure.
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

    # Invariant: population_count == len(stratum_member_ordinals(self, N))
```

`SamplingStratum.start_ordinal`/`end_ordinal` are removed (A2).

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
    population_size must equal the category's canonical population size so the
    large-category stratum covers exactly its share; a population_size smaller
    than the stratum's own population_count is caller error and is not silently
    truncated (returns the intersection it can justify).
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

    Empty population -> (). Census (size <= census_threshold): one stratum,
    stratum_index=0, stratum_offset=0, stratum_stride=1, population_count=size,
    selected_count=target_count=size, is_reduced=(size < per_stratum_target).
    Large: S = sample_strata; offset = category_stratum_offset(population.category,
    sampling_rule_version=sampling_rule_version) (always mod SAMPLE_STRATA);
    for h in 0..S-1 a stratum with stratum_offset=offset, stratum_stride=S, and
    population_count = count of i in 1..size with (i-1+offset) mod S == h.
    Raises ValueError when sample_strata < 1 or per_stratum_target < 1.
    Production callers use the frozen defaults and pass no overrides except the
    version (LREQ-SMP-030). Note: when sample_strata != SAMPLE_STRATA the stride
    differs but the offset is still reduced mod SAMPLE_STRATA (A3) — test-only
    override, see OQ-3.
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

`SampledMember.stratum_start_ordinal`/`stratum_end_ordinal` are removed (A2).

```python
def select_stratum_members(
    population: CanonicalPopulation,
    stratum: SamplingStratum,
    *,
    sample_is_census: bool,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> tuple[SampledMember, ...]:
    """Select up to ``stratum.target_count`` members from ``stratum``.

    Candidates are population.identity_keys at the 1-based ordinals returned by
    stratum_member_ordinals(stratum, population.size). Each is digested by
    selection_digest; sorted by (digest, asset_identity_key); the first
    min(target_count, population_count) are selected, ranked 1-based. Members
    carry stratum.stratum_offset / stratum.stratum_stride unchanged. Empty
    stratum -> (). Deterministic; no RNG; no clock. Unchanged from Chunk 4A apart
    from candidate enumeration and the renamed member fields (LREQ-SMP-060/090).
    """
```

`select_category_sample` calls
`build_strata(population, sampling_rule_version=sampling_rule_version)` and is
otherwise unchanged (census/fraction/basis semantics `sampling.py:481–542`).
`select_run_sample`, `selection_digest`, `build_canonical_population`,
`compute_overlap`, `CanonicalPopulation`, `CategorySamplingResult`,
`RunSamplingResult` are unchanged.

---

## 7. Affected pytest node IDs, `tests/traceability.json`, and counting method

### 7.1 Matrix key format (read, not verified against the validator)

`tests/traceability.json` is keyed by **pytest node ID**, value = list of LREQ IDs
(read at `tests/traceability.json:372–380`, e.g.
`"tests/test_contracts.py::test_census_model_contract": ["LREQ-SMP-040"]`). This
**contradicts** `tests/AGENTS.md`, which says the file is keyed by LREQ ID with an
array of node IDs. The top-level `AGENTS.md` "key = test node ID" matches the file.
Flagged OQ-4; the implementer must follow whatever
`python -m niche_scout.tools.validate_traceability` accepts.

### 7.2 Node-ID that must be renamed (read)

`tests/traceability.json:381`:
`"tests/test_contracts.py::test_category_scores_column_set_includes_failure_cause_and_version_is_1_1_0"`.
Under `SCHEMA_VERSION = "1.2.0"` this Chunk-23 assertion and its node ID (which embeds
`1_1_0`) must change to `..._version_is_1_2_0`; the traceability key moves with it in
the same change (no duplicate/renamed node ID survives — rule "a moved node keeps its
ID" applies to splits, not to a version-literal node name that the requirement text
itself invalidates; still, rename + key update must be one atomic edit).

### 7.3 Counting method and counts (label: **counted**, not verified as node IDs)

Queries run this session with the grep tool:

- A: pattern `LREQ-SMP-0\d+`, path `tests/traceability.json` → **91 matching lines**
  (occurrences of SMP IDs inside value arrays; not distinct keys, not node IDs).
- B: pattern `@pytest\.mark\.lreq\("LREQ-SMP-0`, path `tests` → **90 matching lines**,
  of which one is a docstring, not a decoration:
  `tests/test_sampling_persistence.py:7` (inside a `"""..."""` block). Therefore **89
  marker decorations** at read time. This counts decorations, not distinct node IDs
  (parameterized tests expand to many node IDs).
- C: the run log (`Documents/runs/chunk-24.md:65–68`) states **72 distinct node IDs
  across the 8 affected LREQ keys**, `LREQ-SMP-080` alone = **45 distinct nodes**.
  Label: **read-derived from the run log, unverified** — I did not run
  `pytest --collect-only`.

Final node-ID enumeration is an implementation-stage obligation: run
`python -m pytest --collect-only -q`, filter the SMP-Labelled nodes, and reconcile
`tests/traceability.json` in both directions with
`python -m niche_scout.tools.validate_traceability` (exit 0). Do not write a node
count into a frozen artifact without the anchored enumeration.

### 7.4 Affected LREQ keys and test modules (read)

- Keys: `LREQ-SMP-030, -040, -050, -060, -070, -080, -090`; plus `LREQ-ARCH-010/020`
  (purity of the new pure function/membership helper) and `LREQ-NFR-040` (docstrings).
  `LREQ-SMP-010/020` tests build populations and are mostly unaffected except where
  they assert interval fields.
- `tests/test_sampling.py` — markers at `:126,155,205,230,270,297,313,330,347,390,423,
  446,465,495,518,544,567,630,655,680,702,764,805,828,851,886,941,973`; field-list
  assertion `:923–933` (rename `stratum_start_ordinal`/`end_ordinal` →
  `stratum_offset`/`stratum_stride`); contiguous-stratum vectors `:347–463` recomputed
  for interleaving.
- `tests/test_sampling_persistence.py` — many `LREQ-SMP-080` nodes; interval
  comparisons `:275–276`, `:501–502`, `:531–532`.
- `tests/test_database.py` — `LREQ-SMP-080` nodes `:597,993,1034,2037,2091`; fixtures
  `:251–252, 1055–1056, 1618–1619`.
- `tests/test_contracts.py` — required-fields list `:140–141`; member constructions
  `:617–618, 1056–1057`; version node `:381–383` (rename per §7.2).
- `tests/test_enrichment.py` — `LREQ-SMP-080` nodes `:535…1083` (persisted-member
  round trips).
- `tests/test_end_to_end.py` — `:248,295` (`LREQ-SMP-050`), `:467` (`LREQ-SMP-080`).
- `tests/test_identity.py:878` (`LREQ-SMP-010`) — likely unaffected; confirm.
- Fixtures: `tests/fixtures/sampling_persistence_fixtures.py`,
  `tests/fixtures/report_fixtures.py`, `tests/fixtures/enrichment_fixtures.py`
  (see §8).

---

## 8. Golden vectors / fixtures re-baseline list

1. `tests/fixtures/sampling_persistence_fixtures.py` — the byte-exact O9 census
   literal `:342–347` and key tuple `O9_STRATUM_KEYS :350–361`, plus the fixture table
   around `:330`. Hand-computed new O9 literal for census size 1 (keys in
   `json.dumps(sort_keys=True, separators=(",",":"))` order):
   ```text
   [{"N_h":1,"eligibility_rule":null,"n_h":1,"stratum_index":0,"stratum_offset":0,
   "stratum_stride":1,"u_demand_h":null,"u_quality_h":null,"u_recent_h":null,
   "usable_status":"pending"}]
   ```
   (single concatenated line, no newlines/indent).
2. `tests/test_sampling.py` — add/replace systematic-partition membership vectors.
   Hand-computed fixture: `N = 101`, `offset = 0`, `S = 4` → ordinals per stratum
   `h=0: {1,5,…,101}` (26), `h=1: {2,6,…,98}` (25), `h=2: {3,7,…,99}` (25),
   `h=3: {4,8,…,100}` (25); every `is_reduced == False`. Second: `N=104, offset=0` →
   26 each. Intentionally a boundary vector at `N = 101` (just above census).
   `offset` golden vector: a fixture must record the concrete
   `category_stratum_offset` for a fixed `(sampling_rule_version, category)` pair,
   produced by an **independent** one-liner (`python -c "import hashlib; …"`), not by
   the module under test; the test asserts the recorded value, range `0..3`, and that
   two different categories can differ. The concrete value cannot be hand-computed and
   must be captured at implementation (record the command used).
3. `tests/fixtures/report_fixtures.py:70–80` — stratum JSON helper keys/values.
4. `tests/fixtures/enrichment_fixtures.py:183–184, 378–379` — `SampledMember`
   constructions.
5. `tests/test_database.py:251–252, 1055–1056, 1618–1619` and
   `tests/test_contracts.py:140–141, 617–618, 1056–1057` — member field lists and
   constructions.
6. `tests/fixtures/metric_estimator_fixtures.py` — **verify only**: these build
   `StratumMetricInput` directly (`chunk-7B.md` §3) and carry no interval fields, so
   they are unaffected unless they route through `sampling.select_category_sample`.
   `chunk-24` must not change metric expected values; if an end-to-end vector changes
   only because interleaving moved observations between strata, re-baseline the
   stratum membership, not the formula outputs.
7. `tests/test_end_to_end.py:248,295,467` — end-to-end run vectors recomputed from the
   new pure result.

`SCHEMA_VERSION` / version-string assertions elsewhere (grep `1.1.0`, `1.0.0` in
`tests/`) are re-baselined to `1.2.0` / the value chosen in OQ-2.

---

## 9. Definition of Done / gate

Gate checklist derived from dependency-map §Chunk 4A "Gate" (`requirements-dependency-map.md:594–601`),
§Chunk 4B "Gate" `:628–635`, and the global chunk-0 checklist `:432–441`, applied to a
remediation chunk:

- [ ] Systematic partition: for `N > 100`, `stratum_index(i) = (i-1+offset) mod S`; the
      four strata are a disjoint cover of `1..N`; `offset` is the exact A3 digest with
      range `0..SAMPLE_STRATA-1` and is persisted.
- [ ] Census (`N <= 100`) selects every asset, one stratum, `offset=0`, `stride=1`,
      `sample_fraction = 1.0`, `sample_is_census = True`; zero population still yields
      `sample_fraction is None` (never `0.0`).
- [ ] Repeated selection is identical; changing `SAMPLING_RULE_VERSION` changes both
      the offset and the digest/selection; no RNG, no clock.
- [ ] Early/middle/late discovery positions are represented by every stratum
      (`LREQ-SMP-070`).
- [ ] `sample_fraction` remains distinct from stratum eligibility coverage.
- [ ] Every selected sample has a persisted membership with a reproducible digest; the
      `(offset, stride)` geometry survives a SQLite round trip; `stratum_statistics_json`
      carries exactly the renamed ten-key set.
- [ ] `verify_persisted_sampling` compares `stratum_offset`/`stratum_stride` and still
      returns `mismatches == ()` for a re-materialized run.
- [ ] `SCHEMA_VERSION == "1.2.0"`; `SAMPLING_RULE_VERSION` is the OQ-2 value; a stale
      `1.1.0` database is rejected by the existing create-schema guard.
- [ ] `sampling.py` and `metrics.py`/`scoring.py` remain pure:
      `python -m niche_scout.tools.check_import_boundaries` → exit 0.
- [ ] Every analytical test has a `@pytest.mark.lreq("LREQ-...")` marker and a matching
      `tests/traceability.json` entry (rename §7.2 applied);
      `python -m niche_scout.tools.validate_traceability` → exit 0 in both directions.
- [ ] `python -m pytest -q` passes; `ruff format --check` / `ruff check` clean on the
      touched files (per `pyproject.toml`).
- [ ] No file outside §"Files touched" below changed; no `MIN_USABLE`/coverage/evidence
      value touched (chunk-25 boundary held); no out-of-scope feature added.
- [ ] SRS edits S1–S7 applied textually and the interface deltas of §5 recorded, each
      naming `chunk-24`.

Gate end state: `Documents/runs/chunk-24.md` records `GATE: PASSED` with real command
outputs; the lead is the only committer.

---

## 10. Files touched

| Path | Change |
|---|---|
| `src/niche_scout/models.py` | `SAMPLING_RULE_VERSION`; `SampleMemberRecord` fields |
| `src/niche_scout/sampling.py` | `category_stratum_offset`, `stratum_member_ordinals`, `SamplingStratum`, `SampledMember`, `build_strata`, `select_stratum_members`, header docstring |
| `src/niche_scout/database.py` | `SCHEMA_VERSION`, `CREATE_TABLE_SAMPLE_MEMBERS`, `STRATUM_STATISTICS_KEYS`, `serialize/parse_stratum_statistics`, `persist_run_sampling`, `verify_persisted_sampling` |
| `src/niche_scout/report.py` | `StratumReportRow`, `_strata_from_json`, HTML/text renderers |
| `src/niche_scout/pipeline.py` | `_ordered_members` sort key + docstrings (`:277–303, :281, :320`) |
| `Documents/plans/chunk-24-systematic-strata.md` | this plan |
| `Documents/runs/chunk-24.md` | stage/gate log (lead-owned) |
| `Documents/interfaces/chunk-04A.md` | marked delta (§5) |
| `Documents/interfaces/chunk-4B.md` | marked delta (§5) |
| `Documents/interfaces/chunk-11.md` | marked delta (§5) |
| `Documents/interfaces/chunk-00.md` | marked delta (§5) |
| `Documents/interfaces/chunk-24.md` | new frozen delta file |
| `Documents/SRS-lean.md` | edits S1–S7 (§4), under operator authorization |
| `tests/test_sampling.py`, `test_sampling_persistence.py`, `test_database.py`, `test_contracts.py`, `test_enrichment.py`, `test_end_to_end.py` | re-baseline + rename nodes (§7) |
| `tests/fixtures/sampling_persistence_fixtures.py`, `report_fixtures.py`, `enrichment_fixtures.py`, `metric_estimator_fixtures.py` | re-baseline / verify (§8) |
| `tests/traceability.json` | key move + new vectors (§7) |

Not touched: `config.py`, `config/default.toml`, `metrics.py`, `scoring.py`,
`collector*.py`, `cli.py`.

---

## 11. Open questions

Resolve none of these here; the plan stays DRAFT until the operator/lead answers.

1. **OQ-1 — census stratum `(offset, stride)` encoding.** The SRS (SRS-lean.md:459,
   507–508) says census is "one stratum containing ordinals `1..N`" and is silent on
   encoding it as `(offset, stride)`. A2 requires the two keys in
   `stratum_statistics_json` and in `sample_members`. Proposed: census
   `stratum_offset = 0`, `stratum_stride = 1` (the only stride under
   `(i-1+offset) mod stride == 0` that reproduces all ordinals). Options: (a) proposed
   0/1; (b) persist `stratum_stride = SAMPLE_STRATA` with census membership defined
   only by `sample_is_census`; (c) NULL for census (requires relaxing `NOT NULL`). The
   test vectors in §8.1 depend on the choice.
2. **OQ-2 — exact `SAMPLING_RULE_VERSION` value.** The decisions say "bump" but do not
   fix the string, and §2.2 makes the string an input to every offset, so every offset
   and selection golden vector depends on it. Proposed `"2.0.0"` (behaviour-breaking
   partition change). Confirm or supply the value before test-author writes vectors.
   The same string must be used in `models.py`, the SRS edit S2/S3, and every fixture.
3. **OQ-3 — `build_strata(sample_strata=…)` override interaction.** `LREQ-SMP-030`
   makes `SAMPLE_STRATA` non-configurable in production; the existing parameter exists
   only for tests (`sampling.py:361,379–380`). A3 fixes the offset modulus to
   `SAMPLE_STRATA`. Confirm the offset stays `mod SAMPLE_STRATA` even when a test passes
   a different `sample_strata` (proposed), or state that non-default `sample_strata`
   must also change the offset modulus.
4. **OQ-4 — traceability key direction.** `tests/AGENTS.md` and top-level `AGENTS.md`
   disagree on whether `tests/traceability.json` is keyed by node ID or by LREQ ID; the
   file is keyed by node ID (read, `tests/traceability.json:372–380`). Which document
   is authoritative for the chunk-24 edits?
5. **OQ-5 — SRS revision-history entry.** SRS-lean.md:14–20 is a revision table
   (latest "Lean 1.0.1"). Confirm whether S2–S7 require a new revision-history row and
   a version label, or whether the §5.1 sampling-rule-version bump alone is sufficient.
6. **OQ-6 — `LREQ-SMP-070` wording.** Confirm the added "systematic partition satisfies
   early/middle/late" clause (S4) does not need a quantitative test (e.g. each stratum's
   min/max ordinal span) beyond the existing `LREQ-SMP-070` assertions; the plan
   proposes a structural membership assertion only.