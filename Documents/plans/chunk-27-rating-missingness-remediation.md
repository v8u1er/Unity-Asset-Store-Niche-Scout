# Chunk 27 — Rating missingness remediation (D2)

Status: FROZEN

Chunk 27 is a remediation / follow-on chunk with **no dependency-map §3/§4 row**
(precedent: chunks 14, 24, 25, 26). Registration is plan + run log + branch
(`chunk-27`). The governing defect analysis is
`Documents/plans/chunk-26-analytical-defect-remediation.md` §4 (D2 evidence,
downstream consumers, layer/rule) and §14.1 (operator-adopted OQ-3/OQ-4); §2 item 2.
This plan records the operator-fixed scope and the operator-adopted answers; it does
not re-open them.

Source of truth: `Documents/SRS-lean-v2.md` (`LREQ-` IDs + section numbers),
`Documents/requirements-dependency-map.md`, `Documents/interfaces/chunk-05.md`.

---

## 1. Scope and out of scope

### 1.1 In scope (D2 only)

Unity returns a literal `0` for `rating.average` / `rating.count` on unrated assets.
`collector_graphql` maps those literals to `0.0` / `0` and persists them, so a
"no rating" state is indistinguishable from a real zero. SRS §1.2
(`SRS-lean-v2.md:92-93`) forbids silently converting missing/invalid/contradictory/
unavailable values to zero, and §6.4 `LREQ-GQL-050` (`SRS-lean-v2.md:341-343`)
requires failed fields to remain null or unavailable, never filled with zero or
another default.

The fix is at the **I/O adapter**: `src/niche_scout/collector_graphql.py`
ProductDetail field mapping and the ProductDetail success-result issue channel.
The pure layer (`metrics.py`, `scoring.py`, `validation.py`) is **unchanged**.

### 1.2 Explicitly NOT in this chunk

- No change to `metrics.py`, `scoring.py`, or `validation.py`. `metrics._classify_rating_average`
  keeps its inclusive `[0, 5]` check (LREQ-MET-090, `SRS-lean-v2.md:853-869`).
- No SRS edit.
- No `SAMPLING_RULE_VERSION`, `SCHEMA_VERSION`, or `ENDPOINT_CONTRACT_VERSION` bump.
- No change to `pipeline.py`, `database.py`, `report.py`, config, or
  `Documents/interfaces/`.
- No change to `enrichment_observations.product_detail_error_summary` behavior on the
  success path (§7, rejected alternative), and no new per-row column.
- D1, D3, D4, D5 from chunk-26 are not touched here (OQ-9: `chunk-27` = D2 only).
- No rankability improvement is claimed (§6).

---

## 2. Evidence (read: file:line, LREQ IDs)

| Fact | Locator | LREQ |
|---|---|---|
| `_usable_number` passes a literal `0`/`0.0` through unchanged; only `None` for a JSON `null` | `collector_graphql.py:1062-1081` | LREQ-GQL-040 |
| Rating members are extracted as `rating_average_value` / `rating_count_value` (typed: `float` / `int`) | `collector_graphql.py:1237-1248` | LREQ-GQL-040 |
| Wrong-scalar-type issues for `rating.average` / `rating.count` | `collector_graphql.py:1249-1272` | LREQ-GQL-040 |
| `ProductDetailFields` typed fields `rating_average: float \| None`, `rating_count: int \| None` built from the typed values | `collector_graphql.py:1013-1041`, `:1304-1313` | LREQ-GQL-040 |
| Four-code structural dedup dict; unknown codes append unchanged | `collector_graphql.py:1194-1212` | — |
| `_classify_product_detail_failure` membership tests | `collector_graphql.py:1357-1370` | LREQ-GQL-040 |
| `select_operation_correlation_mode` returns `VALIDATED_POSITION` only when every payload validates | `collector_graphql.py:1603-1613` | LREQ-GQL-040 |
| Success-path `GraphQLOperationResult` build: `operation_issues`, `payload`, `error_summary=None` | `collector_graphql.py:2397-2444` | LREQ-GQL-050 |
| draft-only path re-validates via `_product_detail_fields_from_payload` | `collector_graphql.py:1960-1979`, `:2057-2068` | LREQ-GQL-050 |
| `_operation_diagnostic_issues` iterates `operation.issues` regardless of status, excluding only `graphql_id_mapping_mismatch` | `pipeline.py:619-647`; consumed at `:669` | LREQ-GQL-050 |
| `_build_observation` writes `diagnostic_summary_json` via `summarize_validation_issues` | `pipeline.py:678-693` | LREQ-GQL-050 |
| Pure-layer `[0,5]` inclusive check | `metrics.py:280-295` | LREQ-MET-090 |
| "Missing, invalid, contradictory, or unavailable values SHALL remain unavailable; they SHALL NOT be silently converted to zero" | `SRS-lean-v2.md:92-93` | §1.2 |
| "A valid operation's fields MAY be retained… Failed fields SHALL remain null or unavailable; they SHALL NOT be filled with zero or another default." | `SRS-lean-v2.md:341-343` | LREQ-GQL-050 |
| `enrichment_observations` required fields incl. `rating_average`, `rating_count` | `SRS-lean-v2.md:606-619` | §6.4 |
| `QUALITY_MIN_RATING_COUNT = 5`; quality unavailable below minimum; `rating_count` is a reliability minimum only, not a weight | `SRS-lean-v2.md:853-869` | LREQ-MET-090, LREQ-MET-100 |
| Frozen interface `GraphQLOperationValidation`, `ProductDetailFields` | `Documents/interfaces/chunk-05.md` §5.6 (`:439-481`) | — |
| Frozen interface `EnrichmentObservationDraft`, `build_enrichment_observation_draft` | `Documents/interfaces/chunk-05.md` §5.9 (`:622-691`) | — |

