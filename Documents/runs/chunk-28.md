# Chunk 28 — run log (D1 — page-view semantics; the index formula is wrong)

Started 2026-09-29. Remediation/follow-on chunk: **no dependency-map §3/§4 row**
(chunk-14/24/25/26/27 precedent). Registration = plan + run log + branch.

Scope (operator-fixed): **D1 only** — the Unity `product_page_views` field is a
trailing-7-day (weekly) view count (operator-confirmed 2026-09-29), not a cumulative
lifetime counter. `metrics.age_normalized_page_view_index` currently computes
`product_page_views * 7 / age_days_exact` (LREQ-MET-040). Formula becomes
`= product_page_views`; `MIN_AGE_DAYS_FOR_RATE = 30` stays an eligibility floor only.
New token `PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY`; run-level status seeded
from a module constant (no runtime detector). `ENDPOINT_CONTRACT_VERSION` 1.0.0 → 1.1.0;
`SCHEMA_VERSION` 1.2.0 → 1.3.0 (enum CHECK allow-list); report caveats reworded.

Governing defect plan: `Documents/plans/chunk-26-analytical-defect-remediation.md`
§13 (operator ruling, best-assumption formula, SRS edits D1-S1..D1-S7, versioning) and
§14.1 (operator-adopted OQ-11..OQ-14). This session produces its OWN plan:
`Documents/plans/chunk-28-page-view-semantics-remediation.md`.

## Preflight

| Check | Result |
|---|---|
| Prior gate | chunk-27 `GATE: PASSED` — `Documents/runs/chunk-27.md:127`; merged to `main` at `db47a5c` (log line 116) |
| Working tree | clean — `git status --porcelain --branch` → `## main` only |
| Branch | `git switch -c chunk-28` → "Switched to a new branch 'chunk-28'" |
| Routing (plan) | `chunk-planner` → `test-author` (tests first, D1 analytical) → `impl-deep` → `spec-reviewer` → lead gate |
| Baseline | `python -m pytest -q` → **701 passed in 23.66s** (clean tree) |

### Pre-change snapshot (read-only)

`runtime/niche_scout.sqlite3` run `run-2026-09-29T05:33:21.664034+00:00` is the
pre-change audit snapshot. Page-view semantics status = `unvalidated`; no writer of
`validated_cumulative` / `contradicted` (chunk-26 plan §3.1).

## Stage log

| Stage | Status | Evidence |
|---|---|---|
| Preflight (lead) | DONE | branch `chunk-28`; clean tree; chunk-27 GATE PASSED; baseline 701 passed. |
| Plan — `chunk-planner` | DONE (FROZEN) | First dispatch (`ses_f11b0d1e2ffeYZhS9RAJYQUiGf`) hit its step cap during read-only reconnaissance (INCOMPLETE, no file). Re-dispatched (`ses_f11a54655ffeu7XLaPgJjjcX5m`) with the reconnaissance in the brief; wrote `Documents/plans/chunk-28-page-view-semantics-remediation.md` (601 lines, §1–§14, `Status: FROZEN`). Lead-verified by read: allowlist §6 exact, six gate bullets verbatim (§10), D1-S1…D1-S7 checkpoint (§13), the two load-bearing decisions (§5.3 guard, §8.2 old-DB), two open questions (§12). |

| Tests — `test-author` | DONE | Dispatches `ses_f1198068affeA2EGpVmdUBiLNG` (step cap, recon only, no file) then `ses_f118c598cffeFLAW5hQttiSjsR` (provider reset, then resumed). Files (tests only): `date_eligibility_fixtures.py`, `identity_preflight_vectors.py`, `metric_estimator_fixtures.py`, `report_fixtures.py`, `sampling_persistence_fixtures.py`, `test_validation.py`, `test_contracts.py`, `test_collector.py`, `test_database.py`, `test_pipeline.py`, `test_report.py`, `test_metrics.py`, `traceability.json`. Lead-reproduced below. |

### Tests stage — lead-reproduced (real output)

| Command | Real result |
|---|---|
| `git status --porcelain` | exactly the 13 `tests/**` paths above; no `src/`, `Documents/`, or other file |
| `python -m pytest tests -q --collect-only` | **711 tests collected** in 0.67s — no syntax/collection errors |
| `python -m pytest -q` | **25 failed, 686 passed in 25.20s** — every failure is a missing-implementation failure: wrong index values (`2.333…` vs `10.0`; `0.5` vs `5.0`), absent enum member (`Extra items in the right set: 'validated_windowed_weekly'` at `test_collector.py:3116`), wrong `SCHEMA_VERSION`/`ENDPOINT_CONTRACT_VERSION`, wrong report text, absent seed/non-clobber token |
| `python -m niche_scout.tools.validate_traceability` | exit 0 — **89 LREQ IDs, 690 matrix nodes**, 0 unmarked analytical outside exemption (3 exempted) |
| unchanged nodes | full suite delta: 701 baseline → 711 collected (10 new nodes); the 25 failures are the intended pre-implementation set, no collateral collection or syntax failure |

