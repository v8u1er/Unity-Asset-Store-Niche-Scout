# Chunk 28 — Page-view semantics remediation (D1)

Status: FROZEN

Chunk 28 is a remediation / follow-on chunk with **no dependency-map §3/§4 row**
(ownership matrix names Chunks 0–13 only; §3 ends at Chunk 13, §4 lists 0–13;
precedent: chunks 14, 23, 24, 25, 26, 27). Registration is plan + run log +
branch (`chunk-28`). The governing defect analysis is
`Documents/plans/chunk-26-analytical-defect-remediation.md` §13 (D1 semantics,
best-assumption formula, SRS edits D1-S1…D1-S7, versioning) and §14 (operator
ruling 2026-09-29: OQ-9…OQ-14 adopted; §14.6 the SRS-edit checkpoint). This plan
records the operator-fixed scope and the operator-adopted answers; it does not
re-open them.

Source of truth: `Documents/SRS-lean-v2.md` (`LREQ-` IDs + section numbers, Lean
1.0.3), `Documents/requirements-dependency-map.md`,
`Documents/interfaces/chunk-00.md`, `chunk-02.md`, `chunk-7A.md`.

---

## 1. Goal

Make the persisted page-view signal mean what the Unity endpoint actually
returns. The endpoint's page-view field is a **trailing-7-day (weekly) view
count**, stable within a run and refreshed at most daily; today the tool treats
it as a lifetime cumulative numerator and multiplies by `7 / age_days_exact`
(`metrics.py:448` docstring, `:489` code), producing a dimensionally wrong
"rate" that drives Demand (`D`) and Quality (`Q`) and therefore the composite
score, evidence grades, and rankability. This chunk drops the `* 7 / age_days_exact`
normalization (the index becomes the weekly view count itself), records the
validated weekly semantics on the run, and re-baselines every downstream
`D`/`Q`/rankability golden from a captured run. It does not add a runtime
detector, does not use `contradicted`, and does not change the composite weights
or sampling policy.

---

## 2. Scope

### 2.1 In scope

- The page-view index formula and its docstring in `metrics.py` (LREQ-MET-040).
- A new `PageViewSemanticsStatus` member `validated_windowed_weekly`
  (`models.py`) and the run-level seed that records it.
- The pipeline non-clobber guard that must preserve the new token.
- `SCHEMA_VERSION` `1.2.0 → 1.3.0` and the (automatic) `_ENUM_COLUMNS`
  allow-list extension; old-DB open behavior documented and tested.
- `ENDPOINT_CONTRACT_VERSION` `1.0.0 → 1.1.0` and every fixture that pins it.
- The two report caveats (`report.py:55`, `report.py:128`).
- Re-baselining every `D`/`Q`/rankability golden/scenario that consumes the index.

### 2.2 Explicitly out of scope (and who owns it instead)

- **No SRS edit by any agent.** D1-S1…D1-S7 are operator-only (§13); they are
  the gate's human checkpoint, not an implementation task.
- **No runtime semantics detector.** The run-level status is seeded from a
  module constant; nothing probes the endpoint to detect semantics
  (chunk-26 §14.1 OQ-1, adopted).
- **No `contradicted` use.** The new token is `validated_windowed_weekly`; the
  existing `contradicted` behavior (D/Q unavailable run-wide, LREQ-SCR-050) is
  untouched.
- **No symbol rename.** `age_normalized_page_view_index` keeps its name and is
  documented as a historical label (OQ-11, adopted).
- **No `SAMPLING_RULE_VERSION` bump; `SAMPLE_PER_STRATUM` stays 25; no scoring
  weight, discovery, enrichment, or config-default change** (OQ-5…OQ-7,
  adopted; §15 out-of-scope list).
- **No interface-document edit.** `Documents/interfaces/**` is outside the
  allowlist; a downstream contract change is recorded in §12 instead.
- **No `_ENUM_COLUMNS`→DDL conversion, no migration/ALTER script.** The
  allow-list is Python-side; the version bump is metadata-only (§8.2).
- D2 (chunk-27) and D4/D5 (chunk-26) are not touched.

---

## 3. Requirements this chunk must satisfy

Normative text quoted from `Documents/SRS-lean-v2.md` (Lean 1.0.3). Line
numbers are the **pre-edit** locants; D1-S1…D1-S7 (§13) are the operator's
post-edit text.

