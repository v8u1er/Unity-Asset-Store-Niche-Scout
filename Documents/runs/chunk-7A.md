# Chunk 7A — run log (Metric eligibility, date, and page-view primitives)

Started 2026-09-20. Branch: `chunk-7A` (created from `chunk7` @ `ab9553b`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → "nothing to commit, working tree clean") |
| Branch | created `chunk-7A` from `chunk7` HEAD `ab9553b` (the 4B gate tip) |
| Prerequisite Chunk 0 | `Documents/interfaces/chunk-00.md` → `Status: VERIFIED` |
| Prerequisite Chunk 1 | `Documents/interfaces/chunk-01.md` → `Status: VERIFIED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` |
| Chunk 4A / 4B (context, not 7A prereqs) | `Documents/runs/chunk-4A.md` ends `GATE: PASSED`; `Documents/runs/chunk-4B.md` ends `GATE: PASSED` |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. Branch note: the worktree branch was `chunk7` (not `chunk-7A`); per chunk-lead step 1 a dedicated `chunk-7A` branch was created from `chunk7` HEAD `ab9553b`. |
| Plan | DONE (FROZEN) | `chunk-planner` wrote `Documents/plans/chunk-7A-metric-eligibility-date-and-page-view-primitives.md` (1028 lines, `Status: FROZEN`). First dispatch returned empty (no file); retry ran out of steps after research and surfaced 5 candidate ambiguities. Per the user's instruction, a read-only `explore` agent adjudicated all 5 against the SRS/map/frozen interfaces (evidence in the run record below). Planner then applied the adjudicated decisions and wrote the plan; a second amendment corrected value-level invalidity. |
| Plan — adjudication | DONE | 5 questions resolved: (1) eligibility lives in `metrics.py` only, `validation.py` untouched, no `PURE_MODULES` change (`chunk-01.md` §1 blesses `validation.py`'s `json` import); (2) reuse frozen `MetricResult.value`/`unavailable_reason`, no new enum, no `models.py` edit; (3) Chunk 5 owns page-view payload acceptance (`chunk-05.md` §5.7), 7A owns the metric-eligibility *semantics*; (4) 7A independently rejects naive/future dates via `models.ensure_utc`; (5) tests in `tests/test_validation.py`, new data-only `tests/fixtures/date_eligibility_fixtures.py`, no `LREQ-TST-*` marker. |
| Plan — amendment | DONE | Value-level invalidity corrected to SRS: a product-level value that is wrong-typed/negative/non-finite is classified **unavailable with a distinct reason**, never raised and never `0`. Basis: `SRS-lean.md:655–657` (LREQ-MET-010), dependency map `:211`, `:214`, gate bullet `:801` — all opened and read. The earlier brief's "decision 3" over-read `chunk-05.md:529–530` (that clause scopes *raw scalar* re-derivation, not 7A's value-level classification). Plan sections amended in place (§1, §2, §5.0, §5.1, §5.2, §5.3, §7, §8, §9.2, §9.3, §11, §12). |
| Plan — not-SRS-backed items | RECORDED | A-1: the `unavailable_reason` **string spelling** is a `RECOMMENDATION (not SRS-backed)` (outcome categories are required by LREQ-MET-010/map `:211`). A-6: `malformed` is retained in the closed vocabulary but unproduced by the 7A function set (Chunk 1 owns shape classification). A-3: condition precedence derived from the requirement sentences. These are recorded for the user; none was silently resolved as SRS-backed. |
| Plan — discrepancies | RECORDED | (a) `tests/AGENTS.md` says `tests/traceability.json` is keyed by `LREQ-*` ID; the file on disk is keyed by pytest node ID (`tests/traceability.json:2–3`). Not edited; left for Chunk 13. (b) `tests/test_validation.py` is 1228 lines, past the ~800–1000-line review trigger; the plan appends rather than splits and proposes a cluster-based boundary (§9.1). |

### Dispatch errors (verbatim)
- `chunk-planner` first dispatch: empty result, no file written → retried once (allowed).
- `chunk-planner` second dispatch: "Maximum steps reached" during research → resumed with adjudicated context.
- `chunk-planner` third dispatch (write plan): "Service temporarily unavailable. Please try again later." → retried once (allowed), succeeded.
- `chunk-planner` amendment dispatch: applied all edits, then hit "Maximum steps reached" before a final read-through; the lead read the amended sections (§1–§2 header, §5.1, §5.3, §12) and found them internally consistent.
- `test-author` first dispatch: returned an empty result after writing only part of the surface — `tests/fixtures/date_eligibility_fixtures.py` (328 lines, complete data module), the `tests/fixtures/__init__.py` re-export (2 lines), and the two import lines in `tests/test_validation.py` (`import fixtures.date_eligibility_fixtures as dfx`, `from niche_scout import metrics as m`). No Chunk 7A test nodes were appended and `tests/traceability.json` was not touched. Lead confirmed the partial state by reading the three files and running `pytest tests/test_validation.py -q` → 22 passed (existing tests only). Resumed the same session with the completion brief.

