# Chunk 9B — run log (Sensitivity, final evidence, and final rankability)

Started 2026-09-21. Branch `chunk-9B` created from `chunk-9A` tip (`8eab2fb`).
Tree clean at preflight (`git status --short --branch` → `## chunk-9A`).
`main` is at `153042d` and does **not** contain the Chunk 9A work; Chunk 9B depends
on Chunk 9A, so the branch was cut from the `chunk-9A` tip rather than `main`.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status --short --branch` → `## chunk-9A`) |
| Branch | `chunk-9B` created from `chunk-9A` tip `8eab2fb` (9A not yet merged to `main`) |
| Prerequisite Chunk 9A | `Documents/runs/chunk-9A.md` ends `GATE: PASSED` (line 78); interface `Status: VERIFIED` |
| Prerequisite Chunk 8 | `Documents/runs/chunk-08.md` ends `GATE: PASSED` (line 70); interface `Status: VERIFIED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` (page-view semantics consumed) |
| Baseline suite | `python -m pytest -q` → **436 passed, 0 failed** |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan — dispatch 1 | BLOCKED | `chunk-planner` wrote the full 862-line plan (DRAFT) with 8 open questions in §12; commit pending until frozen. |
| Plan — advisory memo | DONE | Read-only `explore` (`ses_f3a53e1e1ffegEt1R6b8WxD9D0`) researched all 8 questions against the SRS, dependency map, frozen interfaces, and live source; returned cited recommendations for Q1–Q8 with confidence labels. |
| Plan — lead rulings R1–R8 | DONE | Rulings recorded below; all eight follow the memo. Re-dispatched `chunk-planner` to apply them and freeze. |
| Plan commit | DONE | `b7819ed` — `chunk-9B: plan` (frozen plan + this run log). |
| Plan — lead consistency fix | DONE | Plan §12 R2 named a non-existent test node; corrected in place before commit (the §9 marker table and `tests/traceability.json` block — which agree with each other — govern). |
| Tests — `test-author` dispatch 1 | FAILED (empty) | Returned an empty result and wrote no files (session `ses_f3a3b8f65ffepjqolTmgue07I5`). |
| Tests — `test-author` retry | FAILED (empty) | Same session resumed and one fresh session (`ses_f3a282c4bffevdEZxta4t60oxS`) both returned empty with no files written. |
| Tests — `test-author` scoped dispatch (fixtures) | DONE | Small-scope session (`ses_f3a1cde9dffeDUzY7d6pJzKWef`) wrote `tests/fixtures/sensitivity_fixtures.py` (1089 lines, data-only); the earlier empties were a task-size/step failure, not a provider outage. Raised 3 plan-vector inconsistencies. |
| Plan — vector corrections | DONE | Lead corrected the frozen plan in place with dated notes: the §9 top-3 vector's false "every candidate breaches displacement" wording; the displacement vector's self-contradictory equal-top-3-set sentence (now `T3b=T3d={c1,c2,c3}`, `T3c={c8,c1,c2}`); the weak vector's "coverage 0.60 → WEAK" claim (a sufficient count with coverage ≥0.50 is MODERATE per SRS §9.2). |
| Tests — `test-author` scoped dispatch (test file) | DONE | Session `ses_f39fd7016ffefu4dFJndiU7O5K` wrote `tests/test_scoring_sensitivity.py` (39 nodes), updated `tests/fixtures/__init__.py`, and appended 39 entries to `tests/traceability.json`. Node count corrected to **39** (the plan §9 table and JSON block both have 39 rows; my earlier 38 was an estimate error). |
| Tests — lead verification (step 4) | DONE | `python -m pytest tests/test_scoring_sensitivity.py -q` → 1 collection ERROR: `ImportError: cannot import name 'CategorySensitivityRank' from 'niche_scout.scoring'` (required missing-implementation shape; module parsed with no syntax error). `python -m pytest tests -q --ignore=tests/test_scoring_sensitivity.py` → 436 passed. `validate_traceability` → valid, 461 matrix nodes. Node/entry counts queried: `^def test_` → 39; `test_scoring_sensitivity.py::` in traceability → 39; names match 1:1. `ruff check` → "All checks passed!"; lead ran `ruff format` (2 files reformatted, whitespace only). |
| Tests commit | DONE | `625eb09` — `chunk-9B: tests` (test module, fixtures, `__init__` re-export, traceability entries, run log). |
| Implementation — `impl-deep` dispatch | DONE (with 2 test disputes) | Session `ses_f39ec0dcaffeCkv4A2hlZswl5k` added the additive Chunk 9B surface to `src/niche_scout/scoring.py`. `pytest tests/test_scoring_sensitivity.py -q` → 38 passed, 1 failed; full suite → 473 passed, 2 failed. Both failures were test artifacts, not implementation defects. |
| Implementation — dispute 1 | RESOLVED (test defect) | `test_sensitivity_warning_top_three_boundary` compared the per-category `expected_max_rank_displacement` dict to the float `displacement_threshold`; the run-level scalar is `expected_maximum_rank_displacement`. Implementation correct; test-author fixed. |
| Implementation — dispute 2 | RESOLVED (stale Chunk 9A expectation) | `test_scoring_evidence.py::test_base_candidate_set_is_fixed_input_to_sensitivity` asserted `final_evidence_grade`/`final_rankability_status` were absent; Chunk 9B plan §5 legitimately adds them. Fixture `NO_RANKABLE_SURFACE` reduced to `("compute_sensitivity",)` (correctly still absent; the 9B name is `evaluate_sensitivity`). |
| Tests — `test-author` fix dispatch | DONE | Session `ses_f39e6e876ffeNZceazhIS0zpfG` fixed the two artifacts. `pytest tests/test_scoring_sensitivity.py -q` → 39 passed; `tests/test_scoring_evidence.py -q` → 36 passed; full suite → 475 passed. No node ID/marker/traceability entry changed. |
| Lead verification (step 6) | DONE | `python -m pytest -q` → **475 passed, 0 failed** (re-run by the lead). `validate_traceability` → valid, 461 matrix nodes, 89 defined LREQ IDs (7 pre-existing unmarked collector/sampling tests, none a Chunk 9B node). `check_import_boundaries` → valid for `metrics.py, scoring.py`. `ruff check` on the six changed files → "All checks passed!"; `ruff format --check` → all formatted (lead ran `ruff format tests/test_scoring_sensitivity.py` once; whitespace only, suite re-run green). |
| Implementation commits | PENDING | source + adjudicated test fixes. |
| Review — `spec-reviewer` | DONE | Session `ses_f39e0d219ffes2x2LYlwFqSRxz` returned `VERDICT: PASS`, no Blocker, no Major. It re-read the SRS §9.1–§9.3/§7.3/§6.5/§13/Appendix C, the frozen plan, the implementation, the tests, and the adjudicated edits; independently re-derived the golden vectors; re-ran the suite and tooling. |
| Fix rounds used | 0 of 2 | No review-fix commit was needed. |
| Interface produced | DONE | `Documents/interfaces/chunk-9B.md` (Status: VERIFIED) created from the frozen plan §5. Consumers: Chunks 10, 11, 12, 13. |
| Gate | PASSED | See gate table below. |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 | `VERDICT: PASS`, no Blocker, no Major. Commands re-run by the reviewer: `pytest -q` → 475 passed; `pytest tests/test_scoring_sensitivity.py -q` → 39 passed; `validate_traceability` → valid, 461 matrix nodes; `check_import_boundaries` → valid; `ruff check`/`format --check` on the changed files → clean. It verified candidate-set immutability, balanced-score preservation, the null contract, determinism, the R2–R8 warning/evidence/rankability rules, purity, and that no assertion was weakened. |
| Round-1 Minors | (1) `final_evidence_grade` uses `all(coverage >= …)` and would raise `TypeError` (not a typed `ValueError`) on a `None`/NaN coverage; the frozen `PreSensitivityCategoryInput` types coverages non-nullable and the SRS case is handled by `not_rankable` before grading → **not fixed** (Minor, no loop). (2) The purity test does not directly assert `"sampling"` absent from `scoring.py` imports, though it is absent → **not fixed** (Minor, no loop). (3) The `NO_RANKABLE_SURFACE` reduction was verified justified against the frozen 9A/9B interfaces → **accepted**. |
| Reviewer UNVERIFIED | The `python -m ruff` invocation form was permission-denied; the reviewer ran the equivalent `ruff` binary on the changed files (clean). Repo-wide pre-existing ruff debt is outside this chunk and unchanged. |

