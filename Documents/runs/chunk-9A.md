# Chunk 9A — run log (Pre-sensitivity evidence checks and immutable base candidates)

Started 2026-09-21. Branch: `chunk-9A` (created from `main`, HEAD `153042d`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status --short --branch` → `## main`) |
| Branch | `chunk-9A` created from `main` (HEAD `153042d`) |
| Prerequisite Chunk 8 | `Documents/runs/chunk-08.md` ends `GATE: PASSED` (line 70); interface `Status: VERIFIED` |
| Prerequisite Chunk 7B | `Documents/interfaces/chunk-7B.md` → `Status: VERIFIED`; run log `GATE: PASSED` |
| Prerequisite Chunk 6A | `Documents/interfaces/chunk-6A.md` → `Status: VERIFIED`; run log `GATE: PASSED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` |
| Prerequisite Chunk 3 | `Documents/interfaces/chunk-03.md` → `Status: VERIFIED` |
| Baseline suite | `python -m pytest -q` → **400 passed in 13.26s** |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan — dispatch 1 | INCOMPLETE (step limit) | `chunk-planner` hit its 40-step limit after research; **wrote no plan file**. Returned 6 open questions and a 9–20-category reading. |
| Plan — advisory memo | DONE | Lead dispatched `explore` (`ses_f3ad85223ffee3RM6k1RiZ1FQo`) for an independent SRS-backed memo. Q3/Q5/Q6 and the 9–20 reading judged settled by quoted lines; Q1/Q2/Q4 structural readings needing a ruling. |
| Plan — lead rulings recorded | DONE | R1–R10 recorded in this log's rulings section and in the run log at the time; lead opened the cited SRS/dependency-map lines itself. |
| Plan — re-dispatch | DONE (BLOCKED on Q1) | `chunk-planner` wrote `Documents/plans/chunk-9A-pre-sensitivity-evidence-and-base-candidates.md` (DRAFT) and returned `STATUS: BLOCKED` on field-specific reference support (Q1); Q2/Q3/Q4 also open. It also corrected the brief's reversed traceability direction: `tests/traceability.json` is keyed **node → LREQ array**. |
| Plan — Q1–Q4 rulings | DONE | Lead ruled: Q1 option (b) strict per-consumed-field with a keyword-only availability signature; Q2 `SUFFICIENT`/`PROVISIONAL_ONLY`/`INSUFFICIENT`; Q3 `COMPETITION_...` fires on `score.component_c is None`, `INCOMPLETE_BREADTH_FALLBACK` fires regardless of `discovery_bounded_by_verified_total`; Q4 `INSUFFICIENT` counts as preflight failure. Re-dispatched the planner, which set `Status: FROZEN (2026-09-21)` with no open question. |
| Plan commit | DONE | `21b36bc` — `chunk-9A: plan` (plan + this run log). |
| Tests — `test-author` dispatch 1 | TIMEOUT | Provider timeout; resumed the same session. |
| Tests — `test-author` resume | INCOMPLETE | Wrote `tests/test_scoring_evidence.py` (36 nodes), `tests/fixtures/scoring_evidence_fixtures.py`, the `tests/fixtures/__init__.py` re-export, and 36 `tests/traceability.json` entries. Pre-implementation failure shape confirmed by the lead: `ImportError: cannot import name 'BaseCandidateSet' from 'niche_scout.scoring'` (a clean missing-implementation failure, not a syntax/collection error in the test file). |
| Tests — lead lint fix | DONE | `python -m ruff check --fix` + `python -m ruff format` on the two test files and `tests/fixtures/__init__.py`; removed an `__all__` entry for a non-existent fixture symbol (`PROVISIONAL_EXPECTED_VALUES`) and two long lines. `ruff check` → "All checks passed!"; `ruff format --check` → "3 files already formatted". |
| Tests — traceability validator note | DONE | `python -m niche_scout.tools.validate_traceability` → exit 0, "422 matrix nodes, 89 defined LREQ IDs". The test-author's claim that `LREQ-EVD-*` markers would be rejected was **not** reproducible (SRS Appendix B already declares the `LREQ-EVD-*` prefix); see the validator revert below. |
| Tests commit | DONE | `53263ab` — `chunk-9A: tests`. |
| Validator edit (out of plan) | REVERTED | The lead had added grouped-prefix parsing to `src/niche_scout/tools/validate_traceability.py` (`877cbc5`) on the test-author's unverified claim. The lead then re-derived the original `WILDCARD_PATTERN` against SRS Appendix B: it already matches all 15 prefixes and yields 89/89 defined IDs, so the edit was unnecessary and outside the plan's files-touched. Reverted in `f74e6dd`; `git diff 53263ab -- src/niche_scout/tools/validate_traceability.py` is empty and the validator still passes. |
| Implementation — `impl-deep` dispatch | COMPLETED (no result block) | The subagent wrote the additive surface to `src/niche_scout/scoring.py` but returned an empty result block, so the lead verified the state directly: `pytest tests/test_scoring_evidence.py -q` → 6 failed, 30 passed. |
| Implementation — failure triage | DONE | All six failures were test/fixture defects or a plan-vector defect, not implementation defects: (a) `FIELD_REFERENCE_SUPPORT_VECTORS`(i) expected the lenient rule while matrix row expected the strict rule (fixture self-contradiction); (b) `PROVISIONAL_COVERAGE_VECTORS` 0.50 expected no reason, contradicting LREQ-EVD-030 line 999; (c) two misaligned input-tuple constructions; (d) `base_rankable is True` asserted for a 20-category run; (e) a `PARTIAL`-score distinctness vector that produced `RANKABLE`. |
| Plan — in-place vector corrections | DONE | Lead corrected the frozen plan §9 with dated notes: field-support vector (i) → `False` (strict rule; the clause is additive to "all four components available"), coverage `0.50` → fires `COVERAGE_BELOW_STRONG`. Commit `540e770`. |
| Tests — `test-author` fix dispatch | DONE (after 2 provider errors) | Applied all seven adjudicated fixes to the two test files only; no node name, marker, or traceability entry changed. `pytest tests/test_scoring_evidence.py -q` → **36 passed, 0 failed**; full suite → **436 passed**; validator valid. |
| Implementation commit | DONE | `git add src/niche_scout/scoring.py tests/test_scoring_evidence.py tests/fixtures/scoring_evidence_fixtures.py` then `chunk-9A: implementation` (`6e7c745`); plan corrections `540e770`; validator revert `f74e6dd`. |
| Lead verification (step 6) | DONE | `python -m pytest -q` → **436 passed, 0 failed**; `python -m pytest tests/test_scoring_evidence.py -q` → **36 passed**; `validate_traceability` → exit 0 ("422 matrix nodes, 89 defined LREQ IDs"); `check_import_boundaries` → exit 0 ("Import boundaries valid for metrics.py, scoring.py"); `ruff check` on the three Chunk 9A files → "All checks passed!"; `ruff format --check` → "3 files already formatted" (lead ran `ruff format src/niche_scout/scoring.py` once; whitespace only, suite re-run green). |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 | `VERDICT: PASS`, no Blocker, no Major. It read the frozen plan (870 lines incl. both corrections), the base→branch diff, both test files (1,477 + 728 lines), `tests/traceability.json` additions, and the SRS sections §9.1 lines 965–1030, §7.3 lines 740–775, §4.1 lines 255–284, §8.2 lines 890–951, Appendix B, §14. It re-ran all five commands and got 436 passed / validator valid / import boundaries valid / ruff clean / formatted. It verified purity, null-vs-zero, no mutation, chunk boundary, determinism, and that no test was deleted, weakened, or tolerance-loosened. |
| Round-1 Minors | (1) `src/niche_scout/tools/validate_traceability.py` was edited though outside plan §6 → **resolved**: reverted in `f74e6dd`, re-verified. (2) The implementation commit edited test expectations authored earlier → **documented** in the triage/fix rows above with the SRS/plan basis; no assertion weakened. (3) `provisional_reasons` accepts an unused `score` parameter for signature stability per the frozen plan §5 → **not fixed** (Minor, no loop). |
| Fix rounds used | 0 of 2. No review-fix commit was needed. |

### Interface produced

`Documents/interfaces/chunk-9A.md` (Status: VERIFIED) created from the frozen plan §5.
Consumers: Chunks 9B, 10, 11, 12.

### Gate — Chunk 9A

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3 Chunk 9A
(Gate section, lines 912–917), on commit `f74e6dd` (working tree otherwise clean).

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. The base candidate set is frozen before any alternate policy is ranked | PASS | No sensitivity input exists anywhere in the Chunk 9A surface (`git diff base..HEAD -- src/niche_scout/scoring.py` adds no policy weight/stability name; `interfaces/chunk-9A.md` §"Explicitly not produced here"). `build_base_rankable_candidates` (`src/niche_scout/scoring.py:1113`) constructs the tuple only from the LREQ-EVD-020 rules and is called before any policy. Tests `test_base_candidate_set_is_fixed_input_to_sensitivity` (`tests/test_scoring_evidence.py:1277`) and `test_pre_sensitivity_state_excludes_sensitivity_high_reason` (`:1244`) pass. |
| 2. Score state, pre-sensitivity evidence state, and preliminary rankability status remain distinct | PASS | `PreSensitivityEvidenceState` (`scoring.py:777`) and `PreSensitivityRankabilityState` (`:757`) are separate `StrEnum`s, neither is `models.EvidenceGrade` nor `models.RankabilityStatus`, and `PreSensitivityDecision` (`:818`) carries both plus `base_rankable` and the reason tuples; `ScoreResult.score_state` is read only. Tests `test_pre_sensitivity_rankability_state_is_not_final_rankability_status` (`:217`) and `test_score_state_and_rankability_state_remain_distinct` (`:1003`) pass. |
| 3. Categories with insufficient support are excluded from the base candidate set without changing their stored score fields | PASS | `build_base_rankable_candidates` reads `scores` and appends a category only when `decision.base_rankable` (`scoring.py:1154–1169`); it never sorts or rebuilds a `ScoreResult`. Test `test_base_candidate_construction_does_not_change_score_fields` (`tests/test_scoring_evidence.py:892`) compares every field before/after and passes; `test_base_rankable_candidates_require_all_components_and_coverage` (`:817`) passes. |
| 4. No final evidence grade is persisted by this chunk when sensitivity is an input to the final grade | PASS | The Chunk 9A region assigns neither `evidence_grade` nor `rankability_status` (grep over the added lines → 0 assignments; `interfaces/chunk-9A.md` non-scope section). `evaluate_pre_sensitivity_evidence` returns only the internal states (`scoring.py:1097–1110`). Test `test_scoring_evidence_module_is_import_pure_and_clock_free` (`:1340`) passes; no persistence/JSON/DB code is added. |

Supporting evidence: `python -m pytest -q` → **436 passed, 0 failed**;
`python -m pytest tests/test_scoring_evidence.py -q` → **36 passed**;
`python -m niche_scout.tools.validate_traceability` → exit 0 ("7 Chunk 0 requirements
mapped, 422 matrix nodes, 89 defined LREQ IDs"; 7 pre-existing unmarked
collector/sampling tests, none a Chunk 9A node);
`python -m niche_scout.tools.check_import_boundaries` → exit 0;
`python -m ruff check` on the three Chunk 9A files → "All checks passed!";
`python -m ruff format --check` → "3 files already formatted".

**GATE: PASSED**

### Open items carried forward (not gate failures)

- Reviewer Minor 3: `provisional_reasons(score, ...)` accepts `score` for the frozen
  plan §5 signature and does not read it; a future interface revision could drop it.
- The plan's §9 node list transcribed 37 nodes; the delivered test file has 36
  distinct nodes and `tests/traceability.json` has 36 matching entries. The
  validator reports no missing node, mismatch, or orphan, so the matrix and tests
  agree; the 37 was a plan-document count and is not a gate criterion.
- `LREQ-EVD-020`'s orchestration-status half (the `pipeline.py` column, completion
  Chunk 10) is deliberately untouched; Chunk 9A keeps the decision pure.
- The strict field-reference-support predicate and the `0.50` coverage boundary are
  lead rulings on SRS-silent/ambiguous points, recorded in plan §9/§12 with dated
  notes; if a human re-ratifies them differently, `scoring.py`, the fixtures, and
  the plan must move together.