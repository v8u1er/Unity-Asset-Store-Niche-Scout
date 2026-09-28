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
| Plan — `chunk-planner` | DONE (frozen) | `ses_f17de8754ffeVNUCxM3nsgBtje`; `Documents/plans/chunk-25-min-usable-samples.md`; operator answered 2 questions "go with the recommendation". Committed `30f3ef1` (`chunk-25: plan`). |
| Tests — `test-author` | DONE | `ses_f16d8b07affe9ywZ3XxaBbWPq9` (2 turns; hit step cap once, resumed). 11 files under `tests/` + traceability entry. Lead-reproduced below. |
| Implement — `impl-deep` | PENDING | — |
| Review — `spec-reviewer` | PENDING | — |
| Gate (lead) | PENDING | — |

## Implementation stage (lead-reproduced, real output)

`impl-deep` session `ses_f16be5163ffeecFCGbod8NMImb`. Applied the two source defaults;
**did not** apply SRS S1–S5 because the `edit` tool is denied on `Documents/**`
(permission rule `{"permission":"edit","pattern":"Documents/**","action":"deny","source":"agent"}`).
That deny is the stop-and-surface chunk-24 also hit on the retired path.

| Command | Real result |
|---|---|
| `git status --porcelain` | only `M config/default.toml`, `M src/niche_scout/models.py` |
| `python -m pytest -q` | **1 failed, 687 passed in 26.38s** |
| `validate_traceability` | exit 0 — 89 IDs, 666 nodes |
| `check_import_boundaries` / `check_scope_prohibitions` / `check_secrets` | exit 0 |
| `ruff check src/niche_scout/models.py` | `All checks passed!` |

The single failure is **not** a §4.5 scenario node and **not** a source defect:
`tests/test_metrics.py::test_quality_eligible_set_too_small_is_null` asserts, at lines
657–661, that `mfx.QUALITY_ELIGIBLE_SET_TOO_SMALL` produces
`usable_sample_count == 0` / `eligible_population_count == 0`, citing "plan §4.4". The
chunk-25 plan contains **no §4.4** (its §4.4 is "New tests"); those asserts are residual
from another plan's numbering, and they contradict the chunk-25 plan's own framework —
`test_default_min_usable_is_inclusive_at_one` asserts `stratum_is_usable(1) is True`, i.e.
a 4-eligible single stratum **is** usable at the new default, so the quality counts are
`4` / `75`. `metrics.py` is correct as written (unmodified, and its docstring says counts
describe the quality-usable strata and are never nulled). Cheapest correct fix, per the
plan's §4.3 intent, is to pin that call at the former default `min_usable_samples_per_stratum=5`.

Recorded as a bounded fix round: the change is confined to `tests/`, so it is sent to
`test-author` (role boundary; the lead does not edit tests).

### SRS stage — BLOCKED (surface, do not work around)

The SRS edits S1–S5 cannot be applied from any agent session: `edit` is denied on
`Documents/**` (`source: agent`). Chunk-24 hit the same deny on `Documents/SRS-lean.md` and
the operator resolved it by directing the revision to a new file. Chunk-25 must edit the
already-live `Documents/SRS-lean-v2.md` in place, so the same deny has no equivalent
escape. Reported as a human checkpoint; no workaround attempted.

Subagent hit its step cap once mid-edit; resumed and finished. The lead reproduced every
claim rather than trusting the report.

| Command | Real result |
|---|---|
| `python -m pytest -q` | **13 failed, 675 passed in 28.74s** |
| `python -m pytest tests/test_pipeline.py tests/test_end_to_end.py -q` | 1 failed, 55 passed — the only failure is `test_acceptance_sample_fraction_distinct_from_eligibility_coverage`, the intended default-policy re-baseline |
| `python -m pytest -q --collect-only` | **688 tests collected** (no collection/syntax errors) |
| `python -m niche_scout.tools.validate_traceability` | exit 0 — 89 required/defined LREQ IDs mapped, 666 matrix nodes, 0 unmarked outside exemption (3 exempted) |

All 13 failures are expected-value/missing-implementation mismatches against the
not-yet-changed source default (`models.MIN_USABLE_SAMPLES_PER_STRATUM` still `5`,
`config/default.toml` still `5`): `assert 5 == 1` in `test_contracts.py`, `assert False is
True` at `stratum_is_usable(1)` in `test_metrics.py`/`test_validation.py`, and coverage
`0.75` vs expected `1.0` in `test_end_to_end.py`. No syntax or collection error. Oracle
condition met (chunk-lead procedure step 4).

§4.5 scenario nodes were deliberately left unchanged (values not hand-derivable): no
`test_pipeline.py` node failed, so `test_failed_category_does_not_abort_other_categories`
and `test_final_evidence_and_rankability_are_persisted_per_category` need no re-baseline —
to be re-confirmed after implementation.