| LREQ ID | Ownership role here | Normative text (quoted) | SRS section |
|---|---|---|---|
| `LREQ-MET-040` | **Primary.** Formula, docstring, and the usability sentence. | "The page-view index SHALL be: `age_normalized_page_view_index = product_page_views * 7 / age_days_exact`. It is usable only for a finite non-negative page-view value, a valid UTC date no later than cutoff, `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and a matched, published identity. An explicit valid page-view value of zero is usable and yields an index of zero." (`SRS-lean-v2.md:741-750`) | §7.2 |
| §1.4 definition | Primary (same formula; D1-S1). | "Age-normalized page-view index \| `product_page_views * 7 / age_days_exact`, using an undocumented page-view field. It is an unvalidated index, not a validated weekly traffic measurement or weekly traffic rate." (`:133`) | §1.4 |
| §6.3 enumeration | Primary contract for the new token (D1-S3). | "`page_view_semantics_status` SHALL use only `unvalidated`, `validated_cumulative`, or `contradicted`. … When the run-level status is `contradicted`, D and Q are unavailable for all categories, while C and R MAY remain available; no category is final rankable." (`:675-680`) | §6.3 |
| `LREQ-MET-010` | Supporting contract, **unchanged**. | "A product-level value is usable only when its type, range, state, identity, and timestamp conditions for the relevant metric pass. Null, malformed, future, naive, negative, non-finite, or state-excluded values SHALL be unavailable." (`:691-693`) | §7.1 |
| §6.4 `enrichment_observations` | Supporting contract, **unchanged**. | "`product_page_views` SHALL be nullable and SHALL never use zero as an error sentinel." (`:619`) | §6.4 |
| `LREQ-MET-030` / `LREQ-MET-050` / `LREQ-MET-060` / `LREQ-MET-100` | Supporting contract; **no formula change**, but their numeric outputs move because the index input moves. | Demand per asset / weighted median / coverage / quality raw consume `age_normalized_page_view_index` (`:720-727`, `:752-758`, `:765-772`, `:878-897`). | §7.2, §7.5 |
| `LREQ-SCR-050` | Supporting contract; **the new token is not `contradicted`**, so this path is unchanged. | "If `page_view_semantics_status = \"contradicted\"`, `D` and `Q` SHALL be unavailable." (`:985-987`) | §8.2 |
| `LREQ-EVD-020` / `LREQ-EVD-030` / `LREQ-EVD-040` | Supporting contract; rankability policy unchanged, but per-category states move with the re-baselined metrics. | Rankability conditions (`:1016-1046`). | §9.1 |
| `LREQ-RPT-050` | Supporting / integration completion: reword the two report caveats. | "It SHALL distinguish pagination completion from immutable snapshot completeness, **the page-view index from a weekly traffic rate**, …" (`:1163-1170`) | §10 |
| `LREQ-GQL-010` | Supporting contract for the `ENDPOINT_CONTRACT_VERSION` bump (OQ-12). | "Enrichment SHALL use the parent SRS GraphQL batch endpoint and the two required operations: `ProductDetail(id: ID!)` and `ProductPageViews(packageId: String!)`." (`:305-308`) | §4.2 |
| `LREQ-ARCH-030` | Supporting: versioned, deterministic provenance. | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." (`:250-251`) | §3.3 |
| `LREQ-NFR-040` | Supporting: public functions keep type hints and null/edge-case docstrings. | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." (`:1207-1208`) | §11 |
| `LREQ-TST-010` / `LREQ-TST-050` | Test-coverage requirement. | Formula tests cover normal, explicit zero, missing, invalid, ties, minimum boundaries (`:1261-1262`); date/metric tests cover rate-threshold boundaries and zero page views (`:1280-1284`). | §13 |
| `LREQ-SEC-020` | Supporting: no secret in any changed artifact. | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages." (`:367-368`) | §4.3 |
| §16 item 5 | Primary (D1-S5) for the limitations wording; recorded here so the gate can compare. | "the page-view field is an age-normalized index with unvalidated semantics, not a validated weekly traffic measurement" (`:1385`) | §16 |
| Appendix A | Primary (D1-S6) formula block. | "`age_normalized_page_view_index = product_page_views * 7 / age_days_exact`" (`:1442`) | App. A |

---

## 4. Interface contracts consumed (frozen, read from `Documents/interfaces/`)

- `chunk-00.md`: `PageViewSemanticsStatus` (line 65) and
  `ENDPOINT_CONTRACT_VERSION = "1.0.0"` (line 114); the frozen schema fragment
  (line 319); the chunk-24 revision note (lines 510-520). This chunk changes the
  **values** of the enum and the constant; the frozen interface files are **not**
  edited (outside the allowlist) — the change is recorded in §12 as a forward
  note.
- `chunk-7A.md`: `age_normalized_page_view_index` signature (lines 101-106) and
  its documented formula (line 156). Signature and parameter semantics are
  unchanged except for the value produced.
- `chunk-02.md`: `initialize_schema(check_version=...)` / `SchemaVersionError`
  behavior (lines 124, 180-199). This chunk relies on the existing
  `check_version=True` default raising on a version mismatch, and on
  `check_version=False` rewriting only the version row.
- `pipeline.py` internal contract: `run_identity_preflight(...)` non-clobber
  write (`:998-1007`) and the run-seed construction (`:3336-3345`). These are
  in-repo call sites, not frozen interface files; the edits are in §7.

No interface file is a blocking gap: every contract this chunk consumes already
exists.

