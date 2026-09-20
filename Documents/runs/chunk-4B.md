# Chunk 4B — run log (Sample persistence, overlap, and sampling summaries)

Started 2026-09-20. Branch: `chunk-4B` (created from `chunk-4A`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status --short` → no output) |
| Branch | created `chunk-4B` from `chunk-4A` (HEAD at 4A gate commit) |
| Prerequisite Chunk 4A | `Documents/runs/chunk-4A.md` ends `GATE: PASSED` (line 184); 4A branch checked out |
| Prerequisite Chunk 2 | `Documents/interfaces/chunk-02.md` → `Status: VERIFIED` |
| Supporting/completion Chunk 6B | Not a start prerequisite; final usable-count finalization is 6B's |
| Frozen plan | none yet — planner dispatch required |
| Parallel work | Operator will run Chunk 7A in a separate agent. 4B expected files (sampling persistence/`database`-side materialization, `tests/test_sampling_persistence.py`) do not overlap 7A's (`validation.py`, `metrics.py`, `tests/test_validation.py`); the only shared artifact is `tests/traceability.json` (append-only per chunk). |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan | BLOCKED | `chunk-planner` wrote `Documents/plans/chunk-4B-sample-persistence-overlap-and-sampling-summaries.md` with `Status: DRAFT` and 9 open questions (§12). Per chunk-lead step 3 and project-rules "Scope discipline", execution halts and the questions are surfaced to the user verbatim. No test-author or implementer dispatch has occurred. The planner's shell tool was denied globally, so its counts are read-only and unverified by tool; lead spot-checked the blocking facts (see below). |
| Plan | FROZEN | Human ruled all nine §12 questions 2026-09-20 (`Q-1 (a)`, `Q-1(b) do not write`, `Q-2 (a)`, `Q-3 (a)`, `Q-4 4B owns the vocabulary`, `Q-5 False`, `Q-6 create the interface file`, `Q-7 unrounded`, `Q-8 database.py`). Lead created `Documents/interfaces/chunk-4A.md` (Q-6 action) and committed `3866ba0`. Planner applied the rulings in place; the plan was left DRAFT over §12 item 10 (Q-2 create-if-absent path had no value for `NOT NULL category_scores.discovery_status`). Lead ruling 2026-09-20: the create path is a defensive fallback that SHALL NOT invent `discovery_status` — `persist_run_sampling` forwards the value read from `get_category_scores`, and the fallback raises `InvalidRecordValueError`; the Q-2 sampling-phase-only rule governs the update path. Plan set `Status: FROZEN`. Commit `80959f3`. Routing: test-author first, then impl-deep. |
| Tests | DONE | `test-author` wrote `tests/test_sampling_persistence.py` (881 lines), `tests/fixtures/sampling_persistence_fixtures.py` (O1–O10), modified `tests/fixtures/__init__.py`, and appended 31 `["LREQ-SMP-080"]` entries to `tests/traceability.json`. The author's shell was denied, so all 31 nodes failed as required on the first dispatch (missing `sampling.compute_overlap`, `database.persist_run_sampling`/`verify_persisted_sampling`/`SamplingPersistenceReport`, `SqliteRepository.upsert_sampling_summary`). Lead fixed lint by hand + `ruff --fix`/`ruff format`. **Lead verification (step 4):** `pytest tests/test_sampling_persistence.py -q` → 31 failed (all missing-implementation `AttributeError`), no syntax or collection errors; `--collect-only` → 31 collected; full suite → 31 failed, 185 passed; `validate_traceability` → exit 0, 207 matrix nodes, 89 LREQ IDs; `ruff check` / `ruff format --check` on the three files → clean. Commit `147de81`. |
| Implementation | INCOMPLETE → recovered | First `impl-deep` dispatch ran out of steps **and destroyed its own work**: it ran `git stash` (denied, then apparently executed) and copied a HEAD extraction over `src/niche_scout/database.py`, losing the whole 4B database implementation. Lead recovery: no stash entry survives (`refs/stash` absent; the full `--all` reflog contains no `stash` entry — read via `git log -g --oneline --all --date=iso`), and `database.py` was byte-identical to HEAD (`git status --porcelain=v2` empty; only `sampling.py` differed). Lead snapshotted the surviving `sampling.py` work first (`44dc8d6`), then re-dispatched `impl-deep` with an absolute no-destructive-git-command rule; it re-applied the full additive surface to `database.py` (+502 lines) and left `sampling.py` untouched. Commit `f8000d1`. |
| Verification | PARTIAL | See "Lead verification (step 6)" below. One test fails on a genuine fixture/SRS conflict, recorded as an open DISPUTE; everything else is green. |

### Lead verification (step 6), 2026-09-20

- `python -m pytest tests -q` → **1 failed, 215 passed**. The single failure is
  `tests/test_sampling_persistence.py::test_stratum_statistics_json_round_trips_n_h_and_boundaries`.
- `python -m pytest tests/test_sampling_persistence.py -q` → **1 failed, 30 passed**.
- `python -m pytest tests/test_sampling.py -q` → 35 passed; `python -m pytest tests/test_database.py -q` → 23 passed.
- `python -m niche_scout.tools.validate_traceability` → exit 0, 207 matrix nodes, 89 defined LREQ IDs.
- `python -m niche_scout.tools.check_import_boundaries` → exit 0 ("Import boundaries valid for metrics.py, scoring.py").
- `python -m ruff check src/niche_scout/sampling.py` → clean. `src/niche_scout/database.py` → 6 E501s, all **pre-existing at HEAD**: HEAD's long-line set is `[580, 689, 1076, 1234, 1445, 1647]` and maps 1:1 to the current `[583, 692, 1079, 1237, 1576, 1778]`; the additive 4B block introduced none. Lead counted HEAD's set by reading `git show HEAD:src/niche_scout/database.py` through Python and taking `len(line) > 88`, and the current set from `ruff check`. Not fixed (whole-file reformat is outside this chunk's file scope).
- Working tree clean at `f8000d1`.

### DISPUTE (open): `test_stratum_statistics_json_round_trips_n_h_and_boundaries`

Observed vs fixture, verbatim from the failing assertion:

```text
assert ((0, 1, 25, 25, 25), (1, 26, 50, 25, 25), (2, 51, 75, 25, 25), (3, 76, 101, 26, 25)) ==
       ((0, 1, 25, 25, 25), (1, 26, 50, 25, 25), (2, 51, 75, 25, 25), (3, 76, 101, 26, 26))
```

Lead evidence, each verified by running the live engine and reading the files:

- Live 4A on this fixture: `select_run_sample(o6_categories())` → `len(members) == 100`,
  `enriched_sample_count == 100`, `sample_fraction == 100/101`, strata
  `(0,25,25) (1,25,25) (2,25,25) (3,26,25)`, and `is_reduced False` for every stratum
  (`sampling.py:412` `selected_count=min(per_stratum_target, population_count)`).
- The frozen plan §5.3 line reads `is_reduced: True iff population_count < SAMPLE_PER_STRATUM`;
  `sampling.py:131-133` / `:374` agree, and `Documents/interfaces/chunk-4A.md` reproduces it.
- SRS §5.1 LREQ-SMP-090: "If a stratum contains fewer than 25 assets, all assets in that
  stratum SHALL be eligible for selection and the reduced count SHALL be reported." The
  `N=101` final stratum holds **26**, which is not fewer than 25, so its `selected_count`
  is 25 — the live 4A behaviour.
- The fixture's `O8_EXPECTED_STRATA_N101` entry `(3, 76, 101, 26, 26)` and
  `o6_expected_sample_fractions()`'s "the last stratum is reduced and contributes all 26"
  comment assert the opposite. `o6_expected_selected_counts()` expects 100 overall, so
  `N_h(26)` with `n_h(26)` for that stratum is arithmetically inconsistent with the total
  the same fixture asserts (25 + 25 + 25 + 26 = 101 ≠ 100); only 25 for that stratum
  reconciles them.
- 4B persists what the pure result carries (`N_h = population_count`,
  `n_h = selected_count`) and is forbidden to recompute it; the 4B test file and fixtures
  are frozen and were not edited.

Two self-consistent resolutions exist and neither is uniquely forced by the artifacts read,
so the lead did not pick one:
- **(a) Fixture is wrong, live 4A is right.** `n_h` for stratum 3 is 25 and the 26-member
  stratum is not reduced (SRS §5.1 LREQ-SMP-090; `o6_expected_selected_counts` 100 is
  consistent). Fix requires editing the frozen fixture
  (`O8_EXPECTED_STRATA_N101` → `(3, 76, 101, 26, 25)` and the
  `o6_expected_sample_fractions` comment) — a human scope ruling on
  `tests/fixtures/sampling_persistence_fixtures.py`.
- **(b) 4A is wrong, fixture is right.** The final/remainder stratum is treated as reduced
  and contributes all 26 when it holds fewer than `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`
  remaining (i.e. the remainder rule from LREQ-SMP-090 read as "remainder stratum"), giving
  `enriched_sample_count == 101`; then `o6_expected_sample_fractions()` (`100/101`) and the
  `CENSUS_*`/O9 vectors need review. This requires a Chunk 4A change and 4A's gate is
  already `PASSED`.

The 4B gate bullet "Per-category and per-stratum summaries survive a database round trip"
**does** hold: the round trip is verified against the pure `RunSamplingResult` by
`test_persisted_values_verify_against_pure_result` and by `persist_run_sampling`'s read-back.
Only the fixture's fixed `n_h` literal for the `N=101` final stratum is in dispute.

### Lead spot-checks of the blocking facts (2026-09-20)

- `src/niche_scout/models.py:475-477` — `usable_demand_sample_count`,
  `usable_recent_supply_sample_count`, `usable_quality_sample_count` are
  non-optional `int`; `:472` `unique_enrichment_count` non-optional `int`. (read)
- `src/niche_scout/database.py:476-507` — `_IMPLICIT_NOT_NULL_DEFAULTS` for
  `category_scores` fills `usable_*_sample_count` with `0` and
  `unique_enrichment_count` with `0`; the frozen DDL declares no `DEFAULT`.
  (read)
- `src/niche_scout/collector_coveo.py:2208` — Chunk 3 already calls
  `set_category_status(...)`, so a `category_scores` row with those `0`
  defaults exists **before** 4B runs. The 4B gate's "explicitly marked pending"
  therefore has no representable home for the category-level columns. (read)
- `Documents/SRS-lean.md:624-635` — `overlap_category_count` is defined
  **per category** ("this category"); §6.3 lists the same two columns on
  `sample_members` without per-member semantics. Q-3 is a genuine ambiguity.
  (read)
- `Documents/interfaces/chunk-4A.md` does **not** exist (interface dir holds
  chunk-00/01/02/03/05 only); the 4A run log records `GATE: PASSED`
  (`Documents/runs/chunk-4A.md:184`). (read)
