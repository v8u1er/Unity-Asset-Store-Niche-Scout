# Chunk 29 — Coveo retrieval-window coverage remediation (plan)

Status: DRAFT — blocked on Open questions 1 and 2 (see §9). Do not freeze until a human
answers them; both change a frozen public interface or the detection rule.

Branch: `chunk-29` (per `Documents/runs/chunk-29.md` §Branch). Base: `main`.
Predecessors: Chunks 3, 7B, 8, 9A, 9B, 10, 11 are frozen and merged. This plan changes
`models.WarningCode` (frozen in `interfaces/chunk-00.md`) and
`collector_coveo.CategoryDiscoveryResult` (frozen in `interfaces/chunk-03.md`); both
interface files must be amended in the same change (see §5).

Origin (operator-confirmed, `Documents/runs/chunk-29.md` §Origin): for
`3d/characters/humanoids` the live Coveo response reports
`totalCount = totalCountFiltered = 8294`, the storefront stops after 52 pages × 96 =
4,992 persisted rows, and the tool reports `complete` / `bounded` / `rankable` with no
warning. Root cause: `collector_coveo._has_read_enough` (`src/niche_scout/collector_coveo.py:2194`)
and `collector_coveo._endpoint_may_hold_more` (`src/niche_scout/collector_coveo.py:2219`)
treat an empty terminal page as exhaustion without reconciling the persisted count
against the verified `totalCount`.

SRS authority for this chunk: `Documents/SRS-lean-v2.md` LREQ-EXT-050 (lines 282–288,
including the Lean 1.0.5 addendum), LREQ-MET-070 (lines 799–817), LREQ-EXT-090 (lines
304–306), and Appendix C `DISCOVERY_INCOMPLETE` (line 1522).

---

## 1. Scope, non-goals, LREQ roles, files touched

### 1.1 Scope (in)

1. Detection in `collector_coveo.py`: an endpoint-reported verified `totalCount` that the
   traversal cannot reconcile SHALL yield `DiscoveryStatus.TRUNCATED` and SHALL record the
   shortfall as a typed condition (LREQ-EXT-050 addendum, line 288).
2. Warning plumbing: `WarningCode.DISCOVERY_INCOMPLETE` (SRS Appendix C line 1522) added to
   `models.py`, emitted by `pipeline._warning_codes`, surfaced through the existing
   `warnings_json` report path.
3. Verification (not re-implementation) that the existing
   `truncated → _breadth_verified_total=None → breadth fallback / INCOMPLETE_ESTIMATE`
   chain satisfies LREQ-MET-070 for the newly detected case.
4. Audit of `_endpoint_may_hold_more` / `_breadth_verified_total` / `bounded` consistency
   under cap-truncation; fix only if a real inconsistency is found, else record as
   consistent.

### 1.2 Non-goals (explicitly NOT in this chunk)

- No change to `metrics.py` or `scoring.py` (no new formula, threshold, weight, or reason).
- No change to the seven-member `DiscoveryStatus` set (LREQ-EXT-050 line 286 enumerates
  exactly seven); "shortfall" is carried by a typed field, not a new status token (§9 Q1).
- No change to `breadth_raw`'s fallback rule, `competition_component`, or
  `evaluate_pre_sensitivity_evidence` — the chain already implements LREQ-MET-070 (§4).
- No change to `report.py` rendering (it renders arbitrary stored codes: `src/niche_scout/report.py:725-726`, `800-806`).
- No change to `database.py` schema; `unreconciled_total_shortfall` is not persisted as a
  column in this chunk (the warning code is what persists, inside `warnings_json`).
- Sampling representativeness (LREQ-SMP-050 / LREQ-SMP-070) and any alternative collection
  strategy remain out of scope (§8).