---

## 5. Interface contract this chunk produces

### 5.1 `models.py`

```python
class PageViewSemanticsStatus(str, Enum):
    UNVALIDATED = "unvalidated"
    VALIDATED_CUMULATIVE = "validated_cumulative"
    CONTRADICTED = "contradicted"
    VALIDATED_WINDOWED_WEEKLY = "validated_windowed_weekly"   # NEW (D1-S3)
```

New module constant, placed with the other policy versions near
`models.py:25-27`:

```python
#: The run-level page-view semantics this build asserts (chunk-26 §14.1 OQ-1).
#: Seeded at run creation; there is no runtime detector.
PAGE_VIEW_SEMANTICS_CONTRACT: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY
)
```

Changed constant:

```python
ENDPOINT_CONTRACT_VERSION: str = "1.1.0"   # was "1.0.0" (OQ-12)
```

`IDENTITY_MAPPING_RULE_VERSION` (`"1.0.1"`) and `SAMPLING_RULE_VERSION`
(`"2.0.0"`) are **unchanged**.

### 5.2 `metrics.py`

Signature unchanged:

```python
def age_normalized_page_view_index(
    product_page_views: object,
    first_published_date_utc: object,
    *,
    scoring_cutoff_utc: datetime,
    state: str | None,
    id_mapping_mismatch: bool,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
) -> MetricValue: ...
```

Return contract (exact; test-author contract):

- Step 13 value: `float(product_page_views)` — the weekly view count as
  `float64` (Hard rule 4). No multiplication, no division, no dependence on
  `age_days_exact`.
- Steps 1–5 (product-level classification), 6–9 (date), 10
  (`age_days_exact < min_age_days_for_rate` → `METRIC_REASON_AGE_BELOW_MINIMUM`),
  11 (identity), 12 (state) are **unchanged** in order and reason codes.
- An explicit `product_page_views == 0` (int or float) stays usable and yields
  `value == 0.0`.
- `min_age_days_for_rate` stays a validated caller/policy parameter
  (`int >= 1`, else `ValueError`) and an eligibility floor. The docstring's
  "so the division can never be by zero" rationale is removed.
- The symbol name `age_normalized_page_view_index` is kept and documented as a
  **historical label** for the weekly page-view count (OQ-11).

### 5.3 `pipeline.py`

- Run seed (`:3339`):
  `page_view_semantics_status=PAGE_VIEW_SEMANTICS_CONTRACT.value`.
- Non-clobber guard (`:1000-1003`): the preserved tuple gains
  `PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY.value`; the `else` branch
  (`:1006`) still writes `UNVALIDATED.value` for anything else.

### 5.4 `database.py`

- `SCHEMA_VERSION = "1.3.0"` (was `"1.2.0"`; OQ-13).
- `_ENUM_COLUMNS[("runs", "page_view_semantics_status")]` is built from
  `PageViewSemanticsStatus` (`:399-401`), so adding the member extends the
  allow-list **automatically**; no hand edit to the dict.
- No DDL change: `_validate_enum` (`:571-579`) is Python-side validation and the
  frozen DDL carries no `CHECK`. The 1.3.0 bump is metadata-only.

### 5.5 `report.py`

- `HEURISTIC_STATEMENT` (`:48-60`) and `_FORMULA_EXPLANATIONS` (`:107-131`) no
  longer call the index "cumulative" nor "not a weekly traffic rate"; they state
  it **is** a trailing-7-day view count, stable within a run, refreshed at most
  daily, and not a lifetime/cumulative or daily-average rate (OQ-14). Exact
  wording must match the operator's applied D1-S4/D1-S5 SRS text (§12 OQ-2).

---

## 6. Files touched