### Tests

| Item | Result |
|---|---|
| Test-author dispatch 2 | Completed. Appended the Chunk 7A section to `tests/test_validation.py` (37 nodes per plan §9.3), added 37 entries to `tests/traceability.json`, kept the 328-line fixture module. |
| Lead verification (step 4) | `python -m pytest tests/test_validation.py -q` → **36 failed, 23 passed**; `--collect-only` → **59 collected** (22 pre-existing + 37 new; no collection errors). Every failure is a missing-implementation `AttributeError` on a not-yet-existing `niche_scout.metrics` name (`normalize_metric_timestamp`, `age_days_exact`, `age_normalized_page_view_index`, `metric_state_eligibility`, `is_within_recent_window`, `stratum_is_usable`, `quality_observation_eligibility`, `METRIC_REASON_*`, `METRIC_UNAVAILABLE_REASONS`) — the required missing-implementation failure shape, no syntax/collection errors. |
| Lead verification — suite | `python -m pytest tests -q` → **36 failed, 217 passed**; `tests/test_contracts.py` → 22 passed (the pre-existing test-file inventory is not broken by the appended nodes). |
| Lead verification — traceability | `python -m niche_scout.tools.validate_traceability` → "Traceability valid: 7 Chunk 0 requirements mapped, 207 matrix nodes, 89 defined LREQ IDs" (exit 0). The tool's own count is **207**; the JSON file now holds **244** entries, 59 of them `tests/test_validation.py` nodes (lead query on `tests/traceability.json`). The tool is still Chunk-0-scoped per its docstring; the extra entries are validator-visible but not yet required-set-enforced (widening is Chunk 13 / LREQ-NFR-060). The tool's note lists 7 pre-existing unmarked tests outside this chunk. |
| Lead verification — boundaries | `python -m niche_scout.tools.check_import_boundaries` → "Import boundaries valid for metrics.py, scoring.py" (exit 0). |
| Lead verification — lint | `ruff check tests/fixtures/date_eligibility_fixtures.py tests/fixtures/__init__.py` → clean. `ruff check tests/test_validation.py` → **33 E501s, all pre-existing**: the HEAD revision of that file (1228 lines, byte-read via `git show HEAD:tests/test_validation.py` through Python) has long lines at `[105, 106, 124, 150, 185, 240, 331, 337, 350, 380, 421, 422, 501, 504, 513, 528, 539, 585, 615, 634, 668, 823, 831, 861, 871, 882, 938, 943, 950, 1033, 1196, 1221, 1222, 1225]` — **34** long lines; after the insertion of two import lines near the top they map 1:1 to the current `[107, 108, 126, 152, 187, 242, 333, 339, 352, 382, 423, 424, 503, 506, 515, 530, 541, 587, 617, 636, 670, 825, 833, 863, 873, 884, 940, 945, 952, 1035, 1223, 1224, 1227]` — **33**. One HEAD long line (`:1196`) is gone from the current file; the appended Chunk 7A section (`:1231`–end) has none. Counted by reading HEAD's bytes through Python (`len(line) > 88`) and by `ruff check` on the working tree. **Not fixed** (whole-file reformat of a Chunk 1 file is outside this chunk's file scope); reported instead. |

Also confirmed by the lead: mixed-case `"Published"` is treated as **eligible** by the tests, matching
`src/niche_scout/validation.py:1631–1647` (read) and the corrected plan §9.2.

### Implementation and lead verification (step 5–6)

| Item | Result |
|---|---|
| `impl-deep` dispatch | DONE. Added the seven primitives, the result dataclasses, the reason vocabulary, and the task-breakdown docstrings to `src/niche_scout/metrics.py` (+587/−2); `MetricInput`/`MetricResult`/`RawMetricBundle` unchanged. No test, fixture, traceability, `models`, `validation`, or `Documents/` file touched. |
| Lead `pytest -q` | **253 passed, 0 failed** (re-run by the lead, not taken from the subagent). |
| Lead `check_import_boundaries` | exit 0 — "Import boundaries valid for metrics.py, scoring.py". |
| Lead `validate_traceability` | exit 0 — "Traceability valid: 7 Chunk 0 requirements mapped, 207 matrix nodes, 89 defined LREQ IDs". |
| Lead `ruff check`/`ruff format --check` | `src/niche_scout/metrics.py` → "All checks passed!" / "1 file already formatted". |
| Lead import audit | AST walk of `src/niche_scout/metrics.py` → `['__future__', 'math', 'dataclasses', 'datetime', 'models', 'validation']`: no forbidden module, no I/O, no `json`. Clock scan: no `now(`/`utcnow(`/`today(`/`time.time(` in the file (the purity test also covers this). |