The 25 failures are the accepted missing-implementation set (formula, enum token, both version bumps, report caveats, seed + non-clobber). The broad D/Q/rankability captured-run re-baseline is deferred to implementation (chunk-24/25 precedent); the test-author enumerated the affected nodes/fixtures in its report and left their numeric expectations untouched except hand-derivable vectors.

| Implement — `impl-deep` | DONE | Dispatch `ses_f0f3beda5ffehSxcDqmmtsy1nZ` saw a shell denial and stopped correctly. Re-dispatched `ses_f0f39b21dffePKX5gcACzsZCph` (intermittent tool denial). Source changes landed (`models.py`, `metrics.py`, `pipeline.py`, `database.py`, `report.py`) plus numeric re-baseline in `tests/fixtures/metric_estimator_fixtures.py` and `tests/test_metrics.py`. One full-suite failure was a **pre-existing test-isolation defect**: `tests/test_contracts.py::test_repository_protocol_and_schema_specification` deletes/reimports `niche_scout.database`, rebinding the parent-package attribute; the lead fixed it by restoring both `sys.modules` and the `niche_scout.database` package attribute. Lead-reproduced below. |

| Review — `spec-reviewer` | FAIL round 1 (operator checkpoint only) | `ses_f0f14d396ffeDxMa1aeef5Ywgh`. Independent verdict: **FAIL**, 1 Blocker (the operator-only SRS D1-S1…D1-S7 checkpoint, plan §10 bullet 6), **0 Major**, 3 Minor, 2 Nit. The reviewer explicitly states the implementation/tests conform to the plan and the chunk-26 §13/§14.1 ruling, 711 passed, four validators green, no new source lint; FAIL is driven solely by the un-applied SRS edit. Fix round 1 applied the 3 Minors + 1 Nit (see below); the Blocker is the human checkpoint and cannot be cleared by any agent. |

### Review round 1 — findings and disposition

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | **Blocker** | `Documents/SRS-lean-v2.md` still pre-edit at `:133`, `:675-680`, `:741-750`, `:1163-1170`, `:1385`, `:1442` — D1-S1…D1-S7 not applied (plan §10 bullet 6 / §13 / chunk-26 §14.6) | **Open — operator-only.** No agent may edit the SRS. Gate bullet 6 is FAILED until the operator applies the edits with diff/sha256 evidence. |
| 2 | Minor | `models.py:135-137` — `PAGE_VIEW_SEMANTICS_CONTRACT` placed after the enum, not "near the policy versions" (plan §5.1) | Accepted as a recorded deviation: the constant references `PageViewSemanticsStatus`, so it must follow the enum in module order. Functionally correct. |
| 3 | Minor | `tests/fixtures/metric_estimator_fixtures.py:368` comment says "the index IS the daily page-view count" | **Fixed** — now "weekly page-view count". |
| 4 | Minor | `tests/test_validation.py::test_page_view_index_never_divides_by_zero_at_threshold` stale name (no division remains; plan §9.3 encouraged a rename) | **Fixed** — renamed to `test_page_view_index_min_age_floor_validates_and_enforces_threshold`; `tests/traceability.json` key swapped to the same LREQ value, no dangling key. |
| 5 | Nit | `tests/test_collector.py:1985` dead `else "1.0.0"` fallback | **Fixed** — removed; direct equality assertion retained. |
| 6 | Nit | `pipeline.py:537` docstring example endpoint signature `#1.0.0` | **Fixed** — updated to `#1.1.0`. |

Review round 1 fix scope: `tests/fixtures/metric_estimator_fixtures.py`, `tests/test_validation.py`,
`tests/test_collector.py`, `tests/traceability.json`, `src/niche_scout/pipeline.py` (docstring only).
After the fixes: `pytest` **711 passed**; `validate_traceability` exit 0 (89 IDs, 690 nodes);
`ruff check` clean on the changed files (the pre-existing `database.py`/`test_contracts.py` E501 are unchanged).

### Implementation stage — lead-reproduced (step 6, real output)

