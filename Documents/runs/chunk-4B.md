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