### Gate — Chunk 9B

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3 Chunk 9B
(Gate section, lines 947–954), on commit `711b0cf` (working tree clean except this run log
and the interface file).

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. Sensitivity never adds or removes candidates | PASS | `evaluate_sensitivity` iterates only `base_candidates.base_rankable_candidates` (`src/niche_scout/scoring.py:1452–1458`) and returns `ranked_categories=candidates` unchanged (`:1525`); `ranked_under_policy` ranks exactly the supplied `candidates` (`:1384–1396`). Tests `test_sensitivity_ranks_only_fixed_candidates` and `test_sensitivity_does_not_add_or_remove_candidates` pass. |
| 2. Sensitivity never modifies the balanced primary score | PASS | The balanced score is recomputed by `ranked_under_policy` and only read from `score_maps` (`scoring.py:1463–1469, 1483`); no `ScoreResult` field is assigned. Tests `test_sensitivity_preserves_balanced_primary_score` (equality within `1e-9`) and `test_sensitivity_warning_does_not_alter_balanced_score` pass. |
| 3. A sensitivity warning demotes final rankability only as specified | PASS | `final_rankability_status` returns `RANKABLE` iff `sensitivity_warning is False`, else `PROVISIONAL`; `NOT_RANKABLE` is never overridden (`scoring.py:1650–1656`). Tests `test_final_rankability_sensitivity_demotes_to_provisional`, `test_final_rankability_never_demotes_to_not_rankable`, and `test_final_rankability_null_warning_is_provisional` pass. |
| 4. Insufficient candidate counts produce the explicitly defined null outputs | PASS | Empty set ⇒ every run-level stability/displacement/warning `None` with `categories == ()` (`scoring.py:1475–1476, 1518–1521`); `top_k_stability` is `None` below `k`. Tests `test_sensitivity_top_k_null_when_too_few_candidates`, `test_sensitivity_empty_candidate_set_null_outputs`, and `test_sensitivity_warning_is_none_only_without_candidates` pass. |
| 5. `final_evidence_grade` and `final_rankability_status` are assigned here after sensitivity; Chunk 10 persists the complete result | PASS | Both functions are implemented (`scoring.py:1537, 1627`) and take `sensitivity_warning` as an input; `scoring.py` performs no persistence/serialization (purity test + `check_import_boundaries` exit 0). Persistence is Chunk 10 per `interfaces/chunk-9B.md` §5. |
| 6. Final rankability is assigned only after sensitivity is computed | PASS | `final_rankability_status` is a distinct function whose only sensitivity input is the completed `evaluate_sensitivity` warning (`scoring.py:1627–1656`); it is never called from within `evaluate_sensitivity`. Tests `test_sensitivity_high_provisional_clause_completes_evd030` and `test_final_rankability_requires_base_and_sensitivity` pass. |