- No scheduling, resume, historical trends, extra GraphQL fields, favorite-count,
  configurable weights, or confidence intervals (AGENTS.md out-of-scope list).

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-EXT-050` (detection + recorded shortfall; Chunk 3 was primary, this remediation completes the addendum for the empty/short terminal page) |
| Supporting contract | `LREQ-MET-070` (verified-only via fallback; verified by test, not changed), `LREQ-EXT-090` (warning generation for the degraded category) |
| Integration completion | `LREQ-EXT-090` warning surface via `pipeline._warning_codes` + `report.warnings_json`; `LREQ-ARCH-010` (contract enum set pin in `tests/test_contracts.py`) |

### 1.4 Files touched (plan §6 authority)

Production:
- `src/niche_scout/collector_coveo.py` — detection helper + `CategoryDiscoveryResult` field wiring.
- `src/niche_scout/models.py` — `WarningCode.DISCOVERY_INCOMPLETE`.
- `src/niche_scout/pipeline.py` — `_warning_codes` emission.

Interfaces (frozen; must be amended by the lead in the same change):
- `Documents/interfaces/chunk-00.md` — add `DISCOVERY_INCOMPLETE` to `WarningCode`.
- `Documents/interfaces/chunk-03.md` — add `unreconciled_total_shortfall` to
  `CategoryDiscoveryResult`.
- `Documents/interfaces/chunk-10.md` — one-line note that `warnings_json` may now contain
  `DISCOVERY_INCOMPLETE` (no shape/signature change).

Tests:
- `tests/test_collector.py`, `tests/test_pipeline.py`, `tests/test_contracts.py`,
  `tests/traceability.json`.
- Fixture additions only if a builder is needed (reuse `tests/fixtures/coveo_discovery.py`
  `make_page` / `records` and `tests/fixtures/pipeline_fixtures.py` `coveo_page`).

No other file is in scope. Any other file needing a change is a stop-and-flag.

---

## 2. Evidence: the LREQ-MET-070 chain already exists (step 4b)

Do NOT add a new metric condition. The chain is:

1. `collector_coveo._finalize_result` sets `CategoryDiscoveryResult.discovery_status` from
   `_select_terminal_status(conditions)` (`src/niche_scout/collector_coveo.py:2399-2400`).
2. `pipeline._breadth_verified_total` returns `None` when
   `discovery.discovery_status is DiscoveryStatus.TRUNCATED` or the filter verdict is not
   `VERIFIED` (`src/niche_scout/pipeline.py:2785-2789`).
3. The same `None` is passed as `verified_total_count` to `BreadthMetricInput`
   (`src/niche_scout/pipeline.py:3488`).
4. `metrics.breadth_raw` returns `distinct_canonical_discovered_count` /
   `incomplete_estimate` when `verified_total_count is None`
   (`Documents/interfaces/chunk-7B.md` §4.1).
5. `scoring.competition_component` returns `None` unless `breadth_source is
   BreadthSource.VERIFIED_TOTAL_COUNT` **and** `breadth_completeness_status is
   COMPLETE` (`Documents/interfaces/chunk-08.md` §4).
6. `scoring.not_rankable_reasons` emits
   `COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE` exactly when `score.competition is None`
   (`Documents/interfaces/chunk-9A.md` §4.2); the category is therefore not `rankable`.

SRS LREQ-MET-070 (lines 807–817) requires exactly this: fallback breadth is not `rankable`,
and competition is unavailable when discovery is unverified or incomplete. Conclusion:
once detection (step 1) marks the unreconciled case `truncated`, steps 2–6 already satisfy
LREQ-MET-070 with no new condition. This plan adds only detection, the recorded shortfall,
and the warning.

---

## 3. Ordered implementation steps

### Step 1 — Detection in `collector_coveo.py` (LREQ-EXT-050)

Add one module-private pure helper near `_endpoint_may_hold_more` (state the exact
signature in §5; behavior below):

```python
def _verified_total_shortfall(
    *,
    verified_total: int | None,
    persisted: int,
    max_results: int,
    terminal_page_short: bool,
) -> int | None:
    ...