Operator ruling (chunk-26 §14.1, OQ-3/OQ-4): the "no rating" state is produced at the
`collector_graphql` ProductDetail mapping; the four states in §3 below stay distinct.

Lead-grounded live-DB read (2026-09-29, read-only `runtime/niche_scout.sqlite3`, run
`run-2026-09-29T05:33:21.664034+00:00`; recorded in `Documents/runs/chunk-27.md`):
2400 rows / 2400 identities; `rating_count == 0` → 1559 (all average `0.0`);
`rc == 1` → 289; `rc == 2` → 123; `rc >= 5` → 305; `rc > 0 & avg == 0` → **416**;
`avg IS NULL` → 0 and `cnt IS NULL` → 0 today; the partition sums to 2400.

---

## 3. Rule (frozen; operator-adopted Q1–Q6)

The rule applies to the **typed pair** `(rating_average_value, rating_count_value)`
produced at `collector_graphql.py:1237-1248`, i.e. the values `_usable_number` returned
(a Python `float` for `average`; a Python `int` for `count`), **not** to the raw JSON
members.

### 3.1 Typed-pair precedence table (total order)

| # | Condition (typed pair) | `rating_average` result | `rating_count` result | Issue |
|---|---|---|---|---|
| 1 | `avg is None` and `cnt is None` | `None` | `None` | none |
| 2 | `avg is None` and `cnt is not None` | `None` | `cnt` (unchanged) | none |
| 3 | `avg is not None` and `cnt is None` | `avg` (unchanged) | `None` | none (Q5) |
| 4 | `cnt == 0` and `avg is not None` and `avg > 0` | `None` | `None` | code A |
| 5 | `cnt == 0` and `avg == 0.0` | `None` | `None` | none |
| 6 | `cnt > 0` and `avg == 0.0` | `None` | `cnt` (**retained**) | code B |
| 7 | `cnt > 0` and `0 < avg <= 5` | `avg` (unchanged) | `cnt` (unchanged) | none |

Rows 1–3 and 7 are existing behavior and must not change. Rows 4–6 are new. A count
of `0` with an absent (`None`) average is row 5, not row 4 (an absent member is not a
positive average). Key the decision on the **typed** `rating_count_value == 0` and
`rating_average_value`, never on the raw member: a JSON `0.0` count (`float`) is
already rejected by `_usable_number(..., int)` (int-only) and stays the existing
`response_wrong_scalar_type` case — it must not enter this table as a zero count.

### 3.2 New issue codes (Q2)

No issue registry exists; codes are plain string literals. Use unprefixed
`snake_case` (the `response_*` prefix stays reserved for the structural validator):