Supporting evidence: `python -m pytest -q` → **475 passed, 0 failed**;
`python -m pytest tests/test_scoring_sensitivity.py -q` → **39 passed**;
`python -m niche_scout.tools.validate_traceability` → valid ("7 Chunk 0 requirements
mapped, 461 matrix nodes, 89 defined LREQ IDs"; 7 pre-existing unmarked
collector/sampling tests, none a Chunk 9B node);
`python -m niche_scout.tools.check_import_boundaries` → exit 0;
`ruff check` on the changed files → "All checks passed!";
`ruff format --check` → all formatted.

**GATE: PASSED**


### Open items carried forward (not gate failures)

- Reviewer Minors 1–2 (defensive `TypeError` vs `ValueError` on a non-nullable
  coverage; an indirect `"sampling"`-absence check) are recorded but not fixed.
- `tests/test_scoring_sensitivity.py` is 1,540 lines and
  `tests/fixtures/sensitivity_fixtures.py` is 1,089 lines, both past the
  ~800–1000-line review trigger. Fixtures are exempt (inert data); the test file's
  one-module scope is plan-fixed, so no split was taken (a split along the
  `SEN-*` vs `EVD-*` clusters would be a human/plan decision and must not rename a
  node ID).
- Chunk 10 must persist `category_scores.sensitivity_warning` and
  `ranking_sensitivity_json` from `SensitivityDiagnostics`, **not** from the frozen
  `SensitivityResult` (whose `warning: bool = False` cannot express `None`); and it
  must supply `SampleEvidenceFacts` from the authoritative persisted columns.