```

Behavior (exact, for the test author):
- `verified_total is None` → `None` (no verified total to reconcile).
- `persisted >= max_results` → `None` (the read cap already recorded `truncated`; the cap
  case is `DISCOVERY_TRUNCATED`, never `DISCOVERY_INCOMPLETE`).
- `terminal_page_short is False` → `None` (a full terminal page implies cap or a page
  failure, both handled elsewhere; a full page is never an exhaustion signal).
- `persisted >= verified_total` → `None` (the read reconciled; this includes the verified
  zero-result case `0 >= 0`).
- otherwise → `verified_total - persisted` (always `> 0`).
- Never returns `0`: a returned value is a positive shortfall, `None` means "not
  applicable", preserving missing-not-zero.

In `discover_category`'s post-loop block (after the existing
`if last_page is not None and _endpoint_may_hold_more(...)` at
`src/niche_scout/collector_coveo.py:2139-2142`), add:

```python
persisted = counters.emitted
failure_recorded = (
    DiscoveryStatus.PAGE_FAILED in counters.conditions
    or DiscoveryStatus.REQUEST_FAILED in counters.conditions
)
if not failure_recorded and last_page is not None:
    shortfall = _verified_total_shortfall(
        verified_total=counters.total_count,
        persisted=persisted,
        max_results=max_results,
        terminal_page_short=len(last_page.records) < page_size,
    )
    if shortfall is not None:
        counters.conditions.append(DiscoveryStatus.TRUNCATED)
        counters.unreconciled_total_shortfall = shortfall
```

- Use `counters.total_count` (the endpoint's own verified `totalCount`, captured at
  `src/niche_scout/collector_coveo.py:2083-2084`), **not** `last_page.total_count`, so a
  terminal empty page that omits the member still reconciles against the total seen earlier
  in the traversal.
- `failure_recorded` excludes the failure-after-full/short-page cases, so a page failure
  keeps `DISCOVERY_PAGE_FAILED` and does not also fabricate a shortfall.
- Do not change `_has_read_enough`; the empty-page branch (`:2194`) stays the loop-stop
  signal, and the shortfall helper is the post-loop reconciliation the addendum requires.
- `_endpoint_may_hold_more` is **not** changed in this step; its cap and full-page branches
  remain. (Audited in Step 4.)

### Step 2 — Record the shortfall on `CategoryDiscoveryResult` (LREQ-EXT-050)

Add the fields to `_CategoryCounters` (`src/niche_scout/collector_coveo.py:1549-1574`):
`unreconciled_total_shortfall: int | None = None`.

Add to `CategoryDiscoveryResult` (`src/niche_scout/collector_coveo.py:457-481`) as the
last field, with a default so external construction stays additive:

```python
unreconciled_total_shortfall: int | None = None
```

Populate it in `_finalize_result` (`src/niche_scout/collector_coveo.py:2409-2425`) from
`counters.unreconciled_total_shortfall`.

### Step 3 — `WarningCode.DISCOVERY_INCOMPLETE` (models + pipeline; LREQ-EXT-090)

- `src/niche_scout/models.py`: add
  `DISCOVERY_INCOMPLETE = "DISCOVERY_INCOMPLETE"` to `WarningCode`
  (`src/niche_scout/models.py:199-217`), matching SRS Appendix C line 1522.
- `src/niche_scout/pipeline.py` `_warning_codes` (`:2666-2724`): after the conditions loop,
  add

  ```python
  if discovery is not None and discovery.unreconciled_total_shortfall is not None:
      codes.append(WarningCode.DISCOVERY_INCOMPLETE.value)
  ```

  The existing loop already appends `DISCOVERY_TRUNCATED` for the `TRUNCATED` condition, so
  the unreconciled case carries **both** warnings; that is the required distinction
  (Appendix C lists them as separate codes). Dedup/sort stays in `_warnings_json`
  (`:2727-2729`); the JSON shape is unchanged.

### Step 4 — Consistency audit (lead discretion; do not blindly change)

Audit the three names under the cap-truncation path and record the result in the run log:

- Cap path: `counters.conditions.append(TRUNCATED)` at
  `src/niche_scout/collector_coveo.py:2106-2111`, then
  `_endpoint_may_hold_more` returns `True` at `:2217-2218` and appends `TRUNCATED` again;
  `_ordered_conditions` dedups (`:1604-1610`). Terminal status is `TRUNCATED` unless a
  higher-severity condition exists (`:1585-1594`).
- `_breadth_verified_total` (`:2785-2786`) returns `None` whenever the terminal status is
  `TRUNCATED`, so `bounded = _breadth_verified_total(discovery) is not None` is `False`
  (`:2853`) and `breadth` falls back. Consistent under cap-truncation.
- New shortfall path: it appends the same `TRUNCATED` condition, so it inherits the same
  consistent chain.

Expected outcome: **already consistent**, no fix required, recorded as a run-log note.
Record as an observation (not fixed without authorization) that
`_breadth_verified_total` does not exclude a terminal `PAGE_FAILED`/`REQUEST_FAILED` with a
`VERIFIED` filter; whether that is a separate defect is out of this chunk's scope and
belongs in Open questions if the lead wants it addressed.

---

## 4. LREQ-MET-070 chain decision (step 4b conclusion)

No new condition/field in `metrics.py` or `scoring.py`. Evidence in §2. The only new
"condition" is the `counters.conditions` `TRUNCATED` already used by LREQ-EXT-050, plus the
typed `unreconciled_total_shortfall` carrier used only by the warning layer.

---

## 5. Exact typed signatures and interface impact

### 5.1 New field (frozen-interface change)

```python
@dataclass(frozen=True, slots=True)
class CategoryDiscoveryResult:
    ...  # existing fields unchanged
    unreconciled_total_shortfall: int | None = None
    """``totalCount - persisted`` when the endpoint reported a verified total the
    traversal could not reconcile, else ``None``. Always ``> 0`` when not ``None``.
    ``None`` for a reconciled read, a cap truncation, a page/request failure, or an
    absent verified total. Never ``0``. Not a ``DiscoveryStatus`` and never selected
    as ``discovery_status``."""