| Condition | Code | Message |
|---|---|---|
| row 4 (`cnt == 0`, `avg > 0`) | `rating_average_without_rating_count` | `rating.average is positive while rating.count is zero; both are unavailable and neither is coerced to a default` |
| row 6 (`cnt > 0`, `avg == 0.0`) | `rating_average_zero_with_positive_count` | `rating.average is a zero placeholder with a positive rating.count; the average is unavailable and the count is retained as returned` |

Build them with the existing `_issue(code, message, **context)` helper
(`collector_graphql.py:574-576`); context stays redaction-safe (no raw response
body, no credentials — LREQ-SEC-020). Suggested context members are structural only,
e.g. `field="rating.average"`.

Do **not** add these codes to the four-code structural dedup dict
(`collector_graphql.py:1194-1199`): the default branch (`:1204-1205`) appends unknown
codes unchanged, so the mutation sites append them directly with no dedup interaction.

### 3.3 Q3 invariant (load-bearing)

The two new codes MUST NOT appear in `_classify_product_detail_failure`'s membership
tests (`collector_graphql.py:1357-1370`), and must not be a `response_*` code or
`invalid_state_value`. With that, the affected payload keeps `is_valid=True` and
`failure_class=GraphQLFailureClass.NONE`, and the retained count survives
(`:1326-1337`, `:1332-1334`).

Why load-bearing: `select_operation_correlation_mode` (`collector_graphql.py:1603-1613`)
returns `GraphQLOperationCorrelationMode.VALIDATED_POSITION` only when every payload
validates; marking the 416-row payload invalid would flip the persisted
`runs.graphql_operation_correlation_mode` to `EXPLICIT_KEY`, a silent contract-surface
change. New test node 6 (§9.3) pins this.

### 3.4 Q1 — issue channel = option (a) only

- Append the contradiction `ValidationIssue`(s) to the ProductDetail **success**
  result's `issues` tuple — the `operation_issues` list at
  `collector_graphql.py:2412-2440`, which is the `issues=tuple(operation_issues)`
  argument at `:2440`. `pipeline._operation_diagnostic_issues` (`pipeline.py:619-647`)
  iterates `operation.issues` regardless of status, so the issue reaches
  `PreflightObservation.diagnostic_summary_json` and
  `runs.identity_preflight_summary_json.diagnostic_summary_json`.
- Do **not** populate the per-row `enrichment_observations.product_detail_error_summary`
  (it is `NULL`-by-construction on success; option (b) would require `pipeline.py`,
  outside the allowlist).
- Do **not** change the success-path `error_summary=None` (`collector_graphql.py:2441`).
  See §7 for the rejected alternative.

### 3.5 Q1 draft-only path (frozen mechanism: one shared rating-pair builder)

The draft path re-derives fields when `fields=None` by re-validating the retained
payload through `_product_detail_fields_from_payload` →
`validate_product_detail_payload` (`collector_graphql.py:1960-1979`, `:2057-2068`), and
the success path reads the same `validation.product_detail` (`:2397-2444`). Both must
see the **same** row 4/5/6 outcomes (row 6 retains the count; row 4 nulls both; row 5
nulls both).

**One mechanism, no alternative.** The §3.1 typed-pair precedence lives in exactly one
new private function in `collector_graphql.py`:

```python
def _map_rating_pair(
    rating_average_value: float | None,
    rating_count_value: int | None,
) -> tuple[float | None, int | None, tuple[ValidationIssue, ...]]:
    """Apply the §3.1 typed-pair precedence (frozen rule).

    Returns ``(rating_average, rating_count, contradiction_issues)``. It never
    fabricates a value: row 4 returns ``(None, None, (code A,))``, row 5 returns
    ``(None, None, ())``, and row 6 returns ``(None, count, (code B,))``.
    """
```

`validate_product_detail_payload` calls it **once**, after the existing wrong-scalar-type
checks (`:1237-1272`) and before the `ProductDetailFields` construction
(`:1304-1313`). It destructures the three results into `rating_average_mapped`,
`rating_count_mapped`, `rating_issues`; extends the local `issues` list with
`rating_issues`; and passes the mapped pair into the `ProductDetailFields(...)` call at
`:1308-1313`. Because that local `issues` list becomes
`GraphQLOperationValidation.issues` (`:1336`), the contradiction codes are carried on
the validation result and — via `operation_issues = list(validation.issues)`
(`:2412`) — on the success `GraphQLOperationResult` with no further change (§3.4).