The allowlist for this chunk is **exactly**:

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/models.py` | modified | Add `PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY`; add `PAGE_VIEW_SEMANTICS_CONTRACT`; `ENDPOINT_CONTRACT_VERSION` → `"1.1.0"`. |
| `src/niche_scout/metrics.py` | modified | `age_normalized_page_view_index` value + docstring (§5.2). No other metric formula. |
| `src/niche_scout/pipeline.py` | modified | Seed from `PAGE_VIEW_SEMANTICS_CONTRACT` (`:3339`); extend the non-clobber guard (`:1000-1003`). |
| `src/niche_scout/database.py` | modified | `SCHEMA_VERSION = "1.3.0"`; allow-list extends automatically via the enum. |
| `src/niche_scout/report.py` | modified | The two caveats (`:55`, `:128`) only. |
| `tests/**`, `tests/fixtures/**`, `tests/traceability.json` | modified | Re-baselined goldens, renamed/re-baselined nodes, version pins, new nodes, traceability. |
| `Documents/SRS-lean-v2.md` | **OPERATOR-ONLY** | D1-S1…D1-S7 (§13). No agent may edit this file. |
| `Documents/plans/chunk-28-page-view-semantics-remediation.md` | new | This plan. |
| `Documents/runs/chunk-28.md` | run log | Written by the lead, not by this plan or its implementers. |

**NOT in the allowlist:** `src/niche_scout/scoring.py`, `sampling.py`,
`collector*.py`, `config.py`, `cli.py`, `Documents/interfaces/**`, sampling
constants, scoring weights, discovery/enrichment/config defaults. A needed
change outside this list is a STOP-and-flag, not an edit.

---

## 7. Task breakdown

Ordered; each item tagged with its LREQ(s).

1. [ ] `models.py`: add `VALIDATED_WINDOWED_WEEKLY` (LREQ-MET-040, §6.3);
   add `PAGE_VIEW_SEMANTICS_CONTRACT`; bump `ENDPOINT_CONTRACT_VERSION` to
   `"1.1.0"` (LREQ-GQL-010, LREQ-ARCH-030).
2. [ ] `metrics.py`: change step 13 to `value=float(product_page_views)`; rewrite
   the docstring (remove `* 7.0 / age`, remove the divide-by-zero rationale,
   document the historical symbol name and the unchanged precedence steps)
   (LREQ-MET-040, LREQ-NFR-040).
3. [ ] `pipeline.py`: seed the run row from `PAGE_VIEW_SEMANTICS_CONTRACT.value`
   at `:3339` (LREQ-MET-040); add
   `PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY.value` to the preserved
   tuple at `:1000-1003` (LREQ-MET-040, LREQ-SCR-050).
4. [ ] `database.py`: `SCHEMA_VERSION = "1.3.0"` (LREQ-ARCH-030). Confirm the
   allow-list extension is automatic; do not hand-edit `_ENUM_COLUMNS`.
5. [ ] `report.py`: reword `HEURISTIC_STATEMENT` (`:55`) and
   `_FORMULA_EXPLANATIONS` (`:128`) per §5.5 and the operator's applied SRS text
   (LREQ-RPT-050).
6. [ ] `tests/fixtures/date_eligibility_fixtures.py`: rewrite the
   `INDEX_VECTORS` comment (`:148-158`) and make `expected = float(views)`
   (`:159-165`); add a `SEMANTICS_VALIDATED_WINDOWED_WEEKLY` fixture next to the
   existing `SEMANTICS_*` (`:225-230`) (LREQ-MET-040, LREQ-TST-050).
7. [ ] Re-baseline the version pins: `identity_preflight_vectors.py:324`,
   `report_fixtures.py:295`, `sampling_persistence_fixtures.py:231`,
   `test_collector.py:242`, and the `test_contracts.py` enum set (`:84`,
   `:226`, `:496-500`) (LREQ-GQL-010).
8. [ ] Rename/re-baseline the index nodes whose assertions encode `*7/age`
   (`test_validation.py`; §9.3) and re-baseline
   `test_page_view_index_zero_views_is_usable_zero` to `0.0` (LREQ-MET-040).
9. [ ] Re-baseline `metric_estimator_fixtures.py` DEMAND/QUALITY goldens and the
   `test_metrics.py` D/Q nodes from a **captured run** (chunk-24/25 precedent);
   do not hand-invent numbers (LREQ-MET-030/050/060/100, LREQ-EVD-020/030/040).
10. [ ] Add the new nodes of §9.2 (enum, seed, non-clobber, schema version,
    old-DB, endpoint version, report caveat) (LREQ-MET-040, LREQ-SCR-050,
    LREQ-ARCH-030, LREQ-RPT-050).
11. [ ] Update `tests/traceability.json`: replace the renamed node keys; add the
    new node keys (§9.4). Run `validate_traceability` (LREQ-TST-010).
12. [ ] Run the full gate command set (§10.4) and report real output.

---

## 8. Edge cases and invariants

### 8.1 Formula and value

- `product_page_views` is `None`/bool/str/list → unchanged
  `METRIC_REASON_PAGE_VIEWS_UNAVAILABLE` / `WRONG_TYPE`; never a raise, never
  `0`.
- non-finite float → `NON_FINITE`; negative int/float → `NEGATIVE`.
- `product_page_views == 0` (int `0` or float `0.0`) → usable, `value == 0.0`
  (explicit zero is not missing).
- age `< min_age_days_for_rate` (including `0.0` and `29.95…`) →
  `AGE_BELOW_MINIMUM`; the index is **not** a function of age above the floor:
  two observations with the same views and ages `30` and `300` produce the same
  index.
- `min_age_days_for_rate` is still a caller/policy parameter validated as
  `int >= 1`; a `bool`, non-int, or `< 1` raises `ValueError`.
- identity mismatch → `IDENTITY_MISMATCH`; non-`published` state →
  `STATE_EXCLUDED` / `STATE_UNKNOWN` (via Chunk 1's annotation). Precedence
  order is unchanged (steps 1–13, docstring §5.2).

### 8.2 Run-level token and schema

- **Non-clobber trap (load-bearing).** The guard at `pipeline.py:1000-1003`
  preserves only `VALIDATED_CUMULATIVE`/`CONTRADICTED`; seeding
  `VALIDATED_WINDOWED_WEEKLY` at `:3339` would be clobbered back to
  `UNVALIDATED` at `:1006` unless the new token is added to the preserved tuple.
  Both edits ship together.
- The seeded run row is `validated_windowed_weekly`; `contradicted` is never
  seeded and is never written by this chunk. LREQ-SCR-050 is therefore inert for
  a normal run, and D/Q stay available.
- `_ENUM_COLUMNS` is Python-side, not DDL, so `1.3.0` is metadata-only. **Old-DB
  handling (consistent with the code):** the default
  `SqliteRepository(...)` / `initialize_schema()` raises `SchemaVersionError`
  when the stored `schema_metadata.schema_version` (`"1.2.0"`) differs from
  `SCHEMA_VERSION` (`"1.3.0"`); there is no silent migration/ALTER (chunk-24
  precedent). The operator re-runs into a fresh DB, or explicitly calls
  `initialize_schema(check_version=False)`, which rewrites only the
  `schema_version` row (and re-runs the idempotent, unchanged DDL).
- No new DB column, so `TABLE_COLUMNS == MANDATORY_ROW_FIELDS` parity is
  unaffected.

### 8.3 Purity and determinism

- `metrics.py` stays pure: no new import, no clock read; `scoring_cutoff_utc`
  remains an explicit parameter (LREQ-ARCH-010/020). `scoring.py` is untouched.
- The new value is a pure function of `product_page_views` plus the unchanged
  classification steps; no RNG, no set/dict-order dependence.
- Missing/zero/invalid/unavailable stay four distinct states; no `or 0`,
  `.get(k, 0)`, `fillna(0)`, or default-0 parameter is introduced.

### 8.4 No fabricated re-baseline values

The DEMAND/QUALITY/rankability goldens move, but their new numeric values come
from a **captured run** at implementation time (chunk-24/25 precedent). This plan
names the files and nodes that move; it does **not** state new expected numbers.

---

## 9. Test plan

Evidence labels: **counted/read** = established by the reconnaissance grep
queries quoted in the dispatch and re-confirmed here; **plan-sourced** = the node
ID is named in a prior frozen plan, not yet re-confirmed in the live file, and
must be re-grepped at implementation; **to be discovered** = search required.

### 9.1 Version pins that must be re-baselined (counted/read)

| File:line | Pin | New value |
|---|---|---|
| `tests/fixtures/identity_preflight_vectors.py:324` | `ENDPOINT_CONTRACT_VERSION_FIXTURE` | `"1.1.0"` |
| `tests/fixtures/report_fixtures.py:295` | endpoint version | `"1.1.0"` |
| `tests/fixtures/sampling_persistence_fixtures.py:231` | endpoint version | `"1.1.0"` |
| `tests/test_collector.py:242` | endpoint version | `"1.1.0"` |
| `tests/test_contracts.py:84` | enum set | add `"validated_windowed_weekly"` |
| `tests/test_contracts.py:226`, `:496-500` | contract pins | re-confirm/re-baseline |

### 9.2 Golden/vector fixtures that move (counted/read)

- `tests/fixtures/date_eligibility_fixtures.py:148-165`: comment and
  `INDEX_VECTORS` become `expected = float(views)`:
  `(0, AGE_30D, 0.0)`, `(10, AGE_30D, 10.0)`, `(7, AGE_30D, 7.0)`,
  `(5, AGE_30D, 5.0)`, `(1.0, AGE_30D, 1.0)`.
- `tests/fixtures/date_eligibility_fixtures.py:225-230`: add
  `SEMANTICS_VALIDATED_WINDOWED_WEEKLY`.
- `tests/fixtures/metric_estimator_fixtures.py:50-269` (incl. `make_observation`
  at `:192`): DEMAND/QUALITY goldens re-baselined from a captured run.

### 9.3 Existing nodes that move (file + node; evidence-labelled)

Counted/read (grep-established node IDs):

- `tests/test_metrics.py::test_demand_per_asset_uses_population_weighted_means`
- `tests/test_metrics.py::test_demand_median_uses_stratum_expansion_weights`
- `tests/test_metrics.py::test_compute_raw_metric_bundle_maps_all_six_values`
- `tests/test_metrics.py::test_quality_raw_uses_n_h_over_n_h_weights`
- `tests/test_report.py::test_report_states_heuristic_and_six_distinctions`
  (`:857`) — asserts the phrase `"weekly traffic rate"` (`:874`) and
  `"page-view index"` (`:873`); **forced re-baseline** to the new caveat wording.
- `tests/test_identity_preflight.py` non-clobber nodes at `:1148-1213`.

Plan-sourced (chunk-7A §9 / chunk-7B §9; re-grep at implementation):

- `tests/test_validation.py::test_page_view_index_uses_seven_over_age_days` —
  **name and assertion are now false**; rename (delete old traceability key, add
  new key) or re-baseline, per §9.4.
- `tests/test_validation.py::test_page_view_index_zero_views_is_usable_zero` —
  still `0.0`, available.
- `tests/test_validation.py::test_page_view_index_age_threshold_boundary` —
  age `30.0` usable, `29.9583…`/`0.0` → `AGE_BELOW_MINIMUM` (unchanged).
- `tests/test_validation.py::test_page_view_index_never_divides_by_zero_at_threshold`
  — the "never divides" framing is moot; keep the `min_age_days_for_rate < 1`
  `ValueError` and threshold assertions, rename if the name is now misleading.
- `tests/test_validation.py::test_page_view_index_missing_views_is_unavailable_not_zero`,
  `::test_page_view_index_rejects_bool_negative_and_non_finite`,
  `::test_page_view_index_rejects_non_numeric_views_and_accepts_integral_float`,
  `::test_page_view_index_wrong_type_date_is_unavailable`,
  `::test_page_view_index_rejects_state_excluded_and_unknown`,
  `::test_page_view_index_rejects_identity_mismatch`,
  `::test_quality_eligibility_propagates_page_view_index_reason` — reason
  precedence unchanged; only the "7/30" literal expectations move.
- `tests/test_metrics.py::test_estimators_consume_chunk_7a_index_eligibility`
  (chunk-7B §9).

To be discovered at implementation (grep `INDEX_VECTORS`,
`age_normalized_page_view_index`, `LREQ-MET-040`, `page_view_semantics_status`,
`ENDPOINT_CONTRACT_VERSION` over `tests/`): any further node that asserts a
`views * 7 / age` numeric literal, a `1.0.0` pin, or the three-member enum set.
Run the exact greps and enumerate before editing; this plan's list is the
minimum, not a claim of completeness.

### 9.4 New nodes (marker + traceability entry)

Each carries `@pytest.mark.lreq(...)` and a `tests/traceability.json` entry.

1. `tests/test_validation.py::test_page_view_index_equals_weekly_view_count`
   — `10 → 10.0`, `7 → 7.0`, `5 → 5.0`, `1.0 → 1.0`; `pytest.approx(abs=1e-9)`.
   Marker: `@pytest.mark.lreq("LREQ-MET-040")`. Entry:
   `["LREQ-MET-040", "LREQ-TST-050"]`.
2. `tests/test_validation.py::test_page_view_index_is_independent_of_age_above_threshold`
   — same views, ages `30` and `300`, equal index. Marker:
   `@pytest.mark.lreq("LREQ-MET-040")`. Entry:
   `["LREQ-MET-040", "LREQ-TST-010"]`.
3. `tests/test_models.py` (or the file owning enum contract tests)
   `::test_page_view_semantics_status_includes_validated_windowed_weekly` — the
   enum member and its value. Marker:
   `@pytest.mark.lreq("LREQ-MET-040")`. Entry:
   `["LREQ-MET-040", "LREQ-GQL-010"]`.
4. `tests/test_pipeline.py::test_run_seeds_validated_windowed_weekly_semantics`
   — a new run row's `page_view_semantics_status == "validated_windowed_weekly"`.
   Marker: `@pytest.mark.lreq("LREQ-MET-040")`. Entry:
   `["LREQ-MET-040", "LREQ-ARCH-030"]`.
5. `tests/test_pipeline.py::test_preflight_preserves_validated_windowed_weekly_status`
   — a run seeded with the new token is **not** clobbered back to `unvalidated`
   by `persist_preflight`. Marker:
   `@pytest.mark.lreq("LREQ-MET-040")`. Entry:
   `["LREQ-MET-040", "LREQ-SCR-050"]`.
6. `tests/test_database.py::test_enum_allow_list_accepts_validated_windowed_weekly`
   — `_validate_enum("runs", "page_view_semantics_status", "validated_windowed_weekly")`
   accepts. Marker: `@pytest.mark.lreq("LREQ-ARCH-030")`. Entry:
   `["LREQ-ARCH-030", "LREQ-MET-040"]`.
7. `tests/test_database.py::test_schema_version_is_1_3_0` — `SCHEMA_VERSION ==
   "1.3.0"`. Marker: `@pytest.mark.lreq("LREQ-ARCH-030")`. Entry:
   `["LREQ-ARCH-030"]`.
8. `tests/test_database.py::test_open_older_schema_raises_unless_check_version_false`
   — a DB whose stored version is `"1.2.0"` raises `SchemaVersionError` on the
   default open, and `initialize_schema(check_version=False)` rewrites only the
   version row. Marker: `@pytest.mark.lreq("LREQ-ARCH-030")`. Entry:
   `["LREQ-ARCH-030"]`.
9. `tests/test_models.py::test_endpoint_contract_version_is_1_1_0`. Marker:
   `@pytest.mark.lreq("LREQ-GQL-010")`. Entry:
   `["LREQ-GQL-010", "LREQ-ARCH-030"]`.
10. `tests/test_report.py::test_report_caveats_describe_trailing_seven_day_views`
    — both renderers no longer say "cumulative"/"not a weekly traffic rate" and
    do describe the trailing-7-day count. Marker:
    `@pytest.mark.lreq("LREQ-RPT-050")`. Entry: `["LREQ-RPT-050"]`.

### 9.5 Traceability rule

`tests/traceability.json` is keyed by **pytest node ID → array of LREQ IDs**
(verified: `:1-5`). Existing nodes keep **byte-identical** entries except any
renamed node, whose old key is deleted and new key added in the same change (do
not leave a dangling entry). Add entries **only** for genuinely new node IDs.
After editing, run `python -m niche_scout.tools.validate_traceability`.

---

## 10. Definition of done (gate)

Copied verbatim from the chunk-28 gate:

1. `metrics.age_normalized_page_view_index` returns `product_page_views` (no
   `*7`, no `/age`) for a valid observation; explicit 0 stays a usable 0;
   age/state/identity reasons unchanged.
2. `PageViewSemanticsStatus` has `validated_windowed_weekly`; a new `runs` row
   seeds it; the DB enum allow-list accepts it; `SCHEMA_VERSION == "1.3.0"`;
   old-DB handling documented and tested.
3. `ENDPOINT_CONTRACT_VERSION == "1.1.0"`; every fixture pinning `"1.0.0"`
   re-baselined.
4. report caveats no longer say "cumulative" / "not a weekly traffic rate".
5. All D/Q/rankability goldens re-baselined from a captured run; pytest + four
   validators exit 0; ruff no new lint.
6. SRS D1-S1…D1-S7 applied by the operator, with diff/sha256 evidence in the run
   log — else the gate is FAILED and the chunk BLOCKED.

### 10.4 Verification commands

Run from the repository root (PowerShell; chain with `;`):

```powershell
python -m pytest -q
python -m niche_scout.tools.validate_traceability
python -m niche_scout.tools.check_import_boundaries
python -m niche_scout.tools.check_scope_prohibitions
python -m niche_scout.tools.check_secrets
python -m ruff check src/niche_scout tests
python -m ruff format --check src/niche_scout tests
```

Or the fixed-order workflow: `python -m niche_scout.tools.quality_workflow`.
The four validators are `validate_traceability`, `check_import_boundaries`,
`check_scope_prohibitions`, `check_secrets`. Record the real pre/post
`pytest` counts in `Documents/runs/chunk-28.md`; do not claim a pass without the
output.

---

## 11. Explicit prohibitions

- Must not edit `Documents/SRS-lean-v2.md` (operator-only; §13).
- Must not edit `Documents/interfaces/**`.
- Must not import `sqlite3`/network/filesystem/CLI into `metrics.py` or
  `scoring.py`, and must not read the clock in pure code (LREQ-ARCH-010/020).
- Must not introduce `or 0`, `.get(k, 0)`, `fillna(0)`, or a default-0 metric
  parameter; zero, null, invalid, and unavailable stay distinct.
- Must not add a runtime page-view semantics detector, and must not write
  `contradicted` (no detector; OQ-1).
- Must not bump `SAMPLING_RULE_VERSION`, change `SAMPLE_PER_STRATUM`, or touch
  scoring weights, discovery, enrichment, or config defaults.
- Must not add a DB column, a migration/ALTER script, or a DDL `CHECK`.
- Must not change any `metrics.py` formula other than step 13 of
  `age_normalized_page_view_index`.
- Must not fabricate re-baselined golden numbers; they come from a captured run.
- Must not rename a pytest node ID without replacing its `tests/traceability.json`
  key in the same change.
- Must not write secrets, raw response bodies, or credentials into any changed
  artifact (LREQ-SEC-020).

---

## 12. Open questions / assumptions

Recorded, **not resolved** by this plan. The plan is freezeable because §13 and
the operator-adopted §14 fix the substance; neither question changes an
implementation file's contract.

1. **LREQ owner of `ENDPOINT_CONTRACT_VERSION` / `SCHEMA_VERSION`.** chunk-26
   §13.5 OQ-12 flagged that the dependency map does not state the trigger for
   `ENDPOINT_CONTRACT_VERSION`. Options: (a) assign it as a supporting contract
   of `LREQ-GQL-010` (the enrichment endpoint/operations requirement) plus
   `LREQ-ARCH-030`, or (b) leave it unassigned and cite the frozen interface
   (`chunk-00.md:114`) as the authority. This plan records the bump and maps it
   to `LREQ-GQL-010` + `LREQ-ARCH-030` as the working assumption; the ownership
   assignment itself is a human decision. (`SRS-lean-v2.md:305-308`, `:250-251`.)
2. **Exact report phrase for LREQ-RPT-050 after D1-S4.** The replacement wording
   at `report.py:55` and `:128` must match the operator's **applied** SRS text
   for D1-S4/D1-S5, which does not exist until the operator edits the SRS
   (§13). The plan fixes the substance (index **is** a trailing-7-day view
   count, stable within a run, refreshed at most daily; not lifetime/cumulative,
   not daily-average), but the literal string and therefore the assertion in
   `test_report.py::test_report_states_heuristic_and_six_distinctions` must be
   taken from the applied SRS text. (`SRS-lean-v2.md:1163-1170`, `:1385`.)

Carried forward as recorded-but-not-blocking:

- The frozen interface files (`chunk-00.md`) still record `"1.0.0"` and the
  three-member enum after this chunk ships; reconciling them is a future
  interface re-issue, outside the allowlist.
- `_ENUM_COLUMNS` is Python-side validation, not DDL; a future schema-versioning
  policy may revisit whether it belongs in the version (OQ-13 context).

---

## 13. Critical human checkpoint — SRS edits D1-S1…D1-S7

The seven edits below target `Documents/SRS-lean-v2.md` and are **operator-only**
(chunk-26 §13.4 table, §14.6). **No agent may apply them.** Gate bullet 6 cannot
pass without the operator's applied edit plus diff/sha256 evidence in
`Documents/runs/chunk-28.md`; otherwise the gate is **FAILED** and the chunk
**BLOCKED**. Line numbers are the current pre-edit Lean 1.0.3 locants.

| # | Section | Edit |
|---|---|---|
| D1-S1 | §1.4 definition (`SRS:133`) | Redefine "Age-normalized page-view index" as the **weekly page-view count** `= product_page_views` (trailing 7 days); state it is a weekly count and not a lifetime average or daily average. |
| D1-S2 | §7.2 **LREQ-MET-040** (`SRS:741-750`) | `age_normalized_page_view_index = product_page_views * 7 / age_days_exact` → `= product_page_views`; update the usable-conditions sentence so `MIN_AGE_DAYS_FOR_RATE` is an eligibility floor, not a rate normalizer. |
| D1-S3 | §6.3 enumeration (`SRS:675`) | Add `validated_windowed_weekly` to the allowed status values and state its meaning (validated trailing-7-day semantics). |
| D1-S4 | §10 **LREQ-RPT-050** (`SRS:1163-1170`) | Replace "the page-view index from a weekly traffic rate" with wording that the index **is** a trailing-7-day view count and is not a lifetime/cumulative or daily-average rate. |
| D1-S5 | §16 limitations item 5 (`SRS:1385`) | Update the "unvalidated semantics … not a validated weekly traffic measurement" wording to the validated weekly semantics. |
| D1-S6 | Appendix A formula block (`SRS:1442`) | `age_normalized_page_view_index = product_page_views`. |
| D1-S7 | Revision history + header (`SRS:10,18-21`) | New row/version (suggest Lean 1.0.4) recording the semantics correction. |

---

## 14. Role map (LREQ IDs)

| LREQ | Role in this chunk |
|---|---|
| `LREQ-MET-040` (`SRS:741-750`) | **Primary.** The formula, docstring, usability sentence, the run token, and the non-clobber guard. |
| §1.4 (`SRS:133`) | Primary (D1-S1): the definition the docstring must match. |
| §6.3 (`SRS:675-680`) | Primary contract: the enum gains `validated_windowed_weekly`; `contradicted` unchanged. |
| `LREQ-MET-030` / `LREQ-MET-050` / `LREQ-MET-060` / `LREQ-MET-100` | Supporting contract, unchanged formulas; numeric outputs re-baselined. |
| `LREQ-SCR-050` (`SRS:985-987`) | Supporting: the new token is not `contradicted`, so D/Q availability is unchanged; pinned by the non-clobber node. |
| `LREQ-EVD-020/030/040` (`SRS:1016-1046`) | Supporting: rankability policy unchanged; per-category states move with the re-baselined metrics. |
| `LREQ-RPT-050` (`SRS:1163-1170`) | Supporting / integration completion: the two report caveats. |
| `LREQ-GQL-010` (`SRS:305-308`) | Supporting contract: `ENDPOINT_CONTRACT_VERSION` `1.0.0 → 1.1.0`. |
| `LREQ-ARCH-030` (`SRS:250-251`) | Supporting: versioned provenance, `SCHEMA_VERSION` `1.2.0 → 1.3.0`. |
| `LREQ-MET-010` (`SRS:691-693`) | Supporting, unchanged: null/zero/invalid/unavailable distinctness. |
| `LREQ-NFR-040` (`SRS:1207-1208`) | Supporting: docstrings and hints. |
| `LREQ-TST-010` / `LREQ-TST-050` (`SRS:1261-1262`, `:1280-1284`) | Test coverage for the new/renamed nodes. |
| `LREQ-SEC-020` (`SRS:367-368`) | Supporting: no secret in changed artifacts. |