- The four evidence-grade sample-count literals (80/50/40/20) are SRS §9.2 values
  held as private `scoring.py` constants (no public config key); Chunk 12's
  config-precedence chunk should not add a configurable override (out of scope per
  the fixed Lean v1 weights/thresholds rule).

### Plan rulings R1–R8 (Chunk 9B)

SRS is silent or ambiguous on the exact conjunction/boundary in several items; these are
lead rulings, each grounded in cited SRS/dependency-map/interfaces text, not invented
formulas.

- **R1 (`sensitivity_warning` type) — Q1 option (a).** Chunk 9B adds
  `SensitivityDiagnostics.warning: bool | None`; the frozen Chunk 0
  `SensitivityResult.warning: bool` is left byte-identical. Chunk 10 persists from
  `SensitivityDiagnostics.warning` (SRS §6.5 line 607; dependency-map §6.3 line 1161
  "`null` … not `false` or zero"; `models.py:507` `bool | None`).
- **R2 (warning with 1–2 candidates) — Q2 option (a).** The LREQ-SEN-030 condition is a
  disjunction; displacement is computable whenever comparable ranks exist. Per-category
  `warning` is `None` only when there are **zero** base candidates; otherwise `bool`.
  Record explicitly that the top-3 clause is *inapplicable* (not `false`) when
  `top_3_stability is None` (dependency-map §6.3 line 1160).
- **R3 (reference-set size) — Q3 option (a).** `reference_set_size = run_category_count
  - 1` (the leave-one-out peer count; interfaces/chunk-08.md:168), passed explicitly;
  the displacement threshold is `max(3, 0.25 * reference_set_size)`. Caller obligation:
  every supplied per-category `reference_size` must equal the explicit
  `reference_set_size`, else `ValueError`.
- **R4 (which rows carry the top-3 warning) — Q4 option (a).** Each base candidate's
  `warning = (top_3_stability is not None and top_3_stability < 2/3) or its own
  displacement breach`; non-candidates are `None`; the run-level warning is the OR over
  candidates (SRS §9.3 line 1077; §1.2 null discipline).
- **R5 (missing pure contract) — Q5 option (a).** Chunk 9B adds a pure
  `SampleEvidenceFacts` dataclass in `scoring.py`; census/population facts mirror
  `CategorySamplingResult` / the persisted `category_scores` columns, and the three
  `usable_*_sample_count` values mirror `CategoryRawMetrics`. It must not import
  `sampling`; `0` census is an explicit zero (SRS §7.3 lines 769–771).
- **R6 (evidence-grade conjunction) — Q6.** Adopt the plan §5.4 precedence with:
  "verified discovery" = `discovery_filter_verified is True` **and** `discovery_status
  is DiscoveryStatus.COMPLETE`; `sensitivity_warning is None` is **not** acceptable for
  `strong`; the reference condition is `run_category_count >=
  STRONG_REFERENCE_CATEGORY_COUNT` (= 21). `moderate`/`weak`/`insufficient` follow the
  SRS §9.2 table (lines 1049–1052).
- **R7 (rankability on a null warning) — Q7 option (b).** For a pre-sensitivity
  `RANKABLE` category, `sensitivity_warning is None` yields final `PROVISIONAL`
  (conservative; LREQ-EVD-040 line 1007 requires the thresholds *pass*). Under R2/R3
  this branch is unreachable for a base-rankable category (run ≥ 21 ⇒ ≥ 1 candidate),
  but the rule stays defined.
- **R8 (`ranking_sensitivity_json` shape) — Q8 option (a).** The JSON carries only the
  ranked candidate set (`ranked_categories`, per-policy scores/ranks, displacements) plus
  the explicit empty/insufficient-candidate status; non-candidates remain visible via
  their own `category_scores` rows with null rank/displacement/sensitivity fields
  (SRS §9.3 line 1077; dependency-map §6.3 line 1162).

Two plan-text corrections the planner must apply: (i) the `SampleEvidenceFacts`
docstring sources census/population from `CategorySamplingResult`/the persisted row, not
`CategoryRawMetrics`; (ii) add the R3 caller obligation that per-category `reference_size`
values agree with the explicit `reference_set_size`.