Changed source: `models.py` (enum + `PAGE_VIEW_SEMANTICS_CONTRACT` + `ENDPOINT_CONTRACT_VERSION`→"1.1.0"),
`metrics.py` (step 13 `float(product_page_views)` + docstring), `pipeline.py` (import, non-clobber
tuple, seed), `database.py` (`SCHEMA_VERSION`→"1.3.0"), `report.py` (two caveats). Changed tests:
`tests/fixtures/metric_estimator_fixtures.py`, `tests/test_metrics.py`, `tests/test_contracts.py`
(isolation fix + the 1.3.0 docstring/node from the tests stage).

| Command | Real result |
|---|---|
| `python -m pytest -q -p no:cacheprovider` | **711 passed in 28.83s** (was 25 failed / 686 passed at the tests stage) |
| `python -m niche_scout.tools.validate_traceability` | exit 0 — 89 LREQ IDs, **690 matrix nodes**, 0 unmarked analytical outside exemption (3 exempted) |
| `python -m niche_scout.tools.check_import_boundaries` | exit 0 — "Import boundaries valid for metrics.py, scoring.py" |
| `python -m niche_scout.tools.check_scope_prohibitions` | exit 0 — 6 tokens checked, none retired |
| `python -m niche_scout.tools.check_secrets` | exit 0 — no literal credential under src/tests/config/pyproject.toml |
| `python -m ruff check` (models, metrics, pipeline, report, metric_estimator_fixtures, test_metrics) | `All checks passed!` |
| `python -m ruff check database.py` / `test_contracts.py` | **6 / 11 E501** — byte-identical to HEAD (re-run via `git show HEAD:<file> | ruff check --stdin-filename`), so **no new lint** |
| `python -m ruff format --check` (models/metrics/report) | 3 files already formatted; `pipeline.py` would reformat — the deviation is **pre-existing** (HEAD pipeline.py piped to `ruff format --check --stdin-filename` exits 1 at `:3413`; chunk-28's pipeline hunks are `+86`, `+1004`, `+3341`, none at the deviation site) |
| `python -m pytest -q` after the isolation fix | 711 passed (same count) |

**Captured measurement (offline run):** the index is now the weekly count. Move measured:
`DEMAND_UNEQUAL_STRATA` → `demand_per_asset_raw 97.5`, `demand_median_raw 40.0`;
`DEMAND_MEDIAN_EXACT_HALF` → `55.0`; `DEMAND_INELIGIBLE_EXCLUDED` → `30.0`;
`WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR` → `40.0`; `quality_raw` unchanged at `1.0`
(index-scale-invariant ratio). The `acceptance_fixtures.py` / `scoring_evidence_fixtures.py` /
`test_end_to_end.py` D/Q/rankability goldens were **not** re-baselined and the suite is green,
so they do not move (verified by the full-suite pass, not assumed).

**Pre-change live-DB snapshot (lead, read-only `file:runtime/niche_scout.sqlite3?mode=ro`):**
`schema_metadata = [('schema_version','1.2.0'), ('applied_at_utc','2026-09-29T05:33:21.661518+00:00')]`;
latest `runs` row `('run-2026-09-29T05:33:21.664034+00:00', 'unvalidated', '1.0.0')`. So the operator's
existing audit DB is 1.2.0 and will raise `SchemaVersionError` on default open under 1.3.0 — handled by
re-running into a fresh DB or `initialize_schema(check_version=False)` (plan §8.2, tested by
`test_open_older_schema_raises_unless_check_version_false`).

### Plan stage notes (lead-read)

- The plan is freezeable; the two §12 open questions are recorded, not resolved: (1) LREQ
  owner of `ENDPOINT_CONTRACT_VERSION`/`SCHEMA_VERSION` (working assumption
  `LREQ-GQL-010` + `LREQ-ARCH-030`); (2) exact `report.py` phrase must track the operator's
  applied D1-S4/D1-S5 SRS text. Neither changes an implementation file's contract.
- **Load-bearing, verified by lead read:** `database.py:101` declares
  `page_view_semantics_status TEXT NOT NULL` with **no CHECK**; validation is Python-side
  `_validate_enum` (`:571-579`) over `_ENUM_COLUMNS` (`:397-401`, built from the enum), so the
  1.3.0 bump is metadata-only — the plan's §5.4/§8.2 claim is correct.
- **Minor (lead):** plan §9.4 items 3 and 9 name `tests/test_models.py`, which does not exist
  (no such file in `tests/`). The enum/constant contract tests belong in `tests/test_contracts.py`
  (its `:84` enum-set dict is the existing home). The plan hedges "(or the file owning enum
  contract tests)"; the test-author will place them in `tests/test_contracts.py`.
- The plan's D/Q/rankability re-baseline list is explicitly a **minimum**, not a completeness
  claim (§9.3 "to be discovered at implementation"); the exact re-baseline values come from a
  captured run at implementation (chunk-24/25 precedent).