```

- Placement: last field, with default `None`, so no existing constructor call breaks.
- **Changes a frozen public interface:** yes. `interfaces/chunk-03.md` §Typed structures
  (lines 138–154) must be amended, and §semantics (lines 193–198) gains the shortfall
  field. (Interface files are owned by the lead/human; the implementer only uses the
  amended text.)

### 5.2 New enum member (frozen-interface change)

```python
class WarningCode(str, Enum):
    ...  # existing members unchanged
    DISCOVERY_INCOMPLETE = "DISCOVERY_INCOMPLETE"
```

- **Changes a frozen public interface:** yes. `interfaces/chunk-00.md` §`WarningCode`
  (lines 81–96) must be amended.

### 5.3 New private helper (no frozen-interface change)

```python
def _verified_total_shortfall(
    *,
    verified_total: int | None,
    persisted: int,
    max_results: int,
    terminal_page_short: bool,
) -> int | None:
    """Return the positive unreconciled shortfall, or ``None``.

    ``None`` when ``verified_total is None``, ``persisted >= max_results`` (cap
    truncation already recorded), ``terminal_page_short is False`` (a full terminal
    page is not an exhaustion signal), or ``persisted >= verified_total`` (the read
    reconciled, including the verified zero-result case). Otherwise
    ``verified_total - persisted``, which is strictly positive. Pure; reads no clock;
    no I/O (LREQ-ARCH-010/020).
    """