The draft path needs **no change**: `_product_detail_fields_from_payload`
(`:2057-2068`) already reads `validation.product_detail`, i.e. the `ProductDetailFields`
produced by that one call, and `annotate_product_detail_identity` returns it with only
its identity comparison annotated. `build_enrichment_observation_draft` then copies
`detail.rating_average` / `detail.rating_count` (`:2022-2023`). One builder therefore
feeds the validated path and the draft-only path with identical row 4/5/6 fields.

Consequences (frozen): no `GraphQLOperationValidation` member is added or changed, no
`pipeline.py` field is added, and `Documents/interfaces/chunk-05.md` is not edited.
`ProductDetailFields.rating_average` / `rating_count` keep their `float | None` /
`int | None` types; the new codes ride only in `ValidationIssue` (the operation `issues`
tuple) and never enter the typed field values.

### 3.6 Q5 — positive average with absent count is unchanged

`avg > 0` with `count` absent/null yields `rating_average=avg`, `rating_count=None`, and
**no** new issue. Rationale (record, do not re-litigate): the returned average is
genuine and the count stays `None`; `metrics._classify_rating_count` already reports
`null`; no zero is fabricated, so §1.2 / LREQ-GQL-050 are satisfied without an adapter
change. §1.2's "contradictory" applies to values that actually conflict, not to a
missing peer.

### 3.7 Determinism

The mapping is a pure function of the typed pair; there is no RNG, no clock, no set/dict
ordering dependence (AGENTS.md Hard rule 9). The same response body yields the same
fields and the same ordered issue tuple on every run. Issue ordering is the existing
append order; the summary is rendered by `summarize_validation_issues`
(`validation.py:1921`), which is already deterministic and key-sorted.

---

## 4. Layer and purity

- The transformation lives entirely in `collector_graphql.py`, the I/O adapter.
- `metrics.py` and `scoring.py` are untouched and remain free of `sqlite3`, network,
  filesystem, and CLI imports and of clock reads (AGENTS.md Hard rule 1;
  `check_import_boundaries`).
- `validation.py` is untouched; the pure structural validator keeps its current codes.
- No `or 0`, `.get(k, 0)`, `fillna(0)`, or default-0 parameter is introduced. Null,
  explicit valid zero, invalid, and unavailable remain four distinct states
  (AGENTS.md Hard rule 2).
- Row 6 deliberately keeps the integer `rating_count` while nulling the average: the
  count is genuinely returned by the endpoint, and `LREQ-GQL-050` forbids filling a
  missing field with a default — it does not require discarding a member that is
  present and valid.

---

## 5. Downstream consumers and no-eligibility-change-at-default

`rating_average` / `rating_count` flow: `ProductDetailFields` →
`EnrichmentObservationDraft` (`collector_graphql.py:2016-2024`) →
`EnrichmentObservationRecord` → DB columns `rating_average` / `rating_count` (§6.4) →
`metrics` eligibility and raw estimators → scoring → report.

**Explicit statement (frozen, do not soften or upgrade):** at the shipped default
`QUALITY_MIN_RATING_COUNT = 5` (LREQ-MET-090, `SRS-lean-v2.md:853-869`) this change
alters **no quality eligibility**. Every affected row has `rating_count <= 2` (live-DB
partition: `rc == 0` → 1559, `rc == 1` → 289, `rc == 2` → 123; only 2 further
`rc > 0 & avg == 0` rows), so `metrics._classify_rating_count` already rejects each of
them with `rating_count_below_minimum` at the default, and
`quality_observation_eligibility` orders the average check before the count check
(`chunk-26` §4.2). D2 **corrects persisted audit data and matters only when the
configurable `quality_min_rating_count <= an affected row's count`**. Do **not** claim
a rankability improvement, a category-evaluability change, or an acceptance-criteria
gain from this chunk.

---

## 6. Rejected alternatives / risks

### 6.1 Rejected: re-deriving `error_summary=_error_summary(operation_issues)` at `:2441`

Setting the success-path `error_summary` from the accumulated `operation_issues` was
rejected. Today `error_summary=None` on the success path; changing it would populate
`enrichment_observations.product_detail_error_summary` for **every** success already
carrying `comparison.issues` from `annotate_product_detail_identity`
(`collector_graphql.py:2412-2415`) — a real contract-surface change with a
re-baseline blast radius across fixtures and persisted rows, beyond this chunk's D2
scope. Option (a) (§3.4) carries the issue in the run-level audit-summary channel
instead. Recorded here so it is not rediscovered.