### Review (step 7) — round 1

| Item | Result |
|---|---|
| `spec-reviewer` round 1 (initial) | `VERDICT: PASS`, no Blocker, no Major. Independent commands: `pytest -q` → 253 passed; `tests/test_validation.py -q` → 59 passed; `validate_traceability` → exit 0. It could not run `check_import_boundaries` or `ruff` (environment-denied) and labelled them `UNVERIFIED`. It re-derived the counts by query: 37 nodes, 58 `lreq` decorators, 37 appended entries, append-only test history. |
| Round-1 Minors | (1) `age_days_exact`/`stratum_is_usable` annotate `float`/`int` while the module classifies defensively; (2) index literals and rating bounds in the tests are prose-derived rather than taken from the `models` constants. Neither affects a gate bullet. |
| Lead `check_import_boundaries` / `ruff` | Re-run by the lead → exit 0 ("Import boundaries valid for metrics.py, scoring.py"); `ruff check` → "All checks passed!"; `ruff format --check` → "1 file already formatted". Closes the reviewer's UNVERIFIED items. |
| Lead Minor-1 fix attempt | The lead changed `is_within_recent_window(age_days_exact: float)` to `object` and added a docstring sentence; the re-review returned `VERDICT: FAIL` with one **Major**: the signature diverged from frozen plan §5.3 and the docstring claimed a wrong-typed value yields `False` while `math.isfinite` is unguarded and raises `TypeError`. The lead reverted the change by exact inverse edit (not `git checkout`), restoring the committed `3877d5e` state; `git status --short` → no output. No plan or interface amendment was made. |

### Review (step 7) — round 2

`spec-reviewer` re-review of the reverted tree → **`VERDICT: PASS`**, no Blocker, no Major.
It confirmed `git status --short` empty, `metrics.py` at `3877d5e`, the plan §5.3 signature restored,
all six gate bullets with file:line evidence, and re-derived 37 nodes / 58 decorators / 37 entries by
query. Its two Minors are the same as round 1 (below). `LREQ-TST-*` markers: 0 in the 7A block.
One fix round spent in total (the reverted annotation change); no review-fix commit was needed
because the reverted edit was never committed.

**Minors carried forward (do not affect the verdict, no fix round):**
1. `src/niche_scout/metrics.py` — public `age_days_exact` (function) and `stratum_is_usable` annotate
   `float`/`int` while product-level values elsewhere are classified defensively; a wrong-typed
   `age_days_exact` to `is_within_recent_window` raises `TypeError` and is a caller-contract breach not
   listed in plan §5.0. Honest typing; a candidate plan note for a later pass.
2. Chunk 7A test constants for the index literals and rating bounds are prose-derived rather than
   computed from the `models` constants, so they would not track a future SRS §14 config change.