```

- Module-private (leading underscore); not added to `interfaces/chunk-03.md`'s public
  function list. Tests exercise it through `discover_category`.

### 5.4 `_warning_codes` (long internal helper; chunk-10 §5 is not a frozen signature)

No signature change to `run_pipeline`, `PipelineResult`, or any chunk-10 §2/§5 name.
`interfaces/chunk-10.md` §6 `warnings_json` shape is unchanged (array of codes); only the
set of possible codes grows — add a one-line note.

### 5.5 Confirmed NO change (interfaces read)

`interfaces/chunk-07B.md`, `chunk-08.md`, `chunk-09A.md`, `chunk-09B.md`: no public
signature, reason vocabulary, or semantics change. `chunk-07B` `BreadthMetricInput` keeps
`verified_total_count: int | None`; the truncated case passes `None`. `chunk-08`
`competition_component` and `chunk-09A`/`chunk-09B` evidence/rankability logic are
untouched and already handle the fallback.

---

## 6. Test plan (exact node IDs; every analytical node marked `@pytest.mark.lreq(...)`)

### 6.1 `tests/test_collector.py` — marker `@pytest.mark.lreq("LREQ-EXT-050")`

| Node ID | Marker(s) | Asserts | Golden values |
|---|---|---|---|
| `tests/test_collector.py::test_empty_page_with_unreconciled_verified_total_is_truncated` | LREQ-EXT-050 | `discovery_status is DiscoveryStatus.TRUNCATED`; `TRUNCATED in conditions`; `total_count == 8294`; `observations_emitted == 96`; `unreconciled_total_shortfall == 8198`; no zero-asset reading | pages: 96 records `total_count=8294`, then `[]` `total_count=8294`; `persisted=96`; `8294-96=8198` |
| `tests/test_collector.py::test_terminal_empty_page_without_total_still_reconciles_against_seen_total` | LREQ-EXT-050 | truncation still detected when the empty page omits `totalCount` but an earlier page reported it; `unreconciled_total_shortfall == 100` | page 1: `PAGE_SIZE` records `total_count=PAGE_SIZE+100`; page 2: `[]` `total_count=None`; shortfall `100` |
| `tests/test_collector.py::test_short_page_reconciling_verified_total_stays_complete` | LREQ-EXT-050 | `COMPLETE`; `TRUNCATED not in conditions`; `unreconciled_total_shortfall is None` | total `PAGE_SIZE+4`; pages `[96, 4]`; `persisted=100`; `100 >= 100` → `None` |
| `tests/test_collector.py::test_natural_terminal_page_without_verified_total_stays_complete` | LREQ-EXT-050 | `COMPLETE`; `total_count is None`; `unreconciled_total_shortfall is None` (regression for `test_pagination_stops_at_natural_terminal_page`) | total `None`; pages `[96, 7]`; shortfall `None` |
| `tests/test_collector.py::test_verified_zero_result_yields_no_shortfall` | LREQ-EXT-050 | `COMPLETE`; `total_count == 0`; `unreconciled_total_shortfall is None` | `[]` `total_count=0`; `0 >= 0` → `None` |
| `tests/test_collector.py::test_cap_truncation_records_no_unreconciled_shortfall` | LREQ-EXT-050 | `TRUNCATED`; `TRUNCATED in conditions`; `unreconciled_total_shortfall is None` (cap stays `DISCOVERY_TRUNCATED`) | reuse `paging_opener(PAGE_SIZE, MAX+PAGE_SIZE)`; guard `persisted >= max_results` |

Regression preservation: the existing nodes
`test_pagination_stops_at_verified_total_count`,
`test_pagination_stops_at_natural_terminal_page`,
`test_pagination_truncates_at_max_results_and_retains_api_count`,
`test_failed_page_never_becomes_zero_assets`, and
`test_zero_result_category_requires_verified_filter` must still pass unchanged (cases ii
and iii).

### 6.2 `tests/test_pipeline.py` — markers `LREQ-EXT-050`, `LREQ-EXT-090`, `LREQ-MET-070`

Extend the existing end-to-end scenario so the truncated category ends on an **empty**
terminal page instead of the read cap (add a fixture variant in
`tests/fixtures/pipeline_fixtures.py`; re-caption `TRANSPORT_TRUNCATED_CATEGORY`'s script
to `[full page, empty page]` with `total_count=2000`). Then:

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_pipeline.py::test_unreconciled_total_emits_discovery_incomplete_distinct_from_truncated` | LREQ-EXT-050, LREQ-EXT-090 | the row's `discovery_status == TRUNCATED.value`; `json.loads(warnings_json)` contains **both** `"DISCOVERY_INCOMPLETE"` and `"DISCOVERY_TRUNCATED"`, and they are different entries (test v) |
| `tests/test_pipeline.py::test_unreconciled_total_falls_back_to_incomplete_breadth_and_is_not_rankable` | LREQ-MET-070, LREQ-EXT-050 | the row's `breadth_source == "distinct_canonical_discovered_count"`, `breadth_completeness_status == "incomplete_estimate"`, `competition_component` / `missing_components_json` show `C` unavailable, `rankability_status == NOT_RANKABLE.value`, `evidence_grade == INSUFFICIENT.value` (test iv) |

Add `@pytest.mark.lreq("LREQ-MET-070")` to the second node; add
`tests/traceability.json` entries for every new node (§6.4).

### 6.3 `tests/test_contracts.py` — marker `@pytest.mark.lreq("LREQ-ARCH-010")`

Update the existing node `tests/test_contracts.py::test_status_values_and_mandatory_fields_are_typed`
(the enum-set pin at `tests/test_contracts.py:854-874`): insert
`"DISCOVERY_INCOMPLETE"` into `expected_warnings`. No new node ID (test vi). Do not change
the node name or its traceability key.

### 6.4 `tests/traceability.json`