### 6.2 Recorded only, not fixed: stale `chunk-05.md` §5.6 `ProductDetailFields` drift

`Documents/interfaces/chunk-05.md` §5.6 (`:461-481`) omits the `mapping_rule_version`
field that the live dataclass carries first (`collector_graphql.py:1029`). This is
**interface-document drift, recorded only**. This chunk does **not** fix
`Documents/interfaces/` (outside the allowlist). AGENTS.md's
"Do not modify frozen interfaces" applies; a future interface re-issue may reconcile it.

### 6.3 Risk: dedup interaction

Appending an unknown code is explicitly supported by the current dedup loop; if a
future refactor routes these codes through `error_classes`, the dedup `seen` key would
suppress duplicates. No such refactor is in scope; the invariant in §3.3 covers
`failure_class` only.

### 6.4 Risk: row-6 count retention vs. ambiguity

Row 6 retains the count while the average is unavailable. `metrics._classify_rating_count`
will still reject the retained count at the default (below 5); it remains a valid
`int` for audit. This is the operator-adopted reading (§3.1, chunk-26 §14.1 OQ-4).

---

## 7. Files touched (allowlist-checked)

| Path | Change |
|---|---|
| `src/niche_scout/collector_graphql.py` | ProductDetail typed-pair mapping (§3.1), the two new issue codes (§3.2), the Q1 channel append (§3.4), the shared field-builder for the draft path (§3.5). No change to `_classify_product_detail_failure` membership tests. No version constants. |
| `tests/test_collector.py` | Re-baseline one node (§9.1); add the new nodes (§9.3). |
| `tests/fixtures/graphql_fixtures.py` (collector fixture) | Add a **new** helper for the contradiction bodies (§9.2). Do not change `product_detail_payload` defaults. |
| `tests/traceability.json` | Delete+add the renamed node (§9.1); add entries for new node IDs (§9.4). |

Allowlist check against the dispatch and `Documents/runs/chunk-27.md`:

- Allowed: `src/niche_scout/collector_graphql.py`; `tests/test_collector.py` and
  collector fixtures; any test pinning rating null-ness; `tests/traceability.json`
  only if a new node ID is added; `Documents/plans/chunk-27-*.md`.
- **NOT touched:** `metrics.py`, `scoring.py`, `pipeline.py`, `database.py`,
  `report.py`, `config.py`, the SRS, sampling constants,
  `Documents/interfaces/`, `Documents/runs/chunk-27.md` (the run log is written by the
  lead, not by this plan or its implementers).

A needed change outside this list is a STOP-and-flag, not an edit.

---

## 8. Interfaces (frozen shapes)

No public signature changes. The following typed shapes are unchanged and pinned by
`interfaces/chunk-05.md` §5.6 / §5.9:

```python
# collector_graphql.py
@dataclass(frozen=True, slots=True)
class ProductDetailFields:
    mapping_rule_version: str
    graphql_id: str | None
    product_id: str | None
    rating_average: float | None       # row 4/5 -> None; rows 3/7 -> value
    rating_count: int | None           # rows 4/5 -> None; row 6 -> retained int
    review_count: int | None
    first_published_date_utc: datetime | None
    first_published_date_issue: str | None
    publisher_json: str | None
    category_json: str | None
    state: str | None
    state_annotation: StateEligibilityAnnotation | None
    identity_comparison: GraphQLIdentityComparisonResult | None

def validate_product_detail_payload(
    payload: object, *, mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION
) -> GraphQLOperationValidation: ...
```

`GraphQLOperationValidation` gains **no** member: its members stay exactly `is_valid`,
`failure_class`, `product_detail`, `page_views`, `issues` (`:1044-1052`). No dataclass is
extended for this chunk. The draft path inherits the transformed `ProductDetailFields`
from the single `_map_rating_pair` call inside `validate_product_detail_payload` (§3.5);
the only in-file addition is the private `_map_rating_pair` function, which is not part
of the frozen interface.

Null / edge-case behavior (exact, test-author contract):

