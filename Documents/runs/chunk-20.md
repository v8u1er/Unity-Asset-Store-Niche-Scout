# Chunk 20 — run log

Labeled post-completion remediation (Chunks 14–19 pattern): no
`requirements-dependency-map.md` §3/§4 gate row, no new interface file, no
downstream chunk. Scope is the diagnosis in the dispatch brief of 2026-09-25
(`usable_quality_sample_count` persistence inconsistency), read-only verified
before this chunk started.

Branch: `chunk-20` (created from `main` at `20514d9 chunk-19: gate passed`).
Routing: `test-author` first, then `impl-deep` (metrics semantics on a frozen
7B surface), then `spec-reviewer`. No report-rendering subpart: the report already
prints the persisted column (`report.py:431`), so no `impl-fast` stage was needed
and the plan's file list stayed at two files.

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
| 1 | Plan | DONE | `chunk-planner`; plan frozen at `Documents/plans/chunk-20-usable-quality-count-fabricated-zero-remediation.md` (commit `042e8ff`). Two runs were needed (the first exhausted steps after verification; the second authored the plan). No open questions; plan §12 = none. |
| 2 | Tests first | DONE | `test-author` (commit `1d7961c`). `python -m pytest -q tests/test_metrics.py` → **2 failed, 39 passed**: `test_quality_raw_zero_visibility_denominator_is_null` (`assert 0 == 5`, line 601) and `test_quality_raw_null_below_required_coverage` (`assert 0 == 5`, line 680) — missing-implementation-value failures, not syntax or collection errors. Only `tests/test_metrics.py` changed (+50); `tests/traceability.json` unchanged. |
| 3 | Implement | DONE | `impl-deep` (commit `191601f`). `metrics.py` +8/-1: the two keyword arguments at the `INSUFFICIENT_COVERAGE` and `ZERO_DENOMINATOR` returns plus the §4.3 docstring sentence. |
| 4 | Verify (lead) | DONE | See "Gate evidence" below. Lead re-ran every command; all pass. |
| 5 | Review | DONE | `spec-reviewer`: **VERDICT: PASS**, no Blocker or Major; three Minors recorded in "Review findings". |
| 6 | Gate | DONE | All six plan §8 DoD bullets have direct evidence below. **GATE: PASSED.** |

## Gate evidence (plan §8)

- **DoD-1 (offline suite).** `python -m pytest -q` → **658 passed, 0 failed, 0
  skipped, in 24.98s** (lead-run, verbatim count). Scoped:
  `python -m pytest -q tests/test_metrics.py` → **41 passed**.
- **DoD-2 (validators).** All exit 0, verbatim:
  `validate_traceability` → "Traceability valid: 89 required/defined LREQ IDs
  mapped, 639 matrix nodes, 0 unmarked analytical tests outside exemption (3
  exempted non-analytical nodes)";
  `check_import_boundaries` → "Import boundaries valid for metrics.py, scoring.py";
  `check_scope_prohibitions` → "Scope prohibitions valid: no retired token found
  … (6 tokens checked)";
  `check_secrets` → "Secret check valid: no literal credential found under src,
  tests, config, pyproject.toml; .gitignore ignores .env and no tracked .env
  exists".
- **DoD-3 (lint/format).** `ruff check src/niche_scout/metrics.py` → "All checks
  passed!"; `ruff format --check` on the two changed files → "2 files already
  formatted". Repo-wide ruff reports 241 pre-existing errors and 17
  would-reformat files, all byte-identical to `main` and none of them the two
  changed files (reviewer's exact statement).
- **DoD-4 (traceability reconciliation).** `git diff --stat
  main...chunk-20 -- tests/traceability.json` → **empty**. `git diff --name-only
  main...chunk-20 -- src tests` → exactly `src/niche_scout/metrics.py` and
  `tests/test_metrics.py`. No key added, changed, or removed.
- **DoD-5 (prohibitions).** `git diff --stat main...chunk-20` → 4 files: the
  plan (+545), this run log (+71), `metrics.py` (+8/-1), `tests/test_metrics.py`
  (+50). No import, purity, clock, dependency, config knob, persisted field, or
  node-ID change. No live network.

### Real-data proof (lead, beyond the suite)

Re-running the read-only probe against the operator's persisted run with the
fixed code: the 7B count is now **17 / 0 / 6 / 20 / 10 / 8 / 9 / 16** — exactly
the per-stratum `Σ u_quality_h` over the `usable` strata and exactly what 6B
finalized, so §5.5 check B can no longer fire on this shape and Chunk 10's
overwrite now writes the true value. A differently-shaped probe built fresh
typed `CategoryMetricInput`s (not the test fixtures) and returned:
`eligible_set_too_small: 0 0`; `no_usable_stratum: 0 0`;
`insufficient_coverage: 5 25`, coverage `0.25`; `zero_denominator: 5 25`,
coverage `1.0`. Null and zero stay distinct.

## Review findings (spec-reviewer, VERDICT: PASS)

- **Minor (record-only).** The stage table and DoD-1 evidence were pending at
  review time; this section and "Gate evidence" resolve it.
- **Minor (optional defensive pin).** No count assertion pins the
  `ZERO_POPULATION` and `PAGE_VIEW_SEMANTICS_CONTRADICTED` paths at `0`/`0`. The
  plan explicitly excludes them (pre-loop / unreachable); the lead's fresh-input
  probe covers `ZERO_POPULATION` semantics indirectly. Not a violation; no loop.
- **Minor (recorded risk).** The `min_age_days_for_rate` coupling
  (`metrics.py:620-626` vs `:1013-1017`) and the analogous
  `min_usable_samples_per_stratum` config-vs-constant split (`pipeline.py:3412`
  vs `:2018/:2025/:2033`) can diverge under non-default config and would flag
  check B. Same item as plan §11.3; still a non-goal, still open.

## Deviations

- `Documents/plans/chunk-19-...md` §12.2 explicitly records
  `tests/AGENTS.md` traceability orientation as out of scope. The chunk-20 plan
  must not touch it.
- The latent `min_age_days_for_rate` coupling in
  `quality_observation_eligibility` (`metrics.py:620-626`) is recorded as a
  non-goal unless the human re-opens it.
- No live run is required for this chunk (the defect is offline-verifiable); the
  DoD is offline plus an optional operator re-render.
