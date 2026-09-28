# Chunk 25 — run log (D2 sampling support-rule re-baseline)

Started 2026-09-28. Branch `chunk-25` off `main` at `51f55fb`
(`docs(agents): update source of truth to SRS-lean-v2`).

Remediation/follow-on chunk: no dependency-map §3/§4 row (chunk-14/24 precedent).
Prerequisite = chunk-24, whose run log ends `GATE: PASSED`
(`Documents/runs/chunk-24.md:299`). Chunk-25 is the D2 half declared out of scope by
chunk-24 (`Documents/plans/chunk-24-systematic-strata.md` §1.3;
`Documents/interfaces/chunk-24.md` §14.4).

## Scope (operator-fixed; do not re-open)

- Lower `MIN_USABLE_SAMPLES_PER_STRATUM` default 5 → 1 (`src/niche_scout/models.py`),
  mirrored in `config/default.toml` and the SRS §14 row.
- Re-baseline every coverage/evidence/rankability output and golden vector that
  depends on per-stratum usability: the `usable:<min>` eligibility token
  (`pipeline._component_eligibility_rule`), `u_*_h`, the three
  `*_stratum_eligibility_coverage` values, `usable_status`, `usable_*_sample_count`,
  evidence grades, and rankability status.
- Update SRS text (`Documents/SRS-lean-v2.md` only) for the changed default and its
  consequences.

Out of scope: the systematic partition (chunk-24), all formulas, weights,
`QUALITY_MIN_RATING_COUNT`, `SAMPLE_STRATA`/`SAMPLE_PER_STRATUM`, discovery.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at start (`git status` → nothing to commit, `## main`) |
| HEAD | `51f55fb` |
| Prior gate | Chunk 24 `GATE: PASSED` (`Documents/runs/chunk-24.md:299`) |
| SRS live file | `Documents/SRS-lean-v2.md` present; `Documents/SRS-lean.md` absent |
| Validator SRS path | `validate_traceability.py:34` → `SRS-lean-v2.md` (live; pointer repair already landed in `91a426d`) |
| Branch | `chunk-25` created |
| Routing (lead-chosen; analytical) | `chunk-planner` → `test-author` (tests-first) → `impl-deep` → `spec-reviewer` → lead gate |

## Operator answers (2026-09-28) — "go with the recommendation"

- **Q1 — fixture default:** `tests/fixtures/config_fixtures.py` `DEFAULT_TOML_BODY`/`VALUES`
  mirror the shipped default (5 → 1); the scenario end-to-end/pipeline re-baseline is in
  scope.
- **Q2 — version:** no `SAMPLING_RULE_VERSION` bump. `MIN_USABLE_SAMPLES_PER_STRATUM` is a
  configurable policy default, not a §5.1 sampling-rule trigger; only usability-derived
  outputs change.

## Lead-grounded inputs (read/counted from `runtime/niche_scout.sqlite3`, not propagated)

- Latest run `run-2026-09-28T05:59:50.085042+00:00`; `sampling_rule_version=1.0.0`;
  `config_snapshot_json` has `min_usable_samples_per_stratum=1`,
  `quality_min_rating_count=3`.
- Quality usability at floor 1: 53/96 strata usable, 43 unavailable
  (`usable_status` {usable: 53, unavailable: 43}).
- `quality_stratum_eligibility_coverage >= 0.50`: **13/24 at floor 1 vs 2/24 at floor 5**;
  16 categories strictly worse at floor 5 (recomputed from persisted `N_h`/`u_quality_h`).
- Persisted floor-1 outputs: `evidence_grade` {insufficient 11, weak 11, moderate 2};
  `rankability_status` {not_rankable 11, provisional 11, rankable 2};
  `eligibility_rule = demand=usable:1;recent=usable:1;quality=usable:1`.
- Task brief's "~11/24" and `[18,1,0,0]` do not match this DB; the counts above supersede
  them for planning (deviation noted, not silently reconciled).

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | git clean; branch `chunk-25`; this log |
| Plan — `chunk-planner` | DRAFT (questions answered) | `ses_f17de8754ffeVNUCxM3nsgBtje` wrote `Documents/plans/chunk-25-min-usable-samples.md` with 2 questions; operator answered "go with the recommendation" |
| Tests — `test-author` | PENDING | — |
| Implement — `impl-deep` | PENDING | — |
| Review — `spec-reviewer` | PENDING | — |
| Gate (lead) | PENDING | — |