- `validate_product_detail_payload(payload).product_detail.rating_average`:
  `None` when the member is absent, `null`, or wrong-typed; `None` for row 4/5;
  the float value for rows 3/7.
- `...rating_count`: `None` when absent, `null`, or wrong-typed; `None` for rows 4/5;
  the retained `int` for row 6; the value for rows 2/7.
- `is_valid` is `True` and `failure_class is GraphQLFailureClass.NONE` for all rows
  **except** a payload that independently qualifies for a structural failure class.
- `validation.issues` contains exactly one contradiction issue for rows 4 and 6, and
  **none** for rows 1, 2, 3, 5, 7.

---

## 9. Tests (re-baseline + new nodes + traceability)

### 9.1 Exactly one existing node's expectation changes

`tests/test_collector.py::test_product_detail_rating_average_accepts_integral_json_number`
(`:4174-4210`), parametrized case `(0, 0.0)` (its default `rating_count=210` makes it
the **row 6 / 416-row** case). Split it:

- Keep `(5, 5.0)` and `(4.5, 4.5)` as integral-acceptance cases (both are row 7,
  unchanged).
- Move `(0, 0.0)` into the new contradiction node (row 6), which asserts
  `rating_average is None` and `rating_count == 210`.
- Update its `tests/traceability.json` entry (`:287-289`) in the same change
  (rename = delete the old key + add the new key; do not leave a dangling entry).
- The node ID may stay `test_product_detail_rating_average_accepts_integral_json_number`
  for the retained `(5, 5.0)` / `(4.5, 4.5)` cases only if the node keeps asserting
  integral-type acceptance; the `(0, 0.0)` case will assert contradiction and must not
  be a parametrized case of an "accepts" node. The test author chooses the split node
  IDs but **must not** leave the old node asserting `(0, 0.0)` acceptance.

### 9.2 Fixtures

Add a **new** helper in `tests/fixtures/graphql_fixtures.py` for the contradiction
bodies; do **not** change `product_detail_payload` defaults — `rating_average=4.5` /
`rating_count=210` would ripple across existing goldens. Approved shape (follow the
existing `product_detail_payload` style):

```python
def product_detail_contradiction_payload(
    *,
    rating_average: object,
    rating_count: object,
    asset_identity_key: str = GQL_FIXTURE_ASSET_ID,
) -> dict[str, Any]: ...
```

### 9.3 New nodes (in `tests/test_collector.py`)

Each carries `@pytest.mark.lreq` and a `tests/traceability.json` entry.

1. Row 6: zero average + positive count (default `rating_count=210`) retains the count
   and appends **one** issue with code `rating_average_zero_with_positive_count`;
   `is_valid is True`, `failure_class is GraphQLFailureClass.NONE`,
   `rating_average is None`, `rating_count == 210`.
2. Row 4: zero count + positive average → contradictory, both `None`, code
   `rating_average_without_rating_count`.
3. Row 5: zero count + zero average → no rating, both `None`, and **no** contradiction
   code in `validation.issues`.
4. Row 5 variant: zero count + absent average → both `None`, no issue.
5. Q5: positive average + absent count → `rating_count is None`, `rating_average`
   retained, `is_valid is True`, no issue.
6. Q3 collateral: `select_operation_correlation_mode` still returns
   `GraphQLOperationCorrelationMode.VALIDATED_POSITION` for a keyless two-item body
   carrying the row 6 pair.

Also keep an assertion that the retained `rating_count` is a Python `int` (not a
`float`) for row 6, and that `rating_average` is a `float` where retained (rows 3/7).

Hand-computed expectations (exact in binary): `float(210)` retained as `int 210`;
`0.0`/`None` exact; no `1e-9` tolerance is needed for the null/`None` assertions, and
the existing `pytest.approx(expected, abs=1e-9)` pattern stays for float acceptance
cases. `4.5` is exactly representable (9/2); `5.0` and `0.0` are exact.

### 9.4 Traceability rule

- Existing nodes keep **byte-identical** entries except the one renamed/moved node in
  §9.1, whose entry is replaced in the same change.
- Add entries **only** for genuinely new node IDs.
- Map the new collector nodes to `LREQ-GQL-050` and `LREQ-TST-010`, plus
  `LREQ-GQL-040` where integral-scalar acceptance is still asserted (the retained
  `(5, 5.0)` / `(4.5, 4.5)` acceptance case).