Add/extend entries (key = node ID, value = list of LREQ IDs):
- `tests/test_collector.py::test_empty_page_with_unreconciled_verified_total_is_truncated` → `["LREQ-EXT-050"]`
- `...::test_terminal_empty_page_without_total_still_reconciles_against_seen_total` → `["LREQ-EXT-050"]`
- `...::test_short_page_reconciling_verified_total_stays_complete` → `["LREQ-EXT-050"]`
- `...::test_natural_terminal_page_without_verified_total_stays_complete` → `["LREQ-EXT-050"]`
- `...::test_verified_zero_result_yields_no_shortfall` → `["LREQ-EXT-050"]`
- `...::test_cap_truncation_records_no_unreconciled_shortfall` → `["LREQ-EXT-050"]`
- `tests/test_pipeline.py::test_unreconciled_total_emits_discovery_incomplete_distinct_from_truncated` → `["LREQ-EXT-050", "LREQ-EXT-090"]`
- `tests/test_pipeline.py::test_unreconciled_total_falls_back_to_incomplete_breadth_and_is_not_rankable` → `["LREQ-MET-070", "LREQ-EXT-050"]`
- existing `tests/test_contracts.py::test_status_values_and_mandatory_fields_are_typed` unchanged key, marker already `LREQ-ARCH-010`.

The `LREQ-EXT-050` and `LREQ-MET-070` keys already exist; append nodes, do not remove any.

---

## 7. Golden vectors / fixtures

Hand-computed, `PAGE_SIZE == 96` (`tests/test_collector.py:336`):

| # | Traversal | persisted | verified total | terminal page | shortfall | status |
|---|---|---|---|---|---|---|
| A | 96 full page, then `[]` total 8294 | 96 | 8294 | empty | `8294-96 = 8198` | `truncated` |
| B (origin) | 52 full pages (4992), then `[]` total 8294 | 4992 | 8294 | empty | `8294-4992 = 3302` | `truncated` |
| C | 96, then 4, total 100 | 100 | 100 | short | `None` (reconciled) | `complete` |
| D | 96, then 7, total `None` | 103 | `None` | short | `None` | `complete` |
| E | `[]` total 0 | 0 | 0 | empty | `None` (`0 >= 0`) | `complete` |
| F | cap `MAX+PAGE_SIZE`, cap reached | `MAX` | `MAX+PAGE_SIZE` | full | `None` (cap) | `truncated` (cap only) |

Vectors A–F are analytic outputs per `_verified_total_shortfall` §5.3; assert `1e-9`-style
exactness is unnecessary for ints but assert exact equality. Reuse
`tests/fixtures/coveo_discovery.make_page`, `records`, and the existing `page_response`
helper (`tests/test_collector.py:171-183`). For pipeline, extend
`tests/fixtures/pipeline_fixtures.py` around `:1076-1099`; keep fixture credentials
redacted and offline.

---

## 8. Dependency ordering and scope statement

- Depends on frozen Chunks 3 (`CategoryDiscoveryResult`), 7B (`BreadthMetricInput`),
  8 (`competition_component`), 9A/9B (evidence/rankability), 10 (`_warning_codes`,
  `_breadth_verified_total`), 11 (report rendering). All are merged; no back-port.
- Blocking ordering: the interface amendments (`chunk-00.md`, `chunk-03.md`, `chunk-10.md`)
  land **before or with** the implementation so the frozen contract matches the code.
- Downstream: Chunk 11 report already renders any `WarningCode` generically (no code
  change); Chunk 12 CLI needs nothing (warnings are not exit-code inputs); Chunk 13's
  static checks must not flag the new code (it is Appendix C vocabulary).
- Explicitly out of scope and unchanged: sampling representativeness (`LREQ-SMP-050`,
  `LREQ-SMP-070`) and all alternative collection strategies (AGENTS.md out-of-scope list).
  This chunk makes an unreconciled read honest (`truncated` + `DISCOVERY_INCOMPLETE`); it
  does not change how the population is sampled or the denominator estimated.

---

## 9. Open questions (raise, do not decide)

