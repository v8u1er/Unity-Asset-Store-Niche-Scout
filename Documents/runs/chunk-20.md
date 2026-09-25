# Chunk 20 — run log

Labeled post-completion remediation (Chunks 14–19 pattern): no
`requirements-dependency-map.md` §3/§4 gate row, no new interface file, no
downstream chunk. Scope is the diagnosis in the dispatch brief of 2026-09-25
(`usable_quality_sample_count` persistence inconsistency), read-only verified
before this chunk started.

Branch: `chunk-20` (created from `main` at `20514d9 chunk-19: gate passed`).
Routing: `impl-deep` with `test-author` first (metrics semantics on a frozen
7B surface), then `impl-fast` for the report-rendering subpart, then
`spec-reviewer`.

## Root cause (verified read-only before planning; see the brief)

- **H1 confirmed.** `metrics.quality_raw` accumulates `usable_sample_count =
  Σ quality-eligible over quality-usable strata`, then every early-return
  `_null_result(...)` call omits the counts, resetting them to the default `0`
  (`metrics.py:1032-1046`, `1569-1593`). `metrics.py:1656` copies that `0` into
  `CategoryRawMetrics.usable_quality_sample_count`.
- **H2 refuted.** `_quality_observation_index` (`metrics.py:989-1017`) equals
  the eligibility count; recomputed coverage reproduced each persisted
  `quality_stratum_eligibility_coverage` bit-for-bit, and recomputed per-stratum
  eligibility counts equaled every persisted `u_quality_h`.
- **H3 confirmed (mechanism).** 6B `finalize_enrichment` writes the true sum
  (`pipeline.py:2029-2047`) and runs `assert_finalization_consistency`
  (`:2071`); Chunk 10 `_build_scored_rows` overwrites the column with the 7B `0`
  (`pipeline.py:3133`) and upserts at `pipeline.py:3478-3479`; no assertion runs
  after that write. The seven stderr `usable_quality_sample_count` limitation
  strings are §5.5 check B (7B `0` vs finalized 17/6/20/10/8/9/16).
- **H4 refuted.** No existing test or golden vector locks the fabricated zero on
  the `INSUFFICIENT_COVERAGE`/`ZERO_DENOMINATOR` paths.
- **Evaluator path.** The fabricated `0` is *consumed* by
  `SampleEvidenceFacts.minimum_component_sample_count`
  (`scoring.py:1269-1303` → `pipeline.py:3085`) and by
  `_build_scored_rows` → `upsert_category_scores` (`pipeline.py:3133`,
  `3478-3479`); the report prints it (`report.py:431`, observed `0`). Ranks are
  unaffected because every affected category already carries
  `QUALITY_UNAVAILABLE` in `not_rankable_reasons` (`scoring.py:936-937`).

## Scope frozen for this chunk

1. `metrics.quality_raw` returns the accumulated counts on the two null paths
   that can follow a usable-stratum accumulation: `INSUFFICIENT_COVERAGE`
   (`metrics.py:1579-1583`) and `ZERO_DENOMINATOR` (`metrics.py:1584-1588`),
   per SRS §6.5 (lines 618-620) and 7B plan §5.4 (lines 565-577).
2. Extend the existing `LREQ-MET-090` nodes' assertions to pin the count on
   those two paths (node IDs and `tests/traceability.json` entries unchanged).

## Stages

| # | Stage | Status | Notes |
|---|---|---|---|
| 0 | Preflight | DONE | Tree clean at `20514d9`; branch `chunk-20` created. |
| 1 | Plan | PENDING | `chunk-planner`, plan path `Documents/plans/chunk-20-...`. |
| 2 | Tests first | PENDING | `test-author`. |
| 3 | Implement | PENDING | `impl-deep`. |
| 4 | Verify | PENDING | pytest, traceability, import boundaries, scope, secrets, ruff. |
| 5 | Review | PENDING | `spec-reviewer`. |
| 6 | Gate | PENDING | Dispatch DoD opened in the plan. |

## Deviations

- `Documents/plans/chunk-19-...md` §12.2 explicitly records
  `tests/AGENTS.md` traceability orientation as out of scope. The chunk-20 plan
  must not touch it.
- The latent `min_age_days_for_rate` coupling in
  `quality_observation_eligibility` (`metrics.py:620-626`) is recorded as a
  non-goal unless the human re-opens it.
- No live run is required for this chunk (the defect is offline-verifiable); the
  DoD is offline plus an optional operator re-render.
