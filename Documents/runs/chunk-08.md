# Chunk 8 — run log (Normalization and primary scoring)

Started 2026-09-21. Branch: `chunk8` (worktree copy; HEAD `001af49`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → "nothing to commit, working tree clean") |
| Branch | already on `chunk8` (Agent Manager worktree branch); HEAD `001af49` |
| Prerequisite Chunk 2 | `Documents/interfaces/chunk-02.md` → `Status: VERIFIED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` |
| Prerequisite Chunk 7A | `Documents/runs/chunk-7A.md` ends `GATE: PASSED`; interface `Status: VERIFIED` |
| Prerequisite Chunk 7B | `Documents/runs/chunk-7B.md` ends `GATE: PASSED` (re-affirmed); interface `Status: VERIFIED` |
| Baseline suite | `python -m pytest -q` → **294 passed, 0 failed** |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan — first dispatch | BLOCKED | `chunk-planner` wrote the full 12-section plan (`Documents/plans/chunk-08-normalization-and-primary-scoring.md`) but returned `STATUS: BLOCKED` on §12 Q1: does a below-`MIN_REQUIRED_COMPONENT_COVERAGE` `D`/`R` receive primary composite weight? (Variant A: no threshold on the composite; Variant B: below-threshold component unavailable / no composite weight.) It also left a stale duplicate D5 bullet. |
| Plan — lead ruling (SRS-backed) | DONE | The lead read `Documents/SRS-lean.md` §7.5 (lines 835–840) and §9.1 (lines 1019–1022): both state as a SHALL that a below-threshold sample-derived component "is unavailable … and receives no composite weight". The constant is `MIN_REQUIRED_COMPONENT_COVERAGE = 0.50` (§9.1 line 1015; `src/niche_scout/models.py:52`). This is not a silent SRS gap — the SRS answers it, and frozen Chunk 7B already applies the threshold to `QualityRaw`. Ruled **Variant B**; re-dispatched the planner with the exact line citations. |
| Plan — freeze | DONE (FROZEN) | Planner applied Variant B: added `min_required_component_coverage` (default `models.MIN_REQUIRED_COMPONENT_COVERAGE`) to `demand_component`/`recent_supply_component`/`quality_component`/`compute_components`; below-threshold `D`/`R`/`Q` return `None`, `C` unaffected; deleted stale D5; §12 Q1 rewritten RESOLVED; §10 gate bullets kept verbatim; header `Status: FROZEN`. No code, tests, or interface docs written. |
| Plan commit | DONE | `ca43822` — `chunk-8: plan`. |
| Tests — test-author dispatch 1 | PARTIAL | Empty result after writing only `tests/fixtures/scoring_fixtures.py` (with a mangled `__all__` entry). No test file, `__init__` change, or traceability entries. Resumed the same session (allowed retry). |
| Tests — test-author dispatch 2 (resume) | INCOMPLETE (env) | Repaired the fixture `__all__`, wrote the 30-node `tests/test_scoring.py` (exact plan §9 names/markers), added the `scoring_fixtures` re-export, and appended 30 `tests/traceability.json` entries. Could not run `ruff` (sandbox denied every invocation). Returned `QUESTIONS`/`DISPUTE` on one plan midrank vector. |
| Tests — lead verification (step 4) | DONE | `python -m pytest tests/test_scoring.py -q` → **1 collection error**: `ImportError: cannot import name 'NormalizedValues' from 'niche_scout.scoring'` (required missing-implementation shape; no syntax error). `python -m pytest -q` → **9 collection errors**, all the same fixture→`scoring`-names `ImportError` (7B precedent: expected pre-implementation shape). `python -m niche_scout.tools.validate_traceability` → exit 0, "285 matrix nodes, 89 defined LREQ IDs" (7 pre-existing unmarked tests noted). Node count verified by query: `grep '^def test_' tests/test_scoring.py` → **30**; `grep 'tests/test_scoring.py::' tests/traceability.json` → **30**; matches plan §9. |
| Tests — lead lint fix | DONE | `python -m ruff format tests/test_scoring.py tests/fixtures/scoring_fixtures.py tests/fixtures/__init__.py` → "2 files reformatted, 1 file left unchanged"; `python -m ruff check` on the three → "All checks passed!". (Established 7B precedent: the lead runs the formatter on test files when the subagent's environment denies `ruff`.) |
| Tests — DISPUTE adjudicated | RESOLVED | `test-author` raised `DISPUTE: tests/test_scoring.py::test_midrank_golden_vectors — plan §9 lists (5.0, (2.0,2.0,2.0)) → 0.0, SRS §8.1 gives 1.0`. The lead upheld the test: `L=3, E=0, m=3` → `1.0`. Corrected the frozen plan §9 vector in place with a dated note (plan-document defect, no test edit). |
| Implementation — `impl-deep` dispatch | DONE (with 2 deviations) | Added the Chunk 8 surface to `src/niche_scout/scoring.py` (+636 lines, additive): the five typed structures + `COMPONENT_WEIGHT_KEYS` and the 11 functions. `pytest tests/test_scoring.py -q` → 31 passed; full suite → 325 passed. Two deviations reported: (a) a `0.0 < coverage < threshold` special case in the D/R/Q gates; (b) `= None` defaults added to `NormalizedValues`/`ComponentValues` fields. Both contradicted frozen plan §5. |
| Implementation — test defects corrected | DONE | Lead reviewed the tests against plan §5 and found three `test-author` defects: `coverage_zero → 0.5` vectors contradicting SRS §7.5/§9.1; `_normalized(**fields)` requiring field defaults the plan forbids; a `FIELD_USABLE_COUNT_VECTORS` tuple/test shape mismatch. Dispatched `test-author` (tests only): removed the `coverage_zero` vectors and corrected both docstrings, made `_normalized` construct all six fields explicitly, re-shaped the fixture rows to carry the run. No node or marker changed. |
| Implementation — `impl-deep` fix round | DONE | Dispatch 2 (resume): replaced `0.0 < coverage < threshold` with `coverage < threshold` in `demand_component`/`recent_supply_component`/`quality_component` (+ docstrings), and removed the field defaults from `NormalizedValues`/`ComponentValues`. Public signatures unchanged. |
| Lead verification (step 6) | DONE | `python -m pytest -q` → **325 passed, 0 failed** (re-run by the lead). `python -m pytest tests/test_scoring.py -q` → **31 passed**. `python -m niche_scout.tools.check_import_boundaries` → exit 0, "Import boundaries valid for metrics.py, scoring.py". `python -m niche_scout.tools.validate_traceability` → exit 0, "285 matrix nodes, 89 defined LREQ IDs" (7 pre-existing unmarked tests). `python -m ruff check` on the three files → "All checks passed!"; `python -m ruff format --check` → "3 files already formatted" (lead ran `ruff format tests/test_scoring.py` once; whitespace only, suite re-run green). |
| Implementation commit | DONE | `git add src/niche_scout/scoring.py tests/test_scoring.py tests/fixtures/scoring_fixtures.py` then `chunk-8: implementation` (`d21be49`). |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 | `VERDICT: PASS`, no Blocker, no Major. It read `scoring.py` (679 lines), `test_scoring.py` (1002 lines), `scoring_fixtures.py` (1046 lines), the plan, SRS §7.5/§8/§9.1/§14, the dependency map, the interfaces, and `check_import_boundaries.py`. It re-derived 31 nodes / 37 lreq marks / 31 traceability entries by query. Commands: `pytest -q` → 325 passed; `check_import_boundaries` → exit 0; `validate_traceability` → exit 0; `ruff check` / `format --check` on the three Chunk 8 files → clean. It verified commit `d21be49` only replaced tests that contradicted the SRS and weakened no assertion. |
| Round-1 Minors | (1) `score_category` calls `balanced_composite`, which re-validates the constant weights on every call — harmless redundancy, no behavior impact. **Not fixed** (Minor, no loop). |
| Lead closure of the reviewer's UNVERIFIED items | (a) Single-sub-signal `R` re-derived directly against the code: share-only → `0.09999999999999998`, age-only → `0.19999999999999996`, both → `0.13`, each matching `R_ONE_SUBSIGNAL_VECTORS` within `1e-9`. (b) The 7 unmarked tests named by `validate_traceability` are all `tests/test_collector.py` / `tests/test_sampling.py` nodes — none is a Chunk 8 node (all 31 chunk-8 nodes carry markers). (c) Import audit by AST: `['__future__','collections','dataclasses','datetime','math','metrics','models']`; no forbidden module; `datetime.now` / `utcnow` / `time.time` / `random.` occurrences all `0`. |
| Fix rounds used | 0 of 2. No review-fix commit was needed. |

### Gate — Chunk 8

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3
Chunk 8 (Gate section, lines 876–882), on commit `d21be49` (working tree clean
except for this run log; the implementation commit is `d21be49`).

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. A category never appears in its own LOO reference | PASS | `leave_one_out_reference` (`src/niche_scout/scoring.py:318`) builds `peers = [entry for entry in all_metrics if entry.category != target_category]`; a duplicate-category run raises `ValueError` (`:310–311`). `test_leave_one_out_reference_excludes_target` (`tests/test_scoring.py:158`) and `test_leave_one_out_reference_rejects_absent_or_duplicate_target` (`:265`) pass. |
| 2. A 21-category run stores reference size 20 | PASS | `reference_size=len(all_metrics) - 1` (`scoring.py:330`); `test_eight_and_twenty_one_category_run_reference_sizes` (`test_scoring.py:204`) asserts `strong.reference_size == 20` and `!= 21`, and `strong.demand_per_asset_raw == STRONG_REFERENCE_EXPECTED_DEMAND` (20 peers). The persistence half is Chunk 10 (`interfaces/chunk-02.md`); Chunk 8 computes the pure value. |
| 3. Fewer than two components produces an unavailable score | PASS | `renormalized_composite` (`scoring.py:591–597`) returns `market_opportunity_score=None`, `score_state=ScoreState.UNAVAILABLE`, `W_A` still reported when `available_count < 2`. `test_fewer_than_two_components_score_unavailable` (`test_scoring.py:710`) covers 1 and 0 components. |
| 4. Balanced primary scoring exactly matches balanced sensitivity weights | PASS | `balanced_composite` (`scoring.py:615–628`) uses `{"D": W_D, "C": W_C, "R": W_R, "Q": W_Q}`; `models.W_*` are `0.35/0.30/0.20/0.15` and `models.SENSITIVITY_POLICIES["balanced"]` is the same mapping. `test_balanced_primary_matches_balanced_sensitivity_policy` (`test_scoring.py:799`) asserts equality for every composite vector. |
| 5. `score_state` is distinct from `rankability_status` | PASS | `ScoreResult` (`scoring.py:63–73`) keeps both fields separate; `score_category` (`:667–675`) sets `score_state` and never assigns `rankability_status`/`evidence_grade` (left at Chunk 0 defaults). `test_score_state_field_is_distinct_from_rankability_status` (`test_scoring.py:857`) asserts `unavailable`/`partial` states are not rankability values. |

Supporting evidence: `python -m pytest -q` → **325 passed, 0 failed**;
`python -m pytest tests/test_scoring.py -q` → **31 passed**;
`python -m niche_scout.tools.validate_traceability` → exit 0 ("285 matrix nodes,
89 defined LREQ IDs"; 7 pre-existing unmarked tests, none a Chunk 8 node);
`python -m niche_scout.tools.check_import_boundaries` → exit 0;
`python -m ruff check` on the three Chunk 8 files → "All checks passed!";
`python -m ruff format --check` → "3 files already formatted".

**GATE: PASSED**

### Interface produced

`Documents/interfaces/chunk-08.md` (Status: VERIFIED) created from the frozen plan §5.
Consumers: Chunks 9A, 9B, 10, 11, 12.

### Open items carried forward (not gate failures)

- Reviewer Minor 1: `score_category` re-validates the constant weights through
  `balanced_composite` on every call (harmless redundancy).
- LREQ-NRM-020's persistence half (`reference_size`,
  `reference_usable_counts_json` columns) is Chunk 10's; Chunk 8 produces the pure
  values only.
- The below-threshold `D`/`R`/`Q` unavailability is implemented per the SRS
  §7.5/§9.1 ruling, applied uniformly with no `0.0` special case (that was a
  `test-author`/`impl-deep` deviation corrected in this chunk); the rankability
  consequence remains Chunk 9A's.
- One plan-document defect was corrected in place (midrank all-equal vector
  `(5.0, (2,2,2))` expected `1.0`, not the transcribed `0.0`); the test asserted the
  SRS value.
- `tests/test_scoring.py` is 1002 lines, past the ~800–1000-line review trigger:
  a proposed split along the LREQ clusters (`LREQ-NRM-*` normalization vs
  `LREQ-SCR-*` components/composite) is a human/plan decision and must not rename or
  duplicate a pytest node ID.
- Repo-wide `ruff` debt outside the Chunk 8 files is pre-existing and unchanged.