### Gate — Chunk 7A

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3
Chunk 7A (Gate section, lines 795–802), on commit `4bbec8a` (working tree clean at
verification).

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. All primitives are pure and receive `scoring_cutoff_utc` explicitly | PASS | `python -m niche_scout.tools.check_import_boundaries` → exit 0, "Import boundaries valid for metrics.py, scoring.py". AST import set of `src/niche_scout/metrics.py` (lead query): `['__future__', 'math', 'dataclasses', 'datetime', 'models', 'validation']` — no I/O, network, `sqlite3`, `json`, or `scoring` import. Every date/age/index/quality function takes `scoring_cutoff_utc` as a keyword-only, defaultless parameter (`metrics.py:360–364`, `:395–402`, `:541–558`) validated as aware UTC by `_require_utc_cutoff` (`metrics.py:194–205`). `test_metric_primitives_are_pure_no_forbidden_imports_or_clock` (LREQ-ARCH-010/020) passes and calls `check_module`/`clock_violations`. |
| 2. No metric reads the current time | PASS | `ruff`-clean file; the purity node's `clock_violations(tree)` is empty; lead grep of `src/niche_scout/metrics.py` for `datetime.now`/`utcnow`/`today`/`time.time` → 0 occurrences. Dates are compared only against the explicit `scoring_cutoff_utc`; offset conversion uses `astimezone(timezone.utc)` on a supplied value, not a clock. |
| 3. Exact fractional age is used | PASS | `metrics.py:389` and `:461`: `(scoring_cutoff_utc - published_utc).total_seconds() / 86400.0` — no floor, no rounding. Tests `test_age_days_exact_uses_fractional_days` (`DATE_HALF_DAY` → `0.5`, `DATE_29D_1H` → `29.958333333333332`) and `test_page_view_index_uses_seven_over_age_days` assert the fractional values within `1e-9`. |
| 4. Zero is distinguished from null, invalid, and unavailable | PASS | Explicit `0` views → available index `0.0` (`test_page_view_index_zero_views_is_usable_zero`); `DATE_AT_CUTOFF` → available age `0.0`, not future (`test_age_days_exact_at_cutoff_is_valid_zero_not_future`); `None` → a distinct reason (`test_page_view_index_missing_views_is_unavailable_not_zero`, `test_age_days_exact_naive_and_null_are_distinct_reasons`). The four states are separately asserted in `test_metric_primitives_classify_invalid_values_and_never_convert_to_zero`. |
| 5. Invalid values are excluded rather than converted to zero | PASS | Every failure path returns `MetricValue(value=None, unavailable_reason=...)` (`metrics.py:387, :391, :454, :458, :463, :476`) or `MetricEligibility(eligible=False, ...)`; the new tests assert, for each wrong-typed/negative/non-finite/invalid-range vector, `value is None` **and** `!= 0.0` (never a zero substitute). Lead grep of `metrics.py` for `or 0`, `.get(`, `fillna(` → 0 occurrences; no default-0 metric parameter. |
| 6. Structural malformed-shape/type/alias checks remain Chunk 1's; this chunk owns the semantic decision | PASS | `metrics.py` contains no shape/alias code; state eligibility delegates to Chunk 1's `annotate_state_eligibility` (`metrics.py:259–272`; `validation.py:1631–1668`, case-insensitive `casefold() == "published"`), and `METRIC_REASON_MALFORMED` is retained but never produced by this function set (`metrics.py:84`, tuple `:100–116`). Value-level `wrong_type` is this chunk's semantic decision per dependency-map `:211`/`:214` and LREQ-MET-010. `test_metric_primitives_do_not_reclassify_structural_or_pageview_types` and `test_metric_reason_vocabulary_is_closed_and_malformed_is_unproduced` cover both halves. |

Supporting evidence: `python -m pytest -q` → **253 passed, 0 failed**;
`python -m pytest tests/test_validation.py -q` → **59 passed** (22 pre-existing + 37 new);
`python -m niche_scout.tools.validate_traceability` → exit 0 (7 Chunk 0 requirements,
207 matrix nodes, 89 defined LREQ IDs); `python -m ruff check src/niche_scout/metrics.py`
→ "All checks passed!"; `python -m ruff format --check src/niche_scout/metrics.py`
→ "1 file already formatted".

**GATE: PASSED**

### Interface produced

`Documents/interfaces/chunk-7A.md` (Status: VERIFIED) created from the frozen plan §5.

### Open items carried forward (not gate failures)

- Reviewer Minors 1–2 (public `age_days_exact`/`stratum_is_usable` annotations vs the
  module's defensive classification; prose-derived constants in some 7A test expectations).
- `METRIC_REASON_MALFORMED` is retained in the closed vocabulary but unproduced by this
  function set (Chunk 1 owns shape classification).
- The reason-string **spelling** is a `RECOMMENDATION (not SRS-backed)`; the outcome
  categories are SRS/mapped requirements.
- `tests/test_validation.py` now holds both the Chunk 1 structural section and the Chunk 7A
  metric section; it exceeds the ~800–1000-line review trigger. Proposed split boundary
  (plan §9.1, human decision): Chunk 1 `LREQ-EXT-*`/structural vs Chunk 7A
  `LREQ-MET-*`/`LREQ-GQL-06x` clusters, never a mechanical cut, and the split must not
  rename or duplicate a pytest node ID.
- `tests/AGENTS.md` still describes `tests/traceability.json` as `LREQ-*`-keyed while the
  file is node-keyed (Chunk 13 document-consistency pass).
- The repo-wide pre-existing `ruff` debt in `tests/test_validation.py` (33 E501s, all present
  at HEAD) is unchanged and out of this chunk's file scope.
- Chunk 7B consumes these primitives; `LREQ-MET-030/040/080/090` and
  `LREQ-GQL-060/GQL-070` reach their primary/completion owner only once 7B and the
  downstream chunks land.

### Plan correction made by the lead (not a test edit)

The frozen plan §9.2 state-fixture bullet said mixed-case `"Published"` is
`state_unknown` ("case-sensitive exact match"), contradicting the frozen Chunk 1
contract it cites: `src/niche_scout/validation.py:1631–1647` documents and
implements `normalized.casefold() == "published"` (read). The fixture the test
author already wrote (`STATE_MIXED_CASE_PUBLISHED`, with a comment that it is
asserted against `annotate_state_eligibility`) follows the contract. Lead corrected
the plan bullet in place with a dated note; `validation.py` is untouched. This was a
plan-document defect, so no `DISPUTE` against a test is raised.
