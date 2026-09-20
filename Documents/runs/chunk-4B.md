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