- Do not touch the unchanged hits: `tests/test_collector.py:2931-2968, 2975-3013,
  3128-3151, 3921-3935, 4098-4130, 4283-4306`; `tests/test_validation.py:1747-1766,
  1792-1889` (pure layer, frozen `[0, 5]` stays); `graphql_fixtures.py:355-386`,
  `date_eligibility_fixtures.py`, `identity_preflight_vectors.py`,
  `enrichment_fixtures.py`, `metric_estimator_fixtures.py`.

---

## 10. Verification commands

Run from the repository root (PowerShell; chain with `;`). The `ruff` config in
`pyproject.toml` is `line-length = 88`, `select = ["E", "F", "I"]`; invoke ruff as a
module, matching `niche_scout.tools.quality_workflow`:

```powershell
python -m pytest -q
python -m niche_scout.tools.validate_traceability
python -m niche_scout.tools.check_import_boundaries
python -m niche_scout.tools.check_scope_prohibitions
python -m niche_scout.tools.check_secrets
python -m ruff check src/niche_scout/collector_graphql.py tests/test_collector.py tests/fixtures/graphql_fixtures.py
python -m ruff format --check src/niche_scout/collector_graphql.py tests/test_collector.py tests/fixtures/graphql_fixtures.py
```

Or the whole workflow in its fixed order: `python -m niche_scout.tools.quality_workflow`.

Baseline for comparison (ledger, `Documents/runs/chunk-27.md`): `python -m pytest -q`
→ **695 passed**. The four validators must exit 0. Ruff must add no new lint.

---

## 11. Open questions

None blocking. The operator-adopted answers Q1–Q6 are frozen in §3; the layer and scope
are operator-fixed (§1). No unresolved ambiguity remains that prevents a correct plan.

Carried forward as recorded-but-not-blocking (no action in this chunk):

- The stale `chunk-05.md` §5.6 `ProductDetailFields` drift (§6.2) is recorded only.
- The draft-path mechanism is **frozen** in §3.5: one private `_map_rating_pair`
  function in `collector_graphql.py`, called once by `validate_product_detail_payload`,
  read by the draft path through `validation.product_detail`. No dataclass change, no
  implementer choice.

---

## 12. Gate bullets

1. `rating_count==0, rating_average==0` round-trips as `None`/`None`.
2. The 416-row case persists `rating_average=None` with the integer count retained and a
   distinct, deterministic validation issue in the run-level audit-summary channel.
   **Reading (operator-adopted):** "persists … a distinct, deterministic validation
   issue" = the issue persists in the run-level audit-summary channel
   (`runs.identity_preflight_summary_json.diagnostic_summary_json`) plus the
   per-observation `diagnostic_summary_json`; the retained integer count persists in
   the observation row.
3. `count>0, avg in (0,5]` unchanged.
4. `metrics.py`/`scoring.py` unchanged; `check_import_boundaries` exit 0; no `or 0` /
   `.get(k, 0)` added.
5. pytest + four validators exit 0; ruff (check and format --check) no new lint.
6. No SRS edit; no version bump; no out-of-scope file changed.

---

## 13. Role map (LREQ IDs)

| LREQ | Role in this chunk |
|---|---|
| `LREQ-GQL-050` (`SRS-lean-v2.md:341-343`) | **Primary.** The contradiction/no-rating transformation and the issue channel. |
| `LREQ-GQL-040` (`SRS-lean-v2.md:318-323`) | Supporting contract: scalar typing stays int-only for `rating.count`, and existing integral acceptance for a non-zero average is preserved. |
| `LREQ-MET-090` / `LREQ-MET-100` (`SRS-lean-v2.md:853-869`) | Supporting contract, **unchanged**: the pure layer's `[0,5]` check and `QUALITY_MIN_RATING_COUNT = 5` are not touched; the no-eligibility-change statement (§5) is the integration completion here. |
| `LREQ-TST-010` (`tests/AGENTS.md` formula-test coverage) | Test-coverage requirement mapped by the new nodes (normal, explicit zero, missing, invalid, ties, boundary) — the new nodes supply the missing/contradictory/zero cases. |
| `LREQ-SEC-020` (`SRS` §4.3) | Supporting: the new issues are redaction-safe (no raw body/credentials). |