**Q1 — carrier for the recorded shortfall.**
- Option (a) *(recommended in §5.1/§5.2)*: add
  `CategoryDiscoveryResult.unreconciled_total_shortfall: int | None = None`, amend
  `interfaces/chunk-03.md`. Carries the amount, keeps the seven-member `DiscoveryStatus`
  set intact, and gives the warning layer a distinguish-able signal for
  `DISCOVERY_INCOMPLETE` vs `DISCOVERY_TRUNCATED`.
- Option (b): reuse `CategoryDiscoveryResult.conditions` only. This cannot express the
  shortfall amount and cannot yield a warning distinct from `DISCOVERY_TRUNCATED` unless a
  new `DiscoveryStatus` member (e.g. `INCOMPLETE`) is added — which contradicts
  LREQ-EXT-050's enumerated seven-status set (SRS line 286) and the frozen
  `DiscoveryStatus` in `interfaces/chunk-00.md`. Would require an operator-authorized SRS
  amendment.
- Option (c): overload `total_count` / `api_reported_count`. Rejected as a design: it
  destroys the verified-total fact and is not a "recorded condition".
- Consequence: (a) — one additive frozen-interface field, test list as written; (b) —
  changes the SRS status set and rewrites §3/§5/§6; (c) — not viable.
- **Needs a human decision before this plan can freeze.**

**Q2 — materiality of the shortfall.**
- Option (a) *(SRS-faithful)*: strict `persisted < verified_total` (any shortfall reserves
  `truncated` + `DISCOVERY_INCOMPLETE`). No new constant; matches the addendum wording
  "cannot reconcile" without a tolerance.
- Option (b): a configurable materiality threshold (e.g. shortfall must exceed a constant
  or a fraction of `verified_total`). Consequences: introduces a new SRS §14 constant and a
  config key, requires an operator-authorized SRS edit, changes detection semantics and the
  test vectors in §6/§7, and risks silently accepting a real coverage gap — the exact
  failure this chunk exists to fix.
- **Needs a human decision; the plan assumes (a) pending that decision.**

Additional recorded items (not blockers):
- The consistency audit in Step 4 is expected to conclude "already consistent"; if the lead
  wants the `PAGE_FAILED`-with-`VERIFIED`-filter nuance (see Step 4) fixed, that is a
  separate scope decision with its own LREQ-MET-070/EXT-090 evidence.

---

## 10. Gate checklist

Each bullet names a concrete command or a file:line evidence source.

- [ ] `python -m pytest -q` — all existing and new nodes pass (collector, pipeline,
      contracts suites included; §6.1–6.3).
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; every new node has a
      marker and a `tests/traceability.json` entry (§6.4).
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0; `metrics.py` and
      `scoring.py` still import no I/O (unchanged; `interfaces/chunk-7B.md` §1,
      `interfaces/chunk-8.md` §1).
- [ ] Detection: `src/niche_scout/collector_coveo.py:2139-2142` plus the new shortfall block
      record `TRUNCATED` for vector A/B and leave vectors C–F unchanged (§7).
- [ ] Warning: `src/niche_scout/pipeline.py:2666-2724` emits `DISCOVERY_INCOMPLETE` only
      when `unreconciled_total_shortfall is not None`; `warnings_json` shape unchanged
      (`interfaces/chunk-10.md` §6).
- [ ] Interfaces amended and consistent with code: `interfaces/chunk-00.md` (WarningCode),
      `interfaces/chunk-03.md` (CategoryDiscoveryResult), `interfaces/chunk-10.md` (§6 note).
- [ ] `LREQ-MET-070` satisfied without new metric/scoring code: `pipeline.py:2785-2789`,
      `:3488`; `interfaces/chunk-7B.md` §4.1; `interfaces/chunk-8.md` §4;
      `interfaces/chunk-9A.md` §4.2.
- [ ] Regression (vi): `tests/test_contracts.py:854-874` pins the new enum member; node
      name unchanged.
- [ ] Formatter and linter configured in `pyproject.toml` run clean (read `pyproject.toml`
      to confirm the exact commands; do not assume).
- [ ] No file outside §1.4 changed (project-rules file discipline).
- [ ] Run log `Documents/runs/chunk-29.md` records the Step 4 audit outcome.

---

## 11. Status

Plan is DRAFT and **blocked** on Q1 and Q2. Recommended resolutions: Q1 option (a),
Q2 option (a). Once confirmed, amend the three interface files and freeze this plan